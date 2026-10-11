# jira-flow-reports Specification

## Purpose

Describes the flow report tool: it reads one or more API-export CSV files (or the database) and writes Markdown and JSON reports of throughput, lead time, work in progress, ageing, forecasts, arrivals, batch closures and time per segment, then compares successive reports of the same scope. Reports contain no ticket key and no title. Sources are the tests in `tests/flux_jira/`.

## Requirements

### Requirement: Subcommands and former names
The system SHALL offer the subcommands `statuses`, `compute`, `compare` and `config`. It SHALL refuse former French subcommand names with exit code 2 ("invalid choice"), and SHALL accept former option names with a warning that names the new option, producing the same report as the new names.

Source: tests/flux_jira/test_noms_anglais.py (AncienEtNouveau)

#### Scenario: Former options
- **WHEN** former names of the name, today, no-comparison, scope and weeks options are used
- **THEN** each produces a warning "renamed" naming the new option and the report equals the one produced with new names

#### Scenario: Former subcommands
- **WHEN** a former subcommand name is used
- **THEN** the exit code is 2

### Requirement: Input is the API export only
The system SHALL read only CSV files in the layout of the API export (English column headers, day/abbreviated-month/year hour:minute dates) and SHALL refuse a manual export with non-English headers, for both `statuses` and `compute`, with a message pointing to the API export tool and without a traceback. Rows with an unreadable creation date SHALL be counted and reported, naming the API export tool. A legacy date-format setting and French column-alias names in the settings SHALL be ignored with a warning, without changing the computation.

Source: tests/flux_jira/test_flux_jira.py (ExportDeLApiSeulement)

#### Scenario: Non-API export
- **WHEN** an export with French headers is given to `statuses` or `compute`
- **THEN** the exit code is non-zero and the message points to the API export subcommand

#### Scenario: Legacy settings
- **WHEN** the settings hold a legacy date format and French column aliases
- **THEN** warnings state they are ignored, and the report equals the one computed without them

### Requirement: Data source selection
The system SHALL read tickets from CSV files by default (no source, or `csv`), or from the local database when the source option is `--source db`, which is the target path for the flow report; with the database source it SHALL NOT read any CSV file and SHALL pass the settings to the database reader. An unknown source SHALL stop with a message naming the value and listing the allowed values ("csv, db"), in French or English. Files given together with `db` SHALL be refused rather than ignored, before any database read, with "no CSV file may be given" (French equivalent in French). A database error SHALL stop the run with the database-read message followed by the error detail; any other error SHALL NOT be masked by that message.

Source: tests/flux_jira/test_source.py; tools/flux_jira.py (lire_source, lire_tickets, depuis_la_base). End-to-end parity with a database: tests/flow_store/test_sources_scripts.py

#### Scenario: Default source
- **WHEN** no source is given
- **THEN** the CSV files are read

#### Scenario: Unknown source
- **WHEN** `--source ftp` is given
- **THEN** the run stops with a message naming "ftp" and the allowed values "csv, db"

#### Scenario: Files with database
- **WHEN** files are passed with the database source
- **THEN** the run stops with the "no CSV file may be given" message and the database is not read

#### Scenario: Unreachable database
- **WHEN** the database reader raises a database error
- **THEN** the run stops with the database-read message and the error detail; another kind of error is raised unchanged

### Requirement: Merging several exports
The system SHALL accept several export files and, when a key column exists, merge tickets by key with the last file winning, counting duplicates removed and mentioning the merge in the report; without a key column the files SHALL simply be concatenated.

Source: tests/flux_jira/test_flux_jira.py (MultiProjets.test_fusion_par_cle)

#### Scenario: Two files with shared tickets
- **WHEN** two exports share seven tickets
- **THEN** the JSON reports two files and seven duplicates removed, and the Markdown mentions the merge of two exports by key

### Requirement: Exclusions applied to every count
The system SHALL exclude tickets of portfolio-level types and of excluded projects from every count (throughput, lead time, work in progress, to-do, ages, teams, arrivals, forecasts), SHALL report what was excluded by type and by project in the report, and SHALL produce a report identical (apart from the exclusion note and merge info) to one computed on an export from which those tickets were already removed. A former setting name for portfolio types SHALL be accepted.

Source: tests/flux_jira/test_flux_jira.py (MultiProjets, ExclusionPartout), tests/flux_jira/test_noms_anglais.py

#### Scenario: Exclusion note
- **WHEN** epics and one project are excluded
- **THEN** the report's excluded section counts them by type and by project

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
The system SHALL read several team columns or several values in one cell (separator configurable), count tickets that have more than one distinct team and mention it ("current attribution"), while the attribution of a ticket to a team stays the first team column taken as a whole cell; the other columns attribute nothing. Without multi-team tickets the report SHALL be unchanged.

Source: tests/flux_jira/test_flux_jira.py (PlusieursEquipes)

