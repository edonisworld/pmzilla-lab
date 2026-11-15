# workflow-github-issues Specification

## Purpose
PMZilla Lab's work queue lives in the issues of its GitHub repository; this capability defines how those issues are written (created, edited, commented, closed, linked and labelled) only through the write tool `tools/gh_issue.py`, never by a direct `gh` write, and with no name of a person, team, Jira project or domain.

## Requirements

### Requirement: One tool writes to GitHub
The system SHALL provide a write tool that is the only way the repository and the session create, edit, close or reopen an issue, add a comment, a sub-issue, a "blocked by" relation, a label, a milestone, a Project Status or Horizon, set a milestone's description and due date, and remove a "blocked by" relation, a sub-issue link or an issue's milestone on GitHub. It SHALL write only to the repository of `origin`, through the user's `gh` authentication. Codes and messages: design D7, D9.

#### Scenario: Other repository
- **WHEN** the tool is asked to write to a repository other than the one of `origin`
- **THEN** it exits with code 2 and sends nothing

#### Scenario: Relation removed
- **WHEN** `unblock R-2 --by R-1` runs on a feature R-2 blocked by R-1
- **THEN** the relation is removed, and a second run says `nothing to do`

Source: tests/gh_issue/test_gh_issue.py (Depot; Relations: test_block_et_unblock)

#### Scenario: Horizon through the tool
- **WHEN** the Horizon of an idea is set
- **THEN** the request is sent by the write tool through its own Project requests, after the guard, and no session command calls `gh api`

### Requirement: The write tool deletes only relations and sub-issue links
Removing a "blocked by" relation, a sub-issue link or an issue's milestone SHALL be the write tool's only removals. It SHALL NOT delete, transfer, lock or pin an issue, SHALL NOT delete a label or a milestone, SHALL NOT change an existing label, SHALL change an existing milestone only in its description and due date, SHALL NOT write to another repository, and SHALL NOT create a release or a tag.

#### Scenario: No delete
- **WHEN** the tool's text is scanned outside comments
- **THEN** it holds no issue, comment, label or milestone deletion, no transfer, no release or tag creation, and its only deletion requests remove a "blocked by" relation or a sub-issue link

Source: tests/gh_issue/test_gh_issue.py (Depot)

#### Scenario: Milestone removed from an issue
- **WHEN** `edit-idea 7 --no-milestone` runs on an idea of milestone `Hydra`
- **THEN** the request empties the idea's milestone and no request deletes or changes the milestone `Hydra`

### Requirement: Features and sub-issues follow the queue model
The system SHALL create a feature with the title `R-<n> · <title>`, the labels `type:feature` and `theme:<theme>`, a milestone, an identity marker and a valid `roadmap` block (design D1, D5), placed in the Project with a Status. A new feature SHALL receive the next free identifier, the highest identifier among all issues plus one.

#### Scenario: New feature
- **WHEN** the highest identifier among open and closed issues is `R-64` and a new feature is created
- **THEN** it is titled `R-65 · <title>`, carries the marker and the block, and its Status is `Todo`

Source: tests/gh_issue/test_gh_issue.py (Features)

### Requirement: Sub-issues come only from the tagged groups of the change
The system SHALL create sub-issues only from the tagged groups of the `tasks.md` of the unarchived change named in the feature's block (design D3): one `type:task` sub-issue with one model label per agent group, plus `parallel` when tagged; one `owner:user` sub-issue per user group and per user task of an agent group. A sub-issue body SHALL hold the change and the group or task number, never the text of a task.

#### Scenario: Mixed group
- **WHEN** an agent group tagged `[model: sonnet]` holds one task tagged `[user]`
- **THEN** sync creates one `type:task` sub-issue with `model:sonnet` and one `owner:user` sub-issue for that task

Source: tests/gh_issue/test_gh_issue.py (Sync: test_groupe_mixte_et_etiquettes, test_corps_sans_texte_des_taches)

### Requirement: The task sync refuses an untagged group and a missing or archived change
The system SHALL refuse a change with an untagged numbered group, exit 7 and print `tasks.md groups untagged:` with the group numbers. The task sync SHALL exit 7 and write nothing when the feature names no change, when the change's `tasks.md` is not found, or when the change is archived (`change archived`).

#### Scenario: Untagged group
- **WHEN** a numbered group of the change has no model tag and no user tag
- **THEN** the tool exits with code 7, names the group and creates nothing

#### Scenario: Missing change
- **WHEN** the feature's block names no change, or a change whose `tasks.md` does not exist
- **THEN** the task sync exits with code 7 and creates nothing

#### Scenario: Archived change
- **WHEN** the feature's block names a change found only in the archive
- **THEN** the task sync exits with code 7 with `change archived` and sends no write, while `close-feature` on that feature closes it without a sync

Source: tests/gh_issue/test_gh_issue.py (Sync: test_groupe_sans_tag, test_feature_sans_change_ou_change_introuvable, test_sync_refuse_un_change_archive; Fermeture: test_change_archive_ne_bloque_pas)

### Requirement: Writes are idempotent
The system SHALL find an existing issue by its identity marker before creating one, and SHALL NOT create a second issue with the same marker, add a relation or a label already present, or create a label or milestone that exists; in those cases it SHALL print `already exists: <key> (#<number>)` or `nothing to do` and exit 0.

#### Scenario: Second sync
- **WHEN** the task sync runs twice on the same `tasks.md`
- **THEN** the second run sends no creation and says `nothing to do`

Source: tests/gh_issue/test_gh_issue.py (Sync: test_deuxieme_passage_ne_fait_rien; Idempotence; Relations: test_block_et_unblock)

### Requirement: Sub-issues and features close only when complete
The system SHALL close a group sub-issue when its tasks are all ticked and a user-task sub-issue when its task is ticked, and reopen one whose task was unticked unless it was closed with a reason. A feature SHALL close only when none of its sub-issues is open; otherwise the tool SHALL exit 7 with `open sub-issues remain:` and change nothing.

#### Scenario: Group fully ticked
- **WHEN** every task of group 4 is ticked
- **THEN** the sync closes the group-4 sub-issue and no other

#### Scenario: User step still open
- **WHEN** the feature is closed while a user-step sub-issue is open
- **THEN** the tool exits with code 7, names that sub-issue and the feature stays open

#### Scenario: Feature closed
- **WHEN** the only blocker of a `Todo` feature is closed through the tool
- **THEN** that feature is listed as unblocked and its Status stays `Todo`

#### Scenario: Unticked task reopens its sub-issue
- **WHEN** a task of a closed group sub-issue is unticked and that sub-issue was not closed with a reason
- **THEN** the sync reopens it

#### Scenario: Sub-issue closed with a reason stays closed
- **WHEN** an agent sub-issue was closed by close-step with a reason and its group still holds an unticked task
- **THEN** the sync does not reopen it

Source: tests/gh_issue/test_gh_issue.py (Sync: test_groupe_coche_ferme_seulement_lui, test_tache_utilisateur_cochee_ferme_sa_sous_issue_puis_decochee_la_rouvre; Fermeture)

### Requirement: User steps and agent sub-issues closed with a reason close only through close-step
User-step sub-issues, and agent sub-issues closed with a reason, SHALL close only through close-step after the user's confirmation; the sync SHALL list a ticked user group as ready to close after the user's confirmation, without closing it. close-step on a user-step sub-issue SHALL close it without a reason, and say `nothing to do` when it is already closed.

#### Scenario: User group ticked
- **WHEN** every task of a user group is ticked and the sync runs
- **THEN** the user-group sub-issue stays open and the output says `ready to close after your confirmation:` with its key

#### Scenario: User step closed by close-step
- **WHEN** close-step runs without a reason on an open user-step sub-issue, then runs again
- **THEN** the first run closes it and posts no comment, and the second says `nothing to do`

