#!/bin/sh
# Aperçu de la fusion de main dans une branche (change finish-under-lock, design D10). Module sourcé, jamais lancé : tools/finish_branch.sh et
# tools/finish_worktree.sh le chargent ; la règle n'existe qu'ici. POSIX sh. Les fonctions travaillent dans le dossier courant (le dépôt) ;
# elles ne changent ni référence, ni index, ni fichier (git merge-tree --write-tree n'écrit que des objets).
#
# Fonctions :
#   finish_merge_preview <main> <sommet>   écrit « sans conflit » (code 0), ou « conflit » suivi d'un chemin par ligne (code 1), ou
#                                          « impossible » (code 2 : Git n'a pas pu calculer la fusion)
#   finish_merge_lines <main> <sommet>     écrit les lignes que les refus montrent : « fusion de main prévue : sans conflit », ou
#                                          « fusion de main prévue : conflit sur <n> fichier(s) » puis un chemin par ligne, ou rien si
#                                          l'aperçu est impossible ; rend le code de l'aperçu
# Lancé directement, il ne fait rien (code 0) :
#
#     bash tools/finish_merge.sh

finish_merge_preview() {
  fm_sortie=$(git merge-tree --write-tree --name-only "$1" "$2" 2>/dev/null); fm_code=$?
  case "$fm_code" in
    0) echo "sans conflit"; return 0 ;;
    1) echo "conflit"
       # format : l'identifiant de l'arbre, les chemins en conflit, une ligne vide, puis les messages d'information
       printf '%s\n' "$fm_sortie" | sed 1d | awk 'NF == 0 { exit } { print }'
       return 1 ;;
    *) echo "impossible"; return 2 ;;
  esac
}

finish_merge_lines() {
  fm_apercu=$(finish_merge_preview "$1" "$2"); fm_rc=$?
  case "$fm_rc" in
    0) echo "fusion de main prévue : sans conflit" ;;
    1) fm_noms=$(printf '%s\n' "$fm_apercu" | sed 1d)
       fm_n=$(printf '%s\n' "$fm_noms" | grep -c .)
       echo "fusion de main prévue : conflit sur $fm_n fichier(s)"
       printf '%s\n' "$fm_noms" ;;
  esac
  return "$fm_rc"
}
