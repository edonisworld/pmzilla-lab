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
# Tous les contrôles (codes 20 à 29) précèdent le retrait, dans l'ordre de la table des codes. Puis, toujours avant le retrait
# (change safe-branch-finish, D7, option B de la fiche Q3) : la vérification préalable (mode --check de tools/finish_branch.sh, codes 32 à 37),
# le runner complet dans le worktree (codes 38 et 40), puis la même vérification juste avant le retrait (mêmes codes 32 à 37).
# Aucun de ces contrôles n'est réimplémenté ici : les refus viennent du mode --check de tools/finish_branch.sh.
# Codes : 0 terminé ; 20 usage ; 42 une autre fin de branche est en cours (verrou, change multi-session-piloting : refus immédiat, jamais
#         d'attente ; pris juste après l'usage, dès que le dépôt est trouvé, donc avant tout autre contrôle) ; 21 hors du dépôt ; 22 main ou spike/* ; 23 branche introuvable ; 24 l'espace de travail n'est pas sur main ;
#         25 espace de travail pas propre ; 26 aucun worktree pour la branche (ou dossier absent) ; 27 lancé depuis le worktree à retirer ;
#         28 worktree pas propre ; 29 fichiers ignorés qui seraient perdus ; 30 retrait du worktree impossible ;
#         31 bascule de l'espace de travail impossible après le retrait ;
#         32 à 36 la fin de branche refuserait (--check : codes 5, 6, 7, 8, 12), rien n'est changé ; 41 la fin de branche refuserait faute de
#         passage vert de tools/dbtest.sh pour l'arbre du sommet (--check : code 14, test-speed-2 D7), rien n'est changé, refus avant le runner
#         et à la seconde vérification ; 37 vérification préalable impossible
#         (autre code du contrôle, ou lancement en échec), rien n'est changé ; 38 le runner complet n'est pas vert dans le worktree, rien
#         n'est changé ; 40 le sommet de la branche a bougé pendant le runner, rien n'est changé ; 39 réservé, jamais rendu ;
#         44 fenêtre du matin, état du matin non vérifié (change morning-guard : bash tools/morning_state.sh check refuse ; contrôlé juste après
#         le verrou, avant le 22, puis juste avant le retrait du worktree ; aucune variable ne l'écarte ; rien n'est changé : le worktree est encore
#         là, l'espace de travail sur main, le script de fin non lancé) ;
#         45 passage allégé : openspec validate --strict en échec dans le worktree, rien n'est changé (change light-spec-finish ; 43 reste
#         réservé, mothra-slices) ;
#         46 fusion de main dans la branche impossible (conflit prévu, ou fusion refusée puis annulée ; change finish-under-lock D3) ;
#         48 passage dbtest rouge (D4) ; 49 la fin de branche refuserait : la branche touche un autre change OpenSpec (--check : code 19, D6) ;
#         50 mode CI (FINISH_WORKTREE_CI=1, change local-ci-container D8) : le verdict enregistré du conteneur pour l'arbre fusionné est illisible, absent
#         ou rouge ; rien n'est changé (une fusion faite reste, et le dit), la ligne « lancer : bash tools/ci_local.sh run <branche> » est donnée.
#         Ce script ne lance jamais de conteneur et n'écrit jamais le fichier des verdicts.
#         Les codes 0 à 13, 17 et 18 de tools/finish_branch.sh sont transmis tels quels.
# Ordre (finish-under-lock D1) : usage, verrou, garde du matin, contrôles 21 à 29 ; puis, avant tout changement, la première vérification (les
# codes 0, 8 et 14 continuent ; 5, 6, 7, 12 et 19 refusent à l'instant) ; puis, si la branche ne contient pas le plus avancé de main local et de
# origin/main (un seul fetch ; main local n'est jamais déplacé ; un fetch en échec ou des main divergentes : aucune fusion, la vérification
# est refaite et refuse), l'aperçu de la fusion par tools/finish_merge.sh (conflit prévu : code 46, rien
# n'est lancé) et la fusion « git merge --no-edit » dans le worktree, entrée vide, jeton du verrou porté par l'environnement ; la vérification
# est refaite après une fusion (14 : passage de tools/dbtest.sh dans le worktree, entrée vide, jeton porté, remplaçable par FINISH_WORKTREE_DBTEST ;
# rouge : 48 ; vert : nouvelle vérification, 14 encore : 41) ; puis la décision allégée, le runner et la fiche de fin sur le sommet fusionné, la seconde
# vérification, la garde du matin, le retrait, la bascule et le script de fin. Une fusion faite reste dans la branche après un refus ultérieur,
# et chaque refus le dit. L'interruption (129, 130, 143) imprime « finish_worktree : interrompu (code <n>) : <état> » ; elle n'abandonne que
# une fusion que ce script a lancée et qui n'est pas terminée. Après le script de fin réussi, la ligne « terminé : main <avant> -> <après> »
# n'est écrite que si main local contient le sommet terminé.
# Les codes 30 et 31 arrivent après un changement et disent l'état laissé ; les codes 32 à 38, 40 et 41 arrivent avant tout changement : le
# worktree est encore là et listé, l'espace de travail sur main, le script de fin non lancé. Un code non nul du script de fin laisse le
# worktree retiré et l'espace de travail sur la branche ; le script le dit et, pour les codes 1 à 9 (branche non fusionnée), donne la recréation.
# Verrou de fin de branche (change multi-session-piloting, D5 et D6) : le script prend le verrou pmzilla-fin-en-cours du dossier Git commun
# (tools/finish_lock.sh) juste après l'usage, le tient pendant tous les contrôles, le runner, le retrait et la fin de branche, et le libère à
# la sortie, quel que soit le résultat (piège EXIT : fin normale, refus, échec, interruption, fenêtre fermée), seulement s'il porte son jeton. Le jeton est
# exporté dans FINISH_LOCK_TOKEN : le contrôle, le runner, tools/finish_branch.sh et leurs hooks le portent, donc le gel du lanceur de tests
# et du hook pre-commit ne les refuse pas ; il n'est jamais affiché. Un verrou périmé est dit (« verrou de fin périmé, repris ») puis remplacé.
# Après une sortie 0, la note de passage de relais de la branche (tools/pilot.py note, dossier pmzilla-notes du dossier Git commun) est retirée ;
# après toute autre sortie, elle reste.
#
# Passage allégé (change light-spec-finish, D2, D3, D7, D8) : avant son lancement dans le worktree, le script prend, par tools/light_finish.sh,
# la même décision que tools/finish_branch.sh (branche qui ne change que des fichiers ordinaires sous openspec/, arbre de main enregistré comme
# validé depuis 7 jours au plus avec la même signature d'environnement, variable de relance forcée non posée ; main est le plus
# avancé de main local et de origin/main, et leur divergence donne le runner complet). Allégé : il lance dans le worktree tools/light_validate.py
# (éléments OpenSpec touchés, nouveaux avertissements stricts seulement) puis les suites qui lisent openspec/ ; aucune fiche de fin n'est écrite (elle atteste un runner complet), le script de fin
# refait le passage allégé. Complet : comme avant, avec la ligne « runner complet nécessaire : <raison> » pour une branche de spécification.
# La variable de relance forcée de tools/finish_branch.sh n'est lue ici que pour cette décision.
#
# Fiche de fin (change test-speed, D5 à D9, D11) : avant le runner, toute fiche restée dans le dossier Git commun est effacée ; après le
# runner vert et le sommet inchangé, la fiche pmzilla-finish-tested (format, branche, sommet, arbre, signature d'environnement, jeton,
# date ; propriétaire seul, écrite par renommage, aucun chemin) est écrite seulement si le réglage FINISH_WORKTREE_ALLOW_SKIP est absent, vide ou exactement 1
# (permise par défaut, skip-default-on D1 ; toute autre valeur, par exemple 0 : aucune fiche et la ligne « saut non autorisé (réglage désactivé) ») ET si l'empreinte complète que le runner a écrite dans le
# worktree égale l'arbre du sommet ET si le worktree n'a pas bougé pendant le runner (propre au démarrage et à l'écriture, aucun fichier
# suivi, ni aucun dossier du worktree (la racine et chaque dossier qui contient un fichier suivi, test-db-guards D2), au changement d'état (ctime) plus
# récent qu'un repère posé avant le runner hors de l'arbre de travail, même remis en état : un dossier renommé puis remis, un fichier non suivi créé
# puis supprimé sont vus ; aucun chemin n'est affiché). Le jeton (128 bits) est passé au script de fin par FINISH_BRANCH_TESTED_TOKEN, jamais affiché. Le script
# n'écrit aucune empreinte et ne lit jamais la variable de relance forcée de tools/finish_branch.sh (elle lui parvient telle quelle).
#
# Processus dans le worktree (test-speed-2, D12 et D13, idée #285) : la fiche n'est écrite que si, juste avant le runner et juste après, aucun autre
# processus n'a son dossier courant dans le worktree (lsof -w -n -P -d cwd -F pn ; le worktree ou un dossier dedans ; hors le processus de ce script).
# Un processus trouvé, ou une vérification impossible (lsof absent, code non nul, liste qui ne nomme pas ce script), supprime la fiche avec une ligne
# dédiée, après les conditions (b) et (c) et avant l'empreinte et le réglage ; aucun code n'est ajouté ; le script ne signale, n'attend ni ne nomme
# ces processus (ni numéro ni commande). Il ne voit pas : une action par chemin absolu depuis un autre dossier, un processus qui commence et finit
# entre les deux listages, les processus d'un autre utilisateur, un dossier tenu ouvert sans en être le dossier courant, les machines virtuelles
# de conteneurs, un processus dont le dossier courant a été déplacé hors du worktree.
#
# Interdit au script : forcer le retrait, élaguer les worktrees, contourner un hook ou le lancement vert, pousser, fusionner autre chose
# que main dans la branche (D3 : une seule fusion, dans le worktree, et son abandon),
# réinitialiser, remettre de côté, valider, supprimer une branche, revenir en arrière, relancer, lire ou lister un fichier ignoré
# (compte et dossier de premier niveau seulement), filtrer ou cibler le runner, écrire une empreinte de fin de branche.
#
# Variables (pour les tests de ce script) :
#   FINISH_WORKTREE_FINISH   commande de fin de branche (défaut : bash tools/finish_branch.sh), lancée dans l'espace de travail,
#                            entrée standard sur /dev/null
#   FINISH_WORKTREE_CHECK    commande de vérification (défaut : bash tools/finish_branch.sh --check), lancée dans l'espace de travail
#                            avec la branche en argument, entrée standard sur /dev/null
#   FINISH_MORNING_CHECK     commande du garde-fou du matin (défaut : bash tools/morning_state.sh check, celui qui est à côté de ce script) ;
#                            un code non nul refuse avec 44. Réservée aux tests : elle remplace la commande, elle n'écarte jamais le refus.
#   FINISH_WORKTREE_RUNNER   commande du runner complet (défaut : bash tests/run_all.sh), lancée dans le worktree, entrée standard sur /dev/null,
#                            sans la variable réservée à git commit ni la variable de contournement du propriétaire
#   FINISH_WORKTREE_VALIDATE commande de validation OpenSpec du passage allégé (défaut : python3 -I tools/light_validate.py, éléments touchés et
#                            nouveaux avertissements stricts seulement ; change light-finish-touched-specs), lancée dans le worktree avec deux
#                            arguments (référence de main, sommet), entrée standard sur /dev/null ; la sortie 126 ou 127 donne le runner complet, raison « openspec introuvable »
#   FINISH_WORKTREE_LIGHT_RUNNER  commande du passage allégé (défaut : bash tests/run_all.sh), lancée dans le worktree, suivie des noms de suites
#   FINISH_WORKTREE_DBTEST   commande du passage de la base jetable (défaut : bash tools/dbtest.sh, sans argument), lancée dans le worktree,
#                            entrée standard sur /dev/null, jeton du verrou porté par l'environnement ; un code non nul donne 48
#   FINISH_WORKTREE_CI       exactement « 1 » : mode CI (D8), chemin complet seulement ; lit le verdict enregistré de l'arbre fusionné, puis lance la
#                            passe Mac (FINISH_WORKTREE_RUNNER suivi de --mac) au lieu du runner complet ; la fiche gagne passage=ci et image=<clé>
#   FINISH_WORKTREE_CI_VERDICTS  fichier des verdicts (défaut : ci/verdicts du dossier de données du lab) ; réservée aux tests
#   FINISH_WORKTREE_ALLOW_SKIP  absent, vide ou exactement « 1 » (défaut) autorise ce script à écrire la fiche de fin, donc à laisser
#                            tools/finish_branch.sh sauter son second runner complet ; toute autre valeur (« 0 » pour le couper, « oui »,
#                            « 11 », une espace) désactive le saut : aucune fiche, la ligne « saut non autorisé (réglage désactivé) », le
#                            jeton passé quand même. Dans ce cas tools/finish_branch.sh relance son runner et journalise la raison « saut
#                            non autorisé (réglage désactivé) » (fin-relance), sauf si FINISH_BRANCH_FORCE_RUN est posée : « relance
#                            forcée » est alors prioritaire.
#                            Les autres conditions (empreinte, worktree stable, signature) sont inchangées quand le saut est permis.
set -u

