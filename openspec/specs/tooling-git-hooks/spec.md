# tooling-git-hooks Specification

## Purpose
Git hooks, installed from a tracked folder, that protect confidentiality at commit time (pre-commit for sensitive names, commit-msg for personal identifiers), require a green test run of what is committed (pre-commit) and of what is pushed to `main` (pre-push), and optionally trigger the posture evaluation run after a commit (post-commit).

## Requirements

### Requirement: A script installs the hooks as relative links
The system SHALL provide an installer that links the pre-commit, post-commit, commit-msg and pre-push hooks of the repository's tracked hooks folder into the repository's git hooks folder with relative symbolic links, makes the sources executable, and verifies the result. It SHALL be safe to run again (a correct link is left untouched), SHALL move a different existing hook aside instead of deleting it, SHALL repair a wrongly aimed link, SHALL exit non-zero and name a missing source hook, and SHALL offer a verify-only mode that changes nothing. It SHALL NOT delete an existing hook. It SHALL stop with an error, linking nothing, outside a git repository or when the repository's hooks folder is not the standard one that the relative links assume.

#### Scenario: Fresh install
- WHEN the installer runs on a repository without the links
- THEN each of the four hooks is a relative link to its tracked source, executable, and the output says all hooks are in place

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

### Requirement: Only the real workspace reacts
The system SHALL ignore commits made in any repository other than the real workspace location, so temporary copies used by evaluations do not trigger runs.

#### Scenario: Temporary copy
- WHEN a commit happens in a repository outside the real workspace path
- THEN nothing is started

Source: tests/hooks/test_post_commit.sh

### Requirement: Commit-msg hook refuses personal identifiers
The system SHALL, when installed as the repository commit-msg hook, run the personal-identifier scanner on the commit message, without its comment lines, and refuse the commit when the message contains an identifier, SHALL report that the message contains an identifier without printing the identifier nor the message text, and SHALL let a clean message commit.

#### Scenario: Message with an identifier
- WHEN a commit message contains an identifier and git commit runs
- THEN the commit is refused, and the output contains neither the identifier nor the message text

#### Scenario: Clean message
- WHEN a commit message contains no identifier
- THEN the commit succeeds

#### Scenario: Scanner cannot run
- WHEN the scanner exits with an error code other than a finding
- THEN the commit is refused and the output says the message could not be checked

#### Scenario: Identifier on a comment line
- WHEN the identifier appears only on a comment line of the message file
- THEN the commit succeeds

Source: tests/hooks/test_commit_msg.sh

### Requirement: Pre-commit requires a green run of the index, complete on main
The system SHALL make the pre-commit hook refuse a commit on `main` or on a detached head when the complete-run fingerprint is absent or differs from the fingerprint of the index, with the current message asking to run the runner first. On any other branch, the hook SHALL accept the commit when either the complete-run fingerprint or the targeted-run fingerprint equals the fingerprint of the index, and SHALL otherwise refuse with a message asking to run the runner's targeted option after `git add`. The documented owner bypass variable SHALL skip this check only. The hook SHALL NOT accept a targeted fingerprint on `main` or on a detached head, and the sensitive-names check SHALL apply in every case.

#### Scenario: Branch with a matching targeted fingerprint
- **WHEN** a commit is attempted on a work branch and the targeted fingerprint equals the index fingerprint
- **THEN** the green-run check passes

#### Scenario: Main with only a targeted fingerprint
- **WHEN** a commit is attempted on `main` and only the targeted fingerprint matches the index
- **THEN** the commit is refused and the message asks for the complete run

#### Scenario: Branch without fingerprint
- **WHEN** a commit is attempted on a work branch and no fingerprint matches the index
- **THEN** the commit is refused and the message names the targeted option

#### Scenario: Index changed after the targeted run
- **WHEN** a file is staged after the targeted green run
- **THEN** the commit is refused

#### Scenario: Owner bypass
- **WHEN** the bypass variable is set
- **THEN** the green-run check is skipped and the sensitive-names check still applies

#### Scenario: Commit of all tracked changes
- **WHEN** a commit stages tracked changes itself at commit time, so that the index it commits has no recorded fingerprint
- **THEN** the commit is refused; it is accepted when the index was already green before

#### Scenario: Detached head
- **WHEN** a commit is attempted on a detached head with only the targeted fingerprint matching
- **THEN** the commit is refused

Source: tests/hooks/test_pre_commit_green.sh; the sensitive-names check under the bypass: tests/hooks/test_pre_commit.sh (which sets the bypass)

### Requirement: Pre-push requires a green complete run of the pushed main
The system SHALL provide a pre-push hook that, for each pushed reference updating the remote `main`, accepts the push when the complete-run fingerprint equals the tree of the pushed commit; when it does not, and the working tree is clean and the current head is the pushed commit, the hook SHALL run the complete runner itself, without the variable reserved to git commit, and accept only on a green run; otherwise it SHALL refuse with a message saying that `main` requires a complete green run of the pushed tree. Pushes of other references, and deletions of remote references, SHALL pass unchecked. The runner command SHALL be replaceable through an environment variable for the hook's tests. The owner bypass variable of the green-run check SHALL skip this check. The hook SHALL NOT run tests on a tree other than the pushed one, and SHALL NOT accept a targeted fingerprint.

#### Scenario: Matching fingerprint
- **WHEN** `main` is pushed and the complete-run fingerprint equals the pushed tree
- **THEN** the push proceeds without running tests

#### Scenario: No fingerprint, clean tree at the pushed commit
- **WHEN** `main` is pushed, no fingerprint matches, the tree is clean and the head is the pushed commit
- **THEN** the hook runs the complete runner and the push proceeds only if it passes

#### Scenario: No fingerprint, other state
- **WHEN** `main` is pushed, no fingerprint matches and the working tree is dirty or the head differs from the pushed commit
- **THEN** the push is refused with the message

#### Scenario: Work branch
- **WHEN** a work branch is pushed
- **THEN** the hook does not check anything

#### Scenario: Targeted fingerprint only
- **WHEN** `main` is pushed and only the targeted fingerprint equals the pushed tree, and the runner fails
- **THEN** the push is refused

#### Scenario: Another commit pushed to main
- **WHEN** a commit that is not the current head is pushed to the remote `main` without a matching fingerprint
- **THEN** the push is refused without running the runner; with the owner bypass variable it proceeds

#### Scenario: Remote branch deletion
- **WHEN** a push deletes a remote work branch
- **THEN** the hook does not check anything

Source: tests/hooks/test_pre_push.sh

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
