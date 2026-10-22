#!/bin/bash
# Test de tools/ci_local.sh (change local-ci-container, design D1 à D7b, D9, D10, D14) : dépôts Git temporaires, faux Docker et faux
# Colima qui journalisent leurs arguments et sortent comme on le leur dit, faux dossier de données, faux fichier des verdicts
# (CI_LOCAL_VERDICTS). Aucune vraie image, aucun vrai conteneur, aucun réseau ; ni le vrai dossier de données ni le dossier Git du
# dépôt ne sont touchés (chaque cas tourne dans un dépôt temporaire).
# Lancement à la main : bash tests/ci_local/test_ci_local.sh
set -u
racine="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$racine/tools/ci_local.sh"
tmp=$(mktemp -d) || exit 1
trap 'chmod -R u+w "$tmp" 2>/dev/null; rm -rf "$tmp"' EXIT
bin="$tmp/bin"; mkdir -p "$bin" "$tmp/t"
ok=0; ko=0
verifie() { # description  code (0 = vrai)
  if [ "$2" -eq 0 ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1"; ko=$((ko+1)); fi
}

export FX="$tmp/fx"; mkdir -p "$FX"
export FAUX_LOG="$tmp/log"; : > "$FAUX_LOG"
TAB=$(printf '\t')

# Faux Docker : une ligne de journal par appel ; images connues dans $FX/images (« <clé> <clé de base> ») ; « run » garde l'archive reçue
# sur l'entrée, puis imprime une fausse sortie du lanceur selon FAUX_PASSAGE (vert, rouge, sans_verdict, interrompre).
cat > "$bin/docker" <<'SCRIPT'
#!/bin/bash
echo "docker $*" >> "$FAUX_LOG"
case "${1:-}" in
  info) [ "${FAUX_DOCKER_ARRETE:-0}" = "1" ] && exit 1; exit 0 ;;
  image)
    [ "${2:-}" = inspect ] || exit 0
    cle=${3#pmzilla-ci:}
    grep -q "^$cle " "$FX/images" 2>/dev/null; exit $? ;;
  images)
    base=""; for a in "$@"; do case "$a" in label=pmzilla.ci.base=*) base=${a#label=pmzilla.ci.base=} ;; esac; done
    grep -q " $base\$" "$FX/images" 2>/dev/null && echo "id-image"; exit 0 ;;
  build)
    cat > "$FX/contexte.tar"
    [ "${FAUX_BUILD_ECHEC:-0}" = "1" ] && { echo "échec de construction" >&2; exit 1; }
    cle=""; base=""; prec=""
    for a in "$@"; do
      case "$prec" in --tag) cle=${a#pmzilla-ci:} ;; --label) case "$a" in pmzilla.ci.base=*) base=${a#pmzilla.ci.base=} ;; esac ;; esac
      prec=$a
    done
    echo "$cle $base" >> "$FX/images"; exit 0 ;;
  run)
    cat > "$FX/archive.tar"
    case "${FAUX_PASSAGE:-vert}" in
      vert)
        echo "run_all : suites propres au Mac non lancées : 2 (finish_branch:shell hooks:shell)"
        echo "alpha                      3 tests · OK · 0,1 s"
        echo "beta                       2 tests · OK · 0,1 s"
        echo "Tests sautés : 0 (suites Python 0, branches shell 0)"
        echo "TOTAL : 5 tests dans 2 suites · tous réussis · durée totale 1,0 s"
        exit 0 ;;
      rouge)
        echo "run_all : suites propres au Mac non lancées : 2 (finish_branch:shell hooks:shell)"
        echo "alpha                      3 tests · OK · 0,1 s"
        echo "beta                       2 tests · ÉCHEC (code 1) : /home/node/arbre/tests/beta trace · 0,1 s"
        echo "TOTAL : 5 tests dans 2 suites · 1 suite(s) en échec : beta · durée totale 1,0 s"
        exit 1 ;;
      sans_verdict) echo "erreur avant le lanceur" >&2; exit 125 ;;
      interrompre) kill -INT "$PPID"; sleep 1; exit 130 ;;
    esac ;;
  rm) exit 0 ;;
esac
exit 0
SCRIPT
# Faux Colima : « status » réussit sauf avec FAUX_COLIMA_ARRETE=1 ; « start » est journalisé.
cat > "$bin/colima" <<'SCRIPT'
#!/bin/bash
echo "colima $*" >> "$FAUX_LOG"
[ "${1:-}" = status ] && [ "${FAUX_COLIMA_ARRETE:-0}" = "1" ] && exit 1
exit 0
SCRIPT
chmod +x "$bin/docker" "$bin/colima"
export PATH="$bin:$PATH"
export CI_LOCAL_DOCKER="$bin/docker" CI_LOCAL_COLIMA="$bin/colima"
export PMZILLA_LAB_DATA="$tmp/donnees"; mkdir -p "$PMZILLA_LAB_DATA"
export TMPDIR="$tmp/t"
export GIT_CONFIG_GLOBAL="$tmp/gitconfig" GIT_CONFIG_NOSYSTEM=1
: > "$GIT_CONFIG_GLOBAL"
export GIT_AUTHOR_NAME=essai GIT_AUTHOR_EMAIL=essai@exemple.invalid GIT_COMMITTER_NAME=essai GIT_COMMITTER_EMAIL=essai@exemple.invalid
unset CI_LOCAL_VERDICTS FINISH_LOCK_TOKEN FAUX_PASSAGE FAUX_DOCKER_ARRETE FAUX_BUILD_ECHEC FAUX_COLIMA_ARRETE DBTEST_PORT

