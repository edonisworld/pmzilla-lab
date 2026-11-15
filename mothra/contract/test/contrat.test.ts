// Tasks 4.2 and 4.3: the views contract of slice 0 and its loader (floor of five, effective threshold, named refusals).
import assert from "node:assert/strict";
import { test } from "node:test";

import { chargerContrat, lireContrat, RefusContrat, seuilEffectif, validerContrat, vueAcceptee } from "../src/chargeur.ts";
import { PLANCHER } from "../src/plancher.ts";

const CONTRAT_REEL = new URL("../../../contrats/vues.json", import.meta.url);

const VUE = {
  name: "v_team_status",
  schema: "flow",
  roleKind: "flow",
  countColumns: ["tickets"],
  plainColumns: ["team", "type", "status_category", "status"],
};

function contrat(extra: Record<string, unknown> = {}, vue: Record<string, unknown> = {}): unknown {
  return { views: [{ ...VUE, ...vue }], ...extra };
}

function code(valeur: unknown): string | undefined {
  try {
    validerContrat(valeur);
    return undefined;
  } catch (erreur) {
    if (erreur instanceof RefusContrat) {
      return erreur.code;
    }
    throw erreur;
  }
}

test("the floor of five is a constant of the code", () => {
  assert.equal(PLANCHER, 5);
});

test("the contract lists the status by team view and the five aggregated views of slice 1, with their count columns", () => {
  const lu = chargerContrat(CONTRAT_REEL);
  assert.equal(lu.views.length, 7); // status by team, the five aggregated views of slice 1 (task 15.2), then the created and done view (task 36.1)
  assert.deepEqual(lu.views[6].countColumns, ["created", "done"]);
  assert.deepEqual(lu.views[6].plainColumns, ["team", "quarter_start", "type_group"]);
  assert.equal(lu.views[6].name, "v_team_flow_inout");
  assert.deepEqual(
    lu.views.slice(1, 6).map((v) => [v.name, v.schema, v.roleKind]),
    ["v_team_lead_time_throughput", "v_task_without_team_share", "v_team_ready_queue", "v_team_blocked_share", "v_unplanned_share"].map((nom) => [nom, "flow", "flow"]),
  );
  assert.deepEqual(lu.views[1].countColumns, ["throughput", "items_lt", "items_ct", "items_old", "items_without_commitment"]);
  assert.deepEqual(lu.views[2].countColumns, ["tasks_done", "tasks_without_team"]);
  assert.deepEqual(lu.views[3].countColumns, ["ready"]);
  assert.deepEqual(lu.views[4].countColumns, ["blocked_n", "blocked"]);
  assert.deepEqual(lu.views[5].countColumns, ["unplanned_n", "unplanned"]);
  const [vue] = lu.views;
  assert.equal(vue.name, "v_team_status");
  assert.equal(vue.schema, "flow");
  assert.equal(vue.roleKind, "flow");
  assert.deepEqual(vue.countColumns, ["tickets"]);
  assert.deepEqual(vue.plainColumns, ["team", "type", "status_category", "status"]);
  assert.equal(lu.minThreshold, undefined);
});

test("a valid contract is accepted, with or without a minimum threshold at or above five", () => {
  assert.equal(code(contrat()), undefined);
  assert.equal(code(contrat({ minThreshold: 5 })), undefined);
  assert.equal(code(contrat({ minThreshold: 10 })), undefined);
});

test("a threshold under the floor is CONTRACT_FLOOR", () => {
  assert.equal(code(contrat({ minThreshold: 3 })), "CONTRACT_FLOOR");
  assert.equal(code(contrat({ minThreshold: 4 })), "CONTRACT_FLOOR");
  assert.equal(code(contrat({ minThreshold: 0 })), "CONTRACT_FLOOR");
});

test("a contract that does not match the schema is CONTRACT_INVALID", () => {
  assert.equal(code(null), "CONTRACT_INVALID");
  assert.equal(code([]), "CONTRACT_INVALID");
  assert.equal(code({}), "CONTRACT_INVALID");
  assert.equal(code({ views: [] }), "CONTRACT_INVALID");
  assert.equal(code(contrat({ extra: 1 })), "CONTRACT_INVALID");
  assert.equal(code(contrat({ minThreshold: -1 })), "CONTRACT_INVALID");
  assert.equal(code(contrat({ minThreshold: 7.5 })), "CONTRACT_INVALID");
  assert.equal(code(contrat({ minThreshold: "10" })), "CONTRACT_INVALID");
  assert.equal(code(contrat({}, { roleKind: "write" })), "CONTRACT_INVALID");
  assert.equal(code(contrat({}, { countColumns: [] })), "CONTRACT_INVALID");
  assert.equal(code(contrat({}, { owner: "x" })), "CONTRACT_INVALID");
});

