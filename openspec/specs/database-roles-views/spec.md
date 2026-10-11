# database-roles-views Specification

## Purpose

Schemas, least-privilege roles, the Jira flow tables and aggregated masked views, and the knowledge-library schema with full-text, vector and BM25 search (`db/migrations/0001` to `0005`).
## Requirements
### Requirement: Role privileges are isolated per schema
The system SHALL give each schema a read-write role and a read-only role; a read-write role SHALL read and write only its own schema, a read-only role SHALL only read its own schema, no role SHALL read another schema, and no application role SHALL create or drop objects in its schema or in the default schema (objects are owned by a dedicated owner role).

Source: tests/db/test_db.py (TestAvecBase.test_droits_des_roles); tests/db/test_flow_schema.py (test_droits_des_roles_sur_flow)

#### Scenario: Cross-schema denial
- WHEN the knowledge read-write role reads a table of the cases schema, or the cases read-only role reads a knowledge table, or the flow role reads a cases table
- THEN the statement is refused for insufficient privilege

#### Scenario: Read-only role cannot write
- WHEN the knowledge read-only role inserts, or the flow read-only role deletes
- THEN the statement is refused, while selects succeed

#### Scenario: No DDL for application roles
- WHEN the knowledge role creates or drops a table in its schema, or the flow role creates a table in the default schema
- THEN the statement is refused

### Requirement: Flow tables hold tickets, teams, teams per ticket, transitions and links, with no personal or textual fields
The system SHALL provide flow tables for teams, issues, issue-team membership, status transitions and issue links, and SHALL define no column named like a title, summary, description, assignee, reporter, creator, author, label, comment or person name. An issue SHALL record its identity, classification, lifecycle instants, team and parent, and whether history was collected for it. The history flag SHALL be a non-null boolean that is false for an issue inserted without it, SHALL be settable to true, and SHALL refuse a null value; its migration SHALL add it without inserting data.

Source: tests/db/test_flow_schema.py (test_tables_vues_et_colonnes); tests/db/test_lacunes_base.py (ColonneHasHistory, SansBase.test_migration_0003_ajoute_la_colonne_sans_donnee)

#### Scenario: Schema inspection
- WHEN the flow schema's tables and columns are listed after migration
- THEN all five tables exist and no forbidden column name appears

#### Scenario: History flag
- **WHEN** an issue is inserted without the history flag, then flagged, then set to null
- **THEN** the flag reads false, then true, and the null update is refused by a not-null violation

### Requirement: Flow data integrity constraints
The system SHALL reject a transition duplicating an existing one (same ticket, same instant whatever the time zone, same from and to status), a duplicated link, a link whose direction is neither inward nor outward, and a transition referring to an unknown ticket.

Source: tests/db/test_flow_schema.py (test_contraintes_et_doublons)

#### Scenario: Same instant, different offset
- WHEN a transition is inserted twice for the same instant written with two UTC offsets
- THEN the second insert violates a uniqueness constraint

#### Scenario: Invalid link or unknown ticket
- WHEN a link with direction "sideways" is inserted, or a transition for an unknown ticket
- THEN a check violation, respectively a foreign key violation, is raised

### Requirement: Only aggregated team views are exposed, without ticket keys
The system SHALL expose exactly four aggregated flow views (status by team, weekly resolved by team, open ticket age by team, dependencies between teams), and no view SHALL expose a column whose name contains "key".

Source: tests/db/test_flow_schema.py (test_tables_vues_et_colonnes, test_les_vues_ne_montrent_aucune_cle)

#### Scenario: View listing
- WHEN the views of the flow schema are listed
- THEN exactly the four expected views exist and none has a key-like column

### Requirement: Open age and weekly views use time buckets
The system SHALL group open tickets by age bucket relative to the current time in the open-age view (four buckets: up to 7 whole days, 8 to 30, 31 to 90, 91 and more), SHALL leave resolved tickets out of that view, and SHALL cut weeks on Monday at midnight UTC in the weekly-resolved view, whatever the offsets of the stored instants and the session time zone.

