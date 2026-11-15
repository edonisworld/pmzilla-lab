#!/bin/bash
# Termine une liste de branches en un seul train (change finish-train-v1, R-148 branche 5 ; conception D1 à D24).
# À lancer par l'auteur seul, dans le Terminal, depuis le dossier d'exécution (jamais depuis une session Claude Code), avec 1 à 6 branches, chacune
# une fois, dans l'ordre de fusion ; l'option --essai, avant les noms, fait l'essai rapide (sans dbtest ni runner).
#
#     bash tools/finish_train.sh feat/a feat/b
#     bash tools/finish_train.sh --essai feat/a feat/b
#
# Porte du train (change ci-local-runner, D9, R-20261101-114) : dans le worktree d'intégration (HEAD propre = le commit du train), le train lance d'abord
# `bash <outils>/ci_local.sh run` (portable, base, e2e dans le conteneur ; jeton du verrou de fin : file prioritaire), puis la passe Mac `bash tests/run_all.sh --mac`.
# Il réimprime les lignes `ci_passage : phase …` et `ci_local : …` du conteneur. Phase base rouge : 69 ; phase de bout en bout rouge : 82 ; phase portable ou
# passe Mac rouge avec des suites nommées : l'indice et UN rejeu (voir ci-dessous), puis 70 ou 71 ; codes 3 et 5 de ci_local, code 1 sans ligne de phase rouge et tout
# autre code : 71 « runner non concluant : conteneur indisponible (code <c>) » (aucune voie de secours, Q170). Plus aucune passe dbtest ni runner complet du Mac.
# Les contrôles 14 et 16 de finish_checks.py restent lus (le contrôle 6 de l'arbre vient de la même sortie) mais ne lancent plus rien. La stabilité (Q219) exige,
# après la passe Mac, une ligne de l'arbre du train dans pmzilla-run-mac-ok (dossier Git commun) ET la ligne `<arbre><tab><clé><tab>portable,base,e2e` de
# ci/preuves (dossier de données du lab), chacune dans un fichier réécrit après le repère ; main reste enregistré « complet » à l'arrivée sauf commande de test posée
# (FINISH_TRAIN_RUNNER ou FINISH_TRAIN_CI) ; l'empreinte pmzilla-run-all-ok de l'espace de travail reste écrite à l'avance rapide (Q218 a), sauf commande de test posée (Q233 a).
# Remplace : dbtest (code 69 d'avant), la passe de bout en bout `dbtest --e2e` (finish-e2e-proof-shared, D5, D6 ; le code 82 garde son sens) et le runner complet du
# Mac comme porte de main. Retrait : permanent tant que les trains tournent ; Q218 (b) et la fin de l'empreinte complète d'arrivée : ménage d'après le 26/11.
#
# Suite rouge : indice et rejeu (change targeted-suites-admission, D1, D5). La porte (conteneur, puis passe Mac) sur l'arbre intégré reste la seule garde de main,
# quelles que soient les preuves des branches listées (empreinte complète, de branche ou du conteneur). Quand une suite nommée est rouge, le script imprime l'indice
# « train rouge : suites rouges sélectionnées par : <branches> » ou « … par aucune branche » (sélecteur --range par branche ; « indice impossible pour
# <branche> » quand il échoue), puis rejoue UNE fois ces suites sur le sommet du train : `ci_local.sh run --rejeu portable <suites>` pour le conteneur (FINISH_TRAIN_CI
# suivi de ces mêmes arguments), ${FINISH_TRAIN_RUNNER:-bash tests/run_all.sh} suivi des noms pour la passe Mac (ni empreinte, ni verdict, ni preuve, jamais dans l'essai
# rapide) : vert au rejeu, code 71 « runner non concluant : suites rouges non reproduites (<suites>) » ; rouge, ou tout autre
# code : le 70 d'avant, mêmes lignes, et, si aucune branche n'a sélectionné la suite rouge, la ligne « défaut de sélection : … » avant la bannière. Le script ne
# se relance jamais et ne retire aucune ligne de la liste. Remplace : la ligne de 70 sans indice, et un 70 sur une suite qui ne rechoue pas. Retrait : permanent
# tant que le train a une porte. Différé après la démo (R-20261031-39) : la désignation de la branche fautive par bissection.
#
# Le script prend le verrou de fin, vérifie la garde du matin, fait un fetch, exige main local = origin/main (ou un état de reprise des références),
# admet chaque branche (contrôles 19, 5 et 6, fichiers ignorés, processus, outillage protégé), construit LUI-MÊME le train (git merge-tree et
# git commit-tree, sous l'identité de l'auteur), lit chaque commit (range_scan.py), installe les paquets de Mothra dans le worktree d'intégration
# (npm ci --offline --ignore-scripts --no-audit --no-fund --no-update-notifier, quand l'arbre porte mothra/package-lock.json ; la version de Node
# doit être celle de mothra/.node-version ; refus 76, 80 ou 81 avant la porte), lance la porte du conteneur puis la passe Mac
# une seule fois dans un worktree d'intégration, pose UNE question (o/n), avance main en avance rapide, pousse une fois, nettoie sans rien forcer et
# met à jour le dossier d'exécution en dernier. Tout ce qu'il affiche est copié dans un journal ; chaque sortie finit par une bannière de fin.
# Il ne force rien, ne remet rien à zéro, ne contourne aucun crochet ; il n'écrit aucune référence de branche (le sommet du train n'est tenu que par
# le worktree d'intégration, jusqu'à l'avance rapide de main).
#
# Enregistrement de main validé (change finish-single-b7-b9, B9, design D8 ; décision de l'auteur R-20261105-32 Q1) : après son push, le train écrit la ligne
# `<arbre><TAB>complet<TAB><date UTC><TAB><signature>` dans pmzilla-main-validated du dossier Git commun (record_main_validated, tools/finish_env.sh ; au plus 50
# lignes, ni branche ni commit). Plus aucune décision n'en dépend (la voie allégée qui la lisait est retirée par B9) : l'écriture est gardée parce que l'inventaire
# de la tâche 2.1 y a trouvé d'autres lecteurs (aides de tests du train, guide). Remplace : l'écriture de tools/finish_branch.sh (retiré). Condition de retrait : une
# décision de l'auteur de retirer l'enregistrement ; le même changement retire alors record_main_validated, light_record_file et env_signature de finish_env.sh,
# l'appel ci-dessous et les tests de son format.
#
# Plage 60 à 84 (élargie le 2026-10-27 : la plage 60 à 79 était pleine, décision Q de l'auteur ; 82 ajouté par finish-e2e-proof-shared ; 83 par finish-single-b3-b6, B6 ; 84 par autonomous-trains-merge, D19), un sens par code ; le code 0 a deux issues que le sens de la bannière de fin distingue, « fusionné » ou « essai ».
# La conduite à tenir pour chaque code : docs/pmzilla/installation.md, « Finish a train of branches ».
#
# Codes de sortie :
#   0 terminé : train fusionné, poussé et nettoyé (fusionné), ou essai rapide ou réponse autre que « o » (essai)
#   60 usage
#   61 lancement refusé
#   62 branche(s) refusée(s) à l'admission
#   63 base non établie
#   64 conflit ou erreur Git à la construction du train, ou fichier non suivi de l'espace de travail au chemin d'un fichier du train
#   65 secrets, noms ou identifiants trouvés dans le train
#   66 garde du matin refuse : la veille ou la sauvegarde du jour tournent (seul cas de refus, aux deux contrôles)
#   67 verrou de fin tenu par une autre fin
#   68 contrôle de contenu ou contrôle 14 impossible (dont sortie incohérente de range_scan : deux lectures qui ne concordent pas, ou code 1 sans trouvaille)
#   69 phase base du conteneur rouge sur l'arbre du train (ci-local-runner, D9 ; avant : dbtest rouge ou vert sans ligne)
#   70 porte rouge (phase portable du conteneur ou passe Mac), suites nommées
#   71 runner non concluant (dont conteneur indisponible)
#   72 réservé, ancienne réponse autre que « o » (jamais rendu)
#   73 une référence a bougé avant l'avance rapide, ou l'arbre de main diffère de l'arbre testé
#   74 push refusé, train fusionné dans main local seulement
#   75 train fusionné et poussé, fin incomplète
#   76 calcul impossible (dont python3 3.10 ou plus introuvable, npm ou node introuvable, verrou npm ou package.json de Mothra inutilisable)
#   77 réservé, jamais rendu
#   78 dossiers du lab introuvables
#   79 reprise refusée, références dans aucun état connu
#   80 version de Node différente de mothra/.node-version, avant npm ci
#   81 npm ci --offline en échec : paquets de Mothra absents du cache npm, ou autre échec
#   82 phase de bout en bout du conteneur rouge sur l'arbre du train (ci-local-runner, D9)
#   83 jeu d'essai validant absent pour l'arbre du train (contrôle 6 par empreinte)
#   84 politique automatique refuse (--auto : état de reprise S1 ou S2, ou la politique de fin refuse ou ne peut pas calculer ; autonomous-trains-merge, D7, D8, D19)
#   129 interrompu par HUP
#   130 interrompu par INT
#   141 interrompu par PIPE (le lecteur de la sortie a disparu)
#   143 interrompu par TERM
#
# Faux refus 65 du train automatique du 7 novembre (décisions R-20261110-12 à -14 ; le job launchd n'avait que le PATH par défaut de launchd, donc le python3 3.9 du système,
# sur lequel range_scan.py plantait à l'import avec le code 1 que ce script lisait comme « trouvaille ») :
#   - garde de version (check_python, après le contrôle d'usage et l'ouverture du journal, avant le premier appel de python3 des étapes) : python3 absent du PATH ou
#     plus ancien que 3.10 : code 76 « calcul impossible (python3 3.10 ou plus introuvable) ; rien n'est fusionné », étape « version de python3 ». Le 76 n'arme aucun arrêt
#     (le passage automatique n'arme que sur 65 et 79). Remplace : rien. Retrait : quand un interpréteur absolu est adopté pour les appels Python de la fin (la voie B3, écartée).
#   - code 65 (scan_content) : seulement si les DEUX lectures de range_scan (texte, puis --json) sortent en 1 et que le JSON, de format 1, porte le code 1 et au moins une trouvaille
#     de nature secret, name, identifier ou encoding ; deux codes qui diffèrent, ou un code 1 sans trouvaille (plantage, JSON absent) : code 68 « sortie incohérente ». Remplace :
#     la règle « code 1 = trouvaille ». Retrait : permanent.
#   - journal : de la sortie du scan, seules les lignes `range_scan : ` sont montrées et copiées ; toute autre ligne (une trace) se dit une fois « sortie inattendue de
#     range_scan » et n'est ni montrée ni journalisée. Remplace : « montrer ses lignes telles quelles ». Retrait : permanent.
#
# Décisions de l'auteur du 2026-10-27 (revue de u5) :
#   - dossier d'exécution (code 61) : détaché sur main local OU sur origin/main ; en reprise S2 il peut aussi être sur la base du train (le commit qui
#     précède la première fusion), parce que la mise à jour du dossier d'exécution vient en dernier ; toute autre position est refusée à la détection
#     de l'état, avec l'état réel (E2, E3 ou E4) ;
#   - main local qui diffère d'origin/main sans aucune fusion de la liste : code 63 ; main local qui porte tout ou partie des fusions de la liste, ou le
#     train plus autre chose, ou une chaîne qui ne passe pas la vérification de pureté : code 79. Une fusion de la liste est portée par main local quand
#     le sommet noté de la branche est un ancêtre de main local et n'est pas un ancêtre d'origin/main (ascendance Git, jamais le message) ;
#   - SIGPIPE n'est jamais ignoré pour tout le script : un piège PIPE sort en 141, les processus enfants gardent le comportement par défaut.
#
# Une variable de substitution ne fabrique jamais une preuve : FINISH_TRAIN_CI ou FINISH_TRAIN_RUNNER posée, aucune empreinte pmzilla-run-all-ok de l'espace de
# travail n'est écrite à l'avance rapide et main n'est pas enregistré « complet » (Q233 a, R-20261101-118).
# Variables pour les tests (D19) : FINISH_TRAIN_RUNNER (la passe Mac), FINISH_TRAIN_CI (la porte du conteneur : remplace `bash <outils>/ci_local.sh run`, appelée sans
# argument pour le passage et avec `--rejeu portable <suites>` pour le rejeu), FINISH_TRAIN_MORNING_CHECK (remplacent la commande, jamais un refus ni une exemption) et
# FINISH_TRAIN_LOG_DIR (dossier du journal). Aucune ne passe aux commandes lancées. Les commandes sont lancées par `sh -c` depuis le worktree d'intégration, sans les variables
# non exportées du script ; elles ne reçoivent non plus aucune variable DBTEST_
# (finish_env_retire_dbtest, au début de main : le nettoyage fait une fois couvre tous les processus lancés ensuite, hook pre-push compris ;
# le push du train et le hook qu'il déclenche ne reçoivent donc plus non plus de variable DBTEST_, sans test dédié).
#
# Stabilité et processus (change finish-single-b3-b6, B3, D6) : la règle de stabilité du worktree d'intégration après le runner et le listage des
# processus qui ont leur dossier courant dans un worktree sont ceux du module tools/finish_stability.sh, que le train source seul depuis le retrait des fins unitaires
# (fs_snapshot, fs_verdict, fs_processes). Ce script garde ses phrases et le code 71 ; le processus nommé dans « processus dans le worktree (<n> <nom>) »,
# à l'admission, au premier listage, après le runner et au nettoyage, est le nom nettoyé (dernier segment, lettres, chiffres et « ._+ - »).
#
# Admission partagée et classes de l'outillage protégé (change finish-single-b3-b6, B4, D8, D11 et D12) : la propreté du worktree, la règle des fichiers
# ignorés qui seraient perdus et la lecture de la trace de revue sont celles du module tools/finish_admission.sh (fa_clean, fa_ignored, fa_review_done), que
# le train source seul depuis le retrait des fins unitaires (B9) ; le train n'en garde aucune copie. Les classes de l'outillage protégé (`juge` ou `sensible`, étiquettes de
# tools/finish_protected.txt) ne sont lues que dans les champs protected_judges et protected_sensitive du JSON de tools/finish_checks.py, jamais dans le fichier :
#   - un fichier `juge`, .claude/ ou un CLAUDE.md dans la différence de la branche : règle B6 ci-dessous (D18, R-20261102-43 ; l'ancien refus 62
#     « outillage de fin touché (<n> fichier(s)) : fin unitaire » n'existe plus) ;
#   - seulement des fichiers `sensible` : admis quand la liste des branches prêtes (R-20261028-61, lue par tools/train_ready.py) tient une ligne « revue faite »
#     pour cette branche à son sommet exact, avec la ligne « outil sensible admis après revue Opus du sommet <sha12> : <branche> » avant la question ; sinon refus 62
#     « outil sensible touché (<n> fichier(s)) sans revue Opus enregistrée pour le sommet <sha12> : revue ou fin unitaire » ; le train n'écrit jamais cette liste ;
#   - une sortie du module sans les deux champs : refus 62 « contrôles impossibles : classes de l'outillage protégé absentes de la sortie de finish_checks ».
# Remplace : le refus de tout outillage protégé (« outillage protégé touché (<n> fichier(s)) : fin unitaire »). Retrait : la règle `sensible` reste tant que
# la revue Opus conditionne l'entrée au train ; le refus des fichiers `juge` est remplacé par B6 ci-dessous.
#
# Train d'une branche (change finish-single-b3-b6, B6, D18 à D21). Remplace : le refus 62 « outillage de fin touché (<n> fichier(s)) : fin unitaire » et le refus
# du contrôle 6 d'une branche à l'admission (« un jeu d'essai validant vaut pour le sommet de la branche, pas pour l'arbre du train »). Retrait : permanent,
# tant que le train d'une branche juge l'outillage de fin avec le code de main (le dossier d'exécution n'est mis à jour qu'à la fin du train).
#   - D18 : à une seule branche, un fichier `juge`, .claude/ ou un CLAUDE.md est admis, avec « outillage de fin dans ce train d'une branche : <n> fichier(s) »
#     et les chemins avant la question ; à deux branches ou plus : .claude/ ou un CLAUDE.md : refus 62 « outillage de fin touché (<n> fichier(s)) : train
#     d'une seule branche » (fin de l'auteur) ; un fichier `juge` : admis jusqu'à 3 branches juges, refus 62 si deux branches juges touchent le même fichier
#     juge (« fichier juge <chemin> touché aussi par la branche de rang <i> (rang <j> ici) ») ou à partir de la quatrième (R-20261102-43). Remplace : « une
#     branche juge passe seule » ; retrait : permanent tant que le train porte des branches juges. Une branche qui touche tests/run_all.sh, ci/passage.sh,
#     tools/preuve_arbre.py ou tools/finish_train.sh reste seule (62 « modifie le runner ou la preuve : train d'une seule branche (R-20261102-43) » à plusieurs ;
#     nouvelle règle, remplace : rien ; retrait : permanent tant que le train juge son arbre avec le runner et la preuve de ses branches). Les passes (contrôle 6, porte du conteneur (phases portable, base, e2e), passe Mac)
#     lisent l'arbre du train entier, sans supposer une seule branche juge. Un fichier `sensible` garde sa règle de revue (D11) ;
#   - D19 : le contrôle 6 d'une branche n'est plus un motif de refus à l'admission (présent dans le JSON) ; le contrôle 6 de l'arbre du train (mode tree de
#     finish_checks.py, empreinte des fichiers évalués) est lu juste après le contrôle 14 et avant l'installation npm : passe ou sans objet, on continue ;
#     refusé, code 83 « jeu d'essai validant absent pour l'arbre du train ; rien n'est fusionné », étape « contrôle 6 », rien n'est touché ;
#   - D20 : après le fetch, un main local strictement en retard sur origin/main (espace de travail sur main et propre) est avancé en avance rapide
#     (--ff-only) avant la détection de l'état ; échec : code 63 ; un main divergent ou en avance garde le traitement d'avant ;
#   - D21 : après un code 0 de sens « fusionné », la note de relais de chaque branche fusionnée (pmzilla-notes du dossier Git commun, nom encodé comme
#     la fin unitaire retirée par B9, qui l'encodait de même) est retirée ; un retrait en échec est une cause du code 75 ; jamais après un autre code.
#
# Journal des trains (change autonomous-trains-merge, tranche 1, D4). Dans son piège de sortie, une fois le code et le sens de la bannière calculés (compute_banner) et
# avant la libération du verrou de fin, le train écrit UN enregistrement par `python3 -I tools/train_record.py append` (seul écrivain du journal ; il retire d'abord, sous son
# verrou, les enregistrements de plus d'un an) pour chaque lancement qui a pris le verrou de fin et qui n'est pas un essai rapide (--essai) : `code` et `sens` répètent la
# bannière (la source est le code de sortie du script ; un test de tests/finish_train/ les compare sur ses fixtures), `mode` auto ou manuel, `runner` remplace quand
# FINISH_TRAIN_CI ou FINISH_TRAIN_RUNNER est posée, `base` et `front` quand le contrôle 14 ou le contrôle 16 de l'arbre du train est applicable (pass ou refused). Aucun nom
# de branche, de personne ni clé de ticket. Une écriture impossible dit `journal des trains non écrit (écriture impossible)`, ne change jamais un code de refus, et devient,
# après une fusion (code 0, sens fusionné), une cause du code 75 (étape `journal des trains`). Remplace : rien (nouvelle preuve). Retrait : permanent tant que l'activation
# de la fusion automatique lit le journal.
#
# --auto (change autonomous-trains-merge, tranche 1, D7 et D8). `--auto`, lancé par la tâche de l'auteur et non par un terminal, remplace la question o/n par la politique de
# `python3 -I tools/finish_checks.py policy` (la liste prête, la revue Opus du sommet, l'activation, l'arrêt d'urgence, le train de l'auteur, au plus 3 branches) : autorisé,
# l'arrivée suit exactement comme après « o » ; sinon une ligne `politique automatique refuse : <libellé> (<branche>) ; rien n'est fusionné` par raison, code 84, étape de
# la bannière `politique automatique`. Refus : 60 avec --essai (`usage : --auto et --essai ne vont pas ensemble`), 61 depuis un terminal (entrée standard sur un terminal), 84
# en état de reprise S1 ou S2 (jamais de push en reprise), et 61 aussi quand FINISH_TRAIN_CI ou FINISH_TRAIN_RUNNER est posée (R-20261106-57 Q1 (a) : avant toute admission et tout
# push, même famille que le contrôle terminal). En --auto le train ne lit pas l'entrée standard et n'allège ni ne saute aucune preuve. Remplace : la réponse o/n, en --auto
# seulement. Retrait : permanent tant que --auto existe. Garde FINISH_TRAIN_CI / FINISH_TRAIN_RUNNER : remplace la phrase « aucune variable n'est une exemption » ; retrait
# (R-20261107-4) : elle tombe quand finish_train.sh ne lit plus aucune variable FINISH_TRAIN_* sous --auto. Limite déclarée de D6 : PMZILLA_LAB_DATA n'est pas gardée (--auto est refusé en
# session ; l'environnement du job est fixé par le modèle launchd que l'auteur installe).
#
# Le corps est en fonctions ; la dernière ligne appelle main : bash lit tout le fichier avant la première étape, donc une mise à jour du dossier d'exécution
# pendant la fin ne change pas le code qui tourne (D2). Après cette mise à jour, le script ne lance ni ne source plus rien, sauf l'enregistrement du journal des trains de son
# piège de sortie (`python3 -I tools/train_record.py append`, qui n'écrit que le journal du dossier de données) et la lecture de l'heure ; main_apres est lu avant la mise à jour.

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
NOM=finish_train
LIGNE="bash tools/finish_train.sh"   # remplacée par la ligne complète dès que les dossiers du lab sont résolus (set_ligne)
USAGE=""

