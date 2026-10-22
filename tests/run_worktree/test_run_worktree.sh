#!/bin/bash
# Test du script du dossier d'exécution (tools/run_worktree.sh, change run-worktree, R-43) : dépôt de développement Git temporaire,
# dépôt distant nu temporaire, dossier d'exécution, dossier de données du labo, horloge et fenêtres remplacés par des variables,
# faux « uv » qui journalise ses appels. Un test par code de sortie de la décision D3 (0 à 9), les cas du verrou de la veille et des
# trois repères (D12, D14), de l'état du matin (safe-branch-finish), de la préparation des dépendances, des phrases en français et en anglais.
# Aucun réseau, aucun vrai uv, ni le vrai dossier du labo, ni le vrai dossier d'exécution, ni le vrai dossier de données.
# Lancement à la main : bash tests/run_worktree/test_run_worktree.sh (ROUGE tant que tools/run_worktree.sh n'existe pas).
#
# Variables que le script doit lire (noms fixés par cette suite) :
#   PMZILLA_LAB_RUN                 emplacement du dossier d'exécution
#   PMZILLA_LAB_DATA                dossier de données du labo (verrou et repères)
#   PMZILLA_RUN_NOW                 horloge en secondes (âge = PMZILLA_RUN_NOW - debut ; heures du matin lues sur l'heure locale de cet instant) ;
#                                   la lecture de repli (date de modification du dossier) et le délai de 10 s sans pid restent sur l'horloge réelle, comme watch.sh
#   PMZILLA_RUN_MORNING_START       « HH:MM », début du matin, défaut 06:45 (borne comprise)
#   PMZILLA_RUN_MORNING_END         « HH:MM », fin de la période du matin, défaut 22:00 (borne comprise ; heure limite de watch.sh)
#   PMZILLA_RUN_FALLBACK_TIME       « HH:MM », heure de repli quand l'état du matin est illisible, défaut 09:30
#   DB_BACKUP_SAUVEGARDES           dossier des sauvegardes (la suite le place hors du dossier de données)
#   (change safe-branch-finish : l'état du matin remplace les deux fenêtres horaires ; PMZILLA_RUN_MORNING_WINDOW et PMZILLA_RUN_BACKUP_WINDOW n'ont plus d'effet)
#   PMZILLA_WATCH_LOCK_MAX_AGE      âge maximal du verrou veille.verrou (défaut 21600, constante de watch.sh)
#   PMZILLA_RUN_MARKER_MAX_AGE      âge maximal des repères (défaut 21600, constante partagée avec db_backup.sh et offsite_backup.sh)
# Option de langue : « --language fr|en » acceptée avant et après la sous-commande.
# Appels de uv attendus : « uv sync --locked --script tools/<script>.py » depuis le dossier d'exécution, pour chaque script du dépôt
# qui a un bloc `# /// script` et un fichier .lock (liste des liens de tools/install_links.sh, plus composants.py).
set -u
unset PMZILLA_SKIP_GREEN_CHECK PMZILLA_NO_EVALS
racine="$(cd "$(dirname "$0")/../.." && pwd)"
script="$racine/tools/run_worktree.sh"
tmp=$(mktemp -d) || exit 1
vivants=""
trap 'for p in $vivants; do kill "$p" 2>/dev/null; done; chmod -R u+w "$tmp" 2>/dev/null; rm -rf "$tmp"' EXIT
export GIT_CONFIG_GLOBAL="$tmp/gitconfig" GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0
git config --global user.email t@example.org
git config --global user.name test
git config --global init.defaultBranch main
ok=0; ko=0; n=0
SORTIE=""; ERR=""; CODE=0
PATH_INITIAL="$PATH"

verifie() { # description condition-vraie (0 = vrai)
  if [ "$2" -eq 0 ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1 :: $SORTIE"; ko=$((ko+1)); fi
}
contient() { printf '%s' "$SORTIE" | grep -qF -- "$1"; }
contient_err() { printf '%s' "$ERR" | grep -qF -- "$1"; }
code_et() { # description code-attendu [phrase]
  desc=$1; attendu=$2; phrase=${3:-}
  if [ "$CODE" -eq "$attendu" ] && { [ -z "$phrase" ] || contient "$phrase"; }; then
    echo "ok : $desc"; ok=$((ok+1))
  else
    echo "ECHEC : $desc (code $CODE, attendu $attendu, phrase « $phrase ») :: $SORTIE"; ko=$((ko+1))
  fi
}

# instant local de 2026-10-14 « HH:MM » en secondes (fuseau du système, comme les déclenchements de launchd)
instant() { date -j -f "%Y-%m-%d %H:%M" "2026-10-14 $1" +%s; }

en_tete_script() { # fichier avec|sans : script avec ou sans bloc de dépendances
  if [ "$2" = avec ]; then printf '# /// script\n# requires-python = ">=3.11"\n# dependencies = ["pyyaml"]\n# ///\nprint(1)\n' > "$1"; else printf 'print(1)\n' > "$1"; fi
}

modele_construit=0
construit_modele() { # une seule fois par lancement de la suite : dépôt de développement et distant nu après le premier push (test-speed-2, D17)
  modele="$tmp/modele"; mkdir -p "$modele"
  git init -q --bare "$modele/distant.git"
  git init -q "$modele/dev"
  ( cd "$modele/dev" || exit 1
    git remote add origin "$modele/distant.git"
    mkdir -p tools watch-placeholder
    cp "$racine/tools/install_links.sh" tools/install_links.sh 2>/dev/null || echo '# liens' > tools/install_links.sh
    cp "$script" tools/run_worktree.sh 2>/dev/null
    cp "$racine/tools/lab_paths.sh" tools/lab_paths.sh 2>/dev/null   # module partagé : le dossier d'exécution par défaut (R-77)
    cp "$racine/tools/morning_state.sh" tools/morning_state.sh 2>/dev/null   # module partagé de l'état du matin (morning-guard D1) : sourcé par le script
    en_tete_script tools/composants.py avec; echo lock > tools/composants.py.lock
    en_tete_script tools/flux_jira.py avec; echo lock > tools/flux_jira.py.lock
    en_tete_script tools/watch_lab.py sans
    echo base > tools/outil.sh; : > watch-placeholder/.gitkeep; printf 'ignore.log\n' > .gitignore
    git add -A && git commit -q -m initial && git push -q origin main ) || exit 1
  modele_construit=1
}
nouveau() { # copie du dépôt modèle (développement + distant nu) + faux uv + variables ; se place dans le dépôt de développement
  n=$((n+1))
  cas="$tmp/cas$n"; distant="$cas/distant.git"; dev="$cas/dev"
  export HOME="$cas/home"; RUN="$cas/run"; DATA="$cas/data"
  export PMZILLA_LAB_RUN="$RUN" PMZILLA_LAB_DATA="$DATA"
  SAUV="$cas/sauvegardes"; export DB_BACKUP_SAUVEGARDES="$SAUV"   # dossier des sauvegardes de ce cas, hors du dossier de données
  unset PMZILLA_WATCH_LOCK_MAX_AGE PMZILLA_RUN_MARKER_MAX_AGE PMZILLA_RUN_MORNING_WINDOW PMZILLA_RUN_BACKUP_WINDOW PMZILLA_WATCH_NOW UV_STUB_FAIL_ON
  unset PMZILLA_RUN_MORNING_START PMZILLA_RUN_MORNING_END PMZILLA_RUN_FALLBACK_TIME
  NOW=$(instant 12:00); export PMZILLA_RUN_NOW="$NOW"
  mkdir -p "$cas/home" "$cas/bin"
  UVLOG="$cas/uv.log"; : > "$UVLOG"
  cat > "$cas/bin/uv" <<STUB
#!/bin/sh
printf '%s | %s\n' "\$(pwd -P)" "\$*" >> "$UVLOG"
case "\$*" in *"\${UV_STUB_FAIL_ON:-@@aucun@@}"*) echo "uv stub: échec demandé" >&2; exit 1 ;; esac
exit 0
STUB
  chmod +x "$cas/bin/uv"; export PATH="$cas/bin:$PATH_INITIAL"
  [ "$modele_construit" -eq 1 ] || construit_modele
  mkdir -p "$cas"
  cp -R "$modele/distant.git" "$distant"
  cp -R "$modele/dev" "$dev"
  git -C "$dev" remote set-url origin "$distant"   # la copie ne pointe plus vers le modèle
  cd "$dev" || exit 1
  SCRIPT_DEV="$dev/tools/run_worktree.sh"
}
avance() { # nouveau commit sur main du dépôt de développement (main est la branche extraite)
  printf '%s\n' "$RANDOM$RANDOM" > "$dev/tools/outil.sh"; git -C "$dev" add -A; git -C "$dev" commit -q -m "avance $RANDOM"
}
tete_dev() { git -C "$dev" rev-parse refs/heads/main; }
tete_run() { git -C "$RUN" rev-parse HEAD 2>/dev/null; }

