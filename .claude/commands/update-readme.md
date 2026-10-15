---
description: Updates the README with the latest changes to the repository and scripts, checks docs/pmzilla/installation.md, then commits
argument-hint: "[optional note on what changed]"
---

Language: this command is written in English, but serve the user in THEIR language (French by default when their request is in French). The fixed formulas (posture tag, "hors bibliothèque" / "outside the library", "J'en déduis" / "I infer", "Hypothèse" / "Hypothesis", Critic's titles, "Ma lecture de cette critique" / "My reading of this critique") are written in the language of the reply, as listed in `tests/postures/vocabulaire.yaml`. What you write into the README and into `docs/pmzilla/installation.md` follows the language of the file you are updating (both are currently in English), not the language of the conversation.

Update `README.md` so that it describes PMZilla Lab as it is today, check `docs/pmzilla/installation.md`, then commit. Optional note from the user: $ARGUMENTS

Two files, two regimes:

- `README.md`: you align it with the repository. Its sections "3. Step-by-step installation" and "11. Evolution ideas" keep only a paragraph of two to three lines and a link or a command: never recreate them in the README.
- `docs/pmzilla/installation.md`: you check it when a command, a script or a path has changed (step 2).

## 1. Find what changed

- Find the last commit that modified the README or `docs/pmzilla/installation.md`: `git log -1 --format=%H -- README.md docs/pmzilla/installation.md`. List what has changed since that commit (`git diff --stat <commit> HEAD` and `git status --short`), uncommitted changes included.
- Read the modified files that matter for the README and the installation: `CLAUDE.md`, `.claude/commands/`, `.claude/agents/`, `.claude/settings.json`, `watch/*.yaml`, `tests/postures/cas.yaml`, `docs/pmzilla/`, `tools/hooks/`, `tools/evals_auto.sh`, `tools/watch.sh`, `tools/com.pmzilla.watch.plist`, and the scripts in `tools/`.
- For each script in `tools/` (`*.py`), get its real commands and options with `uv run tools/<script>.py --help`, and `--help` on each subcommand (`convert_books.py` and `pmzilla_lab_library.py` have no help: read their header). Invent no command or option: only those the help displays exist.

## 2. Compare the README and the installation with what exists

List the gaps before writing.

For the **README**:

- **Commands**: every command and option of the scripts appears in the table or section where it belongs; every command cited in the README still exists, with the same syntax.
- **Rules**: a new or modified rule in `CLAUDE.md` (citations, privacy, routing, deliverables, watch) is summarized in the section it concerns. The README refers to `CLAUDE.md` for the detail, without copying the rule word for word.
- **Claude Code commands**: every file in `.claude/commands/` is presented (role, how to launch it, result).
- **Layout**: the repository and Mac trees match the real files (`ls`, `git ls-files`), `docs/pmzilla/installation.md` included.
- **Troubleshooting**: a problem encountered and solved since the README's last commit (visible in commit messages, `CLAUDE.md` or the reports in `_bmad-output/essais/`) has its line there, symptom and cause.
- **Installation and evolution ideas**: the README keeps only the paragraph and the link. Check that both links, the one in the table of contents and the one in the section, point to a file that exists. A step or an idea that has been copied into the README does not belong there: remove it and report it.

For **`docs/pmzilla/installation.md`**, only if a script, a command, an option, a path, a file name, a setting in `.claude/settings.json`, the hook, the launchd task, the "Add a book" procedure or the number of books has changed:

- every cited path exists (`ls`, without listing the contents of `Bibliotheque-MD`, `Bibliotheque-Lab`, `Watch-Lab`, `Watch-Excluded` or `Flux-Lab/exports`, which the `deny` rules forbid);
- every script command and every option exists in the help;
- the list of scripts linked into `~/PMZilla-Lab/` (step 3) matches those that `watch.sh`, `evals_auto.sh` and the documentation launch from that folder;
- the "Check the installation" section (headed "Vérifier l'installation" in a French version of the file) still gives the real result of each command (number of books, tags, task names);
- you run no installation command: you check that files, options and paths exist.

## 3. Write

- Change only what is out of line. Keep the structure, the tone and the direct address to the reader (the original is written in the second person, "tutoiement" in French).
- Writing rules: write in the language of the file you are updating (English for the README and `docs/pmzilla/installation.md` today), business terms unchanged (User Story, Refinement, Backlog, Sprint, Discovery, Definition of Done, etc.); no em dash (use colons, parentheses or separate sentences); no colleague's name; no information internal to a company.
- Mention neither backup nor Obsidian. The original books stay in `~/Downloads/Livres - Ressources`.

## 4. Check, then commit

- Reread the diff of the README and of `installation.md`. Check that every cited command exists in the scripts' help, that no internal link in the table of contents is broken (anchors of both files included).
- Display the list of the gaps handled (one line each) and those you left, with the reason.
- If neither the README nor `installation.md` has a gap, change nothing and commit nothing: just say so.
- Otherwise, commit only these two files, without touching what is already staged elsewhere: `git commit -m "README : <summary in a few words>" -- README.md docs/pmzilla/installation.md`, then `git push`. Tell the user about the other uncommitted changes you saw.
