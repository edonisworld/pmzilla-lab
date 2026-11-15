// Task 19.3 (rest, review B4), design D35 (R-20261029-09 Q1 and Q3): wherever the sheet shows the cycle time,
// `cycle_time_includes_ready_queue` is next to it; wherever it shows the blocked share, `blocked_share_current_links` and
// `indirect_indicator` are next to it, never only on the method face. The codes below are the contract's own.
import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";

import { Fiche } from "../src/composants/Fiche.ts";
import { catalogues } from "../src/i18n/langue.ts";
import type { Langue } from "../src/i18n/langue.ts";
import { ficheSimulee } from "./fiche-simulee.ts";
import { rendre, texte as texteDuMarquage } from "./rendu.ts";

const en = catalogues.en;
const fr = catalogues.fr;

function texte(html: string): string {
  return texteDuMarquage(html).replaceAll("&#x27;", "'");
}

const MENTIONS = ["cycle_time_includes_ready_queue", "blocked_share_current_links", "indirect_indicator"] as const;

function ecran(modifs: Parameters<typeof ficheSimulee>[0], langue: Langue): string {
  return rendre(h(Fiche, { fiche: ficheSimulee(modifs), methodeOuverte: true }), langue);
}

// The markup of the cell or the block that holds a marker, from the nearest opening tag of `balise` to its closing tag.
function bloc(html: string, marque: string, balise: string): string {
  const i = html.indexOf(marque);
  assert.ok(i >= 0, `marque absente : ${marque}`);
  return html.slice(html.lastIndexOf(`<${balise}`, i), html.indexOf(`</${balise}>`, i));
}

function mentionsDans(html: string): string[] {
  return [...html.matchAll(/data-mention="([a-z_]+)"/g)].map((m) => m[1]);
}

test("the three mentions have a label in both languages, those of D29", () => {
  assert.equal(en["fiche.mention.cycle_time_includes_ready_queue"], "Time in the ready queue counts in the cycle time.");
  assert.equal(fr["fiche.mention.cycle_time_includes_ready_queue"], "Le temps en file prête compte dans le cycle time.");
  assert.equal(en["fiche.mention.blocked_share_current_links"], "Links in their current state, without history.");
  assert.equal(fr["fiche.mention.blocked_share_current_links"], "Liens à leur état actuel, sans historique.");
  assert.equal(en["fiche.mention.indirect_indicator"], "Indirect indicator.");
  assert.equal(fr["fiche.mention.indirect_indicator"], "Indicateur indirect.");
});

test("the management face shows the cycle time mention next to the chart, in each language", () => {
  const anglais = ecran({}, "en");
  const zone = bloc(anglais, 'data-emplacement="graphique"', "div");
  assert.ok(anglais.indexOf('data-mention="cycle_time_includes_ready_queue"') > anglais.indexOf(zone));
  assert.match(texte(anglais), /Time in the ready queue counts in the cycle time/);
  assert.match(texte(ecran({}, "fr")), /Le temps en file prête compte dans le cycle time/);
  // on the management face, before the verdict zone: never only on the method face (methodeOuverte is false here)
  const direction = anglais.slice(anglais.indexOf('class="fiche-direction"'), anglais.indexOf('class="fiche-verdict-zone"'));
  assert.deepEqual(mentionsDans(direction), ["cycle_time_includes_ready_queue"]);
  assert.deepEqual(mentionsDans(rendre(h(Fiche, { fiche: ficheSimulee() }), "en")).slice(0, 1), ["cycle_time_includes_ready_queue"]);
});

test("the cycle time measures of the method face carry the cycle time mention; a measure of another kind does not", () => {
  const html = ecran(
    {
      method: {
        ...ficheSimulee().method,
        maskedCells: [
          { measure: "cycle_median_days@2026-04-01", cell: { state: "masked", threshold: 5 } },
          { measure: "lead_median_days@2026-04-01", cell: { state: "masked", threshold: 5 } },
        ],
        insufficientSamples: ["cycle_p85_days@pooled_year"],
      },
    },
    "en",
  );
  const masquees = bloc(html, 'data-tableau="masquees"', "table");
  const lignes = masquees.split("<tr>").filter((l) => /Median (cycle|lead) time/.test(l));
  assert.equal(lignes.length, 2);
  assert.deepEqual(mentionsDans(lignes.find((l) => /Median cycle time/.test(l)) ?? ""), ["cycle_time_includes_ready_queue"]);
  assert.deepEqual(mentionsDans(lignes.find((l) => /Median lead time/.test(l)) ?? ""), []);
  assert.deepEqual(mentionsDans(bloc(html, 'data-tableau="insuffisants"', "table")), ["cycle_time_includes_ready_queue"]);
});

