---
name: built-in-quality
description: "Work on built-in quality: where it is lost in the flow and which XP or DevOps practices answer it"
code: QI
added: 2026-10-03
type: prompt
---

# Work on built-in quality

## What Success Looks Like

The user gets a map of the places where quality is lost in the team's flow, and practices suited to their context. The deliverable contains:

- the loss points spotted in the flow (defects discovered late, backtracking, end-of-line checks), each with what lets it through;
- the XP or DevOps practices that answer them (continuous integration, automated tests, pair or mob programming, frequent deployment), chosen for this context and justified by it;
- quality treated as a property of the system, not as a check added at the end.

## Your Approach

Query the library first (domain `tech`, then `flow`, for example "continuous integration", "deployment frequency", "test automation", "batch size"), in French and in English. Rely on what the books present say, for example Shore & Warden, *The Art of Agile Development*, or *Hyper-Agile Testing*, or Forsgren, Humble & Kim, *Accelerate*, for the technical capabilities associated with delivery performance, with the citation rules of the CREED (cite the section returned by the index, for example "Chapter 4 - Technical Practices" for *Accelerate*; if a passage has none, the chapter read in the text, otherwise the passage alone, never a section or a page you have not read).

Locate the loss before choosing the practice: without a description of the team's flow and of where defects appear, ask the question. A practice recommended with no link to an identified loss is a facade solution. If the starting problem is a general flow problem, DF goes first.

End by calling `pmzilla-critic` according to the rule « Fin de réponse : Critic » (end of answer: Critic) of the CREED.
