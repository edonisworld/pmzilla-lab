# segment_sample.py, test run

## sample (exit 0)

````
# Sample of the segment "review_verification"

Period: 2026-04-06 to 2026-10-04 (26 full weeks at most), computed on 2026-10-06.
Keys and statuses only; nothing is written to disk.

## Statuses of the segment ("segments" setting of flux.yaml)

- Ready for Review (Implementation)
- Review - Ongoing (Impl.)
- Review - On Hold (Impl.)
- Ready for Verification
- Verification
- Verification - Ongoing
- Verification - On Hold

Other segments, by number of statuses: definition (8), ready (1), implementation (6), acceptance (2).

## Population

53 tickets read after discarding (2 discarded), 1 without history in the cache.

Tickets that left the segment during the period: 46; cumulative time P50 24 d, P85 38 d, mean 33.4 d, maximum 200 d.
Visits per ticket: 1 visit 45, 2 visits or more 1.

## The 6 longest (cumulative time)

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| CCC-1 | CCC | 200 | 1 | 2026-01-10 | 2026-07-29 | 200 | Open | Implementation - Ongoing |
| CCC-2 | CCC | 190 | 1 | 2026-01-10 | 2026-07-19 | 190 | Open | Implementation - Ongoing |
| CCC-3 | CCC | 180 | 1 | 2026-01-10 | 2026-07-09 | 180 | Open | Implementation - Ongoing |
| FFF-1 | FFF | 60 | 1 | 2026-05-02 | 2026-07-01 | 60 | Open | Done |
| AAA-1 | AAA | 56 | 2 | 2026-05-10 | 2026-06-20 | 41 | Code Review (Impl) | Implementation - Ongoing |
| BBB-40 | BBB | 40 | 1 | 2026-05-01 | 2026-06-10 | 40 | Open | Implementation - Ongoing |

## 4 tickets near the median (random draw, seed 42)

Window: from 19.0 to 28.0 d (P40 to P60); 10 candidates.

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| BBB-28 | BBB | 28 | 1 | 2026-05-01 | 2026-05-29 | 28 | Open | Implementation - Ongoing |
| BBB-23 | BBB | 23 | 1 | 2026-05-01 | 2026-05-24 | 23 | Open | Implementation - Ongoing |
| BBB-20 | BBB | 20 | 1 | 2026-05-01 | 2026-05-21 | 20 | Open | Implementation - Ongoing |
| BBB-19 | BBB | 19 | 1 | 2026-05-01 | 2026-05-20 | 19 | Open | Implementation - Ongoing |

## The 3 oldest still in the segment (out of 4)

| Key | Project | Age of the current visit (d) | Entry | Cumulative days (previous visits included) | Visits (current one included) | Current status | Origin |
|---|---|---|---|---|---|---|---|
| DDD-1 | DDD | 219 | 2026-03-01 | 219 | 1 | Ready for Verification | Open |
| DDD-2 | DDD | 188 | 2026-04-01 | 188 | 1 | Ready for Verification | Open |
| DDD-3 | DDD | 158 | 2026-05-01 | 158 | 1 | Ready for Verification | Open |
````

## --by-state (exit 0)

````
# Sample of the segment "review_verification"

Period: 2026-04-06 to 2026-10-04 (26 full weeks at most), computed on 2026-10-06.
Keys and statuses only; nothing is written to disk.

## Statuses of the segment ("segments" setting of flux.yaml)

- Ready for Review (Implementation)
- Review - Ongoing (Impl.)
- Review - On Hold (Impl.)
- Ready for Verification
- Verification
- Verification - Ongoing
- Verification - On Hold

Other segments, by number of statuses: definition (8), ready (1), implementation (6), acceptance (2).

## Population

53 tickets read after discarding (2 discarded), 1 without history in the cache.

Tickets that left the segment during the period: 46; cumulative time P50 24 d, P85 38 d, mean 33.4 d, maximum 200 d.
Visits per ticket: 1 visit 45, 2 visits or more 1.

## The 6 longest (cumulative time)

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| CCC-1 | CCC | 200 | 1 | 2026-01-10 | 2026-07-29 | 200 | Open | Implementation - Ongoing |
| CCC-2 | CCC | 190 | 1 | 2026-01-10 | 2026-07-19 | 190 | Open | Implementation - Ongoing |
| CCC-3 | CCC | 180 | 1 | 2026-01-10 | 2026-07-09 | 180 | Open | Implementation - Ongoing |
| FFF-1 | FFF | 60 | 1 | 2026-05-02 | 2026-07-01 | 60 | Open | Done |
| AAA-1 | AAA | 56 | 2 | 2026-05-10 | 2026-06-20 | 41 | Code Review (Impl) | Implementation - Ongoing |
| BBB-40 | BBB | 40 | 1 | 2026-05-01 | 2026-06-10 | 40 | Open | Implementation - Ongoing |

## 4 tickets near the median (random draw, seed 42)

Window: from 19.0 to 28.0 d (P40 to P60); 10 candidates.

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| BBB-28 | BBB | 28 | 1 | 2026-05-01 | 2026-05-29 | 28 | Open | Implementation - Ongoing |
| BBB-23 | BBB | 23 | 1 | 2026-05-01 | 2026-05-24 | 23 | Open | Implementation - Ongoing |
| BBB-20 | BBB | 20 | 1 | 2026-05-01 | 2026-05-21 | 20 | Open | Implementation - Ongoing |
| BBB-19 | BBB | 19 | 1 | 2026-05-01 | 2026-05-20 | 19 | Open | Implementation - Ongoing |

## The 3 oldest still in the segment (out of 4)

| Key | Project | Age of the current visit (d) | Entry | Cumulative days (previous visits included) | Visits (current one included) | Current status | Origin |
|---|---|---|---|---|---|---|---|
| DDD-1 | DDD | 219 | 2026-03-01 | 219 | 1 | Ready for Verification | Open |
| DDD-2 | DDD | 188 | 2026-04-01 | 188 | 1 | Ready for Verification | Open |
| DDD-3 | DDD | 158 | 2026-05-01 | 158 | 1 | Ready for Verification | Open |

## Time per status of the segment (population of 46 tickets that left)

| Status | Tickets that went through the status | Total (d) | Share of segment time | P50 (d) | P85 (d) |
|---|---|---|---|---|---|
| Ready for Review (Implementation) | 0 | 0 | 0.0% | - | - |
| Review - Ongoing (Impl.) | 0 | 0 | 0.0% | - | - |
| Review - On Hold (Impl.) | 0 | 0 | 0.0% | - | - |
| Ready for Verification | 46 | 1526 | 99.3% | 24 | 38 |
| Verification | 0 | 0 | 0.0% | - | - |
| Verification - Ongoing | 1 | 10 | 0.7% | 10 | 10 |
| Verification - On Hold | 0 | 0 | 0.0% | - | - |

Segment total: 1536 d (sum of the cumulative times). P50 and P85: days spent in the status per ticket, summed over the visits, among the tickets that went through the status.

## Per-status detail of the sampled tickets

