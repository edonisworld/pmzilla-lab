# cases-search Specification

## Purpose
Search of closed cases and running experiments (hybrid search, similarity threshold, hit contents), the provisional calibration of the threshold, and the three read-only cases tools of the library server.

Source of truth: `tests/cases_store/test_cases_store.py`, `tests/cases_store/test_cases_calibration.py`, `tests/pmzilla_lab_library/test_cases_tools.py`, `tools/cases_store.py`, `tools/cases_calibration.py`, `tools/pmzilla_lab_library.py`.
## Requirements
### Requirement: Cases and running experiments are searched with the library's hybrid search
The system SHALL search cases and running experiments with the same hybrid search as the library (semantic list and BM25 keyword list fused by reciprocal rank, approximate vector scan with the library's default breadth, same candidate count and tie-breaking), through table specifications only, without a second implementation of the fusion. Every hit SHALL receive the neutral freshness bonus, and no collection, date or passage-type filter SHALL be generated. An empty question SHALL be refused, an unavailable embedding service SHALL be reported as such, and a search SHALL never write and SHALL leave no transaction open.

Source: `tests/cases_store/test_cases_store.py` (RechercheSansBase, Recherche.test_le_plus_proche_d_abord_seuil_applique, test_la_transaction_de_lecture_est_annulee)

#### Scenario: Same search code
- **WHEN** the cases search query is built
- **THEN** it is produced by the library's hybrid query builder with a cases table specification, BM25 and the approximate scan

#### Scenario: Closest case first
- **WHEN** invented cases are searched with a question close to one of them
- **THEN** that case is the first hit

### Requirement: Hits below the similarity threshold are dropped
The system SHALL compute, for each hybrid hit, the semantic similarity (dot product) between the question and the hit, SHALL drop hits below a configurable threshold, SHALL keep the hybrid order for the others, and SHALL return at most the requested number of hits (a configurable default when none is requested), bounded by a configurable maximum and by one at the low end; a limit that is not a whole number SHALL be refused. The threshold SHALL ship with a provisional value proposed by the calibration command. While the threshold has no value, the case and experiment searches SHALL refuse with an error saying the threshold is not calibrated, before computing any embedding or reading the database.

Source: `tests/cases_store/test_cases_store.py` (Import.test_constantes, RechercheSansBase.test_bornes_de_limite, test_seuil_non_calibre_refuse_les_deux_recherches, Recherche.test_ligne_a_04_ecartee_ligne_a_06_gardee, test_limite_par_defaut_et_bornee, test_question_sans_rapport_resultat_vide)

#### Scenario: Limit bound
- **WHEN** a limit above the maximum is requested
- **THEN** at most the maximum number of hits is returned

#### Scenario: Unrelated question
- **WHEN** a question unrelated to every invented case is searched
- **THEN** the result is empty

#### Scenario: Threshold not calibrated
- **WHEN** the threshold has no value and a case search is called
- **THEN** an error says the similarity threshold is not calibrated and no hit is returned

### Requirement: The provisional threshold is proposed from the invented evaluation set by a fixed rule
The system SHALL provide a calibration command that, for the evaluation cases that name a cases fixture and for each language, computes the similarity between each question and each fixture entry, labels as related the pair made of a question and the first entry of its own fixture and as unrelated every other pair of the same language, and proposes as threshold the midpoint between the highest unrelated and the lowest related similarity, rounded down to two decimals, only when that value stays strictly above the highest unrelated similarity; otherwise it SHALL report that there is no separation and propose no value. It SHALL print identifiers, labels and numbers only, never a question or a fixture text, and SHALL read no database. It SHALL accept one language or both (the default), print one line per pair with its similarity, then the highest unrelated and the lowest related similarities, then the proposed value or the absence of separation. When the embedding service is unavailable it SHALL print an error and exit with code 1 (read in the code).

Source: `tests/cases_store/test_cases_calibration.py` (EmbeddingIndisponible); `tools/cases_calibration.py` (main)

#### Scenario: Separation
- **WHEN** the lowest related similarity is 0.71 and the highest unrelated is 0.52
- **THEN** the proposed threshold is 0.61

#### Scenario: No separation
- **WHEN** the lowest related similarity is not above the highest unrelated one
- **THEN** no threshold is proposed and the output says there is no separation

#### Scenario: Pairs of the shipped set
- **WHEN** the pairs are built for the three shipped cases with fixtures in one language
- **THEN** there are three related pairs and nine unrelated pairs, and the output holds no question or fixture text

### Requirement: Case hits carry what a citation needs
The system SHALL return for each case hit its number, author, launch and review dates, posture, description fields, note history, outcome, drop reason, what got stuck, confidence, similarity and score.

Source: `tests/cases_store/test_cases_store.py` (Recherche.test_fiche_d_un_cas)

#### Scenario: Case hit
- **WHEN** a case is found
- **THEN** the hit carries its number, author, review date and outcome, among the other fields

### Requirement: Experiment search returns running experiments only and flags the user's own
The system SHALL return from the experiment search only running experiments, with their number, author, dates, description fields, number of notes, similarity and score, and a flag telling whether the experiment belongs to the configured author; without a configured author no hit SHALL be flagged.

Source: `tests/cases_store/test_cases_store.py` (Recherche.test_experiences_en_cours_seulement_et_mine, test_mine_faux_partout_sans_auteur, test_experience_close_ou_abandonnee_n_est_jamais_rendue)

#### Scenario: Closed or dropped experiment
- **WHEN** a closed or dropped experiment matches the question
- **THEN** it is not returned

#### Scenario: Own experiment
- **WHEN** a running experiment of the configured author matches
- **THEN** its hit is flagged as the user's own, and another author's experiment is not

### Requirement: The library server exposes three read-only cases tools
The system SHALL add to the library MCP server a case search tool, a running-experiment search tool and a due-review listing tool, all connected to the cases schema under the cases read-only role, opening that connection at the first cases call and retrying a lost connection once. The database used for cases SHALL be replaceable by an environment setting. The due-review tool SHALL list the configured author's running experiments whose review date is today or past, oldest first, each with its postponement count and a flag when a decision between close and drop is required. The server SHALL then declare seven tools, none of which writes; the cases reader SHALL be created at the first cases call, not at server start, and only once per server.

Source: `tests/pmzilla_lab_library/test_cases_tools.py` (Inventaire, Reponses.test_avec_un_faux_lecteur_les_trois_outils_renvoient_des_listes, test_le_lecteur_n_est_pas_cree_au_demarrage, Fabrique); `tests/cases_store/test_cases_store.py` (ConnectCases, LecteurParesseux, Echeances.test_bilans_dus_du_plus_ancien_au_plus_recent)

#### Scenario: Read-only
- **WHEN** a write is attempted over the cases connection of the server
- **THEN** the database refuses it

#### Scenario: Database setting
- **WHEN** the cases database setting names another database
- **THEN** the cases tools connect to that database and the library tools are unaffected

#### Scenario: Due reviews
- **WHEN** the author has one experiment due yesterday with two postponements and one due next week
- **THEN** only the first is listed, flagged as requiring a decision

### Requirement: Cases tools answer errors without stopping the server
The system SHALL answer a cases tool call with an error object, and keep the server running, when the cases database does not answer (no secret in the message), when the server uses the SQLite backend, when the question is empty, when the similarity threshold is not calibrated, or, for the due-review tool, when no author is configured. The four library tools SHALL answer as before whatever the state of the cases connection. An empty question and the SQLite backend SHALL be answered without creating the cases reader; an empty result SHALL stay an empty list.

Source: `tests/pmzilla_lab_library/test_cases_tools.py` (Reponses)

#### Scenario: Cases database down
- **WHEN** the cases database does not answer and a case search is called
- **THEN** an error object pointing to the database start script is returned, and a following library search still answers

#### Scenario: SQLite backend
- **WHEN** the server runs with the SQLite backend and a cases tool is called
- **THEN** an error object says the cases module requires the PostgreSQL backend

## Open questions

None.