test("the blocked share is never shown without its two labels, on the management face, with its measure", () => {
  for (const langue of ["en", "fr"] as const) {
    const html = ecran(
      {
        explanations: [
          { name: "unplanned_work", state: "not_measurable", reason: "defects_without_team" },
          { name: "capacity", state: "ruled_out" },
          { name: "dependencies", state: "not_ruled_out", reason: "no_adopted_threshold", measure: { state: "value", value: 18 } },
        ],
      },
      langue,
    );
    const ligne = bloc(html, 'data-explication="dependencies"', "li");
    assert.deepEqual(mentionsDans(ligne).sort(), ["blocked_share_current_links", "indirect_indicator"], langue);
    assert.match(texte(ligne), /18/);
    const catalogue = langue === "en" ? en : fr;
    assert.match(texte(ligne), new RegExp(catalogue["fiche.mention.blocked_share_current_links"].slice(0, 12)));
    assert.match(texte(ligne), new RegExp(catalogue["fiche.mention.indirect_indicator"].slice(0, 10)));
  }
});

test("a masked blocked share keeps both labels; the other explanations carry no blocked-share mention", () => {
  const html = ecran(
    {
      explanations: [
        { name: "unplanned_work", state: "not_measurable", reason: "defects_without_team" },
        { name: "capacity", state: "not_ruled_out", reason: "no_adopted_threshold" },
        { name: "dependencies", state: "not_measurable", reason: "masked", measure: { state: "masked", threshold: 5 } },
      ],
    },
    "en",
  );
  assert.deepEqual(mentionsDans(bloc(html, 'data-explication="dependencies"', "li")).sort(), ["blocked_share_current_links", "indirect_indicator"]);
  assert.deepEqual(mentionsDans(bloc(html, 'data-explication="capacity"', "li")), []);
  assert.deepEqual(mentionsDans(bloc(html, 'data-explication="unplanned_work"', "li")), []);
});

test("the blocked share measure of the method face carries both labels; a sheet without any of these measures carries no blocked-share mention", () => {
  const html = ecran(
    { method: { ...ficheSimulee().method, maskedCells: [{ measure: "blocked_share@2026-07-01", cell: { state: "masked", threshold: 5 } }], insufficientSamples: [] } },
    "fr",
  );
  assert.deepEqual(mentionsDans(bloc(html, 'data-tableau="masquees"', "table")).sort(), ["blocked_share_current_links", "indirect_indicator"]);
  const sans = ecran(
    { explanations: [{ name: "unplanned_work", state: "ruled_out" }], method: { ...ficheSimulee().method, maskedCells: [], insufficientSamples: [] } },
    "en",
  );
  assert.deepEqual(mentionsDans(sans).filter((m) => m !== "cycle_time_includes_ready_queue"), []);
});

test("a blocked share without one of its two labels fails: the pair is checked on every line that shows the measure", () => {
  const html = ecran(
    { explanations: [{ name: "dependencies", state: "not_ruled_out", reason: "no_adopted_threshold", measure: { state: "value", value: 7 } }] },
    "en",
  );
  const ligne = bloc(html, 'data-explication="dependencies"', "li");
  const manque = (retire: string) => mentionsDans(ligne.replace(new RegExp(`<[^>]*data-mention="${retire}"[^>]*>.*?</small>`), ""));
  assert.notDeepEqual(manque("indirect_indicator").sort(), ["blocked_share_current_links", "indirect_indicator"]);
  assert.notDeepEqual(manque("blocked_share_current_links").sort(), ["blocked_share_current_links", "indirect_indicator"]);
  assert.deepEqual(mentionsDans(ligne).sort(), ["blocked_share_current_links", "indirect_indicator"]);
  assert.ok(MENTIONS.every((m) => `fiche.mention.${m}` in en && `fiche.mention.${m}` in fr));
});
