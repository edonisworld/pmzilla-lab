// Audit #629, A-66 (R-20261112-30, A66-a): the rule of the quarter (data date not after the day, in the day's quarter) must not depend on the real
// clock in any test of the server. Static test: every test file that mounts the sheet routes (an option `fiches` with `calculerCorps`) fixes the
// UTC day through `aujourdhui`. A file that mounts them without it would pass today and fail when the quarter changes. No clock, no database.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { test } from "node:test";

const DOSSIER = new URL("./", import.meta.url);

test("every mounting of the sheet routes in the server tests fixes the day with `aujourdhui` (or the file freezes the clock)", () => {
  const sansJour: string[] = [];
  const montent: string[] = [];
  for (const nom of readdirSync(DOSSIER).filter((n) => n.endsWith(".test.ts"))) {
    const source = readFileSync(new URL(nom, DOSSIER), "utf8");
    // By mounting: each `construireServeur(` call that mounts the sheets (`fiches:` or `fiches,`) must give `aujourdhui:`, unless the file
    // freezes the clock itself (`mock.timers.enable`).
    let monte = false;
    let manque = false;
    for (const montage of source.split("construireServeur(").slice(1)) {
      // The call ends at its closing parenthesis (balanced count), not at the first `});` of an inner callback.
      let profondeur = 1;
      let fin = 0;
      while (fin < montage.length && profondeur > 0) {
        const c = montage[fin++];
        if (c === "(") profondeur++;
        else if (c === ")") profondeur--;
      }
      const bloc = montage.slice(0, fin);
      // An object literal (`fiches: {`) or the shorthand (`fiches,`); `fiches: sans` (a variable built elsewhere) is not read by this test.
      if (!/\bfiches\s*(:\s*\{|,)/.test(bloc)) continue;
      monte = true;
      // `aujourdhui: ...` or the shorthand `aujourdhui,` / `aujourdhui }` of a parameter named so (fiches.test.ts). For `fiches: {`, only the
      // literal of `fiches` is read (from its opening brace to its closing brace, balanced count); for the shorthand `fiches,`, the whole block.
      // Not read: `fiches: <variable>`, the mountings through `preparer(`, test/db/ and the helper files; the `mock.timers.enable` exemption
      // holds for the whole file.
      let zone = bloc;
      const debutLitteral = bloc.search(/\bfiches\s*:\s*\{/);
      if (debutLitteral >= 0) {
        const ouvrante = bloc.indexOf("{", debutLitteral);
        let accolades = 0;
        let finLitteral = ouvrante;
        for (; finLitteral < bloc.length; finLitteral++) {
          if (bloc[finLitteral] === "{") accolades++;
          else if (bloc[finLitteral] === "}" && --accolades === 0) break;
        }
        zone = bloc.slice(ouvrante, finLitteral + 1);
      }
      if (!/\baujourdhui\s*[:,}]/.test(zone) && !source.includes("mock.timers.enable")) manque = true;
    }
    if (monte) montent.push(nom);
    if (manque) sansJour.push(nom);
  }
  assert.ok(montent.length >= 8, "precondition: the files that mount the sheet routes are found");
  assert.deepEqual(sansJour, []);
});
