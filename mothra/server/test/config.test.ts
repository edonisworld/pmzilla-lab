// Task 6.8: the typed configuration module (design D17): closed list validated before listening, refusals naming the variable only.
import assert from "node:assert/strict";
import { test } from "node:test";

import { VARIABLES, chargerConfiguration } from "../src/config/index.ts";
import { RefusDemarrage } from "../src/refus.ts";
import { SECRET_SENTINELLE, SECRET_STOCKAGE_SENTINELLE, envMinimal } from "./aide.ts";

function refus(env: Record<string, string | undefined>, lireFichier?: (chemin: string) => string): RefusDemarrage {
  try {
    chargerConfiguration(env, lireFichier);
  } catch (erreur) {
    assert.ok(erreur instanceof RefusDemarrage, "a start refusal was expected");
    return erreur;
  }
  assert.fail("a refusal was expected");
}

test("a minimal environment gives the defaults and the view-limited role", () => {
  const config = chargerConfiguration(envMinimal());
  assert.equal(config.ecoute.hote, "127.0.0.1");
  assert.equal(config.ecoute.port, 3000);
  assert.equal(config.base.utilisateur, "pmzilla_mothra_views");
  assert.equal(config.base.port, 5432);
  assert.equal(config.base.nom, "mothra_test");
  assert.equal(config.base.motDePasse(), SECRET_SENTINELLE);
  assert.equal(config.seuil, null);
  assert.equal(config.session, false);
  assert.equal(config.baseJetable, false);
});

test("the throwaway database port wins over the real one and is flagged", () => {
  const config = chargerConfiguration(envMinimal({ DBTEST_PORT: "55432" }));
  assert.equal(config.base.port, 55432);
  assert.equal(config.baseJetable, true);
});

test("the session marker is read", () => {
  assert.equal(chargerConfiguration(envMinimal({ CLAUDECODE: "1" })).session, true);
});

test("the secret variable absent is SECRET_MISSING naming the variable", () => {
  const env = envMinimal();
  delete env[VARIABLES.secretBase];
  const erreur = refus(env);
  assert.equal(erreur.code, "SECRET_MISSING");
  assert.equal(erreur.sortie, 5);
  assert.equal(erreur.phrase, "mothra: refused (SECRET_MISSING) PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS");
});

test("an empty secret variable counts as absent", () => {
  assert.equal(refus(envMinimal({ [VARIABLES.secretBase]: "" })).code, "SECRET_MISSING");
});

// Q28 (audit #629, lot 5). Replaces nothing; permanent: it proves the former flow-views role secret is no longer read.
test("only the former _PMZILLA_FLOW_VIEWS secret set is SECRET_MISSING naming the new variable", () => {
  const env = envMinimal();
  delete env[VARIABLES.secretBase];
  env["PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW_VIEWS"] = SECRET_SENTINELLE;
  const erreur = refus(env);
  assert.equal(erreur.code, "SECRET_MISSING");
  assert.equal(erreur.phrase, "mothra: refused (SECRET_MISSING) PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS");
});

test("the secret comes from a mounted file named by the _FILE variable, without its final newline", () => {
  const env = envMinimal({ [VARIABLES.secretBaseFichier]: "/run/secrets/une-cle" });
  delete env[VARIABLES.secretBase];
  const config = chargerConfiguration(env, (chemin) => {
    assert.equal(chemin, "/run/secrets/une-cle");
    return `${SECRET_SENTINELLE}\n`;
  });
  assert.equal(config.base.motDePasse(), SECRET_SENTINELLE);
});

test("a secret file that does not exist is SECRET_MISSING naming the _FILE variable, never the path", () => {
  const env = envMinimal({ [VARIABLES.secretBaseFichier]: "/chemin/sentinelle/absent" });
  const erreur = refus(env, () => {
    throw new Error("ENOENT /chemin/sentinelle/absent");
  });
  assert.equal(erreur.code, "SECRET_MISSING");
  assert.equal(erreur.variable, "PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS_FILE");
  assert.ok(!erreur.phrase.includes("sentinelle"));
});

test("an empty secret file is SECRET_MISSING, and the file's content is never echoed", () => {
  const env = envMinimal({ [VARIABLES.secretBaseFichier]: "/run/secrets/vide" });
  const erreur = refus(env, () => "\n");
  assert.equal(erreur.code, "SECRET_MISSING");
});

