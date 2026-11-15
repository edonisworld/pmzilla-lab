// Task 37.1, contract part (mothra-slices D35): the answer types of the four panels of the product-scope dashboard and their pure functions.
import assert from "node:assert/strict";
import { test } from "node:test";
import Value from "typebox/value";

import { cellule } from "../src/cellule.ts";
import type { Cellule } from "../src/cellule.ts";
import { verifierFiltres } from "../src/filtres.ts";
import {
  CODES_PANNEAUX,
  MENTIONS_PANNEAUX,
  PorteeProduitRefusee,
  SchemaPanneauBlockedShare,
  SchemaPanneauCorrectionShare,
  SchemaPanneauDefectsInout,
  SchemaPanneauReduit,
  SchemaPanneauStoriesInout,
  panneauBlockedShare,
  panneauCorrectionShare,
  panneauDefectsInout,
  panneauStoriesInout,
  partDeDebitEnCorrection,
} from "../src/panneaux.ts";
import * as modulePanneaux from "../src/panneaux.ts";
import type { EntreeBloque, EntreeFlux } from "../src/panneaux.ts";
import { reduceToStatistics } from "../src/reduction.ts";

const v = (n: number): Cellule => cellule(n, 5);
const m: Cellule = cellule(null, 5);
// Reading on 2026-11-19: last closed quarter 2026-Q3, the three closed quarters 2026-Q1 to 2026-Q3 (R-20261114-49).
const DATE = "2026-11-19";
function filtres(extra: Record<string, unknown> = {}) {
  const r = verifierFiltres({ from: "2026-Q1", to: "2026-Q3", ...extra }, { today: DATE });
  if (!r.ok) throw new Error("filtres");
  return r;
}
const T = ["2026-Q1", "2026-Q2", "2026-Q3"];
const flux = (g: "story" | "defect", q: string, created: Cellule, done: Cellule): EntreeFlux => ({ quarter: q, group: g, created, done });

test("the truncated-quarter flag is gone: no `flags` field on any point, an answer that carries one fails its schema, no removed name is exported", () => {
  const lignes = T.map((q) => flux("story", q, v(10), v(20)));
  const stories = panneauStoriesInout(lignes, filtres(), DATE, 5);
  assert.equal(stories.points.some((p) => "flags" in p), false);
  assert.equal(Value.Check(SchemaPanneauStoriesInout, { ...stories, points: stories.points.map((p) => ({ ...p, flags: [] })) }), false);
  const part = panneauCorrectionShare(T.flatMap((q) => [flux("story", q, v(10), v(20)), flux("defect", q, v(6), v(7))]), filtres(), DATE, 5);
  assert.equal(part.points.some((p) => "flags" in p), false);
  assert.equal(Value.Check(SchemaPanneauCorrectionShare, { ...part, points: part.points.map((p) => ({ ...p, flags: [] })) }), false);
  const bloque = panneauBlockedShare(T.map((q) => ({ quarter: q, blocked: v(6), blockedN: v(20), share: { state: "value" as const, value: 30 } })), filtres({ team: "t-07" }), DATE, 5);
  assert.equal(bloque.points.some((p) => "flags" in p), false);
  assert.equal(Value.Check(SchemaPanneauBlockedShare, { ...bloque, points: bloque.points.map((p) => ({ ...p, flags: [] })) }), false);
  assert.equal("premierTrimestreRetenu" in modulePanneaux, false);
  assert.equal("CODE_PREMIER_TRIMESTRE_TRONQUE" in modulePanneaux, false);
});

test("a duplicated quarter of a group is a TypeError, never silently overwritten", () => {
  const f = filtres({ from: "2026-Q3", to: "2026-Q3" });
  const deux = [flux("story", "2026-Q3", v(7), v(9)), flux("story", "2026-Q3", v(8), v(9))];
  assert.throws(() => panneauStoriesInout(deux, f, DATE, 5), { name: "TypeError", message: "panneau : trimestre en double" });
  assert.throws(() => panneauCorrectionShare(deux, f, DATE, 5), TypeError);
  const bloques: EntreeBloque[] = [
    { quarter: "2026-Q3", blocked: v(6), blockedN: v(20), share: { state: "value", value: 30 } },
    { quarter: "2026-Q3", blocked: v(7), blockedN: v(20), share: { state: "value", value: 35 } },
  ];
  assert.throws(() => panneauBlockedShare(bloques, filtres({ team: "t-07", from: "2026-Q3", to: "2026-Q3" }), DATE, 5), {
    name: "TypeError",
    message: "panneau : trimestre en double",
  });
  // the same quarter in the two groups is not a duplicate
  assert.doesNotThrow(() => panneauCorrectionShare([flux("story", "2026-Q3", v(7), v(9)), flux("defect", "2026-Q3", v(7), v(9))], f, DATE, 5));
});

