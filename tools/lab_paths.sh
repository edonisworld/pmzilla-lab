# PMZilla Lab : résolution partagée des dossiers du lab pour les scripts shell (R-77, design D1, D2, D5).
# Jumeau de tools/lab_paths.py : mêmes noms, même ordre, même échec. Se SOURCE, sous bash comme sous zsh :
#
#     . "$(dirname "$0")/lab_paths.sh"      (ou le chemin du fichier)
#     lab_paths_init || exit $?             pose LAB_CODE_ROOT, LAB_CONTENT_ROOT, LAB_FOLDER, LAB_RUN_TREE, LAB_DATA_FOLDER, LAB_BACKUPS_FOLDER, LAB_CONTEXT_FOLDER, LAB_WORKTREES_FOLDER
#     lab_paths_worktrees_folder <racine de contenu>   dossier des worktrees d'une racine donnée, sans Git (lab-folder-layout, D1)
#     liste=$(lab_paths_local_file sensitive_names)    chemin d'un fichier local du registre (jamais ouvert ici)
#
# Lancé directement, il écrit les huit dossiers, une ligne `nom=chemin` chacun :
#
#     bash tools/lab_paths.sh
#
# Règle : voir tools/lab_paths.py. Échec : message en français sur la sortie d'erreur (jamais un chemin), retour 78.
# Codes de sortie : 0 dossiers posés, 78 dossier de contenu introuvable ou PMZILLA_LAB_WORKSPACE sur un dossier absent.
# Ce fichier ne change ni les options du shell appelant ni son dossier courant.

# Chemin de ce fichier, lien suivi (bash : BASH_SOURCE ; zsh : %x).
if [ -n "${ZSH_VERSION:-}" ]; then
  _lp_fichier=$(eval 'printf %s "${(%):-%x}"')
else
  _lp_fichier=${BASH_SOURCE[0]}
