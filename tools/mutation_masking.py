# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
PMZilla Lab : tests de mutation du code de masquage et de rôles (change masking-mutation-tests, issue #386).

    uv run tools/mutation_masking.py run                  un passage complet sur le périmètre déclaré
    uv run tools/mutation_masking.py run --due            seulement s'il est dû (étape hebdomadaire du passage quotidien)
    uv run tools/mutation_masking.py run --timeout 60     délai maximal par mutant, en secondes
    uv run tools/mutation_masking.py report               relit le dernier passage enregistré

Mutateur maison, bibliothèque standard seulement (décision Q8 du 2026-10-20 : l'essai de mutmut a échoué) : aucune dépendance tierce,
aucune entrée dans docs/pmzilla/composants.yaml. Le programme analyse chaque cible avec ast et ne mute que les fonctions et les
constantes déclarées dans PERIMETRE (design D2), un mutant à la fois, en remplaçant le seul segment du nœud muté. Opérateurs :
comparaison (< et >=, <= et >, == et !=, is et is not), constante (entier n vers n + 1 puis n - 1), max_min, appartenance (in et
not in), negation (condition d'un if, d'une expression conditionnelle ou d'un while niée ; not x devient x ; True et False échangés),
retour_none (return expr devient return None). Rien n'est muté dans une chaîne formatée.

Isolation (D3) : copie des fichiers suivis de HEAD (git archive) dans un dossier temporaire créé ici et retiré à la fin, dont un dépôt Git
jetable est fait sur place ; l'arbre du dépôt et son .git ne sont jamais écrits. Les suites tournent dans la copie (python -m unittest discover), sans aucune variable héritée
PMZILLA_LAB_DB_*, PG* ni DBTEST_PORT, avec des valeurs neutres (adresse sur le port 1, lecteur de Trousseau inexistant, PGPORT=1) :
un mutant qui contourne une garde échoue sans atteindre le Trousseau ni un serveur. Avant tout mutant, chaque suite tourne une fois
sur la copie intacte ; un délai dépassé tue le mutant (groupe de processus compris) et compte comme tué, dit dans le rapport. La
sortie des suites n'est jamais affichée.

Sortie : une ligne par cible, le résumé (tués, total, délais, score, seuil, cible), une ligne par survivant et par délai (fichier,
fonction, ligne, opérateur), jamais de code, de diff ni de donnée. Seuil : tools/mutation_masking_seuil.txt (plancher de 50 à 100,
puis cible informative). Il n'existe aucune liste de survivants tolérés : un survivant se corrige par un test.

État : $PMZILLA_LAB_DATA/mutation-etat.json (défaut ~/.pmzilla-lab ; droits du seul propriétaire, écriture atomique). --due : seulement
si aucune tentative aujourd'hui et si c'est le jour hebdomadaire ou que le dernier passage complet a plus de 7 jours (ou n'existe pas).
Jamais lancé par tests/run_all.sh.

Variables d'environnement : PMZILLA_LAB_DATA, PMZILLA_LAB_TODAY (AAAA-MM-JJ, tests), PMZILLA_MUTATION_DAY (jour hebdomadaire, lundi
par défaut).

Codes de sortie
run : 0 score au moins égal au seuil (ou pas dû), 2 usage ou lancement impossible (seuil, état, copie, suite de référence), 3 sous le seuil
report : 0 dernier passage affiché (ou aucun), 2 usage ou état illisible
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import io
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
SEUIL_RELATIF = "tools/mutation_masking_seuil.txt"
FICHIER_ETAT = "mutation-etat.json"
PREFIXE = "mutation : "
DELAI_MINIMUM = 10          # secondes : délai par mutant au moins égal à ceci...
FACTEUR_DELAI = 5           # ... et à cinq fois la durée de la suite de référence
DELAI_REFERENCE = 900       # secondes : délai de la suite de référence
BORNES_SEUIL = (50, 100)
JOURS = {"monday": 0, "lundi": 0, "tuesday": 1, "mardi": 1, "wednesday": 2, "mercredi": 2, "thursday": 3, "jeudi": 3,
         "friday": 4, "vendredi": 4, "saturday": 5, "samedi": 5, "sunday": 6, "dimanche": 6}

# Interpréteur des suites : les paquets du lanceur de tests utiles aux cibles, pris dans le cache de uv.
LANCEUR = ("uv", "run", "--quiet", "--with", "numpy", "--with", "pyyaml", "--with", "psycopg[binary]", "python", "-W", "ignore")


@dataclass(frozen=True)
class Cible:
    fichier: str                                  # chemin relatif à la racine
    noms: tuple[str, ...]                         # fonctions et constantes de niveau module mutées
    suites: tuple[tuple[str, str | None], ...]    # (dossier de suite, motif des fichiers de test ou None pour tous)


# Périmètre fermé (design D2), aligné sur #386. La garde de rôle de db.connect n'y est pas : ses mutants laisseraient un test qui
# attend un refus ouvrir une connexion vers l'adresse par défaut du Mac. Les tuples de chaînes (COLONNES_COMPTE, listes de rôles) n'offrent
# aucun point aux opérateurs : déclarés pour mémoire. Une cible ajoutée est un changement de cette constante, relu comme du code.
PERIMETRE = (
    Cible("tools/flow_views.py",
          ("PLANCHER", "COLONNES_COMPTE", "fichier_config", "seuil_configure", "seuil_effectif", "cellule", "masquer", "rendre", "lire",
           "main"),
          (("tests/flow_views", None),)),
    Cible("tools/db.py",
          ("ROLES_AVEC_MOT_DE_PASSE", "ROLES_SANS_MOT_DE_PASSE", "verifier_url", "service_du_role", "variable_du_role"),
          (("tests/db", None),)),
    Cible("tools/flux_jira.py",
          ("SEUIL_MASQUE", "cellule_masquee", "suppression_secondaire", "SEUIL_MASQUE_PARTAGES", "partages_par_equipe"),
          (("tests/flux_jira", "test_epics_agregation.py"), ("tests/flux_jira", "test_tickets_partages.py"))),
    Cible("tools/epic_statuses.py", ("SEUIL", "compte"), (("tests/epic_statuses", None),)),
)


class LancementImpossible(Exception):
    """Le passage ne peut pas avoir lieu ; le message est un type d'erreur, jamais une valeur."""


# --- mutateur -------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Mutant:
    fichier: str
    fonction: str        # nom déclaré qui contient le point (fonction ou constante)
    ligne: int
    operateur: str
    debut: int           # position (caractères) du segment remplacé
    fin: int
    remplacement: str


INVERSES = {ast.Lt: ast.GtE, ast.GtE: ast.Lt, ast.LtE: ast.Gt, ast.Gt: ast.LtE, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
            ast.Is: ast.IsNot, ast.IsNot: ast.Is, ast.In: ast.NotIn, ast.NotIn: ast.In}
JETONS = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==", ast.NotEq: "!=", ast.Is: "is", ast.IsNot: "is not",
          ast.In: "in", ast.NotIn: "not in"}
MOTIFS_JETON = {ast.Lt: r"<(?!=)", ast.LtE: r"<=", ast.Gt: r">(?!=)", ast.GtE: r">=", ast.Eq: r"==", ast.NotEq: r"!=",
                ast.Is: r"\bis\b(?!\s+not\b)", ast.IsNot: r"\bis\s+not\b", ast.In: r"(?<!not )\bin\b", ast.NotIn: r"\bnot\s+in\b"}


class Positions:
    """Conversion (ligne, colonne en octets UTF-8 de ast) vers une position en caractères dans le texte."""

    def __init__(self, source: str):
        self.lignes = source.splitlines(keepends=True)
        self.debuts = [0]
        for ligne in self.lignes:
            self.debuts.append(self.debuts[-1] + len(ligne))

    def __call__(self, ligne: int, colonne: int) -> int:
        texte = self.lignes[ligne - 1] if ligne - 1 < len(self.lignes) else ""
        return self.debuts[ligne - 1] + len(texte.encode("utf-8")[:colonne].decode("utf-8", errors="ignore"))

    def etendue(self, noeud: ast.AST) -> tuple[int, int]:
        return self(noeud.lineno, noeud.col_offset), self(noeud.end_lineno, noeud.end_col_offset)


def _descendants(noeud: ast.AST):
    """Nœuds sous `noeud` (lui compris), sans jamais entrer dans une chaîne formatée."""
    if isinstance(noeud, ast.JoinedStr):
        return
    yield noeud
    for enfant in ast.iter_child_nodes(noeud):
        yield from _descendants(enfant)


def _racines(arbre: ast.Module, noms: tuple[str, ...]):
    """(nom déclaré, nœuds à parcourir) pour chaque fonction ou constante de niveau module du périmètre."""
    for noeud in arbre.body:
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)) and noeud.name in noms:
            yield noeud.name, noeud.body
        elif isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                if isinstance(cible, ast.Name) and cible.id in noms:
                    yield cible.id, [noeud.value]
                    break
        elif isinstance(noeud, ast.AnnAssign) and isinstance(noeud.target, ast.Name) and noeud.target.id in noms and noeud.value:
            yield noeud.target.id, [noeud.value]


