from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from .config import project_scope_from_config, search_terms_from_config
from .keywords import GAP_MARKERS, METHOD_MARKERS, TOPIC_KEYWORDS
from .models import ClaimType, ConsensusClaim, ControversyClaim, EvidenceItem, MethodEvidence, SourceRecord


class EvidenceBuilder:
    """Build source records, evidence items, consensus claims, and controversies."""

    def __init__(self, config: dict):
        self.config = config
        self.scope = project_scope_from_config(config)
        self.search_terms = search_terms_from_config(config)
        self.filters = config.get("source_filters", {}) or {}
        self.max_sources = int(self.filters.get("max_sources", 200))
        self.max_text_sources = int(self.filters.get("max_text_sources", self.max_sources))
        self.max_csv_sources = int(self.filters.get("max_csv_sources", self.max_sources))
        self.max_csv_rows = int(self.filters.get("max_csv_rows", 2000))
        self.max_evidence_per_source = int(self.filters.get("max_evidence_per_source", 80))

    def run(self, extra_inputs: Iterable[str | Path] | None = None):
        sources = self.load_sources(extra_inputs or [])
        evidence = self.extract_evidence(sources)
        method_evidence = self.extract_method_evidence(evidence)
        consensus = self.mine_consensus(evidence)
        controversies = self.mine_controversies(evidence)
        return sources, evidence, method_evidence, consensus, controversies

    def load_sources(self, extra_inputs: Iterable[str | Path]) -> list[SourceRecord]:
        paths = self._collect_input_paths(extra_inputs)
        sources: list[SourceRecord] = []
        next_id = 1
        text_sources = 0
        csv_sources = 0
        seen_text_keys: set[str] = set()
        for path in paths:
            if len(sources) >= self.max_sources:
                break
            suffix = path.suffix.lower()
            if suffix == ".csv":
                csv_limit = min(
                    self.max_sources - len(sources),
                    self.max_csv_sources - csv_sources,
                )
                if csv_limit <= 0:
                    continue
                loaded = self._load_csv_sources(path, next_id, csv_limit)
                sources.extend(loaded)
                csv_sources += len(loaded)
                next_id += len(loaded)
            elif suffix in {".md", ".txt"}:
                if text_sources >= self.max_text_sources:
                    continue
                source = self._load_text_source(path, next_id)
                if not self._passes_source_filter(source):
                    continue
                text_key = self._source_key(source)
                if text_key in seen_text_keys:
                    continue
                seen_text_keys.add(text_key)
                sources.append(source)
                text_sources += 1
                next_id += 1
        return sources

    def extract_evidence(self, sources: list[SourceRecord]) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        next_id = 1
        for source in sources:
            text = self._normalize_text(source.raw_text or source.abstract or "")
            source_evidence_count = 0
            for sentence, location in self._candidate_sentences_with_location(text):
                if source_evidence_count >= self.max_evidence_per_source:
                    break
                topic, topic_keywords = self._detect_topic(sentence)
                matched_terms = self._matched_terms(sentence, self.search_terms + topic_keywords)
                if not matched_terms:
                    continue
                evidence.append(
                    EvidenceItem(
                        evidence_id=f"EVD-{next_id:04d}",
                        source_id=source.source_id,
                        claim_type=self._classify_claim(sentence),
                        topic=topic,
                        claim_text=self._claim_text(sentence),
                        supporting_excerpt=sentence.strip(),
                        extracted_from="local_text",
                        source_doi=source.doi,
                        source_title=source.title,
                        source_journal_or_source=source.journal_or_source,
                        source_year=source.year,
                        source_location=location,
                        confidence=self._confidence(sentence, matched_terms),
                        requires_human_check=True,
                        keywords=matched_terms[:12],
                    )
                )
                source_evidence_count += 1
                next_id += 1
        return evidence

    def extract_method_evidence(self, evidence: list[EvidenceItem]) -> list[MethodEvidence]:
        method_evidence: list[MethodEvidence] = []
        next_id = 1
        for item in evidence:
            text = item.supporting_excerpt
            protocol_hints = self._protocol_hints(text, item.topic)
            software_hints = self._software_hints(text)
            parameter_hints = self._parameter_hints(text)
            if item.claim_type != ClaimType.METHOD and not (protocol_hints or software_hints or parameter_hints):
                continue
            method_evidence.append(
                MethodEvidence(
                    method_evidence_id=f"MTH-{next_id:04d}",
                    source_id=item.source_id,
                    linked_evidence_id=item.evidence_id,
                    topic=item.topic,
                    protocol_hints=protocol_hints,
                    software_hints=software_hints,
                    calculation_type=self._calculation_type(text, protocol_hints),
                    parameter_hints=parameter_hints,
                    reference_state_hints=self._reference_state_hints(text, item.topic),
                    excerpt=text,
                    source_location=item.source_location,
                    confidence=item.confidence,
                    requires_human_check=True,
                )
            )
            next_id += 1
        return method_evidence

    def mine_consensus(self, evidence: list[EvidenceItem]) -> list[ConsensusClaim]:
        grouped: dict[str, list[EvidenceItem]] = defaultdict(list)
        for item in evidence:
            if item.claim_type in {ClaimType.CONSENSUS, ClaimType.METHOD, ClaimType.VALUE}:
                grouped[item.topic].append(item)

        claims: list[ConsensusClaim] = []
        for idx, (topic, items) in enumerate(sorted(grouped.items()), start=1):
            claims.append(
                ConsensusClaim(
                    consensus_id=f"CON-{idx:04d}",
                    topic=topic,
                    claim_text=(
                        f"Evidence repeatedly discusses {topic} in relation to "
                        f"{self.scope.catalyst_family} and {self.scope.reaction}. "
                        "This is a machine-extracted consensus candidate and requires manual review."
                    ),
                    supporting_evidence_ids=[item.evidence_id for item in items],
                    evidence_strength=self._strength(len(items)),
                    notes="Do not promote this claim to manuscript text until DOI/source metadata are verified.",
                )
            )
        return claims

    def mine_controversies(self, evidence: list[EvidenceItem]) -> list[ControversyClaim]:
        grouped: dict[str, list[EvidenceItem]] = defaultdict(list)
        for item in evidence:
            if item.claim_type in {ClaimType.GAP, ClaimType.CONTROVERSY}:
                grouped[item.topic].append(item)

        claims: list[ControversyClaim] = []
        for idx, (topic, items) in enumerate(sorted(grouped.items()), start=1):
            claims.append(
                ControversyClaim(
                    controversy_id=f"CTR-{idx:04d}",
                    topic=topic,
                    claim_a=f"The role of {topic} appears unresolved or inconsistently described.",
                    claim_b=(
                        "A follow-up computation should separate adsorption trends, kinetic barriers, "
                        "and electronic-structure explanations."
                    ),
                    supporting_evidence_a=[item.evidence_id for item in items],
                    why_it_matters=(
                        "A controversy or gap can be converted into a calculable mechanism question "
                        "only if a clear model and minimum result set can be defined."
                    ),
                )
            )
        return claims

    def _collect_input_paths(self, extra_inputs: Iterable[str | Path]) -> list[Path]:
        paths: list[Path] = []
        for raw in extra_inputs:
            paths.extend(self._expand_path(Path(raw)))

        config_dir = Path(self.config["_config_dir"])
        local = (self.config.get("sources", {}) or {}).get("local", {}) or {}
        for key in ("pdf_dirs", "markdown_dirs"):
            for raw_dir in local.get(key, []) or []:
                path = Path(raw_dir)
                if not path.is_absolute():
                    path = config_dir / path
                paths.extend(self._expand_path(path))
        for raw_file in local.get("csv_files", []) or []:
            path = Path(raw_file)
            if not path.is_absolute():
                path = config_dir / path
            paths.extend(self._expand_path(path))

        supported = {".md", ".txt", ".csv"}
        unique: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            if path.suffix.lower() not in supported:
                continue
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            unique.append(path)
        unique.sort(key=lambda p: (self._suffix_priority(p.suffix.lower()), str(p).lower()))
        return unique

    def _expand_path(self, path: Path) -> list[Path]:
        if not path.exists():
            return []
        if path.is_file():
            return [path]
        return [p for p in path.rglob("*") if p.is_file()]

    def _suffix_priority(self, suffix: str) -> int:
        if suffix == ".md":
            return 0
        if suffix == ".txt":
            return 1
        if suffix == ".csv":
            return 2
        return 9

    def _load_text_source(self, path: Path, idx: int) -> SourceRecord:
        text = path.read_text(encoding="utf-8", errors="ignore")
        text = self._normalize_text(text)
        text = self._trim_reference_section(text)
        title = self._title_from_text(text) or path.stem
        return SourceRecord(
            source_id=f"SRC-{idx:04d}",
            source_type="local_text",
            title=title,
            journal_or_source="local file",
            local_path=str(path.resolve()),
            abstract=self._shorten(text, 800),
            keywords=self._matched_terms(text, self.search_terms)[:20],
            relevance_score=self._relevance(text),
            quality_flags={"peer_reviewed": False, "local_input": True},
            raw_text=text,
        )

    def _load_csv_sources(self, path: Path, start_idx: int, limit: int) -> list[SourceRecord]:
        rows: list[SourceRecord] = []
        scanned = 0
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if len(rows) >= limit:
                    break
                if scanned >= self.max_csv_rows:
                    break
                scanned += 1
                text = self._row_text(row)
                source_id = f"SRC-{start_idx + len(rows):04d}"
                source = SourceRecord(
                    source_id=source_id,
                    source_type=row.get("source_type") or self._csv_source_type(row),
                    doi=self._blank_to_none(row.get("doi")),
                    title=self._csv_title(row, source_id),
                    authors=self._split_authors(row.get("authors")),
                    journal_or_source=self._blank_to_none(row.get("journal") or row.get("source") or row.get("Source_File")),
                    year=self._parse_int(row.get("year")),
                    url=self._blank_to_none(row.get("url")),
                    local_path=str(path.resolve()),
                    abstract=self._blank_to_none(row.get("abstract") or text),
                    keywords=self._matched_terms(text, self.search_terms)[:20],
                    relevance_score=self._relevance(text),
                    quality_flags={
                        "peer_reviewed": (row.get("peer_reviewed") or "").lower() == "true",
                        "local_input": True,
                        "extracted_catalyst_table": "Entity" in row and "Active_Phase" in row,
                    },
                    raw_text=text,
                )
                if self._passes_source_filter(source):
                    rows.append(source)
        return rows

    def _candidate_sentences(self, text: str) -> list[str]:
        return [sentence for sentence, _location in self._candidate_sentences_with_location(text)]

    def _candidate_sentences_with_location(self, text: str) -> list[tuple[str, str]]:
        clean = self._normalize_text(text)
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", clean) if part.strip()]
        if not paragraphs and clean.strip():
            paragraphs = [clean.strip()]
        out: list[tuple[str, str]] = []
        for paragraph_idx, paragraph in enumerate(paragraphs, start=1):
            parts = re.split(r"(?<=[.!?。！？])\s+|[;\n]+", paragraph)
            sentence_idx = 0
            for part in parts:
                sentence = part.strip()
                if not (40 <= len(sentence) <= 500):
                    continue
                sentence_idx += 1
                out.append((sentence, f"paragraph {paragraph_idx}, sentence {sentence_idx}"))
        return out

    def _protocol_hints(self, text: str, topic: str) -> list[str]:
        lower = self._normalize_text(" ".join([text, topic])).lower()
        mapping = [
            ("slab_model_construction_protocol", ["slab", "surface", "interface", "support", "ceria", "ceo2"]),
            ("oxygen_vacancy_formation_protocol", ["oxygen vacancy", "vacancy formation", "ce3+", "defect"]),
            ("adsorption_energy_protocol", ["adsorption", "adsorb", "binding energy", "intermediate"]),
            ("adsorbate_configuration_screening_protocol", ["configuration", "adsorption site", "site screening", "coverage"]),
            ("reaction_energy_path_protocol", ["reaction path", "pathway", "mechanism", "rate-determining", "rds"]),
            ("neb_barrier_protocol", ["neb", "barrier", "transition state", "activation energy", "dissociation"]),
            ("bader_charge_protocol", ["bader", "charge transfer", "charge density difference"]),
            ("pdos_analysis_protocol", ["pdos", "density of states", "d-band", "electronic structure"]),
            ("cohp_analysis_protocol", ["cohp", "bonding analysis"]),
            ("microkinetic_model_protocol", ["microkinetic", "turnover frequency", "tof", "kinetic model"]),
            ("mlip_prescreening_protocol", ["machine learning potential", "mlip", "neural network potential"]),
        ]
        hints = [protocol for protocol, markers in mapping if any(marker in lower for marker in markers)]
        if "dft" in lower and not hints:
            hints.extend(["slab_model_construction_protocol", "adsorption_energy_protocol"])
        return list(dict.fromkeys(hints))

    def _software_hints(self, text: str) -> list[str]:
        software = ["VASP", "Quantum ESPRESSO", "CP2K", "CASTEP", "GPAW", "Gaussian", "LAMMPS", "LASP"]
        lower = text.lower()
        found: list[str] = []
        for name in software:
            if name.lower() in lower:
                found.append(name)
        if re.search(r"\bQE\b", text):
            found.append("Quantum ESPRESSO")
        return list(dict.fromkeys(found))

    def _parameter_hints(self, text: str) -> list[str]:
        patterns = [
            r"\bPBE\b",
            r"\bRPBE\b",
            r"\bSCAN\b",
            r"\bBEEF[- ]?vdW\b",
            r"\bDFT\+U\b",
            r"\bU\s*=\s*\d+(?:\.\d+)?\s*eV\b",
            r"\bD3\b",
            r"\bvdW\b",
            r"\bcut[- ]?off[^.;,]{0,40}",
            r"\bk[- ]?points?[^.;,]{0,40}",
            r"\bvacuum[^.;,]{0,40}",
            r"\bsupercell[^.;,]{0,40}",
            r"\bslab[^.;,]{0,40}",
        ]
        hints: list[str] = []
        for pattern in patterns:
            hints.extend(match.group(0).strip() for match in re.finditer(pattern, text, flags=re.I))
        return list(dict.fromkeys(hints))[:12]

    def _reference_state_hints(self, text: str, topic: str) -> list[str]:
        lower = self._normalize_text(" ".join([text, topic])).lower()
        hints: list[str] = []
        if "clean" in lower or "pristine" in lower:
            hints.append("clean slab")
        if "oxygen vacancy" in lower or "defect" in lower:
            hints.append("defective slab with oxygen vacancy")
        if "n2" in lower:
            hints.append("gas-phase N2")
        if "h2" in lower:
            hints.append("gas-phase H2")
        if "nh3" in lower:
            hints.append("gas-phase NH3")
        if "oxygen chemical potential" in lower or "o-rich" in lower or "o-poor" in lower:
            hints.append("oxygen chemical potential reference")
        return list(dict.fromkeys(hints))

    def _calculation_type(self, text: str, protocol_hints: list[str]) -> str:
        lower = text.lower()
        if "neb" in lower or "transition state" in lower:
            return "barrier_or_transition_state"
        if "bader" in lower or "pdos" in lower or "cohp" in lower:
            return "electronic_structure_analysis"
        if "adsorption" in lower or "binding energy" in lower:
            return "adsorption_energy"
        if "microkinetic" in lower:
            return "microkinetic_model"
        if "oxygen_vacancy_formation_protocol" in protocol_hints:
            return "defect_formation_energy"
        if "dft" in lower:
            return "dft_calculation"
        return "unknown"

    def _detect_topic(self, text: str) -> tuple[str, list[str]]:
        lower = self._normalize_text(text).lower()
        for topic, keywords in TOPIC_KEYWORDS.items():
            if any(keyword.lower() in lower for keyword in keywords):
                return topic, keywords
        return "general catalysis question", []

    def _matched_terms(self, text: str, terms: list[str]) -> list[str]:
        lower = self._normalize_text(text).lower()
        return [term for term in terms if term and term.lower() in lower]

    def _classify_claim(self, text: str) -> ClaimType:
        lower = self._normalize_text(text).lower()
        if any(marker.lower() in lower for marker in GAP_MARKERS):
            return ClaimType.GAP
        if any(marker.lower() in lower for marker in METHOD_MARKERS):
            return ClaimType.METHOD
        if any(marker in lower for marker in ("activity", "selectivity", "stability", "performance")):
            return ClaimType.VALUE
        return ClaimType.CONSENSUS

    def _claim_text(self, sentence: str) -> str:
        return f"Source states or discusses: {sentence.strip()}"

    def _confidence(self, sentence: str, matched_terms: list[str]) -> float:
        score = 0.45 + min(0.35, 0.05 * len(matched_terms))
        if self._classify_claim(sentence) in {ClaimType.GAP, ClaimType.CONTROVERSY}:
            score += 0.05
        return round(min(score, 0.9), 2)

    def _relevance(self, text: str) -> float:
        matches = self._matched_terms(text, self.search_terms)
        return round(min(1.0, len(matches) / max(6, len(self.search_terms) * 0.25)), 2)

    def _strength(self, count: int) -> str:
        if count >= 4:
            return "high"
        if count >= 2:
            return "medium"
        return "low"

    def _title_from_text(self, text: str) -> str | None:
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("![](") or stripped.startswith("|"):
                continue
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
            if len(stripped) >= 12:
                return self._shorten(stripped, 120)
        return None

    def _shorten(self, text: str, limit: int) -> str:
        clean = re.sub(r"\s+", " ", text).strip()
        return clean if len(clean) <= limit else clean[: limit - 3] + "..."

    def _row_text(self, row: dict[str, str | None]) -> str:
        preferred_keys = [
            "title",
            "abstract",
            "key_findings",
            "notes",
            "limitations",
            "methods",
            "Entity",
            "Active_Phase",
            "Support",
            "Promoter",
            "Structure",
            "Size",
            "Temperature",
            "Pressure",
            "Yield",
            "Unit",
            "Condition_Notes",
            "Source_File",
            "Source_Path",
            "Text_Files",
        ]
        parts = [str(row.get(key) or "") for key in preferred_keys]
        if not any(parts):
            parts = [str(value or "") for value in row.values()]
        return self._normalize_text(" ".join(parts))

    def _csv_source_type(self, row: dict[str, str | None]) -> str:
        if "Entity" in row and "Active_Phase" in row:
            return "extracted_catalyst_record"
        return "csv_record"

    def _csv_title(self, row: dict[str, str | None], source_id: str) -> str:
        for key in ("title", "Source_File", "Entity"):
            value = self._blank_to_none(row.get(key))
            if value:
                return value
        return f"CSV source {source_id}"

    def _split_authors(self, authors: str | None) -> list[str]:
        if not authors:
            return []
        return [item.strip() for item in re.split(r";|,", authors) if item.strip()]

    def _parse_int(self, value: str | None) -> int | None:
        if not value:
            return None
        try:
            return int(float(value))
        except ValueError:
            return None

    def _blank_to_none(self, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    def _source_key(self, source: SourceRecord) -> str:
        title = re.sub(r"\W+", "", self._normalize_text(source.title).lower())
        if title:
            return title
        return re.sub(r"\W+", "", Path(source.local_path or source.source_id).stem.lower())

    def _passes_source_filter(self, source: SourceRecord) -> bool:
        text = self._normalize_text(" ".join([source.title, source.abstract or "", source.raw_text or "", source.local_path or ""]))
        include_keywords = list(self.filters.get("include_keywords", []) or [])
        exclude_keywords = list(self.filters.get("exclude_keywords", []) or [])
        if include_keywords and not self._matched_terms(text, include_keywords):
            return False
        if exclude_keywords and self._matched_terms(text, exclude_keywords):
            return False
        if not self._passes_keyword_groups(text, self.filters.get("required_keyword_groups", []) or []):
            return False
        title_path = self._normalize_text(" ".join([source.title, source.local_path or ""]))
        if not self._passes_keyword_groups(
            title_path,
            self.filters.get("title_path_required_keyword_groups", []) or [],
        ):
            return False
        min_relevance = float(self.filters.get("min_relevance_score", 0.0))
        if source.relevance_score < min_relevance:
            return False
        return True

    def _passes_keyword_groups(self, text: str, groups: list[list[str]]) -> bool:
        for group in groups:
            if group and not self._matched_terms(text, list(group)):
                return False
        return True

    def _normalize_text(self, text: str) -> str:
        replacements = {
            "<sub>2</sub>": "2",
            "<sub>3</sub>": "3",
            "<sub>4</sub>": "4",
            "<sub>x</sub>": "x",
            "<sup>3+</sup>": "3+",
            "<sup>4+</sup>": "4+",
            "<sup>0</sup>": "0",
            "$CeO_2$": "CeO2",
            "CeO_2": "CeO2",
            "$N_2$": "N2",
            "N_2": "N2",
            "$H_2$": "H2",
            "H_2": "H2",
            "$NH_3$": "NH3",
            "NH_3": "NH3",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("Ru clusters/ CeO2", "Ru clusters/CeO2")
        text = text.replace("Ru NPs/ CeO2", "Ru NPs/CeO2")
        return text

    def _trim_reference_section(self, text: str) -> str:
        markers = [
            "\n## ASSOCIATED CONTENT",
            "\n## AUTHOR INFORMATION",
            "\n## REFERENCES",
            "\n# REFERENCES",
            "\nREFERENCES",
            "\nReferences",
        ]
        cut = len(text)
        for marker in markers:
            idx = text.find(marker)
            if idx != -1:
                cut = min(cut, idx)
        return text[:cut]
