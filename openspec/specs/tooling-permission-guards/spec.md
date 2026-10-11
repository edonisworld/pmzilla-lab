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
The system SHALL keep in the shared settings file only a permissions section and a hooks section; the permissions section SHALL hold deny rules only, with no allow or ask rule, default mode or additional directory, and the hooks section SHALL hold only the session-start hook that lists the due reviews of the cases module. Adding any other permission or hook SHALL make a test fail until the test expects it.

#### Scenario: Allow rule added
- WHEN an allow or ask rule is added to the settings file
- THEN the test fails

#### Scenario: Other hook added
- WHEN a hook other than the session-start hook is added
- THEN the test fails

Source: tests/settings_deny/test_settings_autres_regles.py

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

## Open questions
1. The deny rules are enforced by Claude Code, not by this repository; only the matching of rules to sample commands is tested.
