from __future__ import annotations

import hashlib
import sys
from datetime import datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from research_agent.adapters.question_agent_adapter import QuestionAgentImportResult
from research_agent.adapters.question_agent_adapter import QuestionAgentAdapter as CoreQuestionAgentAdapter
from research_agent.gates.orchestrator import AuditGateOrchestrator
from research_agent.protocols.registry import ProtocolRegistry as CoreProtocolRegistry
from research_agent.schemas.core import GateStatus as CoreGateStatus
from research_agent.schemas.core import P0AuditSummary, ResearchQuestionCardV2

from .aiida_adapter import AiiDAAdapter
from .audit_gates import (
    claim_gate,
    gate_summary,
    input_gate,
    project_scope_gate,
    result_gate,
    run_gate,
    structure_gate,
)
from .config import load_config, project_scope_from_config
from .io_utils import model_rows, write_csv, write_json, write_text
from .models import EvidenceItem
from .research_pipeline_models import (
    CalcResult,
    CalculationTask,
    ClaimLevel,
    EvidenceClaim,
    GateAudit,
    ImportedQuestionRecord,
    LiteratureRecord,
    PipelineRunResult,
    ProjectRecord,
    ProtocolBinding,
    QuestionImportReport,
    RunManifest,
    SourceFileRecord,
    SelfBuiltAgentConnection,
    SelfBuiltConnectionManifest,
    StructureModel,
)
from .scaffold_registry import inspect_scaffolds


