# PMZilla Lab : signature d'environnement et horloge des scripts de fin de branche (change test-speed, design D9 et D2).
# Module SOURCÉ (bash) par tools/finish_worktree.sh et tools/finish_branch.sh ; il ne change ni les options du shell appelant
# ni son dossier courant et n'écrit aucun fichier.
#
#     . "$(dirname "$0")/finish_env.sh"
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

finish_env_ms() {
  local t
  t=$(perl -MTime::HiRes=time -e 'printf "%d\n", time() * 1000' 2>/dev/null) || t=""
  case "$t" in ''|*[!0-9]*) t=$(( $(date +%s) * 1000 )) ;; esac
  printf '%s\n' "$t"
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