# Les trois états de la bannière que le texte du script doit porter mot pour mot (D24)
E1="rien n'est fait ; état des références non examiné"
E2="rien n'est fusionné"
E3="main local porte le train, rien n'est poussé ; relancer la même commande pour reprendre au push"
E4="train poussé ; relancer la même commande pour reprendre au nettoyage"
E5="main local a bougé hors du train testé, rien n'est poussé ; examiner main avant de relancer"
E6="références dans aucun état connu ; rien n'est touché"

unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_REPLACE_REF_BASE \
      GIT_LITERAL_PATHSPECS GIT_GLOB_PATHSPECS GIT_NOGLOB_PATHSPECS GIT_ICASE_PATHSPECS GIT_SHALLOW_FILE
# l'identité des commits du train est celle de la configuration Git de l'auteur, jamais celle d'une variable héritée (revue de u5, M-6) ; un jeton de
# verrou hérité n'est jamais reconnu : un train lancé de l'intérieur d'une autre fin trouve son verrou tenu (code 67, m-13)
unset GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_AUTHOR_DATE GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL GIT_COMMITTER_DATE FINISH_LOCK_TOKEN
export GIT_NO_REPLACE_OBJECTS=1
LIGHT_FINISH_DIR="$SCRIPT_DIR"
. "$SCRIPT_DIR/finish_lock.sh"
. "$SCRIPT_DIR/finish_env.sh"
. "$SCRIPT_DIR/lab_paths.sh"
. "$SCRIPT_DIR/finish_stability.sh"   # stabilité du worktree après le runner et processus dans un worktree : la même règle que la fin unitaire (finish-single-b3-b6 D4, D6)
. "$SCRIPT_DIR/finish_admission.sh"   # propreté, fichiers ignorés qui seraient perdus et revue enregistrée : la même règle que la fin unitaire (finish-single-b3-b6 B4, D8, D12)

ETAT_RIEN=0   # 1 : le refus de la garde de version dit « rien n'est fusionné » sans que les références aient été lues (rien n'a encore été touché)
STEP="usage"; REF_READ=0; START_STATE="S0"; FF_DONE=0; PUSH_DONE=0; ESSAI=0; ESSAI_FIN=0; SIGCODE=""; FINISHED=0
# autonomous-trains-merge (D4, D8) : AUTO et MODE (--auto), LOCK_TAKEN (le verrou de fin est tenu), REC_* (le journal des trains), POLICY_CODES (vide hors du code 84)
AUTO=0; MODE=manuel; LOCK_TAKEN=0; REC_BASE=0; REC_FRONT=0; REC_FAILED=0; POLICY_CODES=""; MAIN_END=""; RUN_UPDATED=0; START_EPOCH=$(date +%s 2>/dev/null) || START_EPOCH=0
LOG=""; TEE_PID=""; FIFO=""; INTEG=""; INTEG_NAME=""; MARK=""; DIR_SNAP=""; BASE=""; MAIN_START=""; TRAIN_TIP=""; TRAIN_TREE=""; RUN_PENDING=0; CHAIN_BASE=""
CAUSES=""; CAUSE_STEP=""; WS=""; RUN=""; COMMON=""; TV16_VERDICT=""; TV16_DETAILS=""; NOT_EXAMINED=0
FROZEN_DEST=""; FROZEN_TIP=""; FROZEN_SIG=""   # R-20261110-08 : jamais lues depuis l'environnement hérité. Remplace : rien. Retrait : avec le bac à sable (R-20261110-08).
NAMES=(); TIPS=(); MT=""
exec 3>&1 4>&2

# --- sorties ------------------------------------------------------------------------------------------------------------------------
say() { printf 'finish_train : %s\n' "$*"; }
raw() { printf '%s\n' "$*"; }
refus() { # code message : écrit le message, sort avec le code (sortie calculée, déclarée au registre des codes)
  local code=$1; shift
  say "$*"
  exit "$code"
}
sha12() { printf '%s' "${1:0:12}"; }
direct() { # texte : au journal directement (jamais par le processus de copie), puis à l'écran sur les descripteurs sauvés ; erreurs ignorées
  [ -z "$LOG" ] || printf '%s\n' "$1" >> "$LOG" 2>/dev/null
  # l'écran dans un sous-shell : une écriture qui échoue (lecteur disparu) y laisse son texte dans un tampon qui meurt avec lui, au lieu de ressortir
  # dans l'écriture suivante au journal ou dans la sortie d'une commande capturée
  ( printf '%s\n' "$1" >&3 ) 2>/dev/null
}
add_cause() { CAUSES="${CAUSES}${CAUSES:+
}$1"; [ -n "$CAUSE_STEP" ] || CAUSE_STEP=$STEP; }

# --- journal et processus de copie (D16, D23) -----------------------------------------------------------------------------------------
open_log() {
  local dir=${FINISH_TRAIN_LOG_DIR:-$LAB_FOLDER/etapes} stamp
  mkdir -p "$dir" 2>/dev/null || { say "journal impossible à écrire"; return 0; }
  stamp=$(date +%Y%m%d-%H%M%S)
  LOG="$dir/train-fin-$stamp.log"
  : >> "$LOG" 2>/dev/null || { LOG=""; say "journal impossible à écrire"; return 0; }
  # modèle de tools/etapes/modele-piege-fin.sh (R-148/u14) : le processus de copie ignore INT, TERM et HUP (il garde au journal les dernières lignes du
  # corps) ; le FIFO a un nom unique dans le dossier temporaire et disparaît dès qu'il est ouvert des deux côtés ; les descripteurs 3 et 4 (l'écran
  # d'origine) ne sont pas tenus par la copie ; sans tube, tout va au journal seulement.
  FIFO=$(mktemp -u "${TMPDIR:-/tmp}/fin-tee.XXXXXX" 2>/dev/null)
  if [ -n "$FIFO" ] && mkfifo "$FIFO" 2>/dev/null; then
    ( trap '' INT TERM HUP; exec tee -a "$LOG" ) < "$FIFO" >&3 3>&- 4>&- &
    TEE_PID=$!
    disown "$TEE_PID" 2>/dev/null   # la mort de la copie ne doit pas faire écrire le shell (message de travail tué) dans un tube sans lecteur
    exec > "$FIFO" 2>&1
    rm -f "$FIFO"
    FIFO=""
  else
    FIFO=""
    exec >> "$LOG" 2>&1
  fi
}
drain_tee() { # rend l'écran au script et attend que le processus de copie ait tout écrit (au plus cinq secondes)
  [ -n "$TEE_PID" ] || return 0
  exec 1>&3 2>&4
  local n=0
  while kill -0 "$TEE_PID" 2>/dev/null && [ "$n" -lt 100 ]; do sleep 0.05; n=$((n + 1)); done
  TEE_PID=""
}

# --- état des références et bannière de fin (D24) ------------------------------------------------------------------------------------
state_phrase() { # code : pose ETAT
  local lm
  if [ "$ETAT_RIEN" = 1 ]; then ETAT=$E2
  elif [ "$REF_READ" != 1 ]; then ETAT=$E1
  elif [ "$1" = 79 ]; then ETAT=$E6
  elif [ "$PUSH_DONE" = 1 ] || [ "$START_STATE" = S2 ]; then ETAT=$E4
  else
    # règle générale de D24 (décision du 2026-10-27) : « rien n'est fusionné » (E2) n'est écrit que si main local est encore le main lu au début ;
    # sinon E5. Le code 73 à la relecture des références en est le cas courant.
    lm=$(git -C "$WS" rev-parse -q --verify refs/heads/main 2>/dev/null)
    if [ "$FF_DONE" = 1 ] || [ "$START_STATE" = S1 ]; then
      if [ "$lm" = "$TRAIN_TIP" ]; then ETAT=$E3; else ETAT=$E5; fi
    else
      if [ "$lm" = "$MAIN_START" ]; then ETAT=$E2; else ETAT=$E5; fi
    fi
  fi
}
compute_banner() { # code : pose SENS, ETAPE, ETAT
  ETAPE=$STEP; ETAT=""
  case "$1" in
    0) if [ "$ESSAI_FIN" = 1 ]; then SENS="essai"; else SENS="fusionné"; fi; return 0 ;;
    75) SENS="fusionné"; ETAPE=${CAUSE_STEP:-$STEP} ;;
    129|130|141|143) SENS="interrompu" ;;
    *) SENS="refusé" ;;
  esac
  state_phrase "$1"
}
interrupt_phrase() {
  if [ "$ETAT" = "$E3" ]; then printf '%s' "main avancé sur le train, push non fait : relancer la même ligne"
  elif [ "$ETAT" = "$E4" ]; then printf '%s' "train poussé : relancer la même ligne pour finir le nettoyage"
  elif [ "$ETAT" = "$E5" ]; then printf '%s' "main local a bougé hors du train testé : examiner main avant de relancer"
  else printf '%s' "rien n'est fusionné"
  fi
}

# --- journal des trains (autonomous-trains-merge, D4) ---------------------------------------------------------------------------------
record_train() { # code : écrit UN enregistrement par tools/train_record.py (seul écrivain du journal) ; pose REC_FAILED=1 quand l'écriture échoue
  # Les champs viennent du code et du sens de la bannière (compute_banner) : la source est le code de sortie du script, le journal le répète (un test des suites
  # finish_train compare `code` et `sens` à la bannière sur ses fixtures). Aucun nom de branche, de personne ni clé de ticket n'est passé : les sommets, les
  # références de main, le mode, le nombre de branches et l'étape de la bannière seulement.
  local code=$1 sens runner tips="" t etape="" ma="" end dur
  local -a args
  REC_FAILED=0
  case "$SENS" in
    fusionné) sens=fusionne ;;
    essai) sens=essai ;;
    refusé) sens=refuse ;;
    *) sens=interrompu ;;
  esac
  runner=conteneur
  if [ -n "${FINISH_TRAIN_CI:-}" ] || [ -n "${FINISH_TRAIN_RUNNER:-}" ]; then runner=remplace; fi
  for t in "${TIPS[@]}"; do tips="${tips}${tips:+,}$t"; done
  # main_apres : lu une fois, avant la mise à jour du dossier d'exécution (MAIN_END, posé par after_push) ; jamais une commande Git après elle (le dossier d'exécution est
  # mis à jour en dernier : aucune commande Git ne la suit, voir tests/finish_train_reprise)
  ma=$MAIN_END
  if [ -z "$ma" ] && [ "$RUN_UPDATED" != 1 ] && [ -n "$WS" ]; then ma=$(git -C "$WS" rev-parse -q --verify refs/heads/main 2>/dev/null); fi
  [ "$code" = 0 ] || etape=$ETAPE
  end=$(date +%s 2>/dev/null) || end=$START_EPOCH
  dur=$((end - START_EPOCH))
  if [ "$dur" -lt 0 ] || [ "$dur" -gt 9999999 ]; then dur=0; fi   # horloge illisible : durée nulle plutôt qu'un enregistrement refusé
  args=(append --code "$code" --sens "$sens" --mode "$MODE" --n "${#NAMES[@]}" --sommets "$tips" --sommet-train "$TRAIN_TIP" --main-avant "$MAIN_START"
        --main-apres "$ma" --runner "$runner" --politique "$POLICY_CODES" --duree-s "$dur" --etape "$etape")
  [ "$REC_BASE" != 1 ] || args+=(--base)
  [ "$REC_FRONT" != 1 ] || args+=(--front)
  python3 -I "$SCRIPT_DIR/train_record.py" "${args[@]}" </dev/null >/dev/null 2>&1 3>&- 4>&- || REC_FAILED=1
}

