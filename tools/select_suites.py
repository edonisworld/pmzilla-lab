#!/usr/bin/env python3
"""Sélecteur de suites : lit les chemins de l'index Git et dit quelles suites de tests/ lancer (lancement ciblé, tests/run_all.sh --staged).

    python3 tools/select_suites.py [--root DOSSIER]

Règles (design.md D4 du change workflow-tooling) :
  - un chemin dans le dossier d'une suite (tests/<suite>/) sélectionne cette suite ; un script de test shell listé dans
    tests/run_all.sh sélectionne sa suite shell ;
  - un chemin que le texte d'un fichier de test d'une suite nomme (chemin, ou nom de module pour un .py ou .sh, ou nom de fichier pour
    les autres) sélectionne cette suite ;
  - la suite qui parcourt tous les fichiers suivis (identifiants_personnels) est toujours sélectionnée ;
  - le manuel généré (change user-manual) : un script .py ou .sh directement sous tools/, une commande de .claude/commands/ ou le
    fichier docs/pmzilla/manuel.md sélectionne en plus la suite « manual ». Ce renfort ne tient pas lieu de suite du chemin : un script
    qu'aucun test ne nomme exige toujours l'exécution complète, et le manuel est le seul fichier de documentation qui sélectionne une suite ;
  - documentation seule (docs/, openspec/, CHANGELOG.md, README.md, Markdown de _bmad-output/) : rien de plus ;
  - tout autre chemin qu'aucune suite ne nomme, et tout changement de CLAUDE.md, du fichier de réglages, du lanceur, des hooks ou
    du sélecteur, exige l'exécution complète (sûr par défaut).

Sortie : une ligne « select_suites : <suite> : <raison> » par suite (code 0), ou « select_suites : exécution complète requise : <chemins> »
(code 3). Code 2 : usage ou hors dépôt Git. Le sélecteur ne lance aucun test, n'écrit aucun fichier et ne lit que l'index et tests/.
Limites assumées : une suite qui n'exerce un fichier que par une chaîne d'imports est manquée ; un test qui nomme un fichier dans un
commentaire sélectionne sa suite pour rien. Ces manques n'atteignent jamais main (script de fin de branche et pre-push exigent un
lancement complet vert).

Exemple :
    python3 tools/select_suites.py
"""
import re
import subprocess
import sys
from pathlib import Path

PREFIXE = "select_suites : "
TOUJOURS = {"identifiants_personnels": "toujours sélectionnée : parcourt tous les fichiers suivis"}
COMPLETS = {"CLAUDE.md", ".claude/settings.json", ".claude/settings.local.json", "tests/run_all.sh", "tools/select_suites.py"}
PREFIXES_COMPLETS = ("tools/hooks/",)
DOCS_PREFIXES = ("docs/", "openspec/")
DOCS_FICHIERS = {"CHANGELOG.md", "README.md"}
SUITE_MANUEL = "manual"
CHEMIN_MANUEL = "docs/pmzilla/manuel.md"


def erreur_usage(texte: str) -> int:
    print(f"{PREFIXE}usage : {texte}", file=sys.stderr)
    return 2


def chemins_indexes(racine: Path) -> list[str] | None:
    fait = subprocess.run(["git", "diff", "--cached", "--name-only", "--no-renames", "-z"], cwd=racine, capture_output=True)
    if fait.returncode != 0:
        return None
    return [p for p in fait.stdout.decode("utf-8", errors="replace").split("\0") if p]


def documentation(chemin: str) -> bool:
    return (chemin in DOCS_FICHIERS or chemin.startswith(DOCS_PREFIXES)
            or (chemin.startswith("_bmad-output/") and chemin.endswith(".md")))


def releve_du_manuel(chemin: str) -> bool:
    """Un script directement sous tools/, une commande slash ou le manuel lui-même : le manuel généré peut changer."""
    morceaux = chemin.split("/")
    return (chemin == CHEMIN_MANUEL
            or (len(morceaux) == 2 and morceaux[0] == "tools" and chemin.endswith((".py", ".sh")))
            or (len(morceaux) == 3 and morceaux[:2] == [".claude", "commands"] and chemin.endswith(".md")))


def suites_python(racine: Path) -> list[str]:
    tests = racine / "tests"
    if not tests.is_dir():
        return []
    return sorted(d.name for d in tests.iterdir() if d.is_dir() and any(d.glob("test_*.py")))


