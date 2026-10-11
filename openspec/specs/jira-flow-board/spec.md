# jira-flow-board Specification

## Purpose

Describes the visual flow dashboard: a single self-contained HTML page generated from the flow and dependency reports already written, with a product view and one view per team, charts for throughput, cumulative flow, time per segment, ageing work in progress, work-in-progress breakdown, lead times, flow efficiency and a dependency map, available in English (default) and French, with an anonymous variant. Sources are the tests in `tests/flow_board/`.
## Requirements
### Requirement: Self-contained offline page
The system SHALL write a single HTML file that embeds the charting library, the data (as JSON) and the page code and style, SHALL contain no network address, external link, network call, image tag or external script source, SHALL be written readable only by its owner in an owner-only folder, and SHALL ship page code, style and template that themselves contain no network call. The embedded data SHALL contain no ticket key and no file name, and SHALL not be able to close its enclosing script element.

Source: tests/flow_board/test_flow_board.py (Fichier)

#### Scenario: Offline
- **WHEN** the page is generated
- **THEN** it contains the charting library inline, no http(s) address, link, import, external script source, image, fetch, request, beacon or websocket call

#### Scenario: Permissions
- **WHEN** the file is written
- **THEN** its mode is owner read/write and its folder owner-only

### Requirement: Output naming and options
The system SHALL accept `--language en|fr` (default English), `--anonymous`, `--output` and `--open`; the default file name SHALL carry the day, a French suffix for French and an anonymous suffix for the anonymous version. Former option names SHALL be accepted with a warning naming the new one. Settings for series SHALL be read under the English or the former names and give the same result. With `--open`, combined or not with the other options, the system SHALL open the page just written in the browser through its file address; without the option it SHALL NOT open anything, and when the generation fails (exit code 1) it SHALL NOT open anything either.

Source: tests/flow_board/test_flow_board.py (test_noms_de_fichier_par_langue_et_option, test_anciennes_options_acceptees_avec_avertissement, test_reglages_boards_sous_les_noms_anglais_et_anciens); tests/flow_board/test_ouverture.py

#### Scenario: Output option
- **WHEN** `--output` names a file
- **THEN** the page is written there

#### Scenario: Open the page
- **WHEN** the page is generated with `--open`
- **THEN** the browser is asked once to open the file address of the written page, and the exit code is 0

#### Scenario: No opening without the option or on failure
- **WHEN** the page is generated without `--open`, or the generation fails with `--open`
- **THEN** the browser is not called; the failure exits with code 1

#### Scenario: Former options
- **WHEN** the former language and anonymous options are used
- **THEN** warnings name the new options and the French anonymous file name is produced

### Requirement: Data model of the page
The system SHALL embed, per configured series, the team list in alphabetical order, views keyed with the product view first (empty key) then one per team alphabetically, and in each view weekly departures and arrivals (same length as the weeks), the cumulative flow, the segments (exits), the delivery lead time with commitment, the flow efficiency, the work-in-progress totals and breakdown, the history of reports, the baseline comparison, the ageing points (age, age in segment, nature among active/waiting/dormant, segment, status, team; no key), and the dependency data. Weeks SHALL be ISO dates. A baseline whose options differ SHALL be flagged with the differences (for example the dormant source). Dependencies SHALL list nodes and edges alphabetically with outside-export last, and loops; when the dependency report has no edges, they SHALL be rebuilt from its matrices. Pure helpers SHALL be consistent (percentile lookup, work-in-progress breakdown from either dormant or waiting data, team sort with special labels last, safe JSON that cannot close the script).

Source: tests/flow_board/test_flow_board.py (Donnees)

#### Scenario: Views order
- **WHEN** the data are built for a series with two teams
- **THEN** the views are the product view, then the two teams in alphabetical order

#### Scenario: Baseline
- **WHEN** the baseline report was computed without the dormant-from-history option
- **THEN** the page data lists "dormant source" as a difference

