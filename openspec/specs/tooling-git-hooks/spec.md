# tooling-git-hooks Specification

## Purpose
Git hooks, installed from a tracked folder, that protect confidentiality at commit time (pre-commit for sensitive names, commit-msg for personal identifiers and sensitive names in the message, pre-push for sensitive names in the messages of the commits that leave), require a green test run of what is committed (pre-commit) and of what is pushed to `main` (pre-push), and optionally trigger the posture evaluation run after a commit (post-commit).

## Requirements

### Requirement: A script installs the hooks as relative links
The system SHALL provide an installer that links the pre-commit, post-commit, commit-msg and pre-push hooks of the repository's tracked hooks folder into the repository's git hooks folder with relative symbolic links, makes the sources executable, and verifies the result. It SHALL stop with an error, linking nothing, outside a git repository or when the repository's hooks folder is not the standard one that the relative links assume.

#### Scenario: Fresh install
- WHEN the installer runs on a repository without the links
- THEN each of the four hooks is a relative link to its tracked source, executable, and the output says all hooks are in place

Source: tests/installation/test_install_hooks.sh

### Requirement: The hook installer is safe to run again and never deletes a hook
The system SHALL make the hook installer safe to run again (a correct link is left untouched), and SHALL make it move a different existing hook aside instead of deleting it, repair a wrongly aimed link, exit non-zero and name a missing source hook, and offer a verify-only mode that changes nothing. It SHALL NOT delete an existing hook.

#### Scenario: Second run
- WHEN the installer runs again
- THEN it succeeds, creates no backup and leaves the links unchanged

#### Scenario: Different existing hook
- WHEN a hook that is not the expected link exists
- THEN it is moved aside, not deleted

#### Scenario: Verify only
- WHEN the installer runs in verify-only mode without the links
- THEN it exits non-zero and creates nothing

#### Scenario: Pre-push missing
- WHEN the three former links are in place but the pre-push link is not
- THEN verify-only mode exits non-zero and names the pre-push hook

#### Scenario: Wrongly aimed link
- WHEN a hook link points to another target
- THEN the installer replaces it with the expected link and succeeds

#### Scenario: Missing source hook
- WHEN a tracked hook source is absent
- THEN the installer exits non-zero and names the absent source

Source: tests/installation/test_install_hooks.sh

### Requirement: Pre-commit blocks sensitive names in staged files
The system SHALL refuse a commit when a staged text file contains a name from the local sensitive-names list, matching whole words only, and SHALL report the file and line number but never the name.

#### Scenario: Name found
- WHEN a staged file contains a listed name on line 2
- THEN the hook exits non-zero and prints the file and "line 2", and its output contains no listed name

#### Scenario: Name inside a longer word
- WHEN a listed name is glued to letters, digits or underscores on either side
- THEN the hook does not block

#### Scenario: Names with symbols
- WHEN a listed name starts or ends with a symbol and appears in parentheses or alone on a line
- THEN the hook blocks

Source: tests/hooks/test_pre_commit.sh

### Requirement: Case rules
The system SHALL ignore case for ordinary names, and SHALL compare in a case-sensitive way names of three characters or fewer and names written entirely in capitals.

#### Scenario: Ordinary name
- WHEN a staged line contains a listed ordinary name in lowercase
- THEN the commit is blocked

#### Scenario: Acronym or short name
- WHEN a staged line contains the lowercase form of a listed acronym or short name
- THEN the commit is not blocked, while the exact-case form is blocked

Source: tests/hooks/test_pre_commit.sh

### Requirement: All staged text files are examined
The system SHALL examine every staged added, copied or modified file whatever its extension, except binary files (containing a null byte), which it skips, and files over one megabyte, which it skips with a notice and without blocking.

#### Scenario: Extension-less or .txt file
- WHEN a staged file with no extension or a .txt extension contains a listed name
- THEN the commit is blocked

#### Scenario: Binary file
- WHEN a staged file contains a null byte
- THEN it is not examined

#### Scenario: Large file
- WHEN a staged file is larger than one megabyte
- THEN the hook prints a notice naming the file, does not block

Source: tests/hooks/test_pre_commit.sh

### Requirement: Installed hook refuses real commits
The system SHALL, when installed as the repository pre-commit hook, make a real commit fail on a sensitive name and succeed on a clean one, without relying on any bypass option.

#### Scenario: Real commit
- WHEN a file with a listed name is staged and git commit runs
- THEN the commit is refused; a clean staged file commits normally

Source: tests/hooks/test_pre_commit.sh

### Requirement: Comment lines of the names list are ignored
The system SHALL ignore the lines of the sensitive-names list that start with a comment sign, possibly after spaces, and SHALL keep the other names of the list active.

#### Scenario: Commented name
- WHEN a name is listed only on a comment line and a staged file contains it
- THEN the commit is not blocked, while a name listed on an ordinary line still blocks

Source: tests/hooks/test_pre_commit.sh

### Requirement: Inactive guard warns
The system SHALL not block when the names list is missing or empty, a list holding only comment and blank lines counting as empty, and SHALL print a warning saying the guard is inactive and why.

