// Task 8.8: the server serves the built bundle from its folder only, with the same security headers on every answer, no CORS, a named
// answer when the bundle is not built, and a response-schema exemption limited to the bundle routes. A fake bundle in a temporary folder,
// a sentinel file beside it (and one linked from inside it), a fake database access: no database, no network.
import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import Fastify from "fastify";

import { preparer } from "../src/demarrage.ts";
import { AVERTISSEMENT_BUNDLE_ABSENT, aUneExtension, codeIntrouvable, resoudreChemin } from "../src/routes/bundle.ts";
import { EN_TETES_SECURITE, ROUTES_WITHOUT_RESPONSE_SCHEMA, construireServeur, exigerSchemaDeReponse } from "../src/routes/serveur.ts";
import { AccesFictif, CHEMIN_CONTRAT, SENTINELLE, contrat, envMinimal, journalCapture, ligneStatut } from "./aide.ts";

const PAGE = "<!doctype html><title>faux bundle</title><div id=racine></div>";
const SCRIPT = "console.log('faux');";

interface FauxBundle {
  racine: string;
  dossier: string;
}

// <racine>/dist: index.html, assets/app.js, assets/app.css, assets/sous/x.js, lien.txt (symbolic link to the sentinel); <racine>/sentinelle.txt.
function fauxBundle(): FauxBundle {
  const racine = mkdtempSync(join(tmpdir(), "mothra-bundle-"));
  const dossier = join(racine, "dist");
  mkdirSync(join(dossier, "assets", "sous"), { recursive: true });
  writeFileSync(join(dossier, "index.html"), PAGE);
  writeFileSync(join(dossier, "assets", "app.js"), SCRIPT);
  writeFileSync(join(dossier, "assets", "app.css"), "body{}");
  writeFileSync(join(dossier, "assets", "sous", "x.js"), "");
  writeFileSync(join(racine, "sentinelle.txt"), SENTINELLE);
  symlinkSync(join(racine, "sentinelle.txt"), join(dossier, "lien.txt"));
  return { racine, dossier };
}

function absent(): string {
  return join(mkdtempSync(join(tmpdir(), "mothra-sans-bundle-")), "dist");
}

function serveur(dossierBundle: string, acces = new AccesFictif([ligneStatut("Team A", 12), ligneStatut("Team B", 2)])) {
  return { ...construireServeur({ contrat, acces, reglageSeuil: null, journal: false, dossierBundle }), acces };
}

async function demander(dossierBundle: string, url: string, entetes: Record<string, string> = {}, method: "GET" | "OPTIONS" = "GET") {
  const { app } = serveur(dossierBundle);
  const reponse = await app.inject({ method, url, headers: entetes });
  await app.close();
  return reponse;
}

// ---- the extension, one definition

test("the extension is a dot followed by at least one character in the last segment, query string excluded", () => {
  const avec = ["/app.js", "/assets/absent.js", "/absent.css", "/absent.png", "/absent.svg", "/.well-known", "/a/b.c?x=1", "/x/y.z.w"];
  const sans = ["/", "/sheets/12", "/home.", "/home.?x=a.b", "/a.b/c", "/sheets/12?file=a.js", "", "/assets/", "/s?f=a.b.c.js"];
  for (const chemin of avec) {
    assert.equal(aUneExtension(chemin), true, chemin);
  }
  for (const chemin of sans) {
    assert.equal(aUneExtension(chemin), false, chemin);
  }
});

test("the code of an unknown path: UNKNOWN_VIEW only in the name position of the view route", () => {
  assert.equal(codeIntrouvable("/api/views/x"), "UNKNOWN_VIEW");
  assert.equal(codeIntrouvable("/api/views/"), "UNKNOWN_VIEW");
  assert.equal(codeIntrouvable("/api/views/x?threshold=1"), "UNKNOWN_VIEW");
  for (const chemin of ["/api/unknown", "/api/views/x/y", "/api/views", "/api", "/", "/sheets/12", "/assets/absent.js"]) {
    assert.equal(codeIntrouvable(chemin), "NOT_FOUND", chemin);
  }
});

// ---- resolution, over the file system

