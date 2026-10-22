"""R-68 : les deux voies lisent les transitions dans le fuseau export_timezone, donc comptent les mêmes jours.

    uv run --with pyyaml --with numpy python -m unittest discover -s tests/flux_jira -v

Cause : le cache de history_jira.py garde le décalage d'origine de l'API (+0000 ci-dessous) et la voie CSV n'en lisait que le jour
(les 10 premiers caractères), alors que la voie base convertit chaque transition dans export_timezone, comme les dates `cree` et
`resolu` de l'export. Une transition proche de minuit change de jour d'une voie à l'autre : quelques jours de plus dans un segment,
donc une moyenne qui diffère (7,2 j contre 7,3 j) sans que le nombre de tickets, la médiane ni le P85 ne bougent. Jeu inventé.
"""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import chargeur_csv as chargeur  # noqa: E402
import flow_store  # noqa: E402
import flux_jira as fj  # noqa: E402
import history_common as commun  # noqa: E402

PARIS = ZoneInfo("Europe/Paris")
UTC = dt.timezone.utc
# (ticket, instant UTC, départ, arrivée) : la transition vers l'acceptation tombe à 23:30 UTC, soit 00:30 le lendemain à Paris
TRANSITIONS = [
    ("PROJ-1", dt.datetime(2026, 3, 5, 23, 30, 12, 345000, tzinfo=UTC), "Ready for Verification", "Ready for Acceptance"),
    ("PROJ-1", dt.datetime(2026, 3, 10, 12, 0, tzinfo=UTC), "Ready for Acceptance", "Done"),
]
TICKET = {"cle": "PROJ-1", "etat": "Done", "cree": dt.date(2026, 3, 1), "resolu": dt.date(2026, 3, 10)}


def jours_en_acceptation(histoire: list) -> int:
    periodes = fj.chronologie(TICKET, histoire, dt.date(2026, 3, 31))
    segment_de = {"ready for acceptance": "acceptation", "ready for verification": "revue_verification", "done": "fin"}
    return sum(v["jours"] for v in fj.visites(periodes, segment_de, ouvert=False) if v["segment"] == "acceptation")


def histoire_cache(dossier: Path, fuseau=None) -> list:
    """Le chargeur de test (cache JSON de fixture) ramène chaque date dans le fuseau, comme la base : voir test_la_fixture_*."""
    chemin = dossier / "transitions.json"
    chemin.write_text(json.dumps({"PROJ-1": {"termine": True, "transitions": [
        [t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}+0000", d, a] for _, t, d, a in TRANSITIONS]}}), encoding="utf-8")
    return chargeur.lire_historique({"export_fuseau": "Europe/Paris"}, str(chemin), fuseau)["PROJ-1"]


def histoire_base() -> list:
    with mock.patch.object(flow_store, "_lire", return_value=TRANSITIONS_BASE):
        return flow_store.lire_historique({"export_fuseau": "Europe/Paris"})["PROJ-1"]


TRANSITIONS_BASE = [(c, t, d, a) for c, t, d, a in TRANSITIONS]


class MemesJoursSurLesDeuxVoies(unittest.TestCase):
    def test_la_base_compte_le_jour_de_paris(self):
        self.assertEqual(jours_en_acceptation(histoire_base()), 4)             # 6 mars (Paris) -> 10 mars

    def test_la_fixture_de_test_compte_les_memes_jours(self):
        """Le chargeur de test (D11) convertit comme la base : les tests de rapport sur fixtures comptent les mêmes jours."""
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(jours_en_acceptation(histoire_cache(Path(d), PARIS)), 4)

    def test_conversion_de_la_fixture_identique_a_celle_de_la_base(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(histoire_cache(Path(d), PARIS), histoire_base())

    def test_lire_historique_lit_la_base_avec_les_reglages(self):
        lecture = mock.Mock(return_value={"PROJ-1": histoire_base()})
        with mock.patch.dict(sys.modules, {"flow_store": mock.Mock(lire_historique=lecture)}):
            lu = fj.lire_historique({"export_fuseau": "Europe/Paris"})
        lecture.assert_called_once_with({"export_fuseau": "Europe/Paris"})
        self.assertEqual(jours_en_acceptation(lu["PROJ-1"]), 4)

    def test_date_illisible_gardee_telle_quelle(self):
        self.assertEqual(commun.en_fuseau("pas une date", PARIS), "pas une date")
        self.assertIsNone(commun.en_fuseau(None, PARIS))

    def test_date_sans_decalage_gardee_telle_quelle(self):
        self.assertEqual(commun.en_fuseau("2026-03-05T23:30:00", PARIS), "2026-03-05T23:30:00")


if __name__ == "__main__":
    unittest.main()