# --- sortie : piège EXIT (D17, D23, D24) ---------------------------------------------------------------------------------------------
on_exit() {
  local code=$? t orig
  orig=$code
  trap '' INT TERM HUP PIPE
  [ "$FINISHED" = 0 ] || return 0
  FINISHED=1
  drain_tee
  compute_banner "$code"
  if [ -n "$SIGCODE" ]; then direct "finish_train : interrompu (code $code) : $(interrupt_phrase)"; fi
  if [ -n "$INTEG" ] && [ -n "$WS" ]; then
    if try_remove_wt "$INTEG"; then INTEG=""; else direct "finish_train : worktree gardé : $INTEG : $KEEP_REASON"; fi
  fi
  [ -z "$MARK" ] || rm -f "$MARK" 2>/dev/null
  [ -z "$MT" ] || rm -f "$MT" 2>/dev/null
  [ -z "$FIFO" ] || rm -f "$FIFO" 2>/dev/null
  # journal des trains (autonomous-trains-merge, D4) : une fois le code et le sens calculés, avant la libération du verrou de fin et avant la bannière de fin
  # (le verrou était libéré avant la bannière : l'enregistrement va donc avant la libération). Remplace : rien (nouvelle preuve). Retrait : permanent tant que
  # l'activation de la fusion automatique lit le journal.
  if [ "$LOCK_TAKEN" = 1 ] && [ "$ESSAI" = 0 ]; then
    record_train "$code"
    if [ "$REC_FAILED" = 1 ]; then
      direct "finish_train : journal des trains non écrit (écriture impossible)"   # ne change jamais un code de refus
      if [ "$code" = 0 ] && [ "$SENS" = "fusionné" ]; then   # après une fusion : une cause du code 75 (le train est fusionné et poussé, la fin est incomplète)
        STEP="journal des trains"; CAUSES=""; CAUSE_STEP=""
        add_cause "journal des trains non écrit (écriture impossible)"
        direct "finish_train : train fusionné et poussé, fin incomplète :"
        direct "  - journal des trains non écrit (écriture impossible)"
        code=75
        compute_banner "$code"
      fi
    fi
  fi
  finish_lock_release
  t=$(TZ=Europe/Paris date '+%Y-%m-%d %H:%M:%S' 2>/dev/null) || t=""
  [ -n "$t" ] || t="heure indisponible"
  direct "===== fin du train : code $code ($SENS), $t Paris ====="
  if [ "$code" != 0 ]; then direct "===== arrêt à $ETAPE : $ETAT ====="; fi
  [ "$code" = "$orig" ] || exit 75   # seul cas : le code 0 devenu 75 par l'échec de l'écriture du journal après une fusion
}
trap 'on_exit' EXIT
trap 'SIGCODE=INT; exit 130' INT
trap 'SIGCODE=TERM; exit 143' TERM
trap 'SIGCODE=HUP; exit 129' HUP
# SIGPIPE (décision du 2026-10-27, D17 et D23) : jamais ignoré pour tout le script ; le lecteur de la sortie a disparu, la fin s'arrête en 141 par le
# piège de sortie. Les processus lancés gardent l'action par défaut du signal (un piège attrapé est remis par défaut dans les enfants).
# L'écriture qui a échoué laisse son texte dans le tampon de sortie du shell, que chaque écriture suivante (journal, sortie d'une commande capturée)
# viderait à sa place : « exec >/dev/null 2>&1 » puis un écho vers chacun des deux le jettent avant tout autre écrit ; le journal et l'écran
# d'origine sont écrits ensuite par direct().
trap 'SIGCODE=PIPE; exec >/dev/null 2>&1; echo; echo >&2; exit 141' PIPE

# --- outils Git et système ---------------------------------------------------------------------------------------------------------
wt_of_branch() { # branche : le dossier de son worktree, rien si elle n'en a pas
  git -C "$WS" worktree list --porcelain 2>/dev/null | awk -v b="refs/heads/$1" '/^worktree /{p=substr($0,10)} $0=="branch " b {print p}'
}
# Propreté de l'espace de travail du train (départ, avance rapide, vérification finale). Décision de l'auteur R-20261102-6 (train T20 en 75 le 2026-11-02 à
# 09:47 : un livrable de posture, non suivi, écrit sous _bmad-output/ pendant le contrôle final). Un fichier NON SUIVI dont le chemin commence par
# `_bmad-output/` est ignoré ; tout le reste refuse comme avant : fichier suivi modifié ou indexé (sous _bmad-output/ aussi), non suivi ailleurs, échec de Git.
# Remplace : le refus de tout fichier non suivi dans l'espace de travail (« git status --porcelain » non vide). Retrait : quand les livrables de posture
# quittent l'espace de travail (la règle redevient « git status --porcelain » vide). Ne touche pas fa_clean (worktrees des branches et d'intégration).
# La même règle s'applique au contrôle avant l'avance rapide de main en retard et au message de l'arrivée, par cohérence avec le 61.
ws_clean() { # dossier : 0 quand rien n'est modifié, indexé ou non suivi hors _bmad-output/ ; 1 sinon, dont un échec de Git
  local out rec
  # le statut de Git (et non celui de tr) décide, par un test et non par une sortie calculée : seule celle de refus() est permise (registre des codes)
  out=$(git -C "$1" status --porcelain=v1 -z 2>/dev/null | tr '\0' '\001'; [ "${PIPESTATUS[0]}" -eq 0 ]) || return 1
  while IFS= read -r -d $'\001' rec; do
    case "$rec" in
      "?? _bmad-output/"*) ;;
      *) return 1 ;;
    esac
  done <<< "$out"
  return 0
}
# Conflit à l'avance rapide : un fichier non suivi sous _bmad-output/ au chemin d'un fichier que la fusion apporte fait échouer `git merge --ff-only`.
# Décision de l'auteur R-20261102-37 (Q313) : contrôle AVANT le runner (juste après la construction du train, aussi en --essai) et avant l'avance rapide de
# main en retard : tel fichier refuse en 64, chemins nommés. Remplace : l'échec silencieux de l'avance rapide (63 au départ, 73 à l'arrivée). Retrait : avec la
# règle de R-20261102-6 (quand les livrables de posture quittent l'espace de travail). Reste en dernier recours, pour un fichier écrit après ce contrôle
# (pendant le runner) : la même phrase, dite avant le 73 existant par ws_bmad_report.
ws_bmad_collect() { # révision : pose BMAD_N (nombre) et BMAD_LIST (un chemin cité par ligne) des non-suivis de _bmad-output/ dont le chemin existe dans la révision
  local f QP
  BMAD_N=0; BMAD_LIST=""
  while IFS= read -r -d '' f; do
    [ -n "$f" ] || continue
    git -C "$WS" cat-file -e "$1:$f" 2>/dev/null || continue
    BMAD_N=$((BMAD_N + 1)); quote_path "$f"; BMAD_LIST="${BMAD_LIST}${QP}
"
  done < <(git -C "$WS" ls-files --others --exclude-standard -z -- _bmad-output/ 2>/dev/null)
}
ws_bmad_report() { # révision : écrit la phrase et les chemins quand de tels fichiers existent ; rien sinon
  ws_bmad_collect "$1"
  [ "$BMAD_N" -gt 0 ] || return 0
  say "fichier non suivi de l'espace de travail au chemin d'un fichier du train : $BMAD_N ; le retirer de l'espace de travail puis relancer"
  printf '%s' "$BMAD_LIST"
}
ws_bmad_check() { # révision : refus 64 quand de tels fichiers existent
  ws_bmad_report "$1"
  [ "$BMAD_N" -eq 0 ] || refus 64 "espace de travail en collision avec le train ; rien n'est fusionné"
}
ign_dirs_phrase() { # entrée : FA_IGN_DIRS (module tools/finish_admission.sh, un dossier par ligne) ; sortie : triés, séparés par « , », comme les dossiers de l'admission
  printf '%s' "$FA_IGN_DIRS" | sort | tr '\n' ',' | sed 's/,$//; s/,/, /g'
}
try_remove_wt() { # dossier : retire le worktree sans force après avoir revérifié propreté, fichiers ignorés et processus ; sinon pose KEEP_REASON
  local p=$1 rc
  KEEP_REASON=""
  [ -d "$p" ] || return 0
  fa_clean "$p" || { KEEP_REASON="worktree pas propre"; return 1; }
  fa_ignored "$p"
  if [ "$FA_IGN_COUNT" -gt 0 ]; then KEEP_REASON="fichiers ignorés qui seraient perdus ($FA_IGN_COUNT)"; return 1; fi
  fs_processes "$p"; rc=$?
  if [ "$rc" -eq 2 ]; then KEEP_REASON="processus dans le worktree (vérification impossible)"; return 1; fi
  if [ "$rc" -eq 1 ]; then KEEP_REASON="processus dans le worktree (${FS_PROCESSES%%, *})"; return 1; fi
  git -C "$WS" worktree remove "$p" >/dev/null 2>&1 || { KEEP_REASON="retrait refusé par git"; return 1; }
  return 0
}

