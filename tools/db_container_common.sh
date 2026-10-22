#!/bin/bash
# PMZilla Lab : fonctions communes aux scripts qui démarrent un conteneur PostgreSQL jetable (tools/db_restore_test.sh et
# tools/db_rehearsal.sh) : l'image fixée et la mémoire partagée de docker-compose.yml. Se SOURCE ; lancé directement, il écrit les deux valeurs.
#
#     . "$RACINE/tools/db_container_common.sh"
#     IMAGE="$(db_compose_image "$RACINE/docker-compose.yml")"    image du service (vide si introuvable ; le script appelant la valide)
#     SHM="$(db_compose_shm "$RACINE/docker-compose.yml")"        shm_size du compose, « 1g » à défaut
#
# Lancé directement :
#
#     bash tools/db_container_common.sh    écrit l'image et le shm_size de docker-compose.yml, une ligne chacun (aucun Docker)
#
# Les fonctions ne lisent que le fichier donné : aucun Docker, aucune base, aucun Trousseau.
# Code de sortie : 0 valeurs écrites (lancé directement) ; le fichier sourcé ne change ni les options du shell appelant ni son dossier courant.

db_compose_image() {
  grep -E '^[[:space:]]+image:' "$1" | head -1 | sed -E 's/^[[:space:]]+image:[[:space:]]*//; s/["[:space:]]//g'
}

# /dev/shm du conteneur jetable : la valeur de shm_size de docker-compose.yml (64 Mo par défaut sinon, trop peu pour l'index BM25), repli 1g.
db_compose_shm() {
  local shm
  shm="$(grep -E '^[[:space:]]+shm_size:' "$1" | head -1 | sed -E 's/^[[:space:]]+shm_size:[[:space:]]*//; s/[#].*$//; s/["[:space:]]//g')"
  printf '%s' "$shm" | grep -Eiq '^[0-9]+[bkmg]b?$' || shm="1g"
  printf '%s' "$shm"
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  _dc_racine="$(cd "$(dirname "$0")/.." && pwd)"
  echo "image : $(db_compose_image "$_dc_racine/docker-compose.yml")"
  echo "shm_size : $(db_compose_shm "$_dc_racine/docker-compose.yml")"
fi
