#!/bin/bash
# PMZilla Lab : script intérieur de la CI locale (change ci-local-runner, design D2, tranches 0 et 1).
#
# Lu par tools/ci_local.sh (bash -c "$(cat ci/passage.sh)", l'archive de l'arbre sur l'entrée) et lancé DANS le conteneur du passage
# seulement : il refuse sur macOS, par le système (uname), sans variable qui lève ce refus.
# Remplace : la chaîne INTERIEUR de tools/ci_local.sh (lignes 263 à 279 avant ce change), déplacée ici telle quelle pour la phase 1 ;
# la phase 2 (base) est neuve. Retrait : permanent, tant que tools/ci_local.sh lance les suites dans un conteneur.
#
# Phases (D2) : 1 portable (bash tests/run_all.sh --portable, aucune variable de base), 2 base (les suites de la liste par défaut de
# tools/dbtest.sh, une seule source lue dans l'arbre testé, moins les suites propres au Mac de tests/suites_mac.txt, contre la base du
# conteneur voisin, sur la boucle locale partagée), 3 e2e (tranche 2, R-20261101-113 : les étapes de tools/e2e_steps.sh, que tools/ci_local.sh
# concatène DEVANT ce texte, lu dans le dépôt de l'outil et non dans l'arbre testé ; migrations, jeu synthétique, rôles, bundle, serveur, passe
# Playwright dans Chromium de l'image). Une phase ne commence qu'après la précédente verte ; une phase rouge marque les suivantes « sautée ».
# Sans les étapes devant ce texte (lancé seul, comme les tests de tranches 0 et 1), la phase e2e n'est pas lancée et le dit : jamais un vert de
# bout en bout. Mode rejeu (Q220) : « --rejeu <suites> » en arguments, après l'extraction : bash tests/run_all.sh <suites>, sans base ni phase base
# ou e2e (les noms passent en arguments du shell, jamais interpolés dans une commande).
# Entrée : l'archive tar de l'arbre testé, sur l'entrée standard. Variables posées par ci_local pour ce conteneur : CI_PASSAGE_CPUS
# (les processeurs du passage ; RUN_ALL_JOBS en est égal, jamais lu dans le système du conteneur) et le mot de passe de SA base. Port de
# la base et repère des suites avec base : posés ici, jamais reçus de l'appelant.
# Lignes écrites (une chacune, avant le code de sortie) :
#   ci_passage : phase <portable|base> : verte · <durée> s
#   ci_passage : phase e2e : verte · <n> tests · <durée> s   (R-20261103-6 : verte seulement si la passe a lancé au moins un test ; « 1 test » au singulier)
#   ci_passage : phase e2e : sans objet (aucune spécification de bout en bout dans l'arbre)   (jamais « verte » ; code inchangé)
#   ci_passage : phase <portable|base> : rouge · <durée> s : <suites en échec>
#   ci_passage : phase e2e : rouge · <durée> s : <cause : migrations, jeu synthétique, rôle des vues, rôle de stockage, construction du bundle,
#                serveur, passe, aucun test lancé, ou navigateur absent>
#   ci_passage : phase <base|e2e> : sautée (phase précédente rouge)
#   ci_passage : phase e2e : non lancée (étapes de bout en bout absentes du script intérieur)
#   ci_passage : navigateur absent de l'image (rebaser sur main ou reconstruire l'image)
#   ci_passage : rejeu : verte · <durée> s   ou   ci_passage : rejeu : rouge · <durée> s : <suites en échec>
#   ci_passage : base du conteneur injoignable au bout de 120 s
#   ci_passage : suites propres au Mac non lancées en phase base : <n> (<noms>)
#   ci_passage : couverture serveur : lignes <X>, branches <Y>, sautés <N>   (phase base, npm run test:coverage de mothra/server ; R-20261102-74)
#   ci_passage : mémoire au plus : <n> Mio   ou   ci_passage : mémoire au plus : non lue
# Code de sortie : celui de la première phase rouge (1 au moins) ; 0 si toutes sont vertes ; 2 sur macOS.
if [ "$(uname -s)" = Darwin ]; then
  echo "ci_passage : réservé au conteneur de la CI locale, rien n'est lancé" >&2
  exit 2
