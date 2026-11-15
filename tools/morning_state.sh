#!/bin/bash
# PMZilla Lab : la garde du matin légère, lue à un seul endroit (change tooling-morning-guard-light, R-20261102-3 et R-20261102-5,
# design D1 à D5 ; remplace la fenêtre du matin du change morning-guard).
#
#     bash tools/morning_state.sh check                       dit si une fin de branche est permise maintenant (une ligne, puis un avertissement par partie en défaut)
#     bash tools/morning_state.sh check --language en         les mêmes lignes en anglais (« fr » par défaut)
#     bash tools/morning_state.sh runner                      dit si le runner complet d'une session est permis maintenant (session-runner), sans avertissement
#     . tools/morning_state.sh                                 bibliothèque : morning_watch_state, morning_backup_state,
#                                                              morning_backup_dumps, morning_copy_state, morning_watch_running,
#                                                              morning_backup_running, morning_busy, morning_warnings
#
# Règle : un refus (code 1, pour `check` comme pour `runner`) SEULEMENT tant que la veille du jour ou la sauvegarde tournent, à toute
# heure. Toute autre défaillance (veille en échec, interrompue, reportée, absente ou illisible ; sauvegarde absente, incomplète ou dossier
# illisible ; copie hors du Mac ni prouvée ni reportée) est un avertissement : une ligne après la décision, code 0 (`check` seulement).
# Plus de fenêtre du matin, plus de marge, plus d'heure de début (design D5).
#
# « Tourne » = un verrou ou un repère tenu, jamais un repère de passage seul (design D2) : la veille tourne quand le repère du jour dit
# « commence » ET que le dossier veille.verrou du dossier de données porte le pid d'un processus vivant et n'est pas plus vieux que l'âge
# maximal du verrou de tools/watch.sh (PMZILLA_WATCH_LOCK_MAX_AGE, 21600 s) ; la sauvegarde tourne quand le dossier sauvegarde.encours du
# dossier de données porte le pid d'un processus vivant et n'est pas plus vieux que l'âge maximal du repère de tools/db_backup.sh
# (PMZILLA_RUN_MARKER_MAX_AGE, 21600 s). Un repère « commence » sans verrou tenu est un avertissement. Lecture seule des deux.
#
# Trois parties, lues en lecture seule : le repère du passage du jour de la veille (veille-du-jour.json du dossier de données), le
# dossier daté du jour des sauvegardes (db-AAAA-MM-JJ, date du système) avec son nombre de dumps, et les preuves de la copie hors du
# Mac (journal de la copie : lignes datées du jour ; à défaut, le fichier d'état de offsite_backup.sh, lu comme du texte).
# Une erreur isolée d'une source de la veille ne compte pas : la collecte sort alors en code 0 et la veille écrit « termine ».
#
# Fonctions de décision (design D1) : morning_busy rend « veille », « sauvegarde », « veille sauvegarde » (dans cet ordre) ou rien ;
# morning_warnings <langue> rend les avertissements, un par ligne, dans l'ordre veille, sauvegarde, copie. Les lignes de commande ne
# font que les mettre en forme : aucune décision dans un printf.
#
# Codes de la commande : 0 permis ; 1 refusé (veille ou sauvegarde en cours) ; 2 usage (`--margin` compris) ; 78 résolution des dossiers du
# lab en échec (code et message du module tools/lab_paths.sh).
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
#   PMZILLA_WATCH_LOCK_MAX_AGE, PMZILLA_RUN_MARKER_MAX_AGE   âges maximaux du verrou de la veille et du repère de la sauvegarde (secondes)
#   MORNING_DATA, MORNING_BACKUPS, MORNING_NOW  posées par l'appelant qui a déjà résolu les dossiers et l'horloge ;
#                              vides = illisible ; MORNING_NOW (secondes) l'emporte sur PMZILLA_RUN_NOW
# Constantes : MORNING_EXPECTED_DUMPS (le nombre de dumps qu'écrit tools/db_backup.sh : un par schéma de SCHEMAS, plus le dump partiel de
# quality, obligatoire), MORNING_WATCH_LOCK et MORNING_WATCH_LOCK_MAX_AGE (le verrou de tools/watch.sh : nom et âge maximal, sources
# de ces valeurs), MORNING_MARKER_MAX_AGE (l'âge maximal du repère de tools/db_backup.sh, source de cette valeur) ; des tests statiques les
# comparent. Le nom du repère de la sauvegarde est lu en toutes lettres plus bas.
# Remplace : rien (le module lisait les mêmes parties, sans verrou ; les constantes jumelles sont nouvelles, R-20261102-3 et R-20261102-5).
# Retrait des constantes jumelles : tombent avec D1 (morning_busy), permanentes tant que la veille et la sauvegarde tournent sur le Mac des fins.
# Écart entre un jumeau et sa source : détecté par les tests statiques de tests/morning_state, qui nomment la constante.

