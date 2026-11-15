// The argument sheet screen (design D20 to D22, D29, D33; task 19.3). Management face: effect, cause, the verdict as the service computed
// it (never typed) with its reasons and the signal of tasks without a team next to it, the three competing explanations with their state
// and reason, the throughput part, and a reserved chart area (the chart comes with ECharts, task 19.1). Method face: one click away.
// The screen shows what it receives: it computes no verdict, no state of an explanation, no share and no signal, calls no network and
// holds no field to type in. A published sheet is frozen: nothing editable remains.
import { Children, createElement as h, Fragment, useId, useState } from "react";
import type { ReactElement, ReactNode } from "react";
import { useIntl } from "react-intl";
import type { IntlShape } from "react-intl";

import type { EtatExplication, EtatFiche, ExplicationFiche, ModificationFiche, Part, RaisonVerdict, RefusTexte, ReponseFiche, ResultatAction, ResultatCompletion, TexteLibre } from "../api/fiche.ts";
import type { EXPLICATIONS_DE_FICHE, MotifDeFiche, POSITIONS_DEBIT, QuestionDeDirection } from "@mothra/contract/listes-fiche";
import { cleErreur } from "../api/vue.ts";
import { ChampsFiche, champsDeValeurs, CLES_QUESTION, valeursDeFiche } from "./ChampsFiche.ts";
import type { ValeursChamps } from "./ChampsFiche.ts";
import { FicheMethode } from "./FicheMethode.ts";
import { Mentions, MENTIONS_CYCLE_TIME, MENTIONS_PART_BLOQUEE } from "./FicheMentions.ts";
import { ECHANTILLON_INSUFFISANT, Icone, presentationVerdict } from "./FicheEtats.ts";

export const CLES_ETAT_FICHE: Record<EtatFiche, string> = {
  draft: "fiche.state.draft",
  reviewed: "fiche.state.reviewed",
  published: "fiche.state.published",
};

// The catalogue key of each explanation the service names, the attachment signal included; an unknown name has a fallback key.
const CLES_EXPLICATION_CONTRAT: Record<(typeof EXPLICATIONS_DE_FICHE)[number], string> = {
  unplanned_work: "fiche.explanation.unplanned_work",
  capacity: "fiche.explanation.capacity",
  dependencies: "fiche.explanation.dependencies",
};

export const CLES_EXPLICATION: Record<string, string> = {
  ...CLES_EXPLICATION_CONTRAT,
  tasks_attachment: "fiche.explanation.tasks_attachment",
};

export const PRESENTATION_ETAT_EXPLICATION: Record<EtatExplication, { cle: string; classes: string }> = {
  ruled_out: { cle: "fiche.explanationState.ruled_out", classes: "fiche-explication fiche-explication-ecartee" },
  not_ruled_out: { cle: "fiche.explanationState.not_ruled_out", classes: "fiche-explication fiche-explication-non-ecartee" },
  not_measurable: { cle: "fiche.explanationState.not_measurable", classes: "fiche-explication fiche-explication-non-mesurable" },
};

// The catalogue key of each reason code of the service (explanations, hypothesis 1, hypothesis 5, signal); an unknown code has a fallback key.
export const CLES_MOTIF: Record<MotifDeFiche, string> = {
  defects_without_team: "fiche.reason.defects_without_team",
  no_adopted_threshold: "fiche.reason.no_adopted_threshold",
  masked: "fiche.reason.masked",
  no_data: "fiche.reason.no_data",
  median_masked: "fiche.reason.median_masked",
  median_insufficient_sample: "fiche.reason.median_insufficient_sample",
  p85_masked: "fiche.reason.p85_masked",
  p85_insufficient_sample: "fiche.reason.p85_insufficient_sample",
  throughput_masked: "fiche.reason.throughput_masked",
  tasks_without_team_share_masked: "fiche.reason.tasks_without_team_share_masked",
};

// A message with elements among its values, as one node: one ICU message per line, never pieces glued together.
function message(intl: IntlShape, id: string, valeurs: Record<string, ReactNode>): ReactElement {
  return h(Fragment, null, Children.toArray(intl.formatMessage({ id }, valeurs)));
}

function libelleExplication(intl: IntlShape, nom: string): string {
  return intl.formatMessage({ id: Object.hasOwn(CLES_EXPLICATION, nom) ? CLES_EXPLICATION[nom] : "fiche.explanation.unknown" });
}

