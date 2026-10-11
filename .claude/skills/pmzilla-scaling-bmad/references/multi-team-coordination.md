---
name: multi-team-coordination
description: Improve multi-team coordination by removing dependencies before adding mechanisms
code: CO
added: 2026-10-03
type: prompt
---

# Improve multi-team coordination

## What Success Looks Like

The user gets a reading of the dependencies between teams and of the coordination mechanisms that suit them. The deliverable contains:

- the dependencies identified (who waits for what from whom, how often, at what waiting cost);
- the coordination mechanisms suited to each one, chosen for the nature of the dependency;
- what to remove rather than add: a dependency to dissolve by changing a boundary, a coordination ceremony that has become useless.

## Your Approach

Query the library first (domains `organisation` and `flow`, for example "dependencies between teams", "coordination entre équipes", "Conway's law", "feature teams vs component teams", "queues"), in French and in English. Rely on what the books present say about coordination, following the CREED's citation rules. For SAFe, the library contains Wilmshurst & Quick, *SAFe® Coaches Handbook* (domains `organisation` and `flow`), an implementation guide by SAFe coaches, not an external assessment of the framework: cite it by its section, and do not make it say what the official SAFe documentation says. If that documentation appears in the "WORKS ABSENT FROM THE LIBRARY" block of your waking output (the block that lists the works absent from the library), write the out-of-library formula of your response language when you draw on it.

Start with the dependency, not the mechanism: without a description of what blocks today, ask. A coordination mechanism added to a dependency that could have been removed is a facade solution. Never recommend SAFe by default; if a scaling framework comes up, compare it to the actual dependency rather than to its catalogue of roles.

End by calling `pmzilla-critic` according to the CREED's rule « Fin de réponse : Critic » (end of answer: Critic).
