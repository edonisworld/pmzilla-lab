#!/bin/bash
# Radar, en lecture seule, des worktrees de branche de travail en retard sur main (seul mode : --check).
#
#     bash tools/branch_sync.sh --check     radar : pour chaque worktree de branche de travail, retard sur main et aperçu, sans rien changer
#     bash tools/branch_sync.sh --help      affiche ce texte
#
# Réduit à son mode radar par décision de l'auteur du 2026-10-28 (désherbage, entrée D99). Cette réduction remplace le mode par défaut, qui
# intégrait main dans la branche du worktree courant par une fusion (et son option --manuel), ainsi que la décision de l'auteur du 2026-10-20
# (change branch-sync) qui l'avait gardé : il contredit la règle d'intégration, main s'intègre dans une branche de travail par
# « git rebase main » dans son worktree. Condition de retrait : le retrait de la règle d'intégration par « git rebase main ». Lancé sans option, ou avec une autre option, l'outil refuse (code 2) et dit d'utiliser --check et, pour intégrer main,
# « git rebase main » dans le worktree.
#
# --check : lecture seule, partout dans le dépôt, même sous le verrou d'une autre fin (dit sur une ligne) ; ni fusion, ni fetch, ni référence,
# index ou fichier écrit (git merge-tree n'écrit que des objets). Référence de main : le plus avancé de main local et de origin/main
# (light_main_ref de tools/finish_env.sh, sans fetch) ; des références divergentes ne refusent pas, le retard n'est alors pas calculé.
# Pour chaque worktree de branche de travail (hors espace de travail, dossier d'exécution (PMZILLA_LAB_RUN, sinon « run » dans le dossier du
# lab), main et spike/*) : retard sur main et aperçu de la fusion de main (finish_merge_preview de tools/finish_merge.sh), avec les fichiers
# en conflit prévu. L'outil n'écrit rien : pousser, déplacer main ou origin/main, récupérer le distant, forcer, changer de branche, remettre à
# zéro, mettre de côté ou résoudre un conflit lui sont interdits.
# Codes : 0 radar écrit ; 2 usage ; 3 hors d'un dépôt ; 7 main introuvable ; 129, 130, 143 interruption.
set -u

NOM="branch_sync"
ICI=$(cd "$(dirname "$0")" && pwd)
. "$ICI/finish_merge.sh"    # aperçu de la fusion de main, le même que celui des scripts de fin
. "$ICI/finish_lock.sh"     # règle du verrou de fin (verrou lu seulement)
LIGHT_FINISH_DIR=$ICI
. "$ICI/finish_env.sh"      # light_main_ref : le plus avancé de main local et de origin/main (déplacée de light_finish.sh, retiré par B9)
TOP=""
MAIN_REF=""

dis() { printf '%s : %s\n' "$NOM" "$1"; }
refus() { # code phrase [lignes...] : sur la sortie d'erreur, puis sortie
  rc_refus=$1; shift
  printf '%s : %s\n' "$NOM" "$1" >&2; shift
  for ligne in "$@"; do [ -z "$ligne" ] || printf '%s\n' "$ligne" >&2; done
  exit "$rc_refus"
}

trap 'dis "interrompu (code 130)" >&2; exit 130' INT
trap 'dis "interrompu (code 143)" >&2; exit 143' TERM
trap 'dis "interrompu (code 129)" >&2; exit 129' HUP

aide() { awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "$0"; }
usage() {
  refus 2 "usage : bash tools/branch_sync.sh --check (radar en lecture seule ; --help affiche l'aide)" \
    "pour intégrer main dans une branche de travail : git rebase main, dans son worktree"
}

case $# in
  1) case "$1" in
       --check) ;;
       --help|-h) aide; exit 0 ;;
       *) usage ;;
     esac ;;
  *) usage ;;
esac

TOP=$(git rev-parse --show-toplevel 2>/dev/null) && [ -n "$TOP" ] || { TOP=""; refus 3 "hors d'un dépôt Git : rien n'est fait"; }
TOP=$(cd "$TOP" && pwd -P)
COMMUN=$(git -C "$TOP" rev-parse --path-format=absolute --git-common-dir)
WS=$(cd "$(dirname "$COMMUN")" && pwd -P)
RUN=${PMZILLA_LAB_RUN:-$(dirname "$WS")/run}
case "$RUN" in "~") RUN=$HOME ;; "~/"*) RUN="$HOME/${RUN#\~/}" ;; esac
RUN_P=$(cd "$RUN" 2>/dev/null && pwd -P) || RUN_P=""

