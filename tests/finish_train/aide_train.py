"""
Aide des tests de tools/finish_train.sh (change finish-train-v1, groupe 2, conception D22) : un dépôt Git jetable avec un dépôt distant nu pour
« origin », un espace de travail sur main, un dossier d'exécution qui est un worktree détaché au sommet de main (il porte les copies du script et
de tous les modules qu'il source ou lance), des branches avec et sans worktree, de faux dossiers du lab, de fausses listes et les remplacements
de la conception D19 (passe Mac, ci_local, garde du matin, dossier du journal). Bibliothèque standard seulement, plus Git et le bash du système.
Aucun réseau, aucune base, aucun vrai dossier du lab.

Environnement des lancements : une LISTE BLANCHE (PATH, HOME, langue, dossier temporaire). Rien d'autre ne passe, donc le marqueur de session
d'une session Claude Code n'atteint jamais le script : ces tests jouent des mouvements de main dans des dépôts jetables que le crochet de session
refuserait.

Les faux (runner Mac, ci_local, garde du matin, run_worktree.sh, git espion, lsof, crochets) lisent leurs réglages dans des variables FAKE_* de
l'environnement du lancement, et journalisent leurs appels dans le dossier d'état (appels.log, git.log, env-runner.txt).
"""
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from dataclasses import dataclass
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
OUTILS = RACINE / "tools"
BASH = "/bin/bash" if os.access("/bin/bash", os.X_OK) else "bash"
SCRIPT = "tools/finish_train.sh"
PREFIXE = "finish_train : "

# les six phrases d'état de la bannière de fin (conception D24), mot pour mot
E1 = "rien n'est fait ; état des références non examiné"
E2 = "rien n'est fusionné"
E3 = "main local porte le train, rien n'est poussé ; relancer la même commande pour reprendre au push"
E4 = "train poussé ; relancer la même commande pour reprendre au nettoyage"
E5 = "main local a bougé hors du train testé, rien n'est poussé ; examiner main avant de relancer"
E6 = "références dans aucun état connu ; rien n'est touché"

# ce que le script source ou lance, copié à l'identique dans main du dépôt jetable (finish_train.sh seulement s'il existe : tant que le
# script n'est pas écrit, chaque test échoue sur son absence)
# finish_db_paths.txt : la liste des chemins de la base que le contrôle 14 du module lit (finish-single-b3-b6 D15), copiée à l'identique
COPIES = ("finish_train.sh", "finish_lock.sh", "finish_env.sh", "lab_paths.sh", "lab_paths.py", "morning_state.sh",
          "finish_checks.py", "finish_db_paths.txt", "finish_runner_paths.txt", "posture_eval_fingerprint.py", "range_scan.py", "commit_names_scan.py", "identifiants_personnels.py",
          "secret_scan.py", "secret_scan_exemples.txt", "sensitive_names.py", "hooks/pre-commit", "hooks/pre-push",
          "finish_lock.py", "hooks/reference-transaction", "finish_stability.sh",   # finish_stability.sh : module sourcé par le train (finish-single-b3-b6, D6)
          "finish_admission.sh", "train_ready.py", "train_ready_messages.py", "train_auto_messages.py", "messages.py",
          "preuve_arbre.py",   # preuve_arbre.py : appelé par le crochet pre-push à côté de lui (ci-local-runner, D8) ; sans lui le push du train n'a plus de preuve en test
          "train_record.py", "train_record_messages.py",   # autonomous-trains-merge (D4) : le piège de sortie du train écrit le journal des trains par ce module seul
          "train_auto.py", "pilot.py", "pilot_messages.py")   # autonomous-trains-merge (D7, D8) : « finish_checks.py policy » (--auto) importe train_auto, qui importe pilot
# finish_admission.sh : module sourcé par le train (finish-single-b3-b6, B4, D8) ; train_ready.py et ses trois imports (catalogues, messages.py) : le lecteur de la
# liste des branches prêtes (R-166) que fa_review_done appelle (D12), copiés à l'identique ; train_auto.py n'est jamais importé par read_list

CONSERVEES = ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "USER", "LOGNAME", "TMPDIR")
RESERVEES = ("PMZILLA_NO_EVALS", "PMZILLA_SKIP_GREEN_CHECK", "FINISH_BRANCH_TESTED_TOKEN", "FINISH_BRANCH_FORCE_RUN",
             "FINISH_WORKTREE_ALLOW_SKIP", "FINISH_WORKTREE_CI", "FINISH_WORKTREE_CI_VERDICTS")

NOM_FICTIF = "Vexillonia"          # nom sensible fictif (liste fictive)
IDENTIFIANT = "zorglub-test"       # identifiant personnel fictif
CORPS = "aB3dE5gH7jK9mN2pQ4rS6tU8vW1xY0zC"


def jeton():
    """Un faux jeton de forme reconnue par le contrôle des secrets, assemblé ici pour ne jamais figurer en clair dans un fichier suivi."""
    return "gh" + "p_" + CORPS + "AbCd"


LISTE_JEU = "# liste fictive des fichiers évalués\nCLAUDE.md\n.claude/skills/pmzilla-*\ntests/postures/vocabulaire.yaml\ntests/postures/memoire\n"
LISTE_PROTEGEE = ("# liste fictive de l'outillage protégé\ntools/hooks/\ntools/finish_branch.sh\ntools/finish_train.sh\n"
                  "tools/finish_protected.txt\ntests/run_all.sh\n")
# liste fictive des chemins d'interface (finish-e2e-proof-shared, D1) : une seule entrée, que les autres tests ne touchent jamais, pour que le contrôle 16
# du module ne s'applique qu'aux tests de la passe de bout en bout ; une liste vide serait « illisible » (refusé, jamais sans objet)
LISTE_E2E = "# liste fictive des chemins d'interface\ninterface-factice/\n"
CHEMIN_INTERFACE = "interface-factice/page.txt"   # un fichier que la liste fictive couvre
IGNORES = ".pmzilla/\n*.sentinelle\n__pycache__/\n.DS_Store\nnode_modules/\nmothra/front/dist/\nautre/dist/\n"

RUN_ALL_BIDON = """#!/bin/bash
# runner du dépôt jetable : écrit l'empreinte de l'arbre de HEAD, comme le vrai runner après un passage vert
git rev-parse 'HEAD^{tree}' > "$(git rev-parse --path-format=absolute --git-path pmzilla-run-all-ok)"
git rev-parse 'HEAD^{tree}' >> "$(git rev-parse --path-format=absolute --git-common-dir)/pmzilla-run-mac-ok"   # la passe Mac (--mac) écrit aussi sa ligne (D7), comme le faux runner
echo "TOTAL : 1 tests dans 1 suites · tous réussis · durée totale 1 s"
"""

