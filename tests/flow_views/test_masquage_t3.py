"""
Relation T3 du masquage (change masking-sums, D17, R-20261031-07, tâche 13.1) : lignes_publiees, VUES_LIEES, masquer_vue de la vue du débit et de la
vue hebdomadaire, semaines à cheval, seuil relevé. Aucune base, aucun réseau. Données inventées : équipes A et B, trimestre du 2026-04-01.
Les cas partagés X26a à X26f sont dans test_cas_masquage.py ; la parité avec la migration et le TypeScript est dans test_parite_t3.py.

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_views -p "test_masquage_t3.py" -q
"""
import sys
import unittest
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

NOMS_H = ["team", "type", "week_start", "tickets"]
NOMS_D = ["team", "period", "quarter_start", "throughput"]
T = "2026-04-01"           # un mercredi : la semaine du 2026-03-30 chevauche le début, celle du 2026-06-29 la fin (le trimestre suivant commence le 2026-07-01)


def hebdo(*lignes):
    return NOMS_H, list(lignes)


def debit(n, equipe="A", debut=T):
    return NOMS_D, [(equipe, "quarter", debut, n)]


def liees_debit(n, equipe="A", debut=T):
    return {fv.VUE_DEBIT: debit(n, equipe, debut)}


def liees_hebdo(*lignes):
    return {fv.VUE_HEBDO: hebdo(*lignes)}


def masque(cellule):
    return "masked" in cellule


class VuesLiees(unittest.TestCase):
    def test_les_deux_vues_se_lisent_ensemble(self):
        self.assertEqual(fv.VUES_LIEES[fv.VUE_HEBDO], (fv.VUE_DEBIT,))
        self.assertEqual(fv.VUES_LIEES[fv.VUE_DEBIT], (fv.VUE_HEBDO,))


class RegleA(unittest.TestCase):
    """Débit masqué : aucune ligne Story ni Task de l'équipe pour une semaine du trimestre ; les autres types gardent leurs règles."""

    LIGNES = [("A", "Story", "2026-04-06", None), ("A", "Task", "2026-04-06", None), ("A", "Story", "2026-04-13", None),
              ("A", "Task", "2026-04-13", None), ("A", "Bug", "2026-04-06", 12), ("B", "Story", "2026-04-06", 12)]

    def test_quatre_lignes_de_un_sont_retirees_la_ligne_bug_et_l_autre_equipe_restent(self):
        publiees = fv.lignes_publiees(fv.VUE_HEBDO, NOMS_H, self.LIGNES, 5, liees_debit(4))
        self.assertEqual(publiees, [("A", "Bug", "2026-04-06", 12), ("B", "Story", "2026-04-06", 12)])

    def test_sans_la_vue_du_debit_rien_n_est_retire(self):
        self.assertEqual(fv.lignes_publiees(fv.VUE_HEBDO, NOMS_H, self.LIGNES, 5, None), self.LIGNES)
        self.assertEqual(fv.lignes_publiees(fv.VUE_HEBDO, NOMS_H, self.LIGNES, 5, {}), self.LIGNES)

    def test_une_autre_vue_est_rendue_telle_quelle(self):
        lignes = [("A", "quarter", T, 4)]
        self.assertEqual(fv.lignes_publiees(fv.VUE_DEBIT, NOMS_D, lignes, 5, liees_hebdo()), lignes)

    def test_debit_nul_de_la_vue_est_un_debit_masque(self):
        publiees = fv.lignes_publiees(fv.VUE_HEBDO, NOMS_H, self.LIGNES, 5, liees_debit(None))
        self.assertEqual(len(publiees), 2)

    def test_seuil_releve_debit_de_7_lu_a_10(self):
        lignes = [("A", "Story", "2026-04-06", 5), ("A", "Task", "2026-04-13", 2), ("A", "Bug", "2026-04-06", 12)]
        self.assertEqual(fv.lignes_publiees(fv.VUE_HEBDO, NOMS_H, lignes, 10, liees_debit(7)), [("A", "Bug", "2026-04-06", 12)])
        # au plancher, un débit visible de 12 et deux lignes visibles (7 et 5) : rien à cacher, rien n'est retiré
        visibles = [("A", "Story", "2026-04-06", 7), ("A", "Task", "2026-04-13", 5)]
        self.assertEqual(fv.lignes_publiees(fv.VUE_HEBDO, NOMS_H, visibles, 5, liees_debit(12)), visibles)

    def test_type_en_minuscules_et_semaine_hors_trimestre(self):
        lignes = [("A", "story", "2026-04-06", None), ("A", "Story", "2026-07-06", 12), ("A", "Story", "2026-03-23", 12)]
        publiees = fv.lignes_publiees(fv.VUE_HEBDO, NOMS_H, lignes, 5, liees_debit(4))
        self.assertEqual(publiees, [("A", "Story", "2026-07-06", 12), ("A", "Story", "2026-03-23", 12)])

    def test_semaines_a_cheval_retirees_des_deux_limites(self):
        lignes = [("A", "Story", "2026-03-30", None), ("A", "Task", "2026-06-29", None), ("A", "Story", "2026-03-23", 9), ("A", "Story", "2026-07-06", 9)]
        self.assertEqual(fv.lignes_publiees(fv.VUE_HEBDO, NOMS_H, lignes, 5, liees_debit(4)), lignes[2:])

    def test_dates_en_objets_date(self):
        lignes = [("A", "Story", date(2026, 4, 6), None), ("A", "Bug", date(2026, 4, 6), 12)]
        publiees = fv.lignes_publiees(fv.VUE_HEBDO, NOMS_H, lignes, 5, {fv.VUE_DEBIT: (NOMS_D, [("A", "quarter", date(2026, 4, 1), 3)])})
        self.assertEqual(publiees, [("A", "Bug", date(2026, 4, 6), 12)])

    def test_masquer_vue_masque_les_cellules_des_lignes_retirees_si_l_appelant_oublie_le_filtre(self):
        sorties = fv.masquer_vue(fv.VUE_HEBDO, NOMS_H, [("A", "Story", "2026-04-06", 12), ("A", "Task", "2026-04-06", 8), ("A", "Bug", "2026-04-06", 12)],
                                 5, liees_debit(None))
        self.assertEqual([masque(s["tickets"]) for s in sorties], [True, True, False])
        self.assertEqual(sorties[0]["tickets"], {"value": None, "masked": "under_threshold", "threshold": 5})

    def test_masquer_vue_hebdomadaire_sans_vue_liee_est_inchange(self):
        sorties = fv.masquer_vue(fv.VUE_HEBDO, NOMS_H, [("A", "Story", "2026-04-06", 12)], 5)
        self.assertEqual(sorties[0]["tickets"], {"value": 12})


