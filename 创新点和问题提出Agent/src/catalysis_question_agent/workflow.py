from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config import load_config, manual_review_items, output_base_from_config, project_scope_from_config
from .evidence_builder import EvidenceBuilder
from .insight_ledger import InsightLedger
from .io_utils import model_rows, write_csv, write_json, write_jsonl, write_text
from .llm_client import llm_client_from_config
from .llm_tasks import LLMCallRecord, LLMQuestionIntelligence
from .metadata_enricher import ScholarlyMetadataEnricher
from .models import AgentRunResult, ConsensusClaim, ControversyClaim, EvidenceItem, MethodEvidence, MetadataRecord, ResearchQuestionCard, ReviewDecision, ReviewResult, SimilarWorkCandidate
from .question_generator import QuestionGenerator
from .question_reviewer import QuestionReviewer


class QuestionDiscoveryWorkflow:
    """Sequential MVP workflow for innovation and question discovery."""

    def __init__(self, config_path: str | Path | None = None, config_data: dict | None = None):
        if config_data is not None:
            self.config = config_data
        elif config_path is not None:
            self.config = load_config(config_path)
        else:
            raise ValueError("Either config_path or config_data must be provided.")
        self.scope = project_scope_from_config(self.config)

    def run(self, inputs: list[str | Path] | None = None, output_dir: str | Path | None = None) -> AgentRunResult:
        run_id = self._run_id()
        out_dir = self._output_dir(output_dir, run_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        builder = EvidenceBuilder(self.config)
        sources, evidence, method_evidence, consensus, controversies = builder.run(inputs or [])

        generator = QuestionGenerator(self.config)
        raw_cards = generator.generate(consensus, controversies)

        llm_records: list[LLMCallRecord] = []
        llm_client = llm_client_from_config(self.config)
        if llm_client.enabled:
            intelligence = LLMQuestionIntelligence(llm_client, self.config, self.scope)
            llm_cards, record = intelligence.generate_question_cards(consensus, controversies, raw_cards)
            if record:
                llm_records.append(record)
            if llm_cards:
                raw_cards = self._merge_question_cards(raw_cards, llm_cards)

        reviewer = QuestionReviewer(self.config)
        cards, reviews = reviewer.review(raw_cards)

        if llm_client.enabled:
            intelligence = LLMQuestionIntelligence(llm_client, self.config, self.scope)
            updates, record = intelligence.critique_cards(cards, reviews)
            if record:
                llm_records.append(record)
            if updates:
                self._apply_llm_critiques(cards, reviews, updates)

        metadata_records: list[MetadataRecord] = []
        similar_works: list[SimilarWorkCandidate] = []
        if (self.config.get("metadata_enrichment", {}) or {}).get("enabled", False) or (
            self.config.get("similar_work_search", {}) or {}
        ).get("enabled", False):
            enricher = ScholarlyMetadataEnricher(self.config)
            if (self.config.get("metadata_enrichment", {}) or {}).get("enabled", False):
                metadata_records = enricher.enrich_sources(sources)
            similar_works = enricher.find_similar_works(cards)

        insight_claim_count = 0
        insight_delta_count = 0
        insight_created: list[Path] = []
        ledger = InsightLedger(self.config, out_dir)
        if ledger.enabled:
            insight_state, insight_deltas, insight_created = ledger.update(
                run_id,
                sources,
                evidence,
                consensus,
                controversies,
                cards,
            )
            insight_claim_count = len(insight_state.claims)
            insight_delta_count = len(insight_deltas)

        created = self._write_outputs(
            out_dir,
            sources,
            evidence,
            method_evidence,
            consensus,
            controversies,
            cards,
            reviews,
            metadata_records,
            similar_works,
            llm_records,
        )
        created.extend(insight_created)
        recommended = [card for card in cards if card.status == ReviewDecision.RECOMMEND]

        result = AgentRunResult(
            run_id=run_id,
            project_scope=self.scope,
            source_count=len(sources),
            evidence_count=len(evidence),
            method_evidence_count=len(method_evidence),
            consensus_count=len(consensus),
            controversy_count=len(controversies),
            question_count_raw=len(raw_cards),
            question_count_final=len(cards),
            recommended_count=len(recommended),
            output_dir=str(out_dir.resolve()),
            created_files=[str(path.resolve()) for path in created],
            manual_review_required=manual_review_items(self.config),
            insight_claim_count=insight_claim_count,
            insight_delta_count=insight_delta_count,
        )
        write_json(out_dir / "run_summary.json", result)
        return result

    def _write_outputs(
        self,
        out_dir: Path,
        sources,
        evidence: list[EvidenceItem],
        method_evidence: list[MethodEvidence],
        consensus: list[ConsensusClaim],
        controversies: list[ControversyClaim],
        cards: list[ResearchQuestionCard],
        reviews: list[ReviewResult],
        metadata_records: list[MetadataRecord],
        similar_works: list[SimilarWorkCandidate],
        llm_records: list[LLMCallRecord],
    ) -> list[Path]:
        files = (self.config.get("output", {}) or {}).get("files", {}) or {}
        created: list[Path] = []

        sanitized_sources = [source.model_copy(update={"raw_text": None}) for source in sources]
        created.append(write_jsonl(out_dir / files.get("source_records", "literature/source_records.jsonl"), sanitized_sources))
        created.append(write_csv(out_dir / files.get("literature_matrix", "literature/literature_matrix.csv"), model_rows(sanitized_sources)))
        created.append(write_csv(out_dir / files.get("evidence_table", "literature/evidence_table.csv"), model_rows(evidence)))
        created.append(write_csv(out_dir / files.get("method_evidence", "literature/method_evidence.csv"), model_rows(method_evidence)))
        created.append(write_text(out_dir / files.get("consensus_list", "insight/consensus_list.md"), self._consensus_md(consensus, evidence)))
        created.append(write_text(out_dir / files.get("controversy_list", "insight/controversy_list.md"), self._controversy_md(controversies, evidence)))
        created.append(write_text(out_dir / files.get("open_gap_list", "insight/open_gap_list.md"), self._gap_md(controversies)))
        created.append(write_json(out_dir / files.get("all_question_cards", "question_cards/all_question_cards.json"), cards))
        created.append(write_text(out_dir / files.get("high_priority_cards", "question_cards/high_priority_cards.md"), self._cards_md(cards, reviews, only_recommended=True)))
        created.append(write_text(out_dir / files.get("rejected_cards", "question_cards/rejected_cards.md"), self._cards_md(cards, reviews, only_recommended=False)))
        created.append(write_csv(out_dir / files.get("ranking_table", "review/ranking_table.csv"), model_rows(reviews)))
        created.append(write_text(out_dir / files.get("meta_review", "review/meta_review.md"), self._meta_review_md(cards, reviews)))
        created.append(write_text(out_dir / "review/evidence_gap_report.md", self._evidence_gap_report_md(cards)))
        created.append(write_text(out_dir / "review/gate_audit_report.md", self._gate_audit_report_md(cards, reviews)))
        created.append(write_csv(out_dir / "metadata/enriched_metadata.csv", model_rows(metadata_records)))
        created.append(write_csv(out_dir / "metadata/similar_works.csv", model_rows(similar_works)))
        created.append(write_text(out_dir / "metadata/metadata_enrichment_report.md", self._metadata_report_md(metadata_records, similar_works)))
        created.append(write_json(out_dir / "llm/llm_call_log.json", llm_records))
        return created

    def _output_dir(self, output_dir: str | Path | None, run_id: str) -> Path:
        if output_dir:
            return Path(output_dir)
        return output_base_from_config(self.config) / f"{self.scope.project_id}_{run_id}"

    def _merge_question_cards(
        self,
        rule_cards: list[ResearchQuestionCard],
        llm_cards: list[ResearchQuestionCard],
    ) -> list[ResearchQuestionCard]:
        mode = ((self.config.get("llm", {}) or {}).get("merge_mode") or "prepend").lower()
        if mode == "replace":
            return llm_cards
        if mode == "append":
            return rule_cards + llm_cards
        return llm_cards + rule_cards

    def _apply_llm_critiques(
        self,
        cards: list[ResearchQuestionCard],
        reviews: list[ReviewResult],
        updates: dict[str, dict[str, object]],
    ) -> None:
        review_by_id = {item.question_id: item for item in reviews}
        for card in cards:
            update = updates.get(card.question_id)
            if not update:
                continue
            improved_title = update.get("improved_title")
            if isinstance(improved_title, str) and improved_title.strip():
                card.title = improved_title.strip()
            comments = []
            for key in ("critique_comments", "downstream_checks", "risk_notes"):
                value = update.get(key)
                if isinstance(value, list):
                    comments.extend(str(item) for item in value if str(item).strip())
            if comments:
                card.risks.extend([f"LLM: {comment}" for comment in comments])
                review = review_by_id.get(card.question_id)
                if review:
                    review.review_comments.extend([f"LLM: {comment}" for comment in comments])

    def _run_id(self) -> str:
        return datetime.now().strftime("RUN-%Y%m%d-%H%M%S")

    def _consensus_md(self, claims: list[ConsensusClaim], evidence: list[EvidenceItem]) -> str:
        lookup = {item.evidence_id: item for item in evidence}
        lines = [f"# Consensus Candidates: {self.scope.project_id}", ""]
        if not claims:
            lines.append("No consensus candidates were extracted. Add local literature sources and rerun.")
            return "\n".join(lines) + "\n"
        for claim in claims:
            lines.extend([f"## {claim.consensus_id}: {claim.topic}", "", claim.claim_text, ""])
            lines.append(f"- Evidence strength: `{claim.evidence_strength}`")
            for evidence_id in claim.supporting_evidence_ids[:6]:
                item = lookup.get(evidence_id)
                if item:
                    citation = self._evidence_citation(item)
                    lines.append(f"- `{evidence_id}` from `{item.source_id}` {citation}: {item.supporting_excerpt}")
            lines.append("")
        return "\n".join(lines) + "\n"

    def _controversy_md(self, claims: list[ControversyClaim], evidence: list[EvidenceItem]) -> str:
        lookup = {item.evidence_id: item for item in evidence}
        lines = [f"# Controversy and Gap Candidates: {self.scope.project_id}", ""]
        if not claims:
            lines.append("No controversy/gap candidates were extracted.")
            return "\n".join(lines) + "\n"
        for claim in claims:
            lines.extend([f"## {claim.controversy_id}: {claim.topic}", "", f"- Claim A: {claim.claim_a}"])
            if claim.claim_b:
                lines.append(f"- Claim B: {claim.claim_b}")
            if claim.why_it_matters:
                lines.append(f"- Why it matters: {claim.why_it_matters}")
            for evidence_id in claim.supporting_evidence_a[:6]:
                item = lookup.get(evidence_id)
                if item:
                    citation = self._evidence_citation(item)
                    lines.append(f"- `{evidence_id}` from `{item.source_id}` {citation}: {item.supporting_excerpt}")
            lines.append("")
        return "\n".join(lines) + "\n"

    def _gap_md(self, controversies: list[ControversyClaim]) -> str:
        lines = [f"# Open Gap List: {self.scope.project_id}", ""]
        if not controversies:
            lines.append("No explicit gaps were extracted.")
            return "\n".join(lines) + "\n"
        for claim in controversies:
            lines.append(f"- `{claim.controversy_id}` {claim.topic}: {claim.claim_a}")
        return "\n".join(lines) + "\n"

    def _cards_md(self, cards: list[ResearchQuestionCard], reviews: list[ReviewResult], only_recommended: bool) -> str:
        review_by_id = {item.question_id: item for item in reviews}
        if only_recommended:
            selected = [card for card in cards if card.status == ReviewDecision.RECOMMEND]
            title = "High Priority Question Cards"
        else:
            selected = [card for card in cards if card.status != ReviewDecision.RECOMMEND]
            title = "Non-recommended / Reserved Question Cards"
        lines = [f"# {title}", ""]
        if not selected:
            lines.append("No cards in this category.")
            return "\n".join(lines) + "\n"
        for card in selected:
            review = review_by_id.get(card.question_id)
            lines.extend(
                [
                    f"## {card.question_id}: {card.title}",
                    "",
                    f"- Status: `{card.status}`",
                    f"- Priority score: `{card.priority_score}`",
                    f"- Preliminary computability: `{card.preliminary_computability}`",
                    f"- Evidence count: `{len(card.evidence_ids)}`",
                    f"- Calculation cost: `{card.calculation_cost}`",
                    f"- Literature evidence gate: `{card.literature_evidence_gate}`",
                    f"- Computational verifiability gate: `{card.computational_verifiability_gate}`",
                    f"- Protocol feasibility: `{card.protocol_feasibility}`",
                    f"- AiiDA executability: `{card.aiida_executability}`",
                    f"- Wet-experiment dependency: `{card.wet_experiment_dependency}`",
                    f"- Graduation value: {card.graduation_value}",
                    "",
                    "### Unresolved Gap",
                ]
            )
            lines.extend([f"- {item}" for item in card.unresolved_gap])
            lines.extend(["", "### Required Protocols"])
            lines.extend([f"- `{item}`" for item in card.required_protocols] or ["- None"])
            lines.extend(["", "### Required Reference States"])
            lines.extend([f"- {item}" for item in card.required_reference_states] or ["- None"])
            lines.extend(["", "### Computational Path Hint"])
            lines.extend([f"- {item}" for item in card.computational_path_hint])
            lines.extend(["", "### Minimal Publishable Results"])
            lines.extend([f"- {item}" for item in card.minimal_publishable_results])
            lines.extend(["", "### Expected Audit Risks"])
            lines.extend([f"- {item}" for item in card.expected_audit_risks] or ["- None"])
            if review:
                lines.extend(["", "### Gate Results"])
                for key, passed in review.hard_gate.items():
                    lines.append(f"- `{key}`: `{passed}`")
                lines.extend(["", "### Review Comments"])
                lines.extend([f"- {item}" for item in review.review_comments])
            lines.append("")
        return "\n".join(lines) + "\n"

    def _meta_review_md(self, cards: list[ResearchQuestionCard], reviews: list[ReviewResult]) -> str:
        recommended = [card for card in cards if card.status == ReviewDecision.RECOMMEND]
        reserve = [card for card in cards if card.status == ReviewDecision.RESERVE]
        needs = [card for card in cards if card.status == ReviewDecision.NEEDS_EVIDENCE]
        lines = [
            f"# Meta-review: {self.scope.project_id}",
            "",
            f"- Reaction: {self.scope.reaction}",
            f"- Catalyst family: {self.scope.catalyst_family}",
            f"- Recommended: {len(recommended)}",
            f"- Reserve: {len(reserve)}",
            f"- Needs evidence: {len(needs)}",
            "",
            "## Recommended Next Questions",
            "",
        ]
        if not recommended:
            lines.append("No question passed the high-priority gate. Add verified sources or relax MVP thresholds.")
        for idx, card in enumerate(recommended, start=1):
            lines.append(f"{idx}. `{card.question_id}` {card.title} - score `{card.priority_score}`")
        lines.extend(
            [
                "",
                "## Required Manual Review",
                "",
            ]
        )
        for item in manual_review_items(self.config):
            lines.append(f"- {item}")
        lines.extend(
            [
                "- Replace placeholder recent-duplicate check with real local/online novelty search.",
                "- Verify that extracted evidence supports the corresponding question card.",
            ]
        )
        return "\n".join(lines) + "\n"

    def _evidence_gap_report_md(self, cards: list[ResearchQuestionCard]) -> str:
        lines = ["# Evidence Gap Report", ""]
        weak = [card for card in cards if len(card.evidence_ids) < 2]
        if not weak:
            lines.append("All cards have at least two machine-linked evidence items. Human verification is still required.")
            return "\n".join(lines) + "\n"
        for card in weak:
            lines.append(f"- `{card.question_id}` has {len(card.evidence_ids)} evidence item(s): {card.title}")
        return "\n".join(lines) + "\n"

    def _gate_audit_report_md(self, cards: list[ResearchQuestionCard], reviews: list[ReviewResult]) -> str:
        review_by_id = {item.question_id: item for item in reviews}
        lines = ["# G1-G3 Gate Audit Report", ""]
        lines.extend(
            [
                "| Question | Decision | G1 Evidence | G2 Computability | G3 Protocol | Protocols |",
                "|---|---:|---:|---:|---:|---|",
            ]
        )
        for card in cards:
            review = review_by_id.get(card.question_id)
            gates = review.hard_gate if review else {}
            protocols = ", ".join(card.required_protocols[:6])
            if len(card.required_protocols) > 6:
                protocols += ", ..."
            lines.append(
                "| "
                f"`{card.question_id}` {card.title} | "
                f"`{card.status}` | "
                f"`{gates.get('G1_literature_evidence', False)}` | "
                f"`{gates.get('G2_computational_verifiability', False)}` | "
                f"`{gates.get('G3_protocol_registered', False)}` | "
                f"{protocols or 'None'} |"
            )
        lines.extend(
            [
                "",
                "Notes:",
                "- G1 is only a machine pre-check. DOI/title/journal/year/location still require human verification.",
                "- G2 blocks C0/C1 cards from computation planning; C1 can remain as background or literature-review support.",
                "- G3 means the card has candidate registered protocols; exact settings must still be validated downstream.",
            ]
        )
        return "\n".join(lines) + "\n"

    def _evidence_citation(self, item: EvidenceItem) -> str:
        parts = []
        if item.source_title:
            parts.append(item.source_title)
        if item.source_journal_or_source:
            parts.append(item.source_journal_or_source)
        if item.source_year:
            parts.append(str(item.source_year))
        if item.source_doi:
            parts.append(f"DOI: {item.source_doi}")
        if item.source_location:
            parts.append(item.source_location)
        return f"({' | '.join(parts)})" if parts else ""

    def _metadata_report_md(
        self,
        metadata_records: list[MetadataRecord],
        similar_works: list[SimilarWorkCandidate],
    ) -> str:
        lines = ["# Metadata Enrichment Report", ""]
        if metadata_records:
            resolved = [record for record in metadata_records if record.status == "resolved"]
            lines.extend(
                [
                    "## Source Metadata",
                    "",
                    f"- Queried sources: {len(metadata_records)}",
                    f"- Resolved metadata: {len(resolved)}",
                    "",
                ]
            )
            for record in metadata_records[:30]:
                lines.append(
                    f"- `{record.source_id}` `{record.status}` {record.title or record.query_title}"
                    f" | DOI: `{record.resolved_doi or record.extracted_doi or ''}`"
                    f" | Journal: {record.journal or ''}"
                    f" | Year: {record.year or ''}"
                    f" | API: {record.source_api or ''}"
                    f" | Confidence: {record.confidence}"
                )
        else:
            lines.append("Source metadata enrichment was disabled or returned no records.")

        lines.extend(["", "## Similar Work Candidates", ""])
        if not similar_works:
            lines.append("Similar-work search was disabled or returned no records.")
            return "\n".join(lines) + "\n"
        by_question: dict[str, list[SimilarWorkCandidate]] = {}
        for item in similar_works:
            by_question.setdefault(item.question_id, []).append(item)
        for question_id, items in by_question.items():
            lines.extend([f"### {question_id}", ""])
            for item in items[:10]:
                lines.append(
                    f"- {item.year or ''} {item.title} | {item.journal or ''} | DOI: `{item.doi or ''}`"
                )
            lines.append("")
        return "\n".join(lines) + "\n"
