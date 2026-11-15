// The "no real data" check of the API (mothra-server, "No real data reaches the API"): applied to the answer of a route, it returns
// findings made of the route and a kind, never the matched value. A finding is `{ route, kind }`.
export type GenreDeConstat = "valeur sous le seuil" | "forme de clé de ticket" | "sentinelle";

export interface Constat {
  route: string;
  kind: GenreDeConstat;
}

const FORME_DE_CLE = /\b[A-Z][A-Z0-9]{1,9}-[0-9]{1,6}\b/;

interface CelluleLue {
  state?: unknown;
  value?: unknown;
  threshold?: unknown;
}

function parcourir(valeur: unknown, visiter: (v: unknown) => void): void {
  visiter(valeur);
  if (Array.isArray(valeur)) {
    for (const element of valeur) {
      parcourir(element, visiter);
    }
  } else if (valeur !== null && typeof valeur === "object") {
    for (const [cle, interne] of Object.entries(valeur)) {
      visiter(cle);
      parcourir(interne, visiter);
    }
  }
}

// `colonnesDeCompte`: the count columns of the view answered; `sentinelles`: strings that must never be served.
export function controler(route: string, corps: unknown, colonnesDeCompte: readonly string[], sentinelles: readonly string[]): Constat[] {
  const constats: Constat[] = [];
  const noter = (kind: GenreDeConstat): void => {
    if (!constats.some((c) => c.kind === kind)) {
      constats.push({ route, kind });
    }
  };
  parcourir(corps, (valeur) => {
    if (typeof valeur === "string") {
      if (FORME_DE_CLE.test(valeur)) {
        noter("forme de clé de ticket");
      }
      if (sentinelles.some((s) => valeur.includes(s))) {
        noter("sentinelle");
      }
    }
  });
  const racine = corps as { threshold?: unknown; rows?: unknown } | null;
  const seuil = typeof racine?.threshold === "number" ? racine.threshold : 5;
  if (Array.isArray(racine?.rows)) {
    for (const ligne of racine.rows as Array<Record<string, CelluleLue>>) {
      for (const colonne of colonnesDeCompte) {
        const cellule = ligne[colonne];
        if (cellule?.state === "value" && typeof cellule.value === "number" && cellule.value < seuil) {
          noter("valeur sous le seuil");
        }
        if (cellule?.state === "masked" && "value" in cellule) {
          noter("valeur sous le seuil");
        }
      }
    }
  }
  return constats;
}
