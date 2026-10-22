# jira-flow-organisation Specification

## Purpose
Describes the organisation referential kept in the flow folder outside Git (sites, departments, Mission Teams, teams, headcounts, Jira team identifiers), its strict reading, the export controls built on it, and the reports by Mission Team or by site. Sources are `tests/flow_organisation/test_flow_organisation.py`, `tests/flux_jira/test_regroupement.py`, `tests/dependencies_jira/test_par_groupe.py` and `tests/export_jira_api/test_referentiel_et_etiquettes.py`.

## Requirements

### Requirement: Organisation referential read strictly
The system SHALL read the organisation referential of the flow folder, outside Git, with the strict loader. Its structure is: a source date; sites; departments, each with a name, a site, a headcount and either Mission Teams (each with a name, an optional Discovery Workflow pilot flag and its teams) or teams directly; teams, each with a name, a headcount, an optional site and a list of Jira team identifiers; cross-cutting teams. The system SHALL refuse, with exit code 1 naming the key path and line and never a value: an unknown key, a team referenced by a Mission Team but not described, a team in two Mission Teams, and a Jira team identifier listed under two teams. The referential SHALL hold no person name; the system SHALL NOT read a person field from it.

Source: tests/flow_organisation/test_flow_organisation.py

#### Scenario: Identifier under two teams
- **WHEN** one Jira team identifier is listed under two teams
- **THEN** the reading tool stops with exit code 1 and names both key paths and lines, without the identifier or the team names

#### Scenario: Missing referential
- **WHEN** the referential does not exist and no reader needs it
- **THEN** the tools that only read team labels run as before

### Requirement: Jira teams and referential teams controlled
The system SHALL report at export, with counts and identifiers only:

- the Jira team identifiers in neither the referential nor the catalogue: their number, the number of tickets affected and their sorted list;
- the count of identifiers and tickets of catalogue identifiers that no referential team lists;
- the count of tickets on identifiers flagged obsolete in the catalogue, those listed by a referential team included;
- the number of referential teams without any ticket in the export.

The export SHALL continue (design D17 of the GDPR alignment change). A catalogue entry SHALL NOT enter the count of referential teams without a ticket, and an obsolete catalogue identifier SHALL NOT be counted as unknown. The system SHALL NOT print a team name or label in these controls.

Source: tests/export_jira_api/test_referentiel_et_etiquettes.py (TraductionParReferentiel; to be extended, task 4.5)

#### Scenario: Inactive referential team
- **WHEN** two referential teams have no ticket in the export
- **THEN** the console prints "referential teams without ticket: 2" and no name

#### Scenario: Catalogue teams not counted as idle
- **WHEN** the catalogue holds teams without any ticket in the export
- **THEN** the count of referential teams without a ticket is the same as without the catalogue

### Requirement: Reports by Mission Team and by site
The system SHALL let the flow report and the dependency report aggregate by Mission Team or by site, through the referential, into separately named reports, on both data sources. A team of the export absent from the referential SHALL be grouped under an "outside the referential" group whose ticket count is stated. Sums over groups SHALL equal the global totals.

Source: tests/flux_jira/test_regroupement.py; tests/dependencies_jira/test_par_groupe.py

#### Scenario: Flow by Mission Team
- **WHEN** `compute --by mission-team` runs
- **THEN** the throughput, arrivals and work in progress are given per Mission Team, their sums equal the global figures, and the report name carries the aggregation

#### Scenario: Team outside the referential
- **WHEN** one team of the export is not in the referential
- **THEN** its tickets are counted under "outside the referential"

### Requirement: Headcount describes the structure only
The system SHALL use headcounts only to describe the structure (teams and headcount per Mission Team, department or site) in the structure summary of a report by Mission Team or by site. The system SHALL NOT divide a flow or dependency figure by a headcount, SHALL NOT write a figure per person, and SHALL NOT compare or rank teams, Mission Teams or sites by any figure.

Source: tests/flux_jira/test_regroupement.py; tests/dependencies_jira/test_par_groupe.py; tests/flow_organisation

#### Scenario: No ratio
- **WHEN** a report by Mission Team is written
- **THEN** no figure of the report is a throughput, a work in progress or a dependency count divided by a headcount, and no list is ordered by such a figure

