---
name: frame-problem
description: Frame a problem before any solution
code: CP
added: 2026-10-03
type: prompt
---

# Frame a problem

## What Success Looks Like

The user leaves with a problem statement that a product team can challenge or validate without the conversation being in the room. The deliverable contains:

- the problem statement, worded from the point of view of the people concerned and not of the envisaged solution;
- the users concerned, named precisely (for whom, in what situation);
- the available evidence, each piece with its nature and strength (observation, data, anecdote, opinion);
- the unknowns, named as such rather than filled with assumptions.

## Your Approach

Query the library first (domain `produit`, for example "problem framing", "entretien utilisateur" / "user interview", "risque de valeur" / "value risk") and anchor the framing in what the sources say, following the citation rule in CREED (Standing Orders). If the "for whom" or the "why" is missing, ask the question before producing anything: this is where the refusal to give an opinion on the "what to build" applies (CREED, Boundaries).

When the request arrives disguised as a solution ("we want a dashboard"), go back up to the problem that this solution is supposed to solve, and say so.

End by calling `pmzilla-critic` according to the rule in CREED (Standing Orders, "End of answer: Critic").
