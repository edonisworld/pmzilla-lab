#!/bin/sh
# Test du script de fin de branche (tools/finish_branch.sh) : dépôt Git temporaire, dépôt distant nu temporaire,
# faux runner (FINISH_BRANCH_RUNNER) et faux dossier d'enregistrements du jeu d'essai (FINISH_BRANCH_RECORDS).
# Un test par code de sortie (0 à 11), plus les cas de la spécification (branche de spécification, change archivé sur la branche,
# commit ultérieur sur d'autres fichiers, vocabulaire ou mémoire figée sans passage, état testé disparu, commit non référencé encore présent).
# Change safe-branch-finish : le mode --check <branche> (un cas par code 3 à 8 et 12, aucun changement, aucun runner) et les causes du code 13.
# Le dépôt temporaire contient une copie suivie de finish_branch.sh, de run_worktree.sh (ce dernier lit son propre dépôt) et de lab_paths.sh ;
# le dossier d'exécution est un faux dossier (PMZILLA_LAB_RUN), les données du labo un faux dossier (PMZILLA_LAB_DATA), l'horloge est fixée à midi.
# Aucun réseau, aucune base, aucun jeu d'essai, aucun vrai runner. Lancement à la main : sh tests/finish_branch/test_finish_branch.sh
set -u
unset PMZILLA_SKIP_GREEN_CHECK PMZILLA_NO_EVALS FINISH_WORKTREE_ALLOW_SKIP FINISH_BRANCH_TESTED_TOKEN FINISH_BRANCH_FORCE_RUN FINISH_LOCK_TOKEN PMZILLA_FINISH_LOCK_MAX_AGE PMZILLA_RUN_MORNING_START   # un script de fin lance cette suite avec ces variables : elles ne doivent rien y changer (test-speed-2, groupe 0 ; début du matin : R-104)
outils="$(cd "$(dirname "$0")/../../tools" && pwd)"
script="$outils/finish_branch.sh"
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
export GIT_CONFIG_GLOBAL="$tmp/gitconfig" GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0
# le vrai hook pre-push contrôle les noms des messages qui partent (fix/sorties-et-masquage) : liste fictive, jamais la vraie
printf 'Vexillonia\n' > "$tmp/noms-fictifs.txt"; unset PMZILLA_NOMS; export PMZILLA_LAB_SENSITIVE_NAMES="$tmp/noms-fictifs.txt"
git config --global user.email t@example.org
git config --global user.name test
git config --global init.defaultBranch main
BASH_FIN=bash; [ -x /bin/bash ] && BASH_FIN=/bin/bash   # les scripts de fin tournent sous le bash du système (3.2 sur Mac) : finish-under-lock D13
ok=0; ko=0
n=0
MIDI=$(date -j -f "%Y-%m-%d %H:%M" "2026-01-15 12:00" +%s 2>/dev/null || date -d "2026-01-15 12:00" +%s)

verifie() { # description condition-vraie (0 = vrai)
  if [ "$2" -eq 0 ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1 :: $SORTIE"; ko=$((ko+1)); fi
}
contient() { printf '%s' "$SORTIE" | grep -qF -- "$1"; }
code_et() { # description code-attendu [phrase] : contrôle le dernier lancement
  desc=$1; attendu=$2; phrase=${3:-}
  if [ "$CODE" -eq "$attendu" ] && { [ -z "$phrase" ] || contient "$phrase"; }; then
    echo "ok : $desc"; ok=$((ok+1))
  else
    echo "ECHEC : $desc (code $CODE, attendu $attendu, phrase « $phrase ») :: $SORTIE"; ko=$((ko+1))
  fi
}

modele_construit=0
construit_modele() { # une seule fois par lancement de la suite : dépôt de travail et dépôt distant nu, après le premier push (test-speed-2, D17)
  modele="$tmp/modele"; mkdir -p "$modele"
  git init -q --bare "$modele/distant.git"
  git init -q "$modele/travail"
  ( cd "$modele/travail" || exit 1
    git remote add origin "$modele/distant.git"
    mkdir -p tools openspec/changes/archive .claude/commands .claude/agents .claude/skills/pmzilla-x tests/postures/memoire
    echo base > tools/outil.sh; echo c > CLAUDE.md; echo s > .claude/skills/pmzilla-x/SKILL.md
    echo v > tests/postures/vocabulaire.yaml; echo m > tests/postures/memoire/m.md
    echo cmd > .claude/commands/c.md; echo ag > .claude/agents/autre.md; echo ag > .claude/agents/pmzilla-critic.md
    cp "$outils/morning_state.sh" tools/   # module du garde-fou du matin (morning-guard D1) : lancé par finish_branch.sh, sourcé par run_worktree.sh
    cp "$outils/finish_branch.sh" "$outils/run_worktree.sh" "$outils/lab_paths.sh" "$outils/finish_env.sh" "$outils/finish_lock.sh" "$outils/finish_merge.sh" "$outils/light_finish.sh" "$outils/select_suites.py" "$outils/light_validate.py" tools/   # light_finish.sh : décision du chemin allégé (light-spec-finish D3) ; select_suites.py : liste des suites qui lisent openspec/ ; lab_paths.sh : module partagé des dossiers (R-77, D9) ; finish_env.sh : signature d'environnement (test-speed D9) ; finish_lock.sh : verrou de fin (multi-session-piloting D5, module sourcé comme finish_env.sh)
    echo "# a" > openspec/changes/archive/.gitkeep; printf 'ignore.log\n' > .gitignore
    echo "# liste déclarée vide : le sélecteur ne rend que les gardes (light-spec-finish, Q10)" > tests/openspec_readers.txt
    cp "$outils/posture_eval_fingerprint.py" tools/   # empreinte des fichiers évalués (posture-evals-on-branch-tip D2) : lue par le contrôle 6
    cp "$outils/../tests/postures/fichiers-evalues.txt" tests/postures/   # la liste partagée des chemins évalués (D3)
    git add -A && git commit -q -m initial && git push -q origin main ) || exit 1
  modele_construit=1
}
nouveau() { # copie le dépôt modèle (travail et distant nu) dans un dossier de cas, des enregistrements vides ; place dans le dépôt de travail
  n=$((n+1))
  cas="$tmp/cas$n"; distant="$cas/distant.git"; travail="$cas/travail"; export FINISH_BRANCH_RECORDS="$cas/essais"
  mkdir -p "$cas" "$FINISH_BRANCH_RECORDS"
  [ "$modele_construit" -eq 1 ] || construit_modele
  cp -R "$modele/distant.git" "$distant"
  cp -R "$modele/travail" "$travail"
  git -C "$travail" remote set-url origin "$distant"   # la copie ne pointe plus vers le modèle
  cd "$travail" || exit 1
  export PMZILLA_LAB_RUN="$cas/run" PMZILLA_LAB_DATA="$cas/data" PMZILLA_RUN_NOW="$MIDI" DB_BACKUP_SAUVEGARDES="$cas/sauvegardes"
  mkdir -p "$PMZILLA_LAB_DATA"
  export FINISH_BRANCH_RUNNER=true
  export FINISH_MORNING_CHECK=true   # garde-fou du matin (morning-guard D6) : « true » par défaut, sinon la commande par défaut lirait l'état réel du Mac
  unset FINISH_BRANCH_VALIDATE FINISH_BRANCH_LIGHT_RUNNER   # light-spec-finish : les faux de la validation et du passage allégé sont posés par cas
}
sur_branche() { git checkout -q -b "$1"; }   # nom de branche
valide() { # fichier contenu message : un commit qui écrit le fichier
  mkdir -p "$(dirname "$1")"; printf '%s\n' "$2" > "$1"; git add -A; git commit -q -m "$3"
}
lance() { SORTIE=$("$BASH_FIN" "$travail/tools/finish_branch.sh" "$@" 2>&1); CODE=$?; }
cree_run() { git worktree add -q --detach "$cas/run" main; }   # dossier d'exécution détaché au sommet de main
enregistre() { # nom base complet validant rejuge langue : écrit un enregistrement du jeu d'essai
  mkdir -p "$FINISH_BRANCH_RECORDS/$1"
  cat > "$FINISH_BRANCH_RECORDS/$1/resultats.json" <<EOF
{"date": "$1", "base": "$2", "langue": "$6", "complet": $3, "validant": $4, "rejuge": $5,
 "cas": [{"id": "c1", "verifications": [{"critere": "a", "ok": true}, {"critere": "b", "ok": false}, {"critere": "i", "ok": false, "indicateur": true}]}]}
EOF
}
enregistre_e() { # nom base empreinte complet validant rejuge langue : comme enregistre, avec le champ evaluated_fingerprint
  enregistre "$1" "$2" "$4" "$5" "$6" "$7"
  sed "s|\"base\": \"$2\"|\"base\": \"$2\", \"evaluated_fingerprint\": \"$3\"|" "$FINISH_BRANCH_RECORDS/$1/resultats.json" > "$FINISH_BRANCH_RECORDS/$1/x" && mv "$FINISH_BRANCH_RECORDS/$1/x" "$FINISH_BRANCH_RECORDS/$1/resultats.json"
}
chemins_evalues() { grep -v '^[[:space:]]*#' "$travail/tests/postures/fichiers-evalues.txt" | grep -v '^[[:space:]]*$'; }
empreinte_de() { # rév : empreinte v1 des chemins évalués, calculée par le module (les formats sont vérifiés à part, côté Python)
  python3 -I "$outils/posture_eval_fingerprint.py" "$1" $(chemins_evalues)
}
etat_main() { git rev-parse refs/heads/main; }

# --- code 0 : fusion, push, suppression des deux branches
nouveau; sur_branche feat/travail; valide tools/outil.sh un "code"; git push -q origin feat/travail
avant=$(git rev-parse main)
lance
code_et "code 0 : terminé" 0 "finish_branch : terminé"
contient "fusion" && contient "push" && contient "suppression"; verifie "code 0 : la sortie liste fusion, push et suppression" $?
[ "$(git rev-parse --abbrev-ref HEAD)" = main ] && [ "$(git rev-list --parents -n1 main | wc -w)" -eq 3 ]; verifie "code 0 : main est un commit de fusion à deux parents" $?
[ "$(git rev-parse main)" = "$(git --git-dir="$distant" rev-parse main)" ]; verifie "code 0 : main distant égale main local" $?
git rev-parse -q --verify refs/heads/feat/travail >/dev/null; [ $? -ne 0 ]; verifie "code 0 : branche locale supprimée" $?
git --git-dir="$distant" rev-parse -q --verify refs/heads/feat/travail >/dev/null; [ $? -ne 0 ]; verifie "code 0 : branche distante supprimée" $?
[ "$(git rev-parse main^1)" = "$avant" ]; verifie "code 0 : premier parent = ancien main" $?

# --- code 0 : aide
nouveau; sur_branche feat/aide
lance --help
code_et "aide : code 0 et description des vérifications" 0 "Vérifications"
[ "$(git rev-parse main)" = "$(git rev-parse HEAD)" ]; verifie "aide : rien n'est changé" $?

# --- code 1 : runner en échec
nouveau; sur_branche feat/rouge; valide tools/outil.sh deux "code"; avant=$(etat_main)
FINISH_BRANCH_RUNNER=false lance
code_et "code 1 : tests en échec" 1 "finish_branch : tests en échec, rien n'est fusionné"
[ "$(etat_main)" = "$avant" ] && [ "$(git --git-dir="$distant" rev-parse main)" = "$avant" ]; verifie "code 1 : main inchangé (local et distant)" $?

# --- code 2 : usage
nouveau; sur_branche feat/usage
lance --inconnue
code_et "code 2 : option inconnue" 2 "finish_branch : usage"
lance quelquechose
code_et "code 2 : argument inattendu" 2 "finish_branch : usage"

# --- code 3 : pas de branche à terminer
nouveau
lance
code_et "code 3 : sur main" 3 "finish_branch : aucune branche à terminer"
contient "La branche courante est main."; verifie "code 3 : lancement normal, ligne de détail « La branche courante est main. »" $?
! contient "La branche à terminer est main."; verifie "code 3 : lancement normal, pas la ligne du mode vérification" $?
lance --check main
code_et "code 3 : --check main" 3 "finish_branch : aucune branche à terminer"
contient "La branche à terminer est main."; verifie "code 3 : --check, ligne de détail « La branche à terminer est main. »" $?
sur_branche feat/detache; valide tools/outil.sh trois "code"; git checkout -q --detach
lance
code_et "code 3 : tête détachée" 3 "finish_branch : aucune branche à terminer"
SORTIE=$(cd "$tmp" && "$BASH_FIN" "$script" 2>&1); CODE=$?
code_et "code 3 : hors dépôt" 3 "finish_branch : aucune branche à terminer"

# --- code 3 : branche spike/* refusée (une préversion fusionnée par erreur, R-47)
nouveau; sur_branche spike/essai; valide tools/outil.sh un "essai"; avant=$(etat_main)
lance
code_et "code 3 : branche spike/* refusée" 3 "spike/"
[ "$(etat_main)" = "$avant" ] && [ "$(git rev-parse --abbrev-ref HEAD)" = spike/essai ]; verifie "spike/* : rien n'est fusionné, branche inchangée" $?

# --- code 4 : arbre non propre
nouveau; sur_branche feat/sale; valide tools/outil.sh quatre "code"; echo x > nouveau.txt
lance
code_et "code 4 : fichier non suivi" 4 "finish_branch : l'arbre n'est pas propre"
[ -f nouveau.txt ]; verifie "code 4 : le fichier est intact" $?
rm nouveau.txt; echo modifie >> tools/outil.sh
lance
code_et "code 4 : fichier modifié" 4 "finish_branch : l'arbre n'est pas propre"
git checkout -q -- tools/outil.sh; echo i >> tools/outil.sh; git add tools/outil.sh
lance
code_et "code 4 : fichier indexé" 4 "finish_branch : l'arbre n'est pas propre"
nouveau; sur_branche feat/ignore; valide tools/outil.sh cinq "code"; echo x > ignore.log
lance
code_et "arbre : un fichier ignoré seul ne bloque pas" 0 "finish_branch : terminé"

# --- code 5 : change OpenSpec non archivé
nouveau; mkdir -p openspec/changes/mon-change; echo p > openspec/changes/mon-change/proposal.md; git add -A; git commit -q -m "change"; git push -q origin main
sur_branche feat/mon-change; valide tools/outil.sh six "code"
lance
code_et "code 5 : branche nommée d'après un change ouvert, nom cité" 5 "finish_branch : change OpenSpec non archivé"
contient "mon-change"; verifie "code 5 : le change est nommé" $?
nouveau; mkdir -p openspec/changes/autre-change; echo p > openspec/changes/autre-change/proposal.md; git add -A; git commit -q -m "change"; git push -q origin main
sur_branche feat/sans-rapport; valide tools/outil.sh sept "code"; valide openspec/changes/autre-change/tasks.md t "tâches"
lance
# finish-under-lock D6 : le contrôle 19 passe avant le 5 ; une branche qui touche le dossier d'un change actif sous un autre nom est refusée par le 19
code_et "code 19 avant le 5 : dossier du change touché avec du code, autre nom de branche" 19 "finish_branch : la branche touche un autre change OpenSpec : autre-change"
nouveau; mkdir -p openspec/changes/archivable; echo p > openspec/changes/archivable/proposal.md; git add -A; git commit -q -m "change"; git push -q origin main
sur_branche feat/archivable; valide tools/outil.sh huit "code"; git mv openspec/changes/archivable openspec/changes/archive/2026-10-10-archivable; git commit -q -m archive
lance
code_et "change archivé sur la branche : la vérification passe" 0 "finish_branch : terminé"
nouveau; mkdir -p openspec/changes/spec-seule; echo p > openspec/changes/spec-seule/proposal.md; git add -A; git commit -q -m "change"; git push -q origin main
sur_branche feat/spec-seule; valide openspec/changes/spec-seule/design.md d "spécification"
lance
code_et "branche de spécification : passe" 0 "branche de spécification"
nouveau; mkdir -p openspec/changes/ailleurs; echo p > openspec/changes/ailleurs/proposal.md; git add -A; git commit -q -m "change"; git push -q origin main
sur_branche feat/neutre; valide tools/outil.sh neuf "code"
lance
code_et "change ouvert mais sans lien avec la branche : passe" 0 "finish_branch : terminé"

# --- code 6 : jeu d'essai validant
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; avant=$(etat_main)
lance
code_et "code 6 : posture changée, aucun enregistrement" 6 "finish_branch : jeu d'essai validant absent"
[ "$(etat_main)" = "$avant" ]; verifie "code 6 : main inchangé" $?
nouveau; sur_branche feat/vocabulaire; valide tests/postures/vocabulaire.yaml modif "vocabulaire"
lance
code_et "code 6 : vocabulaire changé sans passage" 6 "finish_branch : jeu d'essai validant absent"
nouveau; sur_branche feat/memoire; valide tests/postures/memoire/m.md modif "mémoire"
lance
code_et "code 6 : mémoire figée changée sans passage" 6 "finish_branch : jeu d'essai validant absent"
nouveau; sur_branche feat/instructions; valide CLAUDE.md modif "instructions"
lance
code_et "code 6 : CLAUDE.md changé sans passage" 6 "finish_branch : jeu d'essai validant absent"
nouveau; sur_branche feat/critic; valide .claude/agents/pmzilla-critic.md modif "critic"
lance
code_et "code 6 : agent Critic changé sans passage" 6 "finish_branch : jeu d'essai validant absent"

# sans FINISH_BRANCH_RECORDS : les enregistrements sont dans le dossier « essais » du dossier de données donné par le module partagé
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; tete=$(git rev-parse HEAD)
FINISH_BRANCH_RECORDS="$PMZILLA_LAB_DATA/essais" enregistre 2026-10-03-100000 "$tete" true true false fr
SORTIE=$(env -u FINISH_BRANCH_RECORDS "$BASH_FIN" "$travail/tools/finish_branch.sh" 2>&1); CODE=$?
code_et "sans FINISH_BRANCH_RECORDS : enregistrement lu dans le dossier essais du dossier de données" 0 "2026-10-03-100000 (1/2)"
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; tete=$(git rev-parse HEAD)
FINISH_BRANCH_RECORDS="$cas/ailleurs" enregistre 2026-10-03-100000 "$tete" true true false fr
SORTIE=$(env -u FINISH_BRANCH_RECORDS "$BASH_FIN" "$travail/tools/finish_branch.sh" 2>&1); CODE=$?
code_et "sans FINISH_BRANCH_RECORDS : un enregistrement hors du dossier essais du dossier de données ne compte pas" 6 "finish_branch : jeu d'essai validant absent"

# sans FINISH_BRANCH_RECORDS et module des dossiers en échec : refus 6
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; avant=$(etat_main)
SORTIE=$(env -u FINISH_BRANCH_RECORDS PMZILLA_LAB_WORKSPACE="$cas/absent" "$BASH_FIN" "$travail/tools/finish_branch.sh" 2>&1); CODE=$?
code_et "code 6 : module des dossiers en échec, dossier de données introuvable" 6 "le dossier de données du lab est introuvable"
[ "$(etat_main)" = "$avant" ]; verifie "code 6 : module en échec, main inchangé" $?

# enregistrements qui ne comptent pas
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; tete=$(git rev-parse HEAD)
enregistre 2026-10-01-100000 "$tete" false true false fr
lance
code_et "code 6 : passage partiel seul" 6 "finish_branch : jeu d'essai validant absent"
enregistre 2026-10-01-100000 "$tete" true false false fr
lance
code_et "code 6 : passage non validant seul" 6 "finish_branch : jeu d'essai validant absent"
enregistre 2026-10-01-100000 "$tete" true true true fr
lance
code_et "code 6 : rejugement seul" 6 "finish_branch : jeu d'essai validant absent"
enregistre 2026-10-01-100000 "$tete" true true false en
lance
code_et "code 6 : passage en autre langue seul" 6 "finish_branch : jeu d'essai validant absent"
enregistre 2026-10-01-100000 "$(git rev-parse main)" true true false fr
lance
code_et "code 6 : passage complet dont le contenu des chemins diffère" 6 "finish_branch : jeu d'essai validant absent"
enregistre 2026-10-01-100000 1111111111111111111111111111111111111111 true true false fr
lance
code_et "code 6 : état testé disparu" 6 "l'état testé n'existe plus"

# enregistrements qui comptent
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; tete=$(git rev-parse HEAD)
enregistre 2026-10-02-100000 "$tete" true true false fr
lance
code_et "passage validant sur le sommet : passe, date et score affichés" 0 "2026-10-02-100000 (1/2)"
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; tete=$(git rev-parse HEAD)
enregistre 2026-10-02-100000 "$tete" true true false fr
valide tools/outil.sh ulterieur "autre fichier"
lance
code_et "commit ultérieur sur d'autres fichiers : le passage reste valide" 0 "jeu d'essai validant trouvé"
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"
orphelin=$(git commit-tree "HEAD^{tree}" -m "état testé non référencé")
enregistre 2026-10-02-100000 "$orphelin" true true false fr
lance
code_et "état testé non référencé mais présent : passe" 0 "jeu d'essai validant trouvé"
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; tete=$(git rev-parse HEAD)
enregistre 2026-10-01-100000 1111111111111111111111111111111111111111 true true false fr
enregistre 2026-10-02-100000 "$tete" true true false fr
lance
code_et "un enregistrement disparu est ignoré quand un autre compte" 0 "jeu d'essai validant trouvé"
nouveau; sur_branche feat/commandes; valide .claude/commands/c.md modif "commande"; valide .claude/agents/autre.md modif "agent"
lance
code_et "commandes et autres agents seulement : aucun enregistrement exigé" 0 "finish_branch : terminé"

# --- posture-evals-on-branch-tip, groupe 3 : le contrôle 6 compte un enregistrement par l'empreinte des fichiers évalués
# l'empreinte vide (aucun fichier évalué) est celle du texte vide, préfixée : vérification indépendante du module
vide_attendue="v1:$(printf '' | shasum -a 256 | cut -d' ' -f1)"
nouveau; vide_calculee=$(python3 -I "$outils/posture_eval_fingerprint.py" HEAD "rien/du/tout")
[ "$vide_calculee" = "$vide_attendue" ]; verifie "empreinte : cas vide égal au SHA-256 du texte vide, préfixé v1:" $?

nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; emp=$(empreinte_de HEAD)
enregistre_e 2026-10-02-100000 1111111111111111111111111111111111111111 "$emp" true true false fr
lance
code_et "empreinte égale, état testé disparu : passe, avec la mention de l'empreinte" 0 "2026-10-02-100000 (1/2) (empreinte des fichiers évalués)"
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; tete=$(git rev-parse HEAD); emp=$(empreinte_de HEAD)
enregistre_e 2026-10-02-100000 "$tete" "$emp" true true false fr
valide tools/outil.sh ulterieur "autre fichier"
lance
code_et "empreinte égale après un commit sur d'autres fichiers : passe" 0 "(empreinte des fichiers évalués)"
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; tete=$(git rev-parse HEAD)
enregistre_e 2026-10-02-100000 "$tete" "v1:$(printf 'autre' | shasum -a 256 | cut -d' ' -f1)" true true false fr
lance
code_et "autre empreinte, même si l'état testé a le contenu du sommet : refus 6" 6 "finish_branch : jeu d'essai validant absent"
! contient "l'état testé n'existe plus"; verifie "autre empreinte : pas le message de l'état testé disparu" $?
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; tete=$(git rev-parse HEAD); emp=$(empreinte_de HEAD)
enregistre_e 2026-10-02-100000 "$tete" "$emp" true true false fr
valide tools/posture_eval_fingerprint.py "raise SystemExit(1)" "module d'empreinte cassé"
lance
code_et "empreinte du sommet incalculable : refus 6" 6 "finish_branch : jeu d'essai validant absent"
contient "l'empreinte des fichiers évalués du sommet n'a pas pu être calculée"; verifie "empreinte incalculable : message dédié" $?
! contient "ont changé sans passage complet validant"; verifie "empreinte incalculable : pas le message générique" $?
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; tete=$(git rev-parse HEAD); emp=$(empreinte_de HEAD)
valide .claude/skills/pmzilla-x/SKILL.md modif2 "posture encore"
enregistre_e 2026-10-02-100000 "$tete" "$emp" true true false fr
lance
code_et "empreinte d'un sommet antérieur dont les fichiers évalués ont changé depuis : refus 6" 6 "finish_branch : jeu d'essai validant absent"
# un enregistrement sans empreinte garde la comparaison par l'état testé (cas d'avant) ; avec empreinte, l'état testé n'est pas comparé
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; tete=$(git rev-parse HEAD)
enregistre_e 2026-10-02-100000 "$tete" "v1:$(printf 'autre' | shasum -a 256 | cut -d' ' -f1)" true true false fr
enregistre 2026-10-01-100000 "$tete" true true false fr
lance
code_et "un enregistrement sans empreinte à côté d'un autre : le premier compte par l'état testé, sans mention" 0 "2026-10-01-100000 (1/2)"
! contient "(empreinte des fichiers évalués)"; verifie "sans empreinte : aucune mention de l'empreinte" $?
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; tete=$(git rev-parse HEAD); emp=$(empreinte_de HEAD)
enregistre_e 2026-10-02-100000 "$tete" "$emp" true false false fr
lance
code_et "empreinte égale mais passage non validant : refus 6" 6 "finish_branch : jeu d'essai validant absent"
enregistre_e 2026-10-02-100000 "$tete" "$emp" true true true fr
lance
code_et "empreinte égale mais rejugement : refus 6" 6 "finish_branch : jeu d'essai validant absent"
enregistre_e 2026-10-02-100000 "$tete" "$emp" true true false en
lance
code_et "empreinte égale mais autre langue : refus 6" 6 "finish_branch : jeu d'essai validant absent"
enregistre_e 2026-10-02-100000 "$tete" "$emp" false true false fr
lance
code_et "empreinte égale mais passage partiel : refus 6" 6 "finish_branch : jeu d'essai validant absent"

# la liste partagée : absente ou vide, refus 6 avec la phrase, sans repli sur des chemins internes
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; avant=$(etat_main)
rm "$travail/tests/postures/fichiers-evalues.txt"; git add -A; git commit -q -m "liste retirée"
lance
code_et "liste absente : refus 6 avec la phrase" 6 "liste des fichiers évalués absente ou vide"
[ "$(etat_main)" = "$avant" ]; verifie "liste absente : main inchangé" $?
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"
printf '# seulement des commentaires\n\n' > "$travail/tests/postures/fichiers-evalues.txt"; git add -A; git commit -q -m "liste vidée"
lance
code_et "liste vide : refus 6 avec la phrase" 6 "liste des fichiers évalués absente ou vide"

# sémantique des chemins (D7) : un CLAUDE.md de sous-dossier n'est pas un chemin évalué
nouveau; sur_branche feat/sousdossier; valide mothra/CLAUDE.md "instructions d'un sous-dossier" "sous-dossier"
lance
code_et "CLAUDE.md d'un sous-dossier seul : aucun enregistrement exigé" 0 "finish_branch : terminé"

# la liste est lue sans construction que le bash système (3.2) refuse : le script passe sous /bin/bash
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; emp=$(empreinte_de HEAD)
enregistre_e 2026-10-02-100000 1111111111111111111111111111111111111111 "$emp" true true false fr
SORTIE=$(/bin/bash "$travail/tools/finish_branch.sh" 2>&1); CODE=$?
code_et "sous /bin/bash : le contrôle 6 par empreinte passe" 0 "(empreinte des fichiers évalués)"
! grep -nE 'mapfile|readarray|declare -A' "$outils/finish_branch.sh" | grep -v '^[0-9]*:[[:space:]]*#' | grep -q .; verifie "aucun mapfile, readarray ni tableau associatif dans le script" $?

# --- code 7 : main pas à jour
nouveau; sur_branche feat/diverge; valide tools/outil.sh dix "code"
git clone -q "$distant" "$cas/autre"; (cd "$cas/autre" && echo d > distant.txt && git add -A && git commit -q -m "distant" && git push -q origin main)
git checkout -q main; echo l > local.txt; git add -A; git commit -q -m "local"; git checkout -q feat/diverge
avant=$(etat_main)
lance
code_et "code 7 : main local a divergé du distant" 7 "finish_branch : main n'est pas à jour"
[ "$(etat_main)" = "$avant" ]; verifie "code 7 : main inchangé" $?
nouveau; sur_branche feat/hors-ligne; valide tools/outil.sh onze "code"; git remote set-url origin "$cas/inexistant.git"
lance
code_et "code 7 : fetch impossible" 7 "finish_branch : main n'est pas à jour"
nouveau; sur_branche feat/retard; valide tools/outil.sh douze "code"
git clone -q "$distant" "$cas/autre"; (cd "$cas/autre" && echo d > distant.txt && git add -A && git commit -q -m "distant" && git push -q origin main)
lance
code_et "main local en retard sur le distant (avance rapide), branche sans main : code 8" 8 "finish_branch : la branche ne contient pas main"
[ "$(etat_main)" = "$(git --git-dir="$distant" rev-parse main)" ]; verifie "main local avancé en avance rapide" $?

# --- code 8 : la branche ne contient pas main
nouveau; sur_branche feat/derriere; valide tools/outil.sh treize "code"
git checkout -q main; valide main.txt m "sur main"; git push -q origin main; git checkout -q feat/derriere
lance
code_et "code 8 : la branche ne contient pas main" 8 "finish_branch : la branche ne contient pas main"

# --- code 9 : fusion impossible, annulée (un hook pre-merge-commit refuse)
nouveau; sur_branche feat/fusion; valide tools/outil.sh quatorze "code"; avant=$(etat_main)
printf '#!/bin/sh\nexit 1\n' > .git/hooks/pre-merge-commit; chmod +x .git/hooks/pre-merge-commit
lance
code_et "code 9 : fusion impossible" 9 "finish_branch : fusion impossible, annulée"
[ "$(git rev-parse --abbrev-ref HEAD)" = feat/fusion ]; verifie "code 9 : retour sur la branche" $?
[ "$(etat_main)" = "$avant" ] && [ ! -f .git/MERGE_HEAD ] && [ -z "$(git status --porcelain)" ]; verifie "code 9 : main inchangé, fusion annulée, arbre propre" $?

# --- code 9 : la raison réelle de l'échec est affichée (ici, le message du hook)
nouveau; sur_branche feat/raison; valide tools/outil.sh quatorze-b "code"
printf '#!/bin/sh\necho "raison-du-hook-xyz" >&2\nexit 1\n' > .git/hooks/pre-merge-commit; chmod +x .git/hooks/pre-merge-commit
lance
code_et "code 9 : la raison réelle de l'échec est affichée" 9 "raison-du-hook-xyz"

# --- code 12 : main est ouvert dans un autre dossier (worktree), refus avant toute fusion
nouveau; sur_branche feat/wt; valide tools/outil.sh douze "code"; git checkout -q main
git worktree add -q "$cas/wt" feat/wt; avant=$(etat_main)
cd "$cas/wt" || exit 1
lance
code_et "code 12 : main ouvert dans un autre worktree" 12 "finish_branch : main est ouvert dans un autre dossier"
contient "$travail"; verifie "code 12 : le message nomme le dossier où main est ouvert" $?
contient "git switch --detach" && contient "git switch feat/wt" && contient "bash tools/finish_branch.sh"; verifie "code 12 : le message donne la manoeuvre" $?
[ "$(etat_main)" = "$avant" ] && [ "$(git rev-parse --abbrev-ref HEAD)" = feat/wt ] && [ -z "$(git status --porcelain)" ]; verifie "code 12 : rien n'est changé" $?
cd "$travail" || exit 1
git worktree remove --force "$cas/wt"

# --- après la manoeuvre (worktree détaché, branche reprise dans le dossier principal), le script réussit
nouveau; sur_branche feat/wt2; valide tools/outil.sh douze-b "code"; git checkout -q main
git worktree add -q "$cas/wt" feat/wt2
(cd "$cas/wt" && git switch -q --detach); git switch -q feat/wt2
lance
code_et "code 12 : après la manoeuvre, la fin de branche réussit" 0 "finish_branch : terminé"

# --- code 10 : push refusé
nouveau; sur_branche feat/push; valide tools/outil.sh quinze "code"; avant=$(etat_main)
printf '#!/bin/sh\nexit 1\n' > "$distant/hooks/pre-receive"; chmod +x "$distant/hooks/pre-receive"
lance
code_et "code 10 : push refusé" 10 "finish_branch : push refusé"
contient "git push origin main"; verifie "code 10 : commande pour réessayer le push" $?
contient "git reset --hard $avant"; verifie "code 10 : commande pour défaire la fusion locale" $?
[ "$(git --git-dir="$distant" rev-parse main)" = "$avant" ] && [ "$(etat_main)" != "$avant" ]; verifie "code 10 : fusion sur main local seulement" $?

# --- code 11 : suppression de la branche distante refusée après fusion et push
nouveau; sur_branche feat/suppr; valide tools/outil.sh seize "code"; git push -q origin feat/suppr
cat > "$distant/hooks/pre-receive" <<'EOF'
#!/bin/sh
while read ancien nouveau ref; do case "$nouveau" in 0000000000000000000000000000000000000000) exit 1;; esac; done
exit 0
EOF
chmod +x "$distant/hooks/pre-receive"
lance
code_et "code 11 : branche non supprimée" 11 "finish_branch : branche non supprimée"
contient "fusionné"; verifie "code 11 : le message dit que le travail est fusionné" $?
[ "$(git --git-dir="$distant" rev-parse main)" = "$(etat_main)" ]; verifie "code 11 : main distant porte la fusion" $?

