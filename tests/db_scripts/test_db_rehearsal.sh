#!/bin/bash
# Test de tools/db_rehearsal.sh (change flow-rebuild-rehearsal, tâche 4.1, design D11) : faux docker, faux uv (lanceur des migrations) et faux
# security (le Trousseau) en tête d'un PATH réduit. Aucun appel à la vraie base, au Trousseau, à Docker ni au réseau.
# Lancement à la main : bash tests/db_scripts/test_db_rehearsal.sh
#
# Garde-fous : le PATH du test ne contient ni Homebrew ni /usr/local (le vrai docker n'y est pas) ; docker est vérifié comme étant le faux ;
# security, docker-compose, colima, psql, pg_dump et pg_restore sont des faux qui font ÉCHOUER le test s'ils sont appelés ; le script ne doit
# contenir aucun chemin absolu vers docker.
#
# Contrat posé par ce test pour la tâche 5.1 (le reste est celui du design D11 et du delta de spec) :
#   - variable d'attente : DB_REHEARSAL_ATTENTE (secondes max avant « prêt », comme DB_RESTORE_ATTENTE) ;
#   - variables lues par `up` : PMZILLA_LAB_DB_PASSWORD (superutilisateur de la copie), PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW et
#     PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW_VIEWS (rôles d'import et des vues), noms de tools/db.py ; le superutilisateur arrive à `docker run`
#     par POSTGRES_PASSWORD (environnement, jamais un argument) ;
#   - migrations : `uv run tools/db.py migrate`, avec PMZILLA_LAB_DB_URL de la copie et PMZILLA_LAB_DB_SECURITY_BIN = une commande qui échoue ;
#   - lecture de la copie : `docker exec <nom> psql` ; lecture de la vraie base : `docker compose exec -T db psql` (comptes et empreinte) ;
#   - inventaire des conteneurs : `docker ps -a` avec --filter label=pmzilla-lab-rehearsal=1 ou name=... (-q ou --format).
set -u
racine="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${DB_REHEARSAL_SCRIPT_TEST:-$racine/tools/db_rehearsal.sh}"   # surcharge réservée à la validation du test lui-même
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
bin="$tmp/bin"; mkdir -p "$bin" "$tmp/tmpdir" "$tmp/home"
ok=0; ko=0
verifie() { # description  code (0 = vrai)
  if [ "$2" -eq 0 ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1"; ko=$((ko+1)); fi
}
absent() { ! grep -q -- "$1" "$2"; echo $?; }   # 0 si le motif est absent du fichier

if [ ! -f "$SCRIPT" ]; then
  echo "ECHEC : tools/db_rehearsal.sh est absent (tâche 5.1) ; le test reste rouge tant que le script n'existe pas"
  echo "0 réussis, 1 échec(s)"
  exit 1
fi

export FX="$tmp/fx"; mkdir -p "$FX"
export FAUX_LOG="$tmp/log"; : > "$FAUX_LOG"
export INTERDIT="$tmp/interdit"; : > "$INTERDIT"
MDP_SU="sentinelle-superutilisateur-5d2e"
MDP_FLOW="sentinelle-import-flow-8a41"
MDP_VUES="sentinelle-vues-flow-c93b"
MDP_REEL="mot-de-passe-reel-sentinelle-7c1e"
BRUIT="CLE-SECRETE-42"            # ligne parasite que les faux psql intercalent : elle ne doit jamais ressortir
ERREUR="ERREUR-SECRETE-77"        # sortie d'erreur d'une commande en échec : elle ne doit jamais ressortir
export BRUIT_FAUX="$BRUIT" ERREUR_FAUX="$ERREUR"
REEL_NOM="pmzilla-lab-db-1"; RESTORE_NOM="pmzilla-lab-restore-test-4242-77"

# Gardes : toute commande qui ne doit jamais être appelée journalise dans INTERDIT et échoue.
for interdit in security docker-compose colima psql pg_dump pg_restore; do
  cat > "$bin/$interdit" <<'SCRIPT'
#!/bin/bash
echo "$(basename "$0") $*" >> "$INTERDIT"; echo "$MDP_REEL_FAUX"; exit 99
SCRIPT
done
export MDP_REEL_FAUX="$MDP_REEL"

# Faux uv : le lanceur des migrations. Journalise les arguments puis, après « | », l'environnement vu par la commande.
cat > "$bin/uv" <<'SCRIPT'
#!/bin/bash
echo "uv $* | URL=${PMZILLA_LAB_DB_URL:-} PW=${PMZILLA_LAB_DB_PASSWORD:-} PWF=${PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW:-} PWV=${PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW_VIEWS:-} SEC=${PMZILLA_LAB_DB_SECURITY_BIN:-}" >> "$FAUX_LOG"
[ "${FAUX_UV_ECHEC:-0}" = "1" ] && { echo "$ERREUR_FAUX"; echo "$ERREUR_FAUX" >&2; exit 1; }
echo "Appliquée : 0001_schemas_roles_extensions.sql"; exit 0
SCRIPT

# Faux docker : un conteneur est une ligne du fichier $FX/conteneurs. Les arguments sont journalisés avant « | », l'environnement après.
cat > "$bin/docker" <<'SCRIPT'
#!/bin/bash
echo "docker $* | PW=${POSTGRES_PASSWORD:-} PWF=${PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW:-} PWV=${PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW_VIEWS:-}" >> "$FAUX_LOG"
args="$*"
case "${1:-}" in
  info) exit "${FAUX_DOCKER_INFO:-0}" ;;
  compose)
    case "$args" in
      *"ps -q"*) [ "${FAUX_CONTENEUR:-1}" = "1" ] && echo abc123; exit 0 ;;
      *pg_isready*) exit 0 ;;
      *psql*)
        echo "$BRUIT_FAUX"
        case "$args" in *"schema_migrations order"*) cat "$FX/mig-reelle" ;; *) cat "$FX/comptes-reels" ;; esac
        exit 0 ;;
    esac
    exit 0 ;;
  run)
    nom=""; prev=""
    for a in "$@"; do [ "$prev" = "--name" ] && nom="$a"; prev="$a"; done
    [ "${FAUX_RUN_ECHEC:-0}" = "1" ] && { echo "$ERREUR_FAUX" >&2; exit 125; }
    echo "$nom" >> "$FX/conteneurs"; echo "id-$nom"; exit 0 ;;
  port) echo "127.0.0.1:${FAUX_PORT:-49153}"; exit 0 ;;
  inspect) echo "2026-10-17T10:00:00Z"; exit 0 ;;
  rm)
    [ "${FAUX_RM_NOOP:-0}" = "1" ] && exit 0
    for a in "$@"; do case "$a" in -*|rm) ;; *) grep -vx -- "$a" "$FX/conteneurs" > "$FX/c.tmp"; mv "$FX/c.tmp" "$FX/conteneurs" ;; esac; done
    exit 0 ;;
  ps)
    filtre=""; fmt=""; q=0; prev=""
    for a in "$@"; do
      case "$prev" in --filter|-f) filtre="$a" ;; --format) fmt="$a" ;; esac
      case "$a" in --filter=*) filtre="${a#--filter=}" ;; --format=*) fmt="${a#--format=}" ;; -q|-aq|-qa|--quiet) q=1 ;; esac
      prev="$a"
    done
    case "$filtre" in
      label=pmzilla-lab-rehearsal*) sel="$(grep '^pmzilla-lab-rehearsal-' "$FX/conteneurs")" ;;
      name=*) sel="$(grep -E -- "${filtre#name=}" "$FX/conteneurs")" ;;
      *) sel="$(cat "$FX/conteneurs")" ;;
    esac
    [ -z "$sel" ] && exit 0
    while read -r n; do
      if [ "$q" = 1 ]; then echo "id-$n"
      elif [ -n "$fmt" ]; then
        l="$fmt"; k1='{{.Names}}'; k2='{{.CreatedAt}}'; k3='{{.Ports}}'; k4='{{.ID}}'; k5='{{.Label "pmzilla-lab-rehearsal"}}'
        l="${l//"$k1"/$n}"; l="${l//"$k2"/2026-10-17 10:00:00 +0200 CEST}"; l="${l//"$k3"/127.0.0.1:${FAUX_PORT:-49153}->5432/tcp}"
        l="${l//"$k4"/id-$n}"; l="${l//"$k5"/1}"; echo "$l"
      else echo "$n"; fi
    done <<< "$sel"
    exit 0 ;;
  exec)
    case "$args" in *" -i "*) cat > /dev/null ;; esac
    case "$args" in
      *pg_isready*) exit "${FAUX_PRET:-0}" ;;
      *psql*)
        echo "$BRUIT_FAUX"
        case "$args" in *"schema_migrations order"*) cat "$FX/mig-copie" ;; *) cat "$FX/comptes-copie" ;; esac
        exit 0 ;;
    esac
    exit 0 ;;
