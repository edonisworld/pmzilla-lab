# tooling-permission-guards Specification

## Purpose
The Claude Code settings file denies the assistant certain commands and file reads: commands that contact the real Jira, read or write the database, touch the keychain, or read sensitive or content folders. A test applies the rules to complete command lines.

## Requirements

### Requirement: Jira-contacting commands are denied
The system SHALL deny, for both the former and the current script names, every subcommand that contacts the real Jira (history test, collect, check with a ticket key; export diagnose, fields, export, and the retired teams-table and compare), whatever the launcher and however the script path is written.

#### Scenario: Launchers and paths
- WHEN a Jira-contacting command is formed from any supported launcher and any path form (relative, absolute, home-relative, bare)
- THEN a deny rule matches it

#### Scenario: Local subcommand
- WHEN a history check runs on local files without a ticket key
- THEN it is not denied

Source: tests/settings_deny/test_settings_deny.py (CommandesJira)

### Requirement: New subcommands must be classified
The system SHALL fail its tests when a subcommand is added to a Jira script without being classified as denied or local.

#### Scenario: Unclassified subcommand
- WHEN a script defines a subcommand unknown to the test lists
- THEN the test fails naming the script

Source: tests/settings_deny/test_settings_deny.py (test_toute_sous_commande_des_scripts_est_classee)

### Requirement: Sensitive Flux folder files are unreadable
The system SHALL deny reading the exports, history, tables, team-assets and sensitive-names files of the flow folder through the Read tool and through terminal reader commands (cat, head, tail, less, more, grep, awk, sed, cp) in every path form, while leaving the reports and the flow configuration readable.

#### Scenario: Terminal read
- WHEN a reader command targets a sensitive file by relative, absolute or home path
- THEN it is denied

#### Scenario: Allowed reads
- WHEN a reader command targets a report or the flow configuration, or an unrelated file
- THEN it is not denied

Source: tests/settings_deny/test_settings_deny.py (FichiersSensibles)

### Requirement: Keychain access is denied
The system SHALL deny commands that read the keychain generic password and any security command mentioning the Jira service.

#### Scenario: Keychain read
- WHEN a command reads the Jira token from the keychain
- THEN it is denied

Source: tests/settings_deny/test_settings_deny.py (test_trousseau)

### Requirement: Content folders are denied under old and new names
The system SHALL deny reading the watch content folders and the excluded folder, under both the former and the current folder names, through the Read tool, and the library, image and watch folders through terminal reader commands in every path form.

#### Scenario: Both names
- WHEN a former or current name of a watch or library folder is read through a terminal reader
- THEN it is denied, while reading a watch tool script is not

Source: tests/settings_deny/test_settings_deny.py (DossiersDeLaVeille, test_dossiers_de_contenu_refuses_aux_commandes_de_lecture)

### Requirement: Database access is denied to the session
The system SHALL deny the Jira import and comparison scripts, any calculation using the database as source, direct database clients, container exec and copy commands, dump and restore tools, reads of the backup folder (including through binary and compressed readers), the database administration, backup, startup, restore-test and throwaway-database test-launcher scripts, the library import script's import, verify and status subcommands, the library indexer's index, rename-collection, probe and status subcommands (through the tools folder and through the linked tools folder), and the control of the backup launchd job, whatever launcher and path form.

Source: tests/settings_deny/test_settings_deny.py (JiraEnBase)

#### Scenario: Database-reading calculation
- **WHEN** a flow or dependency calculation is run with the database as source
- **THEN** it is denied, while the same calculation from CSV files is allowed

#### Scenario: Direct clients
- **WHEN** a command runs a database client, container exec or a dump tool
- **THEN** it is denied

#### Scenario: Backup control
- **WHEN** a command loads, unloads, starts or inspects the backup job, or runs the backup script with options
- **THEN** it is denied

#### Scenario: Restore test
- **WHEN** a command launches the restore-test script with any supported launcher and path form
- **THEN** it is denied, while reading it and running its shell test suite are not

#### Scenario: Indexer writing or reading the database
- **WHEN** a command runs the indexer's index, rename-collection, probe or status subcommand with any supported launcher and path form, including the linked tools folder
- **THEN** it is denied

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
- WHEN the backup folder is read through the Read tool
- THEN a deny rule matches

Source: tests/settings_deny/test_settings_deny.py (test_psql_docker_exec_et_sauvegardes)

