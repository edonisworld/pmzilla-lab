#!/bin/bash
# Test de tools/db_restore_test.sh : faux docker, faux uv et faux security en tête du PATH, sauvegarde fabriquée dans un
# dossier temporaire. Aucun appel à la vraie base, au Trousseau, à Docker ni au réseau.
# Lancement à la main : bash tests/db_scripts/test_db_restore_test.sh (appelé aussi par test_db_scripts.sh)
set -u
racine="$(cd "$(dirname "$0")/../.." && pwd)"
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
bin="$tmp/bin"; mkdir -p "$bin"
ok=0; ko=0
verifie() { # description  code (0 = vrai)
  if [ "$2" -eq 0 ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1"; ko=$((ko+1)); fi
}
absent() { ! grep -q -- "$1" "$2"; echo $?; }   # 0 si le motif est absent du fichier

export FX="$tmp/fx"; mkdir -p "$FX"
export FAUX_LOG="$tmp/log"; : > "$FAUX_LOG"
MDP_REEL="mot-de-passe-reel-sentinelle-7c1e"
BRUIT="CLE-SECRETE-42"      # ligne parasite que les faux psql intercalent : elle ne doit jamais ressortir

# Faux security : doit ne jamais être appelé (le test n'utilise pas le mot de passe de la vraie base).
cat > "$bin/security" <<SCRIPT
#!/bin/bash
echo "security \$*" >> "\$FAUX_LOG"; echo "$MDP_REEL"
SCRIPT
cat > "$bin/uv" <<'SCRIPT'
#!/bin/bash
echo "uv $* | URL=${PMZILLA_LAB_DB_URL:-} | PW=${PMZILLA_LAB_DB_PASSWORD:-} | SEC=${PMZILLA_LAB_DB_SECURITY_BIN:-}" >> "$FAUX_LOG"
[ "${FAUX_UV_ECHEC:-0}" = "1" ] && { echo "Connexion à la base impossible"; exit 1; }
echo "Appliquée : 0001_schemas_roles_extensions.sql"; exit 0
SCRIPT
cat > "$bin/docker" <<'SCRIPT'
#!/bin/bash
echo "docker $* | PW=${POSTGRES_PASSWORD:-}" >> "$FAUX_LOG"
args="$*"
[ "${1:-}" = "info" ] && exit 0
if [ "${1:-}" = "compose" ]; then
  case "$args" in
    *"ps -q"*) echo abc123; exit 0 ;;
    *pg_isready*) exit 0 ;;
    *psql*)
      echo "$BRUIT_FAUX"
      case "$args" in *"schema_migrations order"*) cat "$FX/mig-reelle" ;; *) cat "$FX/comptes-reels" ;; esac
      exit 0 ;;
  esac
  exit 0
fi
case "${1:-}" in
  run)
    nom=""; prev=""
    for a in "$@"; do [ "$prev" = "--name" ] && nom="$a"; prev="$a"; done
    [ "${FAUX_RUN_ECHEC:-0}" = "1" ] && { echo "Unable to find image" >&2; exit 125; }
    echo "$nom" >> "$FX/conteneurs"; echo "id-$nom"; exit 0 ;;
  port) echo "127.0.0.1:${FAUX_PORT:-49153}"; exit 0 ;;
  rm) for a in "$@"; do case "$a" in pmzilla-lab-restore-test-*) grep -vx "$a" "$FX/conteneurs" > "$FX/c.tmp"; mv "$FX/c.tmp" "$FX/conteneurs" ;; esac; done; exit 0 ;;
  ps) while read -r n; do echo "id-$n"; done < "$FX/conteneurs"; exit 0 ;;
  exec)
    case "$args" in
      *pg_isready*) exit "${FAUX_PRET:-0}" ;;
      *pg_restore*)
        contenu="$(cat)"
        case "$contenu" in *"DUMP ${FAUX_RESTORE_ECHEC:-aucun}"*) echo "COPY flow.issues: $BRUIT_FAUX" >&2; exit 1 ;; esac
        exit 0 ;;
      *"DROP SCHEMA"*) [ "${FAUX_DROP_ECHEC:-0}" = "1" ] && { echo "ERROR: drop: $BRUIT_FAUX" >&2; exit 1; }; exit 0 ;;
      *psql*)
        echo "$BRUIT_FAUX"
        case "$args" in *"schema_migrations order"*) cat "$FX/mig-restauree" ;; *) cat "$FX/comptes-restaures" ;; esac
        exit 0 ;;
    esac ;;
