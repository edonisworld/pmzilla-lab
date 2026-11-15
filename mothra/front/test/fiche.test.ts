// Task 19.3: the two-face argument sheet, its competing explanations and its three states (design D20 to D22, D29, D33), on SIMULATED
// answers (test/fiche-simulee.ts, fake data). The screen computes no verdict, state, share or signal: it shows what the service sends.
// The parity test below feeds the screen with the real output of the verdict service of group 17.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement as h } from "react";

import { ETATS_FICHE, EXPLICATIONS, LIENS, VERDICTS_AFFICHES } from "../src/api/fiche.ts";
import type { ConfigH5, Explication, TrimestreH5, VerdictOuEchantillon } from "@mothra/contract";
import { attachmentSignal, h1Verdict, h5Verdict, litLeDebit, unplannedWorkExplanation, verdictFinal } from "@mothra/contract";
import type { CorpsFiche, EtatFiche, ReponseFiche, ResultatAction } from "../src/api/fiche.ts";
import { Fiche, lancerAction, RefusAction } from "../src/composants/Fiche.ts";
import { presentationVerdict } from "../src/composants/FicheEtats.ts";
import { catalogues } from "../src/i18n/langue.ts";
import type { Langue } from "../src/i18n/langue.ts";
import { CLES_ERREUR, cleErreur } from "../src/pages/PageSquelette.ts";
import { DONNEES_SIMULEES, ficheSimulee } from "./fiche-simulee.ts";
import { ficheH1, IDENTIFIANT_OPAQUE } from "./fiches-h1.ts";
import { rendre, texte as texteDuMarquage } from "./rendu.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const en = catalogues.en;
const fr = catalogues.fr;

// The text of a fragment, with the apostrophes the server renderer escapes put back.
function texte(html: string): string {
  return texteDuMarquage(html).replaceAll("&#x27;", "'");
}

function ecran(modifs: Parameters<typeof ficheSimulee>[0], langue: Langue, ouverte = false): string {
  return rendre(h(Fiche, { fiche: ficheSimulee(modifs), methodeOuverte: ouverte }), langue);
}

// A face of the sheet, cut from the markup by its class: from its opening tag to its matching closing tag (nested tags counted).
function face(html: string, classe: string): string {
  const marque = html.indexOf(`class="${classe}"`);
  assert.ok(marque >= 0, `face absente : ${classe}`);
  const debut = html.lastIndexOf("<", marque);
  const balise = /^<(\w+)/.exec(html.slice(debut))?.[1];
  assert.ok(balise, `balise de la face absente : ${classe}`);
  const re = new RegExp(`<(/?)${balise}\\b`, "g");
  re.lastIndex = debut;
  let profondeur = 0;
  for (let m = re.exec(html); m !== null; m = re.exec(html)) {
    profondeur += m[1] === "/" ? -1 : 1;
    if (profondeur === 0) return html.slice(debut, html.indexOf(">", m.index) + 1);
  }
  assert.fail(`face non fermée : ${classe}`);
}

function zoneVerdict(html: string): string {
  return face(html, "fiche-verdict-zone");
}

function ligneExplication(html: string, code: string): string {
  const direction = face(html, "fiche-direction");
  const debut = direction.indexOf(`data-explication="${code}"`);
  assert.ok(debut >= 0, code);
  return direction.slice(direction.lastIndexOf("<li", debut), direction.indexOf("</li>", debut));
}

test("the simulated answers are declared as such", () => {
  assert.equal(DONNEES_SIMULEES, true);
  const source = readFileSync(`${FRONT}test/fiche-simulee.ts`, "utf8");
  assert.match(source, /SIMULATED ANSWERS/);
});

