"""
Tests de `flow_retention.py` avec une vraie base jetable (même mécanisme que tests/flow_import : base pmzilla_test_<hex> créée, migrée
(0008 comprise), puis supprimée). SAUTÉS sans Docker : à faire tourner par l'utilisateur (bash tools/dbtest.sh flow_retention).

Couvre ce que la fausse connexion ne prouve pas : horloge SQL d'un ticket (résolu / sorti de l'export / encore dans l'export), suppression
en cascade des équipes, transitions, liens et périodes, droits du rôle d'import, annulation d'une transaction qui échoue. Données inventées.
"""
import contextlib
import io
import secrets
import sys
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / "db"))
import test_db as base     # noqa: E402
from test_db import db     # noqa: E402

from aide_flow_retention import AUJOURDHUI, Espace, fr  # noqa: E402


class AvecBase(Espace):
    def setUp(self):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        super().setUp()
        self.nom_base = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True)
        self.addCleanup(self._supprimer)
        self.admin.execute(f'CREATE DATABASE "{self.nom_base}"')
        self.url = base.url_vers(self.nom_base)
        self.conn = db.connect(self.url, password=base.MOT_DE_PASSE)
        db.migrer(self.conn, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        self.conn.commit()
        self.conn.execute("SET ROLE pmzilla_flow")
        self.conn.execute("INSERT INTO flow.teams (name) VALUES ('Alpha')")
        self.sauvegarde(AUJOURDHUI)

    def _supprimer(self):
        with contextlib.suppress(Exception):
            self.conn.close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom_base}" WITH (FORCE)')
        self.admin.close()

    def ticket(self, cle, resolu=None, sorti=None, jours_resolu=None, jours_sorti=None):
        self.conn.execute(
            "INSERT INTO flow.issues (key, project, type, status, status_category, created_at, resolved_at, out_of_export_at, updated_at, team_id) "
            "VALUES (%s, 'PROJ', 'Story', 'X', 'Done', '2020-01-01', "
            "CASE WHEN %s::int IS NULL THEN NULL ELSE %s::timestamptz - make_interval(days => %s::int) END, "
            "CASE WHEN %s::int IS NULL THEN NULL ELSE %s::timestamptz - make_interval(days => %s::int) END, now(), "
            "(SELECT id FROM flow.teams LIMIT 1))",
            (cle, jours_resolu, f"{AUJOURDHUI}T12:00:00+00", jours_resolu, jours_sorti, f"{AUJOURDHUI}T12:00:00+00", jours_sorti))
        self.conn.commit()

    def ouvrir(self):
        conn = db.connect(self.url, password=base.MOT_DE_PASSE)
        conn.cursor().execute(f"SET ROLE {fr.ROLE}")
        return conn

    def lancer_base(self, *argv):
        sortie, erreur = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            code = fr.main(list(argv), self.environ, ouvrir_base=self.ouvrir)
        return code, sortie.getvalue(), erreur.getvalue()

    def cles(self):
        return sorted(r[0] for r in self.conn.execute("SELECT key FROM flow.issues").fetchall())


