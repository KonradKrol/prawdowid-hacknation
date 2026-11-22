import csv
import sqlite3
from hashlib import sha256
from io import StringIO
from time import time

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app.contract import CheckRequest, CheckResult, SourcesResponse
from app.core.service import delete_check, delete_session, get_check, get_service, list_sources, run_check

router = APIRouter()


def charge(request, channel):
    service = get_service()
    if not service.settings.rate_limit_enabled:
        return True
    remote = request.client.host if request.client else "local"
    # Use the address forwarded by the ASGI server only when its proxy is trusted.
    key = sha256(f"{channel}:{remote}".encode()).hexdigest()
    return service.store.charge(key, int(time()))


@router.post("/api/v1/checks", response_model=CheckResult)
def create_check(payload: CheckRequest, request: Request, nocache: bool = False):
    result = run_check(payload.text, lang=payload.lang, channel="api", clarifies=payload.clarifies,
                       session_id=request.state.session_id, use_cache=not nocache)
    if result.status == "rate_limited":
        return JSONResponse(result.model_dump(), status_code=429, headers={"Retry-After": "60"})
    return result


@router.get("/api/v1/checks/{check_id}", response_model=CheckResult)
def fetch_check(check_id: str, request: Request):
    record = get_check(check_id, session_id=request.state.session_id)
    if record is None:
        raise HTTPException(404, "Sprawdzenie jest niedostępne.")
    return record


@router.delete("/api/v1/checks/{check_id}", status_code=204)
def remove_check(check_id: str, request: Request):
    if not delete_check(check_id, session_id=request.state.session_id):
        raise HTTPException(404, "Sprawdzenie jest niedostępne.")
    return Response(status_code=204)


@router.delete("/api/v1/session")
def remove_session(request: Request):
    return {"deleted": delete_session(request.state.session_id)}


@router.get("/api/v1/sources", response_model=SourcesResponse)
def sources():
    return list_sources()


@router.get("/api/v1/sources.csv")
def sources_csv():
    report = list_sources()
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(("id", "title", "publisher", "url", "domain", "type", "published_on", "checked_on", "usage"))
    for row in report.sources:
        writer.writerow(safe_csv(value) for value in (
            row.id, row.title, row.publisher, row.url, row.domain, row.type,
            row.published_on, row.checked_on, row.usage,
        ))
    return Response(buffer.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="prawdowid-zrodla.csv"'})


def safe_csv(value):
    text = str(value or "")
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


@router.get("/health")
def health():
    service = get_service()
    report = service.sources()
    try:
        with service.store.connection() as db:
            db.execute("SELECT 1 FROM checks LIMIT 1")
    except (OSError, sqlite3.Error):
        return JSONResponse({"status": "database_unavailable"}, status_code=503)
    if service.settings.environment == "production" and not service.settings.key:
        return JSONResponse({"status": "model_unconfigured"}, status_code=503)
    official = service.official.status()
    return {"status": "ok", "database": "ok", "model_configured": bool(service.settings.key),
            "evaluator": service.settings.evaluator, "corpus": report.model_dump(exclude={"sources"}),
            "official_feed": {"feed": official["feed"], "failing": official["failing"], "stale": official["stale"],
                              "entries": official["entries"],
                              "last_success": (official["last_success"] or {}).get("finished_at"),
                              "last_error": (official["last_run"] or {}).get("error") if official["failing"] else None}}
