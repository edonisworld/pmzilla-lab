# database-roles-views Specification

## Purpose

Schemas, least-privilege roles, the Jira flow tables and aggregated masked views, and the knowledge-library schema with full-text, vector and BM25 search, the flow raw layer, the story-quality schema and the team views (`db/migrations/0001` to `0016`).

## Requirements

### Requirement: Role privileges are isolated per schema
The system SHALL give each schema a read-write role and a read-only role; a read-write role SHALL read and write only its own schema, a read-only role SHALL only read its own schema, no role SHALL read another schema, and no application role SHALL create or drop objects in its schema or in the default schema (objects are owned by a dedicated owner role).

#### Scenario: Cross-schema denial

- **WHEN** the knowledge read-write role reads a table of the cases schema, or the cases read-only role reads a knowledge table, or the flow role reads a cases table
- **THEN** the statement is refused for insufficient privilege

#### Scenario: Read-only role cannot write

- **WHEN** the knowledge read-only role inserts, or the flow read-only role deletes
- **THEN** the statement is refused, while selects succeed

#### Scenario: No DDL for application roles

- **WHEN** the knowledge role creates or drops a table in its schema, or the flow role creates a table in the default schema
- **THEN** the statement is refused

Source: tests/db/test_db.py (TestAvecBase.test_droits_des_roles); tests/db/test_flow_schema.py (test_droits_des_roles_sur_flow)

### Requirement: Flow tables hold tickets, teams, teams per ticket, transitions and links, with no personal or textual fields
The system SHALL provide flow tables for teams, issues, issue-team membership, status transitions, issue links, declared label periods and fix version periods, and SHALL define no column named like a title, summary, description, assignee, reporter, creator, author, comment, product owner or person name, and no column holding personal data (design D3, D20). A label SHALL be stored only in the declared label periods table; no other table SHALL have a label column.

#### Scenario: Schema inspection

- **WHEN** the flow schema's tables and columns are listed after migration
- **THEN** exactly ten tables exist (the seven flow tables and the three raw-layer tables of the requirement "Raw layer tables in the flow schema"), no forbidden column name appears, a label column exists only in the declared label periods table, and no table has a PO or other personal column

Source: tests/db/test_flow_schema.py (test_tables_vues_et_colonnes, test_aucune_colonne_po_ni_personnelle_et_etiquette_dans_une_seule_table); tests/db/test_flow_gdpr.py (ColonneEtTables, SansBase)

### Requirement: An issue records its identity, lifecycle and history flag
An issue SHALL record its identity, classification, lifecycle instants, team and parent, whether history was collected for it, and the optional out-of-export instant. The history flag SHALL be a non-null boolean that is false for an issue inserted without it, SHALL be settable to true, and SHALL refuse a null value; its migration SHALL add it without inserting data.

#### Scenario: History flag

- **WHEN** an issue is inserted without the history flag, then flagged, then set to null
- **THEN** the flag reads false, then true, and the null update is refused by a not-null violation

Source: tests/db/test_lacunes_base.py (ColonneHasHistory, SansBase.test_migration_0003_ajoute_la_colonne_sans_donnee); tests/db/test_flow_gdpr.py (ColonneEtTables)

### Requirement: Deleting an issue deletes its dependent rows
Deleting an issue SHALL delete its team memberships, transitions, links, label periods and version periods.

#### Scenario: Cascade

- **WHEN** an issue with teams, transitions, links, a label period and a version period is deleted by the import role
- **THEN** none of its dependent rows remains

Source: tests/db/test_flow_schema.py (test_suppression_en_cascade_d_une_issue_et_de_ses_dependances); tests/db/test_flow_gdpr.py (ColonneEtTables.test_la_cascade_emporte_les_periodes)

### Requirement: Label and version periods are unique, ordered and tied to a known ticket
The system SHALL reject a label or version period of an unknown ticket (foreign key), a period whose removal instant precedes its addition instant (a period removed at its addition instant being allowed), and a second period of the same ticket, label or version and addition instant, whatever the time zone of that instant; the same label or version added again later SHALL be a new period. The migration of this change SHALL add its columns and tables without inserting data.

#### Scenario: Unknown ticket

- **WHEN** a label period or a version period is inserted for a ticket that is not stored
- **THEN** a foreign-key violation is raised

#### Scenario: Inverted period

- **WHEN** a period is inserted with a removal instant one day before its addition instant, then another with both instants equal
- **THEN** the first raises a check violation and the second is accepted

#### Scenario: Same instant, other time zone

- **WHEN** a period is inserted twice for the same ticket and label (or version) at the same instant written with two UTC offsets, then once more a week later
- **THEN** the second insert raises a uniqueness violation and the third is accepted

#### Scenario: No data

- **WHEN** the migrations are applied to a throwaway database
- **THEN** every flow table is empty

Source: tests/db/test_flow_gdpr.py (ColonneEtTables.test_cle_etrangere_refusee_et_periode_inversee_refusee, test_une_periode_n_existe_qu_une_fois, test_aucune_donnee_inseree_par_la_migration)

### Requirement: Flow data integrity constraints
The system SHALL reject a transition duplicating an existing one (same ticket, same instant whatever the time zone, same from and to status), a duplicated link, a link whose direction is neither inward nor outward, and a transition referring to an unknown ticket.

#### Scenario: Same instant, different offset

- **WHEN** a transition is inserted twice for the same instant written with two UTC offsets
- **THEN** the second insert violates a uniqueness constraint