Source: tests/gh_issue/test_gh_issue.py (Sync: test_groupe_utilisateur_ne_se_ferme_pas_par_la_synchronisation, test_close_step; CloseStepAvecRaison: test_etape_utilisateur_sans_raison_comme_avant)

### Requirement: Dependencies stay acyclic
The system SHALL refuse a "blocked by" relation that targets the feature itself or that would create a cycle, with exit code 7 and `dependency cycle:` followed by the identifiers of the cycle. A target given as a sub-issue key SHALL be a usage error, exit code 2. An unknown target SHALL exit with code 7 and `unknown identifier` followed by that identifier. In each case no relation SHALL be added and no write sent.

#### Scenario: Cycle
- **WHEN** R-2 is blocked by R-1 and the tool is asked to make R-1 blocked by R-2
- **THEN** it exits with code 7, names both features and adds no relation

#### Scenario: Indirect cycle
- **WHEN** R-2 is blocked by R-1, R-3 by R-2, and the tool is asked to make R-1 blocked by R-3
- **THEN** it exits with code 7 with `dependency cycle: R-1 -> R-3 -> R-2 -> R-1`

#### Scenario: Sub-issue as target
- **WHEN** the target of the relation is a sub-issue key such as `R-1/g1`
- **THEN** the tool exits with code 2

#### Scenario: Unknown target
- **WHEN** the target is an identifier that no feature has
- **THEN** the tool exits with code 7 with `unknown identifier` and that identifier, and sends no write

Source: tests/gh_issue/test_gh_issue.py (Relations)

### Requirement: Offline, nothing is written later
The system SHALL exit with code 5 and `GitHub unreachable; nothing was sent` when GitHub cannot be reached or `gh` is not authenticated before any write of the command was attempted, and with code 6 when the token lacks the Project scope or the Project lacks a Status option, printing the command the user runs in the Terminal. It SHALL NOT keep a request to send later and SHALL NOT write from the reader's cache.

#### Scenario: Unreachable
- **WHEN** `gh` fails to reach GitHub before any write of the command
- **THEN** the tool exits with code 5 and records nothing to replay

#### Scenario: Missing scope
- **WHEN** the token has no Project scope and a Status is set
- **THEN** the tool exits with code 6 and prints `gh auth refresh -s project` for the user

#### Scenario: Unreachable after a write
- **WHEN** GitHub cannot be reached after a write of the command was attempted
- **THEN** the tool does not exit with code 5 and does not print `nothing was sent`

### Requirement: GitHub calls are bounded in time
The system SHALL run every `gh` call with its standard input closed when nothing is sent on it, with prompts disabled and with a configurable time limit, and SHALL stop waiting on rate limits once a configurable total wait per command is reached. It SHALL NOT wait without a bound, in any subcommand, task sync included.

#### Scenario: Read that never answers
- **WHEN** `gh` gives no answer to the first read of `sync-tasks` within the time limit
- **THEN** the tool exits with code 5 with `GitHub unreachable (no answer within <s> s); nothing was sent`, before any write

#### Scenario: Rate limit over the cap
- **WHEN** GitHub asks to wait longer than the remaining allowed wait, before any write
- **THEN** the tool does not sleep, exits with code 5 and prints `GitHub rate limit:` followed by the wait and `nothing was sent`

#### Scenario: Standard input
- **WHEN** a read is sent to `gh`
- **THEN** `gh` receives a closed standard input and the variable that disables its prompts

### Requirement: Only a scope error is reported as a missing scope
The system SHALL classify a failed `gh` call from its standard error and its response body, never from the response headers, and SHALL give code 6 for a missing Project scope only on GitHub's insufficient-scope error. Any other refusal SHALL keep code 1 and its guarded message.

#### Scenario: Headers list the project scope on another failure
- **WHEN** a call of `close-feature` fails with HTTP 404 and its headers list the token's scopes, `project` included
- **THEN** the tool exits with code 1 with `GitHub refused:` and does not print `missing token scope project`

#### Scenario: Real scope error
- **WHEN** GitHub answers with an insufficient-scope error on a Project request
- **THEN** the tool exits with code 6 and prints `gh auth refresh -s project` for the user

### Requirement: A write without an answer leaves an unknown state
The system SHALL exit with code 8 and the key phrase `state unknown` when a write gets no answer, or when GitHub becomes unreachable or the rate-limit cap is hit after at least one confirmed write. The tool SHALL NOT print `nothing was sent` in these cases nor retry a write whose result is unknown.

#### Scenario: Write that times out
- **WHEN** the request that closes a sub-issue gets no answer within the time limit
- **THEN** the tool exits with code 8, says the last write got no answer, prints the check command, sends no second request for it, and its output holds no `nothing was sent`

#### Scenario: Network lost after two writes
- **WHEN** two writes of `sync-tasks` were confirmed and the next read cannot reach GitHub
- **THEN** the tool exits with code 8 with `state unknown: GitHub unreachable after 2 confirmed write(s)` and the check command

#### Scenario: Network lost before any write
- **WHEN** the first read of the command cannot reach GitHub
- **THEN** the tool exits with code 5 with `GitHub unreachable; nothing was sent`

#### Scenario: Refusal after confirmed writes
- **WHEN** `close-feature` has set the Status `Done` and closed the feature, and a later call is refused
- **THEN** the tool keeps the refusal's code, adds a line saying how many writes were confirmed before the failure with the check command, and its output holds no `nothing was sent`

Source: tests/gh_issue/test_gh_issue.py (Bornes)

### Requirement: The unknown-state message tells how to check
The message of an unknown state SHALL give the number of confirmed writes and the read command that shows the feature; for a command that names no feature, it SHALL say instead to run the same command again, since it is idempotent.

#### Scenario: Command without a feature
- **WHEN** the milestone creation request gets no answer
- **THEN** the tool exits with code 8, says `run the same command again, it is idempotent` and names no read command of the reader

Source: tests/gh_issue/test_gh_issue.py (Bornes)

### Requirement: A new feature is visible before the tool returns
The system SHALL, after creating a feature, re-read the issue list with a bounded number of spaced tries until the feature is listed, and retry its addition to the Project the same way. When it is still not listed, it SHALL exit with code 8, name the identifier and number created and say to wait before the next creation. It SHALL NOT create a second issue for the same identifier.

#### Scenario: Listing lags
- **WHEN** GitHub lists the new feature only at the third read after its creation
- **THEN** the tool sets its Status, prints `created R-<n> (#<number>)` and exits 0, with one creation request

#### Scenario: Never listed
- **WHEN** the new feature is not listed after the last try
- **THEN** the tool exits with code 8, names `R-<n>` and its number, and says to wait before the next `new-feature`

#### Scenario: Identifier above the highest known
- **WHEN** a command names `R-<n>` above the highest identifier listed and the listing shows it at the second read
- **THEN** the command proceeds on it

#### Scenario: Unknown lower identifier
- **WHEN** a command names an unknown identifier below the highest one listed
- **THEN** the tool exits with code 7 with `unknown identifier` at once, without re-reading

### Requirement: Sub-issues carry the milestone of their feature
The system SHALL create every sub-issue with the milestone of its feature, and the task sync SHALL set that milestone on any sub-issue, open or closed, whose milestone differs. Moving a feature to another milestone SHALL move all its sub-issues too. The tool SHALL NOT leave a sub-issue in a milestone other than its feature's.

#### Scenario: Sub-issues created by the sync
- **WHEN** the sync creates the sub-issues of a feature of milestone `Hydra`
- **THEN** each one is created with milestone `Hydra`

#### Scenario: Older sub-issue without milestone
- **WHEN** a sub-issue created before this rule has no milestone and the sync runs
- **THEN** the sync sets the feature's milestone on it, and a second sync says `nothing to do`

