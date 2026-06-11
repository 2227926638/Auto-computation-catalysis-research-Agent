from __future__ import annotations

import ast
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from research_agent.schemas.core import (
    ComputabilityLabel,
    EvidenceClaim,
    GateStatus,
    ImportedFile,
    MethodEvidence,
    ResearchQuestionCardV2,
)


class QuestionAgentImportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_dir: str
    imported_files: list[ImportedFile] = Field(default_factory=list)
    questions: list[ResearchQuestionCardV2] = Field(default_factory=list)
    evidence: list[EvidenceClaim] = Field(default_factory=list)
    method_evidence: list[MethodEvidence] = Field(default_factory=list)
    candidate_question_ids: list[str] = Field(default_factory=list)
    blocked_or_archived_question_ids: list[str] = Field(default_factory=list)
    manual_review_required: list[str] = Field(default_factory=list)
    status: GateStatus = GateStatus.WARN


class QuestionAgentAdapter:
    """Import outputs from the existing literature/question-discovery agent."""

    REQUIRED_RELATIVE_FILES = {
        "run_summary": "run_summary.json",
        "question_cards": "question_cards/all_question_cards.json",
        "evidence_table": "literature/evidence_table.csv",
    }
    OPTIONAL_RELATIVE_FILES = {
        "method_evidence": "literature/method_evidence.csv",
        "ranking_table": "review/ranking_table.csv",
        "gate_report": "review/gate_audit_report.md",
    }

    def __init__(self, min_evidence_per_candidate: int = 2):
        self.min_evidence_per_candidate = min_evidence_per_candidate

    def import_run(self, output_dir: str | Path) -> QuestionAgentImportResult:
        root = Path(output_dir)
        if not root.exists():
            raise FileNotFoundError(f"Question-agent output directory does not exist: {root}")

        files = self._collect_files(root)
        run_summary = self._read_json(root / self.REQUIRED_RELATIVE_FILES["run_summary"])
        run_id = str(run_summary.get("run_id") or root.name)
        manual_review_required = list(run_summary.get("manual_review_required") or [])

        cards_path = root / self.REQUIRED_RELATIVE_FILES["question_cards"]
        raw_cards = self._read_json(cards_path)
        if not isinstance(raw_cards, list):
            raise ValueError(f"Expected a list of question cards in {cards_path}")

        evidence = self._read_evidence(root / self.REQUIRED_RELATIVE_FILES["evidence_table"])
        method_path = root / self.OPTIONAL_RELATIVE_FILES["method_evidence"]
        method_evidence = self._read_method_evidence(method_path) if method_path.exists() else []

        questions = [
            self._coerce_question_card(item, run_id=run_id, source_file=str(cards_path))
            for item in raw_cards
        ]

        evidence_ids = {item.evidence_id for item in evidence}
        candidate_ids: list[str] = []
        archived_ids: list[str] = []
        for card in questions:
            linked_count = len([evidence_id for evidence_id in card.evidence_ids if evidence_id in evidence_ids])
            if self._is_candidate(card, linked_count):
                candidate_ids.append(card.question_id)
            else:
                archived_ids.append(card.question_id)

        status = GateStatus.PASS if candidate_ids else GateStatus.WARN
        if not method_evidence:
            manual_review_required.append("method_evidence.csv missing or empty; protocol hints need manual review")

        return QuestionAgentImportResult(
            run_id=run_id,
            source_dir=str(root),
            imported_files=files,
            questions=questions,
            evidence=evidence,
            method_evidence=method_evidence,
            candidate_question_ids=candidate_ids,
            blocked_or_archived_question_ids=archived_ids,
            manual_review_required=manual_review_required,
            status=status,
        )

    def _collect_files(self, root: Path) -> list[ImportedFile]:
        collected: list[ImportedFile] = []
        for relative in self.REQUIRED_RELATIVE_FILES.values():
            path = root / relative
            if not path.exists():
                raise FileNotFoundError(f"Required question-agent file is missing: {path}")
            collected.append(self._file_record(path, required=True))
        for relative in self.OPTIONAL_RELATIVE_FILES.values():
            path = root / relative
            if path.exists():
                collected.append(self._file_record(path, required=False))
        return collected

    def _file_record(self, path: Path, required: bool) -> ImportedFile:
        data = path.read_bytes()
        return ImportedFile(
            path=str(path),
            sha256=hashlib.sha256(data).hexdigest(),
            bytes=len(data),
            required=required,
        )

    def _read_json(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def _read_evidence(self, path: Path) -> list[EvidenceClaim]:
        rows = self._read_csv(path)
        evidence: list[EvidenceClaim] = []
        for row in rows:
            evidence.append(
                EvidenceClaim(
                    evidence_id=str(row.get("evidence_id") or ""),
                    source_id=self._none_if_empty(row.get("source_id")),
                    claim_type=str(row.get("claim_type") or "unknown"),
                    topic=str(row.get("topic") or "unknown"),
                    claim_text=str(row.get("claim_text") or ""),
                    supporting_excerpt=self._none_if_empty(row.get("supporting_excerpt")),
                    source_doi=self._none_if_empty(row.get("source_doi")),
                    source_title=self._none_if_empty(row.get("source_title")),
                    source_journal_or_source=self._none_if_empty(row.get("source_journal_or_source")),
                    source_year=self._int_or_none(row.get("source_year")),
                    source_location=self._none_if_empty(row.get("source_location")),
                    confidence=self._float_or_zero(row.get("confidence")),
                    requires_human_check=self._bool(row.get("requires_human_check"), default=True),
                    keywords=self._parse_list(row.get("keywords")),
                    raw=dict(row),
                )
            )
        return evidence

    def _read_method_evidence(self, path: Path) -> list[MethodEvidence]:
        rows = self._read_csv(path)
        evidence: list[MethodEvidence] = []
        for row in rows:
            evidence.append(
                MethodEvidence(
                    method_evidence_id=str(row.get("method_evidence_id") or ""),
                    source_id=self._none_if_empty(row.get("source_id")),
                    linked_evidence_id=self._none_if_empty(row.get("linked_evidence_id")),
                    topic=str(row.get("topic") or "unknown"),
                    protocol_hints=self._parse_list(row.get("protocol_hints")),
                    software_hints=self._parse_list(row.get("software_hints")),
                    calculation_type=str(row.get("calculation_type") or "unknown"),
                    parameter_hints=self._parse_list(row.get("parameter_hints")),
                    reference_state_hints=self._parse_list(row.get("reference_state_hints")),
                    excerpt=str(row.get("excerpt") or ""),
                    source_location=self._none_if_empty(row.get("source_location")),
                    confidence=self._float_or_zero(row.get("confidence")),
                    requires_human_check=self._bool(row.get("requires_human_check"), default=True),
                    raw=dict(row),
                )
            )
        return evidence

    def _read_csv(self, path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def _coerce_question_card(
        self,
        item: dict[str, Any],
        run_id: str,
        source_file: str,
    ) -> ResearchQuestionCardV2:
        payload = dict(item)
        payload["source_run_id"] = run_id
        payload["source_file"] = source_file
        return ResearchQuestionCardV2.model_validate(payload)

    def _is_candidate(self, card: ResearchQuestionCardV2, linked_evidence_count: int) -> bool:
        if card.preliminary_computability not in {ComputabilityLabel.C2, ComputabilityLabel.C3}:
            return False
        if linked_evidence_count < self.min_evidence_per_candidate:
            return False
        if not card.required_protocols:
            return False
        if card.status not in {"recommend", "reserve"}:
            return False
        return True

    def _parse_list(self, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        text = str(value).strip()
        if not text:
            return []
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(text)
            except Exception:
                continue
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        if ";" in text:
            return [item.strip() for item in text.split(";") if item.strip()]
        return [text]

    def _none_if_empty(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _int_or_none(self, value: Any) -> int | None:
        if value is None or str(value).strip() == "":
            return None
        try:
            return int(float(str(value).strip()))
        except ValueError:
            return None

    def _float_or_zero(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _bool(self, value: Any, default: bool) -> bool:
        if value is None or value == "":
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "y"}