test("a port setting that is not a port number is SETTING_INVALID and the sentinel text is absent from the output", () => {
  const sentinelle = "port-SENTINELLE";
  const erreur = refus(envMinimal({ [VARIABLES.port]: sentinelle }));
  assert.equal(erreur.code, "SETTING_INVALID");
  assert.equal(erreur.phrase, "mothra: refused (SETTING_INVALID) MOTHRA_PORT");
  assert.ok(!erreur.phrase.includes(sentinelle));
  assert.ok(!String(erreur.stack).includes(sentinelle));
});

test("a port above 65535 is SETTING_INVALID", () => {
  assert.equal(refus(envMinimal({ [VARIABLES.port]: "65536" })).code, "SETTING_INVALID");
  assert.equal(refus(envMinimal({ [VARIABLES.basePort]: "70000" })).code, "SETTING_INVALID");
});

test("a port is in strict decimal form, 1 to 65535: no zero, no leading zero, no sign, no space", () => {
  for (const mauvais of ["0", "05432", "00", "+80", "-1", " 80", "80 ", "8 0", "1e3", "0x50", "٣٠٠٠", "123456"]) {
    for (const variable of [VARIABLES.port, VARIABLES.basePort]) {
      const erreur = refus(envMinimal({ [variable]: mauvais }));
      assert.equal(erreur.code, "SETTING_INVALID", `${variable} ${JSON.stringify(mauvais)}`);
      assert.equal(erreur.variable, variable);
    }
    assert.equal(refus(envMinimal({ [VARIABLES.basePortJetable]: mauvais })).variable, VARIABLES.basePortJetable);
  }
  assert.equal(chargerConfiguration(envMinimal({ [VARIABLES.port]: "1" })).ecoute.port, 1);
  assert.equal(chargerConfiguration(envMinimal({ [VARIABLES.port]: "65535" })).ecoute.port, 65535);
  assert.equal(refus(envMinimal({ [VARIABLES.port]: "65536" })).code, "SETTING_INVALID");
});

test("the lab connection port is kept when set, null otherwise", () => {
  assert.equal(chargerConfiguration(envMinimal()).portLab, 5432);
  const env = envMinimal({ DBTEST_PORT: "55432" });
  delete env[VARIABLES.basePort];
  assert.equal(chargerConfiguration(env).portLab, null);
});

test("the threshold setting is a non-negative integer, or SETTING_INVALID", () => {
  assert.equal(chargerConfiguration(envMinimal({ [VARIABLES.seuil]: "8" })).seuil, 8);
  assert.equal(refus(envMinimal({ [VARIABLES.seuil]: "-1" })).code, "SETTING_INVALID");
  assert.equal(refus(envMinimal({ [VARIABLES.seuil]: "5.5" })).code, "SETTING_INVALID");
});

test("a missing database name is SETTING_MISSING naming the variable", () => {
  const env = envMinimal();
  delete env[VARIABLES.baseNom];
  const erreur = refus(env);
  assert.equal(erreur.code, "SETTING_MISSING");
  assert.equal(erreur.variable, "MOTHRA_DB_NAME");
});

test("a missing database port is SETTING_MISSING, unless the throwaway port is given", () => {
  const env = envMinimal();
  delete env[VARIABLES.basePort];
  assert.equal(refus(env).code, "SETTING_MISSING");
  assert.equal(chargerConfiguration({ ...env, DBTEST_PORT: "55432" }).base.port, 55432);
});

test("unknown variables are ignored, never echoed", () => {
  const config = chargerConfiguration(envMinimal({ MOTHRA_INCONNUE: "SENTINELLE" }));
  assert.ok(!JSON.stringify({ ...config, base: { ...config.base, motDePasse: undefined } }).includes("SENTINELLE"));
});

test("the first failing item stops: settings are checked before the secret", () => {
  const env = envMinimal({ [VARIABLES.port]: "x" });
  delete env[VARIABLES.secretBase];
  assert.equal(refus(env).code, "SETTING_INVALID");
});

test("the secret never appears when the configuration object is serialized", () => {
  const config = chargerConfiguration(envMinimal());
  assert.ok(!JSON.stringify(config).includes(SECRET_SENTINELLE));
  assert.ok(!JSON.stringify(config).includes(SECRET_STOCKAGE_SENTINELLE));
});

// Task 16.1 (design D17, ADR 0006): the second secret, the storage role's, and the second connection of the closed list.
test("the storage connection holds the storage role and its own secret, never the view role's", () => {
  const config = chargerConfiguration(envMinimal({ DBTEST_PORT: "55432" }));
  assert.equal(config.stockage.utilisateur, "pmzilla_mothra");
  assert.equal(config.stockage.motDePasse(), SECRET_STOCKAGE_SENTINELLE);
  assert.notEqual(config.stockage.motDePasse(), config.base.motDePasse());
  assert.equal(config.stockage.hote, config.base.hote);
  assert.equal(config.stockage.port, config.base.port);
  assert.equal(config.stockage.nom, config.base.nom);
  assert.equal(config.base.utilisateur, "pmzilla_mothra_views");
});

