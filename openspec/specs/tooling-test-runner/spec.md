# tooling-test-runner Specification

## Purpose
Run every test suite of the repository with one command, or only the suites selected from the staged files, report one line per suite and a total, record the fingerprint of a green run for the commit hooks, and exit with a status that lets a command chain stop on failure.
## Requirements
### Requirement: One line per suite and a global total
The system SHALL run each Python test suite folder and each known shell test script, print one line per suite with its test count and verdict, and finish with a total line giving the number of tests and suites.

#### Scenario: All suites pass
- WHEN every suite passes
- THEN each suite is listed with its test count and an OK verdict, the total line states that all suites passed, and the exit code is 0

Source: tests/run_all/test_run_all.py (test_tout_reussit_total_et_code_zero)

### Requirement: Failure reporting
The system SHALL exit with code 1 when at least one suite fails, name the failing suites in the total line, print the tail of each failing suite's output, and still list the passing suites.

#### Scenario: A Python suite fails
- WHEN one suite contains a failing test and another passes
- THEN the failing suite is marked as failed with a diagnostic excerpt, the passing suite is still listed, and the exit code is 1

#### Scenario: A shell test fails
- WHEN a shell test reports a failure count above zero or exits non-zero
- THEN it is marked as failed under its shell label and counted in the failing suites

Source: tests/run_all/test_run_all.py (test_une_suite_en_echec_code_non_nul_et_diagnostic, test_un_test_shell_en_echec)

### Requirement: A suite that cannot start is a failure
The system SHALL count a suite whose code cannot be loaded or that reports no test count as failed.

#### Scenario: Import error in a suite
- WHEN a suite file fails at import time
- THEN the suite is reported as failed and the exit code is 1

Source: tests/run_all/test_run_all.py (test_suite_qui_ne_se_lance_pas_est_un_echec)

### Requirement: Filtering by suite name
The system SHALL run only the suites whose names are given as arguments, and SHALL exit with code 2 and a "no suite found" message when no suite matches or the repository has none.

#### Scenario: One name given
- WHEN a single existing suite name is passed
- THEN only that suite runs and the total covers it alone

#### Scenario: Unknown name
- WHEN a name matching no suite is passed
- THEN the system prints that no suite was found and exits with code 2

Source: tests/run_all/test_run_all.py (test_filtre_par_nom, test_nom_inconnu_ou_depot_sans_suite)

### Requirement: Verbose mode
The system SHALL print the full output of each passing suite only when the verbose option is given.

#### Scenario: Verbose option
- WHEN the verbose option is passed
- THEN the complete output of a passing suite appears; without it, only the summary line does

Source: tests/run_all/test_run_all.py (test_bavard_affiche_la_sortie_complete)

### Requirement: Warning when the judge-inputs check is skipped
The system SHALL, when the judge-inputs-changed environment variable is set to 1, print as the first lines a prominent warning that the judge-inputs test is ignored and that the commit message must say so, and SHALL print no warning otherwise.

#### Scenario: Variable set
- WHEN the variable equals 1
- THEN the first output line warns that the test is ignored and the second states what the commit message must declare

#### Scenario: Variable absent or 0
- WHEN the variable is absent or equals 0
- THEN no warning is printed

Source: tests/run_all/test_run_all.py (test_entrees_du_juge_changees_affichees_clairement_en_tete, test_sans_la_variable_aucun_avertissement)

### Requirement: Injectable root and dependencies
The system SHALL allow the repository root and the extra dependency options of the Python runner to be overridden through environment variables, so the runner can itself be tested on a fake repository.

#### Scenario: Fake root
- WHEN a root override points to a temporary repository
- THEN only the suites of that repository run

Source: tests/run_all/test_run_all.py (lancer helper); tests/run_all.sh header

### Requirement: Test suites needing no network or paid call
The system SHALL run suites offline and without paid calls, each in its own temporary workspace.

#### Scenario: Header contract
- WHEN the runner is documented
- THEN it states that no network call or paid call is made

Source: tests/run_all.sh (header comment). Not directly asserted by a test.

### Requirement: A listed shell suite that is absent is a failure
The system SHALL count a shell test script that is listed in the runner but whose file does not exist as a failed suite, print a line naming it, name it in the total line, and exit with code 1. When a filter by suite name is given, only the filtered suites SHALL be concerned.

#### Scenario: Listed script missing
- WHEN a listed shell script does not exist and no filter is given
- THEN a failure line names the suite, the total line counts it as failing, and the exit code is 1

#### Scenario: Filter on another suite
- WHEN a listed shell script is absent and the filter names a different, existing suite
- THEN only that suite runs and the exit code is 0

#### Scenario: Filter on the absent suite
- WHEN the filter names only the suite whose listed shell script is absent
- THEN the failure line names the script and the exit code is 1

Source: tests/run_all/test_run_all.py (test_suite_shell_listee_mais_absente_est_un_echec_nomme, test_suite_shell_absente_sans_effet_si_le_filtre_vise_une_autre_suite, test_filtre_sur_une_suite_shell_absente_ne_cache_pas_l_echec)

### Requirement: Every shell test script is listed
The system SHALL be covered by a test that fails when a shell test script exists under the tests folder and is neither listed in the runner nor declared as a helper, and the failure message SHALL name the script. Every helper declared in the runner SHALL exist, and the test SHALL fail when a declared helper is missing.

#### Scenario: Unlisted script
- WHEN a shell test script exists that the runner does not list and that is not declared as a helper
- THEN the test fails and names the script

