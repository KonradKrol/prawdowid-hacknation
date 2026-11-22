from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from functools import lru_cache
from hashlib import sha256
import json
import re
from secrets import token_hex
import sqlite3
from threading import Lock
from time import perf_counter
from urllib.error import HTTPError, URLError
from uuid import uuid4

from app.config import Settings
from app.contract import CheckResult, Item, Meta, NoticeItem, PublicSource, SourcesResponse
from app.core.demo import demo_result
from app.core.model import CitationDraft, ItemDraft, PROMPT_VERSION, Provider
from app.core.repository import Corpus
from app.core.result import missing_item, normalize
from app.core.safety import SCOPE, SUSPICIOUS, VAGUE, input_info
from app.ingest.narrative_search import NarrativeSearch
from app.ingest.official import OfficialSync, summarize
from app.ingest.places import needs_place, signature as event_signature
from app.ingest import narratives
from app.core import topics
from app.storage.db import Store
from prawdowid_core import fragments

SESSION = ContextVar("prawdowid_session", default=None)
CLIENT_BUCKET = ContextVar("prawdowid_client_bucket", default=None)
ERROR_MESSAGE = "Wystąpił błąd techniczny i nie udało się zakończyć sprawdzenia."
_PL = str.maketrans("ąćęłńóśźż", "acelnoszz")


def cache_text(text):
    """Klucz pamięci wyników: ta sama treść niezależnie od wielkości liter, interpunkcji,
    polskich znaków i odstępów („Czy RCB wysłało alert?” == „czy rcb wyslalo alert”)."""
    words = re.sub(r"[^\w\s]", " ", text.casefold().translate(_PL)).split()
    return " ".join(words)


def clarification_selection(question, answer):
    # Interpret short selections only when the previous question offered a choice.
    question = cache_text(question)
    answer = cache_text(answer)
    if not question.startswith("czy "):
        return None
    alternatives = re.search(r"\b(?:czy|albo|lub)\b", question[4:])
    if alternatives and answer in {"oba", "obie", "obydwa", "obydwie", "jedno i drugie"}:
        return "both"
    if not alternatives and answer in {"tak", "tak chodzi mi o to", "tak o to chodzi", "zgadza sie", "dokladnie"}:
        return "confirmed"
    return None


def clean_topic(value, marker):
    """Temat od modelu: jedna linia, bez znacznika ochronnego, do 120 znaków."""
    if not value:
        return None
    text = " ".join(str(value).split())
    if marker and marker in text:
        return None
    return text.strip(" .„”\"")[:120] or None


