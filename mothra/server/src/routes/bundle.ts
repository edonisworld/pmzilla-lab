// Serving of the built front bundle by the server (mothra-slices D7, "Bundle served by the server", task 8.8): the bundle folder only, through
// the plugin @fastify/static (its sendFile decorator, no route and no directory listing of its own), with the resolution of a path decided
// here, in this order: a path leaving the folder or naming a folder is a 404, a file of the folder is that file, an absent file with an
// extension is a 404, `/` and any other path without an extension is `index.html` (the routes of the front in the browser).
// The answers carry codes only: NOT_FOUND, and BUNDLE_MISSING (503) when the bundle is not built. Nothing here reads the environment.
import { existsSync, realpathSync, statSync } from "node:fs";
import { isAbsolute, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

import fastifyStatic from "@fastify/static";
import type { FastifyInstance, FastifyReply, FastifyRequest } from "fastify";

// The built bundle of the front package (never tracked by Git); mothra/server/src/routes -> mothra/front/dist.
export const DOSSIER_BUNDLE_STANDARD = fileURLToPath(new URL("../../../front/dist", import.meta.url));

// The warning printed at start, on the standard error, when the bundle is not built (answer Q4): English, no path.
export const AVERTISSEMENT_BUNDLE_ABSENT = "mothra: warning (BUNDLE_MISSING)";

// The routes of the bundle: one handler, registered on `/` and on `/*`. They are the only routes dispensed from a response schema.
export const ROUTES_DU_BUNDLE: readonly string[] = ["GET /", "GET /*"];

// One definition of the extension, used by the server and its tests: the last segment of the path (the text after the last `/`, query
// string excluded) holds a `.` followed by at least one character. `/sheets/12` and `/home.` have none, `/app.js` and `/.well-known` have one.
export function aUneExtension(chemin: string): boolean {
  return extensionDuDernierSegment(chemin.split("?", 1)[0] ?? "");
}

// The code of a path nothing serves: UNKNOWN_VIEW only for the name position of the view route (an unknown view name, whatever its
// spelling or length), NOT_FOUND for any other path.
// Only a GET reaches a view route's name position as an unknown view: any other method is NOT_FOUND (no route answers it).
export function codeIntrouvable(chemin: string, methode = "GET"): "UNKNOWN_VIEW" | "NOT_FOUND" {
  if (methode !== "GET") {
    return "NOT_FOUND";
  }
  return /^\/api\/views\/[^/]*$/.test(chemin.split("?", 1)[0] ?? "") ? "UNKNOWN_VIEW" : "NOT_FOUND";
}

export function sousApi(chemin: string): boolean {
  const sansRequete = chemin.split("?", 1)[0] ?? "";
  return sansRequete === "/api" || sansRequete.startsWith("/api/");
}

// The path of a request as the router sees it: the query string removed on the raw text, then percent-decoded once. Null when the
// encoding is bad. The decoded text is never cut again (a decoded `?` belongs to a name).
export function cheminDecode(chemin: string): string | null {
  try {
    return decodeURIComponent(chemin.split("?", 1)[0] ?? "");
  } catch {
    return null;
  }
}

// The extension of the last segment of an already clean path (no query string to cut): a `.` followed by at least one character.
function extensionDuDernierSegment(propre: string): boolean {
  const segment = propre.slice(propre.lastIndexOf("/") + 1);
  return segment.slice(0, -1).includes(".");
}

export type Resolution = { genre: "absent" } | { genre: "index" } | { genre: "fichier"; relatif: string };

// The resolution of a request path outside /api/ against the bundle folder. Pure over the file system: nothing is read, only looked at.
export function resoudreChemin(dossier: string, chemin: string): Resolution {
  const decode = cheminDecode(chemin);
  if (decode === null) {
    return { genre: "absent" };
  }
  if (decode.includes("\0") || decode.includes("\\")) {
    return { genre: "absent" };
  }
  const segments = decode.split("/").filter((s) => s !== "");
  // 1. a path that leaves the folder, or names the current one, never reads outside it
  if (segments.some((s) => s === ".." || s === ".")) {
    return { genre: "absent" };
  }
  if (segments.length === 0) {
    return { genre: "index" };
  }
  const repli: Resolution = extensionDuDernierSegment(decode) ?{ genre: "absent" } : { genre: "index" };
  let racine: string;
  try {
    racine = realpathSync(dossier);
  } catch {
    return repli;
  }
  let reel: string;
  try {
    reel = realpathSync(join(racine, ...segments));
  } catch {
    return repli;
  }
  const rel = relative(racine, reel);
  if (rel === ".." || rel.startsWith(`..${sep}`) || isAbsolute(rel)) {
    return { genre: "absent" };
  }
  // 2. a folder is never listed, 3. a file of the bundle is that file
  return statSync(reel).isFile() ? { genre: "fichier", relatif: segments.join("/") } : { genre: "absent" };
}

export function enregistrerBundle(app: FastifyInstance, dossier: string): void {
  // `serve: false` and no root: the plugin registers no route and reads no folder, it only decorates the reply with sendFile.
  void app.register(fastifyStatic, { serve: false });
  // One handler on two routes, carrying no response schema: both are declared in ROUTES_WITHOUT_RESPONSE_SCHEMA (the answers are files
  // or code-only errors, whose bodies are written here and hold no data).
  const servir = async (requete: FastifyRequest, reponse: FastifyReply): Promise<FastifyReply> => {
    // /api/ is decided on the decoded path, as the router sees it; a bad encoding is NOT_FOUND.
    const decode = cheminDecode(requete.url);
    if (decode === null) {
      return reponse.code(404).send({ error: "NOT_FOUND" });
    }
    if (sousApi(decode)) {
      return reponse.code(404).send({ error: codeIntrouvable(decode) });
    }
    const resolution = resoudreChemin(dossier, requete.url);
    if (resolution.genre === "absent") {
      return reponse.code(404).send({ error: "NOT_FOUND" });
    }
    if (resolution.genre === "fichier") {
      return reponse.sendFile(resolution.relatif, dossier);
    }
    if (!existsSync(join(dossier, "index.html"))) {
      return reponse.code(503).send({ error: "BUNDLE_MISSING" });
    }
    return reponse.sendFile("index.html", dossier);
  };
  app.get("/", servir);
  app.get("/*", servir);
}