#### Scenario: Feature moved
- **WHEN** `edit R-<n> --milestone Namazu` runs on a feature with an open and a closed sub-issue
- **THEN** the feature and both sub-issues end in `Namazu`

### Requirement: Starting a feature moves it to the current release
The system SHALL, when a feature's Status is set to `In progress` and a current release is configured, move the feature and all its sub-issues to that release's milestone before setting the Status. With no release configured, or no settings file, it SHALL move nothing and say so in one line. It SHALL refuse with code 7 and write nothing when the configured release is not an open milestone, and when the settings file is unreadable or invalid.

#### Scenario: Release configured
- **WHEN** the current release is `Namazu` and a `Ready` feature of `Hydra` with two sub-issues is set `In progress`
- **THEN** the tool prints `moved R-<n> and 2 sub-issue(s) to Namazu` and the Status becomes `In progress`

#### Scenario: Already in the release
- **WHEN** the feature and its sub-issues are already in the current release
- **THEN** no move request is sent

#### Scenario: No release configured
- **WHEN** the current-release setting is empty
- **THEN** the tool prints `no current release; milestone unchanged` and sets the Status

#### Scenario: Closed release
- **WHEN** the configured release is a closed milestone
- **THEN** the tool exits with code 7 with `current release <name> is not an open milestone; nothing was sent` and writes nothing

#### Scenario: Invalid settings file
- **WHEN** the settings file holds a key other than the current release
- **THEN** the tool exits with code 7 with `is invalid; nothing was sent`, writes nothing and the Status is unchanged

Source: tests/gh_issue/test_gh_issue.py (ReleaseEnCours)

### Requirement: Closing a feature records it and names its branch
The system SHALL, when it closes a feature, write the closing date into its block, set its Status to `Done`, post one comment naming the current branch, close it as completed and list the open features whose blockers are now all closed, without changing their Status. It SHALL NOT post that comment twice nor when there is nothing to do, and the guard SHALL check the comment before any write.

#### Scenario: Feature closed on a branch
- **WHEN** `close-feature` closes a feature from the branch `chore/r65-fixes`
- **THEN** the feature has its closing date, Status `Done`, state closed as completed, and one comment that names `chore/r65-fixes` and says the merge is pending

#### Scenario: Second run
- **WHEN** `close-feature` runs again on the closed feature
- **THEN** it says `nothing to do` and posts no comment

#### Scenario: Detached head
- **WHEN** the repository is on a detached head
- **THEN** the comment says the feature was closed outside a branch and names the short commit

Source: tests/gh_issue/test_gh_issue.py (CommentaireDeCloture)

### Requirement: An interrupted close posts its missing comment
When a feature was closed by an earlier run that stopped before its comment, a new run SHALL post the missing comment once and change nothing else.

#### Scenario: Interrupted close
- **WHEN** an earlier `close-feature` closed the feature but stopped before posting its comment, and the command runs again
- **THEN** the comment is posted once, the feature stays closed as completed, and a third run says `nothing to do`

Source: tests/gh_issue/test_gh_issue.py (CommentaireDeCloture)

### Requirement: close-feature closes a feature after the merge
The system SHALL let `close-feature R-<n> --after-merge --comment-file F` close a feature whose work is already merged: the comment SHALL be the closing marker and the text of F, checked by the guard before any write, with no "before the merge" sentence. The closing date, Status `Done` and closing as completed SHALL stay as without the options. One option without the other, or a file absent or empty, SHALL exit 2 and send nothing.

#### Scenario: Closing after the merge
- **WHEN** `close-feature R-1 --after-merge --comment-file F` runs on an open feature
- **THEN** R-1 is closed with Status `Done` and one comment holding the marker and the text of F, without "before the merge"

#### Scenario: Option alone
- **WHEN** `close-feature R-1 --after-merge` runs without `--comment-file`
- **THEN** the tool exits 2 and sends no write

Source: tests/gh_issue/test_gh_issue_apres_coup.py (FermetureApresCoup)

### Requirement: close-feature closes a replaced or dropped feature
The system SHALL let `close-feature R-<n> --reason replaced|dropped --comment-file F` close a feature whose work is not merged, as not planned, with the text of F (guarded) as comment. It SHALL NOT set Status `Done`, `done_on` or `edition:public`, and SHALL say which features stay blocked. A missing or empty F, or `--after-merge` or `--edition-public`, SHALL exit 2 and send nothing.

#### Scenario: Feature replaced
- **WHEN** `close-feature R-1 --reason replaced --comment-file F` runs on R-1, which blocks R-2
- **THEN** R-1 is closed as not planned with one comment, its Status is unchanged, and the output says R-2 still blocked

#### Scenario: Open sub-issues
- **WHEN** `close-feature R-1 --reason replaced --comment-file F` runs while a sub-issue of R-1 is open, or on a feature already closed as completed
- **THEN** the tool exits 7 and sends no write

#### Scenario: Replay
- **WHEN** the same command runs again on a feature it closed as not planned
- **THEN** the output says `nothing to do` and no second comment is posted, an older plain closing comment not counting as the reason

Source: tests/gh_issue/test_gh_issue_valeur_remplacee.py (FermetureRemplaceeOuAbandonnee)

### Requirement: detach-sub-issue removes a sub-issue link
The system SHALL let `detach-sub-issue <parent> <child> [--comment-file F]`, each given as `R-<n>` or an issue number, remove the sub-issue link from the parent, then post the text of F on the child. The guard SHALL check F before any write. A child that is not a sub-issue of that parent SHALL exit 7 and send nothing; an unknown issue SHALL exit 7; an ill-formed reference SHALL exit 2.

#### Scenario: Sub-issue detached
- **WHEN** `detach-sub-issue R-1 2 --comment-file F` runs and issue 2 is a sub-issue of R-1
- **THEN** issue 2 is no longer a sub-issue of R-1 and holds one comment with the text of F

#### Scenario: Not a sub-issue
- **WHEN** issue 3 is not a sub-issue of R-1 and `detach-sub-issue R-1 3` runs
- **THEN** the tool exits 7 with `not a sub-issue` and sends no write

Source: tests/gh_issue/test_gh_issue_apres_coup.py (DetacherUneSousIssue)

### Requirement: status sets the Status of an idea
The system SHALL let `status <n|#n> <Status>` set the Project Status of an open `type:idea` issue, with the statuses of a feature, without changing its milestone, body or start date. An unknown status SHALL exit 2; an issue without `type:idea`, unknown or closed SHALL exit 7; none SHALL send a write. The same status again SHALL print `nothing to do`. `status R-<n>` SHALL behave as before.

#### Scenario: Idea in progress
- **WHEN** `status #2 "In progress"` runs on an open idea
- **THEN** its Status is `In progress` and its body and milestone are unchanged

#### Scenario: Closed idea
- **WHEN** `status #2 Ready` runs on a closed idea
- **THEN** the tool exits 7 and sends no write

Source: tests/gh_issue/test_gh_issue_apres_coup.py (StatutDUneIdee)

### Requirement: close-step closes an agent sub-issue only with a reason
The system SHALL let close-step close a sub-issue without the user-step label only when a reason is given; it SHALL post that reason as a comment through the guard, mark it so that the sync does not reopen the sub-issue, then close it. Without a reason it SHALL exit 7, name the sub-issue and change nothing.

#### Scenario: Agent sub-issue with a reason
- **WHEN** `close-step R-<n>/g6 --reason "user step, no test"` runs on an agent sub-issue
- **THEN** one comment holds the reason, the sub-issue is closed, and the next sync leaves it closed

#### Scenario: Agent sub-issue without a reason
- **WHEN** `close-step R-<n>/g6` runs without a reason on an agent sub-issue
- **THEN** the tool exits with code 7 with `is an agent sub-issue; close it with --reason` and sends nothing

