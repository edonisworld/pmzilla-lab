# library-search-book-conversion

## Purpose

Conversion of PDF and EPUB books into Markdown: format preference and fallback, in-place rewriting with a one-time backup, quality reports, figure blocks and the filter of alternative texts, selective redo and single-book conversion with source-to-Markdown resolution, exclusions, a read-only figure statistics mode, and former-option aliases. A legacy PDF-only converter also exists.

Source of truth: `tests/convert_books/test_convert_books.py`, `tests/convert_books/test_figures_blocs.py`, `tests/convert_books/test_statistiques_figures.py`, `tests/convert_books/test_noms_options.py`, `tools/convert_books.py`, `tools/convert_pdfs.py`, `tools/mapping_lab.py`.
## Requirements
### Requirement: Convert PDF and EPUB to Markdown with a header
The system SHALL convert each book under the source folder (any sub-folder, any letter case of the extension, other file types ignored) into Markdown with a header holding title, source file name, page count (PDF only) and figure count, SHALL take the title from the book and fall back on the file name, and SHALL keep chapter titles of an EPUB, taking the title from the table of contents for a chapter without a heading tag.

Source: `tests/convert_books/test_convert_books.py` (Formats.test_pdf_avec_texte, test_epub_avec_texte_titres_et_table_des_matieres, test_titre_de_repli_sur_le_nom_du_fichier, Selection.test_extensions_en_majuscules_et_autres_fichiers)

#### Scenario: PDF with text
- **WHEN** a text PDF is converted
- **THEN** the Markdown header holds the title, the source, the page count and zero figures, and the text is present

#### Scenario: EPUB with chapters
- **WHEN** an EPUB with a heading chapter and a chapter lacking a heading tag is converted
- **THEN** both titles appear once as headings and the header has no page count

#### Scenario: Empty title
- **WHEN** the EPUB title is blank
- **THEN** the title falls back on the file name

### Requirement: Prefer the EPUB and fall back on the PDF of the same book
The system SHALL, when a book exists as EPUB and PDF with the same name (letter case ignored, same folder), convert the EPUB and ignore the PDF, report the ignored PDFs, and, when the EPUB fails to convert, convert the PDF in its place and report the fallback in the report and on the terminal. A PDF of the same name in another folder SHALL NOT be treated as a duplicate. When both fail, two errors SHALL be reported.

Source: `tests/convert_books/test_convert_books.py` (Selection.test_epub_prefere_au_pdf_meme_nom, Formats.test_epub_corrompu_repli_sur_le_pdf_et_rapport, test_epub_et_pdf_en_echec_sont_deux_erreurs, test_epub_corrompu_sans_pdf_reste_une_erreur, test_repli_sur_un_pdf_scanne_est_a_verifier)

#### Scenario: Both formats
- **WHEN** a book exists as EPUB and PDF
- **THEN** the EPUB is converted, the PDF is listed as ignored because the EPUB exists

#### Scenario: Corrupt EPUB with a PDF
- **WHEN** the EPUB is corrupt and the PDF is valid
- **THEN** the Markdown comes from the PDF, the report counts one fallback and no error

#### Scenario: Both corrupt
- **WHEN** both files are corrupt
- **THEN** two errors are reported and the previous Markdown is kept

#### Scenario: Fallback onto a scanned PDF
- **WHEN** the fallback PDF is scanned
- **THEN** it is flagged to check

### Requirement: Rewrite existing Markdown in place and back it up once
The system SHALL find the existing Markdown of each book by the same resolution as the redo mode and rewrite it at its place, SHALL NOT recreate the source folder tree, SHALL keep the previous version beside it as a backup written only the first time, and SHALL rewrite everything at each run (no resume), reporting the number of previous versions already there.

Source: `tests/convert_books/test_convert_books.py` (Selection.test_le_markdown_garde_son_emplacement_aucune_arborescence_recreee, test_tout_est_reecrit_a_chaque_passage_ancien_garde_une_seule_fois, Formats.test_repli_est_reecrit_a_chaque_passage_avec_l_ancien_garde_une_fois), `tests/convert_books/test_figures_blocs.py` (RefaireLesFigures.test_la_conversion_normale_reecrit_tout_sur_place_avec_sauvegarde)

