#!/bin/bash
# Test de tools/dbtest.sh : faux docker et faux lanceur de suites, aucun appel à Docker, à la base, au Trousseau ni au réseau.
# Le script n'est jamais lancé pour de bon par ce test.
# Lancement à la main : bash tests/db_scripts/test_dbtest.sh
set -u
# Remplace l'héritage de FINISH_LOCK_TOKEN : pendant une vraie fin, le runner lance cette suite avec le jeton de la fin, et dbtest.sh choisit alors la branche « pendant une fin de branche » (refus du port occupé, gel) au lieu de celle que les cas existants vérifient.
# Condition de retrait : permanente tant que dbtest.sh distingue le cas « pendant une fin » par ce jeton ; les cas qui en ont besoin le posent eux-mêmes (préfixe FINISH_LOCK_TOKEN=... devant lance/lance_dep).
unset FINISH_LOCK_TOKEN
racine="$(cd "$(dirname "$0")/../.." && pwd)"
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
bin="$tmp/bin"; mkdir -p "$bin"
ok=0; ko=0
verifie() { # description  code (0 = vrai)
  if [ "$2" -eq 0 ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1"; ko=$((ko+1)); fi
}

# Les passages « lance » tournent sur une COPIE du script dans une racine temporaire hors de tout dépôt Git : sinon le script lit le dossier Git du
# vrai dépôt, et le verrou de fin de branche d'une autre session (finish, run_all) le fait répondre « code 3 » à tous les cas avec Docker (R-135).
export GIT_CEILING_DIRECTORIES="$tmp"
racine_lance="$tmp/racine-lance"; mkdir -p "$racine_lance/tools"
cp "$racine/tools/dbtest.sh" "$racine_lance/tools/"; cp "$racine/docker-compose.yml" "$racine_lance/"
cp "$racine/tools/e2e_steps.sh" "$racine_lance/tools/"   # R-20261101-113 : dbtest.sh source tools/e2e_steps.sh de son arbre (donnée d'entrée, aucune assertion changée)
for s in db flow_import flow_store flow_views hybrid_search pmzilla_lab_library library_backend cases_store watch_store book_usage dashboard flow_retention posture_evals export_jira_api history_jira story_quality mothra_donnees flow_compare; do
  mkdir -p "$racine_lance/tests/$s"
done
# La suite npm « mothra » (mothra-slices, groupe 3) : déclarée par la ligne SUITES_NPM de tests/run_all.sh, SANS dossier tests/mothra.
printf '#!/bin/bash\nSUITES_NPM=(mothra:mothra)\n' > "$racine_lance/tests/run_all.sh"

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
    echo "${PGPASSWORD:-}" > "$FX/pgpw-recu"
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
echo "suite=$1 port=${PMZILLA_LAB_DB_PORT:-} pw_longueur=${#PMZILLA_LAB_DB_PASSWORD} url=${PMZILLA_LAB_DB_URL:-absente} noevals=${PMZILLA_NO_EVALS-absente} marque=${DBTEST_PORT:-absente} variables=$(compgen -v PMZILLA_LAB_DB_ | sort | tr '\n' ',')" >> "$FX/suites"
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
# Le script est lancé via un relais qui rétablit SIGINT par défaut avant d'exécuter bash : lancé en arrière-plan (« & » sans terminal), ce
# test hérite de SIGINT ignoré, et un signal ignoré à l'entrée d'un shell ne peut plus être piégé (le trap INT de dbtest.sh serait inopérant).
# Au Terminal, SIGINT n'est pas ignoré : le relais recrée cette condition, le test vérifie le trap quel que soit le lancement (#242).
lance() { python3 -I -B -c 'import os, signal, sys; signal.signal(signal.SIGINT, signal.SIG_DFL); os.execvp("/bin/bash", ["/bin/bash"] + sys.argv[1:])' "$racine_lance/tools/dbtest.sh" "$@" > "$tmp/s" 2>&1; code=$?; }
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
# Suite npm (mothra-slices, groupe 3) : un nom déclaré par la ligne SUITES_NPM de tests/run_all.sh est une suite valable sans dossier tests/<nom>.
remise; lance mothra
verifie "dbtest : suite npm déclarée par SUITES_NPM acceptée sans dossier de suite (code 0)" "$([ $code -eq 0 ] && [ "$(sed -n 's/^suite=\([^ ]*\) .*/\1/p' "$FX/suites" | tr '\n' ' ')" = "mothra " ]; echo $?)"
printf '#!/bin/bash\n' > "$racine_lance/tests/run_all.sh"
remise; lance mothra
verifie "dbtest : sans déclaration, le nom d'une suite npm est une suite inconnue (code 2)" "$([ $code -eq 2 ] && grep -q 'Suite inconnue' "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
printf '#!/bin/bash\nSUITES_NPM=(mothra:mothra extra)\n' > "$racine_lance/tests/run_all.sh"
remise; lance mothra2
verifie "dbtest : seul le nom d'une entrée déclarée est une suite valable (code 2)" "$([ $code -eq 2 ] && grep -q 'Suite inconnue' "$tmp/s"; echo $?)"
printf '#!/bin/bash\nSUITES_NPM=(mothra:mothra)\n' > "$racine_lance/tests/run_all.sh"

# --- refus du port de la vraie base
remise; lance --port 5432
verifie "dbtest : port 5432 refusé (code 2), rien démarré" "$([ $code -eq 2 ] && grep -q 'Refus' "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
remise; PMZILLA_LAB_DB_PORT=5499 lance --port 5499
verifie "dbtest : port de la vraie base (PMZILLA_LAB_DB_PORT) refusé (code 2)" "$([ $code -eq 2 ] && grep -q 'Refus' "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
remise; lance --port abc
verifie "dbtest : port invalide refusé (code 2)" "$([ $code -eq 2 ]; echo $?)"

# --- une seule règle de port (test-db-guards, D1) : forme décimale simple, comparaison en nombre
for forme in "05432" "+55432" "-55432" " 55432" "55432 " "65536" "99999" "0" "00" "1e4" $'55432\nx' "٥٥٤٣٢" ""; do
  remise; lance --port "$forme"
  verifie "dbtest : --port invalide $(printf '%q' "$forme") refusé (code 2, « Port invalide »), rien démarré" "$([ $code -eq 2 ] && grep -q '^Port invalide : ' "$tmp/s" && [ ! -s "$FAUX_LOG" ]; echo $?)"
done
remise; lance --port 5432
verifie "dbtest : 5432 reste refusé par la ligne de refus (code 2)" "$([ $code -eq 2 ] && grep -q '^Refus : le port 5432 est celui de la vraie base' "$tmp/s" && [ ! -s "$FAUX_LOG" ]; echo $?)"
remise; PMZILLA_LAB_DB_PORT=55499 lance --port 55499
verifie "dbtest : port de la vraie base écrit à l'identique refusé (ligne de refus, rien démarré)" "$([ $code -eq 2 ] && grep -q '^Refus : le port 55499 est celui de la vraie base' "$tmp/s" && [ ! -s "$FAUX_LOG" ]; echo $?)"
for reel in "05432" "055499" " 55499" "+55499" "55499 " "65536" "0" "abc" "55499x"; do
  remise; PMZILLA_LAB_DB_PORT="$reel" lance --port 55433
  verifie "dbtest : port configuré de la vraie base illisible $(printf '%q' "$reel") refusé (code 2, ligne dédiée), rien démarré" "$([ $code -eq 2 ] && grep -qxF 'Refus : le port configuré de la vraie base est illisible (PMZILLA_LAB_DB_PORT) : corrige-le ou retire-le, puis relance.' "$tmp/s" && [ ! -s "$FAUX_LOG" ]; echo $?)"
done
remise; PMZILLA_LAB_DB_PORT=55433 lance --port 55434 flow_store
verifie "dbtest : port configuré valide et différent, le passage a lieu (code 0)" "$([ $code -eq 0 ] && grep -q 'port=55434' "$FX/suites"; echo $?)"
remise; PMZILLA_LAB_DB_PORT= lance flow_store
verifie "dbtest : port configuré vide traité comme absent (code 0)" "$([ $code -eq 0 ]; echo $?)"
verifie "dbtest : la base jetable est créée avec scram-sha-256 pour l'hôte et le socket local (POSTGRES_INITDB_ARGS), comme celle de ci_local" "$(grep '^docker run' "$FAUX_LOG" | grep -qF -- '-e POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256 --auth-local=scram-sha-256'; echo $?)"

# --- prérequis
remise; FAUX_DOCKER_ARRETE=1 lance flow_store
verifie "dbtest : Docker arrêté, refus (code 2) avec le conseil Colima" "$([ $code -eq 2 ] && grep -q 'colima' "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
remise; echo "pmzilla-lab-test-db" > "$FX/conteneurs"; lance flow_store
verifie "dbtest : conteneur déjà présent, refus (code 2), ni démarré, ni supprimé" "$([ $code -eq 2 ] && grep -q 'existe déjà' "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ] && [ "$(n_appels 'docker rm')" -eq 0 ] && [ -s "$FX/conteneurs" ]; echo $?)"

