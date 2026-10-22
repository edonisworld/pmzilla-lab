# Agent preamble

Standing rules for every agent prompt of the lab. Paste the "Standing rules" block at the top of an agent prompt, then add the task. The block holds no absolute path: relative commands are run from the folder of the worktree the agent works in. The rule of the freeze and the commit rule per agent kind come from the change `multi-session-piloting` (design D9), the three rules on commands and file changes from its design D12.

## Standing rules

- Modify every file with the Edit tool (Write only to create a new file); never with a script, `sed -i`, or a shell redirection (`>`, `>>`, `tee`, heredoc).
- Never pipe a command into `python3`, `grep` or `tail`: read a command's output as it is, or use your own tools for searching and reading. The one exception is `tail` right after the targeted test runner (`tests/run_all.sh`) or `unittest`.
- A change that adds or removes deny rules declares the rules to add through a `--json` list function in its settings_deny test; the shared guard must pass on it: no `Write(path)` or `NotebookEdit(path)` rule (an `Edit(path)` rule covers every editing tool), no empty permission key, no duplicate.
- Run only the commands your agent definition and your prompt allow, read-only searches included.
- Before each test run and each commit, run `uv run tools/pilot.py freeze --wait 60`. If it exits 4, stop and report: a branch finish is running and the tests are frozen.
- On a permission refusal, stop and report the exact message; never retry another way and never work around it.
- Never read the content folders (watch, library, images), the sensitive files of the flow folder, or any local file ignored by Git, except through the tools your prompt names.
- No person, team or project name in a tracked file, a commit message or an issue: roles and generic designations only.
- Run suites with the targeted command your prompt gives; never the complete runner, which is reserved to the end of a branch.

## Who commits

- An implementation agent (Sonnet) commits on its own branch, in its own worktree, after a green run of its suites and the freeze command above.
- A framing agent (`spec-writer`, Opus) never commits; the orchestrating session commits its work after review and says so.
- A review agent (Opus) never commits and changes no file; its findings go in its final message.
- A search agent (Haiku) never commits and changes no file; it lists, counts or checks and reports.
- No agent runs a finishing script, and no agent may merge, push, remove a worktree, or write to GitHub other than through the write tool when its prompt allows it. The finishing scripts are typed by the author in a Terminal, one finish at a time.
- A merge of `main` into a branch is simulated only on the committed tip, after the archive of its change is committed, and by the author (a step file or `bash tools/finish_worktree.sh <branch>`, which previews the merge itself): every Git command holding `merge`, the read-only previews included, is refused to sessions and agents.