class HorlogeEtCascade(AvecBase):
    def test_horloge_des_trois_cas(self):
        self.ticket("PROJ-1", jours_resolu=400)                   # résolu depuis longtemps : hors règle
        self.ticket("PROJ-2", jours_resolu=10)                    # résolu récemment
        self.ticket("PROJ-3", jours_sorti=400)                    # ouvert, sorti de l'export depuis longtemps : hors règle
        self.ticket("PROJ-4", jours_sorti=5)                      # ouvert, sorti récemment
        self.ticket("PROJ-5")                                     # ouvert encore dans l'export, créé en 2020 : jamais hors règle
        code, sortie, erreur = self.lancer_base("check", "--language", "en")
        self.assertEqual(code, 4, erreur)
        self.assertIn("database, tickets past the rule: 2", sortie)
        self.assertTrue(sortie.rstrip().endswith("retention check: 2 items out of rule"))

    def test_purge_supprime_en_cascade_et_garde_les_autres(self):
        self.ticket("PROJ-1", jours_resolu=400)
        self.ticket("PROJ-2", jours_resolu=10)
        self.conn.execute("INSERT INTO flow.issue_teams (issue_key, team_id, position) SELECT 'PROJ-1', id, 1 FROM flow.teams")
        self.conn.execute("INSERT INTO flow.transitions (issue_key, transitioned_at, from_status, to_status) VALUES ('PROJ-1', now(), 'A', 'B')")
        self.conn.execute("INSERT INTO flow.links (source_key, target_key, link_type) VALUES ('PROJ-1', 'PROJ-2', 'blocks')")
        self.conn.execute("INSERT INTO flow.issue_label_periods (issue_key, label, added_at) VALUES ('PROJ-1', 'x', now())")
        self.conn.execute("INSERT INTO flow.issue_version_periods (issue_key, version, added_at) VALUES ('PROJ-1', 'v', now())")
        self.conn.commit()
        code, sortie, erreur = self.lancer_base("purge", "--apply", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertEqual(self.cles(), ["PROJ-2"])
        for table in ("issue_teams", "transitions", "issue_label_periods", "issue_version_periods"):
            self.assertEqual(self.conn.execute(f"SELECT count(*) FROM flow.{table}").fetchone()[0], 0, table)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM flow.links").fetchone()[0], 0)
        self.assertEqual(self.lancer_base("check")[0], 0)

    def test_essai_ne_supprime_rien(self):
        self.ticket("PROJ-1", jours_resolu=400)
        code, sortie, _ = self.lancer_base("purge", "--language", "en")
        self.assertEqual(code, 0)
        self.assertEqual(self.cles(), ["PROJ-1"])

    def test_echec_annule_la_transaction(self):
        self.ticket("PROJ-1", jours_resolu=400)
        self.ticket("PROJ-2", jours_sorti=500)
        self.conn.execute("RESET ROLE")
        self.conn.execute("SET ROLE pmzilla_owner")
        self.conn.execute("CREATE FUNCTION flow.zz_echec() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
                          "IF OLD.key = 'PROJ-2' THEN RAISE EXCEPTION 'zz'; END IF; RETURN OLD; END $$")
        self.conn.execute("CREATE TRIGGER zz_echec BEFORE DELETE ON flow.issues FOR EACH ROW EXECUTE FUNCTION flow.zz_echec()")
        self.conn.commit()
        code, sortie, erreur = self.lancer_base("purge", "--apply", "--language", "en")
        self.assertEqual(code, 1)
        self.assertEqual(self.cles(), ["PROJ-1", "PROJ-2"])         # aucune ligne supprimée, même celle qui précédait l'échec
        self.assertNotIn("PROJ", sortie + erreur)


class ContenuDesStories(AvecBase):
    """Magasin « contenu des stories » (schéma quality, migration de R-78) : horloge SQL et cascade, sur une vraie base jetable."""

    def item(self, cle, jours_collecte=1, jours_resolu=None, jours_sorti=None, ouvert=True):
        """Une story du schéma quality sous le rôle de lecture-écriture, avec ses lignes dépendantes. Les jours sont relatifs à AUJOURDHUI."""
        midi = f"{AUJOURDHUI}T12:00:00+00"
        self.conn.execute("RESET ROLE")
        self.conn.execute("SET ROLE pmzilla_quality")
        self.conn.execute(
            "INSERT INTO quality.items (key, kind, status_category, created_at, updated_at, resolved_at, text_collected_at, out_of_collection_at) "
            "VALUES (%s, 'story', %s, '2020-01-01', now(), "
            "CASE WHEN %s::int IS NULL THEN NULL ELSE %s::timestamptz - make_interval(days => %s::int) END, "
            "%s::timestamptz - make_interval(days => %s::int), "
            "CASE WHEN %s::int IS NULL THEN NULL ELSE %s::timestamptz - make_interval(days => %s::int) END)",
            (cle, "To Do" if ouvert else "Done", jours_resolu, midi, jours_resolu, midi, jours_collecte, jours_sorti, midi, jours_sorti))
        self.conn.execute("INSERT INTO quality.item_teams (item_key, team, position) VALUES (%s, 'Alpha', 1)", (cle,))
        self.conn.execute("INSERT INTO quality.contents (item_key, title, description, acceptance_criteria, content_hash) "
                          "VALUES (%s, 'zztitre', 'zzdescription', '', 'h')", (cle,))
        self.conn.execute("INSERT INTO quality.assessments (item_key, core_grid_id, core_grid_version, criterion_code, origin, link, "
                          "verdict, sample) VALUES (%s, 'g', '1', 'c1', 'core', 'refinement', 'met', false)", (cle,))
        self.conn.execute("INSERT INTO quality.coaching_feedback (item_key, core_grid_id, core_grid_version, criterion_code, verdict, feedback) "
                          "VALUES (%s, 'g', '1', 'c1', 'met', 'zzretour')", (cle,))
        self.conn.commit()

    def cles_contenu(self):
        self.conn.execute("RESET ROLE")
        self.conn.execute("SET ROLE pmzilla_quality")
        return sorted(r[0] for r in self.conn.execute("SELECT key FROM quality.items").fetchall())

    def compte(self, table):
        return self.conn.execute(f"SELECT count(*) FROM quality.{table}").fetchone()[0]

    def test_horloge_du_texte_et_du_ticket(self):
        self.item("PROJ-1", jours_collecte=400)                                     # ouvert, texte collecté il y a 13 mois : hors règle
        self.item("PROJ-2", jours_collecte=3)                                       # ouvert, texte récent : dans la règle
        self.item("PROJ-3", jours_collecte=3, jours_resolu=800, ouvert=False)       # ancien résolu, recollecté la semaine dernière : hors règle
        self.item("PROJ-4", jours_collecte=3, jours_resolu=10, ouvert=False)        # résolu récemment, texte récent : dans la règle
        self.item("PROJ-5", jours_collecte=3, jours_sorti=500)                      # sorti de la collecte depuis longtemps : hors règle
        self.item("PROJ-6", jours_collecte=3, jours_sorti=5)                        # sorti récemment : dans la règle
        code, sortie, erreur = self.lancer_base("check", "--language", "en")
        self.assertEqual(code, 4, erreur)
        self.assertIn("story content: 3 items out of rule", sortie)
        self.assertTrue(sortie.rstrip().endswith("retention check: 3 items out of rule"), sortie)

    def test_purge_supprime_en_cascade_et_garde_les_autres(self):
        self.item("PROJ-1", jours_collecte=400)
        self.item("PROJ-2", jours_collecte=3)
        code, sortie, erreur = self.lancer_base("purge", "--apply", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertEqual(self.cles_contenu(), ["PROJ-2"])
        for table in ("item_teams", "contents", "assessments", "coaching_feedback"):
            self.assertEqual(self.compte(table), 1, table)           # seules les lignes de PROJ-2 restent
        self.assertNotIn("zz", sortie + erreur)
        self.assertEqual(self.lancer_base("check")[0], 0)

    def test_essai_ne_supprime_rien(self):
        self.item("PROJ-1", jours_collecte=400)
        code, _, _ = self.lancer_base("purge", "--language", "en")
        self.assertEqual(code, 0)
        self.assertEqual(self.cles_contenu(), ["PROJ-1"])
        self.assertEqual(self.compte("contents"), 1)

    def test_echec_annule_la_suppression_du_contenu(self):
        self.item("PROJ-1", jours_collecte=400)
        self.item("PROJ-2", jours_collecte=500)
        self.conn.execute("RESET ROLE")
        self.conn.execute("SET ROLE pmzilla_owner")
        self.conn.execute("CREATE FUNCTION quality.zz_echec() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
                          "IF OLD.key = 'PROJ-2' THEN RAISE EXCEPTION 'zz'; END IF; RETURN OLD; END $$")
        self.conn.execute("CREATE TRIGGER zz_echec BEFORE DELETE ON quality.items FOR EACH ROW EXECUTE FUNCTION quality.zz_echec()")
        self.conn.commit()
        code, sortie, erreur = self.lancer_base("purge", "--apply", "--language", "en")
        self.assertEqual(code, 1)
        self.assertEqual(self.cles_contenu(), ["PROJ-1", "PROJ-2"])       # aucune ligne supprimée, même celle qui précédait l'échec
        self.assertNotIn("PROJ", sortie + erreur)


if __name__ == "__main__":
    unittest.main()
