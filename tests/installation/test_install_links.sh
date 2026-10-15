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
cp -R "$RACINE/tools" "$LAB/run-tools-copie" && mkdir -p "$LAB/run" && mv "$LAB/run-tools-copie" "$LAB/run/tools"   # dossier d'exécution factice
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
for f in convert_books.py posture_evals.py flux_jira.py history_common.py mapping_lab.py pmzilla_lab_library.py watch_triage.py watch_lab.py sort_by_domain.py morning_summary.py watch.sh db_backup.sh offsite_backup.sh doctor.sh; do
  verifier "$f est un lien vers tools/ du dossier d'exécution" '[[ "$(readlink "$LAB/'$f'")" == "run/tools/'$f'" && -e "$LAB/'$f'" ]]'
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
verifier "le tableau SCRIPTS contient au moins 13 scripts" '(( ${#tableau} >= 13 ))'
verifier "le tableau SCRIPTS contient les scripts de sauvegarde, de copie hors du Mac et du doctor" '(( ${tableau[(Ie)db_backup.sh]} && ${tableau[(Ie)offsite_backup.sh]} && ${tableau[(Ie)doctor.sh]} ))'
verifier "chaque script du tableau est dans tools/ du dossier d'exécution" 'for f in $tableau; do [[ -f "$LAB/run/tools/$f" ]] || return 1; done'
verifier "chaque script du tableau a son lien" 'for f in $tableau; do [[ "$(readlink "$LAB/$f")" == "run/tools/$f" && -e "$LAB/$f" ]] || return 1; done'

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

rm "$LAB/run/tools/sort_by_domain.py"
lancer >/dev/null 2>&1; code=$?
verifier "un script absent de tools/ arrête avec une erreur" '[[ $code -ne 0 ]]'

cp "$RACINE/tools/sort_by_domain.py" "$LAB/run/tools/"
lancer >/dev/null 2>&1
# l'ancien nom --verifier ne crée aucun lien : on le lance avec un lien manquant
rm "$LAB/flux_jira.py"
sortie=$(lancer --verifier 2>&1); code=$?
verifier "--verifier refusé ne crée aucun lien" '[[ $code -ne 0 && ! -e "$LAB/flux_jira.py" && "$sortie" != *"lien créé"* ]]'
# plus de nettoyage des liens pendants de scripts renommés : un lien pendant reste en place
ln -s workspace/tools/script_disparu.py "$LAB/script_disparu.py"
sortie=$(lancer 2>&1)
verifier "un lien pendant n'est plus retiré" '[[ -L "$LAB/script_disparu.py" && "$sortie" != *"ancien lien"* ]]'

# --- change run-worktree, groupe 8 : cibles, refus sans dossier d'exécution, scripts planifiés, sauvegarde par son lien ---
lancer >/dev/null 2>&1
liens_avant=$(for f in $tableau; do print "$f=$(readlink "$LAB/$f")"; done)

# retour en arrière : --target workspace vise tools/ du dépôt de développement, et nomme chaque lien refait
sortie=$(lancer --target workspace 2>&1); code=$?
verifier "--target workspace : réussit" '[[ $code -eq 0 ]]'
verifier "--target workspace : chaque lien vise tools/ du dépôt de développement" 'for f in $tableau; do [[ "$(readlink "$LAB/$f")" == "workspace/tools/$f" && -e "$LAB/$f" ]] || return 1; done'
verifier "--target workspace : les liens refaits sont nommés" '[[ "$sortie" == *"mauvais dossier  watch.sh"* && "$sortie" == *"lien créé  doctor.sh -> workspace/tools/doctor.sh"* ]]'
lancer --verify --target workspace >/dev/null 2>&1; code=$?
verifier "--verify --target workspace réussit après le retour en arrière" '[[ $code -eq 0 ]]'
sortie=$(lancer --verify 2>&1); code=$?
verifier "--verify (cible par défaut) après le retour en arrière : échoue et nomme chaque lien visant le mauvais dossier" '[[ $code -ne 0 && "$sortie" == *"mauvais dossier  watch.sh"* && "$sortie" == *"mauvais dossier  doctor.sh"* ]]'
sortie=$(lancer 2>&1); code=$?
verifier "bascule : chaque lien revient dans le dossier d'exécution et la sortie nomme chaque lien refait" '[[ $code -eq 0 && "$sortie" == *"mauvais dossier  db_backup.sh"* ]] && for f in $tableau; do [[ "$(readlink "$LAB/$f")" == "run/tools/$f" ]] || return 1; done'

# un seul lien visé sur l'autre dossier : --verify le nomme, sort en erreur et ne change rien
rm "$LAB/offsite_backup.sh"; ln -s workspace/tools/offsite_backup.sh "$LAB/offsite_backup.sh"
sortie=$(lancer --verify 2>&1); code=$?
verifier "--verify : un lien visé sur l'autre dossier est nommé et le code n'est pas nul" '[[ $code -ne 0 && "$sortie" == *"mauvais dossier  offsite_backup.sh"* && "$sortie" != *"Tous les liens sont en place"* ]]'
verifier "--verify ne change rien" '[[ "$(readlink "$LAB/offsite_backup.sh")" == "workspace/tools/offsite_backup.sh" && "$sortie" != *"lien créé"* ]]'
lancer >/dev/null 2>&1

