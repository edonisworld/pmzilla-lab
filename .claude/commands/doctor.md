---
description: Runs the read-only health check of the lab (tools/doctor.py), explains each check that is not ok and gives the commands for the user to run
argument-hint: "[fr|en]"
model: sonnet
allowed-tools: Bash(uv run tools/doctor.py:*)
---

This command is written in English, but the user is served in THEIR language: answer in French by default, in English if the request is in English. Pass `--language en` to the script for an English user, `--language fr` otherwise ("$ARGUMENTS" may give the language). This is a maintenance tool: announce no PMZilla posture and call no Critic.

## 1. Run the check

Run `uv run tools/doctor.py --language fr` (or `--language en`), once, never with `--record`. That is the only command you run. Exit code 0: no check is a problem; 1: at least one check is a problem; 2: usage error or the doctor cannot run (give the message as is).

If the exit code is 0 and no check is a warning, say so in one line and run nothing else.

## 2. Explain each check that is not ok

Levels: `ok`, `warning`, `problem`, `skipped` (with its reason). The 12 checks are `db`, `ollama`, `models`, `launchd`, `watch`, `backup`, `offsite`, `parity` (only while a parity window is open), `disk`, `jira`, `branches`, `run-worktree`. For each check that is a problem or a warning (and each skipped one that matters), give: what it means, the consequence, and the next step as a command for the user to run in the Terminal, never run by you. Problems first.

- `db`: the database is not reachable. Next step: `bash tools/db_up.sh`.
- `ollama`: Ollama does not answer. Next step: `ollama serve`.
- `models`: a model of the repository constants is missing. Next step: `ollama pull <model>` for the model named in the line.
- `launchd`: a scheduled job is not loaded or not as expected. Next step: the install script of the job named in the line, run by the user.
- `watch`: the watch did not run when due. Next step: run the watch again (the user's usual watch command), then look at its log.
- `backup`: the database backup is late or missing. Next step: the user's usual backup command.
- `offsite`: the off-site copy is old. Next step: `bash tools/offsite_backup.sh copy`.
- `parity`: the parity window is open and a check is missing. Next step: the parity run named in the line.
- `disk`: free space is low. Next step: free space (old backups, models, build caches) after the user has looked at what is large.
- `jira`: the Jira token expires soon or has expired. Next step: the user renews it themselves; you never read or ask for the token.
- `branches`: branches are merged or stale. Next step: the user reviews them and deletes the ones they choose.
- `run-worktree`: the worktree for the scheduled runs is missing or off. Next step: the user recreates or updates it.

Offer to explain further, but fix nothing.

## Forbidden

You repair nothing. You run no command other than `uv run tools/doctor.py` without `--record`: no `--record`, no `tools/doctor.sh` (the scheduled wrapper), no `launchctl`, no `security` (Keychain), no `psql`, no `docker`, no `db.py`, no `--source db`, no `history_jira`, no `export_jira_api`, no `flow_import`, no `flow_compare`, no `knowledge_import`, no `finish_branch`, no `PMZILLA_SKIP_GREEN_CHECK`. You start, load, unload, pull, delete and prune nothing, and you edit no file. The commands above are given to the user as text.
