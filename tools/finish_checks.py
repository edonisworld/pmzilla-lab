#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
PMZilla Lab : contrôles 19, 5, 6, 14, 16 et 20 de fin de branche en lecture seule, pour une branche ou un arbre. Seule implémentation de ces
contrôles : tools/finish_train.sh en lit les contrôles 19 à 16 (la fin unitaire tools/finish_branch.sh, qui en lisait la sortie JSON, est retirée par B9)
(change finish-train-foundations, design D9 à D17 ; contrôle 16 : change finish-e2e-proof-shared ; contrôle 20, règle de Node unique, base unique et
chemins de la base en fichier de données : change finish-single-b3-b6, groupe 4, D13 à D17).

    python3 tools/finish_checks.py branch <branche> [--repo DIR] [--json]
    python3 tools/finish_checks.py tree <arbre> [--repo DIR] [--json]
    python3 tools/finish_checks.py protected [--repo DIR] [--json]
    python3 tools/finish_checks.py policy --train-tip <sha> --branch <b> --tip <sha> [--branch <b> --tip <sha> …] [--repo DIR] [--json]
    python3 tools/finish_checks.py policy-lines                                  (la sortie JSON de « policy » sur l'entrée standard)
    python3 tools/finish_checks.py node-match <trouvé> <attendu>
    python3 tools/finish_checks.py extract verdicts|phrase|details|error [<id>]      (la sortie JSON de « branch » sur l'entrée standard)

À lancer sous « python3 -I ». « branch » calcule les contrôles 19, 5, 6, 14, 16 et 20 pour la branche locale nommée, sur
merge-base(origin/main, sommet)..sommet, avec les phrases de refus de la fin unitaire, sans s'arrêter au premier refus, puis dit
quels fichiers de l'outillage protégé la branche touche. Quand main local existe et diffère d'origin/main, une seconde base
merge-base(main, sommet) (« base_local » dans le JSON) s'ajoute : l'union des chemins des deux différences s'applique aux contrôles 19, 5, 6
et 14, et les listes sont lues à origin/main, à main et au sommet : une seule règle de base pour toutes les fins. « tree » calcule les contrôles 14, 16 puis 6 pour un arbre (chemins changés
depuis origin/main, ligne de pmzilla-dbtest-ok puis de pmzilla-e2e-ok pour cet arbre ; le 6 par empreinte des fichiers évalués calculée sur l'arbre : finish-single-b3-b6, B6, D19). Le contrôle 14 lit la liste tools/finish_db_paths.txt (chemins du code de
la base) et le contrôle 16 la liste tools/finish_e2e_paths.txt (chemins d'interface), chacune en union comme les autres listes ; absente
partout : refusé, jamais sans objet. Le contrôle 20 lit la ligne SUITES_NPM=(…) de tests/run_all.sh du sommet : sans suite npm, ou branche ouverte
dans aucun dossier, il est sans objet ; sinon le Node trouvé (« node --version », enfant en lecture seule, entrée fermée) doit correspondre à
<dossier>/.node-version selon node_matches (le verrou npm reste au runner, code 7). « node-match » rend 0 (correspond), 1 (diffère), 2 (usage) :
c'est la règle de Node du code 80 du train. « extract » lit sur l'entrée standard la sortie JSON de « branch » et en rend un champ au script de
fin (verdicts : « id verdict » par ligne, dans l'ordre ; sortie 4 si le format n'est pas 1 ou si un contrôle manque). « protected » imprime les motifs de l'outillage protégé (union de ceux
d'origin/main et du sommet courant) et les fichiers protégés que la branche courante touche. Toucher l'outillage protégé ne change pas le
code de sortie : la fin de branche unitaire l'autorise ; c'est l'admission au train qui s'en sert.
Classes (change finish-single-b3-b6, B4, D9) : chaque motif de tools/finish_protected.txt porte une étiquette de commentaire `#[juge]` ou `#[sensible]` ; « branch »
sépare les fichiers touchés en `protected_judges` et `protected_sensitive` (JSON ; `protected_touched` reste, leur union) et le texte donne les lignes « outillage de fin
touché » et « outil sensible touché ». Sans étiquette, ou avec deux classes selon la révision, un motif compte `juge`. Remplace : la ligne unique « outillage protégé touché ».

Politique automatique et train de l'auteur (change autonomous-trains-merge, tranche 1, design D2, D3 et D7). `train_de_l_auteur(rec)` est la fonction UNIQUE qui dit qu'une
branche est un train de l'auteur : sa différence touche un fichier `juge` de tools/finish_protected.txt (le runner et la preuve en sont), un chemin de .claude/ ou un fichier
CLAUDE.md à toute profondeur, ou un fichier des postures (contrôle 6 applicable). `auto_policy` est la politique de la fusion automatique, en un endroit, derrière
« policy » : elle lit la liste prête et la règle de revue par tools/train_ready.py, les fichiers d'arrêt et d'activation par tools/train_auto.py, jamais une variable
comme exemption (la garde de FINISH_TRAIN_CI et FINISH_TRAIN_RUNNER est celle du train, code 61 sous --auto : R-20261106-57 ; elle remplace la phrase « aucune variable n'est une
exemption » ; retrait, R-20261107-4 : elle tombe quand finish_train.sh ne lit plus aucune variable FINISH_TRAIN_* sous --auto ; PMZILLA_LAB_DATA est une limite déclarée de D6), n'écrit rien, et rend `{"format": 1, "allowed": bool, "reasons": [{"code", "branch"?}]}` (toutes les raisons, dans l'ordre de D7 : inactif,
activation-invalide, arret, liste-illisible, absente-de-la-liste, sommet-non-atteste, revue-absente, train-de-l-auteur, plafond, calcul-impossible). Code de sortie de
« policy » : 0 autorisé, 1 refusé, 2 usage, 4 calcul impossible (une raison `calcul-impossible`). « policy-lines » donne le libellé de chaque raison (une ligne chacune ;
4 si la sortie est illisible) : le train ne garde aucune copie des libellés. La liste tools/finish_runner_paths.txt (D3), lue en union comme les autres listes par
`runner_proof_paths`, donne les chemins du runner et de la preuve (`runner_proof_touched` en rend ceux qu'une branche change). Remplace : rien (la politique ne remplace la
question que du train lancé avec --auto ; le motif littéral de l'admission du train est remplacé par le champ runner_proof_touched du JSON de « branch », R-20261106-28 et R-20261106-32).
Retrait : permanent tant que la tâche fusionne.

Le module ne fait ni fetch, ni fusion, ni push, n'écrit aucune référence, aucun fichier, aucun objet ; il ne source, n'enveloppe ni ne lance
tools/finish_train.sh. Branches non contrôlables (code 3) : main, spike/*, une
branche locale inconnue et lot/* (un train se contrôle branche par branche). Les listes (chemins de la base, chemins d'interface, fichiers évalués,
outillage protégé) sont lues dans origin/main, dans main local ET dans le sommet : leur union s'applique, une branche
ne peut pas se desserrer en retirant une entrée. Sortie JSON versionnée par « format », la logique est dans les fonctions de service
check_branch, check_tree, check_tree_14, protected_patterns et protected_touched, qui rendent des enregistrements.

Codes de sortie : 0 tous les contrôles calculés passent ou sont sans objet ; 1 au moins un contrôle refuse ; 2 usage ;
  3 branche non contrôlable (main, spike/*, branche locale inconnue, lot/*) ;
  4 calcul impossible (origin/main introuvable, base commune introuvable, git en échec, liste de l'outillage protégé illisible,
  erreur inattendue : le type seulement).

    python3 tools/finish_checks.py branch feat/ma-branche
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import posixpath
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True   # lecture seule : l'import des modules voisins n'écrit aucun fichier .pyc
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_paths  # noqa: E402
# posture_eval_fingerprint est importé dans controle_6 seulement : un module d'empreinte cassé donne le refus 6 dédié, jamais l'échec de tout le module (53)

PREFIXE = "finish_checks : "
FORMAT = 1
ORIGINE = "refs/remotes/origin/main"
LISTE_JEU = "tests/postures/fichiers-evalues.txt"
LISTE_PROTEGEE = "tools/finish_protected.txt"
LISTE_E2E = "tools/finish_e2e_paths.txt"   # source unique des chemins d'interface (finish-e2e-proof-shared D1) ; jamais copiée dans ce module
LISTE_DB = "tools/finish_db_paths.txt"     # source unique des chemins du code de la base (finish-single-b3-b6 D15) ; remplace l'ancien tableau CHEMINS_BASE de la fin unitaire (retirée par B9)
LISTE_RUNNER = "tools/finish_runner_paths.txt"   # source unique des chemins du runner et de la preuve (autonomous-trains-merge D3) ; remplace le motif littéral de l'admission de tools/finish_train.sh
ID_CONTROLES = ("19", "5", "6", "14", "16", "20")
DELAI_NODE = 30   # secondes accordées à « node --version » ; au-delà, Node est dit introuvable (refus, jamais un passage)

# Racines de la fermeture de l'outillage protégé (design D16). Un nom qui finit par « / » désigne chaque fichier suivi du dossier.
# finish-single-b7-b9, B9 (D8) : tools/finish_branch.sh et tools/finish_worktree.sh, retirés, cèdent la place au train, seul script de fin. Remplace : ces deux racines.
# Retrait : permanent tant que le train est le script de fin.
RACINES_FERMETURE = ("tools/finish_train.sh", "tests/run_all.sh", "tools/hooks/",
                     "tools/morning_state.sh", "tools/install_hooks.sh")

# Graines déclarées de D16 (motifs, écrits dans tools/finish_protected.txt avec leur raison). Celles qui désignent un .py ou un .sh de
# tools/ sont aussi des racines de la récursion : leurs imports, sources et lancements entrent dans la fermeture.
GRAINES_FERMETURE = (".claude/", "CLAUDE.md", "*/CLAUDE.md", ".gitattributes", "ci/",
                     "tools/dbtest.sh", "tools/ci_local.sh", "tools/run_worktree.sh", "tools/worktree.sh", "tools/gh_issue.py", "tools/composants.py",
                     "tools/settings_assemble.py", "tools/pipe_guard.py", "tools/npm_guard.py", "tools/npm_ci_conditions.py", "tools/garde_session.py", "tools/db_backup.sh", "tools/offsite_backup.sh",
                     "tools/lab_paths.*", "tools/secret_scan*", "tools/sensitive_names.py", "tools/commit_names_scan.py",
                     "tools/identifiants_personnels.py", "tools/posture_eval_fingerprint.py", "tools/select_suites.py",
                     "tools/range_scan.py", "tools/finish_checks.py", "tools/finish_protected.txt",
                     "tests/hooks/", "tests/settings_deny/", "tests/run_all/", "tests/finish_*", "tests/db/test_couverture_base.py",
                     "tests/range_scan/", "tests/finish_checks/")


class Impossible(Exception):
    """Un calcul impossible (code 4) : le message est la raison, déjà dite en une phrase."""


class NonControlable(Exception):
    """Une branche non contrôlable (code 3) : le message est le motif."""


# --- analyse des listes (partagée avec tests/db/test_couverture_base.py) -------------------------------------------------------------

def bloc_bash(texte: str, ouverture: str) -> list[str]:
    """Les mots entre guillemets ou nus du tableau Bash « ouverture(...) » ; les lignes de commentaire sont ignorées. Sert à tests/db/test_couverture_base.py
    pour SUITES_PAR_DEFAUT de tools/dbtest.sh ; les chemins de la base ne sont plus un tableau Bash (tools/finish_db_paths.txt, lu par motifs_proteges)."""
    m = re.search(r"^" + re.escape(ouverture) + r"=\((.*?)\)\s*$", texte, re.S | re.M)
    if not m:
        return []
    corps = "\n".join(ligne for ligne in m.group(1).splitlines() if not ligne.lstrip().startswith("#"))
    return [entre_guillemets or nu for entre_guillemets, nu in re.findall(r'"([^"]+)"|(\S+)', corps)]


def couvert(chemin: str, motifs: list[str]) -> bool:
    """Un chemin est couvert par un motif : préfixe quand le motif finit par « / », sinon joker de type Git (« * » traverse les dossiers)."""
    for motif in motifs:
        if motif.endswith("/"):
            if chemin.startswith(motif):
                return True
        elif fnmatch.fnmatchcase(chemin, motif):
            return True
    return False


def motifs_proteges(texte: str) -> list[str]:
    """Les motifs de tools/finish_protected.txt, finish_e2e_paths.txt et finish_db_paths.txt (même format) : un par ligne, « # » commence un
    commentaire, lignes vides ignorées."""
    motifs = []
    for ligne in texte.splitlines():
        ligne = ligne.split("#", 1)[0].strip()
        if ligne:
            motifs.append(ligne)
    return motifs


# --- Git, en lecture seule ------------------------------------------------------------------------------------------------------------

# Variables de l'environnement qui changent ce que Git lit (dépôt, arbre de travail, index, lecture des chemins) : jamais transmises.
_GIT_RETIREES = ("GIT_LITERAL_PATHSPECS", "GIT_GLOB_PATHSPECS", "GIT_NOGLOB_PATHSPECS", "GIT_ICASE_PATHSPECS", "GIT_DIR", "GIT_WORK_TREE",
                 "GIT_COMMON_DIR", "GIT_INDEX_FILE")


def _env() -> dict:
    env = dict(os.environ)
    for nom in _GIT_RETIREES:
        env.pop(nom, None)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def _git(repo, *args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, env=_env())
    except OSError:
        raise Impossible("git en échec")


def _sortie(repo, *args: str) -> str:
    """La sortie de la commande Git, sans le saut de ligne final ; un échec de Git est un calcul impossible."""
    fait = _git(repo, *args)
    if fait.returncode != 0:
        raise Impossible("git en échec")
    return fait.stdout.decode("utf-8", errors="replace").strip()


def _commit(repo, rev: str) -> str | None:
    fait = _git(repo, "rev-parse", "--verify", "-q", f"{rev}^{{commit}}")
    return fait.stdout.decode().strip() if fait.returncode == 0 else None


def _arbre(repo, rev: str) -> str | None:
    fait = _git(repo, "rev-parse", "--verify", "-q", f"{rev}^{{tree}}")
    return fait.stdout.decode().strip() if fait.returncode == 0 else None


def _afficher(repo, rev: str, chemin: str) -> str | None:
    """Le texte du fichier à une révision, ou None quand il n'y est pas."""
    fait = _git(repo, "show", f"{rev}:{chemin}")
    return fait.stdout.decode("utf-8", errors="replace") if fait.returncode == 0 else None


def _chemins_changes(repo, de: str, vers: str, specs: list[str] | None = None) -> list[str]:
    commande = ["diff", "--name-only", "--no-renames", "-z", de, vers]
    if specs is not None:
        commande += ["--", *specs]
    fait = _git(repo, *commande)
    if fait.returncode != 0:
        raise Impossible("git en échec")
    return [p.decode("utf-8", errors="replace") for p in fait.stdout.split(b"\0") if p]


def _base_origine(repo) -> str:
    base = _commit(repo, ORIGINE)
    if base is None:
        raise Impossible("origin/main introuvable")
    return base


def _depot_lisible(repo) -> None:
    if _git(repo, "rev-parse", "--git-dir").returncode != 0:
        raise Impossible("git en échec")


def _base_commune(repo, origine: str, sommet: str) -> str:
    fait = _git(repo, "merge-base", origine, sommet)
    if fait.returncode != 0 or not fait.stdout.strip():
        raise Impossible("base commune introuvable")
    return fait.stdout.decode().strip()


def _chemins_union(repo, bases: list[str], vers: str, specs: list[str] | None = None) -> list[str]:
    """L'union (dans l'ordre) des chemins changés entre chaque base et `vers`."""
    return _union(*(_chemins_changes(repo, base, vers, specs) for base in bases))


def _union(*listes) -> list[str]:
    vus, resultat = set(), []
    for liste in listes:
        for entree in liste:
            if entree not in vus:
                vus.add(entree)
                resultat.append(entree)
    return resultat


def _liste_union(repo, revs, chemin: str, analyse) -> tuple[list[str], bool]:
    """L'union des entrées d'une liste lues à chaque révision, et si elle a pu être lue quelque part."""
    entrees, lue = [], False
    for rev in revs:
        texte = _afficher(repo, rev, chemin)
        if texte is None:
            continue
        lue = True
        entrees.append(analyse(texte))
    return _union(*entrees), lue


# --- les contrôles ----------------------------------------------------------------------------------------------------------------------

def _controle(identifiant: str, verdict: str, phrase: str, details: list[str] | None = None) -> dict:
    return {"id": identifiant, "verdict": verdict, "phrase": phrase, "details": details or []}


def _lisible_par_le_script(chemin: str) -> bool:
    """Le script lit « git diff --name-only » sans -z, avec core.quotepath par défaut : un chemin non ASCII sort entre guillemets, un
    guillemet ou un saut de ligne brouille la lecture. Le module refuse l'exemption dans ces cas (miroir du script, sens strict)."""
    return chemin.isascii() and '"' not in chemin and "\n" not in chemin and "\r" not in chemin


def _branche_de_specification(modifies: list[str]) -> bool:
    return bool(modifies) and all(chemin.startswith("openspec/") and _lisible_par_le_script(chemin) for chemin in modifies)


def _specification_sur_chaque_base(repo, bases: list[str], sommet: str) -> bool:
    """L'exemption ne vaut que si, depuis CHAQUE base, l'ensemble des chemins changés est non vide et tout sous openspec/."""
    return all(_branche_de_specification(_chemins_changes(repo, base, sommet)) for base in bases)


def controle_19(branche: str, modifies: list[str], specification: bool | None = None) -> dict:
    """Une branche ne porte qu'un change : un chemin du dossier d'un change actif autre que le sien refuse (règle de verif_19)."""
    if _branche_de_specification(modifies) if specification is None else specification:
        return _controle("19", "exempt", "contrôle 19 : sans objet (branche de spécification)")
    propre = branche.rsplit("/", 1)[-1]
    autres, archives = set(), set()
    for chemin in modifies:
        if chemin.startswith("openspec/changes/archive/"):
            morceaux = chemin[len("openspec/changes/archive/"):].split("/")
            if len(morceaux) >= 2:   # un fichier directement sous l'archive (.gitkeep) n'est jamais un change actif
                nom = morceaux[0]
                if re.sub(r"^\d{4}-\d{2}-\d{2}-", "", nom) != propre:
                    archives.add(nom)
        elif chemin.startswith("openspec/changes/"):
            reste = chemin[len("openspec/changes/"):]
            if "/" in reste and reste.split("/", 1)[0] != propre:
                autres.add(reste.split("/", 1)[0])
    details = []
    if archives:
        details.append(f"la branche modifie l'archive d'un autre change : {', '.join(sorted(archives))} (permis)")
    if autres:
        return _controle("19", "refused", f"contrôle 19 : refusé : la branche touche un autre change OpenSpec : {', '.join(sorted(autres))}",
                         ["une branche ne porte qu'un change ; déplace ce travail dans sa propre branche"])
    return _controle("19", "pass", "contrôle 19 : passe", details)


def controle_5(repo, branche: str, sommet: str, modifies: list[str], specification: bool | None = None) -> dict:
    """Un change OpenSpec lié à la branche (par le dernier segment de son nom ou par un chemin modifié) et resté au sommet refuse."""
    if _branche_de_specification(modifies) if specification is None else specification:
        return _controle("5", "exempt", "contrôle 5 : sans objet (branche de spécification)")
    dernier = branche.rsplit("/", 1)[-1]
    fait = _git(repo, "ls-tree", "--name-only", sommet, "openspec/changes/")
    if fait.returncode != 0:   # un dossier absent du sommet n'est pas un échec (code 0, sortie vide) ; un échec de Git est un calcul impossible
        raise Impossible("git en échec")
    noms = [ligne[len("openspec/changes/"):] for ligne in fait.stdout.decode("utf-8", errors="replace").splitlines()]
    non_archives = []
    for nom in noms:
        if not nom or nom == "archive":
            continue
        if nom == dernier or any(chemin.startswith(f"openspec/changes/{nom}/") for chemin in modifies):
            non_archives.append(nom)
    if non_archives:
        return _controle("5", "refused", "contrôle 5 : refusé : change OpenSpec non archivé", non_archives)
    return _controle("5", "pass", "contrôle 5 : passe")


def _candidats_essais(dossier: Path) -> list[tuple[str, str, str, str, str]]:
    """Les enregistrements complets, validants, non rejugés, en langue par défaut : (date, base, réussies, total, empreinte ou « - »)."""
    lignes = []
    for chemin in sorted(dossier.glob("*/resultats.json")) if dossier.is_dir() else []:
        try:
            d = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict):
            continue
        cas = d.get("cas") or []
        complet = d.get("complet", len(cas) >= 10)
        if not complet or not d.get("validant", True) or d.get("rejuge") or d.get("langue", "fr") != "fr" or not d.get("base"):
            continue
        verifs = [v for c in cas for v in (c.get("verifications") or []) if not v.get("indicateur")]
        reussies = sum(1 for v in verifs if v.get("ok"))
        empreinte = str(d.get("evaluated_fingerprint") or "-").replace("\t", " ")
        lignes.append((str(d.get("date", "?")), str(d["base"]), str(reussies), str(len(verifs)), empreinte))
    return sorted(lignes)


def _lire_liste_jeu(texte: str) -> list[str]:
    """Les entrées de tests/postures/fichiers-evalues.txt : ni lignes vides ni commentaires (même lecture que posture_eval_fingerprint.read_list,
    qu'on n'importe pas ici pour que son échec ne touche que l'empreinte)."""
    return [ligne.strip() for ligne in texte.splitlines() if ligne.strip() and not ligne.lstrip().startswith("#")]


def controle_6(repo, bases: list[str], sommet: str, revs_listes, env) -> dict:
    """Quand un fichier de la liste des fichiers évalués diffère entre une base et le sommet, un jeu d'essai validant est exigé."""
    refus = "contrôle 6 : refusé : jeu d'essai validant absent"
    specs, _ = _liste_union(repo, revs_listes, LISTE_JEU, _lire_liste_jeu)
    if not specs:
        return _controle("6", "refused", refus, ["liste des fichiers évalués absente ou vide"])
    if not _chemins_union(repo, bases, sommet, specs):
        return _controle("6", "exempt", "contrôle 6 : sans objet (aucun fichier évalué changé)")
    # comme le script de fin : FINISH_BRANCH_RECORDS, quand elle n'est pas vide, désigne le dossier des enregistrements
    dossier_env = env.get("FINISH_BRANCH_RECORDS", "")
    if not dossier_env:   # sinon le dossier de données du lab, trouvé par le module partagé ; introuvable : refus (la ligne de la fin unitaire)
        try:
            lab_paths.content_root(env)
        except lab_paths.LabPathsError:
            return _controle("6", "refused", refus, ["le dossier de données du lab est introuvable : les enregistrements du jeu d'essai ne peuvent pas être lus."])
    dossier = Path(dossier_env) if dossier_env else lab_paths.data_folder(env) / "essais"
    try:
        import posture_eval_fingerprint   # ici et non en tête : un module cassé (même une sortie à l'import) est un échec d'empreinte, pas du module
        empreinte_sommet = posture_eval_fingerprint.fingerprint(Path(repo), sommet, specs)
        echec_empreinte = False
    except (Exception, SystemExit):
        empreinte_sommet, echec_empreinte = "", True
    trouve, disparu = "", False
    for date, base_essai, reussies, total, empreinte in _candidats_essais(dossier):
        if empreinte != "-":   # un enregistrement qui porte une empreinte ne se compare que par elle, jamais par l'état testé
            if empreinte_sommet and empreinte == empreinte_sommet:
                trouve = f"{date} ({reussies}/{total}) (empreinte des fichiers évalués)"
            continue
        if _commit(repo, base_essai) is None:
            disparu = True
            continue
        if not _chemins_changes(repo, base_essai, sommet, specs):
            trouve = f"{date} ({reussies}/{total})"
    if trouve:
        return _controle("6", "pass", "contrôle 6 : passe", [f"jeu d'essai validant trouvé : {trouve}"])
    if echec_empreinte:
        return _controle("6", "refused", refus, ["l'empreinte des fichiers évalués du sommet n'a pas pu être calculée (tools/posture_eval_fingerprint.py) : "
                                                 "aucun passage ne peut être compté par empreinte.",
                                                 "Corrige l'outil ou la liste des fichiers évalués, puis relance."])
    if disparu:
        return _controle("6", "refused", refus, ["l'état testé n'existe plus : relance le jeu d'essai sur l'état commité de la branche."])
    return _controle("6", "refused", refus, ["CLAUDE.md, une posture, Critic, le vocabulaire ou la mémoire figée ont changé sans passage complet "
                                             "validant pour ce sommet.",
                                             "Lance le jeu d'essai sur l'état commité, puis relance."])


def _controle_14(repo, bases: list[str], vers: str, arbre: str, revs_listes) -> dict:
    """Quand un chemin de CHEMINS_BASE a changé depuis une base, la ligne de l'arbre doit figurer dans pmzilla-dbtest-ok du dossier Git commun."""
    refus = "contrôle 14 : refusé : passage dbtest vert absent"
    specs, _ = _liste_union(repo, revs_listes, LISTE_DB, motifs_proteges)   # même format que la liste protégée : « # », lignes vides, espaces
    if not specs:
        return _controle("14", "refused", refus, [f"liste des chemins de la base absente ou illisible : {LISTE_DB}"])
    if not _chemins_union(repo, bases, vers, specs):
        return _controle("14", "exempt", "contrôle 14 : sans objet (code de la base inchangé)")
    commun = _sortie(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    try:
        lignes = (Path(commun) / "pmzilla-dbtest-ok").read_text(encoding="utf-8").splitlines()
    except OSError:
        lignes = []
    if arbre and arbre in lignes:   # jamais un arbre vide contre une ligne vide du registre
        return _controle("14", "pass", "contrôle 14 : passe", ["passage dbtest vert trouvé pour l'arbre du sommet"])
    return _controle("14", "refused", refus, ["Le code de la base a changé sans passage vert de tools/dbtest.sh pour cet arbre."])


def _controle_16(repo, bases: list[str], vers: str, arbre: str, revs_listes) -> dict:
    """Quand un chemin de tools/finish_e2e_paths.txt a changé depuis une base, la ligne de l'arbre doit figurer dans pmzilla-e2e-ok du dossier
    Git commun (finish-e2e-proof-shared, D2 à D4). Une seule fonction pour les modes branch et tree. Liste illisible partout : refusé, jamais exempt."""
    refus = "contrôle 16 : refusé : preuve de bout en bout absente"
    specs, _ = _liste_union(repo, revs_listes, LISTE_E2E, motifs_proteges)   # même format que la liste protégée : « # », lignes vides, espaces
    if not specs:
        return _controle("16", "refused", refus, ["liste des chemins d'interface absente ou illisible"])
    if not _chemins_union(repo, bases, vers, specs):
        return _controle("16", "exempt", "contrôle 16 : sans objet (chemins d'interface inchangés)")
    commun = _sortie(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    try:
        lignes = (Path(commun) / "pmzilla-e2e-ok").read_text(encoding="utf-8").splitlines()
    except OSError:
        lignes = []
    if arbre and arbre in lignes:   # jamais un arbre vide contre une ligne vide du registre
        return _controle("16", "pass", "contrôle 16 : passe", ["preuve de bout en bout trouvée pour l'arbre du sommet"])
    return _controle("16", "refused", refus, ["Un chemin d'interface de Mothra a changé sans preuve de bout en bout pour cet arbre.",
                                              "lancer bash tools/dbtest.sh --e2e puis relancer la fin"])


def _version_de_node(texte: str) -> str:
    """Une version de Node comme la fin la lit : espaces retirés, un « v » de tête retiré."""
    version = "".join(texte.split())
    return version[1:] if version.startswith("v") else version


def node_matches(found: str, want: str) -> bool:
    """La règle de Node unique (design D16 ; R-20261030-24, application de R-20261028-30 au registre), celle du contrôle 20 et du code 80 du train : la version trouvée est la version voulue, à l'égalité
    exacte près ou si la voulue est un préfixe de segments de la trouvée (« 22 » ou « 22.11 » pour « 22.11.0 ») ; le « v » de tête est sans
    effet ; une version vide ne correspond jamais."""
    trouvee, voulue = _version_de_node(found), _version_de_node(want)
    return bool(trouvee) and bool(voulue) and (trouvee == voulue or trouvee.startswith(voulue + "."))


def _node_trouve(env) -> str:
    """La sortie de « node --version » (enfant en lecture seule, entrée standard fermée), sans le « v » ; vide si Node manque ou échoue."""
    try:
        fait = subprocess.run(["node", "--version"], capture_output=True, stdin=subprocess.DEVNULL, env=dict(env), timeout=DELAI_NODE)
    except (OSError, subprocess.SubprocessError):
        return ""
    return _version_de_node(fait.stdout.decode("utf-8", errors="replace")) if fait.returncode == 0 else ""


def _dossier_de_la_branche(repo, branche: str) -> str | None:
    """Le dossier du worktree (le dossier courant compris) où la branche est ouverte, ou None."""
    sortie = _sortie(repo, "worktree", "list", "--porcelain")
    dossier = None
    for ligne in sortie.splitlines():
        if ligne.startswith("worktree "):
            dossier = ligne[len("worktree "):]
        elif ligne == f"branch refs/heads/{branche}" and dossier is not None:
            return dossier
    return None


def _controle_20(repo, branche: str, sommet: str, env) -> dict:
    """Quand tests/run_all.sh du sommet déclare des suites npm (ligne SUITES_NPM=(<dossier>:<nom> …)), le Node trouvé doit correspondre (node_matches)
    à <dossier>/.node-version de l'arbre où la branche est ouverte, sinon refus avec la commande « lancer : cd <dossier> && npm ci ». Le verrou npm
    n'est jamais comparé ici : le runner complet l'arrête avec son code 7. Une branche ouverte nulle part n'a rien à contrôler (sans objet)."""
    texte = _afficher(repo, sommet, "tests/run_all.sh") or ""
    m = re.search(r"^SUITES_NPM=\((.*)\)[ \t]*$", texte, re.M)
    entrees = m.group(1).split() if m else []
    if not entrees:
        return _controle("20", "exempt", "contrôle 20 : sans objet (aucune suite npm déclarée)")
    arbre = _dossier_de_la_branche(repo, branche)
    if arbre is None or not os.path.isdir(arbre):
        return _controle("20", "exempt", "contrôle 20 : sans objet (branche ouverte nulle part)")
    trouve = None
    for entree in entrees:
        dossier = entree.split(":", 1)[0]
        if not dossier or "/" in dossier or ".." in dossier:
            continue
        if not os.path.isdir(os.path.join(arbre, dossier)):
            continue   # un dossier absent reste l'échec nommé du runner
        try:
            with open(os.path.join(arbre, dossier, ".node-version"), encoding="utf-8", errors="replace") as f:
                voulue = _version_de_node(f.read())
        except OSError:
            voulue = ""
        if trouve is None:
            trouve = _node_trouve(env)
        if not voulue or not node_matches(trouve, voulue):
            raison = f"Node {trouve or 'introuvable'} au lieu de {voulue or '?'}, fixé par {dossier}/.node-version"
            choix = f"choisir la version {voulue or f'fixée par {dossier}/.node-version'} de Node, puis :"
            return _controle("20", "refused", f"contrôle 20 : refusé : dépendances npm à mettre en conformité avant la fin ({raison})",
                             [choix, f"lancer : cd {arbre}/{dossier} && npm ci"])
    return _controle("20", "pass", "contrôle 20 : passe")


# --- outillage protégé ------------------------------------------------------------------------------------------------------------------

def protected_patterns(repo, tip: str = "HEAD") -> list[str]:
    """Les motifs de l'outillage protégé : union de ceux d'origin/main, de main local et de `tip` (jamais l'arbre de travail seul)."""
    revs = _union(*([r] for r in (ORIGINE, "refs/heads/main", tip) if _commit(repo, r) is not None))
    motifs, lue = _liste_union(repo, revs, LISTE_PROTEGEE, motifs_proteges)
    if not lue:
        raise Impossible("liste de l'outillage protégé illisible")
    return motifs


def protected_touched(repo, base: str | list[str], tip: str, patterns: list[str] | None = None) -> list[str]:
    """Les fichiers protégés que le sommet change depuis la base (ou depuis chacune des bases, en union), triés ;
    la liste lue est l'union d'origin/main, de main local et du sommet."""
    motifs = protected_patterns(repo, tip) if patterns is None else patterns
    bases = [base] if isinstance(base, str) else base
    return sorted(chemin for chemin in _chemins_union(repo, bases, tip) if couvert(chemin, motifs))


def runner_proof_paths(repo, tip: str = "HEAD") -> list[str]:
    """Les entrées de tools/finish_runner_paths.txt (autonomous-trains-merge, D3) : union des lectures à origin/main, à main local et à `tip`, comme les autres
    listes ; absente partout : Impossible (jamais une liste vide, qui admettrait une branche du runner dans un train de plusieurs)."""
    revs = _union(*([r] for r in (ORIGINE, "refs/heads/main", tip) if _commit(repo, r) is not None))
    motifs, lue = _liste_union(repo, revs, LISTE_RUNNER, motifs_proteges)
    if not lue:
        raise Impossible("liste des chemins du runner et de la preuve illisible")
    return motifs


def runner_proof_touched(repo, base: str | list[str], tip: str, patterns: list[str] | None = None) -> list[str]:
    """Les chemins du runner et de la preuve que le sommet change depuis la base (ou depuis chacune des bases, en union), triés."""
    motifs = runner_proof_paths(repo, tip) if patterns is None else patterns
    bases = [base] if isinstance(base, str) else base
    return sorted(chemin for chemin in _chemins_union(repo, bases, tip) if couvert(chemin, motifs))


# Classes de l'outillage protégé (change finish-single-b3-b6, B4, design D9) : chaque ligne de motif de tools/finish_protected.txt se termine par une étiquette
# dans son commentaire, `#[juge]` ou `#[sensible]` (texte libre ensuite). L'étiquette est après « # » : le lecteur d'avant B4 (motifs_proteges) lit les mêmes motifs,
# aucune protection n'est perdue tant qu'un lecteur ancien tourne. Un motif sans étiquette, ou à étiquette inconnue, compte `juge` (le plus strict).
_ETIQUETTE_CLASSE = re.compile(r"\[(juge|sensible)\]")


def classes_proteges(texte: str) -> dict[str, str]:
    """{motif : classe} d'un texte de la liste, dans l'ordre des lignes ; un motif écrit deux fois avec deux classes compte `juge`."""
    classes: dict[str, str] = {}
    for ligne in texte.splitlines():
        motif, _, commentaire = ligne.partition("#")
        motif = motif.strip()
        if not motif:
            continue
        trouvee = _ETIQUETTE_CLASSE.match(commentaire)
        classe = trouvee.group(1) if trouvee else "juge"
        if len(_ETIQUETTE_CLASSE.findall(commentaire)) > 1:  # plus d'une étiquette sur la ligne : refus par défaut
            classe = "juge"
        classes[motif] = "juge" if classes.get(motif, classe) != classe else classe
    return classes


def protected_classes(repo, tip: str = "HEAD") -> dict[str, str]:
    """La classe de chaque motif de l'union (origin/main, main local, `tip`, comme protected_patterns) ; un motif d'une classe à une révision et d'une autre
    à une autre, ou sans étiquette à l'une, compte `juge` (union la plus stricte)."""
    revs = _union(*([r] for r in (ORIGINE, "refs/heads/main", tip) if _commit(repo, r) is not None))
    classes: dict[str, str] = {}
    lue = False
    for rev in revs:
        texte = _afficher(repo, rev, LISTE_PROTEGEE)
        if texte is None:
            continue
        lue = True
        for motif, classe in classes_proteges(texte).items():
            classes[motif] = "juge" if classes.get(motif, classe) != classe else classe
    if not lue:
        raise Impossible("liste de l'outillage protégé illisible")
    return classes


def protected_split(touches: list[str], classes: dict[str, str]) -> tuple[list[str], list[str]]:
    """(fichiers `juge`, fichiers `sensible`) parmi les fichiers protégés touchés, triés ; un fichier couvert par un motif `juge` est `juge`."""
    juges = [motif for motif, classe in classes.items() if classe == "juge"]
    return (sorted(c for c in touches if couvert(c, juges)), sorted(c for c in touches if not couvert(c, juges)))


# --- fonctions de service -----------------------------------------------------------------------------------------------------------------

def _non_controlable(repo, branche: str) -> str | None:
    if _commit(repo, f"refs/heads/{branche}") is None:
        return "branche locale inconnue"
    if branche == "main":
        return "branche main"
    if branche.startswith("spike/"):
        return "branche spike/*"
    if branche.startswith("lot/"):
        return "branche de train lot/* : contrôler chaque branche du train"
    return None


def check_branch(repo, branche: str, env=None) -> dict:
    """Les contrôles 19, 5, 6, 14, 16 et 20 de la branche, tous calculés, et les fichiers protégés touchés. Jamais d'exception pour un cas attendu :
    le code 3 ou 4 est dans l'enregistrement, avec `error`."""
    env = os.environ if env is None else env
    resultat = {"format": FORMAT, "branch": branche, "tip": None, "base": None, "base_local": None, "controls": [], "runner_proof_touched": [],
                "protected_touched": [], "protected_judges": [], "protected_sensitive": [], "exit": 0}
    try:
        _depot_lisible(repo)
        motif = _non_controlable(repo, branche)
        if motif:
            raise NonControlable(motif)
        sommet = _commit(repo, f"refs/heads/{branche}")
        origine = _base_origine(repo)
        base = _base_commune(repo, origine, sommet)
        # main local, quand il existe et diffère d'origin/main (en avance, en retard ou divergent) : le script de fin compte depuis lui ;
        # le module compte depuis les deux bases, l'union des chemins, et lit les listes aux trois révisions (décision du 2026-10-26, D10)
        principale = _commit(repo, "refs/heads/main")
        if principale is None:
            raise NonControlable("base commune avec main introuvable")   # comme le script de fin (code 3)
        base_locale = _base_commune(repo, principale, sommet) if principale != origine else None
        resultat["tip"], resultat["base"], resultat["base_local"] = sommet, base, base_locale
        bases = _union([base], [base_locale] if base_locale else [])
        modifies = _chemins_union(repo, bases, sommet)
        revs = _union([origine], [principale] if base_locale else [], [sommet])
        motifs = protected_patterns(repo, sommet)
        specification = _specification_sur_chaque_base(repo, bases, sommet)
        resultat["controls"] = [controle_19(branche, modifies, specification), controle_5(repo, branche, sommet, modifies, specification),
                                controle_6(repo, bases, sommet, revs, env),
                                _controle_14(repo, bases, sommet, _arbre(repo, sommet) or "", revs),
                                _controle_16(repo, bases, sommet, _arbre(repo, sommet) or "", revs),
                                _controle_20(repo, branche, sommet, env)]
        resultat["runner_proof_touched"] = runner_proof_touched(repo, bases, sommet)   # D3 : lu par l'admission du train à la place de son motif littéral
        resultat["protected_touched"] = protected_touched(repo, bases, sommet, motifs)
        resultat["protected_judges"], resultat["protected_sensitive"] = protected_split(resultat["protected_touched"], protected_classes(repo, sommet))
        resultat["exit"] = 1 if any(c["verdict"] == "refused" for c in resultat["controls"]) else 0
    except NonControlable as e:
        resultat.update(exit=3, error=f"branche non contrôlable : {e}")
    except Impossible as e:
        resultat.update(exit=4, error=f"calcul impossible ({e})")
    return resultat


def check_tree_14(repo, tree: str) -> dict:
    """Le contrôle 14 pour un arbre : chemins changés depuis origin/main, ligne de pmzilla-dbtest-ok pour cet arbre."""
    resultat = {"format": FORMAT, "tree": tree, "controls": [], "exit": 0}
    try:
        _depot_lisible(repo)
        origine = _base_origine(repo)
        arbre = _arbre(repo, tree)
        if arbre is None:
            raise Impossible("git en échec")
        resultat["tree"] = arbre
        resultat["controls"] = [_controle_14(repo, [origine], arbre, arbre, (origine, arbre))]
        resultat["exit"] = 1 if resultat["controls"][0]["verdict"] == "refused" else 0
    except Impossible as e:
        resultat.update(exit=4, error=f"calcul impossible ({e})")
    return resultat


def check_tree(repo, tree: str, env=None) -> dict:
    """Les contrôles 14, 16 puis 6 pour un arbre : chemins changés depuis origin/main, ligne de pmzilla-dbtest-ok puis de pmzilla-e2e-ok pour cet arbre
    (finish-e2e-proof-shared, D8), puis le jeu d'essai validant par empreinte des fichiers évalués calculée sur l'arbre (finish-single-b3-b6, B6, D19 :
    même fonction que pour une branche, l'arbre à la place du sommet, origin/main pour base). check_tree_14 reste, inchangée, pour ses appelants."""
    env = os.environ if env is None else env
    resultat = {"format": FORMAT, "tree": tree, "controls": [], "exit": 0}
    try:
        _depot_lisible(repo)
        origine = _base_origine(repo)
        arbre = _arbre(repo, tree)
        if arbre is None:
            raise Impossible("git en échec")
        resultat["tree"] = arbre
        revs = (origine, arbre)
        resultat["controls"] = [_controle_14(repo, [origine], arbre, arbre, revs), _controle_16(repo, [origine], arbre, arbre, revs),
                                controle_6(repo, [origine], arbre, revs, env)]
        resultat["exit"] = 1 if any(c["verdict"] == "refused" for c in resultat["controls"]) else 0
    except Impossible as e:
        resultat.update(exit=4, error=f"calcul impossible ({e})")
    return resultat


def protected_report(repo) -> dict:
    """Les motifs effectifs de l'outillage protégé et les fichiers protégés que la branche courante touche."""
    resultat = {"format": FORMAT, "patterns": [], "touched": [], "exit": 0}
    try:
        _depot_lisible(repo)
        origine = _base_origine(repo)
        resultat["patterns"] = protected_patterns(repo, "HEAD")
        sommet = _commit(repo, "HEAD")
        if sommet is None:
            raise Impossible("base commune introuvable")
        base = _base_commune(repo, origine, sommet)
        principale = _commit(repo, "refs/heads/main")   # les deux bases comme protected_touched de check_branch (D10)
        base_locale = _base_commune(repo, principale, sommet) if principale is not None and principale != origine else None
        resultat["touched"] = protected_touched(repo, _union([base], [base_locale] if base_locale else []), sommet, resultat["patterns"])
    except Impossible as e:
        resultat.update(exit=4, error=f"calcul impossible ({e})")
    return resultat


# --- le train de l'auteur et la politique automatique (autonomous-trains-merge, design D2 et D7) ---------------------------------------------

def train_de_l_auteur(rec) -> bool:
    """La fonction UNIQUE qui dit qu'une branche est un train de l'auteur (D2) : sa différence touche un fichier `juge` de tools/finish_protected.txt (le runner et
    la preuve de D3 en sont), un chemin de .claude/ ou un fichier CLAUDE.md à toute profondeur, ou un fichier de tests/postures/fichiers-evalues.txt (contrôle 6
    applicable, c'est-à-dire de verdict `pass` ou `refused`, jamais `exempt`). `rec` est l'enregistrement de `check_branch` (le JSON de `branch`) ; la clé facultative
    `claude_paths` y ajoute les chemins de .claude/ et de CLAUDE.md que l'appelant a lus dans la différence quand la liste protégée ne les couvrirait pas.
    Un enregistrement incomplet ou illisible est un train de l'auteur (le doute refuse). Appelée par la politique automatique ; les exclusions du passage et
    `train_ready add` l'appellent (tranche 3, D16, par `train_de_l_auteur_de_la_branche`) : aucun appelant n'en garde de copie. Remplace : rien (P1 n'est allégé que hors de cet ensemble). Retrait :
    permanent tant que la tâche fusionne."""
    try:
        if rec.get("runner_proof_touched", True):   # revue Opus 4.1, constat 5 : le runner ou la preuve touchés, ou la clé absente (le doute), font un train de l'auteur
            return True
        juges = rec["protected_judges"]
        if not isinstance(juges, list):
            return True
        if juges:
            return True
        chemins = list(rec["protected_touched"]) + list(rec.get("claude_paths", []))
        if any(c.startswith(".claude/") or posixpath.basename(c) == "CLAUDE.md" for c in chemins):
            return True
        verdicts = {c["id"]: c["verdict"] for c in rec["controls"]}
        return verdicts["6"] != "exempt"
    except (KeyError, TypeError, AttributeError):
        return True


# Raisons de la politique (D7), dans l'ordre où elles sont listées. Les libellés sont ceux de D7 ; le train les lit par `policy-lines` (jamais une copie dans le script).
POLITIQUE_LIBELLES = {
    "inactif": "fusion automatique non activée",
    "activation-invalide": "fichier d'activation invalide",
    "arret": "arrêt d'urgence actif",
    "liste-illisible": "liste prête illisible",
    "absente-de-la-liste": "branche absente de la liste prête",
    "sommet-non-atteste": "sommet différent de la liste prête",
    "revue-absente": "revue Opus absente pour ce sommet",
    "train-de-l-auteur": "outillage de fin, runner, preuve, .claude/, CLAUDE.md ou postures : train de l'auteur",
    "plafond": "plus de 3 branches : train de l'auteur",
    "calcul-impossible": "contrôles de fin impossibles",
}
POLITIQUE_ORDRE = tuple(POLITIQUE_LIBELLES)
POLITIQUE_PLAFOND = 3   # au plus trois branches par train automatique (D7)
_HEX40 = re.compile(r"[0-9a-f]{40}")


def _chemins_claude(repo, rec) -> list[str]:
    """Les chemins de .claude/ et les fichiers CLAUDE.md de la différence de la branche (mêmes bases que `check_branch`), pour `train_de_l_auteur`."""
    bases = _union([rec["base"]], [rec["base_local"]] if rec.get("base_local") else [])
    return [c for c in _chemins_union(repo, bases, rec["tip"]) if c.startswith(".claude/") or posixpath.basename(c) == "CLAUDE.md"]


def train_de_l_auteur_de_la_branche(repo, rec) -> bool:
    """`train_de_l_auteur` sur l'enregistrement de `check_branch` (ou son JSON), complété des chemins de .claude/ et de CLAUDE.md de la différence : le point d'entrée
    des exclusions du passage et de `train_ready add` (D16). Le moindre doute (chemins illisibles) est un train de l'auteur. Remplace : rien. Retrait : permanent, avec `train_de_l_auteur`."""
    try:
        return train_de_l_auteur(dict(rec, claude_paths=_chemins_claude(repo, rec)))
    except Exception:   # le doute refuse
        return True


def auto_policy(repo, train_tip: str, branches: list[str], tips: list[str], env=None) -> dict:
    """La politique de la fusion automatique, en UN endroit (D7) : `{"format": 1, "allowed": bool, "reasons": [{"code", "branch"?}]}`. Toutes les raisons sont
    listées, dans l'ordre de D7. Lecture seule : aucun fichier, aucune référence ni aucun objet n'est écrit, et aucune variable d'environnement n'est lue comme une
    exemption (le refus des variables FINISH_TRAIN_CI et FINISH_TRAIN_RUNNER sous --auto est dans le train, code 61, R-20261106-57 ; condition de retrait de cette garde, R-20261107-4 : elle tombe quand finish_train.sh ne lit plus aucune variable FINISH_TRAIN_* sous --auto). Le moindre doute (calcul impossible, enregistrement incomplet, sommet qui a bougé, exception) donne `calcul-impossible`, donc `allowed` faux.
    Lit la liste prête et la règle de revue par tools/train_ready.py, les fichiers d'arrêt et d'activation par tools/train_auto.py, et le train de l'auteur par
    `train_de_l_auteur` : aucune copie de ces lecteurs ici."""
    raisons: list[tuple[str, str | None]] = []
    try:
        import train_auto
        import train_ready
        if (not isinstance(branches, list) or not branches or len(branches) != len(tips) or len(set(branches)) != len(branches)
                or not _HEX40.fullmatch(str(train_tip)) or not all(isinstance(t, str) and _HEX40.fullmatch(t) for t in tips)
                or _commit(repo, str(train_tip)) is None):
            raise Impossible("arguments de la politique")
        etat = train_auto.activation_state()
        if etat == "absent":
            raisons.append(("inactif", None))
        elif etat != "valide":
            raisons.append(("activation-invalide", None))
        if train_auto.stop_path().exists() or train_auto.stop_path().is_symlink():
            raisons.append(("arret", None))
        try:
            entrees = {e["branche"]: e for e in train_ready.read_list()}
        except (train_ready.ListeIllisible, OSError):
            entrees = None
            raisons.append(("liste-illisible", None))
        for branche, sommet in zip(branches, tips):
            rec = check_branch(repo, branche, env)
            if rec.get("exit") not in (0, 1) or rec.get("tip") != sommet or not isinstance(rec.get("controls"), list):
                raisons.append(("calcul-impossible", branche))   # contrôle 3 ou 4, enregistrement incomplet, ou la branche a bougé depuis le sommet donné
                continue
            chemins = train_ready.changed_paths(repo, branche)
            if chemins is None:
                raisons.append(("calcul-impossible", branche))
                continue
            attestee = False
            if entrees is not None:
                ligne = entrees.get(branche)
                if ligne is None:
                    raisons.append(("absente-de-la-liste", branche))
                elif ligne["sommet"] != sommet:
                    raisons.append(("sommet-non-atteste", branche))
                else:
                    attestee = True
                if not train_ready.review_free(chemins) and not (attestee and ligne["revue"] == "faite"):
                    raisons.append(("revue-absente", branche))
            if train_de_l_auteur(dict(rec, claude_paths=_chemins_claude(repo, rec))):
                raisons.append(("train-de-l-auteur", branche))
        if len(branches) > POLITIQUE_PLAFOND:
            raisons.append(("plafond", None))
    except Exception:   # tout doute refuse : jamais d'exception hors de la fonction
        raisons.append(("calcul-impossible", None))
    classees = sorted(raisons, key=lambda r: POLITIQUE_ORDRE.index(r[0]))
    return {"format": FORMAT, "allowed": not classees,
            "reasons": [({"code": c} if b is None else {"code": c, "branch": b}) for c, b in classees]}


def policy_exit(resultat: dict) -> int:
    """0 autorisé, 4 quand le calcul est impossible, 1 refusé (D7)."""
    if resultat["allowed"]:
        return 0
    return 4 if any(r["code"] == "calcul-impossible" for r in resultat["reasons"]) else 1


def policy_lines(texte: str) -> tuple[int, list[str], str]:
    """(code, lignes, raison) : une ligne par raison de la sortie JSON de `policy` lue sur l'entrée standard, `<libellé>` ou `<libellé> (<branche>)`, dans l'ordre
    de la sortie ; code 4 quand la sortie n'est pas du JSON de format 1 d'une politique refusée, ou porte un code de raison inconnu."""
    try:
        r = json.loads(texte)
        if not isinstance(r, dict) or r.get("format") != FORMAT or not isinstance(r.get("reasons"), list):
            raise ValueError
        lignes = []
        for raison in r["reasons"]:
            libelle = POLITIQUE_LIBELLES[raison["code"]]
            branche = raison.get("branch")
            lignes.append(libelle if branche is None else f"{libelle} ({branche})")
    except (ValueError, KeyError, TypeError, AttributeError):
        return 4, [], "sortie illisible (JSON de politique attendu)"
    return 0, [" ".join(ligne.split("\n")) for ligne in lignes], ""


# --- fermeture de l'outillage protégé (design D16) -------------------------------------------------------------------------------------

_LANCEUR = re.compile(r"""(?:^|[\s;&|(`"'])(?:\.|source|bash|sh|zsh|python3?|uv\s+run)(?=\s)""")
_NOM_OUTIL = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:sh|py)\b")
_IMPORT = re.compile(r"^\s*(?:import\s+([A-Za-z_][\w, ]*)|from\s+([A-Za-z_]\w*)\s+import\b)", re.M)
_CHEMIN = re.compile(r"[A-Za-z0-9_.][A-Za-z0-9_./+@-]*")
# Un jeton « /<nom>.sh|py » dont le nom est un fichier suivi de tools/ est une référence, quel que soit le mot qui le précède (fail-closed) :
# il voit « ${VAR:-python3 -I "$SCRIPT_DIR/outil.py"} », que le mot de lancement collé à « - » cache à la règle du lanceur.
_JETON_OUTIL = re.compile(r"/([A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:sh|py))\b")


def _lignes_de_code(texte: str) -> list[str]:
    return [ligne for ligne in texte.splitlines() if not ligne.lstrip().startswith("#")]


def racines_manquantes(suivis: list[str], racines=RACINES_FERMETURE) -> list[str]:
    suivis_ensemble = set(suivis)
    return [r for r in racines if (not any(s.startswith(r) for s in suivis_ensemble) if r.endswith("/") else r not in suivis_ensemble)]


def _fichiers_de_racine(suivis: list[str], racine: str) -> list[str]:
    return sorted(s for s in suivis if s.startswith(racine)) if racine.endswith("/") else ([racine] if racine in suivis else [])


def references(texte: str, suivis_ensemble: set[str]) -> tuple[set[str], set[str]]:
    """Les références d'un fichier, lues sur son texte sans rien lancer, commentaires ignorés : (suivies, lues).
    Suivies (a) : un fichier de tools/ qu'il source, lance (bash, sh, python3, uv run) ou importe. Lues (b) : tout fichier suivi dont le
    chemin figure dans son code."""
    suivies, lues = set(), set()
    lignes = _lignes_de_code(texte)
    for ligne in lignes:
        if _LANCEUR.search(ligne):
            for nom in _NOM_OUTIL.findall(ligne):
                if f"tools/{nom}" in suivis_ensemble:
                    suivies.add(f"tools/{nom}")
        for nom in _JETON_OUTIL.findall(ligne):
            if f"tools/{nom}" in suivis_ensemble:
                suivies.add(f"tools/{nom}")
        for jeton in _CHEMIN.findall(ligne):
            morceaux = re.sub(r"^(?:\.{1,2}/)+", "", posixpath.normpath(jeton)).rstrip(".").split("/")
            for i in range(len(morceaux)):   # « $RACINE/tools/x.py » : le plus long suffixe qui est un fichier suivi
                if i > 0 and len(morceaux) - i < 2:
                    break   # un nom seul n'est jamais lu comme un chemin, sauf le jeton entier
                if "/".join(morceaux[i:]) in suivis_ensemble:
                    lues.add("/".join(morceaux[i:]))
                    break
    corps = "\n".join(lignes)
    for m in _IMPORT.finditer(corps):
        noms = [n.strip() for n in (m.group(1) or "").split(",")] + [m.group(2) or ""]
        for nom in noms:
            nom = nom.split(" ")[0]
            if nom and f"tools/{nom}.py" in suivis_ensemble:
                suivies.add(f"tools/{nom}.py")
    return suivies, lues


def parcours(lecteur, suivis: list[str], racines=RACINES_FERMETURE, graines=GRAINES_FERMETURE,
             exemptions=()) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    """Le parcours de la fermeture : ({chemin : origine}, {(source, cible) : « suivi » ou « lu »}).
    L'origine est « racine », « graine » (un .py ou .sh de tools/ couvert par une graine déclarée, racine de la récursion), « suivi » (source,
    lancé ou importé, récursif) ou « lu » (nommé dans le code d'un fichier de la fermeture, jamais suivi plus loin). `lecteur(chemin)` rend le
    texte du fichier ou None. `exemptions` : des références (source, cible) coupées, chacune avec sa raison ailleurs ; une exemption coupe la
    récursion sur cette arête seulement. Les arêtes rendues comprennent les arêtes coupées, vues depuis un fichier atteint."""
    suivis_ensemble = set(suivis)
    exemptions = set(exemptions)
    resultat: dict[str, str] = {}
    aretes: dict[tuple[str, str], str] = {}
    a_voir: list[str] = []
    for racine in racines:
        for chemin in _fichiers_de_racine(suivis, racine):
            resultat[chemin] = "racine"
            a_voir.append(chemin)
    for chemin in sorted(suivis_ensemble):
        if chemin.startswith("tools/") and chemin.endswith((".py", ".sh")) and couvert(chemin, list(graines)) and chemin not in resultat:
            resultat[chemin] = "graine"
            a_voir.append(chemin)
    traites: set[str] = set()
    while a_voir:
        chemin = a_voir.pop()
        if chemin in traites:
            continue
        traites.add(chemin)
        texte = lecteur(chemin)
        if texte is None:
            continue
        suivies, lues = references(texte, suivis_ensemble)
        suivies.discard(chemin)
        lues.discard(chemin)
        for cible in sorted(suivies):
            aretes[(chemin, cible)] = "suivi"
            if (chemin, cible) in exemptions:
                continue
            if resultat.get(cible) in (None, "lu"):
                resultat[cible] = "suivi"
            a_voir.append(cible)
        for cible in sorted(lues - suivies):
            aretes[(chemin, cible)] = "lu"
            if (chemin, cible) in exemptions:
                continue
            resultat.setdefault(cible, "lu")
    return resultat, aretes


def fermeture(lecteur, suivis: list[str], racines=RACINES_FERMETURE, graines=GRAINES_FERMETURE, exemptions=()) -> dict[str, str]:
    """La fermeture des racines et des graines : {chemin : origine} (voir `parcours`)."""
    return parcours(lecteur, suivis, racines, graines, exemptions)[0]


# --- sorties --------------------------------------------------------------------------------------------------------------------------------

def _lignes_controles(controles: list[dict]) -> list[str]:
    lignes = []
    for c in controles:
        lignes.append(PREFIXE + c["phrase"])
        marque = "  - " if c["id"] == "5" else "  "
        lignes += [marque + d for d in c["details"]]
    return lignes


def formater_branche(r: dict) -> tuple[list[str], list[str]]:
    """(sortie standard, sortie d'erreur) du texte de « branch », construit seulement depuis l'enregistrement."""
    if r["exit"] in (3, 4):
        return [], [PREFIXE + r["error"]]
    sortie = _lignes_controles(r["controls"])
    if r["protected_judges"]:
        sortie.append(PREFIXE + f"outillage de fin touché : {len(r['protected_judges'])} fichier(s)")
        sortie += [f"  - {chemin}" for chemin in r["protected_judges"]]
    if r["protected_sensitive"]:
        sortie.append(PREFIXE + f"outil sensible touché : {len(r['protected_sensitive'])} fichier(s)")
        sortie += [f"  - {chemin}" for chemin in r["protected_sensitive"]]
    if not r["protected_touched"]:
        sortie.append(PREFIXE + "outillage protégé non touché")
    refuses = sum(1 for c in r["controls"] if c["verdict"] == "refused")
    sortie.append(PREFIXE + (f"{r['branch']} : {refuses} contrôle(s) refusé(s) sur {len(ID_CONTROLES)}" if refuses
                             else f"{r['branch']} : les {len(ID_CONTROLES)} contrôles passent"))
    return sortie, []


def formater_arbre(r: dict) -> tuple[list[str], list[str]]:
    if r["exit"] in (3, 4):
        return [], [PREFIXE + r["error"]]
    sortie = _lignes_controles(r["controls"])
    refuses = sum(1 for c in r["controls"] if c["verdict"] == "refused")
    sortie.append(PREFIXE + (f"arbre {r['tree'][:12]} : {refuses} contrôle(s) refusé(s) sur {len(r['controls'])}" if refuses
                             else f"arbre {r['tree'][:12]} : les contrôles 14, 16 et 6 passent"))
    return sortie, []


def formater_protege(r: dict) -> tuple[list[str], list[str]]:
    if r["exit"] in (3, 4):
        return [], [PREFIXE + r["error"]]
    sortie = [PREFIXE + f"outillage protégé : {len(r['patterns'])} motif(s)"] + [f"  - {motif}" for motif in r["patterns"]]
    if r["touched"]:
        sortie.append(PREFIXE + f"outillage protégé touché : {len(r['touched'])} fichier(s)")
        sortie += [f"  - {chemin}" for chemin in r["touched"]]
    else:
        sortie.append(PREFIXE + "outillage protégé non touché")
    return sortie, []


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="finish_checks.py", description="Contrôles de fin de branche en lecture seule.")
    sous = parser.add_subparsers(dest="commande", required=True)
    p_branche = sous.add_parser("branch", help="contrôles 19, 5, 6, 14, 16 et 20 d'une branche locale")
    p_branche.add_argument("branche", help="nom de la branche locale")
    p_arbre = sous.add_parser("tree", help="contrôles 14, 16 et 6 d'un arbre")
    p_arbre.add_argument("arbre", help="arbre, ou révision dont on prend l'arbre")
    p_protege = sous.add_parser("protected", help="motifs de l'outillage protégé et fichiers touchés")
    for p in (p_branche, p_arbre, p_protege):
        p.add_argument("--repo", default=".", help="dépôt Git (défaut : le dossier courant)")
        p.add_argument("--json", action="store_true", help="sortie JSON, format 1")
    p_politique = sous.add_parser("policy", help="politique de la fusion automatique : 0 autorisé, 1 refusé, 2 usage, 4 calcul impossible")
    p_politique.add_argument("--repo", default=".", help="dépôt Git (défaut : le dossier courant)")
    p_politique.add_argument("--json", action="store_true", help="sortie JSON, format 1")
    p_politique.add_argument("--train-tip", required=True, help="sommet du train")
    p_politique.add_argument("--branch", action="append", required=True, help="branche du train, dans l'ordre (à répéter, avec --tip)")
    p_politique.add_argument("--tip", action="append", required=True, help="sommet de la branche donnée au même rang (à répéter)")
    sous.add_parser("policy-lines", help="les raisons d'une sortie JSON de « policy » lue sur l'entrée standard, une ligne chacune")
    p_node = sous.add_parser("node-match", help="règle de Node unique : 0 correspond, 1 diffère, 2 usage")
    p_node.add_argument("trouve", help="version de Node trouvée")
    p_node.add_argument("attendu", help="version de Node attendue")
    p_extrait = sous.add_parser("extract", help="un champ de la sortie JSON de « branch » lue sur l'entrée standard")
    p_extrait.add_argument("champ", choices=("verdicts", "phrase", "details", "error"))
    p_extrait.add_argument("id", nargs="?", default="", help="contrôle (phrase, details)")
    return parser


def extraire(texte: str, champ: str, identifiant: str = "") -> tuple[int, list[str], str]:
    """(code, lignes, raison) : un champ de la sortie JSON de « branch » pour le script de fin. Code 4 quand la sortie n'est pas du JSON de format 1,
    quand un contrôle de ID_CONTROLES manque (verdicts, phrase, details) ou quand le champ demandé est absent. Les sauts de ligne d'une valeur sont
    remplacés par une espace : une ligne par valeur."""
    try:
        r = json.loads(texte)
    except ValueError:
        return 4, [], "sortie illisible (JSON attendu)"
    if not isinstance(r, dict) or r.get("format") != FORMAT:
        return 4, [], "format de sortie inconnu"
    if champ == "error":
        if not isinstance(r.get("error"), str):
            return 4, [], "aucune raison dans la sortie"
        return 0, [" ".join(r["error"].split("\n"))], ""
    controles = r.get("controls")
    if not isinstance(controles, list):
        return 4, [], "contrôles absents de la sortie"
    par_id = {c.get("id"): c for c in controles if isinstance(c, dict)}
    for identifiant_attendu in ID_CONTROLES:
        c = par_id.get(identifiant_attendu)
        if not isinstance(c, dict) or c.get("verdict") not in ("pass", "refused", "exempt") or not isinstance(c.get("phrase"), str) \
                or not isinstance(c.get("details"), list):
            return 4, [], f"contrôle {identifiant_attendu} absent ou illisible dans la sortie"
    if champ == "verdicts":
        return 0, [f"{i} {par_id[i]['verdict']}" for i in ID_CONTROLES], ""
    if identifiant not in par_id:
        return 4, [], f"contrôle {identifiant or '?'} inconnu"
    c = par_id[identifiant]
    if champ == "phrase":
        return 0, [" ".join(c["phrase"].split("\n"))], ""
    return 0, [" ".join(str(d).split("\n")) for d in c["details"]], ""


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)   # une erreur d'usage sort avec le code 2
    if args.commande == "node-match":
        return 0 if node_matches(args.trouve, args.attendu) else 1
    if args.commande == "extract":
        code, lignes, raison = extraire(sys.stdin.read(), args.champ, args.id)
        for ligne in lignes:
            print(ligne)
        if code != 0:
            print(PREFIXE + raison, file=sys.stderr)
        return code
    if args.commande == "policy-lines":
        code, lignes, raison = policy_lines(sys.stdin.read())
        for ligne in lignes:
            print(ligne)
        if code != 0:
            print(PREFIXE + raison, file=sys.stderr)
        return code
    if args.commande == "policy":
        if len(args.branch) != len(args.tip):
            _parser().error("--branch et --tip vont par paires")   # code 2
        try:
            politique = auto_policy(args.repo, args.train_tip, args.branch, args.tip)
        except Exception as e:   # jamais de trace de pile : le type seulement
            print(PREFIXE + f"calcul impossible (erreur inattendue ({type(e).__name__}))", file=sys.stderr)
            return 4
        if args.json:
            print(json.dumps(politique, ensure_ascii=False))
        elif politique["allowed"]:
            print(PREFIXE + "politique : départ autorisé")
        else:
            for raison in politique["reasons"]:
                branche = raison.get("branch")
                print(PREFIXE + "politique : " + POLITIQUE_LIBELLES[raison["code"]] + ("" if branche is None else f" ({branche})"))
        return policy_exit(politique)
    try:
        if args.commande == "branch":
            resultat, formater = check_branch(args.repo, args.branche), formater_branche
        elif args.commande == "tree":
            resultat, formater = check_tree(args.repo, args.arbre), formater_arbre
        else:
            resultat, formater = protected_report(args.repo), formater_protege
    except Exception as e:   # jamais de trace de pile : le type seulement
        resultat = {"format": FORMAT, "exit": 4, "error": f"calcul impossible (erreur inattendue ({type(e).__name__}))"}
        formater = lambda r: ([], [PREFIXE + r["error"]])  # noqa: E731
    if args.json:
        print(json.dumps(resultat, ensure_ascii=False))
    else:
        sortie, erreur = formater(resultat)
        for ligne in sortie:
            print(ligne)
        for ligne in erreur:
            print(ligne, file=sys.stderr)
    return resultat["exit"]


if __name__ == "__main__":
    sys.exit(main())
