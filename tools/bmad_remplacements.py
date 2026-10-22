#!/usr/bin/env python3
"""
PMZilla Lab : rejoue, après l'installeur BMAD, les remplacements de texte que le dépôt impose aux skills installés.

    python3 tools/bmad_remplacements.py [--check] [--racine DOSSIER] [--regles FICHIER]

L'installeur BMAD ne préserve que ce qui est sous _bmad/ (fichiers absents de son manifeste, restaurés ; fichiers
modifiés, remplacés avec une copie .bak). Il réécrit sans prévenir les fichiers de .claude/skills/ : un remplacement
fait à la main dans un SKILL.md disparaît à la mise à jour. Ce script le rejoue.

Les règles sont dans .pmzilla/remplacements-bmad.tsv (local, ignoré par Git : les textes à remplacer sont des noms que le
hook des noms sensibles refuse dans les fichiers suivis). Une règle par ligne, trois colonnes séparées par une
tabulation : chemin relatif à la racine, texte à remplacer, texte de remplacement. Les lignes vides et celles qui
commencent par # sont ignorées.

Sans option, le script écrit les remplacements. Avec --check, il n'écrit rien : il liste les fichiers où un remplacement
reste à faire et sort avec le code 1 (0 sinon). La sortie ne donne que des chemins et des comptes, jamais les textes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_paths  # noqa: E402

REGLES_PAR_DEFAUT = Path(".pmzilla") / "remplacements-bmad.tsv"


def lire_regles(fichier: Path) -> list[tuple[str, str, str]]:
    regles = []
    for numero, ligne in enumerate(fichier.read_text(encoding="utf-8").splitlines(), 1):
        if not ligne.strip() or ligne.lstrip().startswith("#"):
            continue
        colonnes = ligne.split("\t")
        if len(colonnes) != 3 or not all(colonnes):
            sys.exit(f"{fichier} : ligne {numero} : attendu chemin, texte à remplacer, remplacement (trois colonnes, tabulation).")
        regles.append((colonnes[0], colonnes[1], colonnes[2]))
    return regles


def appliquer(racine: Path, regles: list[tuple[str, str, str]], ecrire: bool) -> tuple[dict[str, int], list[str]]:
    """(remplacements par fichier, fichiers absents). N'écrit que si `ecrire`."""
    faits: dict[str, int] = {}
    absents: list[str] = []
    textes: dict[str, str] = {}
    for chemin, ancien, nouveau in regles:
        cible = racine / chemin
        if not cible.is_file():
            if chemin not in absents:
                absents.append(chemin)
            continue
        texte = textes.get(chemin)
        if texte is None:
            texte = cible.read_text(encoding="utf-8")
        n = texte.count(ancien)
        if n:
            texte = texte.replace(ancien, nouveau)
            faits[chemin] = faits.get(chemin, 0) + n
        textes[chemin] = texte
    if ecrire:
        for chemin in faits:
            (racine / chemin).write_text(textes[chemin], encoding="utf-8")
    return faits, absents


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rejoue les remplacements du dépôt dans les skills BMAD installés.")
    parser.add_argument("--racine", default=str(Path(__file__).resolve().parents[1]), help="racine du dépôt")
    parser.add_argument("--regles", help="fichier de règles (défaut : le fichier local du registre des chemins du lab, lu en place)")
    parser.add_argument("--check", action="store_true", help="n'écrit rien ; code 1 s'il reste un remplacement à faire")
    args = parser.parse_args(argv)
    racine = Path(args.racine).resolve()
    fichier = Path(args.regles) if args.regles else lab_paths.local_file_for("bmad_replacements", racine)
    if fichier is None or not fichier.is_file():
        print(f"Fichier de règles absent{f' : {fichier}' if fichier else ''}. Rien à rejouer (le créer si le hook des noms sensibles refuse un SKILL.md).")
        return 0
    regles = lire_regles(fichier)
    faits, absents = appliquer(racine, regles, ecrire=not args.check)
    for chemin in absents:
        print(f"Fichier absent : {chemin}")
    verbe = "à remplacer" if args.check else "remplacé"
    for chemin, n in sorted(faits.items()):
        print(f"{chemin} : {n} occurrence(s) {verbe}")
    if not faits:
        print(f"Aucun remplacement à faire ({len(regles)} règle(s) lue(s)).")
    return 1 if (args.check and faits) else 0


if __name__ == "__main__":
    sys.exit(main())