MORNING_EXPECTED_DUMPS=4
MORNING_WATCH_LOCK="veille.verrou"
MORNING_WATCH_LOCK_MAX_AGE=21600
MORNING_MARKER_MAX_AGE=21600

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

# Verrou ou repère tenu (design D2) : oui si le dossier $1 porte le pid d'un processus vivant et n'est pas plus vieux que $2 secondes
# (début écrit dans le dossier, à défaut la date de modification), non sinon (absent, sans pid lisible, processus mort, trop vieux).
# Lecture seule : jamais créé, retiré ni renouvelé.
morning_held() { # dossier âge-maximal
  local dossier=$1 max=$2 pid debut age mtime
  [ -d "$dossier" ] || { echo non; return; }
  pid=$(cat "$dossier/pid" 2>/dev/null)
  case "$pid" in ''|*[!0-9]*) echo non; return ;; esac
  kill -0 "$pid" 2>/dev/null || { echo non; return; }
  debut=$(cat "$dossier/debut" 2>/dev/null)
  case "$debut" in
    ''|*[!0-9]*)
      mtime=$(stat -c %Y "$dossier" 2>/dev/null || stat -f %m "$dossier" 2>/dev/null)
      case "$mtime" in ''|*[!0-9]*) echo oui; return ;; esac
      age=$(( $(date +%s) - mtime )) ;;
    *) age=$(( $(morning_now) - debut )) ;;
  esac
  if [ "$age" -gt "$max" ]; then echo non; else echo oui; fi
}

# Âge maximal : la variable de réglage de l'appelant si elle est numérique, sinon la valeur par défaut de la source.
morning_max_age() { # variable défaut
  local valeur=${!1:-}
  case "$valeur" in ''|*[!0-9]*) echo "$2" ;; *) echo "$valeur" ;; esac
}

# Veille en cours : oui si le repère du jour dit « commence » ET que le verrou de la veille est tenu (design D2, Q276) ; non sinon.
morning_watch_running() {
  [ "$(morning_watch_state)" = commence ] || { echo non; return; }
  [ -n "${MORNING_DATA:-}" ] || { echo non; return; }
  morning_held "$MORNING_DATA/$MORNING_WATCH_LOCK" "$(morning_max_age PMZILLA_WATCH_LOCK_MAX_AGE "$MORNING_WATCH_LOCK_MAX_AGE")"
}

# Sauvegarde en cours : oui si le repère de passage de tools/db_backup.sh (dossier sauvegarde.encours du dossier de données) est tenu.
morning_backup_running() {
  [ -n "${MORNING_DATA:-}" ] || { echo non; return; }
  morning_held "$MORNING_DATA/sauvegarde.encours" "$(morning_max_age PMZILLA_RUN_MARKER_MAX_AGE "$MORNING_MARKER_MAX_AGE")"
}

# La décision (design D1) : « veille », « sauvegarde », « veille sauvegarde » (dans cet ordre) ou rien.
morning_busy() {
  local sortie=""
  [ "$(morning_watch_running)" = oui ] && sortie="veille"
  [ "$(morning_backup_running)" = oui ] && sortie="${sortie:+$sortie }sauvegarde"
  printf '%s' "$sortie"
}

