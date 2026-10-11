---
name: formulate-hypotheses
description: Formulate testable hypotheses ranked by risk
code: HY
added: 2026-10-03
type: prompt
---

# Formulate testable hypotheses

## What Success Looks Like

The user gets a list of hypotheses the team can test, ranked by type of risk (value, usability, feasibility, viability). Each hypothesis carries its validation criterion: what we would observe if it were true, and what would invalidate it. The list brings out the riskiest hypothesis, the one to test first.

## Your Approach

Query the library first (domain `produit`, for example "formuler une hypothèse testable" / "testable hypothesis", "risque de valeur, d'utilisabilité, de faisabilité, de viabilité" / "value, usability, feasibility, viability risk"), in French and in English. Distinguish what comes from the sources from what comes from your general knowledge; the four-risk classification is to be cited precisely if the library carries it.

A hypothesis that cannot be contradicted is not a hypothesis: reformulate it or flag it as a belief. If the problem is not framed, propose CP before going on. Hypotheses stay at the level of the problem and the need; do not let them slide into solution specifications.

End by calling `pmzilla-critic` according to the rule in CREED (Standing Orders, "End of answer: Critic").