| Key | Group | Total (d) | Ready for Review (Implementation) | Review - Ongoing (Impl.) | Review - On Hold (Impl.) | Ready for Verification | Verification | Verification - Ongoing | Verification - On Hold |
|---|---|---|---|---|---|---|---|---|---|
| CCC-1 | longest | 200 | - | - | - | 200 | - | - | - |
| CCC-2 | longest | 190 | - | - | - | 190 | - | - | - |
| CCC-3 | longest | 180 | - | - | - | 180 | - | - | - |
| FFF-1 | longest | 60 | - | - | - | 60 | - | - | - |
| AAA-1 | longest | 56 | - | - | - | 46 | - | 10 | - |
| BBB-40 | longest | 40 | - | - | - | 40 | - | - | - |
| BBB-28 | drawn near the median | 28 | - | - | - | 28 | - | - | - |
| BBB-23 | drawn near the median | 23 | - | - | - | 23 | - | - | - |
| BBB-20 | drawn near the median | 20 | - | - | - | 20 | - | - | - |
| BBB-19 | drawn near the median | 19 | - | - | - | 19 | - | - | - |
| DDD-1 | still in the segment | 219 | - | - | - | 219 | - | - | - |
| DDD-2 | still in the segment | 188 | - | - | - | 188 | - | - | - |
| DDD-3 | still in the segment | 158 | - | - | - | 158 | - | - | - |

"-": the ticket did not go through the status. For a ticket still in the segment, the total and the detail include the current visit, up to the computation date.

## Grouped exits of the 6 longest

| Key | Exit of the longest visit | Other tickets that left the segment that day |
|---|---|---|
| CCC-1 | 2026-07-29 | 0 |
| CCC-2 | 2026-07-19 | 0 |
| CCC-3 | 2026-07-09 | 0 |
| FFF-1 | 2026-07-01 | 1 |
| AAA-1 | 2026-06-20 | 0 |
| BBB-40 | 2026-06-10 | 0 |

Benchmark: over the 46 days when at least one ticket of the population left the segment, P50 1 and P85 1 exits per day, maximum 2 on 2026-07-01.
````

## --starts, no project reaches the threshold (exit 0)

````
# Sample of the segment "review_verification"

Period: 2026-04-06 to 2026-10-04 (26 full weeks at most), computed on 2026-10-06.
Keys and statuses only; nothing is written to disk.

## Statuses of the segment ("segments" setting of flux.yaml)

- Ready for Review (Implementation)
- Review - Ongoing (Impl.)
- Review - On Hold (Impl.)
- Ready for Verification
- Verification
- Verification - Ongoing
- Verification - On Hold

Other segments, by number of statuses: definition (8), ready (1), implementation (6), acceptance (2).

## Population

53 tickets read after discarding (2 discarded), 1 without history in the cache.

Tickets that left the segment during the period: 46; cumulative time P50 24 d, P85 38 d, mean 33.4 d, maximum 200 d.
Visits per ticket: 1 visit 45, 2 visits or more 1.

## The 6 longest (cumulative time)

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| CCC-1 | CCC | 200 | 1 | 2026-01-10 | 2026-07-29 | 200 | Open | Implementation - Ongoing |
| CCC-2 | CCC | 190 | 1 | 2026-01-10 | 2026-07-19 | 190 | Open | Implementation - Ongoing |
| CCC-3 | CCC | 180 | 1 | 2026-01-10 | 2026-07-09 | 180 | Open | Implementation - Ongoing |
| FFF-1 | FFF | 60 | 1 | 2026-05-02 | 2026-07-01 | 60 | Open | Done |
| AAA-1 | AAA | 56 | 2 | 2026-05-10 | 2026-06-20 | 41 | Code Review (Impl) | Implementation - Ongoing |
| BBB-40 | BBB | 40 | 1 | 2026-05-01 | 2026-06-10 | 40 | Open | Implementation - Ongoing |

## 4 tickets near the median (random draw, seed 42)

Window: from 19.0 to 28.0 d (P40 to P60); 10 candidates.

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| BBB-28 | BBB | 28 | 1 | 2026-05-01 | 2026-05-29 | 28 | Open | Implementation - Ongoing |
| BBB-23 | BBB | 23 | 1 | 2026-05-01 | 2026-05-24 | 23 | Open | Implementation - Ongoing |
| BBB-20 | BBB | 20 | 1 | 2026-05-01 | 2026-05-21 | 20 | Open | Implementation - Ongoing |
| BBB-19 | BBB | 19 | 1 | 2026-05-01 | 2026-05-20 | 19 | Open | Implementation - Ongoing |

## The 3 oldest still in the segment (out of 4)

| Key | Project | Age of the current visit (d) | Entry | Cumulative days (previous visits included) | Visits (current one included) | Current status | Origin |
|---|---|---|---|---|---|---|---|
| DDD-1 | DDD | 219 | 2026-03-01 | 219 | 1 | Ready for Verification | Open |
| DDD-2 | DDD | 188 | 2026-04-01 | 188 | 1 | Ready for Verification | Open |
| DDD-3 | DDD | 158 | 2026-05-01 | 158 | 1 | Ready for Verification | Open |

## Moves from "Ready for Verification" to "Verification - Ongoing" by project

1 moves in the finished visits of the population, 1 tickets concerned. Projects listed: at least 20 moves; 1 project(s) below the threshold (1 moves) not listed.

No project reaches the threshold.
````

## --near-median beyond the candidates, --oldest, --by-state (exit 0)

````
# Sample of the segment "review_verification"

Period: 2026-04-06 to 2026-10-04 (26 full weeks at most), computed on 2026-10-06.
Keys and statuses only; nothing is written to disk.

## Statuses of the segment ("segments" setting of flux.yaml)

- Ready for Review (Implementation)
- Review - Ongoing (Impl.)
- Review - On Hold (Impl.)
- Ready for Verification
- Verification
- Verification - Ongoing
- Verification - On Hold

Other segments, by number of statuses: definition (8), ready (1), implementation (6), acceptance (2).

## Population

53 tickets read after discarding (2 discarded), 1 without history in the cache.

Tickets that left the segment during the period: 46; cumulative time P50 24 d, P85 38 d, mean 33.4 d, maximum 200 d.
Visits per ticket: 1 visit 45, 2 visits or more 1.

## The 2 longest (cumulative time)

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| CCC-1 | CCC | 200 | 1 | 2026-01-10 | 2026-07-29 | 200 | Open | Implementation - Ongoing |
| CCC-2 | CCC | 190 | 1 | 2026-01-10 | 2026-07-19 | 190 | Open | Implementation - Ongoing |

## 10 tickets near the median (random draw, seed 42)

Window: from 19.0 to 28.0 d (P40 to P60); 10 candidates.

Warning: only 10 candidate(s) for 100 requested.

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| BBB-28 | BBB | 28 | 1 | 2026-05-01 | 2026-05-29 | 28 | Open | Implementation - Ongoing |
| BBB-27 | BBB | 27 | 1 | 2026-05-01 | 2026-05-28 | 27 | Open | Implementation - Ongoing |
| BBB-26 | BBB | 26 | 1 | 2026-05-01 | 2026-05-27 | 26 | Open | Implementation - Ongoing |
| BBB-25 | BBB | 25 | 1 | 2026-05-01 | 2026-05-26 | 25 | Open | Implementation - Ongoing |
| BBB-24 | BBB | 24 | 1 | 2026-05-01 | 2026-05-25 | 24 | Open | Implementation - Ongoing |
| BBB-23 | BBB | 23 | 1 | 2026-05-01 | 2026-05-24 | 23 | Open | Implementation - Ongoing |
| BBB-22 | BBB | 22 | 1 | 2026-05-01 | 2026-05-23 | 22 | Open | Implementation - Ongoing |
| BBB-21 | BBB | 21 | 1 | 2026-05-01 | 2026-05-22 | 21 | Open | Implementation - Ongoing |
| BBB-20 | BBB | 20 | 1 | 2026-05-01 | 2026-05-21 | 20 | Open | Implementation - Ongoing |
| BBB-19 | BBB | 19 | 1 | 2026-05-01 | 2026-05-20 | 19 | Open | Implementation - Ongoing |

