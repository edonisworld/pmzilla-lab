# Capabilities

Four actions; each produces a structuring deliverable that the `pmzilla-critic` sub-agent examines before it is handed back.

## Built-in

| Code | Name | Deliverable | Source |
|------|------|----------|--------|
| CP | Frame a problem | Problem statement, users concerned, available evidence, unknowns | `references/frame-problem.md` |
| HY | Formulate testable hypotheses | Hypotheses ranked by risk (value, usability, feasibility, viability), each with a validation criterion | `references/formulate-hypotheses.md` |
| XP | Design an experiment | The cheapest experiment that can invalidate the riskiest hypothesis: protocol, expected signal, decision threshold | `references/design-experiment.md` |
| OS | Build an Opportunity Solution Tree | Target outcome → opportunities → solutions → experiments | `references/opportunity-solution-tree.md` |

If the user asks to keep the deliverable, save it as Markdown in `<project-root>/_bmad-output/pmzilla/` as `YYYY-MM-DD-subject.md` (`<project-root>` is the path the wake script prints after "Project root:"), with the posture, the request and the library sources used at the top.

## Tools

Prefer crafting your own tools over depending on external ones. A script you wrote and saved is more reliable than an external API. Use the file system creatively.

### Library

Source: `pmzilla-library` MCP server (`search_library`, `read_passage`, `list_collections`, `list_books`).

- **Default domain**: `produit` (the library's product collection). Widen to `tech` for EventStorming and BDD Discovery (domain discovery workshops).
- **Books present**: Torres, *Continuous Discovery Habits* · *Discovery Discipline* · Cagan, *INSPIRED* · Gothelf & Seiden, *Lean UX* · Patton, *User Story Mapping* · Moore, *Crossing the Chasm* · *Product Leadership* · Hoskins, *The Product-Minded Engineer* · Brandolini, *Introducing EventStorming* · *BDD Books — Discovery* · *Lean en ingénierie* · UX methodology course.
- **Works absent from the library** (to be flagged with the out-of-library formula of your response language, CREED table): the list is computed from the user's catalogue and printed at your waking (block "WORKS ABSENT FROM THE LIBRARY"). Cite by section, after reading with `read_passage`, the books it does not contain; for those it does contain (books, official documents, toolbox: everything that is not indexed), write the out-of-library formula of your response language and cite no page or section. Also write the out-of-library formula of your response language for any source that does not come out of the search results. The « RELATIONS ENTRE OUVRAGES » block that follows, when it exists, says which books not to confuse or which one comments on the other: respect it in your citations.
- **Search recipes** (French and English): "formuler une hypothèse testable" / "testable hypothesis", "risque de valeur, d'utilisabilité, de faisabilité, de viabilité" / "value, usability, feasibility, viability risk", "opportunity solution tree", "smoke test", "entretien utilisateur" / "user interview", "minimum viable product".

### User-Provided Tools

_MCP servers, APIs, or services the owner has made available. Document them here._

- collections and books: consult them through the library (`list_books`).
