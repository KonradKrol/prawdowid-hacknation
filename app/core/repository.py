from hashlib import sha256
import sqlite3
from threading import Lock

from prawdowid_core import FRAGMENT_SEPARATOR, fold, index_corpus, load_corpus, search_sources


class Corpus:
    def __init__(self, path):
        self.sources, self.base_version = load_corpus(path)
        self.version = self.base_version
        self.live = {}
        self.lock = Lock()
        self.index = sqlite3.connect(":memory:", check_same_thread=False)
        try:
            approved = {key: row for key, row in self.sources.items()
                        if not row.get("guard_suspected")}
            index_corpus(self.index, approved)
            self.index.commit()
        except BaseException:
            self.close()
            raise
        self.urls = {row["url"].rstrip("/"): row for row in approved.values()}

    def upsert(self, source, replaces=None):
        """Dodaje wpis z kanału urzędowego do indeksu bez restartu. Poprzednia wersja wypada z wyszukiwania."""
        if "excerpts" in source:
            source["excerpt"] = FRAGMENT_SEPARATOR.join(" ".join(part.split()) for part in source["excerpts"])
        with self.lock:
            if replaces and replaces in self.sources:
                old = self.sources.pop(replaces)
                self.live.pop(replaces, None)
                self.urls.pop(old["url"].rstrip("/"), None)
                self.index.execute("DELETE FROM source_search WHERE source_id=?", (replaces,))
            self.index.execute("DELETE FROM source_search WHERE source_id=?", (source["id"],))
            self.index.execute(
                "INSERT INTO source_search VALUES (?, ?, ?, ?, ?, ?)",
                (source["id"], fold(source["title"]), fold(source["excerpt"]), fold(source.get("scope", "")),
                 fold(source["publisher"]), source.get("published_on") or ""))
            self.index.commit()
            self.sources[source["id"]] = source
            self.live[source["id"]] = source
            self.urls[source["url"].rstrip("/")] = source
            digest = sha256(self.base_version.encode())
            for key in sorted(self.live):
                digest.update(key.encode())
            self.version = digest.hexdigest()

    def remove(self, source_id):
        """Usuwa wpis z kanału urzędowego z indeksu (np. symulację z panelu moderatora)."""
        with self.lock:
            old = self.sources.pop(source_id, None)
            self.live.pop(source_id, None)
            if old is not None:
                self.urls.pop(old["url"].rstrip("/"), None)
            self.index.execute("DELETE FROM source_search WHERE source_id=?", (source_id,))
            self.index.commit()
            digest = sha256(self.base_version.encode())
            for key in sorted(self.live):
                digest.update(key.encode())
            self.version = digest.hexdigest()
        return old is not None

    def search(self, text, url=None, pinned=None):
        with self.lock:
            rows = search_sources(self.index, self.sources, text)
        first = list(pinned or [])
        match = self.urls.get((url or "").rstrip("/"))
        if match is not None and all(row["id"] != match["id"] for row in first):
            first.append(match)
        if first:
            ids = {row["id"] for row in first}
            return first + [row for row in rows if row["id"] not in ids][:max(0, 4 - len(first))]
        return rows

    def close(self):
        self.index.close()
