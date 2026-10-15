#!/bin/bash
# Test de tools/db_up.sh, tools/db_backup.sh et (fichier voisin) tools/db_restore_test.sh : faux security, faux docker et faux colima en tête du PATH.
# Aucun appel au vrai Trousseau, à Docker ni au réseau. Lancement à la main : bash tests/db_scripts/test_db_scripts.sh
set -u
racine="$(cd "$(dirname "$0")/../.." && pwd)"
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
bin="$tmp/bin"; mkdir -p "$bin"
VRAI_DOCKER="$(command -v docker 2>/dev/null || true)"   # avant le PATH factice : pour docker compose config
HOME_REEL="$HOME"                                         # le plugin compose se trouve via le vrai HOME
MDP="sentinelle-factice-9f3a"
ok=0; ko=0
verifie() { # description  code (0 = vrai)
  if [ "$2" -eq 0 ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1"; ko=$((ko+1)); fi
}

# Faux security : imprime un mot de passe factice si FAUX_ENTREE=1, sinon échoue comme le Trousseau sans entrée.
cat > "$bin/security" <<SCRIPT
#!/bin/bash
echo "security \$*" >> "\$FAUX_LOG"
[ "\${FAUX_ENTREE:-0}" = "1" ] && { echo "$MDP"; exit 0; }
echo "security: SecKeychainSearchCopyNext: The specified item could not be found in the keychain." >&2; exit 44
SCRIPT
cat > "$bin/colima" <<'SCRIPT'
#!/bin/bash
[ "${FAUX_COLIMA:-1}" = "1" ]
SCRIPT
# Faux docker : journalise les arguments et la valeur de POSTGRES_PASSWORD vue par la commande.
cat > "$bin/docker" <<'SCRIPT'
#!/bin/bash
echo "docker $* | PW=${POSTGRES_PASSWORD:-}" >> "$FAUX_LOG"
[ "${1:-}" = "info" ] && exit "${FAUX_DOCKER_INFO:-0}"
[ "${1:-}" = "compose" ] || exit 0
args="$*"
# Interpolation du vrai docker-compose.yml : une variable déclarée obligatoire (${VAR:?…}) et absente fait échouer
# toute commande compose, comme le vrai docker compose (« required variable … is missing a value »).
if [ -z "${POSTGRES_PASSWORD:-}" ] && grep -q '\${POSTGRES_PASSWORD:?' "$FAUX_COMPOSE"; then
  echo "required variable POSTGRES_PASSWORD is missing a value" >&2; exit 1
fi
case "$args" in
  *"ps -q"*) [ "${FAUX_CONTENEUR:-1}" = "1" ] && echo "abc123def456"; exit 0 ;;
  *pg_isready*) exit "${FAUX_PRET:-0}" ;;
  *psql*)
    for s in $FAUX_ABSENTS; do case "$args" in *"nspname = '$s'"*) exit 0 ;; esac; done
    echo 1; exit 0 ;;
  *pg_dump*)
    schema="${args##*-n }"; schema="${schema%% *}"
    echo "MARQ $(cat "${PMZILLA_LAB_DATA:-/inexistant}/sauvegarde.encours/pid" 2>/dev/null) PPID=$PPID" >> "$FAUX_LOG"
    echo "DUMP $schema"; exit 0 ;;
esac
exit 0
SCRIPT
# Faux osascript : journalise la notification (jamais de vraie notification macOS).
cat > "$bin/osascript" <<'SCRIPT'
#!/bin/bash
echo "osascript $*" >> "$OSA_LOG"
SCRIPT
chmod +x "$bin/security" "$bin/colima" "$bin/docker" "$bin/osascript"
export OSA_LOG="$tmp/osa"; : > "$OSA_LOG"
unset DB_BACKUP_NOTIFIER DB_BACKUP_GARDER
export FAUX_LOG="$tmp/log"; : > "$FAUX_LOG"
export FAUX_COMPOSE="$racine/docker-compose.yml"
export FAUX_ABSENTS=""
export PATH="$bin:$PATH"
export HOME="$tmp/home"; mkdir -p "$HOME"
unset PMZILLA_LAB_DB_PASSWORD POSTGRES_PASSWORD