test("a quarter that is not a label AAAA-Qn is a TypeError; a valid quarter out of range is ignored", () => {
  const f = filtres({ from: "2026-Q3", to: "2026-Q3" });
  for (const mauvais of ["2026-07-01", "2026-Q5", "2026-q3", "26-Q3", ""]) {
    assert.throws(() => panneauStoriesInout([flux("story", mauvais, v(7), v(9))], f, DATE, 5), TypeError);
    assert.throws(
      () =>
        panneauBlockedShare(
          [{ quarter: mauvais, blocked: v(6), blockedN: v(20), share: { state: "value", value: 30 } }],
          filtres({ team: "t-07", from: "2026-Q3", to: "2026-Q3" }),
          DATE,
          5,
        ),
      TypeError,
    );
  }
  assert.doesNotThrow(() => panneauStoriesInout([flux("story", "2020-Q1", v(7), v(9))], f, DATE, 5));
});

test("the blocked share panel refuses the product scope with the code SCOPE_INVALID (the slice 1 view has no product row)", () => {
  const f = filtres({ from: "2026-Q3", to: "2026-Q3" });
  assert.throws(() => panneauBlockedShare([], f, DATE, 5), (e: unknown) => e instanceof PorteeProduitRefusee && e.code === "SCOPE_INVALID" && e.status === 422);
  assert.doesNotThrow(() => panneauBlockedShare([], filtres({ team: "t-07", from: "2026-Q3", to: "2026-Q3" }), DATE, 5));
});

test("the share in correction is rounded to one decimal", () => {
  assert.deepEqual(partDeDebitEnCorrection(v(10), v(25)), { state: "value", value: 28.6 });
  assert.deepEqual(partDeDebitEnCorrection(v(5), v(15)), { state: "value", value: 25 });
  assert.deepEqual(partDeDebitEnCorrection(v(5), v(1000)), { state: "value", value: 0.5 });
});

test("the four panels are the four routes of the decision Q5 (a)", () => {
  assert.deepEqual([...CODES_PANNEAUX], ["stories-inout", "correction-share", "defects-inout", "blocked-share"]);
});

test("the share in correction is given only when neither term is masked", () => {
  assert.deepEqual(partDeDebitEnCorrection(v(10), v(30)), { state: "value", value: 25 });
  assert.deepEqual(partDeDebitEnCorrection(m, v(30)), { state: "masked", threshold: 5 });
  assert.deepEqual(partDeDebitEnCorrection(v(10), m), { state: "masked", threshold: 5 });
  assert.deepEqual(partDeDebitEnCorrection({ state: "masked", threshold: 8 }, { state: "masked", threshold: 6 }), { state: "masked", threshold: 8 });
});

test("stories panel: points per closed quarter, range total only without a masked quarter", () => {
  const lignes = T.map((q, i) => flux("story", q, v(10 + i), v(20 + i)));
  const r = panneauStoriesInout(lignes, filtres(), DATE, 5);
  assert.equal(r.panel, "stories-inout");
  assert.equal(r.scope, "product");
  assert.deepEqual(r.points.map((p) => p.quarter), T);
  // R-20261114-49, by hand: created 10 + 11 + 12 = 33 and done 20 + 21 + 22 = 63 (before: four quarters, 10 + 11 + 12 + 13 = 46 and 20 + 21 + 22 + 23 = 86)
  assert.deepEqual(r.total, { created: { state: "value", value: 33 }, done: { state: "value", value: 63 } });
  assert.equal(Value.Check(SchemaPanneauStoriesInout, r), true);
  const masquee = panneauStoriesInout(lignes.map((l, i) => (i === 2 ? flux("story", l.quarter, m, l.done) : l)), filtres(), DATE, 5);
  assert.deepEqual(masquee.total.created, { state: "masked", threshold: 5 });
  assert.deepEqual(masquee.total.done, { state: "value", value: 63 });
});

test("a quarter absent from the data is a masked cell, never an estimate; the other group is ignored", () => {
  const r = panneauStoriesInout([flux("story", "2026-Q3", v(7), v(9)), flux("defect", "2026-Q2", v(50), v(50))], filtres({ from: "2026-Q2", to: "2026-Q3" }), DATE, 5);
  assert.deepEqual(r.points[0].created, { state: "masked", threshold: 5 });
  assert.deepEqual(r.points[1].created, { state: "value", value: 7 });
});

