// The options of the lead time / cycle time chart (design D19, D22, D32). A pure builder: no ECharts import, no DOM, no text, no colour
// and no style of its own. The labels come from the catalogue (given by the caller), the colours and the border, font and pattern
// styles from the design tokens (read from the computed style of the page, one CSS variable per entry). A masked or insufficient
// measure has no point in the series: the gap is told by a marked quarter (a band over the whole quarter, drawn by a custom series
// because a mark area from a category to itself has no width), never by a value estimated, interpolated or recalculated.
import type { Mesure, PointTrimestre } from "@mothra/contract";
import { ANNEE_GROUPEE } from "@mothra/contract/listes-fiche";

import { GLYPHES_ICONES } from "./glyphes.ts";

export interface Libelles {
  lead: string;
  cycle: string;
  axis: string;
  masked: string;
  insufficient: string;
  // A quarter as the API sends it, shown through the catalogue.
  quarter: (brut: string) => string;
}

export interface Palette {
  text: string;
  textMuted: string;
  border: string;
  surface: string;
  leadSeries: string;
  cycleSeries: string;
  maskedText: string;
  maskedBackground: string;
  maskedBorder: string;
  insufficientBorder: string;
  insufficientText: string;
}

// The chart palette: semantic tokens of the generated CSS (design D32), never a brand or raw token. The series have their own tokens:
// a series colour is neither a verdict nor the information colour. The two series differ by symbol as well as by colour.
export const JETONS_PALETTE: Record<keyof Palette, string> = {
  text: "--color-text",
  textMuted: "--color-text-muted",
  border: "--color-border",
  surface: "--color-surface",
  leadSeries: "--color-series-lead",
  cycleSeries: "--color-series-cycle",
  maskedText: "--color-state-masked",
  maskedBackground: "--color-state-masked-bg",
  maskedBorder: "--color-state-masked-border",
  insufficientBorder: "--color-state-insufficient-border",
  insufficientText: "--color-state-insufficient",
};

// The non-colour tokens of the chart: the border patterns and font styles of the two markers, the border width and the font.
export interface Style {
  maskedBorderStyle: string;
  insufficientBorderStyle: string;
  maskedFontStyle: string;
  insufficientFontStyle: string;
  insufficientBackground: string;
  borderWidth: number;
  seriesWidth: number;
  fontFamily: string;
  fontSize: number;
}

export const JETONS_STYLE: Record<keyof Style, string> = {
  maskedBorderStyle: "--cell-masked-border-style",
  insufficientBorderStyle: "--cell-insufficient-border-style",
  maskedFontStyle: "--cell-masked-font-style",
  insufficientFontStyle: "--cell-insufficient-font-style",
  insufficientBackground: "--cell-insufficient-background",
  borderWidth: "--border-width",
  seriesWidth: "--series-line-width",
  fontFamily: "--font-family",
  fontSize: "--font-size-small",
};

type StyleCalcule = Pick<CSSStyleDeclaration, "getPropertyValue">;

const calculerParDefaut = (e: Element): StyleCalcule => getComputedStyle(e);

export function lirePalette(element: Element, calculer: (element: Element) => StyleCalcule = calculerParDefaut): Palette {
  const style = calculer(element);
  const palette = {} as Record<keyof Palette, string>;
  for (const [entree, variable] of Object.entries(JETONS_PALETTE) as Array<[keyof Palette, string]>) {
    palette[entree] = style.getPropertyValue(variable).trim();
  }
  return palette;
}

// A CSS length of a token as a number of pixels: `px` as written, `rem` times the computed font size of the root.
export function enPixels(longueur: string, racine: number): number {
  const nombre = Number.parseFloat(longueur);
  return longueur.trim().endsWith("rem") ? nombre * racine : nombre;
}

export function lireStyle(element: Element, calculer: (element: Element) => StyleCalcule = calculerParDefaut): Style {
  const style = calculer(element);
  const lu = (variable: string): string => style.getPropertyValue(variable).trim();
  const racine = Number.parseFloat(style.getPropertyValue("font-size"));
  return {
    maskedBorderStyle: lu(JETONS_STYLE.maskedBorderStyle),
    insufficientBorderStyle: lu(JETONS_STYLE.insufficientBorderStyle),
    maskedFontStyle: lu(JETONS_STYLE.maskedFontStyle),
    insufficientFontStyle: lu(JETONS_STYLE.insufficientFontStyle),
    insufficientBackground: lu(JETONS_STYLE.insufficientBackground),
    borderWidth: enPixels(lu(JETONS_STYLE.borderWidth), racine),
    seriesWidth: enPixels(lu(JETONS_STYLE.seriesWidth), racine),
    fontFamily: lu(JETONS_STYLE.fontFamily),
    fontSize: enPixels(lu(JETONS_STYLE.fontSize), racine),
  };
}

