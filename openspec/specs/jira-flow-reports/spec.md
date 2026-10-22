# jira-flow-reports Specification

## Purpose

Describes the flow report tool: it reads one or more API-export CSV files (or the database) and writes Markdown and JSON reports of throughput, lead time, work in progress, ageing, forecasts, arrivals, batch closures and time per segment, then compares successive reports of the same scope. Reports contain no ticket key and no title. Sources are the tests in `tests/flux_jira/`.

## Requirements

### Requirement: Subcommands and former names
The system SHALL offer the subcommands `statuses`, `compute`, `compare`, `config`, `cycles` (reading the database only, jira-flow-cycles capability) and `epics` (reading the database only, jira-flow-epic-flow capability). It SHALL refuse former French subcommand names with exit code 2 ("invalid choice").

Source: tests/flux_jira/test_noms_anglais.py (AncienEtNouveau); tests/flux_jira/test_cycles_commande.py (Aide); tests/flux_jira/test_epics_commande.py (`epics`).

#### Scenario: Former subcommands
- **WHEN** a former subcommand name is used
- **THEN** the exit code is 2

#### Scenario: Cycles listed
- **WHEN** the help is printed
- **THEN** `cycles` is listed with the other subcommands

#### Scenario: Epics listed
- **WHEN** the help is printed
- **THEN** `epics` is listed with the other subcommands, and printing the help reads no setting and opens no connection

### Requirement: Former option and setting names refused
The system SHALL refuse former option names with exit code 2 and a message naming the current option, and SHALL refuse former setting names naming the current one; in both cases no report SHALL be written.

Source: tests/flux_jira/test_noms_anglais.py (AncienEtNouveau)

#### Scenario: Former options
- **WHEN** former names of the name, today, no-comparison, scope and weeks options are used
- **THEN** each run exits with code 2, says the option no longer exists and names the current one, and no report is written

#### Scenario: Former setting names
- **WHEN** the settings use a former name for the in-progress states
- **THEN** the run fails naming the current setting and writes no report, while the same settings under the new names run without any message

### Requirement: Legacy settings stop the report
The system SHALL stop the run when the settings hold a legacy date-format setting or a French column alias (jira-flow-config capability); it SHALL NOT ignore them with a warning.

Source: tests/flux_config/test_flux_config.py (test_un_flux_yaml_ancien_est_refuse_par_les_scripts)

#### Scenario: Legacy settings
- **WHEN** the settings hold a legacy date format
- **THEN** the run stops with a message that the setting no longer exists, without its value

### Requirement: Data source selection
The system SHALL read tickets only from the local database, under the read-only role, and SHALL pass the settings to the database reader. The retired option `--source`, whatever its value, SHALL stop the run with exit code 2 and the key phrase of design D6, and an export file given as argument SHALL stop it with exit code 2 and the key phrase of design D6, in French or English, before any database read. A database error SHALL stop the run with the database-read message followed by the error detail; any other error SHALL NOT be masked by that message.

Source: tests/flux_jira/test_lecteur_base.py (Lecture, Refus); tests/flow_store/test_erreurs_scripts.py (Erreurs); tools/flux_jira.py (verifier_usage_lecteur, lire_tickets, depuis_la_base)

#### Scenario: Default source
- **WHEN** `compute` runs with no option
- **THEN** the tickets are read from the database

#### Scenario: Unknown source
- **WHEN** `--source ftp` or `--source db` is given
- **THEN** the run stops with "--source is retired: the database is the only source" and exit code 2, and the database is not read

#### Scenario: Files with database
- **WHEN** an export file is given without `--source`
- **THEN** the run stops with "export files are no longer read: the database is the only source" and exit code 2, and the database is not read

#### Scenario: Unreachable database
- **WHEN** the database reader raises a database error
- **THEN** the run stops with the database-read message and the error detail; another kind of error is raised unchanged

### Requirement: Exclusions applied to every count
The system SHALL exclude tickets of portfolio-level types and of excluded projects from every count (throughput, lead time, work in progress, to-do, ages, teams, arrivals, forecasts), SHALL report what was excluded by type and by project in the report, and SHALL produce a report identical (apart from the exclusion note and merge info) to one computed on an export from which those tickets were already removed.