test("the resolution follows the order: leaving the folder, folder, file, absent file with an extension, index", () => {
  const { dossier } = fauxBundle();
  assert.deepEqual(resoudreChemin(dossier, "/"), { genre: "index" });
  assert.deepEqual(resoudreChemin(dossier, "/index.html"), { genre: "fichier", relatif: "index.html" });
  assert.deepEqual(resoudreChemin(dossier, "/assets/app.js"), { genre: "fichier", relatif: "assets/app.js" });
  assert.deepEqual(resoudreChemin(dossier, "/assets/app.js?v=1"), { genre: "fichier", relatif: "assets/app.js" });
  assert.deepEqual(resoudreChemin(dossier, "/assets"), { genre: "absent" });
  assert.deepEqual(resoudreChemin(dossier, "/assets/"), { genre: "absent" });
  assert.deepEqual(resoudreChemin(dossier, "/assets/sous"), { genre: "absent" });
  assert.deepEqual(resoudreChemin(dossier, "/assets/absent.js"), { genre: "absent" });
  assert.deepEqual(resoudreChemin(dossier, "/.well-known"), { genre: "absent" });
  assert.deepEqual(resoudreChemin(dossier, "/sheets/12"), { genre: "index" });
  assert.deepEqual(resoudreChemin(dossier, "/home."), { genre: "index" });
  for (const chemin of ["/../sentinelle.txt", "/%2e%2e/sentinelle.txt", "/..%2fsentinelle.txt", "/assets/../../sentinelle.txt", "/lien.txt", "/a%00b"]) {
    assert.deepEqual(resoudreChemin(dossier, chemin), { genre: "absent" }, chemin);
  }
  assert.deepEqual(resoudreChemin(dossier, "/%zz"), { genre: "absent" });
});

test("an encoded question mark belongs to the name, not to a query string: the extension is judged on the whole decoded segment", () => {
  const { dossier } = fauxBundle();
  assert.deepEqual(resoudreChemin(dossier, "/a%3F.js"), { genre: "absent" });
  assert.deepEqual(resoudreChemin(dossier, "/assets/app%3F.js"), { genre: "absent" });
  assert.deepEqual(resoudreChemin(dossier, "/a%3Fb"), { genre: "index" });
  assert.deepEqual(resoudreChemin(dossier, "/assets/app.js?x=%3F.png"), { genre: "fichier", relatif: "assets/app.js" });
});

test("the server decides /api/ on the decoded path: an encoded prefix is never the page, a bad encoding is NOT_FOUND", async () => {
  const { dossier } = fauxBundle();
  for (const url of ["/%61pi/unknown", "/api%2Funknown"]) {
    const reponse = await demander(dossier, url);
    assert.ok(!reponse.body.includes("faux bundle"), url);
    assert.equal(reponse.statusCode, 404, url);
    assert.deepEqual(reponse.json(), { error: "NOT_FOUND" }, url);
  }
  const mauvais = await demander(dossier, "/%zz");
  assert.equal(mauvais.statusCode, 404);
  assert.deepEqual(mauvais.json(), { error: "NOT_FOUND" });
});

test("an encoded question mark in a file name answers 404 NOT_FOUND, never index.html", async () => {
  const { dossier } = fauxBundle();
  const reponse = await demander(dossier, "/a%3F.js");
  assert.equal(reponse.statusCode, 404);
  assert.deepEqual(reponse.json(), { error: "NOT_FOUND" });
});

test("a method other than GET on a view route answers NOT_FOUND, never UNKNOWN_VIEW", async () => {
  const { dossier } = fauxBundle();
  for (const method of ["POST", "PUT", "DELETE", "OPTIONS", "PATCH"] as const) {
    for (const url of ["/api/views/v_team_status", "/api/views/inconnue"]) {
      const { app } = serveur(dossier);
      const reponse = await app.inject({ method, url });
      await app.close();
      assert.equal(reponse.statusCode, 404, `${method} ${url}`);
      assert.deepEqual(reponse.json(), { error: "NOT_FOUND" }, `${method} ${url}`);
    }
  }
  const { app } = serveur(dossier);
  const tete = await app.inject({ method: "HEAD", url: "/api/views/v_team_status" });
  await app.close();
  assert.equal(tete.statusCode, 404);
  assert.equal(codeIntrouvable("/api/views/x", "POST"), "NOT_FOUND");
  assert.equal(codeIntrouvable("/api/views/x", "GET"), "UNKNOWN_VIEW");
});