esac
exit 0
SCRIPT
chmod +x "$bin/security" "$bin/uv" "$bin/docker"
export BRUIT_FAUX="$BRUIT"
export PATH="$bin:$PATH"
export HOME="$tmp/home"; mkdir -p "$HOME"
unset PMZILLA_LAB_DB_PASSWORD PMZILLA_LAB_DB_PORT PMZILLA_LAB_DB_URL POSTGRES_PASSWORD
export DB_RESTORE_ATTENTE=4

# Sauvegarde fabriquée par le test (contenu factice, un fichier par schéma comme db_backup.sh).
sauv="$tmp/sauvegardes"; mkdir -p "$sauv/db-2026-09-01" "$sauv/db-2026-10-08"
for d in db-2026-09-01 db-2026-10-08; do for s in knowledge cases flow; do echo "DUMP $s" > "$sauv/$d/$s.dump"; done; done
export DB_BACKUP_SAUVEGARDES="$sauv"

# Données de référence : mêmes comptes des deux côtés, empreintes calculées sur les vrais fichiers de migration.
etat_nominal() {
  cat > "$FX/comptes-reels" <<'EOF'
cases.cases|3
flow.issues|120
flow.transitions|900
knowledge.passages|5000
public.schema_migrations|3
EOF
  cp "$FX/comptes-reels" "$FX/comptes-restaures"
  : > "$FX/mig-reelle"
  for f in "$racine"/db/migrations/*.sql; do
    nom="$(basename "$f")"; echo "$((10#${nom%%_*}))|$nom|$(shasum -a 256 "$f" | cut -d' ' -f1)" >> "$FX/mig-reelle"
  done
  cp "$FX/mig-reelle" "$FX/mig-restauree"
  : > "$FX/conteneurs"; : > "$FAUX_LOG"
}
lance() { bash "$racine/tools/db_restore_test.sh" "$@" > "$tmp/s" 2>&1; code=$?; }

# --- aide et usage
etat_nominal
lance --help
verifie "restore : --help code 0 et décrit --backup" "$([ $code -eq 0 ] && grep -q -- '--backup' "$tmp/s" && grep -q 'jetable' "$tmp/s"; echo $?)"
verifie "restore : --help ne touche pas à Docker" "$([ ! -s "$FAUX_LOG" ]; echo $?)"
lance --bidon
verifie "restore : option inconnue refusée (code 2)" "$([ $code -eq 2 ]; echo $?)"

# --- aucune sauvegarde
etat_nominal; vide="$tmp/vide"; mkdir -p "$vide"
DB_BACKUP_SAUVEGARDES="$vide" lance
verifie "restore : sans sauvegarde, refus clair (code 2) qui renvoie à db_backup.sh" "$([ $code -eq 2 ] && grep -q 'Aucune sauvegarde db-AAAA-MM-JJ' "$tmp/s" && grep -q 'db_backup.sh' "$tmp/s"; echo $?)"
verifie "restore : sans sauvegarde, aucun conteneur démarré" "$(absent 'docker run' "$FAUX_LOG")"
lance --backup "$tmp/inexistant"
verifie "restore : --backup vers un dossier inexistant refusé (code 2)" "$([ $code -eq 2 ] && grep -q 'introuvable' "$tmp/s"; echo $?)"

# --- succès : dernière sauvegarde, nettoyage, aucun accès à la vraie base en écriture
etat_nominal
lance
verifie "restore : succès, code 0" "$([ $code -eq 0 ] && grep -q 'RESTAURATION OK' "$tmp/s"; echo $?)"
verifie "restore : la dernière sauvegarde (db-2026-10-08) est choisie" "$(grep -q 'Sauvegarde restaurée : .*db-2026-10-08' "$tmp/s"; echo $?)"
mkdir -p "$sauv/db-2026-10-08-matin" "$sauv/db-2026-10-09-essai"
for d in db-2026-10-08-matin db-2026-10-09-essai; do for s in knowledge cases flow; do echo "DUMP $s" > "$sauv/$d/$s.dump"; done; done
etat_nominal
lance
verifie "restore : les dossiers avec étiquette (db-AAAA-MM-JJ-matin) sont ignorés, db-2026-10-08 est choisi" "$(grep -q 'Sauvegarde restaurée : .*/db-2026-10-08$' "$tmp/s"; echo $?)"
rm -rf "$sauv/db-2026-10-08-matin" "$sauv/db-2026-10-09-essai"
etat_nominal
lance
verifie "restore : conteneur jetable supprimé après succès" "$([ ! -s "$FX/conteneurs" ] && grep -q 'rm -f -v pmzilla-lab-restore-test-' "$FAUX_LOG" && grep -q 'Conteneur jetable supprimé' "$tmp/s"; echo $?)"
verifie "restore : les trois schémas sont restaurés" "$([ "$(grep -c 'exec -i pmzilla-lab-restore-test-.* pg_restore' "$FAUX_LOG")" = 3 ]; echo $?)"
verifie "restore : comptes identiques signalés OK" "$(grep -q 'flow.issues .*OK' "$tmp/s" && grep -q 'comptes identiques' "$tmp/s"; echo $?)"

# --- jamais la vraie base : image fixée, port non publié en 5432, commandes compose en lecture seule
run_ligne="$(grep '^docker run' "$FAUX_LOG" | head -1)"
image_compose="$(grep -E '^[[:space:]]+image:' "$racine/docker-compose.yml" | head -1 | sed -E 's/^[[:space:]]+image:[[:space:]]*//')"
verifie "restore : conteneur jetable de l'image fixée du compose" "$(printf '%s' "$run_ligne" | grep -q -- "$image_compose"; echo $?)"
verifie "restore : nom unique préfixé, distinct du conteneur de la vraie base" "$(printf '%s' "$run_ligne" | grep -Eq -- '--name pmzilla-lab-restore-test-[0-9]+-[0-9]+'; echo $?)"
verifie "restore : port choisi par Docker sur 127.0.0.1, jamais 5432:5432" "$(printf '%s' "$run_ligne" | grep -q -- '-p 127.0.0.1::5432' && ! printf '%s' "$run_ligne" | grep -q '5432:5432'; echo $?)"
verifie "restore : ni compose up/down/restore, ni écriture sur la vraie base (compose limité à ps, pg_isready, psql)" "$(grep '^docker compose' "$FAUX_LOG" | sed 's/ | PW=.*//' | grep -Ev '^docker compose (ps -q|exec -T db pg_isready|exec -T db psql)' | grep -q .; [ $? -ne 0 ]; echo $?)"
verifie "restore : aucune requête d'écriture sur la vraie base" "$(grep '^docker compose exec' "$FAUX_LOG" | grep -Eqi 'insert|update|delete|drop|truncate|alter|create'; [ $? -ne 0 ]; echo $?)"
verifie "restore : pg_restore jamais lancé sur la vraie base" "$(grep '^docker compose' "$FAUX_LOG" | grep -q pg_restore; [ $? -ne 0 ]; echo $?)"
verifie "restore : migrations sur la base jetable (port jetable, pas 5432, Trousseau neutralisé)" "$(grep '^uv run tools/db.py migrate' "$FAUX_LOG" | grep -q 'URL=postgresql://postgres@127.0.0.1:49153/pmzilla' && ! grep '^uv ' "$FAUX_LOG" | grep -q ':5432' && grep '^uv ' "$FAUX_LOG" | grep -Eq 'SEC=.*false'; echo $?)"
verifie "restore : le Trousseau n'est pas lu, le mot de passe de la vraie base n'est jamais utilisé" "$(grep -q '^security' "$FAUX_LOG"; [ $? -ne 0 ]; echo $?)"
mdp_jetable="$(grep '^uv ' "$FAUX_LOG" | sed -E 's/.*\| PW=([^ ]*) .*/\1/')"
verifie "restore : mot de passe jetable aléatoire, passé par l'environnement, pas en argument" "$([ ${#mdp_jetable} -ge 16 ] && grep '^docker run' "$FAUX_LOG" | grep -q "| PW=$mdp_jetable\$" && ! grep '^docker' "$FAUX_LOG" | sed 's/ | PW=.*//' | grep -q "$mdp_jetable"; echo $?)"

# --- sortie : seulement des noms de tables et des comptes
verifie "restore : la sortie ne contient aucune valeur parasite ni mot de passe" "$(grep -q "$BRUIT" "$tmp/s"; r1=$?; grep -q "$MDP_REEL" "$tmp/s"; r2=$?; grep -q "$mdp_jetable" "$tmp/s"; r3=$?; [ $r1 -ne 0 ] && [ $r2 -ne 0 ] && [ $r3 -ne 0 ]; echo $?)"
verifie "restore : les lignes de comptes ne portent que table, deux nombres et un statut" "$(grep -E '^  (cases|flow|knowledge|public)\.' "$tmp/s" | grep -Evq '^  [a-z_]+\.[a-z_]+ +[0-9]+ / [0-9]+ +OK$'; [ $? -ne 0 ]; echo $?)"

# --- schéma vidé dans le conteneur jetable avant pg_restore (R-22 : knowledge a plus de tables que la sauvegarde)
etat_nominal
lance
verifie "restore : chaque schéma est vidé (DROP SCHEMA IF EXISTS … CASCADE) dans le conteneur jetable, juste avant son pg_restore" "$(
  suite="$(grep -E '^docker exec (-i )?pmzilla-lab-restore-test-.*(DROP SCHEMA|pg_restore)' "$FAUX_LOG" | sed -E 's/^docker exec (-i )?pmzilla-lab-restore-test-[0-9]+-[0-9]+ .*DROP SCHEMA IF EXISTS ([a-z_]+) CASCADE.*/D:\2/; s/^docker exec -i .*pg_restore.*/R/' | tr '\n' ' ')"
  [ "$suite" = "D:knowledge R D:cases R D:flow R " ]; echo $?)"
