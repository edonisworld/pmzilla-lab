// The filters of the second screen (mothra-slices D35, task 31.3): one team by its opaque identifier or the whole product, and a range of
// closed quarters, kept in the address of the page so that a link carries them. Nothing is computed here: the shape of what the address
// holds is checked, anything else is dropped (a team name is not an identifier, an unknown parameter is not read), and the quarters
// the screen offers are those of the dashboard's own answer, never deduced from a clock.
// Replaces: nothing. Removal: with the end of the exception F12 (review of task 44.1), if the filters leave the dashboard.
import type { ReponseLeadCycle, ReponseLeadCycleReduite } from "@mothra/contract";
import { libelle } from "@mothra/contract/composition";
import { MOTIF_IDENTIFIANT_EQUIPE, porteeDeScope } from "@mothra/contract/equipe";

export interface FiltresEcran {
  // The opaque identifier of the team; absent: the whole product.
  team: string | undefined;
  // Closed quarters (`2026-Q1`); absent: the bound of the answer.
  from: string | undefined;
  to: string | undefined;
}

export const ADRESSE_TABLEAU = "#/tableau";
const MOTIF_TRIMESTRE = /^[0-9]{4}-Q[1-4]$/;

export const SANS_FILTRES: FiltresEcran = { team: undefined, from: undefined, to: undefined };

// The value of a parameter given exactly once and well formed; a repeated parameter (a list of teams) or a malformed one is dropped.
function unique(parametres: URLSearchParams, nom: string, motif: RegExp): string | undefined {
  const valeurs = parametres.getAll(nom);
  return valeurs.length === 1 && motif.test(valeurs[0]) ? valeurs[0] : undefined;
}

export function lireFiltresAdresse(adresse: string): FiltresEcran {
  const debut = adresse.indexOf("?");
  const parametres = new URLSearchParams(debut < 0 ? "" : adresse.slice(debut + 1));
  return {
    team: unique(parametres, "team", MOTIF_IDENTIFIANT_EQUIPE),
    from: unique(parametres, "from", MOTIF_TRIMESTRE),
    to: unique(parametres, "to", MOTIF_TRIMESTRE),
  };
}

export function ecrireFiltresAdresse(filtres: FiltresEcran): string {
  const parametres = new URLSearchParams();
  if (filtres.team !== undefined && MOTIF_IDENTIFIANT_EQUIPE.test(filtres.team)) parametres.set("team", filtres.team);
  if (filtres.from !== undefined && MOTIF_TRIMESTRE.test(filtres.from)) parametres.set("from", filtres.from);
  if (filtres.to !== undefined && MOTIF_TRIMESTRE.test(filtres.to)) parametres.set("to", filtres.to);
  const requete = parametres.toString();
  return requete === "" ? ADRESSE_TABLEAU : `${ADRESSE_TABLEAU}?${requete}`;
}

// The range the screen uses (A-81): a bound that is not one of the quarters offered falls back to the oldest (from) or the newest (to) of
// them, and a range read the wrong way round is put in order. Without any quarter offered both bounds are absent.
export function plageEffective(from: string | undefined, to: string | undefined, disponibles: readonly string[]): { from: string | undefined; to: string | undefined } {
  const debut = from !== undefined && disponibles.includes(from) ? from : disponibles.at(0);
  const fin = to !== undefined && disponibles.includes(to) ? to : disponibles.at(-1);
  return debut !== undefined && fin !== undefined && debut > fin ? { from: fin, to: debut } : { from: debut, to: fin };
}

// The address of the dashboard that a sheet's "detail by quarter" link opens (audit #629, A-03): the sheet's team, by its opaque identifier, and
// the first and last quarters of its period, in the filters of the address, so that the dashboard opens on that team and that period and not
// on the first team of the list. The scope gives the identifier (`team.<identifier>`; a team name, the product level or any other text gives
// none); the quarters are the sheet's own, formatted as the address does (`2026-Q3`). A part the sheet does not hold is left out. Nothing is
// computed: the values are read from the method face of the answer.
// Replaces: the plain address `#/tableau` of the link. Removal: permanent while the link is offered.
export function adresseTableauDeFiche(methode: { scope: { id: string; level?: string }; period: { quarters: ReadonlyArray<{ year: number; quarter: number }> } }): string {
  const portee = porteeDeScope(methode.scope.id);
  const premier = methode.period.quarters.at(0);
  const dernier = methode.period.quarters.at(-1);
  const etiquette = (t: { year: number; quarter: number } | undefined): string | undefined => (t === undefined ? undefined : libelle(t));
  return ecrireFiltresAdresse({
    team: portee !== null && portee.kind === "team" ? portee.team : undefined,
    from: etiquette(premier),
    to: etiquette(dernier),
  });
}

// Whether a quarter lies in the range (a bound left out is open). Quarter labels sort as text.
export function dansPlage(trimestre: string, from: string | undefined, to: string | undefined): boolean {
  return (from === undefined || trimestre >= from) && (to === undefined || trimestre <= to);
}

// Whether a label is a calendar quarter; the pooled-year point of a series (`pooled_year`) is not one.
function estTrimestre(etiquette: string): boolean {
  return MOTIF_TRIMESTRE.test(etiquette);
}

// The quarters the answer of the dashboard holds, oldest first, each once: the ones the bar offers. The product line of the real answer is
// empty (the view has no product row), so the quarters are read from the series of the teams too; the pooled-year point is not a quarter.
export function trimestresDisponibles(reponse: ReponseLeadCycle | ReponseLeadCycleReduite): string[] {
  const equipes: ReadonlyArray<{ points: ReadonlyArray<{ quarter: string }> }> = reponse.teams;
  const etiquettes = [...reponse.product.map((point) => point.quarter), ...equipes.flatMap((equipe) => equipe.points.map((point) => point.quarter))];
  return [...new Set(etiquettes.filter(estTrimestre))].sort();
}

// The answer of the dashboard reduced to the quarters of the range: points are kept or dropped, none is altered. The pooled-year point is
// not a quarter: the range never removes it.
export function filtrerParPlage<R extends ReponseLeadCycle | ReponseLeadCycleReduite>(reponse: R, from: string | undefined, to: string | undefined): R {
  const garder = <P extends { quarter: string }>(points: readonly P[]): P[] =>
    points.filter((point) => !estTrimestre(point.quarter) || dansPlage(point.quarter, from, to));
  return {
    ...reponse,
    product: garder(reponse.product),
    teams: reponse.teams.map((equipe) => ({ ...equipe, points: garder(equipe.points) })),
  } as R;
}