// ---- serving (Q7 and the author's answer on the fallback)

test("/ answers the index.html of the bundle with status 200", async () => {
  const { dossier } = fauxBundle();
  const reponse = await demander(dossier, "/");
  assert.equal(reponse.statusCode, 200);
  assert.equal(reponse.body, PAGE);
  assert.match(String(reponse.headers["content-type"]), /text\/html/);
});

test("a file of the bundle answers that file", async () => {
  const { dossier } = fauxBundle();
  const js = await demander(dossier, "/assets/app.js");
  assert.equal(js.statusCode, 200);
  assert.equal(js.body, SCRIPT);
  assert.match(String(js.headers["content-type"]), /javascript/);
  const css = await demander(dossier, "/assets/app.css");
  assert.equal(css.statusCode, 200);
  assert.match(String(css.headers["content-type"]), /text\/css/);
});

test("a path outside /api/ without an extension answers index.html with status 200", async () => {
  const { dossier } = fauxBundle();
  for (const url of ["/sheets/12", "/home.", "/sheets/12?file=a.js", "/a/b/c/"]) {
    const reponse = await demander(dossier, url);
    assert.equal(reponse.statusCode, 200, url);
    assert.equal(reponse.body, PAGE, url);
  }
});

test("an absent file with an extension answers 404 NOT_FOUND, never index.html", async () => {
  const { dossier } = fauxBundle();
  for (const url of ["/assets/absent.js", "/absent.css", "/absent.png", "/absent.svg", "/.well-known"]) {
    const reponse = await demander(dossier, url);
    assert.equal(reponse.statusCode, 404, url);
    assert.deepEqual(reponse.json(), { error: "NOT_FOUND" }, url);
    assert.ok(!reponse.body.includes("faux bundle"), url);
  }
});

// ---- /api/

test("the view route with an unknown view name answers UNKNOWN_VIEW; any other unknown path under /api/ answers NOT_FOUND", async () => {
  const { dossier } = fauxBundle();
  const inconnue = await demander(dossier, "/api/views/inconnue");
  assert.equal(inconnue.statusCode, 404);
  assert.deepEqual(inconnue.json(), { error: "UNKNOWN_VIEW" });
  for (const url of ["/api/unknown", "/api/views/x/y", "/api/views", "/api/", "/api"]) {
    const reponse = await demander(dossier, url);
    assert.equal(reponse.statusCode, 404, url);
    assert.deepEqual(reponse.json(), { error: "NOT_FOUND" }, url);
    assert.ok(!reponse.body.includes("faux bundle"), url);
  }
});

test("the routes under /api/ stay those of the slice: the view still answers its cells", async () => {
  const { dossier } = fauxBundle();
  const reponse = await demander(dossier, "/api/views/v_team_status");
  assert.equal(reponse.statusCode, 200);
  assert.equal((reponse.json() as { view: string }).view, "v_team_status");
});

// ---- traversal and folders (Q6)

test("a path climbing out of the folder, plain or percent-encoded, answers 404 NOT_FOUND and never the sentinel", async () => {
  const { dossier } = fauxBundle();
  for (const url of [
    "/../sentinelle.txt",
    "/%2e%2e/sentinelle.txt",
    "/..%2fsentinelle.txt",
    "/%2e%2e%2fsentinelle.txt",
    "/assets/../../sentinelle.txt",
    "/assets/%2e%2e/%2e%2e/sentinelle.txt",
    "/assets/..%5c..%5csentinelle.txt",
    "//sentinelle.txt",
    "/lien.txt",
  ]) {
    const reponse = await demander(dossier, url);
    assert.ok(!reponse.body.includes(SENTINELLE), `sentinel served for ${url}`);
    assert.ok(reponse.statusCode === 404 || reponse.body === PAGE, `unexpected answer for ${url}`);
  }
  for (const url of ["/../sentinelle.txt", "/%2e%2e/sentinelle.txt", "/..%2fsentinelle.txt", "/assets/../../sentinelle.txt", "/lien.txt"]) {
    const reponse = await demander(dossier, url);
    assert.equal(reponse.statusCode, 404, url);
    assert.deepEqual(reponse.json(), { error: "NOT_FOUND" }, url);
  }
});

