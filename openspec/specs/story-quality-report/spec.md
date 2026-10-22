# story-quality-report Specification

## Purpose
The story quality report, built from the aggregated views only: one section per team, never compared, with its probable causes in the chain, a product-chain section with no team named, small cells masked, a legend that states the denominator and the masking, and the JSON report data contract. Created by the change story-quality-audit (feature R-94).

## Requirements

### Requirement: The report reads the aggregated views only
The system SHALL provide a `report --name <series>` subcommand of the story quality tool. It SHALL connect under the quality views role, read only the three quality views, and, without `--json`, write one Markdown report, named after the series and the day, in the flow reports folder. It SHALL NOT read a table of the `quality` schema, the coaching feedback, a sample verdict or the text. Because it reads views only, it SHALL be allowed to the session. Untested until implemented.

#### Scenario: Tables unreachable
- **WHEN** the report tries to read the contents table under its role
- **THEN** the database refuses for insufficient privilege

#### Scenario: Report written
- **WHEN** the views hold results for two teams
- **THEN** the report is written in the flow reports folder and the output holds "story quality report written"

### Requirement: Each team is presented in its own section
The system SHALL write one section per team, in name order. Each section SHALL give, per item kind, that team's share of items meeting each criterion with its denominator, and its coverage (items collected, items audited at the current pair of versions, items with no acceptance-criteria text). Under the title, the report SHALL write the team-results notice of design D14. Untested until implemented.

#### Scenario: Order and notice
- **WHEN** the report is written for three teams
- **THEN** it has three team sections in name order, and the notice "Team results: never a person's evaluation, never a ranking" follows the title

### Requirement: The report states the grid versions and the overlay's effect
The system SHALL write, after the legend that follows the notice, the grid-versions key phrase of design D14 with the core and overlay versions, or the no-overlay form. When the overlay disables core criteria, it SHALL list their codes with the disabled-criteria key phrase, without the reasons. Every overlay criterion SHALL carry the organisation-rule mark. The report SHALL NOT write the overlay's identifier. Untested until implemented.

#### Scenario: Overlay present
- **WHEN** the views hold verdicts at core version 2 and overlay version 3, with one core criterion disabled and one criterion added
- **THEN** the report holds "Grid: core 2, organisation overlay 3", the disabled code after "Core criteria disabled by the organisation rule:", no disabling reason, and the added criterion marked "organisation rule"

#### Scenario: No overlay
- **WHEN** the verdicts carry no overlay version
- **THEN** the report holds "Grid: core" with the version and "no organisation overlay"

### Requirement: An invalid or refused overlay stops the report
The system SHALL read the organisation overlay for the report through the same reader and checks as `grid`. An invalid or refused overlay SHALL stop `report`, with or without `--json`, with exit code 3 and the overlay phrase of design D14, before any view is read and with no file written. Untested until implemented.

#### Scenario: Overlay refused
- **WHEN** the overlay file holds a fake sensitive name
- **THEN** `report` exits with code 3, its error output holds "organisation overlay refused" without the name, no view is read and no file is written

### Requirement: The report never compares teams
The system SHALL NOT write a table, a line or a chart holding figures of two teams. It SHALL NOT give a composite score, a total per team, a ranking, an order by result, a count of teams, a figure across teams other than the product-chain section's product counts, or any figure per person or per PO. The order of the sections SHALL NOT depend on the results. Untested until implemented.

#### Scenario: No-comparison guard
- **WHEN** the report is written for three teams with very different results
- **THEN** no table or line holds figures of more than one team, no line sums several criteria, and the sections keep the name order

#### Scenario: Results swapped
- **WHEN** the results of two teams are swapped in the fixture
- **THEN** the section order is unchanged

### Requirement: Each team section ends with its probable causes in the chain
The system SHALL end each team's section with the probable-causes sub-section of design D18: its heading and notice, then one line per recurrent defect of that team, giving the criterion's label, its origin mark, the share not met with its denominator and its link label. A defect is recurrent when its share not met reaches the configured threshold. Untested until implemented.

