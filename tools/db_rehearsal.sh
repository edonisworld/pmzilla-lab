#!/bin/bash
# PMZilla Lab : copie de répétition vide de la base PostgreSQL, dans un conteneur à part (change flow-rebuild-rehearsal, R-86, design D3 et D11).
#
#     bash tools/db_rehearsal.sh up                 démarre la copie de répétition (port choisi par Docker, boucle locale)
#     bash tools/db_rehearsal.sh up --port N        idem, sur le port N de la boucle locale (jamais 5432 ni celui de la vraie base)
#     bash tools/db_rehearsal.sh status             dit si une copie de répétition existe (nom, port, création)
#     bash tools/db_rehearsal.sh down               supprime la copie de répétition avec son volume
#
# Ce que fait `up` :
#   1. refuse dans une session Claude Code, puis lit les mots de passe dans l'environnement de l'appelant (noms de tools/db.py : le
#      superutilisateur PMZILLA_LAB_DB_PASSWORD, le rôle d'import PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW, le rôle des vues
#      PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW_VIEWS) ; aucun n'est affiché, écrit dans un fichier ni mis dans un argument ;
#   2. démarre UN conteneur de l'image fixée de docker-compose.yml (même shm_size), au nom unique pmzilla-lab-rehearsal-…, étiquette
#      pmzilla-lab-rehearsal=1, port publié sur 127.0.0.1 seulement ; le superutilisateur y reçoit son mot de passe par l'environnement ;
#   3. applique les migrations (uv run tools/db.py migrate, Trousseau neutralisé), sans restaurer, vider ni supprimer aucune donnée :
#      le schéma flow de la copie est la structure des migrations, sans ligne ;
#   4. active la connexion des deux rôles (import et vues) dans la copie seulement : ALTER ROLE … LOGIN PASSWORD, SQL envoyé sur l'entrée
#      standard de psql (jamais dans un argument). L'export, l'import et la reconstruction se connectent
#      sous le rôle d'import avec le mot de passe de ce rôle (db.connect(role=...)) ; seule la conservation (flow_retention.py) se
#      connecte en superutilisateur puis fait SET ROLE ;
#   5. affiche chaque table de flow avec son nombre de lignes (toutes à 0) et compare l'empreinte des migrations (fichiers, copie, vraie
#      base lue en lecture seule, comme tools/db_restore_test.sh).
# Après un échec, la copie est supprimée avec son volume. Après un succès, elle reste en place jusqu'à `down`.
# La vraie base n'est jamais modifiée : seulement listée, testée (pg_isready) et lue pour l'empreinte des migrations. Le Trousseau n'est pas lu.
# À lancer par l'utilisateur seul, dans le Terminal (refusé dans une session Claude Code).
# Code de sortie : 0 copie prête, listée ou supprimée ; 1 démarrage, attente, migration, table non vide, empreinte différente, port de la vraie base publié ou reste après down ; 2 usage, variable absente, port refusé, copie déjà présente, Docker ou vraie base indisponible ; 3 session Claude Code.
#
# Variable (pour les tests) : DB_REHEARSAL_ATTENTE (secondes max d'attente de la copie, défaut 120).
set -uo pipefail

# --- Session Claude Code : refus avant toute lecture et tout Docker ------------------------------------------------------------
if [ -n "${CLAUDECODE:-}" ]; then echo "Refusé dans une session Claude Code"; exit 3; fi

RACINE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RACINE" || exit 2
PREFIXE="pmzilla-lab-rehearsal"
ETIQUETTE="pmzilla-lab-rehearsal=1"
USAGE="Usage : bash tools/db_rehearsal.sh up [--port N] | status | down"

# --- Usage ---------------------------------------------------------------------------------------------------------------------
SOUS="${1:-}"; PORT_DEMANDE=""
case "$SOUS" in
  --help|-h) sed -n '2,/^set -uo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit 0 ;;
  up)
    shift
    while [ $# -gt 0 ]; do
      case "$1" in
        --port) [ $# -ge 2 ] || { echo "--port demande un numéro"; exit 2; }; PORT_DEMANDE="$2"; shift 2 ;;
        *) echo "$USAGE"; exit 2 ;;
      esac
    done ;;
  status|down) [ $# -eq 1 ] || { echo "$USAGE"; exit 2; } ;;
  *) echo "$USAGE"; exit 2 ;;
