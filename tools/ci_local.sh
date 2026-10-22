#!/bin/bash
# PMZilla Lab : CI locale dans un conteneur (change local-ci-container, design D1 à D7b, D9 à D11).
#
#     bash tools/ci_local.sh run [<branche>]   les suites portables (bash tests/run_all.sh --portable) dans un conteneur jetable, hors
#                                              réseau, sur l'arbre du sommet de <branche> (défaut : HEAD, qui doit être propre)
#     bash tools/ci_local.sh build             construit l'image depuis ci/Dockerfile et l'arbre de HEAD (propre), avec réseau (auteur seul)
#     bash tools/ci_local.sh up [<branche>]    la commande unique (défaut main) : Colima, Docker, image de la clé (construite au besoin),
#                                              puis run (auteur seul)
#     bash tools/ci_local.sh --help
#
# run est permis à la session ; build et up sont à l'auteur, dans son Terminal (règles deny de D12).
#
# Ce que fait run :
#   1. refus avant tout conteneur (codes 2 à 7 ci-dessous) ; l'arbre testé est celui d'UN commit : le sommet de la branche nommée, ou
#      HEAD quand l'extraction est propre (un fichier non suivi non ignoré compte) ; une modification non commitée n'est jamais testée ;
#   2. clé de l'image calculée depuis l'arbre testé : hash de ci/Dockerfile, des entrées « pinned_in: CI Dockerfile » de
#      docs/pmzilla/composants.yaml, de .python-version, de la ligne DEPS de tests/run_all.sh, des blocs « # /// script » des scripts Python de tools, tests et
#      .claude/skills (la sélection de l'étape du Dockerfile) et de chaque verrou npm déclaré (D10 :
#      la liste SUITES_NPM=(<dossier>:<nom> …) du lanceur, verrou <dossier>/package-lock.json ; aujourd'hui aucune) ; aucune image de
#      cette clé : code 5 ; tests/suites_mac.txt est lu au passage, hors de la clé ;
#   3. git archive de l'arbre, envoyé sur l'entrée du conteneur (jamais de montage), recommité dans un dépôt jetable à auteur neutre ;
#   4. docker run --rm, --network none, utilisateur non root, nom au hasard, limites de processeurs et de mémoire, aucun montage, volume,
#      périphérique ni socket ; environnement construit ici (langue, fuseau, HOME et TMPDIR du conteneur, UV_OFFLINE=1, RUN_ALL_JOBS
#      d'après les processeurs du conteneur, RUN_ALL_DURATIONS dans le conteneur) : aucune variable de l'appelant ne passe
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
#   départ : une fois les refus 2 à 7 passés, avant le conteneur, la ligne de l'arbre testé est retirée (un passage interrompu, ou dont
#   le conteneur ne donne pas de verdict du lanceur, n'en laisse aucune) ;
#   fin : la ligne de l'arbre est écrite, vert ou rouge, sans toucher aux autres, par un fichier temporaire renommé, propriétaire seul ;
#   « ci_local : verdict enregistré pour l'arbre <court> » ou « ci_local : verdict non enregistré (dossier de données introuvable |
#   écriture impossible) », juste avant la ligne du verdict ; un enregistrement manqué ne change jamais le code ; un retrait manqué de la
#   ligne de départ le dit tout de suite (« verdict précédent de cet arbre non retiré (écriture impossible) ») et empêche l'écriture finale ;
#   les écritures passent par un verrou mkdir à côté du fichier (verdicts.lock, repris au bout d'une minute, 5 s d'attente au plus) ;
#   qui l'écrit : run seul (et up, qui le lance) ; une ligne écrite à la main passerait (c'est une déclaration, comme pour dbtest) ;
#   qui le lit : la fin d'un worktree en mode CI (FINISH_WORKTREE_CI=1) et tools/finish_branch.sh, pour un arbre exact ; aucun des deux
#   ne lance de conteneur.
#
# Codes de sortie : 0 passage vert, image construite, up vert ; 1 passage rouge ; 2 usage ; 3 Docker (ou Colima) ne répond pas ;
# 4 entrée refusée (hors du dépôt, branche inconnue, arbre non propre) ; 5 image absente ou périmée, ou dépendances npm de l'image
# différentes du verrou ; 6 construction en échec ; 7 une autre fin de branche tient le verrou. Les codes 2 à 7 ne démarrent aucun
# conteneur ; 6 ne laisse aucune image étiquetée. Verrou de fin (même règle que le lanceur de tests) : un verrou vivant d'un autre
# jeton, ou sans FINISH_LOCK_TOKEN, refuse ; un verrou périmé est dit et ignoré ; le jeton de la fin ne change rien ; le script ne
# crée, ne retire ni ne modifie jamais le verrou.
#
# Couche npm (D10) : inerte tant qu'aucun verrou n'est déclaré ; build avec un verrou déclaré refuse (code 6), ci/Dockerfile n'ayant
# pas encore de couche npm. Le passage n'installe jamais rien et n'atteint jamais le registre.
#
# Variables (pour les tests) : CI_LOCAL_DOCKER (commande Docker, défaut docker), CI_LOCAL_COLIMA (commande Colima, défaut colima),
# CI_LOCAL_VERDICTS (autre fichier des verdicts). Dossier de données : celui de tools/lab_paths.sh (PMZILLA_LAB_DATA).
set -uo pipefail
ICI="$(cd "$(dirname "$0")" && pwd)"
DOCKER="${CI_LOCAL_DOCKER:-docker}"
COLIMA="${CI_LOCAL_COLIMA:-colima}"
IMAGE_NOM="pmzilla-ci"
CPUS=3          # dans l'instance Colima du lab (4 processeurs, 6 Go), qui garde de la place pour le conteneur de la base
MEMOIRE=4g
TAB=$(printf '\t')