# --- 1. usage ---------------------------------------------------------------------------------------------------------------------------
set_ligne() { # la ligne à relancer et le texte d'usage, depuis le dossier d'exécution des dossiers du lab (jamais un chemin écrit en dur)
  local run
  if lab_paths_init >/dev/null 2>&1; then
    run=$LAB_RUN_TREE
    case "$run" in "$HOME"/*) run="~/${run#"$HOME"/}" ;; esac
    LIGNE="bash $run/tools/finish_train.sh"
  fi
  USAGE="usage : $LIGNE [--essai] <branche> [<branche> …] (1 à 6 branches, chacune une fois)"
}
parse_args() {
  local a b
  NAMES=()
  for a in "$@"; do
    case "$a" in
      --essai) [ "$ESSAI" = 0 ] || refus 60 "$USAGE"; ESSAI=1 ;;
      --auto) [ "$AUTO" = 0 ] || refus 60 "$USAGE"; AUTO=1; MODE=auto ;;   # autonomous-trains-merge, D8 : la politique remplace la question o/n
      -*|'') refus 60 "$USAGE" ;;
      *) for b in "${NAMES[@]}"; do [ "$b" != "$a" ] || refus 60 "$USAGE"; done; NAMES+=("$a") ;;
    esac
  done
  if [ "${#NAMES[@]}" -lt 1 ] || [ "${#NAMES[@]}" -gt 6 ]; then refus 60 "$USAGE"; fi
  if [ "$AUTO" = 1 ] && [ "$ESSAI" = 1 ]; then refus 60 "usage : --auto et --essai ne vont pas ensemble"; fi
}

# --- 1 bis. garde de version de python3 (faux 65 du train automatique, D3) ------------------------------------------------------------------
check_python() { # refus 76 quand python3 manque dans le PATH ou vaut moins que 3.10 ; avant le premier appel de python3 des étapes, et un seul appel ici
  STEP="version de python3"
  if ! command -v python3 >/dev/null 2>&1 || ! python3 -I -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' </dev/null >/dev/null 2>&1; then
    ETAT_RIEN=1
    refus 76 "calcul impossible (python3 3.10 ou plus introuvable) ; rien n'est fusionné"
  fi
}

# --- 2. lancement (D1) ------------------------------------------------------------------------------------------------------------------
launch_checks() {
  local runphys codephys main origin here w p pp uname umail
  # autonomous-trains-merge, D8 : --auto ne se lance jamais depuis un terminal (la question o/n reste celle de l'auteur) ; R-20261106-57 Q1 (a) : ni FINISH_TRAIN_CI ni FINISH_TRAIN_RUNNER ne sont posées (remplace « aucune variable n'est une exemption » ; retrait, R-20261107-4 : tombe quand finish_train.sh ne lit plus aucune variable FINISH_TRAIN_* sous --auto)
  if [ "$AUTO" = 1 ] && [ -t 0 ]; then refus 61 "lancement refusé : --auto depuis un terminal ; le train de l'auteur garde la question"; fi
  if [ "$AUTO" = 1 ] && { [ -n "${FINISH_TRAIN_CI:-}" ] || [ -n "${FINISH_TRAIN_RUNNER:-}" ]; }; then refus 61 "lancement refusé : --auto avec FINISH_TRAIN_CI ou FINISH_TRAIN_RUNNER posée ; une variable de substitution ne fusionne jamais seule"; fi
  runphys=$(cd "$LAB_RUN_TREE" 2>/dev/null && pwd -P) || runphys=""
  codephys=$(cd "$SCRIPT_DIR/.." && pwd -P)
  if [ -z "$runphys" ] || [ "$codephys" != "$runphys" ]; then refus 61 "lancement refusé : à lancer depuis le dossier d'exécution"; fi
  [ -z "${CLAUDECODE:-}" ] || refus 61 "lancement refusé : session Claude Code ; le train se termine dans le Terminal de l'auteur"
  RUN=$runphys
  COMMON=$(git -C "$RUN" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || refus 61 "lancement refusé : dossier d'exécution modifié ou pas détaché"
  WS=$(dirname "$COMMON")
  if [ -n "$(git -C "$RUN" status --porcelain 2>/dev/null)" ] || git -C "$RUN" symbolic-ref -q HEAD >/dev/null 2>&1; then
    refus 61 "lancement refusé : dossier d'exécution modifié ou pas détaché"
  fi
  # position du dossier d'exécution (décision du 2026-10-27, D1) : détaché sur main local ou sur origin/main (tels qu'avant le fetch), accepté tout de
  # suite ; toute autre position est revérifiée à la détection de l'état, après le fetch (detect_state)
  RUN_HEAD=$(git -C "$RUN" rev-parse HEAD 2>/dev/null)
  main=$(git -C "$WS" rev-parse -q --verify refs/heads/main 2>/dev/null)
  origin=$(git -C "$WS" rev-parse -q --verify refs/remotes/origin/main 2>/dev/null)
  if [ "$RUN_HEAD" != "$main" ] && [ "$RUN_HEAD" != "$origin" ]; then RUN_PENDING=1; fi
  [ "$(git -C "$WS" symbolic-ref -q --short HEAD 2>/dev/null)" = main ] || refus 61 "lancement refusé : l'espace de travail n'est pas sur main"
  ws_clean "$WS" || refus 61 "lancement refusé : l'espace de travail n'est pas propre"
  here=$(pwd -P)
  for w in "${NAMES[@]}"; do
    p=$(wt_of_branch "$w")
    [ -n "$p" ] || continue
    pp=$(cd "$p" 2>/dev/null && pwd -P) || continue
    case "$here/" in "$pp"/*) refus 61 "lancement refusé : le dossier courant est dans le worktree de $w" ;; esac
  done
  uname=$(git -C "$WS" config user.name 2>/dev/null); umail=$(git -C "$WS" config user.email 2>/dev/null)
  if [ -z "$uname" ] || [ -z "$umail" ]; then refus 61 "lancement refusé : identité Git de l'auteur absente"; fi
}

# --- 3. verrou et garde du matin (D3) ---------------------------------------------------------------------------------------------------
take_lock() {
  local rc
  finish_lock_acquire "$COMMON" train; rc=$?
  case "$rc" in
    0) LOCK_TAKEN=1 ;;
    1) refus 67 "une autre fin de branche est en cours (${FL_BRANCH:-?}, depuis $(finish_lock_hhmm "$FL_START"))" ;;
    *) refus 67 "verrou de fin de branche impossible à créer" ;;
  esac
}
# Gel ciblé (autonomous-trains-merge, D18 point 1) : sous son jeton et avant toute construction, le train écrit dans le verrou ses branches, le
# worktree de chacune et le worktree d'intégration (son nom est choisi ici et repris par integration_checks). Un échec d'écriture ne change aucun
# code : le verrou reste sans liste lisible, que les lecteurs traitent comme « tout gelé » (échec fermé).
# Remplace : rien (le verrou ne portait que pid, debut, branche, jeton). Retrait : permanent, tant que le gel est ciblé.
record_freeze() {
  local b p
  INTEG_NAME="wt-train-$(date +%Y%m%d-%H%M%S)"
  {
    for b in "${NAMES[@]}"; do
      printf 'B %s\n' "$b"
      p=$(wt_of_branch "$b")
      [ -z "$p" ] || printf 'W %s\n' "$p"
    done
    printf 'W %s\n' "$LAB_WORKTREES_FOLDER/$INTEG_NAME"
  } | finish_lock_record || say "gel ciblé : liste non écrite (verrou hérité ou écriture impossible)"
}
announce_test_variables() {
  [ -z "${FINISH_TRAIN_RUNNER:-}" ] || say "commande de test posée : FINISH_TRAIN_RUNNER"
  [ -z "${FINISH_TRAIN_CI:-}" ] || say "commande de test posée : FINISH_TRAIN_CI"
  [ -z "${FINISH_TRAIN_MORNING_CHECK:-}" ] || say "commande de test posée : FINISH_TRAIN_MORNING_CHECK"
}
morning_guard() {
  # R-20261102-3 et R-20261102-5 : la garde ne refuse (1) que si la veille ou la sauvegarde du jour tournent ; deux lignes (design D4)
  local cmd out rc
  if [ -n "${FINISH_TRAIN_MORNING_CHECK:-}" ]; then cmd=$FINISH_TRAIN_MORNING_CHECK; else cmd="bash \"$SCRIPT_DIR/morning_state.sh\" check"; fi
  out=$(eval "$cmd" </dev/null 2>&1 3>&- 4>&-); rc=$?
  if [ "$rc" -ne 0 ]; then
    say "veille ou sauvegarde du jour en cours"
    [ -z "$out" ] || raw "${out%%$'\n'*}"   # la première ligne seulement, règle de R-20261102-3 et -5
    refus 66 "relancer la même ligne quand la veille et la sauvegarde sont finies"
  fi
}

# --- 4. base et état des références (D4, D5) -------------------------------------------------------------------------------------------
establish_base() {
  git -C "$WS" fetch -q origin main </dev/null >/dev/null 2>&1 3>&- 4>&- || refus 63 "base non établie : fetch d'origin/main en échec ; rien n'est fusionné"
  BASE=$(git -C "$WS" rev-parse -q --verify "refs/remotes/origin/main^{commit}" 2>/dev/null)
  [ -n "$BASE" ] || refus 63 "base non établie : fetch d'origin/main en échec ; rien n'est fusionné"
  REF_READ=1
  MAIN_START=$(git -C "$WS" rev-parse -q --verify "refs/heads/main^{commit}" 2>/dev/null)
  # D20 (finish-single-b3-b6, B6) : un main local strictement en retard (ancêtre propre d'origin/main) est avancé en avance rapide, l'espace de travail
  # étant sur main et propre (vérifié au lancement) ; un main en retard n'est pas un état de reprise par lui-même (si origin/main porte déjà ce train,
  # l'avance mène à S2, accepté : Q3 (a), R-20261030-48) ; un échec laisse main où il était
  if [ -n "$MAIN_START" ] && [ "$MAIN_START" != "$BASE" ] && git -C "$WS" merge-base --is-ancestor "$MAIN_START" "$BASE" 2>/dev/null; then
    local old=$MAIN_START
    # revue de B6, C3 : « sur main et propre » est revérifié juste avant l'avance (git merge avance la branche courante) ; sinon le même 63 d'échec
    if [ "$(git -C "$WS" symbolic-ref -q --short HEAD 2>/dev/null)" = main ] && ws_clean "$WS"; then
      STEP="base"
      ws_bmad_check "$BASE"   # R-20261102-37 (Q313) : un non suivi de _bmad-output/ au chemin d'un fichier de la base refuse en 64 avant l'avance
      git -C "$WS" merge --ff-only -q "$BASE" </dev/null >/dev/null 2>&1 3>&- 4>&-
    fi
    MAIN_START=$(git -C "$WS" rev-parse -q --verify "refs/heads/main^{commit}" 2>/dev/null)
    if [ "$MAIN_START" != "$BASE" ]; then
      MAIN_START=$old
      STEP="base"
      refus 63 "base non établie : avance rapide de main local en échec ; rien n'est fusionné"
    fi
    say "main local en retard avancé sur origin/main : $(sha12 "$old") -> $(sha12 "$BASE")"
  fi
  if [ -n "$(git -C "$WS" config --get-regexp '^merge\..*\.driver$' 2>/dev/null)" ]; then
    refus 63 "base non établie : pilote de fusion personnalisé configuré ; rien n'est fusionné"
  fi
}
verify_chain() { # S1|S2 : CHAIN porte les commits du plus ancien au plus récent ; la chaîne doit être exactement le train de la liste (D5)
  local mode=$1 k=0 prev="" c nm tipnow tree mt mtout mtrc res uname umail
  local -a arr
  uname=$(git -C "$WS" config user.name); umail=$(git -C "$WS" config user.email)
  for c in $CHAIN; do
    nm=${NAMES[$k]}
    read -r -a arr <<< "$(git -C "$WS" rev-list --parents -n 1 "$c")"
    [ "${#arr[@]}" -eq 3 ] || return 1
    if [ "$k" -eq 0 ]; then
      if [ "$mode" = S1 ]; then [ "${arr[1]}" = "$BASE" ] || return 1; else CHAIN_BASE=${arr[1]}; fi
    else
      [ "${arr[1]}" = "$prev" ] || return 1
    fi
    tipnow=$(git -C "$WS" rev-parse -q --verify "refs/heads/$nm^{commit}" 2>/dev/null)
    if [ -n "$tipnow" ]; then [ "$tipnow" = "${arr[2]}" ] || return 1; elif [ "$mode" = S1 ]; then return 1; fi
    tree=$(git -C "$WS" rev-parse "$c^{tree}" 2>/dev/null)
    mtout=$(git -C "$WS" merge-tree --write-tree "${arr[1]}" "${arr[2]}" 2>/dev/null </dev/null); mtrc=$?
    [ "$mtrc" -eq 0 ] || return 1   # une fusion qui ne se fait pas proprement n'est jamais le train (revue de u5, m-6)
    mt=$(sed -n 1p <<< "$mtout")
    [ -n "$mt" ] && [ "$mt" = "$tree" ] || return 1
    res=$(git -C "$WS" cat-file commit "$c" | awk 'BEGIN{h=1} h==1&&$0==""{h=2;next} h==1{ if($1=="parent")np++; else if($1!="tree"&&$1!="author"&&$1!="committer")bad=1 } h==2{n++;b=$0} END{print bad+0, np+0, n+0, b}')
    [ "$res" = "0 2 1 Merge branch '$nm'" ] || return 1
    git -C "$WS" cat-file commit "$c" | awk -v a="author $uname <$umail> " -v m="committer $uname <$umail> " 'index($0,a)==1{fa=1} index($0,m)==1{fm=1} END{exit !(fa&&fm)}' || return 1
    prev=$c; k=$((k + 1))
  done
  [ "$k" -eq "${#NAMES[@]}" ]
}
carried_listed() { # vrai quand main local porte la fusion d'une branche de la liste : le sommet noté de la branche est un ancêtre de main local et
  # n'est pas un ancêtre d'origin/main (décision du 2026-10-27, D4) ; l'ascendance Git décide, jamais le message du commit
  local nm tip
  for nm in "${NAMES[@]}"; do
    tip=$(git -C "$WS" rev-parse -q --verify "refs/heads/$nm^{commit}" 2>/dev/null)
    [ -n "$tip" ] || continue
    if git -C "$WS" merge-base --is-ancestor "$tip" "$MAIN_START" 2>/dev/null && ! git -C "$WS" merge-base --is-ancestor "$tip" "$BASE" 2>/dev/null; then
      return 0
    fi
  done
  return 1
}
detect_state() {
  local n=${#NAMES[@]} subj cnt found=0
  CHAIN_BASE=""
  if [ "$MAIN_START" = "$BASE" ]; then
    CHAIN=$(git -C "$WS" rev-list --first-parent --reverse -n "$n" refs/heads/main 2>/dev/null)
    subj=$(git -C "$WS" log -1 --format=%s refs/heads/main 2>/dev/null)
    if [ "$subj" = "Merge branch '${NAMES[$((n - 1))]}'" ] && verify_chain S2; then START_STATE=S2; TRAIN_TIP=$MAIN_START
    else START_STATE=S0; CHAIN_BASE=""; fi
  else
    if git -C "$WS" merge-base --is-ancestor "$BASE" "$MAIN_START" 2>/dev/null; then
      CHAIN=$(git -C "$WS" rev-list --first-parent --reverse "$BASE..$MAIN_START" 2>/dev/null)
      cnt=$(grep -c . <<< "$CHAIN")
      if [ "$cnt" -eq "$n" ] && verify_chain S1; then START_STATE=S1; TRAIN_TIP=$MAIN_START; found=1; fi
    fi
    if [ "$found" = 0 ]; then
      if carried_listed; then
        STEP="état des références"
        refus 79 "reprise refusée : main $(sha12 "$MAIN_START") porte tout ou partie des fusions des branches données sans être le train pur sur origin/main $(sha12 "$BASE") ; rien n'est touché"
      fi
      STEP="base"
      refus 63 "base non établie : main local $(sha12 "$MAIN_START") diffère d'origin/main $(sha12 "$BASE") ; rapproche-les à la main, puis relance ; rien n'est fusionné"
    fi
  fi
  # position du dossier d'exécution revérifiée après le fetch (décision du 2026-10-27, D1 et D5) : origin/main, ou la base du train déjà poussé en S2
  if [ "$RUN_PENDING" = 1 ] && [ "$RUN_HEAD" != "$BASE" ]; then
    if [ "$START_STATE" != S2 ] || [ "$RUN_HEAD" != "$CHAIN_BASE" ]; then
      refus 61 "lancement refusé : dossier d'exécution détaché sur $(sha12 "$RUN_HEAD"), ni main local, ni origin/main, ni la base du train déjà poussé"
    fi
  fi
}

# --- 5. admission (D6) ------------------------------------------------------------------------------------------------------------------
REFUSED_N=0; REF_LINES=""; BR_REFUSED=0; SENS_LINES=""; SENS=""; PROT_LINES=""
add_reason() { REF_LINES="${REF_LINES}  - $1 : $2
"; BR_REFUSED=1; }
json_verdict() { sed -nE 's/.*\{"id": "'"$2"'", "verdict": "([a-z]*)".*/\1/p' <<< "$1" | sed -n 1p; }
json_phrase() { sed -nE 's/.*\{"id": "'"$2"'", "verdict": "[a-z]*", "phrase": "(([^"\\]|\\.)*)".*/\1/p' <<< "$1" | sed -n 1p | sed -e 's/\\"/"/g' -e 's/\\\\/\\/g'; }
json_error() { sed -nE 's/.*"error": "(([^"\\]|\\.)*)".*/\1/p' <<< "$1" | sed -n 1p | sed -e 's/\\"/"/g' -e 's/\\\\/\\/g'; }
json_classes_present() { # vrai quand la sortie JSON de finish_checks porte les deux champs de classe, avant "exit" (finish-single-b3-b6 B4, D9 et D11)
  grep -qE '"protected_judges": \[.*\], "protected_sensitive": \[.*\], "exit": [0-9]+' <<< "$1"
}
json_protected() { # champ (protected_judges ou protected_sensitive) : un chemin par ligne, lu dans la sortie JSON de finish_checks ; jamais la liste protégée elle-même
  local arr
  case "$1" in
    protected_judges) arr=$(sed -nE 's/.*"protected_judges": \[(.*)\], "protected_sensitive": \[.*\], "exit": [0-9]+.*/\1/p' <<< "$2" | sed -n 1p) ;;
    *) arr=$(sed -nE 's/.*"protected_sensitive": \[(.*)\], "exit": [0-9]+.*/\1/p' <<< "$2" | sed -n 1p) ;;
  esac
  [ -z "$arr" ] || grep -oE '"(([^"\\]|\\.)*)"' <<< "$arr" | sed -e 's/^"//' -e 's/"$//' -e 's/\\"/"/g' -e 's/\\\\/\\/g'
}
json_runner_present() { # vrai quand la sortie JSON de finish_checks porte le champ runner_proof_touched, avant protected_touched (autonomous-trains-merge D3)
  grep -qE '"runner_proof_touched": \[.*\], "protected_touched": ' <<< "$1"
}
json_runner() { # un chemin par ligne : les chemins du runner et de la preuve que la branche change, lus dans le champ runner_proof_touched du JSON (liste unique : tools/finish_runner_paths.txt)
  local arr
  arr=$(sed -nE 's/.*"runner_proof_touched": \[(.*)\], "protected_touched": .*/\1/p' <<< "$1" | sed -n 1p)
  [ -z "$arr" ] || grep -oE '"(([^"\\]|\\.)*)"' <<< "$arr" | sed -e 's/^"//' -e 's/"$//' -e 's/\\"/"/g' -e 's/\\\\/\\/g'
}
admit_branch() { # nom : pose ADM_TIP, ajoute les motifs de refus
  local nm=$1 path out rc l phrase id v f
  ADM_TIP=""; BR_REFUSED=0; ADM_JUDGE=""
  ADM_TIP=$(git -C "$WS" rev-parse -q --verify "refs/heads/$nm^{commit}" 2>/dev/null)
  if [ -z "$ADM_TIP" ]; then add_reason "$nm" "introuvable en local"; return 0; fi
  if git -C "$WS" merge-base --is-ancestor "$ADM_TIP" "refs/remotes/origin/main" 2>/dev/null; then add_reason "$nm" "déjà contenue dans origin/main"; return 0; fi
  path=$(wt_of_branch "$nm")
  if [ -n "$path" ] && [ -d "$path" ]; then
    fa_clean "$path" || add_reason "$nm" "worktree pas propre"
    fa_ignored "$path"
    if [ "$FA_IGN_COUNT" -gt 0 ]; then add_reason "$nm" "$FA_IGN_COUNT fichier(s) ignoré(s) seraient perdus (dossiers : $(ign_dirs_phrase))"; fi
    fs_processes "$path"; rc=$?
    if [ "$rc" -eq 2 ]; then add_reason "$nm" "vérification des processus impossible"
    elif [ "$rc" -eq 1 ]; then add_reason "$nm" "un processus a son dossier courant dans son worktree (${FS_PROCESSES%%, *})"; fi
  fi
  # D6 : finish_checks.py branch … --json (format 1) ; sortie 0 ou 1, les cinq contrôles présents (le 16 jamais un motif de refus) ; sinon la branche est refusée
  out=$(python3 -I "$SCRIPT_DIR/finish_checks.py" branch "$nm" --repo "$WS" --json 2>/dev/null </dev/null); rc=$?
  PROT=""; SENS=""
  case "$rc" in
    3|4)
      phrase=$(json_error "$out")
      if [ -z "$phrase" ]; then add_reason "$nm" "contrôles impossibles : sortie inattendue de finish_checks (code $rc)"
      elif [ "$rc" -eq 3 ]; then phrase=${phrase#branche non contrôlable : }; add_reason "$nm" "non contrôlable : $phrase"
      else add_reason "$nm" "contrôles impossibles : $phrase"; fi
      return 0 ;;
    0|1) ;;
    *) add_reason "$nm" "contrôles impossibles : sortie inattendue de finish_checks (code $rc)"; return 0 ;;
  esac
  if ! grep -q '^{"format": 1, ' <<< "$out"; then add_reason "$nm" "contrôles impossibles : format de sortie de finish_checks inconnu"; return 0; fi
  for id in 19 5 6 14 16; do
    if [ -z "$(json_verdict "$out" "$id")" ]; then add_reason "$nm" "contrôles impossibles : contrôle $id absent de la sortie de finish_checks"; return 0; fi
  done
  # B4, D11 : les classes de l'outillage protégé viennent du JSON du module seulement ; une sortie sans les deux champs est refusée (jamais une classe par défaut)
  if ! json_classes_present "$out"; then add_reason "$nm" "contrôles impossibles : classes de l'outillage protégé absentes de la sortie de finish_checks"; return 0; fi
  if ! json_runner_present "$out"; then add_reason "$nm" "contrôles impossibles : chemins du runner et de la preuve absents de la sortie de finish_checks"; return 0; fi
  RUNF=$(json_runner "$out")
  # B6, D19 : le contrôle 6 de la branche (présent, vérifié plus haut) n'est plus un motif de refus : l'arbre du train en décide
  for id in 19 5; do
    v=$(json_verdict "$out" "$id")
    case "$id:$v" in
      19:pass|19:exempt|5:pass|5:exempt) ;;
      *:refused) phrase=$(json_phrase "$out" "$id"); add_reason "$nm" "contrôle $id refusé : ${phrase#"contrôle $id : refusé : "}" ;;
      *) add_reason "$nm" "contrôle $id refusé : verdict inconnu" ;;
    esac
  done
  phrase=$(json_protected protected_judges "$out")
  [ -z "$phrase" ] || PROT="${phrase}
"
  SENS=$(json_protected protected_sensitive "$out")
  while IFS= read -r -d '' f; do
    [ -n "$f" ] || continue
    case "$f" in
      .claude/*|CLAUDE.md|*/CLAUDE.md)
        if ! grep -qxF "$f" <<< "$PROT"; then PROT="${PROT}${f}
"; fi ;;
    esac
  done < <(git -C "$WS" diff --name-only -z "refs/remotes/origin/main...refs/heads/$nm" 2>/dev/null)
  PROT_BAD=0
  if [ -n "$PROT" ]; then
    # D18 : un fichier `juge`, ou .claude/ et un CLAUDE.md (la lecture du train lui-même, gardée) : admis dans un train d'une seule branche.
    # R-20261102-43 : à plusieurs branches, .claude/ et un CLAUDE.md restent refusés (fin de l'auteur) ; un fichier `juge` est admis, jusqu'à 3 branches
    # juges sans fichier juge commun (contrôle croisé dans admission()) ; la construction, dans l'ordre de la ligne, refuse tout conflit (64).
    if [ "${#NAMES[@]}" -gt 1 ] && grep -qE '^(\.claude/.*|CLAUDE\.md|.*/CLAUDE\.md)$' <<< "$PROT"; then
      PROT_BAD=1
      add_reason "$nm" "outillage de fin touché ($(grep -c . <<< "$PROT") fichier(s)) : train d'une seule branche"
      while IFS= read -r f; do [ -z "$f" ] || REF_LINES="${REF_LINES}      $f