instantane() { # état du dossier de données (arborescence et contenus) et du dossier des sauvegardes (arborescence seule)
  if [ -d "$DATA" ]; then
    ( cd "$DATA" && find . -print | sort && find . -type f | sort | while read -r f; do printf '%s=' "$f"; cat "$f"; echo; done )
  else echo "(absent)"; fi
  if [ -e "$SAUV" ]; then ( cd "$SAUV" 2>/dev/null && find . -print 2>/dev/null | sort ); ls -ld "$SAUV" | cut -c1-10; else echo "(sauvegardes absentes)"; fi
}
lance() { # arguments du script ; contrôle aussi que le dossier de données est identique avant et après
  avant=$(instantane)
  bash "$SCRIPT_DEV" "$@" >"$cas/sortie" 2>"$cas/erreur"; CODE=$?
  SORTIE="$(cat "$cas/sortie" "$cas/erreur" 2>/dev/null)"; ERR="$(cat "$cas/erreur" 2>/dev/null)"
  apres=$(instantane)
  [ "$avant" = "$apres" ]; verifie "verrou et repères identiques avant et après : $*" $?
}
cree() { # crée le dossier d'exécution et vide le journal de uv
  lance create; : > "$UVLOG"
}
vivant() { sleep 600 & PID_VIVANT=$!; disown "$PID_VIVANT" 2>/dev/null; vivants="$vivants $PID_VIVANT"; }
mort() { true & PID_MORT=$!; wait "$PID_MORT" 2>/dev/null; }
pose() { # nom pid|- age-secondes|- : dossier de verrou ou de repère ; « - » = fichier absent
  mkdir -p "$DATA/$1"
  [ "$2" = - ] || echo "$2" > "$DATA/$1/pid"
  [ "$3" = - ] || echo $((NOW - $3)) > "$DATA/$1/debut"
}
ancien() { touch -t 202001010000 "$DATA/$1"; }   # date de modification très ancienne
appels_uv() { wc -l < "$UVLOG" | tr -d ' '; }

MARQUEURS=("veille.verrou|veille|watch" "sauvegarde.encours|sauvegarde|backup" "horsmac-copie.encours|copie hors du Mac|off-site copy" "horsmac-restauration.encours|test de restauration hors du Mac|off-site restore test")

# --- le script existe
SORTIE="tools/run_worktree.sh absent"; [ -f "$script" ]; verifie "le script tools/run_worktree.sh existe" $?

# --- aide
nouveau; lance --help
code_et "aide : code 0 et les codes décrits" 0 "reportée"
[ ! -e "$RUN" ] && [ "$(appels_uv)" -eq 0 ]; verifie "aide : rien n'est créé, uv non appelé" $?

# --- usage : code 2
nouveau; lance
code_et "code 2 : sans sous-commande" 2
[ ! -e "$RUN" ]; verifie "code 2 : rien n'est créé" $?
nouveau; lance frobnicate
code_et "code 2 : sous-commande inconnue" 2
nouveau; lance --language de status
code_et "code 2 : langue inconnue" 2

