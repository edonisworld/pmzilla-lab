// Typed configuration module (mothra-slices D17): the closed list of settings and secrets of the server, validated at start-up before
// listening and before any connection. It is the ONLY module of the server that reads the environment (a static test checks it): every
// other module receives the typed, validated object.
// A refusal names the variable, never its value and never the content of a secret file. Unknown variables are ignored, never echoed.
import { readFileSync, realpathSync, statSync } from "node:fs";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

import { PLANCHER, lireNoms, nomsDistinctifsDeLExtrait } from "@mothra/contract";
import Type from "typebox";
import Value from "typebox/value";

import { RefusDemarrage } from "../refus.ts";

export type Environnement = Record<string, string | undefined>;

export const VARIABLES = {
  hote: "MOTHRA_HOST",
  port: "MOTHRA_PORT",
  seuil: "MOTHRA_THRESHOLD",
  jeu: "MOTHRA_DATASET",
  baseHote: "MOTHRA_DB_HOST",
  baseNom: "MOTHRA_DB_NAME",
  basePort: "PMZILLA_LAB_DB_PORT",
  basePortJetable: "DBTEST_PORT",
  // The secret of Mothra's own views role (audit #629 A-80, decision R-20261107-26 (3a)): no longer the secret of pmzilla_flow_views, which stays
  // the role of tools/flow_views.py.
  secretBase: "PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS",
  secretBaseFichier: "PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS_FILE",
  // Second secret (task 16.1, ADR 0006): the storage role of the schema mothra, same sources as the first.
  secretStockage: "PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA",
  secretStockageFichier: "PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_FILE",
  // The two lists of names a written text is checked against (task 18.3, design D17, D20, ADR 0007): paths read once at start-up, by the
  // server only. On the Mac the author's launch sets them to the files the pre-commit hook reads; hosted, to mounted files.
  nomsSensibles: "MOTHRA_SENSITIVE_NAMES_FILE",
  nomsEquipes: "MOTHRA_TEAM_NAMES_FILE",
  // The team-name display (D17, D35, R-20261104-33 and -35): off by default; falls with single sign-on (R-20261104-36, N3 (a)).
  afficherNomsEquipes: "MOTHRA_SHOW_TEAM_NAMES",
  // Audit #629, A-67 (b), R-20261107-30: the path of flux.yaml, read at start-up for its `flow_views_min_cell` only, to refuse a threshold that
  // differs from the Python one. Optional: absent, the start is as before (no comparison).
  // Remplace / retrait : tombe au désherbage d'Hydra (flux.yaml source unique, MOTHRA_THRESHOLD retiré).
  reglagesFlux: "MOTHRA_FLUX_SETTINGS_FILE",
  marqueurSession: "CLAUDECODE",
} as const;

// The only role the server connects under for the views: Mothra's own views role, limited to the views of contrats/vues.json (invariant 1,
// audit #629 A-80). It is not pmzilla_flow_views, the role shared with tools/flow_views.py. Not a setting.
export const ROLE_DES_VUES = "pmzilla_mothra_views";
// The only role of the server's second connection: the storage role, limited to the schema mothra (ADR 0006). Not a setting.
export const ROLE_DE_STOCKAGE = "pmzilla_mothra";

const SchemaHote = Type.String({ pattern: "^[A-Za-z0-9._:-]{1,255}$" });
// Strict decimal form, as tests/db/garde_base_jetable.py: no sign, no space, no leading zero, 1 to 5 digits (the bound 65535 is checked after).
const SchemaPort = Type.String({ pattern: "^[1-9][0-9]{0,4}$" });
const SchemaNomDeBase = Type.String({ pattern: "^[a-z][a-z0-9_]{0,62}$" });
const SchemaSeuil = Type.String({ pattern: "^[0-9]{1,9}$" });

export type JeuDeDonnees = "synthetic" | "real";
const JEUX: readonly string[] = ["synthetic", "real"];

