"""CLI: ``python -m app.evals --suite golden --limit 20`` (exit 1 on failure gates)."""
from __future__ import annotations

import argparse
import json
import sys

from ..db import SessionLocal
from .suites import run_suite


def main() -> int:
    ap = argparse.ArgumentParser(description="Run MetaLens agent evaluations")
    ap.add_argument("--suite", choices=["golden", "decisions"], default="golden")
    ap.add_argument("--limit", type=int, default=20, help="golden cases (0 = all)")
    ap.add_argument(
        "--min-description-similarity",
        type=float,
        default=None,
        help="fail (exit 1) if rag/description_similarity is below this, for CI gates",
    )
    args = ap.parse_args()

    with SessionLocal() as db:
        result = run_suite(db, args.suite, limit=args.limit or None)
    print(json.dumps({"suite": result.suite, "run_url": result.run_url, "metrics": result.metrics}, indent=2))

    gate = args.min_description_similarity
    if gate is not None and result.metrics.get("rag/description_similarity", 0.0) < gate:
        print(f"FAILED gate: rag/description_similarity < {gate}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
