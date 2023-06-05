from http.client import HTTPException
import logging
from typing import Iterable, Optional, Sequence

import requests

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

import markupsafe

import bleach
from sciety_labs.app.app_providers_and_models import AppProvidersAndModels
from sciety_labs.app.app_update_manager import AppUpdateManager
from sciety_labs.app.routers.articles import create_articles_router
from sciety_labs.app.routers.lists import create_lists_router
from sciety_labs.app.utils.common import (
    AnnotatedPaginationParameters,
    get_page_title
)
from sciety_labs.config.site_config import get_site_config_from_environment_variables

from sciety_labs.models.article import (
    ArticleSearchResultItem,
    iter_preprint_article_mention
)

from sciety_labs.providers.europe_pmc import EUROPE_PMC_PREPRINT_SERVERS
from sciety_labs.providers.search import SearchDateRange, SearchParameters, SearchSortBy
from sciety_labs.providers.semantic_scholar import (
    SEMANTIC_SCHOLAR_SEARCH_VENUES
)
from sciety_labs.utils.datetime import (
    get_date_as_display_format,
    get_date_as_isoformat,
    get_timestamp_as_isoformat
)
from sciety_labs.utils.pagination import (
    get_url_pagination_state_for_pagination_parameters
)


LOGGER = logging.getLogger(__name__)


ALLOWED_TAGS = [
    'a', 'abbr', 'acronym', 'b', 'blockquote', 'bold',
    'code',
    'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul',
    'h1', 'h2', 'h3', 'p', 'img', 'video', 'div',
    'p', 'br', 'span', 'hr', 'src', 'class',
    'section', 'sub', 'sup'
]


class SearchProviders:
    SEMANTIC_SCHOLAR = 'semantic_scholar'
    EUROPE_PMC = 'europe_pmc'


def get_sanitized_string_as_safe_markup(text: str) -> markupsafe.Markup:
    return markupsafe.Markup(bleach.clean(text, tags=ALLOWED_TAGS))