## The 4 oldest still in the segment (out of 4)

| Key | Project | Age of the current visit (d) | Entry | Cumulative days (previous visits included) | Visits (current one included) | Current status | Origin |
|---|---|---|---|---|---|---|---|
| DDD-1 | DDD | 219 | 2026-03-01 | 219 | 1 | Ready for Verification | Open |
| DDD-2 | DDD | 188 | 2026-04-01 | 188 | 1 | Ready for Verification | Open |
| DDD-3 | DDD | 158 | 2026-05-01 | 158 | 1 | Ready for Verification | Open |
| DDD-4 | DDD | 127 | 2026-06-01 | 127 | 1 | Ready for Verification | Open |

## Time per status of the segment (population of 46 tickets that left)

| Status | Tickets that went through the status | Total (d) | Share of segment time | P50 (d) | P85 (d) |
|---|---|---|---|---|---|
| Ready for Review (Implementation) | 0 | 0 | 0.0% | - | - |
| Review - Ongoing (Impl.) | 0 | 0 | 0.0% | - | - |
| Review - On Hold (Impl.) | 0 | 0 | 0.0% | - | - |
| Ready for Verification | 46 | 1526 | 99.3% | 24 | 38 |
| Verification | 0 | 0 | 0.0% | - | - |
| Verification - Ongoing | 1 | 10 | 0.7% | 10 | 10 |
| Verification - On Hold | 0 | 0 | 0.0% | - | - |

Segment total: 1536 d (sum of the cumulative times). P50 and P85: days spent in the status per ticket, summed over the visits, among the tickets that went through the status.

## Per-status detail of the sampled tickets

| Key | Group | Total (d) | Ready for Review (Implementation) | Review - Ongoing (Impl.) | Review - On Hold (Impl.) | Ready for Verification | Verification | Verification - Ongoing | Verification - On Hold |
|---|---|---|---|---|---|---|---|---|---|
| CCC-1 | longest | 200 | - | - | - | 200 | - | - | - |
| CCC-2 | longest | 190 | - | - | - | 190 | - | - | - |
| BBB-28 | drawn near the median | 28 | - | - | - | 28 | - | - | - |
| BBB-27 | drawn near the median | 27 | - | - | - | 27 | - | - | - |
| BBB-26 | drawn near the median | 26 | - | - | - | 26 | - | - | - |
| BBB-25 | drawn near the median | 25 | - | - | - | 25 | - | - | - |
| BBB-24 | drawn near the median | 24 | - | - | - | 24 | - | - | - |
| BBB-23 | drawn near the median | 23 | - | - | - | 23 | - | - | - |
| BBB-22 | drawn near the median | 22 | - | - | - | 22 | - | - | - |
| BBB-21 | drawn near the median | 21 | - | - | - | 21 | - | - | - |
| BBB-20 | drawn near the median | 20 | - | - | - | 20 | - | - | - |
| BBB-19 | drawn near the median | 19 | - | - | - | 19 | - | - | - |
| DDD-1 | still in the segment | 219 | - | - | - | 219 | - | - | - |
| DDD-2 | still in the segment | 188 | - | - | - | 188 | - | - | - |
| DDD-3 | still in the segment | 158 | - | - | - | 158 | - | - | - |
| DDD-4 | still in the segment | 127 | - | - | - | 127 | - | - | - |

"-": the ticket did not go through the status. For a ticket still in the segment, the total and the detail include the current visit, up to the computation date.

## Grouped exits of the 2 longest

| Key | Exit of the longest visit | Other tickets that left the segment that day |
|---|---|---|
| CCC-1 | 2026-07-29 | 0 |
| CCC-2 | 2026-07-19 | 0 |

Benchmark: over the 46 days when at least one ticket of the population left the segment, P50 1 and P85 1 exits per day, maximum 2 on 2026-07-01.
````

## segment given by its English name (exit 0)

````
# Sample of the segment "review_verification"

Period: 2026-04-06 to 2026-10-04 (26 full weeks at most), computed on 2026-10-06.
Keys and statuses only; nothing is written to disk.

## Statuses of the segment ("segments" setting of flux.yaml)

- Ready for Review (Implementation)
- Review - Ongoing (Impl.)
- Review - On Hold (Impl.)
- Ready for Verification
- Verification
- Verification - Ongoing
- Verification - On Hold

Other segments, by number of statuses: definition (8), ready (1), implementation (6), acceptance (2).

## Population

53 tickets read after discarding (2 discarded), 1 without history in the cache.

Tickets that left the segment during the period: 46; cumulative time P50 24 d, P85 38 d, mean 33.4 d, maximum 200 d.
Visits per ticket: 1 visit 45, 2 visits or more 1.

## The 6 longest (cumulative time)

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| CCC-1 | CCC | 200 | 1 | 2026-01-10 | 2026-07-29 | 200 | Open | Implementation - Ongoing |
| CCC-2 | CCC | 190 | 1 | 2026-01-10 | 2026-07-19 | 190 | Open | Implementation - Ongoing |
| CCC-3 | CCC | 180 | 1 | 2026-01-10 | 2026-07-09 | 180 | Open | Implementation - Ongoing |
| FFF-1 | FFF | 60 | 1 | 2026-05-02 | 2026-07-01 | 60 | Open | Done |
| AAA-1 | AAA | 56 | 2 | 2026-05-10 | 2026-06-20 | 41 | Code Review (Impl) | Implementation - Ongoing |
| BBB-40 | BBB | 40 | 1 | 2026-05-01 | 2026-06-10 | 40 | Open | Implementation - Ongoing |

## 4 tickets near the median (random draw, seed 42)

Window: from 19.0 to 28.0 d (P40 to P60); 10 candidates.

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| BBB-28 | BBB | 28 | 1 | 2026-05-01 | 2026-05-29 | 28 | Open | Implementation - Ongoing |
| BBB-23 | BBB | 23 | 1 | 2026-05-01 | 2026-05-24 | 23 | Open | Implementation - Ongoing |
| BBB-20 | BBB | 20 | 1 | 2026-05-01 | 2026-05-21 | 20 | Open | Implementation - Ongoing |
| BBB-19 | BBB | 19 | 1 | 2026-05-01 | 2026-05-20 | 19 | Open | Implementation - Ongoing |

## The 3 oldest still in the segment (out of 4)

| Key | Project | Age of the current visit (d) | Entry | Cumulative days (previous visits included) | Visits (current one included) | Current status | Origin |
|---|---|---|---|---|---|---|---|
| DDD-1 | DDD | 219 | 2026-03-01 | 219 | 1 | Ready for Verification | Open |
| DDD-2 | DDD | 188 | 2026-04-01 | 188 | 1 | Ready for Verification | Open |
| DDD-3 | DDD | 158 | 2026-05-01 | 158 | 1 | Ready for Verification | Open |
````

## --segment unknown (exit 1)

````
[stderr]
--segment: "whatever" is not a computed segment (definition, ready, implementation, review_verification, acceptance).
````

## --scope without a match (exit 1)

````
[stderr]
--scope: no ticket of the requested projects in the export.
````

## --starts outside the segment (exit 1)

````
# Sample of the segment "implementation"

Period: 2026-04-06 to 2026-10-04 (26 full weeks at most), computed on 2026-10-06.
Keys and statuses only; nothing is written to disk.

## Statuses of the segment ("segments" setting of flux.yaml)

- Implementation
- Implementation - Ongoing
- Implementation - On Hold
- Analysis (Impl)
- Code Review (Impl)
- R&D Test (Impl)

Other segments, by number of statuses: definition (8), ready (1), review_verification (7), acceptance (2).

