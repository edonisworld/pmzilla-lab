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
The system SHALL run only the suites whose names are given as arguments. It SHALL exit with code 5 and the message `run_all : aucune suite ne correspond aux noms donnés (<noms>)` when names are given and none matches a suite, running no suite and writing or erasing no fingerprint (light-spec-finish design D11). It SHALL exit with code 2 and a "no suite found" message when no name is given and the repository has no suite.

#### Scenario: One name given
- WHEN a single existing suite name is passed
- THEN only that suite runs and the total covers it alone

#### Scenario: Unknown name
- WHEN a name matching no suite is passed
- THEN the system prints `run_all : aucune suite ne correspond aux noms donnés (inconnue)` and exits with code 5

#### Scenario: Unknown name in a repository without suites
- WHEN a name is passed in a repository that has no suite
- THEN the system exits with code 5

#### Scenario: One known name among unknown ones
- WHEN an existing suite name and a name matching no suite are passed
- THEN only the existing suite runs and the exit code is that of its run

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
The system SHALL provide a selector that reads the staged paths (added, copied, modified, renamed and deleted; a rename counts as its old and its new path) and selects a suite when a staged path is inside the suite folder, when a test file of the suite names the staged path or its module name (its file name for a data file), or when the staged path is a listed shell test script; it SHALL always select the guard suites that scan every tracked file.

#### Scenario: Tool changed
- **WHEN** a tool file is staged and the test files of one suite name it
- **THEN** that suite and the always-selected guard suites are selected, each with its reason

Source: tests/select_suites/test_select_suites.py

### Requirement: Documentation-only paths need no other suite
Documentation-only paths (the documentation and OpenSpec folders, the changelog, the readme, Markdown files of the output folder) SHALL need no other suite.

#### Scenario: Documentation only
- **WHEN** only documentation and OpenSpec files are staged
- **THEN** only the always-selected guard suites are selected

Source: tests/select_suites/test_select_suites.py

### Requirement: Unmapped paths and guarded files require the complete run
Any other staged path that selects no suite, and any staged change to the session instructions file, the settings files, the runner, the hooks or the selector, SHALL make the selector require the complete run, even when other staged paths select suites.

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

Source: tests/select_suites/test_select_suites.py

### Requirement: The selector reports its selection with one exit code per outcome and changes nothing
The selector SHALL print one line per selected suite with its reason and exit 0, or print that the complete run is required with the paths that caused it and exit 3; it SHALL exit 2 on a usage error or outside a git repository. It SHALL NOT run tests, write files, or select fewer suites than these rules give.

#### Scenario: Outside a repository
- **WHEN** the selector runs on a folder that is not a git repository
- **THEN** it exits with code 2 and says so

Source: tests/select_suites/test_select_suites.py

### Requirement: A targeted green run records a targeted fingerprint
The system SHALL offer a runner option that runs the selector on the index and then the selected suites, first erasing the targeted fingerprint and, when all pass in a git repository, writing the index tree as the targeted fingerprint in the private git folder, apart from the complete one. In a session it SHALL NOT write it unless the conditions of design D1 hold. Replaces the Mac-written fingerprint in a session.
Source: tests/run_all/test_run_all.py (LancementCible)

#### Scenario: Targeted green run
- **WHEN** the targeted option runs and every selected suite passes
- **THEN** the targeted fingerprint equals the fingerprint of the index and the complete-run fingerprint is unchanged

#### Scenario: Targeted red run
- **WHEN** a selected suite fails
- **THEN** no targeted fingerprint remains and the exit code is 1

#### Scenario: Session run proven by the container
- **WHEN** in a session the index-proof file holds a green line for the index tree with the selected portable suites, the Mac-bound part passes and the index did not change
- **THEN** the output holds `run_all : empreinte ciblée écrite (conteneur et Mac) pour l'index <court>` and the targeted fingerprint equals the index tree

#### Scenario: No container proof for the index
- **WHEN** in a session the index-proof file holds no green line for the index tree
- **THEN** the output holds `run_all : empreinte ciblée non écrite (preuve du conteneur absente pour cet index)` and no targeted fingerprint remains

#### Scenario: Container red
- **WHEN** in a session the container exits 1, even when the index-proof file already holds a green line for the index tree
- **THEN** the output holds `run_all : empreinte ciblée non écrite (conteneur rouge (code 1) : sa sortie est plus haut, les lignes ci_passage et ci_local)`, no targeted fingerprint remains and the exit code is 1

#### Scenario: Index changed during the run
- **WHEN** in a session `git write-tree` differs at the end of the run from its start
- **THEN** the output holds `run_all : empreinte ciblée non écrite (index modifié pendant le passage)` and no targeted fingerprint remains

#### Scenario: Mac-bound part red
- **WHEN** in a session a selected Mac-bound suite fails
- **THEN** the output holds `run_all : empreinte ciblée non écrite (suites propres au Mac rouges)` and the exit code is 1

#### Scenario: Mac-bound suites only
- **WHEN** in a session the selector selects only Mac-bound suites, they pass, and `git write-tree` did not change
- **THEN** the fake CI script is not called, no index-proof line is required, the output holds `run_all : empreinte ciblée écrite (conteneur et Mac) pour l'index <court>`, and the targeted fingerprint equals the index tree (design D1, R-20261104-17)

#### Scenario: Mac-bound suites only, red
- **WHEN** in a session the selector selects only Mac-bound suites and one fails
- **THEN** the output holds `run_all : empreinte ciblée non écrite (suites propres au Mac rouges)` and no targeted fingerprint remains

### Requirement: A targeted run escalates to a complete run when the selector requires it
When the selector requires the complete run, the targeted option SHALL run every suite and, outside a session, behave exactly as a complete run, fingerprint included. In a session it SHALL run as design D4 states for an escalated run and SHALL NOT write the complete-run fingerprint.
Source: tests/run_all/test_run_all.py (LancementCible)

#### Scenario: Escalation
- **WHEN** the selector requires the complete run outside a session
- **THEN** every suite runs and, on success, the complete-run fingerprint is written

#### Scenario: Escalation in a session
- **WHEN** the selector requires the complete run in a session and the run passes
- **THEN** the complete-run fingerprint is unchanged and only the targeted fingerprint may be written, under the conditions of design D1

### Requirement: A targeted or filtered run leaves the complete-run fingerprint alone
A targeted run SHALL NOT write or erase the complete-run fingerprint unless it escalated to a complete run, and runs filtered by suite name SHALL still write and erase nothing.

#### Scenario: Filtered run
- **WHEN** a run filtered by suite name passes
- **THEN** neither fingerprint is written nor erased

Source: tests/run_all/test_run_all.py (LancementCible)

### Requirement: The targeted option does not combine with suite names
The targeted option SHALL NOT be combined with suite names: the runner SHALL then exit with code 2, saying the option does not combine with names, and run nothing.

