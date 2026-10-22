#!/bin/bash
# PMZilla Lab : test de restauration de la base PostgreSQL, dans un conteneur jetable (à refaire une fois par trimestre).
#
#     bash tools/db_restore_test.sh                      restaure la dernière sauvegarde db-AAAA-MM-JJ
#     bash tools/db_restore_test.sh --backup <dossier>   restaure ce dossier de sauvegarde (un .dump par schéma)
#     bash tools/db_restore_test.sh --detail             affiche aussi les erreurs de pg_restore (peuvent citer des valeurs)
#     bash tools/db_restore_test.sh --port N             port de l'hôte du conteneur jetable (jamais 5432 ni celui de la vraie base)
#
# Ce que fait le script :
#   1. cherche la dernière sauvegarde dans le dossier des sauvegardes (« sauvegardes » sous PMZILLA_LAB_DATA, soit
#      ~/.pmzilla-lab/sauvegardes par défaut, comme tools/db_backup.sh ; dossier db-AAAA-MM-JJ) ;
#   2. démarre un conteneur JETABLE (même image fixée et même shm_size que docker-compose.yml, nom unique, port 127.0.0.1 choisi par Docker, mot
#      de passe aléatoire propre au conteneur : le mot de passe de la vraie base n'est ni lu ni utilisé) ;
#   3. applique les migrations (uv run tools/db.py migrate : rôles, extensions, schémas), car les sauvegardes sont faites par
#      schéma (pg_dump -n) et ne contiennent ni les rôles, ni les extensions, ni public.schema_migrations ; puis restaure
#      chaque schéma avec pg_restore, après l'avoir VIDÉ (DROP SCHEMA IF EXISTS … CASCADE, dans le conteneur jetable seulement) : une
#      sauvegarde faite avant une migration ne contient pas les tables ajoutées depuis (ex. la 0007, veille et pré-tri), et le DROP SCHEMA
#      sans CASCADE de pg_restore --clean échouerait (« cannot drop schema … because other objects depend on it ») ;
#   3 bis. restaure le dump partiel quality-sans-texte.dump (données seulement) dans les trois tables vides de quality (attributs d'équipe,
#      relectures, versions de surcouche) ; absent ou en échec : code 1 (une sauvegarde antérieure au dump partiel est signalée) ;
#   4. compare le nombre de lignes par table (knowledge, cases, flow, public.schema_migrations) avec la vraie base, lue en COMPTES
#      seulement (docker compose exec, socket locale, aucune valeur lue) ;
#   5. compare l'empreinte des migrations : fichiers de db/migrations/ (sha256, comme tools/db.py), base restaurée, vraie base ;
#   5 bis. après une restauration réussie, chronomètre un REINDEX INDEX de chacun des trois index BM25 (knowledge.chunks_bm25,
#      cases.cases_bm25, cases.experiments_bm25) dans le conteneur jetable, et affiche la durée de chacun puis le total, estimation du
#      REINDEX de la vraie base après une montée de l'image (un index absent est signalé et compté 0, sans échec) ;
#   6. supprime le conteneur jetable à la fin, même en cas d'erreur ou d'interruption.
#
# La vraie base n'est jamais modifiée et aucune sauvegarde n'est faite. Le script n'affiche que des noms de tables et des comptes.
# Un écart de lignes est attendu si la vraie base a changé depuis la sauvegarde : il est signalé mais ne fait pas échouer.
# Une table que la sauvegarde ne contient pas (migration postérieure à la sauvegarde) est signalée MANQUE et fait échouer le test : le
# vidage rend la restauration possible, il ne masque pas l'écart.
# Code de sortie : 0 tout est cohérent ; 1 restauration en échec, table manquante ou empreinte des migrations différente ;
# 2 prérequis absent ou usage incorrect (rien n'a été restauré).
#
# Variables (pour les tests) : DB_BACKUP_SAUVEGARDES (dossier des sauvegardes, comme db_backup.sh ; défaut : « sauvegardes » sous
# PMZILLA_LAB_DATA, par tools/lab_paths.sh), PMZILLA_LAB_DATA (dossier de données du labo, défaut ~/.pmzilla-lab), DB_RESTORE_SCHEMAS
# (défaut : knowledge cases flow), DB_RESTORE_ATTENTE (secondes max d'attente du conteneur, défaut 120).
set -uo pipefail
RACINE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RACINE" || exit 2
# Dossiers du lab : le module partagé tools/lab_paths.sh (comme db_backup.sh) ; sinon code 78, avant tout pas.
. "$RACINE/tools/lab_paths.sh"
lab_paths_init || exit $?
DEST="$LAB_BACKUPS_FOLDER"   # DB_BACKUP_SAUVEGARDES, sinon <dossier de données du labo>/sauvegardes (tools/lab_paths.sh)
SCHEMAS="${DB_RESTORE_SCHEMAS:-knowledge cases flow}"
ATTENTE="${DB_RESTORE_ATTENTE:-120}"
for schema in $SCHEMAS; do
  printf '%s' "$schema" | grep -Eq '^[a-z_][a-z0-9_]*$' || { echo "Nom de schéma invalide : « $schema » (minuscules, chiffres et tiret bas seulement)"; exit 2; }
