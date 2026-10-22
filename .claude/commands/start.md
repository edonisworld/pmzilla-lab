---
description: Starts a job of the work queue (reads its description, creates its branch, runs it as a direct prompt or through /implement), sets its GitHub Status, closes the feature when done and prints the finishing command
argument-hint: "<job id, e.g. R-19>"
allowed-tools: Read, Grep, Glob, Edit, Write, Agent, Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(bash tools/worktree.sh:*), Bash(git add:*), Bash(ls:*), Bash(openspec list:*), Bash(openspec validate:*), Bash(bash tests/run_all.sh:*), Bash(uv run tools/identifiants_personnels.py:*), Bash(uv run --with pyyaml python tools/roadmap.py check:*), Bash(uv run --with pyyaml python tools/roadmap.py show:*)
---

Start the job of the work queue: $ARGUMENTS

Language: this command is written in English, but serve the user in THEIR language (French by default when their request is in French).

## 1. Read and check the job (write nothing yet)

1. Without an identifier, ask for one and do nothing else.
2. Run `uv run --with pyyaml python tools/roadmap.py check`. If the queue is invalid, report each problem line and stop.
3. Run `uv run --with pyyaml python tools/roadmap.py show <id>`: the feature's Status, blockers, `roadmap` block (estimate, method, model, `conditions`, `change`, `not_before`) and free-text brief. Nothing else is read for the queue: the queue lives in GitHub issues.
4. Refuse to start, and say why, when the feature is unknown, its Status is not `Ready` (`Todo`, `In progress` or `Done`), it has an open blocker, or its `not_before` date is later than today. Write nothing, on GitHub or in the repository. Never change a Status or a relation to make it startable.
   When the refusal is only because the Status is `Todo`, end the refusal with the exact command that sets it to Ready, for the user to approve: `uv run tools/gh_issue.py status <id> Ready` (with the feature's key in place of `<id>`, e.g. `R-19`). Print it as text; never run it yourself, and never run it on the user's behalf without their explicit approval. For `In progress` or `Done`, or any other refusal reason (blocker, `not_before`), print no such command.
   Exception, the resume of a batch: an `In progress` feature is accepted when the current branch is the one `/batch` names for it (`git branch --show-current`): `chore/r<n>-<slug>` for a `direct-prompt` job, `chore/spec-r<n>` for an `openspec` job without a `change`, `feat/<change>` for an `openspec` job with a `change`, the slug being the one the reader prints. On any other branch an `In progress` feature is still refused. On resume, blockers, `not_before`, conditions and model (steps 4 to 6) are checked as for a `Ready` feature.
5. Non-empty `conditions`: quote them and ask the user to confirm they hold. Start only after an explicit yes.
6. Model: the feature's `model` is the model to work with. If it differs from the session's model, say so and ask the user to switch with `/model <alias>` before going further; `tbd` means the user chooses. This command fixes no model.

## 2. Branch

On resume of a batch feature (step 1.4), skip the branch creation and the Status write below: the branch exists and the feature is already `In progress`. This command does not set the Status again, and the closing step still applies.

- If the working tree is not clean, stop and list the files.
- Never write or commit on `main`, and never work on a job in the workspace. Branch name: for a `direct-prompt` job, `chore/<id in lower case>-<short slug of the title>` (for example `chore/r19-pre-tri-robuste`); for an `openspec` job, the branch that `/implement` names.
- **Started from the workspace on `main`** (finish-under-lock D7): create the job's worktree with `bash tools/worktree.sh <branch>` (never `git checkout -b`), then run `uv run tools/gh_issue.py status <id> "In progress"`, then stop. Print, labelled as the user's commands: `cd <worktree folder printed by the script> && claude`, then, in that new session, `/start <id>` (the resume below picks it up). Do no work in the worktree from the workspace session and write nothing in the workspace. If the worktree script refuses, report its refusal line and stop without changing the Status.
- **Started in a worktree on the job's branch**: the resume of step 1.4 applies; work there.
- On another branch: ask whether to work on it or to go back to `main` first. Never start a job on the branch of another job without the user's yes.

When the Status is set (from the workspace, above): report to the user the line the tool prints about the release: `moved R-<n> and <k> sub-issue(s) to <milestone>` or `no current release; milestone unchanged`. On exit 7 with `current release <name> is not an open milestone; nothing was sent`, report it and stop: the user fixes the setting. Never move a milestone yourself and never edit `tools/roadmap_settings.yaml`.

## 3. Do the job

- **`direct-prompt`**: the feature's free-text brief is the brief. A step the brief marks as needing the user's decision is a stop: present the options and wait.
- **`openspec` with a `change` field**: read `.claude/commands/implement.md` and follow it for that change, every rule included. After each commit that completes a group, run `uv run tools/gh_issue.py sync-tasks <id>` (the user approves each write at the permission prompt).
- **`openspec` without a `change`**: the change does not exist yet. Have it written by the `spec-writer` agent in Change mode (proposal, tasks, delta specs), run `openspec validate --strict` on it, then stop and ask the user to review it. Implementation starts only after their yes, through `.claude/commands/implement.md`.

Permanent rules, for every method:

- Tests first, then code. While working, run only the suites touched, quietly, with the dependencies of `tests/run_all.sh`.
- Before each commit: run `uv run tools/identifiants_personnels.py` on the files you wrote; stage files by name; run `bash tests/run_all.sh --staged` (no variable, no pipe, in the foreground); commit only when it is green, with `git commit` alone (no `NAME=value` before it). Never set `PMZILLA_AFTER_COMMIT`; the variables a commit needs come from the session's environment (worktree script `tools/worktree.sh`). One commit per coherent unit, with its documentation in the same commit; CHANGELOG.md is frozen: add no entry.
- A test that needs the network and fails: do not work around it; stop and give the user the exact command for their Terminal, without a pipe.
- Roles, never names: write no person's, team's or project's name in any file.

## 4. Close the feature

1. When the work is committed and green, before closing the feature, list the paths changed on the branch since its merge base with `main` (`git diff --name-only main...HEAD`, which compares against that merge base) and check them against the include and template rules of `edition/manifest.yaml`. When at least one changed path enters the edition, name those paths, propose the label `edition:public` and pass `--edition-public` to `close-feature` only after the user's yes; the tool adds the label before closing. Otherwise say that no path of the edition changed and pass no option. Then run `uv run tools/gh_issue.py close-feature <id>`. It runs before the merge and the tool posts one comment naming the branch. It closes the feature with Status `Done` only when no sub-issue is open; otherwise the feature stays `In progress` and you list the open sub-issues.
2. Name the features this unblocks (the write tool prints them), for the user to set `Ready`; never set a Status yourself for them.
3. A job left unfinished (user step pending, decision awaited): do not close it; say what remains.

## 5. Hand over

One single final message: what was done, by commit; what remains and why; the commands reserved to the user; then the finishing command for the user to type in the Terminal, for every job: `bash tools/finish_worktree.sh <branch>`, to run from the workspace once the session has ended (from the worktree, the direct finishing script would stop with exit 12). Never run it.

## GitHub write without an answer

When a `tools/gh_issue.py` command ends with exit code 8 (state unknown): stop, show the user the check command the tool printed, and make no further GitHub write until the user has checked. Never say the write was not sent, and never run it again before the check.

## Never

- Write to GitHub other than through `tools/gh_issue.py`; use any `gh` command to write; pre-approve either in a header.
- Push, merge, or run the branch-finishing scripts (`tools/finish_branch.sh`, `tools/finish_worktree.sh`).
- Use `--no-verify` or the owner bypass variable (`PMZILLA_SKIP_GREEN_CHECK`).
- Change a rank, an estimate, a model or a dependency, or start a job the checks of step 1 refuse.
- Edit `CLAUDE.md`, unless the job says so and the posture evaluation cost was announced and accepted.
- Launch anything reserved to the user: the real Jira tools (`history_jira.py`, `export_jira_api.py`), `flow_import.py`, `flow_compare.py`, the indexer `pmzilla_lab_library.py` (`index`, `rename-collection`, `probe`, `status`), the database scripts (`db.py`, `db_backup.sh`, `db_up.sh`), any calculation with the database as source (`--source db`), any database client (`psql`, `docker exec`), book conversion, sorting and indexing, the posture evaluation set (announce its cost and wait).
- Read the content folders (`Bibliotheque-*`, `Watch-Lab`, `Watch-Excluded`), the sensitive files of `Flux-Lab/` (`exports/`, `historique/`, `tableaux/`, `equipes-assets.yaml`, `noms-sensibles.txt`), the database backups or the journal.
