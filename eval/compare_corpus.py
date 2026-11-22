"""Porównanie odpowiedzi przed i po rozszerzeniu korpusu oraz wariantów wyszukiwania.

    python eval/compare_corpus.py --e5 <katalog z model_quantized.onnx i tokenizer.json> --report eval/wyniki_rozszerzenia

1. Wyszukiwanie (bez modelu): BM25 (SQLite FTS5), E5-small (ONNX, cosinus) i hybryda (RRF, k=60)
   na korpusie v4 i v5 — trafienie na 1. miejscu, wszystkie oczekiwane dokumenty wśród 4,
   liczba kandydatów przy pytaniach bez dowodu, czas wyszukiwania.
2. Pełne sprawdzenie modelem (tryb live, bez pamięci podręcznej) w trzech konfiguracjach:
   v4+BM25, v5+BM25, v5+hybryda. Zapisuje werdykt, cytaty, czas i koszt każdej odpowiedzi.
Pytania i oczekiwane wyniki są w eval/pytania_rozszerzenie.jsonl i nie trafiają do indeksu.
"""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import statistics
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import Settings  # noqa: E402
from app.core.service import Service  # noqa: E402

CORPORA = {"v4": ROOT / "Research/Prawdomir_Korpus_v4.jsonl", "v5": ROOT / "Research/Prawdoskop_Korpus_v5.jsonl"}