Source: tests/flux_jira/test_flux_jira.py (MultiProjets, ExclusionPartout)

#### Scenario: Exclusion note
- **WHEN** epics and one project are excluded
- **THEN** the report's excluded section counts them by type and by project

### Requirement: Former portfolio-types setting refused
The system SHALL refuse the former setting name for portfolio types, naming the current setting.

Source: tests/flux_jira/test_noms_anglais.py (GrandeMigration)

#### Scenario: Former portfolio-types name
- **WHEN** the settings use either former name of the portfolio-types setting
- **THEN** `compute` fails naming the current setting, and after `config migrate` the setting applies

### Requirement: State classification
The system SHALL classify open tickets as in progress or to do by the state-category column when it is present (the category decides, and the report states that classification is by state category), and by the lists in the settings otherwise or for tickets without a category. States that are neither SHALL be reported as unclassified.

Source: tests/flux_jira/test_flux_jira.py (MultiProjets.test_categorie_decide_en_cours_et_a_faire, test_sans_categorie_les_listes_de_flux_yaml_servent)

#### Scenario: Category present
- **WHEN** a state not listed in the settings has the in-progress category
- **THEN** it counts as work in progress

#### Scenario: Category absent
- **WHEN** the export has no category column
- **THEN** the lists of the settings decide and unlisted states are reported as unclassified

### Requirement: Scope filter
The system SHALL, with `--scope`, restrict the report to the listed projects (case- and space-insensitive, empty entries ignored) or to all projects with the word "all", produce for one project the same metrics as an export containing only that project, and state the scope, with tickets kept over tickets read, at the top of the report and on the console, including the number of requested projects without tickets. An empty scope, or one that matches no ticket, SHALL stop with a non-zero code. Without the option the report SHALL NOT change, even if the settings define a project scope used by another tool.

Source: tests/flux_jira/test_flux_jira.py (Perimetre)

#### Scenario: Two projects
- **WHEN** the scope lists two projects out of three
- **THEN** the metrics equal those of an export holding only those two, and the scope line gives retained over read

#### Scenario: Unknown project
- **WHEN** the scope matches no ticket
- **THEN** the exit code is non-zero and the message says no ticket of the requested projects exists

### Requirement: Period and metrics
The system SHALL analyse a configurable number of complete weeks ending with the last full week before today, trimming leading weeks that precede the first resolution in the export. It SHALL compute weekly throughput of delivered tickets (resolved tickets whose resolution is not on the excluded-resolutions list), lead time percentiles, work in progress, to-do count, age of work in progress (from start when available for all, otherwise from creation), ageing counts over thresholds, age per state, age of the to-do queue per state, per-team metrics when a team column exists, Little's law, and Monte Carlo forecasts of the weeks needed (percentiles) and, with a target date, of the items finishable. Resolved but undelivered tickets SHALL be counted separately by resolution, and the target number of items SHALL default to the current work in progress.

Source: tests/flux_jira/test_flux_jira.py (AncienFormat, Arrivees, EtatsAttente); tools/flux_jira.py (cmd_calcul) for the forecast options, not asserted by a test.

#### Scenario: Frozen reference
- **WHEN** a legacy-layout export (no key, no state category) is computed
- **THEN** the Markdown and JSON reports equal the frozen reference reports (apart from the glossary sentence about dormant tickets)

#### Scenario: Excluded resolutions
- **WHEN** tickets are closed as rejected
- **THEN** they are out of throughput and lead time and listed under "closed without delivery"

### Requirement: Arrivals and exits
The system SHALL report, per week, tickets created (including those later rejected) with the same types and exclusions as throughput, the exits, the weekly difference and the totals, and per team (alphabetical order) the arrivals, exits and difference. Sums over teams SHALL equal the global totals.

Source: tests/flux_jira/test_flux_jira.py (ArriveesEtSorties)

#### Scenario: Rejected ticket
- **WHEN** a ticket is created then rejected during the period
- **THEN** arrivals increase by one while throughput is unchanged

### Requirement: Note about many teams
The system SHALL add a note that teams are not comparable with each other (workflows, ticket sizes and types of work differ) in the team sections when more than ten teams are present, and SHALL NOT when there are ten or fewer.