def suites_shell(racine: Path) -> dict[str, str]:
    """{chemin du script de test shell : nom de la suite}, d'après la liste de tests/run_all.sh."""
    lanceur = racine / "tests" / "run_all.sh"
    if not lanceur.is_file():
        return {}
    texte = lanceur.read_text(encoding="utf-8", errors="replace")
    return {chemin: nom for chemin, nom in re.findall(r"(tests/\S+?\.sh):([^:\s]+):\w+", texte)}


def textes_des_suites(racine: Path, py: list[str], shell: dict[str, str]) -> dict[str, str]:
    """{suite : texte concaténé de ses fichiers de test}."""
    textes: dict[str, list[str]] = {}
    for nom in py:
        for fichier in (racine / "tests" / nom).rglob("*"):
            if fichier.is_file() and fichier.suffix in (".py", ".sh"):
                textes.setdefault(nom, []).append(fichier.read_text(encoding="utf-8", errors="replace"))
    for chemin, nom in shell.items():
        fichier = racine / chemin
        if fichier.is_file():
            textes.setdefault(nom, []).append(fichier.read_text(encoding="utf-8", errors="replace"))
    return {nom: "\n".join(parties) for nom, parties in textes.items()}


def nom_cherche(chemin: str) -> str:
    p = Path(chemin)
    return p.stem if p.suffix in (".py", ".sh") else p.name


def suites_du_chemin(chemin: str, py: list[str], shell: dict[str, str], textes: dict[str, str]) -> dict[str, str]:
    trouvees: dict[str, str] = {}
    morceaux = chemin.split("/")
    if len(morceaux) > 2 and morceaux[0] == "tests" and morceaux[1] in py:
        trouvees[morceaux[1]] = "chemin dans la suite"
    if chemin in shell:
        trouvees[shell[chemin]] = "script de test shell listé"
    nom = nom_cherche(chemin)
    motif = re.compile(r"(?<![\w.-])" + re.escape(nom) + r"(?![\w-])")
    for suite, texte in textes.items():
        if suite in trouvees:
            continue
        if chemin in texte:
            trouvees[suite] = "chemin nommé par ses tests"
        elif motif.search(texte):
            trouvees[suite] = f"« {nom} » nommé par ses tests"
    return trouvees


def selectionner(racine: Path, chemins: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    """(raisons par suite, chemins qui exigent l'exécution complète)."""
    py = suites_python(racine)
    shell = suites_shell(racine)
    textes = textes_des_suites(racine, py, shell)
    raisons: dict[str, list[str]] = {nom: [raison] for nom, raison in TOUJOURS.items()}
    complets: list[str] = []
    for chemin in chemins:
        if chemin in COMPLETS or chemin.startswith(PREFIXES_COMPLETS):
            complets.append(chemin)
            continue
        if releve_du_manuel(chemin) and SUITE_MANUEL in py:
            raisons.setdefault(SUITE_MANUEL, []).append(f"{chemin} (peut changer le manuel généré)")
        if documentation(chemin):
            continue
        suites = suites_du_chemin(chemin, py, shell, textes)
        if not suites:
            complets.append(chemin)
            continue
        for suite, motif in suites.items():
            raisons.setdefault(suite, []).append(f"{chemin} ({motif})")
    return raisons, complets


def main(argv: list[str]) -> int:
    racine = Path.cwd()
    arguments = list(argv)
    if arguments in (["-h"], ["--help"]):
        print(__doc__)
        return 0
    if arguments[:1] == ["--root"]:
        if len(arguments) < 2:
            return erreur_usage("--root demande un dossier")
        racine = Path(arguments[1])
        arguments = arguments[2:]
    if arguments:
        return erreur_usage("python3 tools/select_suites.py [--root DOSSIER]")
    chemins = chemins_indexes(racine)
    if chemins is None:
        print(f"{PREFIXE}pas un dépôt Git : {racine}", file=sys.stderr)
        return 2
    raisons, complets = selectionner(racine, chemins)
    if complets:
        print(f"{PREFIXE}exécution complète requise : {', '.join(complets)}")
        return 3
    for suite in sorted(raisons):
        print(f"{PREFIXE}{suite} : {' ; '.join(raisons[suite][:3])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
