---
description: Shows the parallel sessions (worktrees, branches, features, state, finish lock, handoff notes) and what needs the user; launches nothing
argument-hint: ""
allowed-tools: Bash(uv run tools/pilot.py status:*), Bash(uv run tools/pilot.py freeze --check:*)
---

Show the state of the parallel sessions.

Language: this command is written in English, but serve the user in THEIR language (French by default when their request is in French). Translate the labels of the tool's lines for display; branches, commands and paths stay as they are.

This command reads and presents. It never launches, finishes, removes or writes anything.

## 1. Read

1. Run `uv run tools/pilot.py status`. The tool prints French lines (add `--language en` only if the user asks for English output): a header with the number of worktrees, one line per worktree with the fields folder, branch, link (`R-<n>`, `change <name>` and its feature, or a dash), state, commits ahead of and behind `main`, age of the last commit, `occupé` / `libre` / `inconnu` (a process has its current folder there, none, or the listing is impossible), `fusionnée, à retirer`, and the one-line handoff note; then the workspace line, the finish lock line and the run tree line.
2. If the status exits 3, say the command runs inside a clone of the repository and stop.
3. When the user asks whether tests or commits may run now, run `uv run tools/pilot.py freeze --check` (exit 0 free, exit 4 a finish is running) and say which.

## 2. Present

Show a table in the user's language, one row per worktree, then the finish lock and the run tree. Flag, in a short list under the table, only what needs the user:

- a worktree with modified files whose session has ended (no process in it, last commit old);
- a branch merged into `main` whose worktree is still there ("merged, to remove"): the user removes it;
- a stale finish lock ("verrou périmé"): the next finishing script takes it over, nothing to do by hand;
- a worktree `occupé` while the user wants to finish it: the user closes the session first;
- a worktree whose note says it is ready.

For a worktree whose note says it is ready, give its finishing command, labelled as the user's command, to type in the Terminal from the workspace: `bash tools/finish_worktree.sh <branch>`. Only one finish runs at a time: when the finish lock line shows a finish running, say so and give no second finishing command.

## 3. Notes

A note is set with `uv run tools/pilot.py note <branch> "<text>"` and cleared with `--clear`. Propose a note only when the user asks for one, show the exact command, and run it only after the user's yes (it is not pre-approved: the user approves it at the permission prompt). The tool refuses sensitive names, personal identifiers and ticket keys; never write one in a note.

## Never

- Run a finishing script (`tools/finish_branch.sh`, `tools/finish_worktree.sh`).
- Write a note without the user's yes, or read a note's file directly (the status shows it).
- Commit, merge, or push; use `--no-verify` or the owner bypass variable (`PMZILLA_SKIP_GREEN_CHECK`).
- Remove a worktree or a branch, or touch the finish lock.
- Write to GitHub, with `tools/gh_issue.py` or any `gh` command.
- Launch a session or `claude`, or open a Terminal.
- Launch anything reserved to the user: the real Jira tools (`history_jira.py`, `export_jira_api.py`), `flow_import.py`, `flow_compare.py`, the database scripts (`db.py`, `db_backup.sh`, `db_up.sh`), any calculation with the database as source (`--source db`), any database client (`psql`, `docker exec`).
- Read the content folders (`Bibliotheque-*`, `Watch-Lab`, `Watch-Excluded`) or the sensitive files of `Flux-Lab/`.
- Write a person's, team's or project's name in your answer.