Source: tests/flux_jira/test_flux_jira.py (MultiProjets.test_note_sur_les_equipes_au_dela_de_dix, ArriveesEtSorties)

#### Scenario: Eleven or more teams
- **WHEN** the export holds more than ten teams
- **THEN** the note appears in the throughput per team and arrivals sections

### Requirement: Tickets with several teams
The system SHALL read the teams of each ticket in their stored order, count tickets that have more than one distinct team and mention it ("current attribution"), while the attribution of a ticket to a team is its first team; the other teams attribute nothing. Without multi-team tickets the report SHALL be unchanged.

Source: tests/flux_jira/test_flux_jira.py (PlusieursEquipes, through the test loader of tests/flux_jira/chargeur_csv.py)

#### Scenario: Multi-team count
- **WHEN** three tickets have a second team and one has two teams from one cell of the source field
- **THEN** the total counts tickets with two distinct teams out of all tickets, and a team never appears from a second position only

#### Scenario: Separator in the first cell
- **WHEN** the first team cell of a ticket held two teams joined by the separator when it was read
- **THEN** the ticket is attributed to the first of them, and never to the whole cell

### Requirement: Waiting states
The system SHALL, when waiting states are configured (an entry matches a state that equals, starts with, or ends with it, case-insensitively), report active versus waiting work in progress with the waiting share and per-state counts, per team and per state, while the total work in progress is unchanged. Without the setting the sections SHALL be absent.

Source: tests/flux_jira/test_flux_jira.py (EtatsAttente)

#### Scenario: Waiting in the total
- **WHEN** waiting states are configured
- **THEN** total WIP is unchanged, active plus waiting equals WIP, and per-team waiting sums to the total waiting

#### Scenario: Exact state
- **WHEN** a configured waiting entry equals a to-do state
- **THEN** it does not enter WIP and is absent from the waiting list

### Requirement: Dormant tickets from history
The system SHALL, with the dormant-from-history option, derive dormant tickets from the history stored in the database, split work in progress into active, waiting and dormant (exclusive and exhaustive), split to-do into alive and dormant, and report the dormancy threshold in days, the source "history" and the number of tickets without history (not counted dormant). Little's law and the forecast SHALL then use the non-dormant WIP, with the total-WIP results given for comparison; with an explicit target both use that target. Per-team and per-state dormant counts SHALL sum to the totals. The console SHALL give counts and no keys. Without the option the report SHALL NOT change. A path given to the history option SHALL be refused with exit code 2 and the key phrase of design D6, and the removed dormant-file option SHALL be refused with a message naming the replacement.

Source: tests/flux_jira/test_flux_jira.py (DormantsHistorique, Dormants); tests/flux_jira/test_lecteur_base.py (Refus.test_chemin_donne_a_history_refuse, HistoriqueAbsent)

#### Scenario: Edge cases of dormancy
- **WHEN** one ticket has no transition and was created exactly the threshold number of days ago, another one day less, another has no history, another is finished
- **THEN** the first is dormant, the others are not, and the one without history is counted as without history

#### Scenario: Removed option
- **WHEN** the removed dormant-file option is used, in either language
- **THEN** the exit code is non-zero, the message says it no longer exists and names the replacement, and no report is written

#### Scenario: History path
- **WHEN** the history option is given a path
- **THEN** the run stops with "--history takes no file: the history is read from the database" and exit code 2

### Requirement: Batch closures
The system SHALL, when the export has a key column and a resolution time, report per project the delivered tickets resolved within the same minute in groups reaching a configurable threshold, restricted to configurable resolutions (an empty list or the word "all" meaning every delivered resolution), with groups, tickets, largest group, delivered total and share, sorted by tickets descending and with a total line. Groups SHALL NOT merge across projects. Nothing SHALL be removed from throughput. A message SHALL state when there is none. A threshold below two or an empty option SHALL stop the run naming the setting or option. An option SHALL override the setting without writing to the settings file. Without a key column or time the section and its glossary entry SHALL be absent. The report SHALL contain no ticket key.

Source: tests/flux_jira/test_fermetures_groupees.py

