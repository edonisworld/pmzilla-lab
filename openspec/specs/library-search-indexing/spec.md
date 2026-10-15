# library-search-indexing

## Purpose

Building and maintaining the library index from Markdown collections, written directly into the knowledge schema of the database: incremental indexing, passage splitting, figure passages, forced recomputation, collection renaming, the BM25 probe and status counts, and the caption diagnostic.

Source of truth: `tests/pmzilla_lab_library/test_pmzilla_lab_library.py`, `tests/pmzilla_lab_library/test_figures.py`, `tests/pmzilla_lab_library/test_serve_wrapper.py` (catalogue), `tests/pmzilla_lab_library/test_caption_diagnostic.py`, `tests/convert_books/test_noms_options.py`, `tools/pmzilla_lab_library.py`, `tools/caption_diagnostic.py`.
## Requirements
### Requirement: Index collection folders incrementally
The system SHALL index every Markdown file found under the collection folders (the folder name being the collection), SHALL skip files whose name starts with an underscore, SHALL stop with an error when a given folder does not exist, and SHALL report how many books were indexed and how many were unchanged.

Source: `tests/pmzilla_lab_library/test_pmzilla_lab_library.py` (Indexation.test_premiere_indexation, Indexation.test_fichiers_underscore_ignores_et_dossier_absent)

#### Scenario: First indexing
- **WHEN** four books are indexed for the first time
- **THEN** the report says four indexed and the four books are in the index with their titles

#### Scenario: Underscore file and missing folder
- **WHEN** a file whose name starts with an underscore is present, or a folder is missing
- **THEN** the file is ignored, respectively the command stops with an error

### Requirement: Recompute only what changed
The system SHALL compare each book found in the folders with the book stored in the database under the same file name, SHALL recompute embeddings only for added or modified books (content hash or embedding model different, or book forced), SHALL replace the passages of a modified book entirely (including what the keyword index finds), SHALL remove from the database a book whose file disappeared (naming it), SHALL recompute everything when the embedding model changes, and SHALL NOT call the embedding model when nothing changed. A book already stored by the former import, with the same content hash, model, title, metadata and collections, SHALL count as unchanged and SHALL NOT be re-embedded.

Source: `tests/pmzilla_lab_library/test_pmzilla_lab_library.py` (Indexation.test_inchange_ne_recalcule_rien, test_ajout, test_modification_remplace_les_passages, test_fichier_supprime_sort_de_l_index, test_changement_de_modele_reindexe), to be moved onto the fake store and the database class.

#### Scenario: Unchanged run
- **WHEN** indexing is run twice on the same files
- **THEN** the second run reports zero indexed and makes no embedding call

#### Scenario: Modified book
- **WHEN** a book is rewritten
- **THEN** only its passages are replaced and words that disappeared are no longer found by keyword search

#### Scenario: Deleted file
- **WHEN** a file is deleted from the folders
- **THEN** its book and passages leave the database and the report names it

#### Scenario: Book stored by the former import
- **WHEN** the database holds a book with the hash, model, title, metadata and collections that the indexer computes for its file
- **THEN** the book is reported unchanged and no embedding call is made

### Requirement: Update collections, title and author without recomputing embeddings
The system SHALL update a book's collections when its file moves to another collection folder, SHALL record all collections of a book present in several folders while indexing it once, and SHALL apply catalogue changes of title and authors, without recomputing embeddings.

Source: `tests/pmzilla_lab_library/test_pmzilla_lab_library.py` (Indexation.test_changement_de_collection_sans_recalcul, Indexation.test_livre_dans_deux_collections_indexe_une_fois, Indexation.test_catalogue_change_titre_et_auteur_sans_recalcul)

#### Scenario: File moved
- **WHEN** a book file moves from one collection folder to another
- **THEN** its collection changes and no embedding call is made

#### Scenario: Same file in two folders
- **WHEN** the same book exists in two collection folders
- **THEN** it is indexed once and lists both collections

### Requirement: Read the book catalogue leniently
The system SHALL read the book catalogue as entries keyed by file name, normalising each name to the composed Unicode form, SHALL keep every key of an entry while using only the title and the authors for indexing, SHALL accept an entry without authors (the author then becomes the "not stated" marker), SHALL ignore entries that are not mappings, and SHALL treat a missing or empty catalogue as empty, keeping the titles found in the files.

