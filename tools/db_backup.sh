#!/bin/bash
# PMZilla Lab : sauvegarde de la base PostgreSQL, un pg_dump par schéma (knowledge, cases, flow), plus le dump partiel quality-sans-texte
# (trois tables de quality, sans texte de story ni clé de ticket : voir plus bas).
#
#     bash tools/db_backup.sh
#
# Lance pg_dump dans le conteneur (service db, socket locale : aucun mot de passe, ni dans l'environnement ni dans le compose) et écrit un fichier par schéma dans
# ~/.pmzilla-lab/sauvegardes/db-AAAA-MM-JJ/ (hors du dépôt), au format personnalisé (-Fc, restaurable avec pg_restore).
# Lancé chaque jour à 7 h 45 par launchd (com.pmzilla.db-backup.plist). Journal : ~/Library/Logs/pmzilla-db-backup.log
# Jamais d'écrasement : si le dossier du jour existe, le script le dit et se termine en succès (code 0, cas normal d'un
# second passage), avant même de toucher à Docker. Garde ensuite les 14 dossiers db-* les plus récents et supprime les plus
# anciens en affichant ce qu'il supprime. Un schéma absent est signalé et le script se termine en échec (code 1) après
# avoir sauvegardé les autres. Docker injoignable, conteneur arrêté ou PostgreSQL muet : message clair et code 2.
# Il n'affiche que des chemins et des tailles. Aucun mot de passe : pg_dump passe par la socket locale du conteneur
# (le Trousseau n'est pas lu ici, seulement par db_up.sh). Dossiers en 700, dumps en 600.
#
# Codes : 0 sauvegarde faite (ou déjà présente), 1 sauvegarde partielle ou nulle, 2 environnement ou argument invalide.
# Notification macOS (osascript) sur tout code non nul, seulement si DB_BACKUP_NOTIFIER=1 (posé par le .plist, jamais
# en lancement à la main).
#
# Variables (pour les tests) : DB_BACKUP_SAUVEGARDES (défaut : « sauvegardes » sous PMZILLA_LAB_DATA, soit
# ~/.pmzilla-lab/sauvegardes, par tools/lab_paths.sh), DB_BACKUP_DATE (défaut : date du jour, AAAA-MM-JJ ;
# AAAA-MM-JJ-étiquette en minuscules et chiffres pour une deuxième sauvegarde le même jour, jamais
# supprimée par la rotation), DB_BACKUP_GARDER (défaut : 14, entier au moins égal à 1), DB_BACKUP_SCHEMAS (défaut :
# knowledge cases flow), DB_BACKUP_NOTIFIER (défaut : vide, pas de notification), PMZILLA_LAB_DATA (dossier de données du labo,
# défaut ~/.pmzilla-lab : repère sauvegarde.encours), PMZILLA_RUN_MARKER_MAX_AGE (âge maximal du repère, défaut 21600 secondes),
# PMZILLA_LAB_WORKSPACE (dossier de contenu exporté, défaut le dépôt de développement).
# Lancé par son lien <dossier du lab>/db_backup.sh : le script résout le lien pour trouver son dossier de code.
# Repère de passage (D14) : dossier sauvegarde.encours créé avec mkdir après les contrôles d'argument, retiré à la sortie par le seul
# processus qui l'a créé ; il n'empêche jamais la sauvegarde et ne change jamais son code de sortie.
set -uo pipefail
umask 077
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"   # launchd donne un PATH minimal ; ajouté à la fin, un PATH déjà complet reste prioritaire
# Le script se lance par son lien du dossier du labo (<dossier du lab>/<script>) : on résout le lien pour trouver le dossier de code
# (le dossier d'exécution, ou le dépôt de développement après un retour en arrière), jamais le dossier du labo.
SOI="$0"
while [ -L "$SOI" ]; do
  CIBLE_LIEN="$(readlink "$SOI")"
  case "$CIBLE_LIEN" in /*) SOI="$CIBLE_LIEN" ;; *) SOI="$(dirname "$SOI")/$CIBLE_LIEN" ;; esac
done
RACINE="$(cd "$(dirname "$SOI")/.." && pwd)"
# Dossier de contenu : le module partagé tools/lab_paths.sh (variable, sinon dépôt Git du code) ; sinon code 78, avant tout pas.
. "$RACINE/tools/lab_paths.sh"
lab_paths_init || exit $?
PMZILLA_LAB_WORKSPACE="$LAB_CONTENT_ROOT"
export PMZILLA_LAB_WORKSPACE
cd "$RACINE" || exit 2
DEST="$LAB_BACKUPS_FOLDER"   # DB_BACKUP_SAUVEGARDES, sinon <dossier de données du labo>/sauvegardes (tools/lab_paths.sh)
DATE="${DB_BACKUP_DATE:-$(date +%Y-%m-%d)}"
GARDER="${DB_BACKUP_GARDER:-14}"
SCHEMAS="${DB_BACKUP_SCHEMAS:-knowledge cases flow}"
REPERE_DONNEES="${PMZILLA_LAB_DATA:-$HOME/.pmzilla-lab}"

# --- Repère de passage (change run-worktree, D14) : dossier créé par mkdir dans le dossier de données du labo, avec le pid et le début.
# Le repère ne protège pas d'un double passage : il dit seulement à la mise à jour du dossier d'exécution qu'un passage est en cours.
# Même règle de péremption que le verrou de la veille : pid mort, ou âge (secondes écoulées depuis le début) au-dessus du maximum.
AGE_MAX_REPERE="${PMZILLA_RUN_MARKER_MAX_AGE:-21600}"
printf '%s' "$AGE_MAX_REPERE" | grep -Eq '^[0-9]+$' || AGE_MAX_REPERE=21600
REPERE=""; REPERE_PROPRIETAIRE=""
repere_maintenant() { echo "${PMZILLA_RUN_NOW:-$(date +%s)}"; }
repere_perime() {   # 0 si le dossier $1 est périmé (pid mort, trop vieux, ou abandonné), 1 s'il est tenu
  local dossier=$1 pid debut age mtime
  pid="$(cat "$dossier/pid" 2>/dev/null)"
  if ! printf '%s' "$pid" | grep -Eq '^[0-9]+$'; then   # création en cours, ou dossier abandonné
    mtime="$(stat -f %m "$dossier" 2>/dev/null || stat -c %Y "$dossier" 2>/dev/null)"
    printf '%s' "$mtime" | grep -Eq '^[0-9]+$' && [ $(( $(date +%s) - mtime )) -gt 10 ] && return 0
    return 1
  fi
  kill -0 "$pid" 2>/dev/null || return 0
  debut="$(cat "$dossier/debut" 2>/dev/null)"
  if printf '%s' "$debut" | grep -Eq '^[0-9]+$'; then
    age=$(( $(repere_maintenant) - debut ))
  else
    mtime="$(stat -f %m "$dossier" 2>/dev/null || stat -c %Y "$dossier" 2>/dev/null)"
    printf '%s' "$mtime" | grep -Eq '^[0-9]+$' || return 1
    age=$(( $(date +%s) - mtime ))
  fi
  [ "$age" -gt "$AGE_MAX_REPERE" ] && return 0
  return 1
}
poser_repere() {   # nom-du-dossier : crée le repère, ou journalise pourquoi il n'est pas créé ; ne change jamais le code de sortie
  local dossier="$REPERE_DONNEES/$1" essai
  mkdir -p "$REPERE_DONNEES" 2>/dev/null
  for essai in 1 2; do
    if mkdir "$dossier" 2>/dev/null; then
      echo "$$" > "$dossier/pid"; repere_maintenant > "$dossier/debut"
      REPERE="$dossier"; REPERE_PROPRIETAIRE=1
      return 0
    fi
    if [ ! -d "$dossier" ]; then echo "Repère de passage impossible à écrire"; return 0; fi
    if [ "$essai" -eq 1 ] && repere_perime "$dossier"; then
      # renommage atomique : un seul processus reprend le repère périmé
      mv "$dossier" "$dossier.perime.$$" 2>/dev/null && rm -rf "$dossier.perime.$$"
      echo "Repère de passage périmé, repris"
      continue
    fi
    echo "Repère de passage déjà tenu : passage sans repère propre"; return 0
  done
  echo "Repère de passage impossible à écrire"; return 0
}
retirer_repere() {   # seulement le processus qui l'a créé
  [ -n "$REPERE_PROPRIETAIRE" ] && [ "$(cat "$REPERE/pid" 2>/dev/null)" = "$$" ] && rm -rf "$REPERE"
  return 0
}

RAISON="voir le journal ~/Library/Logs/pmzilla-db-backup.log"
notifier_a_la_sortie() {   # un échec de notification ne change jamais le code de sortie
  local code=$?
  retirer_repere
  if [ "$code" -ne 0 ] && [ "${DB_BACKUP_NOTIFIER:-}" = "1" ]; then
    osascript -e "display notification \"Sauvegarde de la base en échec (code $code) : $RAISON\" with title \"PMZilla db-backup\"" \
      >/dev/null 2>&1 || echo "Notification macOS impossible"
  fi
}
trap notifier_a_la_sortie EXIT
echec() {   # code message : affiche, retient pour la notification, sort
  echo "$2"; RAISON="$2"; exit "$1"
}
echo "=== $(date '+%Y-%m-%d %H:%M') ==="

if ! printf '%s' "$GARDER" | grep -Eq '^[1-9][0-9]*$'; then
  echec 2 "DB_BACKUP_GARDER invalide : $GARDER (entier au moins égal à 1)"
fi
if ! printf '%s' "$DATE" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}(-[a-z0-9]+)?$'; then
  echec 2 "Date invalide : $DATE (attendu AAAA-MM-JJ, ou AAAA-MM-JJ-étiquette pour une deuxième sauvegarde le même jour)"
fi
poser_repere sauvegarde.encours
CIBLE="$DEST/db-$DATE"
if [ -e "$CIBLE" ]; then
  echo "La sauvegarde du jour existe déjà : $CIBLE (rien n'a été écrit ni supprimé)"; exit 0
fi
command -v docker >/dev/null 2>&1 || echec 2 "Docker est introuvable (brew install colima docker docker-compose)"
# Trois états distincts : Docker injoignable, conteneur arrêté, conteneur démarré mais PostgreSQL muet.
if ! docker info >/dev/null 2>&1; then
  echec 2 "Docker ne répond pas : Colima est probablement arrêté. Vérifier : colima status (puis colima start --cpu 4 --memory 6)"
fi
if [ -z "$(docker compose ps -q --status running db 2>/dev/null)" ]; then
  echec 2 "Le conteneur de la base est arrêté. Le démarrer : bash tools/db_up.sh"
fi
if ! docker compose exec -T db pg_isready -U postgres -d pmzilla >/dev/null 2>&1; then
  echec 2 "Le conteneur tourne mais PostgreSQL ne répond pas (démarrage en cours ?). Voir : docker compose ps, docker compose logs db"
fi
mkdir -p "$CIBLE" || echec 2 "Impossible de créer $CIBLE"
chmod 700 "$DEST" "$CIBLE" 2>/dev/null || true

echecs=0; faits=0
for schema in $SCHEMAS; do
  existe="$(docker compose exec -T db psql -U postgres -d pmzilla -Atc "select 1 from pg_namespace where nspname = '$schema'" 2>/dev/null | tr -d '[:space:]')"
  if [ "$existe" != "1" ]; then
    echo "Schéma absent, non sauvegardé : $schema"; echecs=$((echecs + 1)); continue
  fi
  fichier="$CIBLE/$schema.dump"
  if docker compose exec -T db pg_dump -U postgres -d pmzilla -n "$schema" -Fc > "$fichier" 2>/dev/null && [ -s "$fichier" ]; then
    chmod 600 "$fichier" 2>/dev/null || true
    echo "Sauvegarde créée : $fichier ($(wc -c < "$fichier" | tr -d ' ') octets)"; faits=$((faits + 1))
  else
    echo "Échec de pg_dump pour le schéma : $schema"; rm -f "$fichier"; echecs=$((echecs + 1))
  fi
done
# Dump partiel de quality (change story-quality-audit, D10 amendé le 2026-10-18) : TROIS tables nommées une à une (attributs d'équipe,
# relectures d'équipe, versions de surcouche), données seulement (le schéma vient des migrations), dans quality-sans-texte.dump. Jamais le
# schéma quality entier, jamais les éléments, contenus, verdicts ni retours de coaching : aucun texte de story ni clé de ticket.
existe="$(docker compose exec -T db psql -U postgres -d pmzilla -Atc "select 1 from pg_namespace where nspname = 'quality'" 2>/dev/null | tr -d '[:space:]')"
if [ "$existe" != "1" ]; then
  echo "Schéma absent, non sauvegardé : quality (dump partiel)"; echecs=$((echecs + 1))
else
  fichier="$CIBLE/quality-sans-texte.dump"
  if docker compose exec -T db pg_dump -U postgres -d pmzilla --data-only -Fc -t quality.team_attributes -t quality.team_reviews -t quality.overlay_versions > "$fichier" 2>/dev/null && [ -s "$fichier" ]; then
    chmod 600 "$fichier" 2>/dev/null || true
    echo "Sauvegarde créée : $fichier ($(wc -c < "$fichier" | tr -d ' ') octets)"; faits=$((faits + 1))
  else
    echo "Échec de pg_dump pour le dump partiel de quality"; rm -f "$fichier"; echecs=$((echecs + 1))
  fi
fi
if [ "$faits" -eq 0 ]; then
  rmdir "$CIBLE" 2>/dev/null && echo "Aucun fichier écrit : dossier $CIBLE retiré"
  echec 1 "Aucune sauvegarde faite, rotation non faite"
fi

# Rotation : on garde les $GARDER dossiers db-AAAA-MM-JJ les plus récents (par date dans le nom).
n=0
for dossier in $(ls -1 "$DEST" | grep -E '^db-[0-9]{4}-[0-9]{2}-[0-9]{2}$' | sort -r); do
  n=$((n + 1))
  [ "$n" -le "$GARDER" ] && continue
  echo "Supprimée : $DEST/$dossier ($(find "$DEST/$dossier" -type f | wc -l | tr -d ' ') fichiers)"
  rm -rf "${DEST:?}/$dossier"
done
echo "Sauvegardes présentes : $(ls -1 "$DEST" | grep -Ec '^db-[0-9]{4}-[0-9]{2}-[0-9]{2}$') (garde les $GARDER plus récentes)"
[ "$echecs" -eq 0 ] || echec 1 "$echecs schéma(s) non sauvegardé(s) : voir le journal"
