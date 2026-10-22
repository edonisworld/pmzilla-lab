# mothra-tooling Specification

## Purpose
Frame the sessions that work on Mothra, the lab's web application: short session instructions in Mothra's folder that point to the recorded decisions, kept out of the public edition and of the posture evaluation set.

## Requirements

### Requirement: Mothra's folder carries short session instructions that point to the decisions
The system SHALL hold a short English `mothra/CLAUDE.md`, written by the author, with the content of design D6 of mothra-session-guards (references, stack, `node -e` rule, invariants 1 to 14 one line each), checked by a static suite with the phrases of design D7. It SHALL NOT copy a version number or the ADR's text, nor name a person, team, project or domain; the session SHALL NOT write it. Untested until implemented (suite `mothra_consignes`).

#### Scenario: Missing reference
- **WHEN** the file does not name `docs/pmzilla/mothra-tranches.md`
- **THEN** the suite fails with `renvoi absent des consignes de Mothra : docs/pmzilla/mothra-tranches.md`

#### Scenario: Stack not named
- **WHEN** the file does not name `Fastify`
- **THEN** the suite fails with `pile absente des consignes de Mothra : Fastify`

#### Scenario: Missing invariant line
- **WHEN** the file holds no line `9.` naming `ADR 0002`
- **THEN** the suite fails with `invariant absent des consignes de Mothra : 9`

#### Scenario: Copied version
- **WHEN** the file holds a dotted version number of three numeric segments
- **THEN** the suite fails with `version recopiée dans les consignes de Mothra : <texte> (la lire dans mothra/.node-version)`

#### Scenario: Too long
- **WHEN** the file holds more than 80 lines
- **THEN** the suite fails with `consignes de Mothra trop longues : <n> lignes (au plus 80)`

#### Scenario: Missing file
- **WHEN** the file does not exist
- **THEN** the suite fails with `consignes de Mothra absentes : mothra/CLAUDE.md`

### Requirement: Mothra's session instructions stay out of the public edition and of the evaluation set
The system SHALL exclude `mothra/CLAUDE.md` from the public edition by a specific manifest rule placed before any folder rule for `mothra/`, and the static suite SHALL fail with `consignes de Mothra évaluées par le jeu d'essai : <entrée> (décision Q11 à revoir)` when an entry of the posture evaluation list matches it. It SHALL NOT add the file to the evaluation list. Untested until implemented (suites `build_edition`, `mothra_consignes`).

#### Scenario: Edition build
- **WHEN** the edition is built with the file tracked
- **THEN** the file is excluded by its specific rule and the build does not stop with code 6

#### Scenario: Evaluation list entry
- **WHEN** a fake evaluation list holds an entry that matches `mothra/CLAUDE.md`
- **THEN** the suite fails and names the entry

#### Scenario: Root entry only
- **WHEN** the real evaluation list holds only the root `CLAUDE.md` entry
- **THEN** the suite passes and a change of `mothra/CLAUDE.md` triggers no posture evaluation check
