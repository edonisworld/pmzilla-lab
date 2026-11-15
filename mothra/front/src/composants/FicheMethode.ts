// The method face of an argument sheet (design D20 to D22, D29): method, scope, period, thresholds with the date they were fixed and
// "fixed by the author alone", data date, fingerprint, coverage, masked cells, insufficient samples, quarters left out of the verdict,
// limits, author role, version and attached hypothesis. It shows what the service sends: no figure is derived here. Method, scope,
// period and limits arrive as codes and parameters; the catalogues translate them, and a code they do not know has a fallback key,
// never the raw code on screen.
import { createElement as h, Fragment } from "react";
import type { ReactElement, ReactNode } from "react";
import { useIntl } from "react-intl";
import type { IntlShape } from "react-intl";

import { lireCodeMesure } from "@mothra/contract/listes-fiche";
import type { CodeLimite, CodeMethode, CodeSeuil, ColonneMesure, ETATS_COUVERTURE } from "@mothra/contract/listes-fiche";

import type { GraphiqueFiche } from "@mothra/contract";

import type { ExclusionsH5, LienId, MethodeFiche, Seuil, Trimestre } from "../api/fiche.ts";
import { CelluleDeTableau, CelluleMasquee } from "./Cellule.ts";
import { ECHANTILLON_INSUFFISANT, Icone } from "./FicheEtats.ts";
import { Mentions, mentionsDeColonne } from "./FicheMentions.ts";
import { libelleEquipe } from "./libelleEquipe.ts";
import type { TableauEnMemoire } from "./libelleEquipe.ts";
import { etatDuTrimestre } from "./optionsGraphique.ts";
import { libelleTrimestre } from "./trimestre.ts";
import { valeurSeuil } from "./valeurSeuil.ts";

// The tables below are typed on the lists of the contract (subpath `./listes-fiche`): a code added to a list without its label fails the
// compilation (task 19.3, review B1), and a test (fiche-listes.test.ts) checks that no table holds a code the contract lacks.
export const CLES_MESURE: Record<ColonneMesure, string> = {
  unplanned_share: "fiche.measure.unplanned_share",
  ready: "fiche.measure.ready",
  blocked_share: "fiche.measure.blocked_share",
  cycle_median_days: "fiche.measure.cycle_median_days",
  cycle_p85_days: "fiche.measure.cycle_p85_days",
  throughput: "fiche.measure.throughput",
  tasks_without_team_share: "fiche.measure.tasks_without_team_share",
  lead_median_days: "fiche.measure.lead_median_days",
  lead_p85_days: "fiche.measure.lead_p85_days",
  median_ratio: "fiche.measure.median_ratio",
  p85_ratio: "fiche.measure.p85_ratio",
};

export const CLES_SEUIL: Record<CodeSeuil, string> = {
  h5_band: "fiche.threshold.h5_band",
  h5_double_band: "fiche.threshold.h5_double_band",
  h5_run_rises: "fiche.threshold.h5_run_rises",
  h5_run_min_cumulative_rise: "fiche.threshold.h5_run_min_cumulative_rise",
  h5_floor: "fiche.threshold.h5_floor",
  h5_low_floor: "fiche.threshold.h5_low_floor",
  h1_lower: "fiche.threshold.h1_lower",
  h1_upper: "fiche.threshold.h1_upper",
  attachment_threshold_points: "fiche.threshold.attachment_threshold_points",
  sample_median_min_items: "fiche.threshold.sample_median_min_items",
  sample_p85_min_items: "fiche.threshold.sample_p85_min_items",
};

export const CLES_METHODE: Record<CodeMethode, string> = {
  lead_time_against_cycle_time: "fiche.methodName.lead_time_against_cycle_time",
};

export const CLES_PERIMETRE: Record<string, string> = {
  team: "fiche.scope.team",
  product: "fiche.scope.product",
};

