#!/bin/zsh
# PMZilla Lab : une seule source de vérité pour les scripts.
# Les scripts lancés par launchd (watch.sh), par le serveur MCP (pmzilla_lab_library.py) et par l'essai des postures
# sont appelés par leur chemin ~/PMZilla-Lab/<script>. Ce chemin devient un lien symbolique vers
# ~/PMZilla-Lab/workspace/tools/<script> : tools/ (suivi par Git) fait foi, il n'y a plus jamais de copie à refaire.
#
#   zsh tools/install_links.sh              crée les liens (sauvegarde d'abord les copies qui existent)
#   zsh tools/install_links.sh --verify     dit l'état de chaque lien, sans rien changer
#
# Chaque copie remplacée est déplacée dans ~/PMZilla-Lab/copies-avant-liens-AAAA-MM-JJ-HHMMSS/, jamais supprimée.
# Relançable sans risque : un lien déjà correct n'est pas touché.
# Ce script utilise zsh. Lancé par bash ou sh (« bash tools/install_links.sh »), il ne parcourait que le premier
# script du tableau et annonçait « Tous les liens sont en place » : on repasse donc par zsh, ou on s'arrête.
if [ -z "${ZSH_VERSION:-}" ]; then
  command -v zsh >/dev/null 2>&1 && exec zsh "$0" "$@"
  echo "Ce script demande zsh (introuvable) : installez zsh, puis lancez zsh tools/install_links.sh" >&2; exit 2
fi
set -u

LAB="$HOME/PMZilla-Lab"
TOOLS="$LAB/workspace/tools"
SCRIPTS=(convert_books.py posture_evals.py flux_jira.py history_common.py
         mapping_lab.py pmzilla_lab_library.py watch_triage.py watch_lab.py sort_by_domain.py watch.sh)
RELIQUATS=(pmzilla_lab_library.py.avant-veille)     # anciennes sauvegardes à ranger avec les copies
VERIFIER=0
case "${1:-}" in
  --verify) VERIFIER=1 ;;
  --verifier) echo "Option « --verifier » refusée : elle s'appelle « --verify »." >&2; exit 2 ;;
esac

[[ -d "$TOOLS" ]] || { echo "Dossier introuvable : $TOOLS (le dépôt doit être cloné dans ~/PMZilla-Lab/workspace)." >&2; exit 1; }
manquants=()
for f in "${SCRIPTS[@]}"; do [[ -f "$TOOLS/$f" ]] || manquants+=("$f"); done
(( ${#manquants} )) && { echo "Absents de $TOOLS : ${manquants[*]}" >&2; exit 1; }

SAUVEGARDE="$LAB/copies-avant-liens-$(date +%Y-%m-%d-%H%M%S)"
rangees=0
ranger() {                       # déplace un fichier dans la sauvegarde (créée à la première fois)
  (( VERIFIER )) && return
  mkdir -p "$SAUVEGARDE" && mv "$1" "$SAUVEGARDE/" && rangees=$((rangees + 1))
}

erreurs=0
for f in "${SCRIPTS[@]}"; do
  lien="$LAB/$f"
  cible="workspace/tools/$f"
  if [[ -L "$lien" ]]; then
    if [[ "$(readlink "$lien")" == "$cible" && -e "$lien" ]]; then
      echo "ok         $f (lien déjà en place)"
      continue
    fi
    echo "à refaire  $f (lien vers $(readlink "$lien"))"
    (( VERIFIER )) || rm "$lien"
  elif [[ -e "$lien" ]]; then
    if cmp -s "$lien" "$TOOLS/$f"; then etat="copie identique à tools/"; else etat="COPIE DIFFÉRENTE de tools/ (tools/ fait foi ; la copie est gardée dans la sauvegarde)"; fi
    echo "copie      $f : $etat"
    ranger "$lien"
  else
    echo "absent     $f"
  fi
  if (( VERIFIER )); then erreurs=$((erreurs + 1)); continue; fi
  ln -s "$cible" "$lien" || { echo "échec     $f" >&2; erreurs=$((erreurs + 1)); continue; }
  echo "lien créé  $f -> $cible"
done

for f in "${RELIQUATS[@]}"; do
  if [[ -e "$LAB/$f" && ! -L "$LAB/$f" ]]; then
    (( VERIFIER )) && echo "reliquat   $f (sera rangé avec les copies)" || echo "reliquat   $f rangé avec les copies"
    ranger "$LAB/$f"
  fi
done

if (( VERIFIER )); then
  (( erreurs )) && { echo "$erreurs lien(s) à créer : lance zsh tools/install_links.sh"; exit 1; }
  echo "Tous les liens sont en place."; exit 0
fi
(( rangees )) && echo "Copies sauvegardées dans : $SAUVEGARDE"
(( erreurs )) && exit 1
echo "Terminé. Vérifie : zsh tools/install_links.sh --verify, puis claude mcp get pmzilla-library (Status: ✔ Connected)."
