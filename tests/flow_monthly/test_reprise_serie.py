"""
Tests de la reprise du suivi mensuel (change flow-monthly-resume, #367) : date de la série (D1, D2), avertissement de réécriture (D6).
Le rapport de flux manquant avant la comparaison (D3) et la sortie 66 d'un outil (D5, code 6) sont retirés avec les étapes de
comparaison (change database-only, D8) : tout code non nul donne le code 1. Faux outils, réglages inventés, aucune donnée réelle
(aide_flow_monthly.py).

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/flow_monthly -q -f
"""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_flow_monthly import Decor, MARQUES, SERIE_1, SERIE_2, aujourdhui  # noqa: E402

EXPORT_OK = "| export | - | passed | 0 | 1 |\n"
EXPORT_SAUTE = "| export | - | skipped | - | - |\n"


def jour_du_mois(rang: int) -> str:
    """Le `rang`-ième jour du mois en cours (1 = le premier), strictement avant aujourd'hui ; sinon le test est sauté."""
    aujourd = dt.date.today()
    if rang >= aujourd.day:
        raise unittest.SkipTest("le test a besoin de jours du mois antérieurs à aujourd'hui")
    return aujourd.replace(day=rang).isoformat()


class AvecSeries(Decor):
    def serie_en_cours(self, jour: str, final: str = "stopped at import") -> None:
        self.resume_ecrit(jour, final, EXPORT_OK)

    def sans_nom(self, r) -> None:
        texte = self.toute_la_sortie_et_le_resume(r)
        for marque in MARQUES:
            self.assertNotIn(marque, texte)
        self.assertNotIn("Flux-Lab/exports", texte)
        self.assertNotIn("Traceback", texte)

    def lignes_de_sortie(self, r) -> list[str]:
        return [l for l in r.sortie.splitlines() if l.strip()]


class DateDeLaSerie(AvecSeries):
    def test_reprise_d_un_jour_anterieur(self):
        d = jour_du_mois(1)
        self.serie_en_cours(d)
        r = self.lancer_en("--from", "import")
        self.assertEqual(r.code, 0, r.sortie)
        self.assertIn(f"Resuming the series of {d}", r.sortie)
        self.assertEqual(self.outils_appeles()[0], "flow_import")
        for appel in self.appels():
            if appel["outil"] == "flow_import":
                self.assertEqual(appel["args"], ["--mark-absent", "--language", "en"])     # aucun chemin : la date ne paraît pas
        self.assertTrue((self.rapports / f"suivi-mensuel-{d}.md").exists())
        self.assertFalse((self.rapports / f"suivi-mensuel-{aujourdhui()}.md").exists())
        self.sans_nom(r)

    def test_le_resume_d_une_reprise_par_defaut_ne_decide_pas_la_date(self):
        d = jour_du_mois(1)
        self.serie_en_cours(d)
        self.resume_ecrit(aujourdhui(), "stopped at history", EXPORT_SAUTE)
        r = self.lancer_en("--from", "import")
        self.assertEqual(r.code, 0, r.sortie)
        self.assertIn(f"Resuming the series of {d}", r.sortie)

    def test_dernier_run_complet(self):
        d = jour_du_mois(1)
        self.serie_en_cours(d, "complete")
        r = self.lancer_en("--force", "--from", "dashboard")
        self.assertEqual(r.code, 0, r.sortie)
        self.assertIn(f"Resuming the series of {d}", r.sortie)
        self.assertTrue((self.rapports / f"suivi-mensuel-{d}.md").exists())

    def test_une_serie_en_cours_apres_le_dernier_complet(self):
        d1, d2, d3 = jour_du_mois(1), jour_du_mois(2), jour_du_mois(3)
        self.serie_en_cours(d1, "stopped at flow")
        self.serie_en_cours(d2, "complete")
        self.serie_en_cours(d3, "stopped at import")
        r = self.lancer_en("--force", "--from", "import")
        self.assertEqual(r.code, 0, r.sortie)
        self.assertIn(f"Resuming the series of {d3}", r.sortie)

    def test_un_resume_d_un_autre_mois_ne_decide_pas(self):
        autre = (dt.date.today().replace(day=1) - dt.timedelta(days=1)).isoformat()
        self.serie_en_cours(autre)
        r = self.lancer_en("--from", "import")
        self.assertEqual(r.code, 2, r.sortie)
        self.assertEqual(self.appels(), [])

    def test_date_explicite_prime(self):
        d = jour_du_mois(1)
        self.serie_en_cours(jour_du_mois(2))
        r = self.lancer_en("--from", "flow", "--date", d)
        self.assertEqual(r.code, 0, r.sortie)
        self.assertNotIn("Resuming the series", r.sortie)
        self.assertTrue((self.rapports / f"suivi-mensuel-{d}.md").exists())

    def test_run_sans_from_garde_la_date_du_jour(self):
        self.serie_en_cours(jour_du_mois(1))
        r = self.lancer_en()
        self.assertEqual(r.code, 0, r.sortie)
        self.assertNotIn("Resuming the series", r.sortie)

    def test_passage_a_blanc_d_une_reprise(self):
        d = jour_du_mois(1)
        self.serie_en_cours(d)
        r = self.lancer_en("--dry-run", "--from", "import")
        self.assertEqual(r.code, 0, r.sortie)
        lignes = self.lignes_de_sortie(r)
        self.assertEqual(lignes[0], f"Resuming the series of {d}")
        for ligne in lignes[1:]:
            self.assertTrue(ligne.startswith("dry run: would run"), ligne)
        self.assertEqual(self.appels(), [])
        self.assertEqual([p.name for p in self.rapports.glob("suivi-mensuel-*")], [f"suivi-mensuel-{d}.md"])


