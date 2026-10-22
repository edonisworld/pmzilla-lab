# tooling-permission-guards Specification

## Purpose
The Claude Code settings file denies the assistant certain commands and file reads: commands that contact the real Jira, read or write the database, touch the keychain, or read sensitive or content folders. A test applies the rules to complete command lines.

## Requirements

### Requirement: Jira-contacting commands are denied
The system SHALL deny, for both the former and the current script names, every subcommand that contacts the real Jira (history test, collect, check with a ticket key; export diagnose, fields, export, and the retired teams-table and compare), whatever the launcher and however the script path is written, with rules anchored on the launcher (requirement "Deny rules of the Jira and flow tools are anchored on the launcher").

#### Scenario: Launchers and paths
- **WHEN** a Jira-contacting command is formed from any supported launcher and any path form (relative, absolute, home-relative, bare)
- **THEN** a deny rule matches it

#### Scenario: Local subcommand
- **WHEN** a history check runs without a ticket key
- **THEN** it is denied, because it reads the database (design D12 of the database-only change)

Source: tests/settings_deny/test_settings_deny.py (CommandesJira); the "Local subcommand" case: tests/settings_deny/test_settings_deny_database_only.py (BlocDatabaseOnly, DansLeFichierDeReglages)

### Requirement: New subcommands must be classified
The system SHALL fail its tests when a subcommand is added to a Jira script without being classified as denied or local.

#### Scenario: Unclassified subcommand
- **WHEN** a script defines a subcommand unknown to the test lists
- **THEN** the test fails naming the script

Source: tests/settings_deny/test_settings_deny.py (test_toute_sous_commande_des_scripts_est_classee)

### Requirement: Sensitive Flux folder files are unreadable
The system SHALL deny reading the exports, history, tables, team-assets and sensitive-names files of the flow folder through the Read tool and through terminal reader commands (cat, head, tail, less, more, grep, awk, sed, cp) in every path form, while leaving the reports and the flow configuration readable.

#### Scenario: Terminal read
- **WHEN** a reader command targets a sensitive file by relative, absolute or home path
- **THEN** it is denied

#### Scenario: Allowed reads
- **WHEN** a reader command targets a report or the flow configuration, or an unrelated file
- **THEN** it is not denied

Source: tests/settings_deny/test_settings_deny.py (FichiersSensibles)

### Requirement: Keychain access is denied
The system SHALL deny commands that read the keychain generic password, any security command mentioning the Jira service, and any security command mentioning the Keychain service of the story analysis key (design D13 of change story-quality-audit), to read, find, add or delete it. The user poses the analysis-key rules; the session SHALL NOT edit the settings file. A security command that names neither service, such as listing the keychains, SHALL NOT be denied by these rules.

#### Scenario: Keychain read
- **WHEN** a command reads the Jira token from the keychain
- **THEN** it is denied

#### Scenario: Analysis key
- **WHEN** a security command names the analysis key's service, to find, add or delete it
- **THEN** a deny rule matches it, while listing the keychains is not denied

Source: tests/settings_deny/test_settings_deny.py (test_trousseau); tests/settings_deny/test_settings_deny_story_quality.py (test_la_cle_d_analyse_est_protegee_dans_le_trousseau)

### Requirement: Content folders are denied under old and new names
The system SHALL deny reading the watch content folders and the excluded folder, under both the former and the current folder names, through the Read tool, and the library, image and watch folders through terminal reader commands in every path form.

#### Scenario: Both names
- **WHEN** a former or current name of a watch or library folder is read through a terminal reader
- **THEN** it is denied, while reading a watch tool script is not

Source: tests/settings_deny/test_settings_deny.py (DossiersDeLaVeille, test_dossiers_de_contenu_refuses_aux_commandes_de_lecture)

### Requirement: Database access is denied to the session
The system SHALL deny the Jira import and comparison scripts, the flow report's `statuses` and `compute`, the dependency tool's `diagnose` and `compute`, the segment sample and the history check, all of which read the database with no option (design D12 of the database-only change), whatever launcher and path form. It SHALL NOT deny the flow report's `compare` and `config`, and SHALL NOT deny a command that only quotes one of these command lines as text.

#### Scenario: Database-reading calculation
- **WHEN** a flow or dependency calculation, the segment sample or the history check is run with any supported launcher and path form, with or without options
- **THEN** it is denied, while the flow report's `compare` and `config` are not

Source: tests/settings_deny/test_settings_deny.py (JiraEnBase); tests/settings_deny/test_settings_deny_database_only.py (BlocDatabaseOnly, DansLeFichierDeReglages)

### Requirement: Direct database clients and backups are denied to the session
The system SHALL deny direct database clients, container exec and copy commands, dump and restore tools, reads of the backup folder (including through binary and compressed readers), the database administration, backup, startup, restore-test and throwaway-database test-launcher scripts, and the control of the backup launchd job, whatever launcher and path form. It SHALL NOT deny a command that only quotes one of these command lines as text.

#### Scenario: Direct clients
- **WHEN** a command runs a database client, container exec or a dump tool
- **THEN** it is denied

#### Scenario: Backup control
- **WHEN** a command loads, unloads, starts or inspects the backup job, or runs the backup script with options
- **THEN** it is denied

#### Scenario: Restore test
- **WHEN** a command launches the restore-test script with any supported launcher and path form
- **THEN** it is denied, while reading it and running its shell test suite are not

Source: tests/settings_deny/test_settings_deny.py (JiraEnBase: test_psql_docker_exec_et_sauvegardes, test_test_de_restauration_interdit_avec_chaque_lanceur_et_chemin, test_tache_launchd_de_sauvegarde_interdite_a_la_session)

### Requirement: Library import and indexing on the database are denied to the session
The system SHALL deny the library import script's import, verify and status subcommands and the library indexer's index, rename-collection, probe and status subcommands, through the tools folder and through the linked tools folder, whatever launcher and path form. It SHALL NOT deny a command that only quotes one of these command lines as text.

#### Scenario: Indexer writing or reading the database
- **WHEN** a command runs the indexer's index, rename-collection, probe or status subcommand with any supported launcher and path form, including the linked tools folder
- **THEN** it is denied

Source: tests/settings_deny/test_settings_deny.py (JiraEnBase: test_import_de_la_bibliotheque_interdit_a_la_session, test_indexeur_interdit_a_la_session)

### Requirement: Permitted database-related commands remain allowed
The system SHALL not deny reading the database scripts' text, running the database script tests through the shell or test runner, reading aggregated views, container status or logs, the help of the database and library import scripts, reading the indexer's text, running the indexer without arguments (help) and the caption diagnostic.

Source: tests/settings_deny/test_settings_deny.py (test_ce_que_la_session_garde, test_lecture_et_test_du_script_de_restauration_non_interdits)

#### Scenario: View listing
- **WHEN** the session lists or shows the aggregated views
- **THEN** the command is not denied

#### Scenario: Indexer help and diagnostic
- **WHEN** the session reads the indexer, runs it without arguments, or runs the caption diagnostic
- **THEN** no deny rule matches

### Requirement: Backup folder unreadable
The system SHALL deny reading the local backup folder through the Read tool.

#### Scenario: Read tool
- **WHEN** the backup folder is read through the Read tool
- **THEN** a deny rule matches

Source: tests/settings_deny/test_settings_deny.py (test_psql_docker_exec_et_sauvegardes)

### Requirement: Wildcard semantics
The system SHALL treat the wildcard as matching any suffix, including empty, and everything else as literal when the test evaluates rules.

#### Scenario: Wildcard
- **WHEN** a pattern contains a wildcard
- **THEN** it matches longer commands but not shorter prefixes of the literal part

Source: tests/settings_deny/test_settings_deny.py (Outil)

### Requirement: Pre-rename rules retained
The system SHALL keep the earlier deny rules active during the English-name transition.

#### Scenario: Old rules
- **WHEN** the settings are loaded
- **THEN** every earlier-generation rule is still present

Source: tests/settings_deny/test_settings_deny.py (test_regles_d_avant_le_lot_3_toujours_presentes)

### Requirement: Personal collection folder is unreadable under its generic name
The system SHALL deny reading the folder of the personal collection inside the watch content folder, named with the generic personal collection name defined in the code, through the Read tool and through the terminal reader commands in every path form, and the test SHALL build that folder name from the code constant.

Source: tests/settings_deny/test_settings_deny.py (DossiersDeLaVeille, test_dossiers_de_contenu_refuses_aux_commandes_de_lecture)

#### Scenario: Read tool
- **WHEN** the settings are loaded
- **THEN** a Read deny rule covers the personal collection folder under the watch content folder

#### Scenario: Terminal readers
- **WHEN** a reader command targets a file of that folder by relative, absolute or home path
- **THEN** it is denied, while reading a watch tool script is not

### Requirement: The branch-finishing script is denied to the session
The system SHALL deny the session the launch of the branch-finishing script through every supported launcher and path form (relative, absolute, home-relative, bare), so that only the user runs it in the Terminal. It SHALL NOT deny reading the script's text, running its shell test suite directly or through the test runner, or running the test runner itself.

