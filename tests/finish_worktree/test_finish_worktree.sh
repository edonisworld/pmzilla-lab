#!/bin/bash
# Test du script de fin de branche depuis un worktree (tools/finish_worktree.sh) : dépôts et worktrees Git TEMPORAIRES,
# script de fin factice (FINISH_WORKTREE_FINISH) qui note la branche et le dossier où il tourne et sort avec le code voulu.
# Cas : aide (0) ; chaque code 20 à 30 avec sa phrase ; 31 (verrou d'index du workspace, la bascule échoue après le retrait) ;
# liste des worktrees, branche du workspace et fichiers du worktree inchangés sur 20 à 29 ; réglage local et caches non bloquants ;
# succès (le faux script tourne dans le workspace, sur la branche, entrée vide) ; codes 0, 1, 9, 10, 11, 12, 13 transmis, conseil
# de recréation seulement pour 1 à 9 ; lancement depuis un autre worktree ; scan du script (hors commentaires) des commandes interdites.
# Jamais le vrai espace de travail ni le vrai script de fin : chaque lancement se fait dans un dépôt sous $tmp (garde-fou dans lance()).
# Lancement à la main : bash tests/finish_worktree/test_finish_worktree.sh </dev/null
set -u
script="$(cd "$(dirname "$0")/../../tools" && pwd)/finish_worktree.sh"
tmp=$(cd "$(mktemp -d)" && pwd -P) || exit 1
trap 'chmod -R u+rwX "$tmp" 2>/dev/null; rm -rf "$tmp"' EXIT
export GIT_CONFIG_GLOBAL="$tmp/gitconfig" GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0 GIT_CEILING_DIRECTORIES="$tmp"
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE
git config --global user.email t@example.org
git config --global user.name test
git config --global init.defaultBranch main
ok=0; ko=0; n=0
SORTIE=""; CODE=0

