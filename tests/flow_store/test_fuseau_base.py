"""Idée #169 (D9), tâche 4.1 : caractérisation du fuseau d'export des lecteurs de la base, verte avant et après la factorisation.
Sans base : la fonction ne se connecte pas.

    uv run --with numpy --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_store -v
"""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import db  # noqa: E402
import flow_store  # noqa: E402

ETE = dt.datetime(2026, 7, 1, 12, 0)
HIVER = dt.datetime(2026, 1, 15, 12, 0)
REGLAGES = [({}, 2, 1), ({"export_fuseau": "Europe/Paris"}, 2, 1), ({"export_fuseau": "UTC"}, 0, 0),
            ({"export_fuseau": "America/New_York"}, -4, -5)]


def heures(zone, naif):
    return naif.replace(tzinfo=zone).utcoffset() / dt.timedelta(hours=1)


class CaracterisationBase(unittest.TestCase):
    def test_defaut_reglage_et_decalages(self):
        for reglages, ete, hiver in REGLAGES:
            zone = flow_store.fuseau_export(reglages)
            self.assertEqual((heures(zone, ETE), heures(zone, HIVER)), (ete, hiver), reglages)

    def test_fuseau_inconnu_erreur_de_base_nommant_le_fuseau(self):
        with self.assertRaises(db.ErreurBase) as ctx:
            flow_store.fuseau_export({"export_fuseau": "Mars/Olympus"})
        self.assertEqual(str(ctx.exception),
                         "export_timezone « Mars/Olympus » n'est pas un fuseau horaire connu (exemple : Europe/Paris).")


if __name__ == "__main__":
    unittest.main()