verifie "restore : le vidage ne vise que le conteneur jetable (jamais docker compose)" "$(! grep '^docker compose' "$FAUX_LOG" | grep -qi 'drop'; echo $?)"
verifie "restore : le vidage précède la restauration mais les migrations restent appliquées avant (uv avant le premier DROP)" "$([ "$(grep -n '^uv ' "$FAUX_LOG" | head -1 | cut -d: -f1)" -lt "$(grep -n 'DROP SCHEMA' "$FAUX_LOG" | head -1 | cut -d: -f1)" ]; echo $?)"
verifie "restore : pg_restore garde --clean --if-exists --exit-on-error --single-transaction" "$(grep -q 'pg_restore -U postgres -d pmzilla --clean --if-exists --exit-on-error --single-transaction' "$FAUX_LOG"; echo $?)"
etat_nominal
FAUX_DROP_ECHEC=1 lance
verifie "restore : vidage en échec, code 1, schéma nommé, pg_restore non lancé, valeurs masquées" "$([ $code -eq 1 ] && grep -q 'ÉCHEC knowledge' "$tmp/s" && ! grep -q 'pg_restore' "$FAUX_LOG" && ! grep -q "$BRUIT" "$tmp/s" && [ ! -s "$FX/conteneurs" ]; echo $?)"
etat_nominal
DB_RESTORE_SCHEMAS='knowledge; drop table x' lance
verifie "restore : nom de schéma invalide refusé (code 2) avant tout conteneur" "$([ $code -eq 2 ] && grep -q 'Nom de schéma invalide' "$tmp/s" && ! grep -q 'docker run' "$FAUX_LOG"; echo $?)"

