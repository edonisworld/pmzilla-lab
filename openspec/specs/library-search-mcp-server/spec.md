# library-search-mcp-server

## Purpose

The library as served to the assistant: the four MCP tools, the shape of their answers, backend choice (PostgreSQL by default, SQLite on request), collection naming and its former-name alias, and the PostgreSQL implementation that mirrors the SQLite one.

Source of truth: `tests/pmzilla_lab_library/test_pmzilla_lab_library.py`, `tests/pmzilla_lab_library/test_figures.py`, `tests/pmzilla_lab_library/test_serve_wrapper.py`, `tests/pmzilla_lab_library/test_coherence_noms.py`, `tests/library_backend/test_backend.py`, `tests/fixtures_library/demo_library.py`, `tools/pmzilla_lab_library.py`, `tools/knowledge_library.py`.
## Requirements
### Requirement: Return passages with book, section and citation metadata
The system SHALL return, for each search hit, the passage identifier, book title, file name, section, position, collections, passage kind, score and text, and SHALL add the author, source, URL and publication date when the document is an article. When the catalogue gives no author the system SHALL return an explicit "author not stated" marker and SHALL NOT invent a name.

Source: `tests/pmzilla_lab_library/test_pmzilla_lab_library.py` (Recherche.test_section_et_champs_renvoyes, Recherche.test_article_porte_url_date_et_site, Indexation.test_catalogue_change_titre_et_auteur_sans_recalcul, Decoupage.test_meta_et_titre)

#### Scenario: Book hit
- **WHEN** a book passage is found
- **THEN** the hit carries its book title, section, collections and a passage identifier

#### Scenario: Article hit
- **WHEN** an article of the watch collection is found
- **THEN** the hit also carries its URL, publication date and the site as author with a "not stated" marker when no author is known

#### Scenario: Catalogue author
- **WHEN** the catalogue gives a title and authors for a book
- **THEN** hits show the catalogue title and the authors joined, without re-embedding the book

### Requirement: Return running text only by default and figures on request
The system SHALL search running text only unless passage types are given, SHALL accept `texte`, `figure` or both (as a list or as a single string), and SHALL refuse an unknown or empty type list with an error. A figure hit SHALL carry a reference record (identifier, label, page, section, image path as plain text, caption, alternative text) and a text hit SHALL NOT carry one.

Source: `tests/pmzilla_lab_library/test_figures.py` (Types.test_texte_seul_par_defaut, Types.test_figures_seules, Types.test_les_deux, Types.test_types_invalides, Types.test_filtres_combines)

#### Scenario: Default
- **WHEN** a search is made without types
- **THEN** every hit has kind text and none has a reference record

#### Scenario: Figures only
- **WHEN** the figure type is requested
- **THEN** every hit is a figure with its label, page, section and image path text

#### Scenario: Invalid type
- **WHEN** the types are unknown or an empty list
- **THEN** the search fails with an error naming the known types

### Requirement: Read a passage with its neighbours
The system SHALL return the requested passage and a bounded number of neighbouring passages before and after it in the same book, in book order, with the kind of each passage and the reference record of figure passages, and SHALL return an error naming the unknown identifier when the identifier does not exist.

Source: `tests/pmzilla_lab_library/test_pmzilla_lab_library.py` (Recherche.test_lecture_avec_voisins), `tests/pmzilla_lab_library/test_figures.py` (Types.test_lecture_kind_et_ref), `tests/library_backend/test_backend.py` (AvecBase.test_passage_inconnu)

#### Scenario: Neighbours
- **WHEN** one passage before and none after is requested
- **THEN** the answer lists the previous and the anchor passage in book order

#### Scenario: Unknown passage
- **WHEN** an identifier that does not exist is requested
- **THEN** the answer is an error saying the identifier is unknown and to use one returned by the search

### Requirement: List collections and books with counts
The system SHALL list collections with their number of books, counting a book once per collection, and SHALL list books with title, file, collections, passage count and figure count, optionally restricted to a collection.

Source: `tests/pmzilla_lab_library/test_pmzilla_lab_library.py` (Recherche.test_collections_et_livres), `tests/pmzilla_lab_library/test_figures.py` (Types.test_liste_des_livres_compte_les_figures)

#### Scenario: Collections
- **WHEN** the collections are listed on a library with four books in four collections
- **THEN** each collection is shown with one book

#### Scenario: Books with figures
- **WHEN** books are listed
- **THEN** each shows how many of its passages are figures

