// The disabled choice with its reason (mothra-demo-habillage D17, D18, lot 3d): an option of a form that exists but cannot be taken, shown
// disabled (never hidden, never enabled) with a sentence of the catalogue that says why, linked to the option by `aria-describedby`. The
// reason sits outside the label, so the option's accessible name stays its own label and the reason is read as its description. Nothing is
// sent for a disabled option: the input is disabled and carries no checked state.
// Replaces: the hypothesis 5 choice hidden on real data. Removal: with the filter of `graphiquesOfferts`, by the author's decision on F-H5 on
// real data (R-20261031-18).
import { createElement as h, useId } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";

export interface PropsChoixDesactive {
  // The name of the radio group and the value of the option.
  nom: string;
  valeur: string;
  // The catalogue keys of the option's label and of its reason.
  libelle: string;
  raison: string;
}

export function ChoixDesactive({ nom, valeur, libelle, raison }: PropsChoixDesactive): ReactElement {
  const intl = useIntl();
  const idRaison = useId();
  const idChoix = useId();
  return h(
    "div",
    { className: "choix-desactive", "data-choix": valeur },
    h(
      "label",
      { className: "portee", htmlFor: idChoix },
      h("input", { id: idChoix, type: "radio", name: nom, value: valeur, disabled: true, "aria-describedby": idRaison }),
      intl.formatMessage({ id: libelle }),
    ),
    h("p", { id: idRaison, className: "choix-raison" }, intl.formatMessage({ id: raison })),
  );
}