#### Scenario: Launch forms
- **WHEN** a command launches the finishing script with any supported launcher and path form
- **THEN** a deny rule matches it

#### Scenario: Allowed commands
- **WHEN** the session reads the script, runs its test suite, or runs the test runner
- **THEN** no deny rule matches

Source: tests/settings_deny/test_settings_deny.py (test_script_de_fin_de_branche_interdit_a_la_session)

### Requirement: The settings file holds only deny rules, one allow rule and the hooks
The system SHALL keep in the shared settings file only a permissions section and a hooks section. Adding any other permission or hook SHALL make a test fail until the test expects it. The session SHALL NOT edit the settings file.

#### Scenario: Allow rule added
- **WHEN** an ask rule, or an allow rule other than the grid rule, is added to the settings file
- **THEN** the test fails

#### Scenario: Other hook added
- **WHEN** a hook other than the two session-start hooks and the pipe-guard entry is added
- **THEN** the test fails

Source: tests/settings_deny/test_settings_autres_regles.py; tests/settings_deny/test_settings_hook_garde_tubes.py

### Requirement: The permissions section holds deny rules and the grid allow rule only
The permissions section SHALL hold deny rules and a single allow rule, `Bash(uv run tools/story_quality.py grid*)` (requirement "The story quality grid check runs without a prompt"), with no ask rule, default mode or additional directory; the former allow rule that read the organisation-context notes is removed (design D10 of change organisation-context).

#### Scenario: Former context allow rule left
- **WHEN** the settings file still holds the allow rule of the organisation-context notes
- **THEN** the test fails and names that rule

Source: tests/settings_deny/test_settings_autres_regles.py

### Requirement: The hooks section holds the session-start hooks and the pipe-guard entry
The hooks section SHALL hold the two session-start hooks, the one that lists the due reviews of the cases module and the one that prints the queue reminder line from the reader's cache, and the `PreToolUse` pipe-guard entry of design D9 of change deny-rules-review (chosen by the author on 2026-10-19): matcher `Bash`, a single command naming the pipe-guard tool with `--event pre`, which only reports and never blocks a command; the `PostToolUse` form SHALL make a test fail.

#### Scenario: Reminder hook missing
- **WHEN** the session-start hooks hold only the due-reviews hook
- **THEN** the test fails and names the queue reminder

#### Scenario: Pipe-guard entry posed
- **WHEN** the hooks section holds the two session-start hooks and one `PreToolUse` entry with matcher `Bash` running the pipe-guard tool with `--event pre`
- **THEN** the test passes

#### Scenario: Former PostToolUse form
- **WHEN** the hooks section holds the pipe-guard entry under `PostToolUse` with `--event post`, alone or beside the `PreToolUse` entry
- **THEN** the test fails and names form A as not admitted

Source: tests/settings_deny/test_settings_autres_regles.py; tests/settings_deny/test_settings_hook_garde_tubes.py

### Requirement: The install script is denied to the session
The system SHALL deny the session every launch of the install script's bootstrap and orchestrator, whatever the launcher and path form. The launchers are the shells, the Python launcher, the Python interpreters and direct execution. The path forms are relative, absolute, home-relative and bare. The deny rules are those of design D6, posed in the settings file by the author; the session SHALL NOT edit the settings file.

#### Scenario: Launch forms
- **WHEN** a command launches the bootstrap or the orchestrator with any supported launcher and path form, with or without the dry-run option
- **THEN** a deny rule matches it

Source: tests/settings_deny/test_settings_deny.py (test_script_d_installation_interdit_a_la_session)

### Requirement: The install script denial covers its options, subcommands and fetched form
A launch through a shell command string that fetches the bootstrap SHALL also be denied. The denial SHALL cover the dry-run option, the help option and any subcommand of the orchestrator, including the pack subcommand planned by change install-migrate, because a dry run probes real services and pack copies the content folders.

#### Scenario: Pack
- **WHEN** a command launches the orchestrator's pack subcommand
- **THEN** a deny rule matches it

Source: tests/settings_deny/test_settings_deny.py (test_script_d_installation_interdit_a_la_session)

### Requirement: Reading and testing the install script stay allowed
The system SHALL NOT deny reading the script files, running the install-script test suite directly, or running the test runner.

#### Scenario: Allowed commands
- **WHEN** the session reads the script files, runs the install-script test suite, or runs the test runner filtered on that suite
- **THEN** no deny rule matches

Source: tests/settings_deny/test_settings_deny.py (test_ce_qui_reste_permis_autour_du_script_d_installation)

### Requirement: The monthly-run orchestrator is denied to the session
The system SHALL deny the session every launch of the monthly-run orchestrator, whatever the launcher and path form. The launchers are the Python launcher, the Python interpreters and direct execution. The path forms are relative, absolute, home-relative and bare. The deny rules are those of design D14, posed in the settings file by the author. The session SHALL NOT edit the settings file.

#### Scenario: Launch forms
- **WHEN** a command launches the orchestrator with any supported launcher and path form, with or without the dry-run, help or resume options
- **THEN** a deny rule matches it

Source: tests/settings_deny/test_settings_deny_flow_monthly.py

### Requirement: The monthly-run orchestrator denial covers its options and test variables
The denial SHALL cover the dry-run option, the help option, the resume options and a command line that sets the orchestrator's test environment variables.

#### Scenario: Test variables on a command line
- **WHEN** a command line sets one of the orchestrator's test environment variables
- **THEN** a deny rule matches it

Source: tests/settings_deny/test_settings_deny_flow_monthly.py

### Requirement: Reading and testing the monthly-run orchestrator stay allowed
The system SHALL NOT deny reading the orchestrator's file, running its test suite directly, or running the test runner.

#### Scenario: Allowed commands
- **WHEN** the session reads the orchestrator's file, runs its test suite, or runs the test runner filtered on that suite
- **THEN** no deny rule matches

Source: tests/settings_deny/test_settings_deny_flow_monthly.py

### Requirement: The off-site copies, the off-site script and its jobs are denied to the session
The system SHALL deny the session the reading and listing of any path inside the fixed off-site folder, through the Read tool and through terminal reader, listing and copy commands, in every path form (relative, absolute, home-relative). It SHALL deny every launch of the off-site backup script other than its help, with every supported launcher and path form, and the loading, unloading, starting and inspecting of its two launchd jobs.

#### Scenario: Reading an off-site copy
- **WHEN** a reader or listing command, or the Read tool, targets a path inside the off-site folder
- **THEN** it is denied

#### Scenario: Launching the script
- **WHEN** the off-site script is launched with the copy, setup or restore-test subcommand, by any launcher and path form
- **THEN** it is denied, while its help, the reading of its source and the run of its test suite are not

#### Scenario: Job control
- **WHEN** a command loads, unloads, starts or inspects one of the two off-site jobs
- **THEN** it is denied

Source: tests/settings_deny/test_settings_deny_offsite_backup.py

### Requirement: The off-site script's source and reports stay readable
The system SHALL NOT deny reading the off-site script's source, running its test suite, or reading the off-site reports and status file of the lab data folder, which hold counts only.

#### Scenario: Source, suite and reports
- **WHEN** the session reads the off-site script's source, runs its test suite, or reads an off-site report or the status file of the lab data folder
- **THEN** no deny rule matches

Source: tests/settings_deny/test_settings_deny_offsite_backup.py

### Requirement: Direct GitHub writes are denied to the session
The system SHALL deny the session, with `gh` written bare, by its absolute path or through `env`: the issue subcommands that create, edit, close, reopen, comment, delete, transfer, lock, unlock, pin, unpin or develop; every `gh api` command; and the authentication commands that print the token, refresh, log in or log out. The deny rules are those of design D18, posed in the settings file by the user; the session SHALL NOT edit the settings file.

#### Scenario: Issue write
- **WHEN** a command creates, edits, closes or comments an issue through `gh` directly, in any supported form
- **THEN** a deny rule matches it

#### Scenario: API call
- **WHEN** a command calls `gh api`, whatever its method and fields
- **THEN** a deny rule matches it

#### Scenario: Token
- **WHEN** a command asks `gh` to print the token
- **THEN** a deny rule matches it

Source: tests/settings_deny/test_settings_deny_github.py

### Requirement: Direct GitHub label, Project, release and repository writes are denied to the session
The system SHALL deny the session, with `gh` written bare, by its absolute path or through `env`: label commands other than listing; Project commands other than listing and viewing projects, fields and items; release commands other than listing and viewing; and repository creation, edition, deletion, renaming, archiving and forking.

#### Scenario: Label, Project, release or repository write
- **WHEN** a command creates a label, edits a Project, creates a release or deletes a repository through `gh` directly, in any supported form
- **THEN** a deny rule matches it, while listing labels, viewing a Project or a release and viewing the repository are not denied

Source: tests/settings_deny/test_settings_deny_github.py