# Dépôt temporaire : les entrées de la clé d'image (ci/Dockerfile, entrées CI de l'inventaire, .python-version, DEPS du lanceur).
n_depot=0
nouveau_depot() {
  n_depot=$((n_depot+1)); depot="$tmp/depot$n_depot"; mkdir -p "$depot"
  ( cd "$depot" && git init -q && git checkout -q -b main
    mkdir -p ci docs/pmzilla tests
    printf 'FROM node:26-slim@sha256:%s\n' "$(printf 'b%.0s' $(seq 64))" > ci/Dockerfile
    printf 'components:\n  - {name: library/node, kind: docker-image, pinned_in: CI Dockerfile, upstream: Docker Hub tags, procedure: Update the CI image}\n' > docs/pmzilla/composants.yaml
    echo "3.14" > .python-version
    printf '#!/bin/bash\nDEPS="${RUN_ALL_DEPS---with numpy --with pyyaml}"\n' > tests/run_all.sh
    printf 'local.txt\n' > .gitignore
    echo "a" > a.txt
    git add -A && git commit -q -m "départ" )
  ARBRE_MAIN=$(git -C "$depot" rev-parse 'main^{tree}')
}
commit_depot() { # message : commit de tout ce qui a changé
  ( cd "$depot" && git add -A && git commit -q -m "$1" )
}
remise() { : > "$FAUX_LOG"; rm -f "$FX/archive.tar" "$FX/contexte.tar"; }
lance() { # lance le script dans le dépôt courant ; sortie et erreurs dans $tmp/s, code dans $code
  ( cd "$depot" && bash "$SCRIPT" "$@" ) > "$tmp/s" 2>&1; code=$?
}
# Relais qui rétablit SIGINT par défaut avant bash (même raison que tests/db_scripts/test_dbtest.sh, #242).
lance_relais() {
  ( cd "$depot" && python3 -I -B -c 'import os, signal, sys; signal.signal(signal.SIGINT, signal.SIG_DFL); os.execvp("bash", ["bash"] + sys.argv[1:])' "$SCRIPT" "$@" ) > "$tmp/s" 2>&1; code=$?
}
construire_image() { # image du sommet de main, par le script lui-même (faux Docker)
  ( cd "$depot" && bash "$SCRIPT" build ) > "$tmp/b" 2>&1
}
n_appels() { grep -c -- "$1" "$FAUX_LOG"; }
derniere() { tail -1 "$tmp/s"; }
droits() { stat -f %Lp "$1" 2>/dev/null || stat -c %a "$1" 2>/dev/null; }

# --- aide et usage (D1, D2 code 2)
nouveau_depot
remise; lance --help
verifie "ci_local : --help code 0, nomme run, build, up, les codes et le verdict enregistré, aucun appel à Docker" "$([ $code -eq 0 ] && grep -q 'run \[<branche>\]' "$tmp/s" && grep -q 'build' "$tmp/s" && grep -q 'up' "$tmp/s" && grep -q 'CI_LOCAL_VERDICTS' "$tmp/s" && grep -q 'verdicts' "$tmp/s" && [ ! -s "$FAUX_LOG" ]; echo $?)"
for args in "" "lancer" "run a b" "build x" "--bidon" "run --x"; do
  remise; lance $args
  verifie "ci_local : usage « $args » refusé (code 2, phrase de D2), aucun appel à Docker" "$([ $code -eq 2 ] && grep -qxF "ci_local : usage : bash tools/ci_local.sh run [<branche>] | build | up" "$tmp/s" && [ ! -s "$FAUX_LOG" ]; echo $?)"
done

# --- refus d'entrée (code 4)
remise; ( cd "$tmp" && bash "$SCRIPT" run ) > "$tmp/s" 2>&1; code=$?
verifie "ci_local : hors du dépôt, code 4, phrase, Docker non appelé" "$([ $code -eq 4 ] && grep -qxF "ci_local : hors du dépôt" "$tmp/s" && [ ! -s "$FAUX_LOG" ]; echo $?)"
remise; lance run inconnue
verifie "ci_local : branche inconnue, code 4, phrase" "$([ $code -eq 4 ] && grep -qxF "ci_local : branche inconnue : inconnue" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
echo "nouveau" > "$depot/non-suivi.txt"
remise; lance run
verifie "ci_local : fichier non suivi non ignoré sans branche : arbre non propre, code 4, aucun conteneur" "$([ $code -eq 4 ] && grep -qxF "ci_local : arbre non propre ; rien n'est lancé" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
remise; lance build
verifie "ci_local : build sur un arbre non propre, code 4, aucune construction" "$([ $code -eq 4 ] && grep -qxF "ci_local : arbre non propre ; rien n'est lancé" "$tmp/s" && [ "$(n_appels 'docker build')" -eq 0 ]; echo $?)"
rm -f "$depot/non-suivi.txt"

