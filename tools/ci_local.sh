#!/bin/bash
# PMZilla Lab : CI locale dans un conteneur (change local-ci-container, design D1 à D7b, D9 à D11).
#
#     bash tools/ci_local.sh run [<branche>]   les suites portables (bash tests/run_all.sh --portable) dans un conteneur jetable, hors
#                                              réseau, sur l'arbre du sommet de <branche> (défaut : HEAD, qui doit être propre)
#     bash tools/ci_local.sh build             construit l'image depuis ci/Dockerfile et l'arbre de HEAD (propre), avec réseau (auteur seul)
#     bash tools/ci_local.sh up [<branche>]    la commande unique (défaut main) : Colima, Docker, image de la clé (construite au besoin),
#                                              puis run (auteur seul) ; après une construction, retire les images pmzilla-ci dont la clé n'est celle
#                                              d'aucune branche locale ni d'aucun worktree (change ci-local-image-prune ; s'abstient pendant une preuve ou la fin)
#     bash tools/ci_local.sh cle               la clé d'image de HEAD et la présence de l'image (lecture seule ; 0 présente, 3 Docker, 5 absente)
#     bash tools/ci_local.sh places [--json]   les places de passage (change ci-local-runner, D3) : lecture seule, ni conteneur ni fichier écrit
#     bash tools/ci_local.sh run --rejeu portable <suite> [<suite> ...]   le rejeu (change ci-local-runner, tranche 2, Q220, R-20261101-113) :
#                                              ces suites seules (bash tests/run_all.sh <suites>), sans base ni phase base ou e2e, dans la file
#                                              avec la priorité du jeton du verrou de fin ; HEAD propre ; n'écrit ni verdict, ni preuve, ni rapport
#     bash tools/ci_local.sh run --index [<suite> ...]    (change tooling-proof-in-container, T2, D4, D1) ces suites seules (bash tests/run_all.sh
#                                              <suites>), sans base ni phase base ou e2e, sur l'arbre de l'INDEX (git write-tree, calculé ici,
#                                              jamais reçu) ; sans suite : le passage complet (trois phases) sur cet arbre. Vert : une ligne
#                                              <arbre><TAB><clé d'image><TAB><suites séparées par des virgules, ou « complet »> est ajoutée au fichier
#                                              des preuves d'index (ci/preuves-index du dossier de données, CI_LOCAL_PREUVES_INDEX pour les tests ;
#                                              avec CI_LOCAL_DOCKER posée sans lui, rien n'est écrit) ; rouge ou interrompu : aucune ligne
#     bash tools/ci_local.sh run --travail [<suite> ...]  de même sur l'arbre de TRAVAIL (fichiers suivis et fichiers non suivis non ignorés, par un
#                                              index temporaire : seuls des objets Git sont écrits, ni référence ni index réel) ; n'écrit ni preuve, ni
#                                              verdict, ni rapport
#     bash tools/ci_local.sh --help
#
# --index et --travail se refusent avec un nom de branche, entre eux, ou avec un nom de suite hors de [A-Za-z0-9_]+ : code 2. Place « ciblée »
# (2 processeurs, 3072 Mio, sans base) dans la file ; la place d'une preuve garde 3 + 1 processeurs (suites + base) et 4096 + 2048 Mio (D5).
# Remplace : les lancements ciblés et filtrés du Mac en session. Retrait : permanent, tant que la CI est le runner.
#
# run et places sont permis à la session ; build et up sont à l'auteur, dans son Terminal (règles deny de D12).
#
# Script intérieur (change ci-local-runner, D2) : ci/passage.sh, lu ici (jamais copié) et lancé par bash -c dans le conteneur ; il remplace
# la chaîne qui était dans ce fichier (retrait : permanent). Phases lues dans sa sortie : lignes « ci_passage : phase <nom> : verte|rouge ».
# Tranche 2 (R-20261101-113) : le texte lancé est tools/e2e_steps.sh puis ci/passage.sh, tous deux lus dans le dépôt de CET outil (jamais dans
# l'arbre testé : R-94) ; tools/e2e_steps.sh manquant : code 4 « script intérieur introuvable (tools/e2e_steps.sh) ». Le conteneur des suites a
# --shm-size 1g (Chromium). Après une phase e2e verte, « ci_local : preuve enregistrée pour l'arbre <court> (phases portable,base,e2e) » (D6) :
# fichier preuves à côté des verdicts, ligne <arbre><TAB><clé d'image><TAB><phases>, mêmes règles d'écriture que les verdicts (verrou, ligne
# retirée au départ, fichier temporaire renommé, propriétaire seul), CI_LOCAL_PREUVES pour les tests (avec CI_LOCAL_DOCKER posée sans lui, rien
# n'est lu ni écrit) ; « ci_local : preuve non enregistrée (<raison>) » sinon. Un passage sans phase e2e verte n'écrit jamais de preuve.
# Places (D3) : la fonction places_calculees est la seule à calculer N ; places --json l'imprime, la forme texte ne fait que la formater.
#
# Deux conteneurs par passage (change ci-local-runner, tranche 1, D1 ; R-20261101-59, -73, -74) : une base ParadeDB jetable
# (pmzilla-ci-<hex>-base : image de docker-compose.yml de l'arbre prouvé, --network none, aucun port publié, données en tmpfs, --shm-size 1g, 1 processeur,
# 2048 Mio, mot de passe au hasard par un fichier d'environnement propriétaire seul, retiré dès la création) et le conteneur des suites,
# qui n'a pour réseau que la boucle locale de la base (--network container:<base>) ; aucun réseau Docker créé, aucun montage ni socket,
# aucune variable de l'appelant. Le mot de passe de la base passe au conteneur des suites par l'environnement du seul processus docker
# (--env NOM sans valeur), jamais en argument. Les deux sont retirés à la fin, en cas d'échec et sur INT/TERM : suites, puis base.
# L'image de la base n'est jamais construite ni tirée ici (l'auteur seul) : absente, code 5 et sa phrase (D11).
# Places et file (D3, R-20261101-76 et -78) : un passage attend sa place sans borne de temps et sans refus ; une place tenue par un
# processus mort est reprise ; le passage qui porte le jeton vivant du verrou de fin passe devant dans la file, jamais dans une place
# tenue ; les codes 2 à 8 sont rendus avant la file. Remplace : le passage unique de la tranche 0 (retrait : permanent, tant que la CI
# est le lanceur).
#
# Ce que fait run :
#   1. refus avant tout conteneur (codes 2 à 8 ci-dessous) ; l'arbre testé est celui d'UN commit : le sommet de la branche nommée, ou
#      HEAD quand l'extraction est propre (un fichier non suivi non ignoré compte) ; une modification non commitée n'est jamais testée ;
#   2. clé de l'image calculée depuis l'arbre testé : hash de ci/Dockerfile, des entrées « pinned_in: CI Dockerfile » de
#      docs/pmzilla/composants.yaml, de .python-version, de la ligne DEPS de tests/run_all.sh, des blocs « # /// script » des scripts Python de tools, tests et
#      .claude/skills (la sélection de l'étape du Dockerfile) et de chaque verrou npm déclaré (D10 :
#      la liste SUITES_NPM=(<dossier>:<nom> …) du lanceur, verrou <dossier>/package-lock.json ; aujourd'hui mothra) ; aucune image de
#      cette clé : code 5 ; tests/suites_mac.txt est lu au passage, hors de la clé ;
#   3. git archive de l'arbre, envoyé sur l'entrée du conteneur (jamais de montage), recommité dans un dépôt jetable à auteur neutre ;
#   4. docker run --rm, --network none, utilisateur non root, nom au hasard, limites de processeurs et de mémoire, aucun montage, volume,
#      périphérique ni socket ; environnement construit ici (langue, fuseau, HOME et TMPDIR du conteneur, UV_OFFLINE=1, CI_PASSAGE_CPUS =
#      les processeurs du passage, dont RUN_ALL_JOBS est égal, RUN_ALL_DURATIONS dans le conteneur) : aucune variable de l'appelant ne passe
#      (PMZILLA_LAB_DB_*, DBTEST_PORT, jetons, FINISH_LOCK_TOKEN, variables des noms sensibles) ; les suites avec base sautent (D11) ;
#   5. le conteneur est retiré à la fin, en cas d'échec et sur interruption (INT, TERM) ;
#   6. rapport : un fichier texte par passage dans le dossier ci du dossier de données du lab (tools/lab_paths.sh), propriétaire seul :
#      arbre, clé, date et heure de début, lignes de suite du lanceur, ligne « Tests sautés », ligne des suites Mac, ligne TOTAL, liste Mac, code ; ni chemin,
#      ni nom de branche, ni personne. Un rapport non écrit est dit en une ligne et ne change ni le verdict ni le code ;
#   7. dernière ligne, toujours, quand un conteneur a tourné :
#        ci_local : verdict vert (arbre <court>, image <clé courte>, <n> suites, <m> suites Mac non lancées)
#        ci_local : verdict rouge (arbre <court>, image <clé courte>) : <suites en échec>
#      précédée de la ligne TOTAL du lanceur, de sa ligne des suites Mac, puis de la ligne d'enregistrement.
#
# Verdict enregistré (D7b, modèle : l'empreinte de tools/dbtest.sh) :
#   fichier : verdicts du dossier ci du dossier de données du lab, hors du dépôt et de tout dossier .git (CI_LOCAL_VERDICTS pour les
#   tests ; avec CI_LOCAL_DOCKER posée sans CI_LOCAL_VERDICTS, rien n'est lu ni écrit) ;
#   ligne : <arbre><TAB><vert|rouge><TAB><clé d'image>, une par arbre (identifiant complet de l'arbre du commit testé), ni branche, ni
#   chemin, ni date, ni jeton, ni personne ;
#   départ : une fois les refus 2 à 8 passés, avant le conteneur, la ligne de l'arbre testé est retirée (un passage interrompu, ou dont
#   le conteneur ne donne pas de verdict du lanceur, n'en laisse aucune) ;
#   fin : la ligne de l'arbre est écrite, vert ou rouge, sans toucher aux autres, par un fichier temporaire renommé, propriétaire seul ;
#   « ci_local : verdict enregistré pour l'arbre <court> » ou « ci_local : verdict non enregistré (dossier de données introuvable |
#   écriture impossible) », juste avant la ligne du verdict ; un enregistrement manqué ne change jamais le code ; un retrait manqué de la
#   ligne de départ le dit tout de suite (« verdict précédent de cet arbre non retiré (écriture impossible) ») et empêche l'écriture finale ;
#   les écritures passent par un verrou mkdir à côté du fichier (verdicts.lock, repris au bout d'une minute, 5 s d'attente au plus) ;
#   qui l'écrit : run seul (et up, qui le lance) ; une ligne écrite à la main passerait (c'est une déclaration, comme pour dbtest) ;
#   qui le lit : plus aucune fin (depuis B78 la fin d'un worktree ne le lit plus, et le dernier lecteur, tools/finish_branch.sh, est retiré par B9,
#   R-20261101-91) ; il ne lance aucun conteneur.
#
# Codes de sortie : 0 passage vert, image construite, up vert ; 1 passage rouge ; 2 usage ; 3 Docker (ou Colima) ne répond pas ;
# 4 entrée refusée (hors du dépôt, branche inconnue, arbre non propre) ; 5 image absente ou périmée, ou dépendances npm de l'image
# différentes du verrou ; 6 construction en échec ; 7 une autre fin de branche tient le verrou ; 8 place libre insuffisante dans la machine Colima
# (moins de 15 Gio dans /var/lib/docker, mesurés par colima ssh ; mesure impossible : une ligne, le passage continue ; change ci-local-image-prune).
# Les codes 2 à 8 ne démarrent aucun conteneur ; 6 ne laisse aucune image étiquetée ; 8 vient après 3 et avant 5.
# Verrou de fin : `build` et `up` gardent le gel général (un verrou vivant d'un autre
# jeton, ou sans FINISH_LOCK_TOKEN, refuse en 7). `run` suit le gel ciblé (autonomous-trains-merge, D18, règle unique de tools/finish_lock.py,
# freezes()) : 7 seulement quand le worktree courant est dans la liste du verrou ou que le verrou n'a pas de liste lisible ; tout autre `run`
# attend dans la file derrière le passage du train, qui garde sa priorité. Remplace : le refus 7 de tout `run` pendant un train
# (R-20261101-72). Retrait : permanent. Un verrou périmé est dit et ignoré ; le jeton de la fin ne change rien ; le script ne
# crée, ne retire ni ne modifie jamais le verrou.
#
# Couche npm (D10) : ci/Dockerfile fait `npm ci` à la construction (avec réseau) pour la suite npm déclarée (mothra) et garde le résultat
# dans /opt/ci/npm/<dossier>/node_modules ; le passage copie ce dossier dans l'arbre extrait (jamais d'installation au passage, jamais le
# registre). Une suite npm déclarée dont le verrou diffère de celui de l'image : code 5, comme une clé périmée.
#
# Variables (pour les tests) : CI_LOCAL_DOCKER (commande Docker, défaut docker), CI_LOCAL_COLIMA (commande Colima, défaut colima),
# CI_LOCAL_VERDICTS (autre fichier des verdicts). Dossier de données : celui de tools/lab_paths.sh (PMZILLA_LAB_DATA).
set -uo pipefail
ICI="$(cd "$(dirname "$0")" && pwd)"
DOCKER="${CI_LOCAL_DOCKER:-docker}"
COLIMA="${CI_LOCAL_COLIMA:-colima}"
IMAGE_NOM="pmzilla-ci"
# Processeurs par place (R-20261103-6, Q4). Le profil Colima du lab est maintenant de 8 processeurs et 16 Go (colima start --cpu 8 --memory 16).
# CPUS_GRAINE (3) ne sert qu'à COMPTER les places : N = min(processeurs / (CPUS_GRAINE + CPUS_BASE), places que la mémoire permet). Le nombre de
# processeurs d'un passage est ensuite CALCULÉ par places_calculees : processeurs / N - CPUS_BASE (au moins 1), le conteneur de la base comprise ;
# 8 processeurs et 2 places donnent 3. Sans processeurs lisibles, la graine tient lieu de valeur. CPUS est posé par passage() et rejeu() depuis le
# champ cpus_passage du JSON. Remplace : « CPUS=3 » écrit en dur (commentaire sur l'ancien profil de 4 processeurs et 6 Go).
# Retrait : permanent, tant que le nombre de processeurs d'une place dépend de celui du moteur.
CPUS_GRAINE=3
CPUS=$CPUS_GRAINE
MEMOIRE_MIO=4096
MEMOIRE="${MEMOIRE_MIO}m"   # une seule source de la mémoire du passage
# Entrées du calcul des places (D3). Remplace : rien (valeurs neuves pour CPUS_BASE, MEMOIRE_BASE_MIO et RESERVE_MIO). Retrait : avec places_calculees.
CPUS_BASE=1; MEMOIRE_BASE_MIO=2048; RESERVE_MIO=3072
# Place ciblée (tooling-proof-in-container, D5) : 2 processeurs et 3072 Mio, sans base. Remplace : rien (les lancements ciblés d'une session ne
# passaient pas par le conteneur). Retrait : permanent, tant que les lancements ciblés d'une session passent par le conteneur.
CPUS_CIBLEE=2; MEMOIRE_CIBLEE_MIO=3072
# Port de PostgreSQL dans la base du passage (boucle locale partagée) : une seule source, ci/passage.sh le répète en constante (55432, comme tools/dbtest.sh).
# Remplace : rien. Retrait : permanent, tant que la base du passage écoute sur ce port.
PORT_BASE=55432
TAB=$(printf '\t')

