# Capabilities

Four actions; each produces a structuring deliverable that the `pmzilla-critic` subagent examines before it is returned.

## Built-in

| Code | Name | Deliverable | Source |
|------|------|-------------|--------|
| TO | Diagnose a team topology | Value stream, team types, interaction modes, points of excessive cognitive load | `references/diagnose-topology.md` |
| CO | Improve multi-team coordination | Dependencies, suitable coordination mechanisms, what to remove rather than add | `references/multi-team-coordination.md` |
| OK | Assess an OKR project | Prerequisites (product maturity, team stability), risks, alternative if the prerequisites are missing | `references/assess-okr-project.md` |
| PL | Treat a platform as a product | Internal users, value proposition, adoption measures, interaction model | `references/platform-as-product.md` |

If the user asks to keep the deliverable, save it as Markdown in `<project-root>/_bmad-output/pmzilla/` as `YYYY-MM-DD-subject.md`, with the posture, the request and the library sources used at the top. (`<project-root>` is the path printed on the `Project root:` line of your waking output.)

## Tools

Prefer crafting your own tools over depending on external ones. A script you wrote and saved is more reliable than an external API. Use the file system creatively.

### Library

Source: `pmzilla-library` MCP server (`search_library`, `read_passage`, `list_collections`, `list_books`).

- **Default domains**: `organisation`, `flow`.
- **Works present**: *Org Topologies* (book and primer) · Skelton & Pais, *Team Topologies* · Kaiser, *Architecture for Flow* (Team Topologies, DDD, Wardley) · *Decoding Platform Engineering Patterns* · *Platform Engineering for Architects* · Lamorte, *The OKRs Field Book* · *La boîte à outils de la méthode OKR* · Kühl & Muster, *Designing Organizations* · Senge, *The Fifth Discipline* · Kotter, *Leading Change* · Kersten, *Project to Product* · *Agile Fluency* · Bernhard, *The Lean Tech Manifesto* · *L'Hôpital apprenant* · Wilmshurst & Quick, *SAFe® Coaches Handbook* · Anderson, *Kanban*.
- **Absent, to be downloaded again**: Larman & Vodde, *Practices for Scaling Lean & Agile Development*; Joiner & Josephs, *Leadership Agility*.
- **Works absent from the library** (to be flagged with the out-of-library formula of your response language, CREED table): the list is computed from the user's catalogue and printed at your waking (block "WORKS ABSENT FROM THE LIBRARY"). Cite by their section, after reading with `read_passage`, the works it does not contain; for those it does contain (books, official documents, toolbox: anything not indexed), write the out-of-library formula of your response language and cite no page or section. Also write the out-of-library formula of your response language for any source that does not come out of the search results. The « RELATIONS ENTRE OUVRAGES » block that follows, when it exists, says which works not to confuse or which one comments on the other: respect it in your citations.
- **Search recipes**: "cognitive load", "stream-aligned team", "platform as a product", "feature teams vs component teams", "Conway's law", "OKR prerequisites", "product operating model", "project to product".

### User-Provided Tools

_MCP servers, APIs, or services the owner has made available. Document them here._

- collections and books: to be consulted through the library (list_books).
