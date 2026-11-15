# PMZilla Lab : signature d'environnement, horloge et retrait des variables DBTEST_ des scripts de fin de branche
# (change test-speed, design D9 et D2).
# Module SOURCÉ (bash) par tools/finish_train.sh et tools/branch_sync.sh ; il ne change ni les options du
# shell appelant ni son dossier courant et n'écrit aucun fichier, sauf record_main_validated (fin du module, pmzilla-main-validated du dossier Git commun,
# appelée par le train seul) ; seule finish_env_retire_dbtest change un attribut (l'export) de variables du shell appelant.
#
#     . "$(dirname "$0")/finish_env.sh"
#     finish_env_retire_dbtest                             une fois, au début du script, avant tout lancement d'enfant
#     signature=$(finish_env_signature) || signature=""    depuis un dossier du dépôt (espace de travail ou worktree)
#     debut=$(finish_env_ms)
#
# finish_env_signature écrit un condensé SHA-256 (64 caractères hexadécimaux) et rien d'autre : les versions de python3, uv, git et
# bash, le dossier de contenu, l'arbre d'exécution et le dossier de données donnés par tools/lab_paths.sh, le dossier des hooks
# (absolu) et la valeur de core.hooksPath. Aucun chemin n'est écrit : seul le condensé sort. Le dossier du code est exclu (il diffère
# par construction entre un worktree et l'espace de travail). Un outil absent ou en échec, le module des dossiers en échec : code 1,
# aucune sortie, donc aucune signature.
# finish_env_ms écrit l'heure en millisecondes (perl, Time::HiRes), à défaut les secondes entières multipliées par 1000.
#
# Lancé directement, il écrit la signature (ligne `signature=` suivie des 64 caractères) et le nom des composants pris en compte
# (ligne `composants=`), jamais leurs valeurs (ni chemin ni version) :
#
#     bash tools/finish_env.sh
#
# Codes de sortie : 0 signature écrite, 1 signature impossible (message court sur la sortie d'erreur, sans chemin).
# Sourcé, il n'écrit rien.
#
# Option --main-signature (change light-spec-finish, question Q9, design D3b) : écrit une seule ligne, la signature de l'environnement qui
# valide l'arbre de main pour le chemin allégé (python3, uv, git, bash et les trois dossiers du lab ; ni dossier de code ni hooks) :
#
#     bash tools/finish_env.sh --main-signature
#
# Chaque version est la première ligne de la sortie (standard et erreur) de `<outil> --version`, sans retour chariot, blancs de bord retirés,
# suites de blancs réduites à une espace. Succès : 64 caractères hexadécimaux, code 0. Échec : `absent:<composant>` (python3, uv, git, bash,
# dossiers-du-lab, ou condensé), code 1 ; jamais un chemin ni une version. N'écrit aucun fichier.

_fe_dossier=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

finish_env_signature() {
  local versions labo hooks chemin_hooks condense
  versions=$(
    for outil in python3 uv git; do
      v=$("$outil" --version 2>&1) || exit 1
      printf '%s %s\n' "$outil" "$v"
    done
    v=$(bash --version 2>&1 | head -1); [ -n "$v" ] || exit 1
    printf 'bash %s\n' "$v"
  ) || return 1
  labo=$(
    . "$_fe_dossier/lab_paths.sh" 2>/dev/null && lab_paths_init 2>/dev/null || exit 1
    printf 'contenu=%s\nexecution=%s\ndonnees=%s\n' "$LAB_CONTENT_ROOT" "$LAB_RUN_TREE" "$LAB_DATA_FOLDER"
  ) || return 1
  hooks=$(git rev-parse --path-format=absolute --git-path hooks 2>/dev/null) || return 1
  chemin_hooks=$(git config --get core.hooksPath 2>/dev/null) || chemin_hooks=""
  condense=$(printf '%s\n%s\nhooks=%s\ncore.hooksPath=%s\n' "$versions" "$labo" "$hooks" "$chemin_hooks" \
    | { shasum -a 256 2>/dev/null || sha256sum 2>/dev/null; } | cut -d' ' -f1)
  case "$condense" in
    ????????????????????????????????????????????????????????????????) ;;
    *) return 1 ;;
  esac
  case "$condense" in *[!0-9a-f]*) return 1 ;; esac
  printf '%s\n' "$condense"
}