# --- dossier d'exécution (change run-worktree, D4)
# absent : une ligne d'information, code 0
nouveau; sur_branche feat/sans-run; valide tools/outil.sh r1 "code"
lance
code_et "run : dossier d'exécution absent, code 0 et ligne d'information" 0 "finish_branch : dossier d'exécution absent, rien à mettre à jour"
contient "finish_branch : terminé"; verifie "run : absent, la fin de branche est terminée" $?

# mis à jour : la liste le dit, puis le rappel du serveur de la bibliothèque
nouveau; cree_run; sur_branche feat/avec-run; valide tools/outil.sh r2 "code"
lance
code_et "run : mise à jour, code 0" 0 "mise à jour du dossier d'exécution"
[ "$(git -C "$cas/run" rev-parse HEAD)" = "$(etat_main)" ] && [ -z "$(git -C "$cas/run" symbolic-ref -q HEAD)" ]; verifie "run : le dossier d'exécution est détaché au nouveau sommet de main" $?
contient "serveur de la bibliothèque : l'ancien code reste chargé jusqu'à la prochaine session"; verifie "run : rappel du serveur de la bibliothèque" $?
printf '%s' "$SORTIE" | awk '/mise à jour du dossier d.exécution/ {a=NR} /serveur de la bibliothèque/ {b=NR} END {exit !(a && b && b > a)}'; verifie "run : le rappel suit la liste" $?

# un dossier d'exécution détaché ne lève pas le code 12 (vérifié par le cas ci-dessus : code 0) ; modification locale : code 13
nouveau; cree_run; sur_branche feat/local; valide tools/outil.sh r3 "code"; echo modif >> "$cas/run/tools/outil.sh"
lance
code_et "run : modification locale, code 13" 13 "finish_branch : dossier d'exécution non mis à jour"
contient "La fusion est faite et poussée dans main."; verifie "run : 13 dit que la fusion est faite et poussée" $?
contient "Pour le mettre à jour : bash tools/run_worktree.sh update"; verifie "run : 13 donne la commande de mise à jour" $?
contient "modifications locales"; verifie "run : 13 donne la cause" $?
[ "$(git --git-dir="$distant" rev-parse main)" = "$(etat_main)" ] && [ "$(git -C "$cas/run" status --porcelain)" = " M tools/outil.sh" ]; verifie "run : 13, main distant porte la fusion, le dossier d'exécution est intact" $?
git rev-parse -q --verify refs/heads/feat/local >/dev/null; [ $? -ne 0 ]; verifie "run : 13, la branche est supprimée" $?

# hors de l'historique de main
nouveau; cree_run; (cd "$cas/run" && echo h > hors.txt && git add -A && git commit -q -m hors); sur_branche feat/hors; valide tools/outil.sh r4 "code"
avant_run=$(git -C "$cas/run" rev-parse HEAD)
lance
code_et "run : hors de l'historique de main, code 13" 13 "finish_branch : dossier d'exécution non mis à jour"
[ "$(git -C "$cas/run" rev-parse HEAD)" = "$avant_run" ]; verifie "run : hors historique, le dossier d'exécution n'a pas bougé" $?

# verrou de la veille tenu par un processus vivant
nouveau; cree_run; sur_branche feat/verrou; valide tools/outil.sh r5 "code"
mkdir "$PMZILLA_LAB_DATA/veille.verrou"; echo $$ > "$PMZILLA_LAB_DATA/veille.verrou/pid"; echo "$MIDI" > "$PMZILLA_LAB_DATA/veille.verrou/debut"
avant_run=$(git -C "$cas/run" rev-parse HEAD)
lance
code_et "run : verrou de la veille tenu, code 13" 13 "finish_branch : dossier d'exécution non mis à jour"
contient "reportée"; verifie "run : 13, la cause dit que la mise à jour est reportée" $?
[ -d "$PMZILLA_LAB_DATA/veille.verrou" ] && [ "$(cat "$PMZILLA_LAB_DATA/veille.verrou/pid")" = "$$" ] && [ "$(git -C "$cas/run" rev-parse HEAD)" = "$avant_run" ]; verifie "run : le verrou et le dossier d'exécution sont inchangés" $?

# préparation des dépendances en échec (uv factice qui échoue)
nouveau; printf '# /// script\n# ///\n' > tools/composants.py; echo l > tools/composants.py.lock; git add -A; git commit -q -m "composants"; git push -q origin main
cree_run; sur_branche feat/prep; valide tools/outil.sh r6 "code"
mkdir -p "$cas/faux"; printf '#!/bin/sh\nexit 1\n' > "$cas/faux/uv"; chmod +x "$cas/faux/uv"
SORTIE=$(PATH="$cas/faux:$PATH" "$BASH_FIN" "$travail/tools/finish_branch.sh" 2>&1); CODE=$?
code_et "run : préparation des dépendances en échec, code 13" 13 "finish_branch : dossier d'exécution non mis à jour"
contient "dépendances non préparées"; verifie "run : 13, la cause dit que les dépendances ne sont pas préparées" $?

# push refusé : le dossier d'exécution n'est pas mis à jour
nouveau; cree_run; sur_branche feat/push-run; valide tools/outil.sh r7 "code"; avant_run=$(git -C "$cas/run" rev-parse HEAD)
printf '#!/bin/sh\nexit 1\n' > "$distant/hooks/pre-receive"; chmod +x "$distant/hooks/pre-receive"
lance
code_et "run : push refusé, code 10" 10 "finish_branch : push refusé"
[ "$(git -C "$cas/run" rev-parse HEAD)" = "$avant_run" ]; verifie "run : push refusé, le dossier d'exécution n'est pas mis à jour" $?