dire() { printf 'ci_local : %s\n' "$*"; }
refus() { local code=$1; shift; printf 'ci_local : %s\n' "$*" >&2; exit "$code"; }
usage() { refus 2 "usage : bash tools/ci_local.sh run [<branche>] | build | up"; }

# --- usage --------------------------------------------------------------------------------------------------------------------
[ $# -ge 1 ] || usage
SOUS=$1; BRANCHE=""
case "$SOUS" in
  --help|-h) [ $# -eq 1 ] || usage; sed -n '2,/^set -uo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit 0 ;;
  run|up) [ $# -le 2 ] || usage; BRANCHE="${2:-}" ;;
  build) [ $# -eq 1 ] || usage ;;
  *) usage ;;
esac
case "$BRANCHE" in -*) usage ;; esac

# --- dépôt et verrou de fin ----------------------------------------------------------------------------------------------------
RACINE_DEPOT=$(git rev-parse --show-toplevel 2>/dev/null) || refus 4 "hors du dépôt"
cd "$RACINE_DEPOT" || refus 4 "hors du dépôt"
COMMUN=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || COMMUN=""
. "$ICI/finish_lock.sh"   # _fl_stale : même règle de péremption que la fin de branche ; sourcé, il n'écrit rien

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

# --- clé de l'image (D4, D10) ----------------------------------------------------------------------------------------------------
if command -v shasum >/dev/null 2>&1; then HACHE=(shasum -a 256); else HACHE=(sha256sum); fi
hacher() { "${HACHE[@]}" | cut -c1-64; }
fichier_de() { git show "$1:$2" 2>/dev/null; }
verrous_npm() { # <commit> : un chemin de verrou par suite npm déclarée par le lanceur
  fichier_de "$1" tests/run_all.sh | sed -n 's/^SUITES_NPM=(\(.*\))[[:space:]]*$/\1/p' | tr ' ' '\n' \
    | sed -n 's/^\([A-Za-z0-9_.-][A-Za-z0-9_./-]*\):[A-Za-z0-9_-]*$/\1\/package-lock.json/p'
}
scripts_pep723() { # <commit> : chemin et bloc « # /// script » de chaque script Python de tools, tests et .claude/skills (la sélection de l'étape du Dockerfile)
  local c=$1 f
  git grep -l '^# /// script' "$c" -- 'tools/*.py' 'tests/*.py' '.claude/skills/*.py' 2>/dev/null | sed "s/^$c://" | LC_ALL=C sort | while IFS= read -r f; do
    echo "$f"
    fichier_de "$c" "$f" | sed -n '/^# \/\/\/ script/,/^# \/\/\/[[:space:]]*$/p'
  done
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
  for v in $(verrous_npm "$c"); do NPM="$NPM$v $(fichier_de "$c" "$v" | hacher);"; done
  CLE=$(printf '%s\n%s\n' "$CLE_BASE" "$NPM" | hacher)
}