esac
exit 0
SCRIPT
chmod +x "$bin"/*

export PATH="$bin:/usr/bin:/bin:/usr/sbin:/sbin"
export HOME="$tmp/home" TMPDIR="$tmp/tmpdir"
export PMZILLA_LAB_WORKSPACE="$tmp"
export DB_REHEARSAL_ATTENTE=4
unset CLAUDECODE PMZILLA_LAB_DB_PORT PMZILLA_LAB_DB_URL PMZILLA_LAB_DB_PASSWORD PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW_VIEWS POSTGRES_PASSWORD PMZILLA_LAB_DATA
unset FAUX_DOCKER_INFO FAUX_CONTENEUR FAUX_RUN_ECHEC FAUX_PORT FAUX_PRET FAUX_UV_ECHEC FAUX_RM_NOOP

# Garde : le docker du PATH est le faux, et le script n'appelle aucun docker par chemin absolu.
verifie "garde : docker résolu dans le PATH du test est le faux" "$([ "$(command -v docker)" = "$bin/docker" ]; echo $?)"
verifie "garde : le script n'appelle aucun docker par chemin absolu" "$(grep -Eq '(/usr/local|/opt/homebrew|/usr)/bin/docker|(^|[^A-Za-z0-9_.-])/[A-Za-z0-9_./-]*/docker( |$)' "$SCRIPT"; [ $? -ne 0 ]; echo $?)"
verifie "contenu : le script ne contient ni set -x ni xtrace" "$(grep -Eq '^[^#]*(set -[a-z]*x|xtrace)' "$SCRIPT"; [ $? -ne 0 ]; echo $?)"
verifie "contenu : le script ne lit pas le Trousseau (aucun appel à security)" "$(grep -Eq '^[^#]*(security |find-generic-password)' "$SCRIPT"; [ $? -ne 0 ]; echo $?)"

