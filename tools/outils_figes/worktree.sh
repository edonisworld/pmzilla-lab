#!/bin/bash
# PMZilla Lab : enveloppe figée de la création d'un worktree (niveau 2 du bac à sable, design D4, D9, D12 ; tâches 7.5 et 7.7 ; R-20261109-12, réponse 2).
#
#     /bin/bash --noprofile --norc -p <dossier personnel>/.pmzilla-lab/outils-figes/worktree.sh add <branche> <base>
#
# Sous le bac à sable, `git worktree add` écrit des chemins refusés (commondir, gitdir, le fichier .git du worktree) : une session ne peut plus
# créer le worktree où commence une branche de travail. Cette enveloppe le crée hors du bac à sable, et ne fait rien d'autre :
#  - sous-commande `add` seulement, avec exactement deux arguments (sinon 96) ;
#  - nom de branche vide, commençant par `main`, commençant par un tiret ou invalide pour git : 96, ligne « argument refusé : branche » ;
#  - base qui n'est pas une branche locale : 96, ligne « argument refusé : base » ;
#  - la branche <branche> est créée depuis <base> et son worktree sous le dossier des worktrees, en `wt-<nom>`, <nom> étant le nom de branche
#    dont chaque `/` devient `-` (spec/exemple-n2 donne wt-spec-exemple-n2) ; dépôt : le workspace de dossiers.conf ;
#  - une branche locale qui existe déjà (R-20261110-18 Q2, -22 Q10) est reprise : le worktree est créé sur elle, sans -b, sans la recréer ni la
#    ramener sur <base> ; ouverte dans un autre worktree, git refuse et son code est rendu tel quel (aucun code ajouté) ;
#  - le réglage local du chemin de la liste des noms sensibles (`noms` de dossiers.conf, jamais ouverte : test d'existence, code 3 si absente avant
#    toute création) est posé dans .claude/settings.local.json du worktree, comme tools/worktree.sh, quand git l'ignore ; jamais à travers un lien ;
#    si le réglage n'est pas ignoré par Git, l'enveloppe crée quand même le worktree, avertit et rend 0 (l'outil du dépôt, lui, refuse en 5) ;
#  - aucun autre programme que git (et mkdir, pour ce dossier) : jamais `npm ci`, ni un script d'installation, ni un crochet écrit ici (les crochets
#    de git sont ceux du dépôt, que la session ne peut pas écrire). La session lance l'installation des dépendances par l'enveloppe figée npm_ci.sh (R-20261110-24), jamais `npm ci` elle-même sous le bac.
# Le code de git est rendu tel quel ; le relevé des empreintes est contrôlé d'abord (97).
# Ne remplace pas tools/worktree.sh, que la session ne peut plus lancer sous le bac à sable pour créer un worktree (il écrit les mêmes chemins).
# Remplace : `git worktree add` lancé par la session. Retrait : avec le bac à sable.
# R-20261111-13, -15 : première instruction, avant tout nom de commande (une fonction exportée ou BASH_ENV ne doit rien exécuter ici). Relance sous `env -i`
# (rien de la session ne passe) par /bin/bash --noprofile --norc ; le marqueur est le PID, conservé par exec. Limite réelle (R-20261111-19 à -22, -23, -38) :
# l'appel se fait dans la forme /bin/bash --noprofile --norc -p (la garde refuse l'ancien ordre `/bin/bash -p --noprofile --norc`). Sur le /bin/bash 3.2.57 du Mac,
# -p ferme BASH_ENV, ENV, les fonctions importées et SHELLOPTS (suite forme_p_mac, M1) ; CDPATH y reste suivi (constat M2) : il est tenu par la relance sous
# `env -i` ci-dessus, qui n'est précédée d'aucune commande nommée ni d'aucun `cd` (test statique), et par la garde de session. Restent à la garde : PATH, IFS,
# LANG, LC_*, et le marqueur, qui se forge par un exec qui garde le PID ; une fonction exportée `exec` ou `unset` détourne la relance.
# Remplace : rien. Retrait : permanent tant que les enveloppes sont exclues du bac à sable. Bash 3.2 (macOS) : `[[ ]]` et `$$` seulement.
if [[ ${FIGE_RELANCE-} != "$$" ]]; then
  exec /usr/bin/env -i "FIGE_RELANCE=$$" /bin/bash --noprofile --norc "$0" "$@"
