# jira-flow-epic-flow Specification

## Purpose
TBD - created by archiving change epic-flow-report. Update Purpose after archive.

## Requirements

### Requirement: Epic flow report from the database
The system SHALL provide a user-run `epics` subcommand of the flow report tool that reads only the database under the read-only role and writes a Markdown and a JSON report named after the series and the day in the reports folder of the flow folder (design D1, D2), printing "epic flow report written" on success. The system SHALL NOT read an export file or the history cache.

#### Scenario: Report written
- **WHEN** `epics` runs on a database holding epics of the pilot with their history, a validated mapping and a cycles block
- **THEN** the Markdown and JSON reports are written in the reports folder, the console prints "epic flow report written" and domain counts only, and the exit code is 0

#### Scenario: No cycles block
- **WHEN** the settings hold no cycles block
- **THEN** the run stops with exit code 1 and the no-cycle phrase of the cycles subcommand, before reading the database, and writes no report

### Requirement: CSV files refused by the epic flow report
The system SHALL refuse CSV files given to `epics` with the "no CSV file may be given" key phrase and exit code 1, before any database read (design D2, D14). The system SHALL NOT read or merge such a file.

#### Scenario: CSV files given
- **WHEN** CSV files are passed to `epics`
- **THEN** the run stops with "no CSV file may be given", the exit code is 1, and the database is not read

### Requirement: Epic flow report outputs without sensitive values
The system SHALL write the report in French by default and in English with `--language en`, with the same JSON in both languages, and SHALL print on the console domain counts and the key phrases of design D14 only. The system SHALL NOT write a key, a title, a person, a label or a version name in the report, the JSON or the console, and SHALL NOT print a team name on the console.

#### Scenario: Distinctive values
- **WHEN** the data hold a distinctive string as key, declared label (domain, cycle, confirmation, Ready and Epic Review), fix version and team name
- **THEN** none of the first three appears in any output, and the team name appears only in the report files

#### Scenario: English report
- **WHEN** `epics` runs with `--language en`
- **THEN** the report is in English and its JSON equals the French run's JSON

### Requirement: Epic flow report refused inside a session
The system SHALL refuse to start `epics`, with exit code 3 and "Refused inside a Claude Code session" (French "Refusé dans une session Claude Code"), when the variable that Claude Code sets in its shells is present, before reading any setting or the database (design D14). The system SHALL NOT read any file or open any connection in that case.

#### Scenario: Started from a session
- **WHEN** the variable is present
- **THEN** no setting is read, no connection is opened, the output holds "Refused inside a Claude Code session", and the exit code is 3

### Requirement: Pilot population from the domain label
The system SHALL count an epic in the pilot when a period of the declared domain label (the `pilot_domain` role) is open on the run day, SHALL put each epic of the pilot in the row of its first team, and an epic of the pilot without a team in the domain row and the "no team" row (design D3). The system SHALL NOT read the population from the organisation referential or from a tracked file, and SHALL NOT count an epic whose domain label is not open on the run day.

#### Scenario: Epic without the domain label
- **WHEN** an epic's first team holds other epics of the pilot but the epic never carried the domain label
- **THEN** the epic is counted nowhere in the report and the console gives no count of it

#### Scenario: Epic of the pilot without a team
- **WHEN** an epic carries the domain label and no team
- **THEN** it counts in the domain row and in the "no team" row, and in no team's row

#### Scenario: Domain label removed
- **WHEN** an epic's domain label period was closed before the run day
- **THEN** the epic is counted nowhere in the report

### Requirement: Pilot population errors
The system SHALL stop `epics` with exit code 1 and the key phrases of design D14 when the declared labels hold no domain label ("pilot domain not configured: no domain label declared") or when no epic belongs to the pilot ("no epic in the pilot domain"), and SHALL write no report. The system SHALL NOT print a team, domain, project or label name in these messages.