#### Scenario: Group below threshold
- **WHEN** a project closes fewer tickets than the threshold in one minute
- **THEN** the project is absent from the section

#### Scenario: Other resolution
- **WHEN** a group has another resolution than the tracked one
- **THEN** it is not counted as a batch but its tickets remain in the delivered total

#### Scenario: Truncated first week
- **WHEN** the export query filters on a resolution window and the period would start before that window
- **THEN** the arrivals section notes the truncated first week with the filter, the window start and the number of missing days, and the JSON holds the window; with no filter, or a period starting after the window, no note appears

### Requirement: Time per segment from history
The system SHALL, with the history option, compute from the history stored in the database time per state and per segment (segments and commitment point configurable): for tickets that left each segment, the days spent (a ticket's visits to the same segment cumulated) with median, 85th percentile and mean; the age of tickets currently in each segment (counting the initial state when no transition exists); delivery lead time from the commitment point and from creation, with the number of tickets without commitment; flow efficiency (active over total, with median and aggregated figure; not computed with a note when no waiting state is configured); coverage (tickets with history over total) with a warning when it is below a minimum; per-team results without ranking; states not assigned to any segment (known start and end states excluded by default); unreadable transition dates counted and warned. An unknown commitment point SHALL stop the run naming the setting; no stored history SHALL stop the run with exit code 1 and the key phrase of design D6. Without the option the report SHALL contain none of these sections. The report SHALL hold no ticket key, and the fixed "how to read" section SHALL gain the corresponding definitions.

Source: tests/flux_jira/test_flux_jira.py (TempsParSegment); tests/flux_jira/test_lecteur_base.py (HistoriqueAbsent.test_history_sans_historique_code_1_et_une_phrase)

#### Scenario: Hand-checked history
- **WHEN** a set of invented journeys is computed
- **THEN** the exits per segment, the age in segment, the delivery lead time, the aggregated efficiency and the coverage equal the hand-computed values

#### Scenario: Custom cache path
- **WHEN** the history option is given a path
- **THEN** the run stops with "--history takes no file: the history is read from the database" and exit code 2

#### Scenario: No history stored
- **WHEN** the history option is given and no transition is stored
- **THEN** the run stops with "no history in the database: run the history collection first" and exit code 1

### Requirement: Dashboard data
The system SHALL add, per team, arrivals per week; with the history option, a weekly cumulative flow (end-of-week counts to-do, per segment and delivered, per team summing to the global one, with delivered cumulative non-decreasing and the total never above the ticket count, plus the number of tickets without history); and, with the points option, a private file of ageing-WIP points (team, age, state, segment, age in segment, nature active or waiting) with no ticket key, written owner-only in an owner-only folder. Without the history option there SHALL be no cumulative flow or segments in points, and without the points option no points file.

Source: tests/flux_jira/test_flux_jira.py (DonneesDuTableau)

#### Scenario: Points file
- **WHEN** the points option is given
- **THEN** the file exists with owner-only permissions, contains no key, and the console reports the number of tickets in progress

### Requirement: Fixed reading guide
The system SHALL include in every report a fixed "how to read this report" section placed after the forecasts and before the limits, whose fixed text does not depend on the data, whose optional notions (waiting, dormant, batch closure, segments) appear only when their section does, and whose examples (age and lead time at the 85th percentile) are computed from the report's own figures.

Source: tests/flux_jira/test_flux_jira.py (CommentLire)

#### Scenario: Two datasets
- **WHEN** two reports are computed on different data
- **THEN** the fixed text before the examples is identical and the examples show each report's own numbers

### Requirement: Reports stored privately and without sensitive content
The system SHALL write the reports as Markdown and JSON into the reports folder of the working area named after the report name and day, with no ticket key, and SHALL create a default settings file with English setting names when none exists (no warning on the next run).

Source: tests/flux_jira/test_flux_jira.py, tests/flux_jira/test_noms_anglais.py (test_reglages_par_defaut_ecrits_avec_les_noms_anglais)

#### Scenario: Default settings file
- **WHEN** no settings file exists
- **THEN** one is created with English names and nothing is printed to the error stream

### Requirement: Evolution comparison between reports
The system SHALL, unless `--no-comparison` is given, compare the new report with the previous one of the same name, and provide a `compare` subcommand with `--before` and `--after` days (defaults: latest and the one before it), writing an evolution report (Markdown, plus JSON with signals, comparability notes and recent throughput) and printing it. It SHALL stop with messages when fewer than two reports exist, when a requested day has no report, or when the dates are not in increasing order. It SHALL flag in comparability notes any difference in types, scope, number of weeks, presence of the start column and appearing or disappearing states, SHALL report the scope difference only when scopes differ and not a mere headcount difference, SHALL give the same result whatever the ordering of lists in the older report, and SHALL, for a report of an older format missing keys, skip only the affected section (or team) with one line saying which keys are missing and a "partial comparison" line, without failing and also on the console.

Source: tests/flux_jira/test_flux_jira.py (Perimetre.test_comparaison_signale_un_perimetre_different_pas_un_effectif_different, OrdreDesListesDansLaSerie, AncienFormatDeRapport); tests/flux_jira/test_noms_anglais.py

#### Scenario: Missing throughput key
- **WHEN** the earlier report lacks the weekly throughput
- **THEN** the throughput section says it is not compared, the partial-comparison line names it, and the other sections are compared

#### Scenario: Different scope
- **WHEN** the two reports have different scopes
- **THEN** the comparability notes say "different scopes" and name both

### Requirement: Settings migration
The system SHALL provide `config migrate` that rewrites the settings file with English names (keeping comments), keeps the old file beside it with a suffix, lists changes as "line: old -> new" using names only and never values, says nothing to migrate on a second run, supports `--dry-run` (writes nothing), and stops when the file does not exist.

Source: tests/flux_jira/test_noms_anglais.py (ConfigMigrate)

#### Scenario: Dry run
- **WHEN** `--dry-run` is used
- **THEN** the changes that would be made are listed and the file is unchanged

### Requirement: Migration conflict stops config migrate
The system SHALL stop `config migrate` with exit 1, without writing, when two old names map to the same new name.

Source: tests/flux_jira/test_noms_anglais.py (GrandeMigration)

#### Scenario: Conflict
- **WHEN** two former keys map to one new key
- **THEN** exit code 1, the message names the lines and keys, no value appears, and nothing is written

### Requirement: Report after migration
The system SHALL compute, after migration, a report equal to the one computed with the new names, without any message. `compute` SHALL refuse a file with former names, naming the current key, and SHALL NOT accept it with a warning.

Source: tests/flux_jira/test_noms_anglais.py (ConfigMigrate, GrandeMigration)

#### Scenario: Migrated file
- **WHEN** a file with former names is refused by `compute`, then migrated
- **THEN** `compute` runs without any message and the report equals the one computed with the new names

### Requirement: Statuses listing
The system SHALL provide `statuses` that lists the columns found for each role, the number of tickets and the creation and resolution ranges, each state with its count and a tag (in progress, to do, done or unclassified, mixed, waiting), the excluded counts, the types with counts, and a warning when the resolution column is absent. The text SHALL name the new settings.

Source: tests/flux_jira/test_noms_anglais.py (test_statuses_et_compare_existent); tools/flux_jira.py (cmd_statuts)

#### Scenario: Listing
- **WHEN** `statuses` runs on an export
- **THEN** the output mentions the in-progress and to-do setting names and no former name

### Requirement: Message language
The system SHALL print messages and write reports in French by default and in English with `--language en`, with the same files and the same JSON data in both languages, refuse other languages with exit 2, refuse the former option name with exit 2 naming the current one, and produce English output matching the recorded reference without French leftovers or former setting names.

Source: tests/flux_jira/test_language.py

#### Scenario: English written report
- **WHEN** `--language en` is given
- **THEN** the written report is English and the JSON equals the French run's JSON

### Requirement: Aggregation by team, Mission Team or site
The system SHALL accept on `compute` the option `--by team|mission-team|site`, default `team`. With `mission-team` or `site`, it SHALL read the organisation referential, replace the per-team sections by per-group sections following the jira-flow-organisation capability, and write a report whose name carries the aggregation, on both data sources. Without the option, the report SHALL stay unchanged. A missing or invalid referential with a group aggregation SHALL stop with exit code 1, naming the referential and never a value.

Source: tests/flux_jira/test_regroupement.py

#### Scenario: Default
- **WHEN** `compute` runs without `--by`
- **THEN** the report is identical to the report of the previous version

#### Scenario: Referential missing
- **WHEN** `compute --by site` runs without a referential
- **THEN** the exit code is 1 and no report is written

### Requirement: Labels and versions absent from the flow report
The system SHALL NOT write a label or a version name in a flow report, an evolution report, an ageing-points file or the console of the flow report tool; cycles appear only by their neutral keys.

Source: tests/flux_jira/test_chaines_distinctives.py; tests/flux_jira/test_cycles_commande.py (SortiesSansValeurDistinctive)

#### Scenario: Distinctive values
- **WHEN** the data hold a distinctive string as declared label and as fix version
- **THEN** none appears in any output of `statuses`, `compute`, `compare` or `cycles`

### Requirement: Map exclusion setting not read by the flow report
The system SHALL NOT use the dependency map's own exclusion setting in the flow report: the report SHALL be identical with or without that setting, and the shared excluded-projects setting SHALL keep its effect on every count.

Source: tests/flux_jira/ (to be written, task 4.2)

#### Scenario: Map setting added
- **WHEN** the flow report is computed twice on the same export, once with the map's exclusion setting added to the settings
- **THEN** the Markdown and JSON reports are identical

#### Scenario: Shared setting kept
- **WHEN** the shared setting excludes a project and the map's setting excludes none
- **THEN** the tickets of that project stay out of every count of the flow report

### Requirement: Shared tickets by team
The system SHALL, when multi-team tickets exist and the aggregation is by team, add the section of design D10: per team, in name order, tickets attributed there and shared, and tickets carried there but attributed elsewhere, cells under five written "masqué" in French and "masked" in English (null in the JSON). It SHALL NOT order rows by count, name a pair of teams or a key, or change another section.

Source: tests/flux_jira/test_tickets_partages.py (SectionPartages)

#### Scenario: No multi-team ticket
- **WHEN** no ticket carries more than one team
- **THEN** the section is absent and the report equals the one of the previous version

#### Scenario: Small cell masked
- **WHEN** a team has twelve shared tickets attributed to it and two carried but attributed elsewhere
- **THEN** its row shows 12 and "masqué" ("masked" in English), and the JSON holds 12 and null

#### Scenario: Group aggregation
- **WHEN** `compute --by site` runs on an export with multi-team tickets
- **THEN** the section is absent

### Requirement: Reports grouped by team type mask single-team groups and rank no team
The system SHALL, in any report section grouped by team type (design, "Complement: team type column"), mask a count cell under the threshold as "<5", mask whole a type group of fewer than 2 teams with "masked: fewer than 2 teams", put a null type in "type not set", and show a team count only from 2 on. It SHALL NOT show a total that recomputes a masked group, a team line, a team label or a ranking, nor let a setting lower the minimum of 2. Untested until implemented.

Source: not built, deferred (idea in Kraken, author decision of 2026-10-21)

#### Scenario: Type held by one team
- **WHEN** a report grouped by type covers one verification team and three development teams
- **THEN** the verification group shows "masked: fewer than 2 teams" in every cell, and no total lets its figures be recomputed

#### Scenario: No team line
- **WHEN** a report grouped by type is written
- **THEN** it holds one line per type, no team label and no ordering of teams

### Requirement: Flow report refused inside a Claude Code session
The system SHALL refuse `statuses` and `compute` to start, with the exit code and the session key phrase of design D6, when the variable that Claude Code sets in its shells is present, before reading any setting (design D12). It SHALL NOT offer an option that bypasses that refusal. `compare` and `config` SHALL NOT be refused.
#### Scenario: Started from a session
- **WHEN** `compute` starts with the variable present
- **THEN** the output holds "Refused inside a Claude Code session", nothing is read and no report is written

#### Scenario: Comparison from a session
- **WHEN** `compare` starts with the variable present
- **THEN** it runs as usual

## Open questions

1. The precise sections and order of the written Markdown report (beyond those asserted) are not specified; is a full outline wanted?
