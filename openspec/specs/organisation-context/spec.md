# organisation-context Specification

## Purpose
TBD - created by archiving change organisation-context. Update Purpose after archive.

## Requirements

### Requirement: The context space lives outside every work tree
The system SHALL keep the organisation context in a context folder outside every Git work tree, with an originals folder and a notes folder, both owner-only, created only by the context tool's init after a confirmation (design D1). The context tool SHALL refuse, with exit code 2, a context folder inside a Git work tree or the workspace. The system SHALL NOT create, copy or track any part of the context folder inside a repository.

#### Scenario: Folder inside a work tree
- **WHEN** the context folder setting names a folder inside a Git work tree
- **THEN** the tool prints "context folder inside a Git work tree, refused", exits with code 2 and writes nothing

#### Scenario: Init
- **WHEN** init is confirmed on a missing context folder
- **THEN** the originals and notes folders exist and only their owner can read them

#### Scenario: Folder missing
- **WHEN** a subcommand other than init runs and the context folder does not exist
- **THEN** the tool prints "context folder not found: run init" and exits with code 6

### Requirement: The context folder moves once, with no link left
The context tool SHALL take the context folder from the lab-paths modules (design D16) and SHALL refuse to run, exit code 2, "former context folder still present: finish the move", while the former folder `Contexte-Lab` exists as a folder or a link. It SHALL test only that former root's existence, and SHALL NOT touch any path inside it, nor move, copy or link either folder: the move is the user's step.

#### Scenario: Former folder left beside the new one
- **WHEN** the fixture lab folder holds both `contexte` and `Contexte-Lab`
- **THEN** every subcommand prints "former context folder still present: finish the move", exits with code 2 and writes nothing

#### Scenario: Compatibility link
- **WHEN** `Contexte-Lab` is a symbolic link towards the new folder
- **THEN** the tool refuses the same way and no path behind the link is touched

### Requirement: No tool reads the originals
The system SHALL let only the user open the originals folder: the context tool, the indexer and the wake script SHALL NOT list, open, stat or test any path inside it, and SHALL NOT print anything taken from it. Tests: `tests/context_lab`, `tests/pmzilla_lab_library`, `tests/wake_postures`, with watchers on file access under the originals folder.

#### Scenario: Every subcommand under watch
- **WHEN** each context-tool subcommand, the indexer with the context option and the wake script run with watchers on the originals folder
- **THEN** no path under that folder is listed, opened, stat-ed or tested, and its sentinel string appears in no output

### Requirement: Every note carries a mandatory header
The system SHALL require of every note a header with a title, a date, a nature that is declarative or measured, a source and a review date later than the date, checked in the order of design D2, and SHALL refuse a note that breaks a rule with the key phrase of that rule. It SHALL NOT infer a missing field from the file name or the body.

#### Scenario: Missing nature
- **WHEN** a draft note has no nature field
- **THEN** add prints "header field missing: nature", exits with code 3 and writes nothing

#### Scenario: Review before the date
- **WHEN** the review date is on or before the note date
- **THEN** add prints "review date must be after the note date" and exits with code 3

#### Scenario: Unknown nature
- **WHEN** the nature is neither declarative nor measured
- **THEN** add prints "nature must be declarative or measured" and exits with code 3

### Requirement: The context tool writes one note, never overwriting
The system SHALL provide a context tool whose add subcommand reads a draft note on standard input, checks its header and its confidentiality, and writes it into the notes folder under its file name, printing "note written:" with that name. It SHALL refuse an existing name with exit code 4 and "note exists, not overwritten". It SHALL NOT write outside the notes folder, nor print a line of the body.

#### Scenario: New note
- **WHEN** a valid draft is piped to add
- **THEN** the note exists in the notes folder, the output says it is indexed at the next daily run, and no body line is printed

#### Scenario: Existing name
- **WHEN** a draft has the file name of an existing note
- **THEN** add exits with code 4 and the existing note is byte for byte unchanged

### Requirement: No personal identifier and no sensitive name in a note
The system SHALL refuse, with exit code 5, a note in which the personal-identifier scanner or the sensitive-names list matches, printing "personal identifier in line" or "sensitive name in line" with the line number only. It SHALL refuse every write with exit code 6 when the sensitive-names list is absent or empty. It SHALL NOT print the matched value, and the session SHALL NOT read the list.

#### Scenario: Name in a draft
- **WHEN** a draft holds a name of the fake sensitive-names list
- **THEN** add exits with code 5, names the line, and the output holds neither the name nor the line text

#### Scenario: List absent
- **WHEN** the sensitive-names list is absent
- **THEN** add prints "sensitive-names list unavailable: nothing written" and exits with code 6

### Requirement: Check and list print headers only
The system SHALL provide check and list subcommands that print, for each note, its file name, date, nature, review date and state ok, stale or invalid with the reason, then the counts of design D7. Check SHALL exit 0 when no note is invalid and 1 otherwise; a stale note SHALL NOT be an error. Neither SHALL print a body line.

#### Scenario: Stale note
- **WHEN** a note's review date is before today
- **THEN** check prints it as stale, counts it, and exits with code 0 if no note is invalid

#### Scenario: Invalid note
- **WHEN** a note edited by hand has lost its source field
- **THEN** check prints it as invalid with "header field missing: source" and exits with code 1

### Requirement: Updating a review date changes nothing else
The system SHALL provide a review subcommand that replaces the review date of one note by a given date later than the note date, after the confidentiality check. It SHALL NOT change any other byte of the note, and SHALL refuse an unknown note or an invalid date without writing.

#### Scenario: New review date
- **WHEN** review is given a note and a later date
- **THEN** the note differs from before only in its review value