#### Scenario: Invalid link or unknown ticket

- **WHEN** a link with direction "sideways" is inserted, or a transition for an unknown ticket
- **THEN** a check violation, respectively a foreign key violation, is raised

Source: tests/db/test_flow_schema.py (test_contraintes_et_doublons)

### Requirement: Only aggregated team views are exposed, without ticket keys
The system SHALL expose exactly four aggregated flow views to the views role (status by team, weekly resolved by team, open ticket age by team, dependencies between teams), the two team-name views (requirement "Team-name views for the views role") and, in addition, only the teams-seen view of the catalogue review (requirement "Teams-seen view for the catalogue review, readable by the flow read-only role only"), so seven flow views in total; no view SHALL expose a column whose name contains "key".

#### Scenario: View listing

- **WHEN** the views of the flow schema are listed
- **THEN** exactly the four aggregated views, the two team-name views and the teams-seen view exist, and none has a key-like column

Source: tests/db/test_flow_schema.py (test_tables_vues_et_colonnes, test_les_vues_ne_montrent_aucune_cle); the fifth view by amendment task 14.6; the two team-name views by change team-names-readable

### Requirement: Flow views count tickets without a team, and links to targets out of the export, under a no-team row
The four aggregated views SHALL count a ticket without a team under the team `(sans équipe)`. The dependencies view SHALL read a link whose target ticket is marked out of the export, or is absent from the database, as a link to the target team `(sans équipe)`, the two cases giving the same rows; such a cell stays masked under the minimum.

#### Scenario: Target marked out of the export

- **WHEN** six tickets of one team block six tickets of another, and one target ticket is then marked out of the export
- **THEN** the dependencies view counts five links between the two teams and a masked count towards `(sans équipe)`

#### Scenario: Unknown target

- **WHEN** the same link points to a ticket absent from the database, then back to the stored ticket marked out of the export
- **THEN** the dependencies view gives the same rows in both cases

#### Scenario: Ticket without a team

- **WHEN** a stored ticket in the export has no team
- **THEN** the status, weekly-resolved and open-age views count it under the team `(sans équipe)`

Source: tests/db/test_flow_gdpr.py (VuesSansTicketsMarques.test_dependances_cible_marquee_se_lit_comme_hors_export, test_dependances_lien_vers_une_cible_inconnue_se_lit_comme_une_cible_marquee). The row of a ticket without a team is read in migration `0008`: untested (suite tests/db)

### Requirement: Open age and weekly views use time buckets
The system SHALL group open tickets by age bucket relative to the current time in the open-age view (four buckets: up to 7 whole days, 8 to 30, 31 to 90, 91 and more), SHALL leave resolved tickets out of that view, and SHALL cut weeks on Monday at midnight UTC in the weekly-resolved view, whatever the offsets of the stored instants and the session time zone.

#### Scenario: Age buckets

- **WHEN** the open-age view is read for tickets aged just under and just over each bucket boundary
- **THEN** each open ticket falls in the bucket matching its age in whole days at the time of reading

#### Scenario: Resolved tickets

- **WHEN** only resolved tickets exist
- **THEN** the open-age view is empty

#### Scenario: Week boundary

- **WHEN** tickets are resolved just before and just after Monday midnight UTC, written with various offsets and read from a session far from UTC
- **THEN** the week is cut in UTC

Source: tests/db/test_lacunes_base.py (VueAgeDesTicketsOuverts, VueSemainesResolues; run on a disposable database)

### Requirement: Small counts are masked in the views
The system SHALL return a null count for any cell of the four aggregated views aggregating fewer than a minimum number of tickets or links, and SHALL return the real count at or above that minimum. The teams-seen view of the catalogue review SHALL NOT mask its counts (design D13): it is read only by the flow read-only role for the author's catalogue review, whose output shows counts and team identifiers, never a ticket; no report, dashboard or views-role reader SHALL use it.

#### Scenario: Large and small cells

- **WHEN** a team has many resolved tickets and another has very few open ones, and a single link exists
- **THEN** the large team's cell shows its count, the small team's cell is null, the dependencies view shows a null link count, and the weekly view shows only the large count

#### Scenario: Teams-seen view unmasked

- **WHEN** a team carries two stored tickets without an out-of-export instant
- **THEN** the teams-seen view shows 2 for that team

Source: tests/db/test_flow_schema.py (test_masquage_des_cellules_de_moins_de_cinq); teams-seen view by amendment task 14.6

### Requirement: Masking functions are executable only by the roles that read the masked views
The system SHALL revoke from every role the execution of the masking functions and SHALL grant it only to the roles reading the views that call them: `flow.mask_count` to the flow views role (migration `0002`), `quality.mask_count` (migration `0010`) and `quality.mask_verdicts` (migration `0016`) to the quality read-write, read-only and views roles.

#### Scenario: Grant of the verdict masking function

- **WHEN** migration `0016` is read without a database
- **THEN** it grants EXECUTE on `quality.mask_verdicts` to the quality read-write, read-only and views roles, after revoking all rights on it from PUBLIC

Source: tests/db/test_quality_masking.py (SansBase.test_la_migration_recree_les_trois_vues_avec_leurs_droits). The grants on the two `mask_count` functions are read in migrations `0002` and `0010`: untested (suite tests/db)

### Requirement: A view-only role reads the views and nothing else
The system SHALL provide a limited role, created by the migration without login capability, that reads the four aggregated views and the two team-name views only and is refused everywhere else (scenario below).

