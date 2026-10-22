#!/bin/bash
# Test du script de fin de branche depuis un worktree (tools/finish_worktree.sh) : dépôts et worktrees Git TEMPORAIRES,
# script de fin factice (FINISH_WORKTREE_FINISH) qui note la branche et le dossier où il tourne et sort avec le code voulu.
# Cas : aide (0) ; chaque code 20 à 30 avec sa phrase ; 31 (verrou d'index du workspace, la bascule échoue après le retrait) ;
# liste des worktrees, branche du workspace et fichiers du worktree inchangés sur 20 à 29 ; réglage local et caches non bloquants ;
# succès (le faux script tourne dans le workspace, sur la branche, entrée vide) ; codes 0, 1, 9, 10, 11, 12, 13 transmis, conseil
# de recréation seulement pour 1 à 9 ; lancement depuis un autre worktree ; scan du script (hors commentaires) des commandes interdites.
# Change safe-branch-finish (R-79, option B) : la vérification préalable (FINISH_WORKTREE_CHECK, codes 32 à 37), le runner complet dans le
# worktree avant le retrait (FINISH_WORKTREE_RUNNER, codes 38 et 40), la seconde vérification juste avant le retrait ; le code 39 est réservé.
# Un faux contrôle et un faux runner journalisent leurs appels dans un journal d'ordre ; un cas (l'incident du 2026-10-15) passe par le vrai
# mode --check de tools/finish_branch.sh, copié dans un dépôt temporaire avec un dépôt distant nu.
# Jamais le vrai espace de travail ni le vrai script de fin : chaque lancement se fait dans un dépôt sous $tmp (garde-fou dans lance()).
# Lancement à la main : bash tests/finish_worktree/test_finish_worktree.sh </dev/null
set -u
script="$(cd "$(dirname "$0")/../../tools" && pwd)/finish_worktree.sh"
BASH_FIN=bash; [ -x /bin/bash ] && BASH_FIN=/bin/bash   # le script tourne sous le bash du système (3.2 sur Mac) : finish-under-lock D13
SUITE="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
tmp=$(cd "$(mktemp -d)" && pwd -P) || exit 1
trap 'chmod -R u+rwX "$tmp" 2>/dev/null; rm -rf "$tmp"' EXIT
export GIT_CONFIG_GLOBAL="$tmp/gitconfig" GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0 GIT_CEILING_DIRECTORIES="$tmp"
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE
unset PMZILLA_RUN_MORNING_START   # une fin lancée avec un début du matin réglé ne change rien à cette suite (R-104)
# le vrai hook pre-push contrôle les noms des messages qui partent (fix/sorties-et-masquage) : liste fictive, jamais la vraie
printf 'Vexillonia\n' > "$tmp/noms-fictifs.txt"; unset PMZILLA_NOMS; export PMZILLA_LAB_SENSITIVE_NAMES="$tmp/noms-fictifs.txt"
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
  printf 'jeton:%s\n' "${FINISH_BRANCH_TESTED_TOKEN-absent}"
  printf 'force:%s\n' "${FINISH_BRANCH_FORCE_RUN-absent}"
} > "$FAKE_TRACE"
cat "$(git rev-parse --path-format=absolute --git-common-dir)/pmzilla-finish-tested" > "$(dirname "$ORDER_LOG")/fiche-vue" 2>/dev/null
echo "finish $(pwd -P) wt=$([ -d "$WT_PATH" ] && echo present || echo absent)" >> "$ORDER_LOG"
echo "faux : fin lancée"
exit "${FAKE_CODE:-0}"
FAUX
# Faux contrôle : journalise l'appel (numéro, arguments, dossier, entrée, présence du worktree) et rend le code de CHECK_SEQ pour cet appel
# (liste de codes séparés par des espaces ; le dernier se répète).
fauxcheck="$tmp/faux_controle.sh"
cat > "$fauxcheck" <<'FAUX'
#!/bin/bash
c=$(cat "$CHECK_COUNT" 2>/dev/null || echo 0); c=$((c+1)); echo "$c" > "$CHECK_COUNT"
echo "check $c args=$* pwd=$(pwd -P) stdin=[$(cat)] wt=$([ -d "$WT_PATH" ] && echo present || echo absent)" >> "$ORDER_LOG"
echo "finish_branch : sortie-du-faux-controle" >&2
# finish-under-lock D11 : à l'appel CHECK_SIGNAL_AT, envoie SIGTERM au script de fin (numéro lu dans le verrou), puis laisse le piège tourner
[ "${CHECK_SIGNAL_AT:-0}" != "$c" ] || { kill -"${CHECK_SIGNAL_SIG:-TERM}" "$(cat "$(git rev-parse --path-format=absolute --git-common-dir)/pmzilla-fin-en-cours/pid")"; sleep 1; }
codes=(${CHECK_SEQ:-0}); i=$((c-1)); [ "$i" -lt "${#codes[@]}" ] || i=$((${#codes[@]}-1))
exit "${codes[$i]}"
FAUX
# Faux runner : journalise le dossier, l'entrée, les deux variables réservées et la présence du worktree ; peut déplacer le sommet de la branche.
fauxrunner="$tmp/faux_runner.sh"
cat > "$fauxrunner" <<'FAUX'
#!/bin/bash
echo "runner pwd=$(pwd -P) stdin=[$(cat)] no_evals=${PMZILLA_NO_EVALS-absente} skip=${PMZILLA_SKIP_GREEN_CHECK-absente} wt=$([ -d "$WT_PATH" ] && echo present || echo absent)" >> "$ORDER_LOG"
printf '%s\n' "$*" > "$(dirname "$ORDER_LOG")/args-runner"   # local-ci-container 7.1 : la passe Mac reçoit --mac
printf 'jeton=%s force=%s saut=%s\n' "${FINISH_BRANCH_TESTED_TOKEN-absent}" "${FINISH_BRANCH_FORCE_RUN-absent}" "${FINISH_WORKTREE_ALLOW_SKIP-absent}" > "$(dirname "$ORDER_LOG")/env-runner"   # test-speed-2 groupe 0 : les trois variables du saut n'atteignent jamais le runner
echo "sortie-du-faux-runner"
case "${RUNNER_FP:-}" in   # tip : écrit l'empreinte complète = arbre du sommet ; autre : un arbre différent ; sinon rien
  tip) git rev-parse 'HEAD^{tree}' > "$(git rev-parse --path-format=absolute --git-path pmzilla-run-all-ok)" ;;
  autre) echo 4b825dc642cb6eb9a060e54bf8d69288fbee4904 > "$(git rev-parse --path-format=absolute --git-path pmzilla-run-all-ok)" ;;
esac
case "${RUNNER_EDIT:-}" in   # ce que le faux runner fait aux fichiers du worktree (les attentes de 2 s dépassent la résolution des dates)
  rien) sleep 2 ;;                                                         # ne touche rien
  retablit) c=$(cat f.txt); sleep 2; echo autre > f.txt; echo "$c" > f.txt ;;   # modifie un fichier suivi puis le remet exactement en état
  deplace) mv f.txt f.bak; sleep 2; mv f.bak f.txt ;;                      # renomme un fichier suivi puis le remet à sa place (contenu, mode et mtime identiques)
  chmod) chmod +x f.txt; sleep 2; chmod -x f.txt ;;                        # change le mode d'un fichier suivi puis le remet (le mode initial est 644)
  suivi) sleep 2; echo autre >> f.txt ;;                                 # laisse un fichier suivi modifié
  nonsuivi) echo x > nouveau-fichier.txt ;;                                # laisse un fichier non suivi
  dossier) mv dossier dossier.bak; sleep 2; mv dossier.bak dossier ;;      # test-db-guards D2 : renomme un dossier suivi puis le remet à sa place (aucun fichier suivi touché)
  ephemere_racine) sleep 2; echo x > ephemere.txt; rm ephemere.txt ;;      # crée puis supprime un fichier non suivi à la racine
  ephemere_sous) sleep 2; echo x > dossier/ephemere.txt; rm dossier/ephemere.txt ;;   # idem dans un sous-dossier suivi
esac
[ -z "${RUNNER_MOVE:-}" ] || git commit -q --allow-empty -m "pendant le runner"
# finish-under-lock D11 : RUNNER_SIGNAL non vide envoie SIGTERM au script de fin (numéro lu dans le verrou) pendant le runner
[ -z "${RUNNER_SIGNAL:-}" ] || { kill -TERM "$(cat "$(git rev-parse --path-format=absolute --git-common-dir)/pmzilla-fin-en-cours/pid")"; sleep 1; }
exit "${RUNNER_CODE:-0}"
FAUX
export FINISH_WORKTREE_FINISH="bash $faux" FINISH_WORKTREE_CHECK="bash $fauxcheck" FINISH_WORKTREE_RUNNER="bash $fauxrunner"
# Garde-fou du matin (change morning-guard, D7) : « true » par défaut pour tous les cas qui précèdent le bloc dédié, sinon la commande par défaut
# lirait le vrai état du matin du Mac (heure et dossiers réels). Le bloc dédié (code 44) le remplace par un faux garde-fou qui journalise.
export FINISH_MORNING_CHECK=true
MIDI=$(date -j -f "%Y-%m-%d %H:%M" "2026-01-15 12:00" +%s 2>/dev/null || date -d "2026-01-15 12:00" +%s)
export FAKE_TRACE="$tmp/trace" FAKE_CODE=0 CHECK_SEQ=0 RUNNER_CODE=0 RUNNER_MOVE="" CHECK_REEL=0 RUNNER_FP="" RUNNER_EDIT="" CHECK_SIGNAL_AT=0 RUNNER_SIGNAL=""
# Faux lsof (test-speed-2, D12) : devant le vrai dans PATH, il rend, selon LSOF_SEQ (un mode par appel, le dernier se répète), la liste « p<numéro> / n<dossier courant> »
# au format de « lsof -F pn ». Il trouve le numéro du script de fin en remontant ses ancêtres (le plus proche dont la ligne de commande nomme tools/finish_worktree.sh ; on monte tant que les ancêtres le nomment, pour atteindre le script et non un de ses sous-shells, et l'on s'arrête au premier qui ne le nomme pas).
# Modes : rien (seulement le script), autre (+ un processus dans le worktree), sous (+ un dans un sous-dossier), voisin (+ un dans un dossier au nom voisin,
# hors du worktree), sanssoi (une liste qui ne nomme pas le script), vide (aucune sortie, code 0), code1 (le script nommé, mais code 1).
fauxlsof="$tmp/fxlsof"; mkdir -p "$fauxlsof"
cat > "$fauxlsof/lsof" <<'FAUX'
#!/bin/bash
c=$(cat "$LSOF_COUNT" 2>/dev/null || echo 0); c=$((c+1)); echo "$c" > "$LSOF_COUNT"
modes=(${LSOF_SEQ:-rien}); i=$((c-1)); [ "$i" -lt "${#modes[@]}" ] || i=$((${#modes[@]}-1)); mode=${modes[$i]}
soi=""; p=$PPID
while [ -n "$p" ] && [ "$p" -gt 1 ] 2>/dev/null; do
  if ps -o command= -p "$p" 2>/dev/null | grep -qF "tools/finish_worktree.sh"; then soi=$p; elif [ -n "$soi" ]; then break; fi
  p=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')
done
echo "args=$*" >> "$(dirname "$LSOF_COUNT")/lsof-args"
case "$mode" in
  vide) exit 0 ;;
  sanssoi) printf 'p424242\nn/\n' ;;
  *) printf 'p%s\nn/\n' "$soi" ;;
esac
case "$mode" in
  autre) printf 'p424242\nn%s\n' "$WT_PATH" ;;
  sous) printf 'p424242\nn%s/sous/dossier\n' "$WT_PATH" ;;
  voisin) printf 'p424242\nn%s-voisin\n' "$WT_PATH" ;;
  code1) exit 1 ;;
esac
exit 0
FAUX
chmod +x "$fauxlsof/lsof"
# Faux docker (local-ci-container 7.1) : devant le vrai dans PATH ; le script de fin ne doit jamais le lancer ; tout appel est journalisé et fait échouer le cas.
cat > "$fauxlsof/docker" <<'FAUX'
#!/bin/bash
echo "docker $*" >> "${DOCKER_LOG:-/dev/null}"
exit 1
FAUX
chmod +x "$fauxlsof/docker"
PATH_REEL="$PATH"; export PATH="$fauxlsof:$PATH"
unset FINISH_BRANCH_TESTED_TOKEN FINISH_BRANCH_FORCE_RUN FINISH_WORKTREE_ALLOW_SKIP FINISH_LOCK_TOKEN PMZILLA_FINISH_LOCK_MAX_AGE   # le réglage du saut est posé cas par cas (saut permis par défaut, skip-default-on, design D1)
unset FINISH_WORKTREE_CI FINISH_WORKTREE_CI_VERDICTS   # une fin lancée en mode CI (D8) passe la variable à sa passe Mac : sans ce retrait, chaque cas d'avant la section CI tournerait en mode CI (test 11.3 du 2026-10-21)