## Population

53 tickets read after discarding (2 discarded), 1 without history in the cache.

Tickets that left the segment during the period: 3; cumulative time P50 13 d, P85 28 d, mean 16.0 d, maximum 34 d.
Visits per ticket: 1 visit 2, 2 visits or more 1.

## The 3 longest (cumulative time)

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| RRR-1 | RRR | 34 | 1 | 2026-03-05 | 2026-04-08 | 34 | Open | Done |
| AAA-1 | AAA | 13 | 2 | 2026-05-02 | 2026-05-10 | 8 | Open | Ready for Verification |
| GGG-1 | GGG | 1 | 1 | 2026-07-01 | 2026-07-02 | 1 | Ready for Verification | Done |

## 0 tickets near the median (random draw, seed 42)

Window: from 10.6 to 17.2 d (P40 to P60); 0 candidates.

Warning: only 0 candidate(s) for 4 requested.

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|

## The 3 oldest still in the segment (out of 44)

| Key | Project | Age of the current visit (d) | Entry | Cumulative days (previous visits included) | Visits (current one included) | Current status | Origin |
|---|---|---|---|---|---|---|---|
| EEE-1 | EEE | 219 | 2026-03-01 | 219 | 1 | Implementation - Ongoing | Ready for Verification |
| BBB-1 | BBB | 157 | 2026-05-02 | 157 | 1 | Implementation - Ongoing | Ready for Verification |
| BBB-2 | BBB | 156 | 2026-05-03 | 156 | 1 | Implementation - Ongoing | Ready for Verification |
[stderr]
--starts: status(es) outside the segment "implementation": Ready for Verification, Verification - Ongoing.
````

## --longest 100, creation and resolution from the segment (exit 0)

````
# Sample of the segment "review_verification"

Period: 2026-04-06 to 2026-10-04 (26 full weeks at most), computed on 2026-10-06.
Keys and statuses only; nothing is written to disk.

## Statuses of the segment ("segments" setting of flux.yaml)

- Ready for Review (Implementation)
- Review - Ongoing (Impl.)
- Review - On Hold (Impl.)
- Ready for Verification
- Verification
- Verification - Ongoing
- Verification - On Hold

Other segments, by number of statuses: definition (8), ready (1), implementation (6), acceptance (2).

## Population

54 tickets read after discarding (2 discarded), 1 without history in the cache.

Tickets that left the segment during the period: 47; cumulative time P50 24 d, P85 38 d, mean 33.3 d, maximum 200 d.
Visits per ticket: 1 visit 46, 2 visits or more 1.

## The 47 longest (cumulative time)

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| CCC-1 | CCC | 200 | 1 | 2026-01-10 | 2026-07-29 | 200 | Open | Implementation - Ongoing |
| CCC-2 | CCC | 190 | 1 | 2026-01-10 | 2026-07-19 | 190 | Open | Implementation - Ongoing |
| CCC-3 | CCC | 180 | 1 | 2026-01-10 | 2026-07-09 | 180 | Open | Implementation - Ongoing |
| FFF-1 | FFF | 60 | 1 | 2026-05-02 | 2026-07-01 | 60 | Open | Done |
| AAA-1 | AAA | 56 | 2 | 2026-05-10 | 2026-06-20 | 41 | Code Review (Impl) | Implementation - Ongoing |
| BBB-40 | BBB | 40 | 1 | 2026-05-01 | 2026-06-10 | 40 | Open | Implementation - Ongoing |
| BBB-39 | BBB | 39 | 1 | 2026-05-01 | 2026-06-09 | 39 | Open | Implementation - Ongoing |
| BBB-38 | BBB | 38 | 1 | 2026-05-01 | 2026-06-08 | 38 | Open | Implementation - Ongoing |
| BBB-37 | BBB | 37 | 1 | 2026-05-01 | 2026-06-07 | 37 | Open | Implementation - Ongoing |
| BBB-36 | BBB | 36 | 1 | 2026-05-01 | 2026-06-06 | 36 | Open | Implementation - Ongoing |
| BBB-35 | BBB | 35 | 1 | 2026-05-01 | 2026-06-05 | 35 | Open | Implementation - Ongoing |
| BBB-34 | BBB | 34 | 1 | 2026-05-01 | 2026-06-04 | 34 | Open | Implementation - Ongoing |
| BBB-33 | BBB | 33 | 1 | 2026-05-01 | 2026-06-03 | 33 | Open | Implementation - Ongoing |
| BBB-32 | BBB | 32 | 1 | 2026-05-01 | 2026-06-02 | 32 | Open | Implementation - Ongoing |
| BBB-31 | BBB | 31 | 1 | 2026-05-01 | 2026-06-01 | 31 | Open | Implementation - Ongoing |
| BBB-30 | BBB | 30 | 1 | 2026-05-01 | 2026-05-31 | 30 | Open | Implementation - Ongoing |
| GGG-1 | GGG | 30 | 1 | 2026-06-01 | 2026-07-01 | 30 | (creation) | Implementation - Ongoing |
| HHH-1 | HHH | 30 | 1 | 2026-05-02 | 2026-06-01 | 30 | Open | (resolved from the segment) |
| BBB-29 | BBB | 29 | 1 | 2026-05-01 | 2026-05-30 | 29 | Open | Implementation - Ongoing |
| BBB-28 | BBB | 28 | 1 | 2026-05-01 | 2026-05-29 | 28 | Open | Implementation - Ongoing |
| BBB-27 | BBB | 27 | 1 | 2026-05-01 | 2026-05-28 | 27 | Open | Implementation - Ongoing |
| BBB-26 | BBB | 26 | 1 | 2026-05-01 | 2026-05-27 | 26 | Open | Implementation - Ongoing |
| BBB-25 | BBB | 25 | 1 | 2026-05-01 | 2026-05-26 | 25 | Open | Implementation - Ongoing |
| BBB-24 | BBB | 24 | 1 | 2026-05-01 | 2026-05-25 | 24 | Open | Implementation - Ongoing |
| BBB-23 | BBB | 23 | 1 | 2026-05-01 | 2026-05-24 | 23 | Open | Implementation - Ongoing |
| BBB-22 | BBB | 22 | 1 | 2026-05-01 | 2026-05-23 | 22 | Open | Implementation - Ongoing |
| BBB-21 | BBB | 21 | 1 | 2026-05-01 | 2026-05-22 | 21 | Open | Implementation - Ongoing |
| BBB-20 | BBB | 20 | 1 | 2026-05-01 | 2026-05-21 | 20 | Open | Implementation - Ongoing |
| BBB-19 | BBB | 19 | 1 | 2026-05-01 | 2026-05-20 | 19 | Open | Implementation - Ongoing |
| BBB-18 | BBB | 18 | 1 | 2026-05-01 | 2026-05-19 | 18 | Open | Implementation - Ongoing |
| BBB-17 | BBB | 17 | 1 | 2026-05-01 | 2026-05-18 | 17 | Open | Implementation - Ongoing |
| BBB-16 | BBB | 16 | 1 | 2026-05-01 | 2026-05-17 | 16 | Open | Implementation - Ongoing |
| BBB-15 | BBB | 15 | 1 | 2026-05-01 | 2026-05-16 | 15 | Open | Implementation - Ongoing |
| BBB-14 | BBB | 14 | 1 | 2026-05-01 | 2026-05-15 | 14 | Open | Implementation - Ongoing |
| BBB-13 | BBB | 13 | 1 | 2026-05-01 | 2026-05-14 | 13 | Open | Implementation - Ongoing |
| BBB-12 | BBB | 12 | 1 | 2026-05-01 | 2026-05-13 | 12 | Open | Implementation - Ongoing |
| BBB-11 | BBB | 11 | 1 | 2026-05-01 | 2026-05-12 | 11 | Open | Implementation - Ongoing |
| BBB-10 | BBB | 10 | 1 | 2026-05-01 | 2026-05-11 | 10 | Open | Implementation - Ongoing |
| BBB-9 | BBB | 9 | 1 | 2026-05-01 | 2026-05-10 | 9 | Open | Implementation - Ongoing |
| BBB-8 | BBB | 8 | 1 | 2026-05-01 | 2026-05-09 | 8 | Open | Implementation - Ongoing |
| BBB-7 | BBB | 7 | 1 | 2026-05-01 | 2026-05-08 | 7 | Open | Implementation - Ongoing |
| BBB-6 | BBB | 6 | 1 | 2026-05-01 | 2026-05-07 | 6 | Open | Implementation - Ongoing |
| BBB-5 | BBB | 5 | 1 | 2026-05-01 | 2026-05-06 | 5 | Open | Implementation - Ongoing |
| BBB-4 | BBB | 4 | 1 | 2026-05-01 | 2026-05-05 | 4 | Open | Implementation - Ongoing |
| BBB-3 | BBB | 3 | 1 | 2026-05-01 | 2026-05-04 | 3 | Open | Implementation - Ongoing |
| BBB-2 | BBB | 2 | 1 | 2026-05-01 | 2026-05-03 | 2 | Open | Implementation - Ongoing |
| BBB-1 | BBB | 1 | 1 | 2026-05-01 | 2026-05-02 | 1 | Open | Implementation - Ongoing |

