// The refusal rule of the throwaway-database helper, on pure data: no database, no connection. A refusal names the variable, never its value.
import assert from "node:assert/strict";
import { test } from "node:test";

import type { Environnement } from "../src/config/index.ts";
import { RefusBaseJetable, portDecimalStrict, sautBaseJetable, verifierServeurJetable } from "./garde-base-jetable.ts";

const MOT_DE_PASSE = "mot-de-passe-super-sentinelle";

function env(extra: Environnement = {}): Environnement {
  return { DBTEST_PORT: "55432", PMZILLA_LAB_DB_PORT: "55432", PMZILLA_LAB_DB_PASSWORD: MOT_DE_PASSE, ...extra };
}

function refus(environnement: Environnement): RefusBaseJetable {
  try {
    verifierServeurJetable(environnement);
  } catch (erreur) {
    assert.ok(erreur instanceof RefusBaseJetable, "a refusal is a RefusBaseJetable");
    return erreur;
  }
  assert.fail("the environment should have been refused");
}

test("the throwaway server of dbtest is accepted: host 127.0.0.1, port of DBTEST_PORT", () => {
  assert.deepEqual(verifierServeurJetable(env()), { hote: "127.0.0.1", port: 55432, motDePasseSuper: MOT_DE_PASSE });
  assert.equal(verifierServeurJetable(env({ MOTHRA_DB_HOST: "127.0.0.1" })).hote, "127.0.0.1");
});

test("PMZILLA_LAB_DB_PORT absent is accepted: the rule compares it only when it is set", () => {
  const sans = env();
  delete sans.PMZILLA_LAB_DB_PORT;
  assert.equal(verifierServeurJetable(sans).port, 55432);
});

test("the standard port 5432 is refused, even when the lab port says 5432 too", () => {
  assert.equal(refus(env({ DBTEST_PORT: "5432" })).variable, "DBTEST_PORT");
  assert.equal(refus(env({ DBTEST_PORT: "5432", PMZILLA_LAB_DB_PORT: "5432" })).variable, "DBTEST_PORT");
});

test("a port different from PMZILLA_LAB_DB_PORT is refused", () => {
  assert.equal(refus(env({ PMZILLA_LAB_DB_PORT: "6000" })).variable, "PMZILLA_LAB_DB_PORT");
  assert.equal(refus(env({ PMZILLA_LAB_DB_PORT: "05432" })).variable, "PMZILLA_LAB_DB_PORT");
  assert.equal(refus(env({ PMZILLA_LAB_DB_PORT: "" })).variable, "PMZILLA_LAB_DB_PORT");
});

test("a port that is not in strict decimal form is refused", () => {
  const mauvais = ["", "05432", "+55432", "-1", " 55432", "55432 ", "55432\n", "5543a", "0x1f90", "1e4", "55.432", "0", "65536", "99999", "123456", "٥٥٤٣٢"];
  for (const valeur of mauvais) {
    assert.equal(refus(env({ DBTEST_PORT: valeur, PMZILLA_LAB_DB_PORT: valeur })).variable, "DBTEST_PORT", JSON.stringify(valeur));
  }
  assert.equal(refus({ PMZILLA_LAB_DB_PASSWORD: MOT_DE_PASSE }).variable, "DBTEST_PORT");
  assert.equal(portDecimalStrict("65535"), 65535);
  assert.equal(portDecimalStrict("1"), 1);
  assert.equal(portDecimalStrict("0123"), null);
  assert.equal(portDecimalStrict(undefined), null);
});

test("a host other than 127.0.0.1 is refused", () => {
  for (const hote of ["localhost", "0.0.0.0", "10.0.0.5", "db.example.invalid", "::1", "127.0.0.1 ", ""]) {
    assert.equal(refus(env({ MOTHRA_DB_HOST: hote })).variable, "MOTHRA_DB_HOST", JSON.stringify(hote));
  }
});

test("a missing superuser password is refused", () => {
  assert.equal(refus(env({ PMZILLA_LAB_DB_PASSWORD: "" })).variable, "PMZILLA_LAB_DB_PASSWORD");
  const VALEUR_ABSENTE = undefined;   // a constant, not a bare literal: the secret scanner reads a lab variable followed by a literal as a secret
  assert.equal(refus(env({ PMZILLA_LAB_DB_PASSWORD: VALEUR_ABSENTE })).variable, "PMZILLA_LAB_DB_PASSWORD");
});

test("a refusal never echoes a value: neither the port, nor the host, nor the password", () => {
  const cas: Environnement[] = [
    env({ DBTEST_PORT: "5432" }),
    env({ DBTEST_PORT: "valeur-port-sentinelle" }),
    env({ PMZILLA_LAB_DB_PORT: "valeur-lab-sentinelle" }),
    env({ MOTHRA_DB_HOST: "hote-sentinelle.invalid" }),
    env({ PMZILLA_LAB_DB_PASSWORD: "" }),
  ];
  for (const cible of cas) {
    const message = refus(cible).message;
    for (const valeur of Object.values(cible)) {
      if (valeur !== undefined && valeur !== "") {
        assert.ok(!message.includes(valeur), "the message holds a value");
      }
    }
    assert.ok(!message.includes(MOT_DE_PASSE));
  }
});

test("the skip reason names the missing variable and never a value", () => {
  assert.equal(sautBaseJetable(env()), false);
  assert.match(String(sautBaseJetable({})), /^DBTEST_PORT absent/);
  assert.match(String(sautBaseJetable({ DBTEST_PORT: "" })), /^DBTEST_PORT absent/);
  assert.match(String(sautBaseJetable({ DBTEST_PORT: "55432" })), /^PMZILLA_LAB_DB_PASSWORD absent/);
  // A present but invalid value is not skipped: the helper refuses it, loudly.
  assert.equal(sautBaseJetable(env({ DBTEST_PORT: "5432" })), false);
});
