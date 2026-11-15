// Tasks 31.3 and 37.2 (mothra-slices D35): the filter bar of the second screen and the panels of the product-scope dashboard.
// The bar: one team (single choice), neutral order, opaque identifier shown by default, no colour per team, no side-by-side view, no rank;
// the filters kept in the address; closed quarters only. The panels: each names its hypothesis, carries its mentions, never shows a time per
// segment, the blocked share only when a team is chosen, a served scope different from the requested one is signalled by a catalogue label.
// The server is another package: it is simulated here by fake answers and a fake fetch. Nothing is computed by the front (static test).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { identifiantEquipe, scopeFiche } from "@mothra/contract/equipe";
import { CODES_PANNEAUX, HYPOTHESES_PANNEAUX, MENTIONS_PANNEAUX } from "@mothra/contract/listes-fiche";
import { servirTableau, tableauLeadCycle } from "@mothra/contract";
import type { PanneauBlockedShare, PanneauCorrectionShare, PanneauDefectsInout, PanneauReduit, PanneauStoriesInout, ReponseLeadCycle } from "@mothra/contract";

import { Application, ecranDuHash } from "../src/Application.ts";
import { lirePanneauHttp } from "../src/api/http.ts";
import { dansPlage, ecrireFiltresAdresse, filtrerParPlage, lireFiltresAdresse, trimestresDisponibles } from "../src/api/filtres.ts";
import { optionsLeadCycle } from "../src/api/leadCycle.ts";
import { optionsPanneau, porteeDemandee, porteeServieDiffere, RefusPanneau } from "../src/api/panneaux.ts";
import { BarreFiltres } from "../src/composants/BarreFiltres.ts";
import { panneauxAffiches, VuePanneau } from "../src/composants/PanneauxProduit.ts";
import { catalogues } from "../src/i18n/langue.ts";
import { ContenuTableau } from "../src/pages/PageTableau.ts";
import { SOURCE_PANNEAUX_SIMULEE } from "../src/simule/panneaux.ts";
import { lireLeadCycleSimule, SOURCE_SIMULEE } from "../src/simule/leadCycle.ts";
import { analyser, derivations, sources, textesVisibles, classesDeCss } from "./statique.ts";
import { rendre, texte as texteDuMarquage } from "./rendu.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const en = catalogues.en;
const fr = catalogues.fr;
const texte = (html: string): string => texteDuMarquage(html).replaceAll("&#x27;", "'");

const A = identifiantEquipe("team-a");
const B = identifiantEquipe("team-b");
const C = identifiantEquipe("team-c");
const TRIMESTRES = ["2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3"];
const val = (v: number) => ({ state: "value" as const, value: v });
const masque = (seuil = 5) => ({ state: "masked" as const, threshold: seuil });

// ---- the address -----------------------------------------------------------------------------------------------------------------

test("the filters are read from the address and written back, team by its opaque identifier", () => {
  const hash = `#/tableau?team=${A}&from=2026-Q1&to=2026-Q3`;
  assert.deepEqual(lireFiltresAdresse(hash), { team: A, from: "2026-Q1", to: "2026-Q3" });
  assert.equal(ecrireFiltresAdresse({ team: A, from: "2026-Q1", to: "2026-Q3" }), hash);
  assert.equal(ecrireFiltresAdresse({ team: undefined, from: undefined, to: undefined }), "#/tableau");
  assert.deepEqual(lireFiltresAdresse("#/tableau"), { team: undefined, from: undefined, to: undefined });
});

test("anything that is not an identifier or a quarter is dropped from the address, a team name included", () => {
  assert.equal(lireFiltresAdresse("#/tableau?team=Team%20A").team, undefined);
  assert.equal(lireFiltresAdresse(`#/tableau?team=${A}&team=${B}`).team, undefined);
  assert.equal(lireFiltresAdresse("#/tableau?from=2026-13").from, undefined);
  assert.equal(lireFiltresAdresse("#/tableau?from=2026-Q5").from, undefined);
  assert.equal(lireFiltresAdresse("#/tableau?sort=asc&rank=1").team, undefined);
  assert.equal(ecrireFiltresAdresse({ team: "Team A", from: "bad", to: undefined }), "#/tableau");
});