Source: `tests/pmzilla_lab_library/test_serve_wrapper.py` (Catalogue, CatalogueDansLIndex.test_cle_supplementaire_ignoree_et_auteur_absent_remplace)

#### Scenario: Extra key
- **WHEN** a catalogue entry has a title, authors and another key, and books are indexed
- **THEN** the loaded entry keeps the three keys, the hit shows the catalogue title and authors, and the other key has no effect

#### Scenario: Entry without authors
- **WHEN** an entry gives only a title
- **THEN** it is accepted and the hits of that book carry the "not stated" author marker

#### Scenario: Malformed entries
- **WHEN** an entry is empty or plain text instead of a mapping
- **THEN** it is ignored and the other entries are kept

#### Scenario: Decomposed accents
- **WHEN** a file name is written with decomposed accents in the catalogue
- **THEN** it is stored under its composed form

#### Scenario: Missing or empty catalogue
- **WHEN** the catalogue file does not exist or is empty
- **THEN** the catalogue is empty

### Requirement: Split a book into passages by heading
The system SHALL split a book body into passages grouped under a hierarchical section path built from its headings, SHALL drop fragments too short to be useful (such as page numbers), SHALL cut an oversized paragraph into several passages within a size limit, and SHALL label passages found before any heading with a "no heading" section.

Source: `tests/pmzilla_lab_library/test_pmzilla_lab_library.py` (Decoupage)

#### Scenario: Hierarchical sections
- **WHEN** a body has a part, a chapter, a debris-only section and a sub-section
- **THEN** passages carry the paths "part > chapter" and "part > other > sub-section" and the debris section yields none

#### Scenario: Large paragraph
- **WHEN** a paragraph exceeds the size target
- **THEN** it is cut into several passages none of which exceeds twice the target

#### Scenario: No heading
- **WHEN** a text has no heading
- **THEN** its passage has the section "(no heading)"

### Requirement: Read title and metadata from the file header
The system SHALL read the title from the file header and fall back on a given name when there is none, SHALL read source, URL and publication date for articles, and SHALL build the author as the site name with a "not stated" marker when the header has no author, never inventing a name.

Source: `tests/pmzilla_lab_library/test_pmzilla_lab_library.py` (Decoupage.test_meta_et_titre)

#### Scenario: Header present
- **WHEN** the header has a title, a source and a URL
- **THEN** the title is returned and the author is the source with the "not stated" marker

#### Scenario: No header
- **WHEN** the text has no header
- **THEN** the fallback title is returned and the body is unchanged

### Requirement: Turn figure blocks into figure passages
The system SHALL turn each figure block of the Markdown into its own passage at its place in the book (kind figure, positions continuing without gap), SHALL NOT leave the block comment, image path or label lines in running text, SHALL discard a malformed or unclosed block comment, and SHALL keep a line that follows a block as running text.

Source: `tests/pmzilla_lab_library/test_figures.py` (PassagesFigure.test_le_commentaire_n_est_jamais_du_texte_courant, test_commentaire_mal_forme_ou_colle_au_texte, test_un_bloc_est_un_passage_a_part_a_sa_place, test_texte_inchange_pour_un_livre_sans_figure)

#### Scenario: Interleaved passages
- **WHEN** a PDF-derived book has two figure blocks between text
- **THEN** its passages alternate text, figure, text, figure, text with consecutive positions and each figure takes the section of its place

#### Scenario: Book without figures
- **WHEN** a book has no figure block
- **THEN** all its passages are text and carry no reference record

#### Scenario: Malformed block
- **WHEN** a block comment is not closed
- **THEN** it is dropped and no comment text remains in running text

### Requirement: Embed figure passages from caption, useful alternative text and referring sentence
The system SHALL build a figure passage text from the caption, the alternative text when it differs from the caption, and the book sentence that refers to the figure label, SHALL embed it with the book title and section as for text, and SHALL NOT embed block comments or image paths.

