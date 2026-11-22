"""HTTP interface shared by the Prawdowid website and future channel adapters."""

import json
import os
from pathlib import Path
from threading import BoundedSemaphore, Lock

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from prawdowid_core import DEFAULT_CORPUS, load_corpus
from prawdowid_verify import MODEL, evaluate_with_openai, verify


DEFAULT_METRICS = Path(__file__).resolve().parent / "pomiary_backend.jsonl"
LOCAL_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


class CheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=4000)


def configured_key():
    return os.environ.get("PRAWDOWID_API_KEY") or os.environ.get("OPENAI_API_KEY")


def evaluate(question, candidates, model):
    key = configured_key()
    if not key:
        raise PermissionError("Brak klucza modelu.")
    return evaluate_with_openai(question, candidates, model, key)


def create_app(*, corpus=DEFAULT_CORPUS, metrics=DEFAULT_METRICS, evaluator=evaluate):
    app = FastAPI(title="Prawdowid", version="0.1.0")
    metrics_lock = Lock()
    capacity = BoundedSemaphore(2)
    model = os.environ.get("PRAWDOWID_MODEL", MODEL)
    configured_origins = os.environ.get("PRAWDOWID_CORS_ORIGINS")
    origins = (
        [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
        if configured_origins is not None else LOCAL_ORIGINS
    )
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    @app.get("/health")
    def health():
        try:
            sources, version = load_corpus(corpus)
        except (OSError, ValueError):
            return JSONResponse({"status": "corpus_unavailable"}, status_code=503)
        return {
            "status": "ok",
            "model_configured": bool(configured_key()),
            "corpus": {
                "version": version,
                "documents": len(sources),
                "domains": len({source["domain"] for source in sources.values()}),
                "source_types": sorted({source["type"] for source in sources.values()}),
            },
        }

    @app.post("/api/v1/checks")
    def check(payload: CheckRequest):
        if not capacity.acquire(blocking=False):
            return JSONResponse(
                {"status": "busy", "message": "Trwają inne sprawdzenia. Spróbuj za chwilę.", "items": []},
                status_code=429,
                headers={"Retry-After": "2"},
            )
        try:
            result = verify(payload.question, corpus, model, evaluator)
            if metrics is not None:
                fields = ("id", "status", "model", "corpus_version", "candidate_ids",
                          "usage", "elapsed_ms", "estimated_cost_usd")
                event = {field: result[field] for field in fields if field in result}
                try:
                    with metrics_lock, Path(metrics).open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                except OSError:
                    return JSONResponse(
                        {"status": "technical_error", "message": "Nie udało się zapisać przebiegu sprawdzenia.", "items": []},
                        status_code=503,
                    )
            status_code = {"ok": 200, "invalid_input": 422, "technical_error": 503}[result["status"]]
            return JSONResponse(result, status_code=status_code)
        finally:
            capacity.release()

    return app


app = create_app()