NOM="finish_worktree"
. "$(cd "$(dirname "$0")" && pwd)/finish_env.sh"   # signature d'environnement (test-speed D9)
. "$(cd "$(dirname "$0")" && pwd)/finish_lock.sh"  # verrou de fin de branche (multi-session-piloting D5)
PRINCIPALE="main"
FIN="${FINISH_WORKTREE_FINISH:-bash tools/finish_branch.sh}"
VERIF="${FINISH_WORKTREE_CHECK:-bash tools/finish_branch.sh --check}"
RUNNER="${FINISH_WORKTREE_RUNNER:-bash tests/run_all.sh}"
VALIDATION="${FINISH_WORKTREE_VALIDATE:-python3 -I '$(cd "$(dirname "$0")" && pwd)/light_validate.py'}"   # light-finish-touched-specs D3
RUNNER_LEGER="${FINISH_WORKTREE_LIGHT_RUNNER:-bash tests/run_all.sh}"
LIGHT_FINISH_DIR=$(cd "$(dirname "$0")" && pwd)
. "$LIGHT_FINISH_DIR/light_finish.sh"   # décision du chemin allégé, la même que celle du script de fin (light-spec-finish D3)
. "$LIGHT_FINISH_DIR/finish_merge.sh"   # aperçu de la fusion de main, le même que celui du script de fin (finish-under-lock D10)
DBTEST="${FINISH_WORKTREE_DBTEST:-bash tools/dbtest.sh}"
MERGE_ETAT="aucune"   # aucune | en_cours (lancée par ce script, pas terminée) | faite (jusqu'au retrait du worktree)
APRES_RETRAIT=0
FIN_LANCEE=0

