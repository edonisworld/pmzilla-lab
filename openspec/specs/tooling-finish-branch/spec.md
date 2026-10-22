# tooling-finish-branch Specification

## Purpose
A branch-finishing script, run by the user in the Terminal, that refuses in a fixed order every state that must not reach `main`, runs the complete test runner, then merges the work branch into `main`, pushes it and deletes the branch, with one exit code per outcome.

## Requirements

### Requirement: One exit code per outcome
The system SHALL check, in this order before any branch change: 2 usage, 15 another finish in progress (normal run only, multi-session-piloting design D5), 17 morning state not verified (normal run only, morning-guard design D6), 3 no branch, 4 tree not clean, 19 another active OpenSpec change touched (finish-under-lock design D6), 5 change not archived, 6 evaluation run missing, 14 throwaway-database run missing, 7 `main` not up to date, 8 branch lacks `main`, 12 `main` open elsewhere, 1 run red; then 9 merge aborted, 10 push refused, 11 branch not deleted, 13 run tree not updated, 0 done. Refusals SHALL go to the error output with the script name, listed in that order by the help. No code SHALL mean two outcomes.

#### Scenario: Each code
- WHEN the script is exercised on a temporary repository in each refused state
- THEN it exits with the code of that state and prints its key phrase

#### Scenario: Help lists the codes
- **WHEN** the help option is given
- **THEN** the help lists the checks in that order with their codes, codes 12, 13, 14, 15, 17 and 19 included, 14 between 6 and 7, 15 right after 2, 17 right after 15, 19 between 4 and 5

#### Scenario: Detached run tree
- **WHEN** the run tree exists, detached at the tip of `main`, and every other check passes
- **THEN** code 12 is not raised and the merge proceeds

#### Scenario: Code 14 before code 7
- **WHEN** a branch changes database code without a record and the fetch of the remote would fail
- **THEN** the script exits 14, not 7

#### Scenario: Code 15 before code 3
- **WHEN** another live finish holds the lock and the script runs on `main`
- **THEN** the script exits 15, not 3

#### Scenario: Code 17 before code 3
- **WHEN** the guard command replaced by the suite exits 1 and the script runs on `main`
- **THEN** the script exits 17, not 3

#### Scenario: Code 19 before code 5
- **WHEN** a code branch touches another active change and holds its own unarchived change
- **THEN** the script exits 19, not 5

### Requirement: The finishing script is launched by the user and checks before any change
The system SHALL provide a branch-finishing script that the user launches in the Terminal from the workspace, that takes no argument other than a help option or the check option followed by one branch (safe-branch-finish design D5), and that runs its refusal checks in a fixed order before changing any branch. It SHALL exit with a usage code and a usage message on an unknown option, an unexpected argument, or the check option without exactly one branch, and SHALL print its help and exit 0 with the help option. It SHALL NOT be launchable from a Claude Code session, check mode included (see tooling-permission-guards), and SHALL NOT change any file of the working tree.

#### Scenario: Help
- **WHEN** the script is started with the help option
- **THEN** it prints what it checks and does, the check option included, exits 0 and changes nothing

#### Scenario: Unexpected argument
- **WHEN** the script is started with an unknown option or an argument
- **THEN** it exits with the usage code and changes nothing

#### Scenario: Check option without a branch
- **WHEN** the script is started with the check option and no branch, or with two branches
- **THEN** it exits with the usage code and changes nothing

Source: tests/finish_branch/test_finish_branch.sh (aide, code 2); launch ban: tests/settings_deny/test_settings_deny.py (test_script_de_fin_de_branche_interdit_a_la_session); the check option untested until implemented

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
The system SHALL refuse with its own exit code, saying the validating evaluation run is missing, when the branch changes from its merge base a path of the shared list of evaluated paths and no record counts. A record SHALL count when it is complete, validating, not a rejudge, in the default language, and its fingerprint of the evaluated files equals the one computed from the branch tip (posture-evals-on-branch-tip design D4). The system SHALL NOT run the evaluation set, read traces or answers, or require a run when no listed path changed.

#### Scenario: Posture changed, no run
- **WHEN** a posture skill changed on the branch and no record matches
- **THEN** the script exits with the missing-run code

#### Scenario: Matching fingerprint
- **WHEN** a complete validating record holds the fingerprint of the branch tip
- **THEN** this check passes and the output gives the run date and score followed by `(empreinte des fichiers évalués)`

#### Scenario: Matching fingerprint, tested state pruned
- **WHEN** the only matching record has the tip's fingerprint and names a tested-state object that no longer exists
- **THEN** this check passes

#### Scenario: Other fingerprint
- **WHEN** the only fingerprinted record holds a fingerprint other than the tip's
- **THEN** the script exits with the missing-run code

#### Scenario: Matching validating run
- **WHEN** a complete validating record without a fingerprint names a tested state whose listed paths equal those of the branch tip
- **THEN** this check passes and the output gives the run date and score

#### Scenario: Tested state pruned
- **WHEN** the only matching record has no fingerprint and names a tested-state object that no longer exists
- **THEN** the script exits with the missing-run code and the message says the tested state no longer exists

#### Scenario: Unreferenced tested state still present
- **WHEN** a validating record without a fingerprint names an unreferenced commit that still exists and whose listed paths equal those of the branch tip
- **THEN** this check passes