#### Scenario: Option combined with names
- **WHEN** the targeted option is given together with a suite name
- **THEN** the runner exits with code 2 and runs no suite

Source: tests/run_all/test_run_all.py (LancementCible)

### Requirement: A failing selector gives a complete run
When the selector fails with any other code than a selection or a complete-run requirement, the runner SHALL say so and run every suite as a complete run; in a session, as the escalated run of design D4, without writing the complete-run fingerprint.
Source: tests/run_all/test_run_all.py (LancementCible.test_selecteur_en_echec_fait_un_passage_complet_avec_empreinte_complete)

#### Scenario: Selector failure
- **WHEN** the selector fails with another code during a targeted run outside a session
- **THEN** the runner says so, runs every suite and, on success, writes the complete-run fingerprint

#### Scenario: Selector failure in a session
- **WHEN** the selector fails with another code during a targeted run in a session
- **THEN** the runner says so, runs as an escalated run of design D4, and the complete-run fingerprint is unchanged

### Requirement: The runner closes its standard input
The system SHALL close the runner's standard input before it runs any suite, so that no suite and no tool a suite launches can wait on the keyboard, whether the runner is launched in the foreground of a terminal, by a hook or by the session's shell. It SHALL NOT depend on the caller to redirect the input.

#### Scenario: Suite that reads its input
- **WHEN** a suite reads its standard input while the runner is launched in the foreground without redirection
- **THEN** the suite reads end of file at once and the run ends with its total line

Source: tests/run_all/test_run_all.py (EntreeEtDelai.test_une_suite_qui_lit_son_entree_lit_la_fin_de_fichier, EntreeEtDelai.test_une_suite_shell_qui_lit_son_entree_lit_la_fin_de_fichier)

### Requirement: A suite over its time limit is a named failure
The system SHALL stop any Python or shell suite that runs longer than a configurable time limit, with the processes it started, mark it failed with the key phrase `délai dépassé`, name it in the total line, go on with the next suites and exit with code 1. An invalid limit SHALL make the runner exit with code 2 before any suite.

#### Scenario: Suite that hangs
- **WHEN** one suite sleeps beyond the limit and another suite passes
- **THEN** the first suite's line holds `ÉCHEC : délai dépassé`, the second suite is still listed as passed, the total line names the first with `(délai dépassé)`, and the exit code is 1

#### Scenario: Processes of the stopped suite
- **WHEN** a suite over the limit has started a child process
- **THEN** no process of that suite remains after the runner ends

#### Scenario: No fingerprint
- **WHEN** a full run has a suite over the limit
- **THEN** no fingerprint remains

#### Scenario: Invalid limit
- **WHEN** the limit is set to a value that is not a positive whole number of seconds
- **THEN** the runner exits with code 2 and runs no suite

Source: tests/run_all/test_run_all.py (EntreeEtDelai)

### Requirement: Each suite line gives its duration and the slowest suites are listed
The system SHALL end each suite line, passed, failed or timed out, with the suite's wall-clock duration in the format of test-speed design D1, list up to ten slowest suites of the run under the heading of D1 before the total line, and add the total duration to the total line. It SHALL NOT move or reword the existing key phrases of the suite lines and of the total line, nor print the fingerprint lines before the total line.

#### Scenario: Two suites
- **WHEN** a run on a fake root has one quick suite and one suite that sleeps about a second
- **THEN** each suite line ends with a duration in seconds, the heading `Suites les plus lentes :` comes after the last suite line and before the total line, the sleeping suite is listed first, and the total line still holds `tous réussis`

#### Scenario: Failed and timed-out suites
- **WHEN** one suite fails and another exceeds the time limit
- **THEN** both lines still hold their failure key phrases and end with a duration, and the exit code is 1

#### Scenario: Fingerprint line stays last
- **WHEN** a complete run passes inside a git repository
- **THEN** the fingerprint line comes after the total line, as before

Source: untested until implemented (tests/run_all/test_run_all.py, task 1.1)

### Requirement: Suite durations are kept outside Git
The system SHALL append, after each suite, one line to the durations file of test-speed design D4, under the lab data folder resolved by the shared lab-paths module, with the fields of D4, the unittest time of a Python suite included. It SHALL NOT write a path, a test name or suite output into that file, nor write it into the repository, and a run on an injected root SHALL write no durations file unless the durations-file variable names one.

#### Scenario: Durations file named by the variable
- **WHEN** a complete run on a fake root runs with the durations-file variable set to a temporary file
- **THEN** that file holds a header line of ten fields and one line per suite with the kind `complet`, the suite name, a duration, its verdict and an empty reason field, and the Python suite's line holds the unittest time

#### Scenario: Injected root without the variable
- **WHEN** a run on a fake root runs without the durations-file variable
- **THEN** no durations file is written anywhere and the run ends as before

#### Scenario: Targeted and filtered runs
- **WHEN** a targeted run, then a run filtered by suite name, pass
- **THEN** their lines carry the kinds `ciblé` and `filtré`

Source: untested until implemented (tests/run_all/test_run_all.py, task 1.2)

### Requirement: Measuring never changes the outcome of a run
The system SHALL, when the lab data folder cannot be resolved or the durations file cannot be written, print once before the total line the key phrase of test-speed design D4 that gives the cause, without any path, and SHALL keep the run's exit code, suite lines and fingerprints as they would be without measuring. It SHALL NOT fail, stop or skip a suite because of a measure.

#### Scenario: Unwritable durations file
- **WHEN** the durations-file variable names a file in a folder that cannot be written and every suite passes
- **THEN** the output holds `run_all : durées non enregistrées (écriture impossible)`, the exit code is 0 and the complete-run fingerprint is written

Source: untested until implemented (tests/run_all/test_run_all.py, task 1.2)

### Requirement: Speed work keeps the runner's guards
The system SHALL keep, through every group of changes test-speed and test-speed-2, the runner's exit codes, the writing and erasing of its two fingerprints, its refusal of the variable reserved to git commit, its time limit and closed input, and the selection and fingerprint rules of the targeted option, in serial and parallel runs. The runner SHALL NOT gain an option that skips suites.

#### Scenario: Existing runner tests
- **WHEN** the runner's suite runs after each group of the change
- **THEN** every test of the fingerprint, targeted-run, reserved-variable, input and time-limit groups passes unchanged

#### Scenario: Targeted run after group 1
- **WHEN** a targeted run selects suites and they pass
- **THEN** the targeted fingerprint equals the index, the complete-run fingerprint is unchanged, and the exit code is 0, as before the change

#### Scenario: Parallel complete run
- **WHEN** a complete run with several jobs passes inside a git repository
- **THEN** the complete-run fingerprint equals the index, as in a serial run

### Requirement: The runner reads the finish lock only as stated and never writes a lock or a test-freeze file
The runner SHALL read the finish lock only as the requirement "The runner refuses to start during another process's finish" states (multi-session-piloting design D7). It SHALL NOT write or remove a test-freeze file or a lock, nor bypass the finish lock.

