# tooling-worktree Specification

## Purpose
Two shell scripts frame work in a Git worktree beside the workspace: one creates the worktree of a branch and points it to the workspace's sensitive-names list without reading it; the other, run by the user, removes the clean worktree of a branch and hands the branch to the branch-finishing script in the workspace.

## Requirements

### Requirement: The worktree script creates a worktree in the worktrees folder
The system SHALL provide a worktree script that creates a Git worktree of the workspace for a given branch, in a given folder or by default in the worktrees folder of the workspace's lab folder, resolved through the shared shell lab-paths module from the workspace found by Git (design D1, D2), under a name made of the `wt-` prefix and the branch with each slash replaced by a hyphen. An existing branch SHALL be checked out; a new one SHALL be created from `main`. The script SHALL NOT compute the worktrees folder itself, push, merge, commit, or run the tests.

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
The system SHALL refuse before any change, in order, with codes 20 to 29: usage, outside the repository, `main` or spike, missing branch, workspace not on `main` or not clean, no worktree, launch from inside it, worktree not clean; code 42, another finish in progress (multi-session-piloting design D5), SHALL come right after the usage check, and code 44, morning state not verified (morning-guard design D7), right after 42. It SHALL run the finishing script's check mode in the workspace with empty input, printing its lines, and map its codes 5, 6, 7, 8, 12, 14 and 19 to 32 to 36, 41 and 49, any other to 37; it SHALL exit 46 when the merge of `main` into the branch is predicted to conflict or fails and is aborted, and 48 when the throwaway-database pass is red (finish-under-lock design D3, D4, D6). Its help SHALL list them in step order, name codes 39 and 50 as reserved, and not name code 47. It SHALL NOT change anything after a refusal, except a merge of `main` into the branch already made, which every later refusal SHALL state on the line after its phrase (`main est fusionnée dans la branche ; rien d'autre n'est changé`); it SHALL NOT exit 39 or 50.

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

#### Scenario: Unarchived linked change seen before the removal
- **WHEN** the branch changes code and holds an unarchived OpenSpec change linked to it, and every check 20 to 29 passes
- **THEN** the script exits 32 with `la fin de branche refuserait : change OpenSpec non archivé`, the worktree folder still exists and is still listed, the workspace is on `main`, and neither the runner nor the finishing script is run

#### Scenario: Main diverged
- **WHEN** the check returns code 7
- **THEN** the script exits 34 and nothing is changed

#### Scenario: Throwaway-database run missing
- **WHEN** the check returns code 14 again after a green throwaway-database pass, at the first or at the second check
- **THEN** the script exits 41 with `la fin de branche refuserait : passage dbtest vert absent`, the worktree is still there, and after a first-check refusal the runner was not run

#### Scenario: Another change touched
- **WHEN** the check returns code 19
- **THEN** the script exits 49 with `la fin de branche refuserait : la branche touche un autre change OpenSpec` and nothing is changed

#### Scenario: Refusal after a merge
- **WHEN** `main` was merged into the branch and the check after the merge returns 5
- **THEN** the script exits 32, and the line after its phrase is `main est fusionnée dans la branche ; rien d'autre n'est changé`

#### Scenario: Check impossible
- **WHEN** the check command fails to run or returns a code outside 0, 5, 6, 7, 8, 12, 14 and 19
- **THEN** the script exits 37 with `vérification préalable impossible` and the code, and nothing is changed

#### Scenario: Check passes
- **WHEN** both runs of the check and the fake runner return 0
- **THEN** the output holds `vérification préalable réussie`, then the worktree is removed, the workspace switched and the finishing script run

#### Scenario: Help lists the codes
- **WHEN** the help option is given
- **THEN** the help lists codes 20, 42, 44, 21 to 38, 40, 41, 45, 46, 48 and 49 in the order of the steps, 42 right after 20, 44 right after 42, 41 between 36 and 37, names codes 39 and 50 as reserved, and does not name code 47

#### Scenario: Another finish running
- **WHEN** a lock of a live process with another token exists
- **THEN** the script exits 42 with `finish_worktree : une autre fin de branche est en cours (<branche>, depuis HH:MM)`, and the worktree list, the workspace branch and the lock are unchanged

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
The system SHALL take the checks it runs before the removal from the branch-finishing script's check mode, SHALL NOT reimplement any of them, and SHALL still run the full finishing script after the removal, every check of which applies again; that script's complete runner is skipped only on a matching finish record (test-speed design D7). Its only merge SHALL be the merge of `main` into the branch, in the worktree, of finish-under-lock design D3. It SHALL NOT pass a hook bypass option, set the owner bypass variable, push, merge the branch into `main`, reset, delete a branch itself, write a fingerprint, or run a filtered or targeted run.

