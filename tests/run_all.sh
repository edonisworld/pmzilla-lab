#!/bin/bash
# Lance toutes les suites de tests de PMZilla Lab d'un coup : les suites Python (uv run python -m unittest) de
# chaque dossier tests/<nom>/ qui contient des test_*.py, puis les tests shell (hook des noms, hook post-commit, evals_auto.sh, liens).
# Affiche une ligne par suite, le total et sort avec le code 1 si une suite a échoué (0 sinon).
#
#     bash tests/run_all.sh           toutes les suites
#     bash tests/run_all.sh watch_lab seulement les suites dont le nom est donné (dossier ou « hooks », « installation »)
#     bash tests/run_all.sh -v        en plus, la sortie complète de chaque suite
#     bash tests/run_all.sh --staged  lancement CIBLÉ : tools/select_suites.py lit l'index et choisit les suites ; il exige l'exécution
#                                     complète pour un fichier qu'aucune suite ne nomme (alors c'est un lancement complet, empreinte comprise)
#     bash tests/run_all.sh --portable  les suites absentes de tests/suites_mac.txt (conteneur de la CI locale), après la ligne
#                                     « run_all : suites propres au Mac non lancées : <n> (<nom:genre …>) »
#     bash tests/run_all.sh --mac       seulement les suites de tests/suites_mac.txt (passe Mac)
#   --portable et --mac (local-ci-container, D3) : ni empreinte écrite ni effacée, comme un lancement filtré ; avec --staged, un nom de
#   suite ou l'un avec l'autre : code 2 ; liste illisible : code 2. Liste : une ligne « <suite>:<python|shell> # <raison> » par suite
#   propre au Mac, commentaires et lignes vides permis ; un test de tests/run_all vérifie chaque entrée.
#
# Codes de sortie : 0 tout vert, 1 une suite en échec, 2 usage ou aucune suite trouvée sans nom donné, 4 fin de branche en cours (gel),
# 5 des noms de suites donnés dont aucun ne correspond à une suite (« run_all : aucune suite ne correspond aux noms donnés (<noms>) » : aucune
# suite lancée, aucune empreinte ni durée écrite ; deux noms dont un existe lancent celui-là ; --staged garde son code 2, le sélecteur décide).
#
# Un test shell listé mais absent du disque est un ÉCHEC nommé (jamais un saut silencieux) ; un filtre ne concerne que ses suites.
# Un script de test shell sous tests/ qui n'est pas listé ci-dessous doit être déclaré auxiliaire (lignes « AUXILIAIRE »), sinon
# tests/run_all/test_run_all.py échoue en le nommant.
# AUXILIAIRE tests/db_scripts/test_db_restore_test.sh : lancé par tests/db_scripts/test_db_scripts.sh (suite voisine) ; le lister le ferait tourner deux fois.
# AUXILIAIRE tests/db_scripts/test_db_rehearsal.sh : lancé par tests/db_scripts/test_db_scripts.sh (suite voisine) ; le lister le ferait tourner deux fois.
#
# Garde-fou de commit : PMZILLA_NO_EVALS (réservée à git commit) fait refuser le lancement (code 2). Un lancement COMPLET (sans nom
# de suite) qui se termine sans échec écrit l'empreinte de l'index (git write-tree) dans .git/pmzilla-run-all-ok ; le hook pre-commit
# refuse le commit si elle ne correspond pas à l'index. Donc : git add, puis run_all.sh && git commit. Un lancement filtré n'écrit rien.
# Un lancement ciblé (--staged) efface d'abord l'empreinte ciblée précédente (.git/pmzilla-run-targeted-ok), puis, s'il se termine sans
# échec, y écrit l'empreinte de l'index : sur une branche de travail, le hook pre-commit accepte l'une ou l'autre ; sur main, jamais la ciblée.
# Un lancement ciblé n'écrit ni n'efface l'empreinte complète (sauf s'il a dû passer en exécution complète).
#
# Base de données (test-speed-2, D2) : hors passage de la base jetable (DBTEST_PORT, posé par tools/dbtest.sh, absent ou vide), le lanceur
# retire de l'environnement de chaque suite, Python ou shell, toute variable PMZILLA_LAB_DB_* et l'écrit en une ligne avant la première suite ;
# avec DBTEST_PORT, elles passent telles quelles. Son propre environnement, ses codes et ses empreintes ne changent pas.
#
# Gel pendant une fin de branche (multi-session-piloting, D7) : après ses contrôles d'usage et avant toute suite, le lanceur cherche le verrou
# de fin de branche (dossier pmzilla-fin-en-cours du dossier Git commun de sa racine ; une racine injectée lit le verrou de CETTE racine seulement).
# Un verrou vivant dont le jeton n'est pas celui de FINISH_LOCK_TOKEN (variable absente comprise) : code 4, « run_all : fin de branche en cours
# (<branche>), lancement refusé », aucune suite, aucune empreinte écrite ni effacée, aucune ligne de durées, aucune attente ; lancement complet,
# ciblé ou filtré. Jeton égal ou verrou absent : rien ne change. Verrou périmé (processus mort, plus vieux que PMZILLA_FINISH_LOCK_MAX_AGE
# secondes, 21600 par défaut, ou sans pid lisible depuis plus de dix secondes) : « run_all : verrou de fin périmé, ignoré », puis le lancement
# continue. Le lanceur ne crée, ne retire ni ne modifie jamais le verrou.
#
# Tests sautés (test-speed-2, D25) : après la liste des plus lentes et avant la ligne de total, « Tests sautés : <total> (suites Python <p>,
# branches shell <s>) ». Suite Python : le nombre après « skipped= » de sa dernière ligne (0 sans) ; suite shell : les lignes de sa sortie
# qui commencent par « saut : » (une par branche sautée) ; une suite en délai dépassé compte 0. Ni les lignes de suite, ni le total, ni le
# fichier des durées, ni les codes ne changent.
# Sauts d'une suite shell (skips-visible, D1) : s'il y en a, sa ligne les montre dans le verdict, « OK (sautés=<n>) » ou
# « ÉCHEC (code <c>, <r> échec(s), sautés=<n>) » ; sans saut, la ligne est celle d'avant. Le même compte sert à la ligne « Tests sautés ».
#
# Suites en parallèle (test-speed-2, D19 à D23). RUN_ALL_JOBS : nombre entier positif de suites à la fois (autre valeur : code 2 avant toute
# suite) ; par défaut la moitié des processeurs logiques (sysctl -n hw.logicalcpu, à défaut getconf _NPROCESSORS_ONLN), au moins 1, 1 si
# illisible. Avec 1 : le passage en
# série d'avant, mêmes lignes dans le même ordre. Avec plus d'une tâche, une ligne « run_all : <n> suites à la fois, puis en série : <liste> »
# précède la première suite. Les suites de EN_SERIE ci-dessous passent après toutes les autres, une à la fois, dans l'ordre déclaré ;
# script_dependencies (la plus longue) part la première. Avec DBTEST_PORT (base jetable) : toutes les suites une à la fois (les rôles de la
# base sont communs à l'instance). Chaque suite garde son groupe de processus, son chien de garde, son entrée fermée et sa sortie, reçoit
# son propre TMPDIR (retiré à la fin) et PYTHONDONTWRITEBYTECODE=1, en série comme en parallèle. Les lignes sortent dans l'ordre déclaré
# (dossiers Python, puis liste shell), chacune dès que sa suite et toutes les précédentes ont fini ; la durée d'une suite est la sienne.
# Une suite est la paire (nom, genre) : « offsite_backup » Python et shell sont deux suites. Sondage toutes les dixièmes de seconde (bash 3.2
# n'a pas wait -n). Interruption (INT, TERM) : TERM puis KILL sur chaque groupe en cours, fichiers temporaires retirés, aucune empreinte,
# sortie par le signal reçu.
#
# Aucun appel réseau ni payant ; chaque suite travaille dans un dossier temporaire (voir son en-tête).
# Variables (pour les tests de ce script) : RUN_ALL_ROOT (racine du dépôt), RUN_ALL_DEPS (options `uv run --with …`).
# Délai par suite : RUN_ALL_SUITE_TIMEOUT (secondes entières, défaut 900). Une suite plus longue est arrêtée avec ses processus
# (TERM puis KILL sur son groupe), comptée en échec « délai dépassé », et le lanceur passe à la suivante. Valeur invalide : code 2.
# Mesures (change test-speed) : chaque ligne de suite finit par sa durée (« · 12,3 s »), les dix suites les plus lentes sont listées avant
# la ligne de total, qui finit par « durée totale ». Une ligne par suite est ajoutée au fichier des durées (dix champs séparés par une
# tabulation), mesures/run_all-durees.tsv du dossier de données du lab (tools/lab_paths.sh), commun à l'espace de travail et aux worktrees ;
# jamais de chemin, de nom de test ni de sortie. RUN_ALL_DURATIONS désigne un autre fichier ; sur une racine injectée (RUN_ALL_ROOT) sans
# cette variable, aucun fichier n'est écrit. Une panne de mesure est dite en une ligne et ne change ni le code, ni les lignes, ni les empreintes.
set -u
exec </dev/null   # entrée standard fermée : aucune suite, aucun outil lancé par une suite ne peut attendre le clavier (D1)
RACINE="${RUN_ALL_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
# pymupdf4llm<2 : la 2.0 (parue le 2026-10-19) ne déclare plus pymupdf, que les suites de convert_books importent.
DEPS="${RUN_ALL_DEPS---with numpy --with httpx --with pyyaml --with requests --with feedparser --with trafilatura --with beautifulsoup4 --with markdownify --with "pymupdf4llm<2" --with ebooklib --with "psycopg[binary]" --with jsonschema}"
BAVARD=0
CIBLE=0
MODE=""   # vide, portable ou mac (local-ci-container, D3)
NOMS=()
for argument in "$@"; do
  case "$argument" in
    -v) BAVARD=1 ;;
    --staged) CIBLE=1 ;;
    --portable|--mac)
      if [ -n "$MODE" ]; then echo "run_all : --portable et --mac ne se combinent pas"; exit 2; fi
      MODE=${argument#--} ;;
    *) NOMS+=("$argument") ;;
  esac
