"""
La borne basse lo = 1 d'un items_old masqué dont items_ct est montré (R-20261106-39 ; revue 21.2, constats 2 et 8 ; conception D2 et D16).

    bash tests/run_all.sh flow_views     (aucune base)

Elle est nommée dans trois fichiers, qu'un test statique compare : la migration 0037 (commentaire de tête, « sur les lignes trimestrielles et sur l'année de la sortie
du lecteur »), tools/flow_views.py (LO_ANCIENS_SI_CT_MONTRE, `_borne` avec son paramètre `items_ct_visible`) et mothra/contract/src/masquage.ts
(LO_ANCIENS_SI_CT_MONTRE). BORNES garde 0 pour items_old sans ce paramètre. Remplace : rien. Retrait : permanent tant que la vue publie items_old.
"""
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

MIGRATION = next((RACINE / "db" / "migrations").glob("0037_*.sql"))
TYPESCRIPT = RACINE / "mothra" / "contract" / "src" / "masquage.ts"


class BorneBasseDesAnciens(unittest.TestCase):
    def test_la_borne_vaut_zero_sans_items_ct_visible_et_un_avec(self):
        self.assertEqual(fv.BORNES[fv.VUE_DEBIT]["items_old"], (0, False))
        self.assertEqual(fv._borne(fv.VUE_DEBIT, "items_old"), (0, False))
        self.assertEqual(fv._borne(fv.VUE_DEBIT, "items_old", items_ct_visible=False), (0, False))
        self.assertEqual(fv._borne(fv.VUE_DEBIT, "items_old", items_ct_visible=True), (1, False))
        self.assertEqual(fv.LO_ANCIENS_SI_CT_MONTRE, 1)

    def test_le_parametre_ne_change_aucune_autre_colonne(self):
        for vue, colonnes in fv.BORNES.items():
            for colonne in colonnes:
                if (vue, colonne) != (fv.VUE_DEBIT, "items_old"):
                    self.assertEqual(fv._borne(vue, colonne, items_ct_visible=True), fv.BORNES[vue][colonne], (vue, colonne))

    def test_la_largeur_d_un_items_old_masque_suit_la_borne_conditionnelle(self):
        noms = ["team", "period", "quarter_start", "throughput", "items_lt", "items_ct", "items_old", "items_without_commitment"]
        ligne = ("A", "quarter", "2026-01-01", 20, 20, 20, 3, 0)
        rangees = [dict(zip(noms, ligne))]
        cellules = fv.masquer_vue(fv.VUE_DEBIT, noms, [ligne], 5)
        self.assertEqual(fv._largeurs(fv.VUE_DEBIT, noms, rangees, cellules, 5)[(0, "items_old")], 5 - 1 - 1)       # items_ct montré : lo = 1, largeur 3

    def test_les_trois_fichiers_nomment_la_meme_borne(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        ts = TYPESCRIPT.read_text(encoding="utf-8")
        self.assertRegex(sql, r"borne basse 1 sur les lignes trimestrielles et sur l'année de la sortie du lecteur")
        self.assertIn("LO_ANCIENS_SI_CT_MONTRE", sql)
        self.assertRegex(ts, r"export const LO_ANCIENS_SI_CT_MONTRE = 1;")
        self.assertEqual(fv.LO_ANCIENS_SI_CT_MONTRE, 1)


if __name__ == "__main__":
    unittest.main()
