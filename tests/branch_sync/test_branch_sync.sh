#!/bin/bash
# Test de l'outil de fusion de main dans une branche de travail (tools/branch_sync.sh, change branch-sync) : dépôts et worktrees Git
# TEMPORAIRES, avec un dépôt distant nu ; l'outil est lancé par /bin/bash (bash 3.2 sur Mac), entrée vide, toujours dans un dossier sous $tmp.
# Cas : usage et aide ; chaque refus (hors dépôt, espace de travail, main, spike/*, dossier d'exécution sur une branche, détaché ou nommé par
# PMZILLA_LAB_RUN, HEAD détachée, worktree sale, fusion en cours, autre opération en cours, verrou d'une autre fin, depuis l'espace de travail
# aussi, verrou laissé tel quel ; verrou périmé ignoré) ; main déjà contenue ; fusion sans conflit (main local en avance, origin/main en
# avance) ; références divergentes ; conflit prévu (rien de commencé) ; crochet commit-msg qui refuse (fusion annulée) ; --manuel (manuel seul
# régénéré par une fausse commande puis commité ; génération en échec ; autre conflit ; manuel seul sans l'option) ; --check en lecture seule ;
# interruption (fusion lancée par l'outil annulée) ; relevé des commandes interdites dans l'outil.
# Revue Opus : BRANCH_SYNC_MANUAL et BRANCH_SYNC_RUNNER n'acceptent qu'un fichier exécutable (refus 2, jamais d'eval) ; runner exécuté en
# --manuel (rouge : 10) ; fusion de refs/heads/main, référence déplacée : 7 ; rerere coupé ; code 11 (fusion commitée, écriture interrompue
# avant MERGE_HEAD, annulation impossible) ; main absente ; radar sur références divergentes ; avance rapide ; fichier non suivi sur le chemin.
# Un faux « git » (créé ici, dans le dossier temporaire, sélectionné par FAUX_GIT) simule : aperçu impossible, aperçu faussement propre,
# référence déplacée après l'aperçu, annulation qui échoue, interruption pendant l'écriture de la fusion.
# Lancement à la main : bash tests/branch_sync/test_branch_sync.sh </dev/null
set -u
script="$(cd "$(dirname "$0")/../../tools" && pwd)/branch_sync.sh"
BASH_OUTIL=bash; [ -x /bin/bash ] && BASH_OUTIL=/bin/bash
tmp=$(cd "$(mktemp -d)" && pwd -P) || exit 1
trap 'chmod -R u+rwX "$tmp" 2>/dev/null; rm -rf "$tmp"' EXIT
export GIT_CONFIG_GLOBAL="$tmp/gitconfig" GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0 GIT_CEILING_DIRECTORIES="$tmp"
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE FINISH_LOCK_TOKEN PMZILLA_LAB_RUN BRANCH_SYNC_MANUAL BRANCH_SYNC_RUNNER PMZILLA_FINISH_LOCK_MAX_AGE FAUX_GIT
git config --global user.email t@example.org
git config --global user.name test
git config --global init.defaultBranch main
ok=0; ko=0; n=0
SORTIE=""; CODE=0

