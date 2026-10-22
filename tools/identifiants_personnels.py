#!/usr/bin/env python3
"""
PMZilla Lab : cherche les identifiants personnels de l'auteur dans les fichiers suivis par Git.

    python3 tools/identifiants_personnels.py [--racine DOSSIER] [--exclure CHEMIN ...] [--lignes]
    python3 tools/identifiants_personnels.py --fichier TEXTE [--racine DOSSIER] [--lignes]
    python3 tools/identifiants_personnels.py --arbre DOSSIER [--racine DOSSIER] [--lignes]

Condition de publication de la version anglaise (plan, section 6.1) : aucun fichier suivi de l'édition ne contient le
nom d'utilisateur de l'auteur ni un chemin de dossier personnel (/home/<nom> ou son équivalent macOS), ni le chemin du workspace réel (qui figure
dans les sanctums créés depuis les modèles). Depuis le lot 6, la recherche porte aussi sur les sanctums eux-mêmes :
chaque modèle de skill est instancié par init-sanctum.py dans un dossier temporaire et le résultat est cherché comme
un fichier suivi (un modèle qui réintroduirait un chemin absolu au moment de la création est ainsi repéré).

Les identifiants ne sont écrits dans aucun fichier suivi : ils viennent du compte de la session (`getpass`, nom du
dossier personnel, sauf compte générique comme « node » du conteneur de la CI locale), du chemin de la racine, au besoin du fichier d'identifiants locaux `.pmzilla/identifiants.txt`, lu en place dans le dossier de contenu (un par ligne, local, ignoré par
Git) et de l'identifiant d'auteur du module des cas, clé `author` de `.pmzilla/cases.yaml` (local, ignoré par Git ; la
variable d'environnement PMZILLA_LAB_CASES_AUTHOR n'est pas lue ; un fichier illisible donne le code 2). La recherche ignore la casse. Les fichiers personnels hors édition sont exclus : bibliotheque-lacunes.md, le plan de la version anglaise et les tables rondes (_bmad-output/pmzilla/table-ronde/).

Sortie : le nombre d'occurrences par fichier (avec --lignes : le numéro des lignes), jamais l'identifiant ni le texte de
la ligne. Code de sortie 0 sans occurrence, 1 sinon, 2 en cas d'erreur.
Avec --fichier, seul ce fichier texte (suivi ou non, par exemple un message de commit) est cherché, avec les mêmes
identifiants et la même sortie ; un chemin absent donne le code 2 et un message qui le nomme.
Avec --arbre, tout fichier texte ordinaire du dossier donné est cherché, Git ou non, avec les identifiants de --racine
(jamais ceux du dossier donné : son .pmzilla/ n'est pas lu), sans exclusion par défaut ; --exclure est refusé (code 2),
tout comme un dossier absent. Les sanctums sont créés depuis les skills de posture de ce dossier ; les chemins sortent
relatifs à lui. La fonction chercher_arbre(arbre, racine) donne le même résultat que chercher.
"""
from __future__ import annotations

import argparse
import getpass
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_paths  # noqa: E402

POSTURES = ("delivery", "discovery", "scaling", "facilitation")

EXCLUS_PAR_DEFAUT = ("docs/pmzilla/bibliotheque-lacunes.md", "docs/pmzilla/version-anglaise.md",
                     "_bmad-output/pmzilla/table-ronde/")   # un chemin qui finit par « / » exclut tout le dossier