done
PREFIXE="pmzilla-lab-restore-test"

SAUVEGARDE=""; PORT_DEMANDE=""; DETAIL=0
while [ $# -gt 0 ]; do
  case "$1" in
    --help|-h) sed -n '2,/^set -uo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit 0 ;;
    --backup) [ $# -ge 2 ] || { echo "--backup demande un dossier"; exit 2; }; SAUVEGARDE="$2"; shift 2 ;;
    --port) [ $# -ge 2 ] || { echo "--port demande un numéro"; exit 2; }; PORT_DEMANDE="$2"; shift 2 ;;
    --detail) DETAIL=1; shift ;;
    *) echo "Usage : bash tools/db_restore_test.sh [--backup <dossier>] [--port N] [--detail] [--help]"; exit 2 ;;
  esac
done

# --- Refus de viser la vraie base -------------------------------------------------------------------------------------
# Une seule règle de port (test-db-guards, D1) : forme décimale simple (chiffres ASCII, sans signe, sans espace, sans zéro en tête, de 1 à
# 65535), comparée en nombre ; un port configuré de la vraie base défini et illisible est refusé (code 2).
port_valide() { local LC_ALL=C; [[ "$1" =~ ^[1-9][0-9]{0,4}$ ]] && [ "$((10#$1))" -le 65535 ]; }
PORT_REEL="${PMZILLA_LAB_DB_PORT:-5432}"
if ! port_valide "$PORT_REEL"; then
  echo "Refus : le port configuré de la vraie base est illisible (PMZILLA_LAB_DB_PORT) : corrige-le ou retire-le, puis relance."; exit 2
fi
if [ -n "$PORT_DEMANDE" ]; then
  if ! port_valide "$PORT_DEMANDE"; then echo "Port invalide : $PORT_DEMANDE"; exit 2; fi
  if [ "$((10#$PORT_DEMANDE))" -eq 5432 ] || [ "$((10#$PORT_DEMANDE))" -eq "$((10#$PORT_REEL))" ]; then
    echo "Refus : le port $PORT_DEMANDE est celui de la vraie base. Le test de restauration n'utilise jamais ce port (laisser Docker en choisir un, ou donner un autre --port)."; exit 2
  fi
fi

# --- Sauvegarde à restaurer ---------------------------------------------------------------------------------------------
if [ -z "$SAUVEGARDE" ]; then
  derniere="$(ls -1 "$DEST" 2>/dev/null | grep -E '^db-[0-9]{4}-[0-9]{2}-[0-9]{2}$' | sort | tail -1)"
  if [ -z "$derniere" ]; then
    echo "Aucune sauvegarde db-AAAA-MM-JJ dans $DEST. En faire une : bash tools/db_backup.sh (ou désigner un dossier : --backup <dossier>)"; exit 2
  fi
  SAUVEGARDE="$DEST/$derniere"