#### Scenario: Reason with a sensitive name
- **WHEN** the reason holds a name of the sensitive-names list
- **THEN** the tool exits with code 3 and sends nothing

### Requirement: The write tool changes no existing milestone
The system SHALL hold no code that closes, reopens, renames or deletes an existing milestone; the only change it makes to an existing milestone SHALL be the description and due date of an open one, through `edit-milestone`. Closing a milestone SHALL stay a user step outside the write tool.

#### Scenario: Tool text
- **WHEN** the text of the write tool is scanned outside comments
- **THEN** it holds no request that changes a milestone's state or title, no milestone-closing function, and its only milestone update carries a description and a due date

### Requirement: The write tool records an idea
The system SHALL provide a write-tool command that records an idea as an issue labelled `type:idea`, with its title, a short body and an idea marker (design D7), without milestone, Project item, Status, `roadmap` block or `R-<n>` identifier. It SHALL pass the guard before any request. It SHALL NOT create a feature, a sub-issue, a milestone or a relation.

#### Scenario: New idea
- **WHEN** the user records an idea with a title and a summary
- **THEN** one issue is created with the `type:idea` label, no milestone and the idea marker, and the tool prints `created idea <slug> (#<number>)` and exits 0

#### Scenario: Name in the summary
- **WHEN** the summary holds a name of the sensitive-names list
- **THEN** the tool exits 3, names the body field and the line, and sends nothing

#### Scenario: Identifiers of features unchanged
- **WHEN** ideas exist and a new feature is created
- **THEN** the feature's identifier is the highest `R-<n>` among the issues plus one, ideas not counted

#### Scenario: Missing summary
- **WHEN** the command is given a title and no summary
- **THEN** the tool exits 2 and sends nothing

Source: tests/gh_issue/test_gh_issue.py (Idees)

### Requirement: Recording an idea is idempotent on its marker
The idea command SHALL be idempotent on the marker, whose slug comes from the title without case, accents or punctuation: an idea with the same slug, open or closed, SHALL NOT be recorded again.

#### Scenario: Second run
- **WHEN** the same idea is recorded again
- **THEN** nothing is sent, the tool prints `already exists: idea <slug> (#<number>)` and exits 0

#### Scenario: Same idea already closed
- **WHEN** an idea whose title differs only in case, accents or spaces from a closed idea is recorded
- **THEN** nothing is sent and the tool prints `already exists: idea <slug> (#<number>)` with the number of the closed idea

Source: tests/gh_issue/test_gh_issue.py (Idees)

### Requirement: The label command creates the public-edition label
The system SHALL include the label `edition:public` in the labels that the write tool's label command creates (design D19 of `edition-publish-tooling`). The system SHALL NOT remove that label.

#### Scenario: Label created
- **WHEN** the label command runs on a repository without `edition:public`
- **THEN** the label is created

#### Scenario: Label already there
- **WHEN** the label command runs on a repository that already has `edition:public`
- **THEN** no creation request is sent for it

Source: tests/gh_issue/test_gh_issue.py (EtiquetteEditionPublique: test_ensure_labels_cree_l_etiquette, test_ensure_labels_ne_la_recree_pas_si_elle_existe); tests/roadmap_model/test_roadmap_model.py (TestLabelEditionPublique)

### Requirement: Closing a feature can record the public-edition label
The system SHALL let `close-feature` take an option that adds `edition:public` to the feature, after the guard. On an open feature, the label SHALL be added before the closing writes; on a feature already closed, the option SHALL add the label only. When the label is already present, the system SHALL send no label request. Without the option, `close-feature` SHALL behave as before.

#### Scenario: Label added at closing
- **WHEN** `close-feature` runs with the public-edition option on an open feature whose sub-issues are all closed
- **THEN** the feature carries `edition:public` and is closed with Status `Done`

#### Scenario: Feature already closed
- **WHEN** `close-feature` runs with the option on a feature closed earlier without the label
- **THEN** the feature carries `edition:public`, and its state, Status, closing date and comments are unchanged

#### Scenario: Label already present
- **WHEN** the feature already carries `edition:public`
- **THEN** no label request is sent

Source: tests/gh_issue/test_gh_issue.py (EtiquetteEditionPublique)

### Requirement: A guard finding refuses the whole command
The system SHALL, before each request, apply to every text it sends (title, body, comment, labels, milestone, block values) the sensitive-name rules of the pre-commit hook with the local list, the identifiers of the personal-identifier scanner, and a ticket-key pattern (two or more capitals, a hyphen, digits; `R-<n>` passes). On a finding it SHALL send nothing for the whole command and exit 3. It SHALL NOT print the value or the line, nor offer an option to skip the guard.

#### Scenario: Name in a body
- **WHEN** a feature body holds a name of the sensitive-names list
- **THEN** the tool exits with code 3 with `refused: sensitive name in body, line <n>; nothing was sent`, sends no request, and its output holds no listed name

#### Scenario: Identifier in a label
- **WHEN** a label name holds an identifier of the session, in any case
- **THEN** the tool exits with code 3 with `refused: personal identifier in label, line 1` and sends nothing

#### Scenario: Ticket key in a body
- **WHEN** a body holds a made-up ticket key (two capital letters, a hyphen, digits)
- **THEN** the tool exits with code 3 with `refused: ticket key in body`, sends nothing and does not print the key

#### Scenario: Queue identifier allowed
- **WHEN** a body holds `R-62`
- **THEN** the guard raises no finding

#### Scenario: One finding refuses the whole command
- **WHEN** the task sync would create three sub-issues and only the title of the third holds a listed name
- **THEN** the tool exits with code 3 and none of the three sub-issues is created

#### Scenario: No option to skip the guard
- **WHEN** a command is given an option such as `--no-guard`, `--skip-guard` or `--force`
- **THEN** the tool exits with code 2 with `usage:`

Source: tests/gh_issue/test_gh_issue.py (Garde)

### Requirement: The guard fails closed when it cannot run
The system SHALL send nothing, call no `gh` command and exit with code 4 and the key phrase `guard could not run:` followed by the cause when the sensitive-names list is absent, empty or holds only comments, or when the personal-identifier scanner fails. The cause SHALL be `sensitive-names list absent`, `sensitive-names list empty` or `identifier scanner failed`. The system SHALL NOT fall back to a partial guard or send the request without it.

#### Scenario: List absent
- **WHEN** the sensitive-names list is absent
- **THEN** the tool exits with code 4 with `guard could not run: sensitive-names list absent` and calls no `gh` command

#### Scenario: List of comments only
- **WHEN** the list holds only comments and blank lines
- **THEN** the tool exits with code 4 with `guard could not run: sensitive-names list empty`

#### Scenario: Scanner failure
- **WHEN** the personal-identifier scanner stops with an error
- **THEN** the tool exits with code 4 with `guard could not run: identifier scanner failed` and sends nothing

Source: tests/gh_issue/test_gh_issue.py (Garde: test_liste_absente, test_liste_vide_ou_de_commentaires, test_echec_du_scanner; Idees: test_garde_impossible_code_4)

### Requirement: A GitHub refusal message is withheld when it holds a name or an identifier
The system SHALL pass the message of a GitHub refusal through the guard before printing it. When it holds a sensitive name or a personal identifier, or when no guard is loaded, the system SHALL exit with code 1 and print `GitHub refused: HTTP <code> (message withheld)`; otherwise it SHALL print `GitHub refused:` followed by the first line of the message, cut to 200 characters. It SHALL NOT print a withheld message in part.

#### Scenario: Identifier in the message
- **WHEN** GitHub refuses a write with a message that holds an identifier of the session or a listed name
- **THEN** the tool exits with code 1, prints `GitHub refused: HTTP 422 (message withheld)` and its output holds neither value