## 0 tickets near the median (random draw, seed 42)

Window: from 19.4 to 28.6 d (P40 to P60); 0 candidates.

Warning: only 0 candidate(s) for 4 requested.

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|

## The 3 oldest still in the segment (out of 4)

| Key | Project | Age of the current visit (d) | Entry | Cumulative days (previous visits included) | Visits (current one included) | Current status | Origin |
|---|---|---|---|---|---|---|---|
| DDD-1 | DDD | 219 | 2026-03-01 | 219 | 1 | Ready for Verification | Open |
| DDD-2 | DDD | 188 | 2026-04-01 | 188 | 1 | Ready for Verification | Open |
| DDD-3 | DDD | 158 | 2026-05-01 | 158 | 1 | Ready for Verification | Open |
````

## segments set in flux.yaml (exit 0)

````
# Sample of the segment "review_verification"

Period: 2026-04-06 to 2026-10-04 (26 full weeks at most), computed on 2026-10-06.
Keys and statuses only; nothing is written to disk.

## Statuses of the segment ("segments" setting of flux.yaml)

- Ready for Verification
- Verification - Ongoing

Other segments, by number of statuses: other (1).

## Population

54 tickets read after discarding (2 discarded), 1 without history in the cache.

Tickets that left the segment during the period: 47; cumulative time P50 24 d, P85 38 d, mean 33.3 d, maximum 200 d.
Visits per ticket: 1 visit 46, 2 visits or more 1.

## The 6 longest (cumulative time)

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| CCC-1 | CCC | 200 | 1 | 2026-01-10 | 2026-07-29 | 200 | Open | Implementation - Ongoing |
| CCC-2 | CCC | 190 | 1 | 2026-01-10 | 2026-07-19 | 190 | Open | Implementation - Ongoing |
| CCC-3 | CCC | 180 | 1 | 2026-01-10 | 2026-07-09 | 180 | Open | Implementation - Ongoing |
| FFF-1 | FFF | 60 | 1 | 2026-05-02 | 2026-07-01 | 60 | Open | Done |
| AAA-1 | AAA | 56 | 2 | 2026-05-10 | 2026-06-20 | 41 | Code Review (Impl) | Implementation - Ongoing |
| BBB-40 | BBB | 40 | 1 | 2026-05-01 | 2026-06-10 | 40 | Open | Implementation - Ongoing |

## 4 tickets near the median (random draw, seed 42)

Window: from 19.4 to 28.6 d (P40 to P60); 9 candidates.

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| BBB-25 | BBB | 25 | 1 | 2026-05-01 | 2026-05-26 | 25 | Open | Implementation - Ongoing |
| BBB-22 | BBB | 22 | 1 | 2026-05-01 | 2026-05-23 | 22 | Open | Implementation - Ongoing |
| BBB-21 | BBB | 21 | 1 | 2026-05-01 | 2026-05-22 | 21 | Open | Implementation - Ongoing |
| BBB-20 | BBB | 20 | 1 | 2026-05-01 | 2026-05-21 | 20 | Open | Implementation - Ongoing |

## The 3 oldest still in the segment (out of 4)

| Key | Project | Age of the current visit (d) | Entry | Cumulative days (previous visits included) | Visits (current one included) | Current status | Origin |
|---|---|---|---|---|---|---|---|
| DDD-1 | DDD | 219 | 2026-03-01 | 219 | 1 | Ready for Verification | Open |
| DDD-2 | DDD | 188 | 2026-04-01 | 188 | 1 | Ready for Verification | Open |
| DDD-3 | DDD | 158 | 2026-05-01 | 158 | 1 | Ready for Verification | Open |

## Time per status of the segment (population of 47 tickets that left)

| Status | Tickets that went through the status | Total (d) | Share of segment time | P50 (d) | P85 (d) |
|---|---|---|---|---|---|
| Ready for Verification | 47 | 1556 | 99.4% | 24 | 38 |
| Verification - Ongoing | 1 | 10 | 0.6% | 10 | 10 |

Segment total: 1566 d (sum of the cumulative times). P50 and P85: days spent in the status per ticket, summed over the visits, among the tickets that went through the status.

## Per-status detail of the sampled tickets

| Key | Group | Total (d) | Ready for Verification | Verification - Ongoing |
|---|---|---|---|---|
| CCC-1 | longest | 200 | 200 | - |
| CCC-2 | longest | 190 | 190 | - |
| CCC-3 | longest | 180 | 180 | - |
| FFF-1 | longest | 60 | 60 | - |
| AAA-1 | longest | 56 | 46 | 10 |
| BBB-40 | longest | 40 | 40 | - |
| BBB-25 | drawn near the median | 25 | 25 | - |
| BBB-22 | drawn near the median | 22 | 22 | - |
| BBB-21 | drawn near the median | 21 | 21 | - |
| BBB-20 | drawn near the median | 20 | 20 | - |
| DDD-1 | still in the segment | 219 | 219 | - |
| DDD-2 | still in the segment | 188 | 188 | - |
| DDD-3 | still in the segment | 158 | 158 | - |

"-": the ticket did not go through the status. For a ticket still in the segment, the total and the detail include the current visit, up to the computation date.

## Grouped exits of the 6 longest

| Key | Exit of the longest visit | Other tickets that left the segment that day |
|---|---|---|
| CCC-1 | 2026-07-29 | 0 |
| CCC-2 | 2026-07-19 | 0 |
| CCC-3 | 2026-07-09 | 0 |
| FFF-1 | 2026-07-01 | 1 |
| AAA-1 | 2026-06-20 | 0 |
| BBB-40 | 2026-06-10 | 0 |

Benchmark: over the 46 days when at least one ticket of the population left the segment, P50 1 and P85 1 exits per day, maximum 2 on 2026-06-01.

## Moves from "Ready for Verification" to "Verification - Ongoing" by project

1 moves in the finished visits of the population, 1 tickets concerned. Projects listed: at least 20 moves; 1 project(s) below the threshold (1 moves) not listed.

