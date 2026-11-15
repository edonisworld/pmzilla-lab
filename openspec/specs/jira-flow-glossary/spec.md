# jira-flow-glossary Specification

## Purpose

Describes the shared glossary of flow measures used by the Markdown flow reports and by the dashboard, so both explain the same terms in the same words. Sources are `tests/flux_jira/test_glossaire.py` (direct test of `tools/flow_glossary.py`) and the reports' tests, which assert the definitions that appear in the reading guide.

## Requirements

### Requirement: Complete and consistent glossary
The system SHALL keep exactly the same set of entries in French and in English, SHALL give every entry a non-empty definition that opens with its term in bold, and SHALL NOT give an entry the same text in both languages. Every entry named by a reading order (report, segments, batch closures) SHALL exist in both languages, and no entry SHALL appear twice across the reading orders.

Source: tests/flux_jira/test_glossaire.py

#### Scenario: Same entries in both languages
- **WHEN** the French and English glossaries are compared
- **THEN** they have the same entries, each non-empty, opening with a bold term, and different from its translation

#### Scenario: Reading orders
- **WHEN** the three reading orders are joined
- **THEN** they hold no duplicate and every entry exists in each language

### Requirement: Fixed order of the reading guide
The system SHALL return the reading-guide definitions as Markdown bullets in a fixed order, in the requested language: percentiles (median, 85th, why percentiles), lead time and age, work in progress, arrivals and exits, Little's law, Monte Carlo forecast; then the optional parts (next requirement).

Source: tools/flow_glossary.py (lignes_rapport); tests/flux_jira/test_glossaire.py (test_lignes_du_rapport_dans_l_ordre_et_la_langue); tests/flux_jira/test_flux_jira.py (CommentLire)

#### Scenario: One bullet per definition
- **WHEN** the reading guide is requested with segments and batch closures, in French then in English
- **THEN** each line is a bullet holding one definition, in the report order then the segment order then the batch-closure order, and the two languages differ

### Requirement: Optional parts of the reading guide
After the report definitions, the system SHALL add, only when requested, the time-per-segment notions (segment, commitment point, flow efficiency, coverage); then, only when requested, the batch closure definition.

Source: tools/flow_glossary.py (lignes_rapport); tests/flux_jira/test_glossaire.py (test_lignes_du_rapport_dans_l_ordre_et_la_langue); tests/flux_jira/test_flux_jira.py (TempsParSegment); tests/flux_jira/test_fermetures_groupees.py (Fermetures)

#### Scenario: Without segments
- **WHEN** the report has no time per segment
- **THEN** no segment definition appears

#### Scenario: With batch closures
- **WHEN** the report has a batch closure section
- **THEN** the batch closure definition is included

### Requirement: Entries outside the reading orders kept out of the reading guide
The entries that no reading order names (throughput, cumulative flow, ageing work in progress) SHALL stay in both languages and SHALL NOT appear in a report's reading guide. The entries for the work in progress breakdown, the dependency map and the baseline evolution (`repartition`, `graphe`, `base`) SHALL be removed (design D6 of change remove-flow-board).

Source: tools/flow_glossary.py (lignes_rapport); tests/flux_jira/test_glossaire.py

#### Scenario: Full reading guide
- **WHEN** the reading guide is requested with segments and batch closures
- **THEN** none of these entries appears in it

#### Scenario: Entries kept
- **WHEN** the French and English glossaries are read after the removal of the dashboard
- **THEN** both still hold the throughput, cumulative flow and ageing work in progress entries, each non-empty and opening with its term in bold, and neither holds `repartition`, `graphe` or `base`

### Requirement: One source of definitions for every reader
The system SHALL hold one definition per flow measure in French and in English, in light Markdown, shared by the flow reports (reading guide) and by every other reader of the glossary module, with no hard-coded figure from data. The entries `debit`, `cfd` and `aging_wip`, which no reading order names, SHALL be kept as definitions for the glossary export planned for Mothra, and SHALL NOT be removed with the dashboard.

Source: tools/flow_glossary.py; tests/flux_jira/test_flux_jira.py (CommentLire)

#### Scenario: Same text for every reader
- **WHEN** a definition is shown in a report and read through the glossary module by another reader
- **THEN** both come from the same text for the chosen language

## Open questions

None.
