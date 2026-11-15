# jira-flow-epic-statuses Specification

## Purpose
Describes the user-run epic statuses report (current epics and observed passages per status, small cells masked) and the validation of the Discovery Workflow mapping read from the flow settings. Sources are `tests/epic_statuses/test_epic_statuses.py` and `tests/flux_config/test_nouveaux_blocs.py`.

## Requirements

### Requirement: Epic statuses report
The system SHALL provide a user-run tool that reads the tickets and the history from the database under the read-only role, keeps the tickets of the configured epic types, and writes in the reports folder of the flow folder a dated Markdown report giving, per status: the number of epics currently in it, the number of passages observed in the history, and its most frequent outgoing transitions with their counts.

Source: tests/epic_statuses/test_epic_statuses.py (TestRapport)

#### Scenario: Report content
- **WHEN** the tool runs on a database holding epics in four statuses with their history
- **THEN** the report lists the four statuses with current counts, passages and frequent transitions, and contains no key and no team name

#### Scenario: No epic
- **WHEN** the database holds no ticket of the configured epic types
- **THEN** the tool writes no report, says no epic was found, and exits with code 1

### Requirement: Same-status transitions are not passages
The system SHALL count neither a passage nor an outgoing transition for a transition whose starting and arrival statuses have the same name (case and spaces ignored, an empty status never counted) in the epic statuses report.

Source: tests/epic_statuses/test_epic_statuses.py (TestTransitionsMemeStatut)

#### Scenario: Epic Review to Epic Review
- **WHEN** an epic history holds Draft to Epic Review, then Epic Review to Epic Review
- **THEN** Epic Review shows one passage and no outgoing transition to itself

### Requirement: Small counts masked in the epic statuses report
Every count below five SHALL be written "masqué" in French and "masked" in English, and the report introduction SHALL state the threshold of five.

Source: tests/epic_statuses/test_epic_statuses.py (TestRapport)

#### Scenario: Small cell
- **WHEN** only two epics are currently in a status
- **THEN** that cell reads "masqué" in a French report and "masked" in an English one

### Requirement: Epic statuses report and console hold no identifying data
The report SHALL hold no key, no title, no team, no person and no label. The console SHALL print counts only and the report key phrase of design D19 of the GDPR alignment.

Source: tests/epic_statuses/test_epic_statuses.py (TestRapport, TestConsole)

#### Scenario: Report and console content
- **WHEN** the tool runs on a database holding epics with keys and teams
- **THEN** neither the report nor the console holds a key or a team name, and the console prints counts and the report key phrase of design D19

### Requirement: Export file refused by the epic statuses tool
An export file or a path given to the history option SHALL be refused with exit code 2 and the key phrases of design D6.

Source: tests/epic_statuses/test_epic_statuses.py (TestConsole)

#### Scenario: Export file
- **WHEN** an export file is given
- **THEN** the output holds "export files are no longer read: the database is the only source" and the exit code is 2

### Requirement: Epic statuses tool refused inside a session
The system SHALL refuse to start, with exit code 3 and the session key phrase of design D19, when the variable that Claude Code sets in its shells is present, before reading any file. It SHALL print in French by default and in English with `--language en`, and refuse another language with exit code 2.

Source: tests/epic_statuses/test_epic_statuses.py (TestSession, TestConsole)

#### Scenario: Started from a session
- **WHEN** the variable is present
- **THEN** no file is read, the output holds "Refused inside a Claude Code session", and the exit code is 3

### Requirement: Discovery Workflow mapping validated before use
The system SHALL read the mapping of statuses to Discovery Workflow columns from the `discovery_workflow` block of the flow settings, whose keys are given in the scenario "Keys of the block". The system SHALL NOT write or change the mapping itself.

Source: tests/flux_config/test_nouveaux_blocs.py (TestDiscoveryWorkflow); tests/epic_statuses/test_epic_statuses.py (TestDiscoveryWorkflow); Ready and active columns untested until implemented.

#### Scenario: Keys of the block
- **WHEN** the `discovery_workflow` block is read
- **THEN** it gives the columns, each with its statuses; a start column; the review-passed columns of design D6; a validation date; and, as optional keys added by design D4 of the epic flow report change, one Ready column and a list of active columns

#### Scenario: Mapped status never observed
- **WHEN** the epic statuses tool runs and a mapped status is absent from the observed statuses
- **THEN** the report lists that status name under "mapped but not observed"

### Requirement: Inconsistent Discovery Workflow mapping stops the tool
A status mapped to two columns, or a start column, a review-passed column, a Ready column or an active column that is not a declared column, or a Ready column listed among the active columns, SHALL stop the reading tool with exit code 1 naming the key path and line, never a value.

Source: tests/flux_config/test_nouveaux_blocs.py (TestDiscoveryWorkflow); Ready and active columns untested until implemented.

#### Scenario: Status in two columns
- **WHEN** a status appears under two columns
- **THEN** the tool stops with exit code 1 and names the key path, not the status

#### Scenario: Ready column among the active columns
- **WHEN** the Ready column is also listed among the active columns
- **THEN** the tool stops with exit code 1, naming the key path and line, without the column name

#### Scenario: Undeclared active column
- **WHEN** an active column is not one of the declared columns
- **THEN** the tool stops with exit code 1, naming the key path and line, without the column name

### Requirement: Unvalidated Discovery Workflow mapping
Without a validation date, the system SHALL compute nothing on the mapping and SHALL say so in the report that would use it.

Source: tests/flux_jira/test_cycles_calcul.py (EpicReview)

#### Scenario: Not validated
- **WHEN** the block holds columns but no validation date
- **THEN** the cycles report says the mapping is not validated and computes no delay, no pass and no rejection

### Requirement: Optional keys of the Discovery Workflow mapping
The cycles report and the epic statuses report SHALL read the block with or without the two optional keys, without any message.

Source: Ready and active columns untested until implemented.

#### Scenario: Optional keys absent
- **WHEN** the block holds neither a Ready column nor active columns
- **THEN** the cycles report and the epic statuses report read it without any message, as before this change
