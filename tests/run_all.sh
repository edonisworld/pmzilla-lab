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
#
# Un test shell listé mais absent du disque est un ÉCHEC nommé (jamais un saut silencieux) ; un filtre ne concerne que ses suites.
# Un script de test shell sous tests/ qui n'est pas listé ci-dessous doit être déclaré auxiliaire (lignes « AUXILIAIRE »), sinon
# tests/run_all/test_run_all.py échoue en le nommant.
# AUXILIAIRE tests/db_scripts/test_db_restore_test.sh : lancé par tests/db_scripts/test_db_scripts.sh (suite voisine) ; le lister le ferait tourner deux fois.
#
# Garde-fou de commit : PMZILLA_NO_EVALS (réservée à git commit) fait refuser le lancement (code 2). Un lancement COMPLET (sans nom
# de suite) qui se termine sans échec écrit l'empreinte de l'index (git write-tree) dans .git/pmzilla-run-all-ok ; le hook pre-commit
# refuse le commit si elle ne correspond pas à l'index. Donc : git add, puis run_all.sh && git commit. Un lancement filtré n'écrit rien.
# Un lancement ciblé (--staged) efface d'abord l'empreinte ciblée précédente (.git/pmzilla-run-targeted-ok), puis, s'il se termine sans
# échec, y écrit l'empreinte de l'index : sur une branche de travail, le hook pre-commit accepte l'une ou l'autre ; sur main, jamais la ciblée.
# Un lancement ciblé n'écrit ni n'efface l'empreinte complète (sauf s'il a dû passer en exécution complète).
#
# Aucun appel réseau ni payant ; chaque suite travaille dans un dossier temporaire (voir son en-tête).
# Variables (pour les tests de ce script) : RUN_ALL_ROOT (racine du dépôt), RUN_ALL_DEPS (options `uv run --with …`).
set -u
RACINE="${RUN_ALL_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DEPS="${RUN_ALL_DEPS---with numpy --with httpx --with pyyaml --with requests --with feedparser --with trafilatura --with beautifulsoup4 --with markdownify --with pymupdf4llm --with ebooklib --with "psycopg[binary]"}"
BAVARD=0
CIBLE=0
NOMS=()
for argument in "$@"; do
  if [ "$argument" = "-v" ]; then BAVARD=1; elif [ "$argument" = "--staged" ]; then CIBLE=1; else NOMS+=("$argument"); fi