#### Scenario: Views allowed, tables denied

- **WHEN** the view-only role selects from each view
- **THEN** each of the four aggregated views and each of the two team-name views succeeds
- **AND** selecting from any flow table or from the teams-seen view, inserting a team, reading cases or knowledge tables, or creating a flow table is refused

Source: tests/db/test_flow_schema.py (test_le_role_des_vues_ne_lit_que_les_vues, test_le_role_des_vues_existe_apres_migration); teams-seen view by amendment task 14.6; team-name views by change team-names-readable

### Requirement: Limited roles log in with their own password, never the superuser's
The system SHALL accept a password to be set only for the view-only flow role, the quality views role, the read-only knowledge role, the read-only cases role, the read-write cases role and the flow import role (design D13), SHALL refuse a role outside this list before any connection, SHALL refuse a password that is too short, SHALL enable login for the role when its password is set, and SHALL read each limited role's password from its own keychain service or its own environment variable.

#### Scenario: Setting and using a limited role password

- **WHEN** a role outside the list, or a short password, is passed to the setter
- **THEN** a database error is raised
- **AND** when a listed role gets a valid password, connecting as that role yields a session of that role

#### Scenario: Unlisted role

- **WHEN** a connection is requested as a role not in the list (including the superuser)
- **THEN** it is refused before any connection attempt

#### Scenario: Per-role secret lookup

- **WHEN** the keychain service and environment variable names are derived for a limited role, including both cases roles, the flow import role and the quality views role
- **THEN** each is specific to that role and distinct from the superuser's

#### Scenario: Cases roles accepted

- **WHEN** the password setter is called for the read-only or the read-write cases role
- **THEN** it is accepted, while the read-write knowledge role is still refused

Source: tests/db/test_flow_schema.py (test_connexion_sous_un_role_limite_avec_son_propre_mot_de_passe, SansBase.test_role_password_n_accepte_que_les_roles_de_lecture_limitee, which covers both cases roles and the quality views role); tests/db/test_knowledge_schema.py (test_roles_de_lecture_limitee_et_leur_trousseau); tests/db/test_lacunes_base.py (CommandeRolePassword.test_aucune_saisie_et_succes, run with the flow views role; test_secret_propre_au_role_des_vues_de_qualite); tests/db/test_flow_raw_layer.py (SansBase.test_le_role_d_import_peut_avoir_un_mot_de_passe_avec_son_propre_trousseau)

### Requirement: A connection error never shows a limited role's password
A connection error as that role SHALL NOT contain the password.

#### Scenario: Wrong password

- **WHEN** a listed role has a valid password and a connection as that role is attempted with a wrong password
- **THEN** the error does not contain the real secret

Source: tests/db/test_flow_schema.py (test_connexion_sous_un_role_limite_avec_son_propre_mot_de_passe)

### Requirement: The import role and the quality roles under the password setter
The flow import role SHALL keep no right outside the flow schema. The read-write and read-only roles of the `quality` schema SHALL NOT be accepted by the setter: they never get a password.

#### Scenario: Flow import role

- **WHEN** the password setter is called for the flow import role and the role then reads a cases or knowledge table
- **THEN** the password is accepted, and the read is refused for insufficient privilege

#### Scenario: Quality roles

- **WHEN** the password setter is called for the quality views role, then for the quality read-write role, then for the quality read-only role
- **THEN** the first is accepted and the two others are refused before any connection

Source: tests/db/test_lacunes_base.py (test_role_des_vues_de_qualite_accepte_et_ses_deux_autres_roles_refuses); tests/db/test_flow_raw_layer.py (SchemaBrut.test_le_role_d_import_ne_lit_rien_hors_de_flow, SchemaBrut.test_le_mot_de_passe_du_role_d_import_est_accepte_par_le_poseur, which checks only that a short password is refused; SansBase.test_le_role_d_import_peut_avoir_un_mot_de_passe_avec_son_propre_trousseau, which checks only the role list and keychain names). Acceptance of the import role's password: acceptance untested (suite tests/db)

### Requirement: Knowledge schema stores books, collections, memberships and chunks
The system SHALL provide in the knowledge schema four library tables (books, collections, book-to-collection links, chunks) and, in addition, only the watch and pre-triage tables of the requirement "Knowledge schema stores the watch and pre-triage state", all owned by the owner role; chunks SHALL carry a vector embedding, a full-text vector, a JSON reference and a kind, with indexes for vector similarity, full text, book and position, kind, and book content hash. No migration SHALL insert data.

#### Scenario: Schema inspection

- **WHEN** the knowledge schema is inspected after migration
- **THEN** the four library tables and the watch and pre-triage tables exist and no other, all owned by the owner role, the expected library columns have the expected types, the expected indexes exist, and every table is empty

Source: tests/db/test_knowledge_schema.py (test_tables_colonnes_et_index, test_aucune_donnee_dans_les_tables_apres_migration)

### Requirement: Book author and publication date derive from metadata
The system SHALL expose each book's author and publication date derived from its JSON metadata, null when absent.

#### Scenario: Generated columns

- **WHEN** a book's metadata has an author only, and another has an author and a publication timestamp
- **THEN** the first book has a null date, the second a date-only value

Source: tests/db/test_knowledge_schema.py (test_plein_texte_sans_accent_et_colonnes_generees)

### Requirement: Full-text search ignores case and accents
The system SHALL match search terms regardless of case and accents on chunk text, through both the full-text vector (simple configuration with accent removal) and the BM25 index (lowercase, ASCII folding, no stemming).