export interface Configuration {
  ecoute: { hote: string; port: number };
  base: { hote: string; port: number; nom: string; utilisateur: string; motDePasse: () => string };
  // The second connection: same server and database, the storage role and its own secret.
  stockage: { hote: string; port: number; nom: string; utilisateur: string; motDePasse: () => string };
  seuil: number | null;
  // The two lists of names, read at start-up: the sensitive names and the distinctive names of the team-names extract. Never empty.
  noms: { sensibles: string[]; equipes: string[] };
  // The dataset setting (design D17, D34): mandatory, no default.
  jeu: JeuDeDonnees;
  // The team-name display setting (D35): false when absent or `false`, true for `true`; any other value is refused at start.
  afficherNomsEquipes: boolean;
  // The lab connection port variable (PMZILLA_LAB_DB_PORT) when it is set, null otherwise.
  portLab: number | null;
  // The Claude Code session marker is set.
  session: boolean;
  // The throwaway database port variable is set.
  baseJetable: boolean;
}

type LireFichier = (chemin: string) => string;

function present(env: Environnement, nom: string): string | undefined {
  const valeur = env[nom];
  return valeur === undefined || valeur === "" ? undefined : valeur;
}

function invalide(variable: string): never {
  throw new RefusDemarrage("SETTING_INVALID", variable);
}

function texte(env: Environnement, variable: string, schema: typeof SchemaHote, parDefaut?: string): string {
  const valeur = present(env, variable) ?? parDefaut;
  if (valeur === undefined) {
    throw new RefusDemarrage("SETTING_MISSING", variable);
  }
  if (!Value.Check(schema, valeur)) {
    return invalide(variable);
  }
  return valeur;
}

function port(env: Environnement, variable: string, parDefaut?: string): number {
  const nombre = Number(texte(env, variable, SchemaPort, parDefaut));
  return nombre <= 65535 ? nombre : invalide(variable);
}

// One secret: from the mounted file named by `<NAME>_FILE` when that variable is set, else from the per-role variable. A refusal names the
// variable it read (the file variable when the file is the source), never a value and never a path.
function secret(env: Environnement, lireFichier: LireFichier, variable: string, variableFichier: string): string {
  const fichier = present(env, variableFichier);
  if (fichier !== undefined) {
    let contenu: string;
    try {
      contenu = lireFichier(fichier);
    } catch {
      throw new RefusDemarrage("SECRET_MISSING", variableFichier);
    }
    const valeur = contenu.replace(/\r?\n$/, "");
    if (valeur === "") {
      throw new RefusDemarrage("SECRET_MISSING", variableFichier);
    }
    return valeur;
  }
  const direct = present(env, variable);
  if (direct === undefined) {
    throw new RefusDemarrage("SECRET_MISSING", variable);
  }
  return direct;
}

// One list of names: the path comes from the setting; a missing setting is SETTING_MISSING, a file that is missing, unreadable or without
// any name is SETTING_INVALID, naming the variable only, never the path, a name or the content. Never an empty list as a fallback.
function chemin(env: Environnement, variable: string): string {
  const valeur = present(env, variable);
  if (valeur === undefined) {
    throw new RefusDemarrage("SETTING_MISSING", variable);
  }
  return valeur;
}

function lire(lireFichier: LireFichier, variable: string, chemin: string): string {
  try {
    return lireFichier(chemin);
  } catch {
    return invalide(variable);
  }
}

function listeDeNoms(env: Environnement, lireFichier: LireFichier, variable: string): string[] {
  const noms = lireNoms(lire(lireFichier, variable, chemin(env, variable)));
  return noms.length === 0 ? invalide(variable) : noms;
}

// The team-names extract: only its distinctive names are kept, less the neighbouring generic list (absent or unreadable: none excluded).
function nomsDesEquipes(env: Environnement, lireFichier: LireFichier, variable: string): string[] {
  const fichier = chemin(env, variable);
  const extrait = lire(lireFichier, variable, fichier);
  let generiques = "";
  try {
    generiques = lireFichier(join(dirname(fichier), "noms-generiques.txt"));
  } catch {
    generiques = "";
  }
  const noms = nomsDistinctifsDeLExtrait(extrait, generiques);
  return noms.length === 0 ? invalide(variable) : noms;
}