#### Scenario: Renamed shelf
- **WHEN** the Markdown of a deeply nested source sits in another folder
- **THEN** it is rewritten there and no folder mirroring the source is created

#### Scenario: Second run
- **WHEN** the Markdown was edited by hand and the conversion runs again
- **THEN** it is rewritten from the book and the backup still holds the first previous version

### Requirement: List books without Markdown instead of converting them
The system SHALL NOT convert a book that has no existing Markdown, SHALL list it on the terminal and in the report with a pointer to the single-book mode, and SHALL create no image folder for it.

Source: `tests/convert_books/test_convert_books.py` (Selection.test_livre_sans_markdown_est_liste_et_non_converti)

#### Scenario: One book without Markdown
- **WHEN** one of two books has no Markdown
- **THEN** only the other is converted, the first is listed with its relative path and nothing is created for it

### Requirement: Report conversion quality without stopping on errors
The system SHALL flag PDFs with very little text as probably scanned (still converting them), flag almost-empty EPUBs, SHALL isolate corrupt or empty files as errors that keep the previous Markdown and are retried at the next run, SHALL write a conversion report with counts (converted, to check, errors, fallbacks, ignored PDFs, books without Markdown, excluded), and SHALL stop with an error for a wrong argument count or a missing source folder.

Source: `tests/convert_books/test_convert_books.py` (Formats.test_pdf_scanne_signale, test_epub_presque_vide_signale, test_fichiers_corrompus_ne_bloquent_pas_les_autres, Selection.test_arguments_et_dossier_absent, test_dossier_vide)

#### Scenario: Scanned PDF
- **WHEN** a PDF without text is converted
- **THEN** the Markdown exists and the report lists it as probably scanned for its page count

#### Scenario: Corrupt files
- **WHEN** corrupt or empty files are among valid books
- **THEN** valid books are converted, the corrupt ones keep their previous Markdown, the report counts errors, and a later run converts a repaired file

#### Scenario: Empty folder
- **WHEN** the source folder holds no book
- **THEN** the run says zero books found and the report says zero converted

### Requirement: Turn retained figures into Markdown blocks
The system SHALL turn a figure into a block (comment with identifier, source format, page for PDFs and image path, followed by caption and alternative text lines) only when it is retained, SHALL number identifiers in book order, SHALL keep the book's running text unchanged apart from the blocks, SHALL place PDF blocks after the text of their page, SHALL leave no provisional marker or Markdown image syntax, and SHALL record the retained-figure count in the header.

Source: `tests/convert_books/test_figures_blocs.py` (EpubBlocs, PdfBlocs)

#### Scenario: EPUB figures
- **WHEN** an EPUB has captioned images, an image with only a useful alternative text, an inline vector graphic, and discarded images
- **THEN** only the retained figures become blocks, numbered in order of appearance, and discarded ones leave no trace

#### Scenario: Neighbouring caption
- **WHEN** a caption sits beside an image
- **THEN** it appears once in the Markdown

#### Scenario: PDF figures
- **WHEN** a PDF has a captioned embedded image and a captioned vector drawing
- **THEN** each becomes a block with its page, and a visual without a numbered caption does not

#### Scenario: PDF without numbered caption
- **WHEN** a PDF has no numbered figure caption
- **THEN** it is converted as before with zero figures and no image folder

### Requirement: Retain a figure only with a caption or a useful alternative text
The system SHALL retain an EPUB image when it has a caption or an alternative text that is useful, and SHALL classify an alternative text as not useful when it is empty, a file name, a generic word (such as image, photo, logo, or a bare figure number), or too short without a caption, with a configurable minimum word count that is waived when a caption exists. For PDFs the system SHALL retain only visuals with a numbered caption.

