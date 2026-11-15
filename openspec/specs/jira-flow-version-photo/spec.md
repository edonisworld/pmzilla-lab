# jira-flow-version-photo Specification

## Purpose
Describes the weekly quality photo by team and version (`tools/version_photo.py`): the reconstruction of past weeks, the Friday photo, the register of N weeks before release, and the photo store kept outside the one-year retention rule, with no count readable before N is adopted (change version-quality-photo, feature R-140). Sources are `tests/version_photo/` and `tests/db/test_flow_version_photo*.py`.

## Requirements

### Requirement: Reconstruction of past weeks
The system SHALL provide a `reconstruct` subcommand that writes one photo run of source "reconstructed" holding, for every week from the week of the oldest resolution among the stored tickets to the last completed one, the rows of design D6 per team and version and per team. It SHALL NOT write a key, a title or a person, nor a week already photographed live.
Source: untested until implemented

#### Scenario: First reconstruction
- **WHEN** `reconstruct` runs on a disposable database holding defects with versions over ten completed weeks
- **THEN** one run of source "reconstructed" holds rows for each of the ten weeks, the output holds "reconstruction: 10 weeks", and no version name is printed

### Requirement: Reconstruction runs once unless replaced
The system SHALL refuse a second `reconstruct` with exit code 3 and "reconstruction already done: use --replace", writing nothing. `reconstruct --replace` SHALL write a new reconstructed run of the weeks still recomputable, print the warnings of design D14, and keep the older run with its weeks and date until it is emptied. It SHALL NOT touch a live photo.

Source: untested until implemented

#### Scenario: Second run
- **WHEN** `reconstruct` runs after a successful reconstruction
- **THEN** the exit code is 3, the output holds "reconstruction already done: use --replace", and the store is unchanged

#### Scenario: Replacement keeps the live photos
- **WHEN** `reconstruct --replace` runs after a reconstruction and two live photos
- **THEN** the output starts with "warning: a reconstruction run again is more partial, the purge has moved on", the reconstructed weeks are rewritten, and the two live photos are unchanged

#### Scenario: Replacement keeps the weeks that can no longer be recomputed
- **WHEN** `reconstruct --replace` runs after a reconstruction whose oldest defects have since been purged, so that the weeks before the oldest remaining resolution can no longer be recomputed
- **THEN** a new run holds the weeks from the oldest remaining resolution, the older run keeps its older weeks, their rows and its date, and the second line of the output counts the weeks kept

### Requirement: Defects found and defects corrected never added
The system SHALL count apart, per team, version V and week, the defects found in V (current affects version containing V) and the defects corrected in V (fix version containing V, resolved), defect types from the setting of design D4. It SHALL NOT add the two counts in a row, a view or an output.

Source: untested until implemented

#### Scenario: Defect in both counts
- **WHEN** a defect created and resolved in week 3 carries V as affects version and as fix version
- **THEN** from week 3 it counts once in the defects found in V and once in the defects corrected in V, and no column holds their sum

### Requirement: Defects without affects version counted apart
The system SHALL count per team and week the defects created by the state instant that carry no affects version, and all defects created, on the version-free row. It SHALL NOT count a defect without affects version among the defects found in any version.

Source: untested until implemented

#### Scenario: Defect without affects version
- **WHEN** a defect created in week 2 has no affects version and the fix version V
- **THEN** from week 2 it counts in the defects without affects version of its team, in no defects found, and in the defects corrected in V once resolved

### Requirement: Fix version as known at the week and as known now
The system SHALL keep two counts of defects corrected in V: with V among the fix versions active at the state instant in the stored periods, and with V among the current fix versions. A live photo SHALL write the same value in both. It SHALL NOT infer a fix version found in neither.

Source: untested until implemented

#### Scenario: Fix version set late
- **WHEN** a defect resolved in week 2 got the fix version V in week 6
- **THEN** in weeks 2 to 5 it counts in "corrected now" only, and from week 6 in both counts

#### Scenario: History never collected
- **WHEN** a resolved defect carries the current fix version V and has no fix version period
- **THEN** it counts in "corrected now" only, and the output holds "defects without fix version history: 1"

### Requirement: Resolution instant read from the transition history
The system SHALL read the resolution instant of a defect, at each photo instant, from the last transition to a status classified done at or before it, and SHALL fall back on the resolution instant of the ticket when the history holds no such transition. It SHALL count a defect resolved once as corrected, whatever happens afterwards.

Source: untested until implemented

#### Scenario: Resolved, reopened, resolved again
- **WHEN** a defect is resolved in week 2, reopened in week 4 and resolved again in week 5
- **THEN** it counts as corrected in weeks 2 and 3, from week 4 on as reopened among the defects corrected at least once, and as resolved during weeks 2 and 5 in the throughput in correction

#### Scenario: History without any closure
- **WHEN** a resolved defect has no transition history, or a history with no transition to a status classified done
- **THEN** its resolution instant is the one of the ticket