#### Scenario: Lock untouched
- **WHEN** a run ends, refused or not, while a lock folder exists
- **THEN** the lock folder and its files are unchanged

### Requirement: No test is removed or weakened to gain time
The system SHALL keep every suite and test that the complete run reports before changes test-speed and test-speed-2, with the same assertions and default time limit per suite, apart from the dead guards and the database list assertion named by test-speed-2 design D27. It SHALL NOT remove, skip, shorten or filter a test, nor loosen an assertion, for the sake of speed.

#### Scenario: Same counts before and after
- **WHEN** the complete run is launched on `main` before the change and on the branch after each group
- **THEN** the number of suites and the number of tests on the total line are the same, apart from tests added by the change

Source: tasks 9.2 and 10.1 (user check, comparison of the two total lines)

### Requirement: The runner keeps the database variables away from the suites
The system SHALL launch every suite without any environment variable whose name starts with `PMZILLA_LAB_DB_`, printing once the line of test-speed-2 design D29 when one was present, unless the throwaway-database mark `DBTEST_PORT` is set, in which case it SHALL pass them unchanged (D2). It SHALL NOT pass a caller's database password to a suite outside a throwaway run, nor change an exit code or a fingerprint for that reason.

#### Scenario: Variables exported in the terminal
- **WHEN** the address, port, password and a per-role password variable are exported and a fake suite records its environment
- **THEN** the suite sees none of them, the output holds the line `variables PMZILLA_LAB_DB_* retirées` once, and the exit code is 0

#### Scenario: Throwaway run
- **WHEN** `DBTEST_PORT` is set together with the port and password variables
- **THEN** the suite sees them unchanged and no removal line is printed

#### Scenario: Nothing exported
- **WHEN** no such variable is set
- **THEN** no removal line is printed and the output is as before

Source: untested until implemented (tests/run_all/test_run_all.py, task 1.2)

### Requirement: Database tests never reach the real database
The system SHALL let a database test use a database only when the mark `DBTEST_PORT` is a port other than the standard one, the port variable equals it, the address variable is unset or names that port, a password is set, and then a connection succeeds; otherwise the test SHALL be skipped with the message of test-speed-2 design D29. Every database helper SHALL apply this one rule (D1). It SHALL NOT attempt a connection before those conditions hold.

#### Scenario: Password exported, standard port
- **WHEN** a password is set, the port variable is unset or the standard port, and no mark is set
- **THEN** the guard answers no, no connection is attempted, and the database tests are skipped

#### Scenario: Configured port other than the mark
- **WHEN** the mark names one port and the port variable another
- **THEN** the guard answers no without any connection attempt

#### Scenario: Throwaway run
- **WHEN** the mark equals the port variable, is not the standard port, a password is set and the connection succeeds
- **THEN** the database tests run

Source: untested until implemented (tests/db, task 1.1)

### Requirement: The unknown-state test of ideas simulates the timeout
The system SHALL make the gh_issue test of an idea closed or commented without an answer simulate the timeout of each write call, without waiting and without the timeout variable (test-speed-2 design D15), keeping its checks (code 8, `state unknown`) and adding that the idea stays open and that each command attempted one write. It SHALL NOT remove, shorten or simulate the real blocking tests of the bounded-calls class.

#### Scenario: Write without an answer
- **WHEN** the test closes, then comments, an idea while every write call raises the timeout exception
- **THEN** both commands exit 8, the first error holds `state unknown`, the idea is still open, and one write was attempted per command

#### Scenario: Real blocking kept
- **WHEN** the bounded-calls class runs
- **THEN** its tests where the fake GitHub really hangs still pass with the real one-second limit

Source: tests/gh_issue/test_gh_issue_ideas.py (test_fermer_etat_inconnu_code_8), tests/gh_issue/test_gh_issue.py (Bornes); task 6.2

### Requirement: Speed changes keep the real-launch checks and the case isolation
The system SHALL stop the doctor suite's fake model server within milliseconds, keep on the real process the launch checks listed in test-speed-2 design D16, and give each case of the run-tree shell suite its own copy of a template repository built once per run of the suite (D17; the two other suites of D17 left with B9). It SHALL NOT change a check line of that shell suite, share a repository between cases, nor run in the process a test that checks the launch itself.

#### Scenario: Shell suite cases
- **WHEN** a case of the run-tree shell suite changes its repository
- **THEN** the next case starts from an unchanged copy of the template, and the suite reports the same check count as before

#### Scenario: Launch checks
- **WHEN** the gh_issue and doctor suites run after the in-process changes
- **THEN** the closed input, disabled prompts, missing executable, unknown option, help and no-traceback checks still run on a real process

Source: tests/run_worktree/test_run_worktree.sh (template built once per run, test-speed-2 D17); tests/doctor and tests/gh_issue: untested until implemented, as before (tasks 6.3 to 6.7 of test-speed-2, not re-checked by change tooling-specs-apres-b9)

### Requirement: Suites run in parallel with a settable number of jobs
The system SHALL run suites in parallel, up to the count of `RUN_ALL_JOBS` or the default of test-speed-2 design D19, each with its own process group, time limit, closed input, output file and temporary folder, and with `PYTHONDONTWRITEBYTECODE=1` (D21). A count of 1 SHALL give the serial run. An invalid count SHALL exit 2 before any suite. It SHALL NOT let a suite share another's temporary folder or process group.

#### Scenario: One job
- **WHEN** `RUN_ALL_JOBS` is 1
- **THEN** the suite lines, their order and the total line are those of a serial run

#### Scenario: Two jobs
- **WHEN** `RUN_ALL_JOBS` is 2 on a fake root of several suites
- **THEN** the same lines come in the same order, and each suite saw its own temporary folder and the bytecode variable

#### Scenario: Invalid count
- **WHEN** `RUN_ALL_JOBS` is 0 or a word
- **THEN** the runner prints `nombre de tâches invalide`, runs no suite and exits 2

Source: untested until implemented (tests/run_all/test_run_all.py, task 7.2)

### Requirement: Declared suites run alone
The system SHALL give each entry of its declared serial list a reason and a mode of run-all-faster-and-guarded design D2, and SHALL start each entry by the starting rules of the scenarios below. It SHALL NOT run two serial suites at the same time, start a parallel suite beside a serial suite, or start a `chevauche` entry beside an entry of the never-overlap list.

#### Scenario: Starting rule of a seule entry
- **WHEN** an entry of mode `seule` is due to start
- **THEN** it starts only when no other suite runs

#### Scenario: Starting rule of a chevauche entry
- **WHEN** an entry of mode `chevauche` is due to start
- **THEN** it starts only when four conditions hold: every parallel suite has started; at most half the jobs (at least one) are still running; no running entry is in the never-overlap list; and no other serial suite runs

#### Scenario: Starting rule without overlap
- **WHEN** the overlap switch is set to 0, or the run has one job or the throwaway-database mark
- **THEN** with the switch at 0 every serial entry starts only when no other suite runs, and with one job or the mark every suite runs one at a time

