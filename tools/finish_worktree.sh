#!/bin/bash
# Termine une branche depuis son worktree : vérifie, retire le worktree de la branche, bascule l'espace de travail sur la branche,
# puis lance tools/finish_branch.sh dans l'espace de travail et sort avec son code, inchangé (design D12 de batch-milestone).
# À lancer par l'utilisateur dans le Terminal, une fois la session de ce worktree terminée (jamais depuis une session Claude Code :
# voir les règles deny).
#
#     bash tools/finish_worktree.sh <branche>          termine la branche
#     bash tools/finish_worktree.sh --help             affiche ce que le script vérifie et fait
#
# Lancé depuis l'espace de travail ou depuis un de ses worktrees autre que celui qu'il retire. L'espace de travail est trouvé par
# git rev-parse --git-common-dir ; chaque commande Git s'y rapporte (git -C). Le worktree de la branche est cherché dans
# git worktree list --porcelain (n'importe quel dossier) ; un worktree détaché ne correspond à aucune branche.
# Tous les contrôles (codes 20 à 29) précèdent le retrait, dans l'ordre de la table des codes.
# Codes : 0 terminé ; 20 usage ; 21 hors du dépôt ; 22 main ou spike/* ; 23 branche introuvable ; 24 l'espace de travail n'est pas sur main ;
#         25 espace de travail pas propre ; 26 aucun worktree pour la branche (ou dossier absent) ; 27 lancé depuis le worktree à retirer ;
#         28 worktree pas propre ; 29 fichiers ignorés qui seraient perdus ; 30 retrait du worktree impossible ;
#         31 bascule de l'espace de travail impossible après le retrait.
#         Les codes 0 à 13 de tools/finish_branch.sh sont transmis tels quels.
# Les codes 30 et 31 arrivent après un changement et disent l'état laissé. Un code non nul du script de fin laisse le worktree retiré
# et l'espace de travail sur la branche ; le script le dit et, pour les codes 1 à 9 (branche non fusionnée), donne la recréation.
#
# Interdit au script : forcer le retrait, élaguer les worktrees, contourner un hook ou le lancement vert, pousser, fusionner,
# réinitialiser, remettre de côté, valider, supprimer une branche, revenir en arrière, relancer, lire ou lister un fichier ignoré
# (compte et dossier de premier niveau seulement), modifier tools/worktree.sh ou tools/finish_branch.sh.
#
# Variable (pour les tests de ce script) :
#   FINISH_WORKTREE_FINISH   commande de fin de branche (défaut : bash tools/finish_branch.sh), lancée dans l'espace de travail,
#                            entrée standard sur /dev/null
set -u

NOM="finish_worktree"
PRINCIPALE="main"
FIN="${FINISH_WORKTREE_FINISH:-bash tools/finish_branch.sh}"

refus() { # code message... : écrit sur la sortie d'erreur et sort
  code=$1; shift
  printf '%s : %s\n' "$NOM" "$1" >&2
  shift
  for ligne in "$@"; do printf '%s\n' "$ligne" >&2; done
  exit "$code"
}
info() { printf '%s : %s\n' "$NOM" "$1"; }

