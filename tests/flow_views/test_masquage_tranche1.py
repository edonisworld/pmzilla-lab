"""
Masquage au seuil relevé des cinq vues de la tranche 1 (migration 0026, mothra-slices tâche 15.2) par masquer_vue.

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_views -v

La base masque sous 5. Ici, le seuil est relevé (10) : une valeur de 5 à 9 ne doit jamais être lisible, ni directement, ni par une statistique
(médiane, P85) dont l'effectif est masqué, ni par une part dont la partie, le tout ou le reste (tout moins partie) est masqué.
"""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

SEUIL = 10
T = "2026-01-01"
LEAD = ["team", "period", "quarter_start", "throughput", "items_lt", "lead_median_days", "lead_p85_days", "items_ct", "cycle_median_days",
        "cycle_p85_days", "items_old", "items_without_commitment"]
TACHES = ["quarter_start", "tasks_done", "tasks_without_team", "share_percent"]
BLOQUES = ["team", "quarter_start", "blocked_n", "blocked", "share_percent"]
NON_PLANIFIE = ["quarter_start", "unplanned_n", "unplanned", "share_percent"]
FILE = ["team", "quarter_start", "ready"]


def cellules(vue, noms, ligne, seuil=SEUIL):
    return fv.masquer_vue(vue, noms, [ligne], seuil)[0]


def masquee(cell) -> bool:
    return "masked" in cell and cell["value"] is None


class ColonnesDeCompte(unittest.TestCase):
    def test_les_trois_comptes_en_case_sont_des_colonnes_de_compte_avec_leurs_bornes(self):
        for colonne in ("tasks_without_team", "blocked", "unplanned"):
            self.assertIn(colonne, fv.COLONNES_COMPTE)
        self.assertEqual(fv.BORNES["v_task_without_team_share"]["tasks_without_team"], (0, True))
        self.assertEqual(fv.BORNES["v_team_blocked_share"]["blocked"], (0, True))
        self.assertEqual(fv.BORNES["v_unplanned_share"]["unplanned"], (0, True))

    def test_chaque_colonne_de_compte_de_chaque_vue_a_ses_bornes(self):
        for vue in fv.VUES_TRANCHE_1:
            for colonne in fv.BORNES[vue]:
                self.assertIn(colonne, fv.COLONNES_COMPTE, f"{vue}.{colonne}")


