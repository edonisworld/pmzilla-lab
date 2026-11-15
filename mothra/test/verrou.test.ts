// Task 2.6: licence and registry check of the npm lock (design D16), from the lock alone: no network, no npm audit.
// Fake locks first, then the real lock when the author has created it.
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";

import { analyserVerrou, exceptionsDeLicence, licencesAcceptees, messageIgnorees, plateformesInstallees, verifierVerrou } from "./verrou.ts";

const ACCEPTEES = ["MIT", "ISC", "Apache-2.0", "BSD-3-Clause"];
const INTEGRITE = "sha512-AAAA";
const REGISTRE = "https://registry.npmjs.org";

function verrou(paquets: Record<string, Record<string, unknown>>): string {
  return JSON.stringify({ name: "mothra", lockfileVersion: 3, packages: { "": { name: "mothra" }, ...paquets } });
}

function bon(nom: string, extra: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    version: "1.0.0",
    resolved: `${REGISTRE}/${nom}/-/${nom.split("/").pop()}-1.0.0.tgz`,
    integrity: INTEGRITE,
    license: "MIT",
    ...extra,
  };
}

test("a lock of public, freely licensed packages passes, workspaces and links included", () => {
  const texte = verrou({
    "node_modules/a": bon("a"),
    "node_modules/@s/b": bon("@s/b", { license: "(MIT OR Apache-2.0)" }),
    "node_modules/a/node_modules/c": bon("c", { license: "BSD-3-Clause" }),
    "node_modules/@mothra/contract": { resolved: "contract", link: true },
    contract: { name: "@mothra/contract", version: "0.0.0" },
  });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES), []);
});

test("a link outside the three workspaces is refused as non public, a workspace link is accepted", () => {
  const refuse = verrou({ "node_modules/x": { resolved: "file:../x", link: true } });
  assert.deepEqual(verifierVerrou(refuse, ACCEPTEES), ["registre non public : x"]);
  const sans = verrou({ "node_modules/y": { link: true } });
  assert.deepEqual(verifierVerrou(sans, ACCEPTEES), ["registre non public : y"]);
  for (const espace of ["contract", "server", "front"]) {
    assert.deepEqual(verifierVerrou(verrou({ [`node_modules/@mothra/${espace}`]: { resolved: espace, link: true } }), ACCEPTEES), []);
  }
});

test("a package resolved from another address is a non-public registry", () => {
  const texte = verrou({ "node_modules/prive": bon("prive", { resolved: "https://npm.interne.example/prive/-/prive-1.0.0.tgz" }) });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES), ["registre non public : prive"]);
});

test("a registry address that only starts like the public one is refused", () => {
  const texte = verrou({ "node_modules/p": bon("p", { resolved: "https://registry.npmjs.org.evil.example/p/-/p-1.0.0.tgz" }) });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES), ["registre non public : p"]);
});

test("a git or file resolution is not the public registry", () => {
  const texte = verrou({ "node_modules/g": bon("g", { resolved: "git+ssh://git@example.invalid/g.git#abc" }) });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES), ["registre non public : g"]);
});

test("a package without a resolved address is refused as non public", () => {
  const sans = bon("n");
  delete sans.resolved;
  assert.deepEqual(verifierVerrou(verrou({ "node_modules/n": sans }), ACCEPTEES), ["registre non public : n"]);
});

test("a package without an integrity hash is named", () => {
  const sans = bon("n");
  delete sans.integrity;
  assert.deepEqual(verifierVerrou(verrou({ "node_modules/n": sans }), ACCEPTEES), ["intégrité absente : n"]);
});

test("a package without licence is named", () => {
  const sans = bon("n");
  delete sans.license;
  const vide = bon("v", { license: "" });
  assert.deepEqual(verifierVerrou(verrou({ "node_modules/n": sans, "node_modules/v": vide }), ACCEPTEES), [
    "licence absente : n",
    "licence absente : v",
  ]);
});

