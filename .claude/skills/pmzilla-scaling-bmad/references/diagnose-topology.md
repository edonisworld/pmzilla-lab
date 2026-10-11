---
name: diagnose-topology
description: Diagnose a team topology from value streams and cognitive load
code: TO
added: 2026-10-03
type: prompt
---

# Diagnose a team topology

## What Success Looks Like

The user leaves with a reading of the topology that they can put in front of the teams concerned. The deliverable contains:

- the starting value stream, that is, what the organisation delivers, to whom, and by which path;
- the team types present (stream-aligned, platform, enabling, complicated-subsystem) and what remains undetermined;
- the interaction modes between teams (collaboration, X-as-a-Service, facilitation) as they are practised, not as they are drawn;
- the points of excessive cognitive load, with what produces them.

## Your Approach

Query the library first (domains `organisation` and `flow`, for example "cognitive load", "stream-aligned team", "Conway's law", "feature teams vs component teams", "product operating model"), in French and in English, and anchor the diagnosis in what the sources say, following the CREED's rules on citation and separation of sources. Skelton & Pais, *Team Topologies*, is in the library: read the passage with `read_passage` and cite it by its section. Kaiser, *Architecture for Flow*, is a commentary on it: do not attribute to it what *Team Topologies* says, nor the reverse.

If the value stream is not described, ask before drawing anything: the reasoning "value stream before org chart" applies. Treat an org design as a problem of flow and cognitive load, never as an HR problem, and say so when the request slides that way.

End by calling `pmzilla-critic` according to the CREED's rule « Fin de réponse : Critic » (end of answer: Critic).
