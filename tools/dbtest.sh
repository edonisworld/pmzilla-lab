#!/bin/bash
# PMZilla Lab : lance les suites de tests qui ont besoin d'une base PostgreSQL, sur une instance JETABLE (installation.md, 14.5).
#
#     bash tools/dbtest.sh                          les suites par défaut : db flow_import flow_store flow_compare flow_views hybrid_search pmzilla_lab_library library_backend cases_store watch_store
#     bash tools/dbtest.sh flow_store flow_compare  seulement ces suites (noms de tests/<suite>/)
#     bash tools/dbtest.sh --port 55433             port de l'hôte du conteneur (défaut 55432 ; jamais 5432 ni celui de la vraie base)
#     bash tools/dbtest.sh --help
#
# À lancer par l'utilisateur seul, dans son Terminal : Claude Code n'y est pas autorisé (règles deny de .claude/settings.json).
#
# Ce que fait le script :
#   1. refuse de démarrer si le port vaut 5432 (ou celui de la vraie base, PMZILLA_LAB_DB_PORT), si une suite n'existe pas, ou si
#      le conteneur pmzilla-lab-test-db existe déjà (il n'est alors ni touché ni supprimé) ;
#   2. démarre un conteneur jetable pmzilla-lab-test-db (même image fixée que docker-compose.yml, publié sur 127.0.0.1 seulement) avec
#      un mot de passe aléatoire : il vit dans ce script, passé par l'environnement des seules commandes qui en ont besoin, jamais affiché,
#      jamais écrit, jamais exporté dans votre shell ; le mot de passe de la vraie base (Trousseau) n'est ni lu ni utilisé ;
#   3. attend que PostgreSQL réponde, puis lance chaque suite avec « bash tests/run_all.sh <suite> », sans tube ;
#   4. supprime le conteneur et son volume (docker rm -f -v) à la fin, même en cas d'échec ou de Ctrl+C ;
#   5. affiche le résumé « suites vertes / en échec ».
# Les suites créent elles-mêmes leurs bases pmzilla_test_<hex> et appliquent leurs migrations.
#
# Code de sortie : 0 toutes les suites sont vertes ; 1 une suite au moins échoue, ou le conteneur ne démarre pas ; 2 usage incorrect ou
# prérequis absent (rien n'a été démarré).
#
# Variables (pour les tests) : DBTEST_ATTENTE (secondes max d'attente du conteneur, défaut 120), DBTEST_RUN_ALL (lanceur des suites,
# défaut tests/run_all.sh).
set -uo pipefail
RACINE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RACINE" || exit 2
NOM="pmzilla-lab-test-db"
ATTENTE="${DBTEST_ATTENTE:-120}"
LANCEUR="${DBTEST_RUN_ALL:-tests/run_all.sh}"
SUITES_PAR_DEFAUT=(db flow_import flow_store flow_compare flow_views hybrid_search pmzilla_lab_library library_backend cases_store watch_store)

PORT="55432"
SUITES=()
while [ $# -gt 0 ]; do
  case "$1" in
    --help|-h) sed -n '2,/^set -uo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit 0 ;;
    --port) [ $# -ge 2 ] || { echo "--port demande un numéro"; exit 2; }; PORT="$2"; shift 2 ;;
    -*) echo "Usage : bash tools/dbtest.sh [--port N] [suite ...] [--help]"; exit 2 ;;
    *) SUITES+=("$1"); shift ;;
  esac
