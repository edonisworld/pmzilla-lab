#!/bin/bash
# PMZilla Lab : la passe de bout en bout de Mothra (mothra-slices, design D12, tâche 8.2). Playwright pour Node, sur le jeu synthétique de la
# base jetable seulement, hors du lanceur complet (tests/run_all.sh ne la connaît pas).
#
#     bash tests/run_e2e.sh      (lancée par bash tools/dbtest.sh --e2e, qui pose DBTEST_PORT et MOTHRA_E2E_URL ; jamais seule en usage normal)
#
# Ce que fait le script :
#   1. refuse sans base jetable : sans DBTEST_PORT (ou avec un port illisible, 5432 ou celui de la vraie base), code 2 et la phrase
#      « run_e2e : base jetable absente (lancer bash tools/dbtest.sh --e2e) » ; aucun navigateur n'est lancé ;
#   2. refuse sans adresse du serveur Mothra (MOTHRA_E2E_URL, posée par tools/dbtest.sh --e2e) ou avec une adresse qui n'est pas
#      http://127.0.0.1:<port> (code 2) : la passe ouvre la page à l'adresse du serveur Mothra, qui sert le bundle construit et l'API
#      (D7) ; jamais le serveur de développement de Vite (port 5173) ni son aperçu (vite preview, port 4173), jamais une autre machine ;
#   3. lance Playwright (mothra/node_modules, installé par npm ci) avec la configuration de tests/e2e/ ; aucun navigateur n'est téléchargé
#      (les navigateurs sont installés une fois par l'auteur) ; aucun mot de passe de base ni variable PMZILLA_LAB_DB_* n'est transmis.
#
# Code de sortie : 0 la passe est verte ; 1 elle est rouge (ou Playwright est introuvable) ; 2 refus (rien n'a été lancé).
# Variable pour les tests : RUN_E2E_LANCEUR (programme qui remplace Playwright ; il reçoit MOTHRA_E2E_URL et DBTEST_PORT).
set -uo pipefail
RACINE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RACINE" || exit 2

port_valide() { local LC_ALL=C; [[ "$1" =~ ^[1-9][0-9]{0,4}$ ]] && [ "$((10#$1))" -le 65535 ]; }
PORT_JETABLE="${DBTEST_PORT:-}"
PORT_REEL="${PMZILLA_LAB_DB_PORT:-5432}"
if [ -z "$PORT_JETABLE" ] || ! port_valide "$PORT_JETABLE" || [ "$((10#$PORT_JETABLE))" -eq 5432 ] \
   || { port_valide "$PORT_REEL" && [ "$((10#$PORT_JETABLE))" -eq "$((10#$PORT_REEL))" ]; }; then
  echo "run_e2e : base jetable absente (lancer bash tools/dbtest.sh --e2e)"
  exit 2
fi

URL="${MOTHRA_E2E_URL:-}"
if ! [[ "$URL" =~ ^http://127\.0\.0\.1:([1-9][0-9]{0,4})$ ]] || [ "$((10#${BASH_REMATCH[1]}))" -gt 65535 ] \
   || [ "$((10#${BASH_REMATCH[1]}))" -eq 5173 ] || [ "$((10#${BASH_REMATCH[1]}))" -eq 4173 ]; then
  echo "run_e2e : adresse du serveur Mothra absente ou refusée (http://127.0.0.1:<port> seulement, jamais Vite ni son aperçu ; lancer bash tools/dbtest.sh --e2e)"
  exit 2
fi

# La passe ne transmet rien de la base : retrait de toute variable PMZILLA_LAB_DB_*.
RETRAIT=()
while IFS= read -r variable; do
  [ -n "$variable" ] && RETRAIT+=(-u "$variable")
done < <(compgen -e PMZILLA_LAB_DB_)

if [ -n "${RUN_E2E_LANCEUR:-}" ]; then
  env ${RETRAIT[@]+"${RETRAIT[@]}"} MOTHRA_E2E_URL="$URL" DBTEST_PORT="$PORT_JETABLE" "$RUN_E2E_LANCEUR"
  code=$?
else
  CLI="mothra/node_modules/@playwright/test/cli.js"
  [ -f "$CLI" ] || { echo "run_e2e : Playwright introuvable (les dépendances de mothra/ sont à installer par l'auteur)"; exit 1; }
  env ${RETRAIT[@]+"${RETRAIT[@]}"} MOTHRA_E2E_URL="$URL" DBTEST_PORT="$PORT_JETABLE" PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    node "$CLI" test --config tests/e2e/playwright.config.ts
  code=$?
fi
[ "$code" -eq 0 ] && exit 0
echo "run_e2e : passe rouge (code $code)"
exit 1