Source: `tests/pmzilla_lab_library/test_figures.py` (PassagesFigure.test_texte_vectorise_legende_alt_utile_et_phrase_de_renvoi, test_alt_identique_a_la_legende_n_est_pas_un_texte_alternatif, PhraseDeRenvoi)

#### Scenario: Caption and referring sentence
- **WHEN** a figure has a numbered caption and a sentence in the book mentions its label
- **THEN** the passage text holds the caption followed by that sentence

#### Scenario: Alternative text only
- **WHEN** a figure has no caption and no sentence refers to it
- **THEN** the passage text is the alternative text alone

#### Scenario: Alternative text equal to caption
- **WHEN** the alternative text is identical to the caption
- **THEN** it is not recorded as an alternative text

#### Scenario: Neighbouring label
- **WHEN** another label is close in the text
- **THEN** only a sentence containing the exact label is chosen, the closest one, within a bounded length

### Requirement: Record the origin of a figure's text in its reference record
The system SHALL give each figure a reference record with identifier, section, source format, and, when known, label, page, image path as text, caption and alternative text each in its own field, SHALL give a PDF figure a caption and never an alternative text, and SHALL fill the section of every figure, using "no heading" before any heading.

Source: `tests/pmzilla_lab_library/test_figures.py` (PassagesFigure.test_ref, test_origine_du_texte_legende_et_texte_alternatif_chacun_dans_son_champ, test_section_toujours_remplie_pour_les_figures_epub_et_pdf, test_section_d_une_figure_avant_tout_titre)

#### Scenario: EPUB with both
- **WHEN** an EPUB figure has a caption and an alternative text
- **THEN** the reference record holds both in separate fields

#### Scenario: Alternative text only
- **WHEN** an EPUB figure has only an alternative text
- **THEN** the reference record has no caption, no label, no page and no image path

#### Scenario: Figure before any heading
- **WHEN** a figure precedes the first heading
- **THEN** its section is "(no heading)"

### Requirement: Remove the duplicated caption from PDF page text
The system SHALL remove from the running text of a PDF-derived book the copy of a figure's caption that the page repeats just before the figure block, only the closest copy and only back to the previous figure, SHALL keep the rest of the paragraph that contained it, SHALL count removed copies, and SHALL leave EPUB-derived books untouched.

Source: `tests/pmzilla_lab_library/test_figures.py` (LegendePdfSansDoublon)

#### Scenario: Single appearance
- **WHEN** a PDF-derived book is indexed
- **THEN** each figure caption appears once in the whole book, in the figure passage

#### Scenario: Paragraph remainder
- **WHEN** the caption shared a paragraph with other text
- **THEN** the other text remains in running text

#### Scenario: EPUB
- **WHEN** an EPUB-derived book is indexed
- **THEN** its text is not modified

### Requirement: Report figure counts when indexing and re-index changed books without duplicating figures
The system SHALL report the number of figure passages with the indexing summary, and SHALL replace, not duplicate, figure passages when a book is rewritten or recomputed.

Source: `tests/pmzilla_lab_library/test_figures.py` (PassagesFigure.test_un_bloc_est_un_passage_a_part_a_sa_place, PassagesFigure.test_relance_et_modification)

#### Scenario: Summary
- **WHEN** a library with two figures is indexed
- **THEN** the summary mentions two figures

#### Scenario: Rewrite
- **WHEN** a book with figures is rewritten
- **THEN** it has the same number of figure passages as before, not twice as many

### Requirement: Force recomputation of named books
The system SHALL accept a recompute option naming books (by name with or without extension, by path, in any letter case, or by a list file with comments and blank lines) and SHALL recompute only those books even if their Markdown is unchanged. It SHALL refuse the option without a book or without a folder, and SHALL stop before touching the database, saying nothing was indexed, when a name is unknown or ambiguous. It SHALL print, before recomputing, the restore-point reminder of design.md D2 naming a labelled database backup. It SHALL NOT create any backup, neither a file in the data folder nor a database backup, and SHALL NOT read the backup folder.

Source: `tests/pmzilla_lab_library/test_figures.py` (Recalcul), to be moved onto the fake store.

#### Scenario: One book
- **WHEN** one book is designated
- **THEN** the report says one indexed and the others unchanged, and its figure passages are replaced

