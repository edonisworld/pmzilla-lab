# workflow-multi-session Specification

## Purpose
Let the user pilot several parallel sessions: a read-only status of the worktrees and their features, a freeze check that tells an agent whether a finish is running, guarded handoff notes, the /pilot command that launches nothing, and a tracked preamble that gives agents their standing rules.

## Requirements

### Requirement: The pilot status lists every worktree from Git
The system SHALL provide a pilot tool whose status subcommand lists, from Git at each call, the main checkout and every linked worktree other than the run tree, with the fields of design D2, then the finish lock line and the run tree line. It SHALL exit 0 whenever it can print, 2 on a usage error and 3 outside a clone of the repository. It SHALL NOT keep or read a registry file of sessions, fetch, or write a reference, the index, the configuration or a fingerprint.

#### Scenario: Three worktrees
- **WHEN** the status runs on a repository with a clean worktree, a worktree holding two untracked files and a worktree whose branch is merged into `main`
- **THEN** the output holds one line per worktree with `propre`, `2 fichier(s) modifié(s)` and `fusionnée, à retirer` respectively, and the exit code is 0

#### Scenario: Run tree left out of the list
- **WHEN** a detached run tree exists
- **THEN** it has no worktree line and the output holds `dossier d'exécution : présent`

#### Scenario: Nothing written
- **WHEN** the status has run
- **THEN** the references, the index, the configuration and the fingerprints of the repository are unchanged

#### Scenario: Outside the repository
- **WHEN** the status runs from a folder that is not a clone
- **THEN** it exits 3 with `pilot : dépôt introuvable`

### Requirement: The status links a worktree to its feature offline
The system SHALL give each worktree the link of design D2: `R-<n>` from the branch patterns of the batch, `change <name>` for a change branch, followed by the feature that the reader's snapshot names for that change when it does, and `—` otherwise. It SHALL NOT call the network or `gh`, and SHALL NOT fail when the snapshot is missing or unreadable.

#### Scenario: Framing branch
- **WHEN** a worktree holds the branch `chore/spec-r12`
- **THEN** its link is `R-12`

#### Scenario: Change branch known to the snapshot
- **WHEN** a worktree holds `feat/<change>` and the snapshot holds a feature whose change field is that change
- **THEN** its link is `change <change> (R-<n>)` with that feature

#### Scenario: No snapshot
- **WHEN** no snapshot exists
- **THEN** a change branch shows `change <change>`, other branches show `—`, no `gh` call is made, and the exit code is 0

### Requirement: The status prints no path, file name or process number
The system SHALL name worktrees by their folder relative to the lab folder, dirty files by their count, and busy worktrees by `occupé`, `libre` or `inconnu` from the process listing of the worktree-finishing script. It SHALL NOT print an absolute path, the home folder, a file name of a worktree, a process number or a process command.

#### Scenario: Busy worktree
- **WHEN** the fake listing reports a process whose current folder is inside a worktree
- **THEN** that worktree's line holds `occupé` and the output holds no process number

#### Scenario: Listing impossible
- **WHEN** the listing command is missing or fails
- **THEN** every worktree shows `inconnu` and the exit code is 0

#### Scenario: Paths scanned
- **WHEN** the output of a status on the fixture is scanned
- **THEN** it holds neither the temporary folder's absolute path nor the home folder nor the name of any dirty file

