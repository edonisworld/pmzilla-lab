# watch-pipeline

## Purpose

The daily watch run (`watch.sh`): ordered steps, failure handling, notifications, index freshness, the daily check of the uv dependency cache, optional PostgreSQL copy, and the scheduler template.

Source of truth: `tests/watch_sh/test_watch_sh.py`, `tools/watch.sh`, `tools/com.pmzilla.watch.plist`.

## Requirements

### Requirement: Run the steps in a fixed order
The system SHALL run, when the local model service responds: collection, scoring, apply, shares, ranked reading list, library indexing of both content folders directly into the database, the BM25 probe, then the dashboard. On full success it SHALL print a timestamp header, end with "Veille terminée sans erreur", exit 0 and raise no notification but the morning summary of a scheduled run. Scripts SHALL be called through their linked path. It SHALL NOT run the former import or verification of the PostgreSQL copy, the former indexer of a frozen copy, or any parity comparison with a former path, whether or not a former parity marker file is present in the data folder.

#### Scenario: Nominal path
- **WHEN** every step succeeds and the run is manual
- **THEN** the steps are called in the order above, the import script is never called, exit code is 0, and no notification is raised

#### Scenario: Former parity marker left
- **WHEN** every step succeeds and a former parity marker file is still present in the data folder
- **THEN** the steps are the same as without it: no former indexer and no parity comparison is run, and the run script names neither

#### Scenario: Nominal scheduled path
- **WHEN** every step of a scheduled run succeeds
- **THEN** the only notification is the morning summary, sent after the dashboard, and exit code is 0

Source: `tests/watch_sh/test_watch_sh.py` (test_chemin_nominal_enchaine_toutes_les_etapes_dans_l_ordre, test_journal_horodate_et_les_deux_dossiers_indexes); the scheduled path is untested until implemented.

### Requirement: Degrade gracefully without the model service
The system SHALL, when the model service does not respond, collect, write the plain reading list, skip scoring and indexing, say they are postponed, generate the dashboard, and exit 0 without recording an index timestamp.

Source: `tests/watch_sh/test_watch_sh.py` (test_ollama_absent_liste_simple_sans_pre_tri_ni_index)

#### Scenario: Service absent
- **WHEN** the model service is unreachable
- **THEN** only collect, plain digest and dashboard run, the output says pre-sorting and indexing are postponed, and exit code is 0

### Requirement: Warn when the index becomes stale
The system SHALL, when the model service is absent and the last successful indexation is older than a configurable number of days (default applied for missing or invalid values), print a staleness message and raise one desktop notification, without changing the exit code. The age SHALL come from the timestamp file only. A missing or unreadable timestamp SHALL be treated as unknown and notified. A recent index SHALL give no notification, including at the exact threshold boundary. A successful indexation SHALL refresh the timestamp; a failed or skipped one, including one stopped because the database does not answer, SHALL leave it. The system SHALL NOT read the date of any index file.

Source: `tests/watch_sh/test_watch_sh.py` (test_ollama_absent_*, test_seuil_*, test_repere_illisible_traite_comme_inconnu, test_indexation_reussie_ecrit_le_repere_et_echouee_le_laisse)

#### Scenario: Too old
- **WHEN** the service is absent and the last indexation is older than the limit
- **THEN** a message states the age in days and the limit, one notification is raised, and exit code is 0

#### Scenario: Invalid limit value
- **WHEN** the limit setting is not a number
- **THEN** the default limit is used

#### Scenario: No timestamp, old SQLite file present
- **WHEN** the service is absent, the timestamp file is missing and a stray file named like a former SQLite index is left in the data folder
- **THEN** the indexation is treated as unknown and one notification is raised, and the stray file is neither read nor dated

### Requirement: Continue after a failing step and report every failure once
The system SHALL log a failing collection, scoring chain, reading list or indexation, continue with later steps, exit 1, end with "Veille terminée avec N étape(s) en échec" naming failed steps in order, and raise one single notification naming them. An indexation stopped because the database does not answer (indexer exit code 2) SHALL be logged with the "base PostgreSQL injoignable" phrase and named with the step label "indexation (base injoignable)" of design D9 of the archived change db-lot5-watch-triage; any other indexing failure keeps the label "indexation". A failure of the pre-sort chain (scoring, apply, shares, digest) SHALL stop that chain at the first failing command, fall back to the plain reading list, and still index. A failing notification SHALL be logged and SHALL NOT change the exit code. A failing indexation SHALL NOT prevent the reading list or the dashboard. A postponed attempt (requirement "Postpone a day the database or the network did not let run") SHALL end with the same summary line and exit code, and SHALL raise its notification only when it is the first postponement of the day; it SHALL NOT notify again for a later postponed attempt of the same day.

