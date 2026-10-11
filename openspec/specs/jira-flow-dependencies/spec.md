# jira-flow-dependencies Specification

## Purpose

Describes the dependency report tool: from the link columns of an export (or the database), it builds a matrix of who waits for whom between teams (or projects), lists current blockages by state of the blocker, produces graph data, ageing facts and a lead-time comparison with and without external dependency. Reports never contain a ticket key. Sources are the tests in `tests/dependencies_jira/`.

## Requirements

### Requirement: Subcommands and former names
The system SHALL offer `diagnose` and `compute`, SHALL refuse former subcommand names with exit code 2, and SHALL accept former option names and former `--by` value names with a warning naming the new one, producing the same report. Former setting names SHALL be accepted with a warning; the report SHALL equal the one produced with the new names, and new names SHALL produce no warning.

Source: tests/dependencies_jira/test_dependencies_jira.py (AnciensNoms)

#### Scenario: Former option and value
- **WHEN** the former name, "by" and "weeks" options and the former value for project aggregation are used
- **THEN** warnings name the new option and value, and the JSON equals the one produced with the new names

#### Scenario: Former setting names
- **WHEN** settings use former names
- **THEN** a warning names the new key, and the report equals the new-name report

### Requirement: Direction of links
The system SHALL read typed link columns (outward and inward per type) and treat a blocking link seen from both ends as a single dependency, with the row team waiting for the column team in the matrix. Link types configured as "waiting" SHALL be read in the opposite direction, and any other link type SHALL be ignored. When links come untyped, the mode SHALL be "undirected", no blockage list SHALL be produced, and the diagnosis SHALL say so.

Source: tests/dependencies_jira/test_dependencies_jira.py (Sens)

#### Scenario: Link seen from both sides
- **WHEN** one ticket blocks another and both rows carry the link
- **THEN** the dependency is counted once, the mode is "directed", and the open matrix has the waiting team as row and the blocking team as column

#### Scenario: Blocker already finished
- **WHEN** the blocker is finished
- **THEN** the link appears in the total matrix but not in the open matrix

#### Scenario: Unknown link type
- **WHEN** only a non-blocking link type is present
- **THEN** zero dependencies are counted

### Requirement: Open blockages by blocker state
The system SHALL list current blockages per pair of teams with the state of the blocker ("in progress" or "not started") and counts, with ageing figures, and SHALL put blockages older than a configurable age separately.

Source: tests/dependencies_jira/test_dependencies_jira.py (Sens, Anciennete.test_blocage_de_plus_d_un_an_est_a_part)

#### Scenario: Blocker states
- **WHEN** one blocker is in progress and another not started
- **THEN** each pair carries its state

#### Scenario: Old blockage
- **WHEN** a blocked ticket has been waiting longer than the configured age
- **THEN** it appears in the "old blockages" list and not in the ordinary list

### Requirement: Graph data
The system SHALL provide, per team pair, an edge with counts of open, unknown and total dependencies, the number of blocked tickets in progress, the age percentiles of those blocked tickets, and a directed flag (false in undirected mode), plus the number of tickets per team. A dependency towards a ticket absent from the export SHALL appear as an edge to an "outside the export" node counted as unknown. The graph data SHALL contain no ticket key.

Source: tests/dependencies_jira/test_dependencies_jira.py (AretesDuGraphe)

#### Scenario: Finished blocker
- **WHEN** the blocker is finished
- **THEN** its edge has zero open, one total, no blocked in progress and no age

#### Scenario: Ticket outside export
- **WHEN** a link points to a ticket not in the export
- **THEN** the edge to the outside node has one unknown and zero open

### Requirement: Links to tickets outside the export
The system SHALL count waits towards tickets absent from the export, list them by project (unknown waits), report their share, and warn on the console when more than a configurable share of dependencies point outside the export.

Source: tests/dependencies_jira/test_dependencies_jira.py (ManuelEtApi, Anciennete.test_attente_vers_un_element_hors_export); tools/dependencies_jira.py (cmd_diagnostic)

#### Scenario: Two waits outside
- **WHEN** two tickets wait on tickets of one project missing from the export
- **THEN** the unknown waits list that project with the count two and the outside-export total is two

### Requirement: Manual and API exports give the same map
The system SHALL produce the same report from an export in the manual layout and from the API export for the same tickets, apart from the export information and the name.

Source: tests/dependencies_jira/test_dependencies_jira.py (ManuelEtApi.test_meme_carte_depuis_le_csv_manuel_et_le_csv_de_l_api)

#### Scenario: Same data in both layouts
- **WHEN** both layouts are computed
- **THEN** the reports are equal once the export and name keys are removed

### Requirement: No key nor ticket name in outputs
The system SHALL NOT write ticket keys in the diagnosis output or in the Markdown or JSON reports, and SHALL NOT write team names in the diagnosis output (team names appear in the reports); the `--keys` option SHALL show blockages with keys on the console only.

Source: tests/dependencies_jira/test_dependencies_jira.py (ManuelEtApi, AretesDuGraphe)

#### Scenario: Diagnosis
- **WHEN** `diagnose` runs on an export
- **THEN** it prints the mode, the link types found, and the meaning of the directions without any key or team name