#### Scenario: List missing
- WHEN the list file does not exist
- THEN the hook exits 0 with a "list absent" warning

#### Scenario: List empty
- WHEN the list file is empty, or holds only comment lines
- THEN the hook exits 0 with a "list empty" warning

Source: tests/hooks/test_pre_commit.sh

### Requirement: Post-commit does nothing unless asked
The system SHALL, after a commit, start the evaluation run in the background only when the after-commit mode variable is set to a recognised value, and SHALL do nothing when it is absent, empty or unknown.

#### Scenario: Evals mode
- WHEN the mode is "evals" and the commit touched a watched file
- THEN the evaluation script is started with no extra option

#### Scenario: All mode
- WHEN the mode is "all" and the commit touched a watched file
- THEN the evaluation script is started with the readme-update option

#### Scenario: No mode
- WHEN the variable is absent, empty or unknown
- THEN nothing is started

Source: tests/hooks/test_post_commit.sh

### Requirement: No-evals override
The system SHALL start nothing when the no-evals variable is set, even if a mode is requested.

#### Scenario: Override
- WHEN the mode is "all" and the no-evals variable is set
- THEN nothing is started

Source: tests/hooks/test_post_commit.sh

### Requirement: Only commits touching watched files trigger a run
The system SHALL trigger a run only when the commit changed instructions, a posture skill, an agent, a command, the posture test cases or vocabulary, the frozen posture memory, or the library server; it SHALL ignore a first commit and unrelated files.

#### Scenario: Watched file
- WHEN a commit changes the posture cases, vocabulary, English neutral memory or a posture skill, with mode "evals"
- THEN the run starts

#### Scenario: Unwatched file
- WHEN a commit changes only an unrelated document, with mode "all"
- THEN nothing starts

Source: tests/hooks/test_post_commit.sh

### Requirement: The watched set includes every entry of the shared list of evaluated paths
The watched set of the post-commit hook is deliberately wider than the shared list of evaluated paths read by the finish, which alone decides whether the paid run is required; every entry of that list SHALL also be watched here (decision of 2026-10-21, point 5), and a test of the posture evaluation suite guards this inclusion.

#### Scenario: Entry of the shared list
- **WHEN** a tracked file aimed by an entry of the shared list is compared with the watched set
- **THEN** that file triggers the post-commit hook

Source: tests/posture_evals/test_branche.py (test_chaque_entree_de_la_fin_est_surveillee_par_le_post_commit)

### Requirement: Only the real workspace reacts
The system SHALL ignore commits made in any repository other than the real workspace location, so temporary copies used by evaluations do not trigger runs.

#### Scenario: Temporary copy
- WHEN a commit happens in a repository outside the real workspace path
- THEN nothing is started

Source: tests/hooks/test_post_commit.sh

### Requirement: Commit-msg hook refuses personal identifiers
The system SHALL, when installed as the repository commit-msg hook, run the personal-identifier scanner on the commit message up to git's scissors line, comment lines included, and refuse the commit when the message contains an identifier, SHALL report that the message contains an identifier without printing the identifier nor the message text, and SHALL let a clean message commit.

#### Scenario: Message with an identifier
- WHEN a commit message contains an identifier and git commit runs
- THEN the commit is refused, and the output contains neither the identifier nor the message text

#### Scenario: Clean message
- WHEN a commit message contains no identifier
- THEN the commit succeeds

#### Scenario: Scanner cannot run
- WHEN the scanner exits with an error code other than a finding
- THEN the commit is refused and the output says the message could not be checked

#### Scenario: Identifier on a comment line or below the scissors line
- WHEN the identifier appears on a comment line kept in the commit
- THEN the commit is refused, since comment lines can stay in the commit; when it appears only below the scissors line, the commit succeeds, since what follows that line, such as the diff of `git commit -v`, is never committed and not checked

Source: tests/hooks/test_commit_msg.sh

### Requirement: Pre-commit requires a green run of the index, complete on main
The system SHALL make the pre-commit hook refuse a commit on `main` or on a detached head when the complete-run fingerprint is absent or differs from the fingerprint of the index, with the current message asking to run the runner first. The hook SHALL NOT accept a targeted fingerprint on `main` or on a detached head.

#### Scenario: Main with only a targeted fingerprint
- **WHEN** a commit is attempted on `main` and only the targeted fingerprint matches the index
- **THEN** the commit is refused and the message asks for the complete run

#### Scenario: Commit of all tracked changes
- **WHEN** a commit stages tracked changes itself at commit time, so that the index it commits has no recorded fingerprint
- **THEN** the commit is refused; it is accepted when the index was already green before

#### Scenario: Detached head
- **WHEN** a commit is attempted on a detached head with only the targeted fingerprint matching
- **THEN** the commit is refused

Source: tests/hooks/test_pre_commit_green.sh

### Requirement: Pre-commit accepts a targeted or complete green run of the index on a work branch
The system SHALL make the pre-commit hook, on any branch other than `main` or a detached head, accept the commit when either the complete-run fingerprint or the targeted-run fingerprint equals the fingerprint of the index, and SHALL make it otherwise refuse with a message asking to run the runner's targeted option after `git add`.

