#!/bin/sh
# Test du hook pre-push : dépôt Git temporaire avec un remote nu temporaire, lanceur factice (PRE_PUSH_RUNNER).
# Lancement à la main : sh tests/hooks/test_pre_push.sh
set -u
unset PMZILLA_SKIP_GREEN_CHECK PRE_PUSH_RUNNER
hook="$(cd "$(dirname "$0")/../../tools/hooks" && pwd)/pre-push"
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
git init -q --bare "$tmp/distant.git"
git init -q -b main "$tmp/depot" && cd "$tmp/depot" || exit 1
git config user.email t@example.org && git config user.name test
git remote add origin "$tmp/distant.git"
ln -sf "$hook" .git/hooks/pre-push
ok=0; ko=0
verifie() { # description code-attendu ; reste : commande
  desc=$1; attendu=$2; shift 2
  sortie=$("$@" 2>&1); code=$?
  if [ "$code" -eq "$attendu" ]; then echo "ok : $desc"; ok=$((ok+1)); else echo "ECHEC : $desc (code $code, attendu $attendu) $sortie"; ko=$((ko+1)); fi
}
vert() { git rev-parse --git-path pmzilla-run-all-ok; }
cible() { git rev-parse --git-path pmzilla-run-targeted-ok; }
valide() { echo "$1" > f.md; git add f.md; git commit -q --no-verify -m "$1"; }   # le commit sans hook : le test porte sur pre-push
echo "echo ok > $tmp/lance" > "$tmp/vert.sh"
echo "echo rouge; exit 1" > "$tmp/rouge.sh"

valide un
git rev-parse 'HEAD^{tree}' > "$(vert)"
verifie "main : empreinte complète égale à l'arbre poussé, passe sans lancer de test" 0 env PRE_PUSH_RUNNER="sh $tmp/vert.sh" git push -q origin main
verifie "main : aucun lanceur n'a tourné" 1 test -e "$tmp/lance"

valide deux
verifie "main : arbre propre, HEAD poussé, lanceur factice vert : accepté" 0 env PRE_PUSH_RUNNER="sh $tmp/vert.sh" git push -q origin main
verifie "main : le lanceur a bien été lancé par le hook" 0 test -e "$tmp/lance"
rm -f "$tmp/lance"

valide trois
rm -f "$(vert)"
verifie "main : lanceur factice rouge : refusé" 1 env PRE_PUSH_RUNNER="sh $tmp/rouge.sh" git push -q origin main
env PRE_PUSH_RUNNER="sh $tmp/rouge.sh" git push -q origin main 2>&1 | grep -q "pre-push : main exige une exécution complète réussie de l'arbre poussé" && { echo "ok : message du refus"; ok=$((ok+1)); } || { echo "ECHEC : message du refus"; ko=$((ko+1)); }

git rev-parse 'HEAD^{tree}' > "$(cible)"
verifie "main : l'empreinte ciblée seule ne suffit pas (lanceur rouge)" 1 env PRE_PUSH_RUNNER="sh $tmp/rouge.sh" git push -q origin main

echo sale > f.md
verifie "main : arbre sale sans empreinte : refusé sans lancer le lanceur" 1 env PRE_PUSH_RUNNER="sh $tmp/vert.sh" git push -q origin main
verifie "main : le lanceur n'a pas tourné sur un arbre sale" 1 test -e "$tmp/lance"
git checkout -q -- f.md

git checkout -q -b travail
valide quatre
verifie "branche de travail : aucun contrôle" 0 env PRE_PUSH_RUNNER="sh $tmp/rouge.sh" git push -q origin travail
git checkout -q main
verifie "poussée de HEAD (travail) vers main sans être sur le commit : refusé" 1 env PRE_PUSH_RUNNER="sh $tmp/vert.sh" git push -q origin travail:main
verifie "contournement PMZILLA_SKIP_GREEN_CHECK=1 : accepté" 0 env PMZILLA_SKIP_GREEN_CHECK=1 PRE_PUSH_RUNNER="sh $tmp/rouge.sh" git push -q origin travail:main
verifie "suppression d'une branche distante : aucun contrôle" 0 env PRE_PUSH_RUNNER="sh $tmp/rouge.sh" git push -q origin :travail

# Référence poussée dont l'arbre est introuvable : refusée (entrée standard fabriquée, hook lancé directement)
inconnu=1234567890123456789012345678901234567890
sortie=$(printf 'refs/heads/main %s refs/heads/main %s\n' "$inconnu" 0000000000000000000000000000000000000000 | PRE_PUSH_RUNNER="sh $tmp/vert.sh" sh "$hook" origin x 2>&1); code=$?
if [ "$code" -eq 1 ]; then echo "ok : arbre introuvable : refusé"; ok=$((ok+1)); else echo "ECHEC : arbre introuvable : refusé (code $code)"; ko=$((ko+1)); fi
case "$sortie" in *"main exige une exécution complète réussie de l'arbre poussé"*) echo "ok : arbre introuvable : message du refus"; ok=$((ok+1));; *) echo "ECHEC : arbre introuvable : message du refus"; ko=$((ko+1));; esac
verifie "arbre introuvable : le lanceur n'a pas tourné" 1 test -e "$tmp/lance"

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
