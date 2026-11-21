"""Strony WWW Prawdomira (właściciel: Claude). Logika weryfikacji jest w backendzie."""

import os
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from . import dev_fixtures, i18n

APP_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = APP_DIR / "static"
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
router = APIRouter()
PRODUCTION = os.environ.get("PRAWDOWID_ENV") == "production"
LANG = "pl"

try:  # backend Codexa (kontrakt v1); do czasu jego powstania działamy na przykładach
    from app.core import service as backend
except Exception:  # noqa: BLE001
    backend = None
if os.environ.get("PRAWDOWID_WEB_FIXTURES") == "1" and not PRODUCTION:
    backend = None  # podgląd wyglądu na przykładowych danych

_dev_results: dict[str, dict] = {}


def _as_dict(result):
    return result.model_dump() if hasattr(result, "model_dump") else result


def _session(request: Request):
    return request.cookies.get("pw_session")


def run_check(text: str, clarifies: str | None, session_id: str | None) -> dict:
    if backend is not None:
        return _as_dict(backend.run_check(text, channel="web", lang=LANG, session_id=session_id,
                                          clarifies=clarifies))
    if PRODUCTION:
        raise RuntimeError("Backend niedostępny")
    result = dev_fixtures.fake_check(text, parent=_dev_results.get(clarifies) if clarifies else None)
    _dev_results[result["id"]] = result
    return result


def get_check(check_id: str):
    if backend is not None:
        found = backend.get_check(check_id)
        return _as_dict(found) if found else None
    return _dev_results.get(check_id)


def corpus_stats() -> dict:
    try:
        if backend is not None:
            data = _as_dict(backend.list_sources())
            return {"documents": data.get("documents"), "domains": data.get("domains"),
                    "types": len(data.get("source_types") or []), "sources": data.get("sources", [])}
        from prawdowid_core import DEFAULT_CORPUS, load_corpus
        sources, version = load_corpus(DEFAULT_CORPUS)
        items = sorted(sources.values(), key=lambda s: (s.get("publisher", ""), s.get("title", "")))
        return {"documents": len(sources), "domains": len({s["domain"] for s in items}),
                "types": len({s["type"] for s in items}), "sources": items, "version": version}
    except Exception:  # noqa: BLE001
        return {"documents": None, "domains": None, "types": None, "sources": []}


# ---------- filtry szablonów ----------

def fmt_date(value) -> str:
    if not value:
        return ""
    try:
        d = datetime.fromisoformat(value) if "T" in str(value) else date.fromisoformat(str(value))
    except ValueError:
        return str(value)
    return f"{d.day} {i18n.MONTHS[LANG][d.month - 1]} {d.year}"


def fmt_datetime(value) -> str:
    try:
        d = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return ""
    return f"{fmt_date(value)}, {d:%H:%M}"


def domain(url: str) -> str:
    from urllib.parse import urlsplit
    host = urlsplit(url or "").hostname or ""
    return host.removeprefix("www.")


def mark_claims(text: str, items: list) -> Markup:
    """Podkreśla w oryginalnej wiadomości fragmenty, których dotyczą tezy."""
    spans = []
    for n, item in enumerate(items, 1):
        span = item.get("claim_span")
        if not span:
            continue
        start = text.find(span)
        if start < 0 or any(s <= start < e or s < start + len(span) <= e for s, e, _ in spans):
            continue
        spans.append((start, start + len(span), n))
    out, pos = [], 0
    for start, end, n in sorted(spans):
        out.append(escape(text[pos:start]))
        out.append(Markup('<span class="span-claim"><span class="span-claim__text">{}</span>'
                          '<sup class="span-claim__n" aria-label="teza {}">{}</sup></span>')
                   .format(text[start:end], n, n))
        pos = end
    out.append(escape(text[pos:]))
    return Markup("").join(out)


def mark_tones(text: str, items: list) -> Markup:
    """Wiadomość z fragmentami podświetlonymi kolorem oceny (wariant „zaznaczenia”)."""
    spans = []
    for n, item in enumerate(items, 1):
        span = item.get("claim_span")
        start = text.find(span) if span else -1
        if start < 0 or any(s < start + len(span) and start < e for s, e, *_ in spans):
            continue
        key = item["label"] if item["kind"] == "verdict" else "answer"
        spans.append((start, start + len(span), n, i18n.LABELS[LANG][key]["tone"]))
    out, pos = [], 0
    for start, end, n, tone in sorted(spans):
        out.append(escape(text[pos:start]))
        out.append(Markup('<mark class="hl hl--{}">{}<span class="hl__n">{}</span></mark>').format(tone, text[start:end], n))
        pos = end
    out.append(escape(text[pos:]))
    return Markup("").join(out)


