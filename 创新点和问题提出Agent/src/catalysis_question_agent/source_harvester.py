from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import load_config, output_base_from_config, project_scope_from_config
from .io_utils import model_rows, write_csv, write_json, write_jsonl, write_text
from .models import SourceCandidate, SourceHarvestResult
from .signal_ranker import SignalRanker
from .source_registry import SourceRegistryEntry, load_source_registry


TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class HarvestApiSettings:
    timeout_seconds: float = 12.0
    sleep_seconds: float = 0.2
    user_agent: str = "catalysis-question-agent/0.1"
    mailto: str | None = None


class SourceHarvester:
    """Discover source candidates without automating closed publisher downloads."""

    def __init__(self, config_path: str | Path | None = None, config_data: dict | None = None):
        if config_data is not None:
            self.config = config_data
        elif config_path is not None:
            self.config = load_config(config_path)
        else:
            raise ValueError("Either config_path or config_data must be provided.")
        self.scope = project_scope_from_config(self.config)
        api = self.config.get("api", {}) or {}
        self.settings = HarvestApiSettings(
            timeout_seconds=float(api.get("timeout_seconds", 12.0)),
            sleep_seconds=float(api.get("sleep_seconds", 0.2)),
            user_agent=api.get("user_agent", "catalysis-question-agent/0.1"),
            mailto=api.get("mailto"),
        )
        harvest = self.config.get("source_harvest", {}) or {}
        self.max_results_per_query = int(harvest.get("max_results_per_query", 20))
        self.from_year = harvest.get("from_year") or self.scope.start_year
        self.to_year = harvest.get("to_year") or self.scope.end_year
        arxiv = harvest.get("arxiv", {}) or {}
        self.arxiv_base_url = str(arxiv.get("base_url", "https://export.arxiv.org/api/query"))
        self.arxiv_sleep_seconds = float(arxiv.get("sleep_seconds", max(3.2, self.settings.sleep_seconds)))
        self.arxiv_timeout_seconds = float(arxiv.get("timeout_seconds", max(45.0, self.settings.timeout_seconds)))
        self.arxiv_max_retries = int(arxiv.get("max_retries", 2))
        self.errors: list[str] = []

    def run(
        self,
        output_dir: str | Path | None = None,
        limit: int | None = None,
        extra_queries: list[str] | None = None,
    ) -> SourceHarvestResult:
        run_id = datetime.now().strftime("HARVEST-%Y%m%d-%H%M%S")
        out_dir = self._output_dir(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        registry = load_source_registry(self.config)
        candidates: list[SourceCandidate] = []
        for entry in registry.entries:
            if not entry.enabled:
                continue
            active_entry = entry
            if extra_queries:
                active_entry = entry.model_copy(update={"queries": _dedupe(entry.queries + extra_queries)})
            try:
                candidates.extend(self._harvest_entry(active_entry, limit=limit))
            except Exception as exc:
                self.errors.append(f"{entry.source_id}: {exc}")

        candidates = self._dedupe_candidates(candidates)
        candidates = self._enrich_open_access(candidates)
        candidates = SignalRanker(self.config).rank(candidates)
        created = self._write_outputs(out_dir, candidates)
        summary_path = out_dir / "source_harvest_summary.json"
        created.append(summary_path)

        result = SourceHarvestResult(
            run_id=run_id,
            project_id=self.scope.project_id,
            candidate_count=len(candidates),
            fulltext_queue_count=sum(1 for item in candidates if item.triage_decision == "fulltext_queue"),
            oa_ready_count=sum(1 for item in candidates if item.triage_decision == "oa_fulltext_ready"),
            metadata_watch_count=sum(1 for item in candidates if item.triage_decision == "metadata_watch"),
            output_dir=str(out_dir.resolve()),
            created_files=[str(path.resolve()) for path in created],
            errors=self.errors,
        )
        write_json(summary_path, result)
        return result

    def _harvest_entry(self, entry: SourceRegistryEntry, limit: int | None) -> list[SourceCandidate]:
        provider = entry.provider.lower()
        if provider == "openalex":
            return self._harvest_openalex(entry, limit)
        if provider == "crossref" or provider == "chemrxiv_crossref":
            return self._harvest_crossref(entry, limit)
        if provider == "arxiv":
            return self._harvest_arxiv(entry, limit)
        if provider == "local_pdf_inbox":
            return []
        raise ValueError(f"Unsupported source provider: {entry.provider}")

    def _harvest_openalex(self, entry: SourceRegistryEntry, limit: int | None) -> list[SourceCandidate]:
        out: list[SourceCandidate] = []
        per_page = limit or self.max_results_per_query
        for query in entry.queries:
            try:
                params: dict[str, str] = {
                    "search": query,
                    "per-page": str(per_page),
                }
                if entry.filters.get("sort"):
                    params["sort"] = str(entry.filters["sort"])
                filters: list[str] = []
                work_type = entry.filters.get("type", "article")
                if work_type:
                    filters.append(f"type:{work_type}")
                year_filter = self._year_filter("publication_year")
                if year_filter:
                    filters.append(year_filter)
                if entry.filters.get("open_access_only"):
                    filters.append("is_oa:true")
                if filters:
                    params["filter"] = ",".join(filters)
                data = self._get_json(f"https://api.openalex.org/works?{urllib.parse.urlencode(params)}")
                for item in data.get("results", []) or []:
                    out.append(self._openalex_work_to_candidate(entry, item))
            except Exception as exc:
                self.errors.append(f"{entry.source_id} query `{query}`: {exc}")
        return out

    def _harvest_crossref(self, entry: SourceRegistryEntry, limit: int | None) -> list[SourceCandidate]:
        out: list[SourceCandidate] = []
        rows = limit or self.max_results_per_query
        for query in entry.queries:
            try:
                params = {
                    "query.bibliographic": query,
                    "rows": str(rows),
                }
                if entry.filters.get("sort"):
                    params["sort"] = str(entry.filters["sort"])
                if entry.filters.get("order"):
                    params["order"] = str(entry.filters["order"])
                filters: list[str] = []
                if self.from_year:
                    filters.append(f"from-pub-date:{int(self.from_year)}-01-01")
                if self.to_year:
                    filters.append(f"until-pub-date:{int(self.to_year)}-12-31")
                if entry.filters.get("prefix"):
                    filters.append(f"prefix:{entry.filters['prefix']}")
                if entry.filters.get("type"):
                    filters.append(f"type:{entry.filters['type']}")
                if filters:
                    params["filter"] = ",".join(filters)
                data = self._get_json(f"https://api.crossref.org/works?{urllib.parse.urlencode(params)}")
                for item in data.get("message", {}).get("items", []) or []:
                    candidate = self._crossref_item_to_candidate(entry, item)
                    if candidate:
                        out.append(candidate)
            except Exception as exc:
                self.errors.append(f"{entry.source_id} query `{query}`: {exc}")
        return out

    def _harvest_arxiv(self, entry: SourceRegistryEntry, limit: int | None) -> list[SourceCandidate]:
        out: list[SourceCandidate] = []
        max_results = limit or self.max_results_per_query
        for query in entry.queries:
            try:
                search_query = self._arxiv_search_query(query, entry.filters.get("categories", []) or [])
                params = urllib.parse.urlencode(
                    {
                        "search_query": search_query,
                        "start": "0",
                        "max_results": str(max_results),
                        "sortBy": str(entry.filters.get("sortBy", "relevance")),
                        "sortOrder": str(entry.filters.get("sortOrder", "descending")),
                    }
                )
                raw = self._get_arxiv_text(f"{self.arxiv_base_url}?{params}")
                root = ET.fromstring(raw)
                ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
                for node in root.findall("atom:entry", ns):
                    candidate = self._arxiv_entry_to_candidate(entry, node, ns)
                    if candidate:
                        out.append(candidate)
            except Exception as exc:
                self.errors.append(f"{entry.source_id} query `{query}`: {exc}")
        return out

    def _enrich_open_access(self, candidates: list[SourceCandidate]) -> list[SourceCandidate]:
        harvest = self.config.get("source_harvest", {}) or {}
        oa = harvest.get("open_access_enrichment", {}) or {}
        if not oa.get("enabled", True):
            return candidates
        email = oa.get("email") or os.getenv(oa.get("email_env", "UNPAYWALL_EMAIL")) or self.settings.mailto
        if not email:
            return candidates
        out: list[SourceCandidate] = []
        for candidate in candidates:
            if not candidate.doi or candidate.pdf_url:
                out.append(candidate)
                continue
            try:
                doi = urllib.parse.quote(candidate.doi, safe="")
                data = self._get_json(f"https://api.unpaywall.org/v2/{doi}?email={urllib.parse.quote(email)}")
                if not data.get("is_oa"):
                    out.append(candidate)
                    continue
                best = data.get("best_oa_location") or {}
                pdf_url = best.get("url_for_pdf")
                landing = best.get("url") or data.get("oa_url")
                license_name = best.get("license")
                notes = list(candidate.notes)
                notes.append("Unpaywall open-access route found.")
                out.append(
                    candidate.model_copy(
                        update={
                            "is_open_access": True,
                            "open_access_url": landing or candidate.open_access_url,
                            "pdf_url": pdf_url or candidate.pdf_url,
                            "content_state": "oa_pdf" if pdf_url else "oa_landing_page",
                            "license_state": "open" if license_name else candidate.license_state,
                            "notes": _dedupe(notes),
                        }
                    )
                )
            except Exception as exc:
                notes = list(candidate.notes)
                notes.append(f"Unpaywall lookup failed: {exc}")
                out.append(candidate.model_copy(update={"notes": _dedupe(notes)}))
        return out

    def _openalex_work_to_candidate(self, entry: SourceRegistryEntry, item: dict[str, Any]) -> SourceCandidate:
        title = item.get("title") or "Untitled OpenAlex work"
        primary_location = item.get("primary_location") or {}
        source = primary_location.get("source") or {}
        open_access = item.get("open_access") or {}
        best_oa = item.get("best_oa_location") or {}
        pdf_url = primary_location.get("pdf_url") or best_oa.get("pdf_url")
        open_url = primary_location.get("landing_page_url") or best_oa.get("landing_page_url")
        doi = _clean_doi(item.get("doi"))
        authors = [
            authorship.get("author", {}).get("display_name", "")
            for authorship in (item.get("authorships", []) or [])[:8]
            if authorship.get("author", {}).get("display_name")
        ]
        is_oa = bool(open_access.get("is_oa") or primary_location.get("is_oa") or pdf_url)
        return SourceCandidate(
            candidate_id=self._stable_candidate_id(doi, title),
            registry_source_id=entry.source_id,
            provider=entry.provider,
            domain=entry.domain,
            tier=entry.tier,
            source_kind=entry.source_kind,
            access_mode=entry.access_mode,
            evidence_level=entry.evidence_level,
            content_state="oa_pdf" if pdf_url else "oa_landing_page" if is_oa else entry.content_state,
            license_state="open" if is_oa else entry.license_state,
            title=title,
            authors=authors,
            journal_or_source=source.get("display_name"),
            publisher=None,
            year=item.get("publication_year"),
            published_date=item.get("publication_date"),
            doi=doi,
            url=item.get("doi") or item.get("id"),
            abstract=self._abstract_text(item.get("abstract_inverted_index")),
            cited_by_count=item.get("cited_by_count"),
            is_open_access=is_oa,
            open_access_url=open_url,
            pdf_url=pdf_url,
            fulltext_routes=self._routes(entry, doi, open_url, pdf_url),
            discovered_at=datetime.now().isoformat(timespec="seconds"),
            notes=list(entry.notes),
            raw_metadata={"openalex_id": item.get("id")},
        )

    def _crossref_item_to_candidate(self, entry: SourceRegistryEntry, item: dict[str, Any]) -> SourceCandidate | None:
        title = self._first(item.get("title"))
        if not title:
            return None
        doi = _clean_doi(item.get("DOI"))
        links = item.get("link", []) or []
        pdf_url = self._first_link(links, "application/pdf")
        fulltext_url = self._first_link(links, None)
        license_state = self._license_state(item.get("license", []) or [], entry.license_state)
        authors = [
            " ".join(part for part in [author.get("given"), author.get("family")] if part)
            for author in (item.get("author", []) or [])[:8]
        ]
        published_date, year = self._date_parts(item)
        abstract = _strip_tags(item.get("abstract") or "")
        return SourceCandidate(
            candidate_id=self._stable_candidate_id(doi, title),
            registry_source_id=entry.source_id,
            provider=entry.provider,
            domain=entry.domain,
            tier=entry.tier,
            source_kind=entry.source_kind,
            access_mode=entry.access_mode,
            evidence_level=entry.evidence_level,
            content_state="oa_pdf" if pdf_url else "metadata_with_tdm_link" if fulltext_url else entry.content_state,
            license_state=license_state,
            title=title,
            authors=[author for author in authors if author],
            journal_or_source=self._first(item.get("container-title")),
            publisher=item.get("publisher"),
            year=year,
            published_date=published_date,
            doi=doi,
            url=item.get("URL") or (f"https://doi.org/{doi}" if doi else None),
            abstract=abstract or None,
            is_open_access=license_state == "open",
            open_access_url=fulltext_url,
            pdf_url=pdf_url,
            fulltext_routes=self._routes(entry, doi, fulltext_url, pdf_url),
            discovered_at=datetime.now().isoformat(timespec="seconds"),
            notes=list(entry.notes),
            raw_metadata={"crossref_type": item.get("type")},
        )

    def _arxiv_entry_to_candidate(
        self,
        entry: SourceRegistryEntry,
        node: ET.Element,
        ns: dict[str, str],
    ) -> SourceCandidate | None:
        title = self._xml_text(node, "atom:title", ns)
        if not title:
            return None
        url = self._xml_text(node, "atom:id", ns)
        arxiv_id = (url or "").rsplit("/", 1)[-1]
        published = self._xml_text(node, "atom:published", ns)
        year = int(published[:4]) if published and published[:4].isdigit() else None
        authors = [
            self._xml_text(author, "atom:name", ns)
            for author in node.findall("atom:author", ns)[:8]
            if self._xml_text(author, "atom:name", ns)
        ]
        doi = _clean_doi(self._xml_text(node, "arxiv:doi", ns))
        pdf_url = None
        for link in node.findall("atom:link", ns):
            if link.attrib.get("type") == "application/pdf":
                pdf_url = link.attrib.get("href")
                break
        primary_category = node.find("arxiv:primary_category", ns)
        category = primary_category.attrib.get("term") if primary_category is not None else None
        return SourceCandidate(
            candidate_id=self._stable_candidate_id(doi or arxiv_id, title),
            registry_source_id=entry.source_id,
            provider=entry.provider,
            domain=entry.domain,
            tier=entry.tier,
            source_kind=entry.source_kind,
            access_mode=entry.access_mode,
            evidence_level=entry.evidence_level,
            content_state="oa_pdf",
            license_state="open",
            title=_clean_space(title),
            authors=authors,
            journal_or_source=f"arXiv:{category}" if category else "arXiv",
            year=year,
            published_date=published,
            doi=doi,
            url=url,
            abstract=_clean_space(self._xml_text(node, "atom:summary", ns) or ""),
            is_open_access=True,
            open_access_url=url,
            pdf_url=pdf_url,
            fulltext_routes=self._routes(entry, doi, url, pdf_url),
            discovered_at=datetime.now().isoformat(timespec="seconds"),
            notes=list(entry.notes),
            raw_metadata={"arxiv_id": arxiv_id, "category": category},
        )

    def _write_outputs(self, out_dir: Path, candidates: list[SourceCandidate]) -> list[Path]:
        sanitized = [item.model_copy(update={"raw_metadata": {}}) for item in candidates]
        created = [
            write_csv(out_dir / "new_sources.csv", model_rows(sanitized)),
            write_jsonl(out_dir / "new_sources.jsonl", sanitized),
            write_text(out_dir / "source_triage.md", self._triage_report(candidates)),
        ]
        if self.errors:
            created.append(write_json(out_dir / "source_harvest_errors.json", self.errors))
        return created

    def _triage_report(self, candidates: list[SourceCandidate]) -> str:
        lines = [f"# Source Triage: {self.scope.project_id}", ""]
        lines.extend(
            [
                f"- Total candidates: {len(candidates)}",
                f"- OA fulltext ready: {sum(1 for item in candidates if item.triage_decision == 'oa_fulltext_ready')}",
                f"- Fulltext queue: {sum(1 for item in candidates if item.triage_decision == 'fulltext_queue')}",
                f"- Metadata watch: {sum(1 for item in candidates if item.triage_decision == 'metadata_watch')}",
                f"- Low signal archive: {sum(1 for item in candidates if item.triage_decision == 'archive_low_signal')}",
                "",
                "## Policy",
                "",
                "This harvester discovers and triages sources. It does not automate closed publisher downloads.",
                "Closed full text should enter `local_pdf_inbox` or licensed TDM/API routes after access is verified.",
                "",
                "## Top Candidates",
                "",
            ]
        )
        if not candidates:
            lines.append("No candidates were harvested.")
            return "\n".join(lines) + "\n"
        for idx, item in enumerate(candidates[:40], start=1):
            routes = ", ".join(item.fulltext_routes[:4])
            doi = item.doi or ""
            lines.extend(
                [
                    f"### {idx}. {item.title}",
                    "",
                    f"- Decision: `{item.triage_decision}` | Score: `{item.triage_score}` | Relevance: `{item.relevance_score}`",
                    f"- Source: {item.journal_or_source or item.provider} | Year: {item.year or ''} | Tier: `{item.tier}`",
                    f"- DOI: `{doi}`",
                    f"- Access: `{item.content_state}` / `{item.license_state}`",
                    f"- Routes: {routes}",
                    f"- Matched terms: {', '.join(item.matched_terms[:10])}",
                    "",
                ]
            )
        return "\n".join(lines) + "\n"

    def _dedupe_candidates(self, candidates: list[SourceCandidate]) -> list[SourceCandidate]:
        by_key: dict[str, SourceCandidate] = {}
        for candidate in candidates:
            key = candidate.doi.lower() if candidate.doi else _normalize_title(candidate.title)
            existing = by_key.get(key)
            if not existing:
                by_key[key] = candidate
                continue
            by_key[key] = self._merge_duplicate(existing, candidate)
        return list(by_key.values())

    def _merge_duplicate(self, left: SourceCandidate, right: SourceCandidate) -> SourceCandidate:
        preferred = right if self._access_rank(right) > self._access_rank(left) else left
        other = left if preferred is right else right
        notes = _dedupe(preferred.notes + other.notes + [f"Duplicate metadata merged from {other.provider}."])
        routes = _dedupe(preferred.fulltext_routes + other.fulltext_routes)
        return preferred.model_copy(
            update={
                "notes": notes,
                "fulltext_routes": routes,
                "cited_by_count": preferred.cited_by_count or other.cited_by_count,
                "abstract": preferred.abstract or other.abstract,
                "authors": preferred.authors or other.authors,
                "journal_or_source": preferred.journal_or_source or other.journal_or_source,
            }
        )

    def _access_rank(self, candidate: SourceCandidate) -> int:
        if candidate.pdf_url:
            return 4
        if candidate.open_access_url:
            return 3
        if candidate.doi:
            return 2
        return 1

    def _routes(self, entry: SourceRegistryEntry, doi: str | None, open_url: str | None, pdf_url: str | None) -> list[str]:
        routes = list(entry.fulltext_routes)
        if pdf_url:
            routes.insert(0, "open_access_pdf")
        elif open_url:
            routes.insert(0, "open_access_landing_page")
        if doi:
            routes.append("unpaywall")
            routes.append("crossref_tdm_link")
        return _dedupe(routes)

    def _output_dir(self, output_dir: str | Path | None) -> Path:
        if output_dir:
            return Path(output_dir)
        harvest = self.config.get("source_harvest", {}) or {}
        base = harvest.get("output_base_dir")
        if base:
            base_path = Path(base)
            if not base_path.is_absolute():
                base_path = Path(self.config.get("_config_dir", ".")) / base_path
        else:
            base_path = output_base_from_config(self.config) / "intelligence"
        return base_path / datetime.now().strftime("%Y-%m-%d")

    def _get_json(self, url: str) -> dict[str, Any]:
        return json.loads(self._get_text(self._append_mailto(url)))

    def _get_text(self, url: str) -> str:
        request = urllib.request.Request(url, headers={"User-Agent": self.settings.user_agent})
        with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
        time.sleep(self.settings.sleep_seconds)
        return raw

    def _get_arxiv_text(self, url: str) -> str:
        last_exc: Exception | None = None
        for attempt in range(self.arxiv_max_retries + 1):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": self.settings.user_agent})
                with urllib.request.urlopen(request, timeout=self.arxiv_timeout_seconds) as response:
                    raw = response.read().decode("utf-8", errors="replace")
                time.sleep(self.arxiv_sleep_seconds)
                return raw
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code != 429 or attempt >= self.arxiv_max_retries:
                    raise
                time.sleep(self.arxiv_sleep_seconds * (attempt + 2))
            except TimeoutError as exc:
                last_exc = exc
                if attempt >= self.arxiv_max_retries:
                    raise
                time.sleep(self.arxiv_sleep_seconds * (attempt + 2))
        if last_exc:
            raise last_exc
        raise RuntimeError("arXiv request failed without an exception.")

    def _append_mailto(self, url: str) -> str:
        if not self.settings.mailto:
            return url
        if "api.openalex.org" not in url and "api.crossref.org" not in url:
            return url
        if "mailto=" in url:
            return url
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}mailto={urllib.parse.quote(self.settings.mailto)}"

    def _year_filter(self, field: str) -> str | None:
        if self.from_year and self.to_year:
            return f"{field}:{int(self.from_year)}-{int(self.to_year)}"
        if self.from_year:
            return f"from_{field}:{int(self.from_year)}"
        return None

    def _arxiv_search_query(self, query: str, categories: list[str]) -> str:
        tokens = [token for token in re.findall(r"[A-Za-z0-9]+", query) if len(token) >= 2]
        if tokens:
            term_query = " AND ".join(f"all:{token}" for token in tokens[:8])
        else:
            term_query = f'all:"{query}"'
        if not categories:
            return term_query
        cat_query = " OR ".join(f"cat:{cat}" for cat in categories)
        return f"({cat_query}) AND {term_query}"

    def _abstract_text(self, inverted: Any) -> str | None:
        if not isinstance(inverted, dict):
            return None
        words: list[tuple[int, str]] = []
        for word, positions in inverted.items():
            if not isinstance(positions, list):
                continue
            for position in positions:
                if isinstance(position, int):
                    words.append((position, word))
        return " ".join(word for _, word in sorted(words)[:450]) or None

    def _date_parts(self, item: dict[str, Any]) -> tuple[str | None, int | None]:
        data = item.get("published-print") or item.get("published-online") or item.get("published") or item.get("issued") or {}
        parts = data.get("date-parts") or []
        if not parts or not parts[0]:
            return None, None
        first = parts[0]
        year = int(first[0]) if first and isinstance(first[0], int) else None
        date = "-".join(str(part).zfill(2) for part in first[:3])
        return date, year

    def _license_state(self, licenses: list[dict[str, Any]], default: str) -> str:
        for item in licenses:
            url = str(item.get("URL") or "").lower()
            if "creativecommons.org" in url or "open-access" in url:
                return "open"
        return default

    def _first_link(self, links: list[dict[str, Any]], content_type: str | None) -> str | None:
        for item in links:
            if content_type is None or item.get("content-type") == content_type:
                return item.get("URL")
        return None

    def _first(self, value: Any) -> str | None:
        if isinstance(value, list) and value:
            return str(value[0])
        if isinstance(value, str):
            return value
        return None

    def _xml_text(self, node: ET.Element, path: str, ns: dict[str, str]) -> str | None:
        child = node.find(path, ns)
        if child is None or child.text is None:
            return None
        return _clean_space(child.text)

    def _stable_candidate_id(self, doi_or_id: str | None, title: str) -> str:
        key = (doi_or_id or _normalize_title(title)).lower()
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
        return f"SRC-{digest}"


def _clean_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    return doi.strip().rstrip(".),;]").lower()


def _strip_tags(text: str) -> str:
    return _clean_space(TAG_RE.sub(" ", text))


def _clean_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out
