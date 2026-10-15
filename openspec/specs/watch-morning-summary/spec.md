# watch-morning-summary Specification

## Purpose
TBD - created by archiving change morning-summary. Update Purpose after archive.

## Requirements

### Requirement: Print the morning summary with counts only
The system SHALL provide a summary script that prints, after a title, one line each for the watch of the day, the due reviews, the ready jobs and the doctor's last check, in that order, with the key phrases of design D7, in French by default or English with the shared language option. It SHALL give counts and dates only. It SHALL NOT print an article title, a review's problem text, a job title, a path, a name or a secret. Untested until implemented.

#### Scenario: Every part known
- **WHEN** the run record, the count file, the snapshot and the doctor's state file are today's and the database answers
- **THEN** the output holds the title and four lines with the key phrases of design D7, and exit code is 0

#### Scenario: No text leaks
- **WHEN** the fixtures' titles and problem texts hold a sentinel string
- **THEN** neither the output, the JSON nor the notification arguments contain it

#### Scenario: English
- **WHEN** the script runs with the English language option
- **THEN** the lines use the English key phrases of design D7

### Requirement: Outputs and exit codes of the summary script
The system SHALL exit 0 once the summary is printed, whatever part is unknown; 1 when an allowed notification could not be sent; 2 on a usage error; 3 when an allowed notification was skipped because one was already sent today; 4 when it was skipped because the summary is switched off (design D2, D15). With the JSON option it SHALL print the same parts as states, counts and dates. An unknown part SHALL NOT stop the summary nor change its exit code. Untested until implemented.

#### Scenario: Nothing readable
- **WHEN** no run record, count file, snapshot or doctor state exists and the database does not answer
- **THEN** every line says its part is unknown, unreachable or absent, and exit code is 0

#### Scenario: JSON
- **WHEN** the script runs with the JSON option
- **THEN** it prints one JSON object with the keys of design D2 and no title or problem text

#### Scenario: Unknown option
- **WHEN** an unknown option is given
- **THEN** the script exits 2 and notifies nothing

### Requirement: The watch line comes from the run record of the day
The system SHALL read the watch state only from the record of the run of the day: done, done by catch-up, or failed with the count and labels of the failed steps given by the run, or "failed" without labels. A missing, unreadable or other-day record SHALL give the "watch state unknown" key phrase of design D7. It SHALL NOT read the watch log or the content folders. Untested until implemented.

#### Scenario: Catch-up run done
- **WHEN** today's record says done with the catch-up trigger
- **THEN** the watch line carries the catch-up mark of design D7

#### Scenario: Failed run
- **WHEN** today's record says failed and the run gives two failed step labels
- **THEN** the watch line gives the count 2 and both labels in order

#### Scenario: Yesterday's record
- **WHEN** the record holds yesterday's date
- **THEN** the watch line says the watch state is unknown

### Requirement: The kept count comes from the count file of the day's run
The system SHALL take the count of articles kept by the day's run only from the count file written by the ranked reading list, and only when its date is the date of the day's run record (design D3). A count file that is missing, unreadable or of another date SHALL give the "no triage today" key phrase of design D7. It SHALL NOT read the reading list, the watch folder or the triage store. Untested until implemented.

#### Scenario: Count of today
- **WHEN** the count file holds the date of today's run record and the count 7 and the record says done
- **THEN** the watch line says done with 7 articles kept

#### Scenario: Plain list only
- **WHEN** the record says done and the count file holds the previous run's date
- **THEN** the watch line says done with no triage today

### Requirement: Due reviews are counted by the shared due rule
The system SHALL count the configured author's due reviews, and among them those flagged "decision required", with the single due rule of the cases module, under the cases read-only role and a short connection timeout. It SHALL give the "database unreachable" key phrase when the database does not answer, and omit the line, opening no connection, when no author is configured. It SHALL NOT print a problem text or a connection error. Untested until implemented.

#### Scenario: Two due, one at the postponement limit
- **WHEN** two reviews of the author are due and one has reached the maximum of postponements
- **THEN** the reviews line gives 2 due with 1 decision required

#### Scenario: Database down
- **WHEN** the cases database does not answer
- **THEN** the reviews line is the "database unreachable" key phrase, the other lines are printed and exit code is 0

#### Scenario: No author
- **WHEN** no author is configured
- **THEN** the summary has no reviews line and no database connection is opened

