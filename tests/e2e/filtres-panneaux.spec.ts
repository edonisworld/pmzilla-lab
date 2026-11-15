// Filter bar and panels of the second screen (mothra-slices task 42.3, design D35), on the synthetic dataset of the throwaway database:
// the filters kept in the address with one team, an address without a team or with several, the whole product and a multi-team scope
// answered 422 SCOPE_INVALID by the panel routes, and one panel per hypothesis (task 37.2). The page "preparation of a cycle" is NOT covered
// here: it is out of slice 1 (R-20261102-64 (1)); its spec (tests/e2e/cycle-preparation.spec.ts) is resumed after 2026-11-26.
// Teams and quarters are read from the dashboard's own answer (opaque identifiers, closed quarters aligned on the loading instant), never
// written here. The bar has no product option (R-20261031-61, Q110 a): the whole product is reached through the routes, not through the bar.
// Run: the same pass as the other specs (bash tools/dbtest.sh --e2e, or the e2e phase of the local CI); nothing in this file starts a server.
import { expect, test } from "../../mothra/node_modules/@playwright/test";
import type { APIRequestContext, Page } from "../../mothra/node_modules/@playwright/test";

const BASE = process.env.MOTHRA_E2E_URL ?? "";
const TRIMESTRE = /^[0-9]{4}-Q[1-4]$/;

// The panels of the screen with the hypothesis and the mentions the contract fixes (codes-panneaux.ts), and the label of the hypothesis in
// the English catalogue (en.json, `tableau.hypothesis.*`): a gap between the contract and the page is detected here.
const PANNEAUX = [
  { code: "stories-inout", titre: "User stories created against done", hypothese: "h1_second_half", libelle: "Serves the question: inflow against outflow", mentions: ["indirect_indicator"], portee: "team" },
  { code: "correction-share", titre: "Share of throughput in correction", hypothese: "h3", libelle: "Serves the question: quality per version", mentions: ["indirect_indicator", "product_level"], portee: "product" },
  { code: "defects-inout", titre: "Defects created against resolved", hypothese: "h3", libelle: "Serves the question: quality per version", mentions: ["indirect_indicator", "product_level"], portee: "product" },
  { code: "blocked-share", titre: "Share of done items blocked by another team", hypothese: "dependencies_explanation", libelle: "Competing explanation: dependencies", mentions: ["indirect_indicator", "blocked_share_current_links"], portee: "team" },
] as const;

async function equipesEtTrimestres(request: APIRequestContext): Promise<{ equipes: string[]; trimestres: string[] }> {
  const reponse = await request.get(`${BASE}/api/dashboards/lead_cycle`);
  expect(reponse.status()).toBe(200);
  const corps = (await reponse.json()) as { product: Array<{ quarter: string }>; teams: Array<{ teamId: string; points: Array<{ quarter: string }> }> };
  const equipes = corps.teams.map((e) => e.teamId).sort((a, b) => a.localeCompare(b));
  expect(equipes.length).toBeGreaterThan(0);
  const etiquettes = [...corps.product, ...corps.teams.flatMap((e) => e.points)].map((p) => p.quarter).filter((q) => TRIMESTRE.test(q));
  const trimestres = [...new Set(etiquettes)].sort();
  expect(trimestres.length).toBeGreaterThan(0);
  return { equipes, trimestres };
}

const requete = (params: Array<[string, string]>): string => new URLSearchParams(params).toString();

