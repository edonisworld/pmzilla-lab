"""tools/history_common.py : lecteur partagé du point d'engagement (change flow-definitions-loader, tâche 2.3, conception D2 ; spec jira-flow-config,
exigence « The commitment point default is read through one shared reader »).

Sans réglage, le lecteur rend la constante POINT_ENGAGEMENT_PAR_DEFAUT ; avec un réglage, il le rend. Les réglages par défaut du rapport de
flux tiennent cette même constante (identité). Noms de segments inventés.

    bash tests/run_all.sh history_jira
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import flux_jira  # noqa: E402
import history_common as commun  # noqa: E402


class PointEngagement(unittest.TestCase):
    def test_sans_reglage_la_constante(self):
        self.assertIs(commun.point_engagement({}), commun.POINT_ENGAGEMENT_PAR_DEFAUT)
        self.assertIs(commun.point_engagement({"point_engagement": None}), commun.POINT_ENGAGEMENT_PAR_DEFAUT)
        self.assertIs(commun.point_engagement({"point_engagement": ""}), commun.POINT_ENGAGEMENT_PAR_DEFAUT)

    def test_reglage_donne_rendu_tel_quel(self):
        self.assertEqual(commun.point_engagement({"point_engagement": "t-segment"}), "t-segment")

    def test_les_reglages_par_defaut_du_rapport_de_flux_tiennent_la_constante(self):
        self.assertIs(flux_jira.DEFAULT_CONFIG["point_engagement"], commun.POINT_ENGAGEMENT_PAR_DEFAUT)
        self.assertEqual(commun.point_engagement(flux_jira.DEFAULT_CONFIG), commun.POINT_ENGAGEMENT_PAR_DEFAUT)


if __name__ == "__main__":
    unittest.main()