verifie() { # description condition-vraie (0 = vrai)
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

# Faux script de fin : note la branche et le dossier courant, lit l'entrée standard, sort avec $FAKE_CODE.
faux="$tmp/faux_fin.sh"
cat > "$faux" <<'FAUX'
#!/bin/bash
{
  git rev-parse --abbrev-ref HEAD
  pwd -P
  printf 'entree:%s\n' "$(cat)"
} > "$FAKE_TRACE"
echo "faux : fin lancée"
exit "${FAKE_CODE:-0}"
FAUX
export FINISH_WORKTREE_FINISH="bash $faux" FAKE_TRACE="$tmp/trace" FAKE_CODE=0

nouveau() { # espace de travail temporaire $tmp/casN/espace, sur main, avec .gitignore ; $wt = worktree de feat/x
  n=$((n+1)); cas="$tmp/cas$n"; ws="$cas/espace"
  mkdir -p "$ws"; git init -q "$ws"; cd "$ws" || exit 1
  echo base > f.txt
  printf '.claude/settings.local.json\n__pycache__/\n*.pyc\n.DS_Store\nsortie/\n' > .gitignore
  git add -A; git commit -q -m initial
  rm -f "$FAKE_TRACE"
  wt="$cas/wt-feat-x"
}
avec_worktree() { git -C "$ws" worktree add -q -b feat/x "$wt" main; }
lance() { # [dossier] -- arguments : lance le script depuis le dossier (défaut : le workspace), jamais hors de $tmp
  dossier=$ws
  if [ "${1:-}" != "--" ]; then dossier=$1; shift; fi
  shift
  case "$dossier" in "$tmp"/*) ;; *) echo "garde-fou : $dossier hors de $tmp" >&2; exit 1 ;; esac
  rm -f "$FAKE_TRACE"
  SORTIE=$(cd "$dossier" && bash "$script" "$@" 2>&1 </dev/null); CODE=$?
}
etat() { # liste des worktrees, branche du workspace, fichiers du worktree
  git -C "$ws" worktree list --porcelain; git -C "$ws" rev-parse --abbrev-ref HEAD
  if [ -d "$wt" ]; then (cd "$wt" && find . -path ./.git -prune -o -print | sort); fi
}
inchange() { # description état-avant : état identique, faux script non lancé
  [ "$(etat)" = "$2" ] && [ ! -e "$FAKE_TRACE" ]; verifie "$1 : worktrees, branche du workspace et fichiers inchangés, rien lancé" $?
}

# --- aide
nouveau; avec_worktree; avant=$(etat); lance -- --help
code_et "aide : code 0 et usage" 0 "finish_worktree : usage : bash tools/finish_worktree.sh <branche> [--help]"
for c in 20 21 22 23 24 25 26 27 28 29 30 31; do
  contient " $c "; verifie "aide : le code $c est décrit" $?
done
inchange "aide" "$avant"

# --- 20 usage
nouveau; avec_worktree; avant=$(etat)
lance --; code_et "sans argument : code 20" 20 "usage : bash tools/finish_worktree.sh <branche>"
lance -- feat/x autre; code_et "deux arguments : code 20" 20 "usage : bash tools/finish_worktree.sh <branche>"
lance -- --inconnue; code_et "option inconnue : code 20" 20 "usage : bash tools/finish_worktree.sh <branche>"
lance -- --help feat/x; code_et "aide avec un argument de plus : code 20" 20 "usage"
inchange "usage" "$avant"

# --- 21 hors du dépôt
mkdir -p "$tmp/hors"; lance "$tmp/hors" -- feat/x
code_et "hors du dépôt : code 21" 21 "hors du dépôt"

# --- 22 main, spike
nouveau; avec_worktree; avant=$(etat)
lance -- main; code_et "main : code 22" 22 "aucune branche à terminer"
lance -- spike/idee; code_et "branche spike/* : code 22" 22 "aucune branche à terminer"
inchange "22" "$avant"

# --- 23 branche introuvable
nouveau; avec_worktree; avant=$(etat)
lance -- fantome; code_et "branche inconnue : code 23" 23 "branche fantome introuvable"
inchange "23" "$avant"

# --- 24 workspace pas sur main
nouveau; avec_worktree; git checkout -q -b autre; avant=$(etat)
lance -- feat/x; code_et "workspace sur une autre branche : code 24" 24 "l'espace de travail n'est pas sur main"
inchange "24 (branche)" "$avant"
nouveau; avec_worktree; git checkout -q --detach; avant=$(etat)
lance -- feat/x; code_et "workspace en tête détachée : code 24" 24 "l'espace de travail n'est pas sur main"
inchange "24 (détachée)" "$avant"

# --- 25 workspace pas propre
nouveau; avec_worktree; echo x > nouveau.txt; avant=$(etat)
lance -- feat/x; code_et "workspace avec fichier non suivi : code 25" 25 "l'espace de travail n'est pas propre"
inchange "25 (non suivi)" "$avant"
nouveau; avec_worktree; echo y >> f.txt; avant=$(etat)
lance -- feat/x; code_et "workspace avec fichier modifié : code 25" 25 "l'espace de travail n'est pas propre"
inchange "25 (modifié)" "$avant"
nouveau; avec_worktree; echo y >> f.txt; git add f.txt; avant=$(etat)
lance -- feat/x; code_et "workspace avec fichier indexé : code 25" 25 "l'espace de travail n'est pas propre"
inchange "25 (indexé)" "$avant"

# --- 26 aucun worktree pour la branche, ou dossier absent
nouveau; git branch feat/x; avant=$(etat)
lance -- feat/x; code_et "aucun worktree : code 26 et branche nommée" 26 "aucun worktree pour la branche feat/x"
contient "git switch feat/x" && contient "bash tools/finish_branch.sh"; verifie "26 : le conseil git switch puis finish_branch" $?
inchange "26 (aucun worktree)" "$avant"
nouveau; avec_worktree; rm -rf "$wt"; avant=$(etat)
lance -- feat/x; code_et "dossier du worktree absent : code 26" 26 "dossier du worktree absent : $wt"
inchange "26 (dossier absent)" "$avant"
nouveau; git worktree add -q --detach "$cas/arbre-detache" main; git branch feat/x; avant=$(etat)
lance -- feat/x; code_et "worktree détaché : ne correspond à aucune branche, code 26" 26 "aucun worktree pour la branche feat/x"
inchange "26 (détaché)" "$avant"

# --- 27 lancé depuis le worktree à retirer
nouveau; avec_worktree; mkdir -p "$wt/sous/dossier"; avant=$(etat)
lance "$wt" -- feat/x; code_et "lancé depuis le worktree : code 27" 27 "lance le script depuis l'espace de travail"
lance "$wt/sous/dossier" -- feat/x; code_et "lancé depuis un sous-dossier du worktree : code 27" 27 "lance le script depuis l'espace de travail"
inchange "27" "$avant"

# --- 28 worktree pas propre
nouveau; avec_worktree; echo x > "$wt/nouveau.txt"; avant=$(etat)
lance -- feat/x; code_et "worktree avec fichier non suivi : code 28" 28 "le worktree n'est pas propre"
inchange "28 (non suivi)" "$avant"
nouveau; avec_worktree; echo y >> "$wt/f.txt"; avant=$(etat)
lance -- feat/x; code_et "worktree avec fichier modifié : code 28" 28 "le worktree n'est pas propre"
inchange "28 (modifié)" "$avant"
nouveau; avec_worktree; echo y >> "$wt/f.txt"; git -C "$wt" add f.txt; avant=$(etat)
lance -- feat/x; code_et "worktree avec fichier indexé : code 28" 28 "le worktree n'est pas propre"
inchange "28 (indexé)" "$avant"

# --- 29 fichiers ignorés qui seraient perdus
nouveau; avec_worktree; mkdir -p "$wt/sortie/rapports"; echo secret > "$wt/sortie/rapports/livrable-prive.md"; echo 1 > "$wt/sortie/autre.txt"; avant=$(etat)
lance -- feat/x; code_et "livrable ignoré : code 29" 29 "fichiers ignorés qui seraient perdus"
contient "2" && contient "sortie"; verifie "29 : le nombre et le dossier de premier niveau" $?
! contient "livrable-prive" && ! contient "autre.txt" && ! contient "secret"; verifie "29 : ni nom de fichier ni contenu" $?
[ -f "$wt/sortie/rapports/livrable-prive.md" ]; verifie "29 : le fichier ignoré est toujours là" $?
inchange "29" "$avant"
nouveau; avec_worktree; echo z > "$wt/racine-ignoree.bak"; printf 'racine-ignoree.bak\n' >> "$ws/.git/info/exclude"; avant=$(etat)
lance -- feat/x; code_et "fichier ignoré à la racine : code 29" 29 "fichiers ignorés qui seraient perdus"
inchange "29 (racine)" "$avant"

# --- réglage local et caches : ne bloquent pas
nouveau; avec_worktree
mkdir -p "$wt/.claude" "$wt/tools/__pycache__"; echo '{}' > "$wt/.claude/settings.local.json"; echo c > "$wt/tools/__pycache__/m.cpython-312.pyc"
echo c > "$wt/m.pyc"; echo c > "$wt/.DS_Store"
FAKE_CODE=0; lance -- feat/x
code_et "réglage local, caches, .pyc et .DS_Store seuls : le contrôle passe" 0 "worktree retiré"

# --- succès
nouveau; avec_worktree; FAKE_CODE=0
rm -f "$FAKE_TRACE"; SORTIE=$(cd "$ws" && echo intrus | bash "$script" feat/x 2>&1); CODE=$?
code_et "succès : code 0" 0 "finish_worktree : worktree retiré : $wt"
contient "finish_worktree : espace de travail sur la branche feat/x"; verifie "succès : message de bascule" $?
contient "faux : fin lancée"; verifie "succès : la sortie du script de fin suit" $?
[ ! -e "$wt" ] && ! git -C "$ws" worktree list | grep -qF "$wt"; verifie "succès : le dossier du worktree n'existe plus et n'est plus listé" $?
[ "$(sed -n 1p "$FAKE_TRACE")" = "feat/x" ]; verifie "succès : le faux script tourne sur la branche" $?
[ "$(sed -n 2p "$FAKE_TRACE")" = "$ws" ]; verifie "succès : le faux script tourne dans le workspace" $?
[ "$(sed -n 3p "$FAKE_TRACE")" = "entree:" ]; verifie "succès : entrée standard vide pour le script de fin" $?
! contient "la fin de branche a rendu le code"; verifie "succès : pas de ligne d'échec" $?
[ "$(git -C "$ws" rev-parse --abbrev-ref HEAD)" = "feat/x" ]; verifie "succès : le workspace reste sur la branche" $?

# --- worktree dans un dossier au nom libre
nouveau; wt="$cas/dossier libre"; git worktree add -q -b feat/x "$wt" main; FAKE_CODE=0; lance -- feat/x
code_et "worktree dans un dossier au nom libre : retiré" 0 "worktree retiré : $wt"
[ ! -e "$wt" ]; verifie "nom libre : dossier supprimé" $?

# --- lancé depuis un autre worktree
nouveau; avec_worktree; git worktree add -q -b feat/y "$cas/wt-feat-y" main; FAKE_CODE=0
lance "$cas/wt-feat-y" -- feat/x
code_et "lancé depuis un autre worktree : code 0" 0 "worktree retiré"
[ ! -e "$wt" ] && [ -d "$cas/wt-feat-y" ]; verifie "autre worktree : celui de la branche est retiré, l'autre reste" $?
[ "$(sed -n 2p "$FAKE_TRACE")" = "$ws" ] && [ "$(sed -n 1p "$FAKE_TRACE")" = "feat/x" ]; verifie "autre worktree : le faux script tourne dans le workspace, sur la branche" $?

# --- codes du script de fin transmis
for c in 0 1 9 10 11 12 13; do
  nouveau; avec_worktree; FAKE_CODE=$c; lance -- feat/x
  code_et "code $c du script de fin transmis" "$c"
  if [ "$c" -ne 0 ]; then
    contient "finish_worktree : la fin de branche a rendu le code $c ; le worktree de feat/x est retiré"; verifie "code $c : ligne d'état" $?
  fi
  [ ! -e "$wt" ]; verifie "code $c : le worktree reste retiré (aucun retour en arrière)" $?
  [ "$(git -C "$ws" rev-parse --abbrev-ref HEAD)" = "feat/x" ]; verifie "code $c : le workspace reste sur la branche, sans bascule retour" $?
  case $c in
    1|9) contient "pour reprendre dans un worktree : git switch main && bash tools/worktree.sh feat/x"; verifie "code $c : conseil de recréation" $? ;;
    *)   ! contient "worktree.sh"; verifie "code $c : aucun conseil de recréation" $? ;;
  esac
done
FAKE_CODE=0

# --- 30 retrait impossible (worktree verrouillé)
nouveau; avec_worktree; git -C "$ws" worktree lock "$wt"; avant=$(etat)
lance -- feat/x; code_et "worktree verrouillé : code 30" 30 "retrait du worktree impossible"
contient "git worktree list"; verifie "30 : renvoie à git worktree list" $?
inchange "30" "$avant"
[ "$(git -C "$ws" rev-parse --abbrev-ref HEAD)" = "main" ]; verifie "30 : le workspace est resté sur main" $?

# --- 31 bascule impossible après le retrait (verrou d'index dans le workspace : status passe, switch échoue)
nouveau; avec_worktree; : > "$ws/.git/index.lock"
lance -- feat/x
code_et "bascule impossible après retrait : code 31" 31 "bascule de l'espace de travail impossible"
[ ! -e "$wt" ]; verifie "31 : le worktree est retiré" $?
contient "bash tools/worktree.sh feat/x"; verifie "31 : donne la commande de recréation" $?
[ ! -e "$FAKE_TRACE" ]; verifie "31 : le script de fin n'est pas lancé" $?
rm -f "$ws/.git/index.lock"
[ "$(git -C "$ws" rev-parse --abbrev-ref HEAD)" = "main" ]; verifie "31 : le workspace est sur main" $?

# --- scan du script, hors commentaires
code_script=$(grep -v '^[[:space:]]*#' "$script")
for interdit in '--no-verify' '--force' ' -f ' 'prune' 'push' 'merge' 'reset' 'stash' 'PMZILLA_SKIP_GREEN_CHECK' 'PMZILLA_NO_EVALS' 'BYPASS' 'finish_branch.sh --'; do
  ! printf '%s\n' "$code_script" | grep -qF -- "$interdit"; SORTIE="« $interdit » trouvé"; verifie "le script ne contient pas « $interdit »" $?
done
! printf '%s\n' "$code_script" | grep -E 'git[^|;&]* (commit|branch -[dD]|checkout|rm )' >/dev/null; SORTIE="commande interdite"; verifie "le script ne valide, ne supprime ni ne checkout" $?
printf '%s\n' "$code_script" | grep -qF '</dev/null'; SORTIE="entrée non fermée"; verifie "le script de fin est lancé avec </dev/null" $?
grep -qF 'tools/finish_branch.sh' "$script"; SORTIE="finish_branch absent"; verifie "le script de fin par défaut est tools/finish_branch.sh" $?

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
