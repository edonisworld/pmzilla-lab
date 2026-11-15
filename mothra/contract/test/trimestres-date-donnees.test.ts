// Audit #629, A-66 (R-20261112-30, design D29): the three pure functions of the data date, with the UTC day passed as text (no clock).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { dateDonneesAdmise, fenetreConforme, fenetreTroisTrimestres, fichePerimee } from "../src/index.ts";

// Window parity (change of three closed quarters, design D2): every UTC day of 2027 to 2030 (2028 is a leap year). The expected starts are recomputed here
// by hand from the quarter number (year * 4 + quarter), never read from the function under test; tools/flow_views.py and flow.closed_quarter_starts
// are tested against the same formula on the same days (tests/flow_views and tests/db), most recent quarter first in all three.
test("fenetreTroisTrimestres: three closed quarters, the most recent first, never the running one, on every UTC day of 2027 to 2030", () => {
  for (let jour = Date.UTC(2027, 0, 1); jour <= Date.UTC(2030, 11, 31); jour += 86_400_000) {
    const d = new Date(jour);
    const annee = d.getUTCFullYear();
    const mois = d.getUTCMonth() + 1;
    const texte = `${String(annee)}-${String(mois).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}`;
    const numero = annee * 4 + Math.floor((mois - 1) / 3);
    const attendus = [1, 2, 3].map((k) => {
      const n = numero - k;
      return `${String(Math.floor(n / 4))}-${String(3 * (n % 4) + 1).padStart(2, "0")}-01`;
    });
    assert.deepEqual(fenetreTroisTrimestres(texte), attendus, texte);
    assert.equal(fenetreConforme(attendus, texte), true, texte);
    const courant = `${String(annee)}-${String(3 * Math.floor((mois - 1) / 3) + 1).padStart(2, "0")}-01`;
    assert.equal(fenetreConforme([courant], texte), false, texte);
  }
});

// Window parity on ONE shared list of days (design D2): tests/flow_views/test_trois_trimestres_clos.py reads the same file, written by hand, and compares
// tools/flow_views.py (trois_trimestres_clos) to the same expected starts, so the Python and TypeScript functions agree on these days.
test("fenetreTroisTrimestres: the shared list of days (read by the Python test too) gives the same three starts", () => {
  const { cas } = JSON.parse(readFileSync(new URL("../test-data/cas-fenetre-trois-trimestres.json", import.meta.url), "utf8")) as {
    cas: Array<{ jour: string; debuts: string[] }>;
  };
  assert.equal(cas.length, 48, "16 quarters, three days each");
  for (const c of cas) {
    assert.deepEqual(fenetreTroisTrimestres(c.jour), c.debuts, c.jour);
    assert.equal(fenetreConforme(c.debuts, c.jour), true, c.jour);
  }
});

test("dateDonneesAdmise: not after the UTC day, in the quarter of that day", () => {
  assert.equal(dateDonneesAdmise("2026-11-12", "2026-11-12"), true);
  assert.equal(dateDonneesAdmise("2026-10-01", "2026-11-12"), true);
  assert.equal(dateDonneesAdmise("2026-11-13", "2026-11-12"), false);
  assert.equal(dateDonneesAdmise("2026-09-30", "2026-11-12"), false);
  assert.equal(dateDonneesAdmise("2026-01-01", "2025-12-31"), false, "1 January 00:30 in Paris is still 31 December in UTC");
  assert.equal(dateDonneesAdmise("2025-12-31", "2025-12-31"), true);
});

test("fichePerimee: stale as soon as the quarter of the data date is not the current UTC quarter", () => {
  assert.equal(fichePerimee("2026-12-31", "2026-12-31"), false);
  assert.equal(fichePerimee("2026-12-31", "2027-01-01"), true);
  assert.equal(fichePerimee("2026-10-01", "2026-12-31"), false);
});

test("fenetreConforme: every quarter start read is one of the three quarters ending with the last closed quarter of the data date", () => {
  assert.equal(fenetreConforme(["2025-04-01", "2025-07-01", "2025-10-01"], "2026-03-15"), true);
  assert.equal(fenetreConforme(["2025-01-01"], "2026-03-15"), false, "a fourth quarter is refused (R-20261114-49)");
  assert.equal(fenetreConforme(["2025-10-01"], "2026-03-15"), true);
  assert.equal(fenetreConforme([], "2026-03-15"), true);
  assert.equal(fenetreConforme(["2026-01-01"], "2026-03-15"), false, "the quarter of the data date itself is not closed");
  assert.equal(fenetreConforme(["2025-01-01", "2026-01-01"], "2026-03-15"), false);
  assert.equal(fenetreConforme(["2026-10-01"], "2026-12-31"), false);
});
