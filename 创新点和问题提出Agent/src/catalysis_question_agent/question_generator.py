from __future__ import annotations

import re

from .config import project_scope_from_config
from .models import (
    ComputabilityLabel,
    ConsensusClaim,
    ControversyClaim,
    ResearchQuestionCard,
)


class QuestionGenerator:
    """Generate research-question cards from consensus and controversy claims."""

    def __init__(self, config: dict):
        self.config = config
        self.scope = project_scope_from_config(config)
        self.patterns = list((config.get("generation", {}) or {}).get("opportunity_patterns", []) or [])
        if not self.patterns:
            self.patterns = [
                "consensus_without_mechanistic_closure",
                "literature_conflict",
                "oversimplified_model",
                "method_gap",
            ]

    def generate(
        self,
        consensus: list[ConsensusClaim],
        controversies: list[ControversyClaim],
    ) -> list[ResearchQuestionCard]:
        target = int((self.config.get("generation", {}) or {}).get("target_final_cards", 20))
        topics = self._topics(consensus, controversies)
        cards: list[ResearchQuestionCard] = []
        next_id = 1

        for pattern in self.patterns:
            for topic in topics:
                con_ids = [item.consensus_id for item in consensus if item.topic == topic]
                ctr_ids = [item.controversy_id for item in controversies if item.topic == topic]
                evidence_ids = self._evidence_ids(topic, consensus, controversies)
                card = self._make_card(next_id, topic, pattern, con_ids, ctr_ids, evidence_ids)
                cards.append(card)
                next_id += 1
                if len(cards) >= target:
                    return cards

        return cards

    def _make_card(
        self,
        idx: int,
        topic: str,
        pattern: str,
        consensus_ids: list[str],
        controversy_ids: list[str],
        evidence_ids: list[str],
    ) -> ResearchQuestionCard:
        title = self._title(topic, pattern)
        computability, cost = self._computability_and_cost(pattern)
        protocols = self._required_protocols(topic, pattern)
        reference_states = self._required_reference_states(topic, pattern)
        audit_risks = self._expected_audit_risks(topic, pattern, protocols)
        evidence_gate = "pass_G1_prefilter" if len(evidence_ids) >= 2 else "fail_G1_needs_more_literature_evidence"
        verifiability_gate = (
            "pass_G2_C2_C3_candidate"
            if computability in {ComputabilityLabel.C2, ComputabilityLabel.C3}
            else "fail_G2_support_only_or_experimental_dependency"
        )
        return ResearchQuestionCard(
            question_id=f"RQ-{self._slug(self.scope.project_id)}-{idx:03d}",
            title=title,
            reaction=self.scope.reaction,
            catalyst=self.scope.catalyst_family,
            question_type=pattern,
            background_consensus_ids=consensus_ids,
            controversy_ids=controversy_ids,
            evidence_ids=evidence_ids,
            unresolved_gap=self._gaps(topic, pattern),
            computational_path_hint=self._computational_path(topic, pattern),
            expected_result_types=self._expected_results(pattern),
            minimal_publishable_results=self._minimal_results(pattern),
            required_protocols=protocols,
            required_reference_states=reference_states,
            protocol_feasibility=(
                "candidate_protocols_available_in_mvp_registry"
                if protocols
                else "no_registered_protocol_hint"
            ),
            aiida_executability=self._aiida_executability(computability, protocols),
            computational_verifiability_gate=verifiability_gate,
            literature_evidence_gate=evidence_gate,
            expected_audit_risks=audit_risks,
            wet_experiment_dependency=self._wet_experiment_dependency(pattern),
            preliminary_computability=computability,
            novelty_risk="unknown_until_recent_work_check",
            calculation_cost=cost,
            graduation_value="B档机制论文候选；也可作为 A档 Agent 方法论文案例",
            risks=[
                "Requires manual DOI/source verification.",
                "Needs downstream novelty check against recent complete studies.",
                "Protocol binding is a pre-screen; downstream Protocol Registry Agent must validate exact settings.",
            ],
            metadata={"topic": topic, "opportunity_pattern": pattern},
        )

    def _topics(self, consensus: list[ConsensusClaim], controversies: list[ControversyClaim]) -> list[str]:
        topics = [item.topic for item in consensus] + [item.topic for item in controversies]
        if not topics:
            topics = [
                "oxygen vacancy",
                "metal-support interaction",
                "N2 activation",
                "NHx hydrogenation",
                "rate-determining step",
            ]
        seen: set[str] = set()
        out: list[str] = []
        generic_topics = {"general catalysis question", "computational method"}
        for topic in topics:
            if topic in generic_topics and len(set(topics)) > 1:
                continue
            if topic not in seen:
                seen.add(topic)
                out.append(topic)
        return out

    def _evidence_ids(
        self,
        topic: str,
        consensus: list[ConsensusClaim],
        controversies: list[ControversyClaim],
    ) -> list[str]:
        ids: list[str] = []
        for item in consensus:
            if item.topic == topic:
                ids.extend(item.supporting_evidence_ids)
        for item in controversies:
            if item.topic == topic:
                ids.extend(item.supporting_evidence_a)
                ids.extend(item.supporting_evidence_b)
        return list(dict.fromkeys(ids))

    def _title(self, topic: str, pattern: str) -> str:
        reaction = self.scope.reaction
        catalyst = self.scope.catalyst_family
        templates = {
            "consensus_without_mechanistic_closure": (
                f"Can {topic} mechanistically explain {reaction} on {catalyst}?"
            ),
            "literature_conflict": (
                f"Which {topic}-related pathway controls {reaction} on {catalyst}?"
            ),
            "oversimplified_model": (
                f"Do realistic {topic}-aware models change the computed mechanism of {reaction} on {catalyst}?"
            ),
            "strong_experiment_weak_computation": (
                f"Can computation rationalize reported {topic} effects in {reaction} over {catalyst}?"
            ),
            "industry_hot_basic_gap": (
                f"Is {topic} a calculable design lever for applied {reaction} on {catalyst}?"
            ),
            "available_data_not_integrated": (
                f"Can literature and database evidence reveal {self._article(topic)} {topic} descriptor for {reaction} on {catalyst}?"
            ),
            "scaling_relation_outlier": (
                f"Does {topic} break common adsorption-energy scaling in {reaction} on {catalyst}?"
            ),
            "method_gap": (
                f"Which minimum DFT/NEB/electronic-structure set is needed to resolve {topic} in {reaction} on {catalyst}?"
            ),
        }
        return templates.get(pattern, f"Can {topic} define a computable research question for {reaction} on {catalyst}?")

    def _gaps(self, topic: str, pattern: str) -> list[str]:
        return [
            f"The literature signal around {topic} needs to be converted into a specific mechanism claim.",
            "It is not yet clear whether adsorption trends, kinetic barriers, or electronic structure dominate the story.",
            f"Opportunity pattern: {pattern}.",
        ]

    def _computational_path(self, topic: str, pattern: str) -> list[str]:
        base = [
            f"Construct baseline and {topic}-modified models for {self.scope.catalyst_family}.",
            "Enumerate relevant adsorbates/intermediates for N2, N, NH, NH2, and NH3 where applicable.",
            "Compute adsorption energies and key reaction energies for the minimum model set.",
            "Use NEB or transition-state search for the most decisive competing steps.",
            "Use Bader/PDOS/charge-density-difference analysis to connect energetics with electronic structure.",
        ]
        if pattern == "available_data_not_integrated":
            base.insert(0, "Build a small structured table from literature/database records before new calculations.")
        if pattern == "method_gap":
            base.append("Benchmark whether low-cost screening changes the final DFT task ranking.")
        return base

    def _expected_results(self, pattern: str) -> list[str]:
        results = [
            "literature-grounded mechanism map",
            "adsorption-energy table",
            "reaction-pathway energy diagram",
            "electronic-structure interpretation",
        ]
        if pattern in {"literature_conflict", "consensus_without_mechanistic_closure", "method_gap"}:
            results.append("rate-determining-step comparison")
        if pattern == "available_data_not_integrated":
            results.append("descriptor or evidence matrix")
        return results

    def _minimal_results(self, pattern: str) -> list[str]:
        results = [
            "2-3 surface or interface models",
            "key intermediate adsorption energies",
            "at least one decisive competing reaction path",
            "one electronic-structure analysis set",
        ]
        if pattern in {"literature_conflict", "method_gap", "consensus_without_mechanistic_closure"}:
            results.append("NEB barriers for decisive steps")
        return results

    def _required_protocols(self, topic: str, pattern: str) -> list[str]:
        lower = " ".join([topic, pattern]).lower()
        protocols = ["slab_model_construction_protocol"]
        if any(term in lower for term in ("oxygen vacancy", "vacancy", "ce3", "defect")):
            protocols.append("oxygen_vacancy_formation_protocol")
        if any(term in lower for term in ("n2", "nhx", "adsorption", "hydrogenation", "descriptor", "scaling")):
            protocols.append("adsorption_energy_protocol")
            protocols.append("adsorbate_configuration_screening_protocol")
        if any(term in lower for term in ("pathway", "rate-determining", "literature_conflict", "mechanistic", "mechanism")):
            protocols.append("reaction_energy_path_protocol")
        if any(term in lower for term in ("barrier", "dissociation", "neb", "literature_conflict", "rate-determining")):
            protocols.append("neb_barrier_protocol")
        if any(term in lower for term in ("charge", "ce3", "metal-support", "smsi", "electronic", "oxygen vacancy")):
            protocols.append("bader_charge_protocol")
            protocols.append("pdos_analysis_protocol")
        if any(term in lower for term in ("cohp", "bond")):
            protocols.append("cohp_analysis_protocol")
        if any(term in lower for term in ("microkinetic", "tof", "rate")):
            protocols.append("microkinetic_model_protocol")
        if pattern == "method_gap":
            protocols.extend(["adsorption_energy_protocol", "neb_barrier_protocol", "bader_charge_protocol", "pdos_analysis_protocol"])
        if pattern == "available_data_not_integrated":
            protocols.append("mlip_prescreening_protocol")
        return list(dict.fromkeys(protocols))

    def _required_reference_states(self, topic: str, pattern: str) -> list[str]:
        lower = " ".join([topic, pattern]).lower()
        states = [
            "relaxed clean slab/interface model",
            "gas-phase N2, H2, and NH3 references",
        ]
        if any(term in lower for term in ("oxygen vacancy", "vacancy", "ce3", "defect")):
            states.extend(
                [
                    "relaxed defective slab with specified oxygen vacancy",
                    "oxygen chemical potential reference for vacancy formation",
                ]
            )
        if any(term in lower for term in ("n2", "nhx", "hydrogenation", "pathway", "adsorption")):
            states.append("adsorbed N2/N/NH/NH2/NH3 intermediates on enumerated sites")
        if any(term in lower for term in ("barrier", "dissociation", "rate-determining", "literature_conflict")):
            states.append("validated initial/final states for each NEB path")
        return list(dict.fromkeys(states))

    def _expected_audit_risks(self, topic: str, pattern: str, protocols: list[str]) -> list[str]:
        lower = " ".join([topic, pattern, " ".join(protocols)]).lower()
        risks = [
            "DFT functional, U value, dispersion correction, slab size, vacuum, and k-point settings must match protocol.",
            "Adsorption and reaction energies require explicit reference-state bookkeeping.",
        ]
        if "oxygen_vacancy_formation_protocol" in protocols:
            risks.append("Vacancy formation energy is sensitive to oxygen chemical potential and Ce3+/Ce4+ localization.")
        if "neb_barrier_protocol" in protocols:
            risks.append("NEB endpoints, image count, force threshold, and possible alternative paths require audit.")
        if "bader_charge_protocol" in protocols or "pdos_analysis_protocol" in protocols:
            risks.append("Electronic-structure interpretation must be tied to converged geometries and consistent charge partitioning.")
        if "microkinetic_model_protocol" in protocols:
            risks.append("Microkinetic claims need temperature/pressure assumptions and uncertainty propagation.")
        if "mlip_prescreening_protocol" in protocols:
            risks.append("MLIP pre-screening cannot become manuscript-level evidence without DFT confirmation.")
        if "scaling" in lower:
            risks.append("Scaling-relation outlier claims need comparable site definitions and coverage conditions.")
        return list(dict.fromkeys(risks))

    def _aiida_executability(self, computability: ComputabilityLabel, protocols: list[str]) -> str:
        if computability not in {ComputabilityLabel.C2, ComputabilityLabel.C3}:
            return "blocked_before_aiida_planning"
        if not protocols:
            return "blocked_until_protocol_registered"
        return "candidate_for_aiida_workchain_after_protocol_gate"

    def _wet_experiment_dependency(self, pattern: str) -> str:
        if pattern == "strong_experiment_weak_computation":
            return "uses_experiment_as_background; pure_computation_can_answer_mechanistic_subquestion"
        if pattern == "industry_hot_basic_gap":
            return "likely_needs_experiment_for_performance_claim; computation_only_support"
        return "not_required_for_mechanism_claim; required_only_for_external_validation"

    def _computability_and_cost(self, pattern: str) -> tuple[ComputabilityLabel, str]:
        if pattern == "industry_hot_basic_gap":
            return ComputabilityLabel.C1, "medium"
        if pattern in {"available_data_not_integrated", "method_gap"}:
            return ComputabilityLabel.C3, "medium"
        if pattern in {"literature_conflict", "consensus_without_mechanistic_closure"}:
            return ComputabilityLabel.C2, "medium-high"
        return ComputabilityLabel.C2, "medium"

    def _slug(self, value: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-")
        return clean or "project"

    def _article(self, value: str) -> str:
        return "an" if value[:1].lower() in {"a", "e", "i", "o", "u"} else "a"
