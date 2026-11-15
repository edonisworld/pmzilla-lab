# library-search-domain-sorting

## Purpose

Distribution of converted Markdown books into domain collection folders from a classification table, the consistency rules of that table, and the read-only table of books set aside by the sorting.

Source of truth: `tests/sort_by_domain/test_sort_by_domain.py`, `tests/sort_by_domain/test_sorting_exclusions.py`, `tools/sort_by_domain.py`, `tools/sorting_exclusions.py`, `tools/mapping_lab.py`. The book catalogue `tools/book_catalog.yaml` is read by the indexer and specified in `library-search-indexing`.

## Requirements

### Requirement: Copy each book into the folder of each of its domains
The system SHALL copy (never move or modify) each classified Markdown book into one folder per domain code of its table entry, the folder name being the collection name, SHALL copy a book of several domains into each, SHALL copy a book once even if a domain code is repeated, and SHALL print the number of books copied per domain.

Source: `tests/sort_by_domain/test_sort_by_domain.py` (Ventilation); `tests/sort_by_domain/test_mapping_prive.py` (TroisLivresDuPilote)

#### Scenario: Several domains
- **WHEN** five books are classified with codes for one domain each and one book with two domains
- **THEN** each domain folder holds its books, the two-domain book is in both, and the report counts per domain

#### Scenario: Originals
- **WHEN** a book is copied
- **THEN** the original file is unchanged and the copies have the same content

### Requirement: Sort into the five library domains
The domains SHALL be product, flow, organisation, facilitation and tech.

Source: `tests/sort_by_domain/test_sort_by_domain.py` (MappingReel.test_domaines_documentes)

#### Scenario: Domain list
- **WHEN** the domains of the sorting are listed
- **THEN** they are product, flow, organisation, facilitation and tech

### Requirement: Set aside duplicates and report what is missing or unclassified
The system SHALL not copy books whose entry has an empty domain code and SHALL list them as set aside, SHALL list entries whose file is not found (but not set-aside ones that are present), SHALL list Markdown files present but not in the table (ignoring service files starting with an underscore and non-Markdown files), and SHALL create no output folder when the table is empty.

Source: `tests/sort_by_domain/test_sort_by_domain.py` (Ventilation)

#### Scenario: Set aside
- **WHEN** one entry has an empty code
- **THEN** it is not copied and appears in the set-aside list

#### Scenario: Not found
- **WHEN** entries point to absent files
- **THEN** they are listed as not found and present books are still copied

#### Scenario: Unclassified
- **WHEN** a new Markdown file is not in the table
- **THEN** it is listed as present but unclassified, while service files and non-Markdown files are not

### Requirement: Stop before any copy on an unknown domain code
The system SHALL check all domain codes of the table before copying, SHALL stop with exit failure and list every unknown code (even for files that are absent) and the valid codes, and SHALL copy nothing, not even valid books classified earlier.

Source: `tests/sort_by_domain/test_sort_by_domain.py` (Ventilation.test_code_inconnu_arrete_avant_toute_copie, test_tous_les_codes_inconnus_listes_meme_pour_un_fichier_absent)

#### Scenario: One unknown code
- **WHEN** one entry holds a code outside the valid ones
- **THEN** the message gives the count, the file and the code, the valid codes, and says nothing was copied; the output folder does not exist

#### Scenario: Several
- **WHEN** several unknown codes are spread over present and absent files
- **THEN** all are listed

### Requirement: Reject files whose name would collide
The system SHALL treat two classified books with the same file name (different folders, different domains, or differing only by letter case) as duplicates, SHALL copy the first and report each following one with the name of the one it duplicates, SHALL never overwrite one file with another, and SHALL not count set-aside books as duplicates.

Source: `tests/sort_by_domain/test_sort_by_domain.py` (Ventilation)

#### Scenario: Same name in two folders
- **WHEN** two classified books share a file name
- **THEN** the first is copied with its content, the second is reported as a duplicate of the first, and no classified note says it is unclassified

#### Scenario: Different domains
- **WHEN** same-named books go to different domains
- **THEN** still only the first is copied, because the library groups by file name

#### Scenario: Letter case
- **WHEN** names differ only by case
- **THEN** they are duplicates

### Requirement: Count each copy once and rerun identically after a duplicate
The report SHALL count a book once per copy actually made, and a rerun SHALL give the same result.

Source: `tests/sort_by_domain/test_sort_by_domain.py` (Ventilation.test_relance_apres_doublon_idempotente)

#### Scenario: Rerun after a duplicate
- **WHEN** the sorting is run again after a duplicate was reported
- **THEN** the result is the same and the report counts each book once per copy made

### Requirement: Be idempotent and tolerant of accent encodings
The system SHALL give the same result when run again and SHALL match entries whose accented names are stored in composed or decomposed form.

Source: `tests/sort_by_domain/test_sort_by_domain.py` (Ventilation.test_relance_idempotente, test_noms_accentues_nfd_et_nfc)

