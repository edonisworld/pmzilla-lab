// The names of the two lists a written text is checked against (design D20, task 18.3): the part of `tools/sensitive_names.py` that picks
// the distinctive names of the team-names extract (`is_distinctive`, `generic_names`, the dependency-free reader of the extract), ported to
// TypeScript. The list of sensitive names is read with `lireNoms` (texte.ts). Pure functions: the server reads the files, never this module.
import { lignesDeLaListe, lireNoms } from "./texte.ts";

const LONGUEUR_MIN = 6;

// The closed list of common words of `tools/sensitive_names.py` (COMMON_WORDS), copied; a gap between the two is caught by the parity
// cases of test-data/cas-noms.json played against the Python functions.
const MOTS_COURANTS = new Set(
  `team teams equipe equipes squad squads platform platforms plateforme plateformes support service services product products produit
produits data donnees core domain domains domaine domaines backend frontend front back quality qualite delivery livraison
integration integrations infrastructure security securite operations operation ops development developpement verification
validation management gestion other autre autres group groups groupe groupes project projects projet projets business mobile
cloud release releases test tests testing design research architecture program programme tooling outils outil devops engineering
ingenierie solutions solution systems systemes system experience client clients customer customers pilotage transverse commun
communs common shared partage tech technique technical application applications applicatif logiciel software hardware reseau
network analytics analyse analyses reporting discovery strategy strategie growth marketing sales finance legal compliance
conformite payment payments paiement paiements billing facturation portal portail gateway workflow workflows pipeline pipelines
monitoring supervision observability reliability fiabilite performance enablement capability capabilities foundation
foundations enterprise global regional central digital innovation success onboarding search recherche catalog catalogue
content contenu media identity identite access acces account accounts compte comptes maintenance exploitation operationnel
conception formation accompagnement soutien parcours flux stream streams enabling complicated subsystem sous-systeme
process processus programs office train planning roadmap backlog sprint agile scrum kanban`.split(/\s+/),
);

// Python's `str.casefold`, for the comparison of a name with the generic list and of a word with the common words: the full case folding
// ("Straße" and "STRASSE" meet, as do a final and a medial sigma), approximated by an upper-case then lower-case round trip, which gives the
// same result on every letter that has a folding.
function replierCasse(texte: string): string {
  return texte.toUpperCase().toLowerCase();
}

function simple(texte: string): string {
  return replierCasse(texte.normalize("NFD").replace(/\p{Mn}/gu, ""));
}

function estMotCourant(mot: string): boolean {
  return MOTS_COURANTS.has(simple(mot.trim()));
}

function motsLongs(libelle: string): string[] {
  return libelle
    .trim()
    .split(/[\s\-_]+/)
    .filter((m) => [...m].length > 3);
}

// A label to keep for the list: at least 6 characters (spaces at the ends not counted) and at least one word of more than three letters
// that is not a common word (`is_distinctive`).
export function estDistinctif(libelle: string): boolean {
  const propre = libelle.trim();
  return [...propre].length >= LONGUEUR_MIN && motsLongs(propre).some((m) => !estMotCourant(m));
}

const SECTIONS_EXTRAIT = ["referential_teams", "catalogue_teams"];

// The `name:` lines of the two sections of the extract, bare or quoted (the dependency-free reader of the Python tool). The lines are cut as
// Python's `splitlines` cuts them (a lone carriage return included), and leading byte-order marks are dropped.
function nomsBrutsDeLExtrait(texte: string): string[] {
  const noms: string[] = [];
  let section: string | null = null;
  for (const ligne of lignesDeLaListe(texte)) {
    if (ligne !== "" && !/^\s/.test(ligne) && !ligne.startsWith("-")) {
      section = ligne.split(":", 1)[0].trim();
      continue;
    }
    const m = /^\s*(?:-\s+)?name:\s*(.*?)\s*$/.exec(ligne);
    if (m !== null && section !== null && SECTIONS_EXTRAIT.includes(section)) {
      let valeur = m[1];
      if (valeur.length >= 2 && valeur[0] === "'" && valeur[valeur.length - 1] === "'") {
        valeur = valeur.slice(1, -1).replace(/''/g, "'");
      } else if (valeur.length >= 2 && valeur[0] === '"' && valeur[valeur.length - 1] === '"') {
        valeur = valeur.slice(1, -1).replace(/\\"/g, '"');
      }
      noms.push(valeur);
    }
  }
  return noms;
}

// The distinctive names of the extract, without duplicate, less the names of the neighbouring generic list (`extract_names`): that list is
// one name per line, compared case-folded, whole name.
export function nomsDistinctifsDeLExtrait(extrait: string, generiques: string): string[] {
  const exclus = new Set(lireNoms(generiques).map(replierCasse));
  const vus: string[] = [];
  for (const brut of nomsBrutsDeLExtrait(extrait)) {
    const nom = brut.trim();
    if (!vus.includes(nom) && estDistinctif(nom) && !exclus.has(replierCasse(nom))) vus.push(nom);
  }
  return vus;
}
