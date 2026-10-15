# tooling-worktree Specification

## Purpose
Two shell scripts frame work in a Git worktree beside the workspace: one creates the worktree of a branch and points it to the workspace's sensitive-names list without reading it; the other, run by the user, removes the clean worktree of a branch and hands the branch to the branch-finishing script in the workspace.

## Requirements

### Requirement: The worktree script creates a worktree beside the workspace
The system SHALL provide a worktree script that creates a Git worktree of the workspace for a given branch, in a given folder or by default in a folder beside the workspace named after the branch. An existing branch SHALL be checked out; a new one SHALL be created from `main`. The script SHALL NOT push, merge, commit, or run the tests.

#### Scenario: New branch
- **WHEN** the script is given a branch that does not exist
- **THEN** a worktree is created beside the workspace on a new branch from `main`, the script prints `worktree : créé` with the folder and the branch, and exits 0

#### Scenario: Existing branch
- **WHEN** the script is given an existing branch that no worktree has checked out
- **THEN** the worktree checks out that branch

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

### Requirement: The worktree-finishing script finishes a branch from its worktree
The system SHALL provide a script, run by the user, that takes a branch, removes the clean worktree holding it with Git's worktree removal, switches the workspace to that branch, runs the branch-finishing script there with no input, and exits with that script's code unchanged (design D12). Its help option SHALL print the checks and codes and exit 0. It SHALL NOT force the removal nor prune worktrees.

Source: tests/finish_worktree/test_finish_worktree.sh

#### Scenario: Branch finished
- **WHEN** the branch's worktree is clean, the workspace is on `main` and clean, and the finishing script exits 0
- **THEN** the worktree folder no longer exists, the finishing script ran in the workspace on that branch, and the exit code is 0

#### Scenario: Code passed through
- **WHEN** the finishing script exits 13
- **THEN** the worktree-finishing script exits 13

#### Scenario: Launched from another worktree
- **WHEN** the user runs the script from a worktree other than the one of the branch
- **THEN** it finds the workspace, removes the branch's worktree and runs the finishing script in the workspace

#### Scenario: Help
- **WHEN** the script is started with the help option
- **THEN** it prints its checks and exit codes, exits 0 and changes nothing

### Requirement: The worktree-finishing script refuses before any change
The system SHALL refuse, with the codes 20 to 29 and key phrases of design D12, in that order: a usage error, a folder outside the repository, `main` or a spike branch, a missing branch, a workspace not on `main` or not clean, no worktree for the branch, a launch from inside it, and a worktree not clean. It SHALL NOT change any worktree or branch before every check passes.

Source: tests/finish_worktree/test_finish_worktree.sh

#### Scenario: Workspace on a work branch
- **WHEN** the workspace is not on `main`
- **THEN** the script exits 24 with `l'espace de travail n'est pas sur main`, and the worktree list and the workspace branch are unchanged

#### Scenario: No worktree for the branch
- **WHEN** the branch exists but no worktree other than the workspace holds it
- **THEN** the script exits 26, names the branch, and runs no finishing script

#### Scenario: Worktree folder deleted by hand
- **WHEN** the branch's worktree is still registered but its folder no longer exists
- **THEN** the script exits 26 with `dossier du worktree absent`, and the worktree list and the workspace branch are unchanged

#### Scenario: Launched from inside the worktree
- **WHEN** the current folder is inside the worktree to remove
- **THEN** the script exits 27 and the worktree still exists

### Requirement: The worktree-finishing script never deletes uncommitted or ignored work
The system SHALL refuse with code 28 a worktree holding a modified, staged or untracked non-ignored file, and with code 29 one holding ignored files other than the throwaway ones of design D12, printing only their count and first-level folders. It SHALL NOT stash, commit, discard, read or list by name those files.

Source: tests/finish_worktree/test_finish_worktree.sh

#### Scenario: Untracked file
- **WHEN** the worktree holds an untracked file that is not ignored
- **THEN** the script exits 28 and the worktree and the file are untouched

#### Scenario: Ignored deliverable
- **WHEN** the worktree holds an ignored file under an ignored output folder
- **THEN** the script exits 29 with `fichiers ignorés qui seraient perdus`, and the file is still there

#### Scenario: Local settings and caches only
- **WHEN** the only ignored files are the local settings written by the worktree script and Python caches
- **THEN** this check passes

### Requirement: Failures after the removal say what is left
The system SHALL, when Git's worktree removal fails, exit 30 without retrying; when the workspace switch fails after a removal, exit 31 and give the command that recreates the worktree; when the finishing script fails, say the worktree is removed and, for the codes of design D12 that leave the branch unmerged, give the recreation command. It SHALL NOT switch back, retry, merge or push on its own.

Source: tests/finish_worktree/test_finish_worktree.sh

#### Scenario: Red runner
- **WHEN** the finishing script exits 1
- **THEN** the script exits 1, the workspace is on the branch, and the output gives `git switch main && bash tools/worktree.sh` with the branch

#### Scenario: Merge done, run tree not updated
- **WHEN** the finishing script exits 13
- **THEN** the output says the worktree is removed and gives no recreation command

#### Scenario: Locked worktree
- **WHEN** Git refuses to remove the worktree because it is locked
- **THEN** the script exits 30, the worktree is still listed, and the finishing script is not run

### Requirement: The worktree-finishing script bypasses no check
The system SHALL leave every check to the branch-finishing script. It SHALL NOT pass a hook bypass option, set the owner bypass variable, push, merge, reset, or delete a branch itself.

Source: tests/finish_worktree/test_finish_worktree.sh

#### Scenario: Forbidden commands
- **WHEN** the script text is scanned outside comments
- **THEN** it contains no hook bypass option, forced removal, prune, push, merge, reset or owner bypass variable

### Requirement: The worktree-finishing script is testable without the real workspace
The system SHALL include a shell suite, listed in the runner's shell list, that runs the worktree-finishing script on temporary repositories with a fake finishing script set through the variable of design D12. It SHALL NOT read the real workspace, run the real finishing script or reach a remote.

Source: tests/finish_worktree/test_finish_worktree.sh; tests/run_all.sh (shell list)

#### Scenario: Suite run
- **WHEN** the runner runs the worktree-finishing suite
- **THEN** every case runs in a temporary folder and the suite reports its counts in the runner's shell format