### Requirement: The freeze check tells an agent whether a finish is running
The system SHALL give the pilot tool a freeze check that exits 0 when no live finish lock is held, when the caller carries the lock's token, or when the lock's readable list (`freeze_scope()`, change autonomous-trains-merge, design D18) does not hold the caller's worktree (with the phrase `pilot : fin en cours : <n> worktree(s) gelé(s), main, dossier d'exécution et liste prête` of design D19 when a live lock is held but does not list the caller's worktree, R-20261106-13 Q2), and 4 with the phrase of design D3 naming the branch and the start time when a live lock without the caller's token lists the caller's worktree or holds no readable list, and a wait form that repeats the check until it is free or the minutes given are spent (exit 4 with its phrase). A stale lock SHALL count as free and be reported. Minutes outside the range of D3 SHALL exit 2. It SHALL NOT create, remove or change the lock, run tests, nor keep a freeze rule of its own beside `freeze_scope()`.

#### Scenario: Finish running
- **WHEN** a lock of a live process names a branch, lists the caller's worktree, and the caller has no token
- **THEN** the check exits 4 with `pilot : fin de branche en cours (<branche>, depuis HH:MM)` and the lock is unchanged

#### Scenario: Finish running in other worktrees
- **WHEN** a lock of a live process lists two other worktrees than the caller's, and the caller has no token
- **THEN** the check exits 0 with `pilot : fin en cours : 2 worktree(s) gelé(s), main, dossier d'exécution et liste prête` and the lock is unchanged

#### Scenario: Lock without a readable list
- **WHEN** a lock of a live process holds no readable list and the caller has no token
- **THEN** the check exits 4

#### Scenario: Caller is the finish
- **WHEN** the caller's token equals the lock's token
- **THEN** the check exits 0

#### Scenario: Lock released during the wait
- **WHEN** the wait form runs with a short poll interval and the test removes the lock after two polls
- **THEN** it exits 0 with `pilot : aucune fin de branche en cours`

#### Scenario: Wait spent
- **WHEN** the lock stays held and keeps listing the caller's worktree for the whole wait
- **THEN** it exits 4 with `pilot : fin de branche toujours en cours après <minutes> min`

#### Scenario: Stale lock
- **WHEN** the lock names a process that no longer exists
- **THEN** the check exits 0, the output holds `pilot : verrou de fin périmé, ignoré`, and the lock folder is still there

### Requirement: Handoff notes are one guarded line per worktree
The system SHALL let the pilot tool set or clear one line of at most the length of design D4 for the worktree of a branch, stored owner-only in the common Git folder, shown by the status. The text SHALL pass the write tool's guard first: a finding exits 5 and a guard that cannot run exits 6, nothing written in either case; a branch without a worktree exits 7. It SHALL NOT print the matched value, store a note in a tracked folder, a worktree or the lab data folder, or accept a line break.

#### Scenario: Note set and shown
- **WHEN** a note is set for a worktree's branch
- **THEN** the tool exits 0 with `pilot : note enregistrée` and the next status shows `note : <text>` on that worktree's line

#### Scenario: Sensitive name
- **WHEN** the note holds a name of the fixture sensitive-names list
- **THEN** the tool exits 5 with `pilot : note refusée (nom sensible, identifiant ou clé de ticket)`, writes nothing, and its output does not hold the name

#### Scenario: Guard unavailable
- **WHEN** the sensitive-names list is absent
- **THEN** the tool exits 6 with `pilot : contrôle de la note impossible` and writes nothing

#### Scenario: No worktree
- **WHEN** the branch has no worktree
- **THEN** the tool exits 7 and writes nothing

### Requirement: The pilot tool writes only its notes
The system SHALL keep every subcommand of the pilot tool free of any write other than the notes of design D4. It SHALL NOT commit, create or delete a branch or a worktree, merge, push, call `gh`, create, remove or change the finish lock, run a finishing script or the test runner.

#### Scenario: Forbidden commands
- **WHEN** the tool's text is scanned outside comments
- **THEN** it holds no commit, merge, push, worktree removal, branch deletion, `gh` call, finishing-script launch, runner launch or removal of the lock folder

### Requirement: The pilot tool speaks French by default and English on request
The system SHALL print the pilot tool's phrases in French by default and in English with the shared language option, every refusal on the error output prefixed with the tool's name, one exit code per outcome as design D2 to D4 list them.

#### Scenario: English check
- **WHEN** the freeze check runs with the English option while a live lock is held
- **THEN** the phrase is in English and the exit code is 4

