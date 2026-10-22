#!/bin/sh
# Test des crochets pre-merge-commit et reference-transaction (change finish-under-lock, design D17, tâche 5.2) dans un dépôt Git
# TEMPORAIRE : les deux crochets et tools/finish_lock.py y sont copiés, puis liés comme le fait tools/install_hooks.sh. Le verrou de fin
# est un dossier pmzilla-fin-en-cours du dossier Git commun, fait ici à la main (pid, debut, branche, jeton).
# Cas : sous un verrou vivant d'un autre jeton, un commit de fusion (pre-merge-commit), une avance rapide, un reset --hard et un update-ref
# de main (reference-transaction) sont refusés, main inchangé, avec la phrase exacte ; les mêmes passent avec le jeton du verrou ; une autre
# branche bouge sous le verrou ; sans dossier de verrou tout passe ; un verrou périmé est dit puis tout passe.
# Lancement : sh tests/hooks/test_lock_hooks.sh
set -u
RACINE=$(cd "$(dirname "$0")/../.." && pwd -P)
tmp=$(cd "$(mktemp -d)" && pwd -P) || exit 1
trap 'rm -rf "$tmp"' EXIT
export GIT_CONFIG_GLOBAL="$tmp/gitconfig" GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0 GIT_CEILING_DIRECTORIES="$tmp"
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE FINISH_LOCK_TOKEN PMZILLA_FINISH_LOCK_MAX_AGE
git config --global user.email t@example.org
git config --global user.name test
git config --global init.defaultBranch main
ok=0; ko=0
verifie() { # description condition-vraie (0 = vrai)
  if [ "$2" -eq 0 ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1 :: $SORTIE"; ko=$((ko+1)); fi
}
contient() { printf '%s' "$SORTIE" | grep -qF -- "$1"; }

L_FUSION="pre-merge-commit : fin de branche en cours (feat/autre), fusion refusée"
L_MAIN="reference-transaction : fin de branche en cours (feat/autre), mise à jour de main refusée"
L_PERIME_FUSION="pre-merge-commit : verrou de fin périmé, ignoré"
L_PERIME_MAIN="reference-transaction : verrou de fin périmé, ignoré"

n=0
nouveau() { # dépôt $depot sur main, avec les deux crochets liés ; main a un commit de plus que sa base, feat/x un commit à elle
  n=$((n+1)); depot="$tmp/cas$n"; mkdir -p "$depot/tools/hooks"
  cp "$RACINE/tools/finish_lock.py" "$depot/tools/"
  cp "$RACINE/tools/hooks/pre-merge-commit" "$RACINE/tools/hooks/reference-transaction" "$depot/tools/hooks/" 2>/dev/null
  ( cd "$depot" && git init -q . && echo base > f.txt && git add -A && git commit -q -m base \
    && git switch -q -c feat/x && echo b > b.txt && git add b.txt && git commit -q -m branche \
    && git switch -q main && echo m > m.txt && git add m.txt && git commit -q -m "main avance" ) || exit 1
  mkdir -p "$depot/.git/hooks"
  for h in pre-merge-commit reference-transaction; do ln -s "../../tools/hooks/$h" "$depot/.git/hooks/$h"; done
  base=$(git -C "$depot" rev-parse main~1)
}
pose_verrou() { # pid jeton [âge en secondes]
  mkdir -p "$depot/.git/pmzilla-fin-en-cours"
  ( cd "$depot/.git/pmzilla-fin-en-cours" && echo "$1" > pid && echo $(( $(date +%s) - ${3:-0} )) > debut && echo feat/autre > branche && echo "$2" > jeton )
}
lance() { # commande… dans le dépôt : sortie et code dans SORTIE et CODE
  SORTIE=$(cd "$depot" && "$@" 2>&1 </dev/null); CODE=$?
}
main_est() { [ "$(git -C "$depot" rev-parse main)" = "$1" ]; }

# --- verrou vivant d'un autre jeton : tout déplacement de main et tout commit de fusion sont refusés
nouveau; pose_verrou $$ jeton-du-verrou; avant=$(git -C "$depot" rev-parse main)
lance git merge --no-ff --no-edit feat/x
[ "$CODE" -ne 0 ] && contient "$L_FUSION" && main_est "$avant"; verifie "verrou vivant : commit de fusion refusé par pre-merge-commit, main inchangé" $?
nouveau; pose_verrou $$ jeton-du-verrou
git -C "$depot" switch -q feat/x; git -C "$depot" reset -q --hard main >/dev/null 2>&1   # sous le verrou : une autre branche bouge
git -C "$depot" commit -q --allow-empty -m "devant main"; git -C "$depot" switch -q main; avant=$(git -C "$depot" rev-parse main)
lance git merge --ff-only feat/x
[ "$CODE" -ne 0 ] && contient "$L_MAIN" && main_est "$avant"; verifie "verrou vivant : avance rapide de main refusée par reference-transaction" $?
lance git reset --hard "$base"
[ "$CODE" -ne 0 ] && contient "$L_MAIN" && main_est "$avant"; verifie "verrou vivant : reset --hard de main refusé" $?
lance git update-ref refs/heads/main "$base"
[ "$CODE" -ne 0 ] && contient "$L_MAIN" && main_est "$avant"; verifie "verrou vivant : update-ref de main refusé" $?
lance git update-ref refs/heads/feat/x "$base"
[ "$CODE" -eq 0 ] && [ "$(git -C "$depot" rev-parse feat/x)" = "$base" ] && ! contient "refusée"; verifie "verrou vivant : une autre branche bouge (update-ref)" $?
lance git branch autre "$base"
[ "$CODE" -eq 0 ]; verifie "verrou vivant : une nouvelle branche est créée" $?
FINISH_LOCK_TOKEN=jeton-different; export FINISH_LOCK_TOKEN
lance git update-ref refs/heads/main "$base"
[ "$CODE" -ne 0 ] && main_est "$avant"; verifie "verrou vivant : un autre jeton ne passe pas" $?
unset FINISH_LOCK_TOKEN

# --- le jeton du verrou : les mêmes gestes passent
nouveau; pose_verrou $$ jeton-du-verrou; FINISH_LOCK_TOKEN=jeton-du-verrou; export FINISH_LOCK_TOKEN
lance git merge --no-ff --no-edit feat/x
[ "$CODE" -eq 0 ] && ! main_est "$(git -C "$depot" rev-parse main~1)" ; verifie "jeton du verrou : commit de fusion accepté" $?
git -C "$depot" rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1; [ $? -ne 0 ]; verifie "jeton du verrou : aucune fusion en cours après le commit" $?
lance git reset --hard "$base"
[ "$CODE" -eq 0 ] && main_est "$base"; verifie "jeton du verrou : reset --hard de main accepté" $?
lance git merge --ff-only feat/x
[ "$CODE" -eq 0 ] && main_est "$(git -C "$depot" rev-parse feat/x)"; verifie "jeton du verrou : avance rapide de main acceptée" $?
lance git update-ref refs/heads/main "$base"
[ "$CODE" -eq 0 ] && main_est "$base"; verifie "jeton du verrou : update-ref de main accepté" $?
unset FINISH_LOCK_TOKEN

# --- sans dossier de verrou : tout passe, sans aucune ligne des crochets
nouveau
lance git merge --no-ff --no-edit feat/x
[ "$CODE" -eq 0 ] && ! contient "pre-merge-commit" && ! contient "reference-transaction"; verifie "sans verrou : commit de fusion accepté, aucune ligne" $?
lance git update-ref refs/heads/main "$base"
[ "$CODE" -eq 0 ] && main_est "$base" && [ -z "$SORTIE" ]; verifie "sans verrou : update-ref de main accepté, aucune ligne" $?

# --- verrou périmé (processus mort) : la ligne dédiée, puis le geste passe
nouveau; mort=$(sh -c 'echo $$'); pose_verrou "$mort" jeton-perime
lance git merge --no-ff --no-edit feat/x
[ "$CODE" -eq 0 ] && contient "$L_PERIME_FUSION"; verifie "verrou périmé : commit de fusion accepté avec la ligne de pre-merge-commit" $?
lance git update-ref refs/heads/main "$base"
[ "$CODE" -eq 0 ] && main_est "$base" && contient "$L_PERIME_MAIN"; verifie "verrou périmé : update-ref de main accepté avec la ligne de reference-transaction" $?
# verrou trop vieux (processus vivant, âge au-delà du maximum) : périmé aussi
nouveau; PMZILLA_FINISH_LOCK_MAX_AGE=60; export PMZILLA_FINISH_LOCK_MAX_AGE; pose_verrou $$ jeton-vieux 120
lance git update-ref refs/heads/main "$base"
[ "$CODE" -eq 0 ] && main_est "$base" && contient "$L_PERIME_MAIN"; verifie "verrou plus vieux que le maximum : update-ref de main accepté avec la ligne" $?
unset PMZILLA_FINISH_LOCK_MAX_AGE

# --- relecture Opus du 2026-10-20 : référence exacte, état « prepared » seulement, aucun Python sans verrou, worktree lié, pack-refs
nouveau; pose_verrou $$ jeton-du-verrou
lance git update-ref refs/heads/main2 "$base"
[ "$CODE" -eq 0 ] && ! contient "refusée"; verifie "verrou vivant : refs/heads/main2 bouge (référence exacte refs/heads/main seulement)" $?
lance git update-ref refs/remotes/origin/main "$base"
[ "$CODE" -eq 0 ] && ! contient "refusée"; verifie "verrou vivant : refs/remotes/origin/main bouge (le fetch reste permis)" $?
avant=$(git -C "$depot" rev-parse main)
git -C "$depot" switch -q feat/x
lance git update-ref -d refs/heads/main
[ "$CODE" -ne 0 ] && contient "$L_MAIN" && main_est "$avant"; verifie "verrou vivant : la suppression de main est refusée" $?
git -C "$depot" switch -q main
lance git pack-refs --all   # limite écrite : le rangement de main est refusé sous le verrou, main reste
main_est "$avant" && git -C "$depot" rev-parse -q --verify refs/heads/main >/dev/null; verifie "verrou vivant : git pack-refs ne change pas main (rangement refusé, limite écrite)" $?
for etat in committed aborted; do
  SORTIE=$(cd "$depot" && printf '%s %s refs/heads/main\n' "$base" "$avant" | sh .git/hooks/reference-transaction "$etat" 2>&1); CODE=$?
  [ "$CODE" -eq 0 ] && [ -z "$SORTIE" ]; verifie "verrou vivant : état « $etat », le crochet sort 0 sans rien dire" $?
done
SORTIE=$(cd "$depot" && printf '%s %s refs/heads/main\n' "$base" "$avant" | sh .git/hooks/reference-transaction prepared 2>&1); CODE=$?
[ "$CODE" -ne 0 ] && contient "$L_MAIN"; verifie "verrou vivant : état « prepared » sur refs/heads/main, refus" $?
git -C "$depot" worktree add -q "$tmp/lie$n" feat/x 2>/dev/null
SORTIE=$(cd "$tmp/lie$n" && git update-ref refs/heads/main "$base" 2>&1); CODE=$?
[ "$CODE" -ne 0 ] && contient "$L_MAIN" && main_est "$avant"; verifie "verrou vivant : depuis un worktree lié, update-ref de main refusé" $?
nouveau; mkdir -p "$tmp/faux-python$n"
printf '#!/bin/sh\necho appel > "%s/python-lance"\nexit 0\n' "$tmp/faux-python$n" > "$tmp/faux-python$n/python3"; chmod +x "$tmp/faux-python$n/python3"
SORTIE=$(cd "$depot" && PATH="$tmp/faux-python$n:$PATH" git update-ref refs/heads/main "$base" 2>&1); CODE=$?
[ "$CODE" -eq 0 ] && [ ! -e "$tmp/faux-python$n/python-lance" ]; verifie "sans verrou : reference-transaction ne lance pas Python" $?

# --- les crochets eux-mêmes : POSIX sh pour reference-transaction, aucune variable de contournement
SORTIE=$(head -1 "$RACINE/tools/hooks/reference-transaction" 2>&1); [ "$SORTIE" = "#!/bin/sh" ]; verifie "reference-transaction : POSIX sh" $?
SORTIE=$(grep -n "PMZILLA_SKIP_GREEN_CHECK\|--no-verify" "$RACINE/tools/hooks/pre-merge-commit" "$RACINE/tools/hooks/reference-transaction" 2>&1); [ -z "$SORTIE" ]; verifie "aucune variable de contournement dans les deux crochets" $?
SORTIE="mode"; [ -x "$RACINE/tools/hooks/pre-merge-commit" ] && [ -x "$RACINE/tools/hooks/reference-transaction" ]; verifie "les deux crochets sont exécutables" $?

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
