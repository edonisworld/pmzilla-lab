"""L'écart D4 (d) rétabli contre la base (R-20261106-22, qui remplace R-20261105-6 Q4 (a) ; revue des chemins de démasquage de 0035, C1 et C1').

    bash tools/dbtest.sh db

Écrit pour le dbtest de l'auteur : aucune de ces classes ne tourne sans la base jetable de test_flow_schema.py et aucune n'est lancée par une session.
Une ligne d'équipe, ou du produit, sans ligne de version retenue cette semaine-là fait masquer ses défauts créés et sans affects, dans la fonction
flow.photo_masque et dans la vue, et la fonction SQL au plancher donne les cellules de `masquer_vue` (parité), pour une semaine puis pour trois (la
cascade C1'). La lecture statique de la migration et du lecteur Python est dans tests/flow_views/test_masquage_ecart_d4d.py ; les cas d'oracle
(aucune cellule publiée de plus que dans 0022, aucune fuite, balayage 0 <= w <= c <= 30) sont dans tests/oracle_masquage/test_oracle_ecart_d4d.py.
Données inventées : équipe A, semaines de mars 2026, versions synthétiques.
"""
import datetime as dt
import unittest

import test_masquage_propagation_vues as pv   # noqa: E402
import test_flow_version_photo_views as photo   # noqa: E402
import flow_views as fv                         # noqa: E402

PRODUIT = pv.PRODUIT
NOMS = pv.NOMS
APPEL = pv.APPEL
S1, S2, S3 = pv.S1, pv.S2, pv.S3


def une_semaine():
    """A et le produit : créés 40, sans affects 10, aucune ligne de version."""
    return [(S1, True, "A", None, None, 40, 10, 20, 10), (S1, True, PRODUIT, None, None, 40, 10, 20, 10)]


def cascade():
    """La cascade C1' : la semaine 1 n'a pas de ligne de version (créés 10, sans affects 5) ; les semaines 2 et 3 ont deux versions de trouvé 5 (créés 12 et
    15, sans affects 7 et 10, défauts distincts 5). Le produit est la somme de l'équipe A."""
    lignes = []
    for equipe in ("A", PRODUIT):
        lignes += [(S1, True, equipe, None, None, 10, 5, 20, 10),
                   (S2, True, equipe, None, None, 12, 7, 20, 10), (S2, True, equipe, 1, 5, None, None, None, None), (S2, True, equipe, 2, 5, None, None, None, None),
                   (S3, True, equipe, None, None, 15, 10, 20, 10), (S3, True, equipe, 3, 5, None, None, None, None), (S3, True, equipe, 4, 5, None, None, None, None)]
    return lignes


class EcartD4dRetabli(pv.AvecBase):
    @staticmethod
    def indice_sql(col):
        return pv.PariteMultiSemaines.indice_sql(col)

    def parite(self, lignes):
        """La fonction SQL au plancher et `masquer_vue` donnent les mêmes cellules ; rend la sortie SQL par rang pour les assertions du cas."""
        rangees, tab = pv.tableaux(lignes)
        python = fv.masquer_vue(fv.VUE_PHOTO, NOMS, rangees, fv.PLANCHER)
        sql, erreur = self.appeler(self.conn(), APPEL, (*tab, None, None))
        self.assertIsNone(erreur, erreur)
        par_rang = {ligne[0]: ligne for ligne in sql}
        for i, (ligne, cellules) in enumerate(zip(rangees, python), start=1):
            for col in (("found",) if ligne[3] is not None else ("defects_created", "defects_without_affects")):
                self.assertEqual(par_rang[i][1 + self.indice_sql(col)], "masked" not in cellules[col], f"{ligne[:4]} {col}")
        return rangees, par_rang

    def visibles_libres(self, rangees, par_rang, equipe):
        """Par semaine, (créés publiés, sans affects publiés) de la ligne sans version de l'équipe ou du produit, d'après la fonction SQL."""
        return [(bool(par_rang[i][1 + self.indice_sql("defects_created")]), bool(par_rang[i][1 + self.indice_sql("defects_without_affects")]))
                for i, ligne in enumerate(rangees, start=1) if ligne[2] == equipe and ligne[3] is None]

    def test_une_semaine_la_fonction_sql_masque_comme_python_equipe_et_produit(self):
        rangees, par_rang = self.parite(une_semaine())
        for equipe in ("A", PRODUIT):
            self.assertEqual(self.visibles_libres(rangees, par_rang, equipe), [(False, False)], equipe)

    def test_plusieurs_semaines_la_fonction_sql_masque_comme_python_cascade(self):
        """Semaines 1 et 2 masquées, semaine 3 publiée (créés 15, sans affects 10) : comme la vue de 0022."""
        rangees, par_rang = self.parite(cascade())
        for equipe in ("A", PRODUIT):
            self.assertEqual(self.visibles_libres(rangees, par_rang, equipe), [(False, False), (False, False), (True, True)], equipe)

    def test_la_vue_une_semaine_sans_ligne_de_version_masque_creees_et_sans_affects(self):
        """Le cas du test fixe de tests/db/test_masquage_somme_vues.py (créés 40, sans affects 10, aucune ligne de version, équipe et produit) : la vue masque
        les créés, les sans affects et la part, comme 0022."""
        c = self.conn()
        self.version(c, nom="v-un", sortie=photo.SORTIE)
        self.semaine(c, photo.LUNDI, "reconstructed")
        self.ligne_libre(c, photo.LUNDI, "A", creees=40, sans_affects=10, resolus=20, resolus_defauts=10)
        self.adopter(c, 6)
        libres = {l["team"]: l for l in self.lire_photo(c) if l["team"] is not None and l["version_no"] is None}
        self.assertEqual(set(libres), {"A", PRODUIT})                                  # ensemble : « (produit) » trie avant « A »
        for equipe, libre in libres.items():
            self.assertEqual((libre["defects_created"], libre["defects_without_affects"], libre["without_affects_share_percent"]), (None, None, None), equipe)

    def test_la_vue_plusieurs_semaines_cascade(self):
        c = self.conn()
        semaines = [(photo.LUNDI, photo.SORTIE), (photo.LUNDI + dt.timedelta(days=35), dt.date(2027, 1, 20)),
                    (photo.LUNDI + dt.timedelta(days=70), dt.date(2027, 2, 24))]
        donnees = [(10, 5, ()), (12, 7, (5, 5)), (15, 10, (5, 5))]
        for rang, ((lundi, sortie), (crees, sans, trouves)) in enumerate(zip(semaines, donnees)):
            self.semaine(c, lundi, "reconstructed")
            versions = [self.version(c, nom=f"v-{rang}-{k}", sortie=sortie) for k in range(2)]      # la semaine 1 a ses versions retenues, sans ligne
            for no, found in zip(versions, trouves):
                self.ligne_version(c, lundi, "A", no, found=found)
            self.ligne_libre(c, lundi, "A", creees=crees, sans_affects=sans, resolus=20, resolus_defauts=10)
        self.adopter(c, 6)
        for equipe in ("A", PRODUIT):
            libres = sorted([l for l in self.lire_photo(c) if l["team"] == equipe and l["version_no"] is None], key=lambda l: l["week_start"])
            self.assertEqual([(l["defects_created"], l["defects_without_affects"]) for l in libres], [(None, None), (None, None), (15, 10)], equipe)


if __name__ == "__main__":
    unittest.main()