No project reaches the threshold.
````

## nothing left the segment (exit 0)

````
# Sample of the segment "review_verification"

Period: 2026-04-06 to 2026-10-04 (26 full weeks at most), computed on 2026-10-06.
Keys and statuses only; nothing is written to disk.

## Statuses of the segment ("segments" setting of flux.yaml)

- Ready for Review (Implementation)
- Review - Ongoing (Impl.)
- Review - On Hold (Impl.)
- Ready for Verification
- Verification
- Verification - Ongoing
- Verification - On Hold

Other segments, by number of statuses: definition (8), ready (1), implementation (6), acceptance (2).

## Population

1 tickets read after discarding, 0 without history in the cache.

No ticket left the segment during the period: nothing to sample.
````

## export without a Resolved column (exit 1)

````
[stderr]
Column "Resolved" missing from the export: add it (see flux_jira.py statuses).
````

## export without a key column (exit 1)

````
[stderr]
The export has no key column, so tickets cannot be linked to their history.
````

## --starts by project (exit 0)

````
# Sample of the segment "review_verification"

Period: 2026-04-06 to 2026-10-04 (26 full weeks at most), computed on 2026-10-06.
Keys and statuses only; nothing is written to disk.

## Statuses of the segment ("segments" setting of flux.yaml)

- Ready for Review (Implementation)
- Review - Ongoing (Impl.)
- Review - On Hold (Impl.)
- Ready for Verification
- Verification
- Verification - Ongoing
- Verification - On Hold

Other segments, by number of statuses: definition (8), ready (1), implementation (6), acceptance (2).

## Population

96 tickets read after discarding, 0 without history in the cache.

Tickets that left the segment during the period: 95; cumulative time P50 26 d, P85 36 d, mean 28.1 d, maximum 50 d.
Visits per ticket: 1 visit 95, 2 visits or more 0.

## The 6 longest (cumulative time)

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| QQQ-30 | QQQ | 50 | 1 | 2026-05-01 | 2026-06-20 | 50 | Open | Implementation - Ongoing |
| QQQ-29 | QQQ | 49 | 1 | 2026-05-01 | 2026-06-19 | 49 | Open | Implementation - Ongoing |
| QQQ-28 | QQQ | 48 | 1 | 2026-05-01 | 2026-06-18 | 48 | Open | Implementation - Ongoing |
| QQQ-27 | QQQ | 47 | 1 | 2026-05-01 | 2026-06-17 | 47 | Open | Implementation - Ongoing |
| QQQ-26 | QQQ | 46 | 1 | 2026-05-01 | 2026-06-16 | 46 | Open | Implementation - Ongoing |
| QQQ-25 | QQQ | 45 | 1 | 2026-05-01 | 2026-06-15 | 45 | Open | Implementation - Ongoing |

## 4 tickets near the median (random draw, seed 42)

Window: from 24.0 to 27.0 d (P40 to P60); 22 candidates.

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| PPP-11 | PPP | 27 | 1 | 2026-05-01 | 2026-05-28 | 27 | Open | Implementation - Ongoing |
| PPP-14 | PPP | 27 | 1 | 2026-05-01 | 2026-05-28 | 27 | Open | Implementation - Ongoing |
| SANSPROJET6 |  | 26 | 1 | 2026-05-01 | 2026-05-27 | 26 | Open | Implementation - Ongoing |
| PPP-22 | PPP | 25 | 1 | 2026-05-01 | 2026-05-26 | 25 | Open | Implementation - Ongoing |

## The 0 oldest still in the segment (out of 0)

| Key | Project | Age of the current visit (d) | Entry | Cumulative days (previous visits included) | Visits (current one included) | Current status | Origin |
|---|---|---|---|---|---|---|---|

## Moves from "Ready for Verification" to "Verification - Ongoing" by project

95 moves in the finished visits of the population, 95 tickets concerned. Projects listed: at least 20 moves; 1 project(s) below the threshold (19 moves) not listed.

| Project | Moves | Distinct days | Busiest days kept (20%) | Share of moves on these days | Share expected at random (equal active days) | 95th percentile of the draws (equal active days) | More concentrated than chance at equal active days | Distinct days expected at random | 5th percentile of the distinct days | Ratio observed / expected days | Fewer active days than chance | P50 of the wait before the move (d) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| QQQ | 30 | 30 | 6 | 20.0% | 30.0% | 36.7% | no | 26.8 | 24.0 | 1.12 | no | 16 |
| PPP | 25 | 10 | 2 | 68.0% | 28.7% | 36.0% | yes | 22.7 | 20.0 | 0.44 | yes | 7 |
| (no project) | 21 | 9 | 2 | 28.6% | 27.5% | 38.1% | no | 19.4 | 17.0 | 0.46 | yes | 3 |

The wait is the time spent in "Ready for Verification" just before the move. The moves counted are those of finished visits, whatever their date, several per ticket when tickets go back and forth.
Both measures draw the project's moves at random, with replacement, over the 124 working days (Monday to Friday, French public holidays removed, Alsace-Moselle excepted) from 2026-04-06 to 2026-10-04; 1000 draws, seed 42, each draw having the same number of moves as the real data. Concentration at equal active days: each draw keeps its own number of distinct days and the rule of the 20% busiest days (rounded up) is applied to it; "yes" if the observed share is strictly above the 95th percentile of these shares. Because it takes the active days as given, it does not see a project that has only few active days: a project that starts in bursts almost always comes out "yes". Active days: the observed number of distinct days is compared with that of the draws (mean, 5th percentile, observed / expected ratio) without imposing anything on it; "yes" if the observed number is strictly below the 5th percentile of the draws, that is, fewer active days than chance produces. In the population, 54 move(s) fall on a weekend, a public holiday or outside the period: the model does not know them.
````

## --starts with a higher threshold (exit 0)

````
# Sample of the segment "review_verification"

Period: 2026-04-06 to 2026-10-04 (26 full weeks at most), computed on 2026-10-06.
Keys and statuses only; nothing is written to disk.

## Statuses of the segment ("segments" setting of flux.yaml)

- Ready for Review (Implementation)
- Review - Ongoing (Impl.)
- Review - On Hold (Impl.)
- Ready for Verification
- Verification
- Verification - Ongoing
- Verification - On Hold

Other segments, by number of statuses: definition (8), ready (1), implementation (6), acceptance (2).

## Population

96 tickets read after discarding, 0 without history in the cache.

Tickets that left the segment during the period: 95; cumulative time P50 26 d, P85 36 d, mean 28.1 d, maximum 50 d.
Visits per ticket: 1 visit 95, 2 visits or more 0.

## The 6 longest (cumulative time)

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| QQQ-30 | QQQ | 50 | 1 | 2026-05-01 | 2026-06-20 | 50 | Open | Implementation - Ongoing |
| QQQ-29 | QQQ | 49 | 1 | 2026-05-01 | 2026-06-19 | 49 | Open | Implementation - Ongoing |
| QQQ-28 | QQQ | 48 | 1 | 2026-05-01 | 2026-06-18 | 48 | Open | Implementation - Ongoing |
| QQQ-27 | QQQ | 47 | 1 | 2026-05-01 | 2026-06-17 | 47 | Open | Implementation - Ongoing |
| QQQ-26 | QQQ | 46 | 1 | 2026-05-01 | 2026-06-16 | 46 | Open | Implementation - Ongoing |
| QQQ-25 | QQQ | 45 | 1 | 2026-05-01 | 2026-06-15 | 45 | Open | Implementation - Ongoing |

## 4 tickets near the median (random draw, seed 42)