#### Scenario: Recurrent defect
- **WHEN** a team has twelve audited stories, nine of which do not meet a criterion linked to the Definition of Ready, and the threshold is below that share
- **THEN** the team's sub-section "Probable causes in the chain" holds a line for that criterion with "9/12" and "Definition of Ready"

#### Scenario: No recurrent defect
- **WHEN** no criterion of a team reaches the threshold
- **THEN** its sub-section holds "No recurrent defect at the current grid"

### Requirement: Probable causes stay aggregated, per team and uncompared
The system SHALL order the lines of a team's probable-causes sub-section by link, then by criterion code, never by result. It SHALL NOT treat a masked cell as recurrent, put another team's figure or name in a team's sub-section, count the teams sharing a defect, or name a person. Untested until implemented.

#### Scenario: Masked cell
- **WHEN** a team has three audited stories, all not meeting a criterion
- **THEN** no probable-cause line is written for that criterion and its cells read "<5"

#### Scenario: Same defect in two teams
- **WHEN** two teams share a recurrent defect
- **THEN** each team's sub-section holds its own line, and no line or table mentions both teams or a count of teams

### Requirement: A product-chain section lists the product's recurrent defects
The system SHALL write, after the last team section, the product-chain section of design D18: its heading and notice, then one line per recurrent defect of the product, all teams taken together, from the product view only, giving the criterion's label, its origin mark, the product share not met with its denominator and its link label. Lines SHALL be ordered by link, then code. Untested until implemented.

#### Scenario: Product defect
- **WHEN** the product view shows, for a criterion linked to Refinement, twenty audited stories of which fifteen do not meet it, and the threshold is below that share
- **THEN** the section "Product chain" follows the last team section, starts with its notice, and holds a line for that criterion with "15/20" and "Refinement"

#### Scenario: No product defect
- **WHEN** no criterion of the product view reaches the threshold
- **THEN** the product-chain section holds "No recurrent defect at the current grid"

#### Scenario: French heading
- **WHEN** the report is written in French
- **THEN** the section is headed "Chaîne du produit"

### Requirement: A product row masked by the product view writes no product line
The system SHALL NOT write the product line of a criterion whose product row the product view masks by the secondary masking of design D18, and SHALL write no figure or estimate in its place. The report SHALL read that masking from the product view and SHALL NOT recompute it from the per-team view. Untested until implemented.

#### Scenario: Product row masked by the view
- **WHEN** the product view returns a criterion's row with its five counts masked, because exactly one team cell of a visible column is masked in the per-team view
- **THEN** no product line is written for that criterion, and no figure is estimated

#### Scenario: Product row shown by the view
- **WHEN** the product view shows a recurrent defect for a criterion, even though the per-team view masks the cell of one team for it
- **THEN** the product line for that criterion is written as the view gives it, with no masking recomputed by the report

### Requirement: The product-chain section names no team and holds no per-team figure
The system SHALL NOT write in the product-chain section a team name, a figure of one team, a list or count of the teams sharing a defect, or a person. It SHALL NOT compute product figures by summing team cells, and SHALL NOT treat a masked product cell (under five) as recurrent or estimate it. Untested until implemented.

#### Scenario: No team in the section
- **WHEN** three teams with distinctive names have recurrent defects that make a product defect
- **THEN** the product-chain section holds none of the team names, no per-team share and no count of teams

#### Scenario: Masked product cell
- **WHEN** the product view masks a criterion's cells because fewer than five items were audited for it
- **THEN** no product line is written for that criterion, and no figure is estimated

#### Scenario: Item with two teams
- **WHEN** an item belongs to two teams
- **THEN** its verdicts count once in the product line's denominator, as in the product view

### Requirement: Single-PO teams are flagged without person data
The system SHALL write the single-PO key phrase of design D14 at the top of the section of each team whose attributes carry the single-PO flag. The flag SHALL change no figure and mask nothing. The report SHALL NOT write a name, an account or any other data about the PO. Untested until implemented.

#### Scenario: Flagged team
- **WHEN** one of two teams carries the single-PO flag
- **THEN** only that team's section starts with "Single-PO team: these results are those of one person's work; never use them to evaluate that person", and its figures equal those computed without the flag