// The folder of the fictitious lists (mothra/server/test/listes/), resolved from this module (mothra/server/src/config/).
const DOSSIER_LISTES_FICTIVES = resolve(dirname(fileURLToPath(import.meta.url)), "../../test/listes");

// Whether a path, once normalised (dot segments removed), lies inside the folder of the fictitious lists. A symbolic link is resolved
// when the file exists; a path that does not resolve is judged on its normalised text.
function dansListesFictives(chemin: string): boolean {
  let reel = resolve(chemin);
  try {
    reel = realpathSync(reel);
  } catch {
    // not resolvable: the normalised text decides
  }
  const dossier = (() => {
    try {
      return realpathSync(DOSSIER_LISTES_FICTIVES);
    } catch {
      return DOSSIER_LISTES_FICTIVES;
    }
  })();
  const rel = relative(dossier, reel);
  if (rel === "" || rel === ".." || rel.startsWith(`..${sep}`) || isAbsolute(rel)) {
    return false;
  }
  // A hard link placed under test/listes/ to a file elsewhere would pass the path test: a file with several links is refused.
  // Remplace : rien. Retrait : permanent tant que les sessions ne lisent aucune donnée réelle (avec A-62).
  try {
    if (statSync(reel).nlink > 1) {
      return false;
    }
  } catch {
    // absent file: the normalised text decided above
  }
  return true;
}

