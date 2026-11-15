"""
Les trois derniers trimestres clos (change de trois trimestres clos, R-20261114-45, -49, -51 ; conception D2, D3, D5).

    - trois_trimestres_clos : la fonction pure de fenêtre de tools/flow_views.py, essayée sur chaque jour UTC de 2027 à 2030 (2028 est bissextile) ;
    - la limite déclarée de D3 dans la description de chaque vue trimestrielle de `list` et dans l'aide, en français et en anglais.

Sans base : aucune lecture de vue. Le calcul attendu est refait ici à la main (numéro de trimestre), jamais lu dans la fonction essayée.
"""
import contextlib
import io
import json
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402
import flux_config as cfg  # noqa: E402
from flow_views_messages import CATALOGS  # noqa: E402

LIMITE_FR = "le plus ancien des trois trimestres peut perdre au plus un jour et quelques heures les derniers jours d'un trimestre (environ 1 %)"
LIMITE_EN = "the oldest of the three quarters may lose at most one day and a few hours on the last days of a quarter (about 1 %)"
VUES_TRIMESTRIELLES = ("v_team_fix_version_share", "v_team_fix_version_lag", "v_team_lead_time_throughput", "v_task_without_team_share",
                       "v_team_ready_queue", "v_team_blocked_share", "v_unplanned_share", "v_team_flow_inout", "v_team_delivery_fields_coverage")


def jours(debut: date, fin: date):
    jour = debut
    while jour <= fin:
        yield jour
        jour += timedelta(days=1)


def attendus_a_la_main(jour: date) -> list[date]:
    """Les trois débuts : numéro de trimestre de `jour` (année * 4 + trimestre), moins 1, 2 et 3, le plus récent d'abord."""
    numero = jour.year * 4 + (jour.month - 1) // 3
    return [date(n // 4, 3 * (n % 4) + 1, 1) for n in (numero - 1, numero - 2, numero - 3)]


class FenetreTroisTrimestres(unittest.TestCase):
    def test_trois_debuts_chaque_jour_de_2027_a_2030(self):
        for jour in jours(date(2027, 1, 1), date(2030, 12, 31)):
            instant = datetime(jour.year, jour.month, jour.day, 23, 59, 59, tzinfo=timezone.utc)
            debuts = fv.trois_trimestres_clos(instant)
            self.assertEqual(debuts, attendus_a_la_main(jour), jour)
            self.assertEqual(len(set(debuts)), 3, jour)
            premier_du_courant = date(jour.year, 3 * ((jour.month - 1) // 3) + 1, 1)
            self.assertNotIn(premier_du_courant, debuts, jour)           # le trimestre en cours n'est jamais lu
            self.assertTrue(all(d < premier_du_courant for d in debuts), jour)

    def test_le_plus_ancien_n_est_pas_plus_vieux_que_la_duree_de_conservation_plus_un_jour(self):
        borne = timedelta(days=cfg.PERIODE_MAX_JOURS + 1)
        for jour in jours(date(2027, 1, 1), date(2030, 12, 31)):
            plus_ancien = fv.trois_trimestres_clos(datetime(jour.year, jour.month, jour.day, tzinfo=timezone.utc))[-1]
            self.assertGreaterEqual(plus_ancien, jour - borne, jour)

    def test_ancres_fixes(self):
        self.assertEqual(fv.trois_trimestres_clos(datetime(2027, 3, 31, 23, 0, tzinfo=timezone.utc)),
                         [date(2026, 10, 1), date(2026, 7, 1), date(2026, 4, 1)])               # dernier jour d'un trimestre
        self.assertEqual(fv.trois_trimestres_clos(datetime(2027, 4, 1, 0, 0, tzinfo=timezone.utc)),
                         [date(2027, 1, 1), date(2026, 10, 1), date(2026, 7, 1)])               # premier jour d'un trimestre
        self.assertEqual(fv.trois_trimestres_clos(datetime(2028, 2, 29, 12, 0, tzinfo=timezone.utc)),
                         [date(2027, 10, 1), date(2027, 7, 1), date(2027, 4, 1)])               # 29 février 2028

    def test_parite_sur_la_liste_de_jours_partagee_avec_typescript(self):
        """Parité (D2, tâche 2.3) : la liste de jours et ses attendus, écrits à la main, sont dans un fichier lu aussi par le test TypeScript de
        fenetreTroisTrimestres (mothra/contract/test/trimestres-date-donnees.test.ts) ; chaque langue compare sa fonction aux mêmes attendus, donc les deux
        fonctions se valent sur ces jours. Remplace : rien. Retrait : avec la fonction de fenêtre."""
        cas = json.loads((RACINE / "mothra" / "contract" / "test-data" / "cas-fenetre-trois-trimestres.json").read_text(encoding="utf-8"))["cas"]
        self.assertEqual(len(cas), 48)                                                              # 16 trimestres, trois jours chacun
        for c in cas:
            jour = date.fromisoformat(c["jour"])
            attendus = [date.fromisoformat(d) for d in c["debuts"]]
            self.assertEqual(fv.trois_trimestres_clos(datetime(jour.year, jour.month, jour.day, 12, tzinfo=timezone.utc)), attendus, c["jour"])

    def test_un_instant_est_lu_en_utc(self):
        decale = timezone(timedelta(hours=-5))
        instant = datetime(2027, 3, 31, 21, 0, tzinfo=decale)                                     # le 1er avril 2027, 02:00 UTC
        self.assertEqual(fv.trois_trimestres_clos(instant), [date(2027, 1, 1), date(2026, 10, 1), date(2026, 7, 1)])


class LimiteDeclareeD3(unittest.TestCase):
    def liste(self, langue):
        sortie = io.StringIO()
        with mock.patch.object(fv, "seuil_configure", return_value=5), contextlib.redirect_stdout(sortie):
            self.assertEqual(fv.main(["--language", langue, "list"]), 0)
        return {l.split()[0]: l for l in sortie.getvalue().splitlines()[1:]}

    def test_chaque_vue_trimestrielle_porte_la_limite_dans_list(self):
        for langue, limite in (("fr", LIMITE_FR), ("en", LIMITE_EN)):
            lignes = self.liste(langue)
            for vue in VUES_TRIMESTRIELLES:
                self.assertIn(vue, lignes)
                self.assertIn(limite, lignes[vue], (langue, vue))

    def test_les_autres_vues_ne_la_portent_pas(self):
        for langue, limite in (("fr", LIMITE_FR), ("en", LIMITE_EN)):
            for vue, ligne in self.liste(langue).items():
                if vue not in VUES_TRIMESTRIELLES:
                    self.assertNotIn(limite, ligne, (langue, vue))

    def test_l_aide_porte_la_limite_dans_les_deux_langues(self):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie), self.assertRaises(SystemExit):
            fv.main(["--help"])
        aide = " ".join(sortie.getvalue().split())
        self.assertIn(LIMITE_FR, aide)
        self.assertIn(LIMITE_EN, aide)

    def test_les_catalogues_ont_les_memes_cles(self):
        self.assertEqual(set(CATALOGS["fr"]), set(CATALOGS["en"]))


if __name__ == "__main__":
    unittest.main()
