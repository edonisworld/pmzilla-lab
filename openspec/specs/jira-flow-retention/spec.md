# jira-flow-retention Specification

## Purpose
Describes the user-run retention tool for the ticket-level flow data: the per-ticket retention clock, the `check` subcommand that counts what is past the rule in every store, and the `purge` subcommand, a dry run by default, which deletes only after a labelled backup of the same day. Sources are the tests in `tests/flow_retention/`.

## Requirements

### Requirement: One-year retention clock per ticket
The system SHALL compute for every stored ticket a retention clock: the resolution instant for a resolved ticket, the out-of-export instant for an open ticket that left the export, and no clock for an open ticket still in the export. A ticket is past the rule when its clock is older than the retention period. The retention period SHALL be configurable and SHALL be refused, with exit code 3 before any read, when it exceeds one year (the agreement of 12 October). The system SHALL NOT use the creation or the last update as a clock, and SHALL NOT expire an open ticket still in the export.

Source: tests/flow_retention/test_controle.py; tests/flow_retention/test_base.py; tests/flow_retention/test_regles.py (DureeAuDelaDUnAn)

#### Scenario: Resolved ticket
- **WHEN** a ticket was resolved more than the retention period ago
- **THEN** it is counted as past the rule in the database and in the history cache

#### Scenario: Open ticket in the export
- **WHEN** a ticket created years ago is still open and present in the last export
- **THEN** it is not past the rule

#### Scenario: Open ticket out of the export
- **WHEN** an open ticket carries an out-of-export instant older than the retention period
- **THEN** it is past the rule

#### Scenario: Period above one year
- **WHEN** the configured retention period is longer than one year
- **THEN** the tool stops with exit code 3, names the setting without its value, and reads nothing

### Requirement: Retention check
The system SHALL provide a `check` subcommand that reads the exports folder, the ageing-points files, the history cache, the database (through the import role), the local backups folder and the off-site status, deletes nothing, and prints per store only counts and ages: tickets past the rule, CSV and points files older than the maximum file age, files holding a forbidden column, labelled backups whose flow dump outlived the labelled-backup lifetime, and off-site copies holding a flow dump older than the configured age as reported by the off-site script. It SHALL end with the check key phrase of design D19 and exit with code 0 when every count is zero and code 4 otherwise. It SHALL NOT print a key, a team, a file name of the exports folder, a label, a version or a value.

Source: tests/flow_retention/test_controle.py

#### Scenario: Clean stores
- **WHEN** no store holds anything past the rule
- **THEN** the output ends with "retention check: nothing out of rule" and the exit code is 0

#### Scenario: Items out of rule
- **WHEN** the database holds three tickets past the rule and the cache two
- **THEN** each store line gives its count, the output ends with "retention check: 5 items out of rule", and the exit code is 4

#### Scenario: Both paths
- **WHEN** the check runs while the CSV path and the database path both hold data
- **THEN** it counts both, and a clean database does not hide an old CSV file

### Requirement: Purge is a dry run by default
The system SHALL provide a `purge` subcommand that, without `--apply`, computes what it would delete in every store, prints the same per-store counts as the check followed by the check total line of design D19, deletes nothing, ends with the dry-run key phrase of design D19, and exits with code 0 whatever the counts (exit code 1 on an error). With `--apply` it SHALL delete, in this order: CSV and points files past the maximum file age or holding a forbidden column, history cache entries past the rule (the cache rewritten owner-only), database tickets past the rule in one transaction (their teams, transitions, links, label periods and version periods removed by cascade), and the flow dump of labelled backups past their lifetime. It SHALL NOT delete a knowledge or cases dump, a plain dated backup (rotated by the backup script), an aggregated report (requirement "Ticket-level files under the rule, aggregated reports kept"), or an off-site copy (handled by the off-site script).

Source: tests/flow_retention/test_purge.py (Essai, Application)

#### Scenario: Dry run
- **WHEN** `purge` runs without `--apply`
- **THEN** the counts are printed, the line before the last is the check total line, the output ends with "dry run: nothing deleted", every file, cache entry and row is still there, and the exit code is 0

#### Scenario: Dry run with items out of rule
- **WHEN** `purge` runs without `--apply` and the database holds three tickets past the rule
- **THEN** the output holds "retention check: 3 items out of rule" followed by "dry run: nothing deleted", and the exit code is 0, not 4

#### Scenario: Applied purge
- **WHEN** `purge --apply` runs after the labelled backup of the day
- **THEN** the counted items are gone, the output ends with "purge done", a following `check` exits with code 0, and the knowledge and cases dumps of the labelled backups are untouched

#### Scenario: Database failure during the purge
- **WHEN** the database raises an error while deleting
- **THEN** the transaction is rolled back, no database row is deleted, the error type alone is printed, and the exit code is 1

