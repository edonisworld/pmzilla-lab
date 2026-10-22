"""La couche brute sous la règle de conservation (change jira-data-architecture, D6, D11 ; spec jira-flow-retention « Raw layer under
the rule »). Tâche 4.7 (rouge d'abord), partie avec la fausse base ; les scénarios SQL sont dans test_couche_brute_base.py.

    bash tests/run_all.sh flow_retention </dev/null

La fausse base compte `brute` instantanés hors règle ; les requêtes écrites sont lues telles qu'elles partent à la base.
"""
import re
import unittest

from aide_flow_retention import AUJOURDHUI, ETIQUETTE, Espace, FausseBase, jours_avant       # place tools/ sur le chemin d'import
import flux_config as cfg

AGE_MAX = cfg.retention({})["max_file_age_days"]


class Controle(Espace):
    def test_la_ligne_de_la_couche_brute_dans_les_deux_langues(self):
        for langue, phrase in (("en", "raw layer: 2 snapshots out of rule"), ("fr", "couche brute : 2 instantanés hors règle")):
            code, sortie, erreur, _ = self.lancer("check", "--language", langue, base=FausseBase(0, brute=2))
            self.assertEqual(code, 4, erreur)
            self.assertIn(phrase, sortie.splitlines())                           # la ligne entière, sans suffixe
            self.assertEqual(sortie.splitlines().index(phrase), 1)               # juste après la ligne de la base

    def test_ligne_a_zero_et_code_0_quand_tout_est_propre(self):
        code, sortie, _, _ = self.lancer("check", "--language", "en", base=FausseBase(0, brute=0))
        self.assertEqual(code, 0)
        self.assertIn("raw layer: 0 snapshots out of rule", sortie.splitlines())

    def test_le_total_compte_la_couche_brute(self):
        code, sortie, _, _ = self.lancer("check", "--language", "en", base=FausseBase(3, jours_avant(400), brute=4))
        self.assertEqual(code, 4)
        self.assertTrue(sortie.rstrip().endswith("retention check: 7 items out of rule"), sortie)

    def test_les_visites_hors_regle_comptent_dans_le_total_sans_changer_la_ligne_des_instantanes(self):
        code, sortie, _, _ = self.lancer("check", "--language", "en", base=FausseBase(0, brute=0, visites=3))
        self.assertEqual(code, 4)                                                # des visites seules suffisent à sortir 4
        self.assertIn("raw layer: 0 snapshots out of rule", sortie.splitlines())  # la phrase de D11 ne compte que les instantanés
        self.assertTrue(sortie.rstrip().endswith("retention check: 3 items out of rule"), sortie)
        code, sortie, _, _ = self.lancer("check", "--language", "en", base=FausseBase(0, brute=2, visites=3))
        self.assertTrue(sortie.rstrip().endswith("retention check: 5 items out of rule"), sortie)

    def test_les_requetes_de_comptage_recoivent_les_dates_limites_du_ticket_de_l_age_maximal_et_des_cles_orphelines(self):
        base = FausseBase(0)
        self.lancer("check", base=base)
        parametres = (jours_avant(365), jours_avant(AGE_MAX), jours_avant(365))
        for table in ("raw_issue_snapshots", "raw_run_sightings"):
            comptes = [r for r in base.requetes if r[0].startswith("SELECT count(*)") and f"FROM flow.{table} s" in r[0]]
            self.assertEqual(len(comptes), 1, table)
            self.assertEqual(comptes[0][1], parametres)
        self.assertEqual(base.suppressions_brutes(), [])

    def test_aucune_cle_dans_la_sortie(self):
        _, sortie, erreur, _ = self.lancer("check", base=FausseBase(1, jours_avant(400), brute=5))
        self.assertNotRegex(sortie + erreur, r"[A-Z]+-\d+")


