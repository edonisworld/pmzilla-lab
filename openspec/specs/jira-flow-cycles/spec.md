# jira-flow-cycles Specification

## Purpose
Describes the neutral cycle and patch keys mapped in the flow settings and the cycles report computed from the database (cycle flow, up-merge share and provision, Epic Review section), which names cycles only by their neutral keys. Sources are `tests/flux_config/test_nouveaux_blocs.py`, `tests/flux_jira/test_cycles_calcul.py`, `tests/flux_jira/test_cycles_commande.py` and `tests/flow_store/test_lecteurs_cycles.py`.

## Requirements

### Requirement: Neutral cycle keys mapped in the flow settings
The system SHALL read from the `cycles` block of the flow settings a mapping from a neutral cycle key to one fix version, a start date and an end date, and from the `patches` block a mapping from a quarterly patch key to its fix versions. Cycle keys SHALL have the form of design D12 (`YYYY-Cn` with n from 1 to 6, or `YYYY-EOY`), patch keys the form `YYYY-Qn` with n from 1 to 4. The system SHALL refuse, with exit code 1 naming the key path and line and never a value: a key of another form, a fix version mapped to two keys, a start date that is not a Monday, an end date that is not a Friday, and a cycle that does not start on the Monday after the previous cycle's end. A cycle that does not last eight weeks SHALL give a warning naming the key only.

Source: tests/flux_config/test_nouveaux_blocs.py (TestCycles, TestPatches)

#### Scenario: Valid year
- **WHEN** six consecutive eight-week cycles and a year-end version are mapped
- **THEN** they are read without warning

#### Scenario: Gap between cycles
- **WHEN** a cycle starts two weeks after the previous end
- **THEN** the tool stops with exit code 1 and names the cycle key and its line, without the dates

#### Scenario: Wrong key form
- **WHEN** a key is written as a version number
- **THEN** it is refused with exit code 1 and the key path, and the version number is not echoed

### Requirement: First cycle of the year functional unless flagged as base version
The system SHALL treat every `YYYY-Cn` cycle as a functional version, C1 included, unless that cycle carries the optional base-version flag of design D12 in the cycles block (provisional reading, pending confirmation by the release manager). For a flagged cycle, the cycles report SHALL write the base-version label of design D19 next to the cycle key in its header, and SHALL compute its figures like any other cycle. The flag SHALL be refused with exit code 1, naming the key path and line, when it is set on a key other than a `YYYY-Cn` cycle or on more than one cycle of a year. The system SHALL NOT infer the base version from a version number or a date, and SHALL NOT need a code change for either answer.

Source: tests/flux_config/test_nouveaux_blocs.py (test_base_version*); tests/flux_jira/test_cycles_commande.py (VersionDeBase)

#### Scenario: No flag
- **WHEN** no cycle carries the flag
- **THEN** C1 to C6 are reported as functional versions and no header carries "base version"

#### Scenario: C1 flagged
- **WHEN** C1 carries the flag
- **THEN** the report header writes "base version" next to C1, and C2 to C6 are reported as functional versions

#### Scenario: Two flags in one year
- **WHEN** two cycles of the same year carry the flag
- **THEN** the tool stops with exit code 1 and names both key paths and lines

### Requirement: Version numbers never in outputs
The system SHALL write cycles and patches in every output, report and summary only by their neutral keys, and SHALL count fix versions that map to no key as "unmapped fix versions" without naming them. The system SHALL NOT write a fix version name or a product version number in an output, a report or a tracked file.

Source: tests/flux_jira/test_cycles_calcul.py (test_versions_non_mappees_comptees_sans_nom); tests/flux_jira/test_cycles_commande.py

#### Scenario: Unmapped version
- **WHEN** tickets carry a fix version absent from the mapping
- **THEN** the cycles report gives the count of unmapped versions and of their tickets, and no version name