# --- les faux ------------------------------------------------------------------------------------------------------------------------
FAUX_RUNNER = """#!/bin/bash
ETAT="@ETAT@"
echo "runner pwd=$(pwd -P) args=[$*] stdin=[$(cat)]" >> "$ETAT/appels.log"
env | sort > "$ETAT/env-runner.txt"
git rev-parse HEAD > "$ETAT/runner-head.txt"
git -C "@CONTENU@" for-each-ref --format='%(refname)' refs/heads > "$ETAT/runner-refs.txt"
ecrit_fp() { git rev-parse 'HEAD^{tree}' > "$(git rev-parse --path-format=absolute --git-path pmzilla-run-all-ok)"; git rev-parse 'HEAD^{tree}' >> "$(git rev-parse --path-format=absolute --git-common-dir)/pmzilla-run-mac-ok"; }   # la passe Mac (--mac, D7) écrit aussi sa ligne ; l'empreinte complète reste écrite (Q218 a)
[ -z "${FAKE_RUNNER_IGNORE_DANS:-}" ] || { mkdir -p "$FAKE_RUNNER_IGNORE_DANS" && echo x > "$FAKE_RUNNER_IGNORE_DANS/ecrit-apres.sentinelle"; }
[ -z "${FAKE_RUNNER_PROCESSUS_DANS:-}" ] || ( cd "$FAKE_RUNNER_PROCESSUS_DANS" && { sleep 600 >/dev/null 2>&1 </dev/null & echo $! > "$ETAT/pid-sleep"; } )
[ -z "${FAKE_RUNNER_PROCESSUS_ICI:-}" ] || { sleep 600 >/dev/null 2>&1 </dev/null & echo $! > "$ETAT/pid-sleep"; }   # un vrai enfant laissé dans le dossier courant du runner (le worktree d'intégration)
[ -z "${FAKE_RUNNER_BRANCHE_DANS:-}" ] || git -C "$FAKE_RUNNER_BRANCHE_DANS" commit -q --allow-empty -m "pendant le runner"
[ -z "${FAKE_RUNNER_MAIN:-}" ] || git -C "@CONTENU@" commit -q --allow-empty -m "commit étranger pendant le runner"
[ -z "${FAKE_RUNNER_LSOF_MODE:-}" ] || echo "$FAKE_RUNNER_LSOF_MODE" > "$ETAT/lsof-mode"
[ -z "${FAKE_RUNNER_CHECK_IGNORE_CODE:-}" ] || echo "$FAKE_RUNNER_CHECK_IGNORE_CODE" > "$ETAT/check-ignore-code"
[ -z "${FAKE_RUNNER_ECRIT_ESPACE:-}" ] || { mkdir -p "$(dirname "@CONTENU@/$FAKE_RUNNER_ECRIT_ESPACE")"; echo x > "@CONTENU@/$FAKE_RUNNER_ECRIT_ESPACE"; }
[ -z "${FAKE_RUNNER_JETON_AUTRE:-}" ] || echo "jeton-d-un-autre" > "$(git rev-parse --path-format=absolute --git-common-dir)/pmzilla-fin-en-cours/jeton"
[ -z "${FAKE_RUNNER_ORIGIN_CASSE:-}" ] || git -C "@CONTENU@" remote set-url origin "$FAKE_RUNNER_ORIGIN_CASSE"
[ -z "${FAKE_RUNNER_ORIGIN:-}" ] || { git -C "$FAKE_RUNNER_ORIGIN" commit -q --allow-empty -m "pousse ailleurs" && PMZILLA_SKIP_GREEN_CHECK=1 git -C "$FAKE_RUNNER_ORIGIN" push -q origin main; }
case "${FAKE_RUNNER_MODE:-vert}" in
  vert) ecrit_fp; echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  rouge) echo "TOTAL : 3 tests dans 2 suites · 2 suite(s) en échec : suite_a suite_b · durée totale 1 s"; exit 1 ;;
  code4) echo "gel : une fin de branche est en cours"; exit 4 ;;
  code6) echo "lanceur : refusé en session"; exit 6 ;;
  code1_sans_total) echo "échec sans ligne de total"; exit 1 ;;
  modifie_suivi) ecrit_fp; echo autre >> README.md; echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  modifie_non_suivi) ecrit_fp; echo x > fichier-non-suivi.txt; echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  reecrit_meme_contenu) ecrit_fp; contenu=$(cat README.md); printf '%s\\n' "$contenu" > README.md   # seul le ctime change : git status reste propre
    echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  ignores_crees) ecrit_fp; mkdir -p tools/__pycache__ mothra/front/dist; echo x > tools/__pycache__/o.pyc; echo x > mothra/front/dist/index.html   # ignorés par Git : le train reste concluant
    echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  ignores_supprimes) mkdir -p tools/__pycache__; echo x > tools/__pycache__/o.pyc; rm -rf tools/__pycache__; ecrit_fp
    echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  passager_non_ignore) ecrit_fp; echo x > passager.txt; rm passager.txt   # non ignoré, créé puis supprimé : la liste est identique, la date a changé
    echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  limite_passager) ecrit_fp; echo x > passager.txt; mkdir node_modules; rm passager.txt   # limite connue : le passager est caché par l'ajout ignoré du même dossier
    echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  dossier_vide_cree) ecrit_fp; mkdir tools/vide   # ajout non ignoré (dossier vide : git status ne le voit pas, la liste des entrées oui)
    echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  dossier_tout_ignore_cree) ecrit_fp; mkdir -p tools/neuf/__pycache__; echo x > tools/neuf/__pycache__/o.pyc   # le dossier « neuf » n'est pas ignoré, seul son contenu l'est
    echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  ls_echoue) ecrit_fp; chmod 311 db   # traversable mais non listable : ls échoue, git status reste propre
    echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  dossier_renomme_remis) ecrit_fp; mv db db.x; mv db.x db   # même dossier, même inode : seule la date le trahit
    echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  renomme_suivi) ecrit_fp; mv tools/outil.sh tools/outil-renomme.sh; mv tools/outil-renomme.sh tools/outil.sh   # revenu à l'identique : seul le ctime du fichier le trahit
    echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  renomme_suivi_definitif) ecrit_fp; mv tools/outil.sh tools/outil-renomme.sh
    echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  dossier_recree) ecrit_fp; mkdir openspec.n; mv openspec/changes openspec.n/; rmdir openspec; mv openspec.n openspec   # mêmes fichiers, même contenu, aucune date de fichier changée : seul le dossier « openspec » est un autre (autre inode)
    echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  code7) echo "lancer : cd mothra/serveur && npm ci"; echo "dépendances npm à mettre en conformité"; exit 7 ;;
  pipe_enfant) yes | head -n 1 > /dev/null; echo "${PIPESTATUS[0]}" > "$ETAT/yes-status"
    ecrit_fp; echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  pipe_ferme) : > "$ETAT/runner-demarre"; while [ ! -f "$ETAT/pipe-ferme" ]; do sleep 0.05; done
    ecrit_fp; echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  sans_empreinte) echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  autre_empreinte) echo 4b825dc642cb6eb9a060e54bf8d69288fbee4904 > "$(git rev-parse --path-format=absolute --git-path pmzilla-run-all-ok)"
    echo 4b825dc642cb6eb9a060e54bf8d69288fbee4904 >> "$(git rev-parse --path-format=absolute --git-common-dir)/pmzilla-run-mac-ok"   # la passe Mac écrit une ligne d'un AUTRE arbre (R-20261101-114, revue Opus point 2)
    echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
  dort) : > "$ETAT/runner-demarre"; i=0; while [ ! -f "$ETAT/reveil" ]; do [ "$i" -lt 2400 ] || { echo "faux runner : borne de sécurité de 120 secondes atteinte, reveil jamais écrit par le test"; exit 97; }; i=$((i+1)); sleep 0.05; done; ecrit_fp; echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"; exit 0 ;;
esac
"""

