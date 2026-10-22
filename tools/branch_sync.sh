#!/bin/bash
# Fusionne main dans la branche de travail du worktree courant, à la demande d'une session (change branch-sync, décision de l'auteur du
# 2026-10-20) ; son mode --check est le radar, en lecture seule, des worktrees de branche de travail en retard sur main.
#
#     bash tools/branch_sync.sh             fusionne main dans la branche du worktree courant (aperçu d'abord, arrêt au premier conflit)
#     bash tools/branch_sync.sh --manuel    idem, et accepte un conflit sur le seul manuel généré, régénéré par tools/manual.py
#     bash tools/branch_sync.sh --check     radar : pour chaque worktree de branche de travail, retard sur main et aperçu, sans rien changer
#     bash tools/branch_sync.sh --help      affiche ce texte
#
# Lancé dans le worktree d'une branche de travail, jamais dans l'espace de travail, le dossier d'exécution (PMZILLA_LAB_RUN, sinon « run »
# dans le dossier du lab), sur une HEAD détachée, sur main ou sur spike/*. Aucun argument de branche : la seule branche touchée est celle du
# worktree courant. Ordre : usage, dépôt, verrou d'une autre fin (avant tout le reste ; règle de tools/finish_lock.sh, verrou jamais créé,
# retiré ni modifié), lieu, worktree propre (fichiers suivis ; un fichier non suivi ne compte pas), aucune fusion ni autre opération Git en
# cours, référence de main (le plus avancé de main local et de origin/main, light_main_ref de tools/light_finish.sh, sans fetch), main déjà
# contenue (rien n'est fait), aperçu par finish_merge_preview de tools/finish_merge.sh (conflit prévu : rien n'est commencé), puis
# « git merge --no-edit » (entrée vide, crochets actifs), enfin la vérification. Un échec de la fusion (conflit non prévu, crochet qui refuse)
# l'annule par « git merge --abort ». L'outil ne résout JAMAIS rien : la résolution se prépare par Edit dans la branche, se commite, puis
# l'outil est relancé. --manuel : seulement quand le conflit prévu porte sur docs/pmzilla/manuel.md seul ; la fusion s'arrête sur ce fichier,
# la commande de génération le refait dans le worktree, puis la fusion est commitée (crochets actifs) ; tout échec annule la fusion.
# --check : lecture seule, partout dans le dépôt, même sous le verrou d'une autre fin (dit sur une ligne) ; ni fusion, ni fetch, ni référence,
# index ou fichier écrit (git merge-tree n'écrit que des objets).
# Interdit à l'outil : pousser, déplacer main ou origin/main, récupérer le distant, forcer, contourner un crochet, changer de branche,
# remettre à zéro, mettre de côté, résoudre un conflit.
# Codes : 0 main fusionnée, déjà contenue, ou radar écrit ; 2 usage ; 3 hors d'un dépôt, ou lieu refusé (espace de travail, dossier
#   d'exécution, HEAD détachée, main, spike/*) ; 4 une autre fin de branche tient le verrou ; 5 worktree pas propre ; 6 fusion, rebase,
#   cherry-pick ou revert en cours ; 7 main introuvable, ou main local et origin/main divergents ; 8 conflit prévu ou aperçu impossible
#   (rien n'est commencé) ; 9 fusion en échec, annulée ; 10 --manuel : régénération, runner ou commit en échec, fusion annulée ; 11
#   vérification d'après en échec, annulation impossible, ou interruption pendant l'écriture de la fusion avant MERGE_HEAD (rien n'est remis
#   à zéro, la phrase donne le sommet d'avant) ; 129, 130, 143 interruption (une fusion lancée par l'outil et non terminée est annulée).
# --manuel : après la régénération du manuel, l'outil lance « bash tests/run_all.sh --staged » avant le commit (comme fusion-main.sh) ; rouge :
#   fusion annulée, code 10.
# Variables (pour les tests), chacune n'est acceptée que si elle désigne un fichier exécutable (sinon code 2), lancé sans eval, dans le
# worktree, entrée vide : BRANCH_SYNC_MANUAL remplace « uv run tools/manual.py --write » ; BRANCH_SYNC_RUNNER remplace
# « bash tests/run_all.sh --staged ».
set -u

