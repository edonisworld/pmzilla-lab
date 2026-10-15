# jira-flow-compare Specification

## Purpose

Describes the comparison tool that checks the database route against the CSV route. The comparison is asymmetric: the CSV route is the reference and the database is compared against it, until a later decision. It compares the data read by both routes and compares two report files, reporting counts only and never a ticket key, a team name or a value. Sources are `tests/flow_compare/test_flow_compare.py`.

## Requirements

### Requirement: Subcommands and exit codes
The system SHALL offer `data <export>... [--history [cache]]` and `reports <report-a> <report-b>`. The exit code SHALL be 0 when there is no difference (with a "no difference" message), 1 when differences exist, and 2 when an input file cannot be read.

Source: tests/flow_compare/test_flow_compare.py (test_main_rapports_codes_de_sortie, test_main_de_bout_en_bout)

#### Scenario: Equal reports
- **WHEN** two reports differ only by their title
- **THEN** the output says no difference and the exit code is 0

#### Scenario: Different or missing
- **WHEN** one line differs, or a file is absent
- **THEN** the exit code is 1, respectively 2

### Requirement: CSV route is the reference
The system SHALL treat the CSV route as the reference side and the database route as the compared side, SHALL NOT treat the comparison as symmetric, and SHALL label differences from that point of view (present on the CSV side only, present on the database side only), until a later decision changes this.

Source: tests/flow_compare/test_flow_compare.py (test_comparer_dicts_ne_montre_que_des_comptes, AvecBase)

#### Scenario: Labels
- **WHEN** a ticket exists on one side only
- **THEN** the output names the side as "CSV only" or "database only", the CSV side being the reference

### Requirement: Field comparison reports counts only
The system SHALL compare two keyed collections field by field and report only counts: tickets only on the CSV side, only on the database side, per differing field, and per project of the differences, never a key, a team name or a value. Identical data SHALL give zero differences.

Source: tests/flow_compare/test_flow_compare.py (test_comparer_dicts_ne_montre_que_des_comptes, test_donnees_identiques_ne_donnent_aucun_ecart, AvecBase)

#### Scenario: Counts only
- **WHEN** one ticket exists on each side only and two fields differ on a common ticket
- **THEN** the total is four, the counts "CSV only: 1", "database only: 1" and one line per differing field appear, and no key or team name does

#### Scenario: Data route
- **WHEN** an export is imported and then compared with itself
- **THEN** there is no difference, and after altering a status and deleting a ticket in the database the output counts "CSV only 1" and "status differs 1" without values

### Requirement: Data route covers both report inputs
The system SHALL, with `data`, read the given exports through the CSV readers and the database readers of the flow and dependency tools, and compare the flow tickets, the dependency tickets and the links (counts of links on one side only). It SHALL NOT compare the reports' text in this mode, and SHALL print only the error type, never its message, for an unexpected error (exit code 2).

Source: tests/flow_compare/test_flow_compare.py (AvecBase); error output untested.

#### Scenario: Same export on both routes
- **WHEN** an export with typed and untyped links is imported, then compared with itself
- **THEN** the flow tickets, the dependency tickets and the links give no difference and the exit code is 0

### Requirement: History comparison by instant
The system SHALL compare history by instants (not text), tolerate different offsets and formats, flag a 30-minute shift as one difference, ignore keys outside the export, and flag a difference in which tickets have history.

Source: tests/flow_compare/test_flow_compare.py (test_historique_compare_les_instants_pas_les_textes, test_historique_ignore_les_cles_hors_export, AvecBase.test_historique); tests/flow_store/test_couverture_historique.py

#### Scenario: Same instant, other text
- **WHEN** the same instant is written with different offsets
- **THEN** it is not a difference

#### Scenario: Added transition
- **WHEN** the cache holds one more transition than the database
- **THEN** one difference is counted

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
