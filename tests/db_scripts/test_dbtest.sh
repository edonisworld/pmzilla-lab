#!/bin/bash
# Test de tools/dbtest.sh : faux docker et faux lanceur de suites, aucun appel à Docker, à la base, au Trousseau ni au réseau.
# Le script n'est jamais lancé pour de bon par ce test.
# Lancement à la main : bash tests/db_scripts/test_dbtest.sh
set -u
racine="$(cd "$(dirname "$0")/../.." && pwd)"
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
bin="$tmp/bin"; mkdir -p "$bin"
ok=0; ko=0
verifie() { # description  code (0 = vrai)
  if [ "$2" -eq 0 ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1"; ko=$((ko+1)); fi
}

export FX="$tmp/fx"; mkdir -p "$FX"
export FAUX_LOG="$tmp/log"; : > "$FAUX_LOG"

# Faux docker : journal des appels (sans le mot de passe), le mot de passe reçu par « docker run » est mis à part (pw-recu).
cat > "$bin/docker" <<'SCRIPT'
#!/bin/bash
echo "docker $*" >> "$FAUX_LOG"
case "${1:-}" in
  info) [ "${FAUX_DOCKER_ARRETE:-0}" = "1" ] && exit 1; exit 0 ;;
  ps) [ -s "$FX/conteneurs" ] && echo "id-existant"; exit 0 ;;
  run)
    echo "${POSTGRES_PASSWORD:-}" > "$FX/pw-recu"
    [ "${FAUX_RUN_ECHEC:-0}" = "1" ] && { echo "port is already allocated" >&2; exit 125; }
    echo "pmzilla-lab-test-db" > "$FX/conteneurs"; echo "id-nouveau"; exit 0 ;;
  exec) exit "${FAUX_PRET:-0}" ;;
  rm) : > "$FX/conteneurs"; exit 0 ;;
esac
exit 0
SCRIPT
# Faux lanceur de suites : note la suite, le port, la présence du mot de passe, ce qui ne doit pas passer ; échoue ou s'interrompt à la demande.
cat > "$tmp/run_all_faux.sh" <<'SCRIPT'
#!/bin/bash
echo "suite=$1 port=${PMZILLA_LAB_DB_PORT:-} pw_longueur=${#PMZILLA_LAB_DB_PASSWORD} url=${PMZILLA_LAB_DB_URL:-absente} noevals=${PMZILLA_NO_EVALS-absente}" >> "$FX/suites"
echo "PW=${PMZILLA_LAB_DB_PASSWORD}" >> "$FX/pw-vu-par-les-suites"
[ "$1" = "${FAUX_SUITE_KO:-}" ] && exit 1
[ "$1" = "${FAUX_SUITE_CTRL_C:-}" ] && { kill -INT "$PPID"; sleep 1; exit 1; }
exit 0
SCRIPT
chmod +x "$bin/docker" "$tmp/run_all_faux.sh"
export PATH="$bin:$PATH"
export DBTEST_RUN_ALL="$tmp/run_all_faux.sh"
export DBTEST_ATTENTE=1
unset PMZILLA_LAB_DB_PASSWORD PMZILLA_LAB_DB_PORT PMZILLA_LAB_DB_URL POSTGRES_PASSWORD FAUX_SUITE_KO FAUX_SUITE_CTRL_C \
      FAUX_DOCKER_ARRETE FAUX_RUN_ECHEC FAUX_PRET

remise() { : > "$FAUX_LOG"; : > "$FX/conteneurs"; rm -f "$FX/suites" "$FX/pw-recu" "$FX/pw-vu-par-les-suites"; }
lance() { bash "$racine/tools/dbtest.sh" "$@" > "$tmp/s" 2>&1; code=$?; }
a_appele() { grep -q -- "$1" "$FAUX_LOG"; echo $?; }       # 0 si le motif figure au journal de docker
n_appels() { grep -c -- "$1" "$FAUX_LOG"; }

# --- aide et usage
remise; lance --help
verifie "dbtest : --help code 0, décrit le port et le nettoyage, ne touche pas à Docker" "$([ $code -eq 0 ] && grep -q -- '--port' "$tmp/s" && grep -q 'docker rm -f -v' "$tmp/s" && [ ! -s "$FAUX_LOG" ]; echo $?)"
remise; lance --bidon
verifie "dbtest : option inconnue refusée (code 2), Docker non appelé" "$([ $code -eq 2 ] && [ ! -s "$FAUX_LOG" ]; echo $?)"
remise; lance flow_inexistante
verifie "dbtest : suite inconnue refusée (code 2) avant tout démarrage" "$([ $code -eq 2 ] && grep -q 'Suite inconnue' "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
remise; lance '../tools'
verifie "dbtest : nom de suite avec chemin refusé (code 2)" "$([ $code -eq 2 ] && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"

