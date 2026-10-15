"""Format du cache d'historique étendu (R-58, tâches 6.1 et 6.2) : lecture commune par history_common.lire_cache.

    bash tests/run_all.sh history_jira

Données inventées. Un ancien cache (sans résolu, vu_le, versions, etiquettes) reste lisible ; les événements sont triés par instant.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import history_common as commun  # noqa: E402


def lire(contenu: dict) -> dict:
    with tempfile.TemporaryDirectory() as d:
        chemin = Path(d) / "transitions.json"
        chemin.write_text(json.dumps(contenu), encoding="utf-8")
        return commun.lire_cache(chemin)


class FormatCache(unittest.TestCase):
    def test_ancien_cache_lu_avec_des_valeurs_vides(self):
        cache = lire({"PROJ-1": {"termine": True, "transitions": [["2026-03-01T09:00:00.000+0200", "Open", "Done"]]}})
        entree = cache["PROJ-1"]
        self.assertTrue(entree["termine"])
        self.assertEqual(len(entree["transitions"]), 1)
        self.assertIsNone(entree["resolu"])
        self.assertIsNone(entree["vu_le"])
        self.assertEqual(entree["versions"], [])
        self.assertEqual(entree["etiquettes"], [])

    def test_cles_nouvelles_lues_et_evenements_tries_par_instant(self):
        cache = lire({"PROJ-1": {
            "termine": True, "transitions": [], "resolu": "2026-03-05T10:00:00.000+0100", "vu_le": "2026-10-13",
            "versions": [["2026-03-04T10:00:00.000+0100", "add", "V-B"], ["2026-03-02T10:00:00.000+0100", "add", "V-A"]],
            "etiquettes": [["2026-03-03T09:00:00.000+0100", "remove", "L-1"], ["2026-03-01T09:00:00.000+0100", "add", "L-1"]]}})
        entree = cache["PROJ-1"]
        self.assertEqual(entree["resolu"], "2026-03-05T10:00:00.000+0100")
        self.assertEqual(entree["vu_le"], "2026-10-13")
        self.assertEqual([e[2] for e in entree["versions"]], ["V-A", "V-B"])
        self.assertEqual([e[1] for e in entree["etiquettes"]], ["add", "remove"])

    def test_evenement_mal_forme_ecarte(self):
        cache = lire({"PROJ-1": {"termine": False, "transitions": [],
                                 "versions": [["2026-03-04T10:00:00.000+0100", "move", "V-A"], ["x"], "texte"]}})
        self.assertEqual(cache["PROJ-1"]["versions"], [])


if __name__ == "__main__":
    unittest.main()