// The `flow_views_min_cell` of flux.yaml, read by one regular expression, without YAML (A-67 (b)). A missing key is the floor, as in
// `seuil_configure` of tools/flow_views.py; a value that is not a plain integer is SETTING_INVALID naming the file variable.
// Limits of the reading by regular expression, against the YAML reader of Python: a quoted value (`"5"`) is not a plain integer, so it is
// refused (closed); a key written twice gives the first one (Python's YAML would refuse the duplicate or keep the last); a broken YAML
// elsewhere in the file does not stop the start-up, where Python refuses the file. In each case the effect is closed or leaks nothing:
// the threshold read is never below the floor, and a wrong value only raises or keeps the masking.
// Remplace / retrait : tombe au désherbage d'Hydra (flux.yaml source unique, MOTHRA_THRESHOLD retiré).
const MOTIF_SEUIL_FLUX = /^flow_views_min_cell:[ \t]*([^\s#]*)[ \t]*(?:#.*)?$/m;

function seuilDeFlux(lireFichier: LireFichier, variable: string, fichier: string): number {
  const correspondance = MOTIF_SEUIL_FLUX.exec(lire(lireFichier, variable, fichier));
  if (correspondance === null) {
    return PLANCHER;
  }
  if (!Value.Check(SchemaSeuil, correspondance[1])) {
    return invalide(variable);
  }
  return Math.max(PLANCHER, Number(correspondance[1]));
}

// Validates the whole closed list; the first failing item stops, in the fixed order below.
// `lireFichier` reads the secret files; `lireListe` reads the two lists of names (a separate reader, so that a test that fakes the secret
// files does not have to serve the lists).
export function chargerConfiguration(
  env: Environnement,
  lireFichier: LireFichier = (chemin) => readFileSync(chemin, "utf8"),
  lireListe: LireFichier = (chemin) => readFileSync(chemin, "utf8"),
): Configuration {
  const hote = texte(env, VARIABLES.hote, SchemaHote, "127.0.0.1");
  const portEcoute = port(env, VARIABLES.port, "3000");
  const reglage = present(env, VARIABLES.seuil);
  if (reglage !== undefined && !Value.Check(SchemaSeuil, reglage)) {
    invalide(VARIABLES.seuil);
  }
  // The dataset setting: no default; missing is SETTING_MISSING, any other value than the two is SETTING_INVALID (the value is never echoed).
  const jeu = present(env, VARIABLES.jeu);
  if (jeu === undefined) {
    throw new RefusDemarrage("SETTING_MISSING", VARIABLES.jeu);
  }
  if (!JEUX.includes(jeu)) {
    invalide(VARIABLES.jeu);
  }
  // The team-name display: a closed boolean, off by default; any other text is SETTING_INVALID naming the variable only.
  const noms = present(env, VARIABLES.afficherNomsEquipes);
  if (noms !== undefined && noms !== "true" && noms !== "false") {
    invalide(VARIABLES.afficherNomsEquipes);
  }
  const baseJetable = present(env, VARIABLES.basePortJetable) !== undefined;
  const baseHote = texte(env, VARIABLES.baseHote, SchemaHote, "127.0.0.1");
  // No default database name: without MOTHRA_DB_NAME the server refuses to start (SETTING_MISSING naming the variable).
  const baseNom = texte(env, VARIABLES.baseNom, SchemaNomDeBase);
  const portLab = present(env, VARIABLES.basePort) === undefined ? null : port(env, VARIABLES.basePort);
  const portBase = baseJetable ? port(env, VARIABLES.basePortJetable) : port(env, VARIABLES.basePort);
  const mot = secret(env, lireFichier, VARIABLES.secretBase, VARIABLES.secretBaseFichier);
  const motStockage = secret(env, lireFichier, VARIABLES.secretStockage, VARIABLES.secretStockageFichier);
  // After the secrets: the earlier refusals keep their order.
  // A-62 (audit 629, L3-03): in a session the sensitive-names list can only be a fictitious list of mothra/server/test/listes/ (the 422
  // answer of a sheet text confirms a name: with a free path, the real closed list would be probed). Checked on the path text, before
  // any read; the refusal names the variable only. Replaces: nothing. Removal: permanent while sessions never read real data.
  if (present(env, VARIABLES.marqueurSession) !== undefined) {
    const liste = present(env, VARIABLES.nomsSensibles);
    if (liste !== undefined && !dansListesFictives(liste)) {
      invalide(VARIABLES.nomsSensibles);
    }
    // Same control for the team-names extract (R-20261107-27, decision 5): in a session only a fictitious list (realpath, hard link).
    // Replaces: nothing. Removal: permanent while sessions never read real data (with A-62).
    const extrait = present(env, VARIABLES.nomsEquipes);
    if (extrait !== undefined && !dansListesFictives(extrait)) {
      invalide(VARIABLES.nomsEquipes);
    }
  }
  const sensibles = listeDeNoms(env, lireListe, VARIABLES.nomsSensibles);
  const equipes = nomsDesEquipes(env, lireListe, VARIABLES.nomsEquipes);
  // A-67 (b): when the path of flux.yaml is given, both thresholds (the setting absent counting as the floor) must be equal; the refusal names
  // the two variables, never a value.
  const fichierFlux = present(env, VARIABLES.reglagesFlux);
  if (fichierFlux !== undefined) {
    const seuilFlux = seuilDeFlux(lireListe, VARIABLES.reglagesFlux, fichierFlux);
    if (Math.max(PLANCHER, reglage === undefined ? PLANCHER : Number(reglage)) !== seuilFlux) {
      throw new RefusDemarrage("SETTING_INVALID", `${VARIABLES.seuil} ${VARIABLES.reglagesFlux}`);
    }
  }
  return {
    noms: { sensibles, equipes },
    ecoute: { hote, port: portEcoute },
    base: { hote: baseHote, port: portBase, nom: baseNom, utilisateur: ROLE_DES_VUES, motDePasse: () => mot },
    stockage: { hote: baseHote, port: portBase, nom: baseNom, utilisateur: ROLE_DE_STOCKAGE, motDePasse: () => motStockage },
    seuil: reglage === undefined ? null : Number(reglage),
    jeu: jeu as JeuDeDonnees,
    afficherNomsEquipes: noms === "true",
    portLab,
    session: present(env, VARIABLES.marqueurSession) !== undefined,
    baseJetable,
  };
}

// The one place where the process environment is read.
export function lireEnvironnement(): Environnement {
  return process.env;
}
