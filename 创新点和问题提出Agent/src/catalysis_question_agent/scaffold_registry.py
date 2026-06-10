from __future__ import annotations

from pathlib import Path


SCAFFOLD_PROJECTS = [
    {
        "name": "aiida-core",
        "url": "https://github.com/aiidateam/aiida-core.git",
        "role": "AiiDA provenance and process graph backbone",
        "phase": "active_mvp_reference",
    },
    {
        "name": "aiida-quantumespresso",
        "url": "https://github.com/aiidateam/aiida-quantumespresso.git",
        "role": "Quantum ESPRESSO CalcJob/WorkChain plugin reference",
        "phase": "active_mvp_reference",
    },
    {
        "name": "aiida-vasp",
        "url": "https://github.com/aiida-vasp/aiida-vasp.git",
        "role": "VASP CalcJob/WorkChain plugin reference",
        "phase": "active_mvp_reference",
    },
    {
        "name": "aiida-cp2k",
        "url": "https://github.com/aiidateam/aiida-cp2k.git",
        "role": "CP2K CalcJob/WorkChain plugin reference",
        "phase": "active_mvp_reference",
    },
    {
        "name": "pymatgen",
        "url": "https://github.com/materialsproject/pymatgen.git",
        "role": "Structure, slab, defect, and input helper toolkit",
        "phase": "active_mvp_reference",
    },
    {
        "name": "custodian",
        "url": "https://github.com/materialsproject/custodian.git",
        "role": "Error pattern and recovery policy reference",
        "phase": "active_mvp_reference",
    },
    {
        "name": "atomate2",
        "url": "https://github.com/materialsproject/atomate2.git",
        "role": "Protocol and TaskDocument design reference",
        "phase": "active_mvp_reference",
    },
    {
        "name": "jobflow",
        "url": "https://github.com/materialsproject/jobflow.git",
        "role": "Workflow design reference, not provenance backbone",
        "phase": "active_mvp_reference",
    },
    {
        "name": "paper-qa",
        "url": "https://github.com/Future-House/paper-qa.git",
        "role": "PaperQA2 literature RAG and citation localization reference",
        "phase": "active_mvp_reference",
    },
    {
        "name": "langgraph",
        "url": "https://github.com/langchain-ai/langgraph.git",
        "role": "Optional long-running state machine and human interrupt reference",
        "phase": "active_mvp_reference",
    },
    {
        "name": "cclib",
        "url": "https://github.com/cclib/cclib.git",
        "role": "Molecular or cluster calculation parser reference",
        "phase": "parser_extension_reference",
    },
    {
        "name": "QCEngine",
        "url": "https://github.com/MolSSI/QCEngine.git",
        "role": "Molecular quantum chemistry execution/schema reference",
        "phase": "parser_extension_reference",
    },
    {
        "name": "optimade-python-tools",
        "url": "https://github.com/Materials-Consortia/optimade-python-tools.git",
        "role": "Materials database and structure discovery reference",
        "phase": "database_extension_reference",
    },
    {
        "name": "ASE",
        "url": "https://gitlab.com/ase/ase.git",
        "role": "Atomic structure and calculator ecosystem; upstream is GitLab",
        "phase": "dependency_only_not_github",
    },
    {
        "name": "MatGL",
        "url": "https://github.com/materialsvirtuallab/matgl.git",
        "role": "Optional MLIP pre-screening backend",
        "phase": "deferred_optional",
    },
    {
        "name": "CHGNet",
        "url": "https://github.com/CederGroupHub/chgnet.git",
        "role": "Optional MLIP pre-screening backend",
        "phase": "deferred_optional",
    },
    {
        "name": "FAIR-Chem",
        "url": "https://github.com/facebookresearch/fairchem.git",
        "role": "Optional large MLIP pre-screening backend",
        "phase": "deferred_optional_large",
    },
]


def inspect_scaffolds(base_dir: str | Path) -> list[dict[str, object]]:
    base = Path(base_dir)
    manifest: list[dict[str, object]] = []
    for row in SCAFFOLD_PROJECTS:
        local_path = base / str(row["name"])
        item = dict(row)
        item["local_path"] = str(local_path)
        item["present"] = local_path.exists()
        item["head"] = _read_git_head(local_path) if local_path.exists() else None
        manifest.append(item)
    return manifest


def _read_git_head(repo_dir: Path) -> str | None:
    git_dir = repo_dir / ".git"
    head_path = git_dir / "HEAD"
    if not head_path.exists():
        return None
    head = head_path.read_text(encoding="utf-8").strip()
    if not head.startswith("ref:"):
        return head[:12]
    ref = head.split(" ", 1)[1].strip()
    ref_path = git_dir / ref
    if ref_path.exists():
        return ref_path.read_text(encoding="utf-8").strip()[:12]
    packed = git_dir / "packed-refs"
    if packed.exists():
        for line in packed.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#") or " " not in line:
                continue
            commit, packed_ref = line.split(" ", 1)
            if packed_ref.strip() == ref:
                return commit[:12]
    return None