#### Scenario: No domain label declared
- **WHEN** the declared labels hold no `pilot_domain` role
- **THEN** the run stops with exit code 1, the output holds "pilot domain not configured", no name is printed, and no report is written

#### Scenario: No epic in the pilot
- **WHEN** the domain label is declared but no stored epic carries it on the run day
- **THEN** the run stops with exit code 1 and "no epic in the pilot domain"

### Requirement: Epic history coverage
The system SHALL write on the console and in the report "epics with history: {h} of {n}", masked under five, and SHALL stop with exit code 1 and "no epic history in the database: run the history collection first" when epics belong to the pilot and none has stored history (design D14). The system SHALL NOT treat an epic without history as an epic that never moved.

#### Scenario: No epic history
- **WHEN** twelve epics belong to the pilot and none has stored history
- **THEN** the run stops with exit code 1 and the no-epic-history phrase, and writes no report

### Requirement: Idea to Ready start point
The system SHALL start the idea-to-Ready measure at the epic's first transition into a status of the start column, or at its creation instant when its initial status maps to the start column (design D5). The system SHALL NOT take the creation instant as the start when the initial status is outside the start column, and SHALL NOT use the cycle label or the fix version as a start.

#### Scenario: Created in the start column
- **WHEN** an epic is created in a status of the start column and first enters a Ready status twenty days later
- **THEN** its duration is twenty days

#### Scenario: Created elsewhere
- **WHEN** an epic is created in an unmapped status, enters the start column ten days later, and reaches Ready fifteen days after that
- **THEN** its duration is fifteen days, not twenty-five

### Requirement: Ready source
The system SHALL take the end of idea to Ready from the first add of the declared Ready label when that label is configured, and otherwise from the first entry into the Ready column of the mapping, choosing one source per run and writing it on the "Ready source" line of design D14 in the report and the JSON (design D5). The system SHALL NOT mix the two sources in one run.

#### Scenario: Ready label configured
- **WHEN** the Ready label is configured, and an epic gets it twelve days after entering the start column and enters the Ready column three days later
- **THEN** its duration is twelve days and the report reads "Ready source: Ready label"

### Requirement: Ready label not configured
The system SHALL, when the Ready label is empty or absent, write "Ready label not configured: Ready column used" in the report and on the console and use the Ready column (design D5, D14). The system SHALL NOT stop the run, change its exit code or treat the empty label as a settings error.

#### Scenario: Ready label empty
- **WHEN** the Ready role holds an empty value and the mapping holds a Ready column
- **THEN** the report and the console hold "Ready label not configured: Ready column used", the durations end at the first entry into the Ready column, and the exit code is 0

### Requirement: Idea to Ready figures
The system SHALL compute, only with a validated mapping and a Ready source (design D5), the calendar days (export time zone) from the start point to the Ready end, count the epic in the cycle holding its end day, and give per cycle and overall the epics that reached Ready, median and 85th percentile. The system SHALL NOT put an epic without a known start in the duration: it is counted under "no start-column entry".

#### Scenario: Never in the start column
- **WHEN** an epic reaches Ready without any status of the start column in its history
- **THEN** it is counted under "no start-column entry" and not in the duration

#### Scenario: Cycle of the end day
- **WHEN** an epic enters the start column in cycle C1 and reaches Ready in cycle C2
- **THEN** it counts in C2's figures and not in C1's

### Requirement: Passages in Epic Review
The system SHALL compute from the adds of the declared Epic Review label of the pilot's epics (design D6): per cycle, the submissions and the resubmissions (adds that are not the epic's first); and, for the epics submitted at least once, their distribution in the buckets 1, 2, and 3 or more submissions, without needing a validated mapping. The system SHALL NOT infer a passage from a status, and SHALL NOT repeat the passes and rejections of the cycles report.

#### Scenario: Resubmission
- **WHEN** an epic gets the label in one cycle, loses it, and gets it again in the next cycle
- **THEN** the first cycle counts one submission and no resubmission, the next one counts one submission and one resubmission, and the epic falls in the bucket of two submissions

