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
# sur l'entrée, puis imprime une fausse sortie du lanceur selon FAUX_PASSAGE (vert, rouge, sans_verdict, interrompre, long : run de 6 s
# que le faux « rm » arrête) ; FAUX_CREATE_LONG=1 : « create » attend 6 s après avoir lu le fichier d'environnement (R-20261105-12).
cat > "$bin/docker" <<'SCRIPT'
#!/bin/bash
echo "docker $*" >> "$FAUX_LOG"
case "${1:-}" in
  info) [ "${FAUX_DOCKER_ARRETE:-0}" = "1" ] && exit 1; [ -n "${FAUX_INFO:-}" ] && echo "$FAUX_INFO"; exit 0 ;;
  image)
    # « image rm pmzilla-ci:<clé> » (ci-local-image-prune, D2) : journalisé ; retire la clé de $FX/images ; refusé pour une clé de FAUX_IMAGES_UTILISEES
    if [ "${2:-}" = rm ]; then
      cle=${3#pmzilla-ci:}
      case " ${FAUX_IMAGES_UTILISEES:-} " in *" $cle "*) echo "Error: image is being used by a container" >&2; exit 1 ;; esac
      grep -v "^$cle " "$FX/images" > "$FX/images.tmp"; mv "$FX/images.tmp" "$FX/images"; exit 0
    fi
    [ "${2:-}" = inspect ] || exit 0
    case "${3:-}" in
      pmzilla-ci:*) ;;
      # image de la base (change ci-local-runner, D11) : connue sauf FAUX_BASE_ABSENTE=1 ; FAUX_BASE_CONNUE=<image> : seule celle-ci est connue
      # (change ci-local-base-image-from-tree, D2 : prouve l'absence de repli vers l'image du dépôt de l'outil)
      *) [ "${FAUX_BASE_ABSENTE:-0}" = "1" ] && exit 1
         [ -n "${FAUX_BASE_CONNUE:-}" ] && { [ "${3:-}" = "$FAUX_BASE_CONNUE" ]; exit $?; }
         exit 0 ;;
    esac
    cle=${3#pmzilla-ci:}
    grep -q "^$cle " "$FX/images" 2>/dev/null; exit $? ;;
  create)   # base du passage (change ci-local-runner, D1) : garde le fichier d'environnement tel qu'il est AU MOMENT de la création
    envf=""; prec=""
    for a in "$@"; do [ "$prec" = --env-file ] && envf=$a; prec=$a; done
    if [ -n "$envf" ]; then
      cp "$envf" "$FX/envfile"; echo "$envf" > "$FX/envfile.chemin"
      { stat -f %Lp "$envf" 2>/dev/null || stat -c %a "$envf"; } > "$FX/envfile.mode"
    fi
    # Création longue (écart 2 de la revue 4.1) : le test interrompt le script PENDANT « docker create » (le faux client est arrêté avec lui, comme un Ctrl-C).
    if [ "${FAUX_CREATE_LONG:-0}" = "1" ]; then echo $$ > "$FX/create.pid"; touch "$FX/create-en-cours"; sleep 6; fi
    [ "${FAUX_CREATE_ECHEC:-0}" = "1" ] && exit 1
    exit 0 ;;
  start) exit 0 ;;
  images)
    # « images --filter reference=pmzilla-ci --format {{.Tag}} » (ci-local-image-prune, D2) : une étiquette par ligne, les clés de $FX/images puis
    # les étiquettes de FAUX_TAGS_EXTRA ; FAUX_IMAGES_ECHEC=1 : la liste échoue
    if printf '%s ' "$@" | grep -q 'reference=pmzilla-ci '; then
      [ "${FAUX_IMAGES_ECHEC:-0}" = "1" ] && exit 1
      [ -f "$FX/images" ] && cut -d' ' -f1 "$FX/images"
      for t in ${FAUX_TAGS_EXTRA:-}; do echo "$t"; done
      exit 0
    fi
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
    printf '%s' "${PMZILLA_LAB_DB_PASSWORD:-}" > "$FX/mdp-suites"   # ce que le processus docker reçoit dans SON environnement
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
      phases)
        echo "run_all : suites propres au Mac non lancées : 2 (finish_branch:shell hooks:shell)"
        echo "TOTAL : 5 tests dans 2 suites · tous réussis · durée totale 1,0 s"
        echo "ci_passage : phase portable : verte · 4 s"
        echo "ci_passage : mémoire au plus : ${FAUX_MEM:-812 Mio}"
        exit 0 ;;
      phases_rouge)
        echo "TOTAL : 5 tests dans 2 suites · 1 suite(s) en échec : beta · durée totale 1,0 s"
        echo "ci_passage : phase portable : rouge · 4 s : beta"
        exit 1 ;;
      phases_base)   # tranche 1 : phases portable et base vertes (la ligne TOTAL de la phase portable vient la première)
        echo "run_all : suites propres au Mac non lancées : 2 (finish_branch:shell hooks:shell)"
        echo "TOTAL : 5 tests dans 2 suites · tous réussis · durée totale 1,0 s"
        echo "ci_passage : phase portable : verte · 4 s"
        echo "TOTAL : 1 tests dans 1 suites · tous réussis · durée totale 1,0 s"
        echo "ci_passage : suites propres au Mac non lancées en phase base : 1 (posture_evals)"
        echo "ci_passage : phase base : verte · 9 s"
        echo "ci_passage : mémoire au plus : 900 Mio"
        exit 0 ;;
      phases_base_rouge)
        echo "TOTAL : 5 tests dans 2 suites · tous réussis · durée totale 1,0 s"
        echo "ci_passage : phase portable : verte · 4 s"
        echo "TOTAL : 1 tests dans 1 suites · 1 suite(s) en échec : flow_store · durée totale 1,0 s"
        echo "ci_passage : phase base : rouge · 9 s : flow_store"
        exit 1 ;;
      phases_e2e)   # tranche 2 : les trois phases vertes (ajout de cas, aucun cas existant changé)
        echo "run_all : suites propres au Mac non lancées : 2 (finish_branch:shell hooks:shell)"
        echo "TOTAL : 5 tests dans 2 suites · tous réussis · durée totale 1,0 s"
        echo "ci_passage : phase portable : verte · 4 s"
        echo "ci_passage : phase base : verte · 9 s"
        echo "ci_passage : phase e2e : verte · 20 s"
        echo "ci_passage : mémoire au plus : 900 Mio"
        exit 0 ;;
      phases_e2e_rouge)
        echo "TOTAL : 5 tests dans 2 suites · tous réussis · durée totale 1,0 s"
        echo "ci_passage : phase portable : verte · 4 s"
        echo "ci_passage : phase base : verte · 9 s"
        echo "ci_passage : phase e2e : rouge · 20 s : passe"
        exit 1 ;;
      phases_e2e_non_lancee)
        echo "TOTAL : 5 tests dans 2 suites · tous réussis · durée totale 1,0 s"
        echo "ci_passage : phase portable : verte · 4 s"
        echo "ci_passage : phase base : verte · 9 s"
        echo "ci_passage : phase e2e : non lancée (étapes de bout en bout absentes du script intérieur)"
        exit 0 ;;
      rejeu_vert) echo "TOTAL : 1 tests dans 1 suites · tous réussis · durée totale 1,0 s"; echo "ci_passage : rejeu : verte · 3 s"; exit 0 ;;
      rejeu_rouge)
        echo "TOTAL : 1 tests dans 1 suites · 1 suite(s) en échec : beta · durée totale 1,0 s"
        echo "ci_passage : rejeu : rouge · 3 s : beta"
        exit 1 ;;
      sans_verdict) echo "erreur avant le lanceur" >&2; exit 125 ;;
      # Le tube du script tourne dans un sous-shell d'arrière-plan (écart 1 de la revue 4.1) : le signal va à chaque ancêtre proche qui est ci_local.sh
      # (le sous-shell ignore INT, le script a son trap) ; jamais au shell du test.
      interrompre) p=$PPID
        for _ in 1 2; do
          ps -o command= -p "$p" 2>/dev/null | grep -q 'tools/ci_local\.sh' && kill -INT "$p" 2>/dev/null
          p=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' '); [ -n "$p" ] || break
        done
        sleep 1; exit 130 ;;
      # Passage long (écart 1) : tant que « docker rm » ne l'a pas arrêté, il va à sa fin naturelle (marque run-fini) au bout de 6 s.
      long) echo $$ > "$FX/run.pid"; touch "$FX/run-en-cours"; sleep 6; echo fini > "$FX/run-fini"; exit 0 ;;
    esac ;;
  rm) if [ -f "$FX/run.pid" ]; then kill "$(cat "$FX/run.pid")" 2>/dev/null; rm -f "$FX/run.pid"; fi; exit 0 ;;
esac
exit 0
SCRIPT
# Faux Colima : « status » réussit sauf avec FAUX_COLIMA_ARRETE=1 ; « start » est journalisé.
cat > "$bin/colima" <<'SCRIPT'
#!/bin/bash
echo "colima $*" >> "$FAUX_LOG"
[ "${1:-}" = status ] && [ "${FAUX_COLIMA_ARRETE:-0}" = "1" ] && exit 1
# « ssh -- df -Pk <dossier> » (ci-local-image-prune, D4) : une sortie de df dont les Kio libres (champ 4) viennent de FAUX_DF_KIO, par défaut au-dessus
# du seuil de 15 Gio (aucun cas existant ne change) ; FAUX_DF_ECHEC=1 : la mesure échoue.
if [ "${1:-}" = ssh ]; then
  [ "${FAUX_DF_ECHEC:-0}" = "1" ] && exit 1
  echo "Filesystem     1024-blocks      Used Available Capacity Mounted on"
  echo "/dev/vda1        100000000  50000000 ${FAUX_DF_KIO-50000000}      50% ${5:-/var/lib/docker}"
fi
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
unset CI_LOCAL_VERDICTS FINISH_LOCK_TOKEN FAUX_PASSAGE FAUX_DOCKER_ARRETE FAUX_BUILD_ECHEC FAUX_COLIMA_ARRETE DBTEST_PORT FAUX_INFO FAUX_MEM FAUX_PEAK FAUX_UNAME CLAUDECODE FAUX_DF_KIO FAUX_DF_ECHEC FAUX_IMAGES_UTILISEES FAUX_TAGS_EXTRA FAUX_IMAGES_ECHEC

# Image de la base du dépôt de l'outil (change ci-local-base-image-from-tree) : valeur par défaut du docker-compose.yml des dépôts de test.
image_outil=$(grep -E '^[[:space:]]+image:' "$racine/docker-compose.yml" | head -1 | sed -E 's/^[[:space:]]+image:[[:space:]]*//; s/["[:space:]]//g')

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
    # change ci-local-base-image-from-tree : l'image de la base est lue dans l'arbre prouvé, qui doit donc porter son docker-compose.yml
    printf 'services:\n  db:\n    image: %s\n' "$image_outil" > docker-compose.yml   # même image que le dépôt de l'outil par défaut : les cas existants restent inchangés
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
verifie "ci_local : aucune image de la clé, code 5, phrase, aucun conteneur" "$([ $code -eq 5 ] && grep -qxF "ci_local : image absente ou périmée pour cet arbre (lancer : cd $(cd "$depot" && git rev-parse --show-toplevel) && bash tools/ci_local.sh up)" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"

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
# Amendement R-20261101-109 (Q206) : une seule option --network par conteneur ; suites = container:<nom>-base, base = none.
cmd_s=$(printf '%s\n' "$ligne_run" | head -1); cree_s=$(grep '^docker create' "$FAUX_LOG"); nom_s0=$(printf '%s' "$cmd_s" | sed -n 's/.*--name \(pmzilla-ci-[0-9a-f]*\) .*/\1/p')
verifie "ci_local : réseau : une seule option --network, container:<nom>-base pour les suites, none pour la base ; --rm, utilisateur non root, nom au hasard, entrée sur stdin" "$([ "$(printf '%s' "$cmd_s" | grep -o -- '--network [^ ]*' | wc -l | tr -d ' ')" -eq 1 ] && [ "$(printf '%s' "$cmd_s" | grep -o -- '--network [^ ]*')" = "--network container:${nom_s0}-base" ] && [ "$(printf '%s' "$cree_s" | grep -o -- '--network [^ ]*' | wc -l | tr -d ' ')" -eq 1 ] && [ "$(printf '%s' "$cree_s" | grep -o -- '--network [^ ]*')" = "--network none" ] && printf '%s' "$ligne_run" | grep -q -- '--rm' && printf '%s' "$ligne_run" | grep -q -- '--user node' && printf '%s' "$ligne_run" | grep -Eq -- '--name pmzilla-ci-[0-9a-f]{8,}' && printf '%s' "$ligne_run" | grep -q -- ' -i '; echo $?)"
verifie "ci_local : aucun montage, volume, périphérique ni socket" "$(! printf '%s' "$ligne_run" | grep -Eq -- '(^| )(-v|--volume|--mount|--device|--privileged)( |=)|docker\.sock|--env-file'; echo $?)"
# Amendement R-20261101-109 (Q206) : quatre vérifications (valeurs de l'appelant, noms dans la ligne run, valeur témoin du mot de passe, contenu du fichier d'environnement).
verifie "ci_local : aucune valeur de l'appelant (base, DBTEST_PORT, jetons, noms sensibles) dans le create ni dans la ligne run" "$(! printf '%s\n%s' "$cree_s" "$cmd_s" | grep -Eq 'mdp-appelant-x|55999|jeton-appelant-x|faux-jeton-x|noms-x|noms-y'; echo $?)"
verifie "ci_local : ligne run : seul PMZILLA_LAB_DB_PASSWORD (sans =) parmi les PMZILLA_LAB_DB_*, et ni DBTEST_PORT, FINISH_LOCK_TOKEN, GH_TOKEN, SENSITIVE ni PMZILLA_NOMS" "$([ "$(printf '%s' "$cmd_s" | grep -o 'PMZILLA_LAB_DB_[A-Z_]*' | sort -u)" = PMZILLA_LAB_DB_PASSWORD ] && ! printf '%s' "$cmd_s" | grep -q 'PMZILLA_LAB_DB_PASSWORD[=]' && ! printf '%s' "$cmd_s" | grep -Eq 'DBTEST_PORT|FINISH_LOCK_TOKEN|GH_TOKEN|SENSITIVE|PMZILLA_NOMS'; echo $?)"
verifie "ci_local : valeur témoin du mot de passe de l'appelant : ni dans les arguments, ni dans le fichier d'environnement de la base, ni dans ce que reçoit le conteneur des suites" "$(! grep -qF "$faux_mdp" "$FAUX_LOG" && ! grep -qF "$faux_mdp" "$FX/envfile" && [ "$(cat "$FX/mdp-suites")" != "$faux_mdp" ] && [ -s "$FX/mdp-suites" ]; echo $?)"
verifie "ci_local : le fichier d'environnement de la base impose scram-sha-256 à initdb (hôte et socket local), sinon initdb écrit trust" "$(grep -qx 'POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256 --auth-local=scram-sha-256' "$FX/envfile"; echo $?)"
# Liste fermée étendue de POSTGRES_INITDB_ARGS (scram-sha-256, l.246) : R-20261101-130 (Q271 a).
verifie "ci_local : le fichier d'environnement de la base ne contient que POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_INITDB_ARGS et PGPORT" "$([ "$(sed 's/=.*//' "$FX/envfile" | sort | paste -sd, -)" = "PGPORT,POSTGRES_DB,POSTGRES_INITDB_ARGS,POSTGRES_PASSWORD" ]; echo $?)"
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
# R-20261101-128 : la sortie complète du passage, à côté du rapport (même nom, suffixe -sortie.txt)
sortie_pleine="${rapport%.txt}-sortie.txt"
verifie "ci_local : sortie complète : fichier à côté du rapport (même nom, suffixe -sortie.txt), droits 600, et le rapport en donne le nom" "$([ -f "$sortie_pleine" ] && [ "$(droits "$sortie_pleine")" = 600 ] && grep -qxF "sortie complète : $(basename "$sortie_pleine") (même dossier que ce rapport)" "$rapport"; echo $?)"
verifie "ci_local : sortie complète : contient le détail de l'échec du faux passage (trace de la suite en échec, chemin du conteneur compris)" "$(grep -qF 'ÉCHEC (code 1) : /home/node/arbre/tests/beta trace' "$sortie_pleine" && grep -q '^TOTAL : ' "$sortie_pleine"; echo $?)"
verifie "ci_local : sortie complète : aucune valeur témoin de secret (mot de passe de l'appelant, et mot de passe de base reçu par les suites)" "$(mdp_base_recu=$(cat "$FX/mdp-suites"); [ -n "$faux_mdp" ] && [ -n "$mdp_base_recu" ] && ! grep -qF "$faux_mdp" "$sortie_pleine" && ! grep -qF "$mdp_base_recu" "$sortie_pleine"; echo $?)"

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
verifie "ci_local : ci/Dockerfile changé depuis la construction : code 5, phrase de l'image, aucun conteneur" "$([ $code -eq 5 ] && grep -qxF "ci_local : image absente ou périmée pour cet arbre (lancer : cd $(cd "$depot" && git rev-parse --show-toplevel) && bash tools/ci_local.sh up)" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
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
verifie "ci_local : verrou npm déclaré différent de l'image : code 5, phrase npm, aucun conteneur" "$([ $code -eq 5 ] && grep -qxF "ci_local : dépendances npm de l'image différentes du verrou (lancer : cd $(cd "$depot" && git rev-parse --show-toplevel) && bash tools/ci_local.sh up)" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
# R-20261101-120 (Q237) : HEAD détaché (train) : commande sur le worktree principal, puis la ligne fixe préfixée « ci_local : » (forme npm).
git -C "$depot" checkout -q --detach
remise; lance run
verifie "ci_local (R-120, Q237) : HEAD détaché, phrase npm : commande sur le worktree principal, puis la ligne fixe" "$([ $code -eq 5 ] && [ "$(sed -n 1p "$tmp/s")" = "ci_local : dépendances npm de l'image différentes du verrou (lancer : cd $(cd "$depot" && git rev-parse --show-toplevel) && bash tools/ci_local.sh up)" ] && [ "$(sed -n 2p "$tmp/s")" = "ci_local : si une branche du train change la clé (ci/Dockerfile, verrou npm, bloc # /// script, engines.npm), construire l'image depuis le worktree de cette branche" ] && [ "$(wc -l < "$tmp/s" | tr -d ' ')" -eq 2 ]; echo $?)"
git -C "$depot" checkout -q main
remise; lance build
verifie "ci_local : build avec un verrou npm déclaré : plus de refus (la couche npm existe), construction lancée sur le faux Docker (code 0)" "$([ $code -eq 0 ] && [ "$(n_appels 'docker build')" -eq 1 ] && ! grep -q 'pas encore de couche npm' "$tmp/s"; echo $?)"
remise; lance run
verifie "ci_local : image construite pour le verrou npm déclaré : le passage a lieu (code 0)" "$([ $code -eq 0 ]; echo $?)"
printf '26.12.1\n' > "$depot/mothra/.node-version"; commit_depot "node-version"
remise; lance run
verifie "ci_local : .node-version de la suite npm ajouté : la clé change, code 5" "$([ $code -eq 5 ]; echo $?)"
construire_image
printf '# registre\n' > "$depot/mothra/.npmrc"; commit_depot "npmrc"
remise; lance run
verifie "ci_local : .npmrc de la suite npm ajouté : la clé change, code 5" "$([ $code -eq 5 ]; echo $?)"
construire_image
printf '{\n  "engines": {\n    "node": "26.12.1",\n    "npm": "12.2.1"\n  }\n}\n' > "$depot/mothra/package.json"; commit_depot "engines npm"
remise; lance run
verifie "ci_local : engines.npm de mothra/package.json ajouté : la clé change, code 5 (R-20261101-112)" "$([ $code -eq 5 ]; echo $?)"
construire_image
remise; lance run
verifie "ci_local : image construite pour engines.npm 12.2.1 : le passage a lieu (code 0)" "$([ $code -eq 0 ]; echo $?)"
printf '{\n  "engines": {\n    "node": "26.12.1",\n    "npm": "12.3.0"\n  }\n}\n' > "$depot/mothra/package.json"; commit_depot "engines npm change"
remise; lance run
# Valeur attendue alignée sur la phrase du code 5 de R-20261101-116 (Q222) et -118 (Q229), comme les trois de R-20261101-117 (l.367) :
# test venu de main au rebase (fix/ci-image-npm), même intention, aussi strict.
verifie "ci_local : engines.npm changé avec une image construite pour l'ancienne clé : code 5, phrase npm, aucun conteneur (R-20261101-112)" "$([ $code -eq 5 ] && grep -qxF "ci_local : dépendances npm de l'image différentes du verrou (lancer : cd $(cd "$depot" && git rev-parse --show-toplevel) && bash tools/ci_local.sh up)" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
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
# gel ciblé (autonomous-trains-merge, D18 points 3 et 4, tâche 6.4) : `run` suit la liste du verrou (règle unique de tools/finish_lock.py) ; build et up gardent le gel général
mkdir -p "$verrou"; echo $$ > "$verrou/pid"; date +%s > "$verrou/debut"; echo "feat/autre" > "$verrou/branche"; echo "jeton-verrou-x" > "$verrou/jeton"
printf 'B feat/autre\nW %s\nfin\n' "$tmp/ailleurs" > "$verrou/gel"
remise; lance run
verifie "ci_local : run, verrou d'une autre fin dont la liste ne nomme pas ce worktree : plus de code 7, le passage a lieu" "$([ $code -eq 0 ] && [ "$(n_appels 'docker run')" -eq 1 ]; echo $?)"
printf 'B feat/autre\nW %s\nfin\n' "$depot" > "$verrou/gel"
remise; lance run
verifie "ci_local : run dans un worktree nommé par la liste du verrou : code 7, phrase, Docker non appelé" "$([ $code -eq 7 ] && grep -qxF "ci_local : fin de branche en cours (feat/autre), lancement refusé" "$tmp/s" && [ ! -s "$FAUX_LOG" ]; echo $?)"
rm -f "$verrou/gel"
remise; lance run
verifie "ci_local : run sous un verrou sans liste lisible : code 7 (échec fermé)" "$([ $code -eq 7 ] && [ ! -s "$FAUX_LOG" ]; echo $?)"
printf 'B feat/autre\nW %s\nfin\n' "$tmp/ailleurs" > "$verrou/gel"
for sous in build up; do
  remise; lance $sous
  verifie "ci_local : $sous garde le gel général : code 7 même hors de la liste" "$([ $code -eq 7 ] && [ ! -s "$FAUX_LOG" ]; echo $?)"
done
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
verifie "ci_local : up avec Colima qui ne répond pas : colima start avec les ressources du lab, une ligne le dit" "$([ "$(n_appels 'colima start --cpu 8 --memory 16')" -eq 1 ] && grep -q "^ci_local : Colima ne répond pas" "$tmp/s"; echo $?)"
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