fi
set -e
mkdir -p "$HOME/depot"; cd "$HOME/depot"
tar -xf -
git init -q
git add -A -f
git -c user.name=ci-local -c user.email=ci-local@exemple.invalid commit -q -m "ci locale"
for d in /opt/ci/npm/*/; do
  n=$(basename "$d")
  [ -d "$n" ] || continue
  for m in $(cd "$d" && find . -name node_modules -type d -prune -print); do
    mkdir -p "$n/$(dirname "$m")"; cp -a "$d/$m" "$n/$m"
  done
done
set +e

cpus=${CI_PASSAGE_CPUS:-}
case "$cpus" in ""|*[!0-9]*|0) cpus=1 ;; esac

# Port de la base du conteneur voisin et repère des suites avec base : UNE définition, écrite ici, pour la phase base et la phase e2e (R-20261101-113).
# Remplace : la chaîne écrite en ligne dans la commande de la phase base. Retrait : permanent, tant que ces deux phases parlent à la même base.
BASE_ENV=(DBTEST_PORT=55432 PMZILLA_LAB_DB_PORT=55432 PMZILLA_LAB_DB_SECURITY_BIN=/usr/bin/false)

# Rejeu (Q220, R-20261101-113) : les suites nommées en arguments (déjà vérifiées par tools/ci_local.sh), sans base ni phase base ou e2e. Une suite
# rouge en phase portable l'est sans base ; la rejouer ici est le même passage, seulement filtré. Remplace : rien. Retrait : avec ci_local.sh run --rejeu.
if [ "${1:-}" = "--rejeu" ]; then
  shift
  sortie=$(mktemp)
  debut=$(date +%s)
  env -u PMZILLA_LAB_DB_PASSWORD RUN_ALL_JOBS=$cpus bash tests/run_all.sh "$@" | tee "$sortie"
  code=${PIPESTATUS[0]}
  duree=$(( $(date +%s) - debut ))
  if [ "$code" -eq 0 ] && grep -aq '^TOTAL : .*· tous réussis ·' "$sortie"; then
    echo "ci_passage : rejeu : verte · $duree s"
  else
    echecs=$(grep -a '^TOTAL : ' "$sortie" | tail -1 | sed -n 's/^TOTAL : .* suite(s) en échec : \(.*\) · durée totale.*/\1/p')
    if [ -z "$echecs" ]; then
      if grep -aq '^TOTAL : ' "$sortie"; then echecs="code $code"; else echecs="aucune ligne TOTAL du lanceur (code $code)"; fi
    fi
    [ "$code" -ne 0 ] || code=1
    echo "ci_passage : rejeu : rouge · $duree s : $echecs"
  fi
  rm -f "$sortie"
  exit "$code"
fi

# Phase 1 : portable. Les suites avec base sautent : le mot de passe de la base est retiré de cet environnement, et le repère des suites
# avec base n'y est pas posé.
sortie=$(mktemp)
debut=$(date +%s)
env -u PMZILLA_LAB_DB_PASSWORD RUN_ALL_JOBS=$cpus bash tests/run_all.sh --portable | tee "$sortie"
code=${PIPESTATUS[0]}
fin=$(date +%s)
duree=$((fin - debut))
if [ "$code" -eq 0 ] && grep -aq '^TOTAL : .*· tous réussis ·' "$sortie"; then
  echo "ci_passage : phase portable : verte · $duree s"
else
  echecs=$(grep -a '^TOTAL : ' "$sortie" | tail -1 | sed -n 's/^TOTAL : .* suite(s) en échec : \(.*\) · durée totale.*/\1/p')
  if [ -z "$echecs" ]; then
    # Désaccord avec le lanceur de l'arbre testé (option inconnue, ligne TOTAL absente) : rouge et bruyant, jamais un vert.
    if grep -aq '^TOTAL : ' "$sortie"; then echecs="code $code"; else echecs="aucune ligne TOTAL du lanceur (code $code)"; fi
  fi
  [ "$code" -ne 0 ] || code=1
  echo "ci_passage : phase portable : rouge · $duree s : $echecs"
fi
rm -f "$sortie"

# Phase 2 : base. Le port et le repère DBTEST_PORT sont ceux de la base du conteneur voisin (boucle locale partagée) ; le mot de passe est
# celui que ci_local a posé pour elle. Une base qui ne répond pas au bout de 120 s, ou une liste introuvable, est un rouge bruyant.
base_repond() { python3 -I -c 'import socket; socket.create_connection(("127.0.0.1", 55432), 2).close()' >/dev/null 2>&1; }
# Garde de la base en trust (Q269). Remplace : rien. Retrait : permanent tant que la phase base crée sa propre base.
# Une connexion avec un mot de passe construit à l'instant (jamais un littéral, lu par Python dans l'environnement) : réussir signifie que la base
# n'authentifie pas. Trois issues, jamais de faux vert : code 0 = connexion réussie (trust) ; code 10 = refus d'authentification (SQLSTATE 28P01, ou à défaut
# le message serveur « password authentication failed », car psycopg 3 peut rendre un SQLSTATE vide à la connexion) ; tout autre code (uv absent, psycopg absent,
# délai dépassé, port fermé, plantage) = garde inopérante, avec une cause courte sans secret (nom de l'exception et SQLSTATE, jamais un message du serveur).
# CI_CMD_CONNEXION remplace le client pour les tests (mot de passe faux dans CI_MDP_FAUX, mêmes codes, cause sur la première ligne de sa sortie) ;
# aucune n'est posée dans le conteneur de la CI.
CLIENT_PY='import os, sys
try:
    import psycopg
    psycopg.connect(host="127.0.0.1", port=55432, user="postgres", dbname="pmzilla", password=os.environ["CI_MDP_FAUX"], connect_timeout=5).close()
