===== statuses-first-run =====
Settings created: <WS>/Flux-Lab/flux.yaml (fill in the statuses of your workflow)
Columns used:
  type                                 Issue Type
  status                               Status
  team (optional)                      MISSING
  created                              Created
  resolved                             Resolved
  start (status category changed)      MISSING
1 ticket(s) with an unreadable creation date, left out of the reading

1 tickets, created from 2026-08-01 to 2026-08-01
1 resolved, from 2026-08-10 to 2026-08-10

Statuses (to sort into in_progress_states and todo_states of flux.yaml):
      1  Done  (done or unclassified)

Types:
      1  Story
--- stderr ---

===== statuses =====
$ statuses <WS>/a.csv <WS>/b.csv
exit code: 0
--- stdout ---
Columns used:
  type                                 Issue Type
  status                               Status
  team (optional)                      Team
  created                              Created
  resolved                             Resolved
  start (status category changed)      Status Category Changed
  status category (optional)           Status Category
  ticket key (optional)                Issue key

200 tickets, created from 2024-03-06 to 2026-09-24
87 resolved, from 2026-04-06 to 2026-09-26

Statuses (to sort into in_progress_states and todo_states of flux.yaml):
     48  Closed  (done or unclassified)
     39  Done  (done or unclassified)
     24  Doing  (in progress)
     22  Waiting  (to do)
     19  Open  (to do)
     18  In Review  (in progress)
     16  Validation  (in progress)
     14  In Progress  (in progress)

Left out of the computation (portfolio_types and excluded_projects): 74 tickets; by type: Epic 27, RN Task 27; by project: BUG 20.

Types:
     72  Story
     51  Bug
     27  Epic
     27  RN Task
     23  Task
--- stderr ---

===== statuses-one-export =====
$ statuses <WS>/a.csv
exit code: 0
--- stdout ---
Columns used:
  type                                 Issue Type
  status                               Status
  team (optional)                      Team
  created                              Created
  resolved                             Resolved
  start (status category changed)      Status Category Changed
  status category (optional)           Status Category
  ticket key (optional)                Issue key

90 tickets, created from 2024-03-06 to 2026-09-20
39 resolved, from 2026-04-26 to 2026-09-26

Statuses (to sort into in_progress_states and todo_states of flux.yaml):
     39  Done  (done or unclassified)
     19  Open  (to do)
     18  In Review  (in progress)
     14  In Progress  (in progress)

Left out of the computation (portfolio_types and excluded_projects): 27 tickets; by type: Epic 27.

Types:
     40  Story
     27  Epic
     23  Task
--- stderr ---

===== statuses-no-key =====
$ statuses <WS>/no-key.csv <WS>/no-key.csv
exit code: 0
--- stdout ---
Columns used:
  type                                 Issue Type
  status                               Status
  team (optional)                      MISSING
  created                              Created
  resolved                             Resolved
  start (status category changed)      MISSING

4 tickets, created from 2026-08-01 to 2026-08-05
2 resolved, from 2026-08-10 to 2026-08-10

Statuses (to sort into in_progress_states and todo_states of flux.yaml):
      2  Done  (done or unclassified)
      2  Open  (to do)

Types:
      4  Story
--- stderr ---

===== statuses-no-resolved =====
$ statuses <WS>/no-resolved.csv
exit code: 0
--- stdout ---
Columns used:
  type                                 Issue Type
  status                               Status
  team (optional)                      MISSING
  created                              Created
  resolved                             MISSING
  start (status category changed)      MISSING

1 tickets, created from 2026-08-05 to 2026-08-05

Statuses (to sort into in_progress_states and todo_states of flux.yaml):
      1  Open  (to do)

Types:
      1  Story

Without a "Resolved" column, neither lead time nor throughput can be computed: add it to the export.
--- stderr ---

===== compute-older =====
$ compute <WS>/a.csv <WS>/b.csv --name s --today 2026-09-20 --no-comparison --scope ABC,DEF,ZZZ --history --dormant-from-history --points --target-date 2026-11-15 --batch-closure-resolutions Done,Closed
exit code: 0
--- stdout ---
--scope: 180 ticket(s) kept out of 200; 1 requested project(s) with no ticket in the export.
--dormant-from-history: 13 dormant ticket(s) according to the history; 11 unfinished ticket(s) with no history in the cache, not counted as dormant; 10 in progress and 3 to do dormant.
--history: 3 ticket(s) have an unreadable transition date in the cache: their transitions are ignored (run history_jira.py collect --refresh again).
# Flow metrics: s, as of 2026-09-20

Period: 2026-04-06 to 2026-09-13 (23 complete weeks). Types: all. Aggregates computed locally from a Jira export; no ticket is quoted.

Scope: projects ABC, DEF, ZZZ (180 ticket(s) kept out of 200 read, option --scope).

Left out of throughput, lead time, WIP and forecasts (portfolio_types and excluded_projects in flux.yaml): 54 tickets; by type: Epic 27, RN Task 27.

## Throughput
- 32 items finished, i.e. 1.4 per week on average (median 1); 3 week(s) with no item finished.
- Per week, from the oldest to the most recent: 2, 0, 1, 0, 1, 1, 1, 2, 0, 1, 3, 2, 1, 2, 1, 1, 2, 1, 3, 2, 1, 3, 1.
- Resolutions counted as delivered: Done 32.
- Closed without delivery, left out of throughput, lead time and forecasts: none.

## Arrivals and departures

Arrivals: tickets created during the period, same types and same exclusions as the throughput. Departures: finished items counted as delivered (the throughput). Difference: arrivals minus departures; when positive, the stock of open tickets grows, when negative, it shrinks.

| Week (start) | Arrivals | Departures | Difference |
|---|---|---|---|
| 2026-04-06 | 1 | 2 | -1 |
| 2026-04-13 | 3 | 0 | +3 |
| 2026-04-20 | 2 | 1 | +1 |
| 2026-04-27 | 4 | 0 | +4 |
| 2026-05-04 | 1 | 1 | 0 |
| 2026-05-11 | 1 | 1 | 0 |
| 2026-05-18 | 6 | 1 | +5 |
| 2026-05-25 | 4 | 2 | +2 |
| 2026-06-01 | 6 | 0 | +6 |
| 2026-06-08 | 5 | 1 | +4 |
| 2026-06-15 | 3 | 3 | 0 |
| 2026-06-22 | 3 | 2 | +1 |
| 2026-06-29 | 5 | 1 | +4 |
| 2026-07-06 | 7 | 2 | +5 |
| 2026-07-13 | 5 | 1 | +4 |
| 2026-07-20 | 0 | 1 | -1 |
| 2026-07-27 | 7 | 2 | +5 |
| 2026-08-03 | 5 | 1 | +4 |
| 2026-08-10 | 5 | 3 | +2 |
| 2026-08-17 | 6 | 2 | +4 |
| 2026-08-24 | 2 | 1 | +1 |
| 2026-08-31 | 1 | 3 | -2 |
| 2026-09-07 | 4 | 1 | +3 |
| **Total** | **86** | **32** | **+54** |

- Average per week: 3.7 arrivals, 1.4 departures.
- Note: tickets created then rejected, or left without movement, count in the arrivals but never in the departures (excluded closure resolutions are not throughput): the difference therefore does not measure a growth of the real work. A dormant ticket (more than 365 days) only enters the arrivals if its creation falls in the period, which implies a period of more than 52 weeks. Arrivals also depend on the export query.

- **First week truncated.** The export query filters `resolved >= -20w`: the window starts on 2026-05-03 (from the computation date), so the whole first week and more is missing from the export. The week of 2026-04-06 is underestimated (departures, and arrivals of tickets created then resolved before the window): leave it out of comparisons (series, averages, trends).

### By team

| Team | Arrivals | Departures | Difference |
|---|---|---|---|
| (no team) | 2 | 2 | 0 |
| Team A | 10 | 5 | +5 |
| Team B | 1 | 0 | +1 |
| Team C | 10 | 1 | +9 |
| Team D | 10 | 3 | +7 |
| Team E | 6 | 2 | +4 |
| Team F | 6 | 3 | +3 |
| Team G | 5 | 2 | +3 |
| Team H | 7 | 5 | +2 |
| Team I | 7 | 2 | +5 |
| Team J | 6 | 2 | +4 |
| Team K | 13 | 4 | +9 |
| Team L | 3 | 1 | +2 |

Teams are not compared with each other: workflows, ticket sizes and types of work differ. Each row is first for the team concerned.

### Shared tickets by team

First-team attribution: each ticket counts once, for its first team.

| Team | Attributed here, shared | Carried here, attributed elsewhere |
|---|---|---|
| Team A | 5 | masked |
| Team B | masked | 5 |

## Batched closures

Delivered tickets (resolution: closed, done) whose resolution falls in the same minute as that of at least 4 others of the same project (threshold of 5 tickets, batch_closure_threshold setting). A count only: these tickets stay in the throughput, the lead time and the forecasts.

No batched closure in the period (32 tickets delivered).

## Lead time (from creation to resolution)
- All types: P50 46 d · P70 67 d · P85 80 d · P95 88 d.
- Bug (7 finished): P50 54 d · P70 69 d · P85 71 d · P95 74 d.
- Story (18 finished): P50 33 d · P70 53 d · P85 69 d · P95 87 d.
- Task (7 finished): P50 80 d · P70 82 d · P85 88 d · P95 89 d.

## Work in progress
- WIP: 46 items in progress (Doing 14, In Review 12, In Progress 10, Validation 10); 29 items to do.
- Age of items in progress since they started: P50 87 d · P70 106 d · P85 122 d · P95 174 d.
- Age since creation: P50 102 d · P70 165 d · P85 927 d · P95 927 d.
- 29 item(s) in progress are older (basis: creation) than the P85 lead time of finished items.
- Items in progress for more than 30 / 90 / 180 / 365 / 730 days: 42 / 27 / 11 / 10 / 10.
- Active WIP: 36 (78%); waiting WIP: 0 (0%); dormant WIP: 10 (22%). A dormant ticket is taken out of the other two categories; the total WIP stays 46.
- To do: 26 excluding dormant, 3 dormant (10% of the 29).
- Note: a ticket is dormant when it is unfinished, created at least 365 days ago, with no status change for at least 365 days, according to the status history (date of the last transition, or of creation if there is none). 11 unfinished ticket(s) with no history in the cache are not counted as dormant. No key is written here.
- "In progress" and "to do" are decided by the Jira status category (column "Status Category"); the lists in flux.yaml only serve for tickets with no category.

### Age by status (basis: creation)

| Status | Nature | Items | Age P50 | Age P85 | Over 90 d | Over 365 d | Dormant | Dormant share |
|---|---|---|---|---|---|---|---|---|
| Doing | active | 14 | 69 d | 927 d | 6 | 3 | 3 | 21% |
| In Review | active | 12 | 150 d | 927 d | 9 | 5 | 5 | 42% |
| In Progress | active | 10 | 102 d | 169 d | 7 | 1 | 1 | 10% |
| Validation | active | 10 | 90 d | 107 d | 5 | 1 | 1 | 10% |

### Queues before commitment: age of the items to do, by status

An item can wait a long time before it is started: this time counts neither in the WIP nor in the lead time of an item that is not finished yet. "Since the category" starts at the last Jira status category change (entering analysis or definition, for example), when it is known.

| To do status | Items | Age P50 (creation) | Age P85 (creation) | Age P50 (category) | Over 90 d | Over 365 d | Dormant |
|---|---|---|---|---|---|---|---|
| Open | 15 | 154 d | 853 d | n/a | 10 | 3 | 2 |
| Waiting | 14 | 72 d | 223 d | n/a | 6 | 2 | 1 |

- Little's law on the non-dormant WIP (36 items, active and waiting) divided by the average throughput: at this pace, an item stays in progress for about 181 days on average; compare with the age of the items in progress and with the median lead time. For comparison, on the total WIP (46 items): about 231 days.

## By team

| Team | Finished | Throughput / wk | Lead time P50 | Lead time P85 | WIP | WIP age P50 | WIP > 90 d | Active WIP | Waiting WIP | Dormant WIP | Active share | Waiting share | Dormant share | To do | Dormant to do |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (no team) | 2 | 0.1 | 57 d | 80 d | 1 | 183 d | 1 | 1 | 0 | 0 | 100% | 0% | 0% | 1 | 0 |
| Team A | 5 | 0.2 | 14 d | 70 d | 3 | 115 d | 2 | 2 | 0 | 1 | 67% | 0% | 33% | 3 | 0 |
| Team B | 0 | 0.0 | n/a | n/a | 1 | 158 d | 1 | 1 | 0 | 0 | 100% | 0% | 0% | 1 | 0 |
| Team C | 1 | 0.0 | 50 d | 50 d | 3 | 97 d | 2 | 3 | 0 | 0 | 100% | 0% | 0% | 5 | 0 |
| Team D | 3 | 0.1 | 21 d | 44 d | 9 | 168 d | 7 | 6 | 0 | 3 | 67% | 0% | 33% | 3 | 1 |
| Team E | 2 | 0.1 | 45 d | 61 d | 1 | 84 d | 0 | 1 | 0 | 0 | 100% | 0% | 0% | 2 | 0 |
| Team F | 3 | 0.1 | 71 d | 84 d | 4 | 116 d | 4 | 3 | 0 | 1 | 75% | 0% | 25% | 4 | 0 |
| Team G | 2 | 0.1 | 44 d | 50 d | 3 | 175 d | 2 | 2 | 0 | 1 | 67% | 0% | 33% | 1 | 0 |
| Team H | 5 | 0.2 | 42 d | 62 d | 3 | 927 d | 2 | 1 | 0 | 2 | 33% | 0% | 67% | 2 | 0 |
| Team I | 2 | 0.1 | 56 d | 74 d | 4 | 56 d | 1 | 4 | 0 | 0 | 100% | 0% | 0% | 0 | 0 |
| Team J | 2 | 0.1 | 38 d | 62 d | 4 | 52 d | 1 | 4 | 0 | 0 | 100% | 0% | 0% | 0 | 0 |
| Team K | 4 | 0.2 | 50 d | 78 d | 9 | 75 d | 4 | 7 | 0 | 2 | 78% | 0% | 22% | 2 | 1 |
| Team L | 1 | 0.0 | 80 d | 80 d | 1 | 4 d | 0 | 1 | 0 | 0 | 100% | 0% | 0% | 5 | 1 |

Teams are not compared with each other: workflows, ticket sizes and types of work differ. Each row is first for the team concerned.

Items finished per week and per team, from the oldest to the most recent (zero weeks between two peaks point to batched closures):

- (no team): 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0
- Team A: 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0
- Team B: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
- Team C: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0
- Team D: 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0
- Team E: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1
- Team F: 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0
- Team G: 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0
- Team H: 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0
- Team I: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0
- Team J: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0
- Team K: 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0
- Team L: 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0

Tickets with several teams: 5 out of 126 (1 finished, 2 in progress). Current attribution: each ticket counts once, in the row of the first value of its first team column; the other values and the other team columns attribute nothing. Teams are recognised by the columns of the same name and by the separator ";" in a cell (team_separator setting of flux.yaml).


## Time in segment

Time spent in each segment of statuses (segments setting of flux.yaml), from the status history, in calendar days (differences of dates), initial status included. The time of a ticket adds up over all its visits to the segment. Computed to be compared with the Jira Control Chart, on the same statuses and the same dates.

- Coverage: 73 tickets out of 78 (delivered during the period or in progress) have a history (94%).
- WARNING: 3 ticket(s) have an unreadable transition date in the cache; their transitions are ignored and their time in segment is wrong. Run the collection again with --refresh.

### Tickets that left a segment during the period (cumulative time in the segment)

| Segment | Tickets | P50 | P85 | Mean |
|---|---|---|---|---|
| Definition | 76 | 3 d | 5 d | 3.2 d |
| Ready | 77 | 3 d | 4 d | 2.8 d |
| Implementation | 28 | 42 d | 72 d | 41.1 d |
| Review and verification | 0 | n/a | n/a | n/a |
| Acceptance | 0 | n/a | n/a | n/a |

### Tickets still in a segment (age of the current visit)

| Segment | Tickets | Age P50 | Age P85 |
|---|---|---|---|
| Definition | 0 | n/a | n/a |
| Ready | 0 | n/a | n/a |
| Implementation | 64 | 102 d | 918 d |
| Review and verification | 0 | n/a | n/a |
| Acceptance | 0 | n/a | n/a |

### Delivery lead time

From the commitment point (entry into the segment "Ready") to resolution, for the 29 tickets delivered during the period that went through it (1 delivered ticket(s) with a history but no commitment point are not counted).

- Since commitment: P50 44 d · P70 64 d · P85 75 d · P95 83 d.
- Since creation, for the same tickets: P50 50 d · P70 70 d · P85 81 d · P95 89 d. The lead time of all delivered items is higher up in the report.

### Flow efficiency

- Share of time in an active status, between the commitment point and resolution (the waiting statuses are those of waiting_states): 92% at P50 per ticket (28 tickets), 93% in aggregate value (total active time over total time).

### By team

| Team | Coverage | Delivered with commitment | Delivery lead time P50 | P85 | Efficiency P50 | Aggregate efficiency |
|---|---|---|---|---|---|---|
| (no team) | 100% | 2 | 50 d | 74 d | 92% | 95% |
| Team A | 88% | 4 | 30 d | 68 d | 84% | 92% |
| Team B | 100% | 0 | n/a | n/a | n/a | n/a |
| Team C | 100% | 1 | 44 d | 44 d | 93% | 93% |
| Team D | 92% | 3 | 15 d | 38 d | 87% | 90% |
| Team E | 100% | 2 | 39 d | 54 d | 90% | 95% |
| Team F | 100% | 3 | 66 d | 78 d | 95% | 94% |
| Team G | 100% | 2 | 38 d | 45 d | 87% | 88% |
| Team H | 88% | 4 | 22 d | 54 d | 82% | 91% |
| Team I | 83% | 2 | 50 d | 68 d | 88% | 92% |
| Team J | 100% | 1 | 66 d | 66 d | 95% | 95% |
| Team K | 92% | 4 | 44 d | 73 d | 91% | 92% |
| Team L | 100% | 1 | 75 d | 75 d | 96% | 96% |

