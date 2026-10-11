---
description: Implements an OpenSpec change task by task on its own branch (tests first, one commit per group, no push, no merge)
argument-hint: "<change name>"
model: sonnet
allowed-tools: Read, Grep, Glob, Edit, Write, Agent, Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(git checkout -b:*), Bash(git add:*), Bash(ls:*), Bash(openspec list:*), Bash(bash tests/run_all.sh:*), Bash(uv run tools/identifiants_personnels.py:*), Bash(uv run --with pyyaml python tools/roadmap.py check:*)
---

Implement the OpenSpec change: $ARGUMENTS

Recommended model: frame and specify on Opus, then `/model sonnet` in the same session to execute while the context is useful (the header sets Sonnet).

Language: this command is written in English, but serve the user in THEIR language (French by default when their request is in French).

## Start

1. Read `openspec/changes/<change>/` (proposal, design, tasks, delta specs). If the folder does not exist, or the change is archived (it sits under `openspec/changes/archive/`), say so, name the change and write nothing.
2. If the current branch is `main`, create and switch to a branch whose last name segment is the change name (for example `feat/<change>`) BEFORE writing anything. Never write or commit on `main`.
3. Follow `tasks.md` in order. Its section "Order, commits and parallel work" decides the commits and what may run in parallel: launch agents in ONE message and only for work on distinct files; edit shared files (CHANGELOG, installation guide, the shell list of the runner, the settings file) yourself, one group at a time.

## Permanent rules

- Tests first, then code. While working, run only the suites touched, quietly and stopping at the first failure, with the dependencies of `tests/run_all.sh`.
- Before each commit: run `uv run tools/identifiants_personnels.py` on the files you wrote; stage files by name; run `bash tests/run_all.sh --staged` (no variable, no pipe, in the foreground); commit only when it is green, with `PMZILLA_NO_EVALS=1` on the commit. One commit per coherent unit, with its CHANGELOG line and its documentation in the same commit.
- If a commit stumbles on a test that needs the network, do not work around it: stop and give the user the exact command to run in their Terminal, without a pipe.
- Tick a task only when the suite it names passes in the current state. A task that names no suite stays unticked, with the short reason given by the user (a user step, a manual check). Never tick on your own judgement.
- Roles, never names: write no person's, team's or project's name in any file.

## Stop and hand over to the user (print the command and its purpose, run nothing)

- Any launch against the real Jira: `history_jira.py` (test, collect, check with a key), `export_jira_api.py` (diagnose, fields, export).
- `flow_import.py`, `flow_compare.py`, `knowledge_import.py` (import, verify, status), the indexer `pmzilla_lab_library.py` (`index`, `rename-collection`, `probe`, `status`), the database scripts (`db.py`, `db_backup.sh`, `db_up.sh`), any calculation with the database as source (`--source db`), any database client (`psql`, `docker exec`).
- Book conversion, sorting by domain and indexing; edits of the settings file that the change assigns to the user.
- The posture evaluation set: announce its cost first and run nothing until the user agrees.

## Never

- Push, merge, or run the branch-finishing script (`tools/finish_branch.sh`): the user types it in the Terminal.
- Use `--no-verify` or the owner bypass variable (`PMZILLA_SKIP_GREEN_CHECK`).
- Edit `CLAUDE.md`, unless the change's tasks say so and the evaluation cost was announced and accepted.
- Read the content folders (`Bibliotheque-*`, `Watch-Lab`, `Watch-Excluded`), the sensitive files of `Flux-Lab/` (`exports/`, `historique/`, `tableaux/`, `equipes-assets.yaml`, `noms-sensibles.txt`), the database backups or the journal.

## End

One single final message: tasks ticked by group with their suite, remaining tasks and why, then the commands the user must run (including the finishing command, not run).
