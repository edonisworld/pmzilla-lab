// The sample size of hypothesis 1, from published cells only (mothra-slices D30, masking-sums D16 "Sample size of H1", R-20261106-18, task 22.1).
// The lead time sample without the old items is items_lt - items_old, the cycle time sample is items_ct - items_old, both read from shown cells. When the
// count or items_old is masked, whatever rule masked it (primary, complement or the pair rule), there is no size: the verdict is "insufficient sample",
// with no lower bound taken, since a masked items_old may hide a value at or above the threshold. The size is never published, neither in the sheet nor in
// a table. Same rule as `taille_echantillon_h1` of tools/flow_views.py (a gap is detected by the shared cases H1a to H1c of contrats/cas-masquage.json).
// Replaces: the lower bound items_lt - (T - 1) of R-20261105-30 (false, R-20261106-18).
// Removal: permanent while a masked items_old may hide a value of the threshold or more and no view publishes the sample without the old items.
import type { CelluleLue } from "./lecture-vue.ts";

export type GenreEchantillon = "lead" | "cycle";

export function tailleEchantillonH1(
  genre: GenreEchantillon,
  cellules: { items_lt?: CelluleLue | null; items_ct?: CelluleLue | null; items_old?: CelluleLue | null },
): number | null {
  if (genre !== "lead" && genre !== "cycle") {
    throw new TypeError("genre : lead ou cycle attendu");
  }
  const effectif = genre === "lead" ? cellules.items_lt : cellules.items_ct;
  const anciens = cellules.items_old;
  if (effectif === undefined || effectif === null || anciens === undefined || anciens === null) {
    return null;
  }
  if (effectif.state !== "value" || anciens.state !== "value") {
    return null;
  }
  return effectif.value - anciens.value;
}
