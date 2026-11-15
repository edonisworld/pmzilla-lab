// Audit #629, L3-08 (Q238, R-20261107-30): the series of the dashboard answer are ordered by name when the names are on (and by identifier when
// they are off: tri-equipes.test.ts). The service layer (`servirTableau`) decides.
import assert from "node:assert/strict";
import { test } from "node:test";

import { servirTableau, tableauLeadCycle } from "@mothra/contract";
import { identifiantEquipe } from "@mothra/contract/equipe";

import { CONFIG_ECHANTILLON, DATE_DONNEES, EQUIPES, MODE_SYNTHETIQUE, reponseVueLeadCycle } from "./reponses-contrat.ts";

test("names on: the series come in the order of the names", () => {
  const plein = tableauLeadCycle(reponseVueLeadCycle(), CONFIG_ECHANTILLON, DATE_DONNEES, identifiantEquipe);
  const noms = servirTableau(plein, { ...MODE_SYNTHETIQUE, afficherNoms: true }).teams.map((s) => ("team" in s ? s.team : undefined));
  assert.deepEqual(noms, [...EQUIPES]);
});
