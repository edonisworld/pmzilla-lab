// Path of an argument sheet, from the draft to the publication, for both sheet kinds (mothra-slices task 20.1, R-20261102-66 (1)), on the
// synthetic dataset of the throwaway database and its two synthetic users (tests/mothra_donnees/jeu_synthetique.py): `author-synth` (role
// author) and `reviewer-synth` (role reviewer). Driven through the API (Playwright request) because the front ships the page of the sheet
// for hypothesis 1 only. The dataset of this pass holds no transition, so no team has a cycle time: both kinds compute the verdict
// `insufficient_sample` (hypothesis 1: median ratio masked; hypothesis 5: no reference quarter). That is the verdict expected here; the
// other verdicts need the dataset of slice 1 (tests/mothra_donnees/tranche1.py) and are played by the server tests.
// The thresholds the sheets read are posted through the route when the history lacks them (the pass inserts the two sample ones only); the
// codes are those of `codesRequis` (mothra/contract/src/listes-fiche.ts) and the values those of the server tests (fiches-calcul.test.ts).
import { expect, test } from "../../mothra/node_modules/@playwright/test";
import type { APIRequestContext } from "../../mothra/node_modules/@playwright/test";

const BASE = process.env.MOTHRA_E2E_URL ?? "";
// Source: UTILISATEURS_SYNTHETIQUES in tests/mothra_donnees/jeu_synthetique.py. A gap is detected at the first write: the server answers 403
// UNKNOWN_USER for an identifier the loader does not insert, and this spec fails.
const AUTEUR = "author-synth";
const RELECTEUR = "reviewer-synth";
const EN_TETE = "x-mothra-user";

const SEUILS: Record<string, number> = {
  h5_band: 0.2,
  h5_double_band: 0.4,
  h5_run_rises: 2,
  h5_run_min_cumulative_rise: 0.1,
  h5_floor: 0.8,
  h5_low_floor: 0.6,
  attachment_threshold_points: 10,
  h1_lower: 1.5,
  h1_upper: 3,
  sample_median_min_items: 5,
  sample_p85_min_items: 20,
};
// Copy of `codesRequis` (mothra/contract/src/listes-fiche.ts), not imported: this folder has no package of its own and a runtime import of an
// ES-module source of the contract under Playwright cannot be checked without running it. A gap is detected by the pass: a code added to the
// contract and absent here makes the creation answer 409 THRESHOLDS_NOT_SET, and this spec fails.
const CODES_REQUIS: Record<string, string[]> = {
  lead_cycle_h5: ["h5_band", "h5_double_band", "h5_run_rises", "h5_run_min_cumulative_rise", "h5_floor", "h5_low_floor", "attachment_threshold_points", "sample_median_min_items", "sample_p85_min_items"],
  lead_cycle_h1: ["h1_lower", "h1_upper", "sample_median_min_items", "sample_p85_min_items"],
};

const autorise = (utilisateur: string) => ({ [EN_TETE]: utilisateur });

// A team of the dashboard (its opaque identifier) and the data date, as the dashboard answers them.
async function equipeEtDate(request: APIRequestContext): Promise<{ scope: string; dataDate: string }> {
  const reponse = await request.get(`${BASE}/api/dashboards/lead_cycle`);
  expect(reponse.status()).toBe(200);
  const corps = (await reponse.json()) as { dataDate: string; teams: Array<{ teamId: string }> };
  expect(corps.teams.length).toBeGreaterThan(0);
  return { scope: `team.${corps.teams[0].teamId}`, dataDate: corps.dataDate };
}

// The thresholds a kind reads: the missing codes only are posted, by the author, dated before the creation of any sheet.
async function poserSeuils(request: APIRequestContext, graphique: string): Promise<void> {
  const lu = await request.get(`${BASE}/api/thresholds`);
  expect(lu.status()).toBe(200);
  const presents = new Set(((await lu.json()) as { thresholds: Array<{ code: string }> }).thresholds.map((s) => s.code));
  for (const code of CODES_REQUIS[graphique].filter((c) => !presents.has(c))) {
    const pose = await request.post(`${BASE}/api/thresholds`, { headers: autorise(AUTEUR), data: { code, value: SEUILS[code], setOn: "2026-10-27" } });
    expect(pose.status(), code).toBe(200);
  }
}

