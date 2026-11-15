// Task 17.1: the verdict parity cases of design D30, played by the npm player, and the guards around the pure functions.
import assert from "node:assert/strict";
import { test } from "node:test";

import { chargerCasVerdict, jouerCasVerdict } from "../src/parite-verdict.ts";
import type { CasVerdict } from "../src/parite-verdict.ts";
import {
  attachmentSignal,
  h5Verdict,
  litLeDebit,
  referenceH5,
  twoThresholds,
  unplannedWorkExplanation,
  verdictFinal,
} from "../src/verdict.ts";
import type { ConfigH5, Explication } from "../src/verdict.ts";
import { DEPART_ECHANTILLON, DEPART_H5, DEPART_RATTACHEMENT } from "./depart.ts";

const CHEMIN = new URL("../test-data/cas-verdict.json", import.meta.url);

function nomDeLEchec(cas: CasVerdict[]): string | undefined {
  try {
    jouerCasVerdict(cas);
    return undefined;
  } catch (erreur) {
    return (erreur as Error).message;
  }
}

test("every verdict case gives its expected result, names are unique", () => {
  const cas = chargerCasVerdict(CHEMIN);
  assert.ok(cas.length > 0);
  assert.equal(new Set(cas.map((c) => c.name)).size, cas.length);
  assert.equal(nomDeLEchec(cas), undefined);
});

test("the cases cover each rule of design D30", () => {
  const cas = chargerCasVerdict(CHEMIN);
  const fonctions = new Set(cas.map((c) => c.fn));
  for (const f of ["twoThresholds", "h1Verdict", "h5Verdict", "attachmentSignal", "unplannedWorkExplanation", "verdictFinal", "thresholdModifiedAfterReading", "linkColour", "litLeDebit", "echantillonSuffisant", "referenceH5"]) {
    assert.ok(fonctions.has(f), f);
  }
});

test("the player fails on the first differing verdict case and names it", () => {
  const cas = structuredClone(chargerCasVerdict(CHEMIN));
  cas[1].expected = "confirmed";
  cas[2].expected = "confirmed";
  assert.equal(nomDeLEchec(cas), `cas de parité différent : ${cas[1].name}`);
});

test("an unknown function or an error while a case is played makes it differ, naming it", () => {
  const inconnue: CasVerdict[] = [{ name: "inconnue", fn: "nope", input: {}, expected: null }];
  assert.equal(nomDeLEchec(inconnue), "cas de parité différent : inconnue");
  const erreur: CasVerdict[] = [{ name: "seuils inversés", fn: "twoThresholds", input: { measure: 1, lower: 3, upper: 1.5 }, expected: "refuted" }];
  assert.equal(nomDeLEchec(erreur), "cas de parité différent : seuils inversés");
});

test("a verdict file that is not an array is refused at loading", () => {
  assert.throws(() => chargerCasVerdict(new URL("../test-data/licences-acceptees.json", import.meta.url)), /tableau attendu/);
});

test("the functions refuse inverted thresholds and take the grey zone bounds as inside it", () => {
  assert.throws(() => twoThresholds({ measure: 2, lower: 3, upper: 3 }), RangeError);
  assert.equal(twoThresholds({ measure: 3, lower: 1.5, upper: 3 }), "not_settled");
});

test("a verdict never takes the value confirmed when an explanation is not ruled out, for every raw verdict", () => {
  for (const raw of ["refuted", "not_settled", "confirmed", "insufficient_sample"] as const) {
    for (const etat of ["not_ruled_out", "not_measurable"] as const) {
      const r = verdictFinal({
        raw,
        readsThroughput: false,
        attachment: "not_raised",
        explanations: troisExplications({ capacity: etat }),
      });
      assert.notEqual(r.verdict, "confirmed");
      assert.equal(r.verdict, raw === "confirmed" ? "not_settled" : raw);
    }
  }
});

function troisExplications(etats: Partial<Record<Explication["name"], Explication["state"]>> = {}): Explication[] {
  return (["unplanned_work", "capacity", "dependencies"] as const).map((name) => ({ name, state: etats[name] ?? "ruled_out" }));
}

test("a list of explanations that is not the three expected ones is refused", () => {
  const base = { raw: "confirmed", readsThroughput: false, attachment: "not_raised" } as const;
  assert.throws(() => verdictFinal({ ...base, explanations: [] }), Error);
  assert.throws(() => verdictFinal({ ...base, explanations: troisExplications().slice(0, 2) }), Error);
  assert.throws(() => verdictFinal({ ...base, explanations: [...troisExplications().slice(0, 2), { name: "capacity", state: "ruled_out" }] }), Error);
  assert.equal(verdictFinal({ ...base, explanations: troisExplications() }).verdict, "confirmed");
});

