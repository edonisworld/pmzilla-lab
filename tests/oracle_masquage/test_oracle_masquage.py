"""Tests de l'oracle de masquage tests/db/oracle_masquage.py (change masking-sums, R-144, tâche 1.1, conception D8).

    uv run python -m unittest discover -s tests/db -q -f

Sans base, sans dépendance : deux tables faites à la main, l'une qui fuit et l'autre non, plus quelques mesures de largeur. Chiffres inventés.
"""
import unittest

import oracle_masquage as oracle

SEUIL = 5


def une_ligne(table, seuil):
    """Règle d'essai : une cellule sous le seuil est masquée, le total de la ligne est toujours publié."""
    return tuple(tuple(None if v < seuil else v for v in ligne) + (sum(ligne),) for ligne in table)


def avec_produit(table, seuil):
    """Règle d'essai à deux dimensions : cellules sous le seuil masquées, une ligne « produit » donne la somme de chaque colonne."""
    image = tuple(tuple(None if v < seuil else v for v in ligne) for ligne in table)
    produit = tuple(sum(ligne[j] for ligne in table) for j in range(len(table[0])))
    return image + (produit,)


class Oracle(unittest.TestCase):
    def test_table_qui_fuit_une_valeur_unique(self):
        # 3 est masqué, 10 et 12 visibles, le total 25 est publié : 25 - 22 = 3, une seule valeur possible
        resultat = oracle.analyser(une_ligne, ((3, 10, 12),), SEUIL)
        self.assertEqual(resultat["intervalles"], {(0, 0): (3, 3)})
        self.assertEqual(resultat["largeurs"], {(0, 0): 0})
        self.assertEqual(resultat["fuites"], ["valeur unique : cellule (0, 0) = 3"])
        self.assertEqual(resultat["compatibles"], 1)

    def test_table_qui_ne_fuit_pas(self):
        # 3 et 2 sont masqués et leur somme (5) est au seuil : chacun peut valoir de 1 à 4, aucune valeur exacte, aucune somme sous le seuil
        resultat = oracle.analyser(une_ligne, ((3, 2, 10),), SEUIL)
        self.assertEqual(resultat["fuites"], [])
        self.assertEqual(resultat["intervalles"], {(0, 0): (1, 4), (0, 1): (1, 4)})
        self.assertEqual(resultat["largeurs"], {(0, 0): 3, (0, 1): 3})
        self.assertEqual(resultat["etroites"], 0)
        self.assertEqual(resultat["compatibles"], 4)

    def test_somme_deductible_sous_le_seuil(self):
        # 1 et 2 sont masqués, leur somme 3 se déduit du total et reste sous 5, bien qu'aucune cellule n'ait une valeur unique
        resultat = oracle.analyser(une_ligne, ((1, 2, 10),), SEUIL)
        self.assertEqual(resultat["fuites"], ["somme unique sous le seuil : cellules ((0, 0), (0, 1)) = 3"])
        self.assertEqual(resultat["intervalles"], {(0, 0): (0, 3), (0, 1): (0, 3)})

    def test_intervalle_etroit_permis_et_mesure(self):
        # deux cellules de 3 et 4 en colonne, la ligne du produit donne 7 : chacune vaut 3 ou 4 (une unité de large), aucune fuite
        resultat = oracle.analyser(avec_produit, ((3, 12), (4, 12)), SEUIL)
        self.assertEqual(resultat["fuites"], [])
        self.assertEqual(resultat["largeurs"], {(0, 0): 1, (1, 0): 1})
        self.assertEqual((resultat["etroites"], resultat["plus_etroite"]), (2, 1))

    def test_deux_cellules_de_quatre_se_retrouvent_par_la_somme_huit(self):
        # k cellules masquées de somme 4k valent chacune 4 : le cas X3 du produit
        resultat = oracle.analyser(avec_produit, ((4, 12), (4, 12)), SEUIL)
        self.assertEqual(resultat["intervalles"], {(0, 0): (4, 4), (1, 0): (4, 4)})
        self.assertEqual(len(resultat["fuites"]), 2)
        self.assertTrue(all(f.startswith("valeur unique") for f in resultat["fuites"]))

    def test_somme_unique_au_seuil_ou_au_dessus_est_permise(self):
        resultat = oracle.analyser(une_ligne, ((3, 2, 10),), SEUIL)
        self.assertFalse([f for f in resultat["fuites"] if f.startswith("somme unique")])

    def test_seuil_releve(self):
        # au seuil 10, 8 et 10 visible : 8 est masqué et 10 ne l'est pas ; le total 28 donne 8
        resultat = oracle.analyser(une_ligne, ((8, 10, 10),), 10, valeurs=range(0, 13))
        self.assertEqual(resultat["fuites"], ["valeur unique : cellule (0, 0) = 8"])

    def test_table_sans_cellule_masquee(self):
        resultat = oracle.analyser(une_ligne, ((6, 7, 8),), SEUIL)
        self.assertEqual((resultat["intervalles"], resultat["fuites"], resultat["plus_etroite"], resultat["etroites"]), ({}, [], None, 0))

    def test_elagage_et_domaine_reduit_donnent_le_meme_resultat(self):
        complet = oracle.analyser(avec_produit, ((3, 12), (4, 12)), SEUIL)
        reduit = oracle.analyser(avec_produit, ((3, 12), (4, 12)), SEUIL, valeurs=range(0, 13),
                                 elaguer=lambda lignes: all(ligne[1] >= SEUIL for ligne in lignes))      # la colonne visible est connue : on l'élague
        self.assertEqual(reduit["intervalles"], complet["intervalles"])
        self.assertEqual(reduit["compatibles"], complet["compatibles"])

    def test_tables_compatibles_ont_la_meme_image(self):
        compatibles = oracle.tables_compatibles(une_ligne, ((3, 2, 10),), SEUIL)
        self.assertEqual({une_ligne(t, SEUIL) for t in compatibles}, {une_ligne(((3, 2, 10),), SEUIL)})
        self.assertEqual(sorted(compatibles), [((1, 4, 10),), ((2, 3, 10),), ((3, 2, 10),), ((4, 1, 10),)])


if __name__ == "__main__":
    unittest.main()