#### Scenario: Malformed serial list
- **WHEN** an entry of the serial list names no existing suite of its kind or has no mode
- **THEN** a test fails

#### Scenario: Run_all overlaps the tail
- **WHEN** a fake root holds the `run_all` serial suite in mode `chevauche`, several parallel suites that record their start and end, and two jobs
- **THEN** `run_all` starts after every parallel suite has started and may start before the last one ends, and no parallel suite starts after it

#### Scenario: Serial suite
- **WHEN** a fake root holds the `dbtest` serial suite in mode `seule` and parallel suites that record their start and end
- **THEN** it starts after every other suite, serial ones included, has ended, and no other suite runs during it

#### Scenario: Never-overlap suite still running
- **WHEN** an entry of the never-overlap list is still running when the other conditions hold
- **THEN** `run_all` starts only after that entry ends

#### Scenario: Overlap switched off
- **WHEN** `RUN_ALL_OVERLAP` is 0
- **THEN** every serial suite starts after every parallel suite has ended and the output holds `chevauchement coupé (RUN_ALL_OVERLAP=0)`

#### Scenario: Throwaway run
- **WHEN** `DBTEST_PORT` is set
- **THEN** no two suites overlap

#### Scenario: Unknown entry
- **WHEN** the serial list names a suite that does not exist
- **THEN** the list test fails and names it

Source: untested until implemented (tests/run_all/test_run_all.py, tasks 2.4 and 2.5)

### Requirement: Parallel output keeps the declared order
The system SHALL print suite lines in the declared order, each once it and every earlier suite have ended, with its own wall-clock duration, then the slowest list, the skipped line and the total line, and SHALL write fingerprints only after every suite ended green (test-speed-2 design D22, D23). A Python and a shell suite of one name SHALL be two suites. On an interruption it SHALL stop every running suite and write no fingerprint.

#### Scenario: Same name, two kinds
- **WHEN** a Python suite and a shell suite share a name
- **THEN** both run and both lines appear, and a filter by that name selects both

#### Scenario: Interruption
- **WHEN** the runner is interrupted while two suites run
- **THEN** no process of either suite remains and no fingerprint is written

Source: untested until implemented (tests/run_all/test_run_all.py, task 7.2)

### Requirement: The runner prints the total of skipped tests
The system SHALL print, after the slowest list and before the total line, the line `Tests sautés :` with the sum of the skipped counts of the Python suites and the number of skip lines of the shell suites (test-speed-2 design D25), in complete, targeted and filtered runs. It SHALL NOT change the suite lines, the total line, the durations file or the exit code for that count.

#### Scenario: Skips in both kinds
- **WHEN** a Python suite reports two skipped tests and a shell suite prints one line beginning with `saut :`
- **THEN** the output holds `Tests sautés : 3 (suites Python 2, branches shell 1)` before the total line, and the total line is unchanged

#### Scenario: Nothing skipped
- **WHEN** no test is skipped
- **THEN** the line gives 0

Source: untested until implemented (tests/run_all/test_run_all.py, task 8.1)

### Requirement: Dead skip guards are removed with proof
The system SHALL import the migration suite's helper in the views suite without a guard, so that an import error fails the suite, and SHALL run the psycopg-dependent tests of the migration suite without a psycopg skip, since the runner always installs it (test-speed-2 design D24). It SHALL keep the same test and skip counts under the runner, and SHALL NOT remove a test.

#### Scenario: Counts before and after
- **WHEN** the migration and views suites run under the runner before and after the removal
- **THEN** their test counts and skipped counts are equal

Source: untested until implemented (tests/db, tests/flow_views; tasks 8.3 and 8.4)

### Requirement: The runner refuses to start during another process's finish
The system SHALL make the runner, before any suite, exit 4 with the phrase of multi-session-piloting design D7 when the common Git folder of its root holds a live finish lock whose token the caller does not carry and the targeted freeze of change autonomous-trains-merge (design D18, through `freeze_scope()`) covers the run: the root's worktree is in the lock's list, the run writes `main`, the run tree or the ready list, or the lock holds no readable list; in complete, targeted and filtered runs alike. A matching token, a stale lock reported as design D6 states, or a root whose worktree the lock does not list SHALL change nothing. A refused run SHALL NOT run a suite, touch a fingerprint, write a durations line or wait. The runner SHALL NOT keep a freeze rule of its own beside `freeze_scope()`.

#### Scenario: Agent run during a finish
- **WHEN** a lock of a live process lists the root's worktree and the runner starts without a token, filtered on one suite
- **THEN** it exits 4 with `run_all : fin de branche en cours (<branche>), lancement refusé`, no suite runs, and both fingerprints are unchanged

#### Scenario: Run in a worktree outside the train
- **WHEN** a lock of a live process lists other worktrees and the runner starts without a token, filtered on one suite, in a worktree that the lock does not list
- **THEN** the run proceeds as without a lock

#### Scenario: Lock without a readable list
- **WHEN** a lock of a live process holds no readable list and the runner starts without a token
- **THEN** it exits 4 and no suite runs

#### Scenario: The finish's own runner
- **WHEN** the caller's token equals the lock's token
- **THEN** the run proceeds as without a lock

#### Scenario: Stale lock
- **WHEN** the lock names a process that no longer exists
- **THEN** the output holds `verrou de fin périmé, ignoré` and the run proceeds

#### Scenario: Injected root
- **WHEN** the runner runs on an injected root whose repository holds no lock while the test's own repository holds one
- **THEN** the run proceeds

### Requirement: A shell suite line shows its own skips
The system SHALL add to the verdict of a shell suite line the number of its output lines that begin with `saut :`, in the form of skips-visible design D3, when that number is above zero, whether the suite passed or failed, and SHALL use the same number in the shell part of the skipped line. It SHALL NOT change the line of a shell suite without such lines, the line of a suite over its time limit, the Python suite lines, the total line, the durations file or the exit code.

#### Scenario: Shell suite with skipped branches
- **WHEN** a shell suite passes and prints two lines beginning with `saut :`
- **THEN** its line holds `OK (sautés=2)`, the skipped line counts 2 for the shell suites, and the exit code is 0

#### Scenario: Failing shell suite with skipped branches
- **WHEN** a shell suite fails and prints one line beginning with `saut :`
- **THEN** its line holds its failure verdict with `sautés=1`, and the exit code is 1

#### Scenario: Shell suite without skips
- **WHEN** a shell suite passes without any such line
- **THEN** its line is `OK` followed by its duration, as before

Source: tests/run_all/test_run_all.py (TestsSautes: test_ligne_shell_reussie_avec_sauts_les_montre, test_ligne_shell_en_echec_avec_sauts_les_montre, test_ligne_shell_sans_saut_reste_comme_avant, test_ligne_shell_en_delai_garde_sa_ligne_de_delai)