test("each secret has its own variable, and its own _FILE variable for hosting", () => {
  assert.equal(VARIABLES.secretBase, "PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS");
  assert.equal(VARIABLES.secretStockage, "PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA");
  assert.equal(VARIABLES.secretStockageFichier, "PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_FILE");
  assert.equal(new Set(Object.values(VARIABLES)).size, Object.values(VARIABLES).length);
});

test("the storage secret absent or empty is SECRET_MISSING naming its variable, not the view role's", () => {
  const env = envMinimal();
  delete env[VARIABLES.secretStockage];
  const erreur = refus(env);
  assert.equal(erreur.code, "SECRET_MISSING");
  assert.equal(erreur.sortie, 5);
  assert.equal(erreur.phrase, "mothra: refused (SECRET_MISSING) PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA");
  assert.equal(refus(envMinimal({ [VARIABLES.secretStockage]: "" })).variable, VARIABLES.secretStockage);
});

test("each secret missing names its own variable: the view role's first, then the storage role's", () => {
  const env = envMinimal();
  delete env[VARIABLES.secretBase];
  delete env[VARIABLES.secretStockage];
  assert.equal(refus(env).variable, VARIABLES.secretBase);
  const seul = envMinimal();
  delete seul[VARIABLES.secretStockage];
  assert.equal(refus(seul).variable, VARIABLES.secretStockage);
});

test("the storage secret comes from a mounted file named by its _FILE variable, and a missing file names that variable only", () => {
  const env = envMinimal({ [VARIABLES.secretStockageFichier]: "/run/secrets/stockage" });
  delete env[VARIABLES.secretStockage];
  const config = chargerConfiguration(env, (chemin) => {
    assert.equal(chemin, "/run/secrets/stockage");
    return `${SECRET_STOCKAGE_SENTINELLE}\n`;
  });
  assert.equal(config.stockage.motDePasse(), SECRET_STOCKAGE_SENTINELLE);
  assert.equal(config.base.motDePasse(), SECRET_SENTINELLE);
  const absent = refus(env, () => {
    throw new Error("ENOENT /run/secrets/stockage");
  });
  assert.equal(absent.code, "SECRET_MISSING");
  assert.equal(absent.variable, VARIABLES.secretStockageFichier);
  assert.ok(!absent.phrase.includes("/run/secrets"));
  assert.equal(refus(env, () => "\n").variable, VARIABLES.secretStockageFichier);
});

// Task 16.2 (design D17, D34): the dataset setting, mandatory, no default.
test("MOTHRA_DATASET synthetic or real is read", () => {
  assert.equal(chargerConfiguration(envMinimal({ MOTHRA_DATASET: "synthetic" })).jeu, "synthetic");
  assert.equal(chargerConfiguration(envMinimal({ MOTHRA_DATASET: "real" })).jeu, "real");
});

test("MOTHRA_DATASET missing or empty is SETTING_MISSING, exit 5, naming the variable only", () => {
  const env = envMinimal();
  delete env.MOTHRA_DATASET;
  for (const e of [env, { ...env, MOTHRA_DATASET: "" }]) {
    const erreur = refus(e);
    assert.equal(erreur.code, "SETTING_MISSING");
    assert.equal(erreur.sortie, 5);
    assert.equal(erreur.phrase, "mothra: refused (SETTING_MISSING) MOTHRA_DATASET");
  }
});

test("any other value, demo included, is SETTING_INVALID, exit 5, naming the variable and never the value", () => {
  for (const valeur of ["demo", "Synthetic", "REAL", "synthetic ", "real\n", "true", "1", "valeur-SENTINELLE"]) {
    const erreur = refus(envMinimal({ MOTHRA_DATASET: valeur }));
    assert.equal(erreur.code, "SETTING_INVALID", valeur);
    assert.equal(erreur.sortie, 5);
    assert.equal(erreur.phrase, "mothra: refused (SETTING_INVALID) MOTHRA_DATASET");
    assert.ok(!erreur.phrase.includes("SENTINELLE"));
  }
});

test("no refusal phrase holds either secret", () => {
  for (const extra of [{ [VARIABLES.port]: "x" }, { [VARIABLES.secretStockage]: "" }]) {
    const phrase = refus(envMinimal(extra)).phrase;
    assert.ok(!phrase.includes(SECRET_SENTINELLE) && !phrase.includes(SECRET_STOCKAGE_SENTINELLE));
  }
});
