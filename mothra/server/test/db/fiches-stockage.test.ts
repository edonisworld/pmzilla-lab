// Task 18.1 (design D20, D29, ADR 0006): the sheet depot through the storage connection (migrations 0024 and 0027), on the throwaway database
// only. Skipped, never failed, without DBTEST_PORT (same guard as stockage.test.ts). Written for the author's run (tools/dbtest.sh), never run
// by a session. Invented identifiers and figures.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";

import { lireEnvironnement } from "../../src/config/index.ts";
import pg from "pg";

import { creerAccesStockage, parametresStockage } from "../../src/db/stockage.ts";
import { empreinte } from "../../src/fiches/depot.ts";
import type { ContenuFige, CorpsCalcule } from "../../src/fiches/depot.ts";
import { sautBaseJetable } from "../aide.ts";
import { corpsSynthetique } from "../depot-memoire.ts";
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

function acces() {
  assert.ok(base !== null, "the throwaway database was not created");
  return creerAccesStockage(base.configuration());
}

const ENTREE = { chart: "lead-cycle", scope: "team-a", dataDate: "2026-10-01", createdBy: "agile-lead-1" };

// The frozen content of a sheet: the computed body with its effect, cause and question.
const figee = (corps: CorpsCalcule): ContenuFige => ({
  ...corps,
  effect: { text: "Effect.", lang: "en" },
  cause: { text: "Cause.", lang: "en" },
  managementQuestion: "predictability",
});

test("a sheet is created with its context and texts, and read back as it was written", { skip: saut }, async () => {
  const depot = acces();
  try {
    const id = await depot.creer({
      ...ENTREE,
      managementQuestion: "predictability",
      effect: { text: "Delivery slowed down.", lang: "en" },
      cause: { text: "Les relectures attendent.", lang: "fr" },
    });
    const fiche = await depot.lire(id);
    assert.deepEqual(fiche, {
      id,
      chart: "lead-cycle",
      scope: "team-a",
      dataDate: "2026-10-01",
      state: "draft",
      managementQuestion: "predictability",
      effect: { text: "Delivery slowed down.", lang: "en" },
      cause: { text: "Les relectures attendent.", lang: "fr" },
      createdBy: "agile-lead-1",
      reviewedBy: undefined,
    });
  } finally {
    await depot.fermer();
  }
});

test("a draft without question, effect or cause is stored; an unknown or non-numeric identifier reads as null", { skip: saut }, async () => {
  const depot = acces();
  try {
    const fiche = await depot.lire(await depot.creer(ENTREE));
    assert.equal(fiche?.managementQuestion, undefined);
    assert.equal(fiche?.effect, undefined);
    assert.equal(fiche?.cause, undefined);
    assert.equal(await depot.lire("999999"), null);
    assert.equal(await depot.lire("1; DROP TABLE sheets"), null);
  } finally {
    await depot.fermer();
  }
});

test("a review sets the state and the reviewer; a value the table refuses is a failure without detail", { skip: saut }, async () => {
  const depot = acces();
  try {
    const id = await depot.creer({ ...ENTREE, managementQuestion: "scope_growth" });
    await depot.relire(id, "agile-lead-2");
    const fiche = await depot.lire(id);
    assert.equal(fiche?.state, "reviewed");
    assert.equal(fiche?.reviewedBy, "agile-lead-2");
    await assert.rejects(depot.creer({ ...ENTREE, scope: "Team A" }), (e: Error) => e.name === "BaseIndisponible");
  } finally {
    await depot.fermer();
  }
});

