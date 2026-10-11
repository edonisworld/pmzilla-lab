---
name: choose-and-read-metrics
description: Choose and read flow or DORA metrics suited to the question asked
code: ME
added: 2026-10-03
type: prompt
---

# Choose and read metrics

## What Success Looks Like

The user gets the metrics suited to the question the team is asking, not a generic dashboard. The deliverable contains:

- the metrics retained (flow, DORA), each tied to the question it answers;
- the reading pitfalls specific to each (average versus distribution, measurement on a sample that is too small, an indicator turned into a target);
- the alert thresholds, and what would be done when they are crossed;
- the date of each value read, so that its age can be judged later.

## Your Approach

Query the library first (domains `flow` and `tech`, for example "flow time / flow load / flow efficiency", "deployment frequency", "mean time to recovery", "continuous integration"). Forsgren, Humble & Kim, *Accelerate*, is the reference for the DORA metrics and is in the library (domains `flow`, `organisation` and `tech`): read the passage with `read_passage` before relying on it. For the citation: cite the section returned by the index (the index of *Accelerate* gives the chapter or the appendix, for example "Chapter 4 - Technical Practices" or "Appendix A: Capabilities to Drive Improvement"); if a passage has none, the chapter read in the text, otherwise the passage alone, never a section or a page you have not read. Other books take up the DORA metrics (for example *The Platform Engineering Playbook*): cite the source you actually read. Complete with what the books present say about flow and delivery, with the citation rules of the CREED.

Start from the question, not from the metric: if the question is not clear, ask it first. Lead time before velocity, mean time to recovery before zero incidents: velocity is never retained as a performance indicator, and you say so when the request leads there.

End by calling `pmzilla-critic` according to the rule « Fin de réponse : Critic » (end of answer: Critic) of the CREED.