refus() { # code message... : écrit sur la sortie d'erreur et sort
  code=$1; shift
  printf '%s : %s\n' "$NOM" "$1" >&2
  # une fusion faite reste dans la branche : tout refus avant le retrait le dit sur la ligne qui suit sa phrase (finish-under-lock D3)
  if [ "$MERGE_ETAT" = "faite" ] && [ "$APRES_RETRAIT" -eq 0 ]; then
    printf '%s\n' "main est fusionnée dans la branche ; rien d'autre n'est changé" >&2
  fi
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
  42  aucune autre fin de branche n'est en cours (verrou pmzilla-fin-en-cours du dossier Git commun, tenu jusqu'à la sortie ; refus immédiat,
      jamais d'attente ; pris dès que le dépôt est trouvé, avant les contrôles suivants)
  44  le garde-fou du matin permet la fin (bash tools/morning_state.sh check, pris après le verrou puis juste avant le retrait ; aucune
      variable ne l'écarte ; rien n'est changé en cas de refus)
  21  le dossier courant est dans un dépôt Git
  22  la branche n'est ni main ni spike/*
  23  la branche existe en local
  24  l'espace de travail est sur main
  25  l'espace de travail est propre (fichiers non ignorés compris)
  26  un worktree autre que l'espace de travail tient la branche, et son dossier existe
  27  le script n'est pas lancé depuis le worktree à retirer
  28  le worktree est propre (fichiers non ignorés compris)
  29  le worktree ne tient pas de fichier ignoré qui serait perdu (réglage local, __pycache__, .pyc et .DS_Store exceptés)
Puis, avant tout retrait : la vérification préalable (tools/finish_branch.sh --check, lancé dans l'espace de travail avec la branche ; les codes 0, 8 et 14
continuent, les autres refusent à l'instant), la fusion du plus avancé de main local et de origin/main dans la branche si elle ne le contient pas (aperçu
d'abord, puis git merge --no-edit dans le worktree, entrée vide), la vérification refaite après une fusion (14 : passage de tools/dbtest.sh dans le worktree,
puis nouvelle vérification), le runner complet des tests dans le worktree sur le sommet fusionné, puis la même vérification juste avant le retrait. Un refus
arrête le script sans rien changer, sauf une fusion déjà faite, que la phrase du refus dit (« main est fusionnée dans la branche ; rien d'autre n'est changé ») :
  32  la fin de branche refuserait : change OpenSpec non archivé
  33  la fin de branche refuserait : jeu d'essai validant absent
  34  la fin de branche refuserait : main n'est pas à jour
  35  la fin de branche refuserait : la branche ne contient pas main
  36  la fin de branche refuserait : main est ouvert dans un autre dossier
  41  la fin de branche refuserait : passage dbtest vert absent
  49  la fin de branche refuserait : la branche touche un autre change OpenSpec
  37  vérification préalable impossible (autre code du contrôle, ou lancement en échec)
  46  fusion de main dans la branche impossible (conflit prévu sur <n> fichier(s), ou fusion refusée puis annulée) : rien n'est changé
  48  passage dbtest rouge (avec son code), après la fusion de main, la fusion reste dans la branche
  38  le runner complet n'est pas vert dans le worktree (avec son code ; sur le chemin allégé, une suite qui lit openspec/ n'est pas verte)
  45  chemin allégé : openspec validate --strict est en échec dans le worktree
  39  réservé, jamais rendu
  40  le sommet de la branche a changé pendant le runner
  50  mode CI (FINISH_WORKTREE_CI=1) : verdict du conteneur illisible, absent ou rouge pour l'arbre fusionné ; la fin donne
      « lancer : bash tools/ci_local.sh run <branche> (depuis le worktree), puis relancer la fin » ; la passe Mac suit un verdict vert (38 si rouge)
