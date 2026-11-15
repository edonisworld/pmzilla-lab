# PMZilla Lab : stabilité d'un worktree après le runner et processus qui y ont leur dossier courant
# (change finish-single-b3-b6, design D4 à D7). Source unique de la règle, pour tools/finish_train.sh (train) ; les fins unitaires qui la partageaient sont retirées par B9.
# Module SOURCÉ (bash du système, 3.2 sur Mac ; ni mapfile ni construction récente) ; il ne contient aucun exit, n'imprime rien, ne change ni les
# options du shell appelant ni son dossier courant, et n'écrit aucun fichier. Chaque appelant garde ses phrases, ses codes, son repère et sa marge
# d'une seconde, et la vérification de l'empreinte du runner.
#
#     . "$(dirname "$0")/finish_stability.sh"
#     fs_snapshot "$worktree"                          avant le runner, après le repère et sa marge ; pose FS_SNAP (« erreur » si un outil échoue), rend 0 ou 1
#     fs_verdict "$worktree" "$repere" "$FS_SNAP"      après le runner ; rend 0 stable, 1 modifié
#     fs_processes "$worktree"                         avant et après le runner ; rend 0 aucun, 1 trouvé, 2 vérification impossible ; pose FS_PROCESSES
#
# Lancé seul, il ne fait rien (il ne définit que des fonctions) :
#
#     bash tools/finish_stability.sh
#
# fs_verdict : modifié si le worktree n'est pas propre ; si un fichier suivi a une date de changement d'état (ctime) plus récente que le repère ;
# si un dossier suivi (la racine et chaque dossier qui contient un fichier suivi) a une date plus récente ET que sa liste « inode nom » montre une
# entrée disparue ou d'un autre inode, un ajout que Git n'ignore pas, ou une liste identique malgré la date ; ou si un outil échoue (fail-closed).
# Seuls les ajouts que Git ignore sont pardonnés. Aucun chemin n'est affiché.
# fs_snapshot : pose FS_SNAP = « erreur » (et rend 1) quand le worktree n'est pas propre au moment du relevé, ou quand un outil échoue ; fs_verdict
# rend alors « modifié » (condition « propre juste avant le runner », une seule règle pour les deux fins).
# LIMITE CONNUE (pour la fin unitaire comme pour le train) : un fichier passager non ignoré, créé puis supprimé dans un dossier qui a aussi reçu un
# ajout ignoré (un __pycache__ par exemple), n'est pas vu : la liste des entrées ne montre que l'ajout ignoré. Dans un worktree neuf, la limite concerne
# chaque dossier où le runner crée un __pycache__. Conséquence acceptée : un fichier ignoré créé puis supprimé laisse la liste identique, donc « modifié ».
# fs_processes : lsof -w -n -P -d cwd -F pn ; les AUTRES processus (hors celui de l'appelant) dont le dossier courant est le worktree ou un dossier
# dedans ; FS_PROCESSES = « numéro nom » séparés par « , », le nom étant le dernier segment de la commande, réduit aux lettres, chiffres et « ._+ - »
# (« ? » s'il est vide), jamais les arguments ni le chemin complet. Impossible : lsof absent, code non nul, ou liste qui ne nomme pas l'appelant.
#
# Codes de sortie du script : sans objet (module sourcé).

FS_SNAP=""
FS_PROCESSES=""