Source: tests/db/test_lacunes_base.py (VueAgeDesTicketsOuverts, VueSemainesResolues; run on a disposable database)

#### Scenario: Age buckets
- WHEN the open-age view is read for tickets aged just under and just over each bucket boundary
- THEN each open ticket falls in the bucket matching its age in whole days at the time of reading

#### Scenario: Resolved tickets
- **WHEN** only resolved tickets exist
- **THEN** the open-age view is empty

#### Scenario: Week boundary
- WHEN tickets are resolved just before and just after Monday midnight UTC, written with various offsets and read from a session far from UTC
- THEN the week is cut in UTC

### Requirement: Small counts are masked in the views
The system SHALL return a null count for any view cell aggregating fewer than a minimum number of tickets or links, and SHALL return the real count at or above that minimum.

Source: tests/db/test_flow_schema.py (test_masquage_des_cellules_de_moins_de_cinq)

#### Scenario: Large and small cells
- WHEN a team has many resolved tickets and another has very few open ones, and a single link exists
- THEN the large team's cell shows its count, the small team's cell is null, the dependencies view shows a null link count, and the weekly view shows only the large count

### Requirement: A view-only role reads the views and nothing else
The system SHALL provide a limited role with read access to the four views only: it SHALL be refused on every flow table, on write attempts, on the cases and knowledge schemas, and on object creation. The migration SHALL create this role without login capability.

Source: tests/db/test_flow_schema.py (test_le_role_des_vues_ne_lit_que_les_vues, test_le_role_des_vues_existe_apres_migration)

#### Scenario: Views allowed, tables denied
- WHEN the view-only role selects from each view
- THEN each succeeds
- AND selecting from any flow table, inserting a team, reading cases or knowledge tables, or creating a flow table is refused

### Requirement: Limited roles log in with their own password, never the superuser's
The system SHALL accept a password to be set only for the view-only flow role, the read-only knowledge role, the read-only cases role and the read-write cases role, SHALL refuse a role outside this list before any connection, SHALL refuse a password that is too short, SHALL enable login for the role when its password is set, and SHALL read each limited role's password from its own keychain service or its own environment variable. A connection error as that role SHALL NOT contain the password.

Source: tests/db/test_flow_schema.py (test_connexion_sous_un_role_limite_avec_son_propre_mot_de_passe, SansBase.test_role_password_n_accepte_que_les_roles_de_lecture_limitee, which covers both cases roles); tests/db/test_knowledge_schema.py (test_roles_de_lecture_limitee_et_leur_trousseau); tests/db/test_lacunes_base.py (CommandeRolePassword.test_mot_de_passe_valide_affiche_la_commande_du_trousseau_sans_le_mot_de_passe, for the read-write cases role)

#### Scenario: Setting and using a limited role password
- **WHEN** a role outside the list, or a short password, is passed to the setter
- **THEN** a database error is raised
- **AND** when a listed role gets a valid password, connecting as that role yields a session of that role, while a wrong password gives an error that does not contain the real secret

#### Scenario: Unlisted role
- **WHEN** a connection is requested as a role not in the list (including the superuser)
- **THEN** it is refused before any connection attempt

#### Scenario: Per-role secret lookup
- **WHEN** the keychain service and environment variable names are derived for a limited role, including both cases roles
- **THEN** each is specific to that role and distinct from the superuser's

#### Scenario: Cases roles accepted
- **WHEN** the password setter is called for the read-only or the read-write cases role
- **THEN** it is accepted, while the read-write knowledge and flow roles are still refused

### Requirement: Knowledge schema stores books, collections, memberships and chunks
The system SHALL provide in the knowledge schema exactly four tables (books, collections, book-to-collection links, chunks), owned by the owner role; chunks SHALL carry a vector embedding, a full-text vector, a JSON reference and a kind, with indexes for vector similarity, full text, book and position, kind, and book content hash. The migration SHALL insert no data.

