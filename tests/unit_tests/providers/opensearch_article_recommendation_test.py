from datetime import date
from sciety_labs.providers.opensearch_article_recommendation import (
    get_article_meta_from_document,
    get_vector_search_query,
    iter_article_recommendation_from_opensearch_hits
)


DOI_1 = "10.00000/doi_1"

VECTOR_1 = [1, 1, 1]


class TestGetArticleMetaFromDocument:
    def test_should_create_article_meta_with_minimal_fields(self):
        article_meta = get_article_meta_from_document({
            'doi': 'doi1',
            'title': 'Title 1'
        })
        assert article_meta.article_doi == 'doi1'
        assert article_meta.article_title == 'Title 1'


class TestIterArticleRecommendationFromOpenSearchHits:
    def test_should_yield_items_with_article_meta(self):
        recommendations = list(iter_article_recommendation_from_opensearch_hits([{
            '_source': {
                'doi': 'doi1',
                'title': 'Title 1'
            }
        }]))
        assert len(recommendations) == 1
        assert recommendations[0].article_doi == 'doi1'
        assert recommendations[0].article_meta.article_doi == 'doi1'


class TestGetVectorSearchQuery:
    def test_should_include_query_vector(self):
        search_query = get_vector_search_query(
            query_vector=VECTOR_1,
            embedding_vector_mapping_name='embedding1',
            max_results=3
        )
        assert search_query == {
            'size': 3,
            'query': {
                'knn': {
                    'embedding1': {
                        'vector': VECTOR_1,
                        'k': 3
                    }
                }
            }
        }

    def test_should_add_doi_filter(self):
        search_query = get_vector_search_query(
            query_vector=VECTOR_1,
            embedding_vector_mapping_name='embedding1',
            max_results=3,
            exclude_article_dois={DOI_1}
        )
        assert search_query == {
            'size': 3,
            'query': {
                'knn': {
                    'embedding1': {
                        'vector': VECTOR_1,
                        'k': 3,
                        'filter': {
                            'bool': {
                                'must_not': [{
                                    'term': {'doi': {'value': DOI_1}}
                                }]
                            }
                        }
                    }
                }
            }
        }

    def test_should_add_from_publication_date_filter(self):
        search_query = get_vector_search_query(
            query_vector=VECTOR_1,
            embedding_vector_mapping_name='embedding1',
            max_results=3,
            from_publication_date=date.fromisoformat('2001-02-03')
        )
        assert search_query == {
            'size': 3,
            'query': {
                'knn': {
                    'embedding1': {
                        'vector': VECTOR_1,
                        'k': 3,
                        'filter': {
                            'bool': {
                                'must': [{
                                    'range': {
                                        'publication_date': {'gte': '2001-02-03'}
                                    }
                                }]
                            }
                        }
                    }
                }
            }
        }