fi
if [ ! -d "$SAUVEGARDE" ]; then echo "Dossier de sauvegarde introuvable : $SAUVEGARDE"; exit 2; fi
if ! ls "$SAUVEGARDE"/*.dump >/dev/null 2>&1; then echo "Aucun fichier .dump dans $SAUVEGARDE"; exit 2; fi

# --- Prérequis ------------------------------------------------------------------------------------------------------------
command -v docker >/dev/null 2>&1 || { echo "Docker est introuvable (brew install colima docker docker-compose)"; exit 2; }
command -v uv >/dev/null 2>&1 || { echo "uv est introuvable (nécessaire pour appliquer les migrations : uv run tools/db.py migrate)"; exit 2; }
if ! docker info >/dev/null 2>&1; then
  echo "Docker ne répond pas. Vérifier Colima : colima status (puis colima start --cpu 4 --memory 6)"; exit 2
fi
if [ -z "$(docker compose ps -q --status running db 2>/dev/null)" ]; then
  echo "Le conteneur de la vraie base est arrêté : le test compare avec elle. Le démarrer : bash tools/db_up.sh"; exit 2
fi
if ! docker compose exec -T db pg_isready -U postgres -d pmzilla >/dev/null 2>&1; then
  echo "Le conteneur de la vraie base tourne mais PostgreSQL ne répond pas. Voir : docker compose ps, docker compose logs db"; exit 2
fi
. "$RACINE/tools/db_container_common.sh"   # image fixée et shm_size du compose, partagés avec tools/db_rehearsal.sh
IMAGE="$(db_compose_image docker-compose.yml)"
case "$IMAGE" in
  */*:[0-9]*) ;;
  *) echo "Image de docker-compose.yml introuvable ou non fixée : « $IMAGE »"; exit 2 ;;
esac
SHM="$(db_compose_shm docker-compose.yml)"   # 64 Mo par défaut de Docker sinon, trop peu pour l'index BM25 ; repli 1g
if command -v shasum >/dev/null 2>&1; then SHA() { shasum -a 256 "$1" | cut -d' ' -f1; }
elif command -v sha256sum >/dev/null 2>&1; then SHA() { sha256sum "$1" | cut -d' ' -f1; }
else echo "shasum et sha256sum sont introuvables"; exit 2; fi

TMP="$(mktemp -d)" || exit 2
NOM="$PREFIXE-$$-$RANDOM"
CONTENEUR=""
nettoyer() {
  code=$?
  trap '' INT TERM
  if [ -n "$CONTENEUR" ]; then
    docker rm -f -v "$CONTENEUR" >/dev/null 2>&1
    if [ -n "$(docker ps -a -q --filter "name=^${CONTENEUR}\$" 2>/dev/null)" ]; then
      echo "ATTENTION : le conteneur jetable $CONTENEUR existe encore ; le supprimer : docker rm -f -v $CONTENEUR"
    else
      echo "Conteneur jetable supprimé : $CONTENEUR"
    fi
  fi
  rm -rf "$TMP"
  exit "$code"
}
trap nettoyer EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "Sauvegarde restaurée : $SAUVEGARDE"
echo "Image du conteneur jetable : $IMAGE (celle de docker-compose.yml)"

# --- Conteneur jetable : mot de passe aléatoire propre au conteneur, passé par l'environnement de la seule commande ----------
mdp_jetable="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
if [ -z "$mdp_jetable" ]; then echo "Impossible de générer le mot de passe du conteneur jetable"; exit 2; fi
if [ -n "$PORT_DEMANDE" ]; then PUBLICATION="127.0.0.1:$PORT_DEMANDE:5432"; else PUBLICATION="127.0.0.1::5432"; fi
if POSTGRES_PASSWORD="$mdp_jetable" docker run -d --name "$NOM" --label pmzilla-lab-restore-test=1 \
     --shm-size "$SHM" -e POSTGRES_PASSWORD -e POSTGRES_DB=pmzilla -p "$PUBLICATION" "$IMAGE" >/dev/null 2>"$TMP/run.err"; then
  CONTENEUR="$NOM"
