# library-search-knowledge-import

## Purpose

Faithful, incremental, idempotent copy of the SQLite library index into the PostgreSQL `knowledge` schema, with verification and status commands.

Source of truth: `tests/knowledge_import/test_knowledge_import.py`, `tools/knowledge_import.py`, `tools/knowledge_library.py`.

## Requirements

### Requirement: Copy faithfully without recomputing anything
The system SHALL copy books, passages, figure reference records and book metadata from the SQLite index to the database without reconverting books, recomputing vectors or calling the embedding service or the network, SHALL convert each stored half-precision vector into the exact database vector (round trip lossless, including zero, extreme and subnormal values), SHALL map the passage kind "texte" to "text", SHALL give collections their canonical names, and SHALL reject a vector of the wrong size without printing book text.

Source: `tests/knowledge_import/test_knowledge_import.py` (SansBase.test_aller_retour_float16_litteral_halfvec, test_vecteur_de_mauvaise_taille_refuse_sans_texte, test_livres_sqlite_collections_canoniques_et_comptes, test_aucune_importation_d_embed_ni_d_appel_reseau; AvecBase.test_copie_fidele_vecteur_ref_et_meta)

#### Scenario: Vector round trip
- **WHEN** vectors with special and random values are converted to database text and back
- **THEN** the bytes are identical

#### Scenario: Wrong vector size
- **WHEN** a vector blob has the wrong number of dimensions
- **THEN** the import raises an error that mentions dimensions and no text

#### Scenario: Copied values
- **WHEN** an import completes
- **THEN** every stored vector equals its source, a figure keeps its label in its reference record, and an article keeps its URL, author and publication date

#### Scenario: Former collection name
- **WHEN** a book is stored under the former watch name or both names
- **THEN** it is copied under the current name only

### Requirement: Read the source index read-only
The system SHALL open the SQLite index read-only so that any write fails, and SHALL fail with an import error when the index does not exist.

Source: `tests/knowledge_import/test_knowledge_import.py` (SansBase.test_sqlite_ouvert_en_lecture_seule, test_index_introuvable)

#### Scenario: Write attempt
- **WHEN** a delete or an insert is attempted over the import's SQLite connection
- **THEN** the operation fails

#### Scenario: Missing index
- **WHEN** the index path does not exist
- **THEN** an import error is raised

### Requirement: Preserve the SQLite identifier order for ties
The system SHALL copy passages in the order of the SQLite identifiers, so that equal-relevance ties resolve the same way on both paths, while computing the content fingerprint by position then identifier so that it is comparable on both sides.

Source: `tests/knowledge_import/test_knowledge_import.py` (SansBase.test_copie_dans_l_ordre_des_identifiants_sqlite_empreinte_par_position)

#### Scenario: Passage added later at position zero
- **WHEN** a passage with position zero is added to a book after its others
- **THEN** the copy order puts it last while the fingerprint order puts it among the position-zero passages

### Requirement: Fingerprint the content of each book
The system SHALL compute a book fingerprint over, for each passage in order, its position, section, text, kind (text and the SQLite kind name being equivalent), reference record (key order irrelevant) and vector bytes, so that any change to one of these, the order, or the number of passages changes the fingerprint, and SHALL give the same fingerprint on repeated reads.

Source: `tests/knowledge_import/test_knowledge_import.py` (SansBase.test_empreinte, test_empreinte_sqlite_stable_d_un_appel_a_l_autre)

#### Scenario: Equivalent forms
- **WHEN** two passage lists differ only in kind spelling or reference key order
- **THEN** their fingerprints are equal

#### Scenario: Real change
- **WHEN** a text, a vector, the order or the count differs
- **THEN** the fingerprints differ

### Requirement: Import per book, incrementally and idempotently
The system SHALL compare books by file name and add books absent from the database, replace in full (in one transaction) books whose hash, model, title, metadata, collections, index date or passage and figure counts differ, delete books removed from SQLite along with their passages, and leave the others unchanged. It SHALL report counts "to add, to replace, to delete, unchanged". A second import of unchanged data SHALL change nothing and SHALL NOT recreate passages.

