from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class GateStatus(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ComputabilityLabel(StrEnum):
    C0 = "C0"
    C1 = "C1"
    C2 = "C2"
    C3 = "C3"


class ProtocolStatus(StrEnum):
    PLANNING_STUB = "planning_stub"
    EXECUTABLE_MVP = "executable_mvp"
    EXECUTABLE_REVIEWED = "executable_reviewed"
    DEPRECATED = "deprecated"


class GateName(StrEnum):
    G1_LITERATURE_EVIDENCE = "G1_literature_evidence"
    G2_COMPUTATIONAL_VERIFIABILITY = "G2_computational_verifiability"
    G3_PROTOCOL = "G3_protocol"


def combine_status(statuses: list[GateStatus]) -> GateStatus:
    if GateStatus.BLOCK in statuses:
        return GateStatus.BLOCK
    if GateStatus.WARN in statuses:
        return GateStatus.WARN
    return GateStatus.PASS


class ImportedFile(StrictModel):
    path: str
    sha256: str
    bytes: int
    required: bool = True


class EvidenceClaim(StrictModel):
    evidence_id: str
    source_id: str | None = None
    claim_type: str = "unknown"
    topic: str = "unknown"
    claim_text: str
    supporting_excerpt: str | None = None
    source_doi: str | None = None
    source_title: str | None = None
    source_journal_or_source: str | None = None
    source_year: int | None = None
    source_location: str | None = None
    confidence: float = 0.0
    requires_human_check: bool = True
    keywords: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class MethodEvidence(StrictModel):
    method_evidence_id: str
    source_id: str | None = None
    linked_evidence_id: str | None = None
    topic: str = "unknown"
    protocol_hints: list[str] = Field(default_factory=list)
    software_hints: list[str] = Field(default_factory=list)
    calculation_type: str = "unknown"
    parameter_hints: list[str] = Field(default_factory=list)
    reference_state_hints: list[str] = Field(default_factory=list)
    excerpt: str
    source_location: str | None = None
    confidence: float = 0.0
    requires_human_check: bool = True
    raw: dict[str, Any] = Field(default_factory=dict)


class ResearchQuestionCardV2(StrictModel):
    question_id: str
    title: str
    reaction: str
    catalyst: str
    question_type: str = "unknown"
    background_consensus_ids: list[str] = Field(default_factory=list)
    controversy_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    unresolved_gap: list[str] = Field(default_factory=list)
    computational_path_hint: list[str] = Field(default_factory=list)
    expected_result_types: list[str] = Field(default_factory=list)
    minimal_publishable_results: list[str] = Field(default_factory=list)
    required_protocols: list[str] = Field(default_factory=list)
    required_reference_states: list[str] = Field(default_factory=list)
    protocol_feasibility: str = "unknown"
    aiida_executability: str = "unknown"
    computational_verifiability_gate: str = "unknown"
    literature_evidence_gate: str = "unknown"
    expected_audit_risks: list[str] = Field(default_factory=list)
    wet_experiment_dependency: str = "unknown"
    preliminary_computability: ComputabilityLabel = ComputabilityLabel.C1
    novelty_risk: str = "unknown"
    calculation_cost: str = "unknown"
    graduation_value: str = "unknown"
    priority_score: float = 0.0
    status: str = "needs_evidence"
    risks: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_run_id: str | None = None
    source_file: str | None = None

    @field_validator("preliminary_computability", mode="before")
    @classmethod
    def normalize_computability(cls, value: Any) -> ComputabilityLabel:
        if isinstance(value, ComputabilityLabel):
            return value
        text = str(value).strip().upper()
        if text in {"C0", "C1", "C2", "C3"}:
            return ComputabilityLabel(text)
        return ComputabilityLabel.C1


class CalcProtocol(StrictModel):
    protocol_id: str
    version: str = "0.1.0"
    status: ProtocolStatus = ProtocolStatus.PLANNING_STUB
    name: str | None = None
    purpose: str
    applicable_systems: list[str] = Field(default_factory=list)
    forbidden_uses: list[str] = Field(default_factory=list)
    supported_software: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    required_reference_states: list[str] = Field(default_factory=list)
    default_parameters: dict[str, Any] = Field(default_factory=dict)
    convergence_criteria: dict[str, Any] = Field(default_factory=dict)
    required_controls: list[str] = Field(default_factory=list)
    audit_rules: list[str] = Field(default_factory=list)
    publication_boundary: str | None = None
    allowed_claim_strength: str = "background_or_planning_only"
    notes: list[str] = Field(default_factory=list)

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: Any) -> ProtocolStatus:
        if isinstance(value, ProtocolStatus):
            return value
        return ProtocolStatus(str(value).strip())


class ProtocolAuditReport(StrictModel):
    protocol_id: str
    status: GateStatus
    findings: list[str] = Field(default_factory=list)
    blocking_findings: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    human_review_required: bool = False
    next_action: str = "none"


class ProtocolBinding(StrictModel):
    question_id: str
    status: GateStatus
    requested_protocol_ids: list[str] = Field(default_factory=list)
    bound_protocol_ids: list[str] = Field(default_factory=list)
    executable_protocol_ids: list[str] = Field(default_factory=list)
    non_executable_protocol_ids: list[str] = Field(default_factory=list)
    missing_protocol_ids: list[str] = Field(default_factory=list)
    required_reference_states: list[str] = Field(default_factory=list)
    reports: list[ProtocolAuditReport] = Field(default_factory=list)
    human_review_required: bool = False
    next_action: str = "none"


class ComputabilityAuditReport(StrictModel):
    question_id: str
    status: GateStatus
    input_label: ComputabilityLabel
    final_label: ComputabilityLabel
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    required_protocols: list[str] = Field(default_factory=list)
    required_reference_states: list[str] = Field(default_factory=list)
    claim_boundary: str
    unanswered_by_computation: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    human_review_required: bool = True
    next_action: str = "none"


class GateAuditRecord(StrictModel):
    gate: GateName
    target_type: str
    target_id: str
    status: GateStatus
    reasons: list[str] = Field(default_factory=list)
    evidence_links: list[str] = Field(default_factory=list)
    human_review_required: bool = False
    next_action: str = "none"
    created_at: str = Field(default_factory=utc_now_iso)


class P0AuditSummary(StrictModel):
    question_id: str
    overall_status: GateStatus
    candidate_for_next_stage: bool
    gates: list[GateAuditRecord] = Field(default_factory=list)
    computability_report: ComputabilityAuditReport
    protocol_binding: ProtocolBinding
    created_at: str = Field(default_factory=utc_now_iso)