function motif(intl: IntlShape, code: string): string {
  return intl.formatMessage({ id: Object.hasOwn(CLES_MOTIF, code) ? CLES_MOTIF[code as MotifDeFiche] : "fiche.reason.unknown" });
}

function etatExplication(intl: IntlShape, etat: EtatExplication): string {
  return intl.formatMessage({ id: Object.hasOwn(PRESENTATION_ETAT_EXPLICATION, etat) ? PRESENTATION_ETAT_EXPLICATION[etat].cle : "fiche.reason.unknown" });
}

// Free text with its own language: marked with `lang` when it is not the language of the screen.
function TexteLangue({ texte }: { texte: TexteLibre | undefined }): ReactElement {
  const intl = useIntl();
  if (texte === undefined) return h("span", { className: "fiche-champ-absent" }, intl.formatMessage({ id: "fiche.text.missing" }));
  return h("span", { lang: texte.lang === intl.locale ? undefined : texte.lang }, texte.text);
}

// An absent question has the missing-field label.
function libelleQuestion(intl: IntlShape, question: QuestionDeDirection | undefined): string {
  return intl.formatMessage({ id: question !== undefined && Object.hasOwn(CLES_QUESTION, question) ? CLES_QUESTION[question] : "fiche.text.missing" });
}

// A share is a percentage from 0 to 100, shown as received.
function Partie({ part }: { part: Part }): ReactElement {
  const intl = useIntl();
  if (part.state === "masked") return h("span", { className: "fiche-part-masquee", "data-state": "masked" }, intl.formatMessage({ id: "cellState.masked" }));
  if (part.state === "insufficient_sample") {
    return h(
      "span",
      { className: "fiche-part-insuffisante", "data-state": "insufficient" },
      h(Icone, { nom: ECHANTILLON_INSUFFISANT.icone }),
      intl.formatMessage({ id: ECHANTILLON_INSUFFISANT.cle }),
    );
  }
  return h("span", { className: "fiche-part-valeur", "data-state": "value" }, intl.formatMessage({ id: "fiche.share.value" }, { value: part.value }));
}

function LigneExplication({ explication, partProduit }: { explication: ExplicationFiche; partProduit?: Part }): ReactElement {
  const intl = useIntl();
  const presentation = PRESENTATION_ETAT_EXPLICATION[explication.state];
  return h(
    "li",
    { className: presentation.classes, "data-explication": explication.name, "data-etat-explication": explication.state },
    h(
      "p",
      null,
      message(intl, "fiche.explanation.line", {
        name: h("strong", null, libelleExplication(intl, explication.name)),
        state: h("span", { className: "fiche-etat-explication" }, etatExplication(intl, explication.state)),
      }),
    ),
    explication.reason === undefined ? null : h("p", { className: "fiche-motif" }, intl.formatMessage({ id: "fiche.reason.line" }, { reason: motif(intl, explication.reason) })),
    partProduit === undefined ? null : h("p", { className: "fiche-part" }, message(intl, "fiche.unplannedShare.line", { share: h(Partie, { part: partProduit }) })),
    // The blocked share (D35): the explanation of the dependencies rests on it; it never appears without its two labels.
    explication.name === "dependencies"
      ? h(
          "p",
          { className: "fiche-part" },
          explication.measure === undefined
            ? null
            : message(intl, "fiche.explanation.measureLine", {
                measure: intl.formatMessage({ id: "fiche.measure.blocked_share" }),
                value: h(Partie, { part: explication.measure }),
              }),
          h(Mentions, { codes: MENTIONS_PART_BLOQUEE }),
        )
      : null,
  );
}

// A reason of the verdict as the service returns it: the explanation and its state, and the specific reason when it is not the
// explanation's own name (the service falls back on the name). The attachment signal has its own sentence, shown once.
function LigneRaison({ raison }: { raison: RaisonVerdict }): ReactElement {
  const intl = useIntl();
  const valeurs = { name: h("strong", null, libelleExplication(intl, raison.explanation)), state: h("span", null, etatExplication(intl, raison.state)) };
  // One ICU message per line, with or without the reason: the pieces are never glued together.
  return h(
    "li",
    { className: "fiche-raison", "data-raison": raison.explanation },
    raison.reason === raison.explanation
      ? message(intl, "fiche.explanation.line", valeurs)
      : message(intl, "fiche.explanation.lineWithReason", { ...valeurs, reason: h("span", { className: "fiche-motif" }, motif(intl, raison.reason)) }),
  );
}