# l'aide liste les codes 12 et 13 et la phrase sur les fichiers
nouveau; sur_branche feat/aide2
lance --help
contient "13 "; verifie "aide : le code 13 est listé" $?
contient "12 main est ouvert"; verifie "aide : le code 12 est listé" $?
contient "ne modifie aucun fichier, sauf l'avance rapide du dossier d'exécution"; verifie "aide : phrase sur les fichiers modifiés" $?

# --- causes du code 13 quand la veille retient la mise à jour (safe-branch-finish D8, fiche Q1) : la raison de l'attente et la reprise
# sont gardées, la ligne générique de relance est retirée, la commande de mise à jour du script reste donnée
jour_paris_midi=$(TZ=Europe/Paris date -r "$MIDI" +%Y-%m-%d 2>/dev/null || TZ=Europe/Paris date -d "@$MIDI" +%Y-%m-%d)
jour_midi=$(date -r "$MIDI" +%Y-%m-%d 2>/dev/null || date -d "@$MIDI" +%Y-%m-%d)
for etat_veille in reporte commence; do
  nouveau; cree_run; sur_branche feat/attente-$etat_veille; valide tools/outil.sh a1 "code"
  mkdir -p "$DB_BACKUP_SAUVEGARDES/db-$jour_midi"
  printf '{"date": "%s", "declencheur": "planifie", "debut": "06:50", "fin": "07:10", "etat": "%s", "code": 0}\n' "$jour_paris_midi" "$etat_veille" > "$PMZILLA_LAB_DATA/veille-du-jour.json"
  avant_run=$(git -C "$cas/run" rev-parse HEAD)
  lance
  code_et "run : veille $etat_veille, code 13" 13 "finish_branch : dossier d'exécution non mis à jour"
  contient "mise à jour reportée, passages du matin pas terminés (veille)"; verifie "run : 13, la ligne du matin nomme la veille ($etat_veille)" $?
  contient "run_worktree : en attente du repère du passage du jour de la veille, état : "; verifie "run : 13, la raison de l'attente est gardée ($etat_veille)" $?
  contient "Une fois la veille débloquée : bash tools/run_worktree.sh update"; verifie "run : 13, la ligne de reprise est gardée ($etat_veille)" $?
  contient "Pour le mettre à jour : bash tools/run_worktree.sh update"; verifie "run : 13, la commande de mise à jour du script reste donnée ($etat_veille)" $?
  ! contient "Pour le relancer plus tard"; verifie "run : 13, la ligne générique de relance est retirée ($etat_veille)" $?
  ! contient "veille-du-jour" && ! contient "$cas"; verifie "run : 13, ni nom de fichier du repère ni chemin dans la sortie ($etat_veille)" $?
  [ "$(git -C "$cas/run" rev-parse HEAD)" = "$avant_run" ] && [ "$(git --git-dir="$distant" rev-parse main)" = "$(etat_main)" ]; verifie "run : 13 ($etat_veille), le dossier d'exécution intact, main poussé" $?
done
# sauvegarde du jour absente : la ligne générique de relance est retirée aussi, la commande de mise à jour du script reste
nouveau; cree_run; sur_branche feat/attente-sauvegarde; valide tools/outil.sh a2 "code"; mkdir -p "$DB_BACKUP_SAUVEGARDES"
printf '{"date": "%s", "etat": "termine"}\n' "$jour_paris_midi" > "$PMZILLA_LAB_DATA/veille-du-jour.json"
lance
code_et "run : sauvegarde pas terminée, code 13" 13 "passages du matin pas terminés (sauvegarde)"
! contient "Pour le relancer plus tard"; verifie "run : 13 (sauvegarde), seule la commande de mise à jour du script est donnée" $?
# matin terminé : la mise à jour passe
nouveau; cree_run; sur_branche feat/matin-fini; valide tools/outil.sh a3 "code"; mkdir -p "$DB_BACKUP_SAUVEGARDES/db-$jour_midi"
printf '{"date": "%s", "etat": "echoue"}\n' "$jour_paris_midi" > "$PMZILLA_LAB_DATA/veille-du-jour.json"
lance
code_et "run : matin terminé, la mise à jour passe" 0 "mise à jour du dossier d'exécution"

# --- mode vérification seule : --check <branche> (safe-branch-finish D5, D6)
# depuis le dossier principal, sur main, pour la branche nommée ; le faux runner journalise tout appel
verif() { # branche... : lancement du mode vérification, le runner factice pose un témoin
  FINISH_BRANCH_RUNNER="touch $cas/runner-appele" lance --check "$@"
}
etat_complet() { # main local, main distant, branches, dossier d'exécution, arbre : tout ce que le mode ne doit pas changer
  git rev-parse refs/heads/main; git --git-dir="$distant" rev-parse refs/heads/main; git for-each-ref --format='%(refname) %(objectname)' refs/heads refs/remotes | sort
  git rev-parse --abbrev-ref HEAD; git status --porcelain
  if [ -d "$cas/run" ]; then git -C "$cas/run" rev-parse HEAD; fi
}
nouveau; cree_run; sur_branche feat/verif; valide tools/outil.sh v1 "code"; git push -q origin feat/verif; git checkout -q main
avant=$(etat_complet)
verif feat/verif
code_et "vérification : tous les refus passent, ligne de réussite" 0 "finish_branch : vérification seule : la branche feat/verif peut être terminée (le runner complet reste à lancer)"
[ "$avant" = "$(etat_complet)" ]; verifie "vérification : rien n'est fusionné, poussé, supprimé ni avancé, aucune branche changée, dossier d'exécution intact" $?
[ ! -e "$cas/runner-appele" ]; verifie "vérification : le runner complet n'est pas lancé" $?
! contient "mise à jour du dossier d'exécution" && ! contient "finish_branch : terminé"; verifie "vérification : ni fin de branche ni mise à jour du dossier d'exécution" $?
git rev-parse -q --verify refs/heads/feat/verif >/dev/null && git --git-dir="$distant" rev-parse -q --verify refs/heads/feat/verif >/dev/null; verifie "vérification : la branche locale et la branche distante existent encore" $?
# la branche courante n'entre pas en jeu : depuis une autre branche propre, la branche nommée est vérifiée
git checkout -q -b feat/autre; verif feat/verif
code_et "vérification : la branche courante n'est pas celle qui est vérifiée" 0 "la branche feat/verif peut être terminée"
git checkout -q main

# usage : code 2
nouveau; sur_branche feat/u; git checkout -q main
verif
code_et "vérification : sans branche, code 2" 2 "finish_branch : usage"
verif a b
code_et "vérification : deux branches, code 2" 2 "finish_branch : usage"
verif ""
code_et "vérification : branche vide, code 2" 2 "finish_branch : usage"
lance feat/u --check
code_et "vérification : l'option après la branche, code 2" 2 "finish_branch : usage"
[ ! -e "$cas/runner-appele" ]; verifie "usage : aucun runner" $?

# code 3 : la branche nommée n'existe pas, main, spike/*
nouveau; verif feat/inconnue
code_et "vérification code 3 : branche inexistante" 3 "finish_branch : aucune branche à terminer"
verif main
code_et "vérification code 3 : main" 3 "finish_branch : aucune branche à terminer"
sur_branche spike/essai; valide tools/outil.sh v2 "essai"; git checkout -q main
verif spike/essai
code_et "vérification code 3 : branche spike/*" 3 "spike/"
verif origin/main
code_et "vérification code 3 : une branche distante seule n'est pas une branche locale" 3 "finish_branch : aucune branche à terminer"

# code 4 : arbre courant sale, ou worktree de la branche nommée sale
nouveau; sur_branche feat/sale; valide tools/outil.sh v3 "code"; git checkout -q main; echo x > nouveau.txt
verif feat/sale
code_et "vérification code 4 : arbre courant sale" 4 "finish_branch : l'arbre n'est pas propre"
[ -f nouveau.txt ]; verifie "vérification code 4 : le fichier est intact" $?
nouveau; sur_branche feat/wt-sale; valide tools/outil.sh v4 "code"; git checkout -q main
git worktree add -q "$cas/wt" feat/wt-sale
verif feat/wt-sale
code_et "vérification : worktree propre de la branche nommée, le refus 12 ne s'applique pas à lui" 0 "peut être terminée"
echo x > "$cas/wt/nouveau.txt"
verif feat/wt-sale
code_et "vérification code 4 : worktree de la branche nommée sale" 4 "Le worktree de feat/wt-sale"
[ -f "$cas/wt/nouveau.txt" ]; verifie "vérification code 4 : le fichier du worktree est intact" $?
git worktree remove --force "$cas/wt"

# code 5 : change OpenSpec non archivé, sur le sommet et le nom de la branche nommée
nouveau; mkdir -p openspec/changes/mon-change; echo p > openspec/changes/mon-change/proposal.md; git add -A; git commit -q -m "change"; git push -q origin main
sur_branche feat/mon-change; valide tools/outil.sh v5 "code"; git checkout -q main; avant=$(etat_complet)
verif feat/mon-change
code_et "vérification code 5 : change lié non archivé" 5 "finish_branch : change OpenSpec non archivé"
contient "mon-change"; verifie "vérification code 5 : le change est nommé" $?
[ "$avant" = "$(etat_complet)" ]; verifie "vérification code 5 : rien n'est changé" $?
nouveau; mkdir -p openspec/changes/archivable; echo p > openspec/changes/archivable/proposal.md; git add -A; git commit -q -m "change"; git push -q origin main
sur_branche feat/archivable; valide tools/outil.sh v6 "code"; git mv openspec/changes/archivable openspec/changes/archive/2026-10-10-archivable; git commit -q -m archive; git checkout -q main
verif feat/archivable
code_et "vérification : change archivé sur le sommet de la branche nommée, passe" 0 "peut être terminée"
nouveau; mkdir -p openspec/changes/spec-seule; echo p > openspec/changes/spec-seule/proposal.md; git add -A; git commit -q -m "change"; git push -q origin main
sur_branche feat/spec-seule; valide openspec/changes/spec-seule/design.md d "spécification"; git checkout -q main
verif feat/spec-seule
code_et "vérification : branche de spécification, passe" 0 "branche de spécification"

# code 6 : jeu d'essai validant, contre le sommet de la branche nommée
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; tete=$(git rev-parse HEAD); git checkout -q main
verif feat/poste
code_et "vérification code 6 : posture changée, aucun enregistrement" 6 "finish_branch : jeu d'essai validant absent"
enregistre 2026-10-02-100000 "$(git rev-parse main)" true true false fr
verif feat/poste
code_et "vérification code 6 : enregistrement dont le contenu des chemins diffère du sommet" 6 "finish_branch : jeu d'essai validant absent"
enregistre 2026-10-02-100000 "$tete" true true false fr
verif feat/poste
code_et "vérification : passage validant sur le sommet de la branche nommée, passe" 0 "2026-10-02-100000 (1/2)"
[ "$(git rev-parse --abbrev-ref HEAD)" = main ]; verifie "vérification code 6 : la branche courante n'a pas bougé" $?

# mode vérification : même règle, depuis main, pour la branche nommée
nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; emp=$(empreinte_de HEAD); git checkout -q main
enregistre_e 2026-10-02-100000 1111111111111111111111111111111111111111 "$emp" true true false fr
verif feat/poste
code_et "vérification : empreinte du sommet de la branche nommée, état testé disparu : passe" 0 "(empreinte des fichiers évalués)"

nouveau; sur_branche feat/poste; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; git checkout -q main
git rm -q tests/postures/fichiers-evalues.txt; git commit -q -m "liste retirée"
verif feat/poste
code_et "vérification, liste absente : refus 6 avec la phrase" 6 "liste des fichiers évalués absente ou vide"

# code 7 : divergence, fetch impossible ; main local en retard accepté et laissé où il est
nouveau; sur_branche feat/diverge; valide tools/outil.sh v7 "code"; git checkout -q main
git clone -q "$distant" "$cas/autre"; (cd "$cas/autre" && echo d > distant.txt && git add -A && git commit -q -m "distant" && git push -q origin main)
echo l > local.txt; git add -A; git commit -q -m "local"; avant=$(etat_main)
verif feat/diverge
code_et "vérification code 7 : main local a divergé du distant" 7 "finish_branch : main n'est pas à jour"
[ "$(etat_main)" = "$avant" ]; verifie "vérification code 7 : main inchangé" $?
nouveau; sur_branche feat/hors-ligne; valide tools/outil.sh v8 "code"; git checkout -q main; git remote set-url origin "$cas/inexistant.git"
verif feat/hors-ligne
code_et "vérification code 7 : fetch impossible" 7 "finish_branch : main n'est pas à jour"
nouveau; sur_branche feat/retard; valide tools/outil.sh v9 "code"; git checkout -q main
git clone -q "$distant" "$cas/autre"; (cd "$cas/autre" && echo d > distant.txt && git add -A && git commit -q -m "distant" && git push -q origin main)
avant=$(etat_main); avant_distant=$(git --git-dir="$distant" rev-parse main)
verif feat/retard
code_et "vérification : main local en retard, la branche ne contient pas main distant : code 8" 8 "finish_branch : la branche ne contient pas main"
[ "$(etat_main)" = "$avant" ] && [ "$(git --git-dir="$distant" rev-parse main)" = "$avant_distant" ]; verifie "vérification : main local en retard n'est pas avancé" $?
git checkout -q feat/retard; git fetch -q origin main; git merge -q --no-edit FETCH_HEAD; git checkout -q main
verif feat/retard
code_et "vérification : main local en retard, la branche contient main distant : passe" 0 "peut être terminée"
[ "$(etat_main)" = "$avant" ]; verifie "vérification : main local reste en retard après la réussite" $?

# code 8 : la branche ne contient pas main
nouveau; sur_branche feat/derriere; valide tools/outil.sh v10 "code"
git checkout -q main; valide main.txt m "sur main"; git push -q origin main
verif feat/derriere
code_et "vérification code 8 : la branche ne contient pas main" 8 "finish_branch : la branche ne contient pas main"

# code 12 : main ouvert dans un autre dossier ; depuis le worktree de la branche, la même règle que la fin de branche
nouveau; sur_branche feat/wt; valide tools/outil.sh v11 "code"; git checkout -q main
git worktree add -q "$cas/wt" feat/wt; avant=$(etat_main)
cd "$cas/wt" || exit 1
verif feat/wt
code_et "vérification code 12 : main ouvert dans un autre dossier" 12 "finish_branch : main est ouvert dans un autre dossier"
contient "git switch --detach"; verifie "vérification code 12 : la manoeuvre est donnée" $?
[ "$(etat_main)" = "$avant" ] && [ "$(git rev-parse --abbrev-ref HEAD)" = feat/wt ] && [ ! -e "$cas/runner-appele" ]; verifie "vérification code 12 : rien n'est changé, aucun runner" $?
cd "$travail" || exit 1
git worktree remove --force "$cas/wt"

# l'ordre des refus : le premier refus de la liste arrête le mode, comme la fin de branche
nouveau; mkdir -p openspec/changes/ordre; echo p > openspec/changes/ordre/proposal.md; git add -A; git commit -q -m "change"; git push -q origin main
sur_branche feat/ordre; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; git checkout -q main
verif feat/ordre
code_et "vérification : change non archivé (5) avant jeu d'essai absent (6)" 5 "change OpenSpec non archivé"

# l'aide décrit le mode
nouveau; sur_branche feat/aide3; lance --help
contient "--check <branche>"; verifie "aide : le mode --check est décrit" $?
contient "main local n'est jamais déplacé"; verifie "aide : main local n'est jamais déplacé en mode vérification" $?

# --- test-speed-2, D6 : code 14, passage vert de tools/dbtest.sh enregistré pour l'arbre du sommet quand le code de la base a changé
# L'empreinte est une ligne « arbre » dans pmzilla-dbtest-ok, dossier Git commun du dépôt où le script tourne (workspace en mode vérification).
empreinte_fichier() { printf '%s/pmzilla-dbtest-ok' "$(git rev-parse --path-format=absolute --git-common-dir)"; }
empreinte_ecrire() { printf '%s\n' "$1" >> "$(empreinte_fichier)"; }
L14_REFUS="finish_branch : passage dbtest vert absent"
L14_D1="Le code de la base a changé sur la branche sans passage vert de tools/dbtest.sh pour l'arbre du sommet."
L14_D2="Lance bash tools/dbtest.sh dans le worktree de la branche, arbre propre, après le dernier commit, puis relance."
L14_TROUVE="finish_branch : passage dbtest vert trouvé pour l'arbre du sommet"

# fin de branche : sans empreinte, refus 14 avant le runner, rien n'est changé
nouveau; sur_branche feat/base; valide db/migrations/9999_test.sql "SELECT 1;" "migration"; avant=$(etat_main)
FINISH_BRANCH_RUNNER="touch $cas/runner-appele" lance
code_et "code 14 : migration changée, aucune empreinte" 14 "$L14_REFUS"
contient "$L14_D1" && contient "$L14_D2"; verifie "code 14 : les deux lignes de détail" $?
[ "$(etat_main)" = "$avant" ] && [ ! -e "$cas/runner-appele" ] && [ "$(git rev-parse --abbrev-ref HEAD)" = feat/base ]; verifie "code 14 : main inchangé, runner non lancé, branche courante inchangée" $?
# empreinte d'un autre arbre : refusée
empreinte_ecrire "1111111111111111111111111111111111111111"
lance
code_et "code 14 : empreinte d'un autre arbre refusée" 14 "$L14_REFUS"
# empreinte de l'arbre du sommet : la ligne trouvée est affichée et la fin de branche va jusqu'au bout
empreinte_ecrire "$(git rev-parse 'HEAD^{tree}')"
lance
code_et "empreinte de l'arbre du sommet : acceptée, la ligne trouvée est affichée, fin de branche réussie" 0 "$L14_TROUVE"
# l'empreinte est exacte : un commit de plus (même sur un chemin sans rapport) la rend caduque
nouveau; sur_branche feat/base2; valide db/migrations/9999_test.sql "SELECT 1;" "migration"; empreinte_ecrire "$(git rev-parse 'HEAD^{tree}')"
valide tools/outil.sh ulterieur "autre fichier"
lance
code_et "code 14 : un commit ultérieur après l'empreinte, arbre différent, refus" 14 "$L14_REFUS"

# chaque famille de chemins de la liste exige l'empreinte ; un chemin hors liste ne l'exige pas
for chemin in docker-compose.yml tools/db.py tools/dbtest.sh tools/flow_views.py tools/hybrid_search.py tests/db/test_x.py tests/flow_store/aide_base.py tests/library_backend/pg_demo.py tests/fixtures_library/demo.py tools/posture_evals.py tools/cases_calibration.py tools/morning_summary.py tools/offsite_backup.sh tools/com.pmzilla.db-backup.plist tools/install_lab_database.py tools/install_lab_check.py tools/install_lab_context.py; do
  nouveau; sur_branche feat/chemin; valide "$chemin" "x" "chemin base"
  lance
  code_et "code 14 : le chemin $chemin exige l'empreinte" 14 "$L14_REFUS"
done
for chemin in tools/outil.sh tests/postures/autre.py docs/guide.md; do
  nouveau; sur_branche feat/hors; valide "$chemin" "x" "hors base"
  lance
  code_et "aucune empreinte exigée pour $chemin (hors liste)" 0 "finish_branch : terminé"
  ! contient "dbtest"; verifie "hors liste $chemin : aucune ligne dbtest" $?
