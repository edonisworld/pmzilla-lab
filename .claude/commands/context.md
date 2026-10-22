---
description: Lists the organisation context notes, or drafts a new one from your text and writes it only after your explicit yes (tools/context_lab.py)
argument-hint: "[add <text>]"
model: sonnet
allowed-tools: Bash(uv run tools/context_lab.py list:*), Bash(uv run tools/context_lab.py check:*)
---

This command is written in English, but the user is served in THEIR language: answer in French by default, in English if the request is in English. This is a maintenance tool: announce no PMZilla posture and call no Critic.

A context note is a short, dated, distilled statement of the organisation's situation (roles, forums, flows, dependencies), kept outside the repository by the context tool. The notes reach the postures through the library search, never as files.

## `/context` alone

Run `uv run tools/context_lab.py list`, once, and show its lines with the stale notes first, then the valid ones, then the invalid ones with their reason. The last line gives the counts. Nothing else is run. If the exit code is 6, the context folder does not exist: tell the user to run `uv run tools/context_lab.py init` themselves.

## `/context add [text]`

1. Draft a note from the user's text: a short title, the body in the user's own words, each person replaced by their role, each team and project by a generic designation ("team A", "the platform team"), and no figure of a cell under five (write `masqué`, or `masked` in an English note).
2. Ask for each header field you cannot take from the text: nature (`declarative` for what someone said or wrote, `measured` for figures read in a flow report or an aggregated view), source (by role or document type), review date (propose three months after the note date). The date is the note's date.
3. Show the whole draft, header included, and wait for an explicit yes. No yes: write nothing and run nothing.
4. Pipe the validated draft to `uv run tools/context_lab.py add` and report its line. The permission prompt of this command is expected: `add` and `review` are not pre-approved.
5. On exit code 5, say which line of the draft to rewrite (the tool gives the line number only), never the value; on code 3, give the header rule it names; on code 4, the note exists and is never overwritten.

To change only the review date of a note, run `uv run tools/context_lab.py review <file> <YYYY-MM-DD>` after the user's yes.

## Forbidden

- Open, list or copy anything in the originals folder of the context space, or read the notes folder as files: the notes are read through the library only.
- Run the indexer `pmzilla_lab_library.py` (`index`, `rename-collection`, `probe`, `status`): the daily run indexes the notes.
- Write a person's name, or a figure of a cell under five.
- Run the real Jira tools (`history_jira.py`, `export_jira_api.py`), `flow_import.py`, `flow_compare.py`, `psql`, `db.py` (nor any calculation with `--source db`), a branch finish (`finish_branch`), or use `PMZILLA_SKIP_GREEN_CHECK` or `--no-verify`.
- Write to GitHub, push or merge.
