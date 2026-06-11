from __future__ import annotations

from research_agent.gates.feasibility import ComputationalFeasibilityGatekeeper
from research_agent.protocols.registry import ProtocolRegistry
from research_agent.schemas.core import (
    EvidenceClaim,
    GateAuditRecord,
    GateName,
    GateStatus,
    P0AuditSummary,
    ResearchQuestionCardV2,
    combine_status,
)


class AuditGateOrchestrator:
    """Run the P0 gate sequence: G1 evidence, G2 computability, G3 protocol."""

    def __init__(
        self,
        protocol_registry: ProtocolRegistry,
        feasibility_gatekeeper: ComputationalFeasibilityGatekeeper | None = None,
        min_evidence: int = 2,
    ):
        self.protocol_registry = protocol_registry
        self.feasibility_gatekeeper = feasibility_gatekeeper or ComputationalFeasibilityGatekeeper()
        self.min_evidence = min_evidence

    def audit_question(
        self,
        card: ResearchQuestionCardV2,
        evidence: list[EvidenceClaim] | None = None,
    ) -> P0AuditSummary:
        evidence_by_id = {item.evidence_id: item for item in evidence or []}
        linked_evidence = [evidence_id for evidence_id in card.evidence_ids if evidence_id in evidence_by_id]

        g1 = self._g1_literature_gate(card, linked_evidence, evidence_by_id)
        computability = self.feasibility_gatekeeper.audit(card)
        g2 = GateAuditRecord(
            gate=GateName.G2_COMPUTATIONAL_VERIFIABILITY,
            target_type="ResearchQuestionCardV2",
            target_id=card.question_id,
            status=computability.status,
            reasons=computability.reasons + computability.warnings,
            evidence_links=card.evidence_ids,
            human_review_required=computability.human_review_required,
            next_action=computability.next_action,
        )

        binding = self.protocol_registry.bind_question(card, require_executable=True)
        g3_reasons: list[str] = []
        for report in binding.reports:
            g3_reasons.extend(
                f"{report.protocol_id}: {finding}"
                for finding in report.blocking_findings
            )
            g3_reasons.extend(
                f"{report.protocol_id}: {warning}"
                for warning in report.warnings
            )
        if binding.missing_protocol_ids:
            g3_reasons.append(f"Missing protocols: {', '.join(binding.missing_protocol_ids)}")
        if binding.non_executable_protocol_ids:
            g3_reasons.append(f"Protocols not executable yet: {', '.join(binding.non_executable_protocol_ids)}")

        g3 = GateAuditRecord(
            gate=GateName.G3_PROTOCOL,
            target_type="ResearchQuestionCardV2",
            target_id=card.question_id,
            status=binding.status,
            reasons=g3_reasons,
            evidence_links=binding.bound_protocol_ids,
            human_review_required=binding.human_review_required,
            next_action=binding.next_action,
        )

        overall = combine_status([g1.status, g2.status, g3.status])
        return P0AuditSummary(
            question_id=card.question_id,
            overall_status=overall,
            candidate_for_next_stage=overall == GateStatus.PASS,
            gates=[g1, g2, g3],
            computability_report=computability,
            protocol_binding=binding,
        )

    def _g1_literature_gate(
        self,
        card: ResearchQuestionCardV2,
        linked_evidence: list[str],
        evidence_by_id: dict[str, EvidenceClaim],
    ) -> GateAuditRecord:
        reasons: list[str] = []
        human_review_required = False
        if len(linked_evidence) < self.min_evidence:
            reasons.append(
                f"Only {len(linked_evidence)} linked evidence records were found; minimum is {self.min_evidence}."
            )
        unchecked = [
            evidence_id
            for evidence_id in linked_evidence
            if evidence_by_id[evidence_id].requires_human_check
        ]
        if unchecked:
            reasons.append(f"{len(unchecked)} linked evidence records still require human source/context verification.")
            human_review_required = True

        if len(linked_evidence) < self.min_evidence:
            status = GateStatus.BLOCK
            next_action = "add_verified_literature_or_remove_question_from_compute_pool"
        elif human_review_required:
            status = GateStatus.WARN
            next_action = "verify_literature_metadata_and_context_before_publication_claims"
        else:
            status = GateStatus.PASS
            next_action = "proceed_to_computability_gate"

        return GateAuditRecord(
            gate=GateName.G1_LITERATURE_EVIDENCE,
            target_type="ResearchQuestionCardV2",
            target_id=card.question_id,
            status=status,
            reasons=reasons,
            evidence_links=linked_evidence,
            human_review_required=human_review_required,
            next_action=next_action,
        )