#### Scenario: Pruned record beside a valid one
- **WHEN** one record without a fingerprint names a tested state that no longer exists and another validating record matches
- **THEN** this check passes

#### Scenario: Non-validating run only
- **WHEN** the only matching record is non-validating or partial
- **THEN** the script exits with the missing-run code

#### Scenario: Later commit on other files
- **WHEN** the validating run was on an earlier commit and later commits changed only other files
- **THEN** this check passes

#### Scenario: Vocabulary changed
- **WHEN** the posture vocabulary or the frozen posture memory changed on the branch and no record matches
- **THEN** the script exits with the missing-run code

#### Scenario: Only commands or other agents changed
- **WHEN** the branch changes slash commands or agents other than Critic, and none of the listed paths
- **THEN** this check passes without looking for a record

#### Scenario: Instructions or Critic changed
- **WHEN** the session instructions file or the Critic agent file changed on the branch and no record matches
- **THEN** the script exits with the missing-run code

#### Scenario: Rejudged or other-language run only
- **WHEN** the only matching record is a rejudge or a run in another language
- **THEN** the script exits with the missing-run code

Source: tests/finish_branch/test_finish_branch.sh (code 6 and the records that count); the fingerprint untested until implemented (task 3.2)

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
The system SHALL, once every refusal check passed, run the complete test runner on the branch tip (no filter, without the variable reserved to git commit nor the owner bypass variable), unless a finish record matches as test-speed design D7 states, and SHALL refuse with the tests-red code, merging nothing, when the run fails. It SHALL NOT run a targeted or filtered run instead, nor skip the run without a matching record.

#### Scenario: Red run
- **WHEN** the complete run fails
- **THEN** the script exits with the tests-red code and `main` is unchanged

#### Scenario: Green run
- **WHEN** the complete run passes
- **THEN** the script goes on to the merge

#### Scenario: Launched by hand
- **WHEN** the script runs without the token variable of test-speed design D6, a valid finish record being present
- **THEN** the fake runner is called, the record is neither read nor deleted, and the output holds no reason line

Source: tests/finish_branch/test_finish_branch.sh (code 1); the launch without token untested until implemented (task 2.3)

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
The system SHALL, once `main` is pushed and the branch deleted, update the run tree through the run-tree script. A missing run tree SHALL be stated in one line, with exit 0. A refused or postponed update, or unprepared dependencies, SHALL give exit 13 with the key phrases of design D4. It SHALL NOT update before the push, nor reset, clean or recreate the run tree, nor touch the watch lock or a run marker.

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

### Requirement: Check-only mode for a named branch
The system SHALL give the finishing script a check-only mode that runs, for the named branch, the refusals 3, 4, 5, 6, 14, 7, 8 and 12 in that order (safe-branch-finish D6, test-speed-2 D6), with the codes and key phrases of the normal run, one implementation per check, and exits 0 with the success line of design D6. It SHALL NOT merge, push, delete a branch, move `main`, run the test runner, update the run tree, switch a branch, write a fingerprint, or change a file.

#### Scenario: Unarchived linked change
- **WHEN** the check mode runs from the workspace on `main` for a branch that changes code and holds an unarchived change named after its last segment
- **THEN** the exit code is 5, the change is named, and the workspace, `main` and the branch are unchanged

#### Scenario: All checks pass
- **WHEN** the check mode runs for a branch that every check accepts
- **THEN** the exit code is 0, the output holds the success line, the fake runner records no call, and nothing is merged, pushed or deleted

#### Scenario: Main open in another folder
- **WHEN** the check mode runs from a folder while `main` is checked out in another worktree
- **THEN** the exit code is 12 and nothing changes

#### Scenario: Branch to finish
- **WHEN** the named branch is `main`, a `spike/*` branch, or does not exist locally
- **THEN** the exit code is 3

#### Scenario: Throwaway-database run missing
- **WHEN** the named branch changes a migration and no record holds its tip tree
- **THEN** the exit code is 14 and nothing changes

Source: tests/finish_branch/test_finish_branch.sh (check mode); code 14 untested until implemented (task 2.6)

### Requirement: The check mode never moves main
The system SHALL, in check mode, fetch the remote `main` and refuse with the main-not-up-to-date code on a failed fetch or a divergence, SHALL accept a local `main` behind the remote without moving it, and SHALL refuse with the branch-lacks-main code when the branch does not contain the most advanced of local and remote `main`. It SHALL NOT fast-forward, reset or update the reference of local `main`, since the check runs from a workspace where `main` is checked out.

#### Scenario: Local main behind the remote
- **WHEN** the check mode runs while local `main` is an ancestor of the remote `main` and the branch contains the remote `main`
- **THEN** the check passes and local `main` still points to its former commit

#### Scenario: Branch lacking the remote main
- **WHEN** local `main` is behind the remote and the branch contains local `main` but not the remote `main`
- **THEN** the exit code is 8 and local `main` is unchanged

#### Scenario: Diverged main in check mode
- **WHEN** local `main` and the remote `main` have each a commit the other lacks
- **THEN** the exit code is 7 and nothing changes

Source: untested until implemented (tests/finish_branch/test_finish_branch.sh, task 3.1)

### Requirement: The finishing script skips its complete run on a matching finish record
The system SHALL, in the normal run with the token variable set, read and then delete the finish record, and skip the complete runner only when every condition of test-speed design D7 holds (the setting of D5 included), printing the skip line of D11. On the first condition that fails it SHALL print the no-skip line with that reason and run the complete runner as before. It SHALL NOT keep the record after reading it, nor read it in check mode.

