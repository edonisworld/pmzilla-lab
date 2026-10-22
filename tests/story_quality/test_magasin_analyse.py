"""
Tests du magasin de `analyse` et `coach` (tools/story_quality_audit_store.py ; change story-quality-audit, design D7, « Data model ») sur
une FAUSSE connexion (aide_story_quality.py) : lectures terminées par une annulation, une transaction par écriture, remplacement des
verdicts à la même paire (audit) ou de tous les verdicts d'échantillon, jamais un audit par un échantillon, retour de coaching dans sa
propre table. Le même SQL est essayé sur la base jetable par test_magasin_analyse_base.py. Données inventées.
"""
from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path

from aide_story_quality import FausseConnexion

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import story_quality_audit_store as audit_store  # noqa: E402

INSTANT = dt.datetime(2026, 9, 1, 10, 0, tzinfo=dt.timezone.utc)
PAIRE = ("socle-fictif", "3", "surcouche-fictive", "2")


class Lectures(unittest.TestCase):
    def test_elements_avec_leurs_equipes_sans_texte(self):
        conn = FausseConnexion({"SELECT i.key": [("ZZ-1", "story", INSTANT, "h1"), ("ZZ-2", "epic", INSTANT, "h2")],
                                "FROM quality.item_teams": [("ZZ-1", "A"), ("ZZ-1", "B")]})
        elements = audit_store.MagasinAnalyse(conn).elements()
        self.assertEqual(elements, [{"key": "ZZ-1", "kind": "story", "updated_at": INSTANT, "content_hash": "h1", "teams": ["A", "B"]},
                                    {"key": "ZZ-2", "kind": "epic", "updated_at": INSTANT, "content_hash": "h2", "teams": []}])
        self.assertIn("out_of_collection_at IS NULL", audit_store.SQL_ELEMENTS)
        self.assertNotIn("title", audit_store.SQL_ELEMENTS)
        self.assertEqual(conn.commits, 0)
        self.assertEqual(conn.rollbacks, 2)

    def test_derniers_audits_hors_echantillon_a_la_paire(self):
        conn = FausseConnexion({"DISTINCT ON (item_key)": [("ZZ-1", "h1"), ("ZZ-2", None)]})
        self.assertEqual(audit_store.MagasinAnalyse(conn).derniers_audits(PAIRE), {"ZZ-1": "h1", "ZZ-2": None})
        sql, params = conn.requetes[0]
        self.assertIn("NOT sample", sql)
        self.assertIn("ORDER BY item_key, analysed_at DESC, id DESC", sql)
        self.assertEqual(params, PAIRE)

    def test_textes_vides_rendus_en_chaines_avec_l_empreinte_lue_avec_le_texte(self):
        conn = FausseConnexion({"FROM quality.contents": [("ZZ-1", "t", None, None, "h1")]})
        self.assertEqual(audit_store.MagasinAnalyse(conn).textes(["ZZ-1"]), {"ZZ-1": ("t", "", "", "h1")})
        self.assertIn("content_hash", audit_store.SQL_TEXTES)

    def test_une_lecture_en_erreur_annule_quand_meme(self):
        conn = FausseConnexion()
        conn.echec = ("FROM quality.team_reviews", RuntimeError("zz"))
        with self.assertRaises(RuntimeError):
            audit_store.MagasinAnalyse(conn).equipes_relues()
        self.assertEqual((conn.commits, conn.rollbacks), (0, 1))

    def test_coaching_et_empreinte(self):
        conn = FausseConnexion({"FROM quality.coaching_feedback": [("ZZ-1", "c1", "met", "r"), ("ZZ-1", "c2", "not_met", "")],
                                "FROM quality.overlay_versions": [("e1",)]})
        magasin = audit_store.MagasinAnalyse(conn)
        self.assertEqual(magasin.lire_coaching(["ZZ-1"]), {"ZZ-1": [("c1", "met", "r"), ("c2", "not_met", "")]})
        self.assertEqual(magasin.empreinte_surcouche("surcouche-fictive", "2"), "e1")


class Ecritures(unittest.TestCase):
    def test_audit_remplace_la_meme_paire_en_une_transaction(self):
        conn = FausseConnexion()
        audit_store.MagasinAnalyse(conn).enregistrer_audit("ZZ-1", PAIRE, [("c1", "core", "refinement", "met")], False, "h1")
        (effacer, p1), (inserer, p2), (fin, _) = conn.requetes
        self.assertTrue(effacer.startswith("DELETE FROM quality.assessments") and "NOT sample" in effacer)
        self.assertEqual(p1, ("ZZ-1", *PAIRE))
        self.assertEqual(p2, ("ZZ-1", *PAIRE, "c1", "core", "refinement", "met", False, "h1"))
        self.assertEqual((fin, conn.commits), ("COMMIT", 1))

    def test_echantillon_ne_remplace_que_l_echantillon(self):
        conn = FausseConnexion()
        audit_store.MagasinAnalyse(conn).enregistrer_audit("ZZ-1", PAIRE, [("c1", "core", "refinement", "met")], True)
        effacer, params = conn.requetes[0]
        self.assertEqual(effacer, audit_store.SQL_EFFACER_ECHANTILLON)
        self.assertIn("AND sample", effacer)
        self.assertEqual(params, ("ZZ-1",))
        self.assertIs(conn.requetes[1][1][-2], True)

    def test_empreinte_de_surcouche_relue_dans_la_transaction(self):
        conn = FausseConnexion({"SELECT content_hash FROM quality.overlay_versions": [("e-autre",)]})
        self.assertEqual(audit_store.MagasinAnalyse(conn).enregistrer_empreinte("surcouche-fictive", "2", "e-mienne"), "e-autre")
        self.assertEqual([s.split(" ")[0] for s, _ in conn.requetes], ["INSERT", "SELECT", "COMMIT"])

    def test_coaching_dans_sa_table_seulement(self):
        conn = FausseConnexion()
        audit_store.MagasinAnalyse(conn).enregistrer_coaching("ZZ-1", PAIRE, [("c1", "met", "retour")])
        self.assertFalse(any("assessments" in s for s, _ in conn.requetes))
        self.assertEqual(conn.requetes[1][1], ("ZZ-1", *PAIRE, "c1", "met", "retour"))

    def test_erreur_annule(self):
        conn = FausseConnexion()
        conn.echec = ("INSERT INTO quality.assessments", RuntimeError("zz"))
        with self.assertRaises(RuntimeError):
            audit_store.MagasinAnalyse(conn).enregistrer_audit("ZZ-1", PAIRE, [("c1", "core", "refinement", "met")], False)
        self.assertEqual((conn.commits, conn.rollbacks), (0, 1))


if __name__ == "__main__":
    unittest.main()