# --- create : création, déjà présent, occupé
nouveau; lance create
code_et "code 0 : create en français" 0 "run_worktree : créé"
[ "$(tete_run)" = "$(tete_dev)" ]; verifie "create : tête détachée au sommet de main" $?
[ "$(git -C "$RUN" rev-parse --abbrev-ref HEAD)" = HEAD ]; verifie "create : aucune branche n'est extraite" $?
[ -z "$(git -C "$dev" branch --list | grep -v main)" ]; verifie "create : aucune branche créée dans le dépôt de développement" $?
[ -f "$RUN/watch-placeholder/.gitkeep" ] && [ "$(ls -A "$RUN/watch-placeholder" | wc -l | tr -d ' ')" -eq 1 ]; verifie "create : les dossiers de contenu ne tiennent que leur espace réservé" $?
contient "run_worktree : dépendances préparées"; verifie "create : la préparation est annoncée" $?
nouveau; lance --language en create
code_et "code 0 : create en anglais" 0 "run_worktree: created"
# dossier d'exécution par défaut (R-77) : sans PMZILLA_LAB_RUN, le dossier run du dossier du lab (parent du dépôt de développement)
nouveau; unset PMZILLA_LAB_RUN; export PMZILLA_LAB_WORKSPACE="$dev"; RUN="$cas/run"
lance create
code_et "code 0 : create sans PMZILLA_LAB_RUN crée le dossier run du dossier du lab" 0 "run_worktree : créé"
[ "$(tete_run)" = "$(tete_dev)" ]; verifie "défaut : le dossier run du dossier du lab est au sommet de main" $?
unset PMZILLA_LAB_WORKSPACE
nouveau; unset PMZILLA_LAB_RUN; export PMZILLA_LAB_WORKSPACE="$cas/absent"
lance status
code_et "code 78 : PMZILLA_LAB_WORKSPACE sur un dossier absent, sans PMZILLA_LAB_RUN" 78 "PMZILLA_LAB_WORKSPACE désigne un dossier absent"
unset PMZILLA_LAB_WORKSPACE
# PMZILLA_LAB_RUN posé, PMZILLA_LAB_DATA absent, résolution en échec : sortie 78, sans lire le verrou ni les repères avec un dossier de données vide
nouveau; unset PMZILLA_LAB_DATA; export PMZILLA_LAB_WORKSPACE="$cas/absent"
lance status
code_et "code 78 : PMZILLA_LAB_WORKSPACE sur un dossier absent, PMZILLA_LAB_RUN posé, dossier de données non posé" 78 "PMZILLA_LAB_WORKSPACE désigne un dossier absent"
unset PMZILLA_LAB_WORKSPACE
nouveau; cree; lance create
code_et "code 0 : déjà présent (français)" 0 "run_worktree : déjà présent"
[ "$(appels_uv)" -eq 0 ]; verifie "déjà présent : rien n'est changé, pas de préparation" $?
nouveau; cree; lance --language en create
code_et "code 0 : déjà présent (anglais)" 0 "run_worktree: already present"
nouveau; mkdir -p "$RUN"; echo mien > "$RUN/fichier.txt"
lance create
code_et "code 4 : create sur un dossier qui n'est pas le dossier d'exécution" 4 "le dossier existe et n'est pas le dossier d'exécution"
[ "$(cat "$RUN/fichier.txt")" = mien ] && [ "$(ls -A "$RUN" | wc -l | tr -d ' ')" -eq 1 ]; verifie "code 4 : le dossier est intact" $?
lance --language en create
code_et "code 4 : create occupé (anglais)" 4 "the folder exists and is not the run tree"

# --- code 3 : dépôt de développement ou main introuvable
nouveau; mkdir -p "$cas/horsdepot/tools"; cp "$SCRIPT_DEV" "$cas/horsdepot/tools/" 2>/dev/null
SCRIPT_DEV="$cas/horsdepot/tools/run_worktree.sh"; lance create
code_et "code 3 : script hors de tout dépôt" 3 "dépôt de développement introuvable"
nouveau; git -C "$dev" branch -m main autre; lance create
code_et "code 3 : pas de main local" 3 "dépôt de développement introuvable"
lance --language en status
code_et "code 3 : phrase anglaise" 3 "development checkout not found"

# --- code 1 : commande Git en échec (le dossier parent du dossier d'exécution n'est pas inscriptible)
nouveau; mkdir -p "$cas/ferme"; export PMZILLA_LAB_RUN="$cas/ferme/run"; RUN="$PMZILLA_LAB_RUN"; chmod 555 "$cas/ferme"
lance create
code_et "code 1 : commande git en échec" 1 "run_worktree : commande git en échec"
lance --language en create
code_et "code 1 : phrase anglaise" 1 "run_worktree: git command failed"
chmod 755 "$cas/ferme"

# --- status : manquant, propre, en retard, branche, hors historique, modifications
nouveau; lance status
code_et "code 4 : status, dossier d'exécution absent" 4 "dossier d'exécution absent"
[ ! -e "$RUN" ]; verifie "code 4 : status ne crée rien" $?
lance --language en status
code_et "code 4 : status absent (anglais)" 4 "run_worktree: run tree missing"
nouveau; cree; lance status
code_et "code 0 : status propre au sommet de main" 0 "run_worktree : à jour"
lance --language en status
code_et "code 0 : status à jour (anglais)" 0 "run_worktree: up to date"
nouveau; cree; avance; avant_tete=$(tete_run); lance status
code_et "code 8 : status en retard sur main" 8 "run_worktree : en retard sur main"
lance --language en status
code_et "code 8 : en retard (anglais)" 8 "run_worktree: behind main"
[ "$(tete_run)" = "$avant_tete" ] && [ "$(appels_uv)" -eq 0 ]; verifie "status : tête inchangée, aucune préparation" $?
nouveau; cree; git -C "$RUN" checkout -q -b travail; lance status
code_et "code 6 : status, dossier d'exécution sur une branche" 6 "pas sur un ancêtre de main"
nouveau; cree; git -C "$RUN" commit -q --allow-empty -m ailleurs; lance status
code_et "code 6 : status, hors de l'historique de main" 6
nouveau; cree; echo x >> "$RUN/tools/outil.sh"; lance status
code_et "code 5 : status, fichier suivi modifié" 5 "modifications locales dans le dossier d'exécution"
nouveau; cree; vivant; pose veille.verrou "$PID_VIVANT" 60; avance; export PMZILLA_RUN_NOW="$(instant 07:30)"; lance status
code_et "status : ni verrou ni fenêtre ne comptent (code 8)" 8

