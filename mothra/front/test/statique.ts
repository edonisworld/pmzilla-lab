// Static checks of the front sources (tasks 7.1, 7.2, 7.3). Pure functions over file contents: no network, no build.
// Every finding is reported as "<file>:<line>", so a failure names the file and the line.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

export interface Litteral {
  texte: string;
  ligne: number;
}

export interface Analyse {
  code: string; // the source with comments blanked (newlines kept), strings and regular-expression literals kept
  litteraux: Litteral[];
  expressions: number; // how many regular-expression literals the code holds
}

// A `/` opens a regular-expression literal, not a division, after one of these characters (an operator, `=>` included, or an opening
// or separating mark), after one of these words, or at the start. After `)`, `]`, an identifier or a number it is ambiguous (a division,
// or the regular expression of `if (a) /x/.test(s)`); after `++` or `--` it is a division.
const AVANT_EXPRESSION = new Set(["(", ",", "=", ":", "[", "!", "&", "|", "?", "{", "}", ";", "+", "-", "*", "%", "<", ">", "~", "^"]);
const MOTS_AVANT_EXPRESSION = /(?:^|[^\w$])(?:return|typeof|else|case|throw|await|void|in|of|delete|instanceof|new|yield|do)$/;

type Contexte = "expression" | "division" | "ambigu";

function contexteDeBarre(code: string): Contexte {
  const reste = code.trimEnd();
  if (reste === "") return "expression";
  const dernier = reste[reste.length - 1];
  if ((dernier === "+" || dernier === "-") && reste.endsWith(dernier + dernier)) return "division";
  if (AVANT_EXPRESSION.has(dernier) || MOTS_AVANT_EXPRESSION.test(reste)) return "expression";
  return "ambigu";
}

// The regular-expression literal that starts at `debut`: its end (exclusive, flags included), or -1 when none ends on the line, and
// whether it is suspect (a quote, a backtick, or a `/` inside a class: what would open a false string or comment if misread).
function lireExpression(source: string, debut: number): { fin: number; suspect: boolean } {
  let j = debut + 1;
  let classe = false;
  let suspect = false;
  while (j < source.length) {
    const c = source[j];
    if (c === "\n") return { fin: -1, suspect };
    if (c === "\\") j += 2;
    else {
      if (c === '"' || c === "'" || c === "`" || (c === "/" && classe)) suspect = true;
      if (c === "[") classe = true;
      else if (c === "]") classe = false;
      else if (c === "/" && !classe) {
        j++;
        while (j < source.length && /[a-z]/.test(source[j])) j++;
        return { fin: j, suspect };
      }
      j++;
    }
  }
  return { fin: -1, suspect };
}

// The end of the regular-expression literal at `debut` when the context says one opens there, -1 for a division. An ambiguous slash that
// reads as a suspect literal on its line fails the checker (closed by default): the reading of the rest of the line could not be trusted.
function finExpression(source: string, debut: number, code: string): number {
  const contexte = contexteDeBarre(code);
  if (contexte === "division") return -1;
  const { fin, suspect } = lireExpression(source, debut);
  if (contexte === "expression") return fin;
  if (fin > 0 && suspect) throw new Error(`vérificateur : barre oblique ambiguë (ligne ${ligneDe(source, debut)}), division ou expression régulière douteuse`);
  return -1;
}

// One pass over a TypeScript source: comments are blanked, string literals are listed with their line, regular-expression literals are
// read whole (a `/*` or a quote inside one opens nothing). Limit, accepted: no `${...}` holding a quote or a backtick.
export function analyser(source: string): Analyse {
  let code = "";
  const litteraux: Litteral[] = [];
  let expressions = 0;
  let ligne = 1;
  let i = 0;
  while (i < source.length) {
    const c = source[i];
    const suivant = source[i + 1];
    const fin = c === "/" && suivant !== "*" && suivant !== "/" ? finExpression(source, i, code) : -1;
    if (fin > 0) {
      code += source.slice(i, fin);
      expressions++;
      i = fin;
    } else if (c === "/" && suivant === "*") {
      const fin = source.indexOf("*/", i + 2);
      const bloc = fin < 0 ? source.slice(i) : source.slice(i, fin + 2);
      code += bloc.replace(/[^\n]/g, " ");
      ligne += (bloc.match(/\n/g) ?? []).length;
      i += bloc.length;
    } else if (c === "/" && suivant === "/") {
      while (i < source.length && source[i] !== "\n") {
        code += " ";
        i++;
      }
    } else if (c === '"' || c === "'" || c === "`") {
      let j = i + 1;
      while (j < source.length && source[j] !== c && (c === "`" || source[j] !== "\n")) j += source[j] === "\\" ? 2 : 1;
      const morceau = source.slice(i, j + 1);
      litteraux.push({ texte: source.slice(i + 1, j), ligne });
      code += morceau;
      ligne += (morceau.match(/\n/g) ?? []).length;
      i = j + 1;
    } else {
      if (c === "\n") ligne++;
      code += c;
      i++;
    }
  }
  return { code, litteraux, expressions };
}

