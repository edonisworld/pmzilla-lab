---
description: Roundtable of authors, several authors from the library defend their position on a question, then confront each other, with quotations
argument-hint: "<question> [| authors to invite, separated by commas]"
---

This command is written in English, but the user is served in THEIR language: answer in French by default when the request is in French, in English when it is in English. The fixed formulas are written in the language of the answer, as in `tests/postures/vocabulaire.yaml`: posture tag (`[Posture : X]` in French, `[Posture: X]` in English), "hors bibliothèque" / "outside the library", "J'en déduis" / "I infer", "Hypothèse" / "Hypothesis", the Critic section title "Ce que Critic conteste" / "What Critic challenges", "Ma lecture de cette critique" / "My reading of this critique". A French request keeps producing a French answer with the French formulas. Literal quotations from the library stay in their original language.

Organize a roundtable of the library's authors on: $ARGUMENTS

If a bar `|` separates the question from a list of authors, invite those; otherwise, choose them. This is not the roundtable of postures (`/bmad-party-mode`): here, the **books** speak, and only them.

**Absolute rule**: an author says only what their read passages say. No imagined first-person dialogue, no position attributed from what is known of the author outside the library. Positions are written in the third person ("Reinertsen argues that..."). When the library contains nothing from an author on the question, they do not take part.

## 1. Choose the guests

1. Run `search_library` on the question, across all book collections (not the watch), with two or three different formulations, including one that looks for the opposite position.
2. Select **three to five authors** whose passages really address the question, looking for **different** positions: a roundtable where everyone agrees teaches nothing. If there is no real disagreement in the library, say so and present the nuances instead.
3. Announce the table: each author, their book, and in one line why they are invited. One watch article may sit at the end of the table (one at most), presented as a contemporary voice that does not carry the weight of a book.

## 2. The positions

For each author, read the central passages (`read_passage`, with `before` and `after` if the passage is cut off), then write:

- **Their thesis**, in one sentence;
- **Their argument**, in two or three lines: what it rests on (mechanism, data, experience);
- **Their conditions**: in which context they defend it, and the limits they set themselves;
- **A short quotation**, in the original language, with *Author, Title*, section.

## 3. The confrontation

Take the two or three sharpest disagreements. For each:

1. What A's position opposes to B's, relying on what A writes (a quotation if possible). If the reply is a transposition and not a passage where A answers this idea, write "J'en déduis" / "I infer" or "Hypothèse" / "Hypothesis".
2. **Real disagreement or different contexts?** Many apparent oppositions come from different objects: size of the organization, type of work (discovery or delivery), time horizon, what is meant by "estimating" or "product". Say which of the two it is, and on what you base it.
3. **What would settle it**: the data, observation or context that would prove one or the other right.

Then **the points of agreement** (often more instructive than the disagreements) and **what the library does not say** on the question, marked "hors bibliothèque" / "outside the library".

## 4. Putting it to use

- **Workshop**: three discussion questions that make people choose between the positions in a real context, and a way to stage the debate (one position per group, for example).
- **Article**: the strongest angle, in one sentence, and the objection that will have to be addressed.

## 5. Critic

Pass the roundtable to the `pmzilla-critic` subagent. It checks that each position and each quotation is carried by the passages read (section included, with no invented chapter), that no author says what their book does not say, that the disagreements are neither fabricated nor smoothed over, and that the table is not unbalanced (one position caricatured against another developed). Correct the factual or attribution errors it raises, then restitute as follows. Call it in the foreground, never in the background, giving it only the request and the deliverable, and do not end your turn before it has answered. The final message is single and follows the restitution rule of `CLAUDE.md`, in this order: (a) the posture's response, with its analysis and key points; (b) a short section `[Posture : Critic]` (French) / `[Posture: Critic]` (English) that summarizes the objections in a few lines; (c) "Ma lecture de cette critique" / "My reading of this critique": what you keep, what you set aside and why. Never a message that announces that Critic is examining the deliverable and that the result will follow. A saved roundtable keeps Critic's complete answer in its file, in a section "Ce que Critic conteste" / "What Critic challenges" (the title in the language of the answer).

## Format and saving

In the language of the user's request (French by default when it is in French), domain terms in English, quotations in the original language; no em dash; 1,200 words at most, quotations included. Nothing is saved, unless the user says "garde cette table ronde" / "keep this roundtable": write it then to `_bmad-output/pmzilla/table-ronde/AAAA-MM-JJ-<sujet>.md` (folder created if needed, never overwriting: suffix `-2`, `-3`).
