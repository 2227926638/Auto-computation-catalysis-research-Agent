from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import Field

from .models import StrictModel


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class GateStatus(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"


class TaskStatus(StrEnum):
    PLANNED = "planned"
    SUBMITTED = "submitted"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"
    SIMULATED = "simulated"


class ClaimLevel(StrEnum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


class ProjectRecord(StrictModel):
    project_id: str
    title: str
    reaction: str
    catalyst_family: str
    graduation_target: str | None = None
    aiida_profile: str | None = None
    status: str = "planning"
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class SourceFileRecord(StrictModel):
    role: str
    path: str
    exists: bool
    sha256: str | None = None
    size_bytes: int | None = None


class RunManifest(StrictModel):
    import_id: str
    project_id: str
    frontend_run_id: str | None = None
    frontend_output_dir: str
    imported_at: str = Field(default_factory=utc_now)
    source_files: list[SourceFileRecord] = Field(default_factory=list)
    source_hashes: dict[str, str] = Field(default_factory=dict)
    status: str = "imported"
    audit_status: str = "unchecked_frontend_metadata"
    human_review_required: bool = True


class LiteratureRecord(StrictModel):
    literature_id: str
    project_id: str
    source_id: str
    title: str
    doi: str | None = None
    year: int | None = None
    journal_or_source: str | None = None
    local_path: str | None = None
    source_files: list[str] = Field(default_factory=list)
    source_hashes: dict[str, str] = Field(default_factory=dict)
    status: str = "imported"
    audit_status: str = "unchecked"
    human_review_required: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImportedQuestionRecord(StrictModel):
    question_id: str
    project_id: str
    title: str
    preliminary_computability: str
    frontend_decision: str
    candidate_for_protocol_planning: bool
    block_reasons: list[str] = Field(default_factory=list)
    required_protocols: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)
    source_hashes: dict[str, str] = Field(default_factory=dict)
    status: str = "imported"
    audit_status: str = "frontend_gate_imported"
    human_review_required: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuestionImportReport(StrictModel):
    import_id: str
    project_id: str
    frontend_run_id: str | None = None
    imported_question_count: int
    candidate_for_protocol_planning_count: int
    imported_evidence_count: int
    imported_method_evidence_count: int
    imported_literature_count: int
    source_files: list[SourceFileRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    status: str = "imported"
    audit_status: str = "needs_manual_metadata_check"
    human_review_required: bool = True


class CalcProtocol(StrictModel):
    protocol_id: str
    name: str
    purpose: str
    status: str = "planning_stub"
    applicable_systems: list[str] = Field(default_factory=list)
    forbidden_uses: list[str] = Field(default_factory=list)
    software: list[str] = Field(default_factory=list)
    default_parameters: dict[str, Any] = Field(default_factory=dict)
    convergence_criteria: dict[str, Any] = Field(default_factory=dict)
    reference_state_definition: list[str] = Field(default_factory=list)
    required_controls: list[str] = Field(default_factory=list)
    audit_rules: list[str] = Field(default_factory=list)
    publication_text_template: str | None = None
    version: str = "mvp-0.1"
    source_scaffolds: list[str] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)
    source_hashes: dict[str, str] = Field(default_factory=dict)
    audit_status: str = "not_audited"
    human_review_required: bool = True


class ProtocolBinding(StrictModel):
    binding_id: str
    project_id: str
    question_id: str
    protocol_id: str
    protocol_version: str
    protocol_status: str
    can_generate_input: bool
    can_submit_aiida: bool
    block_reasons: list[str] = Field(default_factory=list)
    source_scaffolds: list[str] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)
    source_hashes: dict[str, str] = Field(default_factory=dict)
    status: str = "bound"
    audit_status: str = "protocol_gate_pending"
    human_review_required: bool = True


