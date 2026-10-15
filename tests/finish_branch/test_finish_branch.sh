#!/bin/sh
# Test du script de fin de branche (tools/finish_branch.sh) : dépôt Git temporaire, dépôt distant nu temporaire,
# faux runner (FINISH_BRANCH_RUNNER) et faux dossier d'enregistrements du jeu d'essai (FINISH_BRANCH_RECORDS).
# Un test par code de sortie (0 à 11), plus les cas de la spécification (branche de spécification, change archivé sur la branche,
# commit ultérieur sur d'autres fichiers, vocabulaire ou mémoire figée sans passage, état testé disparu, commit non référencé encore présent).
# Le dépôt temporaire contient une copie suivie de finish_branch.sh et de run_worktree.sh (ce dernier lit son propre dépôt) ;
# le dossier d'exécution est un faux dossier (PMZILLA_LAB_RUN), les données du labo un faux dossier (PMZILLA_LAB_DATA), l'horloge est fixée à midi.
# Aucun réseau, aucune base, aucun jeu d'essai, aucun vrai runner. Lancement à la main : sh tests/finish_branch/test_finish_branch.sh
set -u
unset PMZILLA_SKIP_GREEN_CHECK PMZILLA_NO_EVALS
outils="$(cd "$(dirname "$0")/../../tools" && pwd)"
script="$outils/finish_branch.sh"
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
export GIT_CONFIG_GLOBAL="$tmp/gitconfig" GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0
git config --global user.email t@example.org
git config --global user.name test
git config --global init.defaultBranch main
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

nouveau() { # prépare un dépôt de travail, un dépôt distant nu et des enregistrements vides ; place dans le dépôt de travail
  n=$((n+1))
  cas="$tmp/cas$n"; distant="$cas/distant.git"; travail="$cas/travail"; export FINISH_BRANCH_RECORDS="$cas/essais"
  mkdir -p "$cas" "$FINISH_BRANCH_RECORDS"
  git init -q --bare "$distant"
  git init -q "$travail"
  cd "$travail" || exit 1
  git remote add origin "$distant"
  mkdir -p tools openspec/changes/archive .claude/commands .claude/agents .claude/skills/pmzilla-x tests/postures/memoire
  echo base > tools/outil.sh; echo c > CLAUDE.md; echo s > .claude/skills/pmzilla-x/SKILL.md
  echo v > tests/postures/vocabulaire.yaml; echo m > tests/postures/memoire/m.md
  echo cmd > .claude/commands/c.md; echo ag > .claude/agents/autre.md; echo ag > .claude/agents/pmzilla-critic.md
  cp "$outils/finish_branch.sh" "$outils/run_worktree.sh" tools/
  export PMZILLA_LAB_RUN="$cas/run" PMZILLA_LAB_DATA="$cas/data" PMZILLA_RUN_NOW="$MIDI"
  mkdir -p "$PMZILLA_LAB_DATA"
  echo "# a" > openspec/changes/archive/.gitkeep; printf 'ignore.log\n' > .gitignore
  git add -A && git commit -q -m initial && git push -q origin main
  export FINISH_BRANCH_RUNNER=true
}
sur_branche() { git checkout -q -b "$1"; }   # nom de branche
valide() { # fichier contenu message : un commit qui écrit le fichier
  mkdir -p "$(dirname "$1")"; printf '%s\n' "$2" > "$1"; git add -A; git commit -q -m "$3"
}
lance() { SORTIE=$(bash "$travail/tools/finish_branch.sh" "$@" 2>&1); CODE=$?; }
cree_run() { git worktree add -q --detach "$cas/run" main; }   # dossier d'exécution détaché au sommet de main
enregistre() { # nom base complet validant rejuge langue : écrit un enregistrement du jeu d'essai
  mkdir -p "$FINISH_BRANCH_RECORDS/$1"
  cat > "$FINISH_BRANCH_RECORDS/$1/resultats.json" <<EOF
{"date": "$1", "base": "$2", "langue": "$6", "complet": $3, "validant": $4, "rejuge": $5,
 "cas": [{"id": "c1", "verifications": [{"critere": "a", "ok": true}, {"critere": "b", "ok": false}, {"critere": "i", "ok": false, "indicateur": true}]}]}
EOF
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
sur_branche feat/detache; valide tools/outil.sh trois "code"; git checkout -q --detach
lance
code_et "code 3 : tête détachée" 3 "finish_branch : aucune branche à terminer"
SORTIE=$(cd "$tmp" && bash "$script" 2>&1); CODE=$?
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
code_et "code 5 : dossier du change touché avec du code, autre nom de branche" 5 "finish_branch : change OpenSpec non archivé"
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
SORTIE=$(PATH="$cas/faux:$PATH" bash "$travail/tools/finish_branch.sh" 2>&1); CODE=$?
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

# --- le script ne remet à zéro ni ne nettoie le dossier d'exécution
grep -v '^[[:space:]]*#' "$script" | grep -E -e 'git +clean|git -C [^ ]+ +(reset|clean|stash|checkout)|worktree +(remove|prune|add)|run_worktree.sh +(create|remove)' >/dev/null
[ $? -ne 0 ]; SORTIE="remise à zéro ou nettoyage du dossier d'exécution trouvé"; verifie "aucune remise à zéro ni nettoyage du dossier d'exécution dans le script" $?

# --- le script n'emploie aucune commande interdite
grep -v '^[[:space:]]*#' "$script" | grep -E -e '--force|push -f|--no-verify|branch -D|rebase |PMZILLA_SKIP_GREEN_CHECK=|posture_evals' >/dev/null
[ $? -ne 0 ]; SORTIE="commande interdite trouvée"; verifie "aucune commande interdite dans le script (force, rebase, -D, --no-verify, jeu d'essai)" $?

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
