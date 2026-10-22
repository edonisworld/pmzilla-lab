"""Idée #169 (D9), tâche 4.1 : caractérisation du fuseau d'export de export_jira_api.py, verte avant et après la factorisation.

    uv run --with pyyaml --with requests python -m unittest discover -s tests/export_jira_api -v
"""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import export_jira_api as ex  # noqa: E402

ETE = dt.datetime(2026, 7, 1, 12, 0)
HIVER = dt.datetime(2026, 1, 15, 12, 0)
REGLAGES = [({}, 2, 1), ({"export_fuseau": "Europe/Paris"}, 2, 1), ({"export_fuseau": "UTC"}, 0, 0),
            ({"export_fuseau": "America/New_York"}, -4, -5)]


def heures(zone, naif):
    return naif.replace(tzinfo=zone).utcoffset() / dt.timedelta(hours=1)


class CaracterisationExport(unittest.TestCase):
    def test_defaut_reglage_et_decalages(self):
        for reglages, ete, hiver in REGLAGES:
            zone = ex.fuseau_export(reglages)
            self.assertEqual((heures(zone, ETE), heures(zone, HIVER)), (ete, hiver), reglages)

    def test_fuseau_inconnu_arret_avec_le_nom_du_reglage_et_celui_du_fuseau(self):
        with self.assertRaises(ex.Arret) as ctx:
            ex.fuseau_export({"export_fuseau": "Mars/Olympus"})
        self.assertEqual(str(ctx.exception), ex.t("timezone_invalid", name="Mars/Olympus", example="Europe/Paris"))
        self.assertIn("export_timezone", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