### Requirement: The database-test guard compares ports as numbers
The system SHALL let the database-test guard answer yes only when the mark and the port variable are in the plain decimal form of test-db-guards design D1, the mark is not the standard port, and the port variable and address port equal the mark as numbers; every database helper keeps this one guard. It SHALL NOT attempt a connection when a condition fails, nor accept a form naming the standard port as a number.

#### Scenario: Standard port with a leading zero
- **WHEN** the mark and the port variable are both the standard port written with a leading zero and a password is set
- **THEN** the guard answers no, no connection is attempted, and the database tests are skipped with the existing message

#### Scenario: Sign or spaces
- **WHEN** the mark or the port variable carries a sign or spaces
- **THEN** the guard answers no without any connection attempt

#### Scenario: Address port with another form
- **WHEN** the address names the mark's port as a different number
- **THEN** the guard answers no without any connection attempt

#### Scenario: Plain form
- **WHEN** the mark and the port variable are the same plain port, not the standard one, a password is set and the connection double succeeds
- **THEN** the guard answers yes

Source: untested until implemented (tests/db/test_db.py, task 2.1)

### Requirement: The selector lists the suites that read the OpenSpec folder
The system SHALL give the suite selector an option that prints, with a reason, the always-selected guard suites and the suites of the declared list `tests/openspec_readers.txt` (design D6, question Q10), and exits 0, or 2 on a usage error, outside a repository, or on a missing or malformed list file. It SHALL NOT select a suite for the mere text `openspec` in its tests, read the index, run a test, write a file, or exit 3. Untested until implemented (suite `select_suites`).

#### Scenario: Declared suite
- **WHEN** the list file of a fake root names a suite
- **THEN** the option lists that suite with the reason `déclarée (tests/openspec_readers.txt)`, and the always-selected guard suite

#### Scenario: Suite naming the folder but not declared
- **WHEN** a suite of the fake root names `openspec/` in its test files and is not in the list file
- **THEN** the option does not list it

#### Scenario: Missing list file
- **WHEN** the fake root has no `tests/openspec_readers.txt`
- **THEN** the option exits 2

#### Scenario: Outside a repository
- **WHEN** the option runs on a folder that is not a git repository
- **THEN** it exits 2

### Requirement: A coverage test keeps the declared list of OpenSpec readers complete
The system SHALL provide a coverage test that fails, naming the suite, when a suite reads files under `openspec/` in the real tree without being listed or exempted in `tests/openspec_readers.txt`, when a listed or exempted suite no longer exists, or on a malformed or duplicated line (design D6). Comments, docstrings and fake repositories under a temporary folder SHALL NOT make a reader. Untested until implemented (suite `select_suites`).

#### Scenario: Unlisted real reader
- **WHEN** a suite of a fake root reads `openspec/config.yaml` through a root built from `__file__` and is not in the list file
- **THEN** the coverage check fails and names that suite

#### Scenario: Fake repository only
- **WHEN** a suite creates `openspec/changes/` under a temporary folder and names `openspec/` in a docstring
- **THEN** the coverage check does not flag it

#### Scenario: Listed suite removed
- **WHEN** the list file names a suite whose folder no longer exists under `tests/`
- **THEN** the coverage check fails and names that suite

#### Scenario: Real tree today
- **WHEN** the coverage test runs on the repository
- **THEN** it passes with the readers `workflow_commands`, `roadmap_model`, `build_edition` and `correspondance_suites` listed

### Requirement: The selector treats the hook modules as hooks
The system SHALL make the suite selector require the complete run when the secret scanner module or the sensitive-names module, both imported by the pre-commit hook, is staged, and SHALL always select the secret guard suite with its reason. It SHALL NOT let a targeted run cover a change to either module. Untested until implemented (suite `select_suites`).

#### Scenario: Scanner module staged
- **WHEN** only the secret scanner module is staged
- **THEN** the selector exits 3 and names that module

#### Scenario: Documentation only
- **WHEN** only documentation files are staged
- **THEN** the secret guard suite is selected with the reason "toujours sélectionnée : parcourt tous les fichiers suivis"

### Requirement: Mac-bound suites are declared in one list
The system SHALL read the Mac-bound suites from `tests/suites_mac.txt`, one `<suite>:<python|shell> # <raison>` line each, a suite being portable unless it has a verified reason of design D6. A coverage test SHALL fail, naming the entry, for a missing suite, a missing reason or a duplicate. An entry SHALL NOT leave the list before two green container replays, one commit per entry. Replaces "shell suites listed by default"; falls when the list is empty.
Source: tests/run_all/test_run_all.py

#### Scenario: Count of the Mac pass at the archive of tooling-proof-in-container
- **WHEN** the uncommented entries of `tests/suites_mac.txt` on main are counted on 2026-11-12 (design D6 of that change)
- **THEN** they are 22 suites, 18 shell and 4 Python, `forme_p_mac` included, added after T3 by change bash-sandbox-n2

#### Scenario: Entry for a missing suite
- **WHEN** the list names a suite that does not exist in that kind
- **THEN** the coverage test fails and names the entry

#### Scenario: Entry without reason
- **WHEN** a line of the list has no reason after `#`
- **THEN** the coverage test fails and names the line

#### Scenario: Suite moved into the image
- **WHEN** a suite retained as portable has had two green replays through `bash tools/ci_local.sh run --rejeu portable <suite>`
- **THEN** its line is removed in a commit of its own, and a `--portable` run launches it while a `--mac` run does not

### Requirement: The runner runs the portable or the Mac-bound suites on request
The system SHALL run with `--portable` every suite absent from the Mac-bound list, after the line `run_all : suites propres au Mac non lancées : <n> (<liste>)`, and with `--mac` only the listed suites (design D3). Neither SHALL write or erase a fingerprint, and each SHALL refuse `--staged` or a suite name with code 2.

#### Scenario: Portable run
- **WHEN** the runner gets `--portable` on a fake root where one suite is listed
- **THEN** that suite is not launched, the list line names it, and no fingerprint file is written

#### Scenario: Mac run
- **WHEN** the runner gets `--mac` on the same root
- **THEN** only the listed suite is launched

### Requirement: The runner finds the processor count on Linux
The system SHALL, without `RUN_ALL_JOBS` and when `sysctl -n hw.logicalcpu` is unreadable, take the processor count from `getconf _NPROCESSORS_ONLN` before falling back to one job (design D3). It SHALL NOT change the count on the Mac.

#### Scenario: No sysctl
- **WHEN** a fake `sysctl` fails and a fake `getconf` answers 8
- **THEN** the runner announces 4 suites at a time

### Requirement: The shell suites are listed in one sorted data file
The system SHALL read the shell suites from `tests/suites_shell.txt`, one `<path> <name> <interpreter>` line each, sorted by path, and the runner and the selector SHALL both read it. A line with a missing or extra field, an unknown interpreter or a path outside `tests/*.sh` SHALL make the runner exit 2 and name the line number. A test SHALL fail when the file is not sorted.

