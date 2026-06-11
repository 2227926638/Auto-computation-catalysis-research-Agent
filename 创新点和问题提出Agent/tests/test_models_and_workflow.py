from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from catalysis_question_agent.config import load_config, project_scope_from_config
from catalysis_question_agent.models import ComputabilityLabel, ResearchQuestionCard, SourceCandidate
from catalysis_question_agent.protocol_registry import load_protocol_registry
from catalysis_question_agent.question_agent_adapter import QuestionAgentAdapter
from catalysis_question_agent.research_pipeline import ResearchPipeline
from catalysis_question_agent.signal_ranker import SignalRanker
from catalysis_question_agent.source_harvester import SourceHarvester
from catalysis_question_agent.source_intake import SourceIntakeBuilder
from catalysis_question_agent.source_registry import load_source_registry
from catalysis_question_agent.workflow import QuestionDiscoveryWorkflow


class ModelsAndWorkflowTest(unittest.TestCase):
    def test_question_card_model(self) -> None:
        card = ResearchQuestionCard(
            question_id="RQ-test-001",
            title="Test question",
            reaction="N2 activation",
            catalyst="Ru-CeO2",
            question_type="method_gap",
            preliminary_computability=ComputabilityLabel.C2,
        )
        self.assertEqual(card.preliminary_computability, ComputabilityLabel.C2)

    def test_config_loads(self) -> None:
        config = load_config(ROOT / "05_config_catalysis_question_agent.yaml")
        scope = project_scope_from_config(config)
        self.assertIn("N2", scope.reaction)
        self.assertIn("Ru", scope.catalyst_family)

    def test_protocol_registry_loads(self) -> None:
        registry = load_protocol_registry(ROOT / "protocol_registry" / "protocols.yaml")
        self.assertIn("adsorption_energy_protocol", registry.known_ids())
        protocol = registry.require("slab_model_construction_protocol")
        self.assertIn("pymatgen", protocol.source_scaffolds)
        self.assertTrue(registry.can_generate_input("slab_model_construction_protocol"))
        self.assertFalse(registry.can_generate_input("oxygen_vacancy_formation_protocol"))

    def test_question_agent_adapter_imports_frontend_artifacts(self) -> None:
        config_path = ROOT / "05_config_catalysis_question_agent.yaml"
        input_path = ROOT / "examples" / "toy_sources"
        with tempfile.TemporaryDirectory() as tmp:
            workflow_dir = Path(tmp) / "workflow"
            QuestionDiscoveryWorkflow(config_path).run(inputs=[input_path], output_dir=workflow_dir)
            manifest, cards, imported_questions, evidence, method_evidence, literature, report = (
                QuestionAgentAdapter(workflow_dir).import_run("ru_ceo2_n2_001")
            )
            self.assertGreater(len(cards), 0)
            self.assertGreater(len(evidence), 0)
            self.assertGreater(len(method_evidence), 0)
            self.assertGreater(len(literature), 0)
            self.assertGreater(report.candidate_for_protocol_planning_count, 0)
            self.assertIn("question_cards", manifest.source_hashes)
            self.assertTrue(all(item.human_review_required for item in imported_questions))

    def test_source_registry_loads(self) -> None:
        config = load_config(ROOT / "05_config_catalysis_question_agent.yaml")
        registry = load_source_registry(config)
        ids = {entry.source_id for entry in registry.entries}
        self.assertIn("openalex_catalysis_ru_ceo2", ids)
        self.assertIn("local_pdf_inbox", ids)

    def test_signal_ranker_routes_relevant_open_source(self) -> None:
        config = load_config(ROOT / "05_config_catalysis_question_agent.yaml")
        candidate = SourceCandidate(
            candidate_id="SRC-test",
            registry_source_id="openalex_catalysis_ru_ceo2",
            provider="openalex",
            domain="catalysis",
            tier="S",
            title="Ru-CeO2 oxygen vacancy controls N2 activation in ammonia synthesis",
            year=2025,
            abstract="DFT analysis of ruthenium ceria oxygen vacancy and NHx hydrogenation.",
            cited_by_count=12,
            is_open_access=True,
            open_access_url="https://example.org/paper",
            pdf_url="https://example.org/paper.pdf",
            fulltext_routes=["open_access_pdf"],
        )
        ranked = SignalRanker(config).rank([candidate])
        self.assertEqual(ranked[0].triage_decision, "oa_fulltext_ready")
        self.assertGreaterEqual(ranked[0].relevance_score, 0.2)

    def test_openalex_candidate_mapping(self) -> None:
        config = load_config(ROOT / "05_config_catalysis_question_agent.yaml")
        entry = next(item for item in load_source_registry(config).entries if item.source_id == "openalex_catalysis_ru_ceo2")
        work = {
            "id": "https://openalex.org/W1",
            "doi": "https://doi.org/10.1000/test",
            "title": "Ru supported ceria catalysts for ammonia synthesis",
            "publication_year": 2025,
            "publication_date": "2025-05-01",
            "cited_by_count": 5,
            "abstract_inverted_index": {"Ru": [0], "ceria": [2], "ammonia": [5]},
            "open_access": {"is_oa": True},
            "primary_location": {
                "is_oa": True,
                "pdf_url": "https://example.org/test.pdf",
                "landing_page_url": "https://example.org/test",
                "source": {"display_name": "Example Journal"},
            },
            "authorships": [{"author": {"display_name": "A. Author"}}],
        }
        candidate = SourceHarvester(config_data=config)._openalex_work_to_candidate(entry, work)
        self.assertEqual(candidate.doi, "10.1000/test")
        self.assertEqual(candidate.content_state, "oa_pdf")
        self.assertIn("open_access_pdf", candidate.fulltext_routes)

    def test_source_intake_stubs_feed_workflow(self) -> None:
        config = load_config(ROOT / "05_config_catalysis_question_agent.yaml")
        candidate = SourceCandidate(
            candidate_id="SRC-intake",
            registry_source_id="openalex_catalysis_ru_ceo2",
            provider="openalex",
            domain="catalysis",
            tier="S",
            title="Ru-CeO2 oxygen vacancy controls N2 activation in ammonia synthesis",
            year=2025,
            abstract=(
                "DFT and NEB calculations show that Ru-CeO2 oxygen vacancy sites affect "
                "N2 activation, NHx hydrogenation, Bader charge transfer, and the rate-determining barrier. "
                "The role of hydrogen poisoning remains unclear."
            ),
            cited_by_count=12,
            is_open_access=True,
            open_access_url="https://example.org/paper",
            pdf_url="https://example.org/paper.pdf",
            fulltext_routes=["open_access_pdf"],
            triage_score=0.8,
            relevance_score=0.7,
            triage_decision="oa_fulltext_ready",
            matched_terms=["Ru-CeO2", "oxygen vacancy", "N2 activation", "NHx hydrogenation"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            stub_dir, _created = SourceIntakeBuilder(config).build([candidate], Path(tmp) / "intake")
            result = QuestionDiscoveryWorkflow(config_data=config).run(inputs=[stub_dir], output_dir=Path(tmp) / "workflow")
            self.assertGreater(result.source_count, 0)
            self.assertGreater(result.evidence_count, 0)
            self.assertGreater(result.question_count_final, 0)
            self.assertTrue((Path(tmp) / "workflow" / "question_cards" / "all_question_cards.json").exists())

    def test_workflow_smoke(self) -> None:
        config_path = ROOT / "05_config_catalysis_question_agent.yaml"
        input_path = ROOT / "examples" / "toy_sources"
        with tempfile.TemporaryDirectory() as tmp:
            result = QuestionDiscoveryWorkflow(config_path).run(inputs=[input_path], output_dir=tmp)
            self.assertGreater(result.evidence_count, 0)
            self.assertGreater(result.question_count_final, 0)
            self.assertGreater(result.insight_claim_count, 0)
            self.assertTrue((Path(tmp) / "run_summary.json").exists())
            self.assertTrue((Path(tmp) / "insight" / "insight_delta_report.md").exists())

    def test_research_pipeline_smoke(self) -> None:
        config_path = ROOT / "05_config_catalysis_question_agent.yaml"
        input_path = ROOT / "examples" / "toy_sources"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workflow_dir = tmp_path / "workflow"
            QuestionDiscoveryWorkflow(config_path).run(inputs=[input_path], output_dir=workflow_dir)
            result = ResearchPipeline(
                config_path=config_path,
                question_output_dir=workflow_dir,
                protocol_registry_path=ROOT / "protocol_registry" / "protocols.yaml",
                scaffold_dir=ROOT.parent / "external" / "github_scaffolds",
                max_questions=2,
                max_protocols_per_question=2,
            ).run(output_dir=tmp_path / "pipeline")
            self.assertEqual(result.selected_question_count, 0)
            self.assertEqual(result.task_count, 0)
            self.assertEqual(result.claim_count, 0)
            self.assertTrue((tmp_path / "pipeline" / "audit_gate_report.md").exists())
            self.assertTrue((tmp_path / "pipeline" / "claim_ledger.json").exists())
            self.assertTrue((tmp_path / "pipeline" / "manuscript_skeleton.md").exists())
            self.assertTrue((tmp_path / "pipeline" / "p0_audit_report.md").exists())
            p0 = json.loads((tmp_path / "pipeline" / "p0_audit_summaries.json").read_text(encoding="utf-8"))
            self.assertTrue(any(item["overall_status"] == "BLOCK" for item in p0))
            bindings = json.loads((tmp_path / "pipeline" / "protocol_bindings.json").read_text(encoding="utf-8"))
            self.assertEqual(bindings, [])
            tasks = json.loads((tmp_path / "pipeline" / "calculation_tasks.json").read_text(encoding="utf-8"))
            self.assertEqual(tasks, [])
            self.assertTrue((tmp_path / "pipeline" / "self_built_agent_connection_manifest.json").exists())

    def test_insight_ledger_uses_stable_delta_across_runs(self) -> None:
        config = load_config(ROOT / "05_config_catalysis_question_agent.yaml")
        input_path = ROOT / "examples" / "toy_sources"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config["insight_ledger"] = {
                "enabled": True,
                "ledger_path": str(tmp_path / "persistent_ledger.json"),
                "files": {
                    "snapshot": "insight/insight_ledger_snapshot.json",
                    "delta_json": "insight/insight_delta.json",
                    "delta_report": "insight/insight_delta_report.md",
                },
            }

            first_dir = tmp_path / "run1"
            first = QuestionDiscoveryWorkflow(config_data=config).run(inputs=[input_path], output_dir=first_dir)
            first_delta = json.loads((first_dir / "insight" / "insight_delta.json").read_text(encoding="utf-8"))
            first_types = {item["change_type"] for item in first_delta}

            second_dir = tmp_path / "run2"
            second = QuestionDiscoveryWorkflow(config_data=config).run(inputs=[input_path], output_dir=second_dir)
            second_delta = json.loads((second_dir / "insight" / "insight_delta.json").read_text(encoding="utf-8"))
            second_types = {item["change_type"] for item in second_delta}

            self.assertGreater(first.insight_claim_count, 0)
            self.assertEqual(first.insight_claim_count, second.insight_claim_count)
            self.assertTrue({"new_claim", "new_question"} & first_types)
            self.assertEqual(second_types, {"unchanged"})
            self.assertTrue((tmp_path / "persistent_ledger.json").exists())


if __name__ == "__main__":
    unittest.main()
