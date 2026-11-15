// The one place that decides between the name of a team and its opaque identifier (mothra-slices D35, "Team names on screen", author's
// decisions R-20261104-33, -35, -62 Q1 (a)). The server leaves `team` out of the dashboard series unless its setting is on; the front learns
// the setting from the presence of `team` and shows the name when the dashboard answer holds one for the identifier, the identifier
// otherwise (never an empty label, never an error). No component decides this: they call `libelleEquipe` and `ordreEquipes`.
// Replaces: nothing (the sheet showed the identifier only, R-20261101-121 Q238, which stays the behaviour with the setting off).
// Removal: with single sign-on (D18, slice 5), when the authenticated role decides who sees the names (N3 (a)).
import { porteeDeScope } from "@mothra/contract/equipe";

import type { MethodeFiche } from "../api/fiche.ts";

// What the function reads of the dashboard answer: the series, by identifier, with the name when the setting is on.
export interface TableauEnMemoire {
  teams: readonly { team?: string; teamId: string }[];
}

// The shape of the opaque identifier is the one `identifiantEquipe` of the contract gives (16 hexadecimal characters): the contract's reader of a
// scope also accepts any lower-case word, so a scope `team.<a name>` is refused here and never shown.
const MOTIF_IDENTIFIANT_OPAQUE = /^[0-9a-f]{16}$/;

function nomDe(identifiant: string, tableau: TableauEnMemoire | undefined): string | undefined {
  const nom = tableau?.teams.find((serie) => serie.teamId === identifiant)?.team;
  return nom === undefined || nom === "" ? undefined : nom;
}

// A sheet's method (its scope gives the identifier; a scope that is not `team.<opaque identifier>` gives `undefined`) or an identifier given by
// a selector: the name when the dashboard answer in memory holds it, else the identifier.
export function libelleEquipe(entree: string, tableau?: TableauEnMemoire): string;
export function libelleEquipe(entree: MethodeFiche, tableau?: TableauEnMemoire): string | undefined;
export function libelleEquipe(entree: MethodeFiche | string, tableau?: TableauEnMemoire): string | undefined {
  if (typeof entree === "string") return nomDe(entree, tableau) ?? entree;
  const portee = porteeDeScope(entree.scope.id);
  if (portee === null || portee.kind !== "team" || !MOTIF_IDENTIFIANT_OPAQUE.test(portee.team)) return undefined;
  return nomDe(portee.team, tableau) ?? portee.team;
}

// The order of every selector: the order of the identifiers when the setting is off (no name in the answer), the alphabetical order of the
// names when it is on; the same order in all selectors. An order that depends on no figure.
export function ordreEquipes(identifiants: readonly string[], tableau?: TableauEnMemoire): string[] {
  const avecNoms = tableau?.teams.some((serie) => serie.team !== undefined && serie.team !== "") === true;
  const cle = (identifiant: string): string => (avecNoms ? (nomDe(identifiant, tableau) ?? identifiant) : identifiant);
  return [...identifiants].sort((a, b) => cle(a).localeCompare(cle(b)) || a.localeCompare(b));
}

// The key of a team on the screen of `ContenuTableau` (its own selector, the points drawn): the name when the answer holds one (setting on),
// else the identifier. A key of the screen only: the scope sent, the address and the stored texts take `teamId`, never this key.
// Replaces: the local helper of PageTableau.ts. Removal: with the setting (N3 (a)), or when the author makes `teamId` the only screen key.
export function cleEquipe(serie: { team?: string; teamId: string }): string {
  return serie.team === undefined || serie.team === "" ? serie.teamId : serie.team;
}