#### Scenario: Rerun
- **WHEN** the sorting is run twice
- **THEN** the folders hold the same files

#### Scenario: Accents
- **WHEN** the file is stored decomposed and the table entry composed
- **THEN** the book is neither "not found" nor "unclassified" and is copied once

### Requirement: Match by full path when source folders were renamed
The system SHALL match table entries on the full relative path, so that a book in a renamed (numbered) folder is not paired with an entry of the old folder name, SHALL report the entry as not found and the book as unclassified, SHALL not let a duplicate in a renamed folder disturb the classified book, and SHALL ignore a trash folder outside the source folder.

Source: `tests/sort_by_domain/test_sort_by_domain.py` (DossiersRenommes)

#### Scenario: Only the renamed folder exists
- **WHEN** the book is only under the new folder name
- **THEN** nothing is copied, the entry is reported not found and the book unclassified

#### Scenario: Both exist
- **WHEN** the book exists under both folder names
- **THEN** the classified one is copied, the other is listed unclassified, and no duplicate message appears

### Requirement: Fail on bad arguments or a missing source
The system SHALL exit with failure for a missing source folder or a wrong argument count.

Source: `tests/sort_by_domain/test_sort_by_domain.py` (Ventilation.test_dossier_source_absent_et_arguments)

#### Scenario: One argument
- **WHEN** only one folder is given
- **THEN** the exit code is 1

### Requirement: Keep the classification table internally consistent
The classification table SHALL use only known domain codes with no repetition inside an entry, SHALL have unique keys and unique copied file names, SHALL hold only keys under the conversion output folder, and SHALL document the five domains.

Source: `tests/sort_by_domain/test_sort_by_domain.py` (MappingReel)

#### Scenario: Codes
- **WHEN** every entry is inspected
- **THEN** its codes are known and distinct

#### Scenario: Keys
- **WHEN** keys are compared after Unicode normalisation
- **THEN** none is repeated and copied entries have distinct file names

### Requirement: Keep the explicit sources and exclusions of the table consistent
The classification table SHALL have explicit-source targets that are keys of the table and copied (not set aside) with no two sources sharing a target, and SHALL give each exclusion a non-empty reason and keep exclusions distinct from explicit sources.

Source: `tests/sort_by_domain/test_sort_by_domain.py` (MappingReel)

#### Scenario: Explicit sources and exclusions
- **WHEN** the explicit sources and exclusions are inspected
- **THEN** each source targets a copied key, no two share a target, and each exclusion has a reason and is not also an explicit source

### Requirement: List the books set aside with kept edition, reason, size, format and figures
The system SHALL produce a table of the books set aside by the sorting, giving for each one the kept book (with its domain codes) or "none (not a duplicate)" for set-aside books without duplicate, the reason taken from the table comment, the Markdown sizes, the source formats and the figure counts of both files, and SHALL start with a summary of counts by kind.

Source: `tests/sort_by_domain/test_sorting_exclusions.py` (Tableau, GardesEtMapping)

#### Scenario: Rows
- **WHEN** the table is built for one duplicate, one off-topic book and one unidentified book
- **THEN** the summary counts one duplicate, one without duplicate and one to identify, and each row shows kept book, reason, sizes, formats and figure counts

### Requirement: Read only sizes and header lines for the set-aside table
The set-aside table SHALL read only file size and the first header lines (source and figures), never book text, and SHALL modify nothing.

Source: `tests/sort_by_domain/test_sorting_exclusions.py` (Tableau.test_lecture_seule)

#### Scenario: Read-only
- **WHEN** the table is built
- **THEN** no file is changed or created

### Requirement: Mark unidentified and missing entries in the set-aside table
The system SHALL mark a set-aside entry that is absent from the kept-book map as "to identify" with a missing comment note, and SHALL show "absent" for missing files.

Source: `tests/sort_by_domain/test_sorting_exclusions.py` (Tableau.test_lignes_taille_format_et_figures, test_garde_absent_du_disque)

#### Scenario: Unidentified entry
- **WHEN** the table is built for a set-aside entry absent from the kept-book map
- **THEN** its row is marked "to identify" with a missing comment note

#### Scenario: Kept book missing from disk
- **WHEN** the kept book's file is absent
- **THEN** its size, format and figure cells read "absent"

### Requirement: Check that set-aside books and kept-book map agree with the classification table
The system SHALL keep the set of set-aside entries in the classification table equal to the keys of the kept-book map, SHALL require every kept book to be an entry copied by the sorting, and SHALL require a comment (reason) on every set-aside entry.

Source: `tests/sort_by_domain/test_sorting_exclusions.py` (GardesEtMapping)

#### Scenario: Equality
- **WHEN** the entries with empty domain code are compared with the kept-book map
- **THEN** they are the same set

#### Scenario: Kept book copied
- **WHEN** each kept book is looked up in the table
- **THEN** its domain code is non-empty

## Open questions

1. `tools/mapping_lab.py` comments are also read by the dashboard (per its docstring) to list missing books; that behavior belongs to another domain and is not specified here.
