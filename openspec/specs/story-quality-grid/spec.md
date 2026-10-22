# story-quality-grid Specification

## Purpose
The audit grid of story and epic quality: a versioned core grid of criteria, each sourced in the library or marked outside it, completed by one optional organisation overlay that is checked for names and never loosens a confidentiality rule, and the `grid` subcommand that validates the grid and shows the effective criteria, as text or JSON. Created by the change story-quality-audit (feature R-94).

## Requirements

### Requirement: A versioned core grid for stories and epics
The system SHALL provide one tracked core grid, as a human-readable file and a machine-readable twin with the same content. The core grid SHALL hold an identifier, a version, a list of story criteria and a list of epic criteria. The postures and the analysis tool SHALL read the same core grid. Untested until implemented.

#### Scenario: Same grid for both readers
- **WHEN** the human-readable file and the twin are compared
- **THEN** they list the same codes for the same version

### Requirement: Each criterion is fully described
The system SHALL give each criterion a stable code, a definition written in the project's own words, the question put to the analysis engine, an optional "not applicable" condition, its link in the chain (design D18) and French and English labels. The grid SHALL NOT hold a ticket key, a team, a project, a domain or a person's name. Untested until implemented.

#### Scenario: Structure
- **WHEN** the grid twin is loaded
- **THEN** it has at least one story criterion and one epic criterion, and every criterion has a unique code, a definition, an engine question, a link among ticket template, Discovery Workflow step, Definition of Ready and Refinement, and both labels

#### Scenario: Name in the grid
- **WHEN** a criterion text holds an entry of the sensitive-names list
- **THEN** the grid test fails without printing the entry

### Requirement: Every core criterion is sourced in the library or marked outside it
The system SHALL give every core criterion a source line: a library reference written as *Author, Title*, section, as returned by the library's read tool for a passage that was read, or the out-of-library formula of the grid's language. The grid SHALL NOT cite a passage that was not read. It SHALL NOT hold an excerpt beyond a short quotation in quotation marks, and SHALL NOT copy a figure. Untested until implemented.

#### Scenario: Missing source line
- **WHEN** a criterion of the twin has no source line
- **THEN** the grid test fails naming the criterion code

#### Scenario: Out-of-library criterion
- **WHEN** a criterion has no library source
- **THEN** its source line is the out-of-library formula, not an empty line and not a general-knowledge reference presented as a library source

### Requirement: Verdicts are enumerated codes tied to the core and overlay versions
The system SHALL express every verdict on a criterion as one of four codes: met, not met, not applicable and undetermined. Every stored verdict SHALL carry the identifier and version of the core grid and of the organisation overlay, the overlay ones empty when there is no overlay. A verdict SHALL NOT be free text. Untested until implemented.

#### Scenario: New core version
- **WHEN** the core grid version changes
- **THEN** verdicts of the former version are no longer read by the report, and the coverage view counts the items audited at the current pair of versions

#### Scenario: New overlay version
- **WHEN** the overlay version changes after every item was audited
- **THEN** no verdict of the former pair is counted by any view or the report until `analyse` has audited the items again

#### Scenario: Versions recorded
- **WHEN** an item is analysed with the core grid and an overlay
- **THEN** each of its verdicts carries both identifiers and both versions

### Requirement: One organisation overlay applies to every item
The system SHALL read at most one organisation overlay, the YAML file of the `regles/` subfolder of the context folder (design D17), validated against the tracked JSON Schema, and SHALL apply it to every item of every team. It SHALL NOT read a per-team overlay, nor take the overlay's path from `flux.yaml`. Without the file, it SHALL use the core grid alone and print the no-overlay key phrase of design D14. Untested until implemented.

#### Scenario: Path from the context folder
- **WHEN** the context-folder variable points to a temporary folder whose `regles/` subfolder holds a valid fixture overlay
- **THEN** `grid` reads that overlay, and a `story_quality` block naming another overlay path is refused as an unknown key

#### Scenario: Schema file
- **WHEN** the overlay is validated
- **THEN** the validation uses the tracked file `tools/story_quality_overlay.schema.json` through the `jsonschema` library, and an overlay breaking one of its rules is refused with the overlay-invalid key phrase

