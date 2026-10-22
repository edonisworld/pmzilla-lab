# jira-flow-raw-layer Specification

## Purpose
TBD - created by archiving change jira-data-architecture. Update Purpose after archive.

## Requirements

### Requirement: One dated run per export
The system SHALL record, in the export's raw-layer transaction, one run per successful export (kind, instant, number of named queries searched, and whether every named query of the settings was searched) and one sighting per ticket key read and kept after the retention skip (design D3, D4). It SHALL NOT record a file name, a query name, a title, a description or a person in a run, and SHALL leave no run, sighting or snapshot after a failed export. Untested until implemented.

#### Scenario: First export
- **WHEN** an export of two named queries returning three tickets in all succeeds against a fake Jira server and a disposable database
- **THEN** one run of kind export exists, marked as covering every named query, with three sightings, and the run holds no file name and no query name

#### Scenario: One query only
- **WHEN** the export runs with `--query` naming one of two configured queries
- **THEN** its run is marked as not covering every named query

#### Scenario: Failed export
- **WHEN** Jira refuses a page after the first one
- **THEN** no run, sighting or snapshot of that export remains

### Requirement: Snapshot only when a ticket changes
The system SHALL write a snapshot of a ticket's allowed attributes (design D3) for a new ticket, or when its content differs from its latest snapshot, its teams included. It SHALL NOT write a snapshot for an unchanged ticket, for a ticket whose updated instant precedes that of its latest snapshot, or for a ticket past retention, and a snapshot SHALL NOT hold a title, a description, a person, a declared label or a fix version. Untested until implemented.

#### Scenario: Second export
- **WHEN** the same tickets are exported twice with no change in Jira
- **THEN** the second run adds sightings but no snapshot

#### Scenario: One field changes
- **WHEN** a later export finds the status of one ticket changed
- **THEN** exactly one snapshot is added, for that ticket

### Requirement: Snapshot teams keep their Jira identifiers
The system SHALL store each team of a snapshot, in column order, with its translated name and, when the team field returned an asset identifier, that Jira team identifier, an identifier found in neither translation source included (team-mapping Q2 (a)). A change of the name translated for an identifier SHALL count as a change of the ticket. It SHALL NOT print a team identifier on the raw-layer line. Untested until implemented.

#### Scenario: Team identifiers kept
- **WHEN** the team field returns two asset identifiers for a ticket, one in the translation sources and one unknown
- **THEN** its snapshot holds both identifiers in API order, the first with its translated name and the second with the unknown-team marker

#### Scenario: Mapping corrected
- **WHEN** the name translated for an identifier changes between two exports and nothing else changes
- **THEN** one snapshot is added for each ticket carrying that identifier

### Requirement: Raw layer is append-only
The system SHALL NOT update or delete a run, a sighting or a snapshot during an export, an import or a rebuild, and SHALL leave every raw deletion to the retention purge. Untested until implemented.

#### Scenario: Rebuild applied
- **WHEN** a rebuild runs with `--apply`
- **THEN** every run, sighting and snapshot present before it is unchanged after it

### Requirement: Raw-layer counts without content
The system SHALL print on every successful export the raw-layer line of design D11 ("raw layer: {s} tickets seen, {n} snapshots added" in English) with counts only. It SHALL NOT print a ticket key, a team name, a team identifier or a field value on that line. Untested until implemented.

#### Scenario: Distinctive names absent
- **WHEN** the fake Jira server returns a distinctive string in every key and team label
- **THEN** the raw-layer line appears and none of those strings is printed

### Requirement: Rebuild is a comparison by default
The system SHALL, with `flow_import.py --rebuild`, rebuild ticket rows, teams per ticket and links from the latest snapshot of each ticket, using the team names stored in the snapshot, compare them with the live tables and print the counts of design D11. Without `--apply` it SHALL write nothing. It SHALL NOT rebuild out-of-export instants, transitions, history flags or periods, and SHALL NOT read the organisation referential or the team catalogue. The out-of-export instants are replayed by the import from the sightings of the last export run (jira-flow-import, "Import derives from the raw layer without files"), never by the rebuild.

