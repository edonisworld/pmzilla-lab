#!/bin/bash
# Dossier d'exécution du labo (change run-worktree, R-43) : un worktree Git détaché au sommet de la branche locale main,
# à côté du dépôt de développement. Les tâches planifiées et le serveur de la bibliothèque lancent le code de ce dossier.
#
#     bash tools/run_worktree.sh create [--language fr|en]    crée le dossier d'exécution puis prépare ses dépendances
#     bash tools/run_worktree.sh update [--language fr|en]    avance le dossier d'exécution au sommet de main (avance rapide seulement)
#     bash tools/run_worktree.sh status [--language fr|en]    dit l'état, sans rien changer
#     bash tools/run_worktree.sh --help                       affiche ce texte et les codes
#
# Codes : 0 créé, déjà présent, mis à jour, à jour (status : propre au sommet de main) ; 1 commande git en échec ; 2 usage ;
#         3 dépôt de développement ou main local introuvable ; 4 dossier d'exécution absent (update, status) ou dossier occupé (create) ;
#         5 modifications locales dans le dossier d'exécution ; 6 dossier sur une branche ou hors de l'historique de main ;
#         7 mise à jour reportée (verrou de la veille ou repère de passage tenu, ou passages du matin pas terminés) ;
#         8 status seulement : en retard sur main ; 9 dépendances du nouveau code non préparées (create, update).
# Le code 9 arrive après le mouvement : la tête reste au sommet de main, la commande update relancée refait la préparation.
#
# Le script ne fait que lire le verrou veille.verrou et les repères sauvegarde.encours, horsmac-copie.encours et
# horsmac-restauration.encours du dossier de données : il n'en crée, n'en prend et n'en retire aucun (décisions D12 à D14).
# État du matin (change safe-branch-finish, D1 à D4) : du début du matin jusqu'à la fin de la période du matin, la mise à jour est
# reportée tant que les passages du matin du jour ne sont pas terminés : le repère du passage du jour de la veille porte la date du jour
# (Paris) et un état final (termine, echoue, interrompu), et le dossier des sauvegardes porte le dossier daté du jour (db-AAAA-MM-JJ,
# date du système, jamais une sauvegarde étiquetée). Un dossier des sauvegardes absent : la partie sauvegarde ne compte pas. Quand
# l'état ne peut pas être lu, la mise à jour est reportée jusqu'à l'heure de repli, puis elle continue avec une ligne d'information.
# Le repère de la veille n'est jamais écrit, le dossier des sauvegardes n'est jamais listé ni ouvert, aucun chemin n'est affiché.
# Ces deux lectures passent par le module partagé tools/morning_state.sh (change morning-guard) ; la règle de ce script (états finaux,
# sauvegarde du jour sans compter les dumps, ni copie hors du Mac) n'est pas celle du garde-fou des fins de branche.
# Interdit au script : toute remise à zéro, tout nettoyage, toute mise de côté, toute récupération distante, tout changement de branche,
# tout retrait ou toute recréation du dossier, tout contournement ; il n'écrit aucun fichier suivi ni aucun fichier de verrou.
#
# Variables (nommées par la suite de tests) :
#   PMZILLA_LAB_RUN              emplacement du dossier d'exécution (défaut : le dossier run du dossier du lab, par tools/lab_paths.sh)
#   PMZILLA_LAB_DATA             dossier de données du labo (défaut : celui de tools/lab_paths.sh)
#   PMZILLA_RUN_NOW              horloge en secondes (défaut : l'heure réelle)
#   PMZILLA_RUN_MORNING_START    « HH:MM », début du matin, heure du système (défaut 06:45)
#   PMZILLA_RUN_MORNING_END      « HH:MM », fin de la période du matin (défaut 22:00, l'heure limite de watch.sh)
#   PMZILLA_RUN_FALLBACK_TIME    « HH:MM », heure de repli quand l'état du matin est illisible (défaut 09:30)
#   (une valeur invalide revient au défaut ; les anciennes variables de fenêtres n'ont plus d'effet)
#   DB_BACKUP_SAUVEGARDES        dossier des sauvegardes (même règle que db_backup.sh, par tools/lab_paths.sh)
#   PMZILLA_WATCH_LOCK_MAX_AGE   âge maximal du verrou de la veille, en secondes (même constante que watch.sh)
#   PMZILLA_RUN_MARKER_MAX_AGE   âge maximal des repères, en secondes (même constante que db_backup.sh et offsite_backup.sh)
set -u