# --- /dev/shm du conteneur jetable : shm_size lu dans docker-compose.yml (R-22), jamais recopié ; repli 1g
etat_nominal; lance
shm_reel="$(grep -E '^[[:space:]]+shm_size:' "$racine/docker-compose.yml" | head -1 | sed -E 's/^[[:space:]]+shm_size:[[:space:]]*//; s/[#].*$//; s/["[:space:]]//g')"
verifie "restore : docker run reçoit --shm-size avec la valeur de shm_size du compose réel" "$([ -n "$shm_reel" ] && grep '^docker run' "$FAUX_LOG" | grep -q -- "--shm-size $shm_reel "; echo $?)"
racine_shm() {   # $1 = ligne shm_size du compose factice (vide : aucune)
  rm -rf "$tmp/root"; mkdir -p "$tmp/root/tools" "$tmp/root/db"
  cp "$racine/tools/db_restore_test.sh" "$tmp/root/tools/"; cp -R "$racine/db/migrations" "$tmp/root/db/"
  { grep -v 'shm_size' "$racine/docker-compose.yml"; [ -n "$1" ] && echo "    $1"; } > "$tmp/root/docker-compose.yml"
  etat_nominal; bash "$tmp/root/tools/db_restore_test.sh" > "$tmp/s" 2>&1; code=$?
}
racine_shm "shm_size: 2gb  # commentaire"
verifie "restore : la valeur vient du compose (2gb), commentaire retiré" "$(grep '^docker run' "$FAUX_LOG" | grep -q -- '--shm-size 2gb '; echo $?)"
racine_shm ""
verifie "restore : sans shm_size dans le compose, repli 1g" "$(grep '^docker run' "$FAUX_LOG" | grep -q -- '--shm-size 1g '; echo $?)"
racine_shm "shm_size: grand; rm -rf /"
verifie "restore : shm_size illisible, repli 1g (la valeur n'est jamais passée telle quelle)" "$(grep '^docker run' "$FAUX_LOG" | grep -q -- '--shm-size 1g ' && ! grep -q 'rm -rf' "$FAUX_LOG"; echo $?)"

