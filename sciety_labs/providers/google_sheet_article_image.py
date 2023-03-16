import logging
from typing import Iterable, Mapping, Optional

import google.auth
import googleapiclient.discovery

from sciety_labs.models.article import ArticleImages, ArticleMention


LOGGER = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


DEFAULT_SHEET_ID = '1zEiW1AniF8SRcM__3q1gbRbT_Svd_9d83oICVtom00w'
DEFAULT_SHEET_RANGE = 'A:B'


class GoogleSheetArticleImageProvider:
    def __init__(
        self,
        sheet_id: str = DEFAULT_SHEET_ID,
        sheet_range: str = DEFAULT_SHEET_RANGE
    ) -> None:
        self.sheet_id = sheet_id
        self.sheet_range = sheet_range
        self.image_url_by_doi: Mapping[str, str] = {}
        LOGGER.info('sheet_id: %r, sheet_range: %r', sheet_id, sheet_range)
        self.reload()

    def load_mapping(self) -> Mapping[str, str]:
        credentials, _ = google.auth.default(scopes=SCOPES)
        service = googleapiclient.discovery.build('sheets', 'v4', credentials=credentials)
        sheets = service.spreadsheets()
        result = sheets.values().get(
            spreadsheetId=self.sheet_id,
            range=self.sheet_range
        ).execute()
        values = result.get('values', [])
        LOGGER.info('sheet values: %r', values)
        return dict(values[1:])

    def reload(self):
        self.image_url_by_doi = self.load_mapping()

    def get_article_image_url_by_doi(self, article_doi: str) -> Optional[str]:
        return self.image_url_by_doi.get(article_doi)

    def get_article_images_by_doi(self, article_doi: str) -> ArticleImages:
        return ArticleImages(
            image_url=self.get_article_image_url_by_doi(article_doi)
        )

    def iter_article_mention_with_article_image_url(
        self,
        article_mention_iterable: Iterable[ArticleMention]
    ) -> Iterable[ArticleMention]:
        return (
            article_mention._replace(
                article_images=self.get_article_images_by_doi(
                    article_mention.article_doi
                )
            )
            for article_mention in article_mention_iterable
        )