def create_app():  # pylint: disable=too-many-locals, too-many-statements
    site_config = get_site_config_from_environment_variables()
    LOGGER.info('site_config: %r', site_config)

    update_interval_in_secs = 60 * 60  # 1 hour
    min_article_count = 2

    app_providers_and_models = AppProvidersAndModels()
    article_aggregator = app_providers_and_models.article_aggregator

    app_update_manager = AppUpdateManager(
        app_providers_and_models=app_providers_and_models
    )
    app_update_manager.start(update_interval_in_secs=update_interval_in_secs)

    LOGGER.info('Preloading data')
    app_update_manager.check_or_reload_data()

    templates = Jinja2Templates(directory='templates')
    templates.env.filters['sanitize'] = get_sanitized_string_as_safe_markup
    templates.env.filters['date_isoformat'] = get_date_as_isoformat
    templates.env.filters['date_display_format'] = get_date_as_display_format
    templates.env.filters['timestamp_isoformat'] = get_timestamp_as_isoformat
    templates.env.globals['site_config'] = site_config

    app = FastAPI()
    app.mount('/static', StaticFiles(directory='static', html=False), name='static')

    app.include_router(create_lists_router(
        app_providers_and_models=app_providers_and_models,
        min_article_count=min_article_count,
        templates=templates
    ))
    app.include_router(create_articles_router(
        app_providers_and_models=app_providers_and_models,
        templates=templates
    ))

    @app.exception_handler(404)
    async def not_found_exception_handler(request: Request, exception: HTTPException):
        return templates.TemplateResponse(
            'errors/404.html', {
                'request': request,
                'page_title': get_page_title('Page not found'),
                'exception': exception
            },
            status_code=404
        )

    @app.exception_handler(500)
    async def server_error_exception_handler(request: Request, exception: HTTPException):
        return templates.TemplateResponse(
            'errors/500.html', {
                'request': request,
                'page_title': get_page_title('Something went wrong'),
                'exception': exception
            },
            status_code=500
        )

    @app.get('/', response_class=HTMLResponse)
    def index(request: Request):
        user_list_summary_data_list = list(
            app_providers_and_models
            .google_sheet_list_image_provider.iter_list_summary_data_with_list_image_url(
                app_providers_and_models.lists_model.get_most_active_user_lists(
                    top_n=3,
                    min_article_count=min_article_count
                )
            )
        )
        LOGGER.info('user_list_summary_data_list: %r', user_list_summary_data_list)
        group_list_summary_data_list = list(
            app_providers_and_models
            .google_sheet_list_image_provider.iter_list_summary_data_with_list_image_url(
                app_providers_and_models.lists_model.get_most_active_group_lists(
                    top_n=3,
                    min_article_count=min_article_count
                )
            )
        )
        LOGGER.info('group_list_summary_data_list: %r', group_list_summary_data_list)
        return templates.TemplateResponse(
            'pages/index.html', {
                'request': request,
                'user_lists': user_list_summary_data_list,
                'group_lists': group_list_summary_data_list
            }
        )

    @app.get('/search', response_class=HTMLResponse)
    def search(  # pylint: disable=too-many-arguments, too-many-locals
        request: Request,
        pagination_parameters: AnnotatedPaginationParameters,
        query: str = '',
        evaluated_only: bool = False,
        search_provider: str = SearchProviders.SEMANTIC_SCHOLAR,
        sort_by: str = SearchSortBy.RELEVANCE,
        date_range: str = SearchDateRange.LAST_90_DAYS
    ):
        search_result_iterable: Iterable[ArticleSearchResultItem]
        error_message: Optional[str] = None
        status_code: int = 200
        try:
            preprint_servers: Optional[Sequence[str]] = None
            search_parameters = SearchParameters(
                query=query,
                is_evaluated_only=evaluated_only,
                sort_by=sort_by,
                date_range=date_range
            )
            LOGGER.info('search_parameters: %r', search_parameters)
            if not query:
                search_result_iterable = []
            elif search_provider == SearchProviders.SEMANTIC_SCHOLAR:
                search_result_iterable = (
                    app_providers_and_models
                    .semantic_scholar_search_provider.iter_search_result_item(
                        search_parameters=search_parameters
                    )
                )
                preprint_servers = SEMANTIC_SCHOLAR_SEARCH_VENUES
            elif search_provider == SearchProviders.EUROPE_PMC:
                search_result_iterable = (
                    app_providers_and_models
                    .europe_pmc_provider.iter_search_result_item(
                        search_parameters=search_parameters
                    )
                )
                preprint_servers = EUROPE_PMC_PREPRINT_SERVERS
            else:
                search_result_iterable = []
            search_result_iterator = iter(search_result_iterable)
            search_result_list_with_article_meta = list(
                article_aggregator.iter_page_article_mention_with_article_meta_and_stats(
                    iter_preprint_article_mention(
                        search_result_iterator
                    ),
                    page=pagination_parameters.page,
                    items_per_page=pagination_parameters.items_per_page
                )
            )
            LOGGER.info(
                'search_result_list_with_article_meta[:1]=%r',
                search_result_list_with_article_meta[:1]
            )
        except requests.exceptions.HTTPError as exc:
            error_message = f'Error retrieving search results from provider: {exc}'
            status_code = exc.response.status_code
            search_result_list_with_article_meta = []
            search_result_iterator = iter([])
        url_pagination_state = get_url_pagination_state_for_pagination_parameters(
            url=request.url,
            pagination_parameters=pagination_parameters,
            is_this_page_empty=not search_result_list_with_article_meta,
            remaining_item_iterable=search_result_iterator
        )
        return templates.TemplateResponse(
            'pages/search.html', {
                'request': request,
                'page_title': (
                    f'Search results for {query}' if query else 'Search'
                ),
                'query': query,
                'is_search_evaluated_only': evaluated_only,
                'sort_by': sort_by,
                'date_range': date_range,
                'preprint_servers': preprint_servers,
                'error_message': error_message,
                'search_provider': search_provider,
                'search_results': search_result_list_with_article_meta,
                'pagination': url_pagination_state
            },
            status_code=status_code
        )

    return app