test("a team scope on the stories panel is served for that team; the product-level panels serve the product row only", () => {
  const f = filtres({ team: "t-07" });
  assert.equal(panneauStoriesInout([], f, DATE, 5).scope, "team.t-07");
  const d = panneauDefectsInout([], f, DATE, 5);
  assert.equal(d.scope, "product");
  assert.deepEqual(d.mentions, ["indirect_indicator", "product_level"]);
  assert.equal(panneauCorrectionShare([], f, DATE, 5).scope, "product");
});

test("correction share panel: terms from the product row, share masked as soon as a term is masked", () => {
  const lignes = [
    flux("story", "2026-Q2", v(1 * 5), v(30)),
    flux("defect", "2026-Q2", v(6), v(10)),
    flux("story", "2026-Q3", v(40), v(30)),
    flux("defect", "2026-Q3", v(6), m),
  ];
  const r = panneauCorrectionShare(lignes, filtres({ from: "2026-Q2", to: "2026-Q3" }), DATE, 5);
  assert.deepEqual(r.points[0].share, { state: "value", value: 25 });
  assert.deepEqual(r.points[1].share, { state: "masked", threshold: 5 });
  assert.equal(r.hypothesis, "h3");
  assert.equal(Value.Check(SchemaPanneauCorrectionShare, r), true);
});

test("defects panel carries hypothesis 3, indirect indicator and product level", () => {
  const r = panneauDefectsInout([flux("defect", "2026-Q3", v(6), v(7))], filtres({ from: "2026-Q3", to: "2026-Q3" }), DATE, 5);
  assert.equal(r.hypothesis, "h3");
  assert.deepEqual(r.mentions, MENTIONS_PANNEAUX["defects-inout"]);
  assert.equal(Value.Check(SchemaPanneauDefectsInout, r), true);
});

test("blocked share panel always carries both mentions", () => {
  const lignes: EntreeBloque[] = [{ quarter: "2026-Q3", blocked: v(6), blockedN: v(20), share: { state: "value", value: 30 } }];
  const r = panneauBlockedShare(lignes, filtres({ team: "t-07", from: "2026-Q3", to: "2026-Q3" }), DATE, 5);
  assert.equal(r.scope, "team.t-07");
  assert.ok(r.mentions.includes("blocked_share_current_links") && r.mentions.includes("indirect_indicator"));
  assert.equal(Value.Check(SchemaPanneauBlockedShare, r), true);
  assert.equal(Value.Check(SchemaPanneauBlockedShare, { ...r, mentions: ["indirect_indicator"] }), false);
  assert.equal(Value.Check(SchemaPanneauBlockedShare, { ...r, mentions: ["blocked_share_current_links"] }), false);
});

test("no collection is indexed by team and any undeclared field is refused", () => {
  const r = panneauStoriesInout([], filtres(), DATE, 5);
  assert.equal(Value.Check(SchemaPanneauStoriesInout, { ...r, teams: [] }), false);
  assert.equal(Value.Check(SchemaPanneauStoriesInout, { ...r, rank: 1 }), false);
  assert.equal(Object.keys(r).some((k) => k === "teams" || k === "byTeam"), false);
});

test("a nominal answer is the dataset code when the caller sets it", () => {
  const r = panneauStoriesInout([], filtres(), DATE, 5, "synthetic");
  assert.equal(r.dataset, "synthetic");
});

test("on real data every panel goes through reduceToStatistics: no count, no share of a count", () => {
  const lignes = T.flatMap((q) => [flux("story", q, v(10), v(20)), flux("defect", q, v(6), v(7))]);
  const pleines = [
    panneauStoriesInout(lignes, filtres(), DATE, 5, "real"),
    panneauCorrectionShare(lignes, filtres(), DATE, 5, "real"),
    panneauDefectsInout(lignes, filtres(), DATE, 5, "real"),
    panneauBlockedShare([{ quarter: "2026-Q3", blocked: v(6), blockedN: v(20), share: { state: "value", value: 30 } }], filtres({ team: "t-07" }), DATE, 5, "real"),
  ];
  for (const p of pleines) {
    const r = reduceToStatistics(p);
    assert.equal(Value.Check(SchemaPanneauReduit, r), true);
    assert.equal(r.panel, p.panel);
    assert.equal(r.dataset, "real");
    assert.deepEqual(r.limits, ["reduced_form"]);
    assert.equal(JSON.stringify(r).includes('"value"'), false);
    assert.equal("points" in r, false);
    assert.equal("total" in r, false);
    assert.deepEqual(r.mentions, p.mentions);
  }
});
