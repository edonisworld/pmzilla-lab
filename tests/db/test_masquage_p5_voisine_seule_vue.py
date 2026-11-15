"""P5 et la voisine seule candidate contre la base (change du masquage des sommes, R-144, groupe 20, tâches 20.1 et 20.3 ; décision R-20261104-49, réponses
Q1 (e) et Q2 (a) ; conception D15, P5 et B15 ; revue 19.1, correction C1).

    bash tools/dbtest.sh db

Écrit pour le dbtest de l'auteur : aucune de ces classes ne tourne sans la base jetable de test_flow_schema.py et aucune n'est lancée par une session.
  - la voisine seule candidate (spécification, « Neighbour that was the only candidate ») contre la vue : C 12 créés, 4 sans affects, trouvés 5 et 3 ; B 5,
    4, trouvé 1 (données réécrites selon R-20261106-24 ; à l'origine A 30 / 3 sans trouvé, B 40 / 8, deux trouvés de 32) ; au plancher, la vue rend ses lignes sans erreur et le créé de B est masqué (la cellule qui part sans borne haute) ; l'ensemble publié
    de ce cas n'est pas affirmé ;
  - la même photo contre la fonction SQL : aucune erreur, et les mêmes cellules que `masquer_vue` (la parité tient avec NULL pour « sans borne haute » :
    `greatest` ignorerait le NULL de `reg_a` et garderait T - 1 sans erreur, C1 de la revue 19.1) ;
  - le cas inventé de l'équipe A (12 créés publié, 12 sans affects masqué par la paire ; B 40, 27, trouvé 13) : la fonction SQL et `masquer_vue` masquent
    les mêmes cellules, dont le créé de A (P5 ferme la fuite) ;
  - le cas « D3 avant D2 » : la fonction SQL ne lève rien et masque les mêmes cellules que `masquer_vue` (P5 sautée la lecture « U_P = 0 »).
Données inventées. Replaces: rien (tests neufs). Removal: tombent avec P5 et avec la règle de la voisine seule (B15).
"""
import datetime as dt
import unittest

import test_masquage_propagation_vues as prop   # noqa: E402
import test_flow_version_photo_views as photo   # noqa: E402
import flow_views as fv                          # noqa: E402

PRODUIT = prop.PRODUIT
NOMS = prop.NOMS
APPEL = prop.APPEL
S1 = dt.date(2026, 3, 2)
COLONNES = {"found": 0, "defects_created": 5, "defects_without_affects": 6, "resolved_week": 7, "resolved_week_defects": 8}


def lignes_voisine_seule():
    """Données réécrites (R-20261106-24 (a), après R-20261106-22 et R-20261106-23 : écart D4 (d) rétabli, une équipe sans ligne de version a toujours ses
    deux cellules masquées par D2), celles de `voisine_seule_versions` (tests/flow_views/test_masquage_p5_voisine_seule.py) : la voisine seule joue sur la
    ligne de B, qui a une ligne de version au trouvé masqué. C 12 / 4, trouvés v1 = 5 et v3 = 3 ; B 5 / 4, trouvé v3 = 1 ; produit 17 / 8, trouvés 5 et 4.
    Données d'origine : A 30 / 3 sans trouvé, B 40 / 8, deux trouvés de 32."""
    return [(S1, True, "C", None, None, 12, 4, 20, 10), (S1, True, "B", None, None, 5, 4, 20, 10), (S1, True, "B", 3, 1, None, None, None, None),
            (S1, True, "C", 1, 5, None, None, None, None), (S1, True, "C", 3, 3, None, None, None, None), (S1, True, PRODUIT, None, None, 17, 8, 40, 20),
            (S1, True, PRODUIT, 1, 5, None, None, None, None), (S1, True, PRODUIT, 3, 4, None, None, None, None)]


def lignes_equipe_a_inventee():
    return [(S1, True, "A", None, None, 12, 12, 20, 10), (S1, True, "B", None, None, 40, 27, 20, 10), (S1, True, "B", 1, 13, None, None, None, None),
            (S1, True, PRODUIT, None, None, 52, 39, 40, 20), (S1, True, PRODUIT, 1, 13, None, None, None, None)]