#### Scenario: Accent and case variants

- **WHEN** the terms "equipe", an uppercase accented form and the accented form are searched
- **THEN** the same chunk is returned each time

#### Scenario: No stemming, OR semantics

- **WHEN** a plural form not present in the text is searched
- **THEN** nothing is returned
- **AND** when a query lists two words of which only one occurs, the chunk containing one of them is returned

Source: tests/db/test_knowledge_schema.py (test_plein_texte_sans_accent_et_colonnes_generees, test_index_bm25_accents_casse_et_score)

### Requirement: BM25 index scores matches and is usable by the read-only role
The system SHALL maintain an always-computed searchable text (section plus text) indexed for BM25, SHALL return a positive relevance score for matches, and SHALL let the read-only knowledge role run BM25 queries.

#### Scenario: Scored top results

- **WHEN** a BM25 query matches one chunk, ordered by score with a limit
- **THEN** that chunk is returned with a score greater than zero

#### Scenario: Read-only role

- **WHEN** the read-only role runs the same query
- **THEN** it gets the same result

Source: tests/db/test_knowledge_schema.py (test_index_bm25_accents_casse_et_score, test_le_role_de_lecture_peut_chercher_en_bm25)

### Requirement: The BM25 migration builds its index without parallel workers and documents its equivalence
The system SHALL, in the BM25 migration, disable parallel maintenance workers before building the index, SHALL name the ASCII-folding tokenizer, and SHALL record in the file the equivalence with the previous SQLite full-text tokenizer settings.

#### Scenario: Static content check

- **WHEN** the BM25 migration is read
- **THEN** the setting disabling parallel maintenance workers appears before the index creation, and the tokenizer and equivalence notes are present

Source: tests/db/test_knowledge_schema.py (SansBase.test_migration_0005_presente_sans_donnee_et_documentee)

### Requirement: Chunk kind is constrained and deleting a book cascades
The system SHALL reject a chunk whose kind is outside the allowed set, and SHALL delete a book's chunks and collection links when the book is deleted.

#### Scenario: Invalid kind

- **WHEN** a chunk is inserted with the kind "texte"
- **THEN** the insert fails

#### Scenario: Cascade

- **WHEN** one of two books is deleted by the read-write knowledge role
- **THEN** one chunk and one membership row remain

Source: tests/db/test_knowledge_schema.py (test_kind_contraint_et_suppression_en_cascade)

### Requirement: Knowledge read-only role cannot modify or create
The system SHALL let the read-only knowledge role count chunks while refusing inserts, deletes and table creation, and SHALL refuse table creation to the read-write knowledge role.

#### Scenario: Denied statements

- **WHEN** the read-only role inserts a collection, deletes chunks or creates a table
- **THEN** each raises an error, while its select returns the stored count

Source: tests/db/test_knowledge_schema.py (test_droits_du_role_d_acces_et_du_role_de_lecture)

### Requirement: Views leave out tickets out of the export
The system SHALL leave out of the four aggregated views the issues carrying an out-of-export instant.

#### Scenario: Marked ticket

- **WHEN** a team has six open tickets of which one is marked out of the export
- **THEN** the status view counts five open tickets for that team

Source: tests/db/test_flow_gdpr.py (VuesSansTicketsMarques)

### Requirement: Knowledge schema stores the watch and pre-triage state
The system SHALL provide, through a migration of the knowledge schema, tables for: collected watch articles (one per cleaned address, with a flag telling whether its cited links were extracted), the last collection attempt of each source, the links cited by each article, the pre-triage references, the article scores, the manual rescues, the manual exclusions, the user's shares, the daily picks (one per day and article), the shadow scores (one per article address and language) and the calibration (one entry per article, holding the values shown at the last export and the user's opinion).

#### Scenario: Fresh migration

- **WHEN** all migrations are applied to a throwaway database
- **THEN** the eleven watch and pre-triage tables exist in the knowledge schema, owned by the owner role, and are empty

#### Scenario: Uniqueness

- **WHEN** a second article with the same address, a second shadow score for the same address and language, or a second pick for the same day and file is inserted
- **THEN** a uniqueness violation is raised

Source: tests/db/test_watch_schema.py

### Requirement: Watch cited links and calibration values are constrained, and the watch migration inserts nothing
A cited link SHALL refer to a recorded article and SHALL be deleted with it. A calibration verdict and opinion SHALL be restricted to keep or discard (an opinion may be absent). The migration SHALL insert no data, set no password and alter no role.

#### Scenario: Link of an unknown article

- **WHEN** a cited link is inserted for an article that is not recorded
- **THEN** a foreign-key violation is raised, and deleting a recorded article deletes its links

#### Scenario: Calibration values

- **WHEN** a calibration entry is written with an opinion other than keep, discard or none
- **THEN** a check violation is raised

Source: tests/db/test_watch_schema.py

### Requirement: Knowledge roles' rights on the watch and pre-triage tables
The system SHALL let the knowledge read-write role read, insert, update and delete rows of every watch and pre-triage table, and SHALL let the knowledge read-only role only read them. Neither role SHALL create, alter or drop these tables, and no role of another schema SHALL read them.

#### Scenario: Read-write role

- **WHEN** the knowledge read-write role inserts, updates and deletes an article, a score and a calibration entry
- **THEN** each statement succeeds, and creating a table in the knowledge schema is refused

#### Scenario: Read-only role