export const CLES_LIMITE: Record<CodeLimite, string> = {
  no_per_team_unplanned_measure: "fiche.limit.no_per_team_unplanned_measure",
  capacity_dependencies_no_adopted_threshold: "fiche.limit.capacity_dependencies_no_adopted_threshold",
  views_last_four_quarters: "fiche.limit.views_last_four_quarters",
  views_last_three_closed_quarters: "fiche.limit.views_last_three_closed_quarters",
  attachment_signal_product_level: "fiche.limit.attachment_signal_product_level",
  throughput_own_past_only: "fiche.limit.throughput_own_past_only",
  reduced_form: "fiche.limit.reduced_form",
};

// The label of each coverage state of the reduced form (D29, D34): the service sends the code, the screen only translates it.
export const CLES_ETAT_COUVERTURE: Record<(typeof ETATS_COUVERTURE)[number], string> = {
  coverage_sufficient: "fiche.coverageState.coverage_sufficient",
  coverage_insufficient: "fiche.coverageState.coverage_insufficient",
  coverage_masked: "fiche.coverageState.coverage_masked",
};

export const CLES_LIEN: Record<LienId, string> = {
  h1_first_half: "fiche.link.h1_first_half",
  h1_second_half: "fiche.link.h1_second_half",
  h2: "fiche.link.h2",
  h3: "fiche.link.h3",
  h4: "fiche.link.h4",
  h5: "fiche.link.h5",
};

export const CLES_ROLE: Record<string, string> = { agile_lead: "fiche.role.agile_lead" };

export const CLES_FIXE_PAR: Record<Seuil["fixedBy"], string> = { author_alone: "fiche.fixedBy.author_alone" };

// The statistics whose quarters the service leaves out of the verdict, with the catalogue key of each.
const STATISTIQUES_EXCLUES: Array<[keyof ExclusionsH5, string]> = [
  ["median", "fiche.excluded.median"],
  ["p85", "fiche.excluded.p85"],
  ["throughput", "fiche.excluded.throughput"],
];

// A code translated by its table; a code the table does not know shows the fallback key, never itself.
function traduit(intl: IntlShape, cles: Record<string, string>, code: string, repli: string, valeurs?: Record<string, string>): string {
  return intl.formatMessage({ id: Object.hasOwn(cles, code) ? cles[code] : repli }, valeurs);
}

function date(intl: IntlShape, iso: string): string {
  return intl.formatDate(iso, { dateStyle: "medium", timeZone: "UTC" });
}

// A measure code of the body is `<column>@<quarter start>` or `<column>@pooled_year` (read by the contract's reader, never by hand);
// a code with no `@` is looked up as it is.
function mesure(intl: IntlShape, code: string): string {
  const lue = lireCodeMesure(code);
  if (lue === null) return traduit(intl, CLES_MESURE, code, "fiche.measure.unknown");
  const nom = traduit(intl, CLES_MESURE, lue.column, "fiche.measure.unknown");
  return lue.when === "pooled_year"
    ? intl.formatMessage({ id: "fiche.measure.atPooledYear" }, { measure: nom })
    : intl.formatMessage({ id: "fiche.measure.atQuarter" }, { measure: nom, date: date(intl, lue.when) });
}

// A measure code of the body with its mentions (D35): the cycle time carries `cycle_time_includes_ready_queue`, the blocked share its
// two labels; any other measure carries none.
function MesureAvecMentions({ code }: { code: string }): ReactElement {
  const intl = useIntl();
  const colonne = lireCodeMesure(code)?.column ?? code;
  return h(Fragment, null, mesure(intl, code), " ", h(Mentions, { codes: mentionsDeColonne(colonne) }));
}

// A quarter formatted by the front from its year and number; the parameters are given as text so that no digit grouping applies.
function trimestre(intl: IntlShape, quarter: Trimestre | undefined): string {
  if (quarter === undefined || !Number.isInteger(quarter.year) || ![1, 2, 3, 4].includes(quarter.quarter)) {
    return intl.formatMessage({ id: "fiche.quarter.unknown" });
  }
  return intl.formatMessage({ id: "fiche.quarter" }, { quarter: String(quarter.quarter), year: String(quarter.year) });
}

