#!/bin/zsh
# PMZilla Lab : une seule source de vérité pour les scripts.
# Les scripts lancés par launchd (watch.sh), par le serveur MCP (pmzilla_lab_library.py) et par l'essai des postures
# sont appelés par leur chemin ~/PMZilla-Lab/<script>. Ce chemin devient un lien symbolique vers
# ~/PMZilla-Lab/run/tools/<script> (le dossier d'exécution, change run-worktree) : tools/ (suivi par Git) fait foi, il n'y a plus jamais de copie à refaire.
#
#   zsh tools/install_links.sh                        crée les liens vers le dossier d'exécution (sauvegarde d'abord les copies qui existent)
#   zsh tools/install_links.sh --verify               dit l'état de chaque lien, sans rien changer
#   zsh tools/install_links.sh --target workspace     retour en arrière : les liens visent tools/ du dépôt de développement
#   zsh tools/install_links.sh --verify --target workspace
#
# Sans dossier d'exécution (et sans --target workspace), le script refuse et ne crée ni ne change aucun lien : le créer d'abord avec
# bash tools/run_worktree.sh create. Un lien qui vise l'autre dossier est refait (« mauvais dossier » en mode --verify, code non nul).
# Variable : PMZILLA_LAB_RUN, emplacement du dossier d'exécution (défaut ~/PMZilla-Lab/run).
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
RUN="${PMZILLA_LAB_RUN:-$LAB/run}"
# Les scripts que lance un modèle launchd (watch.sh, db_backup.sh, offsite_backup.sh, doctor.sh) y figurent : un modèle ne nomme jamais un dossier de code.
SCRIPTS=(convert_books.py posture_evals.py flux_jira.py history_common.py
         mapping_lab.py pmzilla_lab_library.py watch_triage.py watch_lab.py sort_by_domain.py morning_summary.py watch.sh
         db_backup.sh offsite_backup.sh doctor.sh)
RELIQUATS=(pmzilla_lab_library.py.avant-veille)     # anciennes sauvegardes à ranger avec les copies
VERIFIER=0
CIBLE_ARBRE=run
while (( $# )); do
  case "$1" in
    --verify) VERIFIER=1 ;;
    --verifier) echo "Option « --verifier » refusée : elle s'appelle « --verify »." >&2; exit 2 ;;
    --target)
      case "${2:-}" in
        workspace|run) CIBLE_ARBRE="$2"; shift ;;
        *) echo "Option « --target » : valeur attendue « workspace » (retour en arrière) ou « run »." >&2; exit 2 ;;
      esac ;;
    *) echo "Option inconnue : $1 (options : --verify, --target workspace)." >&2; exit 2 ;;
  esac
  shift
done

# Dossier de code visé : le dossier d'exécution (défaut) ou le dépôt de développement (retour en arrière). Le lien est relatif au dossier du labo
# quand le dossier visé est dans le dossier du labo (cas normal), absolu sinon.
DEV_TOOLS="$LAB/workspace/tools"
RUN_TOOLS="$RUN/tools"
relatif() { [[ "$1" == "$LAB/"* ]] && print -r -- "${1#$LAB/}" || print -r -- "$1"; }
if [[ "$CIBLE_ARBRE" == workspace ]]; then
  TOOLS="$DEV_TOOLS"; AUTRE_TOOLS="$RUN_TOOLS"
else
  TOOLS="$RUN_TOOLS"; AUTRE_TOOLS="$DEV_TOOLS"
  [[ -d "$RUN" ]] || { echo "Dossier d'exécution introuvable : $RUN. Le créer d'abord : bash tools/run_worktree.sh create (aucun lien créé ni changé)." >&2; exit 1; }
fi

[[ -d "$TOOLS" ]] || { echo "Dossier introuvable : $TOOLS (le dépôt doit être cloné dans ~/PMZilla-Lab/workspace, le dossier d'exécution créé par bash tools/run_worktree.sh create)." >&2; exit 1; }
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
  cible="$(relatif "$TOOLS")/$f"
  if [[ -L "$lien" ]]; then
    if [[ "$(readlink "$lien")" == "$cible" && -e "$lien" ]]; then
      echo "ok         $f (lien déjà en place)"
      continue
    fi
    if [[ "$(readlink "$lien")" == "$(relatif "$AUTRE_TOOLS")/$f" || "$(readlink "$lien")" == "$AUTRE_TOOLS/$f" ]]; then
      echo "mauvais dossier  $f (lien vers l'autre dossier de code : $(readlink "$lien") ; attendu : $cible)"
    else
      echo "à refaire  $f (lien vers $(readlink "$lien"))"
    fi
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
