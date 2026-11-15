// Static checks over the server sources: only the configuration module reads the environment (task 6.8, mothra-server "Direct
// environment read"), and no module makes an outgoing network call (task 6.6, invariant 6). Pure functions over file contents first.
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

interface Source {
  chemin: string; // relative to server/src, "/" separators
  contenu: string;
}

const LECTURE_ENVIRONNEMENT = [
  /\bprocess\s*\.\s*env\b/,
  /\bprocess\s*\[\s*["'`]env["'`]\s*\]/,
  /\bimport\.meta\.env\b/,
  /\bloadEnvFile\b/,
  /\bgetBuiltinModule\b/,
  /\bfrom\s*["'](?:node:)?process["']/,
  /\brequire\s*\(\s*["'](?:node:)?process["']\s*\)/,
];

const APPEL_SORTANT = [
  /\bfetch\s*\(/,
  /\bXMLHttpRequest\b/,
  /\bWebSocket\b/,
  /\bEventSource\b/,
  /\bfrom\s*["'](?:node:)?(?:http|https|http2|net|tls|dgram|dns|dns\/promises|child_process|worker_threads|cluster)["']/,
  /\bimport\s*\(\s*["'](?:node:)?(?:http|https|http2|net|tls|dgram|dns|child_process)["']\s*\)/,
  /\brequire\s*\(\s*["'](?:node:)?(?:http|https|http2|net|tls|dgram|dns|child_process)["']\s*\)/,
  /["']https?:\/\//,
];

export function modulesLisantEnvironnement(sources: Source[]): string[] {
  return sources.filter((s) => s.chemin !== "config/index.ts" && LECTURE_ENVIRONNEMENT.some((m) => m.test(s.contenu))).map((s) => s.chemin);
}

export function modulesAppelantDehors(sources: Source[]): string[] {
  return sources.filter((s) => APPEL_SORTANT.some((m) => m.test(s.contenu))).map((s) => s.chemin);
}

function collecter(dossier: string, relatif = ""): Source[] {
  const sources: Source[] = [];
  for (const nom of readdirSync(dossier)) {
    const complet = `${dossier}/${nom}`;
    const rel = relatif === "" ? nom : `${relatif}/${nom}`;
    if (statSync(complet).isDirectory()) {
      sources.push(...collecter(complet, rel));
    } else if (/\.(?:ts|js|mjs)$/.test(nom)) {
      sources.push({ chemin: rel, contenu: readFileSync(complet, "utf8") });
    }
  }
  return sources;
}

const sourcesReelles = collecter(fileURLToPath(new URL("../src", import.meta.url)));

test("the detector names a module that reads the environment, and spares the configuration module", () => {
  const trouves = modulesLisantEnvironnement([
    { chemin: "config/index.ts", contenu: "export const e = process.env;" },
    { chemin: "a.ts", contenu: "const x = process.env.HOME;" },
    { chemin: "b.ts", contenu: 'const y = process["env"];' },
    { chemin: "c.ts", contenu: 'import { env } from "node:process";' },
    { chemin: "d.ts", contenu: "const z = process.argv;" },
  ]);
  assert.deepEqual(trouves, ["a.ts", "b.ts", "c.ts"]);
});

test("only the configuration module of the server reads the environment", () => {
  assert.ok(sourcesReelles.some((s) => s.chemin === "config/index.ts"));
  assert.deepEqual(modulesLisantEnvironnement(sourcesReelles), []);
});

test("the detector names a module that calls outside", () => {
  const trouves = modulesAppelantDehors([
    { chemin: "a.ts", contenu: 'const r = await fetch("x");' },
    { chemin: "b.ts", contenu: 'import http from "node:http";' },
    { chemin: "c.ts", contenu: 'const u = "https://example.invalid";' },
    { chemin: "d.ts", contenu: 'import pg from "pg";' },
  ]);
  assert.deepEqual(trouves, ["a.ts", "b.ts", "c.ts"]);
});

test("no module of the server makes an outgoing call (only the database driver reaches the network, locally)", () => {
  assert.deepEqual(modulesAppelantDehors(sourcesReelles), []);
});