Source: `tests/watch_sh/test_watch_sh.py` (test_collecte_en_erreur_est_journalisee_et_la_suite_continue, test_echec_du_pre_tri_bascule_sur_la_liste_non_triee_et_arrete_la_chaine, test_echec_de_l_indexation_est_dit_et_notifie, test_plusieurs_echecs_nommes_dans_l_ordre, test_liste_a_lire_en_erreur, test_notification_impossible_ne_change_pas_le_code_de_sortie); the postponed attempt is untested until implemented.

#### Scenario: Scoring fails
- **WHEN** the apply command fails
- **THEN** shares and digest are not run, the plain list is written, indexing runs, exit is 1 and the summary names the pre-sort step

#### Scenario: Several failures
- **WHEN** collection, scoring and indexing fail
- **THEN** one notification and one summary line list them in that order

#### Scenario: Database does not answer
- **WHEN** the indexer exits with code 2
- **THEN** the log says the database is unreachable, the summary and the single notification name "indexation (base injoignable)", the dashboard runs, the timestamp is unchanged and exit is 1

#### Scenario: Second postponed attempt of the day
- **WHEN** a second scheduled launch of the same day is postponed again
- **THEN** the summary line names the failed step, the exit code is 1 and no notification is raised

### Requirement: Never fail the run on the dashboard
The system SHALL log a failing dashboard generation, keep exit code 0 and raise no notification for it. The morning summary of a scheduled run SHALL still be sent.

Source: `tests/watch_sh/test_watch_sh.py` (test_echec_du_dashboard_ne_fait_pas_echouer_la_veille); the summary after a dashboard failure is untested until implemented.

#### Scenario: Dashboard error
- **WHEN** the dashboard fails
- **THEN** "Tableau de bord non généré" is logged and exit is 0

#### Scenario: Dashboard error on a scheduled run
- **WHEN** the dashboard fails during a scheduled run whose other steps succeed
- **THEN** the morning summary is called and is the only notification

### Requirement: Resolve the watch folder through the shared path logic
The system SHALL index the current-named watch folder, and SHALL stop the step with an error naming the migration tool when only a former-named folder exists.

#### Scenario: Former folder only
- **WHEN** only the former folder exists
- **THEN** it is not indexed and the error names the migration tool

### Requirement: Stay inside the user's home in tests and templates
The scheduler file SHALL be a template carrying a label, a script path and one log path used for both outputs, all relative to a home placeholder, with no real absolute path, no former watch name and no code-tree folder (neither the development checkout nor the run tree), and SHALL render into a valid property list when the placeholder is replaced. The script path the template launches SHALL be the run script's lab-folder link, in the folder from which the run script derives its tools, its code root and its content root, so that the launched script finds its tools in the code tree the link points to. It SHALL NOT name a code-tree folder, so that switching the code tree changes the links only.

Source: `tests/watch_sh/test_watch_sh.py` (Plist, including test_le_chemin_du_plist_est_le_dossier_des_outils_de_watch_sh; test_aucune_commande_reelle_et_rien_hors_du_faux_home); the code-tree folder rule untested until implemented

#### Scenario: Rendering
- **WHEN** the placeholder is substituted
- **THEN** the result parses as a property list whose program argument is the substituted script path

#### Scenario: Script path and tools folder agree
- **WHEN** the rendered program argument is compared with the tools folder declared by the run script
- **THEN** the program's folder equals that tools folder, the code root and the content root are declared from it, and the program is the run script

#### Scenario: No code-tree folder
- **WHEN** the raw template is read
- **THEN** it names neither the development checkout nor the run tree