#### Scenario: Clean message
- **WHEN** GitHub refuses a write with a message that holds no name and no identifier
- **THEN** the tool prints `GitHub refused:` followed by that message

Source: tests/gh_issue/test_gh_issue.py (Reseau: test_message_de_gh_avec_identifiant_retenu, test_message_de_gh_propre_conserve, test_refus_de_github_code_1_sans_texte_envoye)

### Requirement: Feature fields are checked before any write
The system SHALL check the fields of `new-feature` and `edit` before any write: an unknown theme exits 2; a rank already held by an open feature exits 7 with `rank already used by R-<n>`; an invalid block value, a zero estimate included, exits 7 with `invalid block:` and the fields; an unknown blocker or milestone exits 7; moving an open feature to a closed milestone exits 7. In each case nothing SHALL be sent.

#### Scenario: Unknown milestone
- **WHEN** `new-feature` names a milestone that does not exist
- **THEN** the tool exits with code 7 with `unknown milestone` and sends no write

#### Scenario: Rank already used
- **WHEN** `new-feature` sets a rank held by the open feature R-1
- **THEN** the tool exits with code 7 with `rank already used by R-1`

#### Scenario: Zero estimate
- **WHEN** `edit` sets the estimate to `0min` or `0h`
- **THEN** the tool exits with code 7 and names the estimate field

#### Scenario: Open feature to a closed milestone
- **WHEN** `edit` moves an open feature to a closed milestone
- **THEN** the tool exits with code 7 with `closed milestone` and sends no write

Source: tests/gh_issue/test_gh_issue.py (Features: test_usage_theme_inconnu_et_jalon_inconnu, test_rang_deja_pris, test_estimation_nulle_refusee, test_edit_identifiant_inconnu_ou_bloc_invalide, test_edit_vers_un_jalon_ferme_refuse_sur_une_feature_ouverte); that the rank and block refusals come before any write is read in tools/gh_issue.py

### Requirement: The start date is written once
The system SHALL, when a feature's Status is set to `In progress` and its block has no start date, write the day's date into the block before setting the Status. It SHALL NOT change a start date already written, even when the feature leaves `In progress` and comes back to it, and a Status already set SHALL give `nothing to do`.

#### Scenario: First start
- **WHEN** a `Ready` feature without a start date is set `In progress`
- **THEN** its block holds the day's date as start date and its Status is `In progress`

#### Scenario: Second start
- **WHEN** the same feature is set `Ready`, then `In progress` again on a later day
- **THEN** its start date is still the first one

Source: tests/gh_issue/test_gh_issue.py (Features: test_status_en_cours_ecrit_started_on_une_fois)

### Requirement: An idea's text can come from a file
The system SHALL let `new-idea` read the idea's text from `--body-file` instead of `--body`, with exactly one of the two required, and SHALL read the file as UTF-8 text. The file's text SHALL pass the guard like `--body`. A missing path, a path that is not a regular file, an unreadable or non-UTF-8 file, or a whitespace-only file SHALL exit 2 with `usage:`. The system SHALL NOT accept both options together, and SHALL NOT send a write after any of these refusals.

#### Scenario: Idea created from a file
- **WHEN** `new-idea --title "Une idée" --body-file idee.md` runs and `idee.md` holds two lines of text
- **THEN** one issue is created whose body is the idea marker, a blank line and the two lines, and the tool prints `created idea une-idee (#<number>)` and exits 0

#### Scenario: Both options given
- **WHEN** `new-idea --title "Une idée" --body "Texte." --body-file idee.md` runs
- **THEN** the tool exits 2 with `usage:` and sends no write

#### Scenario: Neither option given
- **WHEN** `new-idea --title "Une idée"` runs without `--body` or `--body-file`
- **THEN** the tool exits 2 with `usage:` and sends no write

#### Scenario: File missing, blank or a folder
- **WHEN** `--body-file` names a path that does not exist, a file that holds only spaces and blank lines, or a folder
- **THEN** the tool exits 2 with `usage:` each time and sends no write

#### Scenario: Name in the file
- **WHEN** the file holds a name of the sensitive-names list or a made-up ticket key
- **THEN** the tool exits 3, names the body field, sends no write, and its output does not hold the name or the key

Source: tests/gh_issue/test_gh_issue_body_file.py (NewIdeaBodyFile); the UTF-8 reading and the refusal of an unreadable or non-UTF-8 file are read in tools/gh_issue.py (untested)

### Requirement: edit-idea replaces an idea's body from a file
The system SHALL let `edit-idea` replace the body of an issue labelled `type:idea` with the text of `--body-file`, read and checked as for `new-idea`. It SHALL keep the idea marker at the top of the body and send the change in the same request as a `--value` or `--milestone` change. It SHALL NOT accept `--body`. It SHALL NOT edit an issue without `type:idea` (exit 7), and SHALL send nothing on a file refusal (exit 2) or a guard finding (exit 3).

#### Scenario: Body replaced
- **WHEN** `edit-idea #1 --body-file idee.md` runs on an idea and `idee.md` holds `Nouveau texte.`
- **THEN** the idea's body is its marker, a blank line and `Nouveau texte.`, one write is sent, and the tool prints `edited idea #1`

#### Scenario: Combined with a value
- **WHEN** `edit-idea 1 --value 2 --body-file idee.md` runs
- **THEN** one PATCH request carries both the new body and the `value:2` label

#### Scenario: Inline body refused
- **WHEN** `edit-idea 1 --body "Texte."` runs
- **THEN** the tool exits 2 with `usage:` and sends no write

#### Scenario: Not an idea
- **WHEN** `edit-idea 2 --body-file idee.md` names a feature issue
- **THEN** the tool exits 7 and sends no write

#### Scenario: Name in the file
- **WHEN** the file holds a name of the sensitive-names list or a made-up ticket key
- **THEN** the tool exits 3, sends no write, and the idea keeps its previous body

Source: tests/gh_issue/test_gh_issue_body_file.py (EditIdeaBodyFile)

### Requirement: edit renames a feature
The system SHALL let `edit` take `--title` with the title text without its key, and add the prefix `R-<n> · ` itself. It SHALL refuse an empty or blank title, and a title that already starts with an `R-<n> · ` prefix, with exit code 2 and `usage:`, and print `nothing to do` for an identical title. It SHALL NOT change the identifier and SHALL NOT send a write after a refusal.

#### Scenario: Feature renamed
- **WHEN** `edit R-1 --title "Titre neuf"` runs on the feature R-1
- **THEN** its title becomes `R-1 · Titre neuf`

#### Scenario: Title already prefixed
- **WHEN** `edit R-1 --title "R-1 · Titre neuf"` runs
- **THEN** the tool exits 2 with `usage:` and sends no write

#### Scenario: Empty title
- **WHEN** `edit R-1 --title ""` or a title of spaces runs
- **THEN** the tool exits 2 with `usage:` and sends no write

#### Scenario: Identical title
- **WHEN** `edit R-1 --title "Stable"` runs a second time on a feature already titled `R-1 · Stable`
- **THEN** the tool prints `nothing to do` and sends no write

#### Scenario: Name in the title
- **WHEN** the title holds a name of the sensitive-names list
- **THEN** the tool exits 3 naming the title field, sends no write, and its output does not hold the name

Source: tests/gh_issue/test_gh_issue_title.py (EditTitreFeature)

### Requirement: edit-idea renames an idea
The system SHALL let `edit-idea` take `--title`, refuse an empty or blank title with exit code 2 and `usage:`, keep the idea marker in the body, and print `nothing to do` for an identical title. The new title SHALL pass the guard before any request. It SHALL NOT change the marker and SHALL NOT send a write after a refusal.