# Données de référence : copie vide, mêmes migrations que les fichiers et que la vraie base.
etat_nominal() {
  cat > "$FX/comptes-copie" <<'EOF'
flow.teams|0
flow.issues|0
flow.issue_teams|0
flow.transitions|0
flow.links|0
flow.issue_label_periods|0
flow.issue_version_periods|0
flow.raw_runs|0
flow.raw_run_sightings|0
flow.raw_issue_snapshots|0
public.schema_migrations|9
EOF
  cp "$FX/comptes-copie" "$FX/comptes-reels"
  sed -E 's/\|0$/|120/' "$FX/comptes-copie" | grep -v '^public' > "$FX/comptes-reels"; echo "public.schema_migrations|9" >> "$FX/comptes-reels"
  : > "$FX/mig-copie"
  for f in "$racine"/db/migrations/*.sql; do
    nom="$(basename "$f")"; echo "$((10#${nom%%_*}))|$nom|$(shasum -a 256 "$f" | cut -d' ' -f1)" >> "$FX/mig-copie"
  done
  cp "$FX/mig-copie" "$FX/mig-reelle"
  printf '%s\n%s\n' "$REEL_NOM" "$RESTORE_NOM" > "$FX/conteneurs"; : > "$FAUX_LOG"; : > "$INTERDIT"
  export PMZILLA_LAB_DB_PASSWORD="$MDP_SU" PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW="$MDP_FLOW" PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW_VIEWS="$MDP_VUES"
  unset CLAUDECODE FAUX_DOCKER_INFO FAUX_CONTENEUR FAUX_RUN_ECHEC FAUX_PORT FAUX_PRET FAUX_UV_ECHEC FAUX_RM_NOOP PMZILLA_LAB_DB_PORT
}
lance() { bash "$SCRIPT" "$@" > "$tmp/s" 2>&1 < /dev/null; code=$?; }
arguments() { sed 's/ | .*//' "$FAUX_LOG"; }                        # le journal sans l'environnement vu par chaque commande
rehearsal_restants() { grep -c '^pmzilla-lab-rehearsal-' "$FX/conteneurs"; }
nom_copie() { grep '^pmzilla-lab-rehearsal-' "$FX/conteneurs" | head -1; }
PREFIXE_RE='pmzilla-lab-rehearsal-[0-9]+-[0-9]+'

# --- Session Claude Code : refus de chaque sous-commande avant toute lecture et tout Docker
for sous in "up" "up --port 49200" "status" "down"; do
  etat_nominal
  CLAUDECODE=1 lance $sous
  verifie "session ($sous) : code 3 et phrase de session" "$([ $code -eq 3 ] && grep -q '^Refusé dans une session Claude Code' "$tmp/s"; echo $?)"
  verifie "session ($sous) : journal de Docker vide, aucun conteneur touché" "$([ ! -s "$FAUX_LOG" ] && [ "$(wc -l < "$FX/conteneurs" | tr -d ' ')" = 2 ]; echo $?)"
done
etat_nominal; unset PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW_VIEWS
CLAUDECODE=1 lance up
verifie "session : refus avant la lecture des variables (code 3, pas 2, même avec une variable absente)" "$([ $code -eq 3 ]; echo $?)"

# --- Usage
etat_nominal
lance
verifie "usage : sans sous-commande, code 2 et aucun Docker" "$([ $code -eq 2 ] && [ ! -s "$FAUX_LOG" ]; echo $?)"
lance bidon
verifie "usage : sous-commande inconnue refusée (code 2)" "$([ $code -eq 2 ]; echo $?)"
lance up --bidon
verifie "usage : option inconnue de up refusée (code 2), aucun conteneur démarré" "$([ $code -eq 2 ] && [ "$(rehearsal_restants)" = 0 ]; echo $?)"

# --- Démarrage nominal : copie vide, une seule migration, aucun redémarrage
etat_nominal
lance up
verifie "up : succès, code 0" "$([ $code -eq 0 ]; echo $?)"
nom="$(nom_copie)"
verifie "up : phrase de fin avec le nom, le port de la boucle locale et « schéma flow vide »" "$(grep -Eq "^copie de répétition prête : $PREFIXE_RE \(127\.0\.0\.1:49153\), schéma flow vide\$" "$tmp/s"; echo $?)"
verifie "up : adresse sans mot de passe" "$(grep -Eq '^adresse : postgresql://postgres@127\.0\.0\.1:49153/pmzilla \(sans mot de passe\)$' "$tmp/s"; echo $?)"
verifie "up : chaque table de flow est affichée avec 0 ligne" "$(for t in teams issues issue_teams transitions links issue_label_periods issue_version_periods raw_runs raw_run_sightings raw_issue_snapshots; do grep -qx "  flow.$t 0" "$tmp/s" || exit 1; done; echo 0)"
verifie "up : la copie reste en place après un succès (un seul conteneur de répétition)" "$([ "$(rehearsal_restants)" = 1 ] && [ -n "$nom" ]; echo $?)"
run_ligne="$(grep '^docker run' "$FAUX_LOG" | head -1)"
image_compose="$(grep -E '^[[:space:]]+image:' "$racine/docker-compose.yml" | head -1 | sed -E 's/^[[:space:]]+image:[[:space:]]*//; s/["[:space:]]//g')"
verifie "up : un seul docker run" "$([ "$(grep -c '^docker run' "$FAUX_LOG")" = 1 ]; echo $?)"
verifie "up : conteneur de l'image fixée du compose" "$(printf '%s' "$run_ligne" | grep -q -- "$image_compose"; echo $?)"
verifie "up : nom unique au préfixe de répétition, distinct de celui du test de restauration et de la vraie base" "$(printf '%s' "$run_ligne" | grep -Eq -- "--name $PREFIXE_RE" && ! printf '%s' "$run_ligne" | grep -q 'restore-test' && ! printf '%s' "$run_ligne" | grep -q -- "--name $REEL_NOM"; echo $?)"
verifie "up : étiquette pmzilla-lab-rehearsal=1" "$(printf '%s' "$run_ligne" | grep -q -- '--label pmzilla-lab-rehearsal=1'; echo $?)"
verifie "up : port publié sur la boucle locale seulement, choisi par Docker, jamais 5432:5432" "$(printf '%s' "$run_ligne" | grep -q -- '-p 127.0.0.1::5432' && ! printf '%s' "$run_ligne" | grep -Eq -- '-p (0\.0\.0\.0:)?[0-9]*:?5432:5432|-p 5432'; echo $?)"
verifie "up : migrations lancées une fois, sur l'adresse de la copie, Trousseau neutralisé" "$([ "$(grep -c '^uv run tools/db.py migrate' "$FAUX_LOG")" = 1 ] && grep '^uv ' "$FAUX_LOG" | grep -q 'URL=postgresql://postgres@127.0.0.1:49153/pmzilla' && grep '^uv ' "$FAUX_LOG" | grep -Eq 'SEC=[^ ]*false'; echo $?)"
verifie "up : le superutilisateur de la copie arrive à docker run par l'environnement" "$(grep '^docker run' "$FAUX_LOG" | grep -q "| PW=$MDP_SU "; echo $?)"
verifie "up : le Trousseau et les outils interdits ne sont jamais appelés" "$([ ! -s "$INTERDIT" ] && ! grep -q '^security' "$FAUX_LOG"; echo $?)"

