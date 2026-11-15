# jira-flow-retention Specification

## Purpose
Describes the user-run retention tool for the ticket-level flow data: the per-ticket retention clock, the `check` subcommand that counts what is past the rule in every store, and the `purge` subcommand, a dry run by default, which deletes only after a labelled backup of the same day. Sources are the tests in `tests/flow_retention/`.

## Requirements

### Requirement: One-year retention clock per ticket
The system SHALL compute for every stored ticket a retention clock: the resolution instant for a resolved ticket, the out-of-export instant for an open ticket that left the export, and no clock for an open ticket still in the export. A ticket is past the rule when its clock is older than the retention period. The system SHALL NOT use the creation or the last update as a clock, and SHALL NOT expire an open ticket still in the export.

Source: tests/flow_retention (test_controle.py, test_base.py)

#### Scenario: Resolved ticket
- **WHEN** a ticket was resolved more than the retention period ago
- **THEN** it is counted as past the rule in the database

#### Scenario: Open ticket in the export
- **WHEN** a ticket created years ago is still open and present in the last export
- **THEN** it is not past the rule

#### Scenario: Open ticket out of the export
- **WHEN** an open ticket carries an out-of-export instant older than the retention period
- **THEN** it is past the rule

### Requirement: Retention period of at most one year
The retention period SHALL be configurable and SHALL be refused, with exit code 3 before any read, when it exceeds one year (the agreement of 12 October).

Source: tests/flow_retention/test_regles.py (DureeAuDelaDUnAn)

#### Scenario: Period above one year
- **WHEN** the configured retention period is longer than one year
- **THEN** the tool stops with exit code 3, names the setting without its value, and reads nothing

### Requirement: Retention check
The system SHALL provide a `check` subcommand that reads the names and dates of the files left from the CSV route (requirement "Files left from the CSV route are deleted whatever their age"), the ageing-points files, the database (the flow schema through the import role, then the `quality` schema through its read-write role), the local backups folder and the off-site status. It SHALL delete nothing.

Source: tests/flow_retention, test_controle.py and test_contenu_stories.py (Controle)

#### Scenario: Both paths
- **WHEN** the check runs while the database holds data and one CSV file is left in the exports folder
- **THEN** it counts both, and a clean database does not hide the file left from the CSV route

### Requirement: Retention check store lines
The check SHALL print per store only counts and ages, one line for each store listed in the scenario "Store lines". The raw-layer line SHALL come right after the database tickets line, the story content line right after the raw-layer line, and the version references line right after the story content line. The story content and version references counts SHALL add to the total.

Source: tests/flow_retention (test_controle.py, test_contenu_stories.py)

#### Scenario: Store lines
- **WHEN** `check` runs
- **THEN** it prints one line of counts and ages for each store: tickets past the rule; raw-layer snapshots past the rule (requirement "Raw layer under the rule"); story content items past the rule (requirement "Story content under the one-year rule"), on the story content line of design S1 of change story-quality-schema; version references past the rule (requirement "Version references under the rule"); files left from the CSV route, on the store line of design D10 of the database-only change; points files older than the maximum file age; labelled backups whose flow dump outlived the labelled-backup lifetime; off-site copies holding a flow dump older than the configured age, as reported by the off-site script

#### Scenario: Story content past the rule
- **WHEN** the `quality` schema holds two items past the rule and every other store is clean
- **THEN** the output holds "story content: 2 items out of rule", ends with "retention check: 2 items out of rule", and the exit code is 4

#### Scenario: Story content added to the total
- **WHEN** the database holds three tickets past the rule, the `quality` schema four items past the rule, and two files are left from the CSV route
- **THEN** the output holds "database, tickets past the rule: 3" and "story content: 4 items out of rule", and ends with "retention check: 9 items out of rule"

#### Scenario: Line order
- **WHEN** `check` runs in English on clean stores
- **THEN** the line "raw layer: 0 snapshots out of rule" directly follows "database, tickets past the rule: 0", the line "story content: 0 items out of rule" directly follows the raw-layer line, and the line "version references: 0 out of rule" directly follows the story content line

#### Scenario: French store line
- **WHEN** `check` runs in French and the `quality` schema holds two items past the rule
- **THEN** the output holds "contenu des stories : 2 éléments hors règle" and ends with "contrôle de conservation : 2 éléments hors règle"

