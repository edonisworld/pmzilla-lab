// A-08 of the design pass 2 (point 8, "method face"), R-20261107-23 and R-20261107-33 point 8: the scope line of the method face shows the team as
// the rest of the screen shows it (`libelleEquipe`: the opaque identifier by default, the name only when the dashboard answer holds it), never
// the internal code of the scope ("team.<identifier>"). The sheet answers come from the contract (`ficheH1`, `servirTableau`); no free value.
import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";

import { servirTableau, tableauLeadCycle } from "@mothra/contract";
import { identifiantEquipe } from "@mothra/contract/equipe";

import { FicheConviction } from "../src/composants/FicheConviction.ts";
import { FicheMethode } from "../src/composants/FicheMethode.ts";
import { catalogues } from "../src/i18n/langue.ts";
import { EQUIPE_SYNTHETIQUE, ficheH1, IDENTIFIANT_OPAQUE } from "./fiches-h1.ts";
import { rendre, texte } from "./rendu.ts";

const val = (v: number) => ({ state: "value" as const, value: v });

// The dashboard answer as the service layer serves it: with the setting off the series carry no `team`, with it on they carry the name.
function reponseTableau(avecNom: boolean) {
  const ligne = (debut: string | null) => ({
    team: EQUIPE_SYNTHETIQUE,
    period: debut === null ? "pooled_year" : "quarter",
    quarter_start: debut,
    items_lt: val(30),
    items_ct: val(30),
    lead_median_days: val(40),
    cycle_median_days: val(10),
  });
  const debuts = ["2025-10-01", "2026-01-01", "2026-04-01", "2026-07-01"];
  const vue = { view: "v_team_lead_time_throughput", threshold: 5, columns: [], rows: [...debuts.map(ligne), ligne(null)], sources: ["flow"] };
  const base = tableauLeadCycle(vue as never, { medianMinItems: 10, p85MinItems: 20 }, "2026-10-05", identifiantEquipe);
  return servirTableau(base, { jeu: "synthetic", comptesAutorises: false, afficherNoms: avecNom });
}

// The line "Scope" of the face, from the definition list.
function ligneDePortee(html: string): string {
  const m = /<dt[^>]*>(?:Scope|Périmètre)<\/dt><dd[^>]*>(.*?)<\/dd>/s.exec(html);
  assert.ok(m !== null, "the scope line is there");
  return m[1];
}

test("A-08: the scope of the method face never shows the internal code of the scope", () => {
  const f = ficheH1("confirmed");
  assert.match(f.method.scope.id, /^team\.[0-9a-f]{16}$/, "precondition: the contract's scope is the prefixed code");
  for (const langue of ["en", "fr"] as const) {
    const html = rendre(h(FicheMethode, { methode: f.method, id: "methode" }), langue);
    assert.doesNotMatch(html, /team\.[0-9a-f]{16}/, langue);
    const portee = ligneDePortee(html);
    assert.equal(texte(portee), `${catalogues[langue]["fiche.scope.team"]} ${IDENTIFIANT_OPAQUE}`, langue);
    assert.match(portee, new RegExp(`<data value="${IDENTIFIANT_OPAQUE}">${IDENTIFIANT_OPAQUE}</data>`), langue);
  }
});

test("A-08: the scope of the method face reads like the header of the sheet, identifier by default, name only with the setting", () => {
  const f = ficheH1("confirmed");
  const message = catalogues.en["conviction.scope.team"];
  const sansNom = rendre(h(FicheConviction, { fiche: f, methodeOuverte: true, tableau: reponseTableau(false) }), "en");
  assert.ok(texte(sansNom).includes(message.replace("{team}", IDENTIFIANT_OPAQUE)), "the header shows the identifier");
  assert.equal(texte(ligneDePortee(sansNom)), `Team ${IDENTIFIANT_OPAQUE}`);
  assert.doesNotMatch(sansNom, /team\.[0-9a-f]{16}/);
  assert.doesNotMatch(sansNom, new RegExp(EQUIPE_SYNTHETIQUE, "i"));

  const avecNom = rendre(h(FicheConviction, { fiche: f, methodeOuverte: true, tableau: reponseTableau(true) }), "en");
  assert.ok(texte(avecNom).includes(message.replace("{team}", EQUIPE_SYNTHETIQUE)), "the header shows the name");
  assert.equal(texte(ligneDePortee(avecNom)), `Team ${EQUIPE_SYNTHETIQUE}`);
  assert.ok(!texte(avecNom).includes(IDENTIFIANT_OPAQUE), "the identifier is not shown beside the name");
  assert.doesNotMatch(avecNom, /team\.[0-9a-f]{16}/);
});

test("A-08: a scope that is not an opaque team shows the level alone, never the raw code", () => {
  const f = ficheH1("confirmed");
  const methode = { ...f.method, scope: { level: "team" as const, id: `team.${EQUIPE_SYNTHETIQUE}` } };
  const portee = ligneDePortee(rendre(h(FicheMethode, { methode, id: "methode" }), "en"));
  assert.equal(texte(portee), "Team");
  assert.doesNotMatch(portee, new RegExp(EQUIPE_SYNTHETIQUE, "i"));
});