test("a publication freezes the content with its fingerprint, as the next version, and the sheet reads as published", { skip: saut }, async () => {
  const depot = acces();
  try {
    const id = await depot.creer({ ...ENTREE, managementQuestion: "predictability", effect: { text: "E.", lang: "en" }, cause: { text: "C.", lang: "en" } });
    await depot.relire(id, "agile-lead-2");
    const contenu = figee(corpsSynthetique());
    const publie = await depot.publier(id, { content: contenu, fingerprint: empreinte(contenu), publishedBy: "agile-lead-2" });
    assert.equal(publie.version, 1);
    assert.match(publie.publishedOn, /^\d{4}-\d{2}-\d{2}$/);
    const fiche = await depot.lire(id);
    assert.equal(fiche?.state, "published");
    assert.equal(fiche?.published?.version, 1);
    assert.equal(fiche?.published?.fingerprint, empreinte(contenu));
    assert.deepEqual(fiche?.published?.content, JSON.parse(JSON.stringify(contenu)));
    // A review of a published sheet changes nothing.
    await depot.relire(id, "agile-lead-3");
    assert.equal((await depot.lire(id))?.state, "published");
    // A second freeze of the same sheet is refused (the state is checked again in the transaction): no second version.
    await assert.rejects(depot.publier(id, { content: contenu, fingerprint: empreinte(contenu), publishedBy: "agile-lead-2" }), (e: Error) => e.name === "FicheDejaPubliee");
    assert.equal((await depot.lire(id))?.published?.version, 1);
  } finally {
    await depot.fermer();
  }
});

test("only a reviewed sheet is frozen: a draft is refused with no row inserted, and two freezes in a race give one version", { skip: saut }, async () => {
  const depot = acces();
  try {
    const brouillon = await depot.creer({ ...ENTREE, managementQuestion: "predictability", effect: { text: "E.", lang: "en" }, cause: { text: "C.", lang: "en" } });
    const contenu = figee(corpsSynthetique());
    await assert.rejects(depot.publier(brouillon, { content: contenu, fingerprint: empreinte(contenu), publishedBy: "agile-lead-1" }), (e: Error) => e.name === "FicheDejaPubliee");
    assert.equal((await depot.lire(brouillon))?.published, undefined);
    assert.equal((await depot.lire(brouillon))?.state, "draft");
    const relue = await depot.creer({ ...ENTREE, managementQuestion: "predictability", effect: { text: "E.", lang: "en" }, cause: { text: "C.", lang: "en" } });
    await depot.relire(relue, "agile-lead-2");
    const issues = await Promise.allSettled([
      depot.publier(relue, { content: contenu, fingerprint: empreinte(contenu), publishedBy: "agile-lead-1" }),
      depot.publier(relue, { content: contenu, fingerprint: empreinte(contenu), publishedBy: "agile-lead-1" }),
    ]);
    assert.equal(issues.filter((i) => i.status === "fulfilled").length, 1);
    assert.equal((await depot.lire(relue))?.published?.version, 1);
  } finally {
    await depot.fermer();
  }
});

test("a change of the table after the publication changes neither the frozen content nor its fingerprint, effect, cause and question included", { skip: saut }, async () => {
  assert.ok(base !== null, "the throwaway database was not created");
  const depot = acces();
  const client = new pg.Client(parametresStockage(base.configuration()));
  await client.connect();
  try {
    const id = await depot.creer({ ...ENTREE, managementQuestion: "predictability", effect: { text: "Effect.", lang: "en" }, cause: { text: "Cause.", lang: "en" } });
    await depot.relire(id, "agile-lead-2");
    const contenu = figee(corpsSynthetique());
    const empreinteGelee = empreinte(contenu);
    await depot.publier(id, { content: contenu, fingerprint: empreinteGelee, publishedBy: "agile-lead-1" });
    // The table moves (the storage role may update `sheets`): the frozen version, in its own table, does not.
    await client.query("UPDATE mothra.sheets SET effect_text = 'Changed.', cause_text = 'Changed.', management_question = 'scope_growth' WHERE id = $1", [id]);
    const fiche = await depot.lire(id);
    assert.equal(fiche?.published?.fingerprint, empreinteGelee);
    assert.deepEqual(fiche?.published?.content, JSON.parse(JSON.stringify(contenu)));
    assert.equal(fiche?.published?.content.effect.text, "Effect.");
    assert.equal(fiche?.published?.content.managementQuestion, "predictability");
    assert.equal(empreinte(fiche?.published?.content), empreinteGelee, "the fingerprint is that of the content read back");
  } finally {
    await client.end();
    await depot.fermer();
  }
});

