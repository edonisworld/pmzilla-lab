# jira-flow-compare Specification

## Purpose

Describes the comparison tool that checks the database route against the CSV route. The comparison is asymmetric: the CSV route is the reference and the database is compared against it, until a later decision. It compares the data read by both routes and compares two report files, reporting counts only and never a ticket key, a team name or a value. Sources are `tests/flow_compare/test_flow_compare.py`.

## Requirements

### Requirement: Subcommands and exit codes
The system SHALL offer `reports <report-a> <report-b>`. The exit code SHALL be 0 when there is no difference (with a "no difference" message), 1 when differences exist, and 2 when an input file cannot be read. The retired subcommand `data` SHALL be refused with exit code 2 and the key phrase of design D9, without any database connection or file read.

Source: tests/flow_compare/test_flow_compare.py (test_main_rapports_codes_de_sortie, test_main_de_bout_en_bout, test_data_refusee_avec_la_phrase_de_la_conception_dans_les_deux_langues, test_data_ne_lit_aucun_fichier_et_n_ouvre_aucune_connexion)

#### Scenario: Equal reports
- **WHEN** two reports differ only by their title
- **THEN** the output says no difference and the exit code is 0

#### Scenario: Different or missing
- **WHEN** one line differs, or a file is absent
- **THEN** the exit code is 1, respectively 2

#### Scenario: Retired data subcommand
- **WHEN** `data` is run with an export path
- **THEN** the output holds "data is retired: the CSV route no longer exists", the exit code is 2, and no file or database is opened

### Requirement: Report comparison
The system SHALL compare two Markdown reports line by line after normalizing the title, the merge line and the export line (file names versus "database" in either language, while a different count is still a difference), align the lines so one inserted line does not shift the rest, and report the remaining differences as a count per section number, with no content. A list in a different order SHALL be a localized difference.

Source: tests/flow_compare/test_flow_compare.py (test_rapports, test_alignement_*, test_ligne_export_*, test_ecarts_restants_*, test_listes_dans_un_autre_ordre_*)

#### Scenario: Merge line ignored
- **WHEN** one report adds a merge line and the same lines otherwise
- **THEN** there is no difference

#### Scenario: Per-section output
- **WHEN** two sections have differing lines
- **THEN** the output gives "section 2: 1 line(s) differ" and "section 3: 1 line(s) differ", without text, and never "section 0"

### Requirement: Message catalogs
The system SHALL keep consistent message catalogs across languages.

Source: tests/flow_compare/test_flow_compare.py (test_catalogues_coherents)

#### Scenario: Catalog check
- **WHEN** the catalogs are checked
- **THEN** no inconsistency is reported

## Open questions

1. The tool is meant to be run by the user only on real data; the access rule is not specified here.
