#!/bin/bash
# PMZilla Lab : démarre (ou arrête) la base de données PostgreSQL du conteneur, voir docs/pmzilla/application.md.
#
#     bash tools/db_up.sh          démarre la base (docker compose up -d --wait) et attend qu'elle soit saine
#     bash tools/db_up.sh down     arrête la base ; le volume pgdata est conservé (aucune donnée supprimée)
#
# Le mot de passe est lu dans le Trousseau macOS (service pmzilla-lab-db), passé à docker compose par l'environnement
# de cette seule commande, jamais affiché ni écrit. À défaut d'entrée du Trousseau, la variable PMZILLA_LAB_DB_PASSWORD
# (repli, hors Git) est utilisée si elle est définie.
# Ce script ne supprime jamais de données : ni `down -v`, ni `colima delete`.
# Codes de sortie : 0 base prête ; 1 Docker ou Colima absent ou muet, ou échec de docker compose ; 2 option inconnue ;
# 3 mot de passe introuvable (ni entrée du Trousseau ni variable de repli) : le script d'installation lit ce code, jamais le message.
set -euo pipefail

RACINE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RACINE"
SERVICE_TROUSSEAU="pmzilla-lab-db"
ACTION="${1:-up}"

case "$ACTION" in
  up|down) ;;
  *) echo "Usage : bash tools/db_up.sh [down]"; exit 2 ;;
esac

command -v docker >/dev/null 2>&1 || { echo "Docker est introuvable. Installer : brew install colima docker docker-compose"; exit 1; }
if command -v colima >/dev/null 2>&1; then
  colima status >/dev/null 2>&1 || { echo "Colima ne tourne pas. Le démarrer : colima start --cpu 4 --memory 6 (ou brew services start colima)"; exit 1; }
fi
docker info >/dev/null 2>&1 || { echo "Docker ne répond pas. Vérifier Colima : colima status (puis colima start --cpu 4 --memory 6)"; exit 1; }

if [ "$ACTION" = "down" ]; then
  # Le mot de passe n'est pas nécessaire pour arrêter (docker-compose.yml ne l'exige pas à l'interpolation).
  docker compose down
  echo "Base arrêtée. Le volume pgdata est conservé (relancer : bash tools/db_up.sh)."
  exit 0
fi

mdp=""
if command -v security >/dev/null 2>&1; then
  mdp="$(security find-generic-password -s "$SERVICE_TROUSSEAU" -w 2>/dev/null || true)"
fi
if [ -z "$mdp" ] && [ -n "${PMZILLA_LAB_DB_PASSWORD:-}" ]; then
  mdp="$PMZILLA_LAB_DB_PASSWORD"
fi
if [ -z "$mdp" ]; then
  cat <<MSG
Mot de passe de la base introuvable : aucune entrée « $SERVICE_TROUSSEAU » dans le Trousseau macOS.
Créer l'entrée une fois, dans un Terminal ordinaire (le mot de passe est saisi à l'invite, jamais en argument) :

    security add-generic-password -s $SERVICE_TROUSSEAU -a "\$USER" -w

Puis relancer : bash tools/db_up.sh
(Repli hors Trousseau : définir PMZILLA_LAB_DB_PASSWORD dans l'environnement, sans l'écrire dans un fichier suivi par Git.)
MSG
  exit 3
fi

# Le mot de passe n'existe dans l'environnement que pour cette commande.
POSTGRES_PASSWORD="$mdp" docker compose up -d --wait
mdp=""
echo "Base prête : 127.0.0.1:${PMZILLA_LAB_DB_PORT:-5432}, base pmzilla (docker compose ps pour l'état)."
