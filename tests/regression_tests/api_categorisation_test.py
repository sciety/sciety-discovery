

from typing import Set

import pytest

from requests import Session

from sciety_labs.app.routers.api.categorisation.typing import (
    ArticleSearchResponseDict,
    CategorisationResponseDict
)


BIOPHYISICS_DOI_1 = '10.1101/2022.02.23.481615'


class Categories:
    BIOPHYSICS = 'Biophysics'


NON_BIORXIV_MEDRXIV_GROUP_TITLE_1 = 'PsyArXiv'
NON_BIORXIV_MEDRXIV_DOI_WITH_GROUP_TITLE_1 = '10.31234/osf.io/2hv6x'


@pytest.fixture(name='categorisation_list_response_dict', scope='session')
def _categorisation_list_response_dict(
    regression_test_session: Session
) -> CategorisationResponseDict:
    response = regression_test_session.get(
        '/api/categorisation/v1/categories'
    )
    response.raise_for_status()
    response_json: CategorisationResponseDict = response.json()
    return response_json


def get_category_set(
    categorisation_list_response_dict: CategorisationResponseDict
) -> Set[str]:
    return {
        categorisation['attributes']['display_name']
        for categorisation in categorisation_list_response_dict['data']
        if categorisation['type'] == 'category'
    }


class TestApiCategorisationList:
    def test_should_return_non_empty_list(
        self,
        categorisation_list_response_dict: CategorisationResponseDict
    ):
        assert len(categorisation_list_response_dict['data']) > 0

    def test_should_contain_biophysics(
        self,
        categorisation_list_response_dict: CategorisationResponseDict
    ):
        category_set = get_category_set(categorisation_list_response_dict)
        assert Categories.BIOPHYSICS in category_set

    def test_should_not_contain_non_biorxiv_medrxiv_group_title(
        self,
        categorisation_list_response_dict: CategorisationResponseDict
    ):
        category_set = get_category_set(categorisation_list_response_dict)
        assert NON_BIORXIV_MEDRXIV_GROUP_TITLE_1 not in category_set


class TestApiAticlesByCategory:
    def test_should_list_articles_for_valid_category(self, regression_test_session: Session):
        response = regression_test_session.get(
            '/api/categorisation/v1/articles/by/category',
            params={'category': Categories.BIOPHYSICS}
        )
        response.raise_for_status()
        response_json: ArticleSearchResponseDict = response.json()
        assert len(response_json['data']) > 0

    def test_should_return_empty_list_for_non_biorxiv_medrxiv_group_title(
        self,
        regression_test_session: Session
    ):
        response = regression_test_session.get(
            '/api/categorisation/v1/articles/by/category',
            params={'category': NON_BIORXIV_MEDRXIV_GROUP_TITLE_1}
        )
        response.raise_for_status()
        response_json: ArticleSearchResponseDict = response.json()
        assert len(response_json['data']) == 0


class TestApiCategorisationByDoi:
    def test_should_list_categories_by_doi(self, regression_test_session: Session):
        response = regression_test_session.get(
            '/api/categorisation/v1/categories/by/doi',
            params={'article_doi': BIOPHYISICS_DOI_1}
        )
        response.raise_for_status()
        response_json: CategorisationResponseDict = response.json()
        assert len(response_json['data']) > 0
        assert response_json['data'] == [
            {
                'type': 'category',
                'attributes': {
                    'display_name': Categories.BIOPHYSICS,
                    'source_id': 'crossref_group_title'
                }
            }
        ]

    def test_should_return_empty_list_for_non_biorxiv_medrxiv_doi_with_group_title(
        self,
        regression_test_session: Session
    ):
        response = regression_test_session.get(
            '/api/categorisation/v1/categories/by/doi',
            params={'article_doi': NON_BIORXIV_MEDRXIV_DOI_WITH_GROUP_TITLE_1}
        )
        response.raise_for_status()
        response_json: CategorisationResponseDict = response.json()
        assert len(response_json['data']) == 0
