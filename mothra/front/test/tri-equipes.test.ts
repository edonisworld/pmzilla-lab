// Audit #629, L3-08 (Q238, R-20261107-30): names off, the series of the dashboard answer come in the order of the identifiers, never of the names.
import assert from "node:assert/strict";
import { test } from "node:test";

import { servirTableau, tableauLeadCycle } from "@mothra/contract";
import { identifiantEquipe } from "@mothra/contract/equipe";

import { CONFIG_ECHANTILLON, DATE_DONNEES, EQUIPES, MODE_SYNTHETIQUE, reponseVueLeadCycle } from "./reponses-contrat.ts";

test("names off: the series come in the order of the identifiers, not of the names", () => {
  const plein = tableauLeadCycle(reponseVueLeadCycle(), CONFIG_ECHANTILLON, DATE_DONNEES, identifiantEquipe);
  const ids = servirTableau(plein, MODE_SYNTHETIQUE).teams.map((s) => s.teamId);
  assert.deepEqual(ids, EQUIPES.map((n) => identifiantEquipe(n)).sort());
  assert.notDeepEqual(ids, EQUIPES.map((n) => identifiantEquipe(n)), "précondition : l'ordre des identifiants n'est pas celui des noms (sinon le test ne prouve rien)");
});
