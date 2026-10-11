---
description: Closes an implemented OpenSpec change (ticks, status documents, CHANGELOG, archive, queue job done) and prints the finishing command
argument-hint: "<change name>"
model: sonnet
allowed-tools: Read, Grep, Glob, Edit, Write, Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(git add:*), Bash(ls:*), Bash(openspec list:*), Bash(bash tests/run_all.sh:*), Bash(uv run tools/identifiants_personnels.py:*), Bash(uv run --with pyyaml python tools/roadmap.py check:*)
---

Close the OpenSpec change: $ARGUMENTS

Language: this command is written in English, but serve the user in THEIR language (French by default when their request is in French).

## Sequence

1. **Tasks.** For each task of `openspec/changes/<change>/tasks.md`: tick it only if the suite it names passes now (targeted run of that suite). Otherwise leave it unticked and write the reason "(pas de test : …)" given by the user (a user step, a manual check). Never tick on your own judgement.
2. **Status documents.** Update the status documents the repository keeps, when there are any (a status line at the top of a design document, the matching entry of an evolutions list); when there is none, write nothing and create no entry. The dated history stays the CHANGELOG; no other log is fed.
3. **CHANGELOG.** Add the line under today's date.
4. **Archive.** Only if every unticked task carries a reason AND the user confirms: archive with the OpenSpec archive command. If an unticked task has no reason, do not archive and name the task.
5. **Queue.** Find the job of the queue (`docs/pmzilla/feuille-de-route.md`) whose `change` field names this change. If there is none, say so and edit no job (never invent one). Otherwise mark it `done` with the queue reader's `done` command and list the jobs the change unblocks, for the user to set `ready`. Then run the reader's `archive` command (it asks for permission, like `done`) and show what left the queue (the jobs moved to `docs/pmzilla/feuille-de-route-archive.md`); stage both files at the commit. A job that stays in the queue because an open job depends on it is not an error.
6. **Commit.** Stage files by name, run `uv run tools/identifiants_personnels.py` on them, run `bash tests/run_all.sh --staged` (no variable, no pipe, foreground), commit with `PMZILLA_NO_EVALS=1` when green. A test that needs the network and fails: stop and give the user the exact command for their Terminal, without a pipe.
7. **Hand over.** Print the finishing command for the user to type in the Terminal: `bash tools/finish_branch.sh`. Never run it.

## Never

- Run the branch-finishing script (`tools/finish_branch.sh`), push, or merge.
- Archive with an unticked task that has no reason.
- Use `--no-verify` or the owner bypass variable (`PMZILLA_SKIP_GREEN_CHECK`).
- Launch anything reserved to the user: the real Jira tools (`history_jira.py`, `export_jira_api.py`), `flow_import.py`, `flow_compare.py`, `knowledge_import.py` (import, verify, status), the database scripts (`db.py`, `db_backup.sh`, `db_up.sh`), any calculation with the database as source (`--source db`), any database client (`psql`, `docker exec`), the posture evaluation set.
- Read the content folders (`Bibliotheque-*`, `Watch-Lab`, `Watch-Excluded`), the sensitive files of `Flux-Lab/`, the database backups or the journal; write a person's, team's or project's name in any file.
