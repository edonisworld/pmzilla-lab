// Checks of the production bundle (task 7.5, invariants 4, 6 and 7). Pure functions over the bundle's files: a finding names the file
// and the kind of finding, never the address or the string found.
export interface FichierBundle {
  nom: string; // relative to the bundle folder, "/" separators
  contenu: string;
}

// Sentinel strings of the synthetic dataset (tests/mothra_donnees/jeu_synthetique.py, SENTINELLES): written in table columns that
// no view exposes, so they must never reach the bundle. Only the shared prefix is kept: it catches every sentinel of the family,
// present and later, and no copy of the list can drift from the dataset.
const PREFIXE_SENTINELLE = "SENTINELLE-";

// Hosts of absolute addresses that are only identifiers or documentation links of the libraries, never requested: XML namespaces of
// the DOM, the page that decodes React's production error codes, and the documentation links of react-intl's error messages
// (formatjs.github.io), and the base address of TypeBox's uri-reference format check, carried by the front's check of the answer
// (example.com, reserved by RFC 2606, only passed to URL.canParse, never requested). Extended only by a commit the author reviews.
export const HOTES_ADMIS = ["www.w3.org", "react.dev", "formatjs.github.io", "example.com"] as const;

const EXTENSIONS_ADMISES = [".html", ".js", ".css"];
// The font files of IBM Plex Sans and IBM Plex Serif (licence OFL-1.1, packages of the Fontsource project, design D10) are the only font
// files admitted: a closed list of file names (family, weight, normal style, latin subset), under assets/ of the bundle, with the hash
// vite appends (8 characters) and one of the two formats the packages' style sheets name. Authorised by R-20261031-74; never a general
// extension. Replaces: nothing. Removal: falls if the fonts are dropped.
export const POLICES_ADMISES = [
  "ibm-plex-sans-latin-400-normal",
  "ibm-plex-sans-latin-500-normal",
  "ibm-plex-sans-latin-600-normal",
  "ibm-plex-sans-latin-700-normal",
  "ibm-plex-serif-latin-500-normal",
  "ibm-plex-serif-latin-600-normal",
] as const;
const DOSSIER_POLICES = "assets/";
const FICHIER_POLICE = new RegExp(`^${DOSSIER_POLICES}(?:${POLICES_ADMISES.join("|")})-[A-Za-z0-9_-]{8}\\.(?:woff2|woff)$`);
// The logos (public/logos/, copied to logos/ of the bundle) are the only .svg files admitted. Their C2PA provenance block declares the
// c2pa.org namespace; that host is admitted only as the value of an XML namespace attribute (xmlns:name="http://c2pa.org/...") of such
// a file, an identifier that is never requested. Anywhere else the same address stays refused (decision of 2026-10-27).
const DOSSIER_LOGOS = "logos/";
const ESPACE_DE_NOMS_C2PA = /(?<![\w:-])xmlns(?::[\w.-]+)?\s*=\s*(["'])http:\/\/c2pa\.org\/[^"'<>\s]*\1/g;
const ADRESSE_ABSOLUE = /\b(?:https?|wss?|ftp):\/\/([a-z0-9.-]+)/gi;
const ADRESSE_SANS_PROTOCOLE = /["'`(]\/\/[a-z0-9-]+(?:\.[a-z0-9-]+)+/i;
const CDN = /(?:^|[^a-z0-9])(?:cdn|cdnjs|unpkg|jsdelivr|googleapis|gstatic|bootstrapcdn|fastly|akamai|cloudflare)(?:[^a-z0-9]|$)/i;
const APPELS_EXTERNES = /\b(?:XMLHttpRequest|WebSocket|EventSource|sendBeacon|importScripts)\b/;
const SCRIPT_EN_LIGNE = /<script\b[^>]*>([^<]+)<\/script>/gi;
const DONNEES_EN_LIGNE = /<script[^>]*type\s*=\s*["']application\/(?:ld\+)?json["']|data:(?:application\/json|text\/csv)/i;
const LIGNES_EMBARQUEES = /["']?rows["']?\s*:\s*\[\s*[{[]/;

export function controlerBundle(fichiers: readonly FichierBundle[]): string[] {
  const trouves: string[] = [];
  for (const { nom, contenu } of fichiers) {
    const logo = nom.startsWith(DOSSIER_LOGOS) && nom.endsWith(".svg");
    const police = FICHIER_POLICE.test(nom);
    if (!logo && !police && !EXTENSIONS_ADMISES.some((e) => nom.endsWith(e))) trouves.push(`${nom} : type de fichier non admis (donnée embarquée possible)`);
    if (contenu.includes(PREFIXE_SENTINELLE)) {
      trouves.push(`${nom} : chaîne sentinelle du jeu synthétique`);
    }
    const aScruter = logo ? contenu.replace(ESPACE_DE_NOMS_C2PA, "") : contenu;
    const horsListe = [...aScruter.matchAll(ADRESSE_ABSOLUE)].filter((m) => !(HOTES_ADMIS as readonly string[]).includes(m[1].toLowerCase()));
    if (horsListe.length > 0) trouves.push(`${nom} : adresse absolue hors liste (${horsListe.length})`);
    if (ADRESSE_SANS_PROTOCOLE.test(contenu)) trouves.push(`${nom} : adresse sans protocole`);
    if ((nom.endsWith(".html") || nom.endsWith(".css")) && CDN.test(contenu)) trouves.push(`${nom} : adresse de CDN`);
    const appel = APPELS_EXTERNES.exec(contenu);
    if (appel) trouves.push(`${nom} : appel externe possible (${appel[0]})`);
    if (nom.endsWith(".html")) {
      if ([...contenu.matchAll(SCRIPT_EN_LIGNE)].some((m) => m[1].trim() !== "")) trouves.push(`${nom} : script en ligne`);
      if (DONNEES_EN_LIGNE.test(contenu)) trouves.push(`${nom} : donnée en ligne`);
    }
    if (DONNEES_EN_LIGNE.test(contenu) && !nom.endsWith(".html")) trouves.push(`${nom} : donnée en ligne`);
    if (LIGNES_EMBARQUEES.test(contenu)) trouves.push(`${nom} : lignes de vue embarquées`);
  }
  return trouves;
}