done

# mode vérification : mêmes refus, mêmes phrases, depuis le workspace, avec l'empreinte du sommet de la branche nommée
nouveau; sur_branche feat/verif14; valide db/migrations/9999_test.sql "SELECT 1;" "migration"; git checkout -q main; avant=$(etat_complet)
verif feat/verif14
code_et "vérification code 14 : migration changée, aucune empreinte" 14 "$L14_REFUS"
contient "$L14_D1" && contient "$L14_D2"; verifie "vérification code 14 : les deux lignes de détail" $?
[ "$avant" = "$(etat_complet)" ] && [ ! -e "$cas/runner-appele" ]; verifie "vérification code 14 : rien n'est changé, aucun runner" $?
empreinte_ecrire "$(git rev-parse 'feat/verif14^{tree}')"
verif feat/verif14
code_et "vérification : empreinte du sommet de la branche nommée, passe avec la ligne trouvée" 0 "$L14_TROUVE"

# l'ordre : 6 avant 14, 14 avant 7 (fetch en échec), 7 reste atteignable avec l'empreinte
nouveau; sur_branche feat/ordre6; valide db/migrations/9999_test.sql "SELECT 1;" "migration"; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"; git checkout -q main
verif feat/ordre6
code_et "vérification : jeu d'essai absent (6) avant empreinte absente (14)" 6 "finish_branch : jeu d'essai validant absent"
nouveau; sur_branche feat/ordre6b; valide db/migrations/9999_test.sql "SELECT 1;" "migration"; valide .claude/skills/pmzilla-x/SKILL.md modif "posture"
lance
code_et "fin de branche : jeu d'essai absent (6) avant empreinte absente (14)" 6 "finish_branch : jeu d'essai validant absent"
nouveau; sur_branche feat/ordre7; valide db/migrations/9999_test.sql "SELECT 1;" "migration"; git checkout -q main; git remote set-url origin "$cas/inexistant.git"
verif feat/ordre7
code_et "vérification : empreinte absente (14) avant main pas à jour (7, fetch en échec)" 14 "$L14_REFUS"
empreinte_ecrire "$(git rev-parse 'feat/ordre7^{tree}')"
verif feat/ordre7
code_et "vérification : avec l'empreinte, le fetch en échec est refusé ensuite (7)" 7 "finish_branch : main n'est pas à jour"

# l'aide : la ligne 14 entre 6 et 7, dans le texte exact, et le mode vérification la cite
nouveau; sur_branche feat/aide14; lance --help
contient "  14 un passage vert de tools/dbtest.sh est enregistré pour l'arbre du sommet si le code de la base a changé"; verifie "aide : la ligne du code 14" $?
n6=$(printf '%s\n' "$SORTIE" | grep -n "^  6  " | head -1 | cut -d: -f1); n14=$(printf '%s\n' "$SORTIE" | grep -n "^  14 " | head -1 | cut -d: -f1); n7=$(printf '%s\n' "$SORTIE" | grep -n "^  7  " | head -1 | cut -d: -f1)
[ -n "$n6" ] && [ -n "$n14" ] && [ -n "$n7" ] && [ "$n6" -lt "$n14" ] && [ "$n14" -lt "$n7" ]; verifie "aide : la ligne 14 est entre les lignes 6 et 7" $?
contient "refus 3, 4, 19, 5, 6, 14, 7, 8 et 12"; verifie "aide : le mode vérification cite 14 dans l'ordre" $?

# --- test-speed, groupe 2 : pas de second runner pour un arbre déjà testé dans le worktree (D5 à D11, D16, D17)
# Une fiche de fin valide (écrite ici à la main, comme le fait tools/finish_worktree.sh), le jeton dans FINISH_BRANCH_TESTED_TOKEN.
# Un faux « git » ne remplace que « merge-tree » (FAUX_MERGE_TREE), un faux « uv » donne une version d'outil à la signature.
real_git=$(command -v git)
mkdir -p "$tmp/fgit" "$tmp/fx1" "$tmp/fx2"
printf '#!/bin/sh\nif [ "$1" = merge ] && [ -n "${FAUX_AMEND:-}" ]; then\n  %s "$@"; rc=$?; echo extra > extra.txt; %s add extra.txt; %s commit -q --amend --no-edit; exit $rc\nfi\nif [ "$1" = merge-tree ] && [ -n "${FAUX_MERGE_TREE:-}" ]; then\n  [ "$FAUX_MERGE_TREE" = echec ] && exit 1\n  echo "$FAUX_MERGE_TREE"; exit 0\nfi\nexec %s "$@"\n' "$real_git" "$real_git" "$real_git" "$real_git" > "$tmp/fgit/git"; chmod +x "$tmp/fgit/git"
for v in 1 2; do printf '#!/bin/sh\necho "uv %s.0"\n' "$v" > "$tmp/fx$v/uv"; chmod +x "$tmp/fx$v/uv"; done
PATH="$tmp/fgit:$tmp/fx1:$PATH"; export PATH
JETON=jeton-test
fiche_commun() { git rev-parse --path-format=absolute --git-common-dir; }
fiche_ecrire() { # [champ=valeur | absente | vide]... : fiche valide pour le sommet de la branche courante, altérée par les arguments
  f_format=1; f_branche=$(git rev-parse --abbrev-ref HEAD); f_sommet=$(git rev-parse HEAD); f_arbre=$(git rev-parse 'HEAD^{tree}')
  f_env=$(. "$travail/tools/finish_env.sh" && finish_env_signature); f_jeton=$JETON; f_passage=""; f_image=""
  for a in "$@"; do
    case "$a" in
      absente) return 0 ;;
      vide) : > "$(fiche_commun)/pmzilla-finish-tested"; return 0 ;;
      format=*) f_format=${a#*=} ;; branche=*) f_branche=${a#*=} ;; sommet=*) f_sommet=${a#*=} ;; arbre=*) f_arbre=${a#*=} ;;
      env=*) f_env=${a#*=} ;; jeton=*) f_jeton=${a#*=} ;; passage=*) f_passage=${a#*=} ;; image=*) f_image=${a#*=} ;;
    esac
  done
  printf 'format=%s\nbranch=%s\ntip=%s\ntree=%s\nenv=%s\ntoken=%s\ndate=2026-10-16T12:00:00\n' "$f_format" "$f_branche" "$f_sommet" "$f_arbre" "$f_env" "$f_jeton" > "$(fiche_commun)/pmzilla-finish-tested"
  [ -z "${f_passage:-}" ] || printf 'passage=%s\nimage=%s\n' "$f_passage" "${f_image:-}" >> "$(fiche_commun)/pmzilla-finish-tested"   # mode CI (local-ci-container 7.2) : champs ajoutés par tools/finish_worktree.sh
}
PERMET=1   # valeur de FINISH_WORKTREE_ALLOW_SKIP passée par lancej (PERMET non définie : la variable n'est pas posée ; définie, même vide : posée) ; le saut est permis par défaut (skip-default-on)
lancej() { # arguments du script : lancement par le script de fin de worktree (jeton posé) ; PATH_RUN remplace le PATH du lancement
  SORTIE=$(env PATH="${PATH_RUN:-$PATH}" FINISH_BRANCH_TESTED_TOKEN="$JETON" ${PERMET+FINISH_WORKTREE_ALLOW_SKIP="$PERMET"} "$BASH_FIN" "$travail/tools/finish_branch.sh" "$@" 2>&1); CODE=$?
}
compte_runner() { FINISH_BRANCH_RUNNER="echo x >> $cas/appels"; export FINISH_BRANCH_RUNNER; }
n_appels() { if [ -e "$cas/appels" ]; then wc -l < "$cas/appels" | tr -d ' '; else echo 0; fi; }
champ() { # fichier numéro-de-ligne numéro-de-champ
  sed -n "$2p" "$1" | awk -F'\t' -v c="$3" '{print $c}'
}
cas_raison() { # description raison [argument de fiche_ecrire]... : le runner tourne, avec la raison attendue avant la ligne de lancement
  desc=$1; raison=$2; shift 2
  nouveau; sur_branche feat/r; valide tools/outil.sh r "code"; compte_runner; fiche_ecrire "$@"
  lancej
  code_et "$desc : code 0 et raison « $raison »" 0 "finish_branch : second lancement nécessaire : $raison"
  [ "$(n_appels)" -eq 1 ]; verifie "$desc : le runner est lancé une fois" $?
  [ ! -e "$(fiche_commun)/pmzilla-finish-tested" ]; verifie "$desc : la fiche n'existe plus" $?
  ! contient "second lancement sauté"; verifie "$desc : aucune ligne de saut" $?
  printf '%s' "$SORTIE" | awk '/second lancement nécessaire/ {a=NR} /lancement du runner complet sur/ {b=NR} END {exit !(a && b && a < b)}'; verifie "$desc : la raison précède la ligne de lancement du runner" $?
  ! contient "$JETON" && ! contient "—"; verifie "$desc : ni jeton ni tiret cadratin dans la sortie" $?
}
cas_raison "aucune fiche" "fiche de fin absente" absente
cas_raison "fiche vide" "fiche de fin illisible" vide
cas_raison "version de format inconnue" "fiche de fin illisible" format=9
cas_raison "autre jeton" "jeton différent" jeton=autre-jeton
cas_raison "autre branche" "autre branche" branche=feat/autre
cas_raison "autre sommet" "autre sommet" sommet=1111111111111111111111111111111111111111
cas_raison "arbre du sommet différent" "arbre du sommet différent" arbre=4b825dc642cb6eb9a060e54bf8d69288fbee4904
FAUX_MERGE_TREE=4b825dc642cb6eb9a060e54bf8d69288fbee4904 cas_raison "arbre fusionné différent" "arbre fusionné différent"
FAUX_MERGE_TREE=echec cas_raison "arbre fusionné non calculable" "arbre fusionné non calculable"
unset FAUX_MERGE_TREE
nouveau; sur_branche feat/env; valide tools/outil.sh e "code"; compte_runner; fiche_ecrire
PATH_RUN="$tmp/fx2:$PATH" lancej; unset PATH_RUN
code_et "environnement différent : la version d'un outil a changé" 0 "second lancement nécessaire : environnement différent"
[ "$(n_appels)" -eq 1 ]; verifie "environnement différent : le runner est lancé" $?
cas_raison "fiche pour la branche mais jeton vide dans la fiche" "jeton différent" jeton=
# Les raisons suivent l'ordre de la spécification : un jeton faux passe avant une branche fausse
cas_raison "jeton et branche faux : le jeton d'abord" "jeton différent" jeton=autre-jeton branche=feat/autre

# Correspondance complète : le second runner est sauté, l'empreinte complète est écrite pour l'arbre testé, le hook pre-push ne lance rien
nouveau; sur_branche feat/saut; valide tools/outil.sh s "code"; compte_runner; fiche_ecrire
ln -sf "$outils/hooks/pre-push" .git/hooks/pre-push; export PRE_PUSH_RUNNER="touch $cas/hook-appele"; export RUN_ALL_DURATIONS="$cas/durees.tsv"
lancej
unset PRE_PUSH_RUNNER RUN_ALL_DURATIONS
code_et "saut : la fin réussit" 0 "finish_branch : terminé"
contient "finish_branch : runner complet déjà vert dans le worktree pour l'arbre fusionné : second lancement sauté"; verifie "saut : la ligne de saut" $?
[ "$(n_appels)" -eq 0 ]; verifie "saut : le faux runner n'est pas appelé" $?
contient "runner complet sauté (arbre déjà testé dans le worktree)"; verifie "saut : la liste finale le dit" $?
! contient "lancement du runner complet sur" && ! contient "second lancement nécessaire"; verifie "saut : ni ligne de lancement ni raison" $?
[ ! -e "$(fiche_commun)/pmzilla-finish-tested" ]; verifie "saut : la fiche est consommée" $?
[ "$(git rev-list --parents -n1 main | wc -w)" -eq 3 ] && [ "$(git rev-parse main)" = "$(git --git-dir="$distant" rev-parse main)" ]; verifie "saut : main fusionné et poussé" $?
[ "$(cat "$(git rev-parse --git-path pmzilla-run-all-ok)")" = "$(git rev-parse 'main^{tree}')" ]; verifie "saut : l'empreinte complète égale l'arbre de la fusion" $?
[ ! -e "$cas/hook-appele" ]; verifie "saut : le hook pre-push n'a lancé aucun runner" $?
[ ! -e "$(git rev-parse --git-path pmzilla-run-targeted-ok)" ]; verifie "saut : aucune empreinte ciblée" $?
! contient "$JETON" && ! contient "—" && ! contient "$cas"; verifie "saut : ni jeton, ni tiret cadratin, ni chemin dans la sortie" $?
# la ligne du fichier des durées (D17)
[ "$(sed -n 1p "$cas/durees.tsv" | awk -F'\t' '{print NF}')" -eq 10 ] && [ "$(wc -l < "$cas/durees.tsv" | tr -d ' ')" -eq 2 ]; rc=$?; SORTIE="$(cat "$cas/durees.tsv" 2>&1)"; verifie "durées : en-tête de dix champs et une ligne" $rc
[ "$(champ "$cas/durees.tsv" 2 3)" = fin-saut ] && [ "$(champ "$cas/durees.tsv" 2 4)" = espace ] && [ -z "$(champ "$cas/durees.tsv" 2 5)" ] && [ -z "$(champ "$cas/durees.tsv" 2 6)" ] && [ -z "$(champ "$cas/durees.tsv" 2 7)" ] && [ -z "$(champ "$cas/durees.tsv" 2 8)" ]; rc=$?; SORTIE="$(cat "$cas/durees.tsv" 2>&1)"; verifie "durées : saut : genre fin-saut, copie espace, suite, type et secondes vides" $rc
[ "$(champ "$cas/durees.tsv" 2 9)" = "sauté" ] && [ "$(champ "$cas/durees.tsv" 2 10)" = "arbre déjà testé dans le worktree" ]; verifie "durées : saut : verdict et raison" $?
champ "$cas/durees.tsv" 2 1 | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$'; verifie "durées : saut : date ISO locale" $?
[ -s "$cas/durees.tsv" ] && ! grep -qF -e feat/saut -e "$JETON" -e "$cas" -e "$(git rev-parse main)" -e "$(git rev-parse 'main^{tree}')" "$cas/durees.tsv"; rc=$?; SORTIE="$(cat "$cas/durees.tsv" 2>&1)"; verifie "durées : ni branche, ni commit, ni arbre, ni jeton, ni chemin" $rc

# mode CI (local-ci-container 7.2, D8 étape 5) : une fiche avec passage=ci et une ligne « vert » pour l'arbre du sommet (FINISH_BRANCH_CI_VERDICTS) saute le
# second runner avec la ligne du mode CI et écrit l'empreinte complète ; sans ligne « vert » pour cet arbre, le runner tourne avec la raison ; jamais de conteneur.
printf '#!/bin/sh\necho "docker $*" >> "${DOCKER_LOG:-/dev/null}"\nexit 1\n' > "$tmp/fgit/docker"; chmod +x "$tmp/fgit/docker"
CLE_CI="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
cas_ci() { # description verdict-du-sommet (vert|rouge|aucun|autre|illisible) : fiche passage=ci, fichier des verdicts selon le mode ; attend le saut ou la raison
  nouveau; sur_branche feat/ci; valide tools/outil.sh c "code"; compte_runner; fiche_ecrire passage=ci image="$CLE_CI"
  VERDICTS_CI="$cas/verdicts"; ARBRE_TETE=$(git rev-parse 'HEAD^{tree}'); export DOCKER_LOG="$cas/docker-appele"
  printf '4b825dc642cb6eb9a060e54bf8d69288fbee4904\tvert\t%s\n' "$CLE_CI" > "$VERDICTS_CI"
  case "$2" in
    vert|rouge) printf '%s\t%s\t%s\n' "$ARBRE_TETE" "$2" "$CLE_CI" >> "$VERDICTS_CI" ;;
    illisible) chmod 000 "$VERDICTS_CI" ;;
    absent) rm -f "$VERDICTS_CI" ;;
  esac
  export FINISH_BRANCH_CI_VERDICTS="$VERDICTS_CI"
  RUN_ALL_DURATIONS="$cas/durees.tsv" lancej
  chmod 600 "$VERDICTS_CI" 2>/dev/null; unset FINISH_BRANCH_CI_VERDICTS
  [ ! -e "$DOCKER_LOG" ]; verifie "$1 : aucun conteneur lancé" $?
  ! contient "$JETON" && ! contient "$cas"; verifie "$1 : ni jeton ni chemin dans la sortie" $?
}
cas_ci "mode CI, verdict vert pour l'arbre du sommet" vert
code_et "mode CI vert : la fin réussit avec la ligne de saut" 0 "finish_branch : saut du second runner : verdict du conteneur et passe Mac (arbre $(git rev-parse 'HEAD^{tree}' | cut -c1-12))"
[ "$(n_appels)" -eq 0 ]; verifie "mode CI vert : le faux runner n'est pas appelé" $?
! contient "second lancement nécessaire" && ! contient "lancement du runner complet sur"; verifie "mode CI vert : ni raison ni ligne de lancement" $?
[ "$(cat "$(git rev-parse --git-path pmzilla-run-all-ok)")" = "$(git rev-parse 'main^{tree}')" ]; verifie "mode CI vert : l'empreinte complète égale l'arbre de la fusion" $?
[ ! -e "$(fiche_commun)/pmzilla-finish-tested" ]; verifie "mode CI vert : la fiche est consommée" $?
[ "$(champ "$cas/durees.tsv" 2 3)" = fin-saut ] && [ "$(champ "$cas/durees.tsv" 2 9)" = "sauté" ]; rc=$?; SORTIE="$(cat "$cas/durees.tsv" 2>&1)"; verifie "mode CI vert : la ligne de durées est un saut" $rc
for def in "rouge|ligne rouge" "autre|aucune ligne pour l'arbre du sommet (autre arbre seulement)" "illisible|fichier illisible" "absent|fichier absent"; do
  IFS='|' read -r mode lib <<EOF2
$def
EOF2
  cas_ci "mode CI, $lib" "$mode"
  code_et "mode CI ($lib) : la fin réussit, second runner lancé avec la raison" 0 "finish_branch : second lancement nécessaire : verdict du conteneur absent ou non vert pour l'arbre du sommet"
  [ "$(n_appels)" -eq 1 ]; verifie "mode CI ($lib) : le runner est lancé une fois" $?
  ! contient "saut du second runner"; verifie "mode CI ($lib) : aucune ligne de saut" $?
  printf '%s' "$SORTIE" | awk '/second lancement nécessaire/ {a=NR} /lancement du runner complet sur/ {b=NR} END {exit !(a && b && a < b)}'; verifie "mode CI ($lib) : la raison précède la ligne de lancement" $?