# --- écart de lignes : attendu possible, code 0
etat_nominal; sed -i.bak 's/^flow.issues|120/flow.issues|100/' "$FX/comptes-restaures"
lance
verifie "restore : écart de lignes affiché avec sa valeur, signalé comme attendu possible, code 0" "$([ $code -eq 0 ] && grep -q 'flow.issues .*100 / 120 .*écart -20 (attendu possible' "$tmp/s"; echo $?)"

# --- table manquante
etat_nominal; grep -v '^flow.transitions' "$FX/comptes-restaures" > "$FX/c"; mv "$FX/c" "$FX/comptes-restaures"
lance
verifie "restore : table manquante, code 1 et nom de la table" "$([ $code -eq 1 ] && grep -q 'flow.transitions .*MANQUE' "$tmp/s"; echo $?)"
verifie "restore : table manquante, conteneur quand même supprimé" "$([ ! -s "$FX/conteneurs" ]; echo $?)"

# --- empreinte des migrations
etat_nominal; sed -i.bak '$ s/[0-9a-f]\{64\}$/0000000000000000000000000000000000000000000000000000000000000000/' "$FX/mig-restauree"
lance
verifie "restore : empreinte différente côté base restaurée, code 1" "$([ $code -eq 1 ] && grep -q "l'empreinte des migrations diffère" "$tmp/s"; echo $?)"
verifie "restore : empreinte différente, conteneur supprimé" "$([ ! -s "$FX/conteneurs" ]; echo $?)"
etat_nominal; sed -i.bak '$ d' "$FX/mig-reelle"
lance
verifie "restore : migration absente de la vraie base, code 1, nom de la migration listé" "$([ $code -eq 1 ] && grep -q "l'empreinte des migrations diffère" "$tmp/s" && grep -Eq '^    [0-9]+\|[0-9a-z_]+\.sql' "$tmp/s"; echo $?)"

# --- nettoyage après échec
etat_nominal
FAUX_RESTORE_ECHEC=cases lance
verifie "restore : pg_restore en échec, code 1, schéma nommé" "$([ $code -eq 1 ] && grep -q 'ÉCHEC cases' "$tmp/s"; echo $?)"
verifie "restore : pg_restore en échec, le message suggère une sauvegarde antérieure à une migration et --backup" "$(grep -q 'antérieure à une migration' "$tmp/s" && grep -q -- '--backup' "$tmp/s"; echo $?)"
verifie "restore : pg_restore en échec, conteneur supprimé" "$([ ! -s "$FX/conteneurs" ] && grep -q 'rm -f -v pmzilla-lab-restore-test-' "$FAUX_LOG"; echo $?)"
verifie "restore : le détail de pg_restore (qui peut citer des valeurs) est masqué par défaut" "$(grep -q "$BRUIT" "$tmp/s"; [ $? -ne 0 ]; echo $?)"
etat_nominal
FAUX_RESTORE_ECHEC=cases lance --detail
verifie "restore : --detail affiche les erreurs de pg_restore" "$(grep -q "$BRUIT" "$tmp/s"; echo $?)"
etat_nominal
FAUX_UV_ECHEC=1 lance
verifie "restore : migrations en échec, code 1, conteneur supprimé" "$([ $code -eq 1 ] && [ ! -s "$FX/conteneurs" ] && grep -q 'rm -f -v' "$FAUX_LOG"; echo $?)"
etat_nominal
FAUX_RUN_ECHEC=1 lance
verifie "restore : démarrage du conteneur en échec, code 1, suppression tentée" "$([ $code -eq 1 ] && grep -q 'Impossible de démarrer' "$tmp/s" && grep -q 'rm -f -v' "$FAUX_LOG"; echo $?)"
etat_nominal
rm "$sauv/db-2026-10-08/flow.dump"
lance
verifie "restore : fichier .dump d'un schéma absent, code 1, conteneur supprimé" "$([ $code -eq 1 ] && grep -q 'flow.dump absent' "$tmp/s" && [ ! -s "$FX/conteneurs" ]; echo $?)"
echo "DUMP flow" > "$sauv/db-2026-10-08/flow.dump"

