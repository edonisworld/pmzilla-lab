// Audit #629, A-66 (R-20261112-30, D29): a draft whose data date left the current quarter comes without a body, with `bodyState`
// DATA_DATE_STALE. The front shows its catalogue message, in both languages, and no body, no verdict, no chart. Server rendering without a browser
// (as audit629-l5.test.ts); the request is answered by a double, the cache holds the refusal. Invented values only.
import assert from "node:assert/strict";
import { test } from "node:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement as h } from "react";

import { optionsFiche } from "../src/api/ficheLecture.ts";
import type { LecteurFiche } from "../src/api/ficheLecture.ts";
import { lireFicheHttp } from "../src/api/http.ts";
import { optionsPanneau, RefusPanneau } from "../src/api/panneaux.ts";
import { SectionPanneaux, panneauxAffiches } from "../src/composants/PanneauxProduit.ts";
import { ErreurApi } from "../src/api/vue.ts";
import { catalogues } from "../src/i18n/langue.ts";
import type { Langue } from "../src/i18n/langue.ts";
import { PageConviction } from "../src/pages/PageConviction.ts";
import { PageFiche } from "../src/pages/PageFiche.ts";
import { rendre } from "./rendu.ts";

const PERIMEE = { id: "7", state: "draft", managementQuestion: "predictability", effect: { text: "E.", lang: "en" }, cause: { text: "C.", lang: "en" }, bodyState: "DATA_DATE_STALE" };

function propre(html: string): string {
  return html.replaceAll("&#x27;", "'");
}

const TEXTES_FICHE: Record<Langue, string> = {
  en: "The data date is no longer in the current quarter: create a new sheet.",
  fr: "La date des données n'est plus dans le trimestre en cours : créez une nouvelle fiche.",
};
const TEXTES_PANNEAU: Record<Langue, string> = {
  en: "The quarter has just changed: reload the page.",
  fr: "Le trimestre vient de changer : rechargez la page.",
};

test("one code, two texts (R-20261112-34): the sheet text on a sheet, the reload text on a panel, in both languages", () => {
  for (const langue of ["en", "fr"] as Langue[]) {
    assert.equal(propre(catalogues[langue]["error.DATA_DATE_STALE"]), propre(TEXTES_FICHE[langue]), `sheet text ${langue}`);
    assert.equal(propre(catalogues[langue]["error.DATA_DATE_STALE_PANEL"]), propre(TEXTES_PANNEAU[langue]), `panel text ${langue}`);
  }
  const filtres = { team: undefined, from: "2026-Q1", to: "2026-Q3" } as never;
  const lire = (async () => {
    throw new RefusPanneau("DATA_DATE_STALE");
  }) as never;
  // The panel query has no `retryOnMount: false` of its own: without it the cached refusal is read again on mount and shown as loading.
  const client = new QueryClient({ defaultOptions: { queries: { retryOnMount: false } } });
  for (const code of panneauxAffiches(filtres)) {
    client.getQueryCache().build(
      client,
      optionsPanneau(code, filtres, lire) as never,
      { data: undefined, dataUpdateCount: 0, dataUpdatedAt: 0, error: new RefusPanneau("DATA_DATE_STALE"), errorUpdateCount: 1, errorUpdatedAt: Date.now(), fetchFailureCount: 1, fetchFailureReason: null, fetchMeta: null, isInvalidated: false, status: "error", fetchStatus: "idle" } as never,
    );
  }
  for (const langue of ["en", "fr"] as Langue[]) {
    const html = propre(rendre(h(QueryClientProvider, { client }, h(SectionPanneaux, { lire, filtres })), langue));
    assert.ok(html.includes(propre(TEXTES_PANNEAU[langue])), `panel ${langue}`);
    assert.ok(!html.includes(propre(TEXTES_FICHE[langue])), "the sheet text is not shown on a panel");
    assert.ok(!html.includes("DATA_DATE_STALE"), "the code itself is never shown");
  }
});

test("the reader turns the answer of a stale sheet into its code: no body is passed on", async () => {
  const fauxServeur = (async () => new Response(JSON.stringify(PERIMEE), { status: 200, headers: { "content-type": "application/json" } })) as unknown as typeof fetch;
  await assert.rejects(
    () => lireFicheHttp("7", fauxServeur),
    (erreur: unknown) => erreur instanceof ErreurApi && erreur.code === "DATA_DATE_STALE",
  );
});

test("a stale sheet is shown with its catalogue message, in English and in French, and with no body, no verdict and no chart", () => {
  const client = new QueryClient();
  const erreur = new ErreurApi("DATA_DATE_STALE");
  const lire: LecteurFiche = async () => {
    throw erreur;
  };
  client.getQueryCache().build(
    client,
    optionsFiche(lire, "7") as never,
    {
      data: undefined,
      dataUpdateCount: 0,
      dataUpdatedAt: 0,
      error: erreur,
      errorUpdateCount: 1,
      errorUpdatedAt: Date.now(),
      fetchFailureCount: 1,
      fetchFailureReason: erreur,
      fetchMeta: null,
      isInvalidated: false,
      status: "error",
      fetchStatus: "idle",
    } as never,
  );
  for (const langue of ["en", "fr"] as Langue[]) {
    // The conviction page and the sheet page read the same cached refusal (the error branch of the sheet page never reads its cycle).
    const pages = [
      h(PageConviction, { conviction: { genre: "lead_cycle_h1", id: "7" }, lire }),
      h(PageFiche, { id: "7", lire } as never),
    ];
    for (const page of pages) {
      const html = propre(rendre(h(QueryClientProvider, { client }, page), langue));
      assert.ok(!html.includes(catalogues[langue]["page.loading"]), "precondition: the cache was read");
      assert.match(html, /role="alert"/);
      assert.ok(html.includes(propre(catalogues[langue]["error.DATA_DATE_STALE"])), langue);
      assert.ok(!html.includes("DATA_DATE_STALE"), "the code itself is never shown");
      assert.ok(!html.includes("<svg") && !html.includes("<canvas"), "no chart");
      assert.ok(!html.includes(catalogues[langue]["fiche.method.show"]), "no method face, so no body");
    }
  }
});