# --- update : mouvement, à jour, refus 4/5/6
nouveau; cree; avance; lance update
code_et "code 0 : update en retard, mis à jour" 0 "run_worktree : mis à jour"
[ "$(tete_run)" = "$(tete_dev)" ]; verifie "update : la tête est au sommet de main" $?
contient "serveur de la bibliothèque : l'ancien code reste chargé jusqu'à la prochaine session"; verifie "update : rappel du serveur de la bibliothèque (français)" $?
contient "dépendances préparées"; verifie "update : dépendances préparées" $?
! printf '%s' "$SORTIE" | grep -q '—'; verifie "update : aucun tiret cadratin" $?
nouveau; cree; avance; lance --language en update
code_et "update en anglais : updated" 0 "run_worktree: updated"
contient "library server: the old code stays loaded until the next session"; verifie "update : rappel du serveur (anglais)" $?
nouveau; cree; avance; lance update --language en
code_et "update puis --language en : accepté après la sous-commande" 0 "run_worktree: updated"
nouveau; cree; lance update
code_et "code 0 : update déjà à jour" 0 "run_worktree : à jour"
nouveau; cree; git -C "$dev" checkout -q -b feat/x; git -C "$dev" checkout -q main; avance; git -C "$dev" checkout -q feat/x; lance update
code_et "update : main avance alors que le dépôt de développement est sur une autre branche" 0 "mis à jour"
[ "$(tete_run)" = "$(tete_dev)" ]; verifie "update : sommet de main local, pas de la branche courante" $?
nouveau; lance update
code_et "code 4 : update, dossier d'exécution absent" 4 "dossier d'exécution absent"
[ ! -e "$RUN" ]; verifie "code 4 : update ne crée rien" $?
nouveau; cree; avance; echo x >> "$RUN/tools/outil.sh"; avant_tete=$(tete_run); lance update
code_et "code 5 : fichier suivi modifié" 5 "modifications locales dans le dossier d'exécution"
[ "$(tete_run)" = "$avant_tete" ] && [ "$(tail -1 "$RUN/tools/outil.sh")" = x ]; verifie "code 5 : tête et fichier inchangés" $?
lance --language en update
code_et "code 5 : refus en anglais" 5 "run_worktree: local changes in the run tree"
contient_err "run_worktree: local changes in the run tree"; verifie "code 5 : la phrase est sur la sortie d'erreur" $?
contient_err "bash tools/run_worktree.sh update"; verifie "code 5 : la commande à relancer est donnée" $?
nouveau; cree; avance; echo x > "$RUN/nouveau.txt"; lance update
code_et "code 5 : fichier non suivi non ignoré" 5
rm "$RUN/nouveau.txt"; echo y > "$RUN/stage.txt"; git -C "$RUN" add stage.txt; lance update
code_et "code 5 : fichier indexé" 5
nouveau; cree; avance; echo log > "$RUN/ignore.log"; lance update
code_et "update : un fichier ignoré ne bloque pas" 0 "mis à jour"
nouveau; cree; avance; git -C "$RUN" checkout -q -b travail; avant_tete=$(tete_run); lance update
code_et "code 6 : update sur une branche" 6 "pas sur un ancêtre de main"
[ "$(tete_run)" = "$avant_tete" ] && [ "$(git -C "$RUN" rev-parse --abbrev-ref HEAD)" = travail ]; verifie "code 6 : rien ne change" $?
lance --language en update
code_et "code 6 : phrase anglaise" 6 "run_worktree: the run tree is not on an ancestor of main"
nouveau; cree; git -C "$RUN" commit -q --allow-empty -m ailleurs; avance; avant_tete=$(tete_run); lance update
code_et "code 6 : update hors de l'historique de main" 6
[ "$(tete_run)" = "$avant_tete" ]; verifie "code 6 : tête inchangée" $?

# --- code 9 : préparation des dépendances
nouveau; lance create
SORTIE="$(cat "$UVLOG")"
[ "$(appels_uv)" -eq 2 ]; verifie "create : un appel de uv par script préparable (composants.py et flux_jira.py, pas watch_lab.py)" $?
grep -q 'sync --locked --script tools/composants.py' "$UVLOG" && grep -q 'sync --locked --script tools/flux_jira.py' "$UVLOG"; verifie "create : sync --locked --script pour composants.py et flux_jira.py" $?
! grep -q 'watch_lab.py' "$UVLOG"; verifie "create : un script sans bloc de dépendances n'est pas préparé" $?
[ "$(cut -d'|' -f1 "$UVLOG" | sort -u | tr -d ' ')" = "$(cd "$RUN" && pwd -P)" ]; verifie "create : uv lancé depuis le dossier d'exécution" $?
! cut -d'|' -f2- "$UVLOG" | grep -Eq 'upgrade|[[:space:]]lock|[[:space:]]add|pip'; verifie "create : aucune commande uv qui écrit un verrou ou ajoute une dépendance" $?
nouveau; cree; avance; lance update
SORTIE="$(cat "$UVLOG")"
[ "$(appels_uv)" -eq 2 ]; verifie "update : préparation en mode verrouillé, une fois par script" $?
[ -z "$(git -C "$RUN" status --porcelain)" ]; verifie "update : aucun fichier de verrou ni fichier suivi écrit" $?
nouveau; cree; avance; export UV_STUB_FAIL_ON="flux_jira.py"; lance update
code_et "code 9 : préparation en échec après le mouvement" 9 "run_worktree : dépendances non préparées"
contient "flux_jira.py"; verifie "code 9 : le script en échec est nommé" $?
contient_err "bash tools/run_worktree.sh update"; verifie "code 9 : la commande à relancer est donnée" $?
[ "$(tete_run)" = "$(tete_dev)" ]; verifie "code 9 : la tête reste au sommet de main" $?
[ -z "$(git -C "$RUN" status --porcelain)" ]; verifie "code 9 : aucun fichier suivi modifié" $?
lance --language en update
code_et "code 9 : phrase anglaise, tête déjà au sommet" 9 "run_worktree: dependencies not prepared"
unset UV_STUB_FAIL_ON; : > "$UVLOG"; lance update
code_et "relance au sommet : à jour" 0 "run_worktree : à jour"
SORTIE="$(cat "$UVLOG")"
[ "$(appels_uv)" -eq 2 ]; verifie "relance au sommet : la préparation est refaite" $?
nouveau; export UV_STUB_FAIL_ON="composants.py"; lance create
code_et "code 9 : create, préparation en échec" 9 "dépendances non préparées"
contient "composants.py"; verifie "code 9 : composants.py est nommé" $?
[ -d "$RUN" ]; verifie "code 9 : le dossier d'exécution reste créé" $?

# --- code 7 : verrou de la veille et repères tenus par un processus vivant (français et anglais)
for def in "${MARQUEURS[@]}"; do
  IFS='|' read -r dossier tache job <<EOF2
$def
EOF2
  nouveau; cree; avance; vivant; pose "$dossier" "$PID_VIVANT" 60; avant_tete=$(tete_run); lance update
  code_et "code 7 : $dossier tenu (français)" 7 "run_worktree : mise à jour reportée, passage planifié en cours ($tache)"
  contient_err "bash tools/run_worktree.sh update"; verifie "code 7 : $dossier : la commande à relancer est donnée sur la sortie d'erreur" $?
  [ "$(tete_run)" = "$avant_tete" ] && [ "$(appels_uv)" -eq 0 ]; verifie "code 7 : $dossier : tête inchangée, aucune préparation" $?
  lance --language en update
  code_et "code 7 : $dossier tenu (anglais)" 7 "run_worktree: update postponed, scheduled run in progress ($job)"