Puis : retrait du worktree (git worktree remove, sans force), bascule de l'espace de travail sur la branche, puis lancement de
tools/finish_branch.sh dans l'espace de travail (entrée vide), qui relance le runner complet sauf si la fiche de fin correspond (la fiche n'est écrite que si FINISH_WORKTREE_ALLOW_SKIP est absent, vide ou exactement 1 ; la valeur 0 coupe le saut) ; le code de ce script est transmis tel quel.
Codes de sortie : 0 terminé ; 20 usage ; 42 une autre fin de branche est en cours ; 21 à 29 refus ci-dessus ; 44 fenêtre du matin, état du matin non vérifié ; 30 retrait du worktree impossible (rien d'autre n'est changé) ;
  31 bascule impossible après le retrait (le worktree est retiré, l'espace de travail est sur main, avec la commande de recréation) ;
  32 à 38, 40, 41, 45, 46, 48, 49 et 50 refus ci-dessus (le worktree est encore là, l'espace de travail sur main ; seule une fusion de main déjà faite reste, 46 la défait) ;
  39 réservé, jamais rendu ;
les codes 0 à 13, 17 et 18 de tools/finish_branch.sh sont transmis, avec l'état laissé ; pour les codes 1 à 9, 17 et 18, la commande de recréation du worktree.
Chemin allégé (branche de spécification dont l'arbre de main est validé) : à la place du runner complet, tools/light_validate.py (éléments touchés, nouveaux avertissements stricts) puis les
suites qui lisent openspec/ ; le script de fin refait ce passage allégé (aucune fiche de fin). Sinon, runner complet, avec la raison sur une ligne.
Le script ne force rien, n'élague rien, ne contourne aucun hook, ne pousse pas, ne fusionne que main dans la branche (dans le worktree), et ne
revient jamais en arrière, sauf l'abandon d'une fusion qu'il a lui-même lancée.
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

# 42. une seule fin de branche à la fois (multi-session-piloting, D5 et D6) : le verrou est pris ici, avant les contrôles 22 et suivants, et tenu
# jusqu'à la sortie. Sortie du script (piège EXIT, quel que soit le résultat) : le repère de stabilité, la note de passage de relais de la branche
# seulement après une sortie 0, puis le verrou (seulement le sien). Les signaux deviennent des sorties pour que le piège tourne.
sortie_du_script() {
  local code=$?
  # interruption (finish-under-lock D11) : ni retrait, ni bascule, ni fusion ici ; seule une fusion lancée par ce script et pas terminée est abandonnée
  case "$code" in
    129|130|143)
      local etat="rien n'est changé"
      if [ "$MERGE_ETAT" = "en_cours" ]; then
        [ -z "${PID_FUSION:-}" ] || kill "$PID_FUSION" 2>/dev/null
        [ -z "${PID_FUSION:-}" ] || wait "$PID_FUSION" 2>/dev/null
        abandonner_fusion
        [ -z "${SORTIE_FUSION:-}" ] || rm "$SORTIE_FUSION" 2>/dev/null
        # le commit de fusion a pu être créé juste avant le signal : le sommet du worktree le dit (relecture de 2026-10-19)
        if [ -n "${SOMMET_AVANT_FUSION:-}" ] && [ "$(git -C "$WT" rev-parse -q --verify HEAD 2>/dev/null)" != "$SOMMET_AVANT_FUSION" ]; then
          etat="main est fusionnée dans la branche ; rien d'autre n'est changé"
        else
          etat="fusion de main annulée, rien n'est changé"
        fi
      elif [ "$APRES_RETRAIT" -eq 1 ]; then etat="le worktree est retiré ; voir les lignes de la fin de branche"
      elif [ "$MERGE_ETAT" = "faite" ]; then etat="main est fusionnée dans la branche ; rien d'autre n'est changé"
      fi
      printf '%s : interrompu (code %s) : %s\n' "$NOM" "$code" "$etat" >&2 ;;
  esac
  [ -z "${REPERE:-}" ] || rm "$REPERE" 2>/dev/null
  # la fiche de fin que ce lancement a écrite ne reste que si le script de fin a été lancé (D16, C17)
  { [ "$FIN_LANCEE" -eq 1 ] || [ -z "${FICHE_FIN:-}" ]; } || rm "$FICHE_FIN" "$FICHE_FIN.tmp.$$" 2>/dev/null
  if [ "$code" -eq 0 ] && [ -n "${COMMUN:-}" ]; then
    rm "$COMMUN/pmzilla-notes/$(printf '%s' "$BRANCHE" | sed -e 's/%/%25/g' -e 's#/#%2F#g')" 2>/dev/null
  fi
  finish_lock_release
}
finish_lock_acquire "$COMMUN" "$BRANCHE"; CODE_VERROU=$?
case "$CODE_VERROU" in
  0) ;;
  1) refus 42 "une autre fin de branche est en cours (${FL_BRANCH:-?}, depuis $(finish_lock_hhmm "$FL_START"))" ;;
  *) refus 42 "verrou de fin de branche impossible à créer" "Le dossier Git commun n'accepte pas l'écriture ; rien n'est changé." ;;
esac
trap 'sortie_du_script' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
# fiche de fin (D5, D16) : toute fiche restée dans le dossier Git commun est effacée ici, juste après le verrou, et jamais lue plus tard
FICHE_FIN="$COMMUN/pmzilla-finish-tested"
rm "$FICHE_FIN" 2>/dev/null

# 44. garde-fou du matin (change morning-guard, D7) : pris ici, après le verrou et avant les contrôles 22 et suivants, puis repris juste avant
# le retrait du worktree (la fenêtre peut s'ouvrir pendant le runner). Aucune variable ne l'écarte ; un refus ne change rien.
garde_matin() {
  local sortie code
  if [ -n "${FINISH_MORNING_CHECK:-}" ]; then
    sortie=$(sh -c "$FINISH_MORNING_CHECK" </dev/null 2>&1); code=$?
  else
    sortie=$(bash "$(cd "$(dirname "$0")" && pwd)/morning_state.sh" check </dev/null 2>&1); code=$?
  fi
  [ "$code" -eq 0 ] || refus 44 "fenêtre du matin, état du matin non vérifié" "$sortie" \
    "relancer quand l'état du matin est vérifié : bash tools/morning_state.sh check, puis bash tools/finish_worktree.sh $BRANCHE"
}
garde_matin

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

# Vérification (D7) : le mode --check du script de fin, dans l'espace de travail, avec la branche, entrée vide. Les refus du mode se
# traduisent en codes 32 à 37 ; rien n'est changé. Une sortie réussie rend 0 ; la sortie du contrôle est montrée seulement en cas de refus.
controle() { # lance le mode --check ; le code dans CODE_CTRL, sa sortie dans SORTIE_CTRL
  SORTIE_CTRL=$( ( cd "$ESPACE" && sh -c "$VERIF \"\$1\"" sh "$BRANCHE" </dev/null ) 2>&1 ); CODE_CTRL=$?
}
verifier() { # contrôle, puis refus de tout code non nul
  controle
  [ "$CODE_CTRL" -eq 0 ] && return 0
  refuser_controle
}
refuser_controle() { # traduit CODE_CTRL (non nul) en refus ; la sortie du contrôle est montrée avant
  local code=$CODE_CTRL
  [ -z "$SORTIE_CTRL" ] || printf '%s\n' "$SORTIE_CTRL" >&2
  case "$code" in
    5)  refus 32 "la fin de branche refuserait : change OpenSpec non archivé ; rien n'est changé" ;;
    6)  refus 33 "la fin de branche refuserait : jeu d'essai validant absent ; rien n'est changé" ;;
    7)  refus 34 "la fin de branche refuserait : main n'est pas à jour ; rien n'est changé" ;;
    8)  refus 35 "la fin de branche refuserait : la branche ne contient pas main ; rien n'est changé" ;;
    12) refus 36 "la fin de branche refuserait : main est ouvert dans un autre dossier ; rien n'est changé" ;;
    14) refus 41 "la fin de branche refuserait : passage dbtest vert absent ; rien n'est changé" ;;
    19) refus 49 "la fin de branche refuserait : la branche touche un autre change OpenSpec ; rien n'est changé" ;;
    *)  refus 37 "vérification préalable impossible (code $code) ; rien n'est changé" ;;
  esac
}

