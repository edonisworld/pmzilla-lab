// Lot 3d of mothra-demo-habillage (task 11.1, design D18, R-20261101-26, R-20261101-36): the real-data states of decision 16. On real data the
// dashboard shows medians only, the form "make it a sheet" shows hypothesis 5 disabled with its reason (never hidden, never enabled, no
// request, no raw error) and the disabled choice is a component of the catalogue in its states. The count panels (task 37.2 of
// mothra-slices) and the page "preparation of a cycle" (task 41.1) draw the code `real_counts_not_shown` only when their answer carries it: on
// main the reduced panel answer carries no such code and the page does not exist, so neither is tested here (see the final message of the lot).
// Practice R-20261031-61: every answer of the dashboard comes from `tableauLeadCycle` of the contract on synthetic view rows, reduced by
// `reduceToStatistics` for the real form; nothing is written by hand.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement as h } from "react";

import { reduceToStatistics, tableauLeadCycle } from "@mothra/contract";
import type { ReponseLeadCycle, ReponseLeadCycleReduite } from "@mothra/contract";
import { identifiantEquipe } from "@mothra/contract/equipe";
import type { GraphiqueDeFiche } from "@mothra/contract/listes-fiche";

import { ChoixDesactive } from "../src/composants/ChoixDesactive.ts";
import { catalogues } from "../src/i18n/langue.ts";
import type { Langue } from "../src/i18n/langue.ts";
import { ContenuTableau, demandeDeFiche, graphiquesOfferts } from "../src/pages/PageTableau.ts";
import type { Jetons } from "../scripts/generer-jetons.ts";
import { genererCatalogue } from "../scripts/catalogue.ts";
import { choixRadio, rendre } from "./rendu.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const LANGUES = ["en", "fr"] as const;
const COMPTE = 7919;

function propre(html: string): string {
  return html.replaceAll("&#x27;", "'");
}

// The answer of the dashboard on synthetic view rows, as the server's route builds it; the count is a distinctive number so that a test can
// check it never reaches the real form.
function reponseComplete(): ReponseLeadCycle {
  const val = (v: number) => ({ state: "value" as const, value: v });
  const ligne = (team: string, debut: string | null) => ({
    team,
    period: debut === null ? "pooled_year" : "quarter",
    quarter_start: debut,
    items_lt: val(COMPTE),
    items_ct: val(COMPTE),
    lead_median_days: val(40),
    cycle_median_days: val(10),
  });
  const debuts = ["2025-10-01", "2026-01-01", "2026-04-01", "2026-07-01"];
  const rows = ["team-a", "team-b"].flatMap((team) => [...debuts.map((d) => ligne(team, d)), ligne(team, null)]);
  const vue = { view: "v_team_lead_time_throughput", threshold: 5, columns: [], rows, sources: ["flow"] };
  return tableauLeadCycle(vue as never, { medianMinItems: 10, p85MinItems: 20 }, "2026-10-05", identifiantEquipe);
}

type Jeu = "synthetic" | "real" | undefined;

function reponseDe(jeu: Jeu): ReponseLeadCycle | ReponseLeadCycleReduite {
  const base = reponseComplete();
  if (jeu === undefined) return base;
  return jeu === "synthetic" ? { ...base, dataset: "synthetic" } : reduceToStatistics({ ...base, dataset: "real" });
}

function tableau(jeu: Jeu, langue: Langue, fiche: Parameters<typeof ContenuTableau>[0]["fiche"] = { genre: "aucune" }): string {
  return propre(
    rendre(h(ContenuTableau, { reponse: reponseDe(jeu), portee: "team-a", surPortee: () => undefined, fiche, surFaire: () => undefined, surCreer: () => undefined, simulee: false }), langue),
  );
}

// ---- the dashboard in medians only (D18 point 1) ----------------------------------------------------------------------------------

test("on a really reduced answer the dashboard shows the medians only: no P85, no ratio, no count column, no count", () => {
  const reduite = reponseDe("real");
  assert.ok(!JSON.stringify(reduite).includes(String(COMPTE)), "la réponse réduite porte un effectif");
  for (const langue of LANGUES) {
    const c = catalogues[langue];
    const html = tableau("real", langue);
    assert.ok(html.includes(c["tableau.column.lead"]), langue);
    assert.ok(html.includes(c["tableau.column.cycle"]), langue);
    assert.ok(!html.includes(c["tableau.column.items"]), `${langue}: pas de colonne des effectifs`);
    assert.doesNotMatch(html, new RegExp(String(COMPTE)), langue);
    assert.doesNotMatch(html, /\bP85\b|\bratio\b/i, langue);
    // Medians come as served: 40 and 10 days for each quarter.
    assert.match(html, />40</, langue);
    assert.match(html, />10</, langue);
  }
});

test("the complete answer of the synthetic dataset keeps its count column", () => {
  assert.ok(tableau("synthetic", "en").includes(catalogues.en["tableau.column.items"]));
});