async function ouvrir(page: Page, adresse: string): Promise<void> {
  const reponse = await page.goto(`${BASE}/${adresse}`);
  expect(reponse?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Lead time against cycle time" })).toBeVisible();
  await expect(page.locator('select[name="team"]')).toBeVisible();
}

test.describe("filter bar kept in the address", () => {
  test("one team in the address is shown in the bar, survives a reload and follows a change of team", async ({ page, request }) => {
    const { equipes, trimestres } = await equipesEtTrimestres(request);
    const premiere = trimestres[0];
    const derniere = trimestres[trimestres.length - 1];
    const equipe = equipes[equipes.length - 1];
    await ouvrir(page, `#/tableau?${requete([["team", equipe], ["from", premiere], ["to", derniere]])}`);
    await expect(page.locator('select[name="team"]')).toHaveValue(equipe);
    await expect(page.locator('select[name="from"]')).toHaveValue(premiere);
    await expect(page.locator('select[name="to"]')).toHaveValue(derniere);
    // The address is the screen's memory: a reload gives the same filters.
    await page.reload();
    await expect(page.locator('select[name="team"]')).toHaveValue(equipe);
    if (equipes.length > 1) {
      // A change of team is written back to the address (team, from and to), and survives a reload.
      const autre = equipes[0];
      await page.locator('select[name="team"]').selectOption(autre);
      await expect(page).toHaveURL(new RegExp(`#/tableau\\?.*team=${autre}`));
      await page.reload();
      await expect(page.locator('select[name="team"]')).toHaveValue(autre);
    }
  });

  test("an address without a team falls to the first team in the neutral order; the bar offers no product option", async ({ page, request }) => {
    const { equipes } = await equipesEtTrimestres(request);
    await ouvrir(page, "#/tableau");
    await expect(page.locator('select[name="team"]')).toHaveValue(equipes[0]);
    const valeurs = await page.locator('select[name="team"] option').evaluateAll((options) => options.map((o) => (o as HTMLOptionElement).value));
    // The bar lists the teams by identifier, alphabetical order, each once, and no empty (product) value.
    expect(valeurs).toEqual(equipes);
    expect(valeurs).not.toContain("");
  });

  test("an address that holds several teams is not read as a list: the bar shows one team", async ({ page, request }) => {
    const { equipes } = await equipesEtTrimestres(request);
    await ouvrir(page, `#/tableau?${requete([["team", equipes[equipes.length - 1]], ["team", equipes[0]]])}`);
    await expect(page.locator('select[name="team"]')).toHaveValue(equipes[0]);
    await expect(page.locator('select[name="team"]')).not.toHaveAttribute("multiple", /.*/);
  });

  test("a team name in the address is not an identifier: it is dropped", async ({ page, request }) => {
    const { equipes } = await equipesEtTrimestres(request);
    await ouvrir(page, "#/tableau?team=Not%20An%20Identifier");
    await expect(page.locator('select[name="team"]')).toHaveValue(equipes[0]);
  });
});

test.describe("panels: one per hypothesis", () => {
  test("with a team chosen, the four panels name their hypothesis, carry their mentions and the synthetic notice", async ({ page, request }) => {
    const { equipes, trimestres } = await equipesEtTrimestres(request);
    await ouvrir(page, `#/tableau?${requete([["team", equipes[0]], ["from", trimestres[0]], ["to", trimestres[trimestres.length - 1]]])}`);
    for (const panneau of PANNEAUX) {
      const section = page.locator(`section.panneau[data-panel="${panneau.code}"]`);
      await expect(section.getByRole("heading", { name: panneau.titre })).toBeVisible();
      // The hypothesis line only exists once the panel is read (an error or a missing mention shows no such line).
      const hypothese = section.locator("[data-hypothesis]");
      await expect(hypothese).toHaveAttribute("data-hypothesis", panneau.hypothese);
      await expect(hypothese).toHaveText(panneau.libelle);
      const mentions = await section.locator("[data-mention]").evaluateAll((noeuds) => noeuds.map((n) => n.getAttribute("data-mention")));
      expect(mentions).toEqual([...panneau.mentions]);
      await expect(section.locator('[data-jeu="synthetic"]')).toBeVisible();
      // A count panel is a table, the chart's equivalent; masked cells are shown as the catalogue label, never a number.
      await expect(section.getByRole("table")).toBeVisible();
    }
    // The panels of hypothesis 3 are product level: asked with a team, they say they are shown for the product.
    for (const panneau of PANNEAUX) {
      const signal = page.locator(`section.panneau[data-panel="${panneau.code}"] [data-signal="served_scope_differs"]`);
      if (panneau.portee === "product") await expect(signal).toBeVisible();
      else await expect(signal).toHaveCount(0);
    }
    // With a team chosen the screen does not ask the team to be chosen.
    await expect(page.locator('[data-note="team-required"]')).toHaveCount(0);
  });

  test("the panels follow a change of team and keep the same four hypotheses", async ({ page, request }) => {
    const { equipes } = await equipesEtTrimestres(request);
    test.skip(equipes.length < 2, "the dataset holds a single team");
    await ouvrir(page, "#/tableau");
    await page.locator('select[name="team"]').selectOption(equipes[equipes.length - 1]);
    const codes = await page.locator("section.panneau").evaluateAll((noeuds) => noeuds.map((n) => n.getAttribute("data-panel")));
    expect(codes).toEqual(PANNEAUX.map((p) => p.code));
  });
});

test.describe("panel routes: the whole product and the refused scopes", () => {
  test("the whole product (no team) is served by the three panels that have a product level", async ({ request }) => {
    const { trimestres } = await equipesEtTrimestres(request);
    const plage = requete([["from", trimestres[0]], ["to", trimestres[trimestres.length - 1]]]);
    for (const panneau of PANNEAUX.filter((p) => p.code !== "blocked-share")) {
      const reponse = await request.get(`${BASE}/api/panels/${panneau.code}?${plage}`);
      expect(reponse.status(), panneau.code).toBe(200);
      const corps = (await reponse.json()) as { panel: string; scope: string; hypothesis: string; mentions: string[]; dataset?: string };
      expect(corps.panel).toBe(panneau.code);
      expect(corps.scope).toBe("product");
      expect(corps.hypothesis).toBe(panneau.hypothese);
      expect(corps.mentions).toEqual([...panneau.mentions]);
      expect(corps.dataset).toBe("synthetic");
    }
  });

  test("the blocked share has no product level: the whole product is answered SCOPE_INVALID", async ({ request }) => {
    const { trimestres } = await equipesEtTrimestres(request);
    const reponse = await request.get(`${BASE}/api/panels/blocked-share?${requete([["from", trimestres[0]], ["to", trimestres[trimestres.length - 1]]])}`);
    expect(reponse.status()).toBe(422);
    expect(await reponse.json()).toEqual({ error: "SCOPE_INVALID" });
  });

  test("an address with several teams is answered SCOPE_INVALID by every panel route", async ({ request }) => {
    const { equipes, trimestres } = await equipesEtTrimestres(request);
    const deux = equipes.length > 1 ? [equipes[0], equipes[1]] : [equipes[0], "other-synth"];
    const plage: Array<[string, string]> = [["from", trimestres[0]], ["to", trimestres[trimestres.length - 1]]];
    for (const panneau of PANNEAUX) {
      const reponse = await request.get(`${BASE}/api/panels/${panneau.code}?${requete([["team", deux[0]], ["team", deux[1]], ...plage])}`);
      expect(reponse.status(), panneau.code).toBe(422);
      expect(await reponse.json(), panneau.code).toEqual({ error: "SCOPE_INVALID" });
    }
  });

  test("a team name, not an identifier, is answered SCOPE_INVALID, and the scope is checked before the range", async ({ request }) => {
    const { trimestres } = await equipesEtTrimestres(request);
    const plage: Array<[string, string]> = [["from", trimestres[0]], ["to", trimestres[trimestres.length - 1]]];
    const nom = await request.get(`${BASE}/api/panels/stories-inout?${requete([["team", "Not An Identifier"], ...plage])}`);
    expect(nom.status()).toBe(422);
    expect(await nom.json()).toEqual({ error: "SCOPE_INVALID" });
    const inverse = await request.get(`${BASE}/api/panels/stories-inout?${requete([["team", "Not An Identifier"], ["from", trimestres[trimestres.length - 1]], ["to", "2000-Q1"]])}`);
    expect(inverse.status()).toBe(422);
    expect(await inverse.json()).toEqual({ error: "SCOPE_INVALID" });
  });

  test("a bad range is answered RANGE_INVALID; a query outside the schema is answered 400 INVALID_REQUEST", async ({ request }) => {
    const { equipes, trimestres } = await equipesEtTrimestres(request);
    const debut = trimestres[0];
    const fin = trimestres[trimestres.length - 1];
    const inverse = await request.get(`${BASE}/api/panels/stories-inout?${requete([["from", fin], ["to", "2000-Q1"]])}`);
    expect(inverse.status()).toBe(422);
    expect(await inverse.json()).toEqual({ error: "RANGE_INVALID" });
    for (const hors of [
      requete([["from", debut]]),
      requete([["to", fin]]),
      requete([["team", equipes[0]]]),
      requete([["from", debut], ["to", fin], ["sort", "asc"]]),
    ]) {
      const reponse = await request.get(`${BASE}/api/panels/stories-inout?${hors}`);
      expect(reponse.status(), hors).toBe(400);
      expect(await reponse.json(), hors).toEqual({ error: "INVALID_REQUEST" });
    }
  });
});