### Requirement: Validate tool arguments and bound sizes
The system SHALL answer the search tool with an error object when a requested collection is unknown (naming the unknown and the known ones), when the date filter is not a calendar date (echoing the value received), or when the search rejects its arguments (such as invalid passage types), SHALL NOT run the search when a collection or the date is refused, SHALL pass a valid date through unchanged, SHALL clamp the result count between one and a maximum and each neighbour count of the read tool between zero and a maximum (with default neighbour counts when none are given), and SHALL keep a successful search as a list.

Source: `tests/pmzilla_lab_library/test_serve_wrapper.py` (Garde.test_collection_inconnue, test_date_invalide, test_date_valide_transmise, test_limite_bornee_de_1_a_20, test_voisins_de_read_passage_bornes_de_0_a_5, test_erreur_de_valeur_de_la_recherche_devient_une_erreur)

#### Scenario: Unknown collection
- **WHEN** the search tool is called with a collection that is not in the library
- **THEN** it returns an error listing the unknown and the known collections instead of an empty list, and no search is made

#### Scenario: Bad date
- **WHEN** the date filter is not a valid year-month-day date (impossible month or day, a word, another separator)
- **THEN** it returns an error naming the expected form and the value received, and no search is made

#### Scenario: Bounds
- **WHEN** a result count below one or above the maximum is requested, or negative or oversized neighbour counts are requested
- **THEN** the search receives the nearest bound and the read receives counts clamped to the allowed range

#### Scenario: Rejected arguments
- **WHEN** the search raises a value error (for example unknown passage types)
- **THEN** the tool returns an error object carrying that message

### Requirement: Choose the backend explicitly, PostgreSQL by default, without silent fallback
The system SHALL serve from PostgreSQL by default, SHALL let an option or an environment variable select SQLite or PostgreSQL (the option winning), SHALL refuse an unknown backend with a message naming it, and SHALL stop with a clear message that mentions the SQLite option, and no secret, when the database does not answer. It SHALL NOT fall back to SQLite silently.

Source: `tests/library_backend/test_backend.py` (Voie.test_defaut_postgres_option_et_variable, Voie.test_voie_inconnue_refusee, Voie.test_open_library_postgres_sans_repli_sur_sqlite, Voie.test_base_qui_ne_repond_pas_message_clair_sans_secret, Voie.test_serve_accepte_l_option_backend)

#### Scenario: Default
- **WHEN** no option and no environment variable are set
- **THEN** the PostgreSQL backend is chosen

#### Scenario: Option over variable
- **WHEN** the variable says PostgreSQL and the option says SQLite
- **THEN** SQLite is chosen

#### Scenario: Database down
- **WHEN** the database does not answer
- **THEN** the server stops with a connection message and a hint to use the SQLite option, and does not open SQLite

#### Scenario: Unknown backend
- **WHEN** the backend name is not known
- **THEN** the server stops with an error naming it

### Requirement: Read from PostgreSQL with a read-only role
The system SHALL connect to the library database under a read-only role, SHALL embed the question with the same embedding function as the SQLite path, SHALL retry a lost connection once, and SHALL be unable to modify library data.

Source: `tests/library_backend/test_backend.py` (Voie.test_connexion_sous_le_role_de_lecture, AvecBase.test_le_role_de_lecture_ne_peut_pas_ecrire)

#### Scenario: Role
- **WHEN** the default connection is opened
- **THEN** it uses the read-only role

#### Scenario: Write attempt
- **WHEN** a delete is attempted over the read connection
- **THEN** the database refuses it

### Requirement: Give the PostgreSQL backend the same interface and answer shapes as the SQLite backend
The system SHALL return from the PostgreSQL backend the same dictionary shape, keys and values (kind named as in SQLite, collections canonical and sorted, figure reference record) as the SQLite backend, SHALL translate passage types and collections (including the former alias) for the database search, SHALL reject unknown types as SQLite does, and SHALL do nothing on refresh since the database is always current.

Source: `tests/library_backend/test_backend.py` (Forme.test_meme_dictionnaire_que_la_voie_sqlite, Forme.test_figure_porte_sa_ref_et_le_texte_non, Parametres.test_types_et_collections_traduits, Parametres.test_types_inconnus_refuses_comme_en_sqlite, Parametres.test_refresh_ne_fait_rien)

#### Scenario: Same shape
- **WHEN** the same passage is described by both backends
- **THEN** both dictionaries have the same keys, and only figures carry a reference record

