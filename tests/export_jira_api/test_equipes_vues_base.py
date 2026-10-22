"""Lecteur des équipes vues de check-teams sur la base jetable (change database-only, D13, tâche 14.1, partie avec base) : sauté sans elle
(bash tools/dbtest.sh export_jira_api), écrit pour être exécuté par l'auteur.

    bash tools/dbtest.sh export_jira_api

Le vrai lecteur (export_jira_api_equipes.lire_equipes_vues) se connecte comme les lecteurs des rapports (flow_store.ouvrir : rôle en
lecture seule) et ne lit que la vue flow.v_team_tickets_seen, jamais une table de flow. Données inventées (équipes Alpha et Beta).
"""
import importlib.util
import sys
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("aide_base_flow_store", ICI.parent / "flow_store" / "aide_base.py")
aide = importlib.util.module_from_spec(_spec)           # la base jetable de flow_store, sans mettre son dossier sur le chemin d'import
_spec.loader.exec_module(aide)
sys.path.insert(0, str(ICI.parents[1] / "tools"))
import db  # noqa: E402
import export_jira_api_equipes as eq  # noqa: E402


class ConnexionEnregistreuse:
    """Délègue à la vraie connexion et note le rôle courant et chaque requête exécutée."""

    def __init__(self, vraie, journal):
        self._vraie, self.journal = vraie, journal

    def execute(self, sql, *args, **kw):
        self.journal.append((self._vraie.execute("SELECT current_user").fetchone()[0], sql))
        return self._vraie.execute(sql, *args, **kw)

    def __getattr__(self, nom):
        return getattr(self._vraie, nom)


class LecteurSurLaBase(aide.AvecBase):
    def jeu(self):
        c = db.connect(self.url, password=aide.MOT_DE_PASSE)
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.teams (name) VALUES ('Alpha'), ('Beta')")
        for cle, sortie in (("PROJ-1", False), ("PROJ-2", True), ("PROJ-3", False)):
            c.execute("INSERT INTO flow.issues (key, project, type, status, created_at, updated_at, team_id, out_of_export_at) "
                      "VALUES (%s, 'PROJ', 'Story', 'Open', now(), now(), 1, CASE WHEN %s THEN now() END)", (cle, sortie))
        c.execute("INSERT INTO flow.issue_teams (issue_key, team_id, position) VALUES "
                  "('PROJ-1', 1, 1), ('PROJ-2', 1, 1), ('PROJ-3', 1, 1), ('PROJ-3', 2, 2)")
        c.commit()
        c.close()

    def test_le_lecteur_rend_les_decomptes_de_la_vue_sous_le_role_en_lecture_seule_et_ne_lit_que_la_vue(self):
        self.jeu()
        journal = []
        vues = eq.lire_equipes_vues(ouvrir=lambda: ConnexionEnregistreuse(self._ouvrir_comme_les_lecteurs(), journal))
        self.assertEqual(vues, {"Alpha": 2, "Beta": 1})            # le ticket sorti de l'export est écarté, un ticket à deux équipes compte deux fois
        roles = {role for role, _ in journal}
        self.assertEqual(roles, {"pmzilla_flow_ro"})
        self.assertEqual([sql for _, sql in journal], [eq.REQUETE_EQUIPES_VUES])

    def _ouvrir_comme_les_lecteurs(self):
        import flow_store
        return flow_store.ouvrir()

    def test_le_lecteur_par_defaut_se_connecte_comme_les_lecteurs_des_rapports(self):
        self.jeu()
        self.assertEqual(eq.lire_equipes_vues(), {"Alpha": 2, "Beta": 1})      # l'adresse et le mot de passe viennent de l'environnement du test

    def test_base_vide_rend_un_dictionnaire_vide(self):
        self.assertEqual(eq.lire_equipes_vues(), {})

    def test_la_vue_refuse_les_tables_au_role_en_lecture_seule_n_est_pas_utilisee(self):
        """Le lecteur n'a besoin d'aucune table : même sans droit sur flow.issues, la vue répond (elle s'exécute avec les droits du propriétaire)."""
        self.jeu()
        self.conn.execute("REVOKE SELECT ON flow.issues, flow.issue_teams, flow.teams FROM pmzilla_flow_ro")
        self.conn.commit()
        self.assertEqual(eq.lire_equipes_vues(), {"Alpha": 2, "Beta": 1})

    def test_base_injoignable_leve_sans_detail(self):
        def echoue():
            raise db.ErreurBase("mot de passe absent")
        with self.assertRaises(eq.EquipesVuesInjoignables):
            eq.lire_equipes_vues(ouvrir=echoue)


if __name__ == "__main__":
    unittest.main()