docker_repond() { "$DOCKER" info >/dev/null 2>&1 || refus 3 "Docker ne répond pas ; rien n'est lancé (colima status)"; }
image_existe() { "$DOCKER" image inspect "$IMAGE_NOM:$1" >/dev/null 2>&1; }
verifier_image() {
  image_existe "$CLE" && return 0
  if [ -n "$NPM" ] && [ -n "$("$DOCKER" images -q --filter "label=pmzilla.ci.base=$CLE_BASE" 2>/dev/null)" ]; then
    refus 5 "dépendances npm de l'image différentes du verrou (lancer bash tools/ci_local.sh up)"
  fi
  refus 5 "image absente ou périmée (lancer bash tools/ci_local.sh up)"
}

# --- construction (D1 build, D4) ---------------------------------------------------------------------------------------------------
construire() { # <commit> : image de la clé de ce commit, contexte = archive de son arbre
  local c=$1
  cles "$c"
  if [ -n "$NPM" ]; then
    printf 'ci_local : verrous npm déclarés, mais ci/Dockerfile n a pas encore de couche npm (D10)\n' >&2
    refus 6 "construction de l'image en échec"
  fi
  if ! git archive --format=tar "$c" | "$DOCKER" build --tag "$IMAGE_NOM:$CLE" --label "pmzilla.ci.cle=$CLE" \
       --label "pmzilla.ci.base=$CLE_BASE" --file ci/Dockerfile -; then
    refus 6 "construction de l'image en échec"
  fi
  dire "image construite (${CLE:0:12})"
}

# --- dossier de données (lab-paths) ------------------------------------------------------------------------------------------------
dossier_donnees() { ( . "$ICI/lab_paths.sh"; lab_paths_init >/dev/null 2>&1 && [ -d "$LAB_DATA_FOLDER" ] && printf '%s' "$LAB_DATA_FOLDER" ); }

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
ecrire_rapport() { # <sortie du lanceur> <code> <début> <ligne TOTAL> <ligne Mac> <ligne « Tests sautés »>
  local sortie=$1 code=$2 debut=$3 total=$4 saut=$5 sautes=${6:-} donnees fichier liste
  if [ -n "${CI_LOCAL_DOCKER:-}" ] && [ -z "${PMZILLA_LAB_DATA:-}" ]; then
    dire "rapport non écrit (passage de test sans dossier de données)"; return 0
  fi
  donnees=$(dossier_donnees) && [ -n "$donnees" ] || { dire "rapport non écrit (dossier de données introuvable)"; return 0; }
  fichier="$donnees/ci/rapport-$(date '+%Y%m%d-%H%M%S')-${ARBRE:0:12}.txt"
  liste=$(printf '%s' "$saut" | sed -n 's/^run_all : suites propres au Mac non lancées : [0-9]* (\(.*\))$/\1/p')
  if ( umask 077; mkdir -p "$donnees/ci" && {
         echo "arbre : $ARBRE"
         echo "image : $CLE"
         echo "début : $debut"
         echo "code : $code"
         echo "suites Mac non lancées : ${liste:-aucune ligne du lanceur}"
         echo "--- lanceur"
         grep -a ' tests · ' "$sortie" | sed 's/\(ÉCHEC (code [0-9]*)\) : .* · /\1 · /'
         [ -z "$sautes" ] || echo "$sautes"
         [ -z "$saut" ] || echo "$saut"
         [ -z "$total" ] || echo "$total"
       } > "$fichier" ) 2>/dev/null; then
    dire "rapport écrit ($(basename "$fichier"))"
  else
    rm -f "$fichier" 2>/dev/null
    dire "rapport non écrit (écriture impossible)"
  fi
}

# --- passage (D1 run, D5 à D7b) --------------------------------------------------------------------------------------------------------
NOM_CONTENEUR=""; SORTIE=""
retirer_conteneur() { [ -n "$NOM_CONTENEUR" ] && "$DOCKER" rm -f "$NOM_CONTENEUR" >/dev/null 2>&1; return 0; }
interrompu() {
  trap '' INT TERM
  retirer_conteneur
  [ -n "$SORTIE" ] && rm -f "$SORTIE"
  dire "passage interrompu ; conteneur retiré, aucun verdict enregistré"
  exit "$1"
}

# Script lancé dans le conteneur : archive extraite, recommitée (auteur neutre), tâches d'après les processeurs du conteneur.
INTERIEUR='set -e
mkdir -p "$HOME/depot"; cd "$HOME/depot"
tar -xf -
git init -q
git add -A -f
git -c user.name=ci-local -c user.email=ci-local@exemple.invalid commit -q -m "ci locale"
set +e
p=$(getconf _NPROCESSORS_ONLN 2>/dev/null); case "$p" in ""|*[!0-9]*) p=2 ;; esac
j=$((p / 2)); [ "$j" -ge 1 ] || j=1
RUN_ALL_JOBS=$j exec bash tests/run_all.sh --portable'

