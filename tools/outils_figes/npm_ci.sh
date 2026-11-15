#!/bin/bash
# PMZilla Lab : enveloppe figée de l'installation des dépendances d'un worktree (niveau 2 du bac à sable, design D4, D5, D12 ; R-20261110-24, voie (c) de la question 14).
#
#     bash ~/.pmzilla-lab/outils-figes/npm_ci.sh <chemin absolu d'un worktree>
#
# Sous le bac à sable, la règle deny sur `npm ci` reste entière (elle ne change pas) : la session ne lance plus cette commande elle-même. Cette enveloppe est
# la seule voie, et ne fait rien d'autre :
#  - exactement un argument, le chemin ABSOLU d'un worktree, sans « . », « .. », caractère de contrôle ni barre finale ; il est validé par
#    fige_worktree_valide (enveloppe.sh) : inscrit par le dépôt de dossiers.conf (clé `workspace`) et situé EXACTEMENT un niveau sous le dossier des
#    worktrees (R-20261110-29 Q2) ; sinon 96, ligne « argument refusé : chemin » (aucune ligne ne reprend le chemin) ;
#  - le worktree doit porter un dossier `mothra` qui n'est pas un lien, et l'enveloppe s'y trouve vraiment après s'y être placée ; sinon 96, ligne
#    « argument refusé : dossier » ;
#  - l'enveloppe lance exactement `npm ci --offline --ignore-scripts` dans ce dossier, sans autre option ni autre programme (aucun git lancé : la
#    validation du chemin est une lecture de fichiers), sous `env -i` avec l'environnement fermé de fige_env ; le code de npm est rendu tel quel ;
#  - le relevé des empreintes est contrôlé d'abord (97).
# Codes (tableau de enveloppe.sh, D12) : 0 et le code de npm ; 96 argument refusé ; 97 empreinte différente de son relevé. Aucun code nouveau.
# PATH fermé : celui de fige_env, plus, juste après le dossier .local/bin de la maison, le dossier de l'alias par défaut de fnm de la maison (R-20261110-25) ; les autres enveloppes ne l'ont pas.
# Décision ferme (R-20261110-29 Q1) : npm_ci.sh reste sous le bac à sable, sans exclusion par le fichier géré ; aucune exclusion future sans décision de
# l'auteur et sans reprendre les contrôles de la garde npm (dont .npmrc, verrou de paquets, arbre propre, fin en cours) ; TMPDIR à vérifier pendant la répétition.
# Remplace : `npm ci` lancé par la session dans un worktree (règle deny de .claude/deny/30-npm-npx.txt, inchangée). Retrait : avec le bac à sable.
# R-20261111-13, -15 : première instruction, avant tout nom de commande (une fonction exportée ou BASH_ENV ne doit rien exécuter ici). Relance sous `env -i`
# (rien de la session ne passe) par /bin/bash --noprofile --norc ; le marqueur est le PID, conservé par exec. Limite réelle (R-20261111-19 à -22, -23) :
# le marqueur se forge par un exec qui garde le PID, et une fonction exportée `exec` ou `unset` détourne la relance ; seule la garde de session ferme
# ces formes, jusqu'à la forme `/bin/bash -p --noprofile --norc`.
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

fige_verifier npm_ci.sh enveloppe.sh dossiers.conf
fige_conf_controle

[ $# -eq 1 ] || fige_arg_refuse chemin
arg=$1
case "$arg" in /*) ;; *) fige_arg_refuse chemin ;; esac
case "$arg" in *[[:cntrl:]]*) fige_arg_refuse chemin ;; esac
case "$arg/" in */../*|*/./*|*//*) fige_arg_refuse chemin ;; esac
phys=$(fige_physique "$arg") || fige_arg_refuse chemin
[ -n "$phys" ] || fige_arg_refuse chemin

maison=$(fige_conf_exige maison) || exit 97

# Un worktree inscrit par le dépôt et situé EXACTEMENT un niveau sous le dossier des worktrees (R-20261110-29 Q2) ; ni le dépôt principal ni un dossier ailleurs.
fige_worktree_valide "$arg" || fige_arg_refuse chemin

{ [ -d "$phys/mothra" ] && [ ! -L "$phys/mothra" ]; } || fige_arg_refuse dossier
cd -P -- "$phys/mothra" 2>/dev/null || fige_arg_refuse dossier
[ "$(pwd -P)" = "$phys/mothra" ] || fige_arg_refuse dossier

fige_env
# PATH fermé de cette enveloppe seulement : l'alias par défaut de fnm du compte, calculé depuis la maison de dossiers.conf, jamais écrit en dur ; le
# FNM_DIR de la session est ignoré. Placé juste après le dossier .local/bin de la maison, avant les dossiers système : c'est le npm de fnm qui est voulu.
ENV_FIGE[0]="PATH=$maison/.local/bin:$maison/.local/share/fnm/aliases/default/bin:${ENV_FIGE[0]#"PATH=$maison/.local/bin:"}"
exec /usr/bin/env -i "${ENV_FIGE[@]}" npm ci --offline --ignore-scripts
