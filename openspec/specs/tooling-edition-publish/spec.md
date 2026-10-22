# tooling-edition-publish Specification

## Purpose
A publication tool, run by the user in the Terminal, that checks the local copy of the public repository without network, builds the edition tree with the generator in the same run, replaces the content of the copy while keeping its Git history, verifies and stages it, prints a summary of the differences with the published version and the commands to commit, push and release. It never commits, pushes, fetches, tags or creates a release.

## Requirements

### Requirement: A publication tool run by the user prepares the public copy
The system SHALL provide a private-repository publication tool that the user runs in the Terminal with a required public-copy folder option and an optional commit that defaults to the current head of the private workspace. It SHALL accept no option that skips the test run, skips a check or tolerates a file.

#### Scenario: Missing copy option
- **WHEN** the tool is started without the public-copy option
- **THEN** it exits with code 2 and changes nothing

#### Scenario: Skip option refused
- **WHEN** the tool is started with an option that would skip the test run
- **THEN** it exits with code 2 and no build starts

### Requirement: The publication tool runs its steps in a fixed order
The system SHALL exit with code 2 on a usage error and run its steps in the order of design D4: usage, public copy checks, build, sync, summary. Exit codes and key phrases are those of design D4 and D17.

#### Scenario: Copy refused before the build
- **WHEN** the public copy is refused
- **THEN** the generator is not called

### Requirement: The public copy is checked before any build, without network
The system SHALL refuse the public copy with exit code 9 and the key phrase "public copy refused:" followed by the cause of design D3. The checks SHALL read local Git state only. On a refusal the system SHALL NOT start a build and SHALL NOT change the copy. The system SHALL NOT fetch, pull or clone to make a check pass.

#### Scenario: Copy on another branch
- **WHEN** the copy's head is on a branch other than `main`
- **THEN** the tool exits with code 9, prints "public copy refused: not on main", and the generator is not called

#### Scenario: Wrong remote
- **WHEN** the copy's `origin` points to another repository
- **THEN** the tool exits with code 9 and the copy is unchanged

#### Scenario: Ignored file in the copy
- **WHEN** the copy holds a file that its ignore rules match
- **THEN** the tool exits with code 9, the cause is "ignored files present", and the file is not deleted

#### Scenario: Local main ahead of origin
- **WHEN** local `main` has a commit that `origin/main` does not have
- **THEN** the tool exits with code 9 and the cause is "main differs from origin/main"

#### Scenario: Copy inside the workspace
- **WHEN** the copy folder lies inside the private workspace
- **THEN** the tool exits with code 9 and writes nothing

#### Scenario: Missing, not a repository, dirty
- **WHEN** the copy folder is missing, is not the top of a Git work tree, or holds a modified, staged or untracked non-ignored file
- **THEN** the tool exits with code 9 with the cause "missing", "not a Git repository" or "working tree not clean"

### Requirement: The published tree is built in the same run, with the full test run
The system SHALL obtain the tree by calling the edition generator in the same run, from the given commit, with the test-run option always set, into a build folder that is a sibling of the copy. On a generator exit code other than 0, the system SHALL exit with that code, relay the generator's lines unchanged and leave the copy unchanged.

#### Scenario: Finding in the tree
- **WHEN** the generator exits with code 7
- **THEN** the tool exits with code 7, the generator's finding lines are printed, the copy is unchanged and the not-publishable tree is kept

#### Scenario: Red tests
- **WHEN** the full runner is red in the generated tree
- **THEN** the tool exits with code 1 and the copy is unchanged

#### Scenario: Leftover build folder
- **WHEN** the build folder or its not-publishable sibling already exists
- **THEN** the tool exits with code 4 and the copy is unchanged

### Requirement: Only a tree built in the run is synced
The system SHALL NOT take a tree built by an earlier run, SHALL NOT sync a not-publishable tree, and SHALL delete the build folder after the sync, whatever its outcome.

#### Scenario: Build folder removed
- **WHEN** the sync ends, verified or restored
- **THEN** the build folder no longer exists

### Requirement: Sync keeps the Git history of the public copy
The system SHALL replace every entry of the copy except its Git folder by the checked tree, keeping bytes, executable bits and symbolic links, so that the copy holds exactly the tree. The system SHALL NOT change the Git folder, the history, the branches, the remotes or the Git configuration of the copy, and SHALL NOT keep in the copy a file that the tree does not hold.

#### Scenario: File removed from the edition
- **WHEN** a file of the published version is absent from the new tree
- **THEN** it is absent from the copy after the sync and appears as deleted in the summary

#### Scenario: History kept
- **WHEN** the sync completes
- **THEN** the copy's commits, branches and remotes are those of before the sync

