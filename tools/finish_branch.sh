#!/bin/bash
# Termine la branche courante : vérifie, lance le runner complet, fusionne dans main (sans avance rapide), pousse main,
# supprime la branche locale (suppression sûre) puis la branche distante si elle existe.
# À lancer par l'utilisateur dans le Terminal, depuis le workspace (jamais depuis une session Claude Code : voir les règles deny).
#
#     bash tools/finish_branch.sh          termine la branche courante
#     bash tools/finish_branch.sh --help   affiche ce que le script vérifie et fait
#
# Les vérifications se font dans l'ordre de la table des codes ; la première qui refuse arrête le script avant tout changement de branche.
# Codes : 0 terminé ; 1 tests en échec ; 2 usage ; 3 aucune branche à terminer (ou branche spike/*) ; 4 arbre non propre ; 5 change OpenSpec non archivé ;
#         6 jeu d'essai validant absent ; 7 main pas à jour ; 8 la branche ne contient pas main ;
#         9 fusion impossible (annulée) ; 10 push refusé ; 11 branche non supprimée (le travail est fusionné) ;
#         12 main est ouvert dans un autre dossier (worktree), refus avant toute fusion ;
#         13 fusion faite et poussée, mais dossier d'exécution non mis à jour (modifications locales, hors de l'historique de main,
#            verrou de la veille ou fenêtre horaire, dépendances non préparées).
# Les codes 9 à 11 et 13 arrivent après un changement et disent l'état laissé.
# Après le push et la suppression des branches, le script lance « tools/run_worktree.sh update » (celui qui est à côté de lui) ;
# un dossier d'exécution absent est dit en une ligne, sans erreur.
#
# Interdit au script : push forcé, rebase, réécriture d'historique, résolution de conflit, --no-verify ou tout contournement de hook,
# la variable de contournement du lancement vert, suppression forcée de branche, lancement du jeu d'essai, remise à zéro ou nettoyage du dossier d'exécution.
#
# Variables (pour les tests de ce script) :
#   FINISH_BRANCH_RUNNER   commande du runner complet (défaut : bash tests/run_all.sh), lancée à la racine du dépôt
#   FINISH_BRANCH_RECORDS  dossier des enregistrements du jeu d'essai (défaut : ${PMZILLA_LAB_DATA:-~/.pmzilla-lab}/essais)
# Le script ne modifie aucun fichier, sauf l'avance rapide du dossier d'exécution.
set -u

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
NOM="finish_branch"
PRINCIPALE="main"
DISTANT="origin"
RUNNER="${FINISH_BRANCH_RUNNER:-bash tests/run_all.sh}"
ENREGISTREMENTS="${FINISH_BRANCH_RECORDS:-${PMZILLA_LAB_DATA:-$HOME/.pmzilla-lab}/essais}"

