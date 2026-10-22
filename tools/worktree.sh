#!/bin/bash
# Crée un worktree Git de l'espace de travail pour une branche, dans le dossier des worktrees du lab, et donne à la session qui y travaillera
# le chemin de la liste des noms sensibles de l'espace (réglage local ignoré par Git + lignes export affichées).
#
#     bash tools/worktree.sh <branche> [<dossier>]
#
# Lancé depuis l'espace de travail ou depuis un de ses worktrees. Dossier par défaut : <dossier des worktrees>/wt-<branche, / remplacé par ->,
# le dossier des worktrees étant `worktrees` sous le dossier du lab, ou PMZILLA_LAB_WORKTREES (lab-folder-layout, D1 à D3) ; il est créé
# après les contrôles quand il manque (code 5 si impossible). Un dossier donné en second argument n'utilise ni ne crée le dossier des worktrees.
# Une branche existante est reprise telle quelle ; une branche neuve part de main.
# Codes : 0 créé ; 2 usage ; 3 liste des noms sensibles absente ; 4 dossier existant ou branche déjà ouverte ailleurs ;
#         5 commande Git en échec, dossier des worktrees impossible à créer ou réglage local non ignoré par Git.
# Les contrôles se font avant tout changement.
# Dépendances npm de Mothra (mothra-npm-ready, D1, D2) : quand le worktree créé porte mothra/package-lock.json, sur un terminal, la
# question « lancer npm ci --offline dans mothra/ depuis le cache local ? [o/N] » ; o lance `npm ci --offline` dans <worktree>/mothra
# (succès ou échec en une ligne nommée, worktree gardé, code 0 inchangé) ; toute autre réponse, ou une entrée standard qui n'est pas
# un terminal (lancement depuis une session), affiche la commande à taper, sans rien lancer. Jamais npm sans --offline, jamais
# npm install, npm audit ni npx. Variables (pour les tests) : WORKTREE_NPM remplace la commande npm ; WORKTREE_TERMINAL=1 ou 0
# force l'entrée standard à valoir terminal ou non (non posée : test [ -t 0 ]).
# Interdit au script : ouvrir, lire, copier ou lier la liste (test d'existence seulement), écrire son chemin dans un fichier suivi,
# pousser, fusionner, valider, lancer les tests.
#
# Exemple :
#     bash tools/worktree.sh feat/ma-branche
set -u

# Module partagé des chemins du lab, pris dans le dossier de ce script ; seule sa fonction lab_paths_worktrees_folder est appelée
# (jamais lab_paths_init : la racine de contenu est celle de l'espace trouvé par Git depuis le dossier courant, pas celle de ce dépôt).
. "$(cd "$(dirname "$0")" && pwd)/lab_paths.sh"

NOM="worktree"
PRINCIPALE="main"
LISTE_RELATIVE="Flux-Lab/noms-sensibles.txt"
REGLAGE_RELATIF=".claude/settings.local.json"

usage() { echo "usage : bash tools/worktree.sh <branche> [<dossier>]" >&2; exit 2; }
refuse() { echo "$NOM : $2" >&2; exit "$1"; }

