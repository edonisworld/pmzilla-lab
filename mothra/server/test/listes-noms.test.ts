// Task 18.3 (design D17, D20, ADR 0007): the two lists of names are read at start-up by the server only. Fake lists of invented names, held
// as test data (test/listes/); a session never sets the variables to the real files.
import assert from "node:assert/strict";
import { test } from "node:test";

import { ligneCorrespond } from "@mothra/contract";

import { chargerConfiguration, VARIABLES } from "../src/config/index.ts";
import type { Environnement } from "../src/config/index.ts";
import { preparer } from "../src/demarrage.ts";
import { RefusDemarrage, codeDeSortie } from "../src/refus.ts";
import { AccesFictif, CHEMIN_CONTRAT, envMinimal } from "./aide.ts";

function refus(env: Environnement, lireListe?: (chemin: string) => string): RefusDemarrage {
  try {
    chargerConfiguration(env, undefined, lireListe);
  } catch (erreur) {
    assert.ok(erreur instanceof RefusDemarrage);
    return erreur;
  }
  return assert.fail("a refusal was expected");
}

test("the two lists are read: the sensitive names, and the distinctive names of the team-names extract", () => {
  const config = chargerConfiguration(envMinimal());
  assert.deepEqual(config.noms.sensibles, ["Zorglub Martin", "abc"]);
  // "Platform Team" holds only common words: not kept, as the hook does.
  assert.deepEqual(config.noms.equipes, ["Quentin Duval", "Nebula Crew"]);
});

test("each unset setting is SETTING_MISSING, exit 5, naming the variable only", () => {
  for (const variable of [VARIABLES.nomsSensibles, VARIABLES.nomsEquipes]) {
    const env = envMinimal();
    delete env[variable];
    const erreur = refus(env);
    assert.equal(erreur.code, "SETTING_MISSING");
    assert.equal(erreur.variable, variable);
    assert.equal(codeDeSortie(erreur.code), 5);
    assert.equal(erreur.phrase, `mothra: refused (SETTING_MISSING) ${variable}`);
  }
});

// A reader that serves a valid list for the other variable and the given fault for the one under test, so that each case really reaches its list.
const SENSIBLES_VALIDES = "Zorglub Martin\n";
const EXTRAIT_VALIDE = "referential_teams:\n  - name: Nebula Crew\n";
function lecteurDontUneListeEstEnDefaut(variable: string, defaut: (chemin: string) => string): (chemin: string) => string {
  const chemins: Record<string, string> = { [VARIABLES.nomsSensibles]: "noms-sensibles.txt", [VARIABLES.nomsEquipes]: "equipes-lisibles.yaml" };
  return (chemin) => {
    if (chemin.endsWith(chemins[variable])) return defaut(chemin);
    if (chemin.endsWith("noms-sensibles.txt")) return SENSIBLES_VALIDES;
    if (chemin.endsWith("noms-generiques.txt")) throw new Error("absent");
    return EXTRAIT_VALIDE;
  };
}

test("a file that is missing, unreadable, or holds no name is SETTING_INVALID, exit 5, naming the variable only, for each of the two lists", () => {
  const defauts: Array<[string, Record<string, (chemin: string) => string>]> = [
    ["missing", { [VARIABLES.nomsSensibles]: () => { throw new Error("ENOENT /chemin/sentinelle/liste"); }, [VARIABLES.nomsEquipes]: () => { throw new Error("ENOENT /chemin/sentinelle/liste"); } }],
    ["unreadable", { [VARIABLES.nomsSensibles]: () => { throw new Error("EACCES /chemin/sentinelle/liste"); }, [VARIABLES.nomsEquipes]: () => { throw new Error("EACCES /chemin/sentinelle/liste"); } }],
    ["without a name", { [VARIABLES.nomsSensibles]: () => "# only a comment\n\n", [VARIABLES.nomsEquipes]: () => "referential_teams:\n" }],
  ];
  for (const variable of [VARIABLES.nomsSensibles, VARIABLES.nomsEquipes]) {
    for (const [nom, parVariable] of defauts) {
      const erreur = refus(envMinimal(), lecteurDontUneListeEstEnDefaut(variable, parVariable[variable]));
      assert.equal(erreur.code, "SETTING_INVALID", `${variable} ${nom}`);
      assert.equal(erreur.variable, variable, `${variable} ${nom}: the refusal names the list that failed`);
      assert.equal(erreur.phrase, `mothra: refused (SETTING_INVALID) ${variable}`, `${variable} ${nom}`);
      assert.ok(!erreur.phrase.includes("sentinelle"));
      assert.equal(codeDeSortie(erreur.code), 5);
    }
  }
});

test("an extract whose names are all common words holds no name: SETTING_INVALID for the team-names variable", () => {
  const lire = (chemin: string): string => {
    if (chemin.endsWith("noms-sensibles.txt")) return "Zorglub Martin\n";
    if (chemin.endsWith("noms-generiques.txt")) throw new Error("absent");
    return "referential_teams:\n  - name: Platform Team\n  - name: Support Services\n";
  };
  const erreur = refus(envMinimal(), lire);
  assert.equal(erreur.code, "SETTING_INVALID");
  assert.equal(erreur.variable, VARIABLES.nomsEquipes);
});

test("the neighbouring generic list removes names of the extract; absent, nothing is removed", () => {
  const extrait = "referential_teams:\n  - name: Nebula Crew\n  - name: Quentin Duval\n";
  const avec = chargerConfiguration(envMinimal(), undefined, (chemin) => {
    if (chemin.endsWith("noms-sensibles.txt")) return "Zorglub Martin\n";
    if (chemin.endsWith("noms-generiques.txt")) return "nebula crew\n";
    return extrait;
  });
  assert.deepEqual(avec.noms.equipes, ["Quentin Duval"]);
  // The generic list absent or unreadable: nothing is removed, both names stay.
  const sans = chargerConfiguration(envMinimal(), undefined, (chemin) => {
    if (chemin.endsWith("noms-sensibles.txt")) return "Zorglub Martin\n";
    if (chemin.endsWith("noms-generiques.txt")) throw new Error("ENOENT");
    return extrait;
  });
  assert.deepEqual(sans.noms.equipes, ["Nebula Crew", "Quentin Duval"]);
});

test("a refusal of a list happens at start-up before any access is created, and the earlier refusals keep their order", () => {
  let acces = 0;
  const env = envMinimal();
  delete env[VARIABLES.nomsSensibles];
  assert.throws(
    () => preparer(env, { cheminContrat: CHEMIN_CONTRAT, creerAcces: () => { acces += 1; return new AccesFictif(); }, journal: false, avertir: () => {} }),
    (e: unknown) => e instanceof RefusDemarrage && e.code === "SETTING_MISSING" && e.variable === VARIABLES.nomsSensibles,
  );
  assert.equal(acces, 0);
  const sansBase = envMinimal();
  delete sansBase[VARIABLES.nomsSensibles];
  delete sansBase.MOTHRA_DB_NAME;
  assert.equal(refus(sansBase).variable, "MOTHRA_DB_NAME");
});

test("the start-up compiles the patterns of both lists, ready for the sheet routes", () => {
  const { motifsNoms } = preparer(envMinimal(), { cheminContrat: CHEMIN_CONTRAT, creerAcces: () => new AccesFictif(), journal: false, avertir: () => {} });
  assert.equal(ligneCorrespond(motifsNoms, "asked Zorglub Martin"), true);
  assert.equal(ligneCorrespond(motifsNoms, "asked nebula crew"), true);
  assert.equal(ligneCorrespond(motifsNoms, "asked xZorglub Martin"), false);
});
