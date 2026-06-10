from __future__ import annotations

import argparse
import csv
from pathlib import Path


REQUIRED_COLUMNS = {
    "literature": [
        "source_id",
        "title",
        "year",
        "journal",
        "doi",
        "topic_tags",
        "catalyst_family",
        "key_claim",
        "review_relevance",
        "priority_level",
    ],
    "evidence": [
        "evidence_id",
        "source_id",
        "doi",
        "evidence_text",
        "evidence_type",
        "claim_category",
        "claim_summary",
        "confidence",
        "needs_manual_check",
        "used_in_section",
    ],
    "claims": [
        "claim_id",
        "claim_type",
        "theme",
        "claim_statement",
        "supporting_evidence_ids",
        "consensus_level",
        "open_gap",
        "priority",
    ],
}


def read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def validate_csv(path: Path, kind: str) -> tuple[bool, list[str]]:
    if kind not in REQUIRED_COLUMNS:
        raise ValueError(f"Unknown CSV kind: {kind}")
    if not path.exists():
        return False, [f"Missing file: {path}"]

    header = read_header(path)
    missing = [column for column in REQUIRED_COLUMNS[kind] if column not in header]
    duplicate = sorted({column for column in header if header.count(column) > 1})

    messages: list[str] = []
    if missing:
        messages.append("Missing required columns: " + ", ".join(missing))
    if duplicate:
        messages.append("Duplicate columns: " + ", ".join(duplicate))
    if not messages:
        messages.append("OK")
    return not missing and not duplicate, messages


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate review CSV headers.")
    parser.add_argument("--kind", choices=sorted(REQUIRED_COLUMNS), required=True)
    parser.add_argument("--path", required=True, help="CSV file to validate.")
    args = parser.parse_args()

    path = Path(args.path)
    ok, messages = validate_csv(path, args.kind)
    print(f"[{args.kind}] {path}")
    for message in messages:
        print(f"- {message}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