### Requirement: Check the uv dependency cache once a day without blocking the run
The system SHALL, at the start of each run and before collection, read the uv version and the Python version uv selects in the code root, and compare them with the versions recorded in the data folder. When both are recorded and unchanged it SHALL do nothing and print nothing about the cache. When either changed or is not recorded, it SHALL build a throwaway script made only of the dependency header of the Discovery posture's wake script, read in the code root, followed by a single `import yaml` line (no wake code is run), copy it into two distinct temporary folders, run it from the first with network access and then, only if that succeeded, from the second in offline mode, both times by relative path and with the Python version read in the code root, and remove both folders. On success it SHALL record both versions and print that the cache was filled and verified offline. On failure (network run, offline run, missing wake script, or a wake script without a dependency header, in which case nothing is run) it SHALL record nothing, so the check is retried at the next run, print a message pointing to the manual procedure of the installation guide ("After an update of uv"), and raise one desktop notification. When the uv or Python version cannot be read, it SHALL print that the cache check is impossible, raise no notification and run nothing. The cache check SHALL NOT change the steps run nor the exit code, including when the notification itself fails, and SHALL NOT read the Python version or the wake script in the content root. The repository root SHALL pin a Python version.

Source: `tests/watch_sh/test_watch_sh.py` (CacheUv, including test_le_controle_du_cache_precede_la_collecte); the code root: a new CacheUv test, untested until implemented

#### Scenario: Versions unchanged
- **WHEN** the recorded uv and Python versions equal the current ones
- **THEN** no throwaway script is run and the output does not mention the cache

#### Scenario: uv updated
- **WHEN** the uv version differs from the recorded one
- **THEN** the throwaway script runs with network then offline, the output says "Cache de uv rempli et vérifié hors ligne", the new version is recorded, no notification is raised and exit code is 0; a second run does not check again

#### Scenario: Offline run fails
- **WHEN** the offline run of the throwaway script fails
- **THEN** one notification and one output line mention "After an update of uv", the recorded version is unchanged, collection and dashboard still run, and exit code is 0

#### Scenario: Network run fails
- **WHEN** the run with network access fails
- **THEN** the offline run is not attempted, one notification is raised and exit code is 0

#### Scenario: Version unreadable
- **WHEN** uv cannot report the Python version
- **THEN** the output says "Contrôle du cache de uv impossible", no notification is raised, no throwaway script is run and exit code is 0

#### Scenario: Throwaway script content
- **WHEN** the check runs against the real wake script
- **THEN** each throwaway copy holds exactly the wake script's dependency header and, apart from blank lines, only `import yaml`

#### Scenario: Code root differs from the content root
- **WHEN** the code root and the content root pin different Python versions and hold different wake-script headers
- **THEN** the check reads the version and the header of the code root

### Requirement: Probe the BM25 index after a good indexation, without blocking
The system SHALL run the indexer's BM25 probe after a successful indexation. A probe exiting with code 3 SHALL be logged as an unreadable BM25 index naming the "Damaged BM25 index" section of the installation guide and SHALL raise one notification pointing to it; any other non-zero code SHALL be logged with its code and raise one notification. A failing probe SHALL NOT count as a failed step, SHALL leave the exit code unchanged and SHALL let later steps continue. The system SHALL NOT repair anything (rebuilding the index is done by the user alone) and SHALL NOT run the probe when indexing fails or is skipped.

#### Scenario: Unreadable BM25 index
- **WHEN** the probe exits with code 3
- **THEN** the log names the unreadable index and the guide section, one notification is raised, the dashboard still runs and exit is 0

#### Scenario: Other probe failure
- **WHEN** the probe exits with another non-zero code
- **THEN** the log gives the code, one notification is raised, and exit is 0

#### Scenario: Probe passes
- **WHEN** the probe exits with 0
- **THEN** no notification is raised

#### Scenario: Indexing failed
- **WHEN** the indexation fails
- **THEN** the probe is not run

