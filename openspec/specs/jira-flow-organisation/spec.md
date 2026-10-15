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
The system SHALL report at export, with counts and identifiers only: the Jira team identifiers absent from the referential (their number, the number of tickets affected and the sorted list of identifiers), and the number of referential teams without any ticket in the export. The export SHALL continue (design D17). The system SHALL NOT print a team name in these controls.

Source: tests/export_jira_api/test_referentiel_et_etiquettes.py (TraductionParReferentiel)

#### Scenario: Inactive referential team
- **WHEN** two referential teams have no ticket in the export
- **THEN** the console prints "referential teams without ticket: 2" and no name

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