### Requirement: Retention check outcome
The check SHALL end with the check key phrase of design D19 and exit with code 0 when every count is zero and code 4 otherwise; a database error while counting the story content SHALL print the error type alone and exit with code 1.

Source: tests/flow_retention/test_controle.py (Controle); tests/flow_retention/test_contenu_stories.py (Controle)

#### Scenario: Clean stores
- **WHEN** no store holds anything past the rule
- **THEN** the output ends with "retention check: nothing out of rule" and the exit code is 0

#### Scenario: Items out of rule
- **WHEN** the database holds three tickets past the rule and two files are left from the CSV route
- **THEN** each store line gives its count, the output ends with "retention check: 5 items out of rule", and the exit code is 4

#### Scenario: Failure while counting the story content
- **WHEN** the database raises an error, carrying sentinel strings, while the story content is counted
- **THEN** the exit code is 1, the error type alone is printed, and no sentinel string appears in the output

### Requirement: Retention check output without content
The check SHALL NOT print a key, a team, a file name of the exports folder, a label, a version, a value or a story text, SHALL NOT read the content of a file left from the CSV route, and SHALL NOT delete or write a row of the `quality` schema.

Source: tests/flow_retention/test_controle.py (Controle); tests/flow_retention/test_contenu_stories.py (Controle)

#### Scenario: Counts only
- **WHEN** `check` runs while the database and the `quality` schema hold items past the rule and a CSV file is left in the exports folder
- **THEN** the output holds no key, team, file name of the exports folder, label, version, value or story text, the content of the CSV file is not read, and no row of the `quality` schema is deleted or written

### Requirement: Purge is a dry run by default
The system SHALL provide a `purge` subcommand. Without `--apply`, it SHALL compute what it would delete in every store, the raw layer and the story content store included, print the same per-store counts as the check followed by the check total line of design D19, delete nothing, end with the dry-run key phrase of design D19, and exit with code 0 whatever the counts (exit code 1 on an error).

Source: tests/flow_retention, test_purge.py (Essai) and test_contenu_stories.py (EssaiEtPurge)

#### Scenario: Dry run
- **WHEN** `purge` runs without `--apply`
- **THEN** the counts are printed, the line before the last is the check total line, the output ends with "dry run: nothing deleted", every file and row is still there, and the exit code is 0

#### Scenario: Dry run with items out of rule
- **WHEN** `purge` runs without `--apply` and the database holds three tickets past the rule
- **THEN** the output holds "retention check: 3 items out of rule" followed by "dry run: nothing deleted", and the exit code is 0, not 4

#### Scenario: Dry run with story content out of rule
- **WHEN** `purge` runs without `--apply` and the `quality` schema holds two items past the rule
- **THEN** the output holds "story content: 2 items out of rule", the last two lines are "retention check: 2 items out of rule" and "dry run: nothing deleted", no row is deleted and no transaction is committed or rolled back

### Requirement: Purge steps with apply
With `--apply` the purge SHALL delete, in this order:
1. the files left from the CSV route, whatever their age;
2. points files past the maximum file age;
3. the raw-layer snapshots and sightings past the rule, then the database tickets past the rule;
4. the story content items past the rule;
5. the flow dump of labelled backups past their lifetime.

Source: tests/flow_retention/test_purge.py (Application, FichiersLaissesParLaVoieCsv); tests/flow_retention/test_contenu_stories.py (EssaiEtPurge)

#### Scenario: Order of the steps
- **WHEN** `purge --apply` runs with a file left from the CSV route, three tickets and two story content items past the rule, and a labelled backup past its lifetime
- **THEN** when the story content is deleted the file left from the CSV route is already gone and the tickets already deleted, while the old flow dump is still there; the flow dump is deleted afterwards, and two transactions are committed

### Requirement: Purge database transactions
With `--apply`, the purge SHALL delete the raw-layer snapshots and sightings past the rule, then the database tickets past the rule, in one flow transaction, and SHALL delete the story content items past the rule in a separate transaction, under the read-write role of the `quality` schema.

Source: tests/flow_retention/test_purge.py (Application); tests/flow_retention/test_contenu_stories.py (EssaiEtPurge)

#### Scenario: Story content purged
- **WHEN** `purge --apply` runs after the labelled backup of the day and two story content items are past the rule
- **THEN** one deletion of the `quality` items past the rule is committed right after it is run, in its own transaction, their teams, content, assessments and coaching feedback go by cascade, the output ends with "purge done", and no text or key appears in the output

