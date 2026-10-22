# PMZilla Lab

A coaching assistant for product management and agility, built on **Claude Code**, the **BMAD** framework and a **personal digital library** of 121 books that can be searched with hybrid search.

PMZilla Lab is version 2 of PMZilla, a Claude Desktop project. It keeps its identity and its five postures, and adds three things: agents that keep the memory of the work from one session to the next, answers grounded in the library with verifiable citations, and an independent critic that challenges every deliverable.

The library is topped up every morning by an **automated watch**: articles from the followed sources are collected, judged by a local model, sorted into a reading list, and the best ones join the library. The articles published by the user form a separate collection, which the postures can set against the books.

The history up to 13 October 2026 is in [CHANGELOG.md](CHANGELOG.md), which is frozen; the later history is in the GitHub releases. This README describes the current state.

---

## Contents

1. [What PMZilla Lab does](#1-what-pmzilla-lab-does)
2. [Architecture](#2-architecture)
3. [Step-by-step installation](docs/pmzilla/installation.md)
   - [User manual (French, generated)](docs/pmzilla/manuel.md)
4. [The five postures](#4-the-five-postures)
5. [The library](#5-the-library)
6. [Watch](#6-watch)
7. [Starting a session](#7-starting-a-session)
8. [Repository layout](#8-repository-layout)
9. [Maintenance](#9-maintenance)
10. [Privacy](#10-privacy)
11. [Evolution ideas](#11-evolution-ideas)

---

## 1. What PMZilla Lab does

PMZilla Lab supports an Agile Lead in daily work: framing a product problem, diagnosing a flow problem, rethinking a multi-team organization, preparing a workshop. It is never a generalist assistant that talks agile. Every answer is produced in an **identified posture**, with its own framework, references and refusals.

Its operating principles:

- **It routes before answering.** Each request is tied to a posture, announced at the top of the answer (`[Posture : Discovery]`). If the request is ambiguous, it asks a question instead of guessing.
- **It searches before framing.** Before drawing on a framework or an author, it queries the library, reads the central passages and cites *Author, Title*, section. Whatever comes from its general knowledge is flagged "hors bibliothèque" (out of library).
- **It remembers.** Each posture keeps in memory the teams, the problems it has framed, the hypotheses and their status, the decisions taken and the experiments run.
- **It gets contradicted.** On a deliverable (a diagnosis, a plan or a synthesis the user keeps, or a diagnosis built from the user's data), never on a framing answer, an independent Critic subagent challenges the answer. It is launched in the foreground, and the final message keeps the order: posture analysis, Critic summary, "Ma lecture de cette critique" (My reading of this critique) (`CLAUDE.md` rule, step 4). It flags: output / outcome confusion, a framework applied without diagnosis, assumed maturity, a symptom treated instead of the cause, agile clichés, an ignored political angle, disproportionate effort.
- **It refuses generic answers.** If an answer could be given to any team, it stops and asks for context.

---

## 2. Architecture

```
                       You
                       │
                       ▼
          ┌──────────────────────────┐
          │       Claude Code        │  CLAUDE.md: identity, context,
          │      (main session)      │  routing protocol, rules
          └────────────┬─────────────┘
                       │ routes to a posture
   ┌──────────────┬────┴─────────┬──────────────┐
   ▼              ▼              ▼              ▼
Discovery      Delivery       Scaling      Facilitation   BMAD agents with memory
   │              │              │              │         (.claude/skills/*-bmad)
   └──────────────┴──────┬───────┴──────────────┘
                         │ deliverable (not a framing)
                         ▼
                ┌─────────────────┐
                │     Critic      │  subagent, separate context
                └────────┬────────┘  (.claude/agents/pmzilla-critic.md)
                         │
     postures and Critic query the library
                         ▼
          ┌──────────────────────────────────┐
          │ MCP server pmzilla-library       │  local, on the Mac
          │ search_library · read_passage    │
          │ list_collections · list_books    │
          │ search_cases · search_experiments│
          │ list_due_reviews                 │
          └──────────────┬───────────────────┘
                         ▼
          PostgreSQL index (BM25 + bge-m3 vectors, Ollama, local),
          written directly by the indexer
          121 books in Markdown, 5 domains,
          plus the collections watch (articles), own-articles (your articles)
          and contexte (organisation context notes, private)
                         ▲
                         │ every morning at 7:10 (launchd)
          ┌──────────────┴───────────────┐
          │ watch.sh                    │  RSS collection (watch_lab.py)
          │ collect · pre-triage · index │  pre-triage gemma4:26b (watch_triage.py)
          └──────────────┬───────────────┘
                         ▼
          Watch-Lab/_to-read.md: the 5 to read, then SignalPM
          ~/PMZilla-Lab/tableau-de-bord.html: dashboard
```

| Component | Role | Where it lives |
|---|---|---|
| Claude Code | Reasoning and orchestration engine | Installed on the Mac (`claude`) |
| BMAD and BMad Builder | Agent framework: persona, menus, memory | `_bmad/` |
| Posture agents | The four postures, with their memory | `.claude/skills/pmzilla-*-bmad/` |
| Critic | Adversarial subagent, deliberately without memory | `.claude/agents/pmzilla-critic.md` |
| `pmzilla-library` server | Hybrid search in the library | `tools/pmzilla_lab_library.py` (called through the `~/PMZilla-Lab/` path, a link to `tools/`) |
| Index | Passages, vectors, full-text search: PostgreSQL (schema `knowledge`), written directly by the indexer. No fallback route; `tools/library_parity.py` compares the search results of a frozen set of queries with a snapshot recorded by hand (regression guard after a REINDEX or a change of the search code) | PostgreSQL (schema `knowledge`) |
| Book catalog | Title and authors of each book, returned with each passage | `tools/book_catalog.yaml`, read at indexing time |
| Watch | Daily collection of articles, feeds the `watch` collection | `tools/watch_lab.py`, `watch_triage.py` and `watch.sh` (launched by launchd through its `~/PMZilla-Lab/` path, a link to `tools/`) |
| Components watch | Inventory of every component (packages, Python, database image, Ollama models, BMAD, tools) and a weekly check of new versions, run by the watch, shown on the dashboard; each update retained becomes a job of the work queue | `docs/pmzilla/composants.yaml`, `tools/composants.py` (`inventory`, `check`); procedure in the [installation](docs/pmzilla/installation.md#18-components-watch) |
| Coaching journal | Sessions, promised follow-ups, experiments (start, note, review, close) and cases; recalled by the postures; due reviews listed at the start of a session by a `SessionStart` hook (`journal_lab.py experiment due --session-hook`, `.claude/settings.json`) and by the MCP tool `list_due_reviews` | `tools/journal_lab.py`, data in `Journal-Lab/` (outside Git) |
| Database (lots 1, 2, 4 and 6) | PostgreSQL in a container (Colima, `paradedb/paradedb` pinned), numbered SQL migrations, one access role per schema, quarterly restore test in a throwaway container; schema `knowledge` (library written directly by the indexer, `pmzilla_lab_library.py status` and `probe`, hybrid search in SQL); schema `cases` (cases and experiments of the journal, migration 0006, read by the postures through the MCP tools `search_cases` and `search_experiments`), schema `flow` (Jira tickets, transitions, links, teams, never a title, a description or a person) fed from the Jira API (raw layer, import, history), schema `quality` (title, description and acceptance criteria of stories and epics, with mentions and sensitive names replaced by markers, kept one year at most, analysed by `tools/story_quality.py`, which you alone run; migrations 0010, 0015 and 0016), nine aggregated views (four flow views, two team-name views, three quality views) with masking under 5 tickets that Claude Code reads only through `tools/flow_views.py`, never a table, the flow and dependency tools reading only the database, one-year retention rule checked by `tools/flow_retention.py` | `docker-compose.yml`, `tools/db_up.sh`, `tools/db_backup.sh`, `tools/com.pmzilla.db-backup.plist` (daily launchd backup at 7:45), `tools/db_restore_test.sh`, `tools/dbtest.sh` (the suites that need a database, in a throwaway container), `tools/hybrid_search.py`, `tools/knowledge_library.py`, `tools/library_parity.py`, `tools/db.py`, `db/migrations/`, `tools/flow_import.py`, `tools/flow_store.py`, `tools/flow_views.py`, `tools/flow_compare.py`, `tools/flow_organisation.py`, `tools/flow_retention.py`, `tools/cases_store.py`; design in [application](docs/pmzilla/application.md), procedure in the [installation](docs/pmzilla/installation.md) |
| Off-site backup | Copy of the newest database and sanctum backups to one encrypted external disk (found by its volume identifier, no network command, checksum manifest, rotation), monthly restore test of that copy in a throwaway container; the flow dump is removed from copies older than the retention age | `tools/offsite_backup.sh` (`setup`, `copy`, `restore-test`, `status`), `tools/com.pmzilla.offsite-copy.plist` (daily at 8:15 and at each volume mount) and `tools/com.pmzilla.offsite-restore-test.plist` (daily at 8:45, the test runs once a month); procedure in the [installation](docs/pmzilla/installation.md#147-off-site-backup-encrypted-external-disk) |
| Monthly flow run | The monthly sequence (export, import, history, flow and dependencies per series, dashboards, retention dry run) in one command, which stops at the first gap; you run it in the Terminal | `tools/flow_monthly.py`, `monthly_run` block of `Flux-Lab/flux.yaml`; summary in `Flux-Lab/rapports/suivi-mensuel-AAAA-MM-JJ.md`; procedure in the [installation](docs/pmzilla/installation.md#monthly-run-in-one-command) |
| Run tree | The scheduled jobs and the library server run the code of a separate linked worktree, `~/PMZilla-Lab/run` (detached head equal to local `main`), so the development checkout can be on any branch at any time; created and updated by you in the Terminal | `tools/run_worktree.sh` (`create`, `update`, `status`), procedure in the [installation](docs/pmzilla/installation.md#run-worktree-toolsrun_worktreesh) |
| Work queue | The jobs live in GitHub issues; reads go through `tools/roadmap.py`, every write through `tools/gh_issue.py`; parallel work in worktrees | `tools/roadmap.py`, `tools/gh_issue.py`, `tools/worktree.sh`, `tools/finish_branch.sh`, `tools/finish_worktree.sh`; commands `/next`, `/start`, `/batch`; see [Working on the repository](#working-on-the-repository) |
| BMAD update | Replays, after the BMAD installer, the text replacements the repository imposes on installed skills (the installer rewrites `.claude/skills/` without warning) | `tools/bmad_remplacements.py`, rules in `.pmzilla/remplacements-bmad.tsv` (local, ignored by Git); procedure in the [installation](docs/pmzilla/installation.md#4-install-bmad) |
| Spec writer | Subagent that writes or reverse-engineers the OpenSpec specs and change proposals, never code | `.claude/agents/spec-writer.md`, specs in `openspec/` (`config.yaml`, `specs/`, `changes/`) |
| Critic mirror | Critic's objections extracted from deliverables, to see which ones come back | `tools/critic_mirror.py`, read by `/critic-mirror` |
| Dashboard | Local HTML page: health, what is to do, the watch, the library, posture quality, flow, Critic, components | `tools/dashboard.py`, page written to `~/PMZilla-Lab/tableau-de-bord.html` |
| User manual | Every command by feature, with its parameters, who launches it (Terminal or Claude Code), exit codes and one example; generated in French by reading the scripts, never run; a blocking test fails when it is stale | `tools/manual.py` (no option: print; `--write`: write `docs/pmzilla/manuel.md`; `--check`: compare), read at [docs/pmzilla/manuel.md](docs/pmzilla/manuel.md); a branch that adds or changes a command regenerates it in the same commit |
| Install script | Scripted steps of a fresh installation (published edition, no personal data), one step at a time, each change confirmed (`y/N`, default no), `--dry-run`, already-done probes, no secret handled; the migrate mode (your own data from another machine) is future work (change `install-migrate`) | `tools/install_lab.sh` (zsh bootstrap), `tools/install_lab.py` (orchestrator) and its modules `tools/install_lab_*.py`; usage in the [installation](docs/pmzilla/installation.md#install-script) |
| English edition | Shareable English tree of a committed state, every tracked file classified by a manifest, checked for personal identifiers and sensitive names; never publishes | `tools/build_edition.py`, `tools/publish_edition.py` (prepares the permanent local copy of the public repository for a publication, never commits nor pushes), `edition/manifest.yaml`, `edition/templates/`; procedure in the [installation](docs/pmzilla/installation.md#generating-the-english-edition-toolsbuild_editionpy) |
| Ollama + bge-m3 | Vector computation, local | Ollama app |
| Ollama + gemma4:26b | Watch pre-triage: themes, compilations, substance, summaries | Ollama app |

---

## 3. Step-by-step installation

**Supported platform: macOS on Apple Silicon. Windows (through WSL2) is planned, not supported yet.**

The installation, from a brand-new Mac to a first session, a watch that runs every morning and an evaluation set that passes, is described in [docs/pmzilla/installation.md](docs/pmzilla/installation.md). Allow half a day, mostly waiting (converting and indexing the books, downloading the models). The file also contains the "Add a book" procedure and eighteen commands to check the installation (section 13, including the `pre-push` hook link). The steps that can be scripted (prerequisites, repository, hooks, links, database, launchd jobs, MCP server, check) are run by `zsh tools/install_lab.sh --mode fresh`, each change confirmed: see its [Install script](docs/pmzilla/installation.md#install-script) section.

---

## 4. The five postures

| Posture | Agent | Activated when the request is about | Reasons in terms of | Domains |
|---|---|---|---|---|
| **Discovery** | `pmzilla-discovery-bmad` | problem, hypotheses, user need, experimentation, opportunity | product risks before solutions, testable hypotheses before roadmap | `produit` |
| **Delivery** | `pmzilla-delivery-bmad` | team performance and predictability, flow, quality, DORA, rituals | flow before capacity, lead time before velocity | `flow`, `tech` |
| **Scaling** | `pmzilla-scaling-bmad` | multi-team coordination, product structure, scaling frameworks, platforms | value stream before org chart, cognitive load before team size | `organisation`, `flow` |
| **Facilitation** | `pmzilla-facilitation-bmad` | workshop, meeting, questioning, coach / SM / PO posture | intent before format, psychological safety before apparent efficiency | `facilitation` |
| **Critic** | `pmzilla-critic` | never alone: on a deliverable, not on a framing | skeptical, dry, undiplomatic | the whole library |

The full framework of each posture (references, refusals, menu) is in `docs/pmzilla/postures/`.

### Action menus

Each agent offers four or five actions, callable by their code (Discovery, Delivery and Facilitation have a fifth, on story quality; Scaling has four):

| Posture | Actions |
|---|---|
| Discovery | **CP** frame a problem · **HY** formulate testable hypotheses · **XP** design an experiment · **OS** build an Opportunity Solution Tree · **SQ** audit a pasted epic's problem, outcome and hypothesis |
| Delivery | **DF** diagnose a flow problem · **ME** choose and read metrics · **RI** review a ritual · **QI** work on built-in quality · **SQ** audit a pasted story (or an epic's readiness and splitting) |
| Scaling | **TO** diagnose a team topology · **CO** improve multi-team coordination · **OK** assess an OKR project · **PL** treat a platform as a product |
| Facilitation | **AT** design a workshop · **RE** prepare a retrospective · **PO** work on a coaching posture · **QU** prepare a line of questioning · **SC** prepare a story coaching conversation with a PO |

**Manual audit mode.** Paste a story or an epic into a session and ask for **SQ**: the posture audits it against the effective grid (core grid plus the organisation overlay), one verdict per criterion with its reason and source. The pasted text is never written to a tracked file, a memory or GitHub, and the audit kept in `_bmad-output/` holds the verdicts, the learning points and a summary of Critic's objections (the objection alone, never a quotation of the pasted text).

### What each posture refuses

- **Discovery**: jumping to the solution; giving an opinion on "what to build" without the "for whom" and the "why"; confusing user validation with stakeholder acceptance.
- **Delivery**: prescribing a framework without diagnosing the constraint; treating velocity as a performance indicator; recommending to "estimate better".
- **Scaling**: recommending SAFe by default; treating org design as an HR problem; proposing OKRs without questioning product maturity and team stability.
- **Facilitation**: recommending a format before clarifying the goal; giving generic templates without knowing the group's context; treating facilitation as a logistics problem.

### Flow metrics (`flux_jira.py`)

**What it is for.** Computing locally, from the tickets in the database, the weekly throughput, lead time, WIP, age of in-progress items, arrivals and departures, Monte Carlo forecasts and, with the state history, the time per segment; then having the Delivery posture interpret them (action **DF**, or `/monthly-flow` for follow-up). Only aggregates are produced: no ticket, no title, no person.

| Command | Role |
|---|---|
| `uv run tools/flux_jira.py statuses` | recognized columns, period, states and types to classify in `flux.yaml`; reads the database only (an export file or `--source` is refused, exit 2); you run it yourself in the Terminal |
| `uv run tools/flux_jira.py compute --name <série> [--scope ABC,DEF] [--by {team,mission-team,site}] [--history] [--dormant-from-history] [--batch-closure-resolutions MOTIFS]` | writes `Flux-Lab/rapports/flux-<série>-AAAA-MM-JJ.md` (and `.json`), then the comparison with the series' previous report; `--by mission-team` or `--by site` groups the report by the groups of the organization reference; reads the `flow` schema only (no export file, no `--source`, no path given to `--history`; with no history in the database, `--history` and `--dormant-from-history` stop with exit 1); you run it yourself in the Terminal |
| `uv run tools/flux_jira.py cycles --name <série> [--scope ABC,DEF]` | cycles report read from the database only (no CSV is accepted); you run it yourself in the Terminal |
| `uv run tools/flux_jira.py epics --name <série> [--language en]` | epic flow report of the pilot domain (idea to Ready, passages in Epic Review, planned cycle and carry-over, epics per column, age), read from the database only; masked under five; you run it yourself in the Terminal |
| `uv run tools/flux_jira.py compare --name <série> [--before AAAA-MM-JJ] [--after AAAA-MM-JJ]` | redoes the comparison on demand |
| `uv run tools/segment_sample.py [--segment revue_verification] [--today AAAA-MM-JJ] [--seed 42] [--by-state] [--starts] [--exclude-batch-closures]` | sample of tickets from a segment (longest ones, draw near the median, oldest ones still in it; `--by-state`: time per state and grouped closures; `--exclude-batch-closures`: leaves out the tickets that left the segment in a batch closure (rule of the flow report's "Fermetures groupées" section); `--starts [--min-passes N]`: verification starts per project, with two measures against chance over the working days (French public holidays removed): the concentration at equal active days (expected share, 95th percentile of the draws, yes/no flag) and the active days without any condition (distinct days observed against expected, 5th percentile, ratio, yes/no flag "fewer active days than chance"), 1000 draws with a fixed seed): keys and states only, in the Terminal |

**Reading.** `/monthly-flow [série]` (`.claude/commands/monthly-flow.md`) has Delivery read the report and its evolution (Scaling first for a product-wide series), with Critic: three to five points that moved, two explanations each, the questions for the teams, in roles and never in names. "Garde ce diagnostic" (Keep this diagnosis) writes it to `_bmad-output/pmzilla/flux/` (outside Git). A gap below the threshold does not prove stability; a gap above it is a question to ask, not a conclusion.

**Limits** (repeated in each report): lead time starts at creation, backlog included, so it is not a cycle time; without `--history`, there is no time per state; throughput counts closed tickets, not delivered value; forecasts assume a future throughput close to the past; per team, series are short and cannot be compared between teams.

Step-by-step procedure, options, `flux.yaml` settings, the `Flux-Lab/` folder and the report contents: [installation](docs/pmzilla/installation.md#flow-metrics-procedure-options-and-reading) and [settings](docs/pmzilla/installation.md#fluxyaml-settings).

### State history (`history_jira.py`)

Collects the history of the status field only for the tickets of the database (date, from-value, to-value) of the status, of the fix version and of the labels declared in `flux.yaml`, never the author of the event, to get the time per state, and writes it into the database: `test`, `collect`, `check` (no export file, no cache file). The measurement is validated by the organization on condition that it is aggregated by team and contains no individual data; the token stays in the macOS Keychain, the history in the `flow` schema (unreadable by Claude Code). Token, settings and output: [installation](docs/pmzilla/installation.md#state-history-collection).

### Jira API export (`export_jira_api.py`)

Reads every ticket of the `jql_export` or `jql_exports` queries of `flux.yaml` at each run and writes them straight into the raw layer of the database (no file; the CSV route ended with the `database-only` change): `export [--query NAME] [--strict-teams]`, `fields`, `diagnose`. `teams-table` and `compare` are removed (the team identifiers are translated through the organisation referential `Flux-Lab/organisation.yaml` and the team catalogue `Flux-Lab/equipes-jira.yaml`; the former table `equipes-assets.yaml` is no longer read, and `export` lists the unknown identifiers). The monthly procedure (export, import, collection, flow, dependencies, readings) is in the [installation](docs/pmzilla/installation.md#monthly-procedure-through-the-api); the detail of the command is in the [installation](docs/pmzilla/installation.md#jira-api-export).

### Jira data in the database, views and retention (`flow_views.py`, `flow_retention.py`)

The Jira tickets, status transitions, links and teams read from the API can also live in the `flow` schema of the local database (imported with `flow_import.py`, which derives them from the raw layer; `flow_compare.py reports` compares two flow reports; you run both yourself). Claude Code never reads the tables: it reads only the aggregated views, with a cell under 5 tickets written `masqué` (`masked` in English).

| Command | Role |
|---|---|
| `uv run tools/flow_views.py list` | the available views |
| `uv run tools/flow_views.py show <view> [--min-cell N]` | the content of a view; the masking threshold can be raised, never lowered under 5 |
| `uv run tools/flow_retention.py check` | counts what is past the one-year retention rule, deletes nothing; exit code 0 when nothing is past the rule, 4 otherwise |
| `uv run tools/flow_retention.py purge [--apply]` | dry run by default; `--apply` deletes, and needs a labelled backup of the day (exit code 3 without it) |
| `uv run tools/epic_statuses.py [--history]` | writes `Flux-Lab/rapports/statuts-epics-AAAA-MM-JJ.md`: per status, the number of Epics and the most frequent outgoing transitions, counts under 5 written `masqué` (`masked` in English) |

`flow_retention.py` and `epic_statuses.py` are run by you alone in the Terminal (they refuse to start in a Claude Code session, exit code 3). Settings (`retention`, `epic_types`, `flow_views_min_cell`), the one-time database setup and the dry run before the first purge: [installation](docs/pmzilla/installation.md#141-jira-in-the-database-lot-6) and [retention](docs/pmzilla/installation.md#148-retention-of-flow-data-one-year-rule).

### Monthly run in one command (`flow_monthly.py`)

`uv run tools/flow_monthly.py [--dry-run] [--from STEP] [--date AAAA-MM-JJ] [--force] [--verbose] [--language {fr,en}] [--open]` chains the monthly steps in a fixed order (`export`, `import`, `history`, `flow`, `dependencies`, `dashboard`, `retention`), passes no file path, and stops at the first gap. It adds no calculation, reads only `Flux-Lab/flux.yaml` (block `monthly_run`, the series to compute) and `Flux-Lab/rapports/`, and writes `Flux-Lab/rapports/suivi-mensuel-AAAA-MM-JJ.md`. You run it yourself in the Terminal. Exit codes: 0 complete; 1 a step failed; 2 usage (an unknown step, the removed `compare-data` and `compare-reports` included); 3 prerequisite refused; 5 this month's run is already complete (`--force` to run again). On a failure it prints the resume command (`--from <step>`). Reading afterwards: `/monthly-flow <série>` and `/dependencies <série>`. Procedure and the `monthly_run` block: [installation](docs/pmzilla/installation.md#monthly-run-in-one-command).

### Visual flow dashboard (`flow_board.py`)

A single self-contained HTML file, readable offline (no network call: the ECharts library, the CSS, the JavaScript and the data are in the file), for Agile Leads who find Markdown reports hard to read: arrivals and departures, cumulative flow diagram, time per segment, Aging WIP, WIP breakdown, delivery lead time and flow efficiency, interactive dependency map, evolution since a pilot's baseline. Product view first, then a team selector in alphabetical order, never a ranking; "How to read" on each chart; English by default (`--language fr` for French); `--anonymous` for a shareable version; A4 printing. `uv run tools/flow_board.py` writes it to `Flux-Lab/tableaux/` (outside Git, unreadable by Claude Code). Library installation (once), settings and procedure: [installation](docs/pmzilla/installation.md#visual-flow-dashboard).

### Dependency map (`dependencies_jira.py`)

**What it is for.** Seeing who waits for whom between teams, from one or more Jira exports (batches of projects, to stay under the 10,000-ticket limit), on the same principle as `flux_jira.py`: ticket keys are used only to link tickets to each other, in memory, and are never written; the report contains only aggregates and team names. The script is run from `tools/`. The export and the settings are described in the [installation](docs/pmzilla/installation.md#dependency-map).

| Command | Role |
|---|---|
| `uv run tools/dependencies_jira.py diagnose [--scope CLÉS]` | recognized columns, link types and their count, share of links that leave the data read, excluded projects, decomposition links, tickets without a team; no keys |
| `uv run tools/dependencies_jira.py compute [--name NOM] [--by {team,project,mission-team,site}] [--scope CLÉS] [--weeks N] [--keys]` | writes `Flux-Lab/rapports/dependances-<nom>-AAAA-MM-JJ.md` (and `.json`); `--by project` aggregates by Jira project, `--by mission-team` or `--by site` by group of the organization reference; reads the `flow` schema only (an export file or `--source` is refused, exit 2; you run it yourself in the Terminal); `--scope` replaces `scope_projects` of `flux.yaml` (comma-separated keys, or `tous`); `--weeks` sets the lead time period (26 by default); `--keys` prints the keys of the blockers in the Terminal only |

The report contains a team-by-team matrix, a Mermaid graph, loops, current and old blockers, waits toward an item outside the export, old Epics (alive or abandoned) and the lead time gap with and without an external dependency; it ends with a reading section. The settings (`scope_projects`, `excluded_projects`, `portfolio_types`, `blocking_link_types`, `waiting_link_types`, `project_names`) are in `flux.yaml`.

`/dependencies [scope or report]` (defined in `.claude/commands/dependencies.md`) reads a report with the Scaling posture. It opens with a verdict on what the map does or does not allow concluding, then reads the loaded pairs, the loops, the splits by site, the Team Topologies interaction modes, the old blockers and the lead time gap presented as a correlation, with two explanations per signal, the questions to ask the teams, actions from the lightest to the most structural and citations from the library, then passes the reading to Critic. "Garde cette lecture" (Keep this reading) writes it to `_bmad-output/pmzilla/dependances/` (a folder excluded from Git).

**Read with caution.** A dependency between two Epics (types set by `portfolio_types`) measures portfolio sequencing, not a wait on work: its age is the age of the Epic's life. When most open dependencies are between Epics, the map first describes this sequencing. The "Même date d'entrée" (Same entry date) column counts the items that entered in progress on the same day (at least 3, and at least half of the row); the "Âges à vérifier" (Ages to check) warning lists these rows: it is the probable sign of a bulk status change (planning, migration), which overestimates the wait. Items with neither an entry date nor a creation date are ignored in this count. Generic example: if Team A has 5 Epics in progress waiting for Team B, their age does not say how long work has been waiting.

**Limits**: only links declared as blocking are seen ("Relates" links do not count); a link to a ticket absent from the exports is "of unknown state" and is never counted as open, but a map where most links are of unknown state does not allow a conclusion; links without a type do not say who waits for whom; the lead time gap is a correlation, on a sample that is often small.

---
## 5. The library

121 books converted from PDF or EPUB to Markdown (EPUB is preferred when both exist; if it fails to convert, the PDF of the same book replaces it, and the report says so), spread over five domains. A book can belong to several domains; it is indexed only once.

| Domain | Books | Examples |
|---|---|---|
| `produit` | 32 | *INSPIRED*, *Empowered*, *Continuous Discovery Habits*, *Discovery Discipline*, *User Story Mapping*, *User Stories Applied*, *Agile Estimating and Planning*, *Lean UX*, *The Lean Startup* |
| `flow` | 36 | *Accelerate*, *The Principles of Product Development Flow*, *Project to Product*, *The Art of Agile Development*, *Clean Agile*, *Fixing Your Scrum*, *Actionable Agile Metrics for Predictability* |
| `organisation` | 56 | *SAFe Coaches Handbook*, *Team Topologies*, *Org Topologies*, *Architecture for Flow*, *Drive*, *The OKRs Field Book*, *Leading Change* |
| `facilitation` | 36 | *The Five Dysfunctions of a Team*, *Coaching Agile Teams*, *Agile Coaching*, *Host*, *Training from the Back of the Room*, *Mindset*, *Coaching d'équipe*, *Zombie Scrum Survival Guide* |
| `tech` | 26 | *Domain-Driven Design Distilled*, *Introducing EventStorming*, *Balancing Coupling*, *The Platform Engineering Playbook*, *AI Agents*, *Latency* |

**Search**: hybrid, by meaning (bge-m3 vectors) and by keywords (BM25 in PostgreSQL), merged by reciprocal rank fusion. It works in French and in English, whatever the language of the book. `search_library` accepts a `since` parameter (YYYY-MM-DD) that keeps only articles published since that date; books, which have no date, are not filtered. When relevance is close, recent watch articles rank ahead of older ones (the bonus is halved every six months); books and the `own-articles` collection do not age.

**Figures**: `convert_books.py` keeps figures as text blocks (the author's caption, useful alternative text) and stores their images in `Bibliotheque-Images/` (outside Git, unreadable by Claude Code). The indexer turns them into passages of type `figure`, separate from running text: vectorized text = caption + useful alternative text + the sentence of the book that refers to the figure ("Figure 1.2"); for a PDF, the caption that the page text repeats is removed from the text passages, so that it appears only once. By default `search_library` returns text only; `types ["figure"]` (or `["texte", "figure"]`) searches figures and returns, along with the caption, a `ref` (label "Figure X.Y", page, section, `image`: a path written as text, which you open yourself). No tool opens or sends an image; the rule for citing a figure is in `CLAUDE.md`. Procedure for a few books: [installation](docs/pmzilla/installation.md#12-add-a-book).

**Read-only diagnostics**: two scripts in `tools/` shed light on figures and on book sorting without changing anything. `uv run tools/caption_diagnostic.py <book.md>` replays the removal of PDF captions from the page text and sorts the ones that remain by cause (too far from the block, stuck to other words, cut off, different form, not found), displaying only counts: never a caption, a title or a path. `python3 tools/sorting_exclusions.py [<markdown_folder>]` tabulates the books that `sort_by_domain.py` sets aside (where the book is kept in their place, reason, size, source format, figures, from the header only), without moving or deleting anything; a set-aside book that is missing from its `GARDES` table appears as "à identifier" (to be identified).

**Author catalog**: `tools/book_catalog.yaml` gives, for each book file (key = the name of the `.md` file), the title, the authors and, when known, the year. At indexing time, the catalog title replaces the one found in the file and the authors become the `author` field returned by `search_library` and `read_passage`, as for watch articles; without an entry, the book comes out as "auteur non indiqué" (author not stated) and is cited by its title alone. `a_verifier: true` marks a title or an author inferred from the file name. A change of title or author updates the index without recomputing the vectors. The server reads the catalog in the repository (`PMZILLA_LAB_CATALOGUE` for another path). The postures cite the author that is returned, never the one they think they know (rule in `CLAUDE.md`).

**Known gaps**: a few references of the postures are not in the library, but none is a priority any more (the official SAFe documentation, the Hyper Island toolbox and the Scrum Guide remain open; *Liberating Structures*, *The Goal*, *Kanban* and other references cited by the postures are in the library). *Accelerate*, *Continuous Discovery Habits*, a SAFe book (*SAFe Coaches Handbook*) and *Team Topologies* were added on 3 October 2026. The full list, with what partly covers each gap, is in `docs/pmzilla/bibliotheque-lacunes.md`. A few books cited by postures are still missing from the library since the clean-up of 5 October 2026 (badly named files, or a file holding another book) and need to be downloaded again: *Switch*, *Practices for Scaling Lean & Agile Development*, *Behind Closed Doors*, *The Sketchnote Handbook*, *The Sketchnote Workbook* and *Leadership Agility* (listed in a comment on `MAPPING`, in `mapping_lab.py`); *Leading Beyond Change* and *The Changing World Order* are still to be classified (`docs/pmzilla/bibliotheque-lacunes.md`, with the prioritized detail). The other books of that clean-up have been reloaded and are in the catalogue (`tools/book_catalog.yaml`): *Zombie Scrum Survival Guide*, *Louder Than Words*, *Turn the Ship Around!*, *Practical Ways to Lead an Innovative Organization*, *Peopleware*, *The Lean Startup*, *Agile Retrospectives*, *Actionable Agile Metrics for Predictability*, *Management 3.0* and *The Secrets of Consulting*. *Scrum Mastery* (Watts), *The Professional ScrumMaster's Handbook* (Viscardi) and *Agile Contracts* (Opelt, Gloger, Pfarl, Mittermayr) were added on 5 October 2026, along with Anderson's *Kanban* (the complete book, which replaces a summary), Cardon's *Coaching d'équipe*, Lenhardt's *Coaching for Meaning* and Rosenberg's *Les mots sont des fenêtres (ou bien ce sont des murs)*. *Host*, by McKergow and Bailey, joined the catalog under its real title. *Gamestorming* (the English edition is missing) is indexed without a source file: its `.md` must not be deleted, and the original should be put back in `Livres - Ressources` if it is found again (`docs/pmzilla/bibliotheque-lacunes.md`).

**Section titles**: citations give the section when the book has one in the index. For books whose conversion produced no headings, the agents cite the chapter read in the text, or the passage alone, and never invent a section. A chapter number is written only if it appears as is in a passage read or in the section returned, never as a reconstructed range (rule in `CLAUDE.md`).

**Organisation context**: short, dated notes about your organisation (roles, forums, flows, dependencies, the Discovery workflow), kept in a context folder outside every repository (`~/PMZilla-Lab/contexte`, its `originaux/` sub-folder opened by you only) and indexed into the private collection `contexte`, embedded on this Mac only. A posture searches it only with `collections ["contexte"]` and only when the request touches one of these subjects; a note frames an answer, never backs a framework claim, and is cited with its date, its nature (`declarative` or `measured`) and its source, flagged when its review date has passed (rule in `CLAUDE.md`). The postures also wake up with the context map, one note of at most 80 lines. `/context` lists the notes and `/context add` drafts one from your text and writes it only after your explicit yes; by hand, `uv run tools/context_lab.py` (`init`, `add`, `check`, `list`, `review`). A note with a personal identifier or a sensitive name is refused. Detail: [installation](docs/pmzilla/installation.md#organisation-context-toolscontext_labpy-context-change-organisation-context).

---

## 6. Watch

The articles from blogs, newsletters and Medium publications that you follow are collected every day, converted to Markdown and indexed in the library's `watch` collection.

- **Sources**: `watch/sources.yaml`, in the repository. Each source has an RSS feed and an `active` setting: `active: true` collects it every day, `active: false` ignores it. The optional `include` and `exclude` lists filter by keywords (title and categories) the publications that are too broad.
- **Reason for a deactivation**: write it in the optional `note:` field of the source (free text). It survives every rewrite of `sources.yaml` by a script, unlike YAML comments, which are lost.
- **Renamed folders (watch, lot 5a)**: `veille/` is now `watch/`, `Veille-Lab/` `Watch-Lab/` (its `veille/` sub-folder `watch/`, `_a-lire.md` `_to-read.md`) and `Veille-Ecartes/` `Watch-Excluded/`. The old names are refused, with a message that gives the current name. You move everything once, in three steps: `uv run tools/migrate_watch.py --dry-run` (counts only, writes nothing), `uv run tools/migrate_watch.py` (verified backup in `~/.pmzilla-lab/sauvegardes/watch-AAAA-MM-JJ/`, then the move; it refuses to migrate without a complete backup and stops if a target folder already holds data), then rerun it (it answers "Rien à faire"). Details and the manual steps (launchd job, index collection name) are in [the installation](docs/pmzilla/installation.md#8-install-the-watch).
- **Extracting sources**: `uv run ~/PMZilla-Lab/watch_lab.py sources --claude-export conversations-000.zip projects-000.zip` reads the links already processed in the SignalPM conversations of the Claude export, deduces the sources from them and looks for their feed. New sources are added with `active: false`: you choose which ones to follow, and the settings of the sources already present are kept.
- **Daily collection**: at 7:10, launchd runs `watch.sh` (job `com.pmzilla.watch`), from the code of the run tree `~/PMZilla-Lab/run` (`tools/run_worktree.sh`), while the content stays in this workspace. If the Mac is asleep at that time, the job starts on wake-up. If the Mac was powered off at that time, the catch-up job (`com.pmzilla.watch-catchup`) runs `watch.sh --catch-up` at login and then every hour; the watch runs at most once a day (a day whose run ended, failed included, is not run again; a day postponed because the database or the network was not up is retried every hour, an interrupted run once), never before 7:10 nor after 22:00 (Europe/Paris), and the record `~/.pmzilla-lab/veille-du-jour.json` says what happened. A forced run is `zsh ~/PMZilla-Lab/watch.sh` in the Terminal. The script collects the new articles, pre-triages them (see below), writes the reading list, then updates the index in the database if Ollama answers, probes the BM25 index (otherwise the pre-triage and the indexing are postponed to the next run; if the pre-triage fails, the reading list is not sorted). Before the collection it checks that the database answers and holds the watch tables (`watch_lab.py check-db --wait`, up to `PMZILLA_WATCH_DB_WAIT` seconds, 120 by default); if not, the day is postponed (no collection, pre-triage, reading list or indexing, retried every hour until 22:00, one notification per day), the step `base de données` is reported and the script exits with code 1. If a step fails (collection, pre-triage, reading list, indexing; `indexation (base injoignable)` when the database does not answer), the log says so on its last line, the script exits with code 1 (the second number in `launchctl list` is then no longer `0`) and a macOS notification names the failed steps; a failure of the dashboard does not count. When Ollama is absent, the run is not a failure (code 0), but a macOS notification warns if the last successful indexing is more than 3 days old (marker: `~/.pmzilla-lab/derniere-indexation`; threshold adjustable with `PMZILLA_INDEXATION_MAX_JOURS`, see [the installation](docs/pmzilla/installation.md#8-install-the-watch)). Each morning `watch.sh` also compares the uv version and the Python version uv picks with those recorded in `~/.pmzilla-lab/`; when one changed, it refills and checks the uv cache offline with a throwaway script, notifies only on failure and never stops the watch (the project Python is fixed by `.python-version`; see [After an update of uv](docs/pmzilla/installation.md#after-an-update-of-uv)). At the end of a scheduled run, one short notification, the morning summary (`tools/morning_summary.py`: the watch of the day, the due reviews, the ready jobs of the queue and the doctor's last check, counts and dates only), is sent once a day; `uv run tools/morning_summary.py` prints it in the Terminal (see [the installation](docs/pmzilla/installation.md#8-install-the-watch)). Log: `~/Library/Logs/pmzilla-watch.log`. The job is installed in [step 8, point 6, of the installation](docs/pmzilla/installation.md#8-install-the-watch).
- **Articles**: one Markdown file per article in `Watch-Lab/watch/` (in the workspace, content excluded from Git). The header holds the title, the link, the author and the publication date.
- **Reading list**: `Watch-Lab/_to-read.md` presents the articles collected over the last few days (`days` in `tri.yaml`). It shows first the 5 to read, with their summary and what they bring you, then the others ranked by relevance, then the compilations, and finally what the filter would set aside, with the reason. It is used to choose the articles to pass to SignalPM.
- **`watch` collection** (named `veille` before the rename: the old name is refused, with a message that gives `watch`): it is queried like a domain, with `search_library` and `collections ["watch"]`. The citation rules are in `CLAUDE.md`: in the text, a short reference (author or site, and date); the answer ends with a "Sources" section that cites each article in full (author or site, title, date, link). An article does not carry the weight of a book. When an article's header has no author, the server returns the site followed by "(auteur non indiqué)" (author not stated): the citation carries the site, never an invented name.
- **Importing your Medium articles**: `uv run ~/PMZilla-Lab/watch_lab.py import-medium medium-export.zip --source medium.com/@<your-user> --author <your-name>` imports your own articles from the Medium export (drafts and short replies excluded, threshold adjustable with `--min-chars`) into `Watch-Lab/own-articles/`. Options: `--source` (the key of the source in `sources.yaml`, default `medium.com/@<your-user>`) and `--collection` (default `own-articles`). A source with `collection: own-articles`, declared in the local layer `watch/sources.local.yaml` (outside Git, next to `sources.yaml`; see the [installation](docs/pmzilla/installation.md#8-install-the-watch)), then stores its new articles there during the daily collection. Run the indexing again after the import (see below).
- **`own-articles` collection**: your published articles, indexed separately and queryable with `collections ["own-articles"]`. These are your positions, not sources: they are cited as "<Your name>, title, date, link", never support a recommendation, and any repetition or contradiction must be flagged and confronted with the books (rule in `CLAUDE.md`). Critic flags a deliverable that merely repeats one of these positions.

- **Cited links**: at collection time, the links present in the body of each article (never the menu or the footer) are recorded in the database (`knowledge.watch_article_links`). They feed the suggested sources. For articles collected before this feature existed: `uv run ~/PMZilla-Lab/watch_lab.py links`, once (unreachable pages are retried at the next run).

### Pre-triage (`watch_triage.py`)

Each collected article receives a relevance score and a judgment, computed locally (Ollama):

- **Relevance**: proximity (bge-m3) to what you have already passed to SignalPM. The reference is made of the SignalPM answers (one per shared link), of the `own-articles` collection (your own articles) and, over time, of the watch articles that you share on Bluesky: the reference follows your interests without intervention. Relevance is a rank out of 100 among all the scored articles, computed on the 3 closest references. **It ranks** the reading list; it decides entry only if you set the optional `relevance_threshold` (below), and then only for the articles collected within the period of the reading list, because a rank moves as the corpus grows.
- **Model judgment** (`gemma4:26b`, adjustable with `model` in `tri.yaml`; the prompts are French or English according to `language`): it is the model that decides entry into the library. Each answer comes with a one-sentence justification that quotes or describes the element of the text. It judges four things:
  - **Within the themes**: does the main subject fall under at least one of the `themes` in `tri.yaml`, even indirectly?
  - **Compilation**: is the bulk of the text a list of content by other authors (link roundup, link newsletter, event program) without sustained argument from the author? Compilations do not replace the original article: they are filed separately in the reading list, to discover sources.
  - **Promotional content**: if you remove the passages that present an offer (book, workshop, webinar, newsletter, tool), is a complete argued article left? If so, the article is not promotional, even with an advertising box at the end. Only announcements and pages presenting an offer are set aside.
  - **Substance grid**: 5 yes/no criteria (central idea, supported claims, own point of view, cited sources, neither promotional nor a generic list). Substance is the number of criteria met out of 5.

  It also writes a two-sentence summary and what the article brings to your themes.

An article enters the library if it is within the themes, is neither a compilation nor promotional content, and reaches `substance_threshold` (and, if it is set, a recent article reaches `relevance_threshold`). Otherwise it is set aside, and the reason is displayed (outside the themes, compilation, promotional content, missing criteria, relevance below the threshold).

- **Observation mode, then filter**: `mode: observation` (initial setting) scores and ranks without removing anything. The reading list shows what the filter would set aside. Switch to `mode: filtre` once the threshold is calibrated: the articles set aside then leave the library, moved to `Watch-Excluded/watch/` (never deleted), and therefore no longer enter the index.
- **Settings**: `watch/tri.yaml`, in the repository: `mode`, `model`, `to_read` (articles highlighted every day), `days` (period of the reading list), `substance_threshold`, `relevance_threshold` (optional, 0 to 100; absent or 0: no relevance filtering), `language` (`fr` or `en`: the prompts that score the articles; absent: `fr`) and `themes` (given to the model). Your Bluesky handle (`bluesky`) goes into `watch/tri.local.yaml`, next to it, ignored by Git and never written by a script (a handle still in `tri.yaml` is refused, with a message that does not show it). The former names `modele`, `a_lire`, `jours` and `seuil_substance` are refused, with the current name in the message.
- **Rescuing**: `uv run ~/PMZilla-Lab/watch_triage.py restore <file.md>` puts an article that was set aside back into the library and protects it from later triages; it enters the index at the next run.

Commands (to run from `~/PMZilla-Lab`, via `uv run watch_triage.py ...`):

| Command | Purpose |
|---|---|
| `references --claude-export conversations-000.zip [projects-000.zip]` | builds the reference for your taste (SignalPM shares and the `own-articles` collection); to rerun from time to time (`--without-own` excludes your own articles) |
| `score [--limit N] [--no-model]` | scores the articles not yet scored |
| `score --rescore` | scores all the articles again, after a change of model or themes |
| `score --rescore --compilations` | rechecks only the articles classified as compilations |
| `score --rescore --promotional` | rechecks only the articles classified as promotional content |
| `score --rescore --max-substance N` | rechecks only the articles scored N or less (to compare two models) |
| `week [--days 7] [--max 40] [--per-run]` | writes `Watch-Lab/_semaine.md`: the inventory of the retained articles published over the period (title, source, link, summary), the starting point of `/watch-digest`. `--per-run` filters on the collection date |
| `shares [--pages 3]` | reads your recent Bluesky posts (`bluesky` in `tri.local.yaml`): a watch article that you shared is marked "partagé" (shared), leaves the "to read" list and joins the relevance reference. Run every morning by `watch.sh` |
| `shadow-backfill [--limit N]` | scores in English (shadow prompts, themes and model) the articles already scored in French, in the library or set aside, and writes only to the shadow table (no French score, threshold, `_to-read.md` or set-aside article changes); run it in your Terminal, never during the morning run (`--limit 0`: all); since the end of lot 5b (10 October) the shadow is disabled, so switch it on again to measure a change of the English prompts, then `shadow-report` |
| `digest` | writes `Watch-Lab/_to-read.md`: the articles to read, the rest ranked by relevance, the compilations, what the filter would set aside or has set aside |
| `calibration [--import [SHEET]]` | refreshes the calibration rows in the database (your stored opinions are kept) and writes `Watch-Lab/_calibration.csv` with the `avis` column pre-filled: fill in the column (`g` = keep, `e` = set aside) on about twenty varied articles, then `calibration --import` stores it (an emptied cell removes the opinion) |
| `thresholds [--save]` | compares your opinions with the possible substance thresholds, then with every pair of substance and relevance thresholds (relevance by steps of 10), and proposes the substance threshold alone and the pair that agrees best with your opinions; flags the articles you want to keep but that a fixed rule (outside the themes, compilation, promotional content) sets aside, and those you want to set aside but that the threshold keeps. `--save` writes the two thresholds of the proposed pair to `tri.yaml` without changing the mode. It reads the opinions stored in the database, never the sheet |
| `apply` | in filter mode only, moves the articles set aside to `Watch-Excluded/` |
| `restore <file.md>` | puts an article that was set aside back into the library |
| `exclude <file.md>` | sets aside by hand a weak article that the model keeps; your decision overrides the model's |
| `suggestions [--min 2] [--max 30] [--reset]` | proposes in `sources.yaml` (with `active: false`) the sources cited by at least 2 retained articles from 2 different sources, or by a compilation, with their feed, the number of citations and examples. Home pages, images, tools, training courses and shops are ignored. `--reset` first removes the suggestions that were never activated |

Recommended order: `references`, `score`, `calibration`, fill in the opinions, `calibration --import`, `thresholds --save`, rescue or set aside the flagged articles, then `mode: filtre`.

The `gemma4:26b` model was chosen after a comparison with `qwen3:30b` on the same articles. Its justifications are more precise (it quotes the text), it keeps the professional terms in English, and it tells weak articles from argued essays better. Allow about 12 seconds per article. After a change of model or themes, rescore everything with `score --rescore`: a calibration does not mix two models.

### Weekly digest (`/watch-digest`)

In a Claude Code session, `/watch-digest` (or `/watch-digest 14` for two weeks) produces the weekly digest of the watch:
- **Themes**: 3 to 5, the ones that come back across several authors, each tied to a posture.
- **For each theme**: what the authors say, with the links and what each idea rests on (data, cases, opinion); convergence or mere echo between authors who cite each other, then divergences; what the library says about it; the repetitions of or contradictions with your positions (the `own-articles` collection, articles read in full, also looking for the article that tests them the most); the questions to ask yourself.
- **At the end of the digest**: the articles to read first, the weak signals, and what Critic challenges. Critic judges a general watch digest (soundness of the findings, use of sources, convergence or echo, treatment of your positions), not its application to a team: that comes afterwards, in a session with a posture.

Claude starts from the inventory prepared locally (`watch_triage.py week`) and reads in detail only the useful passages, through the library, to limit token consumption. Before saving, the command rereads the digest paragraph by paragraph: a dated short reference for any paragraph based on an article, "J'en déduis" (I deduce) or "Hypothèse" (Hypothesis) otherwise, the "Sources" section always last (the open question, if there is one, just before it) with the titles from the inventory. A short reference always names the author or the site, followed by the date, even when it has just been cited (never "sa démonstration" (his demonstration), "du même site" (from the same site), "l'auteur" (the author) alone), and each author or site cited in the text, quotations in quotation marks included, has its line in "Sources", and conversely (rule in `CLAUDE.md`). The result is written to `_bmad-output/pmzilla/veille/synthese-AAAA-MM-JJ.md`: only summaries and links, ready to drop into the PMZilla v1 project of Claude Desktop (work PC). These digests stay local: `.gitignore` excludes them from Git and the command saves nothing in Git. The command is defined in `.claude/commands/watch-digest.md`. Manual launch for now; to be automated once the format is validated.

---

## 7. Starting a session

```bash
cd ~/PMZilla-Lab/workspace
claude
```

Prerequisite: Ollama running, as in [step 2 of the installation](docs/pmzilla/installation.md#2-install-the-tools).

Two ways of working:

- **Let PMZilla route**: ask the question as is. The main session chooses the posture, announces it, then loads it.
  > Our teams rarely keep their Sprint commitments, and the usual answer is to estimate better.
- **Call a posture directly**, for example to resume a topic in progress or to launch an action from its menu:
  > /pmzilla-discovery-bmad
  > HY on the mobile prescription module.

Useful commands:

| Command | Purpose |
|---|---|
| `/journal` | Coaching journal: note a session, review the follow-ups, take stock (see below) |
| `/critic-mirror` | Critic mirror: the objections that come back from one deliverable to the next (see below) |
| `/roundtable` | Roundtable of authors: the books of the library confront each other on a question (see below) |
| `/dependencies` | Reading of the dependency map between teams by the Scaling posture, with a verdict first (see section 4, "Dependency map") |
| `/monthly-flow` | Monthly follow-up of a series' flow, read by Delivery (see section 4, "Flow metrics" and "Monthly run in one command") |
| `/context` | Lists the organisation context notes, or drafts one from your text and writes it only after your explicit yes (see section 5, "Organisation context") |
| `/doctor` | Read-only health check of the lab (`tools/doctor.py`): each check that is not ok, with the commands for you to run |
| `/pilot` | The parallel sessions (worktrees, branches, features, state, finish lock, handoff notes) and what needs you; launches nothing |
| `/mcp` | State of the library server (must be connected, with 7 tools) |
| `/agents` | List of the subagents, including `pmzilla-critic` |
| `/bmad-help` | BMAD help: agents, workflows, Builder |
| `/exit` | Quit the session (the agents' memory is kept) |

**Roundtable**: `/bmad-party-mode` makes several postures debate the same subject. The postures first search the library, then ask the context questions when a necessary element is missing, based on what the search found (a diagnosis requested with its data is not delayed: its questions come at the end of the deliverable, rule in `CLAUDE.md`), each defends its position from the library, then challenges the others'. The remaining disagreements are listed, with no forced consensus summary, and the result can be passed to Critic.
  > /bmad-party-mode with Scaling, Discovery and Delivery on rolling out OKRs in the next cycle. Then pass the result to pmzilla-critic.

**Roundtable of authors** (`/roundtable <question> [| authors to invite]`, defined in `.claude/commands/roundtable.md`). It is no longer the postures that debate but the **books**: the command searches the library (excluding the watch, with a wording that looks for the opposite position), selects three to five authors with different positions and reads their passages. For each one it presents the thesis, the argument, the conditions and a short quotation, then the two or three sharpest disagreements: real disagreement or different contexts, and what would settle them. It ends with the points of agreement, what is "hors bibliothèque" (out of library), questions for a workshop and the angle of an article. An author says only what the passages read say, in the third person, with no imagined dialogue; a reply that transposes is flagged "J'en déduis". Critic checks the attributions, the quotations and the balance of the table. Example: `/roundtable Faut-il estimer ? | Reinertsen, Cagan, Larman` (the question reads "Should we estimate?"). "Garde cette table ronde" (keep this roundtable) writes it to `_bmad-output/pmzilla/table-ronde/AAAA-MM-JJ-<subject>.md`.

**Deliverables**: on request ("garde ce diagnostic", keep this diagnosis), a deliverable is saved to `_bmad-output/pmzilla/AAAA-MM-JJ-subject.md`, with the posture, the request and the sources used.

**Adapting a message to its audience** (`/adapt-message`, defined in `.claude/commands/adapt-message.md`): `/adapt-message _bmad-output/pmzilla/<deliverable>.md` (or a pasted text, followed if needed by the audiences to serve) rewrites a diagnosis for management, the POs and the team. The command first extracts a common base (findings with their strength, figures copied exactly, uncertainties, the request), then writes one version per audience: decision and stakes for management, trade-offs and ranges for the POs, observations on the work system and questions to check together for the team. If the source does not say what you expect from each audience, it asks a single grouped question. Critic then checks that the versions say the same thing (same figures, same limits, no culprit), then a second short pass checks the corrections. Result: the base, the three versions, what Critic flagged and the points not corrected. "Garde ces messages" (keep these messages) writes them to `_bmad-output/pmzilla/messages/AAAA-MM-JJ-<subject>.md` (a folder ignored by Git: team names may stay there), in roles and never in people's names.

**Coaching journal** (`/journal`, defined in `.claude/commands/journal.md`, data in `Journal-Lab/journal.yaml`, outside Git). After each session (workshop, retrospective, coaching, CoP), the journal keeps what was tried, what worked and how you can tell, the promised follow-ups with the role that carries them and a deadline, and if needed an experiment to evaluate later (this is where the hypotheses designed with the Discovery posture go). It contains only roles and scopes, never names, and is modified only through `tools/journal_lab.py`. The first word of the command chooses the mode:

- `/journal add <account of the session>`: fills in the entry, asks a single grouped question if the essentials are missing (scope, finding, deadline of a follow-up), then saves it;
- `/journal follow-ups [scope]` (default mode): overdue follow-ups, then upcoming ones, then experiments whose review is due, with an update of those that are done or abandoned;
- `/journal review [period or scope]`: what was tried and what worked depending on the context, share of follow-ups kept, experiments concluded. With fewer than five sessions on a context, the command says it is too early to draw a rule. Critic checks that each conclusion rests on several sessions and targets no person. "Garde ce bilan" (keep this review) writes it to `Journal-Lab/bilans/`.

The postures run `follow-ups --scope` before preparing a session and propose `/journal add` at the end of the preparation (rule in `CLAUDE.md`). Script commands (`uv run tools/journal_lab.py <command> --help`):

| Command | Purpose |
|---|---|
| `add <file.yaml>` | validates an entry written in a YAML file and adds it to the journal |
| `follow-ups [--scope "…"] [--all]` | open follow-ups and experiments whose review is due; `--all` adds the follow-ups that are done or abandoned |
| `update <identifier> {ouverte,faite,abandonnee,conclue} [--note "…"]` | updates a follow-up or concludes an experiment (`--note` carries the observed result) |
| `review [--since AAAA-MM-JJ] [--scope "…"]` | the material for a review over a period (30 days by default) |

**Critic mirror** (`/critic-mirror`, defined in `.claude/commands/critic-mirror.md`). Critic challenges each deliverable; the mirror looks at **which objections come back**, to fix the flaw at the source rather than deliverable by deliverable. `/critic-mirror` (the current month, or the past month before the 8th; `--since AAAA-MM-JJ --until AAAA-MM-JJ` for another period) runs `uv run tools/critic_mirror.py`, which rereads the deliverables in `_bmad-output/pmzilla/` and extracts from them, without classifying anything, the sections where Critic objects, with their exact number of objections (`--since` alone runs until today; evaluation reports and mirrors are ignored). The command then sorts each objection into one of the eleven categories of the grid printed by `uv run tools/critic_mirror.py --categories` (the only source of the grid: hypothesis taken for a fact, output instead of outcome, assumed maturity, framework forced onto the case, misused source, figures, omitted limit...; `--language fr|en` follows the language of the request), and produces a table, the two or three blind spots that affect at least two deliverables, the evolution since the previous mirror, proposed countermeasures (never applied) and the limits (deliverables without a Critic section, sessions not kept). Under five objections, it says it is too early to speak of recurrence. The mirror is saved to `_bmad-output/pmzilla/miroir/miroir-AAAA-MM.md`; nothing is committed.

---
## 8. Repository layout

```
workspace/
├── README.md                       this file
├── CLAUDE.md                       session instructions: identity, context, routing, rules
├── CHANGELOG.md                    history up to 13 October 2026, frozen (the later history is in the GitHub releases)
├── docker-compose.yml              the PostgreSQL container of the database (see the installation, section 14)
├── openspec/                       specs (specs/), change proposals (changes/), config.yaml; the specs are authoritative for behaviour
├── .pmzilla/                       local context (contexte.md), cases.yaml, remplacements-bmad.tsv (ignored by Git)
├── db/migrations/                  numbered SQL migrations (schemas `knowledge`, `cases`, `flow`, `quality`; applied by `tools/db.py`)
├── edition/                        manifest.yaml (classifies every tracked file: include, exclude with a reason, template) and templates/ (neutral files that replace private ones), read by tools/build_edition.py; never shipped in the edition
├── .claude/
│   ├── agents/
│   │   ├── pmzilla-critic.md       Critic sub-agent
│   │   └── spec-writer.md          sub-agent that writes the OpenSpec specs (never code)
│   ├── commands/
│   │   ├── watch-digest.md         /watch-digest command
│   │   ├── monthly-flow.md         /monthly-flow command: monthly follow-up of a series' flow, interpreted by Delivery (Scaling first for a product series)
│   │   ├── adapt-message.md        /adapt-message command: a diagnostic rewritten for three audiences, checked by Critic
│   │   ├── journal.md              /journal command: session notes, promised follow-ups, review
│   │   ├── critic-mirror.md        /critic-mirror command: the Critic objections that come back from one deliverable to the next
│   │   ├── roundtable.md           /roundtable command: the library's authors confront each other on a question
│   │   ├── dependencies.md         /dependencies command: the dependency map between teams read by Scaling, checked by Critic
│   │   ├── audit.md                /audit command: read-only repository audit (end-of-session check, or `complet`)
│   │   ├── implement.md            /implement command: an OpenSpec change implemented task by task on its own branch (no push, no merge)
│   │   ├── close.md                /close command: closes a change (ticks, status document, archive, queue job), prints the finishing command
│   │   ├── add-books.md            /add-books command: classification, exclusions and catalogue of new books from their file names; prints the commands, runs none
│   │   ├── next.md                 /next command: the jobs of the work queue that fit the time you have
│   │   ├── start.md                /start command: starts one job of the queue on its branch, marks it done, prints the finishing command
│   │   ├── batch.md                /batch command: one worktree and one printed launch per independent ready feature of a milestone (starts no session)
│   │   ├── pilot.md                /pilot command: the parallel sessions (worktrees, branches, features, state, finish lock, handoff notes) and what needs you; launches nothing
│   │   ├── context.md              /context command: lists the organisation context notes, or drafts one and writes it only after your explicit yes
│   │   ├── doctor.md               /doctor command: runs the read-only health check (tools/doctor.py) and gives the commands for you to run
│   │   └── update-readme.md        /update-readme command: README and installation.md aligned with the repository and the scripts, then commit
│   ├── settings.json               deny rules: reading of books, articles, the six protected paths of Flux-Lab (Jira exports, history, tables, the former teams table, the organization reference, noms-sensibles.txt) and the team catalogue; the database tables of the flow and quality schemas; actual launch of the commands that contact Jira or read the database, of the finishing scripts and of the off-site backup; writes to GitHub outside tools/gh_issue.py
│   └── skills/
│       ├── pmzilla-discovery-bmad/ BMAD agent: SKILL.md, references/ (one sheet per action, loaded by the posture; the local sanctum copy in _bmad/memory/<agent>/references/ is refreshed by `tools/sanctum_refresh.py`; a test checks that a new sanctum reproduces these sheets), customize.toml
│       ├── pmzilla-delivery-bmad/
│       ├── pmzilla-scaling-bmad/
│       ├── pmzilla-facilitation-bmad/
│       └── bmad-*/                 skills supplied by BMAD
├── _bmad/                          BMAD installation (core, method, builder) and customizations
├── Bibliotheque-MD/                books in Markdown                           (content excluded from Git)
├── Bibliotheque-Lab/               books sorted by domain, by sort_by_domain (content excluded from Git)
├── Watch-Lab/                     watch/, own-articles/, _to-read.md, _semaine.md  (content excluded from Git)
├── Watch-Excluded/                 articles rejected by the filter             (content excluded from Git)
├── Flux-Lab/                       exports/ (no longer written: CSV files left, deleted by the retention tool), rapports/ (aggregates, changes), tableaux/ (HTML dashboards, Aging WIP points), flux.yaml (content excluded from Git)
├── Journal-Lab/                    journal.yaml, bilans/: coaching journal (content excluded from Git)
├── _bmad-output/                   agent deliverables, watch digests (pmzilla/veille/, outside Git), adapted messages (pmzilla/messages/, outside Git), Critic mirrors (pmzilla/miroir/), dependency readings (pmzilla/dependances/, outside Git), flow diagnostics (pmzilla/flux/, outside Git), evaluation reports (essais/, outside Git)
├── tools/                          single source of all the scripts (flux_jira.py, dependencies_jira.py, history_jira.py, export_jira_api.py, flow_monthly.py, flow_views.py, flow_retention.py, epic_statuses.py, segment_sample.py, history_common.py, mapping_lab.py, caption_diagnostic.py, sorting_exclusions.py, journal_lab.py, critic_mirror.py, dashboard.py, library and watch scripts), run from here; install_links.sh (links from ~/PMZilla-Lab/); watch launchd task,
│                                   book_catalog.yaml (book titles and authors, read at indexing time),
│                                   evals_auto.sh (evaluation set, then README with --readme, on demand) and hooks/post-commit (runs nothing without PMZILLA_AFTER_COMMIT),
│                                   hooks/pre-commit (name safety net, reads Flux-Lab/noms-sensibles.txt; also refuses a commit whose index has no green run: a complete one on `main`, a complete or targeted one (`tests/run_all.sh --staged`) on a work branch), hooks/pre-push (a push of `main` needs a complete green run of the pushed tree) and hooks/commit-msg (refuses a message that carries a personal identifier or a sensitive name), hooks/pre-merge-commit (refuses a merge commit) and hooks/reference-transaction (refuses a move of `main` outside the finishing lock): the six hooks, installed by install_hooks.sh,
│                                   finish_branch.sh (merges, pushes and deletes a finished work branch after its checks; run in your Terminal), finish_worktree.sh (removes the worktree of a batch branch, then runs finish_branch.sh from the workspace; run in your Terminal), select_suites.py (suites to run for the staged files),
│                                   install_lab.sh (zsh bootstrap of the install script: platform, Homebrew, Git and uv confirmed, clone) and install_lab.py (Python orchestrator, standard library only,
│                                   fresh mode, steps prereqs, repo, hooks, links, database, launchd, mcp, check) with its modules install_lab_context, _prereqs, _repo, _database, _launchd, _mcp, _check,
│                                   build_edition.py (English edition generator: `uv run tools/build_edition.py --language en --output <dir>`; private tooling, excluded from the edition),
│                                   roadmap.py (reader of the work queue, the issues of the private GitHub repository: check, next, batch, show, status, board, reminder, release-notes), gh_issue.py (the only write path to GitHub),
│                                   worktree.sh (creates the worktree of a branch in the worktrees folder), run_worktree.sh (creates and updates the run tree `~/PMZilla-Lab/run`, whose code the scheduled jobs run),
│                                   publish_edition.py (prepares the permanent local copy of the public repository for a publication; never commits nor pushes),
│                                   db_backup.sh (daily database backup), db_restore_test.sh (restore test in a throwaway container), offsite_backup.sh with the two com.pmzilla.offsite-*.plist templates (off-site copy to an encrypted disk),
│                                   dashboard.py (local HTML page showing the state of the Lab), flow_board.py with flow_board_page.html, .css and .js (visual flow dashboard), flow_glossary.py (definitions in French and in English),
│                                   vendor/ (Apache ECharts, installed by telecharger_echarts.sh: library, license, fingerprint)
├── tests/
│   ├── postures/
│   │   ├── cas.yaml                evaluation set of the postures: reference questions and checks
│   │   ├── cas-commandes.yaml      cases of the slash commands, replayed apart (`--cases-file`), on invented data (fixtures/)
│   │   └── memoire/                frozen memory of the postures (neutral MEMORY.md and BOND.md; the English ones are in en/) for comparable runs
│   ├── flux_jira/                  tests of flux_jira.py on synthetic exports, with a reference report
│   ├── dependencies_jira/           tests of dependencies_jira.py: fixtures through a test-only loader, link direction, scope, exclusions, old Epics
│   ├── flow_board/               tests of the visual dashboard: standalone file, anonymization, English, JavaScript under Node, actual ECharts rendering
│   ├── watch_triage/ pmzilla_lab_library/ watch_lab/ watch_sh/   tests of the watch and the library: made-up articles, books, feeds and pages, fake `uv` and `curl`
│   ├── convert_books/ sort_by_domain/                            tests of the conversion (tiny EPUBs and PDFs) and of the sorting by domain
│   ├── journal_lab/ critic_mirror/ posture_evals/ run_all/       tests of the journal, of the Critic mirror, of the local logic of the evaluation set and of the launcher
│   ├── segment_sample/        tests of segment_sample.py: fixtures through a test-only loader, parity with the flux_jira.py computation, reproducible draw
│   ├── references_postures/        fails if a new sanctum, created by `init-sanctum.py`, does not reproduce the references of the skill, or if Git tracks the sanctum
│   ├── run_all.sh                  runs all the suites at once (see "Running all the tests")
│   ├── install_lab/                tests of the install script: the real bootstrap and orchestrator, each step, in a fake home and repository with fake commands on the PATH (no real change to the machine)
│   ├── build_edition/              tests of the edition generator and of the manifest (classification, templates, forbidden content, publication check); excluded from the edition
│   ├── installation/               test_install_links.sh (symbolic links, in a fake home folder) and test_install_hooks.sh (Git hooks, in a temporary repository)
│   ├── history_jira/            tests of history_jira.py: fake HTTP server, made-up data, fake token
│   ├── export_jira_api/            tests of export_jira_api.py: fake HTTP server, made-up data, in-memory raw layer
│   ├── hooks/                      test_pre_commit.sh (name safety net, temporary repository) and test_post_commit.sh (the hook runs nothing without PMZILLA_AFTER_COMMIT, fake HOME), test_pre_commit_green.sh (green-run check by branch) and test_pre_push.sh
│   ├── evals_auto/                 test_evals_auto.sh: evaluation set and --readme with fake uv, claude, curl and osascript, refusal if the README has uncommitted changes
│   ├── dashboard/            tests of the dashboard, on fictional data
│   ├── select_suites/ roadmap/ workflow_commands/ finish_branch/ finish_worktree/  tests of the suite selector, of the queue reader, of the headers and bodies of the workflow commands and of the finishing scripts
│   └── (others)              one suite per script: db, db_scripts, offsite_backup, flow_import, flow_store, flow_views, flow_compare, flow_monthly, flow_retention, epic_statuses, gh_issue, flux_config, settings_deny, script_dependencies… (`bash tests/run_all.sh` lists them)
├── watch/
│   ├── sources.yaml                watch sources: active: true to follow them
│   ├── sources.local.yaml          local additions to the watch sources (ignored by Git)
│   ├── tri.yaml                    pre-triage settings: mode, model, language, thresholds, themes
│   └── tri.local.yaml              your Bluesky handle (ignored by Git)
└── docs/pmzilla/
    ├── postures/                   brief of each posture: framework, refusals, references, menu
    ├── application.md              design of the application: why, lots, state
    ├── architecture.md             architecture of the lab: components, data flows, database, security, tests
    ├── version-anglaise.md         English version of the documentation
    ├── watch-prompts-en-correspondance.md   correspondence between the French and English pre-triage prompts
    ├── bibliotheque-lacunes.md     references missing from the library, to acquire
    ├── etudes/                     studies kept for the record
    ├── installation.md             step-by-step installation, Jira procedures (flow, API, dependencies), adding a book, check
    └── archives/                   replaced documents, kept for the record
```

The agents' `customize.toml` files are regenerated by BMAD on every update: lasting customizations go in `_bmad/custom/`.

Outside the repository, on the Mac (the scripts in `~/PMZilla-Lab/` are symbolic links to `workspace/tools/`, created by `tools/install_links.sh`: `tools/` is the only source, there is no copy to redo):

```
~/PMZilla-Lab/
├── convert_books.py, sort_by_domain.py     links: conversion and sorting of the books
├── mapping_lab.py                                         link: MAPPING table shared by convert_books.py and sort_by_domain.py
├── pmzilla_lab_library.py                                 link: MCP server and indexing
├── watch_lab.py, watch_triage.py                           links: watch sources, collection and pre-triage
├── watch.sh                                              link: daily run launched by launchd
├── posture_evals.py                                      link: evaluation set of the postures
├── flux_jira.py                                        link: flow metrics
├── copies-avant-liens-AAAA-MM-JJ-HHMMSS/                  old copies, put away by install_links.sh
└── tableau-de-bord.html                                   page generated by tools/dashboard.py
~/Downloads/Livres - Ressources/    original books (PDF and EPUB)
~/.pmzilla-lab/                     library_parity_snapshot.json (snapshot of the search results, `tools/library_parity.py record`), sauvegardes/ (PostgreSQL dumps), offsite/ (configuration of the off-site disk, status and monthly restore-test reports), essais/ (traces of the evaluation set); the PostgreSQL data live in the Docker volume `pgdata` (Colima)
```

The `Bibliotheque-MD`, `Bibliotheque-Lab`, `Watch-Lab` and `Watch-Excluded` folders are in the workspace to keep everything together, but `.gitignore` excludes their content: only an empty `.gitkeep` file is tracked, so that the folders exist in the repository. Books and articles never go to GitHub: they are copyrighted content, and their volume exceeds what GitHub accepts. `.claude/settings.json` also forbids Claude Code from reading them directly: it goes through the library, which returns only passages.

`Flux-Lab` and `Journal-Lab` follow the same rule: `.gitignore` excludes their content, except an empty `.gitkeep`. `.claude/settings.json` forbids reading `Flux-Lab/exports/` (the Jira exports carry ticket titles), `Flux-Lab/historique/`, `Flux-Lab/tableaux/`, `Flux-Lab/equipes-assets.yaml`, `Flux-Lab/organisation.yaml` and `Flux-Lab/noms-sensibles.txt` (six protected paths), as well as the team catalogue `Flux-Lab/equipes-jira.yaml`, but not `Flux-Lab/rapports/` or `Flux-Lab/flux.yaml`, which contain only aggregates and settings. Likewise, `.gitignore` excludes from Git the dependency readings (`_bmad-output/pmzilla/dependances/`) and the flow diagnostics that are kept (`_bmad-output/pmzilla/flux/`), which carry team names, as well as the watch digests.

The postures' sanctum (`_bmad/memory/`) is not in this tree because Git does not track it: it is local and ignored, created at the first session of each posture, backed up by `bash tools/sauvegarde_sanctum.sh`, and brought up to date from the skills' templates by `python3 tools/sanctum_refresh.py`, which rewrites only `CREED.md`, `CAPABILITIES.md`, `references/` and `scripts/` and never touches its memory (`MEMORY.md`, `BOND.md`, `PERSONA.md`, `INDEX.md`, `sessions/`). The user's personal context is in `.pmzilla/contexte.md` (local, ignored by Git), imported by `CLAUDE.md`; the neutral template is `tests/postures/contexte-neutre.md`.

---

## 9. Maintenance

### Adding a book

The procedure (audit of the batch, EPUB preferred over PDF, translations and double formats not indexed, catalog filled in from the copyright page, moving `Bibliotheque-Lab` in a normal Terminal) is in [docs/pmzilla/installation.md](docs/pmzilla/installation.md#12-add-a-book).

### Checking the repository for personal data and the out-of-library list

- `uv run tools/outside_library.py <delivery|discovery|scaling|facilitation|toutes>` lists, for a posture, the references its rules cite that are not in your catalog (`tools/book_catalog.yaml`): these are the ones to mark "outside the library".
- `python3 tools/identifiants_personnels.py` looks, in the files tracked by Git, for the author's user name and absolute paths (condition for publishing the English edition; the postures' sanctums are checked from the skills' templates).

### Adding or changing a posture

1. Write or change its brief in `docs/pmzilla/postures/`.
2. Generate the agent with the BMad Agent Builder (code **BA**), as type `memory`, modeled on `pmzilla-discovery-bmad`.
3. Check `agent_type = "memory"` in its `customize.toml`.
4. Run its first session and check that it wakes up with its memory (`MODE: WAKING`). Its sanctum (`_bmad/memory/`) is local and not tracked by Git, so there is nothing to commit: back it up with `bash tools/sauvegarde_sanctum.sh`. See [step 7 of the installation](docs/pmzilla/installation.md#7-bring-the-postures-to-life), with the name of the new posture in place of the four existing ones.
5. Update the postures table in `CLAUDE.md`, add at least one case to `tests/postures/cas.yaml`, then replay the evaluation set.

### Updating the repository

Commit what you changed (targeted `git add`; the `pre-commit` hook checks the sensitive names and the green run of the index, see "Working on the repository" below), then push only when you have decided to: `git push`.

The deliverables, the watch settings and the scripts (`tools/`) are tracked by Git. The agents' memory is not: it stays local (see section 8). The scripts are edited in `tools/`: the links in `~/PMZilla-Lab/` follow, there is nothing to copy.

### Working on the repository

Frame and specify an OpenSpec change on Opus, then `/model sonnet` to execute. OpenSpec is for behaviour, postures, `CLAUDE.md` and publication; a direct prompt is for maintenance. Six commands carry the work, and none of them pushes or merges:

- `/implement <change>` implements the tasks of an OpenSpec change on a branch ending with its name, tests first, one commit per group after a green `bash tests/run_all.sh --staged`; it hands over every step reserved to you (real Jira, imports, database scripts, evaluation set).
- `/close <change>` ticks the covered tasks, updates the status document, archives the change, marks its job `done` in the work queue and prints the finishing command.
- `/add-books <files>` prepares the classification, the exclusions and the catalogue entries of new books from their file names, then prints the conversion, sort, indexing and probe commands in order; you run them.
- `/next <duration> [mothra|pmzilla]` proposes the jobs of the work queue (the GitHub issues of the private repository, read by `tools/roadmap.py`) that fit the time you have; Mothra items carry the label `product:mothra`, no `product:` label means PMZilla (`docs/pmzilla/installation.md`, "The work queue on GitHub"). Every write to the queue goes through `uv run tools/gh_issue.py <subcommand>` (never a direct `gh` command), and no name or ticket key enters an issue (rules in `CLAUDE.md`).
- `/start <id>` starts one job of the queue: checks that it is ready, creates its branch, does it (direct prompt, or `/implement` for an OpenSpec change), marks it `done` on the branch and prints `bash tools/finish_branch.sh`. Opened by `/batch` on an `In progress` feature, it resumes on the branch the batch named, creates no branch, does not set the Status again and prints `bash tools/finish_worktree.sh <branch>` instead.
- `/batch <milestone>` prepares a milestone for parallel work: it reads the independent `Ready` features of the milestone, sets aside those that share files with a retained one, asks one yes, then creates one worktree per kept feature, sets it `In progress` and prints, per feature, the `cd <folder> && claude --model <alias> "<prompt>"` line and the `bash tools/finish_worktree.sh <branch>` line. It starts no session and finishes nothing.

For parallel work, `bash tools/worktree.sh <branch> [<folder>]` creates the worktree of a branch in the worktrees folder of the lab folder (`worktrees/`, or `PMZILLA_LAB_WORKTREES`) and gives its session the path of the sensitive-names list (exit codes: 0 created; 2 usage; 3 list missing; 4 folder exists or branch open elsewhere; 5 Git failed or the worktrees folder cannot be created). To finish a batch branch from the workspace, type `bash tools/finish_worktree.sh <branch>`: it checks, removes the worktree, switches the workspace to the branch and runs `tools/finish_branch.sh`, returning its code (own codes 20 to 50, 39, 43 and 47 never returned; 0 to 13, 17 and 18 come from `finish_branch.sh`; the header of the script gives the table).

To finish a branch, type in your Terminal `bash tools/finish_branch.sh`: it checks (clean tree, change archived, validating evaluation run when the instructions or postures changed, `main` up to date, complete green run), merges into `main`, pushes and deletes the branch, with one exit code per refusal. On `main`, a push needs a complete green run of the pushed tree (`pre-push` hook). Detail, exit codes and the uv cache procedure: [installation](docs/pmzilla/installation.md#16-working-on-the-repository).

### Backing up the database

- `bash tools/db_backup.sh` writes one `pg_dump` per schema (`knowledge`, `cases`, `flow`), plus the partial dump `quality-sans-texte.dump` (team attributes, team reviews and overlay versions of `quality`, never a story text), to `~/.pmzilla-lab/sauvegardes/db-AAAA-MM-JJ/`, keeps the 14 newest folders and never overwrites the one of the day. launchd runs it every day at 7:45 (`tools/com.pmzilla.db-backup.plist`). Exit codes: 0 done or already present; 1 partial or empty backup; 2 invalid environment or argument.
- `bash tools/db_restore_test.sh [--backup <folder>] [--detail] [--port N]` restores the latest backup into a throwaway container (same image and `shm_size` as `docker-compose.yml`), empties each schema before `pg_restore`, compares row counts and the migration fingerprint with the real database (counts only) and removes the container. To run once a quarter. Exit codes: 0 consistent; 1 restore failed, table missing or fingerprint different; 2 prerequisite missing.
- `bash tools/offsite_backup.sh <setup <mount point>|copy [--include-protected]|restore-test [--force] [--detail]|status>` copies the newest database and sanctum backups to one encrypted external disk and tests that copy every month. Exit codes: 0 done, already present or test not due; 1 failure; 2 usage or environment refused (unencrypted, internal or network volume, synced folder, Git work tree); 3 deferred (disk absent or locked, real database stopped). It never reads or stores the disk password. Disk setup, the two launchd templates and the flow dump removal on old copies: [installation](docs/pmzilla/installation.md#147-off-site-backup-encrypted-external-disk). Restore and quarterly test: [installation](docs/pmzilla/installation.md#142-restore-the-database-and-test-the-restore-every-quarter).

Claude Code cannot run these scripts (`deny` rules): you type them in your Terminal.

### Auditing the repository

`/audit` (defined in `.claude/commands/audit.md`) checks the repository without changing anything: the state for the night, OpenSpec changes not archived, documentation against the recent commits and any change to the frozen CHANGELOG, books without a complete catalogue entry (names compared after Unicode normalization), the personal-identifier scanner and leftover backup files. `/audit complet` adds parallel agents by domain and a cleanup plan. It writes only `.pmzilla/audit/YYYY-MM-DD.md`; you choose which findings to handle.

### Generating the English edition

`uv run tools/build_edition.py --language en --output <dir>` writes a shareable English tree of the committed state (`HEAD` by default, `--commit <rev>` for another one) in a new folder outside the workspace, from the Git objects only. `edition/manifest.yaml` classifies every tracked file (include, exclude with a reason, or replaced whole by a neutral file from `edition/templates/`); a tracked file without a rule stops the build. The tree is checked for personal identifiers and sensitive names before it gets its final name (`<dir>.not-publishable` otherwise); `--run-tests` also runs the test suites in a throwaway copy. The generator never creates a repository, never pushes and makes no network call, and the private tooling (the generator, `edition/`, `tests/build_edition/`) stays out of the edition. Exit codes and detail: [installation](docs/pmzilla/installation.md#generating-the-english-edition-toolsbuild_editionpy).

### Checking the postures after a change

**On demand, after a commit.** The Git `post-commit` hook no longer runs anything by itself (since 2026-10-07: the cost of a full evaluation set on every commit, and a `claude -p` session that committed the README while another session was working on the repository). Two commands, to run when you want (with Ollama running, about $3 for the full set):

- `tools/evals_auto.sh`: replays the 13 cases on the committed state (the report stays local, outside Git), then regenerates the dashboard and notifies the result;
- `tools/evals_auto.sh --readme`: in addition, runs `/update-readme` unattended (it commits only `README.md` and `docs/pmzilla/installation.md`, and only if there is a gap); the commit stays local, nothing is pushed (your branch finish pushes). Refused, with a message, if one of these two files has uncommitted changes: the session would commit them along with the rest.

**To have the hook run it after a commit**, ask for it explicitly: `PMZILLA_AFTER_COMMIT=evals git commit ...` (evaluation set only) or `PMZILLA_AFTER_COMMIT=all git commit ...` (evaluation set, then README), only if the commit touches `CLAUDE.md`, a posture (`.claude/skills/pmzilla-*`), an agent, a command, `tests/postures/cas.yaml`, `tests/postures/vocabulaire.yaml`, the frozen memory (`tests/postures/memoire/`) or `tools/pmzilla_lab_library.py`. The commit returns immediately; only one run at a time (a second launch during a run triggers another one at the end). Log: `~/Library/Logs/pmzilla-essai.log`. `PMZILLA_NO_EVALS=1` overrides everything. The former names `PMZILLA_APRES_COMMIT` (values `essai` and `tout`) and `PMZILLA_SANS_ESSAI` are refused: the hook prints a message that gives the current name, adds it to its log and runs nothing.

- Installing the hooks, once: `bash tools/install_hooks.sh` from the workspace (links the six hooks `pre-commit`, `post-commit`, `commit-msg`, `pre-push`, `pre-merge-commit` and `reference-transaction`; `commit-msg` and `pre-push` also check the names in commit messages, with `tools/commit_names_scan.py`; `--verify` reports their state; the `post-commit` hook does nothing without `PMZILLA_AFTER_COMMIT`). The `pre-commit` hook refuses a commit unless a run has just passed on the staged index (after `git add`): `bash tests/run_all.sh` in full on `main`, in full or `bash tests/run_all.sh --staged` on a work branch.
- If Ollama does not answer, the run is postponed (notification): rerun `tools/evals_auto.sh`.

**By hand**, for example before committing (with Ollama running), from the workspace (`cd ~/PMZilla-Lab/workspace`):

```bash
uv run tools/posture_evals.py                       # the 13 cases
uv run tools/posture_evals.py --cases veille-goulot   # one or more cases, separated by commas
```

- **Cases**: `tests/postures/cas.yaml`. Each case gives a question, the expected posture, automatic checks (call to `search_library` and collections, call to Critic, the "hors bibliothèque" (out of library) mention, no person's name in the files written) and criteria judged by Claude with a justification (context questions, refusals, citations). A case that cannot be run here (a missing prerequisite) is reported as non évaluable (not evaluable): the run is then non-validating and exits with code 3, since the expected total of 38 blocking checks was not played in full.
- **Isolation**: each case runs in a temporary copy of the workspace (`git worktree`), uncommitted changes included, deleted afterwards. The agents' real memory is never touched.
- **Frozen memory**: in the copy, each posture's accumulated experience (`MEMORY.md`, `BOND.md`, `sessions/`) is replaced by the neutral version from `tests/postures/memoire/<posture>/`, while the structure (identity, capabilities, references) stays that of the tested state. Two runs can thus be compared without the accumulated experience of a posture making the result vary. The report states "mémoire : figée" (memory: frozen) or "mémoire : réelle" (memory: real).
- **Report**: `_bmad-output/essais/essai-AAAA-MM-JJ-HHMMSS.md`, with the regressions against the previous run at the top. The `_bmad-output/essais/` folder is outside Git (`.gitignore`): the reports may contain book excerpts. It contains only the verdicts and their justifications; the raw traces stay in `~/.pmzilla-lab/essais/`.
- **Options**: `--model` and `--judge-model` to change the models (rule: sessions use the model of Claude Code, the judge is Sonnet, `spec-writer` is Opus, Critic inherits the model of the session; effect on validity and records: "Model choice" in the [installation](docs/pmzilla/installation.md)), `--keep` to inspect the copies, `--real-memory` to test with the postures' real memory instead of the frozen memory, `--committed-state` to test the last commit without the changes in progress, `--tools AAAA-MM-JJ-HHMMSS` to list the tools called by each session of a run (with the output of the Bash commands), `--with-bash` if the report says that Bash was refused during a session, `--cases-file tests/postures/cas-commandes.yaml` to replay the cases of the slash commands (`/monthly-flow`, `/watch-digest`) apart from the main set: they run on invented files and a throwaway library (`files` and `library` fields), are reported separately and are not counted in the 38, `--rejudge AAAA-MM-JJ-HHMMSS` to replay the checks and the judge on the traces of a previous run, without a new session (after a change to `cas.yaml`). A verification rule of `cases.yaml` can carry `non_blocking: true`: it is then an indicator, reported apart ("Indicateurs non bloquants") and left out of the total and of the regressions. The rules `ends_with_sources`, `dates_in_sources` and `sources_cited` check the structure of an answer that cites watch articles (see `tests/postures/cas.yaml`). `--retries N` (default 2, 0 to disable) replays a case with a failing blocking check: it is reported "instable" (counted as passed) if it passes all the replays, a confirmed failure otherwise (beyond `--max-retried-cases`, default 3, failing cases, nothing is replayed; the cost of the replays is shown in the report and on the `BILAN` line; "instable répété" flags a case unstable in two complete passes in a row); the judge reads every message of the last exchange, and the non-blocking indicator "Un seul message final" flags a final answer split in several messages (`uv run tools/final_messages_check.py` counts them on the kept traces, with no model call), `--language fr|en` chooses the language of the cases (French by default, so a run without the option behaves as before): in English the evaluation set replays only the cases that have an `en:` block (`question`, `judgements`, `text`) and lists the others; the formulas it recognizes in each language (posture tag `[Posture : X]` in French and `[Posture: X]` in English, out-of-library mention, Critic titles) are in `tests/postures/vocabulaire.yaml`, and an answer that carries the tag of the other language fails the posture check. The former French names of these options (`--cas`, `--modele`, `--juge-modele`, `--garder`, `--memoire-reelle`, `--rejuger`, `--outils`, `--etat-commite`, `--avec-bash`) are refused, with a message that gives the current name.
- **Cost**: one Claude Code session per case, plus one judgment. To run after a change, not every day.

### Running all the tests

`bash tests/run_all.sh` runs all the Python suites at once (`uv run … python -m unittest`, one per `tests/` folder that contains `test_*.py`) and then the shell tests (name hook, post-commit hook, evals_auto.sh, links), prints one line per suite, the total (`TOTAL : N tests dans M suites · tous réussis`, that is, "TOTAL: N tests in M suites, all passed") and exits with code 1 if a suite fails (2 if no suite is found), showing the end of the output of the failing suites. `bash tests/run_all.sh --staged` runs only the suites that the staged files call for (`tools/select_suites.py` chooses them; a file that no suite names, or a change to `CLAUDE.md`, the settings, the runner or the hooks, makes it a complete run); `bash tests/run_all.sh watch_lab hooks` runs only the named suites; `-v` also prints the full output. `--portable` runs only the suites that are not listed in `tests/suites_mac.txt` and `--mac` only those that are (they do not combine). The local CI runs the portable suites in a throwaway container with no network: `bash tools/ci_local.sh run [<branch>]` is run by the session, while `build` (image, with network) and `up` (Colima, Docker, image, then `run`) are run by you in your Terminal. No network or paid call, nothing is written outside temporary folders; `uv` downloads the test libraries on first run, then keeps them in cache. The suites that need a PostgreSQL database (`db`, `flow_import`, `flow_store`, `flow_views`, `hybrid_search`, `pmzilla_lab_library`, `library_backend`, `cases_store`, `watch_store`, `book_usage`, `dashboard`, `flow_retention`, `posture_evals`, `export_jira_api`, `history_jira`, `story_quality`) run on a throwaway container with `bash tools/dbtest.sh [suite...] [--port N]`, typed by you in your Terminal (Claude Code is not allowed to run it): [installation](docs/pmzilla/installation.md#145-suites-with-a-throwaway-database).

### Viewing the dashboard

`uv run tools/dashboard.py --open` writes a standalone HTML page (inline CSS and curves, no JavaScript, no network call) to `~/PMZilla-Lab/tableau-de-bord.html` and opens it in the browser; `--output PATH` chooses another file. It is also regenerated every morning by `watch.sh` and after each automatic run of the evaluation set (`evals_auto.sh`): its failure never makes the watch or the evaluation run fail.

Six sections: **À faire** (to do: late or upcoming follow-ups and experiments whose review is due, from the journal), **Veille** (watch: articles per day, sources in error, pre-triage duration, share of the shared articles proposed in the "à lire" (to read) list), **Bibliothèque** (library: books by domain, books without an author, missing books to download again), **Qualité** (quality: history and state of each case of the evaluation set), **Flux** (flow: latest changes from `Flux-Lab/rapports/`) and **Critic** (this month's objections and the latest mirror). The page includes only counts, dates, source names, book titles and texts written by the user (journal, mirror): never the content or the title of an article, never a book excerpt. A missing data source shows "pas encore de données" (no data yet). Tests, on fictional data: `uv run --with pyyaml python -m unittest discover -s tests/dashboard -v`.

### Updating BMAD

```bash
cd ~/PMZilla-Lab/workspace && npx bmad-method install
```

In the installer's lists, tick with the **space bar** before confirming with Enter. Make a commit first, so that you can go back.

### Troubleshooting

| Symptom | Likely cause |
|---|---|
| `pmzilla-library` missing or disconnected in `/mcp` | Ollama closed, or script path changed: `claude mcp get pmzilla-library` |
| No citation in the answers | The server does not answer: test `search_library` by hand in a session |
| `Unknown collections` | Wrong domain name: `produit`, `flow`, `organisation`, `facilitation`, `tech`, `watch`, `own-articles` (your personal collection of published articles) |
| An agent no longer remembers | Run the agent's `wake.py` ([step 7 of the installation](docs/pmzilla/installation.md#7-bring-the-postures-to-life)): `FIRST_BREATH` means its memory was never created, so run its first session. Otherwise, check its `agent_type` and that the session is launched from `workspace` |
| A posture does not appear | The agent must be in `.claude/skills/`, not in `skills/` |
| An agent reads the files of `Watch-Lab` or of the libraries instead of searching | Check the `deny` rules of `.claude/settings.json` and recall the rule in `CLAUDE.md`: the watch is queried with `search_library` and `collections ["watch"]` |
| `git status` shows books or articles | The lines for the content folders are missing in `.gitignore`: commit nothing, restore them first |
| `Bootstrap failed: 5: Input/output error` when installing a launchd task | File quarantined after download: `xattr -c` on the plist and the script, then rerun |
| `could not resize shared memory segment` while migrating the database or in the restore test | The container's `/dev/shm` is too small (64 MB by default). `docker-compose.yml` sets `shm_size`, and the throwaway containers of `db_restore_test.sh` and `dbtest.sh` read it from that file (1g if absent): run `bash tools/db_up.sh` to recreate the real container, then migrate again |
| `db_restore_test.sh` ends with `cannot drop schema … because other objects depend on it`, or with `MANQUE` for a `knowledge` table | The backup predates a migration that added tables. The script now empties each schema of the throwaway container before restoring; a `MANQUE` that remains is a real gap (a table of the real database is missing from the backup): take a fresh backup with `bash tools/db_backup.sh`, then repeat the test |
| `offsite_backup.sh` answers `disque absent ou verrouillé : copie reportée` (exit code 3) | The encrypted disk is unplugged or locked: plug it in and unlock it, the job retries at the next mount. After 7 days without a copy, a macOS notification warns you |
| `flow_monthly.py` exits with code 5 | This month's run is already complete: `--force` to run again, or `--from <step>` after a failure (the failing step prints the resume command) |
| A tool run from a Claude Code session refuses to start (exit code 3) | The Jira, database and monthly tools check the `CLAUDECODE` variable and the `deny` rules: type them yourself in a Terminal started from the Dock or Spotlight, not from a Claude Code session |
| A source with `ERREUR 403` in `_rapport_collecte.txt` | The site blocks scripts, sometimes temporarily. If the error lasts several days, set the source to `active: false` |
| `NON NOTÉ` (not scored) during pre-triage | The model did not answer in time or returned an incomplete answer: the article is picked up again on the next run |
| Pre-triage seems stuck | Check with `ollama ps` that the model runs on the GPU; after 3 minutes, the article is abandoned and picked up again later |
| A citation gives a range of chapters ("chapitres 1 à 3" (chapters 1 to 3)) that the book does not attest | Number reconstructed by the posture. The `CLAUDE.md` rule requires citing the section by its title when no number is attested; otherwise, reread `read_passage` to check the section |
| An answer cites watch articles without a "Sources" section at the end of the answer, or with the full citation in the middle of the text | `CLAUDE.md` rule clarified on 5 October 2026: short reference in the text, full citation (author or site, title, date, link) in "Sources". The `veille-goulot` criterion in `cas.yaml` expects it; replay the case (`--cases veille-goulot`). This case oscillates from one run to the next: the failures observed are a reference without an author or site name, a single date for a whole paragraph, or an article cited in the text but missing from "Sources" |
| A watch article is cited without an author | The header had no author. The server returns the site ("auteur non indiqué" (author not given)): the mention is written at indexing time, so it applies only to articles indexed after the update of `pmzilla_lab_library.py` (to copy into `~/PMZilla-Lab/`); older ones may still come out without an author |
| `critic_mirror.py` counts no objection for a deliverable that contains some | Critic's section does not have a recognized title: it needs a Markdown heading that names Critic ("## 8. Revue de Critic" works) or, as a single line, "Ce que Critic conteste", "Objections de Critic" or "Revue de Critic". A heading that carries the `[Posture : Critic]` tag is discarded |
| A citation gives a wrong or missing author for a book | The author comes from the catalog, not from the file. Book with no entry in `tools/book_catalog.yaml` (it comes out as "auteur non indiqué"), or entry corrected without reindexing: complete the catalog, then `uv run ~/PMZilla-Lab/pmzilla_lab_library.py index Bibliotheque-Lab Watch-Lab` (the vectors are not recomputed) |
| A book cited by a posture no longer comes up in search | Badly named file or file holding another book, removed from `MAPPING` during the 5 October 2026 cleanup: list in a comment in `mapping_lab.py`, book to download again and reconvert |
| The evaluation set reports "Aucun fichier écrit ne contient …" (No file written contains …) | A person's name slipped into a deliverable in `_bmad-output/`, including in a quotation of the words of the question: replace it with the role before committing, then replay the case (`--cases`). The `CLAUDE.md` rule covers the whole file and requires a reread before each write (clarified on 5 October 2026 after this case) |
| A case that passes intermittently (a posture postpones the search until after the context questions) | Two instructions contradicted each other with no written order. `CLAUDE.md` sets the order search, then question, then recommend, and each CREED recalls it: check this "Ordre" (order) line before touching the case. A diagnostic requested with its data is not delayed: the "Contexte avant discussion" (context before discussion) rule says so, with the questions at the end of the deliverable (case `delivery-diagnostic-critic`); the `SKILL.md` files refer to this rule without copying it |
| A corrected instruction in a posture has no effect, or `tests/references_postures` fails | Each reference exists in the skill (loaded by the posture) and in the local sanctum (copy made at creation). Fix the skill, then run `python3 tools/sanctum_refresh.py` (`--dry-run` shows what would change); it copies the templates, references and scripts into the sanctum without touching its memory (`MEMORY.md`, `BOND.md`, `PERSONA.md`, `sessions/`). The test checks that a new sanctum reproduces the references of the skill |
| A regression in the evaluation set that the last commit does not explain | The accumulated experience of the posture (real memory) can make the answer vary from one run to the next. Since 5 October 2026, the runs use the frozen memory from `tests/postures/memoire/`: check that the report says "mémoire : figée", and replay the case (`--cases`) before concluding there is a drift |
| `tableau-de-bord.html` missing or a section empty | The script never stops on a missing source: the section shows "pas encore de données". Rerun `uv run tools/dashboard.py` and read its message; the failure from `watch.sh` or `evals_auto.sh` is silent or reported in their log |
| `Colonne absente de l'export : clé du ticket` (column missing from the export: ticket key) with `dependencies_jira.py` | The Jira view has no "Key" column: without it, a ticket cannot be linked to those of its links. Add it and export again |
| "Plus de 30 % des liens sortent de l'export" (more than 30% of the links go outside the export) in `dependencies_jira.py diagnose` | The JQL query does not include the linked projects or filters out finished tickets: the team on the other side stays "(hors export)" (outside the export) and its dependencies "à état inconnu" (state unknown). Widen the query or add an export batch, then rerun |
| `watch_triage.py suggestions` answers "Aucun article noté" (no article scored) | The pre-triage database is empty: run `watch_triage.py score` first. This is no longer an error; with `--reset`, suggestions that were never activated are still removed from `sources.yaml` |
| A good article is rejected by the filter | `uv run ~/PMZilla-Lab/watch_triage.py restore <fichier.md>`; if it was "hors thèmes" (off-theme), complete `themes` in `tri.yaml` |
| The daily watch log says `Index BM25 illisible` (unreadable BM25 index), or a filtered text search fails with `bitmap intersection stream … claimed twice` | The BM25 index `knowledge.chunks_bm25` is damaged (pg_search). `pmzilla_lab_library.py probe`, run by `watch.sh` after each successful indexing, probes it and exits with code 3 (`BM25 index readable` when it is sound). The rebuild is yours alone, as superuser: `docs/pmzilla/installation.md`, section 14.6 |

---

## 10. Privacy

- The library, the index and the vectors stay on the Mac. What leaves the Mac is limited to: the passages found by a search and the session exchanges, which go to Claude (Anthropic) in the conversation (context notes read in a session, a story pasted for the manual SQ audit, and the team names read through the extract and the `v_teams` and `v_team_jira_ids` views are part of them); the cleaned text of Jira stories, sent to the Anthropic API by the analysis engine (see the story content bullet below); and the tracked files, pushed to the private GitHub repository.
- The exchanges are processed by Claude (Anthropic) under the subscription.
- **The agents' memory never contains personal data about colleagues**, nor any individual judgment. The deliverables in `_bmad-output/` follow the same rule, throughout the file (quotations included), with a reread before each write (rule in `CLAUDE.md`). In the agents, the commands, the skills and the deliverables, "the user" replaces the first name; the rule does not apply to the author credits of published sources (Sources section, short references, URLs), including your own articles. The Facilitation posture describes dynamics at team level.
- The watch is judged and summarized locally by gemma4:26b: articles go to Claude only when a search brings them up in a session.
- The books and the watch articles stay on the Mac: their folders are in the workspace, but their content is excluded from Git. They are copyrighted content.
- The Jira data (tickets and links) stay in the local database on the Mac, unreadable by Claude Code: the Delivery posture reads only the aggregate reports in `Flux-Lab/rapports/`. The same goes for the state history collected by `history_jira.py` (in the database): the script keeps of each change only its date and its starting and arrival values (status, fix version, labels declared in `flux.yaml`), never the author of the event, and the Jira token never leaves the macOS Keychain.
- The coaching journal (`Journal-Lab/`) stays on the Mac, excluded from Git, and contains only roles and scopes, never names or judgments about a person.
- **Team names, Jira project names and domain names** stay in `Flux-Lab/` and in the ignored folders of `_bmad-output/` (`pmzilla/dependances/`, `pmzilla/flux/`, `pmzilla/messages/`). The files tracked by Git keep only generic designations (rule in `CLAUDE.md`). A `pre-commit` hook reads `Flux-Lab/noms-sensibles.txt` (outside Git) and refuses a commit that contains one of these names; see the [installation](docs/pmzilla/installation.md). The postures' sanctum (`_bmad/memory/`) is local and ignored by Git, like the user's context (`.pmzilla/contexte.md`). Team names read in a session (through the extract `Flux-Lab/equipes-lisibles.yaml` or the views `v_teams` and `v_team_jira_ids`) go to Anthropic with the rest of the exchange.
- **Jira story content (schema `quality`).** Since the authorisation of 2026-10-15, the title, description and acceptance criteria of Jira stories and epics are read, by you alone (`tools/story_quality.py collect`, in your Terminal; Claude Code never runs `collect`, `review`, `analyse` or `coach`). The text is cleaned before storage (mentions, e-mail addresses and sensitive names replaced by markers, profile links becoming `[person]`, media replaced by a marker; a name absent from the sensitive-names list stays in the text, so the cleaned sample of each newly collected team is read by you (`review`) before any of its items can be sent) and kept in the local schema `quality` for one year at most. The deletion is yours, not automatic: after the labelled backup of the day, `uv run tools/flow_retention.py purge --apply`; `collect` only sets aside the items beyond the rule. It is never written to a file, a backup (the backup keeps only a partial dump without any text), a tracked file or GitHub. `analyse` and `coach` (`analyse --sample` included) send the cleaned texts, the effective grid and the overlay's product context summary (never a key, a team or a person) to an analysis engine (the Anthropic API, key in the macOS Keychain), after a cost estimate and your confirmation. Results are by team only, never by person, teams are never ranked, and the coaching feedback stays in the Terminal and enters no report. Claude Code never reads the tables of `quality`: only the three aggregated views through `tools/flow_views.py` (masking under 5) and the `qualite-stories-*` reports. Procedure: [installation](docs/pmzilla/installation.md); design: the `story-quality-*` specs in `openspec/specs/`.
- Reading through the Jira API is approved by the organization for tickets (state, type, dates, resolution, team, parent, links) and for the state history, aggregated by team, with no personal data (the story content above is covered by its own authorisation). The token stays in the macOS Keychain; Claude Code never runs the commands that contact Jira (`deny` rules). When the data live in the `flow` schema of the database, Claude Code never reads its tables: only the aggregated views through `tools/flow_views.py` (a cell under 5 tickets shown as `masqué`, `masked` in English) and the reports. Flow data about tickets are kept at most one year (`tools/flow_retention.py`, run by you). The database backups and their off-site copy to an encrypted disk stay out of Claude Code's reach, and no password is read or stored by the scripts.
- No sensitive internal organization document without an explicit decision.
- The GitHub repository is **private**.

---

## 11. Evolution ideas

The ideas live in the GitHub issues of the private repository, labelled `type:idea`, with no milestone and outside the work queue. Read them with `gh issue list --label type:idea`; create one with `uv run tools/gh_issue.py new-idea --title "<title>" --body "<summary>"`. What is done is found in the GitHub releases (the history up to 13 October 2026 is in the frozen [CHANGELOG](CHANGELOG.md)).