#### Scenario: Branch with a matching targeted fingerprint
- **WHEN** a commit is attempted on a work branch and the targeted fingerprint equals the index fingerprint
- **THEN** the green-run check passes

#### Scenario: Branch without fingerprint
- **WHEN** a commit is attempted on a work branch and no fingerprint matches the index
- **THEN** the commit is refused and the message names the targeted option

#### Scenario: Index changed after the targeted run
- **WHEN** a file is staged after the targeted green run
- **THEN** the commit is refused

Source: tests/hooks/test_pre_commit_green.sh

### Requirement: The owner bypass skips only the pre-commit green-run check
The documented owner bypass variable SHALL skip the green-run check of the pre-commit hook only, and the sensitive-names check SHALL apply in every case.

#### Scenario: Owner bypass
- **WHEN** the bypass variable is set
- **THEN** the green-run check is skipped and the sensitive-names check still applies

Source: tests/hooks/test_pre_commit_green.sh; the sensitive-names check under the bypass: tests/hooks/test_pre_commit.sh (which sets the bypass)

### Requirement: Pre-push requires a green complete run of the pushed main
The system SHALL provide a pre-push hook that, for each pushed reference updating the remote `main`, checks in this order: the complete-run fingerprint, then the command line of the proof function of change ci-local-runner (design D8, Q217, R-20261101-116) for the tree of the pushed commit, accepting the push on a matching fingerprint or on `conteneur`; when none holds, and the working tree is clean and the current head is the pushed commit, the hook SHALL run the complete runner itself, without the variable reserved to git commit, and accept only on a green run, and SHALL refuse otherwise. A proof call that fails or exits other than 0 with `conteneur` SHALL count as no proof, and the hook SHALL go on to the runner fallback. It SHALL NOT accept the `ciblee` proof, nor accept a push because the proof call failed.

#### Scenario: Matching fingerprint
- **WHEN** `main` is pushed and the complete-run fingerprint equals the pushed tree
- **THEN** the push proceeds without running tests

#### Scenario: Container proof of the pushed tree
- **WHEN** the CI proof file and the Mac record hold the pushed tree
- **THEN** the push of `main` passes without a test run

#### Scenario: No fingerprint, clean tree at the pushed commit
- **WHEN** `main` is pushed, the proof function returns neither `complete` nor `conteneur`, the tree is clean and the head is the pushed commit
- **THEN** the hook runs the complete runner and the push proceeds only if it passes

#### Scenario: Proof call fails, clean tree at the pushed commit
- **WHEN** the proof helper cannot run, no fingerprint matches, the tree is clean and the head is the pushed commit
- **THEN** the hook runs its fake runner and the push proceeds only if it passes

#### Scenario: Proof call fails, other state
- **WHEN** the proof helper cannot run, no fingerprint matches and the working tree is dirty
- **THEN** the hook refuses with `pre-push : main exige une exécution complète réussie de l'arbre poussé`

Source: tests/hooks/test_pre_push.sh

### Requirement: The pre-push hook refuses a push of main it cannot check
The system SHALL make the pre-push hook refuse a push of the remote `main` when neither the complete-run fingerprint nor the container proof (`complete` or `conteneur`) holds for the pushed tree and the working tree is not clean, the head is not the pushed commit or the pushed tree cannot be read (change tooling-specs-apres-b9, design D5). It SHALL NOT accept a light fingerprint, `ciblee` or a failed proof call, nor refuse a push whose container proof holds.

#### Scenario: No fingerprint, other state
- **WHEN** `main` is pushed, no complete-run fingerprint matches, the container proof does not hold, and the working tree is dirty or the head differs from the pushed commit
- **THEN** the push is refused with `pre-push : main exige une exécution complète réussie de l'arbre poussé` and the runner does not run

#### Scenario: Rules replaced and removal
- **WHEN** the origin of this requirement is checked
- **THEN** it replaces the wording that named the complete-run fingerprint only (finding 5 of the B9 review, R-20261106-49); the container part falls with the container route of the hook

#### Scenario: Head other than the pushed commit
- **WHEN** a commit that is not the current head is pushed to the remote `main` without a matching fingerprint or container proof
- **THEN** the push is refused and the runner does not run

#### Scenario: Pushed tree unreadable
- **WHEN** the pushed commit's tree cannot be read
- **THEN** the push is refused with the message and the runner does not run

#### Scenario: Container proof with a tree that is not clean
- **WHEN** `main` is pushed, no complete-run fingerprint matches, the proof function returns `conteneur` for the pushed tree and the working tree is dirty
- **THEN** the push passes and no test runs

Source: tests/hooks/test_pre_push.sh (dirty tree without fingerprint, push of another commit to `main`, unreadable tree; the container proof is absent from its throwaway data folder); the container proof with a tree that is not clean: untested (the acceptance case of the container block runs on a clean tree at the pushed commit).

### Requirement: Pushes of other references pass the pre-push test-run check
Pushes of references other than the remote `main`, and deletions of remote references, SHALL pass the test-run check of the pre-push hook (the check of commit-message names below applies to every pushed reference).

