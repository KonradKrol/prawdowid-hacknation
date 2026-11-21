"""WhatsApp Cloud API formatted demonstration adapter. It performs no live send."""

from hashlib import sha256
from hmac import compare_digest, new as hmac_new
import json
from time import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse

from app.api.checks import charge
from app.contract import CheckRequest
from app.core.service import get_service, run_check

router = APIRouter()
DEMO_SENDER = "00000000000"
MAX_WEBHOOK_BYTES = 65536


def messages(payload):
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        raise ValueError("Invalid webhook object")
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "messages":
                continue
            for message in change.get("value", {}).get("messages", []):
                if message.get("type") == "text":
                    identifier = message["id"]
                    sender = message["from"]
                    text = message["text"]["body"]
                    if not all(isinstance(part, str) and part for part in (identifier, sender, text)):
                        raise ValueError("Invalid message")
                    yield identifier, sender, text


def outgoing(sender, body):
    return {"messaging_product": "whatsapp", "to": sender, "type": "text",
            "text": {"preview_url": False, "body": body}}


def process(payload):
    try:
        inbound = list(messages(payload))
    except (AttributeError, KeyError, TypeError, ValueError):
        raise HTTPException(400, "Niepoprawna wiadomość WhatsApp.")
    if len(inbound) > 5:
        raise HTTPException(413, "Zbyt wiele wiadomości w żądaniu.")
    answers = []
    service = get_service()
    for external_id, sender, text in inbound:
        # Only the hashed message ID and outgoing text are stored.
        key = sha256(external_id.encode()).hexdigest()
        if service.store.reserve_message(key, int(time())):
            try:
                result = run_check(text, channel="adapter")
                if result.status == "technical_error":
                    service.store.release_message(key)
                entry = {"check_id": result.id, "status": result.status,
                         "body": (result.summary or result.clarification_question or result.message
                                  or "Sprawdzenie zakończone.")[:3500],
                         "items": [item.model_dump() for item in result.items]}
                if result.status != "technical_error":
                    service.store.finish_message(key, {
                        "check_id": entry["check_id"], "status": entry["status"], "body": entry["body"],
                    })
            except Exception:
                service.store.release_message(key)
                raise
        else:
            entry = service.store.message(key)
            if entry is None:
                continue
        answers.append({"check_id": entry["check_id"], "status": entry["status"],
                        "simulated": True, "message": outgoing(sender, entry["body"]),
                        "items": entry.get("items", [])})
    return {"simulated": True, "messages": answers}


@router.get("/api/whatsapp/webhook", response_class=PlainTextResponse)
def handshake(mode: str = Query(alias="hub.mode"), token: str = Query(alias="hub.verify_token"),
              challenge: str = Query(alias="hub.challenge", max_length=256)):
    configured = get_service().settings.whatsapp_token
    if not configured or mode != "subscribe" or not compare_digest(configured.encode(), token.encode()):
        raise HTTPException(403, "Weryfikacja webhooka nie powiodła się.")
    return challenge


@router.post("/api/whatsapp/webhook")
async def webhook(request: Request):
    secret = get_service().settings.whatsapp_secret
    received = request.headers.get("X-Hub-Signature-256", "")
    if not secret or not received.startswith("sha256="):
        raise HTTPException(403, "Wymagany jest prawidłowy podpis webhooka.")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_WEBHOOK_BYTES:
            raise HTTPException(413, "Żądanie jest za duże.")
    expected = "sha256=" + hmac_new(secret.encode(), body, sha256).hexdigest()
    if not compare_digest(expected.encode(), received.encode()):
        raise HTTPException(403, "Podpis webhooka jest nieprawidłowy.")
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeError):
        raise HTTPException(400, "Niepoprawny JSON.")
    return await run_in_threadpool(process, payload)


def simulate(text):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"field": "messages", "value": {"messaging_product": "whatsapp",
            "messages": [{"id": "demo-" + uuid4().hex, "from": DEMO_SENDER, "type": "text",
                          "text": {"body": text}}]}}]}],
    }
    return process(payload)


@router.post("/api/whatsapp/demo")
def demo(payload: CheckRequest, request: Request):
    if not charge(request, "whatsapp-demo"):
        raise HTTPException(429, "Za dużo zgłoszeń. Spróbuj ponownie za chwilę.")
    return simulate(payload.text)
