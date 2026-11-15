# jira-flow-monthly-run Specification

## Purpose
The monthly flow follow-up in one command: `tools/flow_monthly.py`, run by the user alone in the Terminal, chains the export, the history collection, the import, the calculations, the comparisons and the dashboards for the series of the `monthly_run` block, stops at the first gap and writes a figures-only summary in the flow reports folder (work-queue job R-48).

## Requirements

### Requirement: Ordered monthly steps
The system SHALL provide a monthly-run orchestrator that runs, in the order of design D8 of the database-only change without its dashboard step, the export, the import, the history collection, the flow calculation of each series, the dependency calculation of each series and configured map and, last, the retention dry run (step `retention`). It SHALL NOT run a dashboard step and SHALL NOT call the retired flow dashboard tool.

#### Scenario: Complete run
- **WHEN** every fake tool exits with 0 for a settings file with two series
- **THEN** the tools are called in that order, the flow and dependency steps run once per series, the comparison tool and the flow dashboard tool are never called, the retention tool is called once, after the last dependency step, the output holds "Monthly run complete" in English or "Suivi mensuel terminé" in French, and the exit code is 0

Source: design D2 of change remove-flow-board (dashboard step removed); tests/flow_monthly/test_suivi_mensuel.py (OrdreEtOptions)

### Requirement: Options passed to each monthly step
The system SHALL pass to each tool the options of design D8 and its own output language, and SHALL pass no export path, no `--source` option and, to the flow calculation, no points option (design D2 of change remove-flow-board).

Source: tests/flow_monthly/test_suivi_mensuel.py (OrdreEtOptions); tests/flow_monthly/test_frontiere.py (AucunCheminDeFichier)

#### Scenario: Options of a complete run
- **WHEN** a complete run ends
- **THEN** every tool call carries the run's language option, no call carries an export path or a `--source` option, and no flow calculation call carries the points option

### Requirement: Steps the monthly run never runs
The system SHALL NOT run a comparison step, the import's dry run, a database migration or backup, the history check, the segment sample, a ticket-key inspection, the field search, the team-field diagnose, the retention `check` or the retention `purge` with `--apply`, and it SHALL NOT start any Claude Code command.

Source: tests/flow_monthly/test_suivi_mensuel.py (OrdreEtOptions)

#### Scenario: Excluded tools
- **WHEN** a complete run ends
- **THEN** no call to the comparison tool, the segment sample, the history check, a migration, a backup, the retention check or an applied purge was recorded, no call carries an export path, and the last lines print the reading commands for Claude Code with the placeholder `<series>` and no real series name

### Requirement: A gap is never softened
The system SHALL NOT return exit code 4, SHALL NOT continue after a gap, SHALL NOT retry a step by itself, and SHALL NOT turn a gap into a warning.

Source: tests/flow_monthly/test_reprise_serie.py (CodesRetires)

#### Scenario: Parity gap
- **WHEN** any run of the new plan ends or stops
- **THEN** the output never holds the parity-gap phrase and the exit code is never 4

### Requirement: The orchestrator never opens the data
The system SHALL read only the flow settings file and the reports folder of the flow folder. It SHALL NOT open, list, test for existence or read the metadata of any path in the exports folder, the history folder or the tables folder, nor the team table or the sensitive-names list. It SHALL build no export path.

Source: tests/flow_monthly/test_frontiere.py (Frontiere, AucunCheminDeFichier)

#### Scenario: Recorded file accesses
- **WHEN** a complete run executes under an audit hook in a workspace whose forbidden folders and files hold sentinel files
- **THEN** every recorded open, listing or inspection targets the settings file, the reports folder or a file inside it, and none targets a forbidden path

#### Scenario: Missing export file
- **WHEN** the export step's fake tool exits with 1
- **THEN** the orchestrator has checked no file itself, the run stops at step export, and the exit code is 1

### Requirement: The orchestrator never opens the database
The system SHALL NOT connect to the database, SHALL NOT import a database module and SHALL NOT read any Keychain entry.

Source: tests/flow_monthly/test_frontiere.py (Frontiere)

#### Scenario: No database module
- **WHEN** the orchestrator's imports are checked
- **THEN** no database driver or database helper module is imported

### Requirement: Output and summary without names or keys
The system SHALL write in its own output lines and in its summary only step identifiers, series ordinals, counts, exit codes, durations and fixed labels. It SHALL NOT write a person, team, series, query or project name, a scope, a Jira key or a file name of the exports folder.

Source: tests/flow_monthly/test_frontiere.py (Confidentialite)

