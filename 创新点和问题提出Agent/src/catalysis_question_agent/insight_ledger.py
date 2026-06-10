from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

from .config import project_scope_from_config
from .io_utils import write_json, write_text
from .models import (
    ConsensusClaim,
    ControversyClaim,
    EvidenceItem,
    InsightClaim,
    InsightDelta,
    InsightLedgerState,
    ResearchQuestionCard,
    ReviewDecision,
    SourceRecord,
)


class InsightLedger:
    """Persistent insight memory built from each workflow run."""

    def __init__(self, config: dict, output_dir: str | Path):
        self.config = config
        self.scope = project_scope_from_config(config)
        self.output_dir = Path(output_dir)
        self.ledger_config = config.get("insight_ledger", {}) or {}

    @property
    def enabled(self) -> bool:
        return bool(self.ledger_config.get("enabled", True))

    def update(
        self,
        run_id: str,
        sources: list[SourceRecord],
        evidence: list[EvidenceItem],
        consensus: list[ConsensusClaim],
        controversies: list[ControversyClaim],
        cards: list[ResearchQuestionCard],
    ) -> tuple[InsightLedgerState, list[InsightDelta], list[Path]]:
        now = datetime.now().isoformat(timespec="seconds")
        previous = self._load_state()
        previous_by_id = {claim.claim_id: claim for claim in previous.claims}
        source_lookup = {source.source_id: source for source in sources}
        evidence_lookup = {item.evidence_id: item for item in evidence}

        current_claims = self._current_claims(
            run_id,
            now,
            source_lookup,
            evidence_lookup,
            consensus,
            controversies,
            cards,
        )

        merged_claims: dict[str, InsightClaim] = {claim.claim_id: claim for claim in previous.claims}
        deltas: list[InsightDelta] = []
        for current in current_claims:
            previous_claim = previous_by_id.get(current.claim_id)
            if previous_claim is None:
                merged_claims[current.claim_id] = current
                deltas.append(self._new_delta(current))
                continue

            merged = self._merge_claim(previous_claim, current, run_id, now)
            merged_claims[current.claim_id] = merged
            delta = self._delta(previous_claim, merged, current)
            if delta:
                deltas.append(delta)

        state = InsightLedgerState(
            version=1,
            project_id=self.scope.project_id,
            generated_at=previous.generated_at or now,
            updated_at=now,
            claims=sorted(merged_claims.values(), key=lambda item: (item.source_kind, item.topic, item.claim_id)),
        )
        created = self._write_outputs(state, deltas)
        return state, deltas, created

    def _current_claims(
        self,
        run_id: str,
        now: str,
        source_lookup: dict[str, SourceRecord],
        evidence_lookup: dict[str, EvidenceItem],
        consensus: list[ConsensusClaim],
        controversies: list[ControversyClaim],
        cards: list[ResearchQuestionCard],
    ) -> list[InsightClaim]:
        claims: list[InsightClaim] = []

        for item in consensus:
            support = self._stable_evidence_refs(item.supporting_evidence_ids, source_lookup, evidence_lookup)
            opposing = self._stable_evidence_refs(item.opposing_evidence_ids, source_lookup, evidence_lookup)
            claims.append(
                self._claim(
                    source_kind="consensus",
                    topic=item.topic,
                    proposition=item.claim_text,
                    supporting_evidence_ids=support,
                    opposing_evidence_ids=opposing,
                    linked_question_ids=[],
                    controversy_status="consensus_candidate",
                    novelty_implication=(
                        "共识越强，新颖性越依赖于能否提出更细的机制拆解、边界条件或反例。"
                    ),
                    computability_implication=(
                        "若该共识仍缺少吸附、能垒或电子结构闭环，可转化为可计算机制问题。"
                    ),
                    confidence=self._confidence_from_evidence(len(support), len(opposing)),
                    run_id=run_id,
                    now=now,
                    metadata={
                        "origin_id": item.consensus_id,
                        "evidence_strength": item.evidence_strength,
                        "notes": item.notes,
                    },
                    source_record_ids=self._source_record_refs(
                        item.supporting_evidence_ids + item.opposing_evidence_ids,
                        evidence_lookup,
                    ),
                )
            )

        for item in controversies:
            support = self._stable_evidence_refs(item.supporting_evidence_a, source_lookup, evidence_lookup)
            opposing = self._stable_evidence_refs(item.supporting_evidence_b, source_lookup, evidence_lookup)
            proposition = item.claim_a
            if item.claim_b:
                proposition = f"{item.claim_a} / Counter-claim: {item.claim_b}"
            claims.append(
                self._claim(
                    source_kind="controversy",
                    topic=item.topic,
                    proposition=proposition,
                    supporting_evidence_ids=support,
                    opposing_evidence_ids=opposing,
                    linked_question_ids=[],
                    controversy_status="unresolved",
                    novelty_implication="争议或空白越明确，越适合转化为具有发表潜力的机制创新点。",
                    computability_implication=item.why_it_matters
                    or "需要下游计算可验证性 Agent 判断是否存在清晰模型和最小结果集。",
                    confidence=self._confidence_from_evidence(len(support), len(opposing)),
                    run_id=run_id,
                    now=now,
                    metadata={"origin_id": item.controversy_id},
                    source_record_ids=self._source_record_refs(
                        item.supporting_evidence_a + item.supporting_evidence_b,
                        evidence_lookup,
                    ),
                )
            )

        for card in cards:
            if card.status == ReviewDecision.ARCHIVE:
                continue
            support = self._stable_evidence_refs(card.evidence_ids, source_lookup, evidence_lookup)
            topic = str(card.metadata.get("topic") or card.question_type or "research question")
            claims.append(
                self._claim(
                    source_kind="question",
                    topic=topic,
                    proposition=card.title,
                    supporting_evidence_ids=support,
                    opposing_evidence_ids=[],
                    linked_question_ids=[card.question_id],
                    controversy_status=str(card.status),
                    novelty_implication=f"Novelty risk: {card.novelty_risk}.",
                    computability_implication=(
                        f"Computability: {card.preliminary_computability}; "
                        f"cost: {card.calculation_cost}; "
                        f"minimal results: {'; '.join(card.minimal_publishable_results[:3])}"
                    ),
                    confidence=self._confidence_from_evidence(len(support), 0),
                    run_id=run_id,
                    now=now,
                    metadata={
                        "question_type": card.question_type,
                        "priority_score": card.priority_score,
                        "graduation_value": card.graduation_value,
                        "expected_result_types": card.expected_result_types,
                    },
                    source_record_ids=self._source_record_refs(card.evidence_ids, evidence_lookup),
                )
            )

        return self._dedupe_current_claims(claims)

    def _claim(
        self,
        source_kind: str,
        topic: str,
        proposition: str,
        supporting_evidence_ids: list[str],
        opposing_evidence_ids: list[str],
        linked_question_ids: list[str],
        controversy_status: str,
        novelty_implication: str,
        computability_implication: str,
        confidence: float,
        run_id: str,
        now: str,
        metadata: dict[str, object],
        source_record_ids: list[str],
    ) -> InsightClaim:
        claim_id = self._claim_id(source_kind, topic, proposition)
        return InsightClaim(
            claim_id=claim_id,
            source_kind=source_kind,
            topic=topic,
            proposition=proposition,
            supporting_evidence_ids=self._dedupe(supporting_evidence_ids),
            opposing_evidence_ids=self._dedupe(opposing_evidence_ids),
            linked_question_ids=self._dedupe(linked_question_ids),
            source_record_ids=self._dedupe(source_record_ids),
            controversy_status=controversy_status,
            novelty_implication=novelty_implication,
            computability_implication=computability_implication,
            confidence=confidence,
            first_seen_run_id=run_id,
            last_seen_run_id=run_id,
            first_seen_at=now,
            last_updated_at=now,
            update_count=1,
            metadata=metadata,
        )

    def _merge_claim(
        self,
        previous: InsightClaim,
        current: InsightClaim,
        run_id: str,
        now: str,
    ) -> InsightClaim:
        return previous.model_copy(
            update={
                "supporting_evidence_ids": self._dedupe(
                    previous.supporting_evidence_ids + current.supporting_evidence_ids
                ),
                "opposing_evidence_ids": self._dedupe(previous.opposing_evidence_ids + current.opposing_evidence_ids),
                "linked_question_ids": self._dedupe(previous.linked_question_ids + current.linked_question_ids),
                "source_record_ids": self._dedupe(previous.source_record_ids + current.source_record_ids),
                "controversy_status": current.controversy_status,
                "novelty_implication": current.novelty_implication,
                "computability_implication": current.computability_implication,
                "confidence": max(previous.confidence, current.confidence),
                "last_seen_run_id": run_id,
                "last_updated_at": now,
                "update_count": previous.update_count + 1,
                "metadata": {**previous.metadata, **current.metadata},
            }
        )

    def _delta(
        self,
        previous: InsightClaim,
        merged: InsightClaim,
        current: InsightClaim,
    ) -> InsightDelta | None:
        added_support = sorted(set(current.supporting_evidence_ids) - set(previous.supporting_evidence_ids))
        added_opposing = sorted(set(current.opposing_evidence_ids) - set(previous.opposing_evidence_ids))
        added_questions = sorted(set(current.linked_question_ids) - set(previous.linked_question_ids))

        if added_opposing:
            change_type = "challenged"
            summary = f"新增 {len(added_opposing)} 条反向或争议证据，需要复核该认识的边界。"
        elif added_support:
            change_type = "strengthened"
            summary = f"新增 {len(added_support)} 条支持证据，该认识得到增强。"
        elif current.source_kind == "question" and added_questions:
            change_type = "new_question"
            summary = f"同一认识下出现 {len(added_questions)} 个新增问题卡。"
        else:
            change_type = "unchanged"
            summary = "本次运行再次观察到该认识，但未发现新的稳定证据键。"

        return InsightDelta(
            claim_id=merged.claim_id,
            change_type=change_type,
            source_kind=merged.source_kind,
            topic=merged.topic,
            proposition=merged.proposition,
            summary=summary,
            previous_support_count=len(previous.supporting_evidence_ids),
            current_support_count=len(merged.supporting_evidence_ids),
            previous_opposing_count=len(previous.opposing_evidence_ids),
            current_opposing_count=len(merged.opposing_evidence_ids),
            added_supporting_evidence_ids=added_support,
            added_opposing_evidence_ids=added_opposing,
            linked_question_ids=merged.linked_question_ids,
        )

    def _new_delta(self, claim: InsightClaim) -> InsightDelta:
        change_type = "new_question" if claim.source_kind == "question" else "new_claim"
        if claim.source_kind == "consensus":
            summary = "首次进入长期账本的共识候选。"
        elif claim.source_kind == "controversy":
            summary = "首次进入长期账本的争议或空白候选。"
        else:
            summary = "首次进入长期账本的问题卡候选。"
        return InsightDelta(
            claim_id=claim.claim_id,
            change_type=change_type,
            source_kind=claim.source_kind,
            topic=claim.topic,
            proposition=claim.proposition,
            summary=summary,
            previous_support_count=0,
            current_support_count=len(claim.supporting_evidence_ids),
            previous_opposing_count=0,
            current_opposing_count=len(claim.opposing_evidence_ids),
            added_supporting_evidence_ids=claim.supporting_evidence_ids,
            added_opposing_evidence_ids=claim.opposing_evidence_ids,
            linked_question_ids=claim.linked_question_ids,
        )

    def _load_state(self) -> InsightLedgerState:
        path = self._ledger_path()
        if not path.exists():
            return InsightLedgerState(project_id=self.scope.project_id)
        try:
            raw = path.read_text(encoding="utf-8")
            return InsightLedgerState.model_validate_json(raw)
        except Exception:
            return InsightLedgerState(project_id=self.scope.project_id)

    def _write_outputs(self, state: InsightLedgerState, deltas: list[InsightDelta]) -> list[Path]:
        created: list[Path] = []
        created.append(write_json(self._ledger_path(), state))
        created.append(write_json(self.output_dir / self._run_file("snapshot", "insight/insight_ledger_snapshot.json"), state))
        created.append(write_json(self.output_dir / self._run_file("delta_json", "insight/insight_delta.json"), deltas))
        created.append(
            write_text(
                self.output_dir / self._run_file("delta_report", "insight/insight_delta_report.md"),
                self._delta_report_md(state, deltas),
            )
        )
        return created

    def _ledger_path(self) -> Path:
        raw = self.ledger_config.get("ledger_path")
        if raw:
            path = Path(str(raw))
            if not path.is_absolute():
                path = Path(self.config["_config_dir"]) / path
            return path
        return self.output_dir / "insight" / "insight_ledger.json"

    def _run_file(self, key: str, default: str) -> str:
        files = self.ledger_config.get("files", {}) or {}
        return str(files.get(key, default))

    def _delta_report_md(self, state: InsightLedgerState, deltas: list[InsightDelta]) -> str:
        lines = [
            f"# Insight Delta Report: {state.project_id}",
            "",
            f"- Updated at: `{state.updated_at or ''}`",
            f"- Ledger claims: `{len(state.claims)}`",
            f"- Deltas this run: `{len(deltas)}`",
            "",
        ]
        groups = [
            ("New Consensus / Controversy Claims", ["new_claim"]),
            ("Strengthened Claims", ["strengthened"]),
            ("Challenged Claims", ["challenged"]),
            ("New Question Candidates", ["new_question"]),
            ("Reobserved Without Stable Evidence Change", ["unchanged"]),
        ]
        for title, change_types in groups:
            selected = [item for item in deltas if item.change_type in change_types]
            lines.extend([f"## {title}", ""])
            if not selected:
                lines.extend(["No items in this category.", ""])
                continue
            for item in selected[:30]:
                lines.extend(
                    [
                        f"### {item.claim_id}: {item.topic}",
                        "",
                        f"- Type: `{item.source_kind}` / `{item.change_type}`",
                        f"- Proposition: {item.proposition}",
                        f"- Summary: {item.summary}",
                        f"- Support evidence: `{item.previous_support_count}` -> `{item.current_support_count}`",
                        f"- Opposing evidence: `{item.previous_opposing_count}` -> `{item.current_opposing_count}`",
                    ]
                )
                if item.linked_question_ids:
                    lines.append(f"- Linked questions: `{', '.join(item.linked_question_ids[:8])}`")
                if item.added_supporting_evidence_ids:
                    lines.append(f"- Added support keys: `{', '.join(item.added_supporting_evidence_ids[:8])}`")
                if item.added_opposing_evidence_ids:
                    lines.append(f"- Added opposing keys: `{', '.join(item.added_opposing_evidence_ids[:8])}`")
                lines.append("")
        return "\n".join(lines) + "\n"

    def _stable_evidence_refs(
        self,
        evidence_ids: list[str],
        source_lookup: dict[str, SourceRecord],
        evidence_lookup: dict[str, EvidenceItem],
    ) -> list[str]:
        refs: list[str] = []
        for evidence_id in evidence_ids:
            item = evidence_lookup.get(evidence_id)
            if not item:
                refs.append(evidence_id)
                continue
            source = source_lookup.get(item.source_id)
            source_key = self._source_key(source) if source else item.source_id
            excerpt_key = self._normalize(item.supporting_excerpt or item.claim_text)
            refs.append(f"EVK-{self._hash(source_key + '|' + excerpt_key, 12)}")
        return self._dedupe(refs)

    def _source_record_refs(
        self,
        evidence_ids: list[str],
        evidence_lookup: dict[str, EvidenceItem],
    ) -> list[str]:
        return self._dedupe([evidence_lookup[item].source_id for item in evidence_ids if item in evidence_lookup])

    def _source_key(self, source: SourceRecord | None) -> str:
        if not source:
            return ""
        return "|".join(
            part
            for part in [
                source.doi or "",
                source.url or "",
                source.local_path or "",
                source.title or "",
            ]
            if part
        )

    def _claim_id(self, source_kind: str, topic: str, proposition: str) -> str:
        payload = "|".join([self.scope.project_id, source_kind, self._normalize(topic), self._normalize(proposition)])
        return f"CLM-{self._hash(payload, 10)}"

    def _hash(self, text: str, length: int) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length].upper()

    def _normalize(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^a-z0-9\u4e00-\u9fff +/_-]+", "", text)
        return text.strip()

    def _dedupe_current_claims(self, claims: list[InsightClaim]) -> list[InsightClaim]:
        by_id: dict[str, InsightClaim] = {}
        for claim in claims:
            existing = by_id.get(claim.claim_id)
            if not existing:
                by_id[claim.claim_id] = claim
                continue
            by_id[claim.claim_id] = existing.model_copy(
                update={
                    "supporting_evidence_ids": self._dedupe(
                        existing.supporting_evidence_ids + claim.supporting_evidence_ids
                    ),
                    "opposing_evidence_ids": self._dedupe(existing.opposing_evidence_ids + claim.opposing_evidence_ids),
                    "linked_question_ids": self._dedupe(existing.linked_question_ids + claim.linked_question_ids),
                    "source_record_ids": self._dedupe(existing.source_record_ids + claim.source_record_ids),
                    "confidence": max(existing.confidence, claim.confidence),
                }
            )
        return list(by_id.values())

    def _confidence_from_evidence(self, support_count: int, opposing_count: int) -> float:
        score = 0.35 + min(0.45, 0.08 * support_count)
        if opposing_count:
            score -= min(0.2, 0.05 * opposing_count)
        return round(max(0.1, min(0.95, score)), 2)

    def _dedupe(self, values: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not value:
                continue
            if value in seen:
                continue
            seen.add(value)
            out.append(value)
        return out
