# jira-flow-export Specification

## Purpose

Describes the command-line tool that exports tickets from the Jira API into a CSV file in the same layout as a manual Jira export, so that the flow and dependency reports read it unchanged. The tool never asks Jira for titles, descriptions or individual data. Sources are the tests in `tests/export_jira_api/`.

## Requirements

### Requirement: Subcommands and retired subcommands
The system SHALL offer the subcommands `diagnose`, `fields` and `export`, and SHALL refuse the retired subcommands `compare` and `teams-table` (and the former French subcommand names) with exit code 2, without a traceback, without calling Jira, and with a message that points to the replacement path.

Source: tests/export_jira_api/test_export_jira_api.py (SousCommandesRetirees, AnciensNoms)

#### Scenario: Retired subcommand
- **WHEN** the user runs `compare` or `teams-table`
- **THEN** the exit code is 2, the message says the subcommand is retired and names the replacement (the export subcommand and the comparison tool, or the hand-written team table), and no request reaches Jira

#### Scenario: Help
- **WHEN** the user asks for help
- **THEN** only `diagnose`, `fields` and `export` are listed

#### Scenario: Former option and setting names
- **WHEN** a former option name (for example the French search or output option) or a former setting name is used
- **THEN** it is accepted with a warning naming the new name, while former subcommand names are refused with exit code 2

### Requirement: CSV layout identical to a manual Jira export
The system SHALL write a UTF-8 CSV with the columns issue key, issue type, status, status category, created, resolved, resolution, status-category-changed, parent key, updated, then optional points and team columns, then one column per distinct link type and direction, repeated as many times as the largest number of links of that kind on one ticket. Dates SHALL be written as day/abbreviated-month/year hour:minute.

Source: tests/export_jira_api/test_export_jira_api.py (Export, ColonneUpdated, FormatDate)

#### Scenario: Repeated columns
- **WHEN** one ticket has two outgoing blocking links and two teams
- **THEN** the header has two outgoing-blocks columns and two team columns, and the ticket row fills them in order

#### Scenario: Unreadable or missing date
- **WHEN** a date is missing or not a valid date
- **THEN** the cell is empty

### Requirement: Dates in a configurable time zone
The system SHALL convert every exported date to a configurable time zone, with a default zone applying daylight saving, and SHALL stop before any call to Jira when the configured zone is invalid.

Source: tests/export_jira_api/test_export_jira_api.py (FuseauExport)

#### Scenario: Default zone
- **WHEN** a summer UTC timestamp is exported without a zone setting
- **THEN** it is written with the summer offset of the default zone; a winter timestamp with the winter offset

#### Scenario: Invalid zone
- **WHEN** the zone setting is unknown
- **THEN** the exit code is 1, the message names the setting, no file is written and Jira is not called

### Requirement: Updated column
The system SHALL always request and write the updated date, placed immediately after the parent key, in the export time zone, and empty when Jira returns none.

Source: tests/export_jira_api/test_export_jira_api.py (ColonneUpdated)

#### Scenario: Updated written
- **WHEN** a ticket has an updated date
- **THEN** the header shows parent key, updated, then the next column, and the value follows the configured zone

### Requirement: Complete pagination
The system SHALL follow the page token of the search API until the last page, and SHALL stop (not loop) when the API returns the same token repeatedly.

Source: tests/export_jira_api/test_export_jira_api.py (test_pagination_complete, test_jeton_de_page_qui_se_repete_ne_boucle_pas)

#### Scenario: One ticket per page
- **WHEN** the API pages one ticket at a time
- **THEN** all tickets are exported and the next-page token of each request is the one returned by the previous response

#### Scenario: Repeated token
- **WHEN** the API keeps returning the same page token
- **THEN** the export ends successfully after the second request

### Requirement: No sensitive field requested or printed
The system SHALL NOT request titles, assignee, reporter, creator or description from Jira, SHALL write no title to the file, SHALL NOT print the token, the site address, ticket keys, team labels or the query to the console, and SHALL create the output file readable only by its owner. The console SHALL report the ticket and page counts.