class StructureModel(StrictModel):
    structure_id: str
    question_id: str
    source: str
    format: str = "agent_structure_stub"
    protocol_id: str | None = None
    protocol_version: str | None = None
    ase_hash: str | None = None
    pymatgen_hash: str | None = None
    aiida_node_uuid: str | None = None
    model_type: str = "surface_or_interface_placeholder"
    surface_miller_index: str | None = None
    slab_layers: int | None = None
    vacuum_angstrom: float | None = None
    fixed_atoms: int | None = None
    adsorbates: list[str] = Field(default_factory=list)
    coverage: str | None = None
    defects: list[str] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)
    source_hashes: dict[str, str] = Field(default_factory=dict)
    audit_status: str = "not_audited"
    human_review_required: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CalculationTask(StrictModel):
    task_id: str
    question_id: str
    protocol_id: str
    structure_id: str
    protocol_version: str | None = None
    aiida_process_uuid: str | None = None
    software: str = "unresolved"
    code_uuid: str | None = None
    computer_label: str | None = None
    status: TaskStatus = TaskStatus.PLANNED
    exit_status: int | None = None
    retry_count: int = 0
    created_at: str = Field(default_factory=utc_now)
    completed_at: str | None = None
    provenance_mode: str = "dry_run"
    input_summary: dict[str, Any] = Field(default_factory=dict)
    audit_links: list[str] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)
    source_hashes: dict[str, str] = Field(default_factory=dict)
    audit_status: str = "not_audited"
    human_review_required: bool = True


class CalcResult(StrictModel):
    result_id: str
    task_id: str
    aiida_node_uuid: str | None = None
    parser_version: str = "dry-run-parser-v0"
    energy: float | None = None
    forces: dict[str, Any] | None = None
    magnetization: dict[str, Any] | None = None
    charge: dict[str, Any] | None = None
    optimized_structure_uuid: str | None = None
    derived_quantities: dict[str, Any] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    reference_state: str | None = None
    audit_status: str = "not_audited"
    provenance_mode: str = "dry_run"
    source_files: list[str] = Field(default_factory=list)
    source_hashes: dict[str, str] = Field(default_factory=dict)
    human_review_required: bool = True


class GateAudit(StrictModel):
    gate_id: str
    name: str
    subject_id: str
    status: GateStatus
    reason: str
    evidence_links: list[str] = Field(default_factory=list)
    human_review_required: bool = False
    next_action: str = "continue"
    created_at: str = Field(default_factory=utc_now)
    source_files: list[str] = Field(default_factory=list)
    source_hashes: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceClaim(StrictModel):
    claim_id: str
    claim_text: str
    level: ClaimLevel
    claim_type: str
    literature_evidence_ids: list[str] = Field(default_factory=list)
    calculation_result_ids: list[str] = Field(default_factory=list)
    figure_ids: list[str] = Field(default_factory=list)
    allowed_sections: list[str] = Field(default_factory=list)
    risk_level: str = "medium"
    audit_status: str = "not_audited"
    provenance_links: list[str] = Field(default_factory=list)
    human_review_required: bool = True
    source_files: list[str] = Field(default_factory=list)
    source_hashes: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SelfBuiltAgentConnection(StrictModel):
    agent_name: str
    priority: str
    implemented_in_dry_run: bool
    input_objects: list[str] = Field(default_factory=list)
    output_objects: list[str] = Field(default_factory=list)
    gate_ids: list[str] = Field(default_factory=list)
    status: str = "not_started"
    adapter_module: str | None = None
    notes: list[str] = Field(default_factory=list)


class SelfBuiltConnectionManifest(StrictModel):
    project_id: str
    run_id: str
    generated_at: str = Field(default_factory=utc_now)
    connections: list[SelfBuiltAgentConnection] = Field(default_factory=list)
    blocking_rules: list[str] = Field(default_factory=list)


class PipelineRunResult(StrictModel):
    run_id: str
    project: ProjectRecord
    selected_question_count: int
    structure_count: int
    task_count: int
    result_count: int
    claim_count: int
    output_dir: str
    created_files: list[str] = Field(default_factory=list)
    gate_summary: dict[str, int] = Field(default_factory=dict)
    scaffold_count: int = 0