// ---- hypothesis 5 disabled on real data (D18 point 4) -----------------------------------------------------------------------------

test("on real data hypothesis 1 is offered and hypothesis 5 is shown disabled with its reason, linked by aria-describedby, in both languages", () => {
  for (const langue of LANGUES) {
    const c = catalogues[langue];
    const html = tableau("real", langue, { genre: "formulaire" });
    const choix = choixRadio(html);
    assert.deepEqual(choix.map((x) => x.valeur).sort(), ["lead_cycle_h1", "lead_cycle_h5"], `${langue}: les deux choix sont dessinés`);
    const h1 = choix.find((x) => x.valeur === "lead_cycle_h1");
    const h5 = choix.find((x) => x.valeur === "lead_cycle_h5");
    assert.ok(h1 !== undefined && !h1.desactive, `${langue}: l'hypothèse 1 est offerte`);
    assert.ok(h5 !== undefined && h5.desactive, `${langue}: l'hypothèse 5 est désactivée`);
    assert.ok((/<fieldset[\s\S]*?<\/fieldset>/.exec(html)?.[0] ?? "").includes(c["conviction.nav.lead_cycle_h5"]), `${langue}: le libellé de l'hypothèse 5 reste affiché`);
    // The reason is the catalogue sentence, and the disabled input points at the element that holds it.
    assert.ok(h5.decrit !== undefined && h5.decrit !== "", `${langue}: aria-describedby`);
    assert.ok(html.includes(`id="${h5.decrit}"`), `${langue}: la cible de aria-describedby existe`);
    assert.ok(html.includes(`id="${h5.decrit}" class="choix-raison">${c["tableau.form.h5RealUnavailable"]}<`), `${langue}: la raison est la phrase du catalogue`);
    // Never a raw error, never an alert.
    assert.doesNotMatch(html, /role="alert"|NOT_FOUND|INTERNAL/, langue);
    // No choice is taken at first and the draft button stays disabled.
    assert.doesNotMatch(html, /\bchecked\b/, langue);
    assert.match(html, /<button type="submit"[^>]*disabled=""/, langue);
  }
});

test("an answer without a dataset code is treated as real data: hypothesis 5 disabled, never enabled", () => {
  const choix = choixRadio(tableau(undefined, "en", { genre: "formulaire" }));
  assert.equal(choix.find((x) => x.valeur === "lead_cycle_h5")?.desactive, true);
  assert.equal(choix.find((x) => x.valeur === "lead_cycle_h1")?.desactive, false);
});

test("on the synthetic dataset both hypotheses are offered and enabled, with no reason", () => {
  for (const langue of LANGUES) {
    const html = tableau("synthetic", langue, { genre: "formulaire" });
    const choix = choixRadio(html);
    assert.deepEqual(choix.map((x) => x.valeur).sort(), ["lead_cycle_h1", "lead_cycle_h5"], langue);
    assert.ok(choix.every((x) => !x.desactive && x.decrit === undefined), langue);
    assert.ok(!html.includes(catalogues[langue]["tableau.form.h5RealUnavailable"]), langue);
    assert.doesNotMatch(html, /choix-desactive/, langue);
  }
});

test("no request is made for hypothesis 5 on real data: the form's decision function sends nothing for it, whatever was chosen", () => {
  const h5: GraphiqueDeFiche = "lead_cycle_h5";
  const h1: GraphiqueDeFiche = "lead_cycle_h1";
  assert.deepEqual([...graphiquesOfferts(true)], [h1]);
  assert.deepEqual([...graphiquesOfferts(false)].sort(), [h1, h5]);
  assert.equal(demandeDeFiche(h5, false, true), undefined);
  assert.equal(demandeDeFiche(h1, false, true), h1);
  assert.equal(demandeDeFiche(h5, false, false), h5);
  // Nothing is sent without a choice or without a team, on either dataset.
  assert.equal(demandeDeFiche(null, false, false), undefined);
  assert.equal(demandeDeFiche(h1, true, false), undefined);
  assert.equal(demandeDeFiche(h1, true, true), undefined);
});

test("the real dashboard and its form hold no link to the synthetic dataset (Q157 (a), R-20261101-41)", () => {
  for (const langue of LANGUES) {
    const html = tableau("real", langue, { genre: "formulaire" });
    assert.doesNotMatch(html, /href="[^"]*(synthetic|dataset|jeu)/i, langue);
  }
});

// ---- the disabled choice, a component of the catalogue (D17) ----------------------------------------------------------------------

function choix(langue: Langue): string {
  return propre(rendre(h(ChoixDesactive, { nom: "g", valeur: "lead_cycle_h5", libelle: "conviction.nav.lead_cycle_h5", raison: "tableau.form.h5RealUnavailable" }), langue));
}

