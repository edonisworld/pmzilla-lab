"""Export et couche brute sur la base jetable, sous le rôle d'import (change jira-data-architecture, D3, D4, D13 ; specs jira-flow-export
et jira-flow-raw-layer). Tâche 4.5, partie avec base : sautée sans elle (bash tools/dbtest.sh export_jira_api), écrite pour être
exécutée par l'auteur.

    bash tools/dbtest.sh export_jira_api

Faux serveur Jira (test_export_jira_api.py) et vraie base : un export écrit les passages, les visites et les instantanés avec le vrai
magasin (flow_raw.MagasinBase) ; une erreur de la base ou un échec de la validation ne laisse ni passage ni fichier. Données inventées.
"""
import importlib.util
import unittest
from pathlib import Path
from unittest import mock

ICI = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("aide_base_flow_store", ICI.parent / "flow_store" / "aide_base.py")
aide = importlib.util.module_from_spec(_spec)           # la base jetable de flow_store, sans mettre son dossier sur le chemin d'import
_spec.loader.exec_module(aide)
from test_couche_brute import CHAMP, REFERENTIEL, champs, ex, modifie, objet, trois_tickets  # noqa: E402  (champs, objet, modifie : types d'équipe)
from test_export_jira_api import Base  # noqa: E402
import db  # noqa: E402
import flow_raw  # noqa: E402


class ConnexionQuiEchoueALaValidation:
    """Une connexion dont la validation (commit) échoue : tout le reste est délégué."""

    def __init__(self, vraie):
        self._vraie = vraie

    def commit(self):
        raise RuntimeError("echec de la validation")

    def __getattr__(self, nom):
        return getattr(self._vraie, nom)


