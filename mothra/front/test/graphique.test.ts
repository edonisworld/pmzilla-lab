// Task 19.1: the chart component (ECharts, inventoried, imported by module). A masked cell and the "insufficient sample" marker
// show in the chart, told apart by pattern, icon and label; a masked point carries no value at all (never estimated or recalculated);
// every colour comes from the design tokens (D32), none is written in the code. The data are synthetic.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement as h } from "react";

import { creerGraphique } from "../src/composants/echarts.ts";
import { GLYPHES_ICONES } from "../src/composants/glyphes.ts";
import { Graphique } from "../src/composants/Graphique.ts";
import {
  construireOptions,
  enPixels,
  etatDuTrimestre,
  JETONS_PALETTE,
  JETONS_STYLE,
  lirePalette,
  lireStyle,
  marquesDe,
} from "../src/composants/optionsGraphique.ts";
import type { Mesure, PointTrimestre } from "@mothra/contract";
import type { Libelles, Palette, Style } from "../src/composants/optionsGraphique.ts";
import { libelleTrimestre } from "../src/composants/trimestre.ts";
import { catalogues } from "../src/i18n/langue.ts";
import type { Jetons } from "../scripts/generer-jetons.ts";
import { rendre } from "./rendu.ts";
import { analyser, FICHIER_RENDERITEM, sources, valeursEnDur, valeursEnDurDesSources } from "./statique.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const REEL = JSON.parse(readFileSync(`${FRONT}src/styles/tokens.json`, "utf8")) as Jetons;
const CSS_JETONS = readFileSync(`${FRONT}src/styles/tokens.css`, "utf8");

// A palette of sentinels: whatever colour the options hold must be one of these, so none is written in the builder.
const PALETTE: Palette = {
  text: "PAL-text",
  textMuted: "PAL-textMuted",
  border: "PAL-border",
  surface: "PAL-surface",
  leadSeries: "PAL-lead",
  cycleSeries: "PAL-cycle",
  maskedText: "PAL-maskedText",
  maskedBackground: "PAL-maskedBg",
  maskedBorder: "PAL-maskedBorder",
  insufficientBorder: "PAL-insufficientBorder",
  insufficientText: "PAL-insufficientText",
};

// Sentinels again: every pattern, font and width of the options must be one of these, so none is written in the builder.
const STYLE: Style = {
  maskedBorderStyle: "STY-maskedBorder",
  insufficientBorderStyle: "STY-insufficientBorder",
  maskedFontStyle: "STY-maskedFont",
  insufficientFontStyle: "STY-insufficientFont",
  insufficientBackground: "STY-insufficientBackground",
  borderWidth: 7,
  seriesWidth: 5,
  fontFamily: "STY-family",
  fontSize: 13,
};

const LIBELLES: Libelles = {
  lead: "LEAD-LABEL",
  cycle: "CYCLE-LABEL",
  axis: "AXIS-LABEL",
  masked: "MASKED-LABEL",
  insufficient: "INSUFFICIENT-LABEL",
  quarter: (brut) => `Q<${brut}>`,
};

const valeur = (v: number): Mesure => ({ state: "value", value: v });
const masquee: Mesure = { state: "masked", threshold: 5 };
const insuffisante: Mesure = { state: "insufficient_sample" };

const POINTS: PointTrimestre[] = [
  { quarter: "2025-Q4", lead: valeur(40), cycle: valeur(10) },
  { quarter: "2026-Q1", lead: masquee, cycle: masquee },
  { quarter: "2026-Q2", lead: insuffisante, cycle: insuffisante },
  { quarter: "2026-Q3", lead: valeur(36), cycle: valeur(12) },
];

type Objet = Record<string, unknown>;

// The marked quarters of the options: the data of the custom series, as [rank on the axis, index of the mark].
function serieMarques(options: Objet): Objet | undefined {
  return (options.series as Objet[]).find((s) => s.type === "custom");
}

function rangsMarques(options: Objet): number[] {
  return ((serieMarques(options)?.data ?? []) as number[][]).map(([rang]) => rang);
}

function marque(trimestre: string) {
  const rang = POINTS.findIndex((p) => p.quarter === trimestre);
  const trouvee = marquesDe(POINTS, LIBELLES, PALETTE, STYLE).find((m) => m.rang === rang);
  assert.ok(trouvee, `aucune marque pour ${trimestre}`);
  return trouvee;
}

