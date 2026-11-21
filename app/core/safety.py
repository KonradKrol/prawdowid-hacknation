import re
import unicodedata
from urllib.parse import urlsplit

from app.contract import InputInfo

URL = re.compile(r"https?://[^\s<>]+", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", re.I)
PHONE = re.compile(r"(?<!\w)(?:\+48[ -]?)?\d{3}[ -]\d{3}[ -]\d{3}(?!\w)|(?<!\w)\+48\d{9}(?!\w)")
PESEL = re.compile(r"(?<!\d)\d{11}(?!\d)")
ACCOUNT = re.compile(r"(?<!\w)(?:PL[ -]?)?\d{2}(?:[ -]?\d{4}){6}(?!\d)", re.I)
CARD = re.compile(r"(?<!\d)\d{4}(?:[ -]?\d{4}){3}(?!\d)")
IDENTITY = re.compile(r"(?i)\b(?:dowód|dowod)\s+(?:osobisty\s+)?[A-Z]{3}\s?\d{6}\b")
SUSPICIOUS = re.compile(
    r"\b(?:zignoruj|ignoruj|pomiń|ignore|disregard|override|ігноруй|игнорируй)\b.{0,80}"
    r"\b(?:instrukcj\w*|poleceni\w*|zasad\w*|instructions?\w*|prompt\w*|правил\w*|інструкц\w*)\b"
    r"|\b(?:system prompt|developer message)\b", re.I | re.S,
)
SCOPE = re.compile(
    r"^\s*(?:napisz|stwórz|wymyśl|przetłumacz|zaprogramuj|zagraj|rozwiąż|oblicz|poleć)\b"
    r"|^\s*czy\s+(?:mój\s+)?(?:mąż|partner|partnerka|żona)\s+mnie\s+zdradza"
    r"|^\s*(?:jak (?:mam |powinienem |powinnam )?(?:wyleczyć|leczyć|zainwestować)|czy powinien[ae]m\b)"
    r"|^\s*(?:czy\s+)?[0-9().\s+*/=−-]+[?.!]?\s*$", re.I,
)
VAGUE = re.compile(r"^\s*(?:czy to prawda|czy to fake|sprawdź to|a co z tym\s+\w+)[?.!]?\s*$", re.I)


def sanitize(text):
    return "".join(
        char for char in unicodedata.normalize("NFKC", text)
        if char in "\r\n\t" or unicodedata.category(char) not in {"Cc", "Cf", "Cs"}
    )


def pesel_valid(digits):
    weights = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
    return (10 - sum(int(d) * w for d, w in zip(digits, weights)) % 10) % 10 == int(digits[-1])


def card_valid(value):
    digits = [int(char) for char in value if char.isdecimal()][::-1]
    return sum(d if i % 2 == 0 else (2 * d - 9 if d > 4 else 2 * d)
               for i, d in enumerate(digits)) % 10 == 0


def redact(text):
    kinds = []
    for kind, pattern, validate in (
        ("email", EMAIL, None), ("pesel", PESEL, pesel_valid), ("account", ACCOUNT, None),
        ("card", CARD, card_valid), ("identity", IDENTITY, None), ("phone", PHONE, None),
    ):
        def replace(match):
            if validate is not None and not validate(match.group()):
                return match.group()
            if kind not in kinds:
                kinds.append(kind)
            return "[dane ukryte]"
        text = pattern.sub(replace, text)
    return text, kinds


def input_info(text):
    cleaned = sanitize(text).strip()
    urls = URL.findall(cleaned)
    safe_url = None
    if urls:
        try:
            parsed = urlsplit(urls[0].rstrip(").,!?"))
            if parsed.hostname and not parsed.username and not parsed.password:
                safe_url = parsed._replace(query="", fragment="").geturl()
        except ValueError:
            pass
    # Preserve no user-provided URL parameters, including in stored text.
    cleaned = URL.sub("[adres URL]", cleaned)
    masked, kinds = redact(cleaned)
    return InputInfo(text_masked=masked, url=safe_url, masked=kinds,
                     kind="url" if urls and cleaned.strip(" .!?,") == "[adres URL]" else "text_with_url" if urls else "text")


def safe_copy(text, canary=""):
    if text is None:
        return None
    if canary and canary.casefold() in text.casefold():
        raise ValueError("Unexpected protected marker in output")
    return " ".join(URL.sub("", redact(sanitize(text))[0]).split())