NOM="run_worktree"
LANGUE="fr"
CMD=""
RELANCE="bash tools/run_worktree.sh update"
RUN="${PMZILLA_LAB_RUN:-}"   # vide : le module partagé tools/lab_paths.sh le donne (dossier run du dossier du lab), plus bas
DATA="${PMZILLA_LAB_DATA:-}"   # vide : le module partagé le donne, plus bas
AGE_MAX_VERROU="${PMZILLA_WATCH_LOCK_MAX_AGE:-21600}"
AGE_MAX_REPERE="${PMZILLA_RUN_MARKER_MAX_AGE:-21600}"
# Heures du matin (HH:MM, heure du système) : une valeur invalide revient au défaut. La fin du matin égale l'heure limite de watch.sh.
heure_ou() { if [[ "$1" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]]; then echo "$1"; else echo "$2"; fi; }
DEBUT_MATIN=$(heure_ou "${PMZILLA_RUN_MORNING_START:-}" "06:45")
FIN_MATIN=$(heure_ou "${PMZILLA_RUN_MORNING_END:-}" "22:00")
HEURE_REPLI=$(heure_ou "${PMZILLA_RUN_FALLBACK_TIME:-}" "09:30")
# États qui terminent le jour pour la veille (mêmes noms que watch.sh)
ETATS_FINAUX="termine echoue interrompu"
MAINTENANT="${PMZILLA_RUN_NOW:-$(date +%s)}"
# Scripts lancés par uv run depuis les points d'entrée planifiés, en plus de la liste des liens de install_links.sh.
SUPPLEMENTS=(composants.py dashboard.py doctor.py db.py)

# msg CLE [argument] : phrase de la clé dans la langue choisie
msg() {
  local cle=$1 a=${2:-}
  if [ "$LANGUE" = en ]; then
    case "$cle" in
      cree) echo "run_worktree: created" ;;
      present) echo "run_worktree: already present" ;;
      maj) echo "run_worktree: updated" ;;
      ajour) echo "run_worktree: up to date" ;;
      retard) echo "run_worktree: behind main" ;;
      depok) echo "run_worktree: dependencies prepared" ;;
      depko) echo "run_worktree: dependencies not prepared" ;;
      git) echo "run_worktree: git command failed" ;;
      introuvable) echo "run_worktree: development checkout not found" ;;
      absent) echo "run_worktree: run tree missing" ;;
      occupe) echo "run_worktree: the folder exists and is not the run tree" ;;
      local) echo "run_worktree: local changes in the run tree" ;;
      histoire) echo "run_worktree: the run tree is not on an ancestor of main" ;;
      tenu) echo "run_worktree: update postponed, scheduled run in progress ($a)" ;;
      matin) echo "run_worktree: update postponed, morning runs not finished ($a)" ;;
      illisible) echo "run_worktree: update postponed, morning runs state unreadable, before $a" ;;
      repli) echo "run_worktree: morning runs state unreadable, fallback time passed" ;;
      attente) echo "run_worktree: waiting for the record of the day's watch run, state: $a" ;;
      reprise) echo "Once the watch is unblocked: $RELANCE" ;;
      perime) echo "run_worktree: stale run marker, ignored ($a)" ;;
      serveur) echo "library server: the old code stays loaded until the next session" ;;
      relance) echo "To run it later: $RELANCE" ;;
      script) echo "script: $a" ;;
    esac
  else
    case "$cle" in
      cree) echo "run_worktree : créé" ;;
      present) echo "run_worktree : déjà présent" ;;
      maj) echo "run_worktree : mis à jour" ;;
      ajour) echo "run_worktree : à jour" ;;
      retard) echo "run_worktree : en retard sur main" ;;
      depok) echo "run_worktree : dépendances préparées" ;;
      depko) echo "run_worktree : dépendances non préparées" ;;
      git) echo "run_worktree : commande git en échec" ;;
      introuvable) echo "run_worktree : dépôt de développement introuvable" ;;
      absent) echo "run_worktree : dossier d'exécution absent" ;;
      occupe) echo "run_worktree : le dossier existe et n'est pas le dossier d'exécution" ;;
      local) echo "run_worktree : modifications locales dans le dossier d'exécution" ;;
      histoire) echo "run_worktree : le dossier d'exécution n'est pas sur un ancêtre de main" ;;
      tenu) echo "run_worktree : mise à jour reportée, passage planifié en cours ($a)" ;;
      matin) echo "run_worktree : mise à jour reportée, passages du matin pas terminés ($a)" ;;
      illisible) echo "run_worktree : mise à jour reportée, état des passages du matin illisible, avant $a" ;;
      repli) echo "run_worktree : état des passages du matin illisible, heure de repli passée" ;;
      attente) echo "run_worktree : en attente du repère du passage du jour de la veille, état : $a" ;;
      reprise) echo "Une fois la veille débloquée : $RELANCE" ;;
      perime) echo "run_worktree : repère de passage périmé, ignoré ($a)" ;;
      serveur) echo "serveur de la bibliothèque : l'ancien code reste chargé jusqu'à la prochaine session" ;;
      relance) echo "Pour le relancer plus tard : $RELANCE" ;;
      script) echo "script : $a" ;;
    esac
  fi
}