NOM="branch_sync"
ICI=$(cd "$(dirname "$0")" && pwd)
. "$ICI/finish_merge.sh"    # aperçu de la fusion de main, le même que celui des scripts de fin
. "$ICI/finish_lock.sh"     # règle du verrou de fin (verrou lu seulement)
LIGHT_FINISH_DIR=$ICI
. "$ICI/light_finish.sh"    # light_main_ref : le plus avancé de main local et de origin/main
MANUEL_FICHIER="docs/pmzilla/manuel.md"
MANUEL_EXE=""; RUNNER_EXE=""
FUSION_LANCEE=0
TOP=""
AVANT=""
MAIN_REF=""

dis() { printf '%s : %s\n' "$NOM" "$1"; }
refus() { # code phrase [lignes...] : sur la sortie d'erreur, puis sortie
  rc_refus=$1; shift
  printf '%s : %s\n' "$NOM" "$1" >&2; shift
  for ligne in "$@"; do [ -z "$ligne" ] || printf '%s\n' "$ligne" >&2; done
  exit "$rc_refus"
}
chemin_git() { git -C "$TOP" rev-parse --path-format=absolute --git-path "$1" 2>/dev/null; }
fusion_en_cours() { [ -n "$TOP" ] && [ -e "$(chemin_git MERGE_HEAD)" ]; }

etat_incertain() { # 0 si la fusion lancée n'a ni MERGE_HEAD ni commit mais a touché l'index ou les fichiers suivis
  [ -n "$AVANT" ] && [ "$(git -C "$TOP" rev-parse HEAD 2>/dev/null)" = "$AVANT" ] \
    && [ -n "$(git -C "$TOP" status --porcelain --untracked-files=no 2>/dev/null)" ]
}
dit_incertain() {
  printf '%s : %s\n' "$NOM" "fusion interrompue ou en échec avant l'écriture de MERGE_HEAD : le worktree est modifié, état incertain ; sommet avant la fusion : $AVANT ; rien n'est remis à zéro" >&2
}

fin() {
  rc=$?
  trap '' INT TERM HUP
  if [ "$FUSION_LANCEE" -eq 1 ]; then
    if fusion_en_cours; then
      if git -C "$TOP" merge --abort >/dev/null 2>&1; then
        dis "fusion commencée par l'outil : annulée" >&2
      else
        printf '%s : %s\n' "$NOM" "annulation impossible : une fusion reste en cours dans le worktree" >&2; rc=11
      fi
    elif etat_incertain; then
      dit_incertain; rc=11
    fi
  fi
  exit "$rc"
}
trap fin EXIT
trap 'dis "interrompu (code 130)" >&2; exit 130' INT
trap 'dis "interrompu (code 143)" >&2; exit 143' TERM
trap 'dis "interrompu (code 129)" >&2; exit 129' HUP

aide() { awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "$0"; }
usage() { refus 2 "usage : bash tools/branch_sync.sh [--manuel | --check | --help]"; }

MODE=fusion
case $# in
  0) ;;
  1) case "$1" in
       --manuel) MODE=manuel ;;
       --check) MODE=check ;;
       --help|-h) aide; exit 0 ;;
       *) usage ;;
     esac ;;
  *) usage ;;
esac

