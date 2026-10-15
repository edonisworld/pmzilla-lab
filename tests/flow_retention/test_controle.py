"""
Tests de `flow_retention.py check` (spec jira-flow-retention : « Retention check », « One-year retention clock per ticket »,
« Files holding a forbidden column are deleted »). Suite : tests/flow_retention.

    bash tests/run_all.sh flow_retention </dev/null
"""
import datetime as dt
import unittest

from aide_flow_retention import AUJOURDHUI, ETIQUETTE, Espace, FausseBase, jours_avant

PHRASE_PROPRE = {"fr": "contrôle de conservation : rien hors règle", "en": "retention check: nothing out of rule"}


class Controle(Espace):
    def test_magasins_propres(self):
        for langue in ("fr", "en"):
            code, sortie, erreur, base = self.lancer("check", "--language", langue)
            self.assertEqual(code, 0, erreur)
            self.assertTrue(sortie.rstrip().endswith(PHRASE_PROPRE[langue]), sortie)

    def test_elements_hors_regle_code_4_et_total(self):
        self.cache({"A-1": {"termine": True, "resolu": "2025-01-01T10:00:00.000+0000", "transitions": []},
                    "A-2": {"termine": True, "resolu": "2024-06-01T10:00:00.000+0000", "transitions": []}})
        code, sortie, _, _ = self.lancer("check", "--language", "en", base=FausseBase(3, jours_avant(400)))
        self.assertEqual(code, 4)
        self.assertTrue(sortie.rstrip().endswith("retention check: 5 items out of rule"), sortie)
        self.assertIn("database, tickets past the rule: 3", sortie)
        self.assertIn("history cache, entries past the rule: 2", sortie)
        self.assertIn("oldest: 400 days", sortie)

    def test_deux_voies_une_base_propre_ne_cache_pas_un_vieux_csv(self):
        self.fichier(self.exports, "api-zzfichier.csv", 400)
        code, sortie, _, _ = self.lancer("check", "--language", "en", base=FausseBase(0))
        self.assertEqual(code, 4)
        self.assertIn("CSV exports older than the maximum file age: 1", sortie)
        self.assertIn("database, tickets past the rule: 0", sortie)
        self.assertTrue(sortie.rstrip().endswith("retention check: 1 items out of rule"))

    def test_la_base_seule_est_comptee_quand_les_fichiers_sont_propres(self):
        self.fichier(self.exports, "api-recent.csv", 3)
        code, sortie, _, _ = self.lancer("check", "--language", "en", base=FausseBase(2, jours_avant(366)))
        self.assertEqual(code, 4)
        self.assertTrue(sortie.rstrip().endswith("retention check: 2 items out of rule"))

    def test_la_base_est_interrogee_avec_la_date_limite(self):
        base = FausseBase(0)
        self.lancer("check", base=base)
        self.assertEqual(base.requetes[0][1], (jours_avant(365),))
        self.assertEqual(base.suppressions(), [])

    def test_duree_configuree(self):
        self.ecrire_reglages(f"retention:\n  period_days: 90\n  backup_label: {ETIQUETTE}\n")
        base = FausseBase(0)
        self.lancer("check", base=base)
        self.assertEqual(base.requetes[0][1], (jours_avant(90),))

    def test_colonne_interdite_compte_et_non_ancienne(self):
        self.fichier(self.exports, "manuel-zzfichier.csv", 2, "Issue key,Summary,Status\nZZKEY-1,zztitre,Done\n")
        code, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertEqual(code, 4)
        self.assertIn("files with a forbidden column: 1", sortie)
        self.assertIn("CSV exports older than the maximum file age: 0", sortie)

    def test_chaque_colonne_interdite(self):
        for colonne in ("Summary", "Title", "Résumé", "Description", "Creator", "Reporter", "Assignee", "Comment", "Labels"):
            with self.subTest(colonne=colonne):
                chemin = self.fichier(self.exports, "x.csv", 1, f"Issue key,{colonne}\nK-1,v\n")
                code, sortie, _, _ = self.lancer("check", "--language", "en")
                self.assertIn("files with a forbidden column: 1", sortie)
                chemin.unlink()

    def test_export_de_l_api_avec_etiquettes_declarees_n_est_pas_interdit(self):
        self.fichier(self.exports, "api-x.csv", 2, "Issue key,Status,Declared Label,Fix Version,Declared Label\nK-1,Done,a,b,c\n")
        code, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("files with a forbidden column: 0", sortie)

    def test_seul_l_entete_est_lu(self):
        # une ligne de données qui ressemble à un en-tête interdit ne compte pas ; un fichier binaire en queue ne casse rien
        chemin = self.fichier(self.exports, "api-x.csv", 1, "Issue key,Status\nSummary,Labels\n")
        chemin.write_bytes(chemin.read_bytes() + b"\xff\xfe\x00 fin")
        code, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertEqual(code, 0, sortie)

    def test_fichier_de_points_et_csv_vieux_comptes_separement(self):
        self.fichier(self.tableaux, "points-zzserie-2025-01-01.json", 400, "[]")
        self.fichier(self.tableaux, "points-zzserie-2026-10-01.json", 12, "[]")
        self.fichier(self.exports, "api-ancien.csv", 366)
        self.fichier(self.exports, "api-limite.csv", 365)
        code, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertEqual(code, 4)
        self.assertIn("ageing-points files older than the maximum file age: 1", sortie)
        self.assertIn("CSV exports older than the maximum file age: 1", sortie)
        self.assertTrue(sortie.rstrip().endswith("retention check: 2 items out of rule"))

    def test_age_maximal_de_fichier_configure(self):
        self.ecrire_reglages(f"retention:\n  max_file_age_days: 30\n  backup_label: {ETIQUETTE}\n")
        self.fichier(self.exports, "api-a.csv", 31)
        self.fichier(self.exports, "api-b.csv", 29)
        _, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertIn("CSV exports older than the maximum file age: 1", sortie)

    def test_sauvegardes_etiquetees_trop_vieilles(self):
        self.sauvegarde(jours_avant(31), "rgpd")
        self.sauvegarde(jours_avant(40), "zzlabel")                 # toute étiquette
        self.sauvegarde(jours_avant(10), "rgpd")
        self.sauvegarde(jours_avant(90), None)                      # sauvegarde datée simple : hors règle
        code, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertEqual(code, 4)
        self.assertIn("labelled backups whose flow dump outlived its lifetime: 2", sortie)
        self.assertIn("oldest: 40 days", sortie)

    def test_sauvegarde_sans_dump_flux_n_est_pas_comptee(self):
        self.sauvegarde(jours_avant(80), "rgpd", schemas=("knowledge", "cases"))
        code, _, _, _ = self.lancer("check")
        self.assertEqual(code, 0)

    def test_duree_de_vie_configuree(self):
        self.ecrire_reglages(f"retention:\n  labelled_backup_days: 5\n  backup_label: {ETIQUETTE}\n")
        self.sauvegarde(jours_avant(6), "rgpd")
        _, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertIn("labelled backups whose flow dump outlived its lifetime: 1", sortie)

    def test_copies_hors_site_lues_dans_la_ligne_d_etat(self):
        self.etat_hors_site(2, 35)
        code, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertEqual(code, 4)
        self.assertIn("off-site copies holding a flow dump that is too old: 2", sortie)
        self.assertIn("age configured at copy time: 35 days", sortie)
        self.assertTrue(sortie.rstrip().endswith("retention check: 2 items out of rule"))

    def test_hors_site_zero_et_etat_absent(self):
        self.etat_hors_site(0)
        self.assertEqual(self.lancer("check")[0], 0)
        self.statut.unlink()
        self.assertEqual(self.lancer("check")[0], 0)

    def test_cache_horloge_resolution_ou_dernier_jour_vu(self):
        self.cache({
            "A-1": {"termine": True, "resolu": "2025-01-05T08:00:00.000+0000", "vu_le": "2026-10-01", "transitions": []},   # hors règle
            "A-2": {"termine": True, "resolu": "2026-09-01T08:00:00.000+0000", "vu_le": "2024-01-01", "transitions": []},   # résolu récent
            "A-3": {"termine": False, "vu_le": "2025-02-01", "transitions": []},                                            # hors règle
            "A-4": {"termine": False, "vu_le": "2026-10-10", "resolu": None, "transitions": []},                            # encore dans l'export
            "A-5": {"termine": True, "transitions": []},                                                                    # sans date
            "A-6": {"termine": False, "transitions": []}})                                                                  # sans date
        code, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertEqual(code, 4)
        self.assertIn("history cache, entries past the rule: 2", sortie)

    def test_cache_exactement_a_la_limite_n_est_pas_hors_regle(self):
        self.cache({"A-1": {"termine": True, "resolu": jours_avant(365).isoformat() + "T10:00:00.000+0000", "transitions": []},
                    "A-2": {"termine": True, "resolu": jours_avant(366).isoformat() + "T10:00:00.000+0000", "transitions": []}})
        _, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertIn("history cache, entries past the rule: 1", sortie)

    def test_cache_illisible_code_1(self):
        self.historique.write_text("pas du json", encoding="utf-8")
        code, sortie, erreur, _ = self.lancer("check")
        self.assertEqual(code, 1)
        self.assertNotIn("zz", sortie + erreur)

    def test_erreur_de_base_code_1_type_seul(self):
        class Panne(FausseBase):
            def execute(self, sql, params=()):
                raise RuntimeError("ZZKEY-9 zzequipe")

        code, sortie, erreur, _ = self.lancer("check", base=Panne())
        self.assertEqual(code, 1)
        self.assertIn("RuntimeError", erreur)
        self.assertNotIn("ZZKEY", sortie + erreur)
        self.assertNotIn("zzequipe", sortie + erreur)

    def test_la_base_est_fermee(self):
        _, _, _, base = self.lancer("check")
        self.assertTrue(base.fermee)


if __name__ == "__main__":
    unittest.main()
