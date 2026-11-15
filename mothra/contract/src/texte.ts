// The check of a written text (design D20, invariant 11 amended on 2026-10-27, ADR 0007): the effect and the cause of a sheet.
// A pure function, called by the creation route and by any route that writes these fields, never in a component or in the formatting
// of an answer. The names part is the rule of `tools/sensitive_names.py` (`parse_names`, `patterns`, `line_matches`) reimplemented here,
// checked against the Python functions by the shared cases of test-data/cas-texte.json; the key and e-mail patterns are Mothra's own.

// Maximum length of a written field: Unicode code points, counted after trimming the spaces at the start and the end. One place.
export const TEXTE_LONGUEUR_MAX = 500;

export type RaisonTexte = "ticket_key" | "email" | "sensitive_name" | "too_long";

// Accepted, or refused with the reason; `count` and `max` are present with `too_long` only, the only numbers a refusal holds.
export type ResultatTexte = { ok: true } | { ok: false; reason: RaisonTexte; count?: number; max?: number };

const MOT = "A-Za-z0-9_";

// A word of the form: an uppercase letter, then uppercase letters, digits or underscores, a hyphen, digits (the shape of a Jira key).
const CLE = new RegExp(`(?<![${MOT}])[A-Z][A-Z0-9_]*-[0-9]+`);
// A local part, `@`, a domain holding a dot.
const COURRIEL = /[^\s@]+@[^\s@]+\.[^\s@]+/;

function sensibleALaCasse(nom: string): boolean {
  return [...nom].length <= 3 || (nom === nom.toUpperCase() && nom !== nom.toLowerCase());
}

function echapper(nom: string): string {
  return nom.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function compiler(noms: string[], drapeaux: string): RegExp | null {
  if (noms.length === 0) return null;
  const motifs = [...noms].sort((a, b) => [...b].length - [...a].length);
  return new RegExp(`(?<![${MOT}])(?:${motifs.map(echapper).join("|")})(?![${MOT}])`, drapeaux);
}

// The line breaks of Python's `str.splitlines` and the white space of `str.strip` (which, unlike JavaScript's `trim`, keeps a byte-order mark),
// so that the two readers cut a list the same way (cases of test-data/cas-noms.json). The two separators U+2028 and U+2029 are built from their
// code (a literal one would end the line of a regular-expression literal), and so is the byte-order mark U+FEFF.
const SEPARATEURS_SUPPLEMENTAIRES = String.fromCharCode(0x2028) + String.fromCharCode(0x2029);
const FIN_DE_LIGNE = new RegExp(`\\r\\n|[\\n\\r\\v\\f\\x1c-\\x1e\\x85${SEPARATEURS_SUPPLEMENTAIRES}]`);
const MARQUES_D_ORDRE = new RegExp(`^${String.fromCharCode(0xfeff)}+`);
const BLANCS = "\\t\\n\\v\\f\\r\\x1c-\\x20\\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000";
const ROGNER = new RegExp(`^[${BLANCS}]+|[${BLANCS}]+$`, "g");

// The text as the checks read it (audit #629, L3-06): format characters (`\p{Cf}`, zero-width ones included) removed, NFKC (a no-break space, a
// full-width at sign, a decomposed accent), every run of white space reduced to one space, the dashes of Unicode turned into a hyphen (a key written
// with a non-breaking hyphen). Applied to the text and to the names of the lists, so that both sides are read the same way. The same function exists
// in tools/sensitive_names.py (`normalize_text`), checked by the cases of test-data/cas-texte.json.
// Replaces: nothing. Removal: permanent while a written text is checked against a list of names.
const CARACTERES_DE_FORMAT = /\p{Cf}/gu;
const BLANCS_A_REDUIRE = new RegExp(`[${BLANCS}]+`, "g");
const TIRETS_UNICODE = /[‐-―−]/g;
export function normaliserTexte(texte: string): string {
  return texte.replace(CARACTERES_DE_FORMAT, "").normalize("NFKC").replace(BLANCS_A_REDUIRE, " ").replace(TIRETS_UNICODE, "-");
}

// The lines of a text as `splitlines` cuts them, leading byte-order marks dropped (shared with the reader of the team-names extract).
export function lignesDeLaListe(texte: string): string[] {
  return texte.replace(MARQUES_D_ORDRE, "").split(FIN_DE_LIGNE);
}

// One name per line, empty lines and lines starting with "#" ignored, leading byte-order marks dropped (`parse_names`).
export function lireNoms(texte: string): string[] {
  return lignesDeLaListe(texte)
    .map((ligne) => ligne.replace(ROGNER, ""))
    .filter((ligne) => ligne !== "" && !ligne.startsWith("#"));
}

// The compiled patterns of a list of names (`patterns`): whole word, a name stuck to a letter, digit or underscore does not match, case
// ignored except for names of three characters or fewer and all-capital acronyms, compared with their case.
export function motifsDeNoms(noms: readonly string[]): RegExp[] {
  const propres = new Set(noms.map((n) => normaliserTexte(n).trim()).filter((n) => n !== ""));
  const exacts = [...propres].filter(sensibleALaCasse);
  const autres = [...propres].filter((n) => !sensibleALaCasse(n));
  return [compiler(exacts, "u"), compiler(autres, "iu")].filter((m): m is RegExp => m !== null);
}

export function ligneCorrespond(motifs: readonly RegExp[], ligne: string): boolean {
  // Match on the raw text OR on the normalised text: the normalisation (format characters removed) can stick a name to the neighbouring
  // letter and make it lose its word boundary; the raw text keeps the boundary that main already refused.
  // Replaces: the comparison on the normalised text alone. Removal: permanent, normalisation alone loses the word boundaries.
  const lue = normaliserTexte(ligne);
  return motifs.some((m) => m.test(ligne) || m.test(lue));
}

// The check, in the order of the design: key, e-mail address, name of the lists, length. The result never holds the text nor the value
// that matched. `motifs` come from `motifsDeNoms` over the two lists the server loaded at start-up.
export function verifierTexteEcrit(texte: string, motifs: readonly RegExp[]): ResultatTexte {
  const propre = texte.trim();
  const lue = normaliserTexte(propre);
  // Key and e-mail: the raw text OR the normalised text (same reason as `ligneCorrespond`).
  // Replaces: the comparison on the normalised text alone. Removal: permanent, normalisation alone loses the word boundaries.
  if (CLE.test(propre) || CLE.test(lue)) return { ok: false, reason: "ticket_key" };
  if (COURRIEL.test(propre) || COURRIEL.test(lue)) return { ok: false, reason: "email" };
  if (ligneCorrespond(motifs, propre)) return { ok: false, reason: "sensitive_name" };
  const compte = [...propre].length;
  if (compte > TEXTE_LONGUEUR_MAX) return { ok: false, reason: "too_long", count: compte, max: TEXTE_LONGUEUR_MAX };
  return { ok: true };
}
