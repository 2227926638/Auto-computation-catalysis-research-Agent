from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .models import MetadataRecord, ResearchQuestionCard, SimilarWorkCandidate, SourceRecord


DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)


@dataclass
class ApiSettings:
    timeout_seconds: float = 12.0
    sleep_seconds: float = 0.2
    user_agent: str = "catalysis-question-agent/0.1"
    mailto: str | None = None


class ScholarlyMetadataEnricher:
    """Fetch DOI/venue metadata and recent similar works from open scholarly APIs."""

    def __init__(self, config: dict):
        self.config = config
        api = (config.get("api", {}) or {})
        self.settings = ApiSettings(
            timeout_seconds=float(api.get("timeout_seconds", 12.0)),
            sleep_seconds=float(api.get("sleep_seconds", 0.2)),
            user_agent=api.get("user_agent", "catalysis-question-agent/0.1"),
            mailto=api.get("mailto"),
        )
        enrichment = config.get("metadata_enrichment", {}) or {}
        self.max_sources = int(enrichment.get("max_sources", 40))
        self.min_confidence = float(enrichment.get("min_confidence", 0.65))
        self.source_types = set(enrichment.get("source_types", []) or [])

    def enrich_sources(self, sources: list[SourceRecord]) -> list[MetadataRecord]:
        records: list[MetadataRecord] = []
        eligible = [source for source in sources if not self.source_types or source.source_type in self.source_types]
        for source in eligible[: self.max_sources]:
            record = self._enrich_one_source(source)
            records.append(record)
            self._apply_metadata(source, record)
        return records

    def find_similar_works(self, cards: list[ResearchQuestionCard]) -> list[SimilarWorkCandidate]:
        config = self.config.get("similar_work_search", {}) or {}
        if not config.get("enabled", False):
            return []
        max_questions = int(config.get("max_questions", 5))
        per_question = int(config.get("max_results_per_question", 8))
        from_year = int(config.get("from_year", 2021))
        to_year = int(config.get("to_year", 2026))
        candidates: list[SimilarWorkCandidate] = []

        selected = [card for card in cards if str(card.status) == "recommend"][:max_questions]
        for card in selected:
            query = self._similar_query(card)
            works = self._openalex_search_works(query, per_page=per_question * 3, from_year=from_year, to_year=to_year)
            added_for_question = 0
            for work in works:
                if not self._passes_similar_work_filter(work):
                    continue
                candidates.append(self._openalex_work_to_candidate(card.question_id, query, work))
                added_for_question += 1
                if added_for_question >= per_question:
                    break
        return candidates

    def _enrich_one_source(self, source: SourceRecord) -> MetadataRecord:
        text = " ".join([source.title, source.abstract or "", source.raw_text or ""])
        extracted_doi = self._extract_primary_doi(text)
        base = MetadataRecord(
            source_id=source.source_id,
            query_title=source.title,
            extracted_doi=extracted_doi,
            status="pending",
        )

        if extracted_doi:
            record = self._query_crossref_by_doi(extracted_doi, base)
            if record.status == "resolved":
                return record
            record = self._query_openalex_by_doi(extracted_doi, base)
            if record.status == "resolved":
                return record

        record = self._query_crossref_by_title(source.title, base)
        if record.status == "resolved" and record.confidence >= self.min_confidence:
            return record

        openalex = self._query_openalex_by_title(source.title, base)
        if openalex.status == "resolved":
            return openalex

        if record.status != "pending":
            return record
        return base.model_copy(update={"status": "not_found", "notes": ["No online metadata match found."]})

    def _query_crossref_by_doi(self, doi: str, base: MetadataRecord) -> MetadataRecord:
        try:
            url = f"https://api.crossref.org/works/{urllib.parse.quote(doi)}"
            data = self._get_json(url)
            item = data.get("message", {})
            return self._crossref_item_to_record(item, base, confidence=1.0)
        except Exception as exc:
            return base.model_copy(update={"status": "error", "source_api": "Crossref", "notes": [str(exc)]})

    def _query_crossref_by_title(self, title: str, base: MetadataRecord) -> MetadataRecord:
        try:
            params = urllib.parse.urlencode({"query.title": title, "rows": "3"})
            data = self._get_json(f"https://api.crossref.org/works?{params}")
            items = data.get("message", {}).get("items", [])
            if not items:
                return base.model_copy(update={"status": "not_found", "source_api": "Crossref"})
            best = max(items, key=lambda item: self._title_similarity(title, self._first(item.get("title")) or ""))
            confidence = self._title_similarity(title, self._first(best.get("title")) or "")
            record = self._crossref_item_to_record(best, base, confidence=confidence)
            if confidence < self.min_confidence:
                return record.model_copy(
                    update={
                        "status": "low_confidence",
                        "notes": [f"Best title match below threshold {self.min_confidence}."],
                    }
                )
            return record
        except Exception as exc:
            return base.model_copy(update={"status": "error", "source_api": "Crossref", "notes": [str(exc)]})

    def _query_openalex_by_doi(self, doi: str, base: MetadataRecord) -> MetadataRecord:
        try:
            url = f"https://api.openalex.org/works/https://doi.org/{urllib.parse.quote(doi)}"
            data = self._get_json(url)
            return self._openalex_item_to_record(data, base, confidence=1.0)
        except Exception as exc:
            return base.model_copy(update={"status": "error", "source_api": "OpenAlex", "notes": [str(exc)]})

    def _query_openalex_by_title(self, title: str, base: MetadataRecord) -> MetadataRecord:
        try:
            works = self._openalex_search_works(title, per_page=3, from_year=None, to_year=None)
            if not works:
                return base.model_copy(update={"status": "not_found", "source_api": "OpenAlex"})
            best = max(works, key=lambda item: self._title_similarity(title, item.get("title") or ""))
            confidence = self._title_similarity(title, best.get("title") or "")
            record = self._openalex_item_to_record(best, base, confidence=confidence)
            if confidence < self.min_confidence:
                return record.model_copy(
                    update={
                        "status": "low_confidence",
                        "notes": [f"Best title match below threshold {self.min_confidence}."],
                    }
                )
            return record
        except Exception as exc:
            return base.model_copy(update={"status": "error", "source_api": "OpenAlex", "notes": [str(exc)]})

    def _openalex_search_works(
        self,
        query: str,
        per_page: int,
        from_year: int | None,
        to_year: int | None,
    ) -> list[dict[str, Any]]:
        params = {"search": query, "per-page": str(per_page)}
        filters: list[str] = ["type:article"]
        if from_year and to_year:
            filters.append(f"publication_year:{from_year}-{to_year}")
        if filters:
            params["filter"] = ",".join(filters)
        data = self._get_json(f"https://api.openalex.org/works?{urllib.parse.urlencode(params)}")
        return list(data.get("results", []) or [])

    def _get_json(self, url: str) -> dict[str, Any]:
        if self.settings.mailto and "api.openalex.org" in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}mailto={urllib.parse.quote(self.settings.mailto)}"
        request = urllib.request.Request(url, headers={"User-Agent": self.settings.user_agent})
        with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
        time.sleep(self.settings.sleep_seconds)
        return json.loads(raw)

    def _crossref_item_to_record(self, item: dict[str, Any], base: MetadataRecord, confidence: float) -> MetadataRecord:
        year = None
        date_parts = (item.get("published-print") or item.get("published-online") or item.get("issued") or {}).get("date-parts")
        if date_parts and date_parts[0]:
            year = date_parts[0][0]
        authors = [
            " ".join(part for part in [author.get("given"), author.get("family")] if part)
            for author in item.get("author", [])[:8]
        ]
        return base.model_copy(
            update={
                "resolved_doi": item.get("DOI") or base.extracted_doi,
                "title": self._first(item.get("title")),
                "journal": self._first(item.get("container-title")),
                "year": year,
                "authors": [author for author in authors if author],
                "publisher": item.get("publisher"),
                "source_api": "Crossref",
                "url": item.get("URL"),
                "confidence": round(confidence, 3),
                "status": "resolved" if item else "not_found",
            }
        )

    def _openalex_item_to_record(self, item: dict[str, Any], base: MetadataRecord, confidence: float) -> MetadataRecord:
        authorships = item.get("authorships", []) or []
        authors = [
            authorship.get("author", {}).get("display_name", "")
            for authorship in authorships[:8]
            if authorship.get("author", {}).get("display_name")
        ]
        primary_location = item.get("primary_location") or {}
        source = (primary_location.get("source") or {}).get("display_name")
        return base.model_copy(
            update={
                "resolved_doi": self._clean_doi(item.get("doi")) or base.extracted_doi,
                "title": item.get("title"),
                "journal": source,
                "year": item.get("publication_year"),
                "authors": authors,
                "publisher": None,
                "source_api": "OpenAlex",
                "url": item.get("doi") or item.get("id"),
                "confidence": round(confidence, 3),
                "status": "resolved" if item else "not_found",
            }
        )

    def _openalex_work_to_candidate(self, question_id: str, query: str, work: dict[str, Any]) -> SimilarWorkCandidate:
        authors = [
            authorship.get("author", {}).get("display_name", "")
            for authorship in (work.get("authorships", []) or [])[:8]
            if authorship.get("author", {}).get("display_name")
        ]
        primary_location = work.get("primary_location") or {}
        journal = (primary_location.get("source") or {}).get("display_name")
        return SimilarWorkCandidate(
            question_id=question_id,
            query=query,
            title=work.get("title") or "",
            doi=self._clean_doi(work.get("doi")),
            year=work.get("publication_year"),
            journal=journal,
            authors=authors,
            url=work.get("doi") or work.get("id"),
            cited_by_count=work.get("cited_by_count"),
            relevance_hint="OpenAlex search result; inspect manually for duplicate novelty risk.",
        )

    def _similar_query(self, card: ResearchQuestionCard) -> str:
        topic = str(card.metadata.get("topic", ""))
        return " ".join(
            part
            for part in [
                "Ru CeO2 ammonia synthesis DFT",
                topic,
                "N2 activation",
                "oxygen vacancy" if topic != "oxygen vacancy" else "",
            ]
            if part
        )

    def _passes_similar_work_filter(self, work: dict[str, Any]) -> bool:
        text = " ".join([work.get("title") or "", self._abstract_text(work.get("abstract_inverted_index"))]).lower()
        ammonia_like = any(term in text for term in ["ammonia", "nh3", "nitrogen", "n2"])
        catalyst_like = any(term in text for term in ["ru", "ruthenium", "ceria", "ceo2", "catalyst"])
        off_topic = any(
            term in text
            for term in [
                "propane oxidation",
                "carbon dioxide hydrogenation",
                "polylactic acid",
                "hydrogen evolution",
                "abatement of no",
            ]
        )
        return ammonia_like and catalyst_like and not off_topic

    def _abstract_text(self, inverted: Any) -> str:
        if not isinstance(inverted, dict):
            return ""
        words: list[tuple[int, str]] = []
        for word, positions in inverted.items():
            if not isinstance(positions, list):
                continue
            for position in positions:
                if isinstance(position, int):
                    words.append((position, word))
        return " ".join(word for _, word in sorted(words)[:300])

    def _extract_primary_doi(self, text: str) -> str | None:
        head = text[:6000]
        matches = DOI_RE.findall(head)
        if not matches:
            return None
        return self._clean_doi(matches[0])

    def _clean_doi(self, doi: str | None) -> str | None:
        if not doi:
            return None
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
        return doi.strip().rstrip(".),;]").lower()

    def _apply_metadata(self, source: SourceRecord, record: MetadataRecord) -> None:
        if record.status != "resolved":
            return
        if record.resolved_doi:
            source.doi = record.resolved_doi
        if record.title and record.confidence >= self.min_confidence:
            source.title = record.title
        if record.journal:
            source.journal_or_source = record.journal
        if record.year:
            source.year = record.year
        if record.url:
            source.url = record.url
        if record.authors:
            source.authors = record.authors

    def _first(self, value: Any) -> str | None:
        if isinstance(value, list) and value:
            return value[0]
        if isinstance(value, str):
            return value
        return None

    def _title_similarity(self, a: str, b: str) -> float:
        ta = self._tokens(a)
        tb = self._tokens(b)
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / len(ta | tb)

    def _tokens(self, text: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}
