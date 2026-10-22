# jira-flow-labels Specification

## Purpose
Describes the declared Jira labels and fix versions: how they are declared in the flow settings, kept by the export, the history collection and the import (never the undeclared ones), counted without being printed, and used by the cycles report for up-merge and Epic Review figures. Sources are the export, history, import, settings and cycles tests cited per requirement.

## Requirements

### Requirement: Declared labels in the flow settings
The system SHALL read the declared labels from the `declared_labels` block of the flow settings, organised by role (`up_merge`, `cycle`, `epic_review`, `pilot_domain`, `ready`, `confirmation`), each role giving a prefix and its declared labels, every declared label starting with its role's prefix; the up-merge role SHALL declare exactly the legal and the hotfix label; the `pilot_domain` role SHALL declare exactly one label; the `ready` role SHALL declare at most one label, an empty or absent value being read as not configured without message; each confirmation label SHALL declare its meaning, taken in or not taken in; each cycle label MAY name the cycle key of the `cycles` block that it plans (design D4b of the epic flow report change). The block SHALL be read with the strict loader; an unknown role, a label outside its prefix, a label declared twice, an up-merge role without both labels, a `pilot_domain` role without exactly one label, a `ready` role with more than one label, a confirmation label without its meaning or a cycle key that the `cycles` block does not declare SHALL stop the reading tool with exit code 1, naming the key path and line, never a value. Without the block, the system SHALL read and store no label. The system SHALL NOT deduce a cycle key from the text of a label.

Source: tests/flux_config/test_nouveaux_blocs.py (TestEtiquettesDeclarees); tests/export_jira_api/test_referentiel_et_etiquettes.py (test_sans_bloc_aucune_colonne_d_etiquette_meme_si_le_ticket_en_porte). New roles untested until implemented.

#### Scenario: Label outside its prefix
- **WHEN** a cycle label does not start with the cycle prefix
- **THEN** the tool stops with exit code 1, names the key path and line, and does not echo the label

#### Scenario: No block
- **WHEN** the settings have no declared-labels block
- **THEN** the export requests no label and writes no declared-label column

#### Scenario: Ready label not chosen yet
- **WHEN** the `ready` role holds an empty value
- **THEN** the block is read without message and the Ready label is not configured

#### Scenario: Two domain labels
- **WHEN** the `pilot_domain` role declares two labels
- **THEN** the tool stops with exit code 1, names the key path and line, and echoes neither label

#### Scenario: Unknown cycle key
- **WHEN** a cycle label names a cycle key that the `cycles` block does not declare
- **THEN** the tool stops with exit code 1, names the key path and line, and echoes neither the label nor the key

### Requirement: Only declared labels are stored
The system SHALL keep, from the labels of a ticket read through the API, only the declared ones: the export SHALL NOT request the labels field (design D5 of the database-only change), the history collection SHALL keep only the add and remove events and the current values of declared labels, and SHALL store only periods of declared labels. Undeclared labels SHALL be discarded in memory after counting. The system SHALL NOT write all the labels of a ticket to a file or the database, and SHALL NOT print a label.

Source: tests/export_jira_api/test_export_jira_api.py (NouveauxComportements.test_champs_demandes_sans_etiquette_ni_version); tests/history_jira/test_collecte_etendue.py; tests/history_jira/test_magasin_base.py (skipped without the disposable database)

#### Scenario: Mixed labels
- **WHEN** a ticket carries one declared cycle label and two undeclared labels
- **THEN** the export requests no label, the history collection stores a period for the declared label alone, and neither the database nor the console holds the two others

#### Scenario: Cache events
- **WHEN** the changelog adds an undeclared label and removes a declared one
- **THEN** the stored periods reflect only the removal of the declared label, with its instant

### Requirement: Look-alike labels counted, never listed
The system SHALL count, at export, the distinct undeclared labels that start with a declared prefix and the tickets carrying them, and print the look-alike key phrase of design D19 with the count. It SHALL NOT print, write or store those labels.

Source: tests/export_jira_api/test_referentiel_et_etiquettes.py (EtiquettesProches)

#### Scenario: Renamed label in the application
- **WHEN** a ticket carries a label that starts with the cycle prefix but is not declared
- **THEN** the console prints "undeclared labels with a declared prefix: 1" and no label text

### Requirement: Jira labels only
The system SHALL read labels only from Jira issues through the Jira API and SHALL NOT call a Confluence API or read a Confluence page. Every report section built on labels SHALL name them "Jira labels" in English and "étiquettes Jira" in French. The system SHALL stay read-only towards Jira: it SHALL NOT add, remove or rename a label or a fix version.

