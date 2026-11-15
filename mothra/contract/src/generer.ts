// Generator of the JSON Schema files of contrats/schemas/ from the TypeBox schemas (mothra-slices D5), and their freshness check.
// Author's command, in mothra/contract: `npm run generer` (writes the tracked files). The freshness test never writes.
// Published form: internal TypeBox markers (keys starting with "~") dropped, object keys sorted, two-space indent, final newline.
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { SchemaCellule } from "./cellule.ts";
import { SchemaReponseVue } from "./reponse.ts";
import { SchemaVues } from "./vues.ts";

const RACINE = new URL("../../../", import.meta.url);

function normaliser(valeur: unknown): unknown {
  if (Array.isArray(valeur)) {
    return valeur.map(normaliser);
  }
  if (valeur !== null && typeof valeur === "object") {
    const sortie: Record<string, unknown> = {};
    for (const cle of Object.keys(valeur).sort()) {
      if (!cle.startsWith("~")) {
        sortie[cle] = normaliser((valeur as Record<string, unknown>)[cle]);
      }
    }
    return sortie;
  }
  return valeur;
}

function publier(schema: unknown): string {
  return `${JSON.stringify(normaliser(schema), null, 2)}\n`;
}

// File path (from the root of the workspace) to its expected content.
export function genererSchemas(): Record<string, string> {
  return {
    "contrats/schemas/cellule.schema.json": publier(SchemaCellule),
    "contrats/schemas/reponse-vue.schema.json": publier(SchemaReponseVue),
    "contrats/schemas/vues.schema.json": publier(SchemaVues),
  };
}

// `lire` returns the tracked content of a file, or undefined when it is missing. A stale or missing file is named, in French,
// the runner's language.
export function verifierFraicheur(attendus: Record<string, string>, lire: (chemin: string) => string | undefined): string[] {
  const refus: string[] = [];
  for (const [chemin, contenu] of Object.entries(attendus)) {
    if (lire(chemin) !== contenu) {
      refus.push(`schéma JSON périmé : ${chemin} (régénérer)`);
    }
  }
  return refus;
}

if (process.argv[1] !== undefined && fileURLToPath(import.meta.url) === process.argv[1]) {
  for (const [chemin, contenu] of Object.entries(genererSchemas())) {
    writeFileSync(new URL(chemin, RACINE), contenu);
    console.log(`écrit : ${chemin}`);
  }
}
