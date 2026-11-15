// Task 7.5: the permanent "no real data" test on the bundle (invariants 4, 6 and 7, spec mothra-front "The bundle holds no data and
// calls nothing outside"). The checker is tried on synthetic bundles; then the real production bundle is built by vite into a
// temporary folder (never into the tracked tree) and checked. The build needs the dependencies installed by the author's npm install.
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";
import { after, before, test } from "node:test";
import { build } from "vite";

import { controlerBundle, POLICES_ADMISES } from "./empaquetage.ts";
import type { FichierBundle } from "./empaquetage.ts";
import { fichiers, sources } from "./statique.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const RACINE_DEPOT = new URL("../../../", import.meta.url).pathname;
const HTML_PROPRE = '<!doctype html><html><head><script type="module" src="/assets/index.js"></script></head><body><div id="racine"></div></body></html>';

function bundle(...autres: FichierBundle[]): FichierBundle[] {
  return [{ nom: "index.html", contenu: HTML_PROPRE }, { nom: "assets/index.js", contenu: "const a=1;" }, ...autres];
}

test("a clean bundle passes", () => {
  assert.deepEqual(controlerBundle(bundle()), []);
});

test("a sentinel string of the synthetic dataset fails the check and names the file", () => {
  for (const sentinelle of ["SENTINELLE-PROJET", "SENTINELLE-RESOLUTION", "SENTINELLE-PARENT", "SENTINELLE-AUTRE"]) {
    const trouves = controlerBundle(bundle({ nom: "assets/data.js", contenu: `x="${sentinelle}"` }));
    assert.deepEqual(trouves, ["assets/data.js : chaîne sentinelle du jeu synthétique"]);
  }
});

test("an absolute address fails the check, names the file and does not print the address", () => {
  const trouves = controlerBundle(bundle({ nom: "assets/dep.js", contenu: 'fetch("https://remote.example/api")' }));
  assert.equal(trouves.length, 1);
  assert.match(trouves[0], /^assets\/dep\.js : adresse absolue hors liste/);
  assert.doesNotMatch(trouves[0], /remote|example/);
});

test("the identifiers and documentation links of the libraries are admitted, a CDN is not", () => {
  const admis = 'a="http://www.w3.org/2000/svg";b="https://react.dev/errors/"';
  assert.deepEqual(controlerBundle(bundle({ nom: "assets/lib.js", contenu: admis })), []);
  const cdn = controlerBundle(bundle({ nom: "assets/lib.js", contenu: 'a="https://cdn.jsdelivr.net/npm/x"' }));
  assert.equal(cdn.length, 1);
  assert.match(cdn[0], /adresse absolue hors liste/);
  assert.match(controlerBundle([{ nom: "index.html", contenu: '<link href="https://fonts.googleapis.com/css" rel="stylesheet">' }]).join("\n"), /adresse de CDN/);
  assert.match(controlerBundle([{ nom: "style.css", contenu: "@import url(//fonts.gstatic.com/x.css);" }]).join("\n"), /adresse sans protocole|adresse de CDN/);
});

test("the react-intl documentation host is admitted, another github.io subdomain is not", () => {
  const intl = controlerBundle(bundle({ nom: "assets/lib.js", contenu: 'a="https://formatjs.github.io/docs/react-intl"' }));
  assert.deepEqual(intl, []);
  const autre = controlerBundle(bundle({ nom: "assets/lib.js", contenu: 'a="https://example.github.io/x"' }));
  assert.equal(autre.length, 1);
  assert.match(autre[0], /adresse absolue hors liste/);
});

test("the base address of TypeBox's uri check is admitted by exact host, a subdomain of example.com is not", () => {
  const base = "URL.canParse(e,`http://example.com`)";
  assert.deepEqual(controlerBundle(bundle({ nom: "assets/lib.js", contenu: base })), []);
  const autre = controlerBundle(bundle({ nom: "assets/lib.js", contenu: 'a="https://api.example.com/x"' }));
  assert.equal(autre.length, 1);
  assert.match(autre[0], /adresse absolue hors liste/);
});

const SVG_C2PA =
  '<svg xmlns="http://www.w3.org/2000/svg"><metadata><c2pa:manifest xmlns:c2pa="http://c2pa.org/manifest">AAAA</c2pa:manifest></metadata></svg>';

test("a .svg file is admitted only under logos/ of the bundle, anywhere else it fails", () => {
  assert.deepEqual(controlerBundle(bundle({ nom: "logos/a.svg", contenu: SVG_C2PA })), []);
  assert.match(controlerBundle(bundle({ nom: "assets/a.svg", contenu: SVG_C2PA })).join("\n"), /assets\/a\.svg : type de fichier non admis/);
  assert.match(controlerBundle(bundle({ nom: "a.svg", contenu: "<svg/>" })).join("\n"), /a\.svg : type de fichier non admis/);
  assert.match(controlerBundle(bundle({ nom: "logos/a.png", contenu: "x" })).join("\n"), /type de fichier non admis/);
});

