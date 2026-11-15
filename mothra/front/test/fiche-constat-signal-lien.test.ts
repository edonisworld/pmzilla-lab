// Audit #629, group F1, the sheet's reading face: A-01 (the verdict says why it is what it is, Q6), A-02 (the attachment signal stands next to the
// verdict, on the management face), A-03 (the link "See the detail by quarter" carries the team and the period of the sheet). Every sheet answer
// comes from `corpsDepuisVues` of the contract on synthetic rows (test/fiches-h1.ts, test/fiches-h5.ts); nothing is computed by the front.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement as h } from "react";

import { servirTableau, tableauLeadCycle } from "@mothra/contract";
import { identifiantEquipe } from "@mothra/contract/equipe";
import { CONSTATS_DE_VERDICT } from "@mothra/contract/listes-fiche";

import { Application } from "../src/Application.ts";
import { adresseTableauDeFiche } from "../src/api/filtres.ts";
import { lireFiltresAdresse } from "../src/api/filtres.ts";
import type { ReponseFiche } from "../src/api/fiche.ts";
import { optionsLeadCycle } from "../src/api/leadCycle.ts";
import { FicheConviction } from "../src/composants/FicheConviction.ts";
import { catalogues } from "../src/i18n/langue.ts";
import type { Langue } from "../src/i18n/langue.ts";
import { CAS_H1, EQUIPE_SYNTHETIQUE, ficheH1, IDENTIFIANT_OPAQUE } from "./fiches-h1.ts";
import type { CasH1 } from "./fiches-h1.ts";
import { CAS_H5, ficheH5 } from "./fiches-h5.ts";
import type { CasH5 } from "./fiches-h5.ts";
import { rendre, texte } from "./rendu.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const en = catalogues.en;
const fr = catalogues.fr;

function propre(html: string): string {
  // The apostrophe and the ampersand of an address are written as entities by the renderer.
  return html.replaceAll("&#x27;", "'").replaceAll("&amp;", "&");
}

function fiche(f: ReponseFiche, langue: Langue = "en", props: Partial<Parameters<typeof FicheConviction>[0]> = {}): string {
  return propre(rendre(h(FicheConviction, { fiche: f, ...props }), langue));
}

// The zone of the verdict: the line of the badge, up to the evidence card (what stands "under the badge" and before the evidence).
function zoneVerdict(html: string): string {
  const zone = /<div class="fiche-ligne-badge">[\s\S]*?(?=<section class="carte carte-preuve"|<div class="encarts"|<footer)/.exec(html)?.[0];
  assert.ok(zone !== undefined, "zone du verdict absente");
  return zone;
}

function constats(html: string): string[] {
  return [...zoneVerdict(html).matchAll(/data-constat="([^"]+)"/g)].map((m) => m[1]);
}

// ---- A-01: the verdict says why ---------------------------------------------------------------------------------------------------

// The case "confirmed" of the fixtures has its verdict set by hand on rows the contract turns into "not settled" (D20, D33): the fixture touches
// the verdict, its reasons and its finding (the tests habillage-fiche-h1.test.ts and habillage-fiche-h5.test.ts pin it), so that no "confirmation barred"
// sentence stands under a Confirmed badge: the finding is the one of the figures, `h1_above_upper` / `h5_within_band`.
const CONSTAT_H1: Record<CasH1, string[]> = {
  confirmed: ["h1_above_upper"],
  refuted: ["h1_median_under_lower"],
  not_settled: ["h1_median_in_grey_zone"],
  insufficient_sample: [],
  masked: [],
  not_comparable: ["h1_median_under_lower"],
};

const CONSTAT_H5: Record<CasH5, string[]> = {
  confirmed: ["h5_within_band"],
  refuted: ["h5_under_low_floor"],
  not_settled: ["h5_under_floor"],
  insufficient_sample: [],
  masked: [],
  throughput_masked: [],
  // R-20261114-83: with three closed quarters a judged quarter whose P85 is insufficient or masked leaves two complete quarters: no reference, the verdict is
  // "insufficient_sample" and it has no finding (before: four quarters, a verdict "not settled" that barred a confirmation).
  p85_insufficient: [],
  p85_masked: [],
};