### Requirement: Purge deletions cascade
In the purge, the deletion of a database ticket SHALL remove by cascade its teams, transitions, links, label periods, version periods and current versions, and the deletion of a story content item SHALL remove by cascade its teams, content, assessments and coaching feedback.

Source: tests/flow_retention/test_purge.py (Application); tests/flow_retention/test_base.py (HorlogeEtCascade); tests/flow_retention/test_contenu_stories.py (EssaiEtPurge)

#### Scenario: Ticket purged
- **WHEN** `purge --apply` runs after the labelled backup of the day and a database ticket is past the rule
- **THEN** the ticket is gone with its teams, transitions, links, label periods, version periods and current versions

### Requirement: Purge stops at a failed database step
A failure of a database step of the purge SHALL roll back that step's transaction, print the error type alone, exit with code 1, and SHALL NOT run the following steps.

Source: tests/flow_retention/test_purge.py (Application); tests/flow_retention/test_contenu_stories.py (EssaiEtPurge)

#### Scenario: Database failure during the purge
- **WHEN** the database raises an error while deleting
- **THEN** the transaction is rolled back, no database row is deleted, the error type alone is printed, and the exit code is 1

#### Scenario: Story content deletion fails
- **WHEN** the deletion of the story content raises an error carrying sentinel strings
- **THEN** its transaction is rolled back, the error type alone is printed, the exit code is 1, "purge done" is not printed, no sentinel appears, and the old flow dump of the labelled backup is still there

### Requirement: Purge leaves other stores alone
The purge SHALL NOT delete a knowledge or cases dump, a plain dated backup (rotated by the backup script), an aggregated report (requirement "Ticket-level files under the rule, aggregated reports kept"), or an off-site copy (handled by the off-site script), and SHALL NOT delete a story content item within the rule.

Source: tests/flow_retention/test_purge.py (Application); tests/flow_retention/test_contenu_stories.py (EssaiEtPurge)

#### Scenario: Applied purge
- **WHEN** `purge --apply` runs after the labelled backup of the day
- **THEN** the counted items are gone, the output ends with "purge done", a following `check` exits with code 0, and the knowledge and cases dumps of the labelled backups are untouched

### Requirement: Ticket-level files under the rule, aggregated reports kept
The system SHALL apply the one-year rule (design D1 of the GDPR alignment) to the ageing-points files, by file date against the maximum file age. The system SHALL NOT exempt an ageing-points file because it sits in the reports folder or in the tables folder.

Source: tests/flow_retention/test_purge.py (Application, AnciensRapports); tests/flow_retention/test_controle.py; reworded without the CSV and cache stores.

#### Scenario: Old ageing-points file
- **WHEN** an ageing-points file is older than the maximum file age
- **THEN** the check counts it on the points-files line, the dry run reports it without deleting it, and `purge --apply` deletes it without printing its name

#### Scenario: History cache entry past the rule
- **WHEN** the former history cache file is still present
- **THEN** the check counts it once on the line of files left from the CSV route, not entry by entry, and `purge --apply` deletes the whole file

### Requirement: Aggregated reports outside the rule
The system SHALL keep outside the rule the aggregated reports that hold no ticket key and no person (flow and dependency reports, dashboards, monthly summaries, epic statuses and cycles reports): the check SHALL NOT count them and the purge SHALL NOT delete them, whatever their age. The system SHALL NOT purge an aggregated report because it is older than one year.

Source: tests/flow_retention/test_purge.py (Application, AnciensRapports); tests/flow_retention/test_controle.py

#### Scenario: Old aggregated report
- **WHEN** the reports folder holds a flow report and a monthly summary written more than one year ago, with no key and no person
- **THEN** the check does not count them, `purge --apply` leaves them in place, and the check total is unchanged by them

### Requirement: Points files of the tables folder under the rule
In the tables folder of the flow folder, the system SHALL treat the `points-*.json` files, which hold one row per ticket, as ageing-points files under the rule.

Source: tests/flow_retention/test_purge.py (Application, AnciensRapports); tests/flow_retention/test_controle.py

#### Scenario: Old points file in the tables folder
- **WHEN** the tables folder holds a `points-*.json` file older than the maximum file age
- **THEN** the check counts it on the points-files line, the dry run reports it without deleting it, and `purge --apply` deletes it without printing its name

