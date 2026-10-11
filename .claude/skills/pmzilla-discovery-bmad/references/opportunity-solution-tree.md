---
name: opportunity-solution-tree
description: Build an Opportunity Solution Tree from the target outcome down to the experiments
code: OS
added: 2026-10-03
type: prompt
---

# Build an Opportunity Solution Tree

## What Success Looks Like

The user gets a tree that reads from top to bottom: target outcome, opportunities (user needs, pain points, desires), candidate solutions for each opportunity, experiments to test the solutions' hypotheses. They can see at a glance which branches are backed by evidence, which are assumptions, and where to explore before choosing.

## Your Approach

Query the library first (domain `produit`, for example "opportunity solution tree", "continuous discovery", "outcome"). Torres, *Continuous Discovery Habits*, is the reference for the OST and is in the library (domain `produit`): read the passage with `read_passage` before relying on it. For the citation: cite the section returned by the index (the index of *Continuous Discovery Habits* gives the chapter, for example "Chapter Two: A Common Framework for Continuous Discovery"); if a passage has none, the chapter read in the text, otherwise the passage alone, never a section or a page you have not read. Complete with what the other books present say about outcomes, opportunities and continuous discovery, following the citation rule in CREED (Standing Orders).

The target outcome must be a product or customer outcome, not a delivery. Keep the opportunities worded from the user's point of view and several solutions per priority opportunity: a tree with a single solution per branch is a plan in disguise. If the outcome or the users are unclear, propose CP first.

Present the tree as indented text. End by calling `pmzilla-critic` according to the rule in CREED (Standing Orders, "End of answer: Critic").