#### Scenario: Matching record
- **WHEN** the setting `FINISH_WORKTREE_ALLOW_SKIP` is `1`, the force variable is unset and the record matches the token, the branch, the tip, the tree, the predicted merged tree and the environment signature
- **THEN** the fake runner records no call, the output holds `second lancement sauté`, the record no longer exists, and the merge and push proceed

#### Scenario: Other tip
- **WHEN** the setting is `1` and the record names a commit other than the branch tip
- **THEN** the output holds `second lancement nécessaire : autre sommet`, the fake runner is called, and the record no longer exists

#### Scenario: Wrong token or no record
- **WHEN** the token differs, or no record exists while the variable is set
- **THEN** the reason is `jeton différent` or `fiche de fin absente` and the fake runner is called

#### Scenario: Environment changed
- **WHEN** the environment signature computed now differs from the record's
- **THEN** the reason is `environnement différent` and the fake runner is called

#### Scenario: Check mode
- **WHEN** the check mode runs while a record exists
- **THEN** the record is unchanged

Source: untested until implemented (tests/finish_branch/test_finish_branch.sh, task 2.3)

### Requirement: A skipped run leaves the pushed tree with a complete-run fingerprint
The system SHALL, when it skips the complete runner, write the record's tree into the workspace complete-run fingerprint just before the merge (test-speed design D10), so the pre-push hook accepts the push without a run. If the merge commit's tree differs from the record's, it SHALL erase that fingerprint and print the backstop line of D11. It SHALL NOT write the targeted fingerprint, change a hook, or give the skip an exit code of its own.

#### Scenario: Skipped run and push
- **WHEN** the setting is `1`, the run is skipped, the merge is made and `main` is pushed through a pre-push hook with a fake runner
- **THEN** the hook's fake runner records no call and the complete-run fingerprint equals the tree of the merge commit

#### Scenario: Backstop
- **WHEN** the merge commit's tree differs from the record's tree
- **THEN** the fingerprint is erased, the error output holds `le hook pre-push relancera le runner complet`, and the pre-push hook runs its runner before accepting

#### Scenario: Codes unchanged
- **WHEN** the help option is given
- **THEN** it lists exactly the codes of the requirement "One exit code per outcome", and no outcome of the skip exits with a code of its own

Source: tests/finish_branch/test_finish_branch.sh

### Requirement: A variable can force the second complete run and never skip it
The system SHALL run the finishing script's complete runner whenever the force variable of test-speed design D16 is set to a non-empty value, whatever the value, still reading and deleting the finish record when the token variable is set, and SHALL document that variable in the guide section on finishing a branch. It SHALL NOT let any value or the absence of that variable skip a run, write a fingerprint itself, or change an exit code.

#### Scenario: Forced despite a matching record
- **WHEN** the token variable is set, the setting is `1`, the record matches in every respect and the force variable is `1`
- **THEN** the output holds `second lancement nécessaire : relance forcée` and no skip line, the fake runner is called, the record no longer exists, and the script wrote no complete-run fingerprint itself

#### Scenario: Any value forces
- **WHEN** the force variable is `0` and the record matches in every respect
- **THEN** the fake runner is called and the reason is `relance forcée`

#### Scenario: Unset or empty changes nothing
- **WHEN** the setting is `1`, the force variable is empty and the record matches in every respect
- **THEN** the run is skipped exactly as without the variable

#### Scenario: Launched by hand with the variable
- **WHEN** the force variable is set and the token variable is not
- **THEN** the fake runner is called, the output holds no reason line, and a record present is neither read nor deleted

#### Scenario: Documented
- **WHEN** the guide section on finishing a branch from its worktree and the script's header comment are read
- **THEN** both name `FINISH_BRANCH_FORCE_RUN` and say that it can only force the complete run

Source: untested until implemented (tests/finish_branch/test_finish_branch.sh, tasks 2.3 and 2.6; guide, task 2.5)

### Requirement: The skip is allowed unless FINISH_WORKTREE_ALLOW_SKIP disables it
The system SHALL, with the token variable set and the force variable unset or empty, allow the skip when `FINISH_WORKTREE_ALLOW_SKIP` is absent, empty or exactly `1`; for any other value it SHALL give the reason `saut non autorisé (réglage désactivé)` and run the complete runner, still reading and deleting the record. The force variable keeps priority. It SHALL NOT print `réglage absent` nor add or change an exit code, and SHALL document the setting in the header and the guide.

#### Scenario: Setting absent, valid record
- **WHEN** the token variable is set, the record matches in every respect and the setting is absent
- **THEN** the output holds `second lancement sauté`, the fake runner records no call, and the record no longer exists

#### Scenario: Setting empty
- **WHEN** the setting is empty and the record matches in every respect
- **THEN** the run is skipped as with the setting absent

#### Scenario: Any other value
- **WHEN** the setting is `oui`, `0` or `11` and the record matches
- **THEN** the output holds `second lancement nécessaire : saut non autorisé (réglage désactivé)` and no skip line, the fake runner is called once, and the record no longer exists

#### Scenario: Reason recorded
- **WHEN** the setting is `0` and the durations-file variable names a temporary file
- **THEN** the line is of kind `fin-relance` with the reason `saut non autorisé (réglage désactivé)`