### Requirement: Wildcard semantics
The system SHALL treat the wildcard as matching any suffix, including empty, and everything else as literal when the test evaluates rules.

#### Scenario: Wildcard
- WHEN a pattern contains a wildcard
- THEN it matches longer commands but not shorter prefixes of the literal part

Source: tests/settings_deny/test_settings_deny.py (Outil)

### Requirement: Pre-rename rules retained
The system SHALL keep the earlier deny rules active during the English-name transition.

#### Scenario: Old rules
- WHEN the settings are loaded
- THEN every earlier-generation rule is still present

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

### Requirement: The settings file holds only deny rules and the session-start hook
The system SHALL keep in the shared settings file only a permissions section and a hooks section; the permissions section SHALL hold deny rules and the one allow rule that reads the organisation-context notes, with no other allow rule, no ask rule, default mode or additional directory, and the hooks section SHALL hold only the session-start hooks: the one that lists the due reviews of the cases module and the one that prints the queue reminder line from the reader's cache. Adding any other permission or hook SHALL make a test fail until the test expects it. Untested until implemented.

#### Scenario: Allow rule added
- **WHEN** an allow or ask rule is added to the settings file
- **THEN** the test fails

#### Scenario: Other hook added
- **WHEN** a hook other than the two session-start hooks is added
- **THEN** the test fails

#### Scenario: Reminder hook missing
- **WHEN** the session-start hooks hold only the due-reviews hook
- **THEN** the test fails and names the queue reminder

### Requirement: The install script is denied to the session
The system SHALL deny the session every launch of the install script's bootstrap and orchestrator, whatever the launcher and path form. The launchers are the shells, the Python launcher, the Python interpreters and direct execution. The path forms are relative, absolute, home-relative and bare. A launch through a shell command string that fetches the bootstrap SHALL also be denied. The denial SHALL cover the dry-run option, the help option and any subcommand of the orchestrator, including the pack subcommand planned by change install-migrate, because a dry run probes real services and pack copies the content folders. The deny rules are those of design D6, added to the settings file by the author; the session SHALL NOT edit the settings file and writes only the test cases, before the author's edit. The system SHALL NOT deny reading the script files, running the install-script test suite directly, or running the test runner. Untested until implemented.

#### Scenario: Launch forms
- **WHEN** a command launches the bootstrap or the orchestrator with any supported launcher and path form, with or without the dry-run option
- **THEN** a deny rule matches it

#### Scenario: Pack
- **WHEN** a command launches the orchestrator's pack subcommand
- **THEN** a deny rule matches it

#### Scenario: Allowed commands
- **WHEN** the session reads the script files, runs the install-script test suite, or runs the test runner filtered on that suite
- **THEN** no deny rule matches

### Requirement: The monthly-run orchestrator is denied to the session
The system SHALL deny the session every launch of the monthly-run orchestrator, whatever the launcher and path form. The launchers are the Python launcher, the Python interpreters and direct execution. The path forms are relative, absolute, home-relative and bare. The denial SHALL cover the dry-run option, the help option, the resume options and a command line that sets the orchestrator's test environment variables. The deny rules are those of design D14, added to the settings file by the author. The session SHALL NOT edit the settings file, and writes only the test cases, before the author's edit. The system SHALL NOT deny reading the orchestrator's file, running its test suite directly, or running the test runner. Untested until implemented.

#### Scenario: Launch forms
- **WHEN** a command launches the orchestrator with any supported launcher and path form, with or without the dry-run, help or resume options
- **THEN** a deny rule matches it

#### Scenario: Test variables on a command line
- **WHEN** a command line sets one of the orchestrator's test environment variables
- **THEN** a deny rule matches it

#### Scenario: Allowed commands
- **WHEN** the session reads the orchestrator's file, runs its test suite, or runs the test runner filtered on that suite
- **THEN** no deny rule matches

### Requirement: The off-site copies, the off-site script and its jobs are denied to the session
The system SHALL deny the session the reading and listing of any path inside the fixed off-site folder, through the Read tool and through terminal reader, listing and copy commands, in every path form (relative, absolute, home-relative). It SHALL deny every launch of the off-site backup script other than its help, with every supported launcher and path form, and the loading, unloading, starting and inspecting of its two launchd jobs. It SHALL NOT deny reading the script's source, running its test suite, or reading the off-site reports and status file of the lab data folder, which hold counts only. Untested until implemented.

