#!/bin/bash
# Lance toutes les suites de tests de PMZilla Lab d'un coup : les suites Python (uv run python -m unittest) de
# chaque dossier tests/<nom>/ qui contient des test_*.py, puis les tests shell (hook des noms, hook post-commit, evals_auto.sh, liens).
# Affiche une ligne par suite, le total et sort avec le code 1 si une suite a échoué (0 sinon).
#
#     bash tests/run_all.sh           toutes les suites
#     bash tests/run_all.sh watch_lab seulement les suites dont le nom est donné (dossier ou « hooks », « installation »)
#     bash tests/run_all.sh -v        en plus, la sortie complète de chaque suite
#     bash tests/run_all.sh --staged  lancement CIBLÉ : tools/select_suites.py lit l'index et choisit les suites ; il exige l'exécution
#                                     complète pour un fichier qu'aucune suite ne nomme (alors c'est un lancement complet, empreinte comprise)
#     bash tests/run_all.sh --portable  les suites absentes de tests/suites_mac.txt (conteneur de la CI locale), après la ligne
#                                     « run_all : suites propres au Mac non lancées : <n> (<nom:genre …>) »
#     bash tests/run_all.sh --mac       seulement les suites de tests/suites_mac.txt (passe Mac)
#     bash tests/run_all.sh --branch  lancement de BRANCHE (change targeted-suites-admission, D2) : tools/select_suites.py --range origin/main...HEAD
#                                     choisit les suites de toute la différence de la branche avec origin/main ; elles tournent sur le sommet propre ;
#                                     vertes, la ligne « <arbre du sommet><tab><suites séparées par des virgules> » est écrite dans pmzilla-run-branch-ok
#                                     du dossier Git privé du worktree, puis « run_all : empreinte de branche écrite (<n> suite(s)) » après le total.
#   --branch exige une branche de travail (ni main, ni tête détachée) et un worktree propre, sinon code 2 « run_all : --branch exige une branche de
#   travail et un worktree propre » ; avec un nom de suite, --staged, --portable ou --mac : code 2 « run_all : --branch ne se combine pas avec
#   <option> » (en session aussi : l'usage est contrôlé avant le refus de session). Quand le sélecteur exige l'exécution complète ou échoue, c'est un
#   lancement complet (empreinte complète). Il efface d'abord l'empreinte de branche précédente, n'écrit ni n'efface sinon l'empreinte complète ni la
#   ciblée, garde le gel du code 4. L'empreinte de branche n'est une preuve que pour l'inscription à la liste prête (tools/train_ready.py) : jamais pour pre-commit
#   ni pre-push (le train, depuis ci-local-runner D9, passe par la porte du conteneur puis --mac, pas par un runner complet). Remplace : le runner complet par branche avant l'inscription
#   (design D3 de autonomous-trains-observe). Retrait : tombe si le train cesse de lancer le runner complet sur l'arbre intégré.
#   --portable et --mac (local-ci-container, D3) : ni empreinte pre-commit écrite ni effacée, comme un lancement filtré (--mac écrit seulement celle de D7, ci-dessous) ; avec --staged, un nom de
#   suite ou l'un avec l'autre : code 2 ; liste illisible : code 2. Liste : une ligne « <suite>:<python|shell> # <raison> » par suite
#   propre au Mac, commentaires et lignes vides permis ; un test de tests/run_all vérifie chaque entrée.
#   Empreinte du Mac (ci-local-runner, D7) : --mac, vert, worktree propre au départ et à la fin, arbre de HEAD inchangé, ajoute l'arbre de HEAD
#   (une ligne par arbre, propriétaire seul, ligne retirée au départ) à pmzilla-run-mac-ok du dossier Git commun, puis dit « run_all : empreinte Mac
#   écrite pour l'arbre <court> » ou « run_all : empreinte Mac non écrite (<raison>) ». Jamais lue par pre-commit ; ne change pas le code de sortie.
#   Remplace : rien (--mac n'écrivait rien). Retrait : tombe quand tests/suites_mac.txt ne liste plus aucune suite.
#
# Codes de sortie : 0 tout vert, 1 une suite en échec, 2 usage ou aucune suite trouvée sans nom donné, 4 fin de branche en cours (gel),
# 5 des noms de suites donnés dont aucun ne correspond à une suite (« run_all : aucune suite ne correspond aux noms donnés (<noms>) » : aucune
# suite lancée, aucune empreinte ni durée écrite ; deux noms dont un existe lancent celui-là ; --staged garde son code 2, le sélecteur décide),
# 6 lancement refusé dans une session Claude Code (voir ci-dessous : lancement complet, --branch et --portable compris, la preuve passe par le conteneur), 7 lancement complet arrêté avant la première suite : Node ou node_modules
# de Mothra à mettre en conformité (voir « Suites npm » ci-dessous ; installation.md dit quand lancer npm ci),
# 9 session Claude Code : conteneur indisponible (codes 3, 5, 6, 7 ou 8 de tools/ci_local.sh, ou script introuvable : 127), sans repli sur le Mac, aucune suite
# lancée (celles du Mac comprises), aucune empreinte écrite ni effacée, aucune ligne de durées. Phrase :
# run_all : conteneur indisponible (code <c>) : aucune suite portable lancée ; rien n'est écrit
# Le code 8 (garde des lancements non complets, son script et le prétest de Mothra) est RETIRÉ avec le verrou de session (tooling-proof-in-container, T2,
# R-20261104-7 P2) : remplacé par rien ; plus aucun runner complet ne tourne sur le Mac en session, une forme directe ne produit aucune preuve.
# 10 session Claude Code, enveloppe figée de la CI locale PRÉSENTE (~/.pmzilla-lab/outils-figes/ci_local.sh ; bash-sandbox-n2, D10 et D12, tâche 9.1) : le lanceur
# n'appelle plus ni le script de la CI ni l'enveloppe (son enfant resterait sous le bac à sable, sans la socket de Docker : code 9 certain). Il lance ici les
# suites propres au Mac, puis dit l'appel que la session doit faire elle-même, seul dans son appel Bash :
# run_all : suites portables à lancer d'abord, seules, par l'enveloppe : /bin/bash --noprofile --norc -p <dossier personnel>/.pmzilla-lab/outils-figes/ci_local.sh run --travail --worktree ~/PMZilla-Lab/worktrees/<n> <suites>
# (la forme unique des enveloppes exclues du bac à sable, D13, R-20261111-22, -48, tâche 19.8 ; remplace : la forme `bash ~/…` puis la forme avec `~` ; retrait : avec le bac à sable)
# R-20261111-54 : cette forme n'est imprimée que si le fichier géré du bac à sable est présent (/Library/Application Support/ClaudeCode/managed-settings.d/50-pmzilla-bac-a-sable.json,
# remplacé par un faux fichier dans la copie du lanceur des tests) ; absent, la ligne est « run_all : suites portables à lancer d'abord, seules, en commande directe : bash tools/ci_local.sh run --travail <suites> »
# (`--index` pour un --staged). Remplace : R-20261110-20 (Q7, deux signaux). Retrait : avec le bac à sable.
# et sort avec le code 10 ; une suite du Mac rouge garde le code 1 et la ligne est imprimée quand même. Un --staged sans ligne verte de la preuve d'index
# (tools/preuve_arbre.py --index, pour l'arbre de l'index et les suites choisies, ou « complet ») dit la même ligne avec « run --index » (sans suite pour un
# --staged devenu complet), puis « run_all : aucune empreinte écrite ni effacée », ne lance aucune suite, n'écrit ni n'efface rien et sort avec le code 10 ;
# la session lance l'enveloppe, puis relance --staged. Avec cette ligne verte, il lance les suites propres au Mac et écrit l'empreinte ciblée comme avant.
# Le chemin de l'enveloppe est le dossier personnel de la base des comptes, calculé à l'exécution (jamais écrit dans ce fichier) ; l'argument du worktree s'écrit avec « ~ ». Sans enveloppe, ou hors session : le chemin d'avant (conteneur
# appelé par le lanceur, codes 0, 1 et 9), rien ne change ; aucun signal du bac à sable n'est lu : seule la présence du fichier de l'enveloppe compte.
# Remplace : le code 9 qu'une session reçoit pour une suite portable sous le bac à sable (conteneur injoignable depuis un enfant du bac). Retrait : avec la règle
# D10 qu'il sert (permanent tant que les sessions tournent sous le bac et que le conteneur est le lanceur des suites portables) ; sans enveloppe, le chemin
# d'avant reste.
#
# Ordre de départ (D1) : avec plus d'une tâche, les suites en parallèle partent d'abord sans mesure (ordre déclaré), puis par durée estimée
# décroissante : tools/suite_order.py lit le fichier des durées (médiane des cinq dernières durées vertes d'un passage complet). Fichier
# inutilisable : l'ordre déclaré et une ligne le disant. Remplace la liste statique PREMIERES_SUITES (R-139), retirée dans la même branche.
#
# Chevauchement de la phase en série (D2) : MODE_SERIE donne à chaque entrée de EN_SERIE son mode, « chevauche » ou « seule ». Une entrée
# « seule » part quand plus rien ne tourne. Une entrée « chevauche » part quand toutes les suites en parallèle ont démarré, qu'au plus la moitié
# des tâches (au moins une) tournent encore, qu'aucune entrée de SANS_CHEVAUCHEMENT ne tourne et qu'aucune autre suite en série ne tourne.
# RUN_ALL_OVERLAP=0 coupe le chevauchement. Une tâche ou la base jetable : comme avant.
#
# Journal des runners complets (D4) : chaque lancement complet ajoute une ligne à journal/run-all-complets.tsv (dossier de données du compte en
# session, du lab sinon ; sur une racine injectée, seulement avec RUN_ALL_RUNS_JOURNAL) : début, fin, secondes, verdict, contexte, poste,
# tâches, suites, seul ou concurrent, autres au plus, genres des autres, charge au plus. Les lancements en cours laissent une entrée
# journal/run-all-presence/<pid>. Ni chemin, ni nom de suite, ni sortie. Une panne du journal est dite en une ligne sans changer le code.
#
# Sortie des suites rouges gardée (R-20261101-01, Q136 (a)) : un passage qui se termine rouge écrit la sortie de chacune de ses suites rouges dans UN
# fichier suites-rouges/rouge-<date>-<pid>.txt du dossier de données (celui du compte en session, du lab sinon ; sur une racine injectée, seulement
# avec RUN_ALL_RED_DIR), hors dépôt, avec le nom de la suite, son verdict, la date et le mode du lancement ; les dix derniers fichiers au plus (les
# plus anciens effacés). Aucune valeur n'est ajoutée : seulement la sortie que les suites ont produite. Le passage dit en fin « run_all : sortie des
# suites rouges gardée : ~/.pmzilla-lab/suites-rouges/<fichier> » (le nom du fichier seul hors du dossier du compte : jamais le nom du compte). Une écriture impossible est un avertissement d'une ligne : ni le code de sortie ni les empreintes ne changent.
# Un passage vert, interrompu ou refusé n'écrit rien. Remplace : rien (la sortie était dans un dossier temporaire supprimé à la sortie, donc perdue).
# Retrait : permanent, tant que le lanceur affiche la fin de sortie de ses suites rouges, car sans cette copie la cause d'un rouge disparaît avec le passage.
# Dossier du compte refusé en écriture (bac à sable, bash-sandbox-n2, D10 et tâche 9.4) : la même sortie va alors dans le dossier temporaire de la session,
# ${TMPDIR:-/tmp}/pmzilla-suites-rouges/rouge-<date>-<pid>.txt (dix fichiers au plus), et la ligne d'avertissement l'ajoute : « run_all : sortie des suites
# rouges non gardée (écriture impossible) ; copie dans le dossier temporaire de la session : pmzilla-suites-rouges/<fichier> » (le nom du dossier et du fichier
# seuls, jamais le chemin). L'écriture refusée déclenche elle-même le repli : aucun signal du bac n'est lu. Si le repli échoue aussi : l'avertissement d'avant,
# seul. Les journaux (session, runners complets, présence, durées) restent en échec doux : une ligne, le code de sortie inchangé ; en session, une seule ligne
# « run_all : journaux de session non écrits (écriture impossible) » pour le journal de session et la présence. Remplace : rien en dehors d'une écriture refusée
# (le dossier du compte reste la destination). Retrait : avec le bac à sable (retour arrière final de bash-sandbox-n2).
#
# Préparation des environnements uv (R-20261101-104, sortie rouge du 2026-11-01 : deux uv run concurrents sur un même script à dépendances en ligne
# se disputaient la construction de son environnement dans le cache uv). Avant la phase parallèle, et seulement quand elle existe (plus d'une
# tâche et plus d'une suite), le lanceur construit à la suite, un script après l'autre, l'environnement de chaque script Python des dossiers tools,
# tests et .claude/skills qui porte un bloc « # /// script » : « uv sync --script <script> », qui installe sans lancer le script. Sélection : les
# fichiers SUIVIS par Git (git ls-files, filtre sur l'en-tête), comme le conteneur (git archive) et la clé de l'image ; la source unique est l'étape de
# préparation de ci/Dockerfile (ligne 53), parce qu'elle construit l'image ; tools/ci_local.sh (scripts_pep723) et ce lanceur la suivent, et un test de
# tests/run_all compare les trois lectures sur l'arbre du dépôt. Différences avec la commande du Dockerfile (« uv sync --script » seul, dans une copie
# jetable) : ici le tri est fixé (LC_ALL=C), « --frozen » est ajouté quand <script>.lock est suivi (jamais de verrou réécrit dans le dépôt) et un
# verrou créé par la préparation est retiré (l'arbre reste propre). Hors ligne quand le lanceur l'est (UV_OFFLINE, posée par tools/ci_local.sh dans le
# conteneur). Une préparation en échec est un AVERTISSEMENT, pas un rouge (décision de l'auteur, R-20261101-106) : une ligne « run_all :
# avertissement : préparation uv en échec : <script> (code N) » avec la fin de la sortie de uv, les autres scripts sont préparés, aucune suite n'est
# sautée, le code de sortie ne change pas, et la ligne TOTAL finit par « · avertissement : préparation uv en échec : <scripts> » (tools/ci_local.sh
# la reprend dans son rapport et dans son verdict). Ni journal ni sortie gardée propres : l'avertissement n'est pas un rouge, la ligne TOTAL suffit
# et le passage suit sa vie normale. Sa durée est une ligne du fichier des
# durées (suite « preparation », type « uv ») et figure dans la liste des plus lentes. Ce n'est pas un ordonnancement des suites (R-20261101-58) :
# l'ordre de départ ne change pas. Sans script à bloc (racine factice des tests), ou en série (une tâche, base jetable), rien n'est lancé ni dit.
# Coût : un « uv sync --script » par script (environ cent), coût à mesurer (R-104, preuve).
# Remplace : la course du cache uv entre uv run concurrents (R-104). Retrait : permanent tant que des scripts à dépendances en ligne tournent en parallèle.
#
# Session Claude Code (session-runner, décisions 1 à 3 de l'auteur) :
# CLAUDECODE posée (même vide). Après les contrôles d'usage et PMZILLA_NO_EVALS, avant le gel :
#  - FINISH_LOCK_TOKEN, DBTEST_PORT ou PMZILLA_FINISH_LOCK_MAX_AGE non vides : code 6 pour tout lancement (elles lèveraient le gel ou laisseraient
#    passer la vraie base) ;
#  - PREUVE PAR LE CONTENEUR (tooling-proof-in-container, T1, D3, R-20261102-40 et R-20261102-44) : un lancement complet NU (sans nom de suite, ni
#    --staged, --portable ou --mac) et --branch sont refusés en code 6, aucune suite, aucune empreinte écrite ni effacée : « run_all : lancement
#    complet refusé en session : la preuve passe par le conteneur (bash tools/ci_local.sh run <branche>, puis bash tests/run_all.sh --mac) » et
#    « run_all : --branch refusé en session : la preuve passe par le conteneur (bash tools/ci_local.sh run <branche>, puis bash tests/run_all.sh
#    --mac) » ; --portable de même (« run_all : --portable refusé en session : … »). Hors session, le runner complet du Mac reste la voie de l'auteur (R-76) : rien ne change.
#    Remplace : la garde du lancement complet nu et de --branch en session (matin, verrou), session-runner D1-D3. Retrait : permanent tant que la CI est le runner.
#  - LES SUITES DE LA SESSION (T2, D1, D4, D8 ; R-20261104-7 P3, P5, P6) : un lancement nommé ou --staged coupe ses suites par tests/suites_mac.txt, dit
#    « run_all : suites portables envoyées au conteneur : <n> ; suites propres au Mac lancées ici : <m> », envoie les suites portables à
#    tools/ci_local.sh (trouvé à côté du lanceur, jamais par la racine) et lance ICI les seules suites propres au Mac. Nommé : « run --travail <suites> »
#    (arbre de travail, aucune preuve). --staged : « run --index <suites> » (arbre de l'index ; seul chemin vers l'empreinte ciblée). --staged qui devient
#    complet (sélecteur en échec, absent, vide ou exigeant l'exécution complète) : « run --index » sans suite (mode complet : trois phases) puis toute
#    la passe Mac, l'empreinte COMPLÈTE n'étant ni écrite ni effacée. Le script reçoit un environnement sans aucune variable CI_LOCAL_* présente (liste
#    lue par compgen, R-20261105-7) et PMZILLA_LAB_DATA = le dossier du
#    compte. Un --staged devenu complet refuse RUN_ALL_ROOT et un PMZILLA_LAB_DATA qui n'est pas celui du compte (getpwuid ; realpath des deux côtés), code 6,
#    avant tout appel et tout effacement d'empreinte.
#    Empreinte ciblée (D1) : effacée une fois le conteneur joint, écrite (« run_all : empreinte ciblée écrite (conteneur et Mac) pour l'index <court> »)
#    seulement quand la partie Mac est verte, que git write-tree n'a pas changé et qu'une ligne verte de la preuve d'index porte le même arbre et couvre les
#    suites envoyées (tools/preuve_arbre.py --index) ; sinon « run_all : empreinte ciblée non écrite (<raison>) », <raison> : conteneur rouge (code N), preuve du
#    conteneur absente pour cet index, index modifié pendant le passage, suites propres au Mac rouges, écriture impossible (R-20261104-51 Q1 (a) : la raison « conteneur rouge »
#    remplace la raison unique pour un conteneur rouge ; retrait permanent, tant que la session prouve par le conteneur).
#    Un --staged devenu complet garde, avant tout appel, la garde du matin légère (R-20261102-3 et -5 : veille ou sauvegarde du jour, module
#    tools/morning_state.sh runner, refus fermé) : GARDÉE par décision de l'auteur du 2026-11-04 (T2-1 (a)). --portable est refusé en session (code 6,
#    même phrase que le complet nu, T2-2 (a)). Un code du script du conteneur hors 0, 1, 3, 5, 6, 7, 127 : rien n'est lancé, code 1, une phrase qui
#    donne le code (T2-3 (b)). Un --staged dont toutes les suites sont propres au Mac écrit l'empreinte ciblée sans ligne de preuve d'index (T2-5 (a)).
#    Remplace : les lancements nommés et ciblés des suites portables sur le Mac en session et le verrou « un seul runner complet de session »
#    (R-20261029-31), RETIRÉS. Retrait : permanent, tant que la CI est le runner.
#  - Chaque décision de session (lancement au conteneur, refus) ajoute une ligne au journal journal/run-all-session.tsv du dossier de données
#    (date, verdict, motif, poste ; ni chemin, ni nom, ni sortie) ; les lignes de plus d'un an sont purgées à chaque écriture ; une panne du
#    journal ne change ni le code ni le lancement.
# Un refus de session : aucune suite, aucune empreinte écrite ni effacée, aucune ligne de durées. --mac (sauf les deux variables
# de gel) et hors session : rien ne change. Le gel (code 4) reste lu pour tout lancement qui n'est pas refusé avant lui.
#
# Suites shell (R-130) : tests/suites_shell.txt, une ligne « <chemin> <nom> <interprète> » par suite, triée par chemin ; le lanceur les lance
# dans l'ordre du fichier. Une ligne mal formée : code 2, « run_all : tests/suites_shell.txt, ligne <n> mal formée » ; liste illisible : code 2.
# Un test shell listé mais absent du disque est un ÉCHEC nommé (jamais un saut silencieux) ; un filtre ne concerne que ses suites.
# Un script de test shell sous tests/ qui n'est pas dans tests/suites_shell.txt doit être déclaré auxiliaire (lignes « AUXILIAIRE »), sinon
# tests/run_all/test_run_all.py échoue en le nommant.
# AUXILIAIRE tests/db_scripts/test_db_restore_test.sh : lancé par tests/db_scripts/test_db_scripts.sh (suite voisine) ; le lister le ferait tourner deux fois.
# AUXILIAIRE tests/db_scripts/test_db_rehearsal.sh : lancé par tests/db_scripts/test_db_scripts.sh (suite voisine) ; le lister le ferait tourner deux fois.
# AUXILIAIRE tests/fin_piege/ancien-bloc.sh : données du cas témoin de tests/fin_piege/test_fin_piege.sh (ancien piège de fin), jamais lancé seul.
# AUXILIAIRE tests/sandbox_sonde/sonde.sh : sonde du bac à sable de Bash (bash-sandbox-n2, D9), jouée par la seule session de répétition sous le vrai bac, jamais par le lanceur ; la suite sandbox_config la lit sans la lancer. Retrait : avec la sonde.
#
# Suites npm (mothra-slices, groupe 3, design D9) : la ligne « SUITES_NPM=(<dossier>:<nom> …) » de ce fichier (UNE ligne, sans commentaire à sa
# suite : tools/ci_local.sh, tools/select_suites.py, tools/dbtest.sh et tests/db/test_couverture_base.py la lisent telle quelle ; dossier : un
# dossier de la racine, sans « / » ni « .. »). Entrée mal formée : code 2, « run_all : SUITES_NPM, entrée <n> mal formée ». Une suite npm est la paire
# (nom, « npm »), après les suites shell dans l'ordre de la ligne. Pour les tests de ce script, RUN_ALL_SUITES_NPM remplace la ligne (entrées séparées
# par des blancs, vide : aucune) ; sur une racine injectée (RUN_ALL_ROOT) sans cette variable, aucune suite npm : la ligne est celle du dépôt réel.
# Elle passe par le même relais que les autres (groupe de processus, RUN_ALL_SUITE_TIMEOUT, entrée fermée, TMPDIR propre,
# PMZILLA_LAB_DB_* et MOTHRA_DB_* retirées sauf avec DBTEST_PORT, en série avec DBTEST_PORT) et lance « npm test » dans son dossier, sans réseau,
# SEULEMENT si :
#  - le dossier existe, sinon ÉCHEC nommé « suite npm absente : <nom> » ;
#  - le Node trouvé est celui du fichier <dossier>/.node-version, sinon « Node de Mothra différent de la version fixée » (la suite n'est pas lancée) ;
#  - node_modules correspond au verrou (tools/npm_lock_check.py), sinon « dépendances npm absentes ou différentes du verrou : <nom>
#    (lancer npm ci dans <dossier>/) » : le lanceur n'installe, ne met à jour et ne télécharge jamais un paquet.
# Arrêt immédiat (code 7) : un lancement COMPLET (sans nom de suite, sans --portable ni --mac, y compris un --staged qui devient complet) dont une
# suite npm a son dossier mais un Node différent de <dossier>/.node-version, ou un node_modules qui ne correspond pas au verrou, s'arrête AVANT la
# première suite, sans effacer d'empreinte : « run_all : dépendances npm à mettre en conformité avant un lancement complet (<raison>) » puis la commande à lancer
# (« cd <racine>/<dossier> && npm ci », ou le choix de la bonne version de Node d'abord). Un lancement nommé, ciblé ou filtré garde l'échec nommé de la suite.
# Le rapporteur lit les lignes de RÉSUMÉ de « node --test » (formats spec et TAP : le bloc « tests », « pass », « fail », « cancelled », « skipped »,
# sommé sur tous les paquets ; une ligne « # pass » imprimée par un test, hors d'un bloc de résumé, n'est pas comptée), imprime une ligne « saut : <nom> »
# par test sauté puis « N réussis, M échec(s) » (N = tests − fail − cancelled, les sautés comptent comme réussis, comme une suite shell ; « tests 0 » est
# un échec nommé) ; la sortie de npm test est aussi imprimée en direct (un délai dépassé la montre) ; la ligne de la suite prend la forme shell
# « OK (sautés=<c>) » ou « ÉCHEC (code <c>, <r> échec(s), sautés=<c>) » ; la ligne « Tests sautés » gagne « , suites npm <c> » seulement si une suite
# npm a été lancée ; le fichier des durées prend le type « npm ».
#
# Garde-fou de commit : PMZILLA_NO_EVALS (réservée à git commit) fait refuser le lancement (code 2). Un lancement COMPLET (sans nom
# de suite) qui se termine sans échec écrit l'empreinte de l'index (git write-tree) dans .git/pmzilla-run-all-ok ; le hook pre-commit
# refuse le commit si elle ne correspond pas à l'index. Donc : git add, puis run_all.sh && git commit. Un lancement filtré n'écrit rien.
# Un lancement ciblé (--staged) efface d'abord l'empreinte ciblée précédente (.git/pmzilla-run-targeted-ok), puis, s'il se termine sans
# échec, y écrit l'empreinte de l'index : sur une branche de travail, le hook pre-commit accepte l'une ou l'autre ; sur main, jamais la ciblée.
# Un lancement ciblé n'écrit ni n'efface l'empreinte complète (sauf s'il a dû passer en exécution complète).
#
# Base de données (test-speed-2, D2) : hors passage de la base jetable (DBTEST_PORT, posé par tools/dbtest.sh, absent ou vide), le lanceur
# retire de l'environnement de chaque suite, Python ou shell, toute variable PMZILLA_LAB_DB_* et l'écrit en une ligne avant la première suite ;
# avec DBTEST_PORT, elles passent telles quelles. Son propre environnement, ses codes et ses empreintes ne changent pas.
#
# Gel pendant une fin de branche (multi-session-piloting, D7, rendu ciblé par autonomous-trains-merge, D18) : après ses contrôles d'usage et avant
# toute suite, le lanceur cherche le verrou de fin de branche (dossier pmzilla-fin-en-cours du dossier Git commun de sa racine ; une racine injectée
# lit le verrou de CETTE racine seulement). Un verrou vivant dont le jeton n'est pas celui de FINISH_LOCK_TOKEN (variable absente comprise) et que
# finish_lock.freezes() couvre (la racine est dans la liste du verrou, le lancement écrit main ou le dossier d'exécution, ou le verrou n'a pas de
# liste lisible) : code 4, « run_all : fin de branche en cours (<branche>), lancement refusé », aucune suite, aucune empreinte écrite ni effacée,
# aucune ligne de durées, aucune attente ; lancement complet, ciblé ou filtré. Jeton égal, verrou absent ou racine que la liste ne nomme pas :
# rien ne change. Verrou périmé (processus mort, plus vieux que PMZILLA_FINISH_LOCK_MAX_AGE
# secondes, 21600 par défaut, ou sans pid lisible depuis plus de dix secondes) : « run_all : verrou de fin périmé, ignoré », puis le lancement
# continue. Le lanceur ne crée, ne retire ni ne modifie jamais le verrou.
#
# Tests sautés (test-speed-2, D25) : après la liste des plus lentes et avant la ligne de total, « Tests sautés : <total> (suites Python <p>,
# branches shell <s>) ». Suite Python : le nombre après « skipped= » de sa dernière ligne (0 sans) ; suite shell : les lignes de sa sortie
# qui commencent par « saut : » (une par branche sautée) ; une suite en délai dépassé compte 0. Ni les lignes de suite, ni le total, ni le
# fichier des durées, ni les codes ne changent.
# Sauts d'une suite shell (skips-visible, D1) : s'il y en a, sa ligne les montre dans le verdict, « OK (sautés=<n>) » ou
# « ÉCHEC (code <c>, <r> échec(s), sautés=<n>) » ; sans saut, la ligne est celle d'avant. Le même compte sert à la ligne « Tests sautés ».
#
# Suites en parallèle (test-speed-2, D19 à D23). RUN_ALL_JOBS : nombre entier positif de suites à la fois (autre valeur : code 2 avant toute
# suite) ; par défaut la moitié des processeurs logiques (sysctl -n hw.logicalcpu, à défaut getconf _NPROCESSORS_ONLN), au moins 1, 1 si
# illisible. Avec 1 : le passage en
# série d'avant, mêmes lignes dans le même ordre. Avec plus d'une tâche, une ligne « run_all : <n> suites à la fois, puis en série : <liste> »
# précède la première suite. Les suites de EN_SERIE ci-dessous passent après toutes les autres, une à la fois, dans l'ordre déclaré ;
# les suites mesurées partent par durée décroissante (voir « Ordre de départ »). Avec DBTEST_PORT (base jetable) : toutes les suites une à la fois (les rôles de la
# base sont communs à l'instance). Chaque suite garde son groupe de processus, son chien de garde, son entrée fermée et sa sortie, reçoit
# son propre TMPDIR (retiré à la fin) et PYTHONDONTWRITEBYTECODE=1, en série comme en parallèle. Les lignes sortent dans l'ordre déclaré
# (dossiers Python, puis liste shell), chacune dès que sa suite et toutes les précédentes ont fini ; la durée d'une suite est la sienne.
# Une suite est la paire (nom, genre) : « offsite_backup » Python et shell sont deux suites. Sondage toutes les dixièmes de seconde (bash 3.2
# n'a pas wait -n). Interruption (INT, TERM) : TERM puis KILL sur chaque groupe en cours, fichiers temporaires retirés, aucune empreinte,
# sortie par le signal reçu.
#
# Aucun appel réseau ni payant ; chaque suite travaille dans un dossier temporaire (voir son en-tête).
# Variables (pour les tests de ce script) : RUN_ALL_ROOT (racine du dépôt), RUN_ALL_DEPS (options `uv run --with …`).
# Délai par suite : RUN_ALL_SUITE_TIMEOUT (secondes entières, défaut 900). Une suite plus longue est arrêtée avec ses processus
# (TERM puis KILL sur son groupe), comptée en échec « délai dépassé », et le lanceur passe à la suivante. Valeur invalide : code 2.
# Mesures (change test-speed) : chaque ligne de suite finit par sa durée (« · 12,3 s »), les dix suites les plus lentes sont listées avant
# la ligne de total, qui finit par « durée totale ». Une ligne par suite est ajoutée au fichier des durées (dix champs séparés par une
# tabulation), mesures/run_all-durees.tsv du dossier de données du lab (tools/lab_paths.sh), commun à l'espace de travail et aux worktrees ;
# jamais de chemin, de nom de test ni de sortie. RUN_ALL_DURATIONS désigne un autre fichier ; sur une racine injectée (RUN_ALL_ROOT) sans
# cette variable, aucun fichier n'est écrit. Une panne de mesure est dite en une ligne et ne change ni le code, ni les lignes, ni les empreintes.
set -u
exec </dev/null   # entrée standard fermée : aucune suite, aucun outil lancé par une suite ne peut attendre le clavier (D1)
LANCEUR_DIR=$(cd "$(dirname "$0")" && pwd -P)   # dossier du lanceur, lu avant tout cd : une session y trouve tools/ci_local.sh, tools/preuve_arbre.py et tools/morning_state.sh
RACINE="${RUN_ALL_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
# pymupdf4llm<2 : la 2.0 (parue le 2026-10-19) ne déclare plus pymupdf, que les suites de convert_books importent.
DEPS="${RUN_ALL_DEPS---with numpy --with httpx --with pyyaml --with requests --with feedparser --with trafilatura --with beautifulsoup4 --with markdownify --with "pymupdf4llm<2" --with ebooklib --with "psycopg[binary]" --with jsonschema}"
# Suites npm (mothra-slices, groupe 3, D9) : « <dossier>:<nom> » par suite. UNE ligne, sans commentaire à sa suite (voir l'en-tête).
SUITES_NPM=(mothra:mothra)
if [ -n "${RUN_ALL_SUITES_NPM+x}" ]; then read -r -a SUITES_NPM <<< "$RUN_ALL_SUITES_NPM"   # tests de ce script : remplace la ligne ci-dessus
elif [ -n "${RUN_ALL_ROOT+x}" ]; then SUITES_NPM=()   # racine injectée : la ligne est celle du dépôt réel, pas de celle de la racine factice
fi
BAVARD=0
CIBLE=0
BRANCHE=0   # --branch (targeted-suites-admission, D2)
SESSION_SPLIT=0   # 1 : lancement de session scindé entre le conteneur et le Mac (tooling-proof-in-container, T2, D4) ; posé par session_scinder
SESSION_RIEN_ICI=0   # 1 : rien à lancer sur le Mac dans ce lancement de session (toutes les suites sont parties au conteneur)
FILTRE_MAC=0   # 1 : toute la passe Mac d'un --staged qui devient complet en session (suites de tests/suites_mac.txt seulement, sans empreinte Mac)
CONTENEUR_CODE=0; ARBRE_SESSION=""; PORTABLES=(); NOMS_MAC=()
MODE=""   # vide, portable ou mac (local-ci-container, D3)
NOMS=()
for argument in "$@"; do
  case "$argument" in
    -v) BAVARD=1 ;;
    --staged) CIBLE=1 ;;
    --branch) BRANCHE=1 ;;
    --portable|--mac)
      if [ -n "$MODE" ]; then echo "run_all : --portable et --mac ne se combinent pas"; exit 2; fi
      MODE=${argument#--} ;;
    *) NOMS+=("$argument") ;;
  esac