function periode(intl: IntlShape, trimestres: Trimestre[]): string {
  if (trimestres.length === 0) return intl.formatMessage({ id: "fiche.method.none" });
  const debut = trimestre(intl, trimestres[0]);
  const fin = trimestre(intl, trimestres[trimestres.length - 1]);
  return trimestres.length === 1 ? intl.formatMessage({ id: "fiche.period.single" }, { quarter: debut }) : intl.formatMessage({ id: "fiche.period.range" }, { from: debut, to: fin });
}

function ligne(intl: IntlShape, cle: string, valeur: ReactNode): ReactElement {
  return h("div", { key: cle, className: "fiche-ligne" }, h("dt", null, intl.formatMessage({ id: cle })), h("dd", null, valeur));
}

function liste(intl: IntlShape, elements: string[]): ReactNode {
  if (elements.length === 0) return intl.formatMessage({ id: "fiche.method.none" });
  return h("ul", null, elements.map((element, rang) => h("li", { key: rang }, element)));
}

function Seuils({ methode }: { methode: MethodeFiche }): ReactElement {
  const intl = useIntl();
  return h(
    "div",
    { className: "fiche-seuils" },
    h("p", null, intl.formatMessage({ id: "fiche.method.thresholdsStatement" }, { date: date(intl, methode.thresholdsFixedOn) })),
    h(
      "table",
      { className: "tableau", "data-tableau": "seuils" },
      h(
        "thead",
        null,
        h(
          "tr",
          null,
          ["fiche.column.threshold", "fiche.column.value", "fiche.column.fixedOn", "fiche.column.fixedBy"].map((cle) =>
            h("th", { key: cle, scope: "col" }, intl.formatMessage({ id: cle })),
          ),
        ),
      ),
      h(
        "tbody",
        null,
        methode.thresholds.map((seuil) =>
          h(
            "tr",
            { key: seuil.code },
            h(
              "td",
              { className: "cellule" },
              traduit(intl, CLES_SEUIL, seuil.code, "fiche.threshold.unknown"),
              seuil.modifiedAfterReading === undefined
                ? null
                : h(
                    "p",
                    { className: "fiche-seuil-modifie" },
                    intl.formatMessage(
                      { id: "fiche.thresholdModifiedLine" },
                      { value: valeurSeuil(intl, seuil.code, seuil.modifiedAfterReading.formerValue), date: date(intl, seuil.modifiedAfterReading.formerDate) },
                    ),
                  ),
            ),
            h("td", { className: "cellule cellule-valeur" }, valeurSeuil(intl, seuil.code, seuil.value)),
            h("td", { className: "cellule" }, date(intl, seuil.fixedOn)),
            h("td", { className: "cellule" }, intl.formatMessage({ id: CLES_FIXE_PAR[seuil.fixedBy] })),
          ),
        ),
      ),
    ),
  );
}

// The statement of the confidentiality threshold: counts and statistics alike (D22), stated once per table.
function legendeSeuil(intl: IntlShape, seuil: number): ReactElement {
  return h("p", { className: "tableau-seuil" }, intl.formatMessage({ id: "fiche.maskedThreshold" }, { threshold: seuil }));
}

