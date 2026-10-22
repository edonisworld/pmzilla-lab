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
lance() { python3 -I -B -c 'import os, signal, sys; signal.signal(signal.SIGINT, signal.SIG_DFL); os.execvp("/bin/bash", ["/bin/bash"] + sys.argv[1:])' "$racine/tools/dbtest.sh" "$@" > "$tmp/s" 2>&1; code=$?; }
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

# --- prérequis
remise; FAUX_DOCKER_ARRETE=1 lance flow_store
verifie "dbtest : Docker arrêté, refus (code 2) avec le conseil Colima" "$([ $code -eq 2 ] && grep -q 'colima' "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
remise; echo "pmzilla-lab-test-db" > "$FX/conteneurs"; lance flow_store
verifie "dbtest : conteneur déjà présent, refus (code 2), ni démarré, ni supprimé" "$([ $code -eq 2 ] && grep -q 'existe déjà' "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ] && [ "$(n_appels 'docker rm')" -eq 0 ] && [ -s "$FX/conteneurs" ]; echo $?)"

# --- passage nominal
remise; lance
verifie "dbtest : passage nominal, code 0" "$([ $code -eq 0 ]; echo $?)"
verifie "dbtest : suites par défaut, dans l'ordre" "$([ "$(sed -n 's/^suite=\([^ ]*\) .*/\1/p' "$FX/suites" | tr '\n' ' ')" = "db flow_import flow_store flow_views hybrid_search pmzilla_lab_library library_backend cases_store watch_store book_usage dashboard flow_retention posture_evals export_jira_api history_jira story_quality " ]; echo $?)"
verifie "dbtest : conteneur publié sur 127.0.0.1:55432 seulement, nom fixe, image de docker-compose.yml" "$(grep '^docker run' "$FAUX_LOG" | grep -q -- '--name pmzilla-lab-test-db' && grep '^docker run' "$FAUX_LOG" | grep -q -- '-p 127.0.0.1:55432:5432' && grep '^docker run' "$FAUX_LOG" | grep -q "$(grep -E '^[[:space:]]+image:' "$racine/docker-compose.yml" | head -1 | sed -E 's/^[[:space:]]+image:[[:space:]]*//; s/["[:space:]]//g')"; echo $?)"
verifie "dbtest : chaque suite reçoit le port jetable, un mot de passe de 32 caractères, ni URL ni PMZILLA_NO_EVALS" "$(! grep -v 'port=55432 pw_longueur=32 url=absente noevals=absente' "$FX/suites" | grep -q .; echo $?)"
verifie "dbtest : conteneur supprimé avec ses volumes à la fin" "$(grep -q 'docker rm -f -v pmzilla-lab-test-db' "$FAUX_LOG"; [ $? -eq 0 ] && [ ! -s "$FX/conteneurs" ]; echo $?)"
verifie "dbtest : résumé vert, aucune suite en échec" "$(grep -qx 'Suites vertes : db flow_import flow_store flow_views hybrid_search pmzilla_lab_library library_backend cases_store watch_store book_usage dashboard flow_retention posture_evals export_jira_api history_jira story_quality' "$tmp/s" && grep -q 'Suites en échec : aucune' "$tmp/s"; echo $?)"
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
SUITES_14="db flow_import flow_store flow_views hybrid_search pmzilla_lab_library library_backend cases_store watch_store book_usage dashboard flow_retention posture_evals export_jira_api history_jira story_quality"
depot="$tmp/depot"; REC="$tmp/empreintes"; export DEPOT="$depot"
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null   # aucun réglage ni hook de l'utilisateur dans les dépôts temporaires
GIT_T="git -c user.email=t@example.org -c user.name=test"
depot_neuf() { # dépôt Git temporaire : copie du script, du compose, un dossier par suite par défaut, un faux tests/run_all.sh
  rm -rf "$depot" "$REC"; mkdir -p "$depot/tools" "$depot/tests"
  cp "$racine/tools/dbtest.sh" "$depot/tools/"; cp "$racine/docker-compose.yml" "$depot/"
  for s in $SUITES_14; do mkdir -p "$depot/tests/$s"; : > "$depot/tests/$s/.gitkeep"; done
  printf '#!/bin/bash\nexit 0\n' > "$depot/tests/run_all.sh"
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
for _ in 1 2 3 4 5 6 7 8 9 10; do [ -s "$tmp/ecoute" ] && break; sleep 0.5; done
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
for s in $SUITES_14; do mkdir -p "$tmp/horsgit/tests/$s"; done
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

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
exit 0