done
if [ "$BRANCHE" -eq 1 ]; then
  if [ ${#NOMS[@]} -gt 0 ]; then echo "run_all : --branch ne se combine pas avec des noms de suites (${NOMS[*]})"; exit 2; fi
  if [ "$CIBLE" -eq 1 ]; then echo "run_all : --branch ne se combine pas avec --staged"; exit 2; fi
  if [ -n "$MODE" ]; then echo "run_all : --branch ne se combine pas avec --$MODE"; exit 2; fi
fi
if [ "$CIBLE" -eq 1 ] && [ ${#NOMS[@]} -gt 0 ]; then
  echo "run_all : --staged ne se combine pas avec des noms de suites (${NOMS[*]})"
  exit 2
fi
if [ -n "$MODE" ] && [ "$CIBLE" -eq 1 ]; then
  echo "run_all : --$MODE ne se combine pas avec --staged"
  exit 2
fi
if [ -n "$MODE" ] && [ ${#NOMS[@]} -gt 0 ]; then
  echo "run_all : --$MODE ne se combine pas avec des noms de suites (${NOMS[*]})"
  exit 2
fi
DELAI="${RUN_ALL_SUITE_TIMEOUT-900}"
case "$DELAI" in
  ''|*[!0-9]*|0*) echo "run_all : délai par suite invalide ($DELAI) : un nombre entier de secondes est attendu"; exit 2 ;;
esac
if [ -n "${RUN_ALL_JOBS+x}" ]; then
  case "$RUN_ALL_JOBS" in
    ''|*[!0-9]*|0*) echo "run_all : nombre de tâches invalide ($RUN_ALL_JOBS) : un nombre entier positif est attendu"; exit 2 ;;
  esac
  TACHES=$RUN_ALL_JOBS
else
  processeurs=$(sysctl -n hw.logicalcpu 2>/dev/null) || processeurs=""
  case "$processeurs" in   # sysctl illisible (Linux, conteneur de la CI locale) : getconf avant le repli à 1 (local-ci-container, D3)
    ''|*[!0-9]*) processeurs=$(getconf _NPROCESSORS_ONLN 2>/dev/null) || processeurs="" ;;
  esac
  case "$processeurs" in
    ''|*[!0-9]*) TACHES=1 ;;
    *) TACHES=$(( processeurs / 2 )); [ "$TACHES" -ge 1 ] || TACHES=1 ;;
  esac
fi
[ -z "${DBTEST_PORT:-}" ] || TACHES=1   # base jetable : une suite à la fois
cd "$RACINE" || { echo "Racine introuvable : $RACINE"; exit 2; }

# Suites propres au Mac (local-ci-container, D3) : lues seulement avec --portable ou --mac, une entrée « nom:genre » par ligne.
LISTE_MAC=()
if [ -n "$MODE" ] || [ -n "${CLAUDECODE+x}" ]; then   # T2 : une session scinde ses lancements par cette liste (D4)
  if [ ! -r tests/suites_mac.txt ]; then
    echo "run_all : liste des suites propres au Mac illisible (tests/suites_mac.txt)"
    exit 2
  fi
  while IFS= read -r entree || [ -n "$entree" ]; do
    entree=${entree%%#*}; entree=${entree//[[:space:]]/}
    [ -n "$entree" ] && LISTE_MAC+=("$entree")
  done < tests/suites_mac.txt
fi

# Suites shell (R-130) : tests/suites_shell.txt de la racine, à défaut celui qui est à côté du lanceur (racine injectée des tests). Une ligne
# « <chemin> <nom> <interprète> », commentaires et lignes vides permis ; la première ligne mal formée fait refuser le lancement (code 2).
ligne_shell_valide() {   # chemin nom interprète [reste] : 0 si la ligne a exactement ces trois champs, bien formés
  [ $# -eq 3 ] || return 1
  case "$1" in tests/?*.sh) ;; *) return 1 ;; esac
  case "$1" in *[!A-Za-z0-9_./-]*) return 1 ;; esac
  case "$2" in ''|*[!A-Za-z0-9_-]*) return 1 ;; esac
  case "$3" in sh|bash|zsh) ;; *) return 1 ;; esac
  return 0
}
LISTE_SHELL=tests/suites_shell.txt
[ -r "$LISTE_SHELL" ] || LISTE_SHELL="$(dirname "$0")/suites_shell.txt"
if [ ! -r "$LISTE_SHELL" ]; then
  echo "run_all : liste des suites shell illisible (tests/suites_shell.txt)"
  exit 2