#### Scenario: Work branch
- **WHEN** a work branch whose outgoing commit messages hold no listed name is pushed
- **THEN** the hook does not check the test run

#### Scenario: Remote branch deletion
- **WHEN** a push deletes a remote work branch
- **THEN** the hook does not check anything

Source: tests/hooks/test_pre_push.sh

### Requirement: The pre-push test-run check tests only the pushed tree and never accepts a targeted fingerprint
The pre-push hook SHALL NOT run tests on a tree other than the pushed one, and SHALL NOT accept a targeted fingerprint nor a light fingerprint: only the complete-run fingerprint of the pushed tree, or the container proof of that tree, or the hook's own green complete run on that tree, lets `main` leave (the light path is withdrawn, change finish-single-b7-b9, design D8). The hook SHALL NOT source `tools/light_finish.sh` nor read the main-validation record.

#### Scenario: Targeted fingerprint only
- **WHEN** `main` is pushed and only the targeted fingerprint equals the pushed tree, and the runner fails
- **THEN** the push is refused

#### Scenario: Light fingerprint only
- **WHEN** `main` is pushed, a light fingerprint equal to the pushed tree exists, no complete-run fingerprint matches, and the working tree is not clean
- **THEN** the push is refused with `pre-push : main exige une exécution complète réussie de l'arbre poussé`

Source: tests/hooks/test_pre_push.sh

### Requirement: The pre-push runner is replaceable and the owner bypass skips the test-run check
The runner command of the pre-push hook SHALL be replaceable through an environment variable for the hook's tests. The owner bypass variable of the green-run check SHALL skip the test-run check of the pre-push hook.

#### Scenario: Another commit pushed to main
- **WHEN** a commit that is not the current head is pushed to the remote `main` without a matching fingerprint
- **THEN** the push is refused without running the runner; with the owner bypass variable it proceeds

Source: tests/hooks/test_pre_push.sh

### Requirement: Commit messages never carry a listed name
The system SHALL make the commit-msg hook refuse a commit whose message, up to git's scissors line and comment lines included, holds a name of the two lists the pre-commit hook reads (the sensitive-names list and the distinctive names of the team-names extract), with the same matching rules, reporting the line number of the message and never the name nor the message text.

#### Scenario: Message with a listed name
- **WHEN** a commit message holds a name of the sensitive-names list or of the team-names extract and git commit runs
- **THEN** the commit is refused, the output gives the line of the message and contains neither the name nor the message text

#### Scenario: Name on a comment line, below the scissors line, or glued to a letter
- **WHEN** the name appears on a comment line kept in the commit (`git commit -m "# …"`, verbatim cleanup)
- **THEN** the commit is refused; when it appears only below the scissors line or only glued to a letter, the commit succeeds

Source: tests/hooks/test_commit_msg.sh

### Requirement: The pre-push hook refuses outgoing commit messages that carry a listed name
The system SHALL make the pre-push hook, for every pushed reference except a deletion, read the messages of the commits that leave (those of the pushed commit that no remote-tracking reference of that remote holds, the remote tip excluded when it is known locally) and refuse the push when one holds a listed name, reporting the count and the short identifiers of the touched commits, never a name nor a message.

#### Scenario: Outgoing commit with a listed name
- **WHEN** a work branch, a tag or `main` is pushed and an outgoing commit message holds a listed name
- **THEN** the push is refused with the count and the short identifier of that commit, never the name, and the owner bypass variable does not lift the refusal

#### Scenario: Commit already on the remote
- **WHEN** a touched commit is already held by a remote-tracking reference and only clean commits leave
- **THEN** the push proceeds and the touched commit is not counted

Source: tests/hooks/test_pre_push.sh

### Requirement: The pre-push name check covers annotated tags and remotes given by address
The system SHALL make the pre-push hook, for an annotated tag, also check the tag's own message, and, when the remote is given by address (no remote-tracking reference), exclude the remote tip when known locally and say so.

#### Scenario: Annotated tag message
- **WHEN** an annotated tag whose message holds a listed name is pushed, its commit being clean
- **THEN** the push is refused without printing the name

#### Scenario: Remote given by address
- **WHEN** a branch is pushed to a remote given by its address
- **THEN** the hook says so and excludes only the known remote tip; a new branch has its whole history read

Source: tests/hooks/test_pre_push.sh

### Requirement: The name checks of the commit-msg and pre-push hooks show only the tool's lines and fail closed
For the check of listed names, both the commit-msg and the pre-push hooks SHALL show only the tool's own lines, never a trace, and SHALL never let the tool read the hook's standard input. Both hooks SHALL refuse when the list is missing or unreadable, or when the checking tool is missing or fails (closed by default); an empty list SHALL warn without blocking, as in pre-commit.

#### Scenario: List missing at commit time
- **WHEN** the sensitive-names list is missing
- **THEN** the commit is refused and the output says the list is missing

#### Scenario: List missing at push time
- **WHEN** the list is missing and a reference is pushed
- **THEN** the push is refused; a deletion still proceeds

#### Scenario: Output of the checking tool
- **WHEN** either hook runs the checking tool
- **THEN** the output holds only the tool's own lines, never a trace, and the tool does not read the hook's standard input

