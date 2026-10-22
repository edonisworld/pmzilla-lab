#!/bin/sh
# Décision du chemin allégé d'une fin de branche de spécification (change light-spec-finish, design D1 à D3). Module sourcé, jamais lancé :
# tools/finish_branch.sh, tools/finish_worktree.sh et le hook tools/hooks/pre-push le chargent ; la règle n'existe qu'ici, les appelants
# n'impriment que son résultat. POSIX sh (le hook est un script sh). L'appelant pose LIGHT_FINISH_DIR (le dossier tools/ du module) avant de
# le sourcer, et se trouve dans le dépôt.
#
# Enregistrement de la validation de main : fichier pmzilla-main-validated du dossier Git commun (partagé par l'espace de travail et ses
# worktrees, hors de tout fichier suivi), une ligne par validation : <arbre><TAB><genre><TAB><date><TAB><signature>, genre « complet » ou
# « allégé », date = jour UTC de l'écriture (AAAA-MM-JJ), signature = signature d'environnement (question Q9 : condensé de 64 caractères
# hexadécimaux de python3, uv, git, bash et des dossiers du lab, calculé par « bash tools/finish_env.sh --main-signature »), ou « inconnue »
# quand elle n'a pas pu être calculée (la ligne ne donne alors jamais le chemin allégé). Ni branche, ni commit, ni chemin, ni jeton. Au plus les 50 dernières lignes. Le seul écrivain est
# tools/finish_branch.sh (record_main_validated), après un push réussi ; ce module ne l'écrit jamais autrement.
#
# Fonctions :
#   light_paths_ok <main> <sommet>   0 si au moins un chemin diffère (arbre à arbre, sans renommage) et que tous sont sous « openspec/ »
#                                    (barre comprise) avec des fichiers ordinaires seulement ; 1 sinon (hors openspec/ ou aucun chemin) ;
#                                    2 si un lien symbolique ou un sous-module existe sous openspec/ dans le sommet
#   main_validated <arbre>           écrit « ok » (code 0) ou une raison (code 1) : « arbre de main non validé », « validation de main
#                                    expirée » (plus de 7 jours, valeur fixe ; date mal formée ou future comptée expirée),
#                                    « signature d'environnement absente de la validation » (4e colonne qui n'est pas un condensé de 64 hexadécimaux),
#                                    « signature d'environnement impossible : <composant> absent ou illisible », « environnement changé
#                                    depuis la validation » (l'expiration est vue avant la signature)
#   light_decision <main> <sommet>   écrit « allégé », ou « complet<TAB><raison> » ; <main> vide = main local et distant divergents
#   light_spec_branch <main> <sommet>   0 si la branche ne change, depuis sa base commune avec main, que des chemins sous openspec/
#   light_main_ref <dossier>         écrit le plus avancé de main local et de origin/main, rien s'ils ont divergé (design D2)
#   light_suites                     écrit les suites qui lisent openspec/ (sélecteur, option --openspec-readers), séparées par des espaces ;
#                                    code 1 si le sélecteur échoue ou ne rend rien
#   env_signature                    écrit la signature d'environnement (code 0) ou « absent:<composant> » (code 1)
#   light_genre_leger                écrit le genre d'un passage allégé vert : « allégé-forcé » quand FINISH_BRANCH_LIGHT_RUNNER ou
#                                    FINISH_BRANCH_VALIDATE est non vide (faux runner), sinon « allégé » ; une ligne « allégé-forcé » donne,
#                                    dans main_validated, la raison « validation de main forcée » (jamais le chemin allégé)
#   record_main_validated <arbre> <genre>   écrit la ligne de l'enregistrement ; code 1 si l'écriture est impossible
# Lancé directement, depuis le dépôt, il écrit la décision pour le sommet courant face à main local (« allégé », ou « complet » suivi de la
# raison), sans rien écrire ni changer :
#
#     bash tools/light_finish.sh
#
# Codes de sortie : 0 décision écrite.
# Variable pour les tests : LIGHT_FINISH_TODAY (AAAA-MM-JJ), le jour de l'horloge, lue par main_validated seul ; absente, l'horloge du système.

LIGHT_DUREE_MAX=7   # jours de validité d'une validation de main (décision Q8 du 2026-10-18, valeur fixe)

light_record_file() {
  lf_commun=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || return 1
  [ -n "$lf_commun" ] || return 1
  printf '%s/pmzilla-main-validated\n' "$lf_commun"
}

