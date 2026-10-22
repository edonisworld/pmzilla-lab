# jira-flow-views Specification

## Purpose

Describes the aggregated-views reader, the only route the assistant has to Jira data in the database: it shows nine aggregated views (four flow views by team, two team-name views, three story quality views) with small count cells masked. Sources are `tests/flow_views/test_flow_views.py` and `tests/flow_views/test_langue.py`.

## Requirements

### Requirement: Closed list of views
The system SHALL offer `list` (the available views with their description, the current masking threshold and the masking marker) and `show <view>`. The title of `list` giving the configured threshold and the masking marker is untested (suite tests/flow_views).

Source: tests/flow_views/test_flow_views.py (test_liste_des_vues, VuesDeQualite, VuesDesNomsDEquipe)

#### Scenario: Listing
- **WHEN** `list` is run, in French or in English
- **THEN** every known view appears, the three quality views and the two team-name views included with a description in that language, and the exit code is 0

### Requirement: Nine known views
The system SHALL accept only nine known views:
- the four flow views: team status, weekly resolved per team, open age per team, dependencies per team;
- the two team-name views: teams known to the database, Jira team identifiers seen on tickets by team name;
- the three story quality views: results by team, coverage by team, results for the product.

Source: tests/flow_views/test_flow_views.py (test_les_quatre_vues_sont_celles_de_la_migration, VuesDeQualite, VuesDesNomsDEquipe)

#### Scenario: Views of the migrations
- **WHEN** the known views are compared with the migrations
- **THEN** the four flow views are those of the flow migration, the two team-name views those of migration `0014` and the three quality views those of the quality migration

### Requirement: Unknown view refused
Any other name (a table name of either schema, a schema-qualified name, a name in another case, injection text or empty) SHALL be refused before any database connection, with exit code 1 and an "unknown view" message, and the reader SHALL raise an error for it.

Source: tests/flow_views/test_flow_views.py (test_vue_inconnue_refusee_avant_toute_connexion, VuesDeQualite)

#### Scenario: Unknown view
- **WHEN** `show issues` or `show teams` is run
- **THEN** exit code 1, "unknown view" on stderr, and no connection is opened

#### Scenario: Quality table name refused
- **WHEN** `show contents`, `show quality.quality_by_team` or a quality view name in upper case is run
- **THEN** exit code 1, "unknown view" on stderr, and no connection is opened

### Requirement: Listing language and structured cells
The listing SHALL describe the quality views and the team-name views in the message language. Count columns SHALL be returned by a service function as structured cells, a masked cell carrying its reason and threshold, and `show` SHALL only format them; the Jira team identifier and the team type SHALL never be masked.

Source: tests/flow_views/test_flow_views.py (VuesDeQualite, VuesDesNomsDEquipe); tests/flow_views/test_langue.py (test_liste_des_vues_dans_chaque_langue)

#### Scenario: Structured masked cell
- **WHEN** a count of 3 is read from a team-name view with the threshold at 5
- **THEN** the service function returns the cell with no value, the reason "under_threshold" and the threshold 5, and `show` prints it as "masqué" ("masked" in English) while the Jira team identifier of the same row is printed as stored

### Requirement: Dedicated view role
The system SHALL connect only under a views role whose rights are limited to views: the flow views role for the flow and team-name views, in the flow schema, and the quality views role for the quality views, in the quality schema.

Source: tests/flow_views/test_flow_views.py (test_connexion_sous_le_seul_role_des_vues, VuesDeQualite, VuesDesNomsDEquipe, AvecBase)

#### Scenario: Role per view
- **WHEN** each of the nine views is read
- **THEN** the four flow views and the two team-name views are read under the flow views role in the flow schema, and the three quality views under the quality views role in the quality schema

### Requirement: Unreachable database reported
The system SHALL print the database error with exit code 1 when the database is unreachable.

Source: tests/flow_views/test_flow_views.py (test_connexion_sous_le_seul_role_des_vues); tests/flow_views/test_langue.py (test_erreur_de_base_dans_chaque_langue)

#### Scenario: Unreachable database
- **WHEN** the connection fails
- **THEN** the error message is shown and the exit code is 1

### Requirement: Views roles read no table
Through these roles the system SHALL NOT be able to read the ticket table, nor any table of the `quality` schema. The count columns of the quality views SHALL be masked like the flow counts, and the single-PO flag SHALL never be masked.

Source: tests/flow_views/test_flow_views.py (test_le_chemin_de_lecture_ne_permet_pas_de_lire_une_table, VuesDeQualite, AvecBase.test_le_role_des_vues_de_qualite_lit_les_vues_et_aucune_table)

#### Scenario: Table access
- **WHEN** a direct query of the ticket table is tried under the role
- **THEN** the database refuses for insufficient privilege

#### Scenario: Quality table access
- **WHEN** a direct query of the quality contents or items table, or of the ticket table, is tried under the quality views role
- **THEN** the database refuses for insufficient privilege

#### Scenario: Masked quality counts
- **WHEN** a coverage row holds counts under the threshold and a single-PO flag
- **THEN** the counts are shown as "masqué" ("masked" in English) and the flag is shown as it is

### Requirement: Small-cell masking
The system SHALL write a count cell (tickets, links and the quality counts) smaller than the threshold as "masqué" in French and "masked" in English, show larger values unchanged, never print a ticket key, and print a "no rows" text for an empty view. Only count columns SHALL be masked.