test("UNLICENSED, SEE LICENSE IN, a paid and an unknown licence are refused with the licence", () => {
  const texte = verrou({
    "node_modules/u": bon("u", { license: "UNLICENSED" }),
    "node_modules/s": bon("s", { license: "SEE LICENSE IN LICENSE.md" }),
    "node_modules/c": bon("c", { license: "Commercial" }),
    "node_modules/x": bon("x", { license: "Inconnue-1.0" }),
  });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES), [
    "licence refusée : u (UNLICENSED)",
    "licence refusée : s (SEE LICENSE IN LICENSE.md)",
    "licence refusée : c (Commercial)",
    "licence refusée : x (Inconnue-1.0)",
  ]);
});

test("an expression is accepted when it is made of accepted identifiers, refused otherwise", () => {
  const texte = verrou({
    "node_modules/ou": bon("ou", { license: "(MIT OR Commercial)" }),
    "node_modules/et": bon("et", { license: "(MIT AND Commercial)" }),
    "node_modules/ok": bon("ok", { license: "(ISC AND (MIT OR Apache-2.0))" }),
    "node_modules/minuscules": bon("minuscules", { license: "mit" }),
  });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES), [
    "licence refusée : et ((MIT AND Commercial))",
    "licence refusée : minuscules (mit)",
  ]);
});

test("the legacy object and array forms of the licence field are refused, never accepted by default", () => {
  const texte = verrou({
    "node_modules/o": bon("o", { license: { type: "MIT" } }),
    "node_modules/t": bon("t", { license: ["MIT"] }),
  });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES), [
    'licence refusée : o ({"type":"MIT"})',
    'licence refusée : t (["MIT"])',
  ]);
});

const RAISON = "dépendance de construction de Vite 8, non modifiée, copyleft limité aux fichiers, rien dans le CSS produit";
const EXCEPTIONS = ["lightningcss", "lightningcss-darwin-arm64", "lightningcss-linux-arm64-gnu"].map((paquet) => ({
  paquet,
  licence: "MPL-2.0",
  raison: RAISON,
}));

test("a package under MPL-2.0 passes only through a named exception: lightningcss and its two binaries pass", () => {
  const texte = verrou(Object.fromEntries(EXCEPTIONS.map((e) => [`node_modules/${e.paquet}`, bon(e.paquet, { license: "MPL-2.0" })])));
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES, EXCEPTIONS), []);
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES).length, 3);
});

const EXCEPTION_PRINCIPALE = EXCEPTIONS.filter((e) => e.paquet === "lightningcss");

test("a fictitious package under MPL-2.0 is refused with its licence, the exception being by package name only", () => {
  const texte = verrou({
    "node_modules/fictif": bon("fictif", { license: "MPL-2.0" }),
    "node_modules/lightningcss": bon("lightningcss", { license: "MPL-2.0" }),
    "node_modules/lightningcss-win32-x64-msvc": bon("lightningcss-win32-x64-msvc", { license: "MPL-2.0" }),
  });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES, EXCEPTION_PRINCIPALE), [
    "licence refusée : fictif (MPL-2.0)",
    "licence refusée : lightningcss-win32-x64-msvc (MPL-2.0)",
  ]);
});

test("an exception covers its own licence only, not another one", () => {
  const texte = verrou({ "node_modules/lightningcss": bon("lightningcss", { license: "Commercial" }) });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES, EXCEPTION_PRINCIPALE), ["licence refusée : lightningcss (Commercial)"]);
});

test("an exception whose package is no longer in the lock is reported", () => {
  const texte = verrou({ "node_modules/lightningcss": bon("lightningcss", { license: "MPL-2.0" }) });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES, EXCEPTIONS), [
    "exception sans paquet dans le verrou : lightningcss-darwin-arm64",
    "exception sans paquet dans le verrou : lightningcss-linux-arm64-gnu",
  ]);
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES, EXCEPTION_PRINCIPALE), []);
});