Source: tests/hooks/test_commit_msg.sh; tests/hooks/test_pre_push.sh

### Requirement: The owner bypass does not lift the check of listed names in commit messages
The owner bypass variable of the green-run check SHALL NOT lift the check of listed names of the commit-msg and pre-push hooks.

#### Scenario: Bypass set on a push
- **WHEN** the owner bypass variable is set and an outgoing commit message holds a listed name
- **THEN** the push is still refused

Source: tests/hooks/test_pre_push.sh

### Requirement: A read-only tool runs the name check once over unpushed commits
The system SHALL also provide a read-only tool that runs the same check once over the messages of every local commit missing from the remotes (local branches and tags), or over a given range, and prints the count of commits read and of touched commits and the short identifier of each touched commit, never a name nor a message (decision of the author, 2026-10-21, point 3).

#### Scenario: One-time pass over unpushed commits
- **WHEN** the tool runs in a repository where one of the unpushed commits holds a listed name in its message
- **THEN** it exits 1 and prints the count and that commit's short identifier, never the name nor the message, and changes nothing in the repository

Source: tests/sensitive_names/test_commit_names_scan.py (PassageSurLesCommitsNonPousses)

### Requirement: The one-time name check tool exits with one code per outcome
The read-only tool of the one-time name check SHALL exit 0 without a name, 1 with at least one, 2 when the list is unavailable and 3 on a usage or reading error or any unexpected error (only the exception type is printed).

#### Scenario: List unavailable
- **WHEN** the tool runs while the sensitive-names list is missing
- **THEN** it exits 2

#### Scenario: Unknown revision
- **WHEN** the tool is given a revision that does not exist
- **THEN** it exits 3

Source: tests/sensitive_names/test_commit_names_scan.py (PassageSurLesCommitsNonPousses, ErreurInattendue)

### Requirement: Deprecated variable names refused
The system SHALL refuse the former mode variable, its former values and the former no-evals variable: the hook SHALL print on standard error and append to the hook log a message naming the current variable or value, and SHALL start no run.

#### Scenario: Old name
- **WHEN** the former mode variable is set
- **THEN** no run starts and the message names the current variable in the output and the log

#### Scenario: Old value
- **WHEN** the current mode variable is set to a former value
- **THEN** no run starts and the message names the current value

#### Scenario: Current names
- **WHEN** only current names are set
- **THEN** no refusal message appears

### Requirement: Pre-commit refuses every commit in the run tree
The system SHALL make the pre-commit hook refuse any commit whose repository top level is the run tree, before every other check, with the key phrase of design D6, whatever the branch, the fingerprints or the owner bypass variable. It SHALL NOT refuse a commit in the development checkout or in a work-branch worktree on that ground. Untested until implemented.

#### Scenario: Commit in the run tree
- **WHEN** a commit is attempted in a run tree of a temporary repository, with a matching complete-run fingerprint and the owner bypass variable set
- **THEN** the commit is refused with the run-tree key phrase

#### Scenario: Work-branch worktree
- **WHEN** a commit is attempted in a work-branch worktree of the same repository
- **THEN** the run-tree refusal does not apply

### Requirement: The pre-commit hook refuses a commit during another process's finish
The system SHALL make the `pre-commit` hook, as its first check, refuse the commit with `pre-commit : fin de branche en cours (<branche>), commit refusé` when the finish lock of multi-session-piloting design D5 is held by a live process, the committer's lock token is unset or differs from it, and the targeted freeze of change autonomous-trains-merge (design D18, through `freeze_scope()`) covers the commit: the committing worktree is in the lock's list, the commit writes `main`, or the lock holds no readable list. A matching token, a stale lock (D6), or a commit in a worktree that the lock does not list and that does not write `main` SHALL let the other checks run as before. It SHALL NOT be lifted by the owner bypass variable, keep a freeze rule of its own beside `freeze_scope()`, and SHALL NOT create, remove or change the lock.

#### Scenario: Agent commit during a finish
- **WHEN** a lock of a live process lists the committing worktree and a commit is made without a token in a temporary repository
- **THEN** the commit is refused with that phrase and the branch tip is unchanged

#### Scenario: Commit in a worktree outside the train
- **WHEN** a lock of a live process lists other worktrees and a commit is made without a token on a work branch of a worktree that the lock does not list
- **THEN** the hook goes on to its other checks

#### Scenario: Commit on main during a finish
- **WHEN** a lock of a live process is held and a commit on `main` is made without a token from a worktree that the lock does not list
- **THEN** the commit is refused with that phrase

#### Scenario: Lock without a readable list
- **WHEN** a lock of a live process holds no readable list and a commit is made without a token
- **THEN** the commit is refused with that phrase

#### Scenario: Owner bypass set
- **WHEN** the commit of the scenario "Agent commit during a finish" is made with the owner bypass variable set
- **THEN** it is still refused

#### Scenario: Finish's own commit
- **WHEN** the committer's token equals the lock's token
- **THEN** the hook goes on to its other checks

#### Scenario: Stale lock
- **WHEN** the lock names a process that no longer exists
- **THEN** the hook goes on to its other checks and the lock is unchanged

