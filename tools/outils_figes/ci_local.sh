#!/bin/bash
# PMZilla Lab : enveloppe figée de la CI locale (niveau 2 du bac à sable, design D4, D10, D12 ; tâches 7.2 et 7.3 ; R-20261109-09).
#
#     /bin/bash --noprofile --norc -p <dossier personnel>/.pmzilla-lab/outils-figes/ci_local.sh run [<branche>|--index|--travail|--rejeu ...] [--worktree <dossier>] [<suite> ...]
#     /bin/bash --noprofile --norc -p <dossier personnel>/.pmzilla-lab/outils-figes/ci_local.sh places [--json]
#     (<dossier personnel> : le chemin absolu de la base des comptes, jamais `~` ; R-20261111-48)
#
# Appelée par la session elle-même, seule dans son appel Bash (pas de `cd` avant, ni `&&`, `;` ou tube, jamais depuis un script : une commande
# exclue du bac à sable ne l'est qu'au premier niveau). Elle contrôle le relevé des empreintes (code 97), la sous-commande (`run` ou `places`,
# sinon 96) et `--worktree`, puis lance la copie figée de tools/ci_local.sh, depuis le dossier qu'elle nomme, avec un environnement fermé.
# `--worktree` : un worktree existant, sous le dossier des worktrees, accepté seulement avec `run --index` et `run --travail` (sinon 96, ligne
# « argument refusé : --worktree ») ; le script figé tourne dans ce worktree, donc son gel ciblé (code 7, règle de finish_lock) est évalué
# sur lui : un worktree de la liste du verrou de fin rend 7 et rien ne tourne. Le worktree est exactement un niveau sous le dossier des worktrees et
# inscrit par le workspace (<workspace>/.git/worktrees/<nom>/gitdir contient « <chemin physique>/.git » : lecture seule, aucun git lancé).
# Sans `--worktree`, le script figé tourne dans le workspace de dossiers.conf, jamais dans le dossier courant (que la session choisit).
# L'option `--worktree` n'est pas transmise au script figé, qui ne la connaît pas.
# Codes : ceux de enveloppe.sh (96, 97) ; sinon ceux du script figé (0 à 8, 61).
# Remplace : l'appel de `bash tools/ci_local.sh run|places` depuis l'espace de travail ou un worktree. Retrait : avec le bac à sable.
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

fige_verifier ci_local.sh enveloppe.sh dossiers.conf copie/tools/ci_local.sh copie/tools/finish_lock.sh copie/tools/finish_lock.py \
  copie/tools/lab_paths.sh copie/tools/e2e_steps.sh copie/ci/passage.sh
fige_conf_controle

sous=${1-}
case "$sous" in run|places) ;; *) fige_sous_refusee "$sous" ;; esac
shift

worktree=""
a_worktree=0
a_index=0
a_travail=0
reste=()
while [ $# -gt 0 ]; do
  case "$1" in
    --worktree)
      [ $# -ge 2 ] || fige_arg_refuse --worktree
      worktree=$2; a_worktree=1; shift 2; continue ;;
    --worktree=*)
      worktree=${1#--worktree=}; a_worktree=1; shift; continue ;;
    --index) a_index=1 ;;
    --travail) a_travail=1 ;;
  esac
  reste+=("$1")
  shift
done

if [ "$a_worktree" = 1 ]; then
  if [ "$sous" != run ] || { [ "$a_index" = 0 ] && [ "$a_travail" = 0 ]; }; then fige_arg_refuse --worktree; fi
  fige_worktree_valide "$worktree" || fige_arg_refuse --worktree
fi

fige_env
if [ -n "$worktree" ]; then
  cd -P -- "$worktree" 2>/dev/null || fige_arg_refuse --worktree
else
  cd -P -- "$(fige_conf_exige workspace)" 2>/dev/null || fige_97 dossiers.conf
fi
exec /usr/bin/env -i "${ENV_FIGE[@]}" /bin/bash "$FIGES/copie/tools/ci_local.sh" "$sous" ${reste[@]+"${reste[@]}"}