test("a folder of the bundle answers 404 NOT_FOUND and names none of its files", async () => {
  const { dossier } = fauxBundle();
  for (const url of ["/assets", "/assets/", "/assets/sous", "/assets/sous/"]) {
    const reponse = await demander(dossier, url);
    assert.equal(reponse.statusCode, 404, url);
    assert.deepEqual(reponse.json(), { error: "NOT_FOUND" }, url);
    for (const nom of ["app.js", "app.css", "sous", "x.js", "index.html"]) {
      assert.ok(!reponse.body.includes(nom), `${url} names ${nom}`);
    }
  }
});

// ---- headers (Q1) and no CORS (Q5)

const ATTENDUS = {
  "content-security-policy": "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'",
  "x-content-type-options": "nosniff",
  "referrer-policy": "no-referrer",
  "x-frame-options": "DENY",
};

test("the headers are the four of the decision, written once", () => {
  assert.deepEqual({ ...EN_TETES_SECURITE }, ATTENDUS);
});

test("a bundle file, index.html, a 404 answer and an API answer carry exactly the same four headers, and no HSTS", async () => {
  const { dossier } = fauxBundle();
  for (const url of ["/assets/app.js", "/", "/sheets/12", "/assets/absent.js", "/assets", "/api/views/v_team_status", "/api/views/inconnue", "/api/unknown"]) {
    const reponse = await demander(dossier, url);
    for (const [nom, valeur] of Object.entries(ATTENDUS)) {
      assert.equal(reponse.headers[nom], valeur, `${nom} on ${url}`);
    }
    assert.equal(reponse.headers["strict-transport-security"], undefined, url);
  }
});

test("the answers of the framework errors (bad encoding, over-long parameter) carry the same four headers", async () => {
  const { dossier } = fauxBundle();
  for (const url of ["/%zz", "/api/views/%zz", `/api/views/${"a".repeat(500)}`, `/${"b".repeat(500)}/%zz`]) {
    const reponse = await demander(dossier, url);
    assert.equal(reponse.statusCode, 404, url);
    for (const [nom, valeur] of Object.entries(ATTENDUS)) {
      assert.equal(reponse.headers[nom], valeur, `${nom} on ${url.slice(0, 20)}`);
    }
  }
});

test("the headers are also on the answer of an absent bundle", async () => {
  const reponse = await demander(absent(), "/");
  assert.equal(reponse.statusCode, 503);
  for (const [nom, valeur] of Object.entries(ATTENDUS)) {
    assert.equal(reponse.headers[nom], valeur, nom);
  }
});

test("a request and a preflight with a foreign Origin get no Access-Control-* header", async () => {
  const { dossier } = fauxBundle();
  const origine = { origin: "http://autre.invalid", "access-control-request-method": "GET" };
  for (const [method, url] of [
    ["GET", "/"],
    ["GET", "/assets/app.js"],
    ["GET", "/api/views/v_team_status"],
    ["OPTIONS", "/api/views/v_team_status"],
    ["OPTIONS", "/"],
  ] as const) {
    const reponse = await demander(dossier, url, origine, method);
    const cors = Object.keys(reponse.headers).filter((nom) => nom.startsWith("access-control-"));
    assert.deepEqual(cors, [], `${method} ${url}`);
  }
});

// ---- absent bundle (Q4)

test("without the bundle folder the server runs: / and a path without an extension answer 503 BUNDLE_MISSING, the API is unchanged", async () => {
  const dossier = absent();
  for (const url of ["/", "/sheets/12", "/home."]) {
    const reponse = await demander(dossier, url);
    assert.equal(reponse.statusCode, 503, url);
    assert.deepEqual(reponse.json(), { error: "BUNDLE_MISSING" }, url);
  }
  const fichier = await demander(dossier, "/assets/absent.js");
  assert.equal(fichier.statusCode, 404);
  assert.deepEqual(fichier.json(), { error: "NOT_FOUND" });
  const inconnue = await demander(dossier, "/api/views/inconnue");
  assert.equal(inconnue.statusCode, 404);
  assert.deepEqual(inconnue.json(), { error: "UNKNOWN_VIEW" });
  const vue = await demander(dossier, "/api/views/v_team_status");
  assert.equal(vue.statusCode, 200);
  const autre = await demander(dossier, "/api/unknown");
  assert.deepEqual(autre.json(), { error: "NOT_FOUND" });
});

