# workflow-github-issues Specification

## Purpose
PMZilla Lab's work queue lives in the issues of its GitHub repository; this capability defines how those issues are written (created, edited, commented, closed, linked and labelled) only through the write tool `tools/gh_issue.py`, never by a direct `gh` write, and with no name of a person, team, Jira project or domain.

## Requirements

### Requirement: One tool writes to GitHub
The system SHALL provide a write tool that is the only way the repository and the session create, edit, close or reopen an issue, add a comment, a sub-issue, a "blocked by" relation, a label, a milestone or a Project Status on GitHub, and remove a "blocked by" relation. The tool SHALL write only to the repository of the remote `origin`, through the user's `gh` authentication. Removing a "blocked by" relation SHALL be its only deletion request. It SHALL NOT delete, transfer, lock or pin an issue, SHALL NOT delete or change an existing label or milestone, SHALL NOT write to another repository, and SHALL NOT create a release or a tag. Subcommands, codes and messages are those of design D7 and D9.

#### Scenario: Other repository
- **WHEN** the tool is asked to write to a repository other than the one of `origin`
- **THEN** it exits with code 2 and sends nothing

#### Scenario: No delete
- **WHEN** the tool's text is scanned outside comments
- **THEN** it holds no issue, label or milestone deletion, no transfer, no release or tag creation, and its only deletion request removes a "blocked by" relation

#### Scenario: Relation removed
- **WHEN** `unblock R-2 --by R-1` runs on a feature R-2 blocked by R-1
- **THEN** the relation is removed, and a second run says `nothing to do`

Source: tests/gh_issue/test_gh_issue.py (Depot; Relations: test_block_et_unblock)

### Requirement: Features and sub-issues follow the queue model
The system SHALL create a feature with the title `R-<n> · <title>`, the labels `type:feature` and `theme:<theme>`, a milestone, an identity marker and a valid `roadmap` block (design D1, D5), placed in the Project with a Status. A new feature SHALL receive the next free identifier, the highest identifier among all issues plus one. The system SHALL create sub-issues only from the tagged groups of the `tasks.md` of the unarchived change named in the feature's block (design D3): one `type:task` sub-issue with one model label per agent group, plus `parallel` when tagged; one `owner:user` sub-issue per user group and per user task of an agent group. It SHALL refuse a change with an untagged numbered group, exit 7 and print `tasks.md groups untagged:` with the group numbers. The task sync SHALL exit 7 and write nothing when the feature names no change, when the change's `tasks.md` is not found, or when the change is archived (`change archived`). A sub-issue body SHALL hold the change and the group or task number, never the text of a task.

#### Scenario: New feature
- **WHEN** the highest identifier among open and closed issues is `R-64` and a new feature is created
- **THEN** it is titled `R-65 · <title>`, carries the marker and the block, and its Status is `Todo`

#### Scenario: Mixed group
- **WHEN** an agent group tagged `[model: sonnet]` holds one task tagged `[user]`
- **THEN** sync creates one `type:task` sub-issue with `model:sonnet` and one `owner:user` sub-issue for that task

#### Scenario: Untagged group
- **WHEN** a numbered group of the change has no model tag and no user tag
- **THEN** the tool exits with code 7, names the group and creates nothing

#### Scenario: Missing change
- **WHEN** the feature's block names no change, or a change whose `tasks.md` does not exist
- **THEN** the task sync exits with code 7 and creates nothing

#### Scenario: Archived change
- **WHEN** the feature's block names a change found only in the archive
- **THEN** the task sync exits with code 7 with `change archived` and sends no write, while `close-feature` on that feature closes it without a sync

Source: tests/gh_issue/test_gh_issue.py (Features; Sync: test_groupe_mixte_et_etiquettes, test_corps_sans_texte_des_taches, test_groupe_sans_tag, test_feature_sans_change_ou_change_introuvable, test_sync_refuse_un_change_archive; Fermeture: test_change_archive_ne_bloque_pas)

### Requirement: Writes are idempotent
The system SHALL find an existing issue by its identity marker before creating one, and SHALL NOT create a second issue with the same marker, add a relation or a label already present, or create a label or milestone that exists; in those cases it SHALL print `already exists: <key> (#<number>)` or `nothing to do` and exit 0.

#### Scenario: Second sync
- **WHEN** the task sync runs twice on the same `tasks.md`
- **THEN** the second run sends no creation and says `nothing to do`

Source: tests/gh_issue/test_gh_issue.py (Sync: test_deuxieme_passage_ne_fait_rien; Idempotence; Relations: test_block_et_unblock)

