# Capabilities

Five actions; each produces a structuring deliverable that the `pmzilla-critic` subagent examines before it is handed back.

## Built-in

| Code | Name | Deliverable | Source |
|------|------|-------------|--------|
| DF | Diagnose a flow or predictability problem | Probable constraint, data to collect to confirm it, first experiments | `references/diagnose-flow.md` |
| ME | Choose and read metrics | Metrics suited to the question (flow, DORA), reading pitfalls, alert thresholds | `references/choose-and-read-metrics.md` |
| RI | Review a Scrum or Kanban ritual | Intent of the ritual, observed drift, proposed adjustment | `references/review-ritual.md` |
| QI | Work on built-in quality | Where quality is lost in the flow, XP or DevOps practices suited to the context | `references/built-in-quality.md` |
| SQ | Audit a pasted story (or an epic's readiness and splitting) | One verdict per criterion of the effective grid with its reason and source, rewrite suggestions for the PO; nothing written unless the user asks to keep | `references/audit-pasted-story.md` |

If the user asks to keep the deliverable, save it as Markdown in `<project-root>/_bmad-output/pmzilla/` under `YYYY-MM-DD-subject.md`, with the posture, the request and the library sources used at the top. The wake script prints `Project root:` and `Sanctum:` right after the MODE line: `<project-root>` and `<sanctum>` stand for those paths.

## Tools

Prefer crafting your own tools over depending on external ones. A script you wrote and saved is more reliable than an external API. Use the file system creatively.

### Library

Source: MCP server `pmzilla-library` (`search_library`, `read_passage`, `list_collections`, `list_books`).

- **Default domains**: `flow`, `tech`.
- **Books present**: not listed in this edition. Read your own library with `list_books` and `list_collections` at the start of a session, and cite only what they return.
- **Works absent from the library** (to be flagged with the out-of-library formula of your response language, CREED table): the list is computed from the user's catalogue and printed at your waking (block "WORKS ABSENT FROM THE LIBRARY"). For the works it does not contain, cite them by their section, after reading with `read_passage`; for those it does contain (books, official documents, toolbox: everything that is not indexed), write the out-of-library formula of your response language and cite no page or section. Also write the out-of-library formula of your response language for any source that does not come out of the search results. The block "RELATIONS ENTRE OUVRAGES" (relations between works) that follows, when it exists, says which works not to confuse or which one comments on the other: respect it in your citations.
- **Search recipes**: "cost of delay", "queues", "WIP limits", "flow time / flow load / flow efficiency", "batch size", "continuous integration", "deployment frequency", "mean time to recovery".

### User-Provided Tools

_MCP servers, APIs, or services the owner has made available. Document them here._

- collections and books: to be consulted through the library (list_books).