"; done <<< "$PROT"
    elif [ "${#NAMES[@]}" -gt 1 ] && [ -n "$RUNF" ]; then
      # R-20261102-43 (ajout de l'auteur) : nouvelle règle ; remplace : rien (restreint l'allègement « jusqu'à 3 branches juges ») ; retrait : permanent tant que
      # le train juge son arbre avec le runner et la preuve portés par ses propres branches. Une branche qui modifie le runner ou la preuve reste seule dans son
      # train ; elle ne compte pas parmi les 3 branches juges (elle est refusée, donc absente de JSETS).
      PROT_BAD=1
      add_reason "$nm" "modifie le runner ou la preuve : train d'une seule branche (R-20261102-43)"
      while IFS= read -r f; do
        [ -z "$f" ] || { quote_path "$f"; REF_LINES="${REF_LINES}      $QP
"; }
      done <<< "$RUNF"
    elif [ "${#NAMES[@]}" -gt 1 ]; then
      ADM_JUDGE=$PROT
    else
      PROT_LINES="${PROT_LINES}finish_train : outillage de fin dans ce train d'une branche : $(grep -c . <<< "$PROT") fichier(s)
"
      while IFS= read -r f; do [ -z "$f" ] || PROT_LINES="${PROT_LINES}      $f
"; done <<< "$PROT"
    fi
  fi
  if [ -n "$SENS" ] && { [ -z "$PROT" ] || [ "$PROT_BAD" != 1 ]; }; then
    # D11 et D12 : seulement des fichiers `sensible` : admis quand la revue Opus est enregistrée pour le sommet exact de la branche, refusé sinon
    if fa_review_done "$nm" "$ADM_TIP"; then
      SENS_LINES="${SENS_LINES}finish_train : outil sensible admis après revue Opus du sommet $(sha12 "$ADM_TIP") : $nm
"
      while IFS= read -r f; do [ -z "$f" ] || SENS_LINES="${SENS_LINES}      $f
"; done <<< "$SENS"
    else
      add_reason "$nm" "outil sensible touché ($(grep -c . <<< "$SENS") fichier(s)) sans revue Opus enregistrée pour le sommet $(sha12 "$ADM_TIP") : revue ou fin unitaire"
      while IFS= read -r f; do [ -z "$f" ] || REF_LINES="${REF_LINES}      $f
"; done <<< "$SENS"
    fi
  fi
  # Un chemin d'interface de Mothra changé n'écarte plus la branche (finish-e2e-proof-shared, D6) : l'arbre du train décide, à l'étape de la passe e2e.
  return 0
}
admission() {
  local k n=${#NAMES[@]} rest="" nm i j f judges=0 njf
  local -a REFK JSETS
  STEP="admission"
  TIPS=()
  for ((k = 0; k < n; k++)); do
    nm=${NAMES[$k]}
    admit_branch "$nm"
    TIPS[$k]=$ADM_TIP
    REFK[$k]=$BR_REFUSED
    JSETS[$k]=""
    [ "$BR_REFUSED" = 1 ] || JSETS[$k]=$ADM_JUDGE
  done
  # R-20261102-43 : jusqu'à 3 branches juges par train, deux branches juges ne touchent jamais le même fichier juge (rangs = place dans la ligne, de 1 à 6).
  # Remplace : « une branche juge passe seule » ; retrait : permanent tant que le train porte des branches juges. Les branches déjà refusées ne comptent pas.
  for ((j = 0; j < n; j++)); do
    [ -n "${JSETS[$j]}" ] || continue
    nm=${NAMES[$j]}
    for ((i = 0; i < j; i++)); do
      [ -n "${JSETS[$i]}" ] || continue
      while IFS= read -r f; do
        [ -n "$f" ] || continue
        if grep -qxF "$f" <<< "${JSETS[$i]}"; then
          quote_path "$f"
          REF_LINES="${REF_LINES}  - $nm : fichier juge $QP touché aussi par la branche de rang $((i + 1)) (rang $((j + 1)) ici) : deux branches juges ne passent pas ensemble
"
          REFK[$j]=1; JSETS[$j]=""
          break 2
        fi
      done <<< "${JSETS[$j]}"
    done
  done
  for ((k = 0; k < n; k++)); do
    [ -n "${JSETS[$k]}" ] || continue
    judges=$((judges + 1))
    if [ "$judges" -gt 3 ]; then
      REF_LINES="${REF_LINES}  - ${NAMES[$k]} : quatrième branche juge (rang $((k + 1))) : au plus 3 branches juges par train
"
      REFK[$k]=1; JSETS[$k]=""; judges=$((judges - 1))
    fi
  done
  for ((k = 0; k < n; k++)); do
    nm=${NAMES[$k]}
    if [ "${REFK[$k]}" = 1 ]; then REFUSED_N=$((REFUSED_N + 1)); else rest="${rest}${rest:+ }$(printf '%q' "$nm")"; fi
    if [ -n "${JSETS[$k]}" ]; then
      njf=$(grep -c . <<< "${JSETS[$k]}")
      PROT_LINES="${PROT_LINES}finish_train : outillage de fin dans ce train de plusieurs branches (branche juge de rang $((k + 1)) : $nm) : $njf fichier(s)
"
      while IFS= read -r f; do [ -z "$f" ] || PROT_LINES="${PROT_LINES}      $f
"; done <<< "${JSETS[$k]}"
    fi
  done
  if [ "$REFUSED_N" -gt 0 ]; then
    say "branche(s) refusée(s) au train : $REFUSED_N sur $n ; rien n'est fusionné"
    printf '%s' "$REF_LINES"
    if [ -n "$rest" ]; then refus 62 "ligne sans les branches refusées : $LIGNE $rest"; fi
    refus 62 "aucune branche admise"
  fi
  # D11 : pour chaque branche admise qui touche des fichiers `sensible`, la ligne de la revue Opus qui l'autorise, avant la question
  [ -z "$SENS_LINES" ] || printf '%s' "$SENS_LINES"
  # D18 et R-20261102-43 : l'outillage de fin admis dans ce train d'une ou de plusieurs branches, avant la question
  [ -z "$PROT_LINES" ] || printf '%s' "$PROT_LINES"
}

# --- 6. construction du train (D7) ------------------------------------------------------------------------------------------------------
quote_path() { # chemin : pose QP, entre guillemets doubles à la manière de Git (\n, \t, \" et \\) quand il porte un de ces caractères, tel quel sinon
  local p=$1 out="" ch i
  case "$p" in
    *$'\n'*|*$'\t'*|*'"'*|*'\'*) ;;
    *) QP=$p; return 0 ;;
  esac
  for ((i = 0; i < ${#p}; i++)); do
    ch=${p:i:1}
    case "$ch" in
      $'\n') out="$out"'\n' ;;
      $'\t') out="$out"'\t' ;;
      '"') out="$out"'\"' ;;
      '\') out="$out"'\\' ;;
      *) out="$out$ch" ;;
    esac
  done
  QP="\"$out\""
}
run_merge_tree() { # courant sommet : sortie de merge-tree lue en -z, champ par champ sur l'octet nul, jamais ligne par ligne (D7) ;
  # pose MT_RC, MT_TREE et MT_PATHS (les chemins en conflit : les champs entre l'arbre et le premier champ vide)
  local f first=1
  MT_TREE=""; MT_PATHS=()
  MT="$COMMON/pmzilla-train-mt.$$"
  git -C "$WS" merge-tree --write-tree --name-only -z "$1" "$2" > "$MT" 2>/dev/null </dev/null; MT_RC=$?
  while IFS= read -r -d '' f; do
    if [ "$first" = 1 ]; then MT_TREE=$f; first=0; continue; fi
    [ -n "$f" ] || break
    MT_PATHS+=("$f")
  done < "$MT"
  rm -f "$MT"; MT=""
}
build_train() {
  local k n=${#NAMES[@]} cur=$BASE nm tip rc in_train="" cnt rest j p
  local -a in_names
  in_names=()
  STEP="construction"
  for ((k = 0; k < n; k++)); do
    nm=${NAMES[$k]}; tip=${TIPS[$k]}
    run_merge_tree "$cur" "$tip"; rc=$MT_RC
    case "$rc" in
      0)
        cur=$(git -C "$WS" commit-tree "$MT_TREE" -p "$cur" -p "$tip" -m "Merge branch '$nm'" 2>/dev/null) || refus 76 "calcul impossible (git en échec)"
        in_train="${in_train}${in_train:+, }$nm"; in_names+=("$nm") ;;
      1)
        # le contrôle des noms (D8) passe avant tout affichage des chemins en conflit (revue de u5, m-12)
        if [ "${#in_names[@]}" -gt 0 ]; then scan_content "$cur" "${in_names[@]}"; fi
        scan_content "$tip" "$nm"
        STEP="construction"
        cnt=${#MT_PATHS[@]}
        rest=""
        for ((j = 0; j < n; j++)); do [ "$j" -eq "$k" ] || rest="${rest}${rest:+ }$(printf '%q' "${NAMES[$j]}")"; done
        say "conflit à la construction du train : $nm avec $in_train sur $cnt fichier(s) ; rien n'est fusionné"
        for p in "${MT_PATHS[@]}"; do quote_path "$p"; raw "$QP"; done
        refus 64 "ligne sans cette branche : $LIGNE $rest" ;;
      *) refus 64 "construction du train impossible (git merge-tree, code $rc) ; rien n'est fusionné" ;;
    esac
  done
  TRAIN_TIP=$cur
  TRAIN_TREE=$(git -C "$WS" rev-parse "$cur^{tree}" 2>/dev/null)
  say "train construit : sommet $(sha12 "$TRAIN_TIP"), arbre $(sha12 "$TRAIN_TREE")"
}

# --- 7. contrôle du contenu (D8) --------------------------------------------------------------------------------------------------------
scan_content() { # sommet, puis les noms des branches qu'il porte
  STEP="contrôle des noms"
  local tip=$1 nm out rc rc2 js ligne inattendue=0 verdict s m i
  local -a args
  shift
  args=()
  for nm in "$@"; do args+=(--branch "$nm"); done
  out=$(python3 -I "$SCRIPT_DIR/range_scan.py" "$tip" "${args[@]}" --repo "$WS" </dev/null 2>&1); rc=$?
  # faux 65 du train automatique (D6) : seules les lignes `range_scan : ` sont montrées (et donc copiées au journal) ; toute autre ligne (une trace) se dit une fois
  while IFS= read -r ligne; do
    case "$ligne" in
      "range_scan : "*) raw "$ligne" ;;
      "") ;;
      *) inattendue=1 ;;
    esac
  done <<< "$out"
  [ "$inattendue" = 0 ] || say "sortie inattendue de range_scan"
  case "$rc" in
    0|1) ;;
    *) refus 68 "contrôle de contenu impossible (range_scan, code $rc) ; rien n'est fusionné" ;;
  esac
  js=$(python3 -I "$SCRIPT_DIR/range_scan.py" "$tip" "${args[@]}" --repo "$WS" --json </dev/null 2>/dev/null); rc2=$?
  NOT_EXAMINED=$(grep -o '"reason": "\(binary\|size\)"' <<< "$js" | grep -c .)
  # faux 65 (D5) : le code 65 demande deux lectures concordantes ; sinon 68, jamais une trouvaille supposée
  if [ "$rc" != "$rc2" ]; then
    refus 68 "contrôle de contenu impossible (range_scan, sortie incohérente : codes $rc et $rc2) ; rien n'est fusionné"
  fi
  if [ "$rc" -eq 1 ]; then
    verdict=$(python3 -I -c '
import json, sys
try:
    d = json.loads(sys.stdin.read())
    kinds = [f.get("kind") for f in d.get("findings", []) if isinstance(f, dict)]
    valide = isinstance(d, dict) and d.get("format") == 1 and d.get("exit") == 1
except Exception:
    valide, kinds = False, []
if valide and any(k in ("secret", "name", "identifier", "encoding") for k in kinds):
    print(kinds.count("secret"), kinds.count("name"), kinds.count("identifier"))
else:
    print("sans-trouvaille")
' <<< "$js" 2>/dev/null)
    if [ "$verdict" = "sans-trouvaille" ] || [ -z "$verdict" ]; then
      refus 68 "contrôle de contenu impossible (range_scan, sortie incohérente : code 1 sans trouvaille) ; rien n'est fusionné"
    fi
    read -r s m i <<< "$verdict"
    refus 65 "contenu refusé : le contrôle des noms et des secrets a trouvé $s secret(s), $m nom(s), $i identifiant(s) dans le train ; rien n'est fusionné"
  fi
}

