"""PMZilla Lab : messages de tools/doctor.py par langue (change doctor-command, R-45).

Aucun message ne contient de chemin, de nom de branche ou de modèle (sauf les noms de branches et de tâches affichés dans le
Terminal seulement, par le champ {noms}), ni de secret. Les phrases clés sont celles de la décision D4 du change (design.md).
Un identifiant de contrôle n'est jamais traduit.
"""

CATALOGS = {
    "fr": {
        "ligne": "{check} : {level} : {reason}",
        "niveau_ok": "ok",
        "niveau_warning": "avertissement",
        "niveau_problem": "problème",
        "niveau_skipped": "ignoré",
        "resume_ok": "doctor : tout va bien",
        "resume_warning": "doctor : {n} avertissement(s)",
        "resume_problem": "doctor : {n} problème(s), {m} avertissement(s)",
        "impossible": "doctor : impossible de lancer : {cause}",
        "cause_date": "date du jour illisible",
        "cause_heure": "heure illisible",
        "cause_etat": "fichier d'état non inscriptible",
        "notification": "PMZilla doctor : {n} problème(s) : {checks}",
        # raisons communes
        "raison_not_due": "pas encore dû",
        "raison_not_set_up": "non installé",
        "raison_content_unknown": "dossier de contenu introuvable (PMZILLA_LAB_WORKSPACE ou clone Git du dépôt)",
        "raison_depends": "dépend de {noms}",
        "raison_unknown": "date d'expiration inconnue",
        "raison_not_local": "adresse non locale",
        # db
        "raison_db_ok": "base joignable",
        "raison_db_port_closed": "le port de la base refuse la connexion",
        "raison_db_watch_unreachable": "la veille du jour a noté la base injoignable",
        "raison_db_watch_tables_missing": "la veille du jour a noté les tables absentes",
        # ollama et modèles
        "raison_ollama_ok": "Ollama répond",
        "raison_ollama_down": "Ollama ne répond pas",
        "raison_models_ok": "modèles présents",
        "raison_models_missing": "modèle absent ({noms})",
        # launchd
        "raison_launchd_ok": "{loaded} tâche(s) chargée(s), {not_set_up} non installée(s)",
        "raison_launchd_not_loaded": "tâche installée mais non chargée : {noms}",
        "raison_launchd_none_installed": "aucune tâche installée",
        # watch
        "raison_watch_ok": "la veille du jour est terminée sans erreur",
        "raison_watch_failed": "la veille du jour s'est terminée en échec",
        "raison_watch_missing": "aucune veille aujourd'hui après l'heure prévue",
        "raison_watch_running": "la veille du jour est en cours",
        "raison_watch_interrupted": "passage du jour interrompu",
        "raison_watch_postponed": "veille reportée, nouvel essai dans la journée",
        "raison_watch_missed": "jour manqué : aucun passage terminé avant l'heure limite",
        "raison_watch_record_not_writable": "repère du passage du jour impossible à écrire",
        # backup
        "raison_backup_ok": "sauvegarde du jour complète ({found} dump(s))",
        "raison_backup_missing": "dossier de sauvegarde du jour absent",
        "raison_backup_short": "{found} dump(s) sur {expected}",
        # offsite
        "raison_offsite_ok": "dernière copie hors du Mac il y a {days} jour(s)",
        "raison_offsite_warn_old": "dernière copie hors du Mac il y a {days} jour(s)",
        "raison_offsite_problem_old": "dernière copie hors du Mac il y a {days} jour(s)",
        "raison_offsite_never": "aucune copie hors du Mac réussie depuis l'installation",
        "raison_offsite_not_permitted": "copie hors du Mac refusée par macOS (Operation not permitted) : dernière réussite il y a {days} jour(s)",
        "raison_offsite_incomplete": "copie hors du Mac incomplète d'après le journal : dernière réussite il y a {days} jour(s)",
        # disk
        "raison_disk_ok": "{free_gb} Go libres",
        "raison_disk_low": "{free_gb} Go libres, sous le seuil d'avertissement",
        "raison_disk_critical": "{free_gb} Go libres, sous le seuil critique",
        # jira
        "raison_jira_ok": "jeton valable encore {days} jour(s)",
        "raison_jira_expired": "date d'expiration du jeton dépassée",
        "raison_jira_expiring": "le jeton expire dans {days} jour(s)",
        "raison_jira_unreadable": "date d'expiration illisible ou mal formée",
        # branches
        "raison_branches_ok": "aucune branche ni worktree à ranger",
        "raison_branches_stale": ("{merged_worktrees} worktree(s) fusionné(s), {stale_worktrees} worktree(s) inactif(s), "
                                  "{merged_branches} branche(s) fusionnée(s) non supprimée(s), {prunable} worktree(s) à élaguer, "
                                  "{trial_orphans} copie(s) de séance du jeu d'essai orpheline(s) (posture_evals.py --remove-orphans) : {noms}"),
        # run-worktree
        "raison_run_worktree_ok": "le worktree d'exécution est détaché au sommet de main et propre",
        "raison_run_worktree_wrong_branch": "le worktree d'exécution est sur une branche : il doit être détaché",
        "raison_run_worktree_behind": "le worktree d'exécution est en retard sur main (mise à jour reportée ou refusée)",
        "raison_run_worktree_off_history": "le worktree d'exécution est hors de l'historique de main",
        "raison_run_worktree_dirty": "le worktree d'exécution porte un changement local",
        "raison_run_worktree_missing": "le worktree d'exécution est introuvable",
        # mothra-npm (change mothra-npm-ready, D3)
        "raison_mothra_npm_ok": "Node et node_modules de Mothra conformes au verrou",
        "raison_mothra_npm_no_lock": "pas de verrou npm de Mothra",
        "raison_mothra_npm_node_version": "Node {version} différent de mothra/.node-version ({pinned})",
        "raison_mothra_npm_node_missing": "Node introuvable, mothra/.node-version fixe {pinned}",
        "raison_mothra_npm_node_unpinned": "mothra/.node-version absent : version de Node non vérifiée",
        "raison_mothra_npm_modules_missing": "node_modules absent dans mothra/",
        "raison_mothra_npm_modules_stale": "node_modules périmé : verrou plus récent ou différent",
        # pretooluse (idée 399)
        "raison_pretooluse_ok": "Claude Code est à la version du dernier essai conforme du crochet PreToolUse",
        "raison_pretooluse_claude_missing": "commande claude introuvable",
        "raison_pretooluse_claude_version_unreadable": "version de claude illisible",
        "raison_pretooluse_no_trial": ("aucun essai du crochet PreToolUse enregistré pour Claude Code {version} : "
                                       "lance bash tools/essai_crochet_pretooluse.sh dans le Terminal"),
        "raison_pretooluse_state_unreadable": ("état de l'essai du crochet PreToolUse illisible : "
                                               "relance bash tools/essai_crochet_pretooluse.sh dans le Terminal"),
        "raison_pretooluse_version_changed": ("Claude Code {version}, dernier essai conforme du crochet PreToolUse avec {tried} : "
                                              "relance bash tools/essai_crochet_pretooluse.sh dans le Terminal"),
        "raison_pretooluse_not_read": ("le dernier essai (Claude Code {tried}) n'a pas lu le contexte d'un crochet PreToolUse : "
                                       "reviens à la forme A, PostToolUse (changement de l'entrée seule, design D9 de deny-rules-review)"),
        # ci-container (R-20261103-6, Q9)
        "raison_ci_container_ok": "Colima tourne et l'image de CI de la clé courante existe",
        "raison_ci_container_colima_missing": "commande colima introuvable",
        "raison_ci_container_colima_stopped": "Colima ne tourne pas : lance colima start --cpu 8 --memory 16 dans le Terminal",
        "raison_ci_container_image_absent": ("image de CI absente pour la clé courante : "
                                             "lance bash tools/ci_local.sh up dans le Terminal, depuis le worktree de la branche"),
        "raison_ci_container_image_unreadable": "état de l'image de CI illisible : bash tools/ci_local.sh cle n'a pas répondu",
        # sandbox (change bash-sandbox-n2, design D8) : les lignes du design, caractère pour caractère
        "raison_sandbox_ok": "bac à sable : fichier géré conforme",
        "raison_sandbox_absent": "bac à sable : fichier géré absent (non posé)",
        "raison_sandbox_differs": "bac à sable : fichier géré différent de sa source",
        "raison_sandbox_unprotected": "bac à sable : fichier géré non protégé (propriétaire ou droits)",
        "raison_sandbox_version_low": "bac à sable : version de Claude Code inférieure au minimum",
        "raison_sandbox_frozen_differs": "bac à sable : outil figé différent de son relevé : {noms}",
        "raison_sandbox_claude_missing": "commande claude introuvable",
        "raison_sandbox_claude_version_unreadable": "version de claude illisible",
        # interpreteur_crochets (R-20261108-10)
        "raison_interpreteur_crochets_ok": "interpréteur des crochets conforme (root, inscriptible par root seulement)",
        "raison_interpreteur_crochets_missing": ("interpréteur des crochets absent ou illisible : les crochets risquent de ne plus démarrer ; "
                                                 "vérifie le lien et sa cible avec ls -lL dans le Terminal"),
        "raison_interpreteur_crochets_outside": ("l'interpréteur des crochets pointe hors des CommandLineTools : les crochets risquent de "
                                                 "ne plus démarrer ; vérifie la cible du lien avec ls -lL dans le Terminal"),
        "raison_interpreteur_crochets_owner": ("interpréteur des crochets non détenu par root : les crochets risquent de ne plus démarrer ; "
                                               "vérifie le propriétaire du lien, de sa cible et de leurs dossiers avec ls -ld"),
        "raison_interpreteur_crochets_writable": ("interpréteur des crochets inscriptible par le groupe ou les autres : les crochets risquent "
                                                  "de ne plus démarrer ; vérifie les droits du lien, de sa cible et de leurs dossiers avec ls -ld"),
        "raison_interpreteur_crochets_not_mac": "sans objet hors du Mac",
        # crochet-reference-transaction (R-20261110-42) : la commande de réparation est dans chaque raison de problème, sans chemin
        "raison_crochet_reference_transaction_ok": "crochet reference-transaction installé et conforme",
        "raison_crochet_reference_transaction_no_repo": "dépôt Git introuvable : crochet reference-transaction non vérifié ; lance bash tools/install_hooks.sh --verify dans l'espace de travail",
        "raison_crochet_reference_transaction_source_absent": "fichier suivi tools/hooks/reference-transaction absent ; restaure-le depuis Git, puis lance bash tools/install_hooks.sh dans l'espace de travail",
        "raison_crochet_reference_transaction_wrong_dir": "dossier des hooks inattendu (core.hooksPath ?) ; vérifie-le, puis lance bash tools/install_hooks.sh dans l'espace de travail",
        "raison_crochet_reference_transaction_missing": "crochet reference-transaction non installé ; lance bash tools/install_hooks.sh dans l'espace de travail",
        "raison_crochet_reference_transaction_differs": "crochet reference-transaction différent du lien attendu ou non exécutable ; lance bash tools/install_hooks.sh dans l'espace de travail",
        "raison_module_missing": "module {module} absent",
        # train-auto-plist (R-20261110-14) : la commande de régénération et le rappel sont dans chaque raison de problème, sans chemin
        "raison_train_auto_plist_ok": "modèle launchd du train automatique conforme à celui de train_auto.py plist",
        "raison_train_auto_plist_unreadable": ("modèle launchd du train automatique illisible ; régénère-le avec python3 -I <dossier d'exécution>/tools/train_auto.py plist "
                                               "(python3 3.10 ou plus requis), puis recharge-le dans launchd"),
        "raison_train_auto_plist_python_absent": ("pas de python3 dans le premier dossier du PATH du modèle du train automatique ; régénère-le avec python3 -I "
                                                  "<dossier d'exécution>/tools/train_auto.py plist (python3 3.10 ou plus requis), puis recharge-le dans launchd"),
        "raison_train_auto_plist_python_old": ("python3 du modèle du train automatique plus ancien que 3.10 ou version illisible ; régénère-le avec python3 -I "
                                               "<dossier d'exécution>/tools/train_auto.py plist (python3 3.10 ou plus requis), puis recharge-le dans launchd"),
        "raison_train_auto_plist_different": ("modèle du train automatique différent de celui de train_auto.py plist ({keys}) ; régénère-le avec python3 -I "
                                              "<dossier d'exécution>/tools/train_auto.py plist (python3 3.10 ou plus requis), puis recharge-le dans launchd"),
    },
    "en": {
        "ligne": "{check}: {level}: {reason}",
        "niveau_ok": "ok",
        "niveau_warning": "warning",
        "niveau_problem": "problem",
        "niveau_skipped": "skipped",
        "resume_ok": "doctor: all good",
        "resume_warning": "doctor: {n} warning(s)",
        "resume_problem": "doctor: {n} problem(s), {m} warning(s)",
        "impossible": "doctor: cannot run: {cause}",
        "cause_date": "today's date is unreadable",
        "cause_heure": "time is unreadable",
        "cause_etat": "state file not writable",
        "notification": "PMZilla doctor: {n} problem(s): {checks}",
        "raison_not_due": "not due yet",
        "raison_not_set_up": "not set up",
        "raison_content_unknown": "content folder not found (PMZILLA_LAB_WORKSPACE or a Git clone of the repository)",
        "raison_depends": "depends on {noms}",
        "raison_unknown": "expiry date unknown",
        "raison_not_local": "address not local",
        "raison_db_ok": "database reachable",
        "raison_db_port_closed": "the database port refuses connections",
        "raison_db_watch_unreachable": "today's watch run recorded the database as unreachable",
        "raison_db_watch_tables_missing": "today's watch run recorded the tables as missing",
        "raison_ollama_ok": "Ollama answers",
        "raison_ollama_down": "Ollama does not answer",
        "raison_models_ok": "models present",
        "raison_models_missing": "model missing ({noms})",
        "raison_launchd_ok": "{loaded} job(s) loaded, {not_set_up} not set up",
        "raison_launchd_not_loaded": "job installed but not loaded: {noms}",
        "raison_launchd_none_installed": "no job installed",
        "raison_watch_ok": "today's watch run ended without error",
        "raison_watch_failed": "today's watch run ended in failure",
        "raison_watch_missing": "no watch run today after the due time",
        "raison_watch_running": "today's watch run is in progress",
        "raison_watch_interrupted": "today's run was interrupted",
        "raison_watch_postponed": "watch postponed, retried later today",
        "raison_watch_missed": "day missed: no run ended before the latest start time",
        "raison_watch_record_not_writable": "the run record cannot be written",
        "raison_backup_ok": "today's backup is complete ({found} dump(s))",
        "raison_backup_missing": "today's backup folder is missing",
        "raison_backup_short": "{found} dump(s) out of {expected}",
        "raison_offsite_ok": "last off-site copy {days} day(s) ago",
        "raison_offsite_warn_old": "last off-site copy {days} day(s) ago",
        "raison_offsite_problem_old": "last off-site copy {days} day(s) ago",
        "raison_offsite_never": "no off-site copy has succeeded since setup",
        "raison_offsite_not_permitted": "off-site copy refused by macOS (Operation not permitted): last success {days} day(s) ago",
        "raison_offsite_incomplete": "off-site copy incomplete according to its log: last success {days} day(s) ago",
        "raison_disk_ok": "{free_gb} GB free",
        "raison_disk_low": "{free_gb} GB free, under the warning threshold",
        "raison_disk_critical": "{free_gb} GB free, under the critical threshold",
        "raison_jira_ok": "token valid for {days} more day(s)",
        "raison_jira_expired": "token expiry date has passed",
        "raison_jira_expiring": "token expires in {days} day(s)",
        "raison_jira_unreadable": "expiry date unreadable or malformed",
        "raison_branches_ok": "no branch or worktree to tidy",
        "raison_branches_stale": ("{merged_worktrees} merged worktree(s), {stale_worktrees} inactive worktree(s), "
                                  "{merged_branches} merged branch(es) not deleted, {prunable} prunable worktree(s), "
                                  "{trial_orphans} orphaned trial-run session copy(ies) (posture_evals.py --remove-orphans): {noms}"),
        "raison_run_worktree_ok": "the run worktree is detached at the tip of main and clean",
        "raison_run_worktree_wrong_branch": "the run worktree is on a branch: it must be detached",
        "raison_run_worktree_behind": "the run worktree is behind main (update postponed or refused)",
        "raison_run_worktree_off_history": "the run worktree is off the history of main",
        "raison_run_worktree_dirty": "the run worktree holds a local change",
        "raison_run_worktree_missing": "the run worktree is missing",
        "raison_mothra_npm_ok": "Mothra's Node and node_modules match the lock",
        "raison_mothra_npm_no_lock": "no Mothra npm lock",
        "raison_mothra_npm_node_version": "Node {version} differs from mothra/.node-version ({pinned})",
        "raison_mothra_npm_node_missing": "Node not found, mothra/.node-version pins {pinned}",
        "raison_mothra_npm_node_unpinned": "mothra/.node-version missing: Node version not checked",
        "raison_mothra_npm_modules_missing": "node_modules missing in mothra/",
        "raison_mothra_npm_modules_stale": "stale node_modules: lock newer or different",
        "raison_pretooluse_ok": "Claude Code is at the version of the last conforming PreToolUse hook trial",
        "raison_pretooluse_claude_missing": "claude command not found",
        "raison_pretooluse_claude_version_unreadable": "claude version unreadable",
        "raison_pretooluse_no_trial": ("no PreToolUse hook trial recorded for Claude Code {version}: "
                                       "run bash tools/essai_crochet_pretooluse.sh in the Terminal"),
        "raison_pretooluse_state_unreadable": ("PreToolUse hook trial state unreadable: "
                                               "run bash tools/essai_crochet_pretooluse.sh again in the Terminal"),
        "raison_pretooluse_version_changed": ("Claude Code {version}, last conforming PreToolUse hook trial with {tried}: "
                                              "run bash tools/essai_crochet_pretooluse.sh again in the Terminal"),
        "raison_pretooluse_not_read": ("the last trial (Claude Code {tried}) did not read a PreToolUse hook's context: "
                                       "go back to form A, PostToolUse (change of the entry only, design D9 of deny-rules-review)"),
        # ci-container (R-20261103-6, Q9)
        "raison_ci_container_ok": "Colima is running and the CI image of the current key exists",
        "raison_ci_container_colima_missing": "colima command not found",
        "raison_ci_container_colima_stopped": "Colima is not running: run colima start --cpu 8 --memory 16 in the Terminal",
        "raison_ci_container_image_absent": ("CI image missing for the current key: "
                                             "run bash tools/ci_local.sh up in the Terminal, from the branch's worktree"),
        "raison_ci_container_image_unreadable": "CI image state unreadable: bash tools/ci_local.sh cle did not answer",
        # sandbox (change bash-sandbox-n2, design D8): the design's lines, character for character
        "raison_sandbox_ok": "sandbox: managed file conforms",
        "raison_sandbox_absent": "sandbox: managed file absent (not posed)",
        "raison_sandbox_differs": "sandbox: managed file differs from its source",
        "raison_sandbox_unprotected": "sandbox: managed file not protected (owner or mode)",
        "raison_sandbox_version_low": "sandbox: Claude Code version below the minimum",
        "raison_sandbox_frozen_differs": "sandbox: frozen tool differs from its record: {noms}",
        "raison_sandbox_claude_missing": "claude command not found",
        "raison_sandbox_claude_version_unreadable": "claude version unreadable",
        # interpreteur_crochets (R-20261108-10)
        "raison_interpreteur_crochets_ok": "hooks interpreter conforms (root, writable by root only)",
        "raison_interpreteur_crochets_missing": ("hooks interpreter absent or unreadable: the hooks may no longer start; "
                                                 "check the link and its target with ls -lL in the Terminal"),
        "raison_interpreteur_crochets_outside": ("the hooks interpreter points outside the CommandLineTools: the hooks may no longer "
                                                 "start; check the target of the link with ls -lL in the Terminal"),
        "raison_interpreteur_crochets_owner": ("hooks interpreter not owned by root: the hooks may no longer start; "
                                               "check the owner of the link, its target and their folders with ls -ld"),
        "raison_interpreteur_crochets_writable": ("hooks interpreter writable by the group or others: the hooks may no longer start; "
                                                  "check the mode of the link, its target and their folders with ls -ld"),
        "raison_interpreteur_crochets_not_mac": "not applicable outside the Mac",
        # crochet-reference-transaction (R-20261110-42): the repair command is in every problem reason, without a path
        "raison_crochet_reference_transaction_ok": "reference-transaction hook installed and conforming",
        "raison_crochet_reference_transaction_no_repo": "Git repository not found: reference-transaction hook not checked; run bash tools/install_hooks.sh --verify in the workspace",
        "raison_crochet_reference_transaction_source_absent": "tracked file tools/hooks/reference-transaction absent; restore it from Git, then run bash tools/install_hooks.sh in the workspace",
        "raison_crochet_reference_transaction_wrong_dir": "unexpected hooks folder (core.hooksPath?); check it, then run bash tools/install_hooks.sh in the workspace",
        "raison_crochet_reference_transaction_missing": "reference-transaction hook not installed; run bash tools/install_hooks.sh in the workspace",
        "raison_crochet_reference_transaction_differs": "reference-transaction hook differs from the expected link or is not executable; run bash tools/install_hooks.sh in the workspace",
        "raison_module_missing": "module {module} missing",
        # train-auto-plist (R-20261110-14) : la commande de régénération et le rappel sont dans chaque raison de problème, sans chemin
        "raison_train_auto_plist_ok": "automatic train launchd template matches the model of train_auto.py plist",
        "raison_train_auto_plist_unreadable": ("automatic train launchd template unreadable; regenerate it with python3 -I <run folder>/tools/train_auto.py plist "
                                               "(python3 3.10 or newer required), then reload it in launchd"),
        "raison_train_auto_plist_python_absent": ("no python3 in the first PATH folder of the automatic train template; regenerate it with python3 -I "
                                                  "<run folder>/tools/train_auto.py plist (python3 3.10 or newer required), then reload it in launchd"),
        "raison_train_auto_plist_python_old": ("python3 of the automatic train template older than 3.10 or version unreadable; regenerate it with python3 -I "
                                               "<run folder>/tools/train_auto.py plist (python3 3.10 or newer required), then reload it in launchd"),
        "raison_train_auto_plist_different": ("automatic train template differs from the model of train_auto.py plist ({keys}); regenerate it with python3 -I "
                                              "<run folder>/tools/train_auto.py plist (python3 3.10 or newer required), then reload it in launchd"),
    },
}
