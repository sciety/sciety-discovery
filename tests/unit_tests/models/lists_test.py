from datetime import datetime
from sciety_discovery.models.lists import (
    ScietyEventListsModel
)


DOI_1 = '10.12345/doi_1'
DOI_2 = '10.12345/doi_2'

ARTICLE_ID_1 = f'doi:{DOI_1}'
ARTICLE_ID_2 = f'doi:{DOI_2}'

LIST_ID_1 = 'list_1'
LIST_ID_2 = 'list_2'


SCIETY_LIST_1 = {
    'list_id': LIST_ID_1,
    'list_name': 'List Name 1',
    'list_description': 'List Description 1'
}

USER_ID_1 = 'user_1'

SCIETY_USER_1 = {
    'user_id': USER_ID_1,
    'avatar_url': 'https://user-avatar/1'
}

TIMESTAMP_1 = datetime.fromisoformat('2001-01-01+00:00')
TIMESTAMP_2 = datetime.fromisoformat('2001-01-02+00:00')

ARTICLE_ADDED_TO_LIST_EVENT_1 = {
    'event_timestamp': TIMESTAMP_1,
    'event_name': 'ArticleAddedToList',
    'sciety_list': SCIETY_LIST_1,
    'sciety_user': SCIETY_USER_1,
    'article_id': ARTICLE_ID_1
}


class TestScietyEventListsModel:
    def test_should_return_empty_list_for_no_events(self):
        model = ScietyEventListsModel([])
        assert not model.get_most_active_user_lists()

    def test_should_populate_list_id_and_list_meta_fields(self):
        model = ScietyEventListsModel([
            ARTICLE_ADDED_TO_LIST_EVENT_1,
            ARTICLE_ADDED_TO_LIST_EVENT_1
        ])
        result = model.get_most_active_user_lists()
        assert [
            {
                'list_id': item['list_id'],
                'list_title': item['list_title'],
                'list_description': item['list_description']
            }
            for item in result
        ] == [{
            'list_id': LIST_ID_1,
            'list_title': SCIETY_LIST_1['list_name'],
            'list_description': SCIETY_LIST_1['list_description']
        }]

    def test_should_populate_avatar_url(self):
        model = ScietyEventListsModel([
            ARTICLE_ADDED_TO_LIST_EVENT_1,
            ARTICLE_ADDED_TO_LIST_EVENT_1
        ])
        result = model.get_most_active_user_lists()
        assert [
            {
                'avatar_url': item['avatar_url'],
            }
            for item in result
        ] == [{
            'avatar_url': SCIETY_USER_1['avatar_url']
        }]

    def test_should_calculate_article_count_for_added_only_events(self):
        model = ScietyEventListsModel([{
            **ARTICLE_ADDED_TO_LIST_EVENT_1,
            'article_id': ARTICLE_ID_1
        }, {
            **ARTICLE_ADDED_TO_LIST_EVENT_1,
            'article_id': ARTICLE_ID_2
        }])
        result = model.get_most_active_user_lists()
        assert [item['article_count'] for item in result] == [2]

    def test_should_calculate_last_updated_date(self):
        model = ScietyEventListsModel([{
            **ARTICLE_ADDED_TO_LIST_EVENT_1,
            'event_timestamp': datetime.fromisoformat('2001-01-01+00:00'),
            'article_id': ARTICLE_ID_1
        }, {
            **ARTICLE_ADDED_TO_LIST_EVENT_1,
            'event_timestamp': datetime.fromisoformat('2001-01-02+00:00'),
            'article_id': ARTICLE_ID_2
        }])
        result = model.get_most_active_user_lists()
        assert [item['last_updated_date_isoformat'] for item in result] == [
            '2001-01-02'
        ]