#### Scenario: Malformed line
- **WHEN** line 3 of the file has only two fields
- **THEN** the runner exits 2 with `run_all : tests/suites_shell.txt, ligne 3 mal formée` and launches no suite

### Requirement: The Source lines of the main specs are checked
The system SHALL provide a suite `spec_sources` that reads every `Source:` line of `openspec/specs/*/spec.md` and fails, naming the spec and the line, when a cited path or a cited test class or method does not exist. Known broken references SHALL be declared with a reason; lines marked untested until implemented SHALL be listed apart without failing.

#### Scenario: Cited method absent
- **WHEN** a `Source:` line cites `tests/x/test_x.py (Cas.test_trois)` and the file has no such method
- **THEN** the suite fails naming the spec, `tests/x/test_x.py::Cas.test_trois` and the line

Source: tests/spec_sources/test_spec_sources.py (SurUnDepotFactice.test_chemin_et_noms_casses_sont_nommes)

### Requirement: The longest suites start first
The system SHALL, when more than one job runs, start the parallel suites in the order of run-all-faster-and-guarded design D1, and print its order line, as the scenarios "Order by measure", "Declared order" and "Order line" state. It SHALL NOT change the suite selection, the order of the printed lines, or the start order of a one-job run. It SHALL NOT write to the durations file in order to compute the order, nor keep a static list of the longest suites.

#### Scenario: Order by measure
- **WHEN** more than one job runs, without the throwaway-database mark, and usable measures exist
- **THEN** suites without a measure start first, in declared order, and measured suites follow by decreasing estimate: the median of their last green complete-run durations read from the durations file, divided by their chunk count

#### Scenario: Declared order
- **WHEN** the run has one job, carries the throwaway-database mark, or has no usable measures
- **THEN** the runner uses the declared order

#### Scenario: Order line
- **WHEN** more than one job runs
- **THEN** the runner prints the order line of D1 once before the first suite

#### Scenario: Two jobs
- **WHEN** `RUN_ALL_JOBS` is 2 and the durations file gives suite B a longer median than suite A, both declared before B
- **THEN** B starts before A, the lines keep the declared order, and the output holds `ordre de départ selon les durées mesurées`

#### Scenario: Unmeasured suite
- **WHEN** a suite has no green complete line in the durations file
- **THEN** it starts before every measured suite

#### Scenario: Unusable durations file
- **WHEN** the durations file is missing or holds no usable line and two jobs run
- **THEN** the declared order applies and the output holds `ordre de départ déclaré (durées indisponibles)`

#### Scenario: One job
- **WHEN** `RUN_ALL_JOBS` is 1
- **THEN** the suites start in declared order and no order line is printed

Source: untested until implemented (tests/run_all/test_run_all.py, tests/suite_order/test_suite_order.py; tasks 2.2 and 2.3)

### Requirement: Test fake servers poll quickly
The system SHALL fail a test when a line under `tests/` writes `serve_forever` without `poll_interval`, because the default 0.5 s polling adds about 0.5 s to every test's shutdown. It SHALL NOT accept the call on that line alone.

#### Scenario: Call without a polling interval
- **WHEN** a helper under `tests/` calls `serve_forever` with no `poll_interval`
- **THEN** the guard test fails and names the file and line

Source: tests/run_all/test_sondage_serveur.py (SondageDesFauxServeurs)

### Requirement: A red suite lists all its failures
The system SHALL print, for a red suite and before the usual tail, every `FAIL:` and `ERROR:` line of a Python suite with its first exception line, or every `ECHEC`, `ÉCHEC` and `not ok` line of a shell suite. It SHALL print nothing the suite did not print.

#### Scenario: Four failures
- **WHEN** a suite has four failures
- **THEN** the four names appear before the tail, each with its assertion line

Source: tests/run_all/test_run_all.py (Lanceur)

### Requirement: The never-overlap suites are declared with a reason
The system SHALL declare in the runner one list of suites whose tests rely on short timing windows, bounded waits or duration measures, one `<suite>:<type>` entry each with its reason (run-all-faster-and-guarded design D2). A test SHALL fail, naming the entry, when an entry names no existing suite of its type or has no reason. It SHALL NOT start a serial suite of mode `chevauche` while an entry of this list runs.

#### Scenario: Entry without reason
- **WHEN** an entry of the list has no reason
- **THEN** the coverage test fails and names the entry

#### Scenario: Entry for a missing suite
- **WHEN** an entry names a suite that does not exist in that type
- **THEN** the coverage test fails and names the entry

Source: untested until implemented (tests/run_all/test_run_all.py, task 2.5)

### Requirement: Every complete run writes one journal line
The system SHALL append, at the end of every complete run (interruption included), one line with the fields of run-all-faster-and-guarded design D4 to the journal of complete runs: duration, verdict, context, `seul` or `concurrent`, highest load. Lines older than one year SHALL be purged at each write. It SHALL NOT write a line for a run that ended before its first suite or for a targeted or filtered run, nor write a path, a name, suite output or a person.

#### Scenario: Run alone
- **WHEN** a complete run on a fake root with the journal variable set passes and no other presence entry exists
- **THEN** the journal gains one line with verdict `vert` and `seul`, and its duration matches the total line

#### Scenario: Run beside a targeted run
- **WHEN** a live fake presence entry of kind `ciblé` exists during the complete run
- **THEN** the line holds `concurrent`, `1` others at most, and `ciblé` in the kinds

#### Scenario: Dead presence entry
- **WHEN** a presence entry names a dead process
- **THEN** it is ignored, removed, and the line holds `seul`

#### Scenario: Refused run
- **WHEN** a complete run exits with code 4, 6 or 7
- **THEN** no journal line is written

#### Scenario: Old lines
- **WHEN** the journal holds a line more than one year old before a complete run
- **THEN** that line is gone after the run and the header stays

Source: untested until implemented (tests/run_all/test_run_all.py, task 2.8)

### Requirement: The journal never changes the outcome of a run
The system SHALL, when the journal of complete runs cannot be written, print once, after the total line and before the fingerprint line, `run_all : journal des runners complets non écrit (<cause>)`, without a path. It SHALL keep the exit code, the suite lines and the fingerprints as they would be without the journal. It SHALL NOT fail, stop or skip a suite because of the journal or of the presence entries.

#### Scenario: Unwritable journal
- **WHEN** the journal variable names a file in a folder that cannot be written and every suite passes
- **THEN** the output holds `journal des runners complets non écrit`, the exit code is 0, and the complete-run fingerprint is written

Source: untested until implemented (tests/run_all/test_run_all.py, task 2.8)

### Requirement: A branch run proves the branch's suites on its tip
The system SHALL offer the runner option `--branch`, which runs on the clean tip the suites selected from the whole difference with `origin/main` and, when all pass, writes the branch fingerprint (change targeted-suites-admission, design D2). When the selector requires the complete run or fails, it SHALL run as a complete run. It SHALL NOT otherwise write or erase the complete or targeted fingerprint, nor skip a selected suite. Untested until implemented (suite `run_all`).