passage() { # <branche ou vide>
  local code debut total saut sautes n m echecs verdict
  resoudre "$1"
  cles "$COMMIT"
  docker_repond
  verifier_image
  preparer_registre
  NOM_CONTENEUR="pmzilla-ci-$(od -An -N6 -tx1 /dev/urandom 2>/dev/null | tr -d ' \n')"
  [ "$NOM_CONTENEUR" != "pmzilla-ci-" ] || NOM_CONTENEUR="pmzilla-ci-$$$(date +%s)"
  SORTIE=$(mktemp "${TMPDIR:-/tmp}/ci_local.XXXXXX") || { echo "ci_local : fichier temporaire impossible" >&2; exit 1; }
  trap 'interrompu 130' INT
  trap 'interrompu 143' TERM
  debut=$(date '+%Y-%m-%d %H:%M:%S')
  git archive --format=tar "$COMMIT" | "$DOCKER" run --rm -i --name "$NOM_CONTENEUR" --network none --user node \
      --cpus "$CPUS" --memory "$MEMOIRE" --env LANG=C.UTF-8 --env LC_ALL=C.UTF-8 --env TZ=Europe/Paris \
      --env HOME=/home/node --env TMPDIR=/tmp --env UV_OFFLINE=1 --env RUN_ALL_DURATIONS=/tmp/run_all-durees.tsv \
      "$IMAGE_NOM:$CLE" bash -c "$INTERIEUR" | tee "$SORTIE"
  code=${PIPESTATUS[1]}
  trap '' INT TERM
  retirer_conteneur
  total=$(grep -a '^TOTAL : ' "$SORTIE" | tail -1)
  saut=$(grep -a '^run_all : suites propres au Mac non lancées : ' "$SORTIE" | tail -1)
  if [ "$code" -eq 0 ] && printf '%s' "$total" | grep -q '· tous réussis ·'; then verdict=vert; else verdict=rouge; fi
  [ "$verdict" = vert ] || [ "$code" -ne 0 ] || code=1
  sautes=$(grep -a '^Tests sautés : ' "$SORTIE" | tail -1)
  ecrire_rapport "$SORTIE" "$code" "$debut" "$total" "$saut" "$sautes"
  rm -f "$SORTIE"; SORTIE=""
  [ -z "$sautes" ] || echo "$sautes"
  [ -z "$total" ] || echo "$total"
  [ -z "$saut" ] || echo "$saut"
  if [ -n "$total" ]; then enregistrer "$verdict"; fi   # sans verdict du lanceur, la ligne retirée au départ ne revient pas
  if [ "$verdict" = vert ]; then
    n=$(printf '%s' "$total" | sed -n 's/^TOTAL : .* tests dans \([0-9]*\) suites.*/\1/p')
    m=$(printf '%s' "$saut" | sed -n 's/^run_all : suites propres au Mac non lancées : \([0-9]*\).*/\1/p')
    dire "verdict vert (arbre ${ARBRE:0:12}, image ${CLE:0:12}, ${n:-?} suites, ${m:-0} suites Mac non lancées)"
    exit 0
  fi
  echecs=$(printf '%s' "$total" | sed -n 's/^TOTAL : .* suite(s) en échec : \(.*\) · durée totale.*/\1/p')
  [ -n "$echecs" ] || { if [ -n "$total" ]; then echecs="code $code"; else echecs="aucun verdict du lanceur (code $code)"; fi; }
  dire "verdict rouge (arbre ${ARBRE:0:12}, image ${CLE:0:12}) : $echecs"
  exit 1
}

# --- sous-commandes ---------------------------------------------------------------------------------------------------------------------
case "$SOUS" in
  run)
    verifier_verrou
    passage "$BRANCHE" ;;
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
      dire "Colima ne répond pas : démarrage (colima start --cpu 4 --memory 6)"
      "$COLIMA" start --cpu 4 --memory 6 || true
    fi
    docker_repond
    cles "$COMMIT"
    if image_existe "$CLE"; then dire "image à jour (${CLE:0:12})"; else construire "$COMMIT"; fi
    passage "$BRANCHE" ;;
esac
