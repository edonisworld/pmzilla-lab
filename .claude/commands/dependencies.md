---
description: Reading of the dependency map between teams by the Scaling posture, from a dependencies_jira.py report
argument-hint: "[scope name or report path; empty: the most recent report]"
---

This command is written in English, but the user is served in their own language: answer in French by default if the request is in French, in English if it is in English. The fixed formulas (posture tag, "outside the library", "I infer", "Hypothesis", Critic's section titles, "My reading of this critique") are written in the language of the response, as in `tests/postures/vocabulaire.yaml`: `[Posture : Scaling]` / « hors bibliothèque » / « J'en déduis » or « Hypothèse » / « Ma lecture de cette critique » in French; `[Posture: Scaling]` / "outside the library" / "I infer" or "Hypothesis" / "My reading of this critique" in English. Critic's section titles follow the same rule (French: « Ce que Critic conteste »; English: "What Critic challenges").

Reading of the dependency map "$ARGUMENTS" (empty: the most recent report). The computation is done by the script, locally: your job is the interpretation.

## 1. Find the report

In `Flux-Lab/rapports/`, take the `dependances-*.md` file indicated by "$ARGUMENTS" (a path, or the scope name: `dependances-<nom>-AAAA-MM-JJ.md`, or `dependances-<nom>-projets-AAAA-MM-JJ.md` for a report aggregated by project), otherwise the most recent one. Read its `.json` only if you need an exact figure. Never read `Flux-Lab/exports/`: the Jira exports stay out of your reach, and the report contains no ticket key.

If there is no report, stop and give the commands to run in the Terminal, from `~/PMZilla-Lab/workspace`:

```
uv run tools/dependencies_jira.py diagnose Flux-Lab/exports/<export>.csv [<autres lots>.csv] [--scope ABC,DEF]
uv run tools/dependencies_jira.py compute Flux-Lab/exports/<export>.csv [<autres lots>.csv] --name <perimetre> [--by project] [--scope ABC,DEF] [--weeks 26]
```

The exports are manual exports or the `api-…csv` files from `export_jira_api.py` (same format; see the monthly procedure in `docs/pmzilla/installation.md`). The scope comes from `--scope` or, failing that, from `scope_projects` (old name: `projets_perimetre`) in `flux.yaml`; the other projects in the exports only serve to locate the team on the other side of a link.

## 2. Open with a verdict

After the posture tag, your response starts with a verdict sentence: what the map allows you to conclude, and what it does not. To write it, first read the report's warnings:

- the share of links that point outside the export, and the dependencies of "unknown state" (the awaited item is absent from the export, perhaps already finished: never counted as open);
- links without a type (in which case the report counts links, not blockages), excluded projects, decomposition links removed from the map (setting `portfolio_types`, old name `types_portefeuille`), tickets without a team;
- exports flagged "probably truncated" (a round number of tickets in a file: tickets are missing, do not read the map);
- the size of the lead time samples (types without enough items on both sides, fragile P85).

Nothing structural is decided on a map where most links are of unknown state: say so, and say what to redo first (widen or merge the exports).

## 3. Have the Scaling posture read the map

Activate the Scaling posture (skill `pmzilla-scaling-bmad`), action TO (diagnose a topology), with CO for the coordination mechanisms. Ask it for:

1. **The loaded pairs.** Who waits for whom, the share of the total, the asymmetry; distinguish open dependencies from those of unknown state.
2. **The loops.** They often signal a value stream cut in two rather than a coordination defect: say so as a hypothesis.
3. **Splits by site.** When teams of the same domain are distinguished mainly by their site, a dependency between them may come from the split (Conway's law) rather than from a functional coupling. The report does not give the site: ask the question rather than guess.
4. **The Team Topologies interaction modes.** For each loaded pair, which mode (collaboration, X-as-a-Service, facilitating) seems to be at play and which one would fit. The report does not give the actual mode: this is a deduction, to be announced with "I infer" (French: « J'en déduis »).
5. **Current blockages and old blockages.** An awaited item that is "not started" while the dependent one is in progress is the costliest case. Blockages older than a year are to be cleaned up (abandoned or badly closed ticket), not unblocked: do not count them as active blockages before checking.
6. **Old Epics: alive or abandoned?** When the report has this section, read the breakdown by team (alive, inactive children, no delivery child). An Epic "without children" or "with inactive children" is to be checked before being counted as a wait (the `--keys` query gives the children to look at in Jira, in the Terminal only). An Epic blocked by another Epic is portfolio sequencing, not a wait on work.
7. **The ages to check.** If the report warns "Âges à vérifier avant toute lecture" ("Ages to check before reading anything" in an English report; column "Même date d'entrée", "Same entry date" in English: at least 3 items of a row entered in progress on the same day), say so before reading the ages: it is the probable sign of a bulk status change (planning, migration), which overestimates the wait.
8. **The lead time gap, for the same type.** Present it as a correlation, never as the cost of dependencies (items with a dependency are often bigger or more uncertain, and the delay starts at creation, backlog included). Read it only for the types that have enough items; if none does, say so.
9. **For each signal, two competing explanations**, one of which is a possible measurement cause (links not filled in, projects filtered out by the query, empty or badly filled team, truncated export), and what would settle it: what to check, with which role.
10. **The questions to ask the teams**, open-ended, in roles.
11. **The possible actions, from the lightest to the most structuring** (clean up old tickets, review the use of links, clarify an interaction mode, and only then redraw boundaries). An organizational decision remains a hypothesis as long as the effect on flow has not been observed; the most structuring one is proposed only if the map allows it (see the verdict).
12. **Draw on the library** (`search_library`, domains `organisation` and `flow`, in French and in English) to shed light on the mechanisms, citing author, title and section after reading the passage; a transposition outside the author's subject is announced as such. Also look for a limit of the recommended approach (rule of `CLAUDE.md`).
13. **Pass the reading to Critic**, as for any deliverable.

## 4. Delivery

In the language of the response: the verdict, the limits, three to five signals with their two explanations, the questions to the teams, the actions, then what remains stable. Team and project names stay in the response (they are in the report); roles, never names of people, never ticket keys. If the user pastes keys displayed by `--keys` in the Terminal, do not copy them anywhere.

Nothing is saved to a file, unless the user says "keep this reading" (French: « garde cette lecture »): the posture then writes it to `_bmad-output/pmzilla/dependances/AAAA-MM-JJ-<perimetre>.md` (folder ignored by Git), with the posture, the request and the library sources used at the top.