done
# jamais un refus sur ce motif : le fichier des verdicts absent ne bloque pas la fin
# fiche sans le champ passage : comme aujourd'hui, le fichier des verdicts n'est jamais lu (même illisible), saut avec l'ancienne ligne
nouveau; sur_branche feat/sanspassage; valide tools/outil.sh sp "code"; compte_runner; fiche_ecrire
printf '%s\t%s\t%s\n' "$(git rev-parse 'HEAD^{tree}')" rouge "$CLE_CI" > "$cas/verdicts"; chmod 000 "$cas/verdicts"; export FINISH_BRANCH_CI_VERDICTS="$cas/verdicts"
lancej; chmod 600 "$cas/verdicts"; unset FINISH_BRANCH_CI_VERDICTS
code_et "fiche sans passage : saut comme aujourd'hui" 0 "finish_branch : runner complet déjà vert dans le worktree pour l'arbre fusionné : second lancement sauté"
! contient "verdict du conteneur"; verifie "fiche sans passage : aucune mention du verdict du conteneur" $?
[ "$(n_appels)" -eq 0 ]; verifie "fiche sans passage : le runner n'est pas appelé" $?
# un autre passage que « ci » : jamais de lecture du verdict, le chemin d'aujourd'hui
nouveau; sur_branche feat/autrepassage; valide tools/outil.sh ap "code"; compte_runner; fiche_ecrire passage=mac
export FINISH_BRANCH_CI_VERDICTS="$cas/inexistant"; lancej; unset FINISH_BRANCH_CI_VERDICTS
code_et "passage autre que ci : saut comme aujourd'hui" 0 "second lancement sauté"
! contient "verdict du conteneur"; verifie "passage autre que ci : aucune mention du verdict du conteneur" $?
# les raisons de la fiche restent prioritaires : un jeton faux avec passage=ci et verdict vert lance le runner avec la raison du jeton
nouveau; sur_branche feat/ci-jeton; valide tools/outil.sh cj "code"; compte_runner; fiche_ecrire passage=ci image="$CLE_CI" jeton=autre-jeton
printf '%s\t%s\t%s\n' "$(git rev-parse 'HEAD^{tree}')" vert "$CLE_CI" > "$cas/verdicts"; export FINISH_BRANCH_CI_VERDICTS="$cas/verdicts"; lancej; unset FINISH_BRANCH_CI_VERDICTS
code_et "mode CI : jeton différent d'abord" 0 "second lancement nécessaire : jeton différent"
# le script ne lance jamais de conteneur
! grep -v '^[[:space:]]*#' "$script" | grep -qiE '(^|[;&|({[:space:]])docker[[:space:]]+(run|build|exec|ps|info)|colima|ci_local\.sh'; rc=$?; SORTIE="docker"; verifie "mode CI : aucune commande docker, colima ni ci_local.sh dans finish_branch.sh" $rc
grep -q '^#   FINISH_BRANCH_CI_VERDICTS ' "$script"; rc=$?; SORTIE="en-tête"; verifie "mode CI : l'en-tête nomme FINISH_BRANCH_CI_VERDICTS" $rc

# le saut sans variable de durées, avec le faux runner : aucun fichier dans le dossier de données
nouveau; sur_branche feat/sans-durees; valide tools/outil.sh d0 "code"; compte_runner; fiche_ecrire; unset RUN_ALL_DURATIONS
lancej
code_et "durées : le runner est factice et la variable absente, la fin réussit" 0 "second lancement sauté"
[ ! -e "$PMZILLA_LAB_DATA/mesures" ]; verifie "durées : aucun fichier écrit dans le dossier de données par un test" $?

# seconde exécution notée, avec sa raison, sa durée et le verdict du runner
nouveau; sur_branche feat/relance; valide tools/outil.sh d1 "code"; compte_runner; fiche_ecrire sommet=1111111111111111111111111111111111111111
export RUN_ALL_DURATIONS="$cas/durees.tsv"; lancej; unset RUN_ALL_DURATIONS
code_et "durées : second lancement vert" 0 "second lancement nécessaire : autre sommet"
[ "$(champ "$cas/durees.tsv" 2 3)" = fin-relance ] && [ "$(champ "$cas/durees.tsv" 2 9)" = ok ] && [ "$(champ "$cas/durees.tsv" 2 10)" = "autre sommet" ]; rc=$?; SORTIE="$(cat "$cas/durees.tsv" 2>&1)"; verifie "durées : relance : genre, verdict ok, raison" $rc
champ "$cas/durees.tsv" 2 7 | grep -qE '^[0-9]+\.[0-9]+$'; rc=$?; SORTIE="$(cat "$cas/durees.tsv")"; verifie "durées : relance : une durée avec point décimal" $rc
[ -z "$(champ "$cas/durees.tsv" 2 5)" ] && [ -z "$(champ "$cas/durees.tsv" 2 6)" ] && [ -z "$(champ "$cas/durees.tsv" 2 8)" ]; verifie "durées : relance : suite, type et temps unittest vides" $?
nouveau; sur_branche feat/relance-rouge; valide tools/outil.sh d2 "code"; fiche_ecrire sommet=1111111111111111111111111111111111111111
export FINISH_BRANCH_RUNNER=false RUN_ALL_DURATIONS="$cas/durees.tsv"; avant=$(etat_main); lancej; unset RUN_ALL_DURATIONS
code_et "durées : second lancement rouge, même code et même phrase qu'avant" 1 "finish_branch : tests en échec, rien n'est fusionné"
[ "$(champ "$cas/durees.tsv" 2 3)" = fin-relance ] && [ "$(champ "$cas/durees.tsv" 2 9)" = "échec" ]; rc=$?; SORTIE="$(cat "$cas/durees.tsv" 2>&1)"; verifie "durées : relance rouge : verdict échec" $rc
[ "$(etat_main)" = "$avant" ]; verifie "durées : relance rouge : main inchangé" $?

# relance forcée : toute valeur non vide force le runner, la fiche est quand même lue et effacée, aucune empreinte écrite par le script
for valeur in 1 0 non; do
  nouveau; sur_branche feat/force; valide tools/outil.sh f "code"; compte_runner; fiche_ecrire
  export FINISH_BRANCH_FORCE_RUN="$valeur" RUN_ALL_DURATIONS="$cas/durees.tsv"; lancej; unset FINISH_BRANCH_FORCE_RUN RUN_ALL_DURATIONS
  code_et "relance forcée ($valeur) malgré une fiche valide" 0 "finish_branch : second lancement nécessaire : relance forcée"
  [ "$(n_appels)" -eq 1 ] && [ ! -e "$(fiche_commun)/pmzilla-finish-tested" ]; verifie "relance forcée ($valeur) : le runner tourne, la fiche est effacée" $?
  ! contient "second lancement sauté" && ! contient "runner complet sauté"; verifie "relance forcée ($valeur) : aucun saut" $?
  [ ! -e "$(git rev-parse --git-path pmzilla-run-all-ok)" ]; verifie "relance forcée ($valeur) : le script n'écrit aucune empreinte lui-même" $?
  [ "$(champ "$cas/durees.tsv" 2 3)" = fin-relance ] && [ "$(champ "$cas/durees.tsv" 2 10)" = "relance forcée" ]; rc=$?; SORTIE="$(cat "$cas/durees.tsv" 2>&1)"; verifie "relance forcée ($valeur) : la ligne des durées porte la raison" $rc
done
nouveau; sur_branche feat/force-vide; valide tools/outil.sh f2 "code"; compte_runner; fiche_ecrire
export FINISH_BRANCH_FORCE_RUN=""; lancej; unset FINISH_BRANCH_FORCE_RUN
code_et "relance forcée vide : le saut a lieu comme sans la variable" 0 "second lancement sauté"
[ "$(n_appels)" -eq 0 ]; verifie "relance forcée vide : le runner n'est pas appelé" $?
nouveau; sur_branche feat/force-sans-fiche; valide tools/outil.sh f3 "code"; compte_runner
export FINISH_BRANCH_FORCE_RUN=1; lancej; unset FINISH_BRANCH_FORCE_RUN
code_et "relance forcée sans fiche : la raison forcée passe d'abord" 0 "second lancement nécessaire : relance forcée"
# saut permis par défaut (skip-default-on, design D1) : avec le jeton et une fiche valide, le réglage FINISH_WORKTREE_ALLOW_SKIP absent, vide ou exactement « 1 »
# permet le saut ; toute autre valeur donne la raison « saut non autorisé (réglage désactivé) », le runner tourne, la fiche est lue puis effacée
# (PERMET : variable non définie = réglage absent de l'environnement du lancement ; définie, même vide = réglage posé)
for valeur in absent vide 1; do
  nouveau; sur_branche feat/autorise-defaut; valide tools/outil.sh pa "code"; compte_runner; fiche_ecrire
  case $valeur in absent) unset PERMET ;; vide) PERMET="" ;; *) PERMET=$valeur ;; esac
  export RUN_ALL_DURATIONS="$cas/durees.tsv"; lancej; unset RUN_ALL_DURATIONS; PERMET=1
  code_et "saut permis (réglage $valeur) : second lancement sauté" 0 "finish_branch : runner complet déjà vert dans le worktree pour l'arbre fusionné : second lancement sauté"
  [ "$(n_appels)" -eq 0 ] && [ ! -e "$(fiche_commun)/pmzilla-finish-tested" ]; verifie "saut permis (réglage $valeur) : le runner n'est pas appelé, la fiche est effacée" $?
  ! contient "saut non autorisé" && ! contient "réglage absent"; verifie "saut permis (réglage $valeur) : aucune raison de non-autorisation" $?
  [ "$(champ "$cas/durees.tsv" 2 3)" = fin-saut ] && [ "$(champ "$cas/durees.tsv" 2 10)" = "arbre déjà testé dans le worktree" ]; rc=$?; SORTIE="$(cat "$cas/durees.tsv" 2>&1)"; verifie "saut permis (réglage $valeur) : la ligne fin-saut est écrite" $rc
done
for valeur in 0 oui 11 " " " 1"; do
  nouveau; sur_branche feat/non-autorise; valide tools/outil.sh na "code"; compte_runner; fiche_ecrire
  PERMET=$valeur; export RUN_ALL_DURATIONS="$cas/durees.tsv"; lancej; unset RUN_ALL_DURATIONS; PERMET=1
  code_et "saut non autorisé (réglage « $valeur ») malgré une fiche valide : code 0 et raison" 0 "finish_branch : second lancement nécessaire : saut non autorisé (réglage désactivé)"
  [ "$(n_appels)" -eq 1 ] && [ ! -e "$(fiche_commun)/pmzilla-finish-tested" ]; verifie "saut non autorisé (réglage « $valeur ») : le runner tourne, la fiche est effacée" $?
  ! contient "second lancement sauté" && ! contient "runner complet sauté" && ! contient "réglage absent"; verifie "saut non autorisé (réglage « $valeur ») : aucun saut, jamais l'ancienne raison" $?
  printf '%s' "$SORTIE" | awk '/second lancement nécessaire/ {a=NR} /lancement du runner complet sur/ {b=NR} END {exit !(a && b && a < b)}'; verifie "saut non autorisé (réglage « $valeur ») : la raison précède la ligne de lancement du runner" $?
  [ ! -e "$(git rev-parse --git-path pmzilla-run-all-ok)" ]; verifie "saut non autorisé (réglage « $valeur ») : le script n'écrit aucune empreinte lui-même" $?
  [ "$(champ "$cas/durees.tsv" 2 3)" = fin-relance ] && [ "$(champ "$cas/durees.tsv" 2 9)" = ok ] && [ "$(champ "$cas/durees.tsv" 2 10)" = "saut non autorisé (réglage désactivé)" ]; rc=$?; SORTIE="$(cat "$cas/durees.tsv" 2>&1)"; verifie "saut non autorisé (réglage « $valeur ») : la ligne fin-relance porte la raison" $rc
done
# réglage désactivé sans fiche : la raison du réglage passe avant « fiche de fin absente » (priorité après la relance forcée seulement)
nouveau; sur_branche feat/non-autorise-sans-fiche; valide tools/outil.sh na3 "code"; compte_runner; fiche_ecrire absente
PERMET=0; lancej; PERMET=1
code_et "saut non autorisé sans fiche : la raison du réglage d'abord" 0 "second lancement nécessaire : saut non autorisé (réglage désactivé)"
# réglage absent sans fiche : la raison suivante de la chaîne, « fiche de fin absente »
nouveau; sur_branche feat/defaut-sans-fiche; valide tools/outil.sh na3b "code"; compte_runner; fiche_ecrire absente
unset PERMET; lancej; PERMET=1
code_et "réglage absent sans fiche : la raison est la fiche absente" 0 "second lancement nécessaire : fiche de fin absente"
# la relance forcée garde la priorité, réglage absent comme réglage désactivé
for valeur in absent 0; do
  nouveau; sur_branche feat/force-reglage; valide tools/outil.sh na4 "code"; compte_runner; fiche_ecrire
  case $valeur in absent) unset PERMET ;; *) PERMET=$valeur ;; esac
  export FINISH_BRANCH_FORCE_RUN=1 RUN_ALL_DURATIONS="$cas/durees.tsv"; lancej; unset FINISH_BRANCH_FORCE_RUN RUN_ALL_DURATIONS; PERMET=1
  code_et "relance forcée (réglage $valeur) : la raison forcée est prioritaire" 0 "second lancement nécessaire : relance forcée"
  ! contient "saut non autorisé" && ! contient "second lancement sauté"; verifie "relance forcée (réglage $valeur) : ni raison du réglage ni saut" $?
  [ "$(n_appels)" -eq 1 ] && [ ! -e "$(fiche_commun)/pmzilla-finish-tested" ]; verifie "relance forcée (réglage $valeur) : le runner tourne, la fiche est effacée (lue quand même)" $?
  [ "$(champ "$cas/durees.tsv" 2 3)" = fin-relance ] && [ "$(champ "$cas/durees.tsv" 2 10)" = "relance forcée" ]; rc=$?; SORTIE="$(cat "$cas/durees.tsv" 2>&1)"; verifie "relance forcée (réglage $valeur) : la ligne des durées porte « relance forcée »" $rc
done
# réglage à 1 : le saut a lieu comme avant (le cas « correspondance complète » plus haut le couvre aussi, celui-ci nomme le réglage)
nouveau; sur_branche feat/autorise; valide tools/outil.sh na5 "code"; compte_runner; fiche_ecrire
PERMET=1; lancej
code_et "saut autorisé (réglage 1) : second lancement sauté" 0 "second lancement sauté"
[ "$(n_appels)" -eq 0 ]; verifie "saut autorisé (réglage 1) : le runner n'est pas appelé" $?
! contient "saut non autorisé"; verifie "saut autorisé (réglage 1) : pas de raison de non-autorisation" $?
# test-speed-2, groupe 0 : le runner complet ne reçoit aucune des trois variables du saut (jeton, relance forcée, réglage), qu'il tourne après un jeton ou à la main
nouveau; sur_branche feat/env-runner; valide tools/outil.sh env1 "code"; fiche_ecrire absente
FINISH_BRANCH_RUNNER="printf 'jeton=%s force=%s saut=%s\n' \"\${FINISH_BRANCH_TESTED_TOKEN-absent}\" \"\${FINISH_BRANCH_FORCE_RUN-absent}\" \"\${FINISH_WORKTREE_ALLOW_SKIP-absent}\" > $cas/env-runner"; export FINISH_BRANCH_RUNNER
PERMET=1; export FINISH_BRANCH_FORCE_RUN=1; lancej; unset FINISH_BRANCH_FORCE_RUN
code_et "variables du saut posées (avec jeton) : le runner tourne" 0 "finish_branch : terminé"
[ "$(cat "$cas/env-runner" 2>/dev/null)" = "jeton=absent force=absent saut=absent" ]; rc=$?; SORTIE="$(cat "$cas/env-runner" 2>&1)"; verifie "avec jeton : le runner ne reçoit aucune des trois variables" $rc
nouveau; sur_branche feat/env-main; valide tools/outil.sh env2 "code"
FINISH_BRANCH_RUNNER="printf 'jeton=%s force=%s saut=%s\n' \"\${FINISH_BRANCH_TESTED_TOKEN-absent}\" \"\${FINISH_BRANCH_FORCE_RUN-absent}\" \"\${FINISH_WORKTREE_ALLOW_SKIP-absent}\" > $cas/env-runner"; export FINISH_BRANCH_RUNNER
SORTIE=$(FINISH_BRANCH_TESTED_TOKEN= FINISH_BRANCH_FORCE_RUN=1 FINISH_WORKTREE_ALLOW_SKIP=1 "$BASH_FIN" "$travail/tools/finish_branch.sh" 2>&1); CODE=$?
code_et "variables du saut posées (à la main) : le runner tourne" 0 "finish_branch : terminé"
[ "$(cat "$cas/env-runner" 2>/dev/null)" = "jeton=absent force=absent saut=absent" ]; rc=$?; SORTIE="$(cat "$cas/env-runner" 2>&1)"; verifie "à la main : le runner ne reçoit aucune des trois variables" $rc
# lancement à la main (sans jeton) : le réglage n'y change rien (aucune ligne de raison, la fiche n'est pas lue)
nouveau; sur_branche feat/main-reglage; valide tools/outil.sh na6 "code"; compte_runner; fiche_ecrire
SORTIE=$(FINISH_WORKTREE_ALLOW_SKIP=1 "$BASH_FIN" "$travail/tools/finish_branch.sh" 2>&1); CODE=$?
code_et "à la main avec le réglage à 1 : le runner est lancé" 0 "finish_branch : terminé"
[ "$(n_appels)" -eq 1 ] && ! contient "second lancement" && ! contient "sauté"; verifie "à la main avec le réglage à 1 : ni saut ni ligne de raison" $?
# lancement à la main (sans jeton) : rien ne change, la fiche n'est ni lue ni effacée, avec ou sans la variable de relance
for valeur in "" 1; do
  nouveau; sur_branche feat/main-nue; valide tools/outil.sh m "code"; compte_runner; fiche_ecrire; cp "$(fiche_commun)/pmzilla-finish-tested" "$cas/fiche-avant"
  export RUN_ALL_DURATIONS="$cas/durees.tsv"; [ -z "$valeur" ] || export FINISH_BRANCH_FORCE_RUN="$valeur"; lance; unset RUN_ALL_DURATIONS FINISH_BRANCH_FORCE_RUN
  code_et "à la main (variable « $valeur ») : la fin réussit" 0 "finish_branch : terminé"
  [ "$(n_appels)" -eq 1 ]; verifie "à la main (variable « $valeur ») : le runner est lancé" $?
  cmp -s "$(fiche_commun)/pmzilla-finish-tested" "$cas/fiche-avant"; verifie "à la main (variable « $valeur ») : la fiche n'est ni lue ni effacée" $?
  ! contient "second lancement" && ! contient "sauté" && [ ! -e "$cas/durees.tsv" ]; verifie "à la main (variable « $valeur ») : aucune ligne de raison, aucune ligne de durées" $?
