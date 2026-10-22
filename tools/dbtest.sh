#!/bin/bash
# PMZilla Lab : lance les suites de tests qui ont besoin d'une base PostgreSQL, sur une instance JETABLE (installation.md, 14.5).
#
#     bash tools/dbtest.sh                          les suites par défaut : db flow_import flow_store flow_views hybrid_search pmzilla_lab_library library_backend cases_store watch_store book_usage dashboard flow_retention posture_evals export_jira_api history_jira story_quality
#     bash tools/dbtest.sh flow_store flow_import   seulement ces suites (noms de tests/<suite>/)
#     bash tools/dbtest.sh --port 55433             port de l'hôte du conteneur (défaut 55432 ; jamais 5432 ni celui de la vraie base)
#     bash tools/dbtest.sh --help
#
# À lancer par l'utilisateur seul, dans son Terminal : Claude Code n'y est pas autorisé (règles deny de .claude/settings.json).
#
# Ce que fait le script :
#   1. refuse de démarrer si le port vaut 5432 (ou celui de la vraie base, PMZILLA_LAB_DB_PORT), si une suite n'existe pas, ou si
#      le conteneur pmzilla-lab-test-db existe déjà (il n'est alors ni touché ni supprimé). Un port n'est valable qu'en forme décimale
#      simple (chiffres, sans signe, sans espace, sans zéro en tête, de 1 à 65535) et se compare en nombre : « 05432 » est refusé
#      (« Port invalide ») ; un PMZILLA_LAB_DB_PORT défini et illisible est refusé aussi (code 2), rien n'est démarré ;
#   2. démarre un conteneur jetable pmzilla-lab-test-db (même image fixée que docker-compose.yml, publié sur 127.0.0.1 seulement) avec
#      un mot de passe aléatoire : il vit dans ce script, passé par l'environnement des seules commandes qui en ont besoin, jamais affiché,
#      jamais écrit, jamais exporté dans votre shell ; le mot de passe de la vraie base (Trousseau) n'est ni lu ni utilisé ;
#   3. attend que PostgreSQL réponde, puis lance chaque suite avec « bash tests/run_all.sh <suite> », sans tube, avec pour seules variables de
#      base le port et le mot de passe du conteneur et DBTEST_PORT (le port du conteneur : le repère sans lequel les tests avec base sautent) ;
#      toute autre variable PMZILLA_LAB_DB_* de votre shell est retirée ;
#   4. supprime le conteneur et son volume (docker rm -f -v) à la fin, même en cas d'échec ou de Ctrl+C ;
#   5. affiche le résumé « suites vertes / en échec » ;
#   6. empreinte (test-speed-2, D5) : au départ, retire du fichier pmzilla-dbtest-ok (dossier Git commun, git rev-parse --git-common-dir,
#      partagé par l'espace de travail et ses worktrees) la ligne de l'arbre de HEAD ; à la fin, ajoute cet arbre (une ligne, l'identifiant
#      de l'arbre, ni branche, ni chemin, ni date, ni mot de passe) seulement si TOUT tient : liste par défaut (aucune suite nommée ; --port
#      permis), toutes les suites vertes, arbre de travail propre (fichiers non suivis non ignorés compris) au départ et à la fin, arbre de
#      HEAD inchangé pendant le passage. L'écriture passe par un fichier temporaire renommé, lisible par son propriétaire seul. Sinon rien
#      n'est écrit et la raison est dite (suites choisies, base injoignable depuis l'hôte, arbre non propre,arbre changé pendant le passage, hors dépôt Git, écriture
#      impossible) ; après un passage rouge, rien n'est dit. La fin de branche (tools/finish_branch.sh, code 14) exige cette ligne quand la
#      branche change le code de la base ; une ligne écrite à la main passe, comme les enregistrements du jeu d'essai (c'est une déclaration).
# Les suites créent elles-mêmes leurs bases pmzilla_test_<hex> et appliquent leurs migrations.
#
# Gel (finish-under-lock, D5) : avant tout conteneur, un verrou de fin de branche vivant d'un autre jeton (FINISH_LOCK_TOKEN) refuse avec le code 3 et
# « dbtest : fin de branche en cours (<branche>), lancement refusé » ; un verrou périmé est dit (« dbtest : verrou de fin périmé, ignoré ») et ignoré.
#
# Code de sortie : 0 toutes les suites sont vertes ; 1 une suite au moins échoue, ou le conteneur ne démarre pas ; 2 usage incorrect ou
# prérequis absent (rien n'a été démarré) ; 3 une autre fin de branche tient le verrou (rien n'a été démarré). Une empreinte non écrite ne change jamais le code.
#
# Variables (pour les tests ; DBTEST_PORT est posée par ce script pour les suites, jamais lue de l'appelant) : DBTEST_ATTENTE (secondes max d'attente du conteneur, défaut 120), DBTEST_RUN_ALL (lanceur des suites,
# défaut tests/run_all.sh ; quand il est remplacé et que DBTEST_RECORD ne l'est pas, aucune empreinte n'est lue ni écrite : le test du script
# tourne dans le vrai dépôt et ne touche jamais à son dossier Git), DBTEST_RECORD (autre fichier des empreintes),
# DBTEST_SONDE (commande qui reçoit le port et réussit s'il répond depuis l'hôte ; défaut : essai TCP sur 127.0.0.1).
set -uo pipefail
RACINE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RACINE" || exit 2
NOM="pmzilla-lab-test-db"
ATTENTE="${DBTEST_ATTENTE:-120}"
LANCEUR="${DBTEST_RUN_ALL:-tests/run_all.sh}"
SUITES_PAR_DEFAUT=(db flow_import flow_store flow_views hybrid_search pmzilla_lab_library library_backend cases_store watch_store book_usage dashboard flow_retention posture_evals export_jira_api history_jira story_quality)

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
PAR_DEFAUT=0
[ ${#SUITES[@]} -gt 0 ] || { SUITES=("${SUITES_PAR_DEFAUT[@]}"); PAR_DEFAUT=1; }

# --- Refus de viser la vraie base ou une suite inconnue ---------------------------------------------------------------------
# Une seule règle de port (test-db-guards, D1) : forme décimale simple seulement (chiffres ASCII, sans signe, sans espace, sans zéro en
# tête, de 1 à 65535), comparée en nombre. Même règle que la garde de tests/db/test_db.py.
port_valide() { local LC_ALL=C; [[ "$1" =~ ^[1-9][0-9]{0,4}$ ]] && [ "$((10#$1))" -le 65535 ]; }
PORT_REEL="${PMZILLA_LAB_DB_PORT:-5432}"
if ! port_valide "$PORT"; then echo "Port invalide : $PORT"; exit 2; fi
if ! port_valide "$PORT_REEL"; then
  echo "Refus : le port configuré de la vraie base est illisible (PMZILLA_LAB_DB_PORT) : corrige-le ou retire-le, puis relance."; exit 2
fi
if [ "$((10#$PORT))" -eq 5432 ] || [ "$((10#$PORT))" -eq "$((10#$PORT_REEL))" ]; then
  echo "Refus : le port $PORT est celui de la vraie base. Les suites avec base ne l'utilisent jamais (donner un autre --port)."; exit 2
fi
for suite in "${SUITES[@]}"; do
  if ! printf '%s' "$suite" | grep -Eq '^[A-Za-z0-9_]+$' || [ ! -d "tests/$suite" ]; then
    echo "Suite inconnue : « $suite » (dossier tests/$suite absent)"; exit 2
  fi
done

# --- Gel pendant une fin de branche (finish-under-lock, D5) : lecture seule du verrou du dossier Git commun, avant tout appel à Docker ---------
# Même règle que tests/run_all.sh : un verrou vivant dont le jeton n'est pas celui de FINISH_LOCK_TOKEN (variable absente comprise) refuse, code 3 ;
# un verrou périmé est ignoré avec une ligne ; le script ne crée, ne retire ni ne change jamais le verrou. Hors dépôt Git : rien.
gel_perime() {   # dossier : 0 si le verrou est périmé, 1 s'il est tenu (même règle que tools/finish_lock.sh)
  local dossier=$1 max="${PMZILLA_FINISH_LOCK_MAX_AGE:-21600}" pid debut mtime age now
  case "$max" in ''|*[!0-9]*) max=21600 ;; esac
  now=$(date +%s)
  pid=$(cat "$dossier/pid" 2>/dev/null)
  case "$pid" in
    ''|*[!0-9]*)
      mtime=$(stat -f %m "$dossier" 2>/dev/null || stat -c %Y "$dossier" 2>/dev/null)
      case "$mtime" in ''|*[!0-9]*) return 1 ;; esac
      [ $(( now - mtime )) -gt 10 ] && return 0
      return 1 ;;
  esac
  kill -0 "$pid" 2>/dev/null || return 0
  debut=$(cat "$dossier/debut" 2>/dev/null)
  case "$debut" in
    ''|*[!0-9]*)
      mtime=$(stat -f %m "$dossier" 2>/dev/null || stat -c %Y "$dossier" 2>/dev/null)
      case "$mtime" in ''|*[!0-9]*) return 1 ;; esac
      age=$(( now - mtime )) ;;
    *) age=$(( now - debut )) ;;
  esac
  [ "$age" -gt "$max" ] && return 0
  return 1
}
GEL_COMMUN=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)   # vide hors dépôt Git
if [ -n "$GEL_COMMUN" ] && [ -d "$GEL_COMMUN/pmzilla-fin-en-cours" ]; then
  if gel_perime "$GEL_COMMUN/pmzilla-fin-en-cours"; then
    echo "dbtest : verrou de fin périmé, ignoré"
  elif [ -z "${FINISH_LOCK_TOKEN:-}" ] || [ "$(cat "$GEL_COMMUN/pmzilla-fin-en-cours/jeton" 2>/dev/null)" != "$FINISH_LOCK_TOKEN" ]; then
    echo "dbtest : fin de branche en cours ($(cat "$GEL_COMMUN/pmzilla-fin-en-cours/branche" 2>/dev/null || echo '?')), lancement refusé"
    exit 3
  fi
