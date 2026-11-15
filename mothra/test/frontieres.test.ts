// Task 2.7: static test of the package boundaries (ADR 0002, Q3): the front imports only the contract package,
// the contract imports no other Mothra package, the server never imports the front. Fake file sets first, then the real tree.
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import { collecterFichiers, importsDe, verifierFrontieres } from "./frontieres.ts";

const racine = fileURLToPath(new URL("..", import.meta.url));

test("the front may import the contract package, a third party and itself", () => {
  const ecarts = verifierFrontieres([
    { chemin: "front/src/a.ts", contenu: 'import { x } from "@mothra/contract";\nimport React from "react";\nimport "./b.ts";\n' },
    { chemin: "front/src/b.ts", contenu: 'export * from "../lib/c.ts";\n' },
  ]);
  assert.deepEqual(ecarts, []);
});

test("the front importing the server package fails naming the file and the target package", () => {
  const ecarts = verifierFrontieres([{ chemin: "front/src/a.ts", contenu: 'import { r } from "@mothra/server";\n' }]);
  assert.equal(ecarts.length, 1);
  assert.match(ecarts[0], /front\/src\/a\.ts/);
  assert.match(ecarts[0], /server/);
});

test("a relative import across a package boundary fails naming the file and the target package", () => {
  const ecarts = verifierFrontieres([
    { chemin: "front/src/vues/a.ts", contenu: 'import { r } from "../../../server/src/routes.ts";\n' },
    { chemin: "contract/src/b.ts", contenu: 'import { z } from "../../front/src/z.ts";\n' },
    { chemin: "server/src/c.ts", contenu: 'import { z } from "../../front/src/z.ts";\n' },
  ]);
  assert.equal(ecarts.length, 3);
  assert.match(ecarts[0], /front\/src\/vues\/a\.ts.*server/);
  assert.match(ecarts[1], /contract\/src\/b\.ts.*front/);
  assert.match(ecarts[2], /server\/src\/c\.ts.*front/);
});

test("the front importing the contract package by a relative path is also a crossing", () => {
  // The contract is reached by its package name only: a relative path would bypass the workspace link.
  const ecarts = verifierFrontieres([{ chemin: "front/src/a.ts", contenu: 'import { c } from "../../contract/src/index.ts";\n' }]);
  assert.equal(ecarts.length, 1);
  assert.match(ecarts[0], /front\/src\/a\.ts.*contract/);
});

test("the contract imports no other Mothra package", () => {
  const ecarts = verifierFrontieres([
    { chemin: "contract/src/a.ts", contenu: 'import a from "@mothra/server";\nimport b from "@mothra/front/sub";\n' },
  ]);
  assert.equal(ecarts.length, 2);
});

test("the server may import the contract package but never the front", () => {
  assert.deepEqual(verifierFrontieres([{ chemin: "server/src/a.ts", contenu: 'import { c } from "@mothra/contract";\n' }]), []);
  assert.equal(verifierFrontieres([{ chemin: "server/src/a.ts", contenu: 'import { f } from "@mothra/front";\n' }]).length, 1);
});

test("dynamic imports, requires and re-exports are read as imports; comments are not", () => {
  assert.deepEqual(
    importsDe('const a = await import("x");\nconst b = require("y");\nexport { z } from "w";\nimport "v";\n// import "no"\n/* import "nor" */\n'),
    ["x", "y", "w", "v"],
  );
});

test("a string holding a comment opener does not hide a forbidden import that follows", () => {
  const contenu = 'const a = "/*";\nimport { r } from "@mothra/server";\nconst b = "*/";\n';
  assert.deepEqual(importsDe(contenu), ["@mothra/server"]);
  assert.equal(verifierFrontieres([{ chemin: "front/src/a.ts", contenu }]).length, 1);
});

test("an import-like text inside a string is not an import, a specifier is still read", () => {
  assert.deepEqual(importsDe('const t = \'import "no"\';\nconst u = `from "no2"`;\nimport "yes";\n'), ["yes"]);
});

test("a path outside the three packages is not checked", () => {
  assert.deepEqual(verifierFrontieres([{ chemin: "test/a.ts", contenu: 'import "../server/src/a.ts";\n' }]), []);
});

test("the real tree respects the package boundaries", () => {
  const ecarts = verifierFrontieres(collecterFichiers(racine));
  assert.deepEqual(ecarts, []);
});
