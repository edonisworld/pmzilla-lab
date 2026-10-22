#!/bin/bash
# PMZilla Lab : enveloppeur planifié du doctor (change doctor-command, design D6). Lancé chaque jour par launchd
# (com.pmzilla.doctor.plist), après la veille, la sauvegarde de la base et la copie hors du Mac. Journal : ~/Library/Logs/pmzilla-doctor.log
#
# Lance « doctor.py --record » avec DOCTOR_NOTIFIER=1 (état dans le dossier de données, notification s'il y a un problème, au plus une
# par jour), puis régénère le tableau de bord, sans jamais échouer à cause de lui. Sort avec le code du doctor : 0 sans problème,
# 1 avec au moins un problème, 2 si le doctor n'a pas pu tourner. Le tableau de bord ouvre une session de base : la session Claude Code
# ne lance jamais ce script (règles deny de .claude/settings.json) ; elle lance doctor.py, en lecture seule.
#
# Exemple :
#     bash tools/doctor.sh
set -u
export PATH="$PATH:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin"   # launchd donne un PATH minimal ; ajouté à la fin, un PATH déjà complet reste prioritaire
# Le script se lance par son lien du dossier du labo (<dossier du lab>/<script>) : on résout le lien pour trouver le dossier de code
# (le dossier d'exécution, ou le dépôt de développement après un retour en arrière), jamais le dossier du labo.
SOI="$0"
while [ -L "$SOI" ]; do
  CIBLE_LIEN="$(readlink "$SOI")"
  case "$CIBLE_LIEN" in /*) SOI="$CIBLE_LIEN" ;; *) SOI="$(dirname "$SOI")/$CIBLE_LIEN" ;; esac
done
RACINE="$(cd "$(dirname "$SOI")/.." && pwd)"
# Dossier de contenu : le module partagé tools/lab_paths.sh (variable, sinon dépôt Git du code). Le doctor ne s'arrête jamais (D7) :
# s'il n'est pas trouvé, la variable reste telle quelle et doctor.py le signale comme un problème de sa propre vérification.
. "$RACINE/tools/lab_paths.sh"
if lab_paths_init; then PMZILLA_LAB_WORKSPACE="$LAB_CONTENT_ROOT"; export PMZILLA_LAB_WORKSPACE; fi
echo "=== $(date '+%Y-%m-%d %H:%M') ==="
code=0
DOCTOR_NOTIFIER=1 uv run "$RACINE/tools/doctor.py" --record || code=$?
uv run "$RACINE/tools/dashboard.py" || echo "Tableau de bord non généré (voir ci-dessus)"
exit "$code"
