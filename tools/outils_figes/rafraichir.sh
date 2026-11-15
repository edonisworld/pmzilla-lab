#!/bin/bash
# PMZilla Lab : copie des outils figés et écriture de leur relevé (niveau 2 du bac à sable, design D5 ; tâches 7.3 et 7.4).
#
#     bash tools/outils_figes/rafraichir.sh <dépôt> <dossier des outils figés> [--extrait-du-train]
#
# Le troisième argument, exactement `--extrait-du-train`, est posé par la fin d'un train seulement (tools/finish_train.sh) : le dossier source est alors extrait du commit
# fusionné par `git show`, sans .git, et les contrôles Git ne s'appliquent pas ; un dossier source qui a un .git est alors refusé. Sans lui (appel à la main), le dossier
# source doit avoir son .git et les trois contrôles Git s'appliquent ; sans .git il est refusé. Tout autre troisième argument, ou plus de trois arguments : usage (code 2).
#
# Lancé par la fin d'un train quand le train change une source figée (tools/finish_train.sh, après le push), et par le fichier d'étape de l'auteur
# à la répétition. Jamais par une session : le dossier des outils figés est hors de ses écritures.
#  - lit la liste fermée <dépôt>/tools/outils_figes/liste.txt (lignes `E <nom>` : une enveloppe, copiée à la racine du dossier ; `C <chemin>` : une
#    dépendance, copiée sous copie/<chemin>) ; toutes les sources doivent exister avant la première copie (sinon code 4, rien n'est copié) ;
#  - exige <dossier>/dossiers.conf (écrit par l'auteur, jamais par ce script) : sinon code 4 ;
#  - copie chaque fichier (jamais un lien vers le dépôt) par un fichier temporaire renommé, puis réécrit `empreintes.sha256` : une ligne
#    « <sha256 en hexadécimal> deux espaces <nom relatif> » par fichier figé et pour dossiers.conf, triée, la forme de `shasum -a 256` que lisent
#    les enveloppes et le contrôle `sandbox` du doctor ; le relevé n'est pas listé dans lui-même.
# Codes : 0 copié et relevé écrit ; 2 usage ; 4 liste, source ou dossiers.conf manquant (rien n'est copié, le relevé n'est pas réécrit) ; 5 refus (à la main : dépôt sans
# .git, .git qui n'est pas un dossier, racine Git différente du dossier passé, pas sur main, fetch en échec, HEAD différent de origin/main, fichier de la liste, liste.txt
# ou ce script non suivi ou modifié ; avec --extrait-du-train : dossier source avec un .git ; rien n'est copié, la note du retard reste).
# Remplace : rien (le fichier d'étape de l'auteur copiait seul, à la répétition). Retrait : avec le bac à sable (R-20261110-06, -07, -08).
set -u
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
LC_ALL=C
export LC_ALL
# R-20261110-08 : l'environnement Git hérité ne doit pas faire juger un autre dépôt que le dossier passé (GIT_DIR, GIT_WORK_TREE, GIT_CONFIG_PARAMETERS...).
# Remplace : rien. Retrait : avec le bac à sable (R-20261110-08).
for variable in GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_CEILING_DIRECTORIES GIT_NAMESPACE $(compgen -v GIT_CONFIG); do
  unset "$variable"
done

dire() { printf 'outils figés : %s\n' "$*" >&2; }

extrait=0
case $# in
  2) ;;
  3) [ "$3" = "--extrait-du-train" ] || { dire "usage : bash tools/outils_figes/rafraichir.sh <dépôt> <dossier des outils figés>"; exit 2; }; extrait=1 ;;
  *) dire "usage : bash tools/outils_figes/rafraichir.sh <dépôt> <dossier des outils figés>"; exit 2 ;;
esac
depot=$1
dest=$2
[ -d "$depot" ] && [ -d "$dest" ] || { dire "usage : le dépôt et le dossier des outils figés doivent exister"; exit 2; }
liste="$depot/tools/outils_figes/liste.txt"
[ -f "$liste" ] || { dire "liste des fichiers figés introuvable, rien n'est copié"; exit 4; }
[ -f "$dest/dossiers.conf" ] && [ ! -L "$dest/dossiers.conf" ] || { dire "dossiers.conf absent du dossier des outils figés, rien n'est copié"; exit 4; }