Source: tests/finish_worktree/test_finish_worktree.sh

#### Scenario: Forbidden commands
- **WHEN** the script text is scanned outside comments
- **THEN** it contains no hook bypass option, forced removal, prune, push, reset, owner bypass variable or merge other than the merge of `main` in the worktree with its abort

#### Scenario: Check, runner and finish all run
- **WHEN** the fake check command, the fake runner and the fake finishing script all exit 0
- **THEN** the check ran first with the branch as its argument, then the runner in the worktree, then the check again with the branch, then the finishing script in the workspace on the branch

#### Scenario: No fingerprint written
- **WHEN** the fake runner exits 0 and the script finishes
- **THEN** neither fingerprint of the workspace was written by the worktree-finishing script

### Requirement: The worktree-finishing script is testable without the real workspace
The system SHALL include a shell suite, listed in the runner's shell list, that runs the worktree-finishing script on temporary repositories with a fake finishing script set through the variable of design D12. It SHALL NOT read the real workspace, run the real finishing script or reach a remote.

Source: tests/finish_worktree/test_finish_worktree.sh; tests/run_all.sh (shell list)

#### Scenario: Suite run
- **WHEN** the runner runs the worktree-finishing suite
- **THEN** every case runs in a temporary folder and the suite reports its counts in the runner's shell format

### Requirement: The complete runner runs in the worktree before the removal
The system SHALL, after the check mode, delete any finish record and run the runner's entry point in the worktree with empty input and no bypass variable: exit 38 when it fails, 40 when the tip moved; else write the finish record under design D5, print the green line of D11 and run the check mode again before the removal. It SHALL NOT remove the worktree after codes 32 to 38 or 40, bypass a lock the runner honours, nor write a record when the fingerprint differs from the tip tree.

#### Scenario: Red runner before removal, the worktree stays, nothing changed
- **WHEN** every check 20 to 29 and the check mode pass and the fake runner exits 1
- **THEN** the script exits 38 with `le runner complet n'est pas vert dans le worktree (code 1)`, the worktree folder still exists and is still listed, the workspace is on `main`, no finish record exists, and neither the second check nor the finishing script ran

#### Scenario: Branch moved during the runner
- **WHEN** the fake runner adds a commit to the branch and exits 0
- **THEN** the script exits 40 with `la branche a changé pendant le runner`, the second check is not run, no finish record exists, and the worktree is still there

#### Scenario: Refusal of the second check
- **WHEN** the fake runner exits 0 without moving the tip and the second run of the fake check returns 5
- **THEN** the output holds `runner complet vert dans le worktree`, the script exits 32, the worktree is still there, and the finishing script is not run

#### Scenario: Runner environment
- **WHEN** the fake runner records its current folder, its input and its environment
- **THEN** the folder is the worktree, the input is empty, and neither the variable reserved to git commit nor the owner bypass variable is set

#### Scenario: Fingerprint of the tip present
- **WHEN** `FINISH_WORKTREE_ALLOW_SKIP` is `1` and the fake runner writes the tip tree into the worktree complete-run fingerprint and exits 0
- **THEN** the output holds `fiche de fin écrite`, the common Git folder holds the record with the branch, tip and tree, and the fake finishing script receives the token variable

#### Scenario: Fingerprint absent
- **WHEN** the fake runner exits 0 without writing the worktree complete-run fingerprint
- **THEN** the output holds `empreinte complète absente ou différente du sommet`, no record exists, and the finishing script still runs

#### Scenario: Force variable ignored by the worktree script
- **WHEN** the force variable of test-speed design D16 is set, `FINISH_WORKTREE_ALLOW_SKIP` is `1` and the fake runner writes the tip tree into the worktree complete-run fingerprint
- **THEN** the runner still runs in the worktree, the record is written and the fake finishing script receives the token variable and the force variable unchanged

#### Scenario: Stale record
- **WHEN** a finish record exists before the run and the fake runner exits 1
- **THEN** the script exits 38 and no record exists

Source: tests/finish_worktree/test_finish_worktree.sh (codes 38, 40, runner environment); the finish record untested until implemented (task 2.2); the force variable untested until implemented (task 2.7)