class LeadTimeEtCycleTime(unittest.TestCase):
    def test_les_statistiques_sont_masquees_avec_leur_effectif(self):
        # n = 40, m = 7 (masqué), c = 30, g = 10 : les statistiques suivent leur effectif ; c et g restent visibles (n - c = 10, |m - c| inconnu car m masqué)
        c = cellules("v_team_lead_time_throughput", LEAD, ("A", "quarter", T, 40, 7, 3.0, 9.0, 30, 4.0, 8.0, 0, 10))
        self.assertTrue(masquee(c["items_lt"]))
        self.assertTrue(masquee(c["lead_median_days"]))
        self.assertTrue(masquee(c["lead_p85_days"]))
        self.assertEqual(c["items_ct"], {"value": 30})
        self.assertEqual(c["cycle_median_days"], {"value": 4.0})
        self.assertEqual(c["cycle_p85_days"], {"value": 8.0})
        self.assertEqual(c["items_without_commitment"], {"value": 10})

    def test_la_paire_n_c_g_masque_items_ct_quand_g_est_sous_le_seuil(self):
        """Revue 15.2, constat 1 : n = 20, c = 12, g = 8 : g est masqué, et 20 - 12 = 8 le redonnerait : items_ct et ses statistiques le sont aussi."""
        c = cellules("v_team_lead_time_throughput", LEAD, ("A", "quarter", T, 20, 20, 3.0, 9.0, 12, 4.0, 8.0, 0, 8))
        self.assertTrue(masquee(c["items_ct"]))
        self.assertTrue(masquee(c["items_without_commitment"]))
        self.assertTrue(masquee(c["cycle_median_days"]) and masquee(c["cycle_p85_days"]))

    def test_la_paire_n_m_masque_items_lt_et_la_sortie_g_du_cycle_time_quand_l_ecart_est_sous_le_seuil(self):
        """n = 20, m = 15 (écart 5), c = 6, g = 14 : items_lt est masqué (20 - 15 = 5) et items_ct l'est (6 < 10) ; g = 14 se lirait avec n pour donner c."""
        c = cellules("v_team_lead_time_throughput", LEAD, ("A", "quarter", T, 20, 15, 3.0, 9.0, 6, 4.0, 8.0, 0, 14))
        self.assertEqual(c["throughput"], {"value": 20})
        for colonne in ("items_lt", "lead_median_days", "lead_p85_days", "items_ct", "cycle_median_days", "cycle_p85_days", "items_without_commitment"):
            self.assertTrue(masquee(c[colonne]), colonne)

    def test_cycle_time_masque_avec_items_ct(self):
        c = cellules("v_team_lead_time_throughput", LEAD, ("A", "quarter", T, 40, 30, 3.0, 9.0, 6, 4.0, 8.0, 0, 34))
        self.assertEqual(c["lead_median_days"], {"value": 3.0})
        self.assertTrue(masquee(c["items_ct"]))
        self.assertTrue(masquee(c["cycle_median_days"]))
        self.assertTrue(masquee(c["cycle_p85_days"]))
        self.assertTrue(masquee(c["items_without_commitment"]))     # c masqué : g = 34 avec n = 40 le redonnerait

    def test_au_seuil_les_statistiques_sont_montrees(self):
        c = cellules("v_team_lead_time_throughput", LEAD, ("A", "quarter", T, 20, 10, 3.0, 9.0, 10, 4.0, 8.0, 0, 10))
        self.assertEqual((c["lead_median_days"], c["lead_p85_days"], c["cycle_median_days"], c["cycle_p85_days"]),
                         ({"value": 3.0}, {"value": 9.0}, {"value": 4.0}, {"value": 8.0}))

    def test_une_statistique_au_seuil_du_plancher_reste_masquee_quand_le_seuil_est_releve(self):
        for effectif in range(5, 10):
            c = cellules("v_team_lead_time_throughput", LEAD, ("A", "quarter", T, 20, effectif, 3.0, 9.0, effectif, 4.0, 8.0, 0, 0))
            for colonne in ("lead_median_days", "lead_p85_days", "cycle_median_days", "cycle_p85_days", "items_lt", "items_ct"):
                self.assertTrue(masquee(c[colonne]), f"{colonne} avec effectif {effectif}")

    def test_au_plancher_rien_de_plus_n_est_masque(self):
        # ligne que la base peut rendre : n = 20, m = 15 (écart 5), c = 9, g = 11, |m - c| = 6
        c = cellules("v_team_lead_time_throughput", LEAD, ("A", "quarter", T, 20, 15, 3.0, 9.0, 9, 4.0, 8.0, 0, 11), seuil=fv.PLANCHER)
        self.assertEqual((c["lead_median_days"], c["cycle_median_days"], c["items_lt"], c["items_ct"], c["items_without_commitment"]),
                         ({"value": 3.0}, {"value": 4.0}, {"value": 15}, {"value": 9}, {"value": 11}))

    def test_une_ligne_d_annee_seule_est_entierement_masquee(self):
        """Fail-closed : sans les trimestres de sa série, l'année ne peut pas être comparée : comptes et statistiques masqués."""
        c = cellules("v_team_lead_time_throughput", LEAD, ("A", "pooled_year", None, 40, 8, 3.0, 9.0, 30, 4.0, 8.0, 0, 10))
        for colonne in ("throughput", "items_lt", "lead_median_days", "lead_p85_days", "items_ct", "cycle_median_days", "cycle_p85_days"):
            self.assertTrue(masquee(c[colonne]), colonne)


def ligne_debit(equipe, periode, trimestre, n, m, c, g, o):
    return (equipe, periode, trimestre, n, m, 3.0, 9.0, c, 4.0, 8.0, o, g)


def debit(lignes, seuil=SEUIL):
    return fv.masquer_vue("v_team_lead_time_throughput", LEAD, lignes, seuil)


SERIE = ("throughput", "items_lt", "items_ct", "items_without_commitment", "items_old")