test("the real lock, when present, holds the three packages of the licence exceptions", (t) => {
  const chemin = new URL("../package-lock.json", import.meta.url);
  if (!existsSync(chemin)) {
    t.skip("verrou absent");
    return;
  }
  const texte = readFileSync(chemin, "utf8");
  for (const e of exceptionsDeLicence()) assert.ok(texte.includes(`node_modules/${e.paquet}"`), `paquet absent du verrou : ${e.paquet}`);
});

test("an exception without a reason is refused and grants nothing", () => {
  const sans = [{ paquet: "lightningcss", licence: "MPL-2.0", raison: " " }];
  const texte = verrou({ "node_modules/lightningcss": bon("lightningcss", { license: "MPL-2.0" }) });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES, sans), ["exception sans raison : lightningcss", "licence refusée : lightningcss (MPL-2.0)"]);
});

test("the exceptions are data: by package name, each with its licence and its reason, MPL-2.0 never in the general list", () => {
  assert.ok(!licencesAcceptees().includes("MPL-2.0"));
  const liste = exceptionsDeLicence();
  assert.deepEqual(liste.map((e) => e.paquet).sort(), ["lightningcss", "lightningcss-darwin-arm64", "lightningcss-linux-arm64-gnu"]);
  for (const e of liste) {
    assert.equal(e.licence, "MPL-2.0");
    assert.ok(e.raison.trim() !== "");
  }
});

const PLATEFORMES = [
  { os: "darwin", cpu: "arm64" },
  { os: "linux", cpu: "arm64" },
];
const MPL = { license: "MPL-2.0" };

test("an optional entry marked for another platform only is ignored, and counted with its platforms", () => {
  const texte = verrou({
    "node_modules/bin-x64": bon("bin-x64", { ...MPL, optional: true, os: ["linux"], cpu: ["x64"] }),
    "node_modules/bin-win": bon("bin-win", { ...MPL, optional: true, os: ["win32"], cpu: ["x64"] }),
    "node_modules/bin-win2": bon("bin-win2", { ...MPL, optional: true, os: ["win32"], cpu: ["x64"] }),
  });
  const resultat = analyserVerrou(texte, ACCEPTEES, [], PLATEFORMES);
  assert.deepEqual(resultat.ecarts, []);
  assert.equal(resultat.ignorees.length, 3);
  assert.equal(messageIgnorees(resultat.ignorees), "entrées optionnelles d'autres plateformes ignorées : 3 (linux-x64, win32-x64)");
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES, [], PLATEFORMES), []);
});

test("the message of ignored entries names no licence, no package and no path, and is empty when nothing is ignored", () => {
  const texte = verrou({ "node_modules/binaire": bon("binaire", { ...MPL, optional: true, os: ["linux"], cpu: ["x64"] }) });
  const message = messageIgnorees(analyserVerrou(texte, ACCEPTEES, [], PLATEFORMES).ignorees);
  assert.doesNotMatch(message, /MPL|node_modules|binaire/);
  assert.equal(messageIgnorees([]), "");
});

test("an optional entry without os and cpu is still checked", () => {
  const texte = verrou({ "node_modules/opt": bon("opt", { ...MPL, optional: true }) });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES, [], PLATEFORMES), ["licence refusée : opt (MPL-2.0)"]);
  assert.equal(analyserVerrou(texte, ACCEPTEES, [], PLATEFORMES).ignorees.length, 0);
});

test("a mandatory entry of another platform is still checked", () => {
  const texte = verrou({
    "node_modules/obl": bon("obl", { ...MPL, os: ["linux"], cpu: ["x64"] }),
    "node_modules/faux": bon("faux", { ...MPL, optional: false, os: ["linux"], cpu: ["x64"] }),
  });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES, [], PLATEFORMES), ["licence refusée : obl (MPL-2.0)", "licence refusée : faux (MPL-2.0)"]);
});

