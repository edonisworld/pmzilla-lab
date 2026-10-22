"""
Tests du magasin du schéma quality (tools/story_quality_store.py ; change story-quality-audit, design D3 et D9) sur une FAUSSE connexion
(aide_story_quality.py) : une transaction par collecte, annulation sur erreur, marques de sortie sur un passage complet seulement, tirage
sans clé, relecture sans texte. Le même SQL est essayé sur la base jetable par test_magasin_base.py. Données inventées.
"""
from __future__ import annotations

import datetime as dt
import random
import sys
import unittest
from pathlib import Path
from unittest import mock

from aide_story_quality import FausseConnexion

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import story_quality_store as store  # noqa: E402

INSTANT = dt.datetime(2026, 9, 1, 10, 0, tzinfo=dt.timezone.utc)


def element(cle, equipes=("Equipe Zzalpha",)):
    return store.Element(key=cle, kind="story", parent_key=None, status_category="new", created_at=INSTANT, updated_at=INSTANT,
                         resolved_at=None, teams=list(equipes), title="zztitre", description="zzdescription", acceptance_criteria="",
                         content_hash="h", replacements=2)


class Collecte(unittest.TestCase):
    def test_une_transaction_et_l_ordre_des_ecritures(self):
        conn = FausseConnexion({"SELECT count(*)": [(0,)]}, rowcount=1)
        marques, revenus = store.MagasinQualite(conn).enregistrer_collecte([element("ZZ-1", ("A", "B", "A"))], {"A": True}, complet=True)
        self.assertEqual((marques, revenus), (1, 0))
        sql = [s for s, _ in conn.requetes]
        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 0)
        self.assertEqual(sql[-1], "COMMIT")
        self.assertEqual(sum("quality.item_teams (item_key, team, position)" in s for s in sql), 2)   # A, B : sans doublon
        self.assertTrue(any(s.startswith("UPDATE quality.items SET out_of_collection_at") for s in sql))
        self.assertTrue(any("quality.team_attributes" in s for s in sql))
        insertion = next(p for s, p in conn.requetes if s.startswith("INSERT INTO quality.items"))
        self.assertEqual(insertion[0], "ZZ-1")
        self.assertIn("text_collected_at = now()", store.SQL_ELEMENT)          # la nouvelle collecte remet l'horloge à maintenant
        self.assertIn("out_of_collection_at = NULL", store.SQL_ELEMENT)

    def test_passage_partiel_ne_marque_rien(self):
        conn = FausseConnexion({"SELECT count(*)": [(0,)]}, rowcount=4)
        marques, _ = store.MagasinQualite(conn).enregistrer_collecte([element("ZZ-1")], {}, complet=False)
        self.assertEqual(marques, 0)
        self.assertFalse(any(s.startswith("UPDATE") for s, _ in conn.requetes))

    def test_les_vus_servent_aux_marques(self):
        conn = FausseConnexion({"SELECT count(*)": [(1,)]}, rowcount=0)
        _, revenus = store.MagasinQualite(conn).enregistrer_collecte([element("ZZ-1")], {}, complet=True, vus=["ZZ-1", "ZZ-2"])
        self.assertEqual(revenus, 1)
        marque = next(p for s, p in conn.requetes if s.startswith("UPDATE"))
        self.assertEqual(marque, (["ZZ-1", "ZZ-2"],))

    def test_erreur_annule_tout(self):
        conn = FausseConnexion({"SELECT count(*)": [(0,)]})
        conn.echec = ("quality.contents", RuntimeError("zz"))
        with self.assertRaises(RuntimeError):
            store.MagasinQualite(conn).enregistrer_collecte([element("ZZ-1")], {}, complet=True)
        self.assertEqual((conn.commits, conn.rollbacks), (0, 1))


class EchantillonEtRelecture(unittest.TestCase):
    def test_tirage_sans_cle(self):
        conn = FausseConnexion({"SELECT i.key": [("ZZ-1",), ("ZZ-2",), ("ZZ-3",)],
                                "FROM quality.contents": lambda p: [(c, f"t{c}", "d", "a") for c in p[0]]})
        textes = store.MagasinQualite(conn).echantillon("Equipe Zzalpha", 2, random.Random(1))
        self.assertEqual(len(textes), 2)
        for titre, description, criteres in textes:
            self.assertTrue(titre.startswith("tZZ-"))
            self.assertEqual((description, criteres), ("d", "a"))
        self.assertEqual(conn.commits, 0)
        cles = next(p for s, p in conn.requetes if s.startswith("SELECT i.key"))
        self.assertEqual(cles, ("Equipe Zzalpha",))
        self.assertIn("out_of_collection_at IS NULL", store.SQL_CLES_EQUIPE)

    def test_equipe_sans_element(self):
        conn = FausseConnexion({"SELECT i.key": []})
        self.assertEqual(store.MagasinQualite(conn).echantillon("Equipe Zz", 3, random.Random(1)), [])

    def test_relecture_sans_texte(self):
        conn = FausseConnexion()
        store.MagasinQualite(conn).enregistrer_relecture("Equipe Zzalpha", 3)
        self.assertEqual(conn.requetes[0], (store.SQL_RELECTURE, ("Equipe Zzalpha", 3)))
        self.assertEqual(conn.commits, 1)


class Ouverture(unittest.TestCase):
    def test_role_pose_et_valide(self):
        import db
        import psycopg.sql
        conn = FausseConnexion()
        with mock.patch.object(db, "connect", lambda *a, **k: conn):
            magasin = store.ouvrir()
        self.assertIs(magasin.conn, conn)
        self.assertEqual(conn.requetes[1], ("COMMIT", ()))
        requete = conn.requetes[0][0]
        self.assertIsInstance(requete, psycopg.sql.Composed)           # identifiant composé par psycopg, jamais une chaîne mise en forme
        self.assertEqual(requete.as_string(), 'SET ROLE "pmzilla_quality"')

    def test_base_injoignable_sans_detail(self):
        import db

        def refus(*a, **k):
            raise db.ErreurBase("Connexion à la base impossible : zzdetail")
        with mock.patch.object(db, "connect", refus), self.assertRaises(store.ErreurMagasin) as contexte:
            store.ouvrir()
        self.assertEqual(str(contexte.exception), "")


if __name__ == "__main__":
    unittest.main()
