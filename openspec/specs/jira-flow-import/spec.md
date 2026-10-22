# jira-flow-import Specification

## Purpose

Describes the tool that reads API-export CSV files and imports them incrementally into the `flow` schema of the local database (tickets, teams, links, status transitions). The import never prints a ticket key, a team name or a field value. Sources are the tests in `tests/flow_import/` (database tests use a disposable database and are skipped without it).

## Requirements

### Requirement: Incremental ticket upsert
The system SHALL insert the tickets whose latest snapshot has no live row, update a ticket only when a field of its latest snapshot differs from its live row (a difference in the updated instant alone counts), and leave unchanged tickets alone. Tickets without a snapshot in the latest export run SHALL be kept, and marked out of the export only under the requirement "Out-of-export mark". The console SHALL report counts only: read, inserted, updated, unchanged, teams created, links added, links removed, and the out-of-export line of design D19.

Source: tests/flow_import/test_derivation.py (Derivation); tests/flow_import/test_derivation_base.py (test_un_passage_est_applique_puis_un_second_import_ne_trouve_rien, test_un_champ_modifie_dans_le_dernier_passage_est_mis_a_jour, test_equipes_et_liens_comptes)

#### Scenario: Reimport
- **WHEN** the import runs twice with no export run in between
- **THEN** the second run changes nothing and prints "raw layer: no new run to apply"

#### Scenario: Older export
- **WHEN** the last export run met a ticket whose updated instant is older than that of its latest snapshot
- **THEN** the export recorded no new snapshot for it (jira-flow-raw-layer), and the import keeps the live row unchanged

#### Scenario: Two files
- **WHEN** two export runs were recorded since the last import, and the second changed the status of a stored ticket
- **THEN** that ticket is updated to its latest snapshot, counted once as updated, and every other ticket counts as unchanged

### Requirement: Teams per ticket
The system SHALL create teams on the fly, attribute each ticket to the first team (or none when empty), and store all distinct teams with their positions, writing only the difference when a ticket's teams change and keeping what is unchanged.

Source: tests/flow_import/test_import.py (test_multi_equipes_sans_equipe)

#### Scenario: Team change
- **WHEN** one ticket's teams change from two to one
- **THEN** only that ticket's team rows change and the others are kept

### Requirement: Links without duplicates
The system SHALL add only new links and remove links that disappeared from the latest snapshot, never duplicate a link on a second import, and keep the existing links of a ticket when its latest snapshot does not track links.

Source: tests/flow_import/test_reconstruction.py (test_liens_compares_seulement_quand_ils_sont_suivis, test_liens_non_suivis_gardent_les_derniers_liens); tests/flow_import/test_derivation_base.py (test_equipes_et_liens_comptes)

#### Scenario: Link vanished
- **WHEN** a link has disappeared and another appeared
- **THEN** one is removed and one is added in the counts

### Requirement: Single transaction and failure behavior
The system SHALL perform the import in one transaction that is rolled back on any error, reduce a database error to the name of its type, never print keys or team names in errors, and, when the database is unreachable, print the database connection error with exit code 1.

Source: tests/flow_import/test_import.py (Refus, test_erreur_en_cours_d_import_annule_tout)

#### Scenario: Mid-import failure
- **WHEN** an unexpected error happens after tickets were written
- **THEN** exit code 1, the error type name is printed, no key or team name appears, and no ticket or team remains

### Requirement: Dry run and output hygiene
The system SHALL, with `--dry-run`, compute the same counts in the database and roll back, writing nothing, and SHALL never print a ticket key, team name or field value in any mode or language. English output SHALL be available with `--language en`.

Source: tests/flow_import/test_derivation.py (test_essai_a_blanc_annule_et_ne_dit_pas_rien_quand_il_y_a_une_difference, test_les_sorties_ne_portent_ni_cle_ni_equipe_ni_valeur); tests/flow_import/test_derivation_base.py (test_essai_a_blanc_n_ecrit_rien)