### Requirement: The /pilot command presents the status and launches nothing
The system SHALL provide a `/pilot` command that runs the pilot status, presents it in the user's language, flags what needs the user as design D8 lists, and gives the finishing command of a worktree whose note says it is ready, labelled as the user's command. Its header SHALL pre-approve only the status and the freeze check. It SHALL NOT run a finishing script, write a note without the user's yes, commit, merge, push, remove a worktree, write to GitHub, or read a note's file.

#### Scenario: Pre-approval
- **WHEN** the header of the command file is read
- **THEN** it pre-approves only the pilot status and the freeze check

#### Scenario: Checked command file
- **WHEN** the workflow command test runs
- **THEN** the `/pilot` file is among the checked command files and names each forbidden action of this requirement

### Requirement: A tracked preamble gives agents their standing rules and commit rule
The system SHALL keep a tracked agent preamble with the standing rules and the commit rule per agent kind of design D9: implementation agents commit on their own branch after a green run and the freeze wait; framing agents never commit, the orchestrating session committing their work after review; review and search agents never commit. It SHALL NOT let any agent run a finishing script, merge, push or remove a worktree, nor hold an absolute path, a user name or any person, team or project name.

#### Scenario: Content
- **WHEN** the preamble is read
- **THEN** it holds the freeze command of design D9 and one commit rule for each agent kind

#### Scenario: No path
- **WHEN** the preamble is scanned
- **THEN** it holds no absolute path and no home-folder form

### Requirement: The agent preamble forbids piped interpreters and file changes by script
The system SHALL make the tracked agent preamble tell every agent to modify files with the Edit tool only (Write only to create a new file) and to run only the commands its definition and prompt allow, read-only searches included (design D12 of change multi-session-piloting). It SHALL forbid changing a file with a script, `sed -i` or a shell redirection.

#### Scenario: Three rules present
- **WHEN** the preamble test reads the preamble
- **THEN** it finds the rule on piping into `python3`, `grep` or `tail` with the test-runner exception for `tail`, the rule on Edit for every file change with `sed -i` and redirections named as forbidden, and the rule on allowed commands

### Requirement: The agent preamble forbids piping into an interpreter or a filter
The system SHALL make the tracked agent preamble forbid piping a command into `python3`, `grep` or `tail` (design D4 of change deny-rules-review), except a `tail` right after the targeted test runner or `unittest`.

#### Scenario: Piping rule present
- **WHEN** the preamble test reads the preamble
- **THEN** it finds the rule on piping into `python3`, `grep` or `tail`, with the exception for a `tail` right after the targeted test runner or `unittest`

### Requirement: The pilot tool is testable without the real workspace
The system SHALL include a Python suite, found by the runner, that exercises the pilot tool on temporary repositories with linked worktrees, a fake snapshot, a fake sensitive-names list and identifiers file, a fake process listing, an injectable clock and poll interval (design D11). It SHALL NOT read the real workspace, the real common Git folder, the real snapshot or the real sensitive-names list.

#### Scenario: Suite run
- **WHEN** the runner runs the pilot suite
- **THEN** every case runs in a temporary folder and the suite reports its count

### Requirement: The preamble and the framing review list carry the deny-rule guard
The system SHALL make the agent preamble tell an agent whose change touches deny rules to declare its rules through a `--json` list function kept green by the shared guard, and the framing agent's "Done" checklist require that list function and the guard in such a change's tasks (design D4 of change deny-rules-review). Both SHALL forbid a `Write(path)` or `NotebookEdit(path)` rule and an empty permission key.

#### Scenario: Preamble line
- **WHEN** the preamble test reads the preamble
- **THEN** it finds the deny-rule line naming `Write(path)` and `NotebookEdit(path)` as forbidden and `Edit(path)` as the rule for writing

#### Scenario: Framing checklist
- **WHEN** the framing agent's definition is read
- **THEN** its "Done" checklist holds the deny-rule point