#### Scenario: Distinctive names absent
- **WHEN** the settings fixture holds a distinctive string in every series name, query name and scope, and the run is quiet, a dry run, a failure or a refusal
- **THEN** none of these strings appears in the output or in the summary

### Requirement: Tool output captured unless verbose
By default the system SHALL capture the tools' output, write none of it to any file, and print only the failing tool's error output when a step fails. With `--verbose` it SHALL first print the verbose-mode warning of design D12, then stream the tools' output.

Source: tests/flow_monthly/test_suivi_mensuel.py (SortieSilencieuseEtDetaillee)

#### Scenario: Verbose warning
- **WHEN** the run is started with `--verbose`
- **THEN** the verbose-mode warning is printed before the first step, and the summary still holds no tool output

### Requirement: Series declared in the flow settings
The system SHALL read the series from the `monthly_run` block of the flow settings file, with the structure of design D3, and the export query names from the existing export settings. The settings file SHALL be read with the strict loader of the flow configuration.

Source: tests/flow_monthly/test_suivi_mensuel.py (Reglages, OrdreEtOptions)

#### Scenario: Scope absent
- **WHEN** a series has no scope
- **THEN** its flow and dependency calls carry no scope option

#### Scenario: Dependency maps
- **WHEN** a series asks for both dependency maps
- **THEN** the dependency tool is called once per team and once with the project view for that series

### Requirement: Refusal of invalid monthly settings
Before any step, the system SHALL refuse with exit code 3 and the missing-prerequisite key phrase: a missing settings file, no export query, a missing block, an empty series list, a series without a name, two series with the same name, a series name ending with the database suffix of design D6, an unknown key (the retired `dashboard` key of the block included), or an invalid dependency value. The refusal SHALL name the key path and line, never a value.

#### Scenario: Unknown key
- **WHEN** the block holds an unknown key
- **THEN** the output names the key path and its line with "Missing prerequisite", shows no value, no tool is called, and the exit code is 3

#### Scenario: Retired dashboard key
- **WHEN** the block still holds the `dashboard` key
- **THEN** the output names `monthly_run.dashboard` and its line with "Missing prerequisite", shows no value, no tool is called, and the exit code is 3

Source: design D2 of change remove-flow-board (retired `dashboard` key); tests/flow_monthly/test_suivi_mensuel.py (Reglages)

### Requirement: Resume, run date and dry run
The system SHALL accept `--from <step>` to run that step and the following ones, and `--date YYYY-MM-DD` to set the run date used for the report names and the summary. Without `--date`, the run date SHALL be today for a run without `--from` or with `--from export`, and the series date of design D1 of the flow-monthly-resume change for any other `--from` step.

Source: tests/flow_monthly/test_suivi_mensuel.py (Reprise); tests/flow_monthly/test_reprise_serie.py

#### Scenario: Resume
- **WHEN** the run is started with `--from flow`
- **THEN** no export, import or history tool is called, and the flow tool receives no export path

### Requirement: No state file and no default to today for a resume
The system SHALL keep no state file between runs. It SHALL NOT take today as the run date of a resume after `export` when no summary designates today.

Source: tests/flow_monthly/test_reprise_serie.py

#### Scenario: Resume without a summary of today
- **WHEN** the run starts today with `--from import` and no `--date`, and only a summary of an earlier day of the month records export passed
- **THEN** the run date is that earlier day, not today

### Requirement: Refusal of an invalid step or date
The system SHALL refuse with exit code 2: an unknown step (the retired `compare-data`, `compare-reports` and `dashboard` included), an invalid date, a date in the future, and `--from export` with a date other than today.

Source: tests/flow_monthly/test_suivi_mensuel.py (Reprise)

#### Scenario: Retired step
- **WHEN** the run is started with `--from compare-data`
- **THEN** no tool is called and the exit code is 2

#### Scenario: Retired dashboard step
- **WHEN** the run is started with `--from dashboard`
- **THEN** no tool is called, no summary is written, and the exit code is 2

#### Scenario: Export on another date
- **WHEN** `--from export` is combined with yesterday's date
- **THEN** no tool is called and the exit code is 2

### Requirement: Dry run of the monthly run
With `--dry-run` the system SHALL run the checks done before the first step, print the series-date line of design D1 of the flow-monthly-resume change when a series date was decided, then one dry-run line per call with the placeholders of design D8 of the monthly-run change, call no tool, write no summary and exit with 0 or the code of the failed check.

Source: tests/flow_monthly/test_suivi_mensuel.py (PassageABlanc); tests/flow_monthly/test_reprise_serie.py