# Chemins qui exigent un jeu d'essai validant (CLAUDE.md, postures, Critic, vocabulaire, mémoire figée des postures).
CHEMINS_JEU=("CLAUDE.md" ".claude/skills/pmzilla-*" ".claude/agents/pmzilla-critic.md" "tests/postures/vocabulaire.yaml" "tests/postures/memoire")

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
$NOM : usage : bash tools/finish_branch.sh [--help]
Termine la branche courante, depuis le workspace, dans le Terminal. Aucun autre argument.
Vérifications, dans cet ordre (la première qui refuse arrête le script, sans rien changer) :
  3  il y a une branche à terminer (ni main, ni tête détachée, ni hors dépôt, ni branche spike/*)
  4  l'arbre de travail est propre (fichiers non ignorés compris)
  5  aucun change OpenSpec lié à la branche n'est resté non archivé (une branche qui ne change que openspec/ est une branche de spécification)
  6  un jeu d'essai validant est enregistré pour le sommet de la branche si CLAUDE.md, une posture, Critic, le vocabulaire ou la mémoire figée ont changé
  7  main est à jour depuis le distant (avance rapide seulement)
  8  la branche contient main à jour
  12 main n'est pas déjà ouvert dans un autre dossier (worktree) : sinon, la fusion serait impossible
  1  le runner complet des tests est vert sur la branche
Puis : fusion de la branche dans main sans avance rapide, push de main, suppression de la branche locale (sûre) et de la branche distante,
puis mise à jour du dossier d'exécution par tools/run_worktree.sh update (absent : une ligne d'information).
Codes de sortie : 0 terminé ; 1 tests en échec ; 2 usage ; 3 à 8 refus ci-dessus ; 9 fusion impossible (annulée) ;
10 push refusé (la fusion n'existe que sur main local) ; 11 branche non supprimée (le travail est fusionné) ;
12 main est ouvert dans un autre dossier (refus avant toute fusion, avec la manoeuvre) ;
13 fusion faite et poussée, dossier d'exécution non mis à jour (relancer : bash tools/run_worktree.sh update).
Le script ne force rien, ne rebase pas, ne contourne aucun hook, ne lance pas le jeu d'essai et ne modifie aucun fichier, sauf l'avance rapide du dossier d'exécution.
EOF
}

# 2. usage
if [ $# -gt 0 ]; then
  if [ $# -eq 1 ] && { [ "$1" = "--help" ] || [ "$1" = "-h" ]; }; then aide; exit 0; fi
  refus 2 "usage : bash tools/finish_branch.sh [--help] (aucun autre argument)"
fi

# 3. une branche à terminer
RACINE=$(git rev-parse --show-toplevel 2>/dev/null) || refus 3 "aucune branche à terminer" "Le script se lance depuis le dépôt du workspace."
cd "$RACINE" || refus 3 "aucune branche à terminer" "Dépôt introuvable."
BRANCHE=$(git symbolic-ref --short -q HEAD 2>/dev/null) || BRANCHE=""
[ -n "$BRANCHE" ] || refus 3 "aucune branche à terminer" "La tête est détachée."
[ "$BRANCHE" != "$PRINCIPALE" ] || refus 3 "aucune branche à terminer" "La branche courante est $PRINCIPALE."
case "$BRANCHE" in
  spike/*) refus 3 "branche spike/* refusée" "$BRANCHE est une préversion (spike), jamais fusionnée dans $PRINCIPALE : écarte-la ou renomme-la si elle doit vraiment être livrée." ;;
esac

# 4. arbre propre
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  refus 4 "l'arbre n'est pas propre" "Des fichiers modifiés, indexés ou non suivis (hors fichiers ignorés) existent : commite-les ou écarte-les, puis relance."
fi

BASE_FUSION=$(git merge-base "$PRINCIPALE" HEAD 2>/dev/null) \
  || refus 3 "aucune branche à terminer" "Base commune avec $PRINCIPALE introuvable."
MODIFIES=$(git diff --name-only --no-renames "$BASE_FUSION" HEAD)

# 5. change OpenSpec lié non archivé (D2)
BRANCHE_SPEC=0
if [ -n "$MODIFIES" ] && [ -z "$(printf '%s\n' "$MODIFIES" | grep -v '^openspec/')" ]; then
  BRANCHE_SPEC=1
fi
if [ "$BRANCHE_SPEC" -eq 1 ]; then
  info "branche de spécification : elle ne change que openspec/, aucun change à archiver n'est exigé"
else
  DERNIER_SEGMENT="${BRANCHE##*/}"
  NON_ARCHIVES=""
  while IFS= read -r changement; do
    [ -n "$changement" ] || continue
    [ "$changement" != "archive" ] || continue
    lie=0
    [ "$changement" = "$DERNIER_SEGMENT" ] && lie=1
    if [ "$lie" -eq 0 ] && printf '%s\n' "$MODIFIES" | grep -q "^openspec/changes/$changement/"; then lie=1; fi
    [ "$lie" -eq 1 ] && NON_ARCHIVES="$NON_ARCHIVES $changement"
  done < <(git ls-tree --name-only HEAD openspec/changes/ 2>/dev/null | sed 's|^openspec/changes/||')
  if [ -n "$NON_ARCHIVES" ]; then
    args=()
    for c in $NON_ARCHIVES; do args+=("  - $c"); done
    refus 5 "change OpenSpec non archivé" "Change(s) lié(s) à la branche, à archiver avant de terminer :" "${args[@]}"
  fi
fi

# 6. jeu d'essai validant (D3)
EXIGE=0
for chemin in "${CHEMINS_JEU[@]}"; do
  if git diff --quiet --no-renames "$BASE_FUSION" HEAD -- "$chemin" 2>/dev/null; then :; else EXIGE=1; fi