#### Scenario: Force variable first
- **WHEN** the force variable is `1`, the setting is absent or `0`, and the record matches
- **THEN** the reason is `relance forcée`, the fake runner is called, and no skip line is printed

#### Scenario: Setting at 1
- **WHEN** the setting is `1` and the record matches in every respect
- **THEN** the run is skipped as before

#### Scenario: Former phrase gone
- **WHEN** the script runs in each case above
- **THEN** no output holds `réglage absent`

#### Scenario: Documented
- **WHEN** the script header and the guide section on finishing a branch from its worktree are read
- **THEN** both name `FINISH_WORKTREE_ALLOW_SKIP`, say that absent, empty or `1` allow the skip and that `0` turns it off, and name the priority of `FINISH_BRANCH_FORCE_RUN`

Source: tests/finish_branch/test_finish_branch.sh (untested until implemented, task 2.1 of skip-default-on)

### Requirement: Each skip and each second run is recorded with its reason
The system SHALL, when the finishing script runs with the token variable set, append to the durations file of test-speed design D4 one line for the skip or the second run, with the kind, verdict and reason of D17. It SHALL NOT write a branch, commit, tree, token, signature or path into that line, write a line on a launch by hand or in check mode, nor change the finish's outcome when the line cannot be written.

#### Scenario: Skip recorded
- **WHEN** the setting is `1`, the record matches and the durations-file variable names a temporary file
- **THEN** that file holds one line of kind `fin-saut`, verdict `sauté` and reason `arbre déjà testé dans le worktree`, and no line holds the branch name, the tip, the tree or the token

#### Scenario: Second run recorded
- **WHEN** the reason is `autre sommet` and the fake runner exits 0, then, in another case, exits 1
- **THEN** the line is of kind `fin-relance` with the reason `autre sommet`, a duration, and the verdict `ok`, then `échec` with the script exiting 1 as before

#### Scenario: Forced run recorded
- **WHEN** the force variable is set with the token variable
- **THEN** the line is of kind `fin-relance` with the reason `relance forcée`

#### Scenario: Launch by hand or check mode
- **WHEN** the script runs without the token variable, or in check mode, with the durations-file variable set
- **THEN** the durations file gains no line

#### Scenario: Tests never write into the lab data folder
- **WHEN** the runner variable of the script is set and the durations-file variable is not
- **THEN** no durations file is written and the finish ends as before

#### Scenario: Line not written
- **WHEN** the durations-file variable names a file in a folder that cannot be written, the setting is `1` and the record matches
- **THEN** the output holds `bilan de fin non enregistré (écriture impossible)`, the run is skipped, and the merge, push and exit code are as without the line

Source: untested until implemented (tests/finish_branch/test_finish_branch.sh, task 2.6)

### Requirement: Refuse database code changes without a green throwaway-database run
The system SHALL, when the branch changes from its merge base a path of the database list of test-speed-2 design D4, refuse with code 14 and the lines of D29 unless the throwaway-database record holds the tree of the tip, in the normal run and in check mode; a match SHALL print the found line of D29. It SHALL NOT read the record when no such path changed, accept a record of another tree, run the throwaway-database script, or offer a way to waive the check.

#### Scenario: Migration changed, no record
- **WHEN** the branch adds a migration file and the common Git folder holds no record
- **THEN** the script exits 14 with `passage dbtest vert absent`, nothing is merged, and the fake runner records no call

#### Scenario: Record of another tree
- **WHEN** the branch changes the database layer and the record holds only an older tree of the branch
- **THEN** the script exits 14

#### Scenario: Record of the tip tree
- **WHEN** the record holds the tree of the tip, written from a worktree of the branch
- **THEN** the output holds `passage dbtest vert trouvé pour l'arbre du sommet` and the finish goes on

#### Scenario: No database path changed
- **WHEN** the branch changes only other code and no record exists
- **THEN** no line about the throwaway-database run is printed and the finish goes on

#### Scenario: Check mode
- **WHEN** the check mode runs for a branch that changes a database test file without a record
- **THEN** it exits 14 and changes nothing

Source: untested until implemented (tests/finish_branch/test_finish_branch.sh, task 2.6)

### Requirement: The finishing script holds the finish lock for its whole run
The system SHALL make the finishing script, in its normal run and right after its usage check, take the finish lock of multi-session-piloting design D5, unless the caller's lock token equals the lock's token, and hold it until it exits, passing the token to every command it runs. A live lock of another token SHALL give exit 15 with the phrase of D5, nothing changed. It SHALL NOT wait for the lock or print the token.

#### Scenario: Another finish running
- **WHEN** a lock of a live process with another token exists and the script starts on a work branch
- **THEN** it exits 15 with `finish_branch : une autre fin de branche est en cours (<branche>, depuis HH:MM)`, the fake runner records no call, and the lock and the branches are unchanged

#### Scenario: Lock held and released
- **WHEN** the script runs to its end with a fake runner that records whether the lock exists and the token it receives
- **THEN** the lock existed during the runner, the runner received the lock token, and no lock remains afterwards

#### Scenario: Launched by the worktree-finishing script
- **WHEN** the caller's token equals the token of the lock present
- **THEN** the script takes no second lock, is not refused, and leaves the lock in place on exit

