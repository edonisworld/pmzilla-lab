// The languages of the front and the default language: the only place of the front that names a language code (design D6, decision
// sheet F4: English by default, #330 decided on 2026-10-18). The catalogues are the only source of the front's texts.
import en from "./en.json" with { type: "json" };
import fr from "./fr.json" with { type: "json" };

export const LANGUES = ["en", "fr"] as const;
export type Langue = (typeof LANGUES)[number];

export const LANGUE_PAR_DEFAUT: Langue = "en";

export const catalogues: Record<Langue, Record<string, string>> = { en, fr };

// The catalogue key of each language's own name, shown in the language selector.
export const CLES_LANGUE: Record<Langue, string> = { en: "language.en", fr: "language.fr" };

export function estLangue(valeur: string): valeur is Langue {
  return (LANGUES as readonly string[]).includes(valeur);
}