// What the custom series draws for one mark, with a fake chart API of one band of width 100 centred on the rank (rank * 100 + 50).
function dessin(options: Objet, indice: number): { rect: Objet; texte: Objet } {
  const serie = serieMarques(options) as { data: number[][]; renderItem: (p: unknown, a: unknown) => { children: Objet[] } };
  const [rang, rangMarque] = serie.data[indice];
  const api = {
    value: (dimension: number) => [rang, rangMarque][dimension],
    coord: ([x]: [number, number]) => [x * 100 + 50, 0],
    size: () => [100, 0],
  };
  const { children } = serie.renderItem({ coordSys: { x: 40, y: 10, width: 400, height: 200 } }, api);
  return { rect: children[0], texte: children[1] };
}

function chaines(noeud: unknown, cle = "", sortie: Array<[string, string]> = []): Array<[string, string]> {
  if (typeof noeud === "string") sortie.push([cle, noeud]);
  else if (Array.isArray(noeud)) for (const e of noeud) chaines(e, cle, sortie);
  else if (typeof noeud === "object" && noeud !== null) for (const [k, v] of Object.entries(noeud)) chaines(v, k, sortie);
  return sortie;
}

// ---- states of a quarter -----------------------------------------------------------------------------------------------------

test("a quarter is masked as soon as one of its measures is masked, insufficient when one is, and a value otherwise", () => {
  assert.equal(etatDuTrimestre(POINTS[0]), "value");
  assert.equal(etatDuTrimestre(POINTS[1]), "masked");
  assert.equal(etatDuTrimestre(POINTS[2]), "insufficient_sample");
  assert.equal(etatDuTrimestre({ quarter: "x", lead: valeur(1), cycle: insuffisante }), "insufficient_sample");
  assert.equal(etatDuTrimestre({ quarter: "x", lead: insuffisante, cycle: masquee }), "masked");
});

// ---- no estimated value ------------------------------------------------------------------------------------------------------

test("a masked or insufficient measure has no point at all in the series: no value, no estimate, no interpolation", () => {
  const options = construireOptions(POINTS, LIBELLES, PALETTE, STYLE) as Objet;
  const [lead, cycle] = options.series as Array<{ data: Array<number | null>; connectNulls?: boolean }>;
  assert.deepEqual(lead.data, [40, null, null, 36]);
  assert.deepEqual(cycle.data, [10, null, null, 12]);
  assert.notEqual(lead.connectNulls, true);
  assert.notEqual(cycle.connectNulls, true);
});

test("a value next to a masked measure of the same quarter is kept as received, never recomputed", () => {
  const options = construireOptions([{ quarter: "q", lead: valeur(33), cycle: masquee }], LIBELLES, PALETTE, STYLE) as Objet;
  const [lead, cycle] = options.series as Array<{ data: Array<number | null> }>;
  assert.deepEqual(lead.data, [33]);
  assert.deepEqual(cycle.data, [null]);
});

// ---- masked and insufficient told apart ---------------------------------------------------------------------------------------

test("the masked quarter is a band with the masked pattern, fill and label (no icon), all read from the tokens", () => {
  const m = marque("2026-Q1");
  assert.equal(m.etat, "masked");
  assert.equal(m.motif, STYLE.maskedBorderStyle);
  assert.equal(m.contour, PALETTE.maskedBorder);
  assert.equal(m.fond, PALETTE.maskedBackground);
  assert.equal(m.texte, LIBELLES.masked);
  assert.equal(m.couleurTexte, PALETTE.maskedText);
  assert.equal(m.styleTexte, STYLE.maskedFontStyle);
});

test("the insufficient-sample quarter is an outline with no fill, an icon, its own label and the insufficient-state colour", () => {
  const m = marque("2026-Q2");
  assert.equal(m.etat, "insufficient_sample");
  assert.equal(m.motif, STYLE.insufficientBorderStyle);
  assert.equal(m.contour, PALETTE.insufficientBorder);
  assert.equal(m.fond, STYLE.insufficientBackground);
  const glyphe = GLYPHES_ICONES[REEL.states["state-insufficient"].icon];
  assert.ok(glyphe !== undefined && glyphe !== "", "icône propre attendue");
  assert.equal(m.texte, `${glyphe} ${LIBELLES.insufficient}`);
  assert.equal(m.couleurTexte, PALETTE.insufficientText);
  assert.equal(m.styleTexte, STYLE.insufficientFontStyle);
});

