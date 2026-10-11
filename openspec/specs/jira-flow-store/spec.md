# jira-flow-store Specification

## Purpose

Describes the read path from the `flow` database schema used by the flow and dependency reports (the `db` data source), and the guarantees that both data sources (CSV files and database) give identical reports regardless of reading order. Sources are the tests in `tests/flow_store/` (database tests are skipped without a disposable database).

## Requirements

### Requirement: Database reads equal CSV reads
The system SHALL provide, for the report tools, readers on the database that return exactly the structures of the CSV readers for the same data: tickets for the flow report (including team lists, first-team attribution, "no team" label, resolution time to the minute), the dependency data (tickets, typed and untyped links with their direction, columns, parent keys, file list reduced to the database, no truncated exports), and the history (transitions per upper-cased key, as ISO dates with the offset of the export time zone, summer and winter offsets correct).

Source: tests/flow_store/test_flow_store.py

#### Scenario: Flow tickets
- **WHEN** the same invented data are read from CSV and from the database
- **THEN** the ticket lists are equal after sorting by key, and the found columns, unreadable count and duplicate count are equal

#### Scenario: Other time zone
- **WHEN** the export time zone is changed
- **THEN** values equal the CSV read in the same zone and differ from a read in the default zone

#### Scenario: Unknown time zone
- **WHEN** the configured zone is unknown
- **THEN** a database error naming the zone is raised

### Requirement: Coverage of the history
The system SHALL return a history entry only for tickets marked as having history (an empty list for a ticket never moved), not one per ticket, so that coverage and dormant tickets computed from the database equal those computed from the file cache, and a report computed with history and dormants SHALL be identical byte for byte from CSV plus cache and from the database. The comparison tool SHALL flag a difference in coverage as "tickets with history in the database only".

Source: tests/flow_store/test_couverture_historique.py

#### Scenario: Partial cache
- **WHEN** some tickets have transitions, some have an empty entry and some have no entry
- **THEN** the database read returns the same keys as the cache, with empty lists exactly for the empty entries

### Requirement: Read-only role
The system SHALL read the database under a dedicated read-only role, SHALL fail with a clear error that names the role (never the password) when the role is unusable, and SHALL reject any write attempt.

Source: tests/flow_store/test_flow_store.py (test_lecture_seule, test_role_inutilisable)

#### Scenario: Write attempt
- **WHEN** a delete is attempted over the read connection
- **THEN** the database refuses

### Requirement: Data source option
The system SHALL let the flow and dependency tools choose the source with `--source csv|db`, default `csv`. The CSV path SHALL NOT load the database driver. An unknown source SHALL stop with exit code 1, naming the option and the value, without traceback. CSV files given with the database source SHALL be refused (before any connection) in French and English, and no file with the CSV source SHALL keep the "missing export argument" error. An unreachable database or a database missing on the server SHALL print a database error (French or English according to language), exit with code 1 and never print the password nor a traceback.

Source: tests/flow_store/test_sources_scripts.py (VoieCsvSansPsycopg, Erreurs)

#### Scenario: Unknown source
- **WHEN** `--source ftp` is given
- **THEN** exit code 1 and the message names the option and the value

#### Scenario: Files with database
- **WHEN** CSV files are passed with the database source
- **THEN** exit is non-zero with "no CSV file may be given" and no connection is attempted

#### Scenario: Unreachable database
- **WHEN** the database does not answer
- **THEN** exit code 1, the message begins with the database error, and the password does not appear

### Requirement: Same reports from both sources
The system SHALL produce the same console output and the same report files from the database as from CSV files holding the same data, for the status listing, the flow report (also with history and dormants and with a scope), the dependency diagnosis, and the dependency reports by team and by project in both languages (only the source label differing).

Source: tests/flow_store/test_sources_scripts.py (RapportsIdentiques)

#### Scenario: Flow report
- **WHEN** the flow report is computed from CSV and from the database
- **THEN** the Markdown and JSON are identical

#### Scenario: Shuffled and split exports
- **WHEN** the CSV is shuffled or split into two files in either order
- **THEN** the reports equal the database report once file-merge lines and file names are normalized, and a single file gives a byte-identical flow report

### Requirement: Deterministic report ordering
The system SHALL order every list of a flow or dependency report by descending count then by name, and SHALL give byte-identical reports (console, Markdown, JSON, ageing points) whatever the reading order of the tickets or the order of history entries, including ties between types, resolutions, states and projects.

Source: tests/flow_store/test_ordre_rapports.py

#### Scenario: Two reading orders
- **WHEN** the same tickets are read in two different shuffled orders
- **THEN** the console output, every report file and the points files are equal

#### Scenario: Ranking
- **WHEN** the "closed without delivery" list is read
- **THEN** its entries are sorted by count descending then name

## Open questions

1. `tests/flow_store/test_flow_store.py` (test_format_sans_heure) still passes the retired date-format setting with a format without time of day and expects the CSV and database reads to be equal with an empty resolution-to-the-minute field. The CSV readers now use the fixed export format (date with time), under which such dates are unreadable, and the database reader always fills the resolution minute. The test runs only with a disposable database and was not run for this baseline; whether it still passes, and whether it should be removed or rewritten, is not established.