#### Scenario: List file
- **WHEN** a list file names two books with comments and blank lines
- **THEN** both are recomputed

#### Scenario: Unknown or ambiguous name
- **WHEN** one designated name does not exist or matches two files
- **THEN** the command stops, says nothing was indexed, makes no embedding call and leaves the database unchanged

#### Scenario: Reminder and no backup
- **WHEN** books are recomputed
- **THEN** the output first names a labelled database backup as restore point, and no new file appears in the data folder

### Requirement: Rename a collection in place
The system SHALL rename a collection in the database, under the writing role and in one transaction, without recomputing anything, SHALL support a dry run that changes nothing and says what would be renamed, SHALL be idempotent (saying there is nothing to do), SHALL deduplicate a book that already holds the new name, SHALL remove the former collection when no book uses it, and SHALL keep passages, vectors and other books intact. It SHALL exit 2 with the unreachable message when the database does not answer, and SHALL NOT open any SQLite file. While indexing, a folder that carries a former collection name SHALL be stored under the new name with a warning and without recomputation.

Source: `tests/pmzilla_lab_library/test_pmzilla_lab_library.py` (Renommage), to be moved onto the fake store and the database class.

#### Scenario: Rename
- **WHEN** a collection is renamed from its former to its current name
- **THEN** the stored membership changes, the report counts the books, and passages and vectors are unchanged

#### Scenario: Dry run and repeat
- **WHEN** the rename is run with the dry-run option, then for real, then again
- **THEN** the first changes nothing and says "would be renamed", the second renames, the third says nothing to do

#### Scenario: Folder with former name
- **WHEN** the watch folder is renamed to its former name and indexing is run
- **THEN** the books stay under the current name, a warning names the former name and nothing is recomputed

### Requirement: Diagnose PDF captions that were not removed from page text
The system SHALL provide a command that replays the caption removal on one converted Markdown book and classifies each PDF caption not removed by cause (too far from the block, glued to other words, split over several lines or paragraphs, different form, not found), SHALL print only counts, never book text, caption, title or path, SHALL NOT modify or write any file, and SHALL ignore EPUB figures and figures without a caption.

Source: `tests/pmzilla_lab_library/test_caption_diagnostic.py`

#### Scenario: Each cause
- **WHEN** books are built with a caption that is glued, split, differently spelled, too far or absent
- **THEN** the cause counted is respectively "glued to other words", "split over several lines or paragraphs", "different form", "too far from the block", "not found"

#### Scenario: Counts only
- **WHEN** the command runs on a book with confidential captions
- **THEN** the output holds the numbers of PDF figures with caption, removed and not removed and counts per cause, and no title, caption or path

#### Scenario: Missing file or arguments
- **WHEN** the file does not exist or no argument is given
- **THEN** the command exits with a "file not found" message that does not echo the name, respectively exit code 1

### Requirement: Former recompute option refused
The system SHALL refuse the former French name of the recompute option with an error naming the current option, and SHALL recompute nothing.

#### Scenario: Former name
- **WHEN** the index command is given the former option name and a book
- **THEN** it stops with an error naming the current option and nothing is recomputed

### Requirement: Store the index in the knowledge schema of the database
The system SHALL write the library index of the `index` command directly into the knowledge schema of the database under the knowledge writing role: books with their title, metadata, content hash, model and indexing time, their collection memberships under the current collection names, and their passages in position order with kind text or figure, reference record and half-precision vector. It SHALL write each added or replaced book in one transaction, so that an interrupted run leaves only complete books and a failing book leaves no book row and no orphan passage. It SHALL delete a collection no longer used by any book at the end of the run. It SHALL refuse a vector whose size differs from the model's with an error that mentions dimensions and no text. It SHALL NOT create, open or read any SQLite file when indexing, renaming, probing or reporting status. Tests: `tests/pmzilla_lab_library` (fake store, and database class run with `tools/dbtest.sh`).

#### Scenario: First indexing into an empty database
- **WHEN** five invented books, two of them with figures, are indexed into an empty disposable database
- **THEN** the database holds five books, their passages with kinds text and figure, their collections, and no SQLite file exists in the data folder