### Requirement: Ready jobs are counted from the queue snapshot
The system SHALL count the ready jobs of the work queue from the reader's snapshot in the lab data folder, by the counting rule of the session-start reminder, and add the snapshot's date when it is not today. With no snapshot it SHALL give the "no cache" key phrase of design D7. It SHALL NOT call GitHub or the network, and SHALL NOT print a job title or identifier. Untested until implemented.

#### Scenario: Older snapshot
- **WHEN** the snapshot is three days old and holds four ready jobs
- **THEN** the queue line gives 4 ready with the snapshot's date, and no `gh` command is run

#### Scenario: No snapshot
- **WHEN** no snapshot exists
- **THEN** the queue line is the "no cache" key phrase

### Requirement: The doctor line comes from the doctor's state file
The system SHALL read the doctor's state file and give its check date with its count of problems, or "all good". A missing file SHALL give the "not checked yet" key phrase of design D7, an unreadable one the "state unreadable" key phrase. It SHALL NOT run the doctor, give a check's reason or identifier, nor stop the doctor's own problem notification (design D8). Untested until implemented.

#### Scenario: Problems found yesterday
- **WHEN** the state file holds yesterday's check with two problems
- **THEN** the doctor line gives yesterday's date and 2 problems, and no check name

#### Scenario: Doctor not installed
- **WHEN** the state file does not exist
- **THEN** the doctor line says not checked yet

### Requirement: Notify at most once a day, under the scheduler only
The system SHALL send the summary as one desktop notification, in French, only when the notify option and the scheduler variable of design D10 are both given, at most once a day, remembered in a small owner-only file of the lab data folder written after a successful notification. Without both, it SHALL print the summary and notify nothing. It SHALL pass the title and body to the notifier as arguments, never inside its script text. Untested until implemented.

#### Scenario: Scheduled call
- **WHEN** the script runs with the notify option and the scheduler variable and no summary was sent today
- **THEN** one notification is sent with the title of design D7 and the four parts, and today's date is remembered

#### Scenario: Second call the same day
- **WHEN** the script runs again with both the same day
- **THEN** no notification is sent, the "already sent" key phrase is printed and exit code is 3

#### Scenario: Session launch
- **WHEN** the script runs without the scheduler variable, with or without the notify option
- **THEN** it prints the summary, sends no notification and writes no file

### Requirement: The summary reads its files through the configured roots
The system SHALL find the lab data folder and the workspace that holds the author configuration through their configured settings, never from the script's own location, so that a run from the scheduled-jobs code tree reads the same files as a run from the repository. It SHALL write nothing but its once-a-day memory. Untested until implemented.

#### Scenario: Run from another code tree
- **WHEN** the script is launched from a copy of the code outside the workspace, with the data folder and the content root set
- **THEN** it reads the record, the count file, the snapshot, the doctor state and the author of the configured folders

### Requirement: A credential failure leaves the reviews unavailable
The system SHALL, when the cases reader password cannot be read from the Keychain, give the "unavailable" key phrase of design D7 on the reviews line, distinct from "database unreachable", and still print and send the summary with an unchanged exit code (design D5, D11). Untested until implemented.

#### Scenario: Keychain read fails under the scheduler
- **WHEN** a scheduled call runs and the password read fails
- **THEN** the reviews line says unavailable, the other lines are printed, one notification is sent and exit code is 0

### Requirement: The summary never shows the secret
The system SHALL NOT print, log, write to a file nor pass to the notifier the cases reader password, nor the text of an error raised while reading it or connecting with it (design D5, D13). Untested until implemented.

#### Scenario: Sentinel password
- **WHEN** the fake credential store holds a sentinel password and the read or the connection fails
- **THEN** the sentinel appears neither in the output, the JSON, the notification arguments nor the captured logs

### Requirement: A local switch turns the summary off
The system SHALL keep the summary on unless a local setting outside Git, the marker of design D15 in the lab data folder, switches it off. Off, a scheduled call SHALL print the summary, send no notification, write no memory and exit 4 with the "switched off" key phrase. A session launch SHALL print the summary whatever the switch. Untested until implemented.

#### Scenario: No setting
- **WHEN** no marker exists and a scheduled call runs
- **THEN** the summary is sent

#### Scenario: Switched off
- **WHEN** the marker exists and a scheduled call runs
- **THEN** no notification is sent, no memory is written, the "switched off" key phrase is printed and exit code is 4