Source: `tests/knowledge_import/test_knowledge_import.py` (SansBase.test_plan, AvecBase.test_premier_import_comptes_et_verification, test_second_import_ne_change_rien, test_livre_modifie_remplace_en_entier, test_livre_retire_supprime_sauf_keep_removed)

#### Scenario: First import
- **WHEN** an empty database receives five books
- **THEN** the report says five to add, counts of books, passages, figures and collections equal the source, and verification succeeds

#### Scenario: Second import
- **WHEN** the import is run again
- **THEN** it reports nothing to add, replace or delete and all books unchanged, and passage identifiers are unchanged

#### Scenario: Modified book
- **WHEN** the hash of one book and one passage text change in SQLite
- **THEN** that book alone is replaced and the total passage count is unchanged

#### Scenario: Removed book
- **WHEN** a book is removed from SQLite and the import runs with the keep-removed option, then without
- **THEN** it is kept the first time and deleted with its passages the second time

### Requirement: Probe the BM25 index when verifying
The system SHALL, in the verification command, read the BM25 index like the search does, under the read-only role: one full-text query on common words without a filter and one filtered by passage type (figure). Any error of the probe, such as an internal error "bitmap intersection stream … claimed twice" from a damaged index, SHALL be reported as an unreadable BM25 index and SHALL give exit code 3, which takes precedence over the exit code for differences between the copies (these are printed as well). Each probe query SHALL end its transaction, so that the role does not leak. The probe SHALL repair nothing and its output SHALL hold no text of a book.

Source: `tests/knowledge_import/test_knowledge_import.py` (SondeBm25)

#### Scenario: Readable index
- **WHEN** both probe queries succeed
- **THEN** the verification reports the index as readable and exits 0 if the copies are identical

#### Scenario: Damaged index
- **WHEN** the filtered probe query raises an internal error
- **THEN** the output names the unreadable BM25 index, the failing variant and the error type, points to the rebuild procedure and exit is 3

#### Scenario: Other probe error
- **WHEN** the probe fails for any other reason
- **THEN** the same failure is reported with exit code 3

### Requirement: Detect content drift only on a deep import
The system SHALL compare content fingerprints only with the deep option (which reads all vectors), so that a standard import does not notice an altered passage with unchanged counts, and a deep import SHALL replace the altered book.

Source: `tests/knowledge_import/test_knowledge_import.py` (AvecBase.test_verify_echoue_apres_alteration_et_import_deep_repare)

#### Scenario: Altered text in the database
- **WHEN** a passage is altered in the database, then a standard import and then a deep import run
- **THEN** the standard one reports all unchanged, the deep one replaces one book and verification then succeeds

### Requirement: Remove orphan collections
The system SHALL delete a collection no longer used by any book after an import.

Source: `tests/knowledge_import/test_knowledge_import.py` (AvecBase.test_collection_orpheline_retiree)

#### Scenario: Collection no longer used
- **WHEN** the only book of the author's own collection moves to another collection
- **THEN** that collection no longer exists in the database

### Requirement: Dry run writes nothing
The system SHALL, with the dry-run option, connect read-only, issue only read statements, write nothing, announce the plan and say that nothing was written, and SHALL print no book text.

Source: `tests/knowledge_import/test_knowledge_import.py` (SansBase.test_dry_run_connexion_en_lecture_seule_et_aucun_ordre_d_ecriture, AvecBase.test_dry_run_n_ecrit_rien)

#### Scenario: Empty database
- **WHEN** a dry run targets an empty database
- **THEN** the plan counts five to add and all tables remain empty

#### Scenario: Later dry run
- **WHEN** a dry run is made after one book changed and another was removed
- **THEN** it announces one to replace and one to delete without changing the database

### Requirement: Refuse an empty source against a filled database
The system SHALL refuse, with exit code 1 and a hint to the allow-empty option, to import an index with no book against a database that holds books, and SHALL perform the empty import only with that option.

