"""
Tests de `flow_retention.py purge` (spec jira-flow-retention : « Purge is a dry run by default », « Ticket-level files under the rule,
aggregated reports kept », « Purge requires a labelled backup of the same day », « Files holding a forbidden column are deleted »).
Suite : tests/flow_retention.
"""
import json
import stat
import unittest

from aide_flow_retention import AUJOURDHUI, ETIQUETTE, Espace, FausseBase, jours_avant


class Remplissage(Espace):
    """Un jeu de données avec un élément hors règle dans chaque magasin de fichiers."""

    def setUp(self):
        super().setUp()
        self.vieux_csv = self.fichier(self.exports, "api-zzfichier-vieux.csv", 400)
        self.csv_recent = self.fichier(self.exports, "api-zzfichier-recent.csv", 2)
        self.manuel = self.fichier(self.exports, "manuel-zzfichier.csv", 1, "Issue key,Summary\nZZKEY-1,zztitre\n")
        self.points_vieux = self.fichier(self.tableaux, "points-zzserie-2025-01-01.json", 400, "[]")
        self.points_recent = self.fichier(self.tableaux, "points-zzserie-2026-10-01.json", 12, "[]")
        self.cache({"A-1": {"termine": True, "resolu": "2025-01-05T08:00:00.000+0000", "transitions": [], "vu_le": None},
                    "A-2": {"termine": False, "vu_le": jours_avant(3).isoformat(), "transitions": []}})
        self.historique.chmod(0o644)
        self.vieille_sauvegarde = self.sauvegarde(jours_avant(45), "rgpd")
        self.du_jour = self.sauvegarde(AUJOURDHUI)


class Essai(Remplissage):
    def test_essai_ne_supprime_rien_et_sort_0(self):
        avant = self.instantane()
        code, sortie, _, base = self.lancer("purge", "--language", "en", base=FausseBase(3, jours_avant(400)))
        self.assertEqual(code, 0)
        lignes = sortie.rstrip().splitlines()
        self.assertEqual(lignes[-1], "dry run: nothing deleted")
        self.assertEqual(lignes[-2], "retention check: 8 items out of rule")
        self.assertEqual(self.instantane(), avant)
        self.assertEqual(base.suppressions(), [])
        self.assertEqual((base.commits, base.rollbacks), (0, 0))

    def test_essai_avec_trois_tickets_hors_regle(self):
        for fichier in (self.vieux_csv, self.manuel, self.points_vieux):
            fichier.unlink()
        self.cache({})
        self.vieille_sauvegarde.joinpath("flow.dump").unlink()
        code, sortie, _, _ = self.lancer("purge", "--language", "en", base=FausseBase(3, jours_avant(400)))
        self.assertEqual(code, 0)
        self.assertTrue(sortie.rstrip().endswith("retention check: 3 items out of rule\ndry run: nothing deleted"), sortie)

    def test_essai_en_francais(self):
        code, sortie, _, _ = self.lancer("purge")
        self.assertEqual(code, 0)
        self.assertTrue(sortie.rstrip().endswith("contrôle de conservation : 5 éléments hors règle\nessai : rien n'est supprimé"),
                        sortie)

    def test_essai_propre(self):
        for fichier in (self.vieux_csv, self.manuel, self.points_vieux):
            fichier.unlink()
        self.cache({})
        self.vieille_sauvegarde.joinpath("flow.dump").unlink()
        code, sortie, _, _ = self.lancer("purge", "--language", "en")
        self.assertEqual(code, 0)
        self.assertTrue(sortie.rstrip().endswith("retention check: nothing out of rule\ndry run: nothing deleted"), sortie)

    def test_essai_sans_sauvegarde_etiquetee_du_jour(self):
        import shutil
        shutil.rmtree(self.du_jour)
        code, sortie, _, _ = self.lancer("purge", "--language", "en")
        self.assertEqual(code, 0)                                   # l'essai n'exige pas la sauvegarde


