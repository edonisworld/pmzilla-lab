// The block "Competing explanations" of the conviction page (mothra-demo-habillage D6, D17): a grid of rows, each with the name of the
// explanation, its state as a pill and, when the service gives one, its reason; the state of the attachment signal is the last row of the same
// grid. Only states and reasons are shown, never a measure, so the block reads the same on the full and the reduced form. An unknown name,
// state or reason has a fallback key, never the raw code. The pill of each state is told apart by its fill or outline, never by colour alone.
import { createElement as h } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";
import type { IntlShape } from "react-intl";

import type { ExplicationFiche } from "../api/fiche.ts";
import { CLES_EXPLICATION, CLES_MOTIF, PRESENTATION_ETAT_EXPLICATION } from "./Fiche.ts";
import { Icone } from "./FicheEtats.ts";
import { Mentions } from "./FicheMentions.ts";

export interface PropsExplicationsConcurrentes {
  explications: readonly ExplicationFiche[];
  // The attachment signal: shown, or not; and the reason codes the service gives with it.
  signalMontre: boolean;
  motifsSignal: readonly string[];
}

// The pill class of each state the contract knows; any other state has the neutral pill.
const PASTILLE_ETAT: Record<string, string> = {
  ruled_out: "pastille pastille-ecartee",
  not_ruled_out: "pastille pastille-non-ecartee",
  not_measurable: "pastille pastille-non-mesurable",
};

function nom(intl: IntlShape, code: string): string {
  return intl.formatMessage({ id: Object.hasOwn(CLES_EXPLICATION, code) ? CLES_EXPLICATION[code] : "fiche.explanation.unknown" });
}

function motif(intl: IntlShape, code: string): string {
  return intl.formatMessage({ id: Object.hasOwn(CLES_MOTIF, code) ? CLES_MOTIF[code as keyof typeof CLES_MOTIF] : "fiche.reason.unknown" });
}

function etat(intl: IntlShape, code: string): string {
  return intl.formatMessage({ id: Object.hasOwn(PRESENTATION_ETAT_EXPLICATION, code) ? PRESENTATION_ETAT_EXPLICATION[code as keyof typeof PRESENTATION_ETAT_EXPLICATION].cle : "fiche.reason.unknown" });
}

// The sentence about the attachment signal: shown; or masked when the service gives that reason; or not raised.
function phraseSignal(signalMontre: boolean, motifs: readonly string[]): { cle: string; etat: string } {
  if (signalMontre) return { cle: "fiche.attachmentSignal", etat: "shown" };
  if (motifs.includes("tasks_without_team_share_masked")) return { cle: "fiche.reason.tasks_without_team_share_masked", etat: "masked" };
  return { cle: "fiche.signal.notRaised", etat: "not_raised" };
}

export function ExplicationsConcurrentes({ explications, signalMontre, motifsSignal }: PropsExplicationsConcurrentes): ReactElement {
  const intl = useIntl();
  const signal = phraseSignal(signalMontre, motifsSignal);
  return h(
    "section",
    { className: "explications-concurrentes" },
    h("h2", { className: "explications-titre" }, intl.formatMessage({ id: "fiche.explanations.title" })),
    h("p", { className: "explications-intro" }, intl.formatMessage({ id: "conviction.explanations.intro" })),
    h(
      "ul",
      { className: "explications-liste" },
      explications.map((explication) =>
        h(
          "li",
          { key: explication.name, className: "explication-ligne", "data-explication": explication.name, "data-etat-explication": explication.state },
          h("span", { className: "explication-nom" }, nom(intl, explication.name)),
          h(
            "span",
            { className: Object.hasOwn(PASTILLE_ETAT, explication.state) ? PASTILLE_ETAT[explication.state] : "pastille pastille-neutre" },
            // A state ruled out has a mark besides its outline (hidden from assistive technology: the word keeps the meaning); the other states
            // are told apart by their fill (not ruled out) or by their dashed outline (not measurable).
            explication.state === "ruled_out" ? h(Icone, { nom: "check" }) : null,
            etat(intl, explication.state),
          ),
          h(
            "span",
            { className: "explication-motif" },
            explication.reason === undefined ? null : h("span", { className: "fiche-motif" }, intl.formatMessage({ id: "fiche.reason.line" }, { reason: motif(intl, explication.reason) })),
            // The blocked share rests on current links without history: the mention goes with the explanation when the answer carries its measure.
            explication.name === "dependencies" && explication.measure !== undefined ? h(Mentions, { codes: ["blocked_share_current_links"] }) : null,
          ),
        ),
      ),
      h(
        "li",
        { key: "tasks_attachment", className: "explication-ligne", "data-signal": signal.etat },
        h("span", { className: "explication-nom" }, intl.formatMessage({ id: "fiche.explanation.tasks_attachment" })),
        h("span", { className: "explication-suite" }, h("span", { className: "pastille pastille-neutre" }, intl.formatMessage({ id: signal.cle }))),
      ),
    ),
  );
}
