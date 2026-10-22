# story-quality-manual Specification

## Purpose
The manual analysis, by the postures, of a story or epic pasted in a session: the grid applied and Critic called, the pasted text, keys and names written nowhere, and the reading of report results as team-level hypotheses, never to rank or evaluate people. Created by the change story-quality-audit (feature R-94).

## Requirements

### Requirement: A pasted story or epic goes to the relevant posture
The system SHALL route the analysis of a story or epic that the user pastes into a session as follows:
- Delivery for a story, and for an epic's readiness or splitting;
- Discovery for an epic's problem, outcome or hypothesis, entered through the switch formula;
- Facilitation only to prepare the coaching conversation with the PO.

It SHALL NOT mix two postures' frameworks without the switch formula. Untested until implemented.

#### Scenario: Epic outcome
- **WHEN** the user pastes an epic and asks whether its outcome is measurable
- **THEN** the answer is given by Discovery, with the switch formula when the exchange started in Delivery

### Requirement: The posture applies the grid and calls Critic
The system SHALL make the posture search the cases, then the library, read the effective grid through `grid --show`, give one verdict per effective criterion with its reason and source line or organisation-rule mark, write the manual-mode notice of design D14 once, and call Critic. It SHALL NOT add a criterion absent from the grid except under the hypothesis formula, nor present an out-of-library criterion as sourced. Untested until implemented.

#### Scenario: Overlay criterion cited
- **WHEN** `grid --show` lists an overlay criterion and the posture applies it to a pasted story
- **THEN** it cites that criterion with the organisation-rule mark and never with a library reference

#### Scenario: No overlay
- **WHEN** `grid --show` reports no organisation overlay
- **THEN** the posture applies the core criteria only and says that the core grid applies alone

#### Scenario: Pasted story
- **WHEN** the user pastes an invented story and asks whether it is ready
- **THEN** the answer starts with the Delivery tag, holds "Pasted text: analysed here, written to no tracked file." in an English answer, gives a verdict per story criterion, and ends with the Critic section and the reading of the critique

### Requirement: Pasted text, keys and names are written nowhere
The system SHALL NOT write a pasted story text, its ticket key or a name found in it to a tracked file (deliverables, documentation, specs, evaluation reports), a posture memory, the coaching journal, a case, an experiment, or a GitHub issue or comment. Untested until implemented.

#### Scenario: No request to keep
- **WHEN** a pasted story has been analysed and the user did not ask to keep the result
- **THEN** no file is written

### Requirement: A kept manual analysis holds verdicts and learning points only
The system SHALL write a file for a manual analysis only on the user's explicit request, in the deliverables folder ignored by Git (`_bmad-output/pmzilla/internes/`). That file SHALL hold only the criterion verdicts, the learning points and a summary of Critic's objections (the objection alone, author's decision of 2026-10-20), with the request at the top reworded. It SHALL NOT quote or reword the story, nor hold its key or a name. Untested until implemented.

#### Scenario: Request to keep
- **WHEN** the user asks to keep the analysis
- **THEN** the deliverable holds the verdicts, learning points and summary of Critic's objections, and no sentence, rewording, key or name of the pasted story

### Requirement: Names in a pasted story become roles
The system SHALL replace in its answer a name found in a pasted story by the person's role when it is known, and by "a person" otherwise. It SHALL NOT repeat the name. Untested until implemented.

#### Scenario: Name in the story
- **WHEN** the pasted story holds an invented first name
- **THEN** the answer does not contain that name

### Requirement: The session never reads stored story content
The system SHALL make the postures read the story quality results only through the three aggregated views and the story quality reports. The postures SHALL NOT read the `quality` tables, run the collection, analysis or coaching subcommands, or ask the user to paste coaching feedback into a deliverable. Untested until implemented.

#### Scenario: Reading the results
- **WHEN** the user asks for the story quality of the backlog
- **THEN** the posture reads the latest story quality report or the quality views, and no other source of story data

### Requirement: The postures never read or copy the organisation overlay file
The system SHALL make the postures name the overlay "the organisation overlay" in every tracked file and answer, never by the organisation's or the product's name. The postures SHALL NOT read, write or edit the overlay file directly, copy its content to a tracked file, a posture memory or GitHub, or present it as a library source. Untested until implemented.

#### Scenario: Request to show the overlay
- **WHEN** the user asks the posture to print the organisation overlay file
- **THEN** the posture runs `grid`, then `grid --show`, and shows the versions, the counts and the effective criteria they print
- **AND** it does not read the overlay file and does not propose to open it in an editor

### Requirement: Delivery and Discovery read the probable causes as hypotheses
The system SHALL make Delivery read the probable causes linked to the ticket template, the Definition of Ready and Refinement, and Discovery those linked to a Discovery Workflow step, each line presented under the hypothesis formula as a lead to check with the team. They SHALL NOT present a cause as a person's fault, nor put two teams' causes side by side. Untested until implemented.

#### Scenario: Definition of Ready cause
- **WHEN** the user asks Delivery what the latest story quality report says about a team's chain
- **THEN** the answer reads that team's sub-section only, opens each cause with the hypothesis formula, and names no person and no other team

#### Scenario: Discovery Workflow cause
- **WHEN** a team's sub-section holds a cause linked to a Discovery Workflow step and the user asks about epic outcomes
- **THEN** the answer is given by Discovery, entered with the switch formula when the exchange started in Delivery

### Requirement: The product-chain section is read as a product lead, never to rank a team
The system SHALL make Delivery and Discovery read the report's product-chain section, by link as for the team sub-sections, under the hypothesis formula, as a lead to check with the product's teams. They SHALL NOT use it to rank a team, attribute a product defect to a named team, or set it beside a team's sub-section to compare. Untested until implemented.

#### Scenario: Product chain read
- **WHEN** the user asks Delivery what the product chain section of the latest report says about the Definition of Ready
- **THEN** the answer opens each line with the hypothesis formula, names no team and no person, and gives no team's share

### Requirement: Results are never used to rank or evaluate people
The system SHALL make the postures refuse to rank teams or POs from the story quality results and refuse to use them to evaluate a person, and offer a team-level reading instead. Untested until implemented.

#### Scenario: Request for a PO's figures
- **WHEN** the user asks which PO writes the weakest stories
- **THEN** the posture refuses the comparison, says the results are by team and never a person's evaluation, and offers a team-level reading