#### Scenario: Reading an off-site copy
- **WHEN** a reader or listing command, or the Read tool, targets a path inside the off-site folder
- **THEN** it is denied

#### Scenario: Launching the script
- **WHEN** the off-site script is launched with the copy, setup or restore-test subcommand, by any launcher and path form
- **THEN** it is denied, while its help, the reading of its source and the run of its test suite are not

#### Scenario: Job control
- **WHEN** a command loads, unloads, starts or inspects one of the two off-site jobs
- **THEN** it is denied

### Requirement: Direct GitHub writes are denied to the session
The system SHALL deny the session, with `gh` written bare, by its absolute path or through `env`: the issue subcommands that create, edit, close, reopen, comment, delete, transfer, lock, unlock, pin, unpin or develop; every `gh api` command; label commands other than listing; Project commands other than listing and viewing projects, fields and items; release commands other than listing and viewing; repository creation, edition, deletion, renaming, archiving and forking; and the authentication commands that print the token, refresh, log in or log out. The deny rules are those of design D18, added to the settings file by the user; the session SHALL NOT edit the settings file and writes only the test cases, before the user's edit. The system SHALL NOT deny listing and viewing issues, listing labels, the authentication status, the queue reader, the GitHub write tool, reading the tools or running their suites. Untested until implemented.

#### Scenario: Issue write
- **WHEN** a command creates, edits, closes or comments an issue through `gh` directly, in any supported form
- **THEN** a deny rule matches it

#### Scenario: API call
- **WHEN** a command calls `gh api`, whatever its method and fields
- **THEN** a deny rule matches it

#### Scenario: Token
- **WHEN** a command asks `gh` to print the token
- **THEN** a deny rule matches it

#### Scenario: Allowed commands
- **WHEN** the session lists or views issues, runs the queue reader or the GitHub write tool, or runs their suites
- **THEN** no deny rule matches

### Requirement: The roadmap import tool is denied to the session
The system SHALL deny the session every launch of the one-shot roadmap import tool, its dry run, cross-check and help included, whatever the launcher (Python launcher, Python interpreters, direct execution) and path form (relative, absolute, home-relative, bare). The rules SHALL stay after the tool is removed. The session SHALL NOT edit the settings file and writes only the test cases. Untested until implemented.

#### Scenario: Launch forms
- **WHEN** a command launches the import tool with any supported launcher and path form, with or without the dry-run option
- **THEN** a deny rule matches it

#### Scenario: Cross-check
- **WHEN** a command launches the import tool's cross-check
- **THEN** a deny rule matches it

### Requirement: The worktree-finishing script is denied to the session
The system SHALL deny the session the launch of the worktree-finishing script through every supported launcher and path form (relative, absolute, home-relative, bare), help included, so that only the user runs it in the Terminal. The deny rules are added to the settings file by the author; the session writes only the test cases. It SHALL NOT deny reading the script, running its suite or running the test runner. Untested until implemented.

#### Scenario: Launch from the session
- **WHEN** a command launches the worktree-finishing script with any supported launcher and path form, with or without the help option
- **THEN** a deny rule matches it

#### Scenario: Reading and testing stay allowed
- **WHEN** a command reads the script, runs its shell suite directly or runs the test runner on that suite
- **THEN** no deny rule matches

### Requirement: The retention tool is denied to the session
The system SHALL deny the session every launch of the retention tool, whatever the subcommand (`check`, `purge`, with or without `--apply`), the launcher (Python launcher, Python interpreters, direct execution) and the path form (relative, absolute, home-relative, bare). The deny rules are those of design D18, added to the settings file by the user; the session SHALL NOT edit the settings file and writes only the test cases. The system SHALL NOT deny reading the tool's source, running its test suite or running the test runner. Untested until implemented.

#### Scenario: Launch forms
- **WHEN** a command launches `check` or `purge --apply` with any supported launcher and path form
- **THEN** a deny rule matches it

#### Scenario: Allowed commands
- **WHEN** the session reads the tool, runs its test suite, or runs the test runner filtered on that suite
- **THEN** no deny rule matches