_fe_version() { # outil : première ligne normalisée de `outil --version`, code 1 si l'outil manque, échoue ou ne dit rien
  local v
  command -v "$1" >/dev/null 2>&1 || return 1
  v=$("$1" --version 2>&1) || return 1
  v=$(printf '%s\n' "$v" | head -1 | tr -d '\r' | tr -s ' \t' '  ' | sed 's/^ //; s/ $//')
  [ -n "$v" ] || return 1
  printf '%s\n' "$v"
}

finish_env_main_signature() { # écrit la signature (code 0) ou absent:<composant> (code 1)
  local entree outil v labo condense
  entree=""
  for outil in python3 uv git bash; do
    v=$(_fe_version "$outil") || { printf 'absent:%s\n' "$outil"; return 1; }
    entree="${entree}${outil}=${v}"$'\n'
  done
  labo=$(
    . "$_fe_dossier/lab_paths.sh" 2>/dev/null && lab_paths_init >/dev/null 2>&1 || exit 1
    printf 'contenu=%s\nexecution=%s\ndonnees=%s\n' "${LAB_CONTENT_ROOT%/}" "${LAB_RUN_TREE%/}" "${LAB_DATA_FOLDER%/}"
  ) || { printf 'absent:dossiers-du-lab\n'; return 1; }
  entree="${entree}${labo}"$'\n'
  condense=$(printf '%s' "$entree" | { shasum -a 256 2>/dev/null || sha256sum 2>/dev/null; } | cut -d' ' -f1)
  case "$condense" in
    ????????????????????????????????????????????????????????????????) ;;
    *) printf 'absent:condensé\n'; return 1 ;;
  esac
  case "$condense" in *[!0123456789abcdef]*) printf 'absent:condensé\n'; return 1 ;; esac
  printf '%s\n' "$condense"
}

# finish_env_retire_dbtest (fix/finish-worktree-env-dbtest, décisions de l'auteur du 2026-10-28)
# Ce qu'elle fait : retire l'attribut d'export de chaque variable DBTEST_ du shell appelant ; aucun enfant lancé ensuite (dbtest, passe de
# bout en bout, validation, runners, script de fin, envoi vers le dépôt distant et hook git qui le précède) ne les reçoit. Les valeurs
# restent lisibles dans le shell. Aucun argument ; rend toujours 0 ; ne contient ni sortie de script ni refus.
# Appelant : tools/finish_train.sh (première ligne de main), une seule fois, avant tout lancement d'enfant (les fins unitaires, retirées par B9, l'appelaient aussi).
# Ce qu'elle remplace : le retrait en ligne de fix/train-dbtest-arbre dans tools/finish_train.sh (le tableau dbunsets du dbtest et les
# -u DBTEST_PORT puis compgen -e DBTEST_ ajoutés au tableau unsets du runner).
# Condition de retrait : permanente tant que tools/dbtest.sh lit des variables DBTEST_ de substitution (DBTEST_SONDE, DBTEST_RECORD,
# DBTEST_RUN_ALL, DBTEST_ATTENTE, DBTEST_E2E_*) et que tests/run_all.sh change de comportement avec DBTEST_PORT hors session (passage en
# série, variables de base de l'appelant transmises). Elle ne pourrait être retirée que si ces deux outils ignoraient toute DBTEST_
# venue de l'appelant, hors de leurs propres tests.
# Règle doublée : non, elle est la source unique du retrait des DBTEST_ dans les scripts de fin. Règles voisines, qui ne la doublent pas :
# le refus de DBTEST_PORT par tests/run_all.sh (en session seulement) et le retrait de DBTEST_PORT par tools/dbtest.sh (tableau RETRAIT,
# pour ses propres enfants). Détection d'un écart : dynamique, les tests du train qui posent `dbvars=[]` (tests/finish_train/test_passe_e2e.py,
# tests/finish_train_base/test_dbtest_runner.py) échouent si une variable DBTEST_ de l'appelant atteint un enfant du train.
finish_env_retire_dbtest() {
  local _fe_v
  for _fe_v in $(compgen -e DBTEST_); do export -n "$_fe_v"; done
  return 0
}

finish_env_ms() {
  local t
  t=$(perl -MTime::HiRes=time -e 'printf "%d\n", time() * 1000' 2>/dev/null) || t=""
  case "$t" in ''|*[!0-9]*) t=$(( $(date +%s) * 1000 )) ;; esac
  printf '%s\n' "$t"
}

