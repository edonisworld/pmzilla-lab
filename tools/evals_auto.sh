#!/bin/zsh
# PMZilla Lab : jeu d'essai des postures, puis, sur demande, mise à jour du README et de l'installation.
# À la demande :
#     tools/evals_auto.sh             rejoue les dix cas sur l'état commité, puis régénère le tableau de bord
#     tools/evals_auto.sh --readme    en plus, lance /update-readme en mode non interactif et pousse
# Le hook post-commit ne le lance plus de lui-même : il faut le demander au commit
# (PMZILLA_AFTER_COMMIT=evals ou =all, voir tools/hooks/post-commit). Journal du hook :
# ~/Library/Logs/pmzilla-essai.log
#   1. rejoue les dix cas sur l'état commité (posture_evals.py --committed-state) ;
#   2. garde le rapport d'essai en local (hors Git) ;
#   3. avec --readme : lance /update-readme en mode non interactif (il ne commite que README.md et
#      docs/pmzilla/installation.md), puis pousse. Refusé si l'un de ces deux fichiers a des modifications non
#      commitées : la session les commiterait avec le reste, au risque de prendre le travail d'une autre session ;
#   4. affiche une notification macOS avec le bilan.
# Un seul passage à la fois : un second lancement pendant un passage en demande un autre à la fin.
set -u
AVEC_README=0
for argument in "$@"; do
  case "$argument" in
    --readme) AVEC_README=1 ;;
    -h|--help) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Option inconnue : $argument (evals_auto.sh [--readme])" >&2; exit 2 ;;
  esac
done
# Lancé depuis un hook Git, le script hérite des variables GIT_* du commit (index, dossier .git) :
# elles casseraient les copies temporaires du jeu d'essai
unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE GIT_PREFIX GIT_OBJECT_DIRECTORY GIT_COMMON_DIR
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
WORKSPACE="$HOME/PMZilla-Lab/workspace"
STATE="$HOME/.pmzilla-lab/essais"
LOCK="$STATE/en-cours.lock"
AGAIN="$STATE/a-relancer"
mkdir -p "$STATE"
cd "$WORKSPACE" || exit 1

notify() { osascript -e "display notification \"$1\" with title \"PMZilla Lab\"" >/dev/null 2>&1 }

# Un passage est déjà en cours : il relancera à la fin
if ! mkdir "$LOCK" 2>/dev/null; then
  touch "$AGAIN"
  echo "$(date '+%Y-%m-%d %H:%M') passage déjà en cours, relance demandée"
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

while true; do
  rm -f "$AGAIN"
  echo "=== $(date '+%Y-%m-%d %H:%M') · commit $(git rev-parse --short HEAD) ==="

  if ! curl -s --max-time 5 http://localhost:11434/api/tags >/dev/null; then
    echo "Ollama ne répond pas : essai reporté"
    notify "Jeu d'essai reporté : Ollama ne répond pas. Relancer : tools/evals_auto.sh"
    exit 1
  fi

  OUTPUT=$(uv run "$HOME/PMZilla-Lab/posture_evals.py" --committed-state 2>&1)
  echo "$OUTPUT"
  BILAN=$(print -r -- "$OUTPUT" | grep '^BILAN ' | tail -1)
  REPORT=${BILAN##* · }
  SUMMARY=${${BILAN#BILAN }% · *}

  if [[ -n "$BILAN" && -f "$REPORT" && $AVEC_README -eq 0 ]]; then
    notify "Jeu d'essai : $SUMMARY."
  elif [[ -n "$BILAN" && -f "$REPORT" ]] && [[ -n "$(git status --porcelain -- README.md docs/pmzilla/installation.md)" ]]; then
    # une autre session a peut-être des modifications en cours sur ces fichiers : /update-readme les commiterait
    echo "README non mis à jour : README.md ou docs/pmzilla/installation.md a des modifications non commitées. Les commiter ou les écarter, puis relancer avec --readme."
    notify "Jeu d'essai : $SUMMARY. README non mis à jour : modifications non commitées."
  elif [[ -n "$BILAN" && -f "$REPORT" ]]; then
    # le rapport reste local : _bmad-output/essais/ est ignoré par Git (extraits de livres possibles)
    # /update-readme ne commite que README.md et docs/pmzilla/installation.md ; le hook ne réagit pas à ce commit
    # consigne de la commande /update-readme, sans son en-tête, avec la précision à la place de $ARGUMENTS
    PROMPT=$(awk 'n >= 2 { print; next } /^---$/ { n++ }' .claude/commands/update-readme.md \
      | sed "s|\$ARGUMENTS|mode automatique après le jeu d'essai ($SUMMARY)|")
    claude -p "$PROMPT" \
      --permission-mode acceptEdits \
      --allowedTools Read Glob Grep Edit Write "Bash(git *)" "Bash(uv run tools/*)" "Bash(ls *)" \
      --append-system-prompt "Mode automatique, sans personne pour répondre : ne pose aucune question et n'attends aucune confirmation. N'utilise jamais \$(...), \$PWD ni de variable dans une commande Bash : écris les valeurs en clair. Si le README n'a aucun écart, ne commite rien." \
      | tail -20
    git push -q 2>&1 || echo "Push impossible : à refaire à la main"
    notify "Jeu d'essai : $SUMMARY. README vérifié."
  else
    echo "Essai sans bilan : voir le journal"
    notify "Jeu d'essai en erreur : voir ~/Library/Logs/pmzilla-essai.log"
  fi

  # Tableau de bord (page HTML locale) : son échec ne fait jamais échouer l'essai
  uv run "$WORKSPACE/tools/dashboard.py" >/dev/null 2>&1 || true

  [[ -f "$AGAIN" ]] || break
  echo "Nouveau commit concerné pendant le passage : relance"
done