Tickets that left each segment during the period, by team (count, P50 of the cumulative time):

| Team | Definition | Ready | Implementation | Review and verification | Acceptance |
|---|---|---|---|---|---|
| (no team) | 2 · 4 d | 2 · 2 d | 2 · 48 d | 0 · n/a | 0 · n/a |
| Team A | 8 · 4 d | 8 · 2 d | 4 · 29 d | 0 · n/a | 0 · n/a |
| Team B | 1 · 2 d | 1 · 5 d | 0 · n/a | 0 · n/a | 0 · n/a |
| Team C | 8 · 4 d | 8 · 3 d | 1 · 41 d | 0 · n/a | 0 · n/a |
| Team D | 10 · 4 d | 11 · 3 d | 2 · 28 d | 0 · n/a | 0 · n/a |
| Team E | 6 · 3 d | 6 · 2 d | 2 · 37 d | 0 · n/a | 0 · n/a |
| Team F | 6 · 3 d | 7 · 3 d | 3 · 63 d | 0 · n/a | 0 · n/a |
| Team G | 5 · 3 d | 6 · 3 d | 2 · 34 d | 0 · n/a | 0 · n/a |
| Team H | 5 · 4 d | 5 · 3 d | 4 · 19 d | 0 · n/a | 0 · n/a |
| Team I | 5 · 4 d | 5 · 3 d | 2 · 46 d | 0 · n/a | 0 · n/a |
| Team J | 6 · 2 d | 5 · 3 d | 1 · 63 d | 0 · n/a | 0 · n/a |
| Team K | 11 · 2 d | 11 · 3 d | 4 · 40 d | 0 · n/a | 0 · n/a |
| Team L | 3 · 4 d | 2 · 1 d | 1 · 72 d | 0 · n/a | 0 · n/a |

Tickets still in each segment, by team (count, age P50):

| Team | Definition | Ready | Implementation | Review and verification | Acceptance |
|---|---|---|---|---|---|
| (no team) | 0 · n/a | 0 · n/a | 1 · 175 d | 0 · n/a | 0 · n/a |
| Team A | 0 · n/a | 0 · n/a | 4 · 122 d | 0 · n/a | 0 · n/a |
| Team B | 0 · n/a | 0 · n/a | 2 · 75 d | 0 · n/a | 0 · n/a |
| Team C | 0 · n/a | 0 · n/a | 6 · 101 d | 0 · n/a | 0 · n/a |
| Team D | 0 · n/a | 0 · n/a | 10 · 164 d | 0 · n/a | 0 · n/a |
| Team E | 0 · n/a | 0 · n/a | 2 · 109 d | 0 · n/a | 0 · n/a |
| Team F | 0 · n/a | 0 · n/a | 7 · 104 d | 0 · n/a | 0 · n/a |
| Team G | 0 · n/a | 0 · n/a | 4 · 170 d | 0 · n/a | 0 · n/a |
| Team H | 0 · n/a | 0 · n/a | 5 · 175 d | 0 · n/a | 0 · n/a |
| Team I | 0 · n/a | 0 · n/a | 3 · 82 d | 0 · n/a | 0 · n/a |
| Team J | 0 · n/a | 0 · n/a | 4 · 46 d | 0 · n/a | 0 · n/a |
| Team K | 0 · n/a | 0 · n/a | 10 · 78 d | 0 · n/a | 0 · n/a |
| Team L | 0 · n/a | 0 · n/a | 6 · 52 d | 0 · n/a | 0 · n/a |

Below about ten tickets, a P85 is fragile: read it as a question, not as a finding.

Teams are not compared with each other: workflows, ticket sizes and types of work differ. Each row is first for the team concerned.

## Monte Carlo forecasts (10,000 simulations on the weekly throughput of the period)
- Finish 36 items (non-dormant WIP, active and waiting): 26 weeks with a 50% chance, 30 with 85%, 32 with 95%.
- Note, for comparison, on the total WIP (46 items, dormant included): 33 weeks with a 50% chance, 37 with 85%, 39 with 95%.
- By 2026-11-15: at least 9 items with an 85% chance (11 with 50%, 7 with 95%).

## How to read this report

- **P50 (median)**: half of the items are below, half are above. It is the typical case.
- **P85**: 85% of the items are below, 15% above. It is used to make commitments: "in 85% of cases, less than X days". P70 and P95 read the same way, with 70% and 95%.
- **Why percentiles rather than an average**: a few very long tickets pull the average up. Percentiles are not dragged along by these extreme cases.
- **Lead time**: from creation to resolution, for finished items only. **Age**: since the last status category change (creation date if there is none), for items still in progress. Lead time only sees what finishes; age shows what stays stuck.
- **WIP**: items in progress. **Active WIP**: being worked on right now. **Waiting WIP**: in a waiting status listed in flux.yaml, such as "Ready for". **Dormant WIP**: not finished and with no status change for more than 365 days (inferred from the status history, option --dormant-from-history). A dormant ticket is neither active nor waiting.
- **Arrivals and departures**: tickets created and items finished, week by week. If arrivals keep exceeding departures, the stock grows. Arrivals also count rejected tickets.
- **Little's law**: the number of items in progress divided by the average throughput gives an average time in the system. Read it with care when arrivals keep exceeding departures.
- **Monte Carlo forecast**: 10,000 draws from the throughput of past weeks. It says in how many weeks of throughput the current stock would drain if nothing new came in. It is not a date.
- **Segment**: a group of consecutive workflow statuses (definition, ready, implementation, review and verification, acceptance), set in flux.yaml. **Time in segment**: how many days a ticket spent in the statuses of the segment, in calendar days, initial status included; the time adds up if the ticket comes back to the segment. "Left the segment" means: moved to another segment during the period.
- **Commitment point**: the moment the team commits, here the entry into the segment set by commitment_point. **Delivery lead time**: from the commitment point to resolution; it is shorter than the lead time from creation, which also counts the wait in the backlog.
- **Flow efficiency**: the share of time spent in an active status, between the commitment point and resolution. A waiting status (waiting_states) counts as time lost waiting, any other status as active time. A low efficiency says tickets wait a lot, not that people work badly.
- **Coverage**: the share of the tickets in the report whose history is known. Below 90%, the figures for time in segment only describe part of the tickets.
- **Batched closure**: at least N delivered tickets of the same project whose resolution falls in the same minute (N: batch_closure_threshold in flux.yaml). It most likely points to a bulk status change (clean-up, migration) rather than deliveries as they happen. A count only: these tickets stay in the throughput.
- **Shared tickets**: a ticket carried by several teams counts once, for its first team. For each team, the first column counts the tickets attributed to it while shared, the second those it carries without their being attributed to it. A cell under 5 tickets is written "masked".

Examples taken from this report:
- The P85 age of items in progress is 927 days: 15% of the items in progress have been there for more than 927 days.
- The P85 lead time is 80 days: 85% of the finished items were finished in less than 80 days.
- The aggregate flow efficiency is 93%: out of 100 days spent between the commitment point and resolution, 93 were in an active status and 7 waiting.

## Limits
- Lead time counts from the creation of the ticket, waiting in the backlog included: it is not a cycle time.
- Forecasts assume that the throughput of the coming weeks will look like that of the period, and that items are of comparable size.

Report: <WS>/Flux-Lab/rapports/flux-s-2026-09-20.md
Aging WIP points: 46 ticket(s) in progress, no key: <WS>/Flux-Lab/tableaux/points-s-2026-09-20.json
--- stderr ---
written: rapports/flux-s-2026-09-20.json
written: rapports/flux-s-2026-09-20.md
written: tableaux/points-s-2026-09-20.json

===== compute-newer-with-comparison =====
$ compute <WS>/a.csv <WS>/b.csv --name s --today 2026-10-04 --scope ABC,DEF,ZZZ --history --dormant-from-history --points --target 40 --target-date 2026-11-15 --batch-closure-resolutions Done,Closed
exit code: 0
--- stdout ---
--scope: 180 ticket(s) kept out of 200; 1 requested project(s) with no ticket in the export.
--dormant-from-history: 13 dormant ticket(s) according to the history; 11 unfinished ticket(s) with no history in the cache, not counted as dormant; 10 in progress and 3 to do dormant.
--history: 3 ticket(s) have an unreadable transition date in the cache: their transitions are ignored (run history_jira.py collect --refresh again).
# Flow metrics: s, as of 2026-10-04

Period: 2026-04-06 to 2026-09-27 (25 complete weeks). Types: all. Aggregates computed locally from a Jira export; no ticket is quoted.

Scope: projects ABC, DEF, ZZZ (180 ticket(s) kept out of 200 read, option --scope).

Left out of throughput, lead time, WIP and forecasts (portfolio_types and excluded_projects in flux.yaml): 54 tickets; by type: Epic 27, RN Task 27.

## Throughput
- 48 items finished, i.e. 1.9 per week on average (median 1); 3 week(s) with no item finished.
- Per week, from the oldest to the most recent: 2, 0, 1, 0, 1, 1, 1, 2, 0, 1, 3, 2, 1, 2, 1, 1, 2, 1, 3, 2, 1, 3, 1, 3, 13.
- Resolutions counted as delivered: Done 48.
- Closed without delivery, left out of throughput, lead time and forecasts: Won't Do 3.

## Arrivals and departures

Arrivals: tickets created during the period, same types and same exclusions as the throughput. Departures: finished items counted as delivered (the throughput). Difference: arrivals minus departures; when positive, the stock of open tickets grows, when negative, it shrinks.

| Week (start) | Arrivals | Departures | Difference |
|---|---|---|---|
| 2026-04-06 | 1 | 2 | -1 |
| 2026-04-13 | 3 | 0 | +3 |
| 2026-04-20 | 2 | 1 | +1 |
| 2026-04-27 | 4 | 0 | +4 |
| 2026-05-04 | 1 | 1 | 0 |
| 2026-05-11 | 1 | 1 | 0 |
| 2026-05-18 | 6 | 1 | +5 |
| 2026-05-25 | 4 | 2 | +2 |
| 2026-06-01 | 6 | 0 | +6 |
| 2026-06-08 | 5 | 1 | +4 |
| 2026-06-15 | 3 | 3 | 0 |
| 2026-06-22 | 3 | 2 | +1 |
| 2026-06-29 | 5 | 1 | +4 |
| 2026-07-06 | 7 | 2 | +5 |
| 2026-07-13 | 5 | 1 | +4 |
| 2026-07-20 | 0 | 1 | -1 |
| 2026-07-27 | 7 | 2 | +5 |
| 2026-08-03 | 5 | 1 | +4 |
| 2026-08-10 | 5 | 3 | +2 |
| 2026-08-17 | 6 | 2 | +4 |
| 2026-08-24 | 2 | 1 | +1 |
| 2026-08-31 | 1 | 3 | -2 |
| 2026-09-07 | 4 | 1 | +3 |
| 2026-09-14 | 7 | 3 | +4 |
| 2026-09-21 | 1 | 13 | -12 |
| **Total** | **94** | **48** | **+46** |

- Average per week: 3.8 arrivals, 1.9 departures.
- Note: tickets created then rejected, or left without movement, count in the arrivals but never in the departures (excluded closure resolutions are not throughput): the difference therefore does not measure a growth of the real work. A dormant ticket (more than 365 days) only enters the arrivals if its creation falls in the period, which implies a period of more than 52 weeks. Arrivals also depend on the export query.

- **First week truncated.** The export query filters `resolved >= -20w`: the window starts on 2026-05-17 (from the computation date), so the whole first week and more is missing from the export. The week of 2026-04-06 is underestimated (departures, and arrivals of tickets created then resolved before the window): leave it out of comparisons (series, averages, trends).

### By team

| Team | Arrivals | Departures | Difference |
|---|---|---|---|
| (no team) | 2 | 2 | 0 |
| Team A | 10 | 5 | +5 |
| Team B | 2 | 0 | +2 |
| Team C | 10 | 2 | +8 |
| Team D | 11 | 6 | +5 |
| Team E | 6 | 4 | +2 |
| Team F | 7 | 3 | +4 |
| Team G | 6 | 5 | +1 |
| Team H | 7 | 7 | 0 |
| Team I | 8 | 3 | +5 |
| Team J | 6 | 2 | +4 |
| Team K | 14 | 7 | +7 |
| Team L | 5 | 2 | +3 |

Teams are not compared with each other: workflows, ticket sizes and types of work differ. Each row is first for the team concerned.

### Shared tickets by team

First-team attribution: each ticket counts once, for its first team.

| Team | Attributed here, shared | Carried here, attributed elsewhere |
|---|---|---|
| Team A | 5 | masked |
| Team B | masked | 5 |

## Batched closures

Delivered tickets (resolution: closed, done) whose resolution falls in the same minute as that of at least 4 others of the same project (threshold of 5 tickets, batch_closure_threshold setting). A count only: these tickets stay in the throughput, the lead time and the forecasts.

| Project | Tickets in batched closures | Groups | Largest group | Delivered in the period | Share of throughput |
|---|---|---|---|---|---|
| DEF | 7 | 1 | 7 | 22 | 32% |
| ABC | 5 | 1 | 5 | 26 | 19% |
| **Total** | **12** | **2** | | **48** | **25%** |

## Lead time (from creation to resolution)
- All types: P50 44 d · P70 54 d · P85 73 d · P95 87 d.
- Bug (12 finished): P50 50 d · P70 54 d · P85 69 d · P95 73 d.
- Story (26 finished): P50 32 d · P70 47 d · P85 62 d · P95 83 d.
- Task (10 finished): P50 62 d · P70 80 d · P85 86 d · P95 89 d.

## Work in progress
- WIP: 46 items in progress (Doing 14, In Review 12, In Progress 10, Validation 10); 29 items to do.
- Age of items in progress since they started: P50 101 d · P70 120 d · P85 136 d · P95 188 d.
- Age since creation: P50 116 d · P70 179 d · P85 941 d · P95 941 d.
- 37 item(s) in progress are older (basis: creation) than the P85 lead time of finished items.
- Items in progress for more than 30 / 90 / 180 / 365 / 730 days: 44 / 29 / 14 / 10 / 10.
- Active WIP: 36 (78%); waiting WIP: 0 (0%); dormant WIP: 10 (22%). A dormant ticket is taken out of the other two categories; the total WIP stays 46.
- To do: 26 excluding dormant, 3 dormant (10% of the 29).
- Note: a ticket is dormant when it is unfinished, created at least 365 days ago, with no status change for at least 365 days, according to the status history (date of the last transition, or of creation if there is none). 11 unfinished ticket(s) with no history in the cache are not counted as dormant. No key is written here.
- "In progress" and "to do" are decided by the Jira status category (column "Status Category"); the lists in flux.yaml only serve for tickets with no category.

### Age by status (basis: creation)

| Status | Nature | Items | Age P50 | Age P85 | Over 90 d | Over 365 d | Dormant | Dormant share |
|---|---|---|---|---|---|---|---|---|
| Doing | active | 14 | 83 d | 941 d | 6 | 3 | 3 | 21% |
| In Review | active | 12 | 164 d | 941 d | 9 | 5 | 5 | 42% |
| In Progress | active | 10 | 116 d | 183 d | 8 | 1 | 1 | 10% |
| Validation | active | 10 | 104 d | 121 d | 6 | 1 | 1 | 10% |

### Queues before commitment: age of the items to do, by status

An item can wait a long time before it is started: this time counts neither in the WIP nor in the lead time of an item that is not finished yet. "Since the category" starts at the last Jira status category change (entering analysis or definition, for example), when it is known.

| To do status | Items | Age P50 (creation) | Age P85 (creation) | Age P50 (category) | Over 90 d | Over 365 d | Dormant |
|---|---|---|---|---|---|---|---|
| Open | 15 | 168 d | 867 d | n/a | 12 | 3 | 2 |
| Waiting | 14 | 86 d | 237 d | n/a | 7 | 2 | 1 |

- Little's law on the non-dormant WIP (36 items, active and waiting) divided by the average throughput: at this pace, an item stays in progress for about 131 days on average; compare with the age of the items in progress and with the median lead time. For comparison, on the total WIP (46 items): about 168 days.

## By team

| Team | Finished | Throughput / wk | Lead time P50 | Lead time P85 | WIP | WIP age P50 | WIP > 90 d | Active WIP | Waiting WIP | Dormant WIP | Active share | Waiting share | Dormant share | To do | Dormant to do |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (no team) | 2 | 0.1 | 57 d | 80 d | 1 | 197 d | 1 | 1 | 0 | 0 | 100% | 0% | 0% | 1 | 0 |
| Team A | 5 | 0.2 | 14 d | 70 d | 3 | 129 d | 2 | 2 | 0 | 1 | 67% | 0% | 33% | 3 | 0 |
| Team B | 0 | 0.0 | n/a | n/a | 1 | 172 d | 1 | 1 | 0 | 0 | 100% | 0% | 0% | 1 | 0 |
| Team C | 2 | 0.1 | 52 d | 53 d | 3 | 111 d | 2 | 3 | 0 | 0 | 100% | 0% | 0% | 5 | 0 |
| Team D | 6 | 0.2 | 34 d | 51 d | 9 | 182 d | 7 | 6 | 0 | 3 | 67% | 0% | 33% | 3 | 1 |
| Team E | 4 | 0.2 | 51 d | 62 d | 1 | 98 d | 1 | 1 | 0 | 0 | 100% | 0% | 0% | 2 | 0 |
| Team F | 3 | 0.1 | 71 d | 84 d | 4 | 130 d | 4 | 3 | 0 | 1 | 75% | 0% | 25% | 4 | 0 |
| Team G | 5 | 0.2 | 43 d | 60 d | 3 | 189 d | 2 | 2 | 0 | 1 | 67% | 0% | 33% | 1 | 0 |
| Team H | 7 | 0.3 | 42 d | 56 d | 3 | 941 d | 2 | 1 | 0 | 2 | 33% | 0% | 67% | 2 | 0 |
| Team I | 3 | 0.1 | 32 d | 66 d | 4 | 70 d | 2 | 4 | 0 | 0 | 100% | 0% | 0% | 0 | 0 |
| Team J | 2 | 0.1 | 38 d | 62 d | 4 | 66 d | 1 | 4 | 0 | 0 | 100% | 0% | 0% | 0 | 0 |
| Team K | 7 | 0.3 | 35 d | 68 d | 9 | 89 d | 4 | 7 | 0 | 2 | 78% | 0% | 22% | 2 | 1 |
| Team L | 2 | 0.1 | 46 d | 70 d | 1 | 18 d | 0 | 1 | 0 | 0 | 100% | 0% | 0% | 5 | 1 |

