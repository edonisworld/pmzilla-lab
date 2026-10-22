#!/bin/bash
# PMZilla Lab : l'état du matin, lu à un seul endroit (change morning-guard, idée #366, design D1 à D5).
#
#     bash tools/morning_state.sh check                       dit si une fin de branche est permise maintenant (une ligne, un code)
#     bash tools/morning_state.sh check --language en         la même ligne en anglais (« fr » par défaut)
#     . tools/morning_state.sh                                 bibliothèque : morning_watch_state, morning_backup_state,
#                                                              morning_backup_dumps, morning_copy_state, morning_decision
#
# Trois parties, lues en lecture seule : le repère du passage du jour de la veille (veille-du-jour.json du dossier de données), le
# dossier daté du jour des sauvegardes (db-AAAA-MM-JJ, date du système) avec son nombre de dumps, et les preuves de la copie hors du
# Mac (journal de la copie : lignes datées du jour ; à défaut, le fichier d'état de offsite_backup.sh, lu comme du texte).
# Décision : avant le début du matin, permis ; à partir du début du matin et jusqu'à minuit, permis seulement si la veille s'est
# terminée sans erreur (état « termine »), si la sauvegarde du jour est complète (le nombre de dumps attendu) et si la copie hors du Mac
# du jour est prouvée ou reportée par déclaration (offsite_backup.sh postpone). Un état illisible est refusé, sans heure de repli.
# Une erreur isolée d'une source de la veille ne compte pas : la collecte sort alors en code 0 et la veille écrit « termine ».
#
# Codes de la commande : 0 permis ; 1 refusé (la ligne nomme chaque partie en défaut, dans l'ordre veille, sauvegarde, copie) ; 2 usage ;
# 78 résolution des dossiers du lab en échec (code et message du module tools/lab_paths.sh).
# Le module n'écrit rien, ne crée rien, ne retire rien, ne prend ni verrou ni repère, n'affiche aucun chemin, ne liste jamais le dossier
# des sauvegardes (seul le dossier daté du jour est ouvert), ne lit jamais le contenu d'une sauvegarde et ne lance jamais le script de copie.
# Il ne change ni les options du shell appelant ni son dossier courant ; ses fonctions n'appellent jamais exit.
#
# Variables (pour les tests et le réglage) :
#   PMZILLA_LAB_DATA           dossier de données du labo (par tools/lab_paths.sh)
#   DB_BACKUP_SAUVEGARDES      dossier des sauvegardes (par tools/lab_paths.sh)
#   OFFSITE_COPY_LOG           journal de la copie hors du Mac (défaut ~/Library/Logs/pmzilla-offsite-copy.log, la sortie du modèle launchd)
#   OFFSITE_DONNEES            dossier de données de offsite_backup.sh (défaut ~/.pmzilla-lab) : son fichier d'état est offsite/statut
#   PMZILLA_RUN_NOW            horloge en secondes (défaut : l'heure réelle), comme tools/run_worktree.sh
#   PMZILLA_RUN_MORNING_START  « HH:MM », début du matin, heure du système (défaut 06:45 ; une valeur invalide revient au défaut)
#   MORNING_DATA, MORNING_BACKUPS, MORNING_NOW  posées par l'appelant qui a déjà résolu les dossiers et l'horloge (tools/run_worktree.sh) ;
#                              vides = illisible ; MORNING_NOW (secondes) l'emporte sur PMZILLA_RUN_NOW
# Constantes : MORNING_DEFAULT_START (06:45, égal au défaut de tools/run_worktree.sh et à l'heure du modèle de la veille moins
# MORNING_LEAD_MINUTES) et MORNING_EXPECTED_DUMPS (le nombre de dumps qu'écrit tools/db_backup.sh : un par schéma de SCHEMAS, plus le
# dump partiel de quality, obligatoire) ; des tests statiques les comparent.

MORNING_DEFAULT_START="06:45"
MORNING_LEAD_MINUTES=25
MORNING_EXPECTED_DUMPS=4

