#!/bin/bash
# Termine la branche courante : vérifie, lance le runner complet, fusionne dans main (sans avance rapide), pousse main,
# supprime la branche locale (suppression sûre) puis la branche distante si elle existe.
# À lancer par l'utilisateur dans le Terminal, depuis le workspace (jamais depuis une session Claude Code : voir les règles deny).
#
#     bash tools/finish_branch.sh                   termine la branche courante
#     bash tools/finish_branch.sh --check <branche>   vérifie seulement, pour la branche nommée
#     bash tools/finish_branch.sh --help            affiche ce que le script vérifie et fait
#
# Les vérifications se font dans l'ordre de la table des codes ; la première qui refuse arrête le script avant tout changement de branche.
# Codes : 0 terminé ; 1 tests en échec ; 2 usage ; 15 une autre fin de branche est en cours (verrou, change multi-session-piloting : refus immédiat, jamais
#         d'attente ; contrôlé juste après l'usage, jamais en mode vérification) ;
#         17 fenêtre du matin, état du matin non vérifié (change morning-guard : bash tools/morning_state.sh check refuse ; contrôlé juste après
#            le verrou et avant le 3, jamais en mode vérification, aucune variable ne l'écarte ; rien n'est changé) ;
#         19 la branche touche un autre change OpenSpec actif (finish-under-lock D6 ; après le 4 et avant le 5, aussi en mode vérification ;
#            exempt : branche de spécification, branche lot/*) ;
#         3 aucune branche à terminer (ou branche spike/*) ; 4 arbre non propre ; 5 change OpenSpec non archivé ;
#         6 jeu d'essai validant absent ; 7 main pas à jour ; 8 la branche ne contient pas main ;
#         9 fusion impossible (annulée) ; 10 push refusé ; 11 branche non supprimée (le travail est fusionné) ;
#         12 main est ouvert dans un autre dossier (worktree), refus avant toute fusion ;
#         13 fusion faite et poussée, mais dossier d'exécution non mis à jour (modifications locales, hors de l'historique de main,
#            verrou de la veille ou fenêtre horaire, dépendances non préparées) ;
#         14 passage vert de tools/dbtest.sh absent pour l'arbre du sommet alors que le code de la base a changé (CHEMINS_BASE ; aucune
#            variable ne l'écarte ; vérifié après le 6 et avant le 7, aussi en mode vérification) ;
#         18 chemin allégé d'une branche de spécification : openspec validate --strict en échec, rien n'est fusionné (change light-spec-finish ;
#            vérifié au lancement, après le 12 et avant le 1, jamais en mode vérification). Le code 16 reste réservé
#            (mothra-slices).
# Les codes 9 à 11 et 13 arrivent après un changement et disent l'état laissé.
#
# Chemin allégé (change light-spec-finish, D1 à D5) : une branche qui ne change que des fichiers ordinaires sous openspec/ (test strict de
# tools/light_finish.sh), dont l'arbre de main est dans l'enregistrement pmzilla-main-validated du dossier Git commun (moins de 8 jours, même
# signature d'environnement) et sans variable de relance forcée, remplace le runner complet par tools/light_validate.py
# (éléments OpenSpec touchés, nouveaux avertissements stricts seulement) puis les suites qui lisent openspec/ (tools/select_suites.py --openspec-readers). Toute autre branche garde le runner complet,
# avec la raison sur une ligne quand la branche est une branche de spécification. Après un push réussi, le script enregistre l'arbre du nouveau
# main (genre complet ou allégé) ; il écrit aussi l'empreinte allégée pmzilla-light-ok (dossier Git privé du worktree) que le hook pre-push
# accepte après avoir revérifié les mêmes conditions. Le mode vérification n'en fait rien.
# Mode vérification seule (--check <branche>) : les refus 3, 4, 19, 5, 6, 14, 7, 8 et 12, dans cet ordre, avec les mêmes codes et les mêmes phrases,
# par les mêmes fonctions que la fin de branche ; sortie 0 avec une ligne de réussite. Il ne fusionne pas, ne pousse pas, ne supprime pas de
# branche, n'avance jamais main local (le fetch seul ; un main local en retard est accepté), ne lance pas le runner, ne met pas à jour le
# dossier d'exécution, ne change pas de branche et ne modifie aucun fichier. Le code 7 y refuse un fetch en échec ou une divergence ;
# le code 8, une branche qui ne contient pas le plus avancé de main local et de main distant, suivi de l'aperçu de la fusion (« fusion de main prévue : sans conflit » ou « conflit sur <n> fichier(s) » et les chemins, calculé sur le sommet de la branche par tools/finish_merge.sh, sans rien changer).
# Après le push et la suppression des branches, le script lance « tools/run_worktree.sh update » (celui qui est à côté de lui) ;
# un dossier d'exécution absent est dit en une ligne, sans erreur.
#
# Interdit au script : push forcé, rebase, réécriture d'historique, résolution de conflit, --no-verify ou tout contournement de hook,
# la variable de contournement du lancement vert, suppression forcée de branche, lancement du jeu d'essai, remise à zéro ou nettoyage du dossier d'exécution.
#
# Variables (pour les tests de ce script) :
#   FINISH_BRANCH_RUNNER   commande du runner complet (défaut : bash tests/run_all.sh), lancée à la racine du dépôt
#   FINISH_BRANCH_VALIDATE commande de validation OpenSpec du chemin allégé (défaut : python3 -I tools/light_validate.py, qui ne valide en mode
#                          strict que les éléments touchés et ne refuse que les nouveaux avertissements ; change light-finish-touched-specs),
#                          lancée à la racine avec deux arguments (référence de main, sommet), entrée standard fermée ;
#                          la sortie 126 ou 127 (commande absente) donne le runner complet, raison « openspec introuvable »
#   LIGHT_VALIDATE_OPENSPEC commande OpenSpec lue par tools/light_validate.py (défaut : openspec) ; ne sert qu'aux tests
#   FINISH_BRANCH_LIGHT_RUNNER  commande du passage allégé (défaut : bash tests/run_all.sh), suivie des noms de suites du sélecteur
#   LIGHT_FINISH_TODAY     jour de l'horloge de la décision (AAAA-MM-JJ), lu par tools/light_finish.sh seul ; ne sert qu'aux tests
#   FINISH_BRANCH_TESTED_TOKEN  jeton à usage unique que pose tools/finish_worktree.sh : seul il fait lire la fiche de fin
#                          (pmzilla-finish-tested, dossier Git commun) et peut faire sauter le second runner complet ; sans lui, le
#                          script lance toujours son runner et ne touche ni à la fiche ni au fichier des durées
#   FINISH_BRANCH_CI_VERDICTS  fichier des verdicts de la CI locale (défaut : ci/verdicts du dossier de données du lab) ; lu seulement quand la
#                          fiche de fin porte passage=ci (change local-ci-container, D8) : une ligne « vert » pour l'arbre du sommet saute le second
#                          runner (« saut du second runner : verdict du conteneur et passe Mac »), sinon le runner tourne avec la raison « verdict du
#                          conteneur absent ou non vert pour l'arbre du sommet » ; jamais un refus, jamais un conteneur
#   FINISH_BRANCH_FORCE_RUN  toute valeur non vide (« 0 » et « non » comprises) force le runner complet : la variable ne peut que forcer,
#                          jamais faire sauter un lancement ; la fiche est tout de même lue puis effacée ; elle est prioritaire sur
#                          FINISH_WORKTREE_ALLOW_SKIP (raison journalisée « relance forcée »)
#   FINISH_WORKTREE_ALLOW_SKIP  réglage du lanceur (tools/finish_worktree.sh) : absent, vide ou exactement « 1 » (défaut) permet le saut du
#                          second runner complet, avec le jeton et une fiche valide ; toute autre valeur, par exemple « 0 » pour le
#                          couper, donne la raison « saut non autorisé (réglage désactivé) » : la fiche est lue puis effacée, le runner
#                          tourne, la raison est journalisée (ligne fin-relance). Ordre : relance forcée, saut non autorisé, puis les
#                          raisons de la fiche. Aucun code de sortie ajouté ni changé.
#   FINISH_BRANCH_RECORDS  dossier des enregistrements du jeu d'essai (défaut : le dossier « essais » du dossier de données,
#                          trouvé par le module partagé tools/lab_paths.sh)
#   FINISH_MORNING_CHECK   commande du garde-fou du matin (défaut : bash tools/morning_state.sh check, celui qui est à côté de ce script) ;
#                          un code non nul refuse avec 17. Réservée aux tests : elle remplace la commande, elle n'écarte jamais le refus.
#   FINISH_LOCK_TOKEN      jeton du verrou de fin de branche (tools/finish_lock.sh) : posé par tools/finish_worktree.sh, qui tient déjà le verrou
#                          (aucun second verrou, aucune libération ici) ; sinon le script prend le verrou pour toute sa durée, l'exporte sous ce
#                          nom pour le runner et les hooks, et le libère à la sortie quel que soit le résultat (jamais le verrou d'un autre jeton)
# Le script ne modifie aucun fichier, sauf l'avance rapide du dossier d'exécution et le verrou de fin de branche (dossier pmzilla-fin-en-cours du
# dossier Git commun, hors de tout fichier suivi).
set -u

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
NOM="finish_branch"
PRINCIPALE="main"
DISTANT="origin"
RUNNER="${FINISH_BRANCH_RUNNER:-bash tests/run_all.sh}"
VALIDATION="${FINISH_BRANCH_VALIDATE:-python3 -I '$SCRIPT_DIR/light_validate.py'}"   # light-finish-touched-specs D3 : suivi de la référence de main et du sommet
RUNNER_LEGER="${FINISH_BRANCH_LIGHT_RUNNER:-bash tests/run_all.sh}"
LIGHT_FINISH_DIR="$SCRIPT_DIR"
. "$SCRIPT_DIR/finish_merge.sh"   # aperçu de la fusion de main (finish-under-lock D10)
. "$SCRIPT_DIR/light_finish.sh"   # décision du chemin allégé et enregistrement de main (light-spec-finish D3)
ENREGISTREMENTS="${FINISH_BRANCH_RECORDS:-}"
MODE_VERIF=0      # 1 : vérification seule d'une branche nommée (--check)
CIBLE=""