done
if [ "$CIBLE" -eq 1 ] && [ ${#NOMS[@]} -gt 0 ]; then
  echo "run_all : --staged ne se combine pas avec des noms de suites (${NOMS[*]})"
  exit 2
fi
cd "$RACINE" || { echo "Racine introuvable : $RACINE"; exit 2; }

if [ -n "${PMZILLA_NO_EVALS+x}" ]; then
  echo "PMZILLA_NO_EVALS est définie : variable réservée à git commit (elle coupe le jeu d'essai du hook post-commit)."
  echo "Elle fausse les tests du hook : relance sans elle (env -u PMZILLA_NO_EVALS bash tests/run_all.sh)."
  exit 2
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
[ ${#NOMS[@]} -eq 0 ] && [ -n "$EMPREINTE" ] && rm -f "$EMPREINTE"      # un lancement complet invalide l'empreinte précédente

if [ "${PMZILLA_ENTREES_JUGE_CHANGEES:-}" = "1" ]; then
  echo "ATTENTION : PMZILLA_ENTREES_JUGE_CHANGEES=1 : le test des entrées du juge (tests/posture_evals/test_entrees_juge.py) est IGNORÉ."
  echo "            Le commit qui change ces entrées doit le dire dans son message (« Entrées du juge modifiées : … ») ; plan 6.2."
  echo
fi

voulue() {   # sans nom donné, tout est voulu
  [ ${#NOMS[@]} -eq 0 ] && return 0
  for nom in "${NOMS[@]}"; do [ "$nom" = "$1" ] && return 0; done
  return 1
}

total=0; ignores=0; suites=0; echecs=0; echouees=()
ligne() { printf "%-22s %5s tests · %s\n" "$1" "$2" "$3"; }

for dossier in tests/*/; do
  nom=$(basename "$dossier")
  ls "$dossier"test_*.py >/dev/null 2>&1 || continue
  voulue "$nom" || continue
  # shellcheck disable=SC2086
  sortie=$(uv run $DEPS python -W ignore -m unittest discover -s "$dossier" 2>&1); code=$?
  n=$(printf '%s\n' "$sortie" | sed -n 's/^Ran \([0-9][0-9]*\) test.*/\1/p' | tail -1)
  bilan=$(printf '%s\n' "$sortie" | tail -1)
  suites=$((suites + 1)); total=$((total + ${n:-0}))
  if [ "$code" -eq 0 ] && [ -n "$n" ]; then
    ligne "$nom" "$n" "$bilan"
    [ "$BAVARD" -eq 1 ] && printf '%s\n' "$sortie"
  else
    ligne "$nom" "${n:-?}" "ÉCHEC (code $code) : $bilan"
    printf '%s\n' "$sortie" | tail -30 | sed 's/^/    /'
    echecs=$((echecs + 1)); echouees+=("$nom")
  fi
done

for test in tests/hooks/test_pre_commit.sh:hooks:sh tests/hooks/test_post_commit.sh:post-commit:sh tests/hooks/test_commit_msg.sh:commit-msg:sh tests/hooks/test_pre_commit_green.sh:pre-commit-green:sh tests/hooks/test_pre_push.sh:pre-push:sh tests/evals_auto/test_evals_auto.sh:evals_auto:sh tests/installation/test_install_links.sh:installation:zsh tests/installation/test_install_hooks.sh:install_hooks:sh tests/db_scripts/test_db_scripts.sh:db_scripts:bash tests/db_scripts/test_dbtest.sh:dbtest:bash tests/finish_branch/test_finish_branch.sh:finish_branch:bash; do
  chemin=${test%%:*}; reste=${test#*:}; nom=${reste%%:*}; interprete=${reste#*:}
  voulue "$nom" || continue
  if [ ! -f "$chemin" ]; then
    ligne "$nom (shell)" "?" "ÉCHEC : script listé mais absent : $chemin"
    suites=$((suites + 1)); echecs=$((echecs + 1)); echouees+=("$nom ($chemin absent)")
    continue
  fi
  sortie=$("$interprete" "$chemin" 2>&1); code=$?
  reussis=$(printf '%s\n' "$sortie" | sed -n 's/^\([0-9][0-9]*\) réussis, [0-9][0-9]* échec.*/\1/p' | tail -1)
  rates=$(printf '%s\n' "$sortie" | sed -n 's/^[0-9][0-9]* réussis, \([0-9][0-9]*\) échec.*/\1/p' | tail -1)
  n=$(( ${reussis:-0} + ${rates:-0} ))
  suites=$((suites + 1)); total=$((total + n))
  if [ "$code" -eq 0 ] && [ -n "$reussis" ] && [ "${rates:-1}" -eq 0 ]; then
    ligne "$nom (shell)" "$n" "OK"
    [ "$BAVARD" -eq 1 ] && printf '%s\n' "$sortie"
  else
    ligne "$nom (shell)" "$n" "ÉCHEC (code $code, ${rates:-?} échec(s))"
    printf '%s\n' "$sortie" | tail -30 | sed 's/^/    /'
    echecs=$((echecs + 1)); echouees+=("$nom")
  fi
done

echo
if [ "$suites" -eq 0 ]; then
  echo "Aucune suite trouvée (noms demandés : ${NOMS[*]:-aucun})"
  exit 2
fi
if [ "$echecs" -gt 0 ]; then
  echo "TOTAL : $total tests dans $suites suites · $echecs suite(s) en échec : ${echouees[*]}"
  exit 1
fi
echo "TOTAL : $total tests dans $suites suites · tous réussis"
if [ "$ECRIRE_CIBLEE" -eq 1 ] && [ -n "$EMPREINTE_CIBLEE" ]; then
  arbre=$(git write-tree 2>/dev/null) && printf '%s\n' "$arbre" > "$EMPREINTE_CIBLEE" && echo "Empreinte ciblée de l'index enregistrée : le hook pre-commit l'acceptera sur une branche de travail (pas sur main)."
elif [ ${#NOMS[@]} -eq 0 ] && [ -n "$EMPREINTE" ]; then
  arbre=$(git write-tree 2>/dev/null) && printf '%s\n' "$arbre" > "$EMPREINTE" && echo "Empreinte de l'index enregistrée : le hook pre-commit acceptera le commit de cet index."
fi