#### Scenario: Ordering
- **WHEN** groups are listed in a report
- **THEN** they are ordered by name, not by a figure

### Requirement: Names stay in the flow folder
The system SHALL write team, Mission Team, department and site names only into files of the flow folder outside Git. It SHALL NOT write them into a console line of the export controls, a monthly-run summary or any file tracked by Git.

Source: tests/flux_jira/test_regroupement.py (console); tests/dependencies_jira/test_par_groupe.py (console); tests/export_jira_api/test_referentiel_et_etiquettes.py. The monthly-summary scenario is untested.

#### Scenario: Monthly summary
- **WHEN** a monthly run ends with reports by Mission Team
- **THEN** the summary holds no Mission Team, team or site name

### Requirement: Catalogue of Jira teams outside the organisation read strictly
The system SHALL read the team catalogue (outside Git; keys of team-mapping D1: name, identifiers, optional `type` and `obsolete`) with the strict loader, refusing with exit 1, key path and line, never a value: an unknown key (`obsolete_to_confirm` included, E2), an empty or duplicate name, a duplicate identifier. A missing catalogue SHALL be read as empty. It SHALL NOT accept a status key or a mark to confirm.

Source: tests/flow_organisation (task 3.1)

#### Scenario: Unknown key
- **WHEN** a catalogue team holds a headcount key
- **THEN** the reading stops with exit code 1, naming the key path and line, without any value

#### Scenario: Mark to confirm refused
- **WHEN** a catalogue team holds `obsolete_to_confirm: true`
- **THEN** the reading stops with exit code 1 as for an unknown key, naming the key path and line, without any value

#### Scenario: Obsolete flag read
- **WHEN** a catalogue team holds `obsolete: true`
- **THEN** the team is read as obsolete and stays a known team

#### Scenario: Missing catalogue
- **WHEN** the catalogue file does not exist
- **THEN** the translation uses the referential alone, and an identifier absent from it is in neither source

### Requirement: Identifier shared by the referential and the catalogue
The system SHALL accept an identifier listed in both the referential and the catalogue (team-mapping D1): the referential gives its name, the catalogue its type and obsolete flag. It SHALL refuse with exit code 1, naming both key paths and lines and never a value, a catalogue entry named like a referential team that holds an identifier no referential team lists. It SHALL NOT signal a referential name that differs from the catalogue label.

Source: tests/flow_organisation (task 3.2)

#### Scenario: Shared identifier accepted
- **WHEN** one identifier is listed under a referential team and in a catalogue entry with another label, a type and `obsolete: true`
- **THEN** the reading succeeds, the identifier's name is the referential team name, its type is the catalogue type, and it is read as obsolete

#### Scenario: Catalogue name of a referential team with an identifier outside it
- **WHEN** a catalogue entry has the name of a referential team and holds an identifier that no referential team lists
- **THEN** the reading stops with exit code 1 and names both key paths and lines, without the identifier or the names

#### Scenario: Different names not signalled
- **WHEN** every shared identifier has a referential name that differs from its catalogue label
- **THEN** no line, warning or refusal concerns these names, and no name is printed

### Requirement: Catalogue teams stay outside the referential structure
The system SHALL NOT add a catalogue entry to the referential's teams, groups, structure summaries or count of referential teams without a ticket. In a report by Mission Team or by site, a catalogue identifier that no referential team lists SHALL be grouped under "outside the referential", and the system SHALL NOT rename that group (team-mapping Q4).

Source: tests/flow_organisation, tests/flux_jira, tests/dependencies_jira (task 3.3)

#### Scenario: Not a referential team
- **WHEN** a report by Mission Team is computed on tickets of a catalogue identifier that no referential team lists
- **THEN** their tickets are counted under "outside the referential", and the structure summary and its headcounts are the same as without the catalogue

#### Scenario: Shared identifier stays in its referential team
- **WHEN** a report by Mission Team is computed on tickets of an identifier listed by a referential team and held by the catalogue
- **THEN** their tickets are counted under that team's Mission Team, as without the catalogue

### Requirement: Team type kept in the catalogue and the referential
The system SHALL accept in the catalogue and the referential an optional `type` key, one of the four Team sub-type names of team-mapping Q5, and SHALL refuse any other value (exit 1, D11 phrase, no value). A catalogue entry without the key SHALL have no type. It SHALL NOT guess a type from a label or another team, write a type into the referential, store it in the database, or print a label next to a type.