# Chemins qui exigent un jeu d'essai validant (CLAUDE.md, postures, Critic, vocabulaire, mémoire figée des postures) : la liste partagée
# tests/postures/fichiers-evalues.txt du dépôt de ce script, lue par le contrôle 6 (posture-evals-on-branch-tip, D3, D7, D9). Aucun repli.
LISTE_JEU="$SCRIPT_DIR/../tests/postures/fichiers-evalues.txt"
CHEMINS_JEU=()

# Chemins du code de la base (test-speed-2, D4) : un changement sur la branche, depuis la base de fusion, exige un passage vert de
# tools/dbtest.sh enregistré pour l'arbre du sommet (refus 14). Motifs de chemin Git (« * » compris) : la migration et ses vues, le compose,
# la couche base et ses scripts (tools/db*, tools/flow_*), les modules d'outils que les tests avec base importent, les outils qui importent
# ou lancent la base (psycopg, couche db, docker compose, scripts db_*.sh), puis les fichiers de test qui utilisent une base et leurs aides.
# Le test statique tests/db/test_couverture_base.py garde cette liste à jour (R-85 : les outils qui touchent la base, pas seulement les tests).
# Le motif « posture_eval* » (et non le nom complet du module) évite que le test de ce script prenne la liste pour le lancement du jeu d'essai.
CHEMINS_BASE=(
  "db/" "docker-compose.yml" "tools/db*" "tools/flow_*"
  "tools/book_usage.py" "tools/cases_store.py" "tools/dashboard.py" "tools/dependencies_jira.py" "tools/export_jira_api.py" "tools/export_jira_api_equipes.py"
  "tools/epic_statuses.py" "tools/export_jira_api_messages.py" "tools/flux_jira.py" "tools/history_common.py" "tools/history_jira.py" "tools/history_store.py" "tools/hybrid_search.py" "tools/identifiants_personnels.py" "tools/journal_lab.py" "tools/knowledge_library.py"
  "tools/library_parity.py" "tools/messages.py" "tools/pmzilla_lab_library.py" "tools/posture_eval*" "tools/sensitive_names.py"
  "tools/watch_lab.py" "tools/watch_paths.py" "tools/watch_store.py" "tools/watch_triage.py"
  "tools/cases_calibration.py" "tools/morning_summary.py" "tools/offsite_backup.sh" "tools/com.pmzilla.db-backup.plist"
  "tools/install_lab_check.py" "tools/install_lab_context.py" "tools/install_lab_database.py"
  "tests/db/" "tests/fixtures_library/"
  "tests/book_usage/test_book_usage_db.py"
  "tests/cases_store/test_cases_store.py" "tests/cases_store/test_load_fixture.py"
  "tests/dashboard/test_dashboard_db.py"
  "tests/flow_import/test_derivation_base.py" "tests/flow_import/test_reconstruction_base.py"
  "tests/history_jira/test_magasin_base.py" "tests/story_quality/test_magasin_base.py" "tools/story_quality_store.py"
  "tests/story_quality/test_magasin_analyse_base.py" "tools/story_quality_audit_store.py"
  "tests/export_jira_api/aide_couche_brute.py" "tests/export_jira_api/test_couche_brute.py" "tests/export_jira_api/test_couche_brute_base.py"
  "tests/export_jira_api/test_export_jira_api.py" "tests/export_jira_api/test_equipes_vues_base.py" "tests/export_jira_api/test_referentiel_et_etiquettes.py"
  "tests/flow_retention/test_base.py" "tests/flow_retention/test_couche_brute_base.py"
  "tests/flow_store/aide_base.py" "tests/flow_store/aide_scripts.py" "tests/flow_store/test_couverture_historique.py" "tests/flow_store/test_flow_store.py"
  "tests/flow_store/test_lecteur_epics.py" "tests/flow_store/test_lecteurs_cycles.py"
  "tests/flow_store/test_sortis_de_l_export.py" "tests/flow_store/test_erreurs_scripts.py"
  "tests/flow_views/test_flow_views.py"
  "tests/hybrid_search/test_filtre_avant_limite.py" "tests/hybrid_search/test_hybrid_search.py" "tests/hybrid_search/test_hybrid_search_sans_tsvector.py"
  "tests/library_backend/pg_demo.py" "tests/library_backend/test_backend.py"
  "tests/pmzilla_lab_library/test_figures.py" "tests/pmzilla_lab_library/test_pmzilla_lab_library.py" "tests/pmzilla_lab_library/test_probe.py"
  "tests/posture_eval*/test_cases_fixture.py" "tests/posture_eval*/test_prerequis_base.py"
  "tests/watch_store/test_contract.py"
)

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
$NOM : usage : bash tools/finish_branch.sh [--help | --check <branche>]
Termine la branche courante, depuis le workspace, dans le Terminal. Aucun autre argument que --check suivi d'une branche.
Avec --check <branche> : vérification seule des refus 3, 4, 19, 5, 6, 14, 7, 8 et 12 pour la branche nommée (même ordre, mêmes codes), sortie 0 si tous passent ;
rien n'est fusionné, poussé, supprimé ni avancé (main local n'est jamais déplacé), le runner complet n'est pas lancé.
Vérifications, dans cet ordre (la première qui refuse arrête le script, sans rien changer) :
  15 aucune autre fin de branche n'est en cours (verrou pmzilla-fin-en-cours du dossier Git commun, pris pour toute la durée du script et
     libéré à la sortie ; refus immédiat, jamais d'attente ; pas en mode --check ; sans objet quand FINISH_LOCK_TOKEN est celui du verrou)
  17 le garde-fou du matin permet la fin (bash tools/morning_state.sh check : avant la fenêtre du matin, ou veille terminée sans erreur,
     sauvegarde du jour complète et copie hors du Mac du jour prouvée ou reportée par déclaration) ; pas en mode --check ; aucune variable
     ne l'écarte ; rien n'est changé en cas de refus
  3  il y a une branche à terminer (ni main, ni tête détachée, ni hors dépôt, ni branche spike/*)
  4  l'arbre de travail est propre (fichiers non ignorés compris)
  19 la branche ne touche aucun change OpenSpec actif autre que le sien (une branche de spécification, une branche de train lot/* et l'archive d'un autre change sont permises)
  5  aucun change OpenSpec lié à la branche n'est resté non archivé (une branche qui ne change que openspec/ est une branche de spécification)
  6  un jeu d'essai validant est enregistré pour le sommet de la branche si CLAUDE.md, une posture, Critic, le vocabulaire ou la mémoire figée ont changé
  14 un passage vert de tools/dbtest.sh est enregistré pour l'arbre du sommet si le code de la base a changé
  7  main est à jour depuis le distant (avance rapide seulement)
  8  la branche contient main à jour
  12 main n'est pas déjà ouvert dans un autre dossier (worktree) : sinon, la fusion serait impossible
  18 chemin allégé (branche qui ne change que des fichiers ordinaires sous openspec/, arbre de main enregistré comme validé depuis 7 jours au plus,
     même signature d'environnement, relance forcée non posée) : tools/light_validate.py ne trouve aucun nouvel avertissement strict ; sinon rien n'est fusionné
  1  le runner complet des tests est vert sur la branche (remplacé, sur le chemin allégé, par les suites qui lisent openspec/ ; sauté seulement si la fiche de fin de tools/finish_worktree.sh correspond : même
     jeton, branche, sommet, arbre, arbre fusionné prévu et environnement, et seulement si FINISH_WORKTREE_ALLOW_SKIP est absent, vide ou exactement 1 (la valeur 0 coupe le saut) ;
     la variable de relance forcée ne peut que forcer le lancement)
Puis : fusion de la branche dans main sans avance rapide, push de main, suppression de la branche locale (sûre) et de la branche distante,
puis mise à jour du dossier d'exécution par tools/run_worktree.sh update (absent : une ligne d'information).
Codes de sortie : 0 terminé ; 1 tests en échec ; 2 usage ; 15 une autre fin de branche est en cours ; 3 à 8, 14 et 19 refus ci-dessus (19 : la branche touche un autre change OpenSpec) ; 17 fenêtre du matin, état du matin non vérifié ; 9 fusion impossible (annulée) ;
10 push refusé (la fusion n'existe que sur main local) ; 11 branche non supprimée (le travail est fusionné) ;
12 main est ouvert dans un autre dossier (refus avant toute fusion, avec la manoeuvre) ;
13 fusion faite et poussée, dossier d'exécution non mis à jour (relancer : bash tools/run_worktree.sh update) ;
18 passage allégé : openspec validate --strict en échec (rien n'est fusionné).
Après un push réussi, le script enregistre l'arbre du nouveau main comme validé (genre complet ou allégé) dans le dossier Git commun.
Le script ne force rien, ne rebase pas, ne contourne aucun hook, ne lance pas le jeu d'essai et ne modifie aucun fichier, sauf l'avance rapide du dossier d'exécution.
EOF
}

# 2. usage
if [ $# -gt 0 ]; then
  if [ $# -eq 1 ] && { [ "$1" = "--help" ] || [ "$1" = "-h" ]; }; then aide; exit 0; fi
  if [ $# -eq 2 ] && [ "$1" = "--check" ] && [ -n "$2" ]; then MODE_VERIF=1; CIBLE=$2
  else refus 2 "usage : bash tools/finish_branch.sh [--help | --check <branche>] (aucun autre argument)"; fi
fi

# 15. une seule fin de branche à la fois (change multi-session-piloting, D5 et D6) : le verrou est pris ici, pour toute la durée du script,
# sauf en mode vérification (qui ne le prend ni ne le lit) et sauf quand l'appelant porte le jeton du verrou (lancé par finish_worktree.sh).
# Le piège de sortie le libère quel que soit le résultat, l'interruption ou la fermeture de la fenêtre ; il ne retire que son propre verrou.
. "$SCRIPT_DIR/finish_lock.sh"
if [ "$MODE_VERIF" -eq 0 ]; then
  COMMUN_VERROU=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || COMMUN_VERROU=""
  if [ -n "$COMMUN_VERROU" ]; then
    finish_lock_acquire "$COMMUN_VERROU" "$(git symbolic-ref -q --short HEAD 2>/dev/null || echo '?')"; CODE_VERROU=$?
    case "$CODE_VERROU" in
      0) ;;
      1) refus 15 "une autre fin de branche est en cours (${FL_BRANCH:-?}, depuis $(finish_lock_hhmm "$FL_START"))" ;;
      *) refus 15 "verrou de fin de branche impossible à créer" "Le dossier Git commun n'accepte pas l'écriture ; rien n'est changé." ;;
    esac
    trap 'finish_lock_release' EXIT
    trap 'exit 129' HUP
    trap 'exit 130' INT
    trap 'exit 143' TERM
  fi
fi

# 17. garde-fou du matin (change morning-guard, D6) : dans la fenêtre du matin, pas de fin de branche tant que la veille, la sauvegarde et la
# copie hors du Mac du jour ne sont pas vérifiées. Normal run seulement (le mode vérification reste indépendant de l'heure) ; après l'usage et
# le verrou, avant le 3. Aucune variable, option ni réglage ne l'écarte ; rien n'est fusionné, poussé, lancé ni changé en cas de refus.
if [ "$MODE_VERIF" -eq 0 ]; then
  if [ -n "${FINISH_MORNING_CHECK:-}" ]; then
    SORTIE_MATIN=$(sh -c "$FINISH_MORNING_CHECK" </dev/null 2>&1); CODE_MATIN=$?
  else
    SORTIE_MATIN=$(bash "$SCRIPT_DIR/morning_state.sh" check </dev/null 2>&1); CODE_MATIN=$?
  fi
  [ "$CODE_MATIN" -eq 0 ] || refus 17 "fenêtre du matin, état du matin non vérifié" "$SORTIE_MATIN" "relancer quand l'état du matin est vérifié : bash tools/morning_state.sh check"
fi

# Les vérifications, une fonction chacune (safe-branch-finish D5, D6) : la fin de branche et --check les appellent dans le même ordre.
# Variables posées : RACINE, BRANCHE (à terminer), SOMMET (son sommet : HEAD, ou la branche nommée en mode vérification), BASE_FUSION, MODIFIES.

# 3. une branche à terminer
verif_3() {
  RACINE=$(git rev-parse --show-toplevel 2>/dev/null) || refus 3 "aucune branche à terminer" "Le script se lance depuis le dépôt du workspace."
  cd "$RACINE" || refus 3 "aucune branche à terminer" "Dépôt introuvable."
  if [ "$MODE_VERIF" -eq 1 ]; then
    BRANCHE=$CIBLE
    SOMMET=$(git rev-parse -q --verify "refs/heads/$BRANCHE^{commit}" 2>/dev/null)       || refus 3 "aucune branche à terminer" "La branche $BRANCHE n'existe pas en local."
  else
    BRANCHE=$(git symbolic-ref --short -q HEAD 2>/dev/null) || BRANCHE=""
    [ -n "$BRANCHE" ] || refus 3 "aucune branche à terminer" "La tête est détachée."
    SOMMET=HEAD
  fi
  if [ "$BRANCHE" = "$PRINCIPALE" ]; then
    if [ "$MODE_VERIF" -eq 1 ]; then refus 3 "aucune branche à terminer" "La branche à terminer est $PRINCIPALE."
    else refus 3 "aucune branche à terminer" "La branche courante est $PRINCIPALE."; fi
  fi
  case "$BRANCHE" in
    spike/*) refus 3 "branche spike/* refusée" "$BRANCHE est une préversion (spike), jamais fusionnée dans $PRINCIPALE : écarte-la ou renomme-la si elle doit vraiment être livrée." ;;
  esac
}

# 4. arbre propre (en mode vérification : l'arbre courant et, s'il existe, le worktree qui porte la branche nommée)
verif_4() {
  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    refus 4 "l'arbre n'est pas propre" "Des fichiers modifiés, indexés ou non suivis (hors fichiers ignorés) existent : commite-les ou écarte-les, puis relance."
  fi
  if [ "$MODE_VERIF" -eq 1 ]; then
    DOSSIER_BRANCHE=$(git worktree list --porcelain 2>/dev/null | awk -v ref="refs/heads/$BRANCHE" -v ici="$RACINE" '
      /^worktree / { dossier = substr($0, 10) }
      $0 == "branch " ref && dossier != ici { print dossier; exit }')
    if [ -n "$DOSSIER_BRANCHE" ] && [ -d "$DOSSIER_BRANCHE" ] && [ -n "$(git -C "$DOSSIER_BRANCHE" status --porcelain 2>/dev/null)" ]; then
      refus 4 "l'arbre n'est pas propre" "Le worktree de $BRANCHE a des fichiers modifiés, indexés ou non suivis (hors fichiers ignorés) : commite-les ou écarte-les, puis relance."
    fi
  fi
  BASE_FUSION=$(git merge-base "$PRINCIPALE" "$SOMMET" 2>/dev/null)     || refus 3 "aucune branche à terminer" "Base commune avec $PRINCIPALE introuvable."
  MODIFIES=$(git diff --name-only --no-renames "$BASE_FUSION" "$SOMMET")
}

# 19. une branche ne porte qu'un change (finish-under-lock, D6) : un chemin d'un dossier de change actif autre que le sien refuse ; une branche de
# spécification (que openspec/) et une branche de train (lot/*) sont exemptées ; l'archive d'un autre change est permise, avec une ligne.
verif_19() {
  local chemin nom court propre autres="" archives="" portes=""
  if [ -n "$MODIFIES" ] && [ -z "$(printf '%s\n' "$MODIFIES" | grep -v '^openspec/')" ]; then return 0; fi
  propre="${BRANCHE##*/}"
  while IFS= read -r chemin; do
    case "$chemin" in
      (openspec/changes/archive/*/*)
        nom=${chemin#openspec/changes/archive/}; nom=${nom%%/*}
        court=${nom#[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-}
        portes="$portes
$court"
        [ "$court" = "$propre" ] || archives="$archives
$nom" ;;
      (openspec/changes/archive/*) ;;   # un fichier directement sous l'archive (.gitkeep) : jamais un change actif (D6)
      (openspec/changes/*/*)
        nom=${chemin#openspec/changes/}; nom=${nom%%/*}
        portes="$portes
$nom"
        [ "$nom" = "$propre" ] || autres="$autres
$nom" ;;
    esac
  done <<EOM
$MODIFIES
EOM
  case "$BRANCHE" in
    (lot/*)
      portes=$(printf '%s\n' "$portes" | grep . | sort -u | paste -sd, - | sed 's/,/, /g')
      [ -z "$portes" ] || info "branche de train : changes portés : $portes"
      return 0 ;;
  esac
  archives=$(printf '%s\n' "$archives" | grep . | sort -u | paste -sd, - | sed 's/,/, /g')
  [ -z "$archives" ] || info "la branche modifie l'archive d'un autre change : $archives (permis)"
  autres=$(printf '%s\n' "$autres" | grep . | sort -u | paste -sd, - | sed 's/,/, /g')
  [ -z "$autres" ] || refus 19 "la branche touche un autre change OpenSpec : $autres" "une branche ne porte qu'un change ; déplace ce travail dans sa propre branche"
}

# 5. change OpenSpec lié non archivé (D2)
verif_5() {
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
    done < <(git ls-tree --name-only "$SOMMET" openspec/changes/ 2>/dev/null | sed 's|^openspec/changes/||')
    if [ -n "$NON_ARCHIVES" ]; then
      args=()
      for c in $NON_ARCHIVES; do args+=("  - $c"); done
      refus 5 "change OpenSpec non archivé" "Change(s) lié(s) à la branche, à archiver avant de terminer :" "${args[@]}"
    fi
  fi
}

# 6. jeu d'essai validant (D3)
verif_6() {
  CHEMINS_JEU=()   # spécifications de chemin Git depuis la racine ; lecture compatible avec le bash système 3.2, boucle read (D9)
  if [ -f "$LISTE_JEU" ]; then
    while IFS= read -r ligne || [ -n "$ligne" ]; do
      ligne=${ligne%$'\r'}; ligne=${ligne#"${ligne%%[![:space:]]*}"}; ligne=${ligne%"${ligne##*[![:space:]]}"}
      if [ -z "$ligne" ]; then continue; fi
      if [ "${ligne#\#}" != "$ligne" ]; then continue; fi
      CHEMINS_JEU[${#CHEMINS_JEU[@]}]=$ligne
    done < "$LISTE_JEU"
  fi
  [ "${#CHEMINS_JEU[@]}" -gt 0 ] || refus 6 "jeu d'essai validant absent" "liste des fichiers évalués absente ou vide"
  EXIGE=0
  for chemin in "${CHEMINS_JEU[@]}"; do
    if git diff --quiet --no-renames "$BASE_FUSION" "$SOMMET" -- "$chemin" 2>/dev/null; then :; else EXIGE=1; fi
  done
  [ "$EXIGE" -eq 1 ] || return 0
  if [ -z "$ENREGISTREMENTS" ]; then   # dossier de données par le module partagé (R-77), seulement quand il sert
    . "$SCRIPT_DIR/lab_paths.sh"
    lab_paths_init 2>/dev/null || refus 6 "jeu d'essai validant absent" "le dossier de données du lab est introuvable : les enregistrements du jeu d'essai ne peuvent pas être lus."
    ENREGISTREMENTS="$LAB_DATA_FOLDER/essais"
  fi
  EMPREINTE_ECHEC=0
  EMPREINTE_SOMMET=$(python3 -I "$SCRIPT_DIR/posture_eval_fingerprint.py" "$SOMMET" "${CHEMINS_JEU[@]}" 2>/dev/null) || { EMPREINTE_SOMMET=""; EMPREINTE_ECHEC=1; }
  # Lignes « date<TAB>base<TAB>réussies<TAB>total<TAB>empreinte » (« - » sans empreinte) des enregistrements complets, validants, non rejugés, en langue par défaut.
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
    lignes.append("\t".join([str(d.get("date", "?")), str(d["base"]), str(reussies), str(len(verifs)),
                             str(d.get("evaluated_fingerprint") or "-").replace("\t", " ")]))
print("\n".join(sorted(lignes)))
PYEOF
  ) || CANDIDATS=""
  TROUVE=""
  DISPARU=0
  while IFS=$'\t' read -r date base reussies total empreinte; do
    [ -n "${base:-}" ] || continue
    if [ "${empreinte:--}" != "-" ]; then   # un enregistrement qui porte une empreinte ne se compare que par elle, jamais par l'état testé (D4)
      if [ -n "$EMPREINTE_SOMMET" ] && [ "$empreinte" = "$EMPREINTE_SOMMET" ]; then TROUVE="$date ($reussies/$total) (empreinte des fichiers évalués)"; fi
      continue
    fi
    if ! git cat-file -e "${base}^{commit}" 2>/dev/null; then DISPARU=1; continue; fi
    differe=0
    for chemin in "${CHEMINS_JEU[@]}"; do
      git diff --quiet --no-renames "$base" "$SOMMET" -- "$chemin" 2>/dev/null || differe=1
    done
    [ "$differe" -eq 0 ] && TROUVE="$date ($reussies/$total)"
  done <<< "$CANDIDATS"
  if [ -z "$TROUVE" ]; then
    if [ "$EMPREINTE_ECHEC" -eq 1 ]; then
      refus 6 "jeu d'essai validant absent" "l'empreinte des fichiers évalués du sommet n'a pas pu être calculée (tools/posture_eval_fingerprint.py) : aucun passage ne peut être compté par empreinte." "Corrige l'outil ou la liste des fichiers évalués, puis relance."
    fi
    if [ "$DISPARU" -eq 1 ]; then
      refus 6 "jeu d'essai validant absent" "l'état testé n'existe plus : relance le jeu d'essai sur l'état commité de la branche."
    fi
    refus 6 "jeu d'essai validant absent" "CLAUDE.md, une posture, Critic, le vocabulaire ou la mémoire figée ont changé sans passage complet validant pour ce sommet." "Lance le jeu d'essai sur l'état commité, puis relance."
  fi
  info "jeu d'essai validant trouvé : $TROUVE"
}

# 14. passage vert de tools/dbtest.sh pour l'arbre du sommet quand le code de la base a changé (test-speed-2, D6). Aucune variable ne l'écarte.
# L'enregistrement est celui de tools/dbtest.sh (D5) : une ligne par arbre dans pmzilla-dbtest-ok, dossier Git commun. Aucun chemin de la liste
# modifié : rien n'est lu ni affiché.
verif_14() {
  local chemin exige=0 arbre fichier
  for chemin in "${CHEMINS_BASE[@]}"; do
    if git diff --quiet --no-renames "$BASE_FUSION" "$SOMMET" -- "$chemin" 2>/dev/null; then :; else exige=1; fi
  done
  [ "$exige" -eq 1 ] || return 0
  arbre=$(git rev-parse --verify -q "$SOMMET^{tree}" 2>/dev/null) || arbre=""
  fichier="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)/pmzilla-dbtest-ok"
  if [ -n "$arbre" ] && [ -f "$fichier" ] && grep -qx -- "$arbre" "$fichier" 2>/dev/null; then
    info "passage dbtest vert trouvé pour l'arbre du sommet"
    return 0
  fi
  refus 14 "passage dbtest vert absent" \
    "Le code de la base a changé sur la branche sans passage vert de tools/dbtest.sh pour l'arbre du sommet." \
    "Lance bash tools/dbtest.sh dans le worktree de la branche, arbre propre, après le dernier commit, puis relance."
}

# 7. main à jour depuis le distant. Fin de branche : avance rapide de main local si besoin. Vérification seule : fetch seul, main local jamais déplacé.
verif_7() {
  git fetch -q "$DISTANT" "$PRINCIPALE" 2>/dev/null || refus 7 "main n'est pas à jour" "Le fetch de $DISTANT $PRINCIPALE a échoué."
  DISTANTE=$(git rev-parse -q --verify FETCH_HEAD^{commit}) || refus 7 "main n'est pas à jour" "Le fetch de $DISTANT $PRINCIPALE a échoué."
  LOCALE=$(git rev-parse -q --verify "refs/heads/$PRINCIPALE") || refus 7 "main n'est pas à jour" "$PRINCIPALE local introuvable."
  REF_MAIN=$LOCALE   # le plus avancé de main local et de main distant, pour le refus 8 du mode vérification
  if git merge-base --is-ancestor "$DISTANTE" "$LOCALE"; then
    :   # main local est égal ou en avance : rien à rapatrier
  elif git merge-base --is-ancestor "$LOCALE" "$DISTANTE"; then
    REF_MAIN=$DISTANTE   # le plus avancé est main distant
    if [ "$MODE_VERIF" -eq 0 ]; then   # en mode vérification, main local en retard est accepté et laissé où il est
      git update-ref -m "$NOM : avance rapide de $PRINCIPALE" "refs/heads/$PRINCIPALE" "$DISTANTE" "$LOCALE" \
        || refus 7 "main n'est pas à jour" "L'avance rapide de $PRINCIPALE local a échoué."
    fi
  else
    refus 7 "main n'est pas à jour" "$PRINCIPALE local a divergé de $DISTANT/$PRINCIPALE : rapproche-les à la main (sans réécrire l'historique), puis relance."
  fi
}

# 8. la branche contient main à jour
verif_8() {
  git merge-base --is-ancestor "${REF_MAIN:-$PRINCIPALE}" "$SOMMET" && return 0
  # aperçu de la fusion (finish-under-lock D10), sur le sommet de la branche : jamais un changement de référence, d'index ni de fichier ; le code reste 8
  local apercu
  apercu=$(finish_merge_lines "${REF_MAIN:-$PRINCIPALE}" "$SOMMET")
  if [ -n "$apercu" ]; then
    refus 8 "la branche ne contient pas main" "Ramène $PRINCIPALE dans la branche d'abord (git merge $PRINCIPALE), relance les tests, puis relance." "$apercu"
  fi
  refus 8 "la branche ne contient pas main" "Ramène $PRINCIPALE dans la branche d'abord (git merge $PRINCIPALE), relance les tests, puis relance."
}

# 12. main ouvert dans un autre dossier (worktree) : la fusion y serait impossible, on refuse avant le runner
verif_12() {
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
}

verif_3; verif_4; verif_19; verif_5; verif_6; verif_14; verif_7; verif_8; verif_12

if [ "$MODE_VERIF" -eq 1 ]; then
  info "vérification seule : la branche $BRANCHE peut être terminée (le runner complet reste à lancer)"
  exit 0
fi

# L'empreinte allégée (pmzilla-light-ok, dossier Git privé du worktree) est effacée au début de toute fin normale (light-spec-finish, D5).
EMPREINTE_LEGERE=$(git rev-parse --path-format=absolute --git-path pmzilla-light-ok 2>/dev/null)
[ -z "$EMPREINTE_LEGERE" ] || rm -f "$EMPREINTE_LEGERE" 2>/dev/null

# Fiche de fin et fichier des durées (change test-speed, D5 à D11, D16, D17). Tout ce bloc ne sert que lancé par tools/finish_worktree.sh
# (FINISH_BRANCH_TESTED_TOKEN posé) ; lancé à la main, rien ne change : ni lecture de la fiche, ni ligne de raison, ni ligne de durées.
. "$SCRIPT_DIR/finish_env.sh"
SAUTE=0
FAIT=()
RAISON_SECOND=""
noter_bilan() { # genre secondes verdict raison : une ligne du fichier des durées (D17), sans branche, commit, arbre, jeton ni chemin
  local fichier="${RUN_ALL_DURATIONS:-}" donnees
  if [ -z "$fichier" ]; then
    [ -z "${FINISH_BRANCH_RUNNER+x}" ] || return 0   # un test du script n'écrit jamais dans le dossier de données du lab
    donnees=$( ( . "$SCRIPT_DIR/lab_paths.sh" 2>/dev/null && lab_paths_init 2>/dev/null && printf '%s' "$LAB_DATA_FOLDER" ) ) || donnees=""
    [ -n "$donnees" ] || { info "bilan de fin non enregistré (dossier de données introuvable)"; return 0; }
    fichier="$donnees/mesures/run_all-durees.tsv"
  fi
  local date_fin
  date_fin=$(date +%Y-%m-%dT%H:%M:%S)
  if [ ! -s "$fichier" ]; then
    ( umask 077; mkdir -p "$(dirname "$fichier")" ) 2>/dev/null \
      && printf 'lancement\tidentifiant\tgenre\tposte\tsuite\ttype\tsecondes\tsecondes_unittest\tverdict\traison\n' >> "$fichier" 2>/dev/null \
      || { info "bilan de fin non enregistré (écriture impossible)"; return 0; }
  fi
  printf '%s\t%s\t%s\tespace\t\t\t%s\t\t%s\t%s\n' "$date_fin" "$date_fin-$$" "$1" "$2" "$3" "$4" >> "$fichier" 2>/dev/null \
    || info "bilan de fin non enregistré (écriture impossible)"
}
SAUTE_CI=0
verdict_ci_vert() { # arbre : 0 si le fichier des verdicts (mode CI, D8 étape 5) a une ligne « vert » pour cet arbre exact ; sinon 1. Ne lance aucun conteneur et n'écrit rien.
  local fichier donnees contenu
  if [ -n "${FINISH_BRANCH_CI_VERDICTS:-}" ]; then
    fichier=$FINISH_BRANCH_CI_VERDICTS
  else
    donnees=$( ( . "$SCRIPT_DIR/lab_paths.sh" 2>/dev/null && lab_paths_init >/dev/null 2>&1 && [ -d "$LAB_DATA_FOLDER" ] && printf '%s' "$LAB_DATA_FOLDER" ) ) || donnees=""
    [ -n "$donnees" ] || return 1
    fichier="$donnees/ci/verdicts"
  fi
  contenu=$(cat "$fichier" 2>/dev/null) || return 1
  [ "$(printf '%s\n' "$contenu" | awk -F'\t' -v arbre="$1" '$1 == arbre && $2 == "vert" { n++ } END { print n + 0 }')" -gt 0 ]
}
if [ -n "${FINISH_BRANCH_TESTED_TOKEN:-}" ]; then
  FICHE="$(git rev-parse --path-format=absolute --git-common-dir)/pmzilla-finish-tested"
  CONTENU_FICHE=""; FICHE_PRESENTE=0
  if [ -e "$FICHE" ]; then FICHE_PRESENTE=1; CONTENU_FICHE=$(cat "$FICHE" 2>/dev/null); rm "$FICHE" 2>/dev/null; fi   # une seule lecture, quoi qu'il arrive
  champ_fiche() { printf '%s\n' "$CONTENU_FICHE" | sed -n "s/^$1=//p" | head -1; }
  ARBRE_TESTE=$(champ_fiche tree)
  if [ -n "${FINISH_BRANCH_FORCE_RUN:-}" ]; then RAISON_SECOND="relance forcée"
  elif [ "${FINISH_WORKTREE_ALLOW_SKIP:-1}" != "1" ]; then RAISON_SECOND="saut non autorisé (réglage désactivé)"   # saut permis par défaut (skip-default-on D1) : absent, vide ou exactement 1 le permet, toute autre valeur le désactive ; la fiche est lue et effacée plus haut, le runner tourne
  elif [ "$FICHE_PRESENTE" -eq 0 ]; then RAISON_SECOND="fiche de fin absente"
  elif [ "$(champ_fiche format)" != "1" ]; then RAISON_SECOND="fiche de fin illisible"
  elif [ "$(champ_fiche token)" != "$FINISH_BRANCH_TESTED_TOKEN" ]; then RAISON_SECOND="jeton différent"
  elif [ "$(champ_fiche branch)" != "$BRANCHE" ]; then RAISON_SECOND="autre branche"
  elif [ "$(champ_fiche tip)" != "$(git rev-parse HEAD)" ]; then RAISON_SECOND="autre sommet"
  elif [ "$ARBRE_TESTE" != "$(git rev-parse 'HEAD^{tree}')" ]; then RAISON_SECOND="arbre du sommet différent"
  else
    ARBRE_FUSION=$(git merge-tree --write-tree "$PRINCIPALE" HEAD 2>/dev/null) && ARBRE_FUSION=${ARBRE_FUSION%%$'\n'*} || ARBRE_FUSION=""
    case "$ARBRE_FUSION" in
      "") RAISON_SECOND="arbre fusionné non calculable" ;;
      "$ARBRE_TESTE") SIGNATURE_MAINTENANT=$(finish_env_signature 2>/dev/null) || SIGNATURE_MAINTENANT=""
                      if [ -z "$SIGNATURE_MAINTENANT" ] || [ "$SIGNATURE_MAINTENANT" != "$(champ_fiche env)" ]; then RAISON_SECOND="environnement différent"
                      elif [ "$(champ_fiche passage)" = "ci" ]; then   # mode CI (local-ci-container D8) : le verdict du conteneur de l'arbre du sommet remplace l'empreinte du runner
                        if verdict_ci_vert "$ARBRE_TESTE"; then SAUTE=1; SAUTE_CI=1; else RAISON_SECOND="verdict du conteneur absent ou non vert pour l'arbre du sommet"; fi
                      else SAUTE=1; fi ;;
      *) RAISON_SECOND="arbre fusionné différent" ;;
    esac
  fi
fi

# Chemin allégé (light-spec-finish, D4) : décidé par tools/light_finish.sh pour une branche de spécification seulement ; jamais combiné avec le
# saut du second runner (la fiche de fin, déjà lue et effacée, ne sert alors à rien) ; jamais en mode vérification (sorti plus haut).
ARBRE_VALIDE=$(git rev-parse 'HEAD^{tree}')
GENRE_VALIDE="complet"
LEGER=0
if [ "${BRANCHE_SPEC:-0}" -eq 1 ]; then
  DECISION=$(light_decision "$(git rev-parse -q --verify "refs/heads/$PRINCIPALE")" HEAD)
  case "$DECISION" in
    "allégé") LEGER=1; SAUTE=0 ;;
    complet*) info "runner complet nécessaire : ${DECISION#complet?}" ;;
  esac
fi
SANS_VARIABLES_RESERVEES="env -u PMZILLA_NO_EVALS -u PMZILLA_SKIP_GREEN_CHECK -u FINISH_BRANCH_TESTED_TOKEN -u FINISH_BRANCH_FORCE_RUN -u FINISH_WORKTREE_ALLOW_SKIP"
if [ "$LEGER" -eq 1 ]; then
  info "chemin allégé : la branche ne change que openspec/ et l'arbre de main est validé"
  $SANS_VARIABLES_RESERVEES sh -c "$VALIDATION \"\$@\"" _ "$(git rev-parse -q --verify "refs/heads/$PRINCIPALE")" "$(git rev-parse HEAD)" </dev/null
  CODE_VALIDATION=$?
  case "$CODE_VALIDATION" in
    0) ;;
    126|127) info "runner complet nécessaire : openspec introuvable"; LEGER=0 ;;
    *) refus 18 "openspec validate --strict en échec, rien n'est fusionné" "Corrige les specs de la branche, relance." ;;
  esac
fi
if [ "$LEGER" -eq 1 ]; then
  NOMS_LEGERS=$(light_suites) || { info "runner complet nécessaire : sélection des suites impossible"; LEGER=0; }
fi
if [ "$LEGER" -eq 1 ]; then
  $SANS_VARIABLES_RESERVEES sh -c "$RUNNER_LEGER $NOMS_LEGERS"
  CODE_LEGER=$?
  [ "$CODE_LEGER" -eq 0 ] || refus 1 "tests en échec, rien n'est fusionné" "(passage allégé)" "Corrige la branche, relance."
  NOMBRE_LEGERES=$(set -- $NOMS_LEGERS; echo $#)
  ( umask 077; printf '%s\n' "$ARBRE_VALIDE" > "$EMPREINTE_LEGERE" ) 2>/dev/null   # juste avant la fusion : le hook pre-push la revérifie
  GENRE_VALIDE=$(light_genre_leger)   # « allégé-forcé » si un faux runner a été posé : la ligne n'ouvre pas le chemin allégé à la branche suivante
  info "passage allégé vert : $NOMBRE_LEGERES suite(s) au lieu du runner complet"
  FAIT+=("passage allégé (validation OpenSpec et $NOMBRE_LEGERES suite(s)) au lieu du runner complet")
fi

# 1. runner complet vert sur la branche (jamais filtré, sans les variables réservées à git commit), sauf fiche de fin correspondante
if [ "$LEGER" -eq 1 ]; then
  :   # remplacé par le passage allégé ci-dessus
elif [ "$SAUTE" -eq 1 ]; then
  if [ "$SAUTE_CI" -eq 1 ]; then
    info "saut du second runner : verdict du conteneur et passe Mac (arbre $(printf '%s' "$ARBRE_TESTE" | cut -c1-12))"
    noter_bilan fin-saut "" "sauté" "verdict du conteneur et passe Mac"
  else
    info "runner complet déjà vert dans le worktree pour l'arbre fusionné : second lancement sauté"
    noter_bilan fin-saut "" "sauté" "arbre déjà testé dans le worktree"
  fi
  # Même fichier, même sens que celui du runner : un lancement complet vert a validé exactement cet arbre (D10). Jamais l'empreinte ciblée.
  git rev-parse --git-path pmzilla-run-all-ok | { read -r chemin_empreinte; printf '%s\n' "$ARBRE_TESTE" > "$chemin_empreinte"; }
  if [ "$SAUTE_CI" -eq 1 ]; then FAIT+=("runner complet sauté (verdict du conteneur et passe Mac)"); else FAIT+=("runner complet sauté (arbre déjà testé dans le worktree)"); fi
else
  [ -z "$RAISON_SECOND" ] || info "second lancement nécessaire : $RAISON_SECOND"
  info "lancement du runner complet sur $BRANCHE"
  DEBUT_RUNNER=$(finish_env_ms)
  env -u PMZILLA_NO_EVALS -u PMZILLA_SKIP_GREEN_CHECK -u FINISH_BRANCH_TESTED_TOKEN -u FINISH_BRANCH_FORCE_RUN -u FINISH_WORKTREE_ALLOW_SKIP sh -c "$RUNNER"   # les trois variables du saut ne doivent jamais atteindre le runner (test-speed-2, groupe 0)
  CODE_RUNNER=$?
  if [ -n "$RAISON_SECOND" ]; then
    DUREE_MS=$(( $(finish_env_ms) - DEBUT_RUNNER )); [ "$DUREE_MS" -ge 0 ] || DUREE_MS=0
    VERDICT_RUNNER="ok"; [ "$CODE_RUNNER" -eq 0 ] || VERDICT_RUNNER="échec"
    noter_bilan fin-relance "$(printf '%d.%d' $((DUREE_MS / 1000)) $(((DUREE_MS % 1000) / 100)))" "$VERDICT_RUNNER" "$RAISON_SECOND"
  fi
  [ "$CODE_RUNNER" -eq 0 ] || refus 1 "tests en échec, rien n'est fusionné" "Corrige la branche, relance."
fi

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
FAIT+=("fusion de $BRANCHE dans $PRINCIPALE (sans avance rapide)")
if [ "$SAUTE" -eq 1 ] && [ "$(git rev-parse 'HEAD^{tree}')" != "$ARBRE_TESTE" ]; then   # rempart (D8) : jamais attendu
  git rev-parse --git-path pmzilla-run-all-ok | { read -r chemin_empreinte; rm "$chemin_empreinte" 2>/dev/null; }
  printf '%s : %s\n' "$NOM" "arbre de la fusion différent de l'arbre testé : empreinte effacée, le hook pre-push relancera le runner complet" >&2
fi

# Push
if ! env -u PMZILLA_SKIP_GREEN_CHECK git push -q "$DISTANT" "$PRINCIPALE" >/dev/null 2>&1; then   # le hook pre-push ne doit jamais hériter du contournement du propriétaire (rempart D8)
  refus 10 "push refusé" "La fusion n'existe que sur $PRINCIPALE local ; tu es sur $PRINCIPALE." \
    "Pour réessayer le push : git push $DISTANT $PRINCIPALE" \
    "Pour défaire la fusion locale : git reset --hard $ANCIEN_MAIN"
fi
FAIT+=("push de $PRINCIPALE vers $DISTANT")
rm -f "$EMPREINTE_LEGERE" 2>/dev/null   # l'empreinte allégée ne survit pas à un push réussi (elle reste après le code 10, pour la commande de reprise)
# Enregistrement de l'arbre de main validé (light-spec-finish, D1) : seulement quand il est l'arbre que cette fin a validé (jamais attendu autrement)
if [ "$(git rev-parse "refs/heads/$PRINCIPALE^{tree}" 2>/dev/null)" = "$ARBRE_VALIDE" ]; then
  if record_main_validated "$ARBRE_VALIDE" "$GENRE_VALIDE"; then info "arbre de main enregistré comme validé ($GENRE_VALIDE)"
  else info "arbre de main non enregistré (écriture impossible)"; fi
fi

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