- **WHEN** the knowledge read-only role selects from each table, then inserts a score or deletes a pick
- **THEN** the selects succeed and the writes are refused for insufficient privilege

#### Scenario: Other schemas' roles

- **WHEN** the cases read-write role or the flow view role reads a watch table
- **THEN** the statement is refused

Source: tests/db/test_watch_schema.py

### Requirement: Raw layer tables in the flow schema
The system SHALL provide in the flow schema tables for runs, run sightings and ticket snapshots, owned by the owner role and written by the import role, with a run kind restricted to export, seed and history and a Jira team identifier beside each snapshot team name. They SHALL hold no title, summary, description, person or label column and SHALL NOT be granted to the read-only or views role; their migration SHALL add them without data, password or role change.

#### Scenario: Schema inspection

- **WHEN** the flow schema is inspected after migration
- **THEN** the three raw tables exist and are empty, no forbidden column name appears in them, and no label column exists outside the declared label periods table

#### Scenario: Roles

- **WHEN** the read-only role or the views role selects from a raw table
- **THEN** the statement is refused, while the import role can insert and select

#### Scenario: Run kind

- **WHEN** a run is inserted with a kind other than export, seed or history
- **THEN** a check violation is raised

Source: tests/db/test_flow_raw_layer.py (SansBase, SchemaBrut)

### Requirement: The raw layer is append-only, one snapshot per run and ticket
The system SHALL let the import role insert, read and delete raw-layer rows but never update them. A run SHALL record a ticket at most once (one sighting and one snapshot per run and ticket, migration `0009`). A snapshot SHALL hold its teams as a JSON array of team name and Jira team identifier (possibly null), and its links as a JSON array or null when links were not collected. None of the four aggregated views SHALL read the raw layer.

#### Scenario: No update

- **WHEN** the import role updates a run, a sighting or a snapshot
- **THEN** the statement is refused for insufficient privilege

#### Scenario: Same ticket twice in a run

- **WHEN** a second sighting of the same ticket is inserted for the same run, or a sighting for an unknown run
- **THEN** a uniqueness violation, respectively a foreign-key violation, is raised

#### Scenario: Teams and links as JSON

- **WHEN** a snapshot is inserted with two teams, one without Jira identifier, and null links, then another with teams that are not a JSON array
- **THEN** the first keeps both identifiers ("11" and null) and null links, and the second raises a check violation

Source: tests/db/test_flow_raw_layer.py (SchemaBrut.test_le_role_d_import_insere_et_lit_mais_ne_modifie_pas, test_un_passage_et_un_ticket_n_ont_qu_un_instantane_et_une_visite, test_equipes_et_liens_en_json_avec_identifiant_jira, test_les_quatre_vues_ne_lisent_pas_la_couche_brute); tests/db/test_flow_history_not_found.py (ColonnesDuSuivi.test_la_couche_brute_reste_en_ajout_seulement). The snapshot's one-per-run key is read in migration `0009`; the test exercises the sighting's.

### Requirement: The quality schema holds story content apart from the flow data
The system SHALL provide, through a migration that inserts no data, sets no password and creates its roles without login, a `quality` schema owned by the owner role, with tables for items, item teams, team attributes, contents, assessments, coaching feedback, team reviews and overlay versions, and with read-write, read-only and views roles. The migration SHALL NOT name an object of another schema.

#### Scenario: Schema inspection

- **WHEN** the quality schema is inspected after migration
- **THEN** the eight tables and the three views exist, the tables are owned by the owner role and are empty, and the flow schema has no free-text column

#### Scenario: Migration file

- **WHEN** the migration file is read without a database
- **THEN** it holds no insert, update, delete or copy statement, no password, no role alteration and no role created with login, and it creates its objects under the owner role

#### Scenario: One hash per overlay version

- **WHEN** a second row is inserted in the overlay versions table for an identifier and version already recorded
- **THEN** a unique violation is raised

#### Scenario: Team review without sample

- **WHEN** a team review is inserted with a sample size of zero
- **THEN** a check violation is raised

Source: tests/db/test_quality_schema.py (StructureEtColonnes, SansBase)

### Requirement: Quality tables hold text only where it is expected and no person
The system SHALL keep title, description and acceptance-criteria text in the contents table only, and bounded feedback text in the coaching feedback table only. No quality table SHALL have a column named like an assignee, reporter, creator, author, comment, product owner, owner, person, user, account, e-mail or person name; the only column referring to a PO SHALL be the team's single-PO boolean, false unless declared.

#### Scenario: Column inspection

- **WHEN** the columns of the quality tables are listed
- **THEN** free-text columns appear only in contents and coaching feedback, other text columns are identifiers, codes or hashes, and no forbidden column name appears

#### Scenario: Bounded feedback

- **WHEN** a coaching feedback longer than the bound is inserted
- **THEN** a check violation is raised

Source: tests/db/test_quality_schema.py (StructureEtColonnes)

### Requirement: Quality verdicts are constrained and items cascade
The system SHALL restrict, in the database, an assessment's verdict to the four codes, its origin to core or organisation rule and its link to the four links, and SHALL require its sample mark. Assessment and coaching rows SHALL carry the core and overlay versions, the overlay pair both empty or both given. Deleting an item SHALL delete its teams, content, assessments and coaching feedback, and nothing of another item.

#### Scenario: Sample mark required

- **WHEN** an assessment is inserted without a sample mark
- **THEN** a not-null violation is raised

#### Scenario: Verdict constraint

