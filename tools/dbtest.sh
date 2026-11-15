#!/bin/bash
# PMZilla Lab : lance les suites de tests qui ont besoin d'une base PostgreSQL, sur une instance JETABLE (installation.md, 14.5).
#
#     bash tools/dbtest.sh                          les suites par défaut : db flow_import flow_store flow_views hybrid_search pmzilla_lab_library library_backend cases_store watch_store book_usage dashboard flow_retention posture_evals export_jira_api history_jira story_quality mothra_donnees mothra
#     bash tools/dbtest.sh flow_store flow_import   seulement ces suites (noms de tests/<suite>/, ou d'une suite npm de la ligne SUITES_NPM de tests/run_all.sh, comme « mothra »)
#     bash tools/dbtest.sh --port 55433             port de l'hôte du conteneur (défaut 55432 ; jamais 5432 ni celui de la vraie base)
#     bash tools/dbtest.sh --e2e                    la passe de bout en bout (mothra-slices D12), sans suite nommée : conteneur, migrations, jeu
#                                                   synthétique (tests/mothra_donnees/jeu_synthetique.py), rôle des vues, bundle construit depuis l'arbre
#                                                   par le script build de mothra/, serveur Mothra sur la base jetable (127.0.0.1 seulement, il sert le
#                                                   bundle et l'API), puis bash tests/run_e2e.sh avec DBTEST_PORT ; --port permis
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
#      impossible) ; après un passage rouge, rien n'est dit. La fin de branche (contrôle 14 de tools/finish_checks.py, lu par le train) exige cette ligne quand la
#      branche change le code de la base ; une ligne écrite à la main passe, comme les enregistrements du jeu d'essai (c'est une déclaration).
# Les suites créent elles-mêmes leurs bases pmzilla_test_<hex> et appliquent leurs migrations.
#
# Gel (finish-under-lock, D5) : avant tout conteneur, un verrou de fin de branche vivant d'un autre jeton (FINISH_LOCK_TOKEN) refuse avec le code 3 et
# « dbtest : fin de branche en cours (<branche>), lancement refusé » ; un verrou périmé est dit (« dbtest : verrou de fin périmé, ignoré ») et ignoré.
#
# Mode --e2e (mothra-slices, D12) : même conteneur, même gel (code 3), même règle de port. Il applique les migrations, charge le jeu
# synthétique, pose un mot de passe aléatoire au rôle des vues (jamais affiché ; le serveur ne reçoit que celui-là, jamais celui du
# superutilisateur), CONSTRUIT le bundle depuis l'arbre (npm run build dans mothra/, qui appelle le script build du paquet front), démarre le
# serveur Mothra (node src/main.ts de mothra/server, sur 127.0.0.1, port DBTEST_E2E_PORT_SERVEUR, défaut 3210), attend qu'il écoute, lance
# tests/run_e2e.sh avec DBTEST_PORT, puis arrête le serveur. Aucun serveur de développement Vite n'est démarré. Pendant une fin de branche
# (FINISH_LOCK_TOKEN posée), les scripts de fin retirent toute variable DBTEST_ : le port est toujours 3210 et le
# refus d'un port occupé dit de le libérer.
# Le port du serveur doit être libre : si la sonde y répond avant le lancement, refus (code 2, rien démarré, « Refus : le port <n> répond déjà »).
# Après la sonde et après la
# passe, le serveur doit encore tourner (sinon passe en échec, code 1, aucune empreinte). Ni le serveur ni la construction ne reçoivent de
# variable MOTHRA_* ni PMZILLA_LAB_DB_* de l'appelant. Le mot de passe du rôle des vues est posé par préfixe d'affectation (jamais en
# argument de env) ; limite : celui du superutilisateur passe en argument de env aux seules commandes des migrations et du chargeur. L'empreinte est celle de la
# passe de bout en bout : après une passe verte sur un arbre propre et inchangé, l'arbre de HEAD est ajouté à pmzilla-e2e-ok (dossier Git
# commun, une ligne par arbre, lisible par son propriétaire seul) avec « Empreinte e2e enregistrée » ; sinon rien n'est écrit et les mêmes
# raisons sont dites (« Empreinte e2e non écrite (<raison>) »). La ligne de l'arbre courant disparaît au départ. La fin de branche
# (contrôle 16 de tools/finish_checks.py, lu par le train) exige cette ligne quand un chemin d'interface de Mothra a changé.
#
# Code de sortie : 0 toutes les suites sont vertes (ou la passe de bout en bout est verte) ; 1 une suite au moins échoue, ou le conteneur ne démarre pas
# (--e2e : aussi une migration, le chargement, le serveur ou la passe en échec, ou un serveur arrêté pendant la passe) ; 2 usage incorrect ou
# prérequis absent (rien n'a été démarré ; --e2e : aussi le port du serveur déjà occupé) ;
# 3 une autre fin de branche tient le verrou (rien n'a été démarré) ;
# 4 (--e2e seulement) la construction du bundle échoue : phrase « construction du bundle en échec (code <n>) », <n> étant le code de la commande de
# construction ; ni serveur, ni passe, ni empreinte.
# Une empreinte non écrite ne change jamais le code.
#
# Variables (pour les tests ; DBTEST_PORT est posée par ce script pour les suites, jamais lue de l'appelant) : DBTEST_ATTENTE (secondes max d'attente du conteneur, défaut 120), DBTEST_RUN_ALL (lanceur des suites,
# défaut tests/run_all.sh ; quand il est remplacé et que DBTEST_RECORD ne l'est pas, aucune empreinte n'est lue ni écrite : le test du script
# tourne dans le vrai dépôt et ne touche jamais à son dossier Git), DBTEST_RECORD (autre fichier des empreintes),
# DBTEST_SONDE (commande qui reçoit le port et réussit s'il répond depuis l'hôte ; défaut : essai TCP sur 127.0.0.1).
# Mode --e2e, pour les tests, chacune remplace une étape par un programme unique : DBTEST_E2E_MIGRER, DBTEST_E2E_CHARGEUR, DBTEST_E2E_BUILD
# (construction du bundle), DBTEST_E2E_SERVEUR (reste au premier plan jusqu'à son arrêt), DBTEST_E2E_SONDE_SERVEUR (reçoit le port du serveur,
# réussit s'il écoute) et DBTEST_E2E_PASSE (la passe ; remplace tests/run_e2e.sh). Quand l'une d'elles est posée sans DBTEST_RECORD, aucune
# empreinte n'est lue ni écrite (le test tourne dans le vrai dépôt).
set -uo pipefail
RACINE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RACINE" || exit 2
NOM="pmzilla-lab-test-db"
ATTENTE="${DBTEST_ATTENTE:-120}"
LANCEUR="${DBTEST_RUN_ALL:-tests/run_all.sh}"
SUITES_PAR_DEFAUT=(db flow_import flow_store flow_views hybrid_search pmzilla_lab_library library_backend cases_store watch_store book_usage dashboard flow_retention posture_evals export_jira_api history_jira story_quality mothra_donnees mothra)