# --- interruption (SIGTERM) pendant l'attente du conteneur
etat_nominal
FAUX_PRET=1 DB_RESTORE_ATTENTE=40 bash "$racine/tools/db_restore_test.sh" > "$tmp/s" 2>&1 &
pid=$!
for _ in 1 2 3 4 5 6 7 8 9 10; do [ -s "$FX/conteneurs" ] && break; sleep 0.5; done
kill -TERM "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; code=$?
verifie "restore : interruption (SIGTERM), code non nul et conteneur jetable supprimé" "$([ $code -ne 0 ] && [ ! -s "$FX/conteneurs" ] && grep -q 'Conteneur jetable supprimé' "$tmp/s"; echo $?)"

# --- délai d'attente du conteneur jetable : message d'échec et code 1 quand il ne devient jamais prêt
etat_nominal
FAUX_PRET=1 DB_RESTORE_ATTENTE=1 lance
verifie "restore : conteneur jamais prêt, code 1 et message nommant le délai (1 s) et docker logs" "$([ $code -eq 1 ] && grep -q "n'est pas prêt après 1 s" "$tmp/s" && grep -q 'docker logs pmzilla-lab-restore-test-' "$tmp/s"; echo $?)"
verifie "restore : conteneur jamais prêt, rien n'est restauré ni migré et le conteneur est supprimé" "$(! grep -q 'pg_restore' "$FAUX_LOG" && ! grep -q '^uv ' "$FAUX_LOG" && [ ! -s "$FX/conteneurs" ]; echo $?)"
verifie "restore : le délai par défaut est de 120 s (DB_RESTORE_ATTENTE)" "$(grep -Eq 'ATTENTE="\$\{DB_RESTORE_ATTENTE:-120\}"' "$racine/tools/db_restore_test.sh"; echo $?)"

# --- refus de viser la vraie base ou le port 5432
etat_nominal
lance --port 5432
verifie "restore : --port 5432 refusé (code 2), aucun conteneur démarré" "$([ $code -eq 2 ] && grep -q 'Refus' "$tmp/s" && grep -q 'vraie base' "$tmp/s" && ! grep -q 'docker run' "$FAUX_LOG"; echo $?)"
PMZILLA_LAB_DB_PORT=5433 lance --port 5433
verifie "restore : --port égal au port configuré de la vraie base refusé (code 2)" "$([ $code -eq 2 ] && grep -q 'Refus' "$tmp/s" && ! grep -q 'docker run' "$FAUX_LOG"; echo $?)"
etat_nominal
lance --port 5544
verifie "restore : --port libre accepté et publié sur 127.0.0.1 seulement" "$(grep '^docker run' "$FAUX_LOG" | grep -q -- '-p 127.0.0.1:5544:5432'; echo $?)"
etat_nominal
FAUX_PORT=5432 lance
verifie "restore : si Docker publiait 5432, refus (code 1) et conteneur supprimé, rien restauré" "$([ $code -eq 1 ] && grep -q 'Refus' "$tmp/s" && ! grep -q 'pg_restore' "$FAUX_LOG" && [ ! -s "$FX/conteneurs" ]; echo $?)"

# --- hygiène du script
verifie "restore : le script ne contient ni set -x, ni docker exec sur la vraie base, ni down -v" "$(grep -Eq '^[^#]*(set -[a-z]*x|docker compose (down|up)|compose exec[^|]*pg_restore|down -v)' "$racine/tools/db_restore_test.sh"; [ $? -ne 0 ]; echo $?)"

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
