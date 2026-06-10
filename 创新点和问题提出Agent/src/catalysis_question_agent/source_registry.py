from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field

from .config import project_scope_from_config, search_terms_from_config
from .models import StrictModel


class SourceRegistryEntry(StrictModel):
    source_id: str
    name: str
    provider: str
    domain: str
    tier: str = "S"
    enabled: bool = True
    source_kind: str = "paper"
    access_mode: str = "metadata_api"
    evidence_level: str = "triage_until_fulltext"
    content_state: str = "metadata_only"
    license_state: str = "unknown"
    queries: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    fulltext_routes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SourceRegistry(StrictModel):
    version: int = 1
    entries: list[SourceRegistryEntry] = Field(default_factory=list)


def registry_path_from_config(config: dict[str, Any]) -> Path:
    harvest = config.get("source_harvest", {}) or {}
    raw_path = harvest.get("registry_path", "source_registry.yaml")
    path = Path(raw_path)
    if not path.is_absolute():
        config_dir = Path(config.get("_config_dir", "."))
        path = config_dir / path
    return path


def load_source_registry(config: dict[str, Any]) -> SourceRegistry:
    path = registry_path_from_config(config)
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return SourceRegistry.model_validate(data)
    return SourceRegistry(entries=default_source_registry_entries(config))


def default_source_registry_entries(config: dict[str, Any]) -> list[SourceRegistryEntry]:
    scope = project_scope_from_config(config)
    terms = search_terms_from_config(config)
    base_query = " ".join(part for part in [scope.catalyst_family, scope.reaction] if part)
    catalyst_query = base_query or " ".join(terms[:4]) or "catalysis machine learning"
    return [
        SourceRegistryEntry(
            source_id="openalex_project_core",
            name="OpenAlex project core works",
            provider="openalex",
            domain="catalysis",
            tier="S",
            queries=[catalyst_query],
            filters={"type": "article"},
            fulltext_routes=["unpaywall", "crossref_tdm_link", "local_pdf_inbox", "licensed_tdm_api"],
        ),
        SourceRegistryEntry(
            source_id="crossref_project_core",
            name="Crossref project core DOI metadata",
            provider="crossref",
            domain="catalysis",
            tier="S",
            queries=[catalyst_query],
            filters={"type": "journal-article"},
            fulltext_routes=["unpaywall", "crossref_tdm_link", "local_pdf_inbox", "licensed_tdm_api"],
        ),
        SourceRegistryEntry(
            source_id="arxiv_ai4s",
            name="arXiv AI4S preprints",
            provider="arxiv",
            domain="ai4s",
            tier="A",
            source_kind="preprint",
            access_mode="api",
            evidence_level="abstract",
            content_state="oa_pdf",
            license_state="open",
            queries=["AI for science catalysis", "machine learning catalysis"],
            filters={
                "categories": ["cs.LG", "cs.AI", "stat.ML", "cond-mat.mtrl-sci", "physics.chem-ph"],
                "sortBy": "relevance",
                "sortOrder": "descending",
            },
            fulltext_routes=["open_access_pdf"],
        ),
    ]
