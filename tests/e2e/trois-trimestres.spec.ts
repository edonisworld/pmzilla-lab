// The three closed quarters (change flow-three-closed-quarters, task 2.6, R-20261114-49), on the synthetic dataset of the throwaway database: the dashboard and
// the panels show at most three closed quarters and the grouped row « Last three quarters », no panel carries the truncated-quarter flag, a new sheet of
// hypothesis 1 carries the new note, and a sheet frozen before the change shows its former label and note. Driven like the other specs: through the API
// (Playwright request) and the page; nothing in this file starts a server.
// The sheet frozen before the change is played at the boundary of the browser: the answer of the sheet route is read, its window limit code is turned into the
// former one (`views_last_four_quarters`, what a sheet frozen before the change carries) and given to the page; that the server itself keeps such a sheet,
// content and fingerprint, is the server database test of task 2.5 (mothra/server/test/db/fiches-stockage.test.ts).
import { expect, test } from "../../mothra/node_modules/@playwright/test";
import type { APIRequestContext } from "../../mothra/node_modules/@playwright/test";

const BASE = process.env.MOTHRA_E2E_URL ?? "";
const TRIMESTRE = /^[0-9]{4}-Q[1-4]$/;
const AUTEUR = "author-synth";
const EN_TETE = "x-mothra-user";
// The thresholds a sheet of hypothesis 1 reads (copy of `codesRequis`, as in fiche-parcours.spec.ts: a gap makes the creation answer 409 THRESHOLDS_NOT_SET).
const SEUILS_H1: Record<string, number> = { h1_lower: 1.5, h1_upper: 3, sample_median_min_items: 5, sample_p85_min_items: 20 };

interface Tableau {
  dataDate: string;
  product: Array<{ quarter: string }>;
  teams: Array<{ teamId: string; points: Array<{ quarter: string }> }>;
}

async function tableau(request: APIRequestContext): Promise<Tableau> {
  const reponse = await request.get(`${BASE}/api/dashboards/lead_cycle`);
  expect(reponse.status()).toBe(200);
  return (await reponse.json()) as Tableau;
}

test.describe("three closed quarters", () => {
  test("the dashboard holds at most three closed quarters and a grouped row, and no panel carries a flag", async ({ request }) => {
    const corps = await tableau(request);
    expect(corps.teams.length).toBeGreaterThan(0);
    const trimestres = new Set([...corps.product, ...corps.teams.flatMap((e) => e.points)].map((p) => p.quarter).filter((q) => TRIMESTRE.test(q)));
    expect(trimestres.size).toBeGreaterThan(0);
    expect(trimestres.size).toBeLessThanOrEqual(3);
    for (const equipe of corps.teams) {
      expect(equipe.points.filter((p) => TRIMESTRE.test(p.quarter)).length).toBeLessThanOrEqual(3);
    }
    const plage = new URLSearchParams([["from", [...trimestres].sort()[0]], ["to", [...trimestres].sort().reverse()[0]]]).toString();
    for (const panneau of ["stories-inout", "correction-share", "defects-inout"]) {
      const reponse = await request.get(`${BASE}/api/panels/${panneau}?${plage}`);
      expect(reponse.status(), panneau).toBe(200);
      const texte = await reponse.text();
      expect(texte, panneau).not.toMatch(/"flags"|first_quarter_truncated/);
    }
    // A range of four quarters is refused: the fourth closed quarter is out of the window.
    const quatre = new URLSearchParams([["from", "2000-Q1"], ["to", [...trimestres].sort().reverse()[0]]]).toString();
    const refus = await request.get(`${BASE}/api/panels/stories-inout?${quatre}`);
    expect(refus.status()).toBe(422);
    expect(await refus.json()).toEqual({ error: "RANGE_INVALID" });
  });

  test("the dashboard names its grouped row « Last three quarters », never « Pooled year », and no truncated-quarter mention", async ({ page }) => {
    const reponse = await page.goto(`${BASE}/#/tableau`);
    expect(reponse?.status()).toBe(200);
    await expect(page.getByRole("heading", { name: "Lead time against cycle time" })).toBeVisible();
    const lead = page.getByRole("table").filter({ has: page.getByRole("columnheader", { name: "Lead time (median, days)" }) });
    await expect(lead).toBeVisible();
    await expect(lead.getByText("Last three quarters").first()).toBeVisible();
    await expect(page.getByText("Pooled year")).toHaveCount(0);
    await expect(page.getByText(/truncated/i)).toHaveCount(0);
  });

  test("a new sheet of hypothesis 1 shows the note of the last three quarters; a sheet frozen before the change shows its former note", async ({ page, request }) => {
    const lu = await request.get(`${BASE}/api/thresholds`);
    expect(lu.status()).toBe(200);
    const presents = new Set(((await lu.json()) as { thresholds: Array<{ code: string }> }).thresholds.map((s) => s.code));
    for (const [code, value] of Object.entries(SEUILS_H1).filter(([code]) => !presents.has(code))) {
      const pose = await request.post(`${BASE}/api/thresholds`, { headers: { [EN_TETE]: AUTEUR }, data: { code, value, setOn: "2026-10-27" } });
      expect(pose.status(), code).toBe(200);
    }
    const corps = await tableau(request);
    const creation = await request.post(`${BASE}/api/sheets`, {
      headers: { [EN_TETE]: AUTEUR },
      data: { chart: "lead_cycle_h1", scope: `team.${corps.teams[0].teamId}`, dataDate: corps.dataDate, managementQuestion: "predictability" },
    });
    expect(creation.status()).toBe(200);
    const { id } = (await creation.json()) as { id: string };
    const adresse = `${BASE}/#/conviction/lead_cycle_h1/${id}`;
    const note = (marque: string) => page.locator(`[data-note="${marque}"]`);

    // A new sheet: its window limit code is the new one, its note is the new one.
    await page.goto(adresse);
    await expect(note("last-three-quarters")).toBeVisible();
    await expect(note("last-three-quarters")).toHaveText("The last three quarters leave out the items created more than one year before their commitment.");
    await expect(note("pooled-year")).toHaveCount(0);

    // The same sheet as a sheet frozen before the change would be served: the former window limit code, so the former note.
    await page.route(`**/api/sheets/${id}`, async (route) => {
      const origine = await route.fetch();
      const figee = (await origine.json()) as { method: { limits: string[] } };
      figee.method.limits = figee.method.limits.map((l) => (l === "views_last_three_closed_quarters" ? "views_last_four_quarters" : l));
      await route.fulfill({ response: origine, json: figee });
    });
    await page.reload();      // the page reads the sheet again (nothing kept from the first reading), now through the route above
    await expect(note("pooled-year")).toBeVisible();
    await expect(note("pooled-year")).toHaveText("The pooled year leaves out the items created more than one year before their commitment.");
    await expect(note("last-three-quarters")).toHaveCount(0);
  });
});