### Requirement: The epic statuses tool and the verification script are denied to the session
The system SHALL deny the session every launch of the epic statuses tool and of the verification script of change `jira-gdpr-alignment`, whatever the launcher and path form, because both read the exports and the history cache. The system SHALL NOT deny reading their source, reading the epic statuses report in the flow reports folder, or running the epic statuses test suite. Untested until implemented.

#### Scenario: Launch
- **WHEN** a command launches either tool with any supported launcher and path form
- **THEN** a deny rule matches it

#### Scenario: Reading the report
- **WHEN** the session reads an epic statuses report of the flow reports folder
- **THEN** no deny rule matches

### Requirement: The cycles calculation is denied to the session
The system SHALL deny the session every launch of the `cycles` subcommand of the flow report tool, with or without a source option, because it always reads the database. It SHALL NOT deny `compute` from CSV files. Untested until implemented.

#### Scenario: Cycles without source option
- **WHEN** a command runs the flow report tool's `cycles` subcommand without `--source`
- **THEN** a deny rule matches it, while `compute` on a CSV file is not denied

### Requirement: The organisation referential is unreadable
The system SHALL deny reading the organisation referential of the flow folder through the Read tool and through the terminal reader commands (cat, head, tail, less, more, grep, awk, sed, cp) in every path form, while leaving the reports and the flow settings readable. Untested until implemented.

#### Scenario: Terminal read
- **WHEN** a reader command targets the referential by relative, absolute or home path
- **THEN** it is denied

#### Scenario: Flow settings
- **WHEN** a reader command targets the flow settings file
- **THEN** it is not denied

### Requirement: The session cannot launch the publication tool
The system SHALL deny the session every launch of the edition publication tool, whatever the launcher (Python launcher, Python interpreters, direct execution) and path form (relative, absolute, home-relative, bare), the help option included. The deny rules are those of design D16, added to the settings file by the user; the session SHALL NOT edit the settings file and writes only the test cases, before the user's edit. Untested until implemented.

#### Scenario: Launch forms
- **WHEN** a command launches the publication tool with any supported launcher and path form, with or without the help option
- **THEN** a deny rule matches it

### Requirement: The session cannot commit or push in the public copy
The system SHALL deny the session every commit and every push aimed at the local copy of the public repository, through a Git command given the copy's path, under its current and its permanent folder name, and through a change of directory into the copy followed by a commit or a push (design D16). Untested until implemented.

#### Scenario: Push in the public copy
- **WHEN** a command pushes or commits in the public copy, by giving its path to Git or after changing directory into it
- **THEN** a deny rule matches it

### Requirement: The session cannot read the product-version list
The system SHALL deny the session the reading of the local product-version list through the Read tool and through the terminal reader commands, in every path form (design D16). Untested until implemented.

#### Scenario: Product-version list
- **WHEN** a reader command or the Read tool targets the product-version list by relative, absolute or home path
- **THEN** it is denied

### Requirement: The publication guards leave the private work allowed
The system SHALL NOT deny reading the publication tool's text, running its test suite directly, running the test runner, or committing and pushing in the private workspace. Untested until implemented.

#### Scenario: Allowed commands
- **WHEN** the session reads the tool's text, runs its test suite, runs the test runner, or commits in the private workspace
- **THEN** no deny rule matches

### Requirement: The watch copy tool is denied to the session
The system SHALL deny the session every launch of the watch copy tool (copy, dry run, replace, verify, compare and parity), whatever the launcher (shells, the Python launcher, Python interpreters, direct execution) and the path form (relative, absolute, home-relative, bare), because each subcommand reads the real watch and triage data or writes the real database. The deny rules are those of design.md D12, added to the settings file by the author; the session SHALL NOT edit the settings file and writes only the test cases, before the author's edit. The system SHALL NOT deny reading the tool's file, running its test suite directly, or running the test runner, and SHALL NOT deny the collection and pre-triage scripts.

Source: tests/settings_deny/test_settings_deny_watch_copy_tool.py

#### Scenario: Launch forms
- **WHEN** a command launches the copy tool with any supported launcher and path form, with any subcommand, including the dry run
- **THEN** a deny rule matches it

#### Scenario: Allowed commands
- **WHEN** the session reads the copy tool's file, runs its test suite, or runs the weekly inventory of the pre-triage script
- **THEN** no deny rule matches

