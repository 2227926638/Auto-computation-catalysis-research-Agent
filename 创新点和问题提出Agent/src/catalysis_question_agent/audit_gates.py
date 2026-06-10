from __future__ import annotations

from collections import Counter

from .models import ComputabilityLabel, ProjectScope, ResearchQuestionCard
from .protocol_registry import ProtocolRegistry
from .research_pipeline_models import ClaimLevel, EvidenceClaim, GateAudit, GateStatus


GATE_NAMES = {
    "G0": "Project Scope Gate",
    "G1": "Literature Evidence Gate",
    "G2": "Computational Verifiability Gate",
    "G3": "Protocol Gate",
    "G4": "Structure Gate",
    "G5": "Input Gate",
    "G6": "Run Gate",
    "G7": "Result Gate",
    "G8": "Figure Gate",
    "G9": "Claim Gate",
    "G10": "Graduation/Submission Gate",
}


def gate(
    gate_id: str,
    subject_id: str,
    status: GateStatus,
    reason: str,
    *,
    evidence_links: list[str] | None = None,
    human_review_required: bool = False,
    next_action: str = "continue",
    metadata: dict | None = None,
) -> GateAudit:
    return GateAudit(
        gate_id=gate_id,
        name=GATE_NAMES[gate_id],
        subject_id=subject_id,
        status=status,
        reason=reason,
        evidence_links=evidence_links or [],
        human_review_required=human_review_required,
        next_action=next_action,
        metadata=metadata or {},
    )


def project_scope_gate(scope: ProjectScope) -> GateAudit:
    missing = []
    if not scope.project_id:
        missing.append("project_id")
    if not scope.reaction:
        missing.append("reaction")
    if not scope.catalyst_family:
        missing.append("catalyst_family")
    if missing:
        return gate(
            "G0",
            scope.project_id or "unknown_project",
            GateStatus.BLOCK,
            f"Missing project scope fields: {', '.join(missing)}.",
            human_review_required=True,
            next_action="complete project scope before generating question cards",
        )
    return gate(
        "G0",
        scope.project_id,
        GateStatus.PASS,
        "Reaction and catalyst family are defined.",
        human_review_required=scope.graduation_target is None,
        next_action="continue to literature evidence gate",
    )


def question_preplanning_gates(
    card: ResearchQuestionCard,
    registry: ProtocolRegistry,
    *,
    min_evidence: int = 2,
) -> list[GateAudit]:
    evidence_count = len(card.evidence_ids)
    g1_status = GateStatus.PASS if evidence_count >= min_evidence else GateStatus.BLOCK
    g1 = gate(
        "G1",
        card.question_id,
        g1_status,
        f"Question card has {evidence_count} linked evidence item(s); minimum is {min_evidence}.",
        evidence_links=card.evidence_ids,
        human_review_required=True,
        next_action="verify DOI/title/page evidence before computation planning"
        if g1_status == GateStatus.PASS
        else "add literature evidence or keep as background only",
    )

    computable = card.preliminary_computability in {ComputabilityLabel.C2, ComputabilityLabel.C3}
    g2 = gate(
        "G2",
        card.question_id,
        GateStatus.PASS if computable else GateStatus.BLOCK,
        f"Preliminary computability is {card.preliminary_computability}.",
        human_review_required=True,
        next_action="continue to protocol binding" if computable else "do not create calculation tasks",
    )

    known, missing = registry.split_known_missing(card.required_protocols)
    input_ready = [protocol_id for protocol_id in known if registry.can_generate_input(protocol_id)]
    prebind_only = [protocol_id for protocol_id in known if protocol_id not in input_ready]
    protocol_block_reasons = {protocol_id: registry.input_block_reasons(protocol_id) for protocol_id in prebind_only}
    if input_ready and not missing and not prebind_only:
        g3_status = GateStatus.PASS
        reason = f"All {len(input_ready)} requested protocol(s) are executable MVP protocols."
        next_action = "continue to structure and input planning"
    elif input_ready:
        g3_status = GateStatus.WARN
        detail = []
        if prebind_only:
            detail.append(f"prebind-only: {', '.join(prebind_only)}")
        if missing:
            detail.append(f"missing: {', '.join(missing)}")
        reason = f"{len(input_ready)} executable protocol(s) available; " + "; ".join(detail) + "."
        next_action = "generate inputs only for executable_mvp protocols and extend registry for the rest"
    elif known:
        g3_status = GateStatus.BLOCK
        reason = f"{len(known)} protocol(s) are registered but none is executable_mvp with complete required fields."
        next_action = "complete Protocol Registry Agent fields before structure/input planning"
    else:
        g3_status = GateStatus.BLOCK
        reason = "No requested protocol is registered."
        next_action = "add CalcProtocol entries before planning calculation tasks"
    g3 = gate(
        "G3",
        card.question_id,
        g3_status,
        reason,
        evidence_links=known,
        human_review_required=g3_status != GateStatus.PASS,
        next_action=next_action,
        metadata={
            "registered_protocols": known,
            "input_ready_protocols": input_ready,
            "prebind_only_protocols": prebind_only,
            "missing_protocols": missing,
            "protocol_block_reasons": protocol_block_reasons,
        },
    )
    return [g1, g2, g3]