export type EtatTrimestre = "value" | "masked" | "insufficient_sample";

// A quarter is marked masked as soon as one of its measures is, insufficient when one is and none is masked; otherwise it has values.
export function etatDuTrimestre(point: PointTrimestre): EtatTrimestre {
  const etats = [point.lead.state, point.cycle.state];
  if (etats.includes("masked")) return "masked";
  if (etats.includes("insufficient_sample")) return "insufficient_sample";
  return "value";
}

function valeurOuNull(mesure: Mesure): number | null {
  return mesure.state === "value" ? mesure.value : null;
}

// A marked quarter: its rank on the category axis and how it is drawn.
export interface Marque {
  rang: number;
  etat: Exclude<EtatTrimestre, "value">;
  fond: string;
  contour: string;
  motif: string;
  couleurTexte: string;
  styleTexte: string;
  texte: string;
}

export function marquesDe(points: readonly PointTrimestre[], libelles: Libelles, palette: Palette, aspect: Style): Marque[] {
  const marques: Marque[] = [];
  points.forEach((point, rang) => {
    const etat = etatDuTrimestre(point);
    if (etat === "masked") {
      marques.push({
        rang,
        etat,
        fond: palette.maskedBackground,
        contour: palette.maskedBorder,
        motif: aspect.maskedBorderStyle,
        couleurTexte: palette.maskedText,
        styleTexte: aspect.maskedFontStyle,
        texte: libelles.masked,
      });
    } else if (etat === "insufficient_sample") {
      marques.push({
        rang,
        etat,
        fond: aspect.insufficientBackground,
        contour: palette.insufficientBorder,
        motif: aspect.insufficientBorderStyle,
        couleurTexte: palette.insufficientText,
        styleTexte: aspect.insufficientFontStyle,
        texte: [GLYPHES_ICONES.ellipsis, libelles.insufficient].join(" "),
      });
    }
  });
  return marques;
}

// The parts of the custom series' callback arguments that the drawing reads.
interface ParamsDessin {
  coordSys: { x: number; y: number; width: number; height: number };
}
interface ApiDessin {
  value: (dimension: number) => number;
  coord: (valeur: [number, number]) => number[];
  size: (valeur: [number, number]) => number[];
}

// The places (on the category axis) of the first and of the last band, when the label of the bands is drawn once for all of them (A-06).
interface Etendue {
  debut: number;
  fin: number;
  // How many marks (the first ones, the pooled year being always the last point) are quarters and share the label; a later mark keeps its own.
  trimestres: number;
}

// The band of a marked quarter: the whole width of its category, the whole height of the grid, with its pattern and its label.
// The `style` key of the two elements below is the ECharts custom-series API (declared exception of test/statique.ts, this function
// only); every value under it comes from the palette and the style tokens.
// A-06: when `etendue` is given, the label is drawn once, by the first band, centred on all the bands and as wide as they are together;
// the other bands draw their outline only. Otherwise each band draws its own label.
function dessiner(marques: readonly Marque[], aspect: Style, etendue?: Etendue): (params: ParamsDessin, api: ApiDessin) => object {
  return (params, api) => {
    const rang = api.value(1);
    const marque = marques[rang];
    const [centre] = api.coord([api.value(0), 0]);
    const [largeur] = api.size([1, 0]);
    const zone = params.coordSys;
    // The pooled year (a mark after the shared ones) keeps its own label, drawn as without a shared extent.
    const partage = etendue !== undefined && rang < etendue.trimestres;
    const [debut] = !partage ? [centre] : api.coord([etendue.debut, 0]);
    const [fin] = !partage ? [centre] : api.coord([etendue.fin, 0]);
    const rect = {
      type: "rect",
      shape: { x: centre - largeur / 2, y: zone.y, width: largeur, height: zone.height },
      style: { fill: marque.fond, stroke: marque.contour, lineWidth: aspect.borderWidth, lineDash: marque.motif },
    };
    if (partage && rang !== 0) return { type: "group", children: [rect] };
    return {
      type: "group",
      children: [
        rect,
        {
          type: "text",
          style: {
            text: marque.texte,
            x: !partage ? centre : (debut + fin) / 2,
            y: zone.y + zone.height / 2,
            ...(!partage ? {} : { width: fin - debut + largeur, overflow: "break" }),
            textAlign: "center",
            textVerticalAlign: "middle",
            fill: marque.couleurTexte,
            fontStyle: marque.styleTexte,
            fontFamily: aspect.fontFamily,
            fontSize: aspect.fontSize,
          },
        },
      ],
    };
  };
}

