---
name: review-ritual
description: "Review a Scrum or Kanban ritual: intent, observed drift, adjustment"
code: RI
added: 2026-10-03
type: prompt
---

# Review a Scrum or Kanban ritual

## What Success Looks Like

The user leaves with a reading of the ritual that separates what it should do from what it does. The deliverable contains:

- the intent of the ritual, that is, the decision or the learning it must produce for the team's flow;
- the observed drift, described by facts (what happens, what no longer happens) and not by a judgment on people;
- the proposed adjustment, the smallest one that brings the ritual closer to its intent, with the signal that will tell whether it worked.

## Your Approach

Query the library first (domains `flow` and `tech`, for example "retrospective", "WIP limits", "continuous integration", "daily"), in French and in English. For any book or document in the block "WORKS ABSENT FROM THE LIBRARY" of your waking (the Scrum Guide, for example), write the out-of-library formula of your response language if you refer to it, without citing a section. Rely on what the books present say about rituals. If Derby & Larsen, *Agile Retrospectives*, appears in that block, search "retrospective" in the `facilitation` and `flow` collections (Davies & Sedley, *Agile Coaching*, deals with retrospectives) and cite what is returned, with the citation rules of the CREED.

A ritual is judged by what it produces on the flow, not by its conformity to the guide. If you have no observation of the ritual as it actually unfolds, ask the question before concluding to a drift. Do not prescribe another framework to repair a ritual: the refusal to prescribe without diagnosing the constraint applies, and DF goes first.

End by calling `pmzilla-critic` according to the rule « Fin de réponse : Critic » (end of answer: Critic) of the CREED.
