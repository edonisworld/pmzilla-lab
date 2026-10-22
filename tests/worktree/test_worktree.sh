#!/bin/bash
# Test du script de worktree (tools/worktree.sh) : dépôts Git temporaires, liste des noms sensibles factice.
# Change lab-folder-layout (D2, D3) : le dossier par défaut est <dossier des worktrees>/wt-<branche>, le dossier des worktrees étant celui du
# dossier du lab (le parent de l'espace de travail temporaire) ou PMZILLA_LAB_WORKTREES ; il est créé après les contrôles (code 5 si impossible).
# Cas : branche neuve, branche existante, dossier par défaut dans le dossier des worktrees, réglage local avec les deux variables
# et les deux lignes export, liste sans droit de lecture (le worktree est créé quand même), liste absente (3), dossier existant
# et branche ouverte ailleurs (4), réglage local non ignoré (5), aucun argument (2), aucun contenu de la liste dans la sortie.
# Change mothra-npm-ready (D1, D2, D5) : offre de npm ci --offline quand mothra/package-lock.json existe, avec un faux npm
# (WORKTREE_NPM) et un terminal simulé (WORKTREE_TERMINAL) : sans verrou, terminal oui, non ou vide, sans terminal, npm en échec.
# Jamais le vrai espace de travail ni sa vraie liste. Lancement à la main : bash tests/worktree/test_worktree.sh </dev/null
set -u
script="$(cd "$(dirname "$0")/../../tools" && pwd)/worktree.sh"
tmp=$(mktemp -d) || exit 1
trap 'chmod -R u+rwX "$tmp" 2>/dev/null; rm -rf "$tmp"' EXIT
export GIT_CONFIG_GLOBAL="$tmp/gitconfig" GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0
unset PMZILLA_LAB_WORKTREES   # la variable du vrai lab ne doit pas décider de la destination des cas
git config --global user.email t@example.org
git config --global user.name test
git config --global init.defaultBranch main
ok=0; ko=0; n=0
SECRET="valeur-factice-q7x"

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
nouveau() { # $1 = "ignore" (défaut) ou "non" : espace de travail temporaire dans $tmp/casN/espace
  n=$((n+1)); cas="$tmp/cas$n"; ws="$cas/espace"
  mkdir -p "$ws/Flux-Lab"; git init -q "$ws"; cd "$ws" || exit 1
  echo base > f.txt
  [ "${1:-ignore}" = "ignore" ] && printf '.claude/settings.local.json\n' > .gitignore
  printf '%s\n' "$SECRET" > Flux-Lab/noms-sensibles.txt
  printf 'Flux-Lab/\n' >> .git/info/exclude
  git add -A; git commit -q -m initial
  liste="$ws/Flux-Lab/noms-sensibles.txt"
}
lance() { SORTIE=$(bash "$script" "$@" 2>&1 </dev/null); CODE=$?; }
nb_worktrees() { git -C "$ws" worktree list | wc -l | tr -d ' '; }

# --- aucun argument
nouveau; lance
code_et "sans argument : code 2 et usage" 2 "usage"
[ "$(nb_worktrees)" -eq 1 ]; verifie "sans argument : rien n'est créé" $?