done
# mode vérification : la fiche n'est ni lue ni effacée, aucune ligne de durées
nouveau; sur_branche feat/verif-fiche; valide tools/outil.sh v "code"; fiche_ecrire; cp "$(fiche_commun)/pmzilla-finish-tested" "$cas/fiche-avant"; git checkout -q main
export RUN_ALL_DURATIONS="$cas/durees.tsv"; lancej --check feat/verif-fiche; unset RUN_ALL_DURATIONS
code_et "mode vérification avec jeton : réussit" 0 "peut être terminée"
cmp -s "$(fiche_commun)/pmzilla-finish-tested" "$cas/fiche-avant" && [ ! -e "$cas/durees.tsv" ]; verifie "mode vérification : la fiche est intacte, aucune ligne de durées" $?
# fichier des durées impossible à écrire : une ligne, rien d'autre ne change
nouveau; sur_branche feat/durees-ko; valide tools/outil.sh k "code"; compte_runner; fiche_ecrire; echo bloc > "$cas/bloc"
export RUN_ALL_DURATIONS="$cas/bloc/sous/durees.tsv"; lancej; unset RUN_ALL_DURATIONS
code_et "durées impossibles à écrire : la fin réussit quand même" 0 "finish_branch : bilan de fin non enregistré (écriture impossible)"
[ "$(n_appels)" -eq 0 ] && [ "$(git --git-dir="$distant" rev-parse main)" = "$(etat_main)" ]; verifie "durées impossibles : saut effectué, main poussé" $?
! contient "$cas/bloc"; verifie "durées impossibles : aucun chemin dans la ligne" $?
# rempart : l'arbre de la fusion diffère de l'arbre testé (un faux git ajoute un fichier au commit de fusion) ; le hook pre-push prend le relais
nouveau; sur_branche feat/rempart; valide tools/outil.sh b "code"; compte_runner; fiche_ecrire
ln -sf "$outils/hooks/pre-push" .git/hooks/pre-push; export PRE_PUSH_RUNNER="touch $cas/hook-appele"
FAUX_AMEND=1 lancej; unset PRE_PUSH_RUNNER
code_et "rempart : la fin réussit, code inchangé" 0 "finish_branch : arbre de la fusion différent de l'arbre testé : empreinte effacée, le hook pre-push relancera le runner complet"
[ "$(n_appels)" -eq 0 ] && [ -e "$cas/hook-appele" ]; verifie "rempart : le runner de la fin n'a pas tourné, celui du hook oui" $?
[ "$(git --git-dir="$distant" rev-parse main)" = "$(etat_main)" ]; verifie "rempart : main poussé après le runner du hook" $?
! contient "—"; verifie "rempart : aucun tiret cadratin" $?
# rempart avec la variable de contournement exportée par l'utilisateur : le push de main ne doit pas la transmettre au hook (revue du 2026-10-16, constat 3)
nouveau; sur_branche feat/rempart-contournement; valide tools/outil.sh bc "code"; compte_runner; fiche_ecrire
ln -sf "$outils/hooks/pre-push" .git/hooks/pre-push; export PRE_PUSH_RUNNER="touch $cas/hook-appele"; export PMZILLA_SKIP_GREEN_CHECK=1
FAUX_AMEND=1 lancej; unset PRE_PUSH_RUNNER PMZILLA_SKIP_GREEN_CHECK
code_et "rempart avec PMZILLA_SKIP_GREEN_CHECK exportée : la fin réussit" 0 "empreinte effacée, le hook pre-push relancera le runner complet"
[ -e "$cas/hook-appele" ]; rc=$?; SORTIE="runner du hook non lancé"; verifie "rempart avec PMZILLA_SKIP_GREEN_CHECK exportée : le hook lance quand même son runner" $rc

# garde-fous du texte du script : la variable de relance n'est lue que pour forcer, les variables sont dans l'en-tête
grep -v '^[[:space:]]*#' "$script" | sed 's/ -u FINISH_BRANCH_FORCE_RUN / /' | grep -F FINISH_BRANCH_FORCE_RUN | grep -vF '[ -n "${FINISH_BRANCH_FORCE_RUN:-}" ]' | grep -q .
[ $? -ne 0 ]; rc=$?; SORTIE="usage de la variable autre que le test de non-vacuité"; verifie "FINISH_BRANCH_FORCE_RUN n'est lue que par le test « non vide » (elle ne peut que forcer)" $rc
grep -q '^#   FINISH_BRANCH_FORCE_RUN ' "$script" && grep -q '^#   FINISH_BRANCH_TESTED_TOKEN ' "$script"; rc=$?; SORTIE="en-tête"; verifie "les deux variables sont dans le bloc des variables de l'en-tête" $rc
grep '^#' "$script" | grep -q 'ne peut que forcer'; rc=$?; SORTIE="en-tête"; verifie "l'en-tête dit que la variable de relance ne peut que forcer" $rc
grep -q 'FINISH_BRANCH_FORCE_RUN' "$outils/../docs/pmzilla/installation.md"; rc=$?; SORTIE="guide"; verifie "le guide d'installation nomme FINISH_BRANCH_FORCE_RUN" $rc
grep -q '^#   FINISH_WORKTREE_ALLOW_SKIP ' "$script"; rc=$?; SORTIE="en-tête"; verifie "FINISH_WORKTREE_ALLOW_SKIP est dans le bloc des variables de l'en-tête" $rc
! grep -q 'réglage absent' "$script"; rc=$?; SORTIE="ancienne raison présente"; verifie "le script n'imprime plus « réglage absent » (skip-default-on)" $rc
grep '^#' "$script" | grep -q 'réglage désactivé' && grep '^#' "$script" | grep -qF '« 0 »'; rc=$?; SORTIE="en-tête"; verifie "l'en-tête dit que la valeur 0 désactive le saut" $rc
grep -c 'FINISH_WORKTREE_ALLOW_SKIP:-' "$script" | grep -qx 1; rc=$?; SORTIE="plusieurs tests du réglage"; verifie "un seul test du réglage dans le script (D1)" $rc
grep -v '^[[:space:]]*#' "$script" | grep -F FINISH_WORKTREE_ALLOW_SKIP | grep -qF '= "1" ]'; rc=$?; SORTIE="comparaison exacte absente"; verifie "le script désactive le saut pour toute valeur de FINISH_WORKTREE_ALLOW_SKIP autre que 1 exactement (absent ou vide valent 1)" $rc
grep -q 'FINISH_WORKTREE_ALLOW_SKIP' "$outils/../docs/pmzilla/installation.md"; rc=$?; SORTIE="guide"; verifie "le guide d'installation nomme FINISH_WORKTREE_ALLOW_SKIP" $rc
PATH="${PATH#"$tmp/fgit:$tmp/fx1:"}"; export PATH

# --- verrou de fin de branche (change multi-session-piloting, D5 et D6, tâche 5.1) : code 15, verrou pris et libéré, jeton hérité,
# verrou périmé repris, mode vérification qui n'y touche pas, aide. Le verrou est un dossier du dossier Git commun, fait ici à la main.
pose_verrou() { # pid jeton [âge en secondes] : verrou factice dans le dossier Git commun du cas
  gel="$travail/.git/pmzilla-fin-en-cours"; rm -rf "$gel"; mkdir -p "$gel"
  printf '%s\n' "$1" > "$gel/pid"; echo $(( $(date +%s) - ${3:-600} )) > "$gel/debut"; printf 'feat/autre\n' > "$gel/branche"; printf '%s\n' "$2" > "$gel/jeton"
}
etat_verrou() { (cd "$travail/.git/pmzilla-fin-en-cours" 2>/dev/null && cat pid debut branche jeton); }
hhmm() { date -r "$1" +%H:%M 2>/dev/null || date -d "@$1" +%H:%M; }
mort=$(sh -c 'echo $$')   # numéro d'un processus qui n'existe plus

nouveau; sur_branche feat/verrou1; valide tools/outil.sh v1 "code"; git push -q origin feat/verrou1
pose_verrou $$ jeton-de-test; avant=$(etat_main); verrou_avant=$(etat_verrou); debut=$(sed -n 1p "$travail/.git/pmzilla-fin-en-cours/debut")
FINISH_BRANCH_RUNNER="echo appele >> $cas/appels-runner" lance
code_et "code 15 : une autre fin est en cours" 15 "finish_branch : une autre fin de branche est en cours (feat/autre, depuis $(hhmm "$debut"))"
[ ! -e "$cas/appels-runner" ]; verifie "code 15 : le faux runner n'a pas été appelé" $?
[ "$(etat_main)" = "$avant" ] && [ "$(git rev-parse --abbrev-ref HEAD)" = feat/verrou1 ] && git rev-parse -q --verify refs/heads/feat/verrou1 >/dev/null; verifie "code 15 : branches inchangées" $?
[ "$(etat_verrou)" = "$verrou_avant" ]; verifie "code 15 : le verrou de l'autre est intact" $?
! contient "jeton-de-test"; verifie "code 15 : le jeton n'est jamais affiché" $?
rm -rf "$travail/.git/pmzilla-fin-en-cours"

# code 15 avant le code 3 : sur main, un verrou vivant donne 15
nouveau; pose_verrou $$ jeton-de-test; lance
code_et "code 15 avant le code 3 (sur main)" 15 "une autre fin de branche est en cours"
rm -rf "$travail/.git/pmzilla-fin-en-cours"

# verrou pris pour tout le run et libéré : le faux runner note l'existence du verrou et le jeton reçu
nouveau; sur_branche feat/verrou2; valide tools/outil.sh v2 "code"; git push -q origin feat/verrou2
gel="$travail/.git/pmzilla-fin-en-cours"
FINISH_BRANCH_RUNNER="test -d $gel && cat $gel/jeton > $cas/jeton-verrou && printf '%s' \"\$FINISH_LOCK_TOKEN\" > $cas/jeton-runner && cat $gel/branche > $cas/branche-verrou && cat $gel/pid > $cas/pid-verrou" lance
code_et "verrou : la fin réussit avec un faux runner qui regarde le verrou" 0 "finish_branch : terminé"
[ -s "$cas/jeton-verrou" ] && [ "$(tr -d '\n' < "$cas/jeton-verrou")" = "$(cat "$cas/jeton-runner")" ]; verifie "verrou : le verrou existait pendant le runner et le runner a reçu son jeton" $?
[ "$(tr -d '\n' < "$cas/branche-verrou")" = feat/verrou2 ] && [ -n "$(cat "$cas/pid-verrou")" ]; verifie "verrou : il porte la branche et le numéro du script" $?
[ ! -e "$gel" ]; verifie "verrou : aucun verrou après la fin" $?
! contient "$(cat "$cas/jeton-runner")"; verifie "verrou : le jeton n'est jamais affiché" $?

# libéré aussi quand le runner échoue
nouveau; sur_branche feat/verrou3; valide tools/outil.sh v3 "code"
FINISH_BRANCH_RUNNER=false lance
code_et "verrou : runner en échec, code 1" 1 "tests en échec"
[ ! -e "$travail/.git/pmzilla-fin-en-cours" ]; verifie "verrou : libéré après un échec" $?
# libéré après un refus (arbre non propre, code 4)
nouveau; sur_branche feat/verrou4; valide tools/outil.sh v4 "code"; echo x > sale.txt
lance
code_et "verrou : refus 4" 4
[ ! -e "$travail/.git/pmzilla-fin-en-cours" ]; verifie "verrou : libéré après un refus" $?

# libéré à l'interruption (TERM sur le script pendant le runner)
nouveau; sur_branche feat/verrou5; valide tools/outil.sh v5 "code"; git push -q origin feat/verrou5
FINISH_BRANCH_RUNNER="echo \$\$ > $cas/pid-runner; exec sleep 30" "$BASH_FIN" "$travail/tools/finish_branch.sh" > "$cas/sortie-signal" 2>&1 &
pid_script=$!
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do [ -s "$cas/pid-runner" ] && break; sleep 0.5; done
[ -d "$travail/.git/pmzilla-fin-en-cours" ]; verifie "interruption : le verrou existe pendant le runner" $?
kill -TERM "$pid_script" 2>/dev/null; kill -TERM "$(cat "$cas/pid-runner" 2>/dev/null)" 2>/dev/null
wait "$pid_script" 2>/dev/null
[ ! -e "$travail/.git/pmzilla-fin-en-cours" ]; verifie "interruption : verrou libéré après un signal TERM" $?

# jeton hérité (lancé par finish_worktree.sh) : pas de refus, pas de second verrou, verrou laissé en place
nouveau; sur_branche feat/verrou6; valide tools/outil.sh v6 "code"; git push -q origin feat/verrou6
pose_verrou $$ jeton-herite; verrou_avant=$(etat_verrou)
export FINISH_LOCK_TOKEN=jeton-herite
FINISH_BRANCH_RUNNER="echo \"\$FINISH_LOCK_TOKEN\" > $cas/jeton-runner" lance
unset FINISH_LOCK_TOKEN
code_et "jeton hérité : la fin réussit" 0 "finish_branch : terminé"
[ "$(cat "$cas/jeton-runner")" = jeton-herite ]; verifie "jeton hérité : le runner reçoit le même jeton" $?
[ "$(etat_verrou)" = "$verrou_avant" ]; verifie "jeton hérité : le verrou de l'appelant reste en place, inchangé (aucun second verrou)" $?
! contient "périmé"; verifie "jeton hérité : aucune ligne de verrou périmé" $?
rm -rf "$travail/.git/pmzilla-fin-en-cours"

# verrou périmé (processus mort) : repris avec sa ligne, la fin continue, aucun verrou ensuite
nouveau; sur_branche feat/verrou7; valide tools/outil.sh v7 "code"; git push -q origin feat/verrou7
pose_verrou "$mort" jeton-mort
lance
code_et "verrou périmé : la fin continue" 0 "finish_branch : terminé"
contient "finish_branch : verrou de fin périmé, repris"; verifie "verrou périmé : la ligne « verrou de fin périmé, repris »" $?
[ ! -e "$travail/.git/pmzilla-fin-en-cours" ]; verifie "verrou périmé : le nouveau verrou est libéré à la fin" $?
# verrou trop vieux : même chose
nouveau; sur_branche feat/verrou8; valide tools/outil.sh v8 "code"; git push -q origin feat/verrou8
pose_verrou $$ jeton-vieux 500
export PMZILLA_FINISH_LOCK_MAX_AGE=10; lance; unset PMZILLA_FINISH_LOCK_MAX_AGE
code_et "verrou trop vieux : repris" 0 "verrou de fin périmé, repris"

# mode vérification : ni pris, ni lu, ni retiré ; pas de code 15
nouveau; sur_branche feat/verrou9; valide tools/outil.sh v9 "code"; git push -q origin feat/verrou9; git checkout -q main
pose_verrou $$ jeton-de-test; verrou_avant=$(etat_verrou)
lance --check feat/verrou9
code_et "mode vérification : un verrou vivant d'un autre ne le refuse pas" 0 "finish_branch"
[ "$(etat_verrou)" = "$verrou_avant" ]; verifie "mode vérification : le verrou est inchangé" $?
rm -rf "$travail/.git/pmzilla-fin-en-cours"
lance --check feat/verrou9
[ ! -e "$travail/.git/pmzilla-fin-en-cours" ]; verifie "mode vérification : aucun verrou créé" $?

# l'aide : 15 juste après 2
nouveau; lance --help
contient "2 usage ; 15 une autre fin de branche est en cours ; 3 à 8, 14 et 19 refus ci-dessus"; verifie "aide : le code 15 est listé juste après le 2" $?
printf '%s\n' "$SORTIE" | awk '/^  15 aucune autre fin de branche/{a=NR} /^  3  il y a une branche/{b=NR} END {exit !(a && b && a<b)}'; verifie "aide : la ligne 15 précède la ligne 3" $?
grep -q '^#   FINISH_LOCK_TOKEN ' "$script"; rc=$?; SORTIE="en-tête"; verifie "FINISH_LOCK_TOKEN est dans le bloc des variables de l'en-tête" $rc

# --- garde-fou du matin (change morning-guard, D6, tâche 5.1 et 5.3) : code 17 après le verrou et avant le 3, normal run seulement, rien n'est
# changé en cas de refus, aucune variable ne l'écarte. FINISH_MORNING_CHECK remplace la commande (le vrai module est exercé plus bas).
matin_refuse='echo "morning_state : refusé, fenêtre du matin depuis 06:45 : veille du jour absente"; exit 1'
nouveau; sur_branche feat/matin1; valide tools/outil.sh m1 "code"; git push -q origin feat/matin1
avant=$(etat_main); distant_avant=$(git --git-dir="$distant" rev-parse main)
FINISH_MORNING_CHECK="$matin_refuse" FINISH_BRANCH_RUNNER="echo appele >> $cas/appels-runner" lance
code_et "code 17 : le garde-fou refuse, tout le reste passerait" 17 "finish_branch : fenêtre du matin, état du matin non vérifié"
contient "morning_state : refusé, fenêtre du matin depuis 06:45 : veille du jour absente"; verifie "code 17 : la ligne du garde-fou est reprise telle quelle" $?
contient "relancer quand l'état du matin est vérifié : bash tools/morning_state.sh check"; verifie "code 17 : la ligne de relance donne la commande de contrôle" $?
[ ! -e "$cas/appels-runner" ]; verifie "code 17 : le faux runner n'a pas été appelé" $?
[ "$(etat_main)" = "$avant" ] && [ "$(git --git-dir="$distant" rev-parse main)" = "$distant_avant" ] && [ "$(git rev-parse --abbrev-ref HEAD)" = feat/matin1 ] \
  && git rev-parse -q --verify refs/heads/feat/matin1 >/dev/null && git --git-dir="$distant" rev-parse -q --verify refs/heads/feat/matin1 >/dev/null; verifie "code 17 : main, la branche et le distant sont inchangés, rien n'est fusionné ni supprimé" $?
[ ! -e "$travail/.git/pmzilla-fin-en-cours" ]; verifie "code 17 : le verrou de fin est libéré" $?
# le garde-fou autorise : le déroulé est celui d'avant
nouveau; sur_branche feat/matin2; valide tools/outil.sh m2 "code"; git push -q origin feat/matin2
FINISH_MORNING_CHECK='echo "morning_state : autorisé"; exit 0' lance
code_et "garde-fou qui autorise : la fin se termine comme sans garde-fou" 0 "finish_branch : terminé"
# le mode vérification ne lance pas le garde-fou
nouveau; sur_branche feat/matin3; valide tools/outil.sh m3 "code"; git checkout -q main
FINISH_MORNING_CHECK="touch $cas/garde-appele; exit 1" lance --check feat/matin3
code_et "mode vérification : le garde-fou refuserait mais n'est pas appelé, vérification réussie" 0
[ ! -e "$cas/garde-appele" ]; verifie "mode vérification : la commande du garde-fou n'a pas été lancée" $?
# aucune variable ne l'écarte
nouveau; sur_branche feat/matin4; valide tools/outil.sh m4 "code"
FINISH_BRANCH_FORCE_RUN=1 FINISH_WORKTREE_ALLOW_SKIP=1 PMZILLA_SKIP_GREEN_CHECK=1 FINISH_MORNING_SKIP=1 FINISH_MORNING_CHECK_OFF=1 FINISH_MORNING_CHECK="$matin_refuse" lance
code_et "aucune variable n'écarte le refus 17" 17 "fenêtre du matin, état du matin non vérifié"
! grep -v '^[[:space:]]*#' "$script" | grep -qE 'FINISH_MORNING_(SKIP|OFF|WAIVE)|GARDE_MATIN_OFF'; verifie "le script ne lit aucune variable de contournement du garde-fou" $?
# ordre : le verrou (15) puis le garde-fou (17) puis le 3
nouveau; sur_branche feat/matin5; valide tools/outil.sh m5 "code"; pose_verrou $$ jeton-de-test
FINISH_MORNING_CHECK="$matin_refuse" lance
code_et "15 avant 17 : un verrou vivant donne 15" 15 "une autre fin de branche est en cours"
rm -rf "$travail/.git/pmzilla-fin-en-cours"
nouveau; FINISH_MORNING_CHECK="$matin_refuse" lance
code_et "17 avant 3 : sur main, le garde-fou refuse d'abord" 17 "fenêtre du matin, état du matin non vérifié"
# la commande par défaut est le vrai module, ici sur des dossiers factices : midi, ni veille ni sauvegarde ni copie
nouveau; sur_branche feat/matin6; valide tools/outil.sh m6 "code"; git push -q origin feat/matin6
SORTIE=$(env -u FINISH_MORNING_CHECK OFFSITE_COPY_LOG="$cas/copie.log" OFFSITE_DONNEES="$cas/off" "$BASH_FIN" "$travail/tools/finish_branch.sh" 2>&1); CODE=$?
code_et "commande par défaut : le vrai module refuse à midi sans veille ni sauvegarde, code 17" 17 "morning_state : refusé, fenêtre du matin depuis 06:45"
# état du matin entièrement vérifié : le vrai module autorise et la fin se termine
jour=$(date -r "$MIDI" +%Y-%m-%d 2>/dev/null || date -d "@$MIDI" +%Y-%m-%d)
printf '{"date": "%s", "declencheur": "calendrier", "debut": "07:10", "fin": "07:40", "etat": "termine", "code": 0, "notifie": false, "essais": 0, "reprises": 0}\n' \
  "$(TZ=Europe/Paris date -r "$MIDI" +%Y-%m-%d 2>/dev/null || TZ=Europe/Paris date -d "@$MIDI" +%Y-%m-%d)" > "$PMZILLA_LAB_DATA/veille-du-jour.json"
