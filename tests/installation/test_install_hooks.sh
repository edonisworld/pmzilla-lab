#!/bin/sh
# Test de tools/install_hooks.sh dans un dépôt Git temporaire : aucun hook réel n'est touché.
# Lancement : sh tests/installation/test_install_hooks.sh
set -u
RACINE=$(cd "$(dirname "$0")/../.." && pwd)
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/tools/hooks"
cp "$RACINE/tools/install_hooks.sh" "$tmp/tools/"
for h in pre-commit post-commit commit-msg pre-push; do printf '#!/bin/sh\nexit 0\n' > "$tmp/tools/hooks/$h"; chmod -x "$tmp/tools/hooks/$h"; done
cd "$tmp" && git init -q . || exit 1
ok=0; ko=0
verifie() { if eval "$2"; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1"; ko=$((ko+1)); fi; }
installe() { bash tools/install_hooks.sh "$@" >"$tmp/sortie" 2>&1; }

installe --verify; code=$?
verifie "--verify sort en erreur sans les liens" '[ $code -ne 0 ]'
verifie "--verify ne crée rien" '[ ! -e .git/hooks/pre-commit ] && [ ! -L .git/hooks/pre-commit ]'

echo "ancien" > .git/hooks/pre-commit
installe; code=$?
verifie "l'installation réussit" '[ $code -eq 0 ]'
for h in pre-commit post-commit commit-msg pre-push; do
  verifie "$h : lien relatif vers ../../tools/hooks/$h" '[ "$(readlink .git/hooks/'$h')" = "../../tools/hooks/'$h'" ]'
  verifie "$h : le hook est exécutable" '[ -x tools/hooks/'$h' ]'
done
verifie "un hook existant est rangé, pas supprimé" '[ "$(cat .git/hooks/pre-commit.avant-install)" = "ancien" ]'
verifie "le message dit « Tous les hooks sont en place »" 'grep -q "Tous les hooks sont en place" "$tmp/sortie"'

installe; code=$?
verifie "deuxième lancement : succès" '[ $code -eq 0 ]'
verifie "deuxième lancement : aucun nouveau rangement" '[ ! -e .git/hooks/pre-commit.avant-install.avant-install ] && [ "$(ls .git/hooks | grep -c avant-install)" -eq 1 ]'
verifie "deuxième lancement : liens inchangés" '[ "$(readlink .git/hooks/commit-msg)" = "../../tools/hooks/commit-msg" ]'

rm .git/hooks/post-commit; ln -s ../../tools/hooks/inexistant .git/hooks/post-commit
installe; code=$?
verifie "un lien mal dirigé est réparé" '[ $code -eq 0 ] && [ "$(readlink .git/hooks/post-commit)" = "../../tools/hooks/post-commit" ]'

rm .git/hooks/pre-push
installe --verify; code=$?
verifie "--verify : le lien pre-push manquant fait échouer et est nommé" '[ $code -ne 0 ] && grep -q "pre-push" "$tmp/sortie"'
installe; code=$?
verifie "l'installation recrée le lien pre-push" '[ $code -eq 0 ] && [ "$(readlink .git/hooks/pre-push)" = "../../tools/hooks/pre-push" ]'

rm tools/hooks/commit-msg
installe; code=$?
verifie "un hook source absent est un échec nommé" '[ $code -ne 0 ] && grep -q "ABSENT : tools/hooks/commit-msg" "$tmp/sortie"'

# Hors dépôt Git : erreur, aucun lien. Dossier des hooks non standard (core.hooksPath) : erreur, aucun lien.
mkdir -p "$tmp/hors/tools/hooks"
cp "$RACINE/tools/install_hooks.sh" "$tmp/hors/tools/"
for h in pre-commit post-commit commit-msg pre-push; do printf '#!/bin/sh\nexit 0\n' > "$tmp/hors/tools/hooks/$h"; done
# le dépôt temporaire $tmp est un dépôt Git : GIT_CEILING_DIRECTORIES l'empêche d'être trouvé depuis hors/
( cd "$tmp/hors" && GIT_CEILING_DIRECTORIES="$tmp" bash tools/install_hooks.sh >"$tmp/sortie" 2>&1 ); code=$?
verifie "hors dépôt Git : sortie en erreur" '[ $code -ne 0 ] && grep -q "Pas un dépôt Git" "$tmp/sortie"'
verifie "hors dépôt Git : aucun lien créé" '[ ! -e "$tmp/hors/.git" ] && [ -z "$(find "$tmp/hors" -type l)" ]'

git init -q "$tmp/perso" && mkdir -p "$tmp/perso/tools/hooks" "$tmp/perso/mes-hooks"
cp "$tmp/hors/tools/install_hooks.sh" "$tmp/perso/tools/"
for h in pre-commit post-commit commit-msg pre-push; do printf '#!/bin/sh\nexit 0\n' > "$tmp/perso/tools/hooks/$h"; done
( cd "$tmp/perso" && git config core.hooksPath mes-hooks && bash tools/install_hooks.sh >"$tmp/sortie" 2>&1 ); code=$?
verifie "dossier des hooks non standard : sortie en erreur" '[ $code -ne 0 ] && grep -q "Dossier des hooks inattendu" "$tmp/sortie"'
verifie "dossier des hooks non standard : aucun lien créé" '[ -z "$(find "$tmp/perso" -type l)" ] && [ -z "$(ls "$tmp/perso/mes-hooks")" ]'
verifie "dossier des hooks non standard : --verify échoue aussi" '( cd "$tmp/perso" && ! bash tools/install_hooks.sh --verify >/dev/null 2>&1 )'

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