class ResearchPipeline:
    """Connect literature question outputs to a protocol-first research skeleton."""

    def __init__(
        self,
        *,
        config_path: str | Path,
        question_output_dir: str | Path,
        protocol_registry_path: str | Path | None = None,
        scaffold_dir: str | Path | None = None,
        aiida_mode: str = "dry_run",
        max_questions: int = 3,
        max_protocols_per_question: int = 3,
    ):
        self.config_path = Path(config_path)
        self.config = load_config(self.config_path)
        self.scope = project_scope_from_config(self.config)
        self.question_output_dir = Path(question_output_dir)
        self.registry_path = Path(protocol_registry_path) if protocol_registry_path else self._default_registry_path()
        self.registry = CoreProtocolRegistry.from_yaml(self.registry_path)
        self.scaffold_dir = Path(scaffold_dir) if scaffold_dir else self.config_path.parent.parent / "external" / "github_scaffolds"
        if not self.scaffold_dir.exists():
            self.scaffold_dir = self.config_path.parents[1] / "external" / "github_scaffolds"
        self.aiida = AiiDAAdapter(
            mode=aiida_mode,
            aiida_profile=(self.config.get("aiida") or {}).get("profile"),
            computer_label=(self.config.get("aiida") or {}).get("computer_label"),
            code_uuid=(self.config.get("aiida") or {}).get("code_uuid"),
        )
        self.max_questions = max_questions
        self.max_protocols_per_question = max_protocols_per_question

    def run(self, output_dir: str | Path | None = None) -> PipelineRunResult:
        run_id = datetime.now().strftime("PIPE-%Y%m%d-%H%M%S")
        out_dir = Path(output_dir) if output_dir else self.config_path.parent.parent / "pipeline_outputs" / run_id
        out_dir.mkdir(parents=True, exist_ok=True)

        project = self._project_record()
        scaffolds = inspect_scaffolds(self.scaffold_dir)
        imported = CoreQuestionAgentAdapter(min_evidence_per_candidate=self._min_evidence()).import_run(self.question_output_dir)
        p0_summaries = self._p0_summaries(imported)
        import_manifest = self._import_manifest(project.project_id, imported)
        imported_questions = self._imported_questions(project.project_id, imported, p0_summaries)
        evidence = self._frontend_evidence(imported)
        method_evidence = imported.method_evidence
        literature_records: list[LiteratureRecord] = []
        import_report = self._import_report(project.project_id, imported, import_manifest, imported_questions)

        selected_cards = self._select_cards(imported.questions, p0_summaries)
        evidence_rows = {item.evidence_id: item for item in evidence}
        p0_by_id = {item.question_id: item for item in p0_summaries}
        imported_by_id = {item.question_id: item for item in imported_questions}
        gates: list[GateAudit] = [project_scope_gate(self.scope)]
        p0_gate_records = {
            summary.question_id: self._p0_gate_records(summary, imported_by_id[summary.question_id])
            for summary in p0_summaries
            if summary.question_id in imported_by_id
        }
        for records in p0_gate_records.values():
            gates.extend(records)
        structures: list[StructureModel] = []
        tasks: list[CalculationTask] = []
        results: list[CalcResult] = []
        claims: list[EvidenceClaim] = []
        protocol_bindings: list[ProtocolBinding] = []

        task_index = 1
        for card in selected_cards:
            imported_question = imported_by_id[card.question_id]
            summary = p0_by_id[card.question_id]
            known_protocols = list(summary.protocol_binding.bound_protocol_ids)
            input_ready_protocols = list(summary.protocol_binding.executable_protocol_ids)

            claims.append(self._literature_claim(card, evidence_rows, import_manifest))
            for protocol_id in known_protocols:
                protocol = self.registry.get(protocol_id)
                if protocol is None:
                    continue
                can_generate_input = (
                    protocol_id in input_ready_protocols
                    and summary.overall_status != CoreGateStatus.BLOCK
                    and summary.protocol_binding.status != CoreGateStatus.BLOCK
                )
                protocol_bindings.append(
                    ProtocolBinding(
                        binding_id=f"BIND-{card.question_id}-{protocol_id}",
                        project_id=project.project_id,
                        question_id=card.question_id,
                        protocol_id=protocol.protocol_id,
                        protocol_version=protocol.version,
                        protocol_status=protocol.status.value,
                        can_generate_input=can_generate_input,
                        can_submit_aiida=can_generate_input,
                        block_reasons=self._protocol_block_reasons(summary, protocol_id),
                        source_scaffolds=self._protocol_scaffolds(protocol_id),
                        source_files=[str(self.registry_path)] + imported_question.source_files,
                        source_hashes={"protocol_registry": self._file_hash(self.registry_path), **imported_question.source_hashes},
                        audit_status="pass_p0_executable" if can_generate_input else "blocked_by_p0_gate",
                    )
                )
            if summary.overall_status == CoreGateStatus.BLOCK or not known_protocols:
                continue

            executable_for_card = input_ready_protocols[: self.max_protocols_per_question]
            if not executable_for_card:
                continue

            structure = self._structure_stub(card, executable_for_card[0], import_manifest)
            structures.append(structure)
            gates.append(structure_gate(structure.structure_id, dry_run=True))

            for protocol_id in executable_for_card:
                protocol = self.registry.get(protocol_id)
                if protocol is None:
                    continue
                task, result = self.aiida.submit(
                    run_id=run_id,
                    task_index=task_index,
                    card=card,
                    protocol=protocol,
                    structure=structure,
                )
                task_index += 1
                tasks.append(task)
                results.append(result)
                gates.append(input_gate(task.task_id, dry_run=self.aiida.is_dry_run))
                gates.append(run_gate(task.task_id, dry_run=self.aiida.is_dry_run))
                gates.append(result_gate(result.result_id, dry_run=self.aiida.is_dry_run))
                claims.append(self._planned_calculation_claim(card, task, result, protocol_id, protocol))

        claim_gates = [claim_gate(claim) for claim in claims]
        gates.extend(claim_gates)

        created = self._write_outputs(
            out_dir,
            run_id,
            project,
            import_manifest,
            imported_questions,
            evidence,
            method_evidence,
            literature_records,
            import_report,
            p0_summaries,
            selected_cards,
            protocol_bindings,
            structures,
            tasks,
            results,
            claims,
            gates,
            scaffolds,
        )
        result = PipelineRunResult(
            run_id=run_id,
            project=project,
            selected_question_count=len(selected_cards),
            structure_count=len(structures),
            task_count=len(tasks),
            result_count=len(results),
            claim_count=len(claims),
            output_dir=str(out_dir.resolve()),
            created_files=[str(path.resolve()) for path in created],
            gate_summary=gate_summary(gates),
            scaffold_count=sum(1 for item in scaffolds if item.get("present")),
        )
        write_json(out_dir / "pipeline_run_summary.json", result)
        return result

    def _default_registry_path(self) -> Path:
        return _REPO_ROOT / "research_agent" / "protocols" / "core_protocols.yaml"

    def _min_evidence(self) -> int:
        hard_gates = ((self.config.get("review") or {}).get("hard_gates") or {})
        return int(hard_gates.get("min_evidence_per_high_priority_card", 2))

    def _project_record(self) -> ProjectRecord:
        return ProjectRecord(
            project_id=self.scope.project_id,
            title=f"{self.scope.catalyst_family} {self.scope.reaction} auditable research pipeline",
            reaction=self.scope.reaction,
            catalyst_family=self.scope.catalyst_family,
            graduation_target=self.scope.graduation_target,
            aiida_profile=(self.config.get("aiida") or {}).get("profile"),
        )

    def _select_cards(
        self,
        cards: list[ResearchQuestionCardV2],
        p0_summaries: list[P0AuditSummary],
    ) -> list[ResearchQuestionCardV2]:
        candidates = {
            item.question_id
            for item in p0_summaries
            if item.overall_status != CoreGateStatus.BLOCK
        }
        selected = [card for card in cards if card.question_id in candidates]
        return sorted(selected, key=lambda item: item.priority_score, reverse=True)[: self.max_questions]

    def _p0_summaries(self, imported: QuestionAgentImportResult) -> list[P0AuditSummary]:
        orchestrator = AuditGateOrchestrator(self.registry, min_evidence=self._min_evidence())
        return [orchestrator.audit_question(card, imported.evidence) for card in imported.questions]

    def _import_manifest(self, project_id: str, imported: QuestionAgentImportResult) -> RunManifest:
        source_files = [
            SourceFileRecord(
                role=Path(item.path).name,
                path=item.path,
                exists=True,
                sha256=item.sha256,
                size_bytes=item.bytes,
            )
            for item in imported.imported_files
        ]
        return RunManifest(
            import_id=f"QIMPORT-{imported.run_id}",
            project_id=project_id,
            frontend_run_id=imported.run_id,
            frontend_output_dir=imported.source_dir,
            source_files=source_files,
            source_hashes={Path(item.path).name: item.sha256 for item in imported.imported_files},
            audit_status="imported_by_research_agent_p0",
        )

    def _imported_questions(
        self,
        project_id: str,
        imported: QuestionAgentImportResult,
        p0_summaries: list[P0AuditSummary],
    ) -> list[ImportedQuestionRecord]:
        p0_by_id = {item.question_id: item for item in p0_summaries}
        source_files = [item.path for item in imported.imported_files]
        source_hashes = {Path(item.path).name: item.sha256 for item in imported.imported_files}
        records: list[ImportedQuestionRecord] = []
        for card in imported.questions:
            summary = p0_by_id[card.question_id]
            block_reasons = [
                reason
                for gate in summary.gates
                if gate.status == CoreGateStatus.BLOCK
                for reason in gate.reasons
            ]
            records.append(
                ImportedQuestionRecord(
                    question_id=card.question_id,
                    project_id=project_id,
                    title=card.title,
                    preliminary_computability=card.preliminary_computability.value,
                    frontend_decision=card.status,
                    candidate_for_protocol_planning=summary.overall_status != CoreGateStatus.BLOCK,
                    block_reasons=block_reasons,
                    required_protocols=card.required_protocols,
                    evidence_ids=card.evidence_ids,
                    source_files=source_files,
                    source_hashes=source_hashes,
                    audit_status=f"p0_{summary.overall_status.value.lower()}",
                    metadata={
                        "p0_overall_status": summary.overall_status.value,
                        "frontend_adapter_candidate": card.question_id in imported.candidate_question_ids,
                    },
                )
            )
        return records

    def _frontend_evidence(self, imported: QuestionAgentImportResult) -> list[EvidenceItem]:
        out: list[EvidenceItem] = []
        for item in imported.evidence:
            out.append(
                EvidenceItem(
                    evidence_id=item.evidence_id,
                    source_id=item.source_id or "",
                    claim_type=item.claim_type,
                    topic=item.topic,
                    claim_text=item.claim_text,
                    supporting_excerpt=item.supporting_excerpt or "",
                    source_doi=item.source_doi,
                    source_title=item.source_title,
                    source_journal_or_source=item.source_journal_or_source,
                    source_year=item.source_year,
                    source_location=item.source_location,
                    confidence=item.confidence,
                    requires_human_check=item.requires_human_check,
                    keywords=item.keywords,
                )
            )
        return out

    def _import_report(
        self,
        project_id: str,
        imported: QuestionAgentImportResult,
        manifest: RunManifest,
        imported_questions: list[ImportedQuestionRecord],
    ) -> QuestionImportReport:
        return QuestionImportReport(
            import_id=manifest.import_id,
            project_id=project_id,
            frontend_run_id=imported.run_id,
            imported_question_count=len(imported.questions),
            candidate_for_protocol_planning_count=sum(
                1 for item in imported_questions if item.candidate_for_protocol_planning
            ),
            imported_evidence_count=len(imported.evidence),
            imported_method_evidence_count=len(imported.method_evidence),
            imported_literature_count=0,
            source_files=manifest.source_files,
            warnings=list(imported.manual_review_required),
            audit_status="research_agent_p0_integrated",
        )

    def _p0_gate_records(
        self,
        summary: P0AuditSummary,
        imported_question: ImportedQuestionRecord,
    ) -> list[GateAudit]:
        records: list[GateAudit] = []
        for item in summary.gates:
            gate_id = item.gate.value.split("_", 1)[0]
            records.append(
                GateAudit(
                    gate_id=gate_id,
                    name=item.gate.value,
                    subject_id=item.target_id,
                    status=item.status.value,
                    reason="; ".join(item.reasons) if item.reasons else item.next_action,
                    evidence_links=item.evidence_links,
                    human_review_required=item.human_review_required,
                    next_action=item.next_action,
                    source_files=imported_question.source_files,
                    source_hashes=imported_question.source_hashes,
                    metadata={"source": "research_agent.p0", "target_type": item.target_type},
                )
            )
        return records

    def _protocol_block_reasons(self, summary: P0AuditSummary, protocol_id: str) -> list[str]:
        reasons: list[str] = []
        for report in summary.protocol_binding.reports:
            if report.protocol_id != protocol_id:
                continue
            reasons.extend(report.blocking_findings)
            reasons.extend(report.warnings)
        if protocol_id in summary.protocol_binding.executable_protocol_ids and summary.protocol_binding.status == CoreGateStatus.BLOCK:
            reasons.append("question_g3_blocked_by_other_required_non_executable_protocols")
        if protocol_id in summary.protocol_binding.missing_protocol_ids:
            reasons.append("protocol_missing_from_registry")
        return reasons

    def _protocol_scaffolds(self, protocol_id: str) -> list[str]:
        mapping = {
            "slab_model_construction_protocol": ["pymatgen", "ASE", "atomate2"],
            "adsorption_energy_protocol": ["AiiDA", "pymatgen", "ASE"],
            "oxygen_vacancy_formation_protocol": ["pymatgen", "custodian"],
            "reaction_energy_path_protocol": ["AiiDA", "pandas"],
            "neb_barrier_protocol": ["AiiDA", "aiida-vasp", "aiida-quantumespresso"],
            "bader_charge_protocol": ["custodian", "AiiDA"],
            "pdos_analysis_protocol": ["pymatgen", "AiiDA"],
            "adsorbate_configuration_screening_protocol": ["pymatgen", "ASE", "MatGL", "CHGNet"],
            "microkinetic_model_protocol": ["jobflow", "scipy"],
        }
        return mapping.get(protocol_id, [])

    def _file_hash(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _structure_stub(self, card: ResearchQuestionCardV2, protocol_id: str, manifest: RunManifest) -> StructureModel:
        protocol = self.registry.get(protocol_id)
        if protocol is None:
            raise KeyError(f"Unknown protocol_id: {protocol_id}")
        digest = hashlib.sha256(
            f"{card.question_id}|{card.catalyst}|{','.join(card.required_protocols)}".encode("utf-8")
        ).hexdigest()
        defects = []
        text = " ".join([card.title] + card.required_protocols + card.expected_audit_risks).lower()
        if "vacancy" in text:
            defects.append("oxygen_vacancy_candidate")
        adsorbates = [item for item in ["N2", "N", "NH", "NH2", "NH3", "H"] if item.lower() in text]
        return StructureModel(
            structure_id=f"STRUCT-{card.question_id}",
            question_id=card.question_id,
            source="generated_from_question_card_stub",
            protocol_id=protocol.protocol_id,
            protocol_version=protocol.version,
            ase_hash=digest[:16],
            pymatgen_hash=digest[16:32],
            adsorbates=adsorbates,
            defects=defects,
            source_files=[str(self.registry_path)] + [item.path for item in manifest.source_files if item.exists],
            source_hashes={"protocol_registry": self._file_hash(self.registry_path), **manifest.source_hashes},
            audit_status="warn_placeholder_only",
            metadata={"question_title": card.title, "catalyst": card.catalyst},
        )

    def _literature_claim(
        self,
        card: ResearchQuestionCardV2,
        evidence_rows: dict[str, EvidenceItem],
        manifest: RunManifest,
    ) -> EvidenceClaim:
        available = [evidence_id for evidence_id in card.evidence_ids if evidence_id in evidence_rows]
        return EvidenceClaim(
            claim_id=f"CLAIM-LIT-{card.question_id}",
            claim_text=f"Literature motivates the computable question: {card.title}",
            level=ClaimLevel.L1 if available else ClaimLevel.L0,
            claim_type="literature_background",
            literature_evidence_ids=available or card.evidence_ids,
            allowed_sections=["introduction", "background"] if available else [],
            risk_level="medium" if available else "high",
            audit_status="literature_metadata_needs_human_check",
            provenance_links=available or card.evidence_ids,
            human_review_required=True,
            source_files=[item.path for item in manifest.source_files if item.exists],
            source_hashes=manifest.source_hashes,
            metadata={"question_id": card.question_id},
        )

    def _planned_calculation_claim(
        self,
        card: ResearchQuestionCardV2,
        task: CalculationTask,
        result: CalcResult,
        protocol_id: str,
        protocol,
    ) -> EvidenceClaim:
        return EvidenceClaim(
            claim_id=f"CLAIM-PLAN-{task.task_id}",
            claim_text=f"Planned {protocol_id} calculation for: {card.title}",
            level=ClaimLevel.L0,
            claim_type="planned_calculation_not_evidence",
            calculation_result_ids=[result.result_id],
            risk_level="high",
            audit_status="blocked_until_real_aiida_result",
            provenance_links=[task.task_id, result.result_id, result.aiida_node_uuid or ""],
            human_review_required=True,
            source_files=task.source_files,
            source_hashes=task.source_hashes,
            metadata={
                "question_id": card.question_id,
                "protocol_id": protocol_id,
                "protocol_version": protocol.version,
                "protocol_status": protocol.status.value if hasattr(protocol.status, "value") else str(protocol.status),
            },
        )

    def _write_outputs(
        self,
        out_dir: Path,
        run_id: str,
        project: ProjectRecord,
        import_manifest: RunManifest,
        imported_questions: list[ImportedQuestionRecord],
        evidence: list[EvidenceItem],
        method_evidence,
        literature_records: list[LiteratureRecord],
        import_report: QuestionImportReport,
        p0_summaries: list[P0AuditSummary],
        cards: list[ResearchQuestionCardV2],
        protocol_bindings: list[ProtocolBinding],
        structures: list[StructureModel],
        tasks: list[CalculationTask],
        results: list[CalcResult],
        claims: list[EvidenceClaim],
        gates: list[GateAudit],
        scaffolds: list[dict[str, object]],
    ) -> list[Path]:
        created: list[Path] = []
        created.append(write_json(out_dir / "project.json", project))
        created.append(write_json(out_dir / "question_agent_import_manifest.json", import_manifest))
        created.append(write_json(out_dir / "question_import_report.json", import_report))
        created.append(write_json(out_dir / "p0_audit_summaries.json", p0_summaries))
        created.append(write_json(out_dir / "imported_question_records.json", imported_questions))
        created.append(write_json(out_dir / "imported_literature_records.json", literature_records))
        created.append(write_json(out_dir / "imported_evidence_items.json", evidence))
        created.append(write_json(out_dir / "imported_method_evidence.json", method_evidence))
        created.append(write_json(out_dir / "selected_question_cards.json", cards))
        created.append(write_json(out_dir / "protocol_bindings.json", protocol_bindings))
        created.append(write_csv(out_dir / "protocol_binding_table.csv", model_rows(protocol_bindings)))
        created.append(write_json(out_dir / "structure_models.json", structures))
        created.append(write_json(out_dir / "calculation_tasks.json", tasks))
        created.append(write_json(out_dir / "calc_results.json", results))
        created.append(write_json(out_dir / "claim_ledger.json", claims))
        created.append(write_csv(out_dir / "claim_ledger.csv", model_rows(claims)))
        created.append(write_json(out_dir / "audit_gates.json", gates))
        created.append(write_csv(out_dir / "audit_gates.csv", model_rows(gates)))
        created.append(write_text(out_dir / "audit_gate_report.md", self._gate_report_md(gates)))
        created.append(write_text(out_dir / "p0_audit_report.md", self._p0_report_md(p0_summaries)))
        created.append(write_text(out_dir / "claim_ledger_report.md", self._claim_report_md(claims)))
        created.append(write_text(out_dir / "manuscript_skeleton.md", self._manuscript_skeleton(project, claims, gates)))
        created.append(write_json(out_dir / "scaffold_manifest.json", scaffolds))
        connection_manifest = self._connection_manifest(run_id, project, import_report, protocol_bindings, structures, tasks, results, claims)
        created.append(write_json(out_dir / "self_built_agent_connection_manifest.json", connection_manifest))
        created.append(write_text(out_dir / "self_built_agent_connection_report.md", self._connection_report_md(connection_manifest)))
        created.append(write_text(out_dir / "pipeline_manifest.md", self._pipeline_manifest_md(run_id, project, scaffolds)))
        return created

    def _gate_report_md(self, gates: list[GateAudit]) -> str:
        lines = ["# Audit Gate Report", ""]
        lines.extend(["| Gate | Subject | Status | Reason | Next action |", "|---|---|---:|---|---|"])
        for item in gates:
            lines.append(
                f"| {item.gate_id} {item.name} | `{item.subject_id}` | `{item.status}` | "
                f"{item.reason} | {item.next_action} |"
            )
        return "\n".join(lines) + "\n"

    def _p0_report_md(self, summaries: list[P0AuditSummary]) -> str:
        lines = ["# P0 Scientific Gate Report", ""]
        lines.append("This report is generated by the top-level `research_agent` package. Downstream dry-run stages may only continue for questions whose P0 status is not `BLOCK`.")
        lines.extend(["", "| Question | Overall | G1 | G2 | G3 | Next action |", "|---|---:|---:|---:|---:|---|"])
        for summary in summaries:
            gate_status = {item.gate.value.split("_", 1)[0]: item.status.value for item in summary.gates}
            lines.append(
                f"| `{summary.question_id}` | `{summary.overall_status.value}` | "
                f"`{gate_status.get('G1', '')}` | `{gate_status.get('G2', '')}` | `{gate_status.get('G3', '')}` | "
                f"{summary.protocol_binding.next_action} |"
            )
        blocked = [item for item in summaries if item.overall_status == CoreGateStatus.BLOCK]
        if blocked:
            lines.extend(["", "## Blocking Details", ""])
            for summary in blocked[:20]:
                reasons = [
                    reason
                    for gate in summary.gates
                    if gate.status == CoreGateStatus.BLOCK
                    for reason in gate.reasons
                ]
                lines.append(f"### {summary.question_id}")
                if not reasons:
                    lines.append("- BLOCK without detailed reasons; inspect JSON summary.")
                else:
                    lines.extend([f"- {reason}" for reason in reasons[:12]])
                lines.append("")
        return "\n".join(lines) + "\n"

    def _connection_manifest(
        self,
        run_id: str,
        project: ProjectRecord,
        import_report: QuestionImportReport,
        protocol_bindings: list[ProtocolBinding],
        structures: list[StructureModel],
        tasks: list[CalculationTask],
        results: list[CalcResult],
        claims: list[EvidenceClaim],
    ) -> SelfBuiltConnectionManifest:
        executable_bindings = [item for item in protocol_bindings if item.can_generate_input]
        blocked_bindings = [item for item in protocol_bindings if not item.can_generate_input]
        return SelfBuiltConnectionManifest(
            project_id=project.project_id,
            run_id=run_id,
            blocking_rules=[
                "Only QuestionAgentAdapter records marked candidate_for_protocol_planning may enter protocol planning.",
                "planning_stub protocols may be pre-bound but cannot generate input or AiiDA tasks.",
                "G4 WARN/BLOCK structure placeholders cannot support final calculation claims.",
                "Dry-run AiiDA results are L0 and blocked by G7/G9 until replaced by real AiiDA provenance.",
                "Manuscript skeleton reads only claim ledger entries and keeps calculation plans out of results text.",
            ],
            connections=[
                SelfBuiltAgentConnection(
                    agent_name="QuestionAgentAdapter",
                    priority="P0",
                    implemented_in_dry_run=True,
                    input_objects=["frontend question-agent output directory"],
                    output_objects=["RunManifest", "LiteratureRecord", "EvidenceClaim", "MethodEvidence", "ImportedQuestionRecord", "QuestionImportReport"],
                    gate_ids=["G1", "G2", "G3"],
                    status="connected",
                    adapter_module="research_agent.adapters.question_agent_adapter",
                    notes=[
                        f"Imported {import_report.imported_question_count} questions.",
                        f"{import_report.candidate_for_protocol_planning_count} questions are P0 non-BLOCK candidates for protocol planning.",
                    ],
                ),
                SelfBuiltAgentConnection(
                    agent_name="Computational Feasibility Gatekeeper",
                    priority="P0",
                    implemented_in_dry_run=True,
                    input_objects=["ImportedQuestionRecord", "ResearchQuestionCard"],
                    output_objects=["G2 GateAudit", "claim boundary placeholder"],
                    gate_ids=["G2"],
                    status="connected_prefilter_only",
                    adapter_module="research_agent.gates.feasibility",
                    notes=["Uses the top-level ComputationalFeasibilityGatekeeper; deeper domain-specific wet-experiment rules can still be expanded."],
                ),
                SelfBuiltAgentConnection(
                    agent_name="Protocol Registry Agent",
                    priority="P0",
                    implemented_in_dry_run=True,
                    input_objects=["ResearchQuestionCard.required_protocols", "protocol_registry/protocols.yaml"],
                    output_objects=["CalcProtocol", "ProtocolBinding", "G3 GateAudit"],
                    gate_ids=["G3"],
                    status="partially_connected",
                    adapter_module="research_agent.protocols.registry",
                    notes=[
                        f"{len(executable_bindings)} executable protocol binding(s).",
                        f"{len(blocked_bindings)} prebind-only or incomplete binding(s).",
                    ],
                ),
                SelfBuiltAgentConnection(
                    agent_name="Structure Model/Audit Agent",
                    priority="P1",
                    implemented_in_dry_run=True,
                    input_objects=["ProtocolBinding(can_generate_input=true)", "ResearchQuestionCard"],
                    output_objects=["StructureModel", "G4 GateAudit"],
                    gate_ids=["G4"],
                    status="placeholder_connected",
                    adapter_module="catalysis_question_agent.research_pipeline",
                    notes=[f"{len(structures)} placeholder structure model(s); pymatgen/ASE generation is not implemented yet."],
                ),
                SelfBuiltAgentConnection(
                    agent_name="Input Builder/Audit Agent",
                    priority="P1",
                    implemented_in_dry_run=True,
                    input_objects=["CalcProtocol", "StructureModel"],
                    output_objects=["CalculationTask", "G5 GateAudit"],
                    gate_ids=["G5"],
                    status="dry_run_connected",
                    adapter_module="catalysis_question_agent.aiida_adapter",
                    notes=[f"{len(tasks)} task(s) generated only for executable protocol bindings."],
                ),
                SelfBuiltAgentConnection(
                    agent_name="AiiDA Provenance/Execution Agent",
                    priority="P1/P2",
                    implemented_in_dry_run=True,
                    input_objects=["CalculationTask"],
                    output_objects=["CalcResult(dry_run)", "G6 GateAudit"],
                    gate_ids=["G6"],
                    status="dry_run_uuid_only",
                    adapter_module="catalysis_question_agent.aiida_adapter",
                    notes=["Real AiiDA is not installed/configured in this environment; UUIDs are simulation markers."],
                ),
                SelfBuiltAgentConnection(
                    agent_name="Result Parser/Audit/Reference State Agent",
                    priority="P2",
                    implemented_in_dry_run=True,
                    input_objects=["CalcResult(dry_run)", "CalcProtocol"],
                    output_objects=["G7 GateAudit"],
                    gate_ids=["G7"],
                    status="blocking_stub",
                    adapter_module="catalysis_question_agent.audit_gates",
                    notes=[f"{len(results)} dry-run result(s) are intentionally BLOCKED by G7."],
                ),
                SelfBuiltAgentConnection(
                    agent_name="Claim Ledger/Manuscript Claim Audit Agent",
                    priority="P3",
                    implemented_in_dry_run=True,
                    input_objects=["EvidenceClaim", "CalcResult", "GateAudit"],
                    output_objects=["ClaimLedger", "Manuscript skeleton"],
                    gate_ids=["G9"],
                    status="connected_with_l0_blocks",
                    adapter_module="catalysis_question_agent.research_pipeline",
                    notes=[f"{len(claims)} claim(s) written; dry-run calculation claims remain L0."],
                ),
            ],
        )

    def _connection_report_md(self, manifest: SelfBuiltConnectionManifest) -> str:
        lines = ["# Self-built Agent Connection Report", ""]
        lines.extend(["## Blocking Rules", ""])
        lines.extend([f"- {item}" for item in manifest.blocking_rules])
        lines.extend(["", "## Connections", ""])
        lines.extend(["| Agent | Priority | Status | Gates | Outputs | Notes |", "|---|---|---|---|---|---|"])
        for item in manifest.connections:
            lines.append(
                f"| {item.agent_name} | {item.priority} | `{item.status}` | "
                f"{', '.join(item.gate_ids)} | {', '.join(item.output_objects)} | {'; '.join(item.notes)} |"
            )
        return "\n".join(lines) + "\n"

    def _claim_report_md(self, claims: list[EvidenceClaim]) -> str:
        lines = ["# Claim Ledger", ""]
        lines.extend(["| Claim | Level | Type | Audit | Allowed sections |", "|---|---:|---|---|---|"])
        for claim in claims:
            sections = ", ".join(claim.allowed_sections) or "none"
            lines.append(
                f"| `{claim.claim_id}` {claim.claim_text} | `{claim.level}` | "
                f"{claim.claim_type} | {claim.audit_status} | {sections} |"
            )
        return "\n".join(lines) + "\n"

    def _manuscript_skeleton(
        self,
        project: ProjectRecord,
        claims: list[EvidenceClaim],
        gates: list[GateAudit],
    ) -> str:
        background = [claim for claim in claims if claim.level == ClaimLevel.L1]
        blocked = [claim for claim in claims if claim.level == ClaimLevel.L0]
        gate_counts = gate_summary(gates)
        lines = [
            f"# Manuscript Skeleton: {project.title}",
            "",
            "## Scope",
            "",
            f"- Reaction: {project.reaction}",
            f"- Catalyst family: {project.catalyst_family}",
            f"- Graduation target: {project.graduation_target or 'not specified'}",
            "",
            "## Claim-Ledger-Allowed Background",
            "",
        ]
        if not background:
            lines.append("No L1+ background claims are available yet.")
        for claim in background:
            links = ", ".join(f"`{item}`" for item in claim.literature_evidence_ids)
            lines.append(f"- `{claim.claim_id}` {claim.claim_text} Evidence: {links}")
        lines.extend(
            [
                "",
                "## Results Placeholder",
                "",
                "No calculation-backed result claim is allowed yet. Dry-run AiiDA tasks must be replaced by real AiiDA CalcJob/WorkChain results and pass G6-G7 before result text is generated.",
                "",
                "## Blocked Claims",
                "",
            ]
        )
        for claim in blocked:
            lines.append(f"- `{claim.claim_id}` {claim.claim_text} ({claim.audit_status})")
        lines.extend(
            [
                "",
                "## Audit Summary",
                "",
                f"- PASS: {gate_counts.get('PASS', 0)}",
                f"- WARN: {gate_counts.get('WARN', 0)}",
                f"- BLOCK: {gate_counts.get('BLOCK', 0)}",
            ]
        )
        return "\n".join(lines) + "\n"

    def _pipeline_manifest_md(
        self,
        run_id: str,
        project: ProjectRecord,
        scaffolds: list[dict[str, object]],
    ) -> str:
        lines = [
            "# Research Pipeline Manifest",
            "",
            f"- Run id: `{run_id}`",
            f"- Project: `{project.project_id}`",
            f"- Protocol registry: `{self.registry_path}`",
            f"- Question output dir: `{self.question_output_dir}`",
            f"- AiiDA mode: `{self.aiida.mode}`",
            f"- AiiDA importable: `{self.aiida.aiida_importable}`",
            "",
            "## External Scaffolds",
            "",
            "| Project | Phase | Present | HEAD | Role |",
            "|---|---|---:|---|---|",
        ]
        for item in scaffolds:
            lines.append(
                f"| {item['name']} | {item['phase']} | `{item['present']}` | "
                f"`{item.get('head') or ''}` | {item['role']} |"
            )
        return "\n".join(lines) + "\n"