# Fusion de main dans la branche (finish-under-lock D2, D3, D10) : le plus avancé de main local et de origin/main (un seul fetch ; main local n'est
# jamais déplacé). La branche le contient déjà, ou la divergence est laissée à la vérification : aucune fusion. Sinon aperçu (conflit prévu : 46, rien
# n'est lancé), puis la fusion dans le worktree, entrée vide ; le jeton du verrou est dans l'environnement. La fusion tourne en tâche de fond pour que
# l'interruption soit traitée tout de suite (le piège de sortie l'arrête et la défait, seulement si ce script l'a lancée).
FUSION_FAITE=0
REFAIRE_CONTROLE=0
PID_FUSION=""
abandonner_fusion() { # défait une fusion en cours dans le worktree, s'il y en a une
  if git -C "$WT" rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1; then git -C "$WT" merge --abort >/dev/null 2>&1; return; fi
  # arrêtée avant que Git n'écrive l'état de fusion (signal pendant le crochet pre-merge-commit, relecture du 2026-10-20) : l'index et les
  # fichiers fusionnés restent sans MERGE_HEAD. Le worktree était propre avant la fusion (contrôle 28) et le sommet n'a pas bougé : les
  # fichiers suivis reviennent au sommet ; les fichiers ignorés ne sont pas touchés.
  if [ -n "${SOMMET_AVANT_FUSION:-}" ] && [ "$(git -C "$WT" rev-parse -q --verify HEAD 2>/dev/null)" = "$SOMMET_AVANT_FUSION" ] \
     && [ -n "$(git -C "$WT" status --porcelain --untracked-files=no 2>/dev/null)" ]; then
    git -C "$WT" restore --source=HEAD --staged --worktree -- :/ >/dev/null 2>&1
  fi
}
fusion_main() {
  local sommet apercu rc noms n nom_ref sortie_fusion code court
  sommet=$(git -C "$ESPACE" rev-parse --verify -q "refs/heads/$BRANCHE^{commit}" 2>/dev/null)
  # un fetch en échec ou des main divergentes : rien n'est fusionné, et la vérification est refaite, pour qu'elle refuse (7, donc 34) (D2)
  if git -C "$ESPACE" remote get-url origin >/dev/null 2>&1; then
    if ! git -C "$ESPACE" fetch -q origin "$PRINCIPALE" </dev/null >/dev/null 2>&1; then
      info "main distante injoignable : aucune fusion"; REFAIRE_CONTROLE=1; return 0
    fi
  fi
  REF_MAIN=$(light_main_ref "$ESPACE")
  [ -n "$sommet" ] || return 0
  if [ -z "$REF_MAIN" ]; then info "main locale et main distante divergent : aucune fusion"; REFAIRE_CONTROLE=1; return 0; fi
  if git -C "$ESPACE" merge-base --is-ancestor "$REF_MAIN" "$sommet" 2>/dev/null; then
    info "main déjà contenue dans la branche : aucune fusion"; return 0
  fi
  apercu=$( cd "$ESPACE" && finish_merge_preview "$REF_MAIN" "$sommet" ); rc=$?
  if [ "$rc" -eq 1 ]; then
    noms=$(printf '%s\n' "$apercu" | sed 1d)
    n=$(printf '%s\n' "$noms" | grep -c .)
    refus 46 "fusion de main dans la branche impossible : conflit prévu sur $n fichier(s), rien n'est changé" "$noms"
  fi
  nom_ref=$PRINCIPALE
  [ "$REF_MAIN" = "$(git -C "$ESPACE" rev-parse --verify -q "refs/heads/$PRINCIPALE^{commit}" 2>/dev/null)" ] || nom_ref="origin/$PRINCIPALE"
  sortie_fusion="$COMMUN/pmzilla-fusion.$$"
  SORTIE_FUSION=$sortie_fusion
  SOMMET_AVANT_FUSION=$(git -C "$WT" rev-parse -q --verify HEAD 2>/dev/null)
  MERGE_ETAT="en_cours"
  ( cd "$WT" && exec git merge --no-edit "$nom_ref" </dev/null >"$sortie_fusion" 2>&1 ) &
  PID_FUSION=$!
  wait "$PID_FUSION"; code=$?
  PID_FUSION=""
  cat "$sortie_fusion" 2>/dev/null; rm "$sortie_fusion" 2>/dev/null
  if [ "$code" -ne 0 ]; then
    abandonner_fusion
    MERGE_ETAT="aucune"
    refus 46 "fusion de main dans la branche impossible : fusion annulée, rien n'est changé"
  fi
  MERGE_ETAT="faite"; FUSION_FAITE=1
  court=$(git -C "$WT" rev-parse --short HEAD 2>/dev/null)
  info "main fusionnée dans la branche ($court)"
}
# Passage de la base jetable sous le verrou (D4) : sur le code 14 du contrôle, dans le worktree, entrée vide, puis nouvelle vérification.
passage_dbtest() {
  local code
  info "passage dbtest requis pour l'arbre du sommet"
  ( cd "$WT" && sh -c "$DBTEST" </dev/null ); code=$?
  [ "$code" -eq 0 ] || refus 48 "passage dbtest rouge (code $code)"
  info "passage dbtest vert"
  verifier
}

# Mode CI (local-ci-container, D8) : lecture du verdict enregistré d'un arbre. Rend 0 (CI_VERDICT = vert ou rouge, CI_IMAGE = clé de la ligne),
# 1 (aucune ligne exploitable pour cet arbre), 2 (dossier de données introuvable ou fichier illisible). Ne lance rien et n'écrit rien.
lire_verdict_ci() { # arbre
  local fichier donnees contenu ligne
  CI_VERDICT=""; CI_IMAGE=""
  if [ -n "${FINISH_WORKTREE_CI_VERDICTS:-}" ]; then
    fichier=$FINISH_WORKTREE_CI_VERDICTS
  else
    donnees=$( ( . "$LIGHT_FINISH_DIR/lab_paths.sh" 2>/dev/null && lab_paths_init >/dev/null 2>&1 && [ -d "$LAB_DATA_FOLDER" ] && printf '%s' "$LAB_DATA_FOLDER" ) ) || donnees=""
    [ -n "$donnees" ] || return 2
    fichier="$donnees/ci/verdicts"
  fi
  [ -e "$fichier" ] || return 1
  contenu=$(cat "$fichier" 2>/dev/null) || return 2
  ligne=$(printf '%s\n' "$contenu" | awk -F'\t' -v arbre="$1" '$1 == arbre { l = $2 "\t" $3 } END { print l }')
  CI_VERDICT=${ligne%%$'\t'*}; CI_IMAGE=${ligne#*$'\t'}
  case "$CI_VERDICT" in vert|rouge) return 0 ;; esac
  CI_VERDICT=""; CI_IMAGE=""
  return 1
}