fi

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

# --- Empreinte du passage vert (D5) : départ -----------------------------------------------------------------------------------
# Lanceur remplacé sans DBTEST_RECORD (test du script dans le vrai dépôt) : ni lecture ni écriture.
REGISTRE=1
if [ -n "${DBTEST_RUN_ALL:-}" ] && [ -z "${DBTEST_RECORD:-}" ]; then REGISTRE=0; fi
FICHIER_EMPREINTE=""; ARBRE_DEBUT=""; PROPRE_DEBUT=0
if [ "$REGISTRE" -eq 1 ]; then
  ARBRE_DEBUT=$(git rev-parse --verify -q 'HEAD^{tree}' 2>/dev/null) || ARBRE_DEBUT=""
  if [ -n "$ARBRE_DEBUT" ]; then
    if [ -n "${DBTEST_RECORD:-}" ]; then
      FICHIER_EMPREINTE="$DBTEST_RECORD"
    else
      COMMUN=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) && FICHIER_EMPREINTE="$COMMUN/pmzilla-dbtest-ok"
    fi
    # La ligne de l'arbre courant disparaît dès le départ : un passage rouge ensuite ne laisse aucune preuve pour cet arbre.
    if [ -n "$FICHIER_EMPREINTE" ] && [ -f "$FICHIER_EMPREINTE" ] && grep -qx -- "$ARBRE_DEBUT" "$FICHIER_EMPREINTE" 2>/dev/null; then
      ( umask 077; grep -vx -- "$ARBRE_DEBUT" "$FICHIER_EMPREINTE" > "$FICHIER_EMPREINTE.tmp.$$" ) 2>/dev/null
      mv "$FICHIER_EMPREINTE.tmp.$$" "$FICHIER_EMPREINTE" 2>/dev/null || rm -f "$FICHIER_EMPREINTE.tmp.$$"
    fi
    [ -n "$(git status --porcelain 2>/dev/null)" ] || PROPRE_DEBUT=1
  fi