### Requirement: The finish record is private, one-time and holds no path
The system SHALL write the finish record in the common Git folder, owner-only, through a temporary file renamed in place, with the fields of test-speed design D5, the environment signature as a hash only (D9) and a random token (D6) passed to the finishing script through its variable. It SHALL NOT print the token, write a path into the record, or write the record outside the common Git folder.

#### Scenario: Record content
- **WHEN** the record is written
- **THEN** it holds the format version, the branch, the tip, the tree, a signature of hexadecimal characters, a token and a date, and no line holds the worktree or workspace path

#### Scenario: Token never shown
- **WHEN** the script runs to its end with a record written
- **THEN** the token from the record appears nowhere in the standard or error output

Source: untested until implemented (tests/finish_worktree/test_finish_worktree.sh, task 2.2)

### Requirement: The finish record is written only when the skip is allowed
The system SHALL write the finish record only when `FINISH_WORKTREE_ALLOW_SKIP` is absent, empty or exactly `1` (skip-default-on design D1) and every other condition holds. For any other value it SHALL write none, print the line with `saut non autorisé (réglage désactivé)` and still pass the token to the finishing script. It SHALL NOT treat another value as allowed, print `réglage absent`, nor put a file name or a path in that line.

#### Scenario: Setting absent
- **WHEN** the setting is absent, the fake runner writes the tip tree into the worktree complete-run fingerprint, exits 0 and the worktree did not move
- **THEN** the record is written, as in the scenario of the fingerprint of the tip, and the fake finishing script receives the token variable

#### Scenario: Setting empty
- **WHEN** the setting is empty, in the same conditions
- **THEN** the output and the result are the same as with the setting absent

#### Scenario: Another value
- **WHEN** the setting is `oui`, `0` or `11`, in the same conditions
- **THEN** the output holds `saut non autorisé (réglage désactivé) : le script de fin le relancera`, no record exists, the fake finishing script receives a token, and no output holds `réglage absent`

#### Scenario: Setting at 1
- **WHEN** the setting is `1`, in the same conditions
- **THEN** the record is written, as in the scenario of the fingerprint of the tip

#### Scenario: Other lines unchanged
- **WHEN** the setting is absent or `0` and the worktree moved during the runner, or the fingerprint is absent
- **THEN** the output holds the line of that case (`worktree modifié pendant le runner` or `empreinte complète absente ou différente du sommet`), not the line of the setting, and no record exists

#### Scenario: End to end
- **WHEN** the real finishing script and the real pre-push hook run, with fake runners
- **THEN** without the setting, or with the setting at `1`, only the worktree runner runs; with the setting at `0`, or with the force variable set, the worktree runner and the finishing script's runner both run

#### Scenario: Documented
- **WHEN** the script header and the guide section on finishing a branch from its worktree are read
- **THEN** both name `FINISH_WORKTREE_ALLOW_SKIP`, say that absent, empty or `1` allow the skip and that `0` turns it off, and name the priority of `FINISH_BRANCH_FORCE_RUN`

Source: tests/finish_worktree/test_finish_worktree.sh (untested until implemented, task 2.2 of skip-default-on)

### Requirement: No finish record while another process works in the worktree
The system SHALL list, just before and just after the worktree runner, the processes whose current folder is the worktree or inside it, other than its own (test-speed-2 design D12), and SHALL write no finish record, printing the line of D29, when one is found or when the listing is missing, fails or does not name its own process. It SHALL NOT signal, wait for or name those processes, nor add an exit code.

#### Scenario: Process found
- **WHEN** a fake listing reports a process whose current folder is inside the worktree, the setting is `1` and the fake runner writes the tip tree into the worktree complete-run fingerprint
- **THEN** the output holds `un autre processus a son dossier courant dans le worktree`, no record exists, no process number appears, and the finishing script still runs

#### Scenario: Listing impossible
- **WHEN** the listing command is missing, exits non-zero, or does not name the script's own process
- **THEN** the output holds `vérification des processus impossible` and no record exists

#### Scenario: Real listing with a process in the worktree
- **WHEN** a real background process has its current folder in the worktree during the finish
- **THEN** no record is written

#### Scenario: Real listing, worktree free
- **WHEN** no other process has its current folder in the worktree and every other condition holds with the setting at `1`
- **THEN** the record is written as before

Source: untested until implemented (tests/finish_worktree/test_finish_worktree.sh, task 3.1)

