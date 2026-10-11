---
description: Coaching journal, log a session, review the promised follow-ups, take stock of what works
argument-hint: "add <what happened> | follow-ups [scope] | review [period or scope] | start | note <n> | show <n> | postpone <n> <duration> | drop <n> | close <n> | due"
---

PMZilla Lab coaching journal: $ARGUMENTS

Language: this command is written in English, but serve the user in THEIR language (French by default when their request is in French). The fixed formulas (posture tag, "outside the library", "I infer", "Hypothesis", Critic's section titles, "My reading of this critique") are written in the language of the reply, as in `tests/postures/vocabulaire.yaml`. In French: `[Posture : Discovery]`, "hors bibliothèque", "J'en déduis", "Hypothèse", "Ma lecture de cette critique". In English: `[Posture: Discovery]`, "outside the library", "I infer", "Hypothesis", "My reading of this critique". Critic's section titles follow the language of the reply too (French "Ce que Critic conteste", English "What Critic challenges"). The journal entry keys (`tente`, `constat`, `suites`, `quoi`, `pour`, `echeance`, `statut`, `note`, `resultat`) and the status values (`ouverte`, `en cours`) stay in French, whatever the language of the reply. The draft keys of the experiment modes (`start`, `note`, `close`) are in English, as `journal_lab.py` reads them.

The journal lives in `Journal-Lab/journal.yaml`, outside Git, and is modified only through `uv run tools/journal_lab.py` (never by hand). The first word of the arguments chooses the mode, named after the subcommand of `journal_lab.py` that it runs: `add`, `follow-ups`, `review`, or one of the experiment modes `start`, `note <n>`, `show <n>`, `postpone <n> <duration>`, `drop <n>`, `close <n>`, `due` (they run `experiment <mode>`). These English names are the only ones: no French alias. The period `review` is not the closing of an experiment (`close`). With no argument, take `follow-ups`.

**Absolute rule**: roles and scopes (team, domain), never names of people. If the account contains a name, replace it with the role before writing, and say so. No judgment about a person: record what was tried and what was observed about the working system.

## Mode `add`: log a session

1. From the account, fill in the fields of an entry (see `uv run tools/journal_lab.py --help`, FORMAT section):
   - `type` (atelier, rétro, coaching, CoP, formation, diagnostic, autre), `perimetre`, the `posture` concerned;
   - `tente`: what was tried, in one or two sentences;
   - `constat`: what worked or not, and **how you can tell**;
   - `suites`: each commitment made, with the role that carries it and a due date;
   - Never an `experience` block: it is deprecated. If the session launched a trial to be evaluated later (including the hypotheses and experiments designed with the Discovery posture), do not put it in the entry: propose mode `start` below once the entry is written.
2. If the essentials are missing (scope, finding, due date of a follow-up), ask **a single grouped question**. Never complete a finding or a follow-up that the account does not contain.
3. Show the entry in a few lines, then write it as YAML in `Journal-Lab/_brouillon.yaml` (texts in quotes or in a `|` block, so that colons do not break the YAML) and run `uv run tools/journal_lab.py add Journal-Lab/_brouillon.yaml`. If the entry is rejected, fix what the message says and run it again.
4. Finish by recalling the other follow-ups still open on this scope (`follow-ups --scope`), and, if a trial was launched, by proposing `start`.

## Mode `follow-ups`: before a session, or on Monday

1. Run `uv run tools/journal_lab.py follow-ups`, with `--scope "<scope>"` if one is given.
2. Present the overdue follow-ups first, then the upcoming ones, then the experiments whose review is due (the YAML ones and, when an author is configured, those of the cases module).
3. Ask which ones are done or abandoned, and update them (`update <id> faite|abandonnee --note "…"`). For an old YAML experiment (id ending in `.x`), ask what was observed and conclude it (`update <id> conclue --note "<result>"`): the result compares the expected signal with what happened, without rounding a failure up to a success. For an experiment of the cases module (a number), use `close <n>`, `postpone <n> <duration>` or `drop <n>` below.

## Mode `review`: what works, and in which context

1. Run `uv run tools/journal_lab.py review`, with `--since` (30 days by default; "quarter" = 90 days) and `--scope` if they are given.
2. Analyze:
   - what was tried and what worked, **depending on the context** (type of session, scope, posture);
   - the follow-ups: the share kept, the ones that drag on, and what they have in common;
   - the concluded experiments: hypotheses confirmed or not;
   - what comes back from one session to the next (obstacles, topics, reactions).
3. To shed light on a mechanism, search the library (`search_library`) and cite book and section. Always distinguish what the journal says from what you infer from it ("I infer", "Hypothesis" in English; "J'en déduis", "Hypothèse" in French). With fewer than five sessions on a context, draw no rule from it: say it is too early.
4. Pass the review to the `pmzilla-critic` subagent: it checks that each conclusion rests on several sessions of the journal, and that none targets a person. Call it in the foreground, never in the background, giving it only the request and the deliverable, and do not end your turn before it has answered. The final message is single and follows the restitution rule of `CLAUDE.md`, in this order: (a) the posture's response, with its analysis and key points; (b) a short section `[Posture : Critic]` (French) / `[Posture: Critic]` (English) that summarizes the objections in a few lines; (c) "Ma lecture de cette critique" / "My reading of this critique": what you keep, what you set aside and why. Never a message that announces that Critic is examining the deliverable and that the result will follow. A saved review keeps Critic's complete answer in its file, under "Ce que Critic conteste" / "What Critic challenges".
5. Nothing is saved, unless the user says "keep this review" ("garde ce bilan" in French): then write it to `Journal-Lab/bilans/bilan-AAAA-MM-JJ.md` (outside Git, like the journal), without overwriting an existing file.

## Experiment modes (cases module)

These modes run `uv run tools/journal_lab.py experiment <mode>`. Same absolute rule as for `add`: roles and generic designations only ("a team of the pilot domain", "team A"), never a name of a person, a team, a project or a ticket key. The author is read by the tool (`PMZILLA_LAB_CASES_AUTHOR` or `.pmzilla/cases.yaml`); never ask for or write it, nor any database password. Drafts are YAML files written in `Journal-Lab/_brouillon.yaml` (texts in quotes or in a `|` block); the tool deletes the draft after a success and keeps it after a refusal: fix what the message says and run it again. Exit codes: 0 success, 1 refused draft or rule, 2 database unreachable, author not configured, sensitive-names list missing, or embedding service unavailable (say which, do not retry in a loop).

### Mode `start`: start an experiment

1. At the end of a session, propose the draft yourself, from the account, in these keys: `problem` (the problem, reformulated), `context` (a mapping with at least one of `team_type`, `team_size`, `phase`, in generic designations), `hypotheses` (list, optional), `chosen_path` (optional), `references_used` (list, optional), `tested` (what is tested), `expected_signal`, `success_criterion` (all three required), `posture` (`discovery`, `delivery`, `scaling`, `facilitation` or `none`), `review_due` (by default in six weeks, `YYYY-MM-DD`; omit it to let the tool apply the default), `date` (optional, never in the future).
2. Never complete a required field that the account does not contain: ask a single grouped question.
3. Show the draft in a few lines. The user rereads and validates it. **Never start without that validation.**
4. Write the draft, run `uv run tools/journal_lab.py experiment start Journal-Lab/_brouillon.yaml`, and report the number and the review date it prints.

### Mode `note <n>`: add a dated note

Draft keys: `note` (required), `date` (optional, never in the future). Show it, then write it and run `experiment note <n> Journal-Lab/_brouillon.yaml`.

### Mode `show <n>`: read an experiment

Run `experiment show <n>` and restate the experiment and its notes (any author's experiment can be read).

### Mode `postpone <n> <duration>`: move the review date

Run `experiment postpone <n> <duration>` (`10d` or `2w`) and report the new date and the postponement count. After two postponements the subcommand refuses: do not insist, ask the user to choose between `close <n>` and `drop <n>`.

### Mode `drop <n>`: drop without lesson

Confirm with the user that the experiment is dropped without a lesson (no case is created; to keep a lesson, use `close <n>`), then run `experiment drop <n>`.

### Mode `close <n>`: close into a case

1. Run `experiment show <n>`; reread the success criterion and the notes.
2. Propose an outcome among `worked`, `partly`, `failed`, `dropped`, by comparing the expected signal with what happened, without rounding a failure up to a success. Also propose `what_got_stuck` and `confidence` (`low`, `medium`, `high`) when the notes support them. `drop_reason` is required with `dropped` and refused with any other outcome. `date` is optional (not in the future, not before the start).
3. Ask the user to validate the outcome. **Never close without that validation.**
4. Write the close draft (`outcome`, `what_got_stuck`, `confidence`, `drop_reason`, `date`), run `experiment close <n> Journal-Lab/_brouillon.yaml`, and report the case number it prints.

### Mode `due`: reviews that are due

Run `experiment due`. Present the reviews due (number, due date, problem, whether a decision is required), then ask for each one which way to settle it: `close <n>`, `postpone <n> <duration>` or `drop <n>`.
