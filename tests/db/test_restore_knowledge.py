"""
Régression R-22 : la restauration du schéma knowledge dans le conteneur jetable (tools/db_restore_test.sh).

    uv run --with "psycopg[binary]" --with numpy --with httpx python -m unittest discover -s tests/db -v

Sur une base migrée, une sauvegarde faite avant la migration 0007 ne contient pas les tables de la veille et du pré-tri. Le DROP SCHEMA
sans CASCADE que pg_restore --clean émet échoue alors (« cannot drop schema knowledge because other objects depend on it »). Le script
vide donc le schéma (DROP SCHEMA … CASCADE) dans le conteneur jetable avant pg_restore. Ces tests établissent, sur une base jetable
pmzilla_test_<hex> (jamais les schémas réels) : l'origine de l'échec, et qu'aucun objet d'un autre schéma ne dépend de knowledge, donc que
le CASCADE n'emporte que knowledge. Sautés si la base manque. Aucune donnée.
"""
import contextlib
import secrets
import unittest

import test_db as base          # noqa: E402  (même dossier : connexion, base jetable, mot de passe)
from test_db import db          # noqa: E402

AUTRES_SCHEMAS = ("flow", "cases", "public")
TABLES_0007 = "watch_articles"      # créée par la migration 0007, absente d'une sauvegarde antérieure


class RestaurationKnowledge(unittest.TestCase):
    def setUp(self):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        self.nom_base = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True)
        self.addCleanup(self._supprimer)
        self.admin.execute(f'CREATE DATABASE "{self.nom_base}"')
        self.url = base.url_vers(self.nom_base)
        self.ouvertes = []
        c = self.conn()
        db.migrer(c, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        c.commit()

    def _supprimer(self):
        for c in self.ouvertes:
            with contextlib.suppress(Exception):
                c.close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom_base}" WITH (FORCE)')
        self.admin.close()

    def conn(self):
        c = db.connect(self.url, password=base.MOT_DE_PASSE)
        self.ouvertes.append(c)
        return c

    def objets_hors_knowledge(self, c):
        """Tables, vues, séquences, fonctions, types et index des autres schémas : le contenu qui doit survivre."""
        lignes = c.execute(
            "SELECT n.nspname::text || '.' || c.relname::text || ':' || c.relkind::text FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = ANY(%s) UNION ALL "
            "SELECT n.nspname::text || '.' || p.proname::text || '()' FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = ANY(%s) ORDER BY 1", (list(AUTRES_SCHEMAS), list(AUTRES_SCHEMAS))).fetchall()
        return [r[0] for r in lignes]

    def test_drop_schema_sans_cascade_echoue_quand_la_base_a_plus_de_tables_que_la_sauvegarde(self):
        """Origine de l'échec : knowledge contient des objets que le dump n'emporte pas (ici, toutes les tables), le DROP simple est refusé."""
        c = self.conn()
        self.assertTrue(c.execute("SELECT to_regclass('knowledge.watch_articles')").fetchone()[0], "la 0007 est appliquée")
        with self.assertRaises(Exception) as ctx:
            c.execute("DROP SCHEMA IF EXISTS knowledge")
        self.assertIn("cannot drop schema knowledge because other objects depend on it", str(ctx.exception))
        c.rollback()

    def test_aucun_objet_d_un_autre_schema_ne_depend_de_knowledge(self):
        """Le CASCADE ne peut emporter que knowledge : aucune vue, clé étrangère, fonction ou index de flow, cases ou public n'en dépend."""
        c = self.conn()
        avant = self.objets_hors_knowledge(c)
        self.assertTrue(avant, "flow, cases et public ne sont pas vides")
        # Seuls les schémas de l'application comptent : une table de knowledge a sa table TOAST dans pg_toast (schéma système), qui en dépend
        # par construction et disparaît avec elle ; pg_toast et pg_catalog ne sont donc pas des « autres schémas » à protéger.
        dependants = c.execute(
            "SELECT DISTINCT dn.nspname::text || '.' || coalesce(cl.relname, pr.proname, ty.typname, 'objet')::text "
            "FROM pg_depend d "
            "JOIN pg_class rc ON d.refclassid = 'pg_class'::regclass AND d.refobjid = rc.oid "
            "JOIN pg_namespace rn ON rn.oid = rc.relnamespace AND rn.nspname = 'knowledge' "
            "LEFT JOIN pg_class cl ON d.classid = 'pg_class'::regclass AND d.objid = cl.oid "
            "LEFT JOIN pg_proc pr ON d.classid = 'pg_proc'::regclass AND d.objid = pr.oid "
            "LEFT JOIN pg_type ty ON d.classid = 'pg_type'::regclass AND d.objid = ty.oid "
            "JOIN pg_namespace dn ON dn.oid = coalesce(cl.relnamespace, pr.pronamespace, ty.typnamespace) "
            "WHERE dn.nspname = ANY(%s)", (list(AUTRES_SCHEMAS),)).fetchall()
        self.assertEqual(dependants, [], "objets d'autres schémas qui dépendent d'une table de knowledge")
        c.execute("DROP SCHEMA knowledge CASCADE")
        self.assertEqual(self.objets_hors_knowledge(c), avant, "le CASCADE n'a touché ni flow, ni cases, ni public")
        c.rollback()

    def test_apres_le_cascade_le_schema_est_vide_et_un_drop_simple_passe(self):
        """Ce que pg_restore --clean --if-exists trouve après le vidage : rien à supprimer en trop, il recrée knowledge depuis le dump."""
        c = self.conn()
        c.execute("DROP SCHEMA IF EXISTS knowledge CASCADE")
        c.execute("DROP SCHEMA IF EXISTS knowledge")
        self.assertIsNone(c.execute("SELECT to_regnamespace('knowledge')").fetchone()[0])
        c.execute("CREATE SCHEMA knowledge")
        c.rollback()

    def test_extensions_hors_de_knowledge(self):
        """Aucune extension n'est installée dans knowledge : le CASCADE ne retire aucune extension."""
        c = self.conn()
        dans_knowledge = c.execute("SELECT e.extname FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace "
                                   "WHERE n.nspname = 'knowledge'").fetchall()
        self.assertEqual(dans_knowledge, [])


if __name__ == "__main__":
    unittest.main()