test("the findings of the answer are the contract's: one list per case, hypothesis 1 and hypothesis 5", () => {
  for (const cas of CAS_H1) assert.deepEqual(ficheH1(cas).verdictFindings, CONSTAT_H1[cas], `h1 ${cas}`);
  for (const cas of CAS_H5) assert.deepEqual(ficheH5(cas).verdictFindings, CONSTAT_H5[cas], `h5 ${cas}`);
});

test("the case the audit saw: ratios above the upper threshold and a verdict \"not settled\" say that confirming is barred", () => {
  const f = ficheH1("confirmed", { verdictDuContrat: true });
  assert.equal(f.verdict, "not_settled");
  assert.deepEqual(f.verdictFindings, ["confirmation_barred"]);
  for (const langue of ["en", "fr"] as const) {
    const html = fiche(f, langue);
    assert.deepEqual(constats(html), ["confirmation_barred"], langue);
    assert.ok(texte(zoneVerdict(html)).includes(catalogues[langue]["fiche.finding.confirmation_barred"]), langue);
  }
  const h5 = ficheH5("confirmed", { verdictDuContrat: true });
  assert.deepEqual(h5.verdictFindings, ["confirmation_barred"]);
});

test("a confirmed verdict whose finding is the figures' own says the ratios are above the upper threshold", () => {
  const f = { ...ficheH1("confirmed"), verdictFindings: ["h1_above_upper"] } as ReponseFiche;
  assert.deepEqual(constats(fiche(f)), ["h1_above_upper"]);
  assert.ok(texte(zoneVerdict(fiche(f))).includes(en["fiche.finding.h1_above_upper"]));
  const h5 = { ...ficheH5("confirmed"), verdictFindings: ["h5_within_band"] } as ReponseFiche;
  assert.ok(texte(zoneVerdict(fiche(h5))).includes(en["fiche.finding.h5_within_band"]));
});

test("a sentence stands under the badge for every verdict that has a finding, in both languages, in the zone of the badge and before the evidence", () => {
  for (const langue of ["en", "fr"] as const) {
    for (const cas of CAS_H1) {
      const html = fiche(ficheH1(cas), langue);
      assert.deepEqual(constats(html), CONSTAT_H1[cas], `h1 ${cas} ${langue}`);
      for (const code of CONSTAT_H1[cas]) assert.ok(texte(zoneVerdict(html)).includes(catalogues[langue][`fiche.finding.${code}` as keyof typeof en]), `${cas} ${code}`);
      assert.ok(html.indexOf('class="badge') < html.indexOf("data-constat=") || CONSTAT_H1[cas].length === 0, `h1 ${cas}: after the badge`);
    }
    for (const cas of CAS_H5) {
      const html = fiche(ficheH5(cas), langue);
      assert.deepEqual(constats(html), CONSTAT_H5[cas], `h5 ${cas} ${langue}`);
    }
  }
});

test("hypothesis 5 refuted tells its cause in a sentence, not only by the bold line of the table", () => {
  const html = fiche(ficheH5("refuted"));
  assert.equal(texte(zoneVerdict(html)).includes(en["fiche.finding.h5_under_low_floor"]), true);
  assert.match(zoneVerdict(html), /<p class="fiche-constat" data-constat="h5_under_low_floor">/);
});

test("a case without finding keeps its own sentence of the evidence card (insufficient sample, masked), and the finding sentence is not added to it", () => {
  for (const cas of ["insufficient_sample", "masked"] as const) {
    const html = fiche(ficheH1(cas));
    assert.doesNotMatch(html, /fiche-constat/, cas);
    assert.match(html, /class="preuve-constat"/, cas);
  }
});

test("an answer with no findings (a version frozen before the field) tells nothing, and a code the front does not know has the fallback sentence, never the code", () => {
  const sans = { ...ficheH5("refuted") } as Partial<ReponseFiche> & { verdictFindings?: unknown };
  delete sans.verdictFindings;
  assert.doesNotMatch(fiche(sans as ReponseFiche), /fiche-constat/);
  const inconnu = { ...ficheH5("refuted"), verdictFindings: ["a_code_from_the_future"] } as unknown as ReponseFiche;
  const html = fiche(inconnu);
  assert.doesNotMatch(html, /a_code_from_the_future/);
  assert.ok(texte(zoneVerdict(html)).includes(en["fiche.finding.unknown"]));
});

