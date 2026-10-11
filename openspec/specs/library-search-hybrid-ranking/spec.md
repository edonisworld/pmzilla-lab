# library-search-hybrid-ranking

## Purpose

Hybrid ranking of library passages: a semantic list and a keyword list fused by reciprocal rank, a freshness bonus for recent watch articles, tie-breaking rules, filters, and the SQL formulation of the same ranking for the PostgreSQL path.

Source of truth: `tests/hybrid_search/test_hybrid_search.py`, `tests/pmzilla_lab_library/test_pmzilla_lab_library.py`, `tools/hybrid_search.py`, `tools/pmzilla_lab_library.py`.
## Requirements
### Requirement: Fuse a semantic ranking and a keyword ranking by reciprocal rank
The system SHALL rank passages by building a semantic list (vector similarity, dot product without renormalisation) and a keyword list, and SHALL score each passage by the sum of a reciprocal-rank contribution over the lists in which it appears, plus a freshness bonus. A passage present in both lists SHALL outrank a passage present in only one at the same position.

Source: `tests/hybrid_search/test_hybrid_search.py` (FusionEtFraicheur.test_fusion_valeurs_a_la_main, FusionEtFraicheur.test_fusion_identique_a_library_search)

#### Scenario: Passage in both lists
- **WHEN** two lists are fused and passage "a" is first in both while passage "b" is first in only one
- **THEN** "a" is ranked above "b" and its score is the sum of its two reciprocal-rank contributions

#### Scenario: Empty input
- **WHEN** no list is given to the fusion
- **THEN** the result is empty

#### Scenario: Result limit
- **WHEN** a limit smaller than the number of fused passages is given
- **THEN** only that many best passages are returned

### Requirement: Keep the pure-Python fusion identical to the SQLite path
The system SHALL expose the fusion and the freshness bonus as pure functions that give the same order and the same scores (rounded) as the SQLite search path, and SHALL share the fusion constants with that path.

Source: `tests/hybrid_search/test_hybrid_search.py` (Constantes.test_memes_constantes_que_la_voie_sqlite, FusionEtFraicheur.test_fusion_identique_a_library_search)

#### Scenario: Same ranking on a demo library
- **WHEN** several questions (French, English, no known word) are run through the pure fusion and through the SQLite search on the same demo library
- **THEN** the ordered passage identifiers and the rounded scores are equal

### Requirement: Split a question into words
The system SHALL split a question into word tokens on Unicode word characters, so that apostrophes, hyphens and punctuation separate words and a question made only of punctuation yields no word.

Source: `tests/hybrid_search/test_hybrid_search.py` (Constantes.test_mots_comme_la_voie_sqlite), `tests/pmzilla_lab_library/test_pmzilla_lab_library.py` (Recherche.test_requete_sans_mot)

#### Scenario: Elision and hyphens
- **WHEN** the question "Le flux, l'équipe et l'état-de-l'art !" is split
- **THEN** the words are separated at the apostrophes and hyphens

#### Scenario: Question without usable word
- **WHEN** the question contains only punctuation
- **THEN** the keyword list is empty and the search still returns a list

### Requirement: Match any word of the question in the keyword list
The system SHALL build the keyword list as a disjunction of the question words (at least one word matches), ranked by a relevance score that weighs rare words more than common words, and SHALL NOT require all words to be present.

Source: `tests/hybrid_search/test_hybrid_search.py` (DepartageEtNormalisation.test_plein_texte_ou_de_mots_comme_fts5, MotsCourantsContreMotRare.test_reference_sqlite_le_mot_rare_passe_devant)

#### Scenario: Rare word beats common words
- **WHEN** one passage contains a rare word of the question and another contains only repeated common words of the question
- **THEN** the passage with the rare word is ranked first in the keyword list

#### Scenario: Several words without a passage containing all
- **WHEN** a question has several words and no passage contains all of them
- **THEN** the keyword list is the union of the passages that contain at least one word

### Requirement: Rank the semantic list by dot product
The system SHALL rank the semantic list by dot product between the question vector and each passage vector without renormalising, so that a zero vector scores zero and never ranks first, and a vector of larger norm scores higher than a unit vector at the same angle.

Source: `tests/hybrid_search/test_hybrid_search.py` (VecteursDegeneres.test_la_voie_sqlite_est_un_produit_scalaire)