fi
unset FIGE_RELANCE
case "$0" in */*) ICI=${0%/*} ;; *) ICI=. ;; esac
ICI=$(cd -P -- "$ICI" 2>/dev/null && pwd -P) || exit 97
FIGES=$ICI
if [ ! -r "$FIGES/enveloppe.sh" ]; then
  printf "outil figé : empreinte différente de son relevé, rien n'est lancé : enveloppe.sh\n" >&2
  exit 97
fi
. "$FIGES/enveloppe.sh"

fige_verifier worktree.sh enveloppe.sh dossiers.conf
fige_conf_controle

sous=${1-}
[ "$sous" = add ] || fige_sous_refusee "$sous"
[ $# -le 3 ] || fige_arg_refuse base
branche=${2-}
base=${3-}

maison=$(fige_conf_exige maison) || exit 97
workspace=$(fige_conf_exige workspace) || exit 97
worktrees=$(fige_conf_exige worktrees) || exit 97
crochets=$(fige_conf_exige crochets) || exit 97
fige_git_cfg "$crochets"

# Toute commande git tourne sous `env -i` : les variables GIT_* de la session (dossier Git, index, configuration) ne passent jamais ; la configuration de git
# est celle de fige_git_cfg (les crochets du dépôt, pas de moniteur de système de fichiers).
fige_git() { /usr/bin/env -i "PATH=/usr/bin:/bin:/usr/sbin:/sbin" "HOME=$maison" "GIT_TERMINAL_PROMPT=0" "LC_ALL=C" "${GIT_CFG[@]}" git "$@"; }

# Un nom que git développerait (`HEAD`, `@{-1}`, `main@{1}`...) n'est jamais une branche ni une base.
case "$branche" in ""|main*|-*|HEAD|*"@{"*) fige_arg_refuse branche ;; esac
fige_git check-ref-format --branch "$branche" >/dev/null 2>&1 || fige_arg_refuse branche
case "$base" in ""|-*|HEAD|*"@{"*) fige_arg_refuse base ;; esac
fige_git -C "$workspace" show-ref --verify --quiet "refs/heads/$base" || fige_arg_refuse base

noms=$(fige_conf_exige noms) || exit 97
[ -f "$noms" ] || fige_refuse 3 "liste des noms sensibles absente ; rien n'est créé"       # existence seulement : la liste n'est jamais ouverte

nom=${branche//\//-}
dossier="$worktrees/wt-$nom"
if fige_git -C "$workspace" show-ref --verify --quiet "refs/heads/$branche"; then
  # Branche locale existante : le worktree est créé sur elle, sans -b, et la branche n'est ni recréée ni ramenée sur la base. Si elle est déjà ouverte
  # dans un autre worktree, git refuse et son code est rendu tel quel.
  fige_git -C "$workspace" worktree add -- "$dossier" "$branche"
else
  fige_git -C "$workspace" worktree add -b "$branche" -- "$dossier" "refs/heads/$base"
fi
code=$?
[ "$code" -eq 0 ] || exit "$code"

# Réglage local du chemin de la liste des noms sensibles, comme tools/worktree.sh (qui refuse en 5 quand le réglage n'est pas ignoré ; ici le worktree
# existe déjà, on avertit et on rend 0) : posé seulement quand git l'ignore dans le worktree créé, jamais à
# travers un lien (ce que la branche porte dans .claude est écrit par la session) ; sinon rien n'est écrit, un avertissement, et le code reste 0.
reglage=".claude/settings.local.json"
if fige_git -C "$dossier" check-ignore -q -- "$reglage" 2>/dev/null; then
  mkdir -p -- "$dossier/.claude" 2>/dev/null
  if [ -d "$dossier/.claude" ] && [ ! -L "$dossier/.claude" ] && [ ! -L "$dossier/$reglage" ] && fige_sous "$dossier/$reglage" "$dossier"; then
    echappe=${noms//\\/\\\\}; echappe=${echappe//\"/\\\"}
    printf '{\n  "env": {\n    "PMZILLA_LAB_SENSITIVE_NAMES": "%s",\n    "PMZILLA_NOMS": "%s"\n  }\n}\n' "$echappe" "$echappe" > "$dossier/$reglage" \
      || fige_dire "réglage local non écrit"
  else
    fige_dire "réglage local non écrit : .claude n'est pas un dossier du worktree"
  fi
else
  fige_dire "réglage local non posé : $reglage n'est pas ignoré par Git"
fi
exit 0