refus() { # code cle [argument] [relance] : phrase sur la sortie d'erreur, puis la commande à relancer si demandée
  local code=$1 cle=$2 a=${3:-} rel=${4:-}
  msg "$cle" "$a" >&2
  [ -n "$rel" ] && msg relance >&2
  exit "$code"
}

aide() {
  if [ "$LANGUE" = en ]; then
    cat <<'TXT'
run_worktree: the run tree, a Git worktree detached at the tip of local main.

  bash tools/run_worktree.sh create [--language fr|en]
  bash tools/run_worktree.sh update [--language fr|en]   fast-forward only, then prepares the locked dependencies
  bash tools/run_worktree.sh status [--language fr|en]   read-only

Codes: 0 done or up to date; 1 git command failed; 2 usage; 3 development checkout or main not found;
4 run tree missing (update, status) or folder occupied (create); 5 local changes; 6 on a branch or off the history of main;
7 update postponed (watch lock or run marker held, or morning runs not finished; rerun later); 8 status only: behind main;
9 dependencies not prepared (rerun update).
TXT
  else
    cat <<'TXT'
run_worktree : le dossier d'exécution, un worktree Git détaché au sommet de main local.

  bash tools/run_worktree.sh create [--language fr|en]
  bash tools/run_worktree.sh update [--language fr|en]   avance rapide seulement, puis prépare les dépendances verrouillées
  bash tools/run_worktree.sh status [--language fr|en]   lecture seule

Codes : 0 fait ou à jour ; 1 commande git en échec ; 2 usage ; 3 dépôt de développement ou main introuvable ;
4 dossier d'exécution absent (update, status) ou dossier occupé (create) ; 5 modifications locales ; 6 sur une branche ou hors de l'historique de main ;
7 mise à jour reportée (verrou de la veille ou repère tenu, ou passages du matin pas terminés ; à relancer plus tard) ; 8 status seulement : en retard sur main ;
9 dépendances non préparées (relancer update).
TXT
  fi
}

# --- arguments : l'option de langue est acceptée avant et après la sous-commande
AIDE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --help|-h) AIDE=1 ;;
    --language)
      [ $# -ge 2 ] || { echo "run_worktree : usage" >&2; exit 2; }
      case "$2" in fr|en) LANGUE=$2 ;; *) echo "run_worktree : langue inconnue (fr ou en)" >&2; exit 2 ;; esac
      shift ;;
    create|update|status) [ -z "$CMD" ] || { echo "run_worktree : usage" >&2; exit 2; }; CMD=$1 ;;
    *) echo "run_worktree : usage : create, update ou status" >&2; exit 2 ;;
  esac
  shift
done
[ "$AIDE" -eq 1 ] && { aide; exit 0; }
[ -n "$CMD" ] || { echo "run_worktree : usage : create, update ou status" >&2; exit 2; }

# --- dépôt de développement : le dépôt du script lui-même, et son main local
chemin_script="${BASH_SOURCE[0]}"
DEV=$(cd "$(dirname "$chemin_script")/.." 2>/dev/null && git rev-parse --show-toplevel 2>/dev/null)
[ -n "$DEV" ] && DEV=$(cd "$DEV" && pwd -P)
[ -n "$DEV" ] || refus 3 introuvable
git -C "$DEV" rev-parse --verify -q refs/heads/main >/dev/null 2>&1 || refus 3 introuvable
# Dossiers par défaut : le module partagé (R-77, safe-branch-finish D9), jamais un chemin sous le dossier personnel. Échec de résolution :
# code 78 quand le dossier d'exécution en dépend ; sinon l'état du matin le traite comme illisible (le dossier des sauvegardes n'est pas trouvé).
. "$(dirname "$chemin_script")/lab_paths.sh"
if lab_paths_init 2>/dev/null; then
  [ -n "$RUN" ] || RUN="$LAB_RUN_TREE"
  [ -n "$DATA" ] || DATA="$LAB_DATA_FOLDER"
elif [ -z "$RUN" ] || [ -z "$DATA" ]; then
  lab_paths_init; exit $?   # refait l'appel pour écrire le message du module (code 78) ; sans dossier de données, ni verrou ni repères ne se lisent