# --- Fonctions de tools/light_finish.sh encore utilisées après son retrait (change finish-single-b7-b9, B9, design D8) : déplacées telles quelles, jamais copiées.
# Elles servent à l'enregistrement de l'arbre de main validé par le train (tools/finish_train.sh, record_main_validated) et au radar tools/branch_sync.sh
# (light_main_ref). Remplace : tools/light_finish.sh (retiré). Condition de retrait : record_main_validated, light_record_file et env_signature tombent
# avec l'écriture de pmzilla-main-validated par le train, que B9 garde parce que l'inventaire de la tâche 2.1 y a trouvé des lecteurs autres que la décision
# allégée (aides des tests du train, guide) (décision de l'auteur R-20261105-32 Q1 : le marqueur reste écrit par le train) ; light_main_ref tombe quand branch_sync.sh calcule main autrement.
# L'appelant pose LIGHT_FINISH_DIR (le dossier tools/ de ce module) avant d'appeler env_signature ; l'enregistrement est décrit dans installation.md.
light_record_file() {
  lf_commun=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || return 1
  [ -n "$lf_commun" ] || return 1
  printf '%s/pmzilla-main-validated\n' "$lf_commun"
}

env_signature() { # signature d'environnement (question Q9, design D3b) : écrit les 64 caractères (code 0), ou « absent:<composant> » (code 1)
  lf_env=$(bash "${LIGHT_FINISH_DIR:?}/finish_env.sh" --main-signature 2>/dev/null) && lf_env_code=0 || lf_env_code=1
  if [ "$lf_env_code" -eq 0 ] && [ "${#lf_env}" -eq 64 ]; then
    case "$lf_env" in *[!0123456789abcdef]*) ;; *) printf '%s\n' "$lf_env"; return 0 ;; esac
  fi
  case "$lf_env" in absent:?*) printf '%s\n' "$lf_env" ;; *) printf 'absent:bash\n' ;; esac
  return 1
}

light_main_ref() { # <dossier du dépôt> : le plus avancé de main local et de origin/main (après un fetch), vide s'ils ont divergé (design D2)
  lf_local=$(git -C "$1" rev-parse -q --verify "refs/heads/main^{commit}" 2>/dev/null) || return 0
  lf_distant=$(git -C "$1" rev-parse -q --verify "refs/remotes/origin/main^{commit}" 2>/dev/null) || lf_distant=""
  if [ -z "$lf_distant" ] || git -C "$1" merge-base --is-ancestor "$lf_distant" "$lf_local" 2>/dev/null; then
    printf '%s\n' "$lf_local"
  elif git -C "$1" merge-base --is-ancestor "$lf_local" "$lf_distant" 2>/dev/null; then
    printf '%s\n' "$lf_distant"
  fi
}

record_main_validated() { # arbre genre
  lf_fichier=$(light_record_file) || return 1
  [ ! -d "$lf_fichier" ] || return 1
  lf_nouvelle="$lf_fichier.tmp.$$"
  lf_signature=$(env_signature) || lf_signature=inconnue
  (
    umask 077
    {
      if [ -f "$lf_fichier" ]; then tail -n 49 "$lf_fichier"; fi
      printf '%s\t%s\t%s\t%s\n' "$1" "$2" "$(date -u +%Y-%m-%d)" "$lf_signature"
    } > "$lf_nouvelle"
  ) 2>/dev/null && mv -f "$lf_nouvelle" "$lf_fichier" 2>/dev/null || { rm -f "$lf_nouvelle" 2>/dev/null; return 1; }
}

# Lancé directement (et non sourcé) : écrit la signature et le nom des composants pris en compte, jamais leurs valeurs.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  if [ "${1:-}" = "--main-signature" ]; then
    finish_env_main_signature
    exit $?
  fi
  _fe_signature=$(finish_env_signature) || {
    echo "signature d'environnement : calcul impossible (outil, dossiers du lab ou dépôt Git indisponibles)" >&2
    exit 1
  }
  printf 'signature=%s\ncomposants=python3 uv git bash dossier-de-contenu arbre-d-execution dossier-de-donnees dossier-des-hooks core.hooksPath\n' "$_fe_signature"
  exit 0
fi