done
if [ "$CIBLE" -eq 1 ] && [ ${#NOMS[@]} -gt 0 ]; then
  echo "run_all : --staged ne se combine pas avec des noms de suites (${NOMS[*]})"
  exit 2
fi
if [ -n "$MODE" ] && [ "$CIBLE" -eq 1 ]; then
  echo "run_all : --$MODE ne se combine pas avec --staged"
  exit 2
fi
if [ -n "$MODE" ] && [ ${#NOMS[@]} -gt 0 ]; then
  echo "run_all : --$MODE ne se combine pas avec des noms de suites (${NOMS[*]})"
  exit 2
fi
DELAI="${RUN_ALL_SUITE_TIMEOUT-900}"
case "$DELAI" in
  ''|*[!0-9]*|0*) echo "run_all : délai par suite invalide ($DELAI) : un nombre entier de secondes est attendu"; exit 2 ;;
esac
if [ -n "${RUN_ALL_JOBS+x}" ]; then
  case "$RUN_ALL_JOBS" in
    ''|*[!0-9]*|0*) echo "run_all : nombre de tâches invalide ($RUN_ALL_JOBS) : un nombre entier positif est attendu"; exit 2 ;;
  esac
  TACHES=$RUN_ALL_JOBS
else
  processeurs=$(sysctl -n hw.logicalcpu 2>/dev/null) || processeurs=""
  case "$processeurs" in   # sysctl illisible (Linux, conteneur de la CI locale) : getconf avant le repli à 1 (local-ci-container, D3)
    ''|*[!0-9]*) processeurs=$(getconf _NPROCESSORS_ONLN 2>/dev/null) || processeurs="" ;;
  esac
  case "$processeurs" in
    ''|*[!0-9]*) TACHES=1 ;;
    *) TACHES=$(( processeurs / 2 )); [ "$TACHES" -ge 1 ] || TACHES=1 ;;
  esac