Source: tests/export_jira_api/test_export_jira_api.py (test_aucun_titre_demande_a_jira_et_rien_de_sensible_en_sortie)

#### Scenario: Console and file content
- **WHEN** an export succeeds
- **THEN** the requested field list contains none of the forbidden fields, neither output nor file contains the secret title or the token, and the file permissions are owner read/write only

### Requirement: Access errors show only the status code
The system SHALL, when Jira rejects the request, print only the HTTP status code and exit with code 1.

Source: tests/export_jira_api/test_export_jira_api.py (Export, Champs: test_erreur_d_acces_ne_montre_que_le_code)

#### Scenario: Unauthorized
- **WHEN** the credentials are refused
- **THEN** the output is the status code alone and the exit code is 1

### Requirement: Named export queries
The system SHALL read the export queries from the settings either as one query or as a mapping of names to queries; the mapping SHALL take precedence. Without `--query`, the system SHALL run every named query and write one file per query in the exports folder named after the query and the day. With `--query <name>`, it SHALL run only that query. The explicit output option SHALL be refused when several queries would run. Invalid names, empty queries or a non-mapping value SHALL stop with exit code 1 before calling Jira.

Source: tests/export_jira_api/test_export_jira_api.py (RequetesNommees)

#### Scenario: All queries
- **WHEN** two named queries are configured and export runs without options
- **THEN** two files are written with identical format, time zone and team handling, and the console lines are prefixed with the query name

#### Scenario: Unknown query name
- **WHEN** the requested name is not configured
- **THEN** the exit code is 1, the available names are listed, and Jira is not called

#### Scenario: No query configured
- **WHEN** no query is configured
- **THEN** export stops with exit code 1 and names the missing setting, without calling Jira

#### Scenario: Diagnose uses the first query
- **WHEN** `diagnose` runs with several named queries
- **THEN** only the first query is sent

### Requirement: Team field as labels
The system SHALL read the team field when it is configured and write up to as many team columns as the maximum number of teams on one ticket. When no team field is configured, it SHALL write no team column and SHALL NOT request the field. The header text of the team columns SHALL be configurable.

Source: tests/export_jira_api/test_export_jira_api.py (Export, ChampEquipeIllisible)

#### Scenario: No team field
- **WHEN** no team field is set
- **THEN** the header has no team column

#### Scenario: Identifier alone is not a label
- **WHEN** a field value is a bare number, a UUID, or an object holding only a numeric value
- **THEN** it is not accepted as a label, whereas values with a value or name property, or plain strings, are

### Requirement: Team table for asset-object team fields
The system SHALL, when the team field returns asset objects instead of labels, translate identifiers to labels through a hand-written team table file (identifier to label mapping, other keys ignored). Unknown identifiers SHALL be written as an "unknown team" marker in the CSV regardless of the language, and the console SHALL report the number of distinct unknown identifiers, the number of tickets affected, and the list of identifiers only (no labels, no keys). When no table exists the export SHALL stop with exit code 1, write no file, and explain how to create the table by hand, naming the shape of the object (never values). An unreadable table SHALL stop the export.

Source: tests/export_jira_api/test_export_jira_api.py (TableEquipes, ChampEquipeIllisible)

#### Scenario: Partly unknown table
- **WHEN** some identifiers are missing from the table
- **THEN** their cells hold the unknown marker, the original API order of teams is kept, and the console lists the missing identifiers

#### Scenario: Complete table
- **WHEN** every identifier is in the table
- **THEN** no completion message is printed

#### Scenario: No table
- **WHEN** the team field is asset objects and the table does not exist
- **THEN** the exit code is 1, the output file is not created, and the message gives the shape but none of the values

#### Scenario: Permission rules
- **WHEN** the project permission settings are read
- **THEN** reading the team table file and calling the retired subcommands are denied to the assistant

### Requirement: Optional verification column
The system SHALL, when a verification field identifier is configured, write one extra column placed right after the team columns (header configurable), converting choice lists, single choices, checkboxes (as true) and multiple choices (values joined by a semicolon), and writing empty for unknown shapes. The console SHALL report only how many tickets are filled out of the total. Without the setting, no column is written and the field is not requested. An invalid identifier SHALL stop before any Jira call.