env_signature() { # signature d'environnement (question Q9, design D3b) : écrit les 64 caractères (code 0), ou « absent:<composant> » (code 1)
  lf_env=$(bash "${LIGHT_FINISH_DIR:?}/finish_env.sh" --main-signature 2>/dev/null) && lf_env_code=0 || lf_env_code=1
  if [ "$lf_env_code" -eq 0 ] && [ "${#lf_env}" -eq 64 ]; then
    case "$lf_env" in *[!0123456789abcdef]*) ;; *) printf '%s\n' "$lf_env"; return 0 ;; esac
  fi
  case "$lf_env" in absent:?*) printf '%s\n' "$lf_env" ;; *) printf 'absent:bash\n' ;; esac
  return 1
}

light_jours() { # AAAA-MM-JJ : nombre de jours depuis l'époque, code 1 si la date est mal formée
  case "$1" in [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;; *) return 1 ;; esac
  awk -v d="$1" 'BEGIN {
    y = substr(d, 1, 4) + 0; m = substr(d, 6, 2) + 0; j = substr(d, 9, 2) + 0
    if (m < 1 || m > 12 || j < 1 || j > 31) exit 1
    if (m <= 2) y -= 1
    era = int(y / 400); yoe = y - era * 400; mp = (m + 9) % 12
    doy = int((153 * mp + 2) / 5) + j - 1; doe = yoe * 365 + int(yoe / 4) - int(yoe / 100) + doy
    print era * 146097 + doe - 719468 }'
}

light_paths_ok() {
  lf_liste=$(git diff --no-renames -z --name-only "$1" "$2" 2>/dev/null | tr '\0' '\n')
  [ -n "$lf_liste" ] || return 1
  if printf '%s\n' "$lf_liste" | grep -qv '^openspec/'; then return 1; fi
  lf_irreguliers=$(git ls-tree -r "$2" -- openspec/ 2>/dev/null | awk '$1 != "100644" && $1 != "100755" { print "x" }')
  [ -z "$lf_irreguliers" ] || return 2
  return 0
}

main_validated() {
  lf_arbre=$1
  lf_fichier=$(light_record_file) || { echo "arbre de main non validé"; return 1; }
  lf_ligne=""
  [ ! -f "$lf_fichier" ] || lf_ligne=$(awk -F'\t' -v t="$lf_arbre" '$1 == t { l = $0 } END { print l }' "$lf_fichier" 2>/dev/null)
  if [ -z "$lf_ligne" ] || [ "$(printf '%s\n' "$lf_ligne" | awk -F'\t' '{ print NF }')" -ne 4 ]; then
    echo "arbre de main non validé"; return 1
  fi
  if [ "$(printf '%s\n' "$lf_ligne" | cut -f2)" = "allégé-forcé" ]; then echo "validation de main forcée"; return 1; fi   # passage allégé obtenu avec un faux runner : n'ouvre jamais le chemin allégé
  lf_date=$(printf '%s\n' "$lf_ligne" | cut -f3)
  lf_empreinte=$(printf '%s\n' "$lf_ligne" | cut -f4)
  lf_aujourdhui=${LIGHT_FINISH_TODAY:-$(date -u +%Y-%m-%d)}
  lf_j_ligne=$(light_jours "$lf_date") && lf_j_jour=$(light_jours "$lf_aujourdhui") || { echo "validation de main expirée"; return 1; }
  lf_age=$((lf_j_jour - lf_j_ligne))
  if [ "$lf_age" -lt 0 ] || [ "$lf_age" -gt "$LIGHT_DUREE_MAX" ]; then echo "validation de main expirée"; return 1; fi
  if [ "${#lf_empreinte}" -ne 64 ]; then echo "signature d'environnement absente de la validation"; return 1; fi
  case "$lf_empreinte" in *[!0123456789abcdef]*) echo "signature d'environnement absente de la validation"; return 1 ;; esac
  if ! lf_actuelle=$(env_signature); then
    echo "signature d'environnement impossible : ${lf_actuelle#absent:} absent ou illisible"; return 1
  fi
  if [ "$lf_empreinte" != "$lf_actuelle" ]; then echo "environnement changé depuis la validation"; return 1; fi
  echo ok
}