# --- Docker ne répond pas (code 3)
remise; FAUX_DOCKER_ARRETE=1 lance run
verifie "ci_local : Docker arrêté, code 3, phrase avec colima status, aucun conteneur" "$([ $code -eq 3 ] && grep -qxF "ci_local : Docker ne répond pas ; rien n'est lancé (colima status)" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"

# --- image absente (code 5)
remise; lance run
verifie "ci_local : aucune image de la clé, code 5, phrase, aucun conteneur" "$([ $code -eq 5 ] && grep -qxF "ci_local : image absente ou périmée (lancer bash tools/ci_local.sh up)" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"

# --- construction (D1 build, D4) : clé en étiquette et dans le tag, contexte = archive de l'arbre de HEAD
remise; lance build
verifie "ci_local : build, code 0, phrase « image construite (<clé courte>) »" "$([ $code -eq 0 ] && grep -Eq "^ci_local : image construite \([0-9a-f]{12}\)$" "$tmp/s"; echo $?)"
verifie "ci_local : build depuis ci/Dockerfile, clé en étiquette et dans le tag, contexte sur l'entrée" "$(grep '^docker build' "$FAUX_LOG" | grep -q -- '--file ci/Dockerfile' && grep '^docker build' "$FAUX_LOG" | grep -Eq -- '--tag pmzilla-ci:[0-9a-f]{64}' && grep '^docker build' "$FAUX_LOG" | grep -Eq -- '--label pmzilla.ci.cle=[0-9a-f]{64}' && tar -tf "$FX/contexte.tar" | grep -qx 'ci/Dockerfile'; echo $?)"
: > "$FX/images"
remise; FAUX_BUILD_ECHEC=1 lance build
verifie "ci_local : construction en échec, code 6, phrase, aucune image enregistrée, aucun conteneur" "$([ $code -eq 6 ] && grep -qxF "ci_local : construction de l'image en échec" "$tmp/s" && [ ! -s "$FX/images" ] && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"

# --- passage vert (D7) et enregistrement (D7b)
construire_image
export CI_LOCAL_VERDICTS="$tmp/verdicts"
printf 'ffffffffffffffffffffffffffffffffffffffff\tvert\t%s\n' "$(printf 'e%.0s' $(seq 64))" > "$CI_LOCAL_VERDICTS"
autre_ligne=$(cat "$CI_LOCAL_VERDICTS")
remise; lance run
verifie "ci_local : passage vert, code 0, dernière ligne « ci_local : verdict vert (arbre » avec image, suites et suites Mac" "$([ $code -eq 0 ] && derniere | grep -Eq "^ci_local : verdict vert \(arbre ${ARBRE_MAIN:0:12}, image [0-9a-f]{12}, 2 suites, 2 suites Mac non lancées\)$"; echo $?)"
verifie "ci_local : ligne TOTAL et ligne des suites Mac redites juste avant le verdict, ligne d'enregistrement juste avant lui" "$(n=$(wc -l < "$tmp/s"); [ "$(sed -n "$((n-3))p" "$tmp/s")" = "TOTAL : 5 tests dans 2 suites · tous réussis · durée totale 1,0 s" ] && sed -n "$((n-2))p" "$tmp/s" | grep -q '^run_all : suites propres au Mac non lancées : 2' && [ "$(sed -n "$((n-1))p" "$tmp/s")" = "ci_local : verdict enregistré pour l'arbre ${ARBRE_MAIN:0:12}" ]; echo $?)"
verifie "ci_local : ligne vert de l'arbre testé avec la clé d'image, autre ligne inchangée" "$(grep -Eq "^${ARBRE_MAIN}${TAB}vert${TAB}[0-9a-f]{64}\$" "$CI_LOCAL_VERDICTS" && grep -qxF "$autre_ligne" "$CI_LOCAL_VERDICTS" && [ "$(wc -l < "$CI_LOCAL_VERDICTS" | tr -d ' ')" -eq 2 ]; echo $?)"
verifie "ci_local : ligne « Tests sautés » du lanceur redite avant la ligne TOTAL, et dans le rapport" "$(n=$(wc -l < "$tmp/s"); [ "$(sed -n "$((n-4))p" "$tmp/s")" = "Tests sautés : 0 (suites Python 0, branches shell 0)" ] && grep -qxF 'Tests sautés : 0 (suites Python 0, branches shell 0)' "$(ls -t "$PMZILLA_LAB_DATA/ci"/rapport-* | head -1)"; echo $?)"
verifie "ci_local : fichier des verdicts lisible par son propriétaire seul" "$([ "$(droits "$CI_LOCAL_VERDICTS")" = 600 ]; echo $?)"
verifie "ci_local : chaque ligne du fichier = arbre, verdict, clé (ni branche, ni chemin, ni date)" "$(! grep -Evq "^[0-9a-f]{40}${TAB}(vert|rouge)${TAB}[0-9a-f]{64}\$" "$CI_LOCAL_VERDICTS"; echo $?)"