Source: tests/flow_organisation (task 3.4)

#### Scenario: Unknown type
- **WHEN** a catalogue team holds a `type` outside the four sub-type names
- **THEN** the reading stops with exit code 1 and "team type other than the four Team sub-types:" followed by the key path and line, without the value

#### Scenario: Type never taken from the name
- **WHEN** a referential team has no `type` key and none of its identifiers is in the catalogue
- **THEN** the team has no type, and no type is derived from its name

### Requirement: Referential team type deduced, the key only forcing it
The system SHALL deduce a referential team's type as the `type` the catalogue gives to all its `jira_team_ids` found there (team-mapping Q5 step 1, D1). A catalogue entry without `type` SHALL say nothing to the deduction: the type is deduced from the other identifiers (design D7 of the names-and-team-review change, pending the author's choice). The optional referential `type` key SHALL only force it, above the catalogue type (point 2): effective = forced, else deduced, else none. It SHALL NOT require a referential `type`, deduce one when the identifiers differ or none is in the catalogue, read an Assets list for it, or write the referential.

Source: tests/flow_organisation (task 3.5); the test of the catalogue entry without `type` renamed (names-and-team-review task 5.1)

#### Scenario: Type deduced without key
- **WHEN** a referential team without a `type` key holds two identifiers whose fictitious catalogue entries have the same type
- **THEN** its effective type is that type, and the referential file is unchanged

#### Scenario: Forced type wins
- **WHEN** a referential team holds a `type` key that differs from the type the catalogue gives to its identifiers
- **THEN** its effective type is the forced value, and the referential file is unchanged

#### Scenario: No deduction on different types
- **WHEN** a referential team without a `type` key holds two identifiers of different types in the catalogue
- **THEN** the team has no effective type

#### Scenario: Catalogue entry without type ignored
- **WHEN** a referential team without a `type` key holds one identifier whose catalogue entry has `Other Team` and another whose catalogue entry has no `type`
- **THEN** its effective type is `Other Team`, and the test that checks it is named after that behaviour

### Requirement: Team-names extract written by the author
The system SHALL provide the author-only subcommand `extract-teams`, which writes, from the strict loaders of the referential and the catalogue, the team-names extract into the flow folder outside Git, atomically and owner-only (design D4). It SHALL hold only team names, Jira team identifiers, types, flags and the date, chosen by a service function, never a headcount, site, department, Mission Team or other text of the sources. Untested until implemented.

#### Scenario: Only team-level fields
- **WHEN** the subcommand runs on a referential holding sites, departments, Mission Teams, headcounts and comments
- **THEN** the extract holds the team names, identifiers, types and flags, and none of the site, department or Mission Team names, headcounts or comment texts

#### Scenario: Team without identifier
- **WHEN** a referential team has no Jira team identifier
- **THEN** its entry in the extract has an empty identifier list and is marked without identifier

#### Scenario: Catalogue entry outside the referential
- **WHEN** no referential team lists any identifier of a catalogue entry
- **THEN** the entry is marked outside the referential in the extract

### Requirement: Team-names extract runs outside sessions and prints counts only
The system SHALL make `extract-teams` refuse to start inside a Claude Code session (exit 3) before reading any file, write nothing when a source is refused or when neither source exists (exit 1), and print counts only, in French by default and in English with `--language en` (design D10). It SHALL NOT print a name, call Jira or open a database session. Untested until implemented.

#### Scenario: Inside a session
- **WHEN** the subcommand is launched inside a Claude Code session
- **THEN** it exits with code 3 before opening the referential or the catalogue, and writes nothing

#### Scenario: Console
- **WHEN** the extract is written
- **THEN** the console shows the success line with counts only, and no team name

#### Scenario: Refused source
- **WHEN** the catalogue is refused by its strict loader
- **THEN** the subcommand exits with code 1 with the loader's message and the extract is not written or replaced

#### Scenario: No source
- **WHEN** neither the referential nor the catalogue exists
- **THEN** the subcommand exits with code 1, prints `no team source to extract` (English) and writes nothing
