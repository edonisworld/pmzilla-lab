# jira-flow-import Specification

## Purpose

Describes the tool that reads API-export CSV files and imports them incrementally into the `flow` schema of the local database (tickets, teams, links, status transitions). The import never prints a ticket key, a team name or a field value. Sources are the tests in `tests/flow_import/` (database tests use a disposable database and are skipped without it).

## Requirements

### Requirement: Export reading
The system SHALL read one or more API-export CSV files into tickets with key, project (derived from the key), type, status, state category, resolution, parent key, story points (decimal; comma or point; empty or non-numeric becomes none), the creation, resolution, category-change and updated instants, the distinct teams in column order (several team columns and semicolon-separated values; blank entries dropped), and links. Naive dates SHALL be interpreted in the export time zone (configurable, daylight saving respected) and converted to UTC instants. When several files are given, the last file SHALL win for a repeated key. A row with an unreadable creation date SHALL be dropped and counted. A missing file SHALL raise a "file unreadable" error.

Source: tests/flow_import/test_reader.py; tests/flow_import/test_import.py (Import)

#### Scenario: Summer and winter offsets
- **WHEN** a summer date and a winter date are read
- **THEN** their UTC offsets differ by the daylight-saving shift of the configured zone

#### Scenario: Links typed and untyped
- **WHEN** a row has outward, inward typed link columns and an untyped linked-issues column
- **THEN** each link is read with its type and direction (direction none for untyped), and duplicates within a row are kept distinct only by their tuple

#### Scenario: No link column
- **WHEN** the export has no link column
- **THEN** the ticket's links are "not tracked" (none), not an empty list

#### Scenario: Last file wins
- **WHEN** two files share a key
- **THEN** the second file's values are kept

### Requirement: Updated column mandatory
The system SHALL refuse an export whose updated column is missing, or whose updated value is unreadable or empty, with exit code 1, before writing anything, naming the file and the column but never a value or a key, and SHALL not fall back to the import time.

Source: tests/flow_import/test_reader.py; tests/flow_import/test_import.py (Refus)

#### Scenario: Missing column
- **WHEN** the updated column is absent
- **THEN** the exit code is 1, the error names the file and "Updated", no ticket is written, and no key is printed

#### Scenario: Unreadable value
- **WHEN** the updated cell holds an unreadable text
- **THEN** the message names the column but not the text

### Requirement: Incremental ticket upsert
The system SHALL insert new tickets, update a ticket only when a field differs (a difference in the updated date alone counts), leave unchanged tickets alone, and SHALL NOT overwrite a ticket with an export whose updated date is older than the stored one. Tickets absent from a new export SHALL be kept. The console SHALL report counts only: read, inserted, updated, unchanged, unreadable, teams created, links added, links removed.

Source: tests/flow_import/test_import.py (Import)

#### Scenario: Reimport
- **WHEN** the same export is imported twice
- **THEN** the second run reports every ticket unchanged and zero created teams and links

#### Scenario: Older export
- **WHEN** an export with an older updated date is imported
- **THEN** the stored values are kept and the ticket counts as unchanged

#### Scenario: Two files
- **WHEN** two files are imported together
- **THEN** tickets are merged by key and the last file wins

### Requirement: Teams per ticket
The system SHALL create teams on the fly, attribute each ticket to the first team (or none when empty), and store all distinct teams with their positions, writing only the difference when a ticket's teams change and keeping what is unchanged.

Source: tests/flow_import/test_import.py (test_multi_equipes_sans_equipe)

#### Scenario: Team change
- **WHEN** one ticket's teams change from two to one
- **THEN** only that ticket's team rows change and the others are kept

### Requirement: Links without duplicates
The system SHALL add only new links and remove links that disappeared from the export, never duplicate a link on reimport, and keep the existing links of a ticket when the new export has no link column at all.

Source: tests/flow_import/test_import.py (test_liens_sans_doublon_au_reimport, test_export_sans_colonne_de_liens_garde_les_liens)

#### Scenario: Link vanished
- **WHEN** a link has disappeared and another appeared
- **THEN** one is removed and one is added in the counts

### Requirement: Dates and time zone
The system SHALL read dates only in the fixed format of the API export (day, abbreviated month, year, hour and minute), with no date-format setting; a date at midnight SHALL be read as the instant of local midnight, expressed in UTC, while a date without a time of day SHALL be unreadable, so that a row whose creation date has no time is dropped and counted as unreadable. The system SHALL use the configured time zone instead of the default when set, with the summer and winter offsets of that zone.

Source: tests/flow_import/test_import.py (test_format_de_date_fixe_avec_heure, test_fuseau_ete_et_hiver, test_fuseau_reglable)

#### Scenario: Midnight
- **WHEN** a date is written at 00:00
- **THEN** it becomes the instant of local midnight, expressed in UTC

#### Scenario: Date without time
- **WHEN** a row's dates have no time of day
- **THEN** the row is not imported and the unreadable count is one

#### Scenario: Configured zone
- **WHEN** the time zone setting names another zone than the default
- **THEN** local times are converted to UTC with the offset of that zone, not of the default

### Requirement: Transition import
The system SHALL, only when `--history` is given (optionally with a cache path, default the history cache), import transitions from the history cache: epoch milliseconds or ISO dates with offsets converted to UTC instants, keys matched case-insensitively, entries for keys absent from the database ignored and counted, unreadable dates counted, existing transitions never deleted and never duplicated, new transitions of a known ticket added. A ticket with a cache entry, even with no transition, SHALL be marked as having history, and a later run without the history option SHALL neither mark nor unmark tickets. A missing or invalid cache SHALL stop with exit code 1 and a message naming the option, writing nothing. Without the option no transition SHALL be written and the transitions line SHALL not appear.

Source: tests/flow_import/test_import.py (Transitions)

#### Scenario: Mixed cache
- **WHEN** the cache holds a normal entry, an entry with epoch milliseconds and an unreadable date, and a key absent from the export
- **THEN** three transitions are added, one entry is ignored for having no ticket, one date is counted unreadable

#### Scenario: Empty entry
- **WHEN** a cache entry has no transition
- **THEN** its ticket is marked as having history and counted as new once

### Requirement: Single transaction and failure behavior
The system SHALL perform the import in one transaction that is rolled back on any error, reduce a database error to the name of its type, never print keys or team names in errors, and, when the database is unreachable, print the database connection error with exit code 1.

Source: tests/flow_import/test_import.py (Refus, test_erreur_en_cours_d_import_annule_tout)

#### Scenario: Mid-import failure
- **WHEN** an unexpected error happens after tickets were written
- **THEN** exit code 1, the error type name is printed, no key or team name appears, and no ticket or team remains

### Requirement: Dry run and output hygiene
The system SHALL, with `--dry-run`, compute the same counts in the database and roll back, writing nothing, and SHALL never print a ticket key, team name or field value in any mode or language. English output SHALL be available with `--language en`.

Source: tests/flow_import/test_import.py (EssaiEtSortie)

#### Scenario: Dry run counts
- **WHEN** an import runs with `--dry-run` and then for real
- **THEN** the counts lines are identical and tables are empty after the first

#### Scenario: English
- **WHEN** `--language en` is given
- **THEN** the output includes "Tickets read" and "Transitions added ... ignored without ticket" lines

## Open questions

1. The write role used by the import and the rule that only the user runs it are access-control facts documented in code comments; confirm whether to specify them here.
