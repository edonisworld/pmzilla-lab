// Task 16.2 (design D17, D34): the start check of the dataset by the database marker. After the configuration and the environment checks,
// before listening, the server asks the database, under the view-limited role, whether `flow.synthetic_dataset_marker()` exists (a
// catalogue lookup, no table read) and compares it with MOTHRA_DATASET. The fake lookup below stands for the database: no connection here.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { demarrer } from "../src/demarrage.ts";
import type { OptionsDemarrage } from "../src/demarrage.ts";
import { REQUETE_MARQUEUR } from "../src/db/base.ts";
import { RefusDemarrage } from "../src/refus.ts";
import { AccesFictif, CHEMIN_CONTRAT, envMinimal } from "./aide.ts";

interface Essai {
  refus: RefusDemarrage | null;
  consultations: number;
  fermetures: number;
}

async function essai(env: Record<string, string | undefined>, marqueur: boolean, options: Partial<OptionsDemarrage> = {}): Promise<Essai> {
  const compte = { consultations: 0, fermetures: 0 };
  try {
    const serveur = await demarrer(env, {
      cheminContrat: CHEMIN_CONTRAT,
      creerAcces: () => new AccesFictif(),
      creerStockage: () => ({ roleCourant: async () => "x", fermer: async () => {} }),
      lireMarqueur: async () => {
        compte.consultations += 1;
        return marqueur;
      },
      journal: false,
      avertir: () => {},
      ...options,
    });
    await serveur.app.close();
  } catch (erreur) {
    assert.ok(erreur instanceof RefusDemarrage, "a start refusal was expected");
    return { refus: erreur, ...compte };
  }
  return { refus: null, ...compte };
}

test("synthetic on a database without the marker is refused: exit 4, DATASET_MISMATCH, no value", async () => {
  const { refus } = await essai(envMinimal({ MOTHRA_DATASET: "synthetic" }), false);
  assert.equal(refus?.code, "DATASET_MISMATCH");
  assert.equal(refus?.sortie, 4);
  assert.equal(refus?.phrase, "mothra: refused (DATASET_MISMATCH)");
  assert.ok(!String(refus?.phrase).includes("mothra_test"), "the database name is not in the refusal");
  assert.ok(!String(refus?.phrase).includes("synthetic"), "no value in the refusal");
});

test("real on a database with the marker is refused with the same refusal", async () => {
  const { refus } = await essai(envMinimal({ MOTHRA_DATASET: "real" }), true);
  assert.equal(refus?.code, "DATASET_MISMATCH");
  assert.equal(refus?.sortie, 4);
  assert.equal(refus?.phrase, "mothra: refused (DATASET_MISMATCH)");
});

test("synthetic with the marker, and real without it, start", async () => {
  assert.equal((await essai(envMinimal({ MOTHRA_DATASET: "synthetic" }), true)).refus, null);
  assert.equal((await essai(envMinimal({ MOTHRA_DATASET: "real" }), false)).refus, null);
});

test("the check never listens: neither a refusal nor an agreement leaves a listening server (listening is main's step, after the check)", async () => {
  let ecoute: boolean | null = null;
  await essai(envMinimal({ MOTHRA_DATASET: "synthetic" }), true, {
    creerAcces: () => new AccesFictif(),
    avertir: () => {},
    journal: false,
    // The server object is only reachable through the result of demarrer: checked directly below.
  });
  const serveur = await demarrer(envMinimal(), {
    cheminContrat: CHEMIN_CONTRAT,
    creerAcces: () => new AccesFictif(),
    creerStockage: () => ({ roleCourant: async () => "x", fermer: async () => {} }),
    lireMarqueur: async () => true,
    journal: false,
    avertir: () => {},
  });
  ecoute = serveur.app.server.listening;
  await serveur.app.close();
  assert.equal(ecoute, false);
  const refuse = await essai(envMinimal(), false);
  assert.equal(refuse.refus?.code, "DATASET_MISMATCH");
});

test("the lookup happens after the configuration and the environment checks, and only when they pass", async () => {
  for (const [extra, code] of [
    [{ MOTHRA_PORT: "x" }, "SETTING_INVALID"],
    [{ MOTHRA_DATASET: "demo" }, "SETTING_INVALID"],
    [{ MOTHRA_HOST: "0.0.0.0" }, "NOT_LOOPBACK"],
    [{ CLAUDECODE: "1" }, "SESSION_WITHOUT_THROWAWAY_DB"],
  ] as const) {
    const { refus, consultations } = await essai(envMinimal({ ...extra }), false);
    assert.equal(refus?.code, code, JSON.stringify(extra));
    assert.equal(consultations, 0, JSON.stringify(extra));
  }
  const missing = envMinimal();
  delete missing.MOTHRA_DATASET;
  const { refus, consultations } = await essai(missing, false);
  assert.equal(refus?.code, "SETTING_MISSING");
  assert.equal(consultations, 0);
});

test("the lookup is made once", async () => {
  assert.equal((await essai(envMinimal(), true)).consultations, 1);
});

test("the marker lookup reads no table: a catalogue function call, no FROM, no schema table", () => {
  assert.match(REQUETE_MARQUEUR, /to_regprocedure\('flow\.synthetic_dataset_marker\(\)'\)/);
  assert.ok(!/\bFROM\b|\bJOIN\b|\bSELECT\s+\*/i.test(REQUETE_MARQUEUR), REQUETE_MARQUEUR);
});

test("the lookup runs under the view-limited role, not the storage role, and the entry of the server calls the check before listening", () => {
  const base = readFileSync(new URL("../src/db/base.ts", import.meta.url), "utf8");
  assert.match(base, /marqueurPostgres/);
  const main = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");
  assert.ok(main.indexOf("demarrer(") !== -1 && main.indexOf("demarrer(") < main.indexOf("app.listen"), "the start check precedes the listening");
});