- **WHEN** an assessment is inserted with a verdict outside the four codes
- **THEN** a check violation is raised

#### Scenario: Origin constraint

- **WHEN** an assessment is inserted with an origin other than core or organisation rule
- **THEN** a check violation is raised

#### Scenario: Overlay identifier without version

- **WHEN** an assessment is inserted with an overlay identifier and an empty overlay version
- **THEN** a check violation is raised

#### Scenario: Cascade

- **WHEN** an item with teams, content, assessments and coaching feedback is deleted by the read-write role
- **THEN** none of its dependent rows remains, and the rows of another item are still there

Source: tests/db/test_quality_schema.py (ContraintesEtCascade)

### Requirement: An audit verdict keeps the fingerprint of the text sent
The system SHALL add, through migration `0015`, a nullable `content_hash` column to the assessments table, holding the fingerprint of the cleaned text actually sent for that verdict, never an extract of it (null for a verdict older than the column). The migration SHALL add only that column, and no quality view SHALL read it.

#### Scenario: Column added

- **WHEN** the assessments table is inspected after migration, and its migration file is read
- **THEN** `content_hash` is a nullable text column, and the file adds no other column

Source: tests/story_quality/test_magasin_analyse_base.py (test_migration_0015_colonne_sans_texte, test_l_empreinte_stockee_est_celle_du_texte_envoye); tests/db/test_quality_schema.py (SansBase.test_l_ecriture_des_verdicts_ne_nomme_que_les_colonnes_sans_texte)

### Requirement: Quality roles stay inside their schema
The system SHALL refuse to every role of another schema the reading of the `quality` tables and views, and SHALL refuse to every `quality` role the reading of another schema. The read-write role SHALL read and write the tables, the read-only role SHALL only read them, and neither SHALL create or drop an object.

#### Scenario: Cross-schema denial

- **WHEN** a flow, cases or knowledge role reads the contents table or the product view, or a quality role reads a flow table
- **THEN** the statement is refused for insufficient privilege

#### Scenario: No DDL and no write for the read-only role

- **WHEN** the quality read-write role creates or drops a table, or the quality read-only role deletes items
- **THEN** the statement is refused, while both roles can read the contents table

Source: tests/db/test_quality_schema.py (DroitsDesRoles)

### Requirement: Quality views aggregate audit verdicts and mask small cells
The system SHALL expose exactly three views in `quality`, at the current pair of core and overlay versions: results by team, item kind and criterion; coverage by team and item kind; results by item kind and criterion for the whole product. Cells under the minimum SHALL be null, and so SHALL the cells masked so that no masked count is recoverable by difference. No view SHALL read sample verdicts, coaching feedback or items out of collection, nor expose a key, a title, a text or a person.

#### Scenario: Coaching left out

- **WHEN** coaching feedback is inserted for six audited items of a team
- **THEN** the three views give the same rows as before

#### Scenario: Sample verdicts left out

- **WHEN** assessments with the sample mark are inserted for six items at the current versions
- **THEN** the results views give the same rows as before, and the coverage view counts those items as collected but not audited

#### Scenario: Small cell

- **WHEN** a team has three audited stories and another twelve, six met and six not met
- **THEN** the first team's cells are null, and the second's show twelve audited and six not met while its zeros and its six met are masked

#### Scenario: Former versions not counted

- **WHEN** a team has audited items at an earlier version pair only
- **THEN** the results view returns no count for that team at the current pair of versions, and the coverage view shows it collected but not audited

#### Scenario: Items out of collection

- **WHEN** six audited items are marked out of collection
- **THEN** no view counts them

Source: tests/db/test_quality_schema.py (Vues), tests/db/test_quality_masking.py

### Requirement: Quality items without a team are counted in a no-team coverage row
Items without a team SHALL be counted in the coverage row `(sans équipe)`.

#### Scenario: Items without a team

- **WHEN** seven collected stories carry no team and none is audited
- **THEN** the coverage view counts them in the row `(sans équipe)` as collected, with a masked audited count, and the per-team view has no row for them

Source: tests/db/test_quality_masking.py (AvecBase.test_sans_equipe_collecte_et_non_audite_dans_la_couverture)

### Requirement: The per-team quality view carries the criterion's origin and link
The per-team quality view SHALL give, on each row, the origin of the criterion (core or organisation rule) and its link in the chain, as stored with the audit verdicts it counts.

#### Scenario: Organisation rule at the definition of ready

- **WHEN** six stories of a team are audited on a criterion whose origin is an organisation rule and whose link is the definition of ready
- **THEN** the per-team view's row for that team, item kind and criterion shows that origin and that link

Source: tests/db/test_quality_schema.py (Vues.test_la_vue_par_equipe_porte_l_origine_et_le_lien)

### Requirement: The product view counts each item once and has no team column
The system SHALL compute the product view over the audit verdicts of every team taken together, counting each item once even when it belongs to several teams, with stories and epics counted apart. The product view SHALL NOT have a team column or any column that lets its rows be grouped by team.

#### Scenario: Item with two teams

- **WHEN** seventeen audited stories include one that belongs to two teams, the two teams counting twelve and six
- **THEN** the product view counts seventeen stories for each criterion, not eighteen

#### Scenario: No team column

- **WHEN** the columns of the product view are listed
- **THEN** none names or identifies a team

#### Scenario: Small product cell

- **WHEN** only three stories are audited across all teams
- **THEN** the product view's cells for stories are null

Source: tests/db/test_quality_schema.py (VueDuProduit)

