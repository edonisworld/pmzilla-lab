#!/bin/sh
# Test du garde-fou « lancement vert » du hook pre-commit : dépôt Git temporaire, hook installé, aucune liste de noms.
# Lancement à la main : sh tests/hooks/test_pre_commit_green.sh
set -u
unset PMZILLA_SKIP_GREEN_CHECK
hook="$(cd "$(dirname "$0")/../../tools/hooks" && pwd)/pre-commit"
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
cd "$tmp" || exit 1
git init -q . && git config user.email t@example.org && git config user.name test
mkdir -p .git/hooks && ln -sf "$hook" .git/hooks/pre-commit
export PMZILLA_NOMS="$tmp/absente.txt"
ok=0; ko=0
verifie() { # description commande-attendue-en-échec|succès (0/1) ; reste : commande
  desc=$1; attendu=$2; shift 2
  sortie=$("$@" 2>&1); code=$?
  if [ "$code" -eq "$attendu" ]; then echo "ok : $desc"; ok=$((ok+1)); else echo "ECHEC : $desc (code $code, attendu $attendu) $sortie"; ko=$((ko+1)); fi
}
vert() { git rev-parse --git-path pmzilla-run-all-ok; }
marque() { git write-tree > "$(vert)"; }   # ce que fait run_all.sh après un lancement complet réussi

echo un > f.md; git add f.md
verifie "sans empreinte, le commit est refusé" 1 git commit -q -m t
git commit -q -m t 2>&1 | grep -q "lance d'abord bash tests/run_all.sh" && { echo "ok : message « lance d'abord bash tests/run_all.sh »"; ok=$((ok+1)); } || { echo "ECHEC : message du refus"; ko=$((ko+1)); }
marque
verifie "empreinte égale à l'index : commit accepté" 0 git commit -q -m t
echo deux > f.md; git add f.md
verifie "index modifié depuis le lancement : refusé" 1 git commit -q -m t
marque; echo trois > f.md; git add f.md
verifie "empreinte devenue périmée par un nouvel ajout : refusé" 1 git commit -q -m t
verifie "PMZILLA_SKIP_GREEN_CHECK=1 : contournement accepté" 0 env PMZILLA_SKIP_GREEN_CHECK=1 git commit -q -m t
echo quatre > f.md
verifie "commit -a : l'index temporaire n'a pas d'empreinte, refusé" 1 git commit -q -a -m t
git add f.md; marque
verifie "commit -a avec index déjà vert : accepté" 0 git commit -q -a -m t

# Garde sensible à la branche : l'empreinte ciblée (bash tests/run_all.sh --staged) n'est admise que hors main et hors tête détachée.
cible() { git rev-parse --git-path pmzilla-run-targeted-ok; }
marque_ciblee() { git write-tree > "$(cible)"; }
rm -f "$(vert)" "$(cible)"
git checkout -q -b travail
echo cinq > f.md; git add f.md
verifie "branche de travail sans empreinte : refusé" 1 git commit -q -m t
git commit -q -m t 2>&1 | grep -q "lance d'abord bash tests/run_all.sh --staged" && { echo "ok : message de branche « --staged »"; ok=$((ok+1)); } || { echo "ECHEC : message de branche"; ko=$((ko+1)); }
marque_ciblee
verifie "branche de travail, empreinte ciblée égale à l'index : accepté" 0 git commit -q -m t
echo six > f.md; git add f.md; marque_ciblee; echo sept > f.md; git add f.md
verifie "branche de travail, index modifié après le lancement ciblé : refusé" 1 git commit -q -m t
rm -f "$(cible)"; marque
verifie "branche de travail, empreinte complète : accepté" 0 git commit -q -m t
echo huit > f.md; git add f.md; marque_ciblee
git symbolic-ref HEAD refs/heads/main   # change la tête sans toucher à l'index (la branche main existe : le dépôt est créé sur main)
verifie "main avec la seule empreinte ciblée : refusé" 1 git commit -q -m t
git commit -q -m t 2>&1 | grep -q "lance d'abord bash tests/run_all.sh (après git add)" && { echo "ok : message de main inchangé"; ok=$((ok+1)); } || { echo "ECHEC : message de main"; ko=$((ko+1)); }
marque
verifie "main avec l'empreinte complète : accepté" 0 git commit -q -m t
echo neuf > f.md; git add f.md; marque_ciblee; rm -f "$(vert)"
git checkout -q --detach
verifie "tête détachée avec la seule empreinte ciblée : refusé" 1 git commit -q -m t
verifie "tête détachée, contournement : accepté" 0 env PMZILLA_SKIP_GREEN_CHECK=1 git commit -q -m t

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