#### Scenario: No overlay
- **WHEN** `grid` or `analyse --dry-run` runs with no overlay file
- **THEN** the output holds "no organisation overlay: core grid only" and only core criteria are used

#### Scenario: Same overlay for all teams
- **WHEN** items of two teams are analysed with an overlay present
- **THEN** both teams' items are analysed with the same effective grid

### Requirement: The overlay holds structure and business criteria only
The system SHALL accept in the overlay only an identifier, an integer version, the expected structure of an epic and of a User Story, an optional product context summary of bounded length, added criteria, and disabled core criteria each with a reason. Any other key SHALL be refused with exit code 3 and the overlay-invalid key phrase of design D14, naming the key path and never its value. Untested until implemented.

#### Scenario: Product context summary too long
- **WHEN** the overlay's product context summary exceeds the length bound of the schema
- **THEN** the overlay is refused with "organisation overlay invalid:" and the key path, without the summary's text, and the exit code is 3

#### Scenario: Key outside the schema
- **WHEN** the overlay holds a key about masking, scrubbing, the review gate, the cap or retention
- **THEN** the output holds "organisation overlay invalid:" with the key path, nothing is sent, and the exit code is 3

#### Scenario: Disabled without reason
- **WHEN** the overlay disables a core criterion without a reason, or names an unknown core code
- **THEN** the overlay is refused with exit code 3, naming the key path

### Requirement: The overlay never loosens a confidentiality rule
The system SHALL NOT let the overlay change the scrubbing, the masking of small cells, the team review gate, the cap, the confirmation, the dry run, the retention, the deny rules or the four verdict codes. The overlay SHALL NOT reword, relink or relabel a core criterion; it SHALL only add criteria or disable core ones. Untested until implemented.

#### Scenario: Overlay present, rules unchanged
- **WHEN** the same batch runs with and without a valid overlay
- **THEN** the blocked counts, the cap, the confirmation prompt and the masking are identical

#### Scenario: Core criterion relinked
- **WHEN** the overlay sets a new label, definition or link for a core criterion code
- **THEN** the overlay is refused with "organisation overlay invalid:" and the key path, and the exit code is 3

### Requirement: Overlay criteria carry the organisation-rule mark
The system SHALL give each overlay criterion the same fields as a core criterion, except the source line, which SHALL be the organisation-rule mark of design D14 in the output's language. An overlay criterion SHALL NOT carry a library reference. Untested until implemented.

#### Scenario: Mark in place of a source
- **WHEN** the effective grid is built from the core grid and an overlay adding one criterion
- **THEN** the added criterion's source line is "organisation rule" in English and "règle de l'organisation" in French

### Requirement: The overlay is checked for names before any use
The system SHALL check the overlay's text, its identifier and product context summary included, with the sensitive-names list and the personal-identifier scanner before any use. On a match it SHALL stop with exit code 3 and the overlay-refused key phrase of design D14, giving the line number, never the matched value. Untested until implemented.

#### Scenario: Sensitive name in the overlay
- **WHEN** an overlay criterion's definition holds an entry of the fake sensitive-names list
- **THEN** the output holds "organisation overlay refused: sensitive name or identifier in line" with the line number, no request is sent, the entry is not printed, and the exit code is 3

#### Scenario: Identifier in the product context summary
- **WHEN** the product context summary holds an invented e-mail address
- **THEN** the overlay is refused with the same phrase and line number, the address is not printed, and no request is sent

### Requirement: The overlay version is set by hand and never reused for other content
The system SHALL record a content hash per overlay identifier and version on the first real send that uses them. `analyse` and `coach`, dry run included, SHALL refuse with exit code 3 and the content-changed key phrase of design D14 an overlay whose hash differs from the one recorded for its identifier and version. A dry run SHALL record nothing. Untested until implemented.

#### Scenario: Content changed under the same version
- **WHEN** a criterion of the overlay is edited after a confirmed `analyse`, and the version is left unchanged
- **THEN** the next `analyse` or `analyse --dry-run` prints "organisation overlay content changed without a new version", sends nothing, and the exit code is 3

#### Scenario: New version accepted
- **WHEN** the same edit comes with a new version number
- **THEN** the overlay is accepted and its hash is recorded for the new version at the first confirmed send

#### Scenario: Dry run records nothing
- **WHEN** `analyse --dry-run` runs with an overlay version never used
- **THEN** no hash is recorded for that version

