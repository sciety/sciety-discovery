import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from sciety_discovery.models.lists import ScietyEventListsModel
from sciety_discovery.providers.sciety_event import ScietyEventProvider
from sciety_discovery.utils.cache import InMemorySingleObjectCache


LOGGER = logging.getLogger(__name__)


def create_app():
    max_age_in_seconds = 60 * 60  # 1 hour

    sciety_event_provider = ScietyEventProvider(
        query_results_cache=InMemorySingleObjectCache(max_age_in_seconds=max_age_in_seconds)
    )

    templates = Jinja2Templates(directory="templates")

    app = FastAPI()
    app.mount("/static", StaticFiles(directory="static", html=False), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        lists_model = ScietyEventListsModel(
            sciety_event_provider.get_sciety_event_dict_list()
        )
        return templates.TemplateResponse(
            "index.html", {
                "request": request,
                "user_lists": lists_model.get_most_active_user_lists()
            }
        )

    return app