fi
[ -z "${DBTEST_PORT:-}" ] || TACHES=1   # base jetable : une suite à la fois
cd "$RACINE" || { echo "Racine introuvable : $RACINE"; exit 2; }

# Suites propres au Mac (local-ci-container, D3) : lues seulement avec --portable ou --mac, une entrée « nom:genre » par ligne.
LISTE_MAC=()
if [ -n "$MODE" ]; then
  if [ ! -r tests/suites_mac.txt ]; then
    echo "run_all : liste des suites propres au Mac illisible (tests/suites_mac.txt)"
    exit 2
  fi
  while IFS= read -r entree || [ -n "$entree" ]; do
    entree=${entree%%#*}; entree=${entree//[[:space:]]/}
    [ -n "$entree" ] && LISTE_MAC+=("$entree")
  done < tests/suites_mac.txt
fi

if [ -n "${PMZILLA_NO_EVALS+x}" ]; then
  echo "PMZILLA_NO_EVALS est définie : variable réservée à git commit (elle coupe le jeu d'essai du hook post-commit)."
  echo "Elle fausse les tests du hook : relance sans elle (env -u PMZILLA_NO_EVALS bash tests/run_all.sh)."
  exit 2
fi

# Gel pendant une fin de branche (multi-session-piloting, D7) : lecture seule du verrou du dossier Git commun de la racine.
gel_perime() {   # dossier : 0 si le verrou est périmé, 1 s'il est tenu (même règle que tools/finish_lock.sh)
  local dossier=$1 max="${PMZILLA_FINISH_LOCK_MAX_AGE:-21600}" pid debut mtime age now
  case "$max" in ''|*[!0-9]*) max=21600 ;; esac
  now=$(date +%s)
  pid=$(cat "$dossier/pid" 2>/dev/null)
  case "$pid" in
    ''|*[!0-9]*)
      mtime=$(stat -f %m "$dossier" 2>/dev/null || stat -c %Y "$dossier" 2>/dev/null)
      case "$mtime" in ''|*[!0-9]*) return 1 ;; esac
      [ $(( now - mtime )) -gt 10 ] && return 0
      return 1 ;;
  esac
  kill -0 "$pid" 2>/dev/null || return 0
  debut=$(cat "$dossier/debut" 2>/dev/null)
  case "$debut" in
    ''|*[!0-9]*)
      mtime=$(stat -f %m "$dossier" 2>/dev/null || stat -c %Y "$dossier" 2>/dev/null)
      case "$mtime" in ''|*[!0-9]*) return 1 ;; esac
      age=$(( now - mtime )) ;;
    *) age=$(( now - debut )) ;;
  esac
  [ "$age" -gt "$max" ] && return 0
  return 1
}
GEL_COMMUN=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)   # vide hors dépôt Git (faux dépôt des tests)
if [ -n "$GEL_COMMUN" ] && [ -d "$GEL_COMMUN/pmzilla-fin-en-cours" ]; then
  if gel_perime "$GEL_COMMUN/pmzilla-fin-en-cours"; then
    echo "run_all : verrou de fin périmé, ignoré"
  elif [ -z "${FINISH_LOCK_TOKEN:-}" ] || [ "$(cat "$GEL_COMMUN/pmzilla-fin-en-cours/jeton" 2>/dev/null)" != "$FINISH_LOCK_TOKEN" ]; then
    echo "run_all : fin de branche en cours ($(cat "$GEL_COMMUN/pmzilla-fin-en-cours/branche" 2>/dev/null || echo '?')), lancement refusé"
    exit 4
  fi
fi