# --- refus du port de la vraie base
remise; lance --port 5432
verifie "dbtest : port 5432 refusé (code 2), rien démarré" "$([ $code -eq 2 ] && grep -q 'Refus' "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
remise; PMZILLA_LAB_DB_PORT=5499 lance --port 5499
verifie "dbtest : port de la vraie base (PMZILLA_LAB_DB_PORT) refusé (code 2)" "$([ $code -eq 2 ] && grep -q 'Refus' "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
remise; lance --port abc
verifie "dbtest : port invalide refusé (code 2)" "$([ $code -eq 2 ]; echo $?)"

# --- prérequis
remise; FAUX_DOCKER_ARRETE=1 lance flow_store
verifie "dbtest : Docker arrêté, refus (code 2) avec le conseil Colima" "$([ $code -eq 2 ] && grep -q 'colima' "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
remise; echo "pmzilla-lab-test-db" > "$FX/conteneurs"; lance flow_store
verifie "dbtest : conteneur déjà présent, refus (code 2), ni démarré, ni supprimé" "$([ $code -eq 2 ] && grep -q 'existe déjà' "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ] && [ "$(n_appels 'docker rm')" -eq 0 ] && [ -s "$FX/conteneurs" ]; echo $?)"

# --- passage nominal
remise; lance
verifie "dbtest : passage nominal, code 0" "$([ $code -eq 0 ]; echo $?)"
verifie "dbtest : suites par défaut, dans l'ordre" "$([ "$(sed -n 's/^suite=\([^ ]*\) .*/\1/p' "$FX/suites" | tr '\n' ' ')" = "db flow_import flow_store flow_compare flow_views hybrid_search pmzilla_lab_library library_backend cases_store watch_store " ]; echo $?)"
verifie "dbtest : conteneur publié sur 127.0.0.1:55432 seulement, nom fixe, image de docker-compose.yml" "$(grep '^docker run' "$FAUX_LOG" | grep -q -- '--name pmzilla-lab-test-db' && grep '^docker run' "$FAUX_LOG" | grep -q -- '-p 127.0.0.1:55432:5432' && grep '^docker run' "$FAUX_LOG" | grep -q "$(grep -E '^[[:space:]]+image:' "$racine/docker-compose.yml" | head -1 | sed -E 's/^[[:space:]]+image:[[:space:]]*//; s/["[:space:]]//g')"; echo $?)"
verifie "dbtest : chaque suite reçoit le port jetable, un mot de passe de 32 caractères, ni URL ni PMZILLA_NO_EVALS" "$(! grep -v 'port=55432 pw_longueur=32 url=absente noevals=absente' "$FX/suites" | grep -q .; echo $?)"
verifie "dbtest : conteneur supprimé avec ses volumes à la fin" "$(grep -q 'docker rm -f -v pmzilla-lab-test-db' "$FAUX_LOG"; [ $? -eq 0 ] && [ ! -s "$FX/conteneurs" ]; echo $?)"
verifie "dbtest : résumé vert, aucune suite en échec" "$(grep -q 'Suites vertes : db flow_import flow_store flow_compare flow_views hybrid_search pmzilla_lab_library library_backend cases_store watch_store' "$tmp/s" && grep -q 'Suites en échec : aucune' "$tmp/s"; echo $?)"
mdp="$(sed 's/^PW=//' "$FX/pw-recu" | head -1)"
verifie "dbtest : le mot de passe donné au conteneur est celui des suites (32 caractères hexadécimaux)" "$(printf '%s' "$mdp" | grep -Eq '^[0-9a-f]{32}$' && grep -qx "PW=$mdp" "$FX/pw-vu-par-les-suites"; echo $?)"
verifie "dbtest : le mot de passe n'apparaît ni à l'affichage ni dans les arguments de docker" "$(! grep -q -- "$mdp" "$tmp/s" && ! grep -q -- "$mdp" "$FAUX_LOG"; echo $?)"

# --- suites choisies et port choisi
remise; lance --port 55433 flow_store flow_compare
verifie "dbtest : suites données et --port respectés" "$([ $code -eq 0 ] && [ "$(sed -n 's/^suite=\([^ ]*\) .*/\1/p' "$FX/suites" | tr '\n' ' ')" = "flow_store flow_compare " ] && grep -q 'port=55433' "$FX/suites" && grep '^docker run' "$FAUX_LOG" | grep -q -- '-p 127.0.0.1:55433:5432'; echo $?)"
remise; PMZILLA_LAB_DB_URL="postgresql://x@127.0.0.1:5432/pmzilla" PMZILLA_NO_EVALS=1 lance flow_store
verifie "dbtest : l'URL et PMZILLA_NO_EVALS de l'environnement ne passent pas aux suites" "$([ $code -eq 0 ] && grep -q 'url=absente noevals=absente' "$FX/suites"; echo $?)"