### Requirement: The worktree-finishing script holds the finish lock
The system SHALL make the worktree-finishing script take the finish lock of multi-session-piloting design D5 right after its usage check, hold it over every later step, pass its token to the check, the worktree runner and the finishing script, and remove it on exit, whatever the outcome, only when its token is its own. A stale lock (D6) SHALL be reported with `verrou de fin périmé, repris` and replaced. It SHALL NOT wait for the lock, print the token, or remove a live lock of another token.

#### Scenario: Token passed down
- **WHEN** the fake check, the fake runner and the fake finishing script record the lock token they receive and all exit 0
- **THEN** each received the token of the lock, the lock existed during each, and no lock remains after the exit

#### Scenario: Refusal releases the lock
- **WHEN** the worktree is not clean (code 28)
- **THEN** the script exits 28 and no lock remains

### Requirement: The worktree-finishing script removes the handoff note only after a finish
The system SHALL make the worktree-finishing script remove the handoff note of its branch (multi-session-piloting design D4) after an exit 0, and keep it after any other exit. It SHALL NOT remove the note of another branch.

#### Scenario: Note removed after a finish
- **WHEN** a note exists for the branch and the fake finishing script exits 0
- **THEN** the note no longer exists

#### Scenario: Note kept after a refusal
- **WHEN** a note exists for the branch and the fake runner exits 1 (code 38)
- **THEN** the note is still there

### Requirement: No finish record when a directory of the worktree changed during the runner
The system SHALL treat as "worktree moved during the runner" any directory of the worktree that holds a tracked file, the worktree root included, whose change time is newer than the marker set before the runner, as it does for tracked files (test-db-guards design D2): it SHALL write no finish record and print the existing line `worktree modifié pendant le runner`. A failed listing SHALL count as a change. It SHALL NOT print a path, add an exit code, or write a record after such a change.

#### Scenario: Tracked folder renamed and put back
- **WHEN** the fake runner renames a folder holding tracked files, puts it back, writes the tip tree into the fingerprint and exits 0, with the setting at `1`
- **THEN** the output holds `worktree modifié pendant le runner`, no record exists, no path appears, and the finishing script still runs

#### Scenario: Untracked file created then removed
- **WHEN** the fake runner creates an untracked file in the worktree root or in a tracked subfolder and removes it before exiting 0
- **THEN** no record exists and the output holds the same line

#### Scenario: Nothing changed
- **WHEN** the fake runner changes nothing in the worktree and every other condition holds with the setting at `1`
- **THEN** the record is written as before

Source: untested until implemented (tests/finish_worktree/test_finish_worktree.sh, task 3.2)

### Requirement: The worktree-finishing script refuses inside the morning window before any change
The system SHALL run the morning-state check right after the finish lock, before refusal 22, and again just before the removal, and refuse with code 44 and the lines of morning-guard design D7 when it does not allow; a code 17 of the finishing script SHALL be transmitted unchanged. It SHALL NOT remove the worktree, switch the workspace, run the runner or launch the finishing script on refusal, nor offer a way to waive it. Untested until implemented (worktree-finishing suite).

#### Scenario: Refused before the runner
- **WHEN** the guard command replaced by the suite exits 1 and every other check would pass
- **THEN** the exit code is 44, the error output holds `finish_worktree : fenêtre du matin, état du matin non vérifié`, the worktree is still listed, the workspace is on `main`, and the fake runner and the fake finish record no call

#### Scenario: Refused before the removal
- **WHEN** the guard command exits 0 at its first call and 1 at its second
- **THEN** the exit code is 44, the fake runner was called once, the worktree is still listed and the fake finish records no call

#### Scenario: Code 17 of the finish
- **WHEN** the guard command exits 0 both times and the fake finish exits 17
- **THEN** the script exits 17 and gives the recreation line

### Requirement: The worktree run follows the light decision
The system SHALL make the worktree-finishing script compute, before its run in the worktree, the light decision of light-spec-finish design D3 through the shared helper, and run there the validation then the light runner when it is light, or the complete runner as before, with the reason line of D8. It SHALL NOT take the light path when the force variable is set, nor change the meaning of codes 32 to 41. Untested until implemented (suite `finish_worktree`).

#### Scenario: Light run in the worktree
- **WHEN** the branch changes only OpenSpec files and the record holds the tree of `main`
- **THEN** the fake light runner is called in the worktree, the fake complete runner is not, and the output holds `chemin allégé : passage allégé dans le worktree`

#### Scenario: Force variable
- **WHEN** the force variable is set and every light condition holds
- **THEN** the fake complete runner is called in the worktree