function ZoneVerdict({ fiche }: { fiche: ReponseFiche }): ReactElement {
  const intl = useIntl();
  const presentation = presentationVerdict(fiche.verdict);
  const raisons = fiche.verdictReasons.filter((raison) => raison.explanation !== "tasks_attachment");
  const motifs: string[] = [...fiche.h1Reasons, ...fiche.h5Reasons, ...fiche.attachmentSignalReasons];
  return h(
    "section",
    { className: "fiche-verdict-zone" },
    h("h3", null, intl.formatMessage({ id: "fiche.verdict.label" })),
    h(
      "p",
      { className: presentation.classes, "data-verdict": fiche.verdict, "data-contour": presentation.contour },
      h(Icone, { nom: presentation.icone }),
      h("span", null, intl.formatMessage({ id: presentation.cle })),
    ),
    h("p", { className: "fiche-note" }, intl.formatMessage({ id: "fiche.verdict.computed" })),
    raisons.length === 0 && motifs.length === 0
      ? null
      : h(
          "div",
          { className: "fiche-raisons" },
          h("h4", null, intl.formatMessage({ id: "fiche.reasons.title" })),
          h(
            "ul",
            null,
            raisons.map((raison) => h(LigneRaison, { key: `${raison.explanation}:${raison.reason}`, raison })),
            motifs.map((code) => h("li", { key: code, className: "fiche-raison", "data-motif-code": code }, intl.formatMessage({ id: "fiche.reason.line" }, { reason: motif(intl, code) }))),
          ),
        ),
    fiche.attachmentSignalShown ? h("p", { role: "note", className: "fiche-signal" }, intl.formatMessage({ id: "fiche.attachmentSignal" })) : null,
    // The reduced form states the signal as a state of its own (D34): shown when it is not raised and not masked, from the code the service sent.
    estReduite(fiche) && fiche.method.hypothesis === "h5" && !fiche.attachmentSignalShown && fiche.attachmentSignalReasons.length === 0
      ? h("p", { className: "fiche-signal-absent", "data-signal": "not_raised" }, intl.formatMessage({ id: "fiche.signal.notRaised" }))
      : null,
    fiche.dataset === "synthetic"
      ? h("p", { role: "note", className: "fiche-jeu-synthetique", "data-jeu": "synthetic" }, intl.formatMessage({ id: "fiche.syntheticNotice" }))
      : null,
  );
}

// The reduced form of D34 is recognised by what the service sent: the coverage state in place of the coverage count.
function estReduite(fiche: ReponseFiche): boolean {
  return fiche.method.coverage === undefined && fiche.method.coverageState !== undefined;
}

// The catalogue key of each throughput position the service sends (D29, D34); a position the table does not know has a fallback key.
const CLES_POSITION: Record<(typeof POSITIONS_DEBIT)[number], string> = {
  throughput_within_band: "fiche.position.throughput_within_band",
  throughput_under_floor: "fiche.position.throughput_under_floor",
  throughput_under_low_floor: "fiche.position.throughput_under_low_floor",
  masked: "fiche.position.masked",
};

function Positions({ positions }: { positions: NonNullable<ReponseFiche["throughputPositions"]> }): ReactElement | null {
  const intl = useIntl();
  if (positions.length === 0) return null;
  return h(
    "div",
    { className: "fiche-positions" },
    h("h4", null, intl.formatMessage({ id: "fiche.positions.title" })),
    h(
      "ul",
      null,
      positions.map((p) =>
        h(
          "li",
          { key: p.quarter, "data-position": p.position },
          message(intl, "fiche.positions.line", {
            quarter: h("data", { value: p.quarter }, p.quarter),
            position: intl.formatMessage({ id: Object.hasOwn(CLES_POSITION, p.position) ? CLES_POSITION[p.position] : "fiche.position.unknown" }),
          }),
        ),
      ),
    ),
  );
}

// The refusal of a review or a publication: the translated message of its code, never the code.
export function RefusAction({ code }: { code: string }): ReactElement {
  const intl = useIntl();
  return h("p", { role: "alert", className: "fiche-refus" }, intl.formatMessage({ id: cleErreur(code) }));
}