PORT="55432"
SUITES=()
E2E=0
while [ $# -gt 0 ]; do
  case "$1" in
    --help|-h) sed -n '2,/^set -uo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit 0 ;;
    --port) [ $# -ge 2 ] || { echo "--port demande un numéro"; exit 2; }; PORT="$2"; shift 2 ;;
    --e2e) E2E=1; shift ;;
    -*) echo "Usage : bash tools/dbtest.sh [--port N] [--e2e | suite ...] [--help]"; exit 2 ;;
    *) SUITES+=("$1"); shift ;;
  esac
done
if [ "$E2E" -eq 1 ] && [ ${#SUITES[@]} -gt 0 ]; then
  echo "--e2e ne se combine pas avec des noms de suites (la passe de bout en bout n'en lance aucune)"; exit 2
fi
PAR_DEFAUT=0
if [ "$E2E" -eq 1 ]; then PAR_DEFAUT=1
else [ ${#SUITES[@]} -gt 0 ] || { SUITES=("${SUITES_PAR_DEFAUT[@]}"); PAR_DEFAUT=1; }; fi
# Libellé et fichier de l'empreinte : celle de la passe de bout en bout est une autre preuve (pmzilla-e2e-ok), avec ses propres phrases.
LIBELLE="dbtest"; NOM_EMPREINTE="pmzilla-dbtest-ok"
if [ "$E2E" -eq 1 ]; then LIBELLE="e2e"; NOM_EMPREINTE="pmzilla-e2e-ok"; fi
PORT_SERVEUR="${DBTEST_E2E_PORT_SERVEUR:-3210}"
# Étapes de la passe de bout en bout (change ci-local-runner, tranche 2, R-20261101-113) : tools/e2e_steps.sh DE CET ARBRE (celui qui lance ce script),
# sourcé seulement avec --e2e. Remplace : le bloc des étapes qui était ici (retrait : permanent, tant que la CI lance les mêmes étapes).
if [ "$E2E" -eq 1 ]; then
  [ -f "$RACINE/tools/e2e_steps.sh" ] || { echo "dbtest : tools/e2e_steps.sh introuvable ; rien n'est démarré"; exit 2; }
  . "$RACINE/tools/e2e_steps.sh"
  E2E_PORT_BASE="$PORT"; E2E_PORT_SERVEUR="$PORT_SERVEUR"; E2E_ATTENTE="$ATTENTE"; E2E_RACINE="$RACINE"
  E2E_CMD_MIGRER="${DBTEST_E2E_MIGRER:-}"; E2E_CMD_CHARGEUR="${DBTEST_E2E_CHARGEUR:-}"; E2E_CMD_BUILD="${DBTEST_E2E_BUILD:-}"
  E2E_CMD_SERVEUR="${DBTEST_E2E_SERVEUR:-}"; E2E_CMD_SONDE="${DBTEST_E2E_SONDE_SERVEUR:-}"; E2E_CMD_PASSE="${DBTEST_E2E_PASSE:-}"
fi

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
if [ "$E2E" -eq 1 ]; then
  if ! port_valide "$PORT_SERVEUR" || [ "$((10#$PORT_SERVEUR))" -eq "$((10#$PORT))" ]; then
    echo "Port du serveur Mothra invalide : $PORT_SERVEUR (DBTEST_E2E_PORT_SERVEUR : décimal simple, différent du port de la base jetable)"; exit 2
  fi
fi
# Une suite npm (mothra-slices, groupe 3) n'a pas de dossier tests/<nom>/ : elle est valable si la ligne SUITES_NPM=(<dossier>:<nom> …) de tests/run_all.sh la déclare.
suite_npm_declaree() {   # nom : 0 si la ligne SUITES_NPM du lanceur de la racine déclare cette suite
  [ -r tests/run_all.sh ] && awk -v nom="$1" '
    /^SUITES_NPM=\(.*\)[ \t]*$/ {
      ligne = $0; sub(/^SUITES_NPM=\(/, "", ligne); sub(/\)[ \t]*$/, "", ligne)
      n = split(ligne, entrees, /[ \t]+/)
      for (i = 1; i <= n; i++) { if (split(entrees[i], p, ":") == 2 && p[2] == nom) trouvee = 1 }
      exit
    }
    END { exit !trouvee }' tests/run_all.sh
}
for suite in ${SUITES[@]+"${SUITES[@]}"}; do
  if ! printf '%s' "$suite" | grep -Eq '^[A-Za-z0-9_]+$' || { [ ! -d "tests/$suite" ] && ! suite_npm_declaree "$suite"; }; then
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
      mtime=$(stat -c %Y "$dossier" 2>/dev/null || stat -f %m "$dossier" 2>/dev/null)
      case "$mtime" in ''|*[!0-9]*) return 1 ;; esac
      [ $(( now - mtime )) -gt 10 ] && return 0
      return 1 ;;
  esac
  kill -0 "$pid" 2>/dev/null || return 0
  debut=$(cat "$dossier/debut" 2>/dev/null)
  case "$debut" in
    ''|*[!0-9]*)
      mtime=$(stat -c %Y "$dossier" 2>/dev/null || stat -f %m "$dossier" 2>/dev/null)
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

# --- Port du serveur Mothra déjà occupé (--e2e) : refus avant tout conteneur ------------------------------------------------------
# La sonde du serveur ne prouve rien si un autre programme écoute déjà sur ce port : elle réussirait pour lui. Si elle répond avant le lancement
# du serveur, la passe est refusée (code 2, rien n'est démarré) ; le port se change avec DBTEST_E2E_PORT_SERVEUR, sauf pendant une fin de branche
# (FINISH_LOCK_TOKEN posée), où les scripts de fin retirent toute variable DBTEST_ : le refus dit alors de libérer le port.
sonde_serveur() { e2e_sonde_serveur; }   # la sonde de tools/e2e_steps.sh (E2E_CMD_SONDE = DBTEST_E2E_SONDE_SERVEUR), sourcé plus haut avec --e2e
if [ "$E2E" -eq 1 ] && sonde_serveur; then
  if [ -n "${FINISH_LOCK_TOKEN:-}" ]; then
    echo "Refus : le port $PORT_SERVEUR du serveur Mothra répond déjà (un autre programme y écoute ?) : pendant une fin de branche, le port ne se change pas ; libère le port $PORT_SERVEUR (arrête le programme qui l'écoute), puis relance la fin. Rien n'est démarré."; exit 2
  fi
  echo "Refus : le port $PORT_SERVEUR répond déjà (un autre programme y écoute ?) : l'arrêter, ou choisir un autre port avec DBTEST_E2E_PORT_SERVEUR. Rien n'est démarré."; exit 2
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
[ "$E2E" -eq 1 ] || [ -f "$LANCEUR" ] || { echo "Lanceur de suites introuvable : $LANCEUR"; exit 2; }

# --- Empreinte du passage vert (D5) : départ -----------------------------------------------------------------------------------
# Lanceur remplacé sans DBTEST_RECORD (test du script dans le vrai dépôt) : ni lecture ni écriture.
REGISTRE=1
if [ "$E2E" -eq 1 ]; then
  if [ -z "${DBTEST_RECORD:-}" ] && { [ -n "${DBTEST_E2E_MIGRER:-}" ] || [ -n "${DBTEST_E2E_CHARGEUR:-}" ] || [ -n "${DBTEST_E2E_BUILD:-}" ] \
       || [ -n "${DBTEST_E2E_SERVEUR:-}" ] || [ -n "${DBTEST_E2E_SONDE_SERVEUR:-}" ] || [ -n "${DBTEST_E2E_PASSE:-}" ]; }; then REGISTRE=0; fi
elif [ -n "${DBTEST_RUN_ALL:-}" ] && [ -z "${DBTEST_RECORD:-}" ]; then REGISTRE=0; fi
FICHIER_EMPREINTE=""; ARBRE_DEBUT=""; PROPRE_DEBUT=0
if [ "$REGISTRE" -eq 1 ]; then
  ARBRE_DEBUT=$(git rev-parse --verify -q 'HEAD^{tree}' 2>/dev/null) || ARBRE_DEBUT=""
  if [ -n "$ARBRE_DEBUT" ]; then
    if [ -n "${DBTEST_RECORD:-}" ]; then
      FICHIER_EMPREINTE="$DBTEST_RECORD"
    else
      COMMUN=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) && FICHIER_EMPREINTE="$COMMUN/$NOM_EMPREINTE"
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
arreter_serveur() {   # le serveur Mothra de la passe de bout en bout (tools/e2e_steps.sh) : arrêté en cas d'échec ou de Ctrl+C aussi
  if [ "$E2E" -eq 1 ]; then e2e_arreter_serveur; fi
}
nettoyer() {
  code=$?
  trap '' INT TERM
  arreter_serveur
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
if ! POSTGRES_PASSWORD="$mdp" PGPASSWORD="$mdp" docker run -d --name "$NOM" --label pmzilla-lab-test=1 \
     --shm-size "$SHM" -e POSTGRES_PASSWORD -e PGPASSWORD -e POSTGRES_DB=pmzilla \
     -e "POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256 --auth-local=scram-sha-256" -p "127.0.0.1:$PORT:5432" "$IMAGE" >/dev/null 2>&1; then
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
# Le serveur Mothra et la construction du bundle ne reçoivent aucune variable MOTHRA_* de l'appelant (hôte, hôte de base, seuil, port, nom de
# base, adresse de la passe : toute la configuration du serveur vient d'ici) ; ce script repose seulement celles dont il a besoin. Leurs listes
# de retraits (build, serveur, passe) sont celles de e2e_retraits (tools/e2e_steps.sh) ; la liste RETRAIT ci-dessus ne sert plus qu'aux suites.
while IFS= read -r variable; do
  [ -n "$variable" ] || continue
  RETRAIT+=(-u "$variable")
done < <(compgen -e PMZILLA_LAB_DB_)
while IFS= read -r variable; do
  [ -n "$variable" ] || continue
  RETRAIT+=(-u "$variable")
done < <(compgen -e MOTHRA_)

# --- Passe de bout en bout (--e2e, mothra-slices D12) : migrations, jeu synthétique, rôle des vues, bundle, serveur, passe ------------------
# Chaque étape est une commande propre (remplaçable par un programme pour les tests). Le superutilisateur de la base jetable ne sert qu'aux
# migrations et au chargeur ; le serveur ne reçoit que les mots de passe du rôle des vues et du rôle de stockage, posés ici et jamais affichés.
E2E_VERT=0
if [ "$E2E" -eq 1 ]; then
  set +x   # aucune trace des secrets, même si l'appelant a activé xtrace (avant toute affectation d'un secret)
  E2E_VARIABLES_BASE=(PMZILLA_LAB_DB_PASSWORD="$mdp" PMZILLA_LAB_DB_PORT="$PORT" DBTEST_PORT="$PORT" PMZILLA_LAB_DB_SECURITY_BIN=/usr/bin/false)
  # La fonction SQL de dbtest : le SQL (avec le mot de passe d'un rôle) arrive sur l'entrée standard de psql, dans le conteneur jetable (R-20261101-113).
  # Base en scram (POSTGRES_INITDB_ARGS) : psql reçoit PGPASSWORD de l'environnement du conteneur, posé à sa création (docker run -e PGPASSWORD, sans
  # valeur en argument) ; un docker exec hérite de cet environnement, donc la ligne de commande de l'exec reste sans mot de passe ni option -e.
  e2e_sql() { docker exec -i "$NOM" psql -v ON_ERROR_STOP=1 -q -h 127.0.0.1 -U postgres -d pmzilla >/dev/null 2>&1; }
  e2e_retraits
  if e2e_enchainer; then
    E2E_VERT=1
  else
    # Les phrases et les codes de dbtest : 4 pour la construction du bundle, 1 pour les autres échecs (le serveur a déjà dit sa phrase).
    case "$E2E_CAUSE" in
      "construction du bundle") echo "construction du bundle en échec (code $E2E_RC)"; exit 4 ;;
      serveur) exit 1 ;;
      passe) ;;
      *) echo "dbtest : $E2E_CAUSE en échec (code $E2E_RC)"; exit 1 ;;
    esac
  fi
  mdp=""
  echo
  if [ "$E2E_VERT" -ne 1 ]; then echo "Passe de bout en bout en échec"; exit 1; fi
  echo "Passe de bout en bout verte"
fi
for suite in ${SUITES[@]+"${SUITES[@]}"}; do   # tableau vide : « set -u » de bash 3.2 (macOS) refuse "${SUITES[@]}" nu
  echo
  echo "=== $suite ==="
  if env "${RETRAIT[@]}" PMZILLA_LAB_DB_PASSWORD="$mdp" PMZILLA_LAB_DB_PORT="$PORT" DBTEST_PORT="$PORT" bash "$LANCEUR" "$suite"; then
    vertes+=("$suite")
  else
    echouees+=("$suite")
  fi
done
mdp=""

if [ "$E2E" -ne 1 ]; then
  echo
  echo "Suites vertes : ${vertes[*]:-aucune}"
  echo "Suites en échec : ${echouees[*]:-aucune}"
  if [ ${#echouees[@]} -gt 0 ]; then exit 1; fi
fi

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
    echo "Empreinte $LIBELLE enregistrée : la fin de branche l'acceptera pour cet arbre."
  else
    rm -f "$FICHIER_EMPREINTE.tmp.$$" 2>/dev/null
    RAISON="écriture impossible"
  fi
  [ -z "$RAISON" ] || echo "Empreinte $LIBELLE non écrite ($RAISON)"
fi
exit 0
