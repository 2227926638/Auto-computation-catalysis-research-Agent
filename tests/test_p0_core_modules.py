from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from research_agent import (
    AuditGateOrchestrator,
    ComputationalFeasibilityGatekeeper,
    ComputabilityLabel,
    EvidenceClaim,
    GateStatus,
    ProtocolRegistry,
    QuestionAgentAdapter,
    ResearchQuestionCardV2,
)


def make_card(**overrides) -> ResearchQuestionCardV2:
    payload = {
        "question_id": "RQ-test-001",
        "title": "Can adsorption energetics explain N2 activation trends on Ru-CeO2?",
        "reaction": "N2 activation and NHx hydrogenation",
        "catalyst": "Ru-CeO2",
        "question_type": "mechanism_reassessment",
        "evidence_ids": ["EVD-1", "EVD-2"],
        "computational_path_hint": [
            "Build audited slab models.",
            "Compute adsorption energies for key intermediates.",
        ],
        "expected_result_types": ["adsorption-energy table", "mechanism trend comparison"],
        "minimal_publishable_results": ["clean slab", "adsorbate-slab energies"],
        "required_protocols": ["slab_model_construction_protocol", "adsorption_energy_protocol"],
        "required_reference_states": ["relaxed clean slab", "gas-phase N2", "gas-phase H2"],
        "wet_experiment_dependency": "not_required_for_mechanism_claim; required_only_for_external_validation",
        "preliminary_computability": "C2",
        "status": "recommend",
    }
    payload.update(overrides)
    return ResearchQuestionCardV2.model_validate(payload)


def verified_evidence() -> list[EvidenceClaim]:
    return [
        EvidenceClaim(
            evidence_id="EVD-1",
            source_id="SRC-1",
            claim_type="method",
            topic="adsorption",
            claim_text="DFT adsorption energies can compare N2 activation trends.",
            requires_human_check=False,
        ),
        EvidenceClaim(
            evidence_id="EVD-2",
            source_id="SRC-2",
            claim_type="consensus",
            topic="Ru-CeO2",
            claim_text="Ru-CeO2 interfaces are relevant to N2 activation.",
            requires_human_check=False,
        ),
    ]


class ProtocolRegistryTests(unittest.TestCase):
    def test_default_registry_marks_only_mvp_protocols_executable(self) -> None:
        registry = ProtocolRegistry.default()

        slab = registry.audit_protocol(registry.get("slab_model_construction_protocol"))
        adsorption = registry.audit_protocol(registry.get("adsorption_energy_protocol"))
        vacancy = registry.audit_protocol(registry.get("oxygen_vacancy_formation_protocol"))

        self.assertEqual(slab.status, GateStatus.PASS)
        self.assertEqual(adsorption.status, GateStatus.PASS)
        self.assertEqual(vacancy.status, GateStatus.BLOCK)
        self.assertTrue(any("planning stub" in finding for finding in vacancy.blocking_findings))

    def test_binding_blocks_non_executable_required_protocols(self) -> None:
        registry = ProtocolRegistry.default()
        card = make_card(required_protocols=["slab_model_construction_protocol", "bader_charge_protocol"])

        binding = registry.bind_question(card)

        self.assertEqual(binding.status, GateStatus.BLOCK)
        self.assertIn("bader_charge_protocol", binding.non_executable_protocol_ids)
        self.assertIn("slab_model_construction_protocol", binding.executable_protocol_ids)


class FeasibilityGateTests(unittest.TestCase):
    def test_blocks_c1_questions(self) -> None:
        report = ComputationalFeasibilityGatekeeper().audit(
            make_card(preliminary_computability=ComputabilityLabel.C1)
        )

        self.assertEqual(report.status, GateStatus.BLOCK)
        self.assertIn("Only C2/C3 questions can enter computation planning.", report.reasons)

    def test_blocks_wet_experiment_required_main_claim(self) -> None:
        report = ComputationalFeasibilityGatekeeper().audit(
            make_card(wet_experiment_dependency="required_for_main_claim")
        )

        self.assertEqual(report.status, GateStatus.BLOCK)
        self.assertEqual(report.final_label, ComputabilityLabel.C1)

    def test_warns_on_performance_language_without_overblocking_mechanism_question(self) -> None:
        report = ComputationalFeasibilityGatekeeper().audit(
            make_card(title="Can adsorption energetics explain activity trends on Ru-CeO2?")
        )

        self.assertEqual(report.status, GateStatus.WARN)
        self.assertTrue(report.unanswered_by_computation)