function CellulesMasquees({ methode }: { methode: MethodeFiche }): ReactElement {
  const intl = useIntl();
  if (methode.maskedCells.length === 0) return h("p", null, intl.formatMessage({ id: "fiche.method.none" }));
  const seuils = new Set(methode.maskedCells.map((c) => c.cell.threshold));
  // One threshold for the whole table: stated once. Several: no statement that would be wrong for a row, each row shows its own.
  const commun = seuils.size === 1 ? methode.maskedCells[0].cell.threshold : undefined;
  const colonnes = ["fiche.column.measure", "cellState.masked", ...(commun === undefined ? ["fiche.column.threshold"] : [])];
  return h(
    "div",
    // The scrolling container is reached by the keyboard (A-85).
    { className: "tableau-conteneur", tabIndex: 0 },
    commun === undefined ? null : legendeSeuil(intl, commun),
    h(
      "table",
      { className: "tableau", "data-tableau": "masquees" },
      h("thead", null, h("tr", null, colonnes.map((cle) => h("th", { key: cle, scope: "col" }, intl.formatMessage({ id: cle }))))),
      h(
        "tbody",
        null,
        methode.maskedCells.map(({ measure, cell }) =>
          h(
            "tr",
            { key: measure },
            h("td", { className: "cellule" }, h(MesureAvecMentions, { code: measure })),
            h(CelluleMasquee),
            commun === undefined ? h("td", { className: "cellule cellule-valeur" }, intl.formatNumber(cell.threshold)) : null,
          ),
        ),
      ),
    ),
  );
}

function Couverture({ methode }: { methode: MethodeFiche }): ReactElement {
  const intl = useIntl();
  const couverture = methode.coverage;
  // The reduced form (D34) holds the coverage state, computed by the service, and no count.
  if (couverture === undefined) {
    const etat = methode.coverageState;
    return h("p", { "data-etat-couverture": etat }, traduit(intl, CLES_ETAT_COUVERTURE, etat ?? "", "fiche.coverageState.unknown"));
  }
  return h(
    Fragment,
    null,
    h("table", { className: "tableau" }, h("tbody", null, h("tr", null, h(CelluleDeTableau, { valeur: couverture })))),
    couverture.state === "masked" ? legendeSeuil(intl, couverture.threshold) : null,
  );
}

function EchantillonsInsuffisants({ methode }: { methode: MethodeFiche }): ReactElement {
  const intl = useIntl();
  if (methode.insufficientSamples.length === 0) return h("p", null, intl.formatMessage({ id: "fiche.method.noneMasculine" }));
  return h(
    "table",
    { className: "tableau", "data-tableau": "insuffisants" },
    h(
      "thead",
      null,
      h("tr", null, ["fiche.column.measure", ECHANTILLON_INSUFFISANT.cle].map((cle) => h("th", { key: cle, scope: "col" }, intl.formatMessage({ id: cle })))),
    ),
    h(
      "tbody",
      null,
      methode.insufficientSamples.map((code) =>
        h(
          "tr",
          { key: code },
          h("td", { className: "cellule" }, h(MesureAvecMentions, { code })),
          h(
            "td",
            { className: "cellule cellule-insuffisante", "data-state": "insufficient" },
            h(Icone, { nom: ECHANTILLON_INSUFFISANT.icone }),
            intl.formatMessage({ id: ECHANTILLON_INSUFFISANT.cle }),
          ),
        ),
      ),
    ),
  );
}

// The quarters of the chart whose lead time or cycle time is an insufficient sample (A-08), as the service sent them; the pooled year is not a
// quarter. Nothing is computed: the state of each point is read, with the rule that draws the chart (`etatDuTrimestre`), so that a quarter drawn
// as masked is never listed as insufficient. Without a chart, or without such a quarter, there is no line.
function trimestresEnEchantillonInsuffisant(intl: IntlShape, graphique: GraphiqueFiche | undefined): string[] {
  const formater = (id: string, valeurs: { year: string; quarter: string }): string => intl.formatMessage({ id }, valeurs);
  return (graphique?.quarters ?? [])
    .filter((point) => etatDuTrimestre(point) === "insufficient_sample")
    .map((point) => libelleTrimestre(point.quarter, formater));
}

// The quarters the service left out of each statistic, by position in the quarters of the sheet, formatted as quarters.
function TrimestresEcartes({ methode }: { methode: MethodeFiche }): ReactElement {
  const intl = useIntl();
  return h(
    "ul",
    { className: "fiche-ecartes" },
    STATISTIQUES_EXCLUES.map(([statistique, cle]) => {
      const positions = methode.excluded[statistique];
      const quarters = positions.length === 0 ? intl.formatMessage({ id: "fiche.method.none" }) : intl.formatList(positions.map((rang) => trimestre(intl, methode.period.quarters[rang])));
      return h("li", { key: statistique }, intl.formatMessage({ id: "fiche.excluded.line" }, { statistic: intl.formatMessage({ id: cle }), quarters }));
    }),
  );
}