# --- db_up.sh
FAUX_ENTREE=0 bash "$racine/tools/db_up.sh" > "$tmp/s" 2>&1; code=$?
verifie "db_up : sans entrée du Trousseau, code 3 (code dédié lu par le script d'installation)" "$([ $code -eq 3 ]; echo $?)"
verifie "db_up : sans entrée, le message donne la commande de création" "$(grep -q 'security add-generic-password -s pmzilla-lab-db' "$tmp/s"; echo $?)"
verifie "db_up : sans entrée, docker compose up n'est pas lancé" "$(grep -q 'compose up' "$FAUX_LOG"; [ $? -ne 0 ]; echo $?)"
verifie "db_up : le message ne crée pas l'entrée (aucun add-generic-password exécuté)" "$(grep -q '^security add' "$FAUX_LOG"; [ $? -ne 0 ]; echo $?)"

: > "$FAUX_LOG"
FAUX_ENTREE=1 bash "$racine/tools/db_up.sh" > "$tmp/s" 2>&1; code=$?
verifie "db_up : avec l'entrée, code 0" "$code"
verifie "db_up : lit le service pmzilla-lab-db" "$(grep -q 'security find-generic-password -s pmzilla-lab-db -w' "$FAUX_LOG"; echo $?)"
verifie "db_up : docker compose up -d --wait lancé" "$(grep -q 'docker compose up -d --wait' "$FAUX_LOG"; echo $?)"
verifie "db_up : le mot de passe arrive à docker par l'environnement" "$(grep 'compose up' "$FAUX_LOG" | grep -q "| PW=$MDP\$"; echo $?)"
verifie "db_up : le mot de passe n'est dans aucun argument" "$(sed 's/ | PW=.*//' "$FAUX_LOG" | grep -q "$MDP"; [ $? -ne 0 ]; echo $?)"
verifie "db_up : le mot de passe n'est jamais affiché" "$(grep -q "$MDP" "$tmp/s"; [ $? -ne 0 ]; echo $?)"
verifie "db_up : le script ne contient pas de set -x ni d'export persistant" "$(grep -Eq '^[^#]*(set -[a-z]*x|export )' "$racine/tools/db_up.sh"; [ $? -ne 0 ]; echo $?)"

: > "$FAUX_LOG"
FAUX_ENTREE=0 PMZILLA_LAB_DB_PASSWORD="$MDP" bash "$racine/tools/db_up.sh" > "$tmp/s" 2>&1; code=$?
verifie "db_up : repli PMZILLA_LAB_DB_PASSWORD sans Trousseau" "$([ $code -eq 0 ] && grep 'compose up' "$FAUX_LOG" | grep -q "| PW=$MDP\$"; echo $?)"

: > "$FAUX_LOG"
FAUX_COLIMA=1 FAUX_ENTREE=1 bash "$racine/tools/db_up.sh" down > "$tmp/s" 2>&1; code=$?
verifie "db_up down : arrête sans supprimer le volume (pas de -v)" "$([ $code -eq 0 ] && grep -q 'compose down$' <(sed 's/ | PW=.*//' "$FAUX_LOG") && ! grep -Eq 'down.* -v|--volumes' "$FAUX_LOG"; echo $?)"
verifie "db_up down : ne lit pas le Trousseau" "$(grep -q '^security' "$FAUX_LOG"; [ $? -ne 0 ]; echo $?)"

FAUX_COLIMA=1 FAUX_ENTREE=1 bash "$racine/tools/db_up.sh" bidon > "$tmp/s" 2>&1; code=$?
verifie "db_up : option inconnue refusée (code 2)" "$([ $code -eq 2 ]; echo $?)"

FAUX_COLIMA=0 FAUX_ENTREE=1 bash "$racine/tools/db_up.sh" > "$tmp/s" 2>&1; code=$?
verifie "db_up : Colima arrêté, message clair et code non nul" "$([ $code -ne 0 ] && grep -q 'Colima ne tourne pas' "$tmp/s"; echo $?)"