#### Scenario: Green branch run
- **WHEN** `--branch` runs on a clean work branch whose difference selects two suites, and both pass
- **THEN** the branch fingerprint in the worktree's private Git folder holds the tip's tree and both suites, `run_all : empreinte de branche écrite (2 suite(s))` is printed after the total line, and the complete and targeted fingerprints are unchanged

#### Scenario: Selector fails
- **WHEN** the selector exits with a code other than 0 or 3 during a `--branch` run
- **THEN** every suite runs as in a complete run, and on success the complete fingerprint holds the tip's tree

#### Scenario: Red branch run
- **WHEN** one selected suite fails
- **THEN** the runner exits 1 and no branch fingerprint exists afterwards

#### Scenario: Escalation
- **WHEN** the branch changes the runner itself
- **THEN** every suite runs and, on success, the complete fingerprint holds the tip's tree

#### Scenario: A selected name launched nothing
- **WHEN** the selector names a suite that the runner does not launch, so fewer suites ran than were selected
- **THEN** no branch fingerprint is written (it records only suites actually run), and `run_all : empreinte de branche non écrite (suites lancées : <n>, suites sélectionnées : <m>)` is printed

#### Scenario: The worktree changed during the run
- **WHEN** the tip's tree differs at the end of the run, or the worktree is no longer clean
- **THEN** no branch fingerprint is written, and `run_all : empreinte de branche non écrite (l'arbre du sommet a changé ou le worktree n'est plus propre)` is printed

### Requirement: The branch option refuses what it cannot prove
The system SHALL make `--branch` exit 2, running no suite and touching no fingerprint, on `main`, on a detached head, in a worktree that is not clean, or combined with suite names, `--staged`, `--portable` or `--mac` (design D2). It SHALL NOT record a branch fingerprint for a tree other than the tip's, and SHALL NOT bypass the guard of non-complete runs or the finish lock. During another process's finish, `--branch` SHALL follow the targeted freeze of change autonomous-trains-merge (design D18, through `freeze_scope()`), as the runner does: it exits 4 only when the lock's list holds the worktree or the lock holds no readable list (R-20261106-13 Q1).

#### Scenario: Dirty worktree
- **WHEN** `--branch` runs with a modified tracked file
- **THEN** it exits 2 with `run_all : --branch exige une branche de travail et un worktree propre`, and no suite runs

#### Scenario: During a finish
- **WHEN** `--branch` runs in a worktree that the live finish lock of another process lists
- **THEN** it exits 4 and no suite runs

#### Scenario: During a finish in other worktrees
- **WHEN** `--branch` runs in a clean worktree that the live finish lock of another process does not list
- **THEN** it runs as without a lock

#### Scenario: Lock without a readable list
- **WHEN** `--branch` runs while a live finish lock of another process holds no readable list
- **THEN** it exits 4 and no suite runs

### Requirement: The selector reads a range
The system SHALL give the selector the option `--range <base>...<tip>`, applying the rules of the index mode to the paths of that range and the tests of the given root, with the same output and codes (design D3). It SHALL NOT read the index in that mode, run a test, write a file, or select fewer suites than the index mode would for the same paths.

#### Scenario: Same rules as the index
- **WHEN** a range changes a tool that one suite names
- **THEN** the selector prints that suite and the always-selected guards and exits 0

#### Scenario: Guarded path in the range
- **WHEN** a range changes a hook
- **THEN** the selector exits 3 naming the hook

### Requirement: A green Mac pass records the Mac fingerprint
The system SHALL, when `bash tests/run_all.sh --mac` ends green on a clean worktree whose `HEAD` tree did not change, append that tree to `pmzilla-run-mac-ok` in the common Git folder, owner-only, having removed its line at start, and print `run_all : empreinte Mac écrite pour l'arbre <court>`; otherwise it SHALL print `run_all : empreinte Mac non écrite (<raison>)` (change ci-local-runner, design D7). It SHALL NOT write the complete, targeted or branch fingerprint, nor be read by pre-commit.

#### Scenario: Green Mac pass
- **WHEN** a `--mac` run ends green on a clean worktree
- **THEN** the Mac record holds the tree of `HEAD` and no other fingerprint changed

#### Scenario: Unclean worktree
- **WHEN** the worktree holds an untracked non-ignored file
- **THEN** the run prints `run_all : empreinte Mac non écrite (arbre non propre)` and writes nothing

### Requirement: A free-space refusal of the CI script stops a session run
The system SHALL treat code 8 of the CI script (free space below the minimum of the Colima machine) like codes 3, 5, 6 and 7 in a session run: exit 9 with the "container unavailable" phrase naming code 8 (change ci-local-image-prune, design D6). It SHALL NOT run the portable suites on the Mac instead, launch the Mac-bound suites of that run, write or erase a fingerprint, nor report code 8 as an unexpected code.

#### Scenario: CI script out of space
- **WHEN** in a session a targeted run selects a portable suite and the fake CI script exits 8
- **THEN** the runner exits 9 with `run_all : conteneur indisponible (code 8) : aucune suite portable lancée ; rien n'est écrit`, and the portable suite did not run on the Mac

### Requirement: In a session the bare complete run and the branch run are refused
The system SHALL, in a session, refuse a run without suite name, `--staged`, `--portable` or `--mac`, any `--branch` run and, from T2, any `--portable` run, with exit 6 and the phrase of design D3, before the freeze check, journaling it. It SHALL NOT run a suite, the selector or a guard, take a lock, or touch a fingerprint or the durations file. Replaces their session guard; permanent.
Source: tests/run_all/test_run_all.py (SessionPreuveParLeConteneur)

#### Scenario: Bare complete run in a session
- **WHEN** `bash tests/run_all.sh` runs with the session marker set, empty or not
- **THEN** the whole output is `run_all : lancement complet refusé en session : la preuve passe par le conteneur (bash tools/ci_local.sh run <branche>, puis bash tests/run_all.sh --mac)`, the exit code is 6, the complete, targeted and branch fingerprints are unchanged, no durations line is written, and neither the morning guard nor the runner guard is called

#### Scenario: Branch run in a session
- **WHEN** `bash tests/run_all.sh --branch` runs in a session
- **THEN** the whole output is `run_all : --branch refusé en session : la preuve passe par le conteneur (bash tools/ci_local.sh run <branche>, puis bash tests/run_all.sh --mac)`, the exit code is 6, the selector is not launched and no fingerprint changes

#### Scenario: Refusal during a finish
- **WHEN** a live finish lock is held and a session starts a bare complete run, then a `--branch` run, then a run filtered on one suite
- **THEN** the first two exit 6 with their phrase and the filtered run exits 4

