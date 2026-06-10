from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from .aiida_adapter import AiiDAAdapter
from .audit_gates import (
    claim_gate,
    gate_summary,
    input_gate,
    project_scope_gate,
    question_preplanning_gates,
    result_gate,
    run_gate,
    structure_gate,
)
from .config import load_config, project_scope_from_config
from .io_utils import model_rows, write_csv, write_json, write_text
from .models import EvidenceItem, ResearchQuestionCard
from .protocol_registry import ProtocolRegistry, load_protocol_registry
from .question_agent_adapter import QuestionAgentAdapter
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
        self.registry = load_protocol_registry(self.registry_path)
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
        (
            import_manifest,
            cards,
            imported_questions,
            evidence,
            method_evidence,
            literature_records,
            import_report,
        ) = QuestionAgentAdapter(self.question_output_dir).import_run(project.project_id)

        selected_cards = self._select_cards(cards, imported_questions)
        evidence_rows = {item.evidence_id: item for item in evidence}
        imported_by_id = {item.question_id: item for item in imported_questions}
        gates: list[GateAudit] = [project_scope_gate(self.scope)]
        structures: list[StructureModel] = []
        tasks: list[CalculationTask] = []
        results: list[CalcResult] = []
        claims: list[EvidenceClaim] = []
        protocol_bindings: list[ProtocolBinding] = []

        task_index = 1
        for card in selected_cards:
            imported_question = imported_by_id[card.question_id]
            card_gates = question_preplanning_gates(card, self.registry, min_evidence=self._min_evidence())
            for item in card_gates:
                item.source_files = imported_question.source_files
                item.source_hashes = imported_question.source_hashes
            gates.extend(card_gates)
            known_protocols = list(card_gates[-1].metadata.get("registered_protocols", []))
            input_ready_protocols = list(card_gates[-1].metadata.get("input_ready_protocols", []))
            protocol_block_reasons = dict(card_gates[-1].metadata.get("protocol_block_reasons", {}))

            claims.append(self._literature_claim(card, evidence_rows, import_manifest))
            for protocol_id in known_protocols:
                protocol = self.registry.require(protocol_id)
                can_generate_input = protocol_id in input_ready_protocols
                protocol_bindings.append(
                    ProtocolBinding(
                        binding_id=f"BIND-{card.question_id}-{protocol_id}",
                        project_id=project.project_id,
                        question_id=card.question_id,
                        protocol_id=protocol.protocol_id,
                        protocol_version=protocol.version,
                        protocol_status=protocol.status,
                        can_generate_input=can_generate_input,
                        can_submit_aiida=can_generate_input,
                        block_reasons=list(protocol_block_reasons.get(protocol_id, [])),
                        source_scaffolds=protocol.source_scaffolds,
                        source_files=protocol.source_files + imported_question.source_files,
                        source_hashes={**protocol.source_hashes, **imported_question.source_hashes},
                        audit_status="pass_executable_mvp" if can_generate_input else "blocked_prebind_only",
                    )
                )
            if any(item.status.value == "BLOCK" for item in card_gates[:2]) or not known_protocols:
                continue

            executable_for_card = input_ready_protocols[: self.max_protocols_per_question]
            if not executable_for_card:
                continue

            structure = self._structure_stub(card, executable_for_card[0], import_manifest)
            structures.append(structure)
            gates.append(structure_gate(structure.structure_id, dry_run=True))

            for protocol_id in executable_for_card:
                protocol = self.registry.require(protocol_id)
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
        configured = ((self.config.get("protocol_registry") or {}).get("path") or "protocol_registry/protocols.yaml")
        path = Path(configured)
        if path.is_absolute():
            return path
        return self.config_path.parent / path

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
        cards: list[ResearchQuestionCard],
        imported_questions: list[ImportedQuestionRecord],
    ) -> list[ResearchQuestionCard]:
        candidates = {
            item.question_id
            for item in imported_questions
            if item.candidate_for_protocol_planning
        }
        selected = [card for card in cards if card.question_id in candidates]
        return sorted(selected, key=lambda item: item.priority_score, reverse=True)[: self.max_questions]

    def _structure_stub(self, card: ResearchQuestionCard, protocol_id: str, manifest: RunManifest) -> StructureModel:
        protocol = self.registry.require(protocol_id)
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
            source_files=protocol.source_files + [item.path for item in manifest.source_files if item.exists],
            source_hashes={**protocol.source_hashes, **manifest.source_hashes},
            audit_status="warn_placeholder_only",
            metadata={"question_title": card.title, "catalyst": card.catalyst},
        )

    def _literature_claim(
        self,
        card: ResearchQuestionCard,
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
        card: ResearchQuestionCard,
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
                "protocol_status": protocol.status,
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
        cards: list[ResearchQuestionCard],
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
                    adapter_module="catalysis_question_agent.question_agent_adapter",
                    notes=[
                        f"Imported {import_report.imported_question_count} questions.",
                        f"{import_report.candidate_for_protocol_planning_count} questions are candidates for protocol planning.",
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
                    adapter_module="catalysis_question_agent.audit_gates",
                    notes=["Uses C2/C3 and frontend hard gates now; deeper wet-experiment boundary rules remain to implement."],
                ),
                SelfBuiltAgentConnection(
                    agent_name="Protocol Registry Agent",
                    priority="P0",
                    implemented_in_dry_run=True,
                    input_objects=["ResearchQuestionCard.required_protocols", "protocol_registry/protocols.yaml"],
                    output_objects=["CalcProtocol", "ProtocolBinding", "G3 GateAudit"],
                    gate_ids=["G3"],
                    status="partially_connected",
                    adapter_module="catalysis_question_agent.protocol_registry",
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