### Requirement: Dashboard pages kept
In the tables folder of the flow folder, the system SHALL keep outside the rule the dashboard pages `tableau-flux-*.html`, anonymised or not, left by the retired flow dashboard, which are aggregates holding no ticket key: the check SHALL NOT count them and the purge SHALL NOT delete them, whatever their age. The system SHALL NOT purge a dashboard page because it is older than one year.

#### Scenario: Old dashboard pages
- **WHEN** the tables folder holds a `tableau-flux-*.html` page and an anonymised `tableau-flux-*.html` page, both written more than one year ago
- **THEN** the check does not count them, `purge --apply` leaves them in place, and the check total is unchanged by them

No tool writes new pages, and the existing ones stay until the user deletes them.

Source: design D9 of change remove-flow-board (retired flow dashboard); tests/flow_retention/test_purge.py (Application, AnciensRapports); tests/flow_retention/test_controle.py

### Requirement: Anonymisation file kept
In the tables folder of the flow folder, the system SHALL keep outside the rule the configuration file `anonymes.yaml`: the check SHALL NOT count it and the purge SHALL NOT delete it, whatever its age. The system SHALL NOT delete or rewrite `anonymes.yaml`.

Source: tests/flow_retention/test_purge.py (Application, AnciensRapports); tests/flow_retention/test_controle.py

#### Scenario: Anonymisation configuration
- **WHEN** the tables folder holds an `anonymes.yaml` file last modified more than one year ago
- **THEN** the check does not count it, `purge --apply` neither deletes nor rewrites it, and the check total is unchanged by it

### Requirement: Purge requires a labelled backup of the same day
The system SHALL refuse `purge --apply` with exit code 3 and the pre-purge key phrase of design D19 when no local backup folder of the current day carries the pre-purge label of design D10, and SHALL delete nothing in that case. The system SHALL NOT create the backup itself and SHALL NOT accept a labelled backup of another day.

Source: tests/flow_retention/test_purge.py (SansSauvegardeDuJour)

#### Scenario: No labelled backup
- **WHEN** `purge --apply` runs and only a plain dated backup exists for the day
- **THEN** the output holds "pre-purge backup missing: run the labelled backup first", nothing is deleted, and the exit code is 3

#### Scenario: Labelled backup of yesterday
- **WHEN** the only labelled backup is from the day before
- **THEN** the purge is refused in the same way

### Requirement: Retention tool output and session refusal
The system SHALL print in French by default and in English with `--language en`, SHALL refuse another language with exit code 2, and SHALL write in its output only store names, counts, ages in days and the key phrases of design D19. It SHALL refuse to start, with exit code 3 and the session key phrase of design D19, when the variable that Claude Code sets in its shells is present, before reading any setting. It SHALL NOT offer an option that bypasses that refusal.

Source: tests/flow_retention

#### Scenario: Started from a session
- **WHEN** the variable is present
- **THEN** the output holds "Refused inside a Claude Code session", nothing is read, and the exit code is 3

#### Scenario: Distinctive names absent
- **WHEN** the fixtures hold a distinctive string in every key, team, label, version and file name
- **THEN** none of them appears in the output of `check` or `purge`

### Requirement: Raw layer under the rule
The system SHALL count, and with `--apply` delete, the snapshots and sightings of tickets past the rule, and those older than the maximum file age except the latest snapshot and the last sighting of each ticket, on the store line of design D11. It SHALL NOT delete a run, SHALL NOT print a key, and SHALL keep its dry-run, labelled-backup and session rules. Untested until implemented.

#### Scenario: Resolved ticket past the rule
- **WHEN** a ticket resolved before the retention period has two snapshots
- **THEN** `check` counts them on the line "raw layer: 2 snapshots out of rule", and `purge --apply` deletes them with the ticket

#### Scenario: Old snapshots of an open ticket
- **WHEN** an open ticket still in the export has three snapshots older than the maximum file age and none newer
- **THEN** the two older ones are counted and deleted by `purge --apply`, and the latest one is kept

#### Scenario: Dry run
- **WHEN** `purge` runs without `--apply`
- **THEN** the raw-layer line is printed and every snapshot is still there

### Requirement: Story content under the one-year rule
The system SHALL treat a stored story or epic of the `quality` schema as past the rule when its text was collected, resolved or left the collection longer ago than the retention period, the tickets' setting. The system SHALL NOT exempt an open item whose text was not collected again, nor a resolved item collected recently.