# --- branche neuve, dossier par défaut dans le dossier des worktrees (D2 ; ex-défaut « à côté de l'espace », changé par la décision Q1 à Q3)
nouveau; lance feat/ma-branche
dossier="$cas/worktrees/wt-feat-ma-branche"
code_et "branche neuve : code 0 et message de création" 0 "worktree : créé"
# Chemin résolu (pwd -P) : Git donne le dossier commun résolu (/private/var/... pour un dossier temporaire de macOS), pas le chemin de mktemp.
contient "worktree : dossier des worktrees créé : $(cd -P "$cas" && pwd -P)/worktrees"; verifie "dossier des worktrees absent : créé, avec sa ligne (D3)" $?
[ "$(printf '%s\n' "$SORTIE" | grep -n 'dossier des worktrees créé' | cut -d: -f1)" -lt "$(printf '%s\n' "$SORTIE" | grep -n 'worktree : créé' | cut -d: -f1)" ]
verifie "la ligne de création du dossier précède la ligne de création du worktree" $?
[ ! -e "$cas/wt-feat-ma-branche" ]; verifie "rien n'est créé à côté de l'espace de travail" $?
contient "$dossier"; verifie "branche neuve : le message donne le dossier" $?
contient "feat/ma-branche"; verifie "branche neuve : le message donne la branche" $?
[ -d "$dossier" ]; verifie "dossier par défaut : wt-<branche avec / remplacé par -> dans le dossier des worktrees" $?
[ "$(git -C "$dossier" rev-parse --abbrev-ref HEAD)" = "feat/ma-branche" ]; verifie "branche neuve : le worktree est sur la nouvelle branche" $?
[ "$(git -C "$dossier" rev-parse HEAD)" = "$(git -C "$ws" rev-parse main)" ]; verifie "branche neuve : créée depuis main" $?
reglage="$dossier/.claude/settings.local.json"
[ -f "$reglage" ] && grep -qF "\"PMZILLA_LAB_SENSITIVE_NAMES\": \"$liste\"" "$reglage" && grep -qF "\"PMZILLA_NOMS\": \"$liste\"" "$reglage"
SORTIE="$(cat "$reglage" 2>&1)"; verifie "réglage local : les deux variables portent le chemin absolu de la liste" $?
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert set(d["env"])=={"PMZILLA_LAB_SENSITIVE_NAMES","PMZILLA_NOMS"}' "$reglage"
verifie "réglage local : JSON valide avec un bloc env" $?
lance_sortie=$SORTIE
SORTIE=$(bash "$script" feat/autre 2>&1 </dev/null)
! contient "dossier des worktrees créé"; verifie "dossier des worktrees déjà là : pas de ligne de création" $?
contient "export PMZILLA_LAB_SENSITIVE_NAMES=" && contient "export PMZILLA_NOMS="; verifie "sortie : les deux lignes export" $?
contient "cd " && contient "claude"; verifie "sortie : la commande qui ouvre la session dans le dossier" $?
! contient "$SECRET"; verifie "sortie : aucun contenu de la liste" $?
git -C "$dossier" status --porcelain | grep -q settings.local; [ $? -ne 0 ]; verifie "réglage local ignoré par Git (rien à indexer)" $?
[ -z "$(git -C "$ws" log --all --oneline | grep -v initial)" ]; verifie "aucun commit créé par le script" $?

# --- branche existante
nouveau; git branch existante; lance existante
code_et "branche existante : code 0" 0 "worktree : créé"
[ "$(git -C "$cas/worktrees/wt-existante" rev-parse --abbrev-ref HEAD)" = "existante" ]; verifie "branche existante : récupérée telle quelle" $?

# --- dossier donné, lancé depuis un worktree
nouveau; lance un "$cas/autre-dossier"
code_et "dossier donné : code 0" 0 "$cas/autre-dossier"
[ ! -e "$cas/worktrees" ] && ! contient "dossier des worktrees"; verifie "dossier donné : le dossier des worktrees n'est ni créé ni mentionné" $?
SORTIE=$(cd "$cas/autre-dossier" && bash "$script" deux 2>&1 </dev/null); CODE=$?
code_et "lancé depuis un worktree : code 0" 0 "worktree : créé"
[ -d "$cas/worktrees/wt-deux" ] && [ ! -e "$cas/autre-dossier/wt-deux" ] && grep -qF "$liste" "$cas/worktrees/wt-deux/.claude/settings.local.json"
verifie "lancé depuis un worktree : dossier des worktrees du lab (pas à côté du worktree), chemin de la liste de l'espace" $?

# --- variable PMZILLA_LAB_WORKTREES : dossier voulu, tilde développé, relatif rendu absolu ; jamais le dossier des worktrees du lab
nouveau; SORTIE=$(PMZILLA_LAB_WORKTREES="$cas/arbres" bash "$script" par-variable 2>&1 </dev/null); CODE=$?
code_et "variable posée : code 0 et dossier créé" 0 "worktree : dossier des worktrees créé : $cas/arbres"
[ -d "$cas/arbres/wt-par-variable" ] && [ ! -e "$cas/worktrees" ]; verifie "variable posée : le worktree est dans le dossier de la variable" $?
nouveau; mkdir -p "$cas/maison"; SORTIE=$(HOME="$cas/maison" PMZILLA_LAB_WORKTREES="~/arbres" bash "$script" tilde 2>&1 </dev/null); CODE=$?
code_et "variable avec tilde : code 0" 0 "worktree : créé"
[ -d "$cas/maison/arbres/wt-tilde" ]; verifie "variable avec tilde : tilde développé" $?
nouveau; SORTIE=$(PMZILLA_LAB_WORKTREES="relatif" bash "$script" rel 2>&1 </dev/null); CODE=$?   # le dossier courant est l'espace de travail
code_et "variable relative : code 0" 0 "worktree : créé"
[ -d "$ws/relatif/wt-rel" ] && [ ! -e "$cas/worktrees" ]; verifie "variable relative : rendue absolue depuis le dossier courant" $?