except Exception as e:
    etat = getattr(e, "sqlstate", None)
    if etat == "28P01" or "password authentication failed" in str(e):
        sys.exit(10)
    print(type(e).__name__ + (" " + str(etat) if etat else ""))
    sys.exit(11)'
GARDE_CAUSE=""
garde_authentification() { # rend 0 : connexion acceptée (trust) ; 1 : refus d'authentification ; 2 : garde inopérante (GARDE_CAUSE)
  local faux rc sortie
  faux="faux$(od -An -N8 -tx1 /dev/urandom | tr -d ' \n')"
  if [ -n "${CI_CMD_CONNEXION:-}" ]; then sortie=$(CI_MDP_FAUX="$faux" "$CI_CMD_CONNEXION" 2>/dev/null); rc=$?
  else sortie=$(CI_MDP_FAUX="$faux" uv run --no-project --with "psycopg[binary]" python -I -c "$CLIENT_PY" 2>/dev/null); rc=$?; fi
  case "$rc" in
    0) return 0 ;;
    10) return 1 ;;
  esac
  GARDE_CAUSE=$(printf '%s\n' "$sortie" | head -1 | tr -cd 'A-Za-z0-9_. -' | cut -c1-60)
  [ -n "$GARDE_CAUSE" ] || GARDE_CAUSE="client terminé avec le code $rc"
  return 2
}
if [ "$code" -ne 0 ]; then
  echo "ci_passage : phase base : sautée (phase précédente rouge)"