# --- couche npm de l'image (D10) : tests statiques sur le vrai ci/Dockerfile et sur le script (aucun Docker, aucune construction)
DOCKERFILE="$racine/ci/Dockerfile"
verifie "ci_local : ci/Dockerfile a une couche npm ci : manifestes de mothra copiés vers /opt/ci/npm/mothra, npm ci à la construction" "$(grep -Eq '^COPY .* mothra/package-lock.json .* /opt/ci/npm/mothra/$' "$DOCKERFILE" && grep -qxF ' && npm ci' "$DOCKERFILE" && grep -q 'dest=/opt/ci/npm/mothra' "$DOCKERFILE"; echo $?)"
verifie "ci_local : ci/Dockerfile ne copie que les manifestes de mothra : COPY ciblés (racine, contract, server, front), jamais tout mothra/" "$(grep -Eq '^COPY .* mothra/package.json .*mothra/\.npmr\[c\] /opt/ci/npm/mothra/$' "$DOCKERFILE" && for p in contract server front; do grep -Eq "^COPY .* mothra/$p/package.json /opt/ci/npm/mothra/$p/\$" "$DOCKERFILE" || exit 1; done && ! grep -Eq '^COPY .* mothra /opt/ci/npm' "$DOCKERFILE"; echo $?)"
verifie "ci_local : la construction vérifie que le Node de l'image est celui de mothra/.node-version, lu et non recopié" "$(grep -qF 'test "$(node --version)" = "v$(tr -d' "$DOCKERFILE" && grep -qF '"$dest/.node-version"' "$DOCKERFILE"; echo $?)"
PASSAGE="$racine/ci/passage.sh"   # le script intérieur a quitté ci_local.sh pour ci/passage.sh (D2, R-20261101-59) : ces assertions le lisent là
verifie "ci_local : le passage copie tous les dossiers node_modules de /opt/ci/npm/<dossier>, imbriqués compris" "$(grep -qF 'find . -name node_modules -type d -prune -print' "$PASSAGE" && grep -qF 'cp -a "$d/$m" "$n/$m"' "$PASSAGE"; echo $?)"
verifie "ci_local : l'image est en Node 26.12.1, égal à mothra/.node-version" "$([ "$(grep -o '^FROM node:[0-9.]*' "$DOCKERFILE")" = "FROM node:$(tr -d '[:space:]' < "$racine/mothra/.node-version")" ]; echo $?)"
verifie "ci_local : le passage copie node_modules de l'image dans l'arbre extrait, après le commit de l'archive" "$(grep -q 'cp -a "\$d/\$m" "\$n/\$m"' "$PASSAGE" && [ "$(grep -n 'ci locale"' "$PASSAGE" | head -1 | cut -d: -f1)" -lt "$(grep -n 'cp -a "\$d/\$m"' "$PASSAGE" | head -1 | cut -d: -f1)" ]; echo $?)"
verifie "ci_local : plus aucun refus de construction pour une couche npm absente" "$(! grep -q "pas encore de couche npm" "$SCRIPT"; echo $?)"

# --- ci/passage.sh (change ci-local-runner, D2, tranche 0) : script intérieur lu depuis ci/passage.sh, lancé ici avec un faux uname, un faux cat
# (pour memory.peak) et un faux arbre dont tests/run_all.sh est un faux lanceur ; aucun Docker, aucune suite réelle.
verifie "ci_local : le script intérieur est ci/passage.sh : plus de chaîne tar/commit/phase dans ci_local.sh, et le script est exécutable par bash" "$([ -f "$PASSAGE" ] && ! grep -qF 'tar -xf -' "$SCRIPT" && ! grep -qF 'getconf' "$SCRIPT" && ! grep -qF 'getconf' "$PASSAGE" && bash -n "$PASSAGE"; echo $?)"
fp="$tmp/fauxp"; mkdir -p "$fp" "$tmp/arbre-p/tests"
cat > "$fp/uname" <<'SCRIPT'
#!/bin/bash
echo "${FAUX_UNAME:-Linux}"
SCRIPT
cat > "$fp/cat" <<'SCRIPT'
#!/bin/bash
if [ "${1:-}" = /sys/fs/cgroup/memory.peak ]; then [ -n "${FAUX_PEAK:-}" ] && { echo "$FAUX_PEAK"; exit 0; }; exit 1; fi
exec /bin/cat "$@"
SCRIPT
cat > "$tmp/arbre-p/tests/run_all.sh" <<'SCRIPT'
#!/bin/bash
echo "RUN_ALL_JOBS=${RUN_ALL_JOBS:-}"
echo "ARGS=$*"
if [ "${FAUX_ROUGE:-0}" = 2 ]; then echo "run_all : option inconnue : $1" >&2; exit 2; fi
if [ "${FAUX_ROUGE:-0}" = 3 ]; then echo "alpha 3 tests · OK"; exit 0; fi
if [ "${FAUX_ROUGE:-0}" = 1 ]; then echo "TOTAL : 5 tests dans 2 suites · 1 suite(s) en échec : beta · durée totale 1,0 s"; exit 1; fi
echo "TOTAL : 5 tests dans 2 suites · tous réussis · durée totale 1,0 s"
SCRIPT
# Amendement R-20261101-109 (Q206) : arbre-p reçoit tools/dbtest.sh, tests/suites_mac.txt et les faux python3 et sleep (aucune sonde du vrai port 55432 du Mac), pour que les cas de code 0 restent verts avec la phase base.
mkdir -p "$tmp/arbre-p/tools"; cp "$racine/tools/dbtest.sh" "$tmp/arbre-p/tools/dbtest.sh"; cp "$racine/tests/suites_mac.txt" "$tmp/arbre-p/tests/suites_mac.txt"
printf '#!/bin/bash\nexit 0\n' > "$fp/python3"; printf '#!/bin/bash\nexit 0\n' > "$fp/sleep"
chmod +x "$fp/uname" "$fp/cat" "$fp/python3" "$fp/sleep"
tar -cf "$tmp/arbre-p.tar" -C "$tmp/arbre-p" tests tools
# Q269 (R-20261101-129) : faux client de la garde « base en trust » de ci/passage.sh. Par défaut il REFUSE (la base authentifie) et note le mot de passe
# faux reçu ; FAUX_TRUST=1 le fait ACCEPTER (base en trust). Posé pour tous les passages de ce fichier : aucun ne tente un vrai client.
mkdir -p "$tmp/faux-client"
cat > "$tmp/faux-client/connexion" <<'SCRIPT'
#!/bin/bash
echo "${#CI_MDP_FAUX} ${CI_MDP_FAUX}" >> "${FAUX_CONNEXIONS:-/dev/null}"
[ "${FAUX_TRUST:-0}" = 1 ] && exit 0
[ -n "${FAUX_CAUSE:-}" ] && { echo "$FAUX_CAUSE"; exit 11; }
exit 10   # refus d'authentification (28P01)
SCRIPT
chmod +x "$tmp/faux-client/connexion"
export CI_CMD_CONNEXION="$tmp/faux-client/connexion"
lance_passage() { # variables en préfixe ; HOME neuf à chaque passage ; sortie dans $tmp/sp, code dans $code
  rm -rf "$tmp/hp"; mkdir -p "$tmp/hp"
  ( cd "$tmp" && HOME="$tmp/hp" PATH="$fp:$PATH" bash "$PASSAGE" < "$tmp/arbre-p.tar" ) > "$tmp/sp" 2>&1; code=$?
}
FAUX_UNAME=Darwin lance_passage
verifie "ci_passage : sur Darwin, code 2 et la phrase de D2, aucune suite lancée, rien d'extrait" "$([ $code -eq 2 ] && [ "$(cat "$tmp/sp")" = "ci_passage : réservé au conteneur de la CI locale, rien n'est lancé" ] && [ ! -e "$tmp/hp/depot" ]; echo $?)"
FAUX_UNAME=Darwin CI_PASSAGE_CPUS=3 FAUX_PEAK=1048576 lance_passage
verifie "ci_passage : aucune variable ne lève le refus sur Darwin (CPUS et pic de mémoire posés, refus identique)" "$([ $code -eq 2 ] && ! grep -q 'phase' "$tmp/sp"; echo $?)"
CI_PASSAGE_CPUS=5 lance_passage
verifie "ci_passage : phase portable verte : code 0, ligne « phase portable : verte · <durée> s »" "$([ $code -eq 0 ] && grep -Eq '^ci_passage : phase portable : verte · [0-9]+ s$' "$tmp/sp"; echo $?)"
verifie "ci_passage : le lanceur reçoit --portable et RUN_ALL_JOBS égal aux processeurs du passage (5), pas à ceux du système" "$(grep -qx 'ARGS=--portable' "$tmp/sp" && grep -qx 'RUN_ALL_JOBS=5' "$tmp/sp"; echo $?)"
CI_PASSAGE_CPUS=3 lance_passage
verifie "ci_passage : RUN_ALL_JOBS = 3 pour des processeurs de passage égaux à 3" "$(grep -qx 'RUN_ALL_JOBS=3' "$tmp/sp"; echo $?)"
lance_passage
verifie "ci_passage : sans processeurs posés, RUN_ALL_JOBS = 1 (jamais lu dans le système du conteneur)" "$(grep -qx 'RUN_ALL_JOBS=1' "$tmp/sp"; echo $?)"
FAUX_ROUGE=1 CI_PASSAGE_CPUS=3 lance_passage
verifie "ci_passage : phase portable rouge : code du lanceur (1), ligne « rouge · <durée> s : <suites en échec> »" "$([ $code -eq 1 ] && grep -Eq '^ci_passage : phase portable : rouge · [0-9]+ s : beta$' "$tmp/sp" && ! grep -q 'phase portable : verte' "$tmp/sp"; echo $?)"
FAUX_ROUGE=2 CI_PASSAGE_CPUS=3 lance_passage
verifie "ci_passage : le lanceur de l'arbre refuse l'option : code non nul (2), phase rouge nommant le code, jamais un vert" "$([ $code -eq 2 ] && grep -Eq '^ci_passage : phase portable : rouge · [0-9]+ s : aucune ligne TOTAL du lanceur \(code 2\)$' "$tmp/sp" && ! grep -q 'phase portable : verte' "$tmp/sp"; echo $?)"
FAUX_ROUGE=3 CI_PASSAGE_CPUS=3 lance_passage
verifie "ci_passage : ligne TOTAL attendue absente et code 0 du lanceur : code 1, phase rouge, jamais un vert" "$([ $code -eq 1 ] && grep -Eq '^ci_passage : phase portable : rouge · [0-9]+ s : aucune ligne TOTAL du lanceur \(code 0\)$' "$tmp/sp" && ! grep -q 'phase portable : verte' "$tmp/sp"; echo $?)"
FAUX_PEAK=$((812 * 1048576)) CI_PASSAGE_CPUS=3 lance_passage
verifie "ci_passage : mémoire lue (memory.peak en octets) : « mémoire au plus : 812 Mio »" "$(grep -qxF 'ci_passage : mémoire au plus : 812 Mio' "$tmp/sp"; echo $?)"
CI_PASSAGE_CPUS=3 lance_passage
verifie "ci_passage : mémoire non lue : « mémoire au plus : non lue », code inchangé (0)" "$([ $code -eq 0 ] && grep -qxF 'ci_passage : mémoire au plus : non lue' "$tmp/sp"; echo $?)"
FAUX_PEAK=abc CI_PASSAGE_CPUS=3 lance_passage
verifie "ci_passage : memory.peak illisible (non numérique) : non lue" "$(grep -qxF 'ci_passage : mémoire au plus : non lue' "$tmp/sp"; echo $?)"
verifie "ci_passage : ni chemin du Mac ni nom dans les lignes de phase et de mémoire" "$(! grep -E '^ci_passage : (phase|mémoire)' "$tmp/sp" | grep -Eq "$tmp|/Users/|/home/"; echo $?)"
# Amendement R-20261101-109 (Q206) : le script ne lit aucune variable de base de l'appelant ; seules affectations et retraits écrits permis.
verifie "ci_passage : le script n'installe jamais de dépendances npm, ne lit aucune variable de base, ne pose que DBTEST_PORT=55432 PMZILLA_LAB_DB_PORT=55432 en valeurs écrites, ne retire que PMZILLA_LAB_DB_URL et PMZILLA_LAB_DB_PASSWORD, et ne nomme aucun jeton" "$(! grep -Eq '^[^#]*(npm (install|ci)|npx )' "$PASSAGE" && ! grep -Eq '\$\{?(PMZILLA_LAB_DB_|DBTEST_PORT)' "$PASSAGE" && ! grep -v 'env -u PMZILLA_LAB_DB_URL' "$PASSAGE" | grep -Eq 'PMZILLA_LAB_DB_(URL|HOST|USER)' && [ "$(grep -c 'DBTEST_PORT=55432 PMZILLA_LAB_DB_PORT=55432' "$PASSAGE")" -eq 1 ] && grep -q 'env -u PMZILLA_LAB_DB_PASSWORD' "$PASSAGE" && ! grep -Eq 'FINISH_LOCK_TOKEN|GH_TOKEN' "$PASSAGE"; echo $?)"

# --- report, derniere ligne et passage (tranche 0) : depot neuf, image de sa cle, faux Docker qui imprime des lignes de phase
nouveau_depot
: > "$FX/images"
construire_image
export CI_LOCAL_VERDICTS="$tmp/verdicts-p"; : > "$CI_LOCAL_VERDICTS"
remise; FAUX_PASSAGE=phases FAUX_INFO="8 17179869184" lance run
verifie "ci_local : passage vert avec phases lues : « phases portable » après la clé d'image dans la dernière ligne" "$([ $code -eq 0 ] && derniere | grep -Eq "^ci_local : verdict vert \(arbre ${ARBRE_MAIN:0:12}, image [0-9a-f]{12}, phases portable, 2 suites, 2 suites Mac non lancées\)$"; echo $?)"
rapport=$(ls -t "$PMZILLA_LAB_DATA/ci"/rapport-* 2>/dev/null | head -1)
verifie "ci_local : rapport : ligne de phase (verdict et durée) et ligne de mémoire" "$([ -n "$rapport" ] && grep -qxF 'phase portable : verte · 4 s' "$rapport" && grep -qxF 'mémoire au plus : 812 Mio' "$rapport"; echo $?)"
verifie "ci_local : rapport : ligne des places d'après le moteur (8 processeurs, 16 Gio) et ligne d'attente en file" "$(grep -qxF 'places : 2 (processeurs 8, mémoire 16384 Mio)' "$rapport" && grep -qxF 'attente en file : 0 s' "$rapport"; echo $?)"
verifie "ci_local : rapport : ni chemin, ni nom de branche, ni préfixe ci_passage, lisible par son propriétaire seul" "$(! grep -Eq "$tmp|$depot|/home/|ci_passage" "$rapport" && [ "$(droits "$rapport")" = 600 ]; echo $?)"
remise; FAUX_PASSAGE=phases FAUX_MEM="non lue" lance run
rapport=$(ls -t "$PMZILLA_LAB_DATA/ci"/rapport-* 2>/dev/null | head -1)
verifie "ci_local : mémoire non lue au rapport : « mémoire au plus : non lue », code 0" "$([ $code -eq 0 ] && grep -qxF 'mémoire au plus : non lue' "$rapport"; echo $?)"
verifie "ci_local : moteur sans CPU ni mémoire lisibles : rapport « places : 1 (processeurs non lus, mémoire non lue) »" "$(grep -qxF 'places : 1 (processeurs non lus, mémoire non lue)' "$rapport"; echo $?)"
remise; FAUX_PASSAGE=phases_rouge lance run
verifie "ci_local : passage rouge sans phase verte : pas de partie « phases » dans la dernière ligne" "$([ $code -eq 1 ] && derniere | grep -Eq "^ci_local : verdict rouge \(arbre ${ARBRE_MAIN:0:12}, image [0-9a-f]{12}\) : beta$"; echo $?)"
remise; lance run
ligne_run=$(sed -n '/^docker run/,/^docker rm/p' "$FAUX_LOG" | sed '$d')
verifie "ci_local : le conteneur reçoit les processeurs du passage (--cpus 3 et CI_PASSAGE_CPUS=3, posés par le script) et le texte de ci/passage.sh" "$(printf '%s' "$ligne_run" | grep -q -- '--cpus 3' && printf '%s' "$ligne_run" | grep -q -- '--env CI_PASSAGE_CPUS=3' && printf '%s' "$ligne_run" | grep -qF 'Darwin' && printf '%s' "$ligne_run" | grep -qF 'ci_passage : phase portable'; echo $?)"
remise; CI_PASSAGE_CPUS=99 lance run
ligne_run=$(sed -n '/^docker run/,/^docker rm/p' "$FAUX_LOG" | sed '$d')
verifie "ci_local : CI_PASSAGE_CPUS de l'appelant n'atteint pas le conteneur (le script pose 3)" "$(printf '%s' "$ligne_run" | grep -q -- '--env CI_PASSAGE_CPUS=3' && ! printf '%s' "$ligne_run" | grep -q '=99'; echo $?)"

# --- places [--json] (D3) : lecture seule, un seul calcul (places_calculees), la forme texte ne fait que formater le JSON
remise; FAUX_INFO="8 17179869184" lance places --json
j=$(cat "$tmp/s")
verifie "ci_local : places --json (moteur de 8 processeurs et 16 Gio) : N = 2 et les champs d'entrée, de limite, de places tenues et de file" "$([ $code -eq 0 ] && printf '%s' "$j" | grep -Eq '^\{"places":2,"processeurs":8,"memoire_mio":16384,"cpus_passage":3,"memoire_passage_mio":4096,"cpus_base":1,"memoire_base_mio":2048,"reserve_mio":3072,"preuve":\{"processeurs":4,"memoire_mio":6144\},"ciblee":\{"processeurs":2,"memoire_mio":3072\},"detenues":\[\],"libres_ciblees":4,"tenues":0,"file":0\}$'; echo $?)"   # T2 (D5, tâche 6.6) : le JSON gagne les places typées, entre reserve_mio et tenues
verifie "ci_local : places n'appelle ni run, ni create, ni start (R-20261101-93) et ne crée aucun fichier dans le dossier de données" "$(! grep -Eq '^docker (run|create|start)' "$FAUX_LOG" && [ ! -e "$PMZILLA_LAB_DATA/ci/places" ] && [ ! -e "$PMZILLA_LAB_DATA/ci/file" ]; echo $?)"
verifie "ci_local : places ne lance aucun conteneur, ne construit rien, ne retire rien et n'écrit aucun dossier de places" "$([ "$(n_appels 'docker run')" -eq 0 ] && [ "$(n_appels 'docker build')" -eq 0 ] && [ "$(n_appels 'docker rm')" -eq 0 ] && [ ! -e "$PMZILLA_LAB_DATA/ci/places" ] && [ ! -e "$PMZILLA_LAB_DATA/ci/file" ]; echo $?)"
remise; FAUX_INFO="8 17179869184" lance places
verifie "ci_local : places (texte) = le JSON formaté : même N, mêmes processeurs et mémoire" "$([ $code -eq 0 ] && grep -qxF 'ci_local : places : 2 (processeurs 8, mémoire 16384 Mio)' "$tmp/s" && grep -qxF 'ci_local : places tenues : 0, en file : 0' "$tmp/s"; echo $?)"
remise; FAUX_INFO="4 6442450944" lance places --json
verifie "ci_local : instance actuelle (4 processeurs, 6 Gio) : N = 1 (jamais moins de 1)" "$(grep -q '"places":1,"processeurs":4,"memoire_mio":6144' "$tmp/s"; echo $?)"
remise; FAUX_INFO="16 68719476736" lance places --json
verifie "ci_local : 16 processeurs et 64 Gio : N = 4, borné par les processeurs (16 / 4)" "$(grep -q '"places":4,"processeurs":16' "$tmp/s"; echo $?)"
remise; FAUX_INFO="32 12884901888" lance places --json
verifie "ci_local : 32 processeurs et 12 Gio : N = 1, borné par la mémoire ((12288 - 3072) / 6144)" "$(grep -q '"places":1,"processeurs":32,"memoire_mio":12288' "$tmp/s"; echo $?)"
remise; lance places --json
verifie "ci_local : moteur sans valeurs lisibles : N = 1 et entrées « null »" "$(grep -q '"places":1,"processeurs":null,"memoire_mio":null' "$tmp/s"; echo $?)"
# R-20261103-6 (Q4) : les processeurs d'une place sont calculés depuis le nombre de places (processeurs / N - 1 pour la base), plus écrits en dur
verifie "ci_local (Q4) : sans valeurs lisibles, la graine (3) tient lieu de processeurs du passage" "$(grep -q '"cpus_passage":3,' "$tmp/s"; echo $?)"
verifie "ci_local (Q4) : le nombre de processeurs du passage n'est plus écrit en dur (CPUS=3) : une graine pour compter les places, le reste calculé" "$(! grep -q '^CPUS=3' "$SCRIPT" && grep -qx 'CPUS_GRAINE=3' "$SCRIPT" && grep -q 'cpus_p=\$((cpu / n - CPUS_BASE))' "$SCRIPT"; echo $?)"
verifie "ci_local (Q4) : le commentaire du réglage dit le profil actuel (8 processeurs, 16 Go) et sa règle neuve dit ce qu'elle remplace et son retrait" "$(grep -qF 'Colima du lab est maintenant de 8 processeurs et 16 Go' "$SCRIPT" && grep -qF 'Remplace : « CPUS=3 » écrit en dur' "$SCRIPT" && grep -qF 'Retrait : permanent, tant que le nombre de processeurs d'"'"'une place dépend de celui du moteur.' "$SCRIPT"; echo $?)"
for cas in "8 17179869184:2:3" "16 68719476736:4:3" "4 6442450944:1:3" "32 12884901888:1:31" "2 68719476736:1:1" "12 17179869184:2:5"; do
  info=${cas%%:*}; reste=${cas#*:}; attendu_n=${reste%%:*}; attendu_c=${reste#*:}
  remise; FAUX_INFO="$info" lance places --json
  verifie "ci_local (Q4) : moteur « $info » : $attendu_n place(s), $attendu_c processeur(s) par passage (processeurs / places - 1)" "$(grep -q "\"places\":$attendu_n," "$tmp/s" && grep -q "\"cpus_passage\":$attendu_c," "$tmp/s"; echo $?)"
done
remise; FAUX_INFO="32 12884901888" lance run
ligne_run=$(sed -n '/^docker run/,/^docker rm/p' "$FAUX_LOG" | sed '$d')
verifie "ci_local (Q4) : run sur un moteur de 32 processeurs et 12 Gio (1 place) : --cpus 31 et CI_PASSAGE_CPUS=31, le calcul des places est celui qui règle le conteneur" "$(printf '%s' "$ligne_run" | grep -q -- '--cpus 31 ' && printf '%s' "$ligne_run" | grep -q -- '--env CI_PASSAGE_CPUS=31'; echo $?)"
mkdir -p "$PMZILLA_LAB_DATA/ci/places/1" "$PMZILLA_LAB_DATA/ci/places/2" "$PMZILLA_LAB_DATA/ci/file"
echo "$$" > "$PMZILLA_LAB_DATA/ci/places/1/pid"
sleep 0 & mort2=$!; wait "$mort2"; echo "$mort2" > "$PMZILLA_LAB_DATA/ci/places/2/pid"
echo "t1" > "$PMZILLA_LAB_DATA/ci/file/t1"
remise; FAUX_INFO="8 17179869184" lance places --json
verifie "ci_local : une place au pid vivant est tenue, celle au pid mort ne l'est pas ; un ticket en file est compté" "$(grep -q '"tenues":1,"file":1}' "$tmp/s"; echo $?)"
verifie "ci_local : places ne modifie ni les places ni la file (lecture seule)" "$([ -d "$PMZILLA_LAB_DATA/ci/places/2" ] && [ -f "$PMZILLA_LAB_DATA/ci/file/t1" ]; echo $?)"
rm -rf "$PMZILLA_LAB_DATA/ci/places" "$PMZILLA_LAB_DATA/ci/file"
remise; FAUX_DOCKER_ARRETE=1 lance places --json
verifie "ci_local : places avec Docker arrêté : code 3, phrase de D2" "$([ $code -eq 3 ] && grep -qxF "ci_local : Docker ne répond pas ; rien n'est lancé (colima status)" "$tmp/s"; echo $?)"
for args in "places --bidon" "places --json x"; do
  remise; lance $args
  verifie "ci_local : usage « $args » refusé (code 2, phrase de D2), aucun appel à Docker" "$([ $code -eq 2 ] && grep -qxF "ci_local : usage : bash tools/ci_local.sh run [<branche>] | build | up" "$tmp/s" && [ ! -s "$FAUX_LOG" ]; echo $?)"
done
for args in "build" "up" "up main"; do
  remise; CLAUDECODE=1 lance $args
  verifie "ci_local : « $args » en session : code 61, rien de lancé, aucun appel à Docker ni à Colima" "$([ $code -eq 61 ] && grep -q '^ci_local : lancement refusé : session' "$tmp/s" && [ ! -s "$FAUX_LOG" ]; echo $?)"
done
remise; CLAUDECODE=1 lance places --json
verifie "ci_local : places en session n'est pas refusé (lecture seule)" "$([ $code -eq 0 ]; echo $?)"
remise; CLAUDECODE=1 lance run
verifie "ci_local : run en session n'est pas refusé" "$([ $code -ne 61 ] && [ "$(n_appels 'docker run')" -eq 1 ]; echo $?)"
mkdir -p "$tmp/outil/tools"; cp "$racine/tools/ci_local.sh" "$racine/tools/finish_lock.sh" "$racine/tools/lab_paths.sh" "$tmp/outil/tools/"
remise; ( cd "$depot" && bash "$tmp/outil/tools/ci_local.sh" run ) > "$tmp/s" 2>&1; code=$?
verifie "ci_local : ci/passage.sh introuvable : code 4, phrase de D2, aucun conteneur lancé" "$([ $code -eq 4 ] && grep -qxF "ci_local : script intérieur introuvable (ci/passage.sh) ; rien n'est lancé" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
remise; lance --help
verifie "ci_local : --help nomme places" "$(grep -q 'places \[--json\]' "$tmp/s"; echo $?)"

# =================================================================================================================================
# Tranche 1 du change ci-local-runner (D1 à D3, D11 ; R-20261101-59, -73, -74, -76, -78) : deux conteneurs, phase base, places et file.
# Faux Docker : « create » garde le fichier d'environnement de la base tel qu'il est à la création, « run » garde le mot de passe reçu
# dans l'environnement du processus docker (FX/mdp-suites). Les attentes de la file se font sur de vrais processus de fond.
# =================================================================================================================================
nouveau_depot
: > "$FX/images"
construire_image
export CI_LOCAL_VERDICTS="$tmp/verdicts-t1"; : > "$CI_LOCAL_VERDICTS"
unset FAUX_BASE_ABSENTE FAUX_CREATE_ECHEC FAUX_INFO FAUX_BASE_INJOIGNABLE FAUX_PORTABLE_ROUGE FAUX_SUITES_ROUGES PMZILLA_LAB_DB_PORT PMZILLA_LAB_DB_PASSWORD
rm -rf "$PMZILLA_LAB_DATA/ci/places" "$PMZILLA_LAB_DATA/ci/file"
HOLDERS=""
tenir_place() { # <k> : la place k est tenue par un processus vivant
  local h
  mkdir -p "$PMZILLA_LAB_DATA/ci/places/$1"
  sleep 120 >/dev/null 2>&1 &
  h=$!
  echo "$h" > "$PMZILLA_LAB_DATA/ci/places/$1/pid"; HOLDERS="$HOLDERS $h"
}
lacher_places() { # tue les tenants et vide places et file
  local h
  for h in $HOLDERS; do kill "$h" 2>/dev/null; wait "$h" 2>/dev/null; done
  HOLDERS=""; rm -rf "$PMZILLA_LAB_DATA/ci/places" "$PMZILLA_LAB_DATA/ci/file" "$PMZILLA_LAB_DATA/ci/verrou-places"
}
attendre_ligne() { # <fichier> <texte fixe> <dixièmes de seconde au plus> : 0 dès que la ligne est là
  local i=0
  while [ "$i" -lt "$3" ]; do
    grep -qF -- "$2" "$1" 2>/dev/null && return 0
    sleep 0.1; i=$((i + 1))
  done
  return 1
}
attendre_fin() { # <pid> <dixièmes de seconde au plus> : le code dans $code (124 si le passage est abandonné et arrêté)
  local i=0
  while kill -0 "$1" 2>/dev/null && [ "$i" -lt "$2" ]; do sleep 0.1; i=$((i + 1)); done
  if kill -0 "$1" 2>/dev/null; then kill -TERM "$1" 2>/dev/null; wait "$1" 2>/dev/null; code=124; else wait "$1"; code=$?; fi
}
lance_borne() { # comme lance, mais abandonné au bout de 10 s (code 124) : un passage qui attend à tort ne bloque pas le test
  ( cd "$depot" && exec bash "$SCRIPT" "$@" ) > "$tmp/s" 2>&1 &
  attendre_fin "$!" 100
}
retraits_ok() { # les suites sont retirées, puis la base (avec son volume), dans cet ordre
  local l1 l2
  l1=$(grep -n '^docker rm -f pmzilla-ci-[0-9a-f]*$' "$FAUX_LOG" | head -1 | cut -d: -f1)
  l2=$(grep -n '^docker rm -f -v pmzilla-ci-[0-9a-f]*-base$' "$FAUX_LOG" | head -1 | cut -d: -f1)
  [ -n "$l1" ] && [ -n "$l2" ] && [ "$l1" -lt "$l2" ]
}

# --- D1 : deux conteneurs, aucun réseau, aucun port, aucune variable de l'appelant, mot de passe hors des arguments
remise; rm -f "$FX"/envfile* "$FX/mdp-suites"
PMZILLA_LAB_DB_PASSWORD="$faux_mdp" DBTEST_PORT=55999 PMZILLA_LAB_DB_PORT=55998 GH_TOKEN=faux-jeton-x lance run
cree=$(grep '^docker create' "$FAUX_LOG")
ligne_run=$(sed -n '/^docker run/,/^docker rm/p' "$FAUX_LOG" | sed '$d')
nom_s=$(printf '%s\n' "$ligne_run" | sed -n 's/.*--name \(pmzilla-ci-[0-9a-f]*\) .*/\1/p' | head -1)
mdp_b=$(sed -n 's/^POSTGRES_PASSWORD=//p' "$FX/envfile" 2>/dev/null)
img_compose=$(grep -E '^[[:space:]]+image:' "$racine/docker-compose.yml" | head -1 | sed -E 's/^[[:space:]]+image:[[:space:]]*//; s/["[:space:]]//g')
verifie "ci_local : deux conteneurs : une création et un démarrage de la base, un seul docker run (les suites), code 0" "$([ $code -eq 0 ] && [ "$(n_appels 'docker create')" -eq 1 ] && [ "$(n_appels 'docker start')" -eq 1 ] && [ "$(n_appels 'docker run')" -eq 1 ] && [ -n "$nom_s" ]; echo $?)"
verifie "ci_local : base : <suites>-base, --network none, --tmpfs, --shm-size 1g, --cpus 1, --memory 2048m, port 55432, image de docker-compose.yml (une seule source)" "$(printf '%s' "$cree" | grep -qF -- "--name ${nom_s}-base" && printf '%s' "$cree" | grep -qF -- '--network none' && printf '%s' "$cree" | grep -qF -- '--tmpfs ' && printf '%s' "$cree" | grep -qF -- '--shm-size 1g' && printf '%s' "$cree" | grep -qF -- '--cpus 1 ' && printf '%s' "$cree" | grep -qF -- '--memory 2048m' && printf '%s' "$cree" | grep -qF -- " $img_compose" && grep -qx 'PGPORT=55432' "$FX/envfile" && printf '%s' "$cree" | grep -qF -- '--label pmzilla-lab-ci=1' && [ -n "$img_compose" ]; echo $?)"
cmd_run=$(printf '%s\n' "$ligne_run" | head -1)   # la commande docker run seule (le texte du script intérieur, plus bas, contient « mkdir -p »)
verifie "ci_local : aucun port publié, aucun montage, volume, périphérique ni socket, dans la base comme dans les suites" "$(! printf '%s\n%s' "$cree" "$cmd_run" | grep -Eq -- '(^| )(-p|-P|--publish|--publish-all|-v|--volume|--mount|--device|--privileged)( |=)|docker\.sock'; echo $?)"
verifie "ci_local : les suites partagent la boucle locale de la base (--network container:<base>), aucun réseau Docker créé" "$(printf '%s' "$ligne_run" | grep -qF -- "--network container:${nom_s}-base" && ! printf '%s' "$ligne_run" | grep -qF -- '--network none' && ! grep -q '^docker network' "$FAUX_LOG"; echo $?)"
verifie "ci_local : mot de passe de la base : dans un fichier d'environnement de droits 600 à la création, retiré aussitôt" "$([ -n "$mdp_b" ] && [ "${#mdp_b}" -ge 16 ] && [ "$(cat "$FX/envfile.mode")" = 600 ] && [ ! -e "$(cat "$FX/envfile.chemin")" ]; echo $?)"
verifie "ci_local : mot de passe jamais dans un argument enregistré ni dans la sortie ; les suites le reçoivent par l'environnement du processus docker (--env sans valeur)" "$(! grep -qF "$mdp_b" "$FAUX_LOG" && ! grep -qF "$mdp_b" "$tmp/s" && printf '%s' "$ligne_run" | grep -q -- '--env PMZILLA_LAB_DB_PASSWORD ' && [ "$(cat "$FX/mdp-suites")" = "$mdp_b" ]; echo $?)"
verifie "ci_local : rien de l'appelant n'atteint un conteneur (mot de passe, ports, jeton) : ni valeur, et le mot de passe reçu est celui de la base du passage" "$(! printf '%s\n%s' "$cree" "$ligne_run" | grep -Eq 'mdp-appelant-x|55999|55998|faux-jeton-x' && [ "$(cat "$FX/mdp-suites")" != "$faux_mdp" ]; echo $?)"
verifie "ci_local : fin verte : les suites sont retirées, puis la base" "$(retraits_ok; echo $?)"
remise; FAUX_PASSAGE=rouge lance run
verifie "ci_local : fin rouge : les suites sont retirées, puis la base" "$([ $code -eq 1 ] && retraits_ok; echo $?)"
remise; FAUX_PASSAGE=interrompre lance_relais run
verifie "ci_local : interruption (INT) : code 130, les suites puis la base retirées, aucune place gardée" "$([ $code -eq 130 ] && retraits_ok && [ -z "$(ls "$PMZILLA_LAB_DATA/ci/places" 2>/dev/null)" ]; echo $?)"
remise; FAUX_CREATE_ECHEC=1 lance run
verifie "ci_local : base non créée : code 1, phrase, aucun conteneur de suites, base retirée, place rendue" "$([ $code -eq 1 ] && grep -qxF "ci_local : base du conteneur non démarrée ; rien n'est lancé" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ] && grep -q '^docker rm -f -v pmzilla-ci-[0-9a-f]*-base$' "$FAUX_LOG" && [ -z "$(ls "$PMZILLA_LAB_DATA/ci/places" 2>/dev/null)" ]; echo $?)"
unset FAUX_CREATE_ECHEC

# --- Revue a posteriori de 4.1 (R-20261105-12) : TERM au seul script pendant le tube du passage ou du rejeu, TERM pendant « docker create »
attendre_marque() { # <fichier> <dixièmes de seconde au plus> : 0 dès que le fichier existe
  local i=0
  while [ ! -e "$1" ] && [ "$i" -lt "$2" ]; do sleep 0.1; i=$((i + 1)); done
  [ -e "$1" ]
}
remise; rm -f "$FX/run-en-cours" "$FX/run-fini" "$FX/run.pid"
( cd "$depot" && exec env FAUX_PASSAGE=long bash "$SCRIPT" run ) > "$tmp/sq" 2>&1 &
q=$!
attendre_marque "$FX/run-en-cours" 100; vu=$?
kill -TERM "$q" 2>/dev/null
attendre_fin "$q" 150
verifie "ci_local : TERM au seul script pendant le docker run du passage : code 143, les suites puis la base retirées AVANT la fin naturelle du faux run, place rendue" "$([ "$vu" -eq 0 ] && [ $code -eq 143 ] && [ ! -e "$FX/run-fini" ] && retraits_ok && [ -z "$(ls "$PMZILLA_LAB_DATA/ci/places" 2>/dev/null)" ]; echo $?)"
remise; rm -f "$FX/run-en-cours" "$FX/run-fini" "$FX/run.pid"
( cd "$depot" && exec env FAUX_PASSAGE=long bash "$SCRIPT" run --rejeu portable alpha ) > "$tmp/sq" 2>&1 &
q=$!
attendre_marque "$FX/run-en-cours" 100; vu=$?
kill -TERM "$q" 2>/dev/null
attendre_fin "$q" 150
verifie "ci_local : TERM au seul script pendant le docker run du rejeu : code 143, le conteneur retiré AVANT la fin naturelle du faux run, place rendue" "$([ "$vu" -eq 0 ] && [ $code -eq 143 ] && [ ! -e "$FX/run-fini" ] && grep -q '^docker rm -f pmzilla-ci-[0-9a-f]*$' "$FAUX_LOG" && [ -z "$(ls "$PMZILLA_LAB_DATA/ci/places" 2>/dev/null)" ] && [ -z "$(ls "$PMZILLA_LAB_DATA/ci/file" 2>/dev/null)" ]; echo $?)"
sleep 6   # laisse finir les restes du faux run avant la suite
for sig in TERM; do   # INT est ignoré par un script lancé en arrière-plan sans contrôle de tâches (hérité) : TERM seul ici
  remise; rm -f "$FX/create-en-cours" "$FX/create.pid" "$TMPDIR"/ci_local_base.*
  ( cd "$depot" && exec env FAUX_CREATE_LONG=1 bash "$SCRIPT" run ) > "$tmp/sq" 2>&1 &
  q=$!
  attendre_marque "$FX/create-en-cours" 100; vu=$?
  kill -"$sig" "$q" 2>/dev/null
  kill -TERM "$(cat "$FX/create.pid" 2>/dev/null)" 2>/dev/null   # le faux client « docker create » s'arrête avec le script, comme sur un Ctrl-C
  attendre_fin "$q" 150
  restes=$(ls "$TMPDIR"/ci_local_base.* 2>/dev/null | wc -l | tr -d ' ')
  verifie "ci_local : $sig pendant docker create de la base : aucun fichier d'environnement de la base ne reste dans TMPDIR, la base retirée, place rendue" "$([ "$vu" -eq 0 ] && [ $code -eq 143 ] && [ "$restes" -eq 0 ] && grep -q '^docker rm -f -v pmzilla-ci-[0-9a-f]*-base$' "$FAUX_LOG" && [ -z "$(ls "$PMZILLA_LAB_DATA/ci/places" 2>/dev/null)" ]; echo $?)"
done

# --- D11 : image de la base absente = code 5 avant tout conteneur ; jamais tirée ni construite par le script
remise; FAUX_BASE_ABSENTE=1 lance run
verifie "ci_local : image ParadeDB absente : code 5, phrase de D11, aucun docker run ni create ni pull ni build" "$([ $code -eq 5 ] && grep -qxF "ci_local : image de la base absente (à tirer par l'auteur)" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ] && [ "$(n_appels 'docker create')" -eq 0 ] && [ "$(n_appels 'docker pull')" -eq 0 ] && [ "$(n_appels 'docker build')" -eq 0 ]; echo $?)"
verifie "ci_local : le script ne tire jamais d'image (aucun pull hors commentaire)" "$(! grep -Eq '^[^#]*[[:space:]]pull([[:space:]]|$)' "$SCRIPT"; echo $?)"
remise; FAUX_BASE_ABSENTE=1 lance_borne run
verifie "ci_local : image de la base absente avec une place tenue : rendu tout de suite (jamais dans la file)" "$([ $code -eq 5 ]; echo $?)"

# --- change ci-local-base-image-from-tree (D1, D2) : l'image de la base est lue dans l'arbre prouvé, jamais dans le dépôt de l'outil
depot_avant=$depot; arbre_main_avant=$ARBRE_MAIN   # le bloc crée son propre dépôt : les cas suivants reprennent le leur
PHRASE_BASE_INTROUVABLE="ci_local : image de la base introuvable (docker-compose.yml) ; rien n'est lancé"
nouveau_depot; construire_image
printf 'services:\n  db:\n    image: exemple.invalid/base:7777\n' > "$depot/docker-compose.yml"; commit_depot "base 7777"
remise; lance run
verifie "ci_local : image de la base lue dans l'arbre prouvé : le create porte le tag de l'arbre, pas celui du dépôt de l'outil" "$([ $code -eq 0 ] && [ -n "$image_outil" ] && [ "$image_outil" != exemple.invalid/base:7777 ] && grep '^docker create' "$FAUX_LOG" | grep -q -- ' exemple.invalid/base:7777$' && ! grep -qF "$image_outil" "$FAUX_LOG"; echo $?)"
printf 'services:\n  db:\n    image: exemple.invalid/base:2000\n' > "$depot/docker-compose.yml"
( cd "$depot" && git checkout -q -b feat/base-2000 && git add -A && git commit -q -m "base 2000" && git checkout -q main )
remise; lance run feat/base-2000
verifie "ci_local : run <branche> depuis un checkout dont le compose diffère : la base prend le tag du sommet de la branche" "$([ $code -eq 0 ] && grep '^docker create' "$FAUX_LOG" | grep -q -- ' exemple.invalid/base:2000$' && ! grep -q 'exemple.invalid/base:7777' "$FAUX_LOG"; echo $?)"
( cd "$depot" && git checkout -q -b feat/sans-compose && git rm -q docker-compose.yml && git commit -q -m "sans compose" && git checkout -q main )
remise; lance run feat/sans-compose
verifie "ci_local : arbre prouvé sans docker-compose.yml : code 4, phrase de D2, ni run ni create (aucun repli vers le dépôt de l'outil)" "$([ $code -eq 4 ] && grep -qxF "$PHRASE_BASE_INTROUVABLE" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ] && [ "$(n_appels 'docker create')" -eq 0 ]; echo $?)"
( cd "$depot" && git checkout -q -b feat/image-illisible && printf 'services:\n  db:\n    build: .\n' > docker-compose.yml && git add -A && git commit -q -m "image illisible" && git checkout -q main )
remise; lance run feat/image-illisible
verifie "ci_local : ligne image: absente de l'arbre prouvé : code 4, phrase de D2, ni run ni create" "$([ $code -eq 4 ] && grep -qxF "$PHRASE_BASE_INTROUVABLE" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ] && [ "$(n_appels 'docker create')" -eq 0 ]; echo $?)"
( cd "$depot" && git checkout -q -b feat/image-sans-tag && printf 'services:\n  db:\n    image: sans-tag\n' > docker-compose.yml && git add -A && git commit -q -m "image sans tag" && git checkout -q main )
remise; lance run feat/image-sans-tag
verifie "ci_local : ligne image: mal formée (ni dépôt ni tag numérique) : code 4, phrase de D2, ni run ni create" "$([ $code -eq 4 ] && grep -qxF "$PHRASE_BASE_INTROUVABLE" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ] && [ "$(n_appels 'docker create')" -eq 0 ]; echo $?)"
remise; FAUX_BASE_CONNUE="$image_outil" lance run feat/base-2000
verifie "ci_local : image de l'arbre absente alors que celle du dépôt de l'outil est présente : code 5, phrase de D2, aucun create (aucun repli)" "$([ $code -eq 5 ] && grep -qxF "ci_local : image de la base absente (à tirer par l'auteur)" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ] && [ "$(n_appels 'docker create')" -eq 0 ]; echo $?)"
printf 'services:\n  db:\n    image: exemple.invalid/base:3000\n' > "$depot/docker-compose.yml"   # modifié, non commité : HEAD porte 7777
remise; lance run --travail
verifie "ci_local : run --travail complet : la base prend le tag du compose de l'arbre de travail (non commité), pas celui de HEAD" "$([ $code -eq 0 ] && grep '^docker create' "$FAUX_LOG" | grep -q -- ' exemple.invalid/base:3000$' && ! grep -q 'exemple.invalid/base:7777' "$FAUX_LOG"; echo $?)"
printf 'services:\n  db:\n    image: exemple.invalid/base:7777\n' > "$depot/docker-compose.yml"
depot=$depot_avant; ARBRE_MAIN=$arbre_main_avant

# --- D2 : ci/passage.sh, phases portable puis base (arbre : faux lanceur, vraie ligne de tools/dbtest.sh, vraie liste des suites Mac)
fq="$tmp/fauxq"; mkdir -p "$fq" "$tmp/arbre-q/tests" "$tmp/arbre-q/tools"
cat > "$fq/python3" <<'SCRIPT'
#!/bin/bash
echo sonde >> "${FAUX_SONDES:-/dev/null}"
[ "${FAUX_BASE_INJOIGNABLE:-0}" = 1 ] && exit 1
exit 0
SCRIPT
cat > "$fq/sleep" <<'SCRIPT'
#!/bin/bash
exit 0
SCRIPT
cat > "$tmp/arbre-q/tests/run_all.sh" <<'SCRIPT'
#!/bin/bash
echo "ARGS=$*"
echo "RUN_ALL_JOBS=${RUN_ALL_JOBS:-}"
echo "DBPORT=${DBTEST_PORT:-}/${PMZILLA_LAB_DB_PORT:-}"
echo "MDP=${PMZILLA_LAB_DB_PASSWORD:-absent}"
if [ "$1" = --portable ] && [ "${FAUX_PORTABLE_ROUGE:-0}" = 1 ]; then
  echo "TOTAL : 5 tests dans 2 suites · 1 suite(s) en échec : beta · durée totale 1,0 s"; exit 1
fi
case " ${FAUX_SUITES_ROUGES:-} " in
  *" $1 "*) echo "TOTAL : 1 tests dans 1 suites · 1 suite(s) en échec : $1 · durée totale 1,0 s"; exit 1 ;;
esac
echo "TOTAL : 1 tests dans 1 suites · tous réussis · durée totale 1,0 s"
SCRIPT
chmod +x "$fq/python3" "$fq/sleep"
cp "$racine/tools/dbtest.sh" "$tmp/arbre-q/tools/dbtest.sh"; cp "$racine/tests/suites_mac.txt" "$tmp/arbre-q/tests/suites_mac.txt"
tar -cf "$tmp/arbre-q.tar" -C "$tmp/arbre-q" tests tools
mkdir -p "$tmp/arbre-q0/tests"; cp "$tmp/arbre-q/tests/run_all.sh" "$tmp/arbre-q0/tests/run_all.sh"   # arbre sans tools/dbtest.sh
tar -cf "$tmp/arbre-q0.tar" -C "$tmp/arbre-q0" tests
lance_passage_q() { # <archive> ; variables en préfixe ; sortie dans $tmp/spq, sondes de la base dans $tmp/sondes, code dans $code
  rm -rf "$tmp/hp"; mkdir -p "$tmp/hp"; : > "$tmp/sondes"
  ( cd "$tmp" && HOME="$tmp/hp" FAUX_SONDES="$tmp/sondes" PATH="${PATH_AVANT:+$PATH_AVANT:}$fq:$fp:$PATH" bash "$PASSAGE" < "$1" ) > "$tmp/spq" 2>&1; code=$?
}
verifie "ci_passage : garde de dérive : la ligne par défaut de tools/dbtest.sh nomme db, mothra et posture_evals, et tests/suites_mac.txt nomme posture_evals" "$(grep -E '^SUITES_PAR_DEFAUT=\(db .*posture_evals.* mothra\)' "$racine/tools/dbtest.sh" >/dev/null && grep -q '^posture_evals:python' "$racine/tests/suites_mac.txt"; echo $?)"
verifie "ci_passage : une seule source de la liste par défaut : ci/passage.sh n'en recopie aucune suite" "$(! grep -Eq 'flow_import|flow_store|hybrid_search' "$PASSAGE"; echo $?)"
pw_q="pw-faux-q"   # valeur témoin du mot de passe de la base, posée par référence (le scanner de secrets ne lit pas une affectation par variable)
PMZILLA_LAB_DB_PASSWORD="$pw_q" CI_PASSAGE_CPUS=3 lance_passage_q "$tmp/arbre-q.tar"
nb=$(( $(grep -c '^ARGS=' "$tmp/spq") - 1 ))
verifie "ci_passage : portable puis base vertes : code 0, deux lignes de phase dans l'ordre, ligne de mémoire ensuite" "$([ $code -eq 0 ] && grep -Eq '^ci_passage : phase portable : verte · [0-9]+ s$' "$tmp/spq" && grep -Eq '^ci_passage : phase base : verte · [0-9]+ s$' "$tmp/spq" && [ "$(grep -n 'phase portable : verte' "$tmp/spq" | cut -d: -f1)" -lt "$(grep -n 'phase base : verte' "$tmp/spq" | cut -d: -f1)" ]; echo $?)"
verifie "ci_passage : la phase base lance la liste de la ligne de tools/dbtest.sh moins les suites propres au Mac (db et mothra oui, posture_evals non), et nomme celles qu'elle saute" "$(grep -qx 'ARGS=db' "$tmp/spq" && grep -qx 'ARGS=mothra' "$tmp/spq" && ! grep -qx 'ARGS=posture_evals' "$tmp/spq" && grep -Eq '^ci_passage : suites propres au Mac non lancées en phase base : [0-9]+ \(.*posture_evals' "$tmp/spq"; echo $?)"
verifie "ci_passage : la phase portable n'a ni repère ni mot de passe de base ; chaque suite de la phase base a le port 55432 posé par le script, le mot de passe du passage et les processeurs du passage" "$([ "$nb" -ge 2 ] && [ "$(grep -c '^DBPORT=/$' "$tmp/spq")" -eq 1 ] && [ "$(grep -c '^MDP=absent$' "$tmp/spq")" -eq 1 ] && [ "$(grep -c '^DBPORT=55432/55432$' "$tmp/spq")" -eq "$nb" ] && [ "$(grep -c '^MDP=pw-faux-q$' "$tmp/spq")" -eq "$nb" ] && [ "$(grep -c '^RUN_ALL_JOBS=3$' "$tmp/spq")" -eq $((nb + 1)) ]; echo $?)"
FAUX_BASE_INJOIGNABLE=1 PMZILLA_LAB_DB_PASSWORD="$pw_q" CI_PASSAGE_CPUS=3 lance_passage_q "$tmp/arbre-q.tar"
verifie "ci_passage : base injoignable au bout de 120 sondes : phrase de D2, phase base rouge, code 1, aucune suite de la phase base lancée" "$([ $code -eq 1 ] && grep -qxF 'ci_passage : base du conteneur injoignable au bout de 120 s' "$tmp/spq" && grep -Eq '^ci_passage : phase base : rouge · [0-9]+ s : base injoignable$' "$tmp/spq" && [ "$(wc -l < "$tmp/sondes" | tr -d ' ')" -eq 120 ] && [ "$(grep -c '^ARGS=' "$tmp/spq")" -eq 1 ]; echo $?)"
FAUX_PORTABLE_ROUGE=1 PMZILLA_LAB_DB_PASSWORD="$pw_q" CI_PASSAGE_CPUS=3 lance_passage_q "$tmp/arbre-q.tar"
verifie "ci_passage : phase portable rouge : la phase base est sautée (phrase de D2), la base n'est pas sondée, code 1" "$([ $code -eq 1 ] && grep -qxF 'ci_passage : phase base : sautée (phase précédente rouge)' "$tmp/spq" && [ ! -s "$tmp/sondes" ] && [ "$(grep -c '^ARGS=' "$tmp/spq")" -eq 1 ]; echo $?)"
FAUX_SUITES_ROUGES="flow_store" PMZILLA_LAB_DB_PASSWORD="$pw_q" CI_PASSAGE_CPUS=3 lance_passage_q "$tmp/arbre-q.tar"
verifie "ci_passage : une suite de la phase base en échec : phase base rouge qui la nomme, code 1, les suites suivantes sont lancées quand même" "$([ $code -eq 1 ] && grep -Eq '^ci_passage : phase base : rouge · [0-9]+ s : flow_store$' "$tmp/spq" && grep -qx 'ARGS=mothra' "$tmp/spq"; echo $?)"
PMZILLA_LAB_DB_PASSWORD="$pw_q" CI_PASSAGE_CPUS=3 lance_passage_q "$tmp/arbre-q0.tar"
verifie "ci_passage : arbre sans tools/dbtest.sh : phase base rouge et bruyante (liste introuvable), code 1, jamais un vert, base non sondée" "$([ $code -eq 1 ] && grep -Eq '^ci_passage : phase base : rouge · [0-9]+ s : liste par défaut introuvable \(tools/dbtest\.sh\)$' "$tmp/spq" && ! grep -q 'phase base : verte' "$tmp/spq" && [ ! -s "$tmp/sondes" ]; echo $?)"
# Q269 : garde de la base en trust, en tête de la phase base (faux client : FAUX_TRUST=1 accepte la connexion, sinon la refuse)
: > "$tmp/connexions"
FAUX_CONNEXIONS="$tmp/connexions" FAUX_TRUST=1 PMZILLA_LAB_DB_PASSWORD="$pw_q" CI_PASSAGE_CPUS=3 lance_passage_q "$tmp/arbre-q.tar"
verifie "ci_passage : base en trust (le faux client accepte la connexion) : ligne exacte, phase base rouge, code 1, aucune suite de la phase base lancée (la phase portable seule)" "$([ $code -eq 1 ] && grep -qxF "ci_passage : base en trust : l'authentification n'est pas vérifiée" "$tmp/spq" && grep -Eq '^ci_passage : phase base : rouge · [0-9]+ s : base en trust$' "$tmp/spq" && ! grep -q 'phase base : verte' "$tmp/spq" && [ "$(grep -c '^ARGS=' "$tmp/spq")" -eq 1 ]; echo $?)"
verifie "ci_passage : la garde se connecte avec un mot de passe construit (jamais celui de la base du passage, jamais le même deux fois) et ne l'écrit pas dans la sortie" "$(faux=$(sed -n '1s/^[0-9]* //p' "$tmp/connexions"); [ -n "$faux" ] && [ "$faux" != "$pw_q" ] && ! grep -qF "$faux" "$tmp/spq" && [ "$(wc -l < "$tmp/connexions" | tr -d ' ')" -eq 1 ]; echo $?)"
: > "$tmp/connexions"
FAUX_CONNEXIONS="$tmp/connexions" PMZILLA_LAB_DB_PASSWORD="$pw_q" CI_PASSAGE_CPUS=3 lance_passage_q "$tmp/arbre-q.tar"
verifie "ci_passage : base qui refuse le mot de passe faux : la garde a tenté une connexion, la phase base continue et reste verte (code 0, suites lancées)" "$([ $code -eq 0 ] && [ "$(wc -l < "$tmp/connexions" | tr -d ' ')" -eq 1 ] && grep -Eq '^ci_passage : phase base : verte · [0-9]+ s$' "$tmp/spq" && ! grep -q 'base en trust' "$tmp/spq" && grep -qx 'ARGS=mothra' "$tmp/spq"; echo $?)"
verifie "ci_passage : la garde est posée après la sonde de la base et avant les suites, avec son commentaire Remplace / Retrait" "$(grep -qF 'Remplace : rien. Retrait : permanent tant que la phase base crée sa propre base.' "$PASSAGE" && [ "$(grep -n '^      garde_authentification; garde=' "$PASSAGE" | head -1 | cut -d: -f1)" -lt "$(grep -n 'for s in \$liste' "$PASSAGE" | head -1 | cut -d: -f1)" ]; echo $?)"
# Revue Opus : la garde a trois issues (trust / refus d'authentification / garde inopérante). Cas du client lui-même : le vrai texte Python de ci/passage.sh tourne
# sous un faux uv, avec un faux module psycopg (PYTHONPATH) qui joue la réponse choisie par FAUX_PSY ; FAUX_UV=absent joue un uv introuvable (code 127).
PY_REEL=$(command -v python3)   # le vrai interpréteur, pris avant que les faux python3 des passages ne soient en tête du PATH
export PY_REEL
mkdir -p "$tmp/faux-uv-garde" "$tmp/faux-psy/psycopg"
cat > "$tmp/faux-uv-garde/uv" <<'SCRIPT'
#!/bin/bash
[ "${FAUX_UV:-}" = absent ] && { echo "uv: introuvable" >&2; exit 127; }
for dernier in "$@"; do :; done
PYTHONPATH="$FAUX_PSY_DIR" exec "$PY_REEL" -c "$dernier"
SCRIPT
cat > "$tmp/faux-psy/psycopg/__init__.py" <<'SCRIPT'
import os
if os.environ.get("FAUX_PSY") == "absent":
    raise ImportError("No module named psycopg")
class OperationalError(Exception):
    def __init__(self, msg, sqlstate=None):
        super().__init__(msg)
        self.sqlstate = sqlstate
class _Connexion:
    def close(self):
        pass
def connect(**kw):
    if not kw.get("password"):
        raise RuntimeError("pas de mot de passe")
    mode = os.environ.get("FAUX_PSY", "ok")
    if mode == "ok":
        return _Connexion()
    if mode == "28P01":
        raise OperationalError("connexion refusée", "28P01")
    if mode == "message":
        raise OperationalError('connection failed: FATAL:  password authentication failed for user "postgres"', None)
    if mode == "timeout":
        raise OperationalError("timeout expired")
    raise OperationalError("connection refused")
SCRIPT
chmod +x "$tmp/faux-uv-garde/uv"
garde_py() { # <mode FAUX_PSY> [variables en préfixe] : le vrai texte Python de la garde, sous le faux uv
  PATH_AVANT="$tmp/faux-uv-garde" CI_CMD_CONNEXION= FAUX_PSY_DIR="$tmp/faux-psy" FAUX_PSY="$1" PMZILLA_LAB_DB_PASSWORD="$pw_q" CI_PASSAGE_CPUS=3 lance_passage_q "$tmp/arbre-q.tar"
}
garde_py ok
verifie "ci_passage : garde (client Python) : connexion réussie avec le mot de passe faux : base en trust, phase rouge, aucune suite" "$([ $code -eq 1 ] && grep -qxF "ci_passage : base en trust : l'authentification n'est pas vérifiée" "$tmp/spq" && [ "$(grep -c '^ARGS=' "$tmp/spq")" -eq 1 ]; echo $?)"
garde_py 28P01
verifie "ci_passage : garde (client Python) : refus SQLSTATE 28P01 : authentification vérifiée, la phase base continue (verte)" "$([ $code -eq 0 ] && grep -Eq '^ci_passage : phase base : verte · [0-9]+ s$' "$tmp/spq" && ! grep -q 'inopérante\|en trust' "$tmp/spq"; echo $?)"
garde_py message
verifie "ci_passage : garde (client Python) : SQLSTATE vide mais message « password authentication failed » : authentification vérifiée, la phase base continue (verte)" "$([ $code -eq 0 ] && grep -Eq '^ci_passage : phase base : verte · [0-9]+ s$' "$tmp/spq" && ! grep -q 'inopérante\|en trust' "$tmp/spq"; echo $?)"
inop="ci_passage : garde de l'authentification inopérante : "
for mode in timeout refuse; do
  garde_py "$mode"
  verifie "ci_passage : garde (client Python) : échec autre que l'authentification ($mode) : garde inopérante avec la cause courte, phase rouge, code 1, aucune suite, jamais un vert" "$([ $code -eq 1 ] && grep -qxF "${inop}OperationalError" "$tmp/spq" && grep -qF " s : garde de l'authentification inopérante : OperationalError" "$tmp/spq" && ! grep -q 'phase base : verte' "$tmp/spq" && [ "$(grep -c '^ARGS=' "$tmp/spq")" -eq 1 ]; echo $?)"
done
garde_py absent
verifie "ci_passage : garde (client Python) : psycopg absent : garde inopérante (ImportError), phase rouge, aucune suite" "$([ $code -eq 1 ] && grep -qxF "ci_passage : garde de l'authentification inopérante : ImportError" "$tmp/spq" && [ "$(grep -c '^ARGS=' "$tmp/spq")" -eq 1 ]; echo $?)"
FAUX_UV=absent garde_py ok
verifie "ci_passage : garde : uv absent (code 127) : garde inopérante avec le code, phase rouge, aucune suite" "$([ $code -eq 1 ] && grep -qxF "ci_passage : garde de l'authentification inopérante : client terminé avec le code 127" "$tmp/spq" && [ "$(grep -c '^ARGS=' "$tmp/spq")" -eq 1 ]; echo $?)"
FAUX_CAUSE="plantage du client" PMZILLA_LAB_DB_PASSWORD="$pw_q" CI_PASSAGE_CPUS=3 lance_passage_q "$tmp/arbre-q.tar"
verifie "ci_passage : garde : le client de test rend une autre erreur (code 11) : garde inopérante avec sa cause, aucune suite" "$([ $code -eq 1 ] && grep -qxF "ci_passage : garde de l'authentification inopérante : plantage du client" "$tmp/spq" && [ "$(grep -c '^ARGS=' "$tmp/spq")" -eq 1 ]; echo $?)"
verifie "ci_passage : garde : le mot de passe de la base du passage n'est jamais dans la sortie du passage" "$(! grep -qF "$pw_q" "$tmp/spq"; echo $?)"

# Couverture du serveur de Mothra en phase base (R-20261102-74) : arbre avec mothra/server, faux npm (journal des appels, code et sortie choisis)
mkdir -p "$tmp/arbre-c" "$tmp/fauxnpm-c"
cp -R "$tmp/arbre-q/tests" "$tmp/arbre-q/tools" "$tmp/arbre-c/"; mkdir -p "$tmp/arbre-c/mothra/server" "$tmp/arbre-c/mothra/outils"; echo '{}' > "$tmp/arbre-c/mothra/server/package.json"
echo '{"paquets":{"server":{"provisoire":true}}}' > "$tmp/arbre-c/mothra/outils/planchers-couverture.json"   # la couverture se décide sur le plancher déclaré
tar -cf "$tmp/arbre-c.tar" -C "$tmp/arbre-c" tests tools mothra
# arbre avec le plancher du serveur déclaré mais sans mothra/server ; arbre dont le fichier des planchers ne déclare pas « server »
mkdir -p "$tmp/arbre-c2" "$tmp/arbre-c3/mothra/outils"
cp -R "$tmp/arbre-q/tests" "$tmp/arbre-q/tools" "$tmp/arbre-c2/"; cp -R "$tmp/arbre-q/tests" "$tmp/arbre-q/tools" "$tmp/arbre-c3/"
mkdir -p "$tmp/arbre-c2/mothra/outils"; cp "$tmp/arbre-c/mothra/outils/planchers-couverture.json" "$tmp/arbre-c2/mothra/outils/"
echo '{"paquets":{"contract":{"provisoire":false}}}' > "$tmp/arbre-c3/mothra/outils/planchers-couverture.json"; mkdir -p "$tmp/arbre-c3/mothra/server"; echo '{}' > "$tmp/arbre-c3/mothra/server/package.json"
tar -cf "$tmp/arbre-c2.tar" -C "$tmp/arbre-c2" tests tools mothra; tar -cf "$tmp/arbre-c3.tar" -C "$tmp/arbre-c3" tests tools mothra
cat > "$tmp/fauxnpm-c/npm" <<'SCRIPT'
#!/bin/bash
echo "NPM|$*|$PWD|${DBTEST_PORT:-}/${PMZILLA_LAB_DB_PORT:-}|${PMZILLA_LAB_DB_PASSWORD:-absent}|${PMZILLA_LAB_DB_URL-absent}|${npm_config_offline:-}${npm_config_update_notifier:-}${npm_config_audit:-}${npm_config_fund:-}${NO_COLOR:-}|$(cat 2>/dev/null | wc -c | tr -d ' ')" >> "${FAUX_NPM_LOG:-/dev/null}"
[ "${FAUX_NPM_CODE:-0}" = 127 ] && exit 127
[ "${FAUX_NPM_CODE:-0}" = 2 ] && echo "couverture : lancement impossible (spawn node ENOENT)"
echo "ℹ skipped ${FAUX_NPM_SAUTES:-0}"
[ "${FAUX_NPM_SANS_LIGNE:-0}" = 1 ] || echo "ℹ all files                |  91.37 |    84.02 |   88.00 |"
exit "${FAUX_NPM_CODE:-0}"
SCRIPT
cat > "$tmp/fauxnpm-c/timeout" <<'SCRIPT'
#!/bin/bash
echo "TIMEOUT|$*" >> "${FAUX_NPM_LOG:-/dev/null}"
[ "${FAUX_TIMEOUT_124:-0}" = 1 ] && exit 124
shift 3
exec "$@"
SCRIPT
chmod +x "$tmp/fauxnpm-c/npm" "$tmp/fauxnpm-c/timeout"
lance_couv() { # [variables en préfixe ; ARBRE_C pour un autre arbre] : passage avec faux npm et faux timeout en tête du PATH ; journal dans $tmp/npm.log
  : > "$tmp/npm.log"
  PMZILLA_LAB_DB_URL=x FAUX_NPM_LOG="$tmp/npm.log" PATH_AVANT="$tmp/fauxnpm-c" PMZILLA_LAB_DB_PASSWORD="$pw_q" CI_PASSAGE_CPUS=3 lance_passage_q "${ARBRE_C:-$tmp/arbre-c.tar}"
}
lance_couv
verifie "ci_passage : la phase base lance npm run test:coverage dans mothra/server, une seule fois, avec le port de la base jetable et le mot de passe du passage" "$([ "$(grep -c '^NPM|' "$tmp/npm.log")" -eq 1 ] && grep -q '^NPM|run test:coverage|.*/mothra/server|55432/55432|pw-faux-q|' "$tmp/npm.log"; echo $?)"
verifie "ci_passage : la couverture retire PMZILLA_LAB_DB_URL (posée à l'appel), pose l'environnement du relais npm (hors ligne, sans mise à jour ni audit ni couleur), ferme l'entrée, et le mot de passe n'est jamais dans la sortie" "$(grep -q '^NPM|.*|pw-faux-q|absent|truefalsefalsefalse1|0$' "$tmp/npm.log" && ! grep -F "$pw_q" "$tmp/spq" | grep -vq '^MDP='; echo $?)"   # MDP= : la ligne témoin du faux run_all de l'arbre (l. 709), seule à porter le mot de passe
verifie "ci_passage : la couverture passe par timeout -k 5 1200 quand timeout existe" "$(grep -qx 'TIMEOUT|-k 5 1200 npm run test:coverage' "$tmp/npm.log"; echo $?)"
FAUX_TIMEOUT_124=1 lance_couv
verifie "ci_passage : timeout rend 124 : phase base rouge « couverture serveur (délai dépassé) », message dédié, jamais un vert" "$([ $code -eq 1 ] && grep -qxF 'ci_passage : couverture serveur : délai dépassé' "$tmp/spq" && grep -Eq '^ci_passage : phase base : rouge · [0-9]+ s : couverture serveur \(délai dépassé\)$' "$tmp/spq"; echo $?)"
FAUX_NPM_SAUTES=3 lance_couv
verifie "ci_passage : les tests sautés de la sortie sont imprimés avec la mesure (le plancher ne se fixe qu'à « sautés 0 »)" "$([ $code -eq 0 ] && grep -qxF 'ci_passage : couverture serveur : lignes 91.37, branches 84.02, sautés 3' "$tmp/spq"; echo $?)"
lance_couv
verifie "ci_passage : test:coverage code 0 (plancher provisoire ou tenu) : phase base verte, code 0, ligne de couverture lisible (lignes, branches), imprimée avant la ligne de phase" "$([ $code -eq 0 ] && grep -qxF 'ci_passage : couverture serveur : lignes 91.37, branches 84.02, sautés 0' "$tmp/spq" && grep -Eq '^ci_passage : phase base : verte · [0-9]+ s$' "$tmp/spq" && [ "$(grep -n 'couverture serveur : lignes' "$tmp/spq" | cut -d: -f1)" -lt "$(grep -n 'phase base : verte' "$tmp/spq" | cut -d: -f1)" ]; echo $?)"
FAUX_NPM_CODE=1 lance_couv
verifie "ci_passage : test:coverage code 1 (test en échec ou plancher non atteint) : phase base rouge qui nomme la couverture du serveur, code 1" "$([ $code -eq 1 ] && grep -Eq '^ci_passage : phase base : rouge · [0-9]+ s : couverture serveur \(tests en échec ou plancher non atteint\)$' "$tmp/spq" && ! grep -q 'phase base : verte' "$tmp/spq"; echo $?)"
FAUX_NPM_CODE=2 lance_couv
verifie "ci_passage : test:coverage code 2 (lancement impossible) : message dédié avec le code, phase base rouge, code 1" "$([ $code -eq 1 ] && grep -qxF 'ci_passage : couverture serveur : lancement impossible (code 2)' "$tmp/spq" && grep -Eq '^ci_passage : phase base : rouge · [0-9]+ s : couverture serveur \(lancement impossible, code 2\)$' "$tmp/spq"; echo $?)"
FAUX_NPM_CODE=127 lance_couv
verifie "ci_passage : npm absent (code 127) : lancement impossible, phase base rouge, jamais un vert" "$([ $code -eq 1 ] && grep -qxF 'ci_passage : couverture serveur : lancement impossible (code 127)' "$tmp/spq" && ! grep -q 'phase base : verte' "$tmp/spq"; echo $?)"
FAUX_NPM_SANS_LIGNE=1 lance_couv
verifie "ci_passage : test:coverage vert sans ligne « all files » : le dit, phase base verte (le code de couverture.mjs fait foi)" "$([ $code -eq 0 ] && grep -qxF 'ci_passage : couverture serveur : ligne « all files » absente de la sortie' "$tmp/spq"; echo $?)"
FAUX_SUITES_ROUGES="flow_store" lance_couv
verifie "ci_passage : une suite rouge et la couverture verte : la phase base nomme la suite seule, la couverture est quand même mesurée" "$([ $code -eq 1 ] && grep -Eq '^ci_passage : phase base : rouge · [0-9]+ s : flow_store$' "$tmp/spq" && [ "$(grep -c '^NPM|' "$tmp/npm.log")" -eq 1 ]; echo $?)"
PMZILLA_LAB_DB_PASSWORD="$pw_q" CI_PASSAGE_CPUS=3 lance_passage_q "$tmp/arbre-q.tar"
verifie "ci_passage : arbre sans fichier des planchers : couverture non lancée, dite, phase base verte (décision sur le plancher, pas sur le dossier)" "$([ $code -eq 0 ] && grep -qxF "ci_passage : couverture serveur : non lancée (aucun plancher du serveur dans l'arbre)" "$tmp/spq" && grep -Eq '^ci_passage : phase base : verte' "$tmp/spq"; echo $?)"
ARBRE_C="$tmp/arbre-c3.tar" lance_couv
verifie "ci_passage : fichier des planchers sans la clé « server » (mothra/server présent) : couverture non lancée, phase base verte, npm non appelé" "$([ $code -eq 0 ] && grep -qxF "ci_passage : couverture serveur : non lancée (aucun plancher du serveur dans l'arbre)" "$tmp/spq" && [ "$(grep -c '^NPM|' "$tmp/npm.log")" -eq 0 ]; echo $?)"
ARBRE_C="$tmp/arbre-c2.tar" lance_couv
verifie "ci_passage : plancher du serveur déclaré mais mothra/server absent : message propre, phase base rouge, code 1, npm non appelé" "$([ $code -eq 1 ] && grep -qxF 'ci_passage : couverture serveur : plancher déclaré, mothra/server absent' "$tmp/spq" && grep -Eq '^ci_passage : phase base : rouge · [0-9]+ s : couverture serveur \(plancher déclaré, mothra/server absent\)$' "$tmp/spq" && [ "$(grep -c '^NPM|' "$tmp/npm.log")" -eq 0 ]; echo $?)"
verifie "ci_passage : la couverture du serveur porte son commentaire Remplace / Retrait et vient après la boucle des suites" "$(grep -qF 'Retrait : permanent, tant que le plancher du serveur existe' "$PASSAGE" && [ "$(grep -n 'npm run test:coverage </dev/null) 2>&1' "$PASSAGE" | head -1 | cut -d: -f1)" -gt "$(grep -n 'for s in \$liste' "$PASSAGE" | head -1 | cut -d: -f1)" ]; echo $?)"

# --- D2, D5 côté ci_local : phases lues dans la sortie, TOTAL de la phase portable, rapport
remise; FAUX_PASSAGE=phases_base lance run
rapport=$(ls -t "$PMZILLA_LAB_DATA/ci"/rapport-* 2>/dev/null | head -1)
verifie "ci_local : phases portable et base vertes : « phases portable,base » dans la dernière ligne, suites comptées sur la phase portable" "$([ $code -eq 0 ] && derniere | grep -Eq "^ci_local : verdict vert \(arbre ${ARBRE_MAIN:0:12}, image [0-9a-f]{12}, phases portable,base, 2 suites, 2 suites Mac non lancées\)$"; echo $?)"
verifie "ci_local : rapport : lignes des deux phases, suites propres au Mac non lancées en phase base, mémoire" "$(grep -qxF 'phase portable : verte · 4 s' "$rapport" && grep -qxF 'phase base : verte · 9 s' "$rapport" && grep -qxF 'suites propres au Mac non lancées en phase base : 1 (posture_evals)' "$rapport" && grep -qxF 'mémoire au plus : 900 Mio' "$rapport"; echo $?)"
remise; FAUX_PASSAGE=phases_base_rouge lance run
verifie "ci_local : phase base rouge : code 1, verdict rouge qui nomme la suite et garde la phase portable verte, aucune ligne vert pour l'arbre" "$([ $code -eq 1 ] && derniere | grep -Eq "^ci_local : verdict rouge \(arbre ${ARBRE_MAIN:0:12}, image [0-9a-f]{12}, phases portable\) : flow_store$" && ! grep -q "^${ARBRE_MAIN}${TAB}vert" "$CI_LOCAL_VERDICTS"; echo $?)"

# --- D3 : places et file (vrais processus de fond pour les tenants ; moteur de 8 processeurs et 16 Gio = 2 places)
lacher_places
export FAUX_INFO="8 17179869184"
tenir_place 1; tenir_place 2
remise
( cd "$depot" && exec bash "$SCRIPT" run ) > "$tmp/sq" 2>&1 &
q=$!
attendre_ligne "$tmp/sq" 'ci_local : en file (position 1, 2 passage(s) en cours sur 2 places)' 100; vu=$?
set -- $HOLDERS; kill "$1" 2>/dev/null; wait "$1" 2>/dev/null
attendre_fin "$q" 150
verifie "ci_local : troisième passage avec deux places tenues : « en file (position 1, 2 passage(s) en cours sur 2 places) », aucun conteneur pendant l'attente" "$([ "$vu" -eq 0 ]; echo $?)"
verifie "ci_local : une place libérée : le passage attendu la prend (« place k prise, départ »), va au bout (code 0), ne refuse jamais" "$([ $code -eq 0 ] && grep -Eq '^ci_local : place [12] prise, départ$' "$tmp/sq" && [ "$(n_appels 'docker run')" -eq 1 ]; echo $?)"
rapport=$(ls -t "$PMZILLA_LAB_DATA/ci"/rapport-* 2>/dev/null | head -1)
verifie "ci_local : l'attente en file est au rapport (au moins 1 s) et le ticket a disparu" "$(grep -Eq '^attente en file : [1-9][0-9]* s$' "$rapport" && [ -z "$(ls "$PMZILLA_LAB_DATA/ci/file" 2>/dev/null)" ]; echo $?)"
lacher_places
unset FAUX_INFO
# place tenue par un processus mort : reprise sans attendre
mkdir -p "$PMZILLA_LAB_DATA/ci/places/1"; sleep 0 & mort_p=$!; wait "$mort_p"; echo "$mort_p" > "$PMZILLA_LAB_DATA/ci/places/1/pid"
remise; lance_borne run
verifie "ci_local : place au pid mort reprise sans attendre : code 0, aucune ligne de file, un conteneur de suites" "$([ $code -eq 0 ] && ! grep -q 'en file' "$tmp/s" && [ "$(n_appels 'docker run')" -eq 1 ]; echo $?)"
lacher_places
# attente interrompue : le ticket est retiré et aucun conteneur n'est démarré
tenir_place 1
remise
( cd "$depot" && exec bash "$SCRIPT" run ) > "$tmp/sq" 2>&1 &
q=$!
attendre_ligne "$tmp/sq" 'ci_local : en file (position 1, 1 passage(s) en cours sur 1 places)' 100; vu=$?
tickets_avant=$(ls "$PMZILLA_LAB_DATA/ci/file" 2>/dev/null | wc -l | tr -d ' ')
kill -TERM "$q" 2>/dev/null
attendre_fin "$q" 50
verifie "ci_local : attente interrompue (TERM) : un ticket pendant l'attente, aucun après, code 143, aucun conteneur ni création de base" "$([ "$vu" -eq 0 ] && [ "$tickets_avant" -eq 1 ] && [ $code -eq 143 ] && [ -z "$(ls "$PMZILLA_LAB_DATA/ci/file" 2>/dev/null)" ] && [ ! -d "$PMZILLA_LAB_DATA/ci/verrou-places" ] && [ "$(n_appels 'docker run')" -eq 0 ] && [ "$(n_appels 'docker create')" -eq 0 ]; echo $?)"
lacher_places
# jeton vivant du verrou de fin : le ticket du train passe devant (jamais dans une place tenue)
tenir_place 1
remise
( cd "$depot" && exec bash "$SCRIPT" run ) > "$tmp/sqa" 2>&1 &
qa=$!
attendre_ligne "$tmp/sqa" 'ci_local : en file (position 1, 1 passage(s) en cours sur 1 places)' 100; vu_a=$?
commun=$(git -C "$depot" rev-parse --path-format=absolute --git-common-dir)
verrou="$commun/pmzilla-fin-en-cours"
mkdir -p "$verrou"; echo $$ > "$verrou/pid"; date +%s > "$verrou/debut"; echo "feat/train-x" > "$verrou/branche"; echo "jeton-train-x" > "$verrou/jeton"
( cd "$depot" && exec env FINISH_LOCK_TOKEN=jeton-train-x bash "$SCRIPT" run ) > "$tmp/sqb" 2>&1 &
qb=$!
attendre_ligne "$tmp/sqb" 'ci_local : en file (position 1, 1 passage(s) en cours sur 1 places)' 100; vu_b=$?
attendre_ligne "$tmp/sqa" 'ci_local : en file (position 2, 1 passage(s) en cours sur 1 places)' 100; vu_a2=$?
verifie "ci_local : le passage qui porte le jeton vivant du verrou passe en tête de file (position 1), l'autre recule (position 2) ; la place tenue n'est pas prise" "$([ "$vu_a" -eq 0 ] && [ "$vu_b" -eq 0 ] && [ "$vu_a2" -eq 0 ] && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
set -- $HOLDERS; kill "$1" 2>/dev/null; wait "$1" 2>/dev/null
attendre_fin "$qb" 150; code_b=$code
attendre_fin "$qa" 150; code_a=$code
verifie "ci_local : les deux passages vont au bout une fois la place libre (codes 0), file vide" "$([ "$code_a" -eq 0 ] && [ "$code_b" -eq 0 ] && [ -z "$(ls "$PMZILLA_LAB_DATA/ci/file" 2>/dev/null)" ]; echo $?)"
rm -rf "$verrou"
lacher_places
# D18 point 4 : la place du train est tenue (marquée « train »), le budget en laisse une autre (2 places) : le passage de session attend quand même
export FAUX_INFO="8 17179869184"
tenir_place 1; : > "$PMZILLA_LAB_DATA/ci/places/1/train"
remise
( cd "$depot" && exec bash "$SCRIPT" run ) > "$tmp/sqt" 2>&1 &
qt=$!
attendre_ligne "$tmp/sqt" 'ci_local : en file (position 1, 1 passage(s) en cours sur 2 places)' 100; vu_t=$?
sleep 2
appels_attente=$(n_appels 'docker run')
set -- $HOLDERS; kill "$1" 2>/dev/null; wait "$1" 2>/dev/null
attendre_fin "$qt" 150
verifie "ci_local : place du train tenue avec une place libre au budget : le passage de session reste en file (position 1), aucun conteneur ; place rendue, il part (« place k prise, départ », code 0)" "$([ "$vu_t" -eq 0 ] && [ "$appels_attente" -eq 0 ] && [ $code -eq 0 ] && grep -Eq '^ci_local : place [12] prise, départ$' "$tmp/sqt"; echo $?)"
verifie "ci_local : prendre_place note « train » pour la place du passage de rang 0 et le retrait de ce marqueur suit la place (commentaire Remplace / Retrait présent)" "$(grep -qF 'PRIO_PLACE:-1' "$SCRIPT" && grep -qF 'Retrait : permanent, avec le gel ciblé' "$SCRIPT"; echo $?)"
lacher_places
unset FAUX_INFO
# codes 2 à 7 rendus avant la file, même quand toutes les places sont tenues
tenir_place 1
remise; FAUX_DOCKER_ARRETE=1 lance_borne run
verifie "ci_local : place tenue et Docker arrêté : code 3 tout de suite, aucun ticket" "$([ $code -eq 3 ] && [ -z "$(ls "$PMZILLA_LAB_DATA/ci/file" 2>/dev/null)" ]; echo $?)"
remise; lance_borne run inconnue
verifie "ci_local : place tenue et branche inconnue : code 4 tout de suite, aucun ticket" "$([ $code -eq 4 ] && [ -z "$(ls "$PMZILLA_LAB_DATA/ci/file" 2>/dev/null)" ]; echo $?)"
remise; lance_borne run --x
verifie "ci_local : place tenue et usage incorrect : code 2 tout de suite" "$([ $code -eq 2 ]; echo $?)"
mkdir -p "$verrou"; echo $$ > "$verrou/pid"; date +%s > "$verrou/debut"; echo "feat/autre-x" > "$verrou/branche"; echo "jeton-autre-x" > "$verrou/jeton"
remise; lance_borne run
verifie "ci_local : place tenue et verrou de fin d'une autre fin : code 7 tout de suite, aucun ticket" "$([ $code -eq 7 ] && [ -z "$(ls "$PMZILLA_LAB_DATA/ci/file" 2>/dev/null)" ]; echo $?)"
rm -rf "$verrou"
lacher_places

# =================================================================================================================================
# Tranche 2 du change ci-local-runner (tâches 9.1 à 9.4 ; R-20261101-113, R-20261101-116) : phase e2e dans le conteneur, étapes de tools/e2e_steps.sh
# concaténées devant ci/passage.sh, Chromium dans l'image, preuve enregistrée (D6), rejeu (Q220), phrase du code 5 avec le worktree (Q222 a).
# =================================================================================================================================
unset FAUX_INFO FAUX_BASE_ABSENTE FAUX_CREATE_ECHEC FAUX_PASSAGE FINISH_LOCK_TOKEN FAUX_DOCKER_ARRETE
nouveau_depot
: > "$FX/images"
construire_image
export CI_LOCAL_VERDICTS="$tmp/verdicts-t2"; : > "$CI_LOCAL_VERDICTS"
export CI_LOCAL_PREUVES="$tmp/preuves-t2"; : > "$CI_LOCAL_PREUVES"
wt_depot=$(cd "$depot" && git rev-parse --show-toplevel)

# --- ci/Dockerfile : Chromium de Playwright (9.3), version du verrou, lisible par node
verifie "ci/Dockerfile (tranche 2) : PLAYWRIGHT_BROWSERS_PATH hors du dossier personnel, dépendances système en root puis navigateur en node, par la CLI de l'image" "$(grep -qF 'ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ci/ms-playwright' "$DOCKERFILE" && grep -qF './node_modules/.bin/playwright install-deps chromium' "$DOCKERFILE" && grep -qF './node_modules/.bin/playwright install chromium' "$DOCKERFILE" && [ "$(grep -n '^USER root' "$DOCKERFILE" | tail -1 | cut -d: -f1)" -lt "$(grep -n 'playwright install-deps' "$DOCKERFILE" | cut -d: -f1)" ] && [ "$(grep -n 'playwright install-deps' "$DOCKERFILE" | cut -d: -f1)" -lt "$(grep -n 'playwright install chromium' "$DOCKERFILE" | cut -d: -f1)" ] && [ "$(grep '^USER ' "$DOCKERFILE" | tail -1)" = "USER node" ]; echo $?)"
verifie "ci/Dockerfile (tranche 2) : après npm ci (version de @playwright/test du verrou), jamais npx ni une version écrite ici" "$([ "$(grep -n '^ && npm ci' "$DOCKERFILE" | cut -d: -f1)" -lt "$(grep -n 'playwright install-deps' "$DOCKERFILE" | cut -d: -f1)" ] && ! grep -Eq '^[^#]*(npx |playwright@|install chromium@)' "$DOCKERFILE"; echo $?)"

# --- texte intérieur : e2e_steps.sh puis passage.sh, du dépôt de l'outil (R-94), --shm-size 1g
remise; FAUX_PASSAGE=phases_e2e lance run
ligne_run=$(sed -n '/^docker run/,/^docker rm/p' "$FAUX_LOG" | sed '$d')
cmd_s=$(printf '%s\n' "$ligne_run" | head -1)
verifie "ci_local (tranche 2) : le texte lancé est tools/e2e_steps.sh puis ci/passage.sh : les fonctions d'étapes précèdent le refus sur Darwin" "$([ $code -eq 0 ] && printf '%s' "$ligne_run" | grep -qF 'e2e_enchainer()' && [ "$(printf '%s\n' "$ligne_run" | grep -n 'e2e_enchainer()' | head -1 | cut -d: -f1)" -lt "$(printf '%s\n' "$ligne_run" | grep -n 'réservé au conteneur' | head -1 | cut -d: -f1)" ]; echo $?)"
verifie "ci_local (tranche 2) : --shm-size 1g aussi pour le conteneur des suites (Chromium), en plus de la base" "$(printf '%s' "$cmd_s" | grep -qF -- '--shm-size 1g' && grep '^docker create' "$FAUX_LOG" | grep -qF -- '--shm-size 1g'; echo $?)"
mkdir -p "$tmp/outil2/tools" "$tmp/outil2/ci"; cp "$racine/tools/ci_local.sh" "$racine/tools/finish_lock.sh" "$racine/tools/lab_paths.sh" "$tmp/outil2/tools/"; cp "$racine/ci/passage.sh" "$tmp/outil2/ci/"
remise; ( cd "$depot" && bash "$tmp/outil2/tools/ci_local.sh" run ) > "$tmp/s" 2>&1; code=$?
verifie "ci_local (tranche 2) : tools/e2e_steps.sh absent du dépôt de l'outil : code 4, phrase, aucun conteneur" "$([ $code -eq 4 ] && grep -qxF "ci_local : script intérieur introuvable (tools/e2e_steps.sh) ; rien n'est lancé" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ] && [ "$(n_appels 'docker create')" -eq 0 ]; echo $?)"
nouveau_depot
mkdir -p "$depot/tools"; echo '# MARQUEUR_ARBRE_TESTE_E2E' > "$depot/tools/e2e_steps.sh"; commit_depot "etapes de l'arbre testé"
construire_image
remise; FAUX_PASSAGE=phases_e2e lance run
verifie "ci_local (tranche 2) : un tools/e2e_steps.sh de l'arbre testé n'est jamais lu (R-94) : le texte lancé est celui du dépôt de l'outil" "$([ $code -eq 0 ] && ! grep -qF 'MARQUEUR_ARBRE_TESTE_E2E' "$FAUX_LOG" && grep -qF 'e2e_enchainer()' "$FAUX_LOG"; echo $?)"

# --- code 5 : la commande exacte de construction depuis le worktree de l'arbre (R-20261101-116, Q222 a)
nouveau_depot
wt_depot=$(cd "$depot" && git rev-parse --show-toplevel)
: > "$FX/images"
remise; lance run
verifie "ci_local (tranche 2) : image absente : la phrase donne « cd <worktree> && bash tools/ci_local.sh up » avec le dossier de l'arbre testé" "$([ $code -eq 5 ] && grep -qxF "ci_local : image absente ou périmée pour cet arbre (lancer : cd $wt_depot && bash tools/ci_local.sh up)" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
# R-20261101-118 (Q229 a) : la phrase du code 5 nomme le worktree RÉEL de la branche visée (git worktree list --porcelain), non le dépôt courant ;
# sans worktree pour cette branche, elle donne git worktree add <chemin> <branche> avec le chemin de la convention de tools/worktree.sh.
# Les valeurs attendues qui suivent la phrase (l. 210, 331, 367, 806, 971) restent vraies sans changement : la branche visée y est main,
# ouverte dans le dépôt courant. Remplace : rien. Retrait : permanent.
git -C "$depot" branch feat/avec-worktree
git -C "$depot" worktree add -q "$tmp/wt-avec" feat/avec-worktree
git -C "$depot" branch feat/sans-worktree
wt_avec=$(git -C "$tmp/wt-avec" rev-parse --show-toplevel)
remise; lance run feat/avec-worktree
verifie "ci_local (R-118, Q229 a) : branche visée ouverte dans un autre worktree : la phrase nomme ce worktree, non le dépôt courant" "$([ $code -eq 5 ] && grep -qxF "ci_local : image absente ou périmée pour cet arbre (lancer : cd $wt_avec && bash tools/ci_local.sh up)" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
remise; PMZILLA_LAB_WORKTREES="$tmp/wts-q229" lance run feat/sans-worktree
verifie "ci_local (R-118, Q229 a) : branche sans worktree : la phrase donne git worktree add <chemin> <branche> puis cd, chemin wt-<branche avec / remplacé par ->" "$([ $code -eq 5 ] && grep -qxF "ci_local : image absente ou périmée pour cet arbre (lancer : git worktree add $tmp/wts-q229/wt-feat-sans-worktree feat/sans-worktree && cd $tmp/wts-q229/wt-feat-sans-worktree && bash tools/ci_local.sh up)" "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ] && [ ! -e "$tmp/wts-q229" ]; echo $?)"
git -C "$depot" branch 'a;b'
remise; PMZILLA_LAB_WORKTREES="$tmp/wts-q229" lance run 'a;b'
verifie "ci_local (R-118, revue) : branche « a;b » sans worktree : nom et chemins cités par printf %q (a\\;b), jamais un ; nu" "$([ $code -eq 5 ] && grep -qF 'git worktree add '"$tmp"'/wts-q229/wt-a\;b a\;b && cd '"$tmp"'/wts-q229/wt-a\;b && bash tools/ci_local.sh up)' "$tmp/s"; echo $?)"
# R-20261101-120 (Q237) : HEAD détaché (train) : commande sur le worktree principal, puis la ligne fixe préfixée « ci_local : » (image absente).
git -C "$depot" checkout -q --detach
remise; lance run
verifie "ci_local (R-120, Q237) : HEAD détaché, image absente : commande sur le worktree principal, puis la ligne fixe" "$([ $code -eq 5 ] && [ "$(sed -n 1p "$tmp/s")" = "ci_local : image absente ou périmée pour cet arbre (lancer : cd $wt_depot && bash tools/ci_local.sh up)" ] && [ "$(sed -n 2p "$tmp/s")" = "ci_local : si une branche du train change la clé (ci/Dockerfile, verrou npm, bloc # /// script, engines.npm), construire l'image depuis le worktree de cette branche" ] && [ "$(wc -l < "$tmp/s" | tr -d ' ')" -eq 2 ]; echo $?)"
git -C "$depot" checkout -q main
construire_image

# --- ci/passage.sh : phase e2e (9.1, 9.3), avec les VRAIES étapes de tools/e2e_steps.sh et de faux uv, npm, node, sonde et passe
fe="$tmp/fauxe"; mkdir -p "$fe"
cat > "$fe/uv" <<'SCRIPT'
#!/bin/bash
echo "uv $*" >> "$FX/uv-args"
case "$*" in
  *"tools/db.py migrate"*) echo migrer >> "$FX/ordre"; echo "port=${DBTEST_PORT:-absente} pw_longueur=${#PMZILLA_LAB_DB_PASSWORD}" > "$FX/migrer-env"; exit "${FAUX_MIGRER_CODE:-0}" ;;
  *jeu_synthetique.py*) echo chargeur >> "$FX/ordre"; echo "port=${DBTEST_PORT:-absente} pw_longueur=${#PMZILLA_LAB_DB_PASSWORD}" > "$FX/chargeur-env"; exit "${FAUX_CHARGEUR_CODE:-0}" ;;
  *" -c "*)
    n=$(( $(cat "$FX/sql-n" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$FX/sql-n"
    cat >> "$FX/sql-recu"
    echo sql >> "$FX/ordre"; echo "pw_longueur=${#PMZILLA_LAB_DB_PASSWORD} port=${DBTEST_PORT:-absente}" >> "$FX/sql-env"
    [ "$n" = "${FAUX_SQL_KO:-0}" ] && exit 1
    exit 0 ;;
esac
exit 0
SCRIPT
cat > "$fe/npm" <<'SCRIPT'
#!/bin/bash
echo build >> "$FX/ordre"
echo "cwd=$(basename "$PWD") args=$* mothra=$(compgen -v MOTHRA_ | sort | tr '\n' ',') base=$(compgen -v PMZILLA_LAB_DB_ | sort | tr '\n' ',')" > "$FX/build-env"
exit "${FAUX_BUILD_CODE:-0}"
SCRIPT
cat > "$fe/node" <<'SCRIPT'
#!/bin/bash
echo serveur >> "$FX/ordre"
echo "pid=$$ cwd=$(basename "$PWD") jeu=${MOTHRA_DATASET-absent} port=${MOTHRA_PORT:-} base=${DBTEST_PORT:-} vues_longueur=${#PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS} stockage_longueur=${#PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA} superutilisateur=${PMZILLA_LAB_DB_PASSWORD-absent}" > "$FX/serveur-env"
echo "VUES=${PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS:-}" > "$FX/serveur-secret"
echo "STOCKAGE=${PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA:-}" > "$FX/serveur-secret-stockage"
[ "${FAUX_SERVEUR_SORT:-0}" = 1 ] && exit 0
while :; do /bin/sleep 1; done
SCRIPT
cat > "$fe/sonde" <<'SCRIPT'
#!/bin/bash
echo "sonde $1" >> "$FX/sondes"
[ "${FAUX_SONDE_KO:-0}" = 1 ] && exit 1
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
  [ -s "$FX/serveur-env" ] && exit 0
  /bin/sleep 0.1
done
exit 1
SCRIPT
chmod +x "$fe/uv" "$fe/npm" "$fe/node" "$fe/sonde"
rm -rf "$tmp/arbre-e"; mkdir -p "$tmp/arbre-e"; cp -R "$tmp/arbre-q/." "$tmp/arbre-e/"
mkdir -p "$tmp/arbre-e/mothra/server" "$tmp/arbre-e/tests/e2e"; : > "$tmp/arbre-e/mothra/server/.gitkeep"
: > "$tmp/arbre-e/tests/e2e/exemple.spec.ts"   # R-20261103-6 (Q1) : une spécification de bout en bout dans l'arbre, sans quoi la phase e2e est « sans objet »
# Faux run_all propre au scénario e2e (le partagé, copié de arbre-q, imprime le mot de passe pour le test de la phase base et reste tel quel) :
# il n'imprime que la longueur du mot de passe reçu, pour que le contrôle « aucun secret dans la sortie » garde son grep entier.
cat > "$tmp/arbre-e/tests/run_all.sh" <<'SCRIPT'
#!/bin/bash
echo "ARGS=$*"
echo "RUN_ALL_JOBS=${RUN_ALL_JOBS:-}"
echo "DBPORT=${DBTEST_PORT:-}/${PMZILLA_LAB_DB_PORT:-}"
echo "MDP_LONGUEUR=${#PMZILLA_LAB_DB_PASSWORD}"
if [ "$1" = --portable ] && [ "${FAUX_PORTABLE_ROUGE:-0}" = 1 ]; then
  echo "TOTAL : 5 tests dans 2 suites · 1 suite(s) en échec : beta · durée totale 1,0 s"; exit 1
fi
case " ${FAUX_SUITES_ROUGES:-} " in
  *" $1 "*) echo "TOTAL : 1 tests dans 1 suites · 1 suite(s) en échec : $1 · durée totale 1,0 s"; exit 1 ;;
esac
echo "TOTAL : 1 tests dans 1 suites · tous réussis · durée totale 1,0 s"
SCRIPT
cat > "$tmp/arbre-e/tests/run_e2e.sh" <<'SCRIPT'
#!/bin/bash
echo passe >> "$FX/ordre"
echo "port=${DBTEST_PORT:-absente} url=${MOTHRA_E2E_URL:-absente} superutilisateur=${PMZILLA_LAB_DB_PASSWORD-absent}" > "$FX/passe-env"
# Ligne de fin du rapporteur « line » de Playwright (R-20261103-6, Q1) : FAUX_PASSE_SORTIE la remplace, vide = rien d'imprimé
printf '%s\n' "${FAUX_PASSE_SORTIE-  7 passed (3s)}"
exit "${FAUX_PASSE_CODE:-0}"
SCRIPT
tar -cf "$tmp/arbre-e.tar" -C "$tmp/arbre-e" tests tools mothra
rm -rf "$tmp/arbre-e-sans"; mkdir -p "$tmp/arbre-e-sans"; cp -R "$tmp/arbre-e/." "$tmp/arbre-e-sans/"; rm -rf "$tmp/arbre-e-sans/tests/e2e"   # sans aucune spécification
tar -cf "$tmp/arbre-e-sans.tar" -C "$tmp/arbre-e-sans" tests tools mothra
cat "$racine/tools/e2e_steps.sh" "$PASSAGE" > "$tmp/interieur-e.sh"   # ce que ci_local lance : les étapes, puis passage.sh
mkdir -p "$tmp/navigateurs/chromium-1234" "$tmp/sans-navigateur"
pw_e="pw-faux-e"   # valeur témoin du mot de passe de la base, posée par référence
lance_passage_e() { # <archive> ; variables en préfixe ; sortie dans $tmp/spe, code dans $code
  rm -rf "$tmp/hp"; mkdir -p "$tmp/hp"
  rm -f "$FX/ordre" "$FX/sql-recu" "$FX/sql-env" "$FX/sql-n" "$FX/uv-args" "$FX/serveur-env" "$FX/serveur-secret" "$FX/serveur-secret-stockage" "$FX/passe-env" "$FX/build-env" "$FX/sondes" "$FX/migrer-env" "$FX/chargeur-env"
  ( cd "$tmp" && HOME="$tmp/hp" FAUX_SONDES="$tmp/sondes" E2E_CMD_SONDE="$fe/sonde" PATH="$fe:$fq:$fp:$PATH" PMZILLA_LAB_DB_PASSWORD="$pw_e" CI_PASSAGE_CPUS=3 bash "$tmp/interieur-e.sh" < "$1" ) > "$tmp/spe" 2>&1; code=$?
}
ordre_e() { tr '\n' ' ' < "$FX/ordre" 2>/dev/null; }
rouge_e() { # <cause> : la ligne rouge de la phase e2e, code 1, jamais de ligne verte pour elle
  [ "$code" -eq 1 ] && grep -Eq "^ci_passage : phase e2e : rouge · [0-9]+ s : $1\$" "$tmp/spe" && ! grep -q 'phase e2e : verte' "$tmp/spe"
}
export PLAYWRIGHT_BROWSERS_PATH="$tmp/navigateurs"
lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e : trois phases vertes : code 0, lignes portable, base puis e2e dans cet ordre" "$([ $code -eq 0 ] && grep -Eq '^ci_passage : phase e2e : verte · 7 tests · [0-9]+ s$' "$tmp/spe" && [ "$(grep -n 'phase portable : verte' "$tmp/spe" | cut -d: -f1)" -lt "$(grep -n 'phase base : verte' "$tmp/spe" | cut -d: -f1)" ] && [ "$(grep -n 'phase base : verte' "$tmp/spe" | cut -d: -f1)" -lt "$(grep -n 'phase e2e : verte' "$tmp/spe" | cut -d: -f1)" ]; echo $?)"
verifie "ci_passage e2e : ordre des étapes : migrations, jeu synthétique, deux rôles, construction du bundle, serveur, passe" "$([ "$(ordre_e)" = "migrer chargeur sql sql build serveur passe " ]; echo $?)"
attendu_seuils="SET ROLE pmzilla_mothra; INSERT INTO mothra.threshold_history (threshold_code, value, set_on, set_by) VALUES ('sample_median_min_items', 5, DATE '2026-10-27', 'author-1'), ('sample_p85_min_items', 20, DATE '2026-10-27', 'author-1'); RESET ROLE;"
# Q270 (R-20261101-129) : les deux seuils d'échantillon sont posés par l'appel SQL du rôle de stockage, sous ce rôle (la fonction SQL de la base jetable du passage)
# Valeur de la médiane : 5 (R-20261102-5, Q281 (a) : plancher de masquage, tailles du jeu synthétique 5, 5, 9 et 5), qui remplace 10 (Q270)
verifie "ci_passage e2e : seuils d'échantillon : une ligne datée par seuil (5 et 20) dans mothra.threshold_history, posée après SET ROLE pmzilla_mothra, dans l'appel du rôle de stockage" "$(grep 'pmzilla_mothra LOGIN PASSWORD' "$FX/sql-recu" | grep -qF "$attendu_seuils"; echo $?)"
verifie "ci_passage e2e : les seuils ne comptent pas comme un appel de plus : deux appels SQL en tout" "$([ "$(cat "$FX/sql-n")" = 2 ]; echo $?)"
s_vues=$(sed 's/^VUES=//' "$FX/serveur-secret"); s_stockage=$(sed 's/^STOCKAGE=//' "$FX/serveur-secret-stockage")
verifie "ci_passage e2e : les deux rôles reçoivent leur mot de passe par l'entrée standard de la fonction SQL (psycopg via uv, SQL et secret sur l'entrée), jamais en argument ; aucun client psql" "$([ "$(grep -c '^ALTER ROLE' "$FX/sql-recu")" -eq 2 ] && grep -q 'pmzilla_mothra_views' "$FX/sql-recu" && grep -q 'pmzilla_mothra LOGIN' "$FX/sql-recu" && grep -qF "$s_vues" "$FX/sql-recu" && grep -qF "$s_stockage" "$FX/sql-recu" && ! grep -qF "$s_vues" "$FX/uv-args" && ! grep -qF "$s_stockage" "$FX/uv-args" && ! grep -qF "$pw_e" "$FX/uv-args" && grep -q 'uv run --no-project --with psycopg\[binary\] python -I -c' "$FX/uv-args" && ! grep -q psql "$FX/uv-args"; echo $?)"
verifie "ci_passage e2e : le mot de passe du superutilisateur est lu dans l'environnement par le processus (fonction SQL, migrations, chargeur : ${#pw_e} caractères), avec le port de la base du conteneur voisin" "$(grep -qx "pw_longueur=${#pw_e} port=55432" "$FX/sql-env" && grep -qx "port=55432 pw_longueur=${#pw_e}" "$FX/migrer-env" && grep -qx "port=55432 pw_longueur=${#pw_e}" "$FX/chargeur-env"; echo $?)"
verifie "ci_passage e2e : le serveur reçoit les deux secrets de rôle (32 caractères), jamais celui du superutilisateur, sur 3210, jeu synthétique, depuis mothra/server ; la passe vise 127.0.0.1:3210 sans mot de passe" "$(grep -q 'cwd=server jeu=synthetic port=3210 base=55432 vues_longueur=32 stockage_longueur=32 superutilisateur=absent' "$FX/serveur-env" && grep -qx 'port=55432 url=http://127.0.0.1:3210 superutilisateur=absent' "$FX/passe-env"; echo $?)"
verifie "ci_passage e2e : la construction tourne dans mothra/ (npm run build) sans variable MOTHRA_* ni PMZILLA_LAB_DB_*" "$(grep -qx 'cwd=mothra args=run build mothra= base=' "$FX/build-env"; echo $?)"
verifie "ci_passage e2e : le serveur est arrêté à la fin" "$(! kill -0 "$(sed 's/^pid=\([0-9]*\) .*/\1/' "$FX/serveur-env")" 2>/dev/null; echo $?)"
verifie "ci_passage e2e : la suite de la phase base a bien reçu le mot de passe (longueur ${#pw_e}, non nulle), sans qu'il soit imprimé" "$([ "${#pw_e}" -gt 0 ] && grep -qx "MDP_LONGUEUR=${#pw_e}" "$tmp/spe"; echo $?)"
verifie "ci_passage e2e : ni secret de rôle ni mot de passe du superutilisateur dans la sortie du passage" "$(! grep -qF -e "$s_vues" -e "$s_stockage" -e "$pw_e" "$tmp/spe"; echo $?)"
verifie "ci/passage.sh (tranche 2) : le mot de passe est lu par Python (os.environ), jamais développé par le shell ; aucun client psql ; psycopg" "$(grep -qF 'os.environ["PMZILLA_LAB_DB_PASSWORD"]' "$PASSAGE" && grep -qF 'psycopg' "$PASSAGE" && ! grep -Eq '^[^#]*psql' "$PASSAGE"; echo $?)"

FAUX_MIGRER_CODE=3 lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e : migrations en échec : phase rouge « migrations », rien après" "$(rouge_e migrations && [ "$(ordre_e)" = "migrer " ]; echo $?)"
FAUX_CHARGEUR_CODE=1 lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e : jeu synthétique en échec : phase rouge « jeu synthétique »" "$(rouge_e 'jeu synthétique' && [ "$(ordre_e)" = "migrer chargeur " ]; echo $?)"
FAUX_SQL_KO=1 lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e : rôle des vues en échec : phase rouge « rôle des vues »" "$(rouge_e 'rôle des vues' && [ "$(ordre_e)" = "migrer chargeur sql " ]; echo $?)"
FAUX_SQL_KO=2 lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e : rôle de stockage en échec : phase rouge « rôle de stockage »" "$(rouge_e 'rôle de stockage' && [ "$(ordre_e)" = "migrer chargeur sql sql " ]; echo $?)"
FAUX_BUILD_CODE=7 lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e : construction en échec : phase rouge « construction du bundle », ni serveur ni passe" "$(rouge_e 'construction du bundle' && [ "$(ordre_e)" = "migrer chargeur sql sql build " ]; echo $?)"
FAUX_SONDE_KO=1 lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e : le serveur n'écoute jamais : phase rouge « serveur », phrase, passe non lancée, serveur arrêté" "$(rouge_e serveur && grep -q "Le serveur Mothra n'écoute pas" "$tmp/spe" && ! grep -q '^passe$' "$FX/ordre" && ! kill -0 "$(sed 's/^pid=\([0-9]*\) .*/\1/' "$FX/serveur-env")" 2>/dev/null; echo $?)"
FAUX_SERVEUR_SORT=1 lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e : le serveur sort aussitôt alors que la sonde réussit : phase rouge « serveur », passe non lancée" "$(rouge_e serveur && grep -q "s'est arrêté alors que le port répond" "$tmp/spe" && ! grep -q '^passe$' "$FX/ordre"; echo $?)"
FAUX_PASSE_CODE=1 lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e : passe rouge : phase rouge « passe », code 1, serveur arrêté" "$(rouge_e passe && ! kill -0 "$(sed 's/^pid=\([0-9]*\) .*/\1/' "$FX/serveur-env")" 2>/dev/null; echo $?)"
PLAYWRIGHT_BROWSERS_PATH="$tmp/sans-navigateur" lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e : image sans Chromium : phrase exacte, phase rouge « navigateur absent », aucune étape lancée, pas de preuve (Q210)" "$(rouge_e 'navigateur absent' && grep -qxF "ci_passage : navigateur absent de l'image (rebaser sur main ou reconstruire l'image)" "$tmp/spe" && [ ! -e "$FX/ordre" ]; echo $?)"
PLAYWRIGHT_BROWSERS_PATH="" lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e : PLAYWRIGHT_BROWSERS_PATH absente (ancienne image) : même phase rouge" "$(rouge_e 'navigateur absent' && [ ! -e "$FX/ordre" ]; echo $?)"
FAUX_SUITES_ROUGES="flow_store" lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e : phase base rouge : la phase e2e est sautée (phrase), aucune étape lancée, code 1" "$([ $code -eq 1 ] && grep -qxF 'ci_passage : phase e2e : sautée (phase précédente rouge)' "$tmp/spe" && [ ! -e "$FX/ordre" ]; echo $?)"
FAUX_PORTABLE_ROUGE=1 lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e : phase portable rouge : base et e2e sautées" "$([ $code -eq 1 ] && grep -qxF 'ci_passage : phase base : sautée (phase précédente rouge)' "$tmp/spe" && grep -qxF 'ci_passage : phase e2e : sautée (phase précédente rouge)' "$tmp/spe" && [ ! -e "$FX/ordre" ]; echo $?)"
PMZILLA_LAB_DB_PASSWORD="$pw_q" CI_PASSAGE_CPUS=3 lance_passage_q "$tmp/arbre-e.tar"
verifie "ci_passage e2e : ci/passage.sh lancé sans les étapes devant lui : « phase e2e : non lancée », code inchangé (0), jamais une ligne verte pour e2e" "$([ $code -eq 0 ] && grep -qxF 'ci_passage : phase e2e : non lancée (étapes de bout en bout absentes du script intérieur)' "$tmp/spq" && ! grep -q 'phase e2e : verte' "$tmp/spq"; echo $?)"

# --- garde du nombre de tests de la phase e2e (R-20261103-6, Q1) : verte seulement si la passe a lancé au moins un test, le nombre sur sa ligne
lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e (Q1) : la ligne verte porte le nombre de tests lus dans « N passed » de la passe : « verte · 7 tests · <durée> s », la sortie de la passe reste affichée" "$([ $code -eq 0 ] && grep -Eq '^ci_passage : phase e2e : verte · 7 tests · [0-9]+ s$' "$tmp/spe" && grep -qxF '  7 passed (3s)' "$tmp/spe"; echo $?)"
FAUX_PASSE_SORTIE=$'\033[32m  1 passed\033[39m (1s)' lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e (Q1) : un seul test, avec des séquences de couleur autour du compte : « verte · 1 test · <durée> s »" "$([ $code -eq 0 ] && grep -Eq '^ci_passage : phase e2e : verte · 1 test · [0-9]+ s$' "$tmp/spe"; echo $?)"
FAUX_PASSE_SORTIE="" lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e (Q1) : passe de code 0 qui n'imprime aucun compte, alors que l'arbre porte une spécification : phase rouge « aucun test lancé », code 1, jamais verte" "$(rouge_e 'aucun test lancé'; echo $?)"
FAUX_PASSE_SORTIE="  0 passed (1s)" lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e (Q1) : « 0 passed » : phase rouge « aucun test lancé »" "$(rouge_e 'aucun test lancé'; echo $?)"
FAUX_PASSE_SORTIE="  3 skipped" lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e (Q1) : que des tests sautés : phase rouge « aucun test lancé »" "$(rouge_e 'aucun test lancé'; echo $?)"
FAUX_PASSE_CODE=1 FAUX_PASSE_SORTIE="  7 passed (3s)" lance_passage_e "$tmp/arbre-e.tar"
verifie "ci_passage e2e (Q1) : passe de code 1 : la cause reste « passe » (le compte ne la masque pas)" "$(rouge_e passe; echo $?)"
lance_passage_e "$tmp/arbre-e-sans.tar"
verifie "ci_passage e2e (Q1) : aucune spécification de bout en bout dans l'arbre : « sans objet » (phrase exacte), jamais « verte » ni « rouge », aucune étape lancée, code 0" "$([ $code -eq 0 ] && grep -qxF "ci_passage : phase e2e : sans objet (aucune spécification de bout en bout dans l'arbre)" "$tmp/spe" && ! grep -q 'phase e2e : verte' "$tmp/spe" && ! grep -q 'phase e2e : rouge' "$tmp/spe" && [ ! -e "$FX/ordre" ]; echo $?)"
verifie "ci/passage.sh (Q1) : la règle neuve dit ce qu'elle remplace (rien) et sa condition de retrait" "$(grep -qF 'Garde du nombre de tests (R-20261103-6, Q1). Remplace : rien. Retrait : permanent, tant que la phase e2e existe.' "$PASSAGE"; echo $?)"

# --- rejeu dans ci/passage.sh (Q220) : les suites en arguments, sans base ni phase base ou e2e
lance_rejeu() { # <archive> <suites...> ; variables en préfixe ; sortie dans $tmp/spj
  local a=$1; shift
  rm -rf "$tmp/hp"; mkdir -p "$tmp/hp"; : > "$tmp/sondes"
  ( cd "$tmp" && HOME="$tmp/hp" FAUX_SONDES="$tmp/sondes" PATH="$fq:$fp:$PATH" bash "$PASSAGE" --rejeu "$@" < "$a" ) > "$tmp/spj" 2>&1; code=$?
}
PMZILLA_LAB_DB_PASSWORD="$pw_q" CI_PASSAGE_CPUS=3 lance_rejeu "$tmp/arbre-q.tar" alpha beta
verifie "ci_passage rejeu : les suites nommées seules (ARGS=alpha beta, ni --portable ni phase), RUN_ALL_JOBS = processeurs du passage, aucun mot de passe de base, base non sondée, ligne verte, code 0" "$([ $code -eq 0 ] && [ "$(grep -c '^ARGS=' "$tmp/spj")" -eq 1 ] && grep -qx 'ARGS=alpha beta' "$tmp/spj" && grep -qx 'RUN_ALL_JOBS=3' "$tmp/spj" && grep -qx 'MDP=absent' "$tmp/spj" && grep -qx 'DBPORT=/' "$tmp/spj" && [ ! -s "$tmp/sondes" ] && grep -Eq '^ci_passage : rejeu : verte · [0-9]+ s$' "$tmp/spj" && ! grep -q 'ci_passage : phase' "$tmp/spj"; echo $?)"
FAUX_SUITES_ROUGES="beta" CI_PASSAGE_CPUS=3 lance_rejeu "$tmp/arbre-q.tar" beta alpha
verifie "ci_passage rejeu : une suite rouge : « rejeu : rouge · <durée> s : beta », code 1" "$([ $code -eq 1 ] && grep -Eq '^ci_passage : rejeu : rouge · [0-9]+ s : beta$' "$tmp/spj"; echo $?)"
CI_PASSAGE_CPUS=3 lance_rejeu "$tmp/arbre-q.tar" 'x$(echo pwned)'
verifie "ci_passage rejeu : un nom passe en argument du shell, jamais interpolé" "$(grep -qF 'ARGS=x$(echo pwned)' "$tmp/spj" && ! grep -q '^pwned' "$tmp/spj"; echo $?)"

# --- ci_local run --rejeu portable <suites> (Q220, R-20261101-116)
nouveau_depot
wt_depot=$(cd "$depot" && git rev-parse --show-toplevel)
: > "$FX/images"; construire_image
export CI_LOCAL_VERDICTS="$tmp/verdicts-j"; printf '%s\tvert\t%s\n' "$ARBRE_MAIN" "$(printf 'c%.0s' $(seq 64))" > "$CI_LOCAL_VERDICTS"
export CI_LOCAL_PREUVES="$tmp/preuves-j"; printf '%s\t%s\tportable,base,e2e\n' "$ARBRE_MAIN" "$(printf 'c%.0s' $(seq 64))" > "$CI_LOCAL_PREUVES"
verdicts_avant=$(cat "$CI_LOCAL_VERDICTS"); preuves_avant=$(cat "$CI_LOCAL_PREUVES")
n_rapports_avant=$(ls "$PMZILLA_LAB_DATA/ci"/rapport-* 2>/dev/null | wc -l | tr -d ' ')
remise; FAUX_PASSAGE=rejeu_vert lance run --rejeu portable alpha beta
verifie "ci_local rejeu : vert, code 0, dernière ligne « rejeu vert (arbre, image) : alpha beta »" "$([ $code -eq 0 ] && derniere | grep -Eq "^ci_local : rejeu vert \(arbre ${ARBRE_MAIN:0:12}, image [0-9a-f]{12}\) : alpha beta\$"; echo $?)"
cmd_j=$(sed -n '/^docker run/,/^docker rm/p' "$FAUX_LOG" | head -1)
verifie "ci_local rejeu : pas de base (aucun create ni start), une seule option --network none, --shm-size 1g, les noms en arguments après ci_passage --rejeu, aucune variable de base, texte intérieur sans les étapes e2e" "$([ "$(n_appels 'docker create')" -eq 0 ] && [ "$(n_appels 'docker start')" -eq 0 ] && [ "$(printf '%s' "$cmd_j" | grep -o -- '--network [^ ]*' | wc -l | tr -d ' ')" -eq 1 ] && printf '%s' "$cmd_j" | grep -qF -- '--network none' && printf '%s' "$cmd_j" | grep -qF -- '--shm-size 1g' && grep -qF 'ci_passage --rejeu alpha beta' "$FAUX_LOG" && ! printf '%s' "$cmd_j" | grep -q 'PMZILLA_LAB_DB' && ! grep -qF 'e2e_enchainer()' "$FAUX_LOG"; echo $?)"
verifie "ci_local rejeu : le conteneur est retiré, aucune place ni ticket gardés" "$(grep -q '^docker rm -f pmzilla-ci-[0-9a-f]*$' "$FAUX_LOG" && ! grep -q -- '-base' "$FAUX_LOG" && [ -z "$(ls "$PMZILLA_LAB_DATA/ci/places" 2>/dev/null)" ] && [ -z "$(ls "$PMZILLA_LAB_DATA/ci/file" 2>/dev/null)" ]; echo $?)"
verifie "ci_local rejeu : ni verdict (la ligne de l'arbre n'est ni retirée ni changée), ni preuve, ni rapport (Q227 3)" "$([ "$(cat "$CI_LOCAL_VERDICTS")" = "$verdicts_avant" ] && [ "$(cat "$CI_LOCAL_PREUVES")" = "$preuves_avant" ] && [ "$(ls "$PMZILLA_LAB_DATA/ci"/rapport-* 2>/dev/null | wc -l | tr -d ' ')" = "$n_rapports_avant" ] && ! grep -q 'verdict enregistré\|preuve enregistrée' "$tmp/s"; echo $?)"
remise; FAUX_PASSAGE=rejeu_rouge lance run --rejeu portable beta
verifie "ci_local rejeu : rouge, code 1, dernière ligne « rejeu rouge (arbre, image) : beta », verdicts inchangés" "$([ $code -eq 1 ] && derniere | grep -Eq "^ci_local : rejeu rouge \(arbre ${ARBRE_MAIN:0:12}, image [0-9a-f]{12}\) : beta\$" && [ "$(cat "$CI_LOCAL_VERDICTS")" = "$verdicts_avant" ]; echo $?)"
remise; FAUX_PASSAGE=sans_verdict lance run --rejeu portable beta
verifie "ci_local rejeu : conteneur sans ligne du lanceur : code 1, « aucun verdict du lanceur (code 125) »" "$([ $code -eq 1 ] && derniere | grep -q 'rejeu rouge .* : aucun verdict du lanceur (code 125)$'; echo $?)"
for args in "run --rejeu" "run --rejeu portable" "run --rejeu complet alpha" "run --rejeu portable a;b" "run --rejeu portable --x" "run --rejeu portable a-b" "run --rejeu portable é"; do
  remise; lance $args
  verifie "ci_local rejeu : usage « $args » refusé (code 2, phrase d'usage de D9 pour le rejeu), aucun appel à Docker" "$([ $code -eq 2 ] && grep -qxF "ci_local : usage : run --rejeu portable <suite> [<suite>…]" "$tmp/s" && [ ! -s "$FAUX_LOG" ]; echo $?)"
done
remise; lance up --rejeu portable alpha
verifie "ci_local rejeu : « up --rejeu » reste une erreur d'usage générale (code 2)" "$([ $code -eq 2 ] && grep -qxF "ci_local : usage : bash tools/ci_local.sh run [<branche>] | build | up" "$tmp/s" && [ ! -s "$FAUX_LOG" ]; echo $?)"
# passage.sh sans étapes : « phase e2e : non lancée » ne donne jamais un verdict vert ni une preuve (revue de la tranche 2)
export CI_LOCAL_PREUVES="$tmp/preuves-nl"; : > "$CI_LOCAL_PREUVES"
remise; FAUX_PASSAGE=phases_e2e_non_lancee lance run
verifie "ci_local : phase e2e non lancée : verdict rouge (code 1) qui la nomme, aucune ligne vert pour l'arbre, aucune preuve" "$([ $code -eq 1 ] && derniere | grep -Eq "^ci_local : verdict rouge \(arbre ${ARBRE_MAIN:0:12}, image [0-9a-f]{12}, phases portable,base\) : phase e2e non lancée\$" && ! grep -q "^${ARBRE_MAIN}${TAB}vert" "$CI_LOCAL_VERDICTS" && [ ! -s "$CI_LOCAL_PREUVES" ] && ! grep -q 'preuve enregistrée' "$tmp/s"; echo $?)"
unset CI_LOCAL_PREUVES
remise; FAUX_DOCKER_ARRETE=1 lance run --rejeu portable alpha
verifie "ci_local rejeu : Docker arrêté : code 3, aucun conteneur" "$([ $code -eq 3 ] && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
echo "nouveau" > "$depot/non-suivi.txt"
remise; lance run --rejeu portable alpha
verifie "ci_local rejeu : arbre non propre : code 4, aucun conteneur" "$([ $code -eq 4 ] && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
rm -f "$depot/non-suivi.txt"
commun=$(git -C "$depot" rev-parse --path-format=absolute --git-common-dir)
verrou="$commun/pmzilla-fin-en-cours"
mkdir -p "$verrou"; echo $$ > "$verrou/pid"; date +%s > "$verrou/debut"; echo "feat/autre" > "$verrou/branche"; echo "jeton-verrou-j" > "$verrou/jeton"
remise; lance run --rejeu portable alpha
verifie "ci_local rejeu : verrou d'une autre fin : code 7, aucun conteneur" "$([ $code -eq 7 ] && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
remise; FINISH_LOCK_TOKEN=jeton-verrou-j FAUX_PASSAGE=rejeu_vert lance run --rejeu portable alpha
verifie "ci_local rejeu : avec le jeton de la fin, le rejeu a lieu" "$([ $code -eq 0 ] && [ "$(n_appels 'docker run')" -eq 1 ]; echo $?)"
rm -rf "$verrou"
: > "$FX/images"
remise; lance run --rejeu portable alpha
verifie "ci_local rejeu : image absente : code 5 avec la commande exacte depuis le worktree (R-20261101-116)" "$([ $code -eq 5 ] && grep -qxF "ci_local : image absente ou périmée pour cet arbre (lancer : cd $wt_depot && bash tools/ci_local.sh up)" "$tmp/s"; echo $?)"
construire_image
lacher_places
tenir_place 1
remise
( cd "$depot" && exec env FAUX_PASSAGE=rejeu_vert bash "$SCRIPT" run --rejeu portable alpha ) > "$tmp/sq" 2>&1 &
q=$!
attendre_ligne "$tmp/sq" 'ci_local : en file (position 1, 1 passage(s) en cours sur 1 places)' 100; vu=$?
avant_liberation=$(n_appels 'docker run')
set -- $HOLDERS; kill "$1" 2>/dev/null; wait "$1" 2>/dev/null
attendre_fin "$q" 150
verifie "ci_local rejeu : il passe par la file comme un passage (en file tant que la place est tenue, aucun conteneur), puis prend la place et va au bout" "$([ "$vu" -eq 0 ] && [ "$avant_liberation" -eq 0 ] && [ $code -eq 0 ] && grep -Eq '^ci_local : place 1 prise, départ$' "$tmp/sq"; echo $?)"
lacher_places

# --- preuve enregistrée (9.4, D6)
export CI_LOCAL_VERDICTS="$tmp/verdicts-pr"; printf 'ffffffffffffffffffffffffffffffffffffffff\tvert\t%s\n' "$(printf 'e%.0s' $(seq 64))" > "$CI_LOCAL_VERDICTS"
export CI_LOCAL_PREUVES="$tmp/preuves-pr"; printf 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee\t%s\tportable,base,e2e\n' "$(printf 'd%.0s' $(seq 64))" > "$CI_LOCAL_PREUVES"
autre_preuve=$(cat "$CI_LOCAL_PREUVES")
remise; FAUX_PASSAGE=phases_e2e lance run
verifie "ci_local preuve : trois phases vertes : « phases portable,base,e2e » dans le verdict, code 0" "$([ $code -eq 0 ] && derniere | grep -Eq "^ci_local : verdict vert \(arbre ${ARBRE_MAIN:0:12}, image [0-9a-f]{12}, phases portable,base,e2e, 2 suites, 2 suites Mac non lancées\)\$"; echo $?)"
verifie "ci_local preuve : « preuve enregistrée pour l'arbre <court> (phases portable,base,e2e) » juste avant le verdict, après « verdict enregistré »" "$(n=$(wc -l < "$tmp/s"); [ "$(sed -n "$((n-1))p" "$tmp/s")" = "ci_local : preuve enregistrée pour l'arbre ${ARBRE_MAIN:0:12} (phases portable,base,e2e)" ] && [ "$(sed -n "$((n-2))p" "$tmp/s")" = "ci_local : verdict enregistré pour l'arbre ${ARBRE_MAIN:0:12}" ]; echo $?)"
cle_v=$(grep "^$ARBRE_MAIN$TAB" "$CI_LOCAL_VERDICTS" | cut -f3)
verifie "ci_local preuve : ligne <arbre><TAB><clé d'image><TAB><phases>, autre ligne inchangée, droits 600, aucun verrou laissé" "$(grep -qx "${ARBRE_MAIN}${TAB}${cle_v}${TAB}portable,base,e2e" "$CI_LOCAL_PREUVES" && printf '%s' "$cle_v" | grep -Eq '^[0-9a-f]{64}$' && grep -qxF "$autre_preuve" "$CI_LOCAL_PREUVES" && [ "$(wc -l < "$CI_LOCAL_PREUVES" | tr -d ' ')" -eq 2 ] && [ "$(droits "$CI_LOCAL_PREUVES")" = 600 ] && [ ! -e "$CI_LOCAL_PREUVES.lock" ]; echo $?)"
verifie "ci_local preuve : le fichier des verdicts garde son format de trois champs (arbre, vert, clé)" "$(grep -Eq "^${ARBRE_MAIN}${TAB}vert${TAB}[0-9a-f]{64}\$" "$CI_LOCAL_VERDICTS" && ! grep -Eq "portable" "$CI_LOCAL_VERDICTS"; echo $?)"
remise; FAUX_PASSAGE=phases_e2e_rouge lance run
verifie "ci_local preuve : phase e2e rouge : code 1, verdict rouge qui nomme la cause, la ligne de preuve de l'arbre, retirée au départ, ne revient pas ; l'autre reste" "$([ $code -eq 1 ] && derniere | grep -Eq "^ci_local : verdict rouge \(arbre ${ARBRE_MAIN:0:12}, image [0-9a-f]{12}, phases portable,base\) : passe\$" && ! grep -q "^$ARBRE_MAIN$TAB" "$CI_LOCAL_PREUVES" && grep -qxF "$autre_preuve" "$CI_LOCAL_PREUVES" && ! grep -q 'preuve' "$tmp/s"; echo $?)"
cp "$CI_LOCAL_PREUVES" "$tmp/preuves-avant"
remise; FAUX_PASSAGE=phases_base lance run
verifie "ci_local preuve : vert sans phase e2e : ni preuve ni phrase de preuve, fichier inchangé (jamais une preuve sans e2e)" "$([ $code -eq 0 ] && ! grep -q 'preuve' "$tmp/s" && cmp -s "$CI_LOCAL_PREUVES" "$tmp/preuves-avant"; echo $?)"
unset CI_LOCAL_PREUVES
remise; FAUX_PASSAGE=phases_e2e lance run
verifie "ci_local preuve : faux Docker sans CI_LOCAL_PREUVES : rien n'est lu ni écrit (aucun fichier de preuve dans le dossier de données), aucune phrase" "$([ $code -eq 0 ] && [ ! -e "$PMZILLA_LAB_DATA/ci/preuves" ] && ! grep -q 'preuve' "$tmp/s"; echo $?)"
export CI_LOCAL_PREUVES="$tmp/dossier-absent-pr/preuves"
remise; FAUX_PASSAGE=phases_e2e lance run
verifie "ci_local preuve : écriture impossible : « preuve non enregistrée (écriture impossible) » juste avant le verdict, code inchangé (0)" "$(n=$(wc -l < "$tmp/s"); [ $code -eq 0 ] && [ "$(sed -n "$((n-1))p" "$tmp/s")" = "ci_local : preuve non enregistrée (écriture impossible)" ] && [ ! -e "$tmp/dossier-absent-pr" ]; echo $?)"
unset CI_LOCAL_PREUVES

# =================================================================================================================================
# tooling-proof-in-container, T2 (D1, D4, D5 ; tâches 6.1, 6.2, 6.6) : run --index et run --travail, ligne de preuve d'index (verte seulement),
# places typées. Faux Docker, faux dossier de données, CI_LOCAL_PREUVES_INDEX : le vrai fichier n'est jamais touché.
# =================================================================================================================================
nouveau_depot
: > "$FX/images"; construire_image
export CI_LOCAL_VERDICTS="$tmp/verdicts-t2"; : > "$CI_LOCAL_VERDICTS"
export CI_LOCAL_PREUVES="$tmp/preuves-t2"; : > "$CI_LOCAL_PREUVES"
export CI_LOCAL_PREUVES_INDEX="$tmp/preuves-index-t2"; : > "$CI_LOCAL_PREUVES_INDEX"
unset FAUX_INFO FAUX_PASSAGE
rm -rf "$PMZILLA_LAB_DATA/ci/places" "$PMZILLA_LAB_DATA/ci/file"
etat_depot() { ( cd "$depot" && { git for-each-ref; git ls-files -s; git rev-parse HEAD; } | cksum ); }
cible_run() { sed -n '/^docker run/,/^docker rm/p' "$FAUX_LOG" | head -1; }   # la première ligne : les options de docker run
cible_bloc() { sed -n '/^docker run/,/^docker rm/p' "$FAUX_LOG" | sed '$d'; }   # toute la commande (le script intérieur tient sur plusieurs lignes)
nb_valeurs() { printf '%s' "$1" | awk -F, '{ print NF }'; }   # nombre de valeurs d'une liste « a,b,c »
# --- 6.1 : arbre calculé par l'outil, index et arbre de travail
echo "indexé" > "$depot/i.txt"; ( cd "$depot" && git add i.txt )
echo "travail" > "$depot/a.txt"
ARBRE_INDEX=$(git -C "$depot" write-tree)
avant=$(etat_depot)
remise; FAUX_PASSAGE=rejeu_vert lance run --index alpha beta
verifie "ci_local --index : code 0 ; l'archive envoyée est l'arbre de l'index (fichier indexé présent, modification non indexée absente), le conteneur lance ci_passage --rejeu alpha beta" "$([ $code -eq 0 ] && tar -tf "$FX/archive.tar" | grep -qx 'i.txt' && [ "$(tar -xOf "$FX/archive.tar" a.txt)" = a ] && cible_bloc | grep -q -- 'ci_passage --rejeu alpha beta'; echo $?)"
verifie "ci_local --index : aucune référence ni index réel changé, pas de base ni de phase e2e (aucun create), un seul réseau none" "$([ "$(etat_depot)" = "$avant" ] && [ "$(n_appels 'docker create')" -eq 0 ] && [ "$(cible_run | grep -o -- '--network [^ ]*' | wc -l | tr -d ' ')" -eq 1 ] && cible_run | grep -q -- '--network none'; echo $?)"
echo "non suivi" > "$depot/n.txt"
remise; FAUX_PASSAGE=rejeu_vert lance run --index alpha
verifie "ci_local --index : un fichier non suivi non ignoré n'est pas dans l'archive" "$(! tar -tf "$FX/archive.tar" | grep -qx 'n.txt'; echo $?)"
echo "ignoré" > "$depot/local.txt"
avant=$(etat_depot)
remise; FAUX_PASSAGE=rejeu_vert lance run --travail alpha
verifie "ci_local --travail : code 0 ; l'archive tient le fichier non suivi non ignoré, le fichier indexé et la version de travail, pas le fichier ignoré" "$([ $code -eq 0 ] && tar -tf "$FX/archive.tar" | grep -qx 'n.txt' && tar -tf "$FX/archive.tar" | grep -qx 'i.txt' && [ "$(tar -xOf "$FX/archive.tar" a.txt)" = travail ] && ! tar -tf "$FX/archive.tar" | grep -q 'local.txt'; echo $?)"
verifie "ci_local --travail : ni référence, ni index réel, ni fichier changé (git status identique), aucune base" "$([ "$(etat_depot)" = "$avant" ] && [ -n "$(git -C "$depot" status --porcelain | grep -F 'n.txt')" ] && [ "$(n_appels 'docker create')" -eq 0 ]; echo $?)"
for forme in "feat/x alpha" "a;b" "a-b" "é" "--travail alpha" "--index" "alpha complet"; do
  for mode in --index --travail; do
    remise; lance run "$mode" $forme
    verifie "ci_local : usage « run $mode $forme » refusé (code 2), aucun appel à Docker" "$([ $code -eq 2 ] && [ ! -s "$FAUX_LOG" ]; echo $?)"
  done
done
remise; lance run --index 'a;b'
verifie "ci_local : un nom de suite avec « ; » (un seul argument) refusé (code 2), aucun appel à Docker" "$([ $code -eq 2 ] && [ ! -s "$FAUX_LOG" ]; echo $?)"
remise; FAUX_PASSAGE=phases_e2e lance run --travail
verifie "ci_local --travail sans suite : passage complet (une base, trois phases), code 0" "$([ $code -eq 0 ] && [ "$(n_appels 'docker create')" -eq 1 ] && cible_bloc | grep -q 'ci_passage' ; echo $?)"
# --- 6.2 : ligne de preuve d'index, verte seulement, sans champ de verdict
: > "$CI_LOCAL_PREUVES_INDEX"
n_rapports_avant=$(ls "$PMZILLA_LAB_DATA/ci"/rapport-* 2>/dev/null | wc -l | tr -d ' ')
remise; FAUX_PASSAGE=rejeu_vert lance run --index alpha beta
verifie "ci_local preuve d'index : --index vert : une ligne <arbre><TAB><clé d'image><TAB>alpha,beta, sans champ de verdict ; la phrase la dit" "$([ $code -eq 0 ] && [ "$(wc -l < "$CI_LOCAL_PREUVES_INDEX" | tr -d ' ')" -eq 1 ] && grep -Eq "^${ARBRE_INDEX}${TAB}[0-9a-f]{64}${TAB}alpha,beta\$" "$CI_LOCAL_PREUVES_INDEX" && ! grep -Eq 'vert|rouge' "$CI_LOCAL_PREUVES_INDEX" && grep -qF "ci_local : preuve d'index enregistrée pour l'arbre ${ARBRE_INDEX:0:12}" "$tmp/s" && [ "$(droits "$CI_LOCAL_PREUVES_INDEX")" = 600 ]; echo $?)"
verifie "ci_local preuve d'index : ni verdict, ni preuve de commit, ni rapport écrits par un --index de suites" "$([ ! -s "$CI_LOCAL_VERDICTS" ] && [ ! -s "$CI_LOCAL_PREUVES" ] && [ "$(ls "$PMZILLA_LAB_DATA/ci"/rapport-* 2>/dev/null | wc -l | tr -d ' ')" = "$n_rapports_avant" ]; echo $?)"
cp "$CI_LOCAL_PREUVES_INDEX" "$tmp/pi-avant"
remise; FAUX_PASSAGE=rejeu_rouge lance run --index alpha
verifie "ci_local preuve d'index : --index rouge : code 1, le verdict rouge est dit, le fichier des preuves d'index est inchangé" "$([ $code -eq 1 ] && grep -q 'verdict rouge' "$tmp/s" && cmp -s "$CI_LOCAL_PREUVES_INDEX" "$tmp/pi-avant"; echo $?)"
remise; FAUX_PASSAGE=rejeu_vert lance run --travail alpha
verifie "ci_local preuve d'index : --travail vert : ni preuve d'index, ni verdict, ni preuve, ni rapport" "$([ $code -eq 0 ] && cmp -s "$CI_LOCAL_PREUVES_INDEX" "$tmp/pi-avant" && [ ! -s "$CI_LOCAL_VERDICTS" ] && [ ! -s "$CI_LOCAL_PREUVES" ] && [ "$(ls "$PMZILLA_LAB_DATA/ci"/rapport-* 2>/dev/null | wc -l | tr -d ' ')" = "$n_rapports_avant" ] && ! grep -q "preuve d'index" "$tmp/s"; echo $?)"
remise; FAUX_PASSAGE=interrompre lance_relais run --index alpha
verifie "ci_local preuve d'index : interruption (code 130) : le fichier des preuves d'index est inchangé" "$([ $code -eq 130 ] && cmp -s "$CI_LOCAL_PREUVES_INDEX" "$tmp/pi-avant"; echo $?)"
remise; FAUX_PASSAGE=phases_e2e lance run --index
verifie "ci_local preuve d'index : --index sans suite (mode complet) vert : une ligne « complet » pour l'arbre, ni verdict ni preuve de commit" "$([ $code -eq 0 ] && grep -Eq "^${ARBRE_INDEX}${TAB}[0-9a-f]{64}${TAB}complet\$" "$CI_LOCAL_PREUVES_INDEX" && [ ! -s "$CI_LOCAL_VERDICTS" ] && [ ! -s "$CI_LOCAL_PREUVES" ]; echo $?)"
cp "$CI_LOCAL_PREUVES_INDEX" "$tmp/pi-avant"
remise; FAUX_PASSAGE=phases_base lance run --index
verifie "ci_local preuve d'index : --index sans suite vert sur deux phases seulement (portable,base) : aucune ligne, jamais une preuve sans e2e" "$([ $code -eq 0 ] && cmp -s "$CI_LOCAL_PREUVES_INDEX" "$tmp/pi-avant" && ! grep -q "preuve d'index" "$tmp/s"; echo $?)"
remise; FAUX_PASSAGE=phases_e2e lance run --travail
verifie "ci_local preuve d'index : --travail sans suite vert sur trois phases : ni ligne d'index, ni verdict, ni preuve de commit" "$([ $code -eq 0 ] && cmp -s "$CI_LOCAL_PREUVES_INDEX" "$tmp/pi-avant" && [ ! -s "$CI_LOCAL_VERDICTS" ] && [ ! -s "$CI_LOCAL_PREUVES" ]; echo $?)"
unset CI_LOCAL_PREUVES_INDEX
rm -f "$PMZILLA_LAB_DATA/ci/preuves-index"
remise; FAUX_PASSAGE=rejeu_vert lance run --index alpha
verifie "ci_local preuve d'index : faux Docker sans CI_LOCAL_PREUVES_INDEX : rien n'est lu ni écrit dans le dossier de données, aucune phrase" "$([ $code -eq 0 ] && [ ! -e "$PMZILLA_LAB_DATA/ci/preuves-index" ] && ! grep -q "preuve d'index" "$tmp/s"; echo $?)"
export CI_LOCAL_PREUVES_INDEX="$tmp/dossier-absent-pi/preuves-index"
remise; FAUX_PASSAGE=rejeu_vert lance run --index alpha
verifie "ci_local preuve d'index : écriture impossible : « preuve d'index non enregistrée (écriture impossible) », code inchangé (0)" "$([ $code -eq 0 ] && grep -qxF "ci_local : preuve d'index non enregistrée (écriture impossible)" "$tmp/s" && [ ! -e "$tmp/dossier-absent-pi" ]; echo $?)"
export CI_LOCAL_PREUVES_INDEX="$tmp/preuves-index-t2"
rm -f "$depot/i.txt" "$depot/n.txt" "$depot/local.txt"; ( cd "$depot" && git reset -q && git checkout -q -- a.txt )
# --- 6.6 : places typées, jeux de processeurs disjoints, jeton du train en tête
lacher_places
tenir_type() { # <k> <type> <cpuset> : place k tenue par un processus vivant, avec son type et son jeu de processeurs
  tenir_place "$1"; printf '%s' "$2" > "$PMZILLA_LAB_DATA/ci/places/$1/type"; printf '%s' "$3" > "$PMZILLA_LAB_DATA/ci/places/$1/cpuset"
}
cpuset_de() { printf '%s' "$1" | sed -n 's/.*--cpuset-cpus \([0-9,]*\).*/\1/p' | head -1; }
disjoints() { # deux listes « a,b,c » : aucune valeur commune
  local x y; for x in ${1//,/ }; do for y in ${2//,/ }; do [ "$x" != "$y" ] && continue; return 1; done; done; return 0
}
export FAUX_INFO="8 17179869184"
remise; lance places --json
verifie "ci_local places typées : places --json donne le budget de chaque type (preuve 4 processeurs et 6144 Mio, ciblée 2 et 3072 Mio) et la liste des places tenues" "$(grep -q '"preuve":{"processeurs":4,"memoire_mio":6144},"ciblee":{"processeurs":2,"memoire_mio":3072},"detenues":\[\],' "$tmp/s"; echo $?)"
tenir_type 1 preuve "0,1,2,3"; tenir_type 2 preuve "4,5,6,7"
remise; lance places --json
verifie "ci_local places typées : deux preuves tenues : type, processeurs, mémoire et jeu de chacune, jeux disjoints, aucune place ciblée libre" "$(grep -q '{"type":"preuve","processeurs":4,"memoire_mio":6144,"cpuset":"0,1,2,3"}' "$tmp/s" && grep -q '{"type":"preuve","processeurs":4,"memoire_mio":6144,"cpuset":"4,5,6,7"}' "$tmp/s" && grep -q '"libres_ciblees":0' "$tmp/s"; echo $?)"
remise
( cd "$depot" && exec env FAUX_PASSAGE=rejeu_vert bash "$SCRIPT" run --travail alpha ) > "$tmp/sq" 2>&1 &
q=$!
attendre_ligne "$tmp/sq" 'ci_local : en file (position 1, 2 passage(s) en cours sur 2 places)' 100; vu=$?
avant_liberation=$(n_appels 'docker run')
set -- $HOLDERS; kill "$1" 2>/dev/null; wait "$1" 2>/dev/null
attendre_fin "$q" 150
verifie "ci_local places typées : deux preuves tiennent tout le budget : une exécution ciblée attend en file, puis prend la place libérée" "$([ "$vu" -eq 0 ] && [ "$avant_liberation" -eq 0 ] && [ $code -eq 0 ] && grep -Eq '^ci_local : place [0-9]+ prise, départ$' "$tmp/sq"; echo $?)"
lacher_places
tenir_type 1 preuve "0,1,2,3"
remise; FAUX_PASSAGE=rejeu_vert lance_borne run --travail alpha
run1=$(cible_run); jeu1=$(cpuset_de "$run1")
verifie "ci_local places typées : une preuve tenue (0-3) : une exécution ciblée a une place de 2 processeurs (--cpus 2, --memory 3072m, jeu de 2) disjointe de celui de la preuve" "$([ $code -eq 0 ] && printf '%s' "$run1" | grep -q -- '--cpus 2 ' && printf '%s' "$run1" | grep -q -- '--memory 3072m' && [ "$(nb_valeurs "$jeu1")" -eq 2 ] && disjoints "$jeu1" "0,1,2,3"; echo $?)"
tenir_type 2 ciblee "4,5"
remise; FAUX_PASSAGE=rejeu_vert lance_borne run --index alpha
run2=$(cible_run); jeu2=$(cpuset_de "$run2")
verifie "ci_local places typées : une preuve et une ciblée tenues : une seconde ciblée a un jeu disjoint de la preuve (0-3) et de la première ciblée (4,5)" "$([ $code -eq 0 ] && [ -n "$jeu2" ] && disjoints "$jeu2" "0,1,2,3" && disjoints "$jeu2" "4,5"; echo $?)"
lacher_places
remise; FAUX_PASSAGE=phases_e2e lance_borne run
cree=$(grep '^docker create' "$FAUX_LOG"); run3=$(cible_run)
verifie "ci_local places typées : une preuve seule sur 8 processeurs : 4 processeurs disjoints, un pour la base et trois pour les suites" "$(jb=$(cpuset_de "$cree"); js=$(cpuset_de "$run3"); [ $code -eq 0 ] && [ -n "$jb" ] && [ -n "$js" ] && disjoints "$jb" "$js" && [ "$(nb_valeurs "$jb,$js")" -eq 4 ]; echo $?)"
tenir_type 1 preuve "0,1,2,3"
remise; FAUX_PASSAGE=phases_e2e lance_borne run
cree=$(grep '^docker create' "$FAUX_LOG"); run4=$(cible_run)
verifie "ci_local places typées : une seconde preuve avec une preuve tenue (0-3) : ses 4 processeurs sont pris hors de 0-3" "$(jb=$(cpuset_de "$cree"); js=$(cpuset_de "$run4"); [ $code -eq 0 ] && disjoints "$jb" "0,1,2,3" && disjoints "$js" "0,1,2,3"; echo $?)"
lacher_places
# le jeton du verrou de fin passe devant dans la file, jamais dans une place tenue (comme pour les preuves)
tenir_type 1 preuve "0,1,2,3"; tenir_type 2 preuve "4,5,6,7"
remise
( cd "$depot" && exec env FAUX_PASSAGE=rejeu_vert bash "$SCRIPT" run --travail alpha ) > "$tmp/sqa" 2>&1 &
qa=$!
attendre_ligne "$tmp/sqa" 'ci_local : en file (position 1, 2 passage(s) en cours sur 2 places)' 100; vu_a=$?
commun=$(git -C "$depot" rev-parse --path-format=absolute --git-common-dir)
verrou="$commun/pmzilla-fin-en-cours"
mkdir -p "$verrou"; echo $$ > "$verrou/pid"; date +%s > "$verrou/debut"; echo "feat/train-t2" > "$verrou/branche"; echo "jeton-train-t2" > "$verrou/jeton"
( cd "$depot" && exec env FINISH_LOCK_TOKEN=jeton-train-t2 FAUX_PASSAGE=rejeu_vert bash "$SCRIPT" run --travail alpha ) > "$tmp/sqb" 2>&1 &
qb=$!
attendre_ligne "$tmp/sqb" 'ci_local : en file (position 1, 2 passage(s) en cours sur 2 places)' 100; vu_b=$?
attendre_ligne "$tmp/sqa" 'ci_local : en file (position 2, 2 passage(s) en cours sur 2 places)' 100; vu_a2=$?
verifie "ci_local places typées : le jeton du train passe en tête de file (position 1), l'autre recule (position 2), aucune place tenue n'est prise" "$([ "$vu_a" -eq 0 ] && [ "$vu_b" -eq 0 ] && [ "$vu_a2" -eq 0 ] && [ "$(n_appels 'docker run')" -eq 0 ]; echo $?)"
for h in $HOLDERS; do kill "$h" 2>/dev/null; wait "$h" 2>/dev/null; done; HOLDERS=""
attendre_fin "$qb" 150; code_b=$code
attendre_fin "$qa" 150; code_a=$code
verifie "ci_local places typées : les deux exécutions vont au bout une fois les places libres" "$([ "$code_a" -eq 0 ] && [ "$code_b" -eq 0 ]; echo $?)"
rm -rf "$verrou"
lacher_places
unset FAUX_INFO CI_LOCAL_PREUVES_INDEX CI_LOCAL_PREUVES
export CI_LOCAL_VERDICTS="$tmp/verdicts"

# --- place libre de la machine Colima (ci-local-image-prune, D4 à D7) : code 8, avant la file et tout conteneur, après les refus 2, 7, 4 et 3
depot_avant=$depot; arbre_avant=$ARBRE_MAIN
nouveau_depot
phrase8() { printf "ci_local : place libre insuffisante dans la machine Colima (%s Gio libres, minimum 15 Gio) ; rien n'est lancé (nettoyage : docker image ls pmzilla-ci, puis docker image rm pmzilla-ci:<clé> pour chaque clé sans branche ouverte)" "$1"; }
rien_lance() { [ "$(n_appels '^docker create')" -eq 0 ] && [ "$(n_appels '^docker run')" -eq 0 ] && [ -z "$(ls "$PMZILLA_LAB_DATA/ci/file" 2>/dev/null)" ] && [ -z "$(ls "$PMZILLA_LAB_DATA/ci/places" 2>/dev/null)" ]; }
: > "$FX/images"
remise; FAUX_DF_KIO=1 lance run
verifie "ci_local place libre : sans image et sous le seuil, le code 8 passe avant le code 5 (ordre : 3, 8, 5)" "$([ $code -eq 8 ] && grep -qxF "$(phrase8 0)" "$tmp/s" && rien_lance; echo $?)"
construire_image
refus_place() { # <forme> <arguments du script...> : sous le seuil (15 Gio moins 1 Kio), le code 8 et sa phrase sur la sortie d'erreur, rien de lancé
  local forme=$1; shift
  remise; FAUX_DF_KIO=15728639 lance "$@"
  verifie "ci_local place libre : $forme sous le seuil : code 8, phrase de D7 (14 Gio), aucun create ni run, aucune entrée de file ni place" "$([ $code -eq 8 ] && grep -qxF "$(phrase8 14)" "$tmp/s" && rien_lance; echo $?)"
}
refus_place "run" run
refus_place "run --rejeu" run --rejeu portable alpha
refus_place "run --index (complet)" run --index
refus_place "run --index <suite>" run --index alpha
refus_place "run --travail" run --travail
refus_place "run --travail <suite>" run --travail alpha
refus_place "up" up
remise; FAUX_DF_KIO=15728639 lance run >/dev/null; sortie_err=$( cd "$depot" && FAUX_DF_KIO=15728639 bash "$SCRIPT" run 2>&1 >/dev/null )
verifie "ci_local place libre : la phrase du code 8 est sur la sortie d'erreur" "$([ "$sortie_err" = "$(phrase8 14)" ]; echo $?)"
remise; FAUX_DF_KIO=15728640 lance run
verifie "ci_local place libre : exactement au seuil (15 Gio) : le passage a lieu, code 0, aucune ligne de mesure manquée" "$([ $code -eq 0 ] && [ "$(n_appels '^docker run')" -eq 1 ] && grep -qxF 'colima ssh -- df -Pk /var/lib/docker' "$FAUX_LOG" && ! grep -q 'non mesurée' "$tmp/s"; echo $?)"
remise; lance run
verifie "ci_local place libre : mesure par défaut au-dessus du seuil : le passage a lieu, aucune ligne de mesure manquée" "$([ $code -eq 0 ] && ! grep -q 'non mesurée' "$tmp/s"; echo $?)"
for panne in "FAUX_DF_ECHEC=1" "FAUX_DF_KIO=abc" "FAUX_DF_KIO="; do
  remise; env "$panne" bash -c 'cd "$1" && bash "$2" run' _ "$depot" "$SCRIPT" > "$tmp/s" 2>&1; code=$?
  verifie "ci_local place libre : mesure impossible ($panne) : ligne d'avertissement, le passage a lieu (code 0)" "$([ $code -eq 0 ] && grep -qxF 'ci_local : place libre de la machine Colima non mesurée ; passage sans ce contrôle' "$tmp/s" && [ "$(n_appels '^docker run')" -eq 1 ]; echo $?)"
done
remise; FAUX_DOCKER_ARRETE=1 FAUX_DF_KIO=1 lance run
verifie "ci_local place libre : Docker qui ne répond pas donne 3 avant toute mesure (aucun colima ssh)" "$([ $code -eq 3 ] && [ "$(n_appels '^colima ssh')" -eq 0 ]; echo $?)"
remise; FAUX_DF_KIO=1 lance run inconnue
verifie "ci_local place libre : branche inconnue (4) avant la mesure (aucun colima ssh)" "$([ $code -eq 4 ] && [ "$(n_appels '^colima ssh')" -eq 0 ]; echo $?)"

# --- nettoyage des images après une construction de up (ci-local-image-prune, D1 à D3, D7)
STALE=$(printf 'c%.0s' $(seq 64))
commit_branche() { # <branche> : une branche locale avec un Dockerfile propre (donc sa propre clé), HEAD revient sur main
  ( cd "$depot" && git checkout -q -b "$1" && echo "RUN true # $1" >> ci/Dockerfile && git add -A && git commit -q -m "$1" && git checkout -q main )
}
image_de() { # <branche> : construit l'image de la clé de cette branche par build (sans nettoyage) ; la clé est dans cle_img
  ( cd "$depot" && git checkout -q "$1" ) && construire_image; ( cd "$depot" && git checkout -q main )
  cle_img=$(tail -n 1 "$FX/images" | cut -d' ' -f1)
}
: > "$FX/images"
construire_image; K_m0=$(tail -n 1 "$FX/images" | cut -d' ' -f1)
for b in feat/ferme feat/ouverte feat/wt feat/det feat/nouvelle; do commit_branche "$b"; done
image_de feat/ferme; K_f=$cle_img
image_de feat/ouverte; K_o=$cle_img
image_de feat/wt; K_w=$cle_img
image_de feat/det; K_d=$cle_img
( cd "$depot" && git worktree add -q "$tmp/wt-w" feat/wt && git worktree add -q --detach "$tmp/wt-d" feat/det && git branch -q -D feat/ferme && git branch -q -D feat/det )
remise; FAUX_TAGS_EXTRA="<none> latest MAJUSCULES" lance up feat/nouvelle
K_n=$(tail -n 1 "$FX/images" | cut -d' ' -f1)
verifie "ci_local nettoyage : up qui construit retire l'image de la branche fermée, dite par sa clé courte, code 0" "$([ $code -eq 0 ] && [ "$(grep -cxF "ci_local : image supprimée (clé ${K_f:0:12})" "$tmp/s")" -eq 1 ] && [ "$(n_appels '^docker image rm')" -eq 1 ] && grep -qxF "docker image rm pmzilla-ci:$K_f" "$FAUX_LOG" && ! grep -q "^$K_f " "$FX/images"; echo $?)"
verifie "ci_local nettoyage : les images de main, d'une branche, d'un worktree, d'un worktree détaché et de la clé construite sont gardées" "$(for k in "$K_m0" "$K_o" "$K_w" "$K_d" "$K_n"; do grep -q "^$k " "$FX/images" || exit 1; done; [ "$K_n" != "$K_m0" ] && ! grep -Eq "image rm pmzilla-ci:($K_m0|$K_o|$K_w|$K_d|$K_n)" "$FAUX_LOG"; echo $?)"
verifie "ci_local nettoyage : étiquettes mal formées et <none> gardées sans commande ni message, ligne de bilan « 1 supprimée(s), 8 gardée(s) »" "$(grep -qxF 'ci_local : nettoyage des images : 1 supprimée(s), 8 gardée(s)' "$tmp/s" && ! grep -Eq 'none|latest|MAJUSCULES' "$tmp/s" && ! grep -Eq 'image rm pmzilla-ci:(<none>|latest|MAJUSCULES)' "$FAUX_LOG"; echo $?)"
verifie "ci_local nettoyage : après la construction et avant le passage (journal : build, image rm, run ; sortie : bilan avant le verdict)" "$(b=$(grep -n '^docker build' "$FAUX_LOG" | head -1 | cut -d: -f1); r=$(grep -n '^docker image rm' "$FAUX_LOG" | head -1 | cut -d: -f1); u=$(grep -n '^docker run' "$FAUX_LOG" | head -1 | cut -d: -f1); [ "$b" -lt "$r" ] && [ "$r" -lt "$u" ] && [ "$(grep -n 'nettoyage des images' "$tmp/s" | cut -d: -f1)" -lt "$(grep -n 'verdict vert' "$tmp/s" | cut -d: -f1)" ]; echo $?)"
verifie "ci_local nettoyage : seulement « docker image rm pmzilla-ci:<clé> » (jamais --force, prune, volume, conteneur, autre dépôt ni image de la base)" "$(! grep '^docker image rm' "$FAUX_LOG" | grep -vq '^docker image rm pmzilla-ci:[0-9a-f]\{64\}$' && ! grep -Eq '^docker (system|volume|network|builder|rmi|container)|image prune|container prune|--force' "$FAUX_LOG" && ! grep -E '^docker images' "$FAUX_LOG" | grep -vEq 'reference=pmzilla-ci|label=pmzilla\.ci\.base'; echo $?)"
# image refusée par Docker : gardée et dite
grep -v "^$K_n " "$FX/images" > "$FX/i2"; mv "$FX/i2" "$FX/images"; echo "$STALE x" >> "$FX/images"
remise; FAUX_IMAGES_UTILISEES="$STALE" lance up feat/nouvelle
verifie "ci_local nettoyage : image refusée par Docker : gardée, dite avec sa clé courte, bilan « 0 supprimée(s), 6 gardée(s) », code de up inchangé" "$([ $code -eq 0 ] && grep -qxF "ci_local : image gardée (clé ${STALE:0:12}) : suppression refusée par Docker" "$tmp/s" && grep -qxF 'ci_local : nettoyage des images : 0 supprimée(s), 6 gardée(s)' "$tmp/s" && grep -q "^$STALE " "$FX/images"; echo $?)"
# image à jour : rien n'est nettoyé ; build ne nettoie jamais
remise; lance up feat/nouvelle
verifie "ci_local nettoyage : image à jour : ni liste, ni suppression, ni bilan, ni abstention" "$([ $code -eq 0 ] && grep -q "image à jour" "$tmp/s" && [ "$(n_appels 'reference=pmzilla-ci')" -eq 0 ] && [ "$(n_appels '^docker image rm')" -eq 0 ] && ! grep -Eq 'nettoyage des images|non nettoyées|image supprimée' "$tmp/s" && grep -q "^$STALE " "$FX/images"; echo $?)"
remise; lance build
verifie "ci_local nettoyage : build ne nettoie jamais (une image sans branche reste, aucune liste, aucune suppression)" "$([ $code -eq 0 ] && [ "$(n_appels 'reference=pmzilla-ci')" -eq 0 ] && [ "$(n_appels '^docker image rm')" -eq 0 ] && grep -q "^$STALE " "$FX/images"; echo $?)"

# abstentions : une seule image périmée, main sans image (up construit), le nettoyage s'abstient et up va au bout
abstention() { # <raison> <description> : à lire après « lance up » (ou équivalent) dans $tmp/s
  verifie "ci_local nettoyage : abstention ($2) : « images non nettoyées ($1) », rien n'est retiré, up va au bout (code 0, un conteneur)" "$([ $code -eq 0 ] && grep -qxF "ci_local : images non nettoyées ($1)" "$tmp/s" && [ "$(n_appels '^docker image rm')" -eq 0 ] && grep -q "^$STALE " "$FX/images" && [ "$(n_appels '^docker run')" -eq 1 ] && ! grep -q 'nettoyage des images' "$tmp/s"; echo $?)"
}
une_image_perimee() { printf '%s x\n' "$STALE" > "$FX/images"; }
commun=$(git -C "$depot" rev-parse --path-format=absolute --git-common-dir)
verrou="$commun/pmzilla-fin-en-cours"
mkdir -p "$verrou"; echo $$ > "$verrou/pid"; date +%s > "$verrou/debut"; echo "feat/autre" > "$verrou/branche"; echo "jeton-nettoyage-x" > "$verrou/jeton"
une_image_perimee; remise; FINISH_LOCK_TOKEN=jeton-nettoyage-x lance up
abstention "verrou de fin tenu" "verrou de fin tenu, avec le jeton de ce verrou"
une_image_perimee; remise; lance up
verifie "ci_local nettoyage : verrou de fin tenu sans le jeton : up refusé (code 7) avant tout, aucune suppression" "$([ $code -eq 7 ] && [ "$(n_appels '^docker image rm')" -eq 0 ] && grep -q "^$STALE " "$FX/images" && [ ! -s "$FAUX_LOG" ]; echo $?)"
rm -rf "$verrou"
mkdir -p "$PMZILLA_LAB_DATA/ci/places/1"; echo $$ > "$PMZILLA_LAB_DATA/ci/places/1/pid"
une_image_perimee; remise; FAUX_INFO="8 17179869184" lance up
abstention "preuve en cours" "place tenue"
rm -rf "$PMZILLA_LAB_DATA/ci/places" "$PMZILLA_LAB_DATA/ci/file" "$PMZILLA_LAB_DATA/ci/verrou-places"
mkdir -p "$PMZILLA_LAB_DATA/ci/file"; echo $$ > "$PMZILLA_LAB_DATA/ci/file/1-999999999999-x"
une_image_perimee; remise; FAUX_INFO="8 17179869184" lance up
abstention "preuve en cours" "ticket de la file d'un processus vivant"
rm -rf "$PMZILLA_LAB_DATA/ci/places" "$PMZILLA_LAB_DATA/ci/file" "$PMZILLA_LAB_DATA/ci/verrou-places" "$PMZILLA_LAB_DATA/ci/compteur"
une_image_perimee; remise; PMZILLA_LAB_DATA= lance up
abstention "dossier de données introuvable" "pas de dossier de données"
( cd "$depot" && git checkout -q -b feat/cassee && echo "cassee" > cassee.txt && git add -A && git commit -q -m cassee && git checkout -q main )
arbre_casse=$(git -C "$depot" rev-parse 'feat/cassee^{tree}')
rm -f "$depot/.git/objects/${arbre_casse:0:2}/${arbre_casse:2}"
une_image_perimee; remise; lance up
abstention "clé d'une branche non calculée" "arbre d'une branche illisible"
git -C "$depot" branch -q -D feat/cassee
une_image_perimee; remise; FAUX_IMAGES_ECHEC=1 lance up
abstention "liste des images illisible" "liste de Docker en échec"
# revue Opus 3.1, constat 7 : un faux git (devant le vrai dans PATH) dont for-each-ref échoue ou ne rend rien, ou dont worktree list échoue
vrai_git=$(command -v git); mkdir -p "$tmp/gitbin"
cat > "$tmp/gitbin/git" <<SCRIPT
#!/bin/bash
case "\${1:-}:\${FAUX_GIT:-}" in
  for-each-ref:echec|worktree:wt) exit 1 ;;
  for-each-ref:vide) exit 0 ;;
esac
exec "$vrai_git" "\$@"
SCRIPT
chmod +x "$tmp/gitbin/git"
for mode in echec vide wt; do
  une_image_perimee; remise; PATH="$tmp/gitbin:$PATH" FAUX_GIT=$mode lance up
  abstention "clé d'une branche non calculée" "liste des branches ou des worktrees illisible ou vide (faux git : $mode)"
done
# revue Opus 3.1, constat 7 : verrou des places tenu par un autre (récent) : « places indisponibles » ; retiré en tâche de fond dès que la ligne d'abstention
# paraît (attente bornée à 60 s, sans délai fixe) pour que le passage de up ne l'attende pas
mkdir -p "$PMZILLA_LAB_DATA/ci/verrou-places"
une_image_perimee; remise
( for _ in $(seq 600); do grep -qF 'images non nettoyées (places indisponibles)' "$tmp/s" 2>/dev/null && break; sleep 0.1; done; rmdir "$PMZILLA_LAB_DATA/ci/verrou-places" 2>/dev/null ) & attente_verrou=$!
lance up
wait "$attente_verrou"
abstention "places indisponibles" "verrou des places tenu par un autre"
# revue Opus 3.1, constat 7 : un verrou de fin périmé (processus mort) est dit et ignoré par up, et ne retient pas le nettoyage
mkdir -p "$verrou"; sleep 0 & mort_v=$!; wait "$mort_v"
echo "$mort_v" > "$verrou/pid"; date +%s > "$verrou/debut"; echo "feat/autre" > "$verrou/branche"; echo "jeton-perime-x" > "$verrou/jeton"
une_image_perimee; remise; lance up
verifie "ci_local nettoyage : verrou de fin périmé : dit et ignoré, l'image sans branche est retirée, bilan « 1 supprimée(s), 1 gardée(s) », up au bout (code 0)" "$([ $code -eq 0 ] && grep -qxF 'ci_local : verrou de fin périmé, ignoré' "$tmp/s" && grep -qxF "ci_local : image supprimée (clé ${STALE:0:12})" "$tmp/s" && grep -qxF 'ci_local : nettoyage des images : 1 supprimée(s), 1 gardée(s)' "$tmp/s" && ! grep -q "^$STALE " "$FX/images" && [ "$(n_appels '^docker run')" -eq 1 ]; echo $?)"
rm -rf "$verrou"
rm -rf "$PMZILLA_LAB_DATA/ci/places" "$PMZILLA_LAB_DATA/ci/file" "$PMZILLA_LAB_DATA/ci/verrou-places"
depot=$depot_avant; ARBRE_MAIN=$arbre_avant

# --- cle (R-20261103-6, Q9) : lecture seule, lue par le contrôle ci-container de tools/doctor.py ; en dernier, car le test change ci/Dockerfile (donc la clé)
echo "RUN true # cle" >> "$depot/ci/Dockerfile"; commit_depot "cle"
remise; lance cle
verifie "ci_local cle : aucune image de la clé : code 5, phrase avec la clé courte et la commande de construction, aucun conteneur ni construction" "$([ $code -eq 5 ] && grep -Eq '^ci_local : image de la clé [0-9a-f]{12} absente \(lancer : .*bash tools/ci_local.sh up\)$' "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ] && [ "$(n_appels 'docker build')" -eq 0 ] && [ "$(n_appels 'docker create')" -eq 0 ]; echo $?)"
construire_image
remise; lance cle
verifie "ci_local cle : image de la clé présente : code 0, « image de la clé <clé courte> présente », aucun conteneur ni construction" "$([ $code -eq 0 ] && grep -Eq '^ci_local : image de la clé [0-9a-f]{12} présente$' "$tmp/s" && [ "$(n_appels 'docker run')" -eq 0 ] && [ "$(n_appels 'docker build')" -eq 0 ] && [ "$(n_appels 'docker create')" -eq 0 ]; echo $?)"
remise; FAUX_DOCKER_ARRETE=1 lance cle
verifie "ci_local cle : Docker ne répond pas : code 3, phrase de D2" "$([ $code -eq 3 ] && grep -qxF "ci_local : Docker ne répond pas ; rien n'est lancé (colima status)" "$tmp/s"; echo $?)"
remise; lance cle x
verifie "ci_local cle : un argument en trop est un usage refusé (code 2), aucun appel à Docker" "$([ $code -eq 2 ] && [ ! -s "$FAUX_LOG" ]; echo $?)"
remise; CLAUDECODE=1 lance cle
verifie "ci_local cle : permis en session (lecture seule), comme places" "$([ $code -eq 0 ]; echo $?)"

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
