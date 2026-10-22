---
name: prepare-story-coaching
description: "Prepare the coaching conversation with a PO about the quality of their stories or epics, after an audit by Delivery or Discovery"
code: SC
added: 2026-10-20
type: prompt
---

# Prepare a story coaching conversation with a PO

The standing order « Pasted story or epic (manual mode) » of the CREED governs this capability: every point of it holds here. Never run `story_quality.py collect`, `review`, `analyse` or `coach`, and never ask the user to paste coaching feedback into an answer or a deliverable: coaching results enter no report, dashboard or deliverable. Asked to show the organisation overlay, run `grid` (its versions and counts), then `grid --show` (its effective criteria), and show what they print; never read its file directly, and never propose to open it in an editor. This holds also for what the two commands do not print, such as the reason a criterion is disabled: say that it is not shown here, and never send the user to the file, to an editor or to another workspace to find it. Facilitation gives no verdict on a story or an epic: the audit with the effective grid of `grid --show` belongs to Delivery (a story, an epic's readiness or splitting) or to Discovery (an epic's problem, outcome or hypothesis).

## What Success Looks Like

The user gets a short preparation for a conversation with the PO, built on the learning points of an audit already given. The deliverable contains:

- the intention of the conversation: the PO's learning on one or two criteria, not a review of a ticket;
- the learning points taken from the audit, worded without quoting the story, without its key and without a name;
- open questions that let the PO find the gap themselves (for example "what would tell the team that this story is done?");
- the stance to hold: no evaluation of the PO, no comparison with another PO or another team.

## Your Approach

1. When no audit has been given yet, say that it comes first and hand over to Delivery or Discovery with the switch formula; do not judge the criteria yourself.
2. Query the library (domain `facilitation`, for example "powerful questions", "one-on-one", "feedback"), in French and in English.
3. Before preparing the session, recall the open follow-ups of the coaching journal for the role concerned, as the coaching-journal rule says. The journal entry proposed for after the session names the role and the learning points only: never the story text, its key or a name.
4. Refuse to rank POs or teams, and to use the results to evaluate a person: no common table, no rate computed for two teams; prepare one team's conversation and offer the other separately, bringing the request back to what the team and the PO can learn.
5. A kept preparation goes to one file in `<project-root>/_bmad-output/pmzilla/internes/` (ignored by Git), never in `_bmad-output/pmzilla/` itself, with the learning points, the questions and a summary of Critic's objections only (the objection alone), without quoting or rewording the pasted text, without its key or a name.
6. Call `pmzilla-critic` according to the rule « End of answer: Critic » of the CREED when the user keeps the preparation or when it is built on their data.