### Requirement: GitHub reading and the queue tools stay allowed
The system SHALL NOT deny listing and viewing issues, listing labels, the authentication status, the queue reader, the GitHub write tool, reading the tools or running their suites.

#### Scenario: Allowed commands
- **WHEN** the session lists or views issues, runs the queue reader or the GitHub write tool, or runs their suites
- **THEN** no deny rule matches

Source: tests/settings_deny/test_settings_deny_github.py

### Requirement: The roadmap import tool is denied to the session
The system SHALL deny the session every launch of the one-shot roadmap import tool, its dry run, cross-check and help included, whatever the launcher (Python launcher, Python interpreters, direct execution) and path form (relative, absolute, home-relative, bare). The rules SHALL stay after the tool is removed. The session SHALL NOT edit the settings file.

Source: tests/settings_deny/test_settings_deny_github.py (IMPORT, roadmap_import.py)

#### Scenario: Launch forms
- **WHEN** a command launches the import tool with any supported launcher and path form, with or without the dry-run option
- **THEN** a deny rule matches it

#### Scenario: Cross-check
- **WHEN** a command launches the import tool's cross-check
- **THEN** a deny rule matches it

### Requirement: The worktree-finishing script is denied to the session
The system SHALL deny the session the launch of the worktree-finishing script through every supported launcher and path form (relative, absolute, home-relative, bare), help included, so that only the user runs it in the Terminal. The deny rules are added to the settings file by the author. It SHALL NOT deny reading the script, running its suite or running the test runner.

#### Scenario: Launch from the session
- **WHEN** a command launches the worktree-finishing script with any supported launcher and path form, with or without the help option
- **THEN** a deny rule matches it

#### Scenario: Reading and testing stay allowed
- **WHEN** a command reads the script, runs its shell suite directly or runs the test runner on that suite
- **THEN** no deny rule matches

Source: tests/settings_deny/test_settings_deny.py (test_script_de_fin_de_worktree_interdit_a_la_session)

### Requirement: The retention tool is denied to the session
The system SHALL deny the session every launch of the retention tool, whatever the subcommand (`check`, `purge`, with or without `--apply`), the launcher (Python launcher, Python interpreters, direct execution) and the path form (relative, absolute, home-relative, bare). The deny rules are those of design D18, added by the user; the session SHALL NOT edit the settings file. The system SHALL NOT deny reading the tool's source, running its test suite or running the test runner.

#### Scenario: Launch forms
- **WHEN** a command launches `check` or `purge --apply` with any supported launcher and path form
- **THEN** a deny rule matches it

#### Scenario: Allowed commands
- **WHEN** the session reads the tool, runs its test suite, or runs the test runner filtered on that suite
- **THEN** no deny rule matches

Source: tests/settings_deny/test_settings_deny_rgpd.py

### Requirement: The epic statuses tool and the verification script are denied to the session
The system SHALL deny the session every launch of the epic statuses tool and of the verification script of change `jira-gdpr-alignment`, whatever the launcher and path form, because both read the exports and the history cache. The system SHALL NOT deny reading their source, reading the epic statuses report in the flow reports folder, or running the epic statuses test suite.

Source: tests/settings_deny/test_settings_deny_rgpd.py

#### Scenario: Launch
- **WHEN** a command launches either tool with any supported launcher and path form
- **THEN** a deny rule matches it

#### Scenario: Reading the report
- **WHEN** the session reads an epic statuses report of the flow reports folder
- **THEN** no deny rule matches

### Requirement: The cycles calculation is denied to the session
The system SHALL deny the session every launch of the `cycles` subcommand of the flow report tool, because it always reads the database, with a rule anchored on the launcher. Like `statuses` and `compute`, it SHALL be denied whatever its options. It SHALL NOT deny `compare` and `config`.

#### Scenario: Cycles without source option
- **WHEN** a command runs the flow report tool's `cycles` subcommand, with or without options
- **THEN** a deny rule matches it, while `compare` is not denied

Source: tests/settings_deny/test_settings_deny_rgpd.py (REGLES_D18, which carries the `cycles` rules; BlocD18.test_cycles_avec_ou_sans_source_et_compute_sur_csv_non_interdit); tests/settings_deny/test_settings_deny_database_only.py (BlocDatabaseOnly.test_compare_et_config_restent_permis, DansLeFichierDeReglages)

### Requirement: The organisation referential is unreadable
The system SHALL deny reading the organisation referential of the flow folder through the Read tool and through the terminal reader commands (cat, head, tail, less, more, grep, awk, sed, cp) in every path form, while leaving the reports and the flow settings readable.

Source: tests/settings_deny/test_settings_deny_rgpd.py

#### Scenario: Terminal read
- **WHEN** a reader command targets the referential by relative, absolute or home path
- **THEN** it is denied

#### Scenario: Flow settings
- **WHEN** a reader command targets the flow settings file
- **THEN** it is not denied

### Requirement: The session cannot launch the publication tool
The system SHALL deny the session every launch of the edition publication tool, whatever the launcher (Python launcher, Python interpreters, direct execution) and path form (relative, absolute, home-relative, bare), the help option included. The deny rules are those of design D16, added to the settings file by the user; the session SHALL NOT edit the settings file.

Source: tests/settings_deny/test_settings_deny_publication.py

#### Scenario: Launch forms
- **WHEN** a command launches the publication tool with any supported launcher and path form, with or without the help option
- **THEN** a deny rule matches it

### Requirement: The session cannot commit or push in the public copy
The system SHALL deny the session every commit and every push aimed at the local copy of the public repository, through a Git command given the copy's path, under its current and its permanent folder name, and through a change of directory into the copy followed by a commit or a push (design D16).

Source: tests/settings_deny/test_settings_deny_publication.py

#### Scenario: Push in the public copy
- **WHEN** a command pushes or commits in the public copy, by giving its path to Git or after changing directory into it
- **THEN** a deny rule matches it

### Requirement: The session cannot read the product-version list
The system SHALL deny the session the reading of the local product-version list through the Read tool and through the terminal reader commands, in every path form (design D16).

Source: tests/settings_deny/test_settings_deny_publication.py

#### Scenario: Product-version list
- **WHEN** a reader command or the Read tool targets the product-version list by relative, absolute or home path
- **THEN** it is denied

### Requirement: The publication guards leave the private work allowed
The system SHALL NOT deny reading the publication tool's text, running its test suite directly, running the test runner, or committing in the private workspace. Pushing from the private workspace SHALL be denied to the session (requirement "Sessions never push", design D11).

Source: tests/settings_deny/test_settings_deny_publication.py; tests/settings_deny/test_settings_deny_push_merge.py

#### Scenario: Allowed commands
- **WHEN** the session reads the tool's text, runs its test suite, runs the test runner, or commits in the private workspace
- **THEN** no deny rule matches

#### Scenario: Push from the private workspace
- **WHEN** the session pushes from the private workspace, by `git push`, `git -C`, `cd … &&` or `--git-dir`
- **THEN** a deny rule matches

### Requirement: The watch copy tool is denied to the session
The system SHALL deny the session every launch of the watch copy tool (copy, dry run, replace, verify, compare and parity), whatever the launcher (shells, the Python launcher, Python interpreters, direct execution) and the path form (relative, absolute, home-relative, bare), because each subcommand reads the real watch and triage data or writes the real database. The deny rules are those of design.md D12, added to the settings file by the author; the session SHALL NOT edit the settings file.

#### Scenario: Launch forms
- **WHEN** a command launches the copy tool with any supported launcher and path form, with any subcommand, including the dry run
- **THEN** a deny rule matches it

Source: tests/settings_deny/test_settings_deny_watch_copy_tool.py

### Requirement: Reading and testing the watch copy tool stay allowed
The system SHALL NOT deny reading the watch copy tool's file, running its test suite directly, or running the test runner, and SHALL NOT deny the collection and pre-triage scripts.

#### Scenario: Allowed commands
- **WHEN** the session reads the copy tool's file, runs its test suite, or runs the weekly inventory of the pre-triage script
- **THEN** no deny rule matches

Source: tests/settings_deny/test_settings_deny_watch_copy_tool.py

### Requirement: The doctor is allowed to the session, its wrapper is not
The system SHALL let the session run the doctor script in every launch form, with no deny rule matching it, and SHALL deny the session every launch form of the doctor's scheduled wrapper, which regenerates the dashboard and so opens a database session. The author adds the wrapper rules; the session SHALL NOT edit the settings file.

Source: tests/settings_deny/test_settings_deny_doctor.py; tests/settings_deny/test_settings_deny_doctor_sh.py

#### Scenario: Doctor launch
- **WHEN** the session runs the doctor script through the Python launcher, with or without its options
- **THEN** no deny rule matches

#### Scenario: Wrapper launch
- **WHEN** the session launches the doctor's scheduled wrapper by path or through a shell
- **THEN** a deny rule matches it

