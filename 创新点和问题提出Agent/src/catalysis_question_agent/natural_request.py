from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .config import load_config
from .io_utils import write_json, write_text
from .llm_client import LLMError, llm_client_from_config
from .workflow import QuestionDiscoveryWorkflow


SAFE_PATCH_SECTIONS = {
    "project_scope",
    "search_expansion",
    "source_filters",
    "generation",
    "review",
    "metadata_enrichment",
    "similar_work_search",
}


class NaturalLanguageRequestRunner:
    """Compile a natural-language research request into an isolated config and run the workflow."""

    def __init__(self, base_config_path: str | Path):
        self.base_config_path = Path(base_config_path).resolve()
        self.base_config = load_config(self.base_config_path)

    def run(self, request_text: str, output_dir: str | Path | None = None):
        request_id = self._request_id(request_text)
        out_dir = Path(output_dir) if output_dir else self._default_output_dir(request_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        patch = self._compile_request_with_llm(request_text, request_id)
        config = self._merge_config(self.base_config, patch, request_id)
        sanitized_config = self._sanitize_config_for_disk(config)

        write_text(out_dir / "request" / "user_request.md", request_text.strip() + "\n")
        write_json(out_dir / "request" / "config_patch.json", patch)
        write_text(
            out_dir / "request" / "generated_config.yaml",
            yaml.safe_dump(sanitized_config, allow_unicode=True, sort_keys=False),
        )

        result = QuestionDiscoveryWorkflow(config_data=config).run(output_dir=out_dir)
        return result, patch, out_dir

    def _compile_request_with_llm(self, request_text: str, request_id: str) -> dict[str, Any]:
        client = llm_client_from_config(self.base_config)
        if not client.enabled:
            raise LLMError(
                "Natural-language request mode requires llm.enabled: true in the base config."
            )
        messages = [
            {
                "role": "system",
                "content": (
                    "You convert a Chinese or English natural-language catalysis research request "
                    "into a safe YAML-compatible JSON patch for a research-question discovery agent. "
                    "Return only valid JSON. Do not include API keys or secrets."
                ),
            },
            {
                "role": "user",
                "content": self._prompt(request_text, request_id),
            },
        ]
        data = client.chat_json(messages, max_tokens=3500)
        return self._sanitize_patch(data)

    def _prompt(self, request_text: str, request_id: str) -> str:
        base_scope = copy.deepcopy(self.base_config.get("project_scope", {}))
        base_sources = copy.deepcopy(self.base_config.get("sources", {}))
        return json.dumps(
            {
                "task": "Convert the user's natural-language request into config fields.",
                "request_id": request_id,
                "user_request": request_text,
                "base_project_scope": base_scope,
                "base_sources_summary": base_sources,
                "allowed_output_sections": sorted(SAFE_PATCH_SECTIONS),
                "requirements": [
                    "Keep the request focused and computational-catalysis oriented.",
                    "Infer reaction, catalyst_family, focus_keywords, search_expansion terms, and source_filters.",
                    "Preserve the existing local literature sources unless the user explicitly requests another source.",
                    "Set project_scope.default_project_id to the provided request_id.",
                    "Do not include llm, api_key, api, output, or filesystem paths unless the user explicitly provides a source path.",
                    "Prefer 20-50 final cards and 3-5 recommendations.",
                ],
                "schema_hint": {
                    "project_scope": {
                        "default_project_id": request_id,
                        "reaction": "string",
                        "catalyst_family": "string",
                        "focus_keywords": ["string"],
                        "time_range": {"start_year": 2015, "end_year": 2026},
                        "graduation_target": "string",
                    },
                    "search_expansion": {
                        "core_terms": ["string"],
                        "mechanism_terms": ["string"],
                        "evidence_terms": ["string"],
                    },
                    "source_filters": {
                        "include_keywords": ["string"],
                        "required_keyword_groups": [["string"]],
                        "title_path_required_keyword_groups": [["string"]],
                        "max_sources": 80,
                        "max_text_sources": 60,
                        "max_csv_sources": 20,
                    },
                    "generation": {
                        "target_final_cards": 30,
                        "target_recommendations": 5,
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        )

    def _sanitize_patch(self, raw: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise LLMError("Natural-language compiler returned non-object JSON.")
        patch = raw.get("config_patch", raw)
        if not isinstance(patch, dict):
            raise LLMError("Natural-language compiler JSON must contain an object patch.")
        sanitized: dict[str, Any] = {}
        for key, value in patch.items():
            if key in SAFE_PATCH_SECTIONS and isinstance(value, dict):
                sanitized[key] = value
        return sanitized

    def _merge_config(self, base: dict[str, Any], patch: dict[str, Any], request_id: str) -> dict[str, Any]:
        merged = copy.deepcopy(base)
        for section, value in patch.items():
            if section not in SAFE_PATCH_SECTIONS:
                continue
            if isinstance(value, dict) and isinstance(merged.get(section), dict):
                merged[section] = self._deep_merge(merged[section], value)
            else:
                merged[section] = copy.deepcopy(value)

        project_scope = merged.setdefault("project_scope", {})
        project_scope["default_project_id"] = request_id

        # Keep output paths relative inside this run. The CLI passes the exact isolated output dir.
        merged.setdefault("output", copy.deepcopy(base.get("output", {})))
        merged["_config_path"] = str(self.base_config_path)
        merged["_config_dir"] = str(self.base_config_path.parent)
        return merged

    def _deep_merge(self, base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        out = copy.deepcopy(base)
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(out.get(key), dict):
                out[key] = self._deep_merge(out[key], value)
            else:
                out[key] = copy.deepcopy(value)
        return out

    def _sanitize_config_for_disk(self, config: dict[str, Any]) -> dict[str, Any]:
        sanitized = copy.deepcopy(config)
        sanitized.pop("_config_path", None)
        sanitized.pop("_config_dir", None)
        llm = sanitized.get("llm")
        if isinstance(llm, dict):
            if llm.get("api_key"):
                llm["api_key"] = ""
                llm["api_key_note"] = "redacted; use DEEPSEEK_API_KEY or base config for runtime"
        return sanitized

    def _default_output_dir(self, request_id: str) -> Path:
        config_dir = Path(self.base_config["_config_dir"])
        return config_dir / "outputs" / "natural_requests" / request_id

    def _request_id(self, request_text: str) -> str:
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        digest = hashlib.sha1(request_text.encode("utf-8")).hexdigest()[:8]
        slug = self._slug(request_text)[:40]
        return f"nl_{now}_{digest}_{slug}".rstrip("_")

    def _slug(self, text: str) -> str:
        ascii_words = re.findall(r"[A-Za-z0-9]+", text)
        if ascii_words:
            return "_".join(ascii_words[:8]).lower()
        return "request"