class ExportEnBase(aide.AvecBase, Base):
    def setUp(self):
        aide.AvecBase.setUp(self)
        self.url_base = self.url              # Base.setUp réutilise le nom « url » pour l'adresse du faux Jira
        Base.setUp(self)
        self.faux.tickets = trois_tickets()
        self.ecrire_reglages(f"export_team_field: {CHAMP}\njql_exports:\n  a: project = AAA\n  b: project = BBB\n")
        self.exports = self.ws / "Flux-Lab" / "exports"
        self.connexions = []
        self.roles = []                       # rôle courant de chaque connexion de l'export, lu à l'ouverture
        self.enveloppe = lambda connexion: connexion
        patch = mock.patch.object(ex, "ouvrir_magasin", self.ouvrir)
        patch.start()
        self.addCleanup(patch.stop)

    def ouvrir(self):
        connexion = db.connect(self.url_base, password=aide.MOT_DE_PASSE)
        self.connexions.append(connexion)
        connexion.execute("SET ROLE pmzilla_flow")
        # Le rôle se lit ici, sur la connexion ouverte : l'export ferme le magasin (donc la connexion) dans son « finally ».
        self.roles.append(connexion.execute("SELECT current_user").fetchone()[0])
        return flow_raw.MagasinBase(self.enveloppe(connexion))

    def compte(self, table):
        self.conn.rollback()
        return self.conn.execute(f"SELECT count(*) FROM flow.{table}").fetchone()[0]

    def fichiers(self):
        return sorted(p.name for p in self.exports.glob("*")) if self.exports.exists() else []

    def test_un_export_ecrit_le_passage_les_visites_et_les_instantanes(self):
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.conn.execute("SELECT kind, queries_searched, all_queries FROM flow.raw_runs").fetchall(),
                         [("export", 2, True)])
        self.assertEqual(self.compte("raw_run_sightings"), 3)
        self.assertEqual(self.compte("raw_issue_snapshots"), 3)
        self.assertEqual(self.fichiers(), [])                  # aucun fichier (database-only, D1)
        self.assertEqual(self.roles, ["pmzilla_flow"])        # l'export écrit sous le rôle d'import, sur une seule connexion

    def test_deuxieme_export_sans_changement_et_un_champ_qui_change(self):
        self.lancer("export")
        self.lancer("export")
        self.assertEqual((self.compte("raw_runs"), self.compte("raw_run_sightings"), self.compte("raw_issue_snapshots")), (2, 6, 3))
        self.faux.tickets["ABC-2"]["status"] = {"name": "Closed", "statusCategory": {"name": "Done"}}
        self.faux.tickets["ABC-2"]["updated"] = "2026-10-01T10:00:00.000+0200"
        self.lancer("export")
        self.assertEqual(self.compte("raw_issue_snapshots"), 4)

    def test_equipes_avec_identifiants_en_json(self):
        self.ecrire_reglages(f"export_team_field: {CHAMP}\njql_export: project = ABC\n")
        (self.ws / "Flux-Lab" / "organisation.yaml").write_text(REFERENTIEL, encoding="utf-8")
        ticket = modifie(champs("Story", "Open", "To Do", "2026-09-01T16:45:00.000+0200"))
        ticket[CHAMP] = [objet(2), objet(9)]
        self.faux.tickets = {"ABC-1": ticket}
        self.assertEqual(self.lancer("export")[0], 0)
        equipes = self.conn.execute("SELECT teams FROM flow.raw_issue_snapshots").fetchone()[0]
        self.assertEqual([(e["name"], e["jira_team_id"]) for e in equipes], [("Equipe B", "2"), ("(équipe inconnue)", "9")])

    def test_erreur_de_base_pendant_l_ecriture_ne_laisse_ni_passage_ni_fichier(self):
        with mock.patch.object(flow_raw, "_parametres_instantane", side_effect=RuntimeError("ZZSECRET-ABC-1")):
            code, sortie = self.lancer("export")
        self.assertEqual(code, 1, sortie)
        self.assertIn("RuntimeError", sortie)
        self.assertNotIn("ZZSECRET", sortie)
        self.assertEqual((self.compte("raw_runs"), self.compte("raw_run_sightings"), self.compte("raw_issue_snapshots")), (0, 0, 0))
        self.assertEqual(self.fichiers(), [])

    def test_echec_de_la_validation_ne_laisse_ni_passage_ni_fichier(self):
        self.enveloppe = ConnexionQuiEchoueALaValidation
        code, sortie = self.lancer("export")
        self.assertEqual(code, 1, sortie)
        self.assertEqual((self.compte("raw_runs"), self.compte("raw_issue_snapshots")), (0, 0))
        self.assertEqual(self.fichiers(), [])

    def test_la_connexion_est_fermee(self):
        self.lancer("export")
        self.assertTrue(all(c.closed for c in self.connexions))

    # --- type d'équipe (database-only, complément « Complement: team type column »), sur la vraie base
    def ecrire_sources_de_type(self, type_alpha: str = "Development Team") -> None:
        flux = self.ws / "Flux-Lab"
        (flux / "equipes-jira.yaml").write_text(
            f"teams:\n  - name: Alpha\n    jira_team_ids: ['1']\n    type: {type_alpha}\n"
            "  - name: Beta\n    jira_team_ids: ['2']\n    type: Verification Team\n", encoding="utf-8")
        self.ecrire_reglages(f"export_team_field: {CHAMP}\njql_export: project = ABC\n")
        self.faux.tickets = {}
        for cle, ids in (("ABC-1", [1]), ("ABC-2", [2]), ("ABC-3", [9])):
            ticket = modifie(champs("Story", "Open", "To Do", "2026-09-01T16:45:00.000+0200"))
            ticket[CHAMP] = [objet(i) for i in ids]
            self.faux.tickets[cle] = ticket

    def types_en_base(self) -> dict:
        self.conn.rollback()
        return dict(self.conn.execute("SELECT name, team_type FROM flow.teams").fetchall())

    def test_le_type_s_ecrit_dans_la_transaction_et_l_inconnu_garde_un_type_nul(self):
        self.ecrire_sources_de_type()
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.types_en_base(), {"Alpha": "Development Team", "Beta": "Verification Team", "(équipe inconnue)": None})
        self.assertIn("équipes sans type : 1", sortie)
        for interdit in ("Alpha", "Beta", "Development Team"):
            self.assertNotIn(interdit, sortie)

    def test_un_type_qui_change_met_a_jour_seulement_cette_equipe(self):
        self.ecrire_sources_de_type()
        self.lancer("export")
        self.ecrire_sources_de_type("Other Team")
        self.lancer("export")
        self.assertEqual(self.types_en_base(), {"Alpha": "Other Team", "Beta": "Verification Team", "(équipe inconnue)": None})

    def test_une_erreur_de_base_ne_laisse_ni_equipe_ni_type(self):
        self.ecrire_sources_de_type()
        with mock.patch.object(flow_raw, "_parametres_instantane", side_effect=RuntimeError("ZZSECRET")):
            code, _ = self.lancer("export")
        self.assertEqual(code, 1)
        self.assertEqual(self.types_en_base(), {})


if __name__ == "__main__":
    unittest.main()