### Requirement: No Epic Review role declared
The system SHALL write "no Epic Review label declared" in the passages section when the declared labels hold no Epic Review role, and SHALL compute the other sections according to the mapping (design D11). The system SHALL NOT stop the report or change its exit code because of it.

#### Scenario: No Epic Review role
- **WHEN** the declared labels hold no Epic Review role
- **THEN** the section reads "no Epic Review label declared", the other sections follow the mapping, and the exit code is unchanged

### Requirement: Planned cycle as it stood when its cycle started
The system SHALL take an epic's planned cycle from the cycle key of the last cycle label added before the first day of that cycle's window (a label present from creation counts from creation), and SHALL count an epic without a cycle label on the "not planned" line (design D7). The system SHALL NOT take it from a later shift label, the fix version or a status, nor deduce it from label text.

#### Scenario: Shift after the cycle started
- **WHEN** an epic gets the cycle label of C2 before the first day of C2, then the cycle label of C3 during C2
- **THEN** its planned cycle is C2

#### Scenario: Replanned before the start, finished in the new cycle
- **WHEN** an epic gets the cycle label of C1, then, before the first day of C1, the cycle label of C2, and is resolved as done in C2
- **THEN** its planned cycle is C2, it counts under "in planned cycle" and on the "replanned before start" line of C2, and not under "carried over"

### Requirement: Epics planned late
The system SHALL take, for an epic whose cycle labels were all added on or after the first day of the earliest label's cycle, that cycle as planned cycle, and SHALL count the epic on the "planned late" line of that cycle, by team row, masked as in design D10 (design D7, fiche Q19). The system SHALL NOT drop such an epic from the carry-over buckets, and SHALL NOT count it as a declared shift.

#### Scenario: Planned late
- **WHEN** an epic gets its only cycle label, that of C2, on the third day of C2
- **THEN** its planned cycle is C2 and it also counts on the "planned late" line of C2

#### Scenario: Planned late then shifted
- **WHEN** an epic gets the cycle label of C2 on the third day of C2, then the cycle label of C3
- **THEN** its planned cycle is C2, it counts on the "planned late" line of C2, and the C3 label is a declared shift

#### Scenario: No cycle label
- **WHEN** an epic of the pilot never carried a cycle label
- **THEN** it is counted on the "not planned" line and in no planned cycle

