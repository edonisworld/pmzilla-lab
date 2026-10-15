---
description: Prepares one worktree and one session launch per independent ready feature of a milestone (reads the batch through the queue reader, sets In progress after the user's yes, starts no session)
argument-hint: "<milestone, e.g. v1.4>"
allowed-tools: Bash(uv run --with pyyaml python tools/roadmap.py check:*), Bash(uv run --with pyyaml python tools/roadmap.py batch:*), Bash(bash tools/worktree.sh:*), Bash(git status:*), Bash(git rev-parse:*)
---

Prepare a batch of the work queue, milestone: $ARGUMENTS

Language: this command is written in English, but serve the user in THEIR language (French by default when their request is in French). Translate the enumerated values for display (`Ready` is "prêt", `In progress` is "en cours"); identifiers, branches, commands and paths stay as they are.

This command prepares and stops. It creates worktrees and sets Statuses; it never runs a job, a session or a finishing script.

## 1. Read and check (write nothing yet)

1. Without a milestone, ask for one and run nothing else.
2. Run `git rev-parse --abbrev-ref HEAD`. If the branch is not `main`, say that `/batch` runs on `main` only and stop: run neither the reader nor the worktree script, write nothing. Never fetch or pull; if the user needs the latest changes, tell them to bring `main` up to date themselves.
3. Run `git status` and, if the working tree is not clean, list the files and stop.
4. Run `uv run --with pyyaml python tools/roadmap.py check`. If the queue is invalid, report each problem line and stop.
5. Run `uv run --with pyyaml python tools/roadmap.py batch --milestone <milestone>`. Exit codes: 1 the queue is invalid (report each problem line, stop); 2 usage, an unknown or closed milestone, or a missing milestone (report the line, stop); 5 `GitHub unreachable; a batch needs a live read` (report it and propose nothing: never start from a snapshot). The reader prints French lines prefixed `roadmap : `: header, current release, `retenues`, `écartées`, `fichiers partagés`.
6. Stop, writing nothing, when the reader prints `release courante : aucune` (say that the current-release setting is empty; the user fixes it, you never edit `tools/roadmap_settings.yaml`) or when no feature is retained.

## 2. Propose, and wait for one yes

Present the result in the user's language: the retained features (identifier, title, method, branch, launch model, session kind `cadrage` = framing or `exécution` = execution, due date), the `fichiers inconnus` flags (their independence is not checked), the shared files with the features that cite them, the features set aside with their reason (common files with another feature, one `en cours` included, or change not found), and the non-empty conditions, quoted.

Ask one yes. The user may remove features in the answer. A feature with non-empty conditions is started only when the yes confirms them; otherwise drop it from the batch. Nothing is written, no worktree and no GitHub write, before the yes.

## 3. Prepare each kept feature, in rank order

For each kept feature, with the branch the reader printed (never a new slug):

1. Run `bash tools/worktree.sh <branch>`. Keep the folder it prints.
2. Then run `uv run tools/gh_issue.py status <id> "In progress"` (it writes `started_on` and moves the feature and its sub-issues into the current release). Report the line the tool prints: `moved R-<n> and <k> sub-issue(s) to <milestone>` or `no current release; milestone unchanged`. The user approves each write at the permission prompt.

Failures:

| Event | What you do |
|---|---|
| worktree script exits 4 (folder exists, branch open elsewhere) | set the feature aside, say why, send no GitHub write for it, go on with the next one |
| worktree script exits 2, 3 or 5 | stop the batch; list the worktrees created and the features started so far |
| write tool exits with any other non-zero code (1, 3, 4, 5, 6, 7) | stop the batch; report the tool's line; list the worktrees created and the features started; the worktree of the failed feature stays, named, for the user to keep or remove |

Never create two worktrees for one feature.

## GitHub write without an answer

When a `tools/gh_issue.py` command ends with exit code 8 (state unknown): stop the whole batch, show the user the check command the tool printed, and make no further GitHub write until the user has checked. Never say the write was not sent, and never run it again before the check.

## 4. Hand over

One single final message, then one block per started feature:

- the feature (identifier, title), the folder, the branch, the launch model and the session kind;
- the launch command, to type in the Terminal: `cd <folder> && claude --model <alias> "<prompt>"`, and the prompt alone, to paste if needed. Launch model and prompt follow the reader's line: framing (`openspec` without change, branch `chore/spec-r<n>`): `opus` and the framing prompt `Frame R-<n> as an OpenSpec change with the spec-writer agent: proposal, design, tasks, delta specs and fiche-decisions.md with an empty decision column; run openspec validate --strict; commit on this branch; do not push.`; execution: the model the reader printed (`sonnet` for an `openspec` feature with a change, the feature's model for `direct-prompt`, `sonnet` when `tbd`) and the prompt `/start R-<n>`;
- the finishing command, labelled as the user's command, to run in the Terminal from the workspace once that session has ended: `bash tools/finish_worktree.sh <branch>`.

Then list the features set aside or dropped and why, and the worktrees left for the user to keep or remove. Never run a launch command or a finishing command.

## Never

- Launch a session or `claude`.
- Open a Terminal.
- Merge, or push.
- Run the finishing scripts (`tools/finish_branch.sh`, `tools/finish_worktree.sh`).
- Remove a worktree or a branch.
- Write to GitHub other than through `tools/gh_issue.py`, or with any `gh` command; pre-approve either in a header.
- Set a Status other than `In progress` (never `Ready`); change a rank, an estimate, a model, a dependency, a condition or a milestone other than through the Status write; edit `tools/roadmap_settings.yaml`.
- Start a feature the reader did not retain, or one the user removed.
- Use `--no-verify` or the owner bypass variable (`PMZILLA_SKIP_GREEN_CHECK`).
- Launch anything reserved to the user: the real Jira tools (`history_jira.py`, `export_jira_api.py`), `flow_import.py`, `flow_compare.py`, the indexer `pmzilla_lab_library.py` (`index`, `rename-collection`, `probe`, `status`), the database scripts (`db.py`, `db_backup.sh`, `db_up.sh`), any calculation with the database as source (`--source db`), any database client (`psql`, `docker exec`), book conversion, sorting and indexing, the posture evaluation set (announce its cost and wait).
- Read the content folders (`Bibliotheque-*`, `Watch-Lab`, `Watch-Excluded`), the sensitive files of `Flux-Lab/` (`exports/`, `historique/`, `tableaux/`, `equipes-assets.yaml`, `noms-sensibles.txt`), the database backups or the journal.
- Write a person's, team's or project's name in your answer.
