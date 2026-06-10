from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

import yaml

from .research_pipeline_models import CalcProtocol


DEFAULT_PROTOCOL_SOFTWARE: dict[str, list[str]] = {
    "slab_model_construction_protocol": ["pymatgen", "ASE", "AiiDA"],
    "oxygen_vacancy_formation_protocol": ["pymatgen", "AiiDA", "VASP/QE/CP2K"],
    "adsorption_energy_protocol": ["pymatgen", "ASE", "AiiDA", "VASP/QE/CP2K"],
    "adsorbate_configuration_screening_protocol": ["pymatgen", "ASE", "MatGL/CHGNet optional"],
    "reaction_energy_path_protocol": ["pandas", "AiiDA"],
    "neb_barrier_protocol": ["AiiDA", "VASP/QE/CP2K"],
    "bader_charge_protocol": ["AiiDA", "custodian", "Bader external tool"],
    "pdos_analysis_protocol": ["AiiDA", "pymatgen"],
    "cohp_analysis_protocol": ["LOBSTER optional", "pymatgen"],
    "microkinetic_model_protocol": ["pandas", "scipy"],
    "mlip_prescreening_protocol": ["MatGL", "CHGNet", "FAIR-Chem optional"],
}


DEFAULT_PROTOCOL_SCAFFOLDS: dict[str, list[str]] = {
    "slab_model_construction_protocol": ["pymatgen", "atomate2"],
    "oxygen_vacancy_formation_protocol": ["pymatgen", "atomate2", "custodian"],
    "adsorption_energy_protocol": ["pymatgen", "ASE", "aiida-core"],
    "adsorbate_configuration_screening_protocol": ["pymatgen", "ASE", "MatGL", "CHGNet"],
    "reaction_energy_path_protocol": ["aiida-core", "pymatgen"],
    "neb_barrier_protocol": ["aiida-core", "aiida-vasp", "aiida-quantumespresso"],
    "bader_charge_protocol": ["custodian", "aiida-core"],
    "pdos_analysis_protocol": ["pymatgen", "aiida-core"],
    "cohp_analysis_protocol": ["pymatgen"],
    "microkinetic_model_protocol": ["jobflow"],
    "mlip_prescreening_protocol": ["MatGL", "CHGNet", "FAIR-Chem"],
}


class ProtocolRegistry:
    def __init__(self, protocols: Iterable[CalcProtocol]):
        self.protocols = {item.protocol_id: item for item in protocols}

    def get(self, protocol_id: str) -> CalcProtocol | None:
        return self.protocols.get(protocol_id)

    def require(self, protocol_id: str) -> CalcProtocol:
        protocol = self.get(protocol_id)
        if protocol is None:
            raise KeyError(f"Unknown protocol_id: {protocol_id}")
        return protocol

    def known_ids(self) -> set[str]:
        return set(self.protocols)

    def split_known_missing(self, protocol_ids: Iterable[str]) -> tuple[list[str], list[str]]:
        known: list[str] = []
        missing: list[str] = []
        for protocol_id in dict.fromkeys(protocol_ids):
            if protocol_id in self.protocols:
                known.append(protocol_id)
            else:
                missing.append(protocol_id)
        return known, missing

    def input_block_reasons(self, protocol_id: str) -> list[str]:
        protocol = self.require(protocol_id)
        reasons: list[str] = []
        if protocol.status != "executable_mvp":
            reasons.append(f"protocol_status_is_{protocol.status}")
        if not protocol.version:
            reasons.append("protocol_version_missing")
        if not protocol.applicable_systems:
            reasons.append("applicable_systems_missing")
        if not protocol.forbidden_uses:
            reasons.append("forbidden_uses_missing")
        if not protocol.reference_state_definition:
            reasons.append("reference_state_definition_missing")
        if not protocol.audit_rules:
            reasons.append("audit_rules_missing")
        if not protocol.convergence_criteria:
            reasons.append("convergence_criteria_missing")
        if not protocol.publication_text_template:
            reasons.append("publication_boundary_missing")
        return reasons

    def can_generate_input(self, protocol_id: str) -> bool:
        return not self.input_block_reasons(protocol_id)


def load_protocol_registry(path: str | Path) -> ProtocolRegistry:
    registry_path = Path(path)
    if not registry_path.exists():
        raise FileNotFoundError(f"Protocol registry not found: {registry_path}")
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    registry_status = str(data.get("status") or "planning_stub")
    registry_hash = _sha256(registry_path)
    protocols = [_protocol_from_row(row, registry_path, registry_hash, registry_status) for row in data.get("protocols", [])]
    return ProtocolRegistry(protocols)


def _protocol_from_row(row: dict, registry_path: Path, registry_hash: str, registry_status: str) -> CalcProtocol:
    protocol_id = str(row["protocol_id"])
    reference_states = row.get("reference_state_definition") or row.get("required_reference_states") or []
    audit_rules = row.get("audit_rules") or row.get("audit_checks") or []
    return CalcProtocol(
        protocol_id=protocol_id,
        name=str(row.get("name") or protocol_id.replace("_", " ").title()),
        purpose=str(row.get("purpose") or ""),
        status=str(row.get("status") or registry_status),
        applicable_systems=list(row.get("applicable_systems") or []),
        forbidden_uses=list(row.get("forbidden_uses") or []),
        software=list(row.get("software") or DEFAULT_PROTOCOL_SOFTWARE.get(protocol_id, [])),
        default_parameters=dict(row.get("default_parameters") or {}),
        convergence_criteria=dict(row.get("convergence_criteria") or {}),
        reference_state_definition=list(reference_states),
        required_controls=list(row.get("required_controls") or []),
        audit_rules=list(audit_rules),
        publication_text_template=row.get("publication_text_template"),
        version=str(row.get("version") or "mvp-0.1"),
        source_scaffolds=list(row.get("source_scaffolds") or DEFAULT_PROTOCOL_SCAFFOLDS.get(protocol_id, [])),
        source_files=[str(registry_path)],
        source_hashes={"protocol_registry": registry_hash},
        audit_status="registry_imported_needs_protocol_agent_review",
        human_review_required=True,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