test("every code of the contract's list has its sentence in both catalogues, different in the two languages, and the unknown one too", () => {
  for (const code of [...CONSTATS_DE_VERDICT, "unknown"]) {
    const cle = `fiche.finding.${code}` as keyof typeof en;
    assert.ok(typeof en[cle] === "string" && en[cle] !== "", `en ${cle}`);
    assert.ok(typeof fr[cle] === "string" && fr[cle] !== "", `fr ${cle}`);
    assert.notEqual(en[cle], fr[cle], cle);
  }
  const cles = Object.keys(en).filter((cle) => cle.startsWith("fiche.finding."));
  assert.deepEqual(cles.sort(), [...CONSTATS_DE_VERDICT, "unknown"].map((code) => `fiche.finding.${code}`).sort(), "no other finding key");
});

test("the finding sentences hold no figure and no emoji, and say nothing the verdict does not", () => {
  for (const code of CONSTATS_DE_VERDICT) {
    for (const langue of ["en", "fr"] as const) {
      const phrase = catalogues[langue][`fiche.finding.${code}` as keyof typeof en];
      assert.doesNotMatch(phrase.replaceAll("P85", ""), /\d/, `${langue} ${code}`);
      assert.doesNotMatch(phrase, /\p{Extended_Pictographic}/u, `${langue} ${code}`);
    }
  }
});

// ---- A-02: the signal stands next to the verdict ----------------------------------------------------------------------------------

test("a raised attachment signal stands in the zone of the verdict, on the management face, and also in the block of the explanations", () => {
  const f = { ...ficheH5("refuted"), attachmentSignalShown: true } as ReponseFiche;
  for (const langue of ["en", "fr"] as const) {
    const html = fiche(f, langue);
    const phrase = catalogues[langue]["fiche.attachmentSignal"];
    const zone = zoneVerdict(html);
    assert.match(zone, /<p class="fiche-signal" data-signal-verdict="shown">/, langue);
    assert.ok(texte(zone).includes(phrase), langue);
    // The block of the explanations (end of the page) keeps its row.
    const bloc = /<section class="explications-concurrentes">[\s\S]*?<\/section>/.exec(html)?.[0] ?? "";
    assert.ok(texte(bloc).includes(phrase), `bloc ${langue}`);
    assert.ok(html.indexOf("data-signal-verdict") < html.indexOf('class="explications-concurrentes"'), "avant le bloc du bas");
  }
});

test("without a raised signal the zone of the verdict holds no signal sentence; the sentence of the signal is a plain paragraph, one role=note per screen", () => {
  assert.doesNotMatch(fiche(ficheH5("refuted")), /data-signal-verdict/);
  const montre = fiche({ ...ficheH5("refuted"), attachmentSignalShown: true } as ReponseFiche);
  assert.doesNotMatch(montre, /role="note"/);
});