### Requirement: Ticket-level files under the rule, aggregated reports kept
The system SHALL apply the one-year rule (design D1) to every file that holds ticket keys or one row per ticket: the CSV exports and the ageing-points files by file date against the maximum file age, and the history cache by the clock of each entry. It SHALL keep outside the rule the aggregated reports that hold no ticket key and no person (flow and dependency reports, dashboards, monthly summaries, epic statuses and cycles reports): the check SHALL NOT count them and the purge SHALL NOT delete them, whatever their age. In the tables folder of the flow folder (design D1), the system SHALL treat the `points-*.json` files, which hold one row per ticket, as ageing-points files under the rule; it SHALL keep outside the rule the dashboard pages `tableau-flux-*.html`, anonymised or not, which are aggregates holding no ticket key, and the configuration file `anonymes.yaml`: the check SHALL NOT count them and the purge SHALL NOT delete them, whatever their age. The system SHALL NOT exempt an ageing-points file or a CSV export because it sits in the reports folder or in the tables folder, SHALL NOT purge an aggregated report or a dashboard page because it is older than one year, and SHALL NOT delete or rewrite `anonymes.yaml`.

Source: tests/flow_retention/test_purge.py (Application, AnciensRapports, CacheEntrees); tests/flow_retention/test_controle.py

#### Scenario: Old aggregated report
- **WHEN** the reports folder holds a flow report and a monthly summary written more than one year ago, with no key and no person
- **THEN** the check does not count them, `purge --apply` leaves them in place, and the check total is unchanged by them

#### Scenario: Old ageing-points file
- **WHEN** an ageing-points file is older than the maximum file age
- **THEN** the check counts it on the points-files line, the dry run reports it without deleting it, and `purge --apply` deletes it without printing its name

#### Scenario: Old points file in the tables folder
- **WHEN** the tables folder holds a `points-*.json` file older than the maximum file age
- **THEN** the check counts it on the points-files line, the dry run reports it without deleting it, and `purge --apply` deletes it without printing its name

#### Scenario: Old dashboard pages
- **WHEN** the tables folder holds a `tableau-flux-*.html` page and an anonymised `tableau-flux-*.html` page, both written more than one year ago
- **THEN** the check does not count them, `purge --apply` leaves them in place, and the check total is unchanged by them

#### Scenario: Anonymisation configuration
- **WHEN** the tables folder holds an `anonymes.yaml` file last modified more than one year ago
- **THEN** the check does not count it, `purge --apply` neither deletes nor rewrites it, and the check total is unchanged by it

#### Scenario: History cache entry past the rule
- **WHEN** a finished cache entry has a resolution date older than the retention period
- **THEN** the check counts it on the history-cache line and `purge --apply` removes it from the cache

### Requirement: Purge requires a labelled backup of the same day
The system SHALL refuse `purge --apply` with exit code 3 and the pre-purge key phrase of design D19 when no local backup folder of the current day carries the pre-purge label of design D10, and SHALL delete nothing in that case. The system SHALL NOT create the backup itself and SHALL NOT accept a labelled backup of another day.

Source: tests/flow_retention/test_purge.py (SansSauvegardeDuJour)

#### Scenario: No labelled backup
- **WHEN** `purge --apply` runs and only a plain dated backup exists for the day
- **THEN** the output holds "pre-purge backup missing: run the labelled backup first", nothing is deleted, and the exit code is 3

#### Scenario: Labelled backup of yesterday
- **WHEN** the only labelled backup is from the day before
- **THEN** the purge is refused in the same way

### Requirement: Files holding a forbidden column are deleted
The system SHALL read only the header line of each CSV file of the exports folder and treat as forbidden a header naming a title or summary, a description, a creator, a reporter, an assignee, a comment, or the plain Jira labels column (the API export writes its declared labels under the distinct header of design D19). The purge SHALL delete such a file whatever its age, and the check SHALL count it. The system SHALL NOT rewrite such a file, SHALL NOT read its rows, and SHALL NOT print its name or its column values.

Source: tests/flow_retention/test_controle.py; tests/flow_retention/test_purge.py (ColonnesInterdites)

#### Scenario: Old manual export
- **WHEN** the exports folder holds a manual Jira export with a summary column
- **THEN** the check prints "files with a forbidden column: 1", and `purge --apply` deletes the file without printing its name

#### Scenario: API export
- **WHEN** the file is an API export with the declared-labels column
- **THEN** it is not counted as holding a forbidden column

### Requirement: Retention tool output and session refusal
The system SHALL print in French by default and in English with `--language en`, SHALL refuse another language with exit code 2, and SHALL write in its output only store names, counts, ages in days and the key phrases of design D19. It SHALL refuse to start, with exit code 3 and the session key phrase of design D19, when the variable that Claude Code sets in its shells is present, before reading any setting. It SHALL NOT offer an option that bypasses that refusal.

Source: tests/flow_retention

#### Scenario: Started from a session
- **WHEN** the variable is present
- **THEN** the output holds "Refused inside a Claude Code session", nothing is read, and the exit code is 3

#### Scenario: Distinctive names absent
- **WHEN** the fixtures hold a distinctive string in every key, team, label, version and file name
- **THEN** none of them appears in the output of `check` or `purge`