### Requirement: The doctor is allowed to the session, its wrapper is not
The system SHALL let the session run the doctor script in every launch form, with no deny rule matching it, and SHALL deny the session every launch form of the doctor's scheduled wrapper, which regenerates the dashboard and so opens a database session. The author adds the wrapper rules; the session SHALL NOT edit the settings file. Untested until implemented.

#### Scenario: Doctor launch
- **WHEN** the session runs the doctor script through the Python launcher, with or without its options
- **THEN** no deny rule matches

#### Scenario: Wrapper launch
- **WHEN** the session launches the doctor's scheduled wrapper by path or through a shell
- **THEN** a deny rule matches it

### Requirement: The session cannot delete or move files of the data folder
The system SHALL deny the session `rm`, `rmdir`, `mv` and `rsync` on any path that contains the data folder name, in every path form (relative, absolute, home-relative), so that the SQLite files and the labelled copy of design D11 are removed or moved by the user only. It SHALL NOT deny the test runner, the test suites, or commands on temporary folders. The rules are those of design D15, added by the author; the session writes only the test cases.

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
The system SHALL deny the session the check subcommand of the component tool, in every path form (relative, absolute, home-relative) and through `uv run`, `python` and `python3`, so that upstream sources are queried only by the daily run or by the user (fiche C18, design.md D14). It SHALL NOT deny the inventory subcommand, the test runner or the test suites. The deny rules are added to the settings file by the author; the session SHALL NOT edit the settings file and writes only the test cases, before the author's edit. Untested until implemented.

Source: to be covered by tests/settings_deny (task 6.1)

#### Scenario: Check denied
- **WHEN** a command runs the component tool's check subcommand through uv by relative or absolute path
- **THEN** a deny rule matches it

#### Scenario: Inventory allowed
- **WHEN** the session runs the component tool's inventory subcommand with the verify option, or the test runner
- **THEN** no deny rule matches

### Requirement: The morning summary is allowed to the session
The system SHALL NOT deny the session any launch of the morning summary script, with or without its JSON, language or notify options, whatever the launcher and path form: it opens only the cases read-only session and reads the lab data folder (design D11 of change morning-summary). The test SHALL show that these launches match no deny rule. The settings file SHALL gain no hook for the summary. Untested until implemented.

#### Scenario: Launch forms
- **WHEN** the session launches the summary script with any supported launcher and path form, with or without its options
- **THEN** no deny rule matches it

#### Scenario: No new hook
- **WHEN** the settings file is loaded after this change
- **THEN** its hooks are still only the two session-start hooks

### Requirement: The run tree is not editable by the session
The system SHALL deny the session the edit, write and notebook-edit tools on any path inside the run tree, and Git commands that change it through its folder option, in every path form. It SHALL NOT deny reading the run tree. The deny rules are those of design D6, added by the author; the session SHALL NOT edit the settings file and writes only the test cases. Untested until implemented.

#### Scenario: Edit in the run tree
- **WHEN** the session edits or writes a file inside the run tree, by absolute or home-relative path
- **THEN** a deny rule matches

#### Scenario: Read allowed
- **WHEN** the session reads a file inside the run tree
- **THEN** no deny rule matches

### Requirement: The run-tree script changes are denied to the session
The system SHALL deny the session the create and update subcommands of the run-tree script, with every supported launcher and path form. It SHALL NOT deny its status subcommand, its help, reading its source, running its suite or running the test runner. Untested until implemented.

#### Scenario: Update by the session
- **WHEN** a command launches the run-tree script's update or create subcommand, by any launcher and path form
- **THEN** a deny rule matches it

#### Scenario: Status allowed
- **WHEN** the session runs the status subcommand or the script's test suite
- **THEN** no deny rule matches

### Requirement: Denied scripts stay denied through their link and the run tree
The system SHALL make every deny rule that covers a script through the tools folder also cover its lab-folder link and its path inside the run tree, with every supported launcher. It SHALL NOT deny reading those scripts, running their suites or running the test runner. Untested until implemented.

#### Scenario: Backup through the run tree
- **WHEN** a command launches the backup script by its path inside the run tree or by its lab-folder link
- **THEN** a deny rule matches it

#### Scenario: Three path forms checked
- **WHEN** the settings test builds, for each denied script, its tools-folder, lab-folder link and run-tree forms
- **THEN** a deny rule matches each form

## Open questions
1. The deny rules are enforced by Claude Code, not by this repository; only the matching of rules to sample commands is tested.