fi
while [ -L "$_lp_fichier" ]; do
  _lp_cible=$(readlink "$_lp_fichier")
  case "$_lp_cible" in /*) _lp_fichier=$_lp_cible ;; *) _lp_fichier="$(dirname "$_lp_fichier")/$_lp_cible" ;; esac
done
LAB_CODE_ROOT=$(cd -P "$(dirname "$_lp_fichier")/.." && pwd -P)
unset _lp_fichier _lp_cible

_lp_tilde() { case "$1" in "~") printf %s "$HOME" ;; "~/"*) printf %s "$HOME/${1#\~/}" ;; *) printf %s "$1" ;; esac; }

# Dossier Git commun du dossier donné, avec un délai de 5 secondes ; n'écrit que si la sortie est une seule ligne absolue.
_lp_git_commun() {
  local _lp_tmp _lp_pid _lp_garde _lp_ligne _lp_rc
  _lp_tmp=$(mktemp "${TMPDIR:-/tmp}/lab_paths.XXXXXX") || return 1
  { git -C "$1" rev-parse --path-format=absolute --git-common-dir >"$_lp_tmp" 2>/dev/null </dev/null & } 2>/dev/null
  _lp_pid=$!
  { ( sleep 5; kill "$_lp_pid" ) >/dev/null 2>&1 & } 2>/dev/null
  _lp_garde=$!
  { wait "$_lp_pid"; } 2>/dev/null
  _lp_rc=$?
  { kill "$_lp_garde"; } >/dev/null 2>&1
  _lp_ligne=$(cat "$_lp_tmp"); rm -f "$_lp_tmp"
  [ "$_lp_rc" -eq 0 ] || return 1
  case "$_lp_ligne" in
    *$'\n'*|"") return 1 ;;
    /*) printf %s "$_lp_ligne" ;;
    *) return 1 ;;
  esac
}

# Dossier des worktrees d'une racine de contenu donnée (lab-folder-layout, D1) : PMZILLA_LAB_WORKTREES quand elle est non vide, sinon
# « worktrees » sous le dossier du lab (parent de la racine). Ne lance pas Git, ne crée ni n'ouvre rien.
lab_paths_worktrees_folder() {
  if [ -n "${PMZILLA_LAB_WORKTREES:-}" ]; then _lp_tilde "$PMZILLA_LAB_WORKTREES"; else printf %s "$(dirname "$1")/worktrees"; fi
}

lab_paths_init() {
  local _lp_voulu _lp_commun _lp_parent
  _lp_voulu=${PMZILLA_LAB_WORKSPACE:-}
  if [ -n "$_lp_voulu" ]; then
    _lp_voulu=$(_lp_tilde "$_lp_voulu")
    if [ ! -d "$_lp_voulu" ]; then
      echo "chemins du lab : PMZILLA_LAB_WORKSPACE désigne un dossier absent" >&2
      return 78
    fi
    LAB_CONTENT_ROOT=$(cd "$_lp_voulu" && pwd -P)
  else
    _lp_commun=$(_lp_git_commun "$LAB_CODE_ROOT") && _lp_parent=$(dirname "$_lp_commun") && [ -d "$_lp_parent" ] || {
      echo "chemins du lab : dossier de contenu introuvable ; poser PMZILLA_LAB_WORKSPACE ou lancer depuis un clone Git du dépôt" >&2
      return 78
    }
    LAB_CONTENT_ROOT=$_lp_parent
  fi
  LAB_FOLDER=$(dirname "$LAB_CONTENT_ROOT")
  if [ -n "${PMZILLA_LAB_RUN:-}" ]; then LAB_RUN_TREE=$(_lp_tilde "$PMZILLA_LAB_RUN"); else LAB_RUN_TREE="$LAB_FOLDER/run"; fi
  if [ -n "${PMZILLA_LAB_DATA:-}" ]; then LAB_DATA_FOLDER=$(_lp_tilde "$PMZILLA_LAB_DATA"); else LAB_DATA_FOLDER="$HOME/.pmzilla-lab"; fi
  # Dossier des sauvegardes : la variable du script de sauvegarde quand elle est non vide, sinon « sauvegardes » sous le dossier de données.
  if [ -n "${DB_BACKUP_SAUVEGARDES:-}" ]; then LAB_BACKUPS_FOLDER=$(_lp_tilde "$DB_BACKUP_SAUVEGARDES"); else LAB_BACKUPS_FOLDER="$LAB_DATA_FOLDER/sauvegardes"; fi
  # Dossier de contexte (organisation-context, D16) : PMZILLA_LAB_CONTEXT quand elle est non vide, sinon « contexte » sous le dossier du lab.
  if [ -n "${PMZILLA_LAB_CONTEXT:-}" ]; then LAB_CONTEXT_FOLDER=$(_lp_tilde "$PMZILLA_LAB_CONTEXT"); else LAB_CONTEXT_FOLDER="$LAB_FOLDER/contexte"; fi
  LAB_WORKTREES_FOLDER=$(lab_paths_worktrees_folder "$LAB_CONTENT_ROOT")
  export LAB_CODE_ROOT LAB_CONTENT_ROOT LAB_FOLDER LAB_RUN_TREE LAB_DATA_FOLDER LAB_BACKUPS_FOLDER LAB_CONTEXT_FOLDER LAB_WORKTREES_FOLDER
}

# Chemin absolu d'un fichier local du registre (mêmes noms que LOCAL_FILES du module Python) ; code 2 pour un nom inconnu.
# Suppose lab_paths_init déjà appelé. Le fichier n'est jamais ouvert.
lab_paths_local_file() {
  case "$1" in
    sensitive_names) _lp_resultat "Flux-Lab/noms-sensibles.txt" PMZILLA_LAB_SENSITIVE_NAMES PMZILLA_NOMS ;;
    bmad_replacements) _lp_resultat ".pmzilla/remplacements-bmad.tsv" ;;
    personal_identifiers) _lp_resultat ".pmzilla/identifiants.txt" ;;
    product_versions) _lp_resultat "Flux-Lab/versions-produit.txt" PMZILLA_LAB_PRODUCT_VERSIONS ;;
    local_context) _lp_resultat ".pmzilla/contexte.md" ;;
    cases_author) _lp_resultat ".pmzilla/cases.yaml" ;;
    *) return 2 ;;
  esac
}

# $1 = place sous la racine de contenu, puis les variables par ordre de priorité (sans découpage de mots : bash et zsh).
_lp_resultat() {
  local _lp_place _lp_v
  _lp_place=$1; shift
  for _lp_v in "$@"; do
    if [ -n "$(printenv "$_lp_v")" ]; then _lp_tilde "$(printenv "$_lp_v")"; echo; return 0; fi
  done
  echo "$LAB_CONTENT_ROOT/$_lp_place"
}

# Écrit les huit dossiers, une ligne `nom=chemin` chacun (même sortie que `python3 tools/lab_paths.py`).
lab_paths_print() {
  lab_paths_init || return $?
  printf 'code_root=%s\ncontent_root=%s\nlab_folder=%s\nrun_tree=%s\ndata_folder=%s\nbackups_folder=%s\ncontext_folder=%s\nworktrees_folder=%s\n' \
    "$LAB_CODE_ROOT" "$LAB_CONTENT_ROOT" "$LAB_FOLDER" "$LAB_RUN_TREE" "$LAB_DATA_FOLDER" "$LAB_BACKUPS_FOLDER" "$LAB_CONTEXT_FOLDER" "$LAB_WORKTREES_FOLDER"
}

# Lancé directement (et non sourcé) : écrit les huit dossiers.
_lp_execute=0
if [ -n "${ZSH_VERSION:-}" ]; then
  case "${ZSH_EVAL_CONTEXT:-}" in *:file*|file*) ;; *) _lp_execute=1 ;; esac
elif [ "${BASH_SOURCE[0]}" = "$0" ]; then
  _lp_execute=1
fi
if [ "$_lp_execute" = 1 ]; then lab_paths_print; exit $?; fi
unset _lp_execute