#### Scenario: Zero vector
- **WHEN** a passage has a zero vector
- **THEN** it does not rank first and ranks well below close passages

#### Scenario: Larger norm
- **WHEN** a passage has a vector twice the norm of the question's direction
- **THEN** it ranks above a passage at the same angle with a unit norm, except for freshness effects

### Requirement: Give a freshness bonus to recent dated watch articles
The system SHALL add a bonus that decays with the age of the document for documents that belong to the watch collection, carry a valid publication date and do not belong to the author's own collection. The system SHALL give half of the maximum bonus (neutral value) to every other passage: undated documents, books, documents of the author's own collection, and documents whose date is unreadable.

Source: `tests/hybrid_search/test_hybrid_search.py` (FusionEtFraicheur.test_bonus_cas_limites, FusionEtFraicheur.test_bonus_de_fraicheur_identique_a_la_voie_sqlite)

#### Scenario: Article published today
- **WHEN** a watch article is dated today
- **THEN** it receives the maximum bonus

#### Scenario: Neutral cases
- **WHEN** the document has no date, an unreadable date, a collection other than watch, or the author's own collection
- **THEN** it receives the neutral half bonus

#### Scenario: Older article
- **WHEN** a watch article is older
- **THEN** its bonus is lower than that of a recent one, halving at each half-life of age

### Requirement: Order equal relevance by freshness then by identifier
The system SHALL order passages of equal rounded relevance inside each list by freshness (most recent watch article first), then by identifier, and SHALL break ties in the final fused score by semantic rank, then keyword rank (passages absent from a list last), then identifier.

Source: `tests/hybrid_search/test_hybrid_search.py` (DepartageEtNormalisation.test_ordre_final_rang_vectoriel_puis_plein_texte_puis_id, VecteursDegeneres.test_le_bonus_de_fraicheur_peut_depasser_un_rang_sur_la_voie_sqlite_aussi)

#### Scenario: Final tie
- **WHEN** two passages have the same fused score
- **THEN** the one with the better semantic rank comes first, then the better keyword rank, then the lower identifier

#### Scenario: Freshness can outweigh one rank
- **WHEN** a recent watch article ranks one place below an older passage in the semantic list
- **THEN** its freshness bonus may still place it first in the fused result, on both paths

### Requirement: Restrict a search by collection, date and passage type
The system SHALL restrict results to passages of the requested collections, to documents published on or after a given date (keeping undated books), and to the requested passage types. A filter that is not requested SHALL NOT appear in the query. On the PostgreSQL path, the collection filter, the date filter and the passage-type filter SHALL all be applied before the keyword candidate limit (the collection and date filters as a list of book identifiers, without a join in the keyword query), so that a collection holding none of the globally best keyword matches still gets its own keyword candidates.

Source: `tests/hybrid_search/test_hybrid_search.py` (Requete.test_filtres_seulement_si_demandes, Requete.test_bm25_filtre_type_collection_et_date_avant_la_limite, Requete.test_bm25_sans_filtre_de_collection_ni_de_date_requete_inchangee, Requete.test_bm25_date_seule_avant_la_limite), `tests/hybrid_search/test_hybrid_search_sans_tsvector.py` (RequeteDeLaBibliothequeInchangee), `tests/hybrid_search/test_filtre_avant_limite.py` (FiltreAvantLaLimite, skipped when no database is available), `tests/pmzilla_lab_library/test_pmzilla_lab_library.py` (Recherche.test_filtre_par_collection, Recherche.test_filtre_de_date_garde_les_livres), `tests/pmzilla_lab_library/test_figures.py` (Types.test_une_recherche_de_figures_n_est_pas_noyee_par_les_passages_de_texte)

#### Scenario: Unknown collection
- **WHEN** a search is restricted to a collection that does not exist
- **THEN** the result is empty

#### Scenario: Date filter keeps books
- **WHEN** a search uses a date later than a watch article's publication date
- **THEN** that article is excluded and undated books remain

#### Scenario: Figure search not drowned by text
- **WHEN** many running-text passages match better than any figure and only figures are requested
- **THEN** figure passages are still returned, because the type filter is applied inside the keyword query

#### Scenario: Under-represented collection
- **WHEN** a search is restricted to a collection and every best keyword match of the whole library lies outside it
- **THEN** the keyword list contains the best matches inside the collection and is not empty