class Application(Remplissage):
    def appliquer(self, base=None, langue="en"):
        return self.lancer("purge", "--apply", "--language", langue, base=base or FausseBase(3, jours_avant(400)))

    def test_purge_appliquee(self):
        code, sortie, erreur, base = self.appliquer()
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sortie.rstrip().splitlines()[-1], "purge done")
        for supprime in (self.vieux_csv, self.manuel, self.points_vieux, self.vieille_sauvegarde / "flow.dump"):
            self.assertFalse(supprime.exists(), supprime.name)
        for reste in (self.csv_recent, self.points_recent, self.du_jour / "flow.dump"):
            self.assertTrue(reste.exists(), reste.name)
        self.assertEqual(sorted(json.loads(self.historique.read_text())), ["A-2"])
        self.assertEqual(len(base.suppressions()), 1)

    def test_purge_en_francais(self):
        code, sortie, _, _ = self.appliquer(langue="fr")
        self.assertEqual(code, 0)
        self.assertEqual(sortie.rstrip().splitlines()[-1], "purge faite")

    def test_dumps_knowledge_et_cases_des_sauvegardes_etiquetees_restent(self):
        self.appliquer()
        self.assertTrue((self.vieille_sauvegarde / "knowledge.dump").exists())
        self.assertTrue((self.vieille_sauvegarde / "cases.dump").exists())
        self.assertTrue(self.vieille_sauvegarde.is_dir())

    def test_un_controle_apres_la_purge_sort_0(self):
        self.appliquer()
        code, sortie, _, _ = self.lancer("check", "--language", "en", base=FausseBase(0))
        self.assertEqual(code, 0, sortie)

    def test_le_cache_est_reecrit_en_0600(self):
        self.appliquer()
        self.assertEqual(stat.S_IMODE(self.historique.stat().st_mode), 0o600)
        self.assertFalse(self.historique.with_name("transitions.json.tmp").exists())

    def test_cache_sans_entree_hors_regle_n_est_pas_reecrit(self):
        self.cache({"A-2": {"termine": False, "vu_le": jours_avant(3).isoformat(), "transitions": []}})
        self.historique.chmod(0o644)
        self.appliquer()
        self.assertEqual(stat.S_IMODE(self.historique.stat().st_mode), 0o644)

    def test_ordre_fichiers_cache_base_puis_sauvegardes(self):
        observations = {}
        test = self

        class Observatrice(FausseBase):
            def execute(self, sql, params=()):
                if sql.lstrip().upper().startswith("DELETE"):
                    observations["csv_deja_supprime"] = not test.vieux_csv.exists() and not test.points_vieux.exists()
                    observations["cache_deja_reecrit"] = "A-1" not in json.loads(test.historique.read_text())
                    observations["dump_encore_la"] = (test.vieille_sauvegarde / "flow.dump").exists()
                return super().execute(sql, params)

        code, _, _, _ = self.appliquer(Observatrice(3, jours_avant(400)))
        self.assertEqual(code, 0)
        self.assertEqual(observations, {"csv_deja_supprime": True, "cache_deja_reecrit": True, "dump_encore_la": True})
        self.assertFalse((self.vieille_sauvegarde / "flow.dump").exists())

    def test_une_seule_transaction_une_seule_suppression(self):
        _, _, _, base = self.appliquer()
        self.assertEqual(len(base.suppressions()), 1)
        self.assertEqual((base.commits, base.rollbacks), (1, 0))
        self.assertIn("flow.issues", base.suppressions()[0][0])
        self.assertEqual(base.suppressions()[0][1], (jours_avant(365),))

    def test_sans_ticket_hors_regle_aucune_suppression_en_base(self):
        _, _, _, base = self.appliquer(FausseBase(0))
        self.assertEqual(base.suppressions(), [])

    def test_echec_de_la_base_rollback_code_1_type_seul(self):
        base = FausseBase(3, jours_avant(400), echec_suppression=ConnectionError("ZZKEY-5 zzequipe"))
        code, sortie, erreur, _ = self.appliquer(base)
        self.assertEqual(code, 1)
        self.assertEqual((base.commits, base.rollbacks), (0, 1))
        self.assertIn("ConnectionError", erreur)
        self.assertNotIn("ZZKEY", sortie + erreur)
        self.assertNotIn("zzequipe", sortie + erreur)
        self.assertNotIn("purge done", sortie)
        self.assertTrue((self.vieille_sauvegarde / "flow.dump").exists())      # l'étape suivante n'a pas eu lieu

    def test_la_purge_ne_touche_ni_rapport_ni_page_ni_anonymes_ni_sauvegarde_simple_ni_hors_site(self):
        ancien = 800
        gardes = [self.fichier(self.rapports, "flux-zzserie-2024-01-01.md", ancien, "# rapport sans clé\n"),
                  self.fichier(self.rapports, "flux-zzserie-2024-01-01.json", ancien, "{}"),
                  self.fichier(self.rapports, "suivi-mensuel-2024-01-01.md", ancien, "résumé"),
                  self.fichier(self.rapports, "dependances-zzserie-2024-01-01.md", ancien, "# d"),
                  self.fichier(self.tableaux, "tableau-flux-zzserie-2024-01-01.html", ancien, "<html></html>"),
                  self.fichier(self.tableaux, "tableau-flux-zzserie-anonyme-2024-01-01.html", ancien, "<html></html>"),
                  self.fichier(self.tableaux, "anonymes.yaml", ancien, "equipes: {}\n")]
        simple = self.sauvegarde(jours_avant(300), None)
        self.etat_hors_site(0)
        contenus = {p: (p.read_bytes(), p.stat().st_mtime) for p in gardes}
        self.appliquer()
        for chemin, (octets, date) in contenus.items():
            self.assertEqual(chemin.read_bytes(), octets, chemin.name)
            self.assertEqual(chemin.stat().st_mtime, date, chemin.name)            # ni supprimé ni réécrit ni touché
        self.assertTrue((simple / "flow.dump").exists())
        self.assertTrue(self.statut.exists())

    def test_fichier_de_points_vieux_supprime_sans_imprimer_son_nom(self):
        _, sortie, erreur, _ = self.appliquer()
        self.assertFalse(self.points_vieux.exists())
        self.assertNotIn("points-", sortie + erreur)
        self.assertNotIn("zzserie", sortie + erreur)

    def test_fichiers_du_dossier_des_rapports_ne_sont_pas_exemptes(self):
        csv_rapports = self.fichier(self.rapports, "zzfichier.csv", 500)
        points_rapports = self.fichier(self.rapports, "points-zzserie-2024-01-01.json", 500, "[]")
        rapport = self.fichier(self.rapports, "flux-zzserie-2024-01-01.md", 500, "# r")
        self.appliquer()
        self.assertFalse(csv_rapports.exists())
        self.assertFalse(points_rapports.exists())
        self.assertTrue(rapport.exists())

    def test_entree_de_cache_hors_regle_retiree(self):
        self.appliquer()
        self.assertNotIn("A-1", json.loads(self.historique.read_text()))

    def test_export_de_l_api_recent_et_ancien_rapport_hors_champ(self):
        # un export de l'API récent reste, même avec colonnes d'étiquettes déclarées
        recent = self.fichier(self.exports, "api-declare.csv", 5, "Issue key,Declared Label,Fix Version\nK-1,a,b\n")
        self.appliquer()
        self.assertTrue(recent.exists())