export function ligneDe(texte: string, index: number): number {
  return (texte.slice(0, index).match(/\n/g) ?? []).length + 1;
}

export function sansCommentairesCss(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, (bloc) => bloc.replace(/[^\n]/g, " "));
}

function trouver(nom: string, texte: string, motif: RegExp): string[] {
  return [...texte.matchAll(motif)].map((m) => `${nom}:${ligneDe(texte, m.index ?? 0)}`);
}

// ---- Task 7.1: design tokens -------------------------------------------------------------------------------------------------

const COULEUR = /#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color-mix|color)\(/g;
const TAILLE = /(?<![\w.])-?\d*\.?\d+(?:px|rem|em|pt|pc|cm|mm|in|vh|vw|vmin|vmax|ch|ex)\b/g;
// The 148 named colours of CSS Color 4. `transparent` and `currentcolor` are not literals of a colour and are admitted.
export const COULEURS_NOMMEES: ReadonlySet<string> = new Set(
  (
    "aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet brown burlywood cadetblue " +
    "chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan darkgoldenrod darkgray darkgreen darkgrey " +
    "darkkhaki darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen darkslateblue darkslategray " +
    "darkslategrey darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite forestgreen " +
    "fuchsia gainsboro ghostwhite gold goldenrod gray green greenyellow grey honeydew hotpink indianred indigo ivory khaki " +
    "lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen " +
    "lightgrey lightpink lightsalmon lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime " +
    "limegreen linen magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen mediumslateblue " +
    "mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin navajowhite navy oldlace olive " +
    "olivedrab orange orangered orchid palegoldenrod palegreen paleturquoise palevioletred papayawhip peachpuff peru pink plum " +
    "powderblue purple rebeccapurple red rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue " +
    "slateblue slategray slategrey snow springgreen steelblue tan teal thistle tomato turquoise violet wheat white whitesmoke " +
    "yellow yellowgreen"
  ).split(" "),
);
// The style prop is forbidden in scripts: styling goes through class names defined in the stylesheet.
const PROP_STYLE = /(?<![\w-])style=\{|(?<![\w-])["']?style["']?\s*:/g;
const PROPRIETE_DE_COULEUR = /([a-z-]*(?:color|background|border|outline|fill|stroke|shadow)[a-z-]*)\s*:\s*([^;{}]+)/g;

// The code of a source with its comments blanked, and how many regular-expression literals it holds (none for a stylesheet).
function sansCommentaires(nom: string, contenu: string): { texte: string; expressions: number } {
  if (nom.endsWith(".css")) return { texte: sansCommentairesCss(contenu), expressions: 0 };
  const { code, expressions } = analyser(contenu);
  return { texte: code, expressions };
}

// A colour literal (hexadecimal, functional notation, or a named colour in a colour property), a size or a spacing literal.
export function valeursEnDur(nom: string, contenu: string): string[] {
  const { texte, expressions } = sansCommentaires(nom, contenu);
  const trouvees = [...trouver(nom, texte, COULEUR), ...trouver(nom, texte, TAILLE)];
  if (nom.endsWith(".css")) {
    for (const m of texte.matchAll(PROPRIETE_DE_COULEUR)) {
      const valeur = m[2].replace(/var\([^)]*\)/g, " ");
      const mots = valeur.toLowerCase().match(/[a-z]+/g) ?? [];
      if (mots.some((mot) => COULEURS_NOMMEES.has(mot))) trouvees.push(`${nom}:${ligneDe(texte, m.index ?? 0)}`);
    }
  } else {
    trouvees.push(...trouver(nom, sansExceptionRenderItem(nom, texte, expressions), PROP_STYLE));
  }
  return [...new Set(trouvees)];
}

// DECLARED EXCEPTION to the ban on the `style` key: the custom-series API of ECharts names the drawing attributes of the elements that
// renderItem returns `style`. It covers one file and one function, the body of a top-level `function dessiner(` (at the start of a
// line, once, outside any string or template literal) in this file, up to its closing line: a `}` in column 0 followed only by blanks
// (a comment is already blanked). The same key anywhere else in this file, or in any other file, stays refused. The checker fails
// with a message, never widens the exception, on a second function of that name, a missing closing line, or any line of the zone
// (the closing line apart) that starts in column 0.
export const FICHIER_RENDERITEM = "src/composants/optionsGraphique.ts";

// The text with the inside of every string and template literal blanked (quotes and newlines kept): same length, same lines.
function sansContenuDeLitteraux(code: string): string {
  let sortie = "";
  let i = 0;
  while (i < code.length) {
    const c = code[i];
    if (c === '"' || c === "'" || c === "`") {
      let j = i + 1;
      while (j < code.length && code[j] !== c && (c === "`" || code[j] !== "\n")) j += code[j] === "\\" ? 2 : 1;
      const fin = Math.min(j, code.length - 1);
      sortie += c + code.slice(i + 1, fin).replace(/[^\n]/g, " ") + (j < code.length ? code[j] : "");
      i = j + 1;
    } else {
      sortie += c;
      i++;
    }
  }
  return sortie.slice(0, code.length);
}

// Closed by default: the declared file may hold, in its code part (comments apart), neither a backtick (a template literal can nest
// another one and hide a function header) nor a regular-expression literal; either one fails the checker instead of being guessed at.
export function sansExceptionRenderItem(nom: string, texte: string, expressions: number): string {
  if (nom !== FICHIER_RENDERITEM) return texte;
  if (texte.includes("`")) throw new Error(`vérificateur : accent grave (gabarit) dans le code de ${nom}, l'exception de dessiner est fermée par défaut`);
  if (expressions > 0) throw new Error(`vérificateur : expression régulière dans le code de ${nom}, l'exception de dessiner est fermée par défaut`);
  const squelette = sansContenuDeLitteraux(texte);
  const ancres = [...squelette.matchAll(/\nfunction dessiner\(/g)];
  if (ancres.length === 0) return texte;
  if (ancres.length > 1) throw new Error(`vérificateur : ${ancres.length} « function dessiner( » en début de ligne dans ${nom}, une seule admise`);
  const debut = (ancres[0].index ?? 0) + 1;
  const fermeture = /\n\}[ \t]*(?=\n|$)/.exec(squelette.slice(debut));
  if (fermeture === null) throw new Error(`vérificateur : ligne de fermeture « } » introuvable après « function dessiner( » dans ${nom}`);
  const fin = debut + fermeture.index;
  const zone = squelette.slice(debut, fin);
  if (/\n[^\s]/.test(zone)) throw new Error(`vérificateur : ligne en colonne 0 dans la zone de dessiner de ${nom}`);
  // blanked, not removed: the line numbers of what follows stay exact
  return texte.slice(0, debut) + texte.slice(debut, fin).replace(/[^\n]/g, " ") + texte.slice(fin);
}

// Task 24.1: the token source and its generated CSS are the only files exempt from the checker, by exact path.
export const SOURCES_DE_JETONS: readonly string[] = ["src/styles/tokens.json", "src/styles/tokens.css"];

export function valeursEnDurDesSources(fichiers: ReadonlyArray<{ nom: string; contenu: string }>): string[] {
  return fichiers.filter((f) => !SOURCES_DE_JETONS.includes(f.nom)).flatMap((f) => valeursEnDur(f.nom, f.contenu));
}

// ---- Task 7.2: no visible text outside the catalogues ------------------------------------------------------------------------

// A string literal reads as visible text when it holds a non-ASCII character (an accent, an ellipsis), words separated by
// whitespace, or is a single capitalised word. Codes, class names, paths and catalogue keys do not.
// A list of lowercase hyphenated words is a class list, accepted only when every word is a class defined in the stylesheet.
export function ressembleATexte(litteral: string, classes: ReadonlySet<string> = new Set()): boolean {
  const s = litteral.trim();
  if (s === "") return false;
  if (/[^\x00-\x7f]/.test(s)) return true;
  if (/^[a-z][a-z0-9-]*(?: [a-z][a-z0-9-]*)*$/.test(s) && s.split(" ").every((mot) => classes.has(mot))) return false;
  if (/\s/.test(s) && /[A-Za-z]/.test(s)) return true;
  return /^[A-Z][a-z]+[^A-Za-z0-9_]*$/.test(s);
}

const ATTRIBUT_VISIBLE = /["']?(?:aria-label|aria-description|aria-placeholder|title|alt|placeholder)["']?\s*:\s*["'`](?=[^"'`])/g;

