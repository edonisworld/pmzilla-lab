#!/bin/bash
# Gabarit de référence du piège de sortie des fichiers de fin (R-148/u14, #577). Les fichiers d'étape vivent hors Git (dossier etapes/ du lab) :
# la session recopie de ce gabarit le bloc entre « DEBUT DU BLOC » et « FIN DU BLOC » dans chaque fichier de fin, à la place des lignes
# « exec > >(tee …) », de fin() et des pièges ; le reste du fichier (contrôles, corps, controle_final réel) ne change pas.
# Test : tests/fin_piege/test_fin_piege.sh construit un fichier factice depuis ce gabarit et l'interrompt (INT, TERM, HUP, tee tué).
#
# Pourquoi : en bash non interactif, le tee d'une substitution de processus ignore SIGINT (comme toute commande en arrière-plan) ; il meurt
# par TERM ou HUP (terminal fermé), et le premier echo de fin() reçoit alors SIGPIPE : le bandeau n'arrive jamais au journal. Remède : le tee
# est lancé par un FIFO (PID attendable) en ignorant INT, TERM et HUP, donc il garde au journal les dernières lignes du corps ; fin() rend
# l'écran d'origine (descripteurs 3 et 4), attend (au plus 2 s) la fin du tee, puis écrit au journal directement (>> "$JOURNAL"), jamais à
# travers le tee, et tente l'écran en plus, sans double écriture. Un tee tué à part donne SIGPIPE : piège PIPE, code 141.
# Descripteurs : le corps garde les descripteurs 3 et 4 (sortie d'origine) ; les commandes qu'il lance, surtout les longues, reçoivent
# « 3>&- 4>&- » (exemple : bash tools/finish_train.sh "$BRANCHE" 3>&- 4>&-), pour ne pas tenir l'écran d'origine après la fin.
set -u
ETAPE_NOM="modele-piege-fin"; ETAPE_VERSION="v1"
ETAPE_DIR="${ETAPE_DIR:?dossier etapes du lab, posé par le vrai fichier de fin}"   # hors du bloc : chaque fichier de fin garde sa propre ligne
A_BLANC="${ETAPE_A_BLANC:-0}"

# ===== DEBUT DU BLOC ===== (marqueur : BLOC-PIEGE-FIN v2)
JOURNAL="$ETAPE_DIR/$ETAPE_NOM-$(date +%Y%m%d-%H%M%S).log"
ln -sfn "$(basename "$JOURNAL")" "$ETAPE_DIR/$ETAPE_NOM.log"
TEE_PID=""
FIFO=$(mktemp -u "${TMPDIR:-/tmp}/fin-tee.XXXXXX")
if [ -n "$FIFO" ] && mkfifo "$FIFO" 2>/dev/null; then
  ( trap '' INT TERM HUP; exec tee -a "$JOURNAL" ) < "$FIFO" &
  TEE_PID=$!
  exec 3>&1 4>&2 >"$FIFO" 2>&1   # 3 et 4 : sortie d'origine (écran), gardée pour le piège de sortie
  rm -f "$FIFO"
else
  exec 3>&1 4>&2 >>"$JOURNAL" 2>&1   # repli sans tee : tout au journal seulement
fi
echo "$ETAPE_NOM.sh $ETAPE_VERSION, $(date +%H:%M)$([ "$A_BLANC" = "1" ] && echo ', ESSAI À BLANC')"

code=1; REFUS=0; SORTIE=""; VERROU_POSE=0
VERROU="$ETAPE_DIR/.fin-en-cours"
FINAL_VERT=0
ecrire() {   # une ligne au journal, directement (jamais à travers le tee), puis à l'écran d'origine si elle est encore là
  printf '%s\n' "$*" >> "$JOURNAL"
  { printf '%s\n' "$*" >&3; } 2>/dev/null
  return 0
}
fin() {
  trap '' INT TERM HUP PIPE
  exec 1>&3 2>&4   # le tee ne reçoit plus rien et finit seul (il ignore INT, TERM et HUP, donc il vide ses dernières lignes)
  if [ -n "$TEE_PID" ]; then
    local i=0
    while kill -0 "$TEE_PID" 2>/dev/null && [ "$i" -lt 20 ]; do sleep 0.1; i=$((i+1)); done
  fi
  [ -n "$SORTIE" ] && rm -f "$SORTIE"
  [ "$VERROU_POSE" -eq 1 ] && rm -rf "$VERROU"
  case "$code" in 129|130|141|143) ecrire "interrompu : rien n'est fusionné par ce fichier (code $code) ; voir l'état avec git worktree list et git log -1 main" ;; esac
  local cf; cf=$(mktemp "${TMPDIR:-/tmp}/fin-controle.XXXXXX") || cf=""
  if [ -n "$cf" ]; then
    controle_final > "$cf" 2>&1
    while IFS= read -r ligne || [ -n "$ligne" ]; do ecrire "$ligne"; done < "$cf"; rm -f "$cf"
  else
    controle_final >> "$JOURNAL" 2>&1
  fi
  if [ "$code" -eq 0 ] && [ "$FINAL_VERT" -ne 1 ]; then code=7; ecrire "succès de la fin, mais contrôle final non vert : code 7"; fi
  [ "$code" -eq 0 ] || ecrire "après un refus : aucune réparation dans la foulée ; main propre suffit"
  local etat=ÉCHEC; [ "$code" -eq 0 ] && etat=OK
  printf '%s\n' "code de sortie : $code" >> "$JOURNAL"   # au journal seulement
  ecrire ""
  ecrire "===== TERMINÉ : $ETAPE_NOM $ETAPE_VERSION ====="
  ecrire "code $code ($etat)"
  ecrire "Tu peux dire « fait » au chef d'orchestre."
  osascript -e "display notification \"$ETAPE_NOM : code $code ($etat)\" with title \"PMZilla étapes\" sound name \"Glass\"" >/dev/null 2>&1
  exit "$code"
}
trap fin EXIT
trap 'code=130; exit 130' INT
trap 'code=143; exit 143' TERM
trap 'code=129; exit 129' HUP
trap 'code=141; exit 141' PIPE
sortir() { code="$1"; exit "$1"; }
# ===== FIN DU BLOC =====

controle_final() {   # gabarit : les vrais fichiers portent ici leur contrôle final (main propre, état du matin) et posent FINAL_VERT=1 s'il est vert
  echo "--- contrôle final (gabarit)"
  FINAL_VERT=1
}

# ===== CORPS DU FICHIER =====
sortir 0
