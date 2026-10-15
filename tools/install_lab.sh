#!/bin/zsh
# Amorce du script d'installation (change install-script, design D1, D2, D16, D17).
# Tourne avant que uv existe : contrôle la plateforme, trouve Homebrew, propose git et uv, clone le dépôt si besoin,
# puis passe la main à l'orchestrateur Python avec tous les arguments d'origine.
# Aucun état n'est changé sans confirmation (réponse vide = refus). Aucune option d'acceptation automatique.
#
# Exemple :
#     zsh tools/install_lab.sh
set -u

PREFIXE="install_lab: "

dire() { print -r -- "${PREFIXE}$*"; }

# Confirmation lue sur l'entrée standard : défaut non, seuls y et yes (toute casse) acceptent.
confirmer() {
  local reponse=""
  print -rn -- "${PREFIXE}$1 [y/N] "
  read -r reponse || reponse=""
  print ""
  case "${reponse:l}" in
    y|yes) return 0 ;;
    *) return 1 ;;
  esac
}

# --- arguments (lus sans rien retirer : "$@" repart intact vers l'orchestrateur) ---
depot=""
a_blanc=0
direct=0
precedent=""
for arg in "$@"; do
  if [[ "$precedent" == "--repo" ]]; then depot="$arg"; fi
  case "$arg" in
    --repo=*) depot="${arg#--repo=}" ;;
    --dry-run) a_blanc=1 ;;
    --help|-h|--list) direct=1 ;;
  esac
  precedent="$arg"
done

# --- racine : emplacement du script (dossier parent de tools/), remplaçable par la variable de test ---
if [[ -n "${INSTALL_LAB_ROOT:-}" ]]; then
  racine="$INSTALL_LAB_ROOT"
else
  racine="${0:A:h:h}"
fi
cible="$HOME/PMZilla-Lab/workspace"

# --- Homebrew : dans le PATH, sinon environnement du préfixe standard d'Apple Silicon (seule ligne avec un chemin absolu) ---
charger_brew() {
  if [[ -x "${INSTALL_LAB_BREW_PREFIX:-/opt/homebrew}/bin/brew" ]]; then eval "$("${INSTALL_LAB_BREW_PREFIX:-/opt/homebrew}/bin/brew" shellenv)"; fi
}

# --- aide et liste : remise directe si le clone est là, sans contrôle d'état ---
if (( direct )) && [[ -e "$racine/.git" ]]; then
  command -v uv >/dev/null 2>&1 || charger_brew
  if command -v uv >/dev/null 2>&1; then
    exec uv run "$racine/tools/install_lab.py" "$@"
  fi
fi

# --- plateforme ---
if [[ "$(uname -m 2>/dev/null)" != "arm64" || "$(uname -s 2>/dev/null)" != "Darwin" ]]; then
  dire "this installer needs macOS on Apple Silicon (arm64, Darwin)"
  exit 3
fi

# --- Homebrew ---
command -v brew >/dev/null 2>&1 || charger_brew
if ! command -v brew >/dev/null 2>&1; then
  dire "Homebrew not found, install it first: https://brew.sh"
  exit 3
fi

# --- emplacement du clone ---
cible_resolue="${cible:A}"
if [[ -e "$racine/.git" ]]; then
  if [[ "${racine:A}" != "$cible_resolue" ]]; then
    dire "clone must be at $cible"
    exit 3
  fi
  a_cloner=0
else
  if [[ -e "$cible" && ! -e "$cible/.git" ]]; then
    dire "target folder $cible exists and is not a clone, nothing was touched"
    exit 3
  fi
  if [[ -e "$cible/.git" ]]; then
    a_cloner=0
    racine="$cible"
  else
    if [[ -z "$depot" ]]; then
      dire "run outside a clone: give the clone URL with --repo <URL>"
      exit 2
    fi
    a_cloner=1
  fi
fi

# --- git et uv ---
for outil in git uv; do
  command -v "$outil" >/dev/null 2>&1 && continue
  if (( a_blanc )); then
    dire "dry run: would run brew install $outil"
    continue
  fi
  if ! confirmer "step bootstrap: brew install $outil?"; then
    dire "step bootstrap: declined"
    exit 4
  fi
  if ! brew install "$outil"; then
    dire "step bootstrap: failed: brew install $outil"
    exit 1
  fi
done

# --- clone ---
if (( a_cloner )); then
  if (( a_blanc )); then
    dire "dry run: would run git clone $depot $cible"
    dire "dry run: the remaining steps need the clone"
    exit 0
  fi
  if ! confirmer "step bootstrap: git clone $depot $cible?"; then
    dire "step bootstrap: declined"
    exit 4
  fi
  if ! git clone "$depot" "$cible"; then
    dire "step bootstrap: failed: git clone $depot $cible"
    exit 1
  fi
  racine="$cible"
fi

# --- remise à l'orchestrateur ---
if (( a_blanc )) && ! command -v uv >/dev/null 2>&1; then
  dire "dry run: the remaining steps need uv"
  exit 0
fi
exec uv run "$racine/tools/install_lab.py" "$@"