dire() { printf 'ci_local : %s\n' "$*"; }
refus() { local code=$1; shift; printf 'ci_local : %s\n' "$*" >&2; exit "$code"; }
usage() { refus 2 "usage : bash tools/ci_local.sh run [<branche>] | build | up"; }
# Le nom d'une suite du rejeu : [A-Za-z0-9_]+ sous LC_ALL=C (Q230). Une fonction à part, et non un test de forme dans le bloc d'analyse des
# arguments : tests/settings_deny lit ce bloc jusqu'à sa première fin de test de forme. Remplace : le test de forme en ligne. Retrait : permanent.
nom_suite_valide() { ( LC_ALL=C; [[ -n $1 && $1 != *[!A-Za-z0-9_]* ]] ); }
usage_rejeu() { refus 2 "usage : run --rejeu portable <suite> [<suite>…]"; }   # D9 (revue de la tranche 2) ; remplace la phrase générale pour un rejeu mal formé
usage_mode() { refus 2 "usage : run --index|--travail [<suite>…]"; }   # T2 (D8, R-20261104-7 P4) : jamais de nom de branche ; remplace rien, retrait : permanent

# --- usage --------------------------------------------------------------------------------------------------------------------
[ $# -ge 1 ] || usage
SOUS=$1; BRANCHE=""; PLACES_JSON=0; REJEU=0; SUITES_REJEU=(); MODE_ARBRE=""
case "$SOUS" in
  --help|-h) [ $# -eq 1 ] || usage; sed -n '2,/^set -uo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit 0 ;;
  places) [ $# -le 2 ] || usage; if [ $# -eq 2 ]; then [ "$2" = "--json" ] || usage; PLACES_JSON=1; fi ;;
  # Rejeu (Q220) : « run --rejeu portable <suite> ... », au moins une suite, chaque nom en lettres, chiffres et soulignés (jamais une option du
  # lanceur ni un texte interprétable). Remplace : rien. Retrait : permanent, tant que le train rejoue en conteneur.
  run) if [ "${2:-}" = "--rejeu" ]; then
         [ $# -ge 4 ] && [ "$3" = "portable" ] || usage_rejeu
         REJEU=1; shift 3
         # LC_ALL=C : l'intervalle A-Za-z ne dépend pas de la langue (Q230 en attente : la garde [A-Za-z0-9_]+ des deux côtés)
         for s in "$@"; do nom_suite_valide "$s" || usage_rejeu; done
         SUITES_REJEU=("$@")
       elif [ "${2:-}" = "--index" ] || [ "${2:-}" = "--travail" ]; then
         # T2 (D4) : « run --index|--travail [<suite> ...] », jamais un nom de branche, chaque nom en lettres, chiffres et soulignés. Les noms
         # passent par SUITES_REJEU (même conteneur sans base que le rejeu).
         MODE_ARBRE=${2#--}; shift 2
         # Décision R-20261104-58 Q1 (a). Remplace : l'acceptation d'un champ qui contient complet. Retrait : permanent tant que complet désigne le mode complet de la preuve d'index.
         for s in "$@"; do nom_suite_valide "$s" && [ "$s" != complet ] || usage_mode; done   # « complet » est le mot du mode complet, jamais un nom de suite
         SUITES_REJEU=("$@")
       else
         [ $# -le 2 ] || usage; BRANCHE="${2:-}"
       fi ;;
  up) [ $# -le 2 ] || usage; BRANCHE="${2:-}" ;;
  build) [ $# -eq 1 ] || usage ;;
  cle) [ $# -eq 1 ] || usage ;;   # R-20261103-6 (Q9) : lecture seule, lue par le contrôle ci-container de tools/doctor.py
  *) usage ;;
esac
case "$BRANCHE" in -*) usage ;; esac
# build et up sont des gestes de l'auteur : refusés dans une session, avant tout (R-20261101-89 ; même détection et même code que tools/finish_train.sh).
# Remplace : rien (durcit les règles deny, qui restent). Retrait : permanent, tant que build et up sont des gestes de l'auteur.
case "$SOUS" in build|up) [ -z "${CLAUDECODE:-}" ] || refus 61 "lancement refusé : session Claude Code ; $SOUS se lance dans le Terminal de l'auteur" ;; esac

# --- dépôt et verrou de fin ----------------------------------------------------------------------------------------------------
RACINE_DEPOT=$(git rev-parse --show-toplevel 2>/dev/null) || refus 4 "hors du dépôt"
cd "$RACINE_DEPOT" || refus 4 "hors du dépôt"
COMMUN=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || COMMUN=""
. "$ICI/finish_lock.sh"   # _fl_stale : même règle de péremption que la fin de branche ; sourcé, il n'écrit rien

# `run` pendant une fin (autonomous-trains-merge, D18 points 3 et 4) : la règle unique de tools/finish_lock.py (freezes(), via `refuse`), sans règle
# de gel propre à ce script. Code 7 seulement quand le worktree courant est dans la liste du verrou ou que le verrou n'a pas de liste lisible
# (module introuvable ou réponse inattendue : refus, échec fermé) ; tout autre `run` continue et attend dans la file derrière le passage du train
# (le jeton du train garde sa priorité : porte_jeton_vivant). Un verrou périmé est dit et ignoré. build et up gardent verifier_verrou (gel général).
# Remplace : le refus 7 de tout `run` pendant un train (R-20261101-72, tombe avec ce change). Retrait : permanent ; un refus plus large est un défaut.
verifier_gel_run() {
  local dossier="$COMMUN/pmzilla-fin-en-cours" sortie rc
  [ -n "$COMMUN" ] && [ -d "$dossier" ] || return 0
  sortie=$(python3 -I -B "$ICI/finish_lock.py" refuse --common "$COMMUN" --worktree "$RACINE_DEPOT" 2>/dev/null); rc=$?
  case "$rc:$sortie" in
    0:perime) dire "verrou de fin périmé, ignoré" ;;
    0:) ;;
    *) refus 7 "fin de branche en cours (${sortie:-$(cat "$dossier/branche" 2>/dev/null || echo '?')}), lancement refusé" ;;
  esac
}
verifier_verrou() {
  local dossier="$COMMUN/pmzilla-fin-en-cours"
  [ -n "$COMMUN" ] && [ -d "$dossier" ] || return 0
  if _fl_stale "$dossier"; then dire "verrou de fin périmé, ignoré"; return 0; fi
  if [ -z "${FINISH_LOCK_TOKEN:-}" ] || [ "$(cat "$dossier/jeton" 2>/dev/null)" != "$FINISH_LOCK_TOKEN" ]; then
    refus 7 "fin de branche en cours ($(cat "$dossier/branche" 2>/dev/null || echo '?')), lancement refusé"
  fi
}

# --- arbre testé ---------------------------------------------------------------------------------------------------------------
COMMIT=""; ARBRE=""
resoudre() { # <branche> (vide : HEAD propre) -> COMMIT, ARBRE
  if [ -n "$1" ]; then
    git check-ref-format --branch "$1" >/dev/null 2>&1 || refus 4 "branche inconnue : $1"
    COMMIT=$(git rev-parse --verify -q "refs/heads/$1^{commit}") || refus 4 "branche inconnue : $1"
  else
    COMMIT=$(git rev-parse --verify -q 'HEAD^{commit}') || refus 4 "arbre non propre ; rien n'est lancé"
    [ -z "$(git status --porcelain 2>/dev/null)" ] || refus 4 "arbre non propre ; rien n'est lancé"
  fi
  ARBRE=$(git rev-parse "$COMMIT^{tree}")
}
# T2 (D4) : l'arbre est calculé ICI, jamais reçu. index : git write-tree de l'index réel (des objets Git, ni référence ni index modifié). travail :
# un index TEMPORAIRE (HEAD, puis git add -A : fichiers suivis et fichiers non suivis non ignorés), écrit par GIT_INDEX_FILE ; le vrai index et
# les références ne sont jamais touchés. COMMIT porte l'identifiant de l'arbre (git archive et git show l'acceptent). Remplace : rien. Retrait : permanent.
resoudre_arbre() { # index|travail -> COMMIT, ARBRE
  local idx
  if [ "$1" = index ]; then
    ARBRE=$(git write-tree 2>/dev/null) || refus 4 "index illisible ; rien n'est lancé"
  else
    idx=$(mktemp -u "${TMPDIR:-/tmp}/ci_local_index.XXXXXX") || refus 4 "arbre de travail illisible ; rien n'est lancé"
    if git rev-parse --verify -q 'HEAD^{commit}' >/dev/null 2>&1; then
      GIT_INDEX_FILE=$idx git read-tree HEAD >/dev/null 2>&1 || { rm -f "$idx"; refus 4 "arbre de travail illisible ; rien n'est lancé"; }
    fi
    GIT_INDEX_FILE=$idx git add -A >/dev/null 2>&1 || { rm -f "$idx"; refus 4 "arbre de travail illisible ; rien n'est lancé"; }
    ARBRE=$(GIT_INDEX_FILE=$idx git write-tree 2>/dev/null); local rc=$?
    rm -f "$idx"
    [ "$rc" -eq 0 ] && [ -n "$ARBRE" ] || refus 4 "arbre de travail illisible ; rien n'est lancé"
  fi
  [ -n "$ARBRE" ] || refus 4 "arbre illisible ; rien n'est lancé"
  COMMIT=$ARBRE
}
resoudre_source() { # <branche ou vide> : l'arbre d'un commit, ou (T2) celui de l'index ou du travail
  if [ -n "$MODE_ARBRE" ]; then resoudre_arbre "$MODE_ARBRE"; else resoudre "$1"; fi
}

