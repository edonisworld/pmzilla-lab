"""
Les quatre statistiques « sans les anciens » de v_team_lead_time_throughput dans le contrat et dans le lecteur Python (change masking-sums, tâche 22.1 ;
conception D16, « Grouped year without the old items » ; R-20261105-30 ; R-20261106-18 et R-20261106-58 pour la taille d'échantillon).

    bash tests/run_all.sh flow_views     (aucune base)

Règle au seuil relevé T (lecteur Python, copie TypeScript) : une statistique « sans les anciens » est masquée avec son effectif (items_lt pour le lead time, items_ct
pour le cycle time) ; elle l'est aussi sauf si items_old de la ligne est montré et que l'effectif moins items_old atteint T (le lecteur ne lit pas m - o autrement :
il se ferme). Elle est aussi masquée quand sa valeur est nulle dans la vue. La taille d'échantillon de H1 se calcule des seules cellules montrées : l'effectif moins
items_old quand les deux sont montrés, aucune taille (verdict « échantillon insuffisant ») quand items_old est masqué, sans borne basse. Données inventées (équipe A).
"""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

VUE = "v_team_lead_time_throughput"
NOUVELLES = ("lead_median_days_excl_old", "lead_p85_days_excl_old", "cycle_median_days_excl_old", "cycle_p85_days_excl_old")
NOMS = ["team", "period", "quarter_start", "throughput", "items_lt", "lead_median_days", "lead_p85_days", "items_ct", "cycle_median_days", "cycle_p85_days",
        "items_old", "items_without_commitment", *NOUVELLES]
T = "2026-01-01"


def ligne(n, m, c, o, g=None, stats=(2.0, 6.0, 3.0, 7.0), periode="quarter"):
    return ("A", periode, T, n, m, 3.0, 9.0, c, 4.0, 8.0, o, n - c if g is None else g, *stats)


def cellules(brute, seuil=5):
    return fv.masquer_vue(VUE, NOMS, [brute], seuil)[0]


def masquee(cell):
    return "masked" in cell and cell["value"] is None


class Lecteur(unittest.TestCase):
    def test_le_lecteur_masque_chaque_nouvelle_statistique_avec_son_effectif(self):
        regles = fv.STATS_TRANCHE_1[VUE]
        self.assertEqual({k: regles[k] for k in NOUVELLES},
                         {"lead_median_days_excl_old": "items_lt", "lead_p85_days_excl_old": "items_lt",
                          "cycle_median_days_excl_old": "items_ct", "cycle_p85_days_excl_old": "items_ct"})


class AuSeuilRelevePuisAuPlancher(unittest.TestCase):
    def test_items_old_montre_et_reste_au_seuil_les_quatre_statistiques_sont_montrees(self):
        for seuil, o in ((5, 6), (5, 0), (10, 0), (10, 10)):
            with self.subTest(seuil=seuil, o=o):
                c = cellules(ligne(30, 30, 30, o), seuil)
                self.assertFalse(masquee(c["items_old"]), c["items_old"])
                for nom, valeur in zip(NOUVELLES, (2.0, 6.0, 3.0, 7.0)):
                    self.assertEqual(c[nom], {"value": valeur}, nom)

    def test_items_old_masque_masque_les_quatre_statistiques_meme_quand_le_reste_est_grand(self):
        c = cellules(ligne(20, 20, 20, 3))                                          # items_old 3 sous le seuil : masqué, le reste 17 ne se lit pas
        self.assertTrue(masquee(c["items_old"]))
        for nom in NOUVELLES:
            self.assertTrue(masquee(c[nom]), nom)

    def test_le_reste_sous_le_seuil_masque_la_statistique(self):
        # items_old 6 et items_ct 12 au seuil relevé 10 : items_old (6) est sous le seuil, masqué ; le reste 6 est sous 10
        c = cellules(ligne(12, 12, 12, 6), 10)
        for nom in NOUVELLES:
            self.assertTrue(masquee(c[nom]), nom)
        # items_old = items_ct : le reste est nul, la statistique n'a aucun échantillon
        c = cellules(ligne(20, 20, 20, 20))
        for nom in NOUVELLES:
            self.assertTrue(masquee(c[nom]), nom)

    def test_l_effectif_masque_masque_la_statistique(self):
        c = cellules(ligne(40, 7, 30, 0, g=10), 10)                                 # items_lt 7 sous 10 : masqué ; items_ct 30 montré
        self.assertTrue(masquee(c["items_lt"]))
        self.assertTrue(masquee(c["lead_median_days_excl_old"]))
        self.assertTrue(masquee(c["lead_p85_days_excl_old"]))
        self.assertEqual(c["cycle_median_days_excl_old"], {"value": 3.0})
        self.assertEqual(c["cycle_p85_days_excl_old"], {"value": 7.0})

    def test_une_valeur_nulle_dans_la_vue_est_une_cellule_masquee(self):
        c = cellules(ligne(30, 30, 30, 0, stats=(None, None, None, None)))
        for nom in NOUVELLES:
            self.assertIsNone(c[nom]["value"], nom)                                 # aucune valeur n'est inventée (un nul de la vue reste sans valeur)

    def test_sans_la_colonne_items_old_la_statistique_est_masquee(self):
        noms = [n for n in NOMS if n != "items_old"]
        brute = [v for n, v in zip(NOMS, ligne(30, 30, 30, 0)) if n != "items_old"]
        c = fv.masquer_vue(VUE, noms, [tuple(brute)], 5)[0]
        for nom in NOUVELLES:
            self.assertTrue(masquee(c[nom]), nom)

    def test_aucune_statistique_existante_ne_change(self):
        avant = fv.masquer_vue(VUE, NOMS[:12], [ligne(30, 30, 30, 3)[:12]], 5)[0]
        apres = cellules(ligne(30, 30, 30, 3))
        for nom in NOMS[:12]:
            self.assertEqual(apres[nom], avant[nom], nom)


class TailleDEchantillonDeH1(unittest.TestCase):
    def test_taille_de_cellules_montrees(self):
        c = cellules(ligne(20, 20, 20, 6))
        self.assertEqual(fv.taille_echantillon_h1(c, "lead"), 14)
        self.assertEqual(fv.taille_echantillon_h1(c, "cycle"), 14)

    def test_items_old_masque_n_a_pas_de_taille_meme_avec_un_reste_grand(self):
        self.assertIsNone(fv.taille_echantillon_h1(cellules(ligne(20, 20, 20, 3)), "lead"))       # masqué comme compte primaire
        self.assertIsNone(fv.taille_echantillon_h1(cellules(ligne(20, 20, 20, 17)), "cycle"))     # masqué par le complément : reste 3 sous le seuil, valeur 17 >= 5

    def test_effectif_masque_n_a_pas_de_taille(self):
        c = cellules(ligne(40, 7, 30, 0, g=10), 10)
        self.assertIsNone(fv.taille_echantillon_h1(c, "lead"))
        self.assertEqual(fv.taille_echantillon_h1(c, "cycle"), 30)

    def test_un_genre_inconnu_est_refuse(self):
        with self.assertRaises(ValueError):
            fv.taille_echantillon_h1(cellules(ligne(20, 20, 20, 6)), "autre")


if __name__ == "__main__":
    unittest.main()
