// Task 16.2 (design D17, D34), database cases: the marker lookup under the view-limited role, on the throwaway database only. The synthetic
// dataset loader creates the marker; a database without it is a real one. Skipped, never failed, without DBTEST_PORT (the author runs them).
import assert from "node:assert/strict";
import { after, before, test } from "node:test";

import { VARIABLES, lireEnvironnement } from "../../src/config/index.ts";
import { marqueurPostgres } from "../../src/db/base.ts";
import { demarrer } from "../../src/demarrage.ts";
import { RefusDemarrage } from "../../src/refus.ts";
import { AccesFictif, CHEMIN_CONTRAT, LISTE_EQUIPES_FICTIVE, LISTE_SENSIBLE_FICTIVE, sautBaseJetable } from "../aide.ts";
import { creerBaseJetable } from "./base-jetable.ts";
import type { BaseJetable } from "./base-jetable.ts";

const saut = sautBaseJetable();
let base: BaseJetable | null = null;

before(async () => {
  if (saut === false) {
    base = await creerBaseJetable(lireEnvironnement());
  }
});

after(async () => {
  await base?.supprimer();
});

function jetable(): BaseJetable {
  assert.ok(base !== null, "the throwaway database was not created");
  return base;
}

test("after the loader, the marker is found under the view role; once dropped, it is not", { skip: saut }, async () => {
  assert.equal(await marqueurPostgres(jetable().configuration()), true);
  await jetable().retirerMarqueur();
  assert.equal(await marqueurPostgres(jetable().configuration()), false);
});

test("the start check agrees with the database: synthetic without the marker is refused, exit 4", { skip: saut }, async () => {
  await jetable().retirerMarqueur();
  await assert.rejects(
    demarrer(
      {
        MOTHRA_DB_HOST: "127.0.0.1",
        MOTHRA_DB_NAME: jetable().nom,
        MOTHRA_DATASET: "synthetic",
        DBTEST_PORT: String(jetable().port),
        [VARIABLES.secretBase]: jetable().secret,
        [VARIABLES.secretStockage]: jetable().secretStockage,
        // The two lists of names (task 18.3): fake lists of invented names.
        [VARIABLES.nomsSensibles]: LISTE_SENSIBLE_FICTIVE,
        [VARIABLES.nomsEquipes]: LISTE_EQUIPES_FICTIVE,
      },
      { cheminContrat: CHEMIN_CONTRAT, creerAcces: () => new AccesFictif(), journal: false, avertir: () => {} },
    ),
    (erreur: unknown) => erreur instanceof RefusDemarrage && erreur.code === "DATASET_MISMATCH" && erreur.sortie === 4,
  );
});