### Requirement: The coverage view carries the single-PO team flag
The system SHALL expose in the coverage view, per team, the single-PO flag of the team attributes, unmasked, false when the team has no attributes. The team attributes SHALL hold no person: no name, no account and no role holder. The flag SHALL NOT change any count.

#### Scenario: Flagged team

- **WHEN** a team's attributes carry the single-PO flag
- **THEN** the coverage view shows the flag for that team, even when its counts are masked, and its counts equal those of the same team without the flag

Source: tests/db/test_quality_schema.py (test_le_drapeau_d_un_seul_po_est_en_clair_et_ne_change_aucun_compte, test_attributs_d_equipe_et_relectures_sans_personne)

### Requirement: The quality views role reads the three views and nothing else
The system SHALL give the quality views role read access to the three quality views only. It SHALL be refused on every table, on writes, on the other schemas and on object creation, and the migration SHALL create it without login capability and grant it no default privilege.

#### Scenario: Views role

- **WHEN** the quality views role selects from each view, then from each table
- **THEN** the views succeed and every table read is refused

#### Scenario: Nothing else

- **WHEN** the quality views role inserts an item, creates a table in `quality` or in the default schema, or reads a flow, cases or knowledge object
- **THEN** each statement is refused for insufficient privilege

Source: tests/db/test_quality_schema.py (DroitsDesRoles, SansBase.test_le_role_des_vues_ne_recoit_que_les_trois_vues)

### Requirement: Team type column of the flow teams table
The system SHALL provide in the flow teams table a nullable team-type column restricted to the four Team sub-type names, written by the import role, readable by the read-only role, not named like a label or a key, added by a migration that fills no value and changes no password or role (design, "Complement: team type column"). The column SHALL NOT be granted on the table to the views role, which reads the stored type only through `flow.v_teams`; no aggregated view SHALL read it.

#### Scenario: Fresh migration

- **WHEN** the migration is applied to a database holding teams
- **THEN** every team has a null type, and the views role cannot read the column on the teams table

#### Scenario: Value outside the sub-types

- **WHEN** a team type other than the four sub-type names is written
- **THEN** a check violation is raised

#### Scenario: Type read through the teams view

- **WHEN** the views role selects the team type from the teams table, then from `flow.v_teams`
- **THEN** the table read is refused, and the view shows the stored type

Source: tests/db/test_flow_team_type.py (SansBase, ColonneType, AvantLaMigration); tests/db/test_team_name_views.py (AvecBase.test_le_type_est_celui_qui_est_stocke_nul_sans_type_une_ligne_par_equipe, AvecBase.test_le_role_des_vues_reste_refuse_sur_la_table_des_equipes_et_sur_la_couche_brute)

### Requirement: Collection tracking columns on tickets and runs
The system SHALL add, through migration `0012`, to each issue a non-negative count of consecutive history collections answered "not found" (default 0) and a nullable instant at which the ticket was marked gone, and to each run a nullable non-negative count of transient errors and of "not found" answers. The import role SHALL write them, the read-only role SHALL only read the issue columns, and neither the views role nor any of the four aggregated views SHALL read them.

#### Scenario: Defaults and negative values

- **WHEN** a ticket and a history run are inserted without these values, then a negative count is written
- **THEN** the ticket reads 0 and a null instant, the run reads null counts, and the negative count raises a check violation

#### Scenario: Roles

- **WHEN** the import role updates the ticket counts and inserts a run with counts, the read-only role updates a ticket count, and the views role reads a count
- **THEN** the import role's statements succeed, and the two others are refused

Source: tests/db/test_flow_history_not_found.py (SansBase, ColonnesDuSuivi)

### Requirement: Views grouped by team type mask single-team groups and rank no team
The system SHALL, in any view grouped by team type, return a null count for a cell under the masking threshold, mask a type group holding fewer than 2 teams whole, put a null type in a "type not set" group, and show a group's team count only from 2 on (design, "Complement: team type column"). It SHALL NOT expose a total that recomputes a masked group, a line per team, a team name or a ranking of teams, and SHALL NOT let a setting lower the minimum of 2 teams. Untested until implemented.

#### Scenario: Type held by one team

- **WHEN** a view grouped by type is read with one team of a type and four teams of another
- **THEN** the single-team group is masked whole, the other group shows its counts, and no total row allows a subtraction

Source: not built, deferred (idea in Kraken, author decision of 2026-10-21)

### Requirement: Teams-seen view for the catalogue review, readable by the flow read-only role only
The system SHALL provide, through migration `0013`, the view `flow.v_team_tickets_seen` (team identifier, team name, ticket count): one row per team carrying at least one stored ticket without an out-of-export instant, with the number of those tickets (design D13). SELECT SHALL be granted to the flow read-only role only. The view SHALL NOT mask its counts, expose a key, title, person, label, status or instant, or be readable by the views, quality views or import role.

#### Scenario: Migration file

- **WHEN** migration `0013` is read without a database
- **THEN** it creates one view under the owner role, grants SELECT on it to the flow read-only role only, revokes the other rights on it, calls no masking function, and holds no insert, update, delete, copy, password or role statement

#### Scenario: Content

- **WHEN** a team carries one stored ticket without an out-of-export instant and one marked out of the export, and another ticket carries two teams
- **THEN** the first team's row counts 1 (unmasked), the marked ticket is not counted, and the ticket with two teams counts once under each of its teams

#### Scenario: Rights