test("the management face shows the effect, the cause, the verdict, a reserved chart area and the three explanations", () => {
  const html = ecran({}, "en");
  const direction = texte(face(html, "fiche-direction"));
  assert.match(direction, /Simulated effect: deliveries slowed down/);
  assert.match(direction, /Simulated cause: work waits before it starts/);
  assert.match(html, /<div class="fiche-graphique" data-emplacement="graphique"[^>]*>Chart area reserved\.<\/div>/);
  assert.equal((html.match(/data-emplacement="graphique"/g) ?? []).length, 1);
  assert.match(texte(zoneVerdict(html)), /not settled/);
  for (const nom of ["Unplanned work", "Lack of capacity", "Dependencies"]) assert.match(direction, new RegExp(nom));
  assert.equal((html.match(/data-explication="/g) ?? []).length, EXPLICATIONS.length);
});

test("the method face is one click away: closed by default, opened by a button that says so", () => {
  const ferme = ecran({}, "en");
  assert.doesNotMatch(ferme, /fiche-methode"/);
  assert.doesNotMatch(texte(ferme), /Data fingerprint/);
  assert.match(ferme, /<button type="button" class="fiche-bouton" aria-expanded="false">Show the method<\/button>/);
  const ouvert = ecran({}, "en", true);
  assert.match(ouvert, /aria-expanded="true" aria-controls="[^"]+"/);
  assert.match(ouvert, />Hide the method<\/button>/);
  assert.match(texte(face(ouvert, "fiche-methode")), /Data fingerprint/);
});

test("aria-controls points to an id that exists: absent while the method face is closed, present and matching once open", () => {
  assert.doesNotMatch(ecran({}, "en"), /aria-controls/);
  const ouvert = ecran({}, "en", true);
  const id = /aria-controls="([^"]+)"/.exec(ouvert)?.[1];
  assert.ok(id);
  assert.ok(ouvert.includes(`id="${id}"`));
});

test("the method action comes after the method face, never before it", () => {
  const html = rendre(h(Fiche, { fiche: ficheSimulee({ state: "draft" }), methodeOuverte: true, onRelire: () => ({ ok: true as const }) }), "en");
  assert.ok(html.indexOf("Hide the method") < html.indexOf("Mark as reviewed"));
  assert.ok(html.indexOf('class="fiche-methode"') < html.indexOf("Mark as reviewed"));
});

// ---- verdicts: label, icon and outline come from the token source (D32), insufficient sample included ----------------------------

type Etats = Record<string, { label: string; icon: string; outline: string }>;
const ETATS = (JSON.parse(readFileSync(`${FRONT}src/styles/tokens.json`, "utf8")) as { states: Etats }).states;

test("every verdict the service can return shows its label, its icon and its outline, as the token source states them", () => {
  const jeton: Record<VerdictOuEchantillon, string> = {
    confirmed: "verdict-confirmed",
    refuted: "verdict-refuted",
    not_settled: "verdict-not-settled",
    insufficient_sample: "state-insufficient",
  };
  const classe: Record<VerdictOuEchantillon, string> = {
    confirmed: "fiche-verdict-confirmed",
    refuted: "fiche-verdict-refuted",
    not_settled: "fiche-verdict-not-settled",
    insufficient_sample: "fiche-verdict-insufficient",
  };
  assert.deepEqual([...VERDICTS_AFFICHES].sort(), Object.keys(jeton).sort());
  for (const verdict of VERDICTS_AFFICHES) {
    const etat = ETATS[jeton[verdict]];
    for (const [langue, catalogue] of [["en", en], ["fr", fr]] as const) {
      const zone = zoneVerdict(ecran({ verdict }, langue));
      assert.ok(texte(zone).includes(catalogue[etat.label]), `${verdict} ${langue}: libellé`);
      assert.match(zone, new RegExp(`class="fiche-verdict ${classe[verdict]}"`), `${verdict} ${langue}: classe de couleur`);
      assert.match(zone, new RegExp(`data-verdict="${verdict}" data-contour="${etat.outline}"`));
      assert.doesNotMatch(zone, /data-motif=/);
      assert.match(zone, new RegExp(`data-icone="${etat.icon}"`));
      assert.doesNotMatch(texte(zone), /favou?rable|défavorable/i);
    }
  }
});

test("an insufficient sample verdict does not break the sheet and is shown with the insufficient label", () => {
  const zone = zoneVerdict(ecran({ verdict: "insufficient_sample" }, "en"));
  assert.match(texte(zone), /insufficient sample/);
  assert.match(zone, /data-icone="ellipsis"/);
  assert.match(zone, /fiche-verdict-insufficient/);
  assert.match(texte(zoneVerdict(ecran({ verdict: "insufficient_sample" }, "fr"))), /échantillon insuffisant/);
});

test("a verdict the screen does not know does not break the sheet: neutral presentation, fallback label, never the raw value", () => {
  const presentation = presentationVerdict("a_new_verdict");
  assert.equal(presentation.cle, "fiche.verdict.unknown");
  assert.ok(en["fiche.verdict.unknown"] && fr["fiche.verdict.unknown"]);
  for (const langue of ["en", "fr"] as const) {
    const zone = zoneVerdict(ecran({ verdict: "a_new_verdict" as never }, langue));
    assert.ok(texte(zone).includes(catalogues[langue]["fiche.verdict.unknown"]));
    assert.doesNotMatch(texte(zone), /a_new_verdict/);
  }
});

test("the screen offers no way to type a verdict, in any state", () => {
  for (const etat of ETATS_FICHE) {
    const html = rendre(h(Fiche, { fiche: ficheSimulee({ state: etat }), methodeOuverte: true, onRelire: () => ({ ok: true as const }), onPublier: () => ({ ok: true as const }) }), "en");
    assert.doesNotMatch(html, /<(input|textarea|select|form)\b/);
    assert.doesNotMatch(html, /contenteditable/i);
  }
});

// ---- explanations, reasons, signal ----------------------------------------------------------------------------------------------

test("the three competing explanations carry their state and their reason, from the catalogue", () => {
  const html = ecran({}, "en");
  const ligne = (code: string): string => texte(ligneExplication(html, code));
  assert.match(ligne("unplanned_work"), /Unplanned work: Not measurable/);
  assert.match(ligne("unplanned_work"), /Reason: defects carry no team: unplanned work is measured for the product only/);
  assert.match(ligne("capacity"), /Lack of capacity: Ruled out/);
  assert.doesNotMatch(ligne("capacity"), /Reason/);
  assert.match(ligne("dependencies"), /Dependencies: Not measurable/);
  const francais = ecran({}, "fr");
  assert.match(texte(ligneExplication(francais, "unplanned_work")), /Travail non planifié : Non mesurable/);
  assert.match(texte(ligneExplication(francais, "unplanned_work")), /Motif : les défauts ne portent pas d'équipe/);
  assert.match(texte(ligneExplication(francais, "capacity")), /Écartée/);
});

test("a not ruled out explanation is shown as such", () => {
  const html = ecran({ explanations: [{ name: "capacity", state: "not_ruled_out" }] }, "en");
  assert.match(texte(face(html, "fiche-direction")), /Lack of capacity: Not ruled out/);
  assert.match(html, /data-etat-explication="not_ruled_out"/);
});

test("the reasons of the verdict, as the service returns them, appear next to the verdict, with a catalogue text", () => {
  const html = ecran(
    {
      verdict: "not_settled",
      verdictReasons: [
        { explanation: "unplanned_work", state: "not_measurable", reason: "defects_without_team" },
        { explanation: "dependencies", state: "not_measurable", reason: "dependencies" },
        { explanation: "tasks_attachment", state: "not_ruled_out", reason: "tasks_attachment_signal" },
      ],
      attachmentSignal: "raised",
      attachmentSignalShown: true,
    },
    "en",
  );
  const zone = texte(zoneVerdict(html));
  assert.match(zone, /Unplanned work: Not measurable/);
  assert.match(zone, /defects carry no team: unplanned work is measured for the product only/);
  assert.match(zone, /Dependencies: Not measurable/);
  // one message per line: the reason follows the state after a separator, never glued to it (the whole text, not the pieces)
  assert.match(zone, /Unplanned work: Not measurable\. Reason: defects carry no team/);
  assert.doesNotMatch(zone, /measurableReason|mesurableMotif/i);
  assert.match(texte(zoneVerdict(rendre(h(Fiche, { fiche: ficheSimulee({ verdictReasons: [{ explanation: "unplanned_work", state: "not_measurable", reason: "defects_without_team" }] }) }), "fr"))), /Travail non planifié : Non mesurable\. Motif : les défauts/);
  // the signal sentence is shown once, whatever the reasons list holds
  assert.equal(zone.split("The change in this team's throughput may come from the attachment of tasks to teams").length - 1, 1);
});

test("the reasons of hypothesis 1 and of hypothesis 5 are shown next to the verdict, in both languages", () => {
  const html = ecran({ verdict: "not_settled", h1Reasons: ["median_masked", "p85_insufficient_sample", "p85_masked", "median_insufficient_sample"], h5Reasons: ["throughput_masked"] }, "en");
  const zone = texte(zoneVerdict(html));
  for (const attendu of [
    "median masked",
    "the P85 rests on too few items",
    "P85 masked",
    "the median rests on too few items",
    "throughput masked in a quarter: “confirmed” is not possible",
  ]) {
    assert.ok(zone.includes(attendu), `manque : ${attendu}`);
  }
  assert.match(texte(zoneVerdict(ecran({ h5Reasons: ["throughput_masked"] }, "fr"))), /débit masqué sur un trimestre/);
});

test("an unknown reason code is shown with the fallback text of the catalogue, never as a raw code", () => {
  const html = ecran(
    {
      verdictReasons: [{ explanation: "something_new", state: "not_ruled_out", reason: "a_new_reason" }],
      explanations: [{ name: "capacity", state: "not_ruled_out", reason: "another_new_reason" }],
      h1Reasons: ["a_new_h1_reason" as never],
    },
    "en",
    true,
  );
  assert.doesNotMatch(texte(html), /something_new|a_new_reason|another_new_reason|a_new_h1_reason/);
  assert.match(texte(zoneVerdict(html)), /reason not available/);
});

test("the unplanned share is the product share, labelled product level, never the team's measure", () => {
  const html = ecran({}, "en");
  const ligne = texte(ligneExplication(html, "unplanned_work"));
  assert.match(ligne, /Share of unplanned work \(product level\): 31%/);
  assert.match(texte(face(ecran({}, "fr"), "fiche-direction")), /niveau produit/);
  assert.doesNotMatch(texte(ligneExplication(html, "capacity")), /product level/);
});

test("a share is read as a percentage of 0 to 100, in both languages: 22 reads 22 percent, never 2,200", () => {
  const en22 = texte(face(ecran({}, "en"), "fiche-debit"));
  assert.match(en22, /22%/);
  assert.doesNotMatch(en22, /2,200|220/);
  const fr22 = texte(face(ecran({}, "fr"), "fiche-debit"));
  assert.match(fr22, /22\s%/);
  assert.doesNotMatch(fr22, /2\s?200/);
});

test("the throughput part shows the product share of tasks without a team and the own-past statement", () => {
  const enTexte = texte(face(ecran({}, "en"), "fiche-direction"));
  assert.match(enTexte, /Share of done tasks without a team \(product level, attributed to no team\): 22%/);
  assert.match(enTexte, /A team's throughput compares only with its own past\./);
  const frTexte = texte(face(ecran({}, "fr"), "fiche-direction"));
  assert.match(frTexte, /Part des tâches terminées sans équipe \(niveau produit, attribuée à aucune équipe\)/);
  assert.match(frTexte, /Le débit d'une équipe ne se compare qu'à son propre passé\./);
});

test("a masked product share shows the masked label and no number, an insufficient one its label with the insufficient icon", () => {
  const masquee = texte(face(ecran({ tasksWithoutTeamShare: { state: "masked", threshold: 5 } }, "en"), "fiche-debit"));
  assert.match(masquee, /: masked/);
  assert.doesNotMatch(masquee.replace("(product level, attributed to no team)", ""), /\d/);
  const insuffisante = face(ecran({ tasksWithoutTeamShare: { state: "insufficient_sample" } }, "fr"), "fiche-debit");
  assert.match(texte(insuffisante), /échantillon insuffisant/);
  assert.match(insuffisante, /data-icone="ellipsis"/);
});

test("signal shown with confirming data: not settled, the signal next to the verdict on the management face", () => {
  const html = ecran({ verdict: "not_settled", attachmentSignal: "raised", attachmentSignalShown: true }, "en");
  const zone = texte(zoneVerdict(html));
  assert.match(zone, /not settled/);
  assert.match(zone, /The change in this team's throughput may come from the attachment of tasks to teams, not from a real change/);
  assert.match(html, /role="note" class="fiche-signal"/);
});

test("signal shown with refuting data: refuted, shown with the signal", () => {
  const zone = texte(zoneVerdict(ecran({ verdict: "refuted", attachmentSignal: "raised", attachmentSignalShown: true }, "fr")));
  assert.match(zone, /réfutée/);
  assert.match(zone, /La variation du débit de cette équipe peut venir du rattachement des tâches aux équipes/);
});

test("a signal raised on a hypothesis that does not read throughput is not shown: raised is not shown (D20)", () => {
  const html = ecran({ attachmentSignal: "raised", attachmentSignalShown: false }, "en", true);
  assert.doesNotMatch(html, /fiche-signal/);
  assert.doesNotMatch(texte(html), /attachment of tasks to teams/);
});

test("no signal when the service does not raise it, and the verdict is shown unchanged", () => {
  const html = ecran({ verdict: "refuted" }, "en", true);
  assert.doesNotMatch(html, /fiche-signal/);
  assert.match(texte(zoneVerdict(html)), /refuted/);
});

test("a masked share of tasks without a team: no signal, and the reason is shown next to the verdict", () => {
  const html = ecran({ attachmentSignal: "not_raised", attachmentSignalReasons: ["tasks_without_team_share_masked"] }, "en");
  const zone = texte(zoneVerdict(html));
  assert.match(zone, /share of tasks without a team masked/);
  assert.doesNotMatch(zone, /attachment of tasks to teams/);
  assert.match(texte(zoneVerdict(ecran({ attachmentSignalReasons: ["tasks_without_team_share_masked"] }, "fr"))), /part des tâches sans équipe masquée/);
});

test("the signal is never only in the method face", () => {
  const html = ecran({ attachmentSignal: "raised", attachmentSignalShown: true }, "en", true);
  assert.doesNotMatch(texte(face(html, "fiche-methode")), /attachment of tasks to teams/);
});

// ---- the method face ------------------------------------------------------------------------------------------------------------

test("the method face lists the method, scope, period, dates, fingerprint, coverage, limits, role, version and hypothesis", () => {
  // A-08, R-20261107-33 point 8: the scope is the one of the contract ("team.<opaque identifier>"), shown as the identifier, never the code.
  const portee = ficheH1("confirmed").method.scope;
  const avecPortee = { method: { ...ficheSimulee().method, scope: portee } };
  const html = texte(face(ecran(avecPortee, "en", true), "fiche-methode"));
  for (const attendu of [
    "Lead time against cycle time",
    `Team ${IDENTIFIANT_OPAQUE}`,
    "Q1 2026 to Q2 2026",
    "Data date",
    "Nov 2, 2026",
    "0000simulated0000",
    "Coverage (items)",
    "120",
    "Unplanned work is not measured per team: defects carry no team",
    "The views hold the last four closed quarters as of the reading, not as of the data date",
    "Agile Lead",
    "Version 1",
    "Hypothesis 5",
  ]) {
    assert.ok(html.includes(attendu), `manque : ${attendu}`);
  }
  const francais = texte(face(ecran(avecPortee, "fr", true), "fiche-methode"));
  assert.match(francais, /T1 2026 à T2 2026/);
  assert.match(francais, new RegExp(`Équipe ${IDENTIFIANT_OPAQUE}`));
  // the level label comes from the catalogue; the identifier is a datum
  const markup = face(ecran(avecPortee, "en", true), "fiche-methode");
  assert.match(markup, new RegExp(`Team <data value="${IDENTIFIANT_OPAQUE}">${IDENTIFIANT_OPAQUE}</data>`));
  assert.doesNotMatch(markup, /team\.[0-9a-f]{16}/);
  assert.match(texte(face(ecran({ method: { ...ficheSimulee().method, scope: { level: "product", id: "p1" } } }, "en", true), "fiche-methode")), /Scope.*Product/);
});

test("method, scope, period and limits are codes translated by the catalogue, with a fallback key for an unknown code", () => {
  const base = ficheSimulee().method;
  const html = texte(
    face(
      ecran(
        {
          method: {
            ...base,
            method: "a_new_method",
            scope: { level: "a_new_level" as never, id: "x1" },
            limits: ["a_new_limit"],
            thresholds: [{ code: "a_new_threshold", value: 1, fixedOn: "2026-10-28", fixedBy: "author_alone" }],
            maskedCells: [{ measure: "a_new_measure", cell: { state: "masked", threshold: 5 } }],
            insufficientSamples: ["another_new_measure"],
            authorRole: "someone",
            hypothesis: "h99" as never,
          },
        },
        "en",
        true,
      ),
      "fiche-methode",
    ),
  );
  assert.doesNotMatch(html, /a_new_|another_new|h99/);
  for (const attendu of ["Method not available", "Scope not available", "Limit not available", "Threshold not available", "Measure not available", "role not available", "Hypothesis not available"]) {
    assert.ok(html.includes(attendu), `manque : ${attendu}`);
  }
});

test("the hypothesis shows which link and which half, from the identifiers of the service", () => {
  assert.deepEqual([...LIENS].sort(), ["h1_first_half", "h1_second_half", "h2", "h3", "h4", "h5"]);
  const methode = ficheSimulee().method;
  const lu = (hypothesis: (typeof LIENS)[number], langue: Langue): string =>
    texte(face(ecran({ method: { ...methode, hypothesis } }, langue, true), "fiche-methode"));
  assert.match(lu("h1_first_half", "en"), /Hypothesis 1, first half/);
  assert.match(lu("h1_second_half", "en"), /Hypothesis 1, second half/);
  assert.match(lu("h1_second_half", "fr"), /Hypothèse 1, seconde moitié/);
  assert.match(lu("h3", "en"), /Hypothesis 3/);
});

test("the thresholds show their fixing date, the author alone, and the statement of D21, with the throughput floor and the two sample-size thresholds", () => {
  const html = texte(face(ecran({}, "en", true), "fiche-methode"));
  assert.match(html, /Throughput floor of hypothesis 5/);
  assert.match(html, /Minimum number of items for a median/);
  assert.match(html, /Minimum number of items for a P85/);
  assert.match(html, /Oct 28, 2026/);
  assert.match(html, /The author alone/);
  assert.match(html, /Thresholds fixed on Oct 28, 2026: set by the author alone, before any reading of real data by Mothra\./);
  assert.match(html, /The author had already seen real aggregated data in the monthly flow reports\./);
  const francais = texte(face(ecran({}, "fr", true), "fiche-methode"));
  assert.match(francais, /Seuils fixés le 28 oct\. 2026 : fixés par l'auteur seul, avant toute lecture de données réelles par Mothra\./);
  assert.match(francais, /rapports de flux mensuels/);
});

test("every threshold of hypotheses 1 and 5 has a label in both catalogues", () => {
  const codes = [
    "attachment_threshold_points",
    "sample_median_min_items",
    "sample_p85_min_items",
    "h1_lower",
    "h1_upper",
    "h5_band",
    "h5_double_band",
    "h5_floor",
    "h5_low_floor",
    "h5_run_rises",
    "h5_run_min_cumulative_rise",
  ];
  const base = ficheSimulee().method;
  const methode = { ...base, thresholds: codes.map((code) => ({ code, value: 1, fixedOn: "2026-10-28", fixedBy: "author_alone" as const })) };
  for (const langue of ["en", "fr"] as const) {
    assert.doesNotMatch(texte(face(ecran({ method: methode }, langue, true), "fiche-methode")), /not available|non disponible/);
  }
});

test("a threshold modified after reading is flagged with its former value and date, in one message", () => {
  const base = ficheSimulee();
  const html = texte(
    face(
      ecran(
        {
          method: {
            ...base.method,
            thresholds: [{ code: "sample_median_min_items", value: 30, fixedOn: "2026-11-10", fixedBy: "author_alone", modifiedAfterReading: { formerValue: 20, formerDate: "2026-10-28" } }],
          },
        },
        "en",
        true,
      ),
      "fiche-methode",
    ),
  );
  assert.match(html, /Threshold modified after reading: former value 20, fixed on Oct 28, 2026/);
  assert.doesNotMatch(texte(face(ecran({}, "en", true), "fiche-methode")), /modified after reading/i);
});

test("masked cells of the method face are the contract's masked cell: the masked label, the threshold stated once, no value, no reason", () => {
  const html = face(ecran({}, "en", true), "fiche-methode");
  assert.match(html, /<td class="cellule cellule-masquee" data-state="masked">masked<\/td>/);
  const tableau = texte(html.slice(html.indexOf('data-tableau="masquees"'), html.indexOf("</table>", html.indexOf('data-tableau="masquees"'))));
  assert.match(tableau, /Ready queue/);
  assert.doesNotMatch(tableau, /confidentiality threshold|Reason/);
  assert.equal(texte(html).split("Counts and statistics computed on fewer than 5 items are masked.").length - 1, 1);
  const francais = ecran({}, "fr", true);
  assert.match(francais, /data-state="masked">masqué<\/td>/);
  assert.match(texte(francais), /Les comptes et les statistiques calculés sur moins de 5 éléments sont masqués\./);
});

test("masked cells with different thresholds each show theirs, and the statement is not made for a threshold that is not shared", () => {
  const base = ficheSimulee().method;
  const html = texte(
    face(
      ecran(
        {
          method: {
            ...base,
            maskedCells: [
              { measure: "ready@2026-04-01", cell: { state: "masked", threshold: 5 } },
              { measure: "blocked_share", cell: { state: "masked", threshold: 8 } },
            ],
          },
        },
        "en",
        true,
      ),
      "fiche-methode",
    ),
  );
  assert.doesNotMatch(html, /fewer than 5 items are masked/);
  assert.match(html, /Ready queue.*5/);
  assert.match(html, /Share of items blocked by another team.*8/);
});

test("a masked coverage states its threshold, a valued coverage does not", () => {
  const base = ficheSimulee().method;
  const masque = texte(face(ecran({ method: { ...base, coverage: { state: "masked", threshold: 5 } } }, "en", true), "fiche-methode"));
  assert.match(masque, /Coverage \(items\).*masked.*fewer than 5 items are masked/);
  assert.doesNotMatch(texte(face(ecran({}, "en", true), "fiche-methode")).replace(/Counts and statistics computed on fewer than 5 items are masked\./, ""), /fewer than/);
});

test("insufficient samples are listed with their label, the ellipsis icon and the dotted outline, apart from masked cells", () => {
  const html = face(ecran({}, "en", true), "fiche-methode");
  assert.match(html, /<td class="cellule cellule-insuffisante" data-state="insufficient"><span class="fiche-icone" data-icone="ellipsis" aria-hidden="true"><\/span>insufficient sample<\/td>/);
  const tableau = texte(html.slice(html.indexOf('data-tableau="insuffisants"'), html.indexOf("</table>", html.indexOf('data-tableau="insuffisants"'))));
  assert.match(tableau, /Median lead time/);
  assert.doesNotMatch(tableau, /masked/);
  assert.match(texte(face(ecran({}, "fr", true), "fiche-methode")), /échantillon insuffisant/);
});

test("the quarters left out of the verdict are listed by statistic, as formatted quarters", () => {
  const html = texte(face(ecran({}, "en", true), "fiche-methode"));
  assert.match(html, /Median: Q1 2026/);
  assert.match(html, /P85: None\./);
  assert.match(html, /Throughput: None\./);
  const francais = texte(face(ecran({}, "fr", true), "fiche-methode"));
  assert.match(francais, /Médiane : T1 2026/);
});

test("empty lists of the method face say so", () => {
  const base = ficheSimulee();
  const html = texte(
    face(
      ecran({ method: { ...base.method, maskedCells: [], insufficientSamples: [], limits: [], excluded: { median: [], p85: [], throughput: [] } } }, "en", true),
      "fiche-methode",
    ),
  );
  assert.equal(html.split("None.").length - 1, 6);
});

// ---- free text, language, no flow vocabulary -----------------------------------------------------------------------------------

test("the effect and the cause carry their own language: a lang attribute when it differs from the screen's, none otherwise", () => {
  const base = { effect: { text: "Effet simulé : les livraisons ralentissent.", lang: "fr" as const }, cause: { text: "Simulated cause.", lang: "en" as const } };
  const html = ecran(base, "en");
  assert.match(html, /<span lang="fr">Effet simulé : les livraisons ralentissent\.<\/span>/);
  assert.doesNotMatch(html, /<span lang="en">/);
  const francais = ecran(base, "fr");
  assert.match(francais, /<span lang="en">Simulated cause\.<\/span>/);
  assert.doesNotMatch(francais, /<span lang="fr">/);
});

const TERMES_DE_FLUX = [
  /lead[- ]?time/i,
  /cycle[- ]?time/i,
  /throughput/i,
  /\bwip\b/i,
  /work in progress/i,
  /\bp85\b/i,
  /percentile/i,
  /\bflow\b/i,
  /d[ée]bit/i,
  /temps de cycle/i,
  /d[ée]lai de livraison/i,
  /\ben cours\b/i,
  /flux/i,
];

// The first line of the management face: the effect, in management's words (the label of the line excluded).
function premiereLigne(html: string, langue: Langue): string {
  const direction = face(html, "fiche-direction");
  const paragraphe = /<p>(.*?)<\/p>/.exec(direction)?.[1] ?? "";
  return texte(paragraphe).replace(new RegExp(`^${catalogues[langue]["fiche.effect.line"].split("{")[0].trim()}\\s*`), "").trim();
}

test("the first line of the management face is the effect and holds no flow vocabulary, in each language", () => {
  const sains = [
    ["en", { text: "Simulated effect: deliveries slowed down over the quarter.", lang: "en" }],
    ["fr", { text: "Effet simulé : les livraisons ralentissent depuis le trimestre.", lang: "fr" }],
  ] as const;
  for (const [langue, effect] of sains) {
    const ligne = premiereLigne(ecran({ effect }, langue), langue);
    assert.equal(ligne, effect.text);
    for (const terme of TERMES_DE_FLUX) assert.doesNotMatch(ligne, terme, `${langue}: ${String(terme)}`);
  }
});

test("the list of flow terms catches the English and French terms of flow (the check itself)", () => {
  for (const phrase of ["the lead time grew", "cycle time grew", "throughput fell", "WIP is high", "le débit baisse", "temps de cycle en hausse", "le flux ralentit"]) {
    assert.ok(TERMES_DE_FLUX.some((terme) => terme.test(phrase)), phrase);
  }
});

test("the sheet names no ticket, no mention and no person: the author is shown as a role, an unknown role as unavailable", () => {
  const html = texte(ecran({}, "fr", true));
  assert.match(html, /Agile Lead/);
  assert.doesNotMatch(html, /\b[A-Z][A-Z0-9]+-\d+\b/);
  assert.doesNotMatch(html, /@|https?:\/\//);
  const inconnu = texte(face(ecran({ method: { ...ficheSimulee().method, authorRole: "someone" } }, "en", true), "fiche-methode"));
  assert.match(inconnu, /role not available/);
  assert.doesNotMatch(inconnu, /someone/);
});

// ---- states, publication date, actions, refusals --------------------------------------------------------------------------------

test("the three states show their label in each language", () => {
  const attendu: Record<EtatFiche, [string, string]> = { draft: ["Draft", "Brouillon"], reviewed: ["Reviewed", "Relue"], published: ["Published", "Publiée"] };
  for (const etat of ETATS_FICHE) {
    const [enLabel, frLabel] = attendu[etat];
    assert.match(rendre(h(Fiche, { fiche: ficheSimulee({ state: etat }) }), "en"), new RegExp(`data-etat-fiche="${etat}"[^>]*>${enLabel}<`));
    assert.match(rendre(h(Fiche, { fiche: ficheSimulee({ state: etat }) }), "fr"), new RegExp(`data-etat-fiche="${etat}"[^>]*>${frLabel}<`));
  }
});

test("a published sheet shows its publication date; a draft shows none", () => {
  const publiee = ecran({ state: "published", publishedOn: "2026-11-05" }, "en");
  assert.match(texte(publiee), /Published on Nov 5, 2026/);
  assert.match(texte(ecran({ state: "published", publishedOn: "2026-11-05" }, "fr")), /Publiée le 5 nov\. 2026/);
  assert.doesNotMatch(texte(ecran({ state: "draft" }, "en")), /Published on/);
});

test("a draft offers the review action, a reviewed sheet the publish action, only when the caller wires them", () => {
  const sans = rendre(h(Fiche, { fiche: ficheSimulee({ state: "draft" }) }), "en");
  assert.doesNotMatch(sans, /Mark as reviewed|Publish</);
  const actions = { onRelire: () => ({ ok: true }) as ResultatAction, onPublier: () => ({ ok: true }) as ResultatAction };
  const brouillon = rendre(h(Fiche, { fiche: ficheSimulee({ state: "draft" }), ...actions }), "en");
  assert.match(brouillon, />Mark as reviewed<\/button>/);
  assert.doesNotMatch(brouillon, />Publish<\/button>/);
  const relue = rendre(h(Fiche, { fiche: ficheSimulee({ state: "reviewed" }), ...actions }), "en");
  assert.match(relue, />Publish<\/button>/);
  assert.doesNotMatch(relue, />Mark as reviewed<\/button>/);
});

test("a published sheet is frozen: it says so and holds nothing editable, not even a wired action", () => {
  const html = rendre(
    h(Fiche, { fiche: ficheSimulee({ state: "published", publishedOn: "2026-11-05" }), methodeOuverte: true, onRelire: () => ({ ok: true as const }), onPublier: () => ({ ok: true as const }) }),
    "en",
  );
  assert.match(html, /data-figee="true"/);
  assert.match(texte(html), /Published version, frozen: nothing can be edited\./);
  assert.doesNotMatch(html, />Mark as reviewed<|>Publish</);
  assert.doesNotMatch(html, /<(input|textarea|select|form)\b|contenteditable/i);
  // the only control left is the one that opens or closes the method face
  assert.equal((html.match(/<button\b/g) ?? []).length, 1);
  assert.doesNotMatch(rendre(h(Fiche, { fiche: ficheSimulee({ state: "draft" }) }), "en"), /data-figee/);
});

test("a rejected review or publication is shown as the translated internal error in an alert, never left unhandled", async () => {
  const vus: Array<string | undefined> = [];
  await lancerAction(() => Promise.reject(new Error("network")), (c) => vus.push(c));
  await lancerAction(() => {
    throw new Error("sync");
  }, (c) => vus.push(c));
  assert.deepEqual(vus, ["INTERNAL", "INTERNAL"]);
  const html = rendre(h(RefusAction, { code: "INTERNAL" }), "en");
  assert.match(html, /role="alert"/);
  assert.ok(texte(html).includes("Something went wrong."));
  assert.doesNotMatch(texte(html), /INTERNAL|network/);
});

test("the contract type of a sheet body follows its response schema: effect, cause and management question are optional", () => {
  const source = readFileSync(new URL("../../contract/src/fiche.ts", import.meta.url), "utf8");
  assert.match(source, /effect\?: TexteLibre;/);
  assert.match(source, /cause\?: TexteLibre;/);
  assert.match(source, /managementQuestion\?: QuestionDeDirection;/);
});

test("a draft created without management question, effect or cause is shown with catalogue labels, in each language, and does not fail", () => {
  const brouillon = { effect: undefined, cause: undefined, managementQuestion: undefined } as const;
  const anglais = texte(rendre(h(Fiche, { fiche: ficheSimulee({ state: "draft", ...brouillon }) }), "en"));
  assert.match(anglais, /Effect: Not provided yet/);
  assert.match(anglais, /Cause: Not provided yet/);
  assert.match(anglais, /Management question: Not provided yet/);
  const francais = texte(rendre(h(Fiche, { fiche: ficheSimulee({ state: "draft", ...brouillon }) }), "fr"));
  assert.match(francais, /Effet : À renseigner/);
  assert.match(francais, /Cause : À renseigner/);
  assert.match(francais, /Question de direction : À renseigner/);
  for (const cle of ["fiche.text.missing", "fiche.question.line"] as const) {
    assert.ok(cle in en && cle in fr, cle);
    assert.notEqual(en[cle], fr[cle]);
  }
});

test("a sheet completed later shows its texts and its management question, and no missing label", () => {
  const complete = texte(rendre(h(Fiche, { fiche: ficheSimulee({ state: "draft", managementQuestion: "predictability" }) }), "en"));
  assert.match(complete, /Management question: Predictability/);
  assert.match(complete, /Effect: Simulated effect/);
  assert.doesNotMatch(complete, /Not provided yet/);
  for (const code of ["scope_growth", "scope_reachability", "predictability", "next_version_quality"]) {
    assert.ok(`fiche.question.${code}` in en && `fiche.question.${code}` in fr, code);
  }
});

test("a published sheet must carry its publication date: the type is a union discriminated on the state", () => {
  const source = readFileSync(new URL("../../contract/src/fiche.ts", import.meta.url), "utf8");
  assert.match(source, /\{ state: "published"; publishedOn: string \}/);
  assert.match(source, /\{ state: "draft" \| "reviewed"; publishedOn\?: undefined \}/);
  // @ts-expect-error a published sheet without its date is not a ReponseFiche
  const sansDate: ReponseFiche = { ...ficheSimulee(), state: "published", publishedOn: undefined };
  assert.ok(sansDate);
});

test("the three refusals of the service have a translated message in both languages, and an unknown code the internal error", () => {
  for (const code of ["SELF_REVIEW_REFUSED", "NOT_REVIEWED", "VERSION_FROZEN"]) {
    const cle = CLES_ERREUR[code as keyof typeof CLES_ERREUR];
    assert.equal(cleErreur(code), cle);
    assert.ok(en[cle] && fr[cle], code);
    assert.notEqual(en[cle], code);
    assert.notEqual(fr[cle], code);
  }
  assert.match(en["error.SELF_REVIEW_REFUSED"], /own sheet/);
  assert.match(en["error.NOT_REVIEWED"], /reviewed/);
  assert.match(en["error.VERSION_FROZEN"], /frozen/);
  assert.equal(cleErreur("NOPE"), "error.INTERNAL");
});

test("a refusal shows its translated message in an alert, never the raw code", () => {
  for (const code of ["SELF_REVIEW_REFUSED", "NOT_REVIEWED", "VERSION_FROZEN", "NOPE"]) {
    const html = rendre(h(RefusAction, { code }), "en");
    assert.match(html, /role="alert"/);
    assert.ok(texte(html).includes(en[cleErreur(code)]));
    assert.doesNotMatch(texte(html), /_REFUSED|NOT_REVIEWED|VERSION_FROZEN|NOPE/);
  }
  const html = rendre(h(Fiche, { fiche: ficheSimulee({ state: "draft" }), onRelire: () => ({ ok: true as const }), refusInitial: "SELF_REVIEW_REFUSED" }), "fr");
  assert.match(html, /role="alert"/);
  assert.ok(texte(html).includes(fr["error.SELF_REVIEW_REFUSED"]));
});

test("an action that returns a refusal code hands it to the screen, one that succeeds clears it", async () => {
  const vus: Array<string | undefined> = [];
  for (const code of ["SELF_REVIEW_REFUSED", "NOT_REVIEWED", "VERSION_FROZEN"]) {
    await lancerAction(() => ({ ok: false, code }), (c) => vus.push(c));
  }
  await lancerAction(async () => ({ ok: true }), (c) => vus.push(c));
  await lancerAction(async () => ({ ok: false, code: "VERSION_FROZEN" }), (c) => vus.push(c));
  assert.deepEqual(vus, ["SELF_REVIEW_REFUSED", "NOT_REVIEWED", "VERSION_FROZEN", undefined, "VERSION_FROZEN"]);
});

// ---- catalogues and sources -----------------------------------------------------------------------------------------------------

test("every catalogue key of the sheet space exists in both languages", () => {
  const cles = Object.keys(en).filter((c) => c.startsWith("fiche."));
  assert.ok(cles.length > 60);
  for (const cle of cles) assert.ok(cle in fr, `absente de fr.json : ${cle}`);
  for (const cle of Object.keys(fr).filter((c) => c.startsWith("fiche."))) assert.ok(cle in en, `absente de en.json : ${cle}`);
});

test("the sheet sources make no network call and import nothing outside the contract", () => {
  for (const fichier of ["src/composants/Fiche.ts", "src/composants/FicheMethode.ts", "src/composants/FicheEtats.ts", "src/api/fiche.ts"]) {
    const source = readFileSync(`${FRONT}${fichier}`, "utf8").replace(/\/\/.*$/gm, "");
    assert.doesNotMatch(source, /\bfetch\b|XMLHttpRequest|WebSocket|EventSource|sendBeacon|useQuery|https?:\/\//, fichier);
  }
});

test("the types of the sheet are those of the contract package, not a copy, and hold no masked-cell field of their own", () => {
  const source = readFileSync(`${FRONT}src/api/fiche.ts`, "utf8");
  assert.doesNotMatch(source, /reproduit le contrat/);
  assert.match(source, /from "@mothra\/contract"/);
  for (const type of ["Verdict", "VerdictOuEchantillon", "EtatExplication", "LienId", "MotifH1", "MotifH5", "EtatSignal", "MotifSignal", "ExclusionsH5", "Explication", "RaisonVerdict"]) {
    assert.doesNotMatch(source, new RegExp(`export (type|interface) ${type}\\b`), type);
  }
  assert.doesNotMatch(source, /under_threshold/);
});

// ---- parity with the verdict service of group 17: its real output goes into the screen, with renamings only --------------------------
// The only adaptation the route of group 18 will make is to put the results side by side under the names of the sheet
// (`reasons` of h1Verdict / h5Verdict -> h1Reasons / h5Reasons, `excluded` -> method.excluded, `signal` -> attachmentSignal,
// `reasons` of attachmentSignal -> attachmentSignalReasons). `assemblerService` is that renaming and nothing else: it computes nothing.
// Its return type is CorpsFiche, so the type check fails when a field of the service stops fitting the screen.
function assemblerService(entree: {
  h5: ReturnType<typeof h5Verdict>;
  final: ReturnType<typeof verdictFinal>;
  signal: ReturnType<typeof attachmentSignal>;
  explanations: Explication[];
  h1?: ReturnType<typeof h1Verdict>;
}): CorpsFiche {
  const base = ficheSimulee();
  return {
    ...base,
    verdict: entree.final.verdict,
    verdictReasons: entree.final.reasons,
    h1Reasons: entree.h1?.reasons ?? [],
    h5Reasons: entree.h5.reasons,
    explanations: entree.explanations,
    attachmentSignal: entree.signal.signal,
    attachmentSignalReasons: entree.signal.reasons,
    attachmentSignalShown: entree.final.attachmentSignalShown,
    method: { ...base.method, period: { quarters: [{ year: 2026, quarter: 1 }, { year: 2026, quarter: 2 }, { year: 2026, quarter: 3 }] }, excluded: entree.h5.excluded },
  };
}

// The explanations as the service builds them: the unplanned work one by its own function, a dependencies one not ruled out.
function EXPLICATIONS_SERVICE(): Explication[] {
  return [
    unplannedWorkExplanation({ scope: "team", defectsCarryTeam: false, productState: "ruled_out" }),
    { name: "capacity", state: "ruled_out" },
    { name: "dependencies", state: "not_ruled_out" },
  ];
}

// What the screen shows of those explanations: the state of each and, for unplanned work, its reason.
function verifierExplications(html: string): void {
  const travail = ligneExplication(html, "unplanned_work");
  assert.match(travail, /data-etat-explication="not_measurable"/);
  assert.match(texte(travail), /Unplanned work: Not measurable/);
  assert.match(texte(travail), /Reason: defects carry no team/);
  const dependances = ligneExplication(html, "dependencies");
  assert.match(dependances, /data-etat-explication="not_ruled_out"/);
  assert.match(texte(dependances), /Dependencies: Not ruled out/);
}

const CONFIG_H5: ConfigH5 = { band: 0.2, doubleBand: 0.4, runRises: 2, runMinCumulativeRise: 0.1, floor: 0.8, lowFloor: 0.6 };
const TRIMESTRES: TrimestreH5[] = [
  { median: 10, p85: 20, throughput: 30, medianSufficient: true, p85Sufficient: true },
  { median: 10, p85: 20, throughput: null, medianSufficient: false, p85Sufficient: true },
  { median: 10, p85: 20, throughput: 30, medianSufficient: true, p85Sufficient: false },
];

test("the real output of the service goes into the sheet screen with renamings only: raised signal, throughput masked, exclusions", () => {
  const explanations = EXPLICATIONS_SERVICE();
  const h5 = h5Verdict({ quarters: TRIMESTRES, reference: { median: 10, p85: 20, throughput: 30 }, config: CONFIG_H5 });
  const signal = attachmentSignal({ judgedShare: 40, referenceShares: [20, 22], thresholdPoints: 10 });
  const final = verdictFinal({ raw: h5.verdict, explanations, readsThroughput: litLeDebit("h5"), attachment: signal.signal });
  assert.deepEqual(h5.reasons, ["throughput_masked"]);
  assert.equal(signal.signal, "raised");
  assert.equal(final.attachmentSignalShown, true);
  const fiche: ReponseFiche = { ...assemblerService({ explanations, h5, final, signal }), state: "draft" };
  const html = rendre(h(Fiche, { fiche, methodeOuverte: true }), "en");
  assert.match(texte(zoneVerdict(html)), /not settled/);
  assert.match(zoneVerdict(html), /<li class="fiche-raison" data-motif-code="throughput_masked">Reason: throughput masked in a quarter/);
  assert.match(html, /fiche-signal/);
  verifierExplications(html);
  // The exclusion lines of the method face, on the screen: the statistic and the quarters (positions 1, 2 and 1 of the period).
  const ecartes = texte(face(html, "fiche-ecartes"));
  assert.match(ecartes, /Median: Q2 2026/);
  assert.match(ecartes, /P85: Q3 2026/);
  assert.match(ecartes, /Throughput: Q2 2026/);
});

test("the real output of the service for hypothesis 1, with the explanations of the contract, shows its verdict and reasons and no signal when none is raised", () => {
  const explanations = EXPLICATIONS_SERVICE();
  const signal = attachmentSignal({ judgedShare: 20, referenceShares: [20], thresholdPoints: 10 });
  // Real output of hypothesis 5 on three quarters with nothing to leave out: no H5 reason, no exclusion.
  const propres: TrimestreH5[] = TRIMESTRES.map((q) => ({ ...q, throughput: 30, medianSufficient: true, p85Sufficient: true }));
  const h5vide = h5Verdict({ quarters: propres, reference: { median: 10, p85: 20, throughput: 30 }, config: CONFIG_H5 });
  assert.deepEqual(h5vide.reasons, []);
  assert.deepEqual(h5vide.excluded, { median: [], p85: [], throughput: [] });
  const cas = [
    { h1: h1Verdict({ medianRatio: 1.5, p85Ratio: 1.5, lower: 1.1, upper: 1.3, medianSampleSufficient: true, p85SampleSufficient: true }), verdict: "not_settled", motif: null },
    { h1: h1Verdict({ medianRatio: null, p85Ratio: null, lower: 1.1, upper: 1.3, medianSampleSufficient: true, p85SampleSufficient: true }), verdict: "insufficient_sample", motif: "median_masked" },
  ];
  for (const { h1, verdict, motif } of cas) {
    const final = verdictFinal({ raw: h1.verdict, explanations, readsThroughput: false, attachment: signal.signal });
    assert.equal(final.verdict, verdict);
    const fiche: ReponseFiche = { ...assemblerService({ explanations, h5: h5vide, final, signal, h1 }), state: "draft" };
    const html = rendre(h(Fiche, { fiche, methodeOuverte: false }), "en");
    assert.match(zoneVerdict(html), new RegExp(`data-verdict="${verdict}"`));
    verifierExplications(html);
    assert.doesNotMatch(html, /fiche-signal/);
    if (motif !== null) assert.match(zoneVerdict(html), new RegExp(`data-motif-code="${motif}"`));
  }
});

test("the sheet styles hold dedicated tokens, no spacing token borrowed for a chart height or a border width", () => {
  const css = readFileSync(`${FRONT}src/styles/styles.css`, "utf8");
  assert.doesNotMatch(css, /calc\(var\(--space-4\) \* 8\)/);
  assert.doesNotMatch(css, /\.fiche-verdict\[[^\]]*\]\s*\{[^}]*var\(--space-/);
  assert.doesNotMatch(css, /\.fiche-signal\s*\{[^}]*border:\s*var\(--space-/);
  assert.match(css, /var\(--fiche-chart-min-height\)/);
});