Source: `tests/knowledge_import/test_knowledge_import.py` (SansBase.test_index_sqlite_vide_face_a_une_base_remplie_refuse, AvecBase.test_index_vide_refuse_sans_allow_empty)

#### Scenario: Empty index
- **WHEN** the index is emptied and an import runs without the option
- **THEN** it fails with exit code 1 and the database keeps its books

#### Scenario: With the option
- **WHEN** the same import runs with the allow-empty option
- **THEN** it succeeds and the database has no book

### Requirement: Leave nothing partial after a copy failure
The system SHALL copy each book in one transaction so that a failing book leaves no book row and no orphan passage, SHALL exit with code 1, and SHALL name the failing file.

Source: `tests/knowledge_import/test_knowledge_import.py` (AvecBase.test_echec_de_copie_ne_laisse_rien_de_partiel)

#### Scenario: Corrupt vector
- **WHEN** one passage of a book has a corrupt vector
- **THEN** the import exits with code 1 naming the file, the book is absent and no passage is orphaned

### Requirement: Use distinct exit codes
The system SHALL exit with 0 on success, 1 on a discrepancy, missing index or copy error, and 2 when the database is unreachable, with a message pointing to the way to start the database, for import, dry run, verify and status.

Source: `tests/knowledge_import/test_knowledge_import.py` (SansBase.test_base_injoignable_code_2_et_message, test_sqlite_introuvable_code_1)

#### Scenario: Database down
- **WHEN** the database cannot be reached
- **THEN** every command exits with code 2 and mentions how to start the database

#### Scenario: Index missing
- **WHEN** verify runs with a missing index
- **THEN** the exit code is 1 and the message says the index was not found

### Requirement: Verify both sides without exposing content
The system SHALL, in verify mode, recompute on both sides the counts (books, passages, figures, collections by canonical name) and each book's fingerprint, SHALL exit with 1 and name an absent book or a book whose fingerprint differs, and SHALL print only counts and file names, never book text.

Source: `tests/knowledge_import/test_knowledge_import.py` (AvecBase.test_premier_import_comptes_et_verification, test_verify_echoue_apres_alteration_et_import_deep_repare, test_verify_signale_un_livre_absent_et_un_vecteur_altere)

#### Scenario: Identical
- **WHEN** verify runs right after an import
- **THEN** exit code 0 and the output says fingerprints are identical

#### Scenario: Altered text
- **WHEN** a passage text is altered in the database
- **THEN** exit code 1, the book file name and "fingerprint" appear and the altered text does not

#### Scenario: Missing book
- **WHEN** a book is deleted from the database
- **THEN** verify exits with 1 and says the book is absent from the database

### Requirement: Spot-check stored vectors on request
The system SHALL, with the vectors option and an optional seed, reread a random sample of vectors from the database and compare them to SQLite, print only the sample size, the maximum difference, the minimum cosine, extreme norms and the number of zero or non-finite vectors, fail with exit code 1 when a vector differs, and be reproducible for a given seed. A single zero vector against a non-zero one SHALL give the lowest cosine; two identical zero vectors SHALL show no difference.

Source: `tests/knowledge_import/test_knowledge_import.py` (Vecteurs, AvecBase.test_verify_vectors_apres_import, test_verify_vectors_detecte_un_vecteur_altere)

#### Scenario: Identical vectors
- **WHEN** twenty vectors are reread after an import
- **THEN** the output says twenty reread, maximum difference zero and a minimum cosine at or near one

#### Scenario: Altered vectors
- **WHEN** all database vectors are replaced
- **THEN** verify exits with 1 and reports the vector difference

#### Scenario: Options
- **WHEN** the command line has the vectors and seed options
- **THEN** they are parsed, with zero vectors checked by default

### Requirement: Report status as counts only
The system SHALL print, for both the database and SQLite, the numbers of books, passages, figures and collections, and nothing else.

Source: `tests/knowledge_import/test_knowledge_import.py` (AvecBase.test_status_comptes_seulement)

#### Scenario: After import
- **WHEN** the status runs after an import
- **THEN** one line for the database and one for SQLite give equal counts