def _points_du_noeud(noeud: ast.AST, source: str, pos: Positions):
    """(opérateur, ligne, début, fin, remplacement) de chaque mutation possible du nœud."""
    if isinstance(noeud, ast.Compare):
        operandes = [noeud.left, *noeud.comparators]
        for i, op in enumerate(noeud.ops):
            if type(op) not in INVERSES:
                continue
            debut, fin = pos.etendue(operandes[i])[1], pos.etendue(operandes[i + 1])[0]
            trouve = re.search(MOTIFS_JETON[type(op)], source[debut:fin])
            if not trouve:
                continue
            operateur = "appartenance" if isinstance(op, (ast.In, ast.NotIn)) else "comparaison"
            yield operateur, noeud.lineno, debut + trouve.start(), debut + trouve.end(), JETONS[INVERSES[type(op)]]
    elif isinstance(noeud, ast.Constant) and isinstance(noeud.value, bool):
        debut, fin = pos.etendue(noeud)
        yield "negation", noeud.lineno, debut, fin, str(not noeud.value)
    elif isinstance(noeud, ast.Constant) and type(noeud.value) is int:
        debut, fin = pos.etendue(noeud)
        for valeur in (noeud.value + 1, noeud.value - 1):
            yield "constante", noeud.lineno, debut, fin, str(valeur) if valeur >= 0 else f"({valeur})"
    elif isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name) and noeud.func.id in ("max", "min"):
        debut, fin = pos.etendue(noeud.func)
        yield "max_min", noeud.lineno, debut, fin, "min" if noeud.func.id == "max" else "max"
    elif isinstance(noeud, (ast.If, ast.While, ast.IfExp)):
        debut, fin = pos.etendue(noeud.test)
        yield "negation", noeud.test.lineno, debut, fin, f"not ({source[debut:fin]})"
    elif isinstance(noeud, ast.UnaryOp) and isinstance(noeud.op, ast.Not):
        debut, fin = pos.etendue(noeud)
        o_debut, o_fin = pos.etendue(noeud.operand)
        yield "negation", noeud.lineno, debut, fin, f"({source[o_debut:o_fin]})"
    elif isinstance(noeud, ast.Return) and noeud.value is not None and not (
            isinstance(noeud.value, ast.Constant) and noeud.value.value is None):
        debut, fin = pos.etendue(noeud.value)
        yield "retour_none", noeud.lineno, debut, fin, "None"