### Requirement: Pre-commit warns about a list entry that is a common word
The system SHALL make the pre-commit hook print, for each list entry made of common words (shared rule, design D3), one warning line with the list line number and the advice of D3. The warning SHALL NOT block a commit or change the other checks' result; the hook SHALL NOT print the entry or the matched text, flag an entry of three characters or fewer, or write the list.

#### Scenario: Common word in the list, clean commit
- **WHEN** a fictitious list holds a distinctive sentinel name on line 1 and one common word on line 3, and the staged files hold neither
- **THEN** the commit succeeds, the output holds "la ligne 3 de la liste des noms sensibles est un mot courant", and neither entry appears in the output

#### Scenario: Common word matched in a staged file
- **WHEN** the common word of line 3 appears in a staged file
- **THEN** the commit is refused as before, with the file and line of the staged file, and the warning for line 3 is also printed

#### Scenario: Distinctive list
- **WHEN** every entry of the fictitious list holds a word that is not common
- **THEN** no warning line is printed

### Requirement: Pre-commit also blocks the distinctive team names of the extract
The system SHALL refuse a commit when a staged text file contains a distinctive team name of the team-names extract, with the matching rules and report of the sensitive-names list: file and line, never the name (design D8). It SHALL NOT use an extract name made only of common words, SHALL NOT change its behaviour when the extract is missing, and SHALL NOT write the list or the extract. Untested until implemented.

#### Scenario: Distinctive extract name
- **WHEN** a staged file contains, on line 3, a distinctive team name of the extract that is not in the sensitive-names list
- **THEN** the hook exits non-zero and prints the file and "line 3", and its output contains no team name

#### Scenario: Common-word extract name
- **WHEN** a staged file contains a name of the extract made only of common words
- **THEN** the hook does not block for it

#### Scenario: No extract
- **WHEN** the extract does not exist
- **THEN** the hook blocks and lets pass exactly as with the sensitive-names list alone

### Requirement: The extract guard skips the names of the author's generic-names list
The system SHALL, when reading the distinctive team names of the extract, leave out every name equal, without case and surrounding spaces, to a line of the generic-names list kept next to the extract outside Git, comment and empty lines ignored (extract-name-exclusions design D1, D2). It SHALL NOT filter the sensitive-names list, match part of a name, raise an error or print a name when the list is missing or unreadable.

#### Scenario: Listed generic name
- **WHEN** a staged file contains a distinctive name of the extract that the generic-names list holds in another case
- **THEN** the hook does not block for it

#### Scenario: Partial entry
- **WHEN** the list holds one word of a two-word extract name
- **THEN** the two-word name still blocks

#### Scenario: Name also in the sensitive-names list
- **WHEN** a name is in the generic-names list and in the sensitive-names list
- **THEN** the hook still blocks it

#### Scenario: List missing or unreadable
- **WHEN** the generic-names list is missing, or cannot be read
- **THEN** the extract names are the same as without a list, and nothing is printed about the list

### Requirement: Pre-commit refuses staged secrets
The system SHALL refuse a commit when a staged text file, whatever its size, holds a value of a secret family of design D1, printing the file, line and family with the phrase of D8. It SHALL NOT print the value or the line text, skip the scan because the names list is missing or empty, or let the owner bypass variable lift it. Untested until implemented (suite `hooks`).

#### Scenario: Token staged
- **WHEN** a staged file holds, on line 4, a token of a listed family built by the test at run time
- **THEN** the hook exits 1, prints the file, "ligne 4" and the family, and its output holds no part of the token

#### Scenario: Empty names list
- **WHEN** the names list and the extract are empty and a staged file holds a secret
- **THEN** the inactive-guard warning is printed and the commit is still refused for the secret

#### Scenario: Owner bypass
- **WHEN** the owner bypass variable is set and a staged file holds a secret
- **THEN** the commit is refused

#### Scenario: Large file
- **WHEN** a staged text file over one megabyte holds a secret
- **THEN** the commit is refused, and the notice that names are not checked in it is still printed

### Requirement: Placeholders are not secrets
The system SHALL NOT report as a secret a value in angle brackets, a value of one repeated character, or a shell or template variable reference (a name in capitals between braces, `{X}`, included), nor a lock-file hash, image digest or SHA fingerprint. Untested until implemented (suite `secret_scan`).

#### Scenario: Placeholder address
- **WHEN** a staged file holds a connection address whose password part is a variable reference
- **THEN** no secret is reported

#### Scenario: Digest
- **WHEN** a staged file holds an image digest and a lock-file hash
- **THEN** no secret is reported

### Requirement: The secret scan fails closed
The system SHALL refuse the commit with the phrase of design D8 when the scanner module cannot be imported or fails while scanning. No variable SHALL lift this refusal. Untested until implemented (suite `hooks`).

#### Scenario: Module unavailable
- **WHEN** the hook runs with the scanner module made unimportable
- **THEN** the commit is refused with "recherche de secrets impossible"

