from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from functools import lru_cache
from hashlib import sha256
import json
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
from app.storage.db import Store

SESSION = ContextVar("prawdowid_session", default=None)
CLIENT_BUCKET = ContextVar("prawdowid_client_bucket", default=None)
ERROR_MESSAGE = "Wystąpił błąd techniczny i nie udało się zakończyć sprawdzenia."


class Service:
    def __init__(self, settings):
        self.settings = settings
        self.store = Store(settings.data_dir / "prawdowid.db")
        self.corpus = Corpus(settings.corpus)
        self.provider = Provider(settings)
        self.last_prune = 0
        self.maintenance = Lock()

    def sources(self):
        return SourcesResponse(
            documents=len(self.corpus.sources), domains=len({source["domain"] for source in self.corpus.sources.values()}),
            source_types=sorted({source["type"] for source in self.corpus.sources.values()}),
            version=self.corpus.version, sources=[PublicSource.model_validate(row) for row in self.corpus.sources.values()],
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
                quote=None if date else src["excerpt"], field="published_on" if date else "excerpt")],
        )
        if label == "misleading":
            from app.contract import ContextMismatch
            draft.context_mismatch = ContextMismatch(field="date", claim_value="dziś",
                source_value=src.get("published_on") or "inna data", explanation="Próba różnicy daty.")
        return normalize(draft, [src], "t1", claim, "")

    def run(self, text, *, channel="web", lang="pl", session_id=None, use_cache=True, clarifies=None):
        if lang != "pl":
            raise ValueError("Unsupported language")
        start = perf_counter()
        at = datetime.now(timezone.utc)
        now = int(at.timestamp())
        result = self.result(text[:4000], channel, at, clarifies)
        root, rounds = result.input.text_masked, 0
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
                    root = (previous_context + "\n" + (previous.clarification_question or "") +
                            "\n" + result.input.text_masked)[:8000]
            if result.status == "ok":
                source_url = result.input.url
                clean_url = source_url.rstrip("/") if source_url else None
                if SCOPE.match(root):
                    result.status, result.message = "out_of_scope", "Prawdowid weryfikuje sprawdzalne informacje publiczne."
                elif self.settings.evaluator == "fake":
                    demo_result(result, root, list(self.corpus.sources.values()), self.fake_evidence)
                elif (result.input.kind == "url" and clean_url not in self.corpus.urls) or VAGUE.fullmatch(root):
                    self.clarify(result, "Które konkretne twierdzenie sprawdzić? Wklej jego treść.")
                else:
                    candidates = self.corpus.search(root, source_url)
                    suspected = bool(SUSPICIOUS.search(root) or any(SUSPICIOUS.search(row["excerpt"]) for row in candidates))
                    anchor = at.astimezone(ZoneInfo("Europe/Warsaw")).date().isoformat()
                    if not clarifies and not result.input.masked and not source_url and not suspected:
                        lookup = [" ".join(root.split()), self.corpus.version, self.settings.model,
                                  self.settings.url, PROMPT_VERSION, anchor]
                        cache_key = sha256(json.dumps(lookup, ensure_ascii=False).encode()).hexdigest()
                    cached = self.store.cached(cache_key, now) if cache_key and use_cache else None
                    if cached:
                        result.items, result.summary, result.notices = cached.items, cached.summary, cached.notices
                        result.meta.cached, result.meta.estimated_cost_usd = True, 0.0
                    elif not candidates:
                        result.items = [missing_item("t1", root, "W zatwierdzonym korpusie nie znaleziono pasujących dowodów.")]
                    elif not self.settings.key:
                        result.status, result.message = "technical_error", "Brakuje konfiguracji usługi modelu."
                    else:
                        self.assess(result, root, candidates, suspected, now)
            if result.status == "needs_clarification" and rounds >= 2:
                result.status, result.message, result.clarification_question = "ok", None, None
                result.items = [missing_item("t1", result.input.text_masked,
                    "Po doprecyzowaniu nadal brakuje informacji.", "Dokładna teza oraz źródło, którego dotyczy pytanie.")]
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

    def assess(self, result, root, candidates, suspected, now):
        marker = "PW-" + token_hex(16)
        # Do not pass a suspicious document to the evaluator. It remains auditable in the catalog.
        candidates = [row for row in candidates if not SUSPICIOUS.search(row["excerpt"])]
        if not candidates:
            result.items = [missing_item("t1", root, "Brakuje materiałów nadających się do oceny.")]
            usage, guard_cost = {}, None
        else:
            with ThreadPoolExecutor(max_workers=1) as pool:
                task = pool.submit(self.provider.guard, root)
                assessment, usage = self.provider.assess(root, candidates, marker)
                try:
                    guard, guard_usage = task.result()
                    suspected = suspected or (guard.contains_instructions and guard.confidence != "low")
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
