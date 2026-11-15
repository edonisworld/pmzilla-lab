"""
Tests des fonctions du magasin pour le détecteur de données de patient (change patient-data-detection, tâche 3.2, design D6) sur une fausse
connexion : lecture des textes sans clé, enregistrement d'un passage sans compte, lecture du dernier passage et de la dernière levée.
"""
from __future__ import annotations

import datetime as dt
import json
import unittest

from aide_story_quality import FausseConnexion
import story_quality_store as store

INSTANT = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
TOUS_FAUX = {f"P{i}": False for i in range(1, 10)}


class TextesPourLaDetection(unittest.TestCase):
    def test_lit_tous_les_elements_sans_cle_et_annule(self):
        conn = FausseConnexion({"FROM quality.items": [("story", "titre", "description", "critères"), ("epic", None, None, None)]})
        textes = store.MagasinQualite(conn).textes_pour_detection()
        self.assertEqual(textes, [("story", "titre", "description", "critères"), ("epic", "", "", "")])
        sql = conn.requetes[0][0]
        self.assertNotIn("item_key", sql.split("FROM")[0])
        self.assertNotIn("i.key", sql.split("FROM")[0])
        self.assertNotIn("out_of_collection_at IS NULL", sql)                 # les éléments sortis de la collecte sont lus aussi
        self.assertEqual((conn.commits, conn.rollbacks), (0, 1))


class PassageEtLevee(unittest.TestCase):
    def test_enregistrer_un_passage_sans_compte_ni_texte(self):
        conn = FausseConnexion({"INSERT INTO quality.patient_scan_runs": [(INSTANT,)]})
        instant = store.MagasinQualite(conn).enregistrer_detection(1, "empreinte", {"story": 12}, {**TOUS_FAUX, "P5": True})
        self.assertEqual(instant, INSTANT)
        sql, parametres = conn.requetes[0]
        self.assertEqual(parametres[:2], (1, "empreinte"))
        self.assertEqual(json.loads(parametres[2]), {"story": 12})
        self.assertEqual(json.loads(parametres[3]), {**TOUS_FAUX, "P5": True})
        self.assertEqual(conn.commits, 1)

    def test_une_erreur_annule(self):
        conn = FausseConnexion()
        conn.echec = ("patient_scan_runs", RuntimeError("zzdetail"))
        with self.assertRaises(RuntimeError):
            store.MagasinQualite(conn).enregistrer_detection(1, None, {}, TOUS_FAUX)
        self.assertEqual((conn.commits, conn.rollbacks), (0, 1))

    def test_dernier_passage(self):
        ligne = (7, INSTANT, 1, None, {"story": 3}, {**TOUS_FAUX, "P1": True})
        conn = FausseConnexion({"FROM quality.patient_scan_runs ORDER": [ligne]})
        passage = store.MagasinQualite(conn).derniere_detection()
        self.assertEqual(passage, {"id": 7, "run_at": INSTANT, "detector_version": 1, "labels_fingerprint": None,
                                   "items_read": {"story": 3}, "found": {**TOUS_FAUX, "P1": True}})
        self.assertEqual(conn.rollbacks, 1)

    def test_dernier_passage_absent_et_jsonb_en_chaine(self):
        self.assertIsNone(store.MagasinQualite(FausseConnexion({"FROM quality.patient_scan_runs ORDER": []})).derniere_detection())
        ligne = (1, INSTANT, 1, "e", json.dumps({"story": 1}), json.dumps(TOUS_FAUX))
        passage = store.MagasinQualite(FausseConnexion({"FROM quality.patient_scan_runs ORDER": [ligne]})).derniere_detection()
        self.assertEqual((passage["items_read"], passage["found"]), ({"story": 1}, TOUS_FAUX))

    def test_enregistrer_une_levee(self):
        conn = FausseConnexion()
        store.MagasinQualite(conn).enregistrer_levee(1, None, 7, ["P5", "P3", "P5"])
        sql, parametres = conn.requetes[0]
        self.assertIn("INSERT INTO quality.patient_scan_lifts", sql)
        self.assertEqual(parametres, (1, None, 7, ["P3", "P5"]))
        self.assertEqual(conn.commits, 1)

    def test_derniere_levee_avec_les_categories_trouvees_depuis(self):
        conn = FausseConnexion({
            "FROM quality.patient_scan_lifts ORDER": [(3, INSTANT, 1, None, 7, ["P5"])],
            "FROM quality.patient_scan_runs WHERE run_at >": [({**TOUS_FAUX, "P5": True},), (json.dumps({**TOUS_FAUX, "P3": True}),)]})
        levee = store.MagasinQualite(conn).derniere_levee()
        self.assertEqual(levee, {"id": 3, "lifted_at": INSTANT, "detector_version": 1, "labels_fingerprint": None, "run_id": 7,
                                 "accepted": ["P5"], "found_after": ["P3", "P5"]})
        self.assertEqual(conn.requetes[1][1], (INSTANT,))
        self.assertEqual(conn.rollbacks, 1)

    def test_aucune_levee(self):
        conn = FausseConnexion({"FROM quality.patient_scan_lifts ORDER": []})
        self.assertIsNone(store.MagasinQualite(conn).derniere_levee())
        self.assertEqual([r[0] for r in conn.requetes if r[0] != "ROLLBACK"].__len__(), 1)       # pas de lecture des passages sans levée


class Migration(unittest.TestCase):
    """La migration ne donne aucune colonne de texte libre, aucune vue, et aucun droit au rôle des vues (lecture statique)."""

    def test_deux_tables_sans_vue_ni_droit_au_role_des_vues(self):
        from pathlib import Path
        import re
        texte = (Path(__file__).resolve().parents[2] / "db" / "migrations" / "0028_quality_patient_detection.sql").read_text(encoding="utf-8")
        sans = "\n".join(re.sub(r"--.*$", "", ligne) for ligne in texte.splitlines())
        self.assertEqual(set(re.findall(r"CREATE TABLE quality\.([a-z_]+)", sans)), {"patient_scan_runs", "patient_scan_lifts"})
        self.assertNotRegex(sans, r"(?i)CREATE\s+(OR REPLACE\s+)?VIEW")
        for accord in re.findall(r"(?is)GRANT\b.*?;", sans):
            self.assertNotIn("pmzilla_quality_views", accord)
        self.assertRegex(sans, r"REVOKE ALL ON quality\.patient_scan_runs, quality\.patient_scan_lifts FROM PUBLIC, pmzilla_quality_views")
        self.assertNotRegex(sans, r"(?i)CREATE ROLE|PASSWORD")
        for interdit in ("key", "team", "title", "description", "acceptance", "count", "text"):
            self.assertNotRegex(sans, rf"(?i)\b{interdit}\w*\s+(integer|text|bigint|jsonb)", interdit)


if __name__ == "__main__":
    unittest.main()