EMPREINTE=$(git rev-parse --git-path pmzilla-run-all-ok 2>/dev/null)   # vide hors dépôt Git (faux dépôt des tests)
EMPREINTE_CIBLEE=$(git rev-parse --git-path pmzilla-run-targeted-ok 2>/dev/null)
ECRIRE_CIBLEE=0
if [ "$CIBLE" -eq 1 ]; then
  [ -n "$EMPREINTE_CIBLEE" ] && rm -f "$EMPREINTE_CIBLEE"           # un lancement ciblé invalide d'abord l'empreinte ciblée précédente
  selection=$(python3 "$(dirname "$0")/../tools/select_suites.py" --root "$RACINE" 2>&1); code_selection=$?
  printf '%s\n' "$selection"
  if [ "$code_selection" -eq 0 ]; then
    while IFS= read -r nom_suite; do [ -n "$nom_suite" ] && NOMS+=("$nom_suite"); done < <(printf '%s\n' "$selection" | sed -n 's/^select_suites : \([^ ]*\) : .*/\1/p')
    ECRIRE_CIBLEE=1
  elif [ "$code_selection" -ne 3 ]; then
    echo "run_all : le sélecteur a échoué (code $code_selection) : exécution complète"
  fi
  echo
fi
[ ${#NOMS[@]} -eq 0 ] && [ -z "$MODE" ] && [ -n "$EMPREINTE" ] && rm -f "$EMPREINTE"   # un lancement complet invalide l'empreinte précédente

if [ "${PMZILLA_ENTREES_JUGE_CHANGEES:-}" = "1" ]; then
  echo "ATTENTION : PMZILLA_ENTREES_JUGE_CHANGEES=1 : le test des entrées du juge (tests/posture_evals/test_entrees_juge.py) est IGNORÉ."
  echo "            Le commit qui change ces entrées doit le dire dans son message (« Entrées du juge modifiées : … ») ; plan 6.2."
  echo
fi

# Variables de la base (test-speed-2, D2) : hors passage de la base jetable (DBTEST_PORT absent ou vide), aucune suite ne reçoit de variable
# PMZILLA_LAB_DB_* (adresse, port, mots de passe, Trousseau) ; l'environnement du lanceur lui-même ne change pas.
RETRAIT=()
if [ -z "${DBTEST_PORT:-}" ]; then
  while IFS= read -r nom_variable; do
    [ -n "$nom_variable" ] && RETRAIT+=(-u "$nom_variable")
  done < <(compgen -e PMZILLA_LAB_DB_)
  if [ ${#RETRAIT[@]} -gt 0 ]; then
    echo "run_all : variables PMZILLA_LAB_DB_* retirées de l'environnement des suites (la base jetable passe par tools/dbtest.sh)"
  fi
fi

# Suites passées en série après toutes les autres (D20), chacune avec son genre et sa raison ; un test vérifie que chaque entrée nomme
# une suite existante du genre dit. Inventaire complet : annexe B de openspec/changes/test-speed-2/design.md.
EN_SERIE=(
  run_all:python   # lanceur imbriqué sur des racines factices : fenêtres d'une seconde pour des suites lancées par uv, processus sleep à tuer
  dbtest:shell     # signaux (kill -INT du processus lancé, relais SIGINT, #242) : en série par prudence, pas par obligation
)
PREMIERE_SUITE=script_dependencies   # la suite la plus longue part la première quand plusieurs suites tournent ensemble

voulue() {   # sans nom donné, tout est voulu
  [ ${#NOMS[@]} -eq 0 ] && return 0
  for nom in "${NOMS[@]}"; do [ "$nom" = "$1" ] && return 0; done
  return 1
}

SAUTEES_MAC=()
retenue() {   # nom genre : la suite est-elle lancée selon --portable / --mac ? (sans option, toujours) ; note les suites sautées
  local entree dans=1
  [ -z "$MODE" ] && return 0
  for entree in ${LISTE_MAC[@]+"${LISTE_MAC[@]}"}; do [ "$entree" = "$1:$2" ] && dans=0; done
  if [ "$MODE" = mac ]; then return $dans; fi
  [ "$dans" -eq 0 ] && { SAUTEES_MAC+=("$1:$2"); return 1; }
  return 0
}

en_serie() {   # nom genre : la suite est-elle dans EN_SERIE ?
  local entree
  for entree in "${EN_SERIE[@]}"; do
    entree=${entree%%#*}; entree=${entree%"${entree##*[! ]}"}
    [ "$entree" = "$1:$2" ] && return 0
  done
  return 1
}

# Les suites dans l'ordre déclaré : dossiers Python, puis liste shell. Une suite est la paire (nom, genre).
SU_NOM=(); SU_GENRE=(); SU_CHEMIN=(); SU_INTERP=(); SU_ABSENT=(); SU_SERIE=()
for dossier in tests/*/; do
  nom=$(basename "$dossier")
  ls "$dossier"test_*.py >/dev/null 2>&1 || continue
  voulue "$nom" || continue
  retenue "$nom" python || continue
  SU_NOM+=("$nom"); SU_GENRE+=(python); SU_CHEMIN+=("$dossier"); SU_INTERP+=(""); SU_ABSENT+=(0)
  if en_serie "$nom" python; then SU_SERIE+=(1); else SU_SERIE+=(0); fi
done
for test in tests/hooks/test_pre_commit.sh:hooks:sh tests/hooks/test_post_commit.sh:post-commit:sh tests/hooks/test_commit_msg.sh:commit-msg:sh tests/hooks/test_pre_commit_green.sh:pre-commit-green:sh tests/hooks/test_pre_push.sh:pre-push:sh tests/hooks/test_lock_hooks.sh:lock-hooks:sh tests/evals_auto/test_evals_auto.sh:evals_auto:sh tests/installation/test_install_links.sh:installation:zsh tests/installation/test_install_hooks.sh:install_hooks:sh tests/db_scripts/test_db_scripts.sh:db_scripts:bash tests/db_scripts/test_dbtest.sh:dbtest:bash tests/offsite_backup/test_offsite_backup.sh:offsite_backup:bash tests/finish_branch/test_finish_branch.sh:finish_branch:bash tests/worktree/test_worktree.sh:worktree:bash tests/finish_worktree/test_finish_worktree.sh:finish_worktree:bash tests/run_worktree/test_run_worktree.sh:run_worktree:bash tests/morning_state/test_morning_state.sh:morning_state:bash tests/ci_local/test_ci_local.sh:ci_local:bash tests/branch_sync/test_branch_sync.sh:branch_sync:bash; do
  chemin=${test%%:*}; reste=${test#*:}; nom=${reste%%:*}; interprete=${reste#*:}
  voulue "$nom" || continue
  retenue "$nom" shell || continue
  SU_NOM+=("$nom"); SU_GENRE+=(shell); SU_CHEMIN+=("$chemin"); SU_INTERP+=("$interprete")
  if [ -f "$chemin" ]; then SU_ABSENT+=(0); else SU_ABSENT+=(1); fi
  if en_serie "$nom" shell; then SU_SERIE+=(1); else SU_SERIE+=(0); fi
done
NB=${#SU_NOM[@]}
if [ "$MODE" = portable ]; then
  liste_sautees="${SAUTEES_MAC[*]+${SAUTEES_MAC[*]}}"
  echo "run_all : suites propres au Mac non lancées : ${#SAUTEES_MAC[@]} (${liste_sautees:-aucune})"
fi

# Ordre de départ : avec une seule tâche, l'ordre déclaré ; avec plusieurs, les suites en parallèle (la plus longue d'abord), puis les
# suites en série dans l'ordre déclaré.
DEPART=()
if [ "$TACHES" -le 1 ]; then
  i=0; while [ "$i" -lt "$NB" ]; do DEPART+=("$i"); i=$((i + 1)); done
else
  i=0; while [ "$i" -lt "$NB" ]; do
    [ "${SU_SERIE[$i]}" = 0 ] && [ "${SU_NOM[$i]}" = "$PREMIERE_SUITE" ] && [ "${SU_GENRE[$i]}" = python ] && DEPART+=("$i")
    i=$((i + 1))
  done
  i=0; while [ "$i" -lt "$NB" ]; do
    [ "${SU_SERIE[$i]}" = 0 ] && ! { [ "${SU_NOM[$i]}" = "$PREMIERE_SUITE" ] && [ "${SU_GENRE[$i]}" = python ]; } && DEPART+=("$i")
    i=$((i + 1))
  done
  liste_serie=""
  i=0; while [ "$i" -lt "$NB" ]; do
    if [ "${SU_SERIE[$i]}" = 1 ]; then DEPART+=("$i"); liste_serie="${liste_serie:+$liste_serie, }${SU_NOM[$i]}"; fi
    i=$((i + 1))
  done
  echo "run_all : $TACHES suites à la fois, puis en série : ${liste_serie:-aucune}"
fi

RUN=$(mktemp -d "${TMPDIR:-/tmp}/pmzilla-suites.XXXXXX") || { echo "run_all : dossier temporaire impossible"; exit 2; }
RUNNING=(); WRAP=()

# Arrête les suites en cours : TERM puis KILL sur le groupe de chacune et sur son chien de garde.
arreter_suites() {
  local k=0 i pid garde
  while [ "$k" -lt "${#RUNNING[@]}" ]; do
    i=${RUNNING[$k]}
    pid=$(cat "$RUN/pid.$i" 2>/dev/null); garde=$(cat "$RUN/garde.$i" 2>/dev/null)
    [ -n "$garde" ] && kill -TERM -- "-$garde" >/dev/null 2>&1
    kill -TERM "${WRAP[$i]}" >/dev/null 2>&1
    [ -n "$pid" ] && kill -TERM -- "-$pid" >/dev/null 2>&1
    k=$((k + 1))
  done
  sleep 1
  k=0
  while [ "$k" -lt "${#RUNNING[@]}" ]; do
    i=${RUNNING[$k]}
    pid=$(cat "$RUN/pid.$i" 2>/dev/null); garde=$(cat "$RUN/garde.$i" 2>/dev/null)
    [ -n "$garde" ] && kill -KILL -- "-$garde" >/dev/null 2>&1
    kill -KILL "${WRAP[$i]}" >/dev/null 2>&1
    [ -n "$pid" ] && kill -KILL -- "-$pid" >/dev/null 2>&1
    k=$((k + 1))
  done
}
interrompre() {   # signal : arrêt des suites, nettoyage, sortie par le signal reçu (comme un lanceur interrompu d'avant)
  trap '' INT TERM
  arreter_suites
  rm -rf "$RUN"
  trap - EXIT; trap - "$1"
  kill -s "$1" $$
}
trap 'rm -rf "$RUN"' EXIT
trap 'interrompre INT' INT
trap 'interrompre TERM' TERM

total=0; ignores=0; suites=0; echecs=0; echouees=(); sautes_python=0; sautes_shell=0
ligne() { printf "%-22s %5s tests · %s\n" "$1" "$2" "$3"; }

# Mesures (change test-speed, D1 à D4). Horloge en millisecondes par perl (Time::HiRes), à défaut les secondes entières du shell.
horloge() {
  local t
  t=$(perl -MTime::HiRes=time -e 'printf "%d\n", time() * 1000' 2>/dev/null) || t=""
  case "$t" in ''|*[!0-9]*) t=$(( $(date +%s) * 1000 )) ;; esac
  printf '%s' "$t"
}
duree() { printf '%d,%d' $(( $1 / 1000 )) $(( ($1 % 1000) / 100 )); }          # 12,3 (virgule décimale, pour l'affichage)
duree_point() { printf '%d.%d' $(( $1 / 1000 )) $(( ($1 % 1000) / 100 )); }    # 12.3 (point décimal, pour le fichier)
DEBUT_TOTAL=$(horloge)
DATE_DEBUT=$(date +%Y-%m-%dT%H:%M:%S)
IDENTIFIANT="$DATE_DEBUT-$$"
if [ "$CIBLE" -eq 1 ] && [ "$ECRIRE_CIBLEE" -eq 1 ]; then GENRE="ciblé"; elif [ ${#NOMS[@]} -eq 0 ] && [ -z "$MODE" ]; then GENRE="complet"; else GENRE="filtré"; fi
POSTE="espace"
if [ "$(cd "$(git rev-parse --git-dir 2>/dev/null)" 2>/dev/null && pwd -P)" != "$(cd "$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null && pwd -P)" ]; then POSTE="worktree"; fi
# Fichier des durées : RUN_ALL_DURATIONS, sinon (hors racine injectée) mesures/run_all-durees.tsv du dossier de données du lab.
DUREES_FICHIER=""; DUREES_PANNE=""
if [ -n "${RUN_ALL_DURATIONS:-}" ]; then
  DUREES_FICHIER=$RUN_ALL_DURATIONS
elif [ -z "${RUN_ALL_ROOT+x}" ]; then
  donnees=$( ( . "$(dirname "$0")/../tools/lab_paths.sh" 2>/dev/null && lab_paths_init 2>/dev/null && printf '%s' "$LAB_DATA_FOLDER" ) ) || donnees=""
  if [ -n "$donnees" ]; then DUREES_FICHIER="$donnees/mesures/run_all-durees.tsv"; else DUREES_PANNE="dossier de données introuvable"; fi
fi
LENTES=""; RANG=0
noter_suite() { # nom étiquette type verdict temps-unittest : liste des plus lentes et ligne du fichier des durées
  RANG=$((RANG + 1))
  LENTES="$LENTES$MS"$'\t'"$RANG"$'\t'"$2"$'\n'
  [ -n "$DUREES_FICHIER" ] && [ -z "$DUREES_PANNE" ] || return 0
  if [ ! -s "$DUREES_FICHIER" ]; then
    ( umask 077; mkdir -p "$(dirname "$DUREES_FICHIER")" ) 2>/dev/null \
      && printf 'lancement\tidentifiant\tgenre\tposte\tsuite\ttype\tsecondes\tsecondes_unittest\tverdict\traison\n' >> "$DUREES_FICHIER" 2>/dev/null \
      || { DUREES_PANNE="écriture impossible"; return 0; }
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t\n' "$DATE_DEBUT" "$IDENTIFIANT" "$GENRE" "$POSTE" "$1" "$3" "$(duree_point "$MS")" "$5" "$4" \
    >> "$DUREES_FICHIER" 2>/dev/null || DUREES_PANNE="écriture impossible"
}

# Lance la suite d'indice $1 en arrière-plan : un processus relais qui met la suite dans son propre groupe de processus (set -m ; pas de
# commande timeout sur le bash 3.2 de macOS) avec un chien de garde : TERM sur le groupe à l'échéance, puis KILL après 2 s. Le relais
# écrit fin.<i> (code, délai dépassé, horloge de début, horloge de fin) quand plus aucun processus de la suite ne reste.
demarrer_suite() {
  local i=$1
  mkdir "$RUN/tmp.$i"
  (
    local debut fin pid garde code delai_depasse=0 drapeau="$RUN/delai.$i"
    debut=$(horloge)
    set -m
    if [ "${SU_GENRE[$i]}" = python ]; then
      # shellcheck disable=SC2086
      env ${RETRAIT[@]+"${RETRAIT[@]}"} PYTHONDONTWRITEBYTECODE=1 TMPDIR="$RUN/tmp.$i" \
        uv run $DEPS python -W ignore -m unittest discover -s "${SU_CHEMIN[$i]}" >"$RUN/sortie.$i" 2>&1 &
    else
      env ${RETRAIT[@]+"${RETRAIT[@]}"} PYTHONDONTWRITEBYTECODE=1 TMPDIR="$RUN/tmp.$i" \
        "${SU_INTERP[$i]}" "${SU_CHEMIN[$i]}" >"$RUN/sortie.$i" 2>&1 &
    fi
    pid=$!
    printf '%s' "$pid" > "$RUN/pid.$i"
    ( sleep "$DELAI"; : >"$drapeau"; kill -TERM -- "-$pid"; sleep 2; kill -KILL -- "-$pid" ) >/dev/null 2>&1 &
    garde=$!
    printf '%s' "$garde" > "$RUN/garde.$i"
    set +m
    { wait "$pid"; code=$?; } 2>/dev/null
    if [ -f "$drapeau" ]; then
      delai_depasse=1
      { wait "$garde"; } 2>/dev/null   # le chien de garde finit son KILL : plus aucun processus de la suite
    else
      kill -TERM -- "-$garde" >/dev/null 2>&1
      { wait "$garde"; } 2>/dev/null
      kill -KILL -- "-$pid" >/dev/null 2>&1   # descendants éventuels restés après la fin normale
    fi
    fin=$(horloge)
    printf '%s %s %s %s\n' "$code" "$delai_depasse" "$debut" "$fin" > "$RUN/fin.$i.ecrit"
    mv "$RUN/fin.$i.ecrit" "$RUN/fin.$i"
  ) &
  WRAP[$i]=$!
}

# Affiche la ligne de la suite d'indice $1 (sa suite et toutes les précédentes ont fini) et compte son résultat.
afficher_suite() {
  local i=$1 nom genre etiquette code delai_depasse debut fin n temps_unittest bilan reussis rates
  nom=${SU_NOM[$i]}; genre=${SU_GENRE[$i]}
  if [ "$genre" = python ]; then etiquette=$nom; else etiquette="$nom (shell)"; fi
  if [ "${SU_ABSENT[$i]}" = 1 ]; then
    ligne "$etiquette" "?" "ÉCHEC : script listé mais absent : ${SU_CHEMIN[$i]}"
    suites=$((suites + 1)); echecs=$((echecs + 1)); echouees+=("$nom (${SU_CHEMIN[$i]} absent)")
    return
  fi
  read -r code delai_depasse debut fin < "$RUN/fin.$i"
  MS=$(( fin - debut )); [ "$MS" -ge 0 ] || MS=0; DUREE_TXT=$(duree "$MS")
  sortie=$(cat "$RUN/sortie.$i")
  if [ "$delai_depasse" -eq 1 ]; then
    if [ "$genre" = python ]; then noter_suite "$nom" "$etiquette" python "délai" ""; else noter_suite "$nom" "$etiquette" shell "délai" ""; fi
    ligne "$etiquette" "?" "ÉCHEC : délai dépassé ($DELAI s) · $DUREE_TXT s"
    printf '%s\n' "$sortie" | tail -30 | sed 's/^/    /'
    suites=$((suites + 1)); echecs=$((echecs + 1)); echouees+=("$nom (délai dépassé)")
    return
  fi
  if [ "$genre" = python ]; then
    n=$(printf '%s\n' "$sortie" | sed -n 's/^Ran \([0-9][0-9]*\) test.*/\1/p' | tail -1)
    temps_unittest=$(printf '%s\n' "$sortie" | sed -n 's/^Ran [0-9][0-9]* tests\{0,1\} in \([0-9][0-9]*\.[0-9]*\)s.*/\1/p' | tail -1)
    bilan=$(printf '%s\n' "$sortie" | tail -1)
    sautes_python=$((sautes_python + $(printf '%s\n' "$bilan" | sed -n 's/.*skipped=\([0-9][0-9]*\).*/\1/p' | tail -1 | grep . || echo 0)))
    suites=$((suites + 1)); total=$((total + ${n:-0}))
    if [ "$code" -eq 0 ] && [ -n "$n" ]; then
      noter_suite "$nom" "$etiquette" python ok "$temps_unittest"
      ligne "$etiquette" "$n" "$bilan · $DUREE_TXT s"
      [ "$BAVARD" -eq 1 ] && printf '%s\n' "$sortie"
    else
      noter_suite "$nom" "$etiquette" python "échec" "$temps_unittest"
      ligne "$etiquette" "${n:-?}" "ÉCHEC (code $code) : $bilan · $DUREE_TXT s"
      printf '%s\n' "$sortie" | tail -30 | sed 's/^/    /'
      echecs=$((echecs + 1)); echouees+=("$nom")
    fi
  else
    reussis=$(printf '%s\n' "$sortie" | sed -n 's/^\([0-9][0-9]*\) réussis, [0-9][0-9]* échec.*/\1/p' | tail -1)
    rates=$(printf '%s\n' "$sortie" | sed -n 's/^[0-9][0-9]* réussis, \([0-9][0-9]*\) échec.*/\1/p' | tail -1)
    n=$(( ${reussis:-0} + ${rates:-0} ))
    sautes_suite=$(printf '%s\n' "$sortie" | grep -c '^saut :')   # une ligne « saut : … » par branche sautée, comptée une fois (skips-visible, D1)
    sautes_shell=$((sautes_shell + sautes_suite))
    mention_sauts=""; mention_sauts_echec=""
    if [ "$sautes_suite" -gt 0 ]; then mention_sauts=" (sautés=$sautes_suite)"; mention_sauts_echec=", sautés=$sautes_suite"; fi
    suites=$((suites + 1)); total=$((total + n))
    if [ "$code" -eq 0 ] && [ -n "$reussis" ] && [ "${rates:-1}" -eq 0 ]; then
      noter_suite "$nom" "$etiquette" shell ok ""
      ligne "$etiquette" "$n" "OK$mention_sauts · $DUREE_TXT s"
      [ "$BAVARD" -eq 1 ] && printf '%s\n' "$sortie"
    else
      noter_suite "$nom" "$etiquette" shell "échec" ""
      ligne "$etiquette" "$n" "ÉCHEC (code $code, ${rates:-?} échec(s)$mention_sauts_echec) · $DUREE_TXT s"
      printf '%s\n' "$sortie" | tail -30 | sed 's/^/    /'
      echecs=$((echecs + 1)); echouees+=("$nom")
    fi
  fi
}

# Boucle de planification : terminer, lancer, afficher dans l'ordre déclaré, attendre.
ETAT=()   # 0 à lancer, 1 en cours, 2 fini
i=0; while [ "$i" -lt "$NB" ]; do ETAT+=(0); i=$((i + 1)); done
prochain=0; affiche=0; nb_depart=${#DEPART[@]}
while [ "$affiche" -lt "$NB" ]; do
  restantes=(); k=0
  while [ "$k" -lt "${#RUNNING[@]}" ]; do
    i=${RUNNING[$k]}
    if [ -f "$RUN/fin.$i" ]; then ETAT[$i]=2; else restantes+=("$i"); fi
    k=$((k + 1))
  done
  RUNNING=(); k=0
  while [ "$k" -lt "${#restantes[@]}" ]; do RUNNING+=("${restantes[$k]}"); k=$((k + 1)); done
  while [ "$prochain" -lt "$nb_depart" ] && [ "${#RUNNING[@]}" -lt "$TACHES" ]; do
    i=${DEPART[$prochain]}
    if [ "$TACHES" -gt 1 ] && [ "${SU_SERIE[$i]}" = 1 ] && [ "${#RUNNING[@]}" -gt 0 ]; then break; fi   # une suite en série tourne seule
    prochain=$((prochain + 1))
    if [ "${SU_ABSENT[$i]}" = 1 ]; then ETAT[$i]=2; continue; fi
    demarrer_suite "$i"
    ETAT[$i]=1; RUNNING+=("$i")
  done
  while [ "$affiche" -lt "$NB" ] && [ "${ETAT[$affiche]}" = 2 ]; do
    afficher_suite "$affiche"
    affiche=$((affiche + 1))
  done
  [ "$affiche" -lt "$NB" ] || break
  if [ "$TACHES" -eq 1 ] && [ "${#RUNNING[@]}" -eq 1 ]; then
    { wait "${WRAP[${RUNNING[0]}]}"; } 2>/dev/null   # une seule tâche : pas de sondage, la suite finie réveille le lanceur
  else
    sleep 0.1
  fi
done

if [ "$suites" -gt 0 ]; then
  [ -z "$DUREES_PANNE" ] || echo "run_all : durées non enregistrées ($DUREES_PANNE)"
  echo "Suites les plus lentes :"
  printf '%s' "$LENTES" | sort -t $'\t' -k1,1nr -k2,2n | head -10 | while IFS=$'\t' read -r ms_lente rang_lente etiquette_lente; do
    printf '  %s s  %s\n' "$(duree "$ms_lente")" "$etiquette_lente"
  done
  echo "Tests sautés : $((sautes_python + sautes_shell)) (suites Python $sautes_python, branches shell $sautes_shell)"
fi
echo
if [ "$suites" -eq 0 ]; then
  if [ "$CIBLE" -eq 0 ] && [ ${#NOMS[@]} -gt 0 ]; then   # des noms donnés, aucune suite : code 5 (change light-spec-finish, D11)
    echo "run_all : aucune suite ne correspond aux noms donnés (${NOMS[*]})"
    exit 5
  fi
  echo "Aucune suite trouvée (noms demandés : ${NOMS[*]:-aucun})"
  exit 2
fi
DUREE_TOTALE=$(duree $(( $(horloge) - DEBUT_TOTAL )))
if [ "$echecs" -gt 0 ]; then
  echo "TOTAL : $total tests dans $suites suites · $echecs suite(s) en échec : ${echouees[*]} · durée totale $DUREE_TOTALE s"
  exit 1
fi
echo "TOTAL : $total tests dans $suites suites · tous réussis · durée totale $DUREE_TOTALE s"
if [ "$ECRIRE_CIBLEE" -eq 1 ] && [ -n "$EMPREINTE_CIBLEE" ]; then
  arbre=$(git write-tree 2>/dev/null) && printf '%s\n' "$arbre" > "$EMPREINTE_CIBLEE" && echo "Empreinte ciblée de l'index enregistrée : le hook pre-commit l'acceptera sur une branche de travail (pas sur main)."
elif [ ${#NOMS[@]} -eq 0 ] && [ -z "$MODE" ] && [ -n "$EMPREINTE" ]; then
  arbre=$(git write-tree 2>/dev/null) && printf '%s\n' "$arbre" > "$EMPREINTE" && echo "Empreinte de l'index enregistrée : le hook pre-commit acceptera le commit de cet index."
fi
