# tooling-mutation-tests Specification

## Purpose
Mutation tests of the code that masks small counts and checks database roles: an in-house mutator in the standard library mutates a closed scope in a temporary copy of the committed tree, runs the matching suites with no database and no network, and fails below a floor score, so that the masking tests are shown to catch real defects. Launched on demand and as a weekly step of the daily run, never by the test runner.

## Requirements

### Requirement: Mutation testing runs on a closed scope in a temporary copy
The system SHALL provide a mutation command that mutates only the masking and role functions and constants declared in its closed scope (design D2), in a temporary copy of the tracked files of the current commit created by the command itself, and runs the declared suites per mutant with a time limit. It SHALL NOT copy an ignored folder, write the working tree or the Git folder, or leave the temporary folder behind. Tested by suite `mutation_masking`.

#### Scenario: Copy content
- **WHEN** a run starts in a fixture repository holding an ignored folder with a sentinel file
- **THEN** the copy holds the tracked files only, the sentinel is absent, and the working tree is unchanged after the run

#### Scenario: Out of scope
- **WHEN** the fake module holds a function that is not declared in the scope
- **THEN** no mutant touches that function

#### Scenario: Time limit
- **WHEN** a mutant makes the fake suite exceed the time limit
- **THEN** the mutant is counted killed and reported on a "mutation : délai" line

### Requirement: The mutator uses the standard library only
The system SHALL generate mutants with an in-house mutator written with the Python standard library, with the operators of design D1 (comparison inversion, integer constant plus or minus one, `max`/`min` swap, `in`/`not in`, boolean negation, return of `None`). It SHALL NOT depend on a third-party package or a mutation tool, and SHALL add no entry to the component inventory. Tested by suite `mutation_masking`.

#### Scenario: Each operator
- **WHEN** the fake module holds one mutation point of each operator
- **THEN** each operator produces the expected mutant

### Requirement: Mutation runs never reach a database
The system SHALL run the suites of a mutation run without any inherited environment variable whose name starts with `PMZILLA_LAB_DB_` or `PG` and without the throwaway-database mark, so that database-backed tests are skipped, and SHALL set only neutral values (an address on port 1, a keychain reader path that does not exist, `PGPORT` 1) so that a mutant that bypasses a guard cannot reach the keychain or a server. It SHALL NOT open a database connection. Tested by suite `mutation_masking`.

#### Scenario: Variables exported
- **WHEN** the database variables and the throwaway mark are exported and a fake suite records its environment
- **THEN** the suite sees none of the exported values

### Requirement: The score is compared with a threshold setting
The system SHALL print a score per target, the summary with the score and the threshold, and one line per surviving mutant by file, function, line and operator (design D4); it SHALL exit 0 when the score reaches the threshold of its tracked setting file, 3 with `mutation : score <s> % sous le seuil <t> %` below it, and 2 when the run cannot happen. It SHALL NOT print or store source code, a diff, test data or a configuration value. Tested by suite `mutation_masking`.

#### Scenario: Below the threshold
- **WHEN** the threshold is above the score of a run on the fake module
- **THEN** the output holds "sous le seuil" and one "mutation : survivant" line per survivor, and the exit code is 3

#### Scenario: At the threshold
- **WHEN** the threshold equals the score of a run on the fake module
- **THEN** the exit code is 0 and the survivors are still listed

#### Scenario: Reference suite failing
- **WHEN** the fake suite fails on the unchanged copy
- **THEN** the output holds "mutation : lancement impossible" and the exit code is 2

### Requirement: The threshold is a bounded setting and no survivor is excluded
The system SHALL read the threshold as one whole number from 50 to 100 in a tracked setting file (floor 70, target 80) and SHALL exit 2 before any mutant when it is missing, unreadable or out of range (design D5). It SHALL NOT read any list of accepted or excluded survivors: every mutant counts in the score. Tested by suite `mutation_masking`.

#### Scenario: Threshold out of range
- **WHEN** the setting file holds 40
- **THEN** the output holds "mutation : lancement impossible" and the exit code is 2

#### Scenario: No exclusion
- **WHEN** the wrapper's text and folder are read
- **THEN** they name no file of accepted or excluded survivors

### Requirement: The floor mutant is killed
The system SHALL keep the masking suite strong enough that turning the floor of 5 into 4 in `tools/flow_views.py` makes `tests/flow_views` fail. Tested by suite `mutation_masking`.

#### Scenario: Floor 5 becomes 4
- **WHEN** a temporary copy holds `tools/flow_views.py` with its floor set to 4 and the suite `tests/flow_views` runs there
- **THEN** the suite fails

### Requirement: Mutation testing stays out of the test runner
The system SHALL keep the mutation wrapper outside the test folder and SHALL NOT name it in the test runner, so that no complete, targeted or filtered run launches a mutation run. Tested by suite `mutation_masking`.

#### Scenario: Runner text
- **WHEN** the runner script and the test folder are read
- **THEN** the runner does not name the wrapper and no suite folder holds it

### Requirement: Weekly scheduled run with catch-up
The system SHALL, with the due option, run only when no run was attempted today and either today is the configurable weekly day or the last complete run is older than seven days or absent; otherwise it SHALL print "mutation : pas due" and exit 0. It SHALL record each attempt in an owner-only state file of the lab data folder holding no code text. Tested by suite `mutation_masking`.

#### Scenario: Not due
- **WHEN** today is the weekly day and a run was already attempted today
- **THEN** nothing runs, "mutation : pas due" is printed and the exit code is 0

#### Scenario: Catch-up
- **WHEN** today is not the weekly day and the last complete run is older than seven days
- **THEN** the run happens
