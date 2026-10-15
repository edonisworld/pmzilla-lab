# jira-flow-epic-statuses Specification

## Purpose
Describes the user-run epic statuses report (current epics and observed passages per status, small cells masked) and the validation of the Discovery Workflow mapping read from the flow settings. Sources are `tests/epic_statuses/test_epic_statuses.py` and `tests/flux_config/test_nouveaux_blocs.py`.

## Requirements

### Requirement: Epic statuses report
The system SHALL provide a user-run tool that reads one or more API-export files and the history cache, keeps the tickets of the configured epic types, and writes in the reports folder of the flow folder a dated Markdown report giving, per status: the number of epics currently in it, the number of passages observed in the history, and its most frequent outgoing transitions with their counts. Every count below five SHALL be written "<5". The report SHALL hold no key, no title, no team, no person and no label. The console SHALL print counts only and the report key phrase of design D19.

Source: tests/epic_statuses/test_epic_statuses.py (TestRapport, TestConsole)

#### Scenario: Report content
- **WHEN** the tool runs on an export and a cache holding epics in four statuses
- **THEN** the report lists the four statuses with current counts, passages and frequent transitions, and contains no key and no team name

#### Scenario: Small cell
- **WHEN** only two epics are currently in a status
- **THEN** that cell reads "<5"

#### Scenario: No epic
- **WHEN** the exports hold no ticket of the configured epic types
- **THEN** the tool writes no report, says no epic was found, and exits with code 1

### Requirement: Epic statuses tool refused inside a session
The system SHALL refuse to start, with exit code 3 and the session key phrase of design D19, when the variable that Claude Code sets in its shells is present, before reading any file. It SHALL print in French by default and in English with `--language en`, and refuse another language with exit code 2.

Source: tests/epic_statuses/test_epic_statuses.py (TestSession, TestConsole)

#### Scenario: Started from a session
- **WHEN** the variable is present
- **THEN** no file is read, the output holds "Refused inside a Claude Code session", and the exit code is 3

### Requirement: Discovery Workflow mapping validated before use
The system SHALL read the mapping of statuses to Discovery Workflow columns from the `discovery_workflow` block of the flow settings (columns, each with its statuses; a start column; the review-passed columns of design D6; a validation date). A status mapped to two columns, or a start column or a review-passed column that is not a declared column, SHALL stop the reading tool with exit code 1 naming the key path and line. Without a validation date, the system SHALL compute nothing on the mapping and SHALL say so in the report that would use it. The system SHALL NOT write or change the mapping itself.

Source: tests/flux_config/test_nouveaux_blocs.py (TestDiscoveryWorkflow); tests/epic_statuses/test_epic_statuses.py (TestDiscoveryWorkflow); tests/flux_jira/test_cycles_calcul.py (EpicReview)

#### Scenario: Not validated
- **WHEN** the block holds columns but no validation date
- **THEN** the cycles report says the mapping is not validated and computes no delay, no pass and no rejection

#### Scenario: Status in two columns
- **WHEN** a status appears under two columns
- **THEN** the tool stops with exit code 1 and names the key path, not the status

#### Scenario: Mapped status never observed
- **WHEN** the epic statuses tool runs and a mapped status is absent from the observed statuses
- **THEN** the report lists that status name under "mapped but not observed"