modele_espace="$tmp/modele-espace"   # dépôt modèle construit une fois, copié par cas (test-speed-2, D17) : ni worktree, ni distant, ni chemin absolu dedans
construit_modele() {
  mkdir -p "$modele_espace"; git init -q "$modele_espace"
  ( cd "$modele_espace" || exit 1
    echo base > f.txt
    mkdir -p tests; echo "# liste déclarée vide : le sélecteur ne rend que les gardes (light-spec-finish, Q10)" > tests/openspec_readers.txt
    printf '.claude/settings.local.json\n__pycache__/\n*.pyc\n.DS_Store\nsortie/\n' > .gitignore
    git add -A; git commit -q -m initial ) || exit 1
}
nouveau() { # espace de travail temporaire $tmp/casN/espace, sur main, avec .gitignore ; $wt = worktree de feat/x
  n=$((n+1)); cas="$tmp/cas$n"; ws="$cas/espace"
  [ -d "$modele_espace" ] || construit_modele
  mkdir -p "$cas"; cp -R "$modele_espace" "$ws"; cd "$ws" || exit 1
  rm -f "$FAKE_TRACE"
  wt="$cas/wt-feat-x"; fiche="$ws/.git/pmzilla-finish-tested"
  export DOCKER_LOG="$cas/docker-appele"
  export ORDER_LOG="$cas/ordre" CHECK_COUNT="$cas/compte-controle" WT_PATH="$wt" LSOF_COUNT="$cas/compte-lsof"
  CHECK_SEQ=0; RUNNER_CODE=0; RUNNER_MOVE=""; CHECK_REEL=0; FAKE_CODE=0; RUNNER_FP=""; RUNNER_EDIT=""; LSOF_SEQ=rien; CHECK_SIGNAL_AT=0; RUNNER_SIGNAL=""
  export LSOF_SEQ
}
nouveau_reel() { # comme nouveau, avec un dépôt distant nu et les vrais scripts de fin de branche (mode --check) commités sur main
  nouveau; git init -q --bare "$cas/distant.git"; git remote add origin "$cas/distant.git"
  mkdir -p tools; cp "$(dirname "$script")/finish_branch.sh" "$(dirname "$script")/lab_paths.sh" "$(dirname "$script")/finish_env.sh" "$(dirname "$script")/finish_lock.sh" "$(dirname "$script")/run_worktree.sh" "$(dirname "$script")/morning_state.sh" "$(dirname "$script")/posture_eval_fingerprint.py" tools/   # finish_lock.sh : module sourcé par finish_branch.sh (multi-session-piloting D5)
  mkdir -p tests/postures; cp "$(dirname "$script")/../tests/postures/fichiers-evalues.txt" tests/postures/   # liste partagée et empreinte lues par le contrôle 6 (posture-evals-on-branch-tip)
  git add -A; git commit -q -m outils; git push -q origin main
  CHECK_REEL=1
}
avec_worktree() { git -C "$ws" worktree add -q -b feat/x "$wt" main; }
lance() { # [dossier] -- arguments : lance le script depuis le dossier (défaut : le workspace), jamais hors de $tmp
  dossier=$ws
  if [ "${1:-}" != "--" ]; then dossier=$1; shift; fi
  shift
  case "$dossier" in "$tmp"/*) ;; *) echo "garde-fou : $dossier hors de $tmp" >&2; exit 1 ;; esac
  rm -f "$FAKE_TRACE" "$ORDER_LOG" "$CHECK_COUNT" "$LSOF_COUNT" "$cas/lsof-args"
  # CHECK_REEL=1 : le vrai mode --check (commande par défaut du script), au lieu du faux contrôle
  SORTIE=$(cd "$dossier" && { [ "$CHECK_REEL" -ne 1 ] || unset FINISH_WORKTREE_CHECK; "$BASH_FIN" "$script" "$@"; } 2>&1 </dev/null); CODE=$?
}
appels() { if [ -f "$ORDER_LOG" ]; then grep -c "^$1 " "$ORDER_LOG"; else echo 0; fi; }   # nombre d'appels du faux « check », « runner » ou « finish »
ligne_de() { grep "^$1 " "$ORDER_LOG" 2>/dev/null | sed -n "${2:-1}p"; }   # la n-ième ligne du journal d'un appel
intact() { # description : rien n'a changé (worktree présent et listé, workspace sur main, fin de branche non lancée)
  [ -d "$wt" ] && git -C "$ws" worktree list --porcelain | grep -qF "worktree $wt" \
    && [ "$(git -C "$ws" rev-parse --abbrev-ref HEAD)" = main ] && [ "$(appels finish)" -eq 0 ] && [ ! -e "$FAKE_TRACE" ]; verifie "$1 : worktree présent et listé, workspace sur main, fin de branche non lancée" $?
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
for c in 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 40; do
  contient " $c "; verifie "aide : le code $c est décrit" $?
done
printf '%s\n' "$SORTIE" | grep -qE '^  39 +réservé'; verifie "aide : le code 39 est dit réservé" $?
# l'ordre de l'aide suit l'ordre des étapes : contrôles, vérification préalable, runner, seconde vérification
printf '%s\n' "$SORTIE" | awk '/^  29  /{a=NR} /^  32  /{b=NR} /^  37  /{c=NR} /^  38  /{d=NR} /^  40  /{e=NR} END {exit !(a && b && c && d && e && a<b && b<c && c<d && d<e)}'; verifie "aide : les codes 29, 32, 37, 38 et 40 sont dans l'ordre des étapes" $?
inchange "aide" "$avant"
[ ! -s "$ORDER_LOG" ] 2>/dev/null; verifie "aide : ni vérification ni runner" $?

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

# --- l'incident du 2026-10-15 : change OpenSpec lié non archivé, refusé par le vrai mode --check avant le retrait (code 32)
nouveau_reel; avec_worktree
mkdir -p "$wt/openspec/changes/x"; echo p > "$wt/openspec/changes/x/proposal.md"; echo code > "$wt/g.txt"; git -C "$wt" add -A; git -C "$wt" commit -q -m "travail"
avant=$(etat)
lance -- feat/x
code_et "incident : change lié non archivé, code 32" 32 "finish_worktree : la fin de branche refuserait : change OpenSpec non archivé ; rien n'est changé"
contient "finish_branch : change OpenSpec non archivé"; verifie "incident : la ligne du mode vérification est affichée" $?
contient "x"; verifie "incident : le change est nommé" $?
[ "$(etat)" = "$avant" ]; verifie "incident : worktree, branche du workspace et fichiers inchangés" $?
intact "incident"
[ "$(appels runner)" -eq 0 ]; verifie "incident : le runner n'est pas lancé" $?
# le même dépôt, la branche prête : le vrai mode --check passe, puis le faux runner et le faux script de fin
nouveau_reel; avec_worktree; echo code > "$wt/g.txt"; git -C "$wt" add -A; git -C "$wt" commit -q -m "travail"
lance -- feat/x
code_et "vrai mode --check, branche prête : code 0" 0 "finish_worktree : vérification préalable réussie"
[ "$(appels runner)" -eq 1 ] && [ "$(appels finish)" -eq 1 ]; verifie "vrai mode --check : le runner puis la fin de branche sont lancés" $?

# --- vérification préalable : un code par refus (D7), FINISH_WORKTREE_CHECK
for def in "5|32|change OpenSpec non archivé" "6|33|jeu d'essai validant absent" "7|34|main n'est pas à jour" "8|35|la branche ne contient pas main" "12|36|main est ouvert dans un autre dossier"; do
  IFS='|' read -r cc cw phrase <<EOF2
$def
EOF2
  nouveau; avec_worktree; CHECK_SEQ=$cc; lance -- feat/x
  code_et "vérification préalable : code $cc du contrôle, code $cw" "$cw" "finish_worktree : la fin de branche refuserait : $phrase ; rien n'est changé"
  contient "finish_branch : sortie-du-faux-controle"; verifie "code $cw : les lignes du contrôle sont affichées" $?
  intact "code $cw"
  [ "$(appels check)" -eq 1 ] && [ "$(appels runner)" -eq 0 ]; verifie "code $cw : un seul contrôle, le runner n'est pas lancé" $?
done
for cc in 2 3 4 99; do
  nouveau; avec_worktree; CHECK_SEQ=$cc; lance -- feat/x
  code_et "vérification préalable : code $cc du contrôle, code 37" 37 "finish_worktree : vérification préalable impossible (code $cc) ; rien n'est changé"
  intact "code 37 (contrôle $cc)"
  [ "$(appels runner)" -eq 0 ]; verifie "code 37 (contrôle $cc) : le runner n'est pas lancé" $?
done
nouveau; avec_worktree; export FINISH_WORKTREE_CHECK="$tmp/commande-introuvable"; lance -- feat/x
code_et "vérification préalable : commande introuvable, code 37" 37 "vérification préalable impossible (code 127) ; rien n'est changé"
intact "code 37 (commande introuvable)"
export FINISH_WORKTREE_CHECK="bash $fauxcheck"
# le contrôle tourne dans le workspace, avec la branche et une entrée vide ; il passe après les contrôles 20 à 29 et avant le retrait
nouveau; avec_worktree; lance -- feat/x
code_et "contrôle réussi : le script continue" 0 "finish_worktree : vérification préalable réussie"
ligne_de check 1 | grep -qF "args=feat/x pwd=$ws stdin=[] wt=present"; rc=$?; SORTIE="$(ligne_de check 1)"; verifie "le contrôle tourne dans le workspace, avec la branche et une entrée vide, le worktree encore là" $rc
nouveau; avec_worktree; echo y >> "$wt/f.txt"; lance -- feat/x
code_et "worktree sale : le refus 28 précède le contrôle" 28
[ "$(appels check)" -eq 0 ] && [ "$(appels runner)" -eq 0 ]; verifie "28 : ni contrôle ni runner" $?
nouveau; avec_worktree; mkdir -p "$wt/sortie"; echo z > "$wt/sortie/a"; lance -- feat/x
code_et "fichiers ignorés : le refus 29 précède le contrôle" 29
[ "$(appels check)" -eq 0 ] && [ "$(appels runner)" -eq 0 ]; verifie "29 : ni contrôle ni runner" $?
nouveau; avec_worktree; lance -- main
[ "$(appels check)" -eq 0 ] && [ "$(appels runner)" -eq 0 ]; verifie "22 : ni contrôle ni runner" $?

# --- test-speed-2, D7, revu par finish-under-lock D1 et D4 : sur le code 14 du contrôle, le passage dbtest tourne sous le verrou
#     (FINISH_WORKTREE_DBTEST) ; vert puis 14 encore : code 41 ; rouge : code 48
L41="finish_worktree : la fin de branche refuserait : passage dbtest vert absent ; rien n'est changé"
export FINISH_WORKTREE_DBTEST=true
nouveau; avec_worktree; CHECK_SEQ=14; lance -- feat/x
code_et "vérification préalable : code 14, passage dbtest vert, 14 encore : code 41" 41 "$L41"
contient "finish_worktree : passage dbtest requis pour l'arbre du sommet"; verifie "code 14 : la ligne du passage dbtest requis" $?
contient "finish_worktree : passage dbtest vert"; verifie "code 14 : la ligne du passage dbtest vert" $?
contient "finish_branch : sortie-du-faux-controle"; verifie "code 41 : les lignes du contrôle sont affichées" $?
intact "code 41"
[ "$(appels check)" -eq 2 ] && [ "$(appels runner)" -eq 0 ]; verifie "code 41 : deux contrôles (avant et après le passage), le runner n'est pas lancé" $?
export FINISH_WORKTREE_DBTEST=false
nouveau; avec_worktree; CHECK_SEQ=14; lance -- feat/x
code_et "vérification préalable : code 14, passage dbtest rouge : code 48" 48 "finish_worktree : passage dbtest rouge (code 1)"
intact "code 48"
[ "$(appels check)" -eq 1 ] && [ "$(appels runner)" -eq 0 ]; verifie "code 48 : un seul contrôle, le runner n'est pas lancé" $?
export FINISH_WORKTREE_DBTEST=true
# seconde vérification : le runner a tourné, puis le contrôle rend 14 : code 41, rien n'est changé
nouveau; avec_worktree; CHECK_SEQ="0 14"; lance -- feat/x
code_et "runner vert, seconde vérification code 14 : code 41" 41 "$L41"
contient "finish_worktree : runner complet vert dans le worktree ; "; verifie "seconde vérification 14 : la ligne « runner vert » précède le refus" $?
intact "seconde vérification 14"
[ "$(appels check)" -eq 2 ] && [ "$(appels runner)" -eq 1 ]; verifie "seconde vérification 14 : deux contrôles, un runner" $?
! contient "worktree retiré"; verifie "seconde vérification 14 : le worktree n'est pas retiré" $?
# l'aide : la ligne 41 entre 36 et 37, l'ordre 29 < 32 < 37 < 38 < 40 gardé
nouveau; avec_worktree; lance -- --help
contient "  41  la fin de branche refuserait : passage dbtest vert absent"; verifie "aide : la ligne du code 41" $?
printf '%s\n' "$SORTIE" | awk '/^  36  /{a=NR} /^  41  /{b=NR} /^  37  /{c=NR} END {exit !(a && b && c && a<b && b<c)}'; verifie "aide : la ligne 41 est entre les lignes 36 et 37" $?
# par le vrai mode --check : une branche qui change db/ sans empreinte est refusée (41), avec l'empreinte de son sommet elle continue
nouveau_reel; avec_worktree; mkdir -p "$wt/db/migrations"; echo "SELECT 1;" > "$wt/db/migrations/9999_test.sql"; git -C "$wt" add -A; git -C "$wt" commit -q -m "migration"
avant=$(etat); lance -- feat/x
code_et "vrai mode --check : db/ changé sans empreinte, code 41" 41 "$L41"
contient "finish_branch : passage dbtest vert absent"; verifie "vrai mode --check : la phrase du code 14 est affichée" $?
[ "$(etat)" = "$avant" ]; verifie "vrai mode --check 41 : worktree, branche du workspace et fichiers inchangés" $?
intact "vrai mode --check 41"
[ "$(appels runner)" -eq 0 ]; verifie "vrai mode --check 41 : le runner n'est pas lancé" $?
git -C "$wt" rev-parse 'HEAD^{tree}' >> "$ws/.git/pmzilla-dbtest-ok"
lance -- feat/x
code_et "vrai mode --check : empreinte de l'arbre du sommet, la fin de branche continue" 0 "finish_worktree : vérification préalable réussie"
[ "$(appels runner)" -eq 1 ] && [ "$(appels finish)" -eq 1 ]; verifie "vrai mode --check avec empreinte : le runner puis la fin de branche sont lancés" $?
export FINISH_WORKTREE_DBTEST=true   # reste posé : un test qui tomberait sur 14 ne lance jamais le vrai tools/dbtest.sh (relecture de 2026-10-19)

# --- finish-under-lock, tâche 3.1 (D1 à D3, D10) : fusion de main dans la branche, sous le verrou, avant le runner
L46_CONFLIT="finish_worktree : fusion de main dans la branche impossible : conflit prévu sur 1 fichier(s), rien n'est changé"
L46_ANNULEE="finish_worktree : fusion de main dans la branche impossible : fusion annulée, rien n'est changé"
L_FUSIONNEE="main est fusionnée dans la branche ; rien d'autre n'est changé"
# main déjà contenue : aucune fusion
nouveau; avec_worktree; lance -- feat/x
code_et "3.1 : main déjà contenue, la fin réussit" 0 "finish_worktree : main déjà contenue dans la branche : aucune fusion"
! contient "main fusionnée dans la branche"; verifie "3.1 : main déjà contenue, aucune ligne de fusion" $?
# main local en avance, sans conflit : fusion faite dans le worktree, main local jamais déplacé
nouveau; avec_worktree; echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"
main_avant=$(git -C "$ws" rev-parse main); lance -- feat/x
code_et "3.1 : main en avance, fusion puis fin réussie" 0 "finish_worktree : main fusionnée dans la branche ("
git -C "$ws" merge-base --is-ancestor "$main_avant" feat/x; verifie "3.1 : la branche contient main après la fusion" $?
[ "$(git -C "$ws" rev-parse main)" = "$main_avant" ]; verifie "3.1 : main local n'est pas déplacé par la fusion" $?
[ "$(appels check)" -eq 3 ]; verifie "3.1 : contrôle avant la fusion, refait après, puis seconde vérification" $?
# conflit prévu par l'aperçu : 46, aucune fusion commencée, rien n'est changé
nouveau; avec_worktree; echo branche > "$wt/f.txt"; git -C "$wt" commit -q -am "branche"
echo principale > "$ws/f.txt"; git -C "$ws" commit -q -am "main"
sommet=$(git -C "$wt" rev-parse HEAD); lance -- feat/x
code_et "3.1 : conflit prévu, code 46" 46 "$L46_CONFLIT"
contient "f.txt"; verifie "3.1 : 46 nomme le fichier en conflit" $?
[ "$(git -C "$wt" rev-parse HEAD)" = "$sommet" ] && ! git -C "$wt" rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1
verifie "3.1 : 46, aucune fusion commencée, sommet de la branche inchangé" $?
[ "$(appels runner)" -eq 0 ]; verifie "3.1 : 46, le runner n'est pas lancé" $?
intact "3.1 : code 46 (conflit prévu)"
# fusion refusée par un crochet que l'aperçu ne voit pas : 46, fusion annulée (la branche a son propre commit : la fusion crée un commit,
# donc passe par commit-msg ; une avance rapide ne crée aucun commit et ne passe par aucun crochet)
nouveau; avec_worktree; echo b > "$wt/b.txt"; git -C "$wt" add b.txt; git -C "$wt" commit -q -m "branche"
echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"
printf '#!/bin/sh\nexit 1\n' > "$ws/.git/hooks/commit-msg"; chmod +x "$ws/.git/hooks/commit-msg"
sommet=$(git -C "$wt" rev-parse HEAD); lance -- feat/x
code_et "3.1 : fusion refusée par un crochet, code 46" 46 "$L46_ANNULEE"
[ "$(git -C "$wt" rev-parse HEAD)" = "$sommet" ] && ! git -C "$wt" rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1
verifie "3.1 : fusion annulée, aucune fusion en cours, sommet inchangé" $?
intact "3.1 : code 46 (fusion annulée)"
rm -f "$ws/.git/hooks/commit-msg"
# refus avant tout changement : le premier contrôle refuse (5), aucune fusion
nouveau; avec_worktree; echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"
main_avant=$(git -C "$ws" rev-parse main); CHECK_SEQ=5; lance -- feat/x
code_et "3.1 : premier contrôle 5, code 32 avant toute fusion" 32
! git -C "$ws" merge-base --is-ancestor "$main_avant" feat/x; verifie "3.1 : 32 au premier contrôle, aucune fusion faite" $?
! contient "$L_FUSIONNEE"; verifie "3.1 : 32 au premier contrôle, pas de ligne de fusion" $?
# refus après la fusion : la ligne de fusion suit la phrase du refus
nouveau; avec_worktree; echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"
CHECK_SEQ="0 5"; lance -- feat/x
code_et "3.1 : contrôle après la fusion 5, code 32" 32
contient "$L_FUSIONNEE"; verifie "3.1 : 32 après la fusion, la ligne « main est fusionnée dans la branche »" $?
[ "$(appels runner)" -eq 0 ]; verifie "3.1 : 32 après la fusion, le runner n'est pas lancé" $?
# main distant en avance (origin/main plus avancé que main local) : fusion de origin/main, main local jamais déplacé
nouveau; git init -q --bare "$cas/distant.git"; git -C "$ws" remote add origin "$cas/distant.git"; git -C "$ws" push -q origin main; avec_worktree
git clone -q "$cas/distant.git" "$cas/autre"; echo d > "$cas/autre/d.txt"; git -C "$cas/autre" add d.txt; git -C "$cas/autre" commit -q -m "distant avance"; git -C "$cas/autre" push -q origin main
distant=$(git -C "$cas/autre" rev-parse HEAD); main_avant=$(git -C "$ws" rev-parse main); lance -- feat/x
code_et "3.1 : main distant en avance, fusion puis fin réussie" 0 "finish_worktree : main fusionnée dans la branche ("
git -C "$ws" merge-base --is-ancestor "$distant" feat/x; verifie "3.1 : la branche contient le sommet de origin/main" $?
[ "$(git -C "$ws" rev-parse main)" = "$main_avant" ]; verifie "3.1 : main distant en avance, main local n'est pas déplacé" $?
# la fiche de fin est calculée sur le sommet fusionné : son sommet est le commit de fusion, son arbre celui de ce commit (D2, D16)
nouveau; avec_worktree; echo b > "$wt/b.txt"; git -C "$wt" add b.txt; git -C "$wt" commit -q -m "branche"
echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"
avant_fusion=$(git -C "$wt" rev-parse HEAD); RUNNER_FP=tip; lance -- feat/x; RUNNER_FP=""
code_et "3.1 : fusion puis runner vert, fiche écrite" 0 "fiche de fin écrite"
fusionne=$(git -C "$ws" rev-parse feat/x)
[ "$fusionne" != "$avant_fusion" ] && grep -qx "tip=$fusionne" "$cas/fiche-vue" && grep -qx "tree=$(git -C "$ws" rev-parse "$fusionne^{tree}")" "$cas/fiche-vue"
rc=$?; SORTIE=$(cat "$cas/fiche-vue" 2>&1); verifie "3.1 et 3.3 : la fiche porte le sommet fusionné et l'arbre de ce sommet" $rc

# --- relecture Opus du 2026-10-20 : cas du design que les tests précédents ne faisaient pas échouer
# D2 : fetch en échec (distant injoignable) : aucune fusion, la vérification est refaite et refuse (7 -> 34)
nouveau; avec_worktree; git -C "$ws" remote add origin "$cas/absent.git"
echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"; main_avant=$(git -C "$ws" rev-parse main)
CHECK_SEQ="0 7"; lance -- feat/x
code_et "D2 : fetch en échec, aucune fusion, vérification refaite : 34" 34 "finish_worktree : main distante injoignable : aucune fusion"
! git -C "$ws" merge-base --is-ancestor "$main_avant" feat/x && ! contient "main est fusionnée"; verifie "D2 : fetch en échec, la branche ne contient pas main, aucune ligne de fusion" $?
[ "$(appels check)" -eq 2 ] && [ "$(appels runner)" -eq 0 ]; verifie "D2 : fetch en échec, la vérification est refaite, le runner n'est pas lancé" $?
# D2 : main locale et main distante divergentes : aucune fusion, la vérification est refaite et refuse
nouveau; git init -q --bare "$cas/distant.git"; git -C "$ws" remote add origin "$cas/distant.git"; git -C "$ws" push -q origin main; avec_worktree
git clone -q "$cas/distant.git" "$cas/autre"; echo d > "$cas/autre/d.txt"; git -C "$cas/autre" add d.txt; git -C "$cas/autre" commit -q -m "distant avance"; git -C "$cas/autre" push -q origin main
echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main locale avance"; sommet=$(git -C "$wt" rev-parse HEAD)
CHECK_SEQ="0 7"; lance -- feat/x
code_et "D2 : main divergentes, aucune fusion : 34" 34 "finish_worktree : main locale et main distante divergent : aucune fusion"
[ "$(git -C "$wt" rev-parse HEAD)" = "$sommet" ]; verifie "D2 : main divergentes, sommet de la branche inchangé" $?
# D2 : le distant existe et main locale est en avance sur lui : c'est main locale qui est fusionnée
nouveau; git init -q --bare "$cas/distant.git"; git -C "$ws" remote add origin "$cas/distant.git"; git -C "$ws" push -q origin main; avec_worktree
echo b > "$wt/b.txt"; git -C "$wt" add b.txt; git -C "$wt" commit -q -m "branche"
echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main locale avance"; main_avant=$(git -C "$ws" rev-parse main)
lance -- feat/x
code_et "D2 : main locale en avance sur le distant, fusion" 0 "finish_worktree : main fusionnée dans la branche ("
[ "$(git -C "$ws" rev-parse 'feat/x^2')" = "$main_avant" ]; verifie "D2 : le second parent de la fusion est main locale (la plus avancée)" $?
# D1 : la première vérification rend 8 : le script continue vers la fusion, puis la vérification refaite rend 0
nouveau; avec_worktree; echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"; main_avant=$(git -C "$ws" rev-parse main)
CHECK_SEQ="8 0"; lance -- feat/x
code_et "D1 : première vérification 8, fusion puis fin réussie" 0 "finish_worktree : main fusionnée dans la branche ("
git -C "$ws" merge-base --is-ancestor "$main_avant" feat/x; verifie "D1 : après le 8, la branche contient main" $?
# D1 : la première vérification rend 14 : fusion d'abord, puis la vérification refaite décide (ici 0 : aucun passage dbtest)
nouveau; avec_worktree; echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"
CHECK_SEQ="14 0"; lance -- feat/x
code_et "D1 : première vérification 14, fusion, vérification refaite 0 : fin réussie" 0 "finish_worktree : main fusionnée dans la branche ("
! contient "passage dbtest requis"; verifie "D1 : 14 puis 0 après la fusion : aucun passage dbtest" $?
# D3 : la ligne de fusion est la ligne qui suit la phrase du refus, et la fusion reste dans la branche (32, 48, 38)
L_FUS="main est fusionnée dans la branche ; rien d'autre n'est changé"
ligne_suivante() { printf '%s\n' "$SORTIE" | awk -v p="$1" 'index($0, p) {getline s; print s; exit}'; }
nouveau; avec_worktree; echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"; main_avant=$(git -C "$ws" rev-parse main)
CHECK_SEQ="0 5"; lance -- feat/x
[ "$CODE" -eq 32 ] && [ "$(ligne_suivante "change OpenSpec non archivé ; rien n'est changé")" = "$L_FUS" ] && git -C "$ws" merge-base --is-ancestor "$main_avant" feat/x
verifie "D3 : 32 après la fusion, ligne de fusion juste après la phrase, la fusion reste" $?
nouveau; avec_worktree; echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"
export FINISH_WORKTREE_DBTEST=false; CHECK_SEQ="0 14"; lance -- feat/x; export FINISH_WORKTREE_DBTEST=true
[ "$CODE" -eq 48 ] && [ "$(ligne_suivante "passage dbtest rouge (code 1)")" = "$L_FUS" ]; verifie "D3 : 48 après la fusion, ligne de fusion juste après la phrase" $?
nouveau; avec_worktree; echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"
RUNNER_CODE=1; lance -- feat/x; RUNNER_CODE=0
[ "$CODE" -eq 38 ] && [ "$(ligne_suivante "le runner complet n'est pas vert dans le worktree (code 1)")" = "$L_FUS" ]; verifie "D3 : 38 après la fusion, ligne de fusion juste après la phrase" $?
# D3 : fusion refusée par un crochet : la sortie de la fusion précède la phrase du 46, le worktree est propre après l'abandon
nouveau; avec_worktree; echo b > "$wt/b.txt"; git -C "$wt" add b.txt; git -C "$wt" commit -q -m "branche"
echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"
printf '#!/bin/sh\necho "sortie-du-crochet-de-fusion" >&2\nexit 1\n' > "$ws/.git/hooks/commit-msg"; chmod +x "$ws/.git/hooks/commit-msg"
lance -- feat/x; rm -f "$ws/.git/hooks/commit-msg"
awk '/sortie-du-crochet-de-fusion/{a=NR} /fusion annulée, rien n.est changé/{b=NR} END {exit !(a && b && a<b)}' <<< "$SORTIE"; verifie "D3 : 46, la sortie de la fusion est affichée avant la phrase" $?
[ -z "$(git -C "$wt" status --porcelain)" ]; verifie "D3 : 46, le worktree est propre après l'abandon" $?
# D11 : signal pendant le crochet pre-merge-commit (avant que Git n'écrive l'état de fusion) : rien ne reste, ni fichier ni index
nouveau; avec_worktree; echo b > "$wt/b.txt"; git -C "$wt" add b.txt; git -C "$wt" commit -q -m "branche"
echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"
printf '#!/bin/sh\nkill -TERM "$(cat "$(git rev-parse --path-format=absolute --git-common-dir)/pmzilla-fin-en-cours/pid")"\nsleep 3\nexit 1\n' > "$ws/.git/hooks/pre-merge-commit"; chmod +x "$ws/.git/hooks/pre-merge-commit"
sommet=$(git -C "$wt" rev-parse HEAD); lance -- feat/x; rm -f "$ws/.git/hooks/pre-merge-commit"
code_et "D11 : signal pendant pre-merge-commit, code 143" 143 "finish_worktree : interrompu (code 143) : fusion de main annulée, rien n'est changé"
[ "$(git -C "$wt" rev-parse HEAD)" = "$sommet" ] && [ -z "$(git -C "$wt" status --porcelain)" ] && ! git -C "$wt" rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1
rc=$?; SORTIE="$(git -C "$wt" status --porcelain)"; verifie "D11 : signal pendant pre-merge-commit, sommet inchangé, worktree propre, aucune fusion en cours" $rc
# D11 : SIGINT pendant la seconde vérification : 130, la ligne d'interruption
# Le runner lance les suites en tâche de fond : bash y démarre les commandes avec SIGINT ignoré, et un shell non interactif ne peut pas piéger
# un signal ignoré dès son entrée. Le script est donc lancé ici avec SIGINT remis par défaut (comme la suite dbtest), ce qu'il a dans un Terminal.
lance_sigint() { # arguments : comme lance, depuis le workspace, SIGINT remis par défaut
  rm -f "$FAKE_TRACE" "$ORDER_LOG" "$CHECK_COUNT" "$LSOF_COUNT" "$cas/lsof-args"
  SORTIE=$(cd "$ws" && python3 -I -B -c 'import os, signal, sys; signal.signal(signal.SIGINT, signal.SIG_DFL); os.execvp(sys.argv[1], sys.argv[1:])' "$BASH_FIN" "$script" "$@" 2>&1 </dev/null); CODE=$?
}
nouveau; avec_worktree; CHECK_SIGNAL_AT=2; CHECK_SIGNAL_SIG=INT; export CHECK_SIGNAL_SIG; lance_sigint feat/x; CHECK_SIGNAL_AT=0; unset CHECK_SIGNAL_SIG
code_et "D11 : SIGINT, code 130" 130 "finish_worktree : interrompu (code 130) : rien n'est changé"
# D9 : l'aide range 41, 49, 37, 46, 48 dans l'ordre des étapes, et dit 50 réservé
nouveau; avec_worktree; lance -- --help
printf '%s\n' "$SORTIE" | awk '/^  41  /{a=NR} /^  49  /{b=NR} /^  37  /{c=NR} /^  46  /{d=NR} /^  48  /{e=NR} END {exit !(a && b && c && d && e && a<b && b<c && c<d && d<e)}'; verifie "D9 : l'aide range 41, 49, 37, 46, 48 dans l'ordre des étapes" $?
printf '%s\n' "$SORTIE" | grep -q '^  50  mode CI'; verifie "D9 : l'aide décrit le code 50 (mode CI, verdict du conteneur)" $?
! printf '%s\n' "$SORTIE" | grep -q '50.*réservé'; verifie "D9 : le code 50 n'est plus dit réservé" $?
# D16 : une fiche laissée par un passage antérieur est effacée juste après le verrou, même quand le script de fin est lancé sans fiche nouvelle
nouveau; avec_worktree; printf 'format=1\nbranch=feat/x\n' > "$fiche"; RUNNER_FP=""; lance -- feat/x
code_et "D16 : ancienne fiche, runner sans empreinte, fin lancée" 0 "faux : fin lancée"
[ ! -s "$cas/fiche-vue" ]; rc=$?; SORTIE=$(cat "$cas/fiche-vue" 2>&1); verifie "D16 : le script de fin ne voit aucune fiche (l'ancienne a été effacée après le verrou)" $rc
# D16 : une ancienne empreinte égale au sommet ne donne aucune fiche : le script de fin n'en voit aucune
nouveau; avec_worktree; git -C "$wt" rev-parse 'HEAD^{tree}' > "$(git -C "$wt" rev-parse --path-format=absolute --git-path pmzilla-run-all-ok)"
RUNNER_FP=""; lance -- feat/x
[ "$CODE" -eq 0 ] && [ ! -s "$cas/fiche-vue" ]; rc=$?; SORTIE=$(cat "$cas/fiche-vue" 2>&1); verifie "D16 : ancienne empreinte, runner muet : le script de fin ne voit aucune fiche" $rc
# D13 : la suite lance le script par le bash du système, jamais par le premier bash du PATH
SORTIE=$(grep -n 'bash "\$script"' "$SUITE" | grep -v 'grep -n'); [ -z "$SORTIE" ]; verifie "D13 : aucun lancement du script par « bash » du PATH dans cette suite" $?

# --- finish-under-lock, tâche 3.2 (en partie, D12 et D9) : ligne de succès, aide
# script de fin qui rend 0 sans déplacer main : succès non établi, code 0 transmis (la branche a son propre commit : sans lui, son sommet
# est celui de main, que main contient déjà)
nouveau; avec_worktree; echo b > "$wt/b.txt"; git -C "$wt" add b.txt; git -C "$wt" commit -q -m "branche"; lance -- feat/x
code_et "3.2 : script de fin en code 0, main ne contient pas le sommet" 0 "finish_worktree : succès non établi : main ne contient pas le sommet de la branche"
! contient "finish_worktree : terminé : main"; verifie "3.2 : pas de ligne « terminé » quand main ne contient pas le sommet" $?
# script de fin qui amène main au sommet de la branche : la ligne « terminé : main <avant> -> <après> »
nouveau; avec_worktree; echo b > "$wt/b.txt"; git -C "$wt" add b.txt; git -C "$wt" commit -q -m "branche"
avant_court=$(git -C "$ws" rev-parse --short main)
FIN_SAUVE=$FINISH_WORKTREE_FINISH; export FINISH_WORKTREE_FINISH="git update-ref refs/heads/main refs/heads/feat/x"
lance -- feat/x; export FINISH_WORKTREE_FINISH=$FIN_SAUVE
code_et "3.2 : main amenée au sommet, ligne de succès" 0 "finish_worktree : terminé : main $avant_court -> $(git -C "$ws" rev-parse --short main)"
! contient "succès non établi"; verifie "3.2 : succès établi, pas de ligne « succès non établi »" $?
# code 13 du script de fin : aucune des deux lignes
nouveau; avec_worktree; FAKE_CODE=13 lance -- feat/x; FAKE_CODE=0
code_et "3.2 : code 13 transmis" 13
! contient "finish_worktree : terminé :" && ! contient "succès non établi"; verifie "3.2 : code 13, ni ligne de succès ni « succès non établi »" $?
# l'aide : 46, 48 et 49 décrits, 50 réservé, 47 absent
nouveau; avec_worktree; lance -- --help
contient "  46  " && contient "  48  " && contient "  49  " && contient "  50  "; verifie "3.2 : l'aide décrit 46, 48, 49 et 50" $?
! contient "  47  "; verifie "3.2 : l'aide ne décrit pas 47" $?
# code 19 du contrôle (un autre change touché) : 49, rien n'est changé
nouveau; avec_worktree; CHECK_SEQ=19; lance -- feat/x
code_et "3.2 : code 19 du contrôle, code 49" 49 "finish_worktree : la fin de branche refuserait : la branche touche un autre change OpenSpec ; rien n'est changé"
intact "3.2 : code 49"
[ "$(appels runner)" -eq 0 ]; verifie "3.2 : code 49, le runner n'est pas lancé" $?
# code 14 après la fusion : le passage tourne dans le worktree, entrée vide, avec le jeton du verrou ; puis la vérification refaite
DBTEST_SAUVE=$FINISH_WORKTREE_DBTEST
export FINISH_WORKTREE_DBTEST='echo "dbtest pwd=$(pwd -P) stdin=[$(cat)] jeton=$(if [ -n "${FINISH_LOCK_TOKEN:-}" ] && [ "$FINISH_LOCK_TOKEN" = "$(cat "$(git rev-parse --path-format=absolute --git-common-dir)/pmzilla-fin-en-cours/jeton" 2>/dev/null)" ]; then echo verrou; else echo autre; fi)" >> "$ORDER_LOG"'
nouveau; avec_worktree; echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"
CHECK_SEQ="0 14 0"; lance -- feat/x
code_et "3.2 : 14 après la fusion, passage vert, fin réussie" 0 "finish_worktree : passage dbtest vert"
awk '/main fusionnée dans la branche/{a=NR} /passage dbtest requis/{b=NR} /vérification préalable réussie/{c=NR} END {exit !(a && b && c && a<b && b<c)}' <<< "$SORTIE"; verifie "3.2 : l'ordre : fusion, passage dbtest, vérification réussie" $?
ligne_de dbtest | grep -qF "dbtest pwd=$wt stdin=[] jeton=verrou"; rc=$?; SORTIE="$(ligne_de dbtest)"; verifie "3.2 : le passage tourne dans le worktree, entrée vide, avec le jeton du verrou" $rc
[ "$(appels check)" -eq 4 ]; verifie "3.2 : quatre contrôles (avant la fusion, après, après le passage, avant le retrait)" $?
export FINISH_WORKTREE_DBTEST=$DBTEST_SAUVE
# interruptions (D11) : un signal pendant la fusion l'abandonne ; un signal après la fusion la laisse et le dit ; sans fusion, « rien n'est changé »
# signal pendant la fusion : un crochet commit-msg du dépôt temporaire envoie SIGTERM au script de fin pendant que git merge attend
nouveau; avec_worktree; echo b > "$wt/b.txt"; git -C "$wt" add b.txt; git -C "$wt" commit -q -m "branche"
echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"
printf '#!/bin/sh\nkill -TERM "$(cat "$(git rev-parse --path-format=absolute --git-common-dir)/pmzilla-fin-en-cours/pid")"\nsleep 3\nexit 1\n' > "$ws/.git/hooks/commit-msg"; chmod +x "$ws/.git/hooks/commit-msg"
sommet=$(git -C "$wt" rev-parse HEAD); lance -- feat/x
code_et "3.2 : signal pendant la fusion, code 143" 143 "finish_worktree : interrompu (code 143) : fusion de main annulée, rien n'est changé"
[ "$(git -C "$wt" rev-parse HEAD)" = "$sommet" ] && ! git -C "$wt" rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1
verifie "3.2 : signal pendant la fusion, fusion abandonnée, sommet inchangé" $?
intact "3.2 : signal pendant la fusion"
[ ! -e "$ws/.git/pmzilla-fin-en-cours" ]; verifie "3.2 : signal pendant la fusion, le verrou est libéré" $?
rm -f "$ws/.git/hooks/commit-msg"
# signal pendant le runner, après la fusion : la fusion reste, la ligne le dit, aucune fusion n'est abandonnée
nouveau; avec_worktree; echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"
main_avant=$(git -C "$ws" rev-parse main); RUNNER_SIGNAL=1; lance -- feat/x; RUNNER_SIGNAL=""
code_et "3.2 : signal après la fusion, code 143" 143 "finish_worktree : interrompu (code 143) : main est fusionnée dans la branche ; rien d'autre n'est changé"
git -C "$ws" merge-base --is-ancestor "$main_avant" feat/x; verifie "3.2 : signal après la fusion, la fusion reste dans la branche" $?
intact "3.2 : signal après la fusion"
# signal sans fusion (main déjà contenue), pendant le runner : « rien n'est changé »
nouveau; avec_worktree; RUNNER_SIGNAL=1; lance -- feat/x; RUNNER_SIGNAL=""
code_et "3.2 : signal sans fusion, code 143" 143 "finish_worktree : interrompu (code 143) : rien n'est changé"
! contient "fusion de main annulée" && ! contient "main est fusionnée"; verifie "3.2 : signal sans fusion, aucune ligne de fusion" $?
intact "3.2 : signal sans fusion"

# --- finish-under-lock, tâche 5.3 (D17) : avec les deux crochets du verrou installés dans le dépôt temporaire (liens vers ceux du dépôt), la
#     fusion de la fin, son abandon après un refus (46), l'abandon après une interruption et le déplacement de main par le script de fin passent
avec_crochets() { for h in pre-merge-commit reference-transaction; do ln -s "$(dirname "$script")/hooks/$h" "$ws/.git/hooks/$h"; done; }
nouveau; avec_worktree; avec_crochets; echo b > "$wt/b.txt"; git -C "$wt" add b.txt; git -C "$wt" commit -q -m "branche"
echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"; main_avant=$(git -C "$ws" rev-parse main)
lance -- feat/x
code_et "5.3 : crochets installés, la fusion de main dans la branche passe" 0 "finish_worktree : main fusionnée dans la branche ("
! contient "fusion refusée" && ! contient "mise à jour de main refusée"; verifie "5.3 : aucun refus des crochets pendant la fusion" $?
git -C "$ws" merge-base --is-ancestor "$main_avant" feat/x; verifie "5.3 : la branche contient main" $?
# le crochet refuse bien sans le jeton : une fusion lancée à la main pendant que le verrou d'une autre fin est posé
mkdir -p "$ws/.git/pmzilla-fin-en-cours"; ( cd "$ws/.git/pmzilla-fin-en-cours" && echo $$ > pid && date +%s > debut && echo feat/autre > branche && echo jeton-autre > jeton )
SORTIE=$(git -C "$ws" update-ref refs/heads/main feat/x 2>&1); rc=$?
[ "$rc" -ne 0 ] && [ "$(git -C "$ws" rev-parse main)" = "$main_avant" ] && contient "mise à jour de main refusée"; verifie "5.3 : témoin : sans le jeton, les crochets installés refusent de déplacer main" $?
rm -rf "$ws/.git/pmzilla-fin-en-cours"
# fusion refusée par commit-msg : l'abandon (merge --abort) passe les crochets, 46
nouveau; avec_worktree; avec_crochets; echo b > "$wt/b.txt"; git -C "$wt" add b.txt; git -C "$wt" commit -q -m "branche"
echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"
printf '#!/bin/sh\nexit 1\n' > "$ws/.git/hooks/commit-msg"; chmod +x "$ws/.git/hooks/commit-msg"
sommet=$(git -C "$wt" rev-parse HEAD); lance -- feat/x
code_et "5.3 : crochets installés, fusion refusée puis annulée : 46" 46 "$L46_ANNULEE"
[ "$(git -C "$wt" rev-parse HEAD)" = "$sommet" ] && ! git -C "$wt" rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1; verifie "5.3 : l'abandon passe les crochets, sommet inchangé" $?
rm -f "$ws/.git/hooks/commit-msg"
# interruption pendant la fusion : l'abandon du piège passe les crochets
nouveau; avec_worktree; avec_crochets; echo b > "$wt/b.txt"; git -C "$wt" add b.txt; git -C "$wt" commit -q -m "branche"
echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"
printf '#!/bin/sh\nkill -TERM "$(cat "$(git rev-parse --path-format=absolute --git-common-dir)/pmzilla-fin-en-cours/pid")"\nsleep 3\nexit 1\n' > "$ws/.git/hooks/commit-msg"; chmod +x "$ws/.git/hooks/commit-msg"
sommet=$(git -C "$wt" rev-parse HEAD); lance -- feat/x
code_et "5.3 : crochets installés, signal pendant la fusion : 143" 143 "fusion de main annulée, rien n'est changé"
[ "$(git -C "$wt" rev-parse HEAD)" = "$sommet" ] && ! git -C "$wt" rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1; verifie "5.3 : l'abandon après l'interruption passe les crochets" $?
rm -f "$ws/.git/hooks/commit-msg"
# le script de fin déplace main (faux script : update-ref) sous le verrou, avec le jeton : les crochets le laissent passer
nouveau; avec_worktree; avec_crochets; echo b > "$wt/b.txt"; git -C "$wt" add b.txt; git -C "$wt" commit -q -m "branche"
avant_court=$(git -C "$ws" rev-parse --short main)
FIN_SAUVE=$FINISH_WORKTREE_FINISH; export FINISH_WORKTREE_FINISH="git update-ref refs/heads/main refs/heads/feat/x"
lance -- feat/x; export FINISH_WORKTREE_FINISH=$FIN_SAUVE
code_et "5.3 : crochets installés, le script de fin déplace main" 0 "finish_worktree : terminé : main $avant_court -> $(git -C "$ws" rev-parse --short main)"
! contient "mise à jour de main refusée"; verifie "5.3 : reference-transaction laisse passer le déplacement de main par la fin" $?

# --- finish-under-lock, tâche 3.3 (D16, idée #284) : fiche de fin
# une ancienne empreinte égale à l'arbre du sommet, et un runner qui n'écrit rien : aucune fiche, la ligne dédiée
nouveau; avec_worktree
git -C "$wt" rev-parse 'HEAD^{tree}' > "$(git -C "$wt" rev-parse --path-format=absolute --git-path pmzilla-run-all-ok)"
RUNNER_FP=""; lance -- feat/x
code_et "3.3 : ancienne empreinte égale au sommet, runner muet : pas de fiche" 0 "finish_worktree : runner complet vert dans le worktree ; empreinte complète non réécrite par ce runner : le script de fin le relancera"
! contient "fiche de fin écrite"; verifie "3.3 : runner muet, la fiche n'est pas écrite" $?
# une fiche laissée par un passage antérieur est effacée juste après le verrou, même quand le premier contrôle refuse
nouveau; avec_worktree; echo "format=1" > "$fiche"; CHECK_SEQ=5; lance -- feat/x
code_et "3.3 : ancienne fiche et refus du premier contrôle, code 32" 32
[ ! -e "$fiche" ]; verifie "3.3 : l'ancienne fiche est effacée après le verrou" $?
# fiche écrite après un runner vert, puis refus de la seconde vérification : le piège de sortie l'efface (le script de fin n'est pas lancé)
nouveau; avec_worktree; RUNNER_FP=tip; CHECK_SEQ="0 5"; lance -- feat/x
code_et "3.3 : runner vert, fiche écrite, seconde vérification 5 : code 32" 32
contient "fiche de fin écrite"; verifie "3.3 : la fiche avait été écrite après le runner" $?
[ ! -e "$fiche" ]; verifie "3.3 : refus après le runner, la fiche est effacée par le piège de sortie" $?
RUNNER_FP=""
# l'arbre de la fiche est celui de son sommet
nouveau; avec_worktree; echo b > "$wt/b.txt"; git -C "$wt" add b.txt; git -C "$wt" commit -q -m "branche"; RUNNER_FP=tip; lance -- feat/x; RUNNER_FP=""
code_et "3.3 : runner vert, fiche écrite" 0 "fiche de fin écrite"
tip_fiche=$(sed -n 's/^tip=//p' "$cas/fiche-vue"); arbre_fiche=$(sed -n 's/^tree=//p' "$cas/fiche-vue")
[ -n "$tip_fiche" ] && [ "$arbre_fiche" = "$(git -C "$ws" rev-parse "$tip_fiche^{tree}")" ]; rc=$?; SORTIE=$(cat "$cas/fiche-vue" 2>&1); verifie "3.3 : le champ tree de la fiche est l'arbre de son champ tip" $rc
# aucune fiche ne reste après un refus qui suit le runner vert : seconde vérification (33 à 37, 41, 49), garde du matin (44), retrait (30), bascule (31)
for def in "6|33" "7|34" "8|35" "12|36" "4|37" "14|41" "19|49"; do
  IFS='|' read -r cc cw <<EOF2
$def
EOF2
  nouveau; avec_worktree; RUNNER_FP=tip; CHECK_SEQ="0 $cc"; lance -- feat/x; RUNNER_FP=""
  code_et "3.3 : fiche écrite, seconde vérification $cc : code $cw" "$cw" "fiche de fin écrite"
  [ ! -e "$fiche" ]; verifie "3.3 : code $cw, aucune fiche ne reste" $?
done
nouveau; avec_worktree; RUNNER_FP=tip
MATIN_SAUVE=$FINISH_MORNING_CHECK; export FINISH_MORNING_CHECK="c=\$(cat '$cas/compte-matin-fiche' 2>/dev/null || echo 0); c=\$((c+1)); echo \$c > '$cas/compte-matin-fiche'; [ \$c -lt 2 ]"
lance -- feat/x; RUNNER_FP=""; export FINISH_MORNING_CHECK=$MATIN_SAUVE
code_et "3.3 : fiche écrite, garde du matin refusée avant le retrait : code 44" 44 "fiche de fin écrite"
[ ! -e "$fiche" ]; verifie "3.3 : code 44, aucune fiche ne reste" $?
nouveau; avec_worktree; git -C "$ws" worktree lock "$wt"; RUNNER_FP=tip; lance -- feat/x; RUNNER_FP=""
code_et "3.3 : fiche écrite, retrait impossible : code 30" 30 "fiche de fin écrite"
[ ! -e "$fiche" ]; verifie "3.3 : code 30, aucune fiche ne reste" $?
nouveau; avec_worktree; : > "$ws/.git/index.lock"; RUNNER_FP=tip; lance -- feat/x; RUNNER_FP=""; rm -f "$ws/.git/index.lock"
code_et "3.3 : fiche écrite, bascule impossible : code 31" 31 "fiche de fin écrite"
[ ! -e "$fiche" ]; verifie "3.3 : code 31, aucune fiche ne reste" $?
# interruption après le runner vert (pendant la seconde vérification) : la fiche est effacée, la ligne d'interruption est écrite
nouveau; avec_worktree; RUNNER_FP=tip; CHECK_SIGNAL_AT=2; lance -- feat/x; RUNNER_FP=""; CHECK_SIGNAL_AT=0
code_et "3.3 : interruption après le runner vert, code 143" 143 "finish_worktree : interrompu (code 143) : rien n'est changé"
contient "fiche de fin écrite"; verifie "3.3 : la fiche avait été écrite avant l'interruption" $?
[ ! -e "$fiche" ]; verifie "3.3 : interruption après le runner vert, aucune fiche ne reste" $?
intact "3.3 : interruption après le runner vert"

# --- runner complet dans le worktree avant le retrait (Q3, option B) : FINISH_WORKTREE_RUNNER
nouveau; avec_worktree; RUNNER_CODE=3; lance -- feat/x
code_et "runner rouge : code 38 avec son code" 38 "finish_worktree : le runner complet n'est pas vert dans le worktree (code 3) ; rien n'est changé"
contient "finish_worktree : lancement du runner complet dans le worktree"; verifie "38 : la ligne de lancement du runner" $?
contient "sortie-du-faux-runner"; verifie "38 : la sortie du runner est affichée" $?
! contient "runner complet vert"; verifie "38 : la ligne « runner vert » n'est pas écrite" $?
intact "38"
[ "$(appels check)" -eq 1 ] && [ "$(appels runner)" -eq 1 ]; verifie "38 : la seconde vérification n'est pas lancée" $?
nouveau; avec_worktree; RUNNER_CODE=127; lance -- feat/x
code_et "runner : un autre code non nul est transmis dans la phrase" 38 "(code 127)"
nouveau; avec_worktree; RUNNER_MOVE=1; lance -- feat/x
code_et "sommet de la branche déplacé pendant le runner : code 40" 40 "finish_worktree : la branche a changé pendant le runner ; rien n'est changé"
intact "40"
[ "$(appels check)" -eq 1 ] && ! contient "runner complet vert"; verifie "40 : la seconde vérification n'est pas lancée, pas de ligne « runner vert »" $?
nouveau; avec_worktree; RUNNER_MOVE=1; RUNNER_CODE=1; lance -- feat/x
code_et "runner rouge et sommet déplacé : le code du runner d'abord (38)" 38
# runner vert puis seconde vérification qui refuse
for def in "5|32|change OpenSpec non archivé" "7|34|main n'est pas à jour" "8|35|la branche ne contient pas main" "12|36|main est ouvert dans un autre dossier" "4|37|vérification préalable impossible (code 4)"; do
  IFS='|' read -r cc cw phrase <<EOF2
$def
EOF2
  nouveau; avec_worktree; CHECK_SEQ="0 $cc"; lance -- feat/x
  code_et "runner vert, seconde vérification code $cc : code $cw" "$cw" "$phrase"
  contient "finish_worktree : runner complet vert dans le worktree ; "; verifie "seconde vérification $cc : la ligne « runner vert » précède le refus" $?
  intact "seconde vérification $cc"
  [ "$(appels check)" -eq 2 ] && [ "$(appels runner)" -eq 1 ]; verifie "seconde vérification $cc : deux contrôles, un runner" $?
  ! contient "worktree retiré"; verifie "seconde vérification $cc : le worktree n'est pas retiré" $?
done
# test-speed-2, groupe 0 : les trois variables du saut, exportées dans l'environnement du script, n'atteignent pas le runner du worktree
nouveau; avec_worktree; export FINISH_BRANCH_TESTED_TOKEN=jeton-etranger FINISH_BRANCH_FORCE_RUN=1 FINISH_WORKTREE_ALLOW_SKIP=1; lance -- feat/x
unset FINISH_BRANCH_TESTED_TOKEN FINISH_BRANCH_FORCE_RUN FINISH_WORKTREE_ALLOW_SKIP
code_et "variables du saut exportées : succès" 0 "faux : fin lancée"
[ "$(cat "$cas/env-runner" 2>/dev/null)" = "jeton=absent force=absent saut=absent" ]; rc=$?; SORTIE="$(cat "$cas/env-runner" 2>&1)"; verifie "le runner du worktree ne reçoit aucune des trois variables du saut" $rc
# l'ordre des étapes et l'environnement du runner (dossier, entrée vide, variables réservées absentes)
nouveau; avec_worktree; export PMZILLA_NO_EVALS=1 PMZILLA_SKIP_GREEN_CHECK=1; lance -- feat/x
unset PMZILLA_NO_EVALS PMZILLA_SKIP_GREEN_CHECK
code_et "succès avec runner : code 0" 0 "faux : fin lancée"
[ "$(awk '{printf "%s%s,", $1, ($1=="check" ? " " $2 : "")}' "$ORDER_LOG")" = "check 1,runner,check 2,finish," ]; rc=$?; SORTIE="$(cat "$ORDER_LOG")"; verifie "l'ordre : contrôle, runner, contrôle, fin de branche" $rc
ligne_de runner | grep -qF "pwd=$wt stdin=[]"; rc=$?; SORTIE="$(ligne_de runner)"; verifie "le runner tourne dans le worktree, entrée vide" $rc
ligne_de runner | grep -qF "no_evals=absente skip=absente"; verifie "le runner tourne sans les deux variables réservées" $?
ligne_de runner | grep -qF "wt=present"; verifie "le runner tourne avant le retrait" $?
ligne_de check 2 | grep -qF "wt=present"; verifie "la seconde vérification précède le retrait" $?
ligne_de finish | grep -qF "wt=absent"; verifie "la fin de branche tourne après le retrait" $?
ligne_de check 2 | grep -qF "args=feat/x pwd=$ws stdin=[]"; rc=$?; SORTIE="$(ligne_de check 2)"; verifie "la seconde vérification : workspace, branche, entrée vide" $rc
nouveau; avec_worktree; lance -- feat/x
awk '/vérification préalable réussie/{a=NR} /lancement du runner complet dans le worktree/{b=NR} /runner complet vert dans le worktree ; /{c=NR} /worktree retiré/{d=NR} /faux : fin lancée/{e=NR} END {exit !(a && b && c && d && e && a<b && b<c && c<d && d<e)}' <<< "$SORTIE"; verifie "l'ordre des lignes : vérification, lancement, runner vert, retrait, fin" $?
! printf '%s' "$SORTIE" | grep -q '—'; verifie "aucun tiret cadratin dans la sortie" $?

# --- succès
nouveau; avec_worktree; FAKE_CODE=0
rm -f "$FAKE_TRACE"; SORTIE=$(cd "$ws" && echo intrus | "$BASH_FIN" "$script" feat/x 2>&1); CODE=$?
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

# --- worktree dans un sous-dossier `worktrees` du dossier du lab (lab-folder-layout, D4) : trouvé, retiré et terminé comme à la racine
nouveau; mkdir -p "$cas/worktrees"; wt="$cas/worktrees/wt-feat-x"; export WT_PATH="$wt"; git worktree add -q -b feat/x "$wt" main; FAKE_CODE=0; lance -- feat/x
code_et "worktree dans le dossier des worktrees : code 0 et retiré" 0 "worktree retiré : $wt"
[ ! -e "$wt" ] && [ -d "$cas/worktrees" ]; verifie "dossier des worktrees : worktree supprimé, dossier des worktrees laissé" $?
[ "$(appels finish)" -eq 1 ] && [ "$(sed -n 2p "$FAKE_TRACE")" = "$ws" ] && [ "$(sed -n 1p "$FAKE_TRACE")" = "feat/x" ]
verifie "dossier des worktrees : la fin de branche a tourné dans le workspace, sur la branche" $?

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

# --- signature d'environnement (test-speed D9, tâche 2.1) : tools/finish_env.sh, module sourcé par les deux scripts de fin
module="$(dirname "$script")/finish_env.sh"
for v in 1 2; do mkdir -p "$tmp/fx$v"; printf '#!/bin/sh\necho "uv %s.0"\n' "$v" > "$tmp/fx$v/uv"; chmod +x "$tmp/fx$v/uv"; done
mkdir -p "$tmp/fxko"; printf '#!/bin/sh\nexit 1\n' > "$tmp/fxko/uv"; chmod +x "$tmp/fxko/uv"
signature() { # dossier [PATH] : signature calculée dans le dossier (sortie et code dans SORTIE et CODE)
  SORTIE=$(cd "$1" && PATH="${2:-$PATH}" bash -c '. "$1" && finish_env_signature' sh "$module" 2>&1); CODE=$?
}
nouveau; avec_worktree; export PMZILLA_LAB_WORKSPACE="$ws"
signature "$ws" "$tmp/fx1:$PATH"; sig_ws=$SORTIE; code_ws=$CODE
printf '%s' "$sig_ws" | grep -qE '^[0-9a-f]{64}$'; rc=$?; SORTIE="$sig_ws (code $code_ws)"; verifie "signature : un condensé hexadécimal de 64 caractères, rien d'autre" $rc
signature "$wt" "$tmp/fx1:$PATH"; sig_wt=$SORTIE
[ "$sig_ws" = "$sig_wt" ]; rc=$?; SORTIE="$sig_ws / $sig_wt"; verifie "signature : la même dans le worktree et dans l'espace de travail" $rc
! printf '%s' "$sig_ws" | grep -qF "$tmp"; verifie "signature : aucun chemin dans la sortie" $?
signature "$ws" "$tmp/fx2:$PATH"; sig_autre=$SORTIE
[ "$sig_ws" != "$sig_autre" ] && printf '%s' "$sig_autre" | grep -qE '^[0-9a-f]{64}$'; rc=$?; SORTIE="$sig_autre"; verifie "signature : différente quand la version d'un outil change" $rc
signature "$ws" "$tmp/fxko:$PATH"
[ "$CODE" -ne 0 ] && [ -z "$SORTIE" ]; rc=$?; SORTIE="code $CODE, sortie « $SORTIE »"; verifie "signature : un outil en échec ne donne aucune signature" $rc
git config core.hooksPath "$tmp/crochets"; signature "$ws" "$tmp/fx1:$PATH"
[ "$SORTIE" != "$sig_ws" ] && printf '%s' "$SORTIE" | grep -qE '^[0-9a-f]{64}$'; verifie "signature : différente quand core.hooksPath change" $?
git config --unset core.hooksPath
signature "$ws" "$tmp/fx1:$PATH"; [ "$SORTIE" = "$sig_ws" ]; verifie "signature : retrouvée quand le réglage revient" $?
PMZILLA_LAB_WORKSPACE="$tmp/absent" signature "$ws" "$tmp/fx1:$PATH"
[ "$CODE" -ne 0 ] && [ -z "$(printf '%s' "$SORTIE" | grep -E '^[0-9a-f]{64}$')" ]; rc=$?; SORTIE="code $CODE : $SORTIE"; verifie "signature : le module des dossiers en échec ne donne aucune signature" $rc
# lancé directement (bash tools/finish_env.sh) : la signature et le nom des composants, jamais leurs valeurs ; sourcé, rien ne sort
direct() { # dossier [PATH] : lancement direct du module dans le dossier (sortie et code dans SORTIE et CODE)
  SORTIE=$(cd "$1" && PATH="${2:-$PATH}" bash "$module" 2>&1); CODE=$?
}
direct "$ws" "$tmp/fx1:$PATH"; code_d=$CODE; sortie_d=$SORTIE
[ "$code_d" -eq 0 ]; rc=$?; SORTIE="code $code_d :: $sortie_d"; verifie "lancement direct : code 0" $rc
[ "$(printf '%s\n' "$sortie_d" | grep -cE '^signature=[0-9a-f]{64}$')" -eq 1 ]; rc=$?; SORTIE=$sortie_d; verifie "lancement direct : une ligne signature de 64 hexadécimaux" $rc
[ "$(printf '%s\n' "$sortie_d" | sed -n 's/^signature=//p')" = "$sig_ws" ]; rc=$?; SORTIE="$sortie_d / $sig_ws"; verifie "lancement direct : la signature égale celle calculée en sourçant le module dans le même dossier" $rc
[ "$(printf '%s\n' "$sortie_d" | grep -c '^composants=')" -eq 1 ] && [ "$(printf '%s\n' "$sortie_d" | sed -n 's/^composants=//p')" = "python3 uv git bash dossier-de-contenu arbre-d-execution dossier-de-donnees dossier-des-hooks core.hooksPath" ]; rc=$?; SORTIE=$sortie_d; verifie "lancement direct : une ligne des noms de composants" $rc
[ "$(printf '%s\n' "$sortie_d" | wc -l | tr -d ' ')" -eq 2 ]; rc=$?; SORTIE=$sortie_d; verifie "lancement direct : deux lignes, rien d'autre" $rc
! printf '%s' "$sortie_d" | grep -qF "$tmp"; rc=$?; SORTIE=$sortie_d; verifie "lancement direct : aucun chemin du dépôt temporaire" $rc
! printf '%s' "$sortie_d" | grep -qF "uv 1.0"; rc=$?; SORTIE=$sortie_d; verifie "lancement direct : aucune version d'outil" $rc
direct "$ws" "$tmp/fxko:$PATH"; code_k=$CODE; sortie_k=$SORTIE
[ "$code_k" -ne 0 ]; rc=$?; SORTIE="code $code_k :: $sortie_k"; verifie "lancement direct, outil en échec : code non nul" $rc
! printf '%s\n' "$sortie_k" | grep -q '^signature='; rc=$?; SORTIE=$sortie_k; verifie "lancement direct, outil en échec : aucune ligne signature" $rc
! printf '%s' "$sortie_k" | grep -qF "$tmp"; rc=$?; SORTIE=$sortie_k; verifie "lancement direct, outil en échec : aucun chemin dans le message" $rc
SORTIE=$(cd "$ws" && PATH="$tmp/fx1:$PATH" bash -c '. "$1"' sh "$module" 2>&1); CODE=$?
[ "$CODE" -eq 0 ] && [ -z "$SORTIE" ]; rc=$?; SORTIE="code $CODE, sortie « $SORTIE »"; verifie "sourcé : aucune sortie, code 0" $rc
unset PMZILLA_LAB_WORKSPACE

# --- la signature de la fiche est celle du worktree où le runner a tourné (D9), pas celle de l'espace de travail
# Le saut est permis par défaut : les cas de la fiche ci-dessous posent quand même FINISH_WORKTREE_ALLOW_SKIP=1 (valeur exacte),
# jusqu'à la section « saut permis par défaut » qui retire le réglage.
export FINISH_WORKTREE_ALLOW_SKIP=1
nouveau; avec_worktree
mkdir -p "$tmp/fxcwd"
printf '#!/bin/sh\ncase "$PWD" in "%s"*) echo "uv 7.0" ;; *) echo "uv 8.0" ;; esac\n' "$wt" > "$tmp/fxcwd/uv"; chmod +x "$tmp/fxcwd/uv"
signature "$wt" "$tmp/fxcwd:$PATH"; sig_wt_cwd=$SORTIE
signature "$ws" "$tmp/fxcwd:$PATH"; sig_ws_cwd=$SORTIE
[ "$sig_wt_cwd" != "$sig_ws_cwd" ]; rc=$?; SORTIE="$sig_wt_cwd / $sig_ws_cwd"; verifie "fiche : (préalable) l'outil factice donne deux signatures selon le dossier" $rc
RUNNER_FP=tip; PATH="$tmp/fxcwd:$PATH" lance -- feat/x
[ "$(sed -n 's/^env=//p' "$fiche")" = "$sig_wt_cwd" ]; rc=$?; SORTIE="$(cat "$fiche" 2>&1)"; verifie "fiche : la signature est celle du worktree, pas celle de l'espace de travail" $rc

# --- la fiche de fin (D5, D6, D11, tâche 2.2) : écrite seulement si l'empreinte complète du worktree égale l'arbre du sommet
nouveau; avec_worktree; RUNNER_FP=tip; lance -- feat/x
sortie_lancee=$SORTIE
sommet=$(git -C "$ws" rev-parse feat/x); arbre=$(git -C "$ws" rev-parse 'feat/x^{tree}')
code_et "fiche : empreinte du sommet présente, code 0" 0 "finish_worktree : runner complet vert dans le worktree ; fiche de fin écrite : le script de fin ne le relancera pas si l'arbre fusionné est le même"
[ -f "$fiche" ]; verifie "fiche : le fichier existe dans le dossier Git commun" $?
[ "$(sed -n 's/^format=//p' "$fiche")" = 1 ] && [ "$(sed -n 's/^branch=//p' "$fiche")" = feat/x ] && [ "$(sed -n 's/^tip=//p' "$fiche")" = "$sommet" ] && [ "$(sed -n 's/^tree=//p' "$fiche")" = "$arbre" ]; rc=$?; SORTIE="$(cat "$fiche" 2>&1)"; verifie "fiche : version, branche, sommet et arbre" $rc
sed -n 's/^env=//p' "$fiche" | grep -qE '^[0-9a-f]{64}$'; verifie "fiche : signature d'environnement hexadécimale" $?
jeton=$(sed -n 's/^token=//p' "$fiche"); printf '%s' "$jeton" | grep -qE '^[0-9a-f]{32}$'; rc=$?; SORTIE="$jeton"; verifie "fiche : jeton de 128 bits en hexadécimal" $rc
[ -n "$(sed -n 's/^date=//p' "$fiche")" ]; verifie "fiche : une date" $?
[ -n "$(find "$fiche" -perm 600)" ]; verifie "fiche : lisible par son propriétaire seul" $?
! grep -qF "$tmp" "$fiche"; rc=$?; SORTIE="$(cat "$fiche")"; verifie "fiche : aucun chemin du worktree ni de l'espace de travail" $rc
[ "$(find "$ws/.git" -maxdepth 1 -name 'pmzilla-finish-tested*' | wc -l | tr -d ' ')" -eq 1 ]; verifie "fiche : écrite par renommage, aucun fichier temporaire resté" $?
[ "$(sed -n 's/^jeton://p' "$FAKE_TRACE")" = "$jeton" ]; rc=$?; SORTIE="$(cat "$FAKE_TRACE")"; verifie "fiche : le script de fin reçoit le jeton dans FINISH_BRANCH_TESTED_TOKEN" $rc
! printf '%s' "$sortie_lancee" | grep -qF "$jeton"; verifie "fiche : le jeton n'est jamais affiché" $?
[ "$(cat "$cas/fiche-vue")" = "$(cat "$fiche")" ]; rc=$?; SORTIE="fiche vue par le script de fin"; verifie "fiche : présente quand le script de fin tourne" $rc
[ ! -e "$(git -C "$ws" rev-parse --path-format=absolute --git-path pmzilla-run-all-ok)" ]; verifie "fiche : le script n'écrit aucune empreinte dans l'espace de travail" $?

nouveau; avec_worktree; RUNNER_FP=""; lance -- feat/x
code_et "fiche : empreinte absente, aucune fiche, la fin tourne" 0 "empreinte complète absente ou différente du sommet : le script de fin le relancera"
[ ! -e "$fiche" ] && [ "$(appels finish)" -eq 1 ]; verifie "fiche : aucune fiche, le script de fin est lancé" $?
[ "$(sed -n 's/^jeton://p' "$FAKE_TRACE")" != "absent" ]; rc=$?; SORTIE="$(cat "$FAKE_TRACE")"; verifie "fiche : sans fiche, le script de fin reçoit tout de même un jeton (il dira « fiche de fin absente »)" $rc
nouveau; avec_worktree; RUNNER_FP=autre; lance -- feat/x
code_et "fiche : empreinte différente du sommet" 0 "empreinte complète absente ou différente du sommet"
[ ! -e "$fiche" ]; verifie "fiche : empreinte différente, aucune fiche" $?
nouveau; avec_worktree; RUNNER_FP=tip; PATH="$tmp/fxko:$PATH" lance -- feat/x
code_et "fiche : signature impossible, aucune fiche" 0 "empreinte complète absente ou différente du sommet"
[ ! -e "$fiche" ]; verifie "fiche : signature impossible, aucune fiche écrite" $?
nouveau; avec_worktree; echo vieux > "$fiche"; RUNNER_FP=""; lance -- feat/x
[ ! -e "$fiche" ]; verifie "fiche : une ancienne fiche est effacée avant le runner" $?
nouveau; avec_worktree; echo vieux > "$fiche"; RUNNER_CODE=1; RUNNER_FP=tip; lance -- feat/x
code_et "fiche : runner rouge, code 38" 38 "le runner complet n'est pas vert dans le worktree (code 1)"
[ ! -e "$fiche" ]; verifie "fiche : après le code 38, aucune fiche (l'ancienne est effacée)" $?
nouveau; avec_worktree; RUNNER_MOVE=1; RUNNER_FP=tip; lance -- feat/x
code_et "fiche : sommet déplacé, code 40" 40 "la branche a changé pendant le runner"
[ ! -e "$fiche" ]; verifie "fiche : après le code 40, aucune fiche" $?
nouveau; avec_worktree; RUNNER_FP=tip; CHECK_SEQ="0 5"; lance -- feat/x
code_et "fiche : seconde vérification refusée, code 32" 32
[ "$(appels finish)" -eq 0 ]; verifie "fiche : seconde vérification refusée, le script de fin n'est pas lancé" $?

# --- revue du 2026-10-16, constat 1 : la fiche n'est écrite que si le worktree n'a pas bougé pendant le runner (D5)
# Trois conditions en plus de l'empreinte : (a) worktree propre au démarrage du runner, (b) propre à l'écriture de la fiche,
# (c) aucun fichier suivi modifié pendant le runner, même remis en état (repère posé avant le runner, hors de l'arbre de travail).
# Cas témoin : le runner attend sans rien toucher, la fiche est écrite.
nouveau; avec_worktree; RUNNER_FP=tip; RUNNER_EDIT=rien; lance -- feat/x
code_et "fiche témoin : le runner ne touche rien, fiche écrite" 0 "fiche de fin écrite"
[ -f "$fiche" ]; rc=$?; SORTIE="$(cat "$fiche" 2>&1)"; verifie "fiche témoin : la fiche existe" $rc
# (a) worktree propre au démarrage du runner : pas de test, le refus 28 le couvre (rien ne s'exécute dans le worktree entre le refus 28 et le runner) ; garde-fou d'une ligne dans le script.
# (b) Le faux runner laisse un fichier non suivi : seule la propreté à l'écriture manque (aucun fichier suivi touché). Le retrait refuse ensuite (30).
nouveau; avec_worktree; RUNNER_FP=tip; RUNNER_EDIT=nonsuivi; lance -- feat/x
code_et "fiche (b) : fichier non suivi laissé par le runner, ligne de relance" 30 "worktree modifié pendant le runner : le script de fin le relancera"
[ ! -e "$fiche" ]; rc=$?; SORTIE="$(cat "$fiche" 2>&1)"; verifie "fiche (b) : aucune fiche" $rc
# (b) avec un fichier suivi modifié et non remis en état
nouveau; avec_worktree; RUNNER_FP=tip; RUNNER_EDIT=suivi; lance -- feat/x
code_et "fiche (b) : fichier suivi laissé modifié par le runner, ligne de relance" 30 "worktree modifié pendant le runner : le script de fin le relancera"
[ ! -e "$fiche" ]; rc=$?; SORTIE="$(cat "$fiche" 2>&1)"; verifie "fiche (b) : fichier suivi modifié, aucune fiche" $rc
# (c) Le scénario du relecteur : un fichier suivi modifié puis remis exactement en état, index inchangé, empreinte égale au sommet, worktree propre
nouveau; avec_worktree; RUNNER_FP=tip; RUNNER_EDIT=retablit; lance -- feat/x
code_et "fiche (c) : fichier suivi modifié puis remis en état, code 0, ligne de relance" 0 "worktree modifié pendant le runner : le script de fin le relancera"
[ ! -e "$fiche" ]; rc=$?; SORTIE="$(cat "$fiche" 2>&1)"; verifie "fiche (c) : aucune fiche" $rc
[ -z "$(git -C "$ws" worktree list | grep -F "$wt")" ] && [ "$(appels finish)" -eq 1 ]; rc=$?; SORTIE="$(cat "$ORDER_LOG" 2>&1)"; verifie "fiche (c) : le script de fin est lancé (il relancera son runner)" $rc
# (c) par la date de changement d'état (ctime) : un renommage aller-retour et un chmod aller-retour, que la date de modification ne voit pas
nouveau; avec_worktree; RUNNER_FP=tip; RUNNER_EDIT=deplace; lance -- feat/x
code_et "fiche (c) : fichier suivi déplacé puis remis à sa place, code 0, ligne de relance" 0 "worktree modifié pendant le runner : le script de fin le relancera"
[ ! -e "$fiche" ]; rc=$?; SORTIE="$(cat "$fiche" 2>&1)"; verifie "fiche (c) déplacé : aucune fiche" $rc
nouveau; avec_worktree; RUNNER_FP=tip; RUNNER_EDIT=chmod; lance -- feat/x
code_et "fiche (c) : mode d'un fichier suivi changé puis remis, code 0, ligne de relance" 0 "worktree modifié pendant le runner : le script de fin le relancera"
[ ! -e "$fiche" ]; rc=$?; SORTIE="$(cat "$fiche" 2>&1)"; verifie "fiche (c) chmod : aucune fiche" $rc
# le repère est posé hors de l'arbre de travail (aucun fichier non suivi dans le worktree pendant le runner) et retiré après usage, quelle que soit l'issue
nouveau; avec_worktree; RUNNER_FP=tip; RUNNER_EDIT=retablit; lance -- feat/x
[ -z "$(find "$ws/.git" -name 'pmzilla-finish-repere*')" ]; rc=$?; SORTIE="repère resté"; verifie "fiche : le repère est retiré après une issue réussie" $rc
nouveau; avec_worktree; RUNNER_CODE=1; lance -- feat/x
[ -z "$(find "$ws/.git" -name 'pmzilla-finish-repere*')" ]; rc=$?; SORTIE="repère resté"; verifie "fiche : le repère est retiré après un runner rouge (38)" $rc
nouveau; avec_worktree; RUNNER_MOVE=1; lance -- feat/x
[ -z "$(find "$ws/.git" -name 'pmzilla-finish-repere*')" ]; rc=$?; SORTIE="repère resté"; verifie "fiche : le repère est retiré après un sommet déplacé (40)" $rc

# --- test-db-guards, D2 : les dossiers du worktree entrent dans le contrôle de stabilité (condition c, même repère, même ligne)
# Un dossier suivi renommé puis remis, un fichier non suivi créé puis supprimé (racine, sous-dossier) ne changent que la date de changement
# d'état d'un dossier : aucun fichier suivi n'est touché, le worktree est propre au début et à la fin, l'empreinte égale le sommet.
avec_dossier_suivi() { mkdir -p "$ws/dossier"; echo contenu > "$ws/dossier/a.txt"; git -C "$ws" add -A; git -C "$ws" commit -q -m "dossier suivi"; avec_worktree; }
nouveau; avec_dossier_suivi; RUNNER_FP=tip; RUNNER_EDIT=rien; lance -- feat/x
code_et "dossiers (c) témoin : un dossier suivi, le runner ne touche rien, fiche écrite" 0 "fiche de fin écrite"
for mode in dossier ephemere_racine ephemere_sous; do
  nouveau; avec_dossier_suivi; RUNNER_FP=tip; RUNNER_EDIT=$mode; lance -- feat/x; sortie_script=$SORTIE
  code_et "dossiers (c) $mode : code 0, ligne de relance" 0 "worktree modifié pendant le runner : le script de fin le relancera"
  [ ! -e "$fiche" ]; rc=$?; SORTIE="$(cat "$fiche" 2>&1)"; verifie "dossiers (c) $mode : aucune fiche" $rc
  [ "$(appels finish)" -eq 1 ]; rc=$?; SORTIE="$(cat "$ORDER_LOG" 2>&1)"; verifie "dossiers (c) $mode : le script de fin est lancé (il relancera son runner)" $rc
  ! printf '%s' "$sortie_script" | grep -qE 'ephemere|dossier\.bak|a\.txt|/dossier'; rc=$?; SORTIE="$sortie_script"; verifie "dossiers (c) $mode : aucun chemin du dossier ni du fichier dans la sortie" $rc
done

# --- la variable de relance forcée n'est jamais lue par ce script (D16, tâche 2.7)
nouveau; avec_worktree; RUNNER_FP=tip; export FINISH_BRANCH_FORCE_RUN=0; lance -- feat/x
unset FINISH_BRANCH_FORCE_RUN
code_et "relance forcée posée : le runner du worktree tourne quand même, fiche écrite" 0 "fiche de fin écrite"
[ "$(appels runner)" -eq 1 ] && [ -f "$fiche" ]; verifie "relance forcée posée : un runner, une fiche" $?
[ "$(sed -n 's/^force://p' "$FAKE_TRACE")" = 0 ] && [ "$(sed -n 's/^jeton://p' "$FAKE_TRACE")" = "$(sed -n 's/^token=//p' "$fiche")" ]; rc=$?; SORTIE="$(cat "$FAKE_TRACE")"; verifie "relance forcée posée : le script de fin reçoit le jeton et la variable inchangée" $rc
! grep -v '^[[:space:]]*#' "$script" | sed 's/ -u FINISH_BRANCH_FORCE_RUN / /' | grep -qF 'FINISH_BRANCH_FORCE_RUN'; rc=$?;   # le retrait « env -u » (groupe 0 de test-speed-2) n'est pas une lecture SORTIE="variable lue dans le code"; verifie "le script ne lit jamais FINISH_BRANCH_FORCE_RUN (hors commentaires)" $rc

# --- saut permis par défaut (skip-default-on, design D1) : le réglage FINISH_WORKTREE_ALLOW_SKIP absent, vide ou exactement « 1 » autorise la fiche
# Runner vert, empreinte égale au sommet, worktree stable : avec le réglage absent, vide ou « 1 », la fiche est écrite et le jeton passé ;
# avec toute autre valeur (« 0 », « oui », « 11 », une espace, « 1 » précédé d'une espace), aucune fiche, la ligne dédiée
# (sans nom de fichier ni chemin), le jeton passé quand même au script de fin.
unset FINISH_WORKTREE_ALLOW_SKIP
for valeur in absent vide 1; do
  nouveau; avec_worktree; RUNNER_FP=tip
  case $valeur in absent) unset FINISH_WORKTREE_ALLOW_SKIP ;; vide) export FINISH_WORKTREE_ALLOW_SKIP="" ;; *) export FINISH_WORKTREE_ALLOW_SKIP="$valeur" ;; esac
  lance -- feat/x
  unset FINISH_WORKTREE_ALLOW_SKIP
  code_et "saut permis (réglage $valeur) : fiche écrite" 0 "finish_worktree : runner complet vert dans le worktree ; fiche de fin écrite"
  [ -f "$fiche" ]; rc=$?; SORTIE="aucune fiche"; verifie "saut permis (réglage $valeur) : la fiche existe" $rc
  ! contient "saut non autorisé" && ! contient "réglage absent"; verifie "saut permis (réglage $valeur) : pas de ligne « saut non autorisé »" $?
  [ "$(sed -n 's/^jeton://p' "$FAKE_TRACE")" != "absent" ] && [ -n "$(sed -n 's/^jeton://p' "$FAKE_TRACE")" ]; rc=$?; SORTIE="$(cat "$FAKE_TRACE" 2>&1)"; verifie "saut permis (réglage $valeur) : le jeton est passé au script de fin" $rc
done
for valeur in 0 oui 11 " " " 1"; do
  nouveau; avec_worktree; RUNNER_FP=tip
  export FINISH_WORKTREE_ALLOW_SKIP="$valeur"
  lance -- feat/x
  unset FINISH_WORKTREE_ALLOW_SKIP; sortie_lancee=$SORTIE
  code_et "saut désactivé (réglage « $valeur ») : la fin tourne, ligne dédiée" 0 "finish_worktree : runner complet vert dans le worktree ; saut non autorisé (réglage désactivé) : le script de fin le relancera"
  ! printf '%s' "$sortie_lancee" | grep -qF "réglage absent"; rc=$?; SORTIE="$sortie_lancee"; verifie "saut désactivé (réglage « $valeur ») : jamais l'ancienne raison « réglage absent »" $rc
  [ ! -e "$fiche" ]; rc=$?; SORTIE="$(cat "$fiche" 2>&1)"; verifie "saut désactivé (réglage « $valeur ») : aucune fiche écrite" $rc
  [ "$(appels runner)" -eq 1 ] && [ "$(appels finish)" -eq 1 ]; rc=$?; SORTIE="$(cat "$ORDER_LOG" 2>&1)"; verifie "saut désactivé (réglage « $valeur ») : un runner, puis la fin de branche" $rc
  [ "$(sed -n 's/^jeton://p' "$FAKE_TRACE")" != "absent" ] && [ -n "$(sed -n 's/^jeton://p' "$FAKE_TRACE")" ]; rc=$?; SORTIE="$(cat "$FAKE_TRACE" 2>&1)"; verifie "saut désactivé (réglage « $valeur ») : le jeton est passé quand même au script de fin" $rc
  ligne_saut=$(printf '%s\n' "$sortie_lancee" | grep -F 'saut non autorisé')
  ! printf '%s' "$sortie_lancee" | grep -qF -e "fiche de fin écrite" -e "empreinte complète absente" && [ -n "$ligne_saut" ] && ! printf '%s' "$ligne_saut" | grep -qF -e pmzilla -e "$tmp" -e '/'; rc=$?; SORTIE="$sortie_lancee"; verifie "saut désactivé (réglage « $valeur ») : ni « fiche écrite », ni nom de fichier, ni chemin dans la ligne dédiée" $rc
done
# le réglage n'efface pas les autres lignes : worktree modifié ou empreinte absente, la ligne d'origine reste (le réglage ne change rien tant que le saut serait refusé)
for valeur in absent 0; do
  if [ "$valeur" = absent ]; then unset FINISH_WORKTREE_ALLOW_SKIP; else export FINISH_WORKTREE_ALLOW_SKIP="$valeur"; fi
  nouveau; avec_worktree; RUNNER_FP=tip; RUNNER_EDIT=retablit; lance -- feat/x
  code_et "réglage $valeur : worktree modifié pendant le runner, la ligne d'origine" 0 "worktree modifié pendant le runner : le script de fin le relancera"
  [ ! -e "$fiche" ] && ! contient "saut non autorisé"; rc=$?; verifie "réglage $valeur : worktree modifié, ni fiche ni ligne du réglage" $rc
  nouveau; avec_worktree; RUNNER_FP=""; lance -- feat/x
  code_et "réglage $valeur : empreinte absente, la ligne d'origine" 0 "empreinte complète absente ou différente du sommet : le script de fin le relancera"
  [ ! -e "$fiche" ] && ! contient "saut non autorisé"; rc=$?; verifie "réglage $valeur : empreinte absente, ni fiche ni ligne du réglage" $rc
  unset FINISH_WORKTREE_ALLOW_SKIP
done
# le script lit le réglage par une comparaison exacte à 1 (et le nomme dans son en-tête)
grep -v '^[[:space:]]*#' "$script" | grep -F 'FINISH_WORKTREE_ALLOW_SKIP' | grep -qF '= "1" ]'; rc=$?; SORTIE="comparaison exacte absente"; verifie "le script désactive le saut pour toute valeur de FINISH_WORKTREE_ALLOW_SKIP autre que 1 exactement (absent ou vide valent 1)" $rc
grep -q '^#   FINISH_WORKTREE_ALLOW_SKIP ' "$script"; rc=$?; SORTIE="en-tête"; verifie "FINISH_WORKTREE_ALLOW_SKIP est dans le bloc des variables de l'en-tête" $rc
grep -q 'FINISH_WORKTREE_ALLOW_SKIP' "$(dirname "$script")/../docs/pmzilla/installation.md"; rc=$?; SORTIE="guide"; verifie "le guide d'installation nomme FINISH_WORKTREE_ALLOW_SKIP" $rc
! grep -q 'réglage absent' "$script"; rc=$?; SORTIE="ancienne raison présente"; verifie "le script n'imprime plus « réglage absent » (skip-default-on)" $rc
grep '^#' "$script" | grep -q 'réglage désactivé' && grep '^#' "$script" | grep -qF '« 0 »'; rc=$?; SORTIE="en-tête"; verifie "l'en-tête dit que la valeur 0 désactive le saut" $rc
grep -c 'FINISH_WORKTREE_ALLOW_SKIP:-' "$script" | grep -qx 1; rc=$?; SORTIE="plusieurs tests du réglage"; verifie "un seul test du réglage dans le script (D1)" $rc

# --- test-speed-2, D12 : aucun autre processus n'a son dossier courant dans le worktree, avant et après le runner (réglage à 1, empreinte du sommet)
L_AUTRE="finish_worktree : runner complet vert dans le worktree ; un autre processus a son dossier courant dans le worktree : le script de fin le relancera"
L_IMPOSSIBLE="finish_worktree : runner complet vert dans le worktree ; vérification des processus impossible : le script de fin le relancera"
proc() { # séquence-de-modes-lsof : un lancement complet, réglage à 1, empreinte du sommet écrite par le faux runner
  nouveau; avec_worktree; RUNNER_FP=tip; LSOF_SEQ="$1"; export LSOF_SEQ
  FINISH_WORKTREE_ALLOW_SKIP=1 lance -- feat/x
}
proc rien
code_et "processus : aucun autre, fiche écrite" 0 "fiche de fin écrite"
[ -f "$fiche" ] && [ "$(cat "$LSOF_COUNT")" -eq 2 ]; rc=$?; SORTIE="listages : $(cat "$LSOF_COUNT" 2>&1)"; verifie "processus : fiche présente, deux listages (avant et après le runner)" $rc
[ "$(sort -u "$cas/lsof-args")" = "args=-w -n -P -d cwd -F pn" ]; rc=$?; SORTIE="$(cat "$cas/lsof-args" 2>&1)"; verifie "processus : lsof est appelé avec -w -n -P -d cwd -F pn" $rc
proc "autre rien"
code_et "processus : un autre au premier listage, aucune fiche, la ligne dédiée" 0 "$L_AUTRE"
[ ! -e "$fiche" ] && [ "$(appels finish)" -eq 1 ] && [ "$(cat "$LSOF_COUNT")" -eq 2 ]; verifie "processus : au premier listage, aucune fiche, le script de fin est lancé, deux listages" $?
! contient "424242" && ! contient "lsof"; verifie "processus : ni numéro de processus ni nom de commande dans la sortie" $?
proc "rien autre"
code_et "processus : un autre au second listage, aucune fiche, la ligne dédiée" 0 "$L_AUTRE"
[ ! -e "$fiche" ]; verifie "processus : au second listage, aucune fiche" $?
proc "autre autre"
code_et "processus : un autre aux deux listages, la ligne dédiée une seule fois" 0 "$L_AUTRE"
[ "$(printf '%s\n' "$SORTIE" | grep -cF "un autre processus a son dossier courant")" -eq 1 ] && [ ! -e "$fiche" ]; verifie "processus : aux deux listages, une seule ligne, aucune fiche" $?
proc sous
code_et "processus : dossier courant dans un sous-dossier du worktree" 0 "$L_AUTRE"
[ ! -e "$fiche" ]; verifie "processus : sous-dossier, aucune fiche" $?
proc voisin
code_et "processus : dossier au nom voisin hors du worktree, ignoré, fiche écrite" 0 "fiche de fin écrite"
[ -f "$fiche" ]; verifie "processus : dossier voisin, fiche présente" $?
for mode in sanssoi vide code1; do
  proc "$mode"
  code_et "processus : vérification impossible (liste $mode), la ligne dédiée" 0 "$L_IMPOSSIBLE"
  [ ! -e "$fiche" ] && [ "$(appels finish)" -eq 1 ]; verifie "processus : liste $mode, aucune fiche, le script de fin est lancé" $?
  ! contient "424242" && ! contient "lsof"; verifie "processus : liste $mode, ni numéro ni nom de commande dans la sortie" $?
done
# lsof absent du PATH
sans="$tmp/sanslsof"; mkdir -p "$sans"
for outil in git uv python3; do p=$(command -v "$outil" 2>/dev/null) && ln -sf "$p" "$sans/$outil"; done
PATH="$sans:/usr/bin:/bin" command -v lsof >/dev/null 2>&1; rc=$?; SORTIE="lsof présent dans /usr/bin ou /bin : le cas « absent » n'est pas réalisable ici"; [ $rc -ne 0 ]; verifie "processus : précondition, lsof n'est pas dans le PATH réduit" $?
nouveau; avec_worktree; RUNNER_FP=tip; FINISH_WORKTREE_ALLOW_SKIP=1 PATH="$sans:/usr/bin:/bin" lance -- feat/x
code_et "processus : lsof absent, vérification impossible, aucune fiche" 0 "$L_IMPOSSIBLE"
[ ! -e "$fiche" ] && [ "$(appels finish)" -eq 1 ]; verifie "processus : lsof absent, aucune fiche, le script de fin est lancé" $?
# l'ordre des conditions : (b) et (c) d'abord, puis le processus, puis l'empreinte, puis le réglage
nouveau; avec_worktree; RUNNER_FP=tip; RUNNER_EDIT=nonsuivi; LSOF_SEQ=autre; FINISH_WORKTREE_ALLOW_SKIP=1 lance -- feat/x
code_et "ordre : worktree modifié (b) avant le processus" 30 "worktree modifié pendant le runner : le script de fin le relancera"
! contient "un autre processus"; verifie "ordre : worktree modifié, la ligne du processus n'est pas écrite" $?
nouveau; avec_worktree; RUNNER_FP=""; LSOF_SEQ=autre; FINISH_WORKTREE_ALLOW_SKIP=1 lance -- feat/x
code_et "ordre : le processus avant l'empreinte absente" 0 "$L_AUTRE"
nouveau; avec_worktree; RUNNER_FP=tip; LSOF_SEQ=autre; lance -- feat/x
code_et "ordre : le processus avant le réglage désactivé" 0 "$L_AUTRE"
nouveau; avec_worktree; RUNNER_FP=tip; LSOF_SEQ=autre; FINISH_WORKTREE_ALLOW_SKIP=1 lance -- feat/x
[ "$(sed -n 's/^jeton://p' "$FAKE_TRACE")" != "absent" ]; rc=$?; SORTIE="$(cat "$FAKE_TRACE")"; verifie "processus trouvé : le jeton est tout de même passé au script de fin" $rc
# runner rouge : le code 38 est rendu comme avant, quel que soit le listage
nouveau; avec_worktree; RUNNER_CODE=1; LSOF_SEQ=autre; FINISH_WORKTREE_ALLOW_SKIP=1 lance -- feat/x
code_et "processus trouvé et runner rouge : le code 38 d'abord" 38 "le runner complet n'est pas vert dans le worktree (code 1)"
# le vrai lsof : un processus d'arrière-plan dans le worktree, puis aucun
nouveau; avec_worktree; RUNNER_FP=tip
( cd "$wt" && exec sleep 300 ) & fond=$!
sleep 1
FINISH_WORKTREE_ALLOW_SKIP=1 PATH="$PATH_REEL" lance -- feat/x
kill "$fond" 2>/dev/null; wait "$fond" 2>/dev/null
code_et "vrai lsof : un processus d'arrière-plan dans le worktree, aucune fiche, la ligne dédiée" 0 "$L_AUTRE"
[ ! -e "$fiche" ]; verifie "vrai lsof : aucune fiche" $?
! contient "$fond" && ! contient "sleep"; verifie "vrai lsof : ni numéro ni nom de commande dans la sortie" $?
nouveau; avec_worktree; RUNNER_FP=tip
FINISH_WORKTREE_ALLOW_SKIP=1 PATH="$PATH_REEL" lance -- feat/x
code_et "vrai lsof : aucun autre processus, fiche écrite" 0 "fiche de fin écrite"
[ -f "$fiche" ]; verifie "vrai lsof : fiche présente" $?
LSOF_SEQ=rien; export LSOF_SEQ

# --- de bout en bout (tâche 2.4) : vrai finish_branch.sh, faux runners, vrai hook pre-push ; un seul lancement du runner en tout avec le réglage à 1
for mode in 1 absent 0 force; do
nouveau_reel; avec_worktree; echo code > "$wt/g.txt"; git -C "$wt" add -A; git -C "$wt" commit -q -m "travail"
mkdir -p "$cas/data"; ln -sf "$(dirname "$script")/hooks/pre-push" "$ws/.git/hooks/pre-push"
avec_crochets   # finish-under-lock 5.3 (relecture du 2026-10-20) : le vrai finish_branch.sh fusionne dans main et déplace main sous le verrou, crochets installés
export PMZILLA_LAB_WORKSPACE="$ws" PMZILLA_LAB_RUN="$cas/run" PMZILLA_LAB_DATA="$cas/data" DB_BACKUP_SAUVEGARDES="$cas/sauvegardes"
export FINISH_BRANCH_RUNNER="echo 'runner-fin x' >> $ORDER_LOG" PRE_PUSH_RUNNER="echo 'hook x' >> $ORDER_LOG" FINISH_BRANCH_RECORDS="$cas/essais"
RUNNER_FP=tip; fin_sauvee=$FINISH_WORKTREE_FINISH; unset FINISH_WORKTREE_FINISH
case $mode in 1|0) export FINISH_WORKTREE_ALLOW_SKIP=$mode ;; *) unset FINISH_WORKTREE_ALLOW_SKIP ;; esac
[ "$mode" = force ] && export FINISH_BRANCH_FORCE_RUN=1
lance -- feat/x
unset FINISH_WORKTREE_ALLOW_SKIP FINISH_BRANCH_FORCE_RUN
export FINISH_WORKTREE_FINISH=$fin_sauvee; unset FINISH_BRANCH_RUNNER PRE_PUSH_RUNNER FINISH_BRANCH_RECORDS PMZILLA_LAB_WORKSPACE PMZILLA_LAB_RUN PMZILLA_LAB_DATA DB_BACKUP_SAUVEGARDES
code_et "bout en bout (réglage $mode) : la fin réussit" 0 "finish_branch : terminé"
if [ "$mode" = 1 ] || [ "$mode" = absent ]; then
  contient "second lancement sauté"; verifie "bout en bout (réglage $mode) : la ligne de saut est affichée" $?
  [ "$(appels runner)" -eq 1 ] && [ "$(appels runner-fin)" -eq 0 ] && [ "$(appels hook)" -eq 0 ]; rc=$?; SORTIE="$(cat "$ORDER_LOG")"; verifie "bout en bout (réglage $mode) : un seul lancement du runner (celui du worktree), ni runner de fin ni runner du hook" $rc
  [ "$(cat "$ws/.git/pmzilla-run-all-ok")" = "$(git -C "$ws" rev-parse 'main^{tree}')" ]; verifie "bout en bout (réglage $mode) : l'empreinte complète de l'espace de travail égale l'arbre de main" $?
else
  if [ "$mode" = force ]; then raison_fin="relance forcée"; else raison_fin="saut non autorisé (réglage désactivé)"; fi
  contient "second lancement nécessaire : $raison_fin" && ! contient "second lancement sauté" && ! contient "réglage absent"; verifie "bout en bout (réglage $mode) : la raison du second lancement est affichée, aucun saut" $?
  [ "$(appels runner)" -eq 1 ] && [ "$(appels runner-fin)" -eq 1 ]; rc=$?; SORTIE="$(cat "$ORDER_LOG")"; verifie "bout en bout (réglage $mode) : deux lancements du runner, celui du worktree puis celui de la fin" $rc
  [ "$(awk '$1=="runner" {a=NR} $1=="runner-fin" {b=NR} END {print (a && b && a<b) ? "ordre" : "desordre"}' "$ORDER_LOG")" = ordre ]; rc=$?; SORTIE="$(cat "$ORDER_LOG")"; verifie "bout en bout (réglage $mode) : le runner du worktree précède celui de la fin" $rc
fi
[ "$(git -C "$ws" rev-parse main)" = "$(git --git-dir="$cas/distant.git" rev-parse main)" ] && [ "$(git -C "$ws" rev-list --parents -n1 main | wc -w)" -eq 3 ]; verifie "bout en bout (réglage $mode) : main fusionné et poussé" $?
[ ! -e "$fiche" ]; verifie "bout en bout (réglage $mode) : la fiche est consommée ou jamais écrite" $?
done

# --- faux lsof sous un parent qui nomme déjà le script de fin (idée #362) : il rend le plus proche ancêtre qui le nomme, pas le plus haut
# (sous un vrai script de fin, le plus haut est le vrai script et non celui du cas). Trois shells imbriqués, le plus haut et le plus bas nomment le script (en $0), celui du milieu non ; aucun vrai script n'est lancé.
rep362="$tmp/cas-362"; mkdir -p "$rep362"
export NOM362="tools/finish_worktree.sh"   # passé par l'environnement : le texte des shells intermédiaires ne doit pas nommer le script
LSOF_COUNT="$rep362/compte" LSOF_SEQ=rien sh -c 'sh -c '\''sh -c "echo \$\$ > \"\$1\"; lsof -F pn > \"\$2\"; :" "$NOM362" "$1" "$2"; :'\'' intermediaire "$1" "$2"; :' "$NOM362" "$rep362/pid-proche" "$rep362/liste" </dev/null
SORTIE="proche=$(cat "$rep362/pid-proche" 2>&1) liste=$(cat "$rep362/liste" 2>&1)"
[ -s "$rep362/pid-proche" ] && [ "$(sed -n 1p "$rep362/liste")" = "p$(cat "$rep362/pid-proche")" ]; verifie "faux lsof : sous deux parents qui nomment le script, il rend le plus proche (pas le plus haut)" $?

# --- verrou de fin de branche (change multi-session-piloting, D5 et D6, tâche 5.2) : code 42, verrou tenu sur tout le run, jeton passé au contrôle,
# au runner et au script de fin, note de la branche retirée seulement après une sortie 0, aide. Faux contrôle, faux runner et faux script de fin
# communs : ils journalisent, dans $cas/gel-log, le rôle, la présence du jeton, l'existence du verrou et l'égalité du jeton avec celui du verrou.
fauxgel="$tmp/faux_gel.sh"
cat > "$fauxgel" <<'FAUX'
#!/bin/bash
commun=$(git rev-parse --path-format=absolute --git-common-dir)
verrou="$commun/pmzilla-fin-en-cours"
egal=non; [ -n "${FINISH_LOCK_TOKEN:-}" ] && [ "$(cat "$verrou/jeton" 2>/dev/null)" = "$FINISH_LOCK_TOKEN" ] && egal=oui
printf '%s jeton=%s verrou=%s egal=%s\n' "$1" "${FINISH_LOCK_TOKEN:+pose}" "$([ -d "$verrou" ] && echo oui || echo non)" "$egal" >> "$GEL_LOG"
printf '%s' "${FINISH_LOCK_TOKEN:-}" > "$GEL_LOG.jeton-$1"
[ "$1" != runner ] || { [ -z "${GEL_RUNNER_SLEEP:-}" ] || { echo $$ > "$GEL_LOG.pid-runner"; exec sleep 30; }; exit "${GEL_RUNNER_CODE:-0}"; }
exit 0
FAUX
fin_ancien=$FINISH_WORKTREE_FINISH; check_ancien=$FINISH_WORKTREE_CHECK; runner_ancien=$FINISH_WORKTREE_RUNNER
export FINISH_WORKTREE_FINISH="bash $fauxgel fin" FINISH_WORKTREE_CHECK="bash $fauxgel check" FINISH_WORKTREE_RUNNER="bash $fauxgel runner"
pose_verrou() { # pid jeton [âge en secondes] : verrou factice dans le dossier Git commun du cas
  gel="$ws/.git/pmzilla-fin-en-cours"; rm -rf "$gel"; mkdir -p "$gel"
  printf '%s\n' "$1" > "$gel/pid"; echo $(( $(date +%s) - ${3:-600} )) > "$gel/debut"; printf 'feat/autre\n' > "$gel/branche"; printf '%s\n' "$2" > "$gel/jeton"
}
etat_verrou() { (cd "$ws/.git/pmzilla-fin-en-cours" 2>/dev/null && cat pid debut branche jeton); }
hhmm() { date -r "$1" +%H:%M 2>/dev/null || date -d "@$1" +%H:%M; }
mort=$(sh -c 'echo $$')   # numéro d'un processus qui n'existe plus
ecrit_note() { mkdir -p "$ws/.git/pmzilla-notes"; printf 'prête pour la fin\n' > "$ws/.git/pmzilla-notes/$1"; }
export GEL_LOG="$tmp/gel-log" GEL_RUNNER_CODE=0
unset GEL_RUNNER_SLEEP

# code 42 : un verrou vivant d'un autre jeton ; rien n'est changé, aucun faux script n'est lancé, la note reste
nouveau; avec_worktree; rm -f "$GEL_LOG"
pose_verrou $$ jeton-de-test; verrou_avant=$(etat_verrou); debut=$(sed -n 1p "$ws/.git/pmzilla-fin-en-cours/debut"); ecrit_note feat%2Fx; avant=$(etat)
lance -- feat/x
code_et "code 42 : une autre fin est en cours" 42 "finish_worktree : une autre fin de branche est en cours (feat/autre, depuis $(hhmm "$debut"))"
inchange "42" "$avant"
[ ! -e "$GEL_LOG" ]; verifie "42 : ni contrôle, ni runner, ni fin lancés" $?
[ "$(etat_verrou)" = "$verrou_avant" ]; verifie "42 : le verrou de l'autre est intact" $?
[ -f "$ws/.git/pmzilla-notes/feat%2Fx" ]; verifie "42 : la note de la branche reste" $?
! contient "jeton-de-test"; verifie "42 : le jeton n'est jamais affiché" $?
rm -rf "$ws/.git/pmzilla-fin-en-cours"

# 42 juste après 20 : un usage faux reste 20 (même avec un verrou), un verrou passe avant 22 (branche main)
nouveau; avec_worktree; pose_verrou $$ jeton-de-test
lance -- feat/x autre
code_et "20 reste 20 même avec un verrou" 20 "usage"
lance -- main
code_et "42 avant 22 : sur main avec un verrou vivant" 42 "une autre fin de branche est en cours"
rm -rf "$ws/.git/pmzilla-fin-en-cours"

# verrou tenu sur tout le run, jeton passé au contrôle (deux fois), au runner et au script de fin ; libéré à la fin ; note retirée
nouveau; avec_worktree; rm -f "$GEL_LOG"; ecrit_note feat%2Fx; ecrit_note chore%2Fautre
lance -- feat/x
code_et "verrou : la fin réussit" 0 "vérification préalable réussie"
[ "$(grep -c '^check ' "$GEL_LOG")" -eq 2 ] && [ "$(grep -c '^runner ' "$GEL_LOG")" -eq 1 ] && [ "$(grep -c '^fin ' "$GEL_LOG")" -eq 1 ]; verifie "verrou : deux contrôles, un runner, une fin" $?
! grep -v 'jeton=pose verrou=oui egal=oui' "$GEL_LOG" | grep -q .; verifie "verrou : chacun a reçu le jeton du verrou, qui existait pendant son passage" $?
[ -s "$GEL_LOG.jeton-fin" ] && [ "$(cat "$GEL_LOG.jeton-check")" = "$(cat "$GEL_LOG.jeton-runner")" ] && [ "$(cat "$GEL_LOG.jeton-runner")" = "$(cat "$GEL_LOG.jeton-fin")" ]; verifie "verrou : le même jeton partout" $?
[ ! -e "$ws/.git/pmzilla-fin-en-cours" ]; verifie "verrou : aucun verrou après la sortie 0" $?
! contient "$(cat "$GEL_LOG.jeton-fin")"; verifie "verrou : le jeton n'est jamais affiché" $?
[ ! -e "$ws/.git/pmzilla-notes/feat%2Fx" ]; verifie "note : retirée après une sortie 0" $?
[ -f "$ws/.git/pmzilla-notes/chore%2Fautre" ]; verifie "note : celle d'une autre branche reste" $?

# refus après la prise du verrou (28 : worktree pas propre) : verrou libéré, note gardée
nouveau; avec_worktree; ecrit_note feat%2Fx; echo x > "$wt/sale.txt"
lance -- feat/x
code_et "verrou : refus 28" 28 "le worktree n'est pas propre"
[ ! -e "$ws/.git/pmzilla-fin-en-cours" ]; verifie "verrou : libéré après un refus" $?
[ -f "$ws/.git/pmzilla-notes/feat%2Fx" ]; verifie "note : gardée après un refus" $?

# runner en échec (38) : verrou libéré, note gardée, worktree encore là
nouveau; avec_worktree; ecrit_note feat%2Fx
export GEL_RUNNER_CODE=1; lance -- feat/x; export GEL_RUNNER_CODE=0
code_et "verrou : runner en échec, code 38" 38 "le runner complet n'est pas vert"
[ ! -e "$ws/.git/pmzilla-fin-en-cours" ]; verifie "verrou : libéré après le code 38" $?
[ -f "$ws/.git/pmzilla-notes/feat%2Fx" ] && [ -d "$wt" ]; verifie "note : gardée après le code 38 (le worktree est encore là)" $?

# code non nul du script de fin : transmis, verrou libéré, note gardée
# (le faux commun de ce bloc sort toujours 0 : le code 9 vient du faux script de fin d'origine)
nouveau; avec_worktree; ecrit_note feat%2Fx
export FINISH_WORKTREE_FINISH="bash $faux" FAKE_CODE=9; lance -- feat/x; export FAKE_CODE=0 FINISH_WORKTREE_FINISH="bash $fauxgel fin"
code_et "verrou : le script de fin rend 9, transmis" 9
[ ! -e "$ws/.git/pmzilla-fin-en-cours" ]; verifie "verrou : libéré après un code 9 du script de fin" $?
[ -f "$ws/.git/pmzilla-notes/feat%2Fx" ]; verifie "note : gardée après un code 9" $?

# verrou périmé (processus mort) : repris avec sa ligne, la fin continue
nouveau; avec_worktree; pose_verrou "$mort" jeton-mort
lance -- feat/x
code_et "verrou périmé : la fin continue" 0 "finish_worktree : verrou de fin périmé, repris"
[ ! -e "$ws/.git/pmzilla-fin-en-cours" ]; verifie "verrou périmé : le nouveau verrou est libéré à la fin" $?
nouveau; avec_worktree; pose_verrou $$ jeton-vieux 500
export PMZILLA_FINISH_LOCK_MAX_AGE=10; lance -- feat/x; unset PMZILLA_FINISH_LOCK_MAX_AGE
code_et "verrou trop vieux : repris" 0 "verrou de fin périmé, repris"

# interruption (TERM sur le script pendant le runner) : verrou libéré, note gardée
nouveau; avec_worktree; ecrit_note feat%2Fx; rm -f "$GEL_LOG.pid-runner"
( cd "$ws" && GEL_RUNNER_SLEEP=1 "$BASH_FIN" "$script" feat/x > "$cas/sortie-signal" 2>&1 </dev/null ) &
pid_sous=$!
i=0; while [ ! -s "$GEL_LOG.pid-runner" ] && [ "$i" -lt 240 ]; do i=$((i+1)); sleep 0.5; done   # attente bornée : environ 120 s
[ -s "$GEL_LOG.pid-runner" ]; SORTIE="le runner n'a pas démarré en 120 s"; verifie "interruption : le runner démarre" $?
[ -d "$ws/.git/pmzilla-fin-en-cours" ]; verifie "interruption : le verrou existe pendant le runner" $?
pid_script=$(cat "$ws/.git/pmzilla-fin-en-cours/pid" 2>/dev/null)   # numéro lu dans le verrou du dépôt jetable de ce cas, jamais un pgrep global
kill -TERM "$pid_script" 2>/dev/null; kill -TERM "$(cat "$GEL_LOG.pid-runner" 2>/dev/null)" 2>/dev/null
wait "$pid_sous" 2>/dev/null
[ ! -e "$ws/.git/pmzilla-fin-en-cours" ]; verifie "interruption : verrou libéré après un signal TERM" $?
[ -f "$ws/.git/pmzilla-notes/feat%2Fx" ]; verifie "interruption : la note est gardée" $?

# l'aide : 42 juste après 20, avant 21
nouveau; avec_worktree; lance -- --help
printf '%s\n' "$SORTIE" | awk '/^  20  /{a=NR} /^  42  /{b=NR} /^  21  /{c=NR} END {exit !(a && b && c && a<b && b<c)}'; verifie "aide : la ligne 42 est juste après la ligne 20" $?
contient "20 usage ; 42 une autre fin de branche est en cours ; 21 à 29 refus ci-dessus"; verifie "aide : la liste des codes de sortie donne 42 après 20" $?
export FINISH_WORKTREE_FINISH=$fin_ancien FINISH_WORKTREE_CHECK=$check_ancien FINISH_WORKTREE_RUNNER=$runner_ancien

# --- garde-fou du matin (change morning-guard, D7, tâche 5.2) : code 44 avant tout changement, au premier appel et juste avant le retrait ;
# le code 17 du script de fin est transmis ; aucune variable n'écarte le refus. Faux garde-fou qui journalise ses appels dans le journal d'ordre.
fauxmatin="$tmp/faux_matin.sh"
cat > "$fauxmatin" <<'FAUX'
#!/bin/bash
c=$(cat "$MATIN_COUNT" 2>/dev/null || echo 0); c=$((c+1)); echo "$c" > "$MATIN_COUNT"
echo "matin $c" >> "$ORDER_LOG"
echo "faux-matin : ligne $c"
codes=(${MATIN_SEQ:-0}); i=$((c-1)); [ "$i" -lt "${#codes[@]}" ] || i=$((${#codes[@]}-1))
exit "${codes[$i]}"
FAUX
export FINISH_MORNING_CHECK="bash $fauxmatin"
lance_matin() { MATIN_COUNT="$cas/compte-matin"; export MATIN_COUNT; rm -f "$MATIN_COUNT"; lance -- feat/x; }
MATIN_RELANCE="relancer quand l'état du matin est vérifié : bash tools/morning_state.sh check, puis bash tools/finish_worktree.sh feat/x"

# refusé au premier appel : rien n'est lancé, rien n'est changé
nouveau; avec_worktree; avant=$(etat); MATIN_SEQ=1; export MATIN_SEQ; lance_matin
code_et "code 44 : le garde-fou refuse, avant tout" 44 "finish_worktree : fenêtre du matin, état du matin non vérifié"
contient "faux-matin : ligne 1"; verifie "44 : la ligne du garde-fou est reprise telle quelle" $?
contient "$MATIN_RELANCE"; verifie "44 : la ligne de relance donne la commande de contrôle et la commande de fin" $?
[ "$(appels matin)" -eq 1 ] && [ "$(appels check)" -eq 0 ] && [ "$(appels runner)" -eq 0 ] && [ "$(appels finish)" -eq 0 ]; verifie "44 : un seul appel du garde-fou, ni vérification, ni runner, ni fin" $?
intact "44"; inchange "44" "$avant"

# refusé juste avant le retrait : le runner a tourné une fois, le worktree est encore là, la fin n'est pas lancée
nouveau; avec_worktree; avant=$(etat); MATIN_SEQ="0 1"; export MATIN_SEQ; lance_matin
code_et "code 44 : le garde-fou refuse au second appel, juste avant le retrait" 44 "fenêtre du matin, état du matin non vérifié"
[ "$(appels matin)" -eq 2 ] && [ "$(appels runner)" -eq 1 ] && [ "$(appels check)" -eq 2 ] && [ "$(appels finish)" -eq 0 ]; verifie "44 : garde-fou deux fois, vérification deux fois, runner une fois, fin jamais" $?
intact "44 au second appel"
awk '/^matin 1/{a=NR} /^check 1/{b=NR} /^runner /{c=NR} /^check 2/{d=NR} /^matin 2/{e=NR} END {exit !(a && b && c && d && e && a<b && b<c && c<d && d<e)}' "$ORDER_LOG"; verifie "44 : ordre garde-fou, vérification, runner, vérification, garde-fou" $?

# autorisé aux deux appels : la fin se déroule comme sans garde-fou
nouveau; avec_worktree; MATIN_SEQ=0; export MATIN_SEQ; lance_matin
code_et "garde-fou qui autorise : la fin se déroule, code 0" 0
[ "$(appels matin)" -eq 2 ] && [ "$(appels finish)" -eq 1 ] && [ ! -d "$wt" ]; verifie "garde-fou qui autorise : deux appels, fin lancée, worktree retiré" $?
awk '/^matin 2/{a=NR} /^finish /{b=NR} END {exit !(a && b && a<b)}' "$ORDER_LOG"; verifie "garde-fou qui autorise : le second appel précède la fin" $?

# code 17 du script de fin (course entre le dernier contrôle et le sien) : transmis tel quel, avec la recréation
nouveau; avec_worktree; MATIN_SEQ=0; FAKE_CODE=17; export MATIN_SEQ; lance_matin
code_et "code 17 du script de fin : transmis tel quel" 17 "la fin de branche a rendu le code 17"
contient "git switch main && bash tools/worktree.sh feat/x"; verifie "code 17 : la commande de recréation du worktree est donnée" $?

# aucune variable n'écarte le refus
nouveau; avec_worktree; avant=$(etat); MATIN_SEQ=1; export MATIN_SEQ
FINISH_WORKTREE_ALLOW_SKIP=1 PMZILLA_SKIP_GREEN_CHECK=1 FINISH_BRANCH_FORCE_RUN=1 FINISH_MORNING_SKIP=1 FINISH_MORNING_CHECK_OFF=1 lance_matin
code_et "aucune variable n'écarte le refus 44" 44 "fenêtre du matin, état du matin non vérifié"
intact "44 avec des variables de contournement"

# ordre : le verrou (42) passe avant le garde-fou (44) ; le garde-fou passe avant les contrôles 22 et suivants
nouveau; avec_worktree; MATIN_SEQ=1; export MATIN_SEQ; pose_verrou $$ jeton-de-test; lance_matin
code_et "42 avant 44 : un verrou vivant donne 42, le garde-fou n'est pas appelé" 42 "une autre fin de branche est en cours"
[ "$(appels matin)" -eq 0 ]; verifie "42 avant 44 : garde-fou non appelé" $?
rm -rf "$ws/.git/pmzilla-fin-en-cours"
nouveau; avec_worktree; MATIN_SEQ=1; export MATIN_SEQ; MATIN_COUNT="$cas/compte-matin"; export MATIN_COUNT; rm -f "$MATIN_COUNT"; lance -- main
code_et "44 avant 22 : sur main, le garde-fou refuse d'abord" 44 "fenêtre du matin, état du matin non vérifié"

# l'aide : 44 juste après 42, avant 21
nouveau; avec_worktree; lance -- --help
printf '%s\n' "$SORTIE" | awk '/^  20  /{a=NR} /^  42  /{b=NR} /^  44  /{c=NR} /^  21  /{d=NR} END {exit !(a && b && c && d && a<b && b<c && c<d)}'; verifie "aide : la ligne 44 est juste après la ligne 42, avant 21" $?
contient "44 fenêtre du matin, état du matin non vérifié"; verifie "aide : la liste des codes de sortie donne 44" $?

# commande par défaut : le module à côté du script, ici une copie des outils avec des dossiers du lab factices
nouveau; avec_worktree; mkdir -p "$cas/outils" "$cas/data" "$cas/sauv"
for f in finish_worktree.sh morning_state.sh lab_paths.sh finish_env.sh finish_lock.sh light_finish.sh; do cp "$(dirname "$script")/$f" "$cas/outils/"; done
SORTIE=$(cd "$ws" && env -u FINISH_MORNING_CHECK PMZILLA_LAB_WORKSPACE="$cas" PMZILLA_LAB_DATA="$cas/data" DB_BACKUP_SAUVEGARDES="$cas/sauv" \
  OFFSITE_COPY_LOG="$cas/copie.log" OFFSITE_DONNEES="$cas/off" PMZILLA_RUN_NOW="$MIDI" bash "$cas/outils/finish_worktree.sh" feat/x 2>&1 </dev/null); CODE=$?
code_et "commande par défaut : le vrai module, à midi sans veille ni sauvegarde, refuse avec 44" 44 "morning_state : refusé, fenêtre du matin depuis 06:45"
intact "44 avec le vrai module"
export FINISH_MORNING_CHECK=true

# --- light-spec-finish (D7, D8) : le même choix que le script de fin, dans le worktree : passage allégé (validation OpenSpec puis suites qui lisent
# openspec/) ou runner complet, avec la raison ; code 45 ; aucune fiche de fin sur le passage allégé ; code 18 du script de fin transmis.
fauxvalide="$tmp/faux_validation.sh"
cat > "$fauxvalide" <<'FAUX'
#!/bin/bash
echo "valide pwd=$(pwd -P) args=$* stdin=[$(cat)] jeton=${FINISH_BRANCH_TESTED_TOKEN-absent}" >> "$ORDER_LOG"
exit "${VALIDE_CODE:-0}"
FAUX
fauxleger="$tmp/faux_leger.sh"
cat > "$fauxleger" <<'FAUX'
#!/bin/bash
echo "leger pwd=$(pwd -P) args=$* wt=$([ -d "$WT_PATH" ] && echo present || echo absent)" >> "$ORDER_LOG"
exit "${LEGER_CODE:-0}"
FAUX
export FINISH_WORKTREE_VALIDATE="bash $fauxvalide" FINISH_WORKTREE_LIGHT_RUNNER="bash $fauxleger"
export LIGHT_FINISH_TODAY=2026-01-15 VALIDE_CODE=0 LEGER_CODE=0
spec_wt() { avec_worktree; ( cd "$wt" && mkdir -p openspec/specs/x && echo s > openspec/specs/x/spec.md && git add -A && git commit -q -m spec ); VALIDE_CODE=0; LEGER_CODE=0; }
signature_courante() { bash "$(dirname "$script")/finish_env.sh" --main-signature; }   # signature d'environnement (Q9) que le script recalcule
registre_main() { # date [signature ; défaut : celle de l'environnement] : la validation de main enregistrée pour l'arbre de main de l'espace de travail
  printf '%s\tcomplet\t%s\t%s\n' "$(git -C "$ws" rev-parse 'main^{tree}')" "$1" "${2:-$(signature_courante)}" >> "$ws/.git/pmzilla-main-validated"
}
sans_uv="$tmp/sans-uv"   # liens vers chaque exécutable du PATH réel sauf uv
if [ ! -d "$sans_uv" ]; then
  mkdir -p "$sans_uv"
  for d in $(printf '%s' "$PATH" | tr ':' ' '); do
    for f in "$d"/*; do
      b=${f##*/}
      [ "$b" != uv ] && [ -f "$f" ] && [ -x "$f" ] && [ ! -e "$sans_uv/$b" ] && ln -s "$f" "$sans_uv/$b"
    done
  done