#### Scenario: End to end
- **WHEN** a view has a team with 12 tickets and a team with 2
- **THEN** the first shows 12 and the second "masqué", and no ticket key appears

Source: tests/flow_views/test_flow_views.py (SansBase, SurvivantsDeMutation, AvecBase.test_lecture_et_masquage_de_bout_en_bout); tests/flow_views/test_langue.py (test_seuil_releve_rappele_dans_chaque_langue)

### Requirement: Missing value masked
The system SHALL mask a missing value with the same marker, so a count the view itself masked, including by its complementary masking, is shown like a count under the threshold: a masked cell can hide a count of five or more, and nothing SHALL say which.

#### Scenario: Missing value
- **WHEN** a count column holds no value
- **THEN** the cell is shown as "masqué" ("masked" in English), like a count under the threshold

Source: tests/flow_views/test_flow_views.py (test_masquage_et_rendu; cellule on a null count)

### Requirement: Effective threshold
The effective threshold SHALL never be below five: it is the highest of the floor, the settings value (a lower or unreadable setting falls back to the floor, an unreadable one with a warning on stderr; absent file gives the floor) and the optional `--min-cell` value, and a `--min-cell` below the floor SHALL print a notice that the floor is applied.

#### Scenario: Threshold never lowered
- **WHEN** the setting is 2 or the option is 1
- **THEN** the effective threshold is 5

Source: tests/flow_views/test_flow_views.py (SansBase, SurvivantsDeMutation); tests/flow_views/test_langue.py (test_seuil_releve_sous_le_plancher_dans_chaque_langue)

### Requirement: Settings under the content root
The settings value SHALL be read from `Flux-Lab/flux.yaml` under the content root resolved by the shared path module, never under the code root; when that root cannot be found, the run SHALL stop with the shared message and exit code 78, never falling back to the floor.

#### Scenario: Setting under the content root
- **WHEN** the content root holds `Flux-Lab/flux.yaml` with a threshold of 9 and the code root holds none
- **THEN** the configured threshold is 9

#### Scenario: Content root missing
- **WHEN** the content root points to a missing folder
- **THEN** the run stops with exit code 78 instead of using the floor

Source: tests/flow_views/test_flow_views.py (SansBase, SurvivantsDeMutation)

### Requirement: Raised threshold reminder
When the effective threshold is above five, `show` SHALL recall it once on stderr with the marker; at the floor it SHALL print no reminder.

#### Scenario: Raised threshold
- **WHEN** `--min-cell 20` is given
- **THEN** a cell of 12 tickets displays as "masqué", and stderr recalls once that the threshold is 20 tickets

#### Scenario: Floor without reminder
- **WHEN** `show` runs without the option and with a readable setting, so the threshold is at the floor
- **THEN** nothing is printed on stderr

Source: tests/flow_views/test_flow_views.py (SansBase, SurvivantsDeMutation); tests/flow_views/test_langue.py (test_seuil_releve_rappele_dans_chaque_langue)

### Requirement: Read only
The system SHALL write nothing and SHALL display tables with aligned columns and a separator line. The rows of the flow and team-name views SHALL be sorted by their values. The rows of the three story quality views SHALL come in the order of team, item kind and criterion code (the product view, which has no team column: item kind and criterion code), never in the order of a count, whatever the counts (design D15 of change story-quality-audit, M3 (a)).

#### Scenario: Rendering
- **WHEN** a table with masked cells is rendered
- **THEN** columns are aligned and masked cells appear as "masqué" ("masked" in English)

#### Scenario: Quality view order
- **WHEN** `show quality_by_team` runs on a fixture whose counts would reverse the order if the rows were sorted by a count
- **THEN** the rows come in the order of team, item kind and criterion code

#### Scenario: Product view order
- **WHEN** `show quality_by_product` runs on the same kind of fixture
- **THEN** the rows come in the order of item kind and criterion code

Source: tools/flow_views.py (rendre, main); tests/flow_views/test_flow_views.py (test_masquage_et_rendu; VuesDeQualite: test_les_lignes_des_vues_de_qualite_sont_dans_l_ordre_equipe_genre_code_jamais_celui_d_un_compte, test_l_ordre_de_la_vue_du_produit_est_genre_puis_code, test_l_ordre_de_la_couverture_est_equipe_puis_genre)

### Requirement: Message language
The system SHALL accept the `--language fr|en` option, print its messages in French by default and in English with `--language en`: the listing header and view descriptions, the unknown-view message (which lists the available views), the database error, the notice that the threshold is raised to the floor, the reminder of a raised threshold, the "no rows" text and the masking marker ("masqué" in French, "masked" in English). An English run SHALL NOT print the French messages.

#### Scenario: English messages
- **WHEN** `list` runs with `--language en`
- **THEN** the descriptions and notices are printed in English, every known view is listed, and the French header does not appear

#### Scenario: Unknown view in English
- **WHEN** `show issues` runs with `--language en`
- **THEN** the exit code is 1, stderr names the unknown view and the available views in English, and no connection is opened

#### Scenario: French by default
- **WHEN** no language is given
- **THEN** the unknown-view message, the database error and the threshold notice are in French

#### Scenario: Marker in each language
- **WHEN** a view with a masked cell is rendered in French and in English
- **THEN** the cell reads "masqué" in French and "masked" in English

Source: tests/flow_views/test_langue.py