test("the two markers differ by pattern, icon and label, and a quarter with values has no marker", () => {
  const options = construireOptions(POINTS, LIBELLES, PALETTE, STYLE) as Objet;
  const m = marque("2026-Q1");
  const i = marque("2026-Q2");
  assert.notEqual(m.motif, i.motif);
  assert.notEqual(m.texte, i.texte);
  assert.equal(GLYPHES_ICONES[REEL.states["state-masked"].icon] ?? "", "");
  assert.deepEqual(rangsMarques(options), [1, 2]);
  const sans = construireOptions([POINTS[0], POINTS[3]], LIBELLES, PALETTE, STYLE) as Objet;
  assert.equal(serieMarques(sans), undefined);
});

test("every mark is drawn as a band of the whole width of its quarter, never a zero-width area", () => {
  const options = construireOptions(POINTS, LIBELLES, PALETTE, STYLE) as Objet;
  const rangs = rangsMarques(options);
  assert.equal(rangs.length, 2);
  rangs.forEach((rang, indice) => {
    const { rect, texte } = dessin(options, indice);
    const forme = rect.shape as { x: number; y: number; width: number; height: number };
    assert.ok(forme.width > 0 && forme.height > 0);
    assert.equal(forme.x, rang * 100);
    assert.equal(forme.x + forme.width / 2, rang * 100 + 50, "centrée sur le trimestre");
    const style = rect.style as Objet;
    assert.equal(style.lineWidth, STYLE.borderWidth);
    assert.equal(style.lineDash, marque(POINTS[rang].quarter).motif);
    const etiquette = texte.style as Objet;
    assert.equal(etiquette.fontFamily, STYLE.fontFamily);
    assert.equal(etiquette.fontSize, STYLE.fontSize);
  });
});

test("the marker patterns follow the pattern tokens of the states, not a choice of the chart", () => {
  assert.equal(REEL.scale["cell-masked-border-style"], "dashed");
  assert.equal(REEL.scale["cell-insufficient-border-style"], "dotted");
  assert.equal(REEL.scale["cell-masked-font-style"], "italic");
});

test("the style tokens are read from the computed style of the page, in pixels for the lengths", () => {
  const lues: string[] = [];
  const valeurs: Record<string, string> = {
    "--border-width": "1px",
    "--series-line-width": "2px",
    "--font-size-small": "0.875rem",
    "--font-family": " system-ui, sans-serif ",
    "font-size": "20px",
  };
  const style = lireStyle({} as Element, () => ({
    getPropertyValue: (nom: string) => {
      lues.push(nom);
      return valeurs[nom] ?? ` VAL${nom} `;
    },
  }));
  assert.deepEqual(lues.filter((n) => n !== "font-size").sort(), Object.values(JETONS_STYLE).sort());
  assert.equal(style.borderWidth, 1);
  assert.equal(style.seriesWidth, 2);
  assert.equal(style.fontSize, 17.5);
  assert.equal(style.fontFamily, "system-ui, sans-serif");
  assert.equal(style.maskedBorderStyle, "VAL--cell-masked-border-style");
  assert.equal(enPixels("2px", 16), 2);
  for (const variable of Object.values(JETONS_STYLE)) assert.ok(CSS_JETONS.includes(`${variable}:`), `variable absente de tokens.css : ${variable}`);
});

test("the options hold no pattern, width or font of their own: every one comes from the style given", () => {
  const options = construireOptions(POINTS, LIBELLES, PALETTE, STYLE) as Objet;
  assert.deepEqual(options.textStyle, { fontFamily: STYLE.fontFamily, fontSize: STYLE.fontSize });
  const { rect } = dessin(options, 0);
  assert.equal((rect.style as Objet).fill, PALETTE.maskedBackground);
  const json = JSON.stringify(options);
  for (const interdit of ["dashed", "dotted", "italic", "transparent", "system-ui"]) assert.ok(!json.includes(interdit), interdit);
});

test("the series have their own tokens, with declared contrast pairs, and use neither the information colour nor the text colour", () => {
  assert.equal(JETONS_PALETTE.leadSeries, "--color-series-lead");
  assert.equal(JETONS_PALETTE.cycleSeries, "--color-series-cycle");
  assert.equal(JETONS_PALETTE.insufficientText, "--color-state-insufficient");
  for (const jeton of ["series-lead", "series-cycle"]) {
    assert.ok(jeton in REEL.light, jeton);
    const paires = REEL.pairs.filter((p) => p.foreground === jeton);
    assert.ok(paires.some((p) => p.kind === "interface" && p.background === "surface"), jeton);
  }
  const reservees = [JETONS_PALETTE.leadSeries, JETONS_PALETTE.cycleSeries];
  assert.ok(!reservees.includes("--color-info") && !reservees.includes("--color-text"));
});

