"""
Tests de tools/flow_views.py : seule porte de Claude Code vers les données Jira de la base.

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_views -v

Tickets et équipes inventés. Les tests avec base utilisent une base jetable (sautés si elle manque) : la connexion sous le rôle
pmzilla_flow_views est simulée par SET ROLE, le mot de passe réel du rôle n'est jamais utilisé.
"""
import contextlib
import io
import secrets
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(RACINE / "tests" / "db"))
import db  # noqa: E402
import flow_views as fv  # noqa: E402
from flow_views_messages import CATALOGS  # noqa: E402
from messages import Messages, check_catalogs  # noqa: E402

T = Messages(CATALOGS, "fr")
CONNECT_REEL = db.connect
try:
    import test_db as base      # noqa: E402  (base jetable partagée avec les tests de db.py)
except Exception:                # pragma: no cover
    base = None


class SansBase(unittest.TestCase):
    def test_catalogues_coherents(self):
        self.assertEqual(check_catalogs(CATALOGS), [])

    def test_seuil_jamais_sous_cinq(self):
        self.assertEqual(fv.seuil_effectif(5, None), 5)
        self.assertEqual(fv.seuil_effectif(5, 2), 5)
        self.assertEqual(fv.seuil_effectif(8, 6), 8)
        self.assertEqual(fv.seuil_effectif(5, 12), 12)
        self.assertEqual(fv.seuil_effectif(1, 0), 5)

    def test_reglage_du_fichier(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "flux.yaml"
            self.assertEqual(fv.seuil_configure(T, f), 5)                  # absent
            f.write_text("flow_views_min_cell: 8\n", encoding="utf-8")
            self.assertEqual(fv.seuil_configure(T, f), 8)
            f.write_text("flow_views_min_cell: 2\n", encoding="utf-8")
            self.assertEqual(fv.seuil_configure(T, f), 5)                  # jamais en dessous de 5
            f.write_text("flow_views_min_cell: beaucoup\n", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(fv.seuil_configure(T, f), 5)

    def test_masquage_et_rendu(self):
        self.assertEqual(fv.masquer(None, 5, T), "<5")
        self.assertEqual(fv.masquer(7, 10, T), "<10")
        self.assertEqual(fv.masquer(12, 10, T), "12")
        texte = fv.rendre(["team", "tickets"], [("Alpha", 12), ("Beta", None), ("Gamma", 7)], 10, T)
        self.assertIn("Alpha  12", texte)
        self.assertIn("Beta   <10", texte)
        self.assertIn("Gamma  <10", texte)
        self.assertEqual(fv.rendre(["team", "tickets"], [], 5, T), "(aucune ligne)")

    def test_vue_inconnue_refusee_avant_toute_connexion(self):
        for nom in ("flow.issues", "v_team_status; DROP TABLE x", "issues", ""):
            with self.assertRaises(ValueError):
                fv.lire(nom)
        with mock.patch.object(db, "connect", side_effect=AssertionError("pas de connexion")):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(fv.main(["show", "issues"]), 1)
            self.assertIn("Vue inconnue", err.getvalue())

    def test_connexion_sous_le_seul_role_des_vues(self):
        with mock.patch.object(db, "connect", side_effect=db.ErreurBase("injoignable")) as connexion:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(fv.main(["show", "v_team_status"]), 1)
            connexion.assert_called_once_with(role="pmzilla_flow_views")
            self.assertIn("injoignable", err.getvalue())

    def test_liste_des_vues(self):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            self.assertEqual(fv.main(["list"]), 0)
        for vue in fv.VUES:
            self.assertIn(vue, sortie.getvalue())

    def test_les_quatre_vues_sont_celles_de_la_migration(self):
        texte = (RACINE / "db" / "migrations" / "0002_flow_schema.sql").read_text(encoding="utf-8")
        for vue in fv.VUES:
            self.assertIn(f"CREATE VIEW flow.{vue} ", texte)


@unittest.skipIf(base is None, "tests/db/test_db.py introuvable")
class AvecBase(unittest.TestCase):
    def setUp(self):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        self.nom = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True)
        self.addCleanup(self._nettoyer)
        self.admin.execute(f'CREATE DATABASE "{self.nom}"')
        self.url = base.url_vers(self.nom)
        self.conn = db.connect(self.url, password=base.MOT_DE_PASSE)
        db.migrer(self.conn, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        self.conn.commit()
        self.conn.execute("SET ROLE pmzilla_flow")
        self.conn.execute("INSERT INTO flow.teams (name) VALUES ('Alpha'), ('Beta')")
        for i in range(12):
            self.conn.execute("INSERT INTO flow.issues (key, project, type, status, status_category, created_at, resolved_at, updated_at, team_id) "
                              "VALUES (%s, 'PROJ', 'Story', 'Closed', 'Done', now() - interval '20 days', now() - interval '2 days', now(), 1)",
                              (f"PROJ-{i}",))
        for i in range(12, 14):
            self.conn.execute("INSERT INTO flow.issues (key, project, type, status, status_category, created_at, updated_at, team_id) "
                              "VALUES (%s, 'PROJ', 'Story', 'Open', 'To Do', now(), now(), 2)", (f"PROJ-{i}",))
        self.conn.execute("RESET ROLE")
        self.conn.commit()

    def _nettoyer(self):
        with contextlib.suppress(Exception):
            self.conn.close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom}" WITH (FORCE)')
        self.admin.close()

    def connexion_simulee(self, **_):
        c = CONNECT_REEL(self.url, password=base.MOT_DE_PASSE, autocommit=True)
        c.execute("SET ROLE pmzilla_flow_views")
        return c

    def test_lecture_et_masquage_de_bout_en_bout(self):
        with mock.patch.object(db, "connect", side_effect=self.connexion_simulee):
            noms, lignes = fv.lire("v_team_status")
            self.assertEqual(noms, ["team", "type", "status_category", "status", "tickets"])
            sortie = io.StringIO()
            with contextlib.redirect_stdout(sortie):
                self.assertEqual(fv.main(["show", "v_team_status"]), 0)
            texte = sortie.getvalue()
            self.assertIn("Alpha", texte)
            self.assertRegex(texte, r"Alpha\s+Story\s+Done\s+Closed\s+12")
            self.assertRegex(texte, r"Beta\s+Story\s+To Do\s+Open\s+<5")      # 2 tickets : masqués
            self.assertNotIn("PROJ-", texte)
            sortie = io.StringIO()
            with contextlib.redirect_stdout(sortie):
                fv.main(["show", "v_team_status", "--min-cell", "20"])
            self.assertRegex(sortie.getvalue(), r"Alpha\s+Story\s+Done\s+Closed\s+<20")

    def test_le_chemin_de_lecture_ne_permet_pas_de_lire_une_table(self):
        c = self.connexion_simulee()
        with self.assertRaises(db.psycopg.errors.InsufficientPrivilege):
            c.execute("SELECT key FROM flow.issues")
        c.close()


if __name__ == "__main__":
    unittest.main()