aide() {
  cat <<EOF
$NOM : usage : bash tools/finish_worktree.sh <branche> [--help]
Termine la branche donnée depuis son worktree, dans le Terminal, une fois la session de ce worktree terminée.
Vérifications, dans cet ordre (la première qui refuse arrête le script, sans rien changer) :
  20  usage : une branche, pas d'autre argument ni d'option inconnue
  21  le dossier courant est dans un dépôt Git
  22  la branche n'est ni main ni spike/*
  23  la branche existe en local
  24  l'espace de travail est sur main
  25  l'espace de travail est propre (fichiers non ignorés compris)
  26  un worktree autre que l'espace de travail tient la branche, et son dossier existe
  27  le script n'est pas lancé depuis le worktree à retirer
  28  le worktree est propre (fichiers non ignorés compris)
  29  le worktree ne tient pas de fichier ignoré qui serait perdu (réglage local, __pycache__, .pyc et .DS_Store exceptés)
Puis : retrait du worktree (git worktree remove, sans force), bascule de l'espace de travail sur la branche, puis lancement de
tools/finish_branch.sh dans l'espace de travail (entrée vide) ; le code de ce script est transmis tel quel.
Codes de sortie : 0 terminé ; 20 à 29 refus ci-dessus ; 30 retrait du worktree impossible (rien d'autre n'est changé) ;
  31 bascule impossible après le retrait (le worktree est retiré, l'espace de travail est sur main, avec la commande de recréation) ;
les codes 0 à 13 de tools/finish_branch.sh sont transmis, avec l'état laissé ; pour les codes 1 à 9, la commande de recréation du worktree.
Le script ne force rien, n'élague rien, ne contourne aucun hook, ne pousse ni ne fusionne, et ne revient jamais en arrière.
EOF
}

# 20. usage
if [ $# -eq 1 ] && [ "$1" = "--help" ]; then aide; exit 0; fi
{ [ $# -eq 1 ] && [ -n "$1" ] && [ "${1#-}" = "$1" ]; } || refus 20 "usage : bash tools/finish_worktree.sh <branche>" "Un seul argument : la branche (ou --help)."
BRANCHE=$1

# 21. dans un dépôt ; l'espace de travail est le dossier du dépôt commun
COMMUN=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || refus 21 "hors du dépôt" "Le script se lance depuis l'espace de travail ou un de ses worktrees."
ESPACE=$(cd "$(dirname "$COMMUN")" 2>/dev/null && pwd -P) || refus 21 "hors du dépôt" "Espace de travail introuvable."
ICI=$(pwd -P)

# 22. une branche à terminer
case "$BRANCHE" in
  "$PRINCIPALE"|spike/*) refus 22 "aucune branche à terminer" "$BRANCHE est $PRINCIPALE ou une préversion (spike/*), jamais terminée par ce script." ;;
esac

# 23. la branche existe
git -C "$ESPACE" show-ref --verify -q "refs/heads/$BRANCHE" 2>/dev/null || refus 23 "branche $BRANCHE introuvable" "Aucune branche locale de ce nom dans $ESPACE."

# 24. espace de travail sur main
COURANTE=$(git -C "$ESPACE" symbolic-ref --short -q HEAD 2>/dev/null) || COURANTE=""
[ "$COURANTE" = "$PRINCIPALE" ] || refus 24 "l'espace de travail n'est pas sur $PRINCIPALE" "$ESPACE est sur ${COURANTE:-une tête détachée} : reviens sur $PRINCIPALE (git switch $PRINCIPALE), puis relance."

# 25. espace de travail propre
if [ -n "$(git -C "$ESPACE" status --porcelain 2>/dev/null)" ]; then
  refus 25 "l'espace de travail n'est pas propre" "Des fichiers modifiés, indexés ou non suivis (hors fichiers ignorés) existent dans $ESPACE : commite-les ou écarte-les, puis relance."
fi

# 26. le worktree de la branche (jamais l'espace de travail lui-même)
WT=$(git -C "$ESPACE" worktree list --porcelain 2>/dev/null | awk -v ref="refs/heads/$BRANCHE" -v espace="$ESPACE" '
  /^worktree / { dossier = substr($0, 10) }
  $0 == "branch " ref && dossier != espace { print dossier; exit }')
if [ -z "$WT" ]; then
  refus 26 "aucun worktree pour la branche $BRANCHE" "Pour la terminer depuis l'espace de travail :" "  git switch $BRANCHE" "  bash tools/finish_branch.sh"
fi
[ -d "$WT" ] || refus 26 "dossier du worktree absent : $WT" "Le worktree est enregistré mais son dossier n'existe plus ; rien n'est changé." \
  "Pour la terminer depuis l'espace de travail, après avoir vérifié git worktree list :" "  git switch $BRANCHE" "  bash tools/finish_branch.sh"
WT=$(cd "$WT" && pwd -P)

# 27. pas depuis le worktree à retirer
case "$ICI/" in
  "$WT/"*) refus 27 "lance le script depuis l'espace de travail" "Le dossier courant est dans le worktree à retirer ($WT) : va dans $ESPACE ou dans un autre worktree, puis relance." ;;
esac

# 28. worktree propre
if [ -n "$(git -C "$WT" status --porcelain 2>/dev/null)" ]; then
  refus 28 "le worktree n'est pas propre" "Des fichiers modifiés, indexés ou non suivis (hors fichiers ignorés) existent dans $WT : commite-les ou écarte-les, puis relance."
fi

# 29. fichiers ignorés qui seraient perdus (compte et dossier de premier niveau seulement, jamais un nom de fichier)
PERDUS=0
DOSSIERS=""
while IFS= read -r chemin; do
  [ -n "$chemin" ] || continue
  case "$chemin" in
    .claude/settings.local.json|__pycache__/*|*/__pycache__/*|*.pyc|.DS_Store|*/.DS_Store) continue ;;
  esac
  PERDUS=$((PERDUS + 1))
  case "$chemin" in */*) premier="${chemin%%/*}/" ;; *) premier="(racine)" ;; esac
  case "
$DOSSIERS
" in *"
$premier
"*) ;; *) DOSSIERS="$DOSSIERS${DOSSIERS:+
}$premier" ;; esac
done < <(git -C "$WT" ls-files --others --ignored --exclude-standard 2>/dev/null)
if [ "$PERDUS" -gt 0 ]; then
  liste=()
  while IFS= read -r d; do liste+=("  - $d"); done <<< "$DOSSIERS"
  refus 29 "fichiers ignorés qui seraient perdus" "$PERDUS fichier(s) ignoré(s) dans $WT seraient supprimés avec le worktree, dans les dossiers de premier niveau :" "${liste[@]}" \
    "Sauvegarde-les ou supprime-les toi-même, puis relance ; le script ne les lit ni ne les liste."
fi

# Retrait du worktree (sans force, sans nouvel essai)
git -C "$ESPACE" worktree remove "$WT" >/dev/null 2>&1 \
  || refus 30 "retrait du worktree impossible" "git worktree remove a refusé de retirer $WT (worktree verrouillé, par exemple) ; rien d'autre n'est changé." \
    "Vérifie avec : git worktree list"
info "worktree retiré : $WT"

# Bascule de l'espace de travail sur la branche
git -C "$ESPACE" switch -q "$BRANCHE" >/dev/null 2>&1 \
  || refus 31 "bascule de l'espace de travail impossible" "Le worktree $WT est retiré ; l'espace de travail est sur $PRINCIPALE ; le script de fin n'est pas lancé." \
    "Pour recréer le worktree : bash tools/worktree.sh $BRANCHE"
info "espace de travail sur la branche $BRANCHE"

# Fin de branche, dans l'espace de travail, entrée vide ; le code est transmis
( cd "$ESPACE" && sh -c "$FIN" </dev/null )
CODE=$?
if [ "$CODE" -ne 0 ]; then
  printf '%s : la fin de branche a rendu le code %s ; le worktree de %s est retiré\n' "$NOM" "$CODE" "$BRANCHE" >&2
  case "$CODE" in
    [1-9]) printf '%s : pour reprendre dans un worktree : git switch %s && bash tools/worktree.sh %s\n' "$NOM" "$PRINCIPALE" "$BRANCHE" >&2 ;;
  esac
fi
exit "$CODE"