Source: tests/export_jira_api/test_export_jira_api.py (ChampVerification)

#### Scenario: Column present
- **WHEN** the setting is present
- **THEN** the column follows the team columns and the console prints the filled count without values or keys

#### Scenario: Invalid identifier
- **WHEN** the identifier contains spaces
- **THEN** the exit code is non-zero, the message names the setting, and Jira is not called

### Requirement: Optional story points column
The system SHALL, when a points field identifier or list of identifiers is configured, write a "story points" column after the updated column and before the team columns, taking the first non-empty numeric value in list order; non-numeric values and booleans SHALL be written empty. A duplicate identifier SHALL be requested once. The console SHALL report per field how many tickets are filled and how many tickets have another points field filled with a different value, plus the count of non-numeric values, never the values themselves. An invalid identifier SHALL stop before calling Jira.

Source: tests/export_jira_api/test_export_jira_api.py (ChampPoints, ListeDeChampsPoints)

#### Scenario: Several fields
- **WHEN** two fields hold different values on one ticket
- **THEN** the first field in the configured order wins, and the console counts the disagreement

#### Scenario: No setting
- **WHEN** nothing is configured
- **THEN** there is no points column and the field is not requested

#### Scenario: Setting as text or list
- **WHEN** the setting is a single identifier, a list, empty, or absent
- **THEN** it is read as a one-element list, a list, and two empty lists respectively

### Requirement: Field search
The system SHALL provide a `fields --search <text>` subcommand that lists, case-insensitively, only the identifier and name of the Jira fields whose name contains the text, together with the match count over the total count, and SHALL NOT read any ticket. The text SHALL be mandatory and non-blank, and the subcommand SHALL work without an export query.

Source: tests/export_jira_api/test_export_jira_api.py (Champs)

#### Scenario: Search
- **WHEN** the user searches for a text present in two field names
- **THEN** exactly those two identifier and name lines are printed, with no schema or other metadata, and no ticket request is made

#### Scenario: Blank text
- **WHEN** the text is blank
- **THEN** the exit code is 1 and Jira is not called

### Requirement: Diagnose subcommand
The system SHALL provide a `diagnose` subcommand that reads a single page of tickets requesting only the team field and reports, without any value, whether team labels are usable and the shape of the field (for example a list of objects with a value, or asset objects with their count). It SHALL exit 1 when labels are not usable and no team table exists, or when the field is absent from responses, and exit 0 when labels are usable or a table exists (reporting the number of identifiers in the table).

Source: tests/export_jira_api/test_export_jira_api.py (Diagnostic, TableEquipes, ChampEquipeIllisible)

#### Scenario: Usable labels
- **WHEN** the team field returns labels
- **THEN** the report says labels are usable, one single request is made and no label appears in the output

#### Scenario: Field absent
- **WHEN** the configured field never appears in responses
- **THEN** the exit code is 1 and the message says it is absent from responses

### Requirement: CSV compatible with the report tools
The system SHALL produce a CSV that the flow report and the dependency report read without modification and with the same result as an equivalent manual export, including repeated team columns and link columns.

Source: tests/export_jira_api/test_export_jira_api.py (LecturePar)

#### Scenario: Same report
- **WHEN** the flow report is computed on the API CSV and on the equivalent manual CSV
- **THEN** both reports are identical apart from name and column list

### Requirement: Message language
The system SHALL print its messages in French by default and in English with `--language en`, SHALL reject other languages with exit code 2, SHALL NOT keep the language between runs, and SHALL accept the former option name with a warning. English output SHALL contain no French words except the unknown-team marker written in the CSV.

Source: tests/export_jira_api/test_language.py

#### Scenario: English run
- **WHEN** `--language en` is given
- **THEN** the output matches the recorded English reference and contains no French text

#### Scenario: Unknown language
- **WHEN** `--language de` is given
- **THEN** the exit code is 2