done

# --- dossier sans identifiant de processus
for def in "${MARQUEURS[@]}"; do
  IFS='|' read -r dossier tache job <<EOF2
$def
EOF2
  nouveau; cree; avance; pose "$dossier" - -; lance update
  code_et "code 7 : $dossier sans pid, récent : en création, tenu" 7 "($tache)"
done
nouveau; cree; avance; pose veille.verrou - -; ancien veille.verrou; lance update
code_et "dossier sans pid vieux de plus de 10 s : périmé, ignoré, mise à jour faite" 0 "run_worktree : repère de passage périmé, ignoré (veille)"
[ -d "$DATA/veille.verrou" ]; verifie "sans pid périmé : le dossier est toujours là" $?
nouveau; cree; avance; mkdir -p "$DATA/sauvegarde.encours"; echo pasunnombre > "$DATA/sauvegarde.encours/pid"; lance update
code_et "pid illisible et récent : tenu" 7 "(sauvegarde)"
nouveau; cree; avance; vivant; pose horsmac-copie.encours "$PID_VIVANT" -; lance update
code_et "repère sans fichier debut, date de modification récente : tenu" 7 "(copie hors du Mac)"
nouveau; cree; avance; vivant; pose horsmac-copie.encours "$PID_VIVANT" -; ancien horsmac-copie.encours; lance update
code_et "repère sans fichier debut, date de modification ancienne : périmé" 0 "repère de passage périmé, ignoré (copie hors du Mac)"
nouveau; cree; avance; vivant; pose veille.verrou "$PID_VIVANT" -; ancien veille.verrou; lance --language en update
code_et "verrou sans debut, ancien : périmé (anglais)" 0 "run_worktree: stale run marker, ignored (watch)"

# --- verrou et repères périmés : processus mort, âge
for def in "${MARQUEURS[@]}"; do
  IFS='|' read -r dossier tache job <<EOF2
$def
EOF2
  nouveau; cree; avance; mort; pose "$dossier" "$PID_MORT" 60; lance update
  code_et "$dossier : processus mort, périmé et ignoré (français)" 0 "run_worktree : repère de passage périmé, ignoré ($tache)"
  [ "$(tete_run)" = "$(tete_dev)" ]; verifie "$dossier : processus mort, la mise à jour a eu lieu" $?
  [ -d "$DATA/$dossier" ]; verifie "$dossier : le dossier est toujours là après la mise à jour" $?
  nouveau; cree; avance; mort; pose "$dossier" "$PID_MORT" 60; lance --language en update
  code_et "$dossier : processus mort (anglais)" 0 "run_worktree: stale run marker, ignored ($job)"
  nouveau; cree; avance; vivant; pose "$dossier" "$PID_VIVANT" 21601; lance update
  code_et "$dossier : processus vivant mais plus de 21600 s : périmé" 0 "repère de passage périmé, ignoré ($tache)"
  nouveau; cree; avance; vivant; pose "$dossier" "$PID_VIVANT" 21599; lance update
  code_et "$dossier : processus vivant et 21599 s : tenu" 7 "($tache)"
done

# --- âges maximaux configurables, chacun pour son groupe
nouveau; cree; avance; vivant; export PMZILLA_WATCH_LOCK_MAX_AGE=100; pose veille.verrou "$PID_VIVANT" 200; lance update
code_et "PMZILLA_WATCH_LOCK_MAX_AGE=100, verrou de 200 s : périmé" 0 "périmé, ignoré (veille)"
nouveau; cree; avance; vivant; export PMZILLA_WATCH_LOCK_MAX_AGE=100; pose veille.verrou "$PID_VIVANT" 50; lance update
code_et "PMZILLA_WATCH_LOCK_MAX_AGE=100, verrou de 50 s : tenu" 7
nouveau; cree; avance; vivant; export PMZILLA_RUN_MARKER_MAX_AGE=100; pose sauvegarde.encours "$PID_VIVANT" 200; lance update
code_et "PMZILLA_RUN_MARKER_MAX_AGE=100, repère de 200 s : périmé" 0 "périmé, ignoré (sauvegarde)"
nouveau; cree; avance; vivant; export PMZILLA_RUN_MARKER_MAX_AGE=100; pose veille.verrou "$PID_VIVANT" 200; lance update
code_et "l'âge maximal des repères ne s'applique pas au verrou de la veille" 7 "(veille)"
nouveau; cree; avance; vivant; export PMZILLA_WATCH_LOCK_MAX_AGE=100; pose horsmac-restauration.encours "$PID_VIVANT" 200; lance update
code_et "l'âge maximal du verrou ne s'applique pas aux repères" 7 "(test de restauration hors du Mac)"

# --- plusieurs repères, dossier de données absent
nouveau; cree; avance; vivant; mort; pose veille.verrou "$PID_MORT" 60; pose sauvegarde.encours "$PID_VIVANT" 60; lance update
code_et "verrou périmé et repère tenu : refus nommant la sauvegarde" 7 "(sauvegarde)"
contient "périmé, ignoré (veille)"; verifie "verrou périmé et repère tenu : le verrou périmé est signalé" $?
nouveau; cree; avance; lance update
code_et "dossier de données absent : aucun repère, mise à jour faite" 0 "mis à jour"
[ ! -e "$DATA" ]; verifie "dossier de données absent : il n'est pas créé" $?

# --- code 7 : état du matin (safe-branch-finish D1 à D4, D8) : le repère du passage du jour de la veille et le dossier daté des sauvegardes
a_heure() { export PMZILLA_RUN_NOW="$(instant "$1")"; NOW=$PMZILLA_RUN_NOW; }   # heure du jour de test ; les verrous posés ensuite s'en servent
jour_paris() { TZ=Europe/Paris date -r "$NOW" +%Y-%m-%d; }
jour_systeme() { date -r "$NOW" +%Y-%m-%d; }
veille_etat() { # etat [date] : repère du passage du jour, au format de watch.sh ; la date est celle de Paris du jour de test par défaut
  mkdir -p "$DATA"
  printf '{"date": "%s", "declencheur": "planifie", "debut": "06:50", "fin": "07:10", "etat": "%s", "code": 0}\n' "${2:-$(jour_paris)}" "$1" > "$DATA/veille-du-jour.json"
}
sauvegarde_du_jour() { mkdir -p "$SAUV/db-$(jour_systeme)${1:-}"; }   # dossier daté du jour (suffixe : dossier étiqueté)
matin_fini() { veille_etat termine; sauvegarde_du_jour; }

