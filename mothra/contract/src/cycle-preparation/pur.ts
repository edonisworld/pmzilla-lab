// The pure subpath of the page "preparation of a cycle" (`@mothra/contract/cycle-preparation`, author's decision R-20261031-62, Q115): the codes
// and the pure functions only, for the front. No typebox and no schema, directly or through what it imports at run time (types are erased);
// a static test of cycle-preparation-fonctions.test.ts checks it. The schemas stay in schemas.ts, reached by the package entry.
// Adding this subpath to the list of sous-chemins-purs.test.ts is task 41.1's.
export {
  CODES_AVIS,
  CODES_ETAT_PAGE,
  CODES_ETAT_VIDE,
  CODES_REFUS_PAGE,
  CODES_SOURCE_READY,
  CODE_COMPTES_REELS_MASQUES,
  CODE_DOMAINE_TROP_PETIT,
  MOTIF_CLE_CYCLE,
} from "./codes.ts";
export type { CodeAvis, CodeEtatPage, CodeEtatVide, CodeRefusPage, CodeSourceReady } from "./codes.ts";
export { EQUIPES_MINIMUM_DOMAINE, cadrerSelonMapping, choisirCycle, choisirEtats, totalDesCellules, verifierPorteeDomaine } from "./fonctions.ts";
export type { CycleCle, EntreeEtats, EtatCycle, ResultatCycle, ResultatEtats, ResultatPortee } from "./fonctions.ts";
