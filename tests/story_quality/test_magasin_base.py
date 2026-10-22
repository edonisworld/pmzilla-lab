"""
Le SQL du magasin du schéma quality (tools/story_quality_store.py) sur la BASE JETABLE (change story-quality-audit, design D3 et D9) :
sauté sans le repère DBTEST_PORT de bash tools/dbtest.sh (même règle que tests/db et tests/flow_store). La vraie base n'est jamais
ouverte ; les lectures de vérification portent sur la base jetable et sur des données inventées.

    bash tools/dbtest.sh story_quality
"""
from __future__ import annotations

import contextlib
import datetime as dt
import random
import secrets
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(RACINE / "tests" / "db"))
import db  # noqa: E402
import story_quality_store as store  # noqa: E402
import test_db  # noqa: E402  (la garde des tests avec base : une seule règle)

INSTANT = dt.datetime(2026, 9, 1, 10, 0, tzinfo=dt.timezone.utc)


def element(cle, equipes=("Alpha",), titre="zztitre"):
    return store.Element(key=cle, kind="story", parent_key=None, status_category="new", created_at=INSTANT, updated_at=INSTANT,
                         resolved_at=None, teams=list(equipes), title=titre, description="d", acceptance_criteria="",
                         content_hash="h-" + cle, replacements=1)


class MagasinSurBaseJetable(unittest.TestCase):
    def setUp(self):
        if not test_db.BASE_DISPONIBLE:
            self.skipTest(test_db.MESSAGE_SAUT)
        self.nom_base = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(test_db.URL_BASE, password=test_db.MOT_DE_PASSE, autocommit=True)
        self.addCleanup(self._supprimer)
        self.admin.execute(f'CREATE DATABASE "{self.nom_base}"')
        url = test_db.url_vers(self.nom_base)
        migration = db.connect(url, password=test_db.MOT_DE_PASSE)
        db.migrer(migration, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        migration.commit()
        migration.close()
        self.conn = db.connect(url, password=test_db.MOT_DE_PASSE)
        self.conn.execute(f"SET ROLE {store.ROLE}")
        self.conn.commit()
        self.verif = db.connect(url, password=test_db.MOT_DE_PASSE, autocommit=True)
        self.magasin = store.MagasinQualite(self.conn)

    def _supprimer(self):
        for nom in ("conn", "verif"):
            with contextlib.suppress(Exception):
                getattr(self, nom).close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom_base}" WITH (FORCE)')
        self.admin.close()

    def compte(self, sql, params=()):
        return self.verif.execute(sql, params).fetchone()[0]

    def test_collecte_complete_puis_retour(self):
        self.assertEqual(self.magasin.enregistrer_collecte([element("PROJ-1"), element("PROJ-2", ("Alpha", "Beta"))],
                                                           {"Alpha": True, "Beta": False}, complet=True), (0, 0))
        self.assertEqual(self.compte("SELECT count(*) FROM quality.items"), 2)
        self.assertEqual(self.compte("SELECT count(*) FROM quality.item_teams WHERE item_key = 'PROJ-2'"), 2)
        self.assertTrue(self.compte("SELECT single_po FROM quality.team_attributes WHERE team = 'Alpha'"))
        self.assertEqual(self.magasin.enregistrer_collecte([element("PROJ-1", titre="nouveau")], {}, complet=True), (1, 0))
        self.assertEqual(self.compte("SELECT count(*) FROM quality.items WHERE out_of_collection_at IS NOT NULL"), 1)
        self.assertEqual(self.compte("SELECT title FROM quality.contents WHERE item_key = 'PROJ-1'"), "nouveau")
        self.assertEqual(self.magasin.enregistrer_collecte([element("PROJ-1"), element("PROJ-2")], {}, complet=True), (0, 1))

    def test_passage_partiel_et_annulation(self):
        self.magasin.enregistrer_collecte([element("PROJ-1"), element("PROJ-2")], {}, complet=True)
        self.assertEqual(self.magasin.enregistrer_collecte([element("PROJ-1")], {}, complet=False), (0, 0))
        self.assertEqual(self.compte("SELECT count(*) FROM quality.items WHERE out_of_collection_at IS NOT NULL"), 0)
        mauvais = element("PROJ-3")
        mauvais.kind = "bug"                                 # refusé par la contrainte du schéma : rien du passage ne reste
        with self.assertRaises(db.psycopg.Error):
            self.magasin.enregistrer_collecte([element("PROJ-4"), mauvais], {"Gamma": True}, complet=True)
        self.assertEqual(self.compte("SELECT count(*) FROM quality.items"), 2)
        self.assertEqual(self.compte("SELECT count(*) FROM quality.team_attributes WHERE team = 'Gamma'"), 0)

    def test_echantillon_et_relecture(self):
        self.magasin.enregistrer_collecte([element(f"PROJ-{i}") for i in range(1, 5)] + [element("PROJ-9", ("Beta",))], {},
                                          complet=True)
        textes = self.magasin.echantillon("Alpha", 2, random.Random(4))
        self.assertEqual(len(textes), 2)
        self.assertEqual(textes[0], ("zztitre", "d", ""))
        self.assertEqual(self.magasin.echantillon("Absente", 2, random.Random(4)), [])
        self.magasin.enregistrer_relecture("Alpha", 2)
        self.assertEqual(self.verif.execute("SELECT team, sample_size FROM quality.team_reviews").fetchall(), [("Alpha", 2)])


if __name__ == "__main__":
    unittest.main()