test("a quarter is shown through the catalogue, in each language, and an unknown identifier as received", () => {
  const formater = (langue: "en" | "fr") => (id: string, v: { year: string; quarter: string }) =>
    catalogues[langue][id].replace("{quarter}", v.quarter).replace("{year}", v.year);
  assert.equal(libelleTrimestre("2026-Q1", formater("en")), "Q1 2026");
  assert.equal(libelleTrimestre("2026-Q1", formater("fr")), "T1 2026");
  assert.equal(libelleTrimestre("x", formater("en")), "x");
  assert.deepEqual(((construireOptions(POINTS, LIBELLES, PALETTE, STYLE) as Objet).xAxis as { data: string[] }).data, POINTS.map((p) => `Q<${p.quarter}>`));
});

test("the legend cannot be clicked: no series is hidden, as a hidden series would read as a missing figure", () => {
  const options = construireOptions(POINTS, LIBELLES, PALETTE, STYLE) as Objet;
  assert.equal((options.legend as Objet).selectedMode, false);
});

// ---- colours from the tokens --------------------------------------------------------------------------------------------------

test("every colour of the options is a colour of the palette, and the palette is read from the tokens", () => {
  const couleurs = chaines(construireOptions(POINTS, LIBELLES, PALETTE, STYLE)).filter(([cle]) => /color/i.test(cle));
  assert.ok(couleurs.length > 6);
  const admises = new Set<string>(Object.values(PALETTE));
  assert.deepEqual(couleurs.filter(([, c]) => !admises.has(c)), []);
});

test("every palette entry names a colour variable of the generated token CSS, and none names a brand or raw token", () => {
  assert.deepEqual(Object.keys(JETONS_PALETTE).sort(), Object.keys(PALETTE).sort());
  for (const [entree, variable] of Object.entries(JETONS_PALETTE)) {
    assert.match(variable, /^--color-[a-z-]+$/, entree);
    assert.ok(CSS_JETONS.includes(`${variable}:`), `variable absente de tokens.css : ${variable}`);
    assert.doesNotMatch(variable, /brand|amber|gold/, entree);
  }
});

test("the palette is read from the computed style of the page, one variable per entry", () => {
  const lues: string[] = [];
  const palette = lirePalette({} as Element, () => ({
    getPropertyValue: (nom: string) => {
      lues.push(nom);
      return ` VAL${nom} `;
    },
  }));
  assert.deepEqual([...lues].sort(), Object.values(JETONS_PALETTE).sort());
  assert.equal(palette.text, `VAL${JETONS_PALETTE.text}`);
  assert.equal(palette.insufficientBorder, `VAL${JETONS_PALETTE.insufficientBorder}`);
});

test("the two series are told apart by symbol as well as by colour, and the animation is off", () => {
  const options = construireOptions(POINTS, LIBELLES, PALETTE, STYLE) as Objet;
  const [lead, cycle] = options.series as Array<{ symbol: string; name: string; lineStyle: { color: string } }>;
  assert.notEqual(lead.symbol, cycle.symbol);
  assert.notEqual(lead.lineStyle.color, cycle.lineStyle.color);
  assert.equal((lead.lineStyle as { width?: number }).width, STYLE.seriesWidth);
  assert.equal((cycle.lineStyle as { width?: number }).width, STYLE.seriesWidth);
  assert.deepEqual([lead.name, cycle.name], [LIBELLES.lead, LIBELLES.cycle]);
  assert.equal(options.animation, false);
});

test("no source of the new files holds a hard-coded colour, size or style prop", () => {
  const fichiers = sources(FRONT, "src", [".ts", ".tsx", ".css"]);
  assert.deepEqual(valeursEnDurDesSources(fichiers), []);
});