FAUX_DOCKER_INFO=1 FAUX_ENTREE=1 bash "$racine/tools/db_up.sh" > "$tmp/s" 2>&1; code=$?
verifie "db_up : Docker muet, message clair et code non nul" "$([ $code -ne 0 ] && grep -q 'Docker ne répond pas' "$tmp/s"; echo $?)"

# --- db_backup.sh
sauv="$tmp/sauvegardes"
export DB_BACKUP_SAUVEGARDES="$sauv" DB_BACKUP_DATE="2026-10-08"
bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "db_backup : code 0" "$code"
verifie "db_backup : dossier db-2026-10-08 créé" "$([ -d "$sauv/db-2026-10-08" ]; echo $?)"
verifie "db_backup : un fichier par schéma" "$([ -s "$sauv/db-2026-10-08/knowledge.dump" ] && [ -s "$sauv/db-2026-10-08/cases.dump" ] && [ -s "$sauv/db-2026-10-08/flow.dump" ] && [ "$(ls "$sauv/db-2026-10-08" | wc -l | tr -d ' ')" = 3 ]; echo $?)"
verifie "db_backup : chaque fichier contient le dump de son schéma" "$([ "$(cat "$sauv/db-2026-10-08/cases.dump")" = "DUMP cases" ]; echo $?)"
verifie "db_backup : aucun mot de passe demandé ni lu (pas de security, PW vide)" "$(! grep -q '^security' "$FAUX_LOG" && ! grep 'pg_dump' "$FAUX_LOG" | grep -q 'PW=.'; echo $?)"
verifie "db_backup : la sortie ne contient que chemins et tailles" "$(grep -q "$MDP" "$tmp/s"; [ $? -ne 0 ]; echo $?)"

bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "db_backup : le dossier du jour n'est jamais écrasé, second passage en succès (code 0)" "$([ $code -eq 0 ] && grep -q 'existe déjà' "$tmp/s" && [ "$(cat "$sauv/db-2026-10-08/cases.dump")" = "DUMP cases" ]; echo $?)"

# Second passage de launchd : succès sans toucher à Docker (même Colima arrêté), sans notification.
: > "$FAUX_LOG"; : > "$OSA_LOG"
FAUX_DOCKER_INFO=1 DB_BACKUP_NOTIFIER=1 bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "db_backup : sauvegarde du jour présente et Docker muet, code 0, aucun appel docker, aucune notification" "$([ $code -eq 0 ] && grep -q 'existe déjà' "$tmp/s" && [ ! -s "$FAUX_LOG" ] && [ ! -s "$OSA_LOG" ]; echo $?)"

# Permissions : dossiers en 700, dumps en 600 (même avec un umask large).
verifie "db_backup : dossiers en 700 et dumps en 600" "$([ "$(stat -f %Lp "$sauv")" = 700 ] && [ "$(stat -f %Lp "$sauv/db-2026-10-08")" = 700 ] && [ "$(stat -f %Lp "$sauv/db-2026-10-08/flow.dump")" = 600 ] && [ "$(stat -f %Lp "$sauv/db-2026-10-08/knowledge.dump")" = 600 ]; echo $?)"
(umask 000; DB_BACKUP_SAUVEGARDES="$tmp/large" DB_BACKUP_DATE="2026-10-08" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1)
verifie "db_backup : umask 000 du lanceur, dossiers toujours en 700 et dumps en 600" "$([ "$(stat -f %Lp "$tmp/large")" = 700 ] && [ "$(stat -f %Lp "$tmp/large/db-2026-10-08")" = 700 ] && [ "$(stat -f %Lp "$tmp/large/db-2026-10-08/cases.dump")" = 600 ]; echo $?)"

