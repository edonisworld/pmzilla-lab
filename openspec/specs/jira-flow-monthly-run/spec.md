# jira-flow-monthly-run Specification

## Purpose
The monthly flow follow-up in one command: `tools/flow_monthly.py`, run by the user alone in the Terminal, chains the export, the history collection, the import, the calculations, the comparisons and the dashboards for the series of the `monthly_run` block, stops at the first gap and writes a figures-only summary in the flow reports folder (work-queue job R-48).
## Requirements
### Requirement: Ordered monthly steps
The system SHALL provide a monthly-run orchestrator that runs, in the order of design D4, the export, the history collection, the import, the flow calculation of each series, the dependency calculation of each series and configured map, the data comparison, the report comparison of each series and the dashboard. It SHALL pass to each tool the options of design D4 and its own output language. It SHALL NOT run the import's dry run, a database migration or backup, the history check, the segment sample, a ticket-key inspection, the field search or the team-field diagnose, and it SHALL NOT start any Claude Code command. Untested until implemented.

#### Scenario: Complete run
- **WHEN** every fake tool exits with 0 for a settings file with two series
- **THEN** the tools are called in the order of design D4, the flow, dependency and report-comparison steps run once per series, the output ends with "Monthly run complete" in English or "Suivi mensuel terminé" in French, and the exit code is 0

#### Scenario: Excluded tools
- **WHEN** a complete run ends
- **THEN** no call to the segment sample, the history check, a migration or a backup was recorded, and the last lines print the reading commands for Claude Code with the placeholder `<series>` and no real series name

### Requirement: Stop at the first gap
The system SHALL stop at the first step whose tool exits with a non-zero code, SHALL run no later step, and SHALL print the step identifier, the tool's exit code and the resume hint of design D12. A comparison step whose comparison tool reports a difference SHALL stop the run with exit code 4 and the parity-gap key phrase. Any other non-zero tool exit SHALL stop the run with exit code 1. The system SHALL NOT continue after a gap, SHALL NOT retry a step by itself, and SHALL NOT turn a gap into a warning. Untested until implemented.

#### Scenario: Failing import
- **WHEN** the import tool exits with 1
- **THEN** the output holds "Stopped at step import: exit code 1" and "--from import", no calculation, comparison or dashboard tool is called, and the exit code is 1

#### Scenario: Parity gap
- **WHEN** the data comparison tool exits with 1
- **THEN** the output holds "Database and CSV differ at step compare-data", the report comparison and the dashboard are not run, and the exit code is 4

#### Scenario: Unreadable comparison input
- **WHEN** the comparison tool exits with 2
- **THEN** the run stops at that step with exit code 1, not 4

### Requirement: The orchestrator never opens the data
The system SHALL read only the flow settings file and the reports folder of the flow folder. It SHALL NOT open, list, test for existence or read the metadata of any path in the exports folder, the history folder or the tables folder, nor the team table or the sensitive-names list. It SHALL build the export paths from the configured query names and the run date and pass them to the tools without checking them. It SHALL NOT connect to the database, SHALL NOT import a database module and SHALL NOT read any Keychain entry. Untested until implemented.

#### Scenario: Recorded file accesses
- **WHEN** a complete run executes under an audit hook in a workspace whose forbidden folders and files hold sentinel files
- **THEN** every recorded open, listing or inspection targets the settings file, the reports folder or a file inside it, and none targets a forbidden path

#### Scenario: No database module
- **WHEN** the orchestrator's imports are checked
- **THEN** no database driver or database helper module is imported

#### Scenario: Missing export file
- **WHEN** the history step runs and the export file it was given does not exist
- **THEN** the orchestrator has not checked the file itself, the fake history tool's non-zero exit stops the run at step history, and the exit code is 1

### Requirement: Output and summary without names or keys
The system SHALL write in its own output lines and in its summary only step identifiers, series ordinals, counts, exit codes, durations and fixed labels. It SHALL NOT write a person, team, series, query or project name, a scope, a Jira key or a file name of the exports folder. By default it SHALL capture the tools' output, write none of it to any file, and print only the failing tool's error output when a step fails. With `--verbose` it SHALL first print the verbose-mode warning of design D12, then stream the tools' output. Untested until implemented.

#### Scenario: Distinctive names absent
- **WHEN** the settings fixture holds a distinctive string in every series name, query name and scope, and the run is quiet, a dry run, a failure or a refusal
- **THEN** none of these strings appears in the output or in the summary

#### Scenario: Verbose warning
- **WHEN** the run is started with `--verbose`
- **THEN** the verbose-mode warning is printed before the first step, and the summary still holds no tool output

