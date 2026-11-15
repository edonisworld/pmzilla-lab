// Start sequence (mothra-slices D7 and D17), in this order: contract (exit 3), configuration (exit 5), environment (exit 4: loopback and
// session rule, which read the validated settings). Nothing listens and nothing connects before the three checks pass.
// The pool of the database opens its connections lazily, on the first query: creating the access object is not a connection.
import { existsSync } from "node:fs";
import { join } from "node:path";

import { REAL_DATA_COUNTS_ALLOWED, RefusContrat, chargerContrat, motifsDeNoms, seuilEffectif } from "@mothra/contract";
import { identifiantEquipe } from "@mothra/contract/equipe";
import type { Contrat } from "@mothra/contract";
import type { FastifyInstance } from "fastify";

import { chargerConfiguration } from "./config/index.ts";
import type { Configuration, Environnement } from "./config/index.ts";
import type { AccesVues } from "./db/acces.ts";
import { creerAccesPostgres, marqueurPostgres } from "./db/base.ts";
import { creerAccesStockage } from "./db/stockage.ts";
import type { AccesStockage, AccesStockageComplet } from "./db/stockage.ts";
import { creerCalculCorps } from "./fiches/corps.ts";
import { creerCalculPanneaux } from "./fiches/panneaux.ts";
import { creerCalculTableau } from "./fiches/tableau.ts";
import { reduitEnMode } from "./service.ts";
import type { ModeDonnees } from "./service.ts";
import { PHRASE_COLLISION_EQUIPES, collisionsDIdentifiants, nomsDEquipes } from "./fiches/equipes.ts";
import { RefusDemarrage } from "./refus.ts";
import { AVERTISSEMENT_BUNDLE_ABSENT, DOSSIER_BUNDLE_STANDARD } from "./routes/bundle.ts";
import { construireServeur } from "./routes/serveur.ts";

// Slice 0 listens on 127.0.0.1 only, and connects to the database on the loopback only (three spellings of it).
export const ADRESSE_LOCALE = "127.0.0.1";
export const ADRESSES_BASE_LOCALES: readonly string[] = ["127.0.0.1", "::1", "localhost"];
export const PORT_STANDARD_BASE = 5432;

// The session rule is that of tests/db/garde_base_jetable.py: a throwaway port in strict decimal form (checked by the configuration
// module), other than the standard one, and equal to the lab connection port when that one is set.
export function verifierEnvironnement(config: Configuration): void {
  if (config.ecoute.hote !== ADRESSE_LOCALE || !ADRESSES_BASE_LOCALES.includes(config.base.hote)) {
    throw new RefusDemarrage("NOT_LOOPBACK");
  }
  if (config.session) {
    const jetable = config.baseJetable ? config.base.port : null;
    if (jetable === null || jetable === PORT_STANDARD_BASE || (config.portLab !== null && config.portLab !== jetable)) {
      throw new RefusDemarrage("SESSION_WITHOUT_THROWAWAY_DB");
    }
    // A-61 (audit 629, L3-02): a session serves the synthetic dataset only (invariant 7, mothra/CLAUDE.md "Start the server outside the
    // throwaway database, or use real data"). Same code and exit 4 as the rule above: it is the same session rule.
    // Remplace : rien (le contrôle de marqueur de verifierJeuDeDonnees ne couvre pas une base jetable sans marqueur). Retrait : permanent
    // tant que les sessions ne lisent aucune donnée réelle (règle de la racine).
    if (config.jeu !== "synthetic") {
      throw new RefusDemarrage("SESSION_WITHOUT_THROWAWAY_DB");
    }
  }
}

export interface OptionsDemarrage {
  cheminContrat: string | URL;
  lireFichier?: (chemin: string) => string;
  // The reader of the two lists of names (default: the file system); a test gives its own, never the real lists.
  lireListe?: (chemin: string) => string;
  creerAcces?: (config: Configuration) => AccesVues;
  // The second connection, the storage role's (task 16.1); lazy like the first.
  creerStockage?: (config: Configuration) => AccesStockage;
  // Whether the marker of the synthetic dataset exists in the database (design D34); default: the catalogue lookup under the view role.
  lireMarqueur?: (config: Configuration) => Promise<boolean>;  journal?: { level: string; stream?: { write(message: string): void } } | false;
  // The folder of the built bundle (default: mothra/front/dist) and the sink of the start warnings (default: the standard error).
  dossierBundle?: string;
  avertir?: (message: string) => void;
  // The team identifier function (default: identifiantEquipe of the contract). A test gives a declared double of the hash to force a collision.
  identifiantEquipe?: (nom: string) => string;
  // The day of the reading, the data date of the dashboard (default: today, ISO date); a test fixes it.
  aujourdhui?: () => string;
}

export interface Serveur {
  app: FastifyInstance;
  config: Configuration;
  contrat: Contrat;
  stockage: AccesStockage;
  // The compiled patterns of the two lists of names, read at start-up; given to the sheet routes (`fiches.motifsNoms`) when they are
  // wired, with the storage of the sheets and the body builder, which do not exist yet.
  motifsNoms: readonly RegExp[];
  // The view access; its pool is closed on a refusal when it has one (the default access has, a test double may not).
  acces: AccesVues & { fermer?: () => Promise<void> };
  routes: Array<{ method: string; url: string }>;
  // Whether the sheet routes are registered: with a complete storage access, on either dataset (the guard "synthetic only" of task 18.4 was
  // removed by task 19.5, in the branch of `reduceToStatistics`).
  fichesEnregistrees: boolean;
  // Mutable state decided after the start checks: the sheet routes are switched off when two team names give one identifier.
  etat: { fichesDesactivees: boolean };
}

