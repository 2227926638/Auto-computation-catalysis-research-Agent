from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .io_utils import model_rows, write_csv, write_json, write_text
from .models import SourceCandidate


class SourceIntakeBuilder:
    """Convert harvested source candidates into workflow-readable intake files."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        intake = (config.get("source_harvest", {}) or {}).get("intake", {}) or {}
        self.max_sources = int(intake.get("max_sources", 24))
        self.min_score = float(intake.get("min_triage_score", 0.25))
        self.allowed_decisions = set(
            intake.get(
                "decisions",
                ["oa_fulltext_ready", "fulltext_queue", "metadata_watch"],
            )
            or []
        )
        self.include_metadata_watch = bool(intake.get("include_metadata_watch", True))

    def build(self, candidates: list[SourceCandidate], out_dir: str | Path) -> tuple[Path, list[Path]]:
        base = Path(out_dir)
        stub_dir = base / "metadata_evidence_stubs"
        selected = self._select(candidates)
        oa_ready = [item for item in candidates if item.triage_decision == "oa_fulltext_ready"]
        fulltext_queue = [item for item in candidates if item.triage_decision == "fulltext_queue"]
        watch = [item for item in candidates if item.triage_decision == "metadata_watch"]

        created: list[Path] = []
        for idx, candidate in enumerate(selected, start=1):
            created.append(write_text(stub_dir / f"{idx:03d}_{self._slug(candidate.title)}.md", self._stub_md(candidate)))

        created.append(write_csv(base / "selected_metadata_sources.csv", model_rows(selected)))
        created.append(write_csv(base / "oa_fulltext_queue.csv", model_rows(oa_ready)))
        created.append(write_csv(base / "fulltext_acquisition_queue.csv", model_rows(fulltext_queue)))
        created.append(write_csv(base / "metadata_watch_queue.csv", model_rows(watch)))
        created.append(
            write_json(
                base / "intake_manifest.json",
                {
                    "selected_count": len(selected),
                    "oa_fulltext_ready": len(oa_ready),
                    "fulltext_queue": len(fulltext_queue),
                    "metadata_watch": len(watch),
                    "stub_dir": str(stub_dir.resolve()),
                    "note": "Metadata stubs are abstract-level signals. Full manuscript evidence still requires OA PDF, local PDF, or licensed TDM/API access.",
                },
            )
        )
        return stub_dir, created

    def _select(self, candidates: list[SourceCandidate]) -> list[SourceCandidate]:
        selected: list[SourceCandidate] = []
        for candidate in sorted(candidates, key=lambda item: item.triage_score, reverse=True):
            if candidate.triage_score < self.min_score:
                continue
            if candidate.triage_decision not in self.allowed_decisions:
                continue
            if candidate.triage_decision == "metadata_watch" and not self.include_metadata_watch:
                continue
            selected.append(candidate)
            if len(selected) >= self.max_sources:
                break
        return selected

    def _stub_md(self, candidate: SourceCandidate) -> str:
        authors = "; ".join(candidate.authors[:8])
        matched = ", ".join(candidate.matched_terms[:12])
        routes = ", ".join(candidate.fulltext_routes[:8])
        lines = [
            f"# {candidate.title}",
            "",
            "## Source Metadata",
            "",
            f"- Candidate ID: `{candidate.candidate_id}`",
            f"- Provider: `{candidate.provider}`",
            f"- Registry source: `{candidate.registry_source_id}`",
            f"- Domain: `{candidate.domain}`",
            f"- Tier: `{candidate.tier}`",
            f"- Triage decision: `{candidate.triage_decision}`",
            f"- Triage score: `{candidate.triage_score}`",
            f"- Relevance score: `{candidate.relevance_score}`",
            f"- Evidence level: `{candidate.evidence_level}`",
            f"- Content state: `{candidate.content_state}`",
            f"- License state: `{candidate.license_state}`",
            f"- DOI: `{candidate.doi or ''}`",
            f"- URL: {candidate.url or ''}",
            f"- Open access URL: {candidate.open_access_url or ''}",
            f"- PDF URL: {candidate.pdf_url or ''}",
            f"- Year: {candidate.year or ''}",
            f"- Journal/source: {candidate.journal_or_source or ''}",
            f"- Authors: {authors}",
            f"- Matched terms: {matched}",
            f"- Fulltext routes: {routes}",
            "",
            "## Abstract-Level Signal",
            "",
        ]
        if candidate.abstract:
            lines.append(candidate.abstract)
        else:
            lines.append("No abstract was available from the metadata API.")
        lines.extend(
            [
                "",
                "## Evidence Use Policy",
                "",
                (
                    "This file is generated from metadata/abstract-level harvesting. Use it for source triage, "
                    "novelty watch, and question seeding. Do not treat it as full-paper evidence until the full text "
                    "is available through an open PDF, local PDF inbox, or licensed TDM/API route."
                ),
                "",
            ]
        )
        return "\n".join(lines)

    def _slug(self, value: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
        return (clean[:72] or "source").strip("-")
