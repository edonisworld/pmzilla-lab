// SIMULATED ANSWERS of the verdict service, for the sheet screen tests (task 19.3). Every value below is fake: invented words, invented
// figures, invented dates and an invented fingerprint. None comes from a view, from the synthetic dataset or from real data. The
// service itself belongs to group 17 and the routes to group 18; until they are wired, the screen is fed with these answers, which
// follow the shape of the contract of group 17 (names and values as the service returns them).
import type { CorpsFiche, EtatFiche, ReponseFiche } from "../src/api/fiche.ts";

// Render states, not an answer of the server (R-20261031-61, Q114): fiche-simulee-forme.test.ts compares its keys and the shape of its scope to a
// real body built by `corpsDepuisVues`. Known gap of VALUE, not compared: `method.scope.id` is "team A" here, where a real body holds the scope
// code `team.<opaque identifier>` (never a team name). For a server-shaped value in a new test, use reponses-contrat.ts.
export const DONNEES_SIMULEES = true;

// The tests set the state and the date apart from the body; the cast is the only place where a draft could carry a date.
export function ficheSimulee(modifs: Partial<CorpsFiche> & { state?: EtatFiche; publishedOn?: string } = {}): ReponseFiche {
  return {
    id: "fiche-simulee-1",
    state: "draft",
    effect: { text: "Simulated effect: deliveries slowed down over the quarter.", lang: "en" },
    cause: { text: "Simulated cause: work waits before it starts.", lang: "en" },
    verdict: "not_settled",
    verdictReasons: [
      { explanation: "unplanned_work", state: "not_measurable", reason: "defects_without_team" },
      { explanation: "dependencies", state: "not_measurable", reason: "dependencies" },
    ],
    h1Reasons: [],
    h5Reasons: [],
    verdictFindings: [],
    explanations: [
      { name: "unplanned_work", state: "not_measurable", reason: "defects_without_team" },
      { name: "capacity", state: "ruled_out" },
      { name: "dependencies", state: "not_measurable" },
    ],
    unplannedProductShare: { state: "value", value: 31 },
    attachmentSignal: "not_raised",
    attachmentSignalReasons: [],
    attachmentSignalShown: false,
    tasksWithoutTeamShare: { state: "value", value: 22 },
    method: {
      method: "lead_time_against_cycle_time",
      scope: { level: "team", id: "team A" },
      period: { quarters: [{ year: 2026, quarter: 1 }, { year: 2026, quarter: 2 }] },
      thresholds: [
        { code: "h5_floor", value: 5, fixedOn: "2026-10-28", fixedBy: "author_alone" },
        { code: "sample_median_min_items", value: 20, fixedOn: "2026-10-28", fixedBy: "author_alone" },
        { code: "sample_p85_min_items", value: 40, fixedOn: "2026-10-28", fixedBy: "author_alone" },
      ],
      thresholdsFixedOn: "2026-10-28",
      dataDate: "2026-11-02",
      fingerprint: "0000simulated0000",
      coverage: { state: "value", value: 120 },
      maskedCells: [{ measure: "ready@2026-04-01", cell: { state: "masked", threshold: 5 } }],
      insufficientSamples: ["lead_median_days@2026-04-01"],
      excluded: { median: [0], p85: [], throughput: [] },
      limits: ["no_per_team_unplanned_measure", "views_last_four_quarters"],
      authorRole: "agile_lead",
      version: 1,
      hypothesis: "h5",
    },
    ...modifs,
  } as ReponseFiche;
}