#### Scenario: Dry run counts
- **WHEN** an import runs with `--dry-run` and then for real
- **THEN** the counts lines are identical and the derived tables are unchanged after the first

#### Scenario: English
- **WHEN** `--language en` is given
- **THEN** the output includes the "Tickets read" and "Teams created" lines and no transitions line

### Requirement: Out-of-export mark
The system SHALL, with the `--mark-absent` option, set the out-of-export instant (the import instant) on every stored ticket absent from the sightings of the last export run that does not already carry it, and SHALL clear the instant of every ticket sighted in that run, with or without the option. It SHALL report the marked and returned counts with the key phrase of design D19 of the GDPR alignment. It SHALL NOT delete a marked ticket, SHALL NOT move the instant of a ticket already marked, and SHALL NOT print a key.

Source: tests/flow_import/test_derivation.py (Derivation); tests/flow_import/test_derivation_base.py (DerivationEnBase)

#### Scenario: Ticket leaves the export
- **WHEN** a stored ticket is absent from the sightings of the last export run, a complete set, and the option is given
- **THEN** it carries the import instant as out-of-export instant, and the console prints "Tickets out of the export: 1 marked, 0 back"

#### Scenario: Ticket comes back
- **WHEN** a marked ticket is sighted in a later run, even without the option
- **THEN** its mark is cleared and counted as back

#### Scenario: Without the option
- **WHEN** an import runs without the option and a stored ticket is not sighted
- **THEN** no mark is set

### Requirement: Mark only with a complete export set
The system SHALL accept `--mark-absent` only when the last export run searched every named export query of the settings in one run (design D4, confirmed by the author on 2026-10-18; an export with `--query` records a run that is not a complete set). When the last export run is a `--query` run, it SHALL stop with exit code 1, writing nothing, and print the incomplete-set key phrase of design D19 of the GDPR alignment followed by the partial-run phrase of design D4, which tells to run a complete export first. When the raw layer holds no export run, it SHALL stop the same way with the incomplete-set phrase alone. It SHALL NOT combine several `--query` runs into a complete set, look back to an earlier complete run, or name a query in the refusal.

Source: tests/flow_import/test_derivation.py (test_jeu_incomplet_refuse_avant_toute_ecriture, test_aucun_passage_avec_l_option_refuse_comme_un_jeu_incomplet; the partial-run phrase by amendment task 14.3); tests/flow_import/test_derivation_base.py (test_jeu_incomplet_refuse_sans_rien_ecrire)

#### Scenario: One file missing
- **WHEN** two named queries are configured, the last export run searched only one (`--query`), and the option is given
- **THEN** the output holds "incomplete export set: --mark-absent refused" then "last export run limited to one query (--query): run a complete export first, without --query", nothing is written, and the exit code is 1

#### Scenario: Partial run after a complete one
- **WHEN** a complete export run is followed by a `--query` run, and the option is given
- **THEN** the import is refused with the same two lines: the earlier complete run is not used

#### Scenario: Files of two days
- **WHEN** each query was searched by a separate `--query` run, on two different days, and the option is given
- **THEN** the import is refused with the same two lines

#### Scenario: No export run
- **WHEN** the raw layer holds no export run and the option is given
- **THEN** the output holds "incomplete export set: --mark-absent refused" without the partial-run line, nothing is written, and the exit code is 1

#### Scenario: French refusal
- **WHEN** the last export run is a `--query` run and the import runs in French with the option
- **THEN** the output holds "dernier passage d'export limité à une requête (--query) : lancez d'abord un passage complet de l'export, sans --query"

### Requirement: Tickets past retention not imported
The system SHALL skip the snapshots of tickets resolved longer ago than the retention period, count them with the key phrase of design D19, and SHALL NOT insert or update them.

Source: tests/flow_import/test_derivation.py (test_ticket_resolu_au_dela_de_la_conservation_ignore_et_compte); tests/flow_import/test_derivation_base.py (test_ticket_resolu_au_dela_de_la_conservation_ignore_et_compte)

