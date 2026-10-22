# tooling-morning-guard Specification

## Purpose
Read-only shared module that states whether the morning routine (watch, backup, off-site copy) is done, postponed or still due, so that the branch-finishing scripts and the run-tree script refuse a finish inside the morning window instead of each reading the records themselves.

## Requirements

### Requirement: One shared module reads the morning state
The system SHALL provide one shared module (design D1) that reads three parts: the watch record of the day (D2), today's plain dated backup folder and its dump count (D3), and the copy log and off-site status file (D4); it SHALL be the only reader of those sources for a morning decision. It SHALL NOT write, create or remove anything, list the backups folder itself, read a backup file's content, run the copy script, or print a path or file name. Untested until implemented (suite `morning_state`).

#### Scenario: Every part verified
- **WHEN** today's watch record says `termine`, today's plain dated backup folder holds the expected number of dumps, and the copy log holds a line dated today with `copie créée : db-<today>`
- **THEN** the watch part is finished, the backup is complete and the copy part is proven

#### Scenario: Nothing written
- **WHEN** every case of the suite has run
- **THEN** the temporary data folder, backups folder, copy log and status file are exactly as before each case, and no output holds a path

### Requirement: Inside the morning window, a finish is allowed only on a verified morning state
The system SHALL allow before the run-tree morning start and, from it until midnight, only when the watch ended without error, today's backup is complete and the copy is proven or declared postponed (design D5); an unreadable state SHALL be refused, with no fallback. It SHALL NOT end the window at a fixed hour, accept another watch state, count a missing backups folder, or let a postponement cover the watch or backup. Untested until implemented (suite `morning_state`).

#### Scenario: Before the window
- **WHEN** the check runs before the morning start and no watch record of today exists
- **THEN** the line says allowed before the morning window and the exit code is 0

#### Scenario: Watch failed
- **WHEN** the check runs inside the window, today's watch record says `echoue`, the backup is complete and the copy is proven
- **THEN** the exit code is 1 and the line names the watch reason with the state

#### Scenario: Two dumps
- **WHEN** the check runs inside the window and today's backup folder holds one dump fewer than expected
- **THEN** the exit code is 1 and the line holds the "backup incomplete" reason with both counts

#### Scenario: Late evening
- **WHEN** the check runs late in the evening and today's off-site copy is neither proven nor declared
- **THEN** the exit code is 1

#### Scenario: Unreadable record after the run-tree fallback time
- **WHEN** the check runs inside the window, after the run-tree script's fallback time, and the watch record is unreadable
- **THEN** the exit code is 1 and the line holds the "watch state unreadable" reason

#### Scenario: Postponement does not cover the watch
- **WHEN** a postponement is declared today and today's watch record says `reporte`
- **THEN** the exit code is 1 and the line names the watch reason only

### Requirement: An isolated source error is not a watch in error
The system SHALL count the watch part as finished when today's watch run had its collection fail on individual sources only and every other step succeeded (design D2, author decision of 2026-10-18). It SHALL NOT count as finished a collection that failed as a whole, or any other failed step, and SHALL NOT read the watch log or print a source or step name to tell them apart. Untested until implemented (suite `morning_state`).

#### Scenario: Isolated source error
- **WHEN** the check runs inside the window, today's watch run had one source in error in the collection and every other step succeeded, the backup is complete and the copy is proven
- **THEN** the watch part is finished and the exit code is 0

#### Scenario: Collection failed as a whole
- **WHEN** the check runs inside the window and today's watch record says `echoue` with no isolated-source mark
- **THEN** the exit code is 1 and the line names the watch reason with the state

### Requirement: The off-site copy part accepts proofs and declarations of today only
The system SHALL count the copy part as proven on a copy-log line dated today with `copie créée : db-<today>` or `déjà présente : db-<today>`, or on the status file's last database copy `db-<today>`, and as postponed on a line dated today with `copie reportée déclarée : db-<today> : <reason>` (design D4). It SHALL NOT count a line of another day, an undated line, a copy of another backup day, or the absent-disk deferral line. Untested until implemented (suite `morning_state`).

#### Scenario: Declaration of yesterday
- **WHEN** the copy log holds only a declaration dated yesterday
- **THEN** the copy part is absent

#### Scenario: Absent-disk deferral
- **WHEN** the copy log holds, dated today, only `disque absent ou verrouillé : copie reportée`
- **THEN** the copy part is absent

#### Scenario: Manual copy before this change
- **WHEN** the copy log holds no line of today and the status file's last database copy is `db-<today>`
- **THEN** the copy part is proven

#### Scenario: Copy of yesterday's backup
- **WHEN** the copy log holds, dated today, `copie créée : db-<yesterday>`
- **THEN** the copy part is absent

### Requirement: The morning-state command line
The system SHALL provide `check`, printing one decision line of design D5 in French by default and in English with the shared language option, every failing part named in the order watch, backup, copy, and exiting 0 when allowed, 1 when refused and 2 on usage; a failure of the shared lab-paths resolution SHALL keep its own code. It SHALL NOT give one code to two outcomes and SHALL NOT offer an option that changes the decision. Untested until implemented (suite `morning_state`).

#### Scenario: English refusal
- **WHEN** `check --language en` runs inside the window with no watch record of today and no copy proof
- **THEN** the line starts with `morning_state: refused, morning window since`, holds `no watch run today` then `today's off-site copy neither proven nor postponed`, and the exit code is 1

#### Scenario: Usage
- **WHEN** the command runs without a subcommand or with an unknown option
- **THEN** the exit code is 2 and nothing is read

### Requirement: The morning-state module is testable without the real lab folder
The system SHALL include a shell suite, listed in the runner, that runs the module with the lab data folder, the backups folder, the copy log, the status file and the clock replaced through environment variables, and SHALL keep static tests that compare the expected dump count with the backup script's databases and the default morning start with the watch template's scheduled time less the author's lead. The suite SHALL NOT read or change the real lab folders. Untested until implemented.

#### Scenario: Suite run
- **WHEN** the runner runs the `morning_state` suite
- **THEN** every case runs in a temporary folder and the suite reports its counts in the runner's shell format

#### Scenario: Constants aligned
- **WHEN** the backup script's database list or the watch template's time changes without the module's constants
- **THEN** a static test of the suite fails and names the constant