### Requirement: The session cannot delete or move files of the data folder
The system SHALL deny the session `rm`, `rmdir`, `mv` and `rsync` on any path that contains the data folder name, in every path form (relative, absolute, home-relative), so that the SQLite files and the labelled copy of design D11 are removed or moved by the user only. It SHALL NOT deny the test runner, the test suites, or commands on temporary folders. The rules are those of design D15, added by the author.

#### Scenario: Deleting a SQLite file
- **WHEN** a command removes a SQLite file of the data folder by home-relative or absolute path
- **THEN** a deny rule matches it

#### Scenario: Removing the labelled copy
- **WHEN** a command removes or moves the labelled backup folder
- **THEN** a deny rule matches it

#### Scenario: Allowed commands
- **WHEN** the session removes a file in a temporary folder or runs the test runner
- **THEN** no deny rule matches

### Requirement: The session cannot run the component check
The system SHALL deny the session the check subcommand of the component tool, in every path form (relative, absolute, home-relative) and through `uv run`, `python` and `python3`, so that upstream sources are queried only by the daily run or by the user (fiche C18, design.md D14). It SHALL NOT deny the inventory subcommand, the test runner or the test suites. The deny rules are added to the settings file by the author; the session SHALL NOT edit the settings file.

#### Scenario: Check denied
- **WHEN** a command runs the component tool's check subcommand through uv by relative or absolute path
- **THEN** a deny rule matches it

#### Scenario: Inventory allowed
- **WHEN** the session runs the component tool's inventory subcommand with the verify option, or the test runner
- **THEN** no deny rule matches

Source: tests/settings_deny/test_settings_deny_composants.py

### Requirement: The morning summary is allowed to the session
The system SHALL NOT deny the session any launch of the morning summary script, with or without its JSON, language or notify options, whatever the launcher and path form: it opens only the cases read-only session and reads the lab data folder (design D11 of change morning-summary). The test SHALL show that these launches match no deny rule. The settings file SHALL gain no hook for the summary.

Source: tests/settings_deny/test_settings_deny_morning_summary.py

#### Scenario: Launch forms
- **WHEN** the session launches the summary script with any supported launcher and path form, with or without its options
- **THEN** no deny rule matches it

#### Scenario: No new hook
- **WHEN** the settings file is loaded after this change
- **THEN** its hooks are only the two session-start hooks and, once posed, the pipe-guard entry, none of them naming the summary script

### Requirement: The run tree is not editable by the session
The system SHALL deny the session the edit, write and notebook-edit tools on any path inside the run tree, and Git commands that change it through its folder option, in every path form. It SHALL NOT deny reading the run tree. The deny rules are those of design D6, added by the author; the session SHALL NOT edit the settings file.

Source: tests/settings_deny/test_settings_deny_run_worktree.py

#### Scenario: Edit in the run tree
- **WHEN** the session edits or writes a file inside the run tree, by absolute or home-relative path
- **THEN** a deny rule matches

#### Scenario: Read allowed
- **WHEN** the session reads a file inside the run tree
- **THEN** no deny rule matches

### Requirement: The run-tree script changes are denied to the session
The system SHALL deny the session the create and update subcommands of the run-tree script, with every supported launcher and path form. It SHALL NOT deny its status subcommand, its help, reading its source, running its suite or running the test runner.

Source: tests/settings_deny/test_settings_deny_run_worktree.py

#### Scenario: Update by the session
- **WHEN** a command launches the run-tree script's update or create subcommand, by any launcher and path form
- **THEN** a deny rule matches it

#### Scenario: Status allowed
- **WHEN** the session runs the status subcommand or the script's test suite
- **THEN** no deny rule matches

### Requirement: Denied scripts stay denied through their link and the run tree
The system SHALL make every deny rule that covers a script through the tools folder also cover its lab-folder link and its path inside the run tree, with every supported launcher. It SHALL NOT deny reading those scripts, running their suites or running the test runner.

Source: tests/settings_deny/test_settings_deny_run_worktree.py

#### Scenario: Backup through the run tree
- **WHEN** a command launches the backup script by its path inside the run tree or by its lab-folder link
- **THEN** a deny rule matches it

#### Scenario: Three path forms checked
- **WHEN** the settings test builds, for each denied script, its tools-folder, lab-folder link and run-tree forms
- **THEN** a deny rule matches each form

### Requirement: Team sources denied to the session
The system SHALL deny the assistant reading the team catalogue, the organisation referential and the former team table (Read tool and terminal readers), and every anchored launch of `check-teams` and `migrate-teams` (team-mapping D9). It SHALL NOT deny a command that only quotes these names. Only the user edits the settings.

Source: tests/settings_deny/test_settings_deny_equipes.py

#### Scenario: Catalogue read
- **WHEN** the assistant tries to read the catalogue with the Read tool or a terminal reader
- **THEN** the permission rules deny it

#### Scenario: New subcommands
- **WHEN** the assistant tries to launch `check-teams` or `migrate-teams` with any launcher
- **THEN** the permission rules deny it, while a search of the same command text in the documentation is allowed

### Requirement: Complete Assets team list denied to the session
The system SHALL deny the assistant reading any `Flux-Lab/equipes-assets-complet-*.csv` or a copy of that name, with the Read tool and the terminal readers, in relative, absolute and home-relative forms (team-mapping D9 complement, C4 (a)). It SHALL NOT deny the reports or the flow configuration. The author adds the rules; the session SHALL NOT edit the settings.

Source: tests/settings_deny/test_settings_deny_liste_assets.py; tests/settings_deny/test_settings_deny_liste_assets_lecteurs.py

#### Scenario: Assets list read
- **WHEN** the assistant tries to read a dated Assets list of the flow folder with the Read tool or a terminal reader, by relative, absolute or home path
- **THEN** the permission rules deny it

#### Scenario: Copy of the Assets list
- **WHEN** the assistant tries to read with a terminal reader a copy of a dated Assets list placed in another folder under the same name
- **THEN** the permission rules deny it

#### Scenario: Reports still readable
- **WHEN** the assistant reads a report of the flow folder
- **THEN** the new rules do not deny it

### Requirement: The story quality tool is denied to the session
The system SHALL deny the session every launch of the story quality tool's `collect`, `review`, `analyse` and `coach` subcommands, with every option, whatever the launcher and the path form. The user adds the rules of design D13 of change story-quality-audit; the session SHALL NOT edit the settings file. The test SHALL fail when only part of the rules is in the settings.

Source: tests/settings_deny/test_settings_deny_story_quality.py

#### Scenario: Launch forms
- **WHEN** a command launches `collect`, `review`, `analyse`, `coach --team`, `coach --keys` or `coach --show` with any supported launcher and path form
- **THEN** a deny rule matches it

#### Scenario: Dry run
- **WHEN** a command launches `analyse --dry-run` or `coach --dry-run` with any supported launcher and path form
- **THEN** a deny rule matches it, although the dry run sends nothing

#### Scenario: Sample run
- **WHEN** a command launches `analyse --sample 3`, `analyse --sample 3 --team x` or `analyse --sample 3 --dry-run` with any supported launcher and path form
- **THEN** a deny rule matches it

#### Scenario: Partial edit of the settings
- **WHEN** the settings file holds some rules of the block but not all
- **THEN** the test fails and counts the missing rules

### Requirement: The story quality report, grid check and help stay allowed
The system SHALL NOT deny the story quality tool's `report`, `report --json`, `grid`, `grid --show` and `grid --show --json` subcommands (design D15 of change story-quality-audit: they read the views or the grid only), its help, reading its source, the grid and the example overlay, reading the quality views and reports, or running its test suite and the test runner, neither by the new rules nor by the earlier ones.

#### Scenario: Report allowed
- **WHEN** the session runs the `report`, `grid` or `grid --show` subcommand or the help, reads the tool, or runs its test suite
- **THEN** no deny rule matches

#### Scenario: JSON outputs allowed
- **WHEN** the session runs `report --name <series> --json` or `grid --show --json`, with any supported launcher and path form, with or without `--language`
- **THEN** no deny rule matches

Source: tests/settings_deny/test_settings_deny_story_quality.py (including the `report --json` and `grid --show --json` cases)

### Requirement: Story quality subcommands must be classified
A subcommand or option added to the story quality tool without being classified as denied or allowed SHALL make the test fail.

#### Scenario: Unclassified subcommand
- **WHEN** the tool defines a subcommand unknown to the test lists
- **THEN** the test fails naming the tool

Source: tests/settings_deny/test_settings_deny_story_quality.py

### Requirement: The organisation overlay folder is denied to direct access
The system SHALL deny the session reading, writing and editing the `regles/` subfolder of the context folder, in every path form, through Read and Edit rules (an Edit rule also covers Write; no Write rule is added) and the terminal readers denied on the context notes (D13 of story-quality-audit). The session SHALL NOT edit the settings file. The tracked overlay schema, the example overlay and the context notes SHALL stay readable.

Source: tests/settings_deny/test_settings_deny_story_quality.py

#### Scenario: Overlay read
- **WHEN** the Read tool or a terminal reader targets the overlay file, by relative, absolute, home-relative or wildcard path
- **THEN** a deny rule matches it

