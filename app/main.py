from contextlib import asynccontextmanager
from hashlib import sha256
from secrets import token_urlsafe
import re

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.checks import router as checks_router
from app.api.whatsapp import router as whatsapp_router
from app.config import ROOT, Settings
from app.core.service import CLIENT_BUCKET, SESSION, get_service

SESSION_COOKIE = "pw_session"


@asynccontextmanager
async def lifespan(app):
    service = get_service()
    try:
        yield
    finally:
        service.corpus.close()
        get_service.cache_clear()


def create_app():
    settings = Settings()  # Validate production mode before serving.
    application = FastAPI(title="Prawdowid", version="1.0", lifespan=lifespan)
    application.include_router(checks_router)
    application.include_router(whatsapp_router)
    static_dir = ROOT / "app" / "static"
    if static_dir.is_dir():
        application.mount("/static", StaticFiles(directory=static_dir), name="static")
    web_package = ROOT / "app" / "web" / "routes.py"
    if web_package.is_file():
        from app.web.routes import router as web_router
        application.include_router(web_router)
    else:
        @application.get("/")
        def root():
            return {"service": "Prawdowid", "api": "/docs", "health": "/health"}

    @application.middleware("http")
    async def session_cookie(request, call_next):
        if request.url.path.startswith("/static/") or request.url.path in {
            "/api/whatsapp/webhook", "/health", "/openapi.json"
        }:
            return await call_next(request)
        original = request.cookies.get(SESSION_COOKIE, "")
        session_id = original if re.fullmatch(r"[A-Za-z0-9_-]{43}", original) else token_urlsafe(32)
        request.state.session_id = session_id
        token = SESSION.set(session_id)
        client = request.client.host if request.client else "local"
        rate_token = CLIENT_BUCKET.set(sha256(f"check:{client}".encode()).hexdigest())
        try:
            response = await call_next(request)
        finally:
            CLIENT_BUCKET.reset(rate_token)
            SESSION.reset(token)
        if session_id != original:
            response.set_cookie(SESSION_COOKIE, session_id, httponly=True,
                                secure=settings.environment == "production", samesite="lax", max_age=7 * 86400)
        if request.url.path.startswith(("/api/v1/checks", "/wynik/")):
            response.headers["Cache-Control"] = "no-store"
        return response

    return application


app = create_app()
