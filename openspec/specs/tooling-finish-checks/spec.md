# tooling-finish-checks Specification

## Purpose
Describes the read-only module of finish checks, runnable by a Claude Code session: it computes for a branch, from its merge base with `origin/main`, controls 19, 5, 6, 14 and 16 with the rules of the unit finish, computes controls 14 and 16 for a given tree, reports the protected tooling a branch touches, and exposes its verdicts through service functions, a text output, a `--json` output and fixed exit codes.

## Requirements

### Requirement: New read-only module, unit finish script untouched
The system SHALL provide a new read-only module of finish checks, runnable by a Claude Code session (design D9). The system SHALL NOT modify, source, wrap or launch the unit finish script. The module SHALL NOT fetch, merge, push, write a reference or write a file. Untested until implemented.

#### Scenario: Unit finish script unchanged
- **WHEN** the module and its tests are added
- **THEN** the unit finish script and its test suite are unchanged and still green

#### Scenario: Read only
- **WHEN** the module checks a branch
- **THEN** no reference, file or object of the repository is created or changed

### Requirement: Per-branch base and real branch name
The system SHALL compute a branch's changed paths as the union of the paths changed from `merge-base(origin/main, tip)` and, when local `main` differs, from `merge-base(main, tip)`, rename detection off, with the real local branch name (finish-single-b3-b6 D13). It SHALL NOT use a looser set than either base, nor check `main`, `spike/*`, an unknown local branch or `lot/*` (exit 3); a missing `origin/main` or merge base SHALL exit 4.

#### Scenario: Train branch refused
- **WHEN** the module is asked to check a `lot/*` branch
- **THEN** it exits 3 and says to check each branch of the train

#### Scenario: Local main ahead
- **WHEN** local `main` holds a commit on a database path that `origin/main` does not have and the branch does not contain it
- **THEN** the paths changed from both bases are used, and control 14 applies

### Requirement: Controls 19, 5, 6 and 14 with the unit finish rules
The system SHALL compute controls 19, 5, 6 and 14 for a branch with the rules and refusal phrases of the unit finish (design D11, D14). The system SHALL compute all four, SHALL NOT stop at the first refusal, and SHALL NOT pass a control by default when its input cannot be read. Specification branches SHALL be exempt from controls 19 and 5. Untested until implemented.

#### Scenario: What each control checks
- **WHEN** a branch is checked
- **THEN** control 19 checks that no other active change is touched, control 5 that no linked change is left unarchived, control 6 that a validating evaluation record exists when an evaluated file changed, and control 14 that the tip's tree has a green dbtest line when a database path changed

#### Scenario: Evaluation input unavailable
- **WHEN** an evaluated file changed and the evaluated-files list or the records folder cannot be read
- **THEN** control 6 refuses with the phrase of the unit finish

#### Scenario: Another change touched
- **WHEN** a branch that is not a specification branch modifies a file of an active change other than its own
- **THEN** control 19 refuses with the phrase naming the other change, and the exit code is 1

#### Scenario: Two refusals
- **WHEN** a branch both leaves its change unarchived and changes a database path without a dbtest line
- **THEN** controls 5 and 14 are both reported as refused

#### Scenario: Specification branch
- **WHEN** a branch changes only files under `openspec/`
- **THEN** controls 19 and 5 are reported as not applicable and pass

### Requirement: Lists read from origin/main and the tip, strictest union
The system SHALL read the database paths file, the interface paths file, the evaluated-files list and the protected-tooling list at `origin/main`, at local `main` when it differs, and at the tip, and SHALL use their union (design D15 of change finish-single-b3-b6). The system SHALL NOT let a branch loosen a check by removing an entry from a list, and SHALL NOT keep a second copy of any of these lists. Untested until implemented.

#### Scenario: Entry removed on the branch
- **WHEN** a branch removes a database path pattern from the database paths file and changes a file matched by that pattern
- **THEN** control 14 still requires the dbtest line

#### Scenario: Interface entry removed on the branch
- **WHEN** a branch removes an entry from the interface list and changes a file matched by that entry
- **THEN** control 16 still requires the end-to-end line