# Le faux ci_local (ci-local-runner, tranche 3, R-20261101-114 et 115) : remplace `bash tools/ci_local.sh run` (FINISH_TRAIN_CI) ; le rejeu ajoute
# `--rejeu ...` aux arguments. Il journalise (appels.log : « ci pwd=… args=[…] stdin=[…] jeton=… dbvars=[…] » ; ci-appels : les arguments, une ligne par appel),
# écrit son ENVIRONNEMENT ($ETAT/ci-env, ou $ETAT/ci-env-rejeu pour un rejeu) et imprime :
#   - FAUX_CI_LIGNES si posée, sinon les lignes d'un passage vert (fichier ci-vert.txt, voir lignes_ci) ; code de sortie FAUX_CI_CODE (0 par défaut) ;
#   - au rejeu : FAUX_CI_REJEU_LIGNES (sinon une ligne TOTAL verte), code FAUX_CI_REJEU_CODE (0 par défaut) ; ni preuve ni autre écriture.
# Passage vert par défaut : écrit aussi la ligne « <arbre>\tcle-factice\tportable,base,e2e » dans $PMZILLA_LAB_DATA/ci/preuves (sauf FAUX_CI_SANS_PREUVE).
# FAUX_CI_SALE : laisse un fichier non suivi dans le dossier courant ; FAUX_CI_IGNORES_CREES : laisse des fichiers ignorés.
FAUX_CI = """#!/bin/bash
ETAT="@ETAT@"
echo "ci pwd=$(pwd -P) args=[$*] stdin=[$(cat)] jeton=${FINISH_LOCK_TOKEN:+present} dbvars=[$(compgen -e DBTEST_ | tr '\\n' ' ')]" >> "$ETAT/appels.log"
echo "$*" >> "$ETAT/ci-appels"
case " $* " in *" --rejeu "*) rejeu=1 ;; *) rejeu= ;; esac
if [ -n "$rejeu" ]; then env | sort > "$ETAT/ci-env-rejeu"; else env | sort > "$ETAT/ci-env"; fi
[ -z "${FAUX_CI_IGNORES_CREES:-}" ] || { mkdir -p tools/__pycache__; echo x > tools/__pycache__/ci.pyc; }
[ -z "${FAUX_CI_SALE:-}" ] || echo x > sale-avant-releve.txt
if [ -n "$rejeu" ]; then
  if [ -n "${FAUX_CI_REJEU_LIGNES:-}" ]; then printf '%s\\n' "$FAUX_CI_REJEU_LIGNES"; else echo "TOTAL : 1 tests dans 1 suites · tous réussis · durée totale 1 s"; fi
  # la ligne que ci_local écrit pour un rejeu rouge : le code 1 sans elle n'est pas « suite rouge reproduite » (revue croisée tranche 2)
  if [ "${FAUX_CI_REJEU_CODE:-0}" = 1 ] && [ -z "${FAUX_CI_REJEU_SANS_LIGNE:-}" ]; then echo "ci_local : rejeu rouge (arbre aaaaaaaaaaaa, image bbbbbbbbbbbb) : suites"; fi
  exit "${FAUX_CI_REJEU_CODE:-0}"
fi
if [ -n "${FAUX_CI_LIGNES:-}" ]; then printf '%s\\n' "$FAUX_CI_LIGNES"; else cat "@VERT@"; fi
code=${FAUX_CI_CODE:-0}
if [ -z "${FAUX_CI_LIGNES:-}" ] && [ "$code" = 0 ] && [ -z "${FAUX_CI_SANS_PREUVE:-}" ] && [ -n "${PMZILLA_LAB_DATA:-}" ]; then
  mkdir -p "$PMZILLA_LAB_DATA/ci"
  printf '%s\\t%s\\t%s\\n' "$(git rev-parse 'HEAD^{tree}')" "cle-factice" "${FAUX_CI_PREUVE_PHASES:-portable,base,e2e}" >> "$PMZILLA_LAB_DATA/ci/preuves"
fi
exit "$code"
"""


def phase_ci(nom: str, verdict: str = "verte", suites: str = "") -> str:
    """Une ligne de phase, au format de ci/passage.sh (que ci_local imprime telle quelle) : verdict « verte » ou « rouge »."""
    if verdict == "verte":
        return f"ci_passage : phase {nom} : verte · 1 s"
    return f"ci_passage : phase {nom} : rouge · 1 s" + (f" : {suites}" if suites else "")


def lignes_ci(*phases: str, suites: str = "") -> str:
    """Les lignes d'un passage : les lignes de phase données (phase_ci), puis la ligne TOTAL et la dernière ligne au format de ci_local. Rouge si une
    des phases est rouge. Exemple : lignes_ci(phase_ci("portable"), phase_ci("base", "rouge", "suite_a"), suites="suite_a")."""
    rouge = any(": rouge" in p for p in phases)
    noms = ",".join(p.split("phase ")[1].split(" :")[0] for p in phases if ": verte" in p)
    if rouge:
        total = f"TOTAL : 3 tests dans 2 suites · {len(suites.split()) or 1} suite(s) en échec : {suites or 'suite_a'} · durée totale 1 s"
        fin = f"ci_local : verdict rouge (arbre aaaaaaaaaaaa, image bbbbbbbbbbbb{', phases ' + noms if noms else ''}) : {suites or 'suite_a'}"
    else:
        total = "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"
        fin = f"ci_local : verdict vert (arbre aaaaaaaaaaaa, image bbbbbbbbbbbb, phases {noms}, 3 suites, 0 suites Mac non lancées)"
    return "\n".join([*phases, total, fin])


CI_LIGNES_VERT = lignes_ci(phase_ci("portable"), phase_ci("base"), phase_ci("e2e"))

FAUX_MATIN = """#!/bin/bash
ETAT="@ETAT@"
n=$(cat "$ETAT/matin.n" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$ETAT/matin.n"
echo "garde-du-matin appel $n" >> "$ETAT/appels.log"
case "${FAKE_MORNING_MODE:-permet}" in
  permet) echo "morning_state : autorisé (faux garde-fou)"; exit 0 ;;
  refuse) echo "morning_state : refusé (faux garde-fou)"; exit 1 ;;
  refuse_avec_avertissement) echo "morning_state : refusé (faux garde-fou)"; echo "morning_state : avertissement : deuxième ligne (faux garde-fou)"; exit 1 ;;
  permet_avertit) echo "morning_state : autorisé, ni veille ni sauvegarde en cours (faux garde-fou)"; echo "morning_state : avertissement : veille du jour absente (faux garde-fou)"; exit 0 ;;   # R-20261102-3, -5 : avertissement seul
  refuse_des_le_second) if [ "$n" -ge 2 ]; then echo "morning_state : refusé (faux garde-fou)"; exit 1; fi; echo "morning_state : autorisé (faux garde-fou)"; exit 0 ;;
  dort) : > "$ETAT/matin-demarre"; i=0; while [ ! -f "$ETAT/reveil" ]; do [ "$i" -lt 2400 ] || { echo "fausse garde du matin : borne de sécurité de 120 secondes atteinte, reveil jamais écrit par le test"; exit 97; }; i=$((i+1)); sleep 0.05; done; exit 0 ;;
esac
"""