### Requirement: Check the database before collecting and skip the day when it does not answer
The system SHALL, after the uv cache check and before collection, run the database check of the collection tool with a configurable bounded wait (default applied for a missing or invalid value); in scheduled mode, the network check of the requirement "Check the network on a host of the collection" SHALL come between the uv cache check and the database check. When the check succeeds the run SHALL continue as before. When it fails, the system SHALL write the log line of design D5 of the archived change db-lot5-watch-triage for an unreachable database or for absent tables, SHALL skip collection, the pre-sort chain, both reading lists and the library indexing in that attempt, SHALL still generate the dashboard, SHALL name the step "base de données" among the failed steps with the summary line of the failed-steps rule, and SHALL exit 1. When the check reports an unreachable database, in any mode, the system SHALL then log the "postponed" key phrase of design D3, record the day as postponed and raise the notification only if it is the first postponement of the day, so that a later scheduled launch of the same day retries it (requirement "Postpone a day the database or the network did not let run"); it SHALL NOT treat the day as done. When the check reports absent tables, the system SHALL record the day as failed and raise the single notification. It SHALL NOT start the database, SHALL NOT write any article file, reading list or state outside the database other than the run record and the lock of design D2 and D4, and SHALL NOT run any step on a former state file. Untested until implemented for the postponement.

Source: tests/watch_sh/test_watch_sh.py, tools/watch.sh

#### Scenario: Database ready
- **WHEN** the check exits 0
- **THEN** the steps run in their usual order after it and the exit code follows the existing rules

#### Scenario: Database down at the scheduled time
- **WHEN** the check exits with the unreachable-database code after the wait, on the first attempt of the day
- **THEN** the log contains the skipped-day line of the archived design D5 followed by the postponed key phrase of design D3, collection, scoring, digests and indexing are not called, the dashboard is generated, exactly one notification names "base de données", the summary is "Veille terminée avec 1 étape(s) en échec : base de données", the record says postponed and the exit code is 1

#### Scenario: Database down on a manual run
- **WHEN** the script is launched without option and the check exits with the unreachable-database code
- **THEN** the record says postponed with the manual trigger, and a later scheduled launch of the same day between the due time and the latest start runs the day's steps

#### Scenario: Tables absent
- **WHEN** the check exits with the absent-tables code
- **THEN** the log names the missing migration, the same steps are skipped, the record says failed, and the exit code is 1

#### Scenario: Invalid wait setting
- **WHEN** the wait setting is not an integer
- **THEN** the check is called with the default wait

### Requirement: Never fall back to the former watch and triage files
The system SHALL NOT refer to the former watch and triage state files in the run script, SHALL NOT pass them to any step, and SHALL treat a step that exits because the database stopped answering during the run as a failed step under the existing failure rules, including the plain-list fallback of the pre-sort chain.

Source: tests/watch_sh/test_watch_sh.py, tools/watch.sh

#### Scenario: Database lost during the pre-sort chain
- **WHEN** the check succeeds, then scoring exits with the unreachable-database code and the plain-list fallback exits with it too
- **THEN** both are logged as failures, the summary names them in order, and no former state file is read or written

#### Scenario: Script text
- **WHEN** the run script is read
- **THEN** it names neither former state file

### Requirement: The daily run uses no SQLite file and works without one
The system SHALL run the daily watch without naming, opening, creating or testing for existence any SQLite file, and without calling the SQLite command-line tool, in the run script and in every step it calls. A run in a data folder that holds no SQLite file SHALL follow the same steps, the same exit code and the same notifications as before the files were deleted, and SHALL leave no SQLite file behind.

#### Scenario: Script text
- **WHEN** the run script is read
- **THEN** it holds no SQLite file name and no call to the SQLite command-line tool

#### Scenario: Empty data folder
- **WHEN** a full run with every step succeeding is made in a data folder that holds no SQLite file
- **THEN** the steps are called in order, the run ends with "Veille terminée sans erreur" and exit code 0, and the data folder still holds no SQLite file

#### Scenario: Staleness without an index file
- **WHEN** the model service is absent and no indexation timestamp exists
- **THEN** the age is unknown and notified, and no SQLite file is consulted to estimate it

### Requirement: Run the weekly component check just before the dashboard, without blocking
The system SHALL, at every run, immediately before the dashboard and after the steps that depend on the database check, call the component check with its due option (design.md D4), whatever the outcome of the database check and whether the model service answers; the database check SHALL remain the first step after the uv cache check. On exit code 1 it SHALL raise one notification with the fixed text of design.md D4; on any code other than 0 and 1 it SHALL log "Veille des composants impossible" with the code and raise one notification. The component step SHALL NOT be added to the failed steps, SHALL NOT change the exit code, including when the network is unreachable, the check fails or the notification itself fails, and SHALL NOT prevent the dashboard. Untested until implemented.