# --- passage nominal
remise; lance
verifie "dbtest : passage nominal, code 0" "$([ $code -eq 0 ]; echo $?)"
verifie "dbtest : suites par défaut, dans l'ordre" "$([ "$(sed -n 's/^suite=\([^ ]*\) .*/\1/p' "$FX/suites" | tr '\n' ' ')" = "db flow_import flow_store flow_views hybrid_search pmzilla_lab_library library_backend cases_store watch_store book_usage dashboard flow_retention posture_evals export_jira_api history_jira story_quality mothra_donnees mothra " ]; echo $?)"
verifie "dbtest : conteneur publié sur 127.0.0.1:55432 seulement, nom fixe, image de docker-compose.yml" "$(grep '^docker run' "$FAUX_LOG" | grep -q -- '--name pmzilla-lab-test-db' && grep '^docker run' "$FAUX_LOG" | grep -q -- '-p 127.0.0.1:55432:5432' && grep '^docker run' "$FAUX_LOG" | grep -q "$(grep -E '^[[:space:]]+image:' "$racine/docker-compose.yml" | head -1 | sed -E 's/^[[:space:]]+image:[[:space:]]*//; s/["[:space:]]//g')"; echo $?)"
verifie "dbtest : chaque suite reçoit le port jetable, un mot de passe de 32 caractères, ni URL ni PMZILLA_NO_EVALS" "$(! grep -v 'port=55432 pw_longueur=32 url=absente noevals=absente' "$FX/suites" | grep -q .; echo $?)"
verifie "dbtest : conteneur supprimé avec ses volumes à la fin" "$(grep -q 'docker rm -f -v pmzilla-lab-test-db' "$FAUX_LOG"; [ $? -eq 0 ] && [ ! -s "$FX/conteneurs" ]; echo $?)"
verifie "dbtest : résumé vert, aucune suite en échec" "$(grep -qx 'Suites vertes : db flow_import flow_store flow_views hybrid_search pmzilla_lab_library library_backend cases_store watch_store book_usage dashboard flow_retention posture_evals export_jira_api history_jira story_quality mothra_donnees mothra' "$tmp/s" && grep -q 'Suites en échec : aucune' "$tmp/s"; echo $?)"
mdp="$(sed 's/^PW=//' "$FX/pw-recu" | head -1)"
verifie "dbtest : le mot de passe donné au conteneur est celui des suites (32 caractères hexadécimaux)" "$(printf '%s' "$mdp" | grep -Eq '^[0-9a-f]{32}$' && grep -qx "PW=$mdp" "$FX/pw-vu-par-les-suites"; echo $?)"
verifie "dbtest : le mot de passe n'apparaît ni à l'affichage ni dans les arguments de docker" "$(! grep -q -- "$mdp" "$tmp/s" && ! grep -q -- "$mdp" "$FAUX_LOG"; echo $?)"

# --- suites choisies et port choisi
remise; lance --port 55433 flow_store flow_compare
verifie "dbtest : suites données et --port respectés" "$([ $code -eq 0 ] && [ "$(sed -n 's/^suite=\([^ ]*\) .*/\1/p' "$FX/suites" | tr '\n' ' ')" = "flow_store flow_compare " ] && grep -q 'port=55433' "$FX/suites" && grep '^docker run' "$FAUX_LOG" | grep -q -- '-p 127.0.0.1:55433:5432'; echo $?)"
remise; PMZILLA_LAB_DB_URL="postgresql://x@127.0.0.1:5432/pmzilla" PMZILLA_NO_EVALS=1 lance flow_store
verifie "dbtest : l'URL et PMZILLA_NO_EVALS de l'environnement ne passent pas aux suites" "$([ $code -eq 0 ] && grep -q 'url=absente noevals=absente' "$FX/suites"; echo $?)"
remise; lance flow_store
[ $code -eq 0 ] && grep -q 'port=55432 .* marque=55432 variables=PMZILLA_LAB_DB_PASSWORD,PMZILLA_LAB_DB_PORT,$' "$FX/suites"; rc=$?
verifie "dbtest : chaque suite reçoit DBTEST_PORT égal à son port (test-speed-2, D1) et seulement le port et le mot de passe comme variables de base" $rc
remise; lance --port 55433 flow_store
[ $code -eq 0 ] && grep -q 'port=55433 .* marque=55433 ' "$FX/suites"; rc=$?
verifie "dbtest : DBTEST_PORT suit --port" $rc
faux_role="role-de-"'l-appelant'   # fabriqué à l'exécution : aucun littéral pour la garde des secrets
remise; PMZILLA_LAB_DB_PASSWORD_FLOW="$faux_role" PMZILLA_LAB_DB_SECURITY_BIN="/faux/security" PMZILLA_LAB_DB_URL="postgresql://x@127.0.0.1:5432/pmzilla" DBTEST_PORT=5432 lance flow_store
[ $code -eq 0 ] && grep -q 'marque=55432 variables=PMZILLA_LAB_DB_PASSWORD,PMZILLA_LAB_DB_PORT,$' "$FX/suites"; rc=$?
verifie "dbtest : les variables de base de l'appelant (mot de passe d'un rôle, trousseau, adresse) et son DBTEST_PORT ne passent pas" $rc

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

# --- empreinte d'un passage vert (test-speed-2, D5) : copie du script dans un dépôt temporaire, faux Docker, faux lanceur de suites.
# DBTEST_RECORD désigne le fichier des empreintes ; le vrai dossier Git du dépôt n'est jamais touché par ces cas.
SUITES_14="db flow_import flow_store flow_views hybrid_search pmzilla_lab_library library_backend cases_store watch_store book_usage dashboard flow_retention posture_evals export_jira_api history_jira story_quality mothra_donnees"
depot="$tmp/depot"; REC="$tmp/empreintes"; export DEPOT="$depot"
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null   # aucun réglage ni hook de l'utilisateur dans les dépôts temporaires
GIT_T="git -c user.email=t@example.org -c user.name=test"
depot_neuf() { # dépôt Git temporaire : copie du script, du compose, un dossier par suite par défaut, un faux tests/run_all.sh
  rm -rf "$depot" "$REC"; mkdir -p "$depot/tools" "$depot/tests"
  cp "$racine/tools/dbtest.sh" "$depot/tools/"; cp "$racine/docker-compose.yml" "$depot/"
  cp "$racine/tools/e2e_steps.sh" "$depot/tools/"   # R-20261101-113 (donnée d'entrée, aucune assertion changée)
  for s in $SUITES_14; do mkdir -p "$depot/tests/$s"; : > "$depot/tests/$s/.gitkeep"; done
  printf '#!/bin/bash\nSUITES_NPM=(mothra:mothra)\nexit 0\n' > "$depot/tests/run_all.sh"
  ( cd "$depot" && git init -q && git add -A && $GIT_T commit -q -m initial )
  arbre=$(git -C "$depot" rev-parse 'HEAD^{tree}')
}
lance_dep() { # arguments de dbtest.sh ; le script du dépôt temporaire, SIGINT par défaut comme lance()
  python3 -I -B -c 'import os, signal, sys; signal.signal(signal.SIGINT, signal.SIG_DFL); os.execvp("/bin/bash", ["/bin/bash"] + sys.argv[1:])' "$depot/tools/dbtest.sh" "$@" > "$tmp/s" 2>&1; code=$?
}
cat > "$tmp/run_all_commit.sh" <<'SCRIPT'
#!/bin/bash
# Faux lanceur qui commite pendant le passage : l'arbre de HEAD change, l'arbre de travail reste propre.
cd "$DEPOT" && echo "$1" > "pendant-$1.txt" && git add -A && git -c user.email=t@example.org -c user.name=test commit -q -m pendant
exit 0
SCRIPT
chmod +x "$tmp/run_all_commit.sh"
export DBTEST_RECORD="$REC"
# Le faux Docker ne publie aucun port : la sonde depuis l'hôte (le port du conteneur répond-il ?) est remplacée par un script qui réussit,
# sauf dans les cas qui testent la sonde elle-même.
printf '#!/bin/bash\nexit 0\n' > "$tmp/sonde_ok.sh"; chmod +x "$tmp/sonde_ok.sh"; export DBTEST_SONDE="$tmp/sonde_ok.sh"
LIGNE_OK="Empreinte dbtest enregistrée : la fin de branche l'acceptera pour cet arbre."

depot_neuf; remise; lance_dep
[ $code -eq 0 ] && [ "$(cat "$REC" 2>/dev/null)" = "$arbre" ] && grep -qxF "$LIGNE_OK" "$tmp/s"; rc=$?
verifie "dbtest empreinte : passage vert par défaut, arbre propre : l'arbre de HEAD est inscrit et la ligne est affichée (code 0)" $rc
[ "$(stat -f %Lp "$REC" 2>/dev/null || stat -c %a "$REC" 2>/dev/null)" = "600" ]; rc=$?
verifie "dbtest empreinte : le fichier des empreintes est lisible par son propriétaire seul" $rc
[ -z "$(find "$tmp" -maxdepth 1 -name 'empreintes.tmp*' 2>/dev/null)" ]; rc=$?
verifie "dbtest empreinte : aucun fichier temporaire ne reste" $rc
printf '%s\n' "autre-arbre-1111" > "$REC"; remise; lance_dep; lance_dep
[ "$(grep -cx "$arbre" "$REC")" -eq 1 ] && grep -qx "autre-arbre-1111" "$REC"; rc=$?
verifie "dbtest empreinte : deux passages verts du même arbre n'inscrivent qu'une ligne, la ligne d'un autre arbre est conservée" $rc
grep -Evq '^[0-9a-f]{40}$|^autre-arbre-1111$' "$REC"; [ $? -ne 0 ] && [ -s "$REC" ]; rc=$?
verifie "dbtest empreinte : le fichier ne contient que des identifiants d'arbre (ni chemin, ni branche, ni mot de passe)" $rc

depot_neuf; remise; lance_dep db flow_store
[ $code -eq 0 ] && [ ! -e "$REC" ] && grep -qxF "Empreinte dbtest non écrite (suites choisies)" "$tmp/s"; rc=$?
verifie "dbtest empreinte : suites nommées, aucune ligne, raison « suites choisies » (code 0)" $rc
remise; lance_dep --port 55433
[ $code -eq 0 ] && [ "$(cat "$REC" 2>/dev/null)" = "$arbre" ]; rc=$?
verifie "dbtest empreinte : --port seul n'empêche pas l'empreinte (liste par défaut)" $rc