Window: from 24.0 to 27.0 d (P40 to P60); 22 candidates.

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| PPP-11 | PPP | 27 | 1 | 2026-05-01 | 2026-05-28 | 27 | Open | Implementation - Ongoing |
| PPP-14 | PPP | 27 | 1 | 2026-05-01 | 2026-05-28 | 27 | Open | Implementation - Ongoing |
| SANSPROJET6 |  | 26 | 1 | 2026-05-01 | 2026-05-27 | 26 | Open | Implementation - Ongoing |
| PPP-22 | PPP | 25 | 1 | 2026-05-01 | 2026-05-26 | 25 | Open | Implementation - Ongoing |

## The 0 oldest still in the segment (out of 0)

| Key | Project | Age of the current visit (d) | Entry | Cumulative days (previous visits included) | Visits (current one included) | Current status | Origin |
|---|---|---|---|---|---|---|---|

## Moves from "Ready for Verification" to "Verification - Ongoing" by project

95 moves in the finished visits of the population, 95 tickets concerned. Projects listed: at least 100 moves; 4 project(s) below the threshold (95 moves) not listed.

No project reaches the threshold.
````

## batch closures kept (exit 0)

````
# Sample of the segment "review_verification"

Period: 2026-04-06 to 2026-10-04 (26 full weeks at most), computed on 2026-10-06.
Keys and statuses only; nothing is written to disk.

## Statuses of the segment ("segments" setting of flux.yaml)

- Ready for Review (Implementation)
- Review - Ongoing (Impl.)
- Review - On Hold (Impl.)
- Ready for Verification
- Verification
- Verification - Ongoing
- Verification - On Hold

Other segments, by number of statuses: definition (8), ready (1), implementation (6), acceptance (2).

## Population

17 tickets read after discarding, 0 without history in the cache.

Tickets that left the segment during the period: 16; cumulative time P50 78 d, P85 80 d, mean 78.0 d, maximum 81 d.
Visits per ticket: 1 visit 16, 2 visits or more 0.

## The 6 longest (cumulative time)

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| PET-1 | PET | 81 | 1 | 2026-05-01 | 2026-07-21 | 81 | Open | Done |
| ETA-1 | ETA | 80 | 1 | 2026-05-01 | 2026-07-20 | 80 | Open | Done |
| LOT-1 | LOT | 80 | 1 | 2026-05-01 | 2026-07-20 | 80 | Open | Done |
| PET-2 | PET | 80 | 1 | 2026-05-02 | 2026-07-21 | 80 | Open | Done |
| ETA-2 | ETA | 79 | 1 | 2026-05-02 | 2026-07-20 | 79 | Open | Done |
| LOT-2 | LOT | 79 | 1 | 2026-05-02 | 2026-07-20 | 79 | Open | Done |

## 4 tickets near the median (random draw, seed 42)

Window: from 78.0 to 79.0 d (P40 to P60); 4 candidates.

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| PET-3 | PET | 79 | 1 | 2026-05-03 | 2026-07-21 | 79 | Open | Done |
| ETA-3 | ETA | 78 | 1 | 2026-05-03 | 2026-07-20 | 78 | Open | Done |
| LOT-3 | LOT | 78 | 1 | 2026-05-03 | 2026-07-20 | 78 | Open | Done |
| PET-4 | PET | 78 | 1 | 2026-05-04 | 2026-07-21 | 78 | Open | Done |

## The 0 oldest still in the segment (out of 0)

| Key | Project | Age of the current visit (d) | Entry | Cumulative days (previous visits included) | Visits (current one included) | Current status | Origin |
|---|---|---|---|---|---|---|---|

## Time per status of the segment (population of 16 tickets that left)

| Status | Tickets that went through the status | Total (d) | Share of segment time | P50 (d) | P85 (d) |
|---|---|---|---|---|---|
| Ready for Review (Implementation) | 0 | 0 | 0.0% | - | - |
| Review - Ongoing (Impl.) | 0 | 0 | 0.0% | - | - |
| Review - On Hold (Impl.) | 0 | 0 | 0.0% | - | - |
| Ready for Verification | 16 | 16 | 1.3% | 1 | 1 |
| Verification | 0 | 0 | 0.0% | - | - |
| Verification - Ongoing | 16 | 1232 | 98.7% | 77 | 79 |
| Verification - On Hold | 0 | 0 | 0.0% | - | - |

Segment total: 1248 d (sum of the cumulative times). P50 and P85: days spent in the status per ticket, summed over the visits, among the tickets that went through the status.

## Per-status detail of the sampled tickets

| Key | Group | Total (d) | Ready for Review (Implementation) | Review - Ongoing (Impl.) | Review - On Hold (Impl.) | Ready for Verification | Verification | Verification - Ongoing | Verification - On Hold |
|---|---|---|---|---|---|---|---|---|---|
| PET-1 | longest | 81 | - | - | - | 1 | - | 80 | - |
| ETA-1 | longest | 80 | - | - | - | 1 | - | 79 | - |
| LOT-1 | longest | 80 | - | - | - | 1 | - | 79 | - |
| PET-2 | longest | 80 | - | - | - | 1 | - | 79 | - |
| ETA-2 | longest | 79 | - | - | - | 1 | - | 78 | - |
| LOT-2 | longest | 79 | - | - | - | 1 | - | 78 | - |
| PET-3 | drawn near the median | 79 | - | - | - | 1 | - | 78 | - |
| ETA-3 | drawn near the median | 78 | - | - | - | 1 | - | 77 | - |
| LOT-3 | drawn near the median | 78 | - | - | - | 1 | - | 77 | - |
| PET-4 | drawn near the median | 78 | - | - | - | 1 | - | 77 | - |

"-": the ticket did not go through the status. For a ticket still in the segment, the total and the detail include the current visit, up to the computation date.

## Grouped exits of the 6 longest

| Key | Exit of the longest visit | Other tickets that left the segment that day |
|---|---|---|
| PET-1 | 2026-07-21 | 3 |
| ETA-1 | 2026-07-20 | 11 |
| LOT-1 | 2026-07-20 | 11 |
| PET-2 | 2026-07-21 | 3 |
| ETA-2 | 2026-07-20 | 11 |
| LOT-2 | 2026-07-20 | 11 |

Benchmark: over the 2 days when at least one ticket of the population left the segment, P50 8 and P85 11 exits per day, maximum 12 on 2026-07-20.

## Moves from "Ready for Verification" to "Verification - Ongoing" by project

16 moves in the finished visits of the population, 16 tickets concerned. Projects listed: at least 1 moves; 0 project(s) below the threshold (0 moves) not listed.

| Project | Moves | Distinct days | Busiest days kept (20%) | Share of moves on these days | Share expected at random (equal active days) | 95th percentile of the draws (equal active days) | More concentrated than chance at equal active days | Distinct days expected at random | 5th percentile of the distinct days | Ratio observed / expected days | Fewer active days than chance | P50 of the wait before the move (d) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ETA | 6 | 6 | 2 | 33.3% | 33.3% | 33.3% | no | 5.9 | 5.0 | 1.02 | no | 1 |
| LOT | 6 | 6 | 2 | 33.3% | 33.4% | 33.3% | no | 5.9 | 5.0 | 1.02 | no | 1 |
| PET | 4 | 4 | 1 | 25.0% | 26.3% | 50.0% | no | 3.9 | 3.0 | 1.01 | no | 1 |