fi

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
# pg_isready tourne DANS le conteneur : il ne prouve pas que le port publié répond depuis l'hôte, seul chemin des suites. Sans cela, les tests de
# base sont sautés, le passage est vert et l'empreinte serait écrite pour rien. Essai TCP depuis l'hôte (aucun client, aucun mot de passe).
sonde_hote() {
  if [ -n "${DBTEST_SONDE:-}" ]; then "$DBTEST_SONDE" "$PORT" >/dev/null 2>&1
  else ( exec 3<>"/dev/tcp/127.0.0.1/$PORT" ) 2>/dev/null; fi
}
HOTE_OK=0; i=0
while [ "$i" -lt "$ATTENTE" ] && [ "$i" -lt 10 ]; do
  if sonde_hote; then HOTE_OK=1; break; fi
  i=$((i + 1)); [ "$i" -lt "$ATTENTE" ] && [ "$i" -lt 10 ] && sleep 1
done

# --- Les suites, une à une, sans tube ---------------------------------------------------------------------------------------
vertes=(); echouees=()
# Chaque suite ne reçoit de l'appelant aucune variable PMZILLA_LAB_DB_* (adresse, mots de passe de rôle, Trousseau) : seulement le port et le mot
# de passe du conteneur, plus DBTEST_PORT, le repère que les tests avec base exigent (test-speed-2, D1 et D3).
RETRAIT=(-u PMZILLA_NO_EVALS -u DBTEST_PORT)
while IFS= read -r variable; do
  [ -n "$variable" ] && RETRAIT+=(-u "$variable")