### Requirement: Declared examples pass
The system SHALL accept a finding whose path and value fingerprint (SHA-256) are both in the tracked list of declared examples, printing `pre-commit : exemple déclaré accepté : <fichier>, ligne <n> (<famille>)` (design D6). It SHALL NOT store or print the value, accept the same value in another file, offer an inline marker, or read a malformed list (fail closed). Untested until implemented (suites `secret_scan`, `hooks`).

#### Scenario: Declared example
- **WHEN** a staged file holds a token whose path and fingerprint are in the list
- **THEN** the commit succeeds and the output names the file and line, not the token

#### Scenario: Same value elsewhere
- **WHEN** the same token is staged in another file
- **THEN** the commit is refused

### Requirement: Only the author writes the declared examples
The system SHALL write list entries only through a declare command that refuses with code 3 when `CLAUDECODE` is set, and SHALL make the pre-commit hook refuse a staged change of the list when `CLAUDECODE` is set (design D6). The declare command SHALL NOT print the value or its fingerprint. Untested until implemented (suites `secret_scan`, `hooks`).

#### Scenario: Declare from a session
- **WHEN** the declare command runs with `CLAUDECODE` set
- **THEN** it exits 3 and the list is unchanged

#### Scenario: List committed from a session
- **WHEN** a change of the list is staged and the hook runs with `CLAUDECODE` set
- **THEN** the commit is refused with "liste des exemples déclarés modifiée depuis une session"

### Requirement: No tracked file holds an undeclared secret
The system SHALL include a guard test that scans every tracked text file with the secret scanner and fails naming each file, line and family, never the value, unless the finding is a declared example. Test fixtures SHALL build secret-looking values at run time. Untested until implemented (suite `secret_scan`).

#### Scenario: Real repository
- **WHEN** the guard runs on the repository
- **THEN** it passes, and fails as soon as a tracked file holds an undeclared value of a listed family

### Requirement: A merge commit is refused during another process's finish
The system SHALL provide a `pre-merge-commit` hook that, when a live finish lock is held and the caller's lock token is absent or different, exits 1 with `pre-merge-commit : fin de branche en cours (<branche>), fusion refusée` (finish-under-lock design D17). It SHALL let a stale lock through with `pre-merge-commit : verrou de fin périmé, ignoré`, and SHALL NOT run the green-run check or the names guard.

#### Scenario: Merge during another finish
- **WHEN** a temporary repository holds a live lock of another token and `git merge` would create a merge commit
- **THEN** the merge is refused with that phrase and no merge commit is created

#### Scenario: The finish's own merge
- **WHEN** the same merge runs with the lock's token
- **THEN** the merge commit is created

### Requirement: The main branch does not move during another process's finish
The system SHALL provide a `reference-transaction` hook that, in the `prepared` state and for `refs/heads/main` only, exits 1 with `reference-transaction : fin de branche en cours (<branche>), mise à jour de main refusée` when a live finish lock is held and the caller's token is absent or different (finish-under-lock design D17). It SHALL exit 0 at once otherwise, unless the session guard below applies, and SHALL NOT be bypassed by any variable.

#### Scenario: Fast-forward during another finish
- **WHEN** a live lock of another token is held and `git merge --ff-only` would move `main`
- **THEN** `main` keeps its commit and the output holds the refusal phrase

#### Scenario: Reset and update-ref during another finish
- **WHEN** a live lock of another token is held and `git reset --hard` or `git update-ref refs/heads/main` targets another commit
- **THEN** `main` keeps its commit

#### Scenario: Other branches
- **WHEN** a live lock of another token is held and a commit moves another branch
- **THEN** this hook lets the update through

#### Scenario: No lock
- **WHEN** no lock folder exists and the session marker is absent
- **THEN** any update of `main` goes through and no Python process is started

#### Scenario: Stale lock
- **WHEN** the lock is stale and the session marker is absent
- **THEN** the output holds `reference-transaction : verrou de fin périmé, ignoré` and `main` moves

### Requirement: A Claude Code session never moves the main branch
The system SHALL make the `reference-transaction` hook refuse, in the `prepared` state and before any lock lookup, an update of `refs/heads/main` that deletes it or gives it another value than the current one, when the Claude Code session marker is set. No token SHALL lift this, and other references SHALL never be touched (R-148, u13).

#### Scenario: Session moves main
- **WHEN** the session marker is set (even empty) and a rebase, `reset --hard`, `update-ref refs/heads/main`, `cherry-pick`, `branch -f main`, `checkout -B main`, `switch -C main` or a deletion would move `main`
- **THEN** `main` keeps its commit, the hook exits 1 and the output holds `reference-transaction : session Claude Code, mise à jour de main refusée ; intégrer main : git rebase main dans le worktree de la branche ; main n'avance que par une fin de l'auteur`

#### Scenario: Same moves outside a session
- **WHEN** the session marker is absent and no lock is held
- **THEN** the same commands move `main`

#### Scenario: Session leaves other references alone
- **WHEN** the session marker is set and a commit or a rebase moves a work branch, or a fetch updates `refs/remotes/origin/main`
- **THEN** this hook lets the update through

#### Scenario: Session with the lock token
- **WHEN** the session marker is set and the command carries the token of a live finish lock, or another token, or the lock is stale
- **THEN** `main` keeps its commit and the output holds the session phrase, never the lock phrase

