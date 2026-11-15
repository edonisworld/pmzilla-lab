// The reading of one sheet by the conviction page (mothra-demo-habillage D6): the reader is injected by the entry of the bundle (the real one
// is `lireFicheHttp`), and the query options give one cache key per sheet, so that the shell (the banner follows the dataset code of the
// answer) and the page read the same entry with no second request. The only route called is the existing one of the sheet.
import type { ReponseFiche } from "./fiche.ts";

export type LecteurFiche = (id: string) => Promise<ReponseFiche>;

// One key, no retry: an error code is an answer, not a fault to hide (as the dashboard).
export function optionsFiche(lire: LecteurFiche, id: string) {
  return {
    queryKey: ["sheet", id],
    queryFn: () => lire(id),
    retry: false,
    // A refusal stays the answer for this sheet: the page does not ask again by itself on mount.
    retryOnMount: false,
    refetchOnWindowFocus: false,
  };
}