# Première vérification, avant tout changement (D1) : 0, 8 et 14 continuent ; les autres refusent. Puis la fusion, puis la vérification refaite
# après une fusion ; sans fusion, le code de la première est celui qui compte.
controle
case "$CODE_CTRL" in 0|8|14) ;; *) refuser_controle ;; esac
fusion_main
{ [ "$FUSION_FAITE" -eq 0 ] && [ "$REFAIRE_CONTROLE" -eq 0 ]; } || controle
case "$CODE_CTRL" in
  0) ;;
  14) passage_dbtest ;;
  *) refuser_controle ;;
esac
info "vérification préalable réussie"

# Runner complet dans le worktree, avant le retrait (Q3, option B) : le point d'entrée du runner, jamais filtré ni ciblé, entrée vide,
# sans la variable réservée à git commit ni la variable de contournement du propriétaire. Sa sortie est montrée au fil de l'eau.
SOMMET_AVANT=$(git -C "$ESPACE" rev-parse --verify -q "refs/heads/$BRANCHE" 2>/dev/null)
# Chemin allégé (light-spec-finish, D7) : la même décision que le script de fin, par le module partagé, sur le sommet de la branche et dans le
# worktree (main = le plus avancé de main local et de origin/main ; divergents : runner complet). Allégé : validation OpenSpec, puis les suites
# qui lisent openspec/ ; ni runner complet ni fiche de fin (elle atteste un runner complet). Sinon, le bloc du runner complet ci-dessous.
SANS_VARIABLES_RESERVEES="env -u PMZILLA_NO_EVALS -u PMZILLA_SKIP_GREEN_CHECK -u FINISH_BRANCH_TESTED_TOKEN -u FINISH_BRANCH_FORCE_RUN -u FINISH_WORKTREE_ALLOW_SKIP"
LEGER=0
SOMMET_BRANCHE=$(git -C "$ESPACE" rev-parse --verify -q "refs/heads/$BRANCHE^{commit}" 2>/dev/null)
REF_MAIN=$(light_main_ref "$ESPACE")
DECISION=$( cd "$WT" && light_decision "$REF_MAIN" "$SOMMET_BRANCHE" )
case "$DECISION" in
  "allégé") LEGER=1 ;;
  complet*)
    if ( cd "$WT" && light_spec_branch "refs/heads/$PRINCIPALE" "$SOMMET_BRANCHE" ); then info "runner complet nécessaire : ${DECISION#complet?}"; fi ;;
esac
if [ "$LEGER" -eq 1 ]; then
  info "chemin allégé : passage allégé dans le worktree (openspec validate --strict et suites qui lisent openspec/)"
  ( cd "$WT" && $SANS_VARIABLES_RESERVEES sh -c "$VALIDATION \"\$@\"" _ "$REF_MAIN" "$SOMMET_BRANCHE" </dev/null )
  CODE_VALIDATION=$?
  case "$CODE_VALIDATION" in
    0) ;;
    126|127) info "runner complet nécessaire : openspec introuvable"; LEGER=0 ;;
    *) refus 45 "openspec validate --strict en échec dans le worktree ; rien n'est changé" ;;
  esac
fi
if [ "$LEGER" -eq 1 ]; then
  NOMS_LEGERS=$( cd "$WT" && light_suites ) || { info "runner complet nécessaire : sélection des suites impossible"; LEGER=0; }
fi
if [ "$LEGER" -eq 1 ]; then
  ( cd "$WT" && $SANS_VARIABLES_RESERVEES sh -c "$RUNNER_LEGER $NOMS_LEGERS" </dev/null )
  CODE_RUNNER=$?
  [ "$CODE_RUNNER" -eq 0 ] || refus 38 "le runner complet n'est pas vert dans le worktree (code $CODE_RUNNER) ; rien n'est changé" "(passage allégé)"
  SOMMET_APRES=$(git -C "$ESPACE" rev-parse --verify -q "refs/heads/$BRANCHE" 2>/dev/null)
  [ -n "$SOMMET_AVANT" ] && [ "$SOMMET_AVANT" = "$SOMMET_APRES" ] || refus 40 "la branche a changé pendant le runner ; rien n'est changé"
  JETON=$(od -An -N16 -tx1 /dev/urandom 2>/dev/null | tr -d ' \n')
  info "passage allégé vert dans le worktree ; fiche de fin sans objet : le script de fin relancera le passage allégé"
else

# Mode CI (D8) : chemin complet seulement. Le verdict enregistré de l'arbre fusionné est lu, jamais de conteneur ; puis la passe Mac remplace le runner complet.
CMD_RUNNER=$RUNNER; CI_MODE=0; PASSE_VERTE="runner complet vert dans le worktree"
if [ "${FINISH_WORKTREE_CI:-}" = "1" ]; then
  CI_MODE=1; CMD_RUNNER="$RUNNER --mac"; PASSE_VERTE="passe Mac verte dans le worktree"
  ARBRE_CI=$(git -C "$ESPACE" rev-parse --verify -q "$SOMMET_BRANCHE^{tree}" 2>/dev/null)
  COURT_CI=${ARBRE_CI:0:12}
  CMD_CI="lancer : bash tools/ci_local.sh run $BRANCHE (depuis le worktree), puis relancer la fin"
  lire_verdict_ci "$ARBRE_CI"; CODE_VERDICT=$?
  case "$CODE_VERDICT" in
    2) refus 50 "verdict du conteneur illisible (dossier de données introuvable)" "$CMD_CI" ;;
    1) refus 50 "verdict du conteneur absent pour l'arbre fusionné (arbre $COURT_CI)" "$CMD_CI" ;;
  esac
  [ "$CI_VERDICT" != "rouge" ] || refus 50 "verdict du conteneur rouge pour l'arbre fusionné (arbre $COURT_CI)" "$CMD_CI"
  info "verdict du conteneur vert pour l'arbre fusionné (arbre $COURT_CI, image ${CI_IMAGE:0:12})"
fi

