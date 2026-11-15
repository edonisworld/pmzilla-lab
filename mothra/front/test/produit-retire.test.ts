// R-20261031-61 (Q110 a) and R-20261031-66: the second screen has no product option while no view has a product row. It opens on the first
// team in the neutral order of the opaque identifier (never according to a value), and an address that asks for the product, or for an
// identifier the answer does not hold, falls back to that team. The dashboard answers AND the panel answers come from the contract's
// functions applied to synthetic rows of the views (reponses-contrat.ts): no hand-written answer, no SOURCE_PANNEAUX_SIMULEE.
import assert from "node:assert/strict";
import { test } from "node:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import type { ModeDonnees, ReponseLeadCycle, ReponseLeadCycleReduite } from "@mothra/contract";
import { identifiantEquipe } from "@mothra/contract/equipe";
import { CODES_PANNEAUX } from "@mothra/contract/listes-fiche";

import { Application } from "../src/Application.ts";
import { trimestresDisponibles } from "../src/api/filtres.ts";
import { optionsLeadCycle } from "../src/api/leadCycle.ts";
import { optionsPanneau } from "../src/api/panneaux.ts";
import type { SourceLeadCycle } from "../src/api/leadCycle.ts";
import { MODE_REEL, MODE_SYNTHETIQUE, reponseServie, sourcePanneauxContrat } from "./reponses-contrat.ts";

const sansFiltre = { team: undefined, from: undefined, to: undefined };

function source(reponse: ReponseLeadCycle | ReponseLeadCycleReduite): SourceLeadCycle {
  return { lire: async () => reponse, creer: async () => ({ id: "x", state: "draft" }), simulee: false };
}

async function ecran(reponse: ReponseLeadCycle | ReponseLeadCycleReduite, mode: ModeDonnees, team: string | undefined): Promise<string> {
  const client = new QueryClient();
  const tableau = source(reponse);
  await client.prefetchQuery(optionsLeadCycle(tableau.lire));
  // The panels are read with the filters the page resolves: the team of the address if the answer holds it, else the first identifier.
  const identifiants = reponse.teams.map((e) => e.teamId).sort((a, b) => a.localeCompare(b));
  const trimestres = trimestresDisponibles(reponse);
  const panneaux = sourcePanneauxContrat(mode);
  const filtres = { team: team !== undefined && identifiants.includes(team) ? team : identifiants[0], from: trimestres.at(0), to: trimestres.at(-1) };
  for (const code of CODES_PANNEAUX) await client.prefetchQuery(optionsPanneau(code, filtres, panneaux.lire));
  return renderToStaticMarkup(
    h(QueryClientProvider, { client }, h(Application, { tableau, panneaux, ecranInitial: "tableau", filtresInitiaux: { ...sansFiltre, team } })),
  );
}

const SELECT = /<select[^>]*name="team"[^>]*>([\s\S]*?)<\/select>/;
const options = (html: string): string[] => [...(SELECT.exec(html)?.[1] ?? "").matchAll(/<option value="([^"]*)"/g)].map((o) => o[1]);
const choisie = (html: string): string | undefined => /<option value="([^"]*)" selected=""/.exec(SELECT.exec(html)?.[1] ?? "")?.[1];

const CAS: ReadonlyArray<readonly [string, ModeDonnees]> = [
  ["complete answer", MODE_SYNTHETIQUE],
  ["reduced answer of real data", MODE_REEL],
];

for (const [nom, mode] of CAS) {
  const reponse = reponseServie(mode);
  const identifiants = reponse.teams.map((e) => e.teamId).sort((a, b) => a.localeCompare(b));

  test(`${nom}: the team choice offers the identifiers in the neutral order and no product option`, async () => {
    const html = await ecran(reponse, mode, undefined);
    assert.deepEqual(options(html), identifiants);
    assert.doesNotMatch(html, /<option value="">/);
  });

  test(`${nom}: without a team in the address the screen opens on the first identifier, and an address that asks for the product is the same`, async () => {
    const html = await ecran(reponse, mode, undefined);
    assert.equal(choisie(html), identifiants[0]);
    assert.equal(html, await ecran(reponse, mode, identifiants[0]));
  });

  test(`${nom}: an identifier the answer does not hold falls back to the first team`, async () => {
    const inconnu = identifiantEquipe("team-unknown");
    assert.ok(!identifiants.includes(inconnu));
    assert.equal(await ecran(reponse, mode, inconnu), await ecran(reponse, mode, identifiants[0]));
  });

  test(`${nom}: a team chosen in the address is kept, and the screen differs from the one of the first team`, async () => {
    const html = await ecran(reponse, mode, identifiants[1]);
    assert.equal(choisie(html), identifiants[1]);
    assert.notEqual(html, await ecran(reponse, mode, identifiants[0]));
  });
}

test("on the first team, the panels of the contract's functions are the four panels, and the product ones are signalled as served for the product", async () => {
  const reponse = reponseServie(MODE_SYNTHETIQUE);
  const html = await ecran(reponse, MODE_SYNTHETIQUE, undefined);
  assert.deepEqual([...html.matchAll(/data-panel="([a-z-]+)"/g)].map((m) => m[1]), ["stories-inout", "correction-share", "defects-inout", "blocked-share"]);
  // defects-inout and correction-share are product panels (D35): asked for a team, they are served for the product and say so; the two others are not
  assert.equal((html.match(/data-signal="served_scope_differs"/g) ?? []).length, 2);
});
