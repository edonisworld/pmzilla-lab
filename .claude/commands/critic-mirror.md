---
description: Critic's mirror, the objections that recur from one deliverable to the next, to spot recurring blind spots
argument-hint: "[period: nothing for the current month, or --since YYYY-MM-DD --until YYYY-MM-DD]"
---

This command is written in English, but the user is served in their own language (French by default when their request is in French). The fixed formulas are written in the language of the reply, as in `tests/postures/vocabulaire.yaml`: posture tag `[Posture : X]` (French) or `[Posture: X]` (English), "hors bibliothèque" or "outside the library", "J'en déduis" or "I infer", "Hypothèse" or "Hypothesis", "Ma lecture de cette critique" or "My reading of this critique". The section titles written by Critic are recognised in both languages (for example "Ce que Critic conteste / relève / a relevé" or "What Critic challenges / flags / raised", "Objections de Critic" or "Critic's objections", "Revue de Critic" or "Critic's review"). The mirror itself, its table, its categories and its file are written in the language of the reply.

Produce Critic's mirror. Period: $ARGUMENTS (nothing = the current month; at the start of a month, before the 8th, the month just ended).

The goal is not to re-judge the deliverables: it is to see **which Critic objections recur**, in which postures and types of deliverable, in order to fix the defect at its source.

## 1. The corpus

Run `uv run tools/critic_mirror.py --language <fr|en>` with the period options given in the arguments. `<fr|en>` is the language of the user's request (`fr` by default): the script writes its corpus, and the grid of step 2, in that language. The output lists each deliverable with its numbered objections (O1, O2…) and their total count. Do not read the deliverables themselves: the corpus is enough. If it holds fewer than 5 objections, say it is too early to talk about recurrence, give the raw list and stop.

## 2. The classification

Run `uv run tools/critic_mirror.py --categories --language <fr|en>` (same language as in step 1). It prints the grid of eleven categories with what each covers: it is the **only source** of the categories, so do not copy it from memory, rename or merge categories, and write the mirror with the names it prints.

Place **each** objection in **one single** category of that grid (the main one, if it touches several).

If three or more objections fall into the last category ("other" / "autre") with the same motive, propose a new category (name and definition), without adding it to the grid yourself: the grid changes in the script. Check that the classified total equals the number of objections in the corpus.

## 3. The mirror

1. **Table**: categories as rows, with the number of objections, the number of deliverables touched and the postures concerned; empty categories do not appear.
2. **The blind spots**: the two or three categories that recur most, **and only if they touch at least two deliverables**. For each, two short examples (O-number and one sentence), then what they have in common.
3. **The evolution**: if a previous mirror exists in `_bmad-output/pmzilla/miroir/`, compare category by category (what recedes, what rises, what appears). From one month to the next with few deliverables, a variation of one or two objections is not a trend: say so.
4. **The countermeasures**: for each blind spot, one concrete proposal that acts before Critic, for example a rule to add to `CLAUDE.md` or to a posture, a step in a command, a case or a criterion in the test set. **Only propose, apply nothing**: the user decides.
5. **The limits**: the mirror only sees saved deliverables (a session that was not kept leaves no trace); also list the deliverables of the period without a Critic section, which may have escaped review.

Rules: in the language of the reply, no em dash; roles, never names; what the corpus says is kept apart from what you infer ("J'en déduis" / "I infer", "Hypothèse" / "Hypothesis"); no objection invented or reworded to the point of changing its meaning.

## 4. Saving

The mirror is saved by default, so that the following month can compare against it: `_bmad-output/pmzilla/miroir/miroir-AAAA-MM.md` (month of the end of the period, written YYYY-MM; create the folder if needed; if the file exists, add `-2`, `-3`, never overwrite). The title gives the period and the number of objections. Commit nothing. Display the path, then the blind spots in three lines.
