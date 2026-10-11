---
description: Monthly flow follow-up for a series, what moved since the previous report, interpreted by the Delivery posture (and by Scaling for a product-wide series)
argument-hint: "[series name, the same as compute --name; empty: default_series from flux.yaml]"
---

Language: this command is written in English, but the user is served in THEIR language (French by default if their request is in French). The fixed formulas are written in the language of the reply, as in `tests/postures/vocabulaire.yaml`: posture tag `[Posture : Delivery]` (French) / `[Posture: Delivery]` (English); « hors bibliothèque » / "outside the library"; « J'en déduis » or « Hypothèse » / "I infer" or "Hypothesis"; « Ma lecture de cette critique » / "My reading of this critique". The report titles and lines quoted below are in the language of the report (French by default; English for reports produced with `--language en`): both versions are given.

Monthly flow follow-up for the series named "$ARGUMENTS". If this name is empty, read the default series in `Flux-Lab/flux.yaml` (key `default_series`, or `serie_par_defaut` in a file not yet migrated); if that key is missing, ask the user for the name and stop. In what follows, `<nom>` stands for this name. The computation and the comparison are done by the script, locally: your job is the interpretation.

## 1. Find the reports

In `Flux-Lab/rapports/`:

- the latest flow report: the most recent file whose name is exactly `flux-<nom>-AAAA-MM-JJ.md` (not `flux-<nom>-recent-AAAA-MM-JJ.md` nor any other name that starts the same way);
- the latest evolution report: `evolution-<nom>-AAAA-MM-JJ.md`, and the two `flux-<nom>-AAAA-MM-JJ.md` reports it compares (their dates are in its title).

Never read `Flux-Lab/exports/`: the Jira exports stay out of your reach.

- **First series** (a single flow report for this name, so no evolution report): say so in one sentence, then read only the flow report. There is nothing to compare: the reading describes the state, not a trend, and says what the next export will make it possible to compare.
- **Several flow reports but no evolution report**, or an evolution report older than the latest flow report: stop and give the command to run in the Terminal, from `~/PMZilla-Lab/workspace` (the "Types" line of the report ("Types :" in French, "Types:" in English) says whether tickets without a team were excluded, the "Période" line ("Période :" in French, "Period:" in English) gives the number of weeks):

```
uv run tools/flux_jira.py compute Flux-Lab/exports/<nouvel export>.csv [<autres exports>.csv] --name <nom> [mêmes options que la dernière fois]
```

The "same options" are those of the series: `--scope` (the series' projects), `--history` and `--dormant-from-history` (when the state history is collected), `--points` (points of the dashboard's Aging WIP), `--weeks`, `--types`. The export is either a manual export or an `api-…csv` from `export_jira_api.py` (see the monthly procedure in `docs/pmzilla/installation.md`). Or, if both reports already exist, `uv run tools/flux_jira.py compare --name <nom>`. The comparison with the previous report is displayed at the end of the computation and saved in `evolution-…md`.

## 2. Choose the reading: team or product

Count the teams in the "Par équipe" section ("By team" in an English report) of the latest flow report.

**Vocabulary (2a and 2b).** The report ends with a section "Comment lire ce rapport" ("How to read this report" in an English report) that defines the percentiles (P50, P70, P85, P95), lead time, age, active, waiting and dormant WIP, arrivals and departures, Little's law and the Monte Carlo forecast; with the state history, also the segments, the time per segment, the commitment point, the delivery lead time, flow efficiency and coverage. In the reading, refer to this section ("see Comment lire ce rapport" / "see How to read this report") rather than redefining these terms, unless a specific figure requires it (for example why a P85 of 279 days is not read as a promise in this case).

- **10 teams or fewer**: reading by Delivery, as before (2a).
- **More than 10 teams**: product-wide series (2b).

### 2a. Have the Delivery posture interpret

Activate the Delivery posture (skill `pmzilla-delivery-bmad`) and run its DF action in follow-up mode, from the evolution file and the new flow report. Ask it for:

