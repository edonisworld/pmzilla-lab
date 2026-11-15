#!/usr/bin/env python3
"""Assemblage de .claude/settings.json à partir des fragments de règles deny par sujet (R-137, idée #420).

    python3 tools/settings_assemble.py [--check] [--root DOSSIER]
    python3 tools/settings_assemble.py --write [--allow-fewer] [--root DOSSIER]

Sources : .claude/settings.base.json (tout le fichier de réglages, la liste permissions.deny y est vide), .claude/deny/ORDRE (la liste
ordonnée des fragments, un nom de fichier par ligne) et les fragments .claude/deny/<nn>-<sujet>.txt (une règle par ligne, dans l'ordre où
elle apparaît dans les réglages). L'assemblage met les règles des fragments, dans l'ordre de ORDRE, dans permissions.deny, et écrit le
JSON standard (indentation de 2, caractères non ASCII conservés, saut de ligne final).

--check (défaut) : compare l'assemblage au fichier de réglages actuel, sans rien écrire, avec un diff court en positions (jamais le texte
d'une règle : seulement le rang dans les réglages, le fragment et la ligne).
--write : affiche ce diff court, puis écrit .claude/settings.json de façon atomique (fichier temporaire dans .claude/, fsync, mode du
fichier existant conservé, remplacement). C'est le seul geste d'écriture de l'outil ; il est lancé par l'auteur, jamais par une session.
--allow-fewer : sans cette option, --write refuse d'écrire quand le nombre de règles deny baisse par rapport au fichier actuel.

Codes de sortie
0 : identique, ou fichier écrit (--write).
1 : différent (--check), avec le diff court.
2 : usage ou refus, rien n'est écrit.

Refus (code 2, jamais d'écriture) : un fragment en double dans ORDRE, un nom d'ORDRE qui n'a pas la forme nn-sujet.txt, un fragment listé
et absent, un fragment présent dans le dossier (hors fichiers cachés) et inconnu de ORDRE, un fragment vide ou illisible, une ligne vide,
une règle en double (dans un fragment ou entre deux), une règle Write ou NotebookEdit, seule ou avec motif (Claude Code les ignore :
utiliser Edit(...)), une règle sans la forme Outil(motif), nom d'outil seul ou mcp__serveur__outil, une liste permissions.deny non vide
dans la base, une baisse du nombre de règles sans --allow-fewer. Le message nomme le fragment et la ligne, jamais la règle.

Exemple :
    python3 tools/settings_assemble.py --check
"""
import argparse
import difflib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
CHEMIN_REGLAGES = ".claude/settings.json"
CHEMIN_BASE = ".claude/settings.base.json"
DOSSIER_FRAGMENTS = ".claude/deny"
NOM_ORDRE = "ORDRE"
PREFIXE = "settings_assemble : "
FORME = re.compile(r"^(?:[A-Za-z]+\(.+\)|[A-Za-z]+|mcp__[A-Za-z0-9-]+__[A-Za-z0-9_-]+(?:\(.+\))?)$")
NOM_FRAGMENT = re.compile(r"^\d{2}-[a-z0-9-]+\.txt$")
ECRITURES_IGNOREES = ("Write", "NotebookEdit")
MAX_LIGNES_DIFF = 10


class Refus(Exception):
    """Une source que l'assemblage refuse (code 2) : le message nomme le fragment et la ligne, jamais la règle."""


def lire_ordre(racine: Path) -> list[str]:
    chemin = racine / DOSSIER_FRAGMENTS / NOM_ORDRE
    try:
        texte = chemin.read_bytes().decode("utf-8")  # octets : read_text normaliserait les fins de ligne CRLF
    except (OSError, UnicodeDecodeError):
        raise Refus(f"liste ordonnée illisible ({DOSSIER_FRAGMENTS}/{NOM_ORDRE})")
    noms, vus = [], set()
    for numero, ligne in enumerate(texte.split("\n"), 1):
        if ligne == "" and numero == len(texte.split("\n")):
            continue  # dernier saut de ligne
        if ligne.strip() == "" or ligne != ligne.strip():
            raise Refus(f"{NOM_ORDRE}, ligne {numero} : ligne vide ou avec espaces")
        if not NOM_FRAGMENT.match(ligne):
            raise Refus(f"{NOM_ORDRE}, ligne {numero} : nom de fragment invalide (attendu nn-sujet.txt)")
        if ligne in vus:
            raise Refus(f"fragment en double dans {NOM_ORDRE} : {ligne} (ligne {numero})")
        vus.add(ligne)
        noms.append(ligne)
    if not noms:
        raise Refus(f"liste ordonnée vide ({NOM_ORDRE})")
    return noms