test("the signal beside the verdict is drawn by the stylesheet's classes only: no style attribute, no emoji", () => {
  const html = fiche({ ...ficheH5("refuted"), attachmentSignalShown: true } as ReponseFiche);
  assert.doesNotMatch(zoneVerdict(html), /style=|\p{Extended_Pictographic}/u);
  const css = readFileSync(`${FRONT}src/styles/styles.css`, "utf8");
  assert.match(css, /\.fiche-constat\b[^{]*\{[^}]*font-size:\s*var\(--font-size-small\)/);
  assert.doesNotMatch(/\.fiche-constat\b[^{]*\{[^}]*\}/.exec(css)?.[0] ?? "", /#[0-9a-fA-F]{3,8}\b|\brgb|px\b/);
});

// ---- A-03: the link keeps the team and the period ---------------------------------------------------------------------------------

test("the link \"See the detail by quarter\" carries the team and the period of the sheet", () => {
  const f = ficheH1("confirmed");
  const attendu = `#/tableau?team=${IDENTIFIANT_OPAQUE}&from=2026-Q1&to=2026-Q3`;
  assert.equal(adresseTableauDeFiche(f.method), attendu);
  for (const langue of ["en", "fr"] as const) {
    const html = fiche(f, langue);
    assert.match(html, new RegExp(`<a class="lien" href="${attendu.replaceAll("?", "\\?")}">${catalogues[langue]["conviction.detail"]}</a>`), langue);
  }
  assert.match(fiche(ficheH5("confirmed")), new RegExp(`href="${attendu.replaceAll("?", "\\?")}"`));
});

test("the address of the link is read back as the filters of the dashboard, the opaque identifier and the two closed quarters", () => {
  const filtres = lireFiltresAdresse(adresseTableauDeFiche(ficheH1("confirmed").method));
  assert.deepEqual(filtres, { team: IDENTIFIANT_OPAQUE, from: "2026-Q1", to: "2026-Q3" });
});

test("a scope that is not a team, or an identifier that is not the opaque shape, gives the plain address of the dashboard, never a name", () => {
  const f = ficheH1("confirmed");
  // No team in the address, the period of the sheet kept.
  const periode = "#/tableau?from=2026-Q1&to=2026-Q3";
  assert.equal(adresseTableauDeFiche({ ...f.method, scope: { level: "product", id: "product" } }), periode);
  assert.equal(adresseTableauDeFiche({ ...f.method, scope: { level: "team", id: `team.${EQUIPE_SYNTHETIQUE}` } }), periode);
  assert.equal(adresseTableauDeFiche({ ...f.method, scope: { level: "team", id: "team A" } }), periode);
  assert.equal(adresseTableauDeFiche({ ...f.method, scope: { level: "team", id: "team A" }, period: { quarters: [] } }), "#/tableau");
  assert.equal(adresseTableauDeFiche({ ...f.method, period: { quarters: [] } }), `#/tableau?team=${IDENTIFIANT_OPAQUE}`);
});

test("the dashboard opened by the link selects the team and the period of the sheet, not the first team of the list", async () => {
  const f = ficheH1("confirmed");
  const val = (v: number) => ({ state: "value" as const, value: v });
  const ligne = (equipe: string, debut: string | null) => ({
    team: equipe,
    period: debut === null ? "pooled_year" : "quarter",
    quarter_start: debut,
    items_lt: val(30),
    items_ct: val(30),
    lead_median_days: val(40),
    cycle_median_days: val(10),
  });
  const debuts = ["2026-01-01", "2026-04-01", "2026-07-01"];
  // Two teams; the sheet's team is the one whose identifier sorts last, so the first of the list is not the sheet's.
  const equipes = [EQUIPE_SYNTHETIQUE, "Equipe Temoin Autre"].sort((a, b) => identifiantEquipe(a).localeCompare(identifiantEquipe(b)));
  const cible = equipes.find((e) => identifiantEquipe(e) === IDENTIFIANT_OPAQUE);
  assert.ok(cible !== undefined);
  const ordre = [equipes.find((e) => e !== cible) as string, cible];
  const lignes = ordre.flatMap((e) => [...debuts.map((d) => ligne(e, d)), ligne(e, null)]);
  const vue = { view: "v_team_lead_time_throughput", threshold: 5, columns: [], rows: lignes, sources: ["flow"] };
  const base = tableauLeadCycle(vue as never, { medianMinItems: 10, p85MinItems: 20 }, "2026-10-05", identifiantEquipe);
  const reponse = servirTableau(base, { jeu: "synthetic", comptesAutorises: false, afficherNoms: false });
  const lire = async () => reponse;
  const client = new QueryClient({ defaultOptions: { queries: { gcTime: Infinity } } });
  await client.prefetchQuery(optionsLeadCycle(lire));
  const source = { lire, creer: async () => ({ id: "x", state: "draft" as const }), simulee: false };
  const filtres = lireFiltresAdresse(adresseTableauDeFiche(f.method));
  const html = propre(
    rendre(
      h(QueryClientProvider, { client }, h(Application, { tableau: source, panneaux: { lire: async () => { throw new Error("pas de panneau"); }, simulee: true }, ecranInitial: "tableau", filtresInitiaux: filtres })),
      "en",
    ),
  );
  const selectionnee = (nom: string): string | undefined => new RegExp(`<select name="${nom}"[^>]*>[\\s\\S]*?<option value="([^"]+)" selected=""`).exec(html)?.[1];
  assert.equal(selectionnee("team"), IDENTIFIANT_OPAQUE);
  assert.equal(selectionnee("from"), "2026-Q1");
  assert.equal(selectionnee("to"), "2026-Q3");
});
