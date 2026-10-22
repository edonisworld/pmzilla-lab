# database-backup-restore Specification

## Purpose

Daily per-schema backups with rotation and notification, the scheduled job template, the disposable-container restore test, and the start/stop script and container configuration (`tools/db_backup.sh`, `tools/db_restore_test.sh`, `tools/db_up.sh`, `tools/com.pmzilla.db-backup.plist`, `docker-compose.yml`).

## Requirements

### Requirement: Backup writes one dump file per schema, outside the repository
The system SHALL write, for each backed-up schema, one custom-format dump file in a dated backup folder named by the day, using the database client inside the container, with no password read or required. Only the knowledge, cases and flow schemas SHALL be backed up as whole schemas: never the default schema, hence never the migration tracking table (the restore test recreates it by applying the migrations), and never the `quality` schema as a whole, which holds the story content and is kept only in the live database (design D10 of change story-quality-audit). Beside the three schema dumps, the backup SHALL write the partial quality dump of requirement "Backup writes a partial quality dump without story text", which names its three tables one by one (design D10, amendment of 2026-10-18); no other dump SHALL target a single table. The default schema lists of the backup script and of the restore test SHALL NOT name `quality`. The output SHALL contain only paths and sizes.

Source: tests/db_scripts/test_db_scripts.sh (db_backup : dossier créé, un fichier par schéma, plus le dump partiel quality-sans-texte, aucun mot de passe, sortie; aucun dump de public ni de suivi des migrations; pg_dump seulement pour knowledge, cases et flow; quatre pg_dump, aucun ne vise le schéma quality entier; une seule commande vise des tables; seul le fichier quality-sans-texte.dump porte le nom quality; listes par défaut des deux scripts sans quality)

#### Scenario: Nominal backup
- **WHEN** the backup runs for a given date
- **THEN** a folder for that date exists with exactly three schema dump files (knowledge, cases, flow), each holding its schema's dump, and the partial quality dump `quality-sans-texte`; the keychain is not queried and the output does not contain a secret

#### Scenario: Default schema excluded
- **WHEN** the dump commands of a backup are inspected
- **THEN** each schema dump targets one of the three schemas by name, the only command that targets tables is the partial quality dump with its three tables, none targets the default schema or the migration tracking table, and no dump file is named after them

#### Scenario: Quality schema excluded
- **WHEN** the dump commands of a backup and the default schema lists of both scripts are inspected
- **THEN** none targets the `quality` schema as a whole, neither list names it, and the only dump file that refers to it is `quality-sans-texte`

### Requirement: Backups are private to the owner
The system SHALL create backup folders readable only by the owner and dump files readable and writable only by the owner, even when the launcher's umask is permissive.

Source: tests/db_scripts/test_db_scripts.sh (db_backup : dossiers en 700 et dumps en 600, umask 000)

#### Scenario: Permissive umask
- WHEN the backup runs under a fully open umask
- THEN the backup root and the dated folder are owner-only and the dumps are owner read/write only

### Requirement: An existing day's backup is never overwritten
The system SHALL, when the dated folder already exists, report that it exists, write and delete nothing, touch neither Docker nor the notifier, and exit successfully.

