"""Panel moderatora i API kanału urzędowego.

Dostęp: `PRAWDOWID_ADMIN_TOKEN` w nagłówku `X-Admin-Token`, w ciasteczku `pw_admin`
albo jednorazowo w `?klucz=` (ustawia ciasteczko). Bez ustawionego tokenu panel działa
tylko poza produkcją.
"""

from datetime import datetime, timezone
from hmac import compare_digest

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse

from app.core.service import get_service

router = APIRouter()
ADMIN_COOKIE = "pw_admin"


def authorized(request):
    settings = get_service().settings
    token = settings.admin_token
    if settings.admin_open:
        return True
    if not token:
        return settings.environment != "production"
    offered = (request.headers.get("X-Admin-Token") or request.cookies.get(ADMIN_COOKIE)
               or request.query_params.get("klucz") or "")
    return compare_digest(token.encode(), offered.encode())


def require_admin(request):
    if not authorized(request):
        raise HTTPException(404, "Nie znaleziono.")


def board():
    service = get_service()
    cases = []
    for case in service.store.cases():
        proposals = service.store.proposals(case_id=case["id"])
        cases.append({**case, "proposals": proposals, "pending": [p for p in proposals if p["status"] == "pending"],
                      "reports_list": service.store.case_reports(case["id"])})
    now = int(datetime.now(timezone.utc).timestamp())
    from app.core.topics import GROWING_LAST_HOUR
    from app.ingest.places import WARSAW
    stamp = lambda value: datetime.fromtimestamp(value, WARSAW).isoformat()  # noqa: E731  # czas polski w panelu
    topic_rows = [dict(row, updated_at=stamp(row["updated"]), growing=row["last_hour"] >= GROWING_LAST_HOUR,
                       recent=[dict(r, at=stamp(r["created"])) for r in row["recent"]])
                  for row in service.store.topics_board(now, now - 7 * 86400)]
    return {"cases": cases, "official": service.official.status(), "topics": topic_rows,
            "growing_threshold": GROWING_LAST_HOUR}


@router.get("/api/v1/official/status")
def official_status():
    status = get_service().official.status()
    return {key: value for key, value in status.items() if key != "runs"} | {"runs": status["runs"][:5]}


@router.post("/api/v1/official/sync")
async def official_sync(request: Request):
    require_admin(request)
    return await run_in_threadpool(get_service().official.sync)


@router.get("/api/v1/cases")
def list_cases(request: Request):
    require_admin(request)
    return board()


@router.post("/api/v1/proposals/{proposal_id}")
def decide(proposal_id: int, request: Request, decision: str):
    require_admin(request)
    if decision not in {"accept", "reject"}:
        raise HTTPException(422, "Decyzja: accept albo reject.")
    if not get_service().store.proposal_decide(proposal_id, decision == "accept", datetime.now(timezone.utc).isoformat()):
        raise HTTPException(409, "Propozycja nie czeka na decyzję.")
    return {"id": proposal_id, "status": "accepted" if decision == "accept" else "rejected"}


# ---------- strony WWW ----------

@router.get("/moderacja")
def moderation_page(request: Request, synchronizacja: str | None = None, usunieto: int | None = None):
    require_admin(request)
    from app.ingest import imgw
    from app.ingest.places import county_label, gazetteer
    from app.web.routes import _render
    data = gazetteer()[0]
    counties = sorted(((code, county_label(code, data)) for code in data), key=lambda row: row[1])
    sim = {"events": {key: name for key, (name, _) in imgw.SIM_EVENTS.items()}, "counties": counties,
           "active": get_service().official.simulations(), "removed": usunieto}
    response = _render(request, "moderacja.html", b=board(), flash=synchronizacja, sim=sim,
                       demo_open=get_service().settings.admin_open)
    offered = request.query_params.get("klucz")
    if offered:
        response.set_cookie(ADMIN_COOKIE, offered, httponly=True, samesite="strict",
                            secure=get_service().settings.environment == "production", max_age=12 * 3600)
    return response


@router.post("/moderacja/sync")
async def moderation_sync(request: Request):
    require_admin(request)
    summary = await run_in_threadpool(get_service().official.sync)
    return RedirectResponse(f"/moderacja?synchronizacja={summary['status']}", status_code=303)


@router.post("/moderacja/symulacja")
async def moderation_simulate(request: Request, hazard: str = Form(...), teryt: str = Form(...),
                              level: int = Form(2), start: str = Form("teraz"), hours: int = Form(24),
                              text: str = Form("")):
    """Symulowane ostrzeżenie w formacie IMGW — do pokazu przebiegu: import → ponowna ocena → propozycja."""
    require_admin(request)
    from datetime import timedelta
    from app.ingest import imgw
    from app.ingest.places import WARSAW, gazetteer
    if hazard not in imgw.SIM_EVENTS or teryt not in gazetteer()[0] or not 1 <= level <= 3 or not 1 <= hours <= 72:
        raise HTTPException(422, "Nieprawidłowe dane symulacji.")
    now = datetime.now(WARSAW).replace(minute=0, second=0, microsecond=0)
    valid_from = now + timedelta(days=1) if start == "jutro" else now
    summary = await run_in_threadpool(get_service().official.simulate, hazard, (teryt,), level, valid_from,
                                      hours, text.strip()[:500] or None)
    return RedirectResponse(f"/moderacja?synchronizacja={summary['status']}&symulacja=1#symulacje", status_code=303)


@router.post("/moderacja/symulacja/usun")
def moderation_simulation_clear(request: Request):
    require_admin(request)
    removed = get_service().official.remove_simulations()
    return RedirectResponse(f"/moderacja?usunieto={removed}#symulacje", status_code=303)


@router.post("/moderacja/propozycje/{proposal_id}")
def moderation_decide(proposal_id: int, request: Request, decision: str = Form(...)):
    require_admin(request)
    if decision in {"accept", "reject"}:
        get_service().store.proposal_decide(proposal_id, decision == "accept", datetime.now(timezone.utc).isoformat())
    return RedirectResponse("/moderacja", status_code=303)
