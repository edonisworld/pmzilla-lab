"""Dérivation depuis la couche brute sur la base jetable, sous le rôle d'import (change database-only, D4 ; spec jira-flow-import). Tâche 4.4,
partie avec base : sautée sans elle (bash tools/dbtest.sh flow_import), écrite pour être exécutée par l'auteur.

    bash tools/dbtest.sh flow_import

L'écriture de l'export est rejouée sans Jira : les instantanés sont écrits par flow_raw.MagasinBase sous le rôle d'import, puis
flow_raw.deriver (ce que flow_import.py appelle) dérive les tables courantes. Données inventées (tickets PROJ-n, équipes Alpha et Beta).
"""
import datetime as dt
import importlib.util
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("aide_base_flow_store", ICI.parent / "flow_store" / "aide_base.py")
aide = importlib.util.module_from_spec(_spec)           # la base jetable de flow_store, sans mettre son dossier sur le chemin d'import
_spec.loader.exec_module(aide)
import db  # noqa: E402
import flow_raw  # noqa: E402

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
T1 = dt.datetime(2026, 10, 1, 10, 0, tzinfo=UTC)
MAINTENANT = dt.datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def instantane(cle, **valeurs):
    base = {"issue_key": cle, "project": "PROJ", "type": "Story", "status": "Open", "status_category": "To Do",
            "created_at": T0, "resolved_at": None, "resolution": None, "status_category_changed_at": None,
            "story_points": None, "updated_at": T1, "parent_key": None,
            "teams": [{"name": "Alpha", "jira_team_id": "1"}], "links": []}
    base.update(valeurs)
    base["content_hash"] = flow_raw.empreinte(base)
    return base