# Rotation par défaut : 14 dossiers gardés ; réglage invalide refusé sans rien supprimer.
export DB_BACKUP_GARDER=6
for j in 01 02 03 04 05 06 07; do DB_BACKUP_DATE="2026-09-$j" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; done
verifie "db_backup : rotation, 6 dossiers db-* gardés" "$([ "$(ls "$sauv" | grep -Ec '^db-')" = 6 ]; echo $?)"
verifie "db_backup : le plus récent est gardé, le plus ancien supprimé" "$([ -d "$sauv/db-2026-10-08" ] && [ ! -d "$sauv/db-2026-09-01" ]; echo $?)"
verifie "db_backup : la rotation affiche ce qu'elle supprime" "$(grep -q 'Supprimée : .*db-2026-09-0' "$tmp/s"; echo $?)"
mkdir -p "$sauv/db-2026-01-01-matin"; echo x > "$sauv/db-2026-01-01-matin/flow.dump"
DB_BACKUP_DATE="2026-10-07" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1
verifie "db_backup : un dossier avec étiquette (db-AAAA-MM-JJ-matin) n'est ni compté ni supprimé par la rotation" "$([ -d "$sauv/db-2026-01-01-matin" ] && ! grep -q 'matin' "$tmp/s" && [ "$(ls "$sauv" | grep -Ec '^db-[0-9]{4}-[0-9]{2}-[0-9]{2}$')" = 6 ]; echo $?)"

FAUX_ABSENTS="flow" DB_BACKUP_DATE="2026-10-09" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "db_backup : schéma absent signalé, code non nul, les autres sauvegardés" "$([ $code -ne 0 ] && grep -q 'Schéma absent, non sauvegardé : flow' "$tmp/s" && [ -s "$sauv/db-2026-10-09/knowledge.dump" ] && [ ! -e "$sauv/db-2026-10-09/flow.dump" ]; echo $?)"

FAUX_CONTENEUR=0 DB_BACKUP_DATE="2026-10-10" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "db_backup : conteneur arrêté, message dédié, aucun dossier créé" "$([ $code -ne 0 ] && grep -q 'conteneur de la base est arrêté' "$tmp/s" && grep -q 'db_up.sh' "$tmp/s" && [ ! -e "$sauv/db-2026-10-10" ]; echo $?)"

FAUX_PRET=1 DB_BACKUP_DATE="2026-10-10" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "db_backup : conteneur sain mais PostgreSQL muet, message distinct de « arrêté »" "$([ $code -ne 0 ] && grep -q 'tourne mais PostgreSQL ne répond pas' "$tmp/s" && ! grep -q 'est arrêté' "$tmp/s" && [ ! -e "$sauv/db-2026-10-10" ]; echo $?)"

FAUX_DOCKER_INFO=1 DB_BACKUP_DATE="2026-10-10" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "db_backup : Docker muet, message dédié" "$([ $code -ne 0 ] && grep -q 'Docker ne répond pas' "$tmp/s"; echo $?)"

unset DB_BACKUP_GARDER
# Rotation par défaut (14) sur un dossier neuf : 16 jours de sauvegardes, les 14 plus récents restent.
rot="$tmp/rotation"
for j in 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16; do
  DB_BACKUP_SAUVEGARDES="$rot" DB_BACKUP_DATE="2026-08-$j" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1
done
verifie "db_backup : rotation par défaut, 14 dossiers gardés sur 16" "$([ "$(ls "$rot" | grep -Ec '^db-')" = 14 ] && [ -d "$rot/db-2026-08-16" ] && [ -d "$rot/db-2026-08-03" ] && [ ! -d "$rot/db-2026-08-02" ] && [ ! -d "$rot/db-2026-08-01" ]; echo $?)"
verifie "db_backup : la rotation annonce le nombre gardé" "$(grep -q 'Sauvegardes présentes : 14 (garde les 14 plus récentes)' "$tmp/s"; echo $?)"
DB_BACKUP_GARDER=3 DB_BACKUP_SAUVEGARDES="$rot" DB_BACKUP_DATE="2026-08-17" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1
verifie "db_backup : DB_BACKUP_GARDER=3 règle la rotation" "$([ "$(ls "$rot" | grep -Ec '^db-')" = 3 ] && [ -d "$rot/db-2026-08-17" ]; echo $?)"
for invalide in 0 -1 abc; do
  DB_BACKUP_GARDER="$invalide" DB_BACKUP_SAUVEGARDES="$rot" DB_BACKUP_DATE="2026-08-18" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
  verifie "db_backup : DB_BACKUP_GARDER='$invalide' refusé (code 2), rien créé ni supprimé" "$([ $code -eq 2 ] && [ ! -e "$rot/db-2026-08-18" ] && [ "$(ls "$rot" | grep -Ec '^db-')" = 3 ]; echo $?)"