Source: tests/export_jira_api/test_referentiel_et_etiquettes.py (JiraSeulement); tests/flux_jira/test_cycles_commande.py (Etiquettes)

#### Scenario: Calls recorded
- **WHEN** an export and a history collection run against the fake server
- **THEN** every recorded call is a read of the Jira API, none targets a Confluence path, and none is a write method

#### Scenario: Report wording
- **WHEN** the cycles report is written in English
- **THEN** its label section is titled with "Jira labels"

### Requirement: Fix versions stored with their periods
The system SHALL read, in the history collection, the add and remove events and the current fix versions of each ticket it queries, and store in the database the version periods of each ticket; the export SHALL NOT request the fix versions (design D5 of the database-only change). The system SHALL NOT print a version name and SHALL NOT write a version name in a report: reports use the cycle key of the jira-flow-cycles capability.

Source: tests/history_jira/test_collecte_etendue.py; tests/history_jira/test_magasin_base.py (skipped without the disposable database)

#### Scenario: Version moved
- **WHEN** a ticket's fix version is changed from one version to another
- **THEN** the database holds a closed period for the first and an open period for the second, and the console shows counts only

### Requirement: Exactly one up-merge label
The system SHALL count the tickets that carry both declared up-merge labels at the same time, at export (current labels) and in the cycles report (per cycle), and print the two-labels key phrase of design D19 with the count. It SHALL NOT list the tickets, SHALL NOT pick one of the two labels for them, and SHALL leave them out of the up-merge share with the count stated.

Source: tests/export_jira_api/test_referentiel_et_etiquettes.py; tests/flux_jira/test_cycles_*.py

#### Scenario: Two labels
- **WHEN** one ticket carries the legal and the hotfix up-merge labels
- **THEN** the console prints "up-merge items with two labels: 1" and no key, and the cycles report counts it apart

### Requirement: Epic Review submissions, passes and rejections
The system SHALL compute in the cycles report, per cycle, from the declared Epic Review label periods of epics, in the convention of design D6 (label removed on pass and on rejection): the number of submissions, each add of the label counting one submission. Only when the Discovery Workflow mapping is validated, it SHALL classify each removal by the status the epic holds at the end of the removal day, the day and its end being read in the export time zone (the configured zone of the jira-flow-export capability), never in UTC: a pass when that status maps to a review-passed column of the mapping, a rejection when it maps to another column, and "status not mapped" when it maps to no column. Without a validated mapping, the section SHALL give the submissions only, with the not-validated key phrase of design D19, and SHALL compute neither passes nor rejections. The section labels SHALL be those of design D19. The system SHALL NOT count a removal as a pass by itself, SHALL NOT infer a pass or a rejection from anything other than the epic's status, and SHALL NOT name an epic, a team or a person in that section.

Source: tests/flux_jira/test_cycles_calcul.py (EpicReview)

#### Scenario: Mapping not validated
- **WHEN** the settings hold a mapping without a validation date and three adds and two removals fall in a cycle
- **THEN** the section gives three submissions, holds "Discovery Workflow mapping not validated: submissions only", and gives no pass and no rejection count

#### Scenario: Pass and rejection
- **WHEN** the mapping is validated, one removal is followed the same day by a status of a review-passed column and another by a status of another column
- **THEN** the section counts one pass and one rejection

#### Scenario: Status not mapped
- **WHEN** the mapping is validated and the epic's status at the end of the removal day is in no column
- **THEN** that removal is counted under "status not mapped", neither as a pass nor as a rejection

#### Scenario: Removal day in the export time zone
- **WHEN** the mapping is validated, the export time zone is two hours ahead of UTC, the label is removed at 20:00 local time, the epic moves to a review-passed column at 21:00 local time, then to another mapped column at 01:00 local time the next day (23:00 UTC on the removal day)
- **THEN** the status read at the end of the local removal day is the review-passed one and the removal is counted as a pass, not as the rejection a UTC reading would give

### Requirement: Delay to Epic Review
The system SHALL compute in the cycles report the delay to Epic Review, from the start point of design D6 (first entry into the start column of the validated mapping) to the first add of the Epic Review label, only when the Discovery Workflow mapping is validated. Without a validated mapping it SHALL NOT compute the delay and SHALL NOT take the epic creation or the cycle label as a substitute start.

Source: tests/flux_jira/test_cycles_calcul.py (EpicReview: test_delai_*)

#### Scenario: Mapping validated
- **WHEN** the mapping is validated and an epic entered the start column ten days before its first add
- **THEN** the delay distribution includes ten days

#### Scenario: Mapping not validated
- **WHEN** the mapping has no validation date
- **THEN** no delay is written