#### Scenario: Dry run
- **WHEN** the run is started with `--dry-run` and without `--from`
- **THEN** every printed line begins with "dry run: would run" in English or "essai : lancerait" in French, values are replaced by placeholders such as `<series 1>`, no tool is called, no summary file exists, and the exit code is 0

#### Scenario: Dry run of a resume
- **WHEN** the run is started with `--dry-run --from flow` and the series date is decided
- **THEN** the first line is the series-date line, every other line begins with the dry-run phrase, and no tool is called

### Requirement: Summary file and month already done
The system SHALL write, at the end of every run that was not a dry run and was not refused before its first step, a summary file named after the run date in the reports folder of the flow folder, with owner-only permissions and the content of design D10 of the monthly-run change, extended with the step status `skipped`.

Source: tests/flow_monthly/test_suivi_mensuel.py (Resume)

#### Scenario: Summary of a complete run
- **WHEN** a complete run ends
- **THEN** a summary file named after the run date exists in the reports folder of the flow folder, with owner-only permissions

### Requirement: Final status of the summary
The final status of the summary SHALL be complete when every step that is not skipped passed, and "stopped at <step>" otherwise.

Source: tests/flow_monthly/test_suivi_mensuel.py (Resume); tests/flow_monthly/test_conservation_et_reprise.py (StatutSkipped)

#### Scenario: Summary after a stop
- **WHEN** a run stops at step history
- **THEN** the summary lists export and import as passed, history as failed with its exit code, the later steps as not run, and the final status "stopped at history"

### Requirement: Status of the steps before the resume step
A step before the `--from` step SHALL keep the status it had in a summary of the same run date, and SHALL be written `skipped` when no such summary records it; it SHALL NOT be written `not run`, which stays the status of steps after a stop. A step of an earlier summary that is not in the current plan SHALL be ignored.

Source: tests/flow_monthly/test_conservation_et_reprise.py (StatutSkipped)

#### Scenario: Resume without a prior summary
- **WHEN** a run starts with `--from flow`, no summary of that date exists, and every step from flow on passes
- **THEN** the summary lists the steps before flow as skipped, the others as passed, the final status complete, and the exit code is 0

#### Scenario: Resume after a stop
- **WHEN** a run stopped at import and the same date is resumed with `--from import`, which then passes to the end
- **THEN** export keeps the status passed from the earlier summary, no step is skipped, and the final status is complete

#### Scenario: Earlier summary with retired steps
- **WHEN** a summary of the same date lists `compare-data` and `dashboard` and the run resumes with `--from retention`
- **THEN** the retired steps are ignored and the new summary lists neither

### Requirement: Month already done
Before the first step, the system SHALL refuse with exit code 5 and the already-done key phrase when a summary of the current calendar month has the final status complete, unless `--force` is given. `--from` SHALL NOT bypass that check.

Source: tests/flow_monthly/test_suivi_mensuel.py (MoisDejaFait)

#### Scenario: Month already complete
- **WHEN** a complete summary of the current month exists and the run starts without `--force`
- **THEN** no tool is called, the output holds "Monthly run already done this month", and the exit code is 5

#### Scenario: Force
- **WHEN** the same run starts with `--force`
- **THEN** the steps run

### Requirement: Exit codes, key phrases and language
The system SHALL use the exit codes 0, 1, 2, 3 and 5 and the key phrases of design D12 of the monthly-run change, without the parity-gap phrase, and the key phrases of design D7 of the flow-monthly-resume change, without the missing-input phrases. Exit codes 4 (parity gap) and 6 (missing input) are retired with the CSV route and SHALL NOT be reused.

Source: tests/flow_monthly/test_suivi_mensuel.py (ArretAuPremierEcart)

#### Scenario: Retired exit codes
- **WHEN** a step fails
- **THEN** the exit code is 1, never 4 or 6

### Requirement: Output language of the monthly run
The system SHALL print in French by default and in English with `--language en`, keep step identifiers in English in both languages, and refuse any other language with exit code 2. It SHALL NOT mix the two languages in one run's output.

Source: tests/flow_monthly/test_frontiere.py (Langue)

#### Scenario: English run
- **WHEN** a complete run uses `--language en`
- **THEN** every orchestrator line uses the English key phrases, and every tool call carries the English language option

#### Scenario: Unknown language
- **WHEN** `--language de` is given
- **THEN** no tool is called and the exit code is 2

#### Scenario: French refusal of an ambiguous series
- **WHEN** the series date is ambiguous and the run uses the default language
- **THEN** the output holds "Série en cours ambiguë" and no English key phrase

