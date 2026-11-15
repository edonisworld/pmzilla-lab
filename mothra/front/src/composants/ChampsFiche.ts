// The fields a sheet's author writes (design D20, D29; task 19.3): the management question, a choice among the four codes of the
// contract shown through their catalogue labels, and the effect and the cause, each with the language it is written in. All three are
// optional in the draft; the review asks for them. Shared by the creation form and the completion of a draft. The refusal of a written
// text (`TEXT_REFUSED`) is shown through the catalogue label of its reason, never with the refused value.
import { createElement as h, useId } from "react";
import type { ChangeEvent, ReactElement } from "react";
import { useIntl } from "react-intl";

import { QUESTIONS_DE_DIRECTION } from "@mothra/contract/listes-fiche";
import type { QuestionDeDirection } from "@mothra/contract/listes-fiche";

import type { ModificationFiche, RaisonTexte, RefusTexte, TexteLibre } from "../api/fiche.ts";
import { CLES_LANGUE, estLangue, LANGUE_PAR_DEFAUT, LANGUES } from "../i18n/langue.ts";

// The catalogue key of each management question of the contract (a closed list).
export const CLES_QUESTION: Record<QuestionDeDirection, string> = {
  scope_growth: "fiche.question.scope_growth",
  scope_reachability: "fiche.question.scope_reachability",
  predictability: "fiche.question.predictability",
  next_version_quality: "fiche.question.next_version_quality",
};

const CLES_RAISON_TEXTE: Record<Exclude<RaisonTexte, "too_long">, string> = {
  ticket_key: "fiche.textRefused.ticket_key",
  email: "fiche.textRefused.email",
  sensitive_name: "fiche.textRefused.sensitive_name",
};

// The language of a written text is one of the front's languages (the only place that names them is the languages module).
type Langue = TexteLibre["lang"];

export interface ValeursChamps {
  question: QuestionDeDirection | "";
  effect: string;
  effectLang: Langue;
  cause: string;
  causeLang: Langue;
}

function langueDe(locale: string): Langue {
  return estLangue(locale) ? locale : LANGUE_PAR_DEFAUT;
}

// The empty form: the language of each text starts as the language of the screen.
export function valeursVides(locale: string): ValeursChamps {
  const lang = langueDe(locale);
  return { question: "", effect: "", effectLang: lang, cause: "", causeLang: lang };
}

// The values of a draft, to start the completion from what it holds.
export function valeursDeFiche(fiche: { managementQuestion?: QuestionDeDirection; effect?: TexteLibre; cause?: TexteLibre }, locale: string): ValeursChamps {
  const vides = valeursVides(locale);
  return {
    question: fiche.managementQuestion ?? "",
    effect: fiche.effect?.text ?? "",
    effectLang: fiche.effect?.lang ?? vides.effectLang,
    cause: fiche.cause?.text ?? "",
    causeLang: fiche.cause?.lang ?? vides.causeLang,
  };
}

// The request fields: an empty or blank field is absent (it is optional in the draft); a text keeps its language.
export function champsDeValeurs(valeurs: ValeursChamps): ModificationFiche {
  const champs: ModificationFiche = {};
  if (valeurs.question !== "") champs.managementQuestion = valeurs.question;
  if (valeurs.effect.trim() !== "") champs.effect = { text: valeurs.effect.trim(), lang: valeurs.effectLang };
  if (valeurs.cause.trim() !== "") champs.cause = { text: valeurs.cause.trim(), lang: valeurs.causeLang };
  return champs;
}

export function RefusTexteFiche({ refus }: { refus: RefusTexte }): ReactElement {
  const intl = useIntl();
  const message =
    refus.reason === "too_long"
      ? intl.formatMessage({ id: "fiche.textRefused.too_long" }, { count: String(refus.count ?? ""), max: String(refus.max ?? "") })
      : intl.formatMessage({ id: CLES_RAISON_TEXTE[refus.reason] });
  return h("p", { role: "alert", className: "fiche-refus", "data-champ-refuse": refus.field }, message);
}

function ChampTexte({
  champ,
  libelle,
  valeur,
  langue,
  surTexte,
  surLangue,
  refus,
}: {
  champ: "effect" | "cause";
  libelle: string;
  valeur: string;
  langue: Langue;
  surTexte: (texte: string) => void;
  surLangue: (langue: Langue) => void;
  refus: RefusTexte | undefined;
}): ReactElement {
  const intl = useIntl();
  const id = useId();
  const idLangue = useId();
  return h(
    "div",
    { className: "fiche-champ" },
    h("label", { htmlFor: id }, intl.formatMessage({ id: libelle })),
    h("textarea", { id, value: valeur, rows: 3, onChange: (e: ChangeEvent<HTMLTextAreaElement>) => surTexte(e.target.value) }),
    // The label is tied to its list by `for`, and does not wrap it: a wrapped list would add its chosen option ("English") to the name (A-07).
    h(
      "div",
      { className: "fiche-champ-langue" },
      h("label", { htmlFor: idLangue }, intl.formatMessage({ id: "fiche.form.lang" })),
      h(
        "select",
        { id: idLangue, value: langue, "data-champ-langue": champ, onChange: (e: ChangeEvent<HTMLSelectElement>) => surLangue(langueDe(e.target.value)) },
        LANGUES.map((code) => h("option", { key: code, value: code }, intl.formatMessage({ id: CLES_LANGUE[code] }))),
      ),
    ),
    refus !== undefined && refus.field === champ ? h(RefusTexteFiche, { refus }) : null,
  );
}

export function ChampsFiche({
  valeurs,
  surChangement,
  refus,
}: {
  valeurs: ValeursChamps;
  surChangement: (valeurs: ValeursChamps) => void;
  refus?: RefusTexte;
}): ReactElement {
  const intl = useIntl();
  const id = useId();
  return h(
    "div",
    { className: "fiche-champs" },
    h("p", { className: "fiche-note" }, intl.formatMessage({ id: "fiche.form.optional" })),
    h(
      "div",
      { className: "fiche-champ" },
      h("label", { htmlFor: id }, intl.formatMessage({ id: "fiche.form.question" })),
      h(
        "select",
        {
          id,
          value: valeurs.question,
          onChange: (e: ChangeEvent<HTMLSelectElement>) => surChangement({ ...valeurs, question: e.target.value as ValeursChamps["question"] }),
        },
        h("option", { value: "" }, intl.formatMessage({ id: "fiche.form.question.none" })),
        QUESTIONS_DE_DIRECTION.map((question) => h("option", { key: question, value: question }, intl.formatMessage({ id: CLES_QUESTION[question] }))),
      ),
    ),
    h(ChampTexte, {
      champ: "effect",
      libelle: "fiche.form.effect",
      valeur: valeurs.effect,
      langue: valeurs.effectLang,
      surTexte: (effect) => surChangement({ ...valeurs, effect }),
      surLangue: (effectLang) => surChangement({ ...valeurs, effectLang }),
      refus,
    }),
    h(ChampTexte, {
      champ: "cause",
      libelle: "fiche.form.cause",
      valeur: valeurs.cause,
      langue: valeurs.causeLang,
      surTexte: (cause) => surChangement({ ...valeurs, cause }),
      surLangue: (causeLang) => surChangement({ ...valeurs, causeLang }),
      refus,
    }),
  );
}