Source: tests/flow_import/test_reconstruction.py (Champs, Reconstruction); database scenarios: the ten database tests of the former `tests/flow_import/test_reconstruction_base.py`, which built their data through the CSV import and were removed with it, are rewritten on the raw layer by amendment task 14.5 (decided by the author on 2026-10-18, design D16): their data are written as export runs of the raw layer (or seeded with `--seed`), then derived by the import, never read from a file; they run on the disposable database.

#### Scenario: Database scenarios rebuilt on the raw layer
- **WHEN** the database suite of the rebuild runs on the disposable database
- **THEN** each of its ten tests builds its tickets through raw-layer runs and the import, no test of the suite reads or writes an export file, and the scenarios of this requirement and of "Rebuild refusals and usage errors" are covered

#### Scenario: Right after an import
- **WHEN** a rebuild runs without `--apply` just after an export and the import that derived it
- **THEN** the output says no ticket would change and ends with "rebuild dry run: nothing written"

#### Scenario: Altered live row
- **WHEN** a live ticket status was altered under the import role and the rebuild runs without `--apply`
- **THEN** the output counts one difference on the status field, without its value, and the row is still altered

#### Scenario: Out-of-export mark left alone
- **WHEN** a ticket carries an out-of-export instant and the rebuild runs with `--apply`
- **THEN** its out-of-export instant is unchanged

### Requirement: Rebuild applied in one transaction
The system SHALL, with `--rebuild --apply`, write the rebuilt state in one transaction rolled back on any error, create missing teams, and SHALL NOT delete a team, a transition or a period. Untested until implemented.

#### Scenario: Restored row
- **WHEN** the rebuild runs with `--apply` after a live row was altered
- **THEN** the row equals its latest snapshot, the output ends with "rebuild done: 1 tickets changed", and a following dry run reports no difference

#### Scenario: Error during the rebuild
- **WHEN** the database raises an error while the rebuild writes
- **THEN** no live row is changed, the error type alone is printed, and the exit code is 1

### Requirement: Rebuild refusals and usage errors
The system SHALL refuse a rebuild with exit code 1, before any write, when the raw layer is empty or when stored tickets have no snapshot (count printed). It SHALL exit with code 2, before any connection: for an export file, with or without `--rebuild`, with the import's export-file phrase of design D6 of the database-only change; for `--history`, with or without `--rebuild`, with the import's `--history` phrase of design D6; for `--apply` or `--seed` without `--rebuild`, and `--mark-absent` or `--dry-run` with it, with the phrases of design D11.

Source: tests/flow_import/test_reconstruction.py (Reconstruction, UsageEtRefus); the database refusals in the rewritten `tests/flow_import/test_reconstruction_base.py` (amendment task 14.5)

#### Scenario: Empty raw layer
- **WHEN** the rebuild runs on a database whose raw layer is empty
- **THEN** the output holds "raw layer empty: rebuild refused", nothing is written, and the exit code is 1

#### Scenario: Files given
- **WHEN** `--rebuild` is given with an export file
- **THEN** the output holds "export files are no longer read: the import derives from the raw layer" and the exit code is 2

#### Scenario: Dry run option given
- **WHEN** `--rebuild --apply --dry-run` is given
- **THEN** the output holds "--mark-absent and --dry-run are not accepted with --rebuild", nothing is written, and the exit code is 2

### Requirement: Seeding from the live tables
The system SHALL, with `--rebuild --seed`, write one seeded snapshot built from the live row for each stored ticket without any snapshot, attached to a run of kind seed, print the seed line of design D11, and SHALL NOT replace or duplicate an existing snapshot. A seeded snapshot SHALL hold the team names of the live tables and no team identifier. Untested until implemented.

#### Scenario: Seed then rebuild
- **WHEN** a database imported before the raw layer existed is seeded, then rebuilt without `--apply`
- **THEN** every stored ticket has one snapshot and the rebuild reports no difference

### Requirement: Raw layer kept from readers and views
The system SHALL NOT let the flow and dependency report readers, the cycles reader, the four aggregated views or the views role read the raw tables. Reports SHALL stay computed from the derived tables only. Untested until implemented.

#### Scenario: Views role
- **WHEN** the views role selects from a raw table
- **THEN** the database refuses for insufficient privilege