#### Scenario: Expired validation or changed environment
- **WHEN** the record line is 8 days old, or holds another environment signature than the one computed in the worktree
- **THEN** the fake complete runner is called in the worktree and the output holds `runner complet nécessaire : validation de main expirée` or `runner complet nécessaire : environnement changé depuis la validation`

### Requirement: A red light run in the worktree changes nothing
The system SHALL exit 45 with the phrase of light-spec-finish design D8 when the validation fails in the worktree, and 38 with `(passage allégé)` when a light suite fails, leaving the worktree in place and the workspace on `main`. Untested until implemented (suite `finish_worktree`).

#### Scenario: Validation red in the worktree
- **WHEN** the fake validation exits 1
- **THEN** the script exits 45 with `openspec validate --strict en échec dans le worktree ; rien n'est changé`, and the worktree is still listed

#### Scenario: Light suites red in the worktree
- **WHEN** the fake light runner exits 1
- **THEN** the script exits 38 and the output holds `(passage allégé)`

### Requirement: A green light run writes no finish record
The system SHALL, after a green light run in the worktree, write no finish record and print the line of light-spec-finish design D7, so that the finishing script repeats the light run. Untested until implemented (suite `finish_worktree`).

#### Scenario: No record
- **WHEN** the light run is green in the worktree and the skip setting is `1`
- **THEN** no finish record exists and the output holds `fiche de fin sans objet`

### Requirement: Code 18 of the finishing script is transmitted
The system SHALL transmit code 18 of the finishing script unchanged and, since the branch is not merged, print the worktree recreation command as for codes 1 to 9. Untested until implemented (suite `finish_worktree`).

#### Scenario: Validation red in the finishing script
- **WHEN** the fake finishing script exits 18
- **THEN** the worktree-finishing script exits 18 and prints the recreation command

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

### Requirement: A worktree in the worktrees folder is finished like any other
The system SHALL let the worktree-finishing script find, check, remove and finish the worktree of a branch held in the worktrees folder exactly as one held at the lab root, through Git's worktree list (design D4). It SHALL NOT assume a location for the worktree, nor move or prune a worktree. Untested until implemented.

#### Scenario: Worktree under the worktrees folder
- **WHEN** the branch's worktree is in a worktrees subfolder of the temporary lab folder, clean, and the fake check, runner and finishing script exit 0
- **THEN** the worktree folder no longer exists, the finishing script ran in the workspace on that branch, and the exit code is 0

### Requirement: The move of existing worktrees is a documented user step
The system SHALL document in the installation guide the lab folder layout and the move of existing worktrees as a user step of design D5, every lab session closed: Git's worktree move, repair only after a manual move, then a check of the worktree list. No tool SHALL move a worktree, and the guide SHALL NOT tell the user to prune worktrees or move the run tree or the root links. Untested until implemented.

#### Scenario: Guide read
- **WHEN** the installation guide section on the lab folder layout is read
- **THEN** it names the worktree move, the repair after a manual move, the check of the worktree list, states that the run tree and the links stay at the root, with no prune command, and names where Mothra lives (the `mothra/` folder of the workspace, no root entry, worktrees in the worktrees folder) as in the Mothra line of design D7

### Requirement: The worktree finish validates only the touched OpenSpec items on the light path
The system SHALL make the worktree-finishing script, on the light path, run in the worktree the same validation helper as the finishing script, with the up-to-date `main` and the branch tip as arguments, and exit 45 with its existing phrase when the helper reports a new strict finding (light-finish-touched-specs design D3). It SHALL NOT reimplement the items or the comparison, nor run `openspec validate --all --strict` as its default validation.

#### Scenario: New finding in the worktree
- **WHEN** the light decision holds and the helper exits 1
- **THEN** the script exits 45, the worktree is still there, and neither the light runner nor the finishing script ran

#### Scenario: Validation passes
- **WHEN** the helper exits 0
- **THEN** the light runner runs in the worktree as before

### Requirement: The worktree finish runs a first check before any change
The system SHALL make the worktree-finishing script, after its checks 20 to 29 and before any merge, run the check mode for the branch (finish-under-lock design D1). Codes 0, 8 and 14 SHALL let it go on; 5, 6, 19, 7 and 12 SHALL give 32, 33, 49, 34 and 36, any other 37, nothing changed. It SHALL NOT merge, run the throwaway-database script or the runner after such a refusal.