class AnciensRapports(Espace):
    def test_rapports_et_pages_anciens_ne_changent_pas_le_total(self):
        _, avant, _, _ = self.lancer("check", "--language", "en")
        self.fichier(self.rapports, "flux-zzserie-2024-01-01.md", 900, "# r")
        self.fichier(self.rapports, "flux-mensuel-2024-01-01.md", 900, "# r")
        self.fichier(self.tableaux, "tableau-flux-zzserie-2024-01-01.html", 900, "<html></html>")
        self.fichier(self.tableaux, "tableau-flux-zzserie-anonyme-2024-01-01.html", 900, "<html></html>")
        self.fichier(self.tableaux, "anonymes.yaml", 900, "x: 1\n")
        code, apres, _, _ = self.lancer("check", "--language", "en")
        self.assertEqual(code, 0)
        self.assertEqual(avant, apres)


class SansSauvegardeDuJour(Remplissage):
    def test_refus_sans_sauvegarde_etiquetee(self):
        import shutil
        shutil.rmtree(self.du_jour)
        self.sauvegarde(AUJOURDHUI, None)                           # seulement une sauvegarde datée simple
        avant = self.instantane()
        code, sortie, _, base = self.lancer("purge", "--apply", "--language", "en")
        self.assertEqual(code, 3)
        self.assertIn("pre-purge backup missing: run the labelled backup first", sortie)
        self.assertEqual(self.instantane(), avant)
        self.assertEqual(base.requetes, [])

    def test_refus_en_francais(self):
        import shutil
        shutil.rmtree(self.du_jour)
        code, sortie, _, _ = self.lancer("purge", "--apply")
        self.assertEqual(code, 3)
        self.assertIn("sauvegarde avant purge absente : lancer d'abord la sauvegarde étiquetée", sortie)

    def test_sauvegarde_etiquetee_de_la_veille_refusee(self):
        import shutil
        shutil.rmtree(self.du_jour)
        self.sauvegarde(jours_avant(1))
        avant = self.instantane()
        code, sortie, _, _ = self.lancer("purge", "--apply", "--language", "en")
        self.assertEqual(code, 3)
        self.assertIn("pre-purge backup missing", sortie)
        self.assertEqual(self.instantane(), avant)

    def test_une_autre_etiquette_du_jour_est_refusee(self):
        import shutil
        shutil.rmtree(self.du_jour)
        self.sauvegarde(AUJOURDHUI, "autre")
        code, _, _, _ = self.lancer("purge", "--apply")
        self.assertEqual(code, 3)

    def test_etiquette_par_defaut_rgpd(self):
        self.ecrire_reglages("")
        self.sauvegarde(AUJOURDHUI, "rgpd")
        self.assertEqual(self.lancer("purge", "--apply")[0], 0)

    def test_la_purge_ne_cree_pas_la_sauvegarde(self):
        import shutil
        shutil.rmtree(self.du_jour)
        self.lancer("purge", "--apply")
        self.assertFalse((self.sauvegardes / f"db-{AUJOURDHUI.isoformat()}-{ETIQUETTE}").exists())