test("the style key is refused everywhere except in the renderItem function of the option builder (declared exception)", () => {
  const dessinee = "\nfunction dessiner(a) {\n  return { type: \"rect\", style: { fill: a } };\n}\n";
  const ailleurs = "export const x = { style: { fill: 1 } };\n";
  // accepted only in the declared file, inside the function
  assert.deepEqual(valeursEnDur(FICHIER_RENDERITEM, dessinee), []);
  // the same text in another source file is refused
  assert.equal(valeursEnDur("src/composants/Autre.ts", dessinee).length, 1);
  assert.equal(valeursEnDur("src/pages/PageTableau.ts", ailleurs).length, 1);
  // the same key elsewhere in the declared file is refused
  assert.equal(valeursEnDur(FICHIER_RENDERITEM, dessinee + ailleurs).length, 1);
  // an indented function of that name is not the declared one: refused
  assert.equal(valeursEnDur(FICHIER_RENDERITEM, "\n  function dessiner(a) {\n  return { style: 1 };\n}\n").length, 1);
  // a string literal continued over a real line break (backslash then newline) that puts the name at the start of a line, before the
  // real function, moves nothing: only the real function is covered
  const litteral = "\nconst s = \"x\\\nfunction dessiner(\";\nexport const x = { style: 1 };" + dessinee;
  assert.ok(litteral.includes("\\\nfunction dessiner("), "le saut de ligne est bien dans la source simulée");
  assert.equal(valeursEnDur(FICHIER_RENDERITEM, litteral).length, 1);
  // a second function, or a top-level declaration inside the zone, fails the checker instead of widening the exception
  assert.throws(() => valeursEnDur(FICHIER_RENDERITEM, dessinee + dessinee), /une seule admise/);
  assert.throws(() => valeursEnDur(FICHIER_RENDERITEM, "\nfunction dessiner(a) {\n  x;\nconst y = { style: 1 };\n}\n"), /colonne 0/);
  assert.throws(() => valeursEnDur(FICHIER_RENDERITEM, "\nfunction dessiner(a) {\n  x;\nlet y = 1;\n}\n"), /colonne 0/);
  assert.throws(() => valeursEnDur(FICHIER_RENDERITEM, "\nfunction dessiner(a) {\n  x;\n"), /introuvable/);
  // the closing line may carry blanks or a comment; whatever follows it is outside the zone and checked as usual
  assert.deepEqual(valeursEnDur(FICHIER_RENDERITEM, "\nfunction dessiner(a) {\n  style: 1;\n}   \n"), []);
  assert.deepEqual(valeursEnDur(FICHIER_RENDERITEM, "\nfunction dessiner(a) {\n  style: 1;\n} // fin\n"), []);
  assert.equal(valeursEnDur(FICHIER_RENDERITEM, "\nfunction dessiner(a) {\n  x;\n} // fin\nlet o = {\n  style: 1\n}\n").length, 1);
  // a closing line that is not a lone brace (`};`) is a column-0 line of the zone: the checker fails
  assert.throws(() => valeursEnDur(FICHIER_RENDERITEM, "\nfunction dessiner(a) {\n  x;\n};\nlet o = {\n  style: 1\n}\n"), /colonne 0/);
  // closed by default: a backtick or a regular-expression literal in the code of the declared file fails the checker
  const gabarit = "\nconst t = `\nfunction dessiner(a) {\n}\n`;" + dessinee;
  assert.throws(() => valeursEnDur(FICHIER_RENDERITEM, gabarit), /accent grave/);
  const imbrique = "\nconst t = `${`\nfunction dessiner(a) {\n}\n`}`;" + dessinee;
  assert.throws(() => valeursEnDur(FICHIER_RENDERITEM, imbrique), /accent grave/);
  assert.throws(() => valeursEnDur(FICHIER_RENDERITEM, "\nconst r = /`/;" + dessinee), /accent grave/);
  assert.throws(() => valeursEnDur(FICHIER_RENDERITEM, "\nconst r = /a+/g;" + dessinee), /expression régulière/);
  // a backtick in a comment is not code: it does not close the exception
  assert.deepEqual(valeursEnDur(FICHIER_RENDERITEM, "\n// the `style` key" + dessinee), []);
  // an exported function of that name is not the declared one: refused
  assert.equal(valeursEnDur(FICHIER_RENDERITEM, "\nexport function dessiner(a) {\n  return { style: 1 };\n}\n").length, 1);
  // a regular-expression literal holding a comment opener does not hide the code after it from the other files' check
  assert.equal(valeursEnDur("src/pages/Autre.ts", "\nconst r = /[/*]/;\nconst o = { style: 1 };\n").length, 1);
  assert.equal(valeursEnDur("src/pages/Autre.ts", "\nconst q = a / b / c; const o = { style: 1 };\n").length, 1);
  assert.equal(valeursEnDur("src/pages/Autre.ts", "\nconst q = a++ / b; const o = { style: 1 };\n").length, 1);
  // contexts where a slash opens a regular expression, so that the comment opener it holds opens nothing: the key after it is refused,
  // in another file (found) and in the declared file (the checker fails on the regular-expression literal)
  const cas = [
    "const f = (s: string) => /[/*]/.test(s);\nexport const o = { style: 1 };\n",
    "const f = x + /[/*]/.test(s);\nexport const o = { style: 1 };\n",
    "else /[/*]/.test(s);\nexport const o = { style: 1 };\n",
    "const f = await /[/*]/.test(s);\nexport const o = { style: 1 };\n",
    "const f = a instanceof /[/*]/;\nexport const o = { style: 1 };\n",
  ];
  for (const source of cas) {
    assert.equal(valeursEnDur("src/pages/Autre.ts", `\n${source}`).length, 1, source);
    assert.throws(() => valeursEnDur(FICHIER_RENDERITEM, `\n${source}`), /expression régulière/, source);
  }
  // an ambiguous slash (after a closing parenthesis, bracket or a word) that reads as a suspect literal fails the checker, in any file
  const ambigus = [
    "if (a) /[//]/.test(s), (o = { style: 1 });",
    "if (a) /\"/.test(s) && f(\"//x\"); f({ style: 1 });",
    "while (a) /'/.test(s); f({ style: 1 });",
  ];
  for (const source of ambigus) {
    assert.throws(() => valeursEnDur("src/pages/Autre.ts", `\n${source}\n`), /barre oblique ambiguë/, source);
    assert.throws(() => valeursEnDur(FICHIER_RENDERITEM, `\n${source}\n`), /barre oblique ambiguë/, source);
  }
  // and the real option builder passes
  const reel = sources(FRONT, "src", [".ts"]).find((s) => s.nom === FICHIER_RENDERITEM);
  assert.ok(reel && /\bstyle:/.test(reel.contenu));
  assert.deepEqual(valeursEnDur(reel.nom, reel.contenu), []);
});

