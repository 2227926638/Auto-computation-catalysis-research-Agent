from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


DEFAULT_SECTIONS = [
    "introduction",
    "ru_ceo2_rationale",
    "active_site_debate",
    "oxygen_vacancy_emsi",
    "hydrogen_poisoning",
    "computation_microkinetics",
    "ai_evidence_map",
    "outlook",
]


SECTION_HINTS = {
    "active_site_debate": ["active site", "B5", "cluster", "interfacial", "Ru-Ov-Ce"],
    "oxygen_vacancy_emsi": ["oxygen vacancy", "Ce3", "Ce4", "electron", "EMSI", "SMSI"],
    "hydrogen_poisoning": ["hydrogen poisoning", "H2", "hydrogen coverage", "reaction order"],
    "computation_microkinetics": ["DFT", "NEB", "microkinetic", "barrier", "N2 dissociation", "NHx"],
    "ai_evidence_map": ["evidence", "matrix", "claim", "gap", "AI"],
}


def infer_section(row: dict[str, str]) -> str:
    explicit = (row.get("used_in_section") or "").strip()
    if explicit:
        return explicit

    text = " ".join(
        [
            row.get("claim_category", ""),
            row.get("claim_summary", ""),
            row.get("mechanistic_target", ""),
            row.get("evidence_text", ""),
        ]
    ).lower()

    for section, hints in SECTION_HINTS.items():
        if any(hint.lower() in text for hint in hints):
            return section
    return "introduction"


def load_evidence(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_bundle_markdown(rows_by_section: dict[str, list[dict[str, str]]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = ["# Section Evidence Bundles", ""]

    for section in DEFAULT_SECTIONS:
        rows = rows_by_section.get(section, [])
        lines.append(f"## {section}")
        lines.append("")
        if not rows:
            lines.append("- No evidence assigned yet.")
            lines.append("")
            continue

        for row in rows:
            evidence_id = row.get("evidence_id", "")
            source_id = row.get("source_id", "")
            doi = row.get("doi", "")
            evidence_type = row.get("evidence_type", "")
            claim = row.get("claim_summary", "")
            text = (row.get("evidence_text", "") or "").replace("\n", " ").strip()
            if len(text) > 320:
                text = text[:317] + "..."
            lines.append(f"- `{evidence_id}` `{source_id}` `{evidence_type}` DOI: {doi}")
            lines.append(f"  - Claim: {claim}")
            lines.append(f"  - Evidence: {text}")
        lines.append("")

    output.write_text("\n".join(lines), encoding="utf-8")


def write_claim_audit(rows: list[dict[str, str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "evidence_id",
        "source_id",
        "doi",
        "section",
        "evidence_type",
        "confidence",
        "needs_manual_check",
        "audit_issue",
    ]
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            issues = []
            if not row.get("evidence_id"):
                issues.append("missing_evidence_id")
            if not row.get("source_id"):
                issues.append("missing_source_id")
            if not row.get("doi"):
                issues.append("missing_doi")
            if not row.get("evidence_text"):
                issues.append("missing_evidence_text")
            writer.writerow(
                {
                    "evidence_id": row.get("evidence_id", ""),
                    "source_id": row.get("source_id", ""),
                    "doi": row.get("doi", ""),
                    "section": infer_section(row),
                    "evidence_type": row.get("evidence_type", ""),
                    "confidence": row.get("confidence", ""),
                    "needs_manual_check": row.get("needs_manual_check", ""),
                    "audit_issue": ";".join(issues) if issues else "ok",
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build section evidence bundles from evidence_table CSV.")
    parser.add_argument("--evidence", required=True, help="Path to evidence_table CSV.")
    parser.add_argument("--out-dir", required=True, help="Output directory for generated bundles.")
    args = parser.parse_args()

    evidence_path = Path(args.evidence)
    out_dir = Path(args.out_dir)
    rows = load_evidence(evidence_path)

    rows_by_section: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        rows_by_section[infer_section(row)].append(row)

    write_bundle_markdown(rows_by_section, out_dir / "section_evidence_bundles.md")
    write_claim_audit(rows, out_dir / "claim_audit.csv")

    print(f"Loaded evidence rows: {len(rows)}")
    print(f"Wrote: {out_dir / 'section_evidence_bundles.md'}")
    print(f"Wrote: {out_dir / 'claim_audit.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