#### Scenario: Unarchived change refused before the merge
- **WHEN** the branch is behind `main` and the first check returns 5
- **THEN** the script exits 32, the branch does not contain `main`, and no merge, pass or runner ran

#### Scenario: Branch behind main goes on
- **WHEN** the first check returns 8
- **THEN** the script goes on to the merge preview

### Requirement: The worktree finish previews then merges main into the branch under the lock
The system SHALL, holding the finish lock and when the branch lacks it, preview with the shared merge-preview function the merge of the most advanced of local `main` and the fetched remote `main`, then merge it into the branch in its worktree with empty input and the lock token (finish-under-lock design D2, D3, D10). It SHALL NOT move local `main`, force a fast-forward, bypass a hook, or merge after a failed fetch or a divergence.

#### Scenario: Remote main ahead
- **WHEN** the remote `main` holds a commit that local `main` and the branch lack, and every check passes
- **THEN** the branch contains the remote `main`, the output holds `main fusionnée dans la branche`, and local `main` still points to its former commit

#### Scenario: Already contained
- **WHEN** the branch already contains the most advanced `main`
- **THEN** the output holds `main déjà contenue dans la branche : aucune fusion` and the branch tip is unchanged

### Requirement: A predicted or failed merge of main stops the finish with code 46
The system SHALL exit 46 with `fusion de main dans la branche impossible : conflit prévu sur <n> fichier(s), rien n'est changé` and the paths when the preview predicts a conflict, without starting the merge, and exit 46 with `… : fusion annulée, rien n'est changé` after aborting a merge that failed. It SHALL NOT resolve a conflict or retry the merge.

#### Scenario: Predicted conflict
- **WHEN** the branch and `main` change the same lines of a baseline specification
- **THEN** the script exits 46, names that file, no merge is in progress, and the branch tip, the worktree and the workspace are as before

#### Scenario: Merge refused by a hook
- **WHEN** the preview predicts no conflict and a hook refuses the merge commit
- **THEN** the script exits 46 with `fusion annulée`, no merge is in progress, and neither the runner nor the finishing script ran

### Requirement: Refusals after a merge say that main is merged
The system SHALL, after a successful merge of `main`, follow every later refusal before the removal with `main est fusionnée dans la branche ; rien d'autre n'est changé`. It SHALL NOT undo the merge commit.

#### Scenario: Later refusal after a merge
- **WHEN** the merge succeeded and the check after it returns 6
- **THEN** the script exits 33 and the next line is `main est fusionnée dans la branche ; rien d'autre n'est changé`

### Requirement: The worktree finish tests and records the merged tip
The system SHALL read the branch tip, its tree and the light decision after the merge and the throwaway-database pass, so that the runner and the finish record cover the merged tree (finish-under-lock design D1, D14). It SHALL NOT write a finish record for a tree other than the merged tip's.

#### Scenario: Record of the merged tree
- **WHEN** a merge was made and the fake runner writes the merged tip's tree into the worktree complete-run fingerprint
- **THEN** the finish record holds the merged tip and its tree, and the fake finishing script receives the token variable

### Requirement: The worktree finish runs the throwaway-database pass under the lock
The system SHALL, when the check before the runner returns 14, run the pass command (default `bash tools/dbtest.sh`, replaceable by `FINISH_WORKTREE_DBTEST`) without argument in the worktree with empty input and the lock token, then check again (design D4). It SHALL NOT write a throwaway-database record itself, nor run the pass when the check did not return 14.

#### Scenario: Green pass
- **WHEN** the check after the merge returns 14, the fake pass exits 0, and the next check returns 0
- **THEN** the output holds `passage dbtest requis pour l'arbre du sommet` then `passage dbtest vert`, the fake pass ran in the worktree with empty input and the lock token, and the runner runs

#### Scenario: No database change
- **WHEN** the check after the merge returns 0
- **THEN** the fake pass is not run

### Requirement: A red or unrecorded throwaway-database pass stops the finish
The system SHALL exit 48 with `passage dbtest rouge (code <n>)` when the pass exits non-zero, and 41 when the check still returns 14 after a green pass. It SHALL NOT remove the worktree, run the runner or the finishing script after either code.

#### Scenario: Red pass
- **WHEN** the fake pass exits 1
- **THEN** the script exits 48 with `passage dbtest rouge (code 1)`, the worktree is still there, and neither the runner nor the finishing script ran

#### Scenario: Record still missing
- **WHEN** the fake pass exits 0 and the next check returns 14 again
- **THEN** the script exits 41 and the worktree is still there

