# library-search-parity

## Purpose

Regression guard of the library search: the results of a frozen bilingual query set are compared with a snapshot recorded by hand, so that a silently degraded index (after a REINDEX, a migration or a change of the search code) does not go unnoticed: overlap, verdict, latency, per-component runs, plan inspection, changes of the library since the snapshot, and report confidentiality.

Source of truth: `tests/parity/test_parity.py`, `tests/parity/test_parity_main.py`, `tests/parity/queries.yaml` (structure only), `tools/library_parity.py`.

## Requirements

### Requirement: Measure overlap of the top results of two paths
The system SHALL run every query of the set on the PostgreSQL search with the snapshot's limit, filters and freshness date, SHALL compare its top results with the snapshot's as (file, position) pairs and SHALL record, per query, how many results are common. It SHALL compute each query embedding before starting the latency clock. It SHALL NOT run any other search route.

Source: `tests/parity/test_parity.py` (Mesure)

#### Scenario: Full, half and no overlap
- **WHEN** the search returns eight, four or zero of the eight results of the snapshot
- **THEN** the per-query common count is eight, four or zero

#### Scenario: Limit and filters forwarded
- **WHEN** a query of the set has collections and types
- **THEN** the search receives them, with the snapshot's limit and freshness date, and the common count is bounded by the limit

#### Scenario: Warm-up
- **WHEN** a run starts
- **THEN** each question is embedded before its latency is measured

### Requirement: Give a verdict from mean overlap, worst query and rare queries
The system SHALL declare parity with the snapshot when the mean overlap reaches a threshold, no query falls under a minimum overlap, and every query marked rare shares at least a stricter minimum of results. It SHALL expose the mean, the minimum, the worst query, the queries below the minimum and the failing rare queries, and SHALL let the mean threshold be set from the command line.

Source: `tests/parity/test_parity.py` (Mesure.test_moyenne_minimum_et_pire_requete, test_verdict_parite, test_seuil_de_la_moyenne, test_requete_rare_exige_7_sur_8)

#### Scenario: Identical results
- **WHEN** the search returns the snapshot's results for every query
- **THEN** the verdict is parity with a mean of one

#### Scenario: One query without overlap
- **WHEN** one of three queries has no common result with the snapshot
- **THEN** the mean is the average of the three, the minimum is zero, that query is named worst and below the minimum, and the verdict is not parity

#### Scenario: Mean threshold
- **WHEN** the mean is slightly under the default threshold
- **THEN** the verdict fails by default and succeeds with a lower threshold given

#### Scenario: Rare query
- **WHEN** a rare query shares fewer results than the rare-query minimum
- **THEN** it is listed as a failing rare query and the verdict is not parity even with a low threshold

### Requirement: Report latency for each path
The system SHALL measure the search duration of each query on the PostgreSQL search, excluding embedding, and SHALL report a latency summary including a 95th percentile.

Source: `tests/parity/test_parity.py` (Mesure.test_latences, Rapport.test_rapport_sans_texte_ni_titre)

#### Scenario: Timings
- **WHEN** a controlled clock gives durations for two queries
- **THEN** the latency list matches and the 95th percentile is computed from it

### Requirement: Measure one component on request
The system SHALL record and compare one chosen component (semantic only or keyword only) when it is requested, SHALL call the search without a component parameter when the component is the default (both), SHALL refuse to compare a component different from the snapshot's, and SHALL label the report with the component and mark each query "ok" or "gap" with its latency.

Source: `tests/parity/test_parity.py` (Composante)

#### Scenario: Semantic only
- **WHEN** a snapshot was recorded for the semantic component and the comparison asks for it
- **THEN** the search is called with it

#### Scenario: Default component
- **WHEN** no component is chosen (the default, both)
- **THEN** the search is called without a component parameter, at record and at comparison alike

#### Scenario: Per-query verdict
- **WHEN** one query has no overlap in a keyword-only comparison
- **THEN** the report line of that query says gap, the other says ok, and both show their latency in milliseconds

### Requirement: Keep the report free of book content
The system SHALL print by default only query identifiers, overlap, verdict, latency and the counts of library changes, SHALL add file:position pairs only with the details option, SHALL never print passage text or titles, SHALL state the verdict ("parity not reached" when it fails), and SHALL write no file during a comparison.

Source: `tests/parity/test_parity.py` (Rapport.test_rapport_sans_texte_ni_titre, Rapport.test_aucun_fichier_ecrit)

#### Scenario: Default summary
- **WHEN** a report is rendered
- **THEN** no file name and no passage text appears

#### Scenario: Details
- **WHEN** details are requested
- **THEN** file:position pairs found only in the snapshot or only in the current results are listed, but no text

#### Scenario: No file
- **WHEN** a comparison is run and rendered in an empty directory
- **THEN** the directory is still empty and the snapshot is unchanged

### Requirement: Show the query plan without literals
The system SHALL offer a plan mode for a single query on the PostgreSQL path only, SHALL run the query with an execution-analysing explain inside a transaction it rolls back, and SHALL redact from the plan every literal (question words, collections, dates, vector) while keeping nodes, indexes, row counts and times.

Source: `tests/parity/test_parity.py` (Plan)

#### Scenario: Redaction
- **WHEN** a plan containing a question text, a date, a vector and an array literal is rendered
- **THEN** none of those values appear and the node names, row counts and execution time remain

#### Scenario: Rollback
- **WHEN** the plan is requested
- **THEN** setup statements run first, the explain statement runs with its parameters and the transaction is rolled back

