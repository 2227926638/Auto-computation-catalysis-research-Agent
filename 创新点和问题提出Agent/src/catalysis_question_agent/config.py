from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import ProjectScope


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).resolve()
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data["_config_path"] = str(config_path)
    data["_config_dir"] = str(config_path.parent)
    return data


def project_scope_from_config(config: dict[str, Any]) -> ProjectScope:
    scope = config.get("project_scope", {})
    time_range = scope.get("time_range", {}) or {}
    return ProjectScope(
        project_id=scope.get("default_project_id", "default_project"),
        reaction=scope.get("reaction", "unspecified reaction"),
        catalyst_family=scope.get("catalyst_family", "unspecified catalyst"),
        focus_keywords=list(scope.get("focus_keywords", [])),
        start_year=time_range.get("start_year"),
        end_year=time_range.get("end_year"),
        graduation_target=scope.get("graduation_target"),
    )


def search_terms_from_config(config: dict[str, Any]) -> list[str]:
    expansion = config.get("search_expansion", {}) or {}
    terms: list[str] = []
    for key in ("core_terms", "mechanism_terms", "evidence_terms"):
        terms.extend(expansion.get(key, []) or [])
    scope = config.get("project_scope", {}) or {}
    terms.extend(scope.get("focus_keywords", []) or [])
    terms.extend([scope.get("reaction", ""), scope.get("catalyst_family", "")])
    return _dedupe([term for term in terms if term])


def output_base_from_config(config: dict[str, Any]) -> Path:
    config_dir = Path(config["_config_dir"])
    base = config.get("output", {}).get("base_dir", "outputs")
    path = Path(base)
    if not path.is_absolute():
        path = config_dir / path
    return path


def manual_review_items(config: dict[str, Any]) -> list[str]:
    return list(config.get("manual_review_required", []) or [])


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
