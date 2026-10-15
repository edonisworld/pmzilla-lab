# tooling-finish-branch Specification

## Purpose
A branch-finishing script, run by the user in the Terminal, that refuses in a fixed order every state that must not reach `main`, runs the complete test runner, then merges the work branch into `main`, pushes it and deletes the branch, with one exit code per outcome.

## Requirements

### Requirement: One exit code per outcome
The system SHALL give the finishing script the following exit codes, checked in this order before any branch change: 2 usage, 3 no branch to finish, 4 working tree not clean, 5 OpenSpec change not archived, 6 validating evaluation run missing, 7 `main` not up to date, 8 the branch does not contain `main`, 12 `main` checked out in another folder, 1 complete run red; then, after a change, 9 merge impossible and aborted, 10 push refused, 11 branch not deleted, 13 merge done and pushed but the run tree not updated; and 0 when the branch is merged, pushed and deleted and the run tree is updated or absent. Each refusal SHALL be printed on the error output, prefixed with the script name. The help SHALL list the checks in that order with their codes, codes 12 and 13 included. No code SHALL mean two outcomes, and a run tree detached at the tip of `main` SHALL NOT raise code 12.

#### Scenario: Each code
- WHEN the script is exercised on a temporary repository in each refused state
- THEN it exits with the code of that state and prints its key phrase

#### Scenario: Help lists the codes
- **WHEN** the help option is given
- **THEN** the help lists the checks in that order with their codes, codes 12 and 13 included

#### Scenario: Detached run tree
- **WHEN** the run tree exists, detached at the tip of `main`, and every other check passes
- **THEN** code 12 is not raised and the merge proceeds

Source: tests/finish_branch/test_finish_branch.sh (one case per exit code); code 13 and the detached run tree untested until implemented

### Requirement: The finishing script is launched by the user and checks before any change
The system SHALL provide a branch-finishing script that the user launches in the Terminal from the workspace, that takes no argument other than a help option, and that runs its refusal checks in a fixed order before changing any branch. It SHALL exit with a usage code and a usage message on an unknown option or an unexpected argument, and SHALL print its help and exit 0 with the help option. It SHALL NOT be launchable from a Claude Code session (see tooling-permission-guards) and SHALL NOT change any file of the working tree.

#### Scenario: Help
- **WHEN** the script is started with the help option
- **THEN** it prints what it checks and does, exits 0 and changes nothing

#### Scenario: Unexpected argument
- **WHEN** the script is started with an unknown option or an argument
- **THEN** it exits with the usage code and changes nothing

Source: tests/finish_branch/test_finish_branch.sh (aide, code 2); launch ban: tests/settings_deny/test_settings_deny.py (test_script_de_fin_de_branche_interdit_a_la_session)

### Requirement: Refuse when there is no branch to finish
The system SHALL refuse, with its own exit code and a message saying there is no branch to finish, when the script runs outside the repository, on `main`, or on a detached head. It SHALL NOT merge, fetch or push in that case.

#### Scenario: On main
- **WHEN** the current branch is `main`
- **THEN** the script exits with the no-branch code and nothing is merged or pushed

#### Scenario: Detached head
- **WHEN** the head is detached
- **THEN** the script exits with the no-branch code

#### Scenario: Outside the repository
- **WHEN** the script runs from a folder that is not a git repository
- **THEN** the script exits with the no-branch code

Source: tests/finish_branch/test_finish_branch.sh (code 3)

### Requirement: Refuse a dirty working tree
The system SHALL refuse, with its own exit code and a message saying the tree is not clean, when the working tree has a modified, staged or untracked non-ignored file. It SHALL NOT stash, commit, discard or list the content of those files.

#### Scenario: Untracked file
- **WHEN** an untracked file that is not ignored exists
- **THEN** the script exits with the dirty-tree code and the file is untouched

#### Scenario: Ignored file only
- **WHEN** only ignored files are present besides a clean tree
- **THEN** this check passes

#### Scenario: Modified or staged file
- **WHEN** a tracked file is modified or a change is staged
- **THEN** the script exits with the dirty-tree code

Source: tests/finish_branch/test_finish_branch.sh (code 4)

### Requirement: Refuse an unarchived OpenSpec change linked to the branch
The system SHALL refuse, with its own exit code and a message naming each change, when an OpenSpec change linked to the branch is not archived at the branch tip. A change SHALL be linked when its folder exists outside the archive at the tip and either the last segment of the branch name equals the change name or the branch, from its merge base with `main`, changes a file of that folder. When every path changed by the branch is under the OpenSpec folder, the system SHALL treat the branch as a specification branch, SHALL say so, and SHALL NOT require any change to be archived. The system SHALL NOT derive the link from commit messages or from the CHANGELOG.