class SerieIndecidable(AvecSeries):
    def test_deux_series_en_cours(self):
        d1, d2 = jour_du_mois(1), jour_du_mois(2)
        self.serie_en_cours(d1, "stopped at flow")
        self.serie_en_cours(d2, "stopped at import")
        r = self.lancer_en("--from", "import")
        self.assertEqual(r.code, 2, r.sortie)
        self.assertIn("Series in progress ambiguous", r.sortie)
        self.assertIn(f"{d1}, {d2}", r.sortie)
        self.assertIn("--date", r.sortie)
        self.assertEqual(self.appels(), [])
        self.assertEqual(len(list(self.rapports.glob("suivi-mensuel-*"))), 2)
        self.sans_nom(r)

    def test_refus_en_francais(self):
        self.serie_en_cours(jour_du_mois(1), "stopped at flow")
        self.serie_en_cours(jour_du_mois(2), "stopped at import")
        r = self.lancer("--from", "import")
        self.assertEqual(r.code, 2, r.sortie)
        self.assertIn("Série en cours ambiguë", r.sortie)
        self.assertNotIn("Series in progress", r.sortie)

    def test_aucune_serie_en_cours(self):
        r = self.lancer_en("--from", "flow")
        self.assertEqual(r.code, 2, r.sortie)
        self.assertIn("No series in progress this month", r.sortie)
        self.assertEqual(self.appels(), [])
        self.assertFalse(list(self.rapports.glob("suivi-mensuel-*")))

    def test_aucune_serie_en_francais(self):
        r = self.lancer("--from", "flow")
        self.assertEqual(r.code, 2, r.sortie)
        self.assertIn("Aucune série en cours ce mois-ci", r.sortie)


