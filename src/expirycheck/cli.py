"""CLI for checking independent observation JSON."""
import argparse
import json
from pathlib import Path
import sys

from . import ContractError, evaluate


def main() -> int:
    parser = argparse.ArgumentParser(description="Check declared expiry facts against measured observations")
    parser.add_argument("observations", type=Path)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--json", action="store_true", help="Print the full machine-readable report")
    args = parser.parse_args()
    try:
        report = evaluate(args.corpus.read_bytes(), args.observations.read_bytes())
    except (ContractError, OSError) as exc:
        print(f"Cannot check observations: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{report['checked']} cases: {report['passed']} pass, {report['failed']} fail, {report['errors']} errors")
        for row in report["cases"]:
            if row["status"] != "pass":
                details = "; ".join(v["detail"] for v in row["violations"]) or row.get("error", "")
                print(f"{row['status'].upper()} {row['case_id']}: {details}")
    if report["errors"]:
        return 2
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
