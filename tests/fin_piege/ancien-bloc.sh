JOURNAL="$ETAPE_DIR/$ETAPE_NOM-$(date +%Y%m%d-%H%M%S).log"
ln -sfn "$(basename "$JOURNAL")" "$ETAPE_DIR/$ETAPE_NOM.log"
exec > >(tee -a "$JOURNAL") 2>&1
echo "$ETAPE_NOM.sh $ETAPE_VERSION, $(date +%H:%M)$([ "$A_BLANC" = "1" ] && echo ', ESSAI À BLANC')"

code=1; REFUS=0; SORTIE=""; VERROU_POSE=0
VERROU="$ETAPE_DIR/.fin-en-cours"
fin() {
  trap '' INT TERM HUP
  [ -n "$SORTIE" ] && rm -f "$SORTIE"
  [ "$VERROU_POSE" -eq 1 ] && rm -rf "$VERROU"
  case "$code" in 129|130|143) echo "interrompu : rien n'est fusionné par ce fichier (code $code) ; voir l'état avec git worktree list et git log -1 main" ;; esac
  controle_final
  if [ "$code" -eq 0 ] && [ "$FINAL_VERT" -ne 1 ]; then code=7; echo "succès de la fin, mais contrôle final non vert : code 7"; fi
  [ "$code" -eq 0 ] || echo "après un refus : aucune réparation dans la foulée ; main propre suffit"
  local etat=ÉCHEC; [ "$code" -eq 0 ] && etat=OK
  echo "code de sortie : $code" >> "$JOURNAL"
  echo
  echo "===== TERMINÉ : $ETAPE_NOM $ETAPE_VERSION ====="
  echo "code $code ($etat)"
  echo "Tu peux dire « fait » au chef d'orchestre."
  osascript -e "display notification \"$ETAPE_NOM : code $code ($etat)\" with title \"PMZilla étapes\" sound name \"Glass\"" >/dev/null 2>&1
  exit "$code"
}
trap fin EXIT
trap 'code=130; exit 130' INT
trap 'code=143; exit 143' TERM
trap 'code=129; exit 129' HUP
sortir() { code="$1"; exit "$1"; }
FINAL_VERT=0