test("a bundle folder without index.html answers BUNDLE_MISSING on its pages and still serves its files", async () => {
  const { dossier } = fauxBundle();
  const sans = join(mkdtempSync(join(tmpdir(), "mothra-vide-")), "dist");
  mkdirSync(sans, { recursive: true });
  const reponse = await demander(sans, "/");
  assert.equal(reponse.statusCode, 503);
  assert.deepEqual(reponse.json(), { error: "BUNDLE_MISSING" });
  assert.equal((await demander(dossier, "/")).statusCode, 200);
});

function demarrer(dossierBundle: string): string[] {
  const avertissements: string[] = [];
  const { app } = preparer(envMinimal(), {
    cheminContrat: CHEMIN_CONTRAT,
    creerAcces: () => new AccesFictif(),
    journal: false,
    dossierBundle,
    avertir: (message) => avertissements.push(message),
  });
  void app.close();
  return avertissements;
}

test("the start warns once, with the phrase and no path, when the bundle is not built, and keeps running", () => {
  const dossier = absent();
  const avertissements = demarrer(dossier);
  assert.deepEqual(avertissements, ["mothra: warning (BUNDLE_MISSING)"]);
  assert.equal(AVERTISSEMENT_BUNDLE_ABSENT, "mothra: warning (BUNDLE_MISSING)");
  assert.ok(!avertissements[0].includes(dossier));
});

test("the start prints no warning when the bundle is built", () => {
  const { dossier } = fauxBundle();
  assert.deepEqual(demarrer(dossier), []);
});

// ---- response schema (Q2)

test("the list of routes without a response schema holds the bundle routes only", () => {
  assert.deepEqual([...ROUTES_WITHOUT_RESPONSE_SCHEMA], ["GET /", "GET /*"]);
});

test("every route of the server is under /api/ with a response schema, or is a bundle route of the list", () => {
  const { routes } = serveur(fauxBundle().dossier);
  const horsListe = routes.filter((r) => !ROUTES_WITHOUT_RESPONSE_SCHEMA.includes(`${r.method} ${r.url}`));
  assert.ok(horsListe.length > 0);
  for (const route of horsListe) {
    assert.ok(route.url.startsWith("/api/"), `route outside /api/ without exemption: ${route.method} ${route.url}`);
  }
});

test("another route registered without a response schema fails, naming that route, even beside the bundle routes", async () => {
  // exposeHeadRoutes: false as in the server (the automatic HEAD twin of a route is not a route of the list).
  const app = Fastify({ logger: false, exposeHeadRoutes: false });
  exigerSchemaDeReponse(app);
  app.get("/", async () => ({}));
  app.get("/*", async () => ({}));
  await assert.rejects(async () => {
    app.get("/autre", async () => ({}));
    await app.ready();
  }, /route sans schéma de réponse : GET \/autre/);
});

test("a route outside the list cannot be dispensed by spelling: a prefix or a method of a listed route is not listed", async () => {
  for (const [method, url] of [
    ["POST", "/"],
    ["GET", "/autre/*"],
    ["GET", "/api/*"],
  ] as const) {
    const app = Fastify({ logger: false });
    exigerSchemaDeReponse(app);
    await assert.rejects(async () => {
      app.route({ method, url, handler: async () => ({}) });
      await app.ready();
    }, new RegExp(`${method} ${url.replace("*", "\\*")}`));
  }
});

// ---- logs (task 6.6 still holds with the bundle)

test("the log of a bundle request holds no path, no sentinel and no file name", async () => {
  const { dossier } = fauxBundle();
  const journal = journalCapture();
  const { app } = construireServeur({
    contrat,
    acces: new AccesFictif([ligneStatut("Team A", 12)]),
    reglageSeuil: null,
    journal: { level: "info", stream: journal.stream },
    dossierBundle: dossier,
  });
  for (const url of ["/", "/assets/app.js", "/assets/absent.js", `/${SENTINELLE}`, "/../sentinelle.txt", "/%zz", "/lien.txt"]) {
    await app.inject({ method: "GET", url });
  }
  await app.close();
  const texte = journal.texte();
  for (const interdit of [SENTINELLE, "app.js", "absent.js", "sentinelle.txt", "mothra-bundle-"]) {
    assert.ok(!texte.includes(interdit), `the log holds ${interdit.length} characters of a path`);
  }
});