def controle_dossier(racine: Path, noms: list[str]) -> None:
    dossier = racine / DOSSIER_FRAGMENTS
    presents = sorted(p.name for p in dossier.iterdir() if p.is_file() and p.name != NOM_ORDRE and not p.name.startswith("."))
    for nom in presents:
        if nom not in noms:
            raise Refus(f"fragment inconnu de la liste ordonnée : {nom}")
    for nom in noms:
        if not (dossier / nom).is_file():
            raise Refus(f"fragment listé et absent : {nom}")


def lire_fragment(racine: Path, nom: str) -> list[str]:
    try:
        texte = (racine / DOSSIER_FRAGMENTS / nom).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        raise Refus(f"fragment illisible : {nom}")
    lignes = texte.split("\n")
    if lignes and lignes[-1] == "":
        lignes.pop()
    if not lignes:
        raise Refus(f"fragment vide : {nom}")
    for numero, ligne in enumerate(lignes, 1):
        if ligne.strip() == "" or ligne != ligne.strip():
            raise Refus(f"{nom}, ligne {numero} : ligne vide ou avec espaces autour")
        if ligne in ECRITURES_IGNOREES or ligne.startswith(tuple(f"{o}(" for o in ECRITURES_IGNOREES)):
            raise Refus(f"{nom}, ligne {numero} : règle Write ou NotebookEdit, ignorée par Claude Code (utiliser Edit)")
        if not FORME.match(ligne):
            raise Refus(f"{nom}, ligne {numero} : règle mal formée (attendu Outil(motif))")
    return lignes


def regles_ordonnees(racine: Path) -> tuple[list[str], list[tuple[str, int]]]:
    """Les règles dans l'ordre de ORDRE, et pour chacune son origine (fragment, ligne)."""
    noms = lire_ordre(racine)
    controle_dossier(racine, noms)
    regles, origines, vues = [], [], {}
    for nom in noms:
        for numero, regle in enumerate(lire_fragment(racine, nom), 1):
            if regle in vues:
                autre_nom, autre_ligne = vues[regle]
                raise Refus(f"règle en double : {nom} ligne {numero}, déjà dans {autre_nom} ligne {autre_ligne}")
            vues[regle] = (nom, numero)
            regles.append(regle)
            origines.append((nom, numero))
    return regles, origines