VARIANTS = {"kotwica": ("pasek",), "lista": ("karty", "zaznaczenia"), "kolor": ("granat",)}


def variants(request: Request) -> dict:
    chosen = {}
    for key, options in VARIANTS.items():
        value = request.query_params.get(key) or request.cookies.get(f"pw_{key}") or options[0]
        chosen[key] = value if value in options else options[0]
    return chosen


def tally(items: list) -> list:
    counts: dict[str, int] = {}
    for item in items:
        key = item["label"] if item["kind"] == "verdict" else "answer"
        counts[key] = counts.get(key, 0) + 1
    return list(counts.items())


templates.env.filters.update(date=fmt_date, datetime=fmt_datetime, domain=domain)
templates.env.globals.update(L=i18n.LABELS[LANG], PLAIN=i18n.PLAIN[LANG],S=i18n.STATUSES[LANG], STRENGTH=i18n.STRENGTH[LANG],
                             STANCE=i18n.STANCE[LANG], FIELD=i18n.MISMATCH_FIELD[LANG],
                             NOTICE_ICON=i18n.NOTICE_ICON, mark_claims=mark_claims, mark_tones=mark_tones, tally=tally,
                             pl_count=i18n.pl_count, dev=not PRODUCTION)


THEMES = {"a": "styl-a", "b": "styl-b", "v0": "app"}


def _render(request: Request, name: str, **ctx):
    choice = request.query_params.get("styl") or request.cookies.get("pw_styl") or "a"
    choice = choice if choice in THEMES else "a"
    v = variants(request)
    response = templates.TemplateResponse(request, name, dict(ctx, theme=THEMES[choice], theme_key=choice, v=v,
                                                              VARIANTS=VARIANTS, path=request.url.path))
    if request.query_params.get("styl") in THEMES:
        response.set_cookie("pw_styl", choice, samesite="lax")
    for key, value in v.items():
        if request.query_params.get(key):
            response.set_cookie(f"pw_{key}", value, samesite="lax")
    return response


# ---------- strony ----------

@router.get("/", response_class=HTMLResponse)
def start(request: Request, usunieto: int = 0):
    return _render(request, "start.html", stats=corpus_stats(), deleted=bool(usunieto))


@router.post("/sprawdz")
def submit(request: Request, text: str = Form(""), clarifies: str | None = Form(None)):
    text = text.strip()
    if not text:
        return _render(request, "start.html", stats=corpus_stats(), error="Wpisz albo wklej treść do sprawdzenia.")
    if len(text) > 4000:
        return _render(request, "start.html", stats=corpus_stats(), text=text,
                       error="Tekst jest za długi. Skróć go do 4000 znaków.")
    try:
        result = run_check(text, clarifies or None, _session(request))
    except Exception:  # noqa: BLE001
        return _render(request, "wynik.html", r=dev_fixtures.build("awaria", text))
    return RedirectResponse(f"/wynik/{result['id']}", status_code=303)


@router.get("/wynik/{check_id}", response_class=HTMLResponse)
def result_page(request: Request, check_id: str):
    result = get_check(check_id)
    if result is None:
        return _render(request, "brak.html")
    parent = get_check(result["parent_id"]) if result.get("parent_id") else None
    return _render(request, "wynik.html", r=result, parent=parent)


@router.get("/zrodla", response_class=HTMLResponse)
def sources_page(request: Request):
    return _render(request, "zrodla.html", stats=corpus_stats())


@router.get("/dev", response_class=HTMLResponse)
def dev_index(request: Request):
    if PRODUCTION:
        return _render(request, "brak.html")
    return _render(request, "dev.html", names=list(dev_fixtures.FIXTURES))


@router.get("/dev/wynik/{name}", response_class=HTMLResponse)
def dev_result(request: Request, name: str):
    if PRODUCTION or name not in dev_fixtures.FIXTURES:
        return _render(request, "brak.html")
    result = dev_fixtures.build(name)
    _dev_results[result["id"]] = result
    return _render(request, "wynik.html", r=result)