[ $# -ge 1 ] && [ $# -le 2 ] && [ -n "$1" ] || usage
branche=$1

commun=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || refuse 5 "git a échoué : git rev-parse --git-common-dir"
espace=$(dirname "$commun")

[ -f "$espace/$LISTE_RELATIVE" ] || refuse 3 "liste des noms sensibles absente de l'espace de travail ; rien n'est créé"
liste="$espace/$LISTE_RELATIVE"

dossier_des_worktrees=""
if [ $# -eq 2 ]; then
  dossier=$2
  case "$dossier" in /*) ;; *) dossier="$(pwd)/$dossier" ;; esac
else
  dossier_des_worktrees=$(lab_paths_worktrees_folder "$espace")
  case "$dossier_des_worktrees" in /*) ;; *) dossier_des_worktrees="$(pwd)/$dossier_des_worktrees" ;; esac
  dossier="$dossier_des_worktrees/wt-${branche//\//-}"
fi
[ -e "$dossier" ] && refuse 4 "$dossier existe déjà"

ailleurs=$(git -C "$espace" worktree list --porcelain | awk -v b="refs/heads/$branche" '/^worktree /{d=substr($0,10)} $1=="branch" && $2==b {print d; exit}')
[ -n "$ailleurs" ] && refuse 4 "la branche $branche est déjà ouverte dans $ailleurs"

git -C "$espace" check-ignore -q "$REGLAGE_RELATIF" || refuse 5 "le réglage local n'est pas ignoré par Git ; rien n'est écrit"

if [ -n "$dossier_des_worktrees" ] && [ ! -d "$dossier_des_worktrees" ]; then
  mkdir -p "$dossier_des_worktrees" 2>/dev/null || refuse 5 "dossier des worktrees impossible à créer : $dossier_des_worktrees ; rien n'est créé"
  echo "$NOM : dossier des worktrees créé : $dossier_des_worktrees"
fi

if git -C "$espace" show-ref --verify --quiet "refs/heads/$branche"; then
  git -C "$espace" worktree add -q "$dossier" "$branche" >/dev/null 2>&1 || refuse 5 "git a échoué : git worktree add $dossier $branche"
else
  git -C "$espace" worktree add -q -b "$branche" "$dossier" "$PRINCIPALE" >/dev/null 2>&1 || refuse 5 "git a échoué : git worktree add -b $branche $dossier $PRINCIPALE"
fi

echappe=${liste//\\/\\\\}; echappe=${echappe//\"/\\\"}
mkdir -p "$dossier/.claude" || refuse 5 "git a échoué : écriture de $dossier/.claude"
printf '{\n  "env": {\n    "PMZILLA_LAB_SENSITIVE_NAMES": "%s",\n    "PMZILLA_NOMS": "%s"\n  }\n}\n' "$echappe" "$echappe" > "$dossier/$REGLAGE_RELATIF" \
  || refuse 5 "git a échoué : écriture de $dossier/$REGLAGE_RELATIF"

echo "$NOM : créé $dossier sur la branche $branche"
echo "réglage local écrit (ignoré par Git) : $dossier/$REGLAGE_RELATIF"
echo "pour un Terminal sans ce réglage :"
printf 'export PMZILLA_LAB_SENSITIVE_NAMES=%q\n' "$liste"
printf 'export PMZILLA_NOMS=%q\n' "$liste"
printf 'ouvrir la session : cd %q && claude\n' "$dossier"

# Dépendances npm de Mothra (mothra-npm-ready, D1, D2) : seulement quand le worktree porte le verrou de Mothra. Sur un terminal, une
# question ; oui lance npm ci --offline dans mothra/ depuis le cache local ; sinon, ou sans terminal, la commande à taper.
# Un échec ne change ni le worktree ni le code de sortie ; jamais le réseau, jamais une autre sous-commande npm.
if [ -f "$dossier/mothra/package-lock.json" ]; then
  npm=${WORKTREE_NPM:-npm}
  a_taper="$(printf 'cd %q && npm ci --offline' "$dossier/mothra")"
  case "${WORKTREE_TERMINAL:-}" in
    1) terminal=1 ;;
    0) terminal=0 ;;
    *) if [ -t 0 ]; then terminal=1; else terminal=0; fi ;;
  esac
  reponse=""
  if [ "$terminal" = 1 ]; then
    printf '%s ' "dépendances npm de Mothra : lancer npm ci --offline dans mothra/ depuis le cache local ? [o/N]"
    read -r reponse || reponse=""
  fi
  if [ "$terminal" = 1 ] && { [ "$reponse" = o ] || [ "$reponse" = O ]; }; then
    (cd "$dossier/mothra" && "$npm" ci --offline)
    code_npm=$?
    if [ "$code_npm" -eq 0 ]; then
      echo "dépendances npm de Mothra installées depuis le cache local"
    else
      echo "npm ci --offline en échec (code $code_npm) : cache local incomplet ? lancer npm ci dans mothra/ avec le réseau, geste de l'auteur"
    fi
  else
    echo "dépendances npm de Mothra non installées : $a_taper"
  fi
fi
exit 0