Source: `tests/convert_books/test_figures_blocs.py` (FiltreDesTextesAlternatifs.test_etats, test_seuil_de_quatre_mots_sans_legende, StatistiquesAvantReconversion)

#### Scenario: Classification
- **WHEN** alternative texts "IMG_0042.png", "Logo", "Trois colonnes" and "Courbe du lead time" are classified without caption
- **THEN** they are respectively file name, generic, too short and useful

#### Scenario: With a caption
- **WHEN** the same short alternative text comes with a caption
- **THEN** it is useful

#### Scenario: Threshold in one place
- **WHEN** the word threshold is changed
- **THEN** classification follows

### Requirement: Extract images only for retained figures, outside version control
The system SHALL save the image of each retained figure under a per-book folder in the images folder (PDF: the page area rendered as an image at a resolution larger than a thumbnail; EPUB: the embedded, inline or vector image), SHALL NOT extract images of discarded figures, SHALL write a block without an image path when the image cannot be found, SHALL create no folder for a book without retained figures, SHALL remove old images of a redone book, and SHALL report counts of blocks and images. The images folder SHALL be ignored by version control and unreadable by the assistant, and SHALL default to a folder inside the workspace.

Source: `tests/convert_books/test_figures_blocs.py` (EpubBlocs.test_images_extraites_seulement_pour_les_figures_retenues, PdfBlocs.test_images_rendues_seulement_pour_les_figures_retenues, EpubBlocs.test_rapport_de_conversion, EpubBlocs.test_livre_sans_figure_retenue, Cadre)

#### Scenario: Missing image
- **WHEN** a retained figure's image is not in the book
- **THEN** its block has no image path and no file is written for it

#### Scenario: Report counts
- **WHEN** six blocks and five images are produced
- **THEN** the terminal and the report say six blocks and five images

#### Scenario: Protection
- **WHEN** the repository settings are inspected
- **THEN** the images folder is ignored by version control and denied for reading to the assistant

### Requirement: Redo figures for named books only
The system SHALL, with the redo option, reconvert only the named books (relative path with or without extension, file name, any letter case, or a list file with comments, with a trailing comment allowed and a "#" inside a name not being a comment), SHALL find the existing Markdown by explicit source mapping, then by file name anywhere in the output folder, then by the shared classification table (key named after the book, or whose header declares the book as its source, ignoring case and accents, keys of other folders ignored), SHALL rewrite it in place with a one-time backup, SHALL leave unnamed books untouched, SHALL prefer the EPUB over the PDF of the same book, SHALL write a figures report without overwriting the full conversion report, and SHALL remind the user to rerun the domain sorting.

Source: `tests/convert_books/test_figures_blocs.py` (RefaireLesFigures, RefaireDossiersRenommes, RefaireParMapping, CorrespondanceExplicite), `tests/convert_books/test_statistiques_figures.py` (ListeAFaire.test_la_liste_se_relit_par_refaire_figures_commentaires_ignores, test_un_dieze_dans_un_nom_n_est_pas_un_commentaire)

#### Scenario: One book
- **WHEN** one named book is redone
- **THEN** its Markdown gains figure blocks, its backup holds the previous text, the other book is intact, and old images are removed

#### Scenario: Repeated redo
- **WHEN** the redo runs twice on a book
- **THEN** the backup still holds the first previous version and the Markdown is the same

#### Scenario: Name forms
- **WHEN** books are named by extension in capitals and through a list file
- **THEN** both are redone

#### Scenario: File name before table
- **WHEN** a book matches by file name and another only by the table
- **THEN** the first goes by the file name path and the second by the table path, and the route is shown in the output and the report

#### Scenario: Explicit mapping first
- **WHEN** a source is given an explicit Markdown target
- **THEN** that Markdown is rewritten even though a file of the same name exists, and the table route is not consulted

#### Scenario: Conversion failure
- **WHEN** a book fails to convert
- **THEN** its existing Markdown is kept, no backup is made and one error is reported