// Task 2.5 (design D8, flow-three-closed-quarters): a sheet published before the move to three closed quarters keeps its content, the former window limit code and the
// four quarters of its period included, and its fingerprint. The migration of the three quarters recreates views of the `flow` schema only: the first half of this
// test reads its file and refuses any object of the `mothra` schema in it; the second half freezes a sheet of the former kind in the throwaway database, which
// holds that migration, and reads it back unchanged, its fingerprint being that of the content read.
test("a sheet published with the former window limit keeps its content and its fingerprint after the migration of the three closed quarters, which touches no table of the mothra schema", { skip: saut }, async () => {
  const dossier = fileURLToPath(new URL("../../../../db/migrations/", import.meta.url));
  const fichiers = readdirSync(dossier).filter((nom) => nom.endsWith("_flow_trois_trimestres_clos.sql"));
  assert.equal(fichiers.length, 1, "one migration of the three closed quarters");
  const code = readFileSync(`${dossier}${fichiers[0]}`, "utf8").replace(/--[^\n]*/g, "");
  assert.doesNotMatch(code, /\bmothra\s*\./i, "the migration names no object of the mothra schema");
  assert.doesNotMatch(code, /\b(?:sheets|published_versions|threshold_history)\b/i, "nor a table that holds the sheets");
  const depot = acces();
  try {
    const id = await depot.creer({ ...ENTREE, managementQuestion: "predictability", effect: { text: "E.", lang: "en" }, cause: { text: "C.", lang: "en" } });
    await depot.relire(id, "agile-lead-2");
    const ancien = corpsSynthetique({
      method: {
        ...corpsSynthetique().method,
        period: { quarters: [{ year: 2025, quarter: 4 }, { year: 2026, quarter: 1 }, { year: 2026, quarter: 2 }, { year: 2026, quarter: 3 }] },
        limits: ["no_per_team_unplanned_measure", "views_last_four_quarters"],
      },
    });
    const contenu = figee(ancien);
    const empreinteGelee = empreinte(contenu);
    await depot.publier(id, { content: contenu, fingerprint: empreinteGelee, publishedBy: "agile-lead-2" });
    const relue = await depot.lire(id);
    assert.equal(relue?.published?.fingerprint, empreinteGelee);
    assert.deepEqual(relue?.published?.content, JSON.parse(JSON.stringify(contenu)));
    assert.deepEqual(relue?.published?.content.method.limits, ["no_per_team_unplanned_measure", "views_last_four_quarters"]);
    assert.equal(relue?.published?.content.method.period.quarters.length, 4);
    assert.equal(empreinte(relue?.published?.content), empreinteGelee, "the fingerprint is that of the content read back");
  } finally {
    await depot.fermer();
  }
});

test("a change completes a draft, keeps the fields not given, and touches neither a reviewed nor a published sheet", { skip: saut }, async () => {
  const depot = acces();
  try {
    const id = await depot.creer({ ...ENTREE, managementQuestion: "predictability", effect: { text: "E.", lang: "en" } });
    await depot.modifier(id, { cause: { text: "Cause.", lang: "fr" } });
    let fiche = await depot.lire(id);
    assert.deepEqual([fiche?.managementQuestion, fiche?.effect, fiche?.cause], ["predictability", { text: "E.", lang: "en" }, { text: "Cause.", lang: "fr" }]);
    await depot.modifier(id, { managementQuestion: "scope_growth" });
    assert.equal((await depot.lire(id))?.managementQuestion, "scope_growth");
    await depot.relire(id, "agile-lead-2");
    await depot.modifier(id, { managementQuestion: "scope_reachability", effect: { text: "Changed.", lang: "en" } });
    fiche = await depot.lire(id);
    assert.equal(fiche?.managementQuestion, "scope_growth");
    assert.equal(fiche?.effect?.text, "E.");
  } finally {
    await depot.fermer();
  }
});

test("a user is known when the table users holds its identifier; a malformed identifier is never queried", { skip: saut }, async () => {
  assert.ok(base !== null, "the throwaway database was not created");
  const depot = acces();
  const client = new pg.Client(parametresStockage(base.configuration()));
  await client.connect();
  try {
    assert.equal(await depot.utilisateurExiste("agile-lead-9"), false);
    await client.query("INSERT INTO mothra.users (id, role) VALUES ('agile-lead-9', 'author')");
    assert.equal(await depot.utilisateurExiste("agile-lead-9"), true);
    assert.equal(await depot.utilisateurExiste("Agile Lead; DROP TABLE users"), false);
  } finally {
    await client.end();
    await depot.fermer();
  }
});