# --- Aucune restauration, aucune suppression de données
verifie "sans restauration : aucun pg_restore, restore, truncate, drop ni delete dans le journal des commandes" "$(arguments | grep -Eqi 'pg_restore|restore|truncate|drop |delete from|\.dump'; [ $? -ne 0 ]; echo $?)"

# --- Vraie base : lecture seule
verifie "vraie base : compose limité à ps, pg_isready et psql" "$(arguments | grep '^docker compose' | grep -Ev '^docker compose (ps -q|exec -T db pg_isready|exec -T db psql)' | grep -q .; [ $? -ne 0 ]; echo $?)"
verifie "vraie base : aucune écriture (insert, update, delete, drop, truncate, alter, create, grant)" "$(arguments | grep '^docker compose' | grep -Eqi 'insert|update|delete|drop|truncate|alter|create|grant'; [ $? -ne 0 ]; echo $?)"
verifie "vraie base : ni up, down, stop, restart, rm ni exec sur son conteneur par nom" "$(arguments | grep -Eq "^docker (stop|kill|restart|rm|exec).* $REEL_NOM|^docker compose (up|down|stop|restart|rm|start)"; [ $? -ne 0 ]; echo $?)"
verifie "copie : tout docker exec vise un conteneur de répétition" "$(arguments | grep '^docker exec' | grep -Ev "$PREFIXE_RE" | grep -q .; [ $? -ne 0 ]; echo $?)"
verifie "vraie base : l'empreinte des migrations est lue (requête de lecture sur schema_migrations)" "$(arguments | grep '^docker compose exec' | grep -q 'schema_migrations'; echo $?)"