#### Scenario: Overlay written or edited
- **WHEN** the Write or Edit tool targets a file of the `regles/` subfolder, in any path form
- **THEN** a deny rule matches it

#### Scenario: Without organisation-context
- **WHEN** the settings hold the rules of this block and none of change `organisation-context`
- **THEN** every overlay case above is still denied

#### Scenario: Example, schema and notes allowed
- **WHEN** the session reads the tracked overlay schema, the example overlay or a context note
- **THEN** no deny rule matches

### Requirement: The session never creates, removes or moves the finish lock
The system SHALL hold deny rules that refuse to the session the commands `rm`, `rmdir`, `mv`, `mkdir` and `touch` on a path that holds the name of the finish lock of multi-session-piloting design D5, in every launcher and path form used for the other protected paths, and SHALL keep the pilot tool's status, freeze and note subcommands allowed. The rules are added by the author. It SHALL NOT let the session lift the freeze by removing a live lock.

#### Scenario: Removal refused
- **WHEN** the settings test submits a removal of the lock folder in the common Git folder, by relative and absolute path
- **THEN** each form is refused by a deny rule

#### Scenario: Pilot tool allowed
- **WHEN** the settings test submits the pilot status, the freeze check and a note
- **THEN** none of them matches a deny rule

### Requirement: The context originals are unreadable and unlistable in every form
The system SHALL deny the session every read and listing of the originals folder of the context space: through the Read tool in relative, absolute and home-relative forms, and through the terminal reader, listing, archive, decompression, encoding, metadata and copy commands of design D10. The deny rules are added to the settings file by the author; the session SHALL NOT edit the settings file.

Source: tests/settings_deny/test_settings_deny_contexte.py

#### Scenario: Listing the originals
- **WHEN** a listing, archive or metadata command targets the originals folder by absolute or home-relative path
- **THEN** a deny rule matches it

#### Scenario: Read tool, absolute form
- **WHEN** the Read tool targets a file of the originals folder by an absolute path
- **THEN** a deny rule matches it

### Requirement: The context notes are read through the library only
The system SHALL deny the session reading, editing and writing the notes folder of the context space through the Read, Edit and Write tools and the terminal readers of design D10, in every path form, so that notes reach the session only through the library search and are written only by the context tool. It SHALL NOT deny the context tool, reading its source, running its suite or running the test runner.

Source: tests/settings_deny/test_settings_deny_contexte.py

#### Scenario: Reading a note
- **WHEN** the Read tool or a reader command targets a file of the notes folder
- **THEN** a deny rule matches it

#### Scenario: Writing a note directly
- **WHEN** the Write or Edit tool targets a file of the notes folder
- **THEN** a deny rule matches it

#### Scenario: Context tool allowed
- **WHEN** the session runs the context tool's list, check, add or review subcommand, or its test suite
- **THEN** no deny rule matches

### Requirement: The context-folder rules name the new folder only
The system SHALL hold the deny rules of the context folder, its originals, notes and overlay subfolder exactly as listed in design D10, and no rule naming the former folder `Contexte-Lab`. The rules SHALL NOT match the local context file, the neutral context templates or the overlay's `grid` subcommands. The session SHALL NOT edit the settings file: the author does, with the move.

Source: tests/settings_deny/test_settings_deny_contexte.py

#### Scenario: Former folder named
- **WHEN** the settings file still holds a rule that names `Contexte-Lab`
- **THEN** the settings-deny test fails and names that rule

#### Scenario: Overlay reposed
- **WHEN** the Read, Edit or Write tool or a reader targets the overlay file in the `regles` subfolder of the new folder
- **THEN** a deny rule matches it

#### Scenario: Whole folder listed
- **WHEN** `find`, `tree`, `rsync`, `tar`, `ditto` or `zip` names the context folder last, with a path under it, or followed by options
- **THEN** a deny rule matches it

#### Scenario: Local context file still readable
- **WHEN** the Read tool or `cat` targets `.pmzilla/contexte.md` or `tests/postures/contexte-neutre.md`
- **THEN** no deny rule matches

### Requirement: Review list of outside teams denied to the session
The system SHALL deny to the session, through the deny rules of `.claude/settings.json` added by the author (design D4 of the names-and-team-review change), the reading of the review list of outside teams with the Read tool and with the terminal readers and listers already denied on the team catalogue, and its creation or modification with the Edit tool. It SHALL NOT deny a command that only names the file (such as `git grep`), and the session SHALL NOT edit the settings file itself.

#### Scenario: Read refused
- **WHEN** the session tries to read the review list with the Read tool or a terminal reader
- **THEN** the call is denied by a rule, as for the team catalogue

#### Scenario: Edit refused
- **WHEN** the session tries to create or modify the review list with the Edit tool
- **THEN** the call is denied by a rule

#### Scenario: Naming allowed
- **WHEN** a command only names the file without reading it
- **THEN** it is not denied

### Requirement: Every declared deny-rule list passes the shared guard before the pose
The system SHALL apply the shared guard of design D1 (change deny-rules-review) to the list that every settings_deny module prints with `--json`, before any pose. It SHALL refuse a `Write(` or `NotebookEdit(` rule, an empty or malformed rule, a duplicate and an empty list, one line per finding naming the module and the rule. It SHALL NOT check a removal list, run a command, or require editing an existing test.

#### Scenario: Write rule declared
- **WHEN** a module's `--json` list holds a `Write(path)` rule
- **THEN** the suite fails with `garde R-84 : <module> : règle Write(chemin) ou NotebookEdit(chemin) : Claude Code l'ignore ; utiliser Edit(chemin) : <règle>`

#### Scenario: Duplicate declared
- **WHEN** a module's `--json` list holds the same rule twice
- **THEN** the suite fails with a `règle en double` line naming the module and the rule

#### Scenario: List function missing
- **WHEN** a module holds a `--json` entry point and neither `regles_attendues()` nor a function declared in the discovery test's mapping
- **THEN** the suite fails with `garde R-84 : <module> : sortie --json sans fonction de liste`

#### Scenario: Before the pose
- **WHEN** a change's rules are not yet in the settings file and its list is clean
- **THEN** the guard passes on that list

#### Scenario: Removal list
- **WHEN** a module also defines a list of `Write(` rules to remove
- **THEN** that list is not checked and does not fail the guard

### Requirement: The settings file holds no empty permission key
The system SHALL fail its settings test when a key of the permissions section of the shared settings file holds an empty list or an empty string, naming the key with the line of design D2. When the inventory of the change finds no duplicate deny rule, it SHALL also fail on a duplicate deny rule, naming it (design D3); it SHALL NOT be written to fail on duplicates already present.

#### Scenario: Empty allow key left by a pose
- **WHEN** the permissions section holds an `allow` key with an empty list
- **THEN** the test fails with `garde R-84 : clé de permission vide dans .claude/settings.json : allow`

### Requirement: The session never declares the postponement of the off-site copy
The system SHALL refuse to the session, through deny rules, the postpone subcommand of the off-site script (morning-guard design D11), in every form already used for the other protected commands. It SHALL keep the morning-state check allowed; its rules SHALL NOT name the status subcommand, left to the existing copy rules. The session SHALL NOT declare a postponement by any other route, such as appending to the copy log itself.

Source: tests/settings_deny/test_settings_deny_garde_matin.py

#### Scenario: Postpone refused
- **WHEN** the settings test matches the postpone subcommand, called directly, through `bash` and through the lab-folder link, against the deny rules
- **THEN** each form is refused

#### Scenario: Check allowed
- **WHEN** the settings test matches `bash tools/morning_state.sh check` against the real deny rules, and the off-site status subcommand against the rules of this change alone
- **THEN** neither is refused

### Requirement: The former team table stays denied in the archives folder
The system SHALL deny the session reading the former team table in the archives folder and at any place, through the Read rules of design D6 block A and the existing command rules on its unchanged name, all of which SHALL be kept. The author adds the rules; the session SHALL NOT edit the settings file.

Source: tests/settings_deny/test_settings_deny_archives.py

#### Scenario: Read tool at the new place
- **WHEN** the Read tool targets a file of the former team table under the archives folder, by home-relative or absolute path
- **THEN** a deny rule matches it

#### Scenario: Terminal reader at the new place
- **WHEN** a reader, listing or copy command targets the former team table under the archives folder
- **THEN** a deny rule matches it

#### Scenario: Former place still covered
- **WHEN** the Read tool or a reader targets the former team table at its former place
- **THEN** a deny rule still matches it

### Requirement: The whole archives folder is denied to recursive commands
The system SHALL deny the session the recursive listing, copy and archiving commands of design D6 block B on the archives folder, a path under it, or the folder followed by options. The author adds the rules; the session SHALL NOT edit the settings file. The system SHALL NOT deny commands on OpenSpec's archive folder of changes.

Source: tests/settings_deny/test_settings_deny_archives.py

#### Scenario: Recursive copy of the archives folder
- **WHEN** a command copies, archives or searches the archives folder recursively, in any of the three forms
- **THEN** a deny rule matches it

