"""Imports publisher-supplied ClaimReview records discovered via Demagog's RSS."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import json
import logging
import re
from time import perf_counter
from urllib.request import Request, urlopen
from xml.etree import ElementTree


FEED = "demagog-claimreview"
URL = "https://demagog.org.pl/fake_news/feed/"
ARTICLE = re.compile(r"https://demagog\.org\.pl/fake_news/[a-z0-9][a-z0-9-]*/?")
JSON_LD = re.compile(r'<script\b[^>]*\btype=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)
LOGGER = logging.getLogger(__name__)


def fetch(url):
    request = Request(url, headers={"User-Agent": "Prawdoskop/1.0"})
    with urlopen(request, timeout=6) as response:
        if response.url.rstrip("/") != url.rstrip("/"):
            raise ValueError("Unexpected redirect from Demagog")
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError("Demagog response exceeded the size limit")
    return body


def review_fragments(page, url):
    fragments = []
    for script in JSON_LD.findall(page.decode("utf-8")):
        try:
            value = json.loads(script)
        except ValueError:
            continue
        for review in value if isinstance(value, list) else [value]:
            if not isinstance(review, dict) or review.get("@type") != "ClaimReview":
                continue
            if str(review.get("url", "")).rstrip("/") != url:
                continue
            claim = review.get("claimReviewed")
            rating = review.get("reviewRating")
            rating = rating.get("alternateName") if isinstance(rating, dict) else None
            if not isinstance(claim, str) or not isinstance(rating, str):
                continue
            claim, rating = " ".join(claim.split()), " ".join(rating.split())
            if claim and len(claim) <= 350 and rating and len(rating) <= 60:
                fragments.append(f"Teza sprawdzana przez Demagoga: {claim} | Ocena Demagoga: {rating}")
    return list(dict.fromkeys(fragments))[:4]


class DemagogSync:
    def __init__(self, service, fetcher=fetch):
        self.store = service.store
        self.corpus = service.corpus
        self.fetch = fetcher
        self.skipped = set()

    def load_current(self):
        for source in self.store.official_current(FEED):
            if source["url"].rstrip("/") not in self.corpus.urls:
                self.corpus.upsert(source)

    def sync(self):
        started = perf_counter()
        stamp = datetime.now(timezone.utc).isoformat()
        run_id = self.store.sync_start(FEED, stamp)
        indexed = rejected = 0
        try:
            rss = ElementTree.fromstring(self.fetch(URL))
            channel = rss.find("channel")
            if channel is None:
                raise ValueError("Missing RSS channel")
        except (OSError, ValueError, ElementTree.ParseError) as error:
            LOGGER.warning("Demagog RSS import failed: %s", error)
            self.store.sync_finish(run_id, "error", datetime.now(timezone.utc).isoformat(),
                                   round((perf_counter() - started) * 1000), error=type(error).__name__)
            return indexed

        fetched = 0
        items = channel.findall("item")[:60]
        self.skipped.intersection_update(item.findtext("link", "").strip().rstrip("/") for item in items)
        items.sort(key=lambda item: item.findtext("link", "").strip().rstrip("/") in self.skipped)
        for item in items:
            url = item.findtext("link", "").strip().rstrip("/")
            title = " ".join(item.findtext("title", "").split())
            if not ARTICLE.fullmatch(url) or not title or url in self.corpus.urls:
                continue
            if fetched >= 8:
                break
            fetched += 1
            try:
                published = parsedate_to_datetime(item.findtext("pubDate", ""))
                fragments = review_fragments(self.fetch(url + "/"), url)
            except (OSError, ValueError) as error:
                rejected += 1
                self.skipped.add(url)
                LOGGER.warning("Demagog article skipped (%s): %s", url, error)
                continue
            if not fragments:
                rejected += 1
                self.skipped.add(url)
                continue
            self.skipped.discard(url)
            entry_id = sha256(url.encode()).hexdigest()[:20]
            source = {
                "id": f"{FEED}-{entry_id}", "url": url, "title": title,
                "publisher": "Stowarzyszenie Demagog", "domain": "demagog.org.pl", "host": "demagog.org.pl",
                "type": "fact-check", "kind": "fact-check", "language": "pl", "archival": False,
                "published_on": published.date().isoformat(), "checked_on": stamp[:10],
                "excerpts": fragments, "scope": "Teza i ocena redakcji z metadanych ClaimReview Demagoga.",
                "usage": "Metadane ClaimReview z podaniem redakcji i odnośnika do publikacji.",
            }
            digest = sha256(json.dumps(source, ensure_ascii=False).encode()).hexdigest()
            self.store.official_insert(FEED, entry_id, 1, digest, source, published.isoformat(), stamp,
                                       datetime.now(timezone.utc).isoformat())
            self.corpus.upsert(source)
            indexed += 1
        self.store.sync_finish(run_id, "partial" if rejected else "ok", datetime.now(timezone.utc).isoformat(),
                               round((perf_counter() - started) * 1000), fetched=fetched, new=indexed, rejected=rejected)
        return indexed
