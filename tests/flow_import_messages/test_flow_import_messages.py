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
           "links_removed": 8, "label_periods": 12, "version_periods": 13, "refused": 14, "skipped": 15, "back": 16, "percent": "20", "added": 9, "orphans": 10, "marked": 11, "file": "a.csv", "column": "Col", "path": "p/c.json",
           "name": "ValueError", "n": 17, "d": 18, "k": 19, "field": "status"}


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

    def test_lignes_du_groupe_8_aux_phrases_de_la_conception(self):
        """Phrases clés fixées par le design D19 (jeu incomplet, tickets sortis de l'export, au-delà de la conservation)."""
        en, fr = messages.Messages(fim.CATALOGS, "en"), messages.Messages(fim.CATALOGS, "fr")
        self.assertEqual(en("out_of_export", marked=1, back=0), "Tickets out of the export: 1 marked, 0 back")
        self.assertEqual(fr("out_of_export", marked=1, back=0), "Tickets sortis de l'export : 1 marqués, 0 revenus")
        self.assertEqual(en("gone_sighted", n=2), "tickets marked gone, sighted again by the export: 2")
        self.assertEqual(fr("gone_sighted", n=2), "tickets marqués disparus, revus par l'export : 2")
        self.assertEqual(en("incomplete_set"), "incomplete export set: --mark-absent refused")
        self.assertEqual(fr("incomplete_set"), "jeu d'exports incomplet : --mark-absent refusé")
        self.assertEqual(en("partial_run"), "last export run limited to one query (--query): run a complete export first, without --query")
        self.assertEqual(fr("partial_run"), "dernier passage d'export limité à une requête (--query) : lancez d'abord un passage "
                                            "complet de l'export, sans --query")
        self.assertEqual(en("past_retention", skipped=1), "tickets past retention, skipped: 1")
        self.assertEqual(fr("past_retention", skipped=1), "tickets au-delà de la conservation, ignorés : 1")

    def test_jeu_incomplet_ne_nomme_ni_requete_ni_fichier(self):
        for langue in ("fr", "en"):
            self.assertEqual(messages.fields(fim.CATALOGS[langue]["incomplete_set"]), set())

    def test_phrases_du_seuil_et_de_l_export_vide(self):
        en, fr = messages.Messages(fim.CATALOGS, "en"), messages.Messages(fim.CATALOGS, "fr")
        self.assertEqual(en("empty_export"), "empty export: --mark-absent refused")
        self.assertEqual(fr("empty_export"), "export vide : --mark-absent refusé")
        self.assertIn("more than 20% of stored tickets", en("absent_share_exceeded", percent="20"))
        self.assertIn("plus de 20 % des tickets stockés", fr("absent_share_exceeded", percent="20"))
        for langue in ("fr", "en"):
            self.assertIn("--max-absent-percent", fim.CATALOGS[langue]["absent_share_exceeded"])     # comment relancer volontairement
            self.assertEqual(messages.fields(fim.CATALOGS[langue]["empty_export"]), set())
            self.assertEqual(messages.fields(fim.CATALOGS[langue]["absent_share_exceeded"]), {"percent"})

    def test_phrases_de_la_conception_d6_pour_les_fichiers_et_l_historique_retires(self):
        """Design D6 (database-only) : l'import refuse un fichier d'export et --history (code 2), sans nommer de fichier."""
        en, fr = messages.Messages(fim.CATALOGS, "en"), messages.Messages(fim.CATALOGS, "fr")
        self.assertEqual(en("export_files_retired"), "export files are no longer read: the import derives from the raw layer")
        self.assertEqual(fr("export_files_retired"), "les fichiers d'export ne sont plus lus : l'import part de la couche brute")
        self.assertEqual(en("history_retired"), "--history is retired: the history collection writes the transitions")
        self.assertEqual(fr("history_retired"), "--history est retirée : la collecte de l'historique écrit les transitions")
        self.assertEqual(en("no_new_run"), "raw layer: no new run to apply")
        self.assertEqual(fr("no_new_run"), "couche brute : aucun nouveau passage à appliquer")
        for langue in ("fr", "en"):
            for cle in ("export_files_retired", "history_retired", "no_new_run"):
                self.assertEqual(messages.fields(fim.CATALOGS[langue][cle]), set(), f"{langue}/{cle}")

    def test_plus_de_message_de_fichier_ni_de_cache(self):
        for langue, catalogue in fim.CATALOGS.items():
            for cle in ("column_missing", "updated_unreadable", "file_unreadable", "file_empty", "cache_missing",
                        "cache_unreadable", "transitions_summary", "periods_summary", "labels_refused", "timezone_unknown"):
                self.assertNotIn(cle, catalogue, f"{langue}/{cle}")

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