#### Scenario: OpenSpec archive folder
- **WHEN** a command lists or reads OpenSpec's archive folder of changes
- **THEN** no deny rule matches

### Requirement: The public copy guards follow the copy into the archives folder
The system SHALL keep denying every commit and push aimed at the local copy of the public repository when the copy sits under the archives folder, through the existing rules that match its folder name (design D6). No rule SHALL be removed for the move.

Source: tests/settings_deny/test_settings_deny_archives.py

#### Scenario: Push in the moved copy
- **WHEN** a command commits or pushes in the public copy by giving its new path under the archives folder to Git
- **THEN** a deny rule matches it

### Requirement: Worktree commands on the worktrees folder stay allowed
The system SHALL NOT deny listing, moving and inspecting worktrees in the worktrees folder through Git, listing that folder, reading the worktree script and the lab-paths modules, running their suites, or running the test runner (design D6).

Source: tests/settings_deny/test_settings_deny_archives.py

#### Scenario: Worktree commands
- **WHEN** the session lists the worktrees, runs a Git status in a worktree under the worktrees folder, or runs the worktree suite
- **THEN** no deny rule matches

### Requirement: Deny rules of the Jira and flow tools are anchored on the launcher
The system SHALL begin every deny rule of a Jira or flow tool with a launcher or the tool's path, as in `uv run tools/<tool>.py*` (design D12 of the database-only change), and SHALL NOT begin it with a wildcard. A real launch SHALL stay denied; a command that only quotes it SHALL NOT be. Only the user edits the settings file.

#### Scenario: Real launch in the three forms
- **WHEN** `flux_jira.py compute`, `dependencies_jira.py diagnose`, `segment_sample.py` or `history_jira.py check` is launched through `uv run tools/<tool>.py`, `python tools/<tool>.py` or `python3 tools/<tool>.py`, with or without options
- **THEN** a deny rule matches each command

#### Scenario: Documentation search quoting the command
- **WHEN** the session runs a `grep` whose pattern is the text of one of those launches, such as `uv run tools/flux_jira.py compute`, on the documentation folder
- **THEN** no deny rule matches it

#### Scenario: No leading wildcard
- **WHEN** the settings file is loaded
- **THEN** no deny rule that names a Jira or flow tool of the database-only change, or the `--source` option, begins with a wildcard inside `Bash(...)`

### Requirement: Leading-wildcard rules on the source option are replaced
The system SHALL remove the deny rules that begin with a wildcard to catch the `--source db` option anywhere on a command line, and SHALL cover the tools concerned with anchored rules instead (design D12 of the database-only change). It SHALL NOT deny a command that only quotes `--source db`.

#### Scenario: Quoted option
- **WHEN** the session runs a `grep` for `--source db` on the documentation folder
- **THEN** no deny rule matches it

#### Scenario: Former option on a real launch
- **WHEN** `flux_jira.py compute --source db` is launched through `uv run`, `python` or `python3`
- **THEN** an anchored rule of the flow report tool matches it

### Requirement: The team sources check is denied to the session
The system SHALL deny the session every launch of the export tool's `check-teams`, which reads the database (design D13 of the database-only change), with rules anchored on the launcher, such as `uv run tools/export_jira_api.py check-teams*`, in every launcher and path form. Only the user adds them, from the block the deny test prints. It SHALL NOT deny a command that only quotes the launch, nor begin such a rule with a wildcard.

#### Scenario: Real launch denied
- **WHEN** `check-teams` is launched through `uv run tools/export_jira_api.py`, `python tools/export_jira_api.py` or `python3 tools/export_jira_api.py`, with or without options
- **THEN** a deny rule matches each command

#### Scenario: Quoted launch allowed
- **WHEN** the session runs a `grep` whose pattern is `uv run tools/export_jira_api.py check-teams` on the documentation folder
- **THEN** no deny rule matches it

#### Scenario: Block printed for the user
- **WHEN** the deny test of the change is run with its JSON option
- **THEN** the printed block holds the anchored `check-teams` rules beside the other rules of the change, none beginning with a wildcard

### Requirement: The team-names extract subcommand is denied to the session, its file is readable
The system SHALL deny every anchored launch of the export tool's `extract-teams` subcommand under each launcher and path form, with rules that start with the launcher or the script path, declared by a `--json` list function that passes the shared guard (design D5). It SHALL NOT deny reading the team-names extract of the flow folder with the Read tool or a terminal reader, and SHALL NOT deny a command that only quotes the subcommand. Only the user edits the settings.

#### Scenario: Launch
- **WHEN** a command launches `export_jira_api.py extract-teams` through `uv run`, `python`, `python3` or a direct path, with or without `--language`
- **THEN** a deny rule matches it

#### Scenario: Reading the extract
- **WHEN** the Read tool or a terminal reader targets the team-names extract by relative, absolute or home path
- **THEN** no deny rule matches it

#### Scenario: Quote
- **WHEN** a `grep` or `git grep` command only quotes `extract-teams` in the documentation
- **THEN** no deny rule matches it

Source: tests/settings_deny/test_settings_deny_team_names.py

### Requirement: Rules kept by the team-names decision stay in place
The system SHALL keep the deny rules of the items the team-names inventory leaves closed, of the team command launches, of the database clients and of the Keychain and token commands (design D5). The rules of the team catalogue are among them: the catalogue SHALL NOT be opened raw (design decision b). A test SHALL fail when one is missing. The decision of 2026-10-19 SHALL NOT remove any of them.

Source: tests/settings_deny/test_settings_deny_team_names.py (test_le_catalogue_garde_ses_37_regles)

#### Scenario: A kept rule disappears
- **WHEN** the settings lose the Read rule of the sensitive-names list or of the referential
- **THEN** the test fails and names the missing rule

#### Scenario: Catalogue rule removed
- **WHEN** the settings lose any of the 37 rules of the team catalogue
- **THEN** the test fails and names the missing rule

### Requirement: Sessions never push
The system SHALL deny `git push` in every form of design D11: bare, with `-C` or `--git-dir`, after `cd … &&` or `cd …;`, through `env`, through an absolute path of git or of env, on any branch, `--dry-run` included. It SHALL NOT deny `git status`, `git log`, `git fetch` or a `grep` that only quotes `git push`. The finishing scripts the user launches outside any session are not concerned. Only the user edits the settings.

Source: tests/settings_deny/test_settings_deny_push_merge.py

#### Scenario: Push forms
- **WHEN** a command pushes a work branch or the main branch in any form of design D11
- **THEN** a deny rule matches it

#### Scenario: Dry run
- **WHEN** a command runs `git push --dry-run`
- **THEN** a deny rule matches it

#### Scenario: Reading the remote state
- **WHEN** a command runs `git status`, `git log origin/main..main` or `git fetch`
- **THEN** no deny rule matches it

#### Scenario: Quotation in a search
- **WHEN** a `grep` command or `git grep` only quotes `git push`
- **THEN** no deny rule matches it

### Requirement: Sessions never force nor skip the hooks
The system SHALL deny a git command carrying `--force` or `--no-verify`, bare, through `env`, through an absolute path of git or of env, or after `cd … &&` or `cd …;` (design D11). It SHALL NOT deny a git command without these options, nor a `grep` that only quotes them.

Source: tests/settings_deny/test_settings_deny_push_merge.py

#### Scenario: Forced push or skipped hook
- **WHEN** a command runs `git push --force-with-lease` or `git commit --no-verify` in any of these forms
- **THEN** a deny rule matches it

#### Scenario: Ordinary commit
- **WHEN** a command runs `git commit -m` with a message holding neither option
- **THEN** no deny rule matches it

### Requirement: Sessions never merge in the main workspace nor merge a pull request
The system SHALL deny `gh pr merge` bare, through `env` or an absolute path, and `git merge` in the main workspace: the forms naming its path in the shared settings, the bare form only in its local settings, which worktrees do not carry (design D11). It SHALL NOT put the bare form in the shared settings, nor deny `git merge` in a worktree, `gh pr list` or `gh pr view`.

Source: tests/settings_deny/test_settings_deny_push_merge.py

#### Scenario: Pull-request merge
- **WHEN** a command runs `gh pr merge` in any of its four forms
- **THEN** a deny rule matches it

#### Scenario: Merge in the main workspace
- **WHEN** a command merges a branch with `git -C` or `cd` naming the main workspace, or runs a bare `git merge` under the main workspace's local settings
- **THEN** a deny rule matches it

#### Scenario: Merge in a worktree
- **WHEN** a command runs `git merge main` in a worktree, or `gh pr list` or `gh pr view`
- **THEN** no rule of the shared settings matches it

### Requirement: Push and merge rules declared and pinned
The system SHALL declare the rules of design D11 in `--json` list functions that pass the shared guard: no `Write(` or `NotebookEdit(` rule, no empty permission key, no duplicate, no bare leading wildcard. Their tests SHALL be skipped before the user's pose and SHALL fail once one rule is posed and another is missing. The six push and merge rules already present SHALL be kept, not duplicated.