#### Scenario: Idea renamed
- **WHEN** `edit-idea 1 --title "Idée renommée"` runs
- **THEN** the idea's title changes and its body, marker included, is unchanged

#### Scenario: Empty title
- **WHEN** `edit-idea 1 --title "  "` runs
- **THEN** the tool exits 2 with `usage:` and sends no write

#### Scenario: Identical title
- **WHEN** `edit-idea 1 --title` names the idea's current title
- **THEN** the tool prints `nothing to do` and sends no write

#### Scenario: Name in the title
- **WHEN** the title holds a name of the sensitive-names list
- **THEN** the tool exits 3 naming the title field, sends no write and keeps the previous title

Source: tests/gh_issue/test_gh_issue_title.py (EditTitreIdee)

### Requirement: A feature or an idea is created with a product label
The system SHALL let `new-feature` and `new-idea` take `--product` with a value of the closed list of products (today `mothra`) and add the label `product:<value>`. An item with no `product:` label SHALL belong to PMZilla, and the tool SHALL NOT add a label for it. A value outside the list SHALL exit 2 with `usage:` and send no write. The label and the title SHALL pass the guard before any request.

#### Scenario: Feature created for the product
- **WHEN** `new-feature --product mothra` runs
- **THEN** the feature carries `product:mothra` besides `type:feature` and its theme label, and the label exists in the repository

#### Scenario: Feature created without option
- **WHEN** `new-feature` runs without `--product`
- **THEN** the feature carries no `product:` label

#### Scenario: Idea created for the product
- **WHEN** `new-idea --product mothra --value 2` runs
- **THEN** the idea carries `type:idea`, `value:2` and `product:mothra`

#### Scenario: Unknown product
- **WHEN** `--product autre` is given to `new-feature` or `new-idea`
- **THEN** the tool exits 2 with `usage:` and sends no write

#### Scenario: Name in the title with a product
- **WHEN** `new-feature --product mothra` is given a title that holds a name of the sensitive-names list
- **THEN** the tool exits 3 and sends no write

Source: tests/gh_issue/test_gh_issue_product.py (Creation; EtiquettesEtSync: test_garde_sur_le_titre_inchange_avec_le_produit)

### Requirement: edit and edit-idea set or remove the product label
The system SHALL let `edit` and `edit-idea` take `--product` with a value of the closed list or `none`: a value sets `product:<value>` in place of any other `product:` label, `none` removes it, and the other labels stay. An unknown value SHALL exit 2 with `usage:` and send no write; a label state already in place SHALL print `nothing to do` and send no write. The tool SHALL NOT relabel an existing item unless asked. For `edit-idea`, `--product` alone SHALL be a valid command.

#### Scenario: Label set then removed
- **WHEN** `edit R-1 --product mothra` runs, then again, then `edit R-1 --product none`, then again
- **THEN** the first and third runs write, the second and fourth say `nothing to do`, and the feature ends with its theme and type labels only

#### Scenario: Theme changed on a feature of the product
- **WHEN** `edit R-1 --set theme=veille` runs on a feature carrying `product:mothra`
- **THEN** the feature keeps `product:mothra` and takes the new theme label

#### Scenario: Idea relabelled
- **WHEN** `edit-idea 1 --product mothra`, then `edit-idea 1 --value 3`, then `edit-idea 1 --product none` run on an idea with `value:1`
- **THEN** the idea carries `product:mothra` after the first, keeps it with `value:3` after the second, and holds `type:idea` and `value:3` only after the third

#### Scenario: Unknown product
- **WHEN** `edit R-1 --product autre` or `edit-idea 1 --product autre` runs
- **THEN** the tool exits 2 with `usage:` and sends no write

Source: tests/gh_issue/test_gh_issue_product.py (Edition)

### Requirement: new-feature and edit set the value label
The system SHALL let `new-feature` and `edit` take `--value 1|2|3` (1 high, 3 low) and set the label `value:N`, creating it if absent. `edit` SHALL replace any other `value:` label, keep the other labels, and say `nothing to do` when the label is in place. Another value SHALL exit 2 and send nothing.

#### Scenario: Value replaced
- **WHEN** `edit R-1 --value 1`, then `--value 3`, then `--value 3` run
- **THEN** R-1 holds `value:3` only, and the third run says `nothing to do`

Source: tests/gh_issue/test_gh_issue_valeur_remplacee.py (ValeurSurLesFeatures)

### Requirement: The label command creates the product label
The system SHALL include the label `product:mothra` in the labels that the write tool's label command creates, with a colour and a description saying that an item without a `product:` label belongs to PMZilla. It SHALL NOT give a description to the other labels it creates, and SHALL NOT change or remove an existing label.

#### Scenario: Label created
- **WHEN** the label command runs on a repository without `product:mothra`
- **THEN** the label is created with a colour and a description, and `type:feature` is created without description

Source: tests/gh_issue/test_gh_issue_product.py (EtiquettesEtSync: test_ensure_labels_cree_le_label_avec_couleur_et_description)

### Requirement: The task sync copies the product label of the feature
The system SHALL, when the task sync creates sub-issues for a feature that carries a `product:` label, give each new sub-issue that label besides its type, model or user-step labels, after the guard. It SHALL NOT add a `product:` label to a sub-issue of a feature that has none, and SHALL NOT relabel a sub-issue that already exists.

#### Scenario: Feature of the product
- **WHEN** `sync-tasks` runs on a feature carrying `product:mothra` and creates group sub-issues and a user-task sub-issue
- **THEN** each of them carries `product:mothra`, and a group sub-issue holds exactly its model label, `product:mothra` and `type:task`

#### Scenario: Feature without product
- **WHEN** `sync-tasks` runs on a feature without a `product:` label
- **THEN** no sub-issue carries a `product:` label

#### Scenario: Existing sub-issue
- **WHEN** a feature receives `product:mothra` after its sub-issues were created and `sync-tasks` runs
- **THEN** the existing sub-issues keep their labels

Source: tests/gh_issue/test_gh_issue_product.py (EtiquettesEtSync: test_sync_tasks_recopie_le_label_sur_les_taches, test_sync_tasks_sans_produit_ne_pose_rien); that existing sub-issues are not relabelled is read in tools/gh_issue.py (untested)

### Requirement: new-task files a standalone user task
The system SHALL let `new-task R-<n> --title T --body-file F [--milestone M]` create, without any `tasks.md`, a sub-issue of the feature R-<n> labelled `type:task` and `owner:user`, plus the feature's `product:` label when it has one. Its key SHALL be `R-<n>/u<k>`, with `k` the next free number among the standalone tasks of that feature, so that it never collides with a group key or a task key of the sync.

#### Scenario: Task created
- **WHEN** `new-task R-1 --title "Valider le brouillon" --body-file F` runs on a feature R-1 of an existing milestone
- **THEN** a sub-issue `R-1/u1` titled `R-1 · Valider le brouillon` exists with `type:task` and `owner:user`, linked to R-1 and in the milestone of R-1

#### Scenario: Next free number
- **WHEN** R-1 already has the sub-issues `R-1/g1`, `R-1/t2.2` and `R-1/u1` and `new-task` runs with another title
- **THEN** the new task is `R-1/u2`

Source: tests/gh_issue/test_gh_issue_user_task.py

### Requirement: A standalone user task takes its title, body and milestone from the command
The title of a task filed by `new-task` SHALL be the text of `--title` with the prefix `R-<n> · ` added by the tool, and its body SHALL hold the identity marker and the text of the file. Its milestone SHALL be the feature's unless `--milestone` names another existing milestone.

#### Scenario: Explicit milestone
- **WHEN** `new-task` runs with `--milestone` naming an existing milestone, or an unknown one
- **THEN** the task is in the named milestone, or the tool exits 7 and sends no write

Source: tests/gh_issue/test_gh_issue_user_task.py