Teams are not compared with each other: workflows, ticket sizes and types of work differ. Each row is first for the team concerned.

Items finished per week and per team, from the oldest to the most recent (zero weeks between two peaks point to batched closures):

- (no team): 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0
- Team A: 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0
- Team B: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
- Team C: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1
- Team D: 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 3
- Team E: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 2
- Team F: 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0
- Team G: 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 3
- Team H: 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1
- Team I: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0
- Team J: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0
- Team K: 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 2
- Team L: 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1

Tickets with several teams: 5 out of 126 (1 finished, 2 in progress). Current attribution: each ticket counts once, in the row of the first value of its first team column; the other values and the other team columns attribute nothing. Teams are recognised by the columns of the same name and by the separator ";" in a cell (team_separator setting of flux.yaml).


## Time in segment

Time spent in each segment of statuses (segments setting of flux.yaml), from the status history, in calendar days (differences of dates), initial status included. The time of a ticket adds up over all its visits to the segment. Computed to be compared with the Jira Control Chart, on the same statuses and the same dates.

- Coverage: 88 tickets out of 94 (delivered during the period or in progress) have a history (94%).
- WARNING: 3 ticket(s) have an unreadable transition date in the cache; their transitions are ignored and their time in segment is wrong. Run the collection again with --refresh.

### Tickets that left a segment during the period (cumulative time in the segment)

| Segment | Tickets | P50 | P85 | Mean |
|---|---|---|---|---|
| Definition | 85 | 3 d | 4 d | 3.2 d |
| Ready | 86 | 3 d | 4 d | 2.8 d |
| Implementation | 44 | 36 d | 65 d | 37.2 d |
| Review and verification | 0 | n/a | n/a | n/a |
| Acceptance | 0 | n/a | n/a | n/a |

### Tickets still in a segment (age of the current visit)

| Segment | Tickets | Age P50 | Age P85 |
|---|---|---|---|
| Definition | 0 | n/a | n/a |
| Ready | 0 | n/a | n/a |
| Implementation | 64 | 116 d | 932 d |
| Review and verification | 0 | n/a | n/a |
| Acceptance | 0 | n/a | n/a |

### Delivery lead time

From the commitment point (entry into the segment "Ready") to resolution, for the 44 tickets delivered during the period that went through it (1 delivered ticket(s) with a history but no commitment point are not counted).

- Since commitment: P50 40 d · P70 48 d · P85 68 d · P95 82 d.
- Since creation, for the same tickets: P50 46 d · P70 55 d · P85 74 d · P95 88 d. The lead time of all delivered items is higher up in the report.

### Flow efficiency

- Share of time in an active status, between the commitment point and resolution (the waiting statuses are those of waiting_states): 92% at P50 per ticket (43 tickets), 93% in aggregate value (total active time over total time).

### By team

| Team | Coverage | Delivered with commitment | Delivery lead time P50 | P85 | Efficiency P50 | Aggregate efficiency |
|---|---|---|---|---|---|---|
| (no team) | 100% | 2 | 50 d | 74 d | 92% | 95% |
| Team A | 88% | 4 | 30 d | 68 d | 84% | 92% |
| Team B | 100% | 0 | n/a | n/a | n/a | n/a |
| Team C | 100% | 2 | 46 d | 47 d | 93% | 93% |
| Team D | 93% | 6 | 28 d | 44 d | 90% | 90% |
| Team E | 100% | 4 | 44 d | 55 d | 93% | 94% |
| Team F | 100% | 3 | 66 d | 78 d | 95% | 94% |
| Team G | 100% | 5 | 36 d | 55 d | 92% | 92% |
| Team H | 90% | 6 | 22 d | 46 d | 82% | 91% |
| Team I | 86% | 3 | 26 d | 60 d | 96% | 93% |
| Team J | 100% | 1 | 66 d | 66 d | 95% | 95% |
| Team K | 88% | 6 | 34 d | 66 d | 89% | 91% |
| Team L | 100% | 2 | 40 d | 64 d | 78% | 94% |

Tickets that left each segment during the period, by team (count, P50 of the cumulative time):

| Team | Definition | Ready | Implementation | Review and verification | Acceptance |
|---|---|---|---|---|---|
| (no team) | 2 · 4 d | 2 · 2 d | 2 · 48 d | 0 · n/a | 0 · n/a |
| Team A | 8 · 4 d | 8 · 2 d | 5 · 26 d | 0 · n/a | 0 · n/a |
| Team B | 2 · 2 d | 2 · 3 d | 0 · n/a | 0 · n/a | 0 · n/a |
| Team C | 8 · 4 d | 8 · 3 d | 2 · 43 d | 0 · n/a | 0 · n/a |
| Team D | 11 · 4 d | 12 · 3 d | 4 · 38 d | 0 · n/a | 0 · n/a |
| Team E | 6 · 3 d | 6 · 2 d | 4 · 42 d | 0 · n/a | 0 · n/a |
| Team F | 6 · 3 d | 7 · 3 d | 3 · 63 d | 0 · n/a | 0 · n/a |
| Team G | 6 · 3 d | 7 · 3 d | 5 · 35 d | 0 · n/a | 0 · n/a |
| Team H | 6 · 4 d | 6 · 3 d | 6 · 19 d | 0 · n/a | 0 · n/a |
| Team I | 7 · 3 d | 6 · 3 d | 4 · 22 d | 0 · n/a | 0 · n/a |
| Team J | 6 · 2 d | 5 · 3 d | 1 · 63 d | 0 · n/a | 0 · n/a |
| Team K | 12 · 2 d | 12 · 4 d | 6 · 30 d | 0 · n/a | 0 · n/a |
| Team L | 5 · 4 d | 5 · 2 d | 2 · 38 d | 0 · n/a | 0 · n/a |

Tickets still in each segment, by team (count, age P50):

| Team | Definition | Ready | Implementation | Review and verification | Acceptance |
|---|---|---|---|---|---|
| (no team) | 0 · n/a | 0 · n/a | 1 · 189 d | 0 · n/a | 0 · n/a |
| Team A | 0 · n/a | 0 · n/a | 4 · 136 d | 0 · n/a | 0 · n/a |
| Team B | 0 · n/a | 0 · n/a | 2 · 86 d | 0 · n/a | 0 · n/a |
| Team C | 0 · n/a | 0 · n/a | 6 · 115 d | 0 · n/a | 0 · n/a |
| Team D | 0 · n/a | 0 · n/a | 10 · 178 d | 0 · n/a | 0 · n/a |
| Team E | 0 · n/a | 0 · n/a | 2 · 123 d | 0 · n/a | 0 · n/a |
| Team F | 0 · n/a | 0 · n/a | 7 · 118 d | 0 · n/a | 0 · n/a |
| Team G | 0 · n/a | 0 · n/a | 4 · 184 d | 0 · n/a | 0 · n/a |
| Team H | 0 · n/a | 0 · n/a | 5 · 189 d | 0 · n/a | 0 · n/a |
| Team I | 0 · n/a | 0 · n/a | 3 · 96 d | 0 · n/a | 0 · n/a |
| Team J | 0 · n/a | 0 · n/a | 4 · 60 d | 0 · n/a | 0 · n/a |
| Team K | 0 · n/a | 0 · n/a | 10 · 92 d | 0 · n/a | 0 · n/a |
| Team L | 0 · n/a | 0 · n/a | 6 · 66 d | 0 · n/a | 0 · n/a |

Below about ten tickets, a P85 is fragile: read it as a question, not as a finding.

Teams are not compared with each other: workflows, ticket sizes and types of work differ. Each row is first for the team concerned.

## Monte Carlo forecasts (10,000 simulations on the weekly throughput of the period)
- Finish 40 items: 22 weeks with a 50% chance, 28 with 85%, 31 with 95%.
- By 2026-11-15: at least 7 items with an 85% chance (9 with 50%, 5 with 95%).

## How to read this report

- **P50 (median)**: half of the items are below, half are above. It is the typical case.
- **P85**: 85% of the items are below, 15% above. It is used to make commitments: "in 85% of cases, less than X days". P70 and P95 read the same way, with 70% and 95%.
- **Why percentiles rather than an average**: a few very long tickets pull the average up. Percentiles are not dragged along by these extreme cases.
- **Lead time**: from creation to resolution, for finished items only. **Age**: since the last status category change (creation date if there is none), for items still in progress. Lead time only sees what finishes; age shows what stays stuck.
- **WIP**: items in progress. **Active WIP**: being worked on right now. **Waiting WIP**: in a waiting status listed in flux.yaml, such as "Ready for". **Dormant WIP**: not finished and with no status change for more than 365 days (inferred from the status history, option --dormant-from-history). A dormant ticket is neither active nor waiting.
- **Arrivals and departures**: tickets created and items finished, week by week. If arrivals keep exceeding departures, the stock grows. Arrivals also count rejected tickets.
- **Little's law**: the number of items in progress divided by the average throughput gives an average time in the system. Read it with care when arrivals keep exceeding departures.
- **Monte Carlo forecast**: 10,000 draws from the throughput of past weeks. It says in how many weeks of throughput the current stock would drain if nothing new came in. It is not a date.
- **Segment**: a group of consecutive workflow statuses (definition, ready, implementation, review and verification, acceptance), set in flux.yaml. **Time in segment**: how many days a ticket spent in the statuses of the segment, in calendar days, initial status included; the time adds up if the ticket comes back to the segment. "Left the segment" means: moved to another segment during the period.
- **Commitment point**: the moment the team commits, here the entry into the segment set by commitment_point. **Delivery lead time**: from the commitment point to resolution; it is shorter than the lead time from creation, which also counts the wait in the backlog.
- **Flow efficiency**: the share of time spent in an active status, between the commitment point and resolution. A waiting status (waiting_states) counts as time lost waiting, any other status as active time. A low efficiency says tickets wait a lot, not that people work badly.
- **Coverage**: the share of the tickets in the report whose history is known. Below 90%, the figures for time in segment only describe part of the tickets.
- **Batched closure**: at least N delivered tickets of the same project whose resolution falls in the same minute (N: batch_closure_threshold in flux.yaml). It most likely points to a bulk status change (clean-up, migration) rather than deliveries as they happen. A count only: these tickets stay in the throughput.
- **Shared tickets**: a ticket carried by several teams counts once, for its first team. For each team, the first column counts the tickets attributed to it while shared, the second those it carries without their being attributed to it. A cell under 5 tickets is written "masked".

Examples taken from this report:
- The P85 age of items in progress is 941 days: 15% of the items in progress have been there for more than 941 days.
- The P85 lead time is 73 days: 85% of the finished items were finished in less than 73 days.
- The aggregate flow efficiency is 93%: out of 100 days spent between the commitment point and resolution, 93 were in an active status and 7 waiting.

## Limits
- Lead time counts from the creation of the ticket, waiting in the backlog included: it is not a cycle time.
- Forecasts assume that the throughput of the coming weeks will look like that of the period, and that items are of comparable size.

Report: <WS>/Flux-Lab/rapports/flux-s-2026-10-04.md
Aging WIP points: 46 ticket(s) in progress, no key: <WS>/Flux-Lab/tableaux/points-s-2026-10-04.json

========================================================================

# Flow evolution: s, from 2026-09-20 to 2026-10-04

Compares the reports of 2026-09-20 and 2026-10-04 (14 days apart), computed locally from two Jira exports. Aggregates only: no ticket is quoted or followed.

## What moved

- Throughput up: 8.0 items per week over the 2 new week(s), against 1.8 over the 4 weeks before (+357%).
- Little's law: an item would stay in progress for about 131 days, against 181 (-28%).
- More items in progress for more than 90 days: 27 → 29.
- More items in progress older than the P85 lead time: 29 → 37.
- Team D: throughput up, 0.2 → 1.5 per week (+500%).
- Team E: throughput up, 0.2 → 1.0 per week (+300%).
- Team K: throughput up, 0.2 → 1.5 per week (+500%).

Thresholds: throughput ±25% (±30% per team), lead time P85 ±20%, WIP and Little's law ±20%, any increase in aging (at least 3 more items of over 90 days for a team); batched closures when 2 weeks carry at least 60% of the items finished in the last 8 weeks. Each signal is a question to ask the teams, not a conclusion.

## Comparability

- Windows of different sizes: 23 then 25 weeks.

## Throughput

- New weeks (2): 8.0 per week, against 1.8 over the last 4 weeks of the previous report.
- Average over the whole window: 1.4 → 1.9 (+38%); zero weeks: 3 → 3.
- Series of the new report, from the oldest to the most recent: 2, 0, 1, 0, 1, 1, 1, 2, 0, 1, 3, 2, 1, 2, 1, 1, 2, 1, 3, 2, 1, 3, 1, 3, 13.

## Lead time (from creation to resolution)

| Scope | P50 | P85 |
|---|---|---|
| All types | 46 d → 44 d (-3%) | 80 d → 73 d (-9%) |
| Bug | 54 d → 50 d (-7%) | 71 d → 69 d (-3%) |
| Story | 33 d → 32 d (-3%) | 69 d → 62 d (-11%) |
| Task | 80 d → 62 d (-22%) | 88 d → 86 d (-3%) |

## Work in progress

- In progress: 46 → 46 (+0%); to do: 29 → 29 (+0%).
- Little's law: 181 d → 131 d (-28%).

| Status | Before | After |
|---|---|---|
| Doing | 14 | 14 |
| In Review | 12 | 12 |
| In Progress | 10 | 10 |
| Validation | 10 | 10 |

## Aging of the items in progress

| In progress for more than | Before | After |
|---|---|---|
| 30 days | 42 | 44 |
| 90 days | 27 | 29 |
| 180 days | 11 | 14 |
| 365 days | 10 | 10 |
| 730 days | 10 | 10 |
| more than the P85 lead time | 29 | 37 |

## Queues before commitment

| To do status | Items | Age P50 since creation | Over 90 d |
|---|---|---|---|
| Open | 15 → 15 (+0%) | 154 d → 168 d (+9%) | 10 → 12 |
| Waiting | 14 → 14 (+0%) | 72 d → 86 d (+19%) | 6 → 7 |

## By team

| Team | Recent throughput / wk | Lead time P85 | WIP | WIP > 90 d | Closures in 2 weeks |
|---|---|---|---|---|---|
| (no team) | 0.2 → 0.0 (-100%) | 80 d → 80 d (+0%) | 1 → 1 (+0%) | 1 → 1 | n/a → n/a |
| Team A | 0.2 → 0.0 (-100%) | 70 d → 70 d (+0%) | 3 → 3 (+0%) | 2 → 2 | n/a → n/a |
| Team B | 0.0 → 0.0 | n/a → n/a | 1 → 1 (+0%) | 1 → 1 | n/a → n/a |
| Team C | 0.0 → 0.5 | 50 d → 53 d (+5%) | 3 → 3 (+0%) | 2 → 2 | n/a → n/a |
| Team D | 0.2 → 1.5 (+500%) | 44 d → 51 d (+16%) | 9 → 9 (+0%) | 7 → 7 | n/a → n/a |
| Team E | 0.2 → 1.0 (+300%) | 61 d → 62 d (+1%) | 1 → 1 (+0%) | 0 → 1 | n/a → n/a |
| Team F | 0.0 → 0.0 | 84 d → 84 d (+0%) | 4 → 4 (+0%) | 4 → 4 | n/a → n/a |
| Team G | 0.0 → 1.5 | 50 d → 60 d (+20%) | 3 → 3 (+0%) | 2 → 2 | n/a → n/a |
| Team H | 0.0 → 1.0 | 62 d → 56 d (-10%) | 3 → 3 (+0%) | 2 → 2 | n/a → n/a |
| Team I | 0.0 → 0.5 | 74 d → 66 d (-10%) | 4 → 4 (+0%) | 1 → 2 | n/a → n/a |
| Team J | 0.5 → 0.0 (-100%) | 62 d → 62 d (+0%) | 4 → 4 (+0%) | 1 → 1 | n/a → n/a |
| Team K | 0.2 → 1.5 (+500%) | 78 d → 68 d (-13%) | 9 → 9 (+0%) | 4 → 4 | n/a → n/a |
| Team L | 0.0 → 0.5 | 80 d → 70 d (-13%) | 1 → 1 (+0%) | 0 → 0 | n/a → n/a |

"Closures in 2 weeks": share of the items finished over the last 8 weeks of each report that fall on its 2 best weeks (n/a below 5 items finished).

## Forecasts

- Before: 36 items in 30 weeks (85%). After: 40 items in 28 weeks (85%). Different targets: the durations cannot be compared directly.
- By 2026-11-15, at least (85%): 9 → 7 (-22%) items. The remaining time got shorter between the two reports: a decrease is expected.

## Limits

- The two windows overlap: over the common weeks, it is the same data. Only the new weeks say what changed in the throughput.
- Counts are net: an item that left the WIP and another that entered cancel each other out. The script keeps no ticket identifier, so it cannot say which items crossed a threshold.
- By team, the series are short: a gap of one or two units is enough to cross a threshold.

