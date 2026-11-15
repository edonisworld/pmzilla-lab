#!/bin/bash
# PMZilla Lab : enveloppe figée de l'outil de la file de travail (niveau 2 du bac à sable, design D4, D12 ; tâches 7.2, 7.3, 7.8 ; R-20261109-09, -12).
#
#     /bin/bash --noprofile --norc -p <dossier personnel>/.pmzilla-lab/outils-figes/gh_issue.sh <sous-commande> [options]
#
# Appelée par la session elle-même, seule dans son appel Bash. Contrôles, après celui du relevé des empreintes (97) :
#  - la sous-commande est dans la liste fermée SOUS_COMMANDES (celles de tools/gh_issue.py, plus les lectures `view` et `list`) : sinon 96 ;
#  - `--body-file`, `--comment-file` et `--description-file` (fichiers dont le texte part vers GitHub) doivent nommer un fichier du dossier
#    temporaire des sessions (scratchpad) ou du dossier des fichiers d'étape de l'auteur ; `--sortie` (le JSON des lectures `view` et `list`)
#    seulement un fichier du scratchpad : sinon 96, ligne « argument refusé : <option> », sans la valeur ;
#  - une option qui n'est qu'un préfixe d'une de ces quatre options (l'analyse des arguments de l'outil accepte les abréviations) est refusée
#    de la même façon sous le nom complet : l'abréviation ne contourne pas le contrôle du fichier.
# Le script figé tourne avec un environnement fermé (la variable qui désigne le programme `gh` n'y passe jamais), depuis le dossier des copies figées.
# Trois variables lui sont posées ici (celles de la session ne passent jamais) : PMZILLA_GH_ISSUE_RACINE, le dépôt sur lequel porte la commande (le dossier
# courant physique s'il est le workspace ou un worktree inscrit par lui, sinon le workspace de dossiers.conf), et les dossiers permis aux fichiers lus
# (scratchpad et fichiers d'étape) et au fichier écrit (scratchpad seulement) : l'outil rouvre alors chaque fichier sans suivre de lien et le contrôle sur son
# descripteur (ordinaire, un seul lien physique, à l'utilisateur, sous un dossier permis).
# Liste SOUS_COMMANDES : source = le parseur de tools/gh_issue.py ; un écart est détecté par un test de la suite outils_figes qui compare les deux.
# Remplace : l'appel direct de tools/gh_issue.py et les lectures gh issue view et gh issue list de la session. Retrait : avec le bac à sable.
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

SOUS_COMMANDES="new-feature edit status block unblock comment reopen-step sync-tasks close-step new-task set-owner edit-task close-feature \
detach-sub-issue new-idea edit-idea comment-idea close-idea reopen-idea reopen-feature promote-idea attach-sub-issue sub-issues horizon \
edit-milestone ensure-labels ensure-milestone view list"
OPTIONS_FICHIER_TEXTE="--body-file --comment-file --description-file"
OPTION_SORTIE="--sortie"

fige_verifier gh_issue.sh enveloppe.sh dossiers.conf copie/tools/gh_issue.py copie/tools/roadmap_model.py copie/tools/sensitive_names.py \
  copie/tools/identifiants_personnels.py copie/tools/lab_paths.py copie/tools/roadmap_settings.yaml
fige_conf_controle

sous=${1-}
# shellcheck disable=SC2086
fige_dans_liste "$sous" $SOUS_COMMANDES || fige_sous_refusee "$sous"
shift

scratchpad=$(fige_conf_exige scratchpad) || exit 97
etapes=$(fige_conf_exige etapes) || exit 97

# fige_controle_fichier <option complète> <valeur> : 0 si le fichier est permis pour cette option.
fige_controle_fichier() {
  case "$1" in
    "$OPTION_SORTIE") fige_sous "$2" "$scratchpad" ;;
    *) fige_sous "$2" "$scratchpad" || fige_sous "$2" "$etapes" ;;
  esac
}

# fige_option_fichier <nom saisi> : écrit le nom complet de l'option de fichier que ce nom désigne (exact ou préfixe), sinon rien.
fige_option_fichier() {
  local nom=$1 complet
  [ "${#nom}" -ge 3 ] || return 0
  for complet in $OPTIONS_FICHIER_TEXTE $OPTION_SORTIE; do
    if [ "$nom" = "$complet" ]; then printf '%s' "$complet"; return 0; fi
  done
  [ "$nom" = "--body" ] && return 0        # une option réelle (texte de l'idée), sans fichier
  for complet in $OPTIONS_FICHIER_TEXTE $OPTION_SORTIE; do
    case "$complet" in "$nom"*) printf '%s' "$complet"; return 0 ;; esac
  done
  return 0
}

reste=()
while [ $# -gt 0 ]; do
  jeton=$1
  if [ "$jeton" = "--" ]; then
    reste+=("$@")
    break
  fi
  complet=""
  nom=""
  case "$jeton" in --*) nom=${jeton%%=*}; complet=$(fige_option_fichier "$nom") ;; esac
  if [ -n "$complet" ]; then
    case "$jeton" in
      *=*) valeur=${jeton#*=}; forme_egal=1; shift ;;
      *) [ $# -ge 2 ] || fige_arg_refuse "$complet"; valeur=$2; forme_egal=0; shift 2 ;;
    esac
    fige_controle_fichier "$complet" "$valeur" || fige_arg_refuse "$complet"
    if [ "$forme_egal" = 1 ]; then reste+=("$nom=$valeur"); else reste+=("$nom" "$valeur"); fi
    continue
  fi
  reste+=("$jeton")
  shift
done

fige_env
workspace=$(fige_conf_exige workspace) || exit 97
racine=$(fige_physique "$workspace") || fige_97 dossiers.conf
courant=$(pwd -P 2>/dev/null) || courant=""
if [ -n "$courant" ] && { [ "$courant" = "$racine" ] || fige_worktree_valide "$courant"; }; then racine=$courant; fi
base_scratch=$(fige_physique "$scratchpad") || fige_97 dossiers.conf
base_etapes=$(fige_physique "$etapes") || fige_97 dossiers.conf
ENV_FIGE+=("PMZILLA_GH_ISSUE_RACINE=$racine" "PMZILLA_GH_ISSUE_BASES_LECTURE=$base_scratch:$base_etapes" "PMZILLA_GH_ISSUE_BASES_SORTIE=$base_scratch")
cd -P -- "$FIGES/copie" 2>/dev/null || fige_97 copie
exec /usr/bin/env -i "${ENV_FIGE[@]}" uv run --script "$FIGES/copie/tools/gh_issue.py" "$sous" ${reste[@]+"${reste[@]}"}