// Runs the review or publication action wired by the caller and hands the refusal code, if any, to the screen; a success clears it.
// A rejection (or a throw) of the action is shown as the internal error, never left unhandled.
export async function lancerAction(action: () => ResultatAction | Promise<ResultatAction>, definirRefus: (code: string | undefined) => void): Promise<void> {
  try {
    const resultat = await action();
    definirRefus(resultat.ok ? undefined : resultat.code);
  } catch {
    definirRefus("INTERNAL");
  }
}

// The refusal of a completion: the code of the answer and, for `TEXT_REFUSED`, the field and the reason (never the refused value).
export interface RefusCompletion {
  code: string;
  texte?: RefusTexte;
}

// Runs the completion wired by the caller (PATCH /api/sheets/:id) and hands the refusal, if any, to the panel; a success clears it. A
// rejection of the action is shown as the internal error.
export async function lancerCompletion(
  action: () => ResultatCompletion | Promise<ResultatCompletion>,
  definirRefus: (refus: RefusCompletion | undefined) => void,
): Promise<void> {
  try {
    const resultat = await action();
    if (resultat.ok) definirRefus(undefined);
    else definirRefus(resultat.texte === undefined ? { code: resultat.code } : { code: resultat.code, texte: resultat.texte });
  } catch {
    definirRefus({ code: "INTERNAL" });
  }
}

// What the button of the completion does: the values of the form become the request fields, handed to the route wired by the caller.
export function envoyerCompletion(
  valeurs: ValeursChamps,
  onCompleter: (modification: ModificationFiche) => ResultatCompletion | Promise<ResultatCompletion>,
  definirRefus: (refus: RefusCompletion | undefined) => void,
): Promise<void> {
  return lancerCompletion(() => onCompleter(champsDeValeurs(valeurs)), definirRefus);
}

// The completion of a draft: the three fields of the creation form, started from what the draft holds, then sent to the route.
function CompletionBrouillon({
  fiche,
  onCompleter,
  refusInitial,
}: {
  fiche: ReponseFiche;
  onCompleter: (modification: ModificationFiche) => ResultatCompletion | Promise<ResultatCompletion>;
  refusInitial: RefusCompletion | undefined;
}): ReactElement {
  const intl = useIntl();
  const [valeurs, setValeurs] = useState<ValeursChamps>(() => valeursDeFiche(fiche, intl.locale));
  const [refus, setRefus] = useState<RefusCompletion | undefined>(refusInitial);
  return h(
    "section",
    { className: "fiche-completion", "data-completion": "brouillon" },
    h("h3", null, intl.formatMessage({ id: "fiche.complete.title" })),
    h(ChampsFiche, { valeurs, surChangement: setValeurs, refus: refus?.texte }),
    h(
      "button",
      {
        type: "button",
        className: "fiche-bouton",
        onClick: () => {
          void envoyerCompletion(valeurs, onCompleter, setRefus);
        },
      },
      intl.formatMessage({ id: "fiche.action.complete" }),
    ),
    // A refused text is shown beside its field; any other refusal by the translated label of its code.
    refus === undefined || refus.texte !== undefined ? null : h(RefusAction, { code: refus.code }),
  );
}

export interface PropsFiche {
  fiche: ReponseFiche;
  // The completion of a draft, wired by the caller (PATCH /api/sheets/:id); offered to the author of the draft only (`estAuteur`) and
  // never on a reviewed or a published sheet.
  estAuteur?: boolean;
  onCompleter?: (modification: ModificationFiche) => ResultatCompletion | Promise<ResultatCompletion>;
  // A completion refusal already received, for tests and for a screen that reopens on one.
  refusCompletionInitial?: RefusCompletion;
  // The method face starts closed; the argument is for tests and for a screen that opens it directly.
  methodeOuverte?: boolean;
  // Wired by the caller (group 18) when the signed-in Agile Lead may review or publish; never offered on a published sheet. They give
  // back the result of the route: success, or the refusal code the screen shows translated.
  onRelire?: () => ResultatAction | Promise<ResultatAction>;
  onPublier?: () => ResultatAction | Promise<ResultatAction>;
  // A refusal already received, for tests and for a screen that reopens on one.
  refusInitial?: string;
}