done

# Notification macOS (faux osascript) : seulement avec DB_BACKUP_NOTIFIER=1, et le message dit la cause.
notif="$tmp/notif"
: > "$OSA_LOG"
FAUX_CONTENEUR=0 DB_BACKUP_NOTIFIER=1 DB_BACKUP_SAUVEGARDES="$notif" DB_BACKUP_DATE="2026-10-11" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "db_backup : conteneur arrêté sous launchd, code 2, message clair et notification qui dit pourquoi" "$([ $code -eq 2 ] && grep -q 'conteneur de la base est arrêté' "$tmp/s" && [ "$(wc -l < "$OSA_LOG" | tr -d ' ')" = 1 ] && grep -q 'display notification' "$OSA_LOG" && grep -q 'conteneur de la base est arrêté' "$OSA_LOG" && grep -q 'code 2' "$OSA_LOG"; echo $?)"
verifie "db_backup : conteneur arrêté, aucun dossier de sauvegarde créé" "$([ ! -e "$notif/db-2026-10-11" ]; echo $?)"
: > "$OSA_LOG"
FAUX_DOCKER_INFO=1 DB_BACKUP_NOTIFIER=1 DB_BACKUP_SAUVEGARDES="$notif" DB_BACKUP_DATE="2026-10-11" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "db_backup : Colima arrêté sous launchd, code 2, notification qui nomme Colima" "$([ $code -eq 2 ] && grep -q 'Colima' "$OSA_LOG"; echo $?)"
: > "$OSA_LOG"
FAUX_CONTENEUR=0 DB_BACKUP_SAUVEGARDES="$notif" DB_BACKUP_DATE="2026-10-11" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "db_backup : lancé à la main (sans DB_BACKUP_NOTIFIER), échec sans notification" "$([ $code -eq 2 ] && [ ! -s "$OSA_LOG" ]; echo $?)"
: > "$OSA_LOG"
DB_BACKUP_NOTIFIER=1 DB_BACKUP_SAUVEGARDES="$notif" DB_BACKUP_DATE="2026-10-11" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "db_backup : sauvegarde réussie sous launchd, code 0, aucune notification" "$([ $code -eq 0 ] && [ ! -s "$OSA_LOG" ]; echo $?)"
: > "$OSA_LOG"
FAUX_ABSENTS="flow" DB_BACKUP_NOTIFIER=1 DB_BACKUP_SAUVEGARDES="$notif" DB_BACKUP_DATE="2026-10-12" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "db_backup : schéma absent sous launchd, code 1 et notification" "$([ $code -eq 1 ] && grep -q 'code 1' "$OSA_LOG"; echo $?)"
verifie "db_backup : aucune notification ne contient de mot de passe, de chemin de dump ni de contenu" "$(grep -Eq "$MDP|DUMP |\.dump" "$OSA_LOG"; [ $? -ne 0 ]; echo $?)"

# --- change run-worktree (D14) : repère de passage sauvegarde.encours, dossier de contenu, âge maximal
donnees="$tmp/donnees-labo"; mkdir -p "$donnees"; export PMZILLA_LAB_DATA="$donnees"
repere="$donnees/sauvegarde.encours"
unset DB_BACKUP_GARDER
: > "$FAUX_LOG"
DB_BACKUP_DATE="2027-01-01" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "repère : pendant la sauvegarde, le dossier existe et porte l'identifiant du processus du script" "$(l=$(grep -m1 '^MARQ' "$FAUX_LOG"); [ -n "$l" ] && [ "$(echo "$l" | sed -E 's/^MARQ ([0-9]*) PPID=.*/\1/')" = "$(echo "$l" | sed -E 's/.*PPID=//')" ] && echo "$l" | grep -Eq '^MARQ [0-9]+ '; echo $?)"
verifie "repère : après la sauvegarde, plus de repère, code 0" "$([ $code -eq 0 ] && [ ! -e "$repere" ]; echo $?)"

