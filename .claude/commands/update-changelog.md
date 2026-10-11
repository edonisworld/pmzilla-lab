---
description: Updates CHANGELOG.md with the commits made after its latest date, without rewriting existing entries, and shows the diff before any commit
argument-hint: "[optional note on what changed]"
---

This command is written in English, but the user is served in their own language: answer in French by default when the request is in French (otherwise in the language of the request). The fixed formulas (posture tag, "hors bibliothèque", "J'en déduis", "Hypothèse", Critic section titles, "Ma lecture de cette critique") are written in the language of the answer, as listed in `tests/postures/vocabulaire.yaml` (French: `[Posture : X]`, "hors bibliothèque", "J'en déduis", "Hypothèse", "Ma lecture de cette critique"; English: `[Posture: X]`, "outside the library", "I infer", "Hypothesis", "My reading of this critique"). A request in French keeps producing an answer in French with the French formulas.

Update `CHANGELOG.md` with the recent changes of the repository. Optional note from the user: $ARGUMENTS

## 1. Find what is missing

- Read the most recent date of `CHANGELOG.md` (the first `## YYYY-MM-DD` heading) and the hashes already cited in the file.
- List the later commits with `git log --since=<that date> --date=short --pretty=format:'%ad %h %s'`. Commits made on the day of that date whose hash is not in the file count too.
- Add only the missing entries: never rewrite, rephrase or reorder existing entries.

## 2. Write the entries

- Write the new lines in the language of the existing entries of `CHANGELOG.md` (French until lot 8 of the English version), and the section titles likewise: they follow those already in the file ("Ajouté", "Modifié", "Corrigé", "Retiré", or their equivalents if the file changes language).
- One `## YYYY-MM-DD` heading per day on which there was a real change, from the most recent to the oldest; if the date already exists, complete its sections.
- Under each date, at most four sections, only those that have content: "Ajouté" (Added), "Modifié" (Changed), "Corrigé" (Fixed), "Retiré" (Removed).
- One line per change, written for a reader and not copied from the commit message: what changes for the PMZilla Lab user (command, posture, tool, `CLAUDE.md` rule, test set, library, watch, flow). Group several commits of the same day on the same subject into one line. Add the short hash in parentheses at the end of the line.
- Exclude: automatic commits of the test reports ("Jeu d'essai des postures : …") and of automatic README updates, pure formatting commits, merges.

## 3. Writing rules

- In the language of the existing entries (see above), business terms in English, no em dash.
- Roles, never names of people, including in a reused commit message.
- Nothing confidential about the company or its teams, no figure taken from the Jira exports.
- No downloaded or removed book title presented as an acquisition: for the library, write "N livres ajoutés au catalogue" or "catalogue corrigé (auteurs)" (in English: "N books added to the catalog" or "catalog corrected (authors)", according to the language of the file), without a list.

## 4. Show, then commit

- Display the diff of `CHANGELOG.md` (`git diff CHANGELOG.md`) and wait for the user's agreement before any commit.
- If nothing is missing, say so simply: change nothing and commit nothing.
- After agreement: `git commit -m "docs: CHANGELOG mis à jour" -- CHANGELOG.md`, then `git push`. `CHANGELOG.md` is not watched by the post-commit hook: this commit does not relaunch the test set.