// ---- ECharts: imported by module -----------------------------------------------------------------------------------------------

test("ECharts is imported only through its core, charts, components and renderers entries, never the whole package", () => {
  const importsEcharts = sources(FRONT, "src", [".ts", ".tsx"]).flatMap((s) =>
    [...s.contenu.matchAll(/\bfrom\s*["'](echarts[^"']*)["']/g)].map((m) => `${s.nom} ${m[1]}`),
  );
  assert.ok(importsEcharts.length > 0);
  const hors = importsEcharts.filter((i) => !/ echarts\/(?:core|charts|components|renderers)$/.test(i));
  assert.deepEqual(hors, []);
});

test("the charts registered are the ones used: a line chart, a custom series, a grid, a legend, the SVG renderer", () => {
  const source = readFileSync(`${FRONT}src/composants/echarts.ts`, "utf8");
  const nommes = [...source.matchAll(/import\s*\{([^}]*)\}\s*from\s*["']echarts\/(?:charts|components|renderers)["']/g)].flatMap((m) =>
    m[1].split(",").map((n) => n.trim()).filter((n) => n !== ""),
  );
  assert.deepEqual(nommes.sort(), ["CustomChart", "GridComponent", "LegendComponent", "LineChart", "SVGRenderer"]);
});

// ---- the chart as rendered by ECharts (server-side SVG, no browser) -------------------------------------------------------------

function svg(langue: "en" | "fr"): string {
  const c = catalogues[langue];
  const libelles: Libelles = {
    lead: c["tableau.series.lead"],
    cycle: c["tableau.series.cycle"],
    axis: c["tableau.axis.days"],
    masked: c["cellState.masked"],
    insufficient: c["state.insufficient_sample"],
    quarter: (brut) => libelleTrimestre(brut, (id, v) => c[id].replace("{quarter}", v.quarter).replace("{year}", v.year)),
  };
  const graphique = creerGraphique(null, 640, 320);
  graphique.setOption(construireOptions(POINTS, libelles, REELLE_PALETTE, REEL_STYLE));
  const sortie = graphique.renderToSVGString();
  graphique.dispose();
  return sortie;
}

// The style as the real tokens give it (the values of tokens.json, lengths in pixels).
const REEL_STYLE: Style = {
  maskedBorderStyle: REEL.scale["cell-masked-border-style"],
  insufficientBorderStyle: REEL.scale["cell-insufficient-border-style"],
  maskedFontStyle: REEL.scale["cell-masked-font-style"],
  insufficientFontStyle: REEL.scale["cell-insufficient-font-style"],
  insufficientBackground: REEL.scale["cell-insufficient-background"],
  borderWidth: 1,
  seriesWidth: 2,
  fontFamily: REEL.scale["font-family"],
  fontSize: 14,
};

const REELLE_PALETTE: Palette = Object.fromEntries(Object.keys(JETONS_PALETTE).map((cle, rang) => [cle, `#${String(rang).padStart(2, "0")}${String(rang).padStart(2, "0")}${String(rang).padStart(2, "0")}`])) as unknown as Palette;

test("the rendered chart shows the masked label and the insufficient-sample label, each with its own pattern", () => {
  const anglais = svg("en");
  assert.match(anglais, />masked</);
  assert.match(anglais, />\.\.\. insufficient sample</);
  assert.match(svg("fr"), />masqué</);
  assert.match(svg("fr"), />\.\.\. échantillon insuffisant</);
  const motifs = new Set([...anglais.matchAll(/stroke-dasharray="([^"]+)"/g)].map((m) => m[1]));
  const nonVides = [...motifs].filter((m) => m !== "");
  assert.ok(nonVides.length >= 2, "deux motifs de bordure attendus (tirets et pointillés)");
});

test("the rendered chart draws one band of positive width for every marked quarter", () => {
  const sortie = svg("en");
  const bandes = [...sortie.matchAll(/<path[^>]*stroke-dasharray="[^"]+"[^>]*>/g)].map((m) => m[0]);
  assert.equal(bandes.length, 2, "une bande par trimestre marqué");
  for (const bande of bandes) {
    const d = /\sd="([^"]+)"/.exec(bande)?.[1] ?? "";
    // the rectangle is a relative path: M x y, then l dx 0 along its top edge
    const largeur = Number(/^M[\d.]+ [\d.]+l(-?[\d.]+) 0/.exec(d)?.[1]);
    assert.ok(Math.abs(largeur) > 0, `largeur nulle : ${bande}`);
  }
});

test("the rendered chart holds no number for the masked and insufficient quarters", () => {
  const texteSvg = [...svg("en").matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map((m) => m[1]);
  assert.ok(texteSvg.includes("masked"));
  // only axis ticks are numbers here (multiples of 5): no label carries a value, least of all a masked one
  assert.deepEqual(texteSvg.filter((t) => /^\d+$/.test(t) && Number(t) % 5 !== 0), []);
});

// ---- the component ----------------------------------------------------------------------------------------------------------

test("the chart component renders a labelled image container, in each language, and draws nothing without a browser", () => {
  const anglais = rendre(h(Graphique, { points: POINTS }), "en");
  assert.match(anglais, /<div class="graphique" role="img" aria-label="Median lead time and cycle time per quarter"><\/div>/);
  assert.match(rendre(h(Graphique, { points: POINTS }), "fr"), /aria-label="Lead time et cycle time médians par trimestre"/);
});

test("the chart points to its equivalent table and to the threshold sentence with aria-describedby", () => {
  const html = rendre(h(Graphique, { points: POINTS, idTableau: "tab", idSeuil: "seuil" }), "en");
  assert.match(html, /role="img" aria-label="[^"]+" aria-describedby="tab seuil"/);
});

test("the chart loads ECharts on demand: the component has no static import of the ECharts module", () => {
  const source = readFileSync(`${FRONT}src/composants/Graphique.ts`, "utf8");
  assert.doesNotMatch(source, /^import[^\n]*echarts/m);
  assert.match(source, /import\("\.\/echarts\.ts"\)/);
});

test("the component and the option builder hold no literal text: labels come from the catalogue", () => {
  for (const fichier of ["Graphique.ts", "optionsGraphique.ts", "echarts.ts"]) {
    const { litteraux } = analyser(readFileSync(`${FRONT}src/composants/${fichier}`, "utf8"));
    const texte = litteraux.filter((l) => /\s/.test(l.texte.trim()) && /[A-Za-z]/.test(l.texte));
    assert.deepEqual(texte, [], fichier);
  }
});