else
  LAB_BACKUPS_FOLDER=""     # dossier des sauvegardes introuvable : sa partie de l'état du matin est illisible
fi
# Module partagé de l'état du matin (morning-guard D1) : il lit le repère de la veille et le dossier des sauvegardes de ce script, avec son horloge.
. "$(dirname "$chemin_script")/morning_state.sh"
MORNING_DATA="${DATA:-}"; MORNING_BACKUPS="${LAB_BACKUPS_FOLDER:-}"; MORNING_NOW="$MAINTENANT"

tete_main() { git -C "$DEV" rev-parse --verify -q refs/heads/main; }

# 0 si le dossier d'exécution est un worktree du dépôt de développement
run_valide() {
  local haut commun_run commun_dev
  [ -d "$RUN" ] || return 1
  haut=$(git -C "$RUN" rev-parse --show-toplevel 2>/dev/null) || return 1
  [ "$(cd "$haut" && pwd -P)" = "$(cd "$RUN" && pwd -P)" ] || return 1
  commun_run=$(cd "$RUN" && cd "$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null && pwd -P) || return 1
  commun_dev=$(cd "$DEV" && cd "$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null && pwd -P) || return 1
  [ -n "$commun_run" ] && [ "$commun_run" = "$commun_dev" ]
}

exiger_run() { # code 4 si le dossier est absent ou n'est pas le dossier d'exécution
  [ -e "$RUN" ] || refus 4 absent
  run_valide || refus 4 occupe
}

# état : ajour | retard ; sort avec 6 ou 5 si le dossier ne convient pas
etat_run() {
  local tete main
  git -C "$RUN" symbolic-ref -q HEAD >/dev/null 2>&1 && refus 6 histoire "" "${1:-}"
  tete=$(git -C "$RUN" rev-parse --verify -q HEAD 2>/dev/null) || refus 1 git
  main=$(tete_main)
  git -C "$DEV" merge-base --is-ancestor "$tete" "$main" 2>/dev/null || refus 6 histoire "" "${1:-}"
  [ -z "$(git -C "$RUN" status --porcelain 2>/dev/null)" ] || refus 5 local "" "${1:-}"
  if [ "$tete" = "$main" ]; then ETAT=ajour; else ETAT=retard; fi
}

# --- lecture du verrou et des repères (D12, D14) : lecture seule
mtime_de() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null; }
# 0 si le dossier $1 est périmé (processus mort, trop vieux, ou abandonné), 1 s'il est tenu ; $2 : âge maximal
repere_perime() {
  local dossier=$1 max=$2 pid debut age mtime
  pid=$(cat "$dossier/pid" 2>/dev/null)
  if ! [[ "$pid" =~ ^[0-9]+$ ]]; then
    mtime=$(mtime_de "$dossier")
    [[ "$mtime" =~ ^[0-9]+$ ]] && [ $(( $(date +%s) - mtime )) -gt 10 ] && return 0
    return 1
  fi
  kill -0 "$pid" 2>/dev/null || return 0
  debut=$(cat "$dossier/debut" 2>/dev/null)
  if [[ "$debut" =~ ^[0-9]+$ ]]; then
    age=$(( MAINTENANT - debut ))
  else
    mtime=$(mtime_de "$dossier")
    [[ "$mtime" =~ ^[0-9]+$ ]] || return 1
    age=$(( $(date +%s) - mtime ))
  fi
  [ "$age" -gt "$max" ] && return 0
  return 1
}

# Minutes depuis minuit de « HH:MM »
minutes_de() { echo $(( 10#${1%%:*} * 60 + 10#${1##*:} )); }
# date <instant> <format> selon le système (BSD puis GNU)
date_de() { date -r "$MAINTENANT" "+$1" 2>/dev/null || date -d "@$MAINTENANT" "+$1" 2>/dev/null; }

# Les parties veille et sauvegarde de l'état du matin sont lues par le module partagé tools/morning_state.sh (change morning-guard, D1) :
# morning_watch_state (fini | echoue | interrompu | reporte | commence | autrejour | illisible) et morning_backup_state (fini | pasfini |
# ignore | illisible). Ici, les états finaux de ETATS_FINAUX comptent comme « fini » (règle propre à ce script ; le garde-fou des fins de
# branche n'accepte que « termine »).

garde_horaire() { # sort avec 7 si un repère est tenu ou si les passages du matin ne sont pas terminés
  local def dossier tache job nom max premier=""
  for def in "veille.verrou|veille|watch|$AGE_MAX_VERROU" "sauvegarde.encours|sauvegarde|backup|$AGE_MAX_REPERE" \
             "horsmac-copie.encours|copie hors du Mac|off-site copy|$AGE_MAX_REPERE" \
             "horsmac-restauration.encours|test de restauration hors du Mac|off-site restore test|$AGE_MAX_REPERE"; do
    IFS='|' read -r dossier tache job max <<EOF2
$def
EOF2
    [ -n "$DATA" ] && [ -d "$DATA/$dossier" ] || continue
    if [ "$LANGUE" = en ]; then nom=$job; else nom=$tache; fi
    if repere_perime "$DATA/$dossier" "$max"; then
      msg perime "$nom"
    elif [ -z "$premier" ]; then
      premier=$nom
    fi
  done
  [ -z "$premier" ] || refus 7 tenu "$premier" rel
  garde_matin
}

garde_matin() { # état du matin (D2, D3) : lu seulement du début du matin jusqu'à la fin de la période du matin
  local cur v s illisible=0 nom_veille nom_sauv etat_aff
  cur=$(date_de %H:%M) || return 0
  cur=$(minutes_de "$cur")
  [ "$cur" -ge "$(minutes_de "$DEBUT_MATIN")" ] && [ "$cur" -le "$(minutes_de "$FIN_MATIN")" ] || return 0
  v=$(morning_watch_state); s=$(morning_backup_state)
  case " $ETATS_FINAUX " in *" $v "*) v=fini ;; esac
  if [ "$LANGUE" = en ]; then nom_veille=watch; nom_sauv=backup; else nom_veille=veille; nom_sauv=sauvegarde; fi
  case "$v" in
    reporte|commence|autrejour)
      case "$v:$LANGUE" in
        reporte:en) etat_aff="reported" ;; reporte:fr) etat_aff="reporté" ;;
        commence:en) etat_aff="started" ;; commence:fr) etat_aff="commencé" ;;
        autrejour:en) etat_aff="of another day" ;; *) etat_aff="d'un autre jour" ;;
      esac
      msg matin "$nom_veille" >&2; msg attente "$etat_aff" >&2; msg reprise >&2
      exit 7 ;;
    illisible) illisible=1 ;;
  esac
  [ "$s" != pasfini ] || refus 7 matin "$nom_sauv" rel
  [ "$s" != illisible ] || illisible=1
  if [ "$illisible" -eq 1 ]; then
    if [ "$cur" -lt "$(minutes_de "$HEURE_REPLI")" ]; then refus 7 illisible "$HEURE_REPLI" rel; fi
    msg repli
  fi
}