done
if [ "$EXIGE" -eq 1 ]; then
  # Lignes « date<TAB>base<TAB>réussies<TAB>total » des enregistrements complets, validants, non rejugés, en langue par défaut.
  CANDIDATS=$(python3 -I - "$ENREGISTREMENTS" <<'PYEOF'
import json, sys
from pathlib import Path
dossier = Path(sys.argv[1])
lignes = []
for chemin in sorted(dossier.glob("*/resultats.json")) if dossier.is_dir() else []:
    try:
        d = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        continue
    if not isinstance(d, dict):
        continue
    cas = d.get("cas") or []
    complet = d.get("complet", len(cas) >= 10)
    if not complet or not d.get("validant", True) or d.get("rejuge") or d.get("langue", "fr") != "fr" or not d.get("base"):
        continue
    verifs = [v for c in cas for v in (c.get("verifications") or []) if not v.get("indicateur")]
    reussies = sum(1 for v in verifs if v.get("ok"))
    lignes.append("\t".join([str(d.get("date", "?")), str(d["base"]), str(reussies), str(len(verifs))]))
print("\n".join(sorted(lignes)))
PYEOF
  ) || CANDIDATS=""
  TROUVE=""
  DISPARU=0
  while IFS=$'\t' read -r date base reussies total; do
    [ -n "${base:-}" ] || continue
    if ! git cat-file -e "${base}^{commit}" 2>/dev/null; then DISPARU=1; continue; fi
    differe=0
    for chemin in "${CHEMINS_JEU[@]}"; do
      git diff --quiet --no-renames "$base" HEAD -- "$chemin" 2>/dev/null || differe=1
    done
    [ "$differe" -eq 0 ] && TROUVE="$date ($reussies/$total)"
  done <<< "$CANDIDATS"
  if [ -z "$TROUVE" ]; then
    if [ "$DISPARU" -eq 1 ]; then
      refus 6 "jeu d'essai validant absent" "l'état testé n'existe plus : relance le jeu d'essai sur l'état commité de la branche."
    fi
    refus 6 "jeu d'essai validant absent" "CLAUDE.md, une posture, Critic, le vocabulaire ou la mémoire figée ont changé sans passage complet validant pour ce sommet." "Lance le jeu d'essai sur l'état commité, puis relance."
  fi
  info "jeu d'essai validant trouvé : $TROUVE"
fi

# 7. main à jour depuis le distant, en avance rapide seulement
git fetch -q "$DISTANT" "$PRINCIPALE" 2>/dev/null || refus 7 "main n'est pas à jour" "Le fetch de $DISTANT $PRINCIPALE a échoué."
DISTANTE=$(git rev-parse -q --verify FETCH_HEAD^{commit}) || refus 7 "main n'est pas à jour" "Le fetch de $DISTANT $PRINCIPALE a échoué."
LOCALE=$(git rev-parse -q --verify "refs/heads/$PRINCIPALE") || refus 7 "main n'est pas à jour" "$PRINCIPALE local introuvable."
if git merge-base --is-ancestor "$DISTANTE" "$LOCALE"; then
  :   # main local est égal ou en avance : rien à rapatrier
elif git merge-base --is-ancestor "$LOCALE" "$DISTANTE"; then
  git update-ref -m "$NOM : avance rapide de $PRINCIPALE" "refs/heads/$PRINCIPALE" "$DISTANTE" "$LOCALE" \
    || refus 7 "main n'est pas à jour" "L'avance rapide de $PRINCIPALE local a échoué."
else
  refus 7 "main n'est pas à jour" "$PRINCIPALE local a divergé de $DISTANT/$PRINCIPALE : rapproche-les à la main (sans réécrire l'historique), puis relance."
fi

# 8. la branche contient main à jour
git merge-base --is-ancestor "$PRINCIPALE" HEAD \
  || refus 8 "la branche ne contient pas main" "Ramène $PRINCIPALE dans la branche d'abord (git merge $PRINCIPALE), relance les tests, puis relance."