#### Scenario: Same definition of closure for every type
- **WHEN** the transitions of tickets of every type, defects and other items, are loaded
- **THEN** one definition of closure applies to all types

### Requirement: Reopened defects
The system SHALL count per team, version and week the defects corrected in V that hold, by the state instant, a transition from a done status to a status not done (design D5), once each, transitions to the same status excluded. It SHALL count a reopened defect again among the open defects found from its reopening until it is resolved again (design D18-A, decision 6).

Source: untested until implemented

#### Scenario: Reopened then resolved again
- **WHEN** a defect corrected in V goes from a done status to an in-progress status in week 4 and is done again in week 5
- **THEN** it counts once as reopened from week 4 on, and in week 4 it counts again among the open defects found

### Requirement: Throughput in correction
The system SHALL count per team and week the items resolved during the week, portfolio types and tickets out of the export left out, and the defects among them. It SHALL NOT store a typed share: the share is computed in the view.

Source: untested until implemented

#### Scenario: Week with defects
- **WHEN** a team resolved 12 items in a week, 4 of them defects, and an epic
- **THEN** its version-free row of that week holds 12 resolved items and 4 resolved defects

### Requirement: Coverage of a reconstructed week
The system SHALL mark "partial" a reconstructed week that starts before the retention limit of the reconstruction day, and "complete" a later week and every live photo. It SHALL NOT mark complete a week whose tickets may be purged, nor complete it by estimate.

Source: untested until implemented

#### Scenario: Week before the limit
- **WHEN** the retention limit of the reconstruction day falls on the Monday of week 30 and the reconstruction starts at week 28
- **THEN** weeks 28 and 29 are marked partial, the following weeks complete, and the output counts 2 partial weeks

#### Scenario: Limit in the middle of a week
- **WHEN** the retention limit of the reconstruction day falls in the middle of week 30
- **THEN** week 30 is marked partial too, since its Monday precedes the limit, and the following weeks are complete

#### Scenario: Cumulative counts of every reconstructed week
- **WHEN** a reconstructed week is marked complete
- **THEN** its cumulative counts still miss the defects resolved before the retention limit, which the purge removed, and only the two throughput counts of the week are unaffected

### Requirement: Weekly photo taken by the author
The system SHALL provide a `take` subcommand that writes one photo run of source "live" for the current week, with the rows of design D6 computed at the run instant by the same week function as the reconstruction. It SHALL NOT print a version name, a key or a team.

Source: untested until implemented

#### Scenario: Friday photo
- **WHEN** `take` runs on a Friday with no photo of that week
- **THEN** one run of source "live" and coverage "complete" is written, and the output holds "photo taken: week of" followed by the Monday of the week

### Requirement: One live photo per week
The system SHALL refuse a second `take` of the same week with exit code 3 and "photo already taken for this week: use --replace", writing nothing. With `--replace` it SHALL replace the live photo of the current week only, never a past week or a reconstructed week.

Source: untested until implemented

#### Scenario: Second photo of the week
- **WHEN** `take` runs twice in the same week without `--replace`
- **THEN** the second run exits with code 3, prints the key phrase, and the first photo is unchanged

#### Scenario: Replacement
- **WHEN** `take --replace` runs in a week that already has a live photo
- **THEN** that photo is replaced by the new one, and the photos of the past weeks are unchanged

### Requirement: Defect types required
The system SHALL refuse `reconstruct` and `take` with exit code 3 and "defect types not set" when the setting listing the defect types is absent or empty, before writing anything. It SHALL NOT fall back to a built-in type name.

Source: untested until implemented

#### Scenario: Setting absent
- **WHEN** `take` runs with settings that list no defect type
- **THEN** the exit code is 3, the output holds "defect types not set", and nothing is written

### Requirement: Photo tool refused inside a session
The system SHALL refuse every subcommand of the photo tool, with exit code 3 and "Refused inside a Claude Code session", when the variable that Claude Code sets in its shells is present, before reading any setting or connecting. It SHALL NOT offer an option that bypasses that refusal.

Source: untested until implemented

#### Scenario: Started from a session
- **WHEN** the variable is present and `take` or `adopt-n` is run
- **THEN** the exit code is 3, the output holds the key phrase, and no setting is read and no connection opened

### Requirement: Photo tool output and language
The system SHALL print in French by default and in English with `--language en` the key phrases of design D14, only counts and week dates besides them, and on a database error its type alone with exit code 1. It SHALL NOT print a version name, a key, a team or a setting value.

Source: untested until implemented

#### Scenario: Distinctive names absent
- **WHEN** the fixtures hold a distinctive string in every key, team and version name, and `reconstruct` then `take` run in each language
- **THEN** none of them appears in any output

### Requirement: Versions identified by an opaque number
The system SHALL give each version name met an opaque number, kept in a register with the name, a release date and a released flag filled from the current versions of the tickets still in the export, last known values kept (design D5), and SHALL write that number in the photo rows. It SHALL NOT expose the name to a views role, nor estimate a release date.

