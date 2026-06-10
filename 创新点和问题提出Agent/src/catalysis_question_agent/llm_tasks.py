from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .llm_client import DeepSeekChatClient, LLMError
from .models import (
    ComputabilityLabel,
    ConsensusClaim,
    ControversyClaim,
    ProjectScope,
    ResearchQuestionCard,
    ReviewResult,
)


class LLMCallRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    task: str
    status: str
    model: str | None = None
    prompt_summary: str
    usage: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    output_preview: str | None = None


class LLMQuestionIntelligence:
    """LLM adapters for question generation and critique."""

    def __init__(self, client: DeepSeekChatClient, config: dict[str, Any], scope: ProjectScope):
        self.client = client
        self.config = config
        self.scope = scope
        self.llm_config = config.get("llm", {}) or {}
        self.tasks = self.llm_config.get("tasks", {}) or {}

    def generate_question_cards(
        self,
        consensus: list[ConsensusClaim],
        controversies: list[ControversyClaim],
        seed_cards: list[ResearchQuestionCard],
    ) -> tuple[list[ResearchQuestionCard], LLMCallRecord | None]:
        task_config = self.tasks.get("generate_question_cards", {}) or {}
        if not self.client.enabled or not task_config.get("enabled", False):
            return [], None

        target_count = int(task_config.get("target_count", min(24, len(seed_cards) or 20)))
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an AI4Catalysis research-question discovery agent. "
                    "Return only valid JSON. Do not invent citations or DOI. "
                    "Generate concrete, computation-oriented catalysis research questions."
                ),
            },
            {
                "role": "user",
                "content": self._generation_prompt(consensus, controversies, seed_cards, target_count),
            },
        ]
        try:
            data = self.client.chat_json(messages, max_tokens=int(task_config.get("max_tokens", 5000)))
            cards = self._parse_generated_cards(data, seed_cards, target_count)
            return cards, LLMCallRecord(
                task="generate_question_cards",
                status="ok",
                model=self.client.settings.model,
                prompt_summary=f"Generated up to {target_count} LLM question cards.",
                output_preview=json.dumps(data, ensure_ascii=False)[:1200],
            )
        except Exception as exc:
            return [], LLMCallRecord(
                task="generate_question_cards",
                status="error",
                model=self.client.settings.model,
                prompt_summary=f"Attempted to generate up to {target_count} LLM question cards.",
                error=str(exc),
            )

    def critique_cards(
        self,
        cards: list[ResearchQuestionCard],
        reviews: list[ReviewResult],
    ) -> tuple[dict[str, dict[str, Any]], LLMCallRecord | None]:
        task_config = self.tasks.get("critique_cards", {}) or {}
        if not self.client.enabled or not task_config.get("enabled", False):
            return {}, None

        top_n = int(task_config.get("top_n", 8))
        selected = sorted(cards, key=lambda card: card.priority_score, reverse=True)[:top_n]
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a skeptical computational catalysis reviewer. "
                    "Return only valid JSON. Do not invent papers. "
                    "Critique whether each question is specific, computable, and publishable."
                ),
            },
            {
                "role": "user",
                "content": self._critique_prompt(selected, reviews),
            },
        ]
        try:
            data = self.client.chat_json(messages, max_tokens=int(task_config.get("max_tokens", 3500)))
            updates = self._parse_critiques(data)
            return updates, LLMCallRecord(
                task="critique_cards",
                status="ok",
                model=self.client.settings.model,
                prompt_summary=f"Critiqued top {len(selected)} question cards.",
                output_preview=json.dumps(data, ensure_ascii=False)[:1200],
            )
        except Exception as exc:
            return {}, LLMCallRecord(
                task="critique_cards",
                status="error",
                model=self.client.settings.model,
                prompt_summary=f"Attempted to critique top {len(selected)} question cards.",
                error=str(exc),
            )

    def _generation_prompt(
        self,
        consensus: list[ConsensusClaim],
        controversies: list[ControversyClaim],
        seed_cards: list[ResearchQuestionCard],
        target_count: int,
    ) -> str:
        consensus_payload = [
            {
                "consensus_id": item.consensus_id,
                "topic": item.topic,
                "claim_text": item.claim_text,
                "evidence_ids": item.supporting_evidence_ids[:12],
            }
            for item in consensus[:16]
        ]
        controversy_payload = [
            {
                "controversy_id": item.controversy_id,
                "topic": item.topic,
                "claim_a": item.claim_a,
                "claim_b": item.claim_b,
                "evidence_ids": (item.supporting_evidence_a + item.supporting_evidence_b)[:12],
            }
            for item in controversies[:12]
        ]
        seed_payload = [
            {
                "question_id": item.question_id,
                "title": item.title,
                "topic": item.metadata.get("topic"),
                "question_type": item.question_type,
                "computability": item.preliminary_computability,
                "evidence_ids": item.evidence_ids[:12],
                "required_protocols": item.required_protocols,
                "required_reference_states": item.required_reference_states,
            }
            for item in seed_cards[:24]
        ]
        return json.dumps(
            {
                "instruction": (
                    "Generate improved research question cards for the current front-end agent. "
                    "The cards must be specific to the reaction/material scope, suitable for pure computational "
                    "catalysis follow-up, and must not cite evidence ids that are not provided. "
                    "Only assign C2/C3 when the question can be answered by computation without new wet experiments. "
                    "Bind every computation-ready card to registered protocol ids from the schema."
                ),
                "output_schema": {
                    "cards": [
                        {
                            "title": "string",
                            "topic": "string",
                            "question_type": "mechanism_reassessment | literature_conflict | descriptor | method_gap",
                            "background_consensus_ids": ["CON-xxxx"],
                            "controversy_ids": ["CTR-xxxx"],
                            "evidence_ids": ["EVD-xxxx"],
                            "unresolved_gap": ["string"],
                            "computational_path_hint": ["string"],
                            "expected_result_types": ["string"],
                            "minimal_publishable_results": ["string"],
                            "required_protocols": ["registered CalcProtocol id"],
                            "required_reference_states": ["string"],
                            "protocol_feasibility": "candidate_protocols_available_in_mvp_registry | no_registered_protocol_hint | needs_human_protocol_review",
                            "aiida_executability": "candidate_for_aiida_workchain_after_protocol_gate | blocked_until_protocol_registered | blocked_before_aiida_planning",
                            "computational_verifiability_gate": "pass_G2_C2_C3_candidate | fail_G2_support_only_or_experimental_dependency",
                            "expected_audit_risks": ["string"],
                            "wet_experiment_dependency": "string",
                            "preliminary_computability": "C1 | C2 | C3",
                            "novelty_risk": "low | medium | high | unknown",
                            "calculation_cost": "low | medium | medium-high | high",
                            "graduation_value": "string",
                            "risks": ["string"],
                        }
                    ]
                },
                "target_count": target_count,
                "project_scope": self.scope.model_dump(mode="json"),
                "consensus_candidates": consensus_payload,
                "controversy_candidates": controversy_payload,
                "seed_cards": seed_payload,
            },
            ensure_ascii=False,
            indent=2,
        )

    def _critique_prompt(self, cards: list[ResearchQuestionCard], reviews: list[ReviewResult]) -> str:
        review_map = {item.question_id: item for item in reviews}
        payload = []
        for card in cards:
            review = review_map.get(card.question_id)
            payload.append(
                {
                    "question_id": card.question_id,
                    "title": card.title,
                    "topic": card.metadata.get("topic"),
                    "question_type": card.question_type,
                    "priority_score": card.priority_score,
                    "scores": review.scores if review else {},
                    "evidence_count": len(card.evidence_ids),
                    "computational_path_hint": card.computational_path_hint,
                    "minimal_publishable_results": card.minimal_publishable_results,
                    "required_protocols": card.required_protocols,
                    "required_reference_states": card.required_reference_states,
                    "protocol_feasibility": card.protocol_feasibility,
                    "aiida_executability": card.aiida_executability,
                    "expected_audit_risks": card.expected_audit_risks,
                    "risks": card.risks,
                }
            )
        return json.dumps(
            {
                "instruction": (
                    "For each question, improve the title if it is too template-like, "
                    "add concise critique comments, and flag what downstream computation/verifiability agent must check."
                ),
                "output_schema": {
                    "updates": [
                        {
                            "question_id": "string",
                            "improved_title": "string or null",
                            "critique_comments": ["string"],
                            "downstream_checks": ["string"],
                            "risk_notes": ["string"],
                        }
                    ]
                },
                "project_scope": self.scope.model_dump(mode="json"),
                "cards": payload,
            },
            ensure_ascii=False,
            indent=2,
        )

    def _parse_generated_cards(
        self,
        data: dict[str, Any],
        seed_cards: list[ResearchQuestionCard],
        target_count: int,
    ) -> list[ResearchQuestionCard]:
        raw_cards = data.get("cards", [])
        if not isinstance(raw_cards, list):
            raise LLMError("LLM JSON does not contain a cards array.")
        seed_by_topic: dict[str, ResearchQuestionCard] = {}
        for seed in seed_cards:
            topic = str(seed.metadata.get("topic") or "")
            if topic and topic not in seed_by_topic:
                seed_by_topic[topic] = seed

        parsed: list[ResearchQuestionCard] = []
        for idx, item in enumerate(raw_cards[:target_count], start=1):
            if not isinstance(item, dict):
                continue
            topic = str(item.get("topic") or "llm_generated")
            seed = seed_by_topic.get(topic)
            evidence_ids = self._string_list(item.get("evidence_ids"))
            if not evidence_ids and seed:
                evidence_ids = seed.evidence_ids[:12]
            protocols = self._string_list(item.get("required_protocols"))
            if not protocols and seed:
                protocols = seed.required_protocols
            reference_states = self._string_list(item.get("required_reference_states"))
            if not reference_states and seed:
                reference_states = seed.required_reference_states
            computability = self._computability(item.get("preliminary_computability"))
            parsed.append(
                ResearchQuestionCard(
                    question_id=f"LLM-{self.scope.project_id}-{idx:03d}",
                    title=str(item.get("title") or f"LLM generated question for {topic}"),
                    reaction=self.scope.reaction,
                    catalyst=self.scope.catalyst_family,
                    question_type=str(item.get("question_type") or "llm_generated"),
                    background_consensus_ids=self._string_list(item.get("background_consensus_ids")),
                    controversy_ids=self._string_list(item.get("controversy_ids")),
                    evidence_ids=evidence_ids,
                    unresolved_gap=self._string_list(item.get("unresolved_gap")),
                    computational_path_hint=self._string_list(item.get("computational_path_hint")),
                    expected_result_types=self._string_list(item.get("expected_result_types")),
                    minimal_publishable_results=self._string_list(item.get("minimal_publishable_results")),
                    required_protocols=protocols,
                    required_reference_states=reference_states,
                    protocol_feasibility=str(
                        item.get("protocol_feasibility")
                        or ("candidate_protocols_available_in_mvp_registry" if protocols else "no_registered_protocol_hint")
                    ),
                    aiida_executability=str(
                        item.get("aiida_executability")
                        or (
                            "candidate_for_aiida_workchain_after_protocol_gate"
                            if protocols and computability in {ComputabilityLabel.C2, ComputabilityLabel.C3}
                            else "blocked_before_aiida_planning"
                        )
                    ),
                    computational_verifiability_gate=str(
                        item.get("computational_verifiability_gate")
                        or (
                            "pass_G2_C2_C3_candidate"
                            if computability in {ComputabilityLabel.C2, ComputabilityLabel.C3}
                            else "fail_G2_support_only_or_experimental_dependency"
                        )
                    ),
                    literature_evidence_gate="pass_G1_prefilter" if len(evidence_ids) >= 2 else "fail_G1_needs_more_literature_evidence",
                    expected_audit_risks=self._string_list(item.get("expected_audit_risks")),
                    wet_experiment_dependency=str(item.get("wet_experiment_dependency") or "unknown"),
                    preliminary_computability=computability,
                    novelty_risk=str(item.get("novelty_risk") or "unknown"),
                    calculation_cost=str(item.get("calculation_cost") or "unknown"),
                    graduation_value=str(item.get("graduation_value") or "B档机制论文候选"),
                    risks=self._string_list(item.get("risks")),
                    metadata={"topic": topic, "source": "deepseek_llm"},
                )
            )
        return parsed

    def _parse_critiques(self, data: dict[str, Any]) -> dict[str, dict[str, Any]]:
        updates = data.get("updates", [])
        if not isinstance(updates, list):
            raise LLMError("LLM JSON does not contain an updates array.")
        parsed: dict[str, dict[str, Any]] = {}
        for item in updates:
            if not isinstance(item, dict) or not item.get("question_id"):
                continue
            parsed[str(item["question_id"])] = {
                "improved_title": item.get("improved_title"),
                "critique_comments": self._string_list(item.get("critique_comments")),
                "downstream_checks": self._string_list(item.get("downstream_checks")),
                "risk_notes": self._string_list(item.get("risk_notes")),
            }
        return parsed

    def _string_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _computability(self, value: Any) -> ComputabilityLabel:
        text = str(value or "C2").upper()
        if text in {"C1", "C2", "C3"}:
            return ComputabilityLabel(text)
        return ComputabilityLabel.C2