else
  CONTENEUR="$NOM"   # le nettoyage tente quand même la suppression
  echo "Impossible de démarrer le conteneur jetable $NOM (image absente ? réseau ? port pris ?)"; exit 1
fi
PORT_JETABLE="$(docker port "$CONTENEUR" 5432/tcp 2>/dev/null | head -1 | sed -E 's/.*:([0-9]+)$/\1/')"
if ! port_valide "$PORT_JETABLE"; then echo "Port du conteneur jetable introuvable"; exit 1; fi
if [ "$((10#$PORT_JETABLE))" -eq 5432 ] || [ "$((10#$PORT_JETABLE))" -eq "$((10#$PORT_REEL))" ]; then
  echo "Refus : le conteneur jetable écoute sur le port $PORT_JETABLE, celui de la vraie base. Rien n'a été restauré."; exit 1
fi
echo "Conteneur jetable : $CONTENEUR (127.0.0.1:$PORT_JETABLE, jamais le port de la vraie base)"

pret=0; i=0
while [ "$i" -lt "$ATTENTE" ]; do
  if docker exec "$CONTENEUR" pg_isready -h 127.0.0.1 -U postgres -d pmzilla >/dev/null 2>&1; then pret=1; break; fi
  i=$((i + 2)); sleep 2
done
if [ "$pret" -ne 1 ]; then echo "Le conteneur jetable n'est pas prêt après ${ATTENTE} s. Voir : docker logs $CONTENEUR"; exit 1; fi

# --- Migrations sur la base jetable (rôles, extensions, schémas, public.schema_migrations) -------------------------------------
echo "Migrations sur la base jetable :"
if ! PMZILLA_LAB_DB_URL="postgresql://postgres@127.0.0.1:$PORT_JETABLE/pmzilla" PMZILLA_LAB_DB_PASSWORD="$mdp_jetable" \
     PMZILLA_LAB_DB_SECURITY_BIN="$(command -v false || echo /usr/bin/false)" uv run tools/db.py migrate 2>&1 | sed 's/^/  /'; then
  echo "ÉCHEC : les migrations ne s'appliquent pas sur la base jetable"; exit 1
fi
mdp_jetable=""

# --- Restauration, un schéma à la fois ---------------------------------------------------------------------------------------
echec=0
echo "Restauration :"
for schema in $SCHEMAS; do
  fichier="$SAUVEGARDE/$schema.dump"
  if [ ! -s "$fichier" ]; then echo "  ÉCHEC $schema : fichier $schema.dump absent ou vide"; echec=1; continue; fi
  # Vidage du schéma dans le conteneur jetable (jamais la vraie base : docker exec sur le nom du conteneur créé plus haut, jamais compose).
  # Aucun objet d'un autre schéma ne dépend de knowledge, cases ou flow : le CASCADE n'emporte que le schéma visé (tests/db/test_restore_knowledge.py).
  case "$CONTENEUR" in "$PREFIXE"-*) ;; *) echo "Refus : le conteneur visé n'est pas un conteneur jetable"; exit 1 ;; esac
  if ! docker exec "$CONTENEUR" psql -U postgres -d pmzilla -v ON_ERROR_STOP=1 -c "DROP SCHEMA IF EXISTS $schema CASCADE" > /dev/null 2> "$TMP/vidage-$schema.err"; then
    echo "  ÉCHEC $schema : le vidage du schéma dans le conteneur jetable a échoué (détail masqué, relancer avec --detail)"
    [ "$DETAIL" -eq 1 ] && sed 's/^/    /' "$TMP/vidage-$schema.err" | head -10
    echec=1; continue
  fi
  if docker exec -i "$CONTENEUR" pg_restore -U postgres -d pmzilla --clean --if-exists --exit-on-error --single-transaction \
       < "$fichier" > /dev/null 2> "$TMP/restore-$schema.err"; then
    echo "  OK $schema"
  else
    echo "  ÉCHEC $schema : pg_restore a échoué (détail masqué, il peut citer des valeurs ; relancer avec --detail). Une sauvegarde antérieure à une migration peut ne pas se restaurer sur la base migrée : essayer une sauvegarde plus récente ou une autre avec --backup <dossier>"
    [ "$DETAIL" -eq 1 ] && sed 's/^/    /' "$TMP/restore-$schema.err" | head -10
    echec=1
  fi
