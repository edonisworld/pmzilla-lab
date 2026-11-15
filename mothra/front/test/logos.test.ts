// Task 24.7: the logos of slice 1 (design D32). The SVG files of public/logos/ are copied identically and keep their C2PA provenance
// block; the light variant is shown in the side column with an accessible name from the catalogues; the favicon is linked.
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { test } from "node:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { Application } from "../src/Application.ts";
import { catalogues } from "../src/i18n/langue.ts";
import type { Langue } from "../src/i18n/langue.ts";
import { controlerProvenance } from "./logos.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const DOSSIER = `${FRONT}public/logos/`;
const LOGO = "/logos/mothra-logo-clair.svg";
const ICONE = "/logos/mothra-icone-clair.svg";
const FAVICON = "/logos/mothra-favicon.svg";

test("a SVG without the C2PA provenance block fails and the failure names the file", () => {
  const bloc = '<svg xmlns="http://www.w3.org/2000/svg"><metadata><c2pa:manifest xmlns:c2pa="http://c2pa.org/manifest">AAAA</c2pa:manifest></metadata></svg>';
  assert.deepEqual(controlerProvenance([{ nom: "a.svg", contenu: bloc }]), []);
  assert.deepEqual(controlerProvenance([{ nom: "a.svg", contenu: bloc }, { nom: "b.svg", contenu: '<svg xmlns="http://www.w3.org/2000/svg"/>' }]), [
    "bloc de provenance C2PA absent : b.svg",
  ]);
  assert.deepEqual(controlerProvenance([{ nom: "c.svg", contenu: "<svg><c2pa:manifest></c2pa:manifest></svg>" }]), ["bloc de provenance C2PA absent : c.svg"]);
});

// public/logos/ is excluded from the public edition (edition manifest): this case skips when the folder is absent, and runs unchanged in the
// private repository where it exists (R-20261114-107; a static test of tests/build_edition guards the skip).
const SKIP_SANS_LOGOS = existsSync(DOSSIER) ? false : "public/logos/ absent (excluded from the public edition)";

test("each SVG of public/logos keeps its C2PA provenance block, and the three chosen logos are there", { skip: SKIP_SANS_LOGOS }, () => {
  const noms = readdirSync(DOSSIER).filter((n) => n.endsWith(".svg")).sort();
  assert.deepEqual(noms, ["mothra-favicon.svg", "mothra-icone-clair.svg", "mothra-logo-clair.svg"]);
  assert.deepEqual(controlerProvenance(noms.map((nom) => ({ nom: `public/logos/${nom}`, contenu: readFileSync(`${DOSSIER}${nom}`, "utf8") }))), []);
});

function page(langue: Langue): string {
  return renderToStaticMarkup(h(QueryClientProvider, { client: new QueryClient() }, h(Application, { langueInitiale: langue })));
}

// R-20261101-40 (Q156): the home no longer holds the status by team section, which carried the icon; the logo is checked in the side column
// (the mark of the side navigation), with its accessible name from the catalogues. The icon file stays shipped (the test above) and named by
// `src/marque.ts` only; no screen shows it now, and its accessible name `logo.icone.alt` left the catalogues with the section.
test("the side column shows the light logo with its accessible name from the catalogues, and no other variant", () => {
  for (const langue of ["en", "fr"] as const) {
    const html = page(langue);
    const colonne = /<aside[\s\S]*?<\/header>/.exec(html)?.[0] ?? "";
    const alt = (cle: string) => catalogues[langue][cle].replace("'", "&#x27;");
    assert.match(colonne, new RegExp(`<img[^>]*src="${LOGO}"[^>]*alt="${alt("logo.mothra.alt")}"|<img[^>]*alt="${alt("logo.mothra.alt")}"[^>]*src="${LOGO}"`), langue);
    // The link of the mark holds the logo alone: its accessible name is the alternative text of the image.
    assert.match(colonne, new RegExp(`<a href="#/"[^>]*><img[^>]*alt="${alt("logo.mothra.alt")}"[^>]*/?></a>`), langue);
    assert.doesNotMatch(html, /mothra-(logo|icone)-sombre|favicon/);
    // No screen shows the icon any more: the rendering does not name its file.
    assert.doesNotMatch(html, new RegExp(ICONE.replace(/[.]/g, "\\.")), langue);
  }
  assert.notEqual(catalogues.en["logo.mothra.alt"], catalogues.fr["logo.mothra.alt"]);
  assert.equal("logo.icone.alt" in catalogues.en, false);
});

test("the favicon is referenced by index.html", () => {
  const html = readFileSync(`${FRONT}index.html`, "utf8");
  assert.match(html, new RegExp(`<link[^>]*rel="icon"[^>]*href="${FAVICON}"|<link[^>]*href="${FAVICON}"[^>]*rel="icon"`));
});
