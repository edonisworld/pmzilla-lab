#!/bin/zsh
# Test de tools/install_links.sh dans un faux HOME : aucun fichier réel n'est touché.
# Lancement : zsh tests/installation/test_install_links.sh
set -u
RACINE="${0:A:h:h:h}"
HOME_FAUX=$(mktemp -d)
trap 'rm -rf "$HOME_FAUX"' EXIT
LAB="$HOME_FAUX/PMZilla-Lab"
mkdir -p "$LAB/workspace"
cp -R "$RACINE/tools" "$LAB/workspace/tools"
pass=0; fail=0
ok()  { print "ok : $1"; pass=$((pass + 1)); }
ko()  { print "ECHEC : $1"; fail=$((fail + 1)); }
verifier() { if eval "$2"; then ok "$1"; else ko "$1"; fi; }
lancer() { HOME="$HOME_FAUX" zsh "$LAB/workspace/tools/install_links.sh" "$@"; }

# copies de départ : une identique, une différente, un reliquat
cp "$LAB/workspace/tools/flux_jira.py" "$LAB/flux_jira.py"
print "# copie ancienne" > "$LAB/watch_lab.py"
print "vieux" > "$LAB/pmzilla_lab_library.py.avant-veille"

lancer --verify >/dev/null 2>&1; code=$?
verifier "--verify sort en erreur avec des liens manquants" '[[ $code -ne 0 ]]'
verifier "--verify ne crée rien" '[[ ! -L "$LAB/flux_jira.py" ]]'

sortie=$(lancer 2>&1)
for f in convert_books.py posture_evals.py flux_jira.py history_common.py mapping_lab.py pmzilla_lab_library.py watch_triage.py watch_lab.py sort_by_domain.py watch.sh; do
  verifier "$f est un lien vers tools/" '[[ "$(readlink "$LAB/'$f'")" == "workspace/tools/'$f'" && -e "$LAB/'$f'" ]]'
done
verifier "la copie différente est signalée" '[[ "$sortie" == *"watch_lab.py : COPIE DIFFÉRENTE"* ]]'
verifier "la copie identique est signalée" '[[ "$sortie" == *"flux_jira.py : copie identique"* ]]'
sauv=("$LAB"/copies-avant-liens-*(N))
verifier "une sauvegarde est créée" '[[ ${#sauv} -eq 1 ]]'
verifier "la copie différente est dans la sauvegarde" 'grep -q "copie ancienne" "$sauv[1]/watch_lab.py"'
verifier "le reliquat est rangé" '[[ -f "$sauv[1]/pmzilla_lab_library.py.avant-veille" && ! -e "$LAB/pmzilla_lab_library.py.avant-veille" ]]'
verifier "watch.sh reste exécutable par le lien" '[[ -x "$LAB/watch.sh" ]]'

sortie=$(lancer 2>&1)
sauv=("$LAB"/copies-avant-liens-*(N))
verifier "relance : aucun lien recréé" '[[ "$sortie" != *"lien créé"* ]]'
verifier "relance : aucune nouvelle sauvegarde" '[[ ${#sauv} -eq 1 ]]'
lancer --verify >/dev/null 2>&1; code=$?
verifier "--verify réussit une fois les liens créés" '[[ $code -eq 0 ]]'
sortie=$(lancer --verifier 2>&1); code=$?
verifier "l'ancien nom --verifier est refusé, code non nul, et nomme --verify" '[[ $code -ne 0 && "$sortie" == *"--verify"* ]]'

# le tableau SCRIPTS du script lui-même : le test le lit au lieu de le recopier, pour ne rien oublier
tableau=($(sed -n '/^SCRIPTS=(/,/)/p' "$LAB/workspace/tools/install_links.sh" | sed 's/^SCRIPTS=(//; s/)//' | tr -s ' ' '\n' | grep -v '^$'))
verifier "le tableau SCRIPTS contient posture_evals.py" '(( ${tableau[(Ie)posture_evals.py]} ))'
verifier "le tableau SCRIPTS contient au moins 10 scripts" '(( ${#tableau} >= 10 ))'
verifier "chaque script du tableau est dans tools/" 'for f in $tableau; do [[ -f "$LAB/workspace/tools/$f" ]] || return 1; done'
verifier "chaque script du tableau a son lien" 'for f in $tableau; do [[ "$(readlink "$LAB/$f")" == "workspace/tools/$f" && -e "$LAB/$f" ]] || return 1; done'

# --verify doit échouer, en nommant le script, quand UN lien du tableau manque (n'importe lequel, pas le premier)
for manquant in $tableau; do
  rm "$LAB/$manquant"
  sortie=$(lancer --verify 2>&1); code=$?
  verifier "--verify échoue quand le lien $manquant manque, et le nomme" '[[ $code -ne 0 && "$sortie" == *"absent     $manquant"* && "$sortie" != *"Tous les liens sont en place"* ]]'
  sortie=$(HOME="$HOME_FAUX" bash "$LAB/workspace/tools/install_links.sh" --verify 2>&1); code=$?
  verifier "lancé par bash : même verdict quand $manquant manque (le script repasse par zsh)" '[[ $code -ne 0 && "$sortie" == *"absent     $manquant"* ]]'
  lancer >/dev/null 2>&1
done
sortie=$(HOME="$HOME_FAUX" sh "$LAB/workspace/tools/install_links.sh" --verify 2>&1); code=$?
verifier "lancé par sh avec tous les liens en place : verdict correct et tous les scripts examinés" '[[ $code -eq 0 && "$sortie" == *"Tous les liens sont en place"* ]]'
verifier "--verify réussit une fois tous les liens recréés" '[[ -L "$LAB/posture_evals.py" ]] && lancer --verify >/dev/null 2>&1'

rm "$LAB/workspace/tools/sort_by_domain.py"
lancer >/dev/null 2>&1; code=$?
verifier "un script absent de tools/ arrête avec une erreur" '[[ $code -ne 0 ]]'

cp "$RACINE/tools/sort_by_domain.py" "$LAB/workspace/tools/"
lancer >/dev/null 2>&1
cp "$RACINE/tools/sort_by_domain.py" "$LAB/workspace/tools/"
lancer >/dev/null 2>&1
# l'ancien nom --verifier ne crée aucun lien : on le lance avec un lien manquant
rm "$LAB/flux_jira.py"
sortie=$(lancer --verifier 2>&1); code=$?
verifier "--verifier refusé ne crée aucun lien" '[[ $code -ne 0 && ! -e "$LAB/flux_jira.py" && "$sortie" != *"lien créé"* ]]'
# plus de nettoyage des liens pendants de scripts renommés : un lien pendant reste en place
ln -s workspace/tools/script_disparu.py "$LAB/script_disparu.py"
sortie=$(lancer 2>&1)
verifier "un lien pendant n'est plus retiré" '[[ -L "$LAB/script_disparu.py" && "$sortie" != *"ancien lien"* ]]'

print "$pass réussis, $fail échec(s)"
[[ $fail -eq 0 ]]