def assembler(racine: Path) -> tuple[str, list[str], list[tuple[str, int]]]:
    regles, origines = regles_ordonnees(racine)
    try:
        base = json.loads((racine / CHEMIN_BASE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Refus(f"base illisible ou JSON invalide ({CHEMIN_BASE})")
    permissions = base.get("permissions") if isinstance(base, dict) else None
    if not isinstance(permissions, dict) or permissions.get("deny") != []:
        raise Refus(f"{CHEMIN_BASE} : permissions.deny doit exister et être vide (les règles viennent des fragments)")
    permissions["deny"] = regles
    texte = json.dumps(base, indent=2, ensure_ascii=False) + "\n"
    return texte, regles, origines


def diff_court(actuel: str, regles: list[str], origines: list[tuple[str, int]]) -> list[str]:
    """Quelques lignes de positions, sans jamais citer une règle."""
    try:
        reglages = json.loads(actuel)
        anciennes = list(reglages["permissions"]["deny"])
    except (ValueError, KeyError, TypeError):
        return ["le fichier de réglages n'est pas un JSON avec permissions.deny"]
    lignes = [f"règles dans les réglages : {len(anciennes)} ; dans l'assemblage : {len(regles)}"]
    for etiquette, i1, i2, j1, j2 in difflib.SequenceMatcher(None, anciennes, regles, autojunk=False).get_opcodes():
        if etiquette == "equal":
            continue
        debut = origines[j1] if j1 < len(origines) else None
        lieu = f", assemblage {debut[0]} ligne {debut[1]}" if debut else ""
        lignes.append(f"{etiquette} : réglages rangs {i1 + 1} à {i2}, assemblage rangs {j1 + 1} à {j2}{lieu}")
    if len(lignes) == 1:
        lignes.append("mêmes règles dans le même ordre : la différence est dans le reste du fichier ou sa mise en forme")
    if len(lignes) > MAX_LIGNES_DIFF:
        reste = len(lignes) - MAX_LIGNES_DIFF
        lignes = lignes[:MAX_LIGNES_DIFF] + [f"... {reste} autre(s) différence(s)"]
    return lignes


def ecrire(chemin: Path, texte: str, regles: list[str], origines: list[tuple[str, int]], allow_fewer: bool) -> int:
    """--write : diff court, garde sur la baisse du nombre de règles, puis écriture atomique."""
    mode = 0o644
    actuel = None
    try:
        if chemin.exists():
            mode = stat.S_IMODE(chemin.stat().st_mode)
            actuel = chemin.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        actuel = None
    if actuel == texte:
        print(f"{PREFIXE}identique ({len(regles)} règles deny), rien à écrire")
        return 0
    if actuel is not None:
        for ligne in diff_court(actuel, regles, origines):
            print(f"  {ligne}")
        try:
            anciennes = len(json.loads(actuel)["permissions"]["deny"])
        except (ValueError, KeyError, TypeError):
            anciennes = None
        if anciennes is not None and len(regles) < anciennes and not allow_fewer:
            print(f"{PREFIXE}refus : le nombre de règles deny baisse ({anciennes} dans les réglages, {len(regles)} dans l'assemblage) ; "
                  "--allow-fewer si le retrait est voulu")
            return 2
    temporaire = None
    try:
        descripteur, temporaire = tempfile.mkstemp(dir=chemin.parent, prefix=".settings-", suffix=".tmp")
        with os.fdopen(descripteur, "w", encoding="utf-8", newline="\n") as sortie:
            sortie.write(texte)
            sortie.flush()
            os.fsync(sortie.fileno())
        os.chmod(temporaire, mode)
        os.replace(temporaire, chemin)
        temporaire = None
    except OSError as erreur:
        print(f"{PREFIXE}écriture impossible, {CHEMIN_REGLAGES} inchangé ({type(erreur).__name__})")
        return 2
    finally:
        if temporaire is not None:
            try:
                os.unlink(temporaire)
            except OSError:
                pass
    print(f"{PREFIXE}{CHEMIN_REGLAGES} écrit ({len(regles)} règles deny)")
    return 0


def principal(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(prog="settings_assemble.py", add_help=True)
    mode = parseur.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="compare l'assemblage au fichier actuel (défaut)")
    mode.add_argument("--write", action="store_true", help="écrit .claude/settings.json (lancé par l'auteur seul)")
    parseur.add_argument("--allow-fewer", action="store_true", help="--write : accepte une baisse du nombre de règles deny")
    parseur.add_argument("--root", default=str(RACINE), help="racine du dépôt (tests)")
    try:
        options = parseur.parse_args(argv)
    except SystemExit as sortie:
        return 2 if sortie.code else 0
    racine = Path(options.root)
    try:
        texte, regles, origines = assembler(racine)
    except Refus as refus:
        print(f"{PREFIXE}refus : {refus}")
        return 2
    chemin = racine / CHEMIN_REGLAGES
    if options.write:
        return ecrire(chemin, texte, regles, origines, options.allow_fewer)
    try:
        actuel = chemin.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        print(f"{PREFIXE}{CHEMIN_REGLAGES} absent ou illisible")
        return 1
    if actuel == texte:
        print(f"{PREFIXE}identique ({len(regles)} règles deny)")
        return 0
    print(f"{PREFIXE}{CHEMIN_REGLAGES} diffère de l'assemblage")
    for ligne in diff_court(actuel, regles, origines):
        print(f"  {ligne}")
    return 1


if __name__ == "__main__":
    sys.exit(principal())