#### Scenario: Date only
- **WHEN** a search carries a date but no collection and every best keyword match is older
- **THEN** the keyword list contains the best matches of the period and is not empty

#### Scenario: No collection and no date filter
- **WHEN** neither a collection nor a date is requested
- **THEN** the keyword query is the same as before this change

#### Scenario: Specification without a book restriction
- **WHEN** a search specification declares no book column for the keyword index (cases, experiments)
- **THEN** its keyword query is unchanged and its filters apply after the limit as before

### Requirement: Compare components separately on request
The system SHALL accept a component choice (both, semantic only, keyword only) and, when one component is chosen, SHALL fuse and evaluate only that list.

Source: `tests/hybrid_search/test_hybrid_search.py` (DepartageEtNormalisation.test_composantes_ne_fusionnent_qu_une_voie, Requete.test_composante_vecteur_sans_la_voie_texte_et_inversement)

#### Scenario: Semantic only
- **WHEN** the semantic component is requested
- **THEN** the keyword list is neither joined nor evaluated

#### Scenario: Unknown component
- **WHEN** an unknown component name is given
- **THEN** the request is refused with an error

### Requirement: Build the SQL search without interpolating user values
The system SHALL pass the question, its words, the collections, the date, the passage types and the vector as bound parameters and SHALL NOT write any of them into the SQL text. A specification that does not declare a collection filter, a date or a passage-type column SHALL ignore the matching option without inventing a column.

Source: `tests/hybrid_search/test_hybrid_search.py` (Requete.test_aucune_valeur_dans_le_sql, Requete.test_specification_sans_fraicheur_ni_filtre, Requete.test_vecteur_en_texte)

#### Scenario: Hostile question
- **WHEN** the question contains SQL syntax
- **THEN** the SQL text contains none of it and the words appear only in parameters

#### Scenario: Specification without filters
- **WHEN** a table specification declares no collection filter and a collection filter is requested
- **THEN** no collection parameter is produced

### Requirement: Choose the vector scan strategy
The system SHALL support an approximate-nearest-neighbour scan (default) and an exact scan, SHALL rank both by dot product, and SHALL refuse unknown scan or keyword-index names. For the approximate scan it SHALL set the search breadth inside the transaction, SHALL refuse a breadth outside the supported range, and SHALL use a breadth at least as large as the candidate count by default. The scope of candidate passages SHALL never be materialised.

Source: `tests/hybrid_search/test_hybrid_search.py` (Requete.test_balayage_exact_ou_ann, Requete.test_ann_regle_hnsw_dans_la_transaction, Requete.test_ann_ef_search_hors_bornes, Requete.test_defaut_ann_et_400, Requete.test_ann_ef_search_par_defaut_couvre_les_candidats)

#### Scenario: Exact scan
- **WHEN** the exact scan is requested
- **THEN** the score is a dot product that bypasses the approximate index

#### Scenario: Approximate scan setup
- **WHEN** the approximate scan runs
- **THEN** the breadth and iterative-scan settings are applied before the query in the same transaction

#### Scenario: Breadth out of range
- **WHEN** a breadth below or above the supported range is requested
- **THEN** the search is refused with an error

#### Scenario: Unknown scan
- **WHEN** an unknown scan or keyword-index name is given
- **THEN** the query builder raises an error

### Requirement: Offer a legacy text-search ranking for comparison
The system SHALL keep a legacy full-text ranking (word disjunction with a configurable length-normalisation flag from the supported set) selectable for comparison only, with the keyword index (BM25) as default, and SHALL refuse a normalisation flag outside the supported set. A table specification without a BM25 index SHALL be refused when BM25 is selected. A table specification without a legacy full-text column SHALL be accepted with BM25, SHALL carry no full-text vector in its scope, and SHALL be refused when the legacy ranking is selected. The query built for the library specification SHALL be unchanged.

Source: `tests/hybrid_search/test_hybrid_search.py` (DepartageEtNormalisation.test_drapeau_de_normalisation_par_defaut_et_reglable, Requete.test_specification_sans_fraicheur_ni_filtre, Requete.test_constantes_de_la_fusion_dans_le_sql), `tools/hybrid_search.py` (build_query), `tests/hybrid_search/test_hybrid_search_sans_tsvector.py` (SpecificationSansTsvector, SpecificationSansTsvectorAvecBase).

