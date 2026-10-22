# PMZilla Lab : verrou de fin de branche, partie shell (change multi-session-piloting, design D5 et D6).
# Module SOURCÉ (bash) par tools/finish_branch.sh et tools/finish_worktree.sh ; il ne change ni les options du shell appelant ni son dossier
# courant. Le lecteur Python (outil de pilotage, hook pre-commit) est tools/finish_lock.py ; le lanceur de tests lit le verrou lui-même.
#
#     . "$SCRIPT_DIR/finish_lock.sh"
#     finish_lock_acquire "$dossier_git_commun" "$branche"; code=$?     0 pris ou hérité, 1 tenu par un autre, 2 création impossible
#     finish_lock_release                                               à appeler à la sortie (piège EXIT)
#     finish_lock_hhmm <secondes>                                       « HH:MM »
#
# Le verrou est le dossier pmzilla-fin-en-cours du dossier Git commun, créé par mkdir (atomique), propriétaire seul, avec les fichiers pid (celui
# du script), debut (secondes), branche et jeton (128 bits au hasard, jamais affiché). Prise : un verrou dont le jeton est celui de
# FINISH_LOCK_TOKEN est hérité (le script a été lancé par la fin d'un worktree : aucun second verrou, aucune libération) ; un verrou périmé
# (processus mort, plus vieux que PMZILLA_FINISH_LOCK_MAX_AGE secondes, 21600 par défaut, ou sans pid lisible depuis plus de dix secondes) est
# signalé par « verrou de fin périmé, repris » puis remplacé ; un verrou vivant d'un autre jeton est refusé (code 1, branche et début dans
# FL_BRANCH et FL_START). Le jeton pris est exporté dans FINISH_LOCK_TOKEN : toutes les commandes lancées ensuite (contrôle, runner, hooks)
# le portent et ne sont pas refusées par le gel du lanceur de tests et du hook pre-commit. Libération : seulement si le jeton est le sien.
# Sourcé, il n'écrit rien. Lancé directement, il ne fait rien non plus (code 0) :
#
#     bash tools/finish_lock.sh

FINISH_LOCK_NAME="pmzilla-fin-en-cours"
FL_DIR=""
FL_OWN=0
FL_TOKEN=""
FL_BRANCH=""
FL_START=""

_fl_mtime() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null; }

# 0 si le verrou $1 est périmé, 1 s'il est tenu (même règle que les repères de passage de tools/run_worktree.sh)
_fl_stale() {
  local dossier=$1 max="${PMZILLA_FINISH_LOCK_MAX_AGE:-21600}" pid debut mtime age now
  case "$max" in ''|*[!0-9]*) max=21600 ;; esac
  now=$(date +%s)
  pid=$(cat "$dossier/pid" 2>/dev/null)
  case "$pid" in
    ''|*[!0-9]*)
      mtime=$(_fl_mtime "$dossier")
      case "$mtime" in ''|*[!0-9]*) return 1 ;; esac
      [ $(( now - mtime )) -gt 10 ] && return 0
      return 1 ;;
  esac
  kill -0 "$pid" 2>/dev/null || return 0
  debut=$(cat "$dossier/debut" 2>/dev/null)
  case "$debut" in
    ''|*[!0-9]*)
      mtime=$(_fl_mtime "$dossier")
      case "$mtime" in ''|*[!0-9]*) return 1 ;; esac
      age=$(( now - mtime )) ;;
    *) age=$(( now - debut )) ;;
  esac
  [ "$age" -gt "$max" ] && return 0
  return 1
}

finish_lock_hhmm() {
  case "${1:-}" in ''|*[!0-9]*) printf '??:??'; return 0 ;; esac
  date -r "$1" +%H:%M 2>/dev/null || date -d "@$1" +%H:%M 2>/dev/null || printf '??:??'
}

finish_lock_acquire() {
  local commun=$1 branche=$2 dossier lu essai pris=0 jeton
  dossier="$commun/$FINISH_LOCK_NAME"
  FL_BRANCH=""; FL_START=""
  for essai in 1 2 3; do
    if [ -d "$dossier" ]; then
      lu=$(cat "$dossier/jeton" 2>/dev/null)
      if [ -n "${FINISH_LOCK_TOKEN:-}" ] && [ "$lu" = "$FINISH_LOCK_TOKEN" ]; then
        FL_OWN=0
        return 0
      fi
      if _fl_stale "$dossier"; then
        printf '%s : verrou de fin périmé, repris\n' "${NOM:-finish}"
        rm -rf "$dossier"
      else
        FL_BRANCH=$(cat "$dossier/branche" 2>/dev/null)
        FL_START=$(cat "$dossier/debut" 2>/dev/null)
        return 1
      fi
    fi
    if ( umask 077; mkdir "$dossier" ) 2>/dev/null; then pris=1; break; fi
  done
  [ "$pris" -eq 1 ] || return 2
  jeton=$(od -An -N16 -tx1 /dev/urandom 2>/dev/null | tr -d ' \n')
  [ -n "$jeton" ] || jeton="$$-$(date +%s)"
  (
    umask 077
    printf '%s\n' "$$" > "$dossier/pid"
    printf '%s\n' "$(date +%s)" > "$dossier/debut"
    printf '%s\n' "$branche" > "$dossier/branche"
    printf '%s\n' "$jeton" > "$dossier/jeton"
  ) 2>/dev/null || { rm -rf "$dossier"; return 2; }
  FL_DIR=$dossier
  FL_TOKEN=$jeton
  FL_OWN=1
  export FINISH_LOCK_TOKEN="$jeton"
  return 0
}

finish_lock_release() {
  [ "$FL_OWN" -eq 1 ] || return 0
  if [ "$(cat "$FL_DIR/jeton" 2>/dev/null)" = "$FL_TOKEN" ]; then rm -rf "$FL_DIR"; fi
  FL_OWN=0
  return 0
}