export function Fiche({ fiche, methodeOuverte = false, onRelire, onPublier, refusInitial, estAuteur = false, onCompleter, refusCompletionInitial }: PropsFiche): ReactElement {
  const intl = useIntl();
  const idMethode = useId();
  const [ouverte, setOuverte] = useState(methodeOuverte);
  const [refus, setRefus] = useState<string | undefined>(refusInitial);
  const figee = fiche.state === "published";
  const bouton = (cle: string, action: () => ResultatAction | Promise<ResultatAction>): ReactElement =>
    h(
      "button",
      {
        type: "button",
        className: "fiche-bouton",
        onClick: () => {
          void lancerAction(action, setRefus);
        },
      },
      intl.formatMessage({ id: cle }),
    );
  const action =
    fiche.state === "draft" && onRelire !== undefined
      ? bouton("fiche.action.review", onRelire)
      : fiche.state === "reviewed" && onPublier !== undefined
        ? bouton("fiche.action.publish", onPublier)
        : null;
  return h(
    "article",
    { className: "fiche", "data-figee": figee ? "true" : undefined },
    h(
      "header",
      { className: "fiche-entete" },
      h("h2", null, intl.formatMessage({ id: "fiche.title" })),
      h(
        "p",
        { className: "fiche-etat-ligne" },
        message(intl, "fiche.state.line", {
          state: h("span", { className: "fiche-etat", "data-etat-fiche": fiche.state }, intl.formatMessage({ id: CLES_ETAT_FICHE[fiche.state] })),
        }),
      ),
      figee && fiche.publishedOn !== undefined
        ? h("p", { className: "fiche-publiee-le" }, intl.formatMessage({ id: "fiche.publishedOn" }, { date: intl.formatDate(fiche.publishedOn, { dateStyle: "medium", timeZone: "UTC" }) }))
        : null,
      figee ? h("p", { className: "fiche-figee-note" }, intl.formatMessage({ id: "fiche.frozen" })) : null,
    ),
    h(
      "div",
      { className: "fiche-direction" },
      h("p", null, message(intl, "fiche.effect.line", { text: h(TexteLangue, { texte: fiche.effect }) })),
      h("p", null, message(intl, "fiche.cause.line", { text: h(TexteLangue, { texte: fiche.cause }) })),
      h("p", null, intl.formatMessage({ id: "fiche.question.line" }, { text: libelleQuestion(intl, fiche.managementQuestion) })),
      h("div", { className: "fiche-graphique", "data-emplacement": "graphique" }, intl.formatMessage({ id: "fiche.chart.reserved" })),
      // The chart shows the lead time and the cycle time: the mention sits next to it, not only on the method face (D35).
      h("p", { className: "fiche-note" }, h(Mentions, { codes: MENTIONS_CYCLE_TIME })),
      h(ZoneVerdict, { fiche }),
      h(
        "section",
        { className: "fiche-explications" },
        h("h3", null, intl.formatMessage({ id: "fiche.explanations.title" })),
        h(
          "ul",
          null,
          fiche.explanations.map((explication) =>
            h(LigneExplication, {
              key: explication.name,
              explication,
              partProduit: explication.name === "unplanned_work" ? fiche.unplannedProductShare : undefined,
            }),
          ),
        ),
      ),
      h(
        "section",
        { className: "fiche-debit" },
        fiche.tasksWithoutTeamShare === undefined
          ? null
          : h("p", null, message(intl, "fiche.tasksWithoutTeamShare.line", { share: h(Partie, { part: fiche.tasksWithoutTeamShare }) })),
        fiche.throughputPositions === undefined ? null : h(Positions, { positions: fiche.throughputPositions }),
        h("p", null, intl.formatMessage({ id: "fiche.throughputOwnPastOnly" })),
      ),
    ),
    h(
      "button",
      { type: "button", className: "fiche-bouton", "aria-expanded": ouverte, "aria-controls": ouverte ? idMethode : undefined, onClick: () => setOuverte(!ouverte) },
      intl.formatMessage({ id: ouverte ? "fiche.method.hide" : "fiche.method.show" }),
    ),
    ouverte ? h(FicheMethode, { methode: fiche.method, id: idMethode, jeu: fiche.dataset, graphique: fiche.chart }) : null,
    fiche.state === "draft" && estAuteur && onCompleter !== undefined
      ? h(CompletionBrouillon, { fiche, onCompleter, refusInitial: refusCompletionInitial })
      : null,
    action,
    refus === undefined ? null : h(RefusAction, { code: refus }),
  );
}
