# jira-flow-dependencies Specification

## Purpose

Describes the dependency report tool: from the link columns of an export (or the database), it builds a matrix of who waits for whom between teams (or projects), lists current blockages by state of the blocker, produces graph data, ageing facts and a lead-time comparison with and without external dependency. Reports never contain a ticket key. Sources are the tests in `tests/dependencies_jira/`.

## Requirements

### Requirement: Subcommands and former names
The system SHALL offer `diagnose` and `compute`, SHALL refuse former subcommand names with exit code 2, SHALL refuse former option names and former `--by` value names with exit code 2 and a message naming the current one, writing no report, and SHALL refuse former setting names with exit code 1, naming the current key. New names SHALL produce no such message.

Source: tests/dependencies_jira/test_dependencies_jira.py (AnciensNoms)

#### Scenario: Former option and value
- **WHEN** the former name, "by" or "weeks" option, or the former value for project aggregation, is used
- **THEN** the exit code is 2, the message names the current option or value, and no report is written

#### Scenario: Former setting names
- **WHEN** settings use a former name
- **THEN** the exit code is 1 and the message names the current key; with the new names the run prints no such message

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
The system SHALL read the tickets and links only from the database, with the settings passed to the database reader, and the source list of the report SHALL name the database ("base" in French, "database" in English). The retired option `--source`, whatever its value, SHALL stop with exit code 2 and the key phrase of design D6, and an export file given as argument SHALL stop with exit code 2 and the key phrase of design D6, before any connection. A database error SHALL stop with the database-read message followed by the error detail. The report SHALL keep the same confidentiality rules (no ticket key, no title).

Source: tests/dependencies_jira/test_lecteur_base.py (Lecture, Refus); tests/flow_store/test_erreurs_scripts.py (Erreurs)

#### Scenario: Database source
- **WHEN** `compute` runs with no option
- **THEN** the dependencies are read from the database, no file is read, and the source is named "database" in English

#### Scenario: Files with database
- **WHEN** an export file is given, with or without `--source db`
- **THEN** the run stops with exit code 2, no connection is attempted, and the output holds "--source is retired: the database is the only source" when the option is given, "export files are no longer read: the database is the only source" otherwise

#### Scenario: Unknown source
- **WHEN** `--source ftp` is given with `--language en`
- **THEN** the message is "--source is retired: the database is the only source" and the exit code is 2

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
The system SHALL count dependencies of the projects excluded from the map separately (waits for the export and awaited by the export) and remove them from the matrices. The list in force SHALL be, in this order, the exclusion option, else the map's own exclusion setting when present (an empty list excluding nothing), else the shared excluded-projects setting. The system SHALL NOT merge the two settings into one list.

Source: tests/dependencies_jira/test_dependencies_jira.py (Exclusions); precedence: tests/dependencies_jira/test_exclusion_carte.py (to be written, task 3.1)

#### Scenario: Excluded project
- **WHEN** a project is excluded
- **THEN** its links appear in the excluded list and not in the dependency count or the matrix

#### Scenario: Map setting over the shared setting
- **WHEN** the shared setting excludes one project and the map's setting excludes another
- **THEN** only the project of the map's setting leaves the matrices, and the links of the other are counted in them

#### Scenario: Empty map setting
- **WHEN** the map's setting is present with an empty list and the shared setting excludes a project
- **THEN** no project is excluded from the map

### Requirement: Portfolio decomposition links
The system SHALL leave decomposition links involving a portfolio-level ticket type out of the main map (counted by type and mapped in a separate portfolio matrix when both ends are of that kind), and SHALL refuse the former setting name for portfolio types (exit code 1, naming the current one).

Source: tests/dependencies_jira/test_dependencies_jira.py (Exclusions)

#### Scenario: Portfolio decomposition
- **WHEN** an epic points to a story and another epic to an epic
- **THEN** the first is a decomposition link left out of the total matrix and the second goes to the portfolio matrix

#### Scenario: Former portfolio-types name
- **WHEN** the settings use the former name of the portfolio-types setting
- **THEN** the run exits with code 1 and the message names the current setting

### Requirement: Tickets without a team
The system SHALL attribute tickets without a team to a "no team" label that keeps the project.

Source: tests/dependencies_jira/test_dependencies_jira.py (Exclusions)

#### Scenario: Team missing
- **WHEN** a ticket has no team
- **THEN** it appears as "no team" plus its project

### Requirement: Aggregation by project
The system SHALL support aggregation by project with `--by project` into a separately named report.

Source: tests/dependencies_jira/test_dependencies_jira.py (Exclusions)

#### Scenario: Project matrix
- **WHEN** `compute` runs with `--by project`
- **THEN** a separately named report holds the matrix between projects

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
The system SHALL print messages and reports in French by default and in English with `--language en`, matching the English reference without French words, and refuse the former option name with a non-zero exit code and a message naming the current one, printing nothing on stdout.

Source: tests/dependencies_jira/test_language.py

#### Scenario: English output
- **WHEN** `--language en` is used
- **THEN** the output equals the English reference