export function classesDeCss(css: string): Set<string> {
  return new Set([...sansCommentairesCss(css).matchAll(/\.([a-z][a-z0-9-]*)/g)].map((m) => m[1]));
}

// JSX, for a .tsx file: an attribute written attr="…" (not attr={…}) whose name shows to the reader.
const ATTRIBUT_JSX = /(?<![\w-])(?:aria-label|aria-description|aria-placeholder|title|alt|placeholder)\s*=\s*["'](?=[^"'])/g;
// JSX text: what lies between `>` and `<` or `{`, or between `}` and `<`, outside expressions, blanks ignored. A `>` that closes
// an arrow (`=>`) or a generic is followed by code, not by letters then `<`; the arrow case is excluded by the `=` before it.
const TEXTE_JSX = /(?<![=-])>([^<>{}]+)(?=[<{])|\}([^<>{}]+)(?=<)/g;

function texteJsx(nom: string, code: string): string[] {
  const trouves: string[] = [];
  for (const m of code.matchAll(TEXTE_JSX)) {
    const texte = m[1] ?? m[2];
    if (!/[A-Za-zÀ-￿]/.test(texte)) continue;
    const debut = (m.index ?? 0) + m[0].length - texte.length + (texte.length - texte.trimStart().length);
    trouves.push(`${nom}:${ligneDe(code, debut)}`);
  }
  return trouves;
}

export function textesVisibles(nom: string, source: string, classes: ReadonlySet<string> = new Set()): string[] {
  const { code, litteraux } = analyser(source);
  const trouves = litteraux.filter((l) => ressembleATexte(l.texte, classes)).map((l) => `${nom}:${l.ligne}`);
  const jsx = nom.endsWith(".tsx") ? [...texteJsx(nom, code), ...trouver(nom, code, ATTRIBUT_JSX)] : [];
  return [...new Set([...trouves, ...trouver(nom, code, ATTRIBUT_VISIBLE), ...jsx])];
}

// The text of an index.html (a page without script text): anything outside tags, the title included, is a visible literal.
export function texteDuHtml(html: string): string {
  return html.replace(/<!--[\s\S]*?-->/g, "").replace(/<[^>]*>/g, "").trim();
}

// ---- Task 7.3: no component derives a number from cells ----------------------------------------------------------------------

const DERIVATION =
  /\.reduce\s*\(|[-+*/]=|\+\+|--(?!\w)|Math\.(?:sum|max|min|round|floor|ceil|abs)\b|\.(?:value|threshold)\s*[-+*/%]|[-+*/%]\s*[\w$]+\.(?:value|threshold)\b/g;

export function derivations(nom: string, source: string): string[] {
  return [...new Set(trouver(nom, analyser(source).code, DERIVATION))];
}

// ---- Files -------------------------------------------------------------------------------------------------------------------

export function fichiers(dossier: string, extensions: readonly string[]): string[] {
  const sortie: string[] = [];
  for (const entree of readdirSync(dossier).sort()) {
    const chemin = join(dossier, entree);
    if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin, extensions));
    else if (extensions.some((e) => entree.endsWith(e))) sortie.push(chemin);
  }
  return sortie;
}

export interface Source {
  nom: string; // relative to the front folder, "/" separators
  contenu: string;
}

export function sources(racineFront: string, dossier: string, extensions: readonly string[]): Source[] {
  return fichiers(join(racineFront, dossier), extensions).map((chemin) => ({
    nom: relative(racineFront, chemin).split("\\").join("/"),
    contenu: readFileSync(chemin, "utf8"),
  }));
}
