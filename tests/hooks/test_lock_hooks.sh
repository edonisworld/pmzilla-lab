#!/bin/sh
# Test des crochets pre-merge-commit et reference-transaction (change finish-under-lock, design D17, tâche 5.2) dans un dépôt Git
# TEMPORAIRE : les deux crochets et tools/finish_lock.py y sont copiés, puis liés comme le fait tools/install_hooks.sh. Le verrou de fin
# est un dossier pmzilla-fin-en-cours du dossier Git commun, fait ici à la main (pid, debut, branche, jeton).
# Cas : sous un verrou vivant d'un autre jeton, un commit de fusion (pre-merge-commit), une avance rapide, un reset --hard et un update-ref
# de main (reference-transaction) sont refusés, main inchangé, avec la phrase exacte ; les mêmes passent avec le jeton du verrou ; une autre
# branche bouge sous le verrou ; sans dossier de verrou tout passe ; un verrou dont le processus est mort est dit puis tout passe ; un verrou périmé par l'âge dont le processus vit refuse (A-42 de #629).
# Lancement : sh tests/hooks/test_lock_hooks.sh
set -u
RACINE=$(cd "$(dirname "$0")/../.." && pwd -P)
tmp=$(cd "$(mktemp -d)" && pwd -P) || exit 1
trap 'rm -rf "$tmp"' EXIT
export GIT_CONFIG_GLOBAL="$tmp/gitconfig" GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0 GIT_CEILING_DIRECTORIES="$tmp"
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE FINISH_LOCK_TOKEN PMZILLA_FINISH_LOCK_MAX_AGE
# le test tourne parfois dans une session Claude Code : le marqueur de session est retiré ici (garde de session de reference-transaction,
# R-148 u13), puis posé commande par commande dans la dernière section ; les cas du verrou se jouent hors session
unset CLAUDECODE
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
# verrou trop vieux (processus vivant, âge au-delà du maximum) : périmé, mais rien ne prouve que la fin a disparu (A-42 de #629) : refusé
nouveau; PMZILLA_FINISH_LOCK_MAX_AGE=60; export PMZILLA_FINISH_LOCK_MAX_AGE; pose_verrou $$ jeton-vieux 120; avant=$(git -C "$depot" rev-parse main)
lance git update-ref refs/heads/main "$base"
[ "$CODE" -ne 0 ] && main_est "$avant" && contient "reference-transaction : vérification impossible"; verifie "verrou plus vieux que le maximum, processus vivant : update-ref de main refusé (vérification impossible), main inchangé" $?
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