class AnneeGroupeeContreTrimestres(unittest.TestCase):
    """Revue 15.2, constat 2 : au seuil relevé, l'année groupée ne se montre pas quand une cellule de sa série est masquée sur un trimestre
    (elle redonnerait, par différence, le trimestre masqué). Tests sur plusieurs lignes."""

    def lignes(self, trimestres, annee):
        quatre = [ligne_debit("A", "quarter", f"2025-0{k + 1}-01", n, n, n, 0, 0) for k, n in enumerate(trimestres)]
        return quatre + [ligne_debit("A", "pooled_year", None, annee, annee, annee, 0, 0)]

    def test_trimestres_20_20_20_et_7_masquent_l_annee_de_67(self):
        cellules_ = debit(self.lignes((20, 20, 20, 7), 67))
        self.assertTrue(masquee(cellules_[3]["throughput"]))                  # le trimestre à 7
        for colonne in ("throughput", "items_lt", "items_ct"):
            self.assertTrue(masquee(cellules_[4][colonne]), colonne)          # 67 - 60 = 7 se lirait

    def test_quatre_trimestres_visibles_laissent_l_annee_visible(self):
        cellules_ = debit(self.lignes((20, 20, 20, 20), 80))
        for colonne in ("throughput", "items_lt", "items_ct"):
            self.assertEqual(cellules_[4][colonne], {"value": 80}, colonne)

    def test_une_annee_sans_les_trimestres_de_son_equipe_est_masquee(self):
        autre_equipe = debit([ligne_debit("B", "quarter", "2025-01-01", 20, 20, 20, 0, 0), ligne_debit("A", "pooled_year", None, 80, 80, 80, 0, 0)])
        for colonne in SERIE:
            self.assertTrue(masquee(autre_equipe[1][colonne]), colonne)

    def test_sans_colonne_period_aucun_compte_de_la_serie_ne_se_montre(self):
        noms = [n for n in LEAD if n != "period"]
        ligne = ("A", T, 80, 80, 3.0, 9.0, 80, 4.0, 8.0, 0, 0)
        cel = fv.masquer_vue("v_team_lead_time_throughput", noms, [ligne], SEUIL)[0]
        for colonne in SERIE:
            self.assertTrue(masquee(cel[colonne]), colonne)

    def test_une_autre_equipe_n_est_pas_concernee(self):
        lignes = self.lignes((20, 20, 20, 7), 67) + [ligne_debit("B", "quarter", "2025-01-01", 20, 20, 20, 0, 0),
                                                       ligne_debit("B", "pooled_year", None, 20, 20, 20, 0, 0)]
        cellules_ = debit(lignes)
        self.assertEqual(cellules_[6]["throughput"], {"value": 20})

    def test_grille_d_annee_visible_seulement_si_tous_les_trimestres_de_la_serie_le_sont(self):
        valeurs = (0, 4, 7, 9, 10, 20)
        for q1 in valeurs:
            for q2 in valeurs:
                for q3 in valeurs:
                    for q4 in valeurs:
                        trimestres = (q1, q2, q3, q4)
                        cellules_ = debit(self.lignes(trimestres, sum(trimestres)))
                        annee = cellules_[4]
                        for colonne in ("throughput", "items_lt", "items_ct"):
                            if not masquee(annee[colonne]):
                                self.assertGreaterEqual(annee["throughput"]["value"], SEUIL, trimestres)
                                for k in range(4):
                                    self.assertFalse(masquee(cellules_[k][colonne]), (trimestres, colonne, k))