// The level comes from the catalogue; the team is rendered as a datum, not as a translated word, and shown as the rest of the screen shows it:
// `libelleEquipe` decides between the opaque identifier and the name (A-08, R-20261107-23, R-20261107-33 point 8), never the internal code of
// the scope ("team.<identifier>"). A scope that is not a team with an opaque identifier shows the level alone.
function Perimetre({ methode, tableau }: { methode: MethodeFiche; tableau?: TableauEnMemoire }): ReactElement {
  const intl = useIntl();
  const niveau = traduit(intl, CLES_PERIMETRE, methode.scope.level, "fiche.scope.unknown");
  if (methode.scope.level !== "team") return h(Fragment, null, niveau);
  const equipe = libelleEquipe(methode, tableau);
  if (equipe === undefined) return h(Fragment, null, niveau);
  return h(Fragment, null, niveau, " ", h("data", { value: equipe }, equipe));
}

// `jeu` is the dataset code the service sent with the answer: the notice is shown from it when the data are synthetic (D34), never computed.
// `graphique` is the chart figures of the sheet, when it carries them: the line of the quarters in insufficient sample reads it (A-08).
// `tableau` is the dashboard answer in memory, when the page holds it: the scope line shows the team as the header of the sheet does.
export function FicheMethode({ methode, id, jeu, graphique, tableau }: { methode: MethodeFiche; id: string; jeu?: string; graphique?: GraphiqueFiche; tableau?: TableauEnMemoire }): ReactElement {
  const intl = useIntl();
  const insuffisants = trimestresEnEchantillonInsuffisant(intl, graphique);
  return h(
    "section",
    { className: "fiche-methode", id },
    h("h3", null, intl.formatMessage({ id: "fiche.method.title" })),
    jeu === "synthetic" ? h("p", { role: "note", className: "fiche-jeu-synthetique", "data-jeu": "synthetic" }, intl.formatMessage({ id: "fiche.syntheticNotice" })) : null,
    h(
      "dl",
      null,
      ligne(intl, "fiche.method.method", traduit(intl, CLES_METHODE, methode.method, "fiche.methodName.unknown")),
      ligne(intl, "fiche.method.scope", h(Perimetre, { methode, tableau })),
      ligne(intl, "fiche.method.period", periode(intl, methode.period.quarters)),
      ligne(intl, "fiche.method.thresholds", h(Seuils, { methode })),
      ligne(intl, "fiche.method.dataDate", date(intl, methode.dataDate)),
      ligne(intl, "fiche.method.fingerprint", h("code", null, methode.fingerprint)),
      ligne(intl, "fiche.method.coverage", h(Couverture, { methode })),
      ligne(intl, "fiche.method.maskedCells", h(CellulesMasquees, { methode })),
      ligne(intl, "fiche.method.insufficientSamples", h(EchantillonsInsuffisants, { methode })),
      insuffisants.length === 0 ? null : ligne(intl, "fiche.method.insufficientQuarters", intl.formatList(insuffisants)),
      ligne(intl, "fiche.method.excluded", h(TrimestresEcartes, { methode })),
      ligne(intl, "fiche.method.limits", liste(intl, methode.limits.map((limite) => traduit(intl, CLES_LIMITE, limite, "fiche.limit.unknown")))),
      ligne(intl, "fiche.method.authorRole", traduit(intl, CLES_ROLE, methode.authorRole, "fiche.role.other")),
      ligne(intl, "fiche.method.version", intl.formatMessage({ id: "fiche.versionNumber" }, { number: methode.version })),
      ligne(intl, "fiche.method.hypothesis", traduit(intl, CLES_LIEN, methode.hypothesis, "fiche.link.unknown")),
    ),
  );
}