DB_BACKUP_DATE="2027-01-01" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "repère : sauvegarde du jour déjà présente (code 0) : aucun repère laissé" "$([ $code -eq 0 ] && grep -q 'existe déjà' "$tmp/s" && [ ! -e "$repere" ]; echo $?)"
DB_BACKUP_DATE="demain" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "repère : refus d'argument (code 2) : aucun repère créé ni laissé" "$([ $code -eq 2 ] && [ ! -e "$repere" ] && ! grep -q 'Repère' "$tmp/s"; echo $?)"

mkdir -p "$donnees/veille.verrou"; echo 4242 > "$donnees/veille.verrou/pid"
FAUX_ABSENTS="flow" DB_BACKUP_DATE="2027-01-02" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "repère : schéma absent (code 1) : plus de repère, et le verrou de la veille est intact" "$([ $code -eq 1 ] && [ ! -e "$repere" ] && [ "$(cat "$donnees/veille.verrou/pid")" = 4242 ]; echo $?)"
rm -rf "$donnees/veille.verrou"

( : ) & mort=$!; wait "$mort" 2>/dev/null
mkdir "$repere"; echo "$mort" > "$repere/pid"; date +%s > "$repere/debut"
DB_BACKUP_DATE="2027-01-03" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "repère : périmé (processus mort) : repris et journalisé, sauvegarde faite, aucun repère laissé" "$([ $code -eq 0 ] && grep -q '^Repère de passage périmé, repris$' "$tmp/s" && [ -s "$sauv/db-2027-01-03/cases.dump" ] && [ ! -e "$repere" ]; echo $?)"

mkdir "$repere"; echo "$$" > "$repere/pid"; date +%s > "$repere/debut"
DB_BACKUP_DATE="2027-01-04" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "repère : tenu par un processus vivant : sauvegarde faite sans repère propre, ligne journalisée, dossier intact" "$([ $code -eq 0 ] && grep -q '^Repère de passage déjà tenu : passage sans repère propre$' "$tmp/s" && [ -s "$sauv/db-2027-01-04/cases.dump" ] && [ "$(cat "$repere/pid")" = "$$" ]; echo $?)"
rm -rf "$repere"

mkdir "$repere"; echo "$$" > "$repere/pid"; echo 1 > "$repere/debut"
PMZILLA_RUN_MARKER_MAX_AGE=100 PMZILLA_RUN_NOW=5000 DB_BACKUP_DATE="2027-01-05" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "repère : processus vivant mais plus vieux que l'âge maximal : périmé, repris" "$([ $code -eq 0 ] && grep -q '^Repère de passage périmé, repris$' "$tmp/s" && [ ! -e "$repere" ]; echo $?)"

if [ "$(id -u)" != 0 ]; then
  ro="$tmp/donnees-ro"; mkdir -p "$ro"; chmod 500 "$ro"
  PMZILLA_LAB_DATA="$ro" DB_BACKUP_DATE="2027-01-06" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
  verifie "repère : dossier de données non inscriptible : ligne journalisée, dumps écrits, code inchangé (0)" "$([ $code -eq 0 ] && grep -q '^Repère de passage impossible à écrire$' "$tmp/s" && [ -s "$sauv/db-2027-01-06/cases.dump" ]; echo $?)"
  FAUX_ABSENTS="flow" PMZILLA_LAB_DATA="$ro" DB_BACKUP_DATE="2027-01-07" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
  verifie "repère : dossier de données non inscriptible et schéma absent : le code reste 1" "$([ $code -eq 1 ]; echo $?)"
  chmod 700 "$ro"
else
  echo "saut : lancé en administrateur, dossier non inscriptible non simulable"
fi

verifie "contenu : le script exporte PMZILLA_LAB_WORKSPACE" "$(grep -Eq '^export PMZILLA_LAB_WORKSPACE' "$racine/tools/db_backup.sh"; echo $?)"

