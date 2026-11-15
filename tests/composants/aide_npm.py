"""Aide des tests des paquets npm de Mothra (change mothra-slices, tâche 2.4) : faux package.json des trois paquets, faux verrou npm,
entrées d'inventaire et titres de procédure. Les noms et numéros de version sont fictifs.
"""
import json

from aide_composants import GUIDE, entree
from aide_node import avec_mothra, entree_mothra

PAQUET_JSON = "mothra/package.json"
VERROU = "mothra/package-lock.json"
PROC_PAQUET = "Update a Mothra npm package"
PROC_NPM = "Update the npm of Mothra"
NODE = "90.1.0"      # version fictive de mothra/.node-version
NPM = "91.2.3"       # version fictive de npm


def entree_npm() -> dict:
    return entree("npm", "npm-runtime", PAQUET_JSON, "npm registry", PROC_NPM)


def entree_paquet(nom: str) -> dict:
    return entree(nom, "npm-package", VERROU, "npm registry", PROC_PAQUET)


def package_json(nom: str, dependances: dict | None = None, dev: dict | None = None) -> str:
    donnees = {"name": nom, "version": "0.0.0", "private": True}
    if dependances is not None:
        donnees["dependencies"] = dependances
    if dev is not None:
        donnees["devDependencies"] = dev
    return json.dumps(donnees, indent=2)


def racine_json(node: str | None = NODE, npm: str | None = NPM, engines: bool = True) -> str:
    donnees = {"name": "mothra", "private": True, "workspaces": ["contract", "server", "front"]}
    if engines:
        donnees["engines"] = {k: v for k, v in (("node", node), ("npm", npm)) if v is not None}
    return json.dumps(donnees, indent=2)


def verrou_npm(versions: dict[str, str]) -> str:
    paquets = {"": {"name": "mothra"}}
    for nom, version in versions.items():
        paquets[f"node_modules/{nom}"] = {"version": version, "resolved": "https://registry.npmjs.org/x.tgz", "integrity": "sha512-x"}
    paquets["node_modules/@mothra/contract"] = {"resolved": "contract", "link": True}
    return json.dumps({"name": "mothra", "lockfileVersion": 3, "packages": paquets}, indent=2)


def avec_npm(depot, dependances: dict | None = None, dev: dict | None = None, lock: dict | None = "auto", racine: str | None = None,
             entrees: list | None = None, guide: bool = True):
    """Ajoute au faux dépôt le Node de Mothra, les package.json (contrat : dependances ; serveur : dev ; front : aucune), le verrou
    (« auto » : celui des versions exactes déclarées ; None : absent) et les entrées d'inventaire (« auto » : npm et un paquet par
    dépendance directe)."""
    dependances = {"alpha": "1.0.0"} if dependances is None else dependances
    dev = {"beta": "2.0.0"} if dev is None else dev
    avec_mothra(depot, NODE)
    if guide:
        depot.ecrire("docs/pmzilla/installation.md", GUIDE + f"### {PROC_PAQUET}\n### {PROC_NPM}\n### Update the Node of Mothra\n")
    depot.ecrire(PAQUET_JSON, racine if racine is not None else racine_json())
    depot.ecrire("mothra/contract/package.json", package_json("@mothra/contract", dependances))
    depot.ecrire("mothra/server/package.json", package_json("@mothra/server", {"@mothra/contract": "*"}, dev))
    depot.ecrire("mothra/front/package.json", package_json("@mothra/front"))
    if lock == "auto":
        lock = {**dependances, **dev}
    if lock is not None:
        depot.ecrire(VERROU, verrou_npm(lock))
    if entrees is None:
        entrees = [entree_npm()] + [entree_paquet(n) for n in sorted({**dependances, **dev})]
    depot.modifier_inventaire(lambda tout: tout.extend([entree_mothra()] + entrees))
    return entrees
