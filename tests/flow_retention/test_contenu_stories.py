"""
Tests du magasin « contenu des stories » de `flow_retention.py` (change story-quality-audit, tâche 1.8 ; spec jira-flow-retention :
« Retention check », « Purge is a dry run by default », « Story content under the one-year rule », « Story quality reports stay
outside the rule »). Suite : tests/flow_retention.

Ici la base est la FAUSSE connexion de aide_flow_retention.py (comptes choisis, journal des événements) : l'horloge SQL elle-même et la
cascade sont prouvées sur une vraie base par test_base.py (ContenuDesStories), à lancer par l'utilisateur (bash tools/dbtest.sh
flow_retention). Données inventées : aucune clé, aucune équipe, aucun texte ; les marques « zz » ne doivent jamais ressortir.
"""
import json
import unittest

from aide_flow_retention import AUJOURDHUI, Espace, FausseBase, jours_avant


class Controle(Espace):
    def test_deux_elements_hors_regle_seuls(self):
        code, sortie, erreur, _ = self.lancer("check", "--language", "en", base=FausseBase(contenu=2, contenu_plus_ancien=jours_avant(400)))
        self.assertEqual(code, 4, erreur)
        self.assertIn("story content: 2 items out of rule", sortie)
        self.assertTrue(sortie.rstrip().endswith("retention check: 2 items out of rule"), sortie)
        self.assertIn("oldest: 400 days", sortie)

    def test_en_francais(self):
        code, sortie, _, _ = self.lancer("check", base=FausseBase(contenu=2))
        self.assertEqual(code, 4)
        self.assertIn("contenu des stories : 2 éléments hors règle", sortie)
        self.assertTrue(sortie.rstrip().endswith("contrôle de conservation : 2 éléments hors règle"), sortie)

    def test_le_magasin_s_ajoute_au_total(self):
        self.cache({"A-1": {"termine": True, "resolu": "2025-01-01T10:00:00.000+0000", "transitions": []}})
        self.fichier(self.exports, "api-zzfichier.csv", 400)
        code, sortie, _, _ = self.lancer("check", "--language", "en", base=FausseBase(3, jours_avant(400), contenu=4))
        self.assertEqual(code, 4)
        self.assertIn("database, tickets past the rule: 3", sortie)
        self.assertIn("story content: 4 items out of rule", sortie)
        self.assertTrue(sortie.rstrip().endswith("retention check: 9 items out of rule"), sortie)

    def test_ligne_du_magasin_a_zero_et_total_propre(self):
        for langue, ligne, fin in (("en", "story content: 0 items out of rule", "retention check: nothing out of rule"),
                                   ("fr", "contenu des stories : 0 éléments hors règle", "contrôle de conservation : rien hors règle")):
            code, sortie, _, _ = self.lancer("check", "--language", langue)
            self.assertEqual(code, 0)
            self.assertIn(ligne, sortie)
            self.assertTrue(sortie.rstrip().endswith(fin), sortie)

    def test_la_ligne_du_magasin_suit_celle_de_la_couche_brute(self):
        """La ligne de la couche brute suit celle de la base (jira-data-architecture, fusionné avant) ; celle du contenu des stories
        vient juste après, à côté d'elle (jira-data-architecture D7)."""
        _, sortie, _, _ = self.lancer("check", "--language", "en")
        lignes = sortie.splitlines()
        self.assertEqual(lignes.index("story content: 0 items out of rule"),
                         lignes.index("raw layer: 0 snapshots out of rule") + 1)
        self.assertEqual(lignes.index("raw layer: 0 snapshots out of rule"),
                         lignes.index("database, tickets past the rule: 0") + 1)

    def test_la_requete_lit_le_schema_quality_avec_la_date_limite_et_les_trois_instants(self):
        base = FausseBase()
        self.lancer("check", base=base)
        comptes = base.comptes_contenu()
        self.assertEqual(len(comptes), 1)
        sql, params = comptes[0]
        self.assertEqual(params, (jours_avant(365),))
        for colonne in ("quality.items", "text_collected_at", "resolved_at", "out_of_collection_at"):
            self.assertIn(colonne, sql)
        self.assertEqual(base.suppressions_contenu(), [])

    def test_la_requete_du_contenu_vient_apres_celle_des_tickets_sous_le_role_du_schema(self):
        base = FausseBase()
        self.lancer("check", base=base)
        self.assertTrue(base.requetes[0][0].startswith("SELECT") and "flow.issues" in base.requetes[0][0])
        self.assertIn("SET ROLE pmzilla_quality", base.evenements)
        self.assertNotIn("DELETE", " ".join(base.evenements))

    def test_duree_configuree(self):
        self.ecrire_reglages("retention:\n  period_days: 90\n  backup_label: zzetiquette\n")
        base = FausseBase()
        self.lancer("check", base=base)
        self.assertEqual(base.comptes_contenu()[0][1], (jours_avant(90),))

    def test_une_panne_du_magasin_donne_le_type_seul(self):
        class Panne(FausseBase):
            def execute(self, sql, params=()):
                if "quality." in sql:
                    raise RuntimeError("ZZKEY-9 zzequipe zztitre")
                return super().execute(sql, params)

        code, sortie, erreur, _ = self.lancer("check", base=Panne())
        self.assertEqual(code, 1)
        self.assertIn("RuntimeError", erreur)
        for marque in ("ZZKEY", "zzequipe", "zztitre"):
            self.assertNotIn(marque, sortie + erreur)

    def test_aucune_valeur_de_la_base_ne_ressort(self):
        """La sortie ne porte que des effectifs et des âges : la fausse base ne renvoie qu'un compte et une date."""
        _, sortie, erreur, _ = self.lancer("check", "--language", "en", base=FausseBase(contenu=3, contenu_plus_ancien=jours_avant(500)))
        for marque in ("zz", "ZZ", "PROJ-", "quality."):
            self.assertNotIn(marque, sortie + erreur)


