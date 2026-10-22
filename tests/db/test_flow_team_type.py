"""Colonne du type d'équipe de flow.teams (change database-only, complément « Complement: team type column », tâche 4.11 ; migration de
la tâche 5.2). Spec database-roles-views du change.

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

Les tests sans base (SansBase) tournent toujours : lecture du fichier de migration. Les autres utilisent la base jetable de
test_flow_schema.py et sont sautés sans elle (bash tools/dbtest.sh db). La migration est retrouvée par sa description
(flow_team_type), pas par son numéro. Données inventées : équipes Alpha, Beta, Gamma.
"""
import re
import secrets
import unittest

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402

TYPES = ("Development Team", "Verification Team", "Product Management Team", "Other Team")
ROLE_IMPORT = "pmzilla_flow"


def fichier_migration():
    candidats = [m for m in db.lister_migrations() if m.nom.endswith("_flow_team_type.sql")]
    return candidats[0] if len(candidats) == 1 else None


class SansBase(unittest.TestCase):
    def test_migration_presente_sans_donnee_ni_mot_de_passe_ni_role_ni_droit(self):
        migration = fichier_migration()
        self.assertIsNotNone(migration, "une migration *_flow_team_type.sql est attendue")
        texte = migration.chemin.read_text(encoding="utf-8")
        self.assertRegex(texte.splitlines()[0], r"^-- Schéma touché : flow")
        sans_commentaires = re.sub(r"--[^\n]*", "", texte)
        self.assertNotRegex(sans_commentaires, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s)")           # aucune donnée, aucune mise à jour
        self.assertNotRegex(sans_commentaires, r"(?i)\bPASSWORD\b")
        self.assertNotRegex(sans_commentaires, r"(?i)\b(CREATE|ALTER|DROP)\s+ROLE\b")
        self.assertNotRegex(sans_commentaires, r"(?i)\b(LOGIN|GRANT|REVOKE)\b")                # aucun droit changé
        self.assertRegex(sans_commentaires, r"(?is)ALTER\s+TABLE\s+flow\.teams\s+ADD\s+COLUMN\s+team_type\s+text")
        for nom in TYPES:
            self.assertIn(nom, sans_commentaires)

    def test_la_migration_suit_celles_de_r70_et_r78(self):
        numeros = {m.nom.split("_", 1)[1]: m.numero for m in db.lister_migrations()}
        self.assertGreater(numeros["flow_team_type.sql"], numeros["flow_raw_layer.sql"])
        self.assertGreater(numeros["flow_team_type.sql"], numeros["quality_schema.sql"])

    def test_le_nom_de_la_colonne_ne_porte_ni_etiquette_ni_cle(self):
        self.assertNotIn("label", "team_type")
        self.assertNotIn("key", "team_type")


class ColonneType(unittest.TestCase):
    """Même base jetable que SchemaFlow (migrations appliquées, base supprimée à la fin)."""
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie

    def test_la_colonne_est_nulle_pour_une_equipe_sans_type(self):
        c = self.conn()
        c.execute(f"SET ROLE {ROLE_IMPORT}")
        c.execute("INSERT INTO flow.teams (name) VALUES ('Alpha')")
        self.assertIsNone(c.execute("SELECT team_type FROM flow.teams WHERE name = 'Alpha'").fetchone()[0])
        c.execute("RESET ROLE")

    def test_les_quatre_noms_sont_acceptes_et_un_autre_refuse(self):
        c = self.conn()
        c.execute(f"SET ROLE {ROLE_IMPORT}")
        for i, nom in enumerate(TYPES):
            c.execute("INSERT INTO flow.teams (name, team_type) VALUES (%s, %s)", (f"Equipe {i}", nom))
        for refuse in ("Developpement", "development team", "", "Other"):
            with self.assertRaises(db.psycopg.errors.CheckViolation):
                with c.transaction():
                    c.execute("INSERT INTO flow.teams (name, team_type) VALUES ('Intruse', %s)", (refuse,))
        c.execute("RESET ROLE")

    def test_le_role_d_import_ecrit_et_met_a_jour_le_type(self):
        c = self.conn()
        c.execute(f"SET ROLE {ROLE_IMPORT}")
        c.execute("INSERT INTO flow.teams (name) VALUES ('Alpha'), ('Beta')")
        c.execute("UPDATE flow.teams SET team_type = 'Development Team' WHERE name = 'Alpha'")
        c.execute("UPDATE flow.teams SET team_type = 'Verification Team' WHERE name = 'Alpha'")
        types = dict(c.execute("SELECT name, team_type FROM flow.teams").fetchall())
        self.assertEqual(types, {"Alpha": "Verification Team", "Beta": None})
        c.execute("RESET ROLE")

    def test_le_role_en_lecture_seule_lit_la_colonne_et_ne_l_ecrit_pas(self):
        c = self.conn()
        c.execute(f"SET ROLE {ROLE_IMPORT}")
        c.execute("INSERT INTO flow.teams (name, team_type) VALUES ('Alpha', 'Other Team')")
        c.execute("RESET ROLE")
        c.commit()
        self.assertTrue(self.essaie(c, "pmzilla_flow_ro", "SELECT team_type FROM flow.teams"))
        self.assertFalse(self.essaie(c, "pmzilla_flow_ro", "UPDATE flow.teams SET team_type = 'Other Team'"))

    def test_le_role_des_vues_n_a_aucun_acces_a_la_colonne(self):
        c = self.conn()
        self.assertFalse(self.essaie(c, "pmzilla_flow_views", "SELECT team_type FROM flow.teams"))
        self.assertFalse(self.essaie(c, "pmzilla_flow_views", "SELECT * FROM flow.teams"))

    def test_aucune_vue_ne_lit_le_type(self):
        c = self.conn()
        for vue in fs.VUES:
            definition = c.execute("SELECT pg_get_viewdef(%s::regclass)", (f"flow.{vue}",)).fetchone()[0]
            self.assertNotIn("team_type", definition, vue)


class AvantLaMigration(unittest.TestCase):
    """Base jetable migrée jusqu'à la couche brute, avec des équipes, puis la migration du type : aucune ligne n'est touchée."""
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn

    def setUp(self):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        self.nom_base = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True)
        self.addCleanup(self._supprimer)
        self.admin.execute(f'CREATE DATABASE "{self.nom_base}"')
        self.url = base.url_vers(self.nom_base)
        self.ouvertes = []

    def test_une_base_qui_a_deja_des_equipes_les_garde_sans_type(self):
        c = self.conn()
        toutes = db.lister_migrations(db.DOSSIER_MIGRATIONS)
        migration = fichier_migration()
        # « avant » = les migrations antérieures seulement (ordre des numéros) : une migration postérieure peut dépendre de la colonne
        # (0014 lit team_type), donc « toutes sauf une » casserait (team-names-readable, 9.5).
        db.migrer(c, [m for m in toutes if m.numero < migration.numero])
        c.commit()
        c.execute(f"SET ROLE {ROLE_IMPORT}")
        c.execute("INSERT INTO flow.teams (name) VALUES ('Alpha'), ('Beta'), ('Gamma')")
        c.execute("RESET ROLE")
        c.commit()
        self.assertEqual(c.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema = 'flow' "
                                   "AND table_name = 'teams' AND column_name = 'team_type'").fetchone()[0], 0)
        db.migrer(c, toutes)
        c.commit()
        self.assertEqual(c.execute("SELECT count(*), count(team_type) FROM flow.teams").fetchone(), (3, 0))


if __name__ == "__main__":
    unittest.main()
