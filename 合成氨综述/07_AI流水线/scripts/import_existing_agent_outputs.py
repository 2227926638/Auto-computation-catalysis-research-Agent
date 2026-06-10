from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path


NEW_EVIDENCE_FIELDS = [
    "evidence_id",
    "source_id",
    "doi",
    "section_or_figure",
    "evidence_text",
    "evidence_type",
    "claim_category",
    "claim_summary",
    "mechanistic_target",
    "catalyst_model",
    "reaction_step",
    "confidence",
    "needs_manual_check",
    "used_in_section",
    "notes",
]


SECTION_KEYWORDS = {
    "active_site_debate": ["active site", "B5", "cluster", "interfacial", "Ru-Ov-Ce"],
    "oxygen_vacancy_emsi": ["oxygen vacancy", "Ce3", "Ce4", "electron", "EMSI", "SMSI"],
    "hydrogen_poisoning": ["hydrogen poisoning", "H2", "hydrogen coverage", "reaction order"],
    "computation_microkinetics": ["DFT", "NEB", "microkinetic", "barrier", "N2 dissociation", "NHx"],
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def literature_by_source(path: Path) -> dict[str, dict[str, str]]:
    rows = read_csv(path)
    return {row.get("source_id", ""): row for row in rows if row.get("source_id")}


def infer_section(text: str) -> str:
    low = text.lower()
    for section, keywords in SECTION_KEYWORDS.items():
        if any(keyword.lower() in low for keyword in keywords):
            return section
    return ""


def convert_evidence(agent_output: Path, out_path: Path) -> None:
    literature_path = agent_output / "literature" / "literature_matrix.csv"
    evidence_path = agent_output / "literature" / "evidence_table.csv"
    literature = literature_by_source(literature_path)
    evidence_rows = read_csv(evidence_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=NEW_EVIDENCE_FIELDS)
        writer.writeheader()
        for row in evidence_rows:
            source_id = row.get("source_id", "")
            source = literature.get(source_id, {})
            claim = row.get("claim_text", "") or row.get("topic", "")
            excerpt = row.get("supporting_excerpt", "")
            joined = " ".join([claim, row.get("keywords", ""), excerpt])
            writer.writerow(
                {
                    "evidence_id": row.get("evidence_id", ""),
                    "source_id": source_id,
                    "doi": source.get("doi", ""),
                    "section_or_figure": row.get("extracted_from", ""),
                    "evidence_text": excerpt,
                    "evidence_type": row.get("claim_type", ""),
                    "claim_category": row.get("topic", ""),
                    "claim_summary": claim,
                    "mechanistic_target": row.get("keywords", ""),
                    "catalyst_model": source.get("catalyst_family", "") or "Ru-CeO2 / ceria-supported Ru",
                    "reaction_step": "",
                    "confidence": row.get("confidence", ""),
                    "needs_manual_check": row.get("requires_human_check", "true") or "true",
                    "used_in_section": infer_section(joined),
                    "notes": "Converted from existing catalysis_question_agent output; manual verification required.",
                }
            )


def copy_reference_files(agent_output: Path, out_dir: Path) -> None:
    reference_dir = out_dir / "reference_files"
    reference_dir.mkdir(parents=True, exist_ok=True)
    relative_files = [
        "literature/literature_matrix.csv",
        "literature/evidence_table.csv",
        "insight/consensus_list.md",
        "insight/controversy_list.md",
        "insight/open_gap_list.md",
        "question_cards/high_priority_cards.md",
        "review/meta_review.md",
        "metadata/similar_works.csv",
    ]
    for relative in relative_files:
        src = agent_output / relative
        if src.exists():
            safe_name = relative.replace("/", "__").replace("\\", "__")
            shutil.copy2(src, reference_dir / safe_name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import existing catalysis_question_agent output as review starter assets.")
    parser.add_argument("--agent-output", required=True, help="Path to existing Agent output directory.")
    parser.add_argument("--out-dir", required=True, help="Output directory inside the review project.")
    args = parser.parse_args()

    agent_output = Path(args.agent_output)
    out_dir = Path(args.out_dir)
    if not agent_output.exists():
        raise FileNotFoundError(agent_output)

    converted = out_dir / "converted_evidence_table.csv"
    convert_evidence(agent_output, converted)
    copy_reference_files(agent_output, out_dir)

    print(f"Wrote: {converted}")
    print(f"Wrote reference copies under: {out_dir / 'reference_files'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