#### Scenario: Contract on shared data
- **WHEN** both backends search the same demo corpus with and without collections, types, the former alias and a date
- **THEN** they return the same passages with the same top hit and the same field values, and the date filter keeps undated books

#### Scenario: Collections and books agree
- **WHEN** collections, stored aliases and books are listed on both backends
- **THEN** the answers are equal

#### Scenario: Reading around a passage
- **WHEN** a passage is read with neighbours on both backends
- **THEN** the same positions and the same field values are returned, except the backend-specific identifiers

### Requirement: Forward the backend choice to the evaluation configuration
The system SHALL leave the MCP server arguments unchanged when no backend is chosen, SHALL pass the chosen backend (option or environment variable) to the server arguments, and SHALL serve a disposable per-case library from the run's disposable database with the PostgreSQL backend and the database-name variable, whatever backend is chosen for the other cases. It SHALL NOT serve a disposable per-case library from a SQLite file.

Source: `tests/library_backend/test_backend.py` (ConfigurationMcp)

#### Scenario: Default
- **WHEN** no backend is chosen
- **THEN** the server is started with only its serve argument

#### Scenario: Disposable library
- **WHEN** a case provides its own library
- **THEN** the server configuration carries the PostgreSQL backend and the disposable database name, and no data folder for a SQLite index

### Requirement: Expose exactly seven read-only tools without image access
The system SHALL expose exactly seven tools to the assistant: the four library tools (search, read a passage, list collections, list books) and the three cases tools (search cases, search running experiments, list due reviews). It SHALL let the library search tool take a passage-type argument, SHALL NOT include any capability to open, read, encode or display an image file, and SHALL NOT include any tool that writes to the database.

Source: `tests/pmzilla_lab_library/test_figures.py` (Types.test_serveur_ne_declare_que_quatre_outils_sans_acces_aux_images, which checks the seven tools despite its name; Types.test_aucun_acces_aux_images_en_indexant_cherchant_et_lisant)

#### Scenario: Tool inventory
- **WHEN** the server source is inspected for declared tools
- **THEN** the declared tools are the search, read, list-collections, list-books, case-search, experiment-search and due-review tools, and none calls image-handling facilities

#### Scenario: No write tool
- **WHEN** the declared tools are inspected
- **THEN** none starts, notes, postpones, drops or closes an experiment

#### Scenario: Image path is text only
- **WHEN** a library is indexed, searched and read with watchers on file access under the image folder
- **THEN** no file under that folder is opened, read, stat-ed or tested for existence

### Requirement: Describe the search tool without a personal name
The system SHALL describe the library search tool to the assistant as a search of "the user's" library, SHALL name the personal collection by its generic name as the collection of the user's own published articles, and SHALL NOT include any personal identifier in that description.

Source: `tests/pmzilla_lab_library/test_pmzilla_lab_library.py` (DescriptionDeSearchLibrary.test_description_sans_identifiant_personnel)

#### Scenario: Description read from the server source
- **WHEN** the description of the search tool is read
- **THEN** it names the personal collection by the generic name defined in the code, speaks of the user, and contains none of the scanner's identifiers in any case

### Requirement: Former collection name treated as unknown
The system SHALL treat the former watch collection name like any unknown collection: the search tool SHALL return the error object listing the known collections, and counts and listings SHALL show only the names stored in the index.

#### Scenario: Search by the former name
- **WHEN** the search tool is called with the former collection name
- **THEN** it returns an error listing the known collections

#### Scenario: Index still storing the former name
- **WHEN** an index stores the former name and has not been renamed
- **THEN** the counts show the stored name and the current name finds nothing from those books

### Requirement: Read the library from a named database on request
The system SHALL let a configurable database-name variable choose the database that the PostgreSQL library backend and the indexer connect to, the installation database being used when it is unset, so that a disposable database can serve a throwaway library. It SHALL NOT fall back to the installation database when the named database does not answer.

#### Scenario: Variable set
- **WHEN** the database-name variable names a disposable database
- **THEN** both the library backend and the indexer connect to that database

#### Scenario: Named database down
- **WHEN** the named database does not answer
- **THEN** the server stops with its connection message and does not connect to the installation database

## Open questions

1. The `ConfigurationMcp` requirement exercises `tools/posture_evals.py`, which is outside this domain; ownership of that requirement should be confirmed with the posture-evals specs.