### Requirement: Targeted cycle from fix version
The system SHALL take the targeted cycle of a ticket from its current fix version mapped to a cycle key, and SHALL NOT infer it from the cycle label, which stays a marker of topics to work on. A ticket with the domain cycle label and no fix version mapped to a cycle SHALL be counted as "cycle label without targeted cycle".

Source: tests/flux_jira/test_cycles_calcul.py (test_cycle_vise_vient_de_la_version_pas_de_l_etiquette)

#### Scenario: Label without version
- **WHEN** a ticket carries the cycle label and no mapped fix version
- **THEN** it is in no cycle's flow and is counted once under "cycle label without targeted cycle"

### Requirement: Cycles report from the database
The system SHALL provide a `cycles` subcommand of the flow report tool that reads only the database (no CSV option), and writes a Markdown and a JSON report named after the series and the day in the reports folder, giving per cycle key: items targeted, items delivered within the cycle window, items carried to a later cycle, up-merge items resolved within the window, the up-merge share and the configured provision side by side, the two-labels count, the without-patch count, and the Epic Review section of the jira-flow-labels capability. Up-merge items SHALL be counted in their quarterly patch and SHALL NOT count in the cycle flow. Tickets out of the export SHALL be left out. The report SHALL hold no key, no person and no version name.

Source: tests/flux_jira/test_cycles_commande.py; tests/flux_jira/test_cycles_calcul.py (FluxDuCycle); tests/flow_store/test_lecteurs_cycles.py (DeBoutEnBout)

#### Scenario: Up-merge out of the cycle flow
- **WHEN** a cycle window holds twenty delivered cycle items and five up-merge items attached to a quarterly patch
- **THEN** the cycle's delivered count is twenty, the up-merge share is five out of twenty-five, and the patch counts five up-merge items

#### Scenario: Provision missing
- **WHEN** a cycle has no configured provision
- **THEN** the share is written and the provision cell says it is not configured

#### Scenario: CSV files given
- **WHEN** CSV files are passed to `cycles`
- **THEN** the run stops with "no CSV file may be given" and no file is read

#### Scenario: No cycle configured
- **WHEN** the settings hold no cycles block
- **THEN** the run stops with exit code 1 saying no cycle is configured, before reading the database, and writes no report

### Requirement: Up-merge items without a patch fix version counted apart
The system SHALL, pending the domain's confirmation of design D7, count in the cycles report every up-merge item resolved within a cycle window that carries no fix version mapped to a quarterly patch key: it SHALL include it in the cycle's up-merge share (the window comes from the resolution instant) and SHALL write it, instead of under a patch, on a separate line with the without-patch label of design D19 ("without patch" in English, "sans patch" in French) and its count. The system SHALL NOT silently drop such an item, SHALL NOT attach it to a patch by its dates or by guess, SHALL NOT stop the report or change its exit code because of it, and SHALL NOT list its key. Items carrying both up-merge labels stay under the requirement "Exactly one up-merge label" of the jira-flow-labels capability.

Source: tests/flux_jira/test_cycles_calcul.py (FluxDuCycle)

#### Scenario: Up-merge item without patch
- **WHEN** a cycle window holds twenty delivered cycle items, four up-merge items attached to a quarterly patch and one up-merge item with no patch fix version
- **THEN** the up-merge share is five out of twenty-five, the patch counts four up-merge items, the "without patch" line counts one, and the exit code is unchanged

#### Scenario: None without patch
- **WHEN** every up-merge item of the window carries a patch fix version
- **THEN** the "without patch" line gives zero

### Requirement: Up-merge provision per cycle
The system SHALL read the up-merge provision as an optional share of delivered items per cycle key in the cycles block (design D7), refuse a share below zero or above one with exit code 1 naming the key path, and SHALL NOT convert the provision into points, days or capacity.

Source: tests/flux_config/test_nouveaux_blocs.py (test_provision); tests/flux_jira/test_cycles_calcul.py (test_provision_configuree_et_absente)

#### Scenario: Share above one
- **WHEN** a provision is greater than one
- **THEN** the tool stops with exit code 1 and names the key path and line
