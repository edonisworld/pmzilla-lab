# tooling-worktree Specification

## Purpose
One shell script, `tools/worktree.sh`, creates the Git worktree of a branch in the worktrees folder of the lab folder, points it to the workspace's sensitive-names list without reading it, and can install Mothra's npm lock offline. The installation guide documents the lab folder layout and the move of existing worktrees as a user step; no tool moves a worktree.

## Requirements

### Requirement: The worktree script creates a worktree in the worktrees folder
The system SHALL provide a worktree script that creates a Git worktree of the workspace for a given branch, in a given folder or by default in the worktrees folder of the workspace's lab folder, resolved through the shared shell lab-paths module from the workspace found by Git (design D1, D2), under a name made of the `wt-` prefix and the branch with each slash replaced by a hyphen. An existing branch SHALL be checked out; a new one SHALL be created from `main`.

#### Scenario: New branch
- **WHEN** the script is given a branch that does not exist and no folder
- **THEN** a worktree is created in the worktrees folder of the lab folder on a new branch from `main`, the script prints `worktree : créé` with the folder and the branch, and exits 0

#### Scenario: Existing branch
- **WHEN** the script is given an existing branch that no worktree has checked out
- **THEN** the worktree checks out that branch, in the worktrees folder

#### Scenario: Variable set
- **WHEN** the worktrees-folder variable names a folder and no folder is given
- **THEN** the worktree is created in that folder

#### Scenario: Folder given
- **WHEN** the script is given a folder as second argument
- **THEN** the worktree is created in that folder, and the worktrees folder is neither created nor used

#### Scenario: Launched from a worktree
- **WHEN** the script is run from a linked worktree of the workspace
- **THEN** the new worktree is created in the worktrees folder of the workspace's lab folder, not beside the current worktree

Source: tests/worktree/test_worktree.sh (default folder and variable untested until implemented)

### Requirement: The worktree script does nothing beyond the creation
The script SHALL NOT compute the worktrees folder itself, push, merge, commit, or run the tests.

#### Scenario: Creation only
- **WHEN** the script creates a worktree
- **THEN** the worktrees folder comes from the shared lab-paths module, and no push, merge, commit or test run takes place

Source: tests/worktree/test_worktree.sh

### Requirement: The worktree points to the workspace's sensitive-names list without reading it
The system SHALL check only that the workspace's sensitive-names list exists, and SHALL give its absolute path, in the new worktree's local, Git-ignored settings, to the variable of the tools and to the variable of the pre-commit hook, and print the matching export lines. It SHALL NOT open, read, copy or link the list, nor write the path into a tracked file.

#### Scenario: List present
- **WHEN** the workspace holds the sensitive-names list
- **THEN** the worktree's local settings give both variables the path of that list and the output holds the two export lines

#### Scenario: List not readable
- **WHEN** the list exists but cannot be read
- **THEN** the worktree is still created, which shows the script never reads it

#### Scenario: List absent
- **WHEN** the workspace has no sensitive-names list
- **THEN** the script exits with code 3 with `liste des noms sensibles absente` and creates nothing

#### Scenario: Local settings not ignored
- **WHEN** the local settings file of the worktree would not be ignored by Git
- **THEN** the script exits with code 5 and writes no settings

Source: tests/worktree/test_worktree.sh

### Requirement: The worktree script refuses before any change
The system SHALL refuse, before any change, a missing branch argument (code 2), a target folder that already exists or a branch already checked out in another folder (code 4), and a failed Git command (code 5), with a message that names the folder, the branch or the command.

#### Scenario: Folder exists
- **WHEN** the target folder already exists
- **THEN** the script exits with code 4 with `existe déjà` and Git's worktree list is unchanged

#### Scenario: Branch open elsewhere
- **WHEN** the branch is already checked out in another folder
- **THEN** the script exits with code 4, names that folder and creates nothing

#### Scenario: No argument
- **WHEN** the script is run without a branch
- **THEN** it exits with code 2 and prints its usage

Source: tests/worktree/test_worktree.sh