# --- isolement (D6, D11) : arguments enregistrés
faux_mdp="mdp-"'appelant-x'   # fabriqué à l'exécution : aucun littéral pour la garde des secrets
remise; PMZILLA_LAB_DB_PASSWORD="$faux_mdp" DBTEST_PORT=55999 FINISH_LOCK_TOKEN=jeton-appelant-x GH_TOKEN=faux-jeton-x \
  PMZILLA_LAB_SENSITIVE_NAMES="$tmp/noms-x" PMZILLA_NOMS="$tmp/noms-y" lance run
ligne_run=$(sed -n '/^docker run/,/^docker rm/p' "$FAUX_LOG" | sed '$d')   # le script intérieur tient sur plusieurs lignes
verifie "ci_local : réseau coupé, --rm, utilisateur non root, nom au hasard, entrée sur stdin" "$(printf '%s' "$ligne_run" | grep -q -- '--network none' && printf '%s' "$ligne_run" | grep -q -- '--rm' && printf '%s' "$ligne_run" | grep -q -- '--user node' && printf '%s' "$ligne_run" | grep -Eq -- '--name pmzilla-ci-[0-9a-f]{8,}' && printf '%s' "$ligne_run" | grep -q -- ' -i '; echo $?)"
verifie "ci_local : aucun montage, volume, périphérique ni socket" "$(! printf '%s' "$ligne_run" | grep -Eq -- '(^| )(-v|--volume|--mount|--device|--privileged)( |=)|docker\.sock|--env-file'; echo $?)"
verifie "ci_local : aucune variable de l'appelant (base, DBTEST_PORT, jetons, noms sensibles), ni nom ni valeur" "$(! printf '%s' "$ligne_run" | grep -Eq 'mdp-appelant-x|55999|jeton-appelant-x|faux-jeton-x|noms-x|noms-y|PMZILLA_LAB_DB_|DBTEST_PORT|FINISH_LOCK_TOKEN|GH_TOKEN|SENSITIVE|PMZILLA_NOMS'; echo $?)"
verifie "ci_local : environnement construit par le script (UV_OFFLINE=1, HOME et TMPDIR du conteneur, durées dans le conteneur), lanceur --portable" "$(printf '%s' "$ligne_run" | grep -q -- '--env UV_OFFLINE=1' && printf '%s' "$ligne_run" | grep -q -- '--env HOME=/home/node' && printf '%s' "$ligne_run" | grep -q -- '--env TMPDIR=/tmp' && printf '%s' "$ligne_run" | grep -q -- '--env RUN_ALL_DURATIONS=/tmp/' && printf '%s' "$ligne_run" | grep -q -- 'tests/run_all.sh --portable' && printf '%s' "$ligne_run" | grep -q 'RUN_ALL_JOBS'; echo $?)"
verifie "ci_local : limites de processeurs et de mémoire" "$(printf '%s' "$ligne_run" | grep -q -- '--cpus ' && printf '%s' "$ligne_run" | grep -q -- '--memory '; echo $?)"
verifie "ci_local : conteneur retiré à la fin" "$(grep -q '^docker rm -f pmzilla-ci-' "$FAUX_LOG"; echo $?)"

# --- entrée propre (D5) : archive d'un commit, fichier ignoré absent, branche nommée
echo "secret local" > "$depot/local.txt"
( cd "$depot" && git checkout -q -b feat/branche-temoin-x && echo "b" > b.txt && git add b.txt && git commit -q -m "b" && git checkout -q main )
ARBRE_B=$(git -C "$depot" rev-parse 'feat/branche-temoin-x^{tree}')
remise; lance run feat/branche-temoin-x
verifie "ci_local : branche nommée : arbre de son sommet testé (archive avec b.txt, verdict pour cet arbre)" "$(tar -tf "$FX/archive.tar" | grep -qx 'b.txt' && derniere | grep -q "arbre ${ARBRE_B:0:12}" && grep -q "^${ARBRE_B}${TAB}vert${TAB}" "$CI_LOCAL_VERDICTS"; echo $?)"
verifie "ci_local : fichier ignoré absent de l'archive envoyée" "$(! tar -tf "$FX/archive.tar" | grep -q 'local.txt'; echo $?)"
verifie "ci_local : ni branche ni chemin dans le fichier des verdicts" "$(! grep -Eq "branche-temoin|$tmp|/" "$CI_LOCAL_VERDICTS"; echo $?)"
rapport=$(ls -t "$PMZILLA_LAB_DATA/ci"/rapport-* 2>/dev/null | head -1)
verifie "ci_local : rapport écrit dans le dossier ci du dossier de données, arbre, clé, date, ligne TOTAL, liste Mac, code" "$([ -n "$rapport" ] && grep -q "$ARBRE_B" "$rapport" && grep -Eq '[0-9a-f]{64}' "$rapport" && grep -Eq '[0-9]{4}-[0-9]{2}-[0-9]{2}' "$rapport" && grep -qF "TOTAL : 5 tests dans 2 suites" "$rapport" && grep -q 'finish_branch:shell hooks:shell' "$rapport" && grep -q 'code : 0' "$rapport"; echo $?)"
verifie "ci_local : rapport sans chemin ni nom de branche, lisible par son propriétaire seul" "$([ -n "$rapport" ] && ! grep -Eq "branche-temoin|$tmp|$depot|/home/" "$rapport" && [ "$(droits "$rapport")" = 600 ]; echo $?)"
rm -f "$depot/local.txt"

