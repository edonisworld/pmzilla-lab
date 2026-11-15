# jira-flow-views Specification

## Purpose

Describes the aggregated-views reader, the only route the assistant has to Jira data in the database: it shows a closed list of aggregated views (flow views by team, team-name views, story quality views, the fix version share view) with small count cells masked. Sources are `tests/flow_views/test_flow_views.py` and `tests/flow_views/test_langue.py`.

## Requirements

### Requirement: Closed list of views
The system SHALL offer `list` (the available views with their description, the current masking threshold and the masking marker) and `show <view>`. The title of `list` giving the configured threshold and the masking marker is untested (suite tests/flow_views).

Source: tests/flow_views/test_flow_views.py (test_liste_des_vues, VuesDeQualite, VuesDesNomsDEquipe)

#### Scenario: Listing
- **WHEN** `list` is run, in French or in English
- **THEN** every known view appears, the three quality views and the two team-name views included with a description in that language, and the exit code is 0

### Requirement: Known views
The system SHALL accept only the known views: the four flow views, the two team-name views, the fix version share view, the version quality photo view, the fix version lag view, the delivery fields coverage view and the three story quality views.

Source: tests/flow_views (test_flow_views.py, test_part_fix_version.py); photo, lag and coverage views untested until implemented

#### Scenario: Views of the migrations
- **WHEN** the known views are compared with the migrations
- **THEN** the four flow views are those of the flow migration, the two team-name views those of migration `0014`, the share view that of migration `0018`, the photo and lag views those of the photo views migration, the coverage view that of the delivery fields view migration, and the three quality views those of the quality migration

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
- **WHEN** each of the views is read
- **THEN** the flow views, the fix version share view and the team-name views are read under the flow views role in the flow schema, and the quality views under the quality views role in the quality schema

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

### Requirement: Fix version share view
The system SHALL provide the view `v_team_fix_version_share`: per team and calendar quarter of resolution, over the last three closed quarters (the running quarter left out), finished items (type `Epic` and tickets out of the export left out), those with a current fix version, and the share in percent, plus a product line. It SHALL show no version name and no key, and be read under the flow views role only.

Source: tests/db/test_flow_fix_version_share.py

#### Scenario: One team, one quarter
- **WHEN** a team resolved 10 items in a quarter and 8 carry a fix version
- **THEN** the row shows 10, 8 and 80

#### Scenario: Old quarter
- **WHEN** an item was resolved four quarters ago
- **THEN** it is in no row

#### Scenario: Current quarter
- **WHEN** an item was resolved in the current quarter
- **THEN** it is in no row

### Requirement: Fix version share masking
The system SHALL mask, inside the view, a team cell under 5 items, and the count with a version and the share when the count with or without a version is under 5. It SHALL mask the product cells of a quarter when the masked team cells are exactly one, or add up to under 5 items, or under 5 with or without a version.

Source: tests/db/test_flow_fix_version_share.py (test_masquage_sous_cinq, test_masquage_complementaire, test_masquage_de_la_ligne_produit)

#### Scenario: Small team
- **WHEN** a team resolved 3 items in a quarter
- **THEN** its items, with-version count and share are null

#### Scenario: Four without a version
- **WHEN** a team resolved 20 items and 4 have no fix version
- **THEN** its items show 20 and its with-version count and share are null

#### Scenario: Product line recovered by difference
- **WHEN** exactly one team of a quarter is masked
- **THEN** the product cells of that quarter are null

### Requirement: Fix version lower bound
The system SHALL publish in `with_fix_version_min` the items minus 4 for a team and quarter whose items are visible and with fewer than 5 items lacking a version, null otherwise and for the product line. It SHALL give no exact count, alone or by difference with the product line.

Source: tests/db/test_flow_fix_version_share.py (test_borne_basse_publiee_sans_valeur_exacte, test_deux_equipes_a_borne_ne_redonnent_pas_de_valeur_exacte)

#### Scenario: High share
- **WHEN** a team resolved 20 items and 18 carry a fix version
- **THEN** its with-version count and share are null and its lower bound is 16

### Requirement: Homogeneity reading
The system SHALL provide `version-share [--floor N]` (default 80), which reads the view and prints one outcome: homogeneous over the three completed quarters, homogeneous since a quarter start, or not homogeneous. The current quarter never counts. A team whose quarters are all masked, or not all present and readable for the first outcome, SHALL be left out as not established.

Source: tests/flow_views/test_part_fix_version.py (Verdict, QuatreTrimestresTermines)

#### Scenario: Since a date
- **WHEN** every team meets the floor from the second quarter on and one team does not before
- **THEN** the outcome is "homogeneous since" the start of that second quarter

