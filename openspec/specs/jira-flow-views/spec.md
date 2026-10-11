# jira-flow-views Specification

## Purpose

Describes the aggregated-views reader, the only route the assistant has to Jira data in the database: it shows four aggregated views by team with small cells masked. Sources are `tests/flow_views/test_flow_views.py`.

## Requirements

### Requirement: Closed list of views
The system SHALL offer `list` (the available views with their description and the current masking threshold) and `show <view>`, and SHALL accept only the four known views (team status, weekly resolved per team, open age per team, dependencies per team). Any other name (a table name, injection text or empty) SHALL be refused before any database connection, with exit code 1 and an "unknown view" message, and the reader SHALL raise an error for it.

Source: tests/flow_views/test_flow_views.py (test_vue_inconnue_refusee_avant_toute_connexion, test_liste_des_vues, test_les_quatre_vues_sont_celles_de_la_migration)

#### Scenario: Unknown view
- **WHEN** `show issues` is run
- **THEN** exit code 1, "unknown view" on stderr, and no connection is opened

#### Scenario: Listing
- **WHEN** `list` is run
- **THEN** every known view appears and the exit code is 0

### Requirement: Dedicated view role
The system SHALL connect only under the views role, whose rights are limited to the views, SHALL print the database error with exit code 1 when unreachable, and SHALL NOT be able to read the ticket table through that role.

Source: tests/flow_views/test_flow_views.py (test_connexion_sous_le_seul_role_des_vues, test_le_chemin_de_lecture_ne_permet_pas_de_lire_une_table)

#### Scenario: Unreachable database
- **WHEN** the connection fails
- **THEN** the error message is shown and the exit code is 1

#### Scenario: Table access
- **WHEN** a direct query of the ticket table is tried under the role
- **THEN** the database refuses for insufficient privilege

### Requirement: Small-cell masking
The system SHALL mask count cells (tickets and links) smaller than the threshold as "<N" (a missing value is masked too), show larger values unchanged, never print a ticket key, and print a "no rows" text for an empty view. The effective threshold SHALL never be below five: it is the highest of the floor, the settings value (a lower or unreadable setting falls back to the floor, an unreadable one with a warning on stderr; absent file gives the floor) and the optional `--min-cell` value, and a `--min-cell` below the floor SHALL print a notice that the floor is applied. Only count columns SHALL be masked.

Source: tests/flow_views/test_flow_views.py

#### Scenario: Threshold never lowered
- **WHEN** the setting is 2 or the option is 1
- **THEN** the effective threshold is 5

#### Scenario: Raised threshold
- **WHEN** `--min-cell 20` is given
- **THEN** a cell of 12 tickets displays as "<20"

#### Scenario: End to end
- **WHEN** a view has a team with 12 tickets and a team with 2
- **THEN** the first shows 12 and the second "<5", and no ticket key appears

### Requirement: Read only
The system SHALL write nothing and SHALL display tables sorted by their values with aligned columns and a separator line.

Source: tools/flow_views.py (rendre, main); tests/flow_views/test_flow_views.py (test_masquage_et_rendu)

#### Scenario: Rendering
- **WHEN** a table with masked cells is rendered
- **THEN** columns are aligned and masked cells appear as "<N"

### Requirement: Message language
The system SHALL accept the `--language fr|en` option, print its messages in French by default and in English with `--language en`: the listing header and view descriptions, the unknown-view message (which lists the available views), the database error, the notice that the threshold is raised to the floor, and the "no rows" text. The masking marker ("<N") SHALL NOT change with the language. An English run SHALL NOT print the French messages.

Source: tests/flow_views/test_langue.py

#### Scenario: English messages
- **WHEN** `list` runs with `--language en`
- **THEN** the descriptions and notices are printed in English, every known view is listed, and the French header does not appear

#### Scenario: Unknown view in English
- **WHEN** `show issues` runs with `--language en`
- **THEN** the exit code is 1, stderr names the unknown view and the available views in English, and no connection is opened

#### Scenario: French by default
- **WHEN** no language is given
- **THEN** the unknown-view message, the database error and the threshold notice are in French
