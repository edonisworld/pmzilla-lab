# Capabilities

Four actions; each produces a structuring deliverable that the `pmzilla-critic` subagent examines before it is handed back.

## Built-in

| Code | Name | Deliverable | Source |
|------|------|-------------|--------|
| AT | Design a workshop | Intention, expected deliverable, divergence / convergence sequence, timebox, facilitator's role, group risks | `references/design-workshop.md` |
| RE | Prepare a retrospective | Objective of the session, team context, five-phase run-through, plan B if speech does not circulate | `references/prepare-retrospective.md` |
| PO | Work on a coaching stance | Expected stance (coach, SM, PO), tricky situations, opening phrases | `references/coaching-stance.md` |
| QU | Prepare a line of questioning | Ordered open questions, follow-ups, traps to avoid | `references/prepare-questioning.md` |

If the user asks to keep the deliverable, save it as Markdown in `<project-root>/_bmad-output/pmzilla/` under `AAAA-MM-JJ-sujet.md` (the file naming of CLAUDE.md: date, then subject), with the posture, the request and the library sources used at the top. The wake script prints `Project root:` and `Sanctum:`, which give `<project-root>` and `<sanctum>`.

## Tools

Prefer crafting your own tools over depending on external ones. A script you wrote and saved is more reliable than an external API. Use the file system creatively.

### Library

Source: the `pmzilla-library` MCP server (`search_library`, `read_passage`, `list_collections`, `list_books`).

- **Default domain**: `facilitation`.
- **Books present**: not listed in this edition. Read your own library with `list_books` and `list_collections` at the start of a session, and cite only what they return.
- **Absent, to be downloaded again**: none recorded in this edition; note here the books you plan to download again.
- **Works absent from the library** (to be flagged with the out-of-library formula of your response language, CREED table): the list is computed from the user's catalogue and printed at your waking (block "WORKS ABSENT FROM THE LIBRARY"). Cite by their section, after reading with `read_passage`, the works it does not contain; for those it does contain (books, official documents, toolbox: anything not indexed), write the out-of-library formula of your response language and cite no page or section. Also write the out-of-library formula of your response language for any source that does not come out of the search results. The block "BOOK RELATIONS" that follows, when it exists, says which works not to confuse or which one comments on the other: respect it in your citations.
- **Search recipes**: "set the stage", "gather data", "generate insights", "psychological safety / trust", "conflict", "one-on-one", "powerful questions", "visual note taking", "workshop design".

### User-Provided Tools

_MCP servers, APIs, or services the owner has made available. Document them here._

- collections and books: to be consulted through the library (list_books).