# --- passage rouge : remplace la ligne vert de l'arbre
remise; FAUX_PASSAGE=rouge lance run
verifie "ci_local : passage rouge, code 1, dernière ligne « verdict rouge (arbre … ) : beta »" "$([ $code -eq 1 ] && derniere | grep -Eq "^ci_local : verdict rouge \(arbre ${ARBRE_MAIN:0:12}, image [0-9a-f]{12}\) : beta$"; echo $?)"
verifie "ci_local : ligne rouge pour l'arbre, plus de ligne vert pour lui, autres lignes gardées" "$(grep -q "^${ARBRE_MAIN}${TAB}rouge${TAB}" "$CI_LOCAL_VERDICTS" && ! grep -q "^${ARBRE_MAIN}${TAB}vert" "$CI_LOCAL_VERDICTS" && grep -qxF "$autre_ligne" "$CI_LOCAL_VERDICTS" && grep -q "^${ARBRE_B}${TAB}vert" "$CI_LOCAL_VERDICTS"; echo $?)"
rapport=$(ls -t "$PMZILLA_LAB_DATA/ci"/rapport-* 2>/dev/null | head -1)
verifie "ci_local : rapport du passage rouge sans la trace de la suite (chemin du conteneur)" "$(grep -q 'code : 1' "$rapport" && ! grep -q '/home/node' "$rapport"; echo $?)"

# --- passage sans verdict du lanceur : ligne de l'arbre retirée, rien d'écrit
remise; FAUX_PASSAGE=sans_verdict lance run
verifie "ci_local : conteneur sans verdict du lanceur : code 1, verdict rouge dit, aucune ligne pour l'arbre" "$([ $code -eq 1 ] && derniere | grep -q '^ci_local : verdict rouge (arbre' && ! grep -q "^${ARBRE_MAIN}${TAB}" "$CI_LOCAL_VERDICTS" && grep -qxF "$autre_ligne" "$CI_LOCAL_VERDICTS"; echo $?)"

# --- interruption : conteneur retiré, aucune ligne pour l'arbre
remise; lance run >/dev/null
remise; FAUX_PASSAGE=interrompre lance_relais run
verifie "ci_local : interruption : code 130, conteneur retiré, aucune ligne pour l'arbre testé" "$([ $code -eq 130 ] && grep -q '^docker rm -f pmzilla-ci-' "$FAUX_LOG" && ! grep -q "^${ARBRE_MAIN}${TAB}" "$CI_LOCAL_VERDICTS" && grep -qxF "$autre_ligne" "$CI_LOCAL_VERDICTS"; echo $?)"

# --- codes 2 à 7 : la ligne de l'arbre n'est ni retirée ni écrite
lance run >/dev/null
avant=$(cat "$CI_LOCAL_VERDICTS")
remise; FAUX_DOCKER_ARRETE=1 lance run
verifie "ci_local : après le code 3, fichier des verdicts inchangé" "$([ $code -eq 3 ] && [ "$(cat "$CI_LOCAL_VERDICTS")" = "$avant" ]; echo $?)"
remise; lance run inconnue
verifie "ci_local : après le code 4, fichier des verdicts inchangé" "$([ $code -eq 4 ] && [ "$(cat "$CI_LOCAL_VERDICTS")" = "$avant" ]; echo $?)"