# --- Mots de passe : pas dans les arguments, la sortie ni les fichiers
etat_nominal
lance up
verifie "mots de passe : aucun dans les arguments des commandes (docker et uv)" "$(arguments | grep -Eq "$MDP_SU|$MDP_FLOW|$MDP_VUES"; [ $? -ne 0 ]; echo $?)"
verifie "mots de passe : aucun dans la sortie" "$(grep -Eq "$MDP_SU|$MDP_FLOW|$MDP_VUES|$MDP_REEL" "$tmp/s"; [ $? -ne 0 ]; echo $?)"
verifie "mots de passe : aucun dans un fichier écrit par le script (dossier temporaire, HOME, contenu)" "$(grep -rqE "$MDP_SU|$MDP_FLOW|$MDP_VUES" "$tmp/tmpdir" "$tmp/home" 2>/dev/null; [ $? -ne 0 ]; echo $?)"
for var in PMZILLA_LAB_DB_PASSWORD PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW_VIEWS; do
  etat_nominal; unset "$var"
  lance up
  verifie "variable absente ($var) : code 2, la phrase nomme la variable sans valeur, aucun conteneur démarré" "$([ $code -eq 2 ] && grep -qx "variable absente : $var (valeur jamais affichée)" "$tmp/s" && ! grep -q '^docker run' "$FAUX_LOG" && [ "$(rehearsal_restants)" = 0 ] && ! grep -Eq "$MDP_SU|$MDP_FLOW|$MDP_VUES" "$tmp/s"; echo $?)"
done

# --- Ports : jamais celui de la vraie base
etat_nominal
lance up --port 5432
verifie "port standard demandé : code 2, phrase de refus, aucun conteneur" "$([ $code -eq 2 ] && grep -qx 'Refus : le port 5432 est celui de la vraie base.' "$tmp/s" && ! grep -q '^docker run' "$FAUX_LOG"; echo $?)"
etat_nominal
PMZILLA_LAB_DB_PORT=5500 lance up --port 5500
verifie "port configuré de la vraie base demandé : code 2, phrase de refus, aucun conteneur" "$([ $code -eq 2 ] && grep -qx 'Refus : le port 5500 est celui de la vraie base.' "$tmp/s" && ! grep -q '^docker run' "$FAUX_LOG"; echo $?)"
etat_nominal
FAUX_PORT=49200 lance up --port 49200
verifie "port libre demandé : publié sur la boucle locale, code 0" "$([ $code -eq 0 ] && grep '^docker run' "$FAUX_LOG" | grep -q -- '-p 127.0.0.1:49200:5432'; echo $?)"
etat_nominal
FAUX_PORT=5432 lance up
verifie "Docker publie quand même 5432 : code 1, phrase de refus, conteneur supprimé avec son volume" "$([ $code -eq 1 ] && grep -qx 'Refus : le port 5432 est celui de la vraie base.' "$tmp/s" && [ "$(rehearsal_restants)" = 0 ] && arguments | grep -Eq '^docker rm .*(-v|--volumes|-fv|-vf)'; echo $?)"
etat_nominal
PMZILLA_LAB_DB_PORT=5500 FAUX_PORT=5500 lance up
verifie "Docker publie quand même le port configuré de la vraie base : code 1, conteneur supprimé" "$([ $code -eq 1 ] && [ "$(rehearsal_restants)" = 0 ]; echo $?)"
etat_nominal
lance up --port abc
verifie "port non numérique : code 2, aucun conteneur" "$([ $code -eq 2 ] && ! grep -q '^docker run' "$FAUX_LOG"; echo $?)"
# une seule règle de port (test-db-guards, D1, tâche 2.4) : forme décimale simple, comparaison en nombre
for forme in "05432" "+49200" " 49200" "49200 " "65536" "0" "00" $'49200\nx'; do
  etat_nominal
  lance up --port "$forme"
  verifie "port demandé $(printf '%q' "$forme") : code 2, « Port invalide », aucun conteneur" "$([ $code -eq 2 ] && grep -q '^Port invalide : ' "$tmp/s" && ! grep -q '^docker run' "$FAUX_LOG"; echo $?)"
done
for reel in "05432" "05500" " 5500" "5500 " "+5500" "65536" "0" "abc"; do
  etat_nominal
  PMZILLA_LAB_DB_PORT="$reel" lance up --port 49200
  verifie "port configuré de la vraie base illisible $(printf '%q' "$reel") : code 2, ligne dédiée, aucun conteneur" "$([ $code -eq 2 ] && grep -qxF 'Refus : le port configuré de la vraie base est illisible (PMZILLA_LAB_DB_PORT) : corrige-le ou retire-le, puis relance.' "$tmp/s" && ! grep -q '^docker run' "$FAUX_LOG"; echo $?)"