SUFFIXES_TEXTE_IGNORES = (".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".woff", ".woff2", ".zip")
# Comptes génériques (image officielle de Node du conteneur de la CI locale, root, exécuteurs de CI) : un mot banal, pas
# un identifiant de l'auteur ; ignorés quand ils viennent du compte de la session ou du nom du dossier personnel, jamais
# quand ils sont écrits dans le fichier d'identifiants locaux. Le chemin de la racine reste cherché.
COMPTES_GENERIQUES = ("node", "root", "runner")


def identifiant_auteur(racine: Path) -> str | None:
    """Valeur de la clé `author` (colonne 0) de .pmzilla/cases.yaml, sans commentaire ni guillemets ; None si absente ou vide.
    Un fichier illisible (hors UTF-8) arrête le script avec le code 2, sans écrire son contenu."""
    fichier = racine / ".pmzilla" / "cases.yaml"
    if not fichier.is_file():
        return None
    try:
        texte = fichier.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as erreur:
        print(f"fichier illisible : {fichier} ({type(erreur).__name__})", file=sys.stderr)
        raise SystemExit(2)
    for ligne in texte.splitlines():
        trouve = re.match(r"^author:(.*)$", ligne)
        if trouve:
            valeur = re.sub(r"[ \t]#.*$", "", trouve.group(1)).strip()   # espaces de tête gardés pour le commentaire
            if len(valeur) >= 2 and valeur[0] == valeur[-1] and valeur[0] in "'\"":
                valeur = valeur[1:-1].strip()
            return valeur or None
    return None


def identifiants(racine: Path) -> list[str]:
    """Identifiants à chercher (minuscules, sans doublon, 3 caractères au moins)."""
    trouves = {c for c in (getpass.getuser(), Path.home().name) if c.strip().lower() not in COMPTES_GENERIQUES}
    trouves.update((str(racine.resolve()), str(racine)))
    fichier = lab_paths.local_file_for("personal_identifiers", racine)   # lu en place, depuis un worktree aussi (R-77)
    if fichier is not None and fichier.is_file():
        trouves.update(ligne.strip() for ligne in fichier.read_text(encoding="utf-8").splitlines())
    auteur = identifiant_auteur(racine)
    if auteur:
        trouves.add(auteur)
    return sorted({t.lower() for t in trouves if len(t.strip()) >= 3})


def fichiers_suivis(racine: Path) -> list[str]:
    fait = subprocess.run(["git", "ls-files", "-z"], cwd=racine, capture_output=True, text=True)
    if fait.returncode != 0:
        raise SystemExit(f"git ls-files a échoué dans {racine} : {fait.stderr.strip()}")
    return [n for n in fait.stdout.split("\0") if n]


def chercher(racine: Path, exclus: tuple[str, ...], cherches: list[str] | None = None) -> dict[str, list[int]]:
    """Fichier suivi -> numéros des lignes qui contiennent un identifiant."""
    cherches = cherches if cherches is not None else identifiants(racine)
    trouves: dict[str, list[int]] = {}
    for nom in fichiers_suivis(racine):
        if nom in exclus or any(e.endswith("/") and nom.startswith(e) for e in exclus) or nom.lower().endswith(SUFFIXES_TEXTE_IGNORES):
            continue
        chemin = racine / nom
        try:
            texte = chemin.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeDecodeError):
            continue   # lien cassé, fichier binaire
        lignes = [n for n, ligne in enumerate(texte.splitlines(), 1) if any(c in ligne.lower() for c in cherches)]
        if lignes:
            trouves[nom] = lignes
    return trouves


def chercher_dans_les_sanctums(racine: Path, cherches: list[str] | None = None,
                               source: Path | None = None) -> dict[str, list[int]]:
    """Sanctum généré par init-sanctum.py (dans un dossier temporaire) -> numéros des lignes qui contiennent un identifiant.
    Les clés sont « sanctum:<posture>/<fichier> ». Un skill sans init-sanctum.py est ignoré.
    `source` : dossier qui porte les skills (par défaut la racine) ; les identifiants restent ceux de la racine."""
    cherches = cherches if cherches is not None else identifiants(racine)
    trouves: dict[str, list[int]] = {}
    for posture in POSTURES:
        skill = (source if source is not None else racine) / ".claude" / "skills" / f"pmzilla-{posture}-bmad"
        script = skill / "scripts" / "init-sanctum.py"
        if not script.is_file():
            continue
        with tempfile.TemporaryDirectory() as temp:
            fait = subprocess.run([sys.executable, str(script), temp, str(skill)], capture_output=True, text=True)
            if fait.returncode != 0:
                raise SystemExit(f"init-sanctum.py a échoué pour {posture} : {(fait.stderr or fait.stdout).strip()}")
            for fichier in sorted(Path(temp).rglob("*")):
                if not fichier.is_file():
                    continue
                try:
                    texte = fichier.read_text(encoding="utf-8", errors="strict")
                except (OSError, UnicodeDecodeError):
                    continue
                lignes = [n for n, ligne in enumerate(texte.splitlines(), 1) if any(c in ligne.lower() for c in cherches)]
                if lignes:
                    trouves[f"sanctum:{posture}/{fichier.relative_to(temp)}"] = lignes
    return trouves