#### Scenario: Not homogeneous
- **WHEN** a team's last unmasked quarter is under the floor
- **THEN** the outcome is "not homogeneous"

#### Scenario: Masked quarter
- **WHEN** a team has a masked quarter and meets the floor in the others
- **THEN** it is not established and the other teams decide the outcome

#### Scenario: Three completed quarters
- **WHEN** every team meets the floor in each of the three completed quarters
- **THEN** the outcome names the three completed quarters, never four

### Requirement: Bound and no-team line in the reading
The system SHALL read a published lower bound as above the floor for that quarter when bound over items reaches it, else as not established. It SHALL leave the "(sans équipe)" line out of the outcome and print it on its own line.

Source: tests/flow_views/test_part_fix_version.py (BorneBasse, SansEquipe)

#### Scenario: Bound at the floor
- **WHEN** a team's quarters hold the bound 16 of 20 items and the floor is 80
- **THEN** the team is above the floor for those quarters

#### Scenario: No-team line
- **WHEN** the view holds a "(sans équipe)" line
- **THEN** the outcome ignores it and its own line shows its share, bound or masked

### Requirement: Share columns masked with the counts
The system SHALL mask the items and with-version counts of the share view like the other count columns when the reader threshold is raised, the share of a row whenever its items, with or without counts fall under it, and the product line of a quarter whose masked team cells would be recovered by difference. It SHALL recall a raised threshold on the error output.

Source: tests/flow_views/test_part_fix_version.py (Masquage, test_seuil_releve_rappele_sur_la_sortie_d_erreur)

#### Scenario: Raised threshold
- **WHEN** the threshold is raised to 10 and a row holds 12 items, 9 with a version
- **THEN** the with-version count and the share are shown "masqué"

#### Scenario: Product line at a raised threshold
- **WHEN** the threshold is raised to 10 and one team of a quarter holds 7 items
- **THEN** the product line of that quarter is shown "masqué"

### Requirement: Photo view shows coverage only before N
The system SHALL provide the view `v_version_quality_photo`, which returns, while no N is adopted, one coverage row per photo run and week (source, coverage, week, photo instant) and no team, version, count or share. It SHALL be read under the flow views role only and show no version name or key.

Source: untested until implemented

#### Scenario: Before N
- **WHEN** the store holds a reconstruction of ten weeks and one live photo, and the register of N is empty
- **THEN** the view returns eleven coverage rows, with their source and coverage, and no count column holds a value

### Requirement: No count exposed before N
The system SHALL fail its tests when the photo view returns a count or a share while the register of N is empty, for every count and share column of design D14. It SHALL NOT expose a count by any column, row kind or product line before N.

Source: untested until implemented

#### Scenario: Guard test
- **WHEN** a disposable database holds photos with counts of 5 and more and no adopted N, and the view is read under the flow views role
- **THEN** every count and share column is null on every row, and the test fails if one is not

### Requirement: Photo view shows the retained weeks after N
After an adoption of N, the system SHALL return counts only for the week starting N weeks before the release week of each version with a release date, with N and its adoption date, plus the coverage rows. A version with a null release date SHALL have no retained week and no count.

Source: untested until implemented

#### Scenario: Release dates still null
- **WHEN** N is adopted and every release date of the register is null
- **THEN** the view returns the coverage rows only, and no count

#### Scenario: Retained week
- **WHEN** N is 6 and a version's release week starts on a given Monday
- **THEN** only the photo rows of the week starting six weeks earlier carry counts for that version

### Requirement: Photo view shows a modified N
The system SHALL expose on every row of the photo view `n_modified_after_reading`, true as soon as the register holds more than one adoption, and the previous N with its adoption date, null with a single adoption. It SHALL NOT expose the reason of an adoption.

Source: untested until implemented

#### Scenario: One adoption
- **WHEN** N was adopted once
- **THEN** every row shows `n_modified_after_reading` false and no previous N

#### Scenario: Second adoption
- **WHEN** N was adopted at 6 weeks, then at 8 weeks with a reason
- **THEN** every row, coverage rows included, shows `n_modified_after_reading` true, the previous N 6 and its adoption date, and no reason

### Requirement: Photo view masking on the retained weeks
On the retained weeks, the system SHALL mask a count under 5. In each pair (part, whole) of design D11, it SHALL mask the part when the part or the whole minus the part is under 5. It SHALL mask the product cells of a retained week when its masked team cells, zeros included, are exactly one or add up to under 5.

Source: untested until implemented

#### Scenario: Recovered by difference
- **WHEN** a team's retained row holds 20 defects found and 17 still open
- **THEN** the open count is null and the found count shows 20