#### Scenario: Branch named after an open change
- **WHEN** the branch name ends with the name of a change whose folder is not archived and the branch changes code
- **THEN** the script exits with the unarchived-change code and names the change

#### Scenario: Change folder touched
- **WHEN** a branch with another name changes a file of an unarchived change folder and also changes code
- **THEN** the script exits with the unarchived-change code

#### Scenario: Change archived on the branch
- **WHEN** the change folder was moved to the archive on the branch
- **THEN** this check passes

#### Scenario: Specification branch
- **WHEN** every path the branch changes is under the OpenSpec folder
- **THEN** this check passes and the output says the branch is treated as a specification branch

#### Scenario: Open change unrelated to the branch
- **WHEN** an unarchived change exists whose name differs from the last segment of the branch name and whose folder the branch does not touch
- **THEN** this check passes

Source: tests/finish_branch/test_finish_branch.sh (code 5)

### Requirement: Refuse instruction or posture changes without a validating evaluation run
The system SHALL refuse, with its own exit code and a message saying the validating evaluation run is missing, when the branch changes, from its merge base with `main`, the session instructions file, a posture skill, the Critic agent file, the posture vocabulary or the frozen posture memory, and no run record of the evaluation set is complete, validating, not a rejudge, in the default language, with a tested-state object whose content of those paths equals that of the branch tip. The comparison SHALL be by content of those paths, so that a tested state recorded as an unreferenced commit counts. A record whose tested-state object no longer exists SHALL be skipped, and when no record counts for that reason the message SHALL say that the tested state no longer exists and that the set must be run again. When a record counts, the system SHALL print its date and score, without checking regressions. The system SHALL NOT run the evaluation set, SHALL NOT read traces or answers, SHALL NOT count a partial, non-validating, rejudged or other-language run, and SHALL NOT require a run when only slash commands or other agents changed.

#### Scenario: Posture changed, no run
- **WHEN** a posture skill changed on the branch and no record matches
- **THEN** the script exits with the missing-run code

#### Scenario: Matching validating run
- **WHEN** a complete validating run exists on a tested state whose relevant paths equal those of the branch tip
- **THEN** this check passes and the output gives the run date and score

#### Scenario: Non-validating run only
- **WHEN** the only matching record is non-validating or partial
- **THEN** the script exits with the missing-run code

#### Scenario: Later commit on other files
- **WHEN** the validating run was on an earlier commit and later commits changed only other files
- **THEN** this check passes

#### Scenario: Vocabulary changed
- **WHEN** the posture vocabulary or the frozen posture memory changed on the branch and no record matches
- **THEN** the script exits with the missing-run code

#### Scenario: Tested state pruned
- **WHEN** the only matching record names a tested-state object that no longer exists
- **THEN** the script exits with the missing-run code and the message says the tested state no longer exists

#### Scenario: Unreferenced tested state still present
- **WHEN** a validating record names an unreferenced commit that still exists and whose relevant paths equal those of the branch tip
- **THEN** this check passes

#### Scenario: Only commands or other agents changed
- **WHEN** the branch changes slash commands or agents other than Critic, and none of those paths
- **THEN** this check passes without looking for a record

#### Scenario: Instructions or Critic changed
- **WHEN** the session instructions file or the Critic agent file changed on the branch and no record matches
- **THEN** the script exits with the missing-run code

#### Scenario: Rejudged or other-language run only
- **WHEN** the only matching record is a rejudge or a run in another language
- **THEN** the script exits with the missing-run code

#### Scenario: Pruned record beside a valid one
- **WHEN** one record names a tested state that no longer exists and another validating record matches
- **THEN** this check passes

Source: tests/finish_branch/test_finish_branch.sh (code 6 and the records that count)

### Requirement: Refuse when main is not up to date or not contained in the branch
The system SHALL bring local `main` up to date from the remote by fast-forward only, and SHALL refuse with its own exit code when the fetch fails or local `main` diverged from the remote. It SHALL then refuse with another exit code when the branch does not contain the up-to-date `main`, asking the user to bring `main` into the branch first. The system SHALL NOT rebase, reset or force anything.

#### Scenario: Diverged main
- **WHEN** local `main` has commits that the remote does not have and the remote has commits that local `main` does not have
- **THEN** the script exits with the main-not-up-to-date code and nothing is merged

#### Scenario: Branch behind main
- **WHEN** `main` has a commit that the branch does not contain
- **THEN** the script exits with the branch-lacks-main code

#### Scenario: Fetch impossible
- **WHEN** the remote cannot be fetched
- **THEN** the script exits with the main-not-up-to-date code