defaut_db="$(grep -E '^[^#]*PMZILLA_RUN_MARKER_MAX_AGE:-[0-9]+' "$racine/tools/db_backup.sh" | head -1 | sed -E 's/.*PMZILLA_RUN_MARKER_MAX_AGE:-([0-9]+).*/\1/')"
defaut_run="$(grep -E '^[^#]*PMZILLA_RUN_MARKER_MAX_AGE:-[0-9]+' "$racine/tools/run_worktree.sh" | head -1 | sed -E 's/.*PMZILLA_RUN_MARKER_MAX_AGE:-([0-9]+).*/\1/')"
verifie "âge maximal du repère : la constante par défaut de db_backup.sh vaut 21600" "$([ "$defaut_db" = 21600 ]; echo $?)"
verifie "âge maximal du repère : la constante de db_backup.sh est celle de run_worktree.sh" "$([ -n "$defaut_db" ] && [ "$defaut_db" = "$defaut_run" ]; echo $?)"
unset PMZILLA_LAB_DATA

# --- docker-compose.yml : le mot de passe n'est pas exigé à l'interpolation (défaut constaté sur la vraie instance)
verifie "compose : POSTGRES_PASSWORD n'est pas déclaré obligatoire (pas de \${POSTGRES_PASSWORD:?)" "$(grep -q '\${POSTGRES_PASSWORD:?' "$racine/docker-compose.yml"; [ $? -ne 0 ]; echo $?)"
verifie "compose : /dev/shm du conteneur porté à 1 Go (la construction parallèle de l'index BM25 de la 0005 y a besoin de plus de 64 Mo)" "$(grep -Eq '^    shm_size: 1gb$' "$racine/docker-compose.yml"; echo $?)"
verifie "compose : aucune valeur de mot de passe écrite dans le fichier" "$(grep -E '^[^#]*POSTGRES_PASSWORD' "$racine/docker-compose.yml" | grep -Eq 'POSTGRES_PASSWORD: *"?[A-Za-z0-9]'; [ $? -ne 0 ]; echo $?)"
if [ -n "$VRAI_DOCKER" ] && HOME="$HOME_REEL" "$VRAI_DOCKER" compose version >/dev/null 2>&1; then
  env -u POSTGRES_PASSWORD HOME="$HOME_REEL" "$VRAI_DOCKER" compose -f "$racine/docker-compose.yml" config > "$tmp/c" 2>&1; code=$?
  verifie "compose : docker compose config réussit sans POSTGRES_PASSWORD (vrai docker)" "$code"
  verifie "compose : ps, port et exec n'ont pas besoin du mot de passe (config sans la variable ne mentionne pas « required »)" "$(grep -qi 'required variable' "$tmp/c"; [ $? -ne 0 ]; echo $?)"
else
  echo "saut : docker compose absent, docker compose config non vérifié"
fi

# Schémas par défaut : seuls knowledge, cases et flow sont sauvegardés, jamais public (donc pas public.schema_migrations,
# que le test de restauration recrée en appliquant les migrations).
verifie "db_backup : le dossier ne contient aucun dump de public ni de suivi des migrations" "$(ls "$sauv/db-2026-10-08" | grep -Eq 'public|migration'; [ $? -ne 0 ]; echo $?)"
verifie "db_backup : pg_dump n'est lancé que pour knowledge, cases et flow (-n), jamais pour public" "$([ "$(grep 'pg_dump' "$FAUX_LOG" | sed -E 's/.*-n ([a-z_]+).*/\1/' | sort -u | tr '\n' ' ')" = "cases flow knowledge " ] && ! grep 'pg_dump' "$FAUX_LOG" | grep -Eq -- '-n public|schema_migrations|-t '; echo $?)"

DB_BACKUP_DATE="demain" bash "$racine/tools/db_backup.sh" > "$tmp/s" 2>&1; code=$?
verifie "db_backup : date invalide refusée (code 2)" "$([ $code -eq 2 ]; echo $?)"

# --- db_restore_test.sh : suite voisine, avec son propre faux docker (sauvegarde fabriquée, conteneur jetable simulé)
bash "$racine/tests/db_scripts/test_db_restore_test.sh" > "$tmp/restore" 2>&1; code=$?
grep -v '^[0-9]* réussis' "$tmp/restore"
verifie "db_restore_test : suite voisine tests/db_scripts/test_db_restore_test.sh ($(grep -E '^[0-9]+ réussis' "$tmp/restore" | head -1))" "$code"

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