done

# --- Prérequis Docker et vraie base
etat_nominal
FAUX_DOCKER_INFO=1 lance up
verifie "Docker muet : code 2, aucun conteneur" "$([ $code -eq 2 ] && ! grep -q '^docker run' "$FAUX_LOG"; echo $?)"
etat_nominal
FAUX_CONTENEUR=0 lance up
verifie "vraie base arrêtée : code 2, aucun conteneur" "$([ $code -eq 2 ] && ! grep -q '^docker run' "$FAUX_LOG"; echo $?)"

# --- Une seule copie à la fois
etat_nominal
echo "pmzilla-lab-rehearsal-111-222" >> "$FX/conteneurs"
lance up
verifie "copie déjà présente : code 2, la phrase nomme le conteneur et la commande down" "$([ $code -eq 2 ] && grep -qx 'une copie de répétition existe déjà : pmzilla-lab-rehearsal-111-222 ; la supprimer : bash tools/db_rehearsal.sh down' "$tmp/s"; echo $?)"
verifie "copie déjà présente : aucun conteneur démarré ni supprimé, la copie existante est intacte" "$(! grep -Eq '^docker (run|rm)' "$FAUX_LOG" && grep -qx 'pmzilla-lab-rehearsal-111-222' "$FX/conteneurs" && [ "$(rehearsal_restants)" = 1 ]; echo $?)"

# --- Empreinte des migrations
etat_nominal
echo "99|0099_une_migration_de_plus.sql|$(printf '%064d' 0 | tr 0 a)" >> "$FX/mig-reelle"
lance up
verifie "empreinte : la vraie base a une migration de plus : code 1 et phrase d'empreinte" "$([ $code -eq 1 ] && grep -qx "ÉCHEC : l'empreinte des migrations diffère entre la copie et la vraie base" "$tmp/s"; echo $?)"
verifie "empreinte : conteneur supprimé avec son volume et phrase de suppression après échec" "$([ "$(rehearsal_restants)" = 0 ] && arguments | grep -Eq '^docker rm .*(-v|--volumes|-fv|-vf)' && grep -Eq "^copie de répétition supprimée après échec : $PREFIXE_RE\$" "$tmp/s"; echo $?)"
etat_nominal
sed -i.bak '1d' "$FX/mig-copie"; rm -f "$FX/mig-copie.bak"
lance up
verifie "empreinte : la copie diffère des fichiers et de la vraie base : code 1, conteneur supprimé" "$([ $code -eq 1 ] && grep -qx "ÉCHEC : l'empreinte des migrations diffère entre la copie et la vraie base" "$tmp/s" && [ "$(rehearsal_restants)" = 0 ]; echo $?)"

# --- Échecs de démarrage : aucune copie ne reste
etat_nominal
FAUX_UV_ECHEC=1 lance up
verifie "échec des migrations : code 1 et phrase de suppression après échec" "$([ $code -eq 1 ] && grep -Eq "^copie de répétition supprimée après échec : $PREFIXE_RE\$" "$tmp/s"; echo $?)"
verifie "échec des migrations : suppression reçue par Docker avec l'option du volume, aucun conteneur de répétition restant" "$([ "$(rehearsal_restants)" = 0 ] && arguments | grep -Eq '^docker rm .*(-v|--volumes|-fv|-vf)'; echo $?)"
verifie "échec des migrations : la sortie d'erreur de la commande n'est pas affichée" "$(absent "$ERREUR" "$tmp/s")"
etat_nominal
sed -i.bak 's/^flow.issues|0$/flow.issues|3/' "$FX/comptes-copie"; rm -f "$FX/comptes-copie.bak"
lance up
verifie "table non vide : code 1 et phrase nommant la table" "$([ $code -eq 1 ] && grep -qx 'ÉCHEC : table non vide dans la copie : flow.issues' "$tmp/s"; echo $?)"
verifie "table non vide : copie supprimée avec son volume" "$([ "$(rehearsal_restants)" = 0 ] && arguments | grep -Eq '^docker rm .*(-v|--volumes|-fv|-vf)' && grep -Eq "^copie de répétition supprimée après échec : " "$tmp/s"; echo $?)"
etat_nominal
FAUX_PRET=1 lance up
verifie "copie pas prête à temps : code 1, copie supprimée avec son volume, aucune migration lancée" "$([ $code -eq 1 ] && [ "$(rehearsal_restants)" = 0 ] && ! grep -q '^uv ' "$FAUX_LOG" && arguments | grep -Eq '^docker rm .*(-v|--volumes|-fv|-vf)' && grep -Eq "^copie de répétition supprimée après échec : " "$tmp/s"; echo $?)"
etat_nominal
FAUX_RUN_ECHEC=1 lance up
verifie "docker run en échec : code 1, aucun conteneur de répétition restant, erreur non affichée" "$([ $code -eq 1 ] && [ "$(rehearsal_restants)" = 0 ] && ! grep -q "$ERREUR" "$tmp/s"; echo $?)"