verifie() { # description condition (0 = vrai)
  if [ "$2" -eq 0 ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1 :: $SORTIE"; ko=$((ko+1)); fi
}
contient() { printf '%s' "$SORTIE" | grep -qF -- "$1"; }
code_et() { # description code-attendu [phrase]
  desc=$1; attendu=$2; phrase=${3:-}
  if [ "$CODE" -eq "$attendu" ] && { [ -z "$phrase" ] || contient "$phrase"; }; then
    echo "ok : $desc"; ok=$((ok+1))
  else
    echo "ECHEC : $desc (code $CODE, attendu $attendu, phrase « $phrase ») :: $SORTIE"; ko=$((ko+1))
  fi
}

nouveau() { # $ws : espace de travail sur main, distant nu poussé ; $wt : worktree de feat/x
  n=$((n+1)); cas="$tmp/cas$n"; ws="$cas/espace"; wt="$cas/wt-feat-x"
  mkdir -p "$cas"; git init -q "$ws"
  ( cd "$ws" || exit 1
    echo base > f.txt; echo g > g.txt; mkdir -p docs/pmzilla; echo manuel > docs/pmzilla/manuel.md
    git add -A; git commit -q -m initial
    git init -q --bare "$cas/distant.git"; git remote add origin "$cas/distant.git"; git push -q origin main 2>/dev/null
    git fetch -q origin ) || exit 1
  git -C "$ws" worktree add -q -b feat/x "$wt" main
}
commit_dans() { # dossier fichier contenu
  ( cd "$1" && printf '%s\n' "$3" > "$2" && git add -- "$2" && git commit -q -m "change $2" ) || exit 1
}
lance() { # dossier arguments... : lance l'outil depuis le dossier, jamais hors de $tmp
  dossier=$1; shift
  case "$dossier" in "$tmp"/*) ;; *) echo "garde-fou : $dossier hors de $tmp" >&2; exit 1 ;; esac
  SORTIE=$(cd "$dossier" && "$BASH_OUTIL" "$script" "$@" 2>&1 </dev/null); CODE=$?
}
fusion_en_cours() { [ -e "$(git -C "$1" rev-parse --path-format=absolute --git-path MERGE_HEAD)" ]; }
etat() { # dossier : références, HEAD, état des fichiers, fusion en cours
  git -C "$1" for-each-ref --format='%(refname) %(objectname)'
  git -C "$1" rev-parse HEAD
  git -C "$1" status --porcelain
  git -C "$1" ls-files -s
  fusion_en_cours "$1" && echo "fusion en cours"
  return 0
}
inchange() { # description dossier état-avant
  [ "$(etat "$2")" = "$3" ]; verifie "$1 : rien n'a changé" $?
}
contient_ref() { [ "$(git -C "$1" rev-list --count "HEAD..$2")" -eq 0 ]; }   # la branche du dossier contient la référence
propre() { [ -z "$(git -C "$1" status --porcelain --untracked-files=no)" ] && ! fusion_en_cours "$1"; }
pose_verrou() { # pid branche : verrou de fin dans le dossier Git commun de $ws
  v="$ws/.git/pmzilla-fin-en-cours"; mkdir -p "$v"
  printf '%s\n' "$1" > "$v/pid"; date +%s > "$v/debut"; printf '%s\n' "$2" > "$v/branche"; echo jeton-autre > "$v/jeton"
}
pid_mort() { sleep 0 & p=$!; wait "$p"; echo "$p"; }
outil() { # chemin corps : petit exécutable de test
  mkdir -p "$(dirname "$1")"; printf '#!/bin/bash\n%s\n' "$2" > "$1"; chmod +x "$1"
}
lance_avec() { # dossier "VAR=valeur" arguments... : lance l'outil avec une variable d'environnement
  dossier=$1; assign=$2; shift 2
  case "$dossier" in "$tmp"/*) ;; *) echo "garde-fou : $dossier hors de $tmp" >&2; exit 1 ;; esac
  SORTIE=$(cd "$dossier" && env "$assign" "$BASH_OUTIL" "$script" "$@" 2>&1 </dev/null); CODE=$?
}
lance_manuel() { # dossier manuel-exe runner-exe : --manuel avec les deux exécutables
  dossier=$1
  SORTIE=$(cd "$dossier" && BRANCH_SYNC_MANUAL="$2" BRANCH_SYNC_RUNNER="$3" "$BASH_OUTIL" "$script" --manuel 2>&1 </dev/null); CODE=$?
}
lance_faux() { # dossier mode arguments... : lance l'outil avec le faux git du mode
  dossier=$1; mode=$2; shift 2
  case "$dossier" in "$tmp"/*) ;; *) echo "garde-fou : $dossier hors de $tmp" >&2; exit 1 ;; esac
  SORTIE=$(cd "$dossier" && PATH="$tmp/fauxbin:$PATH" FAUX_GIT="$mode" "$BASH_OUTIL" "$script" "$@" 2>&1 </dev/null); CODE=$?
}
GIT_REEL=$(command -v git); export GIT_REEL
mkdir -p "$tmp/fauxbin"
cat > "$tmp/fauxbin/git" <<'FAUX'
#!/bin/bash
reel=$GIT_REEL
cmd=""; abort=0
for a in "$@"; do
  case "$a" in
    merge-tree) [ -n "$cmd" ] || cmd=merge-tree ;;
    merge) [ -n "$cmd" ] || cmd=merge ;;
    --abort) abort=1 ;;
  esac
done
case "${FAUX_GIT:-}:$cmd" in
  apercu-impossible:merge-tree) exit 2 ;;
  apercu-propre:merge-tree) "$reel" rev-parse 'HEAD^{tree}'; exit 0 ;;
  course:merge-tree)
    "$reel" "$@"; rc=$?
    nouveau=$("$reel" commit-tree -p refs/heads/main -m course 'refs/heads/main^{tree}')
    "$reel" update-ref refs/heads/main "$nouveau"
    exit "$rc" ;;
  abort-vain:merge) if [ "$abort" -eq 1 ]; then exit 1; fi ;;
  ecriture:merge)
    "$reel" "$@" --no-commit --no-ff
    rm -f "$("$reel" rev-parse --path-format=absolute --git-path MERGE_HEAD)"
    kill -TERM "$PPID"; sleep 1; exit 1 ;;
  reste:merge) # Git efface MERGE_HEAD après le crochet post-merge : le faux git le remet après le commit
    "$reel" "$@" || exit
    "$reel" rev-parse HEAD > "$("$reel" rev-parse --path-format=absolute --git-path MERGE_HEAD)"; exit 0 ;;
esac
exec "$reel" "$@"
FAUX
chmod +x "$tmp/fauxbin/git"

# --- usage et aide
nouveau; avant=$(etat "$wt")
lance "$wt" --autre; code_et "option inconnue : code 2" 2 "branch_sync : usage : bash tools/branch_sync.sh [--manuel | --check | --help]"
lance "$wt" feat/y; code_et "nom de branche donné : code 2" 2 "usage"
lance "$wt" --check --manuel; code_et "deux options : code 2" 2 "usage"
lance "$wt" --help; code_et "aide : code 0" 0 "Codes"
contient "--check"; verifie "aide : le radar est décrit" $?
inchange "usage et aide" "$wt" "$avant"

# --- 3 hors dépôt
mkdir -p "$tmp/hors"; lance "$tmp/hors"; code_et "hors dépôt : code 3" 3 "branch_sync : hors d'un dépôt Git : rien n'est fait"

# --- 3 espace de travail
nouveau; commit_dans "$ws" g.txt "main avance"; avant=$(etat "$ws")
lance "$ws"; code_et "espace de travail : code 3" 3 "branch_sync : refusé : l'espace de travail n'est pas une branche de travail"
inchange "espace de travail" "$ws" "$avant"

# --- 3 main
nouveau; git -C "$ws" switch -q -c autre; git -C "$ws" worktree add -q "$cas/wt-main" main; avant=$(etat "$cas/wt-main")
lance "$cas/wt-main"; code_et "worktree sur main : code 3" 3 "branch_sync : refusé : main n'est pas une branche de travail"
inchange "worktree sur main" "$cas/wt-main" "$avant"

# --- 3 spike
nouveau; git -C "$ws" worktree add -q -b spike/essai "$cas/wt-spike" main; commit_dans "$ws" g.txt "main avance"; avant=$(etat "$cas/wt-spike")
lance "$cas/wt-spike"; code_et "branche spike : code 3" 3 "branch_sync : refusé : spike/essai n'est pas une branche de travail"
inchange "branche spike" "$cas/wt-spike" "$avant"

# --- 3 dossier d'exécution (sur une branche, détaché, nommé par la variable)
nouveau; git -C "$ws" worktree add -q -b feat/run "$cas/run" main; commit_dans "$ws" g.txt "main avance"; avant=$(etat "$cas/run")
lance "$cas/run"; code_et "dossier d'exécution sur une branche : code 3" 3 "branch_sync : refusé : le dossier d'exécution n'est pas une branche de travail"
inchange "dossier d'exécution sur une branche" "$cas/run" "$avant"
nouveau; git -C "$ws" worktree add -q --detach "$cas/run" main
lance "$cas/run"; code_et "dossier d'exécution détaché : code 3" 3 "le dossier d'exécution n'est pas une branche de travail"
nouveau; commit_dans "$ws" g.txt "main avance"; avant=$(etat "$wt")
SORTIE=$(cd "$wt" && PMZILLA_LAB_RUN="$wt" "$BASH_OUTIL" "$script" 2>&1 </dev/null); CODE=$?
code_et "dossier d'exécution nommé par PMZILLA_LAB_RUN : code 3" 3 "le dossier d'exécution n'est pas une branche de travail"
inchange "dossier d'exécution nommé" "$wt" "$avant"

# --- 3 HEAD détachée
nouveau; git -C "$ws" worktree add -q --detach "$cas/wt-detache" main; commit_dans "$ws" g.txt "main avance"
lance "$cas/wt-detache"; code_et "HEAD détachée : code 3" 3 "branch_sync : refusé : HEAD détachée, aucune branche de travail"

# --- 5 worktree sale ; un fichier non suivi ne compte pas
nouveau; commit_dans "$ws" g.txt "main avance"; echo sale >> "$wt/f.txt"; avant=$(etat "$wt")
lance "$wt"; code_et "worktree sale : code 5" 5 "branch_sync : worktree pas propre : rien n'est fait"
contient "f.txt"; verifie "worktree sale : le fichier modifié est montré" $?
inchange "worktree sale" "$wt" "$avant"
nouveau; commit_dans "$ws" g.txt "main avance"; echo note > "$wt/notes.txt"
lance "$wt"; code_et "fichier non suivi seul : la fusion se fait" 0 "main fusionnée dans feat/x"
[ -f "$wt/notes.txt" ]; verifie "fichier non suivi : laissé en place" $?

# --- 6 fusion en cours, autre opération en cours
nouveau; commit_dans "$ws" g.txt "main avance"
git -C "$ws" rev-parse main > "$(git -C "$wt" rev-parse --path-format=absolute --git-path MERGE_HEAD)"; avant=$(etat "$wt")
lance "$wt"; code_et "fusion en cours : code 6" 6 "branch_sync : une fusion est déjà en cours dans le worktree : rien n'est fait"
inchange "fusion en cours" "$wt" "$avant"
nouveau; commit_dans "$ws" g.txt "main avance"; mkdir -p "$(git -C "$wt" rev-parse --path-format=absolute --git-path rebase-merge)"
lance "$wt"; code_et "rebase en cours : code 6" 6 "branch_sync : une opération Git (rebase, cherry-pick ou revert) est en cours dans le worktree : rien n'est fait"
nouveau; commit_dans "$ws" g.txt "main avance"; mkdir -p "$(git -C "$wt" rev-parse --path-format=absolute --git-path rebase-apply)"; avant=$(etat "$wt")
lance "$wt"; code_et "rebase-apply en cours : code 6" 6 "branch_sync : une opération Git (rebase, cherry-pick ou revert) est en cours dans le worktree : rien n'est fait"
inchange "rebase-apply en cours" "$wt" "$avant"

# --- 4 verrou d'une autre fin (avant le lieu), verrou périmé
nouveau; commit_dans "$ws" g.txt "main avance"; pose_verrou "$$" feat/autre; avant=$(etat "$wt"); verrou_avant=$(cat "$ws/.git/pmzilla-fin-en-cours/jeton")
lance "$wt"; code_et "verrou d'une autre fin : code 4" 4 "branch_sync : fin de branche en cours (feat/autre, depuis "
contient ") : rien n'est fait"; verifie "verrou : fin de la phrase" $?
inchange "verrou d'une autre fin" "$wt" "$avant"
lance "$ws"; code_et "verrou, depuis l'espace de travail : code 4 avant le refus du lieu" 4 "fin de branche en cours (feat/autre"
[ "$(cat "$ws/.git/pmzilla-fin-en-cours/jeton" 2>/dev/null)" = "$verrou_avant" ]; verifie "verrou laissé tel quel" $?
nouveau; commit_dans "$ws" g.txt "main avance"; pose_verrou "$(pid_mort)" feat/morte
lance "$wt"; code_et "verrou périmé : ignoré, la fusion se fait" 0 "main fusionnée dans feat/x"
[ -d "$ws/.git/pmzilla-fin-en-cours" ]; verifie "verrou périmé : jamais retiré par l'outil" $?

# --- 0 main déjà contenue
nouveau; avant=$(etat "$wt")
lance "$wt"; code_et "main déjà contenue : code 0" 0 "branch_sync : déjà à jour : main est contenue dans feat/x"
inchange "main déjà contenue" "$wt" "$avant"

# --- 0 main local en avance, sans conflit
nouveau; commit_dans "$ws" g.txt "main avance"; commit_dans "$wt" h.txt "branche"
main_avant=$(git -C "$ws" rev-parse main); origine_avant=$(git -C "$ws" rev-parse origin/main)
lance "$wt"; code_et "main local en avance : code 0" 0 "branch_sync : main fusionnée dans feat/x : "
contient "fusion de main prévue : sans conflit"; verifie "main local en avance : aperçu montré" $?
contient_ref "$wt" main; verifie "main local en avance : main contenue dans la branche" $?
[ "$(git -C "$wt" rev-list --parents -n 1 HEAD | wc -w | tr -d ' ')" -eq 3 ]; verifie "main local en avance : commit de fusion à deux parents" $?
propre "$wt"; verifie "main local en avance : worktree propre, aucune fusion en cours" $?
[ "$(git -C "$ws" rev-parse main)" = "$main_avant" ] && [ "$(git -C "$ws" rev-parse origin/main)" = "$origine_avant" ]; verifie "main local en avance : main et origin/main inchangées" $?
[ "$(git -C "$wt" log -1 --format=%s)" = "Merge branch 'main' into feat/x" ]; verifie "main local en avance : message de fusion par défaut" $?

# --- 0 origin/main en avance
nouveau; ( cd "$ws" && git switch -q -c tmp && echo distant > g.txt && git commit -q -am distant && git push -q origin tmp:main 2>/dev/null \
  && git switch -q main && git branch -q -D tmp && git fetch -q origin ) || exit 1
commit_dans "$wt" h.txt "branche"
main_avant=$(git -C "$ws" rev-parse main)
lance "$wt"; code_et "origin/main en avance : code 0" 0 "main fusionnée dans feat/x"
contient "origin/main"; verifie "origin/main en avance : la référence est nommée" $?
contient_ref "$wt" origin/main; verifie "origin/main en avance : origin/main contenue dans la branche" $?
[ "$(git -C "$ws" rev-parse main)" = "$main_avant" ]; verifie "origin/main en avance : main local inchangée" $?
[ "$(git -C "$wt" log -1 --format=%s)" = "Merge remote-tracking branch 'origin/main' into feat/x" ]; verifie "origin/main en avance : message de fusion de la référence distante" $?
# --- 7 références divergentes
nouveau; ( cd "$ws" && git switch -q -c tmp && echo distant > g.txt && git commit -q -am distant && git push -q origin tmp:main 2>/dev/null \
  && git switch -q main && git branch -q -D tmp && git fetch -q origin ) || exit 1
commit_dans "$ws" h.txt "local"; avant=$(etat "$wt")
lance "$wt"; code_et "références divergentes : code 7" 7 "branch_sync : main local et origin/main ont divergé : rien n'est fait"
inchange "références divergentes" "$wt" "$avant"

# --- 8 conflit prévu
nouveau; commit_dans "$ws" f.txt "version main"; commit_dans "$wt" f.txt "version branche"; avant=$(etat "$wt")
lance "$wt"; code_et "conflit prévu : code 8" 8 "branch_sync : conflit prévu : rien n'est commencé"
contient "fusion de main prévue : conflit sur 1 fichier(s)" && contient "f.txt"; verifie "conflit prévu : fichiers listés" $?
contient "Edit"; verifie "conflit prévu : la voie de résolution est dite" $?
inchange "conflit prévu" "$wt" "$avant"

# --- 9 crochet commit-msg qui refuse (conflit réel non prévu)
nouveau; commit_dans "$ws" g.txt "main avance"; commit_dans "$wt" h.txt "branche"
mkdir -p "$cas/crochets"; printf '#!/bin/sh\necho "commit-msg : refusé"\nexit 1\n' > "$cas/crochets/commit-msg"; chmod +x "$cas/crochets/commit-msg"
git -C "$ws" config core.hooksPath "$cas/crochets"; avant=$(etat "$wt")
lance "$wt"; code_et "crochet qui refuse : code 9" 9 "branch_sync : fusion en échec (conflit non prévu ou crochet refusé) : annulée, rien n'est changé"
inchange "crochet qui refuse" "$wt" "$avant"
propre "$wt"; verifie "crochet qui refuse : aucune fusion ne reste" $?

# --- --manuel
manuel_conflit() { nouveau; commit_dans "$ws" docs/pmzilla/manuel.md "manuel main"; commit_dans "$wt" docs/pmzilla/manuel.md "manuel branche"; }
manuel_conflit; avant=$(etat "$wt")
lance "$wt"; code_et "manuel seul sans --manuel : code 8" 8 "seul le manuel généré est en conflit : relancer avec --manuel"
inchange "manuel seul sans --manuel" "$wt" "$avant"
manuel_conflit
outil "$tmp/outils/gen-ok" 'printf "régénéré\n" > docs/pmzilla/manuel.md; pwd -P > "$(dirname "$0")/dossier-gen"'
outil "$tmp/outils/gen-echec" 'exit 1'
outil "$tmp/outils/gen-trace" 'printf x > "$(dirname "$0")/genere"'
outil "$tmp/outils/runner-ok" 'pwd -P > "$(dirname "$0")/dossier-runner"; [ -e "$(git rev-parse --path-format=absolute --git-path MERGE_HEAD)" ] && echo merge > "$(dirname "$0")/runner-merge"; git show :docs/pmzilla/manuel.md > "$(dirname "$0")/runner-manuel"; exit 0'
outil "$tmp/outils/runner-rouge" 'exit 1'
outil "$tmp/outils/runner-trace" 'printf x > "$(dirname "$0")/runner-lance"'
rm -f "$tmp/outils/dossier-gen" "$tmp/outils/dossier-runner" "$tmp/outils/runner-merge" "$tmp/outils/runner-manuel" "$tmp/outils/genere" "$tmp/outils/runner-lance"
lance_manuel "$wt" "$tmp/outils/gen-ok" "$tmp/outils/runner-ok"
code_et "--manuel, manuel seul : code 0" 0 "main fusionnée dans feat/x"
[ "$(cat "$wt/docs/pmzilla/manuel.md")" = "régénéré" ]; verifie "--manuel : manuel régénéré par la commande de génération" $?
[ "$(cat "$tmp/outils/dossier-gen" 2>/dev/null)" = "$wt" ]; verifie "--manuel : génération lancée dans le worktree" $?
[ "$(cat "$tmp/outils/dossier-runner" 2>/dev/null)" = "$wt" ]; verifie "--manuel : runner lancé dans le worktree" $?
[ -e "$tmp/outils/runner-merge" ] && [ "$(cat "$tmp/outils/runner-manuel")" = "régénéré" ]; verifie "--manuel : runner lancé avant le commit, manuel régénéré déjà indexé" $?
contient_ref "$wt" main && propre "$wt"; verifie "--manuel : main contenue, worktree propre, fusion commitée" $?
[ "$(git -C "$wt" rev-list --parents -n 1 HEAD | wc -w | tr -d ' ')" -eq 3 ]; verifie "--manuel : commit de fusion à deux parents" $?
manuel_conflit; avant=$(etat "$wt")
lance_manuel "$wt" "$tmp/outils/gen-echec" "$tmp/outils/runner-trace"
code_et "--manuel, génération en échec : code 10" 10 "branch_sync : régénération du manuel, runner ou commit en échec : fusion annulée, rien n'est changé"
[ ! -e "$tmp/outils/runner-lance" ]; verifie "--manuel, génération en échec : runner jamais lancé" $?
inchange "--manuel, génération en échec" "$wt" "$avant"
manuel_conflit; avant=$(etat "$wt")
lance_manuel "$wt" "$tmp/outils/gen-ok" "$tmp/outils/runner-rouge"
code_et "--manuel, runner rouge : code 10" 10 "branch_sync : régénération du manuel, runner ou commit en échec : fusion annulée, rien n'est changé"
inchange "--manuel, runner rouge" "$wt" "$avant"
propre "$wt"; verifie "--manuel, runner rouge : aucune fusion ne reste" $?
nouveau; commit_dans "$ws" g.txt "main avance"; commit_dans "$wt" h.txt "branche"; rm -f "$tmp/outils/runner-lance"
lance_manuel "$wt" "$tmp/outils/gen-trace" "$tmp/outils/runner-trace"
code_et "--manuel sans conflit : fusion ordinaire, code 0" 0 "main fusionnée dans feat/x"
[ ! -e "$tmp/outils/runner-lance" ] && [ ! -e "$tmp/outils/genere" ]; verifie "--manuel sans conflit : ni génération ni runner" $?
manuel_conflit; commit_dans "$ws" f.txt "version main"; commit_dans "$wt" f.txt "version branche"; avant=$(etat "$wt")
lance_manuel "$wt" "$tmp/outils/gen-trace" "$tmp/outils/runner-trace"
code_et "--manuel, autre conflit : code 8" 8 "conflit prévu : rien n'est commencé"
[ ! -e "$tmp/outils/genere" ] && [ ! -e "$tmp/outils/runner-lance" ]; verifie "--manuel, autre conflit : génération et runner jamais lancés" $?
inchange "--manuel, autre conflit" "$wt" "$avant"

# --- 2 BRANCH_SYNC_MANUAL et BRANCH_SYNC_RUNNER : seulement un fichier exécutable, jamais d'eval
nouveau; commit_dans "$ws" g.txt "main avance"; avant=$(etat "$wt"); rm -f "$cas/injecte"
lance_avec "$wt" "BRANCH_SYNC_MANUAL=printf x > '$cas/injecte'"
code_et "BRANCH_SYNC_MANUAL, une commande : code 2" 2 "BRANCH_SYNC_MANUAL doit désigner un fichier exécutable"
[ ! -e "$cas/injecte" ]; verifie "BRANCH_SYNC_MANUAL, une commande : jamais interprétée" $?
lance_avec "$wt" "BRANCH_SYNC_MANUAL=$tmp/outils/inexistant"; code_et "BRANCH_SYNC_MANUAL, fichier absent : code 2" 2 "doit désigner un fichier exécutable"
printf 'x\n' > "$tmp/outils/pas-exec"; chmod -x "$tmp/outils/pas-exec"
lance_avec "$wt" "BRANCH_SYNC_MANUAL=$tmp/outils/pas-exec"; code_et "BRANCH_SYNC_MANUAL, fichier non exécutable : code 2" 2 "doit désigner un fichier exécutable"
lance_avec "$wt" "BRANCH_SYNC_RUNNER=printf x > '$cas/injecte'"
code_et "BRANCH_SYNC_RUNNER, une commande : code 2" 2 "BRANCH_SYNC_RUNNER doit désigner un fichier exécutable"
[ ! -e "$cas/injecte" ]; verifie "BRANCH_SYNC_RUNNER, une commande : jamais interprétée" $?
lance_avec "$wt" "BRANCH_SYNC_RUNNER=$tmp/outils/inexistant"; code_et "BRANCH_SYNC_RUNNER, fichier absent : code 2" 2 "BRANCH_SYNC_RUNNER doit désigner un fichier exécutable"
lance_avec "$wt" "BRANCH_SYNC_RUNNER=$tmp/outils/pas-exec"; code_et "BRANCH_SYNC_RUNNER, fichier non exécutable : code 2" 2 "doit désigner un fichier exécutable"
inchange "variables refusées" "$wt" "$avant"

# --- 0 avance rapide : acceptée, sans commit de fusion
nouveau; commit_dans "$ws" g.txt "main avance"
lance "$wt"; code_et "avance rapide : code 0" 0 "main fusionnée dans feat/x"
[ "$(git -C "$wt" rev-parse HEAD)" = "$(git -C "$ws" rev-parse main)" ] && [ "$(git -C "$wt" rev-list --parents -n 1 HEAD | wc -w | tr -d ' ')" -eq 2 ]; verifie "avance rapide : la branche est sur main, aucun commit de fusion" $?
propre "$wt"; verifie "avance rapide : worktree propre" $?

# --- 0 rerere coupé pour la fusion et le commit
manuel_conflit; git -C "$ws" config rerere.enabled true
lance_manuel "$wt" "$tmp/outils/gen-ok" "$tmp/outils/runner-ok"
code_et "rerere activé dans le dépôt : --manuel, code 0" 0 "main fusionnée dans feat/x"
[ -z "$(ls "$ws/.git/rr-cache" 2>/dev/null)" ]; verifie "rerere coupé : rien n'est enregistré dans rr-cache" $?

# --- 9 fichier non suivi sur le chemin de la fusion
nouveau; commit_dans "$ws" nouveau.txt "de main"; printf 'local\n' > "$wt/nouveau.txt"; avant=$(etat "$wt")
lance "$wt"; code_et "fichier non suivi sur le chemin : code 9" 9 "branch_sync : fusion en échec (conflit non prévu ou crochet refusé) : annulée, rien n'est changé"
[ "$(cat "$wt/nouveau.txt")" = "local" ]; verifie "fichier non suivi sur le chemin : contenu laissé tel quel" $?
inchange "fichier non suivi sur le chemin" "$wt" "$avant"

# --- 6 cherry-pick et revert en cours
for operation in CHERRY_PICK_HEAD REVERT_HEAD; do
  nouveau; commit_dans "$ws" g.txt "main avance"
  git -C "$ws" rev-parse main > "$(git -C "$wt" rev-parse --path-format=absolute --git-path "$operation")"; avant=$(etat "$wt")
  lance "$wt"; code_et "$operation : code 6" 6 "branch_sync : une opération Git (rebase, cherry-pick ou revert) est en cours dans le worktree : rien n'est fait"
  inchange "$operation" "$wt" "$avant"
done

# --- 7 main introuvable (radar compris), main déplacée après l'aperçu
nouveau; git -C "$ws" switch -q -c autre; git -C "$ws" branch -q -D main; avant=$(etat "$wt")
lance "$wt"; code_et "main introuvable : code 7" 7 "branch_sync : main introuvable : rien n'est fait"
inchange "main introuvable" "$wt" "$avant"
lance "$ws" --check; code_et "--check, main introuvable : code 7" 7 "main introuvable"
nouveau; commit_dans "$ws" g.txt "main avance"; tete=$(git -C "$wt" rev-parse HEAD)
lance_faux "$wt" course; code_et "main déplacée après l'aperçu : code 7" 7 "branch_sync : main a changé pendant l'exécution : rien n'est fait"
[ "$(git -C "$wt" rev-parse HEAD)" = "$tete" ]; verifie "main déplacée : la branche n'a pas bougé" $?
propre "$wt"; verifie "main déplacée : worktree propre, aucune fusion ne reste" $?

# --- 8 aperçu impossible
nouveau; commit_dans "$ws" g.txt "main avance"; avant=$(etat "$wt")
lance_faux "$wt" apercu-impossible; code_et "aperçu impossible : code 8" 8 "branch_sync : aperçu de la fusion impossible : rien n'est commencé"
inchange "aperçu impossible" "$wt" "$avant"

# --- 9 vrai conflit que l'aperçu n'a pas prévu (aperçu faussé par le faux git) : fusion annulée
nouveau; commit_dans "$ws" f.txt "version main"; commit_dans "$wt" f.txt "version branche"; avant=$(etat "$wt")
lance_faux "$wt" apercu-propre; code_et "conflit non prévu par l'aperçu : code 9" 9 "branch_sync : fusion en échec (conflit non prévu ou crochet refusé) : annulée, rien n'est changé"
inchange "conflit non prévu par l'aperçu" "$wt" "$avant"
propre "$wt"; verifie "conflit non prévu : aucune fusion ne reste" $?

# --- 11 annulation impossible, interruption avant MERGE_HEAD, vérification d'après en échec
nouveau; commit_dans "$ws" g.txt "main avance"; commit_dans "$wt" h.txt "branche"
mkdir -p "$cas/crochets"; printf '#!/bin/sh\necho "commit-msg : refusé"\nexit 1\n' > "$cas/crochets/commit-msg"; chmod +x "$cas/crochets/commit-msg"
git -C "$ws" config core.hooksPath "$cas/crochets"
lance_faux "$wt" abort-vain; code_et "annulation impossible : code 11" 11 "branch_sync : annulation impossible : une fusion reste en cours dans le worktree"
fusion_en_cours "$wt"; verifie "annulation impossible : la fusion reste en cours, rien n'est forcé" $?
nouveau; commit_dans "$ws" g.txt "main avance"; commit_dans "$wt" h.txt "branche"; avant_sha=$(git -C "$wt" rev-parse HEAD)
lance_faux "$wt" ecriture; code_et "interruption avant MERGE_HEAD : code 11" 11 "sommet avant la fusion : $avant_sha"
contient "rien n'est remis à zéro"; verifie "interruption avant MERGE_HEAD : rien remis à zéro, dit" $?
[ "$(git -C "$wt" rev-parse HEAD)" = "$avant_sha" ] && [ -n "$(git -C "$wt" status --porcelain --untracked-files=no)" ]; verifie "interruption avant MERGE_HEAD : état laissé tel quel (HEAD inchangé, worktree sale)" $?
nouveau; commit_dans "$ws" g.txt "main avance"; commit_dans "$wt" h.txt "branche"; avant_sha=$(git -C "$wt" rev-parse HEAD)
mkdir -p "$cas/crochets"; printf '#!/bin/sh\necho sale >> f.txt\n' > "$cas/crochets/post-merge"; chmod +x "$cas/crochets/post-merge"
git -C "$ws" config core.hooksPath "$cas/crochets"
lance "$wt"; code_et "vérification d'après en échec : code 11, fusion commitée" 11 "branch_sync : vérification : worktree pas propre ; fusion commitée, sommet avant : $(git -C "$wt" rev-parse --short "$avant_sha")"
nouveau; commit_dans "$ws" g.txt "main avance"; commit_dans "$wt" h.txt "branche"; avant_sha=$(git -C "$wt" rev-parse HEAD)
mkdir -p "$cas/crochets"; printf '#!/bin/sh\ngit reset -q --hard HEAD^1\n' > "$cas/crochets/post-merge"; chmod +x "$cas/crochets/post-merge"
git -C "$ws" config core.hooksPath "$cas/crochets"
lance "$wt"; code_et "vérification d'après, main non contenue : code 11" 11 "branch_sync : vérification : main n'est pas contenue dans feat/x ; fusion commitée, sommet avant : $(git -C "$wt" rev-parse --short "$avant_sha")"
nouveau; commit_dans "$ws" g.txt "main avance"; commit_dans "$wt" h.txt "branche"; avant_sha=$(git -C "$wt" rev-parse HEAD)
lance_faux "$wt" reste; code_et "vérification d'après, fusion encore en cours : code 11" 11 "branch_sync : vérification : une fusion est encore en cours ; fusion commitée, sommet avant : $(git -C "$wt" rev-parse --short "$avant_sha")"
fusion_en_cours "$wt"; verifie "vérification d'après, fusion encore en cours : MERGE_HEAD laissé, jamais annulé après le commit" $?

# --- --check (lecture seule)
nouveau; git -C "$ws" worktree add -q -b feat/b "$cas/wt-b" main; git -C "$ws" worktree add -q -b feat/c "$cas/wt-c" main
git -C "$ws" worktree add -q -b spike/s "$cas/wt-s" main
commit_dans "$ws" f.txt "version main"
git -C "$ws" worktree add -q --detach "$cas/run" main
commit_dans "$cas/wt-c" f.txt "version c"; commit_dans "$cas/wt-b" h.txt "b"
git -C "$wt" reset -q --hard main
tous() { for d in "$ws" "$wt" "$cas/wt-b" "$cas/wt-c" "$cas/wt-s" "$cas/run"; do etat "$d"; done; }
avant=$(tous)
lance "$ws" --check; code_et "--check : code 0" 0 "branch_sync : 3 worktree(s) de branche de travail, 2 en retard sur main, 1 avec conflit prévu"
contient "feat/x ($wt) : à jour"; verifie "--check : branche à jour" $?
contient "feat/b ($cas/wt-b) : 1 commit(s) de retard ; fusion de main prévue : sans conflit"; verifie "--check : branche en retard sans conflit" $?
contient "feat/c ($cas/wt-c) : 1 commit(s) de retard ; fusion de main prévue : conflit sur 1 fichier(s)"; verifie "--check : branche en retard avec conflit" $?
printf '%s\n' "$SORTIE" | grep -qx "  f.txt"; verifie "--check : fichier en conflit listé en retrait" $?
! contient "spike/s" && ! contient "$cas/run" ; verifie "--check : spike et dossier d'exécution laissés de côté" $?
contient "radar des worktrees, lecture seule (référence : main "; verifie "--check : référence dite" $?
[ "$(tous)" = "$avant" ]; verifie "--check : rien n'a changé dans aucun worktree" $?
lance "$cas/wt-b" --check; code_et "--check depuis un worktree : code 0" 0 "3 worktree(s) de branche de travail"
pose_verrou "$$" feat/autre
lance "$cas/wt-b" --check; code_et "--check sous le verrou : code 0" 0 "branch_sync : fin de branche en cours (feat/autre, depuis "
contient "aucune fusion possible avant sa fin"; verifie "--check sous le verrou : phrase complète" $?
[ "$(tous)" = "$avant" ]; verifie "--check sous le verrou : rien n'a changé" $?

# --- --check sur références divergentes : code 0, une ligne par branche
nouveau; git -C "$ws" worktree add -q -b feat/b "$cas/wt-b" main
( cd "$ws" && git switch -q -c tmp && echo distant > g.txt && git commit -q -am distant && git push -q origin tmp:main 2>/dev/null \
  && git switch -q main && git branch -q -D tmp && git fetch -q origin ) || exit 1
commit_dans "$ws" h.txt "local"
tous2() { for d in "$ws" "$wt" "$cas/wt-b"; do etat "$d"; done; }
avant=$(tous2)
lance "$ws" --check; code_et "--check, références divergentes : code 0" 0 "radar des worktrees, lecture seule (références de main divergentes)"
[ "$(printf '%s\n' "$SORTIE" | grep -c "ont divergé")" -eq 2 ]; verifie "--check, références divergentes : une ligne par branche" $?
contient "feat/x ($wt) : main local et origin/main ont divergé : retard non calculé"; verifie "--check, références divergentes : phrase de la branche" $?
[ "$(tous2)" = "$avant" ]; verifie "--check, références divergentes : rien n'a changé" $?

# --- interruption : fusion lancée par l'outil annulée
nouveau; commit_dans "$ws" g.txt "main avance"; commit_dans "$wt" h.txt "branche"
mkdir -p "$cas/crochets"
cat > "$cas/crochets/commit-msg" <<'CROCHET'
#!/bin/bash
# remonte les ancêtres jusqu'à l'outil et lui envoie SIGTERM pendant sa fusion
p=$PPID
while [ -n "$p" ] && [ "$p" -gt 1 ] 2>/dev/null; do
  if ps -o command= -p "$p" 2>/dev/null | grep -qF "tools/branch_sync.sh"; then kill -TERM "$p"; break; fi
  p=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')
done
sleep 1
exit 1
CROCHET
chmod +x "$cas/crochets/commit-msg"; git -C "$ws" config core.hooksPath "$cas/crochets"; avant=$(etat "$wt")
lance "$wt"; code_et "interruption : code 143" 143 "branch_sync : interrompu (code 143)"
contient "branch_sync : fusion commencée par l'outil : annulée"; verifie "interruption : annulation dite" $?
inchange "interruption" "$wt" "$avant"
propre "$wt"; verifie "interruption : aucune fusion ne reste" $?

# --- relevé de l'outil : aucune commande interdite hors commentaires
# options globales -C chemin et -c clé=valeur, en nombre quelconque et dans n'importe quel ordre, avant la sous-commande
motif_interdits='git([[:space:]]+-[Cc][[:space:]]+[^[:space:]]+)*[[:space:]]+(push|reset|fetch|pull|checkout|switch|rebase|stash|update-ref|symbolic-ref[[:space:]]+[^-]|branch[[:space:]]+-|clean|cherry-pick|revert)|--force|--no-verify|core\.hooksPath|-c[[:space:]]+core\.'
temoins_ok=0
for temoin in 'git push' 'git -C x push' 'git -C x -c a=b push' 'git -c a=b -C x fetch' 'git -C "$TOP" -c rerere.enabled=false reset --hard'; do
  printf '%s\n' "$temoin" | grep -qE "$motif_interdits" || { temoins_ok=1; SORTIE="témoin non détecté : $temoin"; }
done
verifie "relevé : le motif détecte une sous-commande interdite après -C et -c clé=valeur" "$temoins_ok"
printf '%s\n' 'git -C "$TOP" -c rerere.enabled=false merge --no-edit' | grep -qE "$motif_interdits"; [ $? -ne 0 ]; verifie "relevé : la fusion de l'outil n'est pas un faux positif" $?
if [ -f "$script" ]; then
  interdits=$(grep -v '^[[:space:]]*#' "$script" | grep -nE "$motif_interdits")
else
  interdits="outil absent"
fi
SORTIE=$interdits; [ -z "$interdits" ]; verifie "relevé : ni push, ni reset, ni fetch, ni changement de branche, ni forçage, ni contournement de crochet" $?

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