### Requirement: Aggregation by Mission Team or site
The system SHALL accept on `compute` the `--by` values `mission-team` and `site` in addition to `team` and `project`. With these values it SHALL read the organisation referential and build the matrices, blockages and graph data between groups, with teams outside the referential grouped under "outside the referential", into a separately named report, on both data sources. A dependency between two teams of the same group SHALL be counted as internal to the group and stated, not hidden. A missing or invalid referential SHALL stop with exit code 1 naming the referential, never a value. The report SHALL NOT divide a dependency count by a headcount and SHALL NOT rank groups.

Source: tests/dependencies_jira/test_par_groupe.py

#### Scenario: Mission Team matrix
- **WHEN** `compute --by mission-team` runs on links between three teams of two Mission Teams
- **THEN** the matrix has two rows and columns, the internal dependencies of each Mission Team are stated, and the totals equal those of the team report

#### Scenario: Referential missing
- **WHEN** `compute --by mission-team` runs without a referential
- **THEN** the exit code is 1 and no report is written

### Requirement: Labels and versions absent from the dependency report
The system SHALL NOT write a label or a version name in the diagnosis, the reports or the console of the dependency tool, including with the keys option.

Source: tests/dependencies_jira/test_chaines_distinctives.py; tests/dependencies_jira/test_colonnes_ignorees.py

#### Scenario: Keys option
- **WHEN** `compute` runs with the keys option on data holding a distinctive label and version
- **THEN** the console lines hold keys, teams and states only

### Requirement: Map exclusion setting
The system SHALL apply the map's own exclusion setting, project keys compared without case or surrounding spaces, to the map only, in every view. Without it, the matrices, counts, lead-time groups and old blockages SHALL equal those of the shared setting alone. The system SHALL NOT write the values of the setting in the source line.

Source: tests/dependencies_jira/test_exclusion_carte.py; tests/dependencies_jira/test_lecteur_base.py (ExclusionAvecLaBase)

#### Scenario: No map setting
- **WHEN** the settings hold only the shared exclusion list
- **THEN** the matrices, counts, lead-time groups and old blockages equal those of the tool before the exclusion change

#### Scenario: Project view
- **WHEN** `compute --by project` runs with the map's setting
- **THEN** the projects of that setting are absent from the project matrix and counted in the excluded list

#### Scenario: Database source
- **WHEN** the report is computed from the database with the map's setting
- **THEN** the report applies that list, and its source line names the map setting without its values

### Requirement: Exclusion option
The system SHALL accept `--exclude` on `diagnose` and `compute`: comma-separated project keys, empty entries ignored, or the word `none` or `aucun` to exclude nothing. The option SHALL replace both settings for the run and SHALL NOT write to the settings file. An option holding no key SHALL stop with exit code 2 and the empty-exclusion key phrase of design D4, before any export or database read, writing no report.

Source: tests/dependencies_jira/test_exclusion_carte.py (to be written, task 3.1)

#### Scenario: Option over the settings
- **WHEN** both settings exclude projects and `--exclude` names another one
- **THEN** only the project named by the option leaves the matrices, and the settings file is unchanged

#### Scenario: Nothing excluded
- **WHEN** `--exclude none` is given
- **THEN** no project is excluded and the source line says none, from the option

#### Scenario: Empty option
- **WHEN** `--exclude ","` is given with `--language en`
- **THEN** the exit code is 2, the output holds "--exclude: no project key", no export is read and no report is written

### Requirement: Exclusion source stated
The system SHALL print in the diagnosis and write in the Markdown report the source line of design D4, with the number of projects in force and its source (option, map setting or shared setting), whenever a list is in force, and SHALL add that source and that number to the JSON report. With no option, no map setting and an empty shared list, it SHALL write no such line. The line SHALL NOT name a project key.

Source: tests/dependencies_jira/test_exclusion_carte.py (to be written, task 3.1)

#### Scenario: Shared setting
- **WHEN** only the shared setting excludes two projects and `--language en` is given
- **THEN** the diagnosis and the report hold "Projects excluded from the map: 2 (source: setting excluded_projects, shared with the flow report)"

#### Scenario: Map setting in French
- **WHEN** the map's setting excludes one project
- **THEN** the report holds "Projets exclus de la carte : 1 (source : réglage dependency_excluded_projects)" and the JSON source is the map setting

#### Scenario: No exclusion
- **WHEN** no option, no map setting and an empty shared list are used
- **THEN** no source line is written and the JSON source says none

### Requirement: Dependency tool refused inside a Claude Code session
The system SHALL refuse `diagnose` and `compute` to start, with the exit code and the session key phrase of design D6, when the variable that Claude Code sets in its shells is present, before reading any setting (design D12). It SHALL NOT offer an option that bypasses that refusal.

Source: tests/dependencies_jira/test_lecteur_base.py (Refus: test_session_claude_code_refusee_code_3_avant_le_reste, test_session_variable_vide_refuse_aussi, test_main_refuse_avant_de_lire_les_reglages)

#### Scenario: Started from a session
- **WHEN** `diagnose` starts with the variable present
- **THEN** the output holds "Refused inside a Claude Code session", nothing is read and no report is written

## Open questions

1. Exact names of the report files and the graph/diagram output (Mermaid in the Markdown) are not asserted by tests.
2. The requirement "Project scope" names the word that disables the scope as "all", while the test passes the French word; whether the English word is also accepted is not asserted by a test.