class RegleB(unittest.TestCase):
    """Débit visible : les lignes masquées ne sont publiées que si le reste ne fixe rien ; sinon le débit est masqué, puis la règle (a)."""

    def lignes(self, *masquees, visibles=(12, 11)):
        lignes = [("A", "Story", "2026-04-06", visibles[0]), ("A", "Task", "2026-04-06", visibles[1])]
        suite = [("A", "Story", "2026-04-13"), ("A", "Task", "2026-04-13"), ("A", "Story", "2026-04-20"), ("A", "Task", "2026-04-20")]
        return lignes + [suite[i] + (None,) for i in range(len(masquees))]

    def debit_masque(self, n, lignes, seuil=5):
        sorties = fv.masquer_vue(fv.VUE_DEBIT, NOMS_D, debit(n)[1], seuil, liees_hebdo(*lignes))
        return masque(sorties[0]["throughput"])

    def test_les_quatre_cas_de_defaillance_au_plancher(self):
        self.assertTrue(self.debit_masque(26, self.lignes(0, 0)))                    # k = 2, S = 3 : sous le seuil (k < S < T)
        self.assertTrue(self.debit_masque(25, self.lignes(0, 0)))                    # S = k
        self.assertTrue(self.debit_masque(31, self.lignes(0, 0)))                    # S = 4k
        self.assertTrue(self.debit_masque(26, self.lignes(0)))                       # k = 1 (V = 23 visible + un masque : S = 3)

    def test_temoins_verts(self):
        self.assertFalse(self.debit_masque(28, self.lignes(0, 0)))                   # k = 2, S = 5
        self.assertFalse(self.debit_masque(29, self.lignes(0, 0, 0)))                # k = 3, S = 6
        self.assertFalse(self.debit_masque(23, self.lignes()))                       # aucune ligne masquée : rien à cacher

    def test_lignes_masquees_d_une_equipe_sans_debit_ne_comptent_pas(self):
        sorties = fv.masquer_vue(fv.VUE_DEBIT, NOMS_D, debit(28, "B")[1], 5, liees_hebdo(*self.lignes(0, 0)))
        self.assertFalse(masque(sorties[0]["throughput"]))

    def test_debit_masque_par_la_regle_b_entraine_ses_effectifs_et_la_regle_a_retire_les_lignes(self):
        ligne = ("A", "quarter", T, 26)
        noms = NOMS_D + ["items_lt"]
        sorties = fv.masquer_vue(fv.VUE_DEBIT, noms, [ligne + (26,)], 5, liees_hebdo(*self.lignes(0, 0)))
        self.assertTrue(masque(sorties[0]["throughput"]))
        self.assertTrue(masque(sorties[0]["items_lt"]))
        publiees = fv.lignes_publiees(fv.VUE_HEBDO, NOMS_H, self.lignes(0, 0), 5, liees_debit(26))
        self.assertEqual(publiees, [])
        # le débit lu par la vue est déjà nul quand la vue SQL a retiré les lignes : même résultat
        self.assertEqual(fv.lignes_publiees(fv.VUE_HEBDO, NOMS_H, self.lignes(0, 0), 5, liees_debit(None)), [])

    def test_seuil_releve_les_conditions_se_lisent_au_seuil(self):
        # seuil 10 : lo = 1, hi = 9 ; débit 40, cellules visibles (>= 10) 12 + 11 = 23, deux masquées : S = 17, k = 2 : 17 >= 10, != 2, != 18
        self.assertFalse(self.debit_masque(40, self.lignes(0, 0), seuil=10))
        # S = 18 = 2 x 9 : épinglé
        self.assertTrue(self.debit_masque(41, self.lignes(0, 0), seuil=10))
        # S = 9 < 10 avec k = 2
        self.assertTrue(self.debit_masque(32, self.lignes(0, 0), seuil=10))
        # une cellule de 7 est masquée au seuil 10 : elle compte comme une ligne masquée (publiée à 7 par la vue)
        lignes = [("A", "Story", "2026-04-06", 12), ("A", "Task", "2026-04-06", 7), ("A", "Story", "2026-04-13", 7)]
        self.assertTrue(self.debit_masque(30, lignes, seuil=10))                      # k = 2, S = 18 = 2 x 9


