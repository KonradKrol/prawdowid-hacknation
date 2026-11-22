"""Local source retrieval and literal citation validation for Prawdowid."""

import argparse
from contextlib import closing
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
from urllib.parse import urlsplit


DEFAULT_CORPUS = Path(__file__).resolve().parent / "Research" / "Prawdowid_Korpus_Start.jsonl"
REQUIRED_FIELDS = ("id", "title", "publisher", "type", "domain", "url", "checked_on", "excerpt")
STOP_WORDS = set(
    "aby ale albo było była były czy dla gdy ich jak jaka jaki jakie jest już "
    "kiedy kto która które który ma miał na nie oraz po pod przy się tak też to "
    "tylko we za ze że co jeśli jesli będą beda będzie bedzie prawda czy".split()
)
TOKENS = re.compile(r"[^\W_]+", re.UNICODE)
# Rozdziela fragmenty w polu `excerpt` wyprowadzonym z listy `excerpts` (indeks i prompt widzą jeden tekst).
FRAGMENT_SEPARATOR = " ¶ "


def load_corpus(path):
    raw = Path(path).read_bytes()
    sources = {}
    for line_number, line in enumerate(raw.decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            source = json.loads(line)
            if not isinstance(source, dict):
                raise ValueError("rekord musi być obiektem")
            if "excerpts" in source:
                parts = source["excerpts"]
                if (not isinstance(parts, list) or not parts
                        or not all(isinstance(p, str) and p.strip() and "¶" not in p for p in parts)):
                    raise ValueError("pole excerpts musi być niepustą listą fragmentów tekstu")
                source["excerpts"] = [" ".join(p.split()) for p in parts]
                source["excerpt"] = FRAGMENT_SEPARATOR.join(source["excerpts"])
            for field in REQUIRED_FIELDS:
                if not isinstance(source.get(field), str) or not source[field].strip():
                    raise ValueError(f"brak poprawnego pola {field}")
            url = urlsplit(source["url"])
            if url.scheme not in {"http", "https"} or not url.hostname:
                raise ValueError("źródło wymaga bezwzględnego adresu HTTP(S)")
            date.fromisoformat(source["checked_on"])
            if source.get("published_on") is not None:
                date.fromisoformat(source["published_on"])
            if not isinstance(source.get("scope", ""), str):
                raise ValueError("pole scope musi być tekstem")
            if source["id"] in sources:
                raise ValueError(f"powtarzający się identyfikator {source['id']}")
        except (TypeError, ValueError) as error:
            raise ValueError(f"{path}, wiersz {line_number}: {error}") from error
        sources[source["id"]] = source
    if not sources:
        raise ValueError(f"{path}: pusty korpus")
    version = hashlib.sha256(raw).hexdigest()
    return sources, version


def fold(text):
    """„ł” nie jest literą z ogonkiem w Unicode, więc remove_diacritics jej nie zamienia — robimy to sami."""
    return text.replace("ł", "l").replace("Ł", "L")


def query_term(word):
    """Polska odmiana: szukamy po początku słowa (wrocławiu → wrocl*, darmowe → darmo*)."""
    return f'"{word}"' if len(word) < 6 else f'"{word[:max(4, len(word) - 3)]}"*'


def index_corpus(connection, sources):
    connection.execute(
        """CREATE VIRTUAL TABLE source_search USING fts5(
               source_id UNINDEXED, title, excerpt, scope, publisher, published_on,
               tokenize='unicode61 remove_diacritics 2'
           )"""
    )
    connection.executemany(
        "INSERT INTO source_search VALUES (?, ?, ?, ?, ?, ?)",
        (
            (
                source["id"],
                fold(source["title"]),
                fold(source["excerpt"]),
                fold(source.get("scope", "")),
                fold(source["publisher"]),
                source.get("published_on") or "",
            )
            for source in sources.values()
        ),
    )


def search_sources(connection, sources, question, limit=4):
    """Return document candidates. A candidate alone does not justify a verdict."""
    if not 1 <= limit <= 8:
        raise ValueError("limit musi być od 1 do 8")
    words = TOKENS.findall(fold(question.casefold()))
    terms = list(dict.fromkeys(word for word in words if len(word) >= 2 and word not in STOP_WORDS))
    if not terms:
        return []
    # Limit the query after tokenization. Only letters and numbers enter the FTS expression.
    match = " OR ".join(query_term(term) for term in terms[:48])
    rows = connection.execute(
        """SELECT source_id
           FROM source_search
           WHERE source_search MATCH ?
           ORDER BY bm25(source_search, 0, 2, 3, 1, 1, 1), source_id
           LIMIT ?""",
        (match, limit),
    )
    return [sources[source_id] for (source_id,) in rows]


def fragments(source):
    """Dosłowne fragmenty dokumentu: lista `excerpts`, a w starszych rekordach jedno pole `excerpt`."""
    return source.get("excerpts") or [source["excerpt"]]


def literal_citation(candidates, source_id, quote):
    """Return canonical citation metadata if the quote is present in ONE retrieved fragment.

    Cytat nie może łączyć dwóch fragmentów, więc sprawdzamy każdy osobno."""
    normalized_quote = " ".join(quote.split())
    if not normalized_quote or FRAGMENT_SEPARATOR.strip() in normalized_quote:
        return None
    for source in candidates:
        if source["id"] == source_id and any(normalized_quote in " ".join(part.split()) for part in fragments(source)):
            return {
                "source_id": source_id,
                "title": source["title"],
                "publisher": source["publisher"],
                "published_on": source.get("published_on"),
                "url": source["url"],
                "quote": normalized_quote,
            }
    return None


def main():
    parser = argparse.ArgumentParser(description="Wyszukaj lokalne materiały Prawdowidu.")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("question", nargs="?", help="Pytanie. Bez argumentu pokaż statystyki zbioru.")
    args = parser.parse_args()
    try:
        sources, version = load_corpus(args.corpus)
        if args.question is None:
            result = {
                "documents": len(sources),
                "domain_groups": sorted({doc["domain"] for doc in sources.values()}),
                "source_types": sorted({doc["type"] for doc in sources.values()}),
                "version": version,
            }
        else:
            with closing(sqlite3.connect(":memory:")) as connection:
                index_corpus(connection, sources)
                candidates = search_sources(connection, sources, args.question, args.limit)
            result = {
                "status": "candidates_found" if candidates else "no_candidates",
                "corpus_version": version,
                "candidates": candidates,
            }
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(2, f"Błąd rdzenia: {error}\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
