from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClaimType(StrEnum):
    CONSENSUS = "consensus"
    CONTROVERSY = "controversy"
    GAP = "gap"
    METHOD = "method"
    VALUE = "value"


class ComputabilityLabel(StrEnum):
    C0 = "C0"
    C1 = "C1"
    C2 = "C2"
    C3 = "C3"


class ReviewDecision(StrEnum):
    RECOMMEND = "recommend"
    RESERVE = "reserve"
    ARCHIVE = "archive"
    NEEDS_EVIDENCE = "needs_evidence"


class ProjectScope(StrictModel):
    project_id: str = "default_project"
    reaction: str
    catalyst_family: str
    focus_keywords: list[str] = Field(default_factory=list)
    start_year: int | None = None
    end_year: int | None = None
    graduation_target: str | None = None


class SourceRecord(StrictModel):
    source_id: str
    source_type: str = "local_note"
    doi: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)
    journal_or_source: str | None = None
    year: int | None = None
    url: str | None = None
    local_path: str | None = None
    abstract: str | None = None
    keywords: list[str] = Field(default_factory=list)
    relevance_score: float = 0.0
    quality_flags: dict[str, bool] = Field(default_factory=dict)
    raw_text: str | None = None


class EvidenceItem(StrictModel):
    evidence_id: str
    source_id: str
    claim_type: ClaimType
    topic: str
    claim_text: str
    supporting_excerpt: str
    extracted_from: str = "local_text"
    source_doi: str | None = None
    source_title: str | None = None
    source_journal_or_source: str | None = None
    source_year: int | None = None
    source_location: str | None = None
    confidence: float = 0.5
    requires_human_check: bool = True
    keywords: list[str] = Field(default_factory=list)


class MethodEvidence(StrictModel):
    method_evidence_id: str
    source_id: str
    linked_evidence_id: str | None = None
    topic: str
    protocol_hints: list[str] = Field(default_factory=list)
    software_hints: list[str] = Field(default_factory=list)
    calculation_type: str = "unknown"
    parameter_hints: list[str] = Field(default_factory=list)
    reference_state_hints: list[str] = Field(default_factory=list)
    excerpt: str
    source_location: str | None = None
    confidence: float = 0.5
    requires_human_check: bool = True


class ConsensusClaim(StrictModel):
    consensus_id: str
    topic: str
    claim_text: str
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    opposing_evidence_ids: list[str] = Field(default_factory=list)
    evidence_strength: str = "low"
    notes: str | None = None


class ControversyClaim(StrictModel):
    controversy_id: str
    topic: str
    claim_a: str
    claim_b: str | None = None
    supporting_evidence_a: list[str] = Field(default_factory=list)
    supporting_evidence_b: list[str] = Field(default_factory=list)
    why_it_matters: str | None = None


class ResearchQuestionCard(StrictModel):
    question_id: str
    title: str
    reaction: str
    catalyst: str
    question_type: str
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
    status: ReviewDecision = ReviewDecision.NEEDS_EVIDENCE
    risks: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewResult(StrictModel):
    question_id: str
    scores: dict[str, float]
    priority_score: float
    hard_gate: dict[str, bool]
    review_comments: list[str] = Field(default_factory=list)
    decision: ReviewDecision


class MetadataRecord(StrictModel):
    source_id: str
    query_title: str
    extracted_doi: str | None = None
    resolved_doi: str | None = None
    title: str | None = None
    journal: str | None = None
    year: int | None = None
    authors: list[str] = Field(default_factory=list)
    publisher: str | None = None
    source_api: str | None = None
    url: str | None = None
    confidence: float = 0.0
    status: str = "not_queried"
    notes: list[str] = Field(default_factory=list)


class SimilarWorkCandidate(StrictModel):
    question_id: str
    query: str
    title: str
    doi: str | None = None
    year: int | None = None
    journal: str | None = None
    authors: list[str] = Field(default_factory=list)
    url: str | None = None
    source_api: str = "OpenAlex"
    cited_by_count: int | None = None
    relevance_hint: str | None = None
    novelty_risk: str = "needs_human_check"


class SourceCandidate(StrictModel):
    candidate_id: str
    registry_source_id: str
    provider: str
    domain: str
    tier: str = "S"
    source_kind: str = "paper"
    access_mode: str = "metadata_api"
    evidence_level: str = "triage_until_fulltext"
    content_state: str = "metadata_only"
    license_state: str = "unknown"
    title: str
    authors: list[str] = Field(default_factory=list)
    journal_or_source: str | None = None
    publisher: str | None = None
    year: int | None = None
    published_date: str | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    keywords: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)
    cited_by_count: int | None = None
    is_open_access: bool = False
    open_access_url: str | None = None
    pdf_url: str | None = None
    fulltext_routes: list[str] = Field(default_factory=list)
    relevance_score: float = 0.0
    quality_score: float = 0.0
    triage_score: float = 0.0
    triage_decision: str = "unranked"
    needs_fulltext: bool = True
    discovered_at: str | None = None
    notes: list[str] = Field(default_factory=list)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class SourceHarvestResult(StrictModel):
    run_id: str
    project_id: str
    candidate_count: int
    fulltext_queue_count: int
    oa_ready_count: int
    metadata_watch_count: int
    output_dir: str
    created_files: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class InsightClaim(StrictModel):
    claim_id: str
    source_kind: str
    topic: str
    proposition: str
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    opposing_evidence_ids: list[str] = Field(default_factory=list)
    linked_question_ids: list[str] = Field(default_factory=list)
    source_record_ids: list[str] = Field(default_factory=list)
    controversy_status: str = "unresolved"
    novelty_implication: str = "unknown"
    computability_implication: str = "unknown"
    confidence: float = 0.0
    first_seen_run_id: str | None = None
    last_seen_run_id: str | None = None
    first_seen_at: str | None = None
    last_updated_at: str | None = None
    update_count: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)


class InsightDelta(StrictModel):
    claim_id: str
    change_type: str
    source_kind: str
    topic: str
    proposition: str
    summary: str
    previous_support_count: int = 0
    current_support_count: int = 0
    previous_opposing_count: int = 0
    current_opposing_count: int = 0
    added_supporting_evidence_ids: list[str] = Field(default_factory=list)
    added_opposing_evidence_ids: list[str] = Field(default_factory=list)
    linked_question_ids: list[str] = Field(default_factory=list)


class InsightLedgerState(StrictModel):
    version: int = 1
    project_id: str
    generated_at: str | None = None
    updated_at: str | None = None
    claims: list[InsightClaim] = Field(default_factory=list)


class AgentRunResult(StrictModel):
    run_id: str
    project_scope: ProjectScope
    source_count: int
    evidence_count: int
    method_evidence_count: int = 0
    consensus_count: int
    controversy_count: int
    question_count_raw: int
    question_count_final: int
    recommended_count: int
    output_dir: str
    created_files: list[str] = Field(default_factory=list)
    manual_review_required: list[str] = Field(default_factory=list)
    insight_claim_count: int = 0
    insight_delta_count: int = 0