### Requirement: Refusal inside a Claude Code session
The system SHALL refuse to start, with exit code 3 and the key phrase of design D12, when its environment carries the variable that Claude Code sets in the shells it starts. The check SHALL happen before the settings are read and before any step. The system SHALL NOT offer an option that bypasses this refusal.

Source: tests/flow_monthly/test_frontiere.py (Frontiere, AideEnProcessusReel)

#### Scenario: Started from a session
- **WHEN** the variable is present in the environment
- **THEN** the output holds "Refused inside a Claude Code session", no file is read, no tool is called, and the exit code is 3

### Requirement: Completion line counts run and skipped steps
The system SHALL end a complete run with the completion key phrase, where the run count is the number of step calls made in this run, the total is the number of step calls of the full plan for the configured series (the retention step included, as one call), and the skipped count is the number of step calls before the `--from` step. The system SHALL NOT print a run count equal to the total when steps were skipped.

Source: tests/flow_monthly/test_conservation_et_reprise.py (LigneFinale)

#### Scenario: Full run
- **WHEN** a complete run of a plan of eight calls (two series, one map each) ends
- **THEN** the output holds "Monthly run complete: 8 of 8 steps, 0 skipped"

#### Scenario: Resumed run
- **WHEN** a run of the same plan starts with `--from dependencies` and the last three calls pass
- **THEN** the output holds "Monthly run complete: 3 of 8 steps, 5 skipped"

### Requirement: Step progress numbering
The step progress lines SHALL number the calls of this run from one.

Source: tests/flow_monthly/test_conservation_et_reprise.py (LigneFinale)

#### Scenario: Resumed run numbering
- **WHEN** a run starts with `--from dependencies`
- **THEN** the first step progress line numbers its call one

### Requirement: Import step marks tickets out of the export
The system SHALL call the import step with the out-of-export mark option of the jira-flow-import capability and with no export file, after an export step that ran every named query. The system SHALL NOT pass that option after an export of a subset of the queries.

Source: tests/flow_monthly/test_conservation_et_reprise.py (MarquageDeLImport)

#### Scenario: Import call
- **WHEN** the import step runs for two named queries
- **THEN** the import tool receives the mark option and no export path

### Requirement: Retention dry run as the last step
The system SHALL run, after the last dependency step, a `retention` step that calls the retention tool's `purge` subcommand without `--apply`, with the run's output language.

Source: tests/flow_monthly/test_conservation_et_reprise.py (EtapeRetention)

#### Scenario: Call recorded
- **WHEN** a complete run ends
- **THEN** the retention tool was called once with `purge`, without `--apply`, and with the run's language option, after every dependency call

### Requirement: Retention line of the monthly run
When the retention tool exits with 0, the system SHALL capture the tool's output without printing it, as for every step, and print only the monthly-run retention line of design D19 with the total read from the tool's check total line in the run's language, mark the step passed, and write that retention line in the summary file. Out-of-rule counts SHALL be reported and SHALL NOT stop the run or change its exit code.

Source: tests/flow_monthly/test_conservation_et_reprise.py (EtapeRetention)

#### Scenario: Items out of rule reported
- **WHEN** the fake retention tool prints "retention check: 7 items out of rule" and "dry run: nothing deleted" and exits with 0
- **THEN** the output holds "retention dry run: 7 items out of rule", the summary file holds the same line, the step is passed, the final status is complete, and the exit code is 0

#### Scenario: Nothing out of rule
- **WHEN** the fake retention tool prints "retention check: nothing out of rule" and exits with 0
- **THEN** the output and the summary hold "retention dry run: 0 items out of rule"

#### Scenario: French run
- **WHEN** a complete run uses the default French output and the fake tool prints "contrôle de conservation : 2 éléments hors règle"
- **THEN** the output and the summary hold "essai de purge : 2 éléments hors règle"

### Requirement: Retention step failure
A non-zero exit of the retention tool, or an output without the check total line, SHALL mark the step failed like any step: the run stops at `retention` with exit code 1 and the resume hint, and the summary's final status is "stopped at retention".

Source: tests/flow_monthly/test_conservation_et_reprise.py (EtapeRetention)

#### Scenario: Retention tool error
- **WHEN** the fake retention tool exits with 1
- **THEN** the output holds "Stopped at step retention: exit code 1" and "--from retention", the summary lists the earlier steps as passed and retention as failed, the final status is "stopped at retention", and the exit code is 1

### Requirement: Limits of the retention step
The system SHALL NOT pass `--apply`, SHALL NOT call the retention `check`, SHALL NOT create a labelled backup, SHALL NOT open a store itself, and SHALL NOT write the retention line with a guessed count. The real purge stays a separate command run by the user alone after the labelled backup of the day.