### Requirement: The finishing script releases only its own lock and takes over a stale one
The system SHALL make the finishing script, on exit and whatever the outcome, remove the finish lock only when its token is its own, and report a stale lock (multi-session-piloting design D6) with `verrou de fin périmé, repris` before removing and replacing it. The check mode SHALL neither take, read nor remove the lock. It SHALL NOT remove a live lock of another token.

#### Scenario: Released on failure
- **WHEN** the fake runner exits 1
- **THEN** the script exits 1 and no lock remains

#### Scenario: Stale lock
- **WHEN** the lock names a process that no longer exists
- **THEN** the output holds `verrou de fin périmé, repris` and the finish goes on under a new lock

#### Scenario: Check mode
- **WHEN** the check mode runs while a live lock of another token exists
- **THEN** it does not exit 15 for that reason and the lock is unchanged

### Requirement: The finishing script refuses inside the morning window before the morning state is verified
The system SHALL, in the normal run, after the usage check and the finish lock and before refusal 3, run the morning-state check and refuse with code 17 and the lines of morning-guard design D6 when it does not allow; the help SHALL list 17 there, no other code changing meaning. It SHALL NOT run this check in check mode, SHALL NOT merge, push, fetch, run a runner or change a file on refusal, and SHALL NOT offer any way to waive it.

#### Scenario: Inside the window, morning not verified
- **WHEN** the guard command replaced by the suite exits 1 and every other check would pass
- **THEN** the exit code is 17, the error output holds `finish_branch : fenêtre du matin, état du matin non vérifié`, the guard's line and `relancer quand l'état du matin est vérifié : bash tools/morning_state.sh check`, the fake runner records no call, and `main` and the branch are unchanged

#### Scenario: Morning verified
- **WHEN** the guard command exits 0
- **THEN** the finish goes on to refusal 3 and its outcome is as without the guard

#### Scenario: Check mode
- **WHEN** the check mode runs for a branch while the guard command would exit 1
- **THEN** the guard command is not called and the check mode's outcome is unchanged

#### Scenario: Help
- **WHEN** the help option is given
- **THEN** the help lists code 17 after the usage code and the finish-lock code, and before code 3

### Requirement: The finishing script records the validated tree of main
The system SHALL, in the normal run, after a successful push of `main`, append the tree of the new tip of `main` to the main-validation record, with the kind of the run that validated it, and print the line of light-spec-finish design D8. It SHALL NOT write the record in check mode, after a red run, a refusal or codes 9 and 10, nor write a branch, commit, path or token into it.

#### Scenario: Complete finish recorded
- **WHEN** a branch that changes code is finished with a green fake complete runner
- **THEN** the record holds the tree of the new tip of `main` with the kind `complet` and the output holds `arbre de main enregistré comme validé (complet)`

#### Scenario: Push refused
- **WHEN** the remote refuses the push
- **THEN** the script exits 10 and the record gains no line

#### Scenario: Check mode
- **WHEN** the check mode runs for a branch that every check accepts
- **THEN** the record is unchanged

### Requirement: The record holds the date and the environment signature
The system SHALL write each record line with the tree, the kind, the UTC date of the write and the environment signature of light-spec-finish design D3b computed at the write, or `inconnue` when it cannot be computed, the finish keeping its outcome and code. It SHALL NOT write a name, branch, commit, path or version into it.

#### Scenario: Line content
- **WHEN** a finish records a tree
- **THEN** the line holds four tab-separated columns, the third a `YYYY-MM-DD` date and the fourth 64 lowercase hexadecimal characters equal to the output of `bash tools/finish_env.sh --main-signature`

#### Scenario: Signature impossible at the write
- **WHEN** a finish records a tree while `uv` is absent from its `PATH`
- **THEN** the fourth column is `inconnue` and the exit code is 0

### Requirement: The environment signature has one implementation
The system SHALL compute the environment signature (SHA-256 of the versions of python3, uv, git, bash and of the lab folders, design D3b) only through the option `--main-signature` of the environment script: 64 hexadecimal characters and exit 0, or `absent:<composant>` and exit 1, never a path or a version. The finishing scripts, the helper and the pre-push hook SHALL use that option. No variable SHALL set the signature.

#### Scenario: Stable signature
- **WHEN** the option runs twice with the same `PATH` and lab folders
- **THEN** both runs print the same 64 hexadecimal characters

#### Scenario: Version change
- **WHEN** the fake `uv` of the test `PATH` prints another version
- **THEN** the option prints another signature

#### Scenario: Tool absent
- **WHEN** `uv` is absent from the `PATH`
- **THEN** the option prints `absent:uv` and exits 1

### Requirement: A validation of main expires
The system SHALL treat a recorded tree as not validated for the light path when its date is more than 7 days before the day of the clock, and run the complete runner with the reason `validation de main expirée`. It SHALL NOT take the light path on an expired line, nor on a malformed or future date.

#### Scenario: Expired after 7 days
- **WHEN** the record line for the tree of `main` is 8 days old (injectable clock) and every other light condition holds
- **THEN** the fake complete runner is called and the output holds `runner complet nécessaire : validation de main expirée`

#### Scenario: Still valid at 6 days
- **WHEN** the line is 6 days old with an unchanged signature
- **THEN** the light path is taken

#### Scenario: Still valid at exactly 7 days
- **WHEN** the line is exactly 7 days old with an unchanged signature (the limit confirmed by the author on 2026-10-18: valid at 7 days, expired at 8)
- **THEN** the light path is taken

### Requirement: A changed or unreadable environment gives the complete runner
The system SHALL recompute the environment signature at the light decision, after the expiry check, and run the complete runner with the reason of light-spec-finish design D3 when the recorded signature is missing, when the current one cannot be computed, or when they differ. It SHALL NOT compare the blob hash of the components declaration (question Q9).

#### Scenario: Same signature
- **WHEN** the line is fresh and its signature equals the current one
- **THEN** the light path is taken

#### Scenario: Signature changed
- **WHEN** the line is fresh and the fake `uv` now prints another version
- **THEN** the fake complete runner is called and the output holds `runner complet nécessaire : environnement changé depuis la validation`

#### Scenario: Tool absent at the decision
- **WHEN** the line is fresh and `uv` is absent from the `PATH`
- **THEN** the fake complete runner is called and the output holds `runner complet nécessaire : signature d'environnement impossible : uv absent ou illisible`