- **WHEN** the flow read-only role, the views role, the quality views role and the import role select from the view, and the read-only role tries to insert into it
- **THEN** only the read-only role's select succeeds; the other selects and the insert are refused for insufficient privilege

Source: tests/db/test_flow_team_tickets_seen.py (SansBase, AvecBase)

### Requirement: Team-name views for the views role
The system SHALL provide, through migration `0014`, two views readable by the flow views role only: `flow.v_teams` (team, team type as stored, tickets) and `flow.v_team_jira_ids` (team, Jira team identifier, tickets), with masked counts of tickets in the export (design D2, D3, decision e). They SHALL NOT expose a ticket key, title, description, person, label, project, status, instant or team id, nor group or count by team type.

#### Scenario: Columns

- **WHEN** the columns of the two views are listed
- **THEN** they are exactly team, team type and tickets, and team, Jira team identifier and tickets, and no column name contains key, title, summary, description, person, label, project or status

#### Scenario: Team type as stored

- **WHEN** one team has a stored type among the four sub-type names and another has none
- **THEN** the teams view shows the first team's type as stored and a null type for the second, one row per team

#### Scenario: Masking and scope

- **WHEN** a team carries two tickets in the export and one ticket marked out of the export, and another team carries ten tickets
- **THEN** the first team's count is null, the marked ticket is not counted, and the second team shows 10

#### Scenario: Latest snapshot only

- **WHEN** a ticket's earlier snapshot carries one Jira team identifier and its latest snapshot another
- **THEN** only the latest identifier is counted for that ticket

#### Scenario: Team without identifier on a ticket

- **WHEN** a ticket's latest snapshot carries a team name without Jira team identifier
- **THEN** no row of the identifiers view is made for it, while the teams view counts the ticket under its team

#### Scenario: Rights

- **WHEN** the views role, the read-only role, the import role and the quality views role select from each view
- **THEN** only the views role's selects succeed, and the views role is still refused on the teams table, its type column included, and on the raw tables

Source: tests/db/test_team_name_views.py (SansBase, AvecBase)

### Requirement: No masked count of a results row is recoverable by difference
The system SHALL apply, in the per-team and product views themselves (design D8, migration `0016`), a complementary masking: while the masked counts of a row add up to less than five, the smallest visible count SHALL be masked too, ties in column order. The audited count SHALL never be masked by this rule.

#### Scenario: One small count

- **WHEN** a team has twenty-nine audited stories for a criterion, twenty met, three not met and six not applicable
- **THEN** the per-team view shows the audited count and twenty met, and masks the three other counts

#### Scenario: Zeros given back by their sum

- **WHEN** a team has twelve audited stories for a criterion, six met and six not met
- **THEN** the per-team view masks the two zeros and one of the counts of six, so that the masked counts add up to at least five

#### Scenario: Enumeration of differences

- **WHEN** the views are read on fictitious data drawn with fixed seeds, and the test enumerates every simple difference and sum of the visible cells of each row
- **THEN** the views equal the reference of the test, and no difference or sum gives back a masked cell

Source: tests/db/test_quality_masking.py (SansBase, AvecBase)

### Requirement: No masked coverage count is recoverable by difference
The system SHALL mask, in the coverage view, a cell whose difference with another visible cell of its row is under five: collected minus audited masks the collected count; audited minus empty acceptance criteria, in absolute value, or visible collected minus empty acceptance criteria masks the empty acceptance-criteria count. The audited count SHALL never be masked by this rule.

#### Scenario: Every item audited

- **WHEN** a team has forty collected stories, all audited
- **THEN** the coverage view masks the collected count and shows forty audited

#### Scenario: Close empty count

- **WHEN** a team has seven collected stories, none audited, five of them without acceptance criteria
- **THEN** the coverage view shows seven collected and masks the empty acceptance-criteria count

Source: tests/db/test_quality_masking.py (SansBase.test_toute_ligne_de_couverture_jusqu_a_40_sans_fuite)

### Requirement: The product view masks a row that would give back a masked team cell
The system SHALL mask every count of a product row (design D18) when, for a column whose product cell is visible, exactly one team cell of that kind and criterion is masked, or the masked team cells of the column add up to less than five. The rule SHALL treat the subtraction as exact even for an item of several teams.

#### Scenario: One small team

- **WHEN** one team has forty audited stories for a criterion and another three
- **THEN** every count of the product row for that criterion is null

#### Scenario: Two large masked team cells

- **WHEN** two team cells of a visible product column are masked and add up to five or more
- **THEN** the product row stays shown

#### Scenario: A column masked in the product row

- **WHEN** no item of any team is not applicable or undetermined for a criterion
- **THEN** those zero columns are masked in the product row as in the team rows, and they do not mask the product row

Source: tests/db/test_quality_masking.py (AvecBase.test_une_seule_petite_equipe_masque_la_ligne_du_produit)

### Requirement: The quality views carry the current grid versions
The system SHALL end each of the three quality views with the core grid version and the overlay version of the current pair, null in the coverage view while no audit verdict exists, and SHALL NOT expose the overlay identifier.

#### Scenario: Version columns

- **WHEN** audit verdicts exist at core version 4 and overlay version 2
- **THEN** the last two columns of each view are the core grid version and the overlay version, with these values, and no column names the overlay identifier

Source: tests/db/test_quality_masking.py (AvecBase.test_les_versions_de_la_paire_courante_et_jamais_l_identifiant_de_surcouche)

## Open questions

None. (The cases schema tables are created by a later migration and specified in `cases-schema`.)
