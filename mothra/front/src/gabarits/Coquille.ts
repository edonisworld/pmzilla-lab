// The shell template (mothra-demo-habillage D1, D17): the side navigation on the left, then the one information banner of the screen (when the
// caller gives the dataset code of the answer the screen reads), then the main column. Every screen is drawn inside it.
import { createElement as h } from "react";
import type { ReactElement, ReactNode } from "react";

import { Banniere } from "../composants/Banniere.ts";
import type { JeuDeDonnees } from "../composants/Banniere.ts";

export interface PropsCoquille {
  navigation: ReactElement;
  // The dataset code of the answer the screen reads; absent while it is not known: no banner then.
  jeu?: JeuDeDonnees;
  children?: ReactNode;
}

export function Coquille({ navigation, jeu, children }: PropsCoquille): ReactElement {
  return h(
    "div",
    { className: "coquille" },
    navigation,
    h("div", { className: "coquille-colonne" }, jeu === undefined ? null : h("header", null, h(Banniere, { jeu })), h("main", { className: "coquille-principal" }, children)),
  );
}