### Requirement: The context command writes only a validated draft
The system SHALL provide a `/context` command that lists the notes through the list subcommand and, with `add`, drafts a note from the user's text, asks for each missing header field, shows the whole draft and pipes it to the add subcommand only after the user's explicit yes (design D8). It SHALL NOT read the originals or the notes folder, write a person's name or a figure of a cell under five, or run the indexer.

#### Scenario: Draft refused by the user
- **WHEN** the user does not validate the draft
- **THEN** no note is written and add is not run

#### Scenario: Command file
- **WHEN** the command file is read by the workflow command test
- **THEN** its header pre-approves only the list and check subcommands, and its body names no path of the originals or notes folders

### Requirement: At most one context map, by roles only
The system SHALL accept at most one note marked as the context map, holding the sections of design D9 by roles and generic designations. Check SHALL report a second map as invalid with "more than one context map". The confidentiality check SHALL apply to the map as to any note. The system SHALL NOT accept a map that names a person or a listed team.

#### Scenario: Second map
- **WHEN** two notes are marked as the map
- **THEN** check reports "more than one context map" and exits with code 1

### Requirement: The context map is the postures' starting context
The system SHALL make each posture's wake script print, after the out-of-library list, the map's date, nature, review date, a stale mark when due, and its body capped by the line limit of design D9 with "(map truncated)" when cut; "no context map" or "no context folder" otherwise. It SHALL NOT print any other note, and the wake script SHALL stay read-only and identical across postures.

#### Scenario: Map present
- **WHEN** a posture wakes with a valid map in the fixture context folder
- **THEN** the output holds the map section with its dates and body, and the file tree is unchanged

#### Scenario: Long map
- **WHEN** the map is longer than the line limit
- **THEN** the output stops at the limit and prints "(map truncated)"

#### Scenario: No map
- **WHEN** the notes folder holds no map
- **THEN** the output holds "no context map" and no note text

### Requirement: Private collections are listed once and kept off any sending
The system SHALL list the private collections, the context collection among them, in one code constant with a filter that removes them from a collection list, imported by every tool that names them. No tool SHALL send a passage, title or header of a private collection off the Mac. A test SHALL check the filter and that no tool file writes the context collection name as a literal.

#### Scenario: Filter
- **WHEN** the filter receives a list holding the context, watch and a domain collection
- **THEN** it returns the watch and domain collections only

#### Scenario: Literal name
- **WHEN** a tool file writes the context collection name instead of importing the constant
- **THEN** the test fails naming the file

### Requirement: A tripwire test guards the future server upload
The system SHALL include a test that fails, naming the file, when a tracked tool file both opens the library store and holds a network client, unless the file is in the test's allow-list with a reason and a test proves that it keeps the private collections off its sending (design D11). The allow-list SHALL hold the indexer for the local embedding service only. The test SHALL NOT be skipped when the database is absent.

#### Scenario: New upload tool
- **WHEN** a tool file that reads the library store and posts with an HTTP client is added without an allow-list entry
- **THEN** the test fails and names the file

#### Scenario: Indexer
- **WHEN** the test scans the tools folder of the current tree
- **THEN** only the indexer is found, its entry is accepted, and its loopback test exists

### Requirement: The session instructions replace the bridge
The system SHALL make the session instructions hold the organisation-context rule and the two citation formulas of design D13 in both languages, and SHALL make the neutral context templates hold no instruction to read the notes folder. It SHALL NOT keep a second route to the notes besides the library. The local context file is edited by the user; that edit is untested.

#### Scenario: Formulas present
- **WHEN** the vocabulary test reads the session instructions
- **THEN** the context note citation and the stale formula are present in the French and English columns

#### Scenario: Neutral templates
- **WHEN** the neutral context templates are read
- **THEN** neither names the notes folder nor tells to read it

### Requirement: The confidentiality check also matches the extract's team names
The system SHALL make the confidentiality check of the context tool, the indexer and the wake match the distinctive team names of the extract read locally, minus the generic-names list, and refuse with `extract team name in line <n>` (design D4). It SHALL NOT print the name found in any output, and an empty list SHALL stay unavailable even with a non-empty extract. Untested until implemented.

#### Scenario: Team name in a draft
- **WHEN** a draft holds a distinctive team name of the fake extract that the fake list does not hold
- **THEN** add exits with code 5, prints "extract team name in line" with the line, and the output holds no team name

#### Scenario: Fictitious name never printed
- **WHEN** a fictitious team name is planted in the fake extract, a note and the map, and the context tool, the indexer and the wake run
- **THEN** the name appears in none of their outputs

#### Scenario: Generic name
- **WHEN** a draft holds an extract name that the generic-names list holds
- **THEN** add writes the note

#### Scenario: Empty list, extract present
- **WHEN** the list is empty and the extract holds names
- **THEN** add prints "sensitive-names list unavailable: nothing written" and exits with code 6

### Requirement: The wake prints the map only after the confidentiality check
The system SHALL make the wake script apply the confidentiality check to the map and, on a finding or with the list unavailable, print "context map not shown:" with the reason instead of the map (design D5). It SHALL NOT print a body line of a refused map, and SHALL stay read-only. A clean map SHALL be printed as before. Untested until implemented.

#### Scenario: Name in the map
- **WHEN** a posture wakes with a map holding a name of the fake list on line 3 of the map file (header included)
- **THEN** the output holds "context map not shown: sensitive name in line 3" and no line of the map body

#### Scenario: Extract name in the map
- **WHEN** a posture wakes with a map holding a name of the fake extract on line 4 of the map file (header included)
- **THEN** the output holds "context map not shown: extract team name in line 4", no line of the map body and not the name

#### Scenario: List missing
- **WHEN** a posture wakes with the list absent
- **THEN** the output holds "context map not shown: sensitive-names list unavailable" and the file tree is unchanged
