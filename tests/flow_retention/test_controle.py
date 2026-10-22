"""
Tests de `flow_retention.py check` (spec jira-flow-retention : « Retention check », « One-year retention clock per ticket »,
« Files left from the CSV route are deleted whatever their age », change database-only). Suite : tests/flow_retention.

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
        """Trois tickets hors règle et deux fichiers laissés par la voie CSV (un CSV du jour, l'ancien cache) : cinq éléments."""
        self.fichier(self.exports, "api-zzfichier-2026-10-13.csv", 0)
        self.cache({"A-1": {"termine": True, "resolu": "2025-01-01T10:00:00.000+0000", "transitions": []}})
        code, sortie, _, _ = self.lancer("check", "--language", "en", base=FausseBase(3, jours_avant(400)))
        self.assertEqual(code, 4)
        self.assertTrue(sortie.rstrip().endswith("retention check: 5 items out of rule"), sortie)
        self.assertIn("database, tickets past the rule: 3", sortie)
        self.assertIn("files left from the CSV route: 2", sortie)
        self.assertIn("oldest: 400 days", sortie)

    def test_deux_voies_une_base_propre_ne_cache_pas_un_csv_laisse(self):
        self.fichier(self.exports, "api-zzfichier.csv", 3)                # un CSV récent : hors règle quel que soit son âge
        code, sortie, _, _ = self.lancer("check", "--language", "en", base=FausseBase(0))
        self.assertEqual(code, 4)
        self.assertIn("files left from the CSV route: 1", sortie)
        self.assertIn("database, tickets past the rule: 0", sortie)
        self.assertTrue(sortie.rstrip().endswith("retention check: 1 items out of rule"))

    def test_la_base_seule_est_comptee_quand_aucun_fichier_n_est_laisse(self):
        code, sortie, _, _ = self.lancer("check", "--language", "en", base=FausseBase(2, jours_avant(366)))
        self.assertEqual(code, 4)
        self.assertIn("files left from the CSV route: 0", sortie)
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

    def test_tout_csv_est_compte_quel_que_soit_son_age_et_son_en_tete(self):
        """Database-only (D10) : plus de contrôle d'en-tête ni d'âge, tout CSV du dossier des exports est un fichier laissé."""
        self.fichier(self.exports, "api-recent.csv", 1, "Issue key,Status,Declared Label\nK-1,Done,a\n")
        self.fichier(self.exports, "manuel-zzfichier.csv", 400, "Issue key,Summary,Status\nZZKEY-1,zztitre,Done\n")
        self.fichier(self.exports, "vide.csv", 0, "")
        self.fichier(self.exports, "MAJUSCULE.CSV", 2, "a\n")
        self.fichier(self.exports, "notes.txt", 2, "pas un CSV")                 # un autre fichier n'est jamais compté
        code, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertEqual(code, 4)
        self.assertIn("files left from the CSV route: 4", sortie)
        self.assertTrue(sortie.rstrip().endswith("retention check: 4 items out of rule"))
        self.assertNotIn("forbidden column", sortie)

    def test_le_contenu_n_est_pas_lu(self):
        chemin = self.fichier(self.exports, "api-x.csv", 1, "Issue key,Status\nZZKEY-1,Done\n")
        chemin.write_bytes(chemin.read_bytes() + b"\xff\xfe\x00 fin")            # un fichier illisible compte sans erreur
        code, sortie, erreur, _ = self.lancer("check", "--language", "en")
        self.assertEqual(code, 4, sortie + erreur)
        self.assertIn("files left from the CSV route: 1", sortie)
        self.assertEqual(erreur, "")

    def test_la_ligne_ne_porte_ni_nom_ni_age(self):
        self.fichier(self.exports, "api-zzfichier.csv", 900)
        _, sortie, _, _ = self.lancer("check", "--language", "en")
        ligne = next(l for l in sortie.splitlines() if l.startswith("files left from the CSV route"))
        self.assertEqual(ligne, "files left from the CSV route: 1")
        self.assertNotIn("zzfichier", sortie)

    def test_les_csv_du_dossier_des_rapports_ne_sont_pas_comptes(self):
        self.fichier(self.rapports, "zzfichier.csv", 400)
        code, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("files left from the CSV route: 0", sortie)

    def test_ligne_en_francais(self):
        self.fichier(self.exports, "api-x.csv", 1)
        _, sortie, _, _ = self.lancer("check", "--language", "fr")
        self.assertIn("fichiers laissés par la voie CSV : 1", sortie)

    def test_fichier_de_points_et_csv_comptes_separement(self):
        self.fichier(self.tableaux, "points-zzserie-2025-01-01.json", 400, "[]")
        self.fichier(self.tableaux, "points-zzserie-2026-10-01.json", 12, "[]")
        self.fichier(self.exports, "api-ancien.csv", 366)
        self.fichier(self.exports, "api-limite.csv", 365)
        code, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertEqual(code, 4)
        self.assertIn("ageing-points files older than the maximum file age: 1", sortie)
        self.assertIn("files left from the CSV route: 2", sortie)
        self.assertTrue(sortie.rstrip().endswith("retention check: 3 items out of rule"))

    def test_age_maximal_de_fichier_configure_limite_aux_fichiers_de_points(self):
        self.ecrire_reglages(f"retention:\n  max_file_age_days: 30\n  backup_label: {ETIQUETTE}\n")
        self.fichier(self.tableaux, "points-a-2026-01-01.json", 31, "[]")
        self.fichier(self.tableaux, "points-b-2026-01-01.json", 29, "[]")
        self.fichier(self.exports, "api-b.csv", 29)                              # l'âge maximal ne s'applique pas à ce fichier
        _, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertIn("ageing-points files older than the maximum file age: 1", sortie)
        self.assertIn("files left from the CSV route: 1", sortie)

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

    def test_l_ancien_cache_compte_une_fois_quel_que_soit_son_contenu(self):
        """Le fichier de cache d'historique est un fichier laissé, compté une fois (non entrée par entrée), sans être lu."""
        self.cache({"A-1": {"termine": True, "resolu": "2025-01-05T08:00:00.000+0000", "transitions": []},
                    "A-2": {"termine": False, "vu_le": "2026-10-10", "transitions": []},
                    "A-3": {"termine": True, "transitions": []}})
        code, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertEqual(code, 4)
        self.assertIn("files left from the CSV route: 1", sortie)
        self.assertNotIn("history cache", sortie)

    def test_cache_illisible_compte_sans_erreur(self):
        self.historique.write_text("pas du json", encoding="utf-8")
        code, sortie, erreur, _ = self.lancer("check", "--language", "en")
        self.assertEqual(code, 4)
        self.assertIn("files left from the CSV route: 1", sortie)
        self.assertNotIn("zz", sortie + erreur)

    def test_cache_absent_ne_compte_pas(self):
        _, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertIn("files left from the CSV route: 0", sortie)

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