# Le worktree ne doit pas avoir bougé pendant le runner (D5) : propre au démarrage (a), propre à l'écriture de la fiche (b), aucun fichier
# suivi changé pendant le runner (ctime), même remis en état (c, repère vide posé hors de l'arbre de travail, retiré à la sortie quelle que soit l'issue).
propre_wt() { local s; s=$(git -C "$WT" status --porcelain 2>/dev/null) || return 1; [ -z "$s" ]; }
STABLE=1
propre_wt || STABLE=0
# Aucun autre processus dans le worktree (test-speed-2, D12, idée #285) : « lsof -w -n -P -d cwd -F pn » liste, pour chaque processus visible, son numéro
# (lignes p) et son dossier courant (lignes n). Trouvé : le dossier courant est le worktree ou un dossier dedans (préfixe suivi de /), et le numéro
# n'est pas celui de ce script. Impossible : lsof absent, code non nul, ou liste qui ne nomme pas ce script (une liste qui ne voit rien ne prouve rien).
# Rend 0 aucun autre, 1 un autre trouvé, 2 vérification impossible. Aucun numéro ni nom de commande n'est affiché ni gardé ; rien n'est signalé ni attendu.
listage_processus() {
  local liste ligne pid="" chemin vu_soi=0 trouve=0
  command -v lsof >/dev/null 2>&1 || return 2
  liste=$(lsof -w -n -P -d cwd -F pn 2>/dev/null) || return 2
  while IFS= read -r ligne; do
    case "$ligne" in
      p*) pid=${ligne#p}; [ "$pid" != "$$" ] || vu_soi=1 ;;
      n*) chemin=${ligne#n}
          if [ "$pid" != "$$" ]; then
            case "$chemin/" in "$WT/"*) trouve=1 ;; esac
          fi ;;
    esac
  done <<< "$liste"
  [ "$vu_soi" -eq 1 ] || return 2
  [ "$trouve" -eq 0 ] || return 1
  return 0
}
PROCESSUS=0
retenir_processus() { # code du listage : « trouvé » l'emporte sur « impossible »
  case "$1" in
    1) PROCESSUS=1 ;;
    2) [ "$PROCESSUS" -eq 1 ] || PROCESSUS=2 ;;
  esac
}
REPERE=$(git -C "$WT" rev-parse --path-format=absolute --git-path pmzilla-finish-repere 2>/dev/null)
{ [ -n "$REPERE" ] && : > "$REPERE"; } 2>/dev/null || STABLE=0
sleep 1   # la ctime a une résolution fine, mais une marge d'une seconde sépare le repère du premier changement du runner
listage_processus; retenir_processus $?   # premier listage (D12), après le repère et sa marge
if [ "$CI_MODE" -eq 1 ]; then info "lancement de la passe Mac dans le worktree"; else info "lancement du runner complet dans le worktree"; fi
( cd "$WT" && env -u PMZILLA_NO_EVALS -u PMZILLA_SKIP_GREEN_CHECK -u FINISH_BRANCH_TESTED_TOKEN -u FINISH_BRANCH_FORCE_RUN -u FINISH_WORKTREE_ALLOW_SKIP sh -c "$CMD_RUNNER" </dev/null )   # les trois variables du saut ne doivent jamais atteindre le runner (test-speed-2, groupe 0)
CODE_RUNNER=$?
if [ "$CI_MODE" -eq 1 ]; then
  [ "$CODE_RUNNER" -eq 0 ] || refus 38 "passe Mac rouge dans le worktree (code $CODE_RUNNER) ; rien n'est changé"
else
  [ "$CODE_RUNNER" -eq 0 ] || refus 38 "le runner complet n'est pas vert dans le worktree (code $CODE_RUNNER) ; rien n'est changé"