#### Scenario: Product line recovered by difference
- **WHEN** exactly one team cell of a retained week and version is masked
- **THEN** the product cells of that week and version are null

#### Scenario: Zero recovered by difference
- **WHEN** a team's retained row holds 0 reopened defects and the other team cells of that week and version are visible
- **THEN** the team's reopened cell is null and the product's reopened cell is null, since a masked zero counts as a masked cell

### Requirement: Defects without affects version masked as a row to complete
The system SHALL treat "defects created = without affects + defects found by version" as a row to complete: when the masked cells (without affects, hidden version terms) are exactly one or add up to under 5, it SHALL mask the smallest visible cell of the row too, with the shares, on team and product lines alike (design D18-D).

Source: untested until implemented

#### Scenario: One hidden version
- **WHEN** a team holds in a retained week 40 defects created, 15 without affects version and two versions with 20 and 3 defects found
- **THEN** the hidden term (3) makes the masked cells exactly one: the team's defects without affects version and its share are null, and the defects created show

#### Scenario: Defect with two affects versions
- **WHEN** a defect carries two affects versions
- **THEN** it counts once in each version found, and the masking rule above still applies

#### Scenario: Raised threshold, terms masked by the view
- **WHEN** the view shows 40 defects created, 12 without affects version, a version with 20 found, and masks two versions of 4 found each, and the reader raises the threshold to 10
- **THEN** the hidden sum is 40 - 12 - 20 = 8, under 10, with two hidden terms: the defects without affects version are masked, and so is their share

#### Scenario: Known limit, defects with several affects versions
- **WHEN** a whole row is published (created, without affects version, found by version)
- **THEN** the number of defects with several affects versions is readable by difference (sum of the found minus created plus without affects); it is not a cell and may be under 5, an accepted limit (design, Risks)

### Requirement: Raised threshold on the product line
When the reader raises the threshold, the system SHALL count, for a product cell, every team cell not visible at that threshold, those masked by the view included, and use the product minus the visible team cells as their sum.

Source: untested until implemented

#### Scenario: Two cells masked by the view
- **WHEN** two team cells masked by the view add up to 7 and the threshold is raised to 10
- **THEN** the product cell is masked

### Requirement: Shares of the photo view
On the retained weeks, the system SHALL compute in the view the share of throughput in correction and the share of defects without affects version, in percent, masked with their part or whole. It SHALL NOT add defects found and defects corrected.

Source: untested until implemented

#### Scenario: Share in correction
- **WHEN** a team's retained version-free row holds 20 resolved items, 6 of them defects
- **THEN** the view shows a share in correction of 30

### Requirement: Fix version lag view
The system SHALL provide the view `v_team_fix_version_lag`: per team and quarter of resolution, over the last three closed quarters, resolved items with a current fix version (type `Epic` and tickets out of the export left out), by delay from resolution to the first fix version addition in four buckets, and those without history. It SHALL be readable whether N is adopted or not.

Source: untested until implemented

#### Scenario: Fix version set at release preparation
- **WHEN** a team resolved 10 items in a quarter, each getting its first fix version 40 days after resolution
- **THEN** its row shows 10 items and 10 in the bucket "later"

#### Scenario: Older quarter
- **WHEN** an item with a fix version was resolved four quarters ago
- **THEN** it is in no row of the lag view

### Requirement: Fix version lag masking
The system SHALL mask in the lag view a cell under 5, and the smallest visible bucket of a row when its masked buckets, zeros included, are exactly one or add up to under 5. It SHALL show a team-quarter row only when the detail of the share view is visible for the same team and quarter, and a product bucket only when every team cell of its column is visible (design D18). It SHALL show no version name or key.

Source: untested until implemented

#### Scenario: One small bucket
- **WHEN** a team's row holds 12 items, 3 of them before resolution and 9 later
- **THEN** both bucket cells are null and the item count shows 12

#### Scenario: Zero buckets
- **WHEN** a team's row holds 10 items, all of them later
- **THEN** the item count shows 10 and every bucket cell is null, since the four zero buckets are masked and the visible one would give them back by difference

#### Scenario: Product bucket masked by a team cell
- **WHEN** a team's row holds 13 items, 2 before resolution and 11 within 7 days, and the other teams' cells are visible
- **THEN** no product bucket cell is visible and the product line never has exactly one masked bucket while its items are visible

#### Scenario: Row hidden by the share
- **WHEN** a team resolved 20 items in a quarter, 18 with a fix version, so that the share view masks the count 18 (2 without fix version, under 5)
- **THEN** the lag view shows no cell of that team-quarter row (items included) and none of the product row of the quarter

