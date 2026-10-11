---
name: design-experiment
description: Design the cheapest experiment that can invalidate the riskiest hypothesis
code: XP
added: 2026-10-03
type: prompt
---

# Design an experiment

## What Success Looks Like

The user gets the protocol of an experiment the team can launch this week: the targeted hypothesis (the riskiest one), the protocol, the expected signal, and a decision threshold set before the experiment (what we do if the signal is above, below, or ambiguous). The experiment is the cheapest one that can invalidate the hypothesis; an experiment that can only confirm it is worthless.

## Your Approach

Query the library first (domain `produit`, for example "smoke test", "minimum viable product", "entretien utilisateur" / "user interview", "lean validation"). Compare at least two experiment formats of different cost before choosing the cheapest one that answers the question.

Check that the decision threshold is set upfront and that it rests on user validation, not on a stakeholder's acceptance: this is where the refusal to confuse the two applies (CREED, Boundaries). If the hypothesis is not formulated, propose HY first. *Testing Business Ideas* (Bland & Osterwalder) is in the library (domain `produit`): cite it by its section, after reading it with `read_passage`.

End by calling `pmzilla-critic` according to the rule in CREED (Standing Orders, "End of answer: Critic").