### Requirement: The worktree script is testable without the real workspace
The system SHALL include a shell test suite, listed in the runner, that runs the worktree script on temporary repositories with a fixture list, and SHALL NOT read the real workspace or its list.

#### Scenario: Suite run
- **WHEN** the runner runs the worktree suite
- **THEN** every case runs in a temporary folder and the suite reports its counts in the runner's shell format

Source: tests/worktree/test_worktree.sh; tests/run_all.sh (shell list)

### Requirement: The worktree script creates the missing worktrees folder after its checks
The system SHALL, when the default folder is used and the worktrees folder is missing, create it after every check and before adding the worktree, with the line and the failure code 5 of design D3. It SHALL NOT create the folder when a check refuses, create a branch after a failed creation, or list, move or remove anything inside the worktrees folder. Untested until implemented.

#### Scenario: First worktree
- **WHEN** the worktrees folder is absent and every check passes
- **THEN** the folder is created, the output holds `dossier des worktrees créé` before `worktree : créé`, and the script exits 0

#### Scenario: Refusal leaves no folder
- **WHEN** the worktrees folder is absent and the sensitive-names list is absent
- **THEN** the script exits with code 3 and the worktrees folder still does not exist

#### Scenario: Creation impossible
- **WHEN** the worktrees folder cannot be created because its parent is not writable
- **THEN** the script exits with code 5 with `dossier des worktrees impossible à créer`, no branch is created and Git's worktree list is unchanged

### Requirement: The move of existing worktrees is a documented user step
The system SHALL document in the installation guide the lab folder layout and the move of existing worktrees as a user step of design D5, every lab session closed: Git's worktree move, repair only after a manual move, then a check of the worktree list. No tool SHALL move a worktree, and the guide SHALL NOT tell the user to prune worktrees or move the run tree or the root links. Untested until implemented.

#### Scenario: Guide read
- **WHEN** the installation guide section on the lab folder layout is read
- **THEN** it names the worktree move, the repair after a manual move, the check of the worktree list, states that the run tree and the links stay at the root, with no prune command, and names where Mothra lives (the `mothra/` folder of the workspace, no root entry, worktrees in the worktrees folder) as in the Mothra line of design D7

### Requirement: The worktree script offers an offline npm install of Mothra's lock
The system SHALL, after creating a worktree whose `mothra/package-lock.json` exists, ask on a terminal whether to run `npm ci --offline` in `mothra/` and run it on yes; otherwise, or without a terminal, it SHALL print the command to type, `cd <worktree>/mothra && npm ci`, without `--offline` (mothra-npm-ready design D1; R-20261110-28, R-20261110-35). It SHALL NOT run npm itself without `--offline`, nor any other npm subcommand.

#### Scenario: No terminal
- **WHEN** the lock exists and standard input is not a terminal
- **THEN** the script prints `dépendances npm de Mothra non installées : cd <worktree>/mothra && npm ci`, the line holds no `--offline`, no question is asked and the fake npm records nothing

#### Scenario: Answer no or empty on a terminal
- **WHEN** the lock exists and the answer on a terminal is `n` or empty
- **THEN** the script prints the same command to type, naming `mothra/` of the new worktree and without `--offline`, and the fake npm records nothing

#### Scenario: Yes on a terminal
- **WHEN** the lock exists and the answer on a terminal is `o`
- **THEN** the fake npm records exactly `ci --offline` in `mothra/` and the success line is printed

#### Scenario: No lock
- **WHEN** the worktree has no Mothra lock
- **THEN** no question is asked and the fake npm records nothing

Source: `tests/worktree/test_worktree.sh` (npm cases: without lock, terminal yes, no, empty answer, without terminal, variable not set, npm failing)

### Requirement: A failed offline install keeps the worktree and the exit code
The system SHALL, when `npm ci --offline` fails, print `npm ci --offline en échec (code <n>) : cache local incomplet ? lancer npm ci dans mothra/ avec le réseau, geste de l'auteur`, keep the worktree and exit 0 (design D1, D2). It SHALL NOT retry with the network.

#### Scenario: Incomplete cache
- **WHEN** the fake npm exits 1
- **THEN** the failure line names code 1, the worktree exists and the script exits 0