Evolution: <WS>/Flux-Lab/rapports/evolution-s-2026-10-04.md
--- stderr ---
written: rapports/evolution-s-2026-10-04.json
written: rapports/evolution-s-2026-10-04.md
written: rapports/flux-s-2026-10-04.json
written: rapports/flux-s-2026-10-04.md
written: tableaux/points-s-2026-10-04.json

===== compute-dormants-history =====
$ compute <WS>/a.csv <WS>/b.csv --name d --today 2026-10-04 --no-comparison --dormant-from-history --teams-only --types Story,Bug,Task --batch-closure-resolutions tous --scope tous
exit code: 0
--- stdout ---
--dormant-from-history: 13 dormant ticket(s) according to the history; 11 unfinished ticket(s) with no history in the cache, not counted as dormant; 10 in progress and 3 to do dormant.
# Flow metrics: d, as of 2026-10-04

Period: 2026-04-06 to 2026-09-27 (25 complete weeks). Types: Story,Bug,Task, tickets without a team excluded. Aggregates computed locally from a Jira export; no ticket is quoted.

Scope: all projects of the export (200 ticket(s) kept out of 200 read, option --scope).

Left out of throughput, lead time, WIP and forecasts (portfolio_types and excluded_projects in flux.yaml): 74 tickets; by type: Epic 27, RN Task 27; by project: BUG 20.

## Throughput
- 46 items finished, i.e. 1.8 per week on average (median 1); 3 week(s) with no item finished.
- Per week, from the oldest to the most recent: 2, 0, 1, 0, 1, 1, 1, 2, 0, 1, 3, 2, 1, 2, 1, 1, 1, 1, 3, 2, 1, 2, 1, 3, 13.
- Resolutions counted as delivered: Done 46.
- Closed without delivery, left out of throughput, lead time and forecasts: Won't Do 3.

## Arrivals and departures

Arrivals: tickets created during the period, same types and same exclusions as the throughput. Departures: finished items counted as delivered (the throughput). Difference: arrivals minus departures; when positive, the stock of open tickets grows, when negative, it shrinks.

| Week (start) | Arrivals | Departures | Difference |
|---|---|---|---|
| 2026-04-06 | 1 | 2 | -1 |
| 2026-04-13 | 3 | 0 | +3 |
| 2026-04-20 | 2 | 1 | +1 |
| 2026-04-27 | 4 | 0 | +4 |
| 2026-05-04 | 1 | 1 | 0 |
| 2026-05-11 | 1 | 1 | 0 |
| 2026-05-18 | 6 | 1 | +5 |
| 2026-05-25 | 4 | 2 | +2 |
| 2026-06-01 | 5 | 0 | +5 |
| 2026-06-08 | 5 | 1 | +4 |
| 2026-06-15 | 3 | 3 | 0 |
| 2026-06-22 | 3 | 2 | +1 |
| 2026-06-29 | 5 | 1 | +4 |
| 2026-07-06 | 6 | 2 | +4 |
| 2026-07-13 | 5 | 1 | +4 |
| 2026-07-20 | 0 | 1 | -1 |
| 2026-07-27 | 7 | 1 | +6 |
| 2026-08-03 | 5 | 1 | +4 |
| 2026-08-10 | 5 | 3 | +2 |
| 2026-08-17 | 6 | 2 | +4 |
| 2026-08-24 | 2 | 1 | +1 |
| 2026-08-31 | 1 | 2 | -1 |
| 2026-09-07 | 4 | 1 | +3 |
| 2026-09-14 | 7 | 3 | +4 |
| 2026-09-21 | 1 | 13 | -12 |
| **Total** | **92** | **46** | **+46** |

- Average per week: 3.7 arrivals, 1.8 departures.
- Note: tickets created then rejected, or left without movement, count in the arrivals but never in the departures (excluded closure resolutions are not throughput): the difference therefore does not measure a growth of the real work. A dormant ticket (more than 365 days) only enters the arrivals if its creation falls in the period, which implies a period of more than 52 weeks. Arrivals also depend on the export query.

- **First week truncated.** The export query filters `resolved >= -20w`: the window starts on 2026-05-17 (from the computation date), so the whole first week and more is missing from the export. The week of 2026-04-06 is underestimated (departures, and arrivals of tickets created then resolved before the window): leave it out of comparisons (series, averages, trends).

### By team

| Team | Arrivals | Departures | Difference |
|---|---|---|---|
| Team A | 10 | 5 | +5 |
| Team B | 2 | 0 | +2 |
| Team C | 10 | 2 | +8 |
| Team D | 11 | 6 | +5 |
| Team E | 6 | 4 | +2 |
| Team F | 7 | 3 | +4 |
| Team G | 6 | 5 | +1 |
| Team H | 7 | 7 | 0 |
| Team I | 8 | 3 | +5 |
| Team J | 6 | 2 | +4 |
| Team K | 14 | 7 | +7 |
| Team L | 5 | 2 | +3 |

Teams are not compared with each other: workflows, ticket sizes and types of work differ. Each row is first for the team concerned.

### Shared tickets by team

First-team attribution: each ticket counts once, for its first team.

| Team | Attributed here, shared | Carried here, attributed elsewhere |
|---|---|---|
| Team A | 5 | masked |
| Team B | masked | 5 |

## Batched closures

Delivered tickets (all resolutions counted as delivered) whose resolution falls in the same minute as that of at least 4 others of the same project (threshold of 5 tickets, batch_closure_threshold setting). A count only: these tickets stay in the throughput, the lead time and the forecasts.

| Project | Tickets in batched closures | Groups | Largest group | Delivered in the period | Share of throughput |
|---|---|---|---|---|---|
| DEF | 7 | 1 | 7 | 22 | 32% |
| ABC | 5 | 1 | 5 | 24 | 21% |
| **Total** | **12** | **2** | | **46** | **26%** |

## Lead time (from creation to resolution)
- All types: P50 44 d · P70 54 d · P85 72 d · P95 85 d.
- Bug (12 finished): P50 50 d · P70 54 d · P85 69 d · P95 73 d.
- Story (24 finished): P50 32 d · P70 46 d · P85 57 d · P95 72 d.
- Task (10 finished): P50 62 d · P70 80 d · P85 86 d · P95 89 d.

## Work in progress
- WIP: 45 items in progress (Doing 14, In Review 11, In Progress 10, Validation 10); 28 items to do.
- Age of items in progress since they started: P50 98 d · P70 118 d · P85 132 d · P95 184 d.
- Age since creation: P50 113 d · P70 167 d · P85 941 d · P95 941 d.
- 36 item(s) in progress are older (basis: creation) than the P85 lead time of finished items.
- Items in progress for more than 30 / 90 / 180 / 365 / 730 days: 43 / 28 / 13 / 10 / 10.
- Active WIP: 35 (78%); waiting WIP: 0 (0%); dormant WIP: 10 (22%). A dormant ticket is taken out of the other two categories; the total WIP stays 45.
- To do: 25 excluding dormant, 3 dormant (11% of the 28).
- Note: a ticket is dormant when it is unfinished, created at least 365 days ago, with no status change for at least 365 days, according to the status history (date of the last transition, or of creation if there is none). 11 unfinished ticket(s) with no history in the cache are not counted as dormant. No key is written here.
- "In progress" and "to do" are decided by the Jira status category (column "Status Category"); the lists in flux.yaml only serve for tickets with no category.

### Age by status (basis: creation)

| Status | Nature | Items | Age P50 | Age P85 | Over 90 d | Over 365 d | Dormant | Dormant share |
|---|---|---|---|---|---|---|---|---|
| Doing | active | 14 | 83 d | 941 d | 6 | 3 | 3 | 21% |
| In Review | active | 11 | 132 d | 941 d | 8 | 5 | 5 | 45% |
| In Progress | active | 10 | 116 d | 183 d | 8 | 1 | 1 | 10% |
| Validation | active | 10 | 104 d | 121 d | 6 | 1 | 1 | 10% |

### Queues before commitment: age of the items to do, by status

An item can wait a long time before it is started: this time counts neither in the WIP nor in the lead time of an item that is not finished yet. "Since the category" starts at the last Jira status category change (entering analysis or definition, for example), when it is known.

| To do status | Items | Age P50 (creation) | Age P85 (creation) | Age P50 (category) | Over 90 d | Over 365 d | Dormant |
|---|---|---|---|---|---|---|---|
| Open | 14 | 163 d | 236 d | n/a | 11 | 2 | 2 |
| Waiting | 14 | 86 d | 237 d | n/a | 7 | 2 | 1 |

- Little's law on the non-dormant WIP (35 items, active and waiting) divided by the average throughput: at this pace, an item stays in progress for about 133 days on average; compare with the age of the items in progress and with the median lead time. For comparison, on the total WIP (45 items): about 171 days.

## By team

| Team | Finished | Throughput / wk | Lead time P50 | Lead time P85 | WIP | WIP age P50 | WIP > 90 d | Active WIP | Waiting WIP | Dormant WIP | Active share | Waiting share | Dormant share | To do | Dormant to do |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Team A | 5 | 0.2 | 14 d | 70 d | 3 | 129 d | 2 | 2 | 0 | 1 | 67% | 0% | 33% | 3 | 0 |
| Team B | 0 | 0.0 | n/a | n/a | 1 | 172 d | 1 | 1 | 0 | 0 | 100% | 0% | 0% | 1 | 0 |
| Team C | 2 | 0.1 | 52 d | 53 d | 3 | 111 d | 2 | 3 | 0 | 0 | 100% | 0% | 0% | 5 | 0 |
| Team D | 6 | 0.2 | 34 d | 51 d | 9 | 182 d | 7 | 6 | 0 | 3 | 67% | 0% | 33% | 3 | 1 |
| Team E | 4 | 0.2 | 51 d | 62 d | 1 | 98 d | 1 | 1 | 0 | 0 | 100% | 0% | 0% | 2 | 0 |
| Team F | 3 | 0.1 | 71 d | 84 d | 4 | 130 d | 4 | 3 | 0 | 1 | 75% | 0% | 25% | 4 | 0 |
| Team G | 5 | 0.2 | 43 d | 60 d | 3 | 189 d | 2 | 2 | 0 | 1 | 67% | 0% | 33% | 1 | 0 |
| Team H | 7 | 0.3 | 42 d | 56 d | 3 | 941 d | 2 | 1 | 0 | 2 | 33% | 0% | 67% | 2 | 0 |
| Team I | 3 | 0.1 | 32 d | 66 d | 4 | 70 d | 2 | 4 | 0 | 0 | 100% | 0% | 0% | 0 | 0 |
| Team J | 2 | 0.1 | 38 d | 62 d | 4 | 66 d | 1 | 4 | 0 | 0 | 100% | 0% | 0% | 0 | 0 |
| Team K | 7 | 0.3 | 35 d | 68 d | 9 | 89 d | 4 | 7 | 0 | 2 | 78% | 0% | 22% | 2 | 1 |
| Team L | 2 | 0.1 | 46 d | 70 d | 1 | 18 d | 0 | 1 | 0 | 0 | 100% | 0% | 0% | 5 | 1 |

Teams are not compared with each other: workflows, ticket sizes and types of work differ. Each row is first for the team concerned.

Items finished per week and per team, from the oldest to the most recent (zero weeks between two peaks point to batched closures):

- Team A: 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0
- Team B: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
- Team C: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1
- Team D: 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 3
- Team E: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 2
- Team F: 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0
- Team G: 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 3
- Team H: 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1
- Team I: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0
- Team J: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0
- Team K: 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 2
- Team L: 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1

Tickets with several teams: 5 out of 122 (1 finished, 2 in progress). Current attribution: each ticket counts once, in the row of the first value of its first team column; the other values and the other team columns attribute nothing. Teams are recognised by the columns of the same name and by the separator ";" in a cell (team_separator setting of flux.yaml).


## Monte Carlo forecasts (10,000 simulations on the weekly throughput of the period)
- Finish 35 items (non-dormant WIP, active and waiting): 20 weeks with a 50% chance, 26 with 85%, 29 with 95%.
- Note, for comparison, on the total WIP (45 items, dormant included): 25 weeks with a 50% chance, 32 with 85%, 36 with 95%.

## How to read this report

- **P50 (median)**: half of the items are below, half are above. It is the typical case.
- **P85**: 85% of the items are below, 15% above. It is used to make commitments: "in 85% of cases, less than X days". P70 and P95 read the same way, with 70% and 95%.
- **Why percentiles rather than an average**: a few very long tickets pull the average up. Percentiles are not dragged along by these extreme cases.
- **Lead time**: from creation to resolution, for finished items only. **Age**: since the last status category change (creation date if there is none), for items still in progress. Lead time only sees what finishes; age shows what stays stuck.
- **WIP**: items in progress. **Active WIP**: being worked on right now. **Waiting WIP**: in a waiting status listed in flux.yaml, such as "Ready for". **Dormant WIP**: not finished and with no status change for more than 365 days (inferred from the status history, option --dormant-from-history). A dormant ticket is neither active nor waiting.
- **Arrivals and departures**: tickets created and items finished, week by week. If arrivals keep exceeding departures, the stock grows. Arrivals also count rejected tickets.
- **Little's law**: the number of items in progress divided by the average throughput gives an average time in the system. Read it with care when arrivals keep exceeding departures.
- **Monte Carlo forecast**: 10,000 draws from the throughput of past weeks. It says in how many weeks of throughput the current stock would drain if nothing new came in. It is not a date.
- **Batched closure**: at least N delivered tickets of the same project whose resolution falls in the same minute (N: batch_closure_threshold in flux.yaml). It most likely points to a bulk status change (clean-up, migration) rather than deliveries as they happen. A count only: these tickets stay in the throughput.
- **Shared tickets**: a ticket carried by several teams counts once, for its first team. For each team, the first column counts the tickets attributed to it while shared, the second those it carries without their being attributed to it. A cell under 5 tickets is written "masked".

Examples taken from this report:
- The P85 age of items in progress is 941 days: 15% of the items in progress have been there for more than 941 days.
- The P85 lead time is 72 days: 85% of the finished items were finished in less than 72 days.

## Limits
- Lead time counts from the creation of the ticket, waiting in the backlog included: it is not a cycle time.
- Forecasts assume that the throughput of the coming weeks will look like that of the period, and that items are of comparable size.

Report: <WS>/Flux-Lab/rapports/flux-d-2026-10-04.md
--- stderr ---
written: rapports/flux-d-2026-10-04.json
written: rapports/flux-d-2026-10-04.md

===== compute-simple =====
$ compute <WS>/a.csv --today 2026-10-04 --no-comparison --weeks 8
exit code: 0
--- stdout ---
# Flow metrics, as of 2026-10-04

Period: 2026-08-03 to 2026-09-27 (8 complete weeks). Types: all. Aggregates computed locally from a Jira export; no ticket is quoted.

Left out of throughput, lead time, WIP and forecasts (portfolio_types and excluded_projects in flux.yaml): 27 tickets; by type: Epic 27.

## Throughput
- 14 items finished, i.e. 1.8 per week on average (median 1); 1 week(s) with no item finished.
- Per week, from the oldest to the most recent: 1, 1, 1, 1, 3, 0, 1, 6.
- Resolutions counted as delivered: Done 14.
- Closed without delivery, left out of throughput, lead time and forecasts: none.

## Arrivals and departures

Arrivals: tickets created during the period, same types and same exclusions as the throughput. Departures: finished items counted as delivered (the throughput). Difference: arrivals minus departures; when positive, the stock of open tickets grows, when negative, it shrinks.

| Week (start) | Arrivals | Departures | Difference |
|---|---|---|---|
| 2026-08-03 | 0 | 1 | -1 |
| 2026-08-10 | 2 | 1 | +1 |
| 2026-08-17 | 2 | 1 | +1 |
| 2026-08-24 | 0 | 1 | -1 |
| 2026-08-31 | 1 | 3 | -2 |
| 2026-09-07 | 2 | 0 | +2 |
| 2026-09-14 | 5 | 1 | +4 |
| 2026-09-21 | 0 | 6 | -6 |
| **Total** | **12** | **14** | **-2** |

- Average per week: 1.5 arrivals, 1.8 departures.
- Note: tickets created then rejected, or left without movement, count in the arrivals but never in the departures (excluded closure resolutions are not throughput): the difference therefore does not measure a growth of the real work. A dormant ticket (more than 365 days) only enters the arrivals if its creation falls in the period, which implies a period of more than 52 weeks. Arrivals also depend on the export query.

### By team

| Team | Arrivals | Departures | Difference |
|---|---|---|---|
| (no team) | 0 | 1 | -1 |
| Team A | 1 | 1 | 0 |
| Team D | 2 | 2 | 0 |
| Team G | 1 | 3 | -2 |
| Team I | 2 | 2 | 0 |
| Team J | 1 | 1 | 0 |
| Team K | 3 | 3 | 0 |
| Team L | 2 | 1 | +1 |

### Shared tickets by team

First-team attribution: each ticket counts once, for its first team.

| Team | Attributed here, shared | Carried here, attributed elsewhere |
|---|---|---|
| Team A | 5 | masked |
| Team B | masked | 5 |

## Batched closures

Delivered tickets (resolution: done) whose resolution falls in the same minute as that of at least 4 others of the same project (threshold of 5 tickets, batch_closure_threshold setting). A count only: these tickets stay in the throughput, the lead time and the forecasts.

| Project | Tickets in batched closures | Groups | Largest group | Delivered in the period | Share of throughput |
|---|---|---|---|---|---|
| ABC | 5 | 1 | 5 | 14 | 36% |
| **Total** | **5** | **1** | | **14** | **36%** |

## Lead time (from creation to resolution)
- All types: P50 33 d · P70 74 d · P85 86 d · P95 89 d.
- Story (8 finished): P50 30 d · P70 69 d · P85 85 d · P95 89 d.
- Task (6 finished): P50 52 d · P70 76 d · P85 83 d · P95 86 d.

