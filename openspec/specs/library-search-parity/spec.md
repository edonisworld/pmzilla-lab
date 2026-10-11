# library-search-parity

## Purpose

Measurement of how closely the PostgreSQL search path agrees with the SQLite path on a frozen query set: overlap, verdict, latency, per-component runs, plan inspection, and report confidentiality.

Source of truth: `tests/parity/test_parity.py`, `tests/parity/test_parity_main.py`, `tests/parity/queries.yaml` (structure only), `tools/library_parity.py`.
## Requirements
### Requirement: Measure overlap of the top results of two paths
The system SHALL run every query of the set on both paths with the same limit and filters, SHALL compare the top results as (file, position) pairs and SHALL record, per query, how many results are common. It SHALL compute the query embedding once and share it so that only the search differs, and SHALL do so before starting the latency clock.

Source: `tests/parity/test_parity.py` (Mesure.test_recouvrement_8_sur_8_4_sur_8_0_sur_8, Mesure.test_limite_et_filtres_transmis, Mesure.test_embedding_calcule_avant_la_mesure_de_latence)

#### Scenario: Full, half and no overlap
- **WHEN** the two paths return eight, four or zero common results out of eight
- **THEN** the per-query common count is eight, four or zero

#### Scenario: Limit and filters forwarded
- **WHEN** a query has collections and types and a limit is given, or a global collection filter is set
- **THEN** both paths receive the same arguments and the common count is bounded by the limit

#### Scenario: Warm-up
- **WHEN** a run starts
- **THEN** each question is embedded before its latency is measured

### Requirement: Give a verdict from mean overlap, worst query and rare queries
The system SHALL declare parity when the mean overlap reaches a threshold, no query falls under a minimum overlap, and every query marked rare shares at least a stricter minimum of results. It SHALL expose the mean, the minimum, the worst query, the queries below the minimum and the failing rare queries, and SHALL let the mean threshold be set from the command line.

Source: `tests/parity/test_parity.py` (Mesure.test_moyenne_minimum_et_pire_requete, test_verdict_parite, test_seuil_de_la_moyenne, test_requete_rare_exige_7_sur_8)

#### Scenario: Identical results
- **WHEN** both paths return the same results
- **THEN** the verdict is parity with a mean of one

#### Scenario: One query without overlap
- **WHEN** one of three queries has no common result
- **THEN** the mean is the average of the three, the minimum is zero, that query is named worst and below the minimum, and the verdict is not parity

#### Scenario: Mean threshold
- **WHEN** the mean is slightly under the default threshold
- **THEN** the verdict fails by default and succeeds with a lower threshold given

#### Scenario: Rare query
- **WHEN** a rare query shares fewer results than the rare-query minimum
- **THEN** it is listed as a failing rare query and the verdict is not parity even with a low threshold

### Requirement: Report latency for each path
The system SHALL measure the search duration of each path per query, excluding embedding, and SHALL report per path a latency summary including a 95th percentile.

Source: `tests/parity/test_parity.py` (Mesure.test_latences, Rapport.test_rapport_sans_texte_ni_titre)

#### Scenario: Timings
- **WHEN** a controlled clock gives durations for two queries
- **THEN** per-path latency lists match and the 95th percentile of the PostgreSQL path is computed from them

### Requirement: Measure one component on request
The system SHALL pass a chosen component (semantic only or keyword only) to both paths, SHALL call paths without a component parameter when the component is the default (both), and SHALL label the report with the component and mark each query "ok" or "gap" with both latencies.

Source: `tests/parity/test_parity.py` (Composante)

#### Scenario: Semantic only
- **WHEN** the semantic component is chosen
- **THEN** both paths are called with it

#### Scenario: Default component
- **WHEN** no component is chosen
- **THEN** simple backends that lack the component parameter still work

#### Scenario: Per-query verdict
- **WHEN** one query has no overlap in a keyword-only run
- **THEN** the report line of that query says gap, the other says ok, and both show their latencies in milliseconds

### Requirement: Keep the report free of book content
The system SHALL print by default only query identifiers, overlap, verdict and latency, SHALL add file:position pairs only with the details option, SHALL never print passage text or titles, SHALL state the verdict ("parity not reached" when it fails), and SHALL write no file.

Source: `tests/parity/test_parity.py` (Rapport.test_rapport_sans_texte_ni_titre, Rapport.test_aucun_fichier_ecrit)

#### Scenario: Default summary
- **WHEN** a report is rendered
- **THEN** no file name and no passage text appears

#### Scenario: Details
- **WHEN** details are requested
- **THEN** file:position pairs specific to each path are listed, but no text

#### Scenario: No file
- **WHEN** a report is built and rendered in an empty directory
- **THEN** the directory is still empty

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
The system SHALL exit with 0 when parity is reached, 1 when it is not, and 2 when the measurement could not be made.

Source: `tests/parity/test_parity_main.py` (CodeDeSortie.test_parite_atteinte_code_0, test_parite_non_atteinte_code_1), `tests/parity/test_parity.py` (code-2 paths)

#### Scenario: Parity reached
- **WHEN** a full run compares two paths that return the same results for every query
- **THEN** the exit code is 0 and the report does not say parity was not reached

#### Scenario: Parity not reached
- **WHEN** a full run compares two paths that share no result
- **THEN** the exit code is 1 and the report says parity was not reached

#### Scenario: Not measurable
- **WHEN** the measurement cannot be made
- **THEN** the exit code is 2

### Requirement: Report collection-restricted queries apart
The system SHALL identify in the parity report the queries that ran with a collection restriction (from the query set or from the global option), and SHALL give their overlap separately from the other queries, so that a divergence between the paths that follows from the different order of filter and candidate limit is not read as a regression of the unrestricted queries. The report SHALL stay free of book content. Restricted queries SHALL stay in the overall verdict.

Source: `tests/parity/test_parity.py` (GroupeRestreint)

#### Scenario: Mixed query set
- **WHEN** some queries carry a collection restriction and others do not
- **THEN** the report gives the mean overlap of each group separately in addition to the overall verdict

#### Scenario: Global restriction
- **WHEN** a global collection restriction is given on the command line
- **THEN** every query is reported in the restricted group

#### Scenario: No restricted query
- **WHEN** no query is restricted
- **THEN** the report has no restricted group and the verdict is unchanged

