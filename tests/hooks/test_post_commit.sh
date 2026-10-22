#!/bin/sh
# Test du hook post-commit : faux HOME, dépôt temporaire à l'emplacement attendu, faux evals_auto.sh qui note ses appels.
# Aucun appel à Claude, à Ollama ni au réseau. Lancement à la main : sh tests/hooks/test_post_commit.sh
set -u
hook="$(cd "$(dirname "$0")/../../tools/hooks" && pwd)/post-commit"
tmp=$(mktemp -d) || exit 1
tmp=$(cd "$tmp" && pwd -P)       # git résout les liens (/var -> /private/var sur macOS)
trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp/home"
ws="$HOME/PMZilla-Lab/workspace"
mkdir -p "$ws/tools" "$HOME/Library/Logs"
appels="$tmp/appels"
cat > "$ws/tools/evals_auto.sh" <<SCRIPT
#!/bin/sh
echo "appel: \$*" >> "$appels"
SCRIPT
chmod +x "$ws/tools/evals_auto.sh"
cd "$ws" || exit 1
git init -q . && git config user.email t@example.org && git config user.name test
ok=0; ko=0

commit() { # fichier : un commit qui touche ce fichier
  mkdir -p "$(dirname "$1")"; echo "$RANDOM" > "$1"; git add "$1"; git commit -q -m "t" --no-verify
}
lance() { # variables d'environnement en arguments ; attend un éventuel lancement en arrière-plan
  rm -f "$appels"
  env PMZILLA_LAB_WORKSPACE="$ws" "$@" zsh "$hook" > "$tmp/sortie" 2>&1   # le dossier de contenu du module partagé est le faux dépôt
  i=0; while [ ! -f "$appels" ] && [ "$i" -lt 30 ]; do sleep 0.1; i=$((i+1)); done
  sleep 0.2
}
attend() { # description  attendu ("rien" ou le contenu exact du fichier d'appels)
  desc=$1; attendu=$2
  if [ "$attendu" = "rien" ]; then
    if [ -f "$appels" ]; then echo "ECHEC : $desc (appel inattendu : $(cat "$appels"))"; ko=$((ko+1)); else echo "ok : $desc"; ok=$((ok+1)); fi
  else
    if [ -f "$appels" ] && [ "$(cat "$appels")" = "$attendu" ]; then echo "ok : $desc"; ok=$((ok+1)); else echo "ECHEC : $desc (attendu « $attendu », reçu « $(cat "$appels" 2>/dev/null) »)"; ko=$((ko+1)); fi
  fi
}

commit docs/init.md                 # le hook ignore un premier commit (diff-tree sans --root)
commit CLAUDE.md
lance PMZILLA_X=1;                                  attend "sans variable, le hook ne fait rien" rien
lance PMZILLA_AFTER_COMMIT=;                        attend "variable vide, rien" rien
lance PMZILLA_AFTER_COMMIT=nimportequoi;            attend "valeur inconnue, rien" rien
lance PMZILLA_AFTER_COMMIT=evals;                   attend "essai : le jeu d'essai seul, sans --readme" "appel: "
lance PMZILLA_AFTER_COMMIT=all;                    attend "tout : le jeu d'essai avec --readme" "appel: --readme"
lance PMZILLA_AFTER_COMMIT=all PMZILLA_NO_EVALS=1; attend "PMZILLA_NO_EVALS l'emporte" rien
commit tests/postures/cas.yaml
lance PMZILLA_AFTER_COMMIT=evals;                   attend "cas d'essai modifiés : lancé" "appel: "
commit tests/postures/vocabulaire.yaml
lance PMZILLA_AFTER_COMMIT=evals;                   attend "vocabulaire des postures modifié : lancé" "appel: "
commit tests/postures/memoire/en/delivery/MEMORY.md
lance PMZILLA_AFTER_COMMIT=evals;                   attend "mémoire neutre anglaise modifiée : lancé" "appel: "
commit .claude/skills/pmzilla-delivery-bmad/SKILL.md
lance PMZILLA_AFTER_COMMIT=evals;                   attend "skill de posture modifié : lancé" "appel: "
commit docs/autre.md
lance PMZILLA_AFTER_COMMIT=all;                    attend "fichier non surveillé : rien, même avec all" rien
commit CLAUDE.md
mkdir -p "$tmp/autre" && cd "$tmp/autre" && git init -q . && git config user.email t@example.org && git config user.name test && echo x > CLAUDE.md && git add CLAUDE.md && git commit -q -m t --no-verify
lance PMZILLA_AFTER_COMMIT=all;                    attend "copie temporaire (autre dossier) : rien" rien

# anciens noms de variables et de valeurs : refusés (message qui nomme le nom actuel, sur stderr et dans le journal), aucun lancement
cd "$ws" || exit 1
commit CLAUDE.md
journal="$HOME/Library/Logs/pmzilla-essai.log"
refus() { # description, motif attendu dans la sortie et le journal ; variables en arguments suivants
  desc=$1; motif=$2; shift 2
  rm -f "$journal"
  lance "$@"
  if [ ! -f "$appels" ] && grep -q "$motif" "$tmp/sortie" && grep -q "$motif" "$journal"; then echo "ok : $desc"; ok=$((ok+1)); else echo "ECHEC : $desc"; ko=$((ko+1)); fi
}
refus "PMZILLA_APRES_COMMIT refusé, nomme PMZILLA_AFTER_COMMIT" "PMZILLA_AFTER_COMMIT" PMZILLA_APRES_COMMIT=evals
refus "valeur essai refusée, nomme evals" "evals" PMZILLA_AFTER_COMMIT=essai
refus "valeur tout refusée, nomme all" "all" PMZILLA_AFTER_COMMIT=tout
refus "PMZILLA_SANS_ESSAI refusé, nomme PMZILLA_NO_EVALS" "PMZILLA_NO_EVALS" PMZILLA_SANS_ESSAI=1
refus "ancien nom avec le nouveau : refusé quand même" "PMZILLA_AFTER_COMMIT" PMZILLA_AFTER_COMMIT=evals PMZILLA_APRES_COMMIT=tout
rm -f "$journal"
lance PMZILLA_AFTER_COMMIT=evals;                   attend "nouveaux noms : lancé" "appel: "
if [ ! -s "$journal" ] || ! grep -qi "refus" "$journal"; then echo "ok : nouveaux noms sans refus"; ok=$((ok+1)); else echo "ECHEC : refus inattendu"; ko=$((ko+1)); fi
if ! grep -qi "refus" "$tmp/sortie"; then echo "ok : nouveaux noms, sortie sans refus"; ok=$((ok+1)); else echo "ECHEC : refus inattendu en sortie"; ko=$((ko+1)); fi

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