test("an optional entry of a listed platform is still checked", () => {
  const texte = verrou({
    "node_modules/mac": bon("mac", { ...MPL, optional: true, os: ["darwin"], cpu: ["arm64"] }),
    "node_modules/ci": bon("ci", { ...MPL, optional: true, os: ["linux"], cpu: ["arm64"] }),
    "node_modules/os-seul": bon("os-seul", { ...MPL, optional: true, os: ["darwin"] }),
  });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES, [], PLATEFORMES), [
    "licence refusée : mac (MPL-2.0)",
    "licence refusée : ci (MPL-2.0)",
    "licence refusée : os-seul (MPL-2.0)",
  ]);
  assert.equal(analyserVerrou(texte, ACCEPTEES, [], PLATEFORMES).ignorees.length, 0);
});

test("without a list of installed platforms nothing is ignored", () => {
  const texte = verrou({ "node_modules/bin": bon("bin", { ...MPL, optional: true, os: ["linux"], cpu: ["x64"] }) });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES), ["licence refusée : bin (MPL-2.0)"]);
});

test("the installed platforms are data: the Mac and the CI image, in their own file", () => {
  assert.deepEqual(plateformesInstallees(), [
    { os: "darwin", cpu: "arm64" },
    { os: "linux", cpu: "arm64", libc: "glibc" },
  ]);
});

const PLATEFORMES_LIBC = [
  { os: "darwin", cpu: "arm64" },
  { os: "linux", cpu: "arm64", libc: "glibc" },
];

test("an optional entry of a libc absent from the platform of the same os and cpu is ignored, and counted with its libc", () => {
  const texte = verrou({
    "node_modules/bin-musl": bon("bin-musl", { ...MPL, optional: true, os: ["linux"], cpu: ["arm64"], libc: ["musl"] }),
  });
  const resultat = analyserVerrou(texte, ACCEPTEES, [], PLATEFORMES_LIBC);
  assert.deepEqual(resultat.ecarts, []);
  assert.deepEqual(resultat.ignorees, ["linux-arm64-musl"]);
  assert.doesNotMatch(messageIgnorees(resultat.ignorees), /MPL|node_modules|bin-musl/);
});

test("an optional entry of the same os and cpu is checked when no platform of that os and cpu carries a libc", () => {
  const texte = verrou({
    "node_modules/bin-musl": bon("bin-musl", { ...MPL, optional: true, os: ["linux"], cpu: ["arm64"], libc: ["musl"] }),
  });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES, [], PLATEFORMES), ["licence refusée : bin-musl (MPL-2.0)"]);
  assert.equal(analyserVerrou(texte, ACCEPTEES, [], PLATEFORMES).ignorees.length, 0);
});

test("a mandatory entry of another libc is still checked", () => {
  const texte = verrou({ "node_modules/obl-musl": bon("obl-musl", { ...MPL, os: ["linux"], cpu: ["arm64"], libc: ["musl"] }) });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES, [], PLATEFORMES_LIBC), ["licence refusée : obl-musl (MPL-2.0)"]);
});

test("an optional entry of the right libc is still checked", () => {
  const texte = verrou({ "node_modules/bin-gnu": bon("bin-gnu", { ...MPL, optional: true, os: ["linux"], cpu: ["arm64"], libc: ["glibc"] }) });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES, [], PLATEFORMES_LIBC), ["licence refusée : bin-gnu (MPL-2.0)"]);
  assert.equal(analyserVerrou(texte, ACCEPTEES, [], PLATEFORMES_LIBC).ignorees.length, 0);
});

test("an optional entry without a libc field is still checked", () => {
  const texte = verrou({ "node_modules/bin-sans": bon("bin-sans", { ...MPL, optional: true, os: ["linux"], cpu: ["arm64"] }) });
  assert.deepEqual(verifierVerrou(texte, ACCEPTEES, [], PLATEFORMES_LIBC), ["licence refusée : bin-sans (MPL-2.0)"]);
  assert.equal(analyserVerrou(texte, ACCEPTEES, [], PLATEFORMES_LIBC).ignorees.length, 0);
});

