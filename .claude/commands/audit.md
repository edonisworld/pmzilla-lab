---
description: Read-only repository audit, end-of-session check (default, about 5 minutes) or full audit with parallel agents
argument-hint: "[complet]"
model: sonnet
allowed-tools: Read, Grep, Glob, Agent, Write(.pmzilla/audit/**), Bash(git status:*), Bash(git log:*), Bash(git diff:*), Bash(git branch:*), Bash(git stash list:*), Bash(git rev-parse:*), Bash(bash tools/run_worktree.sh status:*), Bash(git ls-files:*), Bash(git grep:*), Bash(git show:*), Bash(ls:*), Bash(find:*), Bash(date:*), Bash(uv run tools/identifiants_personnels.py:*), Bash(uv run --with pyyaml python -I -c:*)
---

PMZilla Lab repository audit: $ARGUMENTS

Recommended model: Sonnet for the default mode (the header sets it); Opus for `complet` (start the session under Opus, or pass `model: "opus"` to the agents of that mode).

Language: this command is written in English, but serve the user in THEIR language (French by default when their request is in French).

Two modes, chosen by the first word of the arguments. No argument: default mode. `complet`: full mode.

## Rules of both modes

- Read only. You modify, move and delete no file and you make no commit. The only files you write are `.pmzilla/audit/AAAA-MM-JJ.md` (the report; if it already exists today, read it and add a section for this pass) and `.pmzilla/audit/dernier-commit` (the full hash of `HEAD` at the end of the pass, written last).
- No command on the database (no psql, no docker exec, no script of yours that connects to it), no Jira tool, no posture evaluation set, no test suite. Your Python is limited to loading YAML files and comparing lists, never anything that opens the database.
- Same reading bans as always: you read neither `Bibliotheque-*`, nor `Flux-Lab/` (except `rapports/` and `flux.yaml`), nor `Journal-Lab/`, nor `Watch-Lab/`, nor the backups, the exports or the books. In `.pmzilla/` you read only file names, plus `contexte.md`, `audit/dernier-commit` and the earlier reports of `audit/`.
- Nothing already covered by an OpenSpec change in progress: before listing a finding, check the `proposal.md` and `tasks.md` of the changes under `openspec/changes/` (not `archive/`); if the point is there, write "covered by <change>, task <n>" in the report instead of a finding.
- No team name, project name or person name in the report or the message: roles and generic designations.
- A finding that would require editing `CLAUDE.md` is a proposal only, and says that the edit needs the posture evaluation set (to be announced with its cost).
- Every finding is numbered and has an action, a proof (command or reference the user can replay) and a risk (low, medium, high). A file proposed for deletion also has what would be lost.
- The final message is short: counts by risk, the three findings that matter most, the path of the report, and it ends by asking which numbers to handle. You do not handle any yourself.

## Default mode (end of session, aim for 5 minutes)

Run these six checks, in this order, and report what you find:

1. **State for the night.** `git branch --show-current`, `git status --short`, commits not pushed (`git log @{u}..` when an upstream exists, else `git log origin/main..`), `git branch --no-merged main`, `git stash list`. The scheduled jobs run the run tree, not the development checkout: read `bash tools/run_worktree.sh status` and report the run tree first. A missing run tree (exit 4), a run tree on a branch or off the history of `main` (exit 6), with local changes (exit 5) or behind `main` (exit 8) is a numbered finding whose action is for the user: `bash tools/run_worktree.sh update` (or `create` when it is missing); you run neither. The development checkout's branch is not a risk for the night: a work branch there with a clean run tree at the tip of `main` is reported as no risk for the scheduled runs.
2. **OpenSpec changes not archived.** For each change under `openspec/changes/` except `archive/`: ticked tasks over total, and whether it looks ready to archive (all ticked, merged).
3. **Documentation.** Read `.pmzilla/audit/dernier-commit` (if absent, say so and use the last 20 commits). List the files changed since (`git diff --name-only <hash>..HEAD`, plus uncommitted and untracked files). For each changed command, posture, tool, rule or spec, check that `README.md` and `docs/pmzilla/installation.md` still describe it correctly (targeted grep, not full reads). CHANGELOG.md is frozen: report any change to it since the last audit as a finding.
4. **Books without a complete catalogue entry.** Load `tools/book_catalog.yaml` and the `MAPPING` of `tools/mapping_lab.py`; compare the file names after Unicode NFC normalization (`unicodedata.normalize("NFC", name)`), as the indexer does: two names that differ only by their Unicode form are the same book. List the active mapped books with no catalogue entry, and the entries without `titre` or without `auteurs`; list the `a_verifier` entries apart. File name and title only.
5. **Identifier scanner.** For each file changed or untracked and not ignored, run `uv run tools/identifiants_personnels.py --fichier <file>` and report the files with a hit (never copy the identifier found).
6. **Backup or temporary files left.** By name only: `*.avant-*`, `*.pending`, `*.patch`, `*.orig`, `*.bak`, `*.tmp`, `*.swp`, `*~` in the repository and in `.pmzilla/` (names only), with their date (`ls -l`). Propose no deletion without proof that nothing references them (`git grep`).

## Full mode (`complet`)

Same rules. Launch one agent per domain in parallel, in a single message, each with `model: "opus"`, each read-only and briefed with the rules above (it knows nothing else):

- (a) Documentation: README, `docs/pmzilla/`, checked against `openspec/specs/` (they prevail) and `git log`: what is false, outdated, duplicated or missing (PostgreSQL and schemas, cases module, own-articles and local layers, OpenSpec, hooks, agents, model rule, number and list of books against `book_catalog.yaml` and `mapping_lab.py`, entries without an author).
- (b) Code: `tools/` and root scripts never called (by another script, a test, `.claude/settings.json`, a command or agent of `.claude/`, the launchd plists, the `~/PMZilla-Lab/*.py` links: check their targets with `ls -l`), dead options and functions, whether the SQLite route is still needed.
- (c) Tests: orphan tests, duplicates, tests of removed code, suites missing from `tests/run_all.sh`. Do not touch `openspec/test-gaps.md`.
- (d) Configuration: `.claude/` (commands, agents, settings), `.gitignore`, OpenSpec changes and specs, backup files of `.pmzilla/` by name.

Then run the six checks of the default mode yourself. Merge everything into one report with four tables: to correct, to complete, to delete, to keep despite appearances; each line numbered with action, proof and risk. Follow with a cleanup plan in thematic commits on a `chore/...` branch, marking what suits parallel agents (distinct files only).