### Requirement: The copy is verified after the sync
The system SHALL compare the copy, Git folder excluded, with the checked tree after the sync: paths, bytes, executable bits and link targets. Any difference or sync error SHALL be a sync failure. The system SHALL NOT stage or summarise a copy that differs from the checked tree. Untested until implemented.

#### Scenario: Copy differs after the sync
- **WHEN** a file of the copy differs from the tree after the sync
- **THEN** nothing is staged and no summary is printed

### Requirement: A failed sync restores the published state
On a sync failure, the system SHALL restore the copy to its `HEAD`, exit with code 10 and print "sync failed; public copy restored to" followed by the short commit id. When the restore fails, the system SHALL exit with code 11, print "sync failed and the public copy could not be restored:" and the commands the user runs, and SHALL run nothing else.

#### Scenario: Restored copy
- **WHEN** a file of the copy differs from the tree after the sync
- **THEN** the tool exits with code 10 and the copy's work tree and index equal its `HEAD`

#### Scenario: Restore impossible
- **WHEN** the restore fails
- **THEN** the tool exits with code 11 and prints the commands to run

### Requirement: The tool stages and summarises the differences
The system SHALL stage every change of the verified copy and print a summary of the differences between the staged state and the copy's `HEAD`, with the content of design D10. It SHALL print "CHANGELOG unchanged since the published version" when the edition CHANGELOG did not change, as a warning that does not change the exit code. When nothing differs, it SHALL print "nothing to publish: the tree equals the published version" and exit 0 with a clean index.

#### Scenario: Changes to publish
- **WHEN** the tree adds one file and modifies another
- **THEN** the summary counts one added and one modified file, lists both paths, the copy's `HEAD` is unchanged and the exit code is 0

#### Scenario: Nothing to publish
- **WHEN** the tree equals the published version
- **THEN** the tool prints "nothing to publish", nothing is staged and the exit code is 0

#### Scenario: CHANGELOG not updated
- **WHEN** the tree changes files but not the edition CHANGELOG
- **THEN** the warning is printed and the exit code is 0

### Requirement: The summary holds no content and no private id in the copy
The system SHALL NOT print file content, and SHALL NOT write the private commit id into the copy.

#### Scenario: No content printed
- **WHEN** a changed file contains a sentinel string
- **THEN** the output does not contain it

### Requirement: The tool ends with the user's commands
The system SHALL end with the commands the user runs to read, commit and push, then the release lines of design D11 when something is published, then the line "ready to commit in" the copy with "nothing was committed or pushed". The system SHALL NOT commit, create a release or a tag, or run the reader or `gh`.

#### Scenario: Commit and push left to the user
- **WHEN** the tool exits with code 0 after staging changes
- **THEN** the copy's `HEAD` is unchanged and its remote-tracking branch is unchanged

### Requirement: The release lines name the milestone and a free tag
The release lines SHALL hold the reader's public release-notes command for the milestone of the current-release setting, the translation and review step, and the release command whose title is that milestone and whose tag is its lower-case name, with the first free numbered suffix when the copy's local tags already hold it. Without a current release, the system SHALL print "no current release; release lines skipped" without changing the exit code.

#### Scenario: Release lines
- **WHEN** the current release is `Namazu`, the copy holds no tag `namazu` and the tree changes files
- **THEN** the last commands include the public release-notes command for `Namazu` and a release command with the title `Namazu` and the tag `namazu`, and no release is created

#### Scenario: Tag already present
- **WHEN** the copy already holds the tags `namazu` and `namazu-2`
- **THEN** the release command uses the tag `namazu-3`

#### Scenario: No current release
- **WHEN** the current-release setting is empty
- **THEN** the tool prints "no current release; release lines skipped" and the exit code is 0

#### Scenario: Nothing published
- **WHEN** the tree equals the published version
- **THEN** no release line is printed

### Requirement: The publication tool never publishes, installs or evaluates
The publication tool SHALL NOT commit, push, fetch, pull or clone; add, change or remove a remote; create a repository; rewrite history, force an update or bypass a hook; launch the install script or an evaluation set; run the real Jira tools, the database scripts or the import and compare tools; connect to the database or make any network call.

#### Scenario: Forbidden commands
- **WHEN** the tool's text is scanned outside comments
- **THEN** it contains no commit, push, fetch, pull, clone, remote change, forced update, hook bypass, install-script launch or evaluation-set launch

### Requirement: The publication tool stays out of the edition
The tool and its test suite SHALL be excluded from the edition by the manifest; the product-version list is untracked and never enters it.

#### Scenario: Not in the edition
- **WHEN** a tree is built
- **THEN** it holds neither the publication tool nor its test suite
