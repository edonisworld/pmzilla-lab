#!/bin/sh
# Test du hook commit-msg : dépôt temporaire, identifiant fictif dans .pmzilla/identifiants.txt, copie du vrai scanner.
# Aucune donnée réelle, aucun appel réseau. Lancement à la main : sh tests/hooks/test_commit_msg.sh
set -u
tools="$(cd "$(dirname "$0")/../../tools" && pwd)"
tmp=$(mktemp -d) || exit 1
tmp=$(cd "$tmp" && pwd -P)
trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp/home"; mkdir -p "$HOME"
ID="zorglub-test"
depot="$tmp/depot"; mkdir -p "$depot/tools/hooks" "$depot/.pmzilla"
cp "$tools/identifiants_personnels.py" "$depot/tools/"
cp "$tools/hooks/commit-msg" "$depot/tools/hooks/" || exit 1
echo "$ID" > "$depot/.pmzilla/identifiants.txt"
cd "$depot" || exit 1
git init -q . && git config user.email t@example.org && git config user.name test
mkdir -p .git/hooks && ln -sf ../../tools/hooks/commit-msg .git/hooks/commit-msg
ok=0; ko=0
verifie() { # description  condition(0=vrai)
  if [ "$2" -eq 0 ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1"; ko=$((ko+1)); fi
}
echo a > f; git add f

git commit -q -m "ajoute f, chemin /Users/$ID/travail" > "$tmp/sortie" 2>&1; code=$?
verifie "message avec identifiant : commit refusé" "$([ $code -ne 0 ] && echo 0 || echo 1)"
verifie "message avec identifiant : ni l'identifiant ni le texte dans la sortie" "$(grep -qi -e "$ID" -e "ajoute f" "$tmp/sortie" && echo 1 || echo 0)"
verifie "message avec identifiant : le refus est dit" "$(grep -qi 'identifiant' "$tmp/sortie" && echo 0 || echo 1)"
verifie "aucun commit créé" "$(git rev-parse -q --verify HEAD >/dev/null 2>&1 && echo 1 || echo 0)"

git commit -q -m "ajoute f" > "$tmp/sortie" 2>&1; code=$?
verifie "message propre : commit réussi" "$code"

echo b > g; git add g
printf 'ok\n\n# commentaire git avec /Users/%s\n' "$ID" > "$tmp/msg"
git commit -q -F "$tmp/msg" --cleanup=strip > "$tmp/sortie" 2>&1; code=$?
verifie "les lignes de commentaire ne comptent pas" "$code"

echo c > h; git add h
printf '%s\n' 'raise SystemExit(2)' > tools/identifiants_personnels.py
git commit -q -m "autre" > "$tmp/sortie" 2>&1; code=$?
verifie "scanner en erreur : commit refusé" "$([ $code -ne 0 ] && echo 0 || echo 1)"
verifie "scanner en erreur : dit que le message n'a pas pu être vérifié" "$(grep -qi 'pas pu être vérifié' "$tmp/sortie" && echo 0 || echo 1)"

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