test("the screen is chosen from the address whatever the filters it holds", () => {
  assert.equal(ecranDuHash("#/tableau"), "tableau");
  assert.equal(ecranDuHash(`#/tableau?team=${A}&from=2026-Q1`), "tableau");
  assert.equal(ecranDuHash("#/autre?x=1"), "squelette");
});

test("a range is the quarters of the answer between the two bounds, whole quarters only", () => {
  assert.equal(dansPlage("2026-Q1", "2026-Q1", "2026-Q2"), true);
  assert.equal(dansPlage("2026-Q3", "2026-Q1", "2026-Q2"), false);
  assert.equal(dansPlage("2025-Q4", "2026-Q1", "2026-Q2"), false);
  assert.equal(dansPlage("2026-Q3", undefined, undefined), true);
  assert.deepEqual(trimestresDisponibles(SOURCE_REPONSE), TRIMESTRES);
  const filtree = filtrerParPlage(SOURCE_REPONSE, "2026-Q1", "2026-Q2");
  assert.deepEqual(filtree.product.map((p) => p.quarter), ["2026-Q1", "2026-Q2"]);
  assert.deepEqual(filtree.teams[0].points.map((p) => p.quarter), ["2026-Q1", "2026-Q2"]);
});

// A real answer of the contract's `tableauLeadCycle` (the view has no product row, so `product` is empty), with a pooled-year point.
function reponseReelle() {
  const ligne = (team: string, debut: string | null) => ({
    team,
    period: debut === null ? "pooled_year" : "quarter",
    quarter_start: debut,
    items_lt: val(30),
    items_ct: val(30),
    lead_median_days: val(40),
    cycle_median_days: val(10),
  });
  const debuts = ["2025-10-01", "2026-01-01", "2026-04-01", "2026-07-01"];
  const rows = ["team-a", "team-b"].flatMap((team) => [...debuts.map((d) => ligne(team, d)), ligne(team, null)]);
  const vue = { view: "v_team_lead_time_throughput", threshold: 5, columns: [], rows, sources: ["flow"] };
  return tableauLeadCycle(vue as never, { medianMinItems: 10, p85MinItems: 20 }, "2026-10-05", identifiantEquipe);
}

test("the quarters offered come from the series of the teams when the product line is empty, without the pooled year (B1)", () => {
  const reelle = reponseReelle();
  assert.deepEqual(reelle.product, []);
  assert.deepEqual(trimestresDisponibles(reelle), TRIMESTRES);
});

test("a range keeps the pooled-year point of a series, whatever the bounds (C2)", () => {
  const filtree = filtrerParPlage(reponseReelle(), "2026-Q1", "2026-Q2");
  assert.deepEqual(filtree.teams[0].points.map((p) => p.quarter), ["2026-Q1", "2026-Q2", "pooled_year"]);
});

test("the simulated totals follow the server: masked only when a quarter of the range is masked (C3)", async () => {
  const lire = (code: "stories-inout" | "defects-inout", from: string, to: string) => SOURCE_PANNEAUX_SIMULEE.lire(code, { team: undefined, from, to }) as Promise<PanneauStoriesInout>;
  const histoires = await lire("stories-inout", "2026-Q1", "2026-Q2");
  assert.deepEqual(histoires.total, { created: val(255), done: val(225) });
  // R-20261114-49, by hand: the quarter 2025-Q4 (40 created, 38 done) is gone from the three closed quarters, so the range without a masked quarter is the
  // single quarter 2026-Q1: 38 created and 36 done (before: 2025-Q4 to 2026-Q1, 40 + 38 = 78 and 38 + 36 = 74).
  const sansMasque = await lire("defects-inout", "2026-Q1", "2026-Q1");
  assert.deepEqual(sansMasque.total, { created: val(38), done: val(36) });
  const avecMasque = await lire("defects-inout", "2026-Q1", "2026-Q2");
  assert.deepEqual(avecMasque.total, { created: masque(), done: val(73) });
});