test.describe("sheet path: draft, review, publication", () => {
  test("an unknown user is refused", async ({ request }) => {
    const { scope, dataDate } = await equipeEtDate(request);
    const reponse = await request.post(`${BASE}/api/sheets`, { headers: autorise("nobody-synth"), data: { chart: "lead_cycle_h1", scope, dataDate } });
    expect(reponse.status()).toBe(403);
    expect(await reponse.json()).toEqual({ error: "UNKNOWN_USER" });
  });

  for (const graphique of ["lead_cycle_h1", "lead_cycle_h5"]) {
    test(`${graphique}: the author drafts, the other user reviews, the author publishes; the verdict is insufficient_sample`, async ({ request }) => {
      await poserSeuils(request, graphique);
      const { scope, dataDate } = await equipeEtDate(request);

      // Draft by the author, with the question, the effect and the cause.
      const creation = await request.post(`${BASE}/api/sheets`, {
        headers: autorise(AUTEUR),
        data: {
          chart: graphique,
          scope,
          dataDate,
          managementQuestion: "predictability",
          effect: { text: "Work waits long before it starts.", lang: "en" },
          cause: { text: "The ready queue is rarely sorted.", lang: "en" },
        },
      });
      expect(creation.status()).toBe(200);
      const brouillon = (await creation.json()) as { id: string; state: string };
      expect(brouillon.state).toBe("draft");
      const fiche = `${BASE}/api/sheets/${brouillon.id}`;

      // The draft is read with its computed verdict, never typed.
      const lecture = await request.get(fiche);
      expect(lecture.status()).toBe(200);
      const lue = (await lecture.json()) as { state: string; verdict: string };
      expect(lue.state).toBe("draft");
      expect(lue.verdict).toBe("insufficient_sample");

      // The author does not review their own sheet; the reviewer does not publish it (draft or reviewed).
      const autoRelecture = await request.post(`${fiche}/review`, { headers: autorise(AUTEUR) });
      expect(autoRelecture.status()).toBe(403);
      expect(await autoRelecture.json()).toEqual({ error: "SELF_REVIEW_REFUSED" });
      const publicationAvantRelecture = await request.post(`${fiche}/publish`, { headers: autorise(RELECTEUR) });
      expect(publicationAvantRelecture.status()).toBe(403);
      expect(await publicationAvantRelecture.json()).toEqual({ error: "NOT_AUTHOR" });

      // The author cannot publish a sheet that is not reviewed.
      const nonRelue = await request.post(`${fiche}/publish`, { headers: autorise(AUTEUR) });
      expect(nonRelue.status()).toBe(409);
      expect(await nonRelue.json()).toEqual({ error: "NOT_REVIEWED" });

      // Review by the other user.
      const relecture = await request.post(`${fiche}/review`, { headers: autorise(RELECTEUR) });
      expect(relecture.status()).toBe(200);
      const relue = (await relecture.json()) as { state: string; verdict: string };
      expect(relue.state).toBe("reviewed");
      expect(relue.verdict).toBe("insufficient_sample");

      // The reviewer does not publish; the author does.
      const refus = await request.post(`${fiche}/publish`, { headers: autorise(RELECTEUR) });
      expect(refus.status()).toBe(403);
      expect(await refus.json()).toEqual({ error: "NOT_AUTHOR" });
      const publication = await request.post(`${fiche}/publish`, { headers: autorise(AUTEUR) });
      expect(publication.status()).toBe(200);
      const publiee = (await publication.json()) as { state: string; verdict: string; publishedOn?: string };
      expect(publiee.state).toBe("published");
      expect(publiee.verdict).toBe("insufficient_sample");
      expect(publiee.publishedOn).toBeDefined();

      // The published version is frozen: read again it says the same, and a second publication is refused.
      const relue2 = await request.get(fiche);
      expect(relue2.status()).toBe(200);
      const figee = (await relue2.json()) as { state: string; verdict: string };
      expect(figee.state).toBe("published");
      expect(figee.verdict).toBe("insufficient_sample");
      const encore = await request.post(`${fiche}/publish`, { headers: autorise(AUTEUR) });
      expect(encore.status()).toBe(409);
      expect(await encore.json()).toEqual({ error: "VERSION_FROZEN" });
    });
  }
});