#### Scenario: Four teams, columns b1 to b5
- **WHEN** four teams hold A = [10, 2, 20, 20, 20], B = [10, 1, 20, 20, 20], C = [20, 20, 2, 10, 20] and D = [20, 20, 1, 10, 20] in the five buckets, every share detail being visible
- **THEN** each team masks its small number and its smallest visible bucket, the product buckets of columns 1 to 4 are masked, and column 5 (visible in every team) stays: A2 + B2 is never recoverable

### Requirement: Delivery fields coverage view
The system SHALL provide the view `v_team_delivery_fields_coverage` (design D9 of change jira-delivery-fields): per team, quarter of resolution over the last three closed quarters and item kind, epics on their own rows, the finished items and the items with each delivery field filled. It SHALL show no version, sprint, option value or key, and SHALL be read under the flow views role only.

#### Scenario: One team, one quarter
- **WHEN** a team resolved 12 stories in a quarter, 7 of them with a sprint
- **THEN** its story row shows 12 items and 7 with a sprint

#### Scenario: Epics apart
- **WHEN** a team resolved 6 stories and 8 epics in a quarter
- **THEN** the stories and the epics are counted on two rows of their item kind

#### Scenario: Running quarter
- **WHEN** a team resolved stories in the running quarter only
- **THEN** the coverage view has no row for that team

### Requirement: Coverage view masking
The system SHALL mask inside the coverage view an item count under 5, and a filled count when the filled or the unfilled count is under 5. The reader SHALL return these cells as structured masked cells with the reason `under_threshold` and the threshold.

#### Scenario: Few items with a sprint
- **WHEN** a team resolved 12 items in a quarter, 3 of them with a sprint
- **THEN** its items show 12, and the reader returns the sprint cell masked with the reason `under_threshold`

#### Scenario: Few items without a field
- **WHEN** a team resolved 20 items in a quarter, 18 of them with a target version
- **THEN** the target version cell is masked, since the unfilled count is under 5

### Requirement: Quarter views read the last three closed quarters
Every quarter view SHALL cover the last three closed quarters before the UTC quarter of the reading instant, read from `flow.closed_quarter_starts`. It SHALL NOT show the running quarter, a fourth quarter or an inline window. The oldest start SHALL never be older than the reading instant minus the maximum retention period plus one day.

Source: untested until implemented (tasks 2.1, 2.2)

#### Scenario: Running quarter left out
- **WHEN** an item was resolved in the running quarter
- **THEN** it is in no row of any quarter view

#### Scenario: Fourth closed quarter left out
- **WHEN** an item was resolved four quarters before the running quarter
- **THEN** it is in no row of any quarter view

#### Scenario: Window bound on every day
- **WHEN** the window function is evaluated for every UTC day from 2027 to 2030, a leap year included
- **THEN** it gives three quarter starts, none of them the running quarter, and the oldest is never older than that day minus the maximum retention period plus one day

#### Scenario: No inline four-quarter window
- **WHEN** the latest definition of each quarter view is read without a database
- **THEN** none holds a four-quarter series, and each reads its quarters from the window function

### Requirement: Declared limit of the oldest quarter
The system SHALL state in the help of each quarter view (the view's comment, its description in `list` and the help text) that the oldest of the three quarters may lose at most one day and a few hours on the last days of a quarter (about 1 %). It SHALL NOT mask or withhold that quarter for this reason.

Source: untested until implemented (tasks 2.1, 2.2)

#### Scenario: Help in French
- **WHEN** `list` runs in French
- **THEN** the description of each quarter view holds « le plus ancien des trois trimestres peut perdre au plus un jour et quelques heures les derniers jours d'un trimestre (environ 1 %) »

#### Scenario: Last day of a quarter
- **WHEN** the views are read on the last UTC day of a quarter
- **THEN** the oldest quarter is shown with its rows, unmasked by this rule

### Requirement: Grouped row of the last three quarters
The system SHALL give, in the lead time, cycle time and throughput view, one grouped row per team: its counts are the sums of the three quarterly counts shown, its statistics are computed over the items of those quarters. Its masking rules SHALL be unchanged, the series having three terms. The system SHALL NOT pool a quarter that the view does not show.

Source: untested until implemented (change flow-three-closed-quarters, task 2.1)

#### Scenario: Sum of the three quarters
- **WHEN** a team's three quarterly throughput cells are 10, 12 and 9, all visible, on the synthetic dataset
- **THEN** the grouped row shows a throughput of 31

#### Scenario: A masked quarter
- **WHEN** one of a team's three quarterly throughput cells is masked
- **THEN** the throughput of its grouped row is masked
