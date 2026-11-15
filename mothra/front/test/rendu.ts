// Server rendering of a component under the react-intl provider, for tests without a browser.
import { createElement as h } from "react";
import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { IntlProvider } from "react-intl";

import { catalogues } from "../src/i18n/langue.ts";
import type { Langue } from "../src/i18n/langue.ts";

export function rendre(element: ReactElement, langue: Langue): string {
  return renderToStaticMarkup(h(IntlProvider, { locale: langue, messages: catalogues[langue] }, element));
}

// The radio inputs of a markup fragment: the value of each, whether it is disabled, and the id its `aria-describedby` points to.
export interface ChoixRadio {
  valeur: string;
  desactive: boolean;
  decrit: string | undefined;
}

export function choixRadio(html: string): ChoixRadio[] {
  return [...html.matchAll(/<input\b[^>]*\btype="radio"[^>]*>/g)].map(([balise]) => ({
    valeur: /\bvalue="([^"]*)"/.exec(balise)?.[1] ?? "",
    desactive: /\bdisabled=""/.test(balise),
    decrit: /\baria-describedby="([^"]*)"/.exec(balise)?.[1],
  }));
}

// The text of a markup fragment, tags removed.
export function texte(html: string): string {
  return html.replace(/<[^>]*>/g, "");
}
