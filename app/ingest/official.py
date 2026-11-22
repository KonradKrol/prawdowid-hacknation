"""Przyrostowy import z zatwierdzonego kanału urzędowego i ponowna ocena otwartych spraw.

Przebieg jednej synchronizacji:
1. pobranie listy ostrzeżeń (albo dane podane w teście),
2. dla każdego wpisu porównanie skrótu treści z ostatnią zapisaną wersją:
   bez zmian → tylko `last_seen_at`; nowy lub zmieniony → nowa wersja w SQLite i w indeksie,
3. dla każdego nowego lub zmienionego wpisu ponowna ocena pasujących OTWARTYCH spraw
   istniejącym mechanizmem weryfikacji (`Service.run` z wpisem przypiętym do kandydatów),
4. zapis propozycji: poprzedni wynik, proposowany wynik i cytat z nowego wpisu.
Powtórny import tego samego wpisu nie tworzy wersji, propozycji ani rekordów w indeksie.
"""

from datetime import datetime, timezone
from time import perf_counter

from app.ingest import imgw


def now_utc():
    return datetime.now(timezone.utc)


def summarize(result):
    """Skrót wyniku sprawdzenia, który zapisujemy przy sprawie i w propozycji."""
    item = result.items[0] if result.items else None
    return {
        "check_id": result.id,
        "status": result.status,
        "label": item.label if item else None,
        "kind": item.kind if item else None,
        "reason": (item.reason if item else result.message) or "",
        "missing_evidence": item.missing_evidence if item else None,
        "sources": sorted({row.source_id for item in result.items for row in item.evidence}),
    }


class OfficialSync:
    feed = imgw.FEED

    def __init__(self, service, fetcher=imgw.fetch):
        self.service = service
        self.store = service.store
        self.fetcher = fetcher

    def load_current(self):
        """Po starcie aplikacji przywraca do indeksu najnowsze wersje zapisanych wpisów."""
        for source in self.store.official_current(self.feed):
            self.service.corpus.upsert(source)

    def sync(self, raw=None, at=None):
        started = perf_counter()
        at = at or now_utc()
        stamp = at.isoformat()
        run_id = self.store.sync_start(self.feed, stamp)
        counts = {"fetched": 0, "new": 0, "changed": 0, "unchanged": 0, "rejected": 0, "proposals": 0}
        try:
            payload = raw if raw is not None else self.fetcher()
            entries, counts["rejected"] = imgw.parse(payload)
        except Exception as error:  # noqa: BLE001 - każdy błąd pobrania ma trafić do raportu
            message = f"{type(error).__name__}: {error}"[:300]
            self.store.sync_finish(run_id, "error", now_utc().isoformat(), round((perf_counter() - started) * 1000),
                                   error=message, **counts)
            self.store.event(int(at.timestamp()), "official_sync_failed", None, {"feed": self.feed, "error": message})
            return {"run_id": run_id, "status": "error", "error": message, **counts, "proposal_ids": []}
        counts["fetched"] = len(entries)
        touched = []
        for entry in entries:
            previous = self.store.official_latest(self.feed, entry.entry_id)
            if previous and previous["content_hash"] == entry.content_hash:
                counts["unchanged"] += 1
                self.store.official_seen(self.feed, entry.entry_id, previous["version"], stamp)
                continue
            version = previous["version"] + 1 if previous else 1
            source = imgw.to_source(entry, version, at)
            self.service.corpus.upsert(source, replaces=previous["source"]["id"] if previous else None)
            indexed = now_utc().isoformat()
            self.store.official_insert(self.feed, entry.entry_id, version, entry.content_hash, source,
                                       entry.published_at.isoformat(), stamp, indexed)
            counts["changed" if previous else "new"] += 1
            touched.append(source)
        proposal_ids, failures = [], []
        for source in touched:
            created, failed = self.reassess(source)
            proposal_ids += created
            failures += failed
        counts["proposals"] = len(proposal_ids)
        status = "ok" if not failures else "partial"
        error = "; ".join(failures)[:300] or None
        self.store.sync_finish(run_id, status, now_utc().isoformat(), round((perf_counter() - started) * 1000),
                               error=error, **counts)
        return {"run_id": run_id, "status": status, "error": error, **counts, "proposal_ids": proposal_ids}

    def reassess(self, source):
        """Ocenia ponownie tylko otwarte sprawy, których dotyczy wpis (zjawisko, powiat, dzień)."""
        created, failed = [], []
        for case in self.store.cases(status="open"):
            signature = _from_case(case)
            if not imgw.covers(source, signature):
                continue
            result = self.service.run(case["text"], channel="api", use_cache=False, pinned=[source], register=False)
            if result.status != "ok":
                failed.append(f"sprawa {case['id']}: {result.status}")
                continue
            proposed = summarize(result)
            quote = next((row.quote for item in result.items for row in item.evidence
                          if row.source_id == source["id"] and row.quote), None)
            previous = case["last_result"]
            if proposed["label"] == previous.get("label") and quote is None:
                continue
            proposal_id = self.store.proposal_add(case["id"], source, now_utc().isoformat(), previous, proposed, quote)
            if proposal_id:
                created.append(proposal_id)
        return created, failed

    def status(self, stale_after_s=1800):
        runs = self.store.sync_runs(self.feed, limit=10)
        last_ok = next((run for run in runs if run["status"] in {"ok", "partial"}), None)
        last = runs[0] if runs else None
        stale = True
        if last_ok and last_ok["finished_at"]:
            stale = (now_utc() - datetime.fromisoformat(last_ok["finished_at"])).total_seconds() > stale_after_s
        entries = self.store.official_entries(self.feed)
        return {
            "feed": self.feed, "url": imgw.URL,
            "last_run": last, "last_success": last_ok,
            "failing": bool(last and last["status"] == "error"), "stale": stale,
            "entries": len({row["entry_id"] for row in entries}), "versions": len(entries),
            "lag": lag_stats(entries), "runs": runs,
        }


def _from_case(case):
    from datetime import date
    from app.ingest.places import Signature
    return Signature(case["hazard"], tuple(case["counties"]), date.fromisoformat(case["day"]))


def lag_stats(entries):
    """Opóźnienie publikacja → dostępność w indeksie, osobno dla pierwszych wersji wpisów.

    Wpisy wykryte przy pierwszym w historii pobraniu (zaległość) nie mówią nic o opóźnieniu
    importu, więc zwracamy je osobno."""
    if not entries:
        return {"count": 0}
    first_fetch = min(row["first_fetched_at"] for row in entries)
    fresh = [row for row in entries if row["version"] == 1 and row["first_fetched_at"] != first_fetch]
    values = sorted((datetime.fromisoformat(row["indexed_at"]) - datetime.fromisoformat(row["published_at"]))
                    .total_seconds() for row in fresh)
    if not values:
        return {"count": 0, "backlog": len(entries)}
    return {"count": len(values), "median_s": round(values[len(values) // 2]), "max_s": round(values[-1]),
            "backlog": len(entries) - len(fresh)}