else
  debut=$(date +%s)
  liste=$(sed -n 's/^SUITES_PAR_DEFAUT=(\(.*\))[[:space:]]*$/\1/p' tools/dbtest.sh 2>/dev/null | head -1)
  mac=$(sed -n 's/^\([A-Za-z0-9_.-][A-Za-z0-9_.-]*\):[a-z][a-z]*.*$/\1/p' tests/suites_mac.txt 2>/dev/null | tr '\n' ' ')
  rouges=""; mac_sautees=""; nmac=0
  if [ -z "$liste" ]; then
    rouges="liste par défaut introuvable (tools/dbtest.sh)"
  else
    pret=0; i=0
    while [ "$i" -lt 120 ]; do
      if base_repond; then pret=1; break; fi
      i=$((i + 1)); sleep 1
    done
    if [ "$pret" -ne 1 ]; then
      echo "ci_passage : base du conteneur injoignable au bout de 120 s"
      rouges="base injoignable"
    else
      # Garde Q269 (R-20261101-129) : une base qui accepte un mot de passe faux est en « trust » ; les suites de sécurité n'y prouveraient rien.
      garde_authentification; garde=$?
      if [ "$garde" -eq 0 ]; then
        echo "ci_passage : base en trust : l'authentification n'est pas vérifiée"
        rouges="base en trust"
      elif [ "$garde" -eq 2 ]; then
        echo "ci_passage : garde de l'authentification inopérante : $GARDE_CAUSE"
        rouges="garde de l'authentification inopérante : $GARDE_CAUSE"
      fi
    fi
    if [ "$pret" -eq 1 ] && [ -z "$rouges" ]; then
      for s in $liste; do
        case " $mac " in
          *" $s "*) nmac=$((nmac + 1)); mac_sautees="${mac_sautees:+$mac_sautees }$s"; continue ;;
        esac
        sortie_s=$(mktemp)
        env -u PMZILLA_LAB_DB_URL RUN_ALL_JOBS=$cpus "${BASE_ENV[@]}" bash tests/run_all.sh "$s" | tee "$sortie_s"
        c=${PIPESTATUS[0]}
        if [ "$c" -ne 0 ] || ! grep -aq '^TOTAL : .*· tous réussis ·' "$sortie_s"; then rouges="${rouges:+$rouges, }$s"; fi
        rm -f "$sortie_s"
      done
      # Couverture du serveur de Mothra (R-20261102-74) : npm run test:coverage dans mothra/server, avec les variables de la base jetable des suites
      # ci-dessus. Remplace : rien. Retrait : permanent, tant que le plancher du serveur existe (mothra/outils/planchers-couverture.json).
      # Codes de couverture.mjs : 0 = tests verts et plancher tenu (ou plancher provisoire, seulement affiché) ; 1 = test en échec ou plancher non atteint ;
      # 2 ou autre (127 : npm absent) = lancement impossible. Rouge dans les deux derniers cas, jamais à cause d'un plancher provisoire.
      # La ligne « all files » est reprise sous une forme lisible (lignes, branches, sautés) pour que la session fixe le plancher après la première
      # mesure ; le plancher ne se fixe que sur une mesure à « sautés 0 ». La décision de lancer se prend sur le plancher, pas sur le dossier : lancée
      # seulement si mothra/outils/planchers-couverture.json existe et déclare « server » ; plancher déclaré sans mothra/server : rouge.
      # Doublon assumé : la couverture relance les tests du serveur déjà lancés par la suite mothra de la boucle (la suite mothra fait foi pour les échecs).
      # Environnement du relais npm de tests/run_all.sh (hors ligne, sans mise à jour ni audit, sans couleur, entrée fermée). Délai : CI_COUVERTURE_DELAI
      # (1200 s) quand timeout existe (image Linux).
      if [ -f mothra/outils/planchers-couverture.json ] && grep -q '"server"' mothra/outils/planchers-couverture.json; then
        if [ ! -d mothra/server ]; then
          echo "ci_passage : couverture serveur : plancher déclaré, mothra/server absent"
          rouges="${rouges:+$rouges, }couverture serveur (plancher déclaré, mothra/server absent)"
        else
          sortie_c=$(mktemp)
          delai=()
          if type -P timeout >/dev/null 2>&1; then delai=(timeout -k 5 "${CI_COUVERTURE_DELAI:-1200}"); fi
          (cd mothra/server && env -u PMZILLA_LAB_DB_URL "${BASE_ENV[@]}" npm_config_offline=true npm_config_update_notifier=false npm_config_audit=false \
             npm_config_fund=false NO_COLOR=1 "${delai[@]}" npm run test:coverage </dev/null) 2>&1 | tee "$sortie_c"
          c=${PIPESTATUS[0]}
          mesure=$(grep -a 'all files *|' "$sortie_c" | tail -1 | sed -n 's/.*all files *| *\([0-9][0-9.]*\) *| *\([0-9][0-9.]*\) *|.*/lignes \1, branches \2/p')
          sautes=$(grep -a '^[^ ]* skipped [0-9][0-9]*$' "$sortie_c" | tail -1 | sed -n 's/.* skipped \([0-9][0-9]*\)$/\1/p')
          if [ -n "$mesure" ]; then echo "ci_passage : couverture serveur : $mesure${sautes:+, sautés $sautes}"; else echo "ci_passage : couverture serveur : ligne « all files » absente de la sortie"; fi
          case "$c" in
            0) ;;
            1) rouges="${rouges:+$rouges, }couverture serveur (tests en échec ou plancher non atteint)" ;;
            124) echo "ci_passage : couverture serveur : délai dépassé"
                 rouges="${rouges:+$rouges, }couverture serveur (délai dépassé)" ;;
            *) echo "ci_passage : couverture serveur : lancement impossible (code $c)"
               rouges="${rouges:+$rouges, }couverture serveur (lancement impossible, code $c)" ;;
          esac
          rm -f "$sortie_c"
        fi
      else
        echo "ci_passage : couverture serveur : non lancée (aucun plancher du serveur dans l'arbre)"
      fi
    fi
  fi
  fin=$(date +%s)
  duree=$((fin - debut))
  [ "$nmac" -eq 0 ] || echo "ci_passage : suites propres au Mac non lancées en phase base : $nmac ($mac_sautees)"
  if [ -z "$rouges" ]; then
    echo "ci_passage : phase base : verte · $duree s"
  else
    code=1
    echo "ci_passage : phase base : rouge · $duree s : $rouges"
  fi
fi