done

# Dump partiel de quality (change story-quality-audit, D10) : données seulement, dans les trois tables vides recréées par les migrations
# (aucune clé étrangère vers une table hors du dump : tests/db/test_quality_dump_coherence.py). Jamais le schéma quality entier, jamais de DROP.
fichier="$SAUVEGARDE/quality-sans-texte.dump"
if [ "$echec" -ne 0 ]; then
  echo "  quality-sans-texte non tenté : une restauration de schéma a échoué"
elif [ ! -s "$fichier" ]; then
  echo "  ÉCHEC quality-sans-texte : fichier quality-sans-texte.dump absent ou vide"
  echo "  (la sauvegarde précède probablement le dump partiel de quality : en faire une nouvelle avec bash tools/db_backup.sh)"; echec=1
elif docker exec -i "$CONTENEUR" pg_restore -U postgres -d pmzilla --data-only --exit-on-error --single-transaction \
       < "$fichier" > /dev/null 2> "$TMP/restore-quality.err"; then
  echo "  OK quality-sans-texte"
else
  echo "  ÉCHEC quality-sans-texte : pg_restore a échoué (détail masqué, il peut citer des valeurs ; relancer avec --detail)"
  [ "$DETAIL" -eq 1 ] && sed 's/^/    /' "$TMP/restore-quality.err" | head -10
  echec=1
fi

# --- Comptes par table (noms et comptes seulement) ---------------------------------------------------------------------------
REQUETE_COMPTES="select schemaname || '.' || tablename || '|' || (xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I.%I', schemaname, tablename), false, true, '')))[1]::text from pg_tables where schemaname in ($(printf "'%s'," $SCHEMAS quality | sed 's/,$//')) or (schemaname = 'public' and tablename = 'schema_migrations') order by 1"
FILTRE='^[A-Za-z0-9_]+\.[A-Za-z0-9_]+\|[0-9]+$'
REQUETE_MIGRATIONS="select numero || '|' || nom || '|' || empreinte from public.schema_migrations order by numero"
docker compose exec -T db psql -U postgres -d pmzilla -At -c "$REQUETE_COMPTES" 2>/dev/null | grep -E "$FILTRE" > "$TMP/reel.txt"
docker exec "$CONTENEUR" psql -U postgres -d pmzilla -At -c "$REQUETE_COMPTES" 2>/dev/null | grep -E "$FILTRE" > "$TMP/restauree.txt"
if [ ! -s "$TMP/reel.txt" ]; then echo "Aucun compte lu sur la vraie base (lecture de pg_tables en échec)."; exit 2; fi
if [ ! -s "$TMP/restauree.txt" ]; then echo "ÉCHEC : aucune table lue sur la base restaurée"; exit 1; fi

echo "Lignes par table (restaurée / vraie base) :"
awk -F'|' -v OFS='|' 'NR==FNR{r[$1]=$2; n[$1]=1; next} {s[$1]=$2; n[$1]=1}
  END{for(k in n){ if(!(k in s)) print k,"MANQUE","-",r[k]; else if(!(k in r)) print k,"EN_PLUS",s[k],"-";
       else if(s[k]==r[k]) print k,"OK",s[k],r[k]; else print k,"ECART",s[k],r[k]}}' "$TMP/reel.txt" "$TMP/restauree.txt" | sort > "$TMP/comparaison.txt"
