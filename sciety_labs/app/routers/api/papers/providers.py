import logging
from typing import List, Mapping, Optional, Sequence, Set, cast

import opensearchpy

from sciety_labs.app.app_providers_and_models import AppProvidersAndModels
from sciety_labs.app.routers.api.papers.typing import (
    PaperAttributesDict,
    PaperDict,
    PaperResponseDict,
    PaperSearchResponseDict,
    ClassificationDict,
    ClassificationResponseDict
)
from sciety_labs.models.article import InternalArticleFieldNames, KnownDoiPrefix
from sciety_labs.providers.opensearch.typing import (
    DocumentDict,
    OpenSearchSearchResultDict
)
from sciety_labs.providers.opensearch.utils import (
    IS_ARTICLE_DOI_TO_BE_DISPLAYED_OPENSEARCH_FILTER_DICT,
    OPENSEARCH_FIELDS_BY_REQUESTED_FIELD,
    OpenSearchFilterParameters,
    OpenSearchPaginationParameters,
    OpenSearchSortField,
    OpenSearchSortParameters,
    get_article_meta_from_document,
    get_article_stats_from_document,
    get_opensearch_filter_dicts_for_filter_parameters,
    get_source_includes_for_mapping
)
from sciety_labs.providers.opensearch.utils import (
    IS_BIORXIV_MEDRXIV_DOI_PREFIX_OPENSEARCH_FILTER_DICT
)
from sciety_labs.utils.datetime import get_date_as_isoformat
from sciety_labs.utils.json import get_recursively_filtered_dict_without_null_values
from sciety_labs.utils.mapping import get_flat_mapped_values_or_all_values_for_mapping


LOGGER = logging.getLogger(__name__)


INTERNAL_ARTICLE_FIELDS_BY_API_FIELD_NAME: Mapping[str, Sequence[str]] = {
    'doi': [InternalArticleFieldNames.ARTICLE_DOI],
    'title': [InternalArticleFieldNames.ARTICLE_TITLE],
    'publication_date': [InternalArticleFieldNames.PUBLISHED_DATE],
    'evaluation_count': [InternalArticleFieldNames.EVALUATION_COUNT],
    'has_evaluations': [InternalArticleFieldNames.EVALUATION_COUNT],
    'latest_evaluation_activity_timestamp': [
        InternalArticleFieldNames.LATEST_EVALUATION_ACTIVITY_TIMESTAMP
    ]
}


DEFAULT_OPENSEARCH_SEARCH_FIELDS = [
    'doi',
    'calculated.title_with_markup',
    'calculated.abstract_with_markup'
]


class DoiNotFoundError(RuntimeError):
    def __init__(self, doi: str):
        self.doi = doi
        super().__init__(f'DOI not found: {doi}')


def get_classification_list_opensearch_query_dict(
    filter_parameters: OpenSearchFilterParameters
) -> dict:
    filter_dicts: List[dict] = [
        IS_ARTICLE_DOI_TO_BE_DISPLAYED_OPENSEARCH_FILTER_DICT,
        IS_BIORXIV_MEDRXIV_DOI_PREFIX_OPENSEARCH_FILTER_DICT
    ]
    filter_dicts.extend(get_opensearch_filter_dicts_for_filter_parameters(
        filter_parameters=filter_parameters
    ))
    return {
        'query': {
            'bool': {
                'filter': filter_dicts
            }
        },
        'aggs': {
            'group_title': {
                'terms': {
                    'field': 'crossref.group_title.keyword',
                    'size': 10000
                }
            }
        },
        'size': 0
    }


def get_paper_search_query_opensearch_multi_match_query_dict(
    query: str
) -> dict:
    LOGGER.debug('query: %r', query)
    return {
        'query': query,
        'fields': DEFAULT_OPENSEARCH_SEARCH_FIELDS,
        'prefix_length': 3
    }


def get_paper_search_query_opensearch_must_query_dict(
    query: str
) -> dict:
    return {
        'multi_match': get_paper_search_query_opensearch_multi_match_query_dict(
            query=query
        )
    }


