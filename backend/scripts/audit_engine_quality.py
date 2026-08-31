"""Run the deterministic engine-quality audit and optionally update its bundled report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.quality.audit import REPORT_PATH, run_quality_audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="update the bundled JSON report")
    args = parser.parse_args()
    report = run_quality_audit()
    payload = report.model_dump_json(indent=2)
    print(payload)
    if args.write:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(f"{payload}\n", encoding="utf-8")
    if not report.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