# le port du conteneur doit répondre depuis l'hôte : sinon les tests de base sont sautés, le passage est vert pour rien
depot_neuf; remise; DBTEST_SONDE=/usr/bin/false lance_dep
[ $code -eq 0 ] && [ ! -e "$REC" ] && grep -qxF "Empreinte dbtest non écrite (base injoignable depuis l'hôte)" "$tmp/s" && ! grep -q "Empreinte dbtest enregistrée" "$tmp/s"; rc=$?
verifie "dbtest empreinte : le port du conteneur ne répond pas depuis l'hôte, aucune ligne, raison « base injoignable depuis l'hôte » (code 0)" $rc
port_ferme=$(python3 -I -B -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')   # libre, donc fermé
depot_neuf; remise; DBTEST_SONDE= lance_dep --port "$port_ferme"
[ $code -eq 0 ] && [ ! -e "$REC" ] && grep -qxF "Empreinte dbtest non écrite (base injoignable depuis l'hôte)" "$tmp/s"; rc=$?
verifie "dbtest empreinte : sonde réelle, aucun écouteur sur le port, aucune ligne" $rc
rm -f "$tmp/ecoute"
python3 -I -B -c 'import socket, sys
s = socket.socket(); s.bind(("127.0.0.1", 0)); s.listen(8)
open(sys.argv[1], "w").write(str(s.getsockname()[1]))
while True:
    s.accept()' "$tmp/ecoute" &
ECOUTEUR=$!
i=0; while [ ! -s "$tmp/ecoute" ]; do [ "$i" -lt 2400 ] || { echo "test dbtest : borne de sécurité de 120 secondes atteinte, l'écouteur n'a jamais écrit son port" >&2; break; }; i=$((i+1)); sleep 0.05; done
port_ouvert=$(cat "$tmp/ecoute" 2>/dev/null)
depot_neuf; remise; DBTEST_SONDE= lance_dep --port "${port_ouvert:-1}"
[ $code -eq 0 ] && [ "$(cat "$REC" 2>/dev/null)" = "$arbre" ] && grep -qxF "$LIGNE_OK" "$tmp/s"; rc=$?
verifie "dbtest empreinte : sonde réelle, le port répond depuis l'hôte, l'empreinte est écrite" $rc
kill "$ECOUTEUR" 2>/dev/null; wait "$ECOUTEUR" 2>/dev/null

depot_neuf; echo x > "$depot/nouveau.txt"; remise; lance_dep
[ $code -eq 0 ] && [ ! -e "$REC" ] && grep -qxF "Empreinte dbtest non écrite (arbre non propre)" "$tmp/s"; rc=$?
verifie "dbtest empreinte : fichier non suivi au départ, aucune ligne, raison « arbre non propre » (code 0)" $rc
depot_neuf; echo x >> "$depot/docker-compose.yml"; remise; lance_dep
[ $code -eq 0 ] && [ ! -e "$REC" ] && grep -qxF "Empreinte dbtest non écrite (arbre non propre)" "$tmp/s"; rc=$?
verifie "dbtest empreinte : fichier suivi modifié au départ, aucune ligne, raison « arbre non propre »" $rc
depot_neuf; remise
printf '#!/bin/bash\necho x > "$DEPOT/produit-par-la-suite.txt"\nexit 0\n' > "$tmp/run_all_dirty.sh"; chmod +x "$tmp/run_all_dirty.sh"
DBTEST_RUN_ALL="$tmp/run_all_dirty.sh" lance_dep
[ $code -eq 0 ] && [ ! -e "$REC" ] && grep -qxF "Empreinte dbtest non écrite (arbre non propre)" "$tmp/s"; rc=$?
verifie "dbtest empreinte : fichier non suivi apparu pendant le passage, aucune ligne, raison « arbre non propre »" $rc

depot_neuf; remise; DBTEST_RUN_ALL="$tmp/run_all_commit.sh" lance_dep
[ $code -eq 0 ] && [ ! -e "$REC" ] && grep -qxF "Empreinte dbtest non écrite (arbre changé pendant le passage)" "$tmp/s"; rc=$?
verifie "dbtest empreinte : l'arbre de HEAD change pendant le passage, aucune ligne, raison « arbre changé pendant le passage »" $rc

# un passage rouge n'écrit rien, n'affiche rien, et retire la ligne de l'arbre courant
depot_neuf; printf '%s\n%s\n' "$arbre" "autre-arbre-2222" > "$REC"; remise; FAUX_SUITE_KO=flow_store lance_dep
[ $code -eq 1 ] && ! grep -q "Empreinte" "$tmp/s" && ! grep -qx "$arbre" "$REC" && grep -qx "autre-arbre-2222" "$REC"; rc=$?
verifie "dbtest empreinte : suite rouge (code 1), rien n'est affiché, la ligne de l'arbre courant est retirée, celle d'un autre arbre reste" $rc
# la ligne de l'arbre courant est retirée dès le départ, même quand ce passage n'en écrit pas
depot_neuf; printf '%s\n%s\n' "$arbre" "autre-arbre-3333" > "$REC"; remise; lance_dep db
[ $code -eq 0 ] && ! grep -qx "$arbre" "$REC" && grep -qx "autre-arbre-3333" "$REC"; rc=$?
verifie "dbtest empreinte : un passage à suites nommées retire la ligne de l'arbre courant au départ" $rc

# lanceur remplacé sans DBTEST_RECORD : rien n'est écrit dans le dossier Git du dépôt
depot_neuf; remise; env -u DBTEST_RECORD python3 -I -B -c 'import os, signal, sys; signal.signal(signal.SIGINT, signal.SIG_DFL); os.execvp("/bin/bash", ["/bin/bash"] + sys.argv[1:])' "$depot/tools/dbtest.sh" > "$tmp/s" 2>&1; code=$?
[ $code -eq 0 ] && [ ! -e "$depot/.git/pmzilla-dbtest-ok" ] && ! grep -q "Empreinte" "$tmp/s"; rc=$?
verifie "dbtest empreinte : lanceur remplacé (DBTEST_RUN_ALL) sans DBTEST_RECORD : rien dans le dossier Git, aucune ligne" $rc

# lancement par défaut : l'empreinte va dans le dossier Git commun, aussi depuis un worktree
depot_neuf; rm -f "$REC"; git -C "$depot" worktree add -q "$tmp/depot-wt" -b branche-wt 2>/dev/null
arbre_wt=$(git -C "$tmp/depot-wt" rev-parse 'HEAD^{tree}')
remise; env -u DBTEST_RECORD -u DBTEST_RUN_ALL python3 -I -B -c 'import os, signal, sys; signal.signal(signal.SIGINT, signal.SIG_DFL); os.execvp("/bin/bash", ["/bin/bash"] + sys.argv[1:])' "$tmp/depot-wt/tools/dbtest.sh" > "$tmp/s" 2>&1; code=$?
[ $code -eq 0 ] && [ "$(cat "$depot/.git/pmzilla-dbtest-ok" 2>/dev/null)" = "$arbre_wt" ] && [ ! -e "$tmp/depot-wt/.git/pmzilla-dbtest-ok" ]; rc=$?
verifie "dbtest empreinte : sans variable de test, l'empreinte est dans le dossier Git commun (depuis un worktree), pas dans le dossier du worktree" $rc
git -C "$depot" worktree remove --force "$tmp/depot-wt" 2>/dev/null

# hors dépôt Git, écriture impossible : rien ne change le code de sortie
rm -rf "$tmp/horsgit"; mkdir -p "$tmp/horsgit/tools" "$tmp/horsgit/tests"; cp "$racine/tools/dbtest.sh" "$tmp/horsgit/tools/"; cp "$racine/docker-compose.yml" "$tmp/horsgit/"
cp "$racine/tools/e2e_steps.sh" "$tmp/horsgit/tools/"   # R-20261101-113 (donnée d'entrée, aucune assertion changée)
for s in $SUITES_14; do mkdir -p "$tmp/horsgit/tests/$s"; done
printf '#!/bin/bash\nSUITES_NPM=(mothra:mothra)\n' > "$tmp/horsgit/tests/run_all.sh"
remise; python3 -I -B -c 'import os, signal, sys; signal.signal(signal.SIGINT, signal.SIG_DFL); os.execvp("/bin/bash", ["/bin/bash"] + sys.argv[1:])' "$tmp/horsgit/tools/dbtest.sh" > "$tmp/s" 2>&1; code=$?
[ $code -eq 0 ] && [ ! -e "$REC" ] && grep -qxF "Empreinte dbtest non écrite (hors dépôt Git)" "$tmp/s"; rc=$?
verifie "dbtest empreinte : hors dépôt Git, aucune ligne, raison « hors dépôt Git » (code 0)" $rc
depot_neuf; remise; DBTEST_RECORD="$tmp/dossier-absent/empreintes" lance_dep
[ $code -eq 0 ] && grep -qxF "Empreinte dbtest non écrite (écriture impossible)" "$tmp/s" && [ ! -e "$tmp/dossier-absent" ]; rc=$?
verifie "dbtest empreinte : écriture impossible, raison « écriture impossible » (code 0), rien n'est créé" $rc
unset DBTEST_RECORD

# --- gel pendant une fin de branche (finish-under-lock, D5, tâche 5.1) : code 3, aucun conteneur, aucune empreinte touchée ; verrou périmé ignoré
pose_verrou() { # pid jeton : verrou factice dans le dossier Git commun du dépôt temporaire
  rm -rf "$depot/.git/pmzilla-fin-en-cours"; mkdir "$depot/.git/pmzilla-fin-en-cours"
  printf '%s\n' "$1" > "$depot/.git/pmzilla-fin-en-cours/pid"; date +%s > "$depot/.git/pmzilla-fin-en-cours/debut"
  printf 'feat/autre\n' > "$depot/.git/pmzilla-fin-en-cours/branche"; printf '%s\n' "$2" > "$depot/.git/pmzilla-fin-en-cours/jeton"
}
depot_neuf; pose_verrou $$ jeton-d-un-autre; remise; DBTEST_RECORD="$REC" lance_dep
verifie "dbtest gel : verrou vivant d'un autre jeton, code 3 avec la phrase, aucun appel à Docker, aucune empreinte" "$([ $code -eq 3 ] && grep -qxF 'dbtest : fin de branche en cours (feat/autre), lancement refusé' "$tmp/s" && [ ! -s "$FAUX_LOG" ] && [ ! -e "$REC" ]; echo $?)"
verifie "dbtest gel : le verrou n'est ni retiré ni changé" "$([ "$(cat "$depot/.git/pmzilla-fin-en-cours/jeton")" = jeton-d-un-autre ]; echo $?)"
remise; DBTEST_RECORD="$REC" FINISH_LOCK_TOKEN=un-autre-encore lance_dep
verifie "dbtest gel : jeton de l'appelant différent, code 3" "$([ $code -eq 3 ] && [ ! -s "$FAUX_LOG" ]; echo $?)"
remise; DBTEST_RECORD="$REC" FINISH_LOCK_TOKEN=jeton-d-un-autre lance_dep
verifie "dbtest gel : jeton égal, le passage va jusqu'au bout (code 0), sans phrase de gel" "$([ $code -eq 0 ] && ! grep -q 'fin de branche en cours' "$tmp/s" && [ "$(n_appels 'docker run')" -eq 1 ]; echo $?)"
mort=$(sh -c 'echo $$'); pose_verrou "$mort" jeton-perime; remise; DBTEST_RECORD="$REC" lance_dep
verifie "dbtest gel : verrou périmé, ligne « verrou de fin périmé, ignoré », le passage va jusqu'au bout et le verrou reste" "$([ $code -eq 0 ] && grep -qxF 'dbtest : verrou de fin périmé, ignoré' "$tmp/s" && [ -d "$depot/.git/pmzilla-fin-en-cours" ]; echo $?)"
verifie "dbtest gel : la suite lance le script par /bin/bash (lance et lance_dep), jamais par le bash du PATH (relecture du 2026-10-20)" "$([ "$(grep -c 'os.execvp("/bin/bash"' "$0")" -ge 2 ] && ! grep -Eq '(^|[;&|(] *)bash "\$(racine|depot)/tools/dbtest.sh"' "$0"; echo $?)"

# --- mode --e2e (mothra-slices, tâche 8.3, D12) : faux Docker, faux migrations, faux chargeur, fausse construction, faux serveur, fausse passe.
# Chaque étape est remplacée par un programme de ce test (DBTEST_E2E_*) ; aucun npm, aucun navigateur, aucun serveur réel.
cat > "$tmp/e2e_migrer.sh" <<'SCRIPT'
#!/bin/bash
echo migrer >> "$FX/ordre"
exit "${FAUX_MIGRER_CODE:-0}"
SCRIPT
cat > "$tmp/e2e_chargeur.sh" <<'SCRIPT'
#!/bin/bash
echo "chargeur port=${DBTEST_PORT:-absente}" >> "$FX/ordre"
exit 0
SCRIPT
cat > "$tmp/e2e_build.sh" <<'SCRIPT'
#!/bin/bash
echo build >> "$FX/ordre"
echo "hote=${MOTHRA_HOST-absent} hote_base=${MOTHRA_DB_HOST-absent} seuil=${MOTHRA_THRESHOLD-absent} mothra=$(compgen -v MOTHRA_ | sort | tr '\n' ',') base=$(compgen -v PMZILLA_LAB_DB_ | sort | tr '\n' ',')" > "$FX/build-env"
exit "${FAUX_BUILD_CODE:-0}"
SCRIPT
cat > "$tmp/e2e_serveur.sh" <<'SCRIPT'
#!/bin/bash
echo serveur >> "$FX/ordre"
echo "pid=$$ jeu=${MOTHRA_DATASET-absent} liste_sensibles=${MOTHRA_SENSITIVE_NAMES_FILE-absent} liste_equipes=${MOTHRA_TEAM_NAMES_FILE-absent} fichier_stockage=${PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_FILE-absent} stockage_longueur=${#PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA} port=${MOTHRA_PORT:-} base=${DBTEST_PORT:-} vues_longueur=${#PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS} superutilisateur=${PMZILLA_LAB_DB_PASSWORD-absent} nom=${MOTHRA_DB_NAME:-} hote=${MOTHRA_HOST-absent} hote_base=${MOTHRA_DB_HOST-absent} seuil=${MOTHRA_THRESHOLD-absent} mothra=$(compgen -v MOTHRA_ | sort | tr '\n' ',')" > "$FX/serveur-env"
echo "VUES=${PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS:-}" > "$FX/serveur-secret"
echo "STOCKAGE=${PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA:-}" > "$FX/serveur-secret-stockage"
[ "${FAUX_SERVEUR_SORT:-0}" = "1" ] && exit 0
exec sleep 120
SCRIPT
cat > "$tmp/e2e_sonde.sh" <<'SCRIPT'
#!/bin/bash
echo "sonde $1" >> "$FX/ordre"
[ "${FAUX_SONDE_KO:-0}" = "1" ] && exit 1
# un autre programme écoute déjà sur ce port : la sonde répond tout de suite, avant le lancement du serveur
[ "${FAUX_SONDE_OCCUPE:-0}" = "1" ] && exit 0
# premier appel du passage : le contrôle du port libre de dbtest.sh, avant tout lancement du serveur ; rien n'écoute, réponse immédiate (attendre
# ici l'environnement du serveur, qui ne peut pas venir, coûtait la borne de 120 s à chaque passe --e2e et faisait dépasser le délai de la suite)
[ "$(grep -c '^sonde ' "$FX/ordre")" -gt 1 ] || exit 1
# le faux serveur écoute quand il a écrit son environnement (il démarre en arrière-plan)
i=0
while [ "$i" -lt 2400 ]; do
  if [ -s "$FX/serveur-env" ]; then
    # serveur qui sort aussitôt : la sonde réussit quand même, une fois sa sortie constatée (processus disparu, pas un délai fixe)
    if [ "${FAUX_SERVEUR_SORT:-0}" = "1" ]; then
      p=$(sed 's/^pid=\([0-9]*\) .*/\1/' "$FX/serveur-env"); j=0
      while kill -0 "$p" 2>/dev/null; do
        [ "$j" -lt 2400 ] || { echo "fausse sonde : borne de sécurité de 120 secondes atteinte, le faux serveur n'est jamais sorti" > "$FX/sonde-borne"; exit 97; }
        j=$((j+1)); sleep 0.05
      done
    fi
    exit 0
  fi
  i=$((i+1)); sleep 0.05
done
echo "fausse sonde : borne de sécurité de 120 secondes atteinte, le faux serveur n'a jamais écrit son environnement" > "$FX/sonde-borne"
exit 1
SCRIPT
cat > "$tmp/e2e_passe.sh" <<'SCRIPT'
#!/bin/bash
echo passe >> "$FX/ordre"
echo "port=${DBTEST_PORT:-absente} url=${MOTHRA_E2E_URL:-absente} superutilisateur=${PMZILLA_LAB_DB_PASSWORD-absent}" > "$FX/passe-env"
# passe qui voit mourir le serveur pendant qu'elle tourne, puis réussit quand même
if [ "${FAUX_PASSE_TUE_SERVEUR:-0}" = "1" ]; then
  p=$(sed 's/^pid=\([0-9]*\) .*/\1/' "$FX/serveur-env"); kill "$p"
  # la passe attend la disparition du serveur (processus disparu), pas un délai fixe
  j=0; while kill -0 "$p" 2>/dev/null; do
    [ "$j" -lt 2400 ] || { echo "fausse passe : borne de sécurité de 120 secondes atteinte, le serveur n'a jamais disparu" > "$FX/passe-borne"; exit 97; }
    j=$((j+1)); sleep 0.05
  done
fi
exit "${FAUX_PASSE_CODE:-0}"
SCRIPT
chmod +x "$tmp"/e2e_*.sh
unset FAUX_MIGRER_CODE FAUX_BUILD_CODE FAUX_SONDE_KO FAUX_PASSE_CODE FAUX_SONDE_OCCUPE FAUX_SERVEUR_SORT FAUX_PASSE_TUE_SERVEUR
export DBTEST_E2E_MIGRER="$tmp/e2e_migrer.sh" DBTEST_E2E_CHARGEUR="$tmp/e2e_chargeur.sh" DBTEST_E2E_BUILD="$tmp/e2e_build.sh" \
       DBTEST_E2E_SERVEUR="$tmp/e2e_serveur.sh" DBTEST_E2E_SONDE_SERVEUR="$tmp/e2e_sonde.sh" DBTEST_E2E_PASSE="$tmp/e2e_passe.sh"
export DBTEST_RECORD="$REC"
remise_e2e() { remise; rm -f "$FX/ordre" "$FX/serveur-env" "$FX/serveur-secret" "$FX/serveur-secret-stockage" "$FX/passe-env" "$FX/build-env"; }
ordre() { tr '\n' ' ' < "$FX/ordre" 2>/dev/null | sed 's/sonde [0-9]* //g'; }

remise_e2e; lance --help
verifie "dbtest e2e : l'aide décrit --e2e, la construction du bundle et liste le code 4 (échec de la construction), Docker non appelé" "$([ $code -eq 0 ] && grep -q -- '--e2e' "$tmp/s" && grep -Eq '^Code de sortie :.*' "$tmp/s" && grep -q '4 (--e2e seulement) la construction du bundle échoue' "$tmp/s" && grep -q 'construction du bundle en échec (code <n>)' "$tmp/s" && [ ! -s "$FAUX_LOG" ]; echo $?)"
depot_neuf; remise_e2e; lance_dep --e2e flow_store
verifie "dbtest e2e : --e2e avec un nom de suite refusé (code 2), Docker non appelé, rien écrit" "$([ $code -eq 2 ] && [ ! -s "$FAUX_LOG" ] && [ ! -e "$REC" ]; echo $?)"

# passe verte, arbre propre : l'ordre des étapes, l'empreinte, les variables reçues
depot_neuf; remise_e2e; lance_dep --e2e
verifie "dbtest e2e : passe verte, code 0, aucune suite lancée" "$([ $code -eq 0 ] && [ ! -e "$FX/suites" ] && ! grep -q 'Suites vertes' "$tmp/s"; echo $?)"
verifie "dbtest e2e : ordre des étapes : migrations, jeu synthétique, construction du bundle, serveur, passe (la construction avant le serveur et la passe)" "$([ "$(ordre)" = "migrer chargeur port=55432 build serveur passe " ]; echo $?)"
verifie "dbtest e2e : la construction est lancée sur l'arbre avant le serveur (le journal de la construction précède celui du serveur)" "$([ "$(grep -n '^build$' "$FX/ordre" | cut -d: -f1)" -lt "$(grep -n '^serveur$' "$FX/ordre" | cut -d: -f1)" ]; echo $?)"
verifie "dbtest e2e : le rôle des vues reçoit son mot de passe par l'entrée standard de docker exec (jamais par un argument)" "$(grep -q '^docker exec -i pmzilla-lab-test-db psql' "$FAUX_LOG" && ! grep -q -- "$(sed 's/^VUES=//' "$FX/serveur-secret")" "$FAUX_LOG"; echo $?)"
verifie "dbtest e2e : la sonde reçoit le port du serveur, qui reçoit le port de la base jetable, le nom de la base et deux secrets, vues et stockage (32 caractères pour chacun), jamais celui du superutilisateur" "$(grep -q 'port=3210 base=55432 vues_longueur=32 superutilisateur=absent nom=pmzilla' "$FX/serveur-env" && grep -q ' stockage_longueur=32 ' "$FX/serveur-env" && grep -q '^sonde 3210' "$FX/ordre"; echo $?)"
verifie "dbtest e2e : la passe reçoit DBTEST_PORT et l'adresse du serveur Mothra, sans mot de passe de superutilisateur" "$(grep -qx 'port=55432 url=http://127.0.0.1:3210 superutilisateur=absent' "$FX/passe-env"; echo $?)"
verifie "dbtest e2e : le serveur est arrêté à la fin, le conteneur supprimé" "$(! kill -0 "$(sed 's/^pid=\([0-9]*\) .*/\1/' "$FX/serveur-env")" 2>/dev/null && grep -q 'docker rm -f -v' "$FAUX_LOG" && [ ! -s "$FX/conteneurs" ]; echo $?)"
verifie "dbtest e2e : l'arbre de HEAD est inscrit (une ligne) et la ligne « Empreinte e2e enregistrée » est affichée" "$([ "$(cat "$REC" 2>/dev/null)" = "$arbre" ] && grep -qxF "Empreinte e2e enregistrée : la fin de branche l'acceptera pour cet arbre." "$tmp/s" && ! grep -q 'Empreinte dbtest' "$tmp/s"; echo $?)"
[ "$(stat -f %Lp "$REC" 2>/dev/null || stat -c %a "$REC" 2>/dev/null)" = "600" ]; rc=$?
verifie "dbtest e2e : le fichier de l'empreinte est lisible par son propriétaire seul" $rc
remise_e2e; lance_dep --e2e --port 55433
verifie "dbtest e2e : --port permis, la passe reçoit le port choisi" "$([ $code -eq 0 ] && grep -qx 'port=55433 url=http://127.0.0.1:3210 superutilisateur=absent' "$FX/passe-env" && [ "$(cat "$REC")" = "$arbre" ]; echo $?)"
remise_e2e; DBTEST_E2E_PORT_SERVEUR=3333 lance_dep --e2e
verifie "dbtest e2e : le port du serveur est paramétrable (DBTEST_E2E_PORT_SERVEUR)" "$(grep -qx 'port=55432 url=http://127.0.0.1:3333 superutilisateur=absent' "$FX/passe-env"; echo $?)"
remise_e2e; DBTEST_E2E_PORT_SERVEUR=55432 lance_dep --e2e
verifie "dbtest e2e : un port de serveur égal à celui de la base est refusé (code 2), rien démarré" "$([ $code -eq 2 ] && [ ! -s "$FAUX_LOG" ]; echo $?)"

# port du serveur déjà occupé : refus avant tout conteneur
depot_neuf; remise_e2e; FAUX_SONDE_OCCUPE=1 lance_dep --e2e
verifie "dbtest e2e : le port du serveur répond déjà avant le lancement : refus (code 2, « le port 3210 répond déjà »), Docker non appelé, aucune étape, aucune empreinte" "$([ $code -eq 2 ] && grep -q '^Refus : le port 3210 répond déjà' "$tmp/s" && [ ! -s "$FAUX_LOG" ] && [ ! -e "$FX/serveur-env" ] && ! grep -q '^migrer' "$FX/ordre" 2>/dev/null && [ ! -e "$REC" ]; echo $?)"
verifie "dbtest e2e : le refus du port occupé est documenté dans l'aide (code 2)" "$(lance --help; grep -q "le port du serveur déjà occupé" "$tmp/s" && grep -q 'Refus : le port <n> répond déjà' "$tmp/s"; echo $?)"
# D1 : pendant une fin de branche (FINISH_LOCK_TOKEN non vide), les scripts de fin retirent DBTEST_E2E_PORT_SERVEUR : le refus dit de libérer le port, pas de le changer
depot_neuf; remise_e2e; FAUX_SONDE_OCCUPE=1 FINISH_LOCK_TOKEN=jeton-de-test lance_dep --e2e
verifie "dbtest e2e : port occupé pendant une fin (FINISH_LOCK_TOKEN posée) : code 2, « pendant une fin de branche, le port ne se change pas ; libère le port 3210 », sans conseil de changer de port, Docker non appelé, rien démarré" "$([ $code -eq 2 ] && grep -qF 'pendant une fin de branche, le port ne se change pas ; libère le port 3210' "$tmp/s" && ! grep -q 'DBTEST_E2E_PORT_SERVEUR' "$tmp/s" && [ ! -s "$FAUX_LOG" ] && [ ! -e "$FX/serveur-env" ] && ! grep -q '^migrer' "$FX/ordre" 2>/dev/null && [ ! -e "$REC" ]; echo $?)"

# serveur sorti aussitôt pendant que la sonde réussit : pas de passe, pas de preuve
depot_neuf; remise_e2e; FAUX_SERVEUR_SORT=1 lance_dep --e2e
verifie "dbtest e2e : le serveur sort aussitôt alors que la sonde réussit : code 1, passe non lancée, aucune empreinte, conteneur supprimé" "$([ $code -eq 1 ] && ! grep -q '^passe$' "$FX/ordre" && [ ! -e "$FX/passe-env" ] && [ ! -e "$REC" ] && ! grep -q 'Empreinte' "$tmp/s" && grep -q "s'est arrêté alors que le port répond" "$tmp/s" && grep -q 'docker rm -f -v' "$FAUX_LOG"; echo $?)"

# serveur mort pendant la passe : une passe verte ne prouve rien
depot_neuf; remise_e2e; FAUX_PASSE_TUE_SERVEUR=1 lance_dep --e2e
verifie "dbtest e2e : le serveur meurt pendant la passe, qui réussit quand même : code 1, « Passe de bout en bout en échec », aucune empreinte" "$([ $code -eq 1 ] && grep -q "s'est arrêté pendant la passe" "$tmp/s" && grep -qx 'Passe de bout en bout en échec' "$tmp/s" && ! grep -q 'Empreinte' "$tmp/s" && [ ! -e "$REC" ]; echo $?)"

# variables MOTHRA_* et mot de passe de l'appelant : le serveur et la construction ne reçoivent que ce que le script pose
valeur_auteur=secret-de-l-auteur; fichier_auteur=/etc/chemin-de-l-auteur   # valeurs factices, passées par référence de shell
depot_neuf; remise_e2e; MOTHRA_HOST=0.0.0.0 MOTHRA_DB_HOST=base.exemple MOTHRA_THRESHOLD=99 MOTHRA_AUTRE=x MOTHRA_E2E_URL=http://127.0.0.1:9 MOTHRA_DATASET=real \
  PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS="$valeur_auteur" PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS_FILE="$fichier_auteur" lance_dep --e2e
verifie "dbtest e2e : le serveur ne reçoit aucune variable MOTHRA_* exportée par l'appelant (hôte, hôte de base, seuil, autre) : seulement MOTHRA_DATASET, MOTHRA_PORT, MOTHRA_DB_NAME et les deux listes de noms factices (tâche 18.3)" "$([ $code -eq 0 ] && grep -q ' hote=absent hote_base=absent seuil=absent mothra=MOTHRA_DATASET,MOTHRA_DB_NAME,MOTHRA_PORT,MOTHRA_SENSITIVE_NAMES_FILE,MOTHRA_TEAM_NAMES_FILE,$' "$FX/serveur-env"; echo $?)"
verifie "dbtest e2e : le serveur reçoit MOTHRA_SENSITIVE_NAMES_FILE et MOTHRA_TEAM_NAMES_FILE, qui pointent vers les listes factices de mothra/server/test/listes/ du dépôt du script (jamais celles de l'appelant)" "$(grep -q "liste_sensibles=$depot/mothra/server/test/listes/noms-sensibles.txt liste_equipes=$depot/mothra/server/test/listes/equipes-lisibles.yaml " "$FX/serveur-env"; echo $?)"
verifie "dbtest e2e : un appelant qui pose MOTHRA_DATASET=real : le serveur reçoit synthetic" "$(grep -q '^pid=[0-9]* jeu=synthetic ' "$FX/serveur-env"; echo $?)"
verifie "dbtest e2e : la construction du bundle tourne sous le même environnement nettoyé (aucune variable MOTHRA_* ni PMZILLA_LAB_DB_*)" "$(grep -qx 'hote=absent hote_base=absent seuil=absent mothra= base=' "$FX/build-env"; echo $?)"
verifie "dbtest e2e : le serveur reçoit ses deux secrets, vues et stockage (celui des vues : 32 caractères, aléatoire), pas celui de l'appelant ni son fichier ; la passe reçoit l'adresse du script, pas celle de l'appelant" "$(grep -q 'vues_longueur=32 ' "$FX/serveur-env" && ! grep -q 'secret-de-l-auteur' "$FX/serveur-secret" && grep -qx 'port=55432 url=http://127.0.0.1:3210 superutilisateur=absent' "$FX/passe-env"; echo $?)"
verifie "dbtest e2e : le mot de passe du rôle des vues n'est jamais un argument de env (préfixe d'affectation devant exec, lecture du script)" "$(! grep -Eq '^[^#]*env [^|]*PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS=' "$racine/tools/dbtest.sh"; echo $?)"

# secret du rôle de stockage (g16, R-20261029-02) : même traitement que celui des vues, aucun des deux dans une sortie de la passe
depot_neuf; remise_e2e; PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA="$valeur_auteur" PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_FILE="$fichier_auteur" lance_dep --e2e
s_vues="$(sed 's/^VUES=//' "$FX/serveur-secret")"; s_stockage="$(sed 's/^STOCKAGE=//' "$FX/serveur-secret-stockage")"
verifie "dbtest e2e : le serveur reçoit un secret de stockage aléatoire de 32 caractères hexadécimaux, distinct de celui des vues, pas celui de l'appelant ni son fichier" "$([ $code -eq 0 ] && printf '%s' "$s_stockage" | grep -Eq '^[0-9a-f]{32}$' && [ "$s_stockage" != "$s_vues" ]; echo $?)"
verifie "dbtest e2e : le serveur ne reçoit pas le fichier de secret de stockage de l'appelant (variable absente)" "$(grep -q ' fichier_stockage=absent ' "$FX/serveur-env"; echo $?)"
verifie "dbtest e2e : le rôle de stockage reçoit son secret par l'entrée standard de docker exec (jamais par un argument)" "$(grep -c '^docker exec -i pmzilla-lab-test-db psql' "$FAUX_LOG" | grep -qx 2 && ! grep -q -- "$s_stockage" "$FAUX_LOG"; echo $?)"
# Revue Opus : la base est en scram, le psql du docker exec doit s'authentifier. Le mot de passe est dans l'environnement du conteneur (PGPASSWORD, posé au docker run
# par -e sans valeur), que le docker exec hérite : jamais en argument, et le psql de l'exec garde sa ligne de commande sans option -e.
verifie "dbtest e2e : PGPASSWORD est donné à la base par l'environnement du docker run (-e PGPASSWORD sans valeur), égal au mot de passe de la base, et la valeur n'est dans aucun argument de docker" "$(pw=$(cat "$FX/pw-recu"); [ -n "$pw" ] && [ "$(cat "$FX/pgpw-recu")" = "$pw" ] && grep '^docker run' "$FAUX_LOG" | grep -qF -- '-e PGPASSWORD ' && ! grep -qF -- "$pw" "$FAUX_LOG"; echo $?)"
verifie "dbtest e2e : les deux psql de docker exec (rôles des vues et de stockage) sont lancés sans mot de passe ni -e en argument" "$([ "$(grep -c '^docker exec -i [^ ]* psql ' "$FAUX_LOG")" -eq 2 ] && ! grep '^docker exec' "$FAUX_LOG" | grep -q -e 'PGPASSWORD' -e ' -e '; echo $?)"
verifie "dbtest e2e : ni le secret des vues ni celui du stockage n'apparaissent dans la sortie standard, la sortie d'erreur, le journal de docker, l'empreinte ou les fichiers de la passe (hors le fichier où le faux serveur note ce qu'il a reçu)" "$(ok=0; for f in "$tmp/s" "$FAUX_LOG" "$REC" "$FX/ordre" "$FX/serveur-env" "$FX/passe-env" "$FX/build-env" "$FX/conteneurs"; do [ -e "$f" ] || ok=1; done; [ "$ok" -eq 0 ] && [ -n "$s_vues" ] && [ -n "$s_stockage" ] && ! grep -q -e "$s_vues" -e "$s_stockage" "$tmp/s" "$FAUX_LOG" "$REC" "$FX/ordre" "$FX/serveur-env" "$FX/passe-env" "$FX/build-env" "$FX/conteneurs"; echo $?)"

# appelant en xtrace (bash -x sur le script) : aucun des deux secrets dans les sorties
depot_neuf; remise_e2e
python3 -I -B -c 'import os, signal, sys; signal.signal(signal.SIGINT, signal.SIG_DFL); os.execvp("/bin/bash", ["/bin/bash", "-x"] + sys.argv[1:])' "$depot/tools/dbtest.sh" --e2e > "$tmp/s" 2>&1; code=$?
s_vues="$(sed 's/^VUES=//' "$FX/serveur-secret")"; s_stockage="$(sed 's/^STOCKAGE=//' "$FX/serveur-secret-stockage")"
verifie "dbtest e2e : appelant en xtrace (bash -x) : passe verte et aucun des deux secrets dans les sorties, le journal de docker ou les fichiers de la passe" "$([ $code -eq 0 ] && [ -n "$s_vues" ] && [ -n "$s_stockage" ] && [ -s "$tmp/s" ] && ! grep -q -e "$s_vues" -e "$s_stockage" "$tmp/s" "$FAUX_LOG" "$REC" "$FX/ordre" "$FX/serveur-env" "$FX/passe-env" "$FX/build-env"; echo $?)"
verifie "dbtest e2e : le secret du rôle de stockage n'est jamais un argument de env (préfixe d'affectation devant exec, lecture du script)" "$(! grep -Eq '^[^#]*env [^|]*PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA=' "$racine/tools/dbtest.sh"; echo $?)"

# construction en échec : code 4, ni serveur, ni passe, aucune empreinte, conteneur supprimé
depot_neuf; remise_e2e; FAUX_BUILD_CODE=7 lance_dep --e2e
verifie "dbtest e2e : construction en échec : code 4 et « construction du bundle en échec (code 7) » avec le code de la commande" "$([ $code -eq 4 ] && grep -qxF 'construction du bundle en échec (code 7)' "$tmp/s"; echo $?)"
verifie "dbtest e2e : construction en échec : ni serveur ni passe (l'ordre s'arrête à la construction), aucune empreinte, conteneur supprimé" "$([ "$(ordre)" = "migrer chargeur port=55432 build " ] && [ ! -e "$FX/serveur-env" ] && [ ! -e "$FX/passe-env" ] && [ ! -e "$REC" ] && ! grep -q 'Empreinte' "$tmp/s" && grep -q 'docker rm -f -v' "$FAUX_LOG"; echo $?)"
depot_neuf; printf '%s\n' "$arbre" > "$REC"; remise_e2e; FAUX_BUILD_CODE=1 lance_dep --e2e
verifie "dbtest e2e : construction en échec : la ligne de l'arbre courant, retirée au départ, ne revient pas" "$([ $code -eq 4 ] && ! grep -qx "$arbre" "$REC"; echo $?)"

# autres échecs : code 1
depot_neuf; remise_e2e; FAUX_MIGRER_CODE=3 lance_dep --e2e
verifie "dbtest e2e : migrations en échec : code 1, ni chargeur, ni construction, ni serveur, ni passe, conteneur supprimé" "$([ $code -eq 1 ] && grep -q 'migrations en échec (code 3)' "$tmp/s" && [ "$(ordre)" = "migrer " ] && [ ! -e "$REC" ] && grep -q 'docker rm -f -v' "$FAUX_LOG"; echo $?)"
depot_neuf; remise_e2e; FAUX_SONDE_KO=1 lance_dep --e2e
verifie "dbtest e2e : le serveur n'écoute jamais : code 1, la passe n'est pas lancée, le serveur est arrêté, aucune empreinte" "$([ $code -eq 1 ] && ! grep -q '^passe$' "$FX/ordre" && [ ! -e "$REC" ] && ! kill -0 "$(sed 's/^pid=\([0-9]*\) .*/\1/' "$FX/serveur-env")" 2>/dev/null; echo $?)"
depot_neuf; printf '%s\n%s\n' "$arbre" "autre-arbre-4444" > "$REC"; remise_e2e; FAUX_PASSE_CODE=1 lance_dep --e2e
verifie "dbtest e2e : passe rouge : code 1, rien d'affiché sur l'empreinte, la ligne de l'arbre courant est retirée, celle d'un autre arbre reste, serveur arrêté" "$([ $code -eq 1 ] && ! grep -q 'Empreinte' "$tmp/s" && ! grep -qx "$arbre" "$REC" && grep -qx 'autre-arbre-4444' "$REC" && ! kill -0 "$(sed 's/^pid=\([0-9]*\) .*/\1/' "$FX/serveur-env")" 2>/dev/null; echo $?)"

# empreinte : les mêmes raisons que le mode par défaut
depot_neuf; echo x > "$depot/nouveau.txt"; remise_e2e; lance_dep --e2e
verifie "dbtest e2e : fichier non suivi au départ : aucune ligne, raison « arbre non propre » (code 0)" "$([ $code -eq 0 ] && [ ! -e "$REC" ] && grep -qxF 'Empreinte e2e non écrite (arbre non propre)' "$tmp/s"; echo $?)"
depot_neuf; remise_e2e; DBTEST_SONDE=/usr/bin/false lance_dep --e2e
verifie "dbtest e2e : base injoignable depuis l'hôte : aucune ligne, raison « base injoignable depuis l'hôte »" "$([ $code -eq 0 ] && [ ! -e "$REC" ] && grep -qxF "Empreinte e2e non écrite (base injoignable depuis l'hôte)" "$tmp/s"; echo $?)"
depot_neuf; remise_e2e; DBTEST_E2E_PASSE="$tmp/run_all_commit.sh" lance_dep --e2e
verifie "dbtest e2e : l'arbre de HEAD change pendant la passe : aucune ligne, raison « arbre changé pendant le passage »" "$([ $code -eq 0 ] && [ ! -e "$REC" ] && grep -qxF 'Empreinte e2e non écrite (arbre changé pendant le passage)' "$tmp/s"; echo $?)"
depot_neuf; remise_e2e; DBTEST_RECORD="$tmp/dossier-absent/empreintes" lance_dep --e2e
verifie "dbtest e2e : écriture impossible : raison « écriture impossible » (code 0), rien n'est créé" "$([ $code -eq 0 ] && grep -qxF 'Empreinte e2e non écrite (écriture impossible)' "$tmp/s" && [ ! -e "$tmp/dossier-absent" ]; echo $?)"
depot_neuf; remise_e2e; env -u DBTEST_RECORD python3 -I -B -c 'import os, signal, sys; signal.signal(signal.SIGINT, signal.SIG_DFL); os.execvp("/bin/bash", ["/bin/bash"] + sys.argv[1:])' "$depot/tools/dbtest.sh" --e2e > "$tmp/s" 2>&1; code=$?
verifie "dbtest e2e : étapes remplacées sans DBTEST_RECORD : rien dans le dossier Git, aucune ligne" "$([ $code -eq 0 ] && [ ! -e "$depot/.git/pmzilla-e2e-ok" ] && ! grep -q 'Empreinte' "$tmp/s"; echo $?)"
verifie "dbtest e2e : le fichier de preuve par défaut est pmzilla-e2e-ok, pas celui de dbtest (script lu)" "$(grep -q 'NOM_EMPREINTE="pmzilla-e2e-ok"' "$racine/tools/dbtest.sh" && grep -q 'NOM_EMPREINTE="pmzilla-dbtest-ok"' "$racine/tools/dbtest.sh"; echo $?)"

# gel pendant une fin de branche : code 3, rien démarré
depot_neuf; pose_verrou $$ jeton-d-un-autre; remise_e2e; lance_dep --e2e
verifie "dbtest e2e gel : verrou vivant d'un autre jeton : code 3 avec la phrase, aucun appel à Docker, aucune étape, aucune empreinte" "$([ $code -eq 3 ] && grep -qxF 'dbtest : fin de branche en cours (feat/autre), lancement refusé' "$tmp/s" && [ ! -s "$FAUX_LOG" ] && [ ! -e "$FX/ordre" ] && [ ! -e "$REC" ]; echo $?)"
remise_e2e; FINISH_LOCK_TOKEN=jeton-d-un-autre lance_dep --e2e
verifie "dbtest e2e gel : jeton égal, la passe va jusqu'au bout (code 0)" "$([ $code -eq 0 ] && [ "$(ordre)" = "migrer chargeur port=55432 build serveur passe " ]; echo $?)"
rm -rf "$depot/.git/pmzilla-fin-en-cours"
unset DBTEST_E2E_MIGRER DBTEST_E2E_CHARGEUR DBTEST_E2E_BUILD DBTEST_E2E_SERVEUR DBTEST_E2E_SONDE_SERVEUR DBTEST_E2E_PASSE DBTEST_RECORD

# --- tests/run_e2e.sh (tâche 8.2) : copie dans une racine temporaire, faux lanceur Playwright ; aucun navigateur, aucun npm
racine_e2e="$tmp/racine-e2e"; mkdir -p "$racine_e2e/tests"; cp "$racine/tests/run_e2e.sh" "$racine_e2e/tests/"
cat > "$tmp/faux_playwright.sh" <<'SCRIPT'
#!/bin/bash
echo "lance url=${MOTHRA_E2E_URL:-absente} port=${DBTEST_PORT:-absente} variables=$(compgen -v PMZILLA_LAB_DB_ | sort | tr '\n' ',')" >> "$FX/playwright"
exit "${FAUX_E2E_CODE:-0}"
SCRIPT
chmod +x "$tmp/faux_playwright.sh"
lance_e2e() { rm -f "$FX/playwright"; env -u DBTEST_PORT -u MOTHRA_E2E_URL -u PMZILLA_LAB_DB_PORT "$@" /bin/bash "$racine_e2e/tests/run_e2e.sh" > "$tmp/s" 2>&1; code=$?; }
faux_superutilisateur=secret-du-superutilisateur   # valeur factice, passée par référence de shell
PHRASE_E2E="run_e2e : base jetable absente (lancer bash tools/dbtest.sh --e2e)"
lance_e2e RUN_E2E_LANCEUR="$tmp/faux_playwright.sh" MOTHRA_E2E_URL=http://127.0.0.1:3210
verifie "run_e2e : sans DBTEST_PORT, code 2 et la phrase exacte, aucun lanceur de navigateur" "$([ $code -eq 2 ] && [ "$(cat "$tmp/s")" = "$PHRASE_E2E" ] && [ ! -e "$FX/playwright" ]; echo $?)"
for port in 5432 abc 05432 0 70000 ""; do
  lance_e2e RUN_E2E_LANCEUR="$tmp/faux_playwright.sh" MOTHRA_E2E_URL=http://127.0.0.1:3210 DBTEST_PORT="$port"
  verifie "run_e2e : DBTEST_PORT $(printf '%q' "$port") refusé (code 2, même phrase), aucun lanceur" "$([ $code -eq 2 ] && [ "$(cat "$tmp/s")" = "$PHRASE_E2E" ] && [ ! -e "$FX/playwright" ]; echo $?)"
done
lance_e2e RUN_E2E_LANCEUR="$tmp/faux_playwright.sh" MOTHRA_E2E_URL=http://127.0.0.1:3210 DBTEST_PORT=55499 PMZILLA_LAB_DB_PORT=55499
verifie "run_e2e : DBTEST_PORT égal au port de la vraie base refusé (code 2), aucun lanceur" "$([ $code -eq 2 ] && [ "$(cat "$tmp/s")" = "$PHRASE_E2E" ] && [ ! -e "$FX/playwright" ]; echo $?)"
for url in "" "http://127.0.0.1:5173" "http://127.0.0.1:4173" "http://localhost:3210" "https://127.0.0.1:3210" "http://example.org:3210" "http://127.0.0.1:3210/" "http://127.0.0.1:99999" "http://127.0.0.1"; do
  lance_e2e RUN_E2E_LANCEUR="$tmp/faux_playwright.sh" DBTEST_PORT=55432 MOTHRA_E2E_URL="$url"
  verifie "run_e2e : adresse $(printf '%q' "$url") refusée (code 2, jamais Vite, son aperçu 4173 ni une autre machine), aucun lanceur" "$([ $code -eq 2 ] && grep -q '^run_e2e : adresse du serveur Mothra absente ou refusée' "$tmp/s" && [ ! -e "$FX/playwright" ]; echo $?)"
done
lance_e2e RUN_E2E_LANCEUR="$tmp/faux_playwright.sh" DBTEST_PORT=55432 MOTHRA_E2E_URL=http://127.0.0.1:3210 PMZILLA_LAB_DB_PASSWORD="$faux_superutilisateur" PMZILLA_LAB_DB_URL=postgresql://x@127.0.0.1:5432/pmzilla
verifie "run_e2e : passe verte (code 0), le lanceur reçoit l'adresse du serveur et DBTEST_PORT, aucune variable PMZILLA_LAB_DB_*" "$([ $code -eq 0 ] && [ "$(cat "$FX/playwright")" = 'lance url=http://127.0.0.1:3210 port=55432 variables=' ]; echo $?)"
lance_e2e RUN_E2E_LANCEUR="$tmp/faux_playwright.sh" DBTEST_PORT=55432 MOTHRA_E2E_URL=http://127.0.0.1:3210 FAUX_E2E_CODE=3
verifie "run_e2e : passe rouge : code 1 (quel que soit le code du lanceur) et « passe rouge (code 3) »" "$([ $code -eq 1 ] && grep -qxF 'run_e2e : passe rouge (code 3)' "$tmp/s"; echo $?)"
lance_e2e DBTEST_PORT=55432 MOTHRA_E2E_URL=http://127.0.0.1:3210
verifie "run_e2e : sans lanceur de test ni Playwright installé : code 1 et « Playwright introuvable » (rien n'est téléchargé)" "$([ $code -eq 1 ] && grep -q 'run_e2e : Playwright introuvable' "$tmp/s"; echo $?)"
verifie "run_e2e : le script ne télécharge ni n'installe rien (aucun npm install, ci, npx, playwright install) et ne vise pas Vite (lecture du script)" "$(grep -Eq '^[^#]*(npm (install|ci|i)|npx|playwright install|vite)' "$racine/tests/run_e2e.sh"; [ $? -ne 0 ]; echo $?)"
verifie "run_e2e : la spec Playwright ouvre la page à l'adresse du serveur Mothra (MOTHRA_E2E_URL) et jamais à un autre (lecture de tests/e2e)" "$(grep -q 'MOTHRA_E2E_URL' "$racine/tests/e2e/squelette.spec.ts" && grep -q 'MOTHRA_E2E_URL' "$racine/tests/e2e/playwright.config.ts" && ! grep -Eq '5173|localhost|https?://[a-z]' "$racine/tests/e2e/squelette.spec.ts"; echo $?)"
verifie "run_e2e : la spec attend au moins une cellule masquée au libellé « masked », et des routes sans extension (lecture de tests/e2e)" "$(grep -q 'data-state="masked"' "$racine/tests/e2e/squelette.spec.ts" && grep -q 'toHaveText("masked")' "$racine/tests/e2e/squelette.spec.ts" && grep -q '/sheets/12' "$racine/tests/e2e/squelette.spec.ts"; echo $?)"

# --- tools/e2e_steps.sh (change ci-local-runner, tranche 2, tâches 9.1 et 9.2 ; R-20261101-113) : les étapes de la passe de bout en bout, sourcées par
# dbtest.sh (de son propre arbre) et, concaténées devant ci/passage.sh par tools/ci_local.sh, dans le conteneur de la CI. Les cas de --e2e plus haut
# (assertions inchangées) vérifient que dbtest se comporte comme avant ; ceux-ci vérifient la forme du fichier déplacé.
ETAPES="$racine/tools/e2e_steps.sh"
verifie "e2e_steps : le fichier existe et, sourcé sous set -u, n'écrit rien, ne lance rien et définit e2e_enchainer (fonctions seulement)" "$([ -f "$ETAPES" ] && [ -z "$(/bin/bash -c 'set -u; . "$1"; declare -F e2e_enchainer >/dev/null || echo manque' _ "$ETAPES" 2>&1)" ]; echo $?)"
verifie "e2e_steps : les étapes rendent un code et ne font jamais exit (dbtest garde ses exit et ses phrases, la CI ses lignes de phase)" "$(grep -Eq '(^|[;&{(][[:space:]]*)exit([[:space:]]|$)' "$ETAPES"; [ $? -ne 0 ]; echo $?)"
verifie "dbtest : le script source tools/e2e_steps.sh de son propre arbre (jamais d'une autre racine)" "$(grep -qF '. "$RACINE/tools/e2e_steps.sh"' "$racine/tools/dbtest.sh"; echo $?)"
verifie "dbtest : les étapes (migrations, chargeur, construction, serveur) ont quitté dbtest.sh et sont dans e2e_steps.sh" "$(! grep -Eq '^[^#]*(tools/db.py migrate|npm run build|node src/main.ts|jeu_synthetique)' "$racine/tools/dbtest.sh" && grep -q 'tools/db.py migrate' "$ETAPES" && grep -q 'npm run build' "$ETAPES" && grep -q 'node src/main.ts' "$ETAPES" && grep -q 'jeu_synthetique' "$ETAPES"; echo $?)"
# Doublent les deux contrôles statiques « jamais un argument de env » de plus haut, qui lisent dbtest.sh et n'y trouvent plus le code (R-20261101-113).
# Les noms de variables viennent de variables, jamais d'un littéral suivi de « = » (le contrôle des secrets y verrait une affectation).
nom_vues="PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS"
nom_stockage="PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA"
verifie "e2e_steps : le mot de passe du rôle des vues n'est jamais un argument de env (préfixe d'affectation devant exec, lecture du script)" "$(! grep -Eq "^[^#]*env [^|]*${nom_vues}=" "$ETAPES" && grep -q "${nom_vues}=" "$ETAPES"; echo $?)"
verifie "e2e_steps : le secret du rôle de stockage n'est jamais un argument de env (préfixe d'affectation devant exec, lecture du script)" "$(! grep -Eq "^[^#]*env [^|]*${nom_stockage}=" "$ETAPES" && grep -q "${nom_stockage}=" "$ETAPES"; echo $?)"
verifie "e2e_steps : ni Docker ni client psql (la fonction SQL est fournie par l'appelant : docker exec pour dbtest, psycopg pour le conteneur), pas de set -x, set +x présent" "$(grep -Eq '^[^#]*(docker|psql|set -[a-z]*x)' "$ETAPES"; [ $? -ne 0 ] && grep -q 'set +x' "$ETAPES"; echo $?)"
verifie "e2e_steps : aucun secret affiché (aucun echo ni printf d'une variable de secret)" "$(grep -Eq '^[^#]*(echo|printf)[^|#]*E2E_SECRET' "$ETAPES"; [ $? -ne 0 ]; echo $?)"
verifie "e2e_steps : le fichier est lisible par bash 3.2 du Mac (pas de tableau associatif, de mapfile ni de casse par \${x,,})" "$(grep -Eq '^[^#]*(declare -A|mapfile|readarray|\$\{[A-Za-z_]+(,,|\^\^)\})' "$ETAPES"; [ $? -ne 0 ]; echo $?)"
# Sans tools/e2e_steps.sh dans l'arbre du script : refus avant tout appel à Docker (la passe de bout en bout seulement ; les suites par défaut n'en ont pas besoin)
rm -rf "$tmp/racine-sans"; mkdir -p "$tmp/racine-sans/tools" "$tmp/racine-sans/tests"; cp "$racine/tools/dbtest.sh" "$tmp/racine-sans/tools/"; cp "$racine/docker-compose.yml" "$tmp/racine-sans/"
remise; /bin/bash "$tmp/racine-sans/tools/dbtest.sh" --e2e > "$tmp/s" 2>&1; code=$?
verifie "dbtest e2e : sans tools/e2e_steps.sh dans son arbre : code 2, phrase, Docker non appelé, rien démarré" "$([ $code -eq 2 ] && grep -qxF "dbtest : tools/e2e_steps.sh introuvable ; rien n'est démarré" "$tmp/s" && [ ! -s "$FAUX_LOG" ]; echo $?)"

# --- isolation sous charge (R-135) : aucun cas « lance » ne dépend du dossier Git du vrai dépôt (verrou d'une autre session)
verifie "dbtest isolation : la racine des cas « lance » est hors de tout dépôt Git, et lance() ne vise pas le script du vrai dépôt" "$(! git -C "$racine_lance" rev-parse --git-dir >/dev/null 2>&1 && grep -q 'racine_lance/tools/dbtest.sh" "\$@"' "$0" && ! grep -Eq "^lance\(\).*\"\\\$racine/tools/dbtest.sh\"" "$0"; echo $?)"

# --- hygiène du script
verifie "dbtest : pas de set -x, pas de docker compose, pas de Trousseau, pas d'export du mot de passe, pas de tube vers les suites" "$(grep -Eq '^[^#]*(set -[a-z]*x|docker compose|security find|export PMZILLA_LAB_DB_PASSWORD|run_all.*\|)' "$racine/tools/dbtest.sh"; [ $? -ne 0 ]; echo $?)"
verifie "dbtest : le mot de passe n'est jamais affiché (aucun echo ni printf de la variable)" "$(grep -Eq '(echo|printf)[^|#]*\$\{?mdp' "$racine/tools/dbtest.sh"; [ $? -ne 0 ]; echo $?)"

# --- /dev/shm du conteneur jetable : shm_size lu dans docker-compose.yml (R-22), jamais recopié ; repli 1g
verifie "dbtest : docker run reçoit --shm-size, avec la valeur de shm_size du compose réel" "$(remise; lance db; v="$(grep -E '^[[:space:]]+shm_size:' "$racine/docker-compose.yml" | head -1 | sed -E 's/^[[:space:]]+shm_size:[[:space:]]*//; s/[#].*$//; s/["[:space:]]//g')"; [ -n "$v" ] && grep '^docker run' "$FAUX_LOG" | grep -q -- "--shm-size $v "; echo $?)"
racine_shm() {   # $1 = ligne shm_size du compose factice (vide : aucune) ; lance une copie du script dans une racine temporaire
  rm -rf "$tmp/root"; mkdir -p "$tmp/root/tools" "$tmp/root/tests/db"
  cp "$racine/tools/dbtest.sh" "$tmp/root/tools/"
  { grep -v 'shm_size' "$racine/docker-compose.yml"; [ -n "$1" ] && echo "    $1"; } > "$tmp/root/docker-compose.yml"
  remise; /bin/bash "$tmp/root/tools/dbtest.sh" db > "$tmp/s" 2>&1; code=$?
}
racine_shm "shm_size: 2gb  # commentaire"
verifie "dbtest : la valeur vient du compose (2gb), commentaire retiré" "$(grep '^docker run' "$FAUX_LOG" | grep -q -- '--shm-size 2gb '; echo $?)"
racine_shm ""
verifie "dbtest : sans shm_size dans le compose, repli 1g" "$(grep '^docker run' "$FAUX_LOG" | grep -q -- '--shm-size 1g '; echo $?)"
racine_shm "shm_size: grand; rm -rf /"
verifie "dbtest : shm_size illisible, repli 1g (la valeur n'est jamais passée telle quelle)" "$(grep '^docker run' "$FAUX_LOG" | grep -q -- '--shm-size 1g ' && ! grep -q 'rm -rf' "$FAUX_LOG"; echo $?)"

# --- Q270 (R-20261101-129) : forme de l'étape qui pose les seuils d'échantillon (tools/e2e_steps.sh, partagé avec la phase e2e du conteneur)
# La fonction du rôle de stockage est sourcée avec un faux e2e_sql qui garde le SQL reçu : aucune base, aucun Docker.
sql_seuils=$( ( . "$racine/tools/e2e_steps.sh"; E2E_SECRET_STOCKAGE=secret-temoin-q270; e2e_sql() { cat; }; e2e_poser_role_de_stockage ) 2>&1 )
attendu_seuils="ALTER ROLE pmzilla_mothra LOGIN PASSWORD 'secret-temoin-q270'; SET ROLE pmzilla_mothra; INSERT INTO mothra.threshold_history (threshold_code, value, set_on, set_by) VALUES ('sample_median_min_items', 5, DATE '2026-10-27', 'author-1'), ('sample_p85_min_items', 20, DATE '2026-10-27', 'author-1'); RESET ROLE;"
# Valeur de la médiane : 5 (R-20261102-5, Q281 (a) : plancher de masquage, tailles du jeu synthétique 5, 5, 9 et 5), qui remplace 10 (Q270)
verifie "e2e_steps : le rôle de stockage reçoit son mot de passe puis, sous ce rôle (SET ROLE), une ligne datée par seuil d'échantillon (5 et 20) dans mothra.threshold_history, puis RESET ROLE" "$([ "$sql_seuils" = "$attendu_seuils" ]; echo $?)"
verifie "dbtest.sh : un seul docker exec ... psql (e2e_sql), qui hérite PGPASSWORD du conteneur" "$([ "$(grep -c '^  e2e_sql() { docker exec -i "\$NOM" psql ' "$racine/tools/dbtest.sh")" -eq 1 ]; echo $?)"
verifie "e2e_steps.sh et ci/passage.sh : aucun docker exec ni client psql lancé (le passage passe par psycopg, l'étape par e2e_sql)" "$(! grep -q '^[^#]*docker exec' "$racine/tools/e2e_steps.sh" && ! grep -q '^[^#]*psql ' "$racine/tools/e2e_steps.sh" && ! grep -q '^[^#]*docker exec' "$racine/ci/passage.sh" && ! grep -q '^[^#]*psql ' "$racine/ci/passage.sh"; echo $?)"
verifie "e2e_steps : les seuils ne passent que par e2e_sql (la base jetable de l'appelant) et ne comportent ni UPDATE ni DELETE ni connexion directe" "$(! grep -Eq '^[^#]*(UPDATE|DELETE) ' "$racine/tools/e2e_steps.sh" && [ "$(grep -c 'INSERT INTO mothra.threshold_history' "$racine/tools/e2e_steps.sh")" -eq 1 ] && ! grep -Eq '^[^#]*(psql|docker|PMZILLA_LAB_DB_URL)' "$racine/tools/e2e_steps.sh"; echo $?)"
verifie "e2e_steps : sans mot de passe de rôle, rien n'est envoyé (retour 1, aucun SQL)" "$(r=$( ( . "$racine/tools/e2e_steps.sh"; E2E_SECRET_STOCKAGE=""; e2e_sql() { cat; echo APPELE; }; e2e_poser_role_de_stockage; echo "rc=$?" ) 2>&1 ); [ "$r" = "rc=1" ]; echo $?)"

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
exit $?