#### Scenario: No signature in the line
- **WHEN** the line's fourth column is `inconnue` or a 40-character blob hash
- **THEN** the fake complete runner is called and the output holds `runner complet nécessaire : signature d'environnement absente de la validation`

### Requirement: A failed record write changes nothing
The system SHALL, when the main-validation record cannot be written, print `arbre de main non enregistré (écriture impossible)` and keep the outcome and the exit code of the finish.

#### Scenario: Unwritable record
- **WHEN** the record cannot be written after a successful push
- **THEN** the output holds that line and the exit code is 0

### Requirement: A specification branch on a validated main takes the light path
The system SHALL, in the normal run, replace the complete runner by the light run of light-spec-finish design D4 only when the light decision of D3 holds (OpenSpec files only, validated `main`, force variable unset or empty), and print the light-path line of D8. It SHALL NOT combine the light path with the skip of the second complete run, nor take it in check mode. Untested until implemented (suite `finish_branch`).

#### Scenario: Light path
- **WHEN** the branch changes only files under the OpenSpec folder and the record holds the tree of `main`
- **THEN** the fake validation and the fake light runner are called, the fake complete runner records no call, the merge and push happen, and the record holds the new tree with the kind `allégé`

#### Scenario: Check mode
- **WHEN** the check mode runs for such a branch
- **THEN** neither the validation nor the light runner is called and the record is unchanged

### Requirement: The light path is never taken outside the OpenSpec folder
The system SHALL run the complete runner for a branch that changes, adds, deletes or renames any path outside the OpenSpec folder, merge commits included, or that holds a symbolic link or submodule under that folder. It SHALL print `runner complet nécessaire : <raison>` with the reason of light-spec-finish design D3 when check 5 called the branch a specification branch.

#### Scenario: Path outside the OpenSpec folder
- **WHEN** the branch, the record holding the tree of `main`, also modifies a tool, adds a root file, deletes a file outside the folder, renames a file into or out of the folder, adds a root file named `openspec` or a folder `openspecs/`, or holds a merge commit bringing a file outside the folder
- **THEN** in each case the fake complete runner is called once and neither the light runner nor the validation is called

#### Scenario: Symbolic link under the folder
- **WHEN** the branch adds a symbolic link under the OpenSpec folder and the record holds the tree of `main`
- **THEN** the fake complete runner is called and the output holds `runner complet nécessaire : lien symbolique ou sous-module sous openspec/`

### Requirement: The light path is never taken without the record or with the force variable
The system SHALL run the complete runner when the main-validation record does not hold the tree of the up-to-date `main`, and whenever the force variable is set to a non-empty value, whatever the value. No variable SHALL make the light path apply.

#### Scenario: No validated main
- **WHEN** the branch changes only OpenSpec files and the record is absent, lacks the tree of `main`, or holds only the tree of a `main` that a direct commit has since moved
- **THEN** the fake complete runner is called and the output holds `runner complet nécessaire : arbre de main non validé`

#### Scenario: Force variable
- **WHEN** the force variable is `1` or `0` and every other condition holds
- **THEN** the fake complete runner is called and the output holds `runner complet nécessaire : relance forcée`

### Requirement: A forced light pass is marked and never opens the light path
The system SHALL write the kind `allégé-forcé`, instead of `allégé`, in the main-validation record when a green light pass ran with `FINISH_BRANCH_LIGHT_RUNNER` or `FINISH_BRANCH_VALIDATE` non-empty. A line of that kind SHALL never open the light path to the next branch or to the pre-push hook, and SHALL NOT count among the manual light finishes that condition idea #380. Tested (suites `finish_branch` and `hooks`).

#### Scenario: Fake runners set
- **WHEN** a light finish runs with the fake light runner and the fake validation set
- **THEN** the recorded line has the kind `allégé-forcé` and the output holds `arbre de main enregistré comme validé (allégé-forcé)`

#### Scenario: Next branch after a forced pass
- **WHEN** the record holds a fresh line of kind `allégé-forcé` for the tree of `main` and a specification branch is finished
- **THEN** the fake complete runner is called and the output holds `runner complet nécessaire : validation de main forcée`

#### Scenario: Pre-push hook
- **WHEN** the first parent of the pushed commit is recorded with the kind `allégé-forcé`
- **THEN** the hook runs its runner instead of accepting the light fingerprint

### Requirement: A red light run merges nothing
The system SHALL, on the light path, exit 18 with the phrase of light-spec-finish design D8 when the validation fails, before the light runner, and exit 1 with the existing tests-red phrase and `(passage allégé)` when a selected suite fails, merging nothing. A missing or non-executable validation command SHALL give the complete runner with the reason `openspec introuvable`. The help SHALL list 18 after 12 and before 1.

