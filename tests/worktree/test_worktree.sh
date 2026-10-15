#!/bin/bash
# Test du script de worktree (tools/worktree.sh) : dépôts Git temporaires, liste des noms sensibles factice.
# Cas : branche neuve, branche existante, dossier par défaut à côté de l'espace de travail, réglage local avec les deux variables
# et les deux lignes export, liste sans droit de lecture (le worktree est créé quand même), liste absente (3), dossier existant
# et branche ouverte ailleurs (4), réglage local non ignoré (5), aucun argument (2), aucun contenu de la liste dans la sortie.
# Jamais le vrai espace de travail ni sa vraie liste. Lancement à la main : bash tests/worktree/test_worktree.sh </dev/null
set -u
script="$(cd "$(dirname "$0")/../../tools" && pwd)/worktree.sh"
tmp=$(mktemp -d) || exit 1
trap 'chmod -R u+rwX "$tmp" 2>/dev/null; rm -rf "$tmp"' EXIT
export GIT_CONFIG_GLOBAL="$tmp/gitconfig" GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0
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

# --- branche neuve, dossier par défaut à côté de l'espace de travail
nouveau; lance feat/ma-branche
dossier="$cas/wt-feat-ma-branche"
code_et "branche neuve : code 0 et message de création" 0 "worktree : créé"
contient "$dossier"; verifie "branche neuve : le message donne le dossier" $?
contient "feat/ma-branche"; verifie "branche neuve : le message donne la branche" $?
[ -d "$dossier" ]; verifie "dossier par défaut : wt-<branche avec / remplacé par -> à côté de l'espace" $?
[ "$(git -C "$dossier" rev-parse --abbrev-ref HEAD)" = "feat/ma-branche" ]; verifie "branche neuve : le worktree est sur la nouvelle branche" $?
[ "$(git -C "$dossier" rev-parse HEAD)" = "$(git -C "$ws" rev-parse main)" ]; verifie "branche neuve : créée depuis main" $?
reglage="$dossier/.claude/settings.local.json"
[ -f "$reglage" ] && grep -qF "\"PMZILLA_LAB_SENSITIVE_NAMES\": \"$liste\"" "$reglage" && grep -qF "\"PMZILLA_NOMS\": \"$liste\"" "$reglage"
SORTIE="$(cat "$reglage" 2>&1)"; verifie "réglage local : les deux variables portent le chemin absolu de la liste" $?
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert set(d["env"])=={"PMZILLA_LAB_SENSITIVE_NAMES","PMZILLA_NOMS"}' "$reglage"
verifie "réglage local : JSON valide avec un bloc env" $?
lance_sortie=$SORTIE
SORTIE=$(bash "$script" feat/autre 2>&1 </dev/null)
contient "export PMZILLA_LAB_SENSITIVE_NAMES=" && contient "export PMZILLA_NOMS="; verifie "sortie : les deux lignes export" $?
contient "cd " && contient "claude"; verifie "sortie : la commande qui ouvre la session dans le dossier" $?
! contient "$SECRET"; verifie "sortie : aucun contenu de la liste" $?
git -C "$dossier" status --porcelain | grep -q settings.local; [ $? -ne 0 ]; verifie "réglage local ignoré par Git (rien à indexer)" $?
[ -z "$(git -C "$ws" log --all --oneline | grep -v initial)" ]; verifie "aucun commit créé par le script" $?

# --- branche existante
nouveau; git branch existante; lance existante
code_et "branche existante : code 0" 0 "worktree : créé"
[ "$(git -C "$cas/wt-existante" rev-parse --abbrev-ref HEAD)" = "existante" ]; verifie "branche existante : récupérée telle quelle" $?

# --- dossier donné, lancé depuis un worktree
nouveau; lance un "$cas/autre-dossier"
code_et "dossier donné : code 0" 0 "$cas/autre-dossier"
SORTIE=$(cd "$cas/autre-dossier" && bash "$script" deux 2>&1 </dev/null); CODE=$?
code_et "lancé depuis un worktree : code 0" 0 "worktree : créé"
[ -d "$cas/wt-deux" ] && grep -qF "$liste" "$cas/wt-deux/.claude/settings.local.json"; verifie "lancé depuis un worktree : dossier à côté de l'espace, chemin de la liste de l'espace" $?

# --- liste sans droit de lecture
nouveau; chmod 000 "$liste"; lance illisible
code_et "liste illisible : le worktree est créé quand même" 0 "worktree : créé"
chmod 644 "$liste"

# --- liste absente
nouveau; rm "$liste"; lance sans-liste
code_et "liste absente : code 3" 3 "liste des noms sensibles absente"
[ "$(nb_worktrees)" -eq 1 ] && [ ! -e "$cas/wt-sans-liste" ] && ! git -C "$ws" rev-parse -q --verify refs/heads/sans-liste >/dev/null
verifie "liste absente : rien n'est créé (ni dossier ni branche)" $?

# --- dossier existant
nouveau; mkdir "$cas/wt-pris"; lance pris
code_et "dossier existant : code 4" 4 "existe déjà"
[ "$(nb_worktrees)" -eq 1 ] && ! git -C "$ws" rev-parse -q --verify refs/heads/pris >/dev/null; verifie "dossier existant : liste des worktrees inchangée, pas de branche" $?

# --- branche ouverte ailleurs
nouveau; git worktree add -q -b ouverte "$cas/ailleurs"; lance ouverte
code_et "branche ouverte ailleurs : code 4 et dossier nommé" 4 "$cas/ailleurs"
[ "$(nb_worktrees)" -eq 2 ] && [ ! -e "$cas/wt-ouverte" ]; verifie "branche ouverte ailleurs : rien n'est créé" $?

# --- réglage local non ignoré
nouveau non; lance neuf
code_et "réglage non ignoré : code 5" 5 "pas ignoré"
[ "$(nb_worktrees)" -eq 1 ] && [ ! -e "$cas/wt-neuf" ]; verifie "réglage non ignoré : rien n'est créé ni écrit" $?

# --- le script ne lit ni ne copie la liste
grep -v '^[[:space:]]*#' "$script" | grep -E 'cat |<[[:space:]]*"?\$|cp |ln |source |\. "' | grep -i 'noms\|liste' >/dev/null
[ $? -ne 0 ]; SORTIE="lecture de la liste trouvée"; verifie "le script ne lit, copie ni ne lie la liste" $?
grep -v '^[[:space:]]*#' "$script" | grep -E 'git (push|merge|commit)|run_all' >/dev/null
[ $? -ne 0 ]; SORTIE="commande interdite"; verifie "le script ne pousse, ne fusionne, ne valide ni ne lance les tests" $?

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