Source: to be covered by tests/watch_sh/test_watch_sh.py (task 4.1)

#### Scenario: Nothing new
- **WHEN** every step succeeds and the fake check exits 0
- **THEN** the check is called with the due option just before the dashboard, no notification is raised, and the run ends with "Veille terminée sans erreur" and exit code 0

#### Scenario: Something new
- **WHEN** the fake check exits 1
- **THEN** exactly one notification with the fixed text is raised, the dashboard runs, and the exit code is 0

#### Scenario: Check impossible
- **WHEN** the fake check exits 2
- **THEN** the log says "Veille des composants impossible", one notification is raised, the summary names no component step, and the exit code is unchanged

#### Scenario: Database down
- **WHEN** the database check fails
- **THEN** the component check is still called before the dashboard, and the summary names only "base de données"

### Requirement: The daily run never cleans the uv cache nor installs a component
The system SHALL NOT run `uv cache clean` or `uv cache prune` in the run script, and SHALL NOT install, upgrade or download any component from it (no `brew install`, `brew upgrade`, `brew update`, `ollama pull`, `npm install`, `docker pull` or `uv sync`); the existing uv cache check stays the only uv cache step and keeps its never-blocking rule. Untested until implemented.

Source: to be covered by tests/watch_sh/test_watch_sh.py (task 4.2)

#### Scenario: Script text
- **WHEN** the run script is read
- **THEN** it holds none of the forbidden commands

#### Scenario: Recorded calls
- **WHEN** a full run is made with recording fake commands on the path
- **THEN** no recorded call is a cache-cleaning or installing command

### Requirement: Record the run of the day
The system SHALL keep, in the lab data folder, one record of the watch run of the day: date, trigger (calendar, catch-up or manual), start time, end time, outcome (done, failed, postponed or interrupted) and the count of retries of an interrupted run. It SHALL write it atomically, owner-only, before the first step and after the last. A missing, unreadable or other-day record SHALL mean that no run took place today; the system SHALL NOT read the watch log to decide. Untested until implemented.

#### Scenario: Record after a run
- **WHEN** a scheduled run ends with exit code 0
- **THEN** the record holds today's date, the trigger, the start and end times and the outcome done, and only its owner can read it

#### Scenario: Unreadable record
- **WHEN** the record is malformed and a scheduled launch comes after the due time
- **THEN** the log holds the "record unreadable" key phrase of design D8 and the run starts

#### Scenario: Record of another day
- **WHEN** the record holds yesterday's date
- **THEN** a scheduled launch after the due time runs the day's steps

### Requirement: Date the run of the day in the Europe/Paris time zone
The system SHALL compute the date of the run of the day, the record's times and the comparisons with the due time and the latest start time in the Europe/Paris time zone, comparing wall times, and SHALL NOT use the system time zone for these decisions. A new day SHALL start at midnight in Europe/Paris. The lock's age SHALL be measured in elapsed seconds. The current instant SHALL be injectable for tests (design D5). Untested until implemented.

#### Scenario: Process in another time zone
- **WHEN** the system time zone is not Europe/Paris and a scheduled launch comes at an instant after the due time in Europe/Paris but before it in the system time zone, with no run of today
- **THEN** the day's steps run and the record holds the Paris date and the Paris start time

#### Scenario: Just after midnight in Paris
- **WHEN** a scheduled launch comes just after midnight in Europe/Paris, while the system time zone is still on the previous day, and the record says yesterday's run ended
- **THEN** the launch exits 0 without writing anything, since the Paris day is new and the due time is not reached

#### Scenario: Clocks go forward
- **WHEN** two scheduled launches come after the due time on the day the clocks go forward in Europe/Paris, with no run of today before them
- **THEN** the first runs the day's steps and records that day's date, and the second exits 0 without writing anything

#### Scenario: Clocks go back
- **WHEN** scheduled launches come during both occurrences of the repeated hour, before the due time, on the day the clocks go back in Europe/Paris, then one comes after the due time
- **THEN** the launches in the repeated hour exit 0 without writing anything, and the launch after the due time runs the day's steps once, recording that day's date

