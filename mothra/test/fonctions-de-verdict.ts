// Static check of "no verdict, state or share computed in the formatting of a route or in a component" (design D30, task 18.4): the files
// of `server/src/routes/` and `front/src/` never name a verdict or composition function. Only `contract/src/` (the functions) and
// `server/src/fiches/corps.ts` (which hands the views to `corpsDepuisVues`) and `server/src/service.ts` (which calls `partsDAttente`) may. Pure function over file contents: no network, no install.
// Replaces: nothing. Removal condition: permanent (it guards D30). Source of the names: contract/src/verdict.ts, corps-fiche.ts, parts-attente.ts and
// lead-cycle.ts; a function added there that composes a verdict, a state or a share is added to this list in the same branch.
import type { Fichier } from "./frontieres.ts";

export const FONCTIONS_DE_VERDICT = [
  "h1Verdict",
  "h5Verdict",
  // Audit #629, A-01: the same verdict functions with the finding of the verdict, and the one that bars a confirmation (source: contract/src/verdict.ts).
  "h1Evaluer",
  "h5Evaluer",
  "constatsFinaux",
  "referenceH5",
  "attachmentSignal",
  "unplannedWorkExplanation",
  "verdictFinal",
  "twoThresholds",
  "echantillonSuffisant",
  "thresholdModifiedAfterReading",
  "linkColour",
  "corpsDepuisVues",
  "tableauLeadCycle",
  "mesureDeStatistique", // composes "insufficient sample"
  "lireSeuils", // composes "threshold modified after reading"
  // Task 37.1: the panel functions compose a range total and the share of throughput in correction (source: contract/src/panneaux.ts).
  "panneauStoriesInout",
  "panneauDefectsInout",
  "panneauCorrectionShare",
  "panneauBlockedShare",
  "partDeDebitEnCorrection",
  // mothra-demo-habillage lot 1b (R-20261101-20): the bars of the share of waiting are composed by the contract and called by the service layer
  // (server/src/service.ts), never by a route or a component (source: contract/src/parts-attente.ts). Replaces: nothing. Removal: permanent
  // (it guards D30).
  "partsDAttente",
] as const;

// Task 19.5/19.6: the functions of the reduced form. Their names are also field names of the answer (`throughputPositions`, the method's
// `coverageState`) which the front reads, so only a use that is not a property access nor an object key is an offence (a call, an import,
// a shorthand). Source: contract/src/verdict.ts and reduction.ts. Replaces: nothing. Removal: permanent (it guards D30 and D34).
export const FONCTIONS_DE_REDUCTION = ["throughputPositions", "coverageState", "reduceToStatistics"] as const;

// `reduceToStatistics` may also be named in the service layer of the server (server/src/fiches/ and server/src/service.ts), which are not
// watched folders; the watched ones are the routes and the front.
const DOSSIERS_SURVEILLES = ["server/src/routes/", "front/src/"];

function sansCommentairesNiChaines(contenu: string): string {
  return contenu
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/^\s*\/\/.*$/gm, "")
    .replace(/\s\/\/.*$/gm, "")
    .replace(/"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'|`(?:[^`\\]|\\.)*`/g, '""');
}

export function verifierFonctionsDeVerdict(fichiers: Fichier[]): string[] {
  const ecarts: string[] = [];
  for (const { chemin, contenu } of fichiers) {
    if (!DOSSIERS_SURVEILLES.some((d) => chemin.startsWith(d))) continue;
    const code = sansCommentairesNiChaines(contenu);
    for (const nom of FONCTIONS_DE_VERDICT) {
      if (new RegExp(`\\b${nom}\\b`).test(code)) {
        ecarts.push(`verdict calculé hors du service : ${chemin} nomme « ${nom} », réservé au contrat et à server/src/fiches/corps.ts`);
      }
    }
    for (const nom of FONCTIONS_DE_REDUCTION) {
      if (new RegExp(`(?<![.\\w])${nom}\\b(?!\\s*:)`).test(code)) {
        ecarts.push(`réduction ou position calculée hors du service : ${chemin} nomme « ${nom} », réservé au contrat et à la couche de service`);
      }
    }
  }
  return ecarts;
}