Source: untested until implemented

#### Scenario: Same version in two runs
- **WHEN** a version appears in the reconstruction and in a later live photo
- **THEN** both runs carry the same version number

### Requirement: N adopted with a trace
The system SHALL provide `adopt-n --weeks N --adopted-on DATE`, which adds one row to the register of N and prints "N adopted: {n} weeks, on {date}". The effective N SHALL be the latest adoption. It SHALL NOT update or delete an adoption, nor accept N that is not a positive whole number (exit code 2).

Source: untested until implemented

#### Scenario: N changed later
- **WHEN** N is adopted at 6 weeks, then at 8 weeks with a reason on a later date
- **THEN** the register holds both rows with their dates, and the effective N is 8

### Requirement: Adoption of N waits for the masking of team and version crossings
The system SHALL refuse `adopt-n` with exit code 3 and a message naming the reason (team x version crossings not yet masked, feature R-144), in French and in English, writing nothing, while no applied migration name contains `masquage_somme`, and SHALL accept it afterwards. It SHALL NOT touch `reconstruct` and `take` (design D18, decision 2).

Source: untested until implemented

#### Scenario: Migration of R-144 absent
- **WHEN** `adopt-n --weeks 6 --adopted-on 2026-11-20` runs and no applied migration name contains `masquage_somme`
- **THEN** the exit code is 3, the output names the reason and R-144, and the register of N is unchanged

#### Scenario: Migration of R-144 applied
- **WHEN** the same command runs and an applied migration name contains `masquage_somme`
- **THEN** the adoption is written and the output holds "N adopted: 6 weeks, on 2026-11-20"

### Requirement: Later adoption of N needs a reason
When an adoption already exists, `adopt-n` SHALL refuse without `--reason` with exit code 3 and "N already adopted: give --reason", writing nothing; with it, it SHALL print "warning: N modified after a first adoption, shown in the view", then store the reason. It SHALL NOT print or expose the reason.

Source: untested until implemented

#### Scenario: Second adoption without reason
- **WHEN** N was adopted once and `adopt-n --weeks 8` runs without `--reason`
- **THEN** the exit code is 3, the output holds the refusal, and the register still holds one adoption

#### Scenario: Second adoption with reason
- **WHEN** the same command runs with `--reason`
- **THEN** the output holds the warning then "N adopted: 8 weeks", and the reason appears in no output

### Requirement: Release attributes copied into the register
At each `reconstruct` and `take`, the system SHALL write into the register the release date and released flag carried by the tickets still in the export (not those with `out_of_export_at` set), null included, and keep the last known values of a version no such ticket carries. It SHALL NOT derive a date from the history or the photos, nor write on a refused run.

Source: untested until implemented

#### Scenario: Release date set in Jira
- **WHEN** an export and an import bring a release date to a version, then `take` runs
- **THEN** the register holds that date and flag for the version

#### Scenario: Version purged
- **WHEN** the tickets carrying a version are purged, then `take` runs
- **THEN** the register keeps the last date and flag of that version

#### Scenario: Release postponed
- **WHEN** an old ticket out of the export carries the old date of a version and the tickets of the export carry a new date, then `take` runs
- **THEN** the register holds the new date and no conflict is declared

#### Scenario: Every ticket left the export
- **WHEN** every ticket carrying a version has left the export, then `take` runs
- **THEN** the register keeps the last known date and flag of that version

### Requirement: Register numbers without gap
The system SHALL write the register by updating the names already known, then inserting only the new names the photo has not numbered yet, in the order of the names, so that a run consumes no number for a name already known. A run that fails after inserting a new name may leave a gap (design D5).

Source: untested until implemented

#### Scenario: Two takes without a new version
- **WHEN** `take` runs twice with no new version name, then a new name appears and `take` runs
- **THEN** no number is consumed for the known name and the new name takes the next number

### Requirement: Conflicting release attributes
When the stored current versions of tickets still in the export carry different release dates or flags for one version name, the system SHALL write null for each differing attribute and print "versions with conflicting release attributes: {n}" after each `reconstruct` and `take`, even at 0. It SHALL NOT choose one of the values.

Source: untested until implemented

#### Scenario: Same name, two dates
- **WHEN** two stored tickets carry the same version name with two different release dates, then `take` runs
- **THEN** the register date of that version is null and the output holds "versions with conflicting release attributes: 1"

### Requirement: Versions without release date reported
The system SHALL print after each `reconstruct` and `take` "versions without release date: {n}", the register versions whose date is null after the run; such a version SHALL have no retained week in the view. It SHALL NOT print a version name, number, date or flag.

Source: untested until implemented

#### Scenario: Version without date in Jira
- **WHEN** a version carries no release date in Jira and N is adopted, then `take` runs
- **THEN** the output holds "versions without release date: 1", and the view returns coverage rows only for that version

#### Scenario: Distinctive date absent
- **WHEN** the register receives a distinctive release date and `take` runs in each language
- **THEN** the date appears in no output line
