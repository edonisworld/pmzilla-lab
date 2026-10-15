# jira-flow-monthly-run Specification

## Purpose
The monthly flow follow-up in one command: `tools/flow_monthly.py`, run by the user alone in the Terminal, chains the export, the history collection, the import, the calculations, the comparisons and the dashboards for the series of the `monthly_run` block, stops at the first gap and writes a figures-only summary in the flow reports folder (work-queue job R-48).

## Requirements

### Requirement: Ordered monthly steps
The system SHALL provide a monthly-run orchestrator that runs, in the order of design D4 of the monthly-run change, the export, the history collection, the import, the flow calculation of each series, the dependency calculation of each series and configured map, the data comparison, the report comparison of each series, the dashboard and, last, the retention dry run of design D9 of this change (step `retention`). It SHALL pass to each tool the options of design D4 and its own output language. It SHALL NOT run the import's dry run, a database migration or backup, the history check, the segment sample, a ticket-key inspection, the field search, the team-field diagnose, the retention `check` or the retention `purge` with `--apply`, and it SHALL NOT start any Claude Code command.

Source: tests/flow_monthly/test_suivi_mensuel.py (OrdreEtOptions)

#### Scenario: Complete run
- **WHEN** every fake tool exits with 0 for a settings file with two series
- **THEN** the tools are called in the order of design D4, the flow, dependency and report-comparison steps run once per series, the retention tool is called once, after the dashboard, the output holds "Monthly run complete" in English or "Suivi mensuel terminé" in French, and the exit code is 0

#### Scenario: Excluded tools
- **WHEN** a complete run ends
- **THEN** no call to the segment sample, the history check, a migration, a backup, the retention check or an applied purge was recorded, and the last lines print the reading commands for Claude Code with the placeholder `<series>` and no real series name

### Requirement: Stop at the first gap
The system SHALL stop at the first step whose tool exits with a non-zero code, SHALL run no later step, and SHALL print the step identifier, the tool's exit code and the resume hint of design D12. A comparison step whose comparison tool reports a difference SHALL stop the run with exit code 4 and the parity-gap key phrase. Any other non-zero tool exit SHALL stop the run with exit code 1. The system SHALL NOT continue after a gap, SHALL NOT retry a step by itself, and SHALL NOT turn a gap into a warning.

Source: tests/flow_monthly/test_suivi_mensuel.py (ArretAuPremierEcart)

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
The system SHALL read only the flow settings file and the reports folder of the flow folder. It SHALL NOT open, list, test for existence or read the metadata of any path in the exports folder, the history folder or the tables folder, nor the team table or the sensitive-names list. It SHALL build the export paths from the configured query names and the run date and pass them to the tools without checking them. It SHALL NOT connect to the database, SHALL NOT import a database module and SHALL NOT read any Keychain entry.

Source: tests/flow_monthly/test_frontiere.py (Frontiere); tests/flow_monthly/test_suivi_mensuel.py (test_fichier_d_export_manquant_l_orchestrateur_ne_le_verifie_pas)

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
The system SHALL write in its own output lines and in its summary only step identifiers, series ordinals, counts, exit codes, durations and fixed labels. It SHALL NOT write a person, team, series, query or project name, a scope, a Jira key or a file name of the exports folder. By default it SHALL capture the tools' output, write none of it to any file, and print only the failing tool's error output when a step fails. With `--verbose` it SHALL first print the verbose-mode warning of design D12, then stream the tools' output.

Source: tests/flow_monthly/test_frontiere.py (Confidentialite); tests/flow_monthly/test_suivi_mensuel.py (SortieSilencieuseEtDetaillee)

#### Scenario: Distinctive names absent
- **WHEN** the settings fixture holds a distinctive string in every series name, query name and scope, and the run is quiet, a dry run, a failure or a refusal
- **THEN** none of these strings appears in the output or in the summary

#### Scenario: Verbose warning
- **WHEN** the run is started with `--verbose`
- **THEN** the verbose-mode warning is printed before the first step, and the summary still holds no tool output

