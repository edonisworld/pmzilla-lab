// Task 18.1 (design D21, ADR 0006): the threshold history through the storage connection, on the throwaway database only. Skipped, never
// failed, without DBTEST_PORT (same guard as stockage.test.ts). Written for the author's run (tools/dbtest.sh), never run by a session.
import assert from "node:assert/strict";
import { after, before, test } from "node:test";

import { lireEnvironnement } from "../../src/config/index.ts";
import { creerAccesStockage } from "../../src/db/stockage.ts";
import { sautBaseJetable } from "../aide.ts";
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

test("a threshold is inserted with its date and author and read back in date order, as a date text and a number", { skip: saut }, async () => {
  assert.ok(base !== null, "the throwaway database was not created");
  const acces = creerAccesStockage(base.configuration());
  try {
    await acces.ajouterSeuil({ code: "h5_band", value: 0.3, setOn: "2026-11-02", setBy: "author-1" });
    await acces.ajouterSeuil({ code: "h5_band", value: 0.2, setOn: "2026-10-30", setBy: "author-1" });
    const lus = await acces.seuils();
    assert.deepEqual(
      lus.map((s) => [s.code, s.value, s.setOn, s.setBy]),
      [
        ["h5_band", 0.2, "2026-10-30", "author-1"],
        ["h5_band", 0.3, "2026-11-02", "author-1"],
      ],
    );
  } finally {
    await acces.fermer();
  }
});

test("a code the table refuses fails without detail", { skip: saut }, async () => {
  assert.ok(base !== null, "the throwaway database was not created");
  const acces = creerAccesStockage(base.configuration());
  try {
    await assert.rejects(acces.ajouterSeuil({ code: "Not A Code", value: 1, setOn: "2026-10-30", setBy: "author-1" }), (e: Error) => e.name === "BaseIndisponible");
  } finally {
    await acces.fermer();
  }
});