# --- clé de l'image (D4, D10) ----------------------------------------------------------------------------------------------------
if command -v shasum >/dev/null 2>&1; then HACHE=(shasum -a 256); else HACHE=(sha256sum); fi
hacher() { "${HACHE[@]}" | cut -c1-64; }
fichier_de() { git show "$1:$2" 2>/dev/null; }
verrous_npm() { # <commit> : par suite npm déclarée par le lanceur, le verrou, le .npmrc (s'il existe) et le .node-version, qui entrent tous dans la clé
  fichier_de "$1" tests/run_all.sh | sed -n 's/^SUITES_NPM=(\(.*\))[[:space:]]*$/\1/p' | tr ' ' '\n' \
    | sed -n 's/^\([A-Za-z0-9_.-][A-Za-z0-9_./-]*\):[A-Za-z0-9_-]*$/\1\/package-lock.json \1\/.npmrc \1\/.node-version/p' | tr ' ' '\n'
}
scripts_pep723() { # <commit> : chemin et bloc « # /// script » de chaque script Python de tools, tests et .claude/skills (la sélection de l'étape du Dockerfile)
  local c=$1 f
  git grep -l '^# /// script' "$c" -- 'tools/*.py' 'tests/*.py' '.claude/skills/*.py' 2>/dev/null | sed "s/^$c://" | LC_ALL=C sort | while IFS= read -r f; do
    echo "$f"
    fichier_de "$c" "$f" | sed -n '/^# \/\/\/ script/,/^# \/\/\/[[:space:]]*$/p'
  done
}
engines_npm() { # <commit> <package.json> : la valeur du champ engines.npm (vide s'il est absent), lue du commit
  fichier_de "$1" "$2" | sed -n '/"engines"[[:space:]]*:/,/}/p' | sed -n 's/.*"npm"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1
}
CLE_BASE=""; CLE=""; NPM=""
cles() { # <commit> -> CLE_BASE (sans npm), NPM (verrous déclarés et leurs hash), CLE
  local c=$1 v
  CLE_BASE=$( { echo "ci/Dockerfile"; fichier_de "$c" ci/Dockerfile
                echo "inventaire"; fichier_de "$c" docs/pmzilla/composants.yaml | grep -E 'pinned_in:[[:space:]]*CI Dockerfile'
                echo ".python-version"; fichier_de "$c" .python-version
                echo "DEPS"; fichier_de "$c" tests/run_all.sh | grep -E '^DEPS='
                echo "en-têtes PEP 723"; scripts_pep723 "$c"; } | hacher )
  NPM=""
  for v in $(verrous_npm "$c"); do
    NPM="$NPM$v $(fichier_de "$c" "$v" | hacher);"
    # engines.npm du package.json de la suite (R-20261101-112) : le Dockerfile installe cette version de npm, un changement refait l'image
    case "$v" in */package-lock.json) NPM="$NPM${v%package-lock.json}package.json engines.npm=$(engines_npm "$c" "${v%package-lock.json}package.json");" ;; esac
  done
  CLE=$(printf '%s\n%s\n' "$CLE_BASE" "$NPM" | hacher)
}