# --- retrait de la ligne de départ : seule ligne du fichier (grep -v sans sortie), puis retrait raté, puis verrou des écritures concurrentes
printf '%s\tvert\t%s\n' "$ARBRE_MAIN" "$(printf 'e%.0s' $(seq 64))" > "$tmp/seul"
remise; CI_LOCAL_VERDICTS="$tmp/seul" FAUX_PASSAGE=sans_verdict lance run
verifie "ci_local : la seule ligne du fichier est celle de l'arbre : elle est retirée au départ, sans message de retrait manqué" "$([ ! -s "$tmp/seul" ] && ! grep -q 'non retiré' "$tmp/s"; echo $?)"
mkdir -p "$tmp/ro2"; printf '%s\tvert\t%s\n' "$ARBRE_MAIN" "$(printf 'e%.0s' $(seq 64))" > "$tmp/ro2/verdicts"; chmod 500 "$tmp/ro2"
remise; CI_LOCAL_VERDICTS="$tmp/ro2/verdicts" FAUX_PASSAGE=rouge lance run
verifie "ci_local : retrait de la ligne de départ raté : dit tout de suite, puis « verdict non enregistré (écriture impossible) », code du lanceur" "$([ $code -eq 1 ] && grep -qxF 'ci_local : verdict précédent de cet arbre non retiré (écriture impossible)' "$tmp/s" && grep -qxF 'ci_local : verdict non enregistré (écriture impossible)' "$tmp/s"; echo $?)"
chmod 700 "$tmp/ro2"
mkdir -p "$tmp/vd"; printf '%s\tvert\t%s\n' "ffffffffffffffffffffffffffffffffffffffff" "$(printf 'e%.0s' $(seq 64))" > "$tmp/vd/verdicts"
mkdir "$tmp/vd/verdicts.lock"; touch -t 200001010000 "$tmp/vd/verdicts.lock"
remise; CI_LOCAL_VERDICTS="$tmp/vd/verdicts" lance run
verifie "ci_local : verrou des écritures vieux de plus d'une minute : repris, verdict enregistré, verrou retiré" "$([ $code -eq 0 ] && grep -q "^${ARBRE_MAIN}${TAB}vert" "$tmp/vd/verdicts" && [ ! -e "$tmp/vd/verdicts.lock" ]; echo $?)"
mkdir "$tmp/vd/verdicts.lock"
remise; CI_LOCAL_VERDICTS="$tmp/vd/verdicts" lance run
verifie "ci_local : verrou des écritures tenu par un autre passage : verdict non enregistré (écriture impossible), code inchangé, verrou de l'autre laissé" "$([ $code -eq 0 ] && grep -qxF 'ci_local : verdict non enregistré (écriture impossible)' "$tmp/s" && [ -d "$tmp/vd/verdicts.lock" ]; echo $?)"
rmdir "$tmp/vd/verdicts.lock"
remise; CI_LOCAL_VERDICTS="$tmp/vd/verdicts" lance run
verifie "ci_local : sans verrou, deux passages de suite : un seul verrou à la fois, aucun verrou ne reste, une seule ligne par arbre" "$([ ! -e "$tmp/vd/verdicts.lock" ] && [ "$(grep -c "^${ARBRE_MAIN}${TAB}" "$tmp/vd/verdicts")" -eq 1 ]; echo $?)"

# --- fichier des verdicts impossible à écrire : dit en une ligne, code inchangé
mkdir -p "$tmp/ro"; chmod 500 "$tmp/ro"
remise; CI_LOCAL_VERDICTS="$tmp/ro/verdicts" lance run
verifie "ci_local : verdict non écrit (écriture impossible) dit juste avant le verdict, code 0" "$([ $code -eq 0 ] && n=$(wc -l < "$tmp/s") && [ "$(sed -n "$((n-1))p" "$tmp/s")" = "ci_local : verdict non enregistré (écriture impossible)" ] && derniere | grep -q '^ci_local : verdict vert'; echo $?)"
chmod 700 "$tmp/ro"

# --- faux Docker sans CI_LOCAL_VERDICTS : rien lu ni écrit
unset CI_LOCAL_VERDICTS
remise; lance run
verifie "ci_local : CI_LOCAL_DOCKER sans CI_LOCAL_VERDICTS : code 0, aucun fichier des verdicts créé ni lu" "$([ $code -eq 0 ] && [ ! -e "$PMZILLA_LAB_DATA/ci/verdicts" ] && ! grep -q 'verdict enregistré\|verdict non enregistré' "$tmp/s"; echo $?)"
export CI_LOCAL_VERDICTS="$tmp/verdicts"

# --- rapport impossible : dit en une ligne, code du lanceur
remise; FAUX_PASSAGE=rouge PMZILLA_LAB_DATA="$tmp/absent-x" lance run
verifie "ci_local : dossier de données introuvable : rapport non écrit dit, code du lanceur (1)" "$([ $code -eq 1 ] && grep -q '^ci_local : rapport non écrit (' "$tmp/s"; echo $?)"
mkdir -p "$tmp/donnees-ro"; chmod 500 "$tmp/donnees-ro"
remise; PMZILLA_LAB_DATA="$tmp/donnees-ro" lance run
verifie "ci_local : dossier de données non inscriptible : rapport non écrit (écriture impossible), code 0" "$([ $code -eq 0 ] && grep -qxF 'ci_local : rapport non écrit (écriture impossible)' "$tmp/s"; echo $?)"
chmod 700 "$tmp/donnees-ro"