fi
avec_uv() { # version : PATH sans le vrai uv, avec un faux uv qui dit « uv <version> »
  mkdir -p "$cas/uvfaux"; printf '#!/bin/sh\necho "uv %s"\n' "$1" > "$cas/uvfaux/uv"; chmod +x "$cas/uvfaux/uv"
  PATH="$cas/uvfaux:$sans_uv"; export PATH
}

nouveau; spec_wt; registre_main 2026-01-15; FINISH_WORKTREE_ALLOW_SKIP=1 lance -- feat/x; unset FINISH_WORKTREE_ALLOW_SKIP
code_et "allégé : la fin réussit" 0 "finish_worktree : chemin allégé : passage allégé dans le worktree"
contient "(openspec validate --strict et suites qui lisent openspec/)"; verifie "allégé : la ligne précise validation et suites" $?
[ "$(appels valide)" -eq 1 ] && [ "$(appels leger)" -eq 1 ] && [ "$(appels runner)" -eq 0 ]; verifie "allégé : validation et passage allégé appelés, runner complet jamais" $?
ligne_de leger | grep -qF "pwd=$wt " && ligne_de leger | grep -qF "wt=present" && ligne_de valide | grep -qF "pwd=$wt "; verifie "allégé : lancés dans le worktree, encore présent" $?
ligne_de leger | grep -qF "args=identifiants_personnels"; verifie "allégé : le passage allégé reçoit les noms de suites du sélecteur" $?
ligne_de valide | grep -qF "stdin=[]"; verifie "allégé : la validation a l'entrée standard fermée" $?
[ ! -e "$fiche" ]; verifie "allégé : aucune fiche de fin écrite, même avec le réglage du saut à 1" $?
contient "passage allégé vert dans le worktree ; fiche de fin sans objet : le script de fin relancera le passage allégé"; verifie "allégé : la ligne de fiche sans objet" $?
[ "$(appels finish)" -eq 1 ]; verifie "allégé : le script de fin est lancé ensuite" $?

