---
description: Rewrites a diagnosis for leadership, POs and the team, then has Critic check that the versions say the same thing
argument-hint: "<path to the deliverable or pasted text> [audiences, default: leadership, POs, team]"
---

Adapt this message to several audiences: $ARGUMENTS

This command is written in English, but the user is served in THEIR language: reply in French by default if their request is in French, in English if it is in English. The fixed formulas (posture tag, "hors bibliothèque" / "outside the library", "J'en déduis" or "Hypothèse" / "I infer" or "Hypothesis", Critic's titles, "Ma lecture de cette critique" / "My reading of this critique") and the section titles below are written in the language of the reply, as listed in `tests/postures/vocabulaire.yaml`. Both versions are given where this file mentions one.

If it is a path, read the file (usually a deliverable from `_bmad-output/pmzilla/`). Otherwise, the pasted text is the source. If audiences are named after the source, write only those; otherwise: leadership, POs, team.

## 1. The common ground

Before any version, extract the common ground from the source, in five to ten lines at most:

- **Findings**, each with its strength: *measured* (a figure from the source), *observed* (a case, a testimony), *hypothesis* (to be verified). Copy the figures exactly.
- **Uncertainties and limits** that the source flags.
- **What is asked**: a decision, an arbitration, an action, or simple information.

The common ground is the reference: no version adds a finding to it, removes one in a way that changes the meaning, modifies a figure, or promotes a hypothesis to the rank of finding.

## 2. The intent per audience

If the source does not say what you expect from each audience, ask **a single grouped question**: for each audience, what you expect from them (decide, arbitrate, act, be informed) and the channel (email, message, two-minute talk, meeting material). With no answer, take the defaults below and say so at the top.

## 3. The versions

- **Leadership** (default: short email, decision expected). Eight lines at most. Start with the decision or the request, then the stake (deadlines, risk, cost) and one or two figures at most. Say what remains uncertain. No jargon: "work in progress" rather than WIP, "delivery time" rather than lead time.
- **POs** (default: message, arbitration). What the finding changes for prioritization and commitments. Forecasts as ranges with their probability, never a single date. The possible arbitrations and what each one costs.
- **Team** (default: retro or team meeting material, action). What was observed about the work system, never about people. Hypotheses presented as questions to verify together. What changes for the team, and what is expected of it. If the message concerns a single team, only its data and aggregates for the rest: never a ranking between teams.

Rules for all versions: in the language of the reply (French by default for a request in French), with the domain terms kept in English when the audience knows them; roles, never names; no figure absent from the source; no em dash; each version stands on its own.

## 4. Critic

Pass the common ground and the versions to the `pmzilla-critic` subagent, with this scope: it does not judge the diagnosis itself, only the fidelity of the versions to the common ground and to each other. It checks:

- that the findings, the figures and their strength are the same everywhere;
- that no version hides an uncertainty or a limit that another one gives;
- that each version contains the request that concerns it;
- that no version designates a culprit or evaluates people;
- that the tone does not contradict the substance (a reassuring version of an alarming finding, for example).

Correct the versions on each gap it raises. Call it in the foreground, never in the background, giving it only the request and the deliverable, and do not end your turn before it has answered. The final message is single and follows the restitution rule of `CLAUDE.md`, in this order: (a) the posture's response, with its analysis and key points; (b) a short section `[Posture : Critic]` (French) / `[Posture: Critic]` (English) that summarizes the objections in a few lines; (c) "Ma lecture de cette critique" / "My reading of this critique": what you keep, what you set aside and why. Never a message that announces that Critic is examining the deliverable and that the result will follow. Here (a) is the common ground and the three versions.

**Second pass.** If you corrected anything, send `pmzilla-critic` the common ground and only the corrected passages (before and after), asking it two things: is the gap really resolved, and does the correction create a new one? Do not send it the whole message: this pass stays short. Apply what it raises, with no third pass; if a gap remains, flag it in "Points non corrigés" / "Points not corrected". No second pass if nothing was corrected.

## 5. Delivery

Display the common ground, each version under a title (in French "Pour la direction", "Pour les PO", "Pour l'équipe"; in English "For leadership", "For the POs", "For the team"), then the Critic restitution of step 4: `[Posture : Critic]` / `[Posture: Critic]` (a short summary of the objections), the corrections made, the result of the second pass and the "Points non corrigés" / "Points not corrected", each with its reason, then "Ma lecture de cette critique" / "My reading of this critique". A saved file keeps Critic's complete answer under "Ce que Critic a relevé" / "What Critic raised". Nothing is saved ("Rien n'est enregistré" / "Nothing is saved"), unless the user says "garde ces messages" or "keep these messages": then write the whole in `_bmad-output/pmzilla/messages/AAAA-MM-JJ-<sujet>.md` (a folder ignored by Git: team names may stay there, names of people remain forbidden), creating the folder if needed and never overwriting an existing file (suffix `-2`, `-3`).