// ---- the filter bar ----------------------------------------------------------------------------------------------------------------

function elementBarre(equipes: readonly string[], filtres = { team: undefined as string | undefined, from: undefined as string | undefined, to: undefined as string | undefined }) {
  return h(BarreFiltres, { equipes, trimestres: TRIMESTRES, filtres, surFiltres: () => undefined });
}

function barre(equipes: readonly string[], filtres = { team: undefined as string | undefined, from: undefined as string | undefined, to: undefined as string | undefined }, langue: "en" | "fr" = "en"): string {
  return rendre(elementBarre(equipes, filtres), langue);
}

test("the bar offers one team at a time: the product, then the identifiers in a neutral order, whatever the order received", () => {
  const options = (html: string) => [...html.matchAll(/<option value="([^"]*)"[^>]*>([^<]*)<\/option>/g)].map((m) => [m[1], m[2]]);
  const trie = [A, B, C].sort((a, b) => a.localeCompare(b));
  const attendu = trie.map((i) => [i, i]);
  assert.deepEqual(options(barre([A, B, C])).slice(0, 3), attendu);
  assert.deepEqual(options(barre([C, A, B])).slice(0, 3), attendu);
  assert.equal((barre([A, B]).match(/<select[^>]*name="team"/g) ?? []).length, 1);
  assert.doesNotMatch(barre([A, B]), /<select[^>]*multiple/);
  assert.doesNotMatch(barre([A, B]), /type="checkbox"/);
});

test("the team is shown by its opaque identifier, never by a name, and the chosen one is selected", () => {
  const html = barre([A, B], { team: B, from: undefined, to: undefined });
  assert.doesNotMatch(texte(html), /Team [A-C]/i);
  assert.match(html, new RegExp(`<option value="${B}" selected="">${B}</option>`));
});