### Requirement: Run at most once a day when scheduled
The system SHALL, in scheduled mode, start the day's run only between the configurable due time and the configurable latest start time, and only when no run of today has ended other than postponed. Otherwise it SHALL exit 0 without writing to the log, the record or the lock. A failed run SHALL count as done. It SHALL NOT run the day's steps twice in one day in scheduled mode, apart from the single retry of an interrupted run. Untested until implemented.

#### Scenario: Mac powered off at the scheduled time
- **WHEN** the Mac starts between the due time and the latest start time and no run took place today
- **THEN** the catch-up launch runs the day's steps once

#### Scenario: Before the due time
- **WHEN** a scheduled launch comes before the due time
- **THEN** it exits 0, the log, the record and the lock are unchanged, and no tool is called

#### Scenario: After the latest start time
- **WHEN** a scheduled launch comes after the latest start time of design D5 and no run of today has ended
- **THEN** it exits 0, writes nothing and calls no tool, and the day stays missed

#### Scenario: Already run today
- **WHEN** today's record says the run ended, done or failed
- **THEN** a scheduled launch exits 0 and writes nothing

### Requirement: Retry an interrupted run once a day
The system SHALL treat a record of today that says started, while no live process holds the lock, as an interrupted run. In scheduled mode it SHALL run the day's steps again once, log the "interrupted run retried" key phrase of design D3 and count the retry in the record. A run interrupted again the same day SHALL be recorded as interrupted and SHALL NOT be retried. Untested until implemented.

#### Scenario: First interruption
- **WHEN** today's record says started with no retry and no live process holds the lock
- **THEN** the next scheduled launch logs the key phrase, records one retry and runs the day's steps

#### Scenario: Second interruption
- **WHEN** today's record says started with one retry and no live process holds the lock
- **THEN** the next scheduled launch records the outcome interrupted, calls no tool, writes nothing to the log and exits 0

### Requirement: Postpone a day the database or the network did not let run
The system SHALL record the day as postponed when the database check reports an unreachable database, in any mode, or when, in scheduled mode, no host of the collection answers within a configurable wait; it SHALL skip the day's steps and let the next scheduled launch of the day retry until the latest start time. It SHALL raise at most one postponement notification per day. Any other database check error SHALL count as failed. Untested until implemented.

#### Scenario: Database down, then up
- **WHEN** the first launch of the day finds the database down and the next scheduled launch finds it up
- **THEN** the first records postponed, logs the postponement key phrase of design D3, notifies once and exits 1; the second runs the day's steps

#### Scenario: Second postponement of the day
- **WHEN** a second scheduled launch of the same day finds the database down again
- **THEN** it records postponed, exits 1 and raises no notification

#### Scenario: No network at boot
- **WHEN** no host of the active sources answers within the wait
- **THEN** the log holds the "no network" key phrase of design D3, the failed step is named "réseau", nothing is collected and the record says postponed

#### Scenario: Watch tables missing
- **WHEN** the database check exits 5
- **THEN** the record says failed and a later scheduled launch of the day does not run

#### Scenario: Other database check error
- **WHEN** the database check exits with a code other than 0, 4 or 5
- **THEN** the log keeps the unreachable-database line, the record says failed and a later scheduled launch of the day does not run

### Requirement: Check the network on a host of the collection
The system SHALL provide a network check of the watch that tries the hosts of the active sources, one short-timeout connection each, until one answers or a configurable wait is over, and exits 0 or 6 with the key phrases of design D3. It SHALL fetch no feed, write nothing and name no host in its output. It SHALL NOT be run by a manual launch of the watch. Untested until implemented.

#### Scenario: One host answers
- **WHEN** the first active source's host does not answer and the second does
- **THEN** the check prints the "network ready" key phrase and exits 0, and no feed is fetched

#### Scenario: No host answers
- **WHEN** no active source's host answers within the wait
- **THEN** the check prints the "network down" key phrase, names no host and exits 6

### Requirement: Never run two watch runs at the same time
The system SHALL take an exclusive lock in the lab data folder before starting the day's run, read the record again once it holds it, and release the lock at exit whatever the exit code. It SHALL NOT remove a lock it does not hold. A lock whose owner is gone, or older than a configurable age, SHALL be logged as stale and taken over. A scheduled launch that finds the lock held SHALL exit 0 silently. Untested until implemented.

