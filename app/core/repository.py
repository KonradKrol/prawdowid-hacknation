import sqlite3
from threading import Lock

from prawdowid_core import index_corpus, load_corpus, search_sources


class Corpus:
    def __init__(self, path):
        self.sources, self.version = load_corpus(path)
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

    def search(self, text, url=None):
        with self.lock:
            rows = search_sources(self.index, self.sources, text)
        match = self.urls.get((url or "").rstrip("/"))
        if match is not None:
            return [match] + [row for row in rows if row["id"] != match["id"]][:3]
        return rows

    def close(self):
        self.index.close()