function stockageComplet(s: AccesStockage): s is AccesStockageComplet {
  const x = s as Partial<AccesStockageComplet>;
  return typeof x.seuils === "function" && typeof x.creer === "function" && typeof x.utilisateurExiste === "function" && typeof x.creeeLe === "function";
}

// The last start check, the only one that connects (design D17, D34): the database marker against MOTHRA_DATASET. `synthetic` on a database
// without the marker, or `real` on a database with it, stops the start, exit 4, naming neither the database nor a value.
export async function verifierJeuDeDonnees(
  config: Configuration,
  lireMarqueur: (config: Configuration) => Promise<boolean>,
): Promise<void> {
  const marqueur = await lireMarqueur(config);
  if ((config.jeu === "synthetic") !== marqueur) {
    throw new RefusDemarrage("DATASET_MISMATCH");
  }
}

// The whole start before listening: contract (3), configuration (5), environment (4: loopback, session rule, then the dataset check).
// It never listens; the entry listens after it. On a refusal the pools are closed, nothing having connected but the one lookup.
export async function demarrer(env: Environnement, options: OptionsDemarrage): Promise<Serveur> {
  const serveur = preparer(env, options);
  try {
    await verifierJeuDeDonnees(serveur.config, options.lireMarqueur ?? marqueurPostgres);
    // Two team names must not give one identifier (R-20261030-61): otherwise the sheet routes are not served, the rest is.
    if (serveur.fichesEnregistrees) {
      const seuil = seuilEffectif(serveur.contrat, serveur.config.seuil, null);
      const noms = await nomsDEquipes(serveur.acces, serveur.contrat, seuil);
      if (collisionsDIdentifiants(noms, options.identifiantEquipe ?? identifiantEquipe).length > 0) {
        serveur.etat.fichesDesactivees = true;
        (options.avertir ?? ((message: string) => console.error(message)))(PHRASE_COLLISION_EQUIPES);
      }
    }
  } catch (erreur) {
    await serveur.app.close().catch(() => undefined);
    await serveur.stockage.fermer().catch(() => undefined);
    await serveur.acces.fermer?.().catch(() => undefined);
    throw erreur;
  }
  return serveur;
}

export function preparer(env: Environnement, options: OptionsDemarrage): Serveur {
  let contrat: Contrat;
  try {
    contrat = chargerContrat(options.cheminContrat);
  } catch (erreur) {
    if (erreur instanceof RefusContrat) {
      throw new RefusDemarrage(erreur.code);
    }
    throw erreur;
  }
  const config = chargerConfiguration(env, options.lireFichier, options.lireListe);
  verifierEnvironnement(config);
  const acces = (options.creerAcces ?? creerAccesPostgres)(config);
  const stockage = (options.creerStockage ?? creerAccesStockage)(config);
  const dossierBundle = options.dossierBundle ?? DOSSIER_BUNDLE_STANDARD;
  const motifsNoms = motifsDeNoms([...config.noms.sensibles, ...config.noms.equipes]);
  const etat = { fichesDesactivees: false };
  // Task 19.5 (D34): the sheet routes no longer depend on the dataset (the guard of task 18.4, Q9, is removed): on real data the service
  // layer reduces every body to statistics and the routes register the schema without any count field.
  const fichesEnregistrees = stockageComplet(stockage);
  const mode: ModeDonnees = { jeu: config.jeu, comptesAutorises: REAL_DATA_COUNTS_ALLOWED, afficherNoms: config.afficherNomsEquipes };
  const { app, routes } = construireServeur({
    contrat,
    acces,
    reglageSeuil: config.seuil,
    journal: options.journal ?? { level: "info" },
    dossierBundle,
    vuesFermees: reduitEnMode(mode),
    afficherNoms: config.afficherNomsEquipes,
    ...(fichesEnregistrees && stockageComplet(stockage)
      ? {
          fiches: {
            depot: stockage,
            ...creerCalculCorps({
              acces,
              contrat,
              seuil: seuilEffectif(contrat, config.seuil, null),
              depot: stockage,
              identifiantEquipe: options.identifiantEquipe ?? identifiantEquipe,
              mode,
            }),
            motifsNoms,
            desactivees: () => etat.fichesDesactivees,
            reduite: reduitEnMode(mode),
            ...(options.aujourdhui ? { aujourdhui: options.aujourdhui } : {}),
          },
          tableaux: {
            ...creerCalculTableau({
              acces,
              contrat,
              seuil: seuilEffectif(contrat, config.seuil, null),
              depot: stockage,
              identifiantEquipe: options.identifiantEquipe ?? identifiantEquipe,
              aujourdhui: options.aujourdhui ?? (() => new Date().toISOString().slice(0, 10)),
            }),
            mode,
            desactivees: () => etat.fichesDesactivees,
          },
          // The panel routes of the product-scope dashboard (task 37.1): cut after a collision of team identifiers, like the sheets.
          panneaux: {
            ...creerCalculPanneaux({
              acces,
              contrat,
              seuil: seuilEffectif(contrat, config.seuil, null),
              identifiantEquipe: options.identifiantEquipe ?? identifiantEquipe,
            }),
            mode,
            aujourdhui: options.aujourdhui ?? (() => new Date().toISOString().slice(0, 10)),
            desactivees: () => etat.fichesDesactivees,
          },
        }
      : {}),
  });
  // A bundle not built is not a refusal (answer Q4): the server starts, warns once without a path, and answers BUNDLE_MISSING on its pages.
  if (!existsSync(join(dossierBundle, "index.html"))) {
    (options.avertir ?? ((message: string) => console.error(message)))(AVERTISSEMENT_BUNDLE_ABSENT);
  }
  return { app, config, contrat, stockage, motifsNoms, acces, routes, fichesEnregistrees, etat };
}
