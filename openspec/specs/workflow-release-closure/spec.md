# workflow-release-closure Specification

## Purpose
TBD - created by archiving change release-closure. Update Purpose after archive.

## Requirements

### Requirement: A release closure starts with the session's end checks
The system SHALL start the closure of a release only when every end check of design D2 passes (workspace, ready list, worktrees, run tree, active changes, queue check). While a check fails, the session SHALL NOT triage, draft the notes, request the export review or write the decision file, and SHALL NOT remove a worktree, a branch or a finish lock to make a check pass. Untested until implemented.

#### Scenario: A change still active
- **WHEN** a feature of the milestone names a change that `openspec list` still shows as active
- **THEN** the session reports the failed check with its cause and starts no other closure step

#### Scenario: All checks pass
- **WHEN** every end check passes
- **THEN** the session starts the triage, the notes, the next-release branch and the weeding report

### Requirement: The session triages the milestone through the write tool only
The system SHALL leave no open issue in the milestone of the release before the decision file: each open feature, task or idea is closed through the write tool, or moved to the next release with a reason posted as a comment. The session SHALL NOT use a direct `gh` write, SHALL NOT move a closed feature out of its milestone, and SHALL NOT move silently an item the author placed in the release: such a move is listed in the decision file as applied and revocable. Untested until implemented.

#### Scenario: Unfinished feature
- **WHEN** an open feature of the milestone is not done
- **THEN** the session moves it and its sub-issues to the next release with `edit --milestone`, posts the reason, and lists the move in the decision file

#### Scenario: Triage complete
- **WHEN** the triage ends
- **THEN** the release-notes command of the milestone prints no `not listed: <n> open feature(s)` line

### Requirement: The session drafts the public release notes in English
The system SHALL draft the public notes from the reader's public release-notes command of the milestone, translated into English, holding only the closed features labelled `edition:public`, written to the notes file named by the publication tool, outside both repositories, and quoted with their SHA-256 in the decision file. The session SHALL NOT add another line (except under the next requirement), write the notes into a repository, or create a release. Untested until implemented.

#### Scenario: Notes ready for validation
- **WHEN** the milestone holds three closed features, one labelled `edition:public`
- **THEN** the notes hold that feature only, in English, and the decision file quotes their text and fingerprint