#### Scenario: Validation red
- **WHEN** the fake validation exits 1 on the light path
- **THEN** the script exits 18 with `openspec validate --strict en échec, rien n'est fusionné`, no runner is called and `main` is unchanged

#### Scenario: Light suites red
- **WHEN** the fake light runner exits 1
- **THEN** the script exits 1 with `tests en échec, rien n'est fusionné` and `(passage allégé)`, and `main` is unchanged

#### Scenario: Validation command missing
- **WHEN** the fake validation exits 127
- **THEN** the fake complete runner is called and the output holds `runner complet nécessaire : openspec introuvable`

#### Scenario: Help
- **WHEN** the help option is given
- **THEN** it lists 18 between 12 and 1, and no other code changes meaning

### Requirement: A green light run leaves a light fingerprint for the push
The system SHALL, after a green light run and just before the merge, write the branch tip tree into the light fingerprint of light-spec-finish design D5, erase it at the start of every normal run and after a successful push, and keep it after code 10. It SHALL NOT write the complete-run or the targeted fingerprint on the light path. Untested until implemented (suite `finish_branch`).

#### Scenario: Push through the hook
- **WHEN** the light run is green and `main` is pushed through a pre-push hook with a fake runner
- **THEN** the hook's fake runner records no call and the complete-run fingerprint is unchanged

#### Scenario: Retry after a refused push
- **WHEN** the remote refuses the push after a green light run
- **THEN** the script exits 10 and the light fingerprint still holds the branch tip tree

### Requirement: The light-path validation covers the OpenSpec items the branch touches
The system SHALL, on the light path, validate in strict mode only the active changes and baseline specifications whose folder the branch changes from the up-to-date `main` and that exist at the tip, every item when the branch changes another path under the OpenSpec folder, and none when it changes only archive folders (light-finish-touched-specs design D1). It SHALL NOT run `openspec validate --all --strict` as its default validation, nor validate an archive folder.

#### Scenario: One change touched
- **WHEN** a specification branch changes only the files of one active change and the fake OpenSpec command records its calls
- **THEN** the change is validated at the tip and on `main`'s exported tree, and no other item is validated

#### Scenario: Archive only
- **WHEN** the branch changes only files under the archive folder
- **THEN** the output holds `validation OpenSpec : aucun élément à valider (archives seulement)` and the light run goes on

#### Scenario: Configuration touched
- **WHEN** the branch changes the OpenSpec configuration file
- **THEN** every change and specification is validated on both trees

### Requirement: The light-path validation refuses only new strict findings
The system SHALL compare, per item, the strict findings (level and message, counted) at the tip with those of `main`'s tree exported to a temporary folder, and exit 18 with its existing phrase, after one `nouvel avertissement strict : <élément> : <message>` line each, when a finding is more frequent at the tip (light-finish-touched-specs design D2). It SHALL NOT compare a finding's index-based path, write outside a temporary folder, or refuse a finding already on `main`.

#### Scenario: Finding already on main
- **WHEN** a touched specification carries on `main` and at the tip the same long-requirement warning
- **THEN** the output holds `aucun nouvel avertissement strict` and `avertissements stricts déjà présents sur main, non bloquants`, and the light run goes on

#### Scenario: One more finding
- **WHEN** the branch adds one long requirement to a touched specification
- **THEN** the script exits 18, the output holds one `nouvel avertissement strict` line naming that specification, and nothing is merged

#### Scenario: Index shift
- **WHEN** the branch inserts a short requirement before a long one, so the same warning has another index
- **THEN** the validation passes

#### Scenario: New change
- **WHEN** the branch adds a change with one strict finding
- **THEN** the script exits 18

#### Scenario: Provisional purpose left by an archive
- **WHEN** the branch archives a change that creates a new specification and leaves its provisional `TBD` purpose
- **THEN** the script exits 18, the output holds one `nouvel avertissement strict` line naming that new specification, and nothing is merged

#### Scenario: OpenSpec missing
- **WHEN** the OpenSpec command cannot be run
- **THEN** the complete runner runs with `runner complet nécessaire : openspec introuvable`, as before

### Requirement: Records without a fingerprint keep the comparison by tested state
The system SHALL count a record without a fingerprint, written before posture-evals-on-branch-tip, when its tested-state object holds, for the listed paths, the content of the branch tip. Such a record whose object no longer exists SHALL be skipped and, when no record counts for that reason, the message SHALL say that the tested state no longer exists. It SHALL NOT apply this comparison to a record that has a fingerprint.

#### Scenario: Fingerprinted record not compared by object
- **WHEN** a validating record holds a fingerprint other than the tip's and names a tested-state object whose listed paths equal those of the tip
- **THEN** that record does not count

### Requirement: The finish reads the evaluated paths from the shared list
The system SHALL read the evaluated paths of the missing-run check from the tracked list shared with the evaluation script, in the normal run and in check mode, and SHALL refuse with the missing-run code and `liste des fichiers évalués absente ou vide` when that list is missing or empty (design D3). It SHALL NOT fall back to built-in paths, nor read the list with a construct the system bash rejects (design D9). This list is the authority for the paid run; the local post-commit hook watches a wider set that includes every entry of this list (decision of 2026-10-21, point 5).

