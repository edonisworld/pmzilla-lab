---
description: Weekly digest of the watch (veille), by theme and by posture, checked against the books and Critic
argument-hint: "[number of days, 7 by default]"
---

This command is written in English, but the user is served in their own language: answer and write the digest in the language of the user's request (French by default when the request is in French). Fixed formulas are written in the language of the response, in the form given in `tests/postures/vocabulaire.yaml`. Each is given here in both languages (fr / en):

- posture tag: `[Posture : X]` / `[Posture: X]`
- missing from the library: "hors bibliothèque" / "outside the library"
- inference: "J'en déduis" or "Hypothèse" / "I infer" or "Hypothesis"
- analogy: "transposition par analogie, non portée par l'auteur" / "transposition by analogy, not made by the author"
- Critic section title: "Ce que Critic conteste" / "What Critic challenges"
- reading of the critique: "Ma lecture de cette critique" / "My reading of this critique"

Produce the weekly digest of the PMZilla Lab watch. Period: the last $ARGUMENTS days (7 if nothing is given).

## 1. Prepare the inventory

Run `uv run ~/PMZilla-Lab/watch_triage.py week --days <period>`, then read `Watch-Lab/_semaine.md`. It is the list of articles kept by the pre-sort, with title, source, link, date and summary. Do not read the files in `Watch-Lab/watch/` or `Watch-Lab/own-articles/`: for detail, go through the library.

## 2. Identify the themes

Group the articles into **at most 3 to 5 themes**, those that come back across several authors. Attach each theme to a posture following the routing in `CLAUDE.md` (Discovery, Delivery, Scaling or Facilitation) and announce it with the posture tag (`[Posture : Discovery]` in French, `[Posture: Discovery]` in English). An isolated article with no echo among other authors goes under "Signaux faibles" / "Weak signals", after being read: a weak signal that has not been re-read does not appear in the digest, or it is read first (`search_library` then `read_passage`). The inventory summary is not enough.

## 3. For each theme