### Requirement: Control 14 on a given tree
The system SHALL compute control 14 for a given tree, with the paths changed between `origin/main` and that tree, and with the dbtest line looked up for that tree (design D13). The system SHALL NOT accept a dbtest line recorded for another tree. Untested until implemented.

#### Scenario: Train tree without dbtest line
- **WHEN** a tree changes a database path and has no dbtest line
- **THEN** control 14 refuses for that tree, and the exit code is 1

#### Scenario: Tree without database change
- **WHEN** a tree changes no database path
- **THEN** control 14 is reported as not applicable and the exit code is 0

### Requirement: Protected tooling list defined by closure
The system SHALL keep a protected-tooling list whose patterns cover the closure of the roots of design D16 and its declared seeds, and a static test SHALL fail, naming the file, when a closure file is covered by no pattern, when a pattern matches no tracked file, or when a root is missing. The system SHALL NOT leave a closure file out of the list, except through an exemption entry in the test that carries a reason. Untested until implemented.

#### Scenario: Roots and closure
- **WHEN** the static test computes the closure
- **THEN** its roots are the finish scripts, the test runner, every Git hook, the morning guard and the hook installer, and the closure is every file they source, launch, import or name in code, followed recursively through sourced, launched and imported files only

#### Scenario: New sourced module
- **WHEN** a root starts sourcing a new file of `tools/` that no pattern covers
- **THEN** the static test fails and names that file

#### Scenario: Read data file
- **WHEN** a root names in its code a tracked data file that no pattern covers
- **THEN** the static test fails and names that file

#### Scenario: Stale pattern
- **WHEN** a pattern of the list matches no tracked file
- **THEN** the static test fails and names the pattern

### Requirement: Protected files touched are reported
The system SHALL report, for a branch, the protected-tooling files it changes since its base, one path per line and in JSON (design D14). Touching protected tooling SHALL NOT change the exit code of the branch check. The system SHALL NOT read the list from the working tree alone. Untested until implemented.

#### Scenario: Branch touching a hook
- **WHEN** a branch modifies a file of the Git hooks folder
- **THEN** the output says protected tooling is touched and lists that path

### Requirement: Logic in service functions, exit codes and JSON contract
The system SHALL compute every verdict in service functions that return records. The text output and the `--json` output (versioned by a `format` field) SHALL only format them. The exit codes SHALL be 0 (all pass or exempt), 1 (a control refuses), 2 (usage), 3 (branch not checkable) and 4 (cannot compute, exception type only), with the key phrases of design D14. The system SHALL NOT keep a control rule in the formatting code alone, and SHALL NOT print a stack trace. Untested until implemented.

#### Scenario: Same result in both outputs
- **WHEN** the same branch is checked with and without `--json`
- **THEN** both outputs give the same verdicts and the same exit code

#### Scenario: Missing base
- **WHEN** the repository has no `origin/main` reference
- **THEN** the module exits 4 with the phrase `calcul impossible (origin/main introuvable)`

### Requirement: Control 16 with the unit finish rules
The system SHALL compute control 16 for a branch, after control 14 and from the same bases: when a path of the interface list changed, the tip's tree SHALL have a line in the end-to-end record (change finish-e2e-proof-shared, design D2 to D4, phrases of D11). The system SHALL compute it even when an earlier control refuses, SHALL NOT exempt it by default when the list cannot be read, and SHALL NOT accept a line recorded for another tree. Untested until implemented.

#### Scenario: Interface path changed without proof
- **WHEN** a branch changes a path of the interface list and its tip's tree has no line in the end-to-end record
- **THEN** control 16 refuses with `contrôle 16 : refusé : preuve de bout en bout absente`, and the exit code is 1

#### Scenario: Proof recorded for the tip
- **WHEN** a branch changes a path of the interface list and the end-to-end record holds its tip's tree
- **THEN** control 16 passes

#### Scenario: No interface path changed
- **WHEN** a branch changes no path of the interface list
- **THEN** control 16 is reported as `contrôle 16 : sans objet (chemins d'interface inchangés)`

#### Scenario: List unreadable everywhere
- **WHEN** the interface list can be read at none of the revisions
- **THEN** control 16 refuses with the detail `liste des chemins d'interface absente ou illisible`, never exempt