### Requirement: new-task checks its input before any write
For `new-task`, the title and the body SHALL pass the guard before any request. An empty title, a title already prefixed, a missing option, or a file that is absent, empty or not a regular file SHALL exit 2 with `usage:`; an unknown feature or an unknown milestone SHALL exit 7; none of them SHALL send a write. A second run with the same title for the same feature SHALL create nothing and print `already exists`.

#### Scenario: Same title twice
- **WHEN** `new-task` runs a second time with the same feature and title
- **THEN** the tool prints `already exists` and creates no issue

#### Scenario: Name in the title or the body
- **WHEN** the title or the file holds a name of the sensitive-names list
- **THEN** the tool exits 3, sends no write, and its output does not hold the name

Source: tests/gh_issue/test_gh_issue_user_task.py

### Requirement: A standalone user task closes through close-step only
`close-step` SHALL accept the key `R-<n>/u<k>` of a task filed by `new-task` and close the task without a reason, and `sync-tasks` SHALL neither close nor reopen it.

#### Scenario: Closing
- **WHEN** `close-step R-1/u1` runs without a reason, then runs again
- **THEN** the task is closed, then the tool prints `nothing to do`

Source: tests/gh_issue/test_gh_issue_user_task.py

### Requirement: Issue writes refuse the distinctive team names of the extract
The system SHALL refuse, before sending anything to GitHub, an issue write whose title or body contains a distinctive team name of the team-names extract, with its existing refusal for sensitive names, which never prints the name (design D8). A missing or unreadable extract SHALL leave the check of the sensitive-names list unchanged. The write tool SHALL NOT print, send or store a team name. Untested until implemented.

#### Scenario: Body holding an extract name
- **WHEN** an issue body contains a distinctive team name of the extract
- **THEN** the write tool refuses with its sensitive-name refusal, sends nothing, and its output contains no team name

#### Scenario: No extract
- **WHEN** the extract does not exist
- **THEN** the write tool checks the sensitive-names list only, as before

### Requirement: Issue writes skip the names of the author's generic-names list
The system SHALL let an issue write hold an extract team name that the author's generic-names list excludes, through the same reading of the extract as the pre-commit hook (extract-name-exclusions design D2). It SHALL keep refusing a name of the sensitive-names list, even when the generic-names list holds it.

#### Scenario: Listed generic name in a body
- **WHEN** an issue body contains an extract name that the generic-names list holds
- **THEN** the write tool does not refuse it for that name

#### Scenario: Sensitive name also listed as generic
- **WHEN** an issue body contains a name that is in both lists
- **THEN** the write tool refuses with its sensitive-name refusal and sends nothing

### Requirement: sub-issues lists the sub-issues of an issue and the duplicate keys
The system SHALL let `sub-issues <parent>`, given as `R-<n>` or an issue number, list each sub-issue as `#<number> <open|closed> <key>` or `no key`, a count line, then `duplicate key <key>: #<a>, #<b>` per key carried by two or more issues, or `no duplicate key`. It SHALL exit 0 and send no write. It SHALL NOT print a title or a body. The same read SHALL back every check of the writes of this change (design D1).

#### Scenario: Feature with a duplicated key
- **WHEN** `sub-issues R-1` runs and two sub-issues of R-1 carry `R-1/u2`
- **THEN** the output lists both with their state, holds `duplicate key R-1/u2:` with both numbers, and the tool exits 0 with no write

#### Scenario: No duplicate
- **WHEN** every sub-issue of the parent carries its own key or none
- **THEN** the output ends with `no duplicate key`

#### Scenario: Unknown parent
- **WHEN** the parent is an unknown number or identifier
- **THEN** the tool exits 7 and sends nothing

### Requirement: promote-idea turns an idea into a feature
The system SHALL let `promote-idea <n> --theme <theme>` turn an open `type:idea` issue into a feature in one PATCH: same number, title `R-<m> · <idea title>` with the next free identifier, body made of the identity marker, a `roadmap` block and the idea's text, `type:idea` replaced by `type:feature`, the theme label added and the other labels kept. It SHALL then place it in the Project, keeping an existing Status, `Todo` otherwise, and print `promoted #<n> to R-<m>`.

#### Scenario: Idea promoted
- **WHEN** `promote-idea 7 --theme outillage` runs on an open idea with `value:1` and `product:mothra`, the highest identifier being `R-64`
- **THEN** issue 7 is titled `R-65 · <its title>`, carries `type:feature`, `theme:outillage`, `value:1` and `product:mothra`, has the marker and the block followed by its text, and its Status is `Todo`

### Requirement: promote-idea removes the idea marker and keeps the milestone
The PATCH of `promote-idea` SHALL remove the `roadmap-idea` marker from the body; the promotion SHALL NOT keep that marker and SHALL NOT change the milestone (design D2, R-20261103-22 Q3).

#### Scenario: Idea marker removed
- **WHEN** `promote-idea 7 --theme outillage` runs on an idea whose body starts with its `roadmap-idea` marker
- **THEN** the body of issue 7 holds the identity marker `R-65` and no `roadmap-idea` marker, and issue 7 still has no milestone

#### Scenario: Second run
- **WHEN** the same command runs again on the promoted issue
- **THEN** the tool prints `nothing to do: #7 is already R-65` and sends no PATCH

### Requirement: promote-idea checks before any write
For `promote-idea`, the system SHALL refuse, before any write, an issue without `type:idea` (code 7), a closed idea (code 7, `reopen it before promoting it`), an unknown theme (code 2), an invalid block or a used rank (code 7), a next identifier already carried by an issue (code 7, `duplicate key`), and a guard finding in the title or the body (code 3). It SHALL NOT leave an issue half promoted.

#### Scenario: Closed idea
- **WHEN** `promote-idea 7 --theme outillage` runs on a closed idea
- **THEN** the tool exits 7 and sends no write

#### Scenario: Made-up ticket key in the idea's text
- **WHEN** the idea's body holds a made-up ticket key
- **THEN** the tool exits 3 naming the body field, sends no write and does not print the key

### Requirement: attach-sub-issue attaches an existing issue
The system SHALL let `attach-sub-issue <parent> <child>`, each as `R-<n>` or an issue number, add the child as a sub-issue of the open parent and print `attached #<c> to #<p>`, without asking GitHub to replace another parent and without changing a milestone. A child already under that parent SHALL print `nothing to do`.

#### Scenario: Issue attached
- **WHEN** `attach-sub-issue 40 41` runs and issue 41 has no parent
- **THEN** issue 41 is a sub-issue of issue 40 and a second run prints `nothing to do`

### Requirement: attach-sub-issue reports a milestone gap without moving it
When the child's milestone differs from the parent's, `attach-sub-issue` SHALL report it on one line `milestone differs:` and SHALL NOT move either milestone. The gap SHALL be corrected only by a separate, explicit milestone command of the tool (`edit R-<p> --milestone <M>`, `edit-task --milestone`, `edit-idea --milestone`) (design D3, R-20261103-22 Q6).

#### Scenario: Milestone gap reported, not moved
- **WHEN** `attach-sub-issue R-1 41` runs, R-1 being in milestone `Hydra` and issue 41 having no milestone
- **THEN** the output holds `milestone differs: #41 none, #<R-1's number> Hydra`, issue 41 still has no milestone, and a later `edit R-1 --milestone Hydra` puts issue 41 in `Hydra`

#### Scenario: Child with another parent
- **WHEN** the child is already a sub-issue of another issue and GitHub refuses the request
- **THEN** the tool exits 1 with `GitHub refused:` and the child keeps its parent

