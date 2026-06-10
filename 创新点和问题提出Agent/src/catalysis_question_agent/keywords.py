from __future__ import annotations


TOPIC_KEYWORDS: dict[str, list[str]] = {
    "oxygen vacancy": ["oxygen vacancy", "vacancy", "Ce3+", "Ce4+", "ceria defect"],
    "metal-support interaction": ["metal-support", "SMSI", "interface", "interfacial"],
    "N2 activation": ["N2 activation", "N2 dissociation", "nitrogen activation", "N=N"],
    "NHx hydrogenation": ["NHx", "NH species", "NH2", "N-H", "hydrogenation"],
    "rate-determining step": ["rate-determining", "rate limiting", "RDS", "barrier"],
    "hydrogen poisoning": ["hydrogen poisoning", "dissociated hydrogen", "H adatoms", "hydrogen adatoms"],
    "Ru cluster active site": ["sub-nanometer Ru", "Ru clusters", "B5 site", "B5 sites"],
    "reaction kinetics": ["reaction order", "Arrhenius", "activation energy", "apparent activation"],
    "electronic structure": ["Bader", "PDOS", "charge density", "electron transfer", "d-band"],
    "microkinetics": ["microkinetic", "coverage", "temperature", "pressure", "turnover"],
    "computational method": ["DFT", "NEB", "VASP", "pymatgen", "ASE", "MLIP"],
}


GAP_MARKERS = [
    "unclear",
    "unknown",
    "remain",
    "remains",
    "open",
    "lack",
    "lacks",
    "missing",
    "not fully",
    "controversial",
    "debated",
    "inconsistent",
    "争议",
    "尚不清楚",
    "缺少",
    "不足",
]


METHOD_MARKERS = ["DFT", "NEB", "Bader", "PDOS", "COHP", "microkinetic", "VASP", "ASE"]
