# Context note template

A context note is a short, dated, distilled statement of the situation of your organisation. It lives in the notes folder of the context folder (outside every repository), is written with `/context add` or `uv run tools/context_lab.py add`, and is indexed by the daily run into the private collection of the library. This page holds invented examples only: a generic product, roles and generic designations, never a person, a team or a project of a real organisation.

## Rules of the header

Every note starts with a YAML header. Keys are in English, values in the language of the note.

| Key | Meaning |
|---|---|
| `title` | A short title. |
| `date` | The date of the note, `YYYY-MM-DD`. The file is named `YYYY-MM-DD-<slug>.md`. |
| `nature` | `declarative` for what someone said or wrote (an interview, a meeting, an organisation chart); `measured` for figures read in a flow report or an aggregated view (name the report or view as the source, and write a cell under five as `masqué`, or `masked` in an English note). |
| `source` | Where the content comes from, by role or document type. |
| `review` | The date from which the note must be reread, later than `date`. A note past its review date is flagged as possibly out of date. |
| `kind` | `map`, for the context map only. At most one map, named `carte-contexte.md`. |

The tool refuses a note with a missing or invalid header field, a personal identifier, a name listed in the sensitive-names list, or a distinctive team name of the team-names extract (minus the generic-names list); the refusal gives the line number, never the name. The daily indexing applies the same check to every note on every run, unchanged notes included: a refused note is not indexed and its former indexed version is removed. Without the sensitive-names list, no note is indexed or removed. The wake prints the map only after the same check, otherwise `context map not shown:` and the reason. Nothing here is inferred from the file name or the body.

## Example of a note

```markdown
---
title: Decision forums of the product line
date: 2026-09-01
nature: declarative
source: interview with a product leadership role
review: 2026-12-01
---

## Forums

A monthly forum of the product leadership roles decides the order of the major initiatives. The platform team receives requests from three product teams through a shared board, reviewed every two weeks by a coordination role.

## What is not known

How a request is declined when two product teams ask for the same platform capacity.
```

## The context map

The map is the note every posture reads when it wakes: its header and its first 80 lines. It holds these sections, in roles and generic designations:

1. product scope;
2. roles and their decision rights;
3. decision forums and their rhythm;
4. teams and their flows (team A, the platform team);
5. dependencies;
6. what is not known.

```markdown
---
title: Context map
date: 2026-09-01
nature: declarative
source: organisation chart and interviews with two coordination roles
review: 2026-12-01
kind: map
---

## Product scope

One product line, three product teams and one platform team.

## Roles and their decision rights

The product leadership role orders initiatives; each product manager role orders the backlog of its team.

## Decision forums and their rhythm

A monthly portfolio forum; a fortnightly coordination forum between the platform team and the product teams.

## Teams and their flows

Team A and team B share one release train; the platform team works in a continuous flow.

## Dependencies

Teams A and B depend on the platform team for authentication and for the shared data store.

## What is not known

The capacity of the platform team beyond the current quarter.
```