### Requirement: Sub-issues and features close only when complete
The system SHALL close a group sub-issue when its tasks are all ticked and a user-task sub-issue when its task is ticked, and reopen one whose task was unticked unless it was closed with a reason. User-step sub-issues, and agent sub-issues closed with a reason, SHALL close only through close-step after the user's confirmation; the sync SHALL list a ticked user group as ready to close after the user's confirmation, without closing it. close-step on a user-step sub-issue SHALL close it without a reason, and say `nothing to do` when it is already closed. A feature SHALL close only when none of its sub-issues is open; otherwise the tool SHALL exit 7 with `open sub-issues remain:` and change nothing.

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

#### Scenario: User group ticked
- **WHEN** every task of a user group is ticked and the sync runs
- **THEN** the user-group sub-issue stays open and the output says `ready to close after your confirmation:` with its key

#### Scenario: User step closed by close-step
- **WHEN** close-step runs without a reason on an open user-step sub-issue, then runs again
- **THEN** the first run closes it and posts no comment, and the second says `nothing to do`

Source: tests/gh_issue/test_gh_issue.py (Sync: test_groupe_coche_ferme_seulement_lui, test_tache_utilisateur_cochee_ferme_sa_sous_issue_puis_decochee_la_rouvre, test_groupe_utilisateur_ne_se_ferme_pas_par_la_synchronisation, test_close_step; Fermeture; CloseStepAvecRaison: test_etape_utilisateur_sans_raison_comme_avant)

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
The system SHALL exit with code 8 and the key phrase `state unknown` when a write gets no answer, or when GitHub becomes unreachable or the rate-limit cap is hit after at least one confirmed write. The message SHALL give the number of confirmed writes and the read command that shows the feature; for a command that names no feature, it SHALL say instead to run the same command again, since it is idempotent. The tool SHALL NOT print `nothing was sent` in these cases nor retry a write whose result is unknown.

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
The system SHALL, when it closes a feature, write the closing date into its block, set its Status to `Done`, post one comment naming the current branch, close it as completed and list the open features whose blockers are now all closed, without changing their Status. It SHALL NOT post that comment twice nor when there is nothing to do, and the guard SHALL check the comment before any write. When a feature was closed by an earlier run that stopped before its comment, a new run SHALL post the missing comment once and change nothing else.

#### Scenario: Feature closed on a branch
- **WHEN** `close-feature` closes a feature from the branch `chore/r65-fixes`
- **THEN** the feature has its closing date, Status `Done`, state closed as completed, and one comment that names `chore/r65-fixes` and says the merge is pending

#### Scenario: Second run
- **WHEN** `close-feature` runs again on the closed feature
- **THEN** it says `nothing to do` and posts no comment

#### Scenario: Detached head
- **WHEN** the repository is on a detached head
- **THEN** the comment says the feature was closed outside a branch and names the short commit

#### Scenario: Interrupted close
- **WHEN** an earlier `close-feature` closed the feature but stopped before posting its comment, and the command runs again
- **THEN** the comment is posted once, the feature stays closed as completed, and a third run says `nothing to do`

Source: tests/gh_issue/test_gh_issue.py (CommentaireDeCloture)

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
The system SHALL hold no code that closes, reopens, renames or deletes an existing milestone; closing a milestone SHALL stay a user step outside the write tool.

#### Scenario: Tool text
- **WHEN** the text of the write tool is scanned outside comments
- **THEN** it holds no request that changes a milestone, and no milestone-closing function

### Requirement: The write tool records an idea
The system SHALL provide a write-tool command that records an idea as an issue labelled `type:idea`, with its title, a short body and an idea marker (design D7), without milestone, Project item, Status, `roadmap` block or `R-<n>` identifier. It SHALL pass the guard before any request and SHALL be idempotent on the marker, whose slug comes from the title without case, accents or punctuation: an idea with the same slug, open or closed, SHALL NOT be recorded again. It SHALL NOT create a feature, a sub-issue, a milestone or a relation.

#### Scenario: New idea
- **WHEN** the user records an idea with a title and a summary
- **THEN** one issue is created with the `type:idea` label, no milestone and the idea marker, and the tool prints `created idea <slug> (#<number>)` and exits 0

#### Scenario: Second run
- **WHEN** the same idea is recorded again
- **THEN** nothing is sent, the tool prints `already exists: idea <slug> (#<number>)` and exits 0

#### Scenario: Same idea already closed
- **WHEN** an idea whose title differs only in case, accents or spaces from a closed idea is recorded
- **THEN** nothing is sent and the tool prints `already exists: idea <slug> (#<number>)` with the number of the closed idea

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