# HH:MM valide, sinon la valeur de repli
morning_hhmm_or() { if [[ "$1" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]]; then echo "$1"; else echo "$2"; fi; }
# Minutes depuis minuit de « HH:MM »
morning_minutes() { echo $(( 10#${1%%:*} * 60 + 10#${1##*:} )); }
morning_now() { echo "${MORNING_NOW:-${PMZILLA_RUN_NOW:-$(date +%s)}}"; }
# morning_date FORMAT : l'instant de l'horloge, au format donné, selon le système (BSD puis GNU)
morning_date() {
  local instant
  instant=$(morning_now)
  date -r "$instant" "+$1" 2>/dev/null || date -d "@$instant" "+$1" 2>/dev/null
}

# Partie veille : fini | echoue | interrompu | reporte | commence | autrejour | illisible. « fini » seulement pour l'état « termine »,
# que la veille n'écrit que si aucune étape n'a échoué. Lecture seule du repère du jour.
morning_watch_state() {
  local fichier t re jour_repere etat jour
  [ -n "${MORNING_DATA:-}" ] || { echo illisible; return; }
  fichier="$MORNING_DATA/veille-du-jour.json"
  [ -f "$fichier" ] && t=$(cat "$fichier" 2>/dev/null) || { echo illisible; return; }
  re='"date": *"([0-9]{4}-[0-9]{2}-[0-9]{2})"'
  [[ "$t" =~ $re ]] && jour_repere="${BASH_REMATCH[1]}"
  re='"etat": *"(commence|termine|echoue|reporte|interrompu)"'
  [[ "$t" =~ $re ]] && etat="${BASH_REMATCH[1]}"
  { [ -n "${jour_repere:-}" ] && [ -n "${etat:-}" ]; } || { echo illisible; return; }
  jour=$(TZ=Europe/Paris morning_date %Y-%m-%d) || { echo illisible; return; }
  [ "$jour_repere" = "$jour" ] || { echo autrejour; return; }
  case "$etat" in termine) echo fini ;; *) echo "$etat" ;; esac
}

# Partie sauvegarde : fini | pasfini | ignore (dossier des sauvegardes absent) | illisible. Seule l'existence du dossier daté du jour est
# testée ; le dossier des sauvegardes n'est jamais listé, ni ouvert, ni affiché.
morning_backup_state() {
  local dossier="${MORNING_BACKUPS:-}" jour
  [ -n "$dossier" ] || { echo illisible; return; }
  [ -e "$dossier" ] || { echo ignore; return; }
  { [ -d "$dossier" ] && [ -r "$dossier" ] && [ -x "$dossier" ]; } || { echo illisible; return; }
  jour=$(morning_date %Y-%m-%d) || { echo illisible; return; }
  if [ -d "$dossier/db-$jour" ]; then echo fini; else echo pasfini; fi
}

# Nombre de dumps directement dans le dossier daté du jour (les noms ne sont jamais affichés) ; 0 si le dossier est absent.
morning_backup_dumps() {
  local dossier="${MORNING_BACKUPS:-}" jour fichier n=0
  jour=$(morning_date %Y-%m-%d) || { echo 0; return; }
  if [ -n "$dossier" ] && [ -d "$dossier/db-$jour" ]; then
    for fichier in "$dossier/db-$jour"/*.dump; do
      [ -f "$fichier" ] && n=$((n + 1))
    done
  fi
  echo "$n"
}

# Partie copie hors du Mac : prouvee | reportee | absente (design D4). Une ligne du journal sans date en tête, d'un autre jour, ou la
# ligne de report d'un disque absent ne comptent jamais.
morning_copy_state() {
  local jour log statut motif
  jour=$(morning_date %Y-%m-%d) || { echo absente; return; }
  log="${OFFSITE_COPY_LOG:-$HOME/Library/Logs/pmzilla-offsite-copy.log}"
  statut="${OFFSITE_DONNEES:-$HOME/.pmzilla-lab}/offsite/statut"
  motif="^$jour [0-9]{2}:[0-9]{2}:[0-9]{2} "
  if [ -r "$log" ] && grep -q -E "${motif}(copie créée|déjà présente) : db-$jour( |\$)" "$log" 2>/dev/null; then echo prouvee; return; fi
  if [ -r "$statut" ] && grep -q -E "^serie-db .*derniere_copie=db-$jour( |\$)" "$statut" 2>/dev/null; then echo prouvee; return; fi
  if [ -r "$log" ] && grep -q -E "${motif}copie reportée déclarée : db-$jour : " "$log" 2>/dev/null; then echo reportee; return; fi
  echo absente
}

# Évalue les trois parties et la fenêtre ; pose MS_START, MS_WATCH, MS_BACKUP, MS_DUMPS, MS_COPY, MS_DECISION (avant | verifie | refuse).
morning_evaluate() {
  local courant
  MS_START=$(morning_hhmm_or "${PMZILLA_RUN_MORNING_START:-}" "$MORNING_DEFAULT_START")
  MS_WATCH=""; MS_BACKUP=""; MS_DUMPS=0; MS_COPY=""
  courant=$(morning_date %H:%M) || courant=""
  if [ -n "$courant" ] && [ "$(morning_minutes "$courant")" -lt "$(morning_minutes "$MS_START")" ]; then
    MS_DECISION=avant; return 0
  fi
  MS_WATCH=$(morning_watch_state)
  MS_BACKUP=$(morning_backup_state)
  MS_DUMPS=$(morning_backup_dumps)
  MS_COPY=$(morning_copy_state)
  if [ "$MS_WATCH" = fini ] && [ "$MS_BACKUP" = fini ] && [ "$MS_DUMPS" = "$MORNING_EXPECTED_DUMPS" ] \
     && { [ "$MS_COPY" = prouvee ] || [ "$MS_COPY" = reportee ]; }; then
    MS_DECISION=verifie
  else
    MS_DECISION=refuse
  fi
}

# Décision : avant | verifie | refuse
morning_decision() { morning_evaluate; echo "$MS_DECISION"; }

# --- la commande -------------------------------------------------------------------------------------------------------------
morning_usage() { # langue
  if [ "$1" = en ]; then echo "morning_state: usage: check [--language fr|en]" >&2; else echo "morning_state : usage : check [--language fr|en]" >&2; fi
  return 2
}

morning_reasons() { # langue : les raisons de refus, dans l'ordre veille, sauvegarde, copie, séparées par « ; »
  local lang=$1 r=() attendu=$MORNING_EXPECTED_DUMPS
  case "$MS_WATCH" in
    fini) ;;
    autrejour) if [ "$lang" = en ]; then r+=("no watch run today"); else r+=("veille du jour absente"); fi ;;
    illisible) if [ "$lang" = en ]; then r+=("watch state unreadable"); else r+=("état de la veille illisible"); fi ;;
    *) if [ "$lang" = en ]; then r+=("today's watch run not ended without error (state: $MS_WATCH)")
       else r+=("veille du jour pas terminée sans erreur (état : $MS_WATCH)"); fi ;;
  esac
  case "$MS_BACKUP" in
    fini) if [ "$MS_DUMPS" != "$attendu" ]; then
            if [ "$lang" = en ]; then r+=("today's backup incomplete ($MS_DUMPS of $attendu dumps)")
            else r+=("sauvegarde du jour incomplète ($MS_DUMPS dump(s) sur $attendu)"); fi
          fi ;;
    pasfini) if [ "$lang" = en ]; then r+=("today's backup missing"); else r+=("sauvegarde du jour absente"); fi ;;
    *) if [ "$lang" = en ]; then r+=("backups folder unreadable"); else r+=("dossier des sauvegardes illisible"); fi ;;
  esac
  case "$MS_COPY" in
    prouvee|reportee) ;;
    *) if [ "$lang" = en ]; then r+=("today's off-site copy neither proven nor postponed"); else r+=("copie hors du Mac du jour ni prouvée ni reportée"); fi ;;
  esac
  local sortie="" un
  for un in "${r[@]}"; do sortie="${sortie:+$sortie ; }$un"; done
  printf '%s' "$sortie"
}

morning_main() {
  local lang=fr cmd=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --language)
        [ $# -ge 2 ] || { morning_usage "$lang"; return 2; }
        case "$2" in fr|en) lang=$2 ;; *) morning_usage "$lang"; return 2 ;; esac
        shift ;;
      check) [ -z "$cmd" ] || { morning_usage "$lang"; return 2; }; cmd=check ;;
      *) morning_usage "$lang"; return 2 ;;
    esac
    shift
  done
  [ "$cmd" = check ] || { morning_usage "$lang"; return 2; }
  . "$(dirname "${BASH_SOURCE[0]}")/lab_paths.sh"
  lab_paths_init || return $?
  MORNING_DATA="$LAB_DATA_FOLDER"; MORNING_BACKUPS="$LAB_BACKUPS_FOLDER"
  morning_evaluate
  case "$MS_DECISION" in
    avant)
      if [ "$lang" = en ]; then echo "morning_state: allowed, before the morning window (start $MS_START)"
      else echo "morning_state : autorisé, avant la fenêtre du matin (début $MS_START)"; fi
      return 0 ;;
    verifie)
      if [ "$lang" = en ]; then
        printf 'morning_state: allowed, morning state verified (watch without error, backup complete, off-site copy %s)\n' \
          "$([ "$MS_COPY" = reportee ] && echo 'postponed by declaration' || echo proven)"
      else
        printf 'morning_state : autorisé, état du matin vérifié (veille sans erreur, sauvegarde complète, copie hors du Mac %s)\n' \
          "$([ "$MS_COPY" = reportee ] && echo 'reportée par déclaration' || echo prouvée)"
      fi
      return 0 ;;
    *)
      if [ "$lang" = en ]; then echo "morning_state: refused, morning window since $MS_START: $(morning_reasons en)"
      else echo "morning_state : refusé, fenêtre du matin depuis $MS_START : $(morning_reasons fr)"; fi
      return 1 ;;
  esac
}

# Lancé directement (et non sourcé) : la commande.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  morning_main "$@"
  exit $?
fi