### Requirement: The pilot status shows the ready list and the train job
The system SHALL add to the pilot status the two items of design D9 of autonomous-trains-observe: the ready flag on each listed worktree's line, and the `train automatique` line after the finish lock line, which names the mode (`observation`, `fusion automatique` or `activation invalide`, from `activation_valid()`) and the series (`série <k>/5`, from `activation_status()`) (change autonomous-trains-merge, design D20). Each item is computed by a service function of the autonomous-train tools and only formatted by the status. The status SHALL stay offline and read-only. When no train file exists, its output SHALL be unchanged. It SHALL NOT create, remove or change the activation file, nor compute the mode or the series in its formatting.

#### Scenario: Listed branch with a stale tip
- **WHEN** a worktree's branch is listed and has a commit after its line
- **THEN** its status line holds `prête (écartée : sommet changé depuis l'inscription)`

#### Scenario: Stop active
- **WHEN** the stop file exists
- **THEN** the status holds a `train automatique` line with `arrêt actif`

#### Scenario: Merge mode shown
- **WHEN** a valid activation file exists and a pass ran
- **THEN** the line reads `train automatique : fusion automatique ; dernier passage …`

#### Scenario: No train files
- **WHEN** the data folder holds no ready list, no state, no stop file and no activation file
- **THEN** the status output is the same as before this change, and nothing is written

### Requirement: The finish lock freezes only the train's references and worktrees
While a train holds the finish lock, the readers of the freeze SHALL refuse, to a caller without the lock's token, only the actions that write `main`, the run tree or the ready list, and the commits, suites and container passes started in a worktree that the lock lists (each train branch's worktree and the integration worktree), as `freeze_scope()` of `tools/finish_lock.py` returns them (change autonomous-trains-merge, design D18). The readers of the freeze, the pre-commit hook, the runner, `ci_local.sh run`, `pilot.py freeze --check` and `train_ready.py add`, `drop` and `prune`, SHALL all decide through that one function (R-20261106-71 Q1 (a)); a worktree whose current branch is a listed branch SHALL count as listed; the workspace on `main` (head on `main` or detached) and the run folder SHALL count as writing `main` (R-20261106-71 Q2 (a)); and a held lock without a readable list SHALL count as freezing everything. `ci_local.sh run` from another worktree SHALL wait in the queue behind the train's pass instead of exiting 7. The npm guard, the `pre-merge-commit` hook, `ci_local.sh build` and `up` SHALL keep the general freeze, and dbtest SHALL keep its refusal 3. The system SHALL NOT refuse, in a worktree that the lock does not list, a commit, a suite or a `ci_local.sh run` that writes neither `main`, the run tree nor the ready list, nor keep a second freeze rule in any of its readers.

#### Scenario: Session in another worktree
- **WHEN** a train holds the lock and a session commits in a worktree that the lock does not list
- **THEN** the commit is not refused by the freeze

#### Scenario: Train branch worktree
- **WHEN** a train holds the lock and a session runs a suite in the worktree of a branch of the train
- **THEN** the runner refuses it as frozen

#### Scenario: Ready list during a train
- **WHEN** a train holds the lock and a session runs `train_ready.py add`
- **THEN** the addition is refused as frozen and the list is unchanged, whatever the worktree; `train_ready.py drop` and `prune` are refused the same way, and `list` stays allowed

#### Scenario: Train branch checked out in a new worktree
- **WHEN** a train holds the lock and a branch of its list, without a worktree at the start, is checked out in a new worktree during the train
- **THEN** a commit or a suite in that worktree is refused as frozen

#### Scenario: Workspace on main during a train
- **WHEN** a train holds the lock and a session commits or runs a suite in the workspace on `main` (or on a detached head), outside the list
- **THEN** it is refused as frozen, since it counts as writing `main`

#### Scenario: Lock without a list
- **WHEN** the lock is held and its list of branches and worktrees cannot be read
- **THEN** every reader treats every worktree as frozen

#### Scenario: npm ci during a train
- **WHEN** a train holds the lock and `npm ci` is started in a worktree that the lock does not list
- **THEN** the npm guard refuses it, as before this change