### Requirement: The grid subcommand validates and prints counts only
The system SHALL provide a `grid` subcommand that validates the core grid and the overlay and prints the grid-valid key phrase of design D14 with the versions and the counts of criteria added and disabled. It SHALL NOT print a criterion text, a reason or the overlay's identifier, and SHALL read no database, no Jira and no key. Untested until implemented.

#### Scenario: Valid overlay
- **WHEN** `grid` runs with a valid overlay adding two criteria and disabling one
- **THEN** the output holds "grid valid: core" with the versions, "2 criteria added, 1 disabled", and no distinctive string of the overlay fixture

### Requirement: grid --show prints the effective criteria and nothing else
The system SHALL make `grid --show` print, under the header key phrase of design D14, the effective criteria (code, labels, definition, engine question, "not applicable" condition, link, source line or organisation-rule mark) and the expected structure per kind. It SHALL NOT print a disabling reason, the overlay's identifier or the product context summary, and SHALL read no database, no Jira and no key. Untested until implemented.

#### Scenario: Effective criteria shown
- **WHEN** `grid --show` runs with a fixture overlay adding one criterion and disabling one core criterion with a distinctive reason
- **THEN** the output starts with "Effective grid: core", lists the added criterion with "organisation rule" and not the disabled one, and holds neither the reason, the identifier nor the summary's distinctive strings

#### Scenario: No overlay
- **WHEN** `grid --show` runs with no overlay file
- **THEN** it prints the core criteria only, with the no-overlay key phrase

### Requirement: The effective grid is one service result, shown as text or JSON
The system SHALL build the effective grid (core criteria not disabled, overlay criteria with the organisation-rule mark, expected structure per kind) in one service function (design D15), from the validated and checked core grid and overlay. `grid --show` and `grid --show --json` SHALL format its result and SHALL NOT build criteria of their own. The function SHALL read no database, no Jira and no key. Untested until implemented.

#### Scenario: Same criteria in text and JSON
- **WHEN** `grid --show` and `grid --show --json` run with a fixture overlay adding one criterion and disabling one core criterion
- **THEN** both list the same effective criteria in the same order, the added one with the organisation-rule mark, and neither lists the disabled one

### Requirement: grid --show --json prints the effective-grid contract
The system SHALL print, with `grid --show --json`, the effective-grid contract of design D15 as one JSON document on stdout, with the no-overlay phrase on stderr. The document SHALL NOT hold a disabling reason, the overlay's identifier, the product context summary or a key outside the contract. Untested until implemented.

#### Scenario: Nothing private in the JSON
- **WHEN** the fixture overlay holds distinctive strings in its identifier, a disabling reason and the product context summary
- **THEN** none of them appears in the JSON document, and the document holds no key outside the contract

#### Scenario: No overlay in JSON
- **WHEN** `grid --show --json` runs with no overlay file
- **THEN** stdout parses as one JSON document with a null overlay version and core criteria only, and the no-overlay phrase is on stderr

### Requirement: A product context summary in the overlay is the only business context sent
The system SHALL send the overlay's product context summary, when present, with every item of every audit, sample and coaching batch, and count it in the cost estimate. It SHALL NOT read the context collection, notes or map of change `organisation-context`, nor open the library store. Untested until implemented.

#### Scenario: Summary in every request
- **WHEN** a confirmed `analyse` sends three items with an overlay holding a summary with a distinctive string
- **THEN** each of the three recorded requests holds that string, and the batch estimate is larger than with the same overlay without summary

#### Scenario: No library store opened
- **WHEN** the tripwire test of `organisation-context` scans the story quality tool
- **THEN** it passes with no allow-list entry for the tool, because the tool never opens the library store

### Requirement: The edition ships an invented example overlay
The system SHALL track the overlay schema and an invented example overlay, `docs/pmzilla/surcouche-qualite-exemple.yaml` (generic product, roles only, invented product context summary), that the suite validates against the schema. No tracked file SHALL hold the real overlay or name the organisation or the product it describes. Untested until implemented.

#### Scenario: Example valid
- **WHEN** the example overlay is validated against the schema
- **THEN** it is valid, adds at least one story and one epic criterion, holds a product context summary, and holds no entry of the fake sensitive-names list
