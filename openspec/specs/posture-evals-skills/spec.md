# posture-evals-skills Specification

## Purpose

Describes the consistency checks of the four posture skills (cross-references, identical shared copies, fixed-formula block, register titles) and of the wake script that each posture runs at start.
## Requirements
### Requirement: Cross-references to capability sheets resolve
The system SHALL ensure that every reference to a capability sheet in a posture skill points to an existing file, that each sheet declares its own name, that sheet names are English kebab-case, that former French names no longer appear anywhere, and that the fifteen renamed sheets exist. Capability tables of the templates SHALL cite existing sheets.

#### Scenario: Reference to absent sheet
- WHEN a skill file refers to a sheet that does not exist
- THEN the check fails naming the file and the reference

#### Scenario: Former name
- WHEN a former French sheet name appears in a skill
- THEN the check fails

Source: tests/postures_skills/test_postures_skills.py (Renvois)

### Requirement: No absolute path in templates
The system SHALL ensure that templates and skill files contain no user home path, no placeholder for project root or sanctum path, and no workspace path.

#### Scenario: Path leak
- WHEN a template contains an absolute user path
- THEN the check fails

Source: tests/postures_skills/test_postures_skills.py (SansCheminAbsolu)

### Requirement: Common copies are identical up to the posture
The system SHALL ensure that the wake and sanctum-initialisation scripts, and the prompt-quality canon, are identical across the four postures once the posture name is normalised.

#### Scenario: Divergence
- WHEN one posture's script differs beyond its name
- THEN the check fails

Source: tests/postures_skills/test_postures_skills.py (CopiesCommunes)

### Requirement: Fixed-formula block in every identity file
The system SHALL ensure that the reply-language block appears exactly once in each posture's identity template, directly after Core Values and before Standing Orders, with the same section order across postures, an identical block text, and, in both languages, the posture tag (for any posture and for Critic), the out-of-library, hypothesis and Critic-reading-title formulas and the source-separation formulas of the shared vocabulary. The case-citation formula is not required in the block.

#### Scenario: Missing formula
- WHEN a vocabulary formula is absent from the block
- THEN the check fails naming posture, language and formula

Source: tests/postures_skills/test_postures_skills.py (Formules)

### Requirement: Register titles and statuses follow the memory language
The system SHALL ensure the same language rule for register headings and status values in all four postures, that template headings are the English column of the guidance table, that French register titles appear only in the French column of that table, and that expected English statuses are listed.

#### Scenario: French title elsewhere
- WHEN a French register title appears outside the French column
- THEN the check fails

Source: tests/postures_skills/test_postures_skills.py (TitresDeRegistres)

### Requirement: Wake script prints root and mode
The system SHALL ensure that the wake script of each posture, run from either of its two locations, computes the project root and sanctum from its own location, prints the first-breath mode when no sanctum exists and the waking mode when it does, ignores a different root argument with a warning on the error stream (no warning for the same root), and exits successfully.

#### Scenario: First wake
- WHEN no sanctum exists
- THEN it prints the first-breath mode, the project root and the sanctum path

#### Scenario: After initialisation
- WHEN the sanctum is created
- THEN waking mode is printed from both the skill copy and the sanctum copy, and created files contain no absolute system path

#### Scenario: Different argument
- WHEN another root is passed
- THEN a warning says the argument is ignored and the computed root is printed

Source: tests/postures_skills/test_postures_skills.py (Reveil)

### Requirement: Wake is read-only
The system SHALL ensure the wake script writes nothing to the sanctum or the root (the tree is identical before and after, also with the pulse option), and that its code contains no write operation.

#### Scenario: Tree fingerprint
- WHEN the wake script runs in three call forms
- THEN the file tree is unchanged

Source: tests/postures_skills/test_postures_skills.py (Reveil)

### Requirement: Wake command written in each skill works from the project root
The system SHALL ensure that the wake command written in each skill's startup step is identical across postures, is a run of the script by a path relative to the project root, works from the root offline both without and with a sanctum, produces no error output, and that the former relative-to-skill form fails and is no longer written.

#### Scenario: Command as written
- WHEN the command is run from the root
- THEN it prints first-breath mode without a sanctum and waking mode with one, with empty error output

Source: tests/postures_skills/test_postures_skills.py (Reveil)

### Requirement: Missing local context warning and out-of-library list
The system SHALL ensure that each posture's wake output warns "LOCAL FILE MISSING" when the local context file imported by the project instructions is absent (also on first wake). It SHALL NOT warn when the file is present, or when the import marker is just prose or in a sentence. The wake output SHALL print the out-of-library list computed from the catalogue under a language-neutral heading. It SHALL refer to the out-of-library formula of the response language without quoting the formula of either language, including in the message shown when the list cannot be computed. It SHALL print the relations between works for the scaling posture only.

Source: tests/wake_postures/test_wake_postures.py

#### Scenario: Local file absent
- WHEN the import is declared and the file does not exist
- THEN the warning appears for every posture

#### Scenario: Import in a sentence
- WHEN the "@name" appears in prose
- THEN no warning is shown

#### Scenario: Empty catalogue
- WHEN the catalogue is empty
- THEN every referenced work is listed as out of the library

#### Scenario: No fixed formula in the wake output
- WHEN any posture wakes, with the list computed or not
- THEN the output contains neither the French nor the English out-of-library formula of the shared vocabulary

#### Scenario: Relations
- WHEN the scaling posture wakes
- THEN a relations section is printed; the discovery posture prints none