# --- clé d'image (D4) : changement de ci/Dockerfile ou des dépendances du lanceur => 5
lance run >/dev/null; avant_cle=$(cat "$CI_LOCAL_VERDICTS")
echo "RUN true" >> "$depot/ci/Dockerfile"; commit_depot "dockerfile"
remise; lance run
verifie "ci_local : ci/Dockerfile changé depuis la construction : code 5, phrase de l'image, aucun conteneur" "$([ $code -eq 5 ] && grep -qxF "ci_local : image absente ou périmée (lancer bash tools/ci_local.sh up)" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
verifie "ci_local : après le code 5, fichier des verdicts inchangé (ni retrait ni écriture)" "$([ "$(cat "$CI_LOCAL_VERDICTS")" = "$avant_cle" ]; echo $?)"
construire_image
printf '#!/bin/bash\nDEPS="${RUN_ALL_DEPS---with numpy --with pyyaml --with lxml}"\n' > "$depot/tests/run_all.sh"; commit_depot "deps"
remise; lance run
verifie "ci_local : dépendances du lanceur changées : code 5" "$([ $code -eq 5 ] && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
construire_image
echo "3.13" > "$depot/.python-version"; commit_depot "python"
remise; lance run
verifie "ci_local : .python-version changé : code 5" "$([ $code -eq 5 ]; echo $?)"
construire_image
# en-têtes PEP 723 (tools, tests, .claude/skills) : un changement de dépendance d'un en-tête change la clé (5), un changement hors de l'en-tête ne la change pas
mkdir -p "$depot/tools" "$depot/.claude/skills/x"
printf '# /// script\n# dependencies = ["requests"]\n# ///\nprint(1)\n' > "$depot/tools/outil_x.py"
printf '# /// script\n# dependencies = ["pyyaml"]\n# ///\nprint(2)\n' > "$depot/.claude/skills/x/aide_x.py"
printf 'print(3)\n' > "$depot/tools/sans_entete.py"
commit_depot "entetes"
remise; lance run
verifie "ci_local : scripts à en-tête PEP 723 ajoutés : la clé change, code 5" "$([ $code -eq 5 ]; echo $?)"
construire_image
printf '# /// script\n# dependencies = ["requests"]\n# ///\nprint(99)\n' > "$depot/tools/outil_x.py"; printf 'print(4)\n' > "$depot/tools/sans_entete.py"; commit_depot "corps"
remise; lance run
verifie "ci_local : corps d'un script et script sans en-tête changés : la clé ne change pas (code 0)" "$([ $code -eq 0 ]; echo $?)"
printf '# /// script\n# dependencies = ["requests", "feedparser"]\n# ///\nprint(99)\n' > "$depot/tools/outil_x.py"; commit_depot "dep"
remise; lance run
verifie "ci_local : dépendance d'un en-tête de tools changée : code 5" "$([ $code -eq 5 ]; echo $?)"
construire_image
printf '# /// script\n# dependencies = ["pyyaml", "numpy"]\n# ///\nprint(2)\n' > "$depot/.claude/skills/x/aide_x.py"; commit_depot "dep skills"
remise; lance run
verifie "ci_local : dépendance d'un en-tête de .claude/skills changée : code 5" "$([ $code -eq 5 ]; echo $?)"
construire_image

# --- verrou npm déclaré (D10) : clé de base inchangée, verrou absent de l'image => 5 avec la phrase npm
mkdir -p "$depot/mothra"; echo '{"lockfileVersion": 3}' > "$depot/mothra/package-lock.json"
printf 'SUITES_NPM=(mothra:mothra)\n' >> "$depot/tests/run_all.sh"; commit_depot "npm"
remise; lance run
verifie "ci_local : verrou npm déclaré différent de l'image : code 5, phrase npm, aucun conteneur" "$([ $code -eq 5 ] && grep -qxF "ci_local : dépendances npm de l'image différentes du verrou (lancer bash tools/ci_local.sh up)" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
remise; lance build
verifie "ci_local : build avec un verrou npm déclaré : couche npm non prise en charge (D10 inerte), code 6, aucune construction" "$([ $code -eq 6 ] && grep -qxF "ci_local : construction de l'image en échec" "$tmp/s" && [ "$(n_appels 'docker build')" -eq 0 ]; echo $?)"
( cd "$depot" && git rm -q -r mothra && printf '#!/bin/bash\nDEPS="${RUN_ALL_DEPS---with numpy --with pyyaml --with lxml}"\n' > tests/run_all.sh && git add -A && git commit -q -m "sans npm" )
remise; lance run
verifie "ci_local : sans verrou npm déclaré, aucun verrou vérifié (l'image de la clé suffit)" "$([ $code -eq 0 ]; echo $?)"

# --- verrou de fin (code 7)
commun=$(git -C "$depot" rev-parse --path-format=absolute --git-common-dir)
verrou="$commun/pmzilla-fin-en-cours"
mkdir -p "$verrou"; echo $$ > "$verrou/pid"; date +%s > "$verrou/debut"; echo "feat/autre" > "$verrou/branche"; echo "jeton-verrou-x" > "$verrou/jeton"
lance run >/dev/null; avant_verrou=$(cat "$CI_LOCAL_VERDICTS")
for sous in run build up; do
  remise; lance $sous
  verifie "ci_local : $sous refusé sous le verrou d'une autre fin (code 7, phrase), Docker et Colima non appelés" "$([ $code -eq 7 ] && grep -qxF "ci_local : fin de branche en cours (feat/autre), lancement refusé" "$tmp/s" && [ ! -s "$FAUX_LOG" ]; echo $?)"