1. **Read**: `search_library` with `collections ["watch"]` and `since` equal to the start date of the period (older articles do not belong in the digest), then `read_passage` on the central passages. Two or three readings per theme are enough.
2. **What the authors say**: the ideas, with author, title, date and link for each. State what each idea rests on: data (which), a concrete case, or opinion. Summarize, do not copy: at most one short quotation per theme.
3. **Convergence or echo, and divergences**: authors who cite each other, or who take up the same source or the same newsletter, do not form a convergence; it is an echo: say so. Speak of convergence only for independent authors who reach the same finding by different paths, and say whether it rests on data or only on matching opinions. Write neither "independent" nor "convergence" without proof of independence: distinct authors, journals and circles. Two authors of the same publication, the same family of talks or the same circle are not independent by default. Without that proof, write "same finding, same publication conditions, no measurement" (fr: « même constat, mêmes conditions de publication, aucune mesure »). Then the disagreements between authors, if any.
4. **What the library says**: `search_library` on the domains of the posture. Cite the book and the section. If an article contradicts a book, say so without settling it. A transposition by analogy between a watch author and a book in the library (a framework designed for another subject) is announced as such: "transposition by analogy, not made by the author" (fr: « transposition par analogie, non portée par l'auteur »). If the library does not cover the subject, write "outside the library" (fr: « hors bibliothèque »).
5. **User's positions**: `search_library` with `collections ["own-articles"]`. Before writing that an article by the user agrees with or contradicts an author, read it in full (`read_passage` with `before` and `after` until the whole article is covered). Their articles are short; full reading is the rule. Flag the reuse or the contradiction with title, date and link, and state what their position rests on (data, case, opinion). Do not systematically place their positions on the side of the authors who agree with them: also look for the article of the week that tests them the most.
6. **Questions to ask yourself**: two or three concrete questions for an Agile Lead who supports a product transformation.

Always distinguish what the sources say from what you infer from them: an inference starts with "I infer" or "Hypothesis" (fr: « J'en déduis » or « Hypothèse »). A statement of absence is limited to what you have read: "no article kept over the period contradicts it", never "no article contradicts it".

## 4. Critic

Pass the complete digest to the `pmzilla-critic` sub-agent, specifying its scope: this is a general watch digest, not a recommendation. It deliberately applies to no specific team or organization (it is versioned on GitHub and deposited in another tool); application to a context happens afterwards, in a session with a posture. Critic therefore judges the solidity of the findings, the use of sources, the distinction between convergence and echo, and the treatment of the user's positions. Call it in the **foreground**, never in the background, giving it only the digest and the initial request, and do not end your turn before it has answered. The file keeps its complete answer in the section "What Critic challenges" (fr: « Ce que Critic conteste »), followed by the section "My reading of this critique" (fr: « Ma lecture de cette critique »): what you keep, what you set aside and why. Correct the digest only if Critic points out a factual error or a badly cited source. Write no provisional marker in the file: the two sections are added once its answer is received.

## 5. Format

File: `_bmad-output/pmzilla/veille/synthese-AAAA-MM-JJ.md` (today's date; create the folder if needed; if the file already exists, add `-2`, `-3`, never overwrite). Check the word count before passing it to Critic. This file will also be deposited in the PMZilla v1 project of Claude Desktop: it must stand on its own.

Template. Section titles follow the language of the digest (fr / en):

```
# Synthèse de veille, du <date de début> au <date de fin>   /   Watch digest, <start date> to <end date>

<two sentences: what dominated the week. Opening rule below.>

## <Theme 1> [Posture : …]   /   [Posture: …]
### Ce que disent les auteurs   /   What the authors say
### Où ils divergent   /   Where they diverge
### Ce que dit la bibliothèque   /   What the library says
### Positions de l'utilisateur   /   User's positions   (only if there is a reuse or a contradiction)
### Questions à se poser   /   Questions to ask yourself

## <Theme 2> …

## À lire en priorité   /   To read first
<3 articles at most: title, author or site, date, link, one sentence on why>

## Signaux faibles   /   Weak signals
<isolated articles, read, worth attention: title, author or site, date, link, one sentence>

## Ce que Critic conteste   /   What Critic challenges
<complete answer of pmzilla-critic>

## Ma lecture de cette critique   /   My reading of this critique
<what you keep, what you set aside and why>

## Sources   (always the last section)
<one article per line: author or site, "Title" as in the inventory, YYYY-MM-DD, link>
```

**Mandatory opening.** The two-sentence introduction at the top of the file, the first sentence under each theme heading, and each "What the authors say" subsection open either with the first short reference, named and dated, in the form `Author or site (YYYY-MM-DD): …`, or with "I infer" / "Hypothesis". Never open with a general summary of the watch, a transition sentence or a generality. Compliant openings:

- fr: « Auteur ou site (AAAA-MM-JJ) : montre, sur des données de flux d'une équipe, que… » or « J'en déduis que les trois articles de la semaine reposent sur le même cas. »
- en: "Author or site (YYYY-MM-DD): shows, on one team's flow data, that…" or "I infer that the three articles of the week rest on the same case."

Citation rules (aligned with the "Veille" rule of `CLAUDE.md`):

- Every paragraph that states something relying on a source contains at least one complete short reference. For an article: author or site, and YYYY-MM-DD copied from the "Sources" line. For a book: *Author, Title*, section. A reference always names the author or the site, even when just cited: never "his demonstration", "from the same site" or "the author" alone. A reference without a date is incomplete.
- Every paragraph that states something without a source starts with "I infer" or "Hypothesis". A transition sentence or a question does not need one (this covers the "Questions to ask yourself" subsection). A bullet counts as a paragraph.
- A paragraph or bullet that summarizes or compares several articles names each one with its date, or starts with "I infer".
- The author of an article is the one in the `author` field, with no co-author added; when none is given, cite the site as the library returns it, without inventing a name. An article whose link cannot be found is not cited.
- The "Sources" section is always the last of the file: the books cited appear in the text or in a section placed before "Sources", the open question, if there is one, comes just before it, and nothing follows it. It contains only the list of articles, no book and no subsection. In "Sources", the title is the one of the article as in the watch inventory, never reworded.

Writing rules:
- In the language of the user, French by default. Keep the trade terms in English (discovery, delivery, outcome, product trio, flow metrics…).
- No em dash: use colons, parentheses or separate sentences.
- 1,200 words at most, links not included.
- Never copy article text beyond a short quotation: summaries and links only.
- No information internal to a company, no colleague's name.

## 6. Review before saving (mandatory step)

Before saving, re-read the digest paragraph by paragraph, conclusion included, and correct before writing the file:

1. Every paragraph or bullet that relies on one or more articles contains at least one complete short reference (author or site, YYYY-MM-DD copied from the "Sources" line; for a book, *Author, Title*, section). A reference without a date is incomplete, and a reference always names the author or the site, never "the author" alone.
2. Every paragraph or bullet without a source starts with "I infer" or "Hypothesis" (a transition sentence or a question is exempt).
3. Every paragraph or bullet that summarizes or compares several articles names each one with its date, or starts with "I infer".
4. The mandatory opening is respected: the introduction, each theme and each "What the authors say" subsection open with a named and dated reference or with "I infer" / "Hypothesis", never with a general summary, a transition sentence or a generality.
5. Every author or site cited in the text, quotations included, has its line in "Sources", and conversely. The title in "Sources" is the one of the inventory, never reworded; an article with no link is not cited.
6. "Sources" is the last section, contains only the article list, and the open question, if there is one, comes just before it.

## 7. End

Save nothing in Git. The final message is **single** and follows the restitution rule of `CLAUDE.md`, in this order:

1. **The digest**: the path of the file, then the digest in three lines and its key points. These lines follow the same rule as the digest: each one opens with a named and dated short reference (author or site, YYYY-MM-DD, copied from the Sources line) or with « J'en déduis » / « Hypothèse » ("I infer" / "Hypothesis"); none states anything from an article without one of the two.
2. **`[Posture : Critic]`** (fr) / **`[Posture: Critic]`** (en): a short section that summarizes Critic's objections in a few lines. The complete answer stays in the file.
3. **"Ma lecture de cette critique"** (fr) / **"My reading of this critique"** (en): what you keep, what you set aside and why.
4. **"Sources"**, always last: one line per article cited in the message, in the same format as the file's. Never a message that announces that Critic is examining the digest and that the result will follow.
