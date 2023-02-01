from collections import defaultdict
from datetime import datetime
from typing import Dict, NamedTuple, Protocol, Sequence, Set


class ListMetaData(NamedTuple):
    list_id: str
    list_title: str
    list_description: str

    @staticmethod
    def from_sciety_event_list_meta(sciety_event_list_meta: dict) -> 'ListMetaData':
        return ListMetaData(
            list_id=sciety_event_list_meta['list_id'],
            list_title=sciety_event_list_meta['list_name'],
            list_description=sciety_event_list_meta['list_description']
        )


class OwnerMetaData(NamedTuple):
    avatar_url: str

    @staticmethod
    def from_sciety_event_user_meta(sciety_event_user_meta: dict) -> 'OwnerMetaData':
        return OwnerMetaData(
            avatar_url=sciety_event_user_meta['avatar_url']
        )


class ListSummaryData(NamedTuple):
    list_meta: ListMetaData
    owner: OwnerMetaData
    article_count: int
    last_updated_datetime: datetime

    @property
    def last_updated_date_isoformat(self) -> str:
        return self.last_updated_datetime.strftime(r'%Y-%m-%d')

    @property
    def last_updated_date_display_format(self) -> str:
        return self.last_updated_datetime.strftime(r'%b %-d, %Y')


class ScietyEventNames:
    ARTICLE_ADDED_TO_LIST = 'ArticleAddedToList'
    ARTICLE_REMOVED_FROM_LIST = 'ArticleRemovedFromList'


class ListsModel(Protocol):
    def get_most_active_user_lists(self) -> Sequence[ListSummaryData]:
        pass


class ScietyEventListsModel(ListsModel):
    def __init__(self, sciety_events: Sequence[dict]):
        self._sciety_list_meta_by_list_id: Dict[str, ListMetaData] = {}
        self._owner_meta_by_list_id: Dict[str, OwnerMetaData] = {}
        self._article_ids_by_list_id: Dict[str, Set[str]] = defaultdict(set)
        self._last_updated_by_list_id: Dict[str, datetime] = {}
        for event in sciety_events:
            event_timestamp = event['event_timestamp']
            event_name = event['event_name']
            sciety_list = event['sciety_list']
            sciety_user = event.get('sciety_user')
            list_id = sciety_list['list_id']
            article_id = event.get('article_id')
            if not sciety_list:
                continue
            list_meta = ListMetaData.from_sciety_event_list_meta(sciety_list)
            list_id = list_meta.list_id
            self._sciety_list_meta_by_list_id[list_id] = list_meta
            if list_id and sciety_user:
                self._owner_meta_by_list_id[list_id] = (
                    OwnerMetaData.from_sciety_event_user_meta(sciety_user)
                )
            if list_id and article_id:
                self._last_updated_by_list_id[list_id] = event_timestamp
                if event_name == ScietyEventNames.ARTICLE_ADDED_TO_LIST:
                    self._article_ids_by_list_id[list_id].add(article_id)
                if event_name == ScietyEventNames.ARTICLE_REMOVED_FROM_LIST:
                    try:
                        self._article_ids_by_list_id[list_id].remove(article_id)
                    except KeyError:
                        pass

    def get_most_active_user_lists(self) -> Sequence[ListSummaryData]:
        return [
            ListSummaryData(
                list_meta=list_meta,
                owner=self._owner_meta_by_list_id[list_meta.list_id],
                article_count=len(self._article_ids_by_list_id[
                    list_meta.list_id
                ]),
                last_updated_datetime=self._last_updated_by_list_id[
                    list_meta.list_id
                ]
            )
            for list_meta in self._sciety_list_meta_by_list_id.values()
        ]