# --- Interruption pendant l'attente de la copie
etat_nominal
export FAUX_PRET=1 DB_REHEARSAL_ATTENTE=60
bash "$SCRIPT" up > "$tmp/s" 2>&1 < /dev/null &
pid=$!
( sleep 45; kill -9 "$pid" 2>/dev/null ) &
garde=$!
i=0; while [ $i -lt 100 ]; do grep -Eq "^docker exec .*pg_isready" "$FAUX_LOG" && break; sleep 0.2; i=$((i+1)); done
kill -TERM "$pid" 2>/dev/null
wait "$pid" 2>/dev/null; code=$?
kill "$garde" 2>/dev/null; wait "$garde" 2>/dev/null
unset FAUX_PRET; export DB_REHEARSAL_ATTENTE=4
verifie "interruption (TERM pendant l'attente) : sortie non nulle" "$([ $code -ne 0 ] && [ $code -ne 137 ]; echo $?)"
verifie "interruption : le conteneur de répétition est supprimé avec son volume" "$([ "$(rehearsal_restants)" = 0 ] && arguments | grep -Eq '^docker rm .*(-v|--volumes|-fv|-vf)'; echo $?)"

# --- status
etat_nominal
lance status
verifie "status sans copie : phrase dédiée et code 0" "$([ $code -eq 0 ] && grep -qx 'aucune copie de répétition' "$tmp/s"; echo $?)"
etat_nominal
echo "pmzilla-lab-rehearsal-111-222" >> "$FX/conteneurs"
lance status
verifie "status avec copie : nom, port de la boucle locale et instant de création, code 0" "$([ $code -eq 0 ] && grep -Eq '^copie de répétition : pmzilla-lab-rehearsal-111-222 \(127\.0\.0\.1:49153\), créée le .+$' "$tmp/s"; echo $?)"
verifie "status : aucune lecture de base, aucune migration, aucune suppression" "$(arguments | grep -Eq 'psql|pg_isready|^docker (rm|run|exec)|^docker compose|^uv '; [ $? -ne 0 ]; echo $?)"
verifie "status : ne cite ni la vraie base ni le conteneur du test de restauration" "$(grep -Eq "$REEL_NOM|restore-test" "$tmp/s"; [ $? -ne 0 ]; echo $?)"

# --- down
etat_nominal
echo "pmzilla-lab-rehearsal-111-222" >> "$FX/conteneurs"
lance down
verifie "down : copie supprimée avec son volume, phrase de suppression qui la nomme, code 0" "$([ $code -eq 0 ] && grep -qx 'copie de répétition supprimée : pmzilla-lab-rehearsal-111-222' "$tmp/s" && [ "$(rehearsal_restants)" = 0 ] && arguments | grep -Eq '^docker rm .*(-v|--volumes|-fv|-vf).*pmzilla-lab-rehearsal-111-222|^docker rm .*pmzilla-lab-rehearsal-111-222.*(-v|--volumes)'; echo $?)"
verifie "down : la vraie base et le conteneur du test de restauration ne sont pas supprimés" "$(grep -qx "$REEL_NOM" "$FX/conteneurs" && grep -qx "$RESTORE_NOM" "$FX/conteneurs" && arguments | grep '^docker rm' | grep -Eq "$REEL_NOM|restore-test"; [ $? -ne 0 ]; echo $?)"
verifie "down : aucune requête sur une base, aucun Trousseau" "$(arguments | grep -Eq 'psql|^docker compose|^uv '; [ $? -ne 0 ] && [ ! -s "$INTERDIT" ]; echo $?)"
etat_nominal
printf '%s\n%s\n' "pmzilla-lab-rehearsal-111-222" "pmzilla-lab-rehearsal-333-444" >> "$FX/conteneurs"
lance down
verifie "down : deux copies de répétition, les deux supprimées et rapportées" "$([ $code -eq 0 ] && grep -qx 'copie de répétition supprimée : pmzilla-lab-rehearsal-111-222' "$tmp/s" && grep -qx 'copie de répétition supprimée : pmzilla-lab-rehearsal-333-444' "$tmp/s" && [ "$(rehearsal_restants)" = 0 ] && grep -qx "$REEL_NOM" "$FX/conteneurs" && grep -qx "$RESTORE_NOM" "$FX/conteneurs"; echo $?)"
etat_nominal
lance down
verifie "down sans copie : phrase dédiée, code 0, aucune suppression" "$([ $code -eq 0 ] && grep -qx 'aucune copie de répétition à supprimer' "$tmp/s" && ! grep -q '^docker rm' "$FAUX_LOG" && grep -qx "$REEL_NOM" "$FX/conteneurs" && grep -qx "$RESTORE_NOM" "$FX/conteneurs"; echo $?)"
etat_nominal
echo "pmzilla-lab-rehearsal-111-222" >> "$FX/conteneurs"
FAUX_RM_NOOP=1 lance down
verifie "down avec reste : code 1 et phrase ATTENTION avec la commande de suppression" "$([ $code -eq 1 ] && grep -qx 'ATTENTION : la copie pmzilla-lab-rehearsal-111-222 existe encore ; la supprimer : docker rm -f -v pmzilla-lab-rehearsal-111-222' "$tmp/s"; echo $?)"

