// Creating the server emits no Fastify deprecation warning (FSTDEP...). Fastify emits each warning once per process: this file
// holds the one test, so the node:test runner (one process per file) sees any warning of the creation.
import assert from "node:assert/strict";
import { test } from "node:test";

import { construireServeur } from "../src/routes/serveur.ts";
import { AccesFictif, contrat } from "./aide.ts";

test("creating the server emits no Fastify deprecation warning", async () => {
  const avertissements: Array<{ name: string; code: string; message: string }> = [];
  const ecouteur = (avertissement: Error & { code?: string }) => {
    avertissements.push({ name: avertissement.name, code: avertissement.code ?? "", message: avertissement.message });
  };
  process.on("warning", ecouteur);
  try {
    const { app } = construireServeur({ contrat, acces: new AccesFictif([]), reglageSeuil: null, journal: false });
    await app.ready();
    // process.emitWarning delivers on a later tick: wait for it before looking.
    await new Promise((resolu) => setTimeout(resolu, 50));
    await app.close();
  } finally {
    process.off("warning", ecouteur);
  }
  const fastify = avertissements.filter((a) => a.code.startsWith("FSTDEP") || a.code.startsWith("FSTWRN") || a.name === "FastifyDeprecation");
  assert.deepEqual(fastify, []);
});