# matin terminé : la mise à jour passe, même dans l'ancienne fenêtre du matin
nouveau; cree; avance; a_heure 07:30; matin_fini; lance update
code_et "matin terminé (veille et sauvegarde) à 07:30 : la mise à jour passe" 0 "run_worktree : mis à jour"
[ "$(tete_run)" = "$(tete_dev)" ]; verifie "matin terminé : la tête est au sommet de main" $?
! contient "illisible"; verifie "matin terminé : aucune ligne d'état illisible" $?
for etat in termine echoue interrompu; do
  nouveau; cree; avance; a_heure 08:00; veille_etat "$etat"; sauvegarde_du_jour; lance update
  code_et "veille $etat et sauvegarde du jour : la mise à jour passe" 0 "mis à jour"
done
nouveau; cree; avance; a_heure 12:00; matin_fini; lance --language en update
code_et "matin terminé (anglais)" 0 "run_worktree: updated"

# une partie manquante : refus nommant la partie
nouveau; cree; avance; a_heure 07:30; veille_etat termine; mkdir -p "$SAUV"; avant_tete=$(tete_run); lance update
code_et "veille terminée, sauvegarde du jour absente : code 7 nommant la sauvegarde" 7 "run_worktree : mise à jour reportée, passages du matin pas terminés (sauvegarde)"
contient_err "bash tools/run_worktree.sh update"; verifie "sauvegarde pas terminée : la commande à relancer est donnée" $?
[ "$(tete_run)" = "$avant_tete" ] && [ "$(appels_uv)" -eq 0 ]; verifie "sauvegarde pas terminée : tête inchangée, aucune préparation" $?
lance --language en update
code_et "sauvegarde pas terminée (anglais)" 7 "run_worktree: update postponed, morning runs not finished (backup)"
nouveau; cree; avance; a_heure 07:30; veille_etat termine; sauvegarde_du_jour "-manuel"; lance update
code_et "seul un dossier étiqueté du jour : la sauvegarde n'est pas finie" 7 "(sauvegarde)"
nouveau; cree; avance; a_heure 07:30; veille_etat termine; mkdir -p "$SAUV/db-2020-01-01"; lance update
code_et "seul le dossier d'un autre jour : la sauvegarde n'est pas finie" 7 "(sauvegarde)"
nouveau; cree; avance; a_heure 07:30; sauvegarde_du_jour; veille_etat termine "2020-01-01"; lance update
code_et "repère d'un autre jour, sauvegarde faite : code 7 nommant la veille" 7 "passages du matin pas terminés (veille)"
nouveau; cree; avance; a_heure 07:30; veille_etat termine "2020-01-01"; lance update
code_et "veille et sauvegarde manquantes : la veille est nommée en premier" 7 "(veille)"
! contient "(sauvegarde)"; verifie "veille et sauvegarde manquantes : seule la veille est nommée" $?

# la veille reportée, commencée ou d'un autre jour : la raison de l'attente et la reprise (fiche Q1)
for def in "reporte|reporté|reported" "commence|commencé|started"; do
  IFS='|' read -r etat etat_fr etat_en <<EOF2
$def
EOF2
  nouveau; cree; avance; a_heure 07:30; veille_etat "$etat"; sauvegarde_du_jour; avant_tete=$(tete_run); lance update
  code_et "veille $etat : code 7 nommant la veille" 7 "run_worktree : mise à jour reportée, passages du matin pas terminés (veille)"
  contient_err "run_worktree : en attente du repère du passage du jour de la veille, état : $etat_fr"; verifie "veille $etat : la raison de l'attente donne l'état lu" $?
  contient_err "Une fois la veille débloquée : bash tools/run_worktree.sh update"; verifie "veille $etat : la commande de reprise est donnée" $?
  ! contient "Pour le relancer plus tard"; verifie "veille $etat : la ligne générique de relance est remplacée" $?
  ! contient "veille-du-jour"; verifie "veille $etat : aucun nom de fichier du repère" $?
  ! contient "$cas"; verifie "veille $etat : aucun chemin de la machine" $?
  [ "$(tete_run)" = "$avant_tete" ] && [ "$(appels_uv)" -eq 0 ]; verifie "veille $etat : tête inchangée, aucune préparation" $?
  lance --language en update
  code_et "veille $etat (anglais) : la raison" 7 "run_worktree: waiting for the record of the day's watch run, state: $etat_en"
  contient_err "Once the watch is unblocked: bash tools/run_worktree.sh update"; verifie "veille $etat (anglais) : la reprise" $?
  contient "run_worktree: update postponed, morning runs not finished (watch)"; verifie "veille $etat (anglais) : la phrase du matin" $?
done
nouveau; cree; avance; a_heure 07:30; veille_etat termine "2020-01-01"; sauvegarde_du_jour; lance update
contient_err "état : d'un autre jour"; verifie "repère d'un autre jour : l'état lu est dit" $?
lance --language en update
contient_err "state: of another day"; verifie "repère d'un autre jour (anglais) : l'état lu est dit" $?
! contient "$cas"; verifie "repère d'un autre jour : aucun chemin de la machine" $?

# bornes de la période du matin : le début et la fin sont compris ; avant et après, les parties ne sont pas lues
nouveau; cree; avance; a_heure 06:45; lance update
code_et "06:45 (début du matin), rien de fait : refus" 7 "passages du matin"
nouveau; cree; avance; a_heure 22:00; veille_etat reporte; lance update
code_et "22:00 (fin de la période) : encore reporté" 7 "(veille)"
nouveau; cree; avance; a_heure 06:44; veille_etat reporte; lance update
code_et "06:44, avant le début du matin : les parties ne sont pas lues, la mise à jour passe" 0 "mis à jour"
! contient "illisible"; verifie "avant le début du matin : aucune ligne d'état" $?
nouveau; cree; avance; a_heure 22:01; veille_etat reporte; lance update
code_et "22:01, après la fin de la période : la mise à jour passe" 0 "mis à jour"
nouveau; cree; avance; a_heure 23:59; lance update
code_et "23:59, rien de lisible : la mise à jour passe sans lire" 0 "mis à jour"
! contient "illisible"; verifie "après la fin : aucune ligne d'état" $?
nouveau; cree; avance; a_heure 10:30; export PMZILLA_RUN_MORNING_START=10:00 PMZILLA_RUN_MORNING_END=11:00; veille_etat reporte; lance update
code_et "début du matin surchargé : 10:30 est dans la période" 7 "(veille)"
nouveau; cree; avance; a_heure 07:30; export PMZILLA_RUN_MORNING_START=10:00 PMZILLA_RUN_MORNING_END=11:00; veille_etat reporte; lance update
code_et "début du matin surchargé : 07:30 est avant" 0 "mis à jour"
nouveau; cree; avance; a_heure 11:30; export PMZILLA_RUN_MORNING_START=10:00 PMZILLA_RUN_MORNING_END=11:00; veille_etat reporte; lance update
code_et "fin du matin surchargée : 11:30 est après" 0 "mis à jour"
nouveau; cree; avance; a_heure 07:30; export PMZILLA_RUN_MORNING_START=25:99 PMZILLA_RUN_MORNING_END=abc; veille_etat reporte; lance update
code_et "valeurs invalides : retour aux défauts (07:30 dans la période)" 7 "(veille)"