## Work in progress
- WIP: 22 items in progress (In Review 12, In Progress 10); 15 items to do.
- Age of items in progress since they started: P50 116 d · P70 130 d · P85 163 d · P95 191 d.
- Age since creation: P50 132 d · P70 197 d · P85 941 d · P95 941 d.
- 18 item(s) in progress are older (basis: creation) than the P85 lead time of finished items.
- Items in progress for more than 30 / 90 / 180 / 365 / 730 days: 21 / 17 / 8 / 6 / 6.
- Active WIP: 22; waiting WIP: 0 (waiting statuses of flux.yaml: none); share of waiting in the WIP: 0%. The total WIP stays 22.
- "In progress" and "to do" are decided by the Jira status category (column "Status Category"); the lists in flux.yaml only serve for tickets with no category.

### Age by status (basis: creation)

| Status | Nature | Items | Age P50 | Age P85 | Over 90 d | Over 365 d |
|---|---|---|---|---|---|---|
| In Review | active | 12 | 164 d | 941 d | 9 | 5 |
| In Progress | active | 10 | 116 d | 183 d | 8 | 1 |

### Queues before commitment: age of the items to do, by status

An item can wait a long time before it is started: this time counts neither in the WIP nor in the lead time of an item that is not finished yet. "Since the category" starts at the last Jira status category change (entering analysis or definition, for example), when it is known.

| To do status | Items | Age P50 (creation) | Age P85 (creation) | Age P50 (category) | Over 90 d | Over 365 d |
|---|---|---|---|---|---|---|
| Open | 15 | 168 d | 867 d | n/a | 12 | 3 |

- Little's law (current WIP / average throughput): at this pace, an item stays in progress for about 88 days on average; compare with the age of the items in progress and with the median lead time.

## By team

| Team | Finished | Throughput / wk | Lead time P50 | Lead time P85 | WIP | WIP age P50 | WIP > 90 d | Waiting WIP | Waiting share |
|---|---|---|---|---|---|---|---|---|---|
| (no team) | 1 | 0.1 | 90 d | 90 d | 1 | 197 d | 1 | 0 | 0% |
| Team A | 1 | 0.1 | 86 d | 86 d | 2 | 535 d | 2 | 0 | 0% |
| Team B | 0 | 0.0 | n/a | n/a | 1 | 172 d | 1 | 0 | 0% |
| Team C | 0 | 0.0 | n/a | n/a | 2 | 122 d | 2 | 0 | 0% |
| Team D | 2 | 0.2 | 8 d | 8 d | 1 | 941 d | 1 | 0 | 0% |
| Team F | 0 | 0.0 | n/a | n/a | 2 | 130 d | 2 | 0 | 0% |
| Team G | 3 | 0.4 | 34 d | 60 d | 1 | 189 d | 1 | 0 | 0% |
| Team H | 0 | 0.0 | n/a | n/a | 2 | 942 d | 2 | 0 | 0% |
| Team I | 2 | 0.2 | 56 d | 74 d | 2 | 58 d | 1 | 0 | 0% |
| Team J | 1 | 0.1 | 73 d | 73 d | 3 | 82 d | 1 | 0 | 0% |
| Team K | 3 | 0.4 | 26 d | 69 d | 5 | 122 d | 3 | 0 | 0% |
| Team L | 1 | 0.1 | 12 d | 12 d | 0 | n/a | 0 | 0 | n/a |

Teams are not compared with each other: workflows, ticket sizes and types of work differ. Each row is first for the team concerned.

Items finished per week and per team, from the oldest to the most recent (zero weeks between two peaks point to batched closures):

- (no team): 0, 0, 0, 0, 1, 0, 0, 0
- Team A: 0, 0, 1, 0, 0, 0, 0, 0
- Team B: 0, 0, 0, 0, 0, 0, 0, 0
- Team C: 0, 0, 0, 0, 0, 0, 0, 0
- Team D: 0, 0, 0, 1, 0, 0, 0, 1
- Team F: 0, 0, 0, 0, 0, 0, 0, 0
- Team G: 0, 1, 0, 0, 0, 0, 0, 2
- Team H: 0, 0, 0, 0, 0, 0, 0, 0
- Team I: 1, 0, 0, 0, 0, 0, 1, 0
- Team J: 0, 0, 0, 0, 1, 0, 0, 0
- Team K: 0, 0, 0, 0, 1, 0, 0, 2
- Team L: 0, 0, 0, 0, 0, 0, 0, 1

Tickets with several teams: 5 out of 63 (0 finished, 2 in progress). Current attribution: each ticket counts once, in the row of the first value of its first team column; the other values and the other team columns attribute nothing. Teams are recognised by the columns of the same name and by the separator ";" in a cell (team_separator setting of flux.yaml).


## Monte Carlo forecasts (10,000 simulations on the weekly throughput of the period)
- Finish 22 items: 13 weeks with a 50% chance, 17 with 85%, 20 with 95%.

## How to read this report

- **P50 (median)**: half of the items are below, half are above. It is the typical case.
- **P85**: 85% of the items are below, 15% above. It is used to make commitments: "in 85% of cases, less than X days". P70 and P95 read the same way, with 70% and 95%.
- **Why percentiles rather than an average**: a few very long tickets pull the average up. Percentiles are not dragged along by these extreme cases.
- **Lead time**: from creation to resolution, for finished items only. **Age**: since the last status category change (creation date if there is none), for items still in progress. Lead time only sees what finishes; age shows what stays stuck.
- **WIP**: items in progress. **Active WIP**: being worked on right now. **Waiting WIP**: in a waiting status listed in flux.yaml, such as "Ready for". **Dormant WIP**: not finished and with no status change for more than 365 days (inferred from the status history, option --dormant-from-history). A dormant ticket is neither active nor waiting.
- **Arrivals and departures**: tickets created and items finished, week by week. If arrivals keep exceeding departures, the stock grows. Arrivals also count rejected tickets.
- **Little's law**: the number of items in progress divided by the average throughput gives an average time in the system. Read it with care when arrivals keep exceeding departures.
- **Monte Carlo forecast**: 10,000 draws from the throughput of past weeks. It says in how many weeks of throughput the current stock would drain if nothing new came in. It is not a date.
- **Batched closure**: at least N delivered tickets of the same project whose resolution falls in the same minute (N: batch_closure_threshold in flux.yaml). It most likely points to a bulk status change (clean-up, migration) rather than deliveries as they happen. A count only: these tickets stay in the throughput.
- **Shared tickets**: a ticket carried by several teams counts once, for its first team. For each team, the first column counts the tickets attributed to it while shared, the second those it carries without their being attributed to it. A cell under 5 tickets is written "masked".

Examples taken from this report:
- The P85 age of items in progress is 941 days: 15% of the items in progress have been there for more than 941 days.
- The P85 lead time is 86 days: 85% of the finished items were finished in less than 86 days.

## Limits
- Lead time counts from the creation of the ticket, waiting in the backlog included: it is not a cycle time.
- Forecasts assume that the throughput of the coming weeks will look like that of the period, and that items are of comparable size.

Report: <WS>/Flux-Lab/rapports/flux-2026-10-04.md
--- stderr ---
written: rapports/flux-2026-10-04.json
written: rapports/flux-2026-10-04.md

===== compute-simple-no-earlier-report =====
$ compute <WS>/a.csv --today 2026-10-04
exit code: 0
--- stdout ---
# Flow metrics, as of 2026-10-04

Period: 2026-04-20 to 2026-09-27 (23 complete weeks). Types: all. Aggregates computed locally from a Jira export; no ticket is quoted.

Left out of throughput, lead time, WIP and forecasts (portfolio_types and excluded_projects in flux.yaml): 27 tickets; by type: Epic 27.

## Throughput
- 26 items finished, i.e. 1.1 per week on average (median 1); 6 week(s) with no item finished.
- Per week, from the oldest to the most recent: 1, 0, 0, 1, 1, 0, 0, 1, 2, 1, 1, 1, 0, 1, 2, 1, 1, 1, 1, 3, 0, 1, 6.
- Resolutions counted as delivered: Done 26.
- Closed without delivery, left out of throughput, lead time and forecasts: none.

## Arrivals and departures

Arrivals: tickets created during the period, same types and same exclusions as the throughput. Departures: finished items counted as delivered (the throughput). Difference: arrivals minus departures; when positive, the stock of open tickets grows, when negative, it shrinks.

| Week (start) | Arrivals | Departures | Difference |
|---|---|---|---|
| 2026-04-20 | 1 | 1 | 0 |
| 2026-04-27 | 2 | 0 | +2 |
| 2026-05-04 | 1 | 0 | +1 |
| 2026-05-11 | 1 | 1 | 0 |
| 2026-05-18 | 5 | 1 | +4 |
| 2026-05-25 | 2 | 0 | +2 |
| 2026-06-01 | 3 | 0 | +3 |
| 2026-06-08 | 1 | 1 | 0 |
| 2026-06-15 | 3 | 2 | +1 |
| 2026-06-22 | 2 | 1 | +1 |
| 2026-06-29 | 3 | 1 | +2 |
| 2026-07-06 | 3 | 1 | +2 |
| 2026-07-13 | 2 | 0 | +2 |
| 2026-07-20 | 0 | 1 | -1 |
| 2026-07-27 | 1 | 2 | -1 |
| 2026-08-03 | 0 | 1 | -1 |
| 2026-08-10 | 2 | 1 | +1 |
| 2026-08-17 | 2 | 1 | +1 |
| 2026-08-24 | 0 | 1 | -1 |
| 2026-08-31 | 1 | 3 | -2 |
| 2026-09-07 | 2 | 0 | +2 |
| 2026-09-14 | 5 | 1 | +4 |
| 2026-09-21 | 0 | 6 | -6 |
| **Total** | **42** | **26** | **+16** |

- Average per week: 1.8 arrivals, 1.1 departures.
- Note: tickets created then rejected, or left without movement, count in the arrivals but never in the departures (excluded closure resolutions are not throughput): the difference therefore does not measure a growth of the real work. A dormant ticket (more than 365 days) only enters the arrivals if its creation falls in the period, which implies a period of more than 52 weeks. Arrivals also depend on the export query.

- **First week truncated.** The export query filters `resolved >= -20w`: the window starts on 2026-05-17 (from the computation date), so the whole first week and more is missing from the export. The week of 2026-04-20 is underestimated (departures, and arrivals of tickets created then resolved before the window): leave it out of comparisons (series, averages, trends).

### By team

| Team | Arrivals | Departures | Difference |
|---|---|---|---|
| (no team) | 2 | 2 | 0 |
| Team A | 7 | 4 | +3 |
| Team C | 4 | 0 | +4 |
| Team D | 4 | 4 | 0 |
| Team E | 1 | 1 | 0 |
| Team F | 3 | 1 | +2 |
| Team G | 3 | 4 | -1 |
| Team H | 1 | 1 | 0 |
| Team I | 4 | 2 | +2 |
| Team J | 4 | 1 | +3 |
| Team K | 7 | 4 | +3 |
| Team L | 2 | 2 | 0 |

Teams are not compared with each other: workflows, ticket sizes and types of work differ. Each row is first for the team concerned.

### Shared tickets by team

First-team attribution: each ticket counts once, for its first team.

| Team | Attributed here, shared | Carried here, attributed elsewhere |
|---|---|---|
| Team A | 5 | masked |
| Team B | masked | 5 |

## Batched closures

Delivered tickets (resolution: done) whose resolution falls in the same minute as that of at least 4 others of the same project (threshold of 5 tickets, batch_closure_threshold setting). A count only: these tickets stay in the throughput, the lead time and the forecasts.

| Project | Tickets in batched closures | Groups | Largest group | Delivered in the period | Share of throughput |
|---|---|---|---|---|---|
| ABC | 5 | 1 | 5 | 26 | 19% |
| **Total** | **5** | **1** | | **26** | **19%** |

## Lead time (from creation to resolution)
- All types: P50 34 d · P70 66 d · P85 82 d · P95 89 d.
- Story (16 finished): P50 30 d · P70 48 d · P85 70 d · P95 87 d.
- Task (10 finished): P50 62 d · P70 80 d · P85 86 d · P95 89 d.

## Work in progress
- WIP: 22 items in progress (In Review 12, In Progress 10); 15 items to do.
- Age of items in progress since they started: P50 116 d · P70 130 d · P85 163 d · P95 191 d.
- Age since creation: P50 132 d · P70 197 d · P85 941 d · P95 941 d.
- 19 item(s) in progress are older (basis: creation) than the P85 lead time of finished items.
- Items in progress for more than 30 / 90 / 180 / 365 / 730 days: 21 / 17 / 8 / 6 / 6.
- Active WIP: 22; waiting WIP: 0 (waiting statuses of flux.yaml: none); share of waiting in the WIP: 0%. The total WIP stays 22.
- "In progress" and "to do" are decided by the Jira status category (column "Status Category"); the lists in flux.yaml only serve for tickets with no category.

### Age by status (basis: creation)

| Status | Nature | Items | Age P50 | Age P85 | Over 90 d | Over 365 d |
|---|---|---|---|---|---|---|
| In Review | active | 12 | 164 d | 941 d | 9 | 5 |
| In Progress | active | 10 | 116 d | 183 d | 8 | 1 |

### Queues before commitment: age of the items to do, by status

An item can wait a long time before it is started: this time counts neither in the WIP nor in the lead time of an item that is not finished yet. "Since the category" starts at the last Jira status category change (entering analysis or definition, for example), when it is known.

| To do status | Items | Age P50 (creation) | Age P85 (creation) | Age P50 (category) | Over 90 d | Over 365 d |
|---|---|---|---|---|---|---|
| Open | 15 | 168 d | 867 d | n/a | 12 | 3 |

- Little's law (current WIP / average throughput): at this pace, an item stays in progress for about 136 days on average; compare with the age of the items in progress and with the median lead time.

## By team

| Team | Finished | Throughput / wk | Lead time P50 | Lead time P85 | WIP | WIP age P50 | WIP > 90 d | Waiting WIP | Waiting share |
|---|---|---|---|---|---|---|---|---|---|
| (no team) | 2 | 0.1 | 57 d | 80 d | 1 | 197 d | 1 | 0 | 0% |
| Team A | 4 | 0.2 | 37 d | 74 d | 2 | 535 d | 2 | 0 | 0% |
| Team B | 0 | 0.0 | n/a | n/a | 1 | 172 d | 1 | 0 | 0% |
| Team C | 0 | 0.0 | n/a | n/a | 2 | 122 d | 2 | 0 | 0% |
| Team D | 4 | 0.2 | 14 d | 39 d | 1 | 941 d | 1 | 0 | 0% |
| Team E | 1 | 0.0 | 22 d | 22 d | 0 | n/a | 0 | 0 | n/a |
| Team F | 1 | 0.0 | 89 d | 89 d | 2 | 130 d | 2 | 0 | 0% |
| Team G | 4 | 0.2 | 44 d | 63 d | 1 | 189 d | 1 | 0 | 0% |
| Team H | 1 | 0.0 | 42 d | 42 d | 2 | 942 d | 2 | 0 | 0% |
| Team I | 2 | 0.1 | 56 d | 74 d | 2 | 58 d | 1 | 0 | 0% |
| Team J | 1 | 0.0 | 73 d | 73 d | 3 | 82 d | 1 | 0 | 0% |
| Team K | 4 | 0.2 | 30 d | 64 d | 5 | 122 d | 3 | 0 | 0% |
| Team L | 2 | 0.1 | 46 d | 70 d | 0 | n/a | 0 | 0 | n/a |

Teams are not compared with each other: workflows, ticket sizes and types of work differ. Each row is first for the team concerned.

Items finished per week and per team, from the oldest to the most recent (zero weeks between two peaks point to batched closures):

- (no team): 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0
- Team A: 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0
- Team B: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
- Team C: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
- Team D: 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1
- Team E: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0
- Team F: 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
- Team G: 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 2
- Team H: 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
- Team I: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0
- Team J: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0
- Team K: 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 2
- Team L: 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1

Tickets with several teams: 5 out of 63 (1 finished, 2 in progress). Current attribution: each ticket counts once, in the row of the first value of its first team column; the other values and the other team columns attribute nothing. Teams are recognised by the columns of the same name and by the separator ";" in a cell (team_separator setting of flux.yaml).


## Monte Carlo forecasts (10,000 simulations on the weekly throughput of the period)
- Finish 22 items: 20 weeks with a 50% chance, 25 with 85%, 29 with 95%.

## How to read this report

- **P50 (median)**: half of the items are below, half are above. It is the typical case.
- **P85**: 85% of the items are below, 15% above. It is used to make commitments: "in 85% of cases, less than X days". P70 and P95 read the same way, with 70% and 95%.
- **Why percentiles rather than an average**: a few very long tickets pull the average up. Percentiles are not dragged along by these extreme cases.
- **Lead time**: from creation to resolution, for finished items only. **Age**: since the last status category change (creation date if there is none), for items still in progress. Lead time only sees what finishes; age shows what stays stuck.
- **WIP**: items in progress. **Active WIP**: being worked on right now. **Waiting WIP**: in a waiting status listed in flux.yaml, such as "Ready for". **Dormant WIP**: not finished and with no status change for more than 365 days (inferred from the status history, option --dormant-from-history). A dormant ticket is neither active nor waiting.
- **Arrivals and departures**: tickets created and items finished, week by week. If arrivals keep exceeding departures, the stock grows. Arrivals also count rejected tickets.
- **Little's law**: the number of items in progress divided by the average throughput gives an average time in the system. Read it with care when arrivals keep exceeding departures.
- **Monte Carlo forecast**: 10,000 draws from the throughput of past weeks. It says in how many weeks of throughput the current stock would drain if nothing new came in. It is not a date.
- **Batched closure**: at least N delivered tickets of the same project whose resolution falls in the same minute (N: batch_closure_threshold in flux.yaml). It most likely points to a bulk status change (clean-up, migration) rather than deliveries as they happen. A count only: these tickets stay in the throughput.
- **Shared tickets**: a ticket carried by several teams counts once, for its first team. For each team, the first column counts the tickets attributed to it while shared, the second those it carries without their being attributed to it. A cell under 5 tickets is written "masked".