nouveau; spec_wt; registre_main 2026-01-15; FINISH_BRANCH_FORCE_RUN=1 lance -- feat/x; unset FINISH_BRANCH_FORCE_RUN
code_et "relance forcée : runner complet dans le worktree, raison" 0 "finish_worktree : runner complet nécessaire : relance forcée"
[ "$(appels runner)" -eq 1 ] && [ "$(appels leger)" -eq 0 ] && [ "$(appels valide)" -eq 0 ]; verifie "relance forcée : runner complet seul" $?
nouveau; spec_wt
lance -- feat/x
code_et "sans enregistrement : runner complet, raison" 0 "finish_worktree : runner complet nécessaire : arbre de main non validé"
[ "$(appels runner)" -eq 1 ] && [ "$(appels leger)" -eq 0 ]; verifie "sans enregistrement : runner complet seul" $?
nouveau; spec_wt; registre_main 2026-01-07
lance -- feat/x
code_et "enregistrement de 8 jours : runner complet, raison" 0 "finish_worktree : runner complet nécessaire : validation de main expirée"
[ "$(appels runner)" -eq 1 ] && [ "$(appels leger)" -eq 0 ]; verifie "enregistrement de 8 jours : runner complet seul" $?
nouveau; spec_wt; registre_main 2026-01-08
lance -- feat/x
code_et "enregistrement de 7 jours : passage allégé" 0 "finish_worktree : chemin allégé"
PATH_CAS=$PATH
nouveau; spec_wt; avec_uv 1.2.3; registre_main 2026-01-15; avec_uv 1.2.4
lance -- feat/x; PATH=$PATH_CAS; export PATH
code_et "autre signature d'environnement : runner complet, raison" 0 "finish_worktree : runner complet nécessaire : environnement changé depuis la validation"
[ "$(appels runner)" -eq 1 ] && [ "$(appels leger)" -eq 0 ]; verifie "autre signature d'environnement : runner complet seul" $?
nouveau; spec_wt; avec_uv 1.2.3; registre_main 2026-01-15; avec_uv 1.2.3
lance -- feat/x; PATH=$PATH_CAS; export PATH
code_et "même signature d'environnement : passage allégé" 0 "finish_worktree : chemin allégé"
nouveau; spec_wt; registre_main 2026-01-15 inconnue
lance -- feat/x
code_et "signature enregistrée « inconnue » : runner complet, raison" 0 "finish_worktree : runner complet nécessaire : signature d'environnement absente de la validation"
nouveau; avec_worktree; ( cd "$wt" && echo y > code.txt && git add -A && git commit -q -m code ); registre_main 2026-01-15
lance -- feat/x
code_et "branche de code : runner complet, aucune ligne de raison" 0 "finish_worktree : lancement du runner complet dans le worktree"
! contient "runner complet nécessaire"; verifie "branche de code : pas de ligne « runner complet nécessaire »" $?
# finish-under-lock 3.1 (D2) : la décision allégée est prise sur le sommet fusionné. main avance par un fichier hors d'openspec/ : avant la fusion,
# l'écart d'arbre entre main et la branche le contient (runner complet) ; après la fusion, il ne reste que les fichiers de spécification (allégé)
nouveau; spec_wt; echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"; registre_main 2026-01-15
lance -- feat/x
code_et "3.1 : spécification, main en avance, fusion puis passage allégé" 0 "finish_worktree : chemin allégé"
awk '/main fusionnée dans la branche/{a=NR} /chemin allégé/{b=NR} END {exit !(a && b && a<b)}' <<< "$SORTIE"; verifie "3.1 : la fusion précède la décision allégée" $?
[ "$(appels leger)" -eq 1 ] && [ "$(appels runner)" -eq 0 ]; verifie "3.1 : décision allégée sur le sommet fusionné, runner complet jamais" $?
nouveau; spec_wt; registre_main 2026-01-15; ( cd "$wt" && echo y > code.txt && git add -A && git commit -q -m code )
lance -- feat/x
code_et "spécification et code mêlés : runner complet seul" 0
[ "$(appels runner)" -eq 1 ] && [ "$(appels leger)" -eq 0 ]; verifie "spécification et code mêlés : runner complet seul" $?

