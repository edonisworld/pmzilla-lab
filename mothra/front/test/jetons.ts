// Checks of the design tokens (design D32, tasks 24.1, 24.3, 24.4): freshness of the generated CSS, contrast per declared pair,
// undeclared pairs in style rules, state and verdict colours. Pure functions over a token source; messages are those of D32.
import { ErreurValeurJeton, genererCss, HEXADECIMAL, valeurJeton } from "../scripts/generer-jetons.ts";
import type { Jetons, Nature } from "../scripts/generer-jetons.ts";
import { ligneDe, sansCommentairesCss } from "./statique.ts";

export type Catalogues = { en: Record<string, string>; fr: Record<string, string> };

// ---- 24.1 freshness ----------------------------------------------------------------------------------------------------------

export function controlerFraicheur(source: Jetons, cssActuel: string, fichier: string): string[] {
  return genererCss(source) === cssActuel ? [] : [`jetons CSS périmés : ${fichier} (régénérer)`];
}

// ---- 24.3 contrast -----------------------------------------------------------------------------------------------------------

const SEUILS: Record<Nature, number> = { text: 4.5, "large-text": 3, interface: 3 };

function luminance(hex: string): number {
  const canaux = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = canaux.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

// WCAG 2.1 contrast ratio of two #RRGGBB colours.
export function ratio(a: string, b: string): number {
  const [clair, sombre] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (clair + 0.05) / (sombre + 0.05);
}

// Truncation (never rounding up); the epsilon absorbs the floating-point error of a ratio that is exactly on a hundredth.
function tronque(x: number): string {
  return (Math.floor(x * 100 + 1e-9) / 100).toFixed(2);
}

// ---- colour vision: lightness gap between the verdict and error colours (author's decision of 2026-10-27) --------------------------

// Minimum CIELAB L* gap between two verdict colours, and between "confirmed" and the ink: they stay distinct under protanopia and deuteranopia, which blur hue.
export const ECART_L_MINIMUM = 15;

// CIELAB lightness L* (D65 white, from sRGB) of a #RRGGBB colour.
export function lightnessCielab(hex: string): number {
  const y = luminance(hex);
  return y > 216 / 24389 ? 116 * Math.cbrt(y) - 16 : (24389 / 27) * y;
}

// The colours compared: the verdict tokens of the states section (the error colour is left out: its contrast is tested on its own).
function jetonsDeLuminosite(source: Jetons): string[] {
  return Object.keys(source.states).filter((j) => j.startsWith("verdict-"));
}

// "Confirmed" keeps at least `ecartMinimum` L* from the ink of the text (token `text`), so that it never becomes almost black.
export function controlerEncre(source: Jetons, ecartMinimum: number = ECART_L_MINIMUM): string[] {
  const encre = valeurSure(source, "text");
  const confirmee = valeurSure(source, "verdict-confirmed");
  if (encre === undefined || confirmee === undefined) return [];
  const ecart = Math.abs(lightnessCielab(encre) - lightnessCielab(confirmee));
  return ecart < ecartMinimum ? [`verdict trop proche de l'encre : verdict-confirmed (ΔL* ${tronque(ecart)} < ${ecartMinimum})`] : [];
}

// ---- the table of state patterns: no two states share the same look (outline and icon) --------------------------------------

export function controlerStyles(source: Jetons): string[] {
  const trouves: string[] = [];
  const decrits: Array<[string, string]> = [];
  for (const [j, etat] of Object.entries(source.states)) {
    const contour = typeof etat.outline === "string" ? etat.outline.trim().toLowerCase() : "";
    if (contour === "") trouves.push(`contour manquant : ${j}`);
    else decrits.push([j, `${contour}|${etat.icon}`]);
  }
  for (let a = 0; a < decrits.length; a++) {
    for (let b = a + 1; b < decrits.length; b++) {
      if (decrits[a][1] === decrits[b][1]) trouves.push(`styles confondus : ${decrits[a][0]} et ${decrits[b][0]}`);
    }
  }
  return trouves;
}

export function luminosites(source: Jetons): Record<string, number> {
  const resultat: Record<string, number> = {};
  for (const j of jetonsDeLuminosite(source)) {
    const v = valeurSure(source, j);
    if (v !== undefined) resultat[j] = lightnessCielab(v);
  }
  return resultat;
}

export function controlerLuminosites(source: Jetons, ecartMinimum: number = ECART_L_MINIMUM): string[] {
  const l = luminosites(source);
  const jetons = Object.keys(l);
  const trouves: string[] = [];
  for (let a = 0; a < jetons.length; a++) {
    for (let b = a + 1; b < jetons.length; b++) {
      const ecart = Math.abs(l[jetons[a]] - l[jetons[b]]);
      if (ecart < ecartMinimum) trouves.push(`luminosités trop proches : ${jetons[a]} et ${jetons[b]} (ΔL* ${tronque(ecart)} < ${ecartMinimum})`);
    }
  }
  return trouves;
}

function jetonInvalide(source: Jetons, nom: string): boolean {
  try {
    valeurJeton(source, nom);
    return false;
  } catch (e) {
    if (e instanceof ErreurValeurJeton) return true;
    throw e;
  }
}

// The value of a token, or undefined when unknown or invalid (the invalid literal is reported by `controlerContrastes`).
function valeurSure(source: Jetons, nom: string): string | undefined {
  try {
    return valeurJeton(source, nom);
  } catch (e) {
    if (e instanceof ErreurValeurJeton) return undefined;
    throw e;
  }
}

export interface Mesure {
  foreground: string;
  background: string;
  kind: Nature;
  ratio: number | undefined;
}

export function mesures(source: Jetons): Mesure[] {
  return source.pairs.map((p) => {
    const fg = valeurSure(source, p.foreground);
    const bg = valeurSure(source, p.background);
    return { foreground: p.foreground, background: p.background, kind: p.kind, ratio: fg && bg ? ratio(fg, bg) : undefined };
  });
}

export function controlerContrastes(source: Jetons): string[] {
  const trouves: string[] = [];
  for (const section of [source.raw, source.derived, source.light]) {
    for (const [nom, v] of Object.entries(section)) {
      if (v.startsWith("#") && !HEXADECIMAL.test(v)) trouves.push(`valeur de jeton invalide : ${nom}`);
    }
  }
  for (const p of source.pairs) {
    const valeurs = [p.foreground, p.background].map((j) => valeurSure(source, j));
    const inconnus = [p.foreground, p.background].filter((j, i) => valeurs[i] === undefined && !jetonInvalide(source, j));
    for (const j of inconnus) trouves.push(`jeton inconnu dans une paire : ${j}`);
    if (valeurs.some((v) => v === undefined)) continue;
    const r = ratio(valeurs[0] as string, valeurs[1] as string);
    const seuil = SEUILS[p.kind];
    if (r < seuil) trouves.push(`contraste insuffisant : ${p.foreground} sur ${p.background} (${tronque(r)} < ${seuil})`);
  }
  return trouves;
}

// A style rule of a .css file that sets a foreground token (`color`, `border-color` or `outline-color`) and a background token must
// use a declared pair. The check reads one rule at a time. `--cell-masked-*` style variables are followed to the colour token
// they reference (a scale value written `{token}`).
export function controlerPairesCss(source: Jetons, fichiers: ReadonlyArray<{ nom: string; contenu: string }>): string[] {
  const alias: Record<string, string> = {};
  for (const [nom, valeur] of Object.entries(source.scale)) {
    const m = /^\{([^{}]+)\}$/.exec(valeur);
    if (m && Object.hasOwn(source.light, m[1])) alias[nom] = m[1];
  }
  const jetonDe = (valeur: string): string | undefined => {
    const m = /var\(--([\w-]+)\)/.exec(valeur);
    if (!m) return undefined;
    if (m[1].startsWith("color-")) return m[1].slice("color-".length);
    return Object.hasOwn(alias, m[1]) ? alias[m[1]] : undefined;
  };
  const trouves: string[] = [];
  for (const f of fichiers) {
    if (!f.nom.endsWith(".css") || f.nom === "src/styles/tokens.css") continue;
    const texte = sansCommentairesCss(f.contenu);
    for (const regle of texte.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      const premiers: string[] = [];
      let fond: string | undefined;
      for (const declaration of regle[2].split(";")) {
        const i = declaration.indexOf(":");
        if (i < 0) continue;
        const propriete = declaration.slice(0, i).trim();
        const valeur = declaration.slice(i + 1);
        const jeton = jetonDe(valeur);
        if (propriete === "color" || propriete === "border-color" || propriete === "outline-color") {
          if (jeton !== undefined) premiers.push(jeton);
        } else if (propriete === "background" || propriete === "background-color") fond = jeton;
      }
      if (fond === undefined) continue;
      const debut = (regle.index ?? 0) + (regle[1].length - regle[1].trimStart().length);
      for (const premier of premiers) {
        if (source.pairs.some((p) => p.foreground === premier && p.background === fond)) continue;
        trouves.push(`paire non déclarée : ${premier} sur ${fond} (${f.nom}:${ligneDe(texte, debut)})`);
      }
    }
  }
  return trouves;
}

// The brand tokens are reserved to the logos and illustrations: no rule of a .css file (the generated file apart) uses them.
export function controlerMarquesCss(fichiers: ReadonlyArray<{ nom: string; contenu: string }>): string[] {
  const trouves: string[] = [];
  for (const f of fichiers) {
    if (!f.nom.endsWith(".css") || f.nom === "src/styles/tokens.css") continue;
    const texte = sansCommentairesCss(f.contenu);
    for (const m of texte.matchAll(/var\(\s*--color-brand-[\w-]*/g)) {
      trouves.push(`jeton de marque dans une règle : ${f.nom}:${ligneDe(texte, m.index ?? 0)}`);
    }
  }
  return trouves;
}

// ---- 24.4 state and verdict colours ------------------------------------------------------------------------------------------

const FAMILLE_AMBRE = ["amber", "gold", "amber-strong", "dot"];
// Tints, backgrounds and borders belong to a state token and are not states of their own.
const SUFFIXES_DECORATIFS = ["-tint", "-bg", "-border"];
const MOTS_DE_JUGEMENT = /unfavourable|favourable|défavorable|favorable/i;
const ELEMENTS: ReadonlyArray<[keyof Jetons["states"][string], string]> = [
  ["label", "libellé"],
  ["icon", "icône"],
  ["outline", "motif"],
];

export function controlerEtats(source: Jetons, catalogues: Catalogues): string[] {
  const trouves: string[] = [];
  const valeur = (j: string) => valeurSure(source, j);
  // Every colour token of a state or verdict (tints, masked background and border included), read from the colour section.
  const jetons = Object.keys(source.light).filter((j) => j.startsWith("verdict-") || j.startsWith("state-"));
  const propres = jetons.filter((j) => !SUFFIXES_DECORATIFS.some((s) => j.endsWith(s)));
  const ambre = new Set(FAMILLE_AMBRE.map(valeur));
  for (const j of jetons) {
    const v = valeur(j);
    if (v !== undefined && ambre.has(v)) trouves.push(`couleur d'état prise à l'ambre ou à l'or : ${j}`);
  }
  for (const j of propres) {
    if (!Object.hasOwn(source.states, j)) trouves.push(`couleur seule : ${j} (manque : ${ELEMENTS.map(([, nom]) => nom).join(", ")})`);
  }
  for (const j of Object.keys(source.states)) {
    if (!Object.hasOwn(source.light, j)) trouves.push(`état sans jeton de couleur : ${j}`);
  }
  const confondables = jetons.filter((j) => j.startsWith("verdict-") || j === "state-error" || j === "state-masked-bg");
  for (let a = 0; a < confondables.length; a++) {
    for (let b = a + 1; b < confondables.length; b++) {
      const va = valeur(confondables[a]);
      if (va !== undefined && va === valeur(confondables[b])) trouves.push(`couleurs confondues : ${confondables[a]} et ${confondables[b]}`);
    }
  }
  for (const [j, etat] of Object.entries(source.states)) {
    for (const [champ, nom] of ELEMENTS) {
      const present = typeof etat[champ] === "string" && etat[champ].trim() !== "";
      const catalogué = champ !== "label" || (present && Object.hasOwn(catalogues.en, etat.label) && Object.hasOwn(catalogues.fr, etat.label));
      if (!present || !catalogué) trouves.push(`couleur seule : ${j} (manque : ${nom})`);
    }
  }
  for (const [j, etat] of Object.entries(source.states)) {
    if (!j.startsWith("verdict-")) continue;
    if (MOTS_DE_JUGEMENT.test(j)) trouves.push(`verdict jugé : ${j}`);
    for (const catalogue of [catalogues.en, catalogues.fr]) {
      if (Object.hasOwn(catalogue, etat.label) && MOTS_DE_JUGEMENT.test(catalogue[etat.label])) {
        trouves.push(`verdict jugé : ${etat.label}`);
        break;
      }
    }
  }
  return trouves;
}