#### Scenario: All listed
- WHEN every shell test script is listed or declared as a helper
- THEN the test passes

#### Scenario: Declared helper missing
- WHEN a helper declared in the runner does not exist
- THEN the test fails and names it

Source: tests/run_all/test_run_all.py (ScriptsShellDuDepot)

### Requirement: The runner refuses the variable reserved to git commit
The system SHALL refuse to start, exit with code 2 and run no suite when the environment variable that skips the post-commit evaluation run is defined, even if empty, and the message SHALL say that the variable is reserved to git commit.

#### Scenario: Variable defined
- WHEN the runner starts with the variable defined
- THEN it prints the reservation message, runs no suite and exits with code 2

Source: tests/run_all/test_run_all.py (test_variable_definie_refus_sans_rien_lancer, test_variable_definie_mais_vide_refusee_aussi)

### Requirement: A green full run records the index fingerprint
The system SHALL, when a run without any suite filter ends with every suite passing inside a git repository, write the tree fingerprint of the current index in the repository's private git folder. A run without a filter SHALL first erase the previous fingerprint, and a filtered run SHALL neither write nor erase it. Outside a git repository the run SHALL work and write nothing.

#### Scenario: Green full run
- WHEN a full run passes
- THEN the recorded fingerprint equals the fingerprint of the current index

#### Scenario: Failing or filtered run
- WHEN a full run has a failing suite
- THEN no fingerprint remains
- AND WHEN a filtered run passes, THEN no fingerprint is written

Source: tests/run_all/test_run_all.py (EmpreinteDeCommit)

### Requirement: Suites are selected from the staged files
The system SHALL provide a selector that reads the staged paths (added, copied, modified, renamed and deleted; a rename counts as its old and its new path) and selects a suite when a staged path is inside the suite folder, when a test file of the suite names the staged path or its module name (its file name for a data file), or when the staged path is a listed shell test script; it SHALL always select the guard suites that scan every tracked file. Documentation-only paths (the documentation and OpenSpec folders, the changelog, the readme, Markdown files of the output folder) SHALL need no other suite. Any other staged path that selects no suite, and any staged change to the session instructions file, the settings files, the runner, the hooks or the selector, SHALL make the selector require the complete run, even when other staged paths select suites. The selector SHALL print one line per selected suite with its reason and exit 0, or print that the complete run is required with the paths that caused it and exit 3; it SHALL exit 2 on a usage error or outside a git repository. It SHALL NOT run tests, write files, or select fewer suites than these rules give.

#### Scenario: Tool changed
- **WHEN** a tool file is staged and the test files of one suite name it
- **THEN** that suite and the always-selected guard suites are selected, each with its reason

#### Scenario: Documentation only
- **WHEN** only documentation and OpenSpec files are staged
- **THEN** only the always-selected guard suites are selected

#### Scenario: Unmapped code file
- **WHEN** a code file that no suite names is staged
- **THEN** the selector requires the complete run and names that file

#### Scenario: Hook changed
- **WHEN** a hook source is staged
- **THEN** the selector requires the complete run

#### Scenario: Last test file of a suite deleted
- **WHEN** the deletion of the only test file of a suite is staged
- **THEN** the selector requires the complete run

#### Scenario: Unmapped path among mapped ones
- **WHEN** a mapped tool file and an unmapped code file are staged together
- **THEN** the selector requires the complete run and lists no suite

#### Scenario: Outside a repository
- **WHEN** the selector runs on a folder that is not a git repository
- **THEN** it exits with code 2 and says so

Source: tests/select_suites/test_select_suites.py

### Requirement: A targeted green run records a targeted fingerprint
The system SHALL offer a runner option that runs the selector on the index and then the selected suites, or every suite when the selector requires the complete run, in which case the run SHALL behave exactly as a complete run, fingerprint included. A targeted run SHALL first erase the previous targeted fingerprint and, when every selected suite passes inside a git repository, SHALL write the tree fingerprint of the current index as the targeted fingerprint in the repository's private git folder, separate from the complete-run fingerprint. A targeted run SHALL NOT write or erase the complete-run fingerprint unless it escalated to a complete run, and runs filtered by suite name SHALL still write and erase nothing. The targeted option SHALL NOT be combined with suite names: the runner SHALL then exit with code 2, saying the option does not combine with names, and run nothing. When the selector fails with any other code than a selection or a complete-run requirement, the runner SHALL say so and run every suite as a complete run.

#### Scenario: Targeted green run
- **WHEN** the targeted option runs and every selected suite passes
- **THEN** the targeted fingerprint equals the fingerprint of the index and the complete-run fingerprint is unchanged

#### Scenario: Targeted red run
- **WHEN** a selected suite fails
- **THEN** no targeted fingerprint remains and the exit code is 1

#### Scenario: Escalation
- **WHEN** the selector requires the complete run
- **THEN** every suite runs and, on success, the complete-run fingerprint is written

#### Scenario: Filtered run
- **WHEN** a run filtered by suite name passes
- **THEN** neither fingerprint is written nor erased

#### Scenario: Option combined with names
- **WHEN** the targeted option is given together with a suite name
- **THEN** the runner exits with code 2 and runs no suite

Source: tests/run_all/test_run_all.py (LancementCible); tests/run_all/test_run_all.py (LancementCible.test_selecteur_en_echec_fait_un_passage_complet_avec_empreinte_complete)

