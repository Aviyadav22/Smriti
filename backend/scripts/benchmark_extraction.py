#!/usr/bin/env python3
"""Benchmark extraction quality against a gold-standard dataset.

Runs the metadata extraction pipeline on a set of manually verified cases
and computes per-field precision and recall.

Usage:
    python scripts/benchmark_extraction.py --gold-dir data/gold_standard/
    python scripts/benchmark_extraction.py --gold-dir data/gold_standard/ --fields title,citation,year
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.ingestion.metadata import CaseMetadata, extract_metadata_llm
from app.core.ingestion.pdf import extract_and_score

logger = logging.getLogger("benchmark")

# Fields to evaluate — must exist on CaseMetadata
_SCALAR_FIELDS = [
    "title",
    "citation",
    "court",
    "year",
    "decision_date",
    "case_type",
    "jurisdiction",
    "bench_type",
    "petitioner",
    "respondent",
    "author_judge",
    "disposal_nature",
    "case_number",
    "outcome_summary",
    "coram_size",
    "opinion_type",
    "is_reportable",
    "is_pil",
]

_LIST_FIELDS = [
    "judge",
    "acts_cited",
    "cases_cited",
    "keywords",
]


@dataclass
class FieldMetrics:
    """Precision/recall metrics for a single field."""

    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0

    @property
    def precision(self) -> float:
        denom = self.true_positive + self.false_positive
        return self.true_positive / denom if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positive + self.false_negative
        return self.true_positive / denom if denom > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


@dataclass
class BenchmarkResults:
    """Aggregate benchmark results across all cases."""

    total_cases: int = 0
    field_metrics: dict[str, FieldMetrics] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _normalize(value: str | None) -> str:
    """Normalize a string value for comparison."""
    if value is None:
        return ""
    return " ".join(str(value).lower().strip().split())


def _compare_scalar(gold: object, predicted: object) -> tuple[bool, bool]:
    """Compare scalar values. Returns (has_gold, matches)."""
    if gold is None:
        return False, predicted is None
    if predicted is None:
        return True, False
    # Numeric comparison
    if isinstance(gold, int | float) and isinstance(predicted, int | float):
        return True, gold == predicted
    # Boolean
    if isinstance(gold, bool):
        return True, gold == predicted
    # String: normalize whitespace and case
    return True, _normalize(str(gold)) == _normalize(str(predicted))


def _compare_list(gold: list | None, predicted: list | None) -> tuple[int, int, int]:
    """Compare list fields. Returns (TP, FP, FN)."""
    gold_set = {_normalize(str(v)) for v in (gold or []) if v}
    pred_set = {_normalize(str(v)) for v in (predicted or []) if v}

    if not gold_set:
        return 0, len(pred_set), 0

    tp = len(gold_set & pred_set)
    fp = len(pred_set - gold_set)
    fn = len(gold_set - pred_set)
    return tp, fp, fn


def evaluate_case(
    gold: dict,
    predicted: CaseMetadata,
    results: BenchmarkResults,
    fields_filter: set[str] | None = None,
) -> None:
    """Evaluate a single case against gold standard."""
    for f in _SCALAR_FIELDS:
        if fields_filter and f not in fields_filter:
            continue
        if f not in results.field_metrics:
            results.field_metrics[f] = FieldMetrics()

        gold_val = gold.get(f)
        pred_val = getattr(predicted, f, None)
        has_gold, matches = _compare_scalar(gold_val, pred_val)

        if has_gold:
            if matches:
                results.field_metrics[f].true_positive += 1
            else:
                results.field_metrics[f].false_negative += 1
        elif pred_val is not None:
            results.field_metrics[f].false_positive += 1

    for f in _LIST_FIELDS:
        if fields_filter and f not in fields_filter:
            continue
        if f not in results.field_metrics:
            results.field_metrics[f] = FieldMetrics()

        gold_val = gold.get(f)
        pred_val = getattr(predicted, f, None)
        tp, fp, fn = _compare_list(gold_val, pred_val)
        results.field_metrics[f].true_positive += tp
        results.field_metrics[f].false_positive += fp
        results.field_metrics[f].false_negative += fn


async def run_benchmark(
    gold_dir: Path,
    llm: object,
    fields_filter: set[str] | None = None,
) -> BenchmarkResults:
    """Run benchmark on all gold-standard cases in the directory.

    Each case is a JSON file with:
    - "pdf_path": path to the PDF (relative to gold_dir)
    - "metadata": dict of ground-truth metadata fields

    If "pdf_path" is not present, "text" can be provided directly.
    """
    results = BenchmarkResults()

    gold_files = sorted(gold_dir.glob("*.json"))
    if not gold_files:
        logger.error("No gold standard files found in %s", gold_dir)
        return results

    logger.info("Found %d gold standard cases", len(gold_files))

    for gold_file in gold_files:
        try:
            with open(gold_file) as f:
                gold_data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            results.errors.append(f"Failed to load {gold_file.name}: {exc}")
            continue

        gold_meta = gold_data.get("metadata", {})
        case_text = gold_data.get("text")

        # Extract text from PDF if path provided
        if not case_text and gold_data.get("pdf_path"):
            pdf_path = gold_dir / gold_data["pdf_path"]
            if pdf_path.exists():
                quality = await extract_and_score(str(pdf_path))
                case_text = quality.text
            else:
                results.errors.append(f"PDF not found: {pdf_path}")
                continue

        if not case_text:
            results.errors.append(f"No text for {gold_file.name}")
            continue

        # Run LLM extraction
        try:
            predicted = await extract_metadata_llm(case_text, llm)
        except Exception as exc:
            results.errors.append(f"Extraction failed for {gold_file.name}: {exc}")
            continue

        evaluate_case(gold_meta, predicted, results, fields_filter)
        results.total_cases += 1
        logger.info("Evaluated %s (%d/%d)", gold_file.name, results.total_cases, len(gold_files))

    return results


def print_results(results: BenchmarkResults) -> None:
    """Print benchmark results in a formatted table."""

    for field_name in sorted(results.field_metrics.keys()):
        results.field_metrics[field_name]

    # Macro averages
    all_metrics = list(results.field_metrics.values())
    if all_metrics:
        sum(m.precision for m in all_metrics) / len(all_metrics)
        sum(m.recall for m in all_metrics) / len(all_metrics)
        sum(m.f1 for m in all_metrics) / len(all_metrics)

    if results.errors:
        for _err in results.errors:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark metadata extraction")
    parser.add_argument(
        "--gold-dir",
        type=Path,
        default=Path("data/gold_standard"),
        help="Directory with gold standard JSON files",
    )
    parser.add_argument(
        "--fields",
        type=str,
        default=None,
        help="Comma-separated list of fields to evaluate (default: all)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    fields_filter = None
    if args.fields:
        fields_filter = set(args.fields.split(","))

    if not args.gold_dir.exists():
        sys.exit(1)

    # Create a mock LLM for dry-run or use real one
    try:
        from app.core.dependencies import create_llm_provider

        llm = create_llm_provider()
    except Exception:
        sys.exit(1)

    results = asyncio.run(run_benchmark(args.gold_dir, llm, fields_filter))
    print_results(results)


if __name__ == "__main__":
    main()