def get_paper_search_by_category_opensearch_query_dict(
    filter_parameters: OpenSearchFilterParameters,
    sort_parameters: OpenSearchSortParameters,
    pagination_parameters: OpenSearchPaginationParameters,
    query: Optional[str] = None
) -> dict:
    filter_dicts: List[dict] = [
        IS_ARTICLE_DOI_TO_BE_DISPLAYED_OPENSEARCH_FILTER_DICT
    ]
    filter_dicts.extend(get_opensearch_filter_dicts_for_filter_parameters(
        filter_parameters=filter_parameters
    ))
    LOGGER.info('filter_dicts: %r', filter_dicts)
    query_dict: dict = {
        'query': {
            'bool': {
                'filter': filter_dicts
            }
        },
        'size': pagination_parameters.page_size,
        'from': pagination_parameters.get_offset()
    }
    if sort_parameters:
        query_dict['sort'] = sort_parameters.to_opensearch_sort_dict_list()
    if query:
        query_dict['query']['bool']['must'] = [
            get_paper_search_query_opensearch_must_query_dict(query=query)
        ]
    return query_dict


def get_classification_dict_for_crossref_group_title(
    group_title: str
) -> ClassificationDict:
    return {
        'type': 'category',
        'id': group_title,
        'attributes': {
            'display_name': group_title,
            'source_id': 'crossref_group_title'
        }
    }


def get_classification_response_dict_for_opensearch_aggregations_response_dict(
    response_dict: dict
) -> ClassificationResponseDict:
    group_titles = [
        bucket['key']
        for bucket in response_dict['aggregations']['group_title']['buckets']
    ]
    return {
        'data': [
            get_classification_dict_for_crossref_group_title(group_title)
            for group_title in group_titles
        ]
    }


def get_classification_response_dict_for_opensearch_document_dict(
    document_dict: dict,
    doi: str
) -> ClassificationResponseDict:
    crossref_opensearch_dict = document_dict.get('crossref')
    group_title = (
        crossref_opensearch_dict
        and crossref_opensearch_dict.get('group_title')
    )
    if not group_title or not doi.startswith(f'{KnownDoiPrefix.BIORXIV_MEDRXIV}/'):
        return {
            'data': []
        }
    return {
        'data': [
            get_classification_dict_for_crossref_group_title(group_title)
        ]
    }


def get_paper_dict_for_opensearch_document_dict(
    document_dict: DocumentDict,
    paper_fields_set: Optional[Set[str]] = None
) -> PaperDict:
    assert document_dict.get('doi')
    article_meta = get_article_meta_from_document(document_dict)
    article_stats = get_article_stats_from_document(document_dict)
    sciety_dict = document_dict.get('sciety')
    evaluation_count = (
        article_stats.evaluation_count
        if article_stats
        else None
    )
    attributes: PaperAttributesDict = {
        'doi': document_dict['doi'],
        'title': article_meta.article_title,
        'publication_date': get_date_as_isoformat(article_meta.published_date),
        'evaluation_count': evaluation_count,
        'has_evaluations': (
            bool(evaluation_count)
            if evaluation_count is not None
            else None
        ),
        'latest_evaluation_activity_timestamp': (
            sciety_dict.get('last_event_timestamp')
            if sciety_dict
            else None
        )
    }
    if paper_fields_set:
        attributes = cast(PaperAttributesDict, {
            key: value
            for key, value in attributes.items()
            if key in paper_fields_set
        })
    paper_dict: PaperDict = {
        'type': 'paper',
        'id': document_dict['doi'],
        'attributes': attributes
    }
    return get_recursively_filtered_dict_without_null_values(paper_dict)


def get_paper_response_dict_for_opensearch_document_dict(
    document_dict: DocumentDict
) -> PaperResponseDict:
    return {
        'data': get_paper_dict_for_opensearch_document_dict(document_dict)
    }


def get_paper_search_response_dict_for_opensearch_search_response_dict(
    opensearch_search_result_dict: OpenSearchSearchResultDict,
    paper_fields_set: Optional[Set[str]] = None
) -> PaperSearchResponseDict:
    return {
        'meta': {
            'total': opensearch_search_result_dict['hits']['total']['value']
        },
        'data': [
            get_paper_dict_for_opensearch_document_dict(
                document_dict=hit['_source'],
                paper_fields_set=paper_fields_set
            )
            for hit in opensearch_search_result_dict['hits']['hits']
        ]
    }