nouveau; spec_wt; registre_main 2026-01-15; avant=$(etat); VALIDE_CODE=1 lance -- feat/x; VALIDE_CODE=0
code_et "validation rouge : code 45" 45 "finish_worktree : openspec validate --strict en échec dans le worktree ; rien n'est changé"
[ "$(appels leger)" -eq 0 ] && [ "$(appels runner)" -eq 0 ]; verifie "validation rouge : aucun runner" $?
inchange "45" "$avant"
nouveau; spec_wt; registre_main 2026-01-15; avant=$(etat); LEGER_CODE=1 lance -- feat/x; LEGER_CODE=0
code_et "suites allégées rouges : code 38" 38 "le runner complet n'est pas vert dans le worktree (code 1) ; rien n'est changé"
contient "(passage allégé)"; verifie "suites allégées rouges : la mention (passage allégé)" $?
inchange "38 allégé" "$avant"
nouveau; spec_wt; registre_main 2026-01-15; VALIDE_CODE=127 lance -- feat/x; VALIDE_CODE=0
code_et "validation introuvable (127) : runner complet, raison" 0 "finish_worktree : runner complet nécessaire : openspec introuvable"
[ "$(appels runner)" -eq 1 ] && [ "$(appels leger)" -eq 0 ]; verifie "validation introuvable : runner complet seul" $?