class CodesRetires(AvecSeries):
    """Database-only : les codes 4 (écart de parité) et 6 (entrée manquante) n'existent plus ; tout code non nul d'un outil donne 1."""

    def test_un_outil_qui_sort_avec_66_arrete_avec_le_code_1(self):
        d = jour_du_mois(1)
        self.codes(flux_jira=66)
        r = self.lancer_en("--from", "flow", "--date", d)
        self.assertEqual(r.code, 1, r.sortie)
        self.assertIn("Stopped at step flow: exit code 66", r.sortie)
        self.assertIn(f"--from flow --date {d}", r.sortie)
        self.assertNotIn("Missing input", r.sortie)
        self.assertEqual(self.outils_appeles(), ["flux_jira"])
        self.assertIn("| flow | 1 | failed | 66 |", self.resume(d))
        self.sans_nom(r)

    def test_message_en_francais(self):
        d = jour_du_mois(1)
        self.codes(flux_jira=66)
        r = self.lancer("--from", "flow", "--date", d)
        self.assertEqual(r.code, 1, r.sortie)
        self.assertIn("Arrêt à l'étape flow : code de sortie 66", r.sortie)
        self.assertNotIn("Entrée manquante", r.sortie)

    def test_autre_echec_inchange(self):
        d = jour_du_mois(1)
        self.codes(flux_jira=1)
        r = self.lancer_en("--from", "flow", "--date", d)
        self.assertEqual(r.code, 1, r.sortie)
        self.assertIn("Stopped at step flow: exit code 1", r.sortie)

    def test_l_orchestrateur_ne_teste_pas_l_export(self):
        d = jour_du_mois(1)
        r = self.lancer_en("--from", "flow", "--date", d)         # aucun export n'existe : l'outil seul pourrait le dire
        self.assertEqual(r.code, 0, r.sortie)
        self.assertEqual(self.outils_appeles()[0], "flux_jira")


class AvertissementDeReecriture(AvecSeries):
    def avant_la_premiere_etape(self, sortie: str, phrase: str) -> None:
        self.assertIn(phrase, sortie)
        self.assertLess(sortie.index(phrase), sortie.index("Step 1/"))

    def test_date_explicite_d_une_serie_existante(self):
        d = jour_du_mois(1)
        self.serie_en_cours(d)
        r = self.lancer_en("--from", "flow", "--date", d)
        self.assertEqual(r.code, 0, r.sortie)
        self.avant_la_premiere_etape(r.sortie, f"Warning: the reports of {d} will be rewritten")
        self.assertNotIn("Resuming the series", r.sortie)

    def test_date_decidee_par_la_regle_de_serie(self):
        d = jour_du_mois(1)
        self.serie_en_cours(d, "complete")
        r = self.lancer_en("--force", "--from", "flow")
        self.assertEqual(r.code, 0, r.sortie)
        self.avant_la_premiere_etape(r.sortie, f"Resuming the series of {d}")
        self.avant_la_premiere_etape(r.sortie, f"Warning: the reports of {d} will be rewritten")
        self.assertLess(r.sortie.index("Resuming the series"), r.sortie.index("Warning: the reports of"))

    def test_apres_l_avertissement_du_mode_detaille(self):
        d = jour_du_mois(1)
        self.serie_en_cours(d)
        r = self.lancer_en("--verbose", "--from", "flow", "--date", d)
        self.assertEqual(r.code, 0, r.sortie)
        self.assertLess(r.sortie.index("Verbose mode"), r.sortie.index("Warning: the reports of"))

    def test_date_sans_resume(self):
        r = self.lancer_en("--from", "flow", "--date", jour_du_mois(1))
        self.assertEqual(r.code, 0, r.sortie)
        self.assertNotIn("Warning: the reports of", r.sortie)

    def test_pas_d_avertissement_pour_la_date_du_jour(self):
        r = self.lancer_en()
        self.assertNotIn("Warning: the reports of", r.sortie)

    def test_avertissement_en_francais(self):
        d = jour_du_mois(1)
        self.serie_en_cours(d)
        r = self.lancer("--from", "flow", "--date", d)
        self.assertIn(f"Attention : les rapports du {d} seront réécrits", r.sortie)
        self.assertNotIn("Warning:", r.sortie)


if __name__ == "__main__":
    unittest.main()