done
remise; FINISH_LOCK_TOKEN=autre-jeton lance run
verifie "ci_local : jeton différent : code 7" "$([ $code -eq 7 ]; echo $?)"
verifie "ci_local : après le code 7, fichier des verdicts inchangé" "$([ "$(cat "$CI_LOCAL_VERDICTS")" = "$avant_verrou" ]; echo $?)"
remise; FINISH_LOCK_TOKEN=jeton-verrou-x lance run
verifie "ci_local : jeton de la fin : le passage a lieu comme sans verrou" "$([ $code -eq 0 ] && [ "$(n_appels 'docker run')" -eq 1 ]; echo $?)"
verifie "ci_local : le verrou n'est ni retiré ni modifié" "$([ -d "$verrou" ] && [ "$(cat "$verrou/jeton")" = jeton-verrou-x ] && [ "$(cat "$verrou/pid")" = "$$" ]; echo $?)"
sleep 0 & mort=$!; wait "$mort"
echo "$mort" > "$verrou/pid"
remise; lance run
verifie "ci_local : verrou périmé dit et ignoré, le passage a lieu, verrou laissé en place" "$([ $code -eq 0 ] && grep -qxF "ci_local : verrou de fin périmé, ignoré" "$tmp/s" && [ -d "$verrou" ]; echo $?)"
rm -rf "$verrou"

# --- up (D9)
nouveau_depot
: > "$FX/images"   # aucune image : le nouveau dépôt a la même clé que le premier
remise; lance up
verifie "ci_local : up sans image : Colima déjà là (aucun démarrage), construction puis passage, code 0" "$([ $code -eq 0 ] && [ "$(n_appels 'colima start')" -eq 0 ] && [ "$(n_appels 'docker build')" -eq 1 ] && [ "$(n_appels 'docker run')" -eq 1 ] && [ "$(grep -n '^docker build' "$FAUX_LOG" | cut -d: -f1)" -lt "$(grep -n '^docker run' "$FAUX_LOG" | cut -d: -f1)" ]; echo $?)"
verifie "ci_local : up enregistre le verdict de l'arbre du sommet de main" "$(grep -q "^${ARBRE_MAIN}${TAB}vert${TAB}" "$CI_LOCAL_VERDICTS"; echo $?)"
remise; lance up
verifie "ci_local : up avec image de la clé et Colima qui répond : ni démarrage, ni construction, un seul conteneur" "$([ $code -eq 0 ] && [ "$(n_appels 'colima start')" -eq 0 ] && [ "$(n_appels 'docker build')" -eq 0 ] && [ "$(n_appels 'docker run')" -eq 1 ]; echo $?)"
remise; FAUX_COLIMA_ARRETE=1 lance up
verifie "ci_local : up avec Colima qui ne répond pas : colima start avec les ressources du lab, une ligne le dit" "$([ "$(n_appels 'colima start --cpu 4 --memory 6')" -eq 1 ] && grep -q "^ci_local : Colima ne répond pas" "$tmp/s"; echo $?)"
remise; FAUX_PASSAGE=rouge lance up
verifie "ci_local : up rend le code du passage (1 si rouge)" "$([ $code -eq 1 ] && derniere | grep -q '^ci_local : verdict rouge'; echo $?)"
( cd "$depot" && git checkout -q -b feat/up-x && echo "c" > c.txt && git add c.txt && git commit -q -m c )
remise; lance up feat/up-x
verifie "ci_local : up <branche> : passage sur le sommet de cette branche" "$([ $code -eq 0 ] && grep -q '^docker run' "$FAUX_LOG" && tar -tf "$FX/archive.tar" | grep -qx 'c.txt'; echo $?)"
remise; FAUX_DOCKER_ARRETE=1 lance up
verifie "ci_local : up avec Docker qui ne répond pas : code 3, aucun conteneur" "$([ $code -eq 3 ] && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
verifie "ci_local : up ne supprime jamais d'instance, de volume ni d'image" "$(! grep -Eq '^colima (delete|stop)|^docker (volume|rmi|image rm|system)' "$FAUX_LOG"; echo $?)"

# --- jamais le vrai Docker : le script ne lance que la commande de CI_LOCAL_DOCKER
verifie "ci_local : le script lit CI_LOCAL_DOCKER et CI_LOCAL_COLIMA" "$(grep -q 'CI_LOCAL_DOCKER' "$SCRIPT" && grep -q 'CI_LOCAL_COLIMA' "$SCRIPT"; echo $?)"
verifie "ci_local : le script n'installe jamais de dépendances npm au passage (ni npm install, ni npm ci, ni npx)" "$(! grep -Eq '^[^#]*(npm (install|ci)|npx )' "$SCRIPT"; echo $?)"

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