class SemainesACheval(unittest.TestCase):
    """Quatre lectures des deux semaines qui chevauchent une limite ; lecture incohérente écartée ; toutes les lectures restantes doivent passer."""

    def lignes(self):
        return [("A", "Story", "2026-04-06", 12), ("A", "Task", "2026-04-13", 10), ("A", "Task", "2026-04-20", None),
                ("A", "Task", "2026-04-27", None), ("A", "Story", "2026-03-30", 7)]          # la dernière chevauche le début du trimestre

    def masque_le_debit(self, n):
        sorties = fv.masquer_vue(fv.VUE_DEBIT, NOMS_D, debit(n)[1], 5, liees_hebdo(*self.lignes()))
        return masque(sorties[0]["throughput"])

    def test_une_lecture_qui_echoue_suffit_pour_masquer(self):
        # n = 30. Avec la semaine (V = 29) : S = 1 < k = 2, incohérente, écartée. Sans (V = 22) : k = 2, S = 8 = 4k : échoue. Masqué.
        self.assertTrue(self.masque_le_debit(30))

    def test_une_lecture_incoherente_est_ecartee(self):
        # n = 34. Avec (V = 29) : k = 2, S = 5, passe. Sans (V = 22) : S = 12 > 8, incohérente, écartée. Publié.
        self.assertFalse(self.masque_le_debit(34))

    def test_les_semaines_a_cheval_retirent_les_lignes_quand_le_debit_est_masque(self):
        publiees = fv.lignes_publiees(fv.VUE_HEBDO, NOMS_H, self.lignes(), 5, liees_debit(30))
        self.assertEqual(publiees, [])
        publiees = fv.lignes_publiees(fv.VUE_HEBDO, NOMS_H, self.lignes(), 5, liees_debit(34))
        self.assertEqual(len(publiees), 5)

    def test_fin_de_trimestre_et_trimestre_suivant(self):
        # la semaine du 2026-06-29 chevauche la fin du trimestre du 2026-04-01 et fait partie du suivant : le débit masqué du suivant la retire aussi
        lignes = [("A", "Story", "2026-06-29", 12), ("A", "Bug", "2026-06-29", 12)]
        liees = {fv.VUE_DEBIT: (NOMS_D, [("A", "quarter", "2026-04-01", 40), ("A", "quarter", "2026-07-01", 3)])}
        self.assertEqual(fv.lignes_publiees(fv.VUE_HEBDO, NOMS_H, lignes, 5, liees), [("A", "Bug", "2026-06-29", 12)])

    def test_debut_de_trimestre_en_decembre_vers_janvier(self):
        self.assertEqual(fv._debut_suivant(date(2026, 10, 1)), date(2027, 1, 1))
        self.assertEqual(fv._debut_suivant(date(2026, 1, 1)), date(2026, 4, 1))