test("the disabled choice draws a disabled radio with its label and its reason linked by aria-describedby, in both languages", () => {
  for (const langue of LANGUES) {
    const c = catalogues[langue];
    const html = choix(langue);
    const [radio, ...autres] = choixRadio(html);
    assert.equal(autres.length, 0, langue);
    assert.equal(radio.valeur, "lead_cycle_h5");
    assert.equal(radio.desactive, true, langue);
    assert.ok(radio.decrit !== undefined && html.includes(`id="${radio.decrit}" class="choix-raison">${c["tableau.form.h5RealUnavailable"]}<`), langue);
    assert.ok(html.includes(c["conviction.nav.lead_cycle_h5"]), langue);
    // The reason is outside the label, so the option's accessible name stays its own label.
    assert.match(html, /<label[^>]*>[^<]*<input[^>]*\/>[^<]*<\/label>/, langue);
    assert.ok(!/<label[^>]*>[^]*choix-raison[^]*<\/label>/.test(html), langue);
    // Never checked, never a style prop.
    assert.doesNotMatch(html, /\bchecked\b|\bstyle=/, langue);
  }
});

test("two disabled choices on one page point each at its own reason", () => {
  const deux = rendre(
    h("div", null, h(ChoixDesactive, { nom: "g", valeur: "a", libelle: "conviction.nav.lead_cycle_h5", raison: "tableau.form.h5RealUnavailable" }), h(ChoixDesactive, { nom: "g", valeur: "b", libelle: "conviction.nav.lead_cycle_h1", raison: "tableau.form.h5RealUnavailable" })),
    "en",
  );
  const [a, b] = choixRadio(deux);
  assert.ok(a.decrit !== undefined && b.decrit !== undefined && a.decrit !== b.decrit);
  assert.ok(deux.includes(`id="${a.decrit}"`) && deux.includes(`id="${b.decrit}"`));
});

test("the disabled choice reads role-named tokens only: no literal colour, no style prop, a stylesheet rule made of variables", () => {
  const source = readFileSync(`${FRONT}src/composants/ChoixDesactive.ts`, "utf8").split("\n").filter((l) => !l.trimStart().startsWith("//")).join("\n");
  assert.doesNotMatch(source, /#[0-9a-fA-F]{3,8}\b|\bstyle\b|rgb\(|hsl\(/);
  const css = readFileSync(`${FRONT}src/styles/styles.css`, "utf8");
  for (const classe of [".choix-desactive", ".choix-raison"]) {
    const regle = new RegExp(`${classe.replace(".", "\\.")}\\s*\\{([^}]*)\\}`).exec(css);
    assert.ok(regle !== null, `règle absente : ${classe}`);
    assert.doesNotMatch(regle[1], /#[0-9a-fA-F]{3,8}\b|\d+px|rgb\(|hsl\(/, classe);
  }
});

// ---- the catalogue of the components (task 5.5) ----------------------------------------------------------------------------------

test("the catalogue page shows the disabled choice with its reason, in both languages", () => {
  const source = JSON.parse(readFileSync(`${FRONT}src/styles/tokens.json`, "utf8")) as Jetons;
  const page = genererCatalogue(source, "");
  assert.ok(page.includes("Disabled choice with its reason"));
  assert.ok(page.includes('class="choix-desactive"'));
  for (const langue of LANGUES) {
    assert.ok(propre(page).includes(`class="choix-raison">${catalogues[langue]["tableau.form.h5RealUnavailable"]}<`), langue);
  }
});

// ---- the labels (D13, D18) -------------------------------------------------------------------------------------------------------

test("the only new label of the lot is the reason under hypothesis 5, with the texts the author validated (R-20261101-39)", () => {
  assert.equal(catalogues.en["tableau.form.h5RealUnavailable"], "Offered on the synthetic dataset only: its reading on real data is still to be validated.");
  assert.equal(catalogues.fr["tableau.form.h5RealUnavailable"], "Proposée sur le jeu synthétique seulement : sa lecture sur données réelles reste à valider.");
});

test("no label of decision 16 is created: the keys that speak of real data or of counts are the closed list of the design, and one key at most carries the code real_counts_not_shown", () => {
  const permises = new Set(["banner.realReduced", "tableau.form.h5RealUnavailable", "state.real_counts_not_shown"]);
  for (const [langue, catalogue] of Object.entries(catalogues)) {
    const trouvees = Object.keys(catalogue).filter((cle) => /real|counts/i.test(cle));
    assert.deepEqual(trouvees.filter((cle) => !permises.has(cle)), [], `libellé de la décision 16 (${langue})`);
    assert.ok(trouvees.filter((cle) => cle.endsWith("real_counts_not_shown")).length <= 1, `une clé par code (${langue})`);
    // When the key exists it carries the labels of D29, validated by R-20261031-58.
    if ("state.real_counts_not_shown" in catalogue) {
      assert.equal(catalogue["state.real_counts_not_shown"], langue === "en" ? "Counts are not shown on real data." : "Les comptes ne sont pas affichés sur les données réelles.");
    }
  }
});
