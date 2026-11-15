// Audit #629, A-67 (b), R-20261107-30: the server refuses to start when MOTHRA_THRESHOLD differs from the `flow_views_min_cell` of flux.yaml,
// whose path is the setting MOTHRA_FLUX_SETTINGS_FILE (read by one regular expression, without YAML). The refusal names the variables, never
// a value. Absent path: the start is as before. Fictive files only, made by the test in its own temporary folder.
// Remplace / retrait : tombe au désherbage d'Hydra (flux.yaml source unique, MOTHRA_THRESHOLD retiré).
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { VARIABLES, chargerConfiguration } from "../src/config/index.ts";
import { RefusDemarrage } from "../src/refus.ts";
import { envMinimal } from "./aide.ts";

function avecFlux<T>(contenu: string, corps: (chemin: string) => T): T {
  const dossier = mkdtempSync(join(tmpdir(), "mothra-flux-"));
  try {
    const chemin = join(dossier, "flux-fictif.yaml");
    writeFileSync(chemin, contenu, "utf8");
    return corps(chemin);
  } finally {
    rmSync(dossier, { recursive: true, force: true });
  }
}

function refus(env: Record<string, string | undefined>): RefusDemarrage {
  try {
    chargerConfiguration(env);
  } catch (erreur) {
    assert.ok(erreur instanceof RefusDemarrage, "a start refusal was expected");
    return erreur;
  }
  assert.fail("a start refusal was expected");
}

test("the setting has its own variable name", () => {
  assert.equal(VARIABLES.reglagesFlux, "MOTHRA_FLUX_SETTINGS_FILE");
});

test("no path given: the start is as before, with or without MOTHRA_THRESHOLD", () => {
  assert.equal(chargerConfiguration(envMinimal()).seuil, null);
  assert.equal(chargerConfiguration(envMinimal({ MOTHRA_THRESHOLD: "8" })).seuil, 8);
});

test("equal thresholds: the start goes on", () => {
  avecFlux("flow_views_min_cell: 8\n", (chemin) => {
    assert.equal(chargerConfiguration(envMinimal({ MOTHRA_FLUX_SETTINGS_FILE: chemin, MOTHRA_THRESHOLD: "8" })).seuil, 8);
  });
});

test("a missing key and an unset MOTHRA_THRESHOLD both count as the floor of 5, as in tools/flow_views.py", () => {
  avecFlux("autre_reglage: 12\n", (chemin) => {
    assert.equal(chargerConfiguration(envMinimal({ MOTHRA_FLUX_SETTINGS_FILE: chemin })).seuil, null);
    assert.equal(chargerConfiguration(envMinimal({ MOTHRA_FLUX_SETTINGS_FILE: chemin, MOTHRA_THRESHOLD: "5" })).seuil, 5);
  });
  avecFlux("flow_views_min_cell: 2 # sous le plancher\n", (chemin) => {
    assert.equal(chargerConfiguration(envMinimal({ MOTHRA_FLUX_SETTINGS_FILE: chemin })).seuil, null);
  });
});

test("different thresholds are refused: exit 5, SETTING_INVALID, both variables named, no value in the phrase", () => {
  const cas: Array<[string, string | undefined]> = [["flow_views_min_cell: 8\n", undefined], ["flow_views_min_cell: 8\n", "9"], ["flow_views_min_cell: 5\n", "11"]];
  for (const [flux, reglage] of cas) {
    avecFlux(flux, (chemin) => {
      const r = refus(envMinimal({ MOTHRA_FLUX_SETTINGS_FILE: chemin, ...(reglage === undefined ? {} : { MOTHRA_THRESHOLD: reglage }) }));
      assert.equal(r.code, "SETTING_INVALID");
      assert.equal(r.sortie, 5);
      assert.equal(r.phrase, "mothra: refused (SETTING_INVALID) MOTHRA_THRESHOLD MOTHRA_FLUX_SETTINGS_FILE");
      assert.ok(!/\d/.test(r.phrase.replace(/SETTING_INVALID|MOTHRA_\w+/g, "")), "no value in the refusal");
    });
  }
});

test("a file that is missing, or a value that is not an integer, is SETTING_INVALID naming the path variable only", () => {
  const absent = refus(envMinimal({ MOTHRA_FLUX_SETTINGS_FILE: join(tmpdir(), "mothra-flux-inexistant", "flux.yaml") }));
  assert.equal(absent.phrase, "mothra: refused (SETTING_INVALID) MOTHRA_FLUX_SETTINGS_FILE");
  avecFlux("flow_views_min_cell: beaucoup\n", (chemin) => {
    const r = refus(envMinimal({ MOTHRA_FLUX_SETTINGS_FILE: chemin }));
    assert.equal(r.phrase, "mothra: refused (SETTING_INVALID) MOTHRA_FLUX_SETTINGS_FILE");
    assert.ok(!r.phrase.includes("beaucoup"));
  });
});