### Requirement: The session labels the published closed features before drawing the notes
Before drawing the public notes, the system SHALL label `edition:public`, through the write tool, every closed feature of the milestone whose changed paths the manifest publishes, without showing the list first, and SHALL list them in the closure decision file, which the author reads before any publication and where he can have a label removed. The automatic check (idea #757) is a follow-up, not required. Untested until implemented.

#### Scenario: Closed feature with published paths, unlabelled
- **WHEN** a closed feature of the milestone changed a path that the manifest publishes and carries no `edition:public` label
- **THEN** the session labels it before running the public release-notes command, and the decision file lists it

#### Scenario: Closed feature with no published path
- **WHEN** a closed feature changed only paths the manifest excludes
- **THEN** the session does not label it and the notes do not hold it

### Requirement: Any notes line outside the public features needs an explicit decision of the author
The system SHALL write in the public notes a line that is not a closed `edition:public` feature only when an explicit decision of the author, written in the register, names that line for the release, and the decision file SHALL list it under the notes with its register key. Untested until implemented.

#### Scenario: Line decided by the author
- **WHEN** the author decided in the register a notes line that is no closed public feature for the release
- **THEN** the notes hold that line and the decision file lists it under the notes with its register key

### Requirement: The session switches the current release before the export review
The system SHALL set the current-release setting to the next release, and update the documentation's current-release mentions, in one branch of the session merged by a train before the export review, so that the published commit already carries the switch. The session SHALL NOT edit the setting in the workspace outside a branch, and the step script SHALL NOT read the milestone of the release from the setting. Untested until implemented.

#### Scenario: Switch merged
- **WHEN** the next-release branch has merged
- **THEN** the commit to publish is the new tip of `main` and the queue check exits 0

### Requirement: The session never generates the edition nor reads the names list
The system SHALL keep the edition generation and the full names check in the author's step script, through the publication tool. The session SHALL NOT run the generator (with or without tests) nor the publication tool; its permitted route is the edition suites on fakes and the read-only reviewed-paths computation. It SHALL NOT read the names list, the product-version list, the content folders or a line the generator reported. Untested until implemented.

#### Scenario: Finding at publication
- **WHEN** the generator reports a sensitive name in the author's run
- **THEN** the script stops before any commit, the report holds a path and a line number only, and the session does not open that line

### Requirement: The Opus review of the export reads the reviewed paths at a pinned commit
The system SHALL review on Opus, before the publication, every path the publication will add, change or delete, read at the pinned commit from the reviewed-paths list of design D6, with findings by path and line and no suspected sensitive value quoted. The session SHALL NOT write in the public copy or its Git folder, nor request the go-ahead with a verdict other than publishable. Untested until implemented.

#### Scenario: File changed since the last publication
- **WHEN** a file published by an include rule has a blob at the pinned commit that differs from the public copy's
- **THEN** its path is in the reviewed-paths list and the review reads it

#### Scenario: Correction needed
- **WHEN** the review's verdict is "à corriger"
- **THEN** the correction goes through a branch and a train, and the pinned commit and the review are redone

### Requirement: The session reads the public copy without a refused Git command
Until the decision of #752 on the public copy's hooks, the system SHALL compute the reviewed paths by reading the files of the public copy, without Git, when the session guard refuses Git commands there (design D6); this requirement falls with that decision. The session SHALL NOT retry a refused Git command in the copy in another form. Untested until implemented.

#### Scenario: Copy without hooks
- **WHEN** the public copy has no hook links installed
- **THEN** the session compares the copy's files with the sources at the pinned commit and runs no Git command in the copy

### Requirement: An audit's public-tree review shortens the export review only when it covers confidentiality
When a security audit of the same release reviewed the public tree at a frozen commit, the system SHALL compute the reviewed paths against that commit only when the Opus export review records the audit's verdict as covering names, internal paths and the content of `internes/` and of the author's private step folder. Otherwise it SHALL compute them against the public copy. The session SHALL NOT shorten the review on an uncovered point. Untested until implemented.

#### Scenario: Internal paths not covered
- **WHEN** the audit's public-tree verdict does not cover internal absolute paths
- **THEN** the review file says `non couvert` for that point and the reviewed paths are computed against the public copy

### Requirement: The author's decisions of a closure are in one file
The system SHALL gather the author's decisions of a closure in one decision file with the three sections of design D9: release-specific decisions, validation of the notes, go-ahead. The session SHALL NOT ask a closure decision in another file, and SHALL NOT fill the variables of the step script before a go-ahead and validated notes. Untested until implemented.

#### Scenario: Go-ahead given
- **WHEN** the author answers yes to the go-ahead and validates the notes
- **THEN** the session fills the script variables, has the script reviewed on Opus and adds one line to the action queue

#### Scenario: No go-ahead
- **WHEN** the author answers no
- **THEN** no step file line enters the action queue

### Requirement: The author runs one step file whose script is reviewed on Opus
The system SHALL give the author one step file per release and its zsh script, written and reviewed on Opus after the end of the release's security audit when there is one and before its action-queue line, with the mechanics of design D10 (refusal in a session, traps that always write the report, a report readable by its owner only). The script SHALL ask exactly one question and SHALL NOT run in a session, nor commit, push, tag or release before an `o`. Untested until implemented.

#### Scenario: Launched in a session
- **WHEN** the script starts in a Claude Code session
- **THEN** it prints the refusal phrase of design D13, exits 1 and changes nothing

#### Scenario: Answer n
- **WHEN** the author answers `n` to the question
- **THEN** the public copy is put back to its published state, nothing is committed, pushed or released, and the exit code is 0

### Requirement: The script runs its steps in a fixed order and stops at the first failure
The system SHALL run the script's steps in the order of design D11 and stop at the first failure with the code of design D13, before any commit when the failure comes before the question. The script SHALL NOT publish from a workspace `main` other than the pinned commit, nor a staged path absent from the reviewed-paths list or under `_bmad-output/pmzilla/internes/` or the author's private step folder. Untested until implemented.

#### Scenario: Main moved after the review
- **WHEN** the workspace `main` is not the pinned commit
- **THEN** the script exits 1 with `clôture <M> : refusée :` and its cause, and runs nothing

#### Scenario: Staged path not reviewed
- **WHEN** the publication tool stages a path that the reviewed-paths list does not hold
- **THEN** the script restores the public copy, exits 5 and nothing is committed

#### Scenario: Name in the notes
- **WHEN** the names check finds a name in the notes file
- **THEN** the script exits 6, prints the file and the line, never the name, and nothing is published

### Requirement: The posture closure trial is skipped only when validating records cover the pinned commit
The script SHALL skip the paid posture closure trial when complete validating records with the evaluated-files fingerprint of the pinned commit cover both the default set and the context cases (design D12), and SHALL run it otherwise, including when coverage cannot be established. The decision file SHALL say which case applies and the cost when it runs. The script SHALL NOT publish after a run that is not validating. Untested until implemented.

#### Scenario: Records cover the pinned commit
- **WHEN** validating records of the default set and of the context cases carry the fingerprint of the pinned commit
- **THEN** the script prints `jeu d'essai de clôture : sauté` with their dates and runs no paid evaluation

#### Scenario: Context cases not covered
- **WHEN** only the default set has a validating record with that fingerprint
- **THEN** the script runs the trial and prints `jeu d'essai de clôture : lancé`

#### Scenario: Trial not validating
- **WHEN** a record of the trial is not validating
- **THEN** the script exits 3 and nothing is published

### Requirement: The script closes the milestone only when no issue is open
After the release, the script SHALL close the milestone of the release when it holds no open issue, and otherwise SHALL leave it open, exit 9 and report the count. The write tool SHALL keep closing no milestone, and the session SHALL NOT close a milestone by any route. Untested until implemented.

#### Scenario: Leftover issue
- **WHEN** the milestone still holds one open issue after the release
- **THEN** the milestone stays open, the script exits 9 with `jalon <M> non fermé : 1 issue(s) ouverte(s)`, and the release is kept

### Requirement: A relaunch resumes without repeating a push or a release
When relaunched after a push or a release, the script SHALL read the state from the public repository and resume at the first step not done. It SHALL NOT push the same commit twice, SHALL NOT create a second release for the same tag, and SHALL NOT create a tag outside the release command. Untested until implemented.

#### Scenario: Release failed after the push
- **WHEN** the script exited 8 and is relaunched
- **THEN** it creates the release without a new commit or push

### Requirement: Each new closure rule states what it replaces and when it falls
The system SHALL state, for the closure procedure, the staged-paths check, the names check of the notes, the posture closure trial and the switch of the current release, what each replaces and its removal condition (design D15), and SHALL NOT keep a hand-kept closure list of a release beside the procedure. Untested until implemented.

#### Scenario: Next release
- **WHEN** the next release closes
- **THEN** no `cloture-<release>.md` checklist is written: the decision file, the step file and the register line of design D9, D10 and D14 hold the closure
