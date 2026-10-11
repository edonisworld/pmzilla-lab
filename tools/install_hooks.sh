#!/bin/sh
# PMZilla Lab : installe les hooks Git du dépôt (pre-commit, post-commit, commit-msg, pre-push) en liens symboliques RELATIFS
# .git/hooks/<hook> -> ../../tools/hooks/<hook> : tools/hooks/ (suivi par Git) fait foi.
#
#   bash tools/install_hooks.sh              crée les liens, rend les hooks exécutables, puis vérifie
#   bash tools/install_hooks.sh --verify     dit l'état de chaque lien, sans rien changer
#
# Relançable sans risque : un lien déjà correct n'est pas touché. Un hook existant qui n'est pas ce lien est déplacé en
# <hook>.avant-install (jamais supprimé). Sort avec le code 1 si un hook n'est pas en place à la fin.
set -u
HOOKS="pre-commit post-commit commit-msg pre-push"
RACINE=$(cd "$(dirname "$0")/.." && pwd -P) || exit 1
VERIFIER=0
[ "${1:-}" = "--verify" ] && VERIFIER=1
cd "$RACINE" || exit 1
git rev-parse --git-dir >/dev/null 2>&1 || { echo "Pas un dépôt Git : $RACINE" >&2; exit 1; }
DOSSIER=$(git rev-parse --git-path hooks)
[ "$DOSSIER" = ".git/hooks" ] || { echo "Dossier des hooks inattendu ($DOSSIER) : les liens relatifs ../../tools/hooks supposent .git/hooks." >&2; exit 1; }

en_place() {   # le lien .git/hooks/$1 pointe vers ../../tools/hooks/$1, qui existe et est exécutable
  [ -L ".git/hooks/$1" ] && [ "$(readlink ".git/hooks/$1")" = "../../tools/hooks/$1" ] && [ -x ".git/hooks/$1" ]
}

echec=0
for h in $HOOKS; do
  [ -f "tools/hooks/$h" ] || { echo "ABSENT : tools/hooks/$h" >&2; echec=1; continue; }
  if [ "$VERIFIER" -eq 0 ]; then
    chmod +x "tools/hooks/$h"
    if [ -L ".git/hooks/$h" ] && [ "$(readlink ".git/hooks/$h")" = "../../tools/hooks/$h" ]; then
      :
    else
      mkdir -p .git/hooks
      if [ -e ".git/hooks/$h" ] || [ -L ".git/hooks/$h" ]; then
        mv ".git/hooks/$h" ".git/hooks/$h.avant-install" && echo "$h : ancien hook rangé dans $h.avant-install"
      fi
      ln -s "../../tools/hooks/$h" ".git/hooks/$h"
    fi
  fi
  if en_place "$h"; then echo "en place : $h -> ../../tools/hooks/$h"; else echo "Hook manquant ou mal lié : $h" >&2; echec=1; fi
done

if [ "$echec" -eq 0 ]; then echo "Tous les hooks sont en place."; else echo "Des hooks ne sont pas en place." >&2; fi
exit "$echec"