### Requirement: Stop before any conversion on any resolution problem
The system SHALL, whenever a redo or normal run has a book with no match, several matches, an explicit mapping to an absent Markdown, a table key to an absent file, two books mapped to the same Markdown, a duplicated Markdown in the output folder, a source that is unknown or ambiguous, or a missing book name, stop before converting anything and list all errors with a "nothing was converted" statement, leaving the file tree and image folder unchanged.

Source: `tests/convert_books/test_figures_blocs.py` (RefaireLesFigures.test_nom_introuvable_ou_ambigu_arrete_avant_toute_conversion, test_option_sans_livre; RefaireDossiersRenommes.test_markdown_introuvable_arrete_avant_toute_conversion, test_markdown_en_double_arrete_et_liste_les_chemins; RefaireParMapping; ConversionNormaleParRecherche; CorrespondanceExplicite)

#### Scenario: Unknown book among valid ones
- **WHEN** a redo names one valid and one unknown book
- **THEN** the run stops, says nothing was converted, and the valid book is not touched either

#### Scenario: Ambiguous name
- **WHEN** a name matches two sources
- **THEN** the run stops saying it is ambiguous, and a relative path removes the ambiguity

#### Scenario: Several table matches
- **WHEN** several table keys match one book
- **THEN** the run stops and names the book

#### Scenario: Redo without a book
- **WHEN** the redo option has no book
- **THEN** the run stops asking for at least one book

### Requirement: Simulate resolution without writing
The system SHALL, with the dry-run option on normal or redo runs, resolve and display each source, its Markdown and the route taken, the books without Markdown, the excluded sources with their reason and all errors, SHALL write no Markdown, backup, report or image and open no book, and SHALL exit with 1 when an error exists.

Source: `tests/convert_books/test_figures_blocs.py` (Simulation, ConversionNormaleParRecherche.test_simulation_resout_liste_et_n_ecrit_rien, test_simulation_affiche_toutes_les_erreurs, test_simulation_sans_dossier_de_sortie, CorrespondanceExplicite.test_simulation_dit_la_voie_et_ne_modifie_rien, Exclusions.test_simulation_liste_l_exclu_avec_sa_raison)

#### Scenario: Clean simulation
- **WHEN** the dry run resolves all books
- **THEN** it displays source, Markdown and route per book and the file tree is unchanged

#### Scenario: Errors
- **WHEN** the dry run finds problems
- **THEN** all are displayed and the exit code is 1

### Requirement: Convert a single never-converted book into a given Markdown path
The system SHALL, with the single-book option and a target path, convert that one book into the given path relative to the output folder, SHALL refuse (writing nothing) if the Markdown exists, if another Markdown has the same file name, if the path is not a key of the classification table, if the path is invalid (leaving the folder, no Markdown extension, absolute, empty segment), if the book is unknown or ambiguous, or if an option is missing, SHALL write nothing when the conversion fails, SHALL touch no other book, create no folder at the new source name, and SHALL write a single-book report and remind the user to rerun the domain sorting.

Source: `tests/convert_books/test_figures_blocs.py` (ConvertirUnLivre)

#### Scenario: Success
- **WHEN** a new book is converted into an existing folder
- **THEN** its Markdown with figure blocks exists there, only its images are created, no folder appears under the new source name, and the existing Markdown is untouched

#### Scenario: Refusals
- **WHEN** the target exists, is taken elsewhere by name, is not a table key, or is an invalid path
- **THEN** the run is refused with the matching message and the tree is unchanged

#### Scenario: Failed conversion
- **WHEN** the book is corrupt
- **THEN** the run says nothing was written

### Requirement: Skip excluded sources with their reason
The system SHALL ignore in the normal conversion the sources listed in the exclusion table, SHALL NOT list them as without Markdown, SHALL report them with their reason on the terminal and in the report, SHALL leave the Markdown of the kept edition untouched, and SHALL refuse them in the redo mode with their reason.

Source: `tests/convert_books/test_figures_blocs.py` (Exclusions)