FAUX_RUN_WORKTREE = """#!/bin/bash
ETAT="@ETAT@"
echo "update appelé : $*" >> "$ETAT/appels.log"
dossier=$(cd "$(dirname "$0")/.." && pwd)
case "${FAKE_RUN_UPDATE:-ok}" in
  ok) git -C "$dossier" checkout -q --detach main; echo "### update" >> "$ETAT/git.log"; exit 0 ;;
  absent) echo "### update" >> "$ETAT/git.log"; echo "run_worktree : dossier d'exécution absent"; exit 4 ;;
  echec) echo "### update" >> "$ETAT/git.log"; echo "run_worktree : modifications locales"; exit 7 ;;
  remplace) git -C "$dossier" checkout -q --detach main; printf '#!/bin/bash\\necho SCRIPT-REMPLACE\\nexit 99\\n' > "$dossier/tools/finish_train.sh"
    echo "### update" >> "$ETAT/git.log"; exit 0 ;;
esac
"""

FAUX_GIT = """#!/bin/sh
echo "$*" >> "@ETAT@/git.log"
case " $* " in
  *" merge-tree "*) [ -z "${FAKE_MERGE_TREE_CODE:-}" ] || exit "$FAKE_MERGE_TREE_CODE"
    if [ -n "${FAKE_MERGE_TREE_RC_APRES:-}" ]; then "@GIT@" "$@"; exit "$FAKE_MERGE_TREE_RC_APRES"; fi ;;   # la vraie sortie, puis un autre code
  *" worktree add "*) [ -z "${FAKE_WORKTREE_ADD_CODE:-}" ] || exit "$FAKE_WORKTREE_ADD_CODE"
    if [ -n "${FAKE_WORKTREE_ADD_DB_ILLISIBLE:-}" ]; then   # le worktree d'intégration est créé pour de vrai, puis « db » devient non listable AVANT le premier relevé (revue Opus point 7)
      "@GIT@" "$@" || exit $?
      for a in "$@"; do avant_dernier=$dernier; dernier=$a; done
      chmod 311 "$avant_dernier/db"
      exit 0
    fi
    if [ -n "${FAKE_WORKTREE_ADD_SALE:-}" ]; then   # un fichier non suivi laissé dans le worktree d'intégration AVANT le premier relevé (D4 : « sale juste avant l'instantané »)
      "@GIT@" "$@" || exit $?
      for a in "$@"; do avant_dernier=$dernier; dernier=$a; done
      echo x > "$avant_dernier/sale-avant-releve.txt"
      exit 0
    fi ;;
  *" ls-tree "*"mothra/package-lock.json"*) [ -z "${FAKE_LS_TREE_VERROU_CODE:-}" ] || exit "$FAKE_LS_TREE_VERROU_CODE" ;;
  *" ls-tree "*"mothra/.node-version"*) [ -z "${FAKE_LS_TREE_NODE_VERSION_CODE:-}" ] || exit "$FAKE_LS_TREE_NODE_VERSION_CODE" ;;
  *" show "*"mothra/.node-version"*) [ -z "${FAKE_SHOW_NODE_VERSION_CODE:-}" ] || exit "$FAKE_SHOW_NODE_VERSION_CODE" ;;
  *" ls-files "*) # avant le départ du runner (« env-runner.txt » pas encore écrit) : échec seulement dans le worktree d'intégration
    if [ -n "${FAKE_LS_FILES_AVANT_RUNNER:-}" ] && [ ! -f "@ETAT@/env-runner.txt" ]; then
      case " $* " in *"/wt-train-"*) exit 128 ;; esac
    fi ;;
  *" check-ignore "*) [ ! -f "@ETAT@/check-ignore-code" ] || exit "$(cat "@ETAT@/check-ignore-code")" ;;   # posé par le runner factice : échec de l'outil après le premier relevé
  *" branch -d "*) [ -z "${FAKE_MAIN_APRES_BRANCH_D:-}" ] || "@GIT@" -C "@CONTENU@" commit -q --allow-empty -m "main déplacé pendant le nettoyage" ;;
esac
exec "@GIT@" "$@"
"""

FAUX_LSOF = """#!/bin/sh
ETAT="@ETAT@"
if [ -f "$ETAT/lsof-arme" ]; then rm -f "$ETAT/lsof-arme"; : > "$ETAT/lsof-demarre"; i=0; while [ ! -f "$ETAT/reveil" ]; do [ "$i" -lt 2400 ] || { echo "faux lsof : borne de sécurité de 120 secondes atteinte, reveil jamais écrit par le test"; exit 97; }; i=$((i+1)); sleep 0.05; done; fi
mode=${FAKE_LSOF_MODE:-reel}
[ ! -f "$ETAT/lsof-mode" ] || mode=$(cat "$ETAT/lsof-mode")   # posé en cours de route (par le runner factice ou le dépôt distant factice)
case "$mode" in
  casse) exit 1 ;;
  sans_moi) printf 'p1\\nn/\\n'; exit 0 ;;   # une liste qui ne montre pas le script lui-même
esac
PATH=${PATH#*:}
PATH=${PATH#*:}
exec lsof "$@"
"""

CROCHET_PRE_PUSH = """#!/bin/sh
ETAT="@ETAT@"
echo "pre-push appelé" >> "$ETAT/appels.log"
if [ -f "$ETAT/prepush-dort" ]; then : > "$ETAT/prepush-demarre"; i=0; while [ ! -f "$ETAT/reveil" ]; do [ "$i" -lt 2400 ] || { echo "faux pre-push : borne de sécurité de 120 secondes atteinte, reveil jamais écrit par le test"; exit 97; }; i=$((i+1)); sleep 0.05; done; fi
exec "@HOOK@" "$@"
"""

CROCHET_REFERENCE_TRANSACTION = """#!/bin/sh
exec "@HOOK_RT@" "$@"
"""

CROCHET_POST_MERGE = """#!/bin/sh
ETAT="@ETAT@"
cat "$(git rev-parse --git-path pmzilla-run-all-ok)" > "$ETAT/empreinte-a-l-avance-rapide.txt" 2>/dev/null
exit 0
"""

CROCHET_PRE_RECEIVE = """#!/bin/sh
ETAT="@ETAT@"
if [ -f "$ETAT/push-refuse" ]; then echo "refusé par le faux dépôt distant" >&2; exit 1; fi
: > "$ETAT/push-passe"
[ ! -f "$ETAT/lsof-arme-sur-push" ] || : > "$ETAT/lsof-arme"
[ ! -f "$ETAT/lsof-mode-apres-push" ] || cp "$ETAT/lsof-mode-apres-push" "$ETAT/lsof-mode"
exit 0
"""

PREPUSH_RUNNER = """#!/bin/bash
echo "prepush-runner" >> "@ETAT@/appels.log"
exit 1
"""


