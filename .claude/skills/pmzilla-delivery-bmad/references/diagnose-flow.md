---
name: diagnose-flow
description: Diagnose a flow or predictability problem before any solution
code: DF
added: 2026-10-03
type: prompt
---

# Diagnose a flow or predictability problem

## What Success Looks Like

The user leaves with a diagnosis a team can confront with its own data. The deliverable contains:

- the probable constraint, formulated as a hypothesis about the flow (where the work waits, why), not as a framework to adopt;
- the data to collect to confirm or rule it out (lead time, flow time, WIP, flow load, flow efficiency, depending on the question), with the probable source of each piece of data;
- the first experiments, small and reversible, that attack the constraint and not its symptoms.

## Your Approach

Query the library first (domains `flow` and `tech`, for example "queues", "WIP limits", "flow time / flow load / flow efficiency", "batch size", "cost of delay"), in French and in English, and anchor the diagnosis in what the sources say, with the citation and source-separation rules of the CREED. Goldratt, *The Goal*, and Anderson, *Kanban*, are in the library (domains `flow` and `organisation`): cite them by their section, after reading them with `read_passage`.

If the situation is not described (which team, which symptom, since when, which data exist), then ask the question before producing a diagnosis or a recommendation: the search comes before the questions, the questions before the diagnosis. When the request supplies the data and asks for a diagnosis, do not delay it: produce it marking your hypotheses and what remains to be verified, pass it to Critic and place your questions at the end of the deliverable; the action recommendations stay conditional there until the context is confirmed. This is where the refusal to prescribe a framework without diagnosing the real constraint applies. When the request arrives disguised as a solution ("we want to move to Kanban", "we need to estimate better"), go back up to the constraint that this solution assumes it will lift, and say so.

End by calling `pmzilla-critic` according to the rule « Fin de réponse : Critic » (end of answer: Critic) of the CREED.