// A-06: every quarter (the pooled year apart) is an insufficient sample, and there are at least two: one label for the whole span of the
// quarters, not one per band (the labels overlapped, were cut and ran over the axis ticks). Only the marks of the quarters are compared
// (the pooled year, marked or not, keeps its own label and never counts): a quarter with values, or masked, between two insufficient ones
// is never crossed by the label. A mix of states keeps one label per band.
function etendueUnique(points: readonly PointTrimestre[], marques: readonly Marque[], places: readonly number[]): Etendue | undefined {
  const trimestres = points.filter((p) => p.quarter !== ANNEE_GROUPEE).length;
  const marquesTrimestres = marques.filter((m) => points[m.rang].quarter !== ANNEE_GROUPEE);
  if (marquesTrimestres.length < 2 || marquesTrimestres.length !== trimestres || !marquesTrimestres.every((m) => m.etat === "insufficient_sample")) return undefined;
  return { debut: places[marquesTrimestres[0].rang], fin: places[marquesTrimestres[marquesTrimestres.length - 1].rang], trimestres: marquesTrimestres.length };
}

// The place of each point on the category axis. The pooled year is an isolated point (author's answer Q4, R-20261104-42): one empty
// category separates it from the last quarter, and no value is in it, so that no line segment joins the two.
function placesSurAxe(points: readonly PointTrimestre[]): { places: number[]; total: number } {
  const rang = points.findIndex((p) => p.quarter === ANNEE_GROUPEE);
  const espace = rang > 0;
  return { places: points.map((_, i) => (espace && i >= rang ? i + 1 : i)), total: points.length + (espace ? 1 : 0) };
}

export function construireOptions(points: readonly PointTrimestre[], libelles: Libelles, palette: Palette, aspect: Style): Record<string, unknown> {
  const marques = marquesDe(points, libelles, palette, aspect);
  const { places, total } = placesSurAxe(points);
  const sur = (valeurs: Array<number | null>): Array<number | null> => {
    const donnees: Array<number | null> = new Array<number | null>(total).fill(null);
    valeurs.forEach((valeur, i) => {
      donnees[places[i]] = valeur;
    });
    return donnees;
  };
  const categories: string[] = new Array<string>(total).fill("");
  points.forEach((p, i) => {
    categories[places[i]] = libelles.quarter(p.quarter);
  });
  const series: object[] = [
    {
      name: libelles.lead,
      type: "line",
      data: sur(points.map((p) => valeurOuNull(p.lead))),
      symbol: "circle",
      lineStyle: { color: palette.leadSeries, width: aspect.seriesWidth },
      itemStyle: { color: palette.leadSeries },
    },
    {
      name: libelles.cycle,
      type: "line",
      data: sur(points.map((p) => valeurOuNull(p.cycle))),
      symbol: "rect",
      lineStyle: { color: palette.cycleSeries, width: aspect.seriesWidth },
      itemStyle: { color: palette.cycleSeries },
    },
  ];
  if (marques.length > 0) {
    series.push({
      type: "custom",
      silent: true,
      legendHoverLink: false,
      z: 1,
      data: marques.map((m, i) => [places[m.rang], i]),
      encode: { x: 0 },
      renderItem: dessiner(marques, aspect, etendueUnique(points, marques, places)),
    });
  }
  return {
    animation: false,
    textStyle: { fontFamily: aspect.fontFamily, fontSize: aspect.fontSize },
    legend: { data: [libelles.lead, libelles.cycle], selectedMode: false, textStyle: { color: palette.text } },
    xAxis: {
      type: "category",
      data: categories,
      axisLine: { lineStyle: { color: palette.border } },
      axisLabel: { color: palette.textMuted },
    },
    yAxis: {
      type: "value",
      min: 0,
      name: libelles.axis,
      nameTextStyle: { color: palette.textMuted },
      axisLabel: { color: palette.textMuted },
      splitLine: { lineStyle: { color: palette.border } },
    },
    series,
  };
}