class Service:
    def __init__(self, settings):
        self.settings = settings
        self.store = Store(settings.data_dir / "prawdowid.db")
        self.corpus = Corpus(settings.corpus)
        self.provider = Provider(settings)
        self.last_prune = 0
        self.maintenance = Lock()
        self.official = OfficialSync(self)
        self.narratives = narratives.load()
        self.narrative_search = (NarrativeSearch(settings, self.narratives)
                                 if settings.evaluator == "live" and settings.key else None)
        self.official.load_current()

    def sources(self):
        with self.corpus.lock:
            rows = list(self.corpus.sources.values())
            version = self.corpus.version
        return SourcesResponse(
            documents=len(rows), domains=len({source["domain"] for source in rows}),
            source_types=sorted({source["type"] for source in rows}),
            version=version, sources=[PublicSource.model_validate(row) for row in rows],
        )

    def result(self, text, channel, timestamp, parent_id=None):
        return CheckResult(
            id="chk_" + uuid4().hex, created_at=timestamp.isoformat(), channel=channel,
            status="ok", parent_id=parent_id, input=input_info(text),
            meta=Meta(corpus_version=self.corpus.version, corpus_documents=len(self.corpus.sources),
                      model=self.settings.model if self.settings.evaluator == "live" else None,
                      prompt_version=PROMPT_VERSION, elapsed_ms=0),
        )

    def limit(self, text, channel):
        result = self.result(text[:4000], channel, datetime.now(timezone.utc))
        result.status, result.message = "rate_limited", "Za dużo zgłoszeń. Spróbuj ponownie za chwilę."
        return result

    def fake_evidence(self, src, claim, stance, label):
        kind = "answer" if label == "answer" else "verdict"
        date = kind == "answer"
        draft = ItemDraft(
            claim=claim, claim_span=None, kind=kind, label=None if date else label,
            answer=src.get("published_on") if date else None,
            reason="Techniczna próbka deweloperska.", missing_evidence=None,
            context_mismatch=None, evidence=[CitationDraft(source_id=src["id"], stance=stance,
                quote=None if date else fragments(src)[0], field="published_on" if date else "excerpt")],
        )
        if label == "misleading":
            from app.contract import ContextMismatch
            draft.context_mismatch = ContextMismatch(field="date", claim_value="dziś",
                source_value=src.get("published_on") or "inna data", explanation="Próba różnicy daty.")
        return normalize(draft, [src], "t1", claim, "")

    def run(self, text, *, channel="web", lang="pl", session_id=None, use_cache=True, clarifies=None,
            pinned=None, register=True):
        if lang != "pl":
            raise ValueError("Unsupported language")
        start = perf_counter()
        at = datetime.now(timezone.utc)
        now = int(at.timestamp())
        result = self.result(text[:4000], channel, at, clarifies)
        root, rounds = result.input.text_masked, 0
        search_text, source_url = root, result.input.url
        model_context = {"question": root}
        cache_key = None
        try:
            with self.maintenance:
                if now - self.last_prune >= 3600:
                    self.store.prune(now)
                    self.last_prune = now
            if not text.strip() or len(text) > 4000:
                result.status, result.message = "invalid_input", "Wpisz od 1 do 4000 znaków."
            elif clarifies is not None:
                parent = self.store.read(clarifies, session_id) if session_id else None
                if parent is None or parent[0].status != "needs_clarification" or parent[2] >= 2:
                    result.status, result.message = "invalid_input", "Nie można doprecyzować tego zgłoszenia."
                else:
                    previous, previous_context, previous_rounds = parent
                    rounds = previous_rounds + 1
                    question = previous.clarification_question or ""
                    answer = result.input.text_masked
                    clarification = {"question": question, "answer": answer}
                    if selection := clarification_selection(question, answer):
                        clarification["selection"] = selection
                    model_context = {
                        "question": previous_context,
                        "clarification": clarification,
                    }
                    root = "\n".join((previous_context, question, answer))[:8000]
                    search_text = "\n".join((answer, question, previous_context))
                    source_url = source_url or previous.input.url
            if result.status == "ok":
                clean_url = source_url.rstrip("/") if source_url else None
                url_source = self.corpus.urls.get(clean_url)
                if SCOPE.match(root):
                    result.status, result.message = "out_of_scope", "Prawdowid weryfikuje sprawdzalne informacje publiczne."
                elif rounds == 0 and not pinned and needs_place(root):
                    # Ostrzeżenia pogodowe są lokalne: bez miejsca dalibyśmy tylko „Brak potwierdzenia”.
                    # Bez przykładowych nazw: pytanie trafia do kontekstu rozmowy i nazwa zostałaby uznana za miejsce.
                    # Pytanie kończy się słowem „powiatu”, więc sama odpowiedź „bytowski” zostaje rozpoznana jako powiat.
                    self.clarify(result, "Gdzie? Wystarczy nazwa miasta albo powiatu.")
                elif self.settings.evaluator == "fake":
                    pool = list(pinned or []) + [row for row in self.corpus.sources.values()
                                                 if row["id"] not in {p["id"] for p in pinned or []}]
                    demo_result(result, root, pool, self.fake_evidence, at)
                elif (result.input.kind == "url" and url_source is None) or VAGUE.fullmatch(root):
                    self.clarify(result, "Które konkretne twierdzenie sprawdzić? Wklej jego treść.")
                else:
                    if result.input.kind == "url" and url_source is not None:
                        model_context["linked_source_id"] = url_source["id"]
                    candidates = self.corpus.search(search_text, source_url, pinned)
                    suspected = bool(SUSPICIOUS.search(search_text) or any(
                        SUSPICIOUS.search(row["excerpt"]) for row in candidates
                    ))
                    anchor = at.astimezone(ZoneInfo("Europe/Warsaw")).date().isoformat()
                    if not clarifies and not result.input.masked and not source_url and not suspected and not pinned:
                        lookup = [cache_text(root), self.corpus.version, self.settings.model,
                                  self.settings.url, PROMPT_VERSION, anchor]
                        cache_key = sha256(json.dumps(lookup, ensure_ascii=False).encode()).hexdigest()
                    cached = self.store.cached(cache_key, now) if cache_key and use_cache else None
                    if cached:
                        # Uwagę o znanej narracji liczymy zawsze od nowa (poniżej), żeby jej nie dublować.
                        result.items, result.summary = cached.items, cached.summary
                        result.topic, result.subject = cached.topic, cached.subject
                        result.notices = [n for n in cached.notices if n.type != "known_narrative"]
                        result.meta.cached, result.meta.estimated_cost_usd = True, 0.0
                    elif not candidates:
                        result.items = [missing_item("t1", root, "W zatwierdzonym korpusie nie znaleziono pasujących dowodów.")]
                        self.detect_topic(result, root, now)
                    elif not self.settings.key:
                        result.status, result.message = "technical_error", "Brakuje konfiguracji usługi modelu."
                    elif self.settings.paid_check_limit and not self.store.reserve_paid_check(self.settings.paid_check_limit):
                        result.status, result.message = "technical_error", "Pula sprawdzeń w tym demie została wykorzystana."
                    else:
                        self.assess(result, search_text, candidates, suspected, now, model_context)
            if result.status == "needs_clarification" and rounds >= 2:
                result.status, result.message, result.clarification_question = "ok", None, None
                result.items = [missing_item("t1", result.input.text_masked,
                    "Po doprecyzowaniu nadal brakuje informacji.", "Dokładna teza oraz źródło, którego dotyczy pytanie.")]
            if (result.status == "ok" and not pinned and result.input.kind != "url"
                    and not SUSPICIOUS.search(root)
                    and not any(notice.type == "instructions_ignored" for notice in result.notices)):
                if self.narrative_search:
                    case = self.narrative_search.find(root[:4000])
                    match = narratives.compare(case, root) if case else None
                else:
                    match = next(iter(narratives.find(root, self.narratives)), None)
                if match:
                    result.notices.append(NoticeItem(type="known_narrative", text=narratives.notice_text(match),
                                                     url=match["url"], label=match["narrative"],
                                                     state_outlet=match["state_outlet"]))
            if result.status == "ok" and not result.summary:
                result.summary = " ".join((item.answer or item.reason) for item in result.items[:2])
            result.meta.elapsed_ms = round((perf_counter() - start) * 1000)
            if cache_key and result.status == "ok" and not result.meta.cached and not any(
                notice.type == "instructions_ignored" for notice in result.notices
            ):
                # Cache only the shared verdict and source evidence, never individual session data.
                cache_result = result.model_copy(update={"input": input_info(""), "parent_id": None})
                self.store.cache(cache_key, now, cache_result)
            self.store.save(result, session_id, root, rounds)
            if register and result.status in {"ok", "needs_clarification"}:
                self.register_case(result, channel, at, root)
            if register and result.status == "ok":
                self.register_topic(result, channel, now)
            self.store.event(now, "check", result.id, {
                "status": result.status, "channel": channel, "elapsed_ms": result.meta.elapsed_ms,
                "estimated_cost_usd": result.meta.estimated_cost_usd, "corpus_version": self.corpus.version,
            })
        except HTTPError as error:
            error.close()
            self.fail(result, start)
        except (URLError, TimeoutError, OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, sqlite3.Error):
            self.fail(result, start)
        return result

    def assess(self, result, root, candidates, suspected, now, model_context):
        marker = "PW-" + token_hex(16)
        # Do not pass a suspicious document to the evaluator. It remains auditable in the catalog.
        candidates = [row for row in candidates if not SUSPICIOUS.search(row["excerpt"])]
        if not candidates:
            result.items = [missing_item("t1", root, "Brakuje materiałów nadających się do oceny.")]
            usage, guard_cost = {}, None
            self.detect_topic(result, root, now)
        else:
            with ThreadPoolExecutor(max_workers=1) as pool:
                task = pool.submit(self.provider.guard, root, self.known_subjects(now))
                assessment, usage = self.provider.assess(model_context, candidates, marker)
                try:
                    guard, guard_usage = task.result()
                    suspected = suspected or (guard.contains_instructions and guard.confidence != "low")
                    result.topic, result.subject = clean_topic(guard.topic, marker), clean_topic(guard.subject, marker)
                    guard_cost = self.provider.estimated_cost(guard_usage, self.settings.guard_model)
                except HTTPError as error:
                    error.close()
                    guard_cost = None
                    self.store.event(now, "guard_unavailable", result.id, {})
                except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
                    guard_cost = None
                    self.store.event(now, "guard_unavailable", result.id, {})
            if assessment.status == "needs_clarification":
                from app.core.safety import safe_copy
                self.clarify(result, safe_copy(assessment.clarification_question, marker) or "Którą informację sprawdzić?")
            elif assessment.status == "out_of_scope":
                result.status, result.message = "out_of_scope", "Prawdowid weryfikuje sprawdzalne informacje publiczne."
            elif assessment.items:
                result.items = [normalize(item, candidates, f"t{index}", root, marker)
                                for index, item in enumerate(assessment.items[:3], 1)]
            else:
                raise ValueError("Empty assessment")
            if result.status == "ok" and (assessment.partial_check or len(assessment.items) > 3):
                result.notices.append(NoticeItem(type="partial_check", text="Sprawdzono do trzech głównych tez."))
        cost = self.provider.estimated_cost(usage)
        if cost is not None and guard_cost is not None:
            result.meta.estimated_cost_usd = round(cost + guard_cost, 8)
        if suspected:
            result.notices.append(NoticeItem(type="instructions_ignored", text="Pominięto instrukcje zawarte w analizowanej treści."))
            self.store.event(now, "injection_suspected", result.id, {})
        dates = [row for item in result.items for row in item.evidence if row.archival]
        if dates:
            result.notices.append(NoticeItem(type="archival_material", text="Dowód jest archiwalny. Zwróć uwagę na jego datę."))

    def register_case(self, result, channel, at, context=None):
        """Łączy zgłoszenia o tym samym zdarzeniu lokalnym (zjawisko, powiat, dzień) w jedną sprawę.
        Po doprecyzowaniu bierzemy całą rozmowę: „Słupsk” sam nie mówi, o jakie zjawisko chodzi."""
        text = context or result.input.text_masked
        found = event_signature(text, at)
        if found is None:
            return None
        try:
            return self.store.case_register(found, found.title(), found.missing(), text, summarize(result),
                                            result.id, channel, at.isoformat())
        except sqlite3.Error:
            self.store.event(int(at.timestamp()), "case_register_failed", result.id, {})
            return None

    def detect_topic(self, result, root, now):
        """Temat, gdy nie było wywołania oceny (brak kandydatów): jedno tanie wywołanie guard modelu."""
        if not self.settings.key or self.settings.evaluator != "live":
            return
        try:
            guard, _ = self.provider.guard(root, self.known_subjects(now))
            result.topic, result.subject = clean_topic(guard.topic, None), clean_topic(guard.subject, None)
        except HTTPError as error:
            error.close()
        except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
            self.store.event(now, "topic_unavailable", result.id, {})

    def known_subjects(self, now):
        """Przedmioty tematów z ostatnich 48 h, najświeższe najpierw — model może przepisać pasujący."""
        try:
            subjects = self.store.topic_subjects(now - topics.WINDOW_S)
        except sqlite3.Error:
            return []
        # Przedmioty pochodzą z wiadomości innych osób: krótkie i bez śladów poleceń dla modelu.
        return [s for s in subjects if len(s) <= 60 and not SUSPICIOUS.search(s)]

    def register_topic(self, result, channel, now):
        """Dołącza zgłoszenie do tematu z ostatnich 48 h albo zakłada nowy (app/core/topics.py)."""
        title = topics.topic_text(result)
        found = topics.stems(result.subject or title)
        if not found:
            return None
        sources = sorted({row.source_id for item in result.items for row in item.evidence})
        item = result.items[0] if result.items else None
        label = (item.label or ("answer" if item.kind == "answer" else None)) if item else None
        try:
            topic_id = topics.best_match(found, self.store.topics_recent(now - topics.WINDOW_S))
            topic_id = topic_id or self.store.topic_add(title, found, sources, now, result.subject)
            self.store.topic_report(topic_id, now, result.id, channel, label, title, result.input.text_masked, sources)
            return topic_id
        except sqlite3.Error:
            self.store.event(now, "topic_register_failed", result.id, {})
            return None

    @staticmethod
    def clarify(result, question):
        result.status = "needs_clarification"
        result.message = "Potrzebna jest dodatkowa informacja."
        result.clarification_question = question

    @staticmethod
    def fail(result, start):
        result.status, result.message = "technical_error", ERROR_MESSAGE
        result.items, result.summary, result.clarification_question = [], None, None
        result.meta.elapsed_ms = round((perf_counter() - start) * 1000)


@lru_cache(maxsize=1)
def get_service():
    return Service(Settings())


def run_check(text, *, channel="web", lang="pl", session_id=None, use_cache=True, clarifies=None):
    service = get_service()
    bucket = CLIENT_BUCKET.get()
    if (
        service.settings.rate_limit_enabled
        and bucket
        and channel in {"web", "api"}
        and not service.store.charge(bucket, int(datetime.now(timezone.utc).timestamp()))
    ):
        return service.limit(text, channel)
    return service.run(text, channel=channel, lang=lang, session_id=session_id or SESSION.get(),
                       use_cache=use_cache, clarifies=clarifies)


def get_check(check_id, *, session_id=None):
    owner = session_id or SESSION.get()
    if not owner:
        return None
    row = get_service().store.read(check_id, owner)
    return row[0] if row else None


def delete_check(check_id, *, session_id):
    return bool(session_id and get_service().store.delete(session_id, check_id))


def delete_session(session_id):
    return get_service().store.delete(session_id) if session_id else 0


def list_sources():
    return get_service().sources()