#### Scenario: Two triggers at wake
- **WHEN** the calendar job and the catch-up job start together
- **THEN** one runs the day's steps and the other exits 0 without writing to the log

#### Scenario: Stale lock
- **WHEN** the lock's owner process no longer exists
- **THEN** the log holds the "stale lock" key phrase of design D4 and the run proceeds

#### Scenario: Lock released after a failure
- **WHEN** a step fails and the run exits 1
- **THEN** the lock no longer exists

### Requirement: Refuse to run when the record cannot be written
The system SHALL check, before the lock and any step, that the run record can be written. When it cannot, it SHALL start no run, in any mode, and exit 4 with the "record not writable" key phrase of design D8. A scheduled launch SHALL notify at most once per day, remembered outside the data folder, and stay silent afterwards that day. It SHALL NOT relaunch the day's steps at each scheduled launch. Untested until implemented.

#### Scenario: Data folder read-only
- **WHEN** two scheduled launches of the same day find the data folder not writable
- **THEN** both call no tool and exit 4; the first logs the key phrase and notifies once, the second writes nothing and does not notify

#### Scenario: Manual launch
- **WHEN** the record cannot be written and the script is launched without option
- **THEN** it prints the key phrase, calls no tool, raises no notification and exits 4

### Requirement: A manual run forces the day's run but respects the lock
The system SHALL, when launched without a scheduled-mode option, run the day's steps whatever the record says and whatever the time, and record the manual trigger. It SHALL refuse with exit code 3 and the "run in progress" key phrase of design D4 when another run holds the lock. It SHALL NOT wait for the lock nor run the network check. An unknown option SHALL be refused with exit code 2, and no tool SHALL be called. Untested until implemented.

#### Scenario: Manual run after today's run
- **WHEN** today's record says done and the script is launched without option
- **THEN** the day's steps run and the record names the manual trigger

#### Scenario: Manual run during a run
- **WHEN** another run holds the lock
- **THEN** the manual launch prints the "run in progress" key phrase, calls no tool and exits 3

#### Scenario: Unknown option
- **WHEN** the script is launched with an option other than the two scheduled-mode options
- **THEN** it exits 2, calls no tool and writes neither the record nor the lock

### Requirement: Show a catch-up run in the log
The system SHALL, on a run started by the catch-up job, keep the usual timestamp header unchanged and print the "catch-up run" key phrase of design D8 on the next line. A scheduled launch that does not run SHALL print nothing. It SHALL NOT raise a notification for the catch-up itself. Untested until implemented.

#### Scenario: Catch-up run
- **WHEN** the catch-up job runs the day's steps
- **THEN** the line after the timestamp header is the catch-up key phrase and the notifications are those of the run only

#### Scenario: Calendar run
- **WHEN** the calendar job runs the day's steps
- **THEN** the log holds no catch-up line

### Requirement: Scheduler templates of the calendar and catch-up jobs
The system SHALL provide a catch-up template that launches the watch job's lab-folder link with the catch-up option, at load and at a periodic interval fixed in the template, logging both outputs to the watch log, with no calendar schedule, no keep-alive, no real path and no former watch name. The watch template SHALL pass the scheduled-mode option. The due time SHALL equal the watch template's calendar time. Untested until implemented.

#### Scenario: Catch-up template
- **WHEN** the catch-up template is rendered
- **THEN** it parses as a property list whose program is the same link as the watch template's, with the catch-up option, run at load, a periodic interval, and neither calendar schedule nor keep-alive

#### Scenario: Due time and calendar time agree
- **WHEN** the run script's due time is compared with the watch template's calendar schedule
- **THEN** their hour and minute are equal

### Requirement: End a scheduled run with the morning summary
The system SHALL, at the end of a scheduled run whose outcome is done or failed, after the dashboard and the final write of the run record, call the summary script through its linked path with the notify option, the scheduler variable and the labels of the failed steps (design D1). It SHALL NOT call it after a postponed day, an interrupted run not retried, a launch with nothing to do, a refused launch or a manual run. Untested until implemented.

#### Scenario: Calendar run done
- **WHEN** a calendar run ends without failed step
- **THEN** the summary script is called once, after the record says done, with no failed step label

#### Scenario: Catch-up run
- **WHEN** a catch-up run ends
- **THEN** the summary script is called once, as for a calendar run