# --- 8. contrôle 14, dbtest, runner (D9, D10) -------------------------------------------------------------------------------------------
tree_verdict() { # pose TV_CODE, TV_VERDICT (contrôle 14), TV16_VERDICT (contrôle 16) et TV16_DETAILS pour l'arbre du train ; chaque verdict est lu par son identifiant
  local js
  js=$(python3 -I "$SCRIPT_DIR/finish_checks.py" tree "$TRAIN_TREE" --repo "$WS" --json 2>/dev/null </dev/null); TV_CODE=$?
  TV_VERDICT=$(json_verdict "$js" 14)
  TV16_VERDICT=$(json_verdict "$js" 16)
  TV16_DETAILS=$(json_details "$js" 16)
  TV6_VERDICT=$(json_verdict "$js" 6)
  TV6_DETAILS=$(json_details "$js" 6)
  # journal des trains (D4) : « base » et « front » disent que le contrôle 14 ou le contrôle 16 est applicable à l'arbre du train (pass ou refused, jamais exempt)
  case "$TV_VERDICT" in pass|refused) REC_BASE=1 ;; esac
  case "$TV16_VERDICT" in pass|refused) REC_FRONT=1 ;; esac
}
json_details() { # json id : le contenu du tableau « details » du contrôle, chaînes entre guillemets séparées par « , » (le mode arbre rend 14, 16 puis 6)
  sed -nE 's/.*\{"id": "'"$2"'", "verdict": "[a-z]*", "phrase": "(([^"\\]|\\.)*)", "details": \[(("(([^"\\]|\\.)*)"(, )?)*)\]\}.*/\3/p' <<< "$1" | sed -n 1p
}
control6() { # D19 : contrôle 6 de l'arbre du train, juste après le contrôle 14 et avant l'installation npm ; refusé : code 83, rien n'est touché
  local l
  STEP="contrôle 6"
  case "$TV6_VERDICT" in
    exempt) say "jeu d'essai validant sans objet pour l'arbre du train (fichiers évalués inchangés)" ;;
    pass)
      l=$(grep -oE '"(([^"\\]|\\.)*)"' <<< "$TV6_DETAILS" | sed -e 's/^"//' -e 's/"$//' -e 's/\\"/"/g' -e 's/\\\\/\\/g' | sed -n 1p)
      l=${l#"jeu d'essai validant trouvé : "}
      say "jeu d'essai validant trouvé pour l'arbre du train : $l" ;;
    refused)
      say "jeu d'essai validant absent pour l'arbre du train ; rien n'est fusionné"
      while IFS= read -r l; do [ -z "$l" ] || raw "  $l"; done < <(grep -oE '"(([^"\\]|\\.)*)"' <<< "$TV6_DETAILS" | sed -e 's/^"//' -e 's/"$//' -e 's/\\"/"/g' -e 's/\\\\/\\/g')
      exit 83 ;;
    *) refus 68 "contrôle 6 du train impossible (finish_checks, verdict absent) ; rien n'est fusionné" ;;
  esac
}
control14() {
  STEP="contrôle 14"
  tree_verdict
  [ "$TV_CODE" -le 1 ] || refus 68 "contrôle 14 du train impossible (finish_checks, code $TV_CODE) ; rien n'est fusionné"
  [ "$TV_VERDICT" = exempt ] || say "passage du conteneur requis (phase base)"
  # contrôle 16 de la même sortie (finish-e2e-proof-shared, D5) : applicable (pass ou refused) = la passe est exigée, même quand une ligne existe déjà ;
  # sans objet = aucune passe ; absent de la sortie = calcul impossible, jamais une admission par défaut
  case "$TV16_VERDICT" in
    exempt) say "passe de bout en bout sans objet (chemins d'interface inchangés)" ;;
    pass|refused) say "phase e2e du conteneur requise" ;;
    *) refus 68 "contrôle 16 du train impossible (finish_checks, verdict absent) ; rien n'est fusionné" ;;
  esac
}
control6_resume() { # reprise au push (S1), Q3 (b) de l'auteur (R-20261030-48) : le contrôle 6 est rejoué sur l'arbre que main local porte ; refusé : 83, état E3
  TRAIN_TREE=$(git -C "$WS" rev-parse "$MAIN_START^{tree}" 2>/dev/null)
  [ -n "$TRAIN_TREE" ] || refus 68 "contrôle 6 du train impossible (arbre de main illisible) ; rien n'est poussé"
  STEP="contrôle 6"
  tree_verdict
  [ "$TV_CODE" -le 1 ] || refus 68 "contrôle 6 du train impossible (finish_checks, code $TV_CODE) ; rien n'est poussé"
  control6
}
stability_reason() { # écrit la raison de non-conclusion après un runner de code 0, rien si tout est stable
  # La règle de stabilité (propre, fichiers et dossiers suivis, seuls les ajouts ignorés pardonnés, échec d'outil = modifié) et le listage des processus
  # sont ceux de tools/finish_stability.sh (finish-single-b3-b6, D6) ; ici restent les phrases, le code 71 et l'empreinte du runner.
  local fp rc
  fs_verdict "$INTEG" "$MARK" "$DIR_SNAP" || { echo "worktree d'intégration modifié pendant le runner"; return 0; }
  fs_processes "$INTEG"; rc=$?
  if [ "$rc" -eq 2 ]; then echo "processus dans le worktree (vérification impossible)"; return 0; fi
  if [ "$rc" -eq 1 ]; then echo "processus dans le worktree d'intégration (${FS_PROCESSES%%, *})"; return 0; fi
  # Q219 (ci-local-runner, D9) : la preuve de la porte est la ligne de l'arbre du train dans pmzilla-run-mac-ok du dossier Git commun (écrite par la passe
  # Mac, D7) ET la ligne `<arbre><tab><clé><tab>portable,base,e2e` de ci/preuves du dossier de données (écrite par la porte du conteneur, D6), chacune dans un
  # fichier réécrit après le repère. Remplace : l'empreinte pmzilla-run-all-ok du worktree d'intégration réécrite par le runner complet (retirée du train).
  # Retrait : permanent tant que la porte du conteneur existe.
  fp=$(git -C "$INTEG" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
  fp="${fp:+$fp/pmzilla-run-mac-ok}"
  if [ -z "$fp" ] || ! grep -qxF -- "$TRAIN_TREE" "$fp" 2>/dev/null || [ -z "$(find "$fp" -maxdepth 0 -cnewer "$MARK" -print 2>/dev/null)" ]; then
    echo "empreinte du runner absente, différente de l'arbre du train ou non réécrite"
    return 0
  fi
  fp="$LAB_DATA_FOLDER/ci/preuves"
  if ! awk -F '\t' -v t="$TRAIN_TREE" '$1 == t && NF == 3 { ok = ($3 == "portable,base,e2e") ? 1 : 0 } END { exit ok ? 0 : 1 }' "$fp" 2>/dev/null \
     || [ -z "$(find "$fp" -maxdepth 0 -cnewer "$MARK" -print 2>/dev/null)" ]; then
    echo "preuve du conteneur absente, différente de l'arbre du train, sans exactement portable,base,e2e ou non réécrite"
  fi
  return 0
}
quoted_names() { # les noms de branche de la ligne, protégés pour le shell de l'auteur (printf %q : tels quels quand rien n'est à protéger)
  local n out=""
  for n in "${NAMES[@]}"; do out="${out}${out:+ }$(printf '%q' "$n")"; done
  printf '%s' "$out"
}
npm_advice() { # écrit, sur des lignes brutes, les branches du train qui modifient mothra/package-lock.json et la commande conseillée sur une ligne (décision B)
  # les chemins absolus de ces lignes sont voulus : ce sont des lignes à coller dans le Terminal
  local k b wt cmd="" noms=""
  for ((k = 0; k < ${#NAMES[@]}; k++)); do
    b=${NAMES[$k]}
    # un échec de git diff est lu comme « verrou inchangé » : le conseil seulement s'en trouve moins précis, rien d'autre
    [ -n "$(git -C "$WS" diff --name-only "refs/remotes/origin/main...${TIPS[$k]}" -- mothra/package-lock.json 2>/dev/null)" ] || continue
    wt=$(wt_of_branch "$b" | head -n 1)
    if [ -z "$wt" ]; then   # la branche n'a pas de worktree : la commande en crée un d'abord
      wt="$LAB_WORKTREES_FOLDER/wt-${b//\//-}"
      cmd="${cmd}git -C $(printf '%q' "$WS") worktree add $(printf '%q' "$wt") $(printf '%q' "$b") && "
    fi
    noms="${noms}${noms:+, }$b"
    cmd="${cmd}cd $(printf '%q' "$wt/mothra") && npm ci --ignore-scripts && "
  done
  if [ -n "$noms" ]; then
    raw "branche(s) du train qui modifient mothra/package-lock.json : $noms ; remplir le cache npm avec leur propre verrou :"
  else
    cmd="cd $(printf '%q' "$WS/mothra") && npm ci --ignore-scripts && "
    raw "remplir le cache npm avec le verrou de l'espace de travail :"
  fi
  raw "${cmd}cd $(printf '%q' "$WS") && $LIGNE $(quoted_names)"
}
npm_install() { # paquets de Mothra dans le worktree d'intégration (D10, décision A du 2026-10-27) : refus 76, 80 ou 81 ; rien si l'arbre n'a pas de verrou npm
  local entry mode want found out out_err rc
  # le verrou : absent de l'arbre (rien à faire) ou erreur Git (refus), jamais confondus ; présent, il doit être un fichier ordinaire (mode 100644 ou 100755)
  entry=$(git -C "$WS" ls-tree "$TRAIN_TREE" -- mothra/package-lock.json 2>/dev/null); rc=$?
  STEP="paquets npm"
  [ "$rc" -eq 0 ] || refus 76 "calcul impossible (lecture de mothra/package-lock.json dans l'arbre du train en échec : erreur Git) ; rien n'est fusionné"
  [ -n "$entry" ] || return 0
  mode=${entry%% *}
  case "$mode" in
    100644|100755) ;;
    *) refus 76 "calcul impossible (mothra/package-lock.json de l'arbre du train n'est pas un fichier ordinaire : mode $mode) ; rien n'est fusionné" ;;
  esac
  [ -f "$INTEG/mothra/package.json" ] || refus 76 "calcul impossible (mothra/package.json absent du worktree d'intégration, alors que mothra/package-lock.json est dans l'arbre) ; rien n'est fusionné"
  # node avant npm, même sans mothra/.node-version (D10) : node trouvé, sa version lisible, puis npm trouvé
  command -v node >/dev/null 2>&1 || refus 76 "calcul impossible (outil introuvable : node) ; rien n'est fusionné"
  found=$(node --version </dev/null 2>/dev/null 3>&- 4>&- | tr -d ' \t\r\n'); found=${found#v}
  [ -n "$found" ] || refus 76 "calcul impossible (version de node illisible) ; rien n'est fusionné"
  command -v npm >/dev/null 2>&1 || refus 76 "calcul impossible (outil introuvable : npm) ; rien n'est fusionné"
  # mothra/.node-version est contrôlé comme le verrou : absent (pas de contrôle de version), erreur Git (refus), ou fichier ordinaire (sinon refus)
  entry=$(git -C "$WS" ls-tree "$TRAIN_TREE" -- mothra/.node-version 2>/dev/null); rc=$?
  [ "$rc" -eq 0 ] || refus 76 "calcul impossible (lecture de mothra/.node-version dans l'arbre du train en échec : erreur Git) ; rien n'est fusionné"
  if [ -n "$entry" ]; then
    mode=${entry%% *}
    case "$mode" in
      100644|100755) ;;
      *) refus 76 "calcul impossible (mothra/.node-version de l'arbre du train n'est pas un fichier ordinaire : mode $mode) ; rien n'est fusionné" ;;
    esac
    want=$(git -C "$WS" show "$TRAIN_TREE:mothra/.node-version" 2>/dev/null); rc=$?
    [ "$rc" -eq 0 ] || refus 76 "calcul impossible (lecture de mothra/.node-version en échec) ; rien n'est fusionné"
    want=$(printf '%s' "$want" | tr -d ' \t\r\n'); want=${want#v}
    [ -n "$want" ] || refus 76 "calcul impossible (mothra/.node-version vide) ; rien n'est fusionné"
    # la règle de Node unique est celle du module (finish-single-b3-b6, D16) : égalité ou préfixe suivi d'un point ; sortie 0 correspond, 1 diffère, autre : fail-closed
    python3 -I "$SCRIPT_DIR/finish_checks.py" node-match "$found" "$want" </dev/null >/dev/null 2>&1; rc=$?
    if [ "$rc" -ne 0 ] && [ "$rc" -ne 1 ]; then refus 76 "calcul impossible (comparaison des versions de node en échec, code $rc) ; rien n'est fusionné"; fi
    if [ "$rc" -eq 1 ]; then
      say "version de Node trouvée $found, attendue $want (mothra/.node-version de l'arbre du train) ; rien n'est fusionné"
      raw "passer à la version attendue avec le gestionnaire de versions, puis relancer la même ligne :"
      raw "fnm use --install-if-missing $(printf '%q' "$want") && $LIGNE $(quoted_names)"
      exit 80
    fi
  fi
  out=$( cd "$INTEG/mothra" && npm ci --offline --ignore-scripts --no-audit --no-fund --no-update-notifier </dev/null 2>&1 3>&- 4>&- ); rc=$?
  if [ "$rc" -ne 0 ]; then
    # le journal ne garde que les lignes d'erreur de npm (D16), sans la ligne du fichier de journal de npm, et sans le dossier personnel
    out_err=$(grep -E '^npm (error|ERR!)' <<< "$out" | grep -v 'A complete log of this run can be found in')
    out_err=${out_err//"$HOME"/\~}
    if [ -n "$out_err" ]; then raw "$out_err"
    else   # aucune ligne npm error : les 5 dernières lignes de la sortie (dossier personnel en ~), ou le constat qu'il n'y en a aucune
      out_err=$(tail -n 5 <<< "$out"); out_err=${out_err//"$HOME"/\~}
      if [ -n "$out_err" ]; then raw "aucune ligne npm error ; les 5 dernières lignes de la sortie de npm :"; raw "$out_err"; else raw "aucune ligne npm error"; fi
    fi
    if grep -q ENOTCACHED <<< "$out"; then
      say "paquets de Mothra absents du cache npm (npm ci --offline, code $rc) ; rien n'est fusionné"
      npm_advice
      exit 81
    fi
    say "npm ci hors ligne en échec (code $rc) ; rien n'est fusionné"
    raw "voir les lignes npm error ci-dessus, puis relancer la même ligne : $LIGNE $(quoted_names)"
    exit 81
  fi
  say "paquets de Mothra installés dans le worktree d'intégration (npm ci --offline --ignore-scripts)"
}
# Verdict de la porte du conteneur (change ci-local-runner, D9 ; Q215) : code de ci_local et sa sortie ; rend 0 quand la porte est verte, sinon sort par refus.
#   - phase base rouge : 69 ; phase e2e rouge : 82 ; phase portable rouge avec des suites nommées : l'indice, UN rejeu des suites dans le conteneur
#     (ci_local run --rejeu portable <suites>, ou FINISH_TRAIN_CI suivi de ces mêmes arguments), puis 71 (non reproduites) ou 70 comme avant ;
#   - tout autre cas (codes 3 et 5 de ci_local, code 1 sans ligne de phase rouge, tout autre code, dont 7 qui ne peut pas arriver) : 71 « conteneur indisponible ».
# Appelée depuis integration_checks : INTEG et unsets sont ses variables locales (portée dynamique de bash).
# Remplace : le rejeu du runner complet pour une suite rouge du conteneur. Retrait : permanent tant que la porte du conteneur existe.
# Garde des noms de suites avant tout rejeu, conteneur ou passe Mac (Q230, Q236 a ; D9, R-20261101-116, R-20261101-120) : [A-Za-z0-9_]+ par nom (noms séparés par
# des espaces), plages en LC_ALL=C comme ci_local.sh, jamais selon la langue. Un nom hors du jeu : 71 avant l'indice et avant tout rejeu.
# Remplace : la garde du seul rejeu du conteneur. Retrait : permanent tant que le train rejoue des suites par leur nom.
suite_names_guard() {
  ( LC_ALL=C; case "$1" in *[!A-Za-z0-9_\ ]*) false ;; *) true ;; esac ) \
    || refus 71 "runner non concluant : nom de suite refusé pour le rejeu ; rien n'est fusionné"
}
ci_gate_verdict() {
  local rc=$1 out=$2 phase suites rc2 out2 total2
  case "$rc" in
    0)
      # Q226 (a), R-20261101-116 : un vert exige les trois lignes de phase verte et aucune rouge ; sinon 71 (jamais un vert sur le seul code)
      if grep -aq '^ci_passage : phase [a-z0-9]* : rouge' <<< "$out" \
         || ! grep -aq '^ci_passage : phase portable : verte' <<< "$out" \
         || ! grep -aq '^ci_passage : phase base : verte' <<< "$out" \
         || ! grep -aq '^ci_passage : phase e2e : verte' <<< "$out"; then
        refus 71 "runner non concluant : conteneur non concluant ; rien n'est fusionné"
      fi
      return 0 ;;
    1) ;;
    *) refus 71 "runner non concluant : conteneur indisponible (code $rc) ; rien n'est fusionné" ;;
  esac
  # classement par présence de la ligne ancrée au début de ligne (jamais par ordre d'apparition ni par une chaîne au milieu d'une sortie de suite)
  phase=""
  for v in base e2e portable; do
    if grep -aqE "^ci_passage : phase $v : rouge" <<< "$out"; then phase=$v; break; fi
  done
  case "$phase" in
    base) refus 69 "phase base du conteneur rouge sur l'arbre du train ; rien n'est fusionné" ;;
    e2e) refus 82 "phase de bout en bout du conteneur rouge sur l'arbre du train ; rien n'est fusionné" ;;
    portable) ;;
    *) refus 71 "runner non concluant : conteneur indisponible (code $rc) ; rien n'est fusionné" ;;
  esac
  suites=$(sed -n 's/^ci_passage : phase portable : rouge · [0-9]* s : \(.*\)$/\1/p' <<< "$out" | sed -n 1p)
  case "$suites" in
    ''|code\ *|aucune\ *) refus 71 "runner non concluant : phase portable du conteneur rouge sans suite nommée (${suites:-aucune}) ; rien n'est fusionné" ;;
  esac
  suite_names_guard "$suites"
  red_hint "$suites"
  # les noms passent en arguments du shell ($@), jamais par interpolation dans la commande (revue 2026-10-31, point 9)
  if [ -n "${FINISH_TRAIN_CI:-}" ]; then
    out2=$( cd "$INTEG" && env "${unsets[@]}" sh -c "$FINISH_TRAIN_CI \"\$@\"" sh --rejeu portable $suites </dev/null 2>&1 3>&- 4>&- ); rc2=$?
  else
    out2=$( cd "$INTEG" && env "${unsets[@]}" bash "$SCRIPT_DIR/ci_local.sh" run --rejeu portable $suites </dev/null 2>&1 3>&- 4>&- ); rc2=$?
  fi
  total2=$(grep -a '^TOTAL' <<< "$out2" | tail -1)
  [ -z "$total2" ] || raw "$total2"
  [ "$rc2" -ne 0 ] || refus 71 "runner non concluant : suites rouges non reproduites ($suites) ; rien n'est fusionné"
  # « suite rouge reproduite » (70) seulement pour le code 1 ET la ligne « ci_local : rejeu rouge … » ; tout autre code (2, 3, 4, 5, 7, ou 1 sans cette ligne) : 71
  if [ "$rc2" -ne 1 ] || ! grep -aq '^ci_local : rejeu rouge' <<< "$out2"; then
    refus 71 "runner non concluant : rejeu du conteneur non concluant (code $rc2) ; rien n'est fusionné"
  fi
  say "train rouge : suites en échec : $suites ; rien n'est fusionné"
  say "retirer de la liste la branche qui casse ces suites, puis relancer la ligne"
  if [ "$HINT_NAMED" -eq 0 ] && [ "$HINT_FAILED" -eq 0 ]; then
    say "défaut de sélection : suites rouges hors de toute sélection de select_suites ($suites) ; corriger le sélecteur avant le train suivant"
  fi
  exit 70
}
integration_checks() {
  local name cmd out rc v total suites reason prc lancer l
  local -a unsets
  STEP="worktree d'intégration"
  name=${INTEG_NAME:-wt-train-$(date +%Y%m%d-%H%M%S)}   # le nom écrit dans le verrou par record_freeze (gel ciblé, D18)
  mkdir -p "$LAB_WORKTREES_FOLDER" 2>/dev/null
  INTEG="$LAB_WORKTREES_FOLDER/$name"
  if ! git -C "$WS" worktree add -q --detach "$INTEG" "$TRAIN_TIP" >/dev/null 2>&1; then INTEG=""; refus 76 "calcul impossible (worktree d'intégration non créé)"; fi
  npm_install
  # Porte du train (change ci-local-runner, D9) : le repère, l'instantané du worktree et le premier listage des processus précèdent la porte du conteneur
  # et couvrent aussi la passe Mac ; la stabilité (stability_reason) se lit une fois, après la passe Mac.
  # Remplace : dbtest (contrôle 14), la passe de bout en bout (contrôle 16) et le runner complet du Mac. Retrait : permanent tant que les trains tournent.
  STEP="porte du conteneur"
  MARK=$(mktemp "${TMPDIR:-/tmp}/train-repere.XXXXXX") || refus 76 "calcul impossible (repère du runner non créé)"
  sleep 1
  fs_snapshot "$INTEG"; DIR_SNAP=$FS_SNAP
  # premier listage des processus (D10), après le repère et sa marge : une vérification impossible, ou un processus déjà dans le worktree, ne
  # laisse aucun passage conclure (décision du 2026-10-27, D14 et D18)
  fs_processes "$INTEG"; prc=$?
  if [ "$prc" -eq 2 ]; then refus 71 "runner non concluant : processus dans le worktree (vérification impossible) ; rien n'est fusionné"; fi
  if [ "$prc" -eq 1 ]; then refus 71 "runner non concluant : processus dans le worktree d'intégration (${FS_PROCESSES%%, *}) ; rien n'est fusionné"; fi
  unsets=()
  for v in $(compgen -v FINISH_TRAIN_); do unsets+=(-u "$v"); done
  # aucune variable de la vraie base ne part vers la porte du conteneur ni vers la passe Mac (R-20261101-116) ; DBTEST_* est déjà retirée au début de main
  for v in $(compgen -e PMZILLA_LAB_DB_); do unsets+=(-u "$v"); done
  # aucune variable CI_LOCAL_* de l'appelant (faux docker, autre fichier de preuves ou de verdicts) ne part vers la porte, son rejeu ni la passe Mac
  for v in $(compgen -v CI_LOCAL_); do unsets+=(-u "$v"); done
  for v in PMZILLA_NO_EVALS PMZILLA_SKIP_GREEN_CHECK FINISH_BRANCH_TESTED_TOKEN FINISH_BRANCH_FORCE_RUN FINISH_WORKTREE_ALLOW_SKIP FINISH_WORKTREE_CI FINISH_WORKTREE_CI_VERDICTS; do
    unsets+=(-u "$v")
  done
  say "lancement de la porte du conteneur dans le worktree d'intégration"
  # FINISH_TRAIN_CI remplace la commande `bash <outils>/ci_local.sh run` (et son rejeu), jamais un refus ; la commande par défaut est celle de l'arbre
  # d'exécution (le code de main), lancée depuis le worktree d'intégration (HEAD propre = le commit du train), avec le jeton du verrou de fin
  if [ -n "${FINISH_TRAIN_CI:-}" ]; then
    out=$( cd "$INTEG" && env "${unsets[@]}" sh -c "$FINISH_TRAIN_CI" </dev/null 2>&1 3>&- 4>&- ); rc=$?
  else
    out=$( cd "$INTEG" && env "${unsets[@]}" bash "$SCRIPT_DIR/ci_local.sh" run </dev/null 2>&1 3>&- 4>&- ); rc=$?
  fi
  while IFS= read -r l; do [ -z "$l" ] || raw "$l"; done < <(grep -aE '^(ci_passage|ci_local) : ' <<< "$out")
  ci_gate_verdict "$rc" "$out"
  say "porte du conteneur verte sur l'arbre du train"
  STEP="passe Mac"
  say "lancement du runner complet dans le worktree d'intégration"
  cmd=${FINISH_TRAIN_RUNNER:-bash tests/run_all.sh --mac}
  out=$( cd "$INTEG" && env "${unsets[@]}" sh -c "$cmd" </dev/null 2>&1 3>&- 4>&- ); rc=$?
  total=$(grep '^TOTAL' <<< "$out" | tail -1)
  [ -z "$total" ] || raw "$total"
  case "$rc" in
    0)
      reason=$(stability_reason)
      [ -z "$reason" ] || refus 71 "runner non concluant (code $rc) : $reason ; rien n'est fusionné" ;;
    1)
      suites=$(sed -n 's/.*suite(s) en échec : \(.*\) · durée totale.*/\1/p' <<< "$total")
      if [ -n "$suites" ]; then
        suite_names_guard "$suites"   # même garde que le rejeu du conteneur (Q236 a, R-20261101-120) : avant l'indice et avant tout rejeu
        red_hint "$suites"
        # rejeu unique des suites rouges sur le sommet du train (targeted-suites-admission, D5) : même commande, même environnement que le runner,
        # filtrée par les noms (aucune empreinte écrite), jamais dbtest ; vert au rejeu : suites non reproduites (71), tout autre code : le 70 d'avant
        # les noms passent en arguments du shell ($@), jamais par interpolation dans la commande (revue 2026-10-31, point 9)
        # la passe Mac se rejoue sans --mac (le lanceur refuse --mac avec des noms) ; FINISH_TRAIN_RUNNER, posée, reste la commande du rejeu
        out2=$( cd "$INTEG" && env "${unsets[@]}" sh -c "${FINISH_TRAIN_RUNNER:-bash tests/run_all.sh} \"\$@\"" sh $suites </dev/null 2>&1 3>&- 4>&- ); rc2=$?
        total2=$(grep '^TOTAL' <<< "$out2" | tail -1)   # la ligne TOTAL du rejeu entre au journal (revue 2026-10-31, point 10)
        [ -z "$total2" ] || raw "$total2"
        [ "$rc2" -ne 0 ] || refus 71 "runner non concluant : suites rouges non reproduites ($suites) ; rien n'est fusionné"
        say "train rouge : suites en échec : $suites ; rien n'est fusionné"
        say "retirer de la liste la branche qui casse ces suites, puis relancer la ligne"
        # aucune branche n'a sélectionné la suite rouge (et aucun sélecteur n'a échoué) : défaut du sélecteur, signalé sans changer le 70 (R-20261031-41, cas 3)
        if [ "$HINT_NAMED" -eq 0 ] && [ "$HINT_FAILED" -eq 0 ]; then
          say "défaut de sélection : suites rouges hors de toute sélection de select_suites ($suites) ; corriger le sélecteur avant le train suivant"
        fi
        exit 70
      fi
      refus 71 "runner non concluant (code $rc) : ligne TOTAL absente ; rien n'est fusionné" ;;
    4) refus 71 "runner non concluant (code $rc) : fin de branche en cours (gel) ; rien n'est fusionné" ;;
    7) # le runner a arrêté le lancement complet avant sa première suite : dépendances npm à mettre en conformité, pas des tests en échec ;
       # sa ligne « lancer : » donne la commande
       lancer=$(grep -E '^[[:space:]]*lancer :' <<< "$out")
       [ -z "$lancer" ] || raw "$lancer"
       refus 71 "runner non concluant (code $rc) : dépendances npm à mettre en conformité (ligne « lancer : » ci-dessus) ; rien n'est fusionné" ;;
    6) refus 71 "runner non concluant (code $rc) : lancement refusé par le lanceur ; rien n'est fusionné" ;;
    *) refus 71 "runner non concluant (code $rc) : ligne TOTAL absente ; rien n'est fusionné" ;;
  esac
  say "runner complet vert sur l'arbre du train"
}