class DerivationEnBase(aide.AvecBase):
    def setUp(self):
        aide.AvecBase.setUp(self)
        self.role = db.connect(self.url, password=aide.MOT_DE_PASSE)
        self.role.execute("SET ROLE pmzilla_flow")
        self.addCleanup(self.role.close)

    def exporter(self, cles, toutes=True, **valeurs):
        """Un passage d'export qui voit `cles` (et écrit leur instantané)."""
        flow_raw.MagasinBase(self.role).enregistrer(genre="export", nb_requetes=2, toutes=toutes, vus=list(cles),
                                                    instantanes={c: instantane(c, **valeurs) for c in cles})

    def deriver(self, **options):
        return flow_raw.deriver(self.role, maintenant=MAINTENANT, **options)

    def un(self, sql, params=None):
        self.conn.rollback()
        return self.conn.execute(sql, params).fetchone()

    def test_un_passage_est_applique_puis_un_second_import_ne_trouve_rien(self):
        self.exporter(["PROJ-1", "PROJ-2"])
        premier = self.deriver()
        self.assertFalse(premier["rien"])
        self.assertEqual((premier["compares"], premier["inseres"], premier["modifies"], premier["inchanges"]), (2, 2, 0, 0))
        self.assertEqual(self.un("SELECT count(*) FROM flow.issues")[0], 2)
        self.assertEqual(self.un("SELECT count(*) FROM flow.issue_teams")[0], 2)
        second = self.deriver()
        self.assertTrue(second["rien"])
        self.assertEqual((second["inseres"], second["modifies"], second["marques"], second["revenus"]), (0, 0, 0, 0))

    def test_un_champ_modifie_dans_le_dernier_passage_est_mis_a_jour(self):
        self.exporter(["PROJ-1"])
        self.deriver()
        flow_raw.MagasinBase(self.role).enregistrer(genre="export", nb_requetes=2, toutes=True, vus=["PROJ-1"], instantanes={
            "PROJ-1": instantane("PROJ-1", status="Done", updated_at=T1 + dt.timedelta(days=1))})
        resultat = self.deriver()
        self.assertEqual((resultat["inseres"], resultat["modifies"]), (0, 1))
        self.assertEqual(self.un("SELECT status FROM flow.issues WHERE key = 'PROJ-1'")[0], "Done")

    def test_essai_a_blanc_n_ecrit_rien(self):
        self.exporter(["PROJ-1"])
        resultat = self.deriver(appliquer=False)
        self.assertEqual(resultat["inseres"], 1)
        self.assertEqual(self.un("SELECT count(*) FROM flow.issues")[0], 0)

    def test_ticket_absent_du_jeu_complet_marque_avec_l_option_et_jamais_sans(self):
        self.exporter(["PROJ-1", "PROJ-2"])
        self.deriver()
        self.exporter(["PROJ-1"])
        sans = self.deriver()
        self.assertEqual(sans["marques"], 0)                                   # sans l'option, aucune marque
        self.assertIsNone(self.un("SELECT out_of_export_at FROM flow.issues WHERE key = 'PROJ-2'")[0])
        avec = self.deriver(marquer_absents=True, seuil_pourcent=100)
        self.assertEqual(avec["marques"], 1)
        self.assertEqual(self.un("SELECT out_of_export_at FROM flow.issues WHERE key = 'PROJ-2'")[0], MAINTENANT)
        self.assertIsNone(self.un("SELECT out_of_export_at FROM flow.issues WHERE key = 'PROJ-1'")[0])

    def test_une_marque_existante_n_est_pas_deplacee(self):
        self.exporter(["PROJ-1", "PROJ-2"])
        self.deriver()
        self.exporter(["PROJ-1"])
        self.deriver(marquer_absents=True, seuil_pourcent=100)
        plus_tard = dt.datetime(2026, 10, 25, tzinfo=UTC)
        flow_raw.deriver(self.role, marquer_absents=True, seuil_pourcent=100, maintenant=plus_tard)
        self.assertEqual(self.un("SELECT out_of_export_at FROM flow.issues WHERE key = 'PROJ-2'")[0], MAINTENANT)

    def test_ticket_marque_qui_revient_perd_sa_marque_meme_sans_l_option(self):
        self.exporter(["PROJ-1", "PROJ-2"])
        self.deriver()
        self.exporter(["PROJ-1"])
        self.deriver(marquer_absents=True, seuil_pourcent=100)
        self.exporter(["PROJ-1", "PROJ-2"])
        resultat = self.deriver()
        self.assertEqual(resultat["revenus"], 1)
        self.assertIsNone(self.un("SELECT out_of_export_at FROM flow.issues WHERE key = 'PROJ-2'")[0])

    def marquer_disparu(self, cle, compteur=3):
        self.role.execute("UPDATE flow.issues SET history_not_found = %s, history_gone_at = now() WHERE key = %s", (compteur, cle))
        self.role.commit()

    def suivi(self, cle):
        return self.un("SELECT history_not_found, history_gone_at IS NOT NULL FROM flow.issues WHERE key = %s", (cle,))

    def test_ticket_disparu_revu_par_l_export_perd_sa_marque_avec_ou_sans_l_option(self):
        """D15 complété : compteur à 0 et instant effacé pour un ticket marqué disparu que le dernier passage revoit ; transitions
        et périodes intactes ; le compteur d'un ticket non marqué disparu reste ; un ticket disparu non revu garde sa marque."""
        for options in ({}, {"marquer_absents": True, "seuil_pourcent": 100}):
            self.exporter(["PROJ-1", "PROJ-2", "PROJ-3"])
            self.deriver()
            self.role.execute("INSERT INTO flow.transitions (issue_key, transitioned_at, from_status, to_status) "
                              "VALUES ('PROJ-1', %s, NULL, 'Open') ON CONFLICT DO NOTHING", (T0,))
            self.marquer_disparu("PROJ-1")
            self.role.execute("UPDATE flow.issues SET history_not_found = 2 WHERE key = 'PROJ-2'")           # pas disparu : compteur 2
            self.marquer_disparu("PROJ-3")
            self.exporter(["PROJ-1", "PROJ-2"])                                                              # PROJ-3 n'est pas revu
            resultat = self.deriver(**options)
            self.assertEqual(resultat["disparus_revus"], 1, options)
            self.assertEqual(self.suivi("PROJ-1"), (0, False), options)
            self.assertEqual(self.suivi("PROJ-2"), (2, False), options)
            self.assertEqual(self.suivi("PROJ-3"), (3, True), options)
            self.assertEqual(self.un("SELECT count(*) FROM flow.transitions WHERE issue_key = 'PROJ-1'")[0], 1)
            self.role.execute("UPDATE flow.issues SET history_not_found = 0, history_gone_at = NULL")
            self.role.commit()

    def test_essai_a_blanc_compte_les_disparus_revus_sans_effacer_la_marque(self):
        self.exporter(["PROJ-1"])
        self.deriver()
        self.marquer_disparu("PROJ-1")
        self.exporter(["PROJ-1"])
        resultat = self.deriver(appliquer=False)
        self.assertEqual(resultat["disparus_revus"], 1)
        self.assertEqual(self.suivi("PROJ-1"), (3, True))

    def test_jeu_incomplet_refuse_sans_rien_ecrire(self):
        self.exporter(["PROJ-1", "PROJ-2"])
        self.deriver()
        self.exporter(["PROJ-1"], toutes=False)                                # une seule requête nommée lue : jeu incomplet
        with self.assertRaises(flow_raw.RefusDerivation) as contexte:
            self.deriver(marquer_absents=True, seuil_pourcent=100)
        self.assertEqual(contexte.exception.code, "incomplete_set")
        self.assertIsNone(self.un("SELECT out_of_export_at FROM flow.issues WHERE key = 'PROJ-2'")[0])

    def test_export_vide_refuse(self):
        self.exporter(["PROJ-1"])
        self.deriver()
        flow_raw.MagasinBase(self.role).enregistrer(genre="export", nb_requetes=2, toutes=True, vus=[], instantanes={})
        with self.assertRaises(flow_raw.RefusDerivation) as contexte:
            self.deriver(marquer_absents=True)
        self.assertEqual(contexte.exception.code, "empty_export")

    def test_trop_d_absents_refuse_sans_rien_marquer(self):
        self.exporter(["PROJ-1", "PROJ-2", "PROJ-3", "PROJ-4"])
        self.deriver()
        self.exporter(["PROJ-1", "PROJ-2"])
        with self.assertRaises(flow_raw.RefusDerivation) as contexte:
            self.deriver(marquer_absents=True, seuil_pourcent=20)
        self.assertEqual(contexte.exception.code, "absent_share_exceeded")
        self.assertEqual(self.un("SELECT count(*) FROM flow.issues WHERE out_of_export_at IS NOT NULL")[0], 0)

    def test_ticket_resolu_au_dela_de_la_conservation_ignore_et_compte(self):
        flow_raw.MagasinBase(self.role).enregistrer(genre="export", nb_requetes=2, toutes=True, vus=["PROJ-1", "PROJ-2"], instantanes={
            "PROJ-1": instantane("PROJ-1"),
            "PROJ-2": instantane("PROJ-2", resolved_at=dt.datetime(2024, 1, 1, tzinfo=UTC))})
        resultat = self.deriver(retention_jours=365)
        self.assertEqual((resultat["compares"], resultat["hors_conservation"]), (1, 1))
        self.assertEqual(self.un("SELECT count(*) FROM flow.issues")[0], 1)

    def test_equipes_et_liens_comptes(self):
        self.exporter(["PROJ-1"], links=[{"target": "PROJ-2", "type": "Blocks", "direction": "outward"}],
                      teams=[{"name": "Alpha", "jira_team_id": "1"}, {"name": "Gamma", "jira_team_id": None}])
        resultat = self.deriver()
        self.assertEqual((resultat["equipes"], resultat["liens_ajoutes"], resultat["liens_retires"]), (2, 1, 0))
        self.assertEqual(self.un("SELECT target_key FROM flow.links WHERE source_key = 'PROJ-1'")[0], "PROJ-2")

    def test_une_erreur_annule_toute_la_derivation(self):
        self.exporter(["PROJ-1"])
        with self.assertRaises(Exception):
            flow_raw.deriver(self.role, maintenant="pas un instant", marquer_absents=True, seuil_pourcent=100)
        self.assertEqual(self.un("SELECT count(*) FROM flow.issues")[0], 0)

    def test_l_import_ne_touche_ni_transitions_ni_indicateur_ni_periodes(self):
        self.exporter(["PROJ-1"])
        self.deriver()
        self.assertEqual(self.un("SELECT count(*) FROM flow.transitions")[0], 0)
        self.assertEqual(self.un("SELECT bool_or(has_history) FROM flow.issues")[0], False)
        self.assertEqual(self.un("SELECT count(*) FROM flow.issue_label_periods")[0], 0)


if __name__ == "__main__":
    unittest.main()