@dataclass
class Resultat:
    code: int
    sortie: str
    erreur: str

    @property
    def texte(self) -> str:
        return self.sortie + self.erreur


def _signaux_par_defaut():
    """Sous le lanceur de tests (tâche de fond), SIGINT et SIGHUP sont ignorés à l'héritage : le script d'un test de signal les reprend par défaut,
    comme dans un Terminal, sinon bash ne peut plus les piéger."""
    for sig in (signal.SIGINT, signal.SIGHUP, signal.SIGTERM):
        signal.signal(sig, signal.SIG_DFL)


def conserve() -> dict:
    return {k: os.environ[k] for k in CONSERVEES if k in os.environ}


def paris() -> str:
    """L'heure de Paris, au format de la bannière, par la commande date (le fuseau du processus ne compte pas)."""
    env = conserve()
    env["TZ"] = "Europe/Paris"
    return subprocess.run(["date", "+%Y-%m-%d %H:%M:%S"], env=env, capture_output=True, text=True).stdout.strip()


def secondes(horodatage: str) -> int:
    """Secondes d'un « AAAA-MM-JJ HH:MM:SS » lu comme une heure sans fuseau (seules les différences comptent)."""
    import calendar
    import datetime
    d = datetime.datetime.strptime(horodatage, "%Y-%m-%d %H:%M:%S")
    return calendar.timegm(d.timetuple())


