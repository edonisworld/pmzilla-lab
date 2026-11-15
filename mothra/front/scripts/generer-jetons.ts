// Design tokens as data (design D32, group 24): reads the token source and writes the CSS variables of the light theme.
// Run by the npm script `generate-tokens` of the front package. No package, no network. The freshness test of the front
// regenerates in memory with `genererCss` and compares with the tracked file.
import { readFileSync, writeFileSync } from "node:fs";

export type Nature = "text" | "large-text" | "interface";

export interface Paire {
  foreground: string;
  background: string;
  kind: Nature;
  usage: string;
}

export interface Etat {
  label: string; // catalogue key
  icon: string;
  outline?: string; // border pattern (solid, dashed, dotted, double, hatched, none): with the icon, the look of the state
}

export interface Jetons {
  raw: Record<string, string>;
  derived: Record<string, string>;
  light: Record<string, string>; // semantic colour tokens: a hexadecimal value or the name of another token
  scale: Record<string, string>; // spacing, size, font, radius; a value written `{token}` becomes a reference to that light token
  pairs: Paire[];
  states: Record<string, Etat>;
}

export const EN_TETE =
  "/* Generated from tokens.json by `npm run generate-tokens`: do not edit. Design tokens (design D32): the only CSS file that holds a colour, size or spacing literal. */";

export const HEXADECIMAL = /^#[0-9A-F]{6}$/;

export class ErreurValeurJeton extends Error {
  jeton: string;
  constructor(jeton: string) {
    super(`valeur de jeton invalide : ${jeton}`);
    this.jeton = jeton;
  }
}

function brut(source: Jetons, nom: string): string | undefined {
  for (const section of [source.light, source.derived, source.raw]) if (Object.hasOwn(section, nom)) return section[nom];
  return undefined;
}

// The value of a token (raw, derived or semantic), followed through the names it references; undefined when unknown.
// A colour literal that is not #RRGGBB in capitals throws an ErreurValeurJeton naming the token that holds it.
export function valeurJeton(source: Jetons, nom: string, profondeur = 0): string | undefined {
  if (profondeur > 10) return undefined;
  const v = brut(source, nom);
  if (v === undefined) return undefined;
  if (v.startsWith("#")) {
    if (!HEXADECIMAL.test(v)) throw new ErreurValeurJeton(nom);
    return v;
  }
  return valeurJeton(source, v, profondeur + 1);
}

export function genererCss(source: Jetons): string {
  for (const section of [source.raw, source.derived, source.light]) {
    for (const [nom, v] of Object.entries(section)) if (v.startsWith("#") && !HEXADECIMAL.test(v)) throw new ErreurValeurJeton(nom);
  }
  const lignes = [EN_TETE, ":root {"];
  for (const nom of Object.keys(source.light)) {
    const valeur = valeurJeton(source, nom);
    if (valeur === undefined) throw new Error(`jeton sans valeur : ${nom}`);
    lignes.push(`  --color-${nom}: ${valeur};`);
  }
  lignes.push("");
  for (const [nom, valeur] of Object.entries(source.scale)) {
    const reference = /^\{([^{}]+)\}$/.exec(valeur);
    if (reference && !Object.hasOwn(source.light, reference[1])) throw new Error(`jeton inconnu dans l'échelle : ${reference[1]} (${nom})`);
    lignes.push(`  --${nom}: ${reference ? `var(--color-${reference[1]})` : valeur};`);
  }
  lignes.push("}", "");
  return lignes.join("\n");
}

if (import.meta.main) {
  const dossier = new URL("../src/styles/", import.meta.url);
  const source = JSON.parse(readFileSync(new URL("tokens.json", dossier), "utf8")) as Jetons;
  writeFileSync(new URL("tokens.css", dossier), genererCss(source));
}
