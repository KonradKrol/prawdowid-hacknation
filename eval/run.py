"""Run held-out references with a live evaluator and report automatic metrics."""

import argparse
from collections import Counter
from dataclasses import replace
import csv
import json
from pathlib import Path
import statistics
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.core.service import Service

LABELS = {"potwierdzone": "confirmed", "fałszywe": "false", "wprowadzające w błąd": "misleading",
          "brak wystarczających dowodów": "insufficient_evidence", "nie podlega weryfikacji": "not_verifiable"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("Research/Prawdowid_Proby_Start.jsonl"))
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    settings = Settings()
    if settings.evaluator != "live" or not settings.key:
        parser.error("Ewaluacja wymaga trybu live i klucza modelu.")
    report = args.report.with_suffix(".json")
    review = args.report.with_suffix(".csv")
    markdown = args.report.with_suffix(".md")
    if any(path.exists() for path in (report, review, markdown)):
        parser.error("Wybierz nową ścieżkę raportu.")
    cases = [json.loads(line) for line in args.cases.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if not cases:
        parser.error("Zestaw prób jest pusty.")
    counts = Counter()
    gold, predicted, correct = Counter(), Counter(), Counter()
    elapsed, costs, rows = [], [], []
    version = None
    with TemporaryDirectory(prefix="prawdowid-eval-") as folder:
        service = Service(replace(settings, data_dir=Path(folder)))
        try:
            for case in cases:
                result = service.run(case["input"], channel="api", use_cache=False)
                version = result.meta
                elapsed.append(result.meta.elapsed_ms)
                costs.append(result.meta.estimated_cost_usd)
                counts["technical_errors"] += result.status == "technical_error"
                expected = case["expected"]
                if expected["kind"] == "verdict":
                    target = LABELS.get(expected["label"], expected["label"])
                    actual = result.items[0].label if result.items else None
                    gold[target] += 1
                    if actual:
                        predicted[actual] += 1
                        correct[actual] += actual == target
                    counts["expected_abstention"] += target == "insufficient_evidence"
                    counts["correct_abstention"] += target == actual == "insufficient_evidence"
                elif expected["kind"] == "insufficient_evidence":
                    counts["expected_abstention"] += 1
                    counts["correct_abstention"] += any(i.label == "insufficient_evidence" for i in result.items)
                for item in result.items:
                    if item.answer is not None or item.label in {"confirmed", "false", "misleading"}:
                        counts["factual_items"] += 1
                        counts["factual_items_cited"] += bool(item.evidence)
                    for source in item.evidence:
                        rows.append([case["id"], item.claim, source.source_id, source.url,
                                     source.quote or source.published_on, ""])
        finally:
            service.corpus.close()
    scores = {label: round(2 * correct[label] / (gold[label] + predicted[label]), 4)
              for label in gold.keys() | predicted.keys()}
    output = {
        "cases": len(cases), "corpus_version": version.corpus_version, "model": version.model,
        "prompt_version": version.prompt_version, "graded_verdicts": sum(gold.values()),
        "labels_f1": scores, "macro_f1": statistics.mean(scores.values()) if scores else None,
        "median_ms": statistics.median(elapsed), "p95_ms": sorted(elapsed)[(95 * len(elapsed) + 99) // 100 - 1],
        "cost_usd_estimate": round(sum(costs), 8) if all(value is not None for value in costs) else None,
        "cost_known_cases": sum(value is not None for value in costs),
        "citation_correctness": "manual_review", **counts,
    }
    output["citation_coverage"] = (
        counts["factual_items_cited"] / counts["factual_items"] if counts["factual_items"] else None
    )
    output["abstention_rate"] = (
        counts["correct_abstention"] / counts["expected_abstention"] if counts["expected_abstention"] else None
    )
    with report.open("x", encoding="utf-8") as stream:
        json.dump(output, stream, ensure_ascii=False, indent=2)
    with review.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("case", "claim", "source_id", "url", "evidence", "correct_0_or_1"))
        writer.writerows([("'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value)
                          for value in row] for row in rows)
    with markdown.open("x", encoding="utf-8") as stream:
        stream.write("# Wyniki ewaluacji\n\n")
        for field, value in output.items():
            stream.write(f"- **{field}** — `{value}`\n")
    print(f"Zapisano {report}, {review} i {markdown}.")


if __name__ == "__main__":
    main()