### Requirement: Small cells are masked and nothing identifying is written
The system SHALL write "<5" for every cell the views mask, and SHALL NOT estimate a masked value. It SHALL NOT write a ticket key, a title, a story text, a person's name or a value of the coaching feedback. It SHALL write in French by default and in English with `--language en`. Untested until implemented.

#### Scenario: Small team
- **WHEN** a team has three audited stories
- **THEN** its cells read "<5" and no share is computed from them

#### Scenario: Distinctive strings absent
- **WHEN** the fixtures hold a distinctive string in every key, title, text and coaching feedback
- **THEN** none of them appears in the report or the output

### Requirement: The report's legend states the denominator and the masking
The system SHALL write, under the notice, the legend of design D14: a share is read over all audited items, the not-applicable ones included, and a masked cell is under the threshold or masked so that a count under five cannot be recovered by difference. Untested until implemented.

#### Scenario: Legend
- **WHEN** the report is written in English
- **THEN** the line after the notice starts with "Reading: a share is read over all audited items, including those for which the criterion does not apply."

### Requirement: The report's figures come from one service function
The system SHALL compute every share, recurrent defect and order of the story quality report in one service function (design D15), from the three quality views and the threshold, taking the masking from the views without recomputing it. The Markdown and the JSON SHALL only format its result. The function SHALL NOT read a `quality` table, the coaching feedback or a sample verdict, nor rank, score or total teams. Untested until implemented.

#### Scenario: Order independent of the rows and of the results
- **WHEN** the view rows are given in reverse order, or the results of two teams are swapped
- **THEN** the service result keeps the teams in name order and the lines in link then code order

#### Scenario: Formatting computes nothing
- **WHEN** the Markdown report and the JSON output are produced from the same service result
- **THEN** they hold the same figures, the same masked cells and the same order

### Requirement: A share is read over every audited item and a masked part masks it
The system SHALL take as the denominator of a share every audited item at the current pair of versions, those with the not-applicable verdict included, for a team as for the product (design D15, M4 revised to (b)). A share whose numerator or denominator is masked SHALL be a masked cell, never a number, and SHALL NOT be estimated; a masked not-applicable count SHALL NOT mask the share. Untested until implemented.

#### Scenario: Denominator with not-applicable items
- **WHEN** a team has twelve audited stories for a criterion, two of them not applicable and seven not met
- **THEN** the service result gives that criterion a share not met of 7 over 12

#### Scenario: Masked not-applicable count
- **WHEN** a team has twelve audited epics for a criterion, seven of them met, and the per-team view masks the other three counts (five items in all)
- **THEN** the service result gives a share met of 7 over 12, and a masked share not met

#### Scenario: Masked share
- **WHEN** a team's met count for a criterion is masked in the per-team view
- **THEN** the service result gives the masked-cell object for that share, and neither the Markdown nor the JSON shows a number for it

### Requirement: The report data contract is printed as JSON
The system SHALL print, with `report --name <series> --json`, the report data contract of design D15 as one JSON document on stdout: grid versions and disabled codes, the notice, one entry per team in name order and the product chain without team field. A masked cell SHALL be the object with a masked mark and the effective threshold, never a number, null alone or the "<5" text. It SHALL write no file, print nothing else on stdout and keep the exit codes of design D14. Untested until implemented.

#### Scenario: JSON document
- **WHEN** `report --name pilot --json` runs on views holding results for two teams
- **THEN** stdout parses as one JSON document whose teams come in name order, no report file is written, and "story quality report written" is not printed

#### Scenario: Masked cell object
- **WHEN** a team has three audited stories
- **THEN** its counts and shares in the JSON are masked-cell objects with the effective threshold, and no number is given for them

### Requirement: The report data contract has a closed key set
The system SHALL NOT put in the report data contract a key outside design D15: no rank, score, composite, total per team, order by result, count of teams, ticket key, title, story text, person, coaching value, sample verdict, overlay identifier or disabling reason. Untested until implemented.

#### Scenario: Closed key set
- **WHEN** the JSON document is checked against the contract
- **THEN** no key outside the contract appears, the product chain has no team field, and no distinctive string of the fixture's keys, texts or coaching feedback appears