# light-finish-touched-specs (D3) : la validation reçoit la référence de main puis le sommet ; par défaut, c'est tools/light_validate.py
nouveau; spec_wt; registre_main 2026-01-15; principal=$(git -C "$ws" rev-parse refs/heads/main); sommet=$(git -C "$wt" rev-parse HEAD)
FINISH_WORKTREE_ALLOW_SKIP=1 lance -- feat/x; unset FINISH_WORKTREE_ALLOW_SKIP
ligne_de valide | grep -qF "args=$principal $sommet stdin="; rc=$?; SORTIE="$(ligne_de valide)"; verifie "validation remplacée : reçoit la référence de main puis le sommet" $rc
sauve_validate=$FINISH_WORKTREE_VALIDATE; unset FINISH_WORKTREE_VALIDATE
fauxopenspec="$tmp/faux_openspec.sh"
printf '#!/bin/sh\necho "openspec $*" >> "%s"\nif [ -n "$OS_ISSUE" ]; then echo %s; else echo %s; fi\nexit 0\n' "$tmp/appels-openspec" \
  "'{\"items\":[{\"id\":\"x\",\"issues\":[{\"level\":\"WARNING\",\"path\":\"p\",\"message\":\"trop long\"}]}]}'" "'{\"items\":[{\"id\":\"x\",\"issues\":[]}]}'" > "$fauxopenspec"