### Requirement: Series declared in the flow settings
The system SHALL read the series from the `monthly_run` block of the flow settings file, with the structure of design D3, and the export query names from the existing export settings. The settings file SHALL be read with the strict loader of the flow configuration. Before any step, the system SHALL refuse with exit code 3 and the missing-prerequisite key phrase: a missing settings file, no export query, a missing block, an empty series list, a series without a name, two series with the same name, a series name ending with the database suffix of design D6, an unknown key, or an invalid dependency or dashboard value. The refusal SHALL name the key path and line, never a value. Untested until implemented.

#### Scenario: Unknown key
- **WHEN** the block holds an unknown key
- **THEN** the output names the key path and its line with "Missing prerequisite", shows no value, no tool is called, and the exit code is 3

#### Scenario: Scope absent
- **WHEN** a series has no scope
- **THEN** its flow and dependency calls carry no scope option

#### Scenario: Dependency maps
- **WHEN** a series asks for both dependency maps
- **THEN** the dependency tool is called once per team and once with the project view for that series

### Requirement: Comparison through a database series
The system SHALL, for each series, compute the database-source flow report under the series name followed by the database suffix of design D6, with the no-comparison option and without the ageing-points option, then compare the series' CSV report of the run date with that database report through the comparison tool. It SHALL NOT write an evolution report or an ageing-points file for the database series. Untested until implemented.

#### Scenario: Calls of the report comparison
- **WHEN** the report comparison runs for one series
- **THEN** the flow tool is called with the database source, the suffixed name and the no-comparison option and without the points option, and the comparison tool receives the CSV report and the database report of the run date

### Requirement: Resume, run date and dry run
The system SHALL accept `--from <step>` to run that step and the following ones, and `--date YYYY-MM-DD` to set the run date used for the export paths and report names. It SHALL refuse with exit code 2: an unknown step, an invalid date, a date in the future, and `--from export` with a date other than today. With `--dry-run` it SHALL run the checks done before the first step, print one dry-run line per call with the placeholders of design D8, call no tool, write no summary and exit with 0 or the code of the failed check. It SHALL keep no state file between runs. Untested until implemented.

#### Scenario: Resume
- **WHEN** the run is started with `--from compare-data`
- **THEN** no export, history, import, flow or dependency tool is called, and the comparison receives the export paths of the run date

#### Scenario: Export on another date
- **WHEN** `--from export` is combined with yesterday's date
- **THEN** no tool is called and the exit code is 2

#### Scenario: Dry run
- **WHEN** the run is started with `--dry-run`
- **THEN** every printed line begins with "dry run: would run" in English or "essai : lancerait" in French, values are replaced by placeholders such as `<series 1>`, no tool is called, no summary file exists, and the exit code is 0

### Requirement: Summary file and month already done
The system SHALL write, at the end of every run that was not a dry run and was not refused before its first step, a summary file named after the run date in the reports folder of the flow folder, with owner-only permissions and the content of design D10. A resumed run on the same run date SHALL rewrite it, keeping the steps that passed before. Before the first step, the system SHALL refuse with exit code 5 and the already-done key phrase when a summary of the current calendar month has the final status complete, unless `--force` is given. `--from` SHALL NOT bypass that check. Untested until implemented.

#### Scenario: Summary after a stop
- **WHEN** a run stops at step history
- **THEN** the summary lists export as passed, history as failed with its exit code, the later steps as not run, and the final status "stopped at history"

#### Scenario: Month already complete
- **WHEN** a complete summary of the current month exists and the run starts without `--force`
- **THEN** no tool is called, the output holds "Monthly run already done this month", and the exit code is 5

#### Scenario: Force
- **WHEN** the same run starts with `--force`
- **THEN** the steps run

### Requirement: Exit codes, key phrases and language
The system SHALL use the exit codes 0 to 5 and the key phrases of design D12. It SHALL print in French by default and in English with `--language en`, keep step identifiers in English in both languages, and refuse any other language with exit code 2. It SHALL NOT mix the two languages in one run's output. Untested until implemented.

#### Scenario: English run
- **WHEN** a complete run uses `--language en`
- **THEN** every orchestrator line uses the English key phrases, and every tool call carries the English language option

#### Scenario: Unknown language
- **WHEN** `--language de` is given
- **THEN** no tool is called and the exit code is 2

### Requirement: Refusal inside a Claude Code session
The system SHALL refuse to start, with exit code 3 and the key phrase of design D12, when its environment carries the variable that Claude Code sets in the shells it starts. The check SHALL happen before the settings are read and before any step. The system SHALL NOT offer an option that bypasses this refusal. Untested until implemented.

#### Scenario: Started from a session
- **WHEN** the variable is present in the environment
- **THEN** the output holds "Refused inside a Claude Code session", no file is read, no tool is called, and the exit code is 3

