# story-quality-collect Specification

## Purpose
Collection of the title, description and acceptance criteria of Jira stories and epics into the local `quality` schema, by the author alone: authorised fields only, never a person field, mentions, e-mail addresses, sensitive names and media replaced before storage, one transaction, retention applied at collection. Created by the change story-quality-audit (feature R-94).

## Requirements

### Requirement: Collection requests only the authorised fields
The system SHALL provide a user-run `collect` subcommand of the story quality tool. It SHALL request only the title, the description, the configured acceptance-criteria field, the issue type, the status, the team field, the parent, created, updated and resolution date. Untested until implemented.

#### Scenario: Field list
- **WHEN** `collect` runs against the fake Jira server
- **THEN** the requested field list holds exactly the authorised fields

### Requirement: The single-PO flag is copied from the referential
The system SHALL copy, for each team, the optional single-PO flag of the organisation referential into the team attributes of the `quality` schema. It SHALL copy no other referential value and no data about a person. Untested until implemented.

#### Scenario: Flag copied
- **WHEN** the fake referential flags one of two teams as single-PO
- **THEN** only that team's attributes carry the flag, and no headcount, site or other referential value is stored

### Requirement: Collection never requests person or side data
The system SHALL NOT request an assignee, a reporter, a creator, watchers, votes, comments, attachments, worklog, changelog, or any user-type field, the PO in charge included, whatever the settings. Untested until implemented.

#### Scenario: Field list with every setting
- **WHEN** `collect` runs against the fake Jira server with every supported setting present
- **THEN** the requested field list holds none of the person, comment, attachment, worklog or changelog fields

### Requirement: Only stories and epics are collected
The system SHALL store only the items whose issue type is mapped to story or epic in the settings, and SHALL NOT store an item of another issue type. Untested until implemented.

#### Scenario: Other issue type
- **WHEN** the query returns a bug among stories
- **THEN** the bug is not stored

### Requirement: A person field in the settings is refused before any read
The system SHALL check the configured field identifiers against the Jira field list. When one of them is a user or user-list field, it SHALL stop with exit code 3 and the person-field key phrase of design D14, naming the settings key and never its value, before reading any ticket. It SHALL NOT offer an option that bypasses this check. Untested until implemented.

#### Scenario: Acceptance-criteria field set to a user field
- **WHEN** the acceptance-criteria setting names a user-type field
- **THEN** the output holds "person field refused in the story quality settings:" followed by the settings key, no ticket is requested, and the exit code is 3

### Requirement: Mentions and listed names are replaced before storage
The system SHALL rewrite the title, the description and the acceptance criteria before storing them. Every rich-text mention and wiki-style user link SHALL become `[person]`, with no account identifier kept. Every entry of the sensitive-names list, matched case-insensitively on word boundaries, SHALL become `[name]`. Untested until implemented.

#### Scenario: Mention and listed name
- **WHEN** a description holds a mention of an invented account and an invented name present in the fake sensitive-names list
- **THEN** the stored description holds `[person]` and `[name]`, and contains neither the account identifier nor the name

### Requirement: E-mail addresses and media are replaced before storage
The system SHALL replace every e-mail address with `[email]` and every inline image, media or attachment link with `[media]` before storage. Untested until implemented.

#### Scenario: E-mail address
- **WHEN** an acceptance criterion holds an e-mail address
- **THEN** the stored text holds `[email]` in its place

### Requirement: Replaced values are never shown
The system SHALL print only the number of replacements of a run. It SHALL NOT store, print or log a replaced value. Untested until implemented.

#### Scenario: Output of a run with replacements
- **WHEN** a run replaces three mentions
- **THEN** the output holds "story content collected: 1 items, 3 replacements" and none of the replaced values

### Requirement: Collection writes only to the database, in one transaction
The system SHALL write the collected items, their teams and their scrubbed texts straight into the `quality` schema, in one transaction per run. A new collection SHALL replace an item's stored text and reset its collection instant, keeping no former version. It SHALL NOT write the text to a file, a cache, a log or the console. On a database error it SHALL roll back, print the error type alone and exit with code 1. Untested until implemented.

#### Scenario: No file
- **WHEN** `collect` succeeds in a temporary home folder
- **THEN** no new file holding a fixture sentinel string exists anywhere under that folder

#### Scenario: Database failure
- **WHEN** the database raises an error during the write
- **THEN** no row of the run remains, the error type alone is printed, and the exit code is 1

### Requirement: Retention is applied at collection
The system SHALL skip the items resolved longer ago than the retention period and print the past-retention key phrase of design D14 with their count. When it runs every named query of the block, it SHALL mark as out of collection the stored items it no longer sees and clear the mark of those that return. A run limited to one query SHALL NOT set a mark. Untested until implemented.

#### Scenario: Old resolved story
- **WHEN** the query returns a story resolved before the retention period
- **THEN** it is not stored and the output holds "items past retention, skipped: 1"

#### Scenario: One query only
- **WHEN** `collect --query <name>` runs and a stored item of another query is absent
- **THEN** that item is not marked

### Requirement: Collection output and session refusal
The system SHALL print in French by default and in English with `--language en`, and SHALL refuse another language with exit code 2. It SHALL print only counts and the key phrases of design D14. It SHALL refuse to start, with exit code 3 and the session key phrase, when the variable that Claude Code sets in its shells is present, before reading any setting. It SHALL NOT print a ticket key, a team, a title, a text, a field value or the token. Untested until implemented.

#### Scenario: Started from a session
- **WHEN** the Claude Code variable is present
- **THEN** the output holds "Refused inside a Claude Code session", nothing is read, and the exit code is 3

#### Scenario: Distinctive strings absent
- **WHEN** the fixtures hold a distinctive string in every key, team, title, description and acceptance criterion
- **THEN** none of them appears in the output of `collect`