class OrchestratorTests(unittest.TestCase):
    def test_passes_minimal_adsorption_question_with_verified_evidence(self) -> None:
        summary = AuditGateOrchestrator(ProtocolRegistry.default()).audit_question(
            make_card(),
            verified_evidence(),
        )

        self.assertEqual(summary.overall_status, GateStatus.PASS)
        self.assertTrue(summary.candidate_for_next_stage)

    def test_blocks_planning_stub_protocols(self) -> None:
        card = make_card(required_protocols=["oxygen_vacancy_formation_protocol"])
        summary = AuditGateOrchestrator(ProtocolRegistry.default()).audit_question(card, verified_evidence())

        self.assertEqual(summary.overall_status, GateStatus.BLOCK)
        self.assertIn("oxygen_vacancy_formation_protocol", summary.protocol_binding.non_executable_protocol_ids)

    def test_blocks_insufficient_evidence(self) -> None:
        card = make_card(evidence_ids=["EVD-1"])
        summary = AuditGateOrchestrator(ProtocolRegistry.default()).audit_question(card, verified_evidence())

        self.assertEqual(summary.overall_status, GateStatus.BLOCK)
        self.assertEqual(summary.gates[0].status, GateStatus.BLOCK)


class AdapterTests(unittest.TestCase):
    def test_imports_existing_question_agent_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "question_cards").mkdir()
            (root / "literature").mkdir()
            (root / "review").mkdir()

            (root / "run_summary.json").write_text(
                json.dumps(
                    {
                        "run_id": "RUN-test",
                        "manual_review_required": ["metadata verification"],
                    }
                ),
                encoding="utf-8",
            )
            (root / "question_cards" / "all_question_cards.json").write_text(
                json.dumps([make_card().model_dump(mode="json")]),
                encoding="utf-8",
            )
            with (root / "literature" / "evidence_table.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "evidence_id",
                        "source_id",
                        "claim_type",
                        "topic",
                        "claim_text",
                        "supporting_excerpt",
                        "requires_human_check",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "evidence_id": "EVD-1",
                        "source_id": "SRC-1",
                        "claim_type": "method",
                        "topic": "adsorption",
                        "claim_text": "claim",
                        "supporting_excerpt": "excerpt",
                        "requires_human_check": "False",
                    }
                )
                writer.writerow(
                    {
                        "evidence_id": "EVD-2",
                        "source_id": "SRC-2",
                        "claim_type": "method",
                        "topic": "adsorption",
                        "claim_text": "claim 2",
                        "supporting_excerpt": "excerpt 2",
                        "requires_human_check": "False",
                    }
                )
            with (root / "literature" / "method_evidence.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "method_evidence_id",
                        "source_id",
                        "linked_evidence_id",
                        "topic",
                        "protocol_hints",
                        "software_hints",
                        "calculation_type",
                        "parameter_hints",
                        "reference_state_hints",
                        "excerpt",
                        "requires_human_check",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "method_evidence_id": "MTH-1",
                        "source_id": "SRC-1",
                        "linked_evidence_id": "EVD-1",
                        "topic": "adsorption",
                        "protocol_hints": '["adsorption_energy_protocol"]',
                        "software_hints": "[]",
                        "calculation_type": "adsorption_energy",
                        "parameter_hints": "[]",
                        "reference_state_hints": '["gas-phase N2"]',
                        "excerpt": "DFT adsorption energy",
                        "requires_human_check": "True",
                    }
                )

            result = QuestionAgentAdapter().import_run(root)

            self.assertEqual(result.run_id, "RUN-test")
            self.assertEqual(len(result.questions), 1)
            self.assertEqual(len(result.evidence), 2)
            self.assertEqual(len(result.method_evidence), 1)
            self.assertEqual(result.candidate_question_ids, ["RQ-test-001"])


if __name__ == "__main__":
    unittest.main()