def points(source: str, noms: tuple[str, ...], fichier: str) -> list[Mutant]:
    """Tous les mutants des noms déclarés, dans l'ordre du texte ; rien hors de ces noms."""
    arbre = ast.parse(source)
    pos = Positions(source)
    mutants = []
    for nom, noeuds in _racines(arbre, tuple(noms)):
        for racine in noeuds:
            for noeud in _descendants(racine):
                for operateur, ligne, debut, fin, remplacement in _points_du_noeud(noeud, source, pos):
                    mutants.append(Mutant(fichier, nom, ligne, operateur, debut, fin, remplacement))
    return mutants


def appliquer(source: str, mutant: Mutant) -> str:
    return source[:mutant.debut] + mutant.remplacement + source[mutant.fin:]


# --- copie, environnement, suites -------------------------------------------------------------------------------------------------

def copier(racine: Path, destination: Path) -> None:
    """Fichiers suivis de HEAD (git archive) extraits dans `destination` ; le dépôt n'est que lu."""
    try:
        fait = subprocess.run(["git", "-C", str(racine), "archive", "--format=tar", "HEAD"], capture_output=True,
                              stdin=subprocess.DEVNULL, timeout=300)
    except (OSError, subprocess.SubprocessError):
        raise LancementImpossible("copie impossible") from None
    if fait.returncode != 0 or not fait.stdout:
        raise LancementImpossible("copie impossible")
    try:
        with tarfile.open(fileobj=io.BytesIO(fait.stdout)) as archive:
            archive.extractall(destination, filter="data")
    except (OSError, tarfile.TarError):
        raise LancementImpossible("copie impossible") from None
    # La copie devient un dépôt Git jetable (dans le dossier temporaire seulement) : des suites lisent `git ls-files`, et le
    # résolveur des chemins du labo cherche la racine Git du code. Aucun crochet n'y tourne.
    options = ["-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", "-c", "user.name=mutation",
               "-c", "user.email=mutation@localhost"]
    env_git = sans_variables_git(os.environ)   # jamais le dépôt réel, même lancé depuis un crochet qui pose GIT_DIR (relecture 5.1)
    for commande in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "copie"]):
        try:
            fait = subprocess.run(["git", *options, *commande], cwd=destination, capture_output=True, stdin=subprocess.DEVNULL,
                                  timeout=300, env=env_git)
        except (OSError, subprocess.SubprocessError):
            raise LancementImpossible("copie impossible") from None
        if fait.returncode != 0:
            raise LancementImpossible("copie impossible")