### Requirement: Control 16 on a given tree
The system SHALL compute, in the tree mode, control 14 then control 16 for the given tree, with the paths changed between `origin/main` and that tree and the end-to-end line looked up for that tree, through the same control function as the branch mode (design D7, D8). The system SHALL NOT drop control 14 from the tree mode, SHALL NOT change the JSON format version for this addition, and SHALL NOT accept a line recorded for another tree. Untested until implemented.

#### Scenario: Train tree changing the front
- **WHEN** a tree changes a path of the interface list and has no end-to-end line
- **THEN** the tree mode reports control 14 then control 16, control 16 refuses, and the exit code is 1

#### Scenario: Same verdict in both modes
- **WHEN** the tree mode and the branch mode judge the same tree from the same base
- **THEN** they give the same verdict for control 16

### Requirement: Protected tooling classes
The system SHALL give every pattern of the protected-tooling list one class, `juge` or `sensible`, written as a tag in a comment of its line, and SHALL report a branch's touched protected files by class, in two JSON fields and two text lines (change finish-single-b3-b6, design D9, D10). The system SHALL NOT read an untagged pattern, or a pattern with two classes across revisions, as `sensible`, and SHALL NOT remove the existing list of touched files. Untested until implemented.

#### Scenario: Branch touching a sensitive tool only
- **WHEN** a branch changes only a file covered by a `sensible` pattern
- **THEN** the JSON lists it in `protected_sensitive`, `protected_judges` is empty, and the text says `outil sensible touché : 1 fichier(s)`

#### Scenario: Untagged line on an older revision
- **WHEN** a pattern is tagged `sensible` at the tip and has no tag at `origin/main`
- **THEN** a file it covers is reported as `juge`

### Requirement: Class test of the protected list
A static test SHALL fail, naming the line, when a pattern line of the protected-tooling list carries no known class tag, and SHALL fail, naming the file, when a file of the closure computed from the roots and the `juge` seeds is covered only by a `sensible` pattern (design D9). The system SHALL NOT let the test move an entry to `sensible`. Untested until implemented.

#### Scenario: Line without a class
- **WHEN** a pattern line of the list carries no tag
- **THEN** the static test fails and names that line

#### Scenario: Judge closure covered by a sensitive pattern
- **WHEN** a file sourced by a finish script is covered only by a `sensible` pattern
- **THEN** the static test fails and names that file

### Requirement: Control 20 in the branch mode
The system SHALL compute control 20 in the branch mode, after control 16: when the tip declares npm suites and the branch is open in a worktree, the Node version found SHALL be compared with each suite's wanted version by the single Node rule (design D13, D23). The system SHALL NOT install anything, SHALL NOT check the npm lock, and SHALL NOT pass the control when the Node version cannot be read. Untested until implemented.

#### Scenario: Node differs
- **WHEN** a branch open in a worktree declares an npm suite whose wanted Node version differs from the one found
- **THEN** control 20 is refused with `contrôle 20 : refusé : dépendances npm à mettre en conformité avant la fin (<raison>)` and the detail `lancer : cd <dossier>/<suite> && npm ci`, and the exit code is 1

#### Scenario: No npm suite
- **WHEN** the tip's test runner declares no npm suite
- **THEN** control 20 is reported as `contrôle 20 : sans objet (aucune suite npm déclarée)`

### Requirement: One Node version rule
The system SHALL decide whether a Node version found matches a wanted version in one service function, used by control 20 and, through a sub-command of the module, by the train's Node check (design D16). The system SHALL NOT keep a second comparison of Node versions in a finish script. Untested until implemented.

#### Scenario: Same rule for both callers
- **WHEN** the same found and wanted versions are given to control 20 and to the sub-command
- **THEN** both give the same verdict

### Requirement: Database paths in a data file
The system SHALL read the database paths of control 14 from one data file, as a union of `origin/main`, local `main` when it differs, and the tip (design D15). The system SHALL NOT parse them from the text of a finish script, and SHALL NOT keep a second copy of them. Untested until implemented.

#### Scenario: Entry removed on the branch
- **WHEN** a branch removes an entry of the database paths file and changes a file matched by it
- **THEN** control 14 still requires the dbtest line