test("a table name, a schema-qualified name or an injection text is not a view name", () => {
  for (const nom of ["issues", "teams", "transitions", "items", "assessments", "flow.v_team_status", "V_TEAM_STATUS", "v_team_status; drop", ""]) {
    assert.equal(code(contrat({}, { name: nom })), "CONTRACT_INVALID", nom);
  }
});

test("a text column or a key column is refused", () => {
  for (const colonne of ["title", "summary", "description", "issue_key", "key", "assignee", "reporter", "email"]) {
    assert.equal(code(contrat({}, { plainColumns: ["team", colonne] })), "CONTRACT_INVALID", colonne);
    assert.equal(code(contrat({}, { countColumns: ["tickets", colonne] })), "CONTRACT_INVALID", colonne);
  }
});

test("a column listed both as count and as plain, a repeated column or a repeated view is refused", () => {
  assert.equal(code(contrat({}, { plainColumns: ["team", "tickets"] })), "CONTRACT_INVALID");
  assert.equal(code(contrat({}, { plainColumns: ["team", "team"] })), "CONTRACT_INVALID");
  assert.equal(code({ views: [VUE, VUE] }), "CONTRACT_INVALID");
});

test("a schema that differs from the role kind is refused", () => {
  assert.equal(code(contrat({}, { schema: "quality" })), "CONTRACT_INVALID");
});

test("unreadable text is CONTRACT_INVALID, never a fallback", () => {
  for (const texte of ["", "not json", "{", "undefined"]) {
    assert.throws(
      () => lireContrat(texte),
      (erreur: unknown) => erreur instanceof RefusContrat && erreur.code === "CONTRACT_INVALID",
      texte,
    );
  }
});

test("a missing file is CONTRACT_MISSING and the refusal names no path", () => {
  const absent = new URL("./inexistant/vues.json", import.meta.url);
  assert.throws(
    () => chargerContrat(absent),
    (erreur: unknown) => {
      assert.ok(erreur instanceof RefusContrat);
      assert.equal(erreur.code, "CONTRACT_MISSING");
      assert.equal(erreur.message, "contrat des vues absent");
      assert.equal(erreur.message.includes("inexistant"), false);
      return true;
    },
  );
});

test("a folder in place of the file is CONTRACT_INVALID, not a built-in list", () => {
  assert.throws(
    () => chargerContrat(new URL("./", import.meta.url)),
    (erreur: unknown) => erreur instanceof RefusContrat && erreur.code === "CONTRACT_INVALID",
  );
});

test("the refusals carry the phrases of design D2, French, without path", () => {
  const phrases: Record<string, string> = {
    CONTRACT_MISSING: "contrat des vues absent",
    CONTRACT_INVALID: "contrat des vues invalide",
    CONTRACT_FLOOR: "seuil du contrat sous le plancher",
  };
  for (const [valeur, attendu] of [
    [null, "CONTRACT_INVALID"],
    [contrat({ minThreshold: 3 }), "CONTRACT_FLOOR"],
  ] as const) {
    try {
      validerContrat(valeur);
      assert.fail("a refusal was expected");
    } catch (erreur) {
      assert.ok(erreur instanceof RefusContrat);
      assert.equal(erreur.message, phrases[attendu]);
    }
  }
});

test("the effective threshold is the highest of the floor, the contract, the setting and the option", () => {
  const sans = validerContrat(contrat());
  assert.equal(seuilEffectif(sans), 5);
  assert.equal(seuilEffectif(sans, undefined, undefined), 5);
  assert.equal(seuilEffectif(sans, null, null), 5);
  assert.equal(seuilEffectif(sans, 2, 1), 5);
  assert.equal(seuilEffectif(sans, 8, 6), 8);
  assert.equal(seuilEffectif(sans, 6, 12), 12);
  assert.equal(seuilEffectif(sans, 0, 0), 5);
  const dix = validerContrat(contrat({ minThreshold: 10 }));
  assert.equal(seuilEffectif(dix), 10);
  assert.equal(seuilEffectif(dix, 8, 6), 10);
  assert.equal(seuilEffectif(dix, 15, 6), 15);
  assert.equal(seuilEffectif(dix, 6, 20), 20);
});

test("a setting or an option that is not an integer is refused, not ignored", () => {
  const sans = validerContrat(contrat());
  assert.throws(() => seuilEffectif(sans, 7.5), TypeError);
  assert.throws(() => seuilEffectif(sans, undefined, Number.NaN), TypeError);
  assert.throws(() => seuilEffectif(sans, -1), TypeError);
});

test("a view is accepted only when the contract lists it, by exact name", () => {
  const lu = validerContrat(contrat());
  assert.equal(vueAcceptee(lu, "v_team_status"), true);
  for (const nom of ["v_teams", "flow.v_team_status", "V_TEAM_STATUS", " v_team_status", "v_team_status ", "issues", "", "v_team_status; DROP TABLE flow.issues"]) {
    assert.equal(vueAcceptee(lu, nom), false, nom);
  }
});