Source: tests/settings_deny/test_settings_deny_push_merge.py

#### Scenario: Before the pose
- **WHEN** no rule of design D11 is in the settings
- **THEN** the tests against the real settings are skipped and the declared blocks still pass the guard and the matrix

#### Scenario: A rule disappears
- **WHEN** the settings hold some rules of design D11 and lose another
- **THEN** the test fails and names the missing rule

### Requirement: Sessions never write inside a git folder
The system SHALL deny the editing tools on a path inside a `.git` folder and on a worktree's `.git` file, and the Bash writes of design D12 into them: redirections, `cp`, `mv`, `rm`, `touch`, `tee`, `chmod`, `ln`, `mkdir` and `sed -i`, bare, by absolute path or after `&&` or `;`, the path quoted or not. It SHALL NOT add a `Write(` or `NotebookEdit(` rule. Only the user edits the settings.

Source: tests/settings_deny/test_settings_deny_git_dir.py

#### Scenario: Editing tool on a hook
- **WHEN** the Edit tool targets `.git/hooks/pre-commit` or `.git/config` by relative, absolute or home path, or a worktree's `.git` file
- **THEN** an `Edit(` rule of design D12 matches it

#### Scenario: Forged fingerprint
- **WHEN** a command writes a test fingerprint inside a `.git` folder by redirection, `touch` or `tee` after a pipe
- **THEN** a deny rule matches it

#### Scenario: Worktree git file removed or replaced
- **WHEN** a command runs `rm .git`, `mv .git .git.bak` or redirects text into `.git`
- **THEN** a deny rule matches it

#### Scenario: Quoted path
- **WHEN** a command runs `rm -rf ".git"`, `mv '.git' x` or redirects text into `".git"`
- **THEN** a deny rule matches it

#### Scenario: Common git dir
- **WHEN** a command copies, links or edits in place a file under the common git dir or its `worktrees/` folder, bare, by absolute path or after `&&` or `;`
- **THEN** a deny rule matches it

### Requirement: Git folder rules leave git use and reading allowed
The system SHALL NOT deny `git status`, `git log`, `git add`, `git commit`, `git fetch`, `git worktree list` or `git rev-parse`, nor reading a `.git` folder with the Read tool or a terminal reader without redirection, nor editing `.gitignore` or `.github/` (design D12). The harmless commands that D12 refuses SHALL be stated in the design and named in the tests.

Source: tests/settings_deny/test_settings_deny_git_dir.py

#### Scenario: Ordinary git commands
- **WHEN** a command runs `git status`, `git log origin/main..main`, `git add`, `git commit -m x`, `git fetch`, `git worktree list` or `git rev-parse --git-common-dir`
- **THEN** no deny rule of design D12 matches it

#### Scenario: Reading a git folder
- **WHEN** the Read tool, `cat`, `head`, `ls` or `grep` reads a file of a `.git` folder without redirection
- **THEN** no deny rule of design D12 matches it

#### Scenario: Neighbour names
- **WHEN** a command or the Edit tool writes `.gitignore` or a file under `.github/`
- **THEN** no deny rule of design D12 matches it

#### Scenario: Stated effect
- **WHEN** a command holds a redirection followed later by a `.git/` path, such as `git status 2>&1 | grep .git/`
- **THEN** a deny rule matches it and the test names this case as a stated effect

#### Scenario: Commit message quoting a write
- **WHEN** a commit message holds a write chain into a `.git` path, such as `git commit -m "x; rm -rf .git"`
- **THEN** a deny rule matches it, the test names it as a stated effect, and the message is to be written without that text

### Requirement: Git folder rules declared and pinned
The system SHALL declare the rules of design D12 in a `--json` list function that passes the shared guard: no `Write(` or `NotebookEdit(` rule, no empty permission key, no duplicate, none already in the settings. Its tests SHALL be skipped before the user's pose and SHALL fail, naming the missing rules, once one is posed and another is missing. The five finish-lock rules SHALL be kept.

Source: tests/settings_deny/test_settings_deny_git_dir.py

#### Scenario: Before the pose
- **WHEN** no rule of design D12 is in the settings
- **THEN** the tests against the real settings are skipped and the declared block still passes the guard and the matrix

#### Scenario: Partial pose
- **WHEN** the settings hold some rules of design D12 and lack another
- **THEN** the test fails with the D12 phrase and names the missing rule

#### Scenario: Finish lock rule removed
- **WHEN** the settings lose one of the five finish-lock rules
- **THEN** the test fails and names the missing rule

### Requirement: Sessions never install, update or publish npm packages
The system SHALL deny to the session, through rules the author poses, the npm subcommands of the reduced block of design D0 of mothra-session-guards, `npm ci --offline` included, in the five forms of design D2. It SHALL NOT deny the allowed commands of D1 (`npm test`, `npm run`, `npm start`), a command that only quotes a denied form, nor a script that runs npm inside, such as the worktree script's `npm ci --offline`.

Source: tests/settings_deny/test_settings_deny_npm.py

#### Scenario: Install forms
- **WHEN** a command runs `npm install <paquet>`, `npm i`, `npm --prefix mothra install`, `cd mothra && npm ci`, `npm ci --offline`, `env npm update` or the absolute path of npm followed by `install`
- **THEN** a deny rule matches each command

#### Scenario: Allowed commands
- **WHEN** a command runs `npm test`, `npm run build`, `npm start`, `npm ls`, `npm audit` or `bash tools/worktree.sh <branche>`
- **THEN** no deny rule matches it

#### Scenario: Quoted form
- **WHEN** a `grep` or `git grep` command only quotes `npm install`
- **THEN** no deny rule matches it

#### Scenario: Stated effect
- **WHEN** a command runs a script whose name starts with a denied subcommand with options before `run`, such as `npm --prefix mothra run install-check`
- **THEN** a deny rule matches it and the test names this case as a stated effect

### Requirement: Sessions never run a package through npx or npm exec
The system SHALL deny `npx` and `npm exec` with its alias `x`, with or without arguments, in the five forms of design D2. It SHALL NOT deny a command that only quotes them.

Source: tests/settings_deny/test_settings_deny_npm.py

#### Scenario: npx
- **WHEN** a command runs `npx <paquet>`, `cd mothra && npx tsc` or `npm exec <paquet>`
- **THEN** a deny rule matches each command

#### Scenario: Quotation
- **WHEN** a `grep` command searches the guide for `npx`
- **THEN** no deny rule matches it

### Requirement: Sessions never evaluate Node code from the command line
The system SHALL deny the Node evaluation, print and standard-input forms of design D3 (`-e`, `--eval`, `-p`, `--print`, combined short flags, `-` and an input type followed by an evaluation flag), with options before them, in the five forms of design D2. It SHALL NOT deny `node --version`, `node -v` or the launch of a file, and the guide SHALL state that a Node script launched by path is not stopped by a rule.

Source: tests/settings_deny/test_settings_deny_npm.py

#### Scenario: One-liner
- **WHEN** a command runs `node -e "<code>"`, `node --print <expr>`, `node -pe <expr>` or `node -` with a program on standard input
- **THEN** a deny rule matches each command

#### Scenario: Version and file launch
- **WHEN** a command runs `node --version` or `node <fichier>`
- **THEN** no deny rule matches it

### Requirement: Sessions never use another package manager
The system SHALL deny `pnpm`, `yarn`, `bun`, `bunx` and `corepack` as whole commands in the five forms of design D2, unless the inventory of the change finds one used by a tracked script or a procedure of the guide, in which case no rule for it is declared before the author decides. It SHALL NOT deny a command that only quotes them.

Source: tests/settings_deny/test_settings_deny_npm.py

#### Scenario: Other manager
- **WHEN** a command runs `yarn add <paquet>`, `pnpm install` or `bunx <paquet>`
- **THEN** a deny rule matches each command