# Indice d'un train rouge (targeted-suites-admission, D5) : pour chaque branche, la plage origin/main...<sommet> passée au sélecteur (--range) dit si sa
# sélection tient une suite rouge. L'indice ne désigne rien et ne change aucun code : une suite sélectionnée par une branche était verte sur son sommet, le
# train rouge vient d'une interaction, d'un manque du sélecteur ou d'une suite instable. Sélecteur en code 3 (exécution complète exigée) : cette branche a
# été éprouvée par le runner complet, donc elle tient toute suite rouge ; tout autre code : « indice impossible pour <branche> », rien d'autre ne change.
# Pose HINT_NAMED (nombre de branches nommées) et HINT_FAILED (nombre de sélecteurs en échec). Remplace : la ligne de 70 sans indice. Retrait : permanent
# tant que le train lance le runner complet sur l'arbre intégré.
HINT_NAMED=0; HINT_FAILED=0
red_hint() { # suites rouges (séparées par des blancs)
  local reds=$1 k n=${#NAMES[@]} sel rcs held r names="" list=""
  HINT_NAMED=0; HINT_FAILED=0
  for ((k = 0; k < n; k++)); do
    sel=$(python3 -I "$SCRIPT_DIR/select_suites.py" --range "origin/main...${TIPS[$k]}" --root "$INTEG" </dev/null 2>/dev/null 3>&- 4>&-); rcs=$?
    held=0
    if [ "$rcs" -eq 3 ]; then
      held=1
    elif [ "$rcs" -eq 0 ]; then
      names=$(sed -n 's/^select_suites : \([^ ]*\) : .*/\1/p' <<< "$sel")
      for r in $reds; do
        case " $(tr '\n' ' ' <<< "$names") " in *" $r "*) held=1 ;; esac
      done
    else
      say "indice impossible pour ${NAMES[$k]}"
      HINT_FAILED=$((HINT_FAILED + 1))
      continue
    fi
    if [ "$held" -eq 1 ]; then
      list="${list}${list:+, }${NAMES[$k]}"
      HINT_NAMED=$((HINT_NAMED + 1))
    fi
  done
  if [ "$HINT_NAMED" -gt 0 ]; then say "train rouge : suites rouges sélectionnées par : $list"
  else say "train rouge : suites rouges sélectionnées par aucune branche"
  fi
}

