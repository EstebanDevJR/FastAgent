from fastapi import FastAPI

from app.api.routes import router
from app.config.settings import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.2.0")
    app.include_router(router)
    return app


app = create_app()