# --- Cycle complet : up, status, down
etat_nominal
lance up; c1=$code; nom="$(nom_copie)"
lance status; c2=$code; s2="$(cat "$tmp/s")"
lance down; c3=$code
lance status; c4=$code
verifie "cycle up, status, down, status : codes 0, la copie est vue puis retirée" "$([ $c1 -eq 0 ] && [ $c2 -eq 0 ] && [ $c3 -eq 0 ] && [ $c4 -eq 0 ] && printf '%s' "$s2" | grep -q "$nom" && grep -qx 'aucune copie de répétition' "$tmp/s" && [ "$(rehearsal_restants)" = 0 ]; echo $?)"

# --- Hygiène de la sortie : noms, port, adresse sans mot de passe, tables et comptes, états
cat > "$tmp/permis" <<'EOF'
^copie de répétition prête : pmzilla-lab-rehearsal-[0-9]+-[0-9]+ \(127\.0\.0\.1:[0-9]+\), schéma flow vide$
^adresse : postgresql://postgres@127\.0\.0\.1:[0-9]+/pmzilla \(sans mot de passe\)$
^  flow\.[a-z_]+ [0-9]+$
^ÉCHEC : [^|=@]+$
^Refus : le port [0-9]+ est celui de la vraie base\.$
^copie de répétition supprimée( après échec)? : pmzilla-lab-rehearsal-[0-9]+-[0-9]+$
^[^ ][^|=@]* :$
^  [^|=@'"]+$
EOF
etat_nominal
lance up
verifie "hygiène (up nominal) : chaque ligne affichée a une forme permise" "$(grep -Evf "$tmp/permis" "$tmp/s" | grep -q .; [ $? -ne 0 ]; echo $?)"
verifie "hygiène (up nominal) : aucune ligne parasite, aucun mot de passe" "$(grep -Eq "$BRUIT|$ERREUR|$MDP_SU|$MDP_FLOW|$MDP_VUES|$MDP_REEL" "$tmp/s"; [ $? -ne 0 ]; echo $?)"
verifie "hygiène (up nominal) : aucune trace d'exécution (lignes commençant par +)" "$(grep -Eq '^\+' "$tmp/s"; [ $? -ne 0 ]; echo $?)"
etat_nominal
FAUX_UV_ECHEC=1 lance up
verifie "hygiène (up en échec) : chaque ligne affichée a une forme permise, rien de parasite" "$(grep -Evf "$tmp/permis" "$tmp/s" | grep -q .; r1=$?; grep -Eq "$BRUIT|$ERREUR|$MDP_SU|$MDP_FLOW|$MDP_VUES" "$tmp/s"; r2=$?; [ $r1 -ne 0 ] && [ $r2 -ne 0 ]; echo $?)"
etat_nominal
sed -i.bak 's/^flow.issues|0$/flow.issues|3/' "$FX/comptes-copie"; rm -f "$FX/comptes-copie.bak"
lance up
verifie "hygiène (table non vide) : chaque ligne affichée a une forme permise, rien de parasite" "$(grep -Evf "$tmp/permis" "$tmp/s" | grep -q .; r1=$?; grep -Eq "$BRUIT|$ERREUR|$MDP_SU|$MDP_FLOW|$MDP_VUES" "$tmp/s"; r2=$?; [ $r1 -ne 0 ] && [ $r2 -ne 0 ]; echo $?)"
etat_nominal
echo "pmzilla-lab-rehearsal-111-222" >> "$FX/conteneurs"
lance status; s1="$(cat "$tmp/s")"; lance down
verifie "hygiène (status et down) : aucun mot de passe ni ligne parasite" "$(printf '%s\n' "$s1" | cat - "$tmp/s" | grep -Eq "$BRUIT|$ERREUR|$MDP_SU|$MDP_FLOW|$MDP_VUES"; [ $? -ne 0 ]; echo $?)"

verifie "garde finale : aucune commande interdite (Trousseau, psql direct, pg_dump, pg_restore, colima, docker-compose) n'a été appelée" "$([ ! -s "$INTERDIT" ]; echo $?)"

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