test("the bar has no colour per team, no style, no rank and no side-by-side choice", () => {
  const html = barre([A, B, C]);
  assert.doesNotMatch(html, /style=|data-color|data-rank|rang|rank/i);
  const css = readFileSync(`${FRONT}src/styles/styles.css`, "utf8");
  assert.doesNotMatch(css, /\.barre-filtres[^{]*\{[^}]*(?:color|background)/);
});

test("the bar offers the closed quarters of the answer for both bounds, labelled from the catalogue, in each language", () => {
  const html = barre([A], { team: undefined, from: "2026-Q1", to: "2026-Q3" });
  assert.match(html, /<option value="2026-Q1" selected="">Q1 2026<\/option>/);
  assert.match(html, /<option value="2026-Q3" selected="">Q3 2026<\/option>/);
  assert.match(texte(barre([A], undefined, "fr")), /T1 2026/);
  assert.match(texte(html), new RegExp(en["tableau.filters.team"]));
  assert.match(texte(barre([A], undefined, "fr")), new RegExp(fr["tableau.filters.team"]));
});

// ---- the first panel inside the framework ----------------------------------------------------------------------------------------

const SOURCE_REPONSE: ReponseLeadCycle = {
  threshold: 5,
  dataDate: "2026-10-27",
  dataset: "synthetic",
  product: TRIMESTRES.map((quarter) => ({ quarter, lead: val(40), cycle: val(10), items: val(100) })),
  teams: [
    { team: "team-a", teamId: A, points: TRIMESTRES.map((quarter) => ({ quarter, lead: val(50), cycle: val(12), items: val(30) })) },
    { team: "team-b", teamId: B, points: TRIMESTRES.map((quarter) => ({ quarter, lead: val(20), cycle: val(6), items: val(20) })) },
  ],
};

function premierPanneau(avecBarre: boolean, langue: "en" | "fr" = "en"): string {
  const element = h(ContenuTableau, {
    reponse: SOURCE_REPONSE,
    portee: "",
    surPortee: () => undefined,
    fiche: { genre: "aucune" },
    surFaire: () => undefined,
    surCreer: () => undefined,
    simulee: true,
    barre: avecBarre ? elementBarre([A, B]) : undefined,
  });
  return rendre(element, langue);
}

test("inside the framework the first panel takes the bar in place of its own selector and carries the cycle time mention", () => {
  const html = premierPanneau(true);
  assert.equal((html.match(/<select/g) ?? []).length, 3, "un choix d'équipe et deux trimestres, pas de second sélecteur");
  assert.match(html, /data-mention="cycle_time_includes_ready_queue"/);
  assert.match(texte(html), new RegExp(en["fiche.mention.cycle_time_includes_ready_queue"]));
  assert.doesNotMatch(premierPanneau(false), /data-mention=/, "sans le cadre, l'écran existant ne change pas");
});

test("the first panel shows no time per segment", () => {
  const html = texte(premierPanneau(true));
  assert.doesNotMatch(html, /segment/i);
});

// ---- the panels ----------------------------------------------------------------------------------------------------------------

const ENTETE = { scope: "product", from: "2026-Q1", to: "2026-Q3", threshold: 5, dataDate: "2026-10-27", dataset: "synthetic" as const };
const flux = (quarter: string, created: ReturnType<typeof val> | ReturnType<typeof masque>, done: ReturnType<typeof val> | ReturnType<typeof masque>) => ({
  quarter,
  created,
  done,
});

const STORIES: PanneauStoriesInout = {
  ...ENTETE,
  panel: "stories-inout",
  hypothesis: "h1_second_half",
  mentions: ["indirect_indicator"],
  points: [flux("2026-Q1", val(130), val(110)), flux("2026-Q2", masque(), val(90)), flux("2026-Q3", val(140), val(120))],
  // R-20261114-49, by hand: the done total of the three quarters is 110 + 90 + 120 = 320 (before: four quarters, 100 + 110 + 90 + 120 = 420).
  total: { created: masque(), done: val(320) },
};
const DEFECTS: PanneauDefectsInout = {
  ...STORIES,
  panel: "defects-inout",
  hypothesis: "h3",
  mentions: ["indirect_indicator", "product_level"],
};
const CORRECTION: PanneauCorrectionShare = {
  ...ENTETE,
  panel: "correction-share",
  hypothesis: "h3",
  mentions: ["indirect_indicator", "product_level"],
  points: [
    { quarter: "2026-Q1", defectsDone: val(20), storiesDone: val(100), share: { state: "value", value: 16.7 } },
    { quarter: "2026-Q2", defectsDone: masque(), storiesDone: val(110), share: masque() },
  ],
};
const BLOQUE: PanneauBlockedShare = {
  ...ENTETE,
  scope: `team.${A}`,
  panel: "blocked-share",
  hypothesis: "dependencies_explanation",
  mentions: ["indirect_indicator", "blocked_share_current_links"],
  points: [
    { quarter: "2026-Q1", blocked: val(8), blockedN: val(40), share: { state: "value", value: 20 } },
    { quarter: "2026-Q2", blocked: masque(), blockedN: val(35), share: masque() },
  ],
};
const TOUS = [STORIES, CORRECTION, DEFECTS, BLOQUE] as const;

function panneau(reponse: Parameters<typeof VuePanneau>[0]["reponse"], demandee = "product", langue: "en" | "fr" = "en"): string {
  return rendre(h(VuePanneau, { reponse, demandee }), langue);
}

test("the four panels of the contract are the four panels of the screen, in the order of D35", () => {
  assert.deepEqual([...CODES_PANNEAUX], ["stories-inout", "correction-share", "defects-inout", "blocked-share"]);
  assert.deepEqual(panneauxAffiches({ team: A, from: undefined, to: undefined }), ["stories-inout", "correction-share", "defects-inout", "blocked-share"]);
});

test("each panel names its hypothesis in both languages, with the labels of D29 written once validated by the author", () => {
  assert.equal(en["tableau.hypothesis.h1_second_half"], "Serves the question: inflow against outflow");
  assert.equal(fr["tableau.hypothesis.h1_second_half"], "Sert la question : entrées contre sorties");
  assert.equal(en["tableau.hypothesis.h3"], "Serves the question: quality per version");
  assert.equal(fr["tableau.hypothesis.h3"], "Sert la question : qualité par version");
  assert.equal(en["tableau.hypothesis.dependencies_explanation"], "Competing explanation: dependencies");
  assert.equal(fr["tableau.hypothesis.dependencies_explanation"], "Explication concurrente : dépendances");
  assert.equal(en["tableau.signal.served_scope_differs"], "Shown for the product: this panel has no team view.");
  assert.equal(fr["tableau.signal.served_scope_differs"], "Affiché pour le produit : ce panneau n'a pas de vue par équipe.");
  for (const reponse of TOUS) {
    assert.equal(reponse.hypothesis, HYPOTHESES_PANNEAUX[reponse.panel]);
    const html = panneau(reponse, reponse.scope);
    assert.match(html, new RegExp(`data-hypothesis="${reponse.hypothesis}"`));
    assert.match(texte(html), new RegExp(en[`tableau.hypothesis.${reponse.hypothesis}`]));
    assert.match(texte(panneau(reponse, reponse.scope, "fr")), new RegExp(fr[`tableau.hypothesis.${reponse.hypothesis}`]));
  }
});

test("each panel shows its mentions next to the measure, from the catalogue, and the contract decides which", () => {
  for (const reponse of TOUS) {
    assert.deepEqual(reponse.mentions, MENTIONS_PANNEAUX[reponse.panel]);
    const html = panneau(reponse, reponse.scope);
    const montrees = [...html.matchAll(/data-mention="([a-z_]+)"/g)].map((m) => m[1]);
    assert.deepEqual(montrees, [...reponse.mentions]);
  }
  assert.equal(en["fiche.mention.product_level"], "Product level.");
  assert.equal(fr["fiche.mention.product_level"], "Niveau produit.");
  assert.match(texte(panneau(BLOQUE, BLOQUE.scope)), /Links in their current state, without history\./);
});

test("a blocked share without one of its two mentions is not shown", () => {
  for (const mentions of [["indirect_indicator"], ["blocked_share_current_links"], []] as const) {
    const html = panneau({ ...BLOQUE, mentions: [...mentions] } as unknown as PanneauBlockedShare, BLOQUE.scope);
    assert.match(html, /role="alert"/);
    assert.match(texte(html), new RegExp(en["tableau.panel.mentionMissing"]));
    assert.doesNotMatch(html, /<table/);
    assert.doesNotMatch(html, /data-state="value"/);
  }
  assert.match(panneau(BLOQUE, BLOQUE.scope), /<table/);
});

test("the count panels show the cells as received: a masked cell is not a zero, a masked total is a masked cell", () => {
  const html = panneau(STORIES);
  assert.equal((html.match(/data-state="masked"/g) ?? []).length, 2, "un trimestre masqué et le total masqué");
  assert.match(html, />320</);
  assert.match(texte(panneau(CORRECTION)), /16\.7%/);
  assert.match(texte(panneau(CORRECTION, "product", "fr")), /16,7 %/);
});

test("no panel shows a truncated-quarter flag any more: the three closed quarters shown are whole (R-20261114-49)", () => {
  for (const reponse of TOUS) {
    const html = panneau(reponse, reponse.scope);
    assert.doesNotMatch(html, /data-flag|first_quarter_truncated/);
  }
  assert.equal("tableau.flag.first_quarter_truncated" in en, false);
  assert.equal("tableau.flag.first_quarter_truncated" in fr, false);
});

test("a served scope different from the requested one is signalled by the catalogue label, and only then", () => {
  const demandee = porteeDemandee({ team: A, from: undefined, to: undefined });
  assert.equal(demandee, scopeFiche({ kind: "team", team: A }));
  assert.equal(porteeDemandee({ team: undefined, from: undefined, to: undefined }), "product");
  assert.equal(porteeServieDiffere(demandee, "product"), true);
  assert.equal(porteeServieDiffere(demandee, demandee), false);
  assert.equal(porteeServieDiffere("product", "product"), false);
  const signale = panneau(STORIES, demandee);
  assert.match(signale, /data-signal="served_scope_differs"/);
  assert.match(texte(signale), new RegExp(en["tableau.signal.served_scope_differs"]));
  assert.match(texte(panneau(STORIES, demandee, "fr")), new RegExp(fr["tableau.signal.served_scope_differs"]));
  assert.doesNotMatch(panneau(STORIES, "product"), /data-signal/);
  assert.doesNotMatch(panneau(BLOQUE, BLOQUE.scope), /data-signal/);
});

test("the blocked share is neither shown nor requested on the product scope; the other panels are", async () => {
  assert.deepEqual(panneauxAffiches({ team: undefined, from: undefined, to: undefined }), ["stories-inout", "correction-share", "defects-inout"]);
  const demandes: string[] = [];
  const lire = async (code: string) => {
    demandes.push(code);
    return STORIES;
  };
  const client = new QueryClient();
  for (const code of panneauxAffiches({ team: undefined, from: undefined, to: undefined })) {
    await client.prefetchQuery(optionsPanneau(code, { team: undefined, from: undefined, to: undefined }, lire as never));
  }
  assert.deepEqual(demandes, ["stories-inout", "correction-share", "defects-inout"]);
  assert.ok(!demandes.includes("blocked-share"));
});

test("the query of a panel names the panel and the filters, and does not retry an error answer", () => {
  const options = optionsPanneau("stories-inout", { team: A, from: "2026-Q1", to: "2026-Q3" }, async () => STORIES);
  assert.deepEqual(options.queryKey, ["panel", "stories-inout", A, "2026-Q1", "2026-Q3"]);
  assert.equal(options.retry, false);
  assert.deepEqual(optionsPanneau("stories-inout", { team: undefined, from: undefined, to: undefined }, async () => STORIES).queryKey.slice(0, 3), ["panel", "stories-inout", "product"]);
});

test("there is no release panel", () => {
  for (const code of CODES_PANNEAUX) assert.doesNotMatch(code, /release/);
  const css = readFileSync(`${FRONT}src/composants/PanneauxProduit.ts`, "utf8");
  assert.doesNotMatch(css, /release/i);
});

test("on real data a panel is shown in its reduced form: header and label, no table, no count", () => {
  const reduit: PanneauReduit = {
    panel: "stories-inout",
    scope: "product",
    from: "2026-Q1",
    to: "2026-Q3",
    threshold: 5,
    dataDate: "2026-10-27",
    hypothesis: "h1_second_half",
    mentions: ["indirect_indicator"],
    limits: ["reduced_form"],
    dataset: "real",
  };
  const html = panneau(reduit);
  assert.doesNotMatch(html, /<table/);
  assert.match(texte(html), new RegExp(en["fiche.limit.reduced_form"]));
  assert.match(html, /data-hypothesis="h1_second_half"/);
  assert.doesNotMatch(html, /fiche-jeu-synthetique/);
});

test("a panel of the synthetic dataset carries the notice of the synthetic dataset", () => {
  assert.match(panneau(STORIES), /data-jeu="synthetic"/);
  assert.match(texte(panneau(STORIES)), new RegExp(en["fiche.syntheticNotice"]));
});

test("no count panel carries the action make it a sheet, the charts that have a served sheet keep it (Q92)", () => {
  for (const reponse of TOUS) {
    const html = panneau(reponse, reponse.scope);
    assert.doesNotMatch(html, /<button/);
    assert.doesNotMatch(html, /make-sheet/);
    assert.doesNotMatch(texte(html), new RegExp(en["tableau.makeSheet"]));
  }
  const premier = premierPanneau(true);
  assert.match(premier, new RegExp(`<button type="button" class="bouton">${en["tableau.makeSheet"]}</button>`));
});

// ---- the sources -----------------------------------------------------------------------------------------------------------------

test("the simulated panels are declared simulated and answer each panel with the schema of the contract's codes", async () => {
  assert.equal(SOURCE_PANNEAUX_SIMULEE.simulee, true);
  for (const code of CODES_PANNEAUX) {
    const filtres = { team: A, from: undefined, to: undefined };
    const reponse = await SOURCE_PANNEAUX_SIMULEE.lire(code, filtres);
    assert.equal(reponse.panel, code);
    assert.equal(reponse.hypothesis, HYPOTHESES_PANNEAUX[code]);
  }
  await assert.rejects(SOURCE_PANNEAUX_SIMULEE.lire("blocked-share", { team: undefined, from: undefined, to: undefined }), (e) => e instanceof RefusPanneau && e.code === "SCOPE_INVALID");
  const produit = await SOURCE_PANNEAUX_SIMULEE.lire("defects-inout", { team: A, from: undefined, to: undefined });
  assert.equal(produit.scope, "product", "un panneau produit demandé avec une équipe est servi pour le produit");
});

function fauxFetch(reponse: Response | Error): { appeler: typeof fetch; urls: string[] } {
  const urls: string[] = [];
  const appeler = (async (url: string) => {
    urls.push(url);
    if (reponse instanceof Error) throw reponse;
    return reponse;
  }) as unknown as typeof fetch;
  return { appeler, urls };
}
const json = (corps: unknown, statut = 200): Response => new Response(JSON.stringify(corps), { status: statut, headers: { "content-type": "application/json" } });

test("the HTTP reader asks the route of the panel with the team identifier and the quarters, and passes the answer on as received", async () => {
  const { appeler, urls } = fauxFetch(json(STORIES));
  const lue = await lirePanneauHttp("stories-inout", { team: A, from: "2026-Q1", to: "2026-Q3" }, appeler);
  assert.deepEqual(lue, STORIES);
  assert.deepEqual(urls, [`/api/panels/stories-inout?team=${A}&from=2026-Q1&to=2026-Q3`]);
  const produit = fauxFetch(json(STORIES));
  await lirePanneauHttp("stories-inout", { team: undefined, from: "2026-Q1", to: "2026-Q3" }, produit.appeler);
  assert.doesNotMatch(produit.urls[0], /team=/);
});

test("the HTTP reader turns a refusal into a code of the catalogue and a malformed answer into the internal error", async () => {
  for (const code of ["SCOPE_INVALID", "RANGE_INVALID", "INVALID_REQUEST"]) {
    await assert.rejects(lirePanneauHttp("blocked-share", { team: undefined, from: "2026-Q1", to: "2026-Q3" }, fauxFetch(json({ error: code }, 422)).appeler), (e) => e instanceof RefusPanneau && e.code === code);
    assert.ok(en[`error.${code}`] && fr[`error.${code}`], `code d'erreur sans traduction : ${code}`);
  }
  await assert.rejects(lirePanneauHttp("stories-inout", { team: A, from: "2026-Q1", to: "2026-Q3" }, fauxFetch(json({ unrelated: true })).appeler), (e) => e instanceof RefusPanneau && e.code === "INTERNAL");
  await assert.rejects(lirePanneauHttp("stories-inout", { team: A, from: "2026-Q1", to: "2026-Q3" }, fauxFetch(new Error("down")).appeler), (e) => e instanceof RefusPanneau && e.code === "INTERNAL");
  await assert.rejects(lirePanneauHttp("stories-inout", { team: A, from: "2026-Q1", to: "2026-Q3" }, fauxFetch(json({ error: "NOPE" }, 500)).appeler), (e) => e instanceof RefusPanneau && e.code === "INTERNAL");
});

// ---- the screen ------------------------------------------------------------------------------------------------------------------

// R-20261104-36 N1 (a), R-20261104-62 : réponse du serveur réglage désactivé (les séries ne portent pas `team`) ; `avecNom` rend la réponse avec noms.
async function lireTableauServi(avecNom: boolean): Promise<ReponseLeadCycle> {
  const base = await lireLeadCycleSimule();
  return servirTableau(base, { jeu: "synthetic", comptesAutorises: false, afficherNoms: avecNom }) as ReponseLeadCycle;
}

async function ecran(props: Parameters<typeof Application>[0], avecNom = false): Promise<string> {
  const client = new QueryClient();
  await client.prefetchQuery(optionsLeadCycle(() => lireTableauServi(avecNom)));
  return renderToStaticMarkup(h(QueryClientProvider, { client }, h(Application, { tableau: SOURCE_SIMULEE, ecranInitial: "tableau", ...props })));
}

test("without a panels source the second screen is the one it was", async () => {
  const sans = await ecran({});
  assert.doesNotMatch(sans, /data-panel=/);
  assert.doesNotMatch(sans, /barre-filtres/);
  assert.match(sans, /<select/);
});

test("with a panels source the second screen shows the bar and the panels that fit the filters, and the filters of the address", async () => {
  // R-20261031-66 (Q110 a): no product option; an address without a team opens on the first team in the neutral order of the identifiers.
  const produit = await ecran({ panneaux: SOURCE_PANNEAUX_SIMULEE, filtresInitiaux: { team: undefined, from: undefined, to: undefined } });
  assert.match(produit, /barre-filtres/);
  assert.deepEqual([...produit.matchAll(/data-panel="([a-z-]+)"/g)].map((m) => m[1]), ["stories-inout", "correction-share", "defects-inout", "blocked-share"]);
  assert.doesNotMatch(texte(produit), new RegExp(en["tableau.panel.blocked-share.teamRequired"]));
  const equipe = await ecran({ panneaux: SOURCE_PANNEAUX_SIMULEE, filtresInitiaux: { team: identifiantEquipe("team-a"), from: "2026-Q1", to: "2026-Q3" } });
  assert.deepEqual([...equipe.matchAll(/data-panel="([a-z-]+)"/g)].map((m) => m[1]), ["stories-inout", "correction-share", "defects-inout", "blocked-share"]);
  // Setting off (N1 (a)): the option of the chosen team shows its identifier, never a name.
  assert.match(equipe, new RegExp(`<option value="${A}" selected="">${A}</option>`));
  assert.match(equipe, /<option value="2026-Q1" selected="">/);
  assert.doesNotMatch(texte(equipe), /team-a/);
  // Setting on (D35, R-20261104-62 Q2): the same option shows the name, its value stays the identifier.
  const nomme = await ecran({ panneaux: SOURCE_PANNEAUX_SIMULEE, filtresInitiaux: { team: A, from: "2026-Q1", to: "2026-Q3" } }, true);
  assert.match(nomme, new RegExp(`<option value="${A}" selected="">team-a</option>`));
});

// ---- static ------------------------------------------------------------------------------------------------------------------------

test("the front computes no total, share or state in the files of this group, and holds no visible text of its own", () => {
  const classes = classesDeCss(readFileSync(`${FRONT}src/styles/styles.css`, "utf8"));
  const fichiersDuGroupe = sources(FRONT, "src", [".ts"]).filter((s) =>
    ["src/api/filtres.ts", "src/api/panneaux.ts", "src/composants/BarreFiltres.ts", "src/composants/PanneauxProduit.ts", "src/simule/panneaux.ts"].includes(s.nom),
  );
  assert.equal(fichiersDuGroupe.length, 5);
  assert.deepEqual(fichiersDuGroupe.flatMap((s) => derivations(s.nom, s.contenu)), []);
  assert.deepEqual(fichiersDuGroupe.flatMap((s) => textesVisibles(s.nom, s.contenu, classes)), []);
  for (const s of fichiersDuGroupe) assert.doesNotMatch(analyser(s.contenu).code, /\bstyle\b/);
});

test("both catalogues carry the keys of the panels and the filters", () => {
  const cles = [
    "tableau.filters.legend",
    "tableau.filters.team",
    "tableau.filters.from",
    "tableau.filters.to",
    "tableau.panel.title.stories-inout",
    "tableau.panel.title.correction-share",
    "tableau.panel.title.defects-inout",
    "tableau.panel.title.blocked-share",
    "tableau.panel.blocked-share.teamRequired",
    "tableau.panel.mentionMissing",
    "tableau.panel.shareFormat",
    "error.SCOPE_INVALID",
    "error.RANGE_INVALID",
  ];
  for (const cle of cles) assert.ok(en[cle] && fr[cle], `clé absente : ${cle}`);
});