class E5:
    def __init__(self, folder):
        import numpy
        import onnxruntime
        from tokenizers import Tokenizer
        self.np = numpy
        self.tokenizer = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self.tokenizer.enable_truncation(512)
        self.session = onnxruntime.InferenceSession(str(folder / "model_quantized.onnx"), providers=["CPUExecutionProvider"])
        self.inputs = {node.name for node in self.session.get_inputs()}

    def encode(self, texts, batch=16):
        np, out = self.np, []
        for start in range(0, len(texts), batch):
            encodings = self.tokenizer.encode_batch(texts[start:start + batch])
            width = max(len(e.ids) for e in encodings)
            ids = np.array([e.ids + [0] * (width - len(e.ids)) for e in encodings], dtype=np.int64)
            mask = np.array([e.attention_mask + [0] * (width - len(e.ids)) for e in encodings], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self.inputs:
                feed["token_type_ids"] = np.zeros_like(ids)
            hidden = self.session.run(None, feed)[0]
            pooled = (hidden * mask[..., None]).sum(1) / mask.sum(1, keepdims=True)
            out.append(pooled / np.linalg.norm(pooled, axis=1, keepdims=True))
        return np.vstack(out)


def document_text(row):
    return " ".join(str(row.get(key) or "") for key in ("title", "excerpt", "scope", "publisher", "published_on"))


class Retrievers:
    def __init__(self, corpus, e5):
        self.corpus, self.e5 = corpus, e5
        self.ids = [key for key, row in corpus.sources.items() if not row.get("guard_suspected")]
        started = perf_counter()
        self.matrix = e5.encode(["passage: " + document_text(corpus.sources[key]) for key in self.ids]) if e5 else None
        self.encode_ms = round((perf_counter() - started) * 1000)

    def bm25(self, text, limit=4):
        return self.corpus.search(text)[:limit]

    def dense(self, text, limit=4):
        scores = self.matrix @ self.e5.encode(["query: " + text])[0]
        return [self.corpus.sources[self.ids[i]] for i in scores.argsort()[::-1][:limit]]

    def hybrid(self, text, limit=4, k=60):
        from prawdowid_core import search_sources
        with self.corpus.lock:
            lexical = search_sources(self.corpus.index, self.corpus.sources, text, 8)
        ranked = {}
        for ranking in (lexical, self.dense(text, 8)):
            for position, row in enumerate(ranking, 1):
                ranked[row["id"]] = ranked.get(row["id"], 0) + 1 / (k + position)
        order = sorted(ranked, key=lambda key: -ranked[key])[:limit]
        return [self.corpus.sources[key] for key in order]


def retrieval_metrics(retrievers, cases, name):
    method = getattr(retrievers, name)
    hit1 = hit4 = graded = 0
    abstain_candidates, times = [], []
    for case in cases:
        started = perf_counter()
        found = [row["id"] for row in method(case["input"])]
        times.append((perf_counter() - started) * 1000)
        expected = case["expected"]["source_ids"]
        if expected:
            graded += 1
            hit1 += bool(found) and found[0] in expected
            hit4 += all(source in found for source in expected)
        else:
            abstain_candidates.append(len(found))
    return {"graded": graded, "hit_at_1": hit1, "all_in_top4": hit4,
            "abstain_cases": len(abstain_candidates), "abstain_with_candidates": sum(n > 0 for n in abstain_candidates),
            "median_ms": round(statistics.median(times), 3)}


def end_to_end(settings, corpus_name, retriever_name, cases, e5):
    rows = []
    with TemporaryDirectory(prefix="prawdoskop-cmp-") as folder:
        service = Service(replace(settings, data_dir=Path(folder), corpus=CORPORA[corpus_name]))
        try:
            if retriever_name == "hybrid":
                retrievers = Retrievers(service.corpus, e5)
                original = service.corpus.search

                def search(text, url=None, pinned=None):
                    if url or pinned:
                        return original(text, url, pinned)
                    return retrievers.hybrid(text)
                service.corpus.search = search
            for case in cases:
                result = service.run(case["input"], channel="api", use_cache=False, register=False)
                item = result.items[0] if result.items else None
                evidence = [row for it in result.items for row in it.evidence]
                expected = case["expected"]
                rows.append({
                    "id": case["id"], "group": case.get("group"), "input": case["input"],
                    "expected_label": expected.get("label"), "status": result.status,
                    "label": item.label if item else None, "kind": item.kind if item else None,
                    "answer": item.answer if item else None,
                    "reason": item.reason if item else result.message,
                    "missing_evidence": item.missing_evidence if item else None,
                    "cited": [row.source_id for row in evidence],
                    "quotes": [{"source_id": row.source_id, "stance": row.stance, "quote": row.quote or row.published_on}
                               for row in evidence],
                    "expected_cited": bool(set(expected["source_ids"]) & {row.source_id for row in evidence}),
                    "elapsed_ms": result.meta.elapsed_ms, "cost_usd": result.meta.estimated_cost_usd,
                })
        finally:
            service.corpus.close()
    return rows


def summarize(rows):
    graded = [r for r in rows if r["expected_label"]]
    with_sources = [r for r in rows if r["expected_label"] not in {None, "insufficient_evidence"}]
    abstain = [r for r in rows if r["expected_label"] == "insufficient_evidence"]
    costs = [r["cost_usd"] for r in rows if r["cost_usd"] is not None]
    return {
        "cases": len(rows), "label_correct": sum(r["label"] == r["expected_label"] for r in graded), "label_graded": len(graded),
        "expected_source_cited": sum(r["expected_cited"] for r in with_sources), "expected_source_cases": len(with_sources),
        "correct_abstention": sum(r["label"] == "insufficient_evidence" for r in abstain), "abstention_cases": len(abstain),
        "wrong_verdict_on_abstention": sum(r["label"] in {"confirmed", "false", "misleading"} for r in abstain),
        "technical_errors": sum(r["status"] == "technical_error" for r in rows),
        "median_ms": statistics.median(r["elapsed_ms"] for r in rows),
        "p95_ms": sorted(r["elapsed_ms"] for r in rows)[max(0, (95 * len(rows) + 99) // 100 - 1)],
        "cost_usd": round(sum(costs), 6), "cost_per_1000_usd": round(1000 * sum(costs) / len(costs), 3) if costs else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", type=Path, default=ROOT / "eval/pytania_rozszerzenie.jsonl")
    parser.add_argument("--e5", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--skip-live", action="store_true")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    cases = [json.loads(line) for line in args.cases.read_text(encoding="utf-8").splitlines() if line.strip()]
    settings = Settings()
    e5 = E5(args.e5)
    output = {"retrieval": {}, "end_to_end": {}, "conditions": {
        "model": settings.model, "cases": len(cases), "e5": "Xenova/multilingual-e5-small (ONNX int8, rev 761b726)",
        "hybrid": "RRF k=60 z 8 kandydatów BM25 i 8 E5, zwraca 4", "machine": "lokalny CPU (Windows 10), 1 wątek zapytań",
    }}
    for corpus_name, path in CORPORA.items():
        with TemporaryDirectory() as folder:
            service = Service(replace(settings, data_dir=Path(folder), corpus=path, evaluator="fake"))
            retrievers = Retrievers(service.corpus, e5)
            output["retrieval"][corpus_name] = {"documents": len(service.corpus.sources), "e5_encode_ms": retrievers.encode_ms,
                                                **{name: retrieval_metrics(retrievers, cases, name) for name in ("bm25", "dense", "hybrid")}}
            service.corpus.close()
        print(corpus_name, json.dumps(output["retrieval"][corpus_name], ensure_ascii=False))
    if not args.skip_live:
        if settings.evaluator != "live" or not settings.key:
            parser.error("Pełne sprawdzenie wymaga trybu live i klucza.")
        details = {}
        for corpus_name, retriever_name in (("v4", "bm25"), ("v5", "bm25"), ("v5", "hybrid")):
            key = f"{corpus_name}+{retriever_name}"
            details[key] = end_to_end(settings, corpus_name, retriever_name, cases, e5)
            output["end_to_end"][key] = summarize(details[key])
            print(key, json.dumps(output["end_to_end"][key], ensure_ascii=False))
        output["details"] = details
    args.report.with_suffix(".json").write_text(json.dumps(output, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