#### Scenario: Postponed day
- **WHEN** a scheduled launch records the day as postponed
- **THEN** the summary script is not called

#### Scenario: Manual run
- **WHEN** the script is launched without a scheduled-mode option
- **THEN** the summary script is not called

### Requirement: One notification for a failed scheduled run
The system SHALL, on a scheduled run with failed steps, let the morning summary be the single notification naming them (design D9). When the summary exits non-zero or cannot be run, it SHALL send its own failure notification as before. The summary SHALL NOT change the run's exit code nor its end line. A manual run SHALL keep its failure notification. Untested until implemented.

#### Scenario: Scheduled run with two failed steps
- **WHEN** collection and indexing fail during a scheduled run and the summary exits 0
- **THEN** exactly one notification is raised, the summary's, its watch line names both steps, the end line is unchanged and exit is 1

#### Scenario: Summary fails
- **WHEN** a step fails during a scheduled run and the summary exits non-zero
- **THEN** the failure notification naming the failed steps is raised and exit is 1

#### Scenario: Summary switched off
- **WHEN** a step fails during a scheduled run and the summary exits 4 because it is switched off
- **THEN** the failure notification naming the failed steps is raised and exit is 1

#### Scenario: Summary switched off on a successful run
- **WHEN** every step of a scheduled run succeeds and the summary exits 4
- **THEN** no notification is raised and exit code is 0

#### Scenario: Manual run with a failed step
- **WHEN** a step fails during a manual run
- **THEN** the failure notification is raised as before and the summary is not called

### Requirement: Run the code of the code root on the content of the content root
The system SHALL take its code root from where its link resolves and its content root from the workspace variable, by default the development checkout, and SHALL export the content root to the tools it runs. It SHALL run the tools, the component check included, from the code root, and collect, index and build the dashboard on the content root. A run SHALL print both roots with the key phrases of design D2. It SHALL NOT write content into the code root. Untested until implemented.

#### Scenario: Run from the run tree
- **WHEN** the run script is launched through a link that resolves into a run-tree fixture, with a separate content root
- **THEN** the tools called are those of the run tree, the component check is the run tree's, the indexed folders are those of the content root, and no file is written in the run tree

#### Scenario: Roots printed
- **WHEN** a calendar or manual run starts
- **THEN** the two lines after the timestamp header give the code root and the content root

#### Scenario: Catch-up line kept first
- **WHEN** a catch-up run starts
- **THEN** the line after the timestamp header is the catch-up line, and the two roots lines follow it

### Requirement: Refuse to run when the content root is the run tree
The system SHALL, in a run that takes place, once the run record says started and before any step, stop when the content root is the run tree: log the key phrase of design D2, notify once, record the run as failed, release the lock and exit 1. A scheduled launch with nothing to do SHALL stay silent. It SHALL NOT run the uv cache check, collect, index or build the dashboard then. A content root equal to the code root in the development checkout SHALL be accepted. Untested until implemented.

#### Scenario: Content root set to the run tree
- **WHEN** a due scheduled launch finds that the workspace variable names the run tree
- **THEN** the log holds the refusal key phrase, no tool is called, one notification is raised, the run record says failed and the exit code is 1

#### Scenario: Next hourly launch
- **WHEN** a later catch-up launch of the same day comes after that refusal
- **THEN** it exits 0, writes nothing and raises no notification

#### Scenario: Development checkout as both roots
- **WHEN** the link resolves into the development checkout and the content root is that checkout
- **THEN** the run proceeds as usual

### Requirement: The watch lock is the only mark of a watch run in progress
The system SHALL let the watch lock of design D4 of the watch catch-up change, taken by every watch run, scheduled or manual, serve as the watch's scheduled-run marker for the run-tree update. The run script SHALL NOT write, in the lab data folder or elsewhere, any other marker of a run in progress, and SHALL NOT read or remove the markers of the backup and off-site jobs. Untested until implemented.

#### Scenario: Data folder during a run
- **WHEN** the collection step of a run runs
- **THEN** the lab data folder holds the lock folder and no other folder or file that marks a run in progress

#### Scenario: Script text
- **WHEN** the run script is read
- **THEN** it names no marker folder of the backup or off-site jobs and no other run marker than the lock