Examples taken from this report:
- The P85 age of items in progress is 941 days: 15% of the items in progress have been there for more than 941 days.
- The P85 lead time is 82 days: 85% of the finished items were finished in less than 82 days.

## Limits
- Lead time counts from the creation of the ticket, waiting in the backlog included: it is not a cycle time.
- Forecasts assume that the throughput of the coming weeks will look like that of the period, and that items are of comparable size.

Report: <WS>/Flux-Lab/rapports/flux-2026-10-04.md
--- stderr ---
written: rapports/flux-2026-10-04.json
written: rapports/flux-2026-10-04.md

===== compute-simple-history-only =====
$ compute <WS>/a.csv --name h --today 2026-10-04 --no-comparison --history
exit code: 0
--- stdout ---
--history: 1 ticket(s) have an unreadable transition date in the cache: their transitions are ignored (run history_jira.py collect --refresh again).
# Flow metrics: h, as of 2026-10-04

Period: 2026-04-20 to 2026-09-27 (23 complete weeks). Types: all. Aggregates computed locally from a Jira export; no ticket is quoted.

Left out of throughput, lead time, WIP and forecasts (portfolio_types and excluded_projects in flux.yaml): 27 tickets; by type: Epic 27.

## Throughput
- 26 items finished, i.e. 1.1 per week on average (median 1); 6 week(s) with no item finished.
- Per week, from the oldest to the most recent: 1, 0, 0, 1, 1, 0, 0, 1, 2, 1, 1, 1, 0, 1, 2, 1, 1, 1, 1, 3, 0, 1, 6.
- Resolutions counted as delivered: Done 26.
- Closed without delivery, left out of throughput, lead time and forecasts: none.

## Arrivals and departures

Arrivals: tickets created during the period, same types and same exclusions as the throughput. Departures: finished items counted as delivered (the throughput). Difference: arrivals minus departures; when positive, the stock of open tickets grows, when negative, it shrinks.

| Week (start) | Arrivals | Departures | Difference |
|---|---|---|---|
| 2026-04-20 | 1 | 1 | 0 |
| 2026-04-27 | 2 | 0 | +2 |
| 2026-05-04 | 1 | 0 | +1 |
| 2026-05-11 | 1 | 1 | 0 |
| 2026-05-18 | 5 | 1 | +4 |
| 2026-05-25 | 2 | 0 | +2 |
| 2026-06-01 | 3 | 0 | +3 |
| 2026-06-08 | 1 | 1 | 0 |
| 2026-06-15 | 3 | 2 | +1 |
| 2026-06-22 | 2 | 1 | +1 |
| 2026-06-29 | 3 | 1 | +2 |
| 2026-07-06 | 3 | 1 | +2 |
| 2026-07-13 | 2 | 0 | +2 |
| 2026-07-20 | 0 | 1 | -1 |
| 2026-07-27 | 1 | 2 | -1 |
| 2026-08-03 | 0 | 1 | -1 |
| 2026-08-10 | 2 | 1 | +1 |
| 2026-08-17 | 2 | 1 | +1 |
| 2026-08-24 | 0 | 1 | -1 |
| 2026-08-31 | 1 | 3 | -2 |
| 2026-09-07 | 2 | 0 | +2 |
| 2026-09-14 | 5 | 1 | +4 |
| 2026-09-21 | 0 | 6 | -6 |
| **Total** | **42** | **26** | **+16** |

- Average per week: 1.8 arrivals, 1.1 departures.
- Note: tickets created then rejected, or left without movement, count in the arrivals but never in the departures (excluded closure resolutions are not throughput): the difference therefore does not measure a growth of the real work. A dormant ticket (more than 365 days) only enters the arrivals if its creation falls in the period, which implies a period of more than 52 weeks. Arrivals also depend on the export query.

- **First week truncated.** The export query filters `resolved >= -20w`: the window starts on 2026-05-17 (from the computation date), so the whole first week and more is missing from the export. The week of 2026-04-20 is underestimated (departures, and arrivals of tickets created then resolved before the window): leave it out of comparisons (series, averages, trends).

### By team

| Team | Arrivals | Departures | Difference |
|---|---|---|---|
| (no team) | 2 | 2 | 0 |
| Team A | 7 | 4 | +3 |
| Team C | 4 | 0 | +4 |
| Team D | 4 | 4 | 0 |
| Team E | 1 | 1 | 0 |
| Team F | 3 | 1 | +2 |
| Team G | 3 | 4 | -1 |
| Team H | 1 | 1 | 0 |
| Team I | 4 | 2 | +2 |
| Team J | 4 | 1 | +3 |
| Team K | 7 | 4 | +3 |
| Team L | 2 | 2 | 0 |

Teams are not compared with each other: workflows, ticket sizes and types of work differ. Each row is first for the team concerned.

### Shared tickets by team

First-team attribution: each ticket counts once, for its first team.

| Team | Attributed here, shared | Carried here, attributed elsewhere |
|---|---|---|
| Team A | 5 | masked |
| Team B | masked | 5 |

## Batched closures

Delivered tickets (resolution: done) whose resolution falls in the same minute as that of at least 4 others of the same project (threshold of 5 tickets, batch_closure_threshold setting). A count only: these tickets stay in the throughput, the lead time and the forecasts.

| Project | Tickets in batched closures | Groups | Largest group | Delivered in the period | Share of throughput |
|---|---|---|---|---|---|
| ABC | 5 | 1 | 5 | 26 | 19% |
| **Total** | **5** | **1** | | **26** | **19%** |

## Lead time (from creation to resolution)
- All types: P50 34 d · P70 66 d · P85 82 d · P95 89 d.
- Story (16 finished): P50 30 d · P70 48 d · P85 70 d · P95 87 d.
- Task (10 finished): P50 62 d · P70 80 d · P85 86 d · P95 89 d.

## Work in progress
- WIP: 22 items in progress (In Review 12, In Progress 10); 15 items to do.
- Age of items in progress since they started: P50 116 d · P70 130 d · P85 163 d · P95 191 d.
- Age since creation: P50 132 d · P70 197 d · P85 941 d · P95 941 d.
- 19 item(s) in progress are older (basis: creation) than the P85 lead time of finished items.
- Items in progress for more than 30 / 90 / 180 / 365 / 730 days: 21 / 17 / 8 / 6 / 6.
- Active WIP: 22; waiting WIP: 0 (waiting statuses of flux.yaml: none); share of waiting in the WIP: 0%. The total WIP stays 22.
- "In progress" and "to do" are decided by the Jira status category (column "Status Category"); the lists in flux.yaml only serve for tickets with no category.

### Age by status (basis: creation)

| Status | Nature | Items | Age P50 | Age P85 | Over 90 d | Over 365 d |
|---|---|---|---|---|---|---|
| In Review | active | 12 | 164 d | 941 d | 9 | 5 |
| In Progress | active | 10 | 116 d | 183 d | 8 | 1 |

### Queues before commitment: age of the items to do, by status

An item can wait a long time before it is started: this time counts neither in the WIP nor in the lead time of an item that is not finished yet. "Since the category" starts at the last Jira status category change (entering analysis or definition, for example), when it is known.

| To do status | Items | Age P50 (creation) | Age P85 (creation) | Age P50 (category) | Over 90 d | Over 365 d |
|---|---|---|---|---|---|---|
| Open | 15 | 168 d | 867 d | n/a | 12 | 3 |

- Little's law (current WIP / average throughput): at this pace, an item stays in progress for about 136 days on average; compare with the age of the items in progress and with the median lead time.

## By team

| Team | Finished | Throughput / wk | Lead time P50 | Lead time P85 | WIP | WIP age P50 | WIP > 90 d | Waiting WIP | Waiting share |
|---|---|---|---|---|---|---|---|---|---|
| (no team) | 2 | 0.1 | 57 d | 80 d | 1 | 197 d | 1 | 0 | 0% |
| Team A | 4 | 0.2 | 37 d | 74 d | 2 | 535 d | 2 | 0 | 0% |
| Team B | 0 | 0.0 | n/a | n/a | 1 | 172 d | 1 | 0 | 0% |
| Team C | 0 | 0.0 | n/a | n/a | 2 | 122 d | 2 | 0 | 0% |
| Team D | 4 | 0.2 | 14 d | 39 d | 1 | 941 d | 1 | 0 | 0% |
| Team E | 1 | 0.0 | 22 d | 22 d | 0 | n/a | 0 | 0 | n/a |
| Team F | 1 | 0.0 | 89 d | 89 d | 2 | 130 d | 2 | 0 | 0% |
| Team G | 4 | 0.2 | 44 d | 63 d | 1 | 189 d | 1 | 0 | 0% |
| Team H | 1 | 0.0 | 42 d | 42 d | 2 | 942 d | 2 | 0 | 0% |
| Team I | 2 | 0.1 | 56 d | 74 d | 2 | 58 d | 1 | 0 | 0% |
| Team J | 1 | 0.0 | 73 d | 73 d | 3 | 82 d | 1 | 0 | 0% |
| Team K | 4 | 0.2 | 30 d | 64 d | 5 | 122 d | 3 | 0 | 0% |
| Team L | 2 | 0.1 | 46 d | 70 d | 0 | n/a | 0 | 0 | n/a |

Teams are not compared with each other: workflows, ticket sizes and types of work differ. Each row is first for the team concerned.

Items finished per week and per team, from the oldest to the most recent (zero weeks between two peaks point to batched closures):

- (no team): 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0
- Team A: 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0
- Team B: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
- Team C: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
- Team D: 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1
- Team E: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0
- Team F: 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
- Team G: 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 2
- Team H: 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
- Team I: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0
- Team J: 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0
- Team K: 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 2
- Team L: 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1

Tickets with several teams: 5 out of 63 (1 finished, 2 in progress). Current attribution: each ticket counts once, in the row of the first value of its first team column; the other values and the other team columns attribute nothing. Teams are recognised by the columns of the same name and by the separator ";" in a cell (team_separator setting of flux.yaml).


## Time in segment

Time spent in each segment of statuses (segments setting of flux.yaml), from the status history, in calendar days (differences of dates), initial status included. The time of a ticket adds up over all its visits to the segment. Computed to be compared with the Jira Control Chart, on the same statuses and the same dates.

- Coverage: 47 tickets out of 48 (delivered during the period or in progress) have a history (98%).
- WARNING: 1 ticket(s) have an unreadable transition date in the cache; their transitions are ignored and their time in segment is wrong. Run the collection again with --refresh.

### Tickets that left a segment during the period (cumulative time in the segment)

| Segment | Tickets | P50 | P85 | Mean |
|---|---|---|---|---|
| Definition | 38 | 4 d | 4 d | 3.4 d |
| Ready | 38 | 3 d | 4 d | 2.7 d |
| Implementation | 22 | 38 d | 75 d | 40.8 d |
| Review and verification | 0 | n/a | n/a | n/a |
| Acceptance | 0 | n/a | n/a | n/a |

### Tickets still in a segment (age of the current visit)

| Segment | Tickets | Age P50 | Age P85 |
|---|---|---|---|
| Definition | 0 | n/a | n/a |
| Ready | 0 | n/a | n/a |
| Implementation | 32 | 154 d | 932 d |
| Review and verification | 0 | n/a | n/a |
| Acceptance | 0 | n/a | n/a |

### Delivery lead time

From the commitment point (entry into the segment "Ready") to resolution, for the 25 tickets delivered during the period that went through it (0 delivered ticket(s) with a history but no commitment point are not counted).

- Since commitment: P50 29 d · P70 63 d · P85 77 d · P95 83 d.
- Since creation, for the same tickets: P50 35 d · P70 69 d · P85 83 d · P95 89 d. The lead time of all delivered items is higher up in the report.

### Flow efficiency

- Share of time in an active status, between the commitment point and resolution (the waiting statuses are those of waiting_states): 90% at P50 per ticket (24 tickets), 93% in aggregate value (total active time over total time).

### By team

| Team | Coverage | Delivered with commitment | Delivery lead time P50 | P85 | Efficiency P50 | Aggregate efficiency |
|---|---|---|---|---|---|---|
| (no team) | 100% | 2 | 50 d | 74 d | 92% | 95% |
| Team A | 100% | 4 | 30 d | 68 d | 84% | 92% |
| Team B | 100% | 0 | n/a | n/a | n/a | n/a |
| Team C | 100% | 0 | n/a | n/a | n/a | n/a |
| Team D | 100% | 4 | 8 d | 33 d | 80% | 89% |
| Team E | 100% | 1 | 17 d | 17 d | 82% | 82% |
| Team F | 100% | 1 | 83 d | 83 d | 95% | 95% |
| Team G | 100% | 4 | 38 d | 57 d | 87% | 91% |
| Team H | 100% | 1 | 36 d | 36 d | 89% | 89% |
| Team I | 100% | 2 | 50 d | 68 d | 96% | 96% |
| Team J | 100% | 1 | 66 d | 66 d | 95% | 95% |
| Team K | 89% | 3 | 28 d | 66 d | 89% | 92% |
| Team L | 100% | 2 | 40 d | 64 d | 78% | 94% |

Tickets that left each segment during the period, by team (count, P50 of the cumulative time):

| Team | Definition | Ready | Implementation | Review and verification | Acceptance |
|---|---|---|---|---|---|
| (no team) | 2 · 4 d | 2 · 2 d | 2 · 48 d | 0 · n/a | 0 · n/a |
| Team A | 6 · 3 d | 6 · 2 d | 4 · 29 d | 0 · n/a | 0 · n/a |
| Team B | 0 · n/a | 1 · 5 d | 0 · n/a | 0 · n/a | 0 · n/a |
| Team C | 3 · 4 d | 3 · 3 d | 0 · n/a | 0 · n/a | 0 · n/a |
| Team D | 4 · 4 d | 4 · 2 d | 2 · 28 d | 0 · n/a | 0 · n/a |
| Team E | 1 · 2 d | 1 · 3 d | 1 · 14 d | 0 · n/a | 0 · n/a |
| Team F | 2 · 4 d | 2 · 2 d | 1 · 79 d | 0 · n/a | 0 · n/a |
| Team G | 3 · 3 d | 3 · 3 d | 3 · 44 d | 0 · n/a | 0 · n/a |
| Team H | 1 · 4 d | 1 · 4 d | 1 · 32 d | 0 · n/a | 0 · n/a |
| Team I | 4 · 4 d | 3 · 3 d | 2 · 48 d | 0 · n/a | 0 · n/a |
| Team J | 4 · 4 d | 4 · 2 d | 1 · 63 d | 0 · n/a | 0 · n/a |
| Team K | 6 · 2 d | 6 · 3 d | 3 · 25 d | 0 · n/a | 0 · n/a |
| Team L | 2 · 4 d | 2 · 3 d | 2 · 38 d | 0 · n/a | 0 · n/a |

Tickets still in each segment, by team (count, age P50):

| Team | Definition | Ready | Implementation | Review and verification | Acceptance |
|---|---|---|---|---|---|
| (no team) | 0 · n/a | 0 · n/a | 1 · 189 d | 0 · n/a | 0 · n/a |
| Team A | 0 · n/a | 0 · n/a | 3 · 148 d | 0 · n/a | 0 · n/a |
| Team B | 0 · n/a | 0 · n/a | 1 · 164 d | 0 · n/a | 0 · n/a |
| Team C | 0 · n/a | 0 · n/a | 4 · 142 d | 0 · n/a | 0 · n/a |
| Team D | 0 · n/a | 0 · n/a | 2 · 932 d | 0 · n/a | 0 · n/a |
| Team E | 0 · n/a | 0 · n/a | 0 · n/a | 0 · n/a | 0 · n/a |
| Team F | 0 · n/a | 0 · n/a | 3 · 129 d | 0 · n/a | 0 · n/a |
| Team G | 0 · n/a | 0 · n/a | 1 · 181 d | 0 · n/a | 0 · n/a |
| Team H | 0 · n/a | 0 · n/a | 4 · 560 d | 0 · n/a | 0 · n/a |
| Team I | 0 · n/a | 0 · n/a | 2 · 51 d | 0 · n/a | 0 · n/a |
| Team J | 0 · n/a | 0 · n/a | 3 · 76 d | 0 · n/a | 0 · n/a |
| Team K | 0 · n/a | 0 · n/a | 7 · 116 d | 0 · n/a | 0 · n/a |
| Team L | 0 · n/a | 0 · n/a | 1 · 17 d | 0 · n/a | 0 · n/a |

Below about ten tickets, a P85 is fragile: read it as a question, not as a finding.

Teams are not compared with each other: workflows, ticket sizes and types of work differ. Each row is first for the team concerned.

## Monte Carlo forecasts (10,000 simulations on the weekly throughput of the period)
- Finish 22 items: 20 weeks with a 50% chance, 25 with 85%, 29 with 95%.

## How to read this report