#### Scenario: Old row
- **WHEN** the latest snapshot of a ticket is resolved before the retention period
- **THEN** the ticket is not inserted or updated by the import and the console prints "tickets past retention, skipped: 1"

### Requirement: Mark refused on an empty export or too many absent tickets
The system SHALL refuse `--mark-absent` with exit code 1, writing nothing, when the last export run holds no sighting or when the tickets to mark exceed the share of stored tickets set by `--max-absent-percent` (which has a default); it SHALL NOT mark part of them. An invalid percentage SHALL be refused with exit code 2 before any connection.

Source: tests/flow_import/test_derivation.py (test_export_vide_refuse, test_trop_d_absents_refuse_sans_rien_marquer, test_pourcentage_invalide_refuse_avant_toute_connexion); tests/flow_import/test_derivation_base.py

#### Scenario: Empty export
- **WHEN** the last export run is a complete set with no sighting and the option is given
- **THEN** the output holds "empty export: --mark-absent refused", nothing is written, and the exit code is 1

#### Scenario: Too many absent
- **WHEN** two of four stored tickets are not sighted and the threshold given with the option is below that share
- **THEN** the output says too many tickets are absent, no ticket is marked, and the exit code is 1

### Requirement: Import derives from the raw layer without files
The system SHALL, under the import role, in one transaction and with no "applied" state (design D4), bring tickets, their teams and links to each ticket's latest snapshot, and replay the out-of-export marks from the last export run. When nothing changes it SHALL print the no-new-run phrase of design D6 (exit 0). It SHALL refuse an export file and `--history` before any connection (exit 2, phrases of design D6), and SHALL NOT write transitions, history flags or periods.

#### Scenario: One new run
- **WHEN** the export recorded one run and the import runs
- **THEN** the derived tables reflect that run's snapshots, and a second import prints "raw layer: no new run to apply" with exit code 0

#### Scenario: Transitions untouched
- **WHEN** the import runs on a database holding transitions, history flags and periods
- **THEN** none of them is changed

#### Scenario: Export file given
- **WHEN** the import is given an export file
- **THEN** the output holds "export files are no longer read: the import derives from the raw layer", the exit code is 2, and no connection is opened

#### Scenario: History option
- **WHEN** the import is given `--history`
- **THEN** the output holds "--history is retired: the history collection writes the transitions" and the exit code is 2

### Requirement: Gone mark cleared when the export sights the ticket again
The system SHALL, in the import transaction, with or without `--mark-absent`, reset to 0 the not-found counter and clear the gone instant of every ticket marked gone that the last export run sights, and print at every run the count with the key phrase of design D15, the dry run writing nothing. It SHALL NOT change the counter of a ticket not marked gone, delete a ticket, change its transitions or periods, or print a key. Untested until implemented.

#### Scenario: Gone ticket sighted
- **WHEN** a ticket marked gone with a counter of 3 is sighted in the last export run, and the import runs without `--mark-absent`
- **THEN** its counter is 0, it has no gone instant, its transitions are unchanged, and the output holds "tickets marked gone, sighted again by the export: 1"

#### Scenario: Ticket not gone
- **WHEN** a ticket with a counter of 2 and no gone instant is sighted in the last export run
- **THEN** its counter stays 2

#### Scenario: Gone ticket not sighted
- **WHEN** a ticket marked gone is absent from the last export run
- **THEN** its counter and gone instant are unchanged

#### Scenario: Dry run
- **WHEN** the import runs with `--dry-run` and a sighted ticket is marked gone
- **THEN** the output holds the same count line and the ticket keeps its mark

#### Scenario: French
- **WHEN** the import runs in French and one gone ticket is sighted
- **THEN** the output holds "tickets marqués disparus, revus par l'export : 1"

## Open questions

1. The write role used by the import and the rule that only the user runs it are access-control facts documented in code comments; confirm whether to specify them here.