done < <(compgen -e PMZILLA_LAB_DB_)
for suite in "${SUITES[@]}"; do
  echo
  echo "=== $suite ==="
  if env "${RETRAIT[@]}" PMZILLA_LAB_DB_PASSWORD="$mdp" PMZILLA_LAB_DB_PORT="$PORT" DBTEST_PORT="$PORT" bash "$LANCEUR" "$suite"; then
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

# --- Empreinte du passage vert (D5) : fin. Jamais de changement du code de sortie. -------------------------------------------------
if [ "$REGISTRE" -eq 1 ]; then
  RAISON=""
  if [ -z "$ARBRE_DEBUT" ] || [ -z "$FICHIER_EMPREINTE" ]; then RAISON="hors dépôt Git"
  elif [ "$PAR_DEFAUT" -ne 1 ]; then RAISON="suites choisies"
  elif [ "$HOTE_OK" -ne 1 ]; then RAISON="base injoignable depuis l'hôte"
  elif [ "$PROPRE_DEBUT" -ne 1 ] || [ -n "$(git status --porcelain 2>/dev/null)" ]; then RAISON="arbre non propre"
  elif [ "$(git rev-parse --verify -q 'HEAD^{tree}' 2>/dev/null)" != "$ARBRE_DEBUT" ]; then RAISON="arbre changé pendant le passage"
  elif ( umask 077
         { [ -f "$FICHIER_EMPREINTE" ] && grep -vx -- "$ARBRE_DEBUT" "$FICHIER_EMPREINTE"; printf '%s\n' "$ARBRE_DEBUT"; } > "$FICHIER_EMPREINTE.tmp.$$" ) 2>/dev/null \
       && mv "$FICHIER_EMPREINTE.tmp.$$" "$FICHIER_EMPREINTE" 2>/dev/null; then
    echo "Empreinte dbtest enregistrée : la fin de branche l'acceptera pour cet arbre."
  else
    rm -f "$FICHIER_EMPREINTE.tmp.$$" 2>/dev/null
    RAISON="écriture impossible"
  fi
  [ -z "$RAISON" ] || echo "Empreinte dbtest non écrite ($RAISON)"
fi
exit 0
