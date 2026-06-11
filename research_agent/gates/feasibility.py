from __future__ import annotations

import re

from research_agent.schemas.core import (
    ComputabilityAuditReport,
    ComputabilityLabel,
    GateStatus,
    ResearchQuestionCardV2,
    RiskLevel,
)


class ComputationalFeasibilityGatekeeper:
    """Conservative C0-C3 scientific feasibility gate for computation-first claims."""

    QUANTITATIVE_PROTOCOL_MARKERS = {
        "adsorption_energy_protocol",
        "oxygen_vacancy_formation_protocol",
        "reaction_energy_path_protocol",
        "neb_barrier_protocol",
        "microkinetic_model_protocol",
    }

    def audit(self, card: ResearchQuestionCardV2) -> ComputabilityAuditReport:
        reasons: list[str] = []
        warnings: list[str] = []
        unanswered: list[str] = []
        final_label = card.preliminary_computability

        if not card.reaction.strip() or not card.catalyst.strip():
            reasons.append("Reaction and catalyst/model family must both be explicit.")
            final_label = ComputabilityLabel.C1

        if card.preliminary_computability in {ComputabilityLabel.C0, ComputabilityLabel.C1}:
            reasons.append("Only C2/C3 questions can enter computation planning.")

        if self._requires_wet_experiment_for_main_claim(card):
            reasons.append("Main claim appears to require wet-experimental validation, so it cannot be a computation-only core.")
            final_label = ComputabilityLabel.C1

        if not card.required_protocols:
            reasons.append("No required CalcProtocol is bound to the question.")

        if not card.minimal_publishable_results:
            reasons.append("No minimal publishable result set is defined.")

        if not card.evidence_ids:
            reasons.append("No literature/data evidence ids are linked to the question.")

        if not self.QUANTITATIVE_PROTOCOL_MARKERS.intersection(card.required_protocols):
            warnings.append("No quantitative energetics/barrier/kinetic protocol is bound; mechanism claim strength will be limited.")
            if card.preliminary_computability == ComputabilityLabel.C3:
                final_label = ComputabilityLabel.C2

        if self._contains_performance_terms(card):
            warnings.append(
                "The question mentions activity/selectivity/stability/performance. Computation can support mechanism trends, not prove experimental performance."
            )
            unanswered.append("Experimental activity, selectivity, long-term stability, and synthesis feasibility remain outside computation-only proof.")

        if self._mentions_neb(card) and "neb_barrier_protocol" not in card.required_protocols:
            warnings.append("NEB or transition-state evidence is implied but neb_barrier_protocol is not bound.")

        if self._mentions_reference_sensitive_protocol(card) and not card.required_reference_states:
            reasons.append("Reference-sensitive calculations require explicit reference states before planning.")

        claim_boundary = self._claim_boundary(final_label, card)
        if reasons:
            status = GateStatus.BLOCK
            risk_level = RiskLevel.CRITICAL if self._requires_wet_experiment_for_main_claim(card) else RiskLevel.HIGH
            next_action = "revise_question_or_add_missing_evidence_protocols"
        elif warnings:
            status = GateStatus.WARN
            risk_level = RiskLevel.MEDIUM
            next_action = "human_review_required_before_protocol_execution"
        else:
            status = GateStatus.PASS
            risk_level = RiskLevel.LOW if final_label == ComputabilityLabel.C2 else RiskLevel.MEDIUM
            next_action = "proceed_to_protocol_gate"

        return ComputabilityAuditReport(
            question_id=card.question_id,
            status=status,
            input_label=card.preliminary_computability,
            final_label=final_label,
            reasons=reasons,
            warnings=warnings,
            required_protocols=card.required_protocols,
            required_reference_states=card.required_reference_states,
            claim_boundary=claim_boundary,
            unanswered_by_computation=unanswered,
            risk_level=risk_level,
            human_review_required=status != GateStatus.PASS,
            next_action=next_action,
        )

    def _claim_boundary(self, label: ComputabilityLabel, card: ResearchQuestionCardV2) -> str:
        if label == ComputabilityLabel.C3:
            return (
                "May support an independent computational mechanism core only after protocol, structure, input, result, "
                "reference-state, figure, and claim-ledger gates pass. It still must not claim experimentally proven performance."
            )
        if label == ComputabilityLabel.C2:
            return (
                "Can support mechanism reassessment, trend comparison, or hypothesis prioritization. Experimental activity, "
                "stability, selectivity, and synthesis feasibility must remain explicitly outside the claim."
            )
        if label == ComputabilityLabel.C1:
            return "Can provide auxiliary discussion only; not suitable as the main computation-only research claim."
        return "Not answerable as a computation-only research claim."

    def _requires_wet_experiment_for_main_claim(self, card: ResearchQuestionCardV2) -> bool:
        text = card.wet_experiment_dependency.lower().replace("-", "_")
        if not text or "unknown" in text:
            return False
        negations = {
            "not_required",
            "not required",
            "not_needed",
            "not needed",
            "required_only_for_external_validation",
            "only_for_external_validation",
        }
        if any(item in text for item in negations):
            return False
        main_claim_phrases = {
            "required_for_main_claim",
            "required for main claim",
            "must_validate",
            "must validate",
            "requires_wet",
            "requires wet",
            "must be experimentally",
        }
        return any(item in text for item in main_claim_phrases)

    def _combined_text(self, card: ResearchQuestionCardV2) -> str:
        parts = [
            card.title,
            card.question_type,
            card.wet_experiment_dependency,
            *card.unresolved_gap,
            *card.computational_path_hint,
            *card.expected_result_types,
            *card.minimal_publishable_results,
        ]
        return " ".join(parts).lower()

    def _contains_performance_terms(self, card: ResearchQuestionCardV2) -> bool:
        text = self._combined_text(card)
        return bool(re.search(r"\b(activity|selectivity|stability|performance|yield|conversion)\b", text))

    def _mentions_neb(self, card: ResearchQuestionCardV2) -> bool:
        text = self._combined_text(card)
        return bool(re.search(r"\b(neb|transition[- ]state|activation barrier|barrier)\b", text))

    def _mentions_reference_sensitive_protocol(self, card: ResearchQuestionCardV2) -> bool:
        protocols = set(card.required_protocols)
        return bool(
            protocols.intersection(
                {
                    "adsorption_energy_protocol",
                    "oxygen_vacancy_formation_protocol",
                    "reaction_energy_path_protocol",
                    "neb_barrier_protocol",
                    "microkinetic_model_protocol",
                }
            )
        )