### Requirement: Series declared in the flow settings
The system SHALL read the series from the `monthly_run` block of the flow settings file, with the structure of design D3, and the export query names from the existing export settings. The settings file SHALL be read with the strict loader of the flow configuration. Before any step, the system SHALL refuse with exit code 3 and the missing-prerequisite key phrase: a missing settings file, no export query, a missing block, an empty series list, a series without a name, two series with the same name, a series name ending with the database suffix of design D6, an unknown key, or an invalid dependency or dashboard value. The refusal SHALL name the key path and line, never a value.

Source: tests/flow_monthly/test_suivi_mensuel.py (Reglages, OrdreEtOptions)

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
The system SHALL, for each series, compute the database-source flow report under the series name followed by the database suffix of design D6, with the no-comparison option and without the ageing-points option, then compare the series' CSV report of the run date with that database report through the comparison tool. It SHALL NOT write an evolution report or an ageing-points file for the database series.

Source: tests/flow_monthly/test_suivi_mensuel.py

#### Scenario: Calls of the report comparison
- **WHEN** the report comparison runs for one series
- **THEN** the flow tool is called with the database source, the suffixed name and the no-comparison option and without the points option, and the comparison tool receives the CSV report and the database report of the run date

### Requirement: Resume, run date and dry run
The system SHALL accept `--from <step>` to run that step and the following ones, and `--date YYYY-MM-DD` to set the run date used for the export paths and report names. It SHALL refuse with exit code 2: an unknown step, an invalid date, a date in the future, and `--from export` with a date other than today. With `--dry-run` it SHALL run the checks done before the first step, print one dry-run line per call with the placeholders of design D8, call no tool, write no summary and exit with 0 or the code of the failed check. It SHALL keep no state file between runs.

Source: tests/flow_monthly/test_suivi_mensuel.py (Reprise, PassageABlanc)

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
The system SHALL write, at the end of every run that was not a dry run and was not refused before its first step, a summary file named after the run date in the reports folder of the flow folder, with owner-only permissions and the content of design D10 of the monthly-run change, extended with the step status `skipped` of design D19 of this change. A step before the `--from` step SHALL keep the status it had in a summary of the same run date, and SHALL be written `skipped` when no such summary records it; it SHALL NOT be written `not run`, which stays the status of steps after a stop. The final status SHALL be complete when every step that is not skipped passed, and "stopped at <step>" otherwise. Before the first step, the system SHALL refuse with exit code 5 and the already-done key phrase when a summary of the current calendar month has the final status complete, unless `--force` is given. `--from` SHALL NOT bypass that check.

Source: tests/flow_monthly/test_suivi_mensuel.py (Resume, MoisDejaFait); tests/flow_monthly/test_conservation_et_reprise.py (StatutSkipped)

#### Scenario: Summary after a stop
- **WHEN** a run stops at step history
- **THEN** the summary lists export as passed, history as failed with its exit code, the later steps as not run, and the final status "stopped at history"

#### Scenario: Resume without a prior summary
- **WHEN** a run starts with `--from compare-data`, no summary of that date exists, and every step from compare-data on passes
- **THEN** the summary lists the steps before compare-data as skipped, the others as passed, the final status complete, and the exit code is 0

#### Scenario: Resume after a stop
- **WHEN** a run stopped at import and the same date is resumed with `--from import`, which then passes to the end
- **THEN** export and history keep the status passed from the earlier summary, no step is skipped, and the final status is complete

#### Scenario: Month already complete
- **WHEN** a complete summary of the current month exists and the run starts without `--force`
- **THEN** no tool is called, the output holds "Monthly run already done this month", and the exit code is 5

#### Scenario: Force
- **WHEN** the same run starts with `--force`
- **THEN** the steps run

### Requirement: Exit codes, key phrases and language
The system SHALL use the exit codes 0 to 5 and the key phrases of design D12. It SHALL print in French by default and in English with `--language en`, keep step identifiers in English in both languages, and refuse any other language with exit code 2. It SHALL NOT mix the two languages in one run's output.

Source: tests/flow_monthly/test_frontiere.py (Langue)

#### Scenario: English run
- **WHEN** a complete run uses `--language en`
- **THEN** every orchestrator line uses the English key phrases, and every tool call carries the English language option

#### Scenario: Unknown language
- **WHEN** `--language de` is given
- **THEN** no tool is called and the exit code is 2

