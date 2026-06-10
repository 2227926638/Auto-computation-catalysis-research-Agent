from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from .models import ComputabilityLabel, EvidenceItem, MethodEvidence, ResearchQuestionCard
from .research_pipeline_models import (
    ImportedQuestionRecord,
    LiteratureRecord,
    QuestionImportReport,
    RunManifest,
    SourceFileRecord,
    utc_now,
)


class QuestionAgentAdapter:
    """Import frontend question-agent artifacts into self-built pipeline objects."""

    REQUIRED_FILES = {
        "run_summary": "run_summary.json",
        "question_cards": "question_cards/all_question_cards.json",
        "evidence_table": "literature/evidence_table.csv",
        "method_evidence": "literature/method_evidence.csv",
        "literature_matrix": "literature/literature_matrix.csv",
        "gate_audit_report": "review/gate_audit_report.md",
        "ranking_table": "review/ranking_table.csv",
    }

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)

    def import_run(self, project_id: str) -> tuple[
        RunManifest,
        list[ResearchQuestionCard],
        list[ImportedQuestionRecord],
        list[EvidenceItem],
        list[MethodEvidence],
        list[LiteratureRecord],
        QuestionImportReport,
    ]:
        source_files = self._source_files()
        source_hashes = {item.role: item.sha256 for item in source_files if item.sha256}
        run_summary = self._read_json("run_summary")
        frontend_run_id = run_summary.get("run_id")
        import_id = f"QIMPORT-{uuid4().hex[:12]}"
        manifest = RunManifest(
            import_id=import_id,
            project_id=project_id,
            frontend_run_id=frontend_run_id,
            frontend_output_dir=str(self.output_dir),
            imported_at=utc_now(),
            source_files=source_files,
            source_hashes=source_hashes,
        )

        cards = self._read_cards()
        evidence = self._read_evidence()
        method_evidence = self._read_method_evidence()
        literature = self._read_literature(project_id, source_hashes)
        ranking = self._read_ranking()
        imported_questions = [
            self._imported_question(project_id, card, ranking.get(card.question_id, {}), source_hashes)
            for card in cards
        ]
        warnings = [
            f"Missing frontend artifact: {item.role} -> {item.path}"
            for item in source_files
            if not item.exists
        ]
        report = QuestionImportReport(
            import_id=import_id,
            project_id=project_id,
            frontend_run_id=frontend_run_id,
            imported_question_count=len(cards),
            candidate_for_protocol_planning_count=sum(
                1 for item in imported_questions if item.candidate_for_protocol_planning
            ),
            imported_evidence_count=len(evidence),
            imported_method_evidence_count=len(method_evidence),
            imported_literature_count=len(literature),
            source_files=source_files,
            warnings=warnings,
        )
        return manifest, cards, imported_questions, evidence, method_evidence, literature, report

    def _source_files(self) -> list[SourceFileRecord]:
        return [
            self._source_file(role, self.output_dir / relative)
            for role, relative in self.REQUIRED_FILES.items()
        ]

    def _source_file(self, role: str, path: Path) -> SourceFileRecord:
        exists = path.exists()
        return SourceFileRecord(
            role=role,
            path=str(path),
            exists=exists,
            sha256=_sha256(path) if exists and path.is_file() else None,
            size_bytes=path.stat().st_size if exists and path.is_file() else None,
        )

    def _read_json(self, role: str) -> dict:
        path = self.output_dir / self.REQUIRED_FILES[role]
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _read_cards(self) -> list[ResearchQuestionCard]:
        data = self._read_json("question_cards")
        return [ResearchQuestionCard.model_validate(row) for row in data]

    def _read_evidence(self) -> list[EvidenceItem]:
        rows = [
            _coerce_row(
                row,
                list_fields={"keywords"},
                none_fields={
                    "source_doi",
                    "source_title",
                    "source_journal_or_source",
                    "source_year",
                    "source_location",
                },
            )
            for row in self._read_csv("evidence_table")
        ]
        return [EvidenceItem.model_validate(row) for row in rows]

    def _read_method_evidence(self) -> list[MethodEvidence]:
        rows = [
            _coerce_row(
                row,
                list_fields={"protocol_hints", "software_hints", "parameter_hints", "reference_state_hints"},
                none_fields={"linked_evidence_id", "source_location"},
            )
            for row in self._read_csv("method_evidence")
        ]
        return [MethodEvidence.model_validate(row) for row in rows]

    def _read_literature(self, project_id: str, source_hashes: dict[str, str]) -> list[LiteratureRecord]:
        rows = self._read_csv("literature_matrix")
        records: list[LiteratureRecord] = []
        for idx, row in enumerate(rows, start=1):
            records.append(
                LiteratureRecord(
                    literature_id=f"LIT-{idx:04d}",
                    project_id=project_id,
                    source_id=str(row.get("source_id") or f"SRC-{idx:04d}"),
                    title=str(row.get("title") or ""),
                    doi=_none_if_blank(row.get("doi")),
                    year=_int_or_none(row.get("year")),
                    journal_or_source=_none_if_blank(row.get("journal_or_source")),
                    local_path=_none_if_blank(row.get("local_path")),
                    source_files=[str(self.output_dir / self.REQUIRED_FILES["literature_matrix"])],
                    source_hashes={"literature_matrix": source_hashes.get("literature_matrix", "")},
                    metadata={
                        "quality_flags": row.get("quality_flags"),
                        "source_type": row.get("source_type"),
                        "unchecked_fields": ["doi", "year", "journal_or_source", "source_location"],
                    },
                )
            )
        return records

    def _read_ranking(self) -> dict[str, dict]:
        rows = self._read_csv("ranking_table")
        out: dict[str, dict] = {}
        for row in rows:
            question_id = row.get("question_id")
            if not question_id:
                continue
            parsed = dict(row)
            for key in ("hard_gate", "scores", "review_comments"):
                value = parsed.get(key)
                if isinstance(value, str) and value.strip():
                    try:
                        parsed[key] = json.loads(value)
                    except json.JSONDecodeError:
                        parsed[key] = value
            out[str(question_id)] = parsed
        return out

    def _read_csv(self, role: str) -> list[dict]:
        path = self.output_dir / self.REQUIRED_FILES[role]
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def _imported_question(
        self,
        project_id: str,
        card: ResearchQuestionCard,
        ranking: dict,
        source_hashes: dict[str, str],
    ) -> ImportedQuestionRecord:
        hard_gate = ranking.get("hard_gate") if isinstance(ranking.get("hard_gate"), dict) else {}
        gate_ok = all(
            bool(hard_gate.get(key, False))
            for key in ("G1_literature_evidence", "G2_computational_verifiability", "G3_protocol_registered")
        )
        computable = card.preliminary_computability in {ComputabilityLabel.C2, ComputabilityLabel.C3}
        block_reasons: list[str] = []
        if not computable:
            block_reasons.append(f"preliminary_computability_is_{card.preliminary_computability}")
        for key in ("G1_literature_evidence", "G2_computational_verifiability", "G3_protocol_registered"):
            if hard_gate and not hard_gate.get(key, False):
                block_reasons.append(f"frontend_{key}_failed")
        if not hard_gate:
            block_reasons.append("frontend_ranking_gate_missing")
        return ImportedQuestionRecord(
            question_id=card.question_id,
            project_id=project_id,
            title=card.title,
            preliminary_computability=card.preliminary_computability.value,
            frontend_decision=str(ranking.get("decision") or card.status.value),
            candidate_for_protocol_planning=computable and gate_ok,
            block_reasons=block_reasons,
            required_protocols=card.required_protocols,
            evidence_ids=card.evidence_ids,
            source_files=[
                str(self.output_dir / self.REQUIRED_FILES["question_cards"]),
                str(self.output_dir / self.REQUIRED_FILES["ranking_table"]),
                str(self.output_dir / self.REQUIRED_FILES["gate_audit_report"]),
            ],
            source_hashes={
                "question_cards": source_hashes.get("question_cards", ""),
                "ranking_table": source_hashes.get("ranking_table", ""),
                "gate_audit_report": source_hashes.get("gate_audit_report", ""),
            },
            metadata={
                "priority_score": card.priority_score,
                "frontend_hard_gate": hard_gate,
                "unchecked_fields": ["doi", "source_location", "recent_duplicate_check"],
            },
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _none_if_blank(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: object) -> int | None:
    text = _none_if_blank(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _coerce_row(
    row: dict,
    *,
    list_fields: set[str],
    none_fields: set[str],
) -> dict:
    out = dict(row)
    for field in list_fields:
        value = out.get(field)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                out[field] = []
            else:
                try:
                    parsed = json.loads(text)
                    out[field] = parsed if isinstance(parsed, list) else [parsed]
                except json.JSONDecodeError:
                    out[field] = [text]
    for field in none_fields:
        if out.get(field) == "":
            out[field] = None
    return out