class Train:
    """Un dépôt de travail jetable : lab/travail (main), lab/run (détaché au sommet de main), lab/worktrees, lab/data, distant.git."""

    def __init__(self, dossier: Path):
        self.dossier = Path(dossier).resolve()
        self.lab = self.dossier / "lab"
        self.contenu = self.lab / "travail"
        self.run = self.lab / "run"
        self.worktrees = self.lab / "worktrees"
        self.data = self.lab / "data"
        self.distant = self.dossier / "distant.git"
        self.logs = self.dossier / "logs"
        self.sans_substitution = False   # vrai : ni FINISH_TRAIN_CI ni FINISH_TRAIN_RUNNER (les faux sont tools/ci_local.sh de l'arbre d'exécution et tests/run_all.sh)
        self.fakes = self.dossier / "fakes"
        self.etat = self.fakes / "etat"
        self.bin = self.fakes / "bin"
        self.bin_lsof = self.fakes / "bin-lsof"
        self.crochets = self.fakes / "hooks"
        self.autre = self.dossier / "autre"
        self.dernier = None
        self.gitconfig = self.dossier / "gitconfig"
        self.noms = self.dossier / "noms-fictifs.txt"
        self.git_reel = shutil.which("git", path=os.environ.get("PATH")) or "git"
        for d in (self.lab, self.worktrees, self.data, self.logs, self.fakes, self.etat, self.bin, self.bin_lsof, self.crochets):
            d.mkdir(parents=True, exist_ok=True)
        self.noms.write_text(NOM_FICTIF + "\n", encoding="utf-8")
        self.ecrire_gitconfig(identite=True)
        self.env_installation = {**conserve(), "GIT_CONFIG_GLOBAL": str(self.gitconfig), "GIT_CONFIG_SYSTEM": "/dev/null",
                                 "GIT_TERMINAL_PROMPT": "0", "PMZILLA_SKIP_GREEN_CHECK": "1",
                                 "PMZILLA_LAB_SENSITIVE_NAMES": str(self.noms), "PMZILLA_LAB_WORKSPACE": str(self.contenu)}
        self.git("init", "-q", "--bare", str(self.distant), cwd=self.dossier)
        self.git("init", "-q", str(self.contenu), cwd=self.dossier)
        self.git("remote", "add", "origin", str(self.distant))
        (self.contenu / ".pmzilla").mkdir()
        (self.contenu / ".pmzilla" / "identifiants.txt").write_text(IDENTIFIANT + "\n", encoding="utf-8")
        fichiers = {
            "README.md": "base\n", "tools/outil.sh": "base\n", "CLAUDE.md": "c\n", ".claude/skills/pmzilla-x/SKILL.md": "s\n",
            "tests/postures/vocabulaire.yaml": "v\n", "tests/postures/memoire/m.md": "m\n", "tests/postures/fichiers-evalues.txt": LISTE_JEU,
            "tools/finish_protected.txt": LISTE_PROTEGEE, "tools/finish_e2e_paths.txt": LISTE_E2E, "tests/run_all.sh": RUN_ALL_BIDON, "openspec/changes/archive/.gitkeep": "a\n",
            "openspec/changes/autre/p.md": "autre\n", "db/001.sql": "SELECT 1;\n", "tools/db_x.py": "x = 1\n", ".gitignore": IGNORES,
            "tools/run_worktree.sh": self.remplir(FAUX_RUN_WORKTREE),
            "tools/ci_local.sh": f'#!/bin/bash\nexec bash "{self.fakes / "faux-ci"}" "$@"\n',   # le faux ci_local de l'arbre d'exécution (--auto, R-20261106-57) : délègue au faux commun
        }
        for nom, contenu in fichiers.items():
            self.ecrire(nom, contenu)
        for nom in COPIES:
            if (OUTILS / nom).exists():
                self.copier(OUTILS / nom, f"tools/{nom}")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "initial")
        self.git("push", "-q", "origin", "main")
        self.git("worktree", "add", "-q", "--detach", str(self.run), "main")
        self.installer_les_faux()

    # --- installation des faux ------------------------------------------------------------------------------------------------------
    def remplir(self, texte: str) -> str:
        return (texte.replace("@ETAT@", str(self.etat)).replace("@CONTENU@", str(self.contenu)).replace("@GIT@", self.git_reel)
                .replace("@HOOK@", str(self.contenu / "tools" / "hooks" / "pre-push"))
                .replace("@HOOK_RT@", str(self.contenu / "tools" / "hooks" / "reference-transaction")))

    def poser(self, chemin: Path, texte: str, executable=True):
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(self.remplir(texte), encoding="utf-8")
        if executable:
            chemin.chmod(0o755)
        return chemin

    def installer_les_faux(self):
        self.runner = self.poser(self.fakes / "runner.sh", FAUX_RUNNER)
        self.ci_vert = self.fakes / "ci-vert.txt"
        self.ci_vert.write_text(CI_LIGNES_VERT + "\n", encoding="utf-8")
        self.ci = self.poser(self.fakes / "faux-ci", FAUX_CI.replace("@VERT@", str(self.ci_vert)))
        self.matin = self.poser(self.fakes / "matin.sh", FAUX_MATIN)
        self.prepush_runner = self.poser(self.fakes / "prepush_runner.sh", PREPUSH_RUNNER)
        self.poser(self.bin / "git", FAUX_GIT)
        self.poser(self.bin_lsof / "lsof", FAUX_LSOF)
        self.poser(self.crochets / "pre-push", CROCHET_PRE_PUSH)
        self.poser(self.crochets / "reference-transaction", CROCHET_REFERENCE_TRANSACTION)   # le vrai crochet (u13), lu dans main du dépôt jetable
        self.poser(self.crochets / "post-merge", CROCHET_POST_MERGE)
        self.poser(self.crochets / "pre-receive", CROCHET_PRE_RECEIVE)   # core.hooksPath est global : le dépôt nu lit ce dossier aussi
        self.ecrire_gitconfig(identite=True, crochets=True)

    def ecrire_gitconfig(self, identite: bool, crochets: bool = False):
        texte = "[init]\n\tdefaultBranch = main\n"
        if identite:
            texte += "[user]\n\temail = t@example.org\n\tname = test\n"
        if crochets:
            texte += f"[core]\n\thooksPath = {self.crochets}\n"
        self.gitconfig.write_text(texte, encoding="utf-8")

    def sans_identite(self):
        self.ecrire_gitconfig(identite=False, crochets=True)

    # --- Git ---------------------------------------------------------------------------------------------------------------------------
    def git(self, *args, cwd=None, verifie=True, env=None):
        fait = subprocess.run([self.git_reel, *args], cwd=cwd or self.contenu, env=env or self.env_installation, capture_output=True, text=True)
        if verifie and fait.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} : {fait.stderr}")
        return fait.stdout.strip()

    def ecrire(self, chemin: str, contenu: str, racine: Path = None):
        fichier = (racine or self.contenu) / chemin
        fichier.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(contenu, bytes):
            fichier.write_bytes(contenu)
        else:
            fichier.write_text(contenu, encoding="utf-8")

    def copier(self, source: Path, chemin: str):
        fichier = self.contenu / chemin
        fichier.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, fichier)

    def valider(self, racine: Path, fichiers: dict, message: str) -> str:
        for chemin, contenu in fichiers.items():
            if contenu is None:
                (racine / chemin).unlink()
            else:
                self.ecrire(chemin, contenu, racine)
        self.git("add", "-A", cwd=racine)
        self.git("commit", "-q", "--allow-empty", "-m", message, cwd=racine)
        return self.git("rev-parse", "HEAD", cwd=racine)

    def dossier_worktree(self, nom: str) -> Path:
        return self.worktrees / ("wt-" + nom.replace("/", "-"))

    def branche(self, nom: str, fichiers: dict = None, worktree: bool = True, suite=(), depuis: str = "main") -> str:
        """Crée la branche depuis `depuis`, y commite `fichiers` puis chaque dictionnaire de `suite` ; garde ou retire son worktree."""
        chemin = self.dossier_worktree(nom)
        self.git("worktree", "add", "-q", "-b", nom, str(chemin), depuis)
        if fichiers is None:
            fichiers = {f"tools/{nom.replace('/', '_')}.sh": nom + "\n"}
        sommet = self.valider(chemin, fichiers, f"travail de {nom}")
        for k, plus in enumerate(suite):
            sommet = self.valider(chemin, plus, f"suite {k + 1} de {nom}")
        if not worktree:
            self.git("worktree", "remove", "--force", str(chemin))
        return sommet

    def branche_orpheline(self, nom: str):
        temp = self.dossier / "orphelin"
        self.git("worktree", "add", "-q", "--detach", str(temp), "main")
        self.git("checkout", "-q", "--orphan", nom, cwd=temp)
        self.git("rm", "-rq", "--cached", ".", cwd=temp)
        shutil.rmtree(temp / "tools", ignore_errors=True)
        self.valider(temp, {"tools/orphelin.sh": "o\n"}, "orphelin")
        self.git("worktree", "remove", "--force", str(temp))

    def commit_main(self, fichiers: dict, message: str = "travail sur main", pousser: bool = False) -> str:
        sommet = self.valider(self.contenu, fichiers, message)
        if pousser:
            self.git("push", "-q", "origin", "main")
        return sommet

    def mettre_a_jour_run(self):
        self.git("checkout", "-q", "--detach", "main", cwd=self.run)

    def casser_le_module(self, nom: str, contenu: str):
        """Remplace un fichier de tools/ dans main (poussé), puis met le dossier d'exécution à jour."""
        self.commit_main({f"tools/{nom}": contenu}, f"casse {nom}", pousser=True)
        self.mettre_a_jour_run()

    def controle_14_casse(self):
        """Le contrôle 14 sur un arbre sort 4 ; les autres sous-commandes de finish_checks.py restent celles du vrai module."""
        reel = (OUTILS / "finish_checks.py").read_text(encoding="utf-8")
        enveloppe = ("import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parent))\n"
                     "if sys.argv[1:2] == ['tree']:\n    print('finish_checks : calcul impossible (faux)')\n    sys.exit(4)\n"
                     "import finish_checks_reel\nsys.exit(finish_checks_reel.main())\n")
        self.commit_main({"tools/finish_checks_reel.py": reel, "tools/finish_checks.py": enveloppe}, "enveloppe finish_checks", pousser=True)
        self.mettre_a_jour_run()

    @property
    def ligne(self) -> str:
        """La ligne de relance que le script écrit : le dossier d'exécution des dossiers du lab, « ~ » quand il est sous le dossier personnel."""
        run = str(self.run)
        home = os.environ.get("HOME", "")
        if home and run.startswith(home + "/"):
            run = "~/" + run[len(home) + 1:]
        return f"bash {run}/tools/finish_train.sh"

    @property
    def usage(self) -> str:
        return f"usage : {self.ligne} [--essai] <branche> [<branche> …] (1 à 6 branches, chacune une fois)"

    def detacher_le_dossier_d_execution(self, rev: str):
        self.git("checkout", "-q", "--detach", rev, cwd=self.run)

    def commit_sans_lien(self) -> str:
        """Un commit sans parent, de l'arbre de main : le dossier d'exécution détaché dessus garde les mêmes fichiers, sur une position inconnue."""
        return self.git("commit-tree", self.arbre("main"), "-m", "sans lien")

    def remplacer_finish_checks(self, code: int):
        """Le module de contrôles sort avec ce code (sortie 2 : usage) pour toute sous-commande."""
        enveloppe = f"import sys\nprint('finish_checks : faux')\nsys.exit({code})\n"
        self.commit_main({"tools/finish_checks.py": enveloppe}, "finish_checks factice", pousser=True)
        self.mettre_a_jour_run()

    def cloner_ailleurs(self) -> Path:
        self.git("clone", "-q", str(self.distant), str(self.autre), cwd=self.dossier)
        return self.autre

    def refuser_le_push(self, refuse: bool = True):
        fichier = self.etat / "push-refuse"
        if refuse:
            fichier.write_text("x", encoding="utf-8")
        elif fichier.exists():
            fichier.unlink()

    # --- lectures ----------------------------------------------------------------------------------------------------------------------
    def rev(self, rev: str, cwd=None) -> str:
        return self.git("rev-parse", rev, cwd=cwd)

    def sommet(self, nom: str) -> str:
        return self.rev(f"refs/heads/{nom}")

    def main(self) -> str:
        return self.rev("refs/heads/main")

    def origin_main(self) -> str:
        return self.rev("refs/remotes/origin/main")

    def distant_main(self) -> str:
        return self.git("rev-parse", "refs/heads/main", cwd=self.distant)

    def arbre(self, rev: str) -> str:
        return self.rev(f"{rev}^{{tree}}")

    def commun(self) -> Path:
        return Path(self.git("rev-parse", "--path-format=absolute", "--git-common-dir"))

    def fichier_empreinte(self) -> Path:
        return Path(self.git("rev-parse", "--path-format=absolute", "--git-path", "pmzilla-run-all-ok"))

    def empreinte(self):
        f = self.fichier_empreinte()
        return f.read_text(encoding="utf-8").strip() if f.exists() else None

    def instantane(self) -> dict:
        return {"refs": self.git("for-each-ref"), "distant": self.git("for-each-ref", cwd=self.distant),
                "worktrees": self.git("worktree", "list", "--porcelain"), "statut": self.git("status", "--porcelain"),
                "run": self.git("rev-parse", "HEAD", cwd=self.run)}

    def worktrees_train(self) -> list:
        return sorted(p.name for p in self.worktrees.glob("wt-train-*"))

    def appels(self, debut: str) -> list:
        fichier = self.etat / "appels.log"
        if not fichier.exists():
            return []
        return [l for l in fichier.read_text(encoding="utf-8").splitlines() if l.startswith(debut)]

    def ci_appels(self) -> list:
        """Les arguments de chaque appel du faux ci_local, une chaîne par appel (« » pour le passage, « --rejeu … » pour un rejeu)."""
        fichier = self.etat / "ci-appels"
        return fichier.read_text(encoding="utf-8").splitlines() if fichier.exists() else []

    def journal_git(self) -> list:
        fichier = self.etat / "git.log"
        return fichier.read_text(encoding="utf-8").splitlines() if fichier.exists() else []

    def journaux(self) -> list:
        return sorted(self.logs.glob("train-fin-*.log"))

    def log(self) -> str:
        fichiers = self.journaux()
        assert len(fichiers) == 1, f"un seul journal attendu, trouvé : {[f.name for f in fichiers]}"
        return fichiers[0].read_text(encoding="utf-8")

    def lignes_validees(self) -> list:
        f = self.commun() / "pmzilla-main-validated"
        return f.read_text(encoding="utf-8").splitlines() if f.exists() else []

    def chaine_premiers_parents(self, rev: str, jusqu_a: str) -> list:
        sortie = self.git("rev-list", "--first-parent", "--reverse", f"{jusqu_a}..{rev}")
        return sortie.splitlines()

    # --- lancements --------------------------------------------------------------------------------------------------------------------
    def env(self, extra: dict = None, fakes: bool = True) -> dict:
        env = {**conserve(), "GIT_CONFIG_GLOBAL": str(self.gitconfig), "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_TERMINAL_PROMPT": "0",
               "PMZILLA_LAB_WORKSPACE": str(self.contenu), "PMZILLA_LAB_RUN": str(self.run), "PMZILLA_LAB_DATA": str(self.data),
               "PMZILLA_LAB_SENSITIVE_NAMES": str(self.noms), "PRE_PUSH_RUNNER": f"bash {self.prepush_runner}"}
        path = os.environ.get("PATH", "")
        env["PATH"] = f"{self.bin}:{self.bin_lsof}:{path}" if fakes else path
        if fakes:
            env.update(FINISH_TRAIN_MORNING_CHECK=f"bash {self.matin}", FINISH_TRAIN_LOG_DIR=str(self.logs))
            if not self.sans_substitution:   # R-20261106-57 : sous --auto, le train refuse FINISH_TRAIN_CI et FINISH_TRAIN_RUNNER ; les faux sont alors dans l'arbre d'exécution
                env.update(FINISH_TRAIN_RUNNER=f"bash {self.runner}", FINISH_TRAIN_CI=f"bash {self.ci}")
        for cle, valeur in (extra or {}).items():
            if valeur is None:
                env.pop(cle, None)
            else:
                env[cle] = valeur
        return env

    def script(self) -> Path:
        return self.run / SCRIPT

    # delai : filet de garde contre un bash vraiment bloqué, jamais une assertion de durée ; 180 s rétabli une fois la cause corrigée (le `tee`
    # détaché de finish_train.sh qui tenait les tubes de capture_output, R-20261104-26) ; remplace R-20261104-16 (600 s), décision de l'auteur (S1 bis).
    def lance(self, *args, extra: dict = None, entree: str = "", cwd=None, script: Path = None, delai: int = 180) -> Resultat:
        # Sorties vers deux fichiers (pas de tube : un `tee` détaché laissé par le script tiendrait les tubes jusqu'au délai, R-20261104-26) ; le
        # script a son propre groupe de processus, tué au retour, qu'il ait fini ou dépassé le délai.
        with tempfile.TemporaryDirectory() as dossier:
            fichier_sortie, fichier_erreur = Path(dossier) / "sortie", Path(dossier) / "erreur"
            with open(fichier_sortie, "w", encoding="utf-8") as sortie, open(fichier_erreur, "w", encoding="utf-8") as erreur:
                proc = subprocess.Popen([BASH, str(script or self.script()), *args], cwd=cwd or self.lab, env=self.env(extra),
                                        stdin=subprocess.PIPE, stdout=sortie, stderr=erreur, text=True, start_new_session=True)
                try:
                    try:
                        proc.communicate(input=entree, timeout=delai)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                        raise
                finally:
                    self._tue_le_groupe(proc.pid)
            return Resultat(proc.returncode, fichier_sortie.read_text(encoding="utf-8", errors="replace"),
                            fichier_erreur.read_text(encoding="utf-8", errors="replace"))

    @staticmethod
    def _tue_le_groupe(pgid: int):
        """Tue le groupe du script ; signale (information seulement) les processus restés après sa fin."""
        # `ps -g` n'a pas le même sens sous macOS et sous Linux : on liste tout avec le groupe en première colonne et on filtre ici.
        lignes = subprocess.run(["ps", "-ax", "-o", "pgid=,pid=,ppid=,etime=,command="], capture_output=True, text=True).stdout.splitlines()
        restes = [ligne.split(None, 1)[1] for ligne in lignes if ligne.split(None, 1)[:1] == [str(pgid)]]
        if restes:
            sys.stderr.write("aide : processus restés après la fin du script :\n   PID  PPID ELAPSED COMMAND\n" + "\n".join(restes) + "\n")
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def demarre(self, *args, extra: dict = None, cwd=None, entree: str = "") -> subprocess.Popen:
        """Lance le script dans son propre groupe de processus, sortie fusionnée, pour lui envoyer des signaux ; `entree` est écrite puis l'entrée fermée."""
        self.dernier = subprocess.Popen([BASH, str(self.script()), *args], cwd=cwd or self.lab, env=self.env(extra),
                                        stdin=subprocess.PIPE if entree else subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True,
                                        preexec_fn=_signaux_par_defaut)
        if entree:
            self.dernier.stdin.write(entree)
            self.dernier.stdin.close()
        return self.dernier

    def attend_fichier(self, nom: str, delai: float = 60.0) -> Path:
        """Attend un fichier d'état ; échoue tout de suite si le script lancé par demarre() s'est déjà arrêté."""
        fichier = self.etat / nom
        fin = time.time() + delai
        while time.time() < fin:
            if fichier.exists():
                return fichier
            if self.dernier is not None and self.dernier.poll() is not None:
                raise AssertionError(f"le script s'est arrêté (code {self.dernier.returncode}) avant que {nom} n'apparaisse")
            time.sleep(0.05)
        raise AssertionError(f"{nom} n'est jamais apparu")

    def reveille(self):
        """Écrit $ETAT/reveil, que les faux en mode « dort » attendent (au lieu d'un sommeil à durée fixe) ; le test l'écrit après son signal."""
        (self.etat / "reveil").write_text("x", encoding="utf-8")

    def enfants(self, pid: int) -> list:
        sortie = subprocess.run(["ps", "-axo", "pid=,ppid=,comm="], capture_output=True, text=True).stdout
        resultat = []
        for ligne in sortie.splitlines():
            morceaux = ligne.split(None, 2)
            if len(morceaux) == 3 and morceaux[1] == str(pid):
                resultat.append((int(morceaux[0]), os.path.basename(morceaux[2])))
        return resultat

    def descendants(self, pid: int) -> list:
        """Tous les descendants du processus : liste de (numéro, nom de commande)."""
        resultat, a_voir = [], [pid]
        while a_voir:
            courant = a_voir.pop()
            for enfant, nom in self.enfants(courant):
                resultat.append((enfant, nom))
                a_voir.append(enfant)
        return resultat

    def termine(self, proc: subprocess.Popen, delai: float = 60.0):
        """Attend la fin du script, tue ce qui reste de son groupe, rend (code, sortie)."""
        try:
            sortie, _ = proc.communicate(timeout=delai)
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        return proc.returncode, sortie

    # --- états connus -----------------------------------------------------------------------------------------------------------------
    def verrou_etranger(self, branche: str = "feat/autre", vivant: bool = True):
        dossier = self.commun() / "pmzilla-fin-en-cours"
        dossier.mkdir()
        (dossier / "pid").write_text(f"{os.getpid() if vivant else 99999999}\n", encoding="utf-8")
        (dossier / "debut").write_text(f"{int(time.time())}\n", encoding="utf-8")
        (dossier / "branche").write_text(branche + "\n", encoding="utf-8")
        (dossier / "jeton").write_text("jeton-d-un-autre\n", encoding="utf-8")
        return dossier

    def etat_fusionne_localement(self, *noms: str, extra: dict = None) -> Resultat:
        """Joue le train complet avec un push refusé par le dépôt distant : main local porte le train (état S1), code 74."""
        self.refuser_le_push(True)
        r = self.lance(*noms, extra=extra, entree="o\n")
        assert r.code == 74, r.texte
        self.refuser_le_push(False)
        return r

    def etat_pousse(self, *noms: str) -> Resultat:
        """Joue le train complet jusqu'au push, avec un fichier ignoré écrit dans le worktree de la première branche pendant le runner :
        le nettoyage garde ce worktree et sa branche (code 75), main = origin/main = train (état S2, branche encore là)."""
        r = self.lance(*noms, extra={"FAKE_RUNNER_IGNORE_DANS": str(self.dossier_worktree(noms[0]))}, entree="o\n")
        assert r.code == 75, r.texte
        return r

    def construire_train(self, noms, defaut: str = None) -> str:
        """Construit à la main la chaîne de fusions du train sur main local (comme le script la construit), avec un défaut au choix :
        troisieme_parent, message, entete, identite, arbre. Rend le sommet. Main local n'est PAS déplacé : l'appelant le fait."""
        courant = self.origin_main()
        env = dict(self.env_installation)
        for k, nom in enumerate(noms):
            tip = self.sommet(nom)
            fait = subprocess.run([self.git_reel, "merge-tree", "--write-tree", courant, tip], cwd=self.contenu, env=env, capture_output=True, text=True)
            assert fait.returncode == 0, fait.stderr
            arbre = fait.stdout.strip().splitlines()[0]
            message = f"Merge branch '{nom}'\n"
            parents = ["-p", courant, "-p", tip]
            envc = dict(env)
            if k == 0 and defaut == "troisieme_parent":
                parents += ["-p", self.git("commit-tree", self.arbre("main"), "-m", "troisième parent")]
            if k == 0 and defaut == "message":
                message = f"Merge branch '{nom}' modifié\n"
            if k == 0 and defaut == "arbre":
                arbre = self.arbre(courant)
            if k == 0 and defaut == "identite":
                envc.update(GIT_AUTHOR_NAME="autre", GIT_AUTHOR_EMAIL="autre@example.org", GIT_COMMITTER_NAME="autre",
                            GIT_COMMITTER_EMAIL="autre@example.org")
            if k == 0 and defaut == "entete":
                brut = self.git("cat-file", "commit", self.git("commit-tree", arbre, *parents, "-m", f"Merge branch '{nom}'", env=envc))
                brut = brut.replace("\n\n", "\nencoding ISO-8859-1\n\n", 1) + "\n"
                fait = subprocess.run([self.git_reel, "hash-object", "-t", "commit", "-w", "--stdin"], cwd=self.contenu, env=env,
                                      input=brut, capture_output=True, text=True)
                assert fait.returncode == 0, fait.stderr
                courant = fait.stdout.strip()
                continue
            courant = self.git("commit-tree", arbre, *parents, "-m", message.rstrip("\n"), env=envc)
        return courant

    def poser_main(self, sommet: str):
        self.git("update-ref", "refs/heads/main", sommet)
        self.git("reset", "-q", "--hard", "main")


