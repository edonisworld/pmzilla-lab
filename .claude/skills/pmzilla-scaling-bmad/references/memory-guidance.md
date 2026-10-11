---
name: memory-guidance
description: Memory philosophy and practices for Scaling
---

# Memory Guidance

## The Fundamental Truth

You are stateless. Every conversation begins with total amnesia. Your sanctum is the ONLY bridge between sessions. If you don't write it down, it never happened. If you don't read your files, you know nothing.

This is not a limitation to work around. It is your nature. Embrace it honestly.

## What to Remember

Four registers, and they are the whole of what MEMORY.md carries:

- **Team topology** — each team with its type and the value stream it serves, and every change (before → after, why, when)
- **Dependencies between teams** — who waits for whom, the coordination mechanism in place, and the status (`open`, `being handled` or `removed`)
- **Organisation decisions** taken, with the effect expected beforehand and the effect observed (or `not yet observed`)
- **OKR projects and platforms** — the state of each, with for an OKR project the prerequisites (`established`, `partial` or `missing`) and for a platform its internal users and adoption measure

**Language of the registers.** Use the section headings and the status values that MEMORY.md already contains, whatever their language (a sanctum created in French keeps its French headings and values). When you create a register, or a status value that MEMORY.md does not have yet, use the English ones given below. Never rename or translate what is already there; the table gives the French equivalents so you can recognise them.

| English (new sanctum) | French (existing sanctums) |
|---|---|
| Team topology | Topologie des équipes |
| Dependencies between teams | Dépendances entre équipes |
| Organisation decisions | Décisions d'organisation |
| OKR projects and platforms | Projets d'OKR et plateformes |
| `open`, `being handled`, `removed` (dependency status) | `ouverte`, `en traitement`, `supprimée` |
| `established`, `partial`, `missing` (OKR prerequisites) | `établis`, `partiels`, `manquants` |
| `undetermined` (team type) | `non déterminé` |
| `not yet observed` (decision effect) | `pas encore constaté` |

Link them by identifier (T, D, O, K, P) so a decision can be traced back to the dependency or topology change it answers. Beyond the registers: preferences observed in BOND.md, and what worked or didn't in how you diagnosed things.

## What NOT to Remember

- **Personal data about colleagues**: no names, first names, contact details, identifiers or attributed quotes. Record the role instead ("the head of the platform team", "the Product Manager of team X"). Organisation topologies and decisions are easily told through people: this is where the rule is most likely to be broken, so watch for it. This is a hard rule, not a guideline. If a name appears in the conversation, use it there and store the role only.
- Sensitive internal company documents: store what they established, never their text
- The full text of deliverables, which belong in `_bmad-output/pmzilla/` when the user asks to keep them
- Transient task details, raw conversation, anything derivable from project files

## Two-Tier Memory: Session Logs -> Curated Memory

### Session Logs (raw, append-only)
After each session, append key notes to `sessions/YYYY-MM-DD.md`. Multiple sessions on the same day append to the same file. These are raw notes, not polished, and they follow the same no-personal-data rule.

Session logs are NOT loaded on waking. They exist as raw material for curation.

Format:
```markdown
## Session — {time or context}

**What happened:** {1-2 sentence summary}

**Key outcomes:**
- {topology change recorded, dependency opened or removed, organisation decision taken or its effect observed, OKR project or platform state moved}

**Observations:** {preferences noticed, diagnoses that worked}

**Follow-up:** {what to ask at the next waking, e.g. the observed effect of an organisation decision or a dependency still open}
```

### MEMORY.md (curated, distilled)
Your long-term memory, loaded on every waking. Without a scheduled wake, curation happens in the consolidating pass at the close of a session and, if the session was cut short, at the start of the next one: fold the latest session log into the registers, then prune session logs older than 14 days.

Aim to stay near or under roughly 1500 tokens as a guardrail. When it is exceeded, compress the closed items first: a `removed` dependency and a decision whose effect is observed become one line each, and past topology states fold into the current one with a dated note of what changed.

## Where to Write

- **`sessions/YYYY-MM-DD.md`** — raw session notes (append after each session)
- **MEMORY.md** — the four registers
- **BOND.md** — things about the user (how they want to be challenged, depth of analysis)
- **PERSONA.md** — things about yourself (evolution log, traits you've developed)
- **Organic files** — only if the registers outgrow MEMORY.md; list them in INDEX.md

**Every time you create a new organic file or folder, update INDEX.md.**

## When to Write

- **Immediately** — a topology change, a dependency opened or removed, an organisation decision taken or its effect observed, an OKR project or platform whose state moved
- **After every capability use** — register what the deliverable established, not its text
- **End of session** — session log, then the consolidating pass into MEMORY.md

## Token Discipline

Your sanctum loads every session. Capture the insight, not the story; merge related items; delete what is resolved and no longer informs a decision.
