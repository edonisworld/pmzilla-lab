# library-search-knowledge-import

## Purpose

Faithful, incremental, idempotent copy of the SQLite library index into the PostgreSQL `knowledge` schema, with verification and status commands.

Source of truth: `tests/knowledge_import/test_knowledge_import.py`, `tools/knowledge_import.py`, `tools/knowledge_library.py`.
## Requirements
### Requirement: Read the source index read-only
The system SHALL open the SQLite index read-only so that any write fails, in the verification and status commands, and SHALL fail with exit code 1 and a message saying the index was not found when it does not exist. It SHALL NOT create the index file.

Source: `tests/knowledge_import/test_knowledge_import.py` (SansBase.test_sqlite_ouvert_en_lecture_seule, test_index_introuvable)

#### Scenario: Write attempt
- **WHEN** a delete or an insert is attempted over the SQLite connection of the verification
- **THEN** the operation fails

#### Scenario: Missing index
- **WHEN** the index path does not exist
- **THEN** the verification exits with code 1 saying the index was not found, and no file is created

### Requirement: Fingerprint the content of each book
The system SHALL compute a book fingerprint over, for each passage in order of position then identifier, its position, section, text, kind (text and the SQLite kind name being equivalent), reference record (key order irrelevant) and, except in the parity comparison, its vector bytes, so that any change to one of these, the order, or the number of passages changes the fingerprint, and SHALL give the same fingerprint on repeated reads. The parity comparison SHALL use the fingerprint without vector bytes and SHALL NOT let a vector difference change it.

Source: `tests/knowledge_import/test_knowledge_import.py` (SansBase.test_empreinte, test_empreinte_sqlite_stable_d_un_appel_a_l_autre)

#### Scenario: Equivalent forms
- **WHEN** two passage lists differ only in kind spelling or reference key order
- **THEN** their fingerprints are equal

#### Scenario: Real change
- **WHEN** a text, a vector, the order or the count differs
- **THEN** the full fingerprints differ

#### Scenario: Vector-only difference in the parity comparison
- **WHEN** two passage lists differ only in vector bytes
- **THEN** their fingerprints without vector bytes are equal

### Requirement: Use distinct exit codes
The system SHALL exit with 0 on success, 1 on a discrepancy, a missing index or a refused import, and 2 when the database is unreachable, with a message pointing to the way to start the database, for the verification (with or without the parity option) and status commands. It SHALL NOT use exit code 3, the BM25 probe having moved to the indexer.

Source: `tests/knowledge_import/test_knowledge_import.py` (SansBase.test_base_injoignable_code_2_et_message, test_sqlite_introuvable_code_1)

#### Scenario: Database down
- **WHEN** the database cannot be reached
- **THEN** verification and status exit with code 2 and mention how to start the database

#### Scenario: Index missing
- **WHEN** verify runs with a missing index
- **THEN** the exit code is 1 and the message says the index was not found

### Requirement: Verify both sides without exposing content
The system SHALL, in verify mode, recompute on both sides the counts (books, passages, figures, collections by canonical name) and each book's fingerprint, SHALL exit with 1 and name an absent book or a book whose fingerprint differs, and SHALL print only counts, file names and verdicts, never book text. It SHALL read the database under the read-only role and SHALL NOT write to the database nor run the BM25 probe.

Source: `tests/knowledge_import/test_knowledge_import.py` (AvecBase.test_verify_signale_un_livre_absent_et_un_vecteur_altere), to be rebuilt on a database loaded by plain inserts.

#### Scenario: Identical
- **WHEN** both sides hold the same books and passages
- **THEN** exit code 0 and the output says fingerprints are identical

#### Scenario: Altered text
- **WHEN** a passage text is altered in the database
- **THEN** exit code 1, the book file name and "fingerprint" appear and the altered text does not

#### Scenario: Missing book
- **WHEN** a book is absent from the database
- **THEN** verify exits with 1 and says the book is absent from the database

### Requirement: Spot-check stored vectors on request
The system SHALL, with the vectors option and an optional seed, reread a random sample of vectors from the database and compare them to SQLite, print only the sample size, the maximum difference, the minimum cosine, extreme norms and the number of zero or non-finite vectors, fail with exit code 1 when a vector differs (or, with the parity option, when the minimum cosine is below the tolerance), and be reproducible for a given seed. A single zero vector against a non-zero one SHALL give the lowest cosine; two identical zero vectors SHALL show no difference. It SHALL NOT print any book text.

Source: `tests/knowledge_import/test_knowledge_import.py` (Vecteurs)

#### Scenario: Identical vectors
- **WHEN** twenty identical vectors are reread
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

### Requirement: Refuse the retired import command
The system SHALL refuse the import command, with or without any of its former options, with exit code 1 and the message of design.md D6 that names the indexer as the way the library now reaches the database. It SHALL NOT connect to the database, SHALL NOT open the SQLite index and SHALL write nothing.

#### Scenario: Import requested
- **WHEN** the import command is run, alone or with the dry-run or deep option
- **THEN** the exit code is 1, the output names the indexer, and no connection is attempted

### Requirement: Compare the former path with the database during the parity window
The system SHALL provide, with the parity option of the verification command and a start date, a comparison between the SQLite index fed by the former path and the database fed by the indexer: counts on both sides (books, passages, figures, collections by canonical name); per book, title, metadata, collections, content hash and model; per book, the content fingerprint without vector bytes; and, for every book indexed on or after the start date on both sides, every passage vector, reporting the minimum cosine, the number of such books, how many are byte-identical, and zero or non-finite vectors. Books indexed after the start date on one side only SHALL be counted and left out of the vector comparison. The verdict SHALL be "identique" with exit 0 when counts, fields and fingerprints are equal and the minimum cosine reaches a configurable tolerance, and "écart" with exit 1 otherwise, naming differing books by file name only. It SHALL append one line to the parity log of the data folder (date, verdict, counts, re-embedded books, byte-identical books, minimum cosine), SHALL print the number of consecutive "identique" days counted from that log, where an "écart" line resets the count and a day without a line neither counts nor resets, and SHALL NOT write file names or book text into the log nor anything into the database.

#### Scenario: Same content, close vectors
- **WHEN** both sides hold the same books and the vectors of a book re-embedded on both sides differ by less than the tolerance
- **THEN** the verdict is "identique", exit code 0, a log line is appended and the consecutive count grows by one

#### Scenario: Different passage text
- **WHEN** one passage text differs between the two sides
- **THEN** the verdict is "écart", exit code 1, the output names the book file, the log line holds no file name, and the next count starts again from zero

#### Scenario: Recompute on one side only
- **WHEN** a book was re-embedded after the start date on the database side only
- **THEN** its vectors are not compared, it is counted as one-sided, and its fingerprint without vectors is still compared