### Requirement: Refusal inside a Claude Code session
The system SHALL refuse to start, with exit code 3 and the key phrase of design D12, when its environment carries the variable that Claude Code sets in the shells it starts. The check SHALL happen before the settings are read and before any step. The system SHALL NOT offer an option that bypasses this refusal.

Source: tests/flow_monthly/test_frontiere.py (Frontiere, AideEnProcessusReel)

#### Scenario: Started from a session
- **WHEN** the variable is present in the environment
- **THEN** the output holds "Refused inside a Claude Code session", no file is read, no tool is called, and the exit code is 3

### Requirement: Completion line counts run and skipped steps
The system SHALL end a complete run with the completion key phrase of design D19, where the run count is the number of step calls made in this run, the total is the number of step calls of the full plan for the configured series (the retention step included, as one call), and the skipped count is the number of step calls before the `--from` step. The step progress lines SHALL number the calls of this run from one. The system SHALL NOT print a run count equal to the total when steps were skipped.

Source: tests/flow_monthly/test_conservation_et_reprise.py (LigneFinale)

#### Scenario: Full run
- **WHEN** a complete run of a plan of twelve calls ends
- **THEN** the output holds "Monthly run complete: 12 of 12 steps, 0 skipped"

#### Scenario: Resumed run
- **WHEN** a run of the same plan (two series) starts with `--from compare-data` and the last five calls pass
- **THEN** the output holds "Monthly run complete: 5 of 12 steps, 7 skipped"

### Requirement: Import step marks tickets out of the export
The system SHALL call the import step with the out-of-export mark option of the jira-flow-import capability and with the export file of every named query of the run date. The system SHALL NOT pass that option to an import of a subset of the queries.

Source: tests/flow_monthly/test_conservation_et_reprise.py (MarquageDeLImport)

#### Scenario: Import call
- **WHEN** the import step runs for two named queries
- **THEN** the import tool receives the mark option and both export paths of the run date

### Requirement: Retention dry run as the last step
The system SHALL run, after the dashboard, a `retention` step that calls the retention tool's `purge` subcommand without `--apply`, with the run's output language. When the tool exits with 0, the system SHALL capture the tool's output without printing it, as for every step, and print only the monthly-run retention line of design D19 with the total read from the tool's check total line in the run's language, mark the step passed, and write that retention line in the summary file. Out-of-rule counts SHALL be reported and SHALL NOT stop the run or change its exit code. A non-zero exit of the tool, or an output without the check total line, SHALL mark the step failed like any step: the run stops at `retention` with exit code 1 and the resume hint, and the summary's final status is "stopped at retention". The system SHALL NOT pass `--apply`, SHALL NOT call the retention `check`, SHALL NOT create a labelled backup, SHALL NOT open a store itself, and SHALL NOT write the retention line with a guessed count. The real purge stays a separate command run by the user alone after the labelled backup of the day.

Source: tests/flow_monthly/test_conservation_et_reprise.py (EtapeRetention)

#### Scenario: Items out of rule reported
- **WHEN** the fake retention tool prints "retention check: 7 items out of rule" and "dry run: nothing deleted" and exits with 0
- **THEN** the output holds "retention dry run: 7 items out of rule", the summary file holds the same line, the step is passed, the final status is complete, and the exit code is 0

#### Scenario: Nothing out of rule
- **WHEN** the fake retention tool prints "retention check: nothing out of rule" and exits with 0
- **THEN** the output and the summary hold "retention dry run: 0 items out of rule"

#### Scenario: Retention tool error
- **WHEN** the fake retention tool exits with 1
- **THEN** the output holds "Stopped at step retention: exit code 1" and "--from retention", the summary lists the earlier steps as passed and retention as failed, the final status is "stopped at retention", and the exit code is 1

#### Scenario: Call recorded
- **WHEN** a complete run ends
- **THEN** the retention tool was called once with `purge`, without `--apply`, and with the run's language option

#### Scenario: French run
- **WHEN** a complete run uses the default French output and the fake tool prints "contrôle de conservation : 2 éléments hors règle"
- **THEN** the output and the summary hold "essai de purge : 2 éléments hors règle"