#### Scenario: Failing book
- **WHEN** one book fails while its passages are written
- **THEN** that book is absent, no orphan passage remains, the other books are stored and the command exits with code 1 naming the file

#### Scenario: Orphan collection
- **WHEN** the only book of a collection moves to another collection folder and indexing runs
- **THEN** the former collection no longer exists in the database and no embedding call is made

#### Scenario: Wrong vector size
- **WHEN** the embedding service returns a vector of the wrong size
- **THEN** the book is not written and the error mentions dimensions and no book text

### Requirement: Stop before any work when the database does not answer or another run is indexing
The system SHALL connect to the database before any embedding call and SHALL stop with exit code 2 and the unreachable message of design.md D2, pointing to the database start script and holding no secret, when it does not answer. It SHALL take an exclusive lock for the duration of a run and SHALL stop with exit code 1 and the "in progress" message of design.md D2 when another run holds it. In both cases it SHALL write nothing and SHALL NOT call the embedding service.

#### Scenario: Database down
- **WHEN** indexing runs while the database does not answer
- **THEN** the command exits with code 2, says nothing was indexed, names the start script and makes no embedding call

#### Scenario: Concurrent run
- **WHEN** a second indexing run starts while a first one holds the lock
- **THEN** the second exits with code 1, says another run is in progress and changes nothing

### Requirement: Refuse an empty scan against a filled database
The system SHALL refuse, with exit code 1 and the message of design.md D2 that names the allow-empty option, to index folders that contain no book while the database holds books, and SHALL remove every book only when that option is given. It SHALL NOT delete any book before this check.

#### Scenario: Empty folders
- **WHEN** the collection folders are empty and the database holds books
- **THEN** the command exits with code 1, nothing is removed and the output names the allow-empty option

#### Scenario: With the option
- **WHEN** the same run is made with the allow-empty option
- **THEN** every book is removed and the report names them

### Requirement: Probe the BM25 index on request
The system SHALL provide a probe command that reads the BM25 index like the search does, under the read-only role: one full-text query on common words without a filter and one filtered on figure passages, each ending its transaction. It SHALL print "BM25 index readable" and exit 0 when both succeed; SHALL print "BM25 index unreadable" with the failing variant and the error type, point to the "Damaged BM25 index" section of the installation guide and exit 3 when either fails, for an internal error of a damaged index as for any other probe error; and SHALL exit 2 with the unreachable message when the database does not answer. It SHALL NOT repair anything, SHALL NOT write, and its output SHALL hold no book text.

#### Scenario: Readable index
- **WHEN** both probe queries succeed
- **THEN** the output says the index is readable and the exit code is 0

#### Scenario: Damaged index
- **WHEN** the filtered probe query raises an internal error
- **THEN** the output names the unreadable BM25 index, the filtered variant, the error type and the guide section, and the exit code is 3

#### Scenario: No repair
- **WHEN** the probe fails
- **THEN** no statement other than the two read queries and the transaction ends is sent

### Requirement: Report database counts on request
The system SHALL provide a status command that prints, under the read-only role, one line with the numbers of books, passages, figures and collections of the database, and nothing else, and SHALL exit 2 with the unreachable message when the database does not answer. It SHALL NOT print titles, file names or passage text.

#### Scenario: Status
- **WHEN** the status command runs on a database with five books
- **THEN** one line gives five books and the passage, figure and collection counts, and no title appears

## Note on the BM25 index

The full-text index of the PostgreSQL route (`knowledge.chunks_bm25`, migration 0005) can become unreadable ("bitmap intersection stream … claimed twice", pg_search 0.26.0). Detection is the indexer's probe command (requirement "Probe the BM25 index on request" above), run after every successful indexing by `watch-pipeline` (daily check); the rebuild procedure is section 14.6 of the installation guide. There is no fallback route: while the index is damaged, a search tool answers an error object (library-search-mcp-server), and the snapshot comparison of library-search-parity checks after the rebuild that the search ranks as before.

## Open questions

1. `tests/pmzilla_lab_library/test_coherence_noms.py` checks naming across repository files (rules file, test cases); it is described in the MCP server spec, and the exact scope of the files scanned is not established.