esac

# --- Docker ---------------------------------------------------------------------------------------------------------------------
command -v docker >/dev/null 2>&1 || { echo "Docker est introuvable (brew install colima docker docker-compose)"; exit 2; }
if ! docker info >/dev/null 2>&1; then
  echo "Docker ne répond pas. Vérifier Colima : colima status (puis colima start --cpu 4 --memory 6)"; exit 2
fi

# Conteneurs de répétition : étiquette ET préfixe de nom. Une ligne par conteneur : nom|création|ports.
liste_copies() {
  docker ps -a --filter "label=$ETIQUETTE" --format '{{.Names}}|{{.CreatedAt}}|{{.Ports}}' 2>/dev/null | grep -E "^${PREFIXE}-[0-9]+-[0-9]+\|" || true
}
existe() { [ -n "$(docker ps -a -q --filter "name=^${1}\$" 2>/dev/null)" ]; }

# --- status ----------------------------------------------------------------------------------------------------------------------
if [ "$SOUS" = "status" ]; then
  copies="$(liste_copies)"
  if [ -z "$copies" ]; then echo "aucune copie de répétition"; exit 0; fi
  while IFS='|' read -r nom cree ports; do
    port="$(printf '%s' "$ports" | sed -nE 's/.*127\.0\.0\.1:([0-9]+)->.*/\1/p' | head -1)"
    echo "copie de répétition : $nom (127.0.0.1:${port:-?}), créée le $cree"
  done <<< "$copies"
  exit 0
fi

# --- down ------------------------------------------------------------------------------------------------------------------------
if [ "$SOUS" = "down" ]; then
  copies="$(liste_copies | cut -d'|' -f1)"
  if [ -z "$copies" ]; then echo "aucune copie de répétition à supprimer"; exit 0; fi
  reste=0
  while IFS= read -r nom; do
    docker rm -f -v "$nom" >/dev/null 2>&1
    if existe "$nom"; then
      echo "ATTENTION : la copie $nom existe encore ; la supprimer : docker rm -f -v $nom"; reste=1
    else
      echo "copie de répétition supprimée : $nom"
    fi
  done <<< "$copies"
  exit "$reste"
fi

# --- up : variables, port ---------------------------------------------------------------------------------------------------------
for variable in PMZILLA_LAB_DB_PASSWORD PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW_VIEWS; do
  if [ -z "${!variable:-}" ]; then echo "variable absente : $variable (valeur jamais affichée)"; exit 2; fi
done
# Une seule règle de port (test-db-guards, D1) : forme décimale simple (chiffres ASCII, sans signe, sans espace, sans zéro en tête, de 1 à
# 65535), comparée en nombre ; un port configuré de la vraie base défini et illisible est refusé (code 2).
port_valide() { local LC_ALL=C; [[ "$1" =~ ^[1-9][0-9]{0,4}$ ]] && [ "$((10#$1))" -le 65535 ]; }
PORT_REEL="${PMZILLA_LAB_DB_PORT:-5432}"
if ! port_valide "$PORT_REEL"; then
  echo "Refus : le port configuré de la vraie base est illisible (PMZILLA_LAB_DB_PORT) : corrige-le ou retire-le, puis relance."; exit 2
fi
if [ -n "$PORT_DEMANDE" ]; then
  if ! port_valide "$PORT_DEMANDE"; then echo "Port invalide : $PORT_DEMANDE"; exit 2; fi
  if [ "$((10#$PORT_DEMANDE))" -eq 5432 ] || [ "$((10#$PORT_DEMANDE))" -eq "$((10#$PORT_REEL))" ]; then echo "Refus : le port $PORT_DEMANDE est celui de la vraie base."; exit 2; fi
fi

# --- up : prérequis ---------------------------------------------------------------------------------------------------------------
command -v uv >/dev/null 2>&1 || { echo "uv est introuvable (nécessaire pour appliquer les migrations : uv run tools/db.py migrate)"; exit 2; }
if [ -z "$(docker compose ps -q --status running db 2>/dev/null)" ]; then
  echo "Le conteneur de la vraie base est arrêté : la copie compare avec elle. Le démarrer : bash tools/db_up.sh"; exit 2