chmod +x "$fauxopenspec"; export LIGHT_VALIDATE_OPENSPEC="$fauxopenspec"; rm -f "$tmp/appels-openspec"
nouveau; spec_wt; registre_main 2026-01-15; FINISH_WORKTREE_ALLOW_SKIP=1 lance -- feat/x; unset FINISH_WORKTREE_ALLOW_SKIP
code_et "validation par défaut verte : la fin réussit" 0 "validation OpenSpec : 1 élément(s) touché(s), aucun nouvel avertissement strict"
grep -q "^openspec validate x --type spec" "$tmp/appels-openspec" && [ "$(appels leger)" -eq 1 ]; verifie "validation par défaut : le helper interroge OpenSpec, passage allégé lancé" $?
nouveau; spec_wt; registre_main 2026-01-15; avant=$(etat); OS_ISSUE=1 lance -- feat/x; unset OS_ISSUE
code_et "validation par défaut rouge : code 45" 45 "nouvel avertissement strict : spec x : trop long"
contient "finish_worktree : openspec validate --strict en échec dans le worktree ; rien n'est changé"; verifie "validation par défaut rouge : la phrase du code 45 est inchangée" $?
[ "$(appels leger)" -eq 0 ] && [ "$(appels runner)" -eq 0 ]; verifie "validation par défaut rouge : ni passage allégé ni runner complet" $?
inchange "45 par défaut" "$avant"
nouveau; spec_wt; registre_main 2026-01-15; LIGHT_VALIDATE_OPENSPEC="$tmp/inexistante" lance -- feat/x
code_et "validation par défaut sans openspec : runner complet, raison" 0 "finish_worktree : runner complet nécessaire : openspec introuvable"
unset LIGHT_VALIDATE_OPENSPEC; export FINISH_WORKTREE_VALIDATE=$sauve_validate

# code 18 du script de fin : transmis, avec la commande de recréation (la branche n'est pas fusionnée)
nouveau; spec_wt; registre_main 2026-01-15; FAKE_CODE=18 lance -- feat/x; FAKE_CODE=0
code_et "code 18 du script de fin : transmis" 18 "finish_worktree : la fin de branche a rendu le code 18"
contient "pour reprendre dans un worktree : git switch main && bash tools/worktree.sh feat/x"; verifie "code 18 : la commande de recréation du worktree" $?

# l'aide : 45 listé avec 38
nouveau; avec_worktree; lance -- --help
contient " 45 "; verifie "aide : le code 45 est décrit" $?
printf '%s\n' "$SORTIE" | awk '/^  38  /{a=NR} /^  45  /{b=NR} /^  40  /{c=NR} END {exit !(a && b && c && a<b && b<c)}'; verifie "aide : le code 45 suit le 38 et précède le 40" $?
contient "les codes 0 à 13, 17 et 18 de tools/finish_branch.sh sont transmis"; verifie "aide : le code 18 transmis est cité" $?
grep -q '^#   FINISH_WORKTREE_VALIDATE ' "$script" && grep -q '^#   FINISH_WORKTREE_LIGHT_RUNNER ' "$script"; rc=$?; SORTIE="en-tête"; verifie "l'en-tête nomme les deux variables de test du passage allégé" $rc
unset FINISH_WORKTREE_VALIDATE FINISH_WORKTREE_LIGHT_RUNNER LIGHT_FINISH_TODAY VALIDE_CODE LEGER_CODE

