#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
PMZilla Lab : UNE fonction calcule la preuve d'un arbre (change ci-local-runner, design D8, tâche 12.4).

    python3 -I tools/preuve_arbre.py <arbre> [--worktree <chemin>]

Exemple (l'arbre est un hachage Git de 40 caractères) :

    python3 tools/preuve_arbre.py 0123456789abcdef0123456789abcdef01234567

`preuve(arbre, worktree=None)` rend :
  - `complete` : l'empreinte du runner complet du worktree (pmzilla-run-all-ok) égale l'arbre (repli de l'auteur, gardé : R-20261101-76) ;
  - sinon `conteneur` : `ci/preuves` du dossier de données du lab porte l'arbre avec les trois phases (portable, base, e2e) ET pmzilla-run-mac-ok
    du dossier Git commun (écrit par `bash tests/run_all.sh --mac`, D7) le porte aussi ;
  - sinon `ciblee` : l'empreinte de branche du worktree (pmzilla-run-branch-ok, `run_all.sh --branch`) égale l'arbre (jusqu'à D10) ;
  - sinon None.
`complete` et `ciblee` ne se lisent qu'avec un worktree ; `conteneur` se lit sans (le dossier Git commun est alors celui du dossier courant).

CLI : imprime le mot (`complete`, `conteneur`, `ciblee`) ou `aucune`. Codes de sortie : 0 une preuve, 1 aucune preuve, 2 calcul impossible ou usage
(Git en échec quand le fichier du Mac doit être lu, arbre mal formé). Un appelant qui reçoit 2, ou toute autre sortie, n'a PAS de preuve (fermé).
Le module ne lit que : ces quatre fichiers, et le dossier Git commun (git rev-parse). Il n'écrit rien. Bibliothèque standard seulement.

Preuve d'index (tooling-proof-in-container, T2, D1, R-20261104-7 P5) :

    python3 -I tools/preuve_arbre.py --index <arbre> [--suites a,b]

`index_proven(arbre, suites, fichier)` : une ligne verte de `ci/preuves-index` du dossier de données (ou du fichier que nomme CI_LOCAL_PREUVES_INDEX, pour
les tests) porte l'arbre et couvre les suites demandées (`complet`, ou toutes les suites nommées). La ligne de commande imprime `conteneur-index` (code 0)
ou `aucune` (code 1) ; usage ou arbre mal formé : code 2. Ce n'est pas une preuve de commit : `preuve()` ne la lit pas. Appelant : tests/run_all.sh
(écriture de l'empreinte ciblée d'une session). Écrit par tools/ci_local.sh, seulement après un passage `--index` vert.
Remplace : rien (le runner de session écrivait l'empreinte ciblée sans preuve du conteneur). Retrait : permanent, tant que le pre-commit exige un passage vert.

Appelants : tools/train_ready.py (`proof_of`, import à la demande) et tools/hooks/pre-push (`python3 -I`, pour l'arbre poussé : `complete` ou
`conteneur` passent, `ciblee` jamais).

Remplace : les deux lectures séparées de l'empreinte complète et de l'empreinte de branche de tools/train_ready.py (déplacées ici, une seule source).
Retrait : `ciblee` tombe avec D10 (`--branch`, dix trains verts sur conteneurs) ; le module reste tant que la preuve `conteneur` existe.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

HEX40 = re.compile(r"[0-9a-f]{40}")
FINGERPRINT = "pmzilla-run-all-ok"        # écrit par tests/run_all.sh (lancement complet) ; source du nom : tests/run_all.sh
BRANCH_FINGERPRINT = "pmzilla-run-branch-ok"   # écrit par `tests/run_all.sh --branch` ; source du nom : tests/run_all.sh
MAC_FINGERPRINT = "pmzilla-run-mac-ok"     # écrit par `tests/run_all.sh --mac` (D7) ; source du nom : tests/run_all.sh
PHASES = ("portable", "base", "e2e")        # source : ci/passage.sh (D2) ; les trois sont exigées
GIT_TIMEOUT = 30
_GIT_REMOVED = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_LITERAL_PATHSPECS", "GIT_GLOB_PATHSPECS",
                "GIT_NOGLOB_PATHSPECS", "GIT_ICASE_PATHSPECS")


class PreuveImpossible(Exception):
    """Le calcul ne peut pas aboutir (Git en échec, arbre mal formé) : l'appelant n'a pas de preuve."""


def _git(repo, *args):
    env = {k: v for k, v in os.environ.items() if k not in _GIT_REMOVED}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=GIT_TIMEOUT, env=env, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return r.returncode, r.stdout


def fingerprint_of(path):
    """L'arbre noté par le dernier runner complet réussi dans ce worktree (fichier lu par le crochet pre-push), ou None."""
    code, out = _git(path, "rev-parse", "--path-format=absolute", "--git-path", FINGERPRINT)
    if code != 0 or not out.strip():
        return None
    try:
        texte = Path(out.strip()).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return texte if HEX40.fullmatch(texte) else None


def branch_fingerprint_of(path):
    """(arbre, suites) de l'empreinte de branche (« <arbre><tab><suites séparées par des virgules> »), ou None quand le fichier manque ou est mal
    formé. Jamais l'empreinte ciblée par commit (pmzilla-run-targeted-ok : lue par aucune fonction de ce module)."""
    code, out = _git(path, "rev-parse", "--path-format=absolute", "--git-path", BRANCH_FINGERPRINT)
    if code != 0 or not out.strip():
        return None
    try:
        texte = Path(out.strip()).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    champs = texte.split("\t")
    if len(champs) != 2 or not HEX40.fullmatch(champs[0]):
        return None
    return champs[0], [s for s in champs[1].split(",") if s]


def preuves_path():
    """ci/preuves du dossier de données du lab (même source que tools/ci_local.sh : tools/lab_paths)."""
    import lab_paths
    return lab_paths.data_folder() / "ci" / "preuves"


def container_phases(arbre, fichier=None):
    """Les phases de la ligne de `ci/preuves` pour cet arbre (liste), ou None quand le fichier manque ou n'a pas de ligne de cet arbre.
    Ligne : <arbre><tab><clé d'image><tab><phases séparées par des virgules>. Une ligne mal formée est ignorée."""
    try:
        texte = (fichier or preuves_path()).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    trouvee = None
    for ligne in texte.splitlines():
        champs = ligne.split("\t")
        if len(champs) == 3 and champs[0] == arbre:
            trouvee = [p for p in champs[2].split(",") if p]
    return trouvee


def container_proven(arbre, fichier=None):
    """True quand la ligne de ci/preuves pour l'arbre porte EXACTEMENT portable,base,e2e dans cet ordre (D6) ; une autre liste n'est pas une preuve."""
    phases = container_phases(arbre, fichier)
    return phases is not None and tuple(phases) == PHASES


def mac_path(worktree=None):
    """pmzilla-run-mac-ok du dossier Git commun du worktree (du dossier courant sans worktree). PreuveImpossible quand Git ne répond pas."""
    code, out = _git(worktree or os.getcwd(), "rev-parse", "--path-format=absolute", "--git-common-dir")
    if code != 0 or not out.strip():
        raise PreuveImpossible("git")
    return Path(out.strip()) / MAC_FINGERPRINT


def mac_proven(arbre, worktree=None, fichier=None):
    """True quand pmzilla-run-mac-ok porte une ligne égale à l'arbre."""
    try:
        texte = (fichier or mac_path(worktree)).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return arbre in texte.split("\n")


def preuve(arbre, worktree=None, preuves=None, mac=None):
    """« complete », « conteneur », « ciblee » ou None, dans cet ordre (D8). `preuves` et `mac` : chemins des deux fichiers, pour les tests.
    PreuveImpossible quand le fichier du Mac doit être lu et que Git ne répond pas."""
    if not isinstance(arbre, str) or not HEX40.fullmatch(arbre):
        raise PreuveImpossible("arbre")
    if worktree is not None and fingerprint_of(worktree) == arbre:
        return "complete"
    if container_proven(arbre, preuves) and mac_proven(arbre, worktree, mac):
        return "conteneur"
    if worktree is not None:
        branche = branch_fingerprint_of(worktree)
        if branche is not None and branche[0] == arbre:
            return "ciblee"
    return None


INDEX_FILE_VARIABLE = "CI_LOCAL_PREUVES_INDEX"   # variable d'essai de tools/ci_local.sh (T2, R-20261104-7 P5 (ii)) ; source du nom : tools/ci_local.sh
SUITE_NAME = re.compile(r"[A-Za-z0-9_]+")        # source : tools/ci_local.sh (nom_suite_valide)
COMPLETE = "complet"                              # champ « suites » d'une ligne écrite par un passage complet ; source : tools/ci_local.sh


def preuves_index_path():
    """ci/preuves-index du dossier de données du lab (même source que tools/ci_local.sh), ou le fichier que nomme CI_LOCAL_PREUVES_INDEX (tests)."""
    nomme = os.environ.get(INDEX_FILE_VARIABLE)
    if nomme:
        return Path(nomme)
    import lab_paths
    return lab_paths.data_folder() / "ci" / "preuves-index"


def index_proven(arbre, suites=(), fichier=None):
    """True quand UNE ligne du fichier des preuves d'index porte cet arbre (tooling-proof-in-container, T2, D1) et couvre la demande : son champ
    « suites » est `complet`, ou contient toutes les suites demandées. Sans suite demandée, une ligne de l'arbre suffit. Ligne :
    <arbre><tab><clé d'image><tab><suites séparées par des virgules, ou complet>, sans champ de verdict (seule une exécution verte l'écrit). Une ligne mal
    formée est ignorée. Les lignes ne s'additionnent pas : une seule doit couvrir la demande. Ce n'est PAS une preuve de commit (preuve() ne la lit pas)."""
    try:
        texte = (fichier or preuves_index_path()).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    demande = set(suites)
    # Décision R-20261104-58 Q1 (a). Remplace : l'acceptation d'un champ qui contient complet. Retrait : permanent tant que complet désigne le mode complet de la preuve d'index.
    exige_complet = COMPLETE in demande   # le mode complet n'est prouvé que par une ligne « complet » exacte, jamais par une liste qui le nomme
    for ligne in texte.splitlines():
        champs = ligne.split("\t")
        if len(champs) != 3 or champs[0] != arbre:
            continue
        if champs[2] == COMPLETE:
            return True
        if not exige_complet and demande <= set(s for s in champs[2].split(",") if s):
            return True
    return False


def _main_index(argv):
    """`--index <arbre> [--suites a,b]` : « conteneur-index » et le code 0, ou « aucune » et le code 1 ; usage ou arbre mal formé : code 2."""
    usage = "preuve_arbre : usage : preuve_arbre.py --index <arbre> [--suites a,b]"
    if len(argv) not in (2, 4) or argv[0] != "--index" or not HEX40.fullmatch(argv[1]):
        print(usage, file=sys.stderr)
        return 2
    suites = ()
    if len(argv) == 4:
        if argv[2] != "--suites":
            print(usage, file=sys.stderr)
            return 2
        suites = tuple(s for s in argv[3].split(",") if s)
        if not all(SUITE_NAME.fullmatch(s) for s in suites):
            print(usage, file=sys.stderr)
            return 2
    try:
        trouvee = index_proven(argv[1], suites)
    except Exception:   # fermé : toute panne est un calcul impossible, jamais une preuve
        print("preuve_arbre : calcul impossible", file=sys.stderr)
        return 2
    if not trouvee:
        print("aucune")
        return 1
    print("conteneur-index")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    worktree = None
    if argv in (["--help"], ["-h"]):
        print("usage : preuve_arbre.py <arbre> [--worktree <chemin>] | --index <arbre> [--suites a,b]")
        return 0
    if "--index" in argv or "--suites" in argv:
        return _main_index(argv)
    if "--worktree" in argv:
        i = argv.index("--worktree")
        if i + 1 >= len(argv):
            print("preuve_arbre : usage : preuve_arbre.py <arbre> [--worktree <chemin>]", file=sys.stderr)
            return 2
        worktree = argv[i + 1]
        del argv[i:i + 2]
    if len(argv) != 1:
        print("preuve_arbre : usage : preuve_arbre.py <arbre> [--worktree <chemin>]", file=sys.stderr)
        return 2
    try:
        mot = preuve(argv[0], worktree)
    except PreuveImpossible as e:
        print(f"preuve_arbre : calcul impossible ({e})", file=sys.stderr)
        return 2
    except Exception:   # fermé : toute autre panne est un calcul impossible, jamais une preuve
        print("preuve_arbre : calcul impossible", file=sys.stderr)
        return 2
    if mot is None:
        print("aucune")
        return 1
    print(mot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