VARIABLES_GIT = ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY")


def sans_variables_git(base) -> dict:
    """L'environnement sans les variables qui désignent un dépôt Git (un crochet en pose) : Git trouve alors la copie seule."""
    return {k: v for k, v in base.items() if k not in VARIABLES_GIT}


def environnement(copie: Path, base) -> dict:
    """Environnement des suites : aucune variable de base ni de dépôt Git héritée, des valeurs neutres, uv hors ligne, le dossier de
    contenu sur la copie, aucun fichier de bytecode."""
    env = {k: v for k, v in sans_variables_git(base).items()
           if not (k.startswith("PMZILLA_LAB_DB_") or k.startswith("PG") or k == "DBTEST_PORT")}
    env["UV_OFFLINE"] = "1"                                                  # le cache de uv est rempli une fois en ligne (6.1)
    env["PMZILLA_LAB_WORKSPACE"] = str(copie)                                # jamais l'espace de travail réel
    env["PMZILLA_LAB_DB_URL"] = "postgresql://postgres@127.0.0.1:1/pmzilla_mutation"     # rien n'écoute sur le port 1
    env["PMZILLA_LAB_DB_SECURITY_BIN"] = str(copie / ".mutation-sans-trousseau" / "security")   # chemin inexistant
    env["PGPORT"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def juger(copie: Path, cible: Cible, lanceur, env: dict, delai: float) -> str:
    """« tue » (une suite échoue), « delai » (délai dépassé : tué aussi) ou « survivant » (toutes passent). Sortie jamais lue."""
    for dossier, motif in cible.suites:
        commande = [*lanceur, "-m", "unittest", "discover", "-s", dossier, "-q"] + (["-p", motif] if motif else [])
        try:
            processus = subprocess.Popen(commande, cwd=copie, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            return "tue"
        try:
            code = processus.wait(timeout=delai)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(processus.pid, signal.SIGKILL)
            except OSError:
                pass
            processus.wait()
            return "delai"
        if code != 0:
            return "tue"
    return "survivant"


# --- seuil, état, échéance ---------------------------------------------------------------------------------------------------------

def lire_seuil(chemin: Path) -> tuple[int, int]:
    """(plancher, cible) : premières lignes non commentées, entiers de 50 à 100 ; la cible absente vaut le plancher."""
    try:
        lignes = [l.strip() for l in chemin.read_text(encoding="utf-8").splitlines()]
    except (OSError, UnicodeDecodeError):
        raise LancementImpossible("seuil illisible") from None
    valeurs = [l for l in lignes if l and not l.startswith("#")][:2]
    if not valeurs or not all(v.isdigit() and BORNES_SEUIL[0] <= int(v) <= BORNES_SEUIL[1] for v in valeurs):
        raise LancementImpossible("seuil illisible")
    plancher = int(valeurs[0])
    return plancher, int(valeurs[1]) if len(valeurs) > 1 else plancher


def dossier_donnees(env) -> Path:
    return Path(env.get("PMZILLA_LAB_DATA") or Path(env.get("HOME") or Path.home()) / ".pmzilla-lab").expanduser()


def lire_etat(chemin: Path) -> dict:
    if not chemin.exists():
        return {}
    try:
        etat = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        raise LancementImpossible("état illisible") from None
    if not isinstance(etat, dict):
        raise LancementImpossible("état illisible")
    return etat


def ecrire_etat(chemin: Path, etat: dict) -> None:
    """Écriture atomique (fichier temporaire du même dossier, puis renommage), lisible par le seul propriétaire."""
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descripteur, temporaire = tempfile.mkstemp(prefix=".mutation-", dir=chemin.parent)
    except OSError:
        raise LancementImpossible("état non inscriptible") from None
    try:
        os.fchmod(descripteur, 0o600)
        with os.fdopen(descripteur, "w", encoding="utf-8") as f:
            json.dump(etat, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(temporaire, chemin)
    except OSError:
        Path(temporaire).unlink(missing_ok=True)
        raise LancementImpossible("état non inscriptible") from None


def date_ou_none(texte) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(texte)) if texte else None
    except ValueError:
        return None


def aujourd_hui(env) -> dt.date:
    return date_ou_none(env.get("PMZILLA_LAB_TODAY")) or dt.date.today()


def jour_hebdomadaire(env) -> int:
    valeur = str(env.get("PMZILLA_MUTATION_DAY", "")).strip().lower()
    if valeur.isdigit() and int(valeur) < 7:
        return int(valeur)
    return JOURS.get(valeur, 0)


def due(etat: dict, jour: dt.date, hebdomadaire: int) -> bool:
    """Due si aucune tentative ce jour et : jour hebdomadaire, ou dernier passage complet absent ou de plus de 7 jours."""
    if date_ou_none(etat.get("last_attempt")) == jour:
        return False
    complet = date_ou_none(etat.get("last_complete"))
    return jour.weekday() == hebdomadaire or complet is None or (jour - complet).days > 7


# --- passage ------------------------------------------------------------------------------------------------------------------------

def score(tues: int, total: int) -> int:
    return tues * 100 // total if total else 0


def lignes_resultat(etat: dict) -> list[str]:
    """Lignes du résultat d'un passage, depuis l'état (aucun code, aucune valeur)."""
    lignes = [f"{PREFIXE}cible {c['fichier']} : {c['tues']} tués sur {c['total']}, score {c['score']} %" for c in etat["cibles"]]
    lignes.append(f"{PREFIXE}{etat['tues']} mutants tués sur {etat['total']} (dont {etat['delais']} en délai), score {etat['score']} %, "
                  f"seuil {etat['seuil']} %, cible {etat['cible']} %")
    lignes += [f"{PREFIXE}survivant {s['fichier']}:{s['fonction']} ligne {s['ligne']} ({s['operateur']})" for s in etat["survivants"]]
    lignes += [f"{PREFIXE}délai {s['fichier']}:{s['fonction']} ligne {s['ligne']} ({s['operateur']})" for s in etat["en_delai"]]
    return lignes


def passage(racine: Path, perimetre, lanceur, delai_option: float | None) -> dict:
    """Copie, suites de référence, puis chaque mutant ; le dossier temporaire est retiré dans tous les cas."""
    copie = Path(tempfile.mkdtemp(prefix="pmzilla-mutation-"))
    try:
        copier(racine, copie)
        env = environnement(copie, os.environ)
        sources, delais = {}, {}
        for cible in perimetre:
            try:
                sources[cible.fichier] = (copie / cible.fichier).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                raise LancementImpossible("cible illisible") from None
            depart = time.monotonic()
            if juger(copie, cible, lanceur, env, DELAI_REFERENCE) != "survivant":
                raise LancementImpossible("suite de référence en échec")
            duree = time.monotonic() - depart
            delais[cible.fichier] = delai_option or max(DELAI_MINIMUM, math.ceil(FACTEUR_DELAI * duree))
        resultat = {"cibles": [], "survivants": [], "en_delai": []}
        for cible in perimetre:
            source = sources[cible.fichier]
            try:
                mutants = points(source, cible.noms, cible.fichier)
            except SyntaxError:
                raise LancementImpossible("cible illisible") from None
            chemin = copie / cible.fichier
            tues = 0
            for mutant in mutants:
                try:
                    chemin.write_text(appliquer(source, mutant), encoding="utf-8")
                except OSError:
                    raise LancementImpossible("copie impossible") from None
                try:
                    verdict = juger(copie, cible, lanceur, env, delais[cible.fichier])
                finally:
                    chemin.write_text(source, encoding="utf-8")
                fiche = {"fichier": mutant.fichier, "fonction": mutant.fonction, "ligne": mutant.ligne, "operateur": mutant.operateur}
                if verdict == "survivant":
                    resultat["survivants"].append(fiche)
                else:
                    tues += 1
                    if verdict == "delai":
                        resultat["en_delai"].append(fiche)
            ligne = {"fichier": cible.fichier, "tues": tues, "total": len(mutants), "score": score(tues, len(mutants))}
            resultat["cibles"].append(ligne)
            print(f"{PREFIXE}cible {ligne['fichier']} : {ligne['tues']} tués sur {ligne['total']}, score {ligne['score']} %", flush=True)
        return resultat
    finally:
        shutil.rmtree(copie, ignore_errors=True)


def commande_run(args, racine: Path, perimetre, lanceur) -> int:
    chemin_etat = dossier_donnees(os.environ) / FICHIER_ETAT
    jour = aujourd_hui(os.environ)
    etat = lire_etat(chemin_etat)
    if args.due and not due(etat, jour, jour_hebdomadaire(os.environ)):
        print(f"{PREFIXE}pas due")
        return 0
    etat["last_attempt"] = jour.isoformat()
    ecrire_etat(chemin_etat, etat)
    seuil, cible = lire_seuil(racine / SEUIL_RELATIF)
    resultat = passage(racine, perimetre, lanceur, args.timeout)
    total = sum(c["total"] for c in resultat["cibles"])
    if total == 0:
        raise LancementImpossible("aucun mutant")
    tues = sum(c["tues"] for c in resultat["cibles"])
    resultat.update({"tues": tues, "total": total, "delais": len(resultat["en_delai"]), "score": score(tues, total),
                     "seuil": seuil, "cible": cible})
    for ligne in lignes_resultat(resultat)[len(resultat["cibles"]):]:      # les lignes par cible sont déjà affichées
        print(ligne)
    etat.update(resultat)
    etat["last_complete"] = jour.isoformat()
    ecrire_etat(chemin_etat, etat)
    if resultat["score"] < seuil:
        print(f"{PREFIXE}score {resultat['score']} % sous le seuil {seuil} %")
        return 3
    return 0


def commande_report() -> int:
    etat = lire_etat(dossier_donnees(os.environ) / FICHIER_ETAT)
    if not etat.get("last_complete") or not all(k in etat for k in ("cibles", "tues", "total", "survivants", "en_delai")):
        print(f"{PREFIXE}aucun passage enregistré")
        return 0
    try:
        lignes = list(lignes_resultat(etat))
    except (KeyError, TypeError, ValueError):     # état partiel (relecture 5.1) : code 2, jamais une trace
        raise LancementImpossible("état illisible") from None
    print(f"{PREFIXE}dernier passage complet : {etat['last_complete']}")
    for ligne in lignes:
        print(ligne)
    return 0


def main(argv: list[str] | None = None, *, racine: Path = RACINE, perimetre=PERIMETRE, lanceur=LANCEUR) -> int:
    parser = argparse.ArgumentParser(description="Tests de mutation du code de masquage et de rôles (jamais dans run_all.sh).")
    sous = parser.add_subparsers(dest="commande", required=True)
    lancer = sous.add_parser("run", help="un passage sur le périmètre déclaré")
    lancer.add_argument("--due", action="store_true", help="seulement si le passage hebdomadaire est dû")
    lancer.add_argument("--timeout", type=int, metavar="SECONDES", help="délai maximal par mutant (défaut : 5 fois la suite de référence, au moins 10 s)")
    sous.add_parser("report", help="relit le dernier passage enregistré")
    args = parser.parse_args(argv)
    if args.commande == "run" and args.timeout is not None and args.timeout <= 0:
        parser.error("--timeout attend un nombre de secondes positif")
    try:
        if args.commande == "report":
            return commande_report()
        return commande_run(args, racine, perimetre, lanceur)
    except LancementImpossible as erreur:
        print(f"{PREFIXE}lancement impossible ({erreur})")
        return 2


if __name__ == "__main__":
    sys.exit(main())