mkdir -p "$cas/sauvegardes/db-$jour"; for s in knowledge cases flow quality-sans-texte; do : > "$cas/sauvegardes/db-$jour/$s.dump"; done
printf '%s 07:20:11 copie créée : db-%s (3 fichiers, 12 Ko)\n' "$jour" "$jour" > "$cas/copie.log"
SORTIE=$(env -u FINISH_MORNING_CHECK OFFSITE_COPY_LOG="$cas/copie.log" OFFSITE_DONNEES="$cas/off" "$BASH_FIN" "$travail/tools/finish_branch.sh" 2>&1); CODE=$?
code_et "commande par défaut : état du matin vérifié, le vrai module autorise et la fin se termine" 0 "finish_branch : terminé"
# l'aide
nouveau; lance --help
contient "3 à 8, 14 et 19 refus ci-dessus (19 : la branche touche un autre change OpenSpec) ; 17 fenêtre du matin, état du matin non vérifié"; verifie "aide : le code 17 est dans la liste des codes de sortie" $?
printf '%s\n' "$SORTIE" | awk '/^  15 aucune autre fin de branche/{a=NR} /^  17 le garde-fou du matin/{b=NR} /^  3  il y a une branche/{c=NR} END {exit !(a && b && c && a<b && b<c)}'; verifie "aide : la ligne 17 est après la ligne 15 et avant la ligne 3" $?
grep -q '^#   FINISH_MORNING_CHECK ' "$script"; rc=$?; SORTIE="en-tête"; verifie "FINISH_MORNING_CHECK est dans le bloc des variables de l'en-tête" $rc

# --- light-spec-finish : enregistrement de l'arbre de main validé, chemin allégé, code 18 (design D1 à D5, D8, D9)
# Trois faux notent leurs appels dans $cas/appels (runner complet, validation OpenSpec, passage allégé) ; l'horloge de la décision est fixée
# par LIGHT_FINISH_TODAY (variable lue par le seul module tools/light_finish.sh). Les lignes de l'enregistrement sont écrites à la main.
unset FINISH_BRANCH_FORCE_RUN FINISH_WORKTREE_ALLOW_SKIP FINISH_BRANCH_TESTED_TOKEN PERMET
export LIGHT_FINISH_TODAY=2026-01-15
fichier_main() { echo "$travail/.git/pmzilla-main-validated"; }
fakes() { # [code du runner complet] [code de la validation] [code du passage allégé]
  : > "$cas/appels"
  printf '#!/bin/sh\necho complet >> "%s"\nexit %s\n' "$cas/appels" "${1:-0}" > "$cas/complet.sh"
  printf '#!/bin/sh\necho "valide $*" >> "%s"\nexit %s\n' "$cas/appels" "${2:-0}" > "$cas/valide.sh"
  printf '#!/bin/sh\necho "leger $*" >> "%s"\nexit %s\n' "$cas/appels" "${3:-0}" > "$cas/leger.sh"
  chmod +x "$cas/complet.sh" "$cas/valide.sh" "$cas/leger.sh"
  export FINISH_BRANCH_RUNNER="$cas/complet.sh" FINISH_BRANCH_VALIDATE="$cas/valide.sh" FINISH_BRANCH_LIGHT_RUNNER="$cas/leger.sh"
}
n_appel() { grep -c "^$1" "$cas/appels"; }
signature_courante() { bash "$travail/tools/finish_env.sh" --main-signature; }   # signature d'environnement du cas (Q9) : mêmes outils, mêmes dossiers du lab
enregistre_main() { # date [signature ; défaut : celle de l'environnement du cas] [genre] : une ligne pour l'arbre de main
  fp=${2:-$(signature_courante)}
  printf '%s\t%s\t%s\t%s\n' "$(git rev-parse 'main^{tree}')" "${3:-complet}" "$1" "$fp" >> "$(fichier_main)"
}
spec_branche() { sur_branche "$1"; valide openspec/changes/x/proposal.md "texte" "spec"; }
n_lignes() { if [ -f "$(fichier_main)" ]; then wc -l < "$(fichier_main)" | tr -d ' '; else echo 0; fi; }
ligne_champ() { tail -n 1 "$(fichier_main)" | cut -f"$1"; }

# 1. branche de spécification, arbre de main enregistré : chemin allégé, enregistrement du nouvel arbre
nouveau; fakes; spec_branche spec/leger; enregistre_main 2026-01-15
lance
code_et "allégé : terminé" 0 "finish_branch : terminé"
contient "finish_branch : chemin allégé : la branche ne change que openspec/ et l'arbre de main est validé"; verifie "allégé : la ligne du chemin allégé" $?
[ "$(n_appel valide)" -eq 1 ] && [ "$(n_appel leger)" -eq 1 ] && [ "$(n_appel complet)" -eq 0 ]; verifie "allégé : validation et passage allégé appelés, runner complet jamais" $?
grep -q "^leger identifiants_personnels" "$cas/appels"; verifie "allégé : le passage allégé reçoit les noms de suites du sélecteur" $?
contient "finish_branch : passage allégé vert : 2 suite(s) au lieu du runner complet"; verifie "allégé : la ligne de passage vert" $?   # deux gardes toujours sélectionnées depuis pre-commit-secret-scan D7 (identifiants_personnels, secret_scan)
[ "$(git rev-list --parents -n1 main | wc -w)" -eq 3 ] && [ "$(git rev-parse main)" = "$(git --git-dir="$distant" rev-parse main)" ]; verifie "allégé : main fusionné et poussé" $?
# Les faux de ce cas posent FINISH_BRANCH_LIGHT_RUNNER et FINISH_BRANCH_VALIDATE : le passage est donc forcé par définition (risque des faux runners,
# design Risks) ; la ligne porte le genre « allégé-forcé » et non « allégé » (ces deux assertions ont changé pour cette raison, pas l'enregistrement).
[ "$(n_lignes)" -eq 2 ] && [ "$(ligne_champ 1)" = "$(git rev-parse 'main^{tree}')" ] && [ "$(ligne_champ 2)" = "allégé-forcé" ]; verifie "allégé : l'enregistrement gagne l'arbre du nouveau main, genre allégé-forcé (faux runners posés)" $?
contient "finish_branch : arbre de main enregistré comme validé (allégé-forcé)"; verifie "allégé : la ligne d'enregistrement" $?
[ "$(tail -n 1 "$(fichier_main)" | awk -F'\t' '{print NF}')" -eq 4 ] && ligne_champ 3 | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' && [ "$(ligne_champ 3)" = "$(date -u +%Y-%m-%d)" ] && [ "$(ligne_champ 4)" = "$(signature_courante)" ]; verifie "allégé : quatre colonnes, date UTC du jour, signature d'environnement" $?
! tail -n 1 "$(fichier_main)" | grep -qF -e spec/ -e "$(git rev-parse main)"; verifie "allégé : ni branche ni commit dans la ligne" $?
[ ! -e "$(git rev-parse --git-path pmzilla-light-ok)" ]; verifie "allégé : l'empreinte allégée est effacée après le push" $?
[ ! -e "$(git rev-parse --git-path pmzilla-run-all-ok)" ] && [ ! -e "$(git rev-parse --git-path pmzilla-run-targeted-ok)" ]; verifie "allégé : ni empreinte complète ni empreinte ciblée" $?
# le push passe par le hook pre-push (lanceur factice) : l'empreinte allégée revérifiée suffit, aucun test n'est lancé par le hook
nouveau; fakes; spec_branche spec/hook; enregistre_main 2026-01-15
ln -sf "$outils/hooks/pre-push" .git/hooks/pre-push; export PRE_PUSH_RUNNER="touch $cas/hook-appele"
export PMZILLA_LAB_WORKSPACE="$travail"   # le hook calcule la signature depuis les outils du dépôt réel : le dossier de contenu est fixé pour que les deux calculs coïncident
lance
unset PRE_PUSH_RUNNER PMZILLA_LAB_WORKSPACE
code_et "allégé avec le hook pre-push : terminé" 0 "finish_branch : terminé"
[ ! -e "$cas/hook-appele" ] && [ "$(git rev-parse main)" = "$(git --git-dir="$distant" rev-parse main)" ]; verifie "allégé avec le hook pre-push : le hook ne lance aucun runner, main poussé" $?
[ ! -e "$(git rev-parse --git-path pmzilla-run-all-ok)" ]; verifie "allégé avec le hook pre-push : l'empreinte complète est inchangée (absente)" $?

# 2. jamais hors de openspec/ : l'enregistrement tient l'arbre de main, un seul chemin hors du dossier donne le runner complet
cas_hors() { # description commandes (évaluées sur une branche créée depuis main)
  nouveau; fakes; sur_branche feat/hors; eval "$2"; enregistre_main 2026-01-15
  lance
  [ "$CODE" -eq 0 ] && [ "$(n_appel complet)" -eq 1 ] && [ "$(n_appel valide)" -eq 0 ] && [ "$(n_appel leger)" -eq 0 ]; verifie "hors openspec/ : $1 : runner complet seul" $?
}
cas_hors "outil modifié" 'valide tools/outil.sh m1 "t"; valide openspec/specs/x/p.md y "s"'
cas_hors "fichier ajouté à la racine" 'valide racine.txt r "r"; valide openspec/specs/x/p.md y "s"'
cas_hors "fichier supprimé hors du dossier" 'git rm -q tools/outil.sh; git commit -q -m d; valide openspec/specs/x/p.md y "s"'
cas_hors "renommage de openspec/ vers docs/" 'mkdir -p docs; git mv openspec/changes/archive/.gitkeep docs/k; git commit -q -m r'
cas_hors "renommage de docs/ vers openspec/" 'git mv .claude/commands/c.md openspec/changes/c.md; git commit -q -m r'
cas_hors "fichier racine nommé openspec" 'git rm -rq openspec; echo x > openspec; git add -A; git commit -q -m f'
cas_hors "dossier openspecs/" 'valide openspecs/x.md y "o"'
cas_hors "commit de fusion qui apporte un fichier hors du dossier" 'git checkout -q -b autre main; valide tools/autre.sh a "a"; git checkout -q feat/hors; git merge -q --no-ff autre -m m; valide openspec/specs/x/p.md y "s"'
nouveau; fakes; sur_branche spec/lien; ln -s ../x openspec/changes/lien; git add -A; git commit -q -m l; enregistre_main 2026-01-15
lance
code_et "lien symbolique sous openspec/ : runner complet avec la raison" 0 "finish_branch : runner complet nécessaire : lien symbolique ou sous-module sous openspec/"
[ "$(n_appel complet)" -eq 1 ] && [ "$(n_appel valide)" -eq 0 ] && [ "$(n_appel leger)" -eq 0 ]; verifie "lien symbolique sous openspec/ : runner complet seul" $?

# 3. jamais sans l'enregistrement de l'arbre de main
nouveau; fakes; spec_branche spec/sans
lance
code_et "sans fichier d'enregistrement : runner complet, raison" 0 "finish_branch : runner complet nécessaire : arbre de main non validé"
[ "$(n_appel complet)" -eq 1 ] && [ "$(n_appel leger)" -eq 0 ]; verifie "sans fichier d'enregistrement : runner complet seul" $?
nouveau; fakes; spec_branche spec/autre-arbre; printf '%s\tcomplet\t2026-01-15\tabsent\n' 1111111111111111111111111111111111111111 > "$(fichier_main)"
lance
code_et "enregistrement sans l'arbre de main : runner complet, raison" 0 "runner complet nécessaire : arbre de main non validé"
nouveau; fakes; spec_branche spec/direct; enregistre_main 2026-01-15
git checkout -q main; valide tools/outil.sh direct "commit direct sur main"; git checkout -q spec/direct; git merge -q --no-edit main
lance
code_et "main avancé par un commit direct : runner complet, raison" 0 "runner complet nécessaire : arbre de main non validé"
[ "$(n_appel complet)" -eq 1 ] && [ "$(n_appel leger)" -eq 0 ] && [ "$(ligne_champ 2)" = complet ] && [ "$(ligne_champ 1)" = "$(git rev-parse 'main^{tree}')" ]; verifie "main avancé : le runner complet seul, et la chaîne repart avec le nouvel arbre (complet)" $?

# 3b. expiration (question Q8) : valide à 6 et 7 jours, expirée à 8 ; horloge LIGHT_FINISH_TODAY = 2026-01-15
cas_age() { # description date-enregistrée attendu (allege | raison)
  nouveau; fakes; spec_branche spec/age; enregistre_main "$2"
  lance
  if [ "$3" = allege ]; then
    code_et "$1 : chemin allégé" 0 "finish_branch : chemin allégé"
    [ "$(n_appel complet)" -eq 0 ] && [ "$(n_appel leger)" -eq 1 ]; verifie "$1 : passage allégé seul" $?
  else
    code_et "$1 : runner complet, raison" 0 "finish_branch : runner complet nécessaire : $3"
    [ "$(n_appel complet)" -eq 1 ] && [ "$(n_appel leger)" -eq 0 ] && [ "$(n_appel valide)" -eq 0 ]; verifie "$1 : runner complet seul" $?
  fi
}
cas_age "enregistré il y a 6 jours" 2026-01-09 allege
cas_age "enregistré il y a 7 jours (limite)" 2026-01-08 allege
cas_age "enregistré il y a 8 jours" 2026-01-07 "validation de main expirée"
cas_age "date dans le futur" 2026-01-20 "validation de main expirée"
cas_age "date mal formée" hier "validation de main expirée"
# 3c. signature d'environnement (question Q9) : le PATH du lancement est un dossier du cas (liens vers les vrais outils, faux uv qui dit la version choisie)
PATH_REEL=$PATH
sans_uv="$tmp/sans-uv"   # liens vers chaque exécutable du PATH réel sauf uv : un PATH sans uv, sur n'importe quelle machine
if [ ! -d "$sans_uv" ]; then
  mkdir -p "$sans_uv"
  for d in $(printf '%s' "$PATH_REEL" | tr ':' ' '); do
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
chemin_reel() { PATH=$PATH_REEL; export PATH; }
cas_signature() { # description version-enregistrée version-au-lancement ("sans" : PATH sans uv) attendu (allege | raison)
  nouveau; fakes; spec_branche spec/sig
  avec_uv "$2"; enregistre_main 2026-01-15
  if [ "$3" = sans ]; then PATH="$sans_uv"; export PATH; else avec_uv "$3"; fi
  lance; chemin_reel
  if [ "$4" = allege ]; then
    code_et "$1 : chemin allégé" 0 "finish_branch : chemin allégé"
    [ "$(n_appel complet)" -eq 0 ] && [ "$(n_appel leger)" -eq 1 ]; verifie "$1 : passage allégé seul" $?
  else
    code_et "$1 : runner complet, raison" 0 "finish_branch : runner complet nécessaire : $4"
    [ "$(n_appel complet)" -eq 1 ] && [ "$(n_appel leger)" -eq 0 ] && [ "$(n_appel valide)" -eq 0 ]; verifie "$1 : runner complet seul" $?
  fi
}
cas_signature "même signature" 1.2.3 1.2.3 allege
cas_signature "autre version de uv" 1.2.3 1.2.4 "environnement changé depuis la validation"
cas_signature "uv absent du PATH" 1.2.3 sans "signature d'environnement impossible : uv absent ou illisible"
cas_colonne() { # description valeur-de-la-4e-colonne
  nouveau; fakes; spec_branche spec/col; enregistre_main 2026-01-15 "$2"
  lance
  code_et "$1 : runner complet, raison" 0 "finish_branch : runner complet nécessaire : signature d'environnement absente de la validation"
  [ "$(n_appel complet)" -eq 1 ] && [ "$(n_appel leger)" -eq 0 ]; verifie "$1 : runner complet seul" $?
}
cas_colonne "quatrième colonne « inconnue »" inconnue
cas_colonne "ancien hash de blob (40 caractères)" 0123456789012345678901234567890123456789
cas_colonne "quatrième colonne « absent »" absent
cas_colonne "64 caractères dont un en majuscule" "A$(signature_courante | cut -c2-)"
# l'expiration est vue avant la signature
nouveau; fakes; spec_branche spec/exp
enregistre_main 2026-01-07 inconnue
lance
code_et "expirée et signature absente : l'expiration d'abord" 0 "runner complet nécessaire : validation de main expirée"
# une fin au runner complet réécrit la ligne avec la date du jour et la signature d'environnement
nouveau; fakes; sur_branche feat/c; valide tools/outil.sh c1 "code"
lance
code_et "fin au runner complet : terminée" 0 "finish_branch : arbre de main enregistré comme validé (complet)"
[ "$(n_lignes)" -eq 1 ] && [ "$(ligne_champ 1)" = "$(git rev-parse 'main^{tree}')" ] && [ "$(ligne_champ 2)" = complet ] && [ "$(ligne_champ 3)" = "$(date -u +%Y-%m-%d)" ] && [ "$(ligne_champ 4)" = "$(signature_courante)" ] && [ "$(ligne_champ 4 | tr -d '0-9a-f\n' | wc -c | tr -d ' ')" -eq 0 ] && [ "$(ligne_champ 4 | tr -d '\n' | wc -c | tr -d ' ')" -eq 64 ]; verifie "fin complète : tree, genre complet, date du jour, signature de 64 hexadécimaux" $?
[ -f "$(fichier_main)" ] && ! tail -n 1 "$(fichier_main)" | grep -qF -e feat/ -e "$(git rev-parse main)"; verifie "fin complète : ni branche ni commit dans la ligne" $?
# signature impossible à l'écriture : « inconnue », la fin réussit (code 0) et la ligne ne donnera jamais le chemin allégé
nouveau; fakes; sur_branche feat/inc; valide tools/outil.sh i1 "code"
PATH="$sans_uv"; export PATH; lance; chemin_reel
code_et "fin complète sans uv : terminée" 0 "finish_branch : arbre de main enregistré comme validé (complet)"
[ "$(n_lignes)" -eq 1 ] && [ "$(ligne_champ 4)" = inconnue ]; verifie "fin complète sans uv : quatrième colonne « inconnue »" $?