# --- échec d'une suite
remise; FAUX_SUITE_KO=flow_store lance db flow_store flow_compare
verifie "dbtest : une suite en échec : code 1, les autres tournent, résumé nommé" "$([ $code -eq 1 ] && [ "$(wc -l < "$FX/suites" | tr -d ' ')" -eq 3 ] && grep -q 'Suites vertes : db flow_compare' "$tmp/s" && grep -q 'Suites en échec : flow_store' "$tmp/s"; echo $?)"
verifie "dbtest : conteneur supprimé après un échec de suite" "$([ ! -s "$FX/conteneurs" ] && grep -q 'docker rm -f -v' "$FAUX_LOG"; echo $?)"

# --- nettoyage par le trap
remise; FAUX_RUN_ECHEC=1 lance flow_store
verifie "dbtest : démarrage en échec, code 1, nettoyage tenté, aucune suite lancée" "$([ $code -eq 1 ] && grep -q 'docker rm -f -v' "$FAUX_LOG" && [ ! -e "$FX/suites" ]; echo $?)"
remise; FAUX_PRET=1 lance flow_store
verifie "dbtest : conteneur jamais prêt, code 1, message, conteneur supprimé, aucune suite lancée" "$([ $code -eq 1 ] && grep -q 'pas prêt' "$tmp/s" && grep -q 'docker rm -f -v' "$FAUX_LOG" && [ ! -e "$FX/suites" ]; echo $?)"
remise; FAUX_SUITE_CTRL_C=flow_store lance db flow_store flow_compare
verifie "dbtest : Ctrl+C pendant une suite : code 130, conteneur supprimé, suites suivantes non lancées" "$([ $code -eq 130 ] && grep -q 'docker rm -f -v' "$FAUX_LOG" && [ ! -s "$FX/conteneurs" ] && ! grep -q 'suite=flow_compare' "$FX/suites"; echo $?)"

# --- hygiène du script
verifie "dbtest : pas de set -x, pas de docker compose, pas de Trousseau, pas d'export du mot de passe, pas de tube vers les suites" "$(grep -Eq '^[^#]*(set -[a-z]*x|docker compose|security find|export PMZILLA_LAB_DB_PASSWORD|run_all.*\|)' "$racine/tools/dbtest.sh"; [ $? -ne 0 ]; echo $?)"
verifie "dbtest : le mot de passe n'est jamais affiché (aucun echo ni printf de la variable)" "$(grep -Eq '(echo|printf)[^|#]*\$\{?mdp' "$racine/tools/dbtest.sh"; [ $? -ne 0 ]; echo $?)"

# --- /dev/shm du conteneur jetable : shm_size lu dans docker-compose.yml (R-22), jamais recopié ; repli 1g
verifie "dbtest : docker run reçoit --shm-size, avec la valeur de shm_size du compose réel" "$(remise; lance db; v="$(grep -E '^[[:space:]]+shm_size:' "$racine/docker-compose.yml" | head -1 | sed -E 's/^[[:space:]]+shm_size:[[:space:]]*//; s/[#].*$//; s/["[:space:]]//g')"; [ -n "$v" ] && grep '^docker run' "$FAUX_LOG" | grep -q -- "--shm-size $v "; echo $?)"
racine_shm() {   # $1 = ligne shm_size du compose factice (vide : aucune) ; lance une copie du script dans une racine temporaire
  rm -rf "$tmp/root"; mkdir -p "$tmp/root/tools" "$tmp/root/tests/db"
  cp "$racine/tools/dbtest.sh" "$tmp/root/tools/"
  { grep -v 'shm_size' "$racine/docker-compose.yml"; [ -n "$1" ] && echo "    $1"; } > "$tmp/root/docker-compose.yml"
  remise; bash "$tmp/root/tools/dbtest.sh" db > "$tmp/s" 2>&1; code=$?
}
racine_shm "shm_size: 2gb  # commentaire"
verifie "dbtest : la valeur vient du compose (2gb), commentaire retiré" "$(grep '^docker run' "$FAUX_LOG" | grep -q -- '--shm-size 2gb '; echo $?)"
racine_shm ""
verifie "dbtest : sans shm_size dans le compose, repli 1g" "$(grep '^docker run' "$FAUX_LOG" | grep -q -- '--shm-size 1g '; echo $?)"
racine_shm "shm_size: grand; rm -rf /"
verifie "dbtest : shm_size illisible, repli 1g (la valeur n'est jamais passée telle quelle)" "$(grep '^docker run' "$FAUX_LOG" | grep -q -- '--shm-size 1g ' && ! grep -q 'rm -rf' "$FAUX_LOG"; echo $?)"

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
exit 0