Source: tests/flow_monthly/test_conservation_et_reprise.py (EtapeRetention)

#### Scenario: No applied purge and no check
- **WHEN** a complete run ends
- **THEN** no retention call carries `--apply`, no call to the retention check was recorded, and no backup was created

### Requirement: Series date of a resume
The system SHALL, for a run with `--from` a step other than `export` and without `--date`, decide the run date with the rule of design D1 of the flow-monthly-resume change, from the summaries of the current month whose export step passed, and SHALL announce that date before the first step with the series-date key phrase. It SHALL NOT fall back to today and SHALL NOT let a summary whose export step did not pass decide the date.

Source: tests/flow_monthly/test_reprise_serie.py

#### Scenario: Resume of an earlier day
- **WHEN** a summary of an earlier day of the month records export passed and the final status "stopped at import", and the run starts today with `--from import` and no `--date`
- **THEN** the output holds "Resuming the series of" with that earlier date, the import tool receives no export path, and the resume summary is written under that date

#### Scenario: Summary of a defaulted resume ignored
- **WHEN** a summary of today records export skipped and an earlier summary of the month records export passed and is unfinished
- **THEN** the earlier date is used

#### Scenario: Last complete run
- **WHEN** the only candidate of the month is complete and the run starts with `--force --from retention`
- **THEN** that complete run's date is used

#### Scenario: Explicit date wins
- **WHEN** the run starts with `--from flow` and `--date` set to an earlier day
- **THEN** the series rule is not applied and that day is the run date

### Requirement: Refusal when the series date is undecided
The system SHALL refuse a resume before any step, with exit code 2, no summary written and the key phrase of design D2 of this change proposing `--date`, when the series rule finds several unfinished series or none. It SHALL NOT guess a date and SHALL NOT print a series, query or team name.

Source: tests/flow_monthly (to write)

#### Scenario: Ambiguous series
- **WHEN** two unfinished summaries of the month record export passed and no complete summary follows them
- **THEN** no tool is called, the output holds "Series in progress ambiguous" with both dates and "--date", no summary is written, and the exit code is 2

#### Scenario: No series in progress
- **WHEN** no summary of the month records export passed and the run starts with `--from flow`
- **THEN** no tool is called, the output holds "No series in progress this month", and the exit code is 2

### Requirement: Rewrite warning for a series date
The system SHALL print, before the first step, the rewrite key phrase of design D6 of this change when the run date, given by `--date` or decided by the series rule, has a monthly summary in the reports folder. It SHALL NOT ask for a confirmation and SHALL NOT change the exit code.

Source: tests/flow_monthly (to write)

#### Scenario: Date of an existing series
- **WHEN** the run starts with `--from flow --date` set to a date that has a summary
- **THEN** the output holds "Warning: the reports of" with that date before the first step line, and the steps run

#### Scenario: Date decided by the series rule
- **WHEN** the run starts the day after a complete series of the month with `--force --from flow` and no `--date`
- **THEN** the output holds "Resuming the series of" and "Warning: the reports of" with the series date, before the first step line

#### Scenario: Date without a summary
- **WHEN** `--date` names a date without a summary
- **THEN** no rewrite warning is printed

### Requirement: Stop at the first failing step
The system SHALL stop at the first step whose tool exits with a non-zero code, SHALL run no later step, and SHALL print the step identifier, the tool's exit code and the resume hint of design D12 of the monthly-run change. Any non-zero tool exit SHALL stop the run with exit code 1.

Source: tests/flow_monthly/test_suivi_mensuel.py (ArretAuPremierEcart)

#### Scenario: Failing import
- **WHEN** the import tool exits with 1
- **THEN** the output holds "Stopped at step import: exit code 1" and "--from import", no history or calculation tool is called, and the exit code is 1

#### Scenario: Unreadable dependency input
- **WHEN** the dependency tool exits with 2
- **THEN** the run stops at step dependencies with exit code 1

#### Scenario: Failing history
- **WHEN** the history tool exits with 3
- **THEN** the run stops at step history with exit code 1, not 4

### Requirement: Retired open option refused
The system SHALL refuse the retired `--open` option with exit code 2 and its own phrase, French or English by `--language`, before reading any setting (design D3 of change remove-flow-board). It SHALL call no tool and write no summary.

Source: tests/flow_monthly/test_suivi_mensuel.py (OrdreEtOptions)

#### Scenario: Open option given
- **WHEN** the run is started with `--open`
- **THEN** the output holds "--open est retiré avec le tableau des flux" (or the English phrase with `--language en`), no setting is read, no tool is called, no summary is written, and the exit code is 2
