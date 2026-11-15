#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
PMZilla Lab : la liste locale des branches prêtes pour le train automatique (change autonomous-trains-observe, R-166, design D3, D4 et D11).

    python3 -I tools/train_ready.py list
    python3 -I tools/train_ready.py list --json
    python3 -I tools/train_ready.py prune
    python3 -I tools/train_ready.py add <branche> --revue faite|non-requise
    python3 -I tools/train_ready.py drop <branche>
    (--language fr|en avant la commande)

La session écrit la liste par cet outil seulement ; le passage de tools/train_auto.py la lit et ne l'écrit jamais. Le fichier est
`train-auto/pretes.tsv` du dossier de données du lab (hors Git, propriétaire seul). Première ligne `# pmzilla-train-pretes format 1`, puis
une ligne par branche, champs séparés par une tabulation : nom, sommet (40 hex), arbre de l'empreinte du runner complet (40 hex), revue
(`faite` ou `non-requise`), heure d'ajout (UTC, ISO 8601). L'ordre des lignes est l'ordre des ajouts, donc l'ordre de fusion.

add : l'outil calcule lui-même le sommet et la preuve (jamais une option de la ligne de commande). La preuve (change targeted-suites-admission, D4),
    UNE fonction `proof_of` appelée par `add`, `list` et le passage, qui délègue à tools/preuve_arbre.py (ci-local-runner, D8) : l'empreinte du runner complet
    (« complete »), sinon le conteneur et la passe Mac (« conteneur » : ci/preuves avec les trois phases ET pmzilla-run-mac-ok), sinon l'empreinte de branche de
    `bash tests/run_all.sh --branch` (« ciblee »), jamais l'empreinte ciblée par commit. `add` imprime après `inscrite` la ligne `train_ready : preuve :
    runner complet`, `train_ready : preuve : conteneur et passe Mac` ou `train_ready : preuve : suites de la branche (<n>)` ; `list --json` ajoute `preuve` et
    `suites` à chaque ligne. Elle ne remplace pas la porte du train sur l'arbre intégré. Il remplace en place la ligne d'une
    branche déjà inscrite. Il refuse (code 3, une ligne `train_ready : refusée : <branche> : <raison>` par raison, rien d'écrit) quand : la
    branche n'a pas de worktree ou son worktree n'est pas propre ; aucune preuve du sommet (complète ou de branche) n'existe, ou elle est d'un autre arbre ; la
    branche est déjà dans origin/main ou n'est pas contrôlable ; `non-requise` est donné et une exclusion de chemin de train_auto.exclusions
    s'applique (outillage protégé, postures, base, front : avec `faite` elles ne bloquent plus l'inscription, R-20261031-21, et le passage
    écarte la ligne à chaque fois ; elle occupe une place du plafond jusqu'à la fin de sa branche) ;
    `non-requise` est donné pour une branche qui change un chemin hors de openspec/ et docs/ ; la liste tient déjà le plafond et la branche
    n'y est pas. `add` lance d'abord `prune`.
drop : retire la ligne ; code 0 aussi quand la branche n'est pas dans la liste.
prune : retire les lignes dont le sommet est dans origin/main ou dont la branche n'existe plus.
list : écrit chaque ligne et sa validité, calculée par la même fonction que le passage (train_auto.check_line, sans réseau ni contrôle de
    processus) ; ne modifie rien. `--json` : format 1.

Écrit seulement : la liste et son verrou (train-auto/pretes.lock), sous verrou exclusif, par fichier temporaire remplacé atomiquement. Aucune
référence Git, aucun réseau, aucun gh, aucune base. Une ligne mal formée rend toute la liste illisible : `list` nomme le numéro de ligne,
jamais son contenu.

Codes de sortie : 0 fait ; 2 usage ; 3 branche refusée, chaque raison listée ; 4 liste illisible ou non inscriptible ;
  5 calcul impossible (Git en échec, finish_checks.py code 4, dossiers du lab introuvables) ; 6 `add`, `drop` ou `prune` refusé pendant un train (verrou
  de fin tenu dont l'appelant ne porte pas le jeton, par finish_lock.freezes(writes_ready_list=True), quel que soit son worktree, rien d'écrit).
  Toute commande qui écrit la liste prête (`add`, `drop`, `prune`) est gelée pendant un train, `list` reste permis. Code 6 : Remplace : rien. Retrait : permanent, avec le gel ciblé.

Phrases clés : `train_ready : inscrite : <branche> (sommet <sha12>, revue <faite|non requise>)` ; `train_ready : refusée : <branche> : <raison>` ;
`train_ready : retirée : <branche>` ; `train_ready : absente de la liste : <branche>` ; `train_ready : <n> ligne(s) retirée(s) (fusionnées ou
disparues)` ; `train_ready : liste illisible : ligne <n>`.

Libellés des quatre motifs de chemin (autonomous-trains-merge, tranche 3, D16, R-20261101-61) : `outillage-protege` et `postures` disent « train de l'auteur », `base` et `front` disent
« revue Opus requise » (source unique : tools/train_auto_messages.py).

Remplace : le marquage GitHub de T2 (R-20261028-61). Retrait : tombe avec les trains autonomes (R-166 et suivantes) si l'auteur reprend les trains à la main.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_paths  # noqa: E402
from messages import Messages, add_language_option  # noqa: E402
from train_auto_messages import label as reason_label  # noqa: E402
from train_ready_messages import CATALOGS  # noqa: E402

FORMAT_LINE = "# pmzilla-train-pretes format 1"
BRANCH_FINGERPRINT = "pmzilla-run-branch-ok"   # écrit par `bash tests/run_all.sh --branch` (targeted-suites-admission, D2) ; source du nom : tests/run_all.sh
FOLDER = "train-auto"
LIST_NAME = "pretes.tsv"
LOCK_NAME = "pretes.lock"
REVIEWS = ("faite", "non-requise")
# Source : train_auto.exclusions. Un motif ajouté là sans l'être ici refuse l'inscription (côté prudent).
JOB_EXCLUSIONS = ("outillage-protege", "postures", "base", "front")   # motifs d'exclusion du job : refus de `add` seulement avec --revue non-requise (R-20261031-21)
CAP = 5   # P12 : au plus cinq branches de code en attente ; tenu par `add`, relu par le passage de train_auto.py
REVIEW_FREE_PREFIXES = ("openspec/", "docs/")   # chemins de spécification et de documentation (P10) : seuls permis avec « non-requise »
GIT_TIMEOUT = 30
HEX40 = re.compile(r"[0-9a-f]{40}")
TIME_FIELD = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_GIT_REMOVED = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_LITERAL_PATHSPECS", "GIT_GLOB_PATHSPECS",
                "GIT_NOGLOB_PATHSPECS", "GIT_ICASE_PATHSPECS")


class Stop(Exception):
    def __init__(self, code, message=""):
        super().__init__(message)
        self.code = code
        self.message = message


class ListeIllisible(Exception):
    """La liste est illisible : `line` est le numéro de la ligne fautive (jamais son contenu), None quand c'est le fichier."""

    def __init__(self, line=None):
        super().__init__(str(line))
        self.line = line


# --- Git, chemins, dossiers ---------------------------------------------------------------------------------------------------------

def git(repo, *args, timeout=GIT_TIMEOUT, extra_env=None):
    """(code, sortie). Lecture seule : verrous optionnels coupés, entrée fermée ; 127 quand Git ne peut pas tourner ou dépasse le délai."""
    env = {k: v for k, v in os.environ.items() if k not in _GIT_REMOVED}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env.update(extra_env or {})
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, errors="replace", env=env, timeout=timeout,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return r.returncode, r.stdout


def workspace():
    """Le dossier de contenu (l'espace de travail sur main). Lève lab_paths.LabPathsError quand il est introuvable."""
    return lab_paths.content_root()


def data_dir():
    return lab_paths.data_folder() / FOLDER


def ensure_data_dir():
    dossier = data_dir()
    dossier.mkdir(parents=True, exist_ok=True)
    os.chmod(dossier, 0o700)
    return dossier


def ready_path():
    return data_dir() / LIST_NAME


def rev(ws, name):
    code, out = git(ws, "rev-parse", "-q", "--verify", name)
    sortie = out.strip()
    return sortie if code == 0 and HEX40.fullmatch(sortie) else None


def tip_of(ws, branch):
    return rev(ws, f"refs/heads/{branch}^{{commit}}")


def tree_of(ws, tip):
    return rev(ws, f"{tip}^{{tree}}")


def in_origin_main(ws, tip):
    """True, False, ou None quand Git ne peut pas répondre."""
    code, _ = git(ws, "merge-base", "--is-ancestor", tip, "refs/remotes/origin/main")
    return True if code == 0 else (False if code == 1 else None)


def worktree_of(ws, branch):
    code, out = git(ws, "worktree", "list", "--porcelain")
    chemin = None
    for ligne in out.splitlines():
        if ligne.startswith("worktree "):
            chemin = ligne[9:]
        elif ligne == f"branch refs/heads/{branch}":
            return chemin
    return None


def worktree_clean(path):
    code, out = git(path, "status", "--porcelain")
    return code == 0 and not out.strip()


def _preuve():
    """tools/preuve_arbre.py (ci-local-runner, D8), importé à la demande : tools/finish_admission.sh copie ce module sans lui (il n'appelle que read_list)."""
    import preuve_arbre
    return preuve_arbre


def fingerprint_of(path):
    """L'arbre noté par le dernier runner complet réussi dans ce worktree (fichier lu par le crochet pre-push), ou None. Définition : tools/preuve_arbre.py."""
    return _preuve().fingerprint_of(path)


def branch_fingerprint_of(path):
    """(arbre, suites) de l'empreinte de branche écrite par `bash tests/run_all.sh --branch` dans ce worktree, ou None. Définition : tools/preuve_arbre.py
    (jamais l'empreinte ciblée par commit)."""
    return _preuve().branch_fingerprint_of(path)


def proof_of(path, tree):
    """La preuve que le sommet de ce worktree a été éprouvé (ci-local-runner, D8) : « complete », « conteneur », « ciblee » ou None, par
    tools/preuve_arbre.py (UNE fonction, la même que celle du crochet pre-push). Appelée par `add`, `list` et le passage (train_auto.check_line). Un calcul
    impossible n'est pas une preuve. Elle ne tient jamais lieu de la garde de main : le train juge l'arbre intégré par sa porte.
    Remplace : le calcul propre à ce module (complète puis branche). Retrait : `ciblee` tombe avec D10."""
    if tree is None:
        return None
    mod = _preuve()
    try:
        return mod.preuve(tree, worktree=path)
    except mod.PreuveImpossible:
        return None


def proof_reason(path, tree):
    """None quand `proof_of` a une preuve ; sinon « sans-empreinte » (aucun fichier d'empreinte, complet ou de branche) ou « empreinte » (une preuve
    d'un autre arbre, ou une preuve du conteneur incomplète pour cet arbre : l'arbre est dans ci/preuves ou dans pmzilla-run-mac-ok sans que les deux tiennent)."""
    if proof_of(path, tree) is not None:
        return None
    mod = _preuve()
    try:
        partielle = tree is not None and (mod.container_phases(tree) is not None or mod.mac_proven(tree, path))
    except mod.PreuveImpossible:
        partielle = False
    return "empreinte" if partielle or fingerprint_of(path) is not None or branch_fingerprint_of(path) is not None else "sans-empreinte"


def changed_paths(ws, branch):
    """Les chemins que la branche change depuis origin/main (différence à trois points), ou None quand Git échoue."""
    code, out = git(ws, "diff", "--name-only", "--no-renames", "-z", f"refs/remotes/origin/main...refs/heads/{branch}")
    return [p for p in out.split("\0") if p] if code == 0 else None


def review_free(paths):
    return bool(paths) and all(p.startswith(REVIEW_FREE_PREFIXES) for p in paths)


# --- le fichier de la liste ---------------------------------------------------------------------------------------------------------

def parse_list(texte):
    lignes = texte.split("\n")
    if lignes and lignes[-1] == "":
        lignes.pop()
    if not lignes or lignes[0] != FORMAT_LINE:
        raise ListeIllisible(1)
    entrees, vus = [], set()
    for n, ligne in enumerate(lignes[1:], start=2):
        champs = ligne.split("\t")
        if (len(champs) != 5 or not champs[0] or champs[0] in vus or not HEX40.fullmatch(champs[1]) or not HEX40.fullmatch(champs[2])
                or champs[3] not in REVIEWS or not TIME_FIELD.fullmatch(champs[4])):
            raise ListeIllisible(n)
        vus.add(champs[0])
        entrees.append({"branche": champs[0], "sommet": champs[1], "empreinte": champs[2], "revue": champs[3], "ajout": champs[4]})
    return entrees


def read_list(path=None):
    """Les lignes de la liste ; une liste absente est vide ; ListeIllisible quand le fichier ou une ligne ne se lit pas."""
    chemin = Path(path) if path is not None else ready_path()
    try:
        texte = chemin.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except (OSError, UnicodeDecodeError):
        raise ListeIllisible(None) from None
    return parse_list(texte)


def format_list(entrees):
    lignes = [FORMAT_LINE] + ["\t".join((e["branche"], e["sommet"], e["empreinte"], e["revue"], e["ajout"])) for e in entrees]
    return "\n".join(lignes) + "\n"


def write_list(entrees, path=None):
    """Écriture atomique : fichier temporaire du même dossier (propriétaire seul), puis remplacement."""
    chemin = Path(path) if path is not None else ready_path()
    temporaire = chemin.parent / f".{chemin.name}.tmp-{os.getpid()}"
    fd = os.open(temporaire, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(format_list(entrees))
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporaire, chemin)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporaire)
        raise


@contextlib.contextmanager
def exclusive(path, blocking=True):
    """Verrou exclusif sur un fichier de verrou à côté de la ressource (créé, propriétaire seul). Non bloquant : BlockingIOError si tenu."""
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        yield
    finally:
        os.close(fd)


def _auto():
    """tools/train_auto.py, importé à la demande : il importe ce module (exclusions et validité des lignes y sont définies une seule fois)."""
    import train_auto
    return train_auto


# --- services ------------------------------------------------------------------------------------------------------------------------

def prune_entries(ws, entrees):
    """(lignes gardées, nombre retiré) : retirées, celles dont le sommet est dans origin/main ou dont la branche n'existe plus."""
    gardees = []
    for e in entrees:
        tip = tip_of(ws, e["branche"])
        if tip is None:
            continue
        if in_origin_main(ws, tip) is True:
            continue
        gardees.append(e)
    return gardees, len(entrees) - len(gardees)


def list_validity(ws=None, run=None):
    """Service : chaque ligne avec sa validité, par la fonction du passage (train_auto.check_line), hors réseau et hors contrôle de processus.
    ListeIllisible quand la liste ne se lit pas."""
    ws = ws or workspace()
    run = run or lab_paths.run_tree(ws)
    auto = _auto()
    resultat = []
    for e in read_list():
        raisons = auto.check_line(ws, run, e)
        wt = worktree_of(ws, e["branche"])
        preuve = proof_of(wt, e["empreinte"]) if wt and Path(wt).is_dir() else None
        suites = (branch_fingerprint_of(wt) or ("", []))[1] if preuve == "ciblee" else []
        resultat.append(dict(e, valide=not raisons, raison=raisons[0] if raisons else None, preuve=preuve, suites=suites))
    return resultat


def evaluate_add(ws, run, branch, review, entrees):
    """(raisons de refus, calcul impossible : texte ou None, sommet évalué, (preuve, suites)). Toutes les raisons sont calculées, jamais seulement la
    première. Le sommet rendu est celui qui a été évalué : l'appelant écrit celui-là, il ne relit pas la branche. La preuve rendue (« complete », « ciblee »
    ou None, et les suites de l'empreinte de branche) est celle qui a été évaluée : `add` imprime celle-là, sans la recalculer (revue 2026-10-31, point 5)."""
    raisons = []
    preuve, suites_preuve = None, []
    tip = tip_of(ws, branch)
    if tip is None:
        return ["branche-absente"], None, None, (preuve, suites_preuve)
    deja = in_origin_main(ws, tip)
    if deja is None:
        return [], "git", tip, (preuve, suites_preuve)
    if deja:
        raisons.append("deja-fusionnee")
    arbre = tree_of(ws, tip)
    wt = worktree_of(ws, branch)
    if wt is None or not Path(wt).is_dir():
        raisons.append("sans-worktree")
    else:
        if not worktree_clean(wt):
            raisons.append("worktree-sale")
        preuve = proof_of(wt, arbre)
        if preuve == "ciblee":
            suites_preuve = (branch_fingerprint_of(wt) or ("", []))[1]
        elif preuve is None:
            raisons.append(proof_reason(wt, arbre) or "empreinte")
    exclusions, code = _auto().exclusions(ws, run, branch)
    if code == 4:
        return [], "finish_checks", tip, (preuve, suites_preuve)
    if review == "faite":
        # R-20261031-21 : avec la revue faite, les motifs d'exclusion du job n'empêchent pas l'inscription (check_line les écarte à chaque passage)
        exclusions = [r for r in exclusions if r not in JOB_EXCLUSIONS]
    raisons += exclusions
    if review == "non-requise":
        chemins = changed_paths(ws, branch)
        if chemins is None:
            return [], "git", tip, (preuve, suites_preuve)
        if not review_free(chemins):
            raisons.append("revue")
    if len(entrees) >= CAP and not any(e["branche"] == branch for e in entrees):
        raisons.append("liste-pleine")
    vus = []
    for r in raisons:
        if r not in vus:
            vus.append(r)
    return vus, None, tip, (preuve, suites_preuve)


def now_iso():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- commandes -----------------------------------------------------------------------------------------------------------------------

def _context(t):
    try:
        ws = workspace()
        return ws, lab_paths.run_tree(ws)
    except lab_paths.LabPathsError:
        raise Stop(5, t("folders")) from None


def _open_for_write(t):
    try:
        ensure_data_dir()
    except OSError:
        raise Stop(4, t("not_writable")) from None


def _read_or_stop(t):
    try:
        return read_list()
    except ListeIllisible as e:
        raise Stop(4, t("unreadable", n=e.line) if e.line else t("unreadable_file")) from None


def _refuse_during_train(ws, t):
    """Stop(6) pendant un train qui gèle l'appelant : UNE règle, finish_lock.freezes() (D18), appelée avec writes_ready_list=True (la liste prête est écrite par
    `add`, `drop` et `prune` : gelés quel que soit le worktree de l'appelant). Un dossier Git commun ou un sommet illisible hors verrou ne refuse rien. Remplace : rien (la liste prête s'écrivait pendant un train).
    Retrait : permanent, avec le gel ciblé."""
    import finish_lock
    code, commun = git(ws, "rev-parse", "--path-format=absolute", "--git-common-dir")
    code2, sommet = git(Path.cwd(), "rev-parse", "--show-toplevel")
    if code != 0 or not commun.strip():
        return
    appelant = sommet.strip() if code2 == 0 and sommet.strip() else str(Path.cwd())
    scope = finish_lock.freezes(commun.strip(), appelant, os.environ.get("FINISH_LOCK_TOKEN", ""), protected=True,
                                writes_ready_list=True)
    if scope is not None:
        raise Stop(6, t("frozen", branch=scope["branch"]))


def cmd_add(args, t):
    ws, run = _context(t)
    _refuse_during_train(ws, t)
    _open_for_write(t)
    try:
        with exclusive(data_dir() / LOCK_NAME):
            entrees = _read_or_stop(t)
            entrees, retirees = prune_entries(ws, entrees)
            raisons, impossible, tip, (preuve, suites_preuve) = evaluate_add(ws, run, args.branch, args.revue, entrees)
            if impossible:
                raise Stop(5, t("impossible", why=impossible))
            if raisons:
                lignes = [t("refused", branch=args.branch, label=_label(r, args.language, t)) for r in raisons]
                for ligne in lignes:
                    print(ligne, file=sys.stderr)
                if retirees:
                    write_list(entrees)   # le ménage de `prune` ne dépend pas du refus
                return 3
            ligne = {"branche": args.branch, "sommet": tip, "empreinte": tree_of(ws, tip), "revue": args.revue, "ajout": now_iso()}
            for i, e in enumerate(entrees):
                if e["branche"] == args.branch:
                    entrees[i] = ligne
                    break
            else:
                entrees.append(ligne)
            write_list(entrees)
    except OSError:
        raise Stop(4, t("not_writable")) from None
    if retirees:
        print(t("pruned", n=retirees))
    revue = t("review_given") if args.revue == "faite" else t("review_not_required")
    print(t("added", branch=args.branch, tip=tip[:12], review=revue))
    print(t("proof_branch", n=len(suites_preuve)) if preuve == "ciblee" else t("proof_container") if preuve == "conteneur" else t("proof_complete"))
    return 0


def _label(code, language, t):
    if code == "liste-pleine":
        return f"{reason_label(code, language)} ({t('cap', n=CAP)})"
    return reason_label(code, language)


def cmd_drop(args, t):
    ws, _ = _context(t)
    _refuse_during_train(ws, t)
    _open_for_write(t)
    try:
        with exclusive(data_dir() / LOCK_NAME):
            entrees = _read_or_stop(t)
            gardees = [e for e in entrees if e["branche"] != args.branch]
            if len(gardees) == len(entrees):
                print(t("absent", branch=args.branch))
                return 0
            write_list(gardees)
    except OSError:
        raise Stop(4, t("not_writable")) from None
    print(t("dropped", branch=args.branch))
    return 0


def cmd_prune(args, t):
    ws, _ = _context(t)
    _refuse_during_train(ws, t)
    _open_for_write(t)
    try:
        with exclusive(data_dir() / LOCK_NAME):
            entrees = _read_or_stop(t)
            gardees, n = prune_entries(ws, entrees)
            if n:
                write_list(gardees)
    except OSError:
        raise Stop(4, t("not_writable")) from None
    print(t("pruned", n=n))
    return 0


def cmd_list(args, t):
    _context(t)
    try:
        lignes = list_validity()
    except ListeIllisible as e:
        raise Stop(4, t("unreadable", n=e.line) if e.line else t("unreadable_file")) from None
    if args.json:
        print(json.dumps({"format": 1, "lignes": lignes}, ensure_ascii=False))
        return 0
    if not lignes:
        print(t("list_empty"))
    for e in lignes:
        if e["valide"]:
            print(t("list_valid", branch=e["branche"]))
        else:
            print(t("list_excluded", branch=e["branche"], label=reason_label(e["raison"], args.language)))
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="train_ready.py", description="Liste locale des branches prêtes pour le train automatique.")
    add_language_option(p)
    sub = p.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="écrit les lignes et leur validité")   # d'abord : le manuel construit son exemple depuis la première sous-commande
    ls.add_argument("--json", action="store_true")
    a = sub.add_parser("add", help="inscrit une branche (le sommet et l'empreinte sont calculés par l'outil)")
    a.add_argument("branch")
    a.add_argument("--revue", required=True, choices=("faite", "non-requise"))
    d = sub.add_parser("drop", help="retire une branche de la liste")
    d.add_argument("branch")
    sub.add_parser("prune", help="retire les lignes fusionnées ou disparues")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)   # une erreur d'usage sort avec le code 2
    t = Messages(CATALOGS, args.language)
    try:
        return {"add": cmd_add, "drop": cmd_drop, "prune": cmd_prune, "list": cmd_list}[args.cmd](args, t)
    except Stop as e:
        if e.message:
            print(e.message, file=sys.stderr)
        return e.code
    except Exception as e:   # jamais de trace de pile : le type seulement
        print(t("unexpected", kind=type(e).__name__), file=sys.stderr)
        return 5


if __name__ == "__main__":
    sys.exit(main())