sources=()
relatifs=()
while IFS= read -r ligne || [ -n "$ligne" ]; do
  case "$ligne" in ""|"#"*) continue ;; esac
  genre=${ligne%% *}
  chemin=${ligne#* }
  case "$chemin" in ""|/*|*..*|*" "*) dire "ligne refusée dans la liste, rien n'est copié"; exit 4 ;; esac
  case "$genre" in
    E) src="$depot/tools/outils_figes/$chemin"; rel=$chemin ;;
    C) src="$depot/$chemin"; rel="copie/$chemin" ;;
    *) dire "ligne refusée dans la liste, rien n'est copié"; exit 4 ;;
  esac
  { [ -f "$src" ] && [ ! -L "$src" ]; } || { dire "source figée absente de l'arbre : $chemin ; rien n'est copié"; exit 4; }
  sources+=("$src")
  relatifs+=("$rel")
done < "$liste"
[ "${#relatifs[@]}" -gt 0 ] || { dire "liste des fichiers figés vide, rien n'est copié"; exit 4; }

# R-20261110-06 : à la main, avant toute copie, trois refus (code 5, message fixe sans chemin, la note du retard n'est pas touchée) : l'espace de travail n'est pas sur la
# branche main ; `git fetch` échoue, ou HEAD diffère de origin/main après lui ; un fichier de la liste a une modification non commitée (indexée ou non indexée).
# R-20261110-08, plus strict : liste.txt et ce script sont contrôlés comme les fichiers de la liste ; chacun doit être suivi par Git (un fichier ignoré ou non suivi est
# refusé) ; le .git doit être un dossier du dépôt et la racine lue par Git le dossier passé ; le fetch neutralise les crochets. La fin d'un train appelle ce script sur un dossier de préparation (<préparation>/depot), extrait par `git show` du commit du sommet du train, sans
# .git, après le push (le train a déjà vérifié main et origin/main), avec le troisième argument `--extrait-du-train` : les contrôles Git sont alors sautés, et un dossier
# qui a un .git est refusé. R-20261110-07 : sans cet argument, un dossier sans .git est refusé (un appel à la main ne peut pas échapper aux contrôles).
# Remplace : rien. Retrait : avec le bac à sable (R-20261110-06, -07, -08).
if [ "$extrait" = 1 ]; then
  [ ! -e "$depot/.git" ] || { dire "refus : le dossier extrait du train ne doit pas avoir de .git, rien n'est copié"; exit 5; }
else
  [ -e "$depot/.git" ] || { dire "refus : le dépôt n'a pas de .git, rien n'est copié"; exit 5; }
  { [ -d "$depot/.git" ] && [ ! -L "$depot/.git" ]; } || { dire "refus : le .git du dépôt n'est pas un dossier, rien n'est copié"; exit 5; }
  garde=(-c core.fsmonitor=false -c core.hooksPath=/dev/null -C "$depot")
  racine=$(git "${garde[@]}" rev-parse --show-toplevel 2>/dev/null) && [ -n "$racine" ] && [ "$(cd "$racine" 2>/dev/null && pwd -P)" = "$(cd "$depot" && pwd -P)" ] \
    || { dire "refus : la racine Git n'est pas le dossier du dépôt, rien n'est copié"; exit 5; }
  [ "$(git "${garde[@]}" symbolic-ref -q --short HEAD 2>/dev/null)" = "main" ] || { dire "refus : l'espace de travail n'est pas sur la branche main, rien n'est copié"; exit 5; }
  git "${garde[@]}" fetch -q origin </dev/null >/dev/null 2>&1 || { dire "refus : git fetch en échec, rien n'est copié"; exit 5; }
  tete=$(git "${garde[@]}" rev-parse -q --verify HEAD 2>/dev/null) && distant=$(git "${garde[@]}" rev-parse -q --verify refs/remotes/origin/main 2>/dev/null) \
    && [ "$tete" = "$distant" ] || { dire "refus : HEAD diffère de origin/main, rien n'est copié"; exit 5; }
  # Les fichiers de la liste, la liste et ce script lui-même : chacun suivi par Git (un fichier ignoré ou non suivi est refusé, quel que soit status.showUntrackedFiles) et
  # identique à HEAD, qui vaut origin/main : rien d'indexé, rien de modifié. Chaque fichier copié est alors celui de origin/main.
  suivis=(tools/outils_figes/liste.txt tools/outils_figes/rafraichir.sh)
  for rel in "${relatifs[@]}"; do
    case "$rel" in
      copie/*) suivis+=("${rel#copie/}") ;;
      *) suivis+=("tools/outils_figes/$rel") ;;
    esac
  done
  for fichier in "${suivis[@]}"; do
    git "${garde[@]}" ls-files --error-unmatch -- "$fichier" >/dev/null 2>&1 || { dire "refus : un fichier de la liste n'est pas suivi par Git, rien n'est copié"; exit 5; }
  done
  git "${garde[@]}" diff --quiet HEAD -- "${suivis[@]}" >/dev/null 2>&1 && git "${garde[@]}" diff --cached --quiet -- "${suivis[@]}" >/dev/null 2>&1 \
    || { dire "refus : un fichier de la liste a une modification non commitée, rien n'est copié"; exit 5; }
fi

n=${#relatifs[@]}
i=0
while [ "$i" -lt "$n" ]; do
  rel=${relatifs[$i]}
  mkdir -p -- "$dest/$(dirname -- "$rel")" || { dire "dossier impossible à créer pour : $rel"; exit 4; }
  cp -- "${sources[$i]}" "$dest/$rel.nouveau.$$" && mv -f -- "$dest/$rel.nouveau.$$" "$dest/$rel" || { rm -f -- "$dest/$rel.nouveau.$$"; dire "copie impossible : $rel"; exit 4; }
  i=$((i + 1))
done

temp="$dest/empreintes.sha256.nouveau.$$"
{
  for rel in "${relatifs[@]}" dossiers.conf; do
    printf '%s  %s\n' "$(shasum -a 256 -- "$dest/$rel" | cut -d' ' -f1)" "$rel"
  done
} | sort -k2 > "$temp" && mv -f -- "$temp" "$dest/empreintes.sha256" || { rm -f -- "$temp"; dire "relevé impossible à écrire"; exit 4; }

# R-20261110-03, -04 : un rafraîchissement réussi retire la note du retard (voisine du dossier des outils figés, dans le dossier de données) ; en échec (codes 2 et 4
# plus haut) la note reste. Dans la fin d'un train, ce script tourne sur un dossier de préparation : la note du dossier de données y est retirée par l'échange
# (frozen_swap de tools/finish_train.sh), seulement une fois l'échange fait. Remplace : rien. Retrait : avec le bac à sable (R-20261110-03, -04).
rm -f -- "$(dirname -- "$dest")/outils-figes-en-retard" 2>/dev/null

printf 'outils figés : %s fichier(s) copié(s), relevé de %s ligne(s) écrit\n' "$n" "$((n + 1))"
exit 0
