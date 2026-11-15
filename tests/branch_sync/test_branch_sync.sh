#!/bin/bash
# Test de l'outil radar des worktrees en retard sur main (tools/branch_sync.sh, change branch-sync) : dépôts et worktrees Git
# TEMPORAIRES, avec un dépôt distant nu ; l'outil est lancé par /bin/bash (bash 3.2 sur Mac), entrée vide, toujours dans un dossier sous $tmp.
# Réduction du 2026-10-28 (désherbage, entrée D99) : le mode par défaut et --manuel (fusion de main dans la branche) sont retirés ; leurs
# tests sont retirés avec eux, sur décision de l'auteur du 2026-10-28 (une décision par test, celle-ci). Restent : usage (lancé sans option,
# l'outil refuse et dit d'utiliser --check et « git rebase main »), aide, --check en lecture seule (hors dépôt, main introuvable, verrou d'une
# autre fin, références divergentes, spike et dossier d'exécution laissés de côté) et le relevé des commandes interdites dans l'outil.
# Lancement à la main : bash tests/branch_sync/test_branch_sync.sh </dev/null
set -u
script="$(cd "$(dirname "$0")/../../tools" && pwd)/branch_sync.sh"
BASH_OUTIL=bash; [ -x /bin/bash ] && BASH_OUTIL=/bin/bash
tmp=$(cd "$(mktemp -d)" && pwd -P) || exit 1
trap 'chmod -R u+rwX "$tmp" 2>/dev/null; rm -rf "$tmp"' EXIT
export GIT_CONFIG_GLOBAL="$tmp/gitconfig" GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0 GIT_CEILING_DIRECTORIES="$tmp"
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE FINISH_LOCK_TOKEN PMZILLA_LAB_RUN PMZILLA_FINISH_LOCK_MAX_AGE
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
pose_verrou() { # pid branche : verrou de fin dans le dossier Git commun de $ws
  v="$ws/.git/pmzilla-fin-en-cours"; mkdir -p "$v"
  printf '%s\n' "$1" > "$v/pid"; date +%s > "$v/debut"; printf '%s\n' "$2" > "$v/branche"; echo jeton-autre > "$v/jeton"
}

# --- usage et aide : sans option, l'outil refuse et ne change rien (décision du 2026-10-28)
nouveau; commit_dans "$ws" g.txt "main avance"; avant=$(etat "$wt")
lance "$wt"; code_et "sans option : code 2" 2 "branch_sync : usage : bash tools/branch_sync.sh --check"
contient "git rebase main"; verifie "sans option : la voie d'intégration par rebase est dite" $?
inchange "sans option" "$wt" "$avant"
lance "$wt" --manuel; code_et "--manuel (mode retiré) : code 2" 2 "usage"
inchange "--manuel" "$wt" "$avant"
lance "$wt" --autre; code_et "option inconnue : code 2" 2 "branch_sync : usage : bash tools/branch_sync.sh --check"
lance "$wt" feat/y; code_et "nom de branche donné : code 2" 2 "usage"
lance "$wt" --check --manuel; code_et "deux options : code 2" 2 "usage"
lance "$wt" --help; code_et "aide : code 0" 0 "Codes"
contient "--check"; verifie "aide : le radar est décrit" $?
contient "git rebase main"; verifie "aide : la règle d'intégration par rebase est dite" $?
inchange "usage et aide" "$wt" "$avant"

# --- 3 hors dépôt
mkdir -p "$tmp/hors"; lance "$tmp/hors" --check; code_et "--check hors dépôt : code 3" 3 "branch_sync : hors d'un dépôt Git : rien n'est fait"

# --- 7 main introuvable (radar)
nouveau; git -C "$ws" switch -q -c autre; git -C "$ws" branch -q -D main
lance "$ws" --check; code_et "--check, main introuvable : code 7" 7 "main introuvable"

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

# --- relevé de l'outil : aucune commande interdite hors commentaires
# options globales -C chemin et -c clé=valeur, en nombre quelconque et dans n'importe quel ordre, avant la sous-commande
motif_interdits='git([[:space:]]+-[Cc][[:space:]]+[^[:space:]]+)*[[:space:]]+(push|reset|fetch|pull|checkout|switch|rebase|stash|update-ref|symbolic-ref[[:space:]]+[^-]|branch[[:space:]]+-|clean|cherry-pick|revert|merge)|--force|--no-verify|core\.hooksPath|-c[[:space:]]+core\.'
temoins_ok=0
for temoin in 'git push' 'git -C x push' 'git -C x -c a=b push' 'git -c a=b -C x fetch' 'git -C "$TOP" -c rerere.enabled=false reset --hard' 'git -C "$TOP" merge --no-edit'; do
  printf '%s\n' "$temoin" | grep -qE "$motif_interdits" || { temoins_ok=1; SORTIE="témoin non détecté : $temoin"; }
done
verifie "relevé : le motif détecte une sous-commande interdite après -C et -c clé=valeur" "$temoins_ok"
if [ -f "$script" ]; then
  # la seule ligne qui cite « git rebase main » est la phrase d'usage, qui le conseille et ne le lance pas
  interdits=$(grep -v '^[[:space:]]*#' "$script" | grep -v '^[[:space:]]*"pour intégrer main dans une branche de travail : git rebase main, dans son worktree"$' | grep -nE "$motif_interdits")
else
  interdits="outil absent"
fi
SORTIE=$interdits; [ -z "$interdits" ]; verifie "relevé : ni push, ni reset, ni fetch, ni changement de branche, ni forçage, ni fusion, ni écriture" $?

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