verrou_bloquant() { # 0 si un verrou vivant d'un autre jeton est tenu (FL_BRANCH et FL_START posés)
  vb_dossier="$COMMUN/$FINISH_LOCK_NAME"
  [ -d "$vb_dossier" ] || return 1
  if _fl_stale "$vb_dossier"; then return 1; fi
  vb_jeton=$(cat "$vb_dossier/jeton" 2>/dev/null)
  if [ -n "${FINISH_LOCK_TOKEN:-}" ] && [ "$vb_jeton" = "$FINISH_LOCK_TOKEN" ]; then return 1; fi
  FL_BRANCH=$(cat "$vb_dossier/branche" 2>/dev/null); FL_START=$(cat "$vb_dossier/debut" 2>/dev/null)
  return 0
}

reference_main() { # pose MAIN_SHA, MAIN_NOM et MAIN_REF, ou refuse avec 7 ; des références divergentes ne refusent pas (MAIN_SHA vide)
  git -C "$TOP" rev-parse -q --verify "refs/heads/main^{commit}" >/dev/null 2>&1 || refus 7 "main introuvable : rien n'est fait"
  MAIN_SHA=$(light_main_ref "$TOP")
  if [ -z "$MAIN_SHA" ]; then
    MAIN_NOM=""; MAIN_REF=""; return 0
  fi
  if [ "$MAIN_SHA" = "$(git -C "$TOP" rev-parse "refs/heads/main^{commit}")" ]; then
    MAIN_NOM=main; MAIN_REF=refs/heads/main
  else
    MAIN_NOM=origin/main; MAIN_REF=refs/remotes/origin/main
  fi
}

chemin_reel() { (cd "$1" 2>/dev/null && pwd -P) || printf '%s\n' "$1"; }

radar() {
  reference_main
  if [ -n "$MAIN_SHA" ]; then
    dis "radar des worktrees, lecture seule (référence : $MAIN_NOM $(git -C "$TOP" rev-parse --short "$MAIN_SHA"))"
  else
    dis "radar des worktrees, lecture seule (références de main divergentes)"
  fi
  if verrou_bloquant; then
    dis "fin de branche en cours (${FL_BRANCH:-?}, depuis $(finish_lock_hhmm "$FL_START")) : aucune fusion possible avant sa fin"
  fi
  total=0; retard=0; conflits=0
  r_chemin=""; r_branche=""
  traite() {
    [ -n "$r_chemin" ] || return 0
    [ -n "$r_branche" ] || return 0
    case "$r_branche" in main|spike/*) return 0 ;; esac
    r_reel=$(chemin_reel "$r_chemin")
    [ "$r_reel" != "$WS" ] || return 0
    [ -z "$RUN_P" ] || [ "$r_reel" != "$RUN_P" ] || return 0
    total=$((total + 1))
    r_absent=""; [ -d "$r_chemin" ] || r_absent=" ; dossier absent"
    if [ -z "$MAIN_SHA" ]; then
      printf '%s (%s) : main local et origin/main ont divergé : retard non calculé%s\n' "$r_branche" "$r_chemin" "$r_absent"
      return 0
    fi
    r_n=$(git -C "$TOP" rev-list --count "refs/heads/$r_branche..$MAIN_SHA" 2>/dev/null) || r_n="?"
    if [ "$r_n" = "0" ]; then printf '%s (%s) : à jour%s\n' "$r_branche" "$r_chemin" "$r_absent"; return 0; fi
    retard=$((retard + 1))
    r_apercu=$(cd "$TOP" && finish_merge_preview "$MAIN_SHA" "refs/heads/$r_branche"); r_rc=$?
    case "$r_rc" in
      0) printf '%s (%s) : %s commit(s) de retard ; fusion de main prévue : sans conflit%s\n' "$r_branche" "$r_chemin" "$r_n" "$r_absent" ;;
      1) conflits=$((conflits + 1))
         r_noms=$(printf '%s\n' "$r_apercu" | sed 1d)
         printf '%s (%s) : %s commit(s) de retard ; fusion de main prévue : conflit sur %s fichier(s)%s\n' "$r_branche" "$r_chemin" "$r_n" \
           "$(printf '%s\n' "$r_noms" | grep -c .)" "$r_absent"
         printf '%s\n' "$r_noms" | sed 's/^/  /' ;;
      *) printf '%s (%s) : %s commit(s) de retard ; aperçu impossible%s\n' "$r_branche" "$r_chemin" "$r_n" "$r_absent" ;;
    esac
  }
  while IFS= read -r ligne; do
    case "$ligne" in
      "worktree "*) traite; r_chemin=${ligne#worktree }; r_branche="" ;;
      "branch refs/heads/"*) r_branche=${ligne#branch refs/heads/} ;;
    esac
  done < <(git -C "$TOP" worktree list --porcelain)
  traite
  if [ -z "$MAIN_SHA" ]; then
    dis "$total worktree(s) de branche de travail, références de main divergentes : retard non calculé"
  else
    dis "$total worktree(s) de branche de travail, $retard en retard sur main, $conflits avec conflit prévu"
  fi
  exit 0
}

radar
