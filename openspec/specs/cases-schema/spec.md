# cases-schema Specification

## Purpose
The cases schema of the PostgreSQL database: its three tables, integrity constraints, the never-rewritten success criterion, full-text search, and the confinement of the two cases roles.

Source of truth: `tests/db/test_cases_schema.py`, the cases migration under the database migrations folder.
## Requirements
### Requirement: The cases schema stores experiments, their notes and closed cases
The system SHALL provide in the cases schema exactly three tables (experiments, experiment notes, cases), owned by the owner role, created by a migration that inserts no data, contains no password and creates or alters no role. An experiment SHALL record its author, start date, posture, status, problem, context, hypotheses, chosen path, references used, what is tested, expected signal, success criterion, review date, postponement count and an embedding (optional for an experiment, required for a case). A case SHALL record the same description copied from its experiment, its launch and review dates, the history of the experiment's notes, an outcome, a drop reason, what got stuck, a confidence level and an embedding.

Source: `tests/db/test_cases_schema.py` (SansBase, SchemaCases.test_trois_tables_colonnes_index_et_proprietaire, test_tables_vides_apres_migration, test_migration_rejouee_sans_effet)

#### Scenario: Schema inspection
- **WHEN** the cases schema is inspected after all migrations on a disposable database
- **THEN** exactly the three tables exist, all owned by the owner role, with vector, BM25 and lookup indexes, and every table is empty

#### Scenario: Re-running migrations
- **WHEN** the migrations are run a second time
- **THEN** nothing is applied and the cases tables are unchanged

### Requirement: Cases data integrity constraints
The system SHALL reject an experiment whose status, posture or context shape is outside the allowed set, whose hypotheses or references used are not a list, whose postponement count is negative, whose review date is before its start date, or whose author, problem, test, expected signal or success criterion is blank; a note for an unknown experiment or with a blank text; a case whose outcome or confidence is outside the allowed set, whose history is not a list, whose review date is before its launch date, whose outcome is "dropped" without a non-blank drop reason, or whose experiment already has a case. An experiment without posture SHALL be accepted.

Source: `tests/db/test_cases_schema.py` (test_valeurs_refusees_sur_experiments, test_valeurs_refusees_sur_cas, test_un_seul_cas_par_experience_et_note_d_une_experience_inconnue)

#### Scenario: Dropped without reason
- **WHEN** a case is inserted with the outcome "dropped" and no drop reason
- **THEN** a check violation is raised

#### Scenario: One case per experiment
- **WHEN** a second case is inserted for the same experiment
- **THEN** a uniqueness violation is raised

#### Scenario: Invalid enumerations
- **WHEN** an experiment with an unknown status, or a case with an unknown outcome or confidence, is inserted
- **THEN** a check violation is raised

### Requirement: The success criterion is never rewritten
The system SHALL refuse, at the database level, any update that changes the success criterion of an experiment or of a case, and SHALL accept updates that leave it unchanged.

Source: `tests/db/test_cases_schema.py` (test_le_critere_de_reussite_n_est_jamais_reecrit)

#### Scenario: Rewrite attempt
- **WHEN** the read-write cases role updates the success criterion of an experiment or a case
- **THEN** the update is refused and the stored criterion is unchanged

#### Scenario: Other column
- **WHEN** the same role updates the status or the review date of an experiment
- **THEN** the update succeeds

### Requirement: Cases full text ignores case and accents and is searchable by the read-only role
The system SHALL index for BM25 a generated text made of the problem, the chosen path and what is tested, for both experiments and cases, with the same tokenizer as the library (lowercase, accents removed, no stemming), and SHALL let the cases read-only role run BM25 and vector queries on it.

Source: `tests/db/test_cases_schema.py` (SansBase.test_travailleurs_paralleles_coupes_avant_le_premier_index_bm25, test_bm25_trouve_un_mot_accentue_ecrit_sans_accent_en_lecture_seule)

#### Scenario: Accent-free query
- **WHEN** the cases read-only role searches a word without its accents
- **THEN** the case whose problem contains the accented word is returned with a positive score

### Requirement: Cases roles are confined to the cases schema
The system SHALL let the cases read-only role only read the cases tables, and the cases read-write role only read and write them; neither SHALL create or drop objects, and neither SHALL read the knowledge or flow schemas.

Source: `tests/db/test_cases_schema.py` (test_le_role_de_lecture_ne_fait_que_lire, test_le_role_d_ecriture_ecrit_mais_ne_cree_ni_ne_lit_ailleurs); `tests/cases_store/test_cases_store.py` (Lancement.test_le_role_lecture_seule_ne_peut_pas_lancer)

#### Scenario: Read-only role
- **WHEN** the cases read-only role inserts an experiment, deletes a case or creates a table
- **THEN** each statement is refused while its selects succeed

#### Scenario: Read-write role
- **WHEN** the cases read-write role inserts an experiment, then creates a table or reads a knowledge table
- **THEN** the insert succeeds and the two other statements are refused

## Open questions

None.