docker_repond() { "$DOCKER" info >/dev/null 2>&1 || refus 3 "Docker ne répond pas ; rien n'est lancé (colima status)"; }
image_existe() { "$DOCKER" image inspect "$IMAGE_NOM:$1" >/dev/null 2>&1; }
# R-20261101-118 (Q229 a) : la commande de construction nomme le worktree RÉEL de la branche visée (« branch refs/heads/<b> » de
# git worktree list --porcelain). Sans worktree pour cette branche : git worktree add <chemin> <branche>, le chemin suivant la convention
# de tools/worktree.sh (dossier des worktrees de lab_paths.sh, puis wt-<branche avec / remplacé par ->). HEAD détaché : le dépôt courant.
# Remplace : « cd $RACINE_DEPOT » (R-20261101-116), qui nommait le dépôt courant même pour une autre branche. Retrait : permanent.
commande_up() {
  local b=${BRANCHE:-} chemin="" dossier espace
  [ -n "$b" ] || b=$(git symbolic-ref --short -q HEAD 2>/dev/null) || b=""
  # R-20261101-120 (Q237) : HEAD détaché (le worktree d'intégration jetable du train) : le worktree PRINCIPAL, premier de la liste. Remplace :
  # « cd $RACINE_DEPOT ». Retrait : permanent.
  if [ -z "$b" ]; then
    chemin=$(git worktree list --porcelain 2>/dev/null | awk '/^worktree /{print substr($0,10); exit}')
    printf 'cd %q && bash tools/ci_local.sh up' "${chemin:-$RACINE_DEPOT}"; return 0
  fi
  chemin=$(git worktree list --porcelain 2>/dev/null | awk -v b="refs/heads/$b" '/^worktree /{d=substr($0,10)} $1=="branch" && $2==b {print d; exit}')
  if [ -n "$chemin" ]; then printf 'cd %q && bash tools/ci_local.sh up' "$chemin"; return 0; fi
  espace=$(dirname "${COMMUN:-$RACINE_DEPOT/.git}")
  dossier=$( . "$ICI/lab_paths.sh"; lab_paths_worktrees_folder "$espace" )
  case "$dossier" in /*) ;; *) dossier="$RACINE_DEPOT/$dossier" ;; esac
  chemin="$dossier/wt-${b//\//-}"
  # printf %q : l'auteur colle la commande ; git check-ref-format accepte « ; », « $( », « | » et « & » dans un nom de branche.
  printf 'git worktree add %q %q && cd %q && bash tools/ci_local.sh up' "$chemin" "$b" "$chemin"
}
# R-20261101-120 (Q237) : en HEAD détaché, la phrase du code 5 est suivie d'une ligne fixe (préfixe « ci_local : » comme la première : le train ne
# réimprime que les lignes « ^(ci_passage|ci_local) : »). Aucun calcul des branches en cause. Retrait : permanent.
suite_code5() {
  if [ -z "${BRANCHE:-}" ] && ! git symbolic-ref -q HEAD >/dev/null 2>&1; then
    printf '\nci_local : si une branche du train change la clé (ci/Dockerfile, verrou npm, bloc # /// script, engines.npm), construire l'"'"'image depuis le worktree de cette branche'
  fi
}
verifier_image() {
  image_existe "$CLE" && return 0
  if [ -n "$NPM" ] && [ -n "$("$DOCKER" images -q --filter "label=pmzilla.ci.base=$CLE_BASE" 2>/dev/null)" ]; then
    refus 5 "dépendances npm de l'image différentes du verrou (lancer : $(commande_up))$(suite_code5)"
  fi
  # R-20261101-116 (Q222 a) : la commande EXACTE de construction depuis le worktree de cet arbre (up construit l'image de la clé de HEAD ici).
  # Remplace : la phrase « (lancer bash tools/ci_local.sh up) » sans dossier. Retrait : permanent.
  refus 5 "image absente ou périmée pour cet arbre (lancer : $(commande_up))$(suite_code5)"
}

# --- place libre de la machine Colima (change ci-local-image-prune, D4 à D7 ; R-20261106-55, -56) ---------------------------------------------
# Minimum de place libre dans /var/lib/docker de la machine Colima, en Gio, en dessous duquel un passage est refusé (code 8). Une seule source, pas de
# variable pour la changer : les tests passent des deux côtés par la sortie du faux df. Remplace : rien (le manque de place se voyait en plein passage,
# « No space left on device »). Retrait : permanent, tant que la CI tourne dans la machine Colima, dont le disque a une taille fixe et porte aussi la
# vraie base ; il tombe avec le refus de code 8 (verifier_place_vm) qui le lit.
PLACE_LIBRE_MIN_GIO=15
# Place libre en Kio, mesurée depuis le Mac, sans image ni réseau ni conteneur : « colima ssh -- df -Pk /var/lib/docker », champ 4 de la deuxième ligne.
# Sortie non nulle, ligne absente ou champ non entier : mesure impossible (retour 1). Remplace : rien. Retrait : avec PLACE_LIBRE_MIN_GIO.
place_libre_vm_kio() {
  local sortie kio
  sortie=$("$COLIMA" ssh -- df -Pk /var/lib/docker </dev/null 2>/dev/null) || return 1
  kio=$(printf '%s\n' "$sortie" | awk 'NR == 2 { print $4 }')
  entier "$kio" || return 1
  printf '%s' "$kio"
}
# Refus de code 8 avant la file et tout conteneur, juste après docker_repond (donc après 2, 7, 4 et 3, avant 5). Mesure impossible : une ligne, puis
# le passage continue (R-20261106-56 Q1 a : l'échec gardé est un passage rouge, jamais un faux vert). Remplace : rien. Retrait : permanent, tant que la CI
# tourne dans la machine Colima.
verifier_place_vm() {
  local kio
  if ! kio=$(place_libre_vm_kio); then
    dire "place libre de la machine Colima non mesurée ; passage sans ce contrôle"
    return 0
  fi
  if [ "$kio" -lt $((PLACE_LIBRE_MIN_GIO * 1024 * 1024)) ]; then
    refus 8 "place libre insuffisante dans la machine Colima ($((kio / 1048576)) Gio libres, minimum $PLACE_LIBRE_MIN_GIO Gio) ; rien n'est lancé (nettoyage : docker image ls $IMAGE_NOM, puis docker image rm $IMAGE_NOM:<clé> pour chaque clé sans branche ouverte)"
  fi
}

# --- construction (D1 build, D4) ---------------------------------------------------------------------------------------------------
construire() { # <commit> : image de la clé de ce commit, contexte = archive de son arbre
  local c=$1
  cles "$c"
  if ! git archive --format=tar "$c" | "$DOCKER" build --tag "$IMAGE_NOM:$CLE" --label "pmzilla.ci.cle=$CLE" \
       --label "pmzilla.ci.base=$CLE_BASE" --file ci/Dockerfile -; then
    refus 6 "construction de l'image en échec"
  fi
  dire "image construite (${CLE:0:12})"
}

# --- dossier de données (lab-paths) ------------------------------------------------------------------------------------------------
dossier_donnees() { ( . "$ICI/lab_paths.sh"; lab_paths_init >/dev/null 2>&1 && [ -d "$LAB_DATA_FOLDER" ] && printf '%s' "$LAB_DATA_FOLDER" ); }

# --- places (change ci-local-runner, D3) ----------------------------------------------------------------------------------------------
# Remplace : le plan des places de runner (R-20261101-57 et -58) et, pour les passages de la CI, la règle « un seul lanceur complet à la fois ».
# Retrait : permanent, tant que la CI est le lanceur. Tranche 0 : calcul et lecture seulement (places tenues et file lues, jamais écrites).
entier() { case "$1" in ""|*[!0-9]*) return 1 ;; *) return 0 ;; esac; }
valeur_json() { if [ -n "$1" ]; then printf '%s' "$1"; else printf 'null'; fi; }
champ_json() { # <json> <champ> : la valeur de la PREMIÈRE occurrence du champ (les champs de premier niveau d'abord), « null » comprise
  local reste="${1#*\"$2\":}"   # T2 : les objets imbriqués (preuve, ciblee, detenues) répètent « processeurs » et « memoire_mio »
  [ "$reste" != "$1" ] || return 0
  reste="${reste%%[,\}]*}"
  printf '%s\n' "$reste"
}
# Taille d'une place tenue, lue dans son dossier (T2, D5) : « preuve » (processeurs du passage + base, mémoire du passage + base) ou « ciblee »
# (CPUS_CIBLEE, MEMOIRE_CIBLEE_MIO). Une place sans fichier type (écrite avant T2, ou par un test) compte comme une preuve ; sans fichier cpuset,
# son nombre de processeurs est celui de son type. Remplace : rien. Retrait : permanent, tant que les places sont typées.
compter_cpuset() { local x="$1" n=0 i; for i in ${x//,/ }; do n=$((n + 1)); done; printf '%s' "$n"; }
type_de_place() { local t; t=$(cat "$1/type" 2>/dev/null); case "$t" in ciblee) printf ciblee ;; *) printf preuve ;; esac; }
processeurs_de_place() { # <dossier> <processeurs d'une preuve>
  local cs t; cs=$(cat "$1/cpuset" 2>/dev/null); t=$(type_de_place "$1")
  if [ -n "$cs" ]; then compter_cpuset "$cs"; elif [ "$t" = ciblee ]; then printf '%s' "$CPUS_CIBLEE"; else printf '%s' "$2"; fi
}
memoire_de_place() { if [ "$(type_de_place "$1")" = ciblee ]; then printf '%s' "$MEMOIRE_CIBLEE_MIO"; else printf '%s' $((MEMOIRE_MIO + MEMOIRE_BASE_MIO)); fi; }
places_calculees() { # JSON d'une ligne ; la SEULE fonction qui calcule N (places --json l'imprime, la forme texte le formate)
  local ligne cpu="" mem="" mem_mio="" n n_cpu n_mem donnees="" tenues=0 file=0 p f pid cpus_p=$CPUS_GRAINE
  local detenues="" entree pr_p pr_c ut_c=0 ut_m=0 libres_c libres_m libres_ciblees="null" proc_p mem_p cs_p
  ligne=$("$DOCKER" info --format '{{.NCPU}} {{.MemTotal}}' 2>/dev/null)
  read -r cpu mem _ <<< "$ligne"
  entier "$cpu" || cpu=""
  if entier "$mem"; then mem_mio=$((mem / 1048576)); fi
  if [ -n "$cpu" ] && [ -n "$mem_mio" ]; then
    n_cpu=$((cpu / (CPUS_GRAINE + CPUS_BASE)))
    if [ "$mem_mio" -gt "$RESERVE_MIO" ]; then n_mem=$(((mem_mio - RESERVE_MIO) / (MEMOIRE_MIO + MEMOIRE_BASE_MIO))); else n_mem=0; fi
    n=$n_cpu; [ "$n_mem" -ge "$n" ] || n=$n_mem
    [ "$n" -ge 1 ] || n=1
    cpus_p=$((cpu / n - CPUS_BASE)); [ "$cpus_p" -ge 1 ] || cpus_p=1   # les processeurs du moteur partagés entre les places, la base de chaque place déduite
  else
    n=1
  fi
  pr_p=$((cpus_p + CPUS_BASE))   # processeurs d'une place de preuve : ceux du passage + la base (3 + 1 sur 8 processeurs)
  donnees=$(donnees_places) || donnees=""
  if [ -n "$donnees" ]; then
    for p in "$donnees"/ci/places/*/; do
      [ -f "$p/pid" ] || continue
      pid=$(cat "$p/pid" 2>/dev/null)
      if entier "$pid" && kill -0 "$pid" 2>/dev/null; then
        tenues=$((tenues + 1))
        proc_p=$(processeurs_de_place "${p%/}" "$pr_p"); mem_p=$(memoire_de_place "${p%/}"); cs_p=$(cat "$p/cpuset" 2>/dev/null)
        ut_c=$((ut_c + proc_p)); ut_m=$((ut_m + mem_p))
        entree=$(printf '{"type":"%s","processeurs":%s,"memoire_mio":%s,"cpuset":"%s"}' "$(type_de_place "${p%/}")" "$proc_p" "$mem_p" "$cs_p")
        detenues="${detenues:+$detenues,}$entree"
      fi
    done
    for f in "$donnees"/ci/file/*; do
      if [ -f "$f" ]; then file=$((file + 1)); fi
    done
  fi
  if [ -n "$cpu" ] && [ -n "$mem_mio" ]; then   # combien de places ciblées tiennent encore dans le budget (processeurs et mémoire)
    libres_c=$(((cpu - ut_c) / CPUS_CIBLEE)); [ "$libres_c" -ge 0 ] || libres_c=0
    if [ "$mem_mio" -gt "$RESERVE_MIO" ]; then libres_m=$(((mem_mio - RESERVE_MIO - ut_m) / MEMOIRE_CIBLEE_MIO)); else libres_m=0; fi
    [ "$libres_m" -ge 0 ] || libres_m=0
    libres_ciblees=$libres_c; [ "$libres_m" -ge "$libres_ciblees" ] || libres_ciblees=$libres_m
  fi
  printf '{"places":%s,"processeurs":%s,"memoire_mio":%s,"cpus_passage":%s,"memoire_passage_mio":%s,"cpus_base":%s,"memoire_base_mio":%s,"reserve_mio":%s,"preuve":{"processeurs":%s,"memoire_mio":%s},"ciblee":{"processeurs":%s,"memoire_mio":%s},"detenues":[%s],"libres_ciblees":%s,"tenues":%s,"file":%s}\n' \
    "$n" "$(valeur_json "$cpu")" "$(valeur_json "$mem_mio")" "$cpus_p" "$MEMOIRE_MIO" "$CPUS_BASE" "$MEMOIRE_BASE_MIO" "$RESERVE_MIO" \
    "$pr_p" "$((MEMOIRE_MIO + MEMOIRE_BASE_MIO))" "$CPUS_CIBLEE" "$MEMOIRE_CIBLEE_MIO" "$detenues" "$libres_ciblees" "$tenues" "$file"
}
cpus_de_json() { # <json> : pose CPUS d'après le champ cpus_passage (calculé par places_calculees) ; un champ illisible laisse la graine
  local c
  c=$(champ_json "$1" cpus_passage)
  if entier "$c" && [ "$c" -ge 1 ]; then CPUS=$c; fi
}
ligne_places() { # <json> : « places : <N> (processeurs <c>, mémoire <m> Mio) », formatée depuis le JSON seulement
  local c m
  c=$(champ_json "$1" processeurs); m=$(champ_json "$1" memoire_mio)
  if [ "$c" = null ]; then c="non lus"; fi
  if [ "$m" = null ]; then m="non lue"; else m="$m Mio"; fi
  printf 'places : %s (processeurs %s, mémoire %s)' "$(champ_json "$1" places)" "$c" "$m"
}
places_afficher() {
  local j
  j=$(places_calculees)
  if [ "$PLACES_JSON" -eq 1 ]; then printf '%s\n' "$j"; return 0; fi
  dire "$(ligne_places "$j")"
  dire "places tenues : $(champ_json "$j" tenues), en file : $(champ_json "$j" file)"
}

# --- places tenues et file d'attente (change ci-local-runner, tranche 1, D3 ; R-20261101-76 et -78) ---------------------------------------
# Remplace : rien (la tranche 0 lisait seulement). Retrait : permanent, tant que la CI est le lanceur.
# Une place est un dossier ci/places/<k> du dossier de données (pid et début dedans) ; la file est un fichier par passage en attente dans
# ci/file/, dont le nom donne le rang : « 0 » pour le passage qui porte le jeton vivant du verrou de fin (il passe devant, jamais dans une
# place tenue), « 1 » sinon, puis un compteur (ordre de création). Places et file ne changent que sous un verrou mkdir (ci/verrou-places).
# Aucune borne de temps et aucun refus ; un pid mort perd sa place ou son ticket. Sans dossier de données : pas de file (rien n'est écrit).
DONNEES_CI=""; PLACE=""; TICKET=""; VERROU_PLACES_PRIS=0; POS=0; TENUES=0
donnees_places() { # le dossier de données, ou rien (passage de test sans dossier de données : ni place ni file)
  if [ -n "${CI_LOCAL_DOCKER:-}" ] && [ -z "${PMZILLA_LAB_DATA:-}" ]; then return 0; fi
  dossier_donnees
}
pid_vivant() { local pid; pid=$(cat "$1" 2>/dev/null); entier "$pid" && kill -0 "$pid" 2>/dev/null; }
place_tenue() { # <dossier de place> : pid vivant, ou dossier créé il y a moins d'une minute (pid pas encore écrit)
  if [ -f "$1/pid" ]; then pid_vivant "$1/pid"; else [ -z "$(find "$1" -maxdepth 0 -mmin +1 2>/dev/null)" ]; fi
}
verrouiller_places() { # verrou mkdir : 100 essais de 0,1 s ; un verrou de plus d'une minute est celui d'un passage mort
  local i=0 verrou="$DONNEES_CI/ci/verrou-places"
  [ -z "$(find "$verrou" -maxdepth 0 -mmin +1 2>/dev/null)" ] || rmdir "$verrou" 2>/dev/null
  while ! mkdir "$verrou" 2>/dev/null; do
    i=$((i + 1)); [ "$i" -lt 100 ] || return 1
    sleep 0.1
  done
  VERROU_PLACES_PRIS=1
}
deverrouiller_places() { [ "$VERROU_PLACES_PRIS" -eq 1 ] || return 0; rmdir "$DONNEES_CI/ci/verrou-places" 2>/dev/null; VERROU_PLACES_PRIS=0; }
porte_jeton_vivant() { # vrai quand FINISH_LOCK_TOKEN est le jeton du verrou de fin vivant (même contrôle que verifier_verrou)
  local dossier="$COMMUN/pmzilla-fin-en-cours"
  [ -n "${FINISH_LOCK_TOKEN:-}" ] && [ -n "$COMMUN" ] && [ -d "$dossier" ] || return 1
  if _fl_stale "$dossier"; then return 1; fi
  [ "$(cat "$dossier/jeton" 2>/dev/null)" = "$FINISH_LOCK_TOKEN" ]
}
purger_places() { # sous verrou : retire les places et les tickets des processus morts
  local p f
  for p in "$DONNEES_CI"/ci/places/*/; do
    [ -d "$p" ] || continue
    place_tenue "${p%/}" || rm -rf "${p%/}"
  done
  for f in "$DONNEES_CI"/ci/file/*; do
    [ -f "$f" ] || continue
    pid_vivant "$f" || rm -f "$f"
  done
}
etat_places() { # <ticket> : POS (rang du ticket dans la file, 0 s'il n'y est plus) et TENUES (places tenues), sous verrou
  local f n=0
  POS=0; TENUES=0
  for f in "$DONNEES_CI"/ci/places/*/; do [ -d "$f" ] && TENUES=$((TENUES + 1)); done
  for f in $(ls "$DONNEES_CI/ci/file" 2>/dev/null | LC_ALL=C sort); do
    n=$((n + 1))
    if [ "$f" = "$1" ]; then POS=$n; break; fi
  done
}
creer_ticket() { # <rang 0|1> : TICKET, sous verrou
  local c=0 f="$DONNEES_CI/ci/compteur"
  [ -f "$f" ] && c=$(cat "$f" 2>/dev/null)
  entier "$c" || c=0
  c=$((c + 1))
  echo "$c" > "$f" || return 1
  TICKET=$(printf '%s-%012d-%s' "$1" "$c" "$$")
  echo "$$" > "$DONNEES_CI/ci/file/$TICKET" || { TICKET=""; return 1; }
}
TYPE_PLACE=preuve; CPUSET=""
# T2 (D5) : une place a un type (preuve : processeurs du passage + base ; ciblee : CPUS_CIBLEE, sans base). Elle est accordée seulement si le
# budget du moteur (processeurs et mémoire, moins la réserve) laisse la place de son type, les places tenues comptées. Une place tenue ou sans
# type compte comme une preuve. Moteur illisible : l'ancienne règle (tenues < N). Rien n'est tenu : la première place est toujours accordée.
# Remplace : « tenues < N » pour des places toutes pareilles (ci-local-runner D3). Retrait : permanent, tant que le budget est celui du moteur.
besoin_de_place() { # <json> : « processeurs mémoire » demandés par TYPE_PLACE
  if [ "$TYPE_PLACE" = ciblee ]; then printf '%s %s' "$CPUS_CIBLEE" "$MEMOIRE_CIBLEE_MIO"
  else printf '%s %s' "$((CPUS + CPUS_BASE))" "$((MEMOIRE_MIO + MEMOIRE_BASE_MIO))"; fi
}
place_libre() { # <json> : sous verrou ; 0 quand le budget laisse la place de TYPE_PLACE
  local cpu mem n req_c req_m p ut_c=0 ut_m=0
  cpu=$(champ_json "$1" processeurs); mem=$(champ_json "$1" memoire_mio); n=$(champ_json "$1" places)
  if ! entier "$cpu" || ! entier "$mem"; then entier "$n" || n=1; [ "$TENUES" -lt "$n" ]; return; fi
  [ "$TENUES" -gt 0 ] || return 0
  read -r req_c req_m <<< "$(besoin_de_place "$1")"
  for p in "$DONNEES_CI"/ci/places/*/; do
    [ -d "$p" ] || continue
    ut_c=$((ut_c + $(processeurs_de_place "${p%/}" $((CPUS + CPUS_BASE))))); ut_m=$((ut_m + $(memoire_de_place "${p%/}")))
  done
  [ $((cpu - ut_c)) -ge "$req_c" ] && [ $((mem - RESERVE_MIO - ut_m)) -ge "$req_m" ]
}
choisir_cpuset() { # <json> <nombre> : les premiers processeurs que ne tient aucune autre place, « a,b,c » ; vide quand le moteur est illisible
  local cpu p i=0 n=0 pris="," sortie=""
  cpu=$(champ_json "$1" processeurs); entier "$cpu" || return 0
  for p in "$DONNEES_CI"/ci/places/*/; do [ -f "$p/cpuset" ] && pris="$pris$(cat "$p/cpuset" 2>/dev/null),"; done
  while [ "$i" -lt "$cpu" ] && [ "$n" -lt "$2" ]; do
    case "$pris" in *",$i,"*) ;; *) sortie="${sortie:+$sortie,}$i"; n=$((n + 1)) ;; esac
    i=$((i + 1))
  done
  printf '%s' "$sortie"
}
# Design D18 point 4 (autonomous-trains-merge) : un passage de rang 1 ne prend aucune place tant qu'une place marquée « train » a un pid vivant.
# Remplace : rien (le train passait seulement en tête de file, sans fermer les places libres aux autres). Retrait : permanent, avec le gel ciblé.
place_du_train_tenue() { # sous verrou : vrai quand une place du train est tenue par un processus vivant
  local p
  for p in "$DONNEES_CI"/ci/places/*/; do
    [ -f "$p/train" ] && pid_vivant "$p/pid" && return 0
  done
  return 1
}
prendre_place() { # <json> : la première place libre, sous verrou ; PLACE, CPUSET (son type et son jeu de processeurs sont notés dans son dossier)
  local k=1 req_c req_m
  while [ "$k" -le 16 ]; do
    if mkdir "$DONNEES_CI/ci/places/$k" 2>/dev/null; then
      echo "$$" > "$DONNEES_CI/ci/places/$k/pid"; date +%s > "$DONNEES_CI/ci/places/$k/debut"
      printf '%s' "$TYPE_PLACE" > "$DONNEES_CI/ci/places/$k/type"
      [ "${PRIO_PLACE:-1}" -ne 0 ] || : > "$DONNEES_CI/ci/places/$k/train"   # place du train : aucune place ne s'ouvre hors du train tant qu'elle est tenue
      read -r req_c req_m <<< "$(besoin_de_place "$1")"
      CPUSET=$(choisir_cpuset "$1" "$req_c")
      [ -z "$CPUSET" ] || printf '%s' "$CPUSET" > "$DONNEES_CI/ci/places/$k/cpuset"
      PLACE=$k; return 0
    fi
    k=$((k + 1))
  done
  return 1
}
attendre_place() { # <json des places> [<type : preuve|ciblee>] : tient une place avant tout conteneur ; remplit PLACE, CPUSET et ATTENTE_S
  # R-20261101-120 : l'attente se compte à partir du premier sommeil de la boucle (le passage qui trouve une place libre attend 0 s), non depuis
  # l'entrée : la résolution des dossiers du lab et la prise du verrou durent une fraction de seconde, que SECONDS (entier) arrondit parfois à 1.
  # Remplace : debut_s pris à l'entrée. Retrait : permanent.
  local n prio=1 affiche="" ligne debut_s=""
  TYPE_PLACE=${2:-preuve}
  DONNEES_CI=$(donnees_places) || DONNEES_CI=""
  [ -n "$DONNEES_CI" ] || return 0
  n=$(champ_json "$1" places); entier "$n" || n=1
  if porte_jeton_vivant; then prio=0; fi
  PRIO_PLACE=$prio
  if ! ( umask 077; mkdir -p "$DONNEES_CI/ci/places" "$DONNEES_CI/ci/file" ) 2>/dev/null; then
    dire "places indisponibles (écriture impossible), départ sans place"; DONNEES_CI=""; return 0
  fi
  while :; do
    if verrouiller_places; then
      ( umask 077; mkdir -p "$DONNEES_CI/ci/places" "$DONNEES_CI/ci/file" ) 2>/dev/null   # un passage qui finit retire les dossiers vides : sous le verrou, on les recrée
      purger_places
      if [ -z "$TICKET" ] && ! creer_ticket "$prio"; then
        deverrouiller_places; dire "file indisponible (écriture impossible), départ sans place"; DONNEES_CI=""; return 0
      fi
      etat_places "$TICKET"
      [ "$POS" -gt 0 ] || TICKET=""   # ticket disparu : il sera recréé au tour suivant
      if [ "$POS" -eq 1 ] && { [ "$prio" -eq 0 ] || ! place_du_train_tenue; } && place_libre "$1" && prendre_place "$1"; then
        rm -f "$DONNEES_CI/ci/file/$TICKET"; TICKET=""
        deverrouiller_places
        break
      fi
      deverrouiller_places
    fi
    if [ "$POS" -gt 0 ]; then
      ligne="en file (position $POS, $TENUES passage(s) en cours sur $n places)"
      if [ "$ligne" != "$affiche" ]; then dire "$ligne"; affiche=$ligne; fi
    fi
    [ -n "$debut_s" ] || debut_s=$SECONDS
    sleep 1
  done
  if [ -n "$debut_s" ]; then ATTENTE_S=$((SECONDS - debut_s)); else ATTENTE_S=0; fi
  if [ -n "$affiche" ]; then dire "place $PLACE prise, départ"; fi
  return 0
}
liberer_place() { # rend la place et le ticket (idempotent : fin normale, échec, INT/TERM)
  deverrouiller_places
  if [ -n "$DONNEES_CI" ]; then
    [ -z "$TICKET" ] || rm -f "$DONNEES_CI/ci/file/$TICKET"
    [ -z "$PLACE" ] || rm -rf "$DONNEES_CI/ci/places/$PLACE"
    rmdir "$DONNEES_CI/ci/places" "$DONNEES_CI/ci/file" 2>/dev/null   # dossiers vides retirés : places n'en voit aucun tant que rien n'est tenu ni attendu
  fi
  TICKET=""; PLACE=""
  return 0
}

# --- nettoyage des images périmées après une construction de up (change ci-local-image-prune, D1 à D3, D7 ; R-20261106-55, -56) ------------------
# Une clé d'image est « ouverte » quand elle est celle de l'arbre d'une branche locale (main comprise) ou du HEAD d'un worktree (détaché compris) ;
# toute autre image « pmzilla-ci:<clé> » est périmée. Jamais d'autre dépôt (l'image de la base), de volume, de conteneur, de prune ni de --force.
# Remplace : rien. Retrait : avec cles_ouvertes.
cle_valide() { case "$1" in ""|*[!0123456789abcdef]*) return 1 ;; esac; [ "${#1}" -eq 64 ]; }
# Remplace : rien (la liste de ce qu'on garde se calculait à la main). Retrait : permanent, tant qu'une image est étiquetée par la clé d'un arbre.
# Une clé par ligne, retour 1 au moindre doute : un commit illisible (arbre introuvable) ou une clé qui n'a pas 64 hexadécimaux. Sans extraction ni
# construction : cles lit le commit. Appelée dans un sous-shell ($(...)), elle ne change ni CLE ni CLE_BASE du script.
cles_ouvertes() {
  local c refs tetes
  refs=$(git for-each-ref --format='%(objectname)' refs/heads/) || return 1
  [ -n "$refs" ] || return 1   # aucune branche locale lue : un doute, jamais « rien n'est ouvert »
  tetes=$(git worktree list --porcelain) || return 1
  for c in $( { printf '%s\n' "$refs"; printf '%s\n' "$tetes" | sed -n 's/^HEAD //p'; } | LC_ALL=C sort -u ); do
    git cat-file -e "$c^{tree}" 2>/dev/null || return 1
    cles "$c"
    cle_valide "$CLE" || return 1
    printf '%s\n' "$CLE"
  done
}
# Remplace : rien. Retrait : avec cles_ouvertes. <clés ouvertes, une par ligne> <étiquettes listées, une par ligne> : imprime les clés à retirer ;
# une étiquette qui n'est pas de 64 hexadécimaux (<none> comprise) ou dont la clé est ouverte est gardée.
images_a_supprimer() {
  local t
  while IFS= read -r t; do
    cle_valide "$t" || continue
    case $'\n'"$1"$'\n' in *$'\n'"$t"$'\n'*) continue ;; esac
    printf '%s\n' "$t"
  done <<< "$2"
}
# Remplace : rien. Retrait : avec nettoyer_images.
images_non_nettoyees() { dire "images non nettoyées ($1)"; }
# Remplace : le retrait à la main des images (2026-11-06). Retrait : permanent, tant que la CI construit une image par clé (chaque changement de clé laisse
# la précédente et rien d'autre ne la retire). Les contrôles d'abstention appellent _fl_stale, place_tenue et pid_vivant, les sources de run : aucune copie.
# Appelée par up après une construction seulement (jamais par build) ; ne change jamais le code de up. Abstentions, dans l'ordre : verrou de fin tenu,
# dossier de données introuvable, places indisponibles, preuve en cours, clé non calculée, liste illisible. Le verrou des places est tenu jusqu'au dernier
# retrait (aucun passage ne prend de place pendant ce temps : un passage en attente réessaie).
nettoyer_images() { # <clé qui vient d'être construite>
  local construite=$1 verrou_fin="$COMMUN/pmzilla-fin-en-cours" ouvertes etiquettes a_retirer k p f total retirees=0 st_cles=0 st_liste=0
  [ -n "$COMMUN" ] || { images_non_nettoyees "clé d'une branche non calculée"; return 0; }   # dossier Git commun illisible : un doute
  if [ -d "$verrou_fin" ] && ! _fl_stale "$verrou_fin"; then images_non_nettoyees "verrou de fin tenu"; return 0; fi
  DONNEES_CI=$(donnees_places) || DONNEES_CI=""
  if [ -z "$DONNEES_CI" ]; then images_non_nettoyees "dossier de données introuvable"; return 0; fi
  # Clés ouvertes et liste des images calculées AVANT le verrou des places (réputé mort au bout d'une minute : rien de long dessous) ; leur statut
  # est gardé et dit sous le verrou, dans l'ordre de D3, après les contrôles de preuve.
  ouvertes=$(cles_ouvertes) || st_cles=1
  etiquettes=$("$DOCKER" images --filter "reference=$IMAGE_NOM" --format '{{.Tag}}' 2>/dev/null) || st_liste=1
  trap 'deverrouiller_places; exit 130' INT
  trap 'deverrouiller_places; exit 143' TERM
  if ! ( umask 077; mkdir -p "$DONNEES_CI/ci" ) 2>/dev/null || ! verrouiller_places; then
    trap - INT TERM; DONNEES_CI=""; images_non_nettoyees "places indisponibles"; return 0
  fi
  for p in "$DONNEES_CI"/ci/places/*/; do
    if [ -d "$p" ] && place_tenue "${p%/}"; then
      deverrouiller_places; trap - INT TERM; DONNEES_CI=""; images_non_nettoyees "preuve en cours"; return 0
    fi
  done
  for f in "$DONNEES_CI"/ci/file/*; do
    if [ -f "$f" ] && pid_vivant "$f"; then
      deverrouiller_places; trap - INT TERM; DONNEES_CI=""; images_non_nettoyees "preuve en cours"; return 0
    fi
  done
  if [ "$st_cles" -ne 0 ]; then
    deverrouiller_places; trap - INT TERM; DONNEES_CI=""; images_non_nettoyees "clé d'une branche non calculée"; return 0
  fi
  if [ "$st_liste" -ne 0 ]; then
    deverrouiller_places; trap - INT TERM; DONNEES_CI=""; images_non_nettoyees "liste des images illisible"; return 0
  fi
  ouvertes=$(printf '%s\n%s\n' "$ouvertes" "$construite")
  a_retirer=$(images_a_supprimer "$ouvertes" "$etiquettes")
  total=$(printf '%s\n' "$etiquettes" | grep -c . || true)
  for k in $a_retirer; do
    if "$DOCKER" image rm "$IMAGE_NOM:$k" >/dev/null 2>&1; then
      retirees=$((retirees + 1)); dire "image supprimée (clé ${k:0:12})"
    else
      dire "image gardée (clé ${k:0:12}) : suppression refusée par Docker"
    fi
  done
  deverrouiller_places; trap - INT TERM; DONNEES_CI=""
  dire "nettoyage des images : $retirees supprimée(s), $((total - retirees)) gardée(s)"
  return 0
}

# --- verdict enregistré (D7b) ------------------------------------------------------------------------------------------------------
REGISTRE=1; FICHIER_VERDICTS=""; RAISON_REGISTRE=""
preparer_registre() {
  if [ -n "${CI_LOCAL_DOCKER:-}" ] && [ -z "${CI_LOCAL_VERDICTS:-}" ]; then REGISTRE=0; return 0; fi
  if [ -n "${CI_LOCAL_VERDICTS:-}" ]; then
    FICHIER_VERDICTS=$CI_LOCAL_VERDICTS
  else
    local donnees
    donnees=$(dossier_donnees) && [ -n "$donnees" ] || { RAISON_REGISTRE="dossier de données introuvable"; return 0; }
    ( umask 077; mkdir -p "$donnees/ci" ) 2>/dev/null
    FICHIER_VERDICTS="$donnees/ci/verdicts"
  fi
  # Écritures concurrentes (deux passages en même temps) : un verrou par mkdir à côté du fichier, repris au bout d'une minute (passage mort).
  # La ligne de l'arbre testé disparaît dès le départ : un passage interrompu ne laisse aucun verdict pour cet arbre. Un retrait manqué
  # (verrou, écriture ou renommage en échec) laisserait un verdict périmé : la raison « écriture impossible » est posée et dite tout de suite.
  if [ -f "$FICHIER_VERDICTS" ] && grep -q "^$ARBRE$TAB" "$FICHIER_VERDICTS" 2>/dev/null; then
    if verrouiller_verdicts \
       && ( umask 077; grep -v "^$ARBRE$TAB" "$FICHIER_VERDICTS" > "$FICHIER_VERDICTS.tmp.$$"; [ $? -le 1 ] ) 2>/dev/null \
       && mv "$FICHIER_VERDICTS.tmp.$$" "$FICHIER_VERDICTS" 2>/dev/null; then
      deverrouiller_verdicts
    else
      rm -f "$FICHIER_VERDICTS.tmp.$$" 2>/dev/null
      deverrouiller_verdicts
      RAISON_REGISTRE="écriture impossible"
      dire "verdict précédent de cet arbre non retiré (écriture impossible)"
    fi
  fi
}
verrouiller_verdicts() { # verrou mkdir : 50 essais de 0,1 s ; un verrou de plus d'une minute est celui d'un passage mort
  local i=0 verrou="$FICHIER_VERDICTS.lock"
  [ -z "$(find "$verrou" -maxdepth 0 -mmin +1 2>/dev/null)" ] || rmdir "$verrou" 2>/dev/null
  while ! mkdir "$verrou" 2>/dev/null; do
    i=$((i + 1)); [ "$i" -lt 50 ] || return 1
    sleep 0.1
  done
  VERROU_PRIS=1
}
deverrouiller_verdicts() { [ "${VERROU_PRIS:-0}" -eq 1 ] || return 0; rmdir "$FICHIER_VERDICTS.lock" 2>/dev/null; VERROU_PRIS=0; }
enregistrer() { # <vert|rouge> : ligne de l'arbre testé, phrase juste avant le verdict
  [ "$REGISTRE" -eq 1 ] || return 0
  if [ -n "$RAISON_REGISTRE" ]; then dire "verdict non enregistré ($RAISON_REGISTRE)"; return 0; fi
  if verrouiller_verdicts \
     && ( umask 077
       { [ -f "$FICHIER_VERDICTS" ] && grep -v "^$ARBRE$TAB" "$FICHIER_VERDICTS"; printf '%s\t%s\t%s\n' "$ARBRE" "$1" "$CLE"; } \
         > "$FICHIER_VERDICTS.tmp.$$" ) 2>/dev/null \
     && chmod 600 "$FICHIER_VERDICTS.tmp.$$" 2>/dev/null && mv "$FICHIER_VERDICTS.tmp.$$" "$FICHIER_VERDICTS" 2>/dev/null; then
    deverrouiller_verdicts
    dire "verdict enregistré pour l'arbre ${ARBRE:0:12}"
  else
    rm -f "$FICHIER_VERDICTS.tmp.$$" 2>/dev/null
    deverrouiller_verdicts
    dire "verdict non enregistré (écriture impossible)"
  fi
}

# --- rapport (D7) --------------------------------------------------------------------------------------------------------------------
LIGNES_PHASES=""; LIGNE_MEMOIRE=""; LIGNE_PLACES=""; LIGNE_BASE_MAC=""; ATTENTE_S=0   # posées par passage ; l'attente est celle de attendre_place (0 sans file)
ecrire_rapport() { # <sortie du lanceur> <code> <début> <ligne TOTAL> <ligne Mac> <ligne « Tests sautés »>
  local sortie=$1 code=$2 debut=$3 total=$4 saut=$5 sautes=${6:-} donnees fichier liste fichier_sortie ligne_sortie
  if [ -n "${CI_LOCAL_DOCKER:-}" ] && [ -z "${PMZILLA_LAB_DATA:-}" ]; then
    dire "rapport non écrit (passage de test sans dossier de données)"; return 0
  fi
  donnees=$(dossier_donnees) && [ -n "$donnees" ] || { dire "rapport non écrit (dossier de données introuvable)"; return 0; }
  fichier="$donnees/ci/rapport-$(date '+%Y%m%d-%H%M%S')-${ARBRE:0:12}.txt"
  liste=$(printf '%s' "$saut" | sed -n 's/^run_all : suites propres au Mac non lancées : [0-9]* (\(.*\))$/\1/p')
  # R-20261101-128. Remplace : le rapport réduit aux lignes « tests · » comme seule trace d'un passage rouge (le détail d'un échec n'existait
  # que dans le terminal). Retrait : permanent tant que le passage tourne dans un conteneur jetable. Rétention : celle des rapports (aucun
  # nettoyage n'existe aujourd'hui ; le jour où il en existe un, il vaut pour les deux fichiers, qui portent le même nom). La sortie complète
  # est celle que le conteneur écrit sur sa sortie standard (sortie gardée des suites rouges du lanceur comprise), écrite AVANT le rapport.
  fichier_sortie="${fichier%.txt}-sortie.txt"
  if ( umask 077; mkdir -p "$donnees/ci" && cat "$sortie" > "$fichier_sortie" ) 2>/dev/null && chmod 600 "$fichier_sortie" 2>/dev/null; then
    ligne_sortie="sortie complète : $(basename "$fichier_sortie") (même dossier que ce rapport)"
  else
    rm -f "$fichier_sortie" 2>/dev/null
    ligne_sortie="sortie complète : non écrite"
    dire "sortie complète non écrite (écriture impossible)"
  fi
  if ( umask 077; mkdir -p "$donnees/ci" && {
         echo "arbre : $ARBRE"
         echo "image : $CLE"
         echo "début : $debut"
         echo "code : $code"
         echo "suites Mac non lancées : ${liste:-aucune ligne du lanceur}"
         echo "$ligne_sortie"
         echo "--- lanceur"
         grep -a ' tests · ' "$sortie" | sed 's/\(ÉCHEC (code [0-9]*)\) : .* · /\1 · /'
         [ -z "$sautes" ] || echo "$sautes"
         [ -z "$saut" ] || echo "$saut"
         [ -z "$total" ] || echo "$total"
         # D5 : phases, mémoire, places, attente (aucun chemin, aucune branche, aucune personne)
         echo "--- passage"
         [ -z "$LIGNES_PHASES" ] || printf '%s\n' "$LIGNES_PHASES"
         [ -z "$LIGNE_BASE_MAC" ] || echo "$LIGNE_BASE_MAC"
         [ -z "$LIGNE_MEMOIRE" ] || echo "$LIGNE_MEMOIRE"
         [ -z "$LIGNE_PLACES" ] || echo "$LIGNE_PLACES"
         echo "attente en file : $ATTENTE_S s"
       } > "$fichier" ) 2>/dev/null; then
    dire "rapport écrit ($(basename "$fichier"))"
  else
    rm -f "$fichier" 2>/dev/null
    dire "rapport non écrit (écriture impossible)"
  fi
}

# --- passage (D1 run, D5 à D7b) --------------------------------------------------------------------------------------------------------
NOM_CONTENEUR=""; NOM_BASE=""; SORTIE=""; MDP_BASE=""; IMAGE_BASE=""
OPT_CPUSET_BASE=(); OPT_CPUSET_SUITES=()
# Jeux de processeurs de la place prise (T2, D5) : --cpuset-cpus disjoint de ceux des autres places tenues, lus du moteur. Une place de preuve en a 4,
# le dernier va à la base et les autres aux suites ; une place ciblée n'a que des suites. Sans jeu (moteur illisible, pas de dossier de données) : aucune option.
regler_cpuset() { # <avec base : 1|0>
  OPT_CPUSET_BASE=(); OPT_CPUSET_SUITES=()
  [ -n "$CPUSET" ] || return 0
  if [ "$1" -eq 1 ] && [ "$CPUSET" != "${CPUSET%,*}" ]; then
    OPT_CPUSET_BASE=(--cpuset-cpus "${CPUSET##*,}"); OPT_CPUSET_SUITES=(--cpuset-cpus "${CPUSET%,*}")
  elif [ "$1" -eq 1 ]; then
    OPT_CPUSET_SUITES=(--cpuset-cpus "$CPUSET")
  else
    OPT_CPUSET_SUITES=(--cpuset-cpus "$CPUSET")
  fi
}
# Chemin du fichier d'environnement de la base (mot de passe tiré au hasard), visible de retirer_conteneur : appelée par interrompu (INT/TERM),
# par le trap EXIT et par l'échec de demarrer_base, elle le supprime aussi si l'interruption tombe pendant « docker create ».
# Remplace : la variable locale « fenv » de demarrer_base, que l'interruption laissait en place (revue 4.1, écart 2 ; R-20261105-12).
# Retrait : permanent, tant que la base du passage reçoit son mot de passe par un fichier d'environnement.
FENV_BASE=""
retirer_conteneur() { # les suites d'abord, puis la base (et son volume anonyme) ; idempotent
  [ -z "$NOM_CONTENEUR" ] || "$DOCKER" rm -f "$NOM_CONTENEUR" >/dev/null 2>&1
  [ -z "$NOM_BASE" ] || "$DOCKER" rm -f -v "$NOM_BASE" >/dev/null 2>&1
  [ -z "$FENV_BASE" ] || rm -f "$FENV_BASE" 2>/dev/null
  NOM_CONTENEUR=""; NOM_BASE=""; FENV_BASE=""
  return 0
}
# Image de la base : la ligne « image: » du docker-compose.yml de l'arbre prouvé (lu par git show sur $COMMIT, jamais dans le dépôt de ce script
# ni dans le dossier courant) ; aucun repli : fichier ou ligne illisibles, code 4. Jamais construite ni tirée ici (l'auteur seul, D11) : absente,
# code 5. Remplace : la lecture dans le dépôt du script ($ICI/../docker-compose.yml). Retrait : permanent (la base d'un passage doit être celle
# de l'arbre qu'il prouve), tant que la base du passage est lancée par ce script.
verifier_image_base() {
  IMAGE_BASE=$(fichier_de "$COMMIT" docker-compose.yml | grep -E '^[[:space:]]+image:' | head -1 | sed -E 's/^[[:space:]]+image:[[:space:]]*//; s/["[:space:]]//g')
  case "$IMAGE_BASE" in
    */*:[0-9]*) ;;
    *) refus 4 "image de la base introuvable (docker-compose.yml) ; rien n'est lancé" ;;
  esac
  "$DOCKER" image inspect "$IMAGE_BASE" >/dev/null 2>&1 || refus 5 "image de la base absente (à tirer par l'auteur)"
}
demarrer_base() { # la base jetable du passage : créée (mot de passe par un fichier d'environnement propriétaire seul, retiré aussitôt), puis démarrée
  local fenv rc
  MDP_BASE=$(od -An -N16 -tx1 /dev/urandom 2>/dev/null | tr -d ' \n')
  [ -n "$MDP_BASE" ] || return 1
  fenv=$(mktemp "${TMPDIR:-/tmp}/ci_local_base.XXXXXX") || return 1
  FENV_BASE=$fenv   # visible de retirer_conteneur dès la création du fichier (voir FENV_BASE)
  # Port par PGPORT (le serveur temporaire d'initialisation de l'image le respecte aussi) ; label pour balayer les restes (comme dbtest).
  { printf 'POSTGRES_PASSWORD=%s\n' "$MDP_BASE"; printf 'POSTGRES_DB=pmzilla\n'; printf 'PGPORT=%s\n' "$PORT_BASE"
    # Sans méthode d'authentification, initdb écrit « trust » pour le socket local et 127.0.0.1 (les suites atteignent la base par 127.0.0.1 via --network container:) : scram partout.
    printf 'POSTGRES_INITDB_ARGS=%s\n' "--auth-host=scram-sha-256 --auth-local=scram-sha-256"; } > "$fenv" 2>/dev/null
  "$DOCKER" create --name "$NOM_BASE" --label pmzilla-lab-ci=1 --network none --env-file "$fenv" --tmpfs /var/lib/postgresql --shm-size 1g \
      --cpus "$CPUS_BASE" ${OPT_CPUSET_BASE[@]+"${OPT_CPUSET_BASE[@]}"} --memory "${MEMOIRE_BASE_MIO}m" "$IMAGE_BASE" >/dev/null 2>&1
  rc=$?
  rm -f "$fenv"; FENV_BASE=""
  [ "$rc" -eq 0 ] || return 1
  "$DOCKER" start "$NOM_BASE" >/dev/null 2>&1
}
interrompu() {
  trap '' INT TERM
  retirer_conteneur
  liberer_place
  [ -n "$SORTIE" ] && rm -f "$SORTIE"
  dire "passage interrompu ; conteneur retiré, aucun verdict enregistré"
  exit "$1"
}

# Script lancé dans le conteneur : ci/passage.sh (D2), lu ici à chaque passage (archive extraite, recommitée, phases). Il vient du dépôt
# de ce script, non de l'arbre testé : un passage sur une branche plus ancienne le trouve quand même, et l'image ne change pas.
PASSAGE_SH="$ICI/../ci/passage.sh"
# Étapes de la passe de bout en bout (tranche 2, R-20261101-113) : tools/e2e_steps.sh du dépôt de CET outil, concaténé devant passage.sh, jamais lu dans
# l'arbre testé (R-94 : un arbre ne fournit pas le code qui le juge). Remplace : rien. Retrait : permanent, tant que la phase e2e est dans le conteneur.
E2E_STEPS_SH="$ICI/e2e_steps.sh"

# --- preuve enregistrée (D6, tranche 2, tâche 9.4) -------------------------------------------------------------------------------------
# Un passage dont toutes les phases sont vertes, e2e comprise, écrit <arbre><TAB><clé d'image><TAB><phases> dans ci/preuves du dossier de données.
# Écriture comme celle des verdicts (modèle : preparer_registre et enregistrer ci-dessus) : verrou mkdir, ligne retirée au départ, fichier temporaire
# renommé, propriétaire seul. Remplace : rien (le fichier des verdicts garde son format de trois champs pour ses lecteurs). Retrait : permanent ;
# les fonctions des verdicts tombent avec B9 (design D6), celles-ci restent. Un seul nom de fichier pour les tests : CI_LOCAL_PREUVES.
PREUVES=1; FICHIER_PREUVES=""; RAISON_PREUVE=""; VERROU_PREUVES_PRIS=0
verrouiller_preuves() { # verrou mkdir : 50 essais de 0,1 s ; un verrou de plus d'une minute est celui d'un passage mort
  local i=0 verrou="$FICHIER_PREUVES.lock"
  [ -z "$(find "$verrou" -maxdepth 0 -mmin +1 2>/dev/null)" ] || rmdir "$verrou" 2>/dev/null
  while ! mkdir "$verrou" 2>/dev/null; do
    i=$((i + 1)); [ "$i" -lt 50 ] || return 1
    sleep 0.1
  done
  VERROU_PREUVES_PRIS=1
}
deverrouiller_preuves() { [ "$VERROU_PREUVES_PRIS" -eq 1 ] || return 0; rmdir "$FICHIER_PREUVES.lock" 2>/dev/null; VERROU_PREUVES_PRIS=0; }
preparer_preuves() { # après les refus 2 à 8, avant le conteneur : la ligne de l'arbre testé disparaît
  if [ -n "${CI_LOCAL_DOCKER:-}" ] && [ -z "${CI_LOCAL_PREUVES:-}" ]; then PREUVES=0; return 0; fi
  if [ -n "${CI_LOCAL_PREUVES:-}" ]; then
    FICHIER_PREUVES=$CI_LOCAL_PREUVES
  else
    local donnees
    donnees=$(dossier_donnees) && [ -n "$donnees" ] || { RAISON_PREUVE="dossier de données introuvable"; return 0; }
    ( umask 077; mkdir -p "$donnees/ci" ) 2>/dev/null
    FICHIER_PREUVES="$donnees/ci/preuves"
  fi
  if [ -f "$FICHIER_PREUVES" ] && grep -q "^$ARBRE$TAB" "$FICHIER_PREUVES" 2>/dev/null; then
    if verrouiller_preuves \
       && ( umask 077; grep -v "^$ARBRE$TAB" "$FICHIER_PREUVES" > "$FICHIER_PREUVES.tmp.$$"; [ $? -le 1 ] ) 2>/dev/null \
       && mv "$FICHIER_PREUVES.tmp.$$" "$FICHIER_PREUVES" 2>/dev/null; then
      deverrouiller_preuves
    else
      rm -f "$FICHIER_PREUVES.tmp.$$" 2>/dev/null
      deverrouiller_preuves
      RAISON_PREUVE="écriture impossible"
      dire "preuve précédente de cet arbre non retirée (écriture impossible)"
    fi
  fi
}
enregistrer_preuve() { # <phases, séparées par des virgules> : seulement appelée pour un passage vert avec les trois phases
  [ "$PREUVES" -eq 1 ] || return 0
  if [ -n "$RAISON_PREUVE" ]; then dire "preuve non enregistrée ($RAISON_PREUVE)"; return 0; fi
  if verrouiller_preuves \
     && ( umask 077
       { [ -f "$FICHIER_PREUVES" ] && grep -v "^$ARBRE$TAB" "$FICHIER_PREUVES"; printf '%s\t%s\t%s\n' "$ARBRE" "$CLE" "$1"; } \
         > "$FICHIER_PREUVES.tmp.$$" ) 2>/dev/null \
     && chmod 600 "$FICHIER_PREUVES.tmp.$$" 2>/dev/null && mv "$FICHIER_PREUVES.tmp.$$" "$FICHIER_PREUVES" 2>/dev/null; then
    deverrouiller_preuves
    dire "preuve enregistrée pour l'arbre ${ARBRE:0:12} (phases $1)"
  else
    rm -f "$FICHIER_PREUVES.tmp.$$" 2>/dev/null
    deverrouiller_preuves
    dire "preuve non enregistrée (écriture impossible)"
  fi
}

# --- preuve d'index (tooling-proof-in-container, T2, D1) ------------------------------------------------------------------------------
# Un passage --index VERT ajoute <arbre><TAB><clé d'image><TAB><suites séparées par des virgules, ou « complet »> à ci/preuves-index du dossier de
# données (CI_LOCAL_PREUVES_INDEX pour les tests ; avec CI_LOCAL_DOCKER posée sans lui, rien n'est lu ni écrit). Ni champ de verdict, ni branche, ni
# chemin, ni date : un rouge ou une interruption n'écrivent RIEN (le fichier ne garde que des preuves ; la sortie du passage est le diagnostic d'un rouge,
# R-20261104-7 P5 (iii)). Écriture comme celle des preuves : verrou mkdir, fichier temporaire renommé, propriétaire seul ; les 500 dernières lignes sont
# gardées. Lecteur : tools/preuve_arbre.py (index_proven), une seule fonction. Remplace : rien. Retrait : permanent, tant que le pre-commit exige un passage vert.
enregistrer_preuve_index() { # <suites séparées par des virgules, ou « complet »>
  local fichier donnees verrou i=0 ligne
  if [ -n "${CI_LOCAL_DOCKER:-}" ] && [ -z "${CI_LOCAL_PREUVES_INDEX:-}" ]; then return 0; fi
  if [ -n "${CI_LOCAL_PREUVES_INDEX:-}" ]; then
    fichier=$CI_LOCAL_PREUVES_INDEX
  else
    donnees=$(dossier_donnees) && [ -n "$donnees" ] || { dire "preuve d'index non enregistrée (dossier de données introuvable)"; return 0; }
    ( umask 077; mkdir -p "$donnees/ci" ) 2>/dev/null
    fichier="$donnees/ci/preuves-index"
  fi
  [ -d "$(dirname "$fichier")" ] || { dire "preuve d'index non enregistrée (écriture impossible)"; return 0; }
  ligne=$(printf '%s\t%s\t%s' "$ARBRE" "$CLE" "$1")
  verrou="$fichier.lock"
  [ -z "$(find "$verrou" -maxdepth 0 -mmin +1 2>/dev/null)" ] || rmdir "$verrou" 2>/dev/null
  while ! mkdir "$verrou" 2>/dev/null; do
    i=$((i + 1))
    if [ "$i" -ge 50 ]; then dire "preuve d'index non enregistrée (écriture impossible)"; return 0; fi
    sleep 0.1
  done
  if ( umask 077
       { [ -f "$fichier" ] && { grep -vxF -- "$ligne" "$fichier" | tail -n 499; }; printf '%s\n' "$ligne"; } > "$fichier.tmp.$$" ) 2>/dev/null \
     && chmod 600 "$fichier.tmp.$$" 2>/dev/null && mv "$fichier.tmp.$$" "$fichier" 2>/dev/null; then
    dire "preuve d'index enregistrée pour l'arbre ${ARBRE:0:12}"
  else
    rm -f "$fichier.tmp.$$" 2>/dev/null
    dire "preuve d'index non enregistrée (écriture impossible)"
  fi
  rmdir "$verrou" 2>/dev/null
  return 0
}

passage() { # <branche ou vide>
  local code debut total saut sautes n m echecs verdict interieur phases json echecs_ph
  resoudre_source "$1"
  cles "$COMMIT"
  docker_repond
  verifier_place_vm
  verifier_image
  [ -f "$PASSAGE_SH" ] || refus 4 "script intérieur introuvable (ci/passage.sh) ; rien n'est lancé"
  [ -f "$E2E_STEPS_SH" ] || refus 4 "script intérieur introuvable (tools/e2e_steps.sh) ; rien n'est lancé"
  verifier_image_base
  interieur=$(cat "$E2E_STEPS_SH" "$PASSAGE_SH")
  json=$(places_calculees)
  cpus_de_json "$json"
  trap 'interrompu 130' INT
  trap 'interrompu 143' TERM
  trap 'retirer_conteneur; liberer_place' EXIT   # aussi pour une mort autre que INT/TERM (HUP) : suites, base, puis place
  attendre_place "$json" preuve   # les codes 2 à 8 sont rendus avant ; ici la file, sans borne de temps
  regler_cpuset 1
  if [ -z "$MODE_ARBRE" ]; then   # T2 : un passage --index ou --travail n'écrit ni verdict ni preuve de commit (la preuve d'index est écrite à la fin)
    preparer_registre
    preparer_preuves
  fi
  NOM_CONTENEUR="pmzilla-ci-$(od -An -N6 -tx1 /dev/urandom 2>/dev/null | tr -d ' \n')"
  [ "$NOM_CONTENEUR" != "pmzilla-ci-" ] || NOM_CONTENEUR="pmzilla-ci-$$$(date +%s)"
  NOM_BASE="$NOM_CONTENEUR-base"
  SORTIE=$(mktemp "${TMPDIR:-/tmp}/ci_local.XXXXXX") || { echo "ci_local : fichier temporaire impossible" >&2; exit 1; }
  if ! demarrer_base; then
    MDP_BASE=""; retirer_conteneur; liberer_place; rm -f "$SORTIE"; SORTIE=""
    dire "base du conteneur non démarrée ; rien n'est lancé"
    exit 1
  fi
  debut=$(date '+%Y-%m-%d %H:%M:%S')
  # Le mot de passe de la base passe par l'environnement du seul processus docker (--env sans valeur), jamais en argument.
  # Le tube tourne en arrière-plan, puis « wait » : bash diffère un trap tant qu'une commande de premier plan tourne, alors qu'un « wait » interrompu par
  # INT/TERM laisse le trap (interrompu) s'exécuter tout de suite, qui retire le conteneur pendant qu'il tourne (revue 4.1, écart 1 ; R-20261105-12).
  # Le code est celui de docker (PIPESTATUS[1], comme avant), rendu par la sortie du groupe. Compatible bash 3.2 (ni wait -n ni wait -f).
  # Remplace : le tube lancé au premier plan, dont l'interruption n'était traitée qu'à la fin du passage. Retrait : permanent, tant que le tube
  # (git archive | docker run | tee) est lancé par ce script.
  { git archive --format=tar "$COMMIT" | PMZILLA_LAB_DB_PASSWORD="$MDP_BASE" "$DOCKER" run --rm -i --name "$NOM_CONTENEUR" --label pmzilla-lab-ci=1 \
      --network "container:$NOM_BASE" --user node \
      --cpus "$CPUS" ${OPT_CPUSET_SUITES[@]+"${OPT_CPUSET_SUITES[@]}"} --memory "$MEMOIRE" --shm-size 1g --env LANG=C.UTF-8 --env LC_ALL=C.UTF-8 --env TZ=Europe/Paris \
      --env HOME=/home/node --env TMPDIR=/tmp --env UV_OFFLINE=1 --env RUN_ALL_DURATIONS=/tmp/run_all-durees.tsv \
      --env CI_PASSAGE_CPUS="$CPUS" --env PMZILLA_LAB_DB_PASSWORD \
      "$IMAGE_NOM:$CLE" bash -c "$interieur" | tee "$SORTIE"
    exit "${PIPESTATUS[1]}"; } &
  wait "$!"
  code=$?
  trap '' INT TERM
  MDP_BASE=""
  retirer_conteneur
  liberer_place   # la place est rendue dès que les conteneurs sont retirés : la file avance pendant que le rapport s'écrit
  LIGNES_PHASES=$(grep -a '^ci_passage : phase ' "$SORTIE" | sed 's/^ci_passage : //')
  LIGNE_MEMOIRE=$(grep -a '^ci_passage : mémoire au plus : ' "$SORTIE" | tail -1 | sed 's/^ci_passage : //')
  LIGNE_BASE_MAC=$(grep -a '^ci_passage : suites propres au Mac non lancées en phase base : ' "$SORTIE" | tail -1 | sed 's/^ci_passage : //')
  LIGNE_PLACES=$(ligne_places "$json")
  phases=$(printf '%s\n' "$LIGNES_PHASES" | sed -n 's/^phase \([a-z0-9]*\) : verte.*/\1/p' | paste -sd, -)
  echecs_ph=$(printf '%s\n' "$LIGNES_PHASES" | sed -n 's/^phase [a-z0-9]* : rouge · [0-9]* s : \(.*\)$/\1/p' | paste -sd, -)
  # Ligne TOTAL, « Tests sautés » et ligne des suites Mac : celles de la PREMIÈRE exécution du lanceur (la phase portable) ; les suites de la
  # phase base ont chacune leur ligne TOTAL, qui ne sont pas le total du passage.
  total=$(grep -a '^TOTAL : ' "$SORTIE" | head -1)
  saut=$(grep -a '^run_all : suites propres au Mac non lancées : ' "$SORTIE" | head -1)
  if [ "$code" -eq 0 ] && printf '%s' "$total" | grep -q '· tous réussis ·'; then verdict=vert; else verdict=rouge; fi
  # Phase e2e « non lancée » (passage.sh sans les étapes) : jamais un verdict vert ni une preuve (revue de la tranche 2). Remplace : rien. Retrait : permanent.
  if printf '%s\n' "$LIGNES_PHASES" | grep -q '^phase e2e : non lancée'; then
    verdict=rouge; [ "$code" -ne 0 ] || code=1
    [ -n "$echecs_ph" ] || echecs_ph="phase e2e non lancée"
  fi
  [ "$verdict" = vert ] || [ "$code" -ne 0 ] || code=1
  sautes=$(grep -a '^Tests sautés : ' "$SORTIE" | head -1)
  [ -n "$MODE_ARBRE" ] || ecrire_rapport "$SORTIE" "$code" "$debut" "$total" "$saut" "$sautes"   # T2 : ni rapport pour --index ni pour --travail
  rm -f "$SORTIE"; SORTIE=""
  [ -z "$sautes" ] || echo "$sautes"
  [ -z "$total" ] || echo "$total"
  [ -z "$saut" ] || echo "$saut"
  if [ -n "$total" ] && [ -z "$MODE_ARBRE" ]; then enregistrer "$verdict"; fi   # sans verdict du lanceur, la ligne retirée au départ ne revient pas
  if [ "$verdict" = vert ]; then
    n=$(printf '%s' "$total" | sed -n 's/^TOTAL : .* tests dans \([0-9]*\) suites.*/\1/p')
    m=$(printf '%s' "$saut" | sed -n 's/^run_all : suites propres au Mac non lancées : \([0-9]*\).*/\1/p')
    if [ -n "$MODE_ARBRE" ]; then   # T2 : le mode complet d'un --index vert (trois phases) écrit la ligne « complet » ; --travail rien
      [ "$MODE_ARBRE" != index ] || [ "$phases" != "portable,base,e2e" ] || enregistrer_preuve_index complet
    else
      [ "$phases" != "portable,base,e2e" ] || enregistrer_preuve "$phases"   # D6 : seulement les trois phases vertes ; sinon ni preuve ni phrase
    fi
    avert=$(printf '%s' "$total" | sed -n 's/.* · \(avertissement : .*\)$/\1/p')   # préparation uv en échec (R-20261101-106) : dite, jamais un rouge
    dire "verdict vert (arbre ${ARBRE:0:12}, image ${CLE:0:12},${phases:+ phases $phases,} ${n:-?} suites, ${m:-0} suites Mac non lancées)${avert:+ · $avert}"
    exit 0
  fi
  echecs=$echecs_ph   # les suites en échec nommées par les phases rouges d'abord, puis par la ligne TOTAL du lanceur
  [ -n "$echecs" ] || echecs=$(printf '%s' "$total" | sed -n 's/^TOTAL : .* suite(s) en échec : \(.*\) · durée totale.*/\1/p')
  [ -n "$echecs" ] || { if [ -n "$total" ]; then echecs="code $code"; else echecs="aucun verdict du lanceur (code $code)"; fi; }
  dire "verdict rouge (arbre ${ARBRE:0:12}, image ${CLE:0:12}${phases:+, phases $phases}) : $echecs"
  exit 1
}

# --- rejeu (change ci-local-runner, tranche 2, Q220 ; R-20261101-113) ------------------------------------------------------------------
# « run --rejeu portable <suites> » : le seul rejeu en conteneur du train (D9). Même arbre (HEAD propre), même image, même file et même priorité du
# jeton que run ; mais ni base, ni phase base ou e2e : le conteneur n'a que la boucle locale vide (--network none) et lance
# bash tests/run_all.sh <suites>. Les noms passent en arguments du conteneur, jamais interpolés dans une commande. N'écrit ni verdict (preparer_registre
# n'est pas appelée : la ligne de l'arbre n'est ni retirée ni écrite), ni preuve, ni rapport de mesure. Dernière ligne :
#   ci_local : rejeu vert (arbre <court>, image <clé courte>) : <suites>      ou      ci_local : rejeu rouge (arbre <court>, image <clé courte>) : <suites en échec>
# Remplace : rien (le train rejouait jusqu'ici sur le Mac). Retrait : permanent, tant que le train rejoue ses suites portables en conteneur.
rejeu() {
  local code interieur json ligne echecs
  resoudre_source ""
  cles "$COMMIT"
  docker_repond
  verifier_place_vm
  verifier_image
  [ -f "$PASSAGE_SH" ] || refus 4 "script intérieur introuvable (ci/passage.sh) ; rien n'est lancé"
  interieur=$(cat "$PASSAGE_SH")
  json=$(places_calculees)
  cpus_de_json "$json"
  trap 'interrompu 130' INT
  trap 'interrompu 143' TERM
  trap 'retirer_conteneur; liberer_place' EXIT
  if [ -n "$MODE_ARBRE" ]; then   # T2 (D5) : une exécution ciblée tient une place ciblée (2 processeurs, 3072 Mio, sans base)
    attendre_place "$json" ciblee
    CPUS=$CPUS_CIBLEE; MEMOIRE="${MEMOIRE_CIBLEE_MIO}m"
  else
    attendre_place "$json"
  fi
  regler_cpuset 0
  NOM_CONTENEUR="pmzilla-ci-$(od -An -N6 -tx1 /dev/urandom 2>/dev/null | tr -d ' \n')"
  [ "$NOM_CONTENEUR" != "pmzilla-ci-" ] || NOM_CONTENEUR="pmzilla-ci-$$$(date +%s)"
  SORTIE=$(mktemp "${TMPDIR:-/tmp}/ci_local.XXXXXX") || { echo "ci_local : fichier temporaire impossible" >&2; exit 1; }
  # Même tube en arrière-plan puis « wait » que dans passage (voir le commentaire là-bas). Remplace : le tube de premier plan. Retrait : permanent,
  # tant que le tube est lancé par ce script.
  { git archive --format=tar "$COMMIT" | "$DOCKER" run --rm -i --name "$NOM_CONTENEUR" --label pmzilla-lab-ci=1 \
      --network none --user node \
      --cpus "$CPUS" ${OPT_CPUSET_SUITES[@]+"${OPT_CPUSET_SUITES[@]}"} --memory "$MEMOIRE" --shm-size 1g --env LANG=C.UTF-8 --env LC_ALL=C.UTF-8 --env TZ=Europe/Paris \
      --env HOME=/home/node --env TMPDIR=/tmp --env UV_OFFLINE=1 --env RUN_ALL_DURATIONS=/tmp/run_all-durees.tsv \
      --env CI_PASSAGE_CPUS="$CPUS" \
      "$IMAGE_NOM:$CLE" bash -c "$interieur" ci_passage --rejeu "${SUITES_REJEU[@]}" | tee "$SORTIE"
    exit "${PIPESTATUS[1]}"; } &
  wait "$!"
  code=$?
  trap '' INT TERM
  retirer_conteneur
  liberer_place
  ligne=$(grep -a '^ci_passage : rejeu : ' "$SORTIE" | tail -1)
  rm -f "$SORTIE"; SORTIE=""
  if [ "$code" -eq 0 ] && printf '%s' "$ligne" | grep -q '^ci_passage : rejeu : verte'; then
    if [ -n "$MODE_ARBRE" ]; then   # T2 : --index vert écrit sa ligne de preuve d'index ; --travail rien ; le verdict est dit comme celui d'un passage
      [ "$MODE_ARBRE" != index ] || enregistrer_preuve_index "$(IFS=,; printf '%s' "${SUITES_REJEU[*]}")"
      dire "verdict vert (arbre ${ARBRE:0:12}, image ${CLE:0:12}, suites ${SUITES_REJEU[*]})"
    else
      dire "rejeu vert (arbre ${ARBRE:0:12}, image ${CLE:0:12}) : ${SUITES_REJEU[*]}"
    fi
    exit 0
  fi
  echecs=$(printf '%s' "$ligne" | sed -n 's/^ci_passage : rejeu : rouge · [0-9]* s : \(.*\)$/\1/p')
  [ -n "$echecs" ] || echecs="aucun verdict du lanceur (code $code)"
  if [ -n "$MODE_ARBRE" ]; then dire "verdict rouge (arbre ${ARBRE:0:12}, image ${CLE:0:12}) : $echecs"
  else dire "rejeu rouge (arbre ${ARBRE:0:12}, image ${CLE:0:12}) : $echecs"; fi
  exit 1
}

# --- sous-commandes ---------------------------------------------------------------------------------------------------------------------
case "$SOUS" in
  places)   # lecture seule : aucun verrou à vérifier, aucun conteneur, aucun fichier écrit
    docker_repond
    places_afficher
    exit 0 ;;
  cle)   # lecture seule (comme places) : la clé d'image de HEAD et la présence de l'image ; aucun conteneur, aucune construction, aucun fichier écrit
    # Remplace : rien (le contrôle ci-container de tools/doctor.py n'a pas à recalculer la clé : une seule source, cles). Retrait : permanent, tant
    # que la preuve passe par le conteneur et que le doctor contrôle l'image. Codes : 0 image présente ; 3 Docker ne répond pas ; 5 image absente.
    docker_repond
    COMMIT=$(git rev-parse --verify -q 'HEAD^{commit}') || refus 4 "arbre introuvable"
    cles "$COMMIT"
    if image_existe "$CLE"; then dire "image de la clé ${CLE:0:12} présente"; exit 0; fi
    refus 5 "image de la clé ${CLE:0:12} absente (lancer : $(commande_up))" ;;
  run)
    verifier_gel_run
    # T2 : --index ou --travail avec des suites : le conteneur sans base (rejeu) ; sans suite : le passage complet sur cet arbre
    if [ "$REJEU" -eq 1 ] || { [ -n "$MODE_ARBRE" ] && [ ${#SUITES_REJEU[@]} -gt 0 ]; }; then rejeu; else passage "$BRANCHE"; fi ;;
  build)
    verifier_verrou
    resoudre ""
    docker_repond
    construire "$COMMIT"
    exit 0 ;;
  up)
    verifier_verrou
    BRANCHE=${BRANCHE:-main}
    resoudre "$BRANCHE"
    if ! "$COLIMA" status >/dev/null 2>&1; then
      # Profil du lab (R-20261103-25 (2) Q2) : 8 processeurs et 16 Go, comme le calcul des places (R-20261103-6 Q4).
      dire "Colima ne répond pas : démarrage (colima start --cpu 8 --memory 16)"
      "$COLIMA" start --cpu 8 --memory 16 || true
    fi
    docker_repond
    cles "$COMMIT"
    if image_existe "$CLE"; then dire "image à jour (${CLE:0:12})"; else construire "$COMMIT"; nettoyer_images "$CLE"; fi   # ci-local-image-prune D3 : seulement après une construction de up
    passage "$BRANCHE" ;;
esac