# Phase 3 : e2e (tranche 2, D2, R-20261101-113). Les étapes (migrations, jeu synthétique, rôles, bundle, serveur Mothra, passe Playwright) sont celles
# de tools/e2e_steps.sh, concaténées devant ce texte par tools/ci_local.sh. La fonction SQL des rôles passe par psycopg : SQL et secret sur l'entrée
# standard, mot de passe du superutilisateur lu par Python dans l'environnement, jamais développé par le shell ; aucun client psql dans l'image.
# Une image sans Chromium (arbre non rebasé, ancienne clé d'image) : phase rouge, jamais sautée ni verte (Q210). Une seule ligne rouge, avec la cause (Q211).
SQL_PY='import os, sys, psycopg
sql = sys.stdin.read()
with psycopg.connect(host="127.0.0.1", port=int(os.environ["DBTEST_PORT"]), user="postgres", dbname="pmzilla", password=os.environ["PMZILLA_LAB_DB_PASSWORD"], autocommit=True) as c:
    c.execute(sql)'
e2e_sql() {
  env "${BASE_ENV[@]}" uv run --no-project --with "psycopg[binary]" python -I -c "$SQL_PY" >/dev/null 2>&1
}
navigateur_present() { # Chromium de Playwright dans l'image : PLAYWRIGHT_BROWSERS_PATH (posé par ci/Dockerfile) contient un dossier chromium*
  [ -n "${PLAYWRIGHT_BROWSERS_PATH:-}" ] && [ -n "$(find "$PLAYWRIGHT_BROWSERS_PATH" -maxdepth 1 -name 'chromium*' 2>/dev/null | head -1)" ]
}
if [ "$code" -ne 0 ]; then
  echo "ci_passage : phase e2e : sautée (phase précédente rouge)"
elif ! declare -F e2e_enchainer >/dev/null 2>&1; then
  echo "ci_passage : phase e2e : non lancée (étapes de bout en bout absentes du script intérieur)"
elif [ -z "$(find tests/e2e -name '*.spec.ts' -print -quit 2>/dev/null)" ]; then
  # Garde du nombre de tests (R-20261103-6, Q1). Remplace : rien. Retrait : permanent, tant que la phase e2e existe.
  # Aucune spécification de bout en bout dans l'arbre (la configuration Playwright lit tests/e2e/*.spec.ts) : rien à lancer, la phase est sans objet,
  # jamais « verte ».
  echo "ci_passage : phase e2e : sans objet (aucune spécification de bout en bout dans l'arbre)"
else
  debut=$(date +%s)
  cause=""; ntests=0
  if ! navigateur_present; then
    echo "ci_passage : navigateur absent de l'image (rebaser sur main ou reconstruire l'image)"
    cause="navigateur absent"
  else
    E2E_PORT_BASE=${BASE_ENV[0]#DBTEST_PORT=}; E2E_PORT_SERVEUR=3210; E2E_ATTENTE=120; E2E_RACINE=$PWD
    E2E_VARIABLES_BASE=("${BASE_ENV[@]}")
    E2E_SORTIE_PASSE=$(mktemp)
    e2e_retraits
    e2e_enchainer || cause=$E2E_CAUSE
    # Garde du nombre de tests (R-20261103-6, Q1). Remplace : rien. Retrait : permanent, tant que la phase e2e existe.
    # La phase n'est verte que si la passe a lancé au moins un test : le compte est la ligne de fin du rapporteur « line » de Playwright
    # (« N passed (3s) »), lue dans la sortie de la passe sans couleur ni retour chariot. Une passe de code 0 sans cette ligne, ou à « 0 passed »,
    # alors que l'arbre porte des spécifications, est rouge (« aucun test lancé »).
    if [ -z "$cause" ]; then
      ntests=$(tr -d '\r' < "$E2E_SORTIE_PASSE" | sed $'s/\033\\[[0-9;]*[A-Za-z]//g' | grep -aoE '[0-9]+ passed' | tail -1 | grep -aoE '[0-9]+')
      case "$ntests" in ""|*[!0-9]*) ntests=0 ;; esac
      [ "$ntests" -gt 0 ] || cause="aucun test lancé"
    fi
    rm -f "$E2E_SORTIE_PASSE"; unset E2E_SORTIE_PASSE
  fi
  fin=$(date +%s)
  duree=$((fin - debut))
  if [ -z "$cause" ]; then
    mot=tests; [ "$ntests" -gt 1 ] || mot=test
    echo "ci_passage : phase e2e : verte · $ntests $mot · $duree s"
  else
    code=1
    echo "ci_passage : phase e2e : rouge · $duree s : $cause"
  fi
fi

pic=$(cat /sys/fs/cgroup/memory.peak 2>/dev/null)
case "$pic" in
  ""|*[!0-9]*) echo "ci_passage : mémoire au plus : non lue" ;;
  *) echo "ci_passage : mémoire au plus : $((pic / 1048576)) Mio" ;;
esac
exit "$code"