#### Scenario: Keys option
- **WHEN** `compute` runs with the keys option
- **THEN** the console shows lines of the form "ticket (team) waits for ticket (team, state)" and the files stay key-free

### Requirement: Database source
The system SHALL read the export files by default (no source, or `csv`) and SHALL accept the option `--source db` for the dependency report, reading the tickets and links from the database instead of the export files (no CSV file read, settings passed to the database reader), and this SHALL be the target path for the dependency report. With the database source the source list of the report SHALL name the database ("base" in French, "database" in English) instead of file names. An unknown source SHALL stop with a message naming the value and the allowed values ("csv, db"). Files given with the database source SHALL be refused before any connection, with "no CSV file may be given" (French equivalent in French). A database error SHALL stop with the database-read message followed by the error detail. The report SHALL keep the same content and the same confidentiality rules (no ticket key, no title) whatever the source.

Source: tests/dependencies_jira/test_source.py; end-to-end parity with a database: tests/flow_store/test_sources_scripts.py

#### Scenario: Database source
- **WHEN** `compute` runs with `--source db`
- **THEN** the dependencies are read from the database, no export file is read, and the source is named "database" in English

#### Scenario: Files with database
- **WHEN** CSV files are passed with the database source
- **THEN** the run stops with "no CSV file may be given" and no connection is attempted

#### Scenario: Unknown source
- **WHEN** `--source ftp` is given with `--language en`
- **THEN** the message names the unknown value "ftp" and the allowed values "csv, db"

### Requirement: Merging several exports and truncation hint
The system SHALL merge several exports by key, and SHALL warn in the diagnosis and record in the report when the ticket count is a round number (a sign of a truncated export; not for the database source). A missing key column SHALL stop with a message.

Source: tests/dependencies_jira/test_dependencies_jira.py (ManuelEtApi)

#### Scenario: Round number
- **WHEN** an export holds a round number of tickets
- **THEN** the diagnosis warns that a round number suggests truncation and the report lists one truncated export

#### Scenario: Missing key column
- **WHEN** the export has no key column
- **THEN** the exit code is 1 and the message says the column is absent

### Requirement: Project scope
The system SHALL, with `--scope` (or a settings list), keep dependencies of which at least one side belongs to the listed projects, report the number of tickets in scope, let the option replace the setting, and let the word "all" disable it. The diagnosis SHALL state the scope.

Source: tests/dependencies_jira/test_dependencies_jira.py (Perimetre)

#### Scenario: Scope of one project
- **WHEN** the scope is a project with two dependencies on it
- **THEN** the report shows two dependencies and two tickets in scope

#### Scenario: Option overrides setting
- **WHEN** a scope exists in the settings and the option is "all"
- **THEN** all links are counted

### Requirement: Exclusions
The system SHALL count dependencies of excluded projects separately (waits for the export and awaited by the export) and remove them from the matrices, SHALL leave decomposition links involving a portfolio-level ticket type out of the main map (counted by type and mapped in a separate portfolio matrix when both ends are of that kind), SHALL accept the former setting name for portfolio types, SHALL attribute tickets without a team to a "no team" label that keeps the project, and SHALL support aggregation by project with `--by project` into a separately named report.

Source: tests/dependencies_jira/test_dependencies_jira.py (Exclusions)

#### Scenario: Excluded project
- **WHEN** a project is excluded
- **THEN** its links appear in the excluded list and not in the dependency count or the matrix

#### Scenario: Portfolio decomposition
- **WHEN** an epic points to a story and another epic to an epic
- **THEN** the first is a decomposition link left out of the total matrix and the second goes to the portfolio matrix

#### Scenario: Team missing
- **WHEN** a ticket has no team
- **THEN** it appears as "no team" plus its project

### Requirement: Old portfolio epics
The system SHALL report old portfolio-type tickets that have open links, grouped by team and by vitality: alive (a child changed recently), inactive children, or no delivery child. A recent epic, one without an open link, and children closed without delivery SHALL NOT count as activity.

Source: tests/dependencies_jira/test_dependencies_jira.py (Anciennete)

#### Scenario: Three classifications
- **WHEN** three old epics have respectively a recently active child, only an old active child, and no child
- **THEN** each team line shows its classification

### Requirement: Lead time with and without external dependency
The system SHALL compare, per ticket type, lead-time percentiles of delivered tickets that waited for another team's ticket with those that did not (a blocker that blocks no one belongs to the second group), and SHALL exclude tickets closed without delivery.

Source: tests/dependencies_jira/test_dependencies_jira.py (LeadTime)

#### Scenario: With and without
- **WHEN** five delivered tickets waited on another team and eleven did not
- **THEN** the with-dependency group has five tickets with its median and the without group eleven

#### Scenario: Rejected only
- **WHEN** all closed tickets were rejected
- **THEN** the lead-time table is empty

### Requirement: Message language
The system SHALL print messages and reports in French by default and in English with `--language en`, matching the English reference without French words, and accept the former option name with a warning.

Source: tests/dependencies_jira/test_language.py

#### Scenario: English output
- **WHEN** `--language en` is used
- **THEN** the output equals the English reference

## Open questions

1. Exact names of the report files and the graph/diagram output (Mermaid in the Markdown) are not asserted by tests.
