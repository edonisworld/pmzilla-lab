---
name: audit-pasted-story
description: "Audit a story (or an epic's readiness and splitting) that the user pastes, with the effective grid of grid --show"
code: SQ
added: 2026-10-20
type: prompt
---

# Audit a pasted story

The standing order « Pasted story or epic (manual mode) » of the CREED governs this capability: every point of it holds here. Never run `story_quality.py collect`, `review`, `analyse` or `coach`, and never ask the user to paste coaching feedback into an answer or a deliverable: coaching results enter no report, dashboard or deliverable. Asked to show the organisation overlay, run `grid` (its versions and counts), then `grid --show` (its effective criteria), and show what they print; never read its file directly, and never propose to open it in an editor. This holds also for what the two commands do not print, such as the reason a criterion is disabled: say that it is not shown here, and never send the user to the file, to an editor or to another workspace to find it.

## What Success Looks Like

The user gets, for the story they pasted, a reading they can take back to the PO. The answer contains:

- the notice of the manual mode, once, in the reply language;
- one verdict per story criterion of the effective grid (`met`, `not_met`, `not_applicable` or `undetermined`), each with its reason read in the pasted text and its source line copied as `grid --show` prints it (transposition formula included, no criterion without its line), or the mark `règle de l'organisation` (organisation rule) for a criterion of the organisation overlay;
- for an epic, only its readiness and splitting criteria, with no verdict, splitting lead or short answer made to depend on the problem or the outcome; its problem, outcome and measure go to Discovery with the switch formula;
- rewrite suggestions for the PO (a vague acceptance criterion rewritten so that it can be tested, for example), presented as suggestions, never as a verdict, and kept in the answer even when Critic nuances them;
- the Critic section and your reading of the critique, since the audit is a diagnosis built from data the user supplied.

## Your Approach

1. Search the cases with the problem reworded (for example "stories not ready at Sprint planning"), never with the pasted text, its key or a name it holds. Then query the library (domains `flow`, `tech`, and `produit` for the story criteria, for example "acceptance criteria", "splitting user stories", "INVEST"), in French and in English, only to confirm or nuance a source line the grid prints.
2. Run `uv run tools/story_quality.py grid --show` (with `--language en` for an English reply). Apply what it prints, never a grid from memory. If it says there is no organisation overlay, say that the core grid applies alone.
3. Judge each criterion on the text alone. When the text does not allow a judgement (independence and estimability often depend on the team), the verdict is `undetermined`, not `met`. Apply each criterion's "not applicable" condition as printed.
4. Replace a name found in the text by the role when it is known, otherwise by "a person" (« une personne » in French). Never quote the ticket key.
5. Call `pmzilla-critic` in the foreground with the request and the audit, according to the rule « End of answer: Critic » of the CREED.
6. Write nothing unless the user explicitly asks to keep. Then write one file in `<project-root>/_bmad-output/pmzilla/internes/` (ignored by Git), never in `_bmad-output/pmzilla/` itself, with the verdicts, the learning points and a summary of Critic's objections only (the objection alone, for example "acceptance criterion not testable"), the request at the top reworded, without quoting or rewording the story, without its key or a name. Nothing of the story goes to the sanctum, the coaching journal, a case, an experiment or GitHub.

When the user asks instead what the latest story quality report says about a team's chain, read only that team's sub-section of the `qualite-stories-*` report (or the quality views through `uv run tools/flow_views.py show`), and the lines linked to the ticket template, the Definition of Ready or Refinement, each opened with the hypothesis formula as a lead to check with the team. Asked to compare two teams, read one and offer the other separately: no common table, no rate computed for both. The product-chain section is read the same way, with no team named.
