"""Idée #169 (change jira-data-architecture, D9) : une seule règle du fuseau d'export pour les trois outils restants (le
lecteur d'export CSV a disparu avec la voie CSV, change database-only).

    uv run --with pyyaml --with numpy --with requests --with "psycopg[binary]" python -m unittest discover -s tests/flux_jira -v

Tâche 4.1 : caractérisation, verte sur le code d'avant la factorisation et inchangée après (fuseau par défaut, fuseau réglé,
décalages d'été et d'hiver, fuseau inconnu avec le message et le code de chaque outil).
Tâche 4.2 : test croisé, les quatre outils donnent les mêmes décalages pour les mêmes réglages.
Réglages et dates inventés.
"""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import export_jira_api as ex        # noqa: E402
import flow_store                   # noqa: E402
import flux_jira as fj              # noqa: E402
from messages import Messages       # noqa: E402

ETE = dt.datetime(2026, 7, 1, 12, 0)
HIVER = dt.datetime(2026, 1, 15, 12, 0)
REGLAGES = [({}, 2, 1), ({"export_fuseau": "Europe/Paris"}, 2, 1), ({"export_fuseau": "UTC"}, 0, 0),
            ({"export_fuseau": "America/New_York"}, -4, -5)]


def heures(zone, naif):
    return naif.replace(tzinfo=zone).utcoffset() / dt.timedelta(hours=1)


def quatre_fuseaux(reglages):
    tr = Messages(fj.CATALOGS, "fr")
    return {"export": ex.fuseau_export(reglages), "store": flow_store.fuseau_export(reglages),
            "flux": fj.fuseau_des_reglages(reglages, tr)}


class CaracterisationFlux(unittest.TestCase):
    def test_defaut_reglage_et_decalages(self):
        tr = Messages(fj.CATALOGS, "fr")
        for reglages, ete, hiver in REGLAGES:
            zone = fj.fuseau_des_reglages(reglages, tr)
            self.assertEqual((heures(zone, ETE), heures(zone, HIVER)), (ete, hiver), reglages)

    def test_fuseau_inconnu_message_et_sortie(self):
        tr = Messages(fj.CATALOGS, "fr")
        with self.assertRaises(SystemExit) as ctx:
            fj.fuseau_des_reglages({"export_fuseau": "Mars/Olympus"}, tr)
        self.assertEqual(ctx.exception.code, tr("cycles_timezone_unknown"))
        self.assertNotIn("Mars", str(ctx.exception.code))


class TestCroise(unittest.TestCase):
    """Tâche 4.2 : mêmes réglages, mêmes décalages dans les quatre outils."""

    def test_memes_decalages_pour_les_memes_reglages(self):
        for reglages, ete, hiver in REGLAGES:
            for outil, zone in quatre_fuseaux(reglages).items():
                self.assertEqual((heures(zone, ETE), heures(zone, HIVER)), (ete, hiver), (outil, reglages))

    def test_un_seul_fuseau_nomme(self):
        for reglages, _, _ in REGLAGES:
            noms = {str(zone) for zone in quatre_fuseaux(reglages).values()}
            self.assertEqual(len(noms), 1, reglages)

    def test_aucun_outil_ne_garde_sa_copie(self):
        """La règle (lecture du réglage, défaut, ZoneInfo) vit dans history_common seulement."""
        for chemin in ("export_jira_api.py", "flow_store.py", "flux_jira.py"):
            source = (Path(__file__).resolve().parents[2] / "tools" / chemin).read_text(encoding="utf-8")
            self.assertFalse('get("export_fuseau")' in source, chemin)       # assertFalse : pas de source entière dans le message


if __name__ == "__main__":
    unittest.main()