test("the c2pa.org host is admitted only as the value of an XML namespace attribute of a .svg under logos/", () => {
  const hors = (nom: string, contenu: string) => controlerBundle(bundle({ nom, contenu })).join("\n");
  for (const contenu of [
    '<svg><image href="http://c2pa.org/manifest"/></svg>',
    '<svg><image src="http://c2pa.org/manifest"/></svg>',
    '<svg><rect style="fill:url(http://c2pa.org/manifest)"/></svg>',
    "<svg><text>http://c2pa.org/manifest</text></svg>",
    '<svg><a xlink:href="http://c2pa.org/manifest">x</a></svg>',
    '<svg><a data-x="xmlns:c2pa=http://c2pa.org/manifest">x</a></svg>',
  ]) {
    assert.match(hors("logos/a.svg", contenu), /logos\/a\.svg : adresse absolue hors liste \(1\)/, contenu);
  }
  assert.match(hors("assets/lib.js", 'a="http://c2pa.org/manifest"'), /adresse absolue hors liste/);
  assert.match(hors("assets/lib.js", 'a=\'xmlns:c2pa="http://c2pa.org/manifest"\''), /adresse absolue hors liste/);
  assert.match(hors("assets/s.css", "a { background: url(http://c2pa.org/manifest); }"), /adresse absolue hors liste/);
  assert.match(hors("index.html", '<a href="http://c2pa.org/manifest">x</a>'), /adresse absolue hors liste/);
  assert.doesNotMatch(hors("logos/a.svg", SVG_C2PA), /adresse/);
  assert.match(hors("logos/a.svg", SVG_C2PA.replace("c2pa.org", "autre.example")), /adresse absolue hors liste \(1\)/);
});

// Task 3.2 (design D10, authorised by R-20261031-74): the only font files admitted are those of IBM Plex Sans and IBM Plex Serif, by a
// closed list of file names (family, weight, normal style, latin subset) under assets/, never by a general extension.
test("the Plex font files of the closed list are admitted under assets/, in both formats", () => {
  const admis = [
    ...[400, 500, 600, 700].map((p) => `ibm-plex-sans-latin-${p}-normal`),
    ...[500, 600].map((p) => `ibm-plex-serif-latin-${p}-normal`),
  ];
  assert.deepEqual([...POLICES_ADMISES].sort(), [...admis].sort());
  for (const base of admis) {
    for (const extension of ["woff2", "woff"]) {
      assert.deepEqual(controlerBundle(bundle({ nom: `assets/${base}-AbCd1234.${extension}`, contenu: "wOF2" })), [], `${base}.${extension}`);
    }
  }
});

test("any other font file still fails with the existing message: another family, weight, style, format or place", () => {
  const refuses = [
    "assets/roboto-latin-400-normal-AbCd1234.woff2",
    "assets/ibm-plex-mono-latin-400-normal-AbCd1234.woff2",
    "assets/ibm-plex-sans-latin-300-normal-AbCd1234.woff2",
    "assets/ibm-plex-serif-latin-700-normal-AbCd1234.woff2",
    "assets/ibm-plex-sans-latin-400-italic-AbCd1234.woff2",
    "assets/ibm-plex-sans-latin-ext-400-normal-AbCd1234.woff2",
    "assets/ibm-plex-sans-latin-400-normal-AbCd1234.ttf",
    "assets/ibm-plex-sans-latin-400-normal-AbCd1234.otf",
    "assets/ibm-plex-sans-latin-400-normal-AbCd1234.woff2.map",
    "assets/other.woff2",
    "ibm-plex-sans-latin-400-normal-AbCd1234.woff2",
    "logos/ibm-plex-sans-latin-400-normal-AbCd1234.woff2",
  ];
  for (const nom of refuses) {
    assert.deepEqual(controlerBundle(bundle({ nom, contenu: "wOF2" })), [`${nom} : type de fichier non admis (donnée embarquée possible)`], nom);
  }
});

test("a Plex font file is scanned like any file: a sentinel or an absolute address in it fails", () => {
  const nom = "assets/ibm-plex-sans-latin-400-normal-AbCd1234.woff2";
  assert.deepEqual(controlerBundle(bundle({ nom, contenu: "x SENTINELLE-PROJET" })), [`${nom} : chaîne sentinelle du jeu synthétique`]);
  assert.match(controlerBundle(bundle({ nom, contenu: "https://remote.example/f" })).join("\n"), /adresse absolue hors liste/);
});

test("a style sheet that loads a font from another host fails", () => {
  const css = "@font-face { font-family: 'IBM Plex Sans'; src: url(https://fonts.example.org/f.woff2); }";
  assert.match(controlerBundle(bundle({ nom: "assets/index.css", contenu: css })).join("\n"), /adresse absolue hors liste/);
});

test("an address without a protocol fails the check", () => {
  const trouves = controlerBundle(bundle({ nom: "assets/dep.js", contenu: 'import("//evil.example/x.js")' }));
  assert.deepEqual(trouves, ["assets/dep.js : adresse sans protocole"]);
});

test("an API of external calls other than the local fetch fails the check", () => {
  for (const api of ["XMLHttpRequest", "WebSocket", "EventSource", "sendBeacon", "importScripts"]) {
    const trouves = controlerBundle(bundle({ nom: "assets/dep.js", contenu: `new ${api}(u)` }));
    assert.deepEqual(trouves, [`assets/dep.js : appel externe possible (${api})`]);
  }
});

