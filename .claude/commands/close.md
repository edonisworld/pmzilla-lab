---
description: Closes an implemented OpenSpec change (ticks, status document, archive, GitHub feature synced and closed) and prints the finishing command
argument-hint: "<change name>"
model: sonnet
allowed-tools: Read, Grep, Glob, Edit, Write, Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(git add:*), Bash(ls:*), Bash(openspec list:*), Bash(bash tests/run_all.sh:*), Bash(uv run tools/identifiants_personnels.py:*), Bash(uv run --with pyyaml python tools/roadmap.py show:*)
---

Close the OpenSpec change: $ARGUMENTS

Language: this command is written in English, but serve the user in THEIR language (French by default when their request is in French).

## Sequence

1. **Tasks.** For each task of `openspec/changes/<change>/tasks.md`: tick it only if the suite it names passes now (targeted run of that suite). Otherwise leave it unticked and write the reason "(pas de test : …)" given by the user (a user step, a manual check). Never tick on your own judgement.
2. **Status documents.** Update the status documents the repository keeps, when there are any (a status line at the top of a design document); when there is none, write nothing and create no entry.
3. **History.** CHANGELOG.md is frozen: add no entry; the milestone's closed features feed the release notes.
4. **Sync.** Find the feature whose `change` is this change: take the identifier `R-<n>` cited in the change's `proposal.md` or `tasks.md`, run `uv run --with pyyaml python tools/roadmap.py show <id>` and check that its `change :` line is this change. If no identifier is cited or the line differs, ask the user for the identifier and write nothing to GitHub: never invent a feature. Otherwise run `uv run tools/gh_issue.py sync-tasks <id>` now, before the archive (the tool refuses an archived change); the write is approved by the user at the permission prompt. On exit code 8 (state unknown): stop, show the check command the tool printed, make no further GitHub write until the user has checked, and never say the write was not sent.
5. **Archive.** Only if every unticked task carries a reason AND the user confirms: archive with the OpenSpec archive command. If an unticked task has no reason, do not archive and name the task.
6. **Close the feature.** After the archive, before closing the feature, list the paths changed on the branch since its merge base with `main` (`git diff --name-only main...HEAD`, which compares against that merge base) and check them against the include and template rules of `edition/manifest.yaml`. When at least one changed path enters the edition, name those paths, propose the label `edition:public` and pass `--edition-public` to `close-feature` only after the user's yes; the tool adds the label before closing. Otherwise say that no path of the edition changed and pass no option. Then run `uv run tools/gh_issue.py close-feature <id>` (approved at the permission prompt). When user-step sub-issues remain open, the feature stays `In progress`: list them. List the features the closure unblocks, for the user to set `Ready`. When an agent sub-issue stays open and every unticked task of its group carries a reason, propose `uv run tools/gh_issue.py close-step <key> --reason "<reason>"` and run it only after the user's yes; the tool refuses an agent sub-issue without `--reason` (exit 7). Never propose it for a group with an unticked task without a reason: name that task. On exit code 8 from any of these commands: same stop as in step 4.
7. **Commit.** Stage files by name, run `uv run tools/identifiants_personnels.py` on them, run `bash tests/run_all.sh --staged` (no variable, no pipe, foreground), commit with `git commit` alone (no `NAME=value` before it) when green. Never set `PMZILLA_AFTER_COMMIT`; the variables a commit needs come from the session's environment (worktree script `tools/worktree.sh`). A test that needs the network and fails: stop and give the user the exact command for their Terminal, without a pipe.
8. **Hand over.** Print the finishing command for the user to type in the Terminal: `bash tools/finish_branch.sh`. Never run it.

## Never

- Write to GitHub other than through `tools/gh_issue.py`; use any `gh` command to write; pre-approve either in a header.
- Run the branch-finishing script (`tools/finish_branch.sh`), push, or merge.
- Archive with an unticked task that has no reason.
- Use `--no-verify` or the owner bypass variable (`PMZILLA_SKIP_GREEN_CHECK`).
- Launch anything reserved to the user: the real Jira tools (`history_jira.py`, `export_jira_api.py`), `flow_import.py`, `flow_compare.py`, the indexer `pmzilla_lab_library.py` (`index`, `rename-collection`, `probe`, `status`), the database scripts (`db.py`, `db_backup.sh`, `db_up.sh`), any calculation with the database as source (`--source db`), any database client (`psql`, `docker exec`), the posture evaluation set.
- Read the content folders (`Bibliotheque-*`, `Watch-Lab`, `Watch-Excluded`), the sensitive files of `Flux-Lab/`, the database backups or the journal; write a person's, team's or project's name in any file.