### Requirement: npm, npx and node rules declared and pinned
The system SHALL declare the reduced block of design D0 (the forms of design D1 to D4 that #383 and this spec name, 273 rules) in the list function `regles_attendues()` of a settings-deny module with a `--json` entry point, passing the shared guard and the module's checks of design D5. Real-settings tests SHALL be skipped before the pose and fail on a partial pose (design D5). The session SHALL NOT edit the settings file.

Source: tests/settings_deny/test_settings_deny_npm.py

#### Scenario: Before the pose
- **WHEN** no rule of the block is in the settings
- **THEN** the real-settings tests are skipped with `règles npm et Node non posées` and the declared block still passes the shared guard and the matrix

#### Scenario: Partial pose
- **WHEN** the settings hold some rules of the block and lack another
- **THEN** the test fails with `garde npm : règle absente de .claude/settings.json : <règle>` naming the missing rule

#### Scenario: Write rule declared
- **WHEN** the block would hold a `Write(` rule
- **THEN** the shared guard fails and names the module and the rule

#### Scenario: Leading wildcard declared
- **WHEN** the block would hold a rule such as `Bash(*/npm install*)`
- **THEN** the module's tests fail and name the rule

### Requirement: The story quality grid check runs without a prompt
The system SHALL hold, posed by the author, the one allow rule `Bash(uv run tools/story_quality.py grid*)` of design D9 of mothra-session-guards, declared in a settings-deny module that passes the shared guard, and no allow rule covering `story_quality.py *`. The deny rules SHALL keep refusing `collect`, `review`, `analyse` and `coach`, alone and chained after `grid`. The session SHALL NOT edit the settings file.

Source: tests/settings_deny/test_settings_deny_story_quality_grid.py

#### Scenario: Grid allowed
- **WHEN** a session runs `uv run tools/story_quality.py grid --show --json`
- **THEN** the allow rule covers it and no deny rule matches it

#### Scenario: Chained refused subcommand
- **WHEN** a session runs `uv run tools/story_quality.py grid && uv run tools/story_quality.py collect`
- **THEN** a deny rule matches it, deny prevailing over allow

#### Scenario: Wider allow rule
- **WHEN** `permissions.allow` holds another rule naming `story_quality`
- **THEN** the real-file test fails and names it

### Requirement: The CI script's build and up are denied to the session, its run is allowed
The system SHALL deny the session `build` and `up` of `tools/ci_local.sh` through `bash`, `sh`, `zsh` and a direct launch, relative, absolute and home-relative paths, in the anchored form (local-ci-container design D12). The rules are added by the author. It SHALL NOT deny `run`, `--help`, reading the script or running its suite.

#### Scenario: Build from the session
- **WHEN** a command launches the CI script with `build` or `up` in any supported form
- **THEN** a deny rule matches it

#### Scenario: Run stays allowed
- **WHEN** a command launches the CI script with `run` and a branch, or runs its suite
- **THEN** no deny rule matches

### Requirement: The secret scan's declared examples list is written by the author only
The system SHALL deny the session editing the declared examples list of the secret scan, `tools/secret_scan_exemples.txt`, through three `Edit(` rules (relative, absolute and home-relative forms) and ten terminal write forms, redirection included, in every path form (design D6 of change pre-commit-secret-scan). It SHALL NOT deny a `git grep` or `git log` naming the list, reading or running the help of the scan tool, or running its suites. The session SHALL NOT edit the settings file.

#### Scenario: Writing the list
- **WHEN** a command appends to, overwrites, copies over, edits in place or truncates the examples list, by relative, absolute, home-relative or bare path
- **THEN** a deny rule matches it

#### Scenario: Allowed commands
- **WHEN** the session runs `git grep secret_scan_exemples`, reads the scan tool, runs its help or runs the secret scan suite
- **THEN** no deny rule matches

Source: tests/settings_deny/test_settings_deny_secret_examples.py

### Requirement: The book usage tool is denied to the session
The system SHALL deny the session every launch of the book usage tool, which reads all the workspace conversations, `--help` included, with every supported launcher, interpreter options included, and every path form (design D8 of change posture-book-usage). It SHALL NOT deny reading the tool's source, running its suite, or listing and reading its reports.

#### Scenario: Launch forms
- **WHEN** a command launches the tool, with or without `collect`, `report` or `--help`, by any supported launcher and path form
- **THEN** a deny rule matches it

#### Scenario: Allowed commands
- **WHEN** the session reads the tool, runs its suite or reads a book usage report
- **THEN** no deny rule matches

Source: tests/settings_deny/test_settings_deny_book_usage_tool.py

### Requirement: The library parity tool is denied to the session
The system SHALL deny the session every launch of the library parity tool, which connects to the database, through `uv run`, `python` or `python3` with or without options, by direct execution, in every path form (relative, home-relative, absolute, run tree, lab-folder link) and behind an environment variable set before the launcher. It SHALL NOT deny reading the tool, its Git history, running the parity suite or its settings test, or a test file whose name only ends with the tool's name.

#### Scenario: Launch forms
- **WHEN** a command launches the parity tool, with or without a subcommand or option, by any supported launcher, path form or leading environment variable
- **THEN** a deny rule matches it

#### Scenario: Allowed commands
- **WHEN** the session reads the tool, runs the parity suite or runs its settings test module
- **THEN** no deny rule matches

Source: tests/settings_deny/test_settings_deny_library_parity.py

### Requirement: The database rehearsal script is denied to the session
The system SHALL deny the session every launch of the database rehearsal script, `up`, `status`, `down` or none, through `bash`, `sh`, `zsh`, `uv run` or direct execution, in relative, home-relative and absolute path forms (design D11 of change flow-rebuild-rehearsal). It SHALL NOT deny a command that only names the script: reading it, searching the documentation, its Git history, or running its shell suite and the test runner.

#### Scenario: Launch forms
- **WHEN** a command launches the rehearsal script with any subcommand, by any supported launcher and path form
- **THEN** a deny rule matches it

#### Scenario: Naming the script
- **WHEN** the session reads the script, searches its name in the documentation or runs its shell suite
- **THEN** no deny rule matches

Source: tests/settings_deny/test_settings_deny_db_rehearsal.py

### Requirement: The worktree script's test seams are denied to the session
The system SHALL deny the session any command that sets the worktree script's test variables `WORKTREE_TERMINAL=` or `WORKTREE_NPM=` anywhere in the command, and any `export WORKTREE_*`, so that no session forces the dependency install. A variable read by the worktree script and not covered SHALL make the test fail. The system SHALL NOT deny running the worktree script without these variables, its suites, or a search of the variable names written without the equals sign.

#### Scenario: Seam set on a command
- **WHEN** a command sets `WORKTREE_TERMINAL=1` or `WORKTREE_NPM=` before the worktree script, after a pipe, `env` or `cd … &&`, under any shell or path form
- **THEN** a deny rule matches it

#### Scenario: Allowed commands
- **WHEN** the session runs the worktree script without a seam variable, runs its suite, or runs `git grep WORKTREE_NPM`
- **THEN** no deny rule matches

Source: tests/settings_deny/test_settings_deny_worktree_seams.py

### Requirement: Read rules on protected paths cover the absolute forms
The system SHALL deny the Read tool, in the `//**/…` and `~/**/…` forms, the four protected paths of the flow folder (exports, history, tables, sensitive-names list), the product-version list and the content folders (library, image, watch and excluded folders under their former and current names), including from a worktree; the whole watch folder SHALL also be denied in its relative form. The block SHALL hold only `Read(` rules. The session SHALL NOT edit the settings file.

#### Scenario: Absolute read from a worktree
- **WHEN** the Read tool targets a file under a protected flow path or a content folder by an absolute or home-relative path, from the workspace or a worktree
- **THEN** a deny rule matches it

#### Scenario: Watch folder
- **WHEN** the Read tool targets the watch sources file in any relative, absolute or home-relative form
- **THEN** a deny rule matches it

Source: tests/settings_deny/test_settings_deny_read_absolu.py

### Requirement: Extended readers are denied on the protected flow paths
The system SHALL deny `strings`, `xxd`, `od`, `rg` and `bat` on the exports, history and tables folders, the organisation referential, the sensitive-names list, the team-assets file and the product-version list of the flow folder, in every path form and on a copy of a protected file under the same name, with rules of the form `Bash(<reader> *<key>*)`. It SHALL NOT deny these readers on the reports, the flow configuration, the team-names extract or unrelated files.

#### Scenario: Extended reader on a protected path
- **WHEN** one of the five readers targets a protected path of the flow folder by relative, absolute or home-relative path, or a copy of a protected file
- **THEN** a deny rule matches it

#### Scenario: Readable flow files
- **WHEN** one of the five readers targets a report, the flow configuration or the team-names extract
- **THEN** no deny rule matches

Source: tests/settings_deny/test_settings_deny_lecteurs_flux.py

### Requirement: The flow-folder protections are aligned on the catalogue
The system SHALL deny the team catalogue's temporary file through three `Read(` rules and the 34 terminal readers of the catalogue, and the archive folder of the former team table through three `Read(` rules, the 34 readers and five listing commands. It SHALL hold no `Write(` or `NotebookEdit(` rule on the run folder, whose protection holds by its three `Edit(` rules. It SHALL NOT deny a command that only names these files. The session SHALL NOT edit the settings file.

#### Scenario: Temporary catalogue file
- **WHEN** a reader targets the catalogue's temporary file by any path form or a copy of it
- **THEN** a deny rule matches it

#### Scenario: Archive folder of the former team table
- **WHEN** a reader or listing command targets the archive folder or a file under it
- **THEN** a deny rule matches it

#### Scenario: Run folder
- **WHEN** the settings file is loaded
- **THEN** it holds the three `Edit(` rules of the run folder and none of the six former `Write(` and `NotebookEdit(` rules

#### Scenario: Naming allowed
- **WHEN** a `git grep` names the temporary file or the archive folder in the documentation
- **THEN** no deny rule matches

Source: tests/settings_deny/test_settings_deny_r84_flux_lab.py

## Open questions
1. The deny rules are enforced by Claude Code, not by this repository; only the matching of rules to sample commands is tested.