# bash tools/finish_env.sh --main-signature : une ligne de 64 hexadécimaux, stable, sensible au faux uv et à PMZILLA_LAB_DATA, absent:uv sans uv, jamais un chemin ni une version
nouveau; avec_uv 1.2.3
s1=$(bash "$travail/tools/finish_env.sh" --main-signature); c1=$?; s2=$(bash "$travail/tools/finish_env.sh" --main-signature)
[ "$c1" -eq 0 ] && [ "${#s1}" -eq 64 ] && [ -z "$(printf '%s' "$s1" | tr -d '0-9a-f')" ] && [ "$s1" = "$s2" ]; SORTIE="$s1 / $s2"; verifie "--main-signature : 64 hexadécimaux, identique deux fois, code 0" $?
avec_uv 1.2.4; s3=$(bash "$travail/tools/finish_env.sh" --main-signature)
[ "${#s3}" -eq 64 ] && [ "$s3" != "$s1" ]; SORTIE="$s3"; verifie "--main-signature : une autre version de uv change la signature" $?
avec_uv 1.2.3; s4=$(PMZILLA_LAB_DATA="$cas/autre-donnees" bash "$travail/tools/finish_env.sh" --main-signature)
[ "${#s4}" -eq 64 ] && [ "$s4" != "$s1" ]; SORTIE="$s4"; verifie "--main-signature : PMZILLA_LAB_DATA change la signature" $?
PATH="$sans_uv"; export PATH; s5=$(bash "$travail/tools/finish_env.sh" --main-signature 2>&1); c5=$?; chemin_reel
[ "$c5" -eq 1 ] && [ "$s5" = "absent:uv" ]; SORTIE="$s5 (code $c5)"; verifie "--main-signature : sans uv, absent:uv et code 1" $?
! printf '%s\n%s\n%s\n' "$s1" "$s5" "$s3" | grep -qF -e "$cas" -e "$travail" -e 1.2.3 -e 1.2.4 -e "$HOME"; SORTIE="$s1 $s5"; verifie "--main-signature : ni chemin ni version dans les sorties" $?
# fin sautée (second runner) : le même enregistrement
PERMET=1
nouveau; sur_branche feat/saut-leger; valide tools/outil.sh s2 "code"; compte_runner; fiche_ecrire
lancej
code_et "fin sautée : terminée" 0 "second lancement sauté"
[ "$(n_lignes)" -eq 1 ] && [ "$(ligne_champ 1)" = "$(git rev-parse 'main^{tree}')" ] && [ "$(ligne_champ 2)" = complet ]; verifie "fin sautée : l'enregistrement gagne l'arbre testé (complet)" $?
unset PERMET

# écriture impossible : sans effet sur le résultat
nouveau; sur_branche feat/ecriture; valide tools/outil.sh e1 "code"; mkdir "$(fichier_main)"
lance
code_et "écriture impossible : dite, code 0" 0 "finish_branch : arbre de main non enregistré (écriture impossible)"
# aucune écriture : runner rouge, push refusé, mode vérification
nouveau; sur_branche feat/rouge2; valide tools/outil.sh r2 "code"; FINISH_BRANCH_RUNNER=false lance
code_et "runner rouge : code 1" 1 "tests en échec"
[ "$(n_lignes)" -eq 0 ]; verifie "runner rouge : aucune ligne écrite" $?
nouveau; fakes; spec_branche spec/refus; enregistre_main 2026-01-15; arbre_sommet=$(git rev-parse 'HEAD^{tree}')
printf '#!/bin/sh\nexit 1\n' > "$distant/hooks/pre-receive"; chmod +x "$distant/hooks/pre-receive"
lance
code_et "push refusé après un passage allégé vert : code 10" 10 "finish_branch : push refusé"
[ "$(n_lignes)" -eq 1 ]; verifie "push refusé : aucune ligne écrite" $?
[ "$(cat "$(git rev-parse --git-path pmzilla-light-ok)")" = "$arbre_sommet" ]; verifie "push refusé : l'empreinte allégée garde l'arbre du sommet" $?
nouveau; fakes; spec_branche spec/verif; enregistre_main 2026-01-15; git checkout -q main
lance --check spec/verif
code_et "mode vérification : réussit" 0 "finish_branch : vérification seule"
[ "$(wc -c < "$cas/appels" | tr -d ' ')" -eq 0 ] && [ "$(n_lignes)" -eq 1 ] && ! contient "chemin allégé"; verifie "mode vérification : ni validation, ni passage allégé, ni enregistrement" $?

# 4. jamais avec la variable de relance forcée, quelle que soit la valeur
for valeur in 1 0; do
  nouveau; fakes; spec_branche spec/force; enregistre_main 2026-01-15
  FINISH_BRANCH_FORCE_RUN=$valeur lance; unset FINISH_BRANCH_FORCE_RUN
  code_et "relance forcée ($valeur) : runner complet, raison" 0 "finish_branch : runner complet nécessaire : relance forcée"
  [ "$(n_appel complet)" -eq 1 ] && [ "$(n_appel valide)" -eq 0 ] && [ "$(n_appel leger)" -eq 0 ] && ! grep -q "allégé" "$(fichier_main)"; verifie "relance forcée ($valeur) : runner complet seul, aucune ligne allégée" $?
  [ ! -e "$(git rev-parse --git-path pmzilla-light-ok)" ]; verifie "relance forcée ($valeur) : aucune empreinte allégée" $?
done

# 5. validation rouge (18), passage allégé rouge (1), validation introuvable (runner complet)
nouveau; fakes 0 1 0; spec_branche spec/valrouge; enregistre_main 2026-01-15; avant=$(etat_main)
lance
code_et "validation rouge : code 18" 18 "finish_branch : openspec validate --strict en échec, rien n'est fusionné"
contient "Corrige les specs de la branche, relance."; verifie "validation rouge : la consigne" $?
[ "$(n_appel valide)" -eq 1 ] && [ "$(n_appel leger)" -eq 0 ] && [ "$(n_appel complet)" -eq 0 ] && [ "$(etat_main)" = "$avant" ] && [ "$(git --git-dir="$distant" rev-parse main)" = "$avant" ]; verifie "validation rouge : aucun runner, main inchangé (local et distant)" $?
nouveau; fakes 0 0 1; spec_branche spec/legrouge; enregistre_main 2026-01-15; avant=$(etat_main)
lance
code_et "passage allégé rouge : code 1" 1 "finish_branch : tests en échec, rien n'est fusionné"
contient "(passage allégé)"; verifie "passage allégé rouge : la mention (passage allégé)" $?
[ "$(etat_main)" = "$avant" ] && [ "$(n_lignes)" -eq 1 ]; verifie "passage allégé rouge : main inchangé, aucune ligne écrite" $?
nouveau; fakes 0 127 0; spec_branche spec/introuvable; enregistre_main 2026-01-15
lance
code_et "validation introuvable (127) : runner complet, raison" 0 "finish_branch : runner complet nécessaire : openspec introuvable"
[ "$(n_appel complet)" -eq 1 ] && [ "$(n_appel leger)" -eq 0 ] && [ "$(ligne_champ 2)" = complet ]; verifie "validation introuvable : runner complet seul, fin enregistrée (complet)" $?

# light-finish-touched-specs (D3) : la validation reçoit la référence de main et le sommet ; par défaut, c'est tools/light_validate.py
nouveau; fakes; spec_branche spec/args; enregistre_main 2026-01-15
principal=$(git rev-parse refs/heads/main); sommet=$(git rev-parse HEAD)
lance
grep -qx "valide $principal $sommet" "$cas/appels"; rc=$?; SORTIE="$(cat "$cas/appels")"; verifie "validation remplacée : reçoit la référence de main puis le sommet" $rc
nouveau; fakes; spec_branche spec/defaut; enregistre_main 2026-01-15; unset FINISH_BRANCH_VALIDATE
printf '#!/bin/sh\necho "openspec $*" >> "%s"\nif [ -n "$OS_ISSUE" ]; then echo %s; else echo %s; fi\nexit 0\n' "$cas/appels-os" \
  "'{\"items\":[{\"id\":\"x\",\"issues\":[{\"level\":\"WARNING\",\"path\":\"p\",\"message\":\"trop long\"}]}]}'" "'{\"items\":[{\"id\":\"x\",\"issues\":[]}]}'" > "$cas/faux-os.sh"
chmod +x "$cas/faux-os.sh"; export LIGHT_VALIDATE_OPENSPEC="$cas/faux-os.sh"
lance
code_et "validation par défaut verte : terminé" 0 "validation OpenSpec : 1 élément(s) touché(s), aucun nouvel avertissement strict"
grep -q "^openspec validate x --type change" "$cas/appels-os" && [ "$(n_appel leger)" -eq 1 ] && [ "$(n_appel complet)" -eq 0 ]; verifie "validation par défaut : le helper interroge OpenSpec, passage allégé lancé" $?
nouveau; fakes; spec_branche spec/defrouge; enregistre_main 2026-01-15; unset FINISH_BRANCH_VALIDATE
printf '#!/bin/sh\necho %s\n' "'{\"items\":[{\"id\":\"x\",\"issues\":[{\"level\":\"WARNING\",\"path\":\"p\",\"message\":\"trop long\"}]}]}'" > "$cas/faux-os.sh"
chmod +x "$cas/faux-os.sh"; export LIGHT_VALIDATE_OPENSPEC="$cas/faux-os.sh"; avant=$(etat_main)
lance
code_et "validation par défaut rouge : code 18" 18 "nouvel avertissement strict : change x : trop long"
contient "finish_branch : openspec validate --strict en échec, rien n'est fusionné"; verifie "validation par défaut rouge : la phrase du code 18 est inchangée" $?
[ "$(n_appel leger)" -eq 0 ] && [ "$(etat_main)" = "$avant" ]; verifie "validation par défaut rouge : aucun passage, main inchangé" $?
nouveau; fakes; spec_branche spec/defabsent; enregistre_main 2026-01-15; unset FINISH_BRANCH_VALIDATE; export LIGHT_VALIDATE_OPENSPEC="$cas/inexistante"
lance
code_et "validation par défaut sans openspec : runner complet, raison" 0 "finish_branch : runner complet nécessaire : openspec introuvable"
unset LIGHT_VALIDATE_OPENSPEC

# 5b. passage allégé forcé (risque des faux runners) : le genre est « allégé » sans variable, « allégé-forcé » dès que l'une des deux est non vide
genre_leger() { # [LIGHT_RUNNER] [VALIDATE] : le genre que le module écrit pour un passage allégé vert
  env -u FINISH_BRANCH_LIGHT_RUNNER -u FINISH_BRANCH_VALIDATE ${1:+FINISH_BRANCH_LIGHT_RUNNER=$1} ${2:+FINISH_BRANCH_VALIDATE=$2} \
    sh -c 'LIGHT_FINISH_DIR="$1"; . "$1/light_finish.sh"; light_genre_leger' _ "$travail/tools"
}
nouveau
[ "$(genre_leger)" = "allégé" ]; verifie "genre allégé : aucune variable posée, « allégé »" $?
[ "$(genre_leger true)" = "allégé-forcé" ]; verifie "genre allégé : le passage allégé posé à true, « allégé-forcé »" $?
[ "$(genre_leger "" true)" = "allégé-forcé" ]; verifie "genre allégé : la validation posée à true, « allégé-forcé »" $?
# une ligne « allégé-forcé » n'ouvre pas le chemin allégé à la branche suivante, même fraîche et de même signature
nouveau; fakes; spec_branche spec/forcee; enregistre_main 2026-01-15 "" allégé-forcé
lance
code_et "ligne allégé-forcé : runner complet, raison" 0 "finish_branch : runner complet nécessaire : validation de main forcée"
[ "$(n_appel complet)" -eq 1 ] && [ "$(n_appel leger)" -eq 0 ] && [ "$(n_appel valide)" -eq 0 ] && [ "$(ligne_champ 2)" = complet ]; verifie "ligne allégé-forcé : runner complet seul, la chaîne repart (complet)" $?
# deux fins forcées de suite : la seconde reprend le runner complet
nouveau; fakes; spec_branche spec/f1; enregistre_main 2026-01-15
lance
code_et "première fin forcée : chemin allégé" 0 "finish_branch : chemin allégé"
sur_branche spec/f2; valide openspec/changes/y/proposal.md "texte" "spec"; : > "$cas/appels"
lance
code_et "seconde fin après une fin forcée : runner complet, raison" 0 "finish_branch : runner complet nécessaire : validation de main forcée"
[ "$(n_appel complet)" -eq 1 ] && [ "$(n_appel leger)" -eq 0 ]; verifie "seconde fin après une fin forcée : runner complet seul" $?

# 8. l'aide et l'en-tête
nouveau; lance --help
printf '%s\n' "$SORTIE" | awk '/^  12 /{a=NR} /^  18 /{b=NR} /^  1  /{c=NR} END {exit !(a && b && c && a<b && b<c)}'; verifie "aide : le code 18 est listé après le 12 et avant le 1" $?
contient "18 passage allégé"; verifie "aide : le code 18 est dans les codes de sortie" $?
grep -q '^#   FINISH_BRANCH_LIGHT_RUNNER ' "$script" && grep -q '^#   FINISH_BRANCH_VALIDATE ' "$script"; rc=$?; SORTIE="en-tête"; verifie "l'en-tête nomme les deux variables de test du chemin allégé" $rc
unset LIGHT_FINISH_TODAY FINISH_BRANCH_VALIDATE FINISH_BRANCH_LIGHT_RUNNER

# --- finish-under-lock D6 : une branche ne porte qu'un change (code 19), après le 4 et avant le 5
# branche touchant un autre change actif : 19, le nom, la seconde ligne, rien n'est fusionné ; avant le 5 (le change B n'est pas archivé)
nouveau; sur_branche feat/autre-travail; valide tools/outil.sh u1 "code"; valide openspec/changes/changeb/proposal.md p "change b"; avant=$(etat_main)
lance
code_et "code 19 : la branche touche un autre change actif (19 et non 5)" 19 "finish_branch : la branche touche un autre change OpenSpec : changeb"
contient "une branche ne porte qu'un change ; déplace ce travail dans sa propre branche"; verifie "code 19 : la seconde ligne est donnée" $?
[ "$(etat_main)" = "$avant" ] && [ "$(git rev-parse --abbrev-ref HEAD)" = feat/autre-travail ]; verifie "code 19 : rien n'est fusionné, branche inchangée" $?
# mode vérification : 19, rien n'est changé
git checkout -q main
avant=$(etat_complet)
verif feat/autre-travail
code_et "code 19 : le mode vérification sort 19" 19 "la branche touche un autre change OpenSpec : changeb"
[ "$avant" = "$(etat_complet)" ] && [ ! -e "$cas/runner-appele" ]; verifie "code 19 : le mode vérification ne change rien" $?
# branche sans change propre (prompt direct) : 19 aussi
nouveau; sur_branche fix/petit; valide tools/outil.sh u2 "code"; valide openspec/changes/changeb/proposal.md p "change b"
lance
code_et "code 19 : branche de prompt direct qui touche un change" 19 "la branche touche un autre change OpenSpec : changeb"
# son propre change, archivé : passe
nouveau; sur_branche feat/propre; valide tools/outil.sh u3 "code"; valide openspec/changes/archive/2026-01-15-propre/proposal.md p "archive propre"
lance
code_et "code 19 : son propre change archivé passe" 0 "finish_branch : terminé"
! contient "autre change OpenSpec"; verifie "code 19 : son propre change ne déclenche rien" $?
# archive d'un autre change : permise, avec une ligne
nouveau; sur_branche feat/archive-autre; valide tools/outil.sh u4 "code"; valide openspec/changes/archive/2026-01-01-ancien/tasks.md t "archive d'un autre"
lance
code_et "archive d'un autre change : permise" 0 "finish_branch : la branche modifie l'archive d'un autre change : 2026-01-01-ancien (permis)"
# branche de train : permise, avec la ligne des changes portés
nouveau; mkdir -p openspec/changes/ca openspec/changes/cb; echo p > openspec/changes/ca/proposal.md; echo p > openspec/changes/cb/proposal.md
git add -A; git commit -q -m "deux changes"; git push -q origin main
sur_branche lot/deux; valide tools/outil.sh u5 "code"; mkdir -p openspec/changes/archive
git mv openspec/changes/ca openspec/changes/archive/2026-01-15-ca; git mv openspec/changes/cb openspec/changes/archive/2026-01-15-cb; git commit -q -m "archive"
lance
code_et "branche de train : permise, changes portés" 0 "finish_branch : branche de train : changes portés : ca, cb"
# branche de spécification : jamais 19 (mode vérification : on ne court pas le chemin de fin)
nouveau; mkdir -p openspec/changes/sa openspec/changes/sb; echo p > openspec/changes/sa/proposal.md; echo p > openspec/changes/sb/proposal.md
git add -A; git commit -q -m "deux changes"; git push -q origin main
sur_branche spec/deux; valide openspec/changes/sa/proposal.md q "sa"; valide openspec/changes/sb/proposal.md q "sb"; git checkout -q main
verif spec/deux
code_et "branche de spécification : pas de code 19" 0 "vérification seule"
# l'aide : 19 entre 4 et 5
nouveau; lance --help
printf '%s\n' "$SORTIE" | awk '/^  4  /{a=NR} /^  19 /{b=NR} /^  5  /{c=NR} END {exit !(a && b && c && a<b && b<c)}'; verifie "aide : le code 19 est listé entre le 4 et le 5" $?
contient "(19 : la branche touche un autre change OpenSpec)"; verifie "aide : le code 19 est dans les codes de sortie" $?
[ "$BASH_FIN" = /bin/bash ] || [ ! -x /bin/bash ]; verifie "la suite lance le script par /bin/bash quand il existe" $?

# --- finish-under-lock D10 : l'aperçu de la fusion de main avec le code 8, sur le sommet de la branche, dans les deux modes
nouveau; sur_branche feat/conflit; valide tools/outil.sh branche "b"
git checkout -q main; valide tools/outil.sh principale "m"; git push -q origin main; git checkout -q feat/conflit
lance
code_et "aperçu : conflit prévu, code 8 inchangé" 8 "finish_branch : la branche ne contient pas main"
contient "fusion de main prévue : conflit sur 1 fichier(s)" && contient "tools/outil.sh"; verifie "aperçu : le conflit et le fichier sont dits (fin de branche)" $?
[ ! -f .git/MERGE_HEAD ] && [ -z "$(git status --porcelain)" ]; verifie "aperçu : aucune fusion en cours, arbre propre" $?
git checkout -q main
verif feat/conflit
code_et "aperçu : conflit prévu en mode vérification" 8 "fusion de main prévue : conflit sur 1 fichier(s)"
nouveau; sur_branche feat/propre2; valide tools/autre.sh branche "b"
git checkout -q main; valide main.txt m "sur main"; git push -q origin main; git checkout -q feat/propre2
lance
code_et "aperçu : sans conflit" 8 "fusion de main prévue : sans conflit"
git checkout -q main
verif feat/propre2
code_et "aperçu : sans conflit en mode vérification" 8 "fusion de main prévue : sans conflit"

# --- le script ne remet à zéro ni ne nettoie le dossier d'exécution
grep -v '^[[:space:]]*#' "$script" | grep -E -e 'git +clean|git -C [^ ]+ +(reset|clean|stash|checkout)|worktree +(remove|prune|add)|run_worktree.sh +(create|remove)' >/dev/null
[ $? -ne 0 ]; rc=$?; SORTIE="remise à zéro ou nettoyage du dossier d'exécution trouvé"; verifie "aucune remise à zéro ni nettoyage du dossier d'exécution dans le script" $rc

# --- le script n'emploie aucune commande interdite
awk '/<<'"'"'?EOF'"'"'?[[:space:]]*$/ {h=1; next} h && /^EOF$/ {h=0; next} h {next} /^[[:space:]]*#/ {next} {print}' "$script" | grep -E -e '--force|push -f|--no-verify|branch -D|rebase |PMZILLA_SKIP_GREEN_CHECK=|posture_evals' >/dev/null
[ $? -ne 0 ]; rc=$?; SORTIE="commande interdite trouvée"; verifie "aucune commande interdite dans le script (force, rebase, -D, --no-verify, jeu d'essai)" $rc

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