#### Scenario: Refusals journaled
- **WHEN** a session starts a bare complete run, then a `--branch` run
- **THEN** the session journal gains two lines with verdict `refusé` and motives `conteneur-complet` then `conteneur-branche`, and holds no path

#### Scenario: Outside a session
- **WHEN** the session marker is absent and a complete run passes
- **THEN** it runs every suite and its total line holds `tous réussis`, and no output holds `refusé en session`

#### Scenario: Portable run in a session
- **WHEN** `bash tests/run_all.sh --portable` runs in a session, with the session marker empty or not, with or without a live finish lock
- **THEN** the whole output is `run_all : --portable refusé en session : la preuve passe par le conteneur (bash tools/ci_local.sh run <branche>, puis bash tests/run_all.sh --mac)`, the exit code is 6, no suite runs, no fingerprint changes, and the session journal gains one line with verdict `refusé` and motive `conteneur-portable`

#### Scenario: Other runs in a session
- **WHEN** a session starts a run filtered on one suite, a `--mac` run, or a `--staged` run whose selector selects a suite
- **THEN** none of them exits 6 or prints `refusé en session`

### Requirement: In a session the portable suites of a targeted or named run go to the container
The system SHALL, in a session, split `--staged` and named runs by the Mac-bound list (design D4), sending the portable suites to `ci_local.sh run --index` for `--staged`, `run --travail` for a named run, the others running here; an escalated `--staged` runs the complete container phases and the whole Mac pass. It SHALL NOT run a portable suite on the Mac in a session. Replaces session Mac targeted runs; permanent while the CI is the runner.
Source: untested until implemented (T2)

#### Scenario: Split of a targeted run
- **WHEN** in a session the selector selects one portable suite and one Mac-bound suite, and a fake CI script records its calls
- **THEN** the output holds `run_all : suites portables envoyées au conteneur : 1 ; suites propres au Mac lancées ici : 1`, the fake CI script received `run --index` with the portable suite, and only the Mac-bound suite ran on the Mac

#### Scenario: Named run in a session
- **WHEN** in a session `bash tests/run_all.sh a m` names one portable suite `a` and one Mac-bound suite `m`, and a fake CI script records its calls
- **THEN** the fake CI script received `run --travail a`, never `run --index`, only `m` ran on the Mac, and the targeted fingerprint is neither written nor erased

#### Scenario: Escalated targeted run in a session
- **WHEN** in a session the selector requires the complete run
- **THEN** the fake CI script receives the complete mode, every Mac-bound suite runs here, and the complete-run fingerprint is neither written nor erased

#### Scenario: Outside a session
- **WHEN** the session marker is absent and a targeted run selects a portable suite
- **THEN** the suite runs on the Mac as before and the CI script is not called

### Requirement: In a session an escalated targeted run keeps the morning guard
The system SHALL, in a session, refuse with exit 6 and motive `matin` an escalated `--staged` when `tools/morning_state.sh runner` answers a code other than 0 or is missing, after the root and data-folder refusals (design D3). It SHALL NOT then call the container or erase a fingerprint, nor read the module for a named run, a targeted `--staged` or `--mac`. Kept by R-20261104-17; falls with the escalation.
Source: tests/run_all/test_run_all.py (SessionClaudeCode)

#### Scenario: Watch or backup of the day running
- **WHEN** in a session a `--staged` run escalates (selector absent, failing or requiring the complete run) and the fake morning module exits 1
- **THEN** the runner exits 6 with `veille ou sauvegarde du jour en cours`, the fake CI script is not called, no suite runs, the targeted and complete fingerprints are unchanged, and the session journal gains a line with verdict `refusé` and motive `matin`

#### Scenario: Unreadable or missing morning module
- **WHEN** the fake morning module exits with a code other than 0 and 1, or is absent next to the runner, during an escalated `--staged` in a session
- **THEN** the runner exits 6, the refusal stays closed, and the fake CI script is not called

#### Scenario: Environment of the morning module
- **WHEN** the fake morning module records its arguments and environment during an escalated `--staged` in a session
- **THEN** it received `runner` without option, the account's home and data folder and the fixed `PATH` `/usr/bin:/bin:/usr/sbin:/sbin`, and no variable of the caller

#### Scenario: Runs that do not read the morning module
- **WHEN** in a session a named run, a targeted `--staged` and a `--mac` run start
- **THEN** the fake morning module is not called

### Requirement: An unavailable container stops a session run without a Mac fallback
The system SHALL exit 9 with `run_all : conteneur indisponible (code <c>) : aucune suite portable lancée ; rien n'est écrit` when `ci_local.sh` answers 3, 5, 6 or 7, or is not found next to the runner (code 127), to a session run of design D4. It SHALL NOT run the portable suites on the Mac instead, launch the Mac-bound suites of that run, nor write or erase a fingerprint. New exit code; replaces nothing; permanent while the CI is the runner.
Source: untested until implemented (T2)

#### Scenario: Stale image
- **WHEN** in a session a targeted run selects a portable suite and the fake CI script exits 5
- **THEN** the runner exits 9 with `run_all : conteneur indisponible (code 5) : aucune suite portable lancée ; rien n'est écrit`, the portable suite did not run on the Mac, and the targeted fingerprint is absent

#### Scenario: Nothing launched on exit 9
- **WHEN** in a session a targeted run selects one portable suite and one Mac-bound suite, and the fake CI script exits 3
- **THEN** the runner exits 9, neither suite ran on the Mac, no fingerprint is written or erased, and no durations line is written

#### Scenario: CI script not found
- **WHEN** in a session a targeted run selects a portable suite and `tools/ci_local.sh` is absent next to the runner
- **THEN** the runner exits 9 with `run_all : conteneur indisponible (code 127) : aucune suite portable lancée ; rien n'est écrit`, and the session journal gains a line with verdict `refusé` and motive `conteneur-indisponible`

#### Scenario: Container answering
- **WHEN** the fake CI script exits 0 or 1
- **THEN** the runner never exits 9

### Requirement: An unexpected container code stops a session run
The system SHALL exit 1 with the "code inattendu" phrase of design D4 when `ci_local.sh` answers a session run with a code other than 0, 1, 3, 5, 6, 7 and 127 (R-20261104-17). It SHALL NOT then run a Mac-bound suite, write or erase a fingerprint, or write a durations line. Replaces the Mac part run after such a code; permanent while the CI is the runner.
Source: tests/run_all/test_session_conteneur.py

#### Scenario: Usage, refused input or interruption
- **WHEN** in a session a named run and a targeted `--staged`, each with one portable and one Mac-bound suite, and an escalated `--staged` start while the fake CI script exits 2, 4 or 130
- **THEN** each run exits 1 with `run_all : le script du conteneur a rendu un code inattendu (<c>) : aucune suite lancée ; rien n'est écrit`, no Mac-bound suite runs, no durations line is written, the fingerprints are unchanged, and the session journal gains a line with verdict `refusé` and motive `conteneur-code-inattendu`