fi
if ! docker compose exec -T db pg_isready -U postgres -d pmzilla >/dev/null 2>&1; then
  echo "Le conteneur de la vraie base tourne mais PostgreSQL ne répond pas. Voir : docker compose ps, docker compose logs db"; exit 2
fi
existante="$(liste_copies | cut -d'|' -f1 | head -1)"
if [ -n "$existante" ]; then
  echo "une copie de répétition existe déjà : $existante ; la supprimer : bash tools/db_rehearsal.sh down"; exit 2
fi
. "$RACINE/tools/db_container_common.sh"   # image fixée et shm_size du compose, partagés avec tools/db_restore_test.sh
IMAGE="$(db_compose_image docker-compose.yml)"
case "$IMAGE" in
  */*:[0-9]*) ;;
  *) echo "Image de docker-compose.yml introuvable ou non fixée : « $IMAGE »"; exit 2 ;;
esac
SHM="$(db_compose_shm docker-compose.yml)"
if command -v shasum >/dev/null 2>&1; then SHA() { shasum -a 256 "$1" | cut -d' ' -f1; }
elif command -v sha256sum >/dev/null 2>&1; then SHA() { sha256sum "$1" | cut -d' ' -f1; }
else echo "shasum et sha256sum sont introuvables"; exit 2; fi
ATTENTE="${DB_REHEARSAL_ATTENTE:-120}"
printf '%s' "$ATTENTE" | grep -Eq '^[0-9]+$' || ATTENTE=120

# --- up : nettoyage après échec ou interruption -------------------------------------------------------------------------------------
NOM="$PREFIXE-$$-$RANDOM"
CONTENEUR=""
nettoyer() {
  code=$?
  trap '' INT TERM
  if [ -n "$CONTENEUR" ] && existe "$CONTENEUR"; then
    docker rm -f -v "$CONTENEUR" >/dev/null 2>&1
    if existe "$CONTENEUR"; then
      echo "ATTENTION : la copie $CONTENEUR existe encore ; la supprimer : docker rm -f -v $CONTENEUR"
    else
      echo "copie de répétition supprimée après échec : $CONTENEUR"
    fi
  fi
  exit "$code"
}
trap nettoyer EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# --- up : conteneur --------------------------------------------------------------------------------------------------------------
if [ -n "$PORT_DEMANDE" ]; then PUBLICATION="127.0.0.1:$PORT_DEMANDE:5432"; else PUBLICATION="127.0.0.1::5432"; fi
CONTENEUR="$NOM"   # le nettoyage ne supprime que si le conteneur existe
if ! POSTGRES_PASSWORD="$PMZILLA_LAB_DB_PASSWORD" docker run -d --name "$NOM" --label "$ETIQUETTE" \
     --shm-size "$SHM" -e POSTGRES_PASSWORD -e POSTGRES_DB=pmzilla -p "$PUBLICATION" "$IMAGE" >/dev/null 2>&1; then
  echo "ÉCHEC : le conteneur de la copie ne démarre pas"; exit 1
fi
PORT_COPIE="$(docker port "$NOM" 5432/tcp 2>/dev/null | head -1 | sed -E 's/.*:([0-9]+)$/\1/')"
if ! port_valide "$PORT_COPIE"; then echo "ÉCHEC : port de la copie introuvable"; exit 1; fi
if [ "$((10#$PORT_COPIE))" -eq 5432 ] || [ "$((10#$PORT_COPIE))" -eq "$((10#$PORT_REEL))" ]; then echo "Refus : le port $PORT_COPIE est celui de la vraie base."; exit 1; fi

pret=0; i=0
while [ "$i" -lt "$ATTENTE" ]; do
  if docker exec "$NOM" pg_isready -h 127.0.0.1 -U postgres -d pmzilla >/dev/null 2>&1; then pret=1; break; fi
  i=$((i + 1)); sleep 1
done
if [ "$pret" -ne 1 ]; then echo "ÉCHEC : la copie n'est pas prête après ${ATTENTE} s"; exit 1; fi

# --- up : migrations (Trousseau neutralisé par une commande qui échoue), sans mot de passe dans l'adresse ---------------------------
sortie="$(PMZILLA_LAB_DB_URL="postgresql://postgres@127.0.0.1:$PORT_COPIE/pmzilla" \
          PMZILLA_LAB_DB_SECURITY_BIN="$(command -v false || echo /usr/bin/false)" uv run tools/db.py migrate 2>&1)" || {
  echo "ÉCHEC : les migrations ne s'appliquent pas sur la copie"; exit 1; }
echo "Migrations :"
printf '%s\n' "$sortie" | grep -E '^Appliquée : [A-Za-z0-9_.-]+$' | sed 's/^/  /'
sortie=""

# --- up : connexion des deux rôles, dans la copie seulement -----------------------------------------------------------------------
# SQL sur l'entrée standard (printf est interne au shell : le mot de passe n'est ni un argument ni dans la liste des processus).
mdp_flow="${PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW//\'/\'\'}"
mdp_vues="${PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW_VIEWS//\'/\'\'}"
if ! printf "ALTER ROLE pmzilla_flow LOGIN PASSWORD '%s';\nALTER ROLE pmzilla_flow_views LOGIN PASSWORD '%s';\n" "$mdp_flow" "$mdp_vues" \
     | docker exec -i "$NOM" psql -U postgres -d pmzilla -v ON_ERROR_STOP=1 -q >/dev/null 2>&1; then
  mdp_flow=""; mdp_vues=""
  echo "ÉCHEC : la connexion des rôles n'a pas pu être activée dans la copie"; exit 1
fi
mdp_flow=""; mdp_vues=""

# --- up : tables de flow, toutes vides --------------------------------------------------------------------------------------------
REQUETE_COMPTES="select schemaname || '.' || tablename || '|' || (xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I.%I', schemaname, tablename), false, true, '')))[1]::text from pg_tables where schemaname = 'flow' order by 1"
comptes="$(docker exec "$NOM" psql -U postgres -d pmzilla -At -c "$REQUETE_COMPTES" 2>/dev/null | grep -E '^flow\.[a-z_]+\|[0-9]+$' || true)"
if [ -z "$comptes" ]; then echo "ÉCHEC : aucune table du schéma flow lue dans la copie"; exit 1; fi
TABLES="Tables du schéma flow :"; non_vides=""
while IFS='|' read -r table lignes; do
  TABLES="$TABLES"$'\n'"  $table $lignes"
  [ "$lignes" -ne 0 ] && non_vides="$non_vides $table"
done <<< "$comptes"
if [ -n "$non_vides" ]; then
  echo "$TABLES"
  for table in $non_vides; do echo "ÉCHEC : table non vide dans la copie : $table"; done
  exit 1
fi

# --- up : empreinte des migrations (fichiers, copie, vraie base lue en lecture seule) -------------------------------------------------
REQUETE_MIGRATIONS="select numero || '|' || nom || '|' || empreinte from public.schema_migrations order by numero"
FILTRE_MIGRATIONS='^[0-9]+\|[^|]+\|[0-9a-f]{64}$'
fichiers=""
for f in db/migrations/*.sql; do
  [ -e "$f" ] || continue
  nom_f="$(basename "$f")"
  fichiers="$fichiers$((10#${nom_f%%_*}))|$nom_f|$(SHA "$f")"$'\n'
done
migrations_copie="$(docker exec "$NOM" psql -U postgres -d pmzilla -At -c "$REQUETE_MIGRATIONS" 2>/dev/null | grep -E "$FILTRE_MIGRATIONS" || true)"
migrations_reelle="$(docker compose exec -T db psql -U postgres -d pmzilla -At -c "$REQUETE_MIGRATIONS" 2>/dev/null | grep -E "$FILTRE_MIGRATIONS" || true)"
if [ -z "$migrations_reelle" ]; then echo "ÉCHEC : empreinte de la vraie base illisible"; exit 2; fi
if [ -z "$fichiers" ] || [ "${fichiers%$'\n'}" != "$migrations_copie" ] || [ "${fichiers%$'\n'}" != "$migrations_reelle" ]; then
  echo "ÉCHEC : l'empreinte des migrations diffère entre la copie et la vraie base"; exit 1
fi

# --- up : succès, la copie reste en place ---------------------------------------------------------------------------------------------
CONTENEUR=""
echo "copie de répétition prête : $NOM (127.0.0.1:$PORT_COPIE), schéma flow vide"
echo "adresse : postgresql://postgres@127.0.0.1:$PORT_COPIE/pmzilla (sans mot de passe)"
echo "$TABLES"
exit 0
