from __future__ import annotations

from importlib.util import find_spec
from uuid import uuid4

from .models import ResearchQuestionCard
from .research_pipeline_models import CalcProtocol, CalcResult, CalculationTask, StructureModel, TaskStatus, utc_now


class AiiDAAdapter:
    """Thin boundary for AiiDA-backed execution.

    The MVP implements an explicit dry-run mode so the full agent skeleton can be
    exercised before a profile, computer, and code are configured.
    """

    def __init__(
        self,
        *,
        mode: str = "dry_run",
        aiida_profile: str | None = None,
        computer_label: str | None = None,
        code_uuid: str | None = None,
    ):
        self.mode = mode
        self.aiida_profile = aiida_profile
        self.computer_label = computer_label
        self.code_uuid = code_uuid

    @property
    def aiida_importable(self) -> bool:
        return find_spec("aiida") is not None

    @property
    def is_dry_run(self) -> bool:
        return self.mode != "aiida" or not self.aiida_importable

    def submit(
        self,
        *,
        run_id: str,
        task_index: int,
        card: ResearchQuestionCard,
        protocol: CalcProtocol,
        structure: StructureModel,
    ) -> tuple[CalculationTask, CalcResult]:
        task_uuid = str(uuid4())
        result_uuid = str(uuid4())
        protocol_software = list(getattr(protocol, "software", None) or getattr(protocol, "supported_software", []) or [])
        protocol_reference_states = list(
            getattr(protocol, "reference_state_definition", None)
            or getattr(protocol, "required_reference_states", [])
            or []
        )
        protocol_source_files = list(getattr(protocol, "source_files", []) or [])
        protocol_source_hashes = dict(getattr(protocol, "source_hashes", {}) or {})
        protocol_source_scaffolds = list(getattr(protocol, "source_scaffolds", []) or [])
        software = protocol_software[0] if protocol_software else "unresolved"
        task = CalculationTask(
            task_id=f"TASK-{run_id}-{task_index:03d}",
            question_id=card.question_id,
            protocol_id=protocol.protocol_id,
            protocol_version=protocol.version,
            structure_id=structure.structure_id,
            aiida_process_uuid=task_uuid,
            software=software,
            code_uuid=self.code_uuid,
            computer_label=self.computer_label,
            status=TaskStatus.SIMULATED if self.is_dry_run else TaskStatus.PLANNED,
            exit_status=0 if self.is_dry_run else None,
            completed_at=utc_now() if self.is_dry_run else None,
            provenance_mode="dry_run" if self.is_dry_run else "aiida_adapter_stub",
            input_summary={
                "protocol_name": protocol.name,
                "question_title": card.title,
                "reference_states": protocol_reference_states,
                "audit_rules": protocol.audit_rules,
            },
            source_files=list(dict.fromkeys(protocol_source_files + structure.source_files)),
            source_hashes={**protocol_source_hashes, **structure.source_hashes},
        )
        result = CalcResult(
            result_id=f"RESULT-{run_id}-{task_index:03d}",
            task_id=task.task_id,
            aiida_node_uuid=result_uuid,
            derived_quantities={
                "planned_only": self.is_dry_run,
                "protocol_id": protocol.protocol_id,
                "source_scaffolds": protocol_source_scaffolds,
            },
            reference_state="; ".join(protocol_reference_states) or None,
            audit_status="blocked_dry_run" if self.is_dry_run else "not_audited",
            provenance_mode=task.provenance_mode,
        )
        return task, result