The wait is the time spent in "Ready for Verification" just before the move. The moves counted are those of finished visits, whatever their date, several per ticket when tickets go back and forth.
Both measures draw the project's moves at random, with replacement, over the 124 working days (Monday to Friday, French public holidays removed, Alsace-Moselle excepted) from 2026-04-06 to 2026-10-04; 1000 draws, seed 42, each draw having the same number of moves as the real data. Concentration at equal active days: each draw keeps its own number of distinct days and the rule of the 20% busiest days (rounded up) is applied to it; "yes" if the observed share is strictly above the 95th percentile of these shares. Because it takes the active days as given, it does not see a project that has only few active days: a project that starts in bursts almost always comes out "yes". Active days: the observed number of distinct days is compared with that of the draws (mean, 5th percentile, observed / expected ratio) without imposing anything on it; "yes" if the observed number is strictly below the 5th percentile of the draws, that is, fewer active days than chance produces. In the population, 6 move(s) fall on a weekend, a public holiday or outside the period: the model does not know them.
````

## --exclude-batch-closures (exit 0)

````
# Sample of the segment "review_verification"

Period: 2026-04-06 to 2026-10-04 (26 full weeks at most), computed on 2026-10-06.

Batch closures discarded (--exclude-batch-closures): 6 tickets that left the segment, 6 moves from "Ready for Verification" to "Verification - Ongoing". Every figure below is computed without them.
Keys and statuses only; nothing is written to disk.

## Statuses of the segment ("segments" setting of flux.yaml)

- Ready for Review (Implementation)
- Review - Ongoing (Impl.)
- Review - On Hold (Impl.)
- Ready for Verification
- Verification
- Verification - Ongoing
- Verification - On Hold

Other segments, by number of statuses: definition (8), ready (1), implementation (6), acceptance (2).

## Population

17 tickets read after discarding, 0 without history in the cache.

Tickets that left the segment during the period: 10; cumulative time P50 78 d, P85 80 d, mean 78.3 d, maximum 81 d.
Visits per ticket: 1 visit 10, 2 visits or more 0.

## The 6 longest (cumulative time)

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| PET-1 | PET | 81 | 1 | 2026-05-01 | 2026-07-21 | 81 | Open | Done |
| ETA-1 | ETA | 80 | 1 | 2026-05-01 | 2026-07-20 | 80 | Open | Done |
| PET-2 | PET | 80 | 1 | 2026-05-02 | 2026-07-21 | 80 | Open | Done |
| ETA-2 | ETA | 79 | 1 | 2026-05-02 | 2026-07-20 | 79 | Open | Done |
| PET-3 | PET | 79 | 1 | 2026-05-03 | 2026-07-21 | 79 | Open | Done |
| ETA-3 | ETA | 78 | 1 | 2026-05-03 | 2026-07-20 | 78 | Open | Done |

## 1 tickets near the median (random draw, seed 42)

Window: from 78.0 to 79.0 d (P40 to P60); 1 candidates.

Warning: only 1 candidate(s) for 4 requested.

| Key | Project | Cumulative days | Visits | Entry (longest visit) | Exit | Days of this visit | Origin | Destination |
|---|---|---|---|---|---|---|---|---|
| PET-4 | PET | 78 | 1 | 2026-05-04 | 2026-07-21 | 78 | Open | Done |

## The 0 oldest still in the segment (out of 0)

| Key | Project | Age of the current visit (d) | Entry | Cumulative days (previous visits included) | Visits (current one included) | Current status | Origin |
|---|---|---|---|---|---|---|---|

## Time per status of the segment (population of 10 tickets that left)

| Status | Tickets that went through the status | Total (d) | Share of segment time | P50 (d) | P85 (d) |
|---|---|---|---|---|---|
| Ready for Review (Implementation) | 0 | 0 | 0.0% | - | - |
| Review - Ongoing (Impl.) | 0 | 0 | 0.0% | - | - |
| Review - On Hold (Impl.) | 0 | 0 | 0.0% | - | - |
| Ready for Verification | 10 | 10 | 1.3% | 1 | 1 |
| Verification | 0 | 0 | 0.0% | - | - |
| Verification - Ongoing | 10 | 773 | 98.7% | 78 | 79 |
| Verification - On Hold | 0 | 0 | 0.0% | - | - |

Segment total: 783 d (sum of the cumulative times). P50 and P85: days spent in the status per ticket, summed over the visits, among the tickets that went through the status.

## Per-status detail of the sampled tickets

| Key | Group | Total (d) | Ready for Review (Implementation) | Review - Ongoing (Impl.) | Review - On Hold (Impl.) | Ready for Verification | Verification | Verification - Ongoing | Verification - On Hold |
|---|---|---|---|---|---|---|---|---|---|
| PET-1 | longest | 81 | - | - | - | 1 | - | 80 | - |
| ETA-1 | longest | 80 | - | - | - | 1 | - | 79 | - |
| PET-2 | longest | 80 | - | - | - | 1 | - | 79 | - |
| ETA-2 | longest | 79 | - | - | - | 1 | - | 78 | - |
| PET-3 | longest | 79 | - | - | - | 1 | - | 78 | - |
| ETA-3 | longest | 78 | - | - | - | 1 | - | 77 | - |
| PET-4 | drawn near the median | 78 | - | - | - | 1 | - | 77 | - |

"-": the ticket did not go through the status. For a ticket still in the segment, the total and the detail include the current visit, up to the computation date.

## Grouped exits of the 6 longest

| Key | Exit of the longest visit | Other tickets that left the segment that day |
|---|---|---|
| PET-1 | 2026-07-21 | 3 |
| ETA-1 | 2026-07-20 | 5 |
| PET-2 | 2026-07-21 | 3 |
| ETA-2 | 2026-07-20 | 5 |
| PET-3 | 2026-07-21 | 3 |
| ETA-3 | 2026-07-20 | 5 |

Benchmark: over the 2 days when at least one ticket of the population left the segment, P50 5 and P85 6 exits per day, maximum 6 on 2026-07-20.

## Moves from "Ready for Verification" to "Verification - Ongoing" by project

10 moves in the finished visits of the population, 10 tickets concerned. Projects listed: at least 1 moves; 0 project(s) below the threshold (0 moves) not listed.

| Project | Moves | Distinct days | Busiest days kept (20%) | Share of moves on these days | Share expected at random (equal active days) | 95th percentile of the draws (equal active days) | More concentrated than chance at equal active days | Distinct days expected at random | 5th percentile of the distinct days | Ratio observed / expected days | Fewer active days than chance | P50 of the wait before the move (d) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ETA | 6 | 6 | 2 | 33.3% | 33.3% | 33.3% | no | 5.9 | 5.0 | 1.02 | no | 1 |
| PET | 4 | 4 | 1 | 25.0% | 26.3% | 50.0% | no | 3.9 | 3.0 | 1.01 | no | 1 |

The wait is the time spent in "Ready for Verification" just before the move. The moves counted are those of finished visits, whatever their date, several per ticket when tickets go back and forth.
Both measures draw the project's moves at random, with replacement, over the 124 working days (Monday to Friday, French public holidays removed, Alsace-Moselle excepted) from 2026-04-06 to 2026-10-04; 1000 draws, seed 42, each draw having the same number of moves as the real data. Concentration at equal active days: each draw keeps its own number of distinct days and the rule of the 20% busiest days (rounded up) is applied to it; "yes" if the observed share is strictly above the 95th percentile of these shares. Because it takes the active days as given, it does not see a project that has only few active days: a project that starts in bursts almost always comes out "yes". Active days: the observed number of distinct days is compared with that of the draws (mean, 5th percentile, observed / expected ratio) without imposing anything on it; "yes" if the observed number is strictly below the 5th percentile of the draws, that is, fewer active days than chance produces. In the population, 4 move(s) fall on a weekend, a public holiday or outside the period: the model does not know them.
````