### Requirement: Series selection from reports
The system SHALL find the reports of each configured series by exact name prefix (a series whose name merely begins with another's name SHALL NOT be confused with it), ignore unreadable report files, tolerate reports from an older format (missing cumulative flow, segments, arrivals, breakdown, dormant data, or missing dependency report) by leaving the corresponding data empty and showing "missing" notices on the page, and, when no series has reports, produce a valid empty page with an "empty page" notice. A recent-series report with no matching configuration SHALL be ignored.

Source: tests/flow_board/test_flow_board.py (Robustesse)

#### Scenario: Unreadable report
- **WHEN** the report JSON is broken
- **THEN** the page has no series and no error

#### Scenario: Old format
- **WHEN** newer keys are missing from the reports
- **THEN** the data for cumulative flow, segments and arrivals is empty, and the page shows the cumulative-flow and map missing notices

### Requirement: English by default, French on request
The system SHALL produce a page with no French text in English mode (data texts, glossary, page skeleton, rendered text and chart strings) and a French page with `--language fr`, with the same set of text keys in both languages, English flow vocabulary matching the glossary (throughput, arrivals, departures, lead time, delivery lead time, WIP, ageing WIP, cumulative flow diagram, flow efficiency, segment, commitment point, Monte Carlo forecast), Jira statuses and unknown segment names kept unchanged, English date and decimal formats (day unit and decimal point) and French ones (comma) otherwise, and special team labels translated ("no team", "outside export").

Source: tests/flow_board/test_flow_board.py (Langues, test_equipes_speciales_traduites)

#### Scenario: English page
- **WHEN** the default page is generated
- **THEN** the page language is English and no French word appears in the page text

#### Scenario: Unknown segment
- **WHEN** a segment has no label
- **THEN** its raw name is shown

### Requirement: Page behavior in a browser
The system SHALL, when the page script runs, build all charts for the product view, each team, "all teams", ageing by segment, ageing by status, printing and after printing without error, show a team selector, show rendered text with no ticket key, and render the dashboard in light and dark themes. Every chart SHALL be drawn by the real charting library without error when available. Style SHALL include print rules (avoid breaking inside blocks, exact colors) and a dark color scheme.

Source: tests/flow_board/test_flow_board.py (JavaScript, RenduReel, test_impression_et_themes_dans_le_css)

#### Scenario: Every selection
- **WHEN** the page is driven through each team and each ageing mode
- **THEN** no error is raised and the charts of the selection are built each time

#### Scenario: French page rendered
- **WHEN** the French page is driven
- **THEN** it shows the "how to read" and cumulative flow titles

### Requirement: Accessibility of charts
The system SHALL never rely on color alone: charts other than the map SHALL enable pattern decals, the ageing chart SHALL use distinct symbols per nature, the flow chart SHALL use distinct symbols and dash styles, and every dependency node SHALL carry a label. Dependency map nodes SHALL be listed alphabetically (those starting with a parenthesis last) without ranking.

Source: tests/flow_board/test_flow_board.py (test_la_couleur_ne_porte_jamais_seule_l_information, test_graphe_noeuds_alphabetiques_et_sans_classement)

#### Scenario: Symbols
- **WHEN** the ageing chart options are read
- **THEN** three distinct symbols are used for active, waiting and dormant

### Requirement: Anonymous version
The system SHALL, with `--anonymous`, replace team, project and series names with neutral labels ("Team X", "Project X", "Series N" in English; French equivalents) in the data, the page and the file name, so that no real name, project key, or special label from the source appears anywhere in the file or in the rendered page, and SHALL keep the mapping stable across generations (the same name keeps its letter whatever the random seed; a new name receives the first free letter; first-time letters are drawn at random). The mapping SHALL be stored in an owner-only file outside version control; an unreadable mapping SHALL stop with exit 1 naming the file, leaving it untouched. Labels beyond twenty-six SHALL continue in bijective base-26 letters. The non-anonymous version SHALL keep real names and write no mapping. The anonymous page SHALL say it is the anonymous version.

Source: tests/flow_board/test_flow_board.py (Anonyme, AnonymeJavaScript)

#### Scenario: No real name
- **WHEN** the anonymous page is generated and driven
- **THEN** none of the real team, project, series names nor project key appears in the file, the file name or the rendered text

#### Scenario: Stable letters
- **WHEN** the anonymous page is generated twice with different random seeds
- **THEN** team labels and series name are the same and the mapping file is unchanged

#### Scenario: New team
- **WHEN** a third team appears
- **THEN** existing letters do not change and the new team gets the first free letter

#### Scenario: Labels beyond Z
- **WHEN** labels for index 26, 27 and 702 are produced
- **THEN** they are AA, AB and AAA

### Requirement: Database comparison series ignored
The system SHALL ignore every series whose name ends with the database suffix of the monthly run (design D6), whether or not series are configured, so that no report of such a series appears in the page data, the page or the file name. It SHALL NOT ignore a series whose name merely contains the suffix elsewhere. Untested until implemented.

#### Scenario: Comparison series present
- **WHEN** the reports folder holds the reports of a series and of the same series with the database suffix
- **THEN** the page data holds only the first series

#### Scenario: Suffix inside a name
- **WHEN** a series name contains the suffix text without ending with it
- **THEN** the series is shown

## Open questions

1. The list of charts and their precise content (axes, series) beyond what the tests assert is not specified; confirm if a chart-by-chart description is wanted.