# --- garde de session (R-148, u13) : marqueur de session posé, aucun geste ne déplace refs/heads/main ; hors session les mêmes passent
L_SESSION="intégrer main : git rebase main dans le worktree de la branche ; main n'avance que par une fin de l'auteur"
# nom|branche d'où lancer|commande (évaluée dans le dépôt ; $base, feat/x)
gestes='rebase sur main (main checkoutée)|main|git rebase feat/x
reset --hard|main|git reset -q --hard $base
update-ref refs/heads/main|main|git update-ref refs/heads/main $base
cherry-pick sur main|main|git cherry-pick feat/x
branch -f main|feat/x|git branch -f main $base
checkout -B main|feat/x|git checkout -q -B main $base
switch -C main|feat/x|git switch -q -C main $base
suppression de main|feat/x|git update-ref -d refs/heads/main
branch -M x main|feat/x|git branch -q -M feat/x main
fetch . +x:main|feat/x|git fetch -q . +feat/x:main
fetch origine +main:main|feat/x|git fetch -q $tmp/origine +main:main
commit sur main|main|git commit -q --allow-empty -m sur-main
update-ref depuis un worktree lié|main|sh -c "git worktree add -q ../lw$n feat/x && git -C ../lw$n update-ref refs/heads/main $base"'
mkdir -p "$tmp/origine"; ( cd "$tmp/origine" && git init -q . && echo o > o.txt && git add o.txt && git commit -q -m origine )
OLDIFS=$IFS; IFS='
'
for ligne in $gestes; do
  IFS=$OLDIFS
  nom=${ligne%%|*}; reste=${ligne#*|}; branche=${reste%%|*}; cmd=${reste#*|}
  nouveau; git -C "$depot" switch -q "$branche"; avant=$(git -C "$depot" rev-parse main)
  eval "lance env CLAUDECODE=1 $cmd"
  [ "$CODE" -ne 0 ] && contient "$L_SESSION" && main_est "$avant"; verifie "session : $nom refusé avec la voie permise, main inchangée" $?
  nouveau; git -C "$depot" switch -q "$branche"; avant=$(git -C "$depot" rev-parse main)
  eval "lance env -u CLAUDECODE $cmd"
  [ "$CODE" -eq 0 ] && [ "$(git -C "$depot" rev-parse -q --verify refs/heads/main)" != "$avant" ]; verifie "hors session : $nom passe, main bouge" $?
  IFS='
'
done
IFS=$OLDIFS
nouveau; avant=$(git -C "$depot" rev-parse main)
lance env CLAUDECODE= git update-ref refs/heads/main "$base"
[ "$CODE" -ne 0 ] && contient "$L_SESSION" && main_est "$avant"; verifie "session : marqueur posé mais vide, update-ref de main refusé" $?
# les autres références ne sont jamais touchées par la garde
nouveau; git -C "$depot" switch -q feat/x
lance env CLAUDECODE=1 git commit -q --allow-empty -m "sur la branche de travail"
[ "$CODE" -eq 0 ]; verifie "session : un commit sur une branche de travail passe" $?
lance env CLAUDECODE=1 git rebase main
[ "$CODE" -eq 0 ] && git -C "$depot" merge-base --is-ancestor main feat/x; verifie "session : le rebase d'une branche de travail sur main passe, main inchangée" $?
lance env CLAUDECODE=1 git update-ref refs/stash "$base"
[ "$CODE" -eq 0 ]; verifie "session : refs/stash bouge" $?
lance env CLAUDECODE=1 git branch autre "$base"
[ "$CODE" -eq 0 ]; verifie "session : une nouvelle branche est créée" $?
mkdir -p "$tmp/sib$n"; ( cd "$tmp/sib$n" && git init -q . && echo s > s.txt && git add s.txt && git commit -q -m sib )
lance env CLAUDECODE=1 git fetch -q "$tmp/sib$n" main:refs/remotes/origin/main
[ "$CODE" -eq 0 ] && [ "$(git -C "$depot" rev-parse refs/remotes/origin/main)" = "$(git -C "$tmp/sib$n" rev-parse main)" ]; verifie "session : le fetch qui met à jour origin/main passe" $?
# en session, le jeton du verrou ne passe pas (une session pourrait le lire et le passer) : même message que sans verrou, quel que soit le jeton
nouveau; pose_verrou $$ jeton-du-verrou; avant=$(git -C "$depot" rev-parse main)
lance env CLAUDECODE=1 FINISH_LOCK_TOKEN=jeton-du-verrou git update-ref refs/heads/main "$base"
[ "$CODE" -ne 0 ] && contient "$L_SESSION" && main_est "$avant"; verifie "session + jeton du verrou : update-ref de main refusé (le jeton ne vaut que hors session)" $?
lance env CLAUDECODE=1 FINISH_LOCK_TOKEN=jeton-du-verrou git reset -q --hard "$base"
[ "$CODE" -ne 0 ] && contient "$L_SESSION" && main_est "$avant"; verifie "session + jeton du verrou : reset --hard de main refusé" $?
lance env CLAUDECODE=1 FINISH_LOCK_TOKEN=jeton-different git update-ref refs/heads/main "$base"
[ "$CODE" -ne 0 ] && contient "$L_SESSION" && ! contient "fin de branche en cours" && main_est "$avant"; verifie "session + autre jeton : message de session avec la voie permise" $?
lance env -u CLAUDECODE FINISH_LOCK_TOKEN=jeton-du-verrou git update-ref refs/heads/main "$base"
[ "$CODE" -eq 0 ] && main_est "$base"; verifie "hors session + jeton du verrou : update-ref de main accepté" $?
nouveau; mort=$(sh -c 'echo $$'); pose_verrou "$mort" jeton-perime; avant=$(git -C "$depot" rev-parse main)
lance env CLAUDECODE=1 FINISH_LOCK_TOKEN=jeton-perime git update-ref refs/heads/main "$base"
[ "$CODE" -ne 0 ] && contient "$L_SESSION" && main_est "$avant"; verifie "session + verrou périmé : refusé (la session ne passe pas)" $?
nouveau; mkdir -p "$tmp/faux-python$n"
printf '#!/bin/sh\necho appel > "%s/python-lance"\nexit 0\n' "$tmp/faux-python$n" > "$tmp/faux-python$n/python3"; chmod +x "$tmp/faux-python$n/python3"
lance env CLAUDECODE=1 PATH="$tmp/faux-python$n:$PATH" git update-ref refs/heads/main "$base"
[ "$CODE" -ne 0 ] && [ ! -e "$tmp/faux-python$n/python-lance" ]; verifie "session sans verrou : refus sans lancer Python" $?
# limite déclarée, comportement réel constaté : git branch -C x main (copie de branche sur une main existante) écrit la référence hors transaction,
# le crochet n'est pas appelé ; il passe donc en session et main bouge (aucune règle du crochet ne peut l'arrêter)
nouveau; git -C "$depot" switch -q feat/x; avant=$(git -C "$depot" rev-parse main)
lance env CLAUDECODE=1 git branch -q -C feat/x main
[ "$CODE" -eq 0 ] && ! main_est "$avant" && [ "$(git -C "$depot" rev-parse main)" = "$(git -C "$depot" rev-parse feat/x)" ]; verifie "session : git branch -C x main passe et main bouge (limite déclarée : écriture hors transaction)" $?
nouveau; git -C "$depot" switch -q feat/x; avant=$(git -C "$depot" rev-parse main)
lance env -u CLAUDECODE git branch -q -C feat/x main
[ "$CODE" -eq 0 ] && ! main_est "$avant"; verifie "hors session : git branch -C x main passe, main bouge" $?
# Git passe aussi les mises à jour qui ne changent rien (reset nu, reset --hard HEAD, stash, fin de rebase --abort) : la garde ne refuse que
# la suppression ou une valeur différente de main
info() { echo "info : $1"; }
propre() { [ -z "$(git -C "$depot" status --porcelain)" ]; }
nouveau; avant=$(git -C "$depot" rev-parse main)
lance env CLAUDECODE=1 git reset -q
[ "$CODE" -eq 0 ] && main_est "$avant"; verifie "session : git reset nu sur main (mise à jour sans effet) passe, main inchangée" $?
lance env CLAUDECODE=1 git reset -q --hard HEAD
[ "$CODE" -eq 0 ] && main_est "$avant"; verifie "session : git reset --hard HEAD sur main passe, main inchangée" $?
echo modif >> "$depot/f.txt"
lance env CLAUDECODE=1 git stash -q
[ "$CODE" -eq 0 ] && main_est "$avant" && propre; verifie "session : git stash (avec une modification) sur main passe, main inchangée, arbre propre" $?
nouveau; avant=$(git -C "$depot" rev-parse main)
lance env CLAUDECODE=1 git rebase feat/x
[ "$CODE" -ne 0 ] && main_est "$avant" && contient "$L_SESSION"; verifie "session : rebase de main refusé, main inchangée" $?
git -C "$depot" symbolic-ref -q HEAD >/dev/null 2>&1; [ $? -ne 0 ]; verifie "session : après le rebase refusé, la tête est détachée (état constaté)" $?
lance env CLAUDECODE=1 git rebase --abort
[ "$CODE" -eq 0 ] && main_est "$avant" && [ "$(git -C "$depot" symbolic-ref -q HEAD)" = "refs/heads/main" ] && propre; verifie "session : git rebase --abort ramène sur main, arbre propre" $?
# dossier abîmé après un refus de checkout -B / switch -C depuis une branche de travail : état constaté, puis voie de sortie
for geste in "checkout -q -B main" "switch -q -C main"; do
  nouveau; git -C "$depot" switch -q feat/x; avant=$(git -C "$depot" rev-parse main); tete=$(git -C "$depot" rev-parse feat/x)
  lance env CLAUDECODE=1 git $geste "$base"
  [ "$CODE" -ne 0 ] && main_est "$avant"; verifie "session : git $geste refusé, main inchangée" $?
  [ "$(git -C "$depot" symbolic-ref -q HEAD)" = "refs/heads/feat/x" ] && ! propre; verifie "session : après git $geste refusé, état constaté : HEAD reste sur la branche de travail, arbre et index changés" $?
  lance env CLAUDECODE=1 git reset -q --hard
  [ "$CODE" -eq 0 ] && propre && [ "$(git -C "$depot" symbolic-ref -q HEAD)" = "refs/heads/feat/x" ] && [ "$(git -C "$depot" rev-parse HEAD)" = "$tete" ] && [ -f "$depot/b.txt" ]; verifie "session : après git $geste refusé, git reset --hard sur la branche de travail remet arbre et index" $?
done
# pack-refs et gc en session : le rangement de main (retrait du fichier libre) est refusé comme une suppression, main reste inchangée et lisible
nouveau; avant=$(git -C "$depot" rev-parse main)
lance env CLAUDECODE=1 git pack-refs --all
[ "$CODE" -ne 0 ] && main_est "$avant" && [ -f "$depot/.git/refs/heads/main" ]; verifie "session : git pack-refs --all s'arrête en erreur (retrait refusé), main inchangée, lisible et toujours en fichier libre" $?
lance env CLAUDECODE=1 git gc -q
[ "$CODE" -eq 0 ] && main_est "$avant" && git -C "$depot" rev-parse -q --verify refs/heads/main >/dev/null; verifie "session : git gc -q sort 0, main inchangée et lisible" $?
info "gc : fichier libre de main présent = $([ -f "$depot/.git/refs/heads/main" ] && echo oui || echo non)"

# --- les crochets eux-mêmes : POSIX sh pour reference-transaction, aucune variable de contournement
SORTIE=$(head -1 "$RACINE/tools/hooks/reference-transaction" 2>&1); [ "$SORTIE" = "#!/bin/sh" ]; verifie "reference-transaction : POSIX sh" $?
SORTIE=$(grep -n "PMZILLA_SKIP_GREEN_CHECK\|--no-verify" "$RACINE/tools/hooks/pre-merge-commit" "$RACINE/tools/hooks/reference-transaction" 2>&1); [ -z "$SORTIE" ]; verifie "aucune variable de contournement dans les deux crochets" $?
SORTIE="mode"; [ -x "$RACINE/tools/hooks/pre-merge-commit" ] && [ -x "$RACINE/tools/hooks/reference-transaction" ]; verifie "les deux crochets sont exécutables" $?

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