#### Scenario: Same token outside a session
- **WHEN** the session marker is absent and the command carries the token of a live finish lock
- **THEN** `main` moves

#### Scenario: Update with no effect
- **WHEN** the session marker is set and a command rewrites `main` with its current value (`git reset`, `git reset --hard HEAD`, `git stash`, `git rebase --abort`)
- **THEN** the update goes through and `main` keeps its commit

#### Scenario: Folder left half-changed after a refusal
- **WHEN** the session marker is set and `checkout -B main` or `switch -C main` is refused from a work branch, or a rebase of `main` is refused
- **THEN** `HEAD` stays on the work branch (detached for the rebase), and `git reset --hard` on the work branch, or `git rebase --abort`, restores tree and index

#### Scenario: Other bypass gestures
- **WHEN** the session marker is set and `branch -M x main`, `fetch . +x:main`, `fetch <origin> +main:main`, `commit` on `main` or `update-ref` from a linked worktree would move `main`
- **THEN** `main` keeps its commit

#### Scenario: Declared limits
- **WHEN** the session marker is set and `git branch -C x main` copies a branch onto `main`
- **THEN** Git writes the reference outside a transaction, the hook is not called and `main` moves; the same holds for any `core.hooksPath` redirected away from the hook (`git -c core.hooksPath=...`, `GIT_CONFIG_*` variables, `git config core.hooksPath`). Both gestures are refused by the deny rules of fragment 39 (`.claude/deny/39-garde-main-session.txt`): any command that contains `hooksPath` (five spellings) or `GIT_CONFIG_`, and every forced write of `main` by `git branch` (`-M`, `-C`, `-m` or `-c` with `-f`, `main` as destination wherever the options stand, in the bare, `git -*`, absolute-path, `env`, `cd` and chained forms). What remains a limit: the spellings of `hooksPath` outside the five covered (the pattern is case-sensitive), a split or quoted word, `main` written other than as a word that starts with `main` (`refs/heads/main`, `'main'`), an option cluster outside the list, and `git pack-refs --all` (no rule; refused in a session by this hook)

#### Scenario: Tidying of references
- **WHEN** the session marker is set and `git pack-refs --all` or `git gc` would remove the loose file of `main`
- **THEN** the removal is refused, `pack-refs` exits in error, `gc -q` exits 0 and `main` keeps its value as a loose file

### Requirement: The finish's own restoring steps carry the lock token
The system SHALL make every Git command the finishing scripts run under the lock carry the lock token, including the merge of `main`, the move of `main` by the finishing script, `git merge --abort`, the switch back after a refusal or an interruption, and any reset on a failure path, so the hooks of this capability never refuse the finish itself (finish-under-lock design D17).

#### Scenario: Abort after a refused merge
- **WHEN** the worktree finish's merge of `main` fails in a temporary repository with both hooks installed
- **THEN** `git merge --abort` succeeds and the script exits 46

#### Scenario: Interrupted finish restores its state
- **WHEN** the worktree finish is interrupted after it started a merge, with both hooks installed
- **THEN** the merge is aborted and the interruption line of design D11 is printed

#### Scenario: Main moved by the finish
- **WHEN** the finishing script moves `main` to the merged tip with both hooks installed
- **THEN** `main` moves and the success line of design D12 is printed

### Requirement: The install script installs six hooks
The system SHALL make `tools/install_hooks.sh` install `pre-merge-commit` and `reference-transaction` as relative links like the four existing hooks, and `--verify` SHALL report all six.

#### Scenario: Verify
- **WHEN** the install script runs then `--verify` runs in a temporary repository
- **THEN** six links are reported in place

### Requirement: The commit-msg hook runs its scanner from the hook's own folder
The system SHALL make the commit-msg hook resolve its own real path, through the link of the common git folder, and run the personal-identifier scanner from the tools folder next to that path. It SHALL NOT run the scanner from the top level or the tools folder of the committing worktree. Whatever a worktree holds, the scanner that runs is the workspace copy (correction 8 of the level-1 framing, design D5 of change session-guard-n1).

#### Scenario: Worktree copy altered
- **WHEN** a worktree's copy of the scanner is changed to accept every message, and a commit in that worktree carries a personal identifier in its message
- **THEN** the hook runs the workspace copy and refuses the commit

#### Scenario: Ordinary message
- **WHEN** a commit in a worktree carries a message without a personal identifier
- **THEN** the hook accepts it

Source: untested until implemented (tests/hooks, task 8.1)

### Requirement: The commit-msg scanners run under an isolated interpreter
The system SHALL make the commit-msg hook launch both its scanners with `python3 -I`. It SHALL NOT launch them by `python3` without `-I` (design D5 of change session-guard-n1).

#### Scenario: Isolated interpreter
- **WHEN** the commit-msg hook launches either of its scanners
- **THEN** it launches it with `python3 -I`, so that no `PYTHON*` variable of the committing session changes the modules it loads

Source: untested until implemented (tests/hooks, task 8.4); decision R-20261108-04, point 2 (a)
