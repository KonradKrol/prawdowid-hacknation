"""Podgląd frontendu niezależny od backendu: uvicorn app.web.dev_server:app --port 8001"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes import STATIC_DIR, router

app = FastAPI(title="Prawdomir — podgląd WWW", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(router)
