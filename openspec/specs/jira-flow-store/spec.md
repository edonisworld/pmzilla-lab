# jira-flow-store Specification

## Purpose

Describes the read path from the `flow` database schema used by the flow and dependency reports (the `db` data source), and the guarantees that both data sources (CSV files and database) give identical reports regardless of reading order. Sources are the tests in `tests/flow_store/` (database tests are skipped without a disposable database).

## Requirements

### Requirement: Coverage of the history
The system SHALL return a history entry only for tickets marked as having history (an empty list for a ticket never moved), not one per ticket, so that coverage and dormant tickets count only the tickets the history collection has seen.

Source: tests/flow_store/test_couverture_historique.py (CouvertureDeLHistorique, skipped without the disposable database)

#### Scenario: Partial cache
- **WHEN** some tickets have transitions, some are marked as having history with no transition, and some are not marked
- **THEN** the history read returns the first two groups only, with empty lists exactly for the second

### Requirement: Read-only role
The system SHALL read the database under a dedicated read-only role, SHALL fail with a clear error that names the role (never the password) when the role is unusable, and SHALL reject any write attempt.

Source: tests/flow_store/test_flow_store.py (test_lecture_seule, test_role_inutilisable)

#### Scenario: Write attempt
- **WHEN** a delete is attempted over the read connection
- **THEN** the database refuses

### Requirement: Data source option
The system SHALL refuse, in the flow and dependency tools, the retired option `--source`, whatever its value, with exit code 2 and the key phrase of design D6, before any connection, and SHALL refuse an export file given as argument with exit code 2 and the key phrase of design D6. An unreachable database or a database missing on the server SHALL print a database error (French or English according to language), exit with code 1 and never print the password nor a traceback.

Source: tests/flow_store/test_erreurs_scripts.py (Erreurs)

#### Scenario: Unknown source
- **WHEN** `--source ftp`, `--source db` or `--source csv` is given
- **THEN** the exit code is 2, the output holds "--source is retired: the database is the only source", and no connection is attempted

#### Scenario: Files with database
- **WHEN** an export file is given without `--source`
- **THEN** the exit code is 2, the output holds "export files are no longer read: the database is the only source", and no connection is attempted

#### Scenario: Unreachable database
- **WHEN** the database does not answer
- **THEN** exit code 1, the message begins with the database error, and the password does not appear

### Requirement: Deterministic report ordering
The system SHALL order every list of a flow or dependency report by descending count then by name, and SHALL give byte-identical reports (console, Markdown, JSON, ageing points) whatever the reading order of the tickets or the order of history entries, including ties between types, resolutions, states and projects.

Source: tests/flow_store/test_ordre_rapports.py

#### Scenario: Two reading orders
- **WHEN** the same tickets are read in two different shuffled orders
- **THEN** the console output, every report file and the points files are equal

#### Scenario: Ranking
- **WHEN** the "closed without delivery" list is read
- **THEN** its entries are sorted by count descending then name

### Requirement: Out-of-export tickets left out of database reads
The system SHALL leave out of every database reader (flow tickets, dependency data, history) the tickets carrying an out-of-export instant. A link towards a marked ticket SHALL be read as a link towards a ticket outside the export. The readers SHALL NOT count marked tickets in work in progress, to-do, ages, dormant tickets, throughput or dependencies.

Source: tests/flow_store; reworded without the CSV comparison.

#### Scenario: Marked open ticket
- **WHEN** the database holds an open ticket marked out of the export
- **THEN** the flow report from the database does not count it in the work in progress

#### Scenario: Link to a marked ticket
- **WHEN** a ticket waits for a marked ticket
- **THEN** the dependency report shows that wait towards the "outside the export" node

### Requirement: Readers for the cycles report
The system SHALL provide, under the read-only role, a cycles-report reader returning each ticket with its declared-label and fix-version periods and its resolution day in the export time zone, plus status transitions only for tickets with a requested Epic Review label. No query SHALL return a marked ticket or the out-of-export instant.

Source: tests/flow_store/test_lecteurs_cycles.py

#### Scenario: Resolution day
- **WHEN** a ticket is resolved late in the evening UTC and the export time zone is ahead of UTC
- **THEN** its resolution day is the next local day

#### Scenario: Marked ticket
- **WHEN** a ticket carrying declared-label periods is marked out of the export
- **THEN** neither the ticket nor its periods are returned

### Requirement: Reader for the epic flow report
The system SHALL provide, under the read-only role, an epic reader returning for each stored epic its type, project, status, creation, resolution and resolution class (done or not done, from the excluded-resolutions list passed in), teams in attribution order, transitions and label periods by role, in the export time zone (design D13). The reader SHALL NOT return a marked ticket, a title, a person, an undeclared label, a label text or a resolution text. Untested until implemented.

#### Scenario: Epic with history
- **WHEN** the disposable database holds an epic with two transitions, one Epic Review label period and one domain label period, and a story
- **THEN** the reader returns the epic alone, with its two transitions, its two periods by role and its teams in attribution order, in the export time zone

#### Scenario: Label text kept inside
- **WHEN** a declared cycle label holds a distinctive string and names a cycle key
- **THEN** the reader returns the period with its role and cycle key, and the distinctive string appears nowhere in its result

#### Scenario: Resolution class
- **WHEN** one epic is resolved with a resolution on the excluded-resolutions list and another with a resolution that is not on it
- **THEN** the reader returns the class not done for the first and done for the second, and no resolution text

#### Scenario: Marked epic
- **WHEN** an epic is marked out of the export
- **THEN** neither the epic nor its transitions nor its periods are returned

### Requirement: Database readers feed the calculations
The system SHALL provide readers on the database that return the structures the calculations take: flow tickets, dependency data and history in the export time zone. The calculation tests SHALL obtain the same structures from their fixtures through a loader reserved to the tests (design D11). No product module SHALL read a CSV export.
#### Scenario: Fixture and database
- **WHEN** the same invented data are loaded through the test loader and read from a disposable database
- **THEN** the ticket lists are equal after sorting by key

#### Scenario: Other time zone
- **WHEN** the export time zone is changed
- **THEN** the values follow that zone and differ from a read in the default zone

#### Scenario: Unknown time zone
- **WHEN** the configured zone is unknown
- **THEN** a database error naming the zone is raised

## Open questions

1. `tests/flow_store/test_flow_store.py` (test_format_sans_heure) still passes the retired date-format setting with a format without time of day and expects the CSV and database reads to be equal with an empty resolution-to-the-minute field. The CSV readers now use the fixed export format (date with time), under which such dates are unreadable, and the database reader always fills the resolution minute. The test runs only with a disposable database and was not run for this baseline; whether it still passes, and whether it should be removed or rewritten, is not established.
