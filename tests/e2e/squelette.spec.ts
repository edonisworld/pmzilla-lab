// Skeleton path of slice 0 (mothra-slices D12, task 8.2), on the synthetic dataset of the throwaway database: the page is served by the Mothra
// server at the address of MOTHRA_E2E_URL (the built bundle and the API from one address), and shows the status by team table with at least
// one masked cell, labelled in the default language (English). The playwright package is imported by its path: this folder has no
// node_modules of its own, the package lives in mothra/node_modules (installed by npm ci).
import { expect, test } from "../../mothra/node_modules/@playwright/test";

const BASE = process.env.MOTHRA_E2E_URL ?? "";

// R-20261101-40 (Q156): the home no longer holds the status by team section; the path to the masked cell goes through the table of the
// dashboard, reached from the side navigation, and the home is checked by its title.
test("the dashboard shows its table with a masked cell, reached from the home", async ({ page }) => {
  const reponse = await page.goto(`${BASE}/`);
  expect(reponse?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "What the data say about our convictions" })).toBeVisible();
  // The mark of the side column (R-20261101-40): the shipped logo, named by its catalogue text, loaded from the served bundle.
  const logo = page.getByRole("complementary").getByRole("link", { name: "Mothra logo" }).getByRole("img", { name: "Mothra logo" });
  await expect(logo).toBeVisible();
  expect(await logo.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
  // The entry of the side navigation is named "Dashboard" (`nav.dashboard`, R-20261101-68 and -80); the locator follows it (R-20261101-40).
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Dashboard" }).click();
  await expect(page.getByRole("heading", { name: "Lead time against cycle time" })).toBeVisible();
  // The screen holds several tables (the panels of the product scope have theirs): the one meant is the lead time / cycle time table,
  // told apart by its column header.
  const tableau = page.getByRole("table").filter({ has: page.getByRole("columnheader", { name: "Lead time (median, days)" }) });
  await expect(tableau).toBeVisible();
  // The synthetic dataset holds witness cells of 1 to 4 tickets: the view masks them, the front shows the label of the catalogue.
  const masquees = tableau.locator('td[data-state="masked"]');
  await expect(masquees.first()).toHaveText("masked");
  expect(await masquees.count()).toBeGreaterThan(0);
  // A cell of at least five tickets is shown as a value, never as the masked label.
  await expect(tableau.locator('td[data-state="value"]').first()).not.toHaveText("masked");
});

test("a route of the front without an extension is served by the fallback to index.html", async ({ page }) => {
  const reponse = await page.goto(`${BASE}/sheets/12`);
  expect(reponse?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "What the data say about our convictions" })).toBeVisible();
});

test("an absent file with an extension answers the JSON 404, never index.html", async ({ request }) => {
  const reponse = await request.get(`${BASE}/assets/absent.js`);
  expect(reponse.status()).toBe(404);
  expect(await reponse.json()).toEqual({ error: "NOT_FOUND" });
});

test("the API answers from the same address and carries the security headers", async ({ request }) => {
  const reponse = await request.get(`${BASE}/api/views/v_team_status`);
  expect(reponse.status()).toBe(200);
  expect(reponse.headers()["x-content-type-options"]).toBe("nosniff");
  expect(reponse.headers()["access-control-allow-origin"]).toBeUndefined();
});