# --- dossier des worktrees impossible à créer (D3) : code 5, rien n'est créé
nouveau; chmod 555 "$cas"; lance sans-droit; chmod 755 "$cas"
code_et "dossier des worktrees impossible à créer : code 5 et phrase" 5 "dossier des worktrees impossible à créer"
[ "$(nb_worktrees)" -eq 1 ] && [ ! -e "$cas/worktrees" ] && ! git -C "$ws" rev-parse -q --verify refs/heads/sans-droit >/dev/null
verifie "création impossible : ni branche ni worktree ni dossier" $?
contient "rien n'est créé"; verifie "création impossible : la phrase dit que rien n'est créé" $?

# --- liste sans droit de lecture
nouveau; chmod 000 "$liste"; lance illisible
code_et "liste illisible : le worktree est créé quand même" 0 "worktree : créé"
chmod 644 "$liste"

# --- liste absente
nouveau; rm "$liste"; lance sans-liste
code_et "liste absente : code 3" 3 "liste des noms sensibles absente"
[ "$(nb_worktrees)" -eq 1 ] && [ ! -e "$cas/worktrees" ] && ! git -C "$ws" rev-parse -q --verify refs/heads/sans-liste >/dev/null
verifie "liste absente : rien n'est créé (ni dossier des worktrees ni branche)" $?

# --- dossier existant
nouveau; mkdir -p "$cas/worktrees/wt-pris"; lance pris
code_et "dossier existant : code 4" 4 "existe déjà"
[ "$(nb_worktrees)" -eq 1 ] && ! git -C "$ws" rev-parse -q --verify refs/heads/pris >/dev/null; verifie "dossier existant : liste des worktrees inchangée, pas de branche" $?

# --- branche ouverte ailleurs
nouveau; git worktree add -q -b ouverte "$cas/ailleurs"; lance ouverte
code_et "branche ouverte ailleurs : code 4 et dossier nommé" 4 "$cas/ailleurs"
[ "$(nb_worktrees)" -eq 2 ] && [ ! -e "$cas/worktrees" ]; verifie "branche ouverte ailleurs : rien n'est créé (pas même le dossier des worktrees)" $?

# --- réglage local non ignoré
nouveau non; lance neuf
code_et "réglage non ignoré : code 5" 5 "pas ignoré"
[ "$(nb_worktrees)" -eq 1 ] && [ ! -e "$cas/worktrees" ]; verifie "réglage non ignoré : rien n'est créé ni écrit" $?

# --- dépendances npm de Mothra (mothra-npm-ready, D1, D2, D5) : faux npm qui note son dossier et ses arguments et refuse tout
# sauf « ci --offline » ; le terminal est simulé par WORKTREE_TERMINAL (tâche 2.1), la réponse donnée sur l'entrée standard.
faux_npm="$tmp/faux-npm"
printf '#!/bin/sh\nprintf "%%s|%%s\\n" "$(pwd -P)" "$*" >> "$FAUX_NPM_JOURNAL"\n[ "$*" = "ci --offline" ] || exit 97\nexit "${FAUX_NPM_CODE:-0}"\n' > "$faux_npm"
chmod 755 "$faux_npm"
avec_verrou() { mkdir -p mothra; printf '{}\n' > mothra/package-lock.json; git add -A; git commit -q -m verrou; }
npm_lance() { # $1 = valeur de WORKTREE_TERMINAL (vide : non posée), $2 = réponse, $3 = branche
  journal_npm="$cas/npm.log"; : > "$journal_npm"
  if [ -n "$1" ]; then
    SORTIE=$(printf '%s\n' "$2" | WORKTREE_TERMINAL="$1" WORKTREE_NPM="$faux_npm" FAUX_NPM_JOURNAL="$journal_npm" bash "$script" "$3" 2>&1); CODE=$?
  else
    SORTIE=$(printf '%s\n' "$2" | env -u WORKTREE_TERMINAL WORKTREE_NPM="$faux_npm" FAUX_NPM_JOURNAL="$journal_npm" bash "$script" "$3" 2>&1); CODE=$?
  fi
}
QUESTION="dépendances npm de Mothra : lancer npm ci --offline dans mothra/ depuis le cache local ? [o/N]"
SUCCES="dépendances npm de Mothra installées depuis le cache local"