test("the configuration of the hypothesis 5 verdict is mandatory", () => {
  const entree = { quarters: [], reference: { median: 10, p85: 20, throughput: 100 } };
  assert.throws(() => h5Verdict(entree as unknown as Parameters<typeof h5Verdict>[0]), Error);
  const sansPlancher = { ...DEPART_H5, floor: undefined } as unknown as ConfigH5;
  assert.throws(() => h5Verdict({ ...entree, config: sansPlancher }), Error);
});

test("unplanned work refuses a team sheet whose defects carry a team but with no team state", () => {
  assert.throws(() => unplannedWorkExplanation({ scope: "team", defectsCarryTeam: true, productState: "ruled_out" }), Error);
});

test("the attachment signal and the sample size take their configuration from the caller", () => {
  assert.equal(attachmentSignal({ judgedShare: 36, referenceShares: [20, 30], ...DEPART_RATTACHEMENT }).signal, "raised");
  assert.equal(DEPART_ECHANTILLON.p85MinItems > DEPART_ECHANTILLON.medianMinItems, true);
});

test("hypothesis 5 has no reference under three full quarters: insufficient sample whatever the throughput; three or four give a verdict", () => {
  const complet = (throughput: number) => ({ median: 10, p85: 20, throughput, medianSufficient: true, p85Sufficient: true });
  const verdictDe = (trimestres: ReturnType<typeof complet>[]) => {
    const reference = referenceH5(trimestres);
    return { reference, resultat: h5Verdict({ quarters: trimestres, reference, config: DEPART_H5 }) };
  };
  for (const debit of [1, 70, 100]) {
    const deux = verdictDe([complet(debit), complet(100)]);
    assert.equal(deux.reference, null);
    assert.equal(deux.resultat.verdict, "insufficient_sample");
  }
  const trois = verdictDe([complet(100), complet(100), complet(100)]);
  assert.deepEqual(trois.reference, { median: 10, p85: 20, throughput: 100 });
  assert.equal(trois.resultat.verdict, "confirmed");
  assert.equal(verdictDe([complet(100), complet(100), complet(100), complet(50)]).resultat.verdict, "refuted");
});

test("hypothesis 5, signal and ban chained end to end from quarter data", () => {
  const trimestres = [
    { median: 10, p85: 20, throughput: 100, medianSufficient: true, p85Sufficient: true },
    { median: 11, p85: 21, throughput: 95, medianSufficient: true, p85Sufficient: true },
    { median: 9, p85: 19, throughput: 105, medianSufficient: true, p85Sufficient: true },
    { median: 10, p85: 20, throughput: 100, medianSufficient: true, p85Sufficient: true },
  ];
  const reference = referenceH5(trimestres);
  assert.deepEqual(reference, { median: 10, p85: 20, throughput: 100 });
  const h5 = h5Verdict({ quarters: trimestres, reference: reference!, config: DEPART_H5 });
  assert.equal(h5.verdict, "confirmed");
  const lit = litLeDebit("h5");
  const sansSignal = verdictFinal({
    raw: h5.verdict,
    readsThroughput: lit,
    attachment: attachmentSignal({ judgedShare: 24, referenceShares: [20, 30], ...DEPART_RATTACHEMENT }).signal,
    explanations: troisExplications(),
  });
  assert.equal(sansSignal.verdict, "confirmed");
  const avecSignal = verdictFinal({
    raw: h5.verdict,
    readsThroughput: lit,
    attachment: attachmentSignal({ judgedShare: 36, referenceShares: [20, 30], ...DEPART_RATTACHEMENT }).signal,
    explanations: troisExplications(),
  });
  const masque = attachmentSignal({ judgedShare: null, referenceShares: [20, 30], ...DEPART_RATTACHEMENT });
  assert.deepEqual(masque.reasons, ["tasks_without_team_share_masked"]);
  const sansLaPart = verdictFinal({ raw: h5.verdict, readsThroughput: lit, attachment: masque.signal, explanations: troisExplications() });
  assert.equal(sansLaPart.verdict, "confirmed");
  assert.equal(avecSignal.verdict, "not_settled");
  assert.equal(avecSignal.attachmentSignalShown, true);
  assert.deepEqual(avecSignal.reasons.map((r) => r.explanation), ["tasks_attachment"]);
});