fs_tracked_dirs() { # worktree : ses dossiers suivis (racine « . » comprise), chemins relatifs précédés de « ./ », terminés par un octet nul, sans doublon ; code non nul si git ls-files échoue
  (
    set -o pipefail
    { printf '.\0'
      git -C "$1" ls-files -z 2>/dev/null | while IFS= read -r -d '' f; do
        while case "$f" in */*) true ;; *) false ;; esac; do f=${f%/*}; printf './%s\0' "$f"; done
      done
    } | sort -zu
  )
}

fs_ls_norm() { # entrée standard : sortie de « ls -ai » ; sortie : lignes « inode nom » sans espaces de tête (macOS cale les inodes à droite sur la largeur du plus grand), « . » et « .. » retirés, triées en LC_ALL=C ; code 1 si une ligne n'est pas « chiffres, espace, nom » (un nom avec retour à la ligne : liste ambiguë)
  local o
  o=$(LC_ALL=C sed -E -e 's/^ +//' -e '/^[0-9]+ \.{1,2}$/d') || return 1
  [ -z "$(LC_ALL=C grep -v -E '^[0-9]+ .' <<< "$o")" ] || return 1
  [ -z "$o" ] || LC_ALL=C sort <<< "$o"
}

fs_ls_dir() { # worktree dossier (chemin « ./… » depuis le worktree) : ses entrées « inode nom » normalisées par fs_ls_norm ; code 1 si ls échoue ou si fs_ls_norm refuse
  local o
  o=$(cd "$1" && env -u CLICOLOR -u CLICOLOR_FORCE LC_ALL=C /bin/ls -ai -- "$2" 2>/dev/null) || return 1
  fs_ls_norm <<< "$o"
}

fs_snapshot() { # worktree : relevé avant le runner ; pour chaque dossier suivi, une ligne « @@ dossier » puis ses entrées « inode nom » ; FS_SNAP = « erreur » si le worktree n'est pas propre ou si un outil échoue
  local out s
  s=$(git -C "$1" status --porcelain 2>/dev/null) || { FS_SNAP=erreur; return 1; }
  [ -z "$s" ] || { FS_SNAP=erreur; return 1; }
  out=$(set -o pipefail; fs_tracked_dirs "$1" | while IFS= read -r -d '' d; do
    printf '@@ %s\n' "$d"
    fs_ls_dir "$1" "$d" || return 1
  done) || { FS_SNAP=erreur; return 1; }
  FS_SNAP=$out
  return 0
}

fs_dirs_verdict() { # worktree relevé ; entrée standard : dossiers dont la date a changé (octets nuls) ; écrit « x » au premier cas modifié
  local d before after removed added names p n ign rc
  while IFS= read -r -d '' d; do
    [ "$d" != ERREUR ] || { echo x; return 0; }
    before=$(D="$d" awk '$0 == "@@ " ENVIRON["D"] { p = 1; next } /^@@ / { p = 0 } p' <<< "$2")
    after=$(fs_ls_dir "$1" "$d") || { echo x; return 0; }
    [ "$before" != "$after" ] || { echo x; return 0; }
    removed=$(A="$after" awk 'BEGIN { n = split(ENVIRON["A"], x, "\n"); for (i = 1; i <= n; i++) s[x[i]] = 1 } !($0 in s)' <<< "$before")
    [ -z "$removed" ] || { echo x; return 0; }
    added=$(B="$before" awk 'BEGIN { n = split(ENVIRON["B"], x, "\n"); for (i = 1; i <= n; i++) s[x[i]] = 1 } !($0 in s)' <<< "$after")
    [ -n "$added" ] || { echo x; return 0; }
    names=$(sed -E 's/^ *[0-9]+ //' <<< "$added")
    n=$(grep -c . <<< "$names")
    p=${d#./}
    [ "$p" = . ] && p="" || p="$p/"
    # chemins séparés par NUL (check-ignore -z) ; la sortie, comptée par ligne, ne s'accorde qu'avec n : un nom à retour à la ligne donne « modifié »
    ign=$(P="$p" awk '{ print ENVIRON["P"] $0 }' <<< "$names" | tr '\n' '\0' | git -C "$1" check-ignore -z --stdin 2>/dev/null | tr '\0' '\n'; return "${PIPESTATUS[2]}"); rc=$?
    [ "$rc" -le 1 ] || { echo x; return 0; }
    [ "$(grep -c . <<< "$ign")" -eq "$n" ] || { echo x; return 0; }
  done
}

fs_verdict() { # worktree repère relevé : 0 stable, 1 modifié (date de changement d'état comparée au repère ; les dossiers jugés sur leur liste d'entrées)
  local s change
  s=$(git -C "$1" status --porcelain 2>/dev/null) || return 1
  [ -z "$s" ] || return 1
  # fichiers suivis : find de macOS veut les chemins avant l'expression ; aucun nom n'est affiché, un « x » par lot ; une commande en échec donne aussi un « x »
  change=$(set -o pipefail; git -C "$1" ls-files -z 2>/dev/null | (cd "$1" && xargs -0 sh -c 'if [ $# -gt 0 ]; then
    if sortie=$(find -P "$@" -maxdepth 0 -cnewer "$0" -print 2>/dev/null); then [ -z "$sortie" ] || echo x; else echo x; fi
    fi' "$2" 2>/dev/null) || echo x)
  [ -z "$change" ] || return 1
  [ "$3" != erreur ] || return 1
  [ -n "$3" ] || return 1
  change=$(set -o pipefail; fs_tracked_dirs "$1" | (cd "$1" && xargs -0 sh -c 'if [ $# -gt 0 ]; then
    find -P "$@" -maxdepth 0 -cnewer "$0" -print0 2>/dev/null || printf "ERREUR\0"
    fi' "$2" 2>/dev/null) | fs_dirs_verdict "$1" "$3") || change=x
  [ -z "$change" ] || return 1
  return 0
}

fs_processes() { # worktree : 0 aucun autre processus, 1 trouvé, 2 vérification impossible ; pose FS_PROCESSES
  local liste ligne pid="" chemin real vu_soi=0 trouve=0 brut nom vus=" "
  FS_PROCESSES=""
  command -v lsof >/dev/null 2>&1 || return 2
  liste=$(lsof -w -n -P -d cwd -F pn 2>/dev/null </dev/null) || return 2
  real=$(cd "$1" 2>/dev/null && pwd -P) || real=$1
  while IFS= read -r ligne; do
    case "$ligne" in
      p*) pid=${ligne#p}; [ "$pid" != "$$" ] || vu_soi=1 ;;
      n*) chemin=${ligne#n}
          if [ "$pid" != "$$" ]; then
            case "$chemin/" in
              "$real"/*)
                trouve=1
                case "$vus" in
                  *" $pid "*) ;;
                  *)
                    vus="$vus$pid "
                    brut=$(ps -o pid=,comm= -p "$pid" 2>/dev/null | head -n 1)
                    nom=$(printf '%s' "$brut" | sed 's/^ *[0-9]* *//')
                    nom=${nom##*/}
                    nom=$(printf '%s' "$nom" | tr -cd '[:alnum:]._+ -')
                    [ -n "$nom" ] || nom="?"
                    FS_PROCESSES="${FS_PROCESSES:+$FS_PROCESSES, }$pid $nom" ;;
                esac ;;
            esac
          fi ;;
    esac
  done <<< "$liste"
  if [ "$vu_soi" -ne 1 ]; then FS_PROCESSES=""; return 2; fi
  [ "$trouve" -eq 0 ] || return 1
  return 0
}
