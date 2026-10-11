#!/bin/bash
# PMZilla Lab : sauvegarde du sanctum des postures (_bmad/memory/), qui n'est plus dans Git.
#
#     bash tools/sauvegarde_sanctum.sh
#
# Copie _bmad/memory/ dans ~/.pmzilla-lab/sauvegardes/bmad-memory-AAAA-MM-JJ (dossier daté). Jamais d'écrasement : si le
# dossier du jour existe, le script s'arrête avec un message. Garde ensuite les 6 sauvegardes les plus récentes et supprime
# les plus anciennes en affichant ce qu'il supprime ; la sauvegarde du 2026-10-07 n'est jamais supprimée.
# Il n'affiche que des chemins et des nombres de fichiers, jamais le contenu du sanctum.
#
# Variables (pour les tests) : SANCTUM_SOURCE (défaut : _bmad/memory du dépôt), SANCTUM_SAUVEGARDES (défaut :
# ~/.pmzilla-lab/sauvegardes), SANCTUM_DATE (défaut : date du jour, AAAA-MM-JJ ; AAAA-MM-JJ-étiquette en minuscules et chiffres pour une deuxième sauvegarde le même jour, jamais supprimée par la rotation), SANCTUM_GARDER (défaut : 6).
set -u
RACINE="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="${SANCTUM_SOURCE:-$RACINE/_bmad/memory}"
DEST="${SANCTUM_SAUVEGARDES:-$HOME/.pmzilla-lab/sauvegardes}"
DATE="${SANCTUM_DATE:-$(date +%Y-%m-%d)}"
GARDER="${SANCTUM_GARDER:-6}"
PROTEGEE="bmad-memory-2026-10-07"

compter() { find "$1" -type f | wc -l | tr -d ' '; }

if ! printf '%s' "$DATE" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}(-[a-z0-9]+)?$'; then
  echo "Date invalide : $DATE (attendu AAAA-MM-JJ, ou AAAA-MM-JJ-étiquette pour une deuxième sauvegarde le même jour)"; exit 2
fi
if [ ! -d "$SOURCE" ] || [ "$(compter "$SOURCE")" -eq 0 ]; then
  echo "Sanctum introuvable ou vide : $SOURCE"; exit 2
fi
CIBLE="$DEST/bmad-memory-$DATE"
if [ -e "$CIBLE" ]; then
  echo "La sauvegarde du jour existe déjà : $CIBLE (rien n'a été copié ni supprimé)"; exit 1
fi

mkdir -p "$DEST" || { echo "Impossible de créer $DEST"; exit 2; }
cp -R "$SOURCE" "$CIBLE" || { echo "Copie échouée vers $CIBLE"; rm -rf "$CIBLE"; exit 2; }
ATTENDUS=$(compter "$SOURCE"); COPIES=$(compter "$CIBLE")
if [ "$ATTENDUS" -ne "$COPIES" ]; then
  echo "Copie incomplète : $COPIES fichiers sur $ATTENDUS dans $CIBLE (aucune rotation faite)"; exit 2
fi
echo "Sauvegarde créée : $CIBLE ($COPIES fichiers)"

# Rotation : on garde les $GARDER plus récentes (par date dans le nom) ; la sauvegarde protégée n'est jamais supprimée.
n=0
for dossier in $(ls -1 "$DEST" | grep -E '^bmad-memory-[0-9]{4}-[0-9]{2}-[0-9]{2}$' | sort -r); do
  n=$((n + 1))
  [ "$n" -le "$GARDER" ] && continue
  if [ "$dossier" = "$PROTEGEE" ]; then
    echo "Conservée (protégée) : $DEST/$dossier ($(compter "$DEST/$dossier") fichiers)"; continue
  fi
  echo "Supprimée : $DEST/$dossier ($(compter "$DEST/$dossier") fichiers)"
  rm -rf "${DEST:?}/$dossier"
done
echo "Sauvegardes présentes : $(ls -1 "$DEST" | grep -Ec '^bmad-memory-[0-9]{4}-[0-9]{2}-[0-9]{2}$')"
