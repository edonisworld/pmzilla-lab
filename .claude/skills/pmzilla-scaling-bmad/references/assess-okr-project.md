---
name: assess-okr-project
description: "Assess an OKR project: prerequisites, risks and an alternative if the prerequisites are missing"
code: OK
added: 2026-10-03
type: prompt
---

# Assess an OKR project

## What Success Looks Like

The user gets a judgement on the viability of an OKR project before its launch or at its review. The deliverable contains:

- the prerequisites examined: product maturity and team stability, with what establishes or refutes them;
- the risks specific to the context (OKRs turned into a list of deliveries, into a control tool, or aligned on an org chart rather than on value streams);
- the alternative to consider if the prerequisites are missing, more modest but sustainable.

## Your Approach

Query the library first (domains `organisation` and `flow`, for example "OKR prerequisites", "product operating model", "project to product", "cognitive load"), in French and in English. Lamorte, *The OKRs Field Book*, and *La boîte à outils de la méthode OKR* are present. Doerr, *Measure What Matters*, and Wodtke, *Radical Focus*, are also in the library (domains `organisation` and `produit`): cite them by their section, after reading them with `read_passage`. Apply the CREED's citation rules.

Question product maturity and team stability before assessing anything else: the refusal to propose OKRs without questioning them upstream applies. If those two elements are not known, ask and do not conclude. An OKR project on teams that are still moving is first handled by TO.

End by calling `pmzilla-critic` according to the CREED's rule « Fin de réponse : Critic » (end of answer: Critic).
