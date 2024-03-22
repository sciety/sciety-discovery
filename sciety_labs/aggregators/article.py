import logging
from typing import AsyncIterable, AsyncIterator, Optional

from sciety_labs.models.article import ArticleMention
from sciety_labs.models.evaluation import ScietyEventEvaluationStatsModel
from sciety_labs.providers.async_providers.crossref.async_crossref import (
    AsyncCrossrefMetaDataProvider
)
from sciety_labs.providers.google_sheet_image import GoogleSheetArticleImageProvider
from sciety_labs.utils.async_utils import async_get_iterable_and_look_ahead_one
from sciety_labs.utils.pagination import async_get_page_iterable


LOGGER = logging.getLogger(__name__)


class ArticleAggregator:
    def __init__(
        self,
        evaluation_stats_model: ScietyEventEvaluationStatsModel,
        async_crossref_metadata_provider: AsyncCrossrefMetaDataProvider,
        google_sheet_article_image_provider: GoogleSheetArticleImageProvider
    ):
        self.evaluation_stats_model = evaluation_stats_model
        self.async_crossref_metadata_provider = async_crossref_metadata_provider
        self.google_sheet_article_image_provider = google_sheet_article_image_provider

    async def async_iter_page_article_mention_with_article_meta_and_stats(
        self,
        article_mention_iterable: AsyncIterable[ArticleMention],
        page: int,
        items_per_page: Optional[int]
    ) -> AsyncIterator[ArticleMention]:
        article_mention_iterable = (
            self.evaluation_stats_model.async_iter_article_mention_with_article_stats(
                article_mention_iterable
            )
        )
        article_mention_with_article_meta_iterable = (
            self.async_crossref_metadata_provider.iter_article_mention_with_article_meta(
                async_get_page_iterable(
                    article_mention_iterable, page=page, items_per_page=items_per_page
                )
            )
        )
        article_mention_with_article_meta_iterable = (
            self.google_sheet_article_image_provider
            .async_iter_article_mention_with_article_image_url(
                article_mention_with_article_meta_iterable
            )
        )
        if LOGGER.isEnabledFor(logging.DEBUG):
            article_mention_with_article_meta_iterable, first_item = (
                await async_get_iterable_and_look_ahead_one(
                    article_mention_with_article_meta_iterable
                )
            )
            LOGGER.debug(
                'article_mention_with_article_meta[:1]=%r', first_item
            )
        async for item in article_mention_with_article_meta_iterable:
            yield item
