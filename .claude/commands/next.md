---
description: Proposes the jobs of the work queue that fit the time you have (reads docs/pmzilla/feuille-de-route.md, edits nothing)
argument-hint: "<duration, e.g. 2h, 1h30, 45min>"
model: sonnet
allowed-tools: Bash(uv run --with pyyaml python tools/roadmap.py next:*)
---

Work queue, time available: $ARGUMENTS

Language: this command is written in English, but serve the user in THEIR language (French by default when their request is in French).

## What you do

1. Run `uv run --with pyyaml python tools/roadmap.py next --budget <the duration given>`. The reader also reads the archive of finished jobs (`docs/pmzilla/feuille-de-route-archive.md`) to resolve dependencies: an archived identifier counts as done. This is the only command you run. The duration uses the same syntax as an estimate (`45min`, `2h`, `1h30`). Without a duration, ask for one and run nothing.
2. Present the result in the user's language and translate the enumerated values for display: `ready` is "prêt", `blocked` is "bloqué", `in-progress` is "en cours", `done` is "fait", `direct-prompt` and `openspec` stay as they are. For each proposed job give the identifier, the title, the estimate, the method, the model, the conditions the user must confirm and the due date when there is one, then the total of the time used.
3. List the jobs too long for the remaining time, and, apart, the jobs without an estimate (they are never counted in the budget).
4. Ask the user which job to start. Starting it is the user's decision, in a new request.

Exit codes of the reader: 1 means the queue is invalid (report each problem line as printed and propose nothing); 2 means a malformed duration (say so and ask again).

## What you never do

- Edit the queue document or run `done`; start a job; reorder the queue.
- Propose a job that is blocked, done, in progress, waiting for a dependency or before its start date: the reader already leaves them out, so do not add them back.
- Invent an estimate or a model, or count an unestimated job inside the budget.
- Run anything other than the reader's `next`: no other subcommand of the reader, no test suite, no evaluation set.
- Launch anything reserved to the user: the real Jira tools (`history_jira.py`, `export_jira_api.py`), `flow_import.py`, `flow_compare.py`, `knowledge_import.py` (import, verify, status), the indexer `pmzilla_lab_library.py` (`index`, `rename-collection`, `probe`, `status`), the database scripts (`db.py`, `db_backup.sh`, `db_up.sh`), any calculation with the database as source (`--source db`), any database client (`psql`, `docker exec`), book conversion, sorting and indexing, the branch-finishing script (`finish_branch.sh`), the owner bypass variable (`PMZILLA_SKIP_GREEN_CHECK`).
- Write a person's, team's or project's name in your answer.