# état illisible : reporté jusqu'à l'heure de repli, puis la mise à jour continue avec une ligne d'information
nouveau; cree; avance; a_heure 08:00; sauvegarde_du_jour; avant_tete=$(tete_run); lance update
code_et "repère absent à 08:00, avant l'heure de repli : code 7, état illisible" 7 "run_worktree : mise à jour reportée, état des passages du matin illisible, avant 09:30"
contient_err "bash tools/run_worktree.sh update"; verifie "état illisible : la commande à relancer est donnée" $?
[ "$(tete_run)" = "$avant_tete" ] && [ "$(appels_uv)" -eq 0 ]; verifie "état illisible : tête inchangée, aucune préparation" $?
lance --language en update
code_et "état illisible (anglais)" 7 "run_worktree: update postponed, morning runs state unreadable, before 09:30"
nouveau; cree; avance; a_heure 09:29; sauvegarde_du_jour; lance update
code_et "repère absent à 09:29 : encore reporté" 7 "avant 09:30"
nouveau; cree; avance; a_heure 09:30; sauvegarde_du_jour; lance update
code_et "repère absent à 09:30 (heure de repli) : la mise à jour passe" 0 "mis à jour"
contient "run_worktree : état des passages du matin illisible, heure de repli passée"; verifie "après l'heure de repli : la ligne d'information est écrite" $?
lance --language en update
contient "run_worktree: morning runs state unreadable, fallback time passed"; verifie "après l'heure de repli (anglais) : la ligne d'information" $?
nouveau; cree; avance; a_heure 12:00; sauvegarde_du_jour; mkdir -p "$DATA"; echo "pas du json" > "$DATA/veille-du-jour.json"; lance update
code_et "repère illisible après l'heure de repli : la mise à jour passe avec la ligne" 0 "heure de repli passée"
nouveau; cree; avance; a_heure 08:00; sauvegarde_du_jour; mkdir -p "$DATA"; echo '{"date": "x", "etat": "termine"}' > "$DATA/veille-du-jour.json"; lance update
code_et "repère sans date valide avant le repli : illisible, code 7" 7 "illisible"
nouveau; cree; avance; a_heure 08:00; sauvegarde_du_jour; mkdir -p "$DATA"; printf '{"date": "%s", "etat": "inconnu"}\n' "$(jour_paris)" > "$DATA/veille-du-jour.json"; lance update
code_et "repère sans état connu avant le repli : illisible, code 7" 7 "illisible"
nouveau; cree; avance; a_heure 12:00; veille_etat termine; mkdir -p "$SAUV"; lance update
code_et "après l'heure de repli, l'autre partie lisible et pas finie reporte encore" 7 "(sauvegarde)"
nouveau; cree; avance; a_heure 12:00; veille_etat reporte; lance update
code_et "après l'heure de repli, la veille lisible et pas finie reporte encore" 7 "(veille)"
nouveau; cree; avance; a_heure 08:00; veille_etat termine; sauvegarde_du_jour; chmod 000 "$SAUV"; lance update
code_et "dossier des sauvegardes illisible avant le repli : code 7, état illisible" 7 "état des passages du matin illisible, avant 09:30"
chmod 755 "$SAUV"
nouveau; cree; avance; a_heure 12:00; veille_etat termine; sauvegarde_du_jour; chmod 000 "$SAUV"; lance update
code_et "dossier des sauvegardes illisible après le repli : la mise à jour passe avec la ligne" 0 "heure de repli passée"
chmod 755 "$SAUV"
nouveau; cree; avance; a_heure 08:00; sauvegarde_du_jour; export PMZILLA_RUN_FALLBACK_TIME=08:30; lance update
code_et "heure de repli surchargée : 08:00 est avant 08:30" 7 "avant 08:30"
a_heure 08:30; lance update
code_et "heure de repli surchargée : 08:30 est l'heure de repli" 0 "mis à jour"

# dossier des sauvegardes absent : la partie sauvegarde ne compte pas ; ni liste ni écriture
nouveau; cree; avance; a_heure 07:30; veille_etat termine; [ ! -e "$SAUV" ]; lance update
code_et "dossier des sauvegardes absent : la partie sauvegarde ne compte pas" 0 "mis à jour"
! contient "illisible"; verifie "dossier des sauvegardes absent : ce n'est pas un état illisible" $?
[ ! -e "$SAUV" ]; verifie "dossier des sauvegardes absent : il n'est pas créé" $?
nouveau; cree; avance; a_heure 07:30; [ ! -e "$SAUV" ]; lance update
code_et "dossier des sauvegardes absent et veille manquante : la veille retient" 7 "illisible"
# sans la variable du script de sauvegarde : le dossier des sauvegardes du dossier de données (module partagé)
nouveau; cree; avance; a_heure 07:30; unset DB_BACKUP_SAUVEGARDES; veille_etat termine; mkdir -p "$DATA/sauvegardes"; lance update
code_et "sans variable : le dossier des sauvegardes du dossier de données est lu" 7 "(sauvegarde)"
mkdir -p "$DATA/sauvegardes/db-$(jour_systeme)"; lance update
code_et "sans variable : le dossier daté du jour dans le dossier de données" 0 "mis à jour"

# verrous et repères d'abord, à toute heure ; la sous-commande status ne lit pas l'état du matin
nouveau; cree; avance; a_heure 07:30; matin_fini; vivant; pose veille.verrou "$PID_VIVANT" 60; lance update
code_et "matin terminé mais verrou de la veille tenu : le verrou refuse" 7 "passage planifié en cours (veille)"
nouveau; cree; avance; a_heure 07:30; mort; pose veille.verrou "$PID_MORT" 60; lance update
code_et "verrou périmé le matin sans état lisible : l'état du matin refuse" 7 "passages du matin"
nouveau; cree; avance; a_heure 07:30; lance status
code_et "status ne lit pas l'état du matin" 8 "en retard sur main"

