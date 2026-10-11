---
description: Starts a job of the work queue (reads its description, creates its branch, runs it as a direct prompt or through /implement), marks it done on the branch and prints the finishing command
argument-hint: "<job id, e.g. R-19>"
allowed-tools: Read, Grep, Glob, Edit, Write, Agent, Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(git checkout -b:*), Bash(git add:*), Bash(ls:*), Bash(openspec list:*), Bash(openspec validate:*), Bash(bash tests/run_all.sh:*), Bash(uv run tools/identifiants_personnels.py:*), Bash(uv run --with pyyaml python tools/roadmap.py check:*), Bash(uv run --with pyyaml python tools/roadmap.py next:*)
---

Start the job of the work queue: $ARGUMENTS

Language: this command is written in English, but serve the user in THEIR language (French by default when their request is in French).

## 1. Read and check the job (write nothing yet)

1. Without an identifier, ask for one and do nothing else.
2. Run `uv run --with pyyaml python tools/roadmap.py check`. If the queue is invalid, report each problem line and stop.
3. Read `docs/pmzilla/feuille-de-route.md`: the job's entry in the YAML block and its prose paragraph under "Travaux décrits" (the paragraph that starts with its identifier). No paragraph: work from the title alone and say so.
4. Refuse to start, and say why, when the job is unknown, not `ready` (`blocked`, `in-progress` or `done`), has a dependency that is not `done`, or has a `not_before` date later than today. Never change a state to make it startable.
5. Non-empty `conditions`: quote them and ask the user to confirm they hold. Start only after an explicit yes.
6. Model: the job's `model` field is the model to work with. If it differs from the session's model, say so and ask the user to switch with `/model <alias>` before going further; `tbd` means the user chooses. This command fixes no model.

## 2. Branch

- If the working tree is not clean, stop and list the files.
- Never write or commit on `main`. From `main`, create the branch BEFORE writing anything: for a `direct-prompt` job, `chore/<id in lower case>-<short slug of the title>` (for example `chore/r19-pre-tri-robuste`); for an `openspec` job, the branch that `/implement` names.
- On another branch: ask whether to work on it or to go back to `main` first. Never start a job on the branch of another job without the user's yes.

## 3. Do the job

- **`direct-prompt`**: the prose paragraph is the brief. A step the paragraph marks as needing the user's decision is a stop: present the options and wait.
- **`openspec` with a `change` field**: read `.claude/commands/implement.md` and follow it for that change, every rule included.
- **`openspec` without a `change` field**: the change does not exist yet. Have it written by the `spec-writer` agent in Change mode (proposal, tasks, delta specs), run `openspec validate --strict` on it, then stop and ask the user to review it. Implementation starts only after their yes, through `.claude/commands/implement.md`.

Permanent rules, for every method:

- Tests first, then code. While working, run only the suites touched, quietly, with the dependencies of `tests/run_all.sh`.
- Before each commit: run `uv run tools/identifiants_personnels.py` on the files you wrote; stage files by name; run `bash tests/run_all.sh --staged` (no variable, no pipe, in the foreground); commit only when it is green, with `PMZILLA_NO_EVALS=1` on the commit. One commit per coherent unit, with its CHANGELOG line and its documentation in the same commit.
- A test that needs the network and fails: do not work around it; stop and give the user the exact command for their Terminal, without a pipe.
- Roles, never names: write no person's, team's or project's name in any file.

## 4. Mark the job done, on the branch

1. When the work is committed and green, run `uv run --with pyyaml python tools/roadmap.py done <id>` (it asks for permission), then `uv run --with pyyaml python tools/roadmap.py check`.
2. List the jobs whose dependencies are now all `done` (the reader names them): the user decides whether to set them `ready`.
3. Commit the queue change (staged run, as above).
4. A job left unfinished (user step pending, decision awaited): do not mark it `done`; say what remains.

## 5. Hand over

One single final message: what was done, by commit; what remains and why; the commands reserved to the user; then the finishing command for the user to type in the Terminal: `bash tools/finish_branch.sh`. Never run it.

## Never

- Push, merge, or run the branch-finishing script (`tools/finish_branch.sh`).
- Use `--no-verify` or the owner bypass variable (`PMZILLA_SKIP_GREEN_CHECK`).
- Reorder the queue, change a job's estimate, model or dependencies, or start a job the checks of step 1 refuse.
- Edit `CLAUDE.md`, unless the job says so and the posture evaluation cost was announced and accepted.
- Launch anything reserved to the user: the real Jira tools (`history_jira.py`, `export_jira_api.py`), `flow_import.py`, `flow_compare.py`, `knowledge_import.py` (import, verify, status), the database scripts (`db.py`, `db_backup.sh`, `db_up.sh`), any calculation with the database as source (`--source db`), any database client (`psql`, `docker exec`), book conversion, sorting and indexing, the posture evaluation set (announce its cost and wait).
- Read the content folders (`Bibliotheque-*`, `Watch-Lab`, `Watch-Excluded`), the sensitive files of `Flux-Lab/` (`exports/`, `historique/`, `tableaux/`, `equipes-assets.yaml`, `noms-sensibles.txt`), the database backups or the journal.