fi
SHELL_CHEMIN=(); SHELL_NOM=(); SHELL_INTERP=()
numero_ligne=0
while IFS= read -r brute || [ -n "$brute" ]; do
  numero_ligne=$((numero_ligne + 1))
  sans_commentaire=${brute%%#*}
  set -f; set -- $sans_commentaire; set +f   # champs séparés par des blancs, sans développement des jokers
  [ $# -eq 0 ] && continue
  if ! ligne_shell_valide "$@"; then
    echo "run_all : tests/suites_shell.txt, ligne $numero_ligne mal formée : « $brute »"
    exit 2
  fi
  SHELL_CHEMIN+=("$1"); SHELL_NOM+=("$2"); SHELL_INTERP+=("$3")
done < "$LISTE_SHELL"

# Suites npm (mothra-slices, groupe 3, D9) : les entrées « <dossier>:<nom> » de SUITES_NPM, déclarée en tête de ce fichier.
entree_npm_valide() {   # dossier:nom : 0 si l'entrée a exactement ces deux parties, bien formées
  case "$1" in *:*:*|:*|*:) return 1 ;; *:*) ;; *) return 1 ;; esac
  case "${1%%:*}" in ''|*[!A-Za-z0-9_-]*) return 1 ;; esac
  case "${1#*:}" in ''|*[!A-Za-z0-9_-]*) return 1 ;; esac
  return 0
}
NPM_DOSSIER=(); NPM_NOM=()
numero_entree=0
for entree_npm in ${SUITES_NPM[@]+"${SUITES_NPM[@]}"}; do
  numero_entree=$((numero_entree + 1))
  if ! entree_npm_valide "$entree_npm"; then
    echo "run_all : SUITES_NPM, entrée $numero_entree mal formée : « $entree_npm »"
    exit 2
  fi
  NPM_DOSSIER+=("${entree_npm%%:*}"); NPM_NOM+=("${entree_npm#*:}")
done

if [ -n "${PMZILLA_NO_EVALS+x}" ]; then
  echo "PMZILLA_NO_EVALS est définie : variable réservée à git commit (elle coupe le jeu d'essai du hook post-commit)."
  echo "Elle fausse les tests du hook : relance sans elle (env -u PMZILLA_NO_EVALS bash tests/run_all.sh)."
  exit 2
fi