test("embedded data fails the check: a data file, an inline script, an inline JSON, embedded rows", () => {
  assert.match(controlerBundle(bundle({ nom: "assets/vues.json", contenu: "{}" })).join("\n"), /type de fichier non admis/);
  assert.match(controlerBundle([{ nom: "index.html", contenu: "<script>window.donnees=1</script>" }]).join("\n"), /script en ligne/);
  assert.match(controlerBundle([{ nom: "index.html", contenu: '<script type="application/json">{"a":1}</script>' }]).join("\n"), /donnée en ligne/);
  assert.match(controlerBundle(bundle({ nom: "assets/d.js", contenu: 'x={rows:[{team:"A"}]}' })).join("\n"), /lignes de vue embarquées/);
  assert.match(controlerBundle(bundle({ nom: "assets/d.js", contenu: 'x="data:application/json;base64,e30="' })).join("\n"), /donnée en ligne/);
});

test("no source of the front holds an absolute address, so that every request goes to the local server", () => {
  const trouves = [...sources(FRONT, "src", [".ts", ".tsx", ".css"]), { nom: "index.html", contenu: readFileSync(`${FRONT}index.html`, "utf8") }]
    .filter((s) => /\b(?:https?|wss?|ftp):\/\/|["'`(]\/\/[a-z0-9-]+\./i.test(s.contenu))
    .map((s) => s.nom);
  assert.deepEqual(trouves, []);
});

test("the front takes runtime values of the contract only through its browser-safe subpath, never the package entry", () => {
  // The package entry re-exports the loaders, which import node:fs and node:util; vite would externalize them in the bundle.
  const trouves = sources(FRONT, "src", [".ts", ".tsx"])
    .filter((s) => /^import\s+(?!type\b)[^;]*from\s+["']@mothra\/contract["']/m.test(s.contenu))
    .map((s) => s.nom);
  assert.deepEqual(trouves, []);
});

test("the bundle folder is ignored by Git, so the bundle is never tracked", () => {
  const lignes = readFileSync(`${RACINE_DEPOT}.gitignore`, "utf8").split("\n").map((l) => l.trim());
  assert.ok(lignes.includes("/mothra/front/dist/"), "dossier du bundle absent du .gitignore");
});

let sortie = "";
let produits: FichierBundle[] = [];

before(async () => {
  sortie = mkdtempSync(join(tmpdir(), "mothra-bundle-"));
  await build({
    root: FRONT,
    configFile: join(FRONT, "vite.config.ts"),
    logLevel: "silent",
    build: { outDir: sortie, emptyOutDir: true },
  });
  produits = fichiers(sortie, [""]).map((chemin) => ({
    nom: relative(sortie, chemin).split("\\").join("/"),
    contenu: readFileSync(chemin, "utf8"),
  }));
});

after(() => {
  if (sortie !== "") rmSync(sortie, { recursive: true, force: true });
});

test("the production bundle is built, holds the page and its script", () => {
  assert.ok(produits.some((f) => f.nom === "index.html"));
  assert.ok(produits.some((f) => f.nom.endsWith(".js")));
});

test("the production bundle holds no sentinel, no embedded data, no CDN address and no external call", () => {
  assert.deepEqual(controlerBundle(produits), []);
});

test("the production bundle holds the Plex font files of the closed list, in both formats, and no other font file", () => {
  const polices = produits.map((f) => f.nom).filter((n) => /\.(?:woff2?|ttf|otf|eot)$/.test(n));
  assert.equal(polices.length, POLICES_ADMISES.length * 2);
  for (const base of POLICES_ADMISES) {
    for (const extension of ["woff2", "woff"]) {
      assert.ok(polices.some((n) => new RegExp(`^assets/${base}-[A-Za-z0-9_-]{8}\\.${extension}$`).test(n)), `${base}.${extension} absent`);
    }
  }
});

// Task 5.5 (mothra-demo-habillage D17): the catalogue of the components lives in scripts/, which the bundle never reads; the marks below are
// texts and class names that only the catalogue page writes. Replaces: nothing. Removal: falls with the catalogue script.
test("the production bundle holds no catalogue marker", () => {
  const marqueurs = ["Mothra component catalogue", "catalogue-section", "specimen-corps", "Colour swatches", "npm run catalogue", "sw-puce"];
  const trouves = produits.flatMap((f) => marqueurs.filter((m) => f.contenu.includes(m)).map((m) => `${f.nom} : marqueur du catalogue (${m})`));
  assert.deepEqual(trouves, []);
  assert.ok(produits.length > 0);
});

test("the production style sheets name the two Plex families and hold no address of another host", () => {
  const css = produits.filter((f) => f.nom.endsWith(".css")).map((f) => f.contenu).join("\n");
  assert.match(css, /font-family:\s*["']?IBM Plex Sans["']?/);
  assert.match(css, /font-family:\s*["']?IBM Plex Serif["']?/);
  assert.doesNotMatch(css, /https?:\/\//);
});
