"""
Tests de tools/flow_export_reader.py : lecture des CSV factices, sans base.

    uv run --with numpy --with pyyaml python -m unittest discover -s tests/flow_import -v
"""
import datetime as dt
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import csv_factices as cf
import flow_export_reader as lecteur


class Lecteur(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dossier = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def lire(self, lignes, nom="a.csv", entete=None, **surcharges):
        chemin = cf.ecrire(self.dossier / nom, lignes, entete)
        return lecteur.lire_exports([str(chemin)], cf.reglages(**surcharges))

    def test_ligne_complete(self):
        r = self.lire([cf.ligne("PROJ-1", Resolved="10/Jul/2026 14:05", Resolution="Done", **{"Story Points": "3,5"},
                                **{"Parent key": "PROJ-9"})])
        t = r["tickets"][0]
        self.assertEqual((t["cle"], t["projet"], t["type"], t["etat"], t["categorie"], t["motif"], t["parent"]),
                         ("PROJ-1", "PROJ", "Story", "In Progress", "In Progress", "Done", "PROJ-9"))
        self.assertEqual(t["points"], Decimal("3.5"))
        self.assertEqual(t["cree"].utcoffset(), dt.timedelta(hours=1))       # hiver, Europe/Paris
        self.assertEqual(t["resolu"].utcoffset(), dt.timedelta(hours=2))     # été
        self.assertEqual(t["resolu"].astimezone(dt.timezone.utc).hour, 12)

    def test_date_relative_des_tests_avec_base_lue_comme_instant_attendu(self):
        """Les tests avec base datent la résolution d'il y a 30 jours (cf.jour_relatif) : le lecteur doit rendre l'instant que
        calcule cf.instant_utc, été comme hiver, sinon ces tests (sautés sans base) seraient faux sans qu'on le voie."""
        for jours in (30, 200, 330):
            jour = cf.jour_relatif(jours)
            t = self.lire([cf.ligne("PROJ-1", Resolved=cf.date_export(jour, 14, 5))])["tickets"][0]
            self.assertEqual(t["resolu"].astimezone(dt.timezone.utc), cf.instant_utc(jour, 14, 5), jours)

    def test_story_points(self):
        r = self.lire([cf.ligne("PROJ-1", **{"Story Points": "5"}), cf.ligne("PROJ-2", **{"Story Points": "0.5"}),
                       cf.ligne("PROJ-3", **{"Story Points": ""}), cf.ligne("PROJ-4", **{"Story Points": "abc"})])
        self.assertEqual([t["points"] for t in r["tickets"]], [Decimal("5"), Decimal("0.5"), None, None])

    def test_equipes_dedoublonnees_dans_l_ordre(self):
        r = self.lire([cf.ligne("PROJ-1", Team="Alpha; Beta", Team2="Alpha"), cf.ligne("PROJ-2", Team="")])
        self.assertEqual(r["tickets"][0]["equipes"], ["Alpha", "Beta"])
        self.assertEqual(r["tickets"][1]["equipes"], [])

    def test_liens_types_et_sans_type(self):
        r = self.lire([cf.ligne("PROJ-1", **{"Outward issue link (Blocks)": "PROJ-2", "Inward issue link (Blocks)": "PROJ-3",
                                             "Linked Issues": "PROJ-4 PROJ-2"})])
        self.assertEqual(set(r["tickets"][0]["liens"]),
                         {("PROJ-2", "Blocks", "outward"), ("PROJ-3", "Blocks", "inward"),
                          ("PROJ-4", "", None), ("PROJ-2", "", None)})

    def test_sans_colonne_de_liens_liens_non_suivis(self):
        entete = [c for c in cf.ENTETE if "link" not in c.lower() and "Linked" not in c]
        r = self.lire([cf.ligne("PROJ-1")], entete=entete)
        self.assertIsNone(r["tickets"][0]["liens"])

    def test_date_de_creation_illisible_ecartee(self):
        r = self.lire([cf.ligne("PROJ-1", Created="n'importe quoi"), cf.ligne("PROJ-2")])
        self.assertEqual((len(r["tickets"]), r["illisibles"]), (1, 1))

    def test_colonne_updated_absente(self):
        entete = [c for c in cf.ENTETE if c != "Updated"]
        with self.assertRaises(lecteur.ErreurExport) as cm:
            self.lire([cf.ligne("PROJ-1")], nom="export-a.csv", entete=entete)
        self.assertEqual((cm.exception.code, cm.exception.valeurs), ("column_missing", {"file": "export-a.csv", "column": "Updated"}))
        self.assertNotIn("PROJ", repr(cm.exception.valeurs))

    def test_updated_illisible_ou_vide_message_sans_valeur(self):
        for valeur in ("valeur-secrete-xyz", ""):
            with self.assertRaises(lecteur.ErreurExport) as cm:
                self.lire([cf.ligne("PROJ-1", Updated=valeur)], nom="export-b.csv")
            self.assertEqual(cm.exception.code, "updated_unreadable")
            self.assertEqual(cm.exception.valeurs, {"file": "export-b.csv", "column": "Updated"})

    def test_deux_fichiers_le_dernier_l_emporte(self):
        a = cf.ecrire(self.dossier / "a.csv", [cf.ligne("PROJ-1", Status="Open"), cf.ligne("PROJ-2")])
        b = cf.ecrire(self.dossier / "b.csv", [cf.ligne("PROJ-1", Status="Done"), cf.ligne("PROJ-3")])
        r = lecteur.lire_exports([str(a), str(b)], cf.reglages())
        etats = {t["cle"]: t["etat"] for t in r["tickets"]}
        self.assertEqual(etats, {"PROJ-1": "Done", "PROJ-2": "In Progress", "PROJ-3": "In Progress"})

    def test_fichier_absent(self):
        with self.assertRaises(lecteur.ErreurExport) as cm:
            lecteur.lire_exports([str(self.dossier / "absent.csv")], cf.reglages())
        self.assertEqual(cm.exception.code, "file_unreadable")


if __name__ == "__main__":
    unittest.main()
