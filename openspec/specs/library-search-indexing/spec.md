# library-search-indexing

## Purpose

Building and maintaining the SQLite library index from Markdown collections: incremental indexing, passage splitting, figure passages, forced recomputation, collection renaming, schema migration, and the caption diagnostic.

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
The system SHALL recompute embeddings only for added or modified books, SHALL replace the passages of a modified book entirely (including its keyword index), SHALL remove a book whose file disappeared (naming it), SHALL recompute everything when the embedding model changes, and SHALL NOT call the embedding model when nothing changed.

Source: `tests/pmzilla_lab_library/test_pmzilla_lab_library.py` (Indexation.test_inchange_ne_recalcule_rien, test_ajout, test_modification_remplace_les_passages, test_fichier_supprime_sort_de_l_index, test_changement_de_modele_reindexe)

#### Scenario: Unchanged run
- **WHEN** indexing is run twice on the same files
- **THEN** the second run reports zero indexed and makes no embedding call

#### Scenario: Modified book
- **WHEN** a book is rewritten
- **THEN** only its passages are replaced and words that disappeared are no longer found by keyword search

#### Scenario: Deleted file
- **WHEN** a file is deleted from the folders
- **THEN** its book and passages leave the index and the report names it

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
The system SHALL accept a recompute option naming books (by name with or without extension, by path, in any letter case, or by a list file with comments and blank lines) and SHALL recompute only those books even if their Markdown is unchanged. It SHALL refuse the option without a book or without a folder, and SHALL stop before touching the index, saying nothing was indexed, when a name is unknown or ambiguous. It SHALL NOT create any backup of the index.

Source: `tests/pmzilla_lab_library/test_figures.py` (Recalcul)

#### Scenario: One book
- **WHEN** one book is designated
- **THEN** the report says one indexed and the others unchanged, and its figure passages are replaced

#### Scenario: List file
- **WHEN** a list file names two books with comments and blank lines
- **THEN** both are recomputed

#### Scenario: Unknown or ambiguous name
- **WHEN** one designated name does not exist or matches two files
- **THEN** the command stops, says nothing was indexed, makes no embedding call and leaves the index unchanged

#### Scenario: Reference record enriched
- **WHEN** an old index has figure reference records without origin and the books are recomputed
- **THEN** each figure then records a caption or an alternative text

#### Scenario: No backup
- **WHEN** books are recomputed
- **THEN** no new index backup file appears and an existing one is untouched

### Requirement: Rename a collection in place
The system SHALL rename a collection in the stored index without recomputing anything, SHALL support a dry run that changes nothing and says what would be renamed, SHALL be idempotent (saying there is nothing to do), SHALL deduplicate a book that already holds the new name, and SHALL keep passages, keyword index and other books intact. While indexing, a folder that carries a former collection name SHALL be stored under the new name with a warning and without recomputation.

Source: `tests/pmzilla_lab_library/test_pmzilla_lab_library.py` (Renommage.test_rename_collection_en_place_sans_recalcul, test_rename_collection_dry_run_et_idempotence, test_rename_collection_dedoublonne, test_rename_collection_en_ligne_de_commande, test_dossier_ancien_nom_indexe_sous_le_nouveau, test_deplacement_de_dossier_ne_recalcule_rien)

#### Scenario: Rename
- **WHEN** a collection is renamed from its former to its current name
- **THEN** the stored name changes, the report counts the books, and passages, vectors and the keyword index are unchanged

#### Scenario: Dry run and repeat
- **WHEN** the rename is run with the dry-run option, then for real, then again
- **THEN** the first changes nothing and says "would be renamed", the second renames, the third says nothing to do

#### Scenario: Folder with former name
- **WHEN** the watch folder is renamed to its former name and indexing is run
- **THEN** the books stay under the current name, a warning names the former name and nothing is recomputed

### Requirement: Migrate an old index without loss
The system SHALL add the passage kind and reference columns to an index created before figures existed, SHALL give existing passages the text kind and an empty reference, SHALL keep texts, vectors, keyword index and book table intact, SHALL be idempotent, and SHALL let an old index be searched immediately (text hits, no figures). A new index SHALL have the columns and a kind index from the start.

Source: `tests/pmzilla_lab_library/test_figures.py` (Migration)

#### Scenario: Old index
- **WHEN** an old index is opened
- **THEN** every passage is kind text with an empty reference, and the keyword search still finds the old words

#### Scenario: Open twice
- **WHEN** the migration runs twice
- **THEN** the result is the same and searches still work

#### Scenario: Old book removed
- **WHEN** a book with figures is indexed in a migrated index and the old book is absent from the folders
- **THEN** the old book is reported removed and the new book has its figure passages

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

## Note on the BM25 index

The full-text index of the PostgreSQL route (`knowledge.chunks_bm25`, migration 0005) can become unreadable ("bitmap intersection stream … claimed twice", pg_search 0.26.0). Detection and the rebuild procedure are specified in `library-search-knowledge-import` (probe of the verification command) and `watch-pipeline` (daily check); the SQLite indexing described here is the fallback while the index is damaged.

## Open questions

1. `tests/pmzilla_lab_library/test_coherence_noms.py` checks naming across repository files (rules file, test cases); it is described in the MCP server spec, and the exact scope of the files scanned is not established.