LATEST_EVALUATION_TIMESTAMP_DESC_OPENSEARCH_SORT_FIELD = OpenSearchSortField(
    field_name='sciety.last_event_timestamp',
    sort_order='desc'
)


def get_default_paper_search_sort_parameters(
    evaluated_only: bool
) -> OpenSearchSortParameters:
    if evaluated_only:
        return OpenSearchSortParameters(
            sort_fields=[LATEST_EVALUATION_TIMESTAMP_DESC_OPENSEARCH_SORT_FIELD]
        )
    return OpenSearchSortParameters(sort_fields=[])


class AsyncOpenSearchPapersProvider:
    def __init__(self, app_providers_and_models: AppProvidersAndModels):
        self.async_opensearch_client = app_providers_and_models.async_opensearch_client
        self.index_name = app_providers_and_models.opensearch_config.index_name

    async def get_classification_list_response_dict(
        self,
        filter_parameters: OpenSearchFilterParameters,
        headers: Optional[Mapping[str, str]] = None
    ) -> ClassificationResponseDict:
        LOGGER.info('filter_parameters: %r', filter_parameters)
        LOGGER.debug('async_opensearch_client: %r', self.async_opensearch_client)
        opensearch_aggregations_response_dict = await self.async_opensearch_client.search(
            get_classification_list_opensearch_query_dict(
                filter_parameters=filter_parameters
            ),
            index=self.index_name,
            headers=headers
        )
        return get_classification_response_dict_for_opensearch_aggregations_response_dict(
            opensearch_aggregations_response_dict
        )

    async def get_classificiation_response_dict_by_doi(
        self,
        doi: str,
        headers: Optional[Mapping[str, str]] = None
    ) -> ClassificationResponseDict:
        LOGGER.debug('async_opensearch_client: %r', self.async_opensearch_client)
        LOGGER.debug(
            'async_opensearch_client.get_source: %r',
            self.async_opensearch_client.get_source
        )
        try:
            opensearch_document_dict = await self.async_opensearch_client.get_source(
                index=self.index_name,
                id=doi,
                _source_includes=['crossref.group_title'],
                headers=headers
            )
        except opensearchpy.NotFoundError as exc:
            raise DoiNotFoundError(doi=doi) from exc
        return get_classification_response_dict_for_opensearch_document_dict(
            opensearch_document_dict,
            doi=doi
        )

    async def get_paper_search_response_dict(  # pylint: disable=too-many-arguments
        self,
        filter_parameters: OpenSearchFilterParameters,
        sort_parameters: OpenSearchSortParameters,
        pagination_parameters: OpenSearchPaginationParameters,
        query: Optional[str] = None,
        paper_fields_set: Optional[Set[str]] = None,
        headers: Optional[Mapping[str, str]] = None
    ) -> PaperSearchResponseDict:
        LOGGER.info('query: %r', query)
        LOGGER.info('filter_parameters: %r', filter_parameters)
        LOGGER.info('pagination_parameters: %r', pagination_parameters)
        LOGGER.info('paper_fields_set: %r', paper_fields_set)
        internal_paper_fields_set = set(get_flat_mapped_values_or_all_values_for_mapping(
            INTERNAL_ARTICLE_FIELDS_BY_API_FIELD_NAME,
            paper_fields_set
        ))
        opensearch_fields = get_source_includes_for_mapping(
            OPENSEARCH_FIELDS_BY_REQUESTED_FIELD,
            fields=internal_paper_fields_set
        )
        LOGGER.info('opensearch_fields: %r', opensearch_fields)
        opensearch_search_result_dict = await self.async_opensearch_client.search(
            get_paper_search_by_category_opensearch_query_dict(
                filter_parameters=filter_parameters,
                sort_parameters=sort_parameters,
                pagination_parameters=pagination_parameters,
                query=query
            ),
            _source_includes=opensearch_fields,
            index=self.index_name,
            headers=headers
        )
        return get_paper_search_response_dict_for_opensearch_search_response_dict(
            opensearch_search_result_dict,
            paper_fields_set=paper_fields_set
        )