Source: tests/db/test_knowledge_schema.py (test_tables_colonnes_et_index, test_aucune_donnee_dans_les_tables_apres_migration)

#### Scenario: Schema inspection
- WHEN the knowledge schema is inspected after migration
- THEN exactly those four tables exist, all owned by the owner role, the expected columns have the expected types, the expected indexes exist, and every table is empty

### Requirement: Book author and publication date derive from metadata
The system SHALL expose each book's author and publication date derived from its JSON metadata, null when absent.

Source: tests/db/test_knowledge_schema.py (test_plein_texte_sans_accent_et_colonnes_generees)

#### Scenario: Generated columns
- WHEN a book's metadata has an author only, and another has an author and a publication timestamp
- THEN the first book has a null date, the second a date-only value

### Requirement: Full-text search ignores case and accents
The system SHALL match search terms regardless of case and accents on chunk text, through both the full-text vector (simple configuration with accent removal) and the BM25 index (lowercase, ASCII folding, no stemming).

Source: tests/db/test_knowledge_schema.py (test_plein_texte_sans_accent_et_colonnes_generees, test_index_bm25_accents_casse_et_score)

#### Scenario: Accent and case variants
- WHEN the terms "equipe", an uppercase accented form and the accented form are searched
- THEN the same chunk is returned each time

#### Scenario: No stemming, OR semantics
- WHEN a plural form not present in the text is searched
- THEN nothing is returned
- AND WHEN a query lists two words of which only one occurs
- THEN the chunk containing one of them is returned

### Requirement: BM25 index scores matches and is usable by the read-only role
The system SHALL maintain an always-computed searchable text (section plus text) indexed for BM25, SHALL return a positive relevance score for matches, and SHALL let the read-only knowledge role run BM25 queries.

Source: tests/db/test_knowledge_schema.py (test_index_bm25_accents_casse_et_score, test_le_role_de_lecture_peut_chercher_en_bm25)

#### Scenario: Scored top results
- WHEN a BM25 query matches one chunk, ordered by score with a limit
- THEN that chunk is returned with a score greater than zero

#### Scenario: Read-only role
- WHEN the read-only role runs the same query
- THEN it gets the same result

### Requirement: The BM25 migration builds its index without parallel workers and documents its equivalence
The system SHALL, in the BM25 migration, disable parallel maintenance workers before building the index, SHALL name the ASCII-folding tokenizer, and SHALL record in the file the equivalence with the previous SQLite full-text tokenizer settings.

Source: tests/db/test_knowledge_schema.py (SansBase.test_migration_0005_presente_sans_donnee_et_documentee)

#### Scenario: Static content check
- WHEN the BM25 migration is read
- THEN the setting disabling parallel maintenance workers appears before the index creation, and the tokenizer and equivalence notes are present

### Requirement: Chunk kind is constrained and deleting a book cascades
The system SHALL reject a chunk whose kind is outside the allowed set, and SHALL delete a book's chunks and collection links when the book is deleted.

Source: tests/db/test_knowledge_schema.py (test_kind_contraint_et_suppression_en_cascade)

#### Scenario: Invalid kind
- WHEN a chunk is inserted with the kind "texte"
- THEN the insert fails

#### Scenario: Cascade
- WHEN one of two books is deleted by the read-write knowledge role
- THEN one chunk and one membership row remain

### Requirement: Knowledge read-only role cannot modify or create
The system SHALL let the read-only knowledge role count chunks while refusing inserts, deletes and table creation, and SHALL refuse table creation to the read-write knowledge role.

Source: tests/db/test_knowledge_schema.py (test_droits_du_role_d_acces_et_du_role_de_lecture)

#### Scenario: Denied statements
- WHEN the read-only role inserts a collection, deletes chunks or creates a table
- THEN each raises an error, while its select returns the stored count

## Open questions

None. (The cases schema tables are created by a later migration and specified in `cases-schema`.)