class EssaiEtPurge(Espace):
    def preparer(self):
        self.sauvegarde(AUJOURDHUI)

    def test_essai_compte_le_magasin_sans_rien_supprimer(self):
        base = FausseBase(contenu=2, contenu_plus_ancien=jours_avant(400))
        code, sortie, _, _ = self.lancer("purge", "--language", "en", base=base)
        self.assertEqual(code, 0)
        lignes = sortie.rstrip().splitlines()
        self.assertIn("story content: 2 items out of rule", sortie)
        self.assertEqual(lignes[-2], "retention check: 2 items out of rule")
        self.assertEqual(lignes[-1], "dry run: nothing deleted")
        self.assertEqual(base.suppressions_contenu(), [])
        self.assertEqual((base.commits, base.rollbacks), (0, 0))

    def test_purge_appliquee_supprime_le_contenu_en_une_transaction(self):
        self.preparer()
        base = FausseBase(contenu=2, contenu_plus_ancien=jours_avant(400))
        code, sortie, erreur, _ = self.lancer("purge", "--apply", "--language", "en", base=base)
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sortie.rstrip().splitlines()[-1], "purge done")
        self.assertEqual(len(base.suppressions_contenu()), 1)
        sql, params = base.suppressions_contenu()[0]
        self.assertIn("DELETE FROM quality.items", sql)         # équipes, contenu, évaluations et retours partent en cascade
        self.assertEqual(params, (jours_avant(365),))
        self.assertEqual(base.suppressions(), [])               # aucun ticket hors règle : pas de suppression côté flow
        self.assertEqual((base.commits, base.rollbacks), (1, 0))
        i = base.evenements.index("DELETE quality")
        self.assertEqual(base.evenements[i + 1], "commit")      # la suppression et sa validation se suivent : une seule transaction

    def test_sans_element_hors_regle_aucune_suppression(self):
        self.preparer()
        _, _, _, base = self.lancer("purge", "--apply", base=FausseBase(0, contenu=0))
        self.assertEqual(base.suppressions_contenu(), [])
        self.assertEqual(base.commits, 0)

    def test_ordre_fichiers_laisses_tickets_contenu_puis_sauvegardes(self):
        self.preparer()
        vieux = self.sauvegarde(jours_avant(45), "rgpd")
        self.cache({"A-1": {"termine": True, "resolu": "2025-01-05T08:00:00.000+0000", "transitions": [], "vu_le": None}})
        observations = {}
        test = self

        class Observatrice(FausseBase):
            def execute(self, sql, params=()):
                if "DELETE" in sql.upper() and "quality." in sql:
                    observations["laisses_deja_supprimes"] = not test.historique.exists()
                    observations["tickets_deja_supprimes"] = "DELETE flow" in self.evenements
                    observations["dump_encore_la"] = (vieux / "flow.dump").exists()
                return super().execute(sql, params)

        base = Observatrice(3, jours_avant(400), contenu=2, contenu_plus_ancien=jours_avant(400))
        code, _, _, _ = self.lancer("purge", "--apply", base=base)
        self.assertEqual(code, 0)
        self.assertEqual(observations, {"laisses_deja_supprimes": True, "tickets_deja_supprimes": True, "dump_encore_la": True})
        self.assertFalse((vieux / "flow.dump").exists())
        self.assertEqual(base.commits, 2)                      # une transaction pour les tickets, une pour le contenu

    def test_echec_de_la_suppression_du_contenu_annule_et_donne_le_type_seul(self):
        self.preparer()
        vieux = self.sauvegarde(jours_avant(45), "rgpd")
        base = FausseBase(contenu=2, contenu_plus_ancien=jours_avant(400),
                          echec_suppression_contenu=ConnectionError("ZZKEY-5 zzequipe zztitre"))
        code, sortie, erreur, _ = self.lancer("purge", "--apply", base=base)
        self.assertEqual(code, 1)
        self.assertEqual((base.commits, base.rollbacks), (0, 1))
        self.assertIn("ConnectionError", erreur)
        for marque in ("ZZKEY", "zzequipe", "zztitre"):
            self.assertNotIn(marque, sortie + erreur)
        self.assertNotIn("purge done", sortie)
        self.assertTrue((vieux / "flow.dump").exists())         # l'étape suivante n'a pas eu lieu

    def test_refus_sans_sauvegarde_etiquetee_du_jour_inchange(self):
        avant = self.instantane()
        base = FausseBase(contenu=2)
        code, sortie, _, _ = self.lancer("purge", "--apply", "--language", "en", base=base)
        self.assertEqual(code, 3)
        self.assertIn("pre-purge backup missing: run the labelled backup first", sortie)
        self.assertEqual(base.requetes, [])                     # ni le comptage ni la suppression du contenu n'ont eu lieu
        self.assertEqual(self.instantane(), avant)

    def test_un_controle_apres_la_purge_sort_0_quand_le_magasin_est_vide(self):
        self.preparer()
        self.lancer("purge", "--apply", base=FausseBase(contenu=2))
        code, sortie, _, _ = self.lancer("check", "--language", "en", base=FausseBase())
        self.assertEqual(code, 0, sortie)


class RapportsDeQualiteHorsRegle(Espace):
    def test_un_vieux_rapport_n_est_ni_compte_ni_supprime(self):
        rapport = self.fichier(self.rapports, "qualite-stories-zzserie-2024-01-01.md", 800, "# Qualité des stories\n")
        octets = rapport.read_bytes()
        _, avant, _, _ = self.lancer("check", "--language", "en")
        code, apres, _, _ = self.lancer("check", "--language", "en")
        self.assertEqual(code, 0, apres)
        self.assertEqual(avant, apres)
        self.sauvegarde(AUJOURDHUI)
        self.lancer("purge", "--apply")
        self.assertTrue(rapport.exists())
        self.assertEqual(rapport.read_bytes(), octets)


if __name__ == "__main__":
    unittest.main()