def chercher_arbre(arbre: Path, racine: Path) -> dict[str, list[int]]:
    """Mode arbre : fichiers texte ordinaires de `arbre` (hors Git, sans exclusion) et sanctums de ses skills de posture
    -> numéros des lignes qui contiennent un identifiant de `racine`. Chemins relatifs à `arbre`."""
    arbre = Path(arbre)
    if not arbre.is_dir():
        print(f"dossier absent : {arbre}", file=sys.stderr)
        raise SystemExit(2)
    cherches = identifiants(Path(racine))
    trouves: dict[str, list[int]] = {}
    for chemin in sorted(arbre.rglob("*")):
        if chemin.is_symlink() or not chemin.is_file():
            continue
        try:
            texte = chemin.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeDecodeError):
            continue   # fichier binaire ou illisible
        lignes = [n for n, ligne in enumerate(texte.splitlines(), 1) if any(c in ligne.lower() for c in cherches)]
        if lignes:
            trouves[chemin.relative_to(arbre).as_posix()] = lignes
    trouves.update(chercher_dans_les_sanctums(Path(racine), cherches, source=arbre))
    return trouves


def chercher_dans_un_fichier(chemin: Path, cherches: list[str]) -> dict[str, list[int]]:
    """Chemin donné -> numéros des lignes qui contiennent un identifiant (vide sans occurrence)."""
    try:
        texte = chemin.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as erreur:
        print(f"fichier illisible : {chemin} ({type(erreur).__name__})", file=sys.stderr)   # le texte du fichier n'est jamais écrit
        raise SystemExit(2)
    lignes = [n for n, ligne in enumerate(texte.splitlines(), 1) if any(c in ligne.lower() for c in cherches)]
    return {str(chemin): lignes} if lignes else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Cherche les identifiants personnels de l'auteur dans les fichiers suivis")
    parser.add_argument("--racine", default=str(Path(__file__).resolve().parent.parent), help="racine du dépôt")
    parser.add_argument("--exclure", action="append", default=[], help="chemin supplémentaire à exclure (répétable)")
    parser.add_argument("--lignes", action="store_true", help="afficher aussi les numéros de ligne")
    parser.add_argument("--fichier", help="cherche seulement dans ce fichier texte (suivi ou non), par exemple un message de commit")
    parser.add_argument("--arbre", help="cherche dans tous les fichiers texte de ce dossier (Git ou non), sans exclusion, avec les identifiants de --racine")
    args = parser.parse_args()
    racine = Path(args.racine).resolve()
    if args.arbre:
        if args.exclure:
            print("--exclure est refusé avec --arbre", file=sys.stderr)
            return 2
        trouves = chercher_arbre(Path(args.arbre), racine)
    elif args.fichier:
        trouves = chercher_dans_un_fichier(Path(args.fichier), identifiants(racine))
    else:
        trouves = chercher(racine, EXCLUS_PAR_DEFAUT + tuple(args.exclure))
        trouves.update(chercher_dans_les_sanctums(racine))
    total = sum(len(v) for v in trouves.values())
    for nom, lignes in sorted(trouves.items()):
        detail = f" (lignes {', '.join(map(str, lignes))})" if args.lignes else ""
        print(f"{nom} : {len(lignes)}{detail}")
    print(f"Total : {total} ligne(s) dans {len(trouves)} fichier(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