# dossier d'exécution absent : refus, commande de création nommée, aucun lien créé ni changé
mv "$LAB/run" "$LAB/run-absent"
lancer --target workspace >/dev/null 2>&1                       # liens vers workspace, état connu avant le refus
avant=$(for f in $tableau; do print "$f=$(readlink "$LAB/$f")"; done)
rm "$LAB/flux_jira.py"
sortie=$(lancer 2>&1); code=$?
verifier "sans dossier d'exécution : refus, code non nul, commande de création nommée" '[[ $code -ne 0 && "$sortie" == *"bash tools/run_worktree.sh create"* ]]'
verifier "sans dossier d'exécution : aucun lien créé ni changé" '[[ ! -e "$LAB/flux_jira.py" && "$(for f in $tableau; do [[ -L "$LAB/$f" ]] && print "$f=$(readlink "$LAB/$f")"; done)" == "$(print -r -- "$avant" | grep -v "^flux_jira.py=")" ]]'
sortie=$(lancer --verify 2>&1); code=$?
verifier "sans dossier d'exécution : --verify refuse aussi" '[[ $code -ne 0 && "$sortie" == *"bash tools/run_worktree.sh create"* ]]'
lancer --target workspace >/dev/null 2>&1; code=$?
verifier "sans dossier d'exécution : --target workspace fonctionne (retour en arrière possible)" '[[ $code -eq 0 && "$(readlink "$LAB/flux_jira.py")" == "workspace/tools/flux_jira.py" ]]'
mv "$LAB/run-absent" "$LAB/run"
lancer >/dev/null 2>&1

# option inconnue ou valeur de --target inconnue
lancer --target ailleurs >/dev/null 2>&1; code=$?
verifier "--target avec une valeur inconnue est refusé" '[[ $code -eq 2 ]]'

# chaque script lancé par un modèle launchd figure dans le tableau (modèles lus dans le dépôt, doctor compris)
programmes=()
for modele in "$RACINE"/tools/com.pmzilla.*.plist; do
  programmes+=($(sed -nE 's#.*<string>[^<]*/([A-Za-z0-9_]+\.(sh|py))</string>.*#\1#p' "$modele"))
done
verifier "les modèles launchd nomment au moins watch.sh, db_backup.sh, offsite_backup.sh et doctor.sh" '(( ${programmes[(Ie)watch.sh]} && ${programmes[(Ie)db_backup.sh]} && ${programmes[(Ie)offsite_backup.sh]} && ${programmes[(Ie)doctor.sh]} ))'
verifier "chaque script lancé par un modèle est dans le tableau (doctor.sh compris)" 'for f in ${(u)programmes}; do (( ${tableau[(Ie)$f]} )) || { print "absent du tableau : $f"; return 1; }; done'

# la sauvegarde lancée par son lien trouve le dossier de code que le lien vise, jamais le dossier du labo
mkdir -p "$HOME_FAUX/bin" "$HOME_FAUX/sauvegardes" "$HOME_FAUX/donnees"
cat > "$HOME_FAUX/bin/docker" <<'STUB'
#!/bin/sh
echo "$PWD|$PMZILLA_LAB_WORKSPACE" >> "$STUB_JOURNAL"
case "$*" in *"ps -q"*) echo abc ;; *psql*) echo 1 ;; *pg_dump*) echo donnees ;; esac
exit 0
STUB
chmod +x "$HOME_FAUX/bin/docker"
lancer_sauvegarde() { HOME="$HOME_FAUX" PATH="$HOME_FAUX/bin:$PATH" STUB_JOURNAL="$HOME_FAUX/docker.log" DB_BACKUP_SAUVEGARDES="$HOME_FAUX/sauvegardes" \
  PMZILLA_LAB_DATA="$HOME_FAUX/donnees" DB_BACKUP_DATE=2026-01-02 bash "$LAB/db_backup.sh" 2>&1; }
: > "$HOME_FAUX/docker.log"
sortie=$(lancer_sauvegarde); code=$?
verifier "sauvegarde par son lien : réussit" '[[ $code -eq 0 ]]'
attendu_code=$(cd "$LAB/run" && pwd -P)
verifier "sauvegarde par son lien : le dossier de code est le dossier d'exécution, pas le dossier du labo" 'head -1 "$HOME_FAUX/docker.log" | cut -d"|" -f1 | { read -r l; [[ "$(cd "$l" && pwd -P)" == "$attendu_code" ]]; }'
verifier "sauvegarde par son lien : exporte le dossier de contenu (défaut : le dépôt de développement)" '[[ "$(head -1 "$HOME_FAUX/docker.log" | cut -d"|" -f2)" == "$LAB/workspace" ]]'
lancer --target workspace >/dev/null 2>&1
rm -rf "$HOME_FAUX/sauvegardes/db-2026-01-02"; : > "$HOME_FAUX/docker.log"
lancer_sauvegarde >/dev/null
attendu_dev=$(cd "$LAB/workspace" && pwd -P)
verifier "sauvegarde par son lien après le retour en arrière : le dossier de code est le dépôt de développement" 'head -1 "$HOME_FAUX/docker.log" | cut -d"|" -f1 | { read -r l; [[ "$(cd "$l" && pwd -P)" == "$attendu_dev" ]]; }'
lancer >/dev/null 2>&1

print "$pass réussis, $fail échec(s)"
[[ $fail -eq 0 ]]