# --- 9. résumé, essai, question (D12) ---------------------------------------------------------------------------------------------------
print_summary() {
  local k n=${#NAMES[@]} tip mb c f
  for ((k = 0; k < n; k++)); do
    tip=${TIPS[$k]}
    mb=$(git -C "$WS" merge-base refs/remotes/origin/main "$tip" 2>/dev/null)
    c=$(git -C "$WS" rev-list --count "$mb..$tip" 2>/dev/null)
    f=$(git -C "$WS" diff --name-only "$mb" "$tip" 2>/dev/null | grep -c .)
    raw "  $((k + 1)). ${NAMES[$k]} : sommet $(sha12 "$tip"), $c commit(s), $f fichier(s)"
  done
  git -C "$WS" diff --stat refs/remotes/origin/main "$TRAIN_TIP" 2>/dev/null
  say "fichiers non examinés par le contrôle des noms : $NOT_EXAMINED"
}
trial_end() {
  say "essai rapide : contrôles passés, sans dbtest ni runner ; rien n'est écrit dans les références"
  ESSAI_FIN=1
  exit 0
}
question() {
  local rep=""
  STEP="question"
  printf 'Terminer le train (%s branche(s)) ? (o/n) ' "${#NAMES[@]}"
  read -r rep
  echo
  if [ "$rep" != o ]; then
    say "réponse autre que « o » : rien n'est fusionné ; relancer la même ligne pour terminer le train"
    ESSAI_FIN=1
    exit 0
  fi
}

auto_refuse_resumption() { # état (S1 ou S2) : D8 ; avec --auto, une reprise est toujours le train de l'auteur : rien n'est poussé
  [ "$AUTO" = 1 ] || return 0
  STEP="politique automatique"
  refus 84 "politique automatique refuse : état de reprise ($1) ; train de l'auteur"
}
auto_gate() { # D8 : la politique remplace la question o/n ; autorisée, l'arrivée suit exactement comme après « o » ; sinon 84 et rien n'est fusionné
  local out rc k lines codes l
  local -a args
  STEP="politique automatique"
  say "mode automatique : la politique remplace la question"
  args=(--train-tip "$TRAIN_TIP")
  for ((k = 0; k < ${#NAMES[@]}; k++)); do args+=(--branch "${NAMES[$k]}" --tip "${TIPS[$k]}"); done
  out=$(python3 -I "$SCRIPT_DIR/finish_checks.py" policy --repo "$WS" "${args[@]}" --json </dev/null 2>/dev/null); rc=$?
  if [ "$rc" -eq 0 ] && grep -qxF '{"format": 1, "allowed": true, "reasons": []}' <<< "$out"; then
    say "politique automatique : départ autorisé (${#NAMES[@]} branche(s))"
    return 0
  fi
  lines=""; codes=""
  if [ "$rc" -eq 1 ]; then
    lines=$(python3 -I "$SCRIPT_DIR/finish_checks.py" policy-lines <<< "$out" 2>/dev/null) || lines=""
    codes=$(grep -oE '"code": "[a-z-]+"' <<< "$out" | sed -e 's/^"code": "//' -e 's/"$//' | awk '!vu[$0]++' | tr '\n' ',' | sed 's/,$//')
  fi
  if [ -n "$lines" ] && [ -n "$codes" ]; then
    POLICY_CODES=$codes
    while IFS= read -r l; do say "politique automatique refuse : $l ; rien n'est fusionné"; done <<< "$lines"
  else
    # sortie 4 (calcul impossible) ou sortie illisible : la raison unique est « contrôles de fin impossibles » (D7, D8)
    POLICY_CODES=calcul-impossible
    say "politique automatique refuse : contrôles de fin impossibles ; rien n'est fusionné"
  fi
  exit 84
}

# --- 10. arrivée dans main (D11, D13) ---------------------------------------------------------------------------------------------------
push_main() {
  STEP="push"
  # le commit nommé (le sommet du train, en reprise S1 le sommet noté de main), jamais « main » : ce qui part est exactement ce qui a été testé ou noté
  if ! env -u PMZILLA_SKIP_GREEN_CHECK git -C "$WS" push origin "$TRAIN_TIP:refs/heads/main" </dev/null 3>&- 4>&-; then
    refus 74 "push refusé : le train est fusionné dans main local seulement ; relancer la même ligne pour pousser"
  fi
  PUSH_DONE=1
  say "main poussé vers origin"
}
arrival() {
  local k n=${#NAMES[@]} now fp lm
  STEP="relecture des références"
  git -C "$WS" fetch -q origin main </dev/null >/dev/null 2>&1 3>&- 4>&- || refus 73 "relecture des références impossible : fetch d'origin/main en échec ; rien n'est fusionné"
  for ((k = 0; k < n; k++)); do
    now=$(git -C "$WS" rev-parse -q --verify "refs/heads/${NAMES[$k]}^{commit}" 2>/dev/null)
    if [ "$now" != "${TIPS[$k]}" ]; then
      refus 73 "${NAMES[$k]} a bougé depuis le début de la fin ($(sha12 "${TIPS[$k]}") → $(sha12 "$now")) ; rien n'est fusionné"
    fi
  done
  if [ "$(git -C "$WS" rev-parse -q --verify refs/heads/main 2>/dev/null)" != "$MAIN_START" ] || [ "$(git -C "$WS" rev-parse -q --verify refs/remotes/origin/main 2>/dev/null)" != "$BASE" ]; then
    refus 73 "main ou origin/main a bougé depuis le début de la fin ; rien n'est fusionné"
  fi
  STEP="garde du matin"
  morning_guard
  STEP="avance rapide"
  fp=$(git -C "$WS" rev-parse --path-format=absolute --git-path pmzilla-run-all-ok 2>/dev/null)
  if [ -n "${FINISH_TRAIN_RUNNER:-}" ] || [ -n "${FINISH_TRAIN_CI:-}" ]; then   # une variable de substitution ne fabrique jamais une preuve (Q233 a, R-20261101-118)
    say "empreinte de l'espace de travail non écrite (commande de test posée)"
  elif [ -n "$fp" ] && ( umask 077; printf '%s\n' "$TRAIN_TREE" > "$fp.tmp.$$" ) 2>/dev/null && mv -f "$fp.tmp.$$" "$fp" 2>/dev/null; then
    say "empreinte de l'espace de travail écrite pour l'arbre testé"
  else
    [ -z "$fp" ] || rm -f "$fp.tmp.$$" 2>/dev/null
    say "empreinte de l'espace de travail non écrite (écriture impossible) ; le crochet de push relancera le runner"
  fi
  git -C "$WS" merge --ff-only -q "$TRAIN_TIP" </dev/null >/dev/null 2>&1
  lm=$(git -C "$WS" rev-parse -q --verify refs/heads/main 2>/dev/null)
  [ "$lm" != "$TRAIN_TIP" ] || FF_DONE=1
  if [ "$lm" = "$MAIN_START" ] && [ "$lm" != "$TRAIN_TIP" ]; then
    # l'avance rapide a échoué et main n'a pas bougé : rien n'est fusionné (E2) ; la propreté de l'espace de travail est revérifiée
    ws_clean "$WS" || say "l'espace de travail n'est pas propre : à examiner avant de relancer"
    ws_bmad_report "$TRAIN_TIP"
    refus 73 "avance rapide de main en échec, main inchangé ($(sha12 "$MAIN_START")) ; rien n'est fusionné"
  fi
  if [ "$lm" != "$TRAIN_TIP" ] || [ "$(git -C "$WS" rev-parse "refs/heads/main^{tree}" 2>/dev/null)" != "$TRAIN_TREE" ]; then
    refus 73 "arbre de main différent de l'arbre testé après l'avance rapide ; rien n'est poussé ; main était $(sha12 "$MAIN_START")"
  fi
  say "main avancé sur le train : $(sha12 "$MAIN_START") -> $(sha12 "$TRAIN_TIP")"
  push_main
  if [ -n "${FINISH_TRAIN_RUNNER:-}" ] || [ -n "${FINISH_TRAIN_CI:-}" ]; then   # une commande de test posée (porte du conteneur ou passe Mac) : même règle
    say "arbre de main non enregistré (runner remplacé)"
  elif ( cd "$WS" && record_main_validated "$TRAIN_TREE" complet ); then
    say "arbre de main enregistré comme validé (complet)"
  else
    say "arbre de main non enregistré (écriture impossible)"
    add_cause "arbre de main non enregistré (écriture impossible)"
  fi
}

# --- 11. nettoyage, vérification finale, mise à jour du dossier d'exécution (D14, D15) -------------------------------------------------
cleanup_all() {
  local nm p rsha
  STEP="nettoyage"
  for nm in "${NAMES[@]}"; do
    p=$(wt_of_branch "$nm")
    [ -n "$p" ] || continue
    if try_remove_wt "$p"; then say "worktree retiré : $p"
    else say "worktree gardé : $p : $KEEP_REASON"; add_cause "worktree gardé : $p : $KEEP_REASON"; fi
  done
  if [ -n "$INTEG" ]; then
    p=$INTEG
    if try_remove_wt "$p"; then say "worktree retiré : $p"; INTEG=""
    else say "worktree gardé : $p : $KEEP_REASON"; add_cause "worktree gardé : $p : $KEEP_REASON"; fi
  fi
  for nm in "${NAMES[@]}"; do
    if git -C "$WS" rev-parse -q --verify "refs/heads/$nm" >/dev/null 2>&1; then
      p=$(wt_of_branch "$nm")
      if [ -n "$p" ]; then say "branche gardée : $nm : worktree gardé"; add_cause "branche gardée : $nm : worktree gardé"; continue; fi
      if git -C "$WS" branch -d "$nm" >/dev/null 2>&1; then say "branche supprimée : $nm"
      else say "branche gardée : $nm : suppression sûre refusée"; add_cause "branche gardée : $nm : suppression sûre refusée"; continue; fi
    fi
    rsha=$(git -C "$WS" ls-remote --heads origin "refs/heads/$nm" 2>/dev/null </dev/null | awk 'NR==1{print $1}')
    if [ -n "$rsha" ]; then
      # la branche distante n'est supprimée que si son sommet est contenu dans main (revue de u5, m-11) : un commit poussé ailleurs depuis la
      # fin de la branche locale ne se perd jamais
      if ! git -C "$WS" cat-file -e "$rsha^{commit}" 2>/dev/null || ! git -C "$WS" merge-base --is-ancestor "$rsha" refs/heads/main 2>/dev/null; then
        say "branche gardée : $nm : branche distante pas contenue dans main"; add_cause "branche gardée : $nm : branche distante pas contenue dans main"
      elif env -u PMZILLA_SKIP_GREEN_CHECK git -C "$WS" push -q origin --delete "$nm" </dev/null >/dev/null 2>&1 3>&- 4>&-; then say "branche distante supprimée : $nm"
      else say "branche gardée : $nm : branche distante non supprimée"; add_cause "branche gardée : $nm : branche distante non supprimée"; fi
    fi
  done
}
final_check() {
  STEP="vérification finale"
  [ "$(git -C "$WS" symbolic-ref -q --short HEAD 2>/dev/null)" = main ] || add_cause "vérification finale : l'espace de travail n'est plus sur main"
  ws_clean "$WS" || add_cause "vérification finale : l'espace de travail n'est pas propre"
  if git -C "$WS" rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1; then add_cause "vérification finale : une fusion est en cours"; fi
  if [ "$(git -C "$WS" rev-parse -q --verify refs/heads/main 2>/dev/null)" != "$(git -C "$WS" rev-parse -q --verify refs/remotes/origin/main 2>/dev/null)" ]; then
    add_cause "vérification finale : main local diffère d'origin/main"
  fi
  # main doit être le sommet du train (D15) : en reprise S1 ou S2, le sommet noté
  if [ "$(git -C "$WS" rev-parse -q --verify refs/heads/main 2>/dev/null)" != "$TRAIN_TIP" ]; then
    add_cause "vérification finale : main local n'est pas le sommet du train"
  fi
  if [ "$(git -C "$WS" rev-parse -q --verify refs/remotes/origin/main 2>/dev/null)" != "$TRAIN_TIP" ]; then
    add_cause "vérification finale : origin/main n'est pas le sommet du train"
  fi
}
update_run_tree() {
  local out rc
  STEP="mise à jour du dossier d'exécution"
  out=$(bash "$LAB_RUN_TREE/tools/run_worktree.sh" update </dev/null 2>&1 3>&- 4>&-); rc=$?
  if [ "$rc" -eq 0 ]; then say "dossier d'exécution mis à jour"
  elif [ "$rc" -eq 4 ] && grep -q "absent" <<< "$out"; then say "dossier d'exécution absent, rien à mettre à jour"
  else
    say "dossier d'exécution non mis à jour"
    [ -z "$out" ] || raw "$out"
    say "Pour le mettre à jour : bash tools/run_worktree.sh update"
    add_cause "dossier d'exécution non mis à jour (code $rc)"
  fi
}
# Outils figés du bac à sable de Bash (niveau 2, design D5, tâche 7.4 ; réserve C-r4) : quand le train change un fichier de la liste fermée de
# tools/outils_figes/liste.txt (une enveloppe `E`, une dépendance `C`, ou la liste elle-même) et que le dossier outils-figes du dossier de données existe (le
# bac à sable est en répétition ou posé), les fichiers figés sont copiés depuis le COMMIT du sommet du train (git show <sommet>:<chemin>, jamais depuis l'arbre de
# l'espace de travail) vers un dossier de préparation voisin ; le script de copie du même commit (rafraichir.sh) y recopie les fichiers et réécrit le relevé, sur une
# copie du dossier ; l'échange avec le dossier réel ne vient qu'ensuite (deux renommages, sans aucune commande Git). La liste des changements est calculée AVANT la mise
# à jour du dossier d'exécution (frozen_prepare), l'échange APRÈS (frozen_swap). Le dossier absent, ou aucun fichier figé changé : rien n'est dit ni fait.
# Une préparation ou un échange qui échoue est une cause du code 75 (fin incomplète) : le dossier réel reste alors tel qu'il était, entier (copies et relevé d'avant,
# que leurs enveloppes lisent comme avant) ; le geste de reprise est le fichier d'étape de copie de l'auteur, qui recopie à la main.
# Remplace : la copie faite à la main, au fichier d'étape de l'auteur (répétition), et la version de cette étape qui recopiait depuis l'arbre de l'espace de travail
# fichier par fichier. Retrait : avec le bac à sable.
frozen_extract() { # commit, chemin du dépôt, dossier de préparation : le fichier du commit, sous <préparation>/depot/<chemin>
  mkdir -p "$(dirname "$3/depot/$2")" && git -C "$WS" show "$1:$2" > "$3/depot/$2" 2>/dev/null
}
frozen_fail() { # code ou texte, sortie de la copie : une préparation en échec (le dossier de préparation est retiré)
  say "outils figés non rafraîchis ($1)"
  [ -z "${2:-}" ] || raw "$2"
  say "Pour les rafraîchir : le fichier d'étape de copie des outils figés"
  add_cause "outils figés non rafraîchis ($1) ; geste de reprise : le fichier d'étape de copie"
  [ -z "${FROZEN_PREP:-}" ] || rm -rf "$FROZEN_PREP"
  FROZEN_PREP=""
  # R-20261110-04 : le rafraîchissement a échoué après le « o » : les copies sont bien en retard, la note est écrite (le code de sortie de l'échec ne change pas).
  [ -z "${FROZEN_DEST:-}" ] || frozen_late "$FROZEN_DEST" "$FROZEN_TIP"
}
# R-20261110-03 : ces copies tournent hors du bac à sable, certaines avec l'accès à la vraie base ; aucune modification n'y entre sans l'accord de l'auteur.
# Question o/n de l'auteur juste avant la préparation ; en --auto, jamais de rafraîchissement. Dans les deux cas où il n'a pas lieu, le retard est noté dans le
# fichier outils-figes-en-retard du dossier de données (le sommet du train, un espace, la commande exacte à lancer par l'auteur), que le rapport des fusions
# automatiques lit (tools/train_auto.py) ; un rafraîchissement réussi le retire. Remplace : rien. Retrait : avec le bac à sable (R-20261110-03).
# R-20261110-05 : pendant cette question seulement, SIGINT (Ctrl-C) et SIGHUP (terminal fermé) valent « n » : pas de rafraîchissement, la note du retard est écrite
# (frozen_late, par frozen_prepare), puis le train poursuit sa fin normale (dossier d'exécution, verrou rendu) et garde son code de sortie. Les deux pièges ne font
# que poser un drapeau (aucun exit) ; la lecture avance par pas d'une seconde (`read -t 1`, entier : bash 3.2) pour que le drapeau soit vu sans attendre une réponse : sous
# bash 3.2 un `read` bloquant n'est pas interrompu par un signal piégé (mesuré), et un délai de `read -t` rend le code 1, comme la fin d'entrée (le code 142 date de bash 4.0).
# Le délai (SECONDS a avancé pendant la lecture : on relit, sans limite) se distingue donc de la fin d'entrée (rendue sans attendre : vaut « n »).
# Les pièges généraux (les lignes trap INT et trap HUP plus haut, source de ces deux textes) sont remis ensuite.
# Remplace : rien. Retrait : avec le bac à sable (R-20261110-05).
frozen_traps_generaux() {
  trap 'SIGCODE=INT; exit 130' INT
  trap 'SIGCODE=HUP; exit 129' HUP
}
frozen_ask() {
  local rep="" rc=0 debut
  FROZEN_SIG=""
  trap 'FROZEN_SIG=INT' INT
  trap 'FROZEN_SIG=HUP' HUP
  printf 'Rafraîchir les copies figées du bac à sable ? (o/n) '
  while [ -z "$FROZEN_SIG" ]; do
    debut=$SECONDS
    read -r -t 1 rep; rc=$?
    [ "$rc" -ne 0 ] || break                  # une ligne lue
    [ -z "$FROZEN_SIG" ] || break             # signal : vaut « n »
    [ "$rc" -le 128 ] || continue             # délai (bash 4 et plus) : on relit
    [ "$SECONDS" -gt "$debut" ] || break      # bash 3.2 : le délai rend 1 aussi ; une fin d'entrée rend sans attendre
  done
  echo
  frozen_traps_generaux
  if [ -n "$FROZEN_SIG" ]; then
    say "question interrompue ($FROZEN_SIG) : vaut « n », copies figées non rafraîchies"
    return 1
  fi
  [ "$rep" = o ]
}
frozen_late() { # dossier des copies, sommet du train
  local cmd tmp marqueur="$LAB_DATA_FOLDER/outils-figes-en-retard"
  cmd="cd \"$WS\" && bash tools/outils_figes/rafraichir.sh \"$WS\" \"$1\""
  say "copies figées en retard sur main : non rafraîchies"
  say "Pour les rafraîchir : $cmd"
  # R-20261110-04 : écriture atomique (fichier temporaire du même dossier, puis mv -f) ; un lien posé à la place de la note est retiré avant (jamais suivi), un dossier refusé.
  tmp="$marqueur.$$"
  [ ! -L "$marqueur" ] || rm -f "$marqueur" 2>/dev/null
  rm -f "$tmp" 2>/dev/null
  if [ -d "$marqueur" ] || ! printf '%s %s\n' "$2" "$cmd" > "$tmp" 2>/dev/null || ! mv -f "$tmp" "$marqueur" 2>/dev/null; then
    rm -f "$tmp" 2>/dev/null
    say "retard des copies figées non noté (écriture impossible)"
  fi
}
frozen_prepare() { # ancien sommet, nouveau sommet
  local dest liste changed line chemin touched=0 out rc
  STEP="outils figés"
  FROZEN_PREP=""
  dest="$LAB_DATA_FOLDER/outils-figes"
  [ -d "$dest" ] || return 0
  liste=$(git -C "$WS" show "$2:tools/outils_figes/liste.txt" 2>/dev/null) || return 0
  if ! changed=$(git -C "$WS" diff --name-only "$1" "$2" 2>/dev/null); then
    say "outils figés : changements du train illisibles, copies non rafraîchies"
    add_cause "outils figés : changements du train illisibles"
    return 0
  fi
  grep -qxF "tools/outils_figes/liste.txt" <<< "$changed" && touched=1
  while IFS= read -r line; do
    case "$line" in
      "E "*) chemin="tools/outils_figes/${line#E }" ;;
      "C "*) chemin=${line#C } ;;
      *) continue ;;
    esac
    grep -qxF "$chemin" <<< "$changed" && touched=1
  done <<< "$liste"
  [ "$touched" = 1 ] || return 0
  # R-20261110-03 : le rafraîchissement exige le « o » de l'auteur ; en --auto, ou après « n », le train fusionne sans rafraîchir et note le retard.
  if [ "$AUTO" = 1 ]; then
    say "mode automatique : les copies figées ne sont pas rafraîchies"
    frozen_late "$dest" "$2"
    return 0
  fi
  frozen_ask || { frozen_late "$dest" "$2"; return 0; }
  FROZEN_DEST="$dest"; FROZEN_TIP="$2"
  FROZEN_PREP="$dest.preparation.$$"
  rm -rf "$FROZEN_PREP"
  mkdir -p "$FROZEN_PREP/depot" || { frozen_fail "préparation impossible"; return 0; }
  for chemin in tools/outils_figes/liste.txt tools/outils_figes/rafraichir.sh; do
    frozen_extract "$2" "$chemin" "$FROZEN_PREP" || { frozen_fail "fichier absent du commit du train"; return 0; }
  done
  while IFS= read -r line; do
    case "$line" in
      "E "*) chemin="tools/outils_figes/${line#E }" ;;
      "C "*) chemin=${line#C } ;;
      *) continue ;;
    esac
    case "$chemin" in ""|/*|*..*|*" "*) frozen_fail "ligne refusée dans la liste"; return 0 ;; esac
    frozen_extract "$2" "$chemin" "$FROZEN_PREP" || { frozen_fail "fichier absent du commit du train"; return 0; }
  done <<< "$liste"
  cp -R "$dest" "$FROZEN_PREP/nouveau" 2>/dev/null || { frozen_fail "copie du dossier impossible"; return 0; }
  out=$(bash "$FROZEN_PREP/depot/tools/outils_figes/rafraichir.sh" "$FROZEN_PREP/depot" "$FROZEN_PREP/nouveau" --extrait-du-train </dev/null 2>&1 3>&- 4>&-); rc=$?
  [ "$rc" -eq 0 ] || frozen_fail "code $rc" "$out"
  return 0
}
frozen_swap() {
  local dest old
  [ -n "${FROZEN_PREP:-}" ] || return 0
  STEP="outils figés"
  dest="$LAB_DATA_FOLDER/outils-figes"
  old="$dest.avant.$$"
  if mv "$dest" "$old" 2>/dev/null && mv "$FROZEN_PREP/nouveau" "$dest" 2>/dev/null; then
    rm -rf "$old" "$FROZEN_PREP"
    # R-20261110-03 : plus de retard à signaler ; un retrait en échec est dit (sans changer le code de sortie)
    rm -f "$LAB_DATA_FOLDER/outils-figes-en-retard" 2>/dev/null || say "note du retard des copies figées non retirée (retrait impossible)"
    FROZEN_PREP=""
    say "outils figés rafraîchis"
  else
    [ -d "$dest" ] || mv "$old" "$dest" 2>/dev/null
    frozen_fail "échange impossible"
  fi
}
remove_relay_notes() { # D21 : la note de relais de chaque branche fusionnée (nom encodé : % puis / remplacés) ; un retrait en échec est une cause de 75
  local nm note
  STEP="notes de relais"
  for nm in "${NAMES[@]}"; do
    note="$COMMON/pmzilla-notes/$(printf '%s' "$nm" | sed -e 's/%/%25/g' -e 's#/#%2F#g')"
    [ -e "$note" ] || [ -L "$note" ] || continue
    if rm "$note" 2>/dev/null; then say "note de relais retirée : $nm"
    else say "note de relais non retirée : $nm"; add_cause "note de relais non retirée : $nm"; fi
  done
}
after_push() {
  local old new line
  old=${CHAIN_BASE:-$BASE}; new=$TRAIN_TIP
  cleanup_all
  final_check
  MAIN_END=$(git -C "$WS" rev-parse -q --verify refs/heads/main 2>/dev/null)   # journal des trains (D4) : lu avant la mise à jour du dossier d'exécution, que plus aucune commande Git ne suit
  frozen_prepare "$old" "$new"      # outils figés : changements du train et copies préparées depuis le commit, AVANT le dossier d'exécution
  RUN_UPDATED=1
  update_run_tree
  frozen_swap                       # l'échange, sans commande Git, APRÈS lui
  # D21 : seulement quand tout le reste est complet (le code sera 0, sens fusionné) ; jamais après un autre code
  [ -n "$CAUSES" ] || remove_relay_notes
  if [ -n "$CAUSES" ]; then
    say "train fusionné et poussé, fin incomplète :"
    while IFS= read -r line; do raw "  - $line"; done <<< "$CAUSES"
    exit 75
  fi
  say "terminé : main $(sha12 "$old") -> $(sha12 "$new"), ${#NAMES[@]} branche(s)"
  exit 0
}

# --- programme --------------------------------------------------------------------------------------------------------------------------
main() {
  finish_env_retire_dbtest
  STEP="usage"
  set_ligne
  parse_args "$@"
  STEP="dossiers du lab"
  lab_paths_init || exit 78
  open_log
  check_python
  STEP="lancement"
  launch_checks
  STEP="verrou"
  take_lock
  record_freeze
  announce_test_variables
  STEP="garde du matin"
  morning_guard
  STEP="base"
  establish_base
  STEP="état des références"
  detect_state
  say "train : ${#NAMES[@]} branche(s), base origin/main $(sha12 "$BASE")"
  case "$START_STATE" in
    S2)
      auto_refuse_resumption S2
      say "reprise : le train est déjà poussé ; reprise au nettoyage"
      [ "$ESSAI" = 0 ] || trial_end
      PUSH_DONE=1
      after_push ;;
    S1)
      auto_refuse_resumption S1
      say "reprise : main porte déjà le train des ${#NAMES[@]} branche(s) (sommet $(sha12 "$TRAIN_TIP")) ; noms, secrets, contrôles par branche et garde du matin refaits ; reprise au push"
      admission
      scan_content "$MAIN_START" "${NAMES[@]}"
      control6_resume
      [ "$ESSAI" = 0 ] || trial_end
      STEP="garde du matin"
      morning_guard
      push_main
      after_push ;;
    *)
      admission
      build_train
      ws_bmad_check "$TRAIN_TIP"   # R-20261102-37 (Q313) : avant le runner et aussi en --essai
      scan_content "$TRAIN_TIP" "${NAMES[@]}"
      control14
      control6
      if [ "$ESSAI" = 1 ]; then print_summary; trial_end; fi
      integration_checks
      print_summary
      if [ "$AUTO" = 1 ]; then auto_gate; else question; fi
      arrival
      after_push ;;
  esac
}
main "$@"
exit 76