exe_variable() { # nom valeur : écrit le chemin absolu de l'exécutable, ou refuse avec 2 (jamais d'eval)
  if [ -f "$2" ] && [ -x "$2" ]; then
    printf '%s/%s\n' "$(cd "$(dirname "$2")" && pwd -P)" "$(basename "$2")"
  else
    refus 2 "$1 doit désigner un fichier exécutable : rien n'est fait"
  fi
}
if [ -n "${BRANCH_SYNC_MANUAL:-}" ]; then MANUEL_EXE=$(exe_variable BRANCH_SYNC_MANUAL "$BRANCH_SYNC_MANUAL") || exit $?; fi
if [ -n "${BRANCH_SYNC_RUNNER:-}" ]; then RUNNER_EXE=$(exe_variable BRANCH_SYNC_RUNNER "$BRANCH_SYNC_RUNNER") || exit $?; fi
generer_manuel() { if [ -n "$MANUEL_EXE" ]; then "$MANUEL_EXE"; else uv run tools/manual.py --write; fi; }
lancer_runner() { if [ -n "$RUNNER_EXE" ]; then "$RUNNER_EXE"; else bash tests/run_all.sh --staged; fi; }

TOP=$(git rev-parse --show-toplevel 2>/dev/null) && [ -n "$TOP" ] || { TOP=""; refus 3 "hors d'un dépôt Git : rien n'est fait"; }
TOP=$(cd "$TOP" && pwd -P)
COMMUN=$(git -C "$TOP" rev-parse --path-format=absolute --git-common-dir)
GITDIR=$(git -C "$TOP" rev-parse --path-format=absolute --git-dir)
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

