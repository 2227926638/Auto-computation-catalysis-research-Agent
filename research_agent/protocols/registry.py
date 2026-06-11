from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from research_agent.schemas.core import (
    CalcProtocol,
    GateStatus,
    ProtocolAuditReport,
    ProtocolBinding,
    ProtocolStatus,
    ResearchQuestionCardV2,
    combine_status,
)


class ProtocolRegistry:
    """Versioned registry for calculation protocols."""

    def __init__(self, protocols: list[CalcProtocol]):
        self.protocols = {protocol.protocol_id: protocol for protocol in protocols}

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ProtocolRegistry":
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError(f"Protocol registry must be a YAML mapping: {path}")
        top_status = payload.get("status")
        protocols = [cls._coerce_protocol(item, top_status=top_status) for item in payload.get("protocols", [])]
        return cls(protocols)

    @classmethod
    def default(cls) -> "ProtocolRegistry":
        return cls.from_yaml(Path(__file__).with_name("core_protocols.yaml"))

    @staticmethod
    def _coerce_protocol(item: dict[str, Any], top_status: str | None = None) -> CalcProtocol:
        payload = dict(item)
        if "status" not in payload and top_status:
            payload["status"] = top_status
        if "audit_rules" not in payload and "audit_checks" in payload:
            payload["audit_rules"] = payload.pop("audit_checks")
        if "supported_software" not in payload and "software" in payload:
            payload["supported_software"] = payload.pop("software")
        if "publication_boundary" not in payload and "publication_text_template" in payload:
            payload["publication_boundary"] = payload.pop("publication_text_template")
        if "required_reference_states" not in payload and "reference_state_definition" in payload:
            payload["required_reference_states"] = payload.pop("reference_state_definition")
        for legacy_field in ("source_scaffolds", "source_files", "source_hashes", "audit_status", "human_review_required"):
            payload.pop(legacy_field, None)
        return CalcProtocol.model_validate(payload)

    def get(self, protocol_id: str) -> CalcProtocol | None:
        return self.protocols.get(protocol_id)

    def audit_protocol(self, protocol: CalcProtocol, require_executable: bool = True) -> ProtocolAuditReport:
        blocking: list[str] = []
        warnings: list[str] = []
        findings: list[str] = []

        if protocol.status == ProtocolStatus.DEPRECATED:
            blocking.append("Protocol is deprecated and cannot be used for new calculation tasks.")
        if require_executable and protocol.status == ProtocolStatus.PLANNING_STUB:
            blocking.append("Protocol is only a planning stub; it cannot generate auditable calculation tasks.")

        required_lists = {
            "applicable_systems": protocol.applicable_systems,
            "forbidden_uses": protocol.forbidden_uses,
            "required_inputs": protocol.required_inputs,
            "required_reference_states": protocol.required_reference_states,
            "audit_rules": protocol.audit_rules,
        }
        for field_name, values in required_lists.items():
            if not values:
                blocking.append(f"Protocol field '{field_name}' is empty.")

        if require_executable and not protocol.convergence_criteria:
            blocking.append("Executable protocols must define convergence criteria.")
        if require_executable and not protocol.publication_boundary:
            blocking.append("Executable protocols must define publication_boundary.")
        if not protocol.required_controls:
            warnings.append("No required control calculations/checks are defined.")
        if not protocol.supported_software:
            warnings.append("No supported software profile is declared; downstream input building must bind one explicitly.")
        if protocol.status in {ProtocolStatus.EXECUTABLE_MVP, ProtocolStatus.EXECUTABLE_REVIEWED}:
            findings.append(f"Protocol {protocol.protocol_id}@{protocol.version} is executable under status {protocol.status}.")

        status = GateStatus.BLOCK if blocking else GateStatus.WARN if warnings else GateStatus.PASS
        next_action = "fix_protocol_definition_before_execution" if blocking else "human_review_recommended" if warnings else "protocol_ready"
        return ProtocolAuditReport(
            protocol_id=protocol.protocol_id,
            status=status,
            findings=findings,
            blocking_findings=blocking,
            warnings=warnings,
            human_review_required=status != GateStatus.PASS,
            next_action=next_action,
        )

    def bind_question(
        self,
        card: ResearchQuestionCardV2,
        require_executable: bool = True,
    ) -> ProtocolBinding:
        requested = list(dict.fromkeys(card.required_protocols))
        reports: list[ProtocolAuditReport] = []
        missing: list[str] = []
        bound: list[str] = []
        executable: list[str] = []
        non_executable: list[str] = []
        reference_states: list[str] = []

        if not requested:
            return ProtocolBinding(
                question_id=card.question_id,
                status=GateStatus.BLOCK,
                requested_protocol_ids=[],
                next_action="bind_at_least_one_registered_protocol",
                human_review_required=True,
            )

        for protocol_id in requested:
            protocol = self.get(protocol_id)
            if protocol is None:
                missing.append(protocol_id)
                continue
            bound.append(protocol_id)
            reference_states.extend(protocol.required_reference_states)
            report = self.audit_protocol(protocol, require_executable=require_executable)
            reports.append(report)
            if report.status == GateStatus.BLOCK:
                non_executable.append(protocol_id)
            else:
                executable.append(protocol_id)

        statuses = [report.status for report in reports]
        if missing:
            statuses.append(GateStatus.BLOCK)
        if not statuses:
            statuses.append(GateStatus.BLOCK)
        status = combine_status(statuses)
        if status == GateStatus.BLOCK:
            next_action = "complete_or_replace_missing_non_executable_protocols"
        elif status == GateStatus.WARN:
            next_action = "human_protocol_review_before_input_generation"
        else:
            next_action = "proceed_to_structure_or_input_planning"

        return ProtocolBinding(
            question_id=card.question_id,
            status=status,
            requested_protocol_ids=requested,
            bound_protocol_ids=bound,
            executable_protocol_ids=executable,
            non_executable_protocol_ids=non_executable,
            missing_protocol_ids=missing,
            required_reference_states=list(dict.fromkeys(reference_states)),
            reports=reports,
            human_review_required=status != GateStatus.PASS,
            next_action=next_action,
        )