def structure_gate(structure_id: str, *, dry_run: bool = True) -> GateAudit:
    if dry_run:
        return gate(
            "G4",
            structure_id,
            GateStatus.WARN,
            "Only a placeholder StructureModel was generated; no pymatgen/ASE geometry has been audited yet.",
            human_review_required=True,
            next_action="replace placeholder with a real slab/interface model and rerun structure audit",
        )
    return gate("G4", structure_id, GateStatus.PASS, "Structure audit passed.")


def input_gate(task_id: str, *, dry_run: bool = True) -> GateAudit:
    if dry_run:
        return gate(
            "G5",
            task_id,
            GateStatus.WARN,
            "Input parameters are protocol-bound but not yet rendered for VASP/QE/CP2K.",
            human_review_required=True,
            next_action="render engine-specific inputs and compare them with CalcProtocol defaults",
        )
    return gate("G5", task_id, GateStatus.PASS, "Input audit passed.")


def run_gate(task_id: str, *, dry_run: bool = True) -> GateAudit:
    if dry_run:
        return gate(
            "G6",
            task_id,
            GateStatus.WARN,
            "Task was simulated by the AiiDA adapter; no real CalcJob/WorkChain finished.",
            human_review_required=False,
            next_action="submit through a configured AiiDA profile before quantitative analysis",
        )
    return gate("G6", task_id, GateStatus.PASS, "AiiDA task completed successfully.")


def result_gate(result_id: str, *, dry_run: bool = True) -> GateAudit:
    if dry_run:
        return gate(
            "G7",
            result_id,
            GateStatus.BLOCK,
            "Dry-run result has no parsed energy, forces, reference state, or convergence evidence.",
            human_review_required=True,
            next_action="parse a real AiiDA result before adding calculation-backed manuscript claims",
        )
    return gate("G7", result_id, GateStatus.PASS, "Result audit passed.")


def claim_gate(claim: EvidenceClaim) -> GateAudit:
    if claim.level == ClaimLevel.L0:
        return gate(
            "G9",
            claim.claim_id,
            GateStatus.BLOCK,
            "L0 claim is not evidence-supported and cannot enter manuscript text.",
            evidence_links=claim.provenance_links,
            human_review_required=True,
            next_action="upgrade with literature or calculation evidence, or keep outside manuscript",
        )
    if claim.level == ClaimLevel.L1:
        return gate(
            "G9",
            claim.claim_id,
            GateStatus.WARN,
            "L1 claim is literature/background only and cannot be used as a calculation result.",
            evidence_links=claim.provenance_links,
            human_review_required=True,
            next_action="use only in introduction/background unless computation support is added",
        )
    return gate(
        "G9",
        claim.claim_id,
        GateStatus.PASS,
        f"{claim.level} claim has structured evidence links.",
        evidence_links=claim.provenance_links,
        human_review_required=claim.human_review_required,
        next_action="eligible for claim-ledger-only manuscript generation",
    )


def gate_summary(gates: list[GateAudit]) -> dict[str, int]:
    counts = Counter(gate.status.value for gate in gates)
    return {status.value: counts.get(status.value, 0) for status in GateStatus}