### Requirement: Control 6 on a tree
The system SHALL compute control 6 for a given tree in the tree mode, after controls 14 and 16, accepting a validating record whose fingerprint of the evaluated files equals the one computed on that tree, or a record without fingerprint whose tested state has the same evaluated files (design D19). The system SHALL NOT accept a record whose fingerprint differs, and SHALL NOT pass the control when the tree's fingerprint cannot be computed. Untested until implemented.

#### Scenario: Instruction file changed with a matching record
- **WHEN** a tree changes an evaluated file and a validating record carries the fingerprint computed on that tree
- **THEN** control 6 of the tree passes

#### Scenario: No matching record
- **WHEN** a tree changes an evaluated file and no record matches it
- **THEN** control 6 of the tree is refused and the exit code is 1

### Requirement: Delegation of the unit finish to the module
Delegation tests on throwaway repositories SHALL check that the unit finish script, in its check mode and normal run, exits with the code mapped from the first control the module refuses, in the order 19, 5, 6, 14, 16, 20, or 0 when none refuses (design D14, D17). A static test SHALL fail when the script compares a control list or names one. The system SHALL NOT keep an implementation of these controls in the unit finish script. Untested until implemented.

#### Scenario: Same verdict
- **WHEN** a throwaway branch fails control 5 only
- **THEN** the unit finish check mode exits 5 and the module refuses control 5 only

#### Scenario: Control 20 delegated
- **WHEN** a throwaway branch fails control 20 only
- **THEN** the unit finish check mode exits 20 with the module's `lancer :` line

#### Scenario: No implementation left in the script
- **WHEN** the static test reads the unit finish script
- **THEN** it finds no comparison of a control list and no name of the database paths, interface paths or evaluated-files lists

### Requirement: The automatic policy is one service function
The system SHALL compute the automatic policy in one function, `auto_policy`, behind `finish_checks.py policy --train-tip <sha> --branch <b> --tip <sha> … --json`, with the reasons, order and labels of design D7 of change autonomous-trains-merge. It SHALL read the ready list and the review rule through `train_ready`, the stop and activation files through `train_auto`, and the author's-train rule through the one function `train_de_l_auteur` (design D2). It SHALL exit 0 when allowed, 1 when refused, 2 on usage and 4 when it cannot compute, and SHALL return `allowed` false on any reason or doubt. It SHALL NOT write a file, read an environment variable as an exemption, or keep a second copy of the list reader, the review rule, the protected list or `train_de_l_auteur`.

#### Scenario: Stop present
- **WHEN** the stop file exists
- **THEN** the output holds `"allowed": false` and the reason `arret`, and the exit code is 1

#### Scenario: Postures in the train
- **WHEN** a branch changes a path of `tests/postures/fichiers-evalues.txt`
- **THEN** the output holds `train-de-l-auteur` for that branch and `"allowed": false`

#### Scenario: Read only
- **WHEN** the policy has run
- **THEN** no file, reference or object of the repository or the data folder is created or changed

### Requirement: The runner and proof paths are one list
The system SHALL read the runner and proof paths from the one file `tools/finish_runner_paths.txt`, in union at `origin/main`, local `main` and the tip, through `runner_proof_paths()`, and SHALL give the paths a branch touches in the field `runner_proof_touched` of `branch --json` (design D3). The train SHALL read that field instead of its own list. A test SHALL fail when an entry of the file is not covered by a `juge` pattern of `tools/finish_protected.txt`, and another when `tools/finish_train.sh` holds one of these paths as a literal outside a comment. The system SHALL NOT keep a second copy of the list, nor admit a branch when the file is absent everywhere.

#### Scenario: Runner touched
- **WHEN** a branch changes `ci/passage.sh`
- **THEN** `runner_proof_touched` holds `ci/passage.sh`

#### Scenario: Entry outside the judge class
- **WHEN** an entry of the file is covered only by a `sensible` pattern or by none
- **THEN** the coverage test fails and names the entry

#### Scenario: List absent everywhere
- **WHEN** the file is absent at `origin/main`, local `main` and the tip
- **THEN** the train refuses the branch with `contrôles impossibles`