class Purge(Espace):
    def setUp(self):
        super().setUp()
        self.sauvegarde(AUJOURDHUI)

    def appliquer(self, base):
        return self.lancer("purge", "--apply", "--language", "en", base=base)

    def test_essai_garde_tout_et_affiche_la_ligne(self):
        code, sortie, _, base = self.lancer("purge", "--language", "en", base=FausseBase(0, brute=3))
        self.assertEqual(code, 0)
        self.assertIn("raw layer: 3 snapshots out of rule", sortie)
        self.assertEqual(base.suppressions_brutes(), [])
        self.assertEqual(base.suppressions(), [])

    def test_purge_supprime_instantanes_et_visites_avant_les_tickets_dans_une_transaction(self):
        code, sortie, erreur, base = self.appliquer(FausseBase(1, jours_avant(400), brute=2))
        self.assertEqual(code, 0, erreur)
        tables = [re.search(r"flow\.(raw_\w+|issues)", r[0]).group(1) for r in base.requetes if r[0].upper().startswith("DELETE")]
        self.assertEqual(tables, ["raw_issue_snapshots", "raw_run_sightings", "issues"])
        self.assertEqual((base.commits, base.rollbacks), (1, 0))
        for _, parametres in base.suppressions_brutes():
            self.assertEqual(parametres, (jours_avant(365), jours_avant(AGE_MAX), jours_avant(365)))

    def test_jamais_de_passage_supprime(self):
        _, _, _, base = self.appliquer(FausseBase(1, jours_avant(400), brute=2))
        self.assertFalse([r for r in base.requetes if r[0].upper().startswith("DELETE FROM FLOW.RAW_RUNS")])

    def test_la_regle_d_age_garde_le_dernier_instantane_et_la_derniere_visite(self):
        _, _, _, base = self.appliquer(FausseBase(0, brute=2))
        for sql, _ in base.suppressions_brutes():
            self.assertRegex(sql, r"run_id < \(SELECT max\(")                    # le plus récent de chaque ticket reste

    def test_seule_la_couche_brute_hors_regle_declenche_les_suppressions_brutes(self):
        _, _, _, base = self.appliquer(FausseBase(0, brute=3))
        self.assertEqual(len(base.suppressions_brutes()), 2)
        self.assertEqual(base.suppressions(), [])                                # aucun ticket hors règle
        _, _, _, vide = self.appliquer(FausseBase(0, brute=0))
        self.assertEqual((vide.suppressions(), vide.suppressions_brutes()), ([], []))

    def test_des_visites_seules_hors_regle_declenchent_la_purge_des_visites(self):
        """Un ticket ouvert, inchangé depuis un an : un seul instantané (le dernier, gardé), des visites anciennes."""
        code, _, erreur, base = self.appliquer(FausseBase(0, brute=0, visites=11))
        self.assertEqual(code, 0, erreur)
        tables = [re.search(r"flow\.(raw_\w+|issues)", r[0]).group(1) for r in base.requetes if r[0].upper().startswith("DELETE")]
        self.assertIn("raw_run_sightings", tables)
        self.assertEqual(base.suppressions(), [])                                # aucun ticket n'est supprimé pour autant
        self.assertEqual((base.commits, base.rollbacks), (1, 0))

    def test_echec_d_une_suppression_brute_annule_tout(self):
        base = FausseBase(1, jours_avant(400), echec_suppression=RuntimeError("zz"), brute=2)
        code, sortie, erreur, _ = self.appliquer(base)
        self.assertEqual(code, 1)
        self.assertIn("RuntimeError", erreur)
        self.assertEqual((base.commits, base.rollbacks), (0, 1))
        self.assertNotRegex(sortie + erreur, r"[A-Z]+-\d+")

    def test_sans_sauvegarde_du_jour_aucune_suppression(self):
        import shutil
        shutil.rmtree(self.sauvegardes / f"db-{AUJOURDHUI.isoformat()}-{ETIQUETTE}")
        code, sortie, _, base = self.appliquer(FausseBase(0, brute=3))
        self.assertEqual(code, 3)
        self.assertEqual(base.requetes, [])


if __name__ == "__main__":
    unittest.main()
