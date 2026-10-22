"""Garde partagée des listes de règles deny déclarées (change deny-rules-review, design D1 à D3).

Pas de préfixe `test_` : le module n'est pas collecté seul. Il n'ouvre que les sources des modules à contrôler (lecture) et
n'exécute aucune commande.
"""
import importlib.util
import re
from pathlib import Path

FORME = re.compile(r"^[A-Za-z]+\(.+\)$")
MAUVAISE_FORME = "règle mal formée (vide ou sans outil)"
ECRITURE_IGNOREE = "règle Write(chemin) ou NotebookEdit(chemin) : Claude Code l'ignore ; utiliser Edit(chemin)"
DOUBLON = "règle en double"
LISTE_VIDE = "liste vide"
SANS_FONCTION = "sortie --json sans fonction de liste"
CONVENTION = "regles_attendues"


def constats(regles) -> list:
    """Un constat par règle fautive (ordre de la liste), vide si la liste passe. Forme : « <constat> : <règle> »."""
    regles = list(regles)
    if not regles:
        return [LISTE_VIDE]
    trouves, vues = [], set()
    for regle in regles:
        if not isinstance(regle, str) or not FORME.match(regle):
            trouves.append(f"{MAUVAISE_FORME} : {regle!r}")
        elif regle.startswith(("Write(", "NotebookEdit(")):
            trouves.append(f"{ECRITURE_IGNOREE} : {regle}")
        elif regle in vues:
            trouves.append(f"{DOUBLON} : {regle}")
        if isinstance(regle, str):
            vues.add(regle)
    return trouves


def imprime_json(texte: str) -> bool:
    """Le module imprime sa liste avec --json (test `"--json" in sys.argv`), pas seulement une option sous test."""
    return '"--json" in sys.argv' in texte or "'--json' in sys.argv" in texte


def _liste_du_module(chemin: Path, nom: str):
    spec = importlib.util.spec_from_file_location(f"garde_{chemin.stem}", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cible = getattr(module, nom, None)
    if cible is None:
        return None
    return list(cible()) if callable(cible) else list(cible)


def constats_modules(dossier: Path, declarations: dict) -> list:
    """Lignes d'échec « garde R-84 : <module> : <constat> » pour chaque module du dossier qui imprime une liste --json."""
    lignes = []
    for chemin in sorted(Path(dossier).glob("test_settings_deny_*.py")):
        if chemin.stem == "test_settings_deny_listes_declarees":
            continue  # ce test cite le motif dans ses essais, il n'imprime aucune liste
        if not imprime_json(chemin.read_text(encoding="utf-8")):
            continue
        liste = _liste_du_module(chemin, declarations.get(chemin.stem, CONVENTION))
        if liste is None:
            lignes.append(f"garde R-84 : {chemin.stem} : {SANS_FONCTION}")
            continue
        lignes += [f"garde R-84 : {chemin.stem} : {c}" for c in constats(liste)]
    return lignes


def constats_reglages(reglages: dict) -> list:
    """Une clé de `permissions` qui porte une liste vide ou une chaîne vide."""
    permissions = reglages.get("permissions", {})
    return [f"garde R-84 : clé de permission vide dans .claude/settings.json : {cle}"
            for cle, valeur in permissions.items() if valeur in ([], "")]