manque=0; ecarts=0; vides=0; ecarts_quality=0
while IFS='|' read -r table etat restauree reelle; do
  case "$etat" in
    OK) printf '  %-34s %10s / %-10s OK\n' "$table" "$restauree" "$reelle" ;;
    ECART)
      case "$table" in
        quality.team_attributes|quality.team_reviews|quality.overlay_versions) ;;   # restaurées par le dump partiel : comparées comme toute table
        quality.*)   # autres tables de quality (R-78, D10) : jamais sauvegardées, recréées vides par les migrations ; l'écart est attendu, jamais un échec
          diff=$((restauree - reelle)); [ "$diff" -gt 0 ] && diff="+$diff"
          printf '  %-34s %10s / %-10s écart %s (attendu : cette table de quality n'"'"'est jamais sauvegardée, elle est recréée vide)\n' "$table" "$restauree" "$reelle" "$diff"
          ecarts_quality=$((ecarts_quality + 1))
          continue ;;
      esac
      diff=$((restauree - reelle)); [ "$diff" -gt 0 ] && diff="+$diff"
      printf '  %-34s %10s / %-10s écart %s (attendu possible si la vraie base a changé depuis la sauvegarde)\n' "$table" "$restauree" "$reelle" "$diff"
      ecarts=$((ecarts + 1)); [ "$restauree" -eq 0 ] && vides=$((vides + 1)) ;;
    MANQUE) printf '  %-34s %10s / %-10s MANQUE dans la base restaurée\n' "$table" "$restauree" "$reelle"; manque=$((manque + 1)) ;;
    EN_PLUS) printf '  %-34s %10s / %-10s absente de la vraie base (information)\n' "$table" "$restauree" "$reelle" ;;
  esac
done < "$TMP/comparaison.txt"
[ "$manque" -gt 0 ] && echec=1