- **P50 (median)**: half of the items are below, half are above. It is the typical case.
- **P85**: 85% of the items are below, 15% above. It is used to make commitments: "in 85% of cases, less than X days". P70 and P95 read the same way, with 70% and 95%.
- **Why percentiles rather than an average**: a few very long tickets pull the average up. Percentiles are not dragged along by these extreme cases.
- **Lead time**: from creation to resolution, for finished items only. **Age**: since the last status category change (creation date if there is none), for items still in progress. Lead time only sees what finishes; age shows what stays stuck.
- **WIP**: items in progress. **Active WIP**: being worked on right now. **Waiting WIP**: in a waiting status listed in flux.yaml, such as "Ready for". **Dormant WIP**: not finished and with no status change for more than 365 days (inferred from the status history, option --dormant-from-history). A dormant ticket is neither active nor waiting.
- **Arrivals and departures**: tickets created and items finished, week by week. If arrivals keep exceeding departures, the stock grows. Arrivals also count rejected tickets.
- **Little's law**: the number of items in progress divided by the average throughput gives an average time in the system. Read it with care when arrivals keep exceeding departures.
- **Monte Carlo forecast**: 10,000 draws from the throughput of past weeks. It says in how many weeks of throughput the current stock would drain if nothing new came in. It is not a date.
- **Segment**: a group of consecutive workflow statuses (definition, ready, implementation, review and verification, acceptance), set in flux.yaml. **Time in segment**: how many days a ticket spent in the statuses of the segment, in calendar days, initial status included; the time adds up if the ticket comes back to the segment. "Left the segment" means: moved to another segment during the period.
- **Commitment point**: the moment the team commits, here the entry into the segment set by commitment_point. **Delivery lead time**: from the commitment point to resolution; it is shorter than the lead time from creation, which also counts the wait in the backlog.
- **Flow efficiency**: the share of time spent in an active status, between the commitment point and resolution. A waiting status (waiting_states) counts as time lost waiting, any other status as active time. A low efficiency says tickets wait a lot, not that people work badly.
- **Coverage**: the share of the tickets in the report whose history is known. Below 90%, the figures for time in segment only describe part of the tickets.
- **Batched closure**: at least N delivered tickets of the same project whose resolution falls in the same minute (N: batch_closure_threshold in flux.yaml). It most likely points to a bulk status change (clean-up, migration) rather than deliveries as they happen. A count only: these tickets stay in the throughput.
- **Shared tickets**: a ticket carried by several teams counts once, for its first team. For each team, the first column counts the tickets attributed to it while shared, the second those it carries without their being attributed to it. A cell under 5 tickets is written "masked".

Examples taken from this report:
- The P85 age of items in progress is 941 days: 15% of the items in progress have been there for more than 941 days.
- The P85 lead time is 82 days: 85% of the finished items were finished in less than 82 days.
- The aggregate flow efficiency is 93%: out of 100 days spent between the commitment point and resolution, 93 were in an active status and 7 waiting.

## Limits
- Lead time counts from the creation of the ticket, waiting in the backlog included: it is not a cycle time.
- Forecasts assume that the throughput of the coming weeks will look like that of the period, and that items are of comparable size.

Report: <WS>/Flux-Lab/rapports/flux-h-2026-10-04.md
--- stderr ---
written: rapports/flux-h-2026-10-04.json
written: rapports/flux-h-2026-10-04.md

===== compare =====
$ compare --name s
exit code: 0
--- stdout ---
# Flow evolution: s, from 2026-09-20 to 2026-10-04

Compares the reports of 2026-09-20 and 2026-10-04 (14 days apart), computed locally from two Jira exports. Aggregates only: no ticket is quoted or followed.

## What moved

- Throughput up: 8.0 items per week over the 2 new week(s), against 1.8 over the 4 weeks before (+357%).
- Little's law: an item would stay in progress for about 131 days, against 181 (-28%).
- More items in progress for more than 90 days: 27 → 29.
- More items in progress older than the P85 lead time: 29 → 37.
- Team D: throughput up, 0.2 → 1.5 per week (+500%).
- Team E: throughput up, 0.2 → 1.0 per week (+300%).
- Team K: throughput up, 0.2 → 1.5 per week (+500%).

Thresholds: throughput ±25% (±30% per team), lead time P85 ±20%, WIP and Little's law ±20%, any increase in aging (at least 3 more items of over 90 days for a team); batched closures when 2 weeks carry at least 60% of the items finished in the last 8 weeks. Each signal is a question to ask the teams, not a conclusion.

## Comparability

- Windows of different sizes: 23 then 25 weeks.

## Throughput

- New weeks (2): 8.0 per week, against 1.8 over the last 4 weeks of the previous report.
- Average over the whole window: 1.4 → 1.9 (+38%); zero weeks: 3 → 3.
- Series of the new report, from the oldest to the most recent: 2, 0, 1, 0, 1, 1, 1, 2, 0, 1, 3, 2, 1, 2, 1, 1, 2, 1, 3, 2, 1, 3, 1, 3, 13.

## Lead time (from creation to resolution)

| Scope | P50 | P85 |
|---|---|---|
| All types | 46 d → 44 d (-3%) | 80 d → 73 d (-9%) |
| Bug | 54 d → 50 d (-7%) | 71 d → 69 d (-3%) |
| Story | 33 d → 32 d (-3%) | 69 d → 62 d (-11%) |
| Task | 80 d → 62 d (-22%) | 88 d → 86 d (-3%) |

## Work in progress

- In progress: 46 → 46 (+0%); to do: 29 → 29 (+0%).
- Little's law: 181 d → 131 d (-28%).

| Status | Before | After |
|---|---|---|
| Doing | 14 | 14 |
| In Review | 12 | 12 |
| In Progress | 10 | 10 |
| Validation | 10 | 10 |

## Aging of the items in progress

| In progress for more than | Before | After |
|---|---|---|
| 30 days | 42 | 44 |
| 90 days | 27 | 29 |
| 180 days | 11 | 14 |
| 365 days | 10 | 10 |
| 730 days | 10 | 10 |
| more than the P85 lead time | 29 | 37 |

## Queues before commitment

| To do status | Items | Age P50 since creation | Over 90 d |
|---|---|---|---|
| Open | 15 → 15 (+0%) | 154 d → 168 d (+9%) | 10 → 12 |
| Waiting | 14 → 14 (+0%) | 72 d → 86 d (+19%) | 6 → 7 |

## By team

| Team | Recent throughput / wk | Lead time P85 | WIP | WIP > 90 d | Closures in 2 weeks |
|---|---|---|---|---|---|
| (no team) | 0.2 → 0.0 (-100%) | 80 d → 80 d (+0%) | 1 → 1 (+0%) | 1 → 1 | n/a → n/a |
| Team A | 0.2 → 0.0 (-100%) | 70 d → 70 d (+0%) | 3 → 3 (+0%) | 2 → 2 | n/a → n/a |
| Team B | 0.0 → 0.0 | n/a → n/a | 1 → 1 (+0%) | 1 → 1 | n/a → n/a |
| Team C | 0.0 → 0.5 | 50 d → 53 d (+5%) | 3 → 3 (+0%) | 2 → 2 | n/a → n/a |
| Team D | 0.2 → 1.5 (+500%) | 44 d → 51 d (+16%) | 9 → 9 (+0%) | 7 → 7 | n/a → n/a |
| Team E | 0.2 → 1.0 (+300%) | 61 d → 62 d (+1%) | 1 → 1 (+0%) | 0 → 1 | n/a → n/a |
| Team F | 0.0 → 0.0 | 84 d → 84 d (+0%) | 4 → 4 (+0%) | 4 → 4 | n/a → n/a |
| Team G | 0.0 → 1.5 | 50 d → 60 d (+20%) | 3 → 3 (+0%) | 2 → 2 | n/a → n/a |
| Team H | 0.0 → 1.0 | 62 d → 56 d (-10%) | 3 → 3 (+0%) | 2 → 2 | n/a → n/a |
| Team I | 0.0 → 0.5 | 74 d → 66 d (-10%) | 4 → 4 (+0%) | 1 → 2 | n/a → n/a |
| Team J | 0.5 → 0.0 (-100%) | 62 d → 62 d (+0%) | 4 → 4 (+0%) | 1 → 1 | n/a → n/a |
| Team K | 0.2 → 1.5 (+500%) | 78 d → 68 d (-13%) | 9 → 9 (+0%) | 4 → 4 | n/a → n/a |
| Team L | 0.0 → 0.5 | 80 d → 70 d (-13%) | 1 → 1 (+0%) | 0 → 0 | n/a → n/a |

"Closures in 2 weeks": share of the items finished over the last 8 weeks of each report that fall on its 2 best weeks (n/a below 5 items finished).

## Forecasts

- Before: 36 items in 30 weeks (85%). After: 40 items in 28 weeks (85%). Different targets: the durations cannot be compared directly.
- By 2026-11-15, at least (85%): 9 → 7 (-22%) items. The remaining time got shorter between the two reports: a decrease is expected.

## Limits

- The two windows overlap: over the common weeks, it is the same data. Only the new weeks say what changed in the throughput.
- Counts are net: an item that left the WIP and another that entered cancel each other out. The script keeps no ticket identifier, so it cannot say which items crossed a threshold.
- By team, the series are short: a gap of one or two units is enough to cross a threshold.

Evolution: <WS>/Flux-Lab/rapports/evolution-s-2026-10-04.md
--- stderr ---

===== compare-dates =====
$ compare --name s --before 2026-09-20 --after 2026-10-04
exit code: 0
--- stdout ---
# Flow evolution: s, from 2026-09-20 to 2026-10-04

Compares the reports of 2026-09-20 and 2026-10-04 (14 days apart), computed locally from two Jira exports. Aggregates only: no ticket is quoted or followed.

## What moved

- Throughput up: 8.0 items per week over the 2 new week(s), against 1.8 over the 4 weeks before (+357%).
- Little's law: an item would stay in progress for about 131 days, against 181 (-28%).
- More items in progress for more than 90 days: 27 → 29.
- More items in progress older than the P85 lead time: 29 → 37.
- Team D: throughput up, 0.2 → 1.5 per week (+500%).
- Team E: throughput up, 0.2 → 1.0 per week (+300%).
- Team K: throughput up, 0.2 → 1.5 per week (+500%).

Thresholds: throughput ±25% (±30% per team), lead time P85 ±20%, WIP and Little's law ±20%, any increase in aging (at least 3 more items of over 90 days for a team); batched closures when 2 weeks carry at least 60% of the items finished in the last 8 weeks. Each signal is a question to ask the teams, not a conclusion.

## Comparability

- Windows of different sizes: 23 then 25 weeks.

## Throughput

- New weeks (2): 8.0 per week, against 1.8 over the last 4 weeks of the previous report.
- Average over the whole window: 1.4 → 1.9 (+38%); zero weeks: 3 → 3.
- Series of the new report, from the oldest to the most recent: 2, 0, 1, 0, 1, 1, 1, 2, 0, 1, 3, 2, 1, 2, 1, 1, 2, 1, 3, 2, 1, 3, 1, 3, 13.

## Lead time (from creation to resolution)

| Scope | P50 | P85 |
|---|---|---|
| All types | 46 d → 44 d (-3%) | 80 d → 73 d (-9%) |
| Bug | 54 d → 50 d (-7%) | 71 d → 69 d (-3%) |
| Story | 33 d → 32 d (-3%) | 69 d → 62 d (-11%) |
| Task | 80 d → 62 d (-22%) | 88 d → 86 d (-3%) |

## Work in progress

- In progress: 46 → 46 (+0%); to do: 29 → 29 (+0%).
- Little's law: 181 d → 131 d (-28%).

| Status | Before | After |
|---|---|---|
| Doing | 14 | 14 |
| In Review | 12 | 12 |
| In Progress | 10 | 10 |
| Validation | 10 | 10 |

## Aging of the items in progress

| In progress for more than | Before | After |
|---|---|---|
| 30 days | 42 | 44 |
| 90 days | 27 | 29 |
| 180 days | 11 | 14 |
| 365 days | 10 | 10 |
| 730 days | 10 | 10 |
| more than the P85 lead time | 29 | 37 |

## Queues before commitment

| To do status | Items | Age P50 since creation | Over 90 d |
|---|---|---|---|
| Open | 15 → 15 (+0%) | 154 d → 168 d (+9%) | 10 → 12 |
| Waiting | 14 → 14 (+0%) | 72 d → 86 d (+19%) | 6 → 7 |

## By team

| Team | Recent throughput / wk | Lead time P85 | WIP | WIP > 90 d | Closures in 2 weeks |
|---|---|---|---|---|---|
| (no team) | 0.2 → 0.0 (-100%) | 80 d → 80 d (+0%) | 1 → 1 (+0%) | 1 → 1 | n/a → n/a |
| Team A | 0.2 → 0.0 (-100%) | 70 d → 70 d (+0%) | 3 → 3 (+0%) | 2 → 2 | n/a → n/a |
| Team B | 0.0 → 0.0 | n/a → n/a | 1 → 1 (+0%) | 1 → 1 | n/a → n/a |
| Team C | 0.0 → 0.5 | 50 d → 53 d (+5%) | 3 → 3 (+0%) | 2 → 2 | n/a → n/a |
| Team D | 0.2 → 1.5 (+500%) | 44 d → 51 d (+16%) | 9 → 9 (+0%) | 7 → 7 | n/a → n/a |
| Team E | 0.2 → 1.0 (+300%) | 61 d → 62 d (+1%) | 1 → 1 (+0%) | 0 → 1 | n/a → n/a |
| Team F | 0.0 → 0.0 | 84 d → 84 d (+0%) | 4 → 4 (+0%) | 4 → 4 | n/a → n/a |
| Team G | 0.0 → 1.5 | 50 d → 60 d (+20%) | 3 → 3 (+0%) | 2 → 2 | n/a → n/a |
| Team H | 0.0 → 1.0 | 62 d → 56 d (-10%) | 3 → 3 (+0%) | 2 → 2 | n/a → n/a |
| Team I | 0.0 → 0.5 | 74 d → 66 d (-10%) | 4 → 4 (+0%) | 1 → 2 | n/a → n/a |
| Team J | 0.5 → 0.0 (-100%) | 62 d → 62 d (+0%) | 4 → 4 (+0%) | 1 → 1 | n/a → n/a |
| Team K | 0.2 → 1.5 (+500%) | 78 d → 68 d (-13%) | 9 → 9 (+0%) | 4 → 4 | n/a → n/a |
| Team L | 0.0 → 0.5 | 80 d → 70 d (-13%) | 1 → 1 (+0%) | 0 → 0 | n/a → n/a |

"Closures in 2 weeks": share of the items finished over the last 8 weeks of each report that fall on its 2 best weeks (n/a below 5 items finished).

## Forecasts

- Before: 36 items in 30 weeks (85%). After: 40 items in 28 weeks (85%). Different targets: the durations cannot be compared directly.
- By 2026-11-15, at least (85%): 9 → 7 (-22%) items. The remaining time got shorter between the two reports: a decrease is expected.

## Limits

- The two windows overlap: over the common weeks, it is the same data. Only the new weeks say what changed in the throughput.
- Counts are net: an item that left the WIP and another that entered cancel each other out. The script keeps no ticket identifier, so it cannot say which items crossed a threshold.
- By team, the series are short: a gap of one or two units is enough to cross a threshold.

Evolution: <WS>/Flux-Lab/rapports/evolution-s-2026-10-04.md
--- stderr ---

===== compare-evo =====
$ compare --name evo
exit code: 0
--- stdout ---
# Flow evolution: evo, from 2026-09-20 to 2026-10-04

Compares the reports of 2026-09-20 and 2026-10-04 (14 days apart), computed locally from two Jira exports. Aggregates only: no ticket is quoted or followed.

## What moved

- Lead time P85 down: 161 → 73 days (-55%).
- WIP down: 138 → 46 items in progress (-67%).
- Little's law: an item would stay in progress for about 131 days, against 394 (-67%).
- More items in progress for more than 90 days: 22 → 29.
- More items in progress for more than 365 days: 5 → 10.
- More items in progress older than the P85 lead time: 0 → 4.
- Queue "Open": more items to do for more than 90 days, 0 → 12.
- Queue "Open" down: 45 → 15 items (-67%).
- Queue "Waiting": more items to do for more than 90 days, 0 → 7.
- Queue "Waiting" down: 42 → 14 items (-67%).
- (no team): throughput down, 1.0 → 0.0 per week (-100%).
- (no team): batched closures over the last 8 weeks (100% of the finished items in 2 weeks).
- Team B: more items in progress for more than 90 days, 0 → 7.
- Team C: closures are no longer batched (100% → 25% in 2 weeks).
- Team F: more items in progress for more than 90 days, 0 → 4.
- Team K: more items in progress for more than 90 days, 0 → 4.

Thresholds: throughput ±25% (±30% per team), lead time P85 ±20%, WIP and Little's law ±20%, any increase in aging (at least 3 more items of over 90 days for a team); batched closures when 2 weeks carry at least 60% of the items finished in the last 8 weeks. Each signal is a question to ask the teams, not a conclusion.

## Comparability

- Different types kept: "Story" then "all".
- Different scopes (--scope): "ABC" then "all".
- Windows of different sizes: 20 then 25 weeks.
- The start column (Status Category Changed) is present in only one of the two exports: ages are not counted the same way.
- Statuses in progress that appeared: New State (new workflow status, or flux.yaml changed?).
- Statuses in progress that disappeared: Old State.
- Team "Team D" not compared: key(s) missing from one of the two reports, probably an old report format.
- Team "Team Extra" is present in only one of the two reports.
- Team "Team L" is present in only one of the two reports.

## Throughput

- New weeks (2): 8.0 per week, against 0.0 over the last 4 weeks of the previous report.
- Average over the whole window: 1.0 → 1.9 (+92%); zero weeks: 9 → 3.
- Series of the new report, from the oldest to the most recent: 2, 0, 1, 0, 1, 1, 1, 2, 0, 1, 3, 2, 1, 2, 1, 1, 2, 1, 3, 2, 1, 3, 1, 3, 13.

## Lead time (from creation to resolution)

| Scope | P50 | P85 |
|---|---|---|
| All types | 92 d → 44 d (-52%) | 161 d → 73 d (-55%) |
| Bug | 54 d → 50 d (-7%) | 71 d → 69 d (-3%) |
| Story | 33 d → 32 d (-3%) | 69 d → 62 d (-11%) |
| Task | 80 d → 62 d (-22%) | 88 d → 86 d (-3%) |

## Work in progress

- In progress: 138 → 46 (-67%); to do: 29 → 29 (+0%).
- Little's law: 394 d → 131 d (-67%).

| Status | Before | After |
|---|---|---|
| Doing | 14 | 14 |
| In Review | 12 | 12 |
| In Progress | 10 | 10 |
| Validation | 10 | 10 |
| Old State | 3 | 0 |
| New State | 0 | 2 |

## Aging of the items in progress

| In progress for more than | Before | After |
|---|---|---|
| 30 days | 37 | 44 |
| 90 days | 22 | 29 |
| 180 days | 6 | 14 |
| 365 days | 5 | 10 |
| 730 days | 5 | 10 |
| more than the P85 lead time | 0 | 4 |