#### Scenario: Default ranking
- **WHEN** a query is built without options
- **THEN** it uses BM25 and no legacy ranking function

#### Scenario: Unsupported flag
- **WHEN** a normalisation flag outside the supported set is given
- **THEN** an error is raised

#### Scenario: Specification without legacy column
- **WHEN** a specification declares no legacy full-text column and BM25 is selected
- **THEN** the query is built, its scope carries a null full-text vector, and it returns results on a disposable database

#### Scenario: Legacy ranking without legacy column
- **WHEN** the same specification is used with the legacy ranking
- **THEN** the query builder raises an error

#### Scenario: Library query unchanged
- **WHEN** the library query is built with the same arguments before and after this change
- **THEN** the SQL text is identical

### Requirement: Run the SQL search read-only and end the transaction
The system SHALL execute the hybrid SQL on a given connection only for reading, SHALL return (identifier, score) pairs best first, and SHALL roll the transaction back afterwards. A question without a usable word SHALL produce a keyword query that matches nothing.

Source: `tests/hybrid_search/test_hybrid_search.py` (Requete.test_execution_lit_et_ferme_la_transaction, Requete.test_bm25_question_sans_mot_utilisable, AvecBase.test_question_sans_mot_utilisable)

#### Scenario: Normal call
- **WHEN** the search is executed
- **THEN** one query is sent, results are returned best first and the transaction is rolled back

### Requirement: Match accents case-insensitively and give the same results as the SQLite path
The system SHALL ignore case and accents when matching words, and SHALL return on a disposable PostgreSQL database the same passages as the SQLite path on the same demo data, including accented queries, figures, collections and the date filter, for the approximate scan as for the exact one on a small corpus, where the keyword candidate limit never cuts. On a real library, a search restricted by collection or date MAY differ between the two paths by design, because the PostgreSQL path filters before the keyword limit and the SQLite path after it.

Source: `tests/hybrid_search/test_hybrid_search.py` (AvecBase.test_memes_resultats_que_la_voie_sqlite, AvecBase.test_accents_et_figures_et_collections_et_since, AvecBase.test_ann_donne_les_memes_resultats_sur_ce_petit_corpus) (skipped when no database is available)

#### Scenario: Accented question
- **WHEN** a question is typed without accents
- **THEN** passages containing the accented words are found

#### Scenario: Restricted query on a real library
- **WHEN** a search is restricted by collection or date on a library where the keyword limit cuts
- **THEN** the two paths may return different passages by design, and the parity report shows such queries apart

### Requirement: Offer a diagnostic view that does not change the ranking
The system SHALL offer a diagnostic query that adds to each result the intermediate values (semantic rank and score, keyword rank and raw score, reciprocal-rank sum before bonus, bonus) while ranking identically to the production query.

Source: `tests/hybrid_search/test_hybrid_search.py` (DepartageEtNormalisation.test_requete_de_production_et_diagnostic_classent_pareil)

#### Scenario: Same order
- **WHEN** the production and diagnostic queries are built for the same question
- **THEN** their ordering and limit clauses are identical and only the diagnostic one exposes intermediate columns

### Requirement: Use one generic name for the personal collection
The system SHALL name the collection of the user's own articles with a single fixed generic name, identical for every user and free of any personal identifier, defined once and read by both search paths, the watch collection, the pre-sort, the dashboard and the tests. The name SHALL be made of lower-case letters, digits and hyphens, start with a letter, and differ from the watch collection name and its former name. Both search paths SHALL exclude documents of that collection from the freshness bonus under that name only.

Source: `tests/hybrid_search/test_hybrid_search.py` (Constantes.test_nom_de_la_collection_personnelle, FusionEtFraicheur.test_bonus_cas_limites)

#### Scenario: One definition
- **WHEN** the personal collection name is read from the search module, the library server module and the watch folder module
- **THEN** the three values are equal and match the allowed form

#### Scenario: SQL path
- **WHEN** the library search query is built
- **THEN** its freshness expression excludes exactly that name, written as a constant of the code and never taken from user input

#### Scenario: Personal article
- **WHEN** a dated document belongs to the personal collection
- **THEN** it receives the neutral half bonus on both paths

## Open questions

1. The diagnostic comparison of the two paths is only printed when a developer switch is set and asserts nothing; it is therefore not a requirement on the diagnostic output.