# --- Empreinte des migrations ----------------------------------------------------------------------------------------------
for f in db/migrations/*.sql; do
  [ -e "$f" ] || continue
  nom="$(basename "$f")"; numero="$((10#${nom%%_*}))"
  echo "$numero|$nom|$(SHA "$f")"
done > "$TMP/fichiers.txt"
docker exec "$CONTENEUR" psql -U postgres -d pmzilla -At -c "$REQUETE_MIGRATIONS" 2>/dev/null | grep -E '^[0-9]+\|[^|]+\|[0-9a-f]{64}$' > "$TMP/migrations-restauree.txt"
docker compose exec -T db psql -U postgres -d pmzilla -At -c "$REQUETE_MIGRATIONS" 2>/dev/null | grep -E '^[0-9]+\|[^|]+\|[0-9a-f]{64}$' > "$TMP/migrations-reelle.txt"
empreinte() { if [ -s "$1" ]; then SHA "$1" | cut -c1-12; else echo "(vide)"; fi; }
ef="$(empreinte "$TMP/fichiers.txt")"; er="$(empreinte "$TMP/migrations-restauree.txt")"; ev="$(empreinte "$TMP/migrations-reelle.txt")"
echo "Empreinte des migrations (sha256 des numéros, noms et empreintes, 12 premiers caractères) :"
echo "  fichiers db/migrations/ : $ef ($(wc -l < "$TMP/fichiers.txt" | tr -d ' ') migrations)"
echo "  base restaurée          : $er ($(wc -l < "$TMP/migrations-restauree.txt" | tr -d ' ') migrations)"
echo "  vraie base              : $ev ($(wc -l < "$TMP/migrations-reelle.txt" | tr -d ' ') migrations)"
empreinte_ok=1
if [ ! -s "$TMP/fichiers.txt" ] || ! cmp -s "$TMP/fichiers.txt" "$TMP/migrations-restauree.txt" || ! cmp -s "$TMP/fichiers.txt" "$TMP/migrations-reelle.txt"; then
  empreinte_ok=0; echec=1
  echo "  ÉCHEC : l'empreinte des migrations diffère. Migrations en désaccord (numéro et nom seulement) :"
  { cut -d'|' -f1,2 "$TMP/fichiers.txt" | sed 's/^/F|/'; cut -d'|' -f1,2 "$TMP/migrations-restauree.txt" | sed 's/^/R|/'; cut -d'|' -f1,2 "$TMP/migrations-reelle.txt" | sed 's/^/V|/'; } \
    | awk -F'|' '{n[$2"|"$3]=n[$2"|"$3] $1} END{for(k in n) if (n[k] != "FRV") print k, "(présente dans : " n[k] ")"}' \
    | sort | sed 's/^/    /'
  echo "    F = fichiers, R = base restaurée, V = vraie base. Un nom présent partout avec une empreinte différente signale un fichier modifié après application."
else
  echo "  OK : même empreinte partout"
fi

# --- Durée de reconstruction des index BM25 (R-88) ---------------------------------------------------------------------------
# Après une restauration réussie seulement : un REINDEX INDEX par index BM25, chronométré dans le conteneur jetable (docker exec sur le
# conteneur créé plus haut, jamais docker compose : la vraie base n'est pas touchée). Le total estime le REINDEX de la vraie base après une
# montée de l'image. Un index absent (schéma sans données) est signalé et compté 0 ; un REINDEX en échec aussi (détail masqué) : ni l'un ni
# l'autre ne change le code de sortie.
if [ "$echec" -eq 0 ]; then
  case "$CONTENEUR" in "$PREFIXE"-*) ;; *) echo "Refus : le conteneur visé n'est pas un conteneur jetable"; exit 1 ;; esac
  total_reindex=0
  for index in knowledge.chunks_bm25 cases.cases_bm25 cases.experiments_bm25; do
    present="$(docker exec "$CONTENEUR" psql -U postgres -d pmzilla -At -c "select to_regclass('$index') is not null" 2>/dev/null | grep -E '^[tf]$' | head -1)"
    if [ "$present" != "t" ]; then
      echo "index BM25 $index : absent de la base restaurée (schéma sans données), compté 0 s"
      continue
    fi
    debut="$(date +%s)"
    if docker exec "$CONTENEUR" psql -U postgres -d pmzilla -v ON_ERROR_STOP=1 -c "SET max_parallel_maintenance_workers = 0" -c "REINDEX INDEX $index" > /dev/null 2> "$TMP/reindex.err"; then
      duree=$(( $(date +%s) - debut ))
      total_reindex=$((total_reindex + duree))
      echo "durée de reconstruction de l'index BM25 $index : $duree s"
    else
      echo "index BM25 $index : REINDEX en échec dans le conteneur jetable (détail masqué, relancer avec --detail), compté 0 s"
      [ "$DETAIL" -eq 1 ] && sed 's/^/    /' "$TMP/reindex.err" | head -10
    fi
  done
  echo "durée totale de reconstruction des index BM25 : $total_reindex s (estimation du REINDEX de la vraie base)"
fi

# --- Bilan ---------------------------------------------------------------------------------------------------------------------
echo "Bilan :"
if [ "$echec" -ne 0 ]; then
  echo "  ÉCHEC : restauration en échec, table manquante ou empreinte des migrations différente (voir ci-dessus). Une sauvegarde qui ne se restaure pas n'en est pas une."
  exit 1
fi
if [ "$ecarts" -gt 0 ]; then
  echo "  RESTAURATION OK, $ecarts table(s) avec un écart de lignes : attendu possible si la vraie base a changé depuis la sauvegarde ($(basename "$SAUVEGARDE"))."
  [ "$vides" -gt 0 ] && echo "  ATTENTION : $vides table(s) restaurée(s) à 0 ligne alors que la vraie base en contient : à examiner (sauvegarde faite avant l'import ?)."
else
  echo "  RESTAURATION OK, comptes identiques, empreinte des migrations identique."
fi
[ "$ecarts_quality" -gt 0 ] && echo "  Schéma quality : $ecarts_quality table(s) avec un écart de lignes, attendu : ces tables ne sont jamais sauvegardées (le contenu des stories ne vit que dans la base)."
exit 0
