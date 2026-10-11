"""tools/flow_import_messages.py : catalogues fr/en de flow_import.py (clés, champs, absence de données). Aucun accès extérieur.

    uv run python -W ignore -m unittest discover -s tests/flow_import_messages -q
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import flow_import_messages as fim  # noqa: E402
import messages  # noqa: E402

SOURCE = Path(__file__).resolve().parents[2] / "tools" / "flow_import.py"
VALEURS = {"read": 1, "inserted": 2, "updated": 3, "unchanged": 4, "unreadable": 5, "teams": 6, "links_added": 7,
           "links_removed": 8, "added": 9, "orphans": 10, "marked": 11, "file": "a.csv", "column": "Col", "path": "p/c.json",
           "name": "ValueError"}


class CataloguesImport(unittest.TestCase):
    def test_deux_langues(self):
        self.assertEqual(set(fim.CATALOGS), {"fr", "en"})

    def test_memes_cles_dans_les_deux_langues(self):
        self.assertEqual(set(fim.CATALOGS["fr"]), set(fim.CATALOGS["en"]))

    def test_controle_de_coherence_de_messages_py(self):
        self.assertEqual(messages.check_catalogs(fim.CATALOGS), [])

    def test_memes_champs_dans_les_deux_langues(self):
        for cle, texte in fim.CATALOGS["fr"].items():
            self.assertEqual(messages.fields(texte), messages.fields(fim.CATALOGS["en"][cle]), cle)

    def test_chaque_message_se_formate_dans_les_deux_langues(self):
        for langue in ("fr", "en"):
            t = messages.Messages(fim.CATALOGS, langue)
            for cle in fim.CATALOGS[langue]:
                champs = messages.fields(fim.CATALOGS[langue][cle])
                texte = t(cle, **{c: VALEURS[c] for c in champs})
                self.assertTrue(texte.strip(), cle)
                self.assertNotRegex(texte, r"\{[a-z_]+\}", cle)

    def test_valeurs_inserees(self):
        valeurs = dict(read=1, inserted=2, updated=3, unchanged=4, unreadable=5)
        self.assertIn("inserted: 2", messages.Messages(fim.CATALOGS, "en")("tickets_summary", **valeurs))
        self.assertIn("insérés : 2", messages.Messages(fim.CATALOGS, "fr")("tickets_summary", **valeurs))

    def test_erreurs_d_export_disent_que_rien_n_est_ecrit(self):
        for langue, phrase in (("fr", "Rien n'a été écrit"), ("en", "Nothing was written")):
            for cle in ("column_missing", "updated_unreadable"):
                self.assertIn(phrase, fim.CATALOGS[langue][cle], f"{langue}/{cle}")

    def test_aucun_champ_de_donnee_de_ticket(self):
        autorises = set(VALEURS)
        for langue, catalogue in fim.CATALOGS.items():
            for cle, texte in catalogue.items():
                self.assertLessEqual(messages.fields(texte), autorises, f"{langue}/{cle}")

    def test_toutes_les_cles_employees_par_flow_import_existent(self):
        employees = set(re.findall(r"\bt\(\s*\"([a-z_]+)\"", SOURCE.read_text(encoding="utf-8")))
        self.assertTrue(employees)
        self.assertLessEqual(employees, set(fim.CATALOGS["fr"]))


if __name__ == "__main__":
    unittest.main()