### Requirement: Carry-over from the actual cycle
The system SHALL put each epic planned in an ended cycle in exactly one bucket, from its resolution day (export time zone): "in planned cycle" (on or before the cycle's last day), "carried over" (after it), "provisional carry-over" (not resolved on the run day) or "rejected" (next requirement); a cycle not ended reads "cycle in progress" (design D7), without a validated mapping. The system SHALL NOT decide a carry-over from a shift, the fix version or a status.

#### Scenario: Resolved after its planned cycle
- **WHEN** an epic planned in C2 is resolved during C3
- **THEN** it counts under "carried over" for C2, with or without a cycle label of C3

#### Scenario: Not resolved
- **WHEN** an epic planned in C2, which has ended, is not resolved on the run day
- **THEN** it counts under "provisional carry-over" for C2

#### Scenario: Resolved late in the evening
- **WHEN** an epic planned in C2 is resolved at 23:30 local time on the last day of C2, which is the next day in UTC
- **THEN** it counts under "in planned cycle"

#### Scenario: Rejected epic
- **WHEN** an epic planned in C2, which has ended, is resolved during C3 with a resolution on the excluded-resolutions list
- **THEN** it counts under "rejected" for C2, not under "carried over", "provisional carry-over" or "in planned cycle", and in no delivered count

#### Scenario: Planned cycle running
- **WHEN** the run day falls inside C3 and epics are planned in C3
- **THEN** the planned count of C3 is given and its bucket cells read "cycle in progress"

### Requirement: Done and not done resolutions of an epic
The system SHALL read the end date of an epic only from a resolution classed "done", a resolution being "not done" when it is on the existing excluded-resolutions list of the flow settings and "done" otherwise, and SHALL give the epics resolved with a resolution that is not done their own "rejected" line per planned cycle (design D7). The system SHALL NOT add a settings key for this classification, and SHALL NOT take the end date of a rejected epic as a delivery.

#### Scenario: Not done resolution
- **WHEN** an epic is resolved with a resolution on the excluded-resolutions list
- **THEN** it has no end date, is not delivered, and is counted under "rejected"

### Requirement: Confirmation of the planned epics
The system SHALL split the epics planned in a cycle by the confirmation label open at the end of the cycle's last day, or on the run day when the cycle has not ended, into "taken in", "not taken in" and "no confirmation label", according to the meaning declared for each confirmation label, and cross that split with the carry-over buckets (design D7). The system SHALL NOT read the confirmation state at another instant, and SHALL NOT infer it from a status.

#### Scenario: Confirmation changed after the cycle
- **WHEN** an epic planned in C2 carries a taken-in label at the end of C2 and a not-taken-in label from a day of C3
- **THEN** it counts under "taken in" for C2

### Requirement: Declared shift as a practice indicator
The system SHALL count, per planned cycle and team row, the epics given another cycle's label on or after the planned cycle's first day ("shift declared, carried over", "shift declared, not carried over") and the carried epics without one ("carried over without declared shift"), masked as in design D10. The system SHALL NOT use a declared shift to decide a carry-over, and SHALL NOT rank or score a team on this indicator.

#### Scenario: Undeclared shift
- **WHEN** an epic planned in C2 is resolved in C3 and never got another cycle label
- **THEN** it counts under "carried over" and under "carried over without declared shift"

#### Scenario: Declared shift, finished in time
- **WHEN** an epic planned in C2 gets the cycle label of C3 and is still resolved within C2
- **THEN** it counts under "in planned cycle" and under "shift declared, not carried over"

### Requirement: Re-planning before the cycle starts
The system SHALL count apart, per planned cycle and per team row, on the "replanned before start" line, the epics whose plan changed before the first day of their planned cycle's window, so that the planned cycle differs from the cycle of their earliest cycle label, masked as in design D10 (design D7). The system SHALL NOT count such a re-planning as a declared shift, and SHALL NOT use it to decide a carry-over.

#### Scenario: Replanned before the start
- **WHEN** an epic gets the cycle label of C3 and, before the first day of C3, the cycle label of C4
- **THEN** its planned cycle is C4, it counts on the "replanned before start" line of C4 and not under "shift declared, carried over" or "shift declared, not carried over"

#### Scenario: Shift after the start
- **WHEN** an epic planned in C3 gets the cycle label of C4 on the second day of C3
- **THEN** it counts as a declared shift and not on the "replanned before start" line

### Requirement: No cycle label linked to a cycle
The system SHALL write "no cycle label linked to a cycle" in the carry-over section when no declared cycle label names a cycle key, and SHALL compute the other sections (design D11). The system SHALL NOT stop the report or change its exit code because of it.

#### Scenario: Cycle labels without cycle keys
- **WHEN** the cycle role declares labels and none names a cycle key
- **THEN** the carry-over section reads "no cycle label linked to a cycle" and the exit code is unchanged

### Requirement: Epics per board column
The system SHALL count, only with a validated mapping, the pilot's epics whose current status maps to each column of the mapping, in the declared order of the columns, plus one line "status not mapped" (design D8). The system SHALL NOT read a Jira board configuration.

#### Scenario: Unmapped status
- **WHEN** three epics hold a status that maps to no column
- **THEN** the "status not mapped" line reads "masqué" ("masked" in English) and no status name is invented for them

### Requirement: Age of epics in progress
The system SHALL compute, only with a validated mapping holding the active columns, for the pilot's epics currently in an active column, the age in calendar days from the idea-to-Ready start point and the age in the current column from its last entry, with count, median and 85th percentile (design D9). Epics without a known start go under "no start-column entry", without an age. The system SHALL NOT substitute the creation instant for a missing start.

#### Scenario: Epic without start
- **WHEN** an epic in an active column has no status of the start column in its history
- **THEN** it is counted under "no start-column entry", has no age, and keeps its age in column

### Requirement: Epics older than the reference
The system SHALL count the epics in progress older than the 85th percentile of idea to Ready over all analysed cycles, and SHALL write "no reference" in that cell when the percentile is masked or idea to Ready is not computed (design D9). The system SHALL NOT use another reference in its place.

#### Scenario: Older than the reference
- **WHEN** the 85th percentile of idea to Ready is forty days and six epics in progress are older than forty days
- **THEN** the cell of epics older than the reference reads 6

#### Scenario: No reference
- **WHEN** fewer than five epics reached Ready over the analysed cycles
- **THEN** the cell of epics older than the reference reads "no reference"

### Requirement: Rows by pilot domain and team
The system SHALL give every measure as one row for the pilot domain, then one row per team of the pilot holding at least one of its epics, in name order, then the "no team" row when it is not empty (design D10). The system SHALL NOT order rows by a figure, rank or score a team, divide a figure by a headcount, or write a team name outside the report files of the flow folder.

#### Scenario: Name order
- **WHEN** a team with fewer epics has a name that sorts first
- **THEN** its row comes first

### Requirement: Masking of small cells
The system SHALL write every count under five, zero included, and every percentile over fewer than five epics as "masqué" in French and "masked" in English, and the report introduction SHALL state the threshold. When exactly one team cell of a column, or of a bucket row, is masked, it SHALL write the smallest other unmasked cell of that column or row the same way (design D10). The system SHALL NOT estimate a masked value.

#### Scenario: Small team cell
- **WHEN** the domain holds twenty epics in progress, team A twelve, team B six and team C two
- **THEN** the domain row reads 20, team A 12, and teams B and C both read "masked" in an English report

### Requirement: Structured cells in the JSON
The system SHALL write every JSON cell as an object with a value, null when not given, and a state among "ok", "lt5", "masked", "no_reference", "cycle_in_progress" and "not_computed" (design D10). The system SHALL NOT write in the JSON a value that the Markdown masks.

#### Scenario: Masked cells in the JSON
- **WHEN** team B's and team C's cells are both written "masked" in the Markdown of an English report
- **THEN** the JSON holds a null value with the state "masked" for B and "lt5" for C

#### Scenario: Percentile on few epics
- **WHEN** four epics of a team reached Ready in a cycle
- **THEN** the team's count, median and 85th percentile for that cycle read "masked" in an English report

### Requirement: Reduced report without a validated mapping
The system SHALL, when the mapping has no validation date, lacks the active columns, or lacks the Ready column while the Ready label is not configured, write "Discovery Workflow mapping not validated: columns, delays and ages not computed" and give only the passages, the carry-over and the count per Jira status of the pilot's epics (design D11). The system SHALL NOT compute idea to Ready, columns or ages then, and SHALL NOT change its exit code.

#### Scenario: Mapping without validation date
- **WHEN** the block holds columns, a Ready column and active columns but no validation date
- **THEN** the report holds the not-validated phrase, the passages, the carry-over and the counts per status, no duration and no age, and the exit code is 0

### Requirement: Epics stay out of the flow report
The system SHALL keep the portfolio exclusion of the flow report unchanged: with or without the transitions of epics stored, `compute` SHALL give the same Markdown and JSON reports, history, dormant tickets and coverage included (design D12). The system SHALL NOT count an epic in throughput, lead time, work in progress, ages, time per segment or coverage of the flow report.

#### Scenario: Epic history added
- **WHEN** the same tickets are computed with history and dormant tickets, once without and once with the transitions of their epics
- **THEN** both reports are byte-identical