def lignes_d3_avant_d2():
    return [(S1, True, "A", None, None, 30, 3, 20, 10), (S1, True, "B", None, None, 40, 27, 20, 10), (S1, True, "B", 1, 13, None, None, None, None),
            (S1, True, PRODUIT, None, None, 70, 30, 40, 20), (S1, True, PRODUIT, 1, 13, None, None, None, None)]


class VoisineSeuleContreLaVue(prop.AvecBase):
    """Spécification, « Neighbour that was the only candidate » : la photo rend ses lignes sans erreur, le créé de B est masqué."""

    def test_la_vue_publie_sans_erreur_et_masque_le_cree_de_b(self):
        c = self.conn()
        lundi = photo.LUNDI
        self.semaine(c, lundi, "reconstructed")
        # Données réécrites, assertions gardées (R-20261106-24 (a)) : celles de `lignes_voisine_seule` ; la version « v-un » (C seule) précède « v-trois »
        # (B et C), comme v1 et v3 dans les données de flow_views.
        v_un = self.version(c, nom="v-un", sortie=photo.SORTIE)
        v_trois = self.version(c, nom="v-trois", sortie=photo.SORTIE)
        self.ligne_version(c, lundi, "C", v_un, found=5)
        self.ligne_version(c, lundi, "C", v_trois, found=3)
        self.ligne_version(c, lundi, "B", v_trois, found=1)
        self.ligne_libre(c, lundi, "C", creees=12, sans_affects=4, resolus=20, resolus_defauts=10)
        self.ligne_libre(c, lundi, "B", creees=5, sans_affects=4, resolus=20, resolus_defauts=10)
        self.adopter(c, 6)
        lignes = self.lire_photo(c)                                                     # une exception de la vue ferait échouer l'appel
        self.assertTrue(lignes)
        libre_b = [l for l in lignes if l["team"] == "B" and l["version_no"] is None]
        self.assertEqual(len(libre_b), 1)
        self.assertIsNone(libre_b[0]["defects_created"])                                # la cellule masquée comme seule candidate restante


class FonctionSqlContreMasquerVue(prop.AvecBase):
    @staticmethod
    def attendues(lignes):
        rangees, tab = prop.tableaux(lignes)
        python = fv.masquer_vue(fv.VUE_PHOTO, NOMS, rangees, fv.PLANCHER)
        return rangees, tab, python

    def comparer(self, lignes):
        rangees, tab, python = self.attendues(lignes)
        c = self.conn()
        sql, erreur = self.appeler(c, APPEL, (*tab, None, None))
        self.assertIsNone(erreur)
        par_rang = {ligne[0]: ligne for ligne in sql}
        for i, (ligne, cellules) in enumerate(zip(rangees, python), start=1):
            for col in (("found",) if ligne[3] is not None else ("defects_created", "defects_without_affects")):
                self.assertEqual(par_rang[i][1 + COLONNES[col]], "masked" not in cellules[col], f"{ligne[:4]} {col}")
        return rangees, python

    def test_la_voisine_seule_aucune_erreur_et_les_cellules_de_masquer_vue(self):
        rangees, python = self.comparer(lignes_voisine_seule())
        b_libre = next(i for i, r in enumerate(rangees) if r[2] == "B" and r[3] is None)
        self.assertIn("masked", python[b_libre]["defects_created"])                     # B.c : la seule candidate restante, sans borne haute

    def test_le_cas_inventee_de_l_equipe_a_les_cellules_de_masquer_vue_et_le_cree_de_a_masque(self):
        rangees, python = self.comparer(lignes_equipe_a_inventee())
        a_libre = next(i for i, r in enumerate(rangees) if r[2] == "A" and r[3] is None)
        self.assertIn("masked", python[a_libre]["defects_created"])                     # P5 ferme la fuite : A.c masqué avec A.w

    def test_d3_avant_d2_aucune_erreur_et_les_cellules_de_masquer_vue(self):
        self.comparer(lignes_d3_avant_d2())


if __name__ == "__main__":
    unittest.main()