# Les avertissements (design D1, D4) : langue en argument ; un par ligne, dans l'ordre veille, sauvegarde, copie.
morning_warnings() {
  local lang=${1:-fr} attendu=$MORNING_EXPECTED_DUMPS watch backup dumps copie
  watch=$(morning_watch_state); backup=$(morning_backup_state); dumps=$(morning_backup_dumps); copie=$(morning_copy_state)
  case "$watch" in
    fini) ;;
    autrejour) if [ "$lang" = en ]; then echo "no watch run today"; else echo "veille du jour absente"; fi ;;
    illisible) if [ "$lang" = en ]; then echo "watch state unreadable"; else echo "état de la veille illisible"; fi ;;
    *) if [ "$lang" = en ]; then echo "today's watch run not ended without error (state: $watch)"
       else echo "veille du jour pas terminée sans erreur (état : $watch)"; fi ;;
  esac
  case "$backup" in
    fini) if [ "$dumps" != "$attendu" ]; then
            if [ "$lang" = en ]; then echo "today's backup incomplete ($dumps of $attendu dumps)"
            else echo "sauvegarde du jour incomplète ($dumps dump(s) sur $attendu)"; fi
          fi ;;
    pasfini) if [ "$lang" = en ]; then echo "today's backup missing"; else echo "sauvegarde du jour absente"; fi ;;
    *) if [ "$lang" = en ]; then echo "backups folder unreadable"; else echo "dossier des sauvegardes illisible"; fi ;;
  esac
  case "$copie" in
    prouvee|reportee) ;;
    *) if [ "$lang" = en ]; then echo "today's off-site copy neither proven nor postponed"; else echo "copie hors du Mac du jour ni prouvée ni reportée"; fi ;;
  esac
}

# --- la commande -------------------------------------------------------------------------------------------------------------
morning_usage() { # langue
  if [ "$1" = en ]; then echo "morning_state: usage: check [--language fr|en] | runner [--language fr|en]" >&2
  else echo "morning_state : usage : check [--language fr|en] | runner [--language fr|en]" >&2; fi
  return 2
}

morning_running_reasons() { # langue, occupé : les raisons du refus, dans l'ordre veille, sauvegarde, séparées par « ; »
  local lang=$1 occupe=$2 r=() sortie="" un
  case " $occupe " in *" veille "*) if [ "$lang" = en ]; then r+=("today's watch run in progress"); else r+=("veille du jour en cours"); fi ;; esac
  case " $occupe " in *" sauvegarde "*) if [ "$lang" = en ]; then r+=("backup in progress"); else r+=("sauvegarde en cours"); fi ;; esac
  for un in ${r[@]+"${r[@]}"}; do sortie="${sortie:+$sortie ; }$un"; done
  printf '%s' "$sortie"
}

morning_main() {
  local lang=fr cmd="" occupe avertissements un
  while [ $# -gt 0 ]; do
    case "$1" in
      --language)
        [ $# -ge 2 ] || { morning_usage "$lang"; return 2; }
        case "$2" in fr|en) lang=$2 ;; *) morning_usage "$lang"; return 2 ;; esac
        shift ;;
      check|runner) [ -z "$cmd" ] || { morning_usage "$lang"; return 2; }; cmd=$1 ;;
      *) morning_usage "$lang"; return 2 ;;
    esac
    shift
  done
  [ -n "$cmd" ] || { morning_usage "$lang"; return 2; }
  . "$(dirname "${BASH_SOURCE[0]}")/lab_paths.sh"
  lab_paths_init || return $?
  MORNING_DATA="$LAB_DATA_FOLDER"; MORNING_BACKUPS="$LAB_BACKUPS_FOLDER"
  occupe=$(morning_busy)
  if [ "$cmd" = runner ]; then
    if [ -z "$occupe" ]; then
      if [ "$lang" = en ]; then echo "morning_state: session full runner allowed, neither watch nor backup running"
      else echo "morning_state : runner complet de session permis, ni veille ni sauvegarde en cours"; fi
      return 0
    fi
    if [ "$lang" = en ]; then echo "morning_state: session full runner refused, running: $(morning_running_reasons en "$occupe")"
    else echo "morning_state : runner complet de session refusé, en cours : $(morning_running_reasons fr "$occupe")"; fi
    return 1
  fi
  if [ -z "$occupe" ]; then
    if [ "$lang" = en ]; then echo "morning_state: allowed, neither watch nor backup running"
    else echo "morning_state : autorisé, ni veille ni sauvegarde en cours"; fi
  else
    if [ "$lang" = en ]; then echo "morning_state: refused, running: $(morning_running_reasons en "$occupe")"
    else echo "morning_state : refusé, en cours : $(morning_running_reasons fr "$occupe")"; fi
  fi
  avertissements=$(morning_warnings "$lang")
  local IFS=$'\n'
  for un in $avertissements; do
    if [ "$lang" = en ]; then echo "morning_state: warning: $un"; else echo "morning_state : avertissement : $un"; fi
  done
  [ -z "$occupe" ]
}

# Lancé directement (et non sourcé) : la commande.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  morning_main "$@"
  exit $?
fi