class AvecTrain(unittest.TestCase):
    """Base des tests : un dépôt jetable par test (self.t) et les vérifications communes."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.t = Train(Path(self.temp.name))
        self.addCleanup(self.tuer_les_sommeils)

    def tuer_les_sommeils(self):
        if self.t.dernier is not None:
            try:
                os.killpg(self.t.dernier.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        fichier = self.t.etat / "pid-sleep"
        if fichier.exists():
            try:
                os.kill(int(fichier.read_text().strip()), signal.SIGKILL)
            except (ValueError, ProcessLookupError, PermissionError):
                pass

    def code(self, r: Resultat, attendu: int, *phrases: str):
        """Vérifie le code de sortie et chaque phrase (préfixe « finish_train : » ajouté) dans la sortie réunie."""
        self.assertEqual(r.code, attendu, r.texte)
        for phrase in phrases:
            self.assertIn(PREFIXE + phrase, r.texte)

    def contient(self, r: Resultat, *textes: str):
        for texte in textes:
            self.assertIn(texte, r.texte)

    def absent(self, r: Resultat, *textes: str):
        for texte in textes:
            self.assertNotIn(texte, r.texte)

    def rien_ne_change(self, avant: dict):
        self.assertEqual(self.t.instantane(), avant)

    def sha12(self, rev: str) -> str:
        return self.t.rev(rev)[:12]

    def sommet_du_train(self, r: Resultat) -> str:
        m = re.search(r"train construit : sommet ([0-9a-f]{12}), arbre ([0-9a-f]{12})", r.texte)
        self.assertIsNotNone(m, r.texte)
        return self.t.rev(m.group(1))

    def arbre_du_train(self, r: Resultat) -> str:
        m = re.search(r"train construit : sommet ([0-9a-f]{12}), arbre ([0-9a-f]{12})", r.texte)
        self.assertIsNotNone(m, r.texte)
        return m.group(2)

    def deux_branches(self):
        self.t.branche("feat/x")
        self.t.branche("feat/y")
        return "feat/x", "feat/y"