class GrilleDesPaires(unittest.TestCase):
    """Revue 15.2, constat 1 : au seuil 10, sur toute la grille (n, m, c, g = n - c, o) de 0 à 14, aucune relation entre cellules visibles ne laisse
    lire par différence une valeur de 1 à 9 : n = m + (n - m), n = c + g, c = o + (c - o), et m contre c."""

    def lu(self, cell):
        return None if masquee(cell) else cell["value"]

    def test_aucune_difference_de_1_a_9_n_est_lisible(self):
        def trop_petit(d):
            return d is not None and 0 < abs(d) < SEUIL
        for n in range(0, 15):
            for m in range(0, n + 1):
                for c in range(0, n + 1):
                    for o in sorted({0, c // 2, c}):
                        g = n - c
                        ligne = ligne_debit("A", "quarter", T, n, m, c, g, o)
                        cel = debit([ligne])[0]
                        vn, vm, vc, vg, vo = (self.lu(cel[k]) for k in SERIE)
                        contexte = (n, m, c, g, o)
                        for v in (vn, vm, vc, vg):
                            self.assertTrue(v is None or v >= SEUIL, contexte)
                        # R-20261106-39, R-20261106-43 : seule exception, le 0 de items_old quand items_ct est visible ; 1 à 4 restent refusés
                        self.assertTrue(vo is None or vo >= SEUIL or (vo == 0 and vc is not None), contexte)
                        if vn is not None and vm is not None:
                            self.assertFalse(trop_petit(vn - vm), contexte)
                        if vm is not None and vc is not None:
                            self.assertFalse(trop_petit(vm - vc), contexte)
                        if vc is not None and vo is not None:
                            self.assertFalse(trop_petit(vc - vo), contexte)
                        # n = c + g : deux cellules visibles donnent la troisième, qu'elle soit visible ou non
                        if vn is not None and vc is not None:
                            self.assertFalse(trop_petit(vn - vc), contexte)
                        if vn is not None and vg is not None:
                            self.assertFalse(trop_petit(vn - vg), contexte)
                        # les statistiques ne se montrent jamais avec un effectif masqué
                        self.assertEqual(masquee(cel["lead_median_days"]), vm is None, contexte)
                        self.assertEqual(masquee(cel["cycle_median_days"]), vc is None, contexte)


class PartsDesVuesDeLaTranche1(unittest.TestCase):
    CAS = (
        ("v_team_blocked_share", BLOQUES, ("A", T, 30, 12, 40.0), 2, 3),
        ("v_unplanned_share", NON_PLANIFIE, (T, 30, 12, 40.0), 1, 2),
        ("v_task_without_team_share", TACHES, (T, 30, 12, 40.0), 1, 2),
    )

    def test_une_part_est_montree_quand_la_partie_et_le_reste_atteignent_le_seuil(self):
        for vue, noms, ligne, i_tout, i_partie in self.CAS:
            c = cellules(vue, noms, ligne)
            self.assertEqual(c["share_percent"], {"value": 40.0}, vue)
            self.assertEqual(c[noms[i_partie]], {"value": 12}, vue)
            self.assertEqual(c[noms[i_tout]], {"value": 30}, vue)

    def test_une_partie_de_5_a_9_est_masquee_avec_sa_part(self):
        for vue, noms, ligne, i_tout, i_partie in self.CAS:
            for partie in range(5, 10):
                ligne_p = list(ligne)
                ligne_p[i_partie] = partie
                c = cellules(vue, noms, tuple(ligne_p))
                self.assertTrue(masquee(c[noms[i_partie]]), f"{vue} partie {partie}")
                self.assertTrue(masquee(c["share_percent"]), f"{vue} partie {partie}")

    def test_un_reste_de_5_a_9_masque_la_part_et_la_partie_qui_le_redonnerait(self):
        for vue, noms, ligne, i_tout, i_partie in self.CAS:
            for reste in range(0, 10):
                ligne_r = list(ligne)
                ligne_r[i_tout] = 30
                ligne_r[i_partie] = 30 - reste
                c = cellules(vue, noms, tuple(ligne_r))
                self.assertTrue(masquee(c["share_percent"]), f"{vue} reste {reste}")
                self.assertTrue(masquee(c[noms[i_partie]]), f"{vue} reste {reste}")

    def test_un_tout_sous_le_seuil_masque_la_part(self):
        for vue, noms, ligne, i_tout, i_partie in self.CAS:
            ligne_t = list(ligne)
            ligne_t[i_tout] = 8
            ligne_t[i_partie] = None
            ligne_t[-1] = None
            c = cellules(vue, noms, tuple(ligne_t))
            self.assertTrue(masquee(c[noms[i_tout]]), vue)
            self.assertTrue(masquee(c["share_percent"]), vue)

    def test_un_nul_de_la_vue_est_une_cellule_masquee(self):
        for vue, noms, ligne, i_tout, i_partie in self.CAS:
            ligne_n = list(ligne)
            ligne_n[i_partie] = None
            ligne_n[-1] = None
            c = cellules(vue, noms, tuple(ligne_n))
            self.assertTrue(masquee(c[noms[i_partie]]) and masquee(c["share_percent"]), vue)

    def test_aucune_valeur_de_5_a_9_n_est_lisible_sur_toute_la_grille(self):
        """Au seuil 10, pour toutes les valeurs de la partie et du tout de 0 à 25 : aucune cellule visible ne vaut de 5 à 9, et une part visible
        n'a ni partie ni reste sous le seuil (la part se lirait sinon par division)."""
        for vue, noms, _, i_tout, i_partie in self.CAS:
            for tout in range(0, 26):
                for partie in range(0, tout + 1):
                    ligne = [None] * len(noms)
                    ligne[0] = T if noms[0] == "quarter_start" else "A"
                    if noms[0] == "team":
                        ligne[1] = T
                    ligne[i_tout], ligne[i_partie] = tout, partie
                    ligne[-1] = round(100.0 * partie / tout, 1) if tout else None
                    c = cellules(vue, noms, tuple(ligne))
                    for colonne in (noms[i_tout], noms[i_partie]):
                        cell = c[colonne]
                        if not masquee(cell):
                            self.assertGreaterEqual(cell["value"], SEUIL, f"{vue} {tout}/{partie} {colonne}")
                    if not masquee(c["share_percent"]):
                        self.assertGreaterEqual(partie, SEUIL, f"{vue} {tout}/{partie}")
                        self.assertGreaterEqual(tout - partie, SEUIL, f"{vue} {tout}/{partie}")
                        self.assertFalse(masquee(c[noms[i_partie]]), f"{vue} {tout}/{partie}")


class FileEtComptesSimples(unittest.TestCase):
    def test_la_file_prete_de_5_a_9_est_masquee_au_seuil_releve(self):
        for n in range(5, 10):
            self.assertTrue(masquee(cellules("v_team_ready_queue", FILE, ("A", T, n))["ready"]), n)
        self.assertEqual(cellules("v_team_ready_queue", FILE, ("A", T, 10))["ready"], {"value": 10})

    def test_les_colonnes_simples_ne_sont_jamais_masquees(self):
        c = cellules("v_team_ready_queue", FILE, ("A", T, 3))
        self.assertEqual((c["team"], c["quarter_start"]), ({"value": "A"}, {"value": T}))


if __name__ == "__main__":
    unittest.main()
