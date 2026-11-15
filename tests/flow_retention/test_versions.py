"""
Références de version et sprints dans `flow_retention.py` (change jira-delivery-fields, D10 ; spec jira-flow-retention « Version references under
the rule », « Delivery rows follow their ticket », « Retention check store lines »). Suite : tests/flow_retention.

La base est la FAUSSE connexion de aide_flow_retention.py (comptes choisis, journal des requêtes) : l'horloge SQL et les cascades sont prouvées sur
une vraie base par le dbtest de l'auteur. Données inventées ; aucune ligne ne porte un numéro, un nom court ni un identifiant d'objet.
"""
import unittest

from aide_flow_retention import AUJOURDHUI, Espace, FausseBase, jours_avant


class LigneDesReferences(Espace):
    def test_une_reference_hors_regle_code_4_et_ligne_fixe(self):
        code, sortie, erreur, _ = self.lancer("check", "--language", "en", base=FausseBase(versions=1))
        self.assertEqual(code, 4, erreur)
        self.assertIn("version references: 1 out of rule", sortie)
        self.assertTrue(sortie.rstrip().endswith("retention check: 1 items out of rule"), sortie)

    def test_en_francais(self):
        code, sortie, _, _ = self.lancer("check", base=FausseBase(versions=2))
        self.assertEqual(code, 4)
        self.assertIn("références de versions : 2 hors règle", sortie)

    def test_les_instantanes_de_version_trop_anciens_comptent_sur_la_meme_ligne(self):
        _, sortie, _, _ = self.lancer("check", "--language", "en", base=FausseBase(instantanes_de_version=2))
        self.assertIn("version references: 2 out of rule", sortie)

    def test_ligne_a_zero_juste_apres_le_contenu_des_stories(self):
        code, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertEqual(code, 0)
        lignes = sortie.splitlines()
        self.assertEqual(lignes.index("version references: 0 out of rule"), lignes.index("story content: 0 items out of rule") + 1)

    def test_les_references_s_ajoutent_au_total(self):
        _, sortie, _, _ = self.lancer("check", "--language", "en", base=FausseBase(3, jours_avant(400), contenu=4, versions=2))
        self.assertTrue(sortie.rstrip().endswith("retention check: 9 items out of rule"), sortie)

    def test_les_requetes_portent_les_dates_limites_et_aucune_valeur(self):
        base = FausseBase(versions=1)
        _, sortie, _, _ = self.lancer("check", "--language", "en", base=base)
        comptes = [r for r in base.requetes if "release_versions" in r[0] and r[0].upper().startswith("SELECT COUNT")]
        self.assertEqual(len(comptes), 2)
        self.assertEqual(comptes[0][1], (jours_avant(365),))
        for sql, _ in comptes:
            self.assertIn("issue_current_asset_versions", sql)
            self.assertIn("issue_asset_version_periods", sql)
        self.assertNotIn("zz", sortie.lower())


class Purge(Espace):
    def test_sans_apply_rien_n_est_supprime(self):
        base = FausseBase(versions=1)
        code, sortie, _, _ = self.lancer("purge", "--language", "en", base=base)
        self.assertEqual(code, 0)
        self.assertIn("dry run: nothing deleted", sortie)
        self.assertEqual([r for r in base.requetes if r[0].upper().startswith("DELETE")], [])

    def test_apply_supprime_les_references_dans_la_transaction_apres_les_tickets(self):
        self.sauvegarde(AUJOURDHUI)
        base = FausseBase(3, jours_avant(400), versions=1)
        code, sortie, erreur, _ = self.lancer("purge", "--apply", "--language", "en", base=base)
        self.assertEqual(code, 0, erreur)
        suppressions = [r[0] for r in base.requetes if r[0].upper().startswith("DELETE")]
        tickets = next(i for i, s in enumerate(suppressions) if s.startswith("DELETE FROM flow.issues"))
        sprints = next(i for i, s in enumerate(suppressions) if s.startswith("DELETE FROM flow.sprints"))
        versions = next(i for i, s in enumerate(suppressions) if s.startswith("DELETE FROM flow.release_versions"))
        self.assertLess(tickets, sprints)
        self.assertLess(tickets, versions)
        self.assertEqual(base.commits, 1)          # une seule transaction de flow
        self.assertEqual(sum(1 for s in suppressions if "flow.raw_version_snapshots" in s), 2)          # orphelins, puis anciens des gardées

    def test_les_references_seules_declenchent_la_transaction_sans_supprimer_de_ticket(self):
        self.sauvegarde(AUJOURDHUI)
        base = FausseBase(versions=1)
        code, _, erreur, _ = self.lancer("purge", "--apply", base=base)
        self.assertEqual(code, 0, erreur)
        self.assertEqual(base.suppressions(), [])
        self.assertTrue(any(r[0].startswith("DELETE FROM flow.release_versions") for r in base.requetes))
        self.assertFalse(any(r[0].startswith("DELETE FROM flow.sprints") for r in base.requetes))          # aucun ticket supprimé : sprints intacts

    def test_une_reference_encore_portee_n_est_jamais_supprimee(self):
        base = FausseBase(versions=1)
        self.sauvegarde(AUJOURDHUI)
        self.lancer("purge", "--apply", base=base)
        suppressions = [sql for sql, _ in base.requetes if sql.startswith("DELETE FROM flow.release_versions")]
        self.assertEqual(len(suppressions), 1)
        for sql in suppressions:
            self.assertIn("NOT EXISTS", sql)
            self.assertIn("issue_current_asset_versions", sql)
            self.assertIn("issue_asset_version_periods", sql)

    def test_un_sprint_n_est_orphelin_que_sans_ticket_courant_ni_periode(self):
        # R-20261102-41 (Q328)
        self.sauvegarde(AUJOURDHUI)
        base = FausseBase(3, jours_avant(400))
        self.lancer("purge", "--apply", base=base)
        sprints = [r[0] for r in base.requetes if r[0].startswith("DELETE FROM flow.sprints")]
        self.assertEqual(len(sprints), 1)
        self.assertIn("flow.issue_current_sprints", sprints[0])
        self.assertIn("flow.issue_sprint_periods", sprints[0])
        self.assertEqual(sprints[0].count("NOT EXISTS"), 2)

    def test_le_dernier_instantane_de_chaque_objet_est_conserve(self):
        base = FausseBase(instantanes_de_version=1)
        self.sauvegarde(AUJOURDHUI)
        self.lancer("purge", "--apply", base=base)
        anciens = [r[0] for r in base.requetes if r[0].startswith("DELETE FROM flow.raw_version_snapshots s")]
        self.assertEqual(len(anciens), 1)
        self.assertIn("s.run_id < (SELECT max(x.run_id)", anciens[0])

    def test_echec_annule_tout_et_ne_montre_aucune_valeur(self):
        base = FausseBase(versions=1, echec_suppression=RuntimeError("zzversion zzcle"))
        self.sauvegarde(AUJOURDHUI)
        code, sortie, erreur, _ = self.lancer("purge", "--apply", base=base)
        self.assertEqual(code, 1)
        self.assertNotIn("zz", (sortie + erreur).lower())
        self.assertEqual(base.rollbacks, 1)


if __name__ == "__main__":
    unittest.main()