#### Scenario: Multi-team count
- **WHEN** three tickets have a second team and one has two values in one cell
- **THEN** the total counts tickets with two distinct teams out of all tickets, and a team never appears from the second column only

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
The system SHALL, with the dormant-from-history option, derive dormant tickets from the history cache (or database), split work in progress into active, waiting and dormant (exclusive and exhaustive), split to-do into alive and dormant, and report the dormancy threshold in days, the source "history" and the number of tickets without history (not counted dormant). Little's law and the forecast SHALL then use the non-dormant WIP, with the total-WIP results given for comparison; with an explicit target both use that target. Per-team and per-state dormant counts SHALL sum to the totals. The console SHALL give counts and no keys. Without the option the report SHALL NOT change. A different cache path SHALL be accepted with the history option, a missing key column SHALL stop the run, and the removed dormant-file option SHALL be refused with a message naming the replacement.

Source: tests/flux_jira/test_flux_jira.py (DormantsHistorique, Dormants)

#### Scenario: Edge cases of dormancy
- **WHEN** one ticket has no transition and was created exactly the threshold number of days ago, another one day less, another is absent from the cache, another is finished
- **THEN** the first is dormant, the others are not, and the absent one is counted as without history

#### Scenario: Removed option
- **WHEN** the removed dormant-file option is used, in either language
- **THEN** the exit code is non-zero, the message says it no longer exists and names the replacement, and no report is written

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
The system SHALL, with the history option, compute from the cache time per state and per segment (segments and commitment point configurable): for tickets that left each segment, the days spent (a ticket's visits to the same segment cumulated) with median, 85th percentile and mean; the age of tickets currently in each segment (counting the initial state when no transition exists); delivery lead time from the commitment point and from creation, with the number of tickets without commitment; flow efficiency (active over total, with median and aggregated figure; not computed with a note when no waiting state is configured); coverage (tickets with history over total) with a warning when it is below a minimum; per-team results without ranking; states not assigned to any segment (known start and end states excluded by default); unreadable transition dates counted and warned. An unknown commitment point SHALL stop the run naming the setting; a missing key column SHALL stop with a message; a missing cache SHALL stop with a message naming the history collection command. Without the option the report SHALL contain none of these sections. The report SHALL hold no ticket key, and the fixed "how to read" section SHALL gain the corresponding definitions.

Source: tests/flux_jira/test_flux_jira.py (TempsParSegment); tests/history_jira/test_history_jira.py (FluxSurCacheReel)

#### Scenario: Hand-checked history
- **WHEN** a set of invented journeys is computed
- **THEN** the exits per segment, the age in segment, the delivery lead time, the aggregated efficiency and the coverage equal the hand-computed values

#### Scenario: Custom cache path
- **WHEN** the history option is given a path
- **THEN** that file is used

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
The system SHALL provide `config migrate` that rewrites the settings file with English names (keeping comments), keeps the old file beside it with a suffix, lists changes as "line: old -> new" using names only and never values, says nothing to migrate on a second run, supports `--dry-run` (writes nothing), stops with exit 1 without writing when two old names map to the same new name, and stops when the file does not exist. A report computed after migration SHALL equal the one computed before, without warnings. Both former and new names SHALL be accepted by `compute`, with a warning naming the new key for each former key.

Source: tests/flux_jira/test_noms_anglais.py (ConfigMigrate, GrandeMigration)

#### Scenario: Conflict
- **WHEN** two former keys map to one new key
- **THEN** exit code 1, the message names the lines and keys, no value appears, and nothing is written

#### Scenario: Dry run
- **WHEN** `--dry-run` is used
- **THEN** the changes that would be made are listed and the file is unchanged

### Requirement: Statuses listing
The system SHALL provide `statuses` that lists the columns found for each role, the number of tickets and the creation and resolution ranges, each state with its count and a tag (in progress, to do, done or unclassified, mixed, waiting), the excluded counts, the types with counts, and a warning when the resolution column is absent. The text SHALL name the new settings.

Source: tests/flux_jira/test_noms_anglais.py (test_statuses_et_compare_existent); tools/flux_jira.py (cmd_statuts)

#### Scenario: Listing
- **WHEN** `statuses` runs on an export
- **THEN** the output mentions the in-progress and to-do setting names and no former name

### Requirement: Message language
The system SHALL print messages and write reports in French by default and in English with `--language en`, with the same files and the same JSON data in both languages, refuse other languages with exit 2, accept the former option name with a warning, and produce English output matching the recorded reference without French leftovers or former setting names.

Source: tests/flux_jira/test_language.py

#### Scenario: English written report
- **WHEN** `--language en` is given
- **THEN** the written report is English and the JSON equals the French run's JSON

## Open questions

1. The precise sections and order of the written Markdown report (beyond those asserted) are not specified; is a full outline wanted?