### Requirement: The worktree finish maps the one-change refusal
The system SHALL map code 19 of the check mode, at every check, to 49 with `la fin de branche refuserait : la branche touche un autre change OpenSpec ; rien n'est changé`, list 46, 48 and 49 in its help in step order and 50 as reserved. It SHALL NOT exit 47 or 50, nor give 49 another meaning.

#### Scenario: Another change touched
- **WHEN** the first check returns 19
- **THEN** the script exits 49, nothing is merged and the worktree is still there

#### Scenario: Help
- **WHEN** the help option is given
- **THEN** it lists 46, 48 and 49 in the order of the steps, names 50 as reserved, and does not list 47

### Requirement: An interrupted worktree finish says what it leaves
The system SHALL, on exit codes 129, 130 and 143, abort a merge still in progress that it started and print `finish_worktree : interrompu (code <n>) : <état>` with the state of finish-under-lock design D11, before releasing the lock. It SHALL NOT abort a merge it did not start, remove a worktree, switch or merge in that path.

#### Scenario: Interrupted during the merge
- **WHEN** the script receives an interrupt signal while its merge is in progress
- **THEN** it exits 130, no merge is in progress in the worktree, and the output holds `interrompu (code 130) : fusion de main annulée, rien n'est changé`

#### Scenario: Interrupted after the merge
- **WHEN** the script receives a termination signal during the runner, after a merge
- **THEN** it exits 143 and the output holds `main est fusionnée dans la branche ; rien d'autre n'est changé`

### Requirement: A successful worktree finish prints a verifiable line
The system SHALL, after the finishing script exits 0, print `finish_worktree : terminé : main <court avant> -> <court après>` only when local `main` contains the finished tip, and otherwise `finish_worktree : succès non établi : main ne contient pas le sommet de la branche` (design D12). It SHALL NOT change the exit code passed through, nor print the success line for any other code.

#### Scenario: Finish done
- **WHEN** the fake finishing script merges the branch into `main` and exits 0
- **THEN** the output ends with `finish_worktree : terminé : main` followed by the two short identifiers

#### Scenario: Code 13
- **WHEN** the fake finishing script exits 13
- **THEN** the success line is not printed and the script exits 13

### Requirement: The finish record requires a fingerprint rewritten by this runner
The system SHALL write the finish record only when, besides the existing conditions, the worktree complete-run fingerprint changed status after the marker posed before the runner, and SHALL take the record's tree from the tip compared at code 40 (finish-under-lock design D16). It SHALL NOT write a record from a fingerprint left by an earlier run, nor write or erase a fingerprint itself.

#### Scenario: Older fingerprint and a silent runner
- **WHEN** the worktree fingerprint already holds the tip tree and the fake runner exits 0 without writing it
- **THEN** no record exists, the output holds `empreinte complète non réécrite par ce runner`, and the finishing script runs without the skip

#### Scenario: Tree of the checked tip
- **WHEN** a record is written
- **THEN** its tree field equals the tree of its tip field

### Requirement: No finish record outlives a run that did not launch the finishing script
The system SHALL erase any finish record right after taking the lock, and the exit trap SHALL erase the record this run wrote whenever the finishing script was not launched (finish-under-lock design D16). It SHALL NOT leave a record after codes 30, 31, 32 to 37, 41, 44 or 49, nor after an interruption.

#### Scenario: Second check refuses after a green runner
- **WHEN** the record was written and the second check returns 5
- **THEN** the script exits 32 and no record remains in the common Git folder

#### Scenario: Removal or switch fails
- **WHEN** the record was written and the removal fails, or the switch fails after it
- **THEN** the script exits 30 or 31 and no record remains

#### Scenario: Interrupted after the runner
- **WHEN** the script receives an interrupt signal after writing the record
- **THEN** it exits 130 and no record remains

### Requirement: The worktree finish reads the recorded container verdict in CI mode
The system SHALL, when `FINISH_WORKTREE_CI=1` and the complete path is chosen, read after the check following the merge of `main` the recorded verdict line of the merged tip's tree in the verdict file, in place of the complete runner (local-ci-container design D7b, D8). It SHALL NOT start a container, call `tools/ci_local.sh` or write the verdict file, nor change the light path, nor anything when the variable is absent.

#### Scenario: Variable absent
- **WHEN** the worktree finish runs without `FINISH_WORKTREE_CI`
- **THEN** the complete runner runs in the worktree as before and the verdict file is not read

