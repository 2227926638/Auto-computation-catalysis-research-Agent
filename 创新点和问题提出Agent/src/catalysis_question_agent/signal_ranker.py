from __future__ import annotations

import math
import re
from typing import Any

from .config import search_terms_from_config
from .models import SourceCandidate


class SignalRanker:
    """Rank harvested source candidates for evidence-readiness triage."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        harvest = config.get("source_harvest", {}) or {}
        triage = harvest.get("triage", {}) or {}
        self.min_relevance = float(harvest.get("min_relevance_score", 0.2))
        self.fulltext_threshold = float(triage.get("enter_fulltext_queue_score", 0.45))
        configured_terms = list(triage.get("focus_terms", []) or [])
        self.terms = _dedupe(configured_terms + search_terms_from_config(config))

    def rank(self, candidates: list[SourceCandidate]) -> list[SourceCandidate]:
        ranked: list[SourceCandidate] = []
        for candidate in candidates:
            relevance, matched = self._relevance(candidate)
            quality = self._quality(candidate)
            triage_score = round(0.65 * relevance + 0.35 * quality, 3)
            decision, needs_fulltext = self._decision(candidate, triage_score, relevance)
            ranked.append(
                candidate.model_copy(
                    update={
                        "matched_terms": matched,
                        "relevance_score": round(relevance, 3),
                        "quality_score": round(quality, 3),
                        "triage_score": triage_score,
                        "triage_decision": decision,
                        "needs_fulltext": needs_fulltext,
                    }
                )
            )
        return sorted(ranked, key=lambda item: item.triage_score, reverse=True)

    def _relevance(self, candidate: SourceCandidate) -> tuple[float, list[str]]:
        title = candidate.title.lower()
        abstract = (candidate.abstract or "").lower()
        journal = (candidate.journal_or_source or "").lower()
        matched: list[str] = []
        score = 0.0
        for term in self.terms:
            norm = term.lower().strip()
            if not norm:
                continue
            weight = self._term_weight(norm)
            if norm in title:
                score += weight
                matched.append(term)
            elif norm in abstract:
                score += weight * 0.55
                matched.append(term)
            elif norm in journal:
                score += weight * 0.25
                matched.append(term)
        if score <= 0:
            return 0.0, []
        return min(score / 4.5, 1.0), _dedupe(matched)

    def _quality(self, candidate: SourceCandidate) -> float:
        tier_score = {"S": 0.95, "A": 0.75, "B": 0.5, "C": 0.25}.get(candidate.tier.upper(), 0.4)
        year_score = 0.35
        if candidate.year:
            if candidate.year >= 2024:
                year_score = 1.0
            elif candidate.year >= 2021:
                year_score = 0.75
            elif candidate.year >= 2018:
                year_score = 0.55
        cited_by = candidate.cited_by_count or 0
        citation_score = min(math.log1p(cited_by) / math.log(250), 1.0) if cited_by > 0 else 0.25
        access_score = 1.0 if candidate.pdf_url else 0.8 if candidate.open_access_url else 0.45
        return 0.36 * tier_score + 0.24 * year_score + 0.22 * citation_score + 0.18 * access_score

    def _decision(self, candidate: SourceCandidate, triage_score: float, relevance: float) -> tuple[str, bool]:
        if relevance < self.min_relevance:
            return "archive_low_signal", False
        if triage_score >= self.fulltext_threshold and (candidate.pdf_url or candidate.open_access_url):
            return "oa_fulltext_ready", True
        if triage_score >= self.fulltext_threshold:
            return "fulltext_queue", True
        return "metadata_watch", False

    def _term_weight(self, term: str) -> float:
        tokens = re.findall(r"[a-z0-9]+", term)
        if len(tokens) >= 3:
            return 1.4
        if len(tokens) == 2:
            return 1.15
        return 1.0


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out