### Requirement: attach-sub-issue refuses a duplicate key and a cycle
Before any write, `attach-sub-issue` SHALL refuse a child equal to the parent (code 2), an unknown issue (code 7), a closed parent (code 7), a parent that is a sub-issue of the child (code 7), and a child whose key is already carried by a sub-issue of the parent (code 7, `duplicate key <key>: already carried by #<x> under #<p>; nothing was sent`).

#### Scenario: Duplicate key
- **WHEN** the parent R-1 has the sub-issue `R-1/u2` and the child also carries `R-1/u2`
- **THEN** the tool exits 7 with `duplicate key R-1/u2` and sends no write

#### Scenario: Cycle
- **WHEN** `attach-sub-issue 5 6` runs while issue 5 is a sub-issue of issue 6
- **THEN** the tool exits 7 and sends no write

### Requirement: horizon reads and sets the Horizon field of the Project
The system SHALL let `horizon <ref>` print `horizon <ref> <value>` or `horizon <ref> none` for a feature or an idea, and `horizon <ref> <V2|V3|V4|Plus tard>` add the issue to the Project when missing and set the single-select field Horizon, through the tool's own Project requests. The same value SHALL print `nothing to do`. The tool SHALL NOT create or change a Project field. Status commands SHALL work without the Horizon field.

#### Scenario: Idea set to V2
- **WHEN** `horizon 7 V2` runs on an open idea that is not in the Project
- **THEN** the idea is in the Project with Horizon `V2`, its Status unchanged, and `horizon 7` prints `horizon 7 V2`

#### Scenario: Same value
- **WHEN** `horizon R-1 "Plus tard"` runs twice
- **THEN** the second run prints `nothing to do` and sends no write

### Requirement: horizon refuses a task, a closed issue and a missing field
Before any write, `horizon` SHALL refuse a value outside V2, V3, V4 and Plus tard (code 2), a task (code 2, `a task follows its feature`), a write on a closed issue (code 7), and a Project without the field Horizon or one of its options (code 6, `Project has no Horizon field or its options are incomplete; nothing was sent`).

#### Scenario: Field missing
- **WHEN** the Project has no field Horizon and `horizon R-1 V3` runs
- **THEN** the tool exits 6 and sends no write, and `status R-1 Ready` still works

#### Scenario: Task
- **WHEN** `horizon` names a task key `R-1/g2`
- **THEN** the tool exits 2 and sends no write

### Requirement: --no-milestone removes an issue's milestone
The system SHALL let `edit R-<n>`, `edit-task` and `edit-idea` take `--no-milestone`, exclusive with `--milestone` (code 2), and send an empty milestone; on a feature it SHALL also remove the milestone of each of its sub-issues, open or closed, read first. An issue without milestone SHALL print `nothing to do`. The tool SHALL NOT delete the milestone itself. A closed feature SHALL be refused, code 7, nothing sent.

#### Scenario: Closed feature keeps its milestone
- **WHEN** `edit R-2 --no-milestone` runs on a closed feature of milestone `Hydra`
- **THEN** the tool exits 7, sends no write, says a delivered feature keeps its release's milestone, and names the path `reopen-feature`, `edit`, then closing

#### Scenario: Feature and sub-issues
- **WHEN** `edit R-1 --no-milestone` runs on a feature of milestone `Hydra` with an open and a closed sub-issue
- **THEN** the feature and both sub-issues have no milestone, the milestone `Hydra` still exists, and a second run prints `nothing to do`

#### Scenario: Both options
- **WHEN** `edit-idea 7 --milestone Hydra --no-milestone` runs
- **THEN** the tool exits 2 and sends no write

### Requirement: A feature and a task take their text from a file
The system SHALL let `new-feature` and `edit R-<n>` take `--body-file F`, whose text follows the `roadmap` block, and `edit-task` take `--body-file F`, whose text follows the identity marker; the marker and the block SHALL be kept. The file SHALL be read and refused as for `new-idea` (code 2), pass the guard (code 3), and an identical text SHALL print `nothing to do`.

#### Scenario: Feature text replaced
- **WHEN** `edit R-1 --body-file F` runs and F holds `Nouveau texte.`
- **THEN** R-1's body is its marker, its unchanged block and `Nouveau texte.`

#### Scenario: Blank file
- **WHEN** `edit-task R-1/u1 --body-file F` runs and F holds only spaces
- **THEN** the tool exits 2 and sends no write

### Requirement: close-idea and close-feature close an issue as a duplicate
The system SHALL let `close-idea <n>` and `close-feature R-<n>` take `--duplicate-of N`: post one comment with the duplicate marker and `Duplicate of #<N>`, then close the issue with GitHub's duplicate reason, and print `closed <ref> as duplicate of #<N>`. A feature closed so SHALL get no Status `Done`, no `done_on` and no `edition:public`. A rerun SHALL print `nothing to do` and post a missing comment once.

#### Scenario: Idea closed as duplicate
- **WHEN** `close-idea 9 --duplicate-of 12` runs on an open idea
- **THEN** issue 9 is closed as a duplicate with one comment `Duplicate of #12`, and a second run prints `nothing to do`

#### Scenario: Refusals
- **WHEN** N is the issue itself, N is unknown, or the feature has an open sub-issue
- **THEN** the tool exits 2, 7 or 7 respectively and sends no write

### Requirement: reopen-idea and reopen-feature reopen with a reason
The system SHALL let `reopen-idea <n> --reason R` and `reopen-feature R-<n> --reason R` post one comment with the reopening marker and the reason, then reopen the issue; for a feature it SHALL remove `done_on` and set a Status `Done` back to `Todo`. A blank reason SHALL exit 2, a closed milestone 7, both before any write. An open issue SHALL print `nothing to do: <ref> is already open`.

#### Scenario: Feature reopened
- **WHEN** `reopen-feature R-1 --reason "fermée par erreur"` runs on a feature closed with Status `Done`
- **THEN** R-1 is open, its block has no `done_on`, its Status is `Todo` and it holds one comment with the reason

#### Scenario: Already open
- **WHEN** `reopen-idea 7 --reason "x"` runs on an open idea
- **THEN** the tool prints `nothing to do: #7 is already open` and sends no write

### Requirement: A reopened feature gets a rank and resumes cleanly
For `reopen-feature`, the system SHALL give a feature closed without a rank the highest open rank plus 10, and SHALL exit 7 before any write when its rank is held by an open feature, naming `edit R-<n> --set rank=<free>`. It SHALL reopen and write the block in one PATCH, and on an already open feature SHALL repair a `done_on` left in the block or a Status `Done`, without a second comment.

#### Scenario: Closed feature without a rank
- **WHEN** `reopen-feature R-2 --reason "x"` runs on a closed feature without a rank, the highest open rank being 40
- **THEN** R-2 is open with rank 50

#### Scenario: Interrupted reopening resumed
- **WHEN** `reopen-feature R-1` is rerun on a feature that is open but still holds `done_on` and Status `Done`
- **THEN** `done_on` is removed, the Status is `Todo`, and the reopening comment is not posted again

### Requirement: edit-milestone sets a milestone's description and due date
The system SHALL let `edit-milestone <M> [--description-file F] [--due YYYY-MM-DD | --no-due]` change only the description and due date of an existing open milestone, in one request, and print `edited milestone <M>`, or `nothing to do` for the same values. No option, an impossible date or a refused file SHALL exit 2; an unknown or closed milestone SHALL exit 7; the description SHALL pass the guard (code 3); none SHALL send a write.

#### Scenario: Description and due date
- **WHEN** `edit-milestone Kraken --description-file F --due 2026-11-26` runs on an open milestone
- **THEN** the milestone has the text of F and the due date 2026-11-26, keeps its title and state, and a second run prints `nothing to do`

#### Scenario: Closed milestone
- **WHEN** `edit-milestone Cerberus --due 2026-12-01` runs on a closed milestone
- **THEN** the tool exits 7 and sends no write