#### Scenario: Missing list
- **WHEN** the list file is absent and the branch changes a posture skill
- **THEN** the script exits with the missing-run code and the phrase, and nothing is merged

### Requirement: Evaluated paths are Git path specifications from the root
The system SHALL read each entry of the shared list as a Git path specification relative to the repository root, the same way in the finish and in the fingerprint (design D7). It SHALL NOT treat a session instructions file in a sub-folder as an evaluated path unless an entry names it.

#### Scenario: Instructions file in a sub-folder
- **WHEN** the branch changes only a `CLAUDE.md` file under a sub-folder
- **THEN** this check passes without looking for a record

### Requirement: Refuse a code branch that touches another active OpenSpec change
The system SHALL, in the normal run and in check mode, right before the unarchived-change check, refuse with code 19 and `la branche touche un autre change OpenSpec : <noms>` a branch that changes from its merge base a file of an active change folder other than the change named by the last segment of the branch (finish-under-lock design D6). It SHALL NOT merge, fetch, run the runner or change a file after this refusal.

#### Scenario: Another active change touched
- **WHEN** a branch named after change A changes code and a file of the active change B
- **THEN** the script exits 19, names B, prints `une branche ne porte qu'un change ; déplace ce travail dans sa propre branche`, and nothing is merged

#### Scenario: Own change
- **WHEN** a branch named after change A changes code and archives A
- **THEN** this check passes

#### Scenario: Direct-prompt branch
- **WHEN** a branch whose last segment names no change changes code and a file of the active change B
- **THEN** the script exits 19

#### Scenario: Check mode
- **WHEN** the check mode runs for a branch that touches another active change
- **THEN** it exits 19 and changes nothing

#### Scenario: Before the unarchived-change check
- **WHEN** the branch touches the unarchived change B and is not named after it
- **THEN** the script exits 19, not 5

#### Scenario: Help
- **WHEN** the help option is given
- **THEN** it lists 19 between 4 and 5

### Requirement: The one-change rule spares archives, trains and specification branches
The system SHALL let a branch change the archive folder of another change with `la branche modifie l'archive d'un autre change : <noms> (permis)`, exempt a branch whose name starts with `lot/` with `branche de train : changes portés : <noms>`, and not apply code 19 to a specification branch. It SHALL NOT count paths under the specifications folder.

#### Scenario: Archive of another change ticked
- **WHEN** a branch named after change A changes code and ticks a task in the archive folder of change B
- **THEN** this check passes and the output names B in the archive line

#### Scenario: Train branch
- **WHEN** a branch named `lot/<nom>` archives changes A and B
- **THEN** this check passes and the output holds the train line naming A and B

#### Scenario: Specification branch
- **WHEN** every path the branch changes is under the OpenSpec folder and the branch touches changes A and B
- **THEN** this check passes

### Requirement: The finishing script previews the merge of main when the branch lacks it
The system SHALL, when code 8 refuses, in the normal run and in check mode, print after the refusal phrase `fusion de main prévue : sans conflit` or `fusion de main prévue : conflit sur <n> fichier(s)` and the paths, computed on the branch tip by the shared merge-preview function (finish-under-lock design D10). It SHALL NOT change a reference, the index or a file, nor change the exit code.

#### Scenario: Conflict predicted
- **WHEN** the check mode runs for a branch that lacks `main` and changes the same lines of a specification as `main`
- **THEN** it exits 8, names that file after `conflit sur 1 fichier(s)`, and no merge is in progress

#### Scenario: Clean merge predicted
- **WHEN** the branch lacks `main` and changes other files
- **THEN** the output holds `fusion de main prévue : sans conflit`

### Requirement: The finishing scripts stay runnable by the system bash
The system SHALL keep the two finishing scripts, the modules they source and the throwaway-database script free of constructs that the system bash of macOS (3.2) rejects (finish-under-lock design D13), and their suites SHALL run them through `/bin/bash` when it exists. It SHALL NOT rely on `mapfile`, associative arrays, case conversion expansions, or a `case` without its opening parenthesis inside a command substitution.

#### Scenario: Suites under the system bash
- **WHEN** the finishing suites run on a Mac
- **THEN** every launch of a finishing script in them goes through `/bin/bash`

### Requirement: A finish record in CI mode skips the second runner only on a green recorded verdict for the tip's tree
The system SHALL, on a matching finish record with `passage: ci` and a `vert` verdict line for the tip's exact tree, skip the second runner with the CI skip line of local-ci-container design D8 and write the complete-run fingerprint; otherwise it SHALL run the second runner and log the reason of D8. A record without the field SHALL behave as today. It SHALL NOT start a container, write the verdict file, nor refuse on this ground.

#### Scenario: Record in CI mode with a green verdict
- **WHEN** a matching record holds `passage: ci` and the verdict file holds a `vert` line for the tip's tree
- **THEN** the finishing script prints `saut du second runner : verdict du conteneur et passe Mac (arbre <court>)`, runs no runner and writes the complete-run fingerprint

#### Scenario: Record in CI mode without a green verdict
- **WHEN** a matching record holds `passage: ci` and the verdict file holds no `vert` line for the tip's tree
- **THEN** the finishing script runs its second runner, logs the reason, and the fake Docker command records nothing

#### Scenario: Former record
- **WHEN** a matching record has no `passage` field
- **THEN** the skip line and behaviour are those of today and the verdict file is not read