class PoolAnnee(unittest.TestCase):
    def test_la_ligne_de_l_annee_groupee_n_est_pas_un_trimestre(self):
        noms = NOMS_D
        lignes = [("A", "quarter", T, 28), ("A", "pooled_year", None, 28)]
        hebdo_lignes = [("A", "Story", "2026-04-06", 12), ("A", "Task", "2026-04-06", 11), ("A", "Story", "2026-04-13", None), ("A", "Task", "2026-04-13", None)]
        sorties = fv.masquer_vue(fv.VUE_DEBIT, noms, lignes, 5, liees_hebdo(*hebdo_lignes))
        self.assertFalse(masque(sorties[0]["throughput"]))


class AnneeEtVueLieeAbsente(unittest.TestCase):
    """Revue de T3 : B1 (l'année groupée) et non bloquant 1 (vue hebdomadaire ou date illisible : le débit est masqué)."""

    DEBUTS = ("2025-04-01", "2025-07-01", "2025-10-01", "2026-01-01")

    def test_annee_masquee_quand_un_trimestre_est_retire_par_t3(self):
        # q1 = 1 (masqué), q2 = 6 avec une ligne masquée (k = 1, S = 1 : retiré), q3 et q4 visibles ; l'année est masquée
        lignes = [("A", "quarter", self.DEBUTS[0], 1), ("A", "quarter", self.DEBUTS[1], 6), ("A", "quarter", self.DEBUTS[2], 30),
                  ("A", "quarter", self.DEBUTS[3], 30), ("A", "pooled_year", None, 67)]
        hebdo_lignes = [("A", "Story", "2025-07-08", 5), ("A", "Task", "2025-07-08", None)]
        sorties = fv.masquer_vue(fv.VUE_DEBIT, NOMS_D, lignes, 5, liees_hebdo(*hebdo_lignes))
        self.assertEqual([masque(s["throughput"]) for s in sorties], [True, True, False, False, True])

    def test_vue_hebdomadaire_sans_colonne_lisible_le_debit_est_masque(self):
        sorties = fv.masquer_vue(fv.VUE_DEBIT, NOMS_D, [("A", "quarter", T, 40)], 5, {fv.VUE_HEBDO: (["team", "tickets"], [("A", 12)])})
        self.assertTrue(masque(sorties[0]["throughput"]))

    def test_date_de_ligne_hebdomadaire_illisible_le_debit_de_l_equipe_est_masque(self):
        for date_illisible in (None, "pas une date"):
            sorties = fv.masquer_vue(fv.VUE_DEBIT, NOMS_D, [("A", "quarter", T, 40), ("B", "quarter", T, 40)], 5,
                                     liees_hebdo(("A", "Story", date_illisible, 12), ("B", "Story", "2026-04-06", 12)))
            self.assertEqual([masque(s["throughput"]) for s in sorties], [True, False], str(date_illisible))

    def test_date_de_trimestre_illisible_le_debit_est_masque_et_les_lignes_retirees(self):
        sorties = fv.masquer_vue(fv.VUE_DEBIT, NOMS_D, [("A", "quarter", None, 40)], 5, liees_hebdo(("A", "Story", "2026-04-06", 12)))
        self.assertTrue(masque(sorties[0]["throughput"]))
        publiees = fv.lignes_publiees(fv.VUE_HEBDO, NOMS_H, [("A", "Story", "2026-04-06", 12), ("B", "Story", "2026-04-06", 12)], 5,
                                      {fv.VUE_DEBIT: (NOMS_D, [("A", "quarter", None, 40)])})
        self.assertEqual(publiees, [("B", "Story", "2026-04-06", 12)])


if __name__ == "__main__":
    unittest.main()