light_suites() {
  lf_racine=$(git rev-parse --show-toplevel 2>/dev/null) || return 1
  lf_sortie=$(python3 "${LIGHT_FINISH_DIR:?}/select_suites.py" --openspec-readers --root "$lf_racine" 2>/dev/null) || return 1
  lf_noms=$(printf '%s\n' "$lf_sortie" | sed -n 's/^select_suites : \([^ ]*\) : .*/\1/p' | tr '\n' ' ' | sed 's/ $//')
  [ -n "$lf_noms" ] || return 1
  printf '%s\n' "$lf_noms"
}

light_spec_branch() { # <main> <sommet> : 0 si la branche ne change, depuis sa base commune avec main, que des chemins sous openspec/ (au moins un)
  lf_base=$(git merge-base "$1" "$2" 2>/dev/null) || return 1
  lf_chemins=$(git diff --name-only --no-renames "$lf_base" "$2" 2>/dev/null)
  [ -n "$lf_chemins" ] || return 1
  if printf '%s\n' "$lf_chemins" | grep -qv '^openspec/'; then return 1; fi
  return 0
}

light_main_ref() { # <dossier du dépôt> : le plus avancé de main local et de origin/main (après un fetch), vide s'ils ont divergé (design D2)
  lf_local=$(git -C "$1" rev-parse -q --verify "refs/heads/main^{commit}" 2>/dev/null) || return 0
  lf_distant=$(git -C "$1" rev-parse -q --verify "refs/remotes/origin/main^{commit}" 2>/dev/null) || lf_distant=""
  if [ -z "$lf_distant" ] || git -C "$1" merge-base --is-ancestor "$lf_distant" "$lf_local" 2>/dev/null; then
    printf '%s\n' "$lf_local"
  elif git -C "$1" merge-base --is-ancestor "$lf_local" "$lf_distant" 2>/dev/null; then
    printf '%s\n' "$lf_distant"
  fi
}

light_decision() {
  if [ -n "${FINISH_BRANCH_FORCE_RUN:-}" ]; then printf 'complet\trelance forcée\n'; return 0; fi
  if [ -z "$1" ]; then printf 'complet\tmain local et distant divergent\n'; return 0; fi
  light_paths_ok "$1" "$2"; lf_code=$?
  case "$lf_code" in
    0) ;;
    2) printf 'complet\tlien symbolique ou sous-module sous openspec/\n'; return 0 ;;
    *) printf 'complet\tbranche hors openspec/\n'; return 0 ;;
  esac
  lf_arbre_main=$(git rev-parse "$1^{tree}" 2>/dev/null) || { printf 'complet\tarbre de main non validé\n'; return 0; }
  if ! lf_raison=$(main_validated "$lf_arbre_main"); then printf 'complet\t%s\n' "$lf_raison"; return 0; fi
  light_suites >/dev/null || { printf 'complet\tsélection des suites impossible\n'; return 0; }
  printf 'allégé\n'
}

light_genre_leger() { # genre d'un passage allégé vert : « allégé-forcé » si l'une des deux variables de test est non vide, sinon « allégé »
  if [ -n "${FINISH_BRANCH_LIGHT_RUNNER:-}" ] || [ -n "${FINISH_BRANCH_VALIDATE:-}" ]; then echo "allégé-forcé"; else echo "allégé"; fi
}

record_main_validated() { # arbre genre
  lf_fichier=$(light_record_file) || return 1
  [ ! -d "$lf_fichier" ] || return 1
  lf_nouvelle="$lf_fichier.tmp.$$"
  lf_signature=$(env_signature) || lf_signature=inconnue
  (
    umask 077
    {
      if [ -f "$lf_fichier" ]; then tail -n 49 "$lf_fichier"; fi
      printf '%s\t%s\t%s\t%s\n' "$1" "$2" "$(date -u +%Y-%m-%d)" "$lf_signature"
    } > "$lf_nouvelle"
  ) 2>/dev/null && mv -f "$lf_nouvelle" "$lf_fichier" 2>/dev/null || { rm -f "$lf_nouvelle" 2>/dev/null; return 1; }
}

case "${0##*/}" in   # lancé directement (et non sourcé par un script de fin ou le hook) : la décision pour le sommet courant, lecture seule
  light_finish.sh)
    LIGHT_FINISH_DIR=$(cd "$(dirname "$0")" && pwd)
    light_decision "$(git rev-parse -q --verify refs/heads/main 2>/dev/null)" HEAD
    ;;
esac