Source: tests/flow_retention/test_contenu_stories.py; tests/flow_retention/test_base.py

#### Scenario: Text not collected again
- **WHEN** an open story's text was last collected thirteen months ago
- **THEN** it is past the rule, although the story is still open

#### Scenario: Recent collection of an old resolved story
- **WHEN** a story resolved two years ago was collected last week
- **THEN** it is past the rule

#### Scenario: Configured period
- **WHEN** the retention period is set to ninety days
- **THEN** the story content count uses the limit date ninety days before today

### Requirement: Story quality reports stay outside the rule
The system SHALL NOT count or delete the aggregated story quality reports, which hold no key, no text and no person, whatever their age, and SHALL NOT rewrite them.

Source: tests/flow_retention/test_contenu_stories.py (RapportsDeQualiteHorsRegle)

#### Scenario: Old aggregated report
- **WHEN** the reports folder holds a story quality report written more than one year ago
- **THEN** the check does not count it, its output is unchanged by it, and `purge --apply` leaves it in place with the same content

### Requirement: Files left from the CSV route are deleted whatever their age
The system SHALL count every CSV file of the exports folder and the former history cache file, whatever their age, on the store line of design D10 of the database-only change, and SHALL delete them with `purge --apply` under the labelled-backup and session rules. It SHALL NOT read their content, print their names, or delete another file on that line.

#### Scenario: Recent CSV file
- **WHEN** the exports folder holds a CSV file written today and the history folder holds the former cache file
- **THEN** `check` prints "files left from the CSV route: 2" and exits with code 4, the dry run deletes nothing, and `purge --apply` after the labelled backup of the day deletes both without printing their names

#### Scenario: Nothing left
- **WHEN** neither folder holds such a file
- **THEN** the line reads "files left from the CSV route: 0" and does not change the exit code

### Requirement: Version quality photos outside the rule
The system SHALL keep outside the rule the photo runs, photo rows, version register and register of N, which hold no key and no person: the check SHALL NOT count them and the purge SHALL NOT delete them, whatever their age. The purge of a ticket SHALL NOT change a photo.

Source: untested until implemented

#### Scenario: Old photo
- **WHEN** the store holds a photo taken more than one year ago and the tickets it counted are past the rule
- **THEN** the check does not count the photo, `purge --apply` deletes the tickets and leaves the photo rows unchanged

### Requirement: Version references under the rule
The system SHALL count, and with `purge --apply` delete in the flow transaction after the tickets, each version reference that no current asset version and no asset version period references and that was last seen longer ago than the retention period, with its version snapshots, on the version references line. It SHALL NOT delete a referenced version, nor print a number, short name or identifier.

#### Scenario: Unreferenced version seen 400 days ago
- **WHEN** a version reference no ticket references was last seen 400 days ago and the retention period is one year
- **THEN** `check` prints "version references: 1 out of rule" and exits with code 4, and `purge --apply` after the labelled backup of the day deletes it and its version snapshots

#### Scenario: Referenced old version kept
- **WHEN** a version reference last seen 400 days ago is still held by the asset version period of a stored ticket
- **THEN** it is not counted and not deleted

#### Scenario: Old version snapshots of a kept version
- **WHEN** a kept version reference has three version snapshots older than the maximum file age
- **THEN** `purge --apply` deletes the two older ones and keeps the latest

### Requirement: Delivery rows follow their ticket
The purge of a database ticket SHALL remove by cascade its delivery row, current sprints, current asset versions, option identifiers, defect fields (`flow.issue_defect_fields`), sprint periods and asset version periods, and the same transaction SHALL delete a sprint row no ticket references any longer. The system SHALL NOT keep a delivery row of a purged ticket.

#### Scenario: Ticket purged with delivery rows
- **WHEN** `purge --apply` deletes a ticket past the rule that holds a sprint, a target version and their periods
- **THEN** none of its delivery rows remains, its `flow.issue_defect_fields` row included (cascade of migration `0032` line 78, decision R-20261105-35 B3, tested by `tests/db/test_flow_delivery_fields.py` `test_les_tables_d_un_ticket_partent_en_cascade`), and the sprint row shared with a ticket within the rule is kept

#### Scenario: Sprint of purged tickets only
- **WHEN** the only tickets referencing a sprint are deleted by `purge --apply`
- **THEN** the sprint row is deleted in the same transaction