fi
SOMMET_APRES=$(git -C "$ESPACE" rev-parse --verify -q "refs/heads/$BRANCHE" 2>/dev/null)
[ -n "$SOMMET_AVANT" ] && [ "$SOMMET_AVANT" = "$SOMMET_APRES" ] || refus 40 "la branche a changé pendant le runner ; rien n'est changé"
listage_processus; retenir_processus $?   # second listage (D12), le runner a fini, avant la condition (b)
propre_wt || STABLE=0   # (b)
# (c) date de changement d'état (ctime) : elle voit écriture, renommage, chmod et recréation, et ne se remet pas en arrière. Aucun nom de
# fichier n'est affiché : find ne rend qu'un « x » par lot ; un fichier suivi absent ou une commande en échec donnent aussi un « x ».
CHANGE=$(set -o pipefail; git -C "$WT" ls-files -z 2>/dev/null | (cd "$WT" && xargs -0 sh -c '[ $# -gt 0 ] || exit 0
  sortie=$(find -P "$@" -maxdepth 0 -cnewer "$0" -print 2>/dev/null) || { echo x; exit 0; }
  [ -z "$sortie" ] || echo x' "$REPERE" 2>/dev/null) || echo x)
[ -z "$CHANGE" ] || STABLE=0
# (c) aussi sur les dossiers (test-db-guards, D2) : un dossier suivi renommé puis remis, un fichier non suivi créé puis supprimé ne changent que la
# date de changement d'état d'un dossier. Sont contrôlés la racine du worktree et chaque dossier qui contient un fichier suivi, directement ou dans
# un sous-dossier, avec le même repère et le même test. Aucun nom n'est affiché ; une liste ou une commande en échec donne aussi un « x ».
dossiers_suivis() { # liste des dossiers (racine « . » comprise), chemins relatifs précédés de « ./ », terminés par un octet nul, sans doublon
  local f
  { printf '.\0'
    git -C "$WT" ls-files -z 2>/dev/null | while IFS= read -r -d '' f; do
      while case "$f" in */*) true ;; *) false ;; esac; do f=${f%/*}; printf './%s\0' "$f"; done
    done
  } | sort -zu
}
CHANGE_DOSSIERS=$(set -o pipefail; dossiers_suivis | (cd "$WT" && xargs -0 sh -c '[ $# -gt 0 ] || exit 0
  sortie=$(find -P "$@" -maxdepth 0 -cnewer "$0" -print 2>/dev/null) || { echo x; exit 0; }
  [ -z "$sortie" ] || echo x' "$REPERE" 2>/dev/null) || echo x)
[ -z "$CHANGE_DOSSIERS" ] || STABLE=0
# (d) l'empreinte complète doit avoir été réécrite par ce runner (D16, constat 2) : sa date de changement d'état est plus récente que le repère posé
# avant le runner (même repère, même test que (c)), vérifié avant que le repère ne soit retiré. Le script n'écrit ni n'efface jamais l'empreinte.
EMPREINTE_WT=$(git -C "$WT" rev-parse --path-format=absolute --git-path pmzilla-run-all-ok 2>/dev/null)
EMPREINTE_FRAICHE=0
if [ -n "$REPERE" ] && [ -n "$EMPREINTE_WT" ] && [ -s "$EMPREINTE_WT" ] && [ -n "$(find -P "$EMPREINTE_WT" -maxdepth 0 -cnewer "$REPERE" -print 2>/dev/null)" ]; then
  EMPREINTE_FRAICHE=1
fi
rm "$REPERE" 2>/dev/null
# Fiche de fin (D5, D6, D9) : écrite seulement si le worktree n'a pas bougé et si l'empreinte complète que le vrai runner a écrite dans le worktree égale l'arbre du sommet.
JETON=$(od -An -N16 -tx1 /dev/urandom 2>/dev/null | tr -d ' \n')
ARBRE_SOMMET=$(git -C "$ESPACE" rev-parse --verify -q "$SOMMET_APRES^{tree}" 2>/dev/null)   # l'arbre du sommet comparé au code 40, jamais relu depuis la branche (D16, constat 4)
SIGNATURE=$( ( cd "$WT" && finish_env_signature ) 2>/dev/null ) || SIGNATURE=""
if [ "$STABLE" -ne 1 ]; then
  info "$PASSE_VERTE ; worktree modifié pendant le runner : le script de fin le relancera"
elif [ "$PROCESSUS" -eq 1 ]; then   # D12 : après (b) et (c), avant l'empreinte et le réglage
  info "$PASSE_VERTE ; un autre processus a son dossier courant dans le worktree : le script de fin le relancera"
elif [ "$PROCESSUS" -eq 2 ]; then
  info "$PASSE_VERTE ; vérification des processus impossible : le script de fin le relancera"
elif ! { [ -n "$JETON" ] && [ -n "$SIGNATURE" ] && [ -n "$ARBRE_SOMMET" ] \
   && { [ "$CI_MODE" -eq 1 ] || { [ -n "$EMPREINTE_WT" ] && [ -s "$EMPREINTE_WT" ] && [ "$(cat "$EMPREINTE_WT")" = "$ARBRE_SOMMET" ]; }; }; }; then   # mode CI : le verdict lu et la passe Mac tiennent lieu d'empreinte complète (D8 étape 4)
  info "$PASSE_VERTE ; empreinte complète absente ou différente du sommet : le script de fin le relancera"
elif [ "$CI_MODE" -eq 1 ] && [ "$ARBRE_SOMMET" != "$ARBRE_CI" ]; then   # mode CI : le verdict lu est celui de l'arbre du sommet testé, jamais d'un autre
  info "$PASSE_VERTE ; arbre du sommet différent de celui du verdict lu : le script de fin le relancera"
elif [ "$CI_MODE" -ne 1 ] && [ "$EMPREINTE_FRAICHE" -ne 1 ]; then   # D16 : une empreinte égale au sommet mais pas réécrite par ce runner ne prouve rien
  info "$PASSE_VERTE ; empreinte complète non réécrite par ce runner : le script de fin le relancera"
elif [ "${FINISH_WORKTREE_ALLOW_SKIP:-1}" != "1" ]; then   # saut permis par défaut (skip-default-on D1) : absent, vide ou exactement 1 le permet, toute autre valeur le désactive
  info "$PASSE_VERTE ; saut non autorisé (réglage désactivé) : le script de fin le relancera"
elif ( umask 077; printf 'format=1\nbranch=%s\ntip=%s\ntree=%s\nenv=%s\ntoken=%s\ndate=%s\n' "$BRANCHE" "$SOMMET_APRES" "$ARBRE_SOMMET" "$SIGNATURE" "$JETON" "$(date +%Y-%m-%dT%H:%M:%S)" > "$FICHE_FIN.tmp.$$"; [ "$CI_MODE" -ne 1 ] || printf 'passage=ci\nimage=%s\n' "$CI_IMAGE" >> "$FICHE_FIN.tmp.$$" ) 2>/dev/null \
   && mv "$FICHE_FIN.tmp.$$" "$FICHE_FIN" 2>/dev/null; then
  info "$PASSE_VERTE ; fiche de fin écrite : le script de fin ne le relancera pas si l'arbre fusionné est le même"
else
  rm "$FICHE_FIN.tmp.$$" 2>/dev/null
  info "$PASSE_VERTE ; empreinte complète absente ou différente du sommet : le script de fin le relancera"
fi
fi   # fin de l'alternative : passage allégé ou runner complet (light-spec-finish, D7)

# Même vérification, juste avant le retrait : la course avec le distant revient aux secondes du retrait et de la bascule
verifier
garde_matin   # morning-guard D7 : la fenêtre du matin peut s'être ouverte pendant le runner

# Retrait du worktree (sans force, sans nouvel essai)
git -C "$ESPACE" worktree remove "$WT" >/dev/null 2>&1 \
  || refus 30 "retrait du worktree impossible" "git worktree remove a refusé de retirer $WT (worktree verrouillé, par exemple) ; rien d'autre n'est changé." \
    "Vérifie avec : git worktree list"
APRES_RETRAIT=1
info "worktree retiré : $WT"

# Bascule de l'espace de travail sur la branche
git -C "$ESPACE" switch -q "$BRANCHE" >/dev/null 2>&1 \
  || refus 31 "bascule de l'espace de travail impossible" "Le worktree $WT est retiré ; l'espace de travail est sur $PRINCIPALE ; le script de fin n'est pas lancé." \
    "Pour recréer le worktree : bash tools/worktree.sh $BRANCHE"
info "espace de travail sur la branche $BRANCHE"

# Fin de branche, dans l'espace de travail, entrée vide ; le code est transmis
MAIN_AVANT=$(git -C "$ESPACE" rev-parse --short --verify -q "refs/heads/$PRINCIPALE" 2>/dev/null)
FIN_LANCEE=1
( cd "$ESPACE" && FINISH_BRANCH_TESTED_TOKEN="$JETON" sh -c "$FIN" </dev/null )
CODE=$?
if [ "$CODE" -eq 0 ]; then
  # ligne de succès (D12) : seulement si main local contient le sommet terminé ; le code du script de fin reste le code de sortie
  if git -C "$ESPACE" merge-base --is-ancestor "$SOMMET_APRES" "refs/heads/$PRINCIPALE" 2>/dev/null; then
    info "terminé : $PRINCIPALE $MAIN_AVANT -> $(git -C "$ESPACE" rev-parse --short --verify -q "refs/heads/$PRINCIPALE" 2>/dev/null)"
  else
    info "succès non établi : $PRINCIPALE ne contient pas le sommet de la branche"
  fi
fi
if [ "$CODE" -ne 0 ]; then
  printf '%s : la fin de branche a rendu le code %s ; le worktree de %s est retiré\n' "$NOM" "$CODE" "$BRANCHE" >&2
  case "$CODE" in
    [1-9]|17|18) printf '%s : pour reprendre dans un worktree : git switch %s && bash tools/worktree.sh %s\n' "$NOM" "$PRINCIPALE" "$BRANCHE" >&2 ;;
  esac
fi
exit "$CODE"