test("the musl binary of lightningcss is ignored with the real platforms, not refused, while the gnu one passes by its exception", () => {
  const texte = verrou({
    "node_modules/lightningcss-linux-arm64-musl": bon("lightningcss-linux-arm64-musl", { ...MPL, optional: true, os: ["linux"], cpu: ["arm64"], libc: ["musl"] }),
    "node_modules/lightningcss-linux-arm64-gnu": bon("lightningcss-linux-arm64-gnu", { ...MPL, optional: true, os: ["linux"], cpu: ["arm64"], libc: ["glibc"] }),
  });
  const resultat = analyserVerrou(texte, ACCEPTEES, EXCEPTIONS.filter((e) => e.paquet === "lightningcss-linux-arm64-gnu"), plateformesInstallees());
  assert.deepEqual(resultat.ecarts, []);
  assert.deepEqual(resultat.ignorees, ["linux-arm64-musl"]);
});

test("an optional entry of another platform is still refused when resolved from a private registry, a link or without integrity", () => {
  const autre = { ...MPL, optional: true, os: ["win32"], cpu: ["x64"] };
  const texte = verrou({
    "node_modules/prive": bon("prive", { ...autre, resolved: "https://npm.interne.example/prive/-/prive-1.0.0.tgz" }),
    "node_modules/sans-integrite": (() => {
      const e = bon("sans-integrite", autre);
      delete e.integrity;
      return e;
    })(),
    "node_modules/lien": { optional: true, os: ["win32"], cpu: ["x64"], link: true, resolved: "file:../lien" },
    "node_modules/propre": bon("propre", autre),
  });
  const resultat = analyserVerrou(texte, ACCEPTEES, [], PLATEFORMES);
  assert.deepEqual(resultat.ecarts, ["registre non public : prive", "intégrité absente : sans-integrite", "registre non public : lien"]);
  assert.equal(resultat.ignorees.length, 1);
});

test("an unreadable lock is a named failure", () => {
  assert.deepEqual(verifierVerrou("{pas du json", ACCEPTEES), ["verrou npm illisible"]);
  assert.deepEqual(verifierVerrou(JSON.stringify({ lockfileVersion: 3 }), ACCEPTEES), ["verrou npm illisible"]);
});

test("the accepted list is data, closed, and holds no paid or unlicensed identifier", () => {
  const liste = licencesAcceptees();
  assert.ok(liste.length > 0);
  for (const refusee of ["UNLICENSED", "Commercial", "Proprietary"]) assert.ok(!liste.includes(refusee));
  assert.equal(new Set(liste).size, liste.length);
});

test("the static-file plugin is checked like any entry, and so is a package it brings in (task 8.8, Q3)", () => {
  const bonne = verrou({
    "node_modules/@fastify/static": bon("@fastify/static"),
    "node_modules/@fastify/static/node_modules/dependance": bon("dependance"),
  });
  assert.deepEqual(verifierVerrou(bonne, ACCEPTEES), []);
  const refusee = verrou({
    "node_modules/@fastify/static": bon("@fastify/static"),
    "node_modules/dependance-de-static": bon("dependance-de-static", { license: "Commercial" }),
  });
  const ecarts = verifierVerrou(refusee, ACCEPTEES);
  assert.deepEqual(ecarts, ["licence refusée : dependance-de-static (Commercial)"]);
  assert.ok(ecarts[0].startsWith("licence refusée :"));
  const plugin = verrou({ "node_modules/@fastify/static": bon("@fastify/static", { license: "UNLICENSED" }) });
  assert.deepEqual(verifierVerrou(plugin, ACCEPTEES), ["licence refusée : @fastify/static (UNLICENSED)"]);
});

test("the real lock, once the author has created it, holds only public, freely licensed packages", (t) => {
  const chemin = new URL("../package-lock.json", import.meta.url);
  if (!existsSync(chemin)) {
    t.skip("verrou absent : le verrou est créé par npm install de l'auteur (tâche 10.1)");
    return;
  }
  const resultat = analyserVerrou(readFileSync(chemin, "utf8"), licencesAcceptees(), exceptionsDeLicence(), plateformesInstallees());
  if (resultat.ignorees.length > 0) t.diagnostic(messageIgnorees(resultat.ignorees));
  assert.deepEqual(resultat.ecarts, []);
});
