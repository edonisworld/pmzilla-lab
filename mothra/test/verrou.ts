// Licence and registry check of the npm lock (design D16, task 2.6). Reads the lock text only: no network, no npm command.
import { readFileSync } from "node:fs";

const REGISTRE_PUBLIC = "https://registry.npmjs.org/";
const ESPACES: readonly string[] = ["contract", "server", "front"];

export function licencesAcceptees(): string[] {
  const donnees = JSON.parse(readFileSync(new URL("../contract/test-data/licences-acceptees.json", import.meta.url), "utf8"));
  return donnees.licences as string[];
}

// An exception admits one licence for one package, by exact package name, with a stated reason. Never a general licence.
export interface ExceptionLicence {
  paquet: string;
  licence: string;
  raison: string;
}

export function exceptionsDeLicence(): ExceptionLicence[] {
  const donnees = JSON.parse(readFileSync(new URL("../contract/test-data/licences-acceptees.json", import.meta.url), "utf8"));
  return (donnees.exceptions ?? []) as ExceptionLicence[];
}

// SPDX expression: identifiers joined by AND / OR, parentheses allowed. An identifier is accepted only if it is in the list,
// compared exactly (case included); WITH, unknown tokens and malformed expressions are refused.
function expressionAcceptee(expression: string, acceptees: readonly string[]): boolean {
  const jetons = expression.match(/\(|\)|[^\s()]+/g) ?? [];
  let i = 0;
  const ou = (): boolean => {
    let ok = et();
    while (jetons[i] === "OR") {
      i++;
      const suite = et();
      ok = ok || suite;
    }
    return ok;
  };
  const et = (): boolean => {
    let ok = atome();
    while (jetons[i] === "AND") {
      i++;
      const suite = atome();
      ok = ok && suite;
    }
    return ok;
  };
  const atome = (): boolean => {
    const jeton = jetons[i++];
    if (jeton === "(") {
      const ok = ou();
      if (jetons[i++] !== ")") throw new Error("expression");
      return ok;
    }
    if (jeton === undefined || jeton === ")" || jeton === "AND" || jeton === "OR" || jeton === "WITH") throw new Error("expression");
    return acceptees.includes(jeton);
  };
  try {
    const ok = ou();
    return ok && i === jetons.length;
  } catch {
    return false;
  }
}

function nomDuPaquet(chemin: string): string {
  const position = chemin.lastIndexOf("node_modules/");
  return chemin.slice(position + "node_modules/".length);
}

// A platform the author installs on: the Mac and the CI image. Data of contract/test-data/plateformes-installees.json, never a constant.
export interface Plateforme {
  os: string;
  cpu: string;
  libc?: string; // only a platform whose libc is known carries it (the CI image); absent for the Mac
}

export function plateformesInstallees(): Plateforme[] {
  const donnees = JSON.parse(readFileSync(new URL("../contract/test-data/plateformes-installees.json", import.meta.url), "utf8"));
  return donnees.plateformes as Plateforme[];
}

function liste(valeur: unknown): string[] | null {
  return Array.isArray(valeur) && valeur.length > 0 && valeur.every((v) => typeof v === "string") ? (valeur as string[]) : null;
}

// The platform label of an entry that is optional AND marked os or cpu for no installed platform, else null (the entry is checked).
// A field absent from the entry matches every platform; an entry with neither field is never ignored.
// An entry that matches an installed os and cpu is still ignored when its libc field excludes the libc of every platform of the same
// os and cpu that carries one. With no such platform carrying a libc, or with no libc field on the entry, the entry is checked.
function plateformeAutre(paquet: Record<string, unknown>, installees: readonly Plateforme[]): string | null {
  if (paquet.optional !== true || installees.length === 0) return null;
  const os = liste(paquet.os);
  const cpu = liste(paquet.cpu);
  if (os === null && cpu === null) return null;
  const memes = installees.filter((p) => (os === null || os.includes(p.os)) && (cpu === null || cpu.includes(p.cpu)));
  if (memes.length === 0) return `${os === null ? "*" : os.join("|")}-${cpu === null ? "*" : cpu.join("|")}`;
  const libc = liste(paquet.libc);
  if (libc === null) return null;
  const avecLibc = memes.filter((p) => typeof p.libc === "string");
  if (avecLibc.length === 0) return null;
  if (avecLibc.some((p) => libc.includes(p.libc as string))) return null;
  return `${os === null ? "*" : os.join("|")}-${cpu === null ? "*" : cpu.join("|")}-${libc.join("|")}`;
}