# les anciennes variables de fenêtres n'ont plus d'effet
nouveau; cree; avance; a_heure 12:00; matin_fini; export PMZILLA_RUN_MORNING_WINDOW="00:00-23:59" PMZILLA_RUN_BACKUP_WINDOW="00:00-23:59"; lance update
code_et "anciennes variables de fenêtres : sans effet, matin terminé" 0 "mis à jour"
! contient "fenêtre"; verifie "plus aucune phrase de fenêtre" $?
nouveau; cree; avance; a_heure 07:30; matin_fini; export PMZILLA_RUN_MORNING_WINDOW="06:00-23:00"; lance update
code_et "ancienne variable du matin : l'ancienne fenêtre ne retient plus" 0 "mis à jour"

# les constantes et les états finaux sont ceux de watch.sh
fin_script=$(sed -n 's/.*FIN_MATIN=\$(heure_ou "\${PMZILLA_RUN_MORNING_END:-}" "\([0-9:]*\)").*/\1/p' "$script" | head -1)
limite_watch=$(sed -n 's/^HEURE_LIMITE="\([0-9:]*\)".*/\1/p' "$racine/tools/watch.sh" | head -1)
SORTIE="run_worktree.sh=$fin_script watch.sh=$limite_watch"
[ -n "$fin_script" ] && [ "$fin_script" = "$limite_watch" ]; verifie "la fin de la période du matin par défaut égale l'heure limite de watch.sh" $?
finaux_script=$(sed -n 's/^ETATS_FINAUX="\(.*\)".*/\1/p' "$script" | head -1 | tr ' ' '\n' | sort | tr '\n' ' ')
finaux_watch=$(grep -v '^[[:space:]]*#' "$racine/tools/watch.sh" | sed -n 's/.*R_ETAT" == (\([a-z|]*\)) ]].*/\1/p' | head -1 | tr '|' '\n' | sort | tr '\n' ' ')
SORTIE="run_worktree.sh=$finaux_script watch.sh=$finaux_watch"
[ -n "$finaux_script" ] && [ "$finaux_script" = "$finaux_watch" ]; verifie "les états finaux sont ceux qui terminent le jour dans watch.sh" $?
defauts=$(grep -c 'PMZILLA_RUN_MORNING_START:-}" "06:45"' "$script"); defauts2=$(grep -c 'PMZILLA_RUN_FALLBACK_TIME:-}" "09:30"' "$script")
SORTIE="début=$defauts repli=$defauts2"
[ "$defauts" -eq 1 ] && [ "$defauts2" -eq 1 ]; verifie "défauts : début du matin 06:45, heure de repli 09:30" $?
! grep -v '^[[:space:]]*#' "$script" | grep -q 'PMZILLA_RUN_MORNING_WINDOW\|PMZILLA_RUN_BACKUP_WINDOW'; verifie "le script ne lit plus les anciennes variables de fenêtres" $?
! grep -v '^[[:space:]]*#' "$script" | grep -qF 'fenêtre'; verifie "la phrase de fenêtre est retirée du script" $?

# --- le script n'emploie aucune commande interdite et ne touche à aucun verrou ni repère
sans_commentaires=$(grep -v '^[[:space:]]*#' "$script" 2>/dev/null)
mot='(^|[^[:alnum:]_-])(reset|clean|stash|prune|fetch|pull)([^[:alnum:]_-]|$)'
printf '%s\n' "$sans_commentaires" | grep -E "git" | grep -Eq -e "$mot"; r=$?
SORTIE="commande git interdite (reset, clean, stash, prune, fetch, pull) ou script absent"; [ -n "$sans_commentaires" ] && [ "$r" -ne 0 ]; verifie "aucun reset, clean, stash, prune, fetch ni pull dans le script" $?
printf '%s\n' "$sans_commentaires" | grep -Eq -e 'worktree[[:space:]]+(remove|prune)|checkout[[:space:]]+(-f|--force)|--force|push|switch[[:space:]]+(-f|--discard)'; r=$?
SORTIE="commande interdite (worktree remove, prune, checkout forcé, push) ou script absent"; [ -n "$sans_commentaires" ] && [ "$r" -ne 0 ]; verifie "aucun worktree remove, checkout forcé ni push dans le script" $?
printf '%s\n' "$sans_commentaires" | grep -E -e '(^|[^[:alnum:]_])(mkdir|rm|rmdir|touch|mv)([^[:alnum:]_]|$)' | grep -Eq -e 'verrou|encours|VERROU|REPERE'; r=$?
SORTIE="création ou suppression d'un verrou ou d'un repère, ou script absent"; [ -n "$sans_commentaires" ] && [ "$r" -ne 0 ]; verifie "aucun mkdir, rm, rmdir, touch ni mv d'un verrou ou d'un repère" $?
printf '%s\n' "$sans_commentaires" | grep -Eq -e '>[[:space:]]*"?\$[{A-Za-z_]*(VERROU|DATA|REPERE)'; r=$?
SORTIE="écriture dans le dossier de données, ou script absent"; [ -n "$sans_commentaires" ] && [ "$r" -ne 0 ]; verifie "aucune redirection vers le dossier de données" $?

# --- âges maximaux par défaut : mêmes constantes que watch.sh, db_backup.sh et offsite_backup.sh
constante() { # fichier variable : valeur par défaut écrite « ${VARIABLE:-valeur} »
  grep -v '^[[:space:]]*#' "$1" 2>/dev/null | sed -n "s/.*\${$2:-\([0-9][0-9]*\)}.*/\1/p" | head -1
}
v_watch=$(constante "$racine/tools/watch.sh" PMZILLA_WATCH_LOCK_MAX_AGE)
v_run_verrou=$(constante "$script" PMZILLA_WATCH_LOCK_MAX_AGE)
SORTIE="watch.sh=$v_watch run_worktree.sh=$v_run_verrou"
[ -n "$v_watch" ] && [ "$v_watch" = "$v_run_verrou" ]; verifie "l'âge maximal du verrou par défaut égale celui de watch.sh" $?
[ "$v_run_verrou" = 21600 ]; verifie "l'âge maximal du verrou par défaut vaut 21600 s" $?
v_run=$(constante "$script" PMZILLA_RUN_MARKER_MAX_AGE)
# les constantes de db_backup.sh et offsite_backup.sh sont comparées dans leurs suites (tâche 8.3)
SORTIE="run_worktree.sh=$v_run"
[ "$v_run" = 21600 ]; verifie "l'âge maximal des repères par défaut vaut 21600 s dans run_worktree.sh" $?

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