done
[ ${#SUITES[@]} -gt 0 ] || SUITES=("${SUITES_PAR_DEFAUT[@]}")

# --- Refus de viser la vraie base ou une suite inconnue ---------------------------------------------------------------------
PORT_REEL="${PMZILLA_LAB_DB_PORT:-5432}"
if ! printf '%s' "$PORT" | grep -Eq '^[0-9]{2,5}$'; then echo "Port invalide : $PORT"; exit 2; fi
if [ "$PORT" = "5432" ] || [ "$PORT" = "$PORT_REEL" ]; then
  echo "Refus : le port $PORT est celui de la vraie base. Les suites avec base ne l'utilisent jamais (donner un autre --port)."; exit 2
fi
for suite in "${SUITES[@]}"; do
  if ! printf '%s' "$suite" | grep -Eq '^[A-Za-z0-9_]+$' || [ ! -d "tests/$suite" ]; then
    echo "Suite inconnue : « $suite » (dossier tests/$suite absent)"; exit 2
  fi
done

# --- Prérequis ------------------------------------------------------------------------------------------------------------
command -v docker >/dev/null 2>&1 || { echo "Docker est introuvable (brew install colima docker docker-compose)"; exit 2; }
if ! docker info >/dev/null 2>&1; then
  echo "Docker ne répond pas. Vérifier Colima : colima status (puis colima start --cpu 4 --memory 6)"; exit 2
fi
if [ -n "$(docker ps -a -q --filter "name=^${NOM}\$" 2>/dev/null)" ]; then
  echo "Le conteneur $NOM existe déjà (un passage précédent interrompu ?). Il n'est pas touché. S'il est à vous de le supprimer : docker rm -f -v $NOM"; exit 2
fi
IMAGE="$(grep -E '^[[:space:]]+image:' docker-compose.yml | head -1 | sed -E 's/^[[:space:]]+image:[[:space:]]*//; s/["[:space:]]//g')"
case "$IMAGE" in
  */*:[0-9]*) ;;
  *) echo "Image de docker-compose.yml introuvable ou non fixée : « $IMAGE »"; exit 2 ;;
esac
# /dev/shm du conteneur jetable : la valeur de shm_size de docker-compose.yml (64 Mo par défaut sinon, trop peu pour l'index BM25), repli 1g.
SHM="$(grep -E '^[[:space:]]+shm_size:' docker-compose.yml | head -1 | sed -E 's/^[[:space:]]+shm_size:[[:space:]]*//; s/[#].*$//; s/["[:space:]]//g')"
printf '%s' "$SHM" | grep -Eiq '^[0-9]+[bkmg]b?$' || SHM="1g"
[ -f "$LANCEUR" ] || { echo "Lanceur de suites introuvable : $LANCEUR"; exit 2; }

# --- Nettoyage : toujours, même en cas d'échec ou de Ctrl+C ----------------------------------------------------------------
CREE=0
nettoyer() {
  code=$?
  trap '' INT TERM
  if [ "$CREE" -eq 1 ]; then
    docker rm -f -v "$NOM" >/dev/null 2>&1
    if [ -n "$(docker ps -a -q --filter "name=^${NOM}\$" 2>/dev/null)" ]; then
      echo "ATTENTION : le conteneur jetable $NOM existe encore ; le supprimer : docker rm -f -v $NOM"
    else
      echo "Conteneur jetable supprimé : $NOM"
    fi
  fi
  exit "$code"
}
trap nettoyer EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# --- Conteneur jetable : mot de passe aléatoire, propre à ce passage --------------------------------------------------------
mdp="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
if [ -z "$mdp" ]; then echo "Impossible de générer le mot de passe du conteneur jetable"; exit 2; fi
echo "Image : $IMAGE (celle de docker-compose.yml) · conteneur $NOM sur 127.0.0.1:$PORT"
CREE=1   # même si le démarrage échoue, le nettoyage retire ce qui a pu être créé
if ! POSTGRES_PASSWORD="$mdp" docker run -d --name "$NOM" --label pmzilla-lab-test=1 \
     --shm-size "$SHM" -e POSTGRES_PASSWORD -e POSTGRES_DB=pmzilla -p "127.0.0.1:$PORT:5432" "$IMAGE" >/dev/null 2>&1; then
  echo "Impossible de démarrer le conteneur jetable (image absente ? réseau ? port $PORT pris ?)"; exit 1
fi
pret=0; i=0
while [ "$i" -lt "$ATTENTE" ]; do
  if docker exec "$NOM" pg_isready -h 127.0.0.1 -U postgres -d pmzilla >/dev/null 2>&1; then pret=1; break; fi
  i=$((i + 2)); sleep 2
done
if [ "$pret" -ne 1 ]; then echo "Le conteneur jetable n'est pas prêt après ${ATTENTE} s. Voir : docker logs $NOM"; exit 1; fi

# --- Les suites, une à une, sans tube ---------------------------------------------------------------------------------------
vertes=(); echouees=()
for suite in "${SUITES[@]}"; do
  echo
  echo "=== $suite ==="
  if env -u PMZILLA_LAB_DB_URL -u PMZILLA_NO_EVALS PMZILLA_LAB_DB_PASSWORD="$mdp" PMZILLA_LAB_DB_PORT="$PORT" bash "$LANCEUR" "$suite"; then
    vertes+=("$suite")
  else
    echouees+=("$suite")
  fi
done
mdp=""

echo
echo "Suites vertes : ${vertes[*]:-aucune}"
echo "Suites en échec : ${echouees[*]:-aucune}"
if [ ${#echouees[@]} -gt 0 ]; then exit 1; fi
exit 0