### Requirement: Refuse a BM25 run when the migration is missing and refuse out-of-range options
The system SHALL exit with code 2 and say the keyword-index migration is absent, before any connection, when the BM25 option is chosen on a repository lacking that migration; SHALL refuse a search-breadth option outside the supported range; and SHALL expose defaults for breadth and scan consistent with the search module. The normalisation-flag option SHALL accept exactly the values the query builder accepts.

Source: `tests/parity/test_parity.py` (Plan.test_option_explain_de_la_ligne_de_commande, EfSearch, Rapport.test_bm25_non_disponible_tant_que_la_migration_manque), `tests/hybrid_search/test_hybrid_search.py` (DepartageEtNormalisation.test_option_rank_norm_de_la_parite_aligne_sur_la_validation)

#### Scenario: Missing migration
- **WHEN** the BM25 option is used and the migration is absent
- **THEN** the exit code is 2 and the message says the migration is absent

#### Scenario: Breadth out of range
- **WHEN** the breadth is above the supported range
- **THEN** the command exits with an argument error

#### Scenario: Normalisation flag
- **WHEN** the flag is set to a supported value, to an unsupported value, or omitted
- **THEN** it is parsed, refused with an argument error, or left unset

### Requirement: Validate the query set
The system SHALL refuse a query set that is empty, not a list, has an empty query, an unknown language, a duplicate identifier or an unknown key, with a parity error that holds neither book text nor secret.

Source: `tests/parity/test_parity.py` (Rapport.test_jeu_de_requetes_invalide_refuse)

#### Scenario: Invalid sets
- **WHEN** each of the following is loaded: empty list, wrong shape, empty query, language other than French or English, duplicate identifier, unknown key
- **THEN** each raises a parity error

### Requirement: Keep the frozen query set large, bilingual and free of excerpts
The frozen query set SHALL be a readable YAML mapping with unique identifiers, SHALL contain enough queries in both French and English, SHALL contain only short phrasings (not copied sentences), no link, no ticket key, no organisation or person name, SHALL declare only valid passage types and list collections, and SHALL include at least one rare query and at least one with passage types.

Source: `tests/parity/test_parity.py` (JeuFige)

#### Scenario: Size and languages
- **WHEN** the set is loaded
- **THEN** it has at least a minimum number of queries, unique identifiers, and a minimum per language

#### Scenario: Confidentiality
- **WHEN** the file text is scanned
- **THEN** it has no link, no ticket-like key and no organisation or author name

#### Scenario: Coverage
- **WHEN** the entries are inspected
- **THEN** their types are within text and figure, collections are lists, and rare and typed queries exist

### Requirement: Exit with a code reflecting the verdict
The system SHALL exit with 0 when parity with the snapshot is reached, 1 when it is not, and 2 when the measurement could not be made (no snapshot, query set changed, settings differ, database unreachable).

Source: `tests/parity/test_parity_main.py` (CodeDeSortie), `tests/parity/test_parity.py` (code-2 paths)

#### Scenario: Parity reached
- **WHEN** a full comparison finds the snapshot's results for every query
- **THEN** the exit code is 0 and the report does not say parity was not reached

#### Scenario: Parity not reached
- **WHEN** a full comparison shares no result with the snapshot
- **THEN** the exit code is 1 and the report says parity was not reached

#### Scenario: Not measurable
- **WHEN** the measurement cannot be made
- **THEN** the exit code is 2

### Requirement: Record a snapshot of the PostgreSQL results
The system SHALL offer a record command that runs the frozen query set on the PostgreSQL search and writes one owner-only snapshot file in the data folder, with the content listed in design D5. It SHALL print only counts and the snapshot path. It SHALL refuse to replace an existing snapshot without the replace option (exit 2, "snapshot exists"). It SHALL write nothing else.

#### Scenario: First record
- **WHEN** the record command runs with no snapshot present
- **THEN** one owner-only snapshot file is written in the data folder and the output holds counts and its path only

#### Scenario: Snapshot already present
- **WHEN** the record command runs while a snapshot exists and no replace option is given
- **THEN** it exits with code 2, says "snapshot exists" and leaves the snapshot unchanged

#### Scenario: Replace
- **WHEN** the replace option is given
- **THEN** the snapshot is rewritten with the current results

#### Scenario: Snapshot content
- **WHEN** a snapshot is recorded
- **THEN** it holds, per query, the ordered (file, position) results, plus the settings, the freshness date, the query-set fingerprint and the books with their content fingerprint, and no passage text or title

### Requirement: Refuse a comparison that the snapshot cannot support
The system SHALL, before running any query, exit with code 2 and the key phrases of design D5 when no snapshot exists ("no snapshot"), when the frozen query set changed since the snapshot ("query set changed since the snapshot"), or when a search option given on the command line differs from the snapshot's settings ("settings differ from the snapshot"). Without options, the comparison SHALL use the snapshot's settings and its freshness date.

#### Scenario: No snapshot
- **WHEN** a comparison is started and the data folder holds no snapshot
- **THEN** the exit code is 2, the message points to the record command, and no query is run

#### Scenario: Different scan
- **WHEN** the snapshot was recorded with the approximate scan and the exact scan is requested
- **THEN** the exit code is 2 and the message says the settings differ

### Requirement: Report how the library changed since the snapshot
The system SHALL report, with every comparison, the number of books added, removed and changed (different content fingerprint) since the snapshot, as counts only, without file names unless the details option is given and never with titles or text.

#### Scenario: New watch articles
- **WHEN** three articles were indexed after the snapshot
- **THEN** the report says three books were added and the verdict is computed as usual
