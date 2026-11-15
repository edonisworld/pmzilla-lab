// The field of the caller's identifier, in the header of the application (task 19.7, Q67): a pseudonym or a role, with its help, checked
// before it is kept by the browser. The value appears in this field only; nothing is logged.
import { createElement as h, useId, useState } from "react";
import type { ChangeEvent, FormEvent, ReactElement } from "react";
import { useIntl } from "react-intl";

import type { IssueEnregistrement } from "../api/identifiant.ts";

// The catalogue key of each outcome of a save, by literal key (the catalogue test finds every key used in the sources).
const CLES_ISSUE: Record<IssueEnregistrement, "app.identity.saved" | "app.identity.invalid" | "app.identity.unavailable"> = {
  saved: "app.identity.saved",
  invalid: "app.identity.invalid",
  unavailable: "app.identity.unavailable",
};

interface Props {
  // The identifier kept so far, and the save (format check and storage), both injected by the entry of the bundle.
  lire: () => string | undefined;
  ecrire: (valeur: string) => IssueEnregistrement;
}

export function ChampIdentifiant({ lire, ecrire }: Props): ReactElement {
  const intl = useIntl();
  const idAide = useId();
  const idChamp = useId();
  const [valeur, changerValeur] = useState<string>(() => lire() ?? "");
  const [issue, changerIssue] = useState<IssueEnregistrement | null>(null);
  const saisir = (evenement: ChangeEvent<HTMLInputElement>): void => {
    changerValeur(evenement.target.value);
    changerIssue(null);
  };
  const enregistrer = (evenement: FormEvent<HTMLFormElement>): void => {
    evenement.preventDefault();
    changerIssue(ecrire(valeur));
  };
  return h(
    "form",
    { className: "identifiant", onSubmit: enregistrer },
    h(
      "label",
      { className: "langue", htmlFor: idChamp },
      intl.formatMessage({ id: "app.identity.label" }),
      h("input", { id: idChamp, type: "text", value: valeur, onChange: saisir, autoComplete: "off", spellCheck: false, "aria-describedby": idAide }),
    ),
    h("button", { type: "submit", className: "bouton" }, intl.formatMessage({ id: "app.identity.save" })),
    h("p", { id: idAide, className: "tableau-date" }, intl.formatMessage({ id: "app.identity.help" })),
    issue === null ? null : h("p", { role: issue === "saved" ? "status" : "alert", className: "tableau-date" }, intl.formatMessage({ id: CLES_ISSUE[issue] })),
  );
}