#### Scenario: CI mode on a spec branch
- **WHEN** the variable is set and the light decision gives the light path
- **THEN** the light pass runs and the verdict file is not read

#### Scenario: The finish never starts the container
- **WHEN** the variable is set, in any outcome of the verdict
- **THEN** the fake Docker command records nothing and the verdict file is unchanged

### Requirement: A merged tree without a green recorded verdict exits 50
The system SHALL exit 50 with the absent phrase of design D8 when the file holds no line for the merged tree, with the red phrase on a `rouge` line and with the unreadable phrase when the file cannot be read; each followed by the merge line when a merge was made, then `lancer : bash tools/ci_local.sh run <branche> (depuis le worktree), puis relancer la fin`. It SHALL NOT fall back to the complete runner nor accept a verdict recorded for another tree.

#### Scenario: Verdict for another tree only
- **WHEN** the file holds a `vert` line for a tree other than the merged tree
- **THEN** the finish exits 50 with `verdict du conteneur absent pour l'arbre fusionné (arbre <court>)` and the command line, and no runner starts

#### Scenario: Merge made by the finish
- **WHEN** the branch did not contain `main`, the finish merged it, and the file holds a `vert` line for the branch's former tip tree
- **THEN** the finish exits 50 with the absent phrase, then `main est fusionnée dans la branche ; rien d'autre n'est changé`, then the command line

#### Scenario: Red verdict
- **WHEN** the file holds a `rouge` line for the merged tree
- **THEN** the finish exits 50 with `verdict du conteneur rouge pour l'arbre fusionné (arbre <court>)` and the command line

#### Scenario: Unreadable verdict file
- **WHEN** the lab data folder cannot be found
- **THEN** the finish exits 50 with `verdict du conteneur illisible (dossier de données introuvable)` and the command line

### Requirement: The Mac pass follows a green recorded verdict
The system SHALL, on a `vert` line for the exact merged tree, print `verdict du conteneur vert pour l'arbre fusionné (arbre <court>, image <clé courte>)`, run `bash tests/run_all.sh --mac` in the worktree as the complete runner is run today, and exit 38 with `passe Mac rouge dans le worktree` when it is red (design D8). It SHALL NOT run the Mac pass after a code 50.

#### Scenario: Red Mac pass
- **WHEN** the verdict is green for the merged tree and the fake Mac pass exits 1
- **THEN** the finish exits 38 with `passe Mac rouge dans le worktree` and writes no record

### Requirement: The finish record in CI mode
The system SHALL write the finish record after a green recorded verdict for the merged tree and a green Mac pass under the existing conditions other than the complete-run fingerprint, with the fields `passage: ci` and `image: <clé>` taken from the verdict line, format 1 (design D8). It SHALL NOT write it after a single green pass.

#### Scenario: Green pair
- **WHEN** the verdict line of the merged tree is `vert`, the Mac pass is green, the tip unchanged and the worktree stable
- **THEN** the record holds the merged tree, `passage: ci` and the image key of the verdict line

### Requirement: The worktree script offers an offline npm install of Mothra's lock
The system SHALL, after creating a worktree whose `mothra/package-lock.json` exists, ask on a terminal whether to run `npm ci --offline` in `mothra/`, run it on yes, and otherwise or without a terminal print the command (mothra-npm-ready design D1). It SHALL NOT run npm without `--offline`, nor any other npm subcommand.

#### Scenario: No terminal
- **WHEN** the lock exists and standard input is not a terminal
- **THEN** the script prints `dépendances npm de Mothra non installées : cd <worktree>/mothra && npm ci --offline` and the fake npm records nothing

#### Scenario: Yes on a terminal
- **WHEN** the lock exists and the answer on a terminal is `o`
- **THEN** the fake npm records exactly `ci --offline` in `mothra/` and the success line is printed

#### Scenario: No lock
- **WHEN** the worktree has no Mothra lock
- **THEN** no question is asked and the fake npm records nothing

### Requirement: A failed offline install keeps the worktree and the exit code
The system SHALL, when `npm ci --offline` fails, print `npm ci --offline en échec (code <n>) : cache local incomplet ? lancer npm ci dans mothra/ avec le réseau, geste de l'auteur`, keep the worktree and exit 0 (design D1, D2). It SHALL NOT retry with the network.

#### Scenario: Incomplete cache
- **WHEN** the fake npm exits 1
- **THEN** the failure line names code 1, the worktree exists and the script exits 0