class ColonnesInterdites(Espace):
    def test_ancien_export_manuel(self):
        manuel = self.fichier(self.exports, "manuel-zzfichier.csv", 700, "Issue key,Summary,Description\nZZKEY-1,zz,zz\n")
        self.sauvegarde(AUJOURDHUI)
        code, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertIn("files with a forbidden column: 1", sortie)
        code, sortie, erreur, _ = self.lancer("purge", "--apply", "--language", "en")
        self.assertEqual(code, 0)
        self.assertFalse(manuel.exists())
        self.assertNotIn("zzfichier", sortie + erreur)

    def test_fichier_recent_avec_colonne_interdite_supprime_quel_que_soit_l_age(self):
        recent = self.fichier(self.exports, "manuel-recent.csv", 0, "Key,Assignee\nK-1,x\n")
        self.sauvegarde(AUJOURDHUI)
        self.lancer("purge", "--apply")
        self.assertFalse(recent.exists())

    def test_export_de_l_api_conserve(self):
        api = self.fichier(self.exports, "api-x.csv", 3, "Issue key,Status,Declared Label,Fix Version\nK-1,Done,a,b\n")
        self.sauvegarde(AUJOURDHUI)
        self.lancer("purge", "--apply")
        self.assertTrue(api.exists())

    def test_le_fichier_n_est_ni_reecrit_ni_lu_au_dela_de_l_entete(self):
        # un fichier dont les lignes de données sont illisibles : seul l'en-tête est lu, le fichier est supprimé tel quel
        manuel = self.fichier(self.exports, "manuel.csv", 1, "")
        manuel.write_bytes(b"Issue key,Comment\n" + b"\xff\xfe\x00" * 1000)
        self.sauvegarde(AUJOURDHUI)
        self.assertEqual(self.lancer("purge", "--apply")[0], 0)
        self.assertFalse(manuel.exists())


class CacheEntrees(Espace):
    def test_entree_terminee_ancienne_comptee_et_retiree(self):
        self.cache({"A-1": {"termine": True, "resolu": "2025-01-05T08:00:00.000+0000", "transitions": []}})
        self.sauvegarde(AUJOURDHUI)
        _, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertIn("history cache, entries past the rule: 1", sortie)
        self.lancer("purge", "--apply")
        self.assertEqual(json.loads(self.historique.read_text()), {})


if __name__ == "__main__":
    unittest.main()