nouveau; npm_lance 1 o sans-verrou
code_et "sans verrou de Mothra : code 0" 0 "worktree : créé"
! contient "npm" && [ ! -s "$journal_npm" ]; verifie "sans verrou : aucune question, aucune ligne npm, aucun appel" $?

nouveau; avec_verrou; npm_lance 1 o oui
dossier="$(cd -P "$cas" && pwd -P)/worktrees/wt-oui"
code_et "verrou et terminal, oui : code 0 et ligne de succès" 0 "$SUCCES"
contient "$QUESTION"; verifie "terminal : la question exacte est posée" $?
SORTIE="journal npm : $(cat "$journal_npm")"; [ "$(cat "$journal_npm")" = "$dossier/mothra|ci --offline" ]
verifie "oui : un seul appel, exactement « ci --offline », dans mothra/ du worktree" $?

nouveau; avec_verrou; npm_lance 1 n non
code_et "terminal, non : code 0 et commande affichée" 0 "npm ci --offline"
contient "cd $(cd -P "$cas" && pwd -P)/worktrees/wt-non/mothra && npm ci --offline" || contient "cd $cas/worktrees/wt-non/mothra && npm ci --offline"
verifie "non : la commande à taper nomme mothra/ du worktree" $?
[ ! -s "$journal_npm" ] && ! contient "$SUCCES"; verifie "non : aucun appel de npm" $?

nouveau; avec_verrou; npm_lance 1 "" vide
[ ! -s "$journal_npm" ] && contient "npm ci --offline"; verifie "terminal, réponse vide (N par défaut) : commande affichée, aucun appel" $?

nouveau; avec_verrou; npm_lance 0 o sans-terminal
code_et "sans terminal : code 0 et ligne « non installées »" 0 "dépendances npm de Mothra non installées : cd "
contient "/worktrees/wt-sans-terminal/mothra && npm ci --offline"; verifie "sans terminal : la ligne donne la commande exacte" $?
! contient "$QUESTION" && [ ! -s "$journal_npm" ]; verifie "sans terminal : aucune question, aucun appel, même avec « o » sur l'entrée" $?

nouveau; avec_verrou; npm_lance "" o non-pose   # entrée standard en tube : [ -t 0 ] faux
! contient "$QUESTION" && [ ! -s "$journal_npm" ] && contient "dépendances npm de Mothra non installées"
verifie "variable non posée et entrée en tube : pas un terminal, aucun appel" $?

nouveau; avec_verrou; FAUX_NPM_CODE=1; export FAUX_NPM_CODE; npm_lance 1 o echec; unset FAUX_NPM_CODE
code_et "npm en échec : code 0 inchangé et ligne d'échec nommée" 0 "npm ci --offline en échec (code 1) : cache local incomplet ? lancer npm ci dans mothra/ avec le réseau, geste de l'auteur"
[ -d "$cas/worktrees/wt-echec/mothra" ] && [ "$(git -C "$cas/worktrees/wt-echec" rev-parse --abbrev-ref HEAD)" = "echec" ]
verifie "npm en échec : le worktree est gardé" $?
[ "$(wc -l < "$journal_npm" | tr -d ' ')" -eq 1 ] && ! contient "$SUCCES"; verifie "npm en échec : un seul appel, jamais de nouvel essai, pas de ligne de succès" $?

SORTIE="sous-commande npm interdite"; ! grep -v '^[[:space:]]*#' "$script" | grep -qE 'npm (install|audit|i )|npx'
verifie "le script n'appelle ni npm install, ni npm audit, ni npx" $?
SORTIE="npm lancé autrement que par « \"\$npm\" ci --offline »"
[ "$(grep -v '^[[:space:]]*#' "$script" | grep -cF '"$npm"')" -ge 1 ] && ! grep -v '^[[:space:]]*#' "$script" | grep -F '"$npm"' | grep -qvF '"$npm" ci --offline'
verifie "le script ne lance npm que par « ci --offline »" $?

# --- le script ne lit ni ne copie la liste
SORTIE="lecture de la liste trouvée"   # posée avant le contrôle : une affectation remettrait $? à 0
! grep -v '^[[:space:]]*#' "$script" | grep -E 'cat |<[[:space:]]*"?\$|cp |ln |source |\. "' | grep -qi 'noms\|liste'
verifie "le script ne lit, copie ni ne lie la liste" $?
SORTIE="commande interdite"
! grep -v '^[[:space:]]*#' "$script" | grep -qE 'git (push|merge|commit)|run_all'
verifie "le script ne pousse, ne fusionne, ne valide ni ne lance les tests" $?

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