# --- mode CI (local-ci-container 7.1, D8) : FINISH_WORKTREE_CI=1 lit le verdict enregistré de l'arbre fusionné (FINISH_WORKTREE_CI_VERDICTS), ne lance
# jamais de conteneur (faux docker devant le vrai, tout appel est une faute), puis la passe Mac (« FINISH_WORKTREE_RUNNER --mac »). Code 50 : verdict
# illisible, absent pour l'arbre fusionné, ou rouge ; la fiche de fin gagne passage=ci et image=<clé de la ligne>.
CLE_CI="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
AUTRE_ARBRE="4b825dc642cb6eb9a060e54bf8d69288fbee4904"
verdict_ci() { # verdict [arbre] : fichier des verdicts du cas, une ligne pour l'arbre du sommet de feat/x (ou l'arbre donné), plus une ligne d'un autre arbre
  VERDICTS="$cas/verdicts"
  printf '%s\t%s\t%s\n' "${AUTRE_ARBRE}" vert "$CLE_CI" > "$VERDICTS"
  [ -z "${1:-}" ] || printf '%s\t%s\t%s\n' "${2:-$(git -C "$ws" rev-parse 'feat/x^{tree}')}" "$1" "$CLE_CI" >> "$VERDICTS"
  export FINISH_WORKTREE_CI=1 FINISH_WORKTREE_CI_VERDICTS="$VERDICTS"
}
fin_ci() { unset FINISH_WORKTREE_CI FINISH_WORKTREE_CI_VERDICTS; }
rien_lance_ci() { # description : aucun conteneur, fichier des verdicts inchangé
  [ ! -e "$DOCKER_LOG" ]; verifie "$1 : aucun conteneur lancé (faux docker jamais appelé)" $?
  [ "$(cat "$VERDICTS")" = "$AVANT_VERDICTS" ]; verifie "$1 : le fichier des verdicts est inchangé" $?
}
COURT_CI="0123456789ab"
# vert pour l'arbre exact, puis passe Mac verte : la fin réussit, la fiche porte passage=ci et l'image
nouveau; avec_worktree; verdict_ci vert; AVANT_VERDICTS=$(cat "$VERDICTS"); ARBRE_CI=$(git -C "$ws" rev-parse 'feat/x^{tree}')
lance -- feat/x; fin_ci
code_et "CI : verdict vert pour l'arbre fusionné, la fin réussit" 0 "verdict du conteneur vert pour l'arbre fusionné (arbre ${ARBRE_CI:0:12}, image $COURT_CI)"
[ "$(appels runner)" -eq 1 ] && [ "$(cat "$cas/args-runner")" = "--mac" ]; verifie "CI : la passe Mac est le runner lancé avec --mac, une seule fois" $?
[ "$(sed -n 's/^passage=//p' "$cas/fiche-vue")" = "ci" ] && [ "$(sed -n 's/^image=//p' "$cas/fiche-vue")" = "$CLE_CI" ]; rc=$?; SORTIE=$(cat "$cas/fiche-vue" 2>&1); verifie "CI : la fiche porte passage=ci et l'image de la ligne" $rc
[ "$(sed -n 's/^format=//p' "$cas/fiche-vue")" = "1" ] && [ "$(sed -n 's/^tree=//p' "$cas/fiche-vue")" = "$ARBRE_CI" ]; verifie "CI : fiche au format 1, arbre du sommet" $?
rien_lance_ci "CI vert"
# la passe Mac verte n'exige pas l'empreinte complète : pas de RUNNER_FP, la fiche est écrite quand même (vue ci-dessus) ; le script de fin est lancé une fois
[ "$(appels finish)" -eq 1 ]; verifie "CI : le script de fin est lancé" $?
# aucune ligne pour l'arbre : code 50, phrase, ligne de commande ; rien n'est lancé ni changé
nouveau; avec_worktree; verdict_ci ""; AVANT_VERDICTS=$(cat "$VERDICTS"); ARBRE_CI=$(git -C "$ws" rev-parse 'feat/x^{tree}'); avant=$(etat)
lance -- feat/x; fin_ci
code_et "CI : verdicts d'autres arbres seulement, code 50" 50 "verdict du conteneur absent pour l'arbre fusionné (arbre ${ARBRE_CI:0:12})"
contient "lancer : bash tools/ci_local.sh run feat/x (depuis le worktree), puis relancer la fin"; verifie "CI absent : la ligne de commande est donnée" $?
! contient "main est fusionnée dans la branche"; verifie "CI absent sans fusion : pas de ligne de fusion" $?
[ "$(appels runner)" -eq 0 ] && [ ! -e "$fiche" ]; verifie "CI absent : ni passe Mac ni fiche" $?
intact "CI absent"; rien_lance_ci "CI absent"
# ligne rouge pour l'arbre
nouveau; avec_worktree; verdict_ci rouge; AVANT_VERDICTS=$(cat "$VERDICTS"); ARBRE_CI=$(git -C "$ws" rev-parse 'feat/x^{tree}')
lance -- feat/x; fin_ci
code_et "CI : ligne rouge, code 50" 50 "verdict du conteneur rouge pour l'arbre fusionné (arbre ${ARBRE_CI:0:12})"
contient "lancer : bash tools/ci_local.sh run feat/x (depuis le worktree), puis relancer la fin"; verifie "CI rouge : la ligne de commande est donnée" $?
[ "$(appels runner)" -eq 0 ]; verifie "CI rouge : la passe Mac n'est pas lancée" $?
intact "CI rouge"; rien_lance_ci "CI rouge"
# fichier illisible
nouveau; avec_worktree; verdict_ci vert; AVANT_VERDICTS=$(cat "$VERDICTS"); chmod 000 "$VERDICTS"
lance -- feat/x; chmod 600 "$VERDICTS"; fin_ci
code_et "CI : fichier illisible, code 50" 50 "verdict du conteneur illisible (dossier de données introuvable)"
contient "lancer : bash tools/ci_local.sh run feat/x (depuis le worktree), puis relancer la fin"; verifie "CI illisible : la ligne de commande est donnée" $?
intact "CI illisible"; rien_lance_ci "CI illisible"
# main avance : la fusion faite par la fin change l'arbre ; le verdict de l'arbre d'avant ne compte plus (phrase « absent »), ligne de fusion puis commande
nouveau; avec_worktree; echo m > "$ws/m.txt"; git -C "$ws" add m.txt; git -C "$ws" commit -q -m "main avance"
verdict_ci vert "$(git -C "$wt" rev-parse 'HEAD^{tree}')"; AVANT_VERDICTS=$(cat "$VERDICTS")
lance -- feat/x; fin_ci
code_et "CI : main fusionnée par la fin, le verdict de l'arbre d'avant ne compte pas, code 50" 50 "verdict du conteneur absent pour l'arbre fusionné"
contient "main fusionnée dans la branche"; verifie "CI fusion : la fusion a eu lieu" $?
printf '%s\n' "$SORTIE" | awk '/main est fusionnée dans la branche ; rien d.autre n.est changé/{a=NR} /lancer : bash tools\/ci_local.sh run feat\/x/{b=NR} END {exit !(a && b && a<b)}'; verifie "CI fusion : la ligne de fusion précède la ligne de commande" $?
[ "$(appels runner)" -eq 0 ]; verifie "CI fusion : la passe Mac n'est pas lancée" $?
[ -d "$wt" ]; verifie "CI fusion : le worktree est encore là" $?
rien_lance_ci "CI fusion"
# passe Mac rouge : 38 avec sa phrase, rien n'est changé, aucun conteneur
nouveau; avec_worktree; verdict_ci vert; AVANT_VERDICTS=$(cat "$VERDICTS")
RUNNER_CODE=3 lance -- feat/x; fin_ci
code_et "CI : passe Mac rouge, code 38" 38 "passe Mac rouge dans le worktree (code 3)"
intact "CI passe Mac rouge"; rien_lance_ci "CI passe Mac rouge"
# sans la variable : le chemin d'aujourd'hui, le fichier des verdicts n'est pas lu (même illisible), runner sans --mac, fiche sans passage
nouveau; avec_worktree; verdict_ci vert; unset FINISH_WORKTREE_CI; chmod 000 "$VERDICTS"; AVANT_VERDICTS="x"
RUNNER_FP=tip lance -- feat/x; chmod 600 "$VERDICTS"; AVANT_VERDICTS=$(cat "$VERDICTS"); fin_ci; RUNNER_FP=""
code_et "sans FINISH_WORKTREE_CI : chemin d'aujourd'hui, la fin réussit" 0 "fiche de fin écrite"
! contient "verdict du conteneur"; verifie "sans la variable : aucune phrase de verdict" $?
[ -z "$(cat "$cas/args-runner")" ]; verifie "sans la variable : le runner est lancé sans --mac" $?
! grep -q '^passage=' "$cas/fiche-vue"; verifie "sans la variable : la fiche n'a pas de champ passage" $?
# toute valeur autre que 1 : chemin d'aujourd'hui
nouveau; avec_worktree; verdict_ci rouge; export FINISH_WORKTREE_CI=0
lance -- feat/x; fin_ci
code_et "FINISH_WORKTREE_CI=0 : chemin d'aujourd'hui" 0 "lancement du runner complet dans le worktree"
# chemin allégé inchangé avec la variable : ni lecture du verdict ni code 50
export FINISH_WORKTREE_VALIDATE="bash $fauxvalide" FINISH_WORKTREE_LIGHT_RUNNER="bash $fauxleger" LIGHT_FINISH_TODAY=2026-01-15 VALIDE_CODE=0 LEGER_CODE=0
nouveau; spec_wt; registre_main 2026-01-15; verdict_ci ""; chmod 000 "$VERDICTS"; AVANT_VERDICTS="x"
FINISH_WORKTREE_ALLOW_SKIP=1 lance -- feat/x; chmod 600 "$VERDICTS"; fin_ci; unset FINISH_WORKTREE_ALLOW_SKIP
unset FINISH_WORKTREE_VALIDATE FINISH_WORKTREE_LIGHT_RUNNER LIGHT_FINISH_TODAY VALIDE_CODE LEGER_CODE
code_et "CI : chemin allégé inchangé (le verdict n'est pas lu)" 0 "chemin allégé : passage allégé dans le worktree"
! contient "verdict du conteneur"; verifie "CI allégé : aucune phrase de verdict" $?
[ ! -e "$DOCKER_LOG" ] && [ "$(appels runner)" -eq 0 ]; verifie "CI allégé : ni conteneur ni runner complet" $?
# l'aide : 50 décrit, avec la variable et la commande ; 39 reste réservé
nouveau; avec_worktree; lance -- --help
contient "  50  mode CI" && contient "FINISH_WORKTREE_CI=1" && contient "bash tools/ci_local.sh run"; verifie "CI : l'aide décrit le code 50, la variable et la commande" $?
printf '%s\n' "$SORTIE" | awk '/^  40  /{a=NR} /^  50  /{b=NR} END {exit !(a && b && a<b)}'; verifie "CI : le 50 suit le 40 dans l'aide" $?
grep -q '^#   FINISH_WORKTREE_CI ' "$script" && grep -q '^#   FINISH_WORKTREE_CI_VERDICTS ' "$script"; rc=$?; SORTIE="en-tête"; verifie "CI : l'en-tête nomme FINISH_WORKTREE_CI et FINISH_WORKTREE_CI_VERDICTS" $rc
# la fiche du mode CI n'est écrite que si l'arbre du sommet après la passe Mac est celui dont le verdict a été lu (le sommet ne peut pas bouger sans le code 40 :
# la condition est un rempart, vérifiée dans le texte du script)
printf '%s\n' "$(grep -v '^[[:space:]]*#' "$script")" | grep -qF '[ "$CI_MODE" -eq 1 ] && [ "$ARBRE_SOMMET" != "$ARBRE_CI" ]'; rc=$?; SORTIE="rempart"; verifie "CI : la fiche exige l'arbre du sommet égal à l'arbre du verdict lu" $rc
# dossier de données introuvable, sans FINISH_WORKTREE_CI_VERDICTS : code 50 « illisible (dossier de données introuvable) », rien d'autre n'est changé
nouveau; avec_worktree; export FINISH_WORKTREE_CI=1; avant=$(etat)
PMZILLA_LAB_DATA="$cas/absent-x" lance -- feat/x; fin_ci
code_et "CI : dossier de données introuvable (variable des verdicts absente), code 50" 50 "verdict du conteneur illisible (dossier de données introuvable)"
contient "lancer : bash tools/ci_local.sh run feat/x (depuis le worktree), puis relancer la fin"; verifie "CI dossier introuvable : la ligne de commande est donnée" $?
[ "$(appels runner)" -eq 0 ] && [ ! -e "$DOCKER_LOG" ]; verifie "CI dossier introuvable : ni passe Mac ni conteneur" $?
intact "CI dossier introuvable"
# le script ne lance jamais de conteneur ni tools/ci_local.sh, et n'écrit pas le fichier des verdicts
code_ci=$(grep -v '^[[:space:]]*#' "$script")
! printf '%s\n' "$code_ci" | grep -qiE '(^|[^a-z_])docker([^a-z_]|$)|colima'; rc=$?; SORTIE="docker"; verifie "CI : aucune commande docker ni colima dans le script" $rc
! printf '%s\n' "$code_ci" | grep -F 'ci_local.sh' | grep -vF 'lancer : bash tools/ci_local.sh run' | grep -q .; rc=$?; SORTIE="ci_local"; verifie "CI : tools/ci_local.sh n'est cité que dans la ligne « lancer : »" $rc
! printf '%s\n' "$code_ci" | grep -E '>[^&]*(VERDICTS|verdicts)' | grep -q .; rc=$?; SORTIE="écriture"; verifie "CI : le fichier des verdicts n'est jamais une cible d'écriture" $rc

# --- scan du script, hors commentaires
code_script=$(grep -v '^[[:space:]]*#' "$script")
for interdit in '--no-verify' '--force' ' -f ' 'prune' 'push' 'reset' 'stash' 'branch -D' 'PMZILLA_SKIP_GREEN_CHECK=' 'PMZILLA_NO_EVALS=' 'BYPASS' 'exit 39' 'refus 39'; do
  ! printf '%s\n' "$code_script" | grep -qF -- "$interdit"; rc=$?; SORTIE="« $interdit » trouvé"; verifie "le script ne contient pas « $interdit »" $rc
done
# finish-under-lock D20 (#284) : « merge » et « prune » sont cherchés sur une commande git entière, en début de commande, plus comme mots :
# un texte d'aide ou un message qui les cite ne compte pas. Une seule vraie fusion (« merge --no-edit », D3) et son « merge --abort » sont
# permises ; merge-base (lecture seule) n'est pas une fusion.
# « prune » reste cherché comme mot littéral ci-dessus (aucune occurrence permise) ; les ancres couvrent aussi if, elif, while, until, ! et {
COMMANDE_GIT='(^|[|;&({!]|then|do|else|if|elif|while|until)[[:space:]]*(exec[[:space:]]+)?git[^|;&]*[[:space:]]'
fusions=$(printf '%s\n' "$code_script" | grep -E -- "${COMMANDE_GIT}merge([[:space:]]|\$)")
[ "$(printf '%s\n' "$fusions" | grep -c .)" -eq 2 ] && printf '%s\n' "$fusions" | grep -qF -- 'merge --no-edit' && printf '%s\n' "$fusions" | grep -qF -- 'merge --abort'
rc=$?; SORTIE="commandes de fusion : $(printf '%s' "$fusions" | tr '\n' '|')"
verifie "le script ne contient qu'une fusion « merge --no-edit » et son « merge --abort » (D20)" $rc
! printf '%s\n' "$code_script" | grep -qE -- "${COMMANDE_GIT}worktree[[:space:]]+prune"; rc=$?; SORTIE="« worktree prune » trouvé"
verifie "le script ne lance jamais git worktree prune (D20)" $rc
# le scan ancré reconnaît bien une commande interdite et ignore un texte qui la cite
printf 'x && git merge main\n' | grep -qE -- "${COMMANDE_GIT}merge([[:space:]]|\$)"; rc=$?; SORTIE="motif"; verifie "D20 : le motif reconnaît une fusion en début de commande" $rc
! printf 'echo "puis git merge --no-edit dans le worktree"\n' | grep -qE -- "${COMMANDE_GIT}merge([[:space:]]|\$)"; rc=$?; SORTIE="motif"; verifie "D20 : le motif ignore un texte qui cite une fusion" $rc
printf 'then git worktree prune\n' | grep -qE -- "${COMMANDE_GIT}worktree[[:space:]]+prune"; rc=$?; SORTIE="motif"; verifie "D20 : le motif reconnaît git worktree prune" $rc
for forme in 'if git merge main; then' '! git merge main' '{ git merge main; }' 'elif git merge main' 'while git merge main' 'until git merge main'; do
  printf '%s\n' "$forme" | grep -qE -- "${COMMANDE_GIT}merge([[:space:]]|\$)"; rc=$?; SORTIE="motif"; verifie "D20 : le motif reconnaît « $forme »" $rc
done
# le module d'aperçu de fusion (D10) tourne dans ce script : aucune fusion, aucune commande d'écriture
module_fusion="$(dirname "$script")/finish_merge.sh"
[ -s "$module_fusion" ]; rc=$?; SORTIE="module absent"; verifie "le module finish_merge.sh existe à côté du script" $rc
code_fusion=$(grep -v '^[[:space:]]*#' "$module_fusion")
for interdit in '--no-verify' '--force' 'prune' 'push' 'git merge ' 'reset' 'stash' 'checkout' 'update-ref' 'PMZILLA_SKIP_GREEN_CHECK='; do
  ! printf '%s\n' "$code_fusion" | grep -qF -- "$interdit"; rc=$?; SORTIE="« $interdit » trouvé"; verifie "le module finish_merge.sh ne contient pas « $interdit »" $rc
done
# le module sourcé du chemin allégé (light-spec-finish D3) tourne dans ce script : même garantie, merge-base (lecture seule) excepté
module="$(dirname "$script")/light_finish.sh"
[ -s "$module" ]; rc=$?; SORTIE="module absent"; verifie "le module light_finish.sh existe à côté du script" $rc
code_module=$(grep -v '^[[:space:]]*#' "$module")
for interdit in '--no-verify' '--force' 'prune' 'push' 'git merge ' 'reset' 'stash' 'PMZILLA_SKIP_GREEN_CHECK=' 'PMZILLA_NO_EVALS=' 'BYPASS'; do
  ! printf '%s\n' "$code_module" | grep -qF -- "$interdit"; rc=$?; SORTIE="« $interdit » trouvé"; verifie "le module light_finish.sh ne contient pas « $interdit »" $rc
done
# les deux variables réservées ne sont jamais posées, seulement retirées pour le runner ; le contrôle est le seul usage de finish_branch.sh avec une option
printf '%s\n' "$code_script" | grep -qF 'env -u PMZILLA_NO_EVALS -u PMZILLA_SKIP_GREEN_CHECK'; rc=$?; SORTIE="runner sans « env -u »"; verifie "le runner est lancé sans les deux variables réservées (env -u)" $rc
! printf '%s\n' "$code_script" | grep -F 'finish_branch.sh --' | grep -vF 'finish_branch.sh --check' | grep -q .; rc=$?; SORTIE="option autre que --check"; verifie "finish_branch.sh n'est appelé qu'avec --check" $rc
printf '%s\n' "$code_script" | grep -qF 'bash tools/finish_branch.sh --check'; rc=$?; SORTIE="contrôle par défaut"; verifie "le contrôle par défaut est bash tools/finish_branch.sh --check" $rc
printf '%s\n' "$code_script" | grep -qF 'bash tests/run_all.sh'; rc=$?; SORTIE="runner par défaut"; verifie "le runner par défaut est bash tests/run_all.sh, sans filtre" $rc
! printf '%s\n' "$code_script" | grep -F 'run_all.sh' | grep -q -e '--staged' -e 'run_all.sh [a-z]'; rc=$?; SORTIE="runner filtré"; verifie "le runner n'est ni filtré ni ciblé" $rc
! grep -v '^[[:space:]]*#' "$script" | grep -qE 'tools/finish_branch\.sh.*(sed|awk)|verif_[0-9]+'; rc=$?; SORTIE="contrôle réimplémenté"; verifie "aucun contrôle du script de fin n'est réimplémenté" $rc
! grep -qF 'tools/worktree.sh ou tools/finish_branch.sh' "$script"; rc=$?; SORTIE="interdiction de modifier finish_branch.sh"; verifie "l'en-tête n'interdit plus de modifier tools/finish_branch.sh" $rc
! printf '%s\n' "$code_script" | grep -E 'git[^|;&]* (commit|branch -[dD]|checkout|rm )' >/dev/null; rc=$?; SORTIE="commande interdite"; verifie "le script ne valide, ne supprime ni ne checkout" $rc
printf '%s\n' "$code_script" | grep -qF '</dev/null'; rc=$?; SORTIE="entrée non fermée"; verifie "le script de fin est lancé avec </dev/null" $rc
grep -qF 'tools/finish_branch.sh' "$script"; rc=$?; SORTIE="finish_branch absent"; verifie "le script de fin par défaut est tools/finish_branch.sh" $rc

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