# Session Claude Code (session-runner, décisions 1 à 3) : voir l'en-tête. Le marqueur posé, même vide, suffit.
JOURNAL_SESSION=""
POSTE_SESSION="espace"
ENVELOPPE=0   # 1 : session avec l'enveloppe figée de la CI locale présente (bash-sandbox-n2, D10) ; posé avec le dossier de données du compte
PANNE_SESSION=0
dire_panne_session() {   # bash-sandbox-n2, tâche 9.4 : le dossier du compte est refusé en écriture sous le bac ; une seule ligne, le code ne change pas
  [ "$PANNE_SESSION" -eq 0 ] || return 0
  PANNE_SESSION=1
  echo "run_all : journaux de session non écrits (écriture impossible)"
  return 0
}
journal_session() {   # verdict motif : une ligne au journal de session, purge des lignes de plus d'un an ; une panne est dite en une ligne et ne change rien
  [ -n "$JOURNAL_SESSION" ] || return 0
  local limite tmp_journal
  limite=$(date -v-365d +%Y-%m-%d 2>/dev/null || date -d '365 days ago' +%Y-%m-%d 2>/dev/null) || limite=""
  ( umask 077; mkdir -p "$(dirname "$JOURNAL_SESSION")" ) 2>/dev/null || { dire_panne_session; return 0; }
  if [ -f "$JOURNAL_SESSION" ] && [ -n "$limite" ]; then
    tmp_journal="$JOURNAL_SESSION.$$"
    awk -F'\t' -v limite="$limite" 'NR == 1 || substr($1, 1, 10) >= limite' "$JOURNAL_SESSION" > "$tmp_journal" 2>/dev/null \
      && mv -f "$tmp_journal" "$JOURNAL_SESSION" 2>/dev/null || rm -f "$tmp_journal" 2>/dev/null
  fi
  if [ ! -s "$JOURNAL_SESSION" ]; then
    printf 'date\tverdict\tmotif\tposte\n' >> "$JOURNAL_SESSION" 2>/dev/null || { dire_panne_session; return 0; }
  fi
  printf '%s\t%s\t%s\t%s\n' "$(date +%Y-%m-%dT%H:%M:%S)" "$1" "$2" "$POSTE_SESSION" >> "$JOURNAL_SESSION" 2>/dev/null || dire_panne_session
  return 0
}
refus_session() {   # motif message : journal, message, code 6
  journal_session refusé "$1"
  echo "run_all : session Claude Code : $2"
  exit 6
}
refus_preuve_conteneur() {   # motif message : refus de session d'un lanceur de preuve (R-20261102-40, D3) ; le message est dit tel quel, sans préfixe
  journal_session refusé "$1"
  echo "$2"
  exit 6
}
# Le verrou « un seul runner complet de session » est retiré avec T2 de tooling-proof-in-container (R-20261102-44, R-20261104-7 P2) : plus aucun runner complet
# ne tourne sur le Mac en session, donc rien à verrouiller. processus_vivant reste : la présence des runners complets (observer_concurrence) la lit.
processus_vivant() {   # pid : 0 s'il vit, y compris sous un autre compte (kill -0 refusé pour permission = vivant) ; 1 sinon
  local sortie
  sortie=$(LC_ALL=C kill -0 "$1" 2>&1) && return 0   # LC_ALL=C : le message de permission est celui que le motif ci-dessous reconnaît
  case "$sortie" in *ermitted*|*ermission*|*utoris*) return 0 ;; esac
  return 1
}
normaliser_lexical() {   # chemin absolu : forme sans « . », sans « .. » ni barres doublées (sans toucher au disque)
  local reste=$1 segment n=0 i=0 sortie=""
  local pile=()
  while [ -n "$reste" ]; do
    segment=${reste%%/*}
    if [ "$reste" = "$segment" ]; then reste=""; else reste=${reste#*/}; fi
    case "$segment" in
      ''|.) ;;
      ..) if [ "$n" -gt 0 ]; then n=$((n - 1)); fi ;;
      *) pile[n]=$segment; n=$((n + 1)) ;;
    esac
  done
  while [ "$i" -lt "$n" ]; do sortie="$sortie/${pile[i]}"; i=$((i + 1)); done
  printf '%s\n' "${sortie:-/}"
}
chemin_canonique() {   # chemin : forme absolue, liens symboliques résolus (realpath). Chemin inexistant : son plus proche ancêtre existant est
  local p=$1 resolu reste=""   # résolu, le reste est normalisé sans toucher au disque (ce cas est dit dans docs/pmzilla/installation.md)
  case "$p" in /*) ;; *) p="$PWD/$p" ;; esac
  if [ -d "$p" ]; then ( cd "$p" 2>/dev/null && pwd -P ); return; fi
  p=$(normaliser_lexical "$p")
  while [ ! -d "$p" ] && [ "$p" != / ]; do
    reste="/${p##*/}$reste"
    p=${p%/*}
    [ -n "$p" ] || p=/
  done
  resolu=$(cd "$p" 2>/dev/null && pwd -P) || return 1
  [ "$resolu" = / ] && resolu=""
  printf '%s%s\n' "$resolu" "$reste"
}
# Garde d'un --staged de session qui devient complet (T1 puis T2) : la racine injectée, le dossier de données de l'appelant et la garde du matin légère
# (R-20261102-3, -5 : veille ou sauvegarde du jour, module tools/morning_state.sh runner) sont refusés AVANT tout effacement d'empreinte et tout appel du
# conteneur (code 6). Seul le verrou « un seul runner complet de session » est retiré avec T2 (R-20261104-7 P2) ; la garde du matin est GARDÉE (décision de
# l'auteur du 2026-11-04, T2-1 (a)). Remplace : garde_lancement_complet_session (sans son verrou).
# Retrait : tombe avec l'escalade d'un --staged en session (permanent tant que la CI est le runner).
GARDE_COMPLET_FAITE=0
garde_donnees_session() {
  [ "$GARDE_COMPLET_FAITE" -eq 0 ] || return 0
  GARDE_COMPLET_FAITE=1
  local demande ligne_matin code_matin
  [ -z "${RUN_ALL_ROOT+x}" ] || refus_session racine "RUN_ALL_ROOT posée pour un lancement complet, lancement refusé"
  [ -n "$vrai_home" ] && [ -n "$donnees_session" ] || refus_session donnees "dossier personnel du compte introuvable, lancement complet refusé"
  demande="${PMZILLA_LAB_DATA:-}"   # posée et non vide : doit désigner le dossier du compte (realpath des deux côtés), sinon code 6
  case "$demande" in
    "~") demande=$vrai_home ;;
    "~/"*) demande="$vrai_home/${demande#\~/}" ;;
  esac
  if [ -n "$demande" ]; then
    [ -n "$(chemin_canonique "$demande")" ] && [ "$(chemin_canonique "$demande")" = "$(chemin_canonique "$donnees_session")" ] \
      || refus_session donnees "PMZILLA_LAB_DATA différente du dossier de données du compte, lancement complet refusé"
  fi
  [ -f "$LANCEUR_DIR/../tools/morning_state.sh" ] \
    || refus_session matin "lancement complet refusé : tools/morning_state.sh introuvable à côté du lanceur"
  ligne_matin=$(env -i HOME="$vrai_home" PATH=/usr/bin:/bin:/usr/sbin:/sbin PMZILLA_LAB_DATA="$donnees_session" \
    /bin/bash "$LANCEUR_DIR/../tools/morning_state.sh" runner 2>&1)
  code_matin=$?
  ligne_matin=$(printf '%s\n' "$ligne_matin" | head -1)
  [ "$code_matin" -eq 0 ] || {   # 1 : la veille ou la sauvegarde tournent ; tout autre code : garde illisible, le refus reste fermé (R-20261102-3, -5)
    if [ "$code_matin" -eq 1 ]; then refus_session matin "lancement complet refusé : veille ou sauvegarde du jour en cours (${ligne_matin:-tools/morning_state.sh : code 1})"
    else refus_session matin "lancement complet refusé : garde du matin illisible (code $code_matin)"; fi
  }
}
if [ -n "${CLAUDECODE+x}" ]; then
  # Le dossier de données d'une session est celui du compte (getpwuid), jamais celui que désigne l'appelant : journal et module du matin.
  vrai_home=$(/usr/bin/perl -e 'print((getpwuid($<))[7])' 2>/dev/null) || vrai_home=""
  donnees_session=""
  [ -n "$vrai_home" ] && donnees_session="$vrai_home/.pmzilla-lab"
  [ -n "$donnees_session" ] && JOURNAL_SESSION="$donnees_session/journal/run-all-session.tsv"
  # Enveloppe figée de la CI locale (bash-sandbox-n2, D10, tâche 9.1) : sa présence décide du code 10 ; la forme imprimée dépend du fichier géré (R-20261111-54). Présente, le lanceur ne
  # lance plus le conteneur : il dit l'appel que la session doit faire (code 10). Absente : le chemin d'avant. Remplace : rien. Retrait : avec la règle D10.
  if [ -n "$donnees_session" ] && [ -f "$donnees_session/outils-figes/ci_local.sh" ]; then ENVELOPPE=1; fi
  # R-20261111-54 : le fichier géré du bac à sable décide de la forme imprimée (enveloppe ou commande directe) ; le chemin est en dur (aucune variable de contournement : les tests
  # remplacent le chemin dans leur copie du lanceur ; R-20261112-19). Remplace : R-20261110-20 (Q7). Retrait : avec le bac à sable.
  FICHIER_GERE="/Library/Application Support/ClaudeCode/managed-settings.d/50-pmzilla-bac-a-sable.json"
  if [ "$(cd "$(git rev-parse --git-dir 2>/dev/null)" 2>/dev/null && pwd -P)" != "$(cd "$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null && pwd -P)" ]; then
    POSTE_SESSION="worktree"
  fi
  [ -z "${FINISH_LOCK_TOKEN:-}" ] || refus_session FINISH_LOCK_TOKEN "FINISH_LOCK_TOKEN posée, lancement refusé (réservée aux scripts de fin de l'auteur)"
  [ -z "${DBTEST_PORT:-}" ] || refus_session DBTEST_PORT "DBTEST_PORT posée, lancement refusé (la base jetable reste à l'auteur : tools/dbtest.sh)"
  [ -z "${PMZILLA_FINISH_LOCK_MAX_AGE:-}" ] || refus_session FINISH_LOCK_MAX_AGE "PMZILLA_FINISH_LOCK_MAX_AGE posée, lancement refusé (elle lèverait le gel d'une fin de branche)"
  # Preuve par le conteneur (tooling-proof-in-container, T1, D3, R-20261102-40) : en session, ni lancement complet ni --branch ; code 6, aucune suite,
  # aucune empreinte écrite ni effacée. Retrait : permanent tant que la CI est le runner. Seuls le complet NU et --branch sont refusés : un --staged
  # qui devient complet passe, depuis T2, par le mode complet du conteneur (D4) et la passe Mac.
  if [ ${#NOMS[@]} -eq 0 ] && [ "$CIBLE" -eq 0 ] && [ "$BRANCHE" -eq 0 ] && [ -z "$MODE" ]; then
    refus_preuve_conteneur conteneur-complet "run_all : lancement complet refusé en session : la preuve passe par le conteneur (bash tools/ci_local.sh run <branche>, puis bash tests/run_all.sh --mac)"
  fi
  if [ "$BRANCHE" -eq 1 ]; then
    refus_preuve_conteneur conteneur-branche "run_all : --branch refusé en session : la preuve passe par le conteneur (bash tools/ci_local.sh run <branche>, puis bash tests/run_all.sh --mac)"
  fi
  # --portable (T2, décision de l'auteur du 2026-11-04, T2-2 (a)) : il ferait tourner des suites portables sur le Mac en session ; refusé, code 6.
  if [ "$MODE" = portable ]; then
    refus_preuve_conteneur conteneur-portable "run_all : --portable refusé en session : la preuve passe par le conteneur (bash tools/ci_local.sh run <branche>, puis bash tests/run_all.sh --mac)"
  fi
fi

# --branch (targeted-suites-admission, D2) : une branche de travail et un worktree propre, sinon code 2 avant toute garde, toute suite et toute empreinte.
if [ "$BRANCHE" -eq 1 ]; then
  branche_courante=$(git symbolic-ref -q --short HEAD 2>/dev/null) || branche_courante=""
  etat_worktree=$(git status --porcelain 2>/dev/null); code_etat=$?
  if [ -z "$branche_courante" ] || [ "$branche_courante" = main ] || [ "$code_etat" -ne 0 ] || [ -n "$etat_worktree" ]; then
    echo "run_all : --branch exige une branche de travail et un worktree propre"
    exit 2
  fi
fi

# Gel pendant une fin de branche (multi-session-piloting, D7, rendu ciblé par autonomous-trains-merge, D18) : lecture seule du verrou du dossier Git
# commun de la racine, par la règle unique de tools/finish_lock.py (freezes(), appelée par `refuse --protected` : le lancement écrit main, le dossier
# d'exécution ou la liste prête quand la tête de la racine n'est pas une branche de travail). Aucune règle de gel propre au lanceur.
# Remplace : la lecture du verrou par le lanceur lui-même (gel général). Retrait : permanent. Un module de lecture introuvable, ou une réponse
# inattendue, vaut « gelé » tant qu'un dossier de verrou existe (échec fermé).
GEL_COMMUN=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)   # vide hors dépôt Git (faux dépôt des tests)
if [ -n "$GEL_COMMUN" ] && [ -d "$GEL_COMMUN/pmzilla-fin-en-cours" ]; then
  GEL_RACINE=$(git rev-parse --show-toplevel 2>/dev/null) || GEL_RACINE=$PWD
  GEL_SORTIE=$(python3 -I -B "$LANCEUR_DIR/../tools/finish_lock.py" refuse --common "$GEL_COMMUN" --worktree "$GEL_RACINE" --protected 2>/dev/null); GEL_CODE=$?
  case "$GEL_CODE:$GEL_SORTIE" in
    0:perime) echo "run_all : verrou de fin périmé, ignoré" ;;
    0:) ;;
    *) echo "run_all : fin de branche en cours (${GEL_SORTIE:-?}), lancement refusé"
       exit 4 ;;
  esac
fi

# Contrôles d'une suite npm (D9) : le Node trouvé est celui de <dossier>/.node-version, puis node_modules correspond au verrou (tools/npm_lock_check.py,
# sans Node ni réseau). Rend 0 si tout concorde ; sinon 1 avec CAUSE_NPM (« node » ou « verrou »), VERSION_ATTENDUE et VERSION_NODE, ou ECART_NPM (la ligne du contrôle).
CAUSE_NPM=""; ECART_NPM=""; VERSION_ATTENDUE=""; VERSION_NODE=""
controle_npm() {   # dossier
  local dossier=$1
  CAUSE_NPM=""; ECART_NPM=""
  VERSION_ATTENDUE=$(tr -d '[:space:]' < "$dossier/.node-version" 2>/dev/null); VERSION_ATTENDUE=${VERSION_ATTENDUE#v}
  VERSION_NODE=$(node --version 2>/dev/null | tr -d '[:space:]'); VERSION_NODE=${VERSION_NODE#v}
  if [ -z "$VERSION_ATTENDUE" ] || [ "$VERSION_NODE" != "$VERSION_ATTENDUE" ]; then CAUSE_NPM=node; return 1; fi
  ECART_NPM=$(python3 -I -B "$LANCEUR_DIR/../tools/npm_lock_check.py" "$dossier" 2>&1) || { CAUSE_NPM=verrou; return 1; }
  return 0
}
# Arrêt immédiat d'un lancement COMPLET (sans nom de suite ni --portable ni --mac ; un --staged devenu complet compte) dont une suite npm a son dossier
# mais un Node ou un node_modules qui ne conviennent pas : avant la première suite, avant tout effacement d'empreinte, code 7, la commande à lancer.
arret_si_lancement_complet_npm() {
  [ "$SESSION_SPLIT" -eq 0 ] || return 0   # session (T2) : Node et node_modules sont ceux du conteneur, pas du Mac
  [ ${#NOMS[@]} -eq 0 ] && [ -z "$MODE" ] || return 0
  local i=0 dossier
  while [ "$i" -lt "${#NPM_NOM[@]}" ]; do
    dossier=${NPM_DOSSIER[$i]}; i=$((i + 1))
    [ -d "$dossier" ] || continue   # un dossier absent reste l'échec nommé « suite npm absente »
    controle_npm "$dossier" && continue
    if [ "$CAUSE_NPM" = node ]; then
      echo "run_all : dépendances npm à mettre en conformité avant un lancement complet (Node ${VERSION_NODE:-introuvable} au lieu de ${VERSION_ATTENDUE:-?}, fixé par $dossier/.node-version)"
      echo "run_all : choisir cette version de Node, puis lancer : cd $RACINE/$dossier && npm ci"
    else
      echo "run_all : dépendances npm à mettre en conformité avant un lancement complet (node_modules absent ou différent du verrou : $dossier)"
      [ -z "$ECART_NPM" ] || echo "  $ECART_NPM"
      echo "run_all : lancer : cd $RACINE/$dossier && npm ci"
    fi
    echo "run_all : aucune suite lancée, aucune empreinte écrite ni effacée"
    exit 7
  done
  return 0
}

# Session Claude Code, T2 (tooling-proof-in-container, D1, D4, D8 ; R-20261104-7 P3, P5, P6). Aucune suite portable ne tourne sur le Mac : un lancement
# nommé envoie ses suites portables à « tools/ci_local.sh run --travail <suites> » (arbre de travail, aucune preuve), un --staged à « run --index <suites> »
# (arbre de l'index, preuve d'index si vert), un --staged qui devient complet à « run --index » sans suite (mode complet : trois phases) puis toute la passe
# Mac. Les suites de tests/suites_mac.txt tournent ici. Conteneur indisponible (codes 3, 5, 6, 7, 8 du script, ou script introuvable : 127) : code 9, rien n'est
# lancé, écrit ni effacé, pas même les suites propres au Mac. Code 1 du script (rouge) : la partie Mac tourne, le code final est 1. Tout autre code
# (2 usage, 4, interruption…) : rien n'est lancé ni écrit, code 1 et une phrase qui donne le code (T2-3 (b)).
# Le script reçoit un environnement privé de toute variable CI_LOCAL_* présente (liste lue à l'exécution par compgen, aucun nom écrit ici : décision de
# l'auteur R-20261105-7) et le dossier de données du COMPTE (jamais celui de l'appelant).
# Remplace : les lancements nommés et ciblés des suites portables sur le Mac, en session. Retrait : permanent, tant que la CI est le runner.
# Options « -u <nom> » de env pour chaque variable CI_LOCAL_* présente, rangées dans RETRAITS_CI (tableau, éventuellement vide). Servent l'appel du
# conteneur et celui de tools/preuve_arbre.py. Remplace : la liste écrite à la main de cinq noms (R-20261105-7). Retrait : permanent, tant que la session
# lance ces deux appels.
options_retrait_ci() {
  local nom
  RETRAITS_CI=()
  while IFS= read -r nom; do
    if [ -n "$nom" ]; then RETRAITS_CI+=(-u "$nom"); fi
  done < <(compgen -e CI_LOCAL_)
}
# Enveloppe figée présente (bash-sandbox-n2, D10 et D12, tâche 9.1) : le lanceur ne lance NI le script de la CI NI l'enveloppe. Il dit l'appel que la session
# fait elle-même, seul dans son appel Bash. Ligne : « run_all : suites portables à lancer d'abord, seules, par l'enveloppe : /bin/bash --noprofile --norc -p
# <dossier personnel>/.pmzilla-lab/outils-figes/ci_local.sh run <mode> --worktree ~/PMZilla-Lab/worktrees/<n> <suites> » : le chemin de l'enveloppe porte le dossier personnel de la
# base des comptes (R-20261111-48) ; l'argument du worktree garde « ~ » (le dossier du compte, logique ou physique, y est remplacé, jamais écrit).
# Remplace : l'appel du script de la CI par le lanceur en session. Retrait : avec la règle D10 (permanent tant que les sessions tournent sous le bac à sable).
ligne_appel_enveloppe() {   # mode [suite ...]
  local mode=$1 racine_w maison_physique chemin suites=""
  shift
  racine_w=$(git rev-parse --show-toplevel 2>/dev/null) || racine_w=$RACINE
  maison_physique=$(cd "$vrai_home" 2>/dev/null && pwd -P) || maison_physique=$vrai_home
  chemin=$racine_w
  case "$racine_w" in
    "$vrai_home"/*) chemin="~${racine_w#"$vrai_home"}" ;;
    "$maison_physique"/*) chemin="~${racine_w#"$maison_physique"}" ;;
  esac
  [ $# -eq 0 ] || suites=" $*"
  # R-20261111-54 : un seul signal, le fichier géré du bac à sable. Absent : la commande directe de la CI locale (sans --worktree : la session est dans le worktree).
  # Remplace : R-20261110-20 (Q7, deux signaux : la copie figée seule décidait de la forme imprimée). Retrait : avec le bac à sable.
  if [ ! -f "$FICHIER_GERE" ]; then
    echo "run_all : suites portables à lancer d'abord, seules, en commande directe : bash tools/ci_local.sh run $mode$suites"
    return 0
  fi
  # R-20261111-48 : le chemin de l'enveloppe est le dossier personnel de la base des comptes ($vrai_home, getpwuid), jamais `~` ni HOME.
  echo "run_all : suites portables à lancer d'abord, seules, par l'enveloppe : /bin/bash --noprofile --norc -p $vrai_home/.pmzilla-lab/outils-figes/ci_local.sh run $mode --worktree $chemin$suites"
}
# Une ligne verte de la preuve d'index porte-t-elle l'arbre de l'index et couvre-t-elle la demande ? (tools/preuve_arbre.py --index ; le fichier est celui du
# compte, jamais celui de l'appelant, et aucune variable CI_LOCAL_* ne passe). Source unique de cet appel : epilogue_session et session_enveloppe_index.
preuve_index_session() {   # suites séparées par des virgules, ou « complet »
  [ -n "$ARBRE_SESSION" ] && [ -n "$donnees_session" ] || return 1   # dossier du compte introuvable : aucune preuve, jamais le HOME de l'appelant (R-20261105-7)
  options_retrait_ci
  env ${RETRAITS_CI[@]+"${RETRAITS_CI[@]}"} PMZILLA_LAB_DATA="$donnees_session" python3 -I -B "$LANCEUR_DIR/../tools/preuve_arbre.py" \
    --index "$ARBRE_SESSION" --suites "$1" >/dev/null 2>&1
}
# --staged avec l'enveloppe : sans ligne verte pour l'index et les suites portables (ou « complet »), le lanceur dit l'appel « run --index », la phrase
# « aucune empreinte écrite ni effacée », ne lance aucune suite et sort avec le code 10 ; avec elle, il continue (suites du Mac, puis empreinte ciblée).
session_enveloppe_index() {   # complet
  local complet=$1 demande
  [ "$CIBLE" -eq 1 ] || return 0                                    # un lancement nommé dit son appel à la fin (epilogue_session)
  [ "$complet" -eq 1 ] || [ ${#PORTABLES[@]} -gt 0 ] || return 0    # toutes les suites sont propres au Mac : rien à prouver
  if [ "$complet" -eq 1 ]; then demande=complet; else demande=$(IFS=,; printf '%s' "${PORTABLES[*]}"); fi
  if ! preuve_index_session "$demande"; then
    journal_session lancé enveloppe-index   # journalisé avant d'imprimer : une panne du journal s'écrit avant les lignes de D12, qui restent les dernières
    if [ "$complet" -eq 1 ]; then ligne_appel_enveloppe --index; else ligne_appel_enveloppe --index "${PORTABLES[@]}"; fi
    echo "run_all : aucune empreinte écrite ni effacée"
    exit 10
  fi
  [ "$complet" -eq 0 ] || echo "run_all : exécution complète en session : la preuve de l'enveloppe (mode complet), puis toute la passe Mac (${#LISTE_MAC[@]} suite(s) propres au Mac)"
  return 0
}
session_scinder() {
  local nom entree dans complet=0 mode=--travail code
  [ ${#NOMS[@]} -gt 0 ] || complet=1
  SESSION_SPLIT=1
  if [ "$complet" -eq 0 ]; then
    for nom in "${NOMS[@]}"; do
      dans=0
      for entree in ${LISTE_MAC[@]+"${LISTE_MAC[@]}"}; do [ "${entree%%:*}" = "$nom" ] && dans=1; done
      if [ "$dans" -eq 1 ]; then NOMS_MAC+=("$nom"); else PORTABLES+=("$nom"); fi
    done
    if [ "$ENVELOPPE" -eq 1 ]; then
      echo "run_all : suites portables à lancer par l'enveloppe : ${#PORTABLES[@]} ; suites propres au Mac lancées ici : ${#NOMS_MAC[@]}"
    else
      echo "run_all : suites portables envoyées au conteneur : ${#PORTABLES[@]} ; suites propres au Mac lancées ici : ${#NOMS_MAC[@]}"
    fi
  elif [ "$ENVELOPPE" -eq 0 ]; then
    echo "run_all : exécution complète en session : le conteneur (mode complet), puis toute la passe Mac (${#LISTE_MAC[@]} suite(s) propres au Mac)"
  fi
  if [ "$ENVELOPPE" -eq 1 ]; then
    session_enveloppe_index "$complet"   # peut sortir avec le code 10 ; ni le script de la CI ni l'enveloppe ne sont lancés d'ici
  elif [ "$complet" -eq 1 ] || [ ${#PORTABLES[@]} -gt 0 ]; then
    [ "$CIBLE" -eq 0 ] || mode=--index
    if [ -f "$LANCEUR_DIR/../tools/ci_local.sh" ]; then
      options_retrait_ci
      env ${RETRAITS_CI[@]+"${RETRAITS_CI[@]}"} PMZILLA_LAB_DATA="$donnees_session" \
        bash "$LANCEUR_DIR/../tools/ci_local.sh" run "$mode" ${PORTABLES[@]+"${PORTABLES[@]}"}; code=$?
    else
      code=127
    fi
    # Code 8 de tools/ci_local.sh (place libre insuffisante, ci-local-image-prune D6) : sans rapport avec l'ancien code 8 de CE lanceur (retiré) ; chaque
    # script a sa table. Remplace : rien. Retrait : avec le code 8 de tools/ci_local.sh (source de la table ; un écart se voit en « code inattendu (8) »).
    case "$code" in
      3|5|6|7|8|127)
        journal_session refusé conteneur-indisponible
        echo "run_all : conteneur indisponible (code $code) : aucune suite portable lancée ; rien n'est écrit"
        exit 9 ;;
      0|1) ;;
      *)   # T2-3 : usage (2), entrée refusée (4), interruption… le conteneur n'a rien prouvé : rien n'est lancé ici, rien n'est écrit ni effacé
        journal_session refusé conteneur-code-inattendu
        echo "run_all : le script du conteneur a rendu un code inattendu ($code) : aucune suite lancée ; rien n'est écrit"
        exit 1 ;;
    esac
    CONTENEUR_CODE=$code
    journal_session lancé conteneur
  fi
  # Le conteneur a répondu : l'empreinte ciblée précédente est invalidée (comme un lancement ciblé du Mac), puis la partie Mac prend le relais.
  if [ "$CIBLE" -eq 1 ]; then
    EMPREINTE_CIBLEE=$(git rev-parse --git-path pmzilla-run-targeted-ok 2>/dev/null)
    [ -z "$EMPREINTE_CIBLEE" ] || rm -f "$EMPREINTE_CIBLEE"
  fi
  if [ "$complet" -eq 1 ]; then
    NOMS=(); FILTRE_MAC=1
  else
    NOMS=(${NOMS_MAC[@]+"${NOMS_MAC[@]}"})
    [ ${#NOMS[@]} -gt 0 ] || SESSION_RIEN_ICI=1
  fi
}
# Fin d'un lancement de session scindé : l'empreinte ciblée d'un --staged est écrite seulement quand la partie Mac est verte, que l'index n'a pas changé
# depuis le début et qu'une ligne verte de la preuve d'index porte le même arbre et couvre les suites envoyées (tools/preuve_arbre.py --index ; le fichier est
# celui du compte, jamais celui de l'appelant). Aucune suite portable à envoyer : rien à prouver côté conteneur. Sortie : 1 si le conteneur ou la partie Mac sont rouges.
epilogue_session() { # <1 si une suite propre au Mac est rouge>
  local rouge_mac=$1 raison="" arbre_fin code=0 demande_preuve liste_ok=1
  [ "$rouge_mac" -eq 0 ] && [ "$CONTENEUR_CODE" -eq 0 ] || code=1
  if [ "$CIBLE" -eq 1 ]; then
    if [ "$rouge_mac" -ne 0 ]; then
      raison="suites propres au Mac rouges"
    elif [ "$CONTENEUR_CODE" -ne 0 ]; then
      raison="conteneur rouge (code $CONTENEUR_CODE) : sa sortie est plus haut, les lignes ci_passage et ci_local"
    elif [ -z "$ARBRE_SESSION" ]; then
      raison="preuve du conteneur absente pour cet index"
    else
      arbre_fin=$(git write-tree 2>/dev/null) || arbre_fin=""
      if [ "$arbre_fin" != "$ARBRE_SESSION" ]; then
        raison="index modifié pendant le passage"
      elif [ "$FILTRE_MAC" -eq 1 ] || [ ${#PORTABLES[@]} -gt 0 ]; then
        if [ "$FILTRE_MAC" -eq 1 ]; then demande_preuve=complet; else demande_preuve=$(IFS=,; printf '%s' "${PORTABLES[*]}"); fi
        preuve_index_session "$demande_preuve" || liste_ok=0
        [ "$liste_ok" -eq 1 ] || raison="preuve du conteneur absente pour cet index"
      fi
    fi
    if [ -n "$raison" ]; then
      echo "run_all : empreinte ciblée non écrite ($raison)"
    elif [ -n "$EMPREINTE_CIBLEE" ] && printf '%s\n' "$ARBRE_SESSION" > "$EMPREINTE_CIBLEE" 2>/dev/null; then
      echo "run_all : empreinte ciblée écrite (conteneur et Mac) pour l'index ${ARBRE_SESSION:0:12}"
    else
      echo "run_all : empreinte ciblée non écrite (écriture impossible)"
    fi
  fi
  # Enveloppe présente (bash-sandbox-n2, D10 et D12) : un lancement nommé a lancé ses suites du Mac ; les portables restent à la session, qui les lance par
  # l'enveloppe, seule dans son appel. La ligne est imprimée aussi quand une suite du Mac est rouge (le code reste 1) ; sinon le code est 10.
  if [ "$ENVELOPPE" -eq 1 ] && [ "$CIBLE" -eq 0 ] && [ ${#PORTABLES[@]} -gt 0 ]; then
    journal_session lancé enveloppe-travail   # journalisé avant d'imprimer : la ligne d'appel (D12) reste la dernière ligne
    ligne_appel_enveloppe --travail "${PORTABLES[@]}"
    [ "$code" -ne 0 ] || code=10
  fi
  exit "$code"
}

EMPREINTE=$(git rev-parse --git-path pmzilla-run-all-ok 2>/dev/null)   # vide hors dépôt Git (faux dépôt des tests)
EMPREINTE_CIBLEE=$(git rev-parse --git-path pmzilla-run-targeted-ok 2>/dev/null)
ECRIRE_CIBLEE=0
if [ "$CIBLE" -eq 1 ]; then
  selection=$(python3 "$(dirname "$0")/../tools/select_suites.py" --root "$RACINE" 2>&1); code_selection=$?
  printf '%s\n' "$selection"
  if [ "$code_selection" -eq 0 ]; then
    while IFS= read -r nom_suite; do [ -n "$nom_suite" ] && NOMS+=("$nom_suite"); done < <(printf '%s\n' "$selection" | sed -n 's/^select_suites : \([^ ]*\) : .*/\1/p')
    ECRIRE_CIBLEE=1
  elif [ "$code_selection" -ne 3 ]; then
    echo "run_all : le sélecteur a échoué (code $code_selection) : exécution complète"
  fi
  echo
  if [ -n "${CLAUDECODE+x}" ]; then
    # Session (T2) : un --staged qui devient complet (sélecteur en échec, absent, ou exécution complète exigée) a la garde de la racine, du dossier de
    # données et du matin (gardée par T2-1 (a), R-20261104-17), avant tout appel du conteneur et tout effacement d'empreinte ; l'empreinte ciblée précédente n'est effacée que par session_scinder,
    # une fois le conteneur joint (sur le code 9, rien n'est écrit ni effacé).
    [ ${#NOMS[@]} -gt 0 ] || garde_donnees_session
    ARBRE_SESSION=$(git write-tree 2>/dev/null) || ARBRE_SESSION=""
  else
    arret_si_lancement_complet_npm   # un --staged devenu complet : arrêt immédiat avant d'effacer l'empreinte ciblée (code 7)
    [ -n "$EMPREINTE_CIBLEE" ] && rm -f "$EMPREINTE_CIBLEE"           # un lancement ciblé invalide l'empreinte ciblée précédente
  fi
fi
# Session Claude Code (T2, D4) : les suites portables vont au conteneur, seules les suites de tests/suites_mac.txt tournent ici. --portable, --mac et
# --branch (refusé plus haut) ne sont pas scindés.
if [ -n "${CLAUDECODE+x}" ] && [ "$BRANCHE" -eq 0 ] && [ -z "$MODE" ]; then session_scinder; fi
EMPREINTE_BRANCHE=$(git rev-parse --git-path pmzilla-run-branch-ok 2>/dev/null)   # vide hors dépôt Git ; jamais lue par pre-commit ni pre-push
ECRIRE_BRANCHE=0
ARBRE_BRANCHE=""
if [ "$BRANCHE" -eq 1 ]; then
  # Les suites de toute la différence de la branche avec origin/main (targeted-suites-admission, D2, D3), sur le sommet propre (vérifié plus haut).
  selection=$(python3 "$(dirname "$0")/../tools/select_suites.py" --range origin/main...HEAD --root "$RACINE" 2>&1); code_selection=$?
  printf '%s\n' "$selection"
  if [ "$code_selection" -eq 0 ]; then
    while IFS= read -r nom_suite; do [ -n "$nom_suite" ] && NOMS+=("$nom_suite"); done < <(printf '%s\n' "$selection" | sed -n 's/^select_suites : \([^ ]*\) : .*/\1/p')
    ARBRE_BRANCHE=$(git rev-parse 'HEAD^{tree}' 2>/dev/null)
    [ -n "$ARBRE_BRANCHE" ] && ECRIRE_BRANCHE=1
  elif [ "$code_selection" -ne 3 ]; then
    echo "run_all : le sélecteur a échoué (code $code_selection) : exécution complète"
  fi
  echo
  # Exécution complète exigée ou sélecteur en échec : un lancement complet ; en session, --branch est déjà refusé plus haut (R-20261102-40, D3).
  arret_si_lancement_complet_npm
  [ -n "$EMPREINTE_BRANCHE" ] && rm -f "$EMPREINTE_BRANCHE"   # un lancement de branche invalide l'empreinte de branche précédente
fi
arret_si_lancement_complet_npm   # lancement complet : arrêt immédiat avant d'effacer l'empreinte (code 7)
[ "$SESSION_SPLIT" -eq 0 ] && [ ${#NOMS[@]} -eq 0 ] && [ -z "$MODE" ] && [ -n "$EMPREINTE" ] && rm -f "$EMPREINTE"   # un lancement complet invalide l'empreinte précédente (jamais en session : T2)

# Empreinte du Mac (ci-local-runner, D7) : --mac seulement. Au départ, la ligne de l'arbre de HEAD disparaît de pmzilla-run-mac-ok (dossier Git
# commun) : un passage rouge ne laisse aucune preuve pour cet arbre ; l'état propre du worktree est relevé.
FICHIER_MAC=""; ARBRE_MAC=""; PROPRE_MAC=0
if [ "$MODE" = mac ]; then
  ARBRE_MAC=$(git rev-parse --verify -q 'HEAD^{tree}' 2>/dev/null) || ARBRE_MAC=""
  if [ -n "$ARBRE_MAC" ]; then
    COMMUN_MAC=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) && FICHIER_MAC="$COMMUN_MAC/pmzilla-run-mac-ok"
    if [ -n "$FICHIER_MAC" ] && [ -f "$FICHIER_MAC" ] && grep -qx -- "$ARBRE_MAC" "$FICHIER_MAC" 2>/dev/null; then
      ( umask 077; grep -vx -- "$ARBRE_MAC" "$FICHIER_MAC" > "$FICHIER_MAC.tmp.$$" ) 2>/dev/null
      mv "$FICHIER_MAC.tmp.$$" "$FICHIER_MAC" 2>/dev/null || rm -f "$FICHIER_MAC.tmp.$$"
    fi
    [ -n "$(git status --porcelain 2>/dev/null)" ] || PROPRE_MAC=1
  fi
fi

if [ "${PMZILLA_ENTREES_JUGE_CHANGEES:-}" = "1" ]; then
  echo "ATTENTION : PMZILLA_ENTREES_JUGE_CHANGEES=1 : le test des entrées du juge (tests/posture_evals/test_entrees_juge.py) est IGNORÉ."
  echo "            Le commit qui change ces entrées doit le dire dans son message (« Entrées du juge modifiées : … ») ; plan 6.2."
  echo
fi

# Variables de la base (test-speed-2, D2) : hors passage de la base jetable (DBTEST_PORT absent ou vide), aucune suite ne reçoit de variable
# PMZILLA_LAB_DB_* (adresse, port, mots de passe, Trousseau) ; l'environnement du lanceur lui-même ne change pas.
RETRAIT=()
if [ -z "${DBTEST_PORT:-}" ]; then
  while IFS= read -r nom_variable; do
    [ -n "$nom_variable" ] && RETRAIT+=(-u "$nom_variable")
  done < <(compgen -e PMZILLA_LAB_DB_)
  if [ ${#RETRAIT[@]} -gt 0 ]; then
    echo "run_all : variables PMZILLA_LAB_DB_* retirées de l'environnement des suites (la base jetable passe par tools/dbtest.sh)"
  fi
fi

# Suites passées en série après toutes les autres (D20), chacune avec son genre et sa raison ; un test vérifie que chaque entrée nomme
# une suite existante du genre dit. Inventaire complet : annexe B de openspec/changes/test-speed-2/design.md.
EN_SERIE=(
  run_all:python   # lanceur imbriqué sur des racines factices : fenêtres d'une seconde pour des suites lancées par uv, processus sleep à tuer
  dbtest:shell     # signaux (kill -INT du processus lancé, relais SIGINT, #242) : en série par prudence, pas par obligation
)
# Mode de chaque entrée de EN_SERIE (run-all-faster-and-guarded, D2) : « nom:genre:mode », une entrée par ligne de EN_SERIE, mode « chevauche » (peut
# partir pendant la fin de la phase en parallèle, sous les quatre conditions de l'en-tête) ou « seule » (part quand plus rien ne tourne).
# Remplace : rien (avant, toute entrée de EN_SERIE était seule). Retrait : permanent tant que le lanceur a une phase en série. Un test vérifie que
# chaque entrée de EN_SERIE a exactement un mode et que chaque mode nomme une entrée de EN_SERIE.
MODE_SERIE=(
  run_all:python:chevauche   # longue (176 s au 2026-10-27) et presque sans processeur : elle peut partir pendant la queue de la phase en parallèle
  dbtest:shell:seule         # tests de signaux (kill -INT du processus lancé) : seule et en dernier, comme avant
)
# Suites qui ne tournent jamais pendant qu'une entrée « chevauche » démarre (D2) : leurs tests reposent sur des fenêtres de temps courtes, des
# attentes bornées ou des mesures de durée. Une entrée « nom:genre  # raison », la raison obligatoire. Retrait d'une entrée : quand sa suite perd ses
# fenêtres de temps (le change qui le fait cite la suite). La liste est permanente tant que le lanceur a une phase en série. Un test vérifie que
# chaque entrée nomme une suite existante du genre dit et porte sa raison. Candidats de #582 non gardés après lecture de leur en-tête et de leurs
# attentes (task 3.3) : finish_checks, finish_codes (aucune attente, seulement des délais de sécurité de 120 s), pre-push (aucune attente).
SANS_CHEVAUCHEMENT=(
  ci_local:shell             # cas d'interruption : kill -INT puis attente d'une seconde avant la sortie du faux processus
  run_worktree:shell         # fenêtres de 10 s sans pid lues sur l'horloge réelle
  post-commit:shell          # sondage borné du fichier d'appels : 30 tours de 0,1 s
  finish_train:python        # faux runners qui dorment (4 s, 25 s, 30 s) et attendent un fichier d'état en sondant toutes les 0,05 s
  finish_train_fin:python    # attente de 0,2 s et délais de 60 s sur des processus de fin lancés par le test
  finish_train_base:python   # aide commune aide_train de finish_train : faux runners qui dorment, sondage d'un fichier d'état
  finish_train_npm:python    # faux npm qui dort 4 s ou sonde toutes les 0,05 s ; attente du fichier runner-demarre
  finish_train_reprise:python  # aide commune aide_train : faux runners qui dorment ; processus sleep gardé dans un worktree factice
  train_auto:python          # attente de 1,5 s avant d'interrompre un passage, faux git qui dort 6 s sous délai, délais de 2 s qui tuent un groupe de processus sleep 60, sondage toutes les 0,05 s
)

# Le découpage des suites shell en morceaux parallèles (R-139 : tableau MORCEAUX, morceaux_de, SU_MORC, afficher_morceaux, option --chunks de tools/suite_order.py) est retiré
# avec la seule suite qui l'utilisait, finish_branch (B9, finish-single-b7-b9, décisions de l'auteur R-20261105-32 Q2 (b) et R-20261105-33 Q2 bis (a)). Chaque suite
# reçoit toujours `-u FINISH_MORCEAU` (le retrait de la variable de l'appelant reste). Remplace : ce découpage ; retrait : permanent.

voulue() {   # sans nom donné, tout est voulu
  [ "$SESSION_RIEN_ICI" -eq 0 ] || return 1   # session (T2) : toutes les suites nommées sont parties au conteneur, rien ne tourne ici
  [ ${#NOMS[@]} -eq 0 ] && return 0
  for nom in "${NOMS[@]}"; do [ "$nom" = "$1" ] && return 0; done
  return 1
}

SAUTEES_MAC=()
retenue() {   # nom genre : la suite est-elle lancée selon --portable / --mac ? (sans option, toujours) ; note les suites sautées
  local entree dans=1
  [ -z "$MODE" ] && [ "$FILTRE_MAC" -eq 0 ] && return 0
  for entree in ${LISTE_MAC[@]+"${LISTE_MAC[@]}"}; do [ "$entree" = "$1:$2" ] && dans=0; done
  if [ "$FILTRE_MAC" -eq 1 ]; then return $dans; fi   # T2 : toute la passe Mac d'un --staged complet de session, sans l'empreinte Mac
  if [ "$MODE" = mac ]; then return $dans; fi
  [ "$dans" -eq 0 ] && { SAUTEES_MAC+=("$1:$2"); return 1; }
  return 0
}

en_serie() {   # nom genre : la suite est-elle dans EN_SERIE ?
  local entree
  for entree in "${EN_SERIE[@]}"; do
    entree=${entree%%#*}; entree=${entree%"${entree##*[! ]}"}
    [ "$entree" = "$1:$2" ] && return 0
  done
  return 1
}

mode_serie() {   # nom genre : le mode (chevauche ou seule) de la suite dans MODE_SERIE ; « seule » sans entrée (jamais de chevauchement par défaut)
  local entree
  for entree in "${MODE_SERIE[@]}"; do
    entree=${entree%%#*}; entree=${entree%"${entree##*[! ]}"}
    case "$entree" in "$1:$2:"*) echo "${entree##*:}"; return ;; esac
  done
  echo seule
}

sans_chevauchement() {   # nom genre : la suite est-elle dans SANS_CHEVAUCHEMENT ?
  local entree
  for entree in "${SANS_CHEVAUCHEMENT[@]}"; do
    entree=${entree%%#*}; entree=${entree%"${entree##*[! ]}"}
    [ "$entree" = "$1:$2" ] && return 0
  done
  return 1
}

# Les suites dans l'ordre déclaré : dossiers Python, puis liste shell. Une suite est la paire (nom, genre).
SU_NOM=(); SU_GENRE=(); SU_CHEMIN=(); SU_INTERP=(); SU_ABSENT=(); SU_SERIE=()
for dossier in tests/*/; do
  nom=$(basename "$dossier")
  ls "$dossier"test_*.py >/dev/null 2>&1 || continue
  voulue "$nom" || continue
  retenue "$nom" python || continue
  SU_NOM+=("$nom"); SU_GENRE+=(python); SU_CHEMIN+=("$dossier"); SU_INTERP+=(""); SU_ABSENT+=(0)
  if en_serie "$nom" python; then SU_SERIE+=(1); else SU_SERIE+=(0); fi
done
indice_shell=0
while [ "$indice_shell" -lt "${#SHELL_CHEMIN[@]}" ]; do   # tests/suites_shell.txt, dans l'ordre du fichier
  chemin=${SHELL_CHEMIN[$indice_shell]}; nom=${SHELL_NOM[$indice_shell]}; interprete=${SHELL_INTERP[$indice_shell]}
  indice_shell=$((indice_shell + 1))
  voulue "$nom" || continue
  retenue "$nom" shell || continue
  SU_NOM+=("$nom"); SU_GENRE+=(shell); SU_CHEMIN+=("$chemin"); SU_INTERP+=("$interprete")
  if [ -f "$chemin" ]; then SU_ABSENT+=(0); else SU_ABSENT+=(1); fi
  if en_serie "$nom" shell; then SU_SERIE+=(1); else SU_SERIE+=(0); fi
done
indice_npm=0   # SUITES_NPM, dans l'ordre de la ligne, après les suites shell
while [ "$indice_npm" -lt "${#NPM_NOM[@]}" ]; do
  nom=${NPM_NOM[$indice_npm]}; dossier=${NPM_DOSSIER[$indice_npm]}
  indice_npm=$((indice_npm + 1))
  voulue "$nom" || continue
  retenue "$nom" npm || continue
  SU_NOM+=("$nom"); SU_GENRE+=(npm); SU_CHEMIN+=("$dossier"); SU_INTERP+=("")
  if [ -d "$dossier" ]; then SU_ABSENT+=(0); else SU_ABSENT+=(1); fi
  if en_serie "$nom" npm; then SU_SERIE+=(1); else SU_SERIE+=(0); fi
done
NB=${#SU_NOM[@]}
if [ "$MODE" = portable ]; then
  liste_sautees="${SAUTEES_MAC[*]+${SAUTEES_MAC[*]}}"
  echo "run_all : suites propres au Mac non lancées : ${#SAUTEES_MAC[@]} (${liste_sautees:-aucune})"
fi

# Dossier de données du lab (tools/lab_paths.sh), lu une fois et seulement quand un fichier en dépend (durées, journal des runners complets).
DONNEES_LAB=""; DONNEES_LAB_LUES=0
lire_donnees_lab() {
  [ "$DONNEES_LAB_LUES" -eq 0 ] || return 0
  DONNEES_LAB_LUES=1
  DONNEES_LAB=$( ( . "$LANCEUR_DIR/../tools/lab_paths.sh" 2>/dev/null && lab_paths_init 2>/dev/null && printf '%s' "$LAB_DATA_FOLDER" ) ) || DONNEES_LAB=""
  return 0
}
# Fichier des durées : RUN_ALL_DURATIONS, sinon (hors racine injectée) mesures/run_all-durees.tsv du dossier de données du lab. Lu avant l'ordre
# de départ (D1), qui s'en sert.
DUREES_FICHIER=""; DUREES_PANNE=""
if [ -n "${RUN_ALL_DURATIONS:-}" ]; then
  DUREES_FICHIER=$RUN_ALL_DURATIONS
elif [ -z "${RUN_ALL_ROOT+x}" ]; then
  lire_donnees_lab
  if [ -n "$DONNEES_LAB" ]; then DUREES_FICHIER="$DONNEES_LAB/mesures/run_all-durees.tsv"; else DUREES_PANNE="dossier de données introuvable"; fi
fi

# Mode de chevauchement de chaque suite (D2) : SU_CHEV vaut 1 pour une entrée en série de mode « chevauche », SU_SANS 1 pour une suite de la liste
# SANS_CHEVAUCHEMENT. RUN_ALL_OVERLAP=0 coupe le chevauchement ; toute autre valeur, ou aucune, le laisse.
SU_CHEV=(); SU_SANS=()
i=0; while [ "$i" -lt "$NB" ]; do
  if [ "${SU_SERIE[$i]}" = 1 ] && [ "$(mode_serie "${SU_NOM[$i]}" "${SU_GENRE[$i]}")" = chevauche ]; then SU_CHEV+=(1); else SU_CHEV+=(0); fi
  if sans_chevauchement "${SU_NOM[$i]}" "${SU_GENRE[$i]}"; then SU_SANS+=(1); else SU_SANS+=(0); fi
  i=$((i + 1))
done
CHEVAUCHEMENT=1
[ "${RUN_ALL_OVERLAP-}" != 0 ] || CHEVAUCHEMENT=0
MAX_CHEVAUCHEMENT=$(( TACHES / 2 )); [ "$MAX_CHEVAUCHEMENT" -ge 1 ] || MAX_CHEVAUCHEMENT=1   # au plus la moitié des tâches, au moins une

# Journal des runners complets (D4) : RUN_ALL_RUNS_JOURNAL, sinon journal/run-all-complets.tsv du dossier de données du compte en session, du lab
# hors session ; sur une racine injectée, rien sans la variable. Les entrées de présence sont dans le dossier voisin run-all-presence/.
JOURNAL_COMPLETS=""
if [ -n "${RUN_ALL_RUNS_JOURNAL:-}" ]; then
  JOURNAL_COMPLETS=$RUN_ALL_RUNS_JOURNAL
elif [ -z "${RUN_ALL_ROOT+x}" ]; then
  if [ -n "${CLAUDECODE+x}" ]; then
    [ -z "${donnees_session:-}" ] || JOURNAL_COMPLETS="$donnees_session/journal/run-all-complets.tsv"
  else
    lire_donnees_lab
    [ -z "$DONNEES_LAB" ] || JOURNAL_COMPLETS="$DONNEES_LAB/journal/run-all-complets.tsv"
  fi
fi
# Sortie des suites rouges (R-20261101-01) : RUN_ALL_RED_DIR, sinon suites-rouges/ du dossier de données du compte en session, du lab hors session ;
# sur une racine injectée, rien sans la variable.
ROUGES_DIR=""
# Préfixe d'affichage du fichier gardé (le chemin absolu contient le nom du compte, jamais imprimé) : « ~/.pmzilla-lab/suites-rouges/ » en session
# (dossier du compte), vide sinon (hors session, racine injectée, RUN_ALL_RED_DIR) : le nom du fichier seul.
ROUGES_AFFICHE=""
if [ -n "${RUN_ALL_RED_DIR:-}" ]; then
  ROUGES_DIR=$RUN_ALL_RED_DIR
elif [ -z "${RUN_ALL_ROOT+x}" ]; then
  if [ -n "${CLAUDECODE+x}" ]; then
    if [ -n "${donnees_session:-}" ]; then ROUGES_DIR="$donnees_session/suites-rouges"; ROUGES_AFFICHE="~/.pmzilla-lab/suites-rouges/"; fi
  else
    lire_donnees_lab
    if [ -n "$DONNEES_LAB" ]; then
      ROUGES_DIR="$DONNEES_LAB/suites-rouges"   # hors session : le nom du fichier seul est affiché (un seul appel au dossier du compte dans ce lanceur)
    fi
  fi
fi
PRESENCE_DIR=""
[ -z "$JOURNAL_COMPLETS" ] || PRESENCE_DIR="$(dirname "$JOURNAL_COMPLETS")/run-all-presence"

# Ordre de départ : avec une seule tâche, l'ordre déclaré ; avec plusieurs, les suites en parallèle (sans mesure d'abord, puis la plus longue
# estimée d'abord, D1), puis les suites en série dans l'ordre déclaré.
DEPART=()
if [ "$TACHES" -le 1 ]; then
  i=0; while [ "$i" -lt "$NB" ]; do DEPART+=("$i"); i=$((i + 1)); done
else
  LIGNE_ORDRE=""; ordre_calcule=0
  if [ -n "$DUREES_FICHIER" ] || [ -n "$DUREES_PANNE" ]; then
    LIGNE_ORDRE="run_all : ordre de départ déclaré (durées indisponibles)"   # sans durées utilisables (fichier absent, illisible, vide, outil muet)
    if [ -z "$DUREES_PANNE" ] && [ -f "$LANCEUR_DIR/../tools/suite_order.py" ]; then
      estimations_suites=$(python3 -I -B "$LANCEUR_DIR/../tools/suite_order.py" --durations "$DUREES_FICHIER" 2>/dev/null); code_estimations=$?
      if [ "$code_estimations" -eq 0 ]; then
        ordre_brut=$( { printf '%s\n' "$estimations_suites" | awk '{ print "E\t" $0 }'
                        i=0; while [ "$i" -lt "$NB" ]; do
                          [ "${SU_SERIE[$i]}" = 0 ] && printf 'S\t%s\t%s:%s\n' "$i" "${SU_NOM[$i]}" "${SU_GENRE[$i]}"
                          i=$((i + 1))
                        done; } \
          | awk -F'\t' '$1 == "E" { est[$2] = $3; next }
                        $1 == "S" { if ($3 in est) printf "1\t%d\t%d\t%s\n", 100000000 - int(est[$3] * 10 + 0.5), $2, $3; else printf "0\t0\t%d\t%s\n", $2, $3 }' \
          | sort -t $'\t' -k1,1n -k2,2n -k3,3n )
        while IFS= read -r i; do [ -n "$i" ] && DEPART+=("$i"); done <<< "$(printf '%s\n' "$ordre_brut" | cut -f3)"
        compte_mesures=$(printf '%s\n' "$ordre_brut" | awk -F'\t' 'NF == 4 && !vu[$4]++ { if ($1 == 1) k++; else u++ } END { printf "%d %d", k, u }')
        set -- $compte_mesures
        LIGNE_ORDRE="run_all : ordre de départ selon les durées mesurées ($1 suites mesurées, $2 sans mesure)"
        ordre_calcule=1
      fi
    fi
  fi
  if [ "$ordre_calcule" -eq 0 ]; then
    i=0; while [ "$i" -lt "$NB" ]; do
      [ "${SU_SERIE[$i]}" = 0 ] && DEPART+=("$i")
      i=$((i + 1))
    done
  fi
  liste_serie=""
  i=0; while [ "$i" -lt "$NB" ]; do
    if [ "${SU_SERIE[$i]}" = 1 ]; then DEPART+=("$i"); liste_serie="${liste_serie:+$liste_serie, }${SU_NOM[$i]}"; fi
    i=$((i + 1))
  done
  echo "run_all : $TACHES suites à la fois, puis en série : ${liste_serie:-aucune}"
  if [ "$CHEVAUCHEMENT" -eq 1 ]; then
    liste_chevauche=""; liste_sans=""
    i=0; while [ "$i" -lt "$NB" ]; do
      case ", $liste_chevauche, " in *", ${SU_NOM[$i]}, "*) ;; *) [ "${SU_CHEV[$i]}" = 1 ] && liste_chevauche="${liste_chevauche:+$liste_chevauche, }${SU_NOM[$i]}" ;; esac
      case ", $liste_sans, " in *", ${SU_NOM[$i]}, "*) ;; *) [ "${SU_SANS[$i]}" = 1 ] && liste_sans="${liste_sans:+$liste_sans, }${SU_NOM[$i]}" ;; esac
      i=$((i + 1))
    done
    echo "run_all : chevauchement de la phase en série : ${liste_chevauche:-aucune} ; jamais avec : ${liste_sans:-aucune}"
  else
    echo "run_all : chevauchement coupé (RUN_ALL_OVERLAP=0)"
  fi
  [ -z "$LIGNE_ORDRE" ] || echo "$LIGNE_ORDRE"
fi

RUN=$(mktemp -d "${TMPDIR:-/tmp}/pmzilla-suites.XXXXXX") || { echo "run_all : dossier temporaire impossible"; exit 2; }
RUNNING=(); WRAP=()

# Présence et journal des runners complets (run-all-faster-and-guarded, D4). Aucune de ces fonctions ne change le code, les lignes de suite ni les
# empreintes : une panne est dite en une ligne (PANNE_JOURNAL), jamais plus.
GENRE=""; DEBUT_TOTAL=""; DATE_DEBUT=""; PRESENCE=""; PANNE_JOURNAL=""
AUTRES_MAX=0; AUTRES_GENRES=""; CONCURRENT=0; CHARGE_MAX=""
presence_creer() {   # genre : l'entrée journal/run-all-presence/<pid>, retirée à la sortie et sur interruption
  [ -n "$PRESENCE_DIR" ] || return 0
  # Tâche 9.4 : en session, le dossier du compte peut être refusé en écriture (bac à sable) ; une ligne, jamais un changement de code. Hors session, comme avant.
  ( umask 077; mkdir -p "$PRESENCE_DIR" ) 2>/dev/null || { [ -z "${CLAUDECODE+x}" ] || dire_panne_session; return 0; }
  if printf '%s\n' "$1" > "$PRESENCE_DIR/$$" 2>/dev/null; then PRESENCE="$PRESENCE_DIR/$$"; else [ -z "${CLAUDECODE+x}" ] || dire_panne_session; fi
  return 0
}
presence_retirer() {
  [ -z "$PRESENCE" ] || rm -f "$PRESENCE" 2>/dev/null
  return 0
}
descend_de_ce_lanceur() {   # pid : 0 si ce processus descend de ce lanceur (chaîne des parents lue par ps), 1 sinon ou si la chaîne est illisible
  local p=$1 pp profondeur=0
  while [ "$profondeur" -lt 32 ]; do
    pp=$(ps -o ppid= -p "$p" 2>/dev/null) || return 1
    pp=${pp//[[:space:]]/}
    case "$pp" in ''|*[!0-9]*) return 1 ;; esac
    [ "$pp" = "$$" ] && return 0
    [ "$pp" -le 1 ] && return 1
    p=$pp
    profondeur=$((profondeur + 1))
  done
  return 1
}
observer_concurrence() {   # à chaque départ de suite et à la fin d'un lancement complet : les autres lancements vivants (hors ce lanceur et ses descendants), la charge
  [ "$GENRE" = complet ] && [ -n "$JOURNAL_COMPLETS" ] || return 0
  local fichier pid genre nombre=0 genres="" reste g charge
  if [ -d "$PRESENCE_DIR" ]; then
    for fichier in "$PRESENCE_DIR"/*; do
      [ -f "$fichier" ] || continue
      pid=${fichier##*/}
      case "$pid" in ''|*[!0-9]*) continue ;; esac
      [ "$pid" = "$$" ] && continue
      if ! processus_vivant "$pid"; then rm -f "$fichier" 2>/dev/null; continue; fi   # entrée d'un processus mort : ignorée et retirée
      descend_de_ce_lanceur "$pid" && continue
      genre=$(cat "$fichier" 2>/dev/null)
      nombre=$((nombre + 1))
      case ",$genres," in *",$genre,"*) ;; *) genres="${genres:+$genres,}$genre" ;; esac
    done
  fi
  if [ "$nombre" -gt 0 ]; then
    CONCURRENT=1
    [ "$nombre" -le "$AUTRES_MAX" ] || AUTRES_MAX=$nombre
    reste=$genres
    while [ -n "$reste" ]; do
      g=${reste%%,*}
      case "$reste" in *,*) reste=${reste#*,} ;; *) reste="" ;; esac
      case ",$AUTRES_GENRES," in *",$g,"*) ;; *) AUTRES_GENRES="${AUTRES_GENRES:+$AUTRES_GENRES,}$g" ;; esac
    done
  fi
  charge=$(sysctl -n vm.loadavg 2>/dev/null) || charge=""
  if [ -n "$charge" ]; then set -- $charge; charge=${2:-}; else charge=$(cut -d' ' -f1 /proc/loadavg 2>/dev/null) || charge=""; fi
  case "$charge" in ''|*[!0-9.]*) charge="" ;; esac
  if [ -n "$charge" ]; then
    CHARGE_MAX=$(LC_ALL=C awk -v a="$CHARGE_MAX" -v b="$charge" 'BEGIN { if (a == "" || b + 0 > a + 0) print b; else print a }')
  fi
  return 0
}
ecrire_journal() {   # verdict secondes : une ligne au journal des runners complets (purge des lignes de plus d'un an) ; panne : PANNE_JOURNAL
  [ "$GENRE" = complet ] && [ -n "$JOURNAL_COMPLETS" ] || return 0
  local limite tmp contexte concurrence charge=""
  observer_concurrence
  if [ -n "${CLAUDECODE+x}" ]; then contexte=session; elif [ -n "${FINISH_LOCK_TOKEN:-}" ]; then contexte=fin; else contexte=auteur; fi
  concurrence=seul; [ "$CONCURRENT" -eq 0 ] || concurrence=concurrent
  [ -z "$CHARGE_MAX" ] || charge=$(LC_ALL=C awk -v c="$CHARGE_MAX" 'BEGIN { printf "%.1f", c }')
  if ! ( umask 077; mkdir -p "$(dirname "$JOURNAL_COMPLETS")" ) 2>/dev/null; then PANNE_JOURNAL="écriture impossible"; return 0; fi
  limite=$(date -v-365d +%Y-%m-%d 2>/dev/null || date -d '365 days ago' +%Y-%m-%d 2>/dev/null) || limite=""
  # Purge : seulement si la première ligne de données a plus d'un an (les lignes sont dans l'ordre du temps) ; sinon le fichier n'est pas réécrit.
  premiere=""
  [ -f "$JOURNAL_COMPLETS" ] && premiere=$(awk -F'\t' 'NR == 2 { print substr($1, 1, 10); exit }' "$JOURNAL_COMPLETS" 2>/dev/null)
  if [ -n "$premiere" ] && [ -n "$limite" ] && [[ "$premiere" < "$limite" ]]; then
    tmp="$JOURNAL_COMPLETS.$$"
    awk -F'\t' -v limite="$limite" 'NR == 1 || substr($1, 1, 10) >= limite' "$JOURNAL_COMPLETS" > "$tmp" 2>/dev/null \
      && mv -f "$tmp" "$JOURNAL_COMPLETS" 2>/dev/null || rm -f "$tmp" 2>/dev/null
  fi
  if [ ! -s "$JOURNAL_COMPLETS" ]; then
    printf 'debut\tfin\tsecondes\tverdict\tcontexte\tposte\ttaches\tsuites\tconcurrence\tautres_max\tautres_genres\tcharge_max\n' >> "$JOURNAL_COMPLETS" 2>/dev/null \
      || { PANNE_JOURNAL="écriture impossible"; return 0; }
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$DATE_DEBUT" "$(date +%Y-%m-%dT%H:%M:%S)" "$2" "$1" "$contexte" "$POSTE" "$TACHES" \
    "${suites:-0}" "$concurrence" "$AUTRES_MAX" "$AUTRES_GENRES" "$charge" >> "$JOURNAL_COMPLETS" 2>/dev/null || PANNE_JOURNAL="écriture impossible"
  return 0
}

# Arrête les suites en cours : TERM puis KILL sur le groupe de chacune et sur son chien de garde.
arreter_suites() {
  local k=0 i pid garde
  while [ "$k" -lt "${#RUNNING[@]}" ]; do
    i=${RUNNING[$k]}
    pid=$(cat "$RUN/pid.$i" 2>/dev/null); garde=$(cat "$RUN/garde.$i" 2>/dev/null)
    [ -n "$garde" ] && kill -TERM -- "-$garde" >/dev/null 2>&1
    kill -TERM "${WRAP[$i]}" >/dev/null 2>&1
    [ -n "$pid" ] && kill -TERM -- "-$pid" >/dev/null 2>&1
    k=$((k + 1))
  done
  sleep 1
  k=0
  while [ "$k" -lt "${#RUNNING[@]}" ]; do
    i=${RUNNING[$k]}
    pid=$(cat "$RUN/pid.$i" 2>/dev/null); garde=$(cat "$RUN/garde.$i" 2>/dev/null)
    [ -n "$garde" ] && kill -KILL -- "-$garde" >/dev/null 2>&1
    kill -KILL "${WRAP[$i]}" >/dev/null 2>&1
    [ -n "$pid" ] && kill -KILL -- "-$pid" >/dev/null 2>&1
    k=$((k + 1))
  done
}
interrompre() {   # signal : arrêt des suites, nettoyage, sortie par le signal reçu (comme un lanceur interrompu d'avant)
  trap '' INT TERM
  arreter_suites
  # Un lancement complet interrompu écrit sa ligne de journal (verdict « interrompu ») ; une panne du journal n'y change rien.
  if [ "$GENRE" = complet ] && [ -n "$DEBUT_TOTAL" ]; then ecrire_journal interrompu "$(duree_point $(( $(horloge) - DEBUT_TOTAL )))"; fi
  rm -rf "$RUN"
  presence_retirer
  trap - EXIT; trap - "$1"
  kill -s "$1" $$
}
trap 'rm -rf "$RUN"; presence_retirer' EXIT
trap 'interrompre INT' INT
trap 'interrompre TERM' TERM

total=0; ignores=0; suites=0; echecs=0; echouees=(); sautes_python=0; sautes_shell=0; sautes_npm=0; npm_lancees=0
ligne() { printf "%-22s %5s tests · %s\n" "$1" "$2" "$3"; }

# Sortie des suites rouges gardée (R-20261101-01, Q136 (a)) : le texte de chaque suite rouge est accumulé ici, puis écrit une fois en fin de passage
# rouge (ecrire_rouges). Aucune valeur sensible n'est ajoutée : la sortie que la suite a produite, sous son nom, son verdict, la date et le mode.
ROUGES_TEXTE=""
garder_rouge() {   # étiquette verdict sortie
  [ -n "$ROUGES_DIR" ] || return 0
  ROUGES_TEXTE="$ROUGES_TEXTE=== $1 : $2"$'\n'"$3"$'\n\n'
  return 0
}

# Mesures (change test-speed, D1 à D4). Horloge en millisecondes par perl (Time::HiRes), à défaut les secondes entières du shell.
horloge() {
  local t
  t=$(perl -MTime::HiRes=time -e 'printf "%d\n", time() * 1000' 2>/dev/null) || t=""
  case "$t" in ''|*[!0-9]*) t=$(( $(date +%s) * 1000 )) ;; esac
  printf '%s' "$t"
}
duree() { printf '%d,%d' $(( $1 / 1000 )) $(( ($1 % 1000) / 100 )); }          # 12,3 (virgule décimale, pour l'affichage)
duree_point() { printf '%d.%d' $(( $1 / 1000 )) $(( ($1 % 1000) / 100 )); }    # 12.3 (point décimal, pour le fichier)
DEBUT_TOTAL=$(horloge)
DATE_DEBUT=$(date +%Y-%m-%dT%H:%M:%S)
IDENTIFIANT="$DATE_DEBUT-$$"
if [ "$SESSION_SPLIT" -eq 1 ]; then GENRE="filtré"; [ "$CIBLE" -eq 0 ] || GENRE="ciblé"   # session (T2) : jamais « complet » (ni journal des runners complets)
elif [ "$CIBLE" -eq 1 ] && [ "$ECRIRE_CIBLEE" -eq 1 ]; then GENRE="ciblé"; elif [ "$BRANCHE" -eq 1 ] && [ "$ECRIRE_BRANCHE" -eq 1 ]; then GENRE="ciblé"; elif [ ${#NOMS[@]} -eq 0 ] && [ -z "$MODE" ]; then GENRE="complet"; else GENRE="filtré"; fi
POSTE="espace"
if [ "$(cd "$(git rev-parse --git-dir 2>/dev/null)" 2>/dev/null && pwd -P)" != "$(cd "$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null && pwd -P)" ]; then POSTE="worktree"; fi
presence_creer "$GENRE"   # ce lancement est présent pour les lancements complets en cours (D4), jusqu'à sa sortie
LENTES=""; RANG=0
noter_suite() { # nom étiquette type verdict temps-unittest : liste des plus lentes et ligne du fichier des durées
  RANG=$((RANG + 1))
  LENTES="$LENTES$MS"$'\t'"$RANG"$'\t'"$2"$'\n'
  [ -n "$DUREES_FICHIER" ] && [ -z "$DUREES_PANNE" ] || return 0
  if [ ! -s "$DUREES_FICHIER" ]; then
    ( umask 077; mkdir -p "$(dirname "$DUREES_FICHIER")" ) 2>/dev/null \
      && printf 'lancement\tidentifiant\tgenre\tposte\tsuite\ttype\tsecondes\tsecondes_unittest\tverdict\traison\n' >> "$DUREES_FICHIER" 2>/dev/null \
      || { DUREES_PANNE="écriture impossible"; return 0; }
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t\n' "$DATE_DEBUT" "$IDENTIFIANT" "$GENRE" "$POSTE" "$1" "$3" "$(duree_point "$MS")" "$5" "$4" \
    >> "$DUREES_FICHIER" 2>/dev/null || DUREES_PANNE="écriture impossible"
}

# Corps d'une suite npm (D9), exécuté dans le groupe de processus de la suite : les contrôles dans l'ordre, puis « npm test » dans le dossier de la
# suite, puis le rapporteur. Un échec nommé est une ligne « échec nommé : <message> » et le code 1 ; rien n'est installé ni téléchargé.
corps_suite_npm() {   # dossier nom
  local dossier=$1 nom=$2 sortie_npm code bilan lignes_sauts nb_sauts attendus reussis rates
  if ! controle_npm "$dossier"; then
    if [ "$CAUSE_NPM" = node ]; then
      echo "échec nommé : Node de Mothra différent de la version fixée"
    else
      echo "échec nommé : dépendances npm absentes ou différentes du verrou : $nom (lancer npm ci dans $dossier/)"
      [ -z "$ECART_NPM" ] || echo "  $ECART_NPM"
    fi
    return 1
  fi
  sortie_npm="$TMPDIR/npm-sortie"
  # La sortie de npm test passe par tee : imprimée en direct (un délai dépassé la montre), puis analysée.
  ( cd "$dossier" && npm test ) 2>&1 | tee "$sortie_npm"
  code=${PIPESTATUS[0]}
  # Bilan de node --test : seulement les lignes de RÉSUMÉ du rapporteur, en tête de ligne, formats spec (« ℹ tests 5 », « ℹ pass 3 ») et TAP
  # (« # tests 5 », « # pass 3 ») : un bloc qui commence par « tests », puis les compteurs qui le suivent sans rien entre eux, sommé sur la racine et
  # sur chaque paquet. Une ligne « # pass 9 » imprimée par un test, hors d'un tel bloc, n'est pas comptée.
  bilan=$(awk '$0 !~ /^[ \t]/ && ($1 == "ℹ" || $1 == "#") && NF == 3 && $3 ~ /^[0-9]+$/ {
        if ($2 == "tests") { bloc = 1; vu = 1; n["tests"] += $3; next }
        if (bloc && ($2 == "suites" || $2 == "pass" || $2 == "fail" || $2 == "cancelled" || $2 == "skipped" || $2 == "todo")) { n[$2] += $3; next }
      }
      { bloc = 0 }
      END { printf "%d %d %d %d\n", vu + 0, n["tests"] + 0, n["fail"] + n["cancelled"], n["skipped"] + 0 }' "$sortie_npm")
  set -- $bilan
  if [ "$1" -eq 0 ]; then
    [ "$code" -ne 0 ] || { echo "échec nommé : sortie de npm test sans bilan lisible"; return 1; }
    return "$code"
  fi
  if [ "$2" -eq 0 ]; then
    echo "échec nommé : npm test n'a lancé aucun test"
    return 1
  fi
  reussis=$(( $2 - $3 )); rates=$3; attendus=$4
  # Une ligne « saut : <nom> » par test sauté : les lignes marquées « # SKIP » de la sortie, complétées par le bilan s'il en compte davantage.
  lignes_sauts=$(awk '/^[[:space:]]*(ℹ|#)/ { next }
    /# SKIP/ { l = $0; sub(/[[:space:]]*# SKIP.*$/, "", l); sub(/^[[:space:]]*/, "", l); sub(/^(not )?ok [0-9]+ - /, "", l)
               if (match(l, /^[^ ]+ /) && substr(l, 1, RLENGTH - 1) !~ /[A-Za-z0-9]/) l = substr(l, RLENGTH + 1)
               sub(/ \([0-9.]+m?s\)$/, "", l); print "saut : " l }' "$sortie_npm")
  nb_sauts=0
  if [ -n "$lignes_sauts" ]; then printf '%s\n' "$lignes_sauts"; nb_sauts=$(printf '%s\n' "$lignes_sauts" | grep -c '^saut :'); fi
  while [ "$nb_sauts" -lt "$attendus" ]; do echo "saut : (test sauté, nom non relevé)"; nb_sauts=$((nb_sauts + 1)); done
  echo "$reussis réussis, $rates échec(s)"
  return "$code"
}

# Lance la suite d'indice $1 en arrière-plan : un processus relais qui met la suite dans son propre groupe de processus (set -m ; pas de
# commande timeout sur le bash 3.2 de macOS) avec un chien de garde : TERM sur le groupe à l'échéance, puis KILL après 2 s. Le relais
# écrit fin.<i> (code, délai dépassé, horloge de début, horloge de fin) quand plus aucun processus de la suite ne reste.
demarrer_suite() {
  local i=$1
  mkdir "$RUN/tmp.$i"
  (
    local debut fin pid garde code delai_depasse=0 drapeau="$RUN/delai.$i"
    debut=$(horloge)
    set -m
    if [ "${SU_GENRE[$i]}" = python ]; then
      # shellcheck disable=SC2086
      env ${RETRAIT[@]+"${RETRAIT[@]}"} -u FINISH_MORCEAU PYTHONDONTWRITEBYTECODE=1 TMPDIR="$RUN/tmp.$i" \
        uv run $DEPS python -W ignore -m unittest discover -s "${SU_CHEMIN[$i]}" >"$RUN/sortie.$i" 2>&1 &
    elif [ "${SU_GENRE[$i]}" = npm ]; then
      # Suite npm (D9) : même relais, même groupe de processus. Les variables de la base retirées par RETRAIT (paires « -u NOM ») le sont ici par unset ;
      # npm ne contacte aucun registre (offline), ne vérifie rien en ligne et n'écrit aucune notice.
      (
        for mot_retrait in ${RETRAIT[@]+"${RETRAIT[@]}"}; do [ "$mot_retrait" = -u ] || unset "$mot_retrait"; done
        # Les variables de connexion du serveur de Mothra (MOTHRA_DB_*) ne passent, comme celles du lab, que dans le passage de la base jetable.
        if [ -z "${DBTEST_PORT:-}" ]; then
          for mot_retrait in $(compgen -e MOTHRA_DB_); do unset "$mot_retrait"; done
        fi
        unset FINISH_MORCEAU
        export PYTHONDONTWRITEBYTECODE=1 TMPDIR="$RUN/tmp.$i" npm_config_offline=true npm_config_audit=false npm_config_fund=false \
               npm_config_update_notifier=false npm_config_progress=false NO_COLOR=1 NODE_DISABLE_COLORS=1
        corps_suite_npm "${SU_CHEMIN[$i]}" "${SU_NOM[$i]}"
      ) >"$RUN/sortie.$i" 2>&1 &
    else
      env ${RETRAIT[@]+"${RETRAIT[@]}"} -u FINISH_MORCEAU PYTHONDONTWRITEBYTECODE=1 TMPDIR="$RUN/tmp.$i" \
        "${SU_INTERP[$i]}" "${SU_CHEMIN[$i]}" >"$RUN/sortie.$i" 2>&1 &
    fi
    pid=$!
    printf '%s' "$pid" > "$RUN/pid.$i"
    # Au délai, avant l'arrêt : une ligne par processus encore vivant du groupe (5 au plus), ajoutée à la sortie de la suite. Diagnostic
    # seulement, aucun refus (R-20261030-22 et -23, blocage de convert_books du 2026-10-30). Pas de pile native : elle noierait la sortie
    # de la suite que le détail d'échec doit encore montrer.
    ( sleep "$DELAI"; : >"$drapeau"
      { vivants=$(pgrep -g "$pid" 2>/dev/null | head -5)
        [ -n "$vivants" ] && ps -o pid=,ppid=,stat=,etime=,command= -p "$(printf '%s' "$vivants" | tr '\n' ',')" 2>/dev/null | sed 's/^/run_all : vivant au délai : /'
      } >>"$RUN/sortie.$i" 2>/dev/null
      kill -TERM -- "-$pid"; sleep 2; kill -KILL -- "-$pid" ) >/dev/null 2>&1 &
    garde=$!
    printf '%s' "$garde" > "$RUN/garde.$i"
    set +m
    { wait "$pid"; code=$?; } 2>/dev/null
    if [ -f "$drapeau" ]; then
      delai_depasse=1
      { wait "$garde"; } 2>/dev/null   # le chien de garde finit son KILL : plus aucun processus de la suite
    else
      kill -TERM -- "-$garde" >/dev/null 2>&1
      { wait "$garde"; } 2>/dev/null
      kill -KILL -- "-$pid" >/dev/null 2>&1   # descendants éventuels restés après la fin normale
    fi
    fin=$(horloge)
    printf '%s %s %s %s\n' "$code" "$delai_depasse" "$debut" "$fin" > "$RUN/fin.$i.ecrit"
    mv "$RUN/fin.$i.ecrit" "$RUN/fin.$i"
  ) &
  WRAP[$i]=$!
}

# Liste complète des échecs d'une suite rouge (test-speed, idée #525), avant l'extrait de fin : genre et sortie de la suite. Python : chaque ligne
# « FAIL: » ou « ERROR: » avec la première ligne d'exception qui la suit ; shell : les lignes « ECHEC », « ÉCHEC » ou « not ok » de son bilan.
# Rien que ce que la suite imprime déjà ; rien d'imprimé s'il n'y en a aucune.
liste_echecs() {
  local liste
  if [ "$1" = python ]; then
    liste=$(printf '%s\n' "$2" | awk '
      /^(FAIL|ERROR): / { print "    " $0; attente = 1; next }
      /^(=====|-----)/ { next }
      attente && /^[^ \t]/ && !/^(Traceback|Ran |During handling|The above exception|OK|FAILED)/ { print "        " $0; attente = 0 }')
  else
    liste=$(printf '%s\n' "$2" | grep -E '^(ECHEC|ÉCHEC|not ok)' | sed 's/^/    /')
  fi
  [ -n "$liste" ] || return 0
  echo "    Tous les échecs de la suite :"
  printf '%s\n' "$liste"
}

# Affiche la ligne de la suite d'indice $1 (sa suite et toutes les précédentes ont fini) et compte son résultat.
afficher_suite() {
  local i=$1 nom genre etiquette code delai_depasse debut fin n temps_unittest bilan reussis rates
  nom=${SU_NOM[$i]}; genre=${SU_GENRE[$i]}
  if [ "$genre" = python ]; then etiquette=$nom; elif [ "$genre" = npm ]; then etiquette="$nom (npm)"; else etiquette="$nom (shell)"; fi
  if [ "${SU_ABSENT[$i]}" = 1 ]; then
    if [ "$genre" = npm ]; then
      ligne "$etiquette" "?" "ÉCHEC : suite npm absente : $nom"
      echouees+=("$nom (suite npm absente)")
    else
      ligne "$etiquette" "?" "ÉCHEC : script listé mais absent : ${SU_CHEMIN[$i]}"
      garder_rouge "$etiquette" "script absent" ""
      echouees+=("$nom (${SU_CHEMIN[$i]} absent)")
    fi
    suites=$((suites + 1)); echecs=$((echecs + 1))
    return
  fi
  [ "$genre" != npm ] || npm_lancees=$((npm_lancees + 1))
  read -r code delai_depasse debut fin < "$RUN/fin.$i"
  MS=$(( fin - debut )); [ "$MS" -ge 0 ] || MS=0; DUREE_TXT=$(duree "$MS")
  sortie=$(cat "$RUN/sortie.$i")
  if [ "$delai_depasse" -eq 1 ]; then
    noter_suite "$nom" "$etiquette" "$genre" "délai" ""
    ligne "$etiquette" "?" "ÉCHEC : délai dépassé ($DELAI s) · $DUREE_TXT s"
    printf '%s\n' "$sortie" | tail -30 | sed 's/^/    /'
    garder_rouge "$etiquette" "ÉCHEC : délai dépassé ($DELAI s)" "$sortie"
    suites=$((suites + 1)); echecs=$((echecs + 1)); echouees+=("$nom (délai dépassé)")
    return
  fi
  if [ "$genre" = python ]; then
    n=$(printf '%s\n' "$sortie" | sed -n 's/^Ran \([0-9][0-9]*\) test.*/\1/p' | tail -1)
    temps_unittest=$(printf '%s\n' "$sortie" | sed -n 's/^Ran [0-9][0-9]* tests\{0,1\} in \([0-9][0-9]*\.[0-9]*\)s.*/\1/p' | tail -1)
    bilan=$(printf '%s\n' "$sortie" | tail -1)
    sautes_python=$((sautes_python + $(printf '%s\n' "$bilan" | sed -n 's/.*skipped=\([0-9][0-9]*\).*/\1/p' | tail -1 | grep . || echo 0)))
    suites=$((suites + 1)); total=$((total + ${n:-0}))
    if [ "$code" -eq 0 ] && [ -n "$n" ]; then
      noter_suite "$nom" "$etiquette" python ok "$temps_unittest"
      ligne "$etiquette" "$n" "$bilan · $DUREE_TXT s"
      [ "$BAVARD" -eq 1 ] && printf '%s\n' "$sortie"
    else
      noter_suite "$nom" "$etiquette" python "échec" "$temps_unittest"
      ligne "$etiquette" "${n:-?}" "ÉCHEC (code $code) : $bilan · $DUREE_TXT s"
      liste_echecs python "$sortie"
      printf '%s\n' "$sortie" | tail -30 | sed 's/^/    /'
      garder_rouge "$etiquette" "ÉCHEC (code $code)" "$sortie"
      echecs=$((echecs + 1)); echouees+=("$nom")
    fi
  else
    reussis=$(printf '%s\n' "$sortie" | sed -n 's/^\([0-9][0-9]*\) réussis, [0-9][0-9]* échec.*/\1/p' | tail -1)
    rates=$(printf '%s\n' "$sortie" | sed -n 's/^[0-9][0-9]* réussis, \([0-9][0-9]*\) échec.*/\1/p' | tail -1)
    n=$(( ${reussis:-0} + ${rates:-0} ))
    sautes_suite=$(printf '%s\n' "$sortie" | grep -c '^saut :')   # une ligne « saut : … » par branche sautée, comptée une fois (skips-visible, D1)
    if [ "$genre" = npm ]; then sautes_npm=$((sautes_npm + sautes_suite)); else sautes_shell=$((sautes_shell + sautes_suite)); fi   # les sauts npm à part (D9)
    mention_sauts=""; mention_sauts_echec=""
    if [ "$sautes_suite" -gt 0 ]; then mention_sauts=" (sautés=$sautes_suite)"; mention_sauts_echec=", sautés=$sautes_suite"; fi
    suites=$((suites + 1)); total=$((total + n))
    echec_nomme=""
    [ "$genre" != npm ] || echec_nomme=$(printf '%s\n' "$sortie" | sed -n 's/^échec nommé : //p' | head -1)   # suite npm : un contrôle a refusé de la lancer
    if [ -n "$echec_nomme" ]; then
      noter_suite "$nom" "$etiquette" "$genre" "échec" ""
      ligne "$etiquette" "?" "ÉCHEC : $echec_nomme · $DUREE_TXT s"
      printf '%s\n' "$sortie" | tail -30 | sed 's/^/    /'
      garder_rouge "$etiquette" "ÉCHEC : $echec_nomme" "$sortie"
      echecs=$((echecs + 1)); echouees+=("$nom")
    elif [ "$code" -eq 0 ] && [ -n "$reussis" ] && [ "${rates:-1}" -eq 0 ]; then
      noter_suite "$nom" "$etiquette" "$genre" ok ""
      ligne "$etiquette" "$n" "OK$mention_sauts · $DUREE_TXT s"
      [ "$BAVARD" -eq 1 ] && printf '%s\n' "$sortie"
    else
      noter_suite "$nom" "$etiquette" "$genre" "échec" ""
      ligne "$etiquette" "$n" "ÉCHEC (code $code, ${rates:-?} échec(s)$mention_sauts_echec) · $DUREE_TXT s"
      liste_echecs shell "$sortie"
      printf '%s\n' "$sortie" | tail -30 | sed 's/^/    /'
      garder_rouge "$etiquette" "ÉCHEC (code $code)" "$sortie"
      echecs=$((echecs + 1)); echouees+=("$nom")
    fi
  fi
}

# Une suite en série peut-elle partir maintenant ? (D2) Toujours quand plus rien ne tourne. Sinon seulement une entrée « chevauche », le
# chevauchement permis, au plus la moitié des tâches (au moins une) en cours, aucune d'elles en série ni dans SANS_CHEVAUCHEMENT. Que toutes les
# suites en parallèle aient démarré tient à l'ordre de départ : les suites en série sont à la fin, la boucle les atteint après la dernière.
serie_peut_partir() {   # indice
  local i=$1 k=0 j
  [ "${#RUNNING[@]}" -gt 0 ] || return 0
  [ "$CHEVAUCHEMENT" -eq 1 ] && [ "${SU_CHEV[$i]}" = 1 ] || return 1
  [ "${#RUNNING[@]}" -le "$MAX_CHEVAUCHEMENT" ] || return 1
  while [ "$k" -lt "${#RUNNING[@]}" ]; do
    j=${RUNNING[$k]}
    [ "${SU_SERIE[$j]}" = 0 ] || return 1
    [ "${SU_SANS[$j]}" = 0 ] || return 1
    k=$((k + 1))
  done
  return 0
}

# Scripts à bloc « # /// script » SUIVIS par Git (tools, tests, .claude/skills) : la sélection du conteneur (git archive de l'étape de préparation de
# ci/Dockerfile, ligne 53, qui est la SOURCE : elle construit l'image) et de la clé de l'image (tools/ci_local.sh, scripts_pep723). Un fichier non
# suivi n'entre ni dans l'image ni dans la clé ; hors dépôt Git (racine factice des tests), la liste est vide. Un test de tests/run_all compare les trois.
scripts_uv_suivis() {
  local f
  git ls-files -- 'tools/*.py' 'tests/*.py' '.claude/skills/*.py' 2>/dev/null | LC_ALL=C sort | while IFS= read -r f; do
    grep -q '^# /// script' "$f" 2>/dev/null && printf '%s\n' "$f"
  done
  return 0
}

# Préparation des environnements uv (R-20261101-104) : voir l'en-tête.
AVERT_PREP=""   # scripts dont la préparation a échoué (avertissement de la ligne TOTAL, R-20261101-106)
preparer_environnements_uv() {
  local script debut fin n=0 sortie_prep code=0 existait
  local scripts_uv=()
  while IFS= read -r script; do
    [ -n "$script" ] && scripts_uv+=("$script")
  done < <(scripts_uv_suivis)
  [ "${#scripts_uv[@]}" -gt 0 ] || return 0
  debut=$(horloge)
  for script in "${scripts_uv[@]}"; do
    existait=0; [ -e "$script.lock" ] && existait=1
    if [ "$existait" -eq 1 ]; then
      sortie_prep=$(uv sync --script "$script" --frozen 2>&1); code=$?
    else
      sortie_prep=$(uv sync --script "$script" 2>&1); code=$?
      rm -f "$script.lock" 2>/dev/null   # verrou créé par la préparation : retiré, l'arbre reste propre
    fi
    n=$((n + 1))
    if [ "$code" -ne 0 ]; then   # avertissement, pas un rouge : les autres scripts sont préparés, aucune suite n'est sautée
      AVERT_PREP="${AVERT_PREP:+$AVERT_PREP, }$script"
      echo "run_all : avertissement : préparation uv en échec : $script (code $code)"
      printf '%s\n' "$sortie_prep" | tail -10 | sed 's/^/    /'
    fi
  done
  fin=$(horloge)
  MS=$(( fin - debut )); [ "$MS" -ge 0 ] || MS=0
  if [ -n "$AVERT_PREP" ]; then
    noter_suite preparation "préparation uv" uv "échec" ""
  else
    noter_suite preparation "préparation uv" uv ok ""
  fi
  echo "run_all : environnements uv préparés : $n script(s) · $(duree "$MS") s"
}
if [ "$TACHES" -gt 1 ] && [ "$NB" -gt 1 ]; then preparer_environnements_uv; fi

# Boucle de planification : terminer, lancer, afficher dans l'ordre déclaré, attendre.
ETAT=()   # 0 à lancer, 1 en cours, 2 fini
i=0; while [ "$i" -lt "$NB" ]; do ETAT+=(0); i=$((i + 1)); done
prochain=0; affiche=0; nb_depart=${#DEPART[@]}
while [ "$affiche" -lt "$NB" ]; do
  restantes=(); k=0
  while [ "$k" -lt "${#RUNNING[@]}" ]; do
    i=${RUNNING[$k]}
    if [ -f "$RUN/fin.$i" ]; then ETAT[$i]=2; else restantes+=("$i"); fi
    k=$((k + 1))
  done
  RUNNING=(); k=0
  while [ "$k" -lt "${#restantes[@]}" ]; do RUNNING+=("${restantes[$k]}"); k=$((k + 1)); done
  while [ "$prochain" -lt "$nb_depart" ] && [ "${#RUNNING[@]}" -lt "$TACHES" ]; do
    i=${DEPART[$prochain]}
    # une suite en série tourne seule, sauf une entrée « chevauche » sous les quatre conditions de D2 (serie_peut_partir)
    if [ "$TACHES" -gt 1 ] && [ "${SU_SERIE[$i]}" = 1 ] && ! serie_peut_partir "$i"; then break; fi
    prochain=$((prochain + 1))
    if [ "${SU_ABSENT[$i]}" = 1 ]; then ETAT[$i]=2; continue; fi
    observer_concurrence
    demarrer_suite "$i"
    ETAT[$i]=1; RUNNING+=("$i")
  done
  while [ "$affiche" -lt "$NB" ] && [ "${ETAT[$affiche]}" = 2 ]; do
    afficher_suite "$affiche"
    affiche=$((affiche + 1))
  done
  [ "$affiche" -lt "$NB" ] || break
  if [ "$TACHES" -eq 1 ] && [ "${#RUNNING[@]}" -eq 1 ]; then
    { wait "${WRAP[${RUNNING[0]}]}"; } 2>/dev/null   # une seule tâche : pas de sondage, la suite finie réveille le lanceur
  else
    sleep 0.1
  fi
done

if [ "$suites" -gt 0 ]; then
  [ -z "$DUREES_PANNE" ] || echo "run_all : durées non enregistrées ($DUREES_PANNE)"
  echo "Suites les plus lentes :"
  printf '%s' "$LENTES" | sort -t $'\t' -k1,1nr -k2,2n | head -10 | while IFS=$'\t' read -r ms_lente rang_lente etiquette_lente; do
    printf '  %s s  %s\n' "$(duree "$ms_lente")" "$etiquette_lente"
  done
  if [ "$npm_lancees" -gt 0 ]; then   # la partie « suites npm » seulement si une suite npm a été lancée (D9) ; sinon la ligne d'avant
    echo "Tests sautés : $((sautes_python + sautes_shell + sautes_npm)) (suites Python $sautes_python, branches shell $sautes_shell, suites npm $sautes_npm)"
  else
    echo "Tests sautés : $((sautes_python + sautes_shell)) (suites Python $sautes_python, branches shell $sautes_shell)"
  fi
fi
echo
if [ "$suites" -eq 0 ]; then
  if [ "$SESSION_SPLIT" -eq 1 ]; then   # session (T2) : rien à lancer sur le Mac (tout est parti au conteneur, ou la liste Mac est vide) : la fin est celle du conteneur
    if [ "$SESSION_RIEN_ICI" -eq 1 ]; then echo "run_all : aucune suite propre au Mac à lancer ici"; else echo "run_all : aucune suite propre au Mac"; fi
    epilogue_session 0
  fi
  if [ "$CIBLE" -eq 0 ] && [ "$BRANCHE" -eq 0 ] && [ ${#NOMS[@]} -gt 0 ]; then   # des noms donnés, aucune suite : code 5 (change light-spec-finish, D11)
    echo "run_all : aucune suite ne correspond aux noms donnés (${NOMS[*]})"
    exit 5
  fi
  echo "Aucune suite trouvée (noms demandés : ${NOMS[*]:-aucun})"
  exit 2
fi
MS_TOTAL=$(( $(horloge) - DEBUT_TOTAL ))
DUREE_TOTALE=$(duree "$MS_TOTAL")
# Journal des runners complets (D4) : écrit après la ligne de total et avant la ligne d'empreinte ; une panne est dite une fois, sans chemin.
journal_du_lancement() {   # verdict : la ligne de journal, puis la phrase de panne éventuelle
  ecrire_journal "$1" "$(duree_point "$MS_TOTAL")"
  [ -z "$PANNE_JOURNAL" ] || echo "run_all : journal des runners complets non écrit ($PANNE_JOURNAL)"
  return 0
}
# Sortie des suites rouges gardée (R-20261101-01) : un fichier par passage rouge, les dix derniers au plus (les plus anciens effacés). Un échec
# d'écriture est dit en une ligne d'avertissement et ne change ni le code de sortie ni les empreintes.
ecrire_rouges() {
  [ -n "$ROUGES_DIR" ] && [ -n "$ROUGES_TEXTE" ] || return 0
  local fichier liste=() f n k=0 repli
  fichier="$ROUGES_DIR/rouge-${DATE_DEBUT//:/}-$$.txt"
  if ! ( umask 077; mkdir -p "$ROUGES_DIR" && printf 'run_all : sortie des suites rouges\nlancement : %s\nmode : %s\n\n%s' "$DATE_DEBUT" "$GENRE" "$ROUGES_TEXTE" > "$fichier" ) 2>/dev/null; then
    rm -f "$fichier" 2>/dev/null
    # Écriture refusée dans le dossier du compte (bac à sable, bash-sandbox-n2, tâche 9.4) : la même sortie va dans le dossier temporaire de la session, pour
    # qu'elle reste lisible pendant la session. Aucun signal du bac n'est lu : l'écriture refusée déclenche elle-même le repli. Ni le code ni les empreintes ne changent.
    # Le repli ne vaut que pour la destination venue du dossier de données (D10 ne vise que suites-rouges/ de ce dossier) : avec RUN_ALL_RED_DIR posée, rien
    # n'est écrit dans le dossier temporaire (revue 10.1 de K4, constat 6).
    if [ -n "${RUN_ALL_RED_DIR:-}" ]; then
      echo "run_all : sortie des suites rouges non gardée (écriture impossible)"
      return 0
    fi
    repli="${TMPDIR:-/tmp}/pmzilla-suites-rouges"
    fichier="$repli/rouge-${DATE_DEBUT//:/}-$$.txt"
    if ( umask 077; mkdir -p "$repli" && printf 'run_all : sortie des suites rouges\nlancement : %s\nmode : %s\n\n%s' "$DATE_DEBUT" "$GENRE" "$ROUGES_TEXTE" > "$fichier" ) 2>/dev/null; then
      echo "run_all : sortie des suites rouges non gardée (écriture impossible) ; copie dans le dossier temporaire de la session : pmzilla-suites-rouges/${fichier##*/}"
      for f in "$repli"/rouge-*.txt; do [ -f "$f" ] && liste+=("$f"); done
      n=${#liste[@]}
      while [ $((n - k)) -gt 10 ]; do rm -f "${liste[$k]}" 2>/dev/null; k=$((k + 1)); done
    else
      rm -f "$fichier" 2>/dev/null
      echo "run_all : sortie des suites rouges non gardée (écriture impossible)"
    fi
    return 0
  fi
  echo "run_all : sortie des suites rouges gardée : ${ROUGES_AFFICHE}${fichier##*/}"
  for f in "$ROUGES_DIR"/rouge-*.txt; do [ -f "$f" ] && liste+=("$f"); done
  n=${#liste[@]}
  while [ $((n - k)) -gt 10 ]; do rm -f "${liste[$k]}" 2>/dev/null; k=$((k + 1)); done
  return 0
}
# Avertissement de la préparation des environnements uv (R-20261101-106) : en fin de ligne TOTAL, vide sans échec de préparation.
SUFFIXE_PREP=""
[ -z "$AVERT_PREP" ] || SUFFIXE_PREP=" · avertissement : préparation uv en échec : $AVERT_PREP"
if [ "$echecs" -gt 0 ]; then
  echo "TOTAL : $total tests dans $suites suites · $echecs suite(s) en échec : ${echouees[*]} · durée totale $DUREE_TOTALE s$SUFFIXE_PREP"
  journal_du_lancement rouge
  ecrire_rouges
  [ "$SESSION_SPLIT" -eq 0 ] || epilogue_session 1   # session (T2) : la raison de l'empreinte non écrite, puis le code 1
  exit 1
fi
echo "TOTAL : $total tests dans $suites suites · tous réussis · durée totale $DUREE_TOTALE s$SUFFIXE_PREP"
journal_du_lancement vert
if [ "$SESSION_SPLIT" -eq 1 ]; then
  epilogue_session 0   # session (T2) : l'empreinte ciblée (D1) ou rien, puis le code ; jamais l'empreinte complète
elif [ "$ECRIRE_BRANCHE" -eq 1 ] && [ -n "$EMPREINTE_BRANCHE" ]; then
  # L'arbre du sommet lu avant les suites (le worktree était propre) et les suites lancées, séparées par des virgules ; ni complète ni ciblée.
  # Revue 2026-10-31, points 7 et 8, puis R-20261031-67 : rien n'est écrit si une suite sélectionnée n'a pas été lancée (comparaison des noms,
  # pas des comptes), si la sélection est vide, ni si l'arbre du sommet a changé ou si le worktree n'est plus propre depuis le départ ; la raison est dite.
  arbre_fin=$(git rev-parse 'HEAD^{tree}' 2>/dev/null); etat_fin=$(git status --porcelain 2>/dev/null); code_etat_fin=$?
  # Revue R-20261031-67 : la décision se prend sur les ensembles de noms (chaque suite sélectionnée a été lancée ; le lanceur est ici vert, donc
  # elle est verte), pas sur les comptes : une suite lancée en plus par le lanceur ne refuse pas, un nom qui lance deux suites non plus.
  # Cette règle remplace le contrôle par comptes de R-20261031-46 (correction 7) ; condition de retrait : permanente tant que --branch existe.
  # Les comptes de la phrase restent informatifs.
  manquantes=""
  for nom_suite in ${NOMS[@]+"${NOMS[@]}"}; do
    lancee=0; k=0
    while [ "$k" -lt "$NB" ]; do
      if [ "${SU_NOM[$k]}" = "$nom_suite" ] && [ "${SU_ABSENT[$k]}" != 1 ]; then lancee=1; break; fi
      k=$((k + 1))
    done
    [ "$lancee" -eq 1 ] || manquantes="${manquantes:+$manquantes, }$nom_suite"
  done
  if [ "${#NOMS[@]}" -eq 0 ]; then
    echo "run_all : empreinte de branche non écrite (aucune suite sélectionnée)"
  elif [ -n "$manquantes" ]; then
    echo "run_all : empreinte de branche non écrite (suites lancées : $suites, suites sélectionnées : ${#NOMS[@]}) ; suites manquantes : $manquantes"
  elif [ "$arbre_fin" != "$ARBRE_BRANCHE" ] || [ "$code_etat_fin" -ne 0 ] || [ -n "$etat_fin" ]; then
    echo "run_all : empreinte de branche non écrite (l'arbre du sommet a changé ou le worktree n'est plus propre)"
  else
    liste_suites=""; for nom_suite in ${NOMS[@]+"${NOMS[@]}"}; do liste_suites="${liste_suites:+$liste_suites,}$nom_suite"; done
    printf '%s\t%s\n' "$ARBRE_BRANCHE" "$liste_suites" > "$EMPREINTE_BRANCHE" && echo "run_all : empreinte de branche écrite (${#NOMS[@]} suite(s))"
  fi
elif [ "$ECRIRE_CIBLEE" -eq 1 ] && [ -n "$EMPREINTE_CIBLEE" ]; then
  arbre=$(git write-tree 2>/dev/null) && printf '%s\n' "$arbre" > "$EMPREINTE_CIBLEE" && echo "Empreinte ciblée de l'index enregistrée : le hook pre-commit l'acceptera sur une branche de travail (pas sur main)."
elif [ ${#NOMS[@]} -eq 0 ] && [ -z "$MODE" ] && [ -n "$EMPREINTE" ]; then
  arbre=$(git write-tree 2>/dev/null) && printf '%s\n' "$arbre" > "$EMPREINTE" && echo "Empreinte de l'index enregistrée : le hook pre-commit acceptera le commit de cet index."
fi
# Empreinte du Mac (D7) : passage vert (on est ici après le total sans échec), worktree propre au départ et à la fin, arbre de HEAD inchangé. Une
# ligne par arbre, lisible par son propriétaire seul, écrite par un fichier temporaire renommé. Jamais lue par pre-commit. Ne change pas le code de sortie.
if [ "$MODE" = mac ]; then
  RAISON_MAC=""
  if [ -z "$ARBRE_MAC" ] || [ -z "$FICHIER_MAC" ]; then RAISON_MAC="hors dépôt Git"
  elif [ "$PROPRE_MAC" -ne 1 ] || [ -n "$(git status --porcelain 2>/dev/null)" ]; then RAISON_MAC="arbre non propre"
  elif [ "$(git rev-parse --verify -q 'HEAD^{tree}' 2>/dev/null)" != "$ARBRE_MAC" ]; then RAISON_MAC="arbre changé pendant le passage"
  elif ( umask 077
         { [ -f "$FICHIER_MAC" ] && grep -vx -- "$ARBRE_MAC" "$FICHIER_MAC"; printf '%s\n' "$ARBRE_MAC"; } > "$FICHIER_MAC.tmp.$$" ) 2>/dev/null \
       && mv "$FICHIER_MAC.tmp.$$" "$FICHIER_MAC" 2>/dev/null; then
    echo "run_all : empreinte Mac écrite pour l'arbre ${ARBRE_MAC:0:12}"
  else
    rm -f "$FICHIER_MAC.tmp.$$" 2>/dev/null
    RAISON_MAC="écriture impossible"
  fi
  [ -z "$RAISON_MAC" ] || echo "run_all : empreinte Mac non écrite ($RAISON_MAC)"
fi