1. **Comparability first.** If the "Comparabilité" section ("Comparability" in an English report) exists, say what it prevents from concluding before anything else. Three notes are frequent: "Périmètres différents (--scope)" ("Different scopes (--scope)" in English) (the two reports do not cover the same projects: no difference in throughput, WIP or lead time is read as a change in the flow); "Comparaison partielle" ("Partial comparison") or "non comparé" ("not compared") (a report in an old format does not have all the sections: conclude nothing on the skipped sections, and say so); different types, window or in-progress states.
2. **Start from "Ce qui a bougé"** ("What moved" in an English report). For each signal: at least two competing explanations, including one possible measurement cause (export, classification of states in flux.yaml, leave, administrative closures); what would need to be checked, and with which role; the question to ask the team.
3. **Read the recent sections of the flow report, when they exist.** The "Périmètre" line ("Scope:" in an English report) at the top (projects kept, tickets kept out of those read) says what the series covers. "Arrivées et sorties" ("Arrivals and departures"): if arrivals durably exceed departures, the stock grows, but rejected tickets count in the arrivals (see the report's note). "Temps par segment" ("Time in segment") (only with `--history`): where time accumulates, flow efficiency, and above all coverage; below 90%, the report warns and no segment figure describes all the tickets. Refer to "Comment lire ce rapport" ("How to read this report") for the definitions.
4. **Also look below the thresholds.** A difference below the threshold but going in the same direction as the previous month counts: compare with your notes in memory, then update them.
5. **Do not conclude about a team from a single signal.** The per-team series are short; an isolated signal is a question, not a finding.
6. **Draw on the library** (`search_library`) to shed light on the mechanisms (queues, WIP, batch closures, forecasts), citing book and section.
7. **Pass the diagnosis to Critic**, as for any deliverable.

### 2b. Product-wide series

1. **Overview by the Scaling posture** (skill `pmzilla-scaling-bmad`), from the evolution file and the flow report: comparability first (what the "Comparabilité" ("Comparability") section prevents from concluding, including a change of scope or a report in an old format, and, for a first series, the absence of comparison); the scope of the series ("Périmètre" / "Scope:" line at the top of the report, when it exists); then the overall throughput and lead time and their trend ("Ce qui a bougé" / "What moved"); then the share of work set aside as portfolio or as an excluded project, from the "Écartés" line of the report ("Left out of throughput, lead time, WIP and forecasts" in an English report) (number by type and by project: any percentage is computed by the agent and flagged as such). No organizational reading and no structure proposal.
2. **Three teams by the Delivery posture** (skill `pmzilla-delivery-bmad`, DF action in follow-up mode): it comments only on the 3 teams whose differences are the clearest according to "Ce qui a bougé" ("What moved"), and says that other readings are possible, because this choice follows the clarity of the differences, not the importance of the teams. For a first series, no team has a history to compare itself with: it comments on none.
3. **Never rank teams, nor compare teams with each other.** Each difference is compared with the team's own history. The "Par équipe" ("By team") table is not a ranking; repeat the report's note: teams are not compared with each other (workflows, ticket sizes and types of work differ).
4. **Same requirements as a team series:** for each signal, at least two competing explanations, including one possible measurement cause (classification by state category, merging of exports, excluded types or projects, truncated export, administrative closures); what would need to be checked, and with which role; the question to ask the team; the library (`search_library`, book and section) to shed light on the mechanisms.
5. **Pass the complete reading to Critic**, as for any deliverable.

## 3. Delivery

In the language of the user's request (French by default), short. For a team series: three to five points that moved, the hypotheses to check and the questions for the teams, then what remains stable. For a product-wide series: the overview, the three teams commented on with the mention of the other possible readings, the hypotheses to check and the questions, then what remains stable. Roles, never names of people. Nothing is saved to a file, unless the user says "garde ce diagnostic" ("keep this diagnosis"): the posture then writes it to `_bmad-output/pmzilla/flux/AAAA-MM-JJ-<nom>.md` (folder ignored by Git: team names stay there, names of people remain forbidden).
