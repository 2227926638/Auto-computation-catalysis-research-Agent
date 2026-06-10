from __future__ import annotations

import re

from .models import ComputabilityLabel, ResearchQuestionCard, ReviewDecision, ReviewResult


class QuestionReviewer:
    """Apply hard gates, scoring, deduplication, and lightweight evolution."""

    def __init__(self, config: dict):
        self.config = config
        review = config.get("review", {}) or {}
        self.weights = review.get("scoring_weights", {}) or {}
        self.thresholds = review.get("thresholds", {}) or {}
        self.topic_priority_bonus = review.get("topic_priority_bonus", {}) or {}
        hard = review.get("hard_gates", {}) or {}
        self.min_evidence = int(hard.get("min_evidence_per_high_priority_card", 2))
        acceptable = (config.get("computability_prefilter", {}) or {}).get("acceptable_for_next_stage", ["C2", "C3"])
        self.acceptable_computability = {ComputabilityLabel(str(item).upper()) for item in acceptable if str(item).upper() in {"C2", "C3"}}

    def review(self, cards: list[ResearchQuestionCard]) -> tuple[list[ResearchQuestionCard], list[ReviewResult]]:
        deduped = self._dedupe(cards)
        reviews = [self._review_one(card) for card in deduped]

        by_id = {review.question_id: review for review in reviews}
        for card in deduped:
            result = by_id[card.question_id]
            card.priority_score = result.priority_score
            card.status = result.decision
            if result.decision in {ReviewDecision.RECOMMEND, ReviewDecision.RESERVE}:
                card.title = self._evolve_title(card)
                card.risks.extend(result.review_comments)

        sorted_cards = sorted(deduped, key=lambda item: item.priority_score, reverse=True)
        sorted_reviews = sorted(reviews, key=lambda item: item.priority_score, reverse=True)

        target_recommendations = int((self.config.get("generation", {}) or {}).get("target_recommendations", 3))
        chosen_recommend_ids = self._choose_diverse_recommendations(sorted_cards, target_recommendations)
        for card in sorted_cards:
            if card.status == ReviewDecision.RECOMMEND and card.question_id not in chosen_recommend_ids:
                card.status = ReviewDecision.RESERVE
        final_decisions = {card.question_id: card.status for card in sorted_cards}
        for result in sorted_reviews:
            result.decision = final_decisions[result.question_id]
        return sorted_cards, sorted_reviews

    def _review_one(self, card: ResearchQuestionCard) -> ReviewResult:
        evidence_count = len(card.evidence_ids)
        hard_gate = {
            "G1_literature_evidence": evidence_count >= self.min_evidence,
            "G2_computational_verifiability": card.preliminary_computability in self.acceptable_computability,
            "G3_protocol_registered": bool(card.required_protocols)
            and card.protocol_feasibility != "no_registered_protocol_hint",
            "no_complete_recent_duplicate": True,
            "has_modelable_system": bool(card.reaction and card.catalyst),
            "has_minimal_publishable_result_set": bool(card.minimal_publishable_results),
        }

        scores = {
            "novelty_score": self._novelty_score(card),
            "computability_score": self._computability_score(card),
            "publishability_score": self._publishability_score(card),
            "graduation_value_score": self._graduation_value_score(card),
            "evidence_strength_score": min(100.0, 25.0 + evidence_count * 18.0),
            "cost_control_score": self._cost_score(card),
        }
        priority = round(
            sum(scores[key] * float(self.weights.get(key, 0.0)) for key in scores)
            + self._topic_bonus(card),
            2,
        )

        comments: list[str] = []
        if not hard_gate["G1_literature_evidence"]:
            comments.append("G1 Literature Evidence Gate failed: add at least two verified literature/data sources.")
        if not hard_gate["G2_computational_verifiability"]:
            comments.append("G2 Computational Verifiability Gate failed: only C2/C3 can enter computation planning.")
        if not hard_gate["G3_protocol_registered"]:
            comments.append("G3 Protocol Gate failed: bind the card to at least one registered CalcProtocol.")
        if "NEB" in " ".join(card.minimal_publishable_results) and "high" in card.calculation_cost:
            comments.append("NEB-heavy path may need low-cost screening before full DFT.")
        comments.append("Recent-work duplicate check is a placeholder and must be replaced by online/local search.")

        if not all(hard_gate.values()):
            decision = ReviewDecision.NEEDS_EVIDENCE if not hard_gate["G1_literature_evidence"] else ReviewDecision.ARCHIVE
        elif priority >= float(self.thresholds.get("recommend", 75)):
            decision = ReviewDecision.RECOMMEND
        elif priority >= float(self.thresholds.get("reserve", 60)):
            decision = ReviewDecision.RESERVE
        else:
            decision = ReviewDecision.ARCHIVE

        return ReviewResult(
            question_id=card.question_id,
            scores=scores,
            priority_score=priority,
            hard_gate=hard_gate,
            review_comments=comments,
            decision=decision,
        )

    def _dedupe(self, cards: list[ResearchQuestionCard]) -> list[ResearchQuestionCard]:
        seen: set[tuple[str, str]] = set()
        out: list[ResearchQuestionCard] = []
        for card in cards:
            topic = str(card.metadata.get("topic", "")).lower()
            pattern = card.question_type.lower()
            key = (topic, pattern)
            if key in seen:
                continue
            seen.add(key)
            out.append(card)
        return out

    def _choose_diverse_recommendations(
        self,
        cards: list[ResearchQuestionCard],
        target_recommendations: int,
    ) -> set[str]:
        recommendable = [card for card in cards if card.status == ReviewDecision.RECOMMEND]
        chosen: list[ResearchQuestionCard] = []
        seen_topics: set[str] = set()

        for card in recommendable:
            topic = str(card.metadata.get("topic", ""))
            if topic in seen_topics:
                continue
            chosen.append(card)
            seen_topics.add(topic)
            if len(chosen) >= target_recommendations:
                return {card.question_id for card in chosen}

        for card in recommendable:
            if card in chosen:
                continue
            chosen.append(card)
            if len(chosen) >= target_recommendations:
                break
        return {card.question_id for card in chosen}

    def _evolve_title(self, card: ResearchQuestionCard) -> str:
        topic = card.metadata.get("topic", "mechanism")
        if card.question_type == "method_gap":
            return f"Minimum computable evidence set for resolving {topic} in {card.reaction} on {card.catalyst}"
        if card.question_type == "literature_conflict":
            return f"Computational reassessment of {topic}-controlled pathways for {card.reaction} on {card.catalyst}"
        return card.title

    def _novelty_score(self, card: ResearchQuestionCard) -> float:
        base = 72.0
        if card.question_type in {"literature_conflict", "oversimplified_model", "method_gap"}:
            base += 8.0
        if len(card.controversy_ids) > 0:
            base += 6.0
        return min(base, 92.0)

    def _topic_bonus(self, card: ResearchQuestionCard) -> float:
        topic = str(card.metadata.get("topic", ""))
        return float(self.topic_priority_bonus.get(topic, 0.0))

    def _computability_score(self, card: ResearchQuestionCard) -> float:
        mapping = {
            ComputabilityLabel.C0: 20.0,
            ComputabilityLabel.C1: 48.0,
            ComputabilityLabel.C2: 82.0,
            ComputabilityLabel.C3: 90.0,
        }
        score = mapping[card.preliminary_computability]
        if self._has_clear_calculation_terms(card):
            score += 4.0
        return min(score, 95.0)

    def _publishability_score(self, card: ResearchQuestionCard) -> float:
        score = 65.0
        if len(card.expected_result_types) >= 4:
            score += 8.0
        if len(card.minimal_publishable_results) >= 4:
            score += 8.0
        if len(card.evidence_ids) >= self.min_evidence:
            score += 6.0
        return min(score, 90.0)

    def _graduation_value_score(self, card: ResearchQuestionCard) -> float:
        text = card.graduation_value
        if "B" in text or "B档" in text:
            return 82.0
        return 65.0

    def _cost_score(self, card: ResearchQuestionCard) -> float:
        text = card.calculation_cost.lower()
        if "low" in text:
            return 88.0
        if "medium-high" in text:
            return 66.0
        if "medium" in text:
            return 76.0
        if "high" in text:
            return 55.0
        return 60.0

    def _has_clear_calculation_terms(self, card: ResearchQuestionCard) -> bool:
        text = " ".join(card.computational_path_hint + card.minimal_publishable_results)
        return bool(re.search(r"\b(DFT|NEB|Bader|PDOS|adsorption|barrier|microkinetic)\b", text, re.I))
