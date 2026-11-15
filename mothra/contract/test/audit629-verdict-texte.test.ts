// Reproductions de l'audit #629 (chasse Kraken), au commit a98a3ffb : attendues rouges avant le correctif. Valeurs fictives seulement.
// Les caractères spéciaux sont écrits par leurs codes ( , ​, ́, ‑, ＠), pour qu'aucun éditeur ne les normalise.
import assert from "node:assert/strict";
import { test } from "node:test";

import { lireNoms, motifsDeNoms, verifierTexteEcrit } from "../src/texte.ts";
import { h5Verdict } from "../src/verdict.ts";
import { DEPART_H5 } from "./depart.ts";

test("H-06 : une référence H5 à 0 ne laisse pas passer « confirmé » (division sans garde)", () => {
  // audit-kraken/lots/L5.md, H-06 : |0 - 0| / 0 vaut NaN, et un NaN n'est jamais hors de la bande
  const trimestre = { median: 0, p85: 0, throughput: 10, medianSufficient: true, p85Sufficient: true };
  const resultat = h5Verdict({
    quarters: [trimestre, trimestre, trimestre, trimestre],
    reference: { median: 0, p85: 0, throughput: 10 },
    config: {
      band: DEPART_H5.band,
      doubleBand: DEPART_H5.doubleBand,
      runRises: DEPART_H5.runRises,
      runMinCumulativeRise: DEPART_H5.runMinCumulativeRise,
      floor: DEPART_H5.floor,
      lowFloor: DEPART_H5.lowFloor,
    },
  });
  assert.notEqual(resultat.verdict, "confirmed");
});

// Listes inventées. Chaque texte contient un nom, une clé ou une adresse écrits avec un caractère que le contrôle ne normalise pas.
const MOTIFS = motifsDeNoms(lireNoms("Zorglub Martin\nZoé Fictive\n"));

const CONTOURNEMENTS: Array<[string, string, string]> = [
  ["espace insécable dans un nom", "vu avec Zorglub Martin hier", "sensitive_name"],
  ["caractère de largeur nulle dans un nom", "vu avec Zorg​lub Martin hier", "sensitive_name"],
  ["nom décomposé (NFD) contre une liste composée (NFC)", "vu avec Zoé Fictive hier", "sensitive_name"],
  ["tiret non ASCII dans une clé", "voir ABC‑123", "ticket_key"],
  ["arobase pleine largeur dans une adresse", "écrire à quelquun＠exemple.invalid", "email"],
];

for (const [libelle, texte, raison] of CONTOURNEMENTS) {
  test(`L3-06 : le contrôle des textes refuse un contournement par Unicode (${libelle})`, () => {
    // audit-kraken/lots/L3.md, constat 6
    const resultat = verifierTexteEcrit(texte, MOTIFS);
    assert.equal(resultat.ok, false);
    if (!resultat.ok) assert.equal(resultat.reason, raison);
  });
}