## Queues before commitment

| To do status | Items | Age P50 since creation | Over 90 d |
|---|---|---|---|
| Open | 45 → 15 (-67%) | 168 d → 168 d (+0%) | 0 → 12 |
| Waiting | 42 → 14 (-67%) | 86 d → 86 d (+0%) | 0 → 7 |

## By team

| Team | Recent throughput / wk | Lead time P85 | WIP | WIP > 90 d | Closures in 2 weeks |
|---|---|---|---|---|---|
| (no team) | 1.0 → 0.0 (-100%) | 80 d → 80 d (+0%) | 1 → 1 (+0%) | 0 → 1 | 25% → 100% (batched) |
| Team A | n/a | 70 d → 70 d (+0%) | 3 → 3 (+0%) | 0 → 2 | 25% → 33% |
| Team B | n/a | n/a → n/a | 1 → 1 (+0%) | 0 → 7 | 25% → n/a |
| Team C | n/a | 53 d → 53 d (+0%) | 3 → 3 (+0%) | 0 → 2 | 100% (batched) → 25% |
| Team E | n/a | 62 d → 62 d (+0%) | 1 → 1 (+0%) | 0 → 1 | 25% → n/a |
| Team F | n/a | 84 d → 84 d (+0%) | 4 → 4 (+0%) | 0 → 4 | 25% → n/a |
| Team G | n/a | 60 d → 60 d (+0%) | 3 → 3 (+0%) | 0 → 2 | 25% → n/a |
| Team H | n/a | 56 d → 56 d (+0%) | 3 → 3 (+0%) | 0 → 2 | 25% → n/a |
| Team I | n/a | 66 d → 66 d (+0%) | 4 → 4 (+0%) | 0 → 2 | 25% → n/a |
| Team J | n/a | 62 d → 62 d (+0%) | 4 → 4 (+0%) | 0 → 1 | 25% → n/a |
| Team K | n/a | 68 d → 68 d (+0%) | 9 → 9 (+0%) | 0 → 4 | 25% → n/a |

"Closures in 2 weeks": share of the items finished over the last 8 weeks of each report that fall on its 2 best weeks (n/a below 5 items finished).

## Forecasts

- Before: 5 items in 3 weeks (85%). After: 40 items in 28 weeks (85%). Different targets: the durations cannot be compared directly.
- By 2026-11-15, at least (85%): 9 → 7 (-22%) items. The remaining time got shorter between the two reports: a decrease is expected.

## Limits

- The two windows overlap: over the common weeks, it is the same data. Only the new weeks say what changed in the throughput.
- Counts are net: an item that left the WIP and another that entered cancel each other out. The script keeps no ticket identifier, so it cannot say which items crossed a threshold.
- By team, the series are short: a gap of one or two units is enough to cross a threshold.

Evolution: <WS>/Flux-Lab/rapports/evolution-evo-2026-10-04.md
--- stderr ---
written: rapports/evolution-evo-2026-10-04.json
written: rapports/evolution-evo-2026-10-04.md
written: rapports/flux-evo-2026-09-20.json
written: rapports/flux-evo-2026-10-04.json
written: rapports/flux-evo2-2026-09-20.json
written: rapports/flux-evo2-2026-10-04.json
written: rapports/flux-evo3-2026-09-20.json
written: rapports/flux-evo3-2026-10-04.json
written: rapports/flux-evo4-2026-09-20.json
written: rapports/flux-evo4-2026-10-04.json
written: rapports/flux-evo5-2026-10-04.json
written: rapports/flux-evo6-2026-09-20.json
written: rapports/flux-evo6-2026-10-04.json

===== compare-evo2 =====
$ compare --name evo2
exit code: 0
--- stdout ---
# Flow evolution: evo2, from 2026-09-20 to 2026-10-04

Compares the reports of 2026-09-20 and 2026-10-04 (14 days apart), computed locally from two Jira exports. Aggregates only: no ticket is quoted or followed.

## What moved

- No gap beyond the thresholds. This does not prove that the flow is stable: look at the tables below.

Thresholds: throughput ±25% (±30% per team), lead time P85 ±20%, WIP and Little's law ±20%, any increase in aging (at least 3 more items of over 90 days for a team); batched closures when 2 weeks carry at least 60% of the items finished in the last 8 weeks. Each signal is a question to ask the teams, not a conclusion.

## Comparability

- No new complete week since the previous report: recent throughput cannot be compared.

## Throughput

- Average over the whole window: 1.4 → 1.4 (+0%); zero weeks: 3 → 3.
- Series of the new report, from the oldest to the most recent: 2, 0, 1, 0, 1, 1, 1, 2, 0, 1, 3, 2, 1, 2, 1, 1, 2, 1, 3, 2, 1, 3, 1.

## Lead time (from creation to resolution)

| Scope | P50 | P85 |
|---|---|---|
| All types | 46 d → 46 d (+0%) | 80 d → 80 d (+0%) |
| Bug | 54 d → 54 d (+0%) | 71 d → 71 d (+0%) |
| Story | 33 d → 33 d (+0%) | 69 d → 69 d (+0%) |
| Task | 80 d → 80 d (+0%) | 88 d → 88 d (+0%) |

## Work in progress

- In progress: 46 → 46 (+0%); to do: 29 → 29 (+0%).
- Little's law: 181 d → 181 d (+0%).

| Status | Before | After |
|---|---|---|
| Doing | 14 | 14 |
| In Review | 12 | 12 |
| In Progress | 10 | 10 |
| Validation | 10 | 10 |

## Aging of the items in progress

| In progress for more than | Before | After |
|---|---|---|
| 30 days | 42 | 42 |
| 90 days | 27 | 27 |
| 180 days | 11 | 11 |
| 365 days | 10 | 10 |
| 730 days | 10 | 10 |
| more than the P85 lead time | 29 | 29 |

## Queues before commitment

| To do status | Items | Age P50 since creation | Over 90 d |
|---|---|---|---|
| Open | 15 → 15 (+0%) | 154 d → 154 d (+0%) | 10 → 10 |
| Waiting | 14 → 14 (+0%) | 72 d → 72 d (+0%) | 6 → 6 |

## By team

| Team | Recent throughput / wk | Lead time P85 | WIP | WIP > 90 d | Closures in 2 weeks |
|---|---|---|---|---|---|
| (no team) | n/a | 80 d → 80 d (+0%) | 1 → 1 (+0%) | 1 → 1 | n/a → n/a |
| Team A | n/a | 70 d → 70 d (+0%) | 3 → 3 (+0%) | 2 → 2 | n/a → n/a |
| Team B | n/a | n/a → n/a | 1 → 1 (+0%) | 1 → 1 | n/a → n/a |
| Team C | n/a | 50 d → 50 d (+0%) | 3 → 3 (+0%) | 2 → 2 | n/a → n/a |
| Team D | n/a | 44 d → 44 d (+0%) | 9 → 9 (+0%) | 7 → 7 | n/a → n/a |
| Team E | n/a | 61 d → 61 d (+0%) | 1 → 1 (+0%) | 0 → 0 | n/a → n/a |
| Team F | n/a | 84 d → 84 d (+0%) | 4 → 4 (+0%) | 4 → 4 | n/a → n/a |
| Team G | n/a | 50 d → 50 d (+0%) | 3 → 3 (+0%) | 2 → 2 | n/a → n/a |
| Team H | n/a | 62 d → 62 d (+0%) | 3 → 3 (+0%) | 2 → 2 | n/a → n/a |
| Team I | n/a | 74 d → 74 d (+0%) | 4 → 4 (+0%) | 1 → 1 | n/a → n/a |
| Team J | n/a | 62 d → 62 d (+0%) | 4 → 4 (+0%) | 1 → 1 | n/a → n/a |
| Team K | n/a | 78 d → 78 d (+0%) | 9 → 9 (+0%) | 4 → 4 | n/a → n/a |
| Team L | n/a | 80 d → 80 d (+0%) | 1 → 1 (+0%) | 0 → 0 | n/a → n/a |

"Closures in 2 weeks": share of the items finished over the last 8 weeks of each report that fall on its 2 best weeks (n/a below 5 items finished).

## Forecasts

- Finish 5 items, 85% chance: 3 wk → 4 wk (+33%).
- By 2026-11-15, at least (85%): 14 → 10 (-29%) items. The remaining time got shorter between the two reports: a decrease is expected.

## Limits

- The two windows overlap: over the common weeks, it is the same data. Only the new weeks say what changed in the throughput.
- Counts are net: an item that left the WIP and another that entered cancel each other out. The script keeps no ticket identifier, so it cannot say which items crossed a threshold.
- By team, the series are short: a gap of one or two units is enough to cross a threshold.

Evolution: <WS>/Flux-Lab/rapports/evolution-evo2-2026-10-04.md
--- stderr ---
written: rapports/evolution-evo2-2026-10-04.json
written: rapports/evolution-evo2-2026-10-04.md

===== compare-evo3 =====
$ compare --name evo3
exit code: 0
--- stdout ---
# Flow evolution: evo3, from 2026-09-20 to 2026-10-04

Compares the reports of 2026-09-20 and 2026-10-04 (14 days apart), computed locally from two Jira exports. Aggregates only: no ticket is quoted or followed.

## What moved

- Little's law: an item would stay in progress for about 131 days, against 181 (-28%).

Thresholds: throughput ±25% (±30% per team), lead time P85 ±20%, WIP and Little's law ±20%, any increase in aging (at least 3 more items of over 90 days for a team); batched closures when 2 weeks carry at least 60% of the items finished in the last 8 weeks. Each signal is a question to ask the teams, not a conclusion.

## Comparability

- The previous report does not contain the age of the queues before commitment yet: the comparison of these queues will start with the next report.
- Team "(no team)" not compared: key(s) missing from one of the two reports, probably an old report format.
- Team "Team A" not compared: key(s) missing from one of the two reports, probably an old report format.
- Team "Team B" not compared: key(s) missing from one of the two reports, probably an old report format.
- Team "Team C" not compared: key(s) missing from one of the two reports, probably an old report format.
- Team "Team D" not compared: key(s) missing from one of the two reports, probably an old report format.
- Team "Team E" not compared: key(s) missing from one of the two reports, probably an old report format.
- Team "Team F" not compared: key(s) missing from one of the two reports, probably an old report format.
- Team "Team G" not compared: key(s) missing from one of the two reports, probably an old report format.
- Team "Team H" not compared: key(s) missing from one of the two reports, probably an old report format.
- Team "Team I" not compared: key(s) missing from one of the two reports, probably an old report format.
- Team "Team J" not compared: key(s) missing from one of the two reports, probably an old report format.
- Team "Team K" not compared: key(s) missing from one of the two reports, probably an old report format.
- Team "Team L" not compared: key(s) missing from one of the two reports, probably an old report format.
- Types kept not compared: missing key(s) (previous report of 2026-09-20: types), probably an old report format.
- Windows not compared: missing key(s) (previous report of 2026-09-20: semaines), probably an old report format.
- Statuses in progress not compared: missing key(s) (previous report of 2026-09-20: wip_par_etat), probably an old report format.
- Partial comparison: section(s) skipped for lack of keys in one of the two reports: Throughput, Lead time, Work in progress, Aging, Forecasts.

## Throughput

- Throughput not compared: missing key(s) (previous report of 2026-09-20: periode ; new report of 2026-10-04: debit), probably an old report format.

## Lead time (from creation to resolution)

- Lead time not compared: missing key(s) (previous report of 2026-09-20: lead_time_par_type), probably an old report format.

## Work in progress

- Work in progress not compared: missing key(s) (previous report of 2026-09-20: wip), probably an old report format.

## Aging of the items in progress

- Aging not compared: missing key(s) (previous report of 2026-09-20: age_seuils), probably an old report format.

## Forecasts

- Forecasts not compared: missing key(s) (previous report of 2026-09-20: prevision_combien), probably an old report format.

## Limits

- The two windows overlap: over the common weeks, it is the same data. Only the new weeks say what changed in the throughput.
- Counts are net: an item that left the WIP and another that entered cancel each other out. The script keeps no ticket identifier, so it cannot say which items crossed a threshold.
- By team, the series are short: a gap of one or two units is enough to cross a threshold.

Evolution: <WS>/Flux-Lab/rapports/evolution-evo3-2026-10-04.md
--- stderr ---
written: rapports/evolution-evo3-2026-10-04.json
written: rapports/evolution-evo3-2026-10-04.md

===== compare-evo4-no-date =====
$ compare --name evo4
exit code: 1
--- stdout ---
--- stderr ---
One of the two reports has no date: comparison impossible.

===== compare-evo5-single =====
$ compare --name evo5
exit code: 1
--- stdout ---
--- stderr ---
At least two reports "evo5" are needed in <WS>/Flux-Lab/rapports (found: 2026-10-04).

===== compare-evo-missing-after =====
$ compare --name evo --after 2030-01-01
exit code: 1
--- stdout ---
--- stderr ---
No report "evo" of 2030-01-01 (available: 2026-09-20, 2026-10-04).

===== compare-evo-missing-before =====
$ compare --name evo --before 2020-01-01 --after 2026-10-04
exit code: 1
--- stdout ---
--- stderr ---
No report "evo" older than 2026-10-04 to compare with (available: 2026-09-20, 2026-10-04).

===== compare-evo-too-old =====
$ compare --name evo --after 2026-09-20
exit code: 1
--- stdout ---
--- stderr ---
No report "evo" older than 2026-09-20 to compare with (available: 2026-09-20, 2026-10-04).

===== compare-evo6-reversed-dates =====
$ compare --name evo6
exit code: 1
--- stdout ---
--- stderr ---
The "before" report (2026-10-04) must be older than the "after" report (2026-10-04).

===== compare-no-name =====
$ compare
exit code: 1
--- stdout ---
--- stderr ---
At least two reports "(no name)" are needed in <WS>/Flux-Lab/rapports (found: 2026-10-04).

===== err-scope-empty =====
$ compute <WS>/a.csv --today 2026-10-04 --no-comparison --scope ,
exit code: 1
--- stdout ---
--- stderr ---
--scope: give project keys separated by commas, or "all".

===== err-scope-no-key =====
$ compute <WS>/no-key.csv --today 2026-10-04 --no-comparison --scope ABC
exit code: 1
--- stdout ---
--- stderr ---
--scope: the export has no key column, so projects cannot be recognised.

===== err-scope-no-ticket =====
$ compute <WS>/a.csv --today 2026-10-04 --no-comparison --scope QQQ
exit code: 1
--- stdout ---
--- stderr ---
--scope: no ticket of the requested projects in the export.

===== err-no-resolved =====
$ compute <WS>/no-resolved.csv --today 2026-10-04
exit code: 1
--- stdout ---
--- stderr ---
Column "Resolved" is missing from the export: add it (see the statuses command).

===== err-dormants-removed =====
$ compute <WS>/a.csv --today 2026-10-04 --no-comparison --dormants <WS>/dormants.csv
exit code: 1
--- stdout ---
--- stderr ---
--dormants (dormant tickets CSV export) no longer exists: dormant items are inferred from the status history. Use --dormant-from-history (with --history or the default cache of history_jira.py).

===== err-dormant-history-no-key =====
$ compute <WS>/no-key.csv --today 2026-10-04 --no-comparison --dormant-from-history
exit code: 1
--- stdout ---
--- stderr ---
--dormant-from-history: the main export has no key column, so tickets cannot be linked to their history.

===== err-history-no-key =====
$ compute <WS>/no-key.csv --today 2026-10-04 --no-comparison --history
exit code: 1
--- stdout ---
--- stderr ---
--history: the export has no key column, so tickets cannot be linked to their history.

===== err-no-history-in-db =====
$ compute <WS>/a.csv --today 2026-10-04 --no-comparison --history <WS>/absent.json
exit code: 1
--- stdout ---
--- stderr ---
no history in the database: run the history collection first

===== err-teams-only-no-team =====
$ compute <WS>/no-key.csv --today 2026-10-04 --no-comparison --teams-only
exit code: 1
--- stdout ---
--- stderr ---
--teams-only: no team column in the export.

===== err-resolutions-empty =====
$ compute <WS>/a.csv --today 2026-10-04 --no-comparison --batch-closure-resolutions  , 
exit code: 1
--- stdout ---
--- stderr ---
--batch-closure-resolutions: give resolutions separated by commas ("Done,Accepted & Released"), or "all" for every delivered resolution.

===== err-threshold-invalid =====
$ compute <WS>/a.csv --today 2026-10-04 --no-comparison
exit code: 1
--- stdout ---
--- stderr ---
batch_closure_threshold (flux.yaml): an integer of at least 2.

===== err-commitment-point =====
$ compute <WS>/a.csv --today 2026-10-04 --no-comparison --history
exit code: 1
--- stdout ---
--- stderr ---
commitment_point: "nowhere" is not a segment of flux.yaml (definition, ready, implementation, review_verification, acceptance).

===== config-nothing-to-migrate =====
$ config migrate
exit code: 0
--- stdout ---
Nothing to migrate: flux.yaml already uses the English names.
--- stderr ---

===== config-dry-run =====
$ config migrate --dry-run
exit code: 0
--- stdout ---
Changes that would be made in flux.yaml (3):
  L1 : etats_attente -> waiting_states
  L2 : projets_exclus -> excluded_projects
  L3 : seuil_fermetures_groupees -> batch_closure_threshold
--- stderr ---

===== config-migrate =====
$ config migrate
exit code: 0
--- stdout ---
Changes made in flux.yaml (3):
  L1 : etats_attente -> waiting_states
  L2 : projets_exclus -> excluded_projects
  L3 : seuil_fermetures_groupees -> batch_closure_threshold
The old file is kept: flux.yaml.avant-migration
--- stderr ---

===== config-file-missing =====
$ config migrate
exit code: 1
--- stdout ---
--- stderr ---
<WS>/Flux-Lab/flux.yaml not found: nothing to migrate.