reference_main() { # [radar] : pose MAIN_SHA, MAIN_NOM et MAIN_REF, ou refuse avec 7 ; en radar, des références divergentes ne refusent pas (MAIN_SHA vide)
  git -C "$TOP" rev-parse -q --verify "refs/heads/main^{commit}" >/dev/null 2>&1 || refus 7 "main introuvable : rien n'est fait"
  MAIN_SHA=$(light_main_ref "$TOP")
  if [ -z "$MAIN_SHA" ]; then
    [ "${1:-}" = radar ] || refus 7 "main local et origin/main ont divergé : rien n'est fait"
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
  reference_main radar
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

[ "$MODE" != check ] || radar

# --- contrôles, dans l'ordre ; aucun ne change rien
if verrou_bloquant; then
  refus 4 "fin de branche en cours (${FL_BRANCH:-?}, depuis $(finish_lock_hhmm "$FL_START")) : rien n'est fait"
fi
[ "$GITDIR" != "$COMMUN" ] || refus 3 "refusé : l'espace de travail n'est pas une branche de travail"
[ -z "$RUN_P" ] || [ "$TOP" != "$RUN_P" ] || refus 3 "refusé : le dossier d'exécution n'est pas une branche de travail"
BRANCHE=$(git -C "$TOP" symbolic-ref --short -q HEAD) || refus 3 "refusé : HEAD détachée, aucune branche de travail"
case "$BRANCHE" in main|spike/*) refus 3 "refusé : $BRANCHE n'est pas une branche de travail" ;; esac
sale=$(git -C "$TOP" status --porcelain --untracked-files=no)
[ -z "$sale" ] || refus 5 "worktree pas propre : rien n'est fait" "$(git -C "$TOP" status --short --untracked-files=no)"
! fusion_en_cours || refus 6 "une fusion est déjà en cours dans le worktree : rien n'est fait"
for operation in CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply; do
  [ ! -e "$(chemin_git "$operation")" ] || refus 6 "une opération Git (rebase, cherry-pick ou revert) est en cours dans le worktree : rien n'est fait"
done
reference_main
if git -C "$TOP" merge-base --is-ancestor "$MAIN_SHA" HEAD; then dis "déjà à jour : main est contenue dans $BRANCHE"; exit 0; fi
dis "$(git -C "$TOP" rev-list --count "HEAD..$MAIN_SHA") commit(s) de $MAIN_NOM à fusionner dans $BRANCHE ($MAIN_NOM : $(git -C "$TOP" rev-parse --short "$MAIN_SHA"))"

# --- aperçu (lecture seule)
MANUEL=0
apercu=$(cd "$TOP" && finish_merge_preview "$MAIN_SHA" HEAD); rc_apercu=$?
case "$rc_apercu" in
  0) dis "fusion de main prévue : sans conflit" ;;
  1) noms=$(printf '%s\n' "$apercu" | sed 1d)
     dis "fusion de main prévue : conflit sur $(printf '%s\n' "$noms" | grep -c .) fichier(s)"
     printf '%s\n' "$noms"
     if [ "$noms" = "$MANUEL_FICHIER" ] && [ "$MODE" = manuel ]; then
       dis "conflit sur le seul manuel généré : il sera régénéré par tools/manual.py (--manuel)"; MANUEL=1
     elif [ "$noms" = "$MANUEL_FICHIER" ]; then
       refus 8 "conflit prévu : rien n'est commencé" "seul le manuel généré est en conflit : relancer avec --manuel"
     else
       refus 8 "conflit prévu : rien n'est commencé" \
         "résolution : reporter par Edit, dans la branche, ce que main change dans ces fichiers, commiter, puis relancer l'outil"
     fi ;;
  *) refus 8 "aperçu de la fusion impossible : rien n'est commencé" ;;
esac

annule() { # code phrase : annule la fusion lancée par l'outil, puis refuse
  git -C "$TOP" merge --abort >/dev/null 2>&1
  if fusion_en_cours; then FUSION_LANCEE=0; refus 11 "annulation impossible : une fusion reste en cours dans le worktree"; fi
  if etat_incertain; then dit_incertain; FUSION_LANCEE=0; exit 11; fi
  FUSION_LANCEE=0
  refus "$1" "$2"
}

# --- fusion : la référence nommée (jamais un nom ambigu) doit valoir encore MAIN_SHA
[ "$(git -C "$TOP" rev-parse -q --verify "$MAIN_REF^{commit}" 2>/dev/null)" = "$MAIN_SHA" ] \
  || refus 7 "main a changé pendant l'exécution : rien n'est fait"
AVANT=$(git -C "$TOP" rev-parse HEAD)
# la référence complète donnerait « Merge branch 'refs/heads/main' » : le message est écrit ici, comme Git l'écrit pour le nom court
if [ "$MAIN_NOM" = main ]; then MESSAGE_FUSION="Merge branch 'main' into $BRANCHE"; else MESSAGE_FUSION="Merge remote-tracking branch 'origin/main' into $BRANCHE"; fi
FUSION_LANCEE=1
if ! git -C "$TOP" -c rerere.enabled=false merge --no-edit -m "$MESSAGE_FUSION" "$MAIN_REF" </dev/null; then
  restants=$(git -C "$TOP" diff --name-only --diff-filter=U)
  if [ "$MANUEL" -eq 1 ] && [ "$restants" = "$MANUEL_FICHIER" ] && fusion_en_cours; then
    dis "conflit sur le seul manuel : régénération par la commande de génération, runner indexé, puis commit de la fusion"
    if ( cd "$TOP" && generer_manuel ) </dev/null \
       && git -C "$TOP" add -- "$MANUEL_FICHIER" \
       && [ -z "$(git -C "$TOP" diff --name-only --diff-filter=U)" ] \
       && ( cd "$TOP" && lancer_runner ) </dev/null \
       && git -C "$TOP" -c rerere.enabled=false commit --no-edit </dev/null; then
      dis "manuel régénéré, runner vert, fusion commitée"
    else
      annule 10 "régénération du manuel, runner ou commit en échec : fusion annulée, rien n'est changé"
    fi
  else
    annule 9 "fusion en échec (conflit non prévu ou crochet refusé) : annulée, rien n'est changé"
  fi
fi
FUSION_LANCEE=0

# --- vérification
SUITE_11=" ; fusion commitée, sommet avant : $(git -C "$TOP" rev-parse --short "$AVANT")"
git -C "$TOP" merge-base --is-ancestor "$MAIN_SHA" HEAD || refus 11 "vérification : main n'est pas contenue dans $BRANCHE$SUITE_11"
[ -z "$(git -C "$TOP" status --porcelain --untracked-files=no)" ] || refus 11 "vérification : worktree pas propre$SUITE_11"
! fusion_en_cours || refus 11 "vérification : une fusion est encore en cours$SUITE_11"
dis "main fusionnée dans $BRANCHE : $(git -C "$TOP" log -1 --format='%h %s')"
exit 0