#### Scenario: Normal run
- **WHEN** an excluded source sits beside its kept edition
- **THEN** it is neither converted nor listed as without Markdown, and it appears under excluded with its reason

#### Scenario: Redo of an excluded book
- **WHEN** the redo names an excluded book
- **THEN** the run stops stating the book is excluded and why, and the dry run exits with 1

#### Scenario: Without the exclusion
- **WHEN** the exclusion table is empty
- **THEN** the same source is listed as without Markdown

### Requirement: Share one classification table between conversion and sorting
The system SHALL use one classification table and one domain table for both the conversion and the domain sorting, with a letter-case- and accent-insensitive comparison of names that treats composed and decomposed accents as equal.

Source: `tests/convert_books/test_figures_blocs.py` (TableCommune)

#### Scenario: Same objects
- **WHEN** the conversion and sorting modules are loaded
- **THEN** their classification and domain tables are the same object

#### Scenario: Folding
- **WHEN** two names differ only in case and accents
- **THEN** their folded forms are equal

### Requirement: Compute figure statistics without converting
The system SHALL offer a statistics mode that, for each book, counts visuals (vector graphics included), numbered captions, other captions, non-empty alternative texts (useful, not useful with reasons, repeated identical ones), retained figures (those a conversion would create), decorative items, scanned pages, errors and EPUB-to-PDF fallbacks; SHALL exclude covers and scanned pages; SHALL recognise caption label variants; SHALL not let a caption above an image take the next image; and SHALL agree with the conversion on which figures are retained.

Source: `tests/convert_books/test_statistiques_figures.py` (Epub, Pdf), `tests/convert_books/test_figures_blocs.py` (StatistiquesAvantReconversion)

#### Scenario: EPUB units
- **WHEN** an EPUB has figures with captions, isolated images and a vector graphic
- **THEN** visuals, vector, numbered caption, caption, alternative-text, useful, not-useful, reasons, retained and decorative counts are those of the fixture

#### Scenario: Label variants
- **WHEN** captions use "Figure 1.2", "Fig. 3-4", "Exhibit 5" or similar and prose such as "La figure 1.2 montre"
- **THEN** the former are labels and the latter is not

#### Scenario: Scanned PDF
- **WHEN** a PDF is image-only pages
- **THEN** its pages are counted scanned and not as figures

#### Scenario: Same figures as the conversion
- **WHEN** the statistics and the conversion run on the same book
- **THEN** the retained count equals the number of figure blocks created

### Requirement: Write a detail table and a title-free aggregate, and a redo list
The system SHALL print a per-book detail table followed by an aggregate by format and in total that contains no book title or path and is the last part of the output, SHALL write the output to a statistics file in the output folder (default inside the workspace, unreadable by the assistant), SHALL write a list of books having at least one retained figure (relative path, extension, count in a comment) usable by the redo option, replacing it at each run, SHALL modify no book and write no Markdown, and SHALL give the same figures at a second run.

Source: `tests/convert_books/test_statistiques_figures.py` (Rapport, ListeAFaire, Cadre)

#### Scenario: Aggregate
- **WHEN** statistics run on a mixed folder
- **THEN** the aggregate holds per-format and total counts, repeats no title, and the last line starts with a reading note

#### Scenario: Written files
- **WHEN** statistics run
- **THEN** only the statistics file appears in the output folder, and the books are byte-identical

#### Scenario: Redo list
- **WHEN** the list is written
- **THEN** it holds one line per book with retained figures, with relative paths, and omits books without figures, errors and ignored PDFs

#### Scenario: Protection
- **WHEN** the repository settings are inspected
- **THEN** reading the statistics file is denied for the assistant

### Requirement: Former option names refused
The system SHALL refuse the former French names of the statistics and single-book options with an error naming the current option, SHALL convert nothing, and SHALL print no message for the current names.

#### Scenario: Current names
- **WHEN** the current option names are used
- **THEN** no message appears

#### Scenario: Former names
- **WHEN** a former name is used
- **THEN** the action does not run and the error names the current option