# --- préparation des dépendances : uv sync --locked --script pour chaque script à bloc de dépendances et fichier .lock
liste_scripts() {
  local liens=""
  if [ -f "$RUN/tools/install_links.sh" ]; then
    liens=$(sed -n '/^SCRIPTS=(/,/)/p' "$RUN/tools/install_links.sh" | sed 's/^SCRIPTS=(//; s/)//' | tr -s ' \t' '\n\n')
  fi
  { printf '%s\n' "$liens"; printf '%s\n' "${SUPPLEMENTS[@]}"; } | grep -E '\.py$' | awk '!vu[$0]++'
}
preparer() {
  local s
  while IFS= read -r s; do
    [ -f "$RUN/tools/$s" ] && [ -f "$RUN/tools/$s.lock" ] || continue
    grep -q '^# /// script' "$RUN/tools/$s" || continue
    if ! ( cd "$RUN" && uv sync --locked --script "tools/$s" >/dev/null 2>&1 ); then
      msg depko >&2; msg script "$s" >&2; msg relance >&2
      exit 9
    fi
  done <<EOF3
$(liste_scripts)
EOF3
  msg depok
}

# --- sous-commandes
cmd_create() {
  if [ -e "$RUN" ]; then
    run_valide || refus 4 occupe
    msg present
    exit 0
  fi
  git -C "$DEV" worktree add -q --detach "$RUN" refs/heads/main >/dev/null 2>&1 || refus 1 git
  msg cree
  preparer
  exit 0
}

cmd_update() {
  exiger_run
  etat_run rel
  garde_horaire
  if [ "$ETAT" = retard ]; then
    git -C "$RUN" checkout -q --detach refs/heads/main >/dev/null 2>&1 || refus 1 git
    msg maj
    preparer
    msg serveur
  else
    msg ajour
    preparer
  fi
  exit 0
}

cmd_status() {
  exiger_run
  etat_run ""
  if [ "$ETAT" = retard ]; then msg retard; exit 8; fi
  msg ajour
  exit 0
}

case "$CMD" in
  create) cmd_create ;;
  update) cmd_update ;;
  status) cmd_status ;;
esac