export interface Analyse {
  ecarts: string[];
  ignorees: string[]; // one platform label per ignored entry
}

// No licence, no path and no package name: only the count and the platforms.
export function messageIgnorees(ignorees: readonly string[]): string {
  if (ignorees.length === 0) return "";
  const plateformes = [...new Set(ignorees)].sort().join(", ");
  return `entrées optionnelles d'autres plateformes ignorées : ${ignorees.length} (${plateformes})`;
}

export function verifierVerrou(
  texte: string,
  acceptees: readonly string[],
  exceptions: readonly ExceptionLicence[] = [],
  installees: readonly Plateforme[] = [],
): string[] {
  return analyserVerrou(texte, acceptees, exceptions, installees).ecarts;
}

export function analyserVerrou(
  texte: string,
  acceptees: readonly string[],
  exceptions: readonly ExceptionLicence[] = [],
  installees: readonly Plateforme[] = [],
): Analyse {
  let verrou: { packages?: Record<string, Record<string, unknown>> };
  try {
    verrou = JSON.parse(texte);
  } catch {
    return { ecarts: ["verrou npm illisible"], ignorees: [] };
  }
  if (verrou === null || typeof verrou !== "object" || typeof verrou.packages !== "object" || verrou.packages === null) {
    return { ecarts: ["verrou npm illisible"], ignorees: [] };
  }
  const ignorees: string[] = [];
  const ecarts: string[] = [];
  const presents = new Set<string>();
  const valides: ExceptionLicence[] = [];
  for (const e of exceptions) {
    if (typeof e.raison !== "string" || e.raison.trim() === "") ecarts.push(`exception sans raison : ${e.paquet}`);
    else valides.push(e);
  }
  for (const [chemin, paquet] of Object.entries(verrou.packages)) {
    if (!chemin.includes("node_modules/")) continue; // root and workspace folders are not downloads
    const nom = nomDuPaquet(chemin);
    presents.add(nom);
    const autre = plateformeAutre(paquet, installees);
    if (paquet.link === true) {
      // A link is accepted only when it points one of the three workspaces; any other link is a package from outside the registry.
      if (typeof paquet.resolved !== "string" || !ESPACES.includes(paquet.resolved)) ecarts.push(`registre non public : ${nom}`);
      continue;
    }
    const resolu = paquet.resolved;
    if (typeof resolu !== "string" || !resolu.startsWith(REGISTRE_PUBLIC)) {
      ecarts.push(`registre non public : ${nom}`);
      continue;
    }
    if (typeof paquet.integrity !== "string" || paquet.integrity === "") {
      ecarts.push(`intégrité absente : ${nom}`);
      continue;
    }
    // Another platform skips the licence check only: link, public registry and integrity apply to every entry.
    if (autre !== null) {
      ignorees.push(autre);
      continue;
    }
    const licence = paquet.license;
    if (licence === undefined || licence === null || licence === "") {
      ecarts.push(`licence absente : ${nom}`);
      continue;
    }
    if (typeof licence !== "string") {
      ecarts.push(`licence refusée : ${nom} (${JSON.stringify(licence)})`);
      continue;
    }
    if (valides.some((e) => e.paquet === nom && e.licence === licence)) continue;
    if (!expressionAcceptee(licence, acceptees)) ecarts.push(`licence refusée : ${nom} (${licence})`);
  }
  for (const e of exceptions) {
    if (!presents.has(e.paquet)) ecarts.push(`exception sans paquet dans le verrou : ${e.paquet}`);
  }
  return { ecarts, ignorees };
}
