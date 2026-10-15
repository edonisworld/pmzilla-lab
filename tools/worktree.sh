#!/bin/bash
# Crée un worktree Git de l'espace de travail pour une branche, à côté de l'espace de travail, et donne à la session qui y travaillera
# le chemin de la liste des noms sensibles de l'espace (réglage local ignoré par Git + lignes export affichées).
#
#     bash tools/worktree.sh <branche> [<dossier>]
#
# Lancé depuis l'espace de travail ou depuis un de ses worktrees. Dossier par défaut : <parent de l'espace>/wt-<branche, / remplacé par ->.
# Une branche existante est reprise telle quelle ; une branche neuve part de main.
# Codes : 0 créé ; 2 usage ; 3 liste des noms sensibles absente ; 4 dossier existant ou branche déjà ouverte ailleurs ;
#         5 commande Git en échec ou réglage local non ignoré par Git.
# Les contrôles se font avant tout changement.
# Interdit au script : ouvrir, lire, copier ou lier la liste (test d'existence seulement), écrire son chemin dans un fichier suivi,
# pousser, fusionner, valider, lancer les tests.
#
# Exemple :
#     bash tools/worktree.sh feat/ma-branche
set -u

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

if [ $# -eq 2 ]; then
  dossier=$2
  case "$dossier" in /*) ;; *) dossier="$(pwd)/$dossier" ;; esac
else
  dossier="$(dirname "$espace")/wt-${branche//\//-}"
fi
[ -e "$dossier" ] && refuse 4 "$dossier existe déjà"

ailleurs=$(git -C "$espace" worktree list --porcelain | awk -v b="refs/heads/$branche" '/^worktree /{d=substr($0,10)} $1=="branch" && $2==b {print d; exit}')
[ -n "$ailleurs" ] && refuse 4 "la branche $branche est déjà ouverte dans $ailleurs"

git -C "$espace" check-ignore -q "$REGLAGE_RELATIF" || refuse 5 "le réglage local n'est pas ignoré par Git ; rien n'est écrit"

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
exit 0
