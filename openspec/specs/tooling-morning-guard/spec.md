# tooling-morning-guard Specification

## Purpose
Read-only shared module that states whether the morning routine (watch, backup, off-site copy) is done, postponed or still due, so that the branch-finishing scripts and the run-tree script refuse a finish inside the morning window instead of each reading the records themselves.

## Requirements

### Requirement: One shared module reads the morning state
The system SHALL provide one shared module that is the only reader, for a morning decision, of the watch record of the day, today's dated backup folder and its dump count, the copy log and off-site status file, and the watch lock and backup marker (light design D2). It SHALL NOT write, create, remove or renew anything, list the backups folder, read a backup's content, run the copy script, or print a path.

#### Scenario: Every part verified
- **WHEN** today's watch record says `termine`, today's plain dated backup folder holds the expected number of dumps, and the copy log holds a line dated today with `copie créée : db-<today>`
- **THEN** the watch part is finished, the backup is complete and the copy part is proven

#### Scenario: Nothing written
- **WHEN** every case of the suite has run
- **THEN** the temporary data folder, backups folder, copy log, status file, watch lock and backup marker are exactly as before each case, and no output holds a path

#### Scenario: Started record with a live watch lock
- **WHEN** today's watch record says `commence` and the watch lock folder holds the identifier of a live process, younger than the watch script's maximum lock age
- **THEN** the module says the watch is running

#### Scenario: Started record without a held lock
- **WHEN** today's watch record says `commence` and the watch lock folder is absent, names a dead process, or is older than the maximum lock age
- **THEN** the module says the watch is not running, and the watch part gives a warning

### Requirement: An isolated source error is not a watch in error
The system SHALL count the watch part as finished, with no warning, when today's watch run had its collection fail on individual sources only and every other step succeeded (author decision of 2026-10-18). A collection failed as a whole, or any other failed step, SHALL give the watch warning. It SHALL NOT read the watch log or print a source or step name to tell them apart.

#### Scenario: Isolated source error
- **WHEN** the check runs, today's watch run had one source in error in the collection and every other step succeeded, the backup is complete and the copy is proven
- **THEN** the watch part is finished, no warning line is printed and the exit code is 0

#### Scenario: Collection failed as a whole
- **WHEN** the check runs, nothing is running, and today's watch record says `echoue` with no isolated-source mark
- **THEN** the exit code is 0 and one warning line names the watch reason with the state

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
The system SHALL provide `check`, printing the decision line of light design D4 in French or, with the language option, English, then one warning line per part in default, and exiting 0 when allowed, 1 only while the watch or the backup runs, 2 on usage; a lab-paths failure keeps its own code. It SHALL NOT give one code to two outcomes, offer an option that changes the decision, or print a phrase of the former morning window.

#### Scenario: English warnings
- **WHEN** `check --language en` runs with no watch record of today, today's backup complete, no copy proof, and neither the watch lock nor the backup marker held
- **THEN** the first line is `morning_state: allowed, neither watch nor backup running`, the next lines are `morning_state: warning: watch state unreadable` then `morning_state: warning: today's off-site copy neither proven nor postponed`, and the exit code is 0

#### Scenario: English refusal
- **WHEN** `check --language en` runs while the backup marker holds a live process
- **THEN** the line is `morning_state: refused, running: backup in progress`, no line holds `morning window`, and the exit code is 1

#### Scenario: Usage
- **WHEN** the command runs without a subcommand, with an unknown option, or with `--margin`
- **THEN** the exit code is 2 and nothing is read

### Requirement: The morning-state module is testable without the real lab folder
The system SHALL include a shell suite, listed in the runner, that runs the module with the lab data folder, backups folder, copy log, status file and clock replaced through environment variables, and static tests comparing the expected dump count, the backup marker's name, and the watch lock's name and maximum age with the backup and watch scripts. It SHALL NOT keep a static test of a morning start, nor read or change the real lab folders.

#### Scenario: Suite run
- **WHEN** the runner runs the `morning_state` suite
- **THEN** every case runs in a temporary folder and the suite reports its counts in the runner's shell format

#### Scenario: Constants aligned
- **WHEN** the backup script's database list, the backup marker's name, or the watch lock's name or maximum age changes without the module's constants
- **THEN** a static test of the suite fails and names the constant

### Requirement: A finish is refused only while the watch or the backup runs
The system SHALL make `check` exit 1, at any hour, only while today's watch runs or the backup marker is held (light design D2), naming each running job, watch first. It SHALL NOT refuse for a failed, interrupted, postponed, absent or unreadable part, a dump count, a missing backups folder or a missing copy, nor read a time window. Replaces the morning-window refusal; removal: as light design D1.

#### Scenario: Nothing recorded, nothing running
- **WHEN** the check runs at 09:00 with no watch record of today and neither the watch lock nor the backup marker present
- **THEN** the exit code is 0, the decision line is `morning_state : autorisé, ni veille ni sauvegarde en cours`, and a warning line holds `état de la veille illisible`

#### Scenario: Backup running
- **WHEN** the backup marker folder holds the identifier of a live process, recently created
- **THEN** the exit code is 1 and the line is `morning_state : refusé, en cours : sauvegarde en cours`

#### Scenario: Both running
- **WHEN** today's watch record says `commence` with a live watch lock, and the backup marker holds a live process
- **THEN** the exit code is 1 and the line is `morning_state : refusé, en cours : veille du jour en cours ; sauvegarde en cours`

#### Scenario: Early hour
- **WHEN** the check runs at 04:00 with no watch record of today and nothing running
- **THEN** the exit code is 0 and no line holds `fenêtre du matin`

### Requirement: Failures are warnings that never change the decision
The system SHALL print, after the decision line of `check`, one warning line per part in default, in the order watch, backup, copy, with the reasons of light design D4. It SHALL NOT change the exit code for a warning, warn for a finished watch, a complete backup or a proven or declared copy, nor warn in the `runner` reading. Replaces the refusals for failures; removal: with the refusal rule above.

#### Scenario: Three warnings in order
- **WHEN** today's watch record says `echoue`, today's backup folder holds one dump fewer than expected, no copy proof exists, and nothing is running
- **THEN** the exit code is 0, and three warning lines follow the decision line, naming in that order the watch with `(état : echoue)`, the incomplete backup with both counts, and the copy

#### Scenario: Warnings beside a refusal
- **WHEN** the backup marker holds a live process and no copy proof exists
- **THEN** the exit code is 1, the decision line names `sauvegarde en cours`, and a warning line names the copy

### Requirement: The session-runner reading follows the same rule
The system SHALL give `runner` the decision of `check` (light design D1) with its own phrases of light design D4 and no warning line: 0 when neither the watch nor the backup runs, 1 when one runs. It SHALL NOT read a time window, accept `--margin` (usage, code 2), or refuse for a job not done, failed or unreadable. Replaces the runner window and its margin; removal: with the refusal rule above.

#### Scenario: Watch not run yet
- **WHEN** `runner` runs at 08:00 with a watch record of yesterday and no backup folder of today, nothing running
- **THEN** the exit code is 0 and the line is `morning_state : runner complet de session permis, ni veille ni sauvegarde en cours`

#### Scenario: Backup running
- **WHEN** `runner` runs while the backup marker holds a live process
- **THEN** the exit code is 1 and the line is `morning_state : runner complet de session refusé, en cours : sauvegarde en cours`

#### Scenario: Margin option
- **WHEN** `runner --margin 540` runs
- **THEN** the exit code is 2 and nothing is read