#### Scenario: Local main behind the remote
- **WHEN** local `main` is an ancestor of the remote `main`
- **THEN** local `main` is fast-forwarded to the remote one before the containment check

Source: tests/finish_branch/test_finish_branch.sh (codes 7 and 8)

### Requirement: Run the complete test runner before merging
The system SHALL run the complete test runner (no suite filter, without the variable reserved to git commit nor the owner bypass variable) on the branch tip once every refusal check passed, and SHALL refuse with the tests-red exit code, merging nothing, when the run fails. It SHALL NOT run a targeted or filtered run instead.

#### Scenario: Red run
- **WHEN** the complete run fails
- **THEN** the script exits with the tests-red code and `main` is unchanged

#### Scenario: Green run
- **WHEN** the complete run passes
- **THEN** the script goes on to the merge

Source: tests/finish_branch/test_finish_branch.sh (code 1)

### Requirement: Merge, push, delete and report
The system SHALL, after a green complete run, merge the branch into `main` without fast-forward and without editing the message, push `main`, delete the local branch with the safe deletion, delete the remote branch when it exists, update the run tree as the requirement "Update the run tree after the merge is pushed" states, and print the list of what it did, exiting 0. On a merge failure it SHALL abort the merge, return to the branch and exit with its own code; on a push failure it SHALL exit with its own code and print the command to retry the push and the command to undo the local merge; on a branch deletion failure after a successful push it SHALL exit with its own code and say the work is merged. After a failed step it SHALL NOT go on to a later step, the run-tree update included. The system SHALL NOT force-push, use the forced branch deletion, bypass hooks, resolve conflicts, or reset or clean the run tree.

#### Scenario: Success
- **WHEN** every check passes and the run is green
- **THEN** `main` holds a merge commit of the branch, the remote `main` equals it, the branch no longer exists locally or remotely, the run tree is at the new tip of `main`, the output lists merge, push, deletion and update, and the exit code is 0

#### Scenario: Merge conflict
- **WHEN** the merge cannot complete
- **THEN** the merge is aborted, the current branch is the work branch again, and the script exits with the merge-failed code

#### Scenario: Push refused
- **WHEN** the remote refuses the push
- **THEN** the script exits with the push-failed code, prints the retry and undo commands, does not delete the branch and does not update the run tree

#### Scenario: Remote branch deletion refused
- **WHEN** the remote refuses the deletion of the branch after the merge and push
- **THEN** the script exits with the branch-not-deleted code and says the work is merged

#### Scenario: Forbidden commands
- **WHEN** the script text is scanned outside comments
- **THEN** it contains no forced push, forced deletion, rebase, hook bypass, owner bypass variable, evaluation-set launch, reset or clean of the run tree

Source: tests/finish_branch/test_finish_branch.sh (codes 0, 9, 10, 11, forbidden commands); the run-tree update untested until implemented

### Requirement: The finishing script is testable without the real repository
The system SHALL let tests replace the test runner command and the folder of evaluation run records through environment variables, so that a shell suite can exercise every exit code on a temporary repository with a temporary bare remote. The system SHALL NOT read the real evaluation records or run the real runner when those variables are set.

#### Scenario: Fake runner
- **WHEN** the runner override points to a script that fails
- **THEN** the finishing script exits with the tests-red code and the temporary `main` is unchanged

Source: tests/finish_branch/test_finish_branch.sh

### Requirement: Update the run tree after the merge is pushed
The system SHALL, once `main` is pushed and the branch deleted, update the run tree through the run-tree script. A missing run tree SHALL be stated in one line, with exit 0. A refused or postponed update, or unprepared dependencies, SHALL give exit 13 with the key phrases of design D4. It SHALL NOT update before the push, nor reset, clean or recreate the run tree, nor touch the watch lock or a run marker. Untested until implemented.

#### Scenario: Local change in the run tree
- **WHEN** the merge and push succeed and the run tree holds a modified file
- **THEN** the remote `main` holds the merge, the run tree and its file are unchanged, the output says the merge is done and pushed and gives the update command, and the exit code is 13

#### Scenario: Watch run in progress
- **WHEN** the merge and push succeed while the watch lock is held by a live process
- **THEN** the exit code is 13, the cause says the update is postponed, and the lock is unchanged

#### Scenario: No run tree
- **WHEN** the merge and push succeed and no run tree exists
- **THEN** the output says there is nothing to update and the exit code is 0

#### Scenario: Update done
- **WHEN** the merge and push succeed and the update moves the run tree
- **THEN** the output lists the update, then the library-server reminder of design D3, and the exit code is 0