# 12. main ouvert dans un autre dossier (worktree) : la fusion y serait impossible, on refuse avant le runner
DOSSIER_MAIN=$(git worktree list --porcelain 2>/dev/null | awk -v ref="refs/heads/$PRINCIPALE" -v ici="$RACINE" '
  /^worktree / { dossier = substr($0, 10) }
  $0 == "branch " ref && dossier != ici { print dossier; exit }')
if [ -n "$DOSSIER_MAIN" ]; then
  refus 12 "$PRINCIPALE est ouvert dans un autre dossier" "$PRINCIPALE est déjà ouvert dans : $DOSSIER_MAIN" \
    "La fusion y est impossible depuis ici ; rien n'est changé. La manoeuvre :" \
    "  1. ici ($RACINE) : git switch --detach" \
    "  2. dans $DOSSIER_MAIN : git switch $BRANCHE" \
    "  3. dans $DOSSIER_MAIN : bash tools/finish_branch.sh"
fi

# 1. runner complet vert sur la branche (jamais filtré, sans les variables réservées à git commit)
info "lancement du runner complet sur $BRANCHE"
env -u PMZILLA_NO_EVALS -u PMZILLA_SKIP_GREEN_CHECK sh -c "$RUNNER" \
  || refus 1 "tests en échec, rien n'est fusionné" "Corrige la branche, relance."

# Fusion
ANCIEN_MAIN=$(git rev-parse "refs/heads/$PRINCIPALE")
RAISON=$(git checkout -q "$PRINCIPALE" 2>&1) \
  && RAISON=$(git merge --no-ff --no-edit -q "$BRANCHE" 2>&1)
if [ $? -ne 0 ]; then
  git merge --abort >/dev/null 2>&1
  git checkout -q "$BRANCHE" 2>/dev/null
  refus 9 "fusion impossible, annulée" "Raison donnée par git :" "${RAISON:-(aucun message)}" \
    "La fusion est annulée, tu es revenu sur $BRANCHE ; $PRINCIPALE est inchangé."
fi
FAIT=("fusion de $BRANCHE dans $PRINCIPALE (sans avance rapide)")

# Push
if ! git push -q "$DISTANT" "$PRINCIPALE" >/dev/null 2>&1; then
  refus 10 "push refusé" "La fusion n'existe que sur $PRINCIPALE local ; tu es sur $PRINCIPALE." \
    "Pour réessayer le push : git push $DISTANT $PRINCIPALE" \
    "Pour défaire la fusion locale : git reset --hard $ANCIEN_MAIN"
fi
FAIT+=("push de $PRINCIPALE vers $DISTANT")

# Suppression des branches
ECHECS=()
if git branch -d "$BRANCHE" >/dev/null 2>&1; then FAIT+=("suppression de la branche locale $BRANCHE")
else ECHECS+=("la branche locale $BRANCHE n'a pas pu être supprimée (git branch -d)"); fi
if git ls-remote --exit-code --heads "$DISTANT" "$BRANCHE" >/dev/null 2>&1; then
  if git push -q "$DISTANT" --delete "$BRANCHE" >/dev/null 2>&1; then FAIT+=("suppression de la branche distante $BRANCHE")
  else ECHECS+=("la branche distante $BRANCHE n'a pas pu être supprimée"); fi
fi
if [ ${#ECHECS[@]} -gt 0 ]; then
  refus 11 "branche non supprimée" "Le travail est fusionné et poussé dans $PRINCIPALE." "${ECHECS[@]}"
fi

# Mise à jour du dossier d'exécution (jamais avant le push)
SORTIE_RUN=$(bash "$SCRIPT_DIR/run_worktree.sh" update 2>&1); CODE_RUN=$?
if [ "$CODE_RUN" -eq 4 ] && printf '%s' "$SORTIE_RUN" | grep -q "absent"; then
  info "dossier d'exécution absent, rien à mettre à jour"
elif [ "$CODE_RUN" -ne 0 ]; then
  CAUSES=()
  while IFS= read -r ligne; do
    [ -n "$ligne" ] || continue
    case "$ligne" in "Pour le relancer plus tard"*) continue ;; esac
    CAUSES+=("$ligne")
  done <<< "$SORTIE_RUN"
  refus 13 "dossier d'exécution non mis à jour" "La fusion est faite et poussée dans $PRINCIPALE." "${CAUSES[@]}" \
    "Pour le mettre à jour : bash tools/run_worktree.sh update"
else
  FAIT+=("mise à jour du dossier d'exécution")
  RAPPEL="serveur de la bibliothèque : l'ancien code reste chargé jusqu'à la prochaine session"
fi

info "terminé"
for ligne in "${FAIT[@]}"; do printf '  - %s\n' "$ligne"; done
[ -z "${RAPPEL:-}" ] || printf '%s\n' "$RAPPEL"
exit 0