Source: tests/db_scripts/test_db_scripts.sh (db_backup : le dossier du jour n'est jamais écrasé, second passage)

#### Scenario: Second pass of the day
- WHEN the backup runs again for the same date, even with Docker unreachable and notification enabled
- THEN it says the backup exists, exits 0, makes no Docker call and sends no notification

### Requirement: Rotation keeps only the most recent dated backups
The system SHALL, after a successful backup, keep a configurable number of most recent date-named backup folders (with a default), delete older ones while listing each deleted folder, and announce how many are present and kept. A folder with a label suffix after the date SHALL be neither counted nor deleted. An invalid retention setting (zero, negative, non-numeric) SHALL be refused with exit code 2, creating and deleting nothing.

Source: tests/db_scripts/test_db_scripts.sh (db_backup : rotation, étiquette, DB_BACKUP_GARDER)

#### Scenario: Retention exceeded
- WHEN more dated folders exist than the retention allows
- THEN the oldest are removed with a "removed" line each and the newest remain

#### Scenario: Labeled folder
- WHEN a folder named with a date and a label exists
- THEN it is kept and not counted, and is not mentioned in the output

#### Scenario: Invalid retention
- WHEN the retention is 0, -1 or "abc"
- THEN the exit code is 2 and no folder is created or removed

### Requirement: Backup date argument is validated
The system SHALL accept a date of the form year-month-day, optionally followed by a lowercase alphanumeric label for a second backup the same day, and SHALL refuse any other value with exit code 2.

Source: tests/db_scripts/test_db_scripts.sh (db_backup : date invalide refusée)

#### Scenario: Invalid date
- WHEN the date setting is a word
- THEN the exit code is 2

### Requirement: A missing schema is reported and fails the run after backing up the others
The system SHALL, when a schema to back up does not exist, name it as "not backed up", back up the remaining schemas, write no file for the absent one, and exit with code 1.

Source: tests/db_scripts/test_db_scripts.sh (db_backup : schéma absent signalé)

#### Scenario: Absent schema
- WHEN the flow schema is missing
- THEN the output names it, the other dumps exist, no flow dump exists and the exit code is non-zero

### Requirement: Environment problems are distinguished and exit with code 2
The system SHALL give a distinct message and exit code 2, without creating a backup folder, for each of: container runtime unreachable (mentioning the VM runtime), database container stopped (pointing to the start script), and container running while the database does not answer.

Source: tests/db_scripts/test_db_scripts.sh (db_backup : conteneur arrêté, PostgreSQL muet, Docker muet)

#### Scenario: Stopped container
- WHEN the container is not running
- THEN the message says it is stopped and refers to the start script, no folder is created, exit code 2

#### Scenario: Silent database
- WHEN the container runs but the database is not ready
- THEN the message says it runs but the database does not answer, and it does not say "stopped"

### Requirement: Failures notify on macOS only for scheduled runs, without sensitive content
The system SHALL send a single macOS notification on any non-zero exit only when the notifier setting is enabled; the notification SHALL state the cause and the exit code and SHALL NOT contain a password, a dump path or content. A manual run, and a successful run, SHALL send none.

Source: tests/db_scripts/test_db_scripts.sh (db_backup : notification macOS)

#### Scenario: Scheduled failure
- WHEN the container is stopped and the notifier is enabled
- THEN exactly one notification is sent that carries the cause and the exit code 2
- AND WHEN the runtime is unreachable, the notification names the VM runtime

#### Scenario: Manual failure or scheduled success
- WHEN the notifier is not enabled and the run fails, or it is enabled and the run succeeds
- THEN no notification is sent

#### Scenario: Partial backup
- WHEN a schema is absent under the scheduler
- THEN exit code 1 is reported in the notification

### Requirement: The scheduled-job template runs the backup daily after the watch collection
The system SHALL provide a launchd job template that runs the backup script every day (no weekday restriction) at a time later than the watch collection job's time, with output and errors going to the same log file, notifications enabled, no secret and no keychain access, no run at load and no keep-alive.

Source: tests/db_backup_plist/test_plist.py

#### Scenario: Well-formed template
- WHEN the template is parsed
- THEN it is valid XML, has the expected label, and has a daily schedule later than the watch job's schedule

#### Scenario: Rendering
- WHEN the home placeholder is substituted
- THEN the program arguments are the shell and the backup script under the home directory, the log path is under the home directory and shared by stdout and stderr, and no placeholder remains

#### Scenario: No real paths, no secret
- WHEN the raw template is read
- THEN it contains no absolute user path other than the placeholder and system shell paths, no password mention and no keychain command, and the notifier variable is enabled

#### Scenario: Not started at bootstrap
- WHEN the rendered template is read
- THEN it has neither run-at-load nor keep-alive (missed runs are caught up through the calendar schedule at wake)

### Requirement: The restore test uses a disposable container, never the real database
The system SHALL restore a backup into a uniquely named disposable container started from the same pinned image as the compose file, publish its port on the loopback interface only with a Docker-chosen port by default, refuse port 5432 or the real database's configured port (exit 2), and refuse (exit 1, container removed, nothing restored) if Docker nevertheless publishes the standard port. It SHALL run compose commands against the real database only for process listing, readiness and read-only queries, SHALL never run a restore, an up/down or a write statement there, and SHALL NOT read the keychain.

Source: tests/db_scripts/test_db_restore_test.sh (jamais la vraie base; refus de viser la vraie base; hygiène du script)

#### Scenario: Container configuration
- WHEN the restore test runs
- THEN the container uses the compose image, a unique prefixed name distinct from the real one and a loopback-only port, and a throwaway random password is passed through the environment, not as an argument

#### Scenario: Real-database safety
- WHEN the command log is inspected
- THEN compose commands are limited to listing, readiness and psql, none is a write or a restore, and the keychain was not called

#### Scenario: Port refusal
- WHEN the port option is the standard port or the real configured port
- THEN the exit code is 2, a "refused" message mentions the real database and no container starts
- AND WHEN a free port is given, it is published on loopback only

### Requirement: The restore test selects the latest plain dated backup
The system SHALL restore the most recent date-named backup folder, ignoring folders with a label, unless a specific backup folder is given; it SHALL refuse with exit code 2 when none exists (pointing to the backup script) or when the given folder is not found.

Source: tests/db_scripts/test_db_restore_test.sh (aide et usage; aucune sauvegarde; succès)

#### Scenario: Latest selection
- WHEN several dated folders and labeled folders exist
- THEN the restored backup is the newest plain dated one

#### Scenario: No backup
- WHEN the backup root is empty or the given folder does not exist
- THEN exit code 2, a clear message, and no container started

#### Scenario: Help and unknown option
- WHEN help is requested
- THEN it exits 0, describes the backup option and the disposable nature, and does not touch Docker
- AND an unknown option exits 2

### Requirement: The restore test restores each schema, applies migrations and compares to the real database
The system SHALL restore the three schemas into the disposable container, run the migrations against it (without the keychain), restore the partial quality dump into the empty `quality` tables (requirement "The partial quality dump restores coherently"), compare per-table row counts and the migration fingerprints with the real database, and print "restore OK" with exit 0 when they match. A table missing after restoration SHALL give exit 1 naming the table. A row-count gap SHALL be displayed with its value, flagged as possibly expected, with exit 0. A fingerprint difference, or a migration absent from the real database, SHALL give exit 1 with the differing migrations listed.

Source: tests/db_scripts/test_db_restore_test.sh (succès; les trois schémas et le dump partiel de quality sont restaurés, quatre pg_restore; le dump partiel se restaure en données seulement, sans --clean, après les trois schémas; écart de lignes; table manquante; empreinte des migrations)

#### Scenario: Identical counts
- **WHEN** restored and real counts are identical, on a backup holding the partial quality dump
- **THEN** each table line is marked OK, "identical counts" is stated, and four restores were issued: the three schemas and the partial quality dump

#### Scenario: Row gap
- **WHEN** a table has fewer restored rows than live rows
- **THEN** the line shows both counts and the gap, notes that it may be expected, and the exit code is 0

#### Scenario: Missing table
- **WHEN** a table is absent from the restored database
- **THEN** the exit code is 1 and the table is named as missing

#### Scenario: Migration fingerprint mismatch
- **WHEN** the restored database's migration fingerprints differ from the real database's
- **THEN** exit code 1 and a message that the fingerprints differ, with the migration lines listed

### Requirement: The restore test gives up when the disposable container never becomes ready
The system SHALL wait for the disposable database to become ready for a configurable time (with a default), and when it is not ready by then SHALL exit with code 1 and a message naming the waiting time and the command to read the container logs, SHALL restore and migrate nothing, and SHALL remove the container.

Source: tests/db_scripts/test_db_restore_test.sh (délai d'attente du conteneur jetable)

#### Scenario: Never ready
- **WHEN** the disposable database never answers within the waiting time
- **THEN** the exit code is 1, the message names the delay and the container-logs command, no restore or migration is run, and the container is removed

### Requirement: The restore test output is limited to table names, counts and statuses
The system SHALL print only table names, two counts and a status per table, and SHALL NOT print stray lines returned by queries, the real or the throwaway password. Restore error details SHALL be hidden by default and shown only with a detail option.

Source: tests/db_scripts/test_db_restore_test.sh (sortie; nettoyage après échec)

#### Scenario: Output hygiene
- WHEN a run completes
- THEN no noise line or password appears, and every count line has only a table, two numbers and OK

#### Scenario: Restore error detail
- WHEN a restore fails
- THEN the error output hides the restore detail by default, and shows it with the detail option

### Requirement: The disposable container is always removed
The system SHALL remove the disposable container together with its volume after success, restore failure, migration failure, container start failure, comparison failure, a missing dump file, or an interruption (termination signal during the wait), and SHALL report the removal.

Source: tests/db_scripts/test_db_restore_test.sh (nettoyage après échec; interruption SIGTERM)

#### Scenario: Restore failure
- WHEN restoring one schema fails
- THEN exit code 1, the schema is named, the message suggests the backup may predate a migration and points to the backup option, and the container is removed

#### Scenario: Other failures
- WHEN migrations fail, the container fails to start, or a schema's dump file is absent
- THEN exit code 1 and the container is removed (or removal is attempted if none started)

#### Scenario: Interruption
- WHEN the process is terminated while waiting for the container
- THEN it exits non-zero, removes the container and reports the removal

### Requirement: The start script starts and stops the database without exposing or deleting anything
The system SHALL start the database container and wait until healthy, passing the password to compose only through the environment of that one command, never as an argument, never displayed, with no persistent export and no shell tracing. It SHALL read the password from the keychain first, then from an environment fallback; when neither exists, it SHALL exit non-zero, print the command to create the keychain entry without running it, and not start compose.

Source: tests/db_scripts/test_db_scripts.sh (db_up)

#### Scenario: No keychain entry
- WHEN the keychain has no entry and no fallback is set
- THEN exit non-zero, a message gives the creation command, no creation is executed and compose up is not run

#### Scenario: Keychain entry
- WHEN the keychain provides a password
- THEN compose up is run detached and waiting, the password is in the command's environment only, not in any argument, and not in the output

#### Scenario: Environment fallback
- WHEN the keychain has none and the fallback variable is set
- THEN the database starts with the fallback value

### Requirement: Stopping keeps the data and prerequisites are checked
The system SHALL, on the stop action, stop the stack without removing volumes and without reading the keychain; SHALL refuse an unknown action with exit code 2; and SHALL exit non-zero with a clear message when the VM runtime is stopped or Docker does not answer.

Source: tests/db_scripts/test_db_scripts.sh (db_up down; option inconnue; Colima arrêté; Docker muet)

#### Scenario: Stop
- WHEN the stop action is used
- THEN compose down runs without the volume-removal option and the keychain is not read

#### Scenario: Unknown action
- WHEN an unknown argument is given
- THEN exit code 2

#### Scenario: Runtime down
- WHEN the VM runtime is stopped, or Docker is silent
- THEN the exit is non-zero with a dedicated message

### Requirement: The compose file requires no password for non-start commands and holds no secret
The system SHALL NOT declare the database password as mandatory at interpolation time (so listing, port, exec and config work without it), SHALL write no password value in the compose file, and SHALL give the container a shared-memory size large enough for parallel index builds.

Source: tests/db_scripts/test_db_scripts.sh (compose : ...)

#### Scenario: Config without password
- WHEN compose config is run without the password variable
- THEN it succeeds and does not report a required variable

#### Scenario: Static checks
- WHEN the compose file is read
- THEN no mandatory-variable syntax for the password and no literal password value appear, and a shared-memory size is set

### Requirement: The scheduled backup runs from the run tree and marks its run
The system SHALL make the backup job launch the backup script through its lab-folder link, and SHALL make the script mark its run by the rules of design D14: its own folder in the lab data folder, created atomically before any work with its process identifier, removed at exit by its own process only, whatever the exit code. A marker SHALL NOT stop the backup or change its exit code, and the script SHALL NOT remove another job's marker or the watch lock. Untested until implemented.

#### Scenario: Rendered template
- **WHEN** the backup template is rendered
- **THEN** its program is the backup script's lab-folder link under the home directory, and no code-tree folder is named

#### Scenario: Marker during the backup
- **WHEN** the backup dumps a schema in a fixture
- **THEN** the backup's marker folder exists in the lab data folder and holds the backup's process identifier

#### Scenario: Marker removed after a failure
- **WHEN** a schema is missing and the backup exits non-zero
- **THEN** the backup's marker no longer exists, and the watch lock, if present, is untouched

#### Scenario: Stale marker taken over
- **WHEN** the backup starts while its marker folder holds the identifier of a dead process
- **THEN** the log holds the "stale, taken over" line of design D14, the backup runs with its own marker, and no marker is left after it

#### Scenario: Marker held by another backup
- **WHEN** the backup starts while its marker folder holds the identifier of a live process, recently created
- **THEN** the log holds the "already held" line of design D14, the backup runs, and the existing folder is unchanged after it

#### Scenario: Data folder not writable
- **WHEN** the marker cannot be created because the data folder is read-only
- **THEN** the log holds the "cannot be written" line of design D14, the dumps are written, and the exit code is the one the backup would give without a marker

### Requirement: The rehearsal copy script refuses to run inside a Claude Code session
The system SHALL make the rehearsal copy script (`tools/db_rehearsal.sh`) refuse every subcommand inside a Claude Code session, with exit code 3 and the session phrase of design D11, before reading any variable or calling Docker. It SHALL NOT start, list or remove a container in that case.

Source: untested until implemented (tests/db_scripts/test_db_rehearsal.sh, task 4.1)

#### Scenario: Started from a session
- **WHEN** `up`, `status` or `down` runs with the Claude Code session variable set, with fake Docker
- **THEN** the exit code is 3, the session phrase is printed, and the Docker log is empty

### Requirement: The rehearsal copy starts empty from the migrations
The system SHALL make `up` start one container from the compose image, with a unique name carrying the rehearsal prefix (distinct from the restore test's) and the rehearsal label. It SHALL apply the migrations without the keychain, then print each flow table with its row count, exiting 0 only when every flow table is empty. It SHALL NOT restore a dump, truncate or drop a table.

Source: untested until implemented (tests/db_scripts/test_db_rehearsal.sh, task 4.1)

#### Scenario: Nominal start
- **WHEN** `up` runs with every required variable set, fake Docker and fake migrations
- **THEN** one container is started from the compose image with the rehearsal prefix and label, the migrations run once, each flow table line shows 0, the ready phrase gives the loopback port, and the exit code is 0

#### Scenario: No restore
- **WHEN** the Docker and database command log of a nominal `up` is inspected
- **THEN** it holds no restore, no truncate and no drop statement

### Requirement: The rehearsal copy never targets the real database
The system SHALL publish the copy's port on the loopback only, refuse the standard port or the configured real port with exit 2 before starting anything, and exit 1, removing the container, if Docker publishes such a port anyway. Against the real database it SHALL only list, check readiness and read migration fingerprints. It SHALL NOT write there, start or stop it, or read the keychain.

Source: untested until implemented (tests/db_scripts/test_db_rehearsal.sh, task 4.1)

#### Scenario: Real port given
- **WHEN** `up --port` names the standard port or the configured real port
- **THEN** the exit code is 2, the refused-port phrase is printed, and no container starts

#### Scenario: Real-database safety
- **WHEN** the command log of a nominal `up` is inspected
- **THEN** compose commands are limited to listing, readiness and a read-only fingerprint query, and the keychain command was never called

### Requirement: The rehearsal copy takes its passwords from the caller's environment only
The system SHALL read the copy's superuser password and the per-role passwords of the flow import role and the views role from the caller's environment, using the variable names of `tools/db.py`. It SHALL enable the login of these two roles in the copy only. A missing variable SHALL give exit 2 naming it, with no container started. A password SHALL NOT appear in an argument, an output line or a file.

Source: untested until implemented (tests/db_scripts/test_db_rehearsal.sh, task 4.1)

#### Scenario: Missing variable
- **WHEN** `up` runs without the views role's password variable
- **THEN** the exit code is 2, the missing-variable phrase names the variable without any value, and no container starts

#### Scenario: Passwords not exposed
- **WHEN** `up` runs with sentinel passwords
- **THEN** no sentinel appears in the output, in the arguments of the Docker log or in any file written by the script

### Requirement: Only one rehearsal copy exists at a time
The system SHALL make `up` refuse, with exit code 2 and the copy-present phrase naming the existing container and the `down` command, when a container carrying the rehearsal label already exists. It SHALL NOT start a second copy or reuse the existing one.

Source: untested until implemented (tests/db_scripts/test_db_rehearsal.sh, task 4.1)

#### Scenario: Copy already present
- **WHEN** fake Docker lists a container with the rehearsal label and `up` runs
- **THEN** the exit code is 2, the phrase names that container and the `down` command, and no container is started

### Requirement: The rehearsal copy has the same migrations as the real database
The system SHALL, after the migrations, compare the copy's migration fingerprint with the migration files and with the real database, as the restore test does. A difference SHALL give exit 1 with the fingerprint phrase of design D11 and the removal of the container. It SHALL NOT print a value of the migration table other than numbers, names and fingerprints.

Source: untested until implemented (tests/db_scripts/test_db_rehearsal.sh, task 4.1)

#### Scenario: Fingerprint mismatch
- **WHEN** the real database lists one migration more than the copy
- **THEN** the exit code is 1, the fingerprint phrase is printed, and the container is removed

### Requirement: A failed start leaves no rehearsal copy
The system SHALL remove the copy's container and its volume when `up` fails after the container exists: not ready in time, migration failure, a non-empty flow table, a fingerprint difference, or an interruption. It SHALL report the removal with the phrase of design D11. It SHALL NOT leave a container carrying the rehearsal label after a non-zero exit.

Source: untested until implemented (tests/db_scripts/test_db_rehearsal.sh, task 4.1)

#### Scenario: Migration failure
- **WHEN** the migrations fail on the copy
- **THEN** the exit code is 1, the removal-after-failure phrase is printed, and fake Docker received the removal with the volume option

#### Scenario: Interruption
- **WHEN** the process is terminated while waiting for the copy to be ready
- **THEN** it exits non-zero and the container is removed

### Requirement: The rehearsal copy is listed and removed on request
The system SHALL make `status` print the rehearsal container (name, loopback port, creation instant) or the no-copy phrase, with exit 0 and no database read. It SHALL make `down` remove every container carrying both the rehearsal prefix and label, together with its volume, reporting each one, and exit 1 with the left-over phrase if one remains. It SHALL NOT remove any other container.

Source: untested until implemented (tests/db_scripts/test_db_rehearsal.sh, task 4.1)

#### Scenario: Removal
- **WHEN** one rehearsal container exists and `down` runs
- **THEN** the container is removed with its volume, the removal phrase names it, and the exit code is 0

#### Scenario: Other containers untouched
- **WHEN** fake Docker also lists the real database container and a restore-test container
- **THEN** `down` removes neither of them

#### Scenario: Nothing to remove
- **WHEN** no rehearsal container exists
- **THEN** `status` prints the no-copy phrase and `down` prints the nothing-to-remove phrase, both with exit 0

### Requirement: The rehearsal copy output holds names, ports, counts and statuses only
The system SHALL print only container names, the loopback port, the address without password, flow table names with row counts, migration numbers and names, and statuses. It SHALL NOT print a password, a row value or the error output of a failed command (it names the failed step instead), and SHALL NOT run with shell tracing.

Source: untested until implemented (tests/db_scripts/test_db_rehearsal.sh, task 4.1)

#### Scenario: Output hygiene
- **WHEN** a nominal `up` and a failed `up` complete with fake Docker returning noise lines
- **THEN** every printed line matches one of the allowed forms, and no noise line or password appears

### Requirement: The restore test expects the quality tables empty
The system SHALL make the restore test count the `quality` tables. The three tables of the partial quality dump (team attributes, team reviews, overlay versions) SHALL be restored and compared with the live ones like any table. Every other `quality` table, restored empty while the live one holds rows, SHALL be reported as an expected gap with both counts and the never-backed-up note, without failing.

#### Scenario: Restore with empty quality tables
- **WHEN** the restore test runs on a backup holding the partial quality dump, taken while the live `quality` tables hold rows
- **THEN** the run ends with the restore-OK line and exit code 0, the three dumped tables are compared like any table, each other `quality` table line shows its restored and live counts with the never-backed-up note, and no restored-table warning is printed for them

#### Scenario: Flow gap beside the quality gap
- **WHEN** a flow table also has fewer restored rows than live rows
- **THEN** the flow gap keeps its possibly-expected report beside the `quality` note, and the exit code is 0

Source: tests/db_scripts/test_db_restore_test.sh (schéma quality : tables quality vides après restauration, code 0; écart quality attendu avec ses deux comptes; trois tables du dump partiel comparées comme n'importe quelle table; avertissement des tables à 0 ligne absent; écart flow à côté de l'écart quality)

### Requirement: The restore test never restores or drops the quality schema as a whole
The restore test SHALL NOT restore the `quality` schema as a whole or drop it, and SHALL still fail with exit code 1 when a `quality` table is missing after the migrations.

Source: tests/db_scripts/test_db_restore_test.sh (quatre pg_restore, aucun DROP SCHEMA quality; table quality absente, code 1)

#### Scenario: Quality neither restored nor dropped
- **WHEN** the command log of the restore test is inspected
- **THEN** exactly four restores are issued (the three schemas and the partial quality dump), none restores the `quality` schema as a whole, and no statement drops the `quality` schema

#### Scenario: Missing quality table
- **WHEN** a `quality` table is absent from the restored database
- **THEN** the exit code is 1 and the table is named as missing

### Requirement: The restore test and the rehearsal copy compare ports as numbers
The system SHALL accept the port option of the restore test and of `up` of the rehearsal copy only in the plain decimal form of test-db-guards design D1, compare it and the container's published port as numbers with the standard and configured real ports, and refuse with exit 2 (line of D5) a configured real port set in another form. It SHALL NOT start a container after these refusals.

#### Scenario: Port option not in the plain form
- **WHEN** the port option has a leading zero, a sign, spaces, is zero or is above 65535
- **THEN** the exit code is 2, `Port invalide` is printed and no container starts

#### Scenario: Configured real port unreadable
- **WHEN** the configured real port is set to a value that is not a valid port
- **THEN** the exit code is 2, `le port configuré de la vraie base est illisible` is printed and no container starts

Source: tests/db_scripts/test_db_restore_test.sh, tests/db_scripts/test_db_rehearsal.sh (task 2.4)

### Requirement: Backup writes a partial quality dump without story text
The system SHALL write in the dated backup folder one more owner-only dump file, `quality-sans-texte`, holding the data of three `quality` tables named one by one: team attributes, team reviews and overlay versions (design D10). It SHALL NOT dump the whole `quality` schema, the items, item teams, contents, assessments or coaching feedback, so that no story text or ticket key enters a backup.

#### Scenario: Three tables only
- **WHEN** the dump commands of a backup are inspected
- **THEN** one command targets the three tables by name in a file named `quality-sans-texte`, and no command targets the `quality` schema as a whole or any other `quality` table

#### Scenario: No story text in the backup
- **WHEN** the live `quality` tables hold distinctive strings in their contents, coaching feedback and item keys, and a backup runs
- **THEN** none of those strings is found in any file of the dated folder

Source: tests/db_scripts/test_db_scripts.sh (db_backup : dump partiel, sentinelles), tests/db/test_quality_dump_coherence.py

### Requirement: The partial quality dump restores coherently
The system SHALL make the restore test apply the migrations, then restore the partial `quality` dump into the empty `quality` tables, compare the three tables' restored counts with the live ones, and keep the never-backed-up note and expected gap for the other `quality` tables. A test SHALL fail, naming the table, when a dumped table has a foreign key to a table outside the dump. A failed partial restore SHALL end the restore test with exit code 1.

#### Scenario: Coherent restore
- **WHEN** the restore test runs on a backup holding the partial dump while the live team reviews hold rows
- **THEN** the team reviews are restored with their live count, the contents and assessments keep the never-backed-up note, and the exit code is 0

#### Scenario: Foreign key to an excluded table
- **WHEN** a migration gives a dumped table a foreign key to the items table
- **THEN** the coherence test fails and names that table

#### Scenario: Partial restore fails
- **WHEN** restoring the partial dump raises an error
- **THEN** the restore test names the dump and exits with code 1

Source: tests/db_scripts/test_db_restore_test.sh (schéma quality), tests/db/test_quality_dump_coherence.py
