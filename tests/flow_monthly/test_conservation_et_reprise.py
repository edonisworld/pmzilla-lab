"""
Tests de tools/flow_monthly.py pour le change jira-gdpr-alignment (groupe 13) : ligne finale avec les comptes joués et sautés, statut
`skipped` du résumé, option de marquage de l'import et étape `retention` (essai à blanc de la purge). Faux outils (aide_flow_monthly.py).

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/flow_monthly -q -f
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_flow_monthly import Decor, REQUETE_1, REQUETE_2, aujourdhui, hier  # noqa: E402


class LigneFinale(Decor):
    def test_run_complet(self):
        r = self.lancer_en()
        self.assertEqual(r.code, 0, r.sortie)
        self.assertIn("Monthly run complete: 12 of 12 steps, 0 skipped", r.sortie)

    def test_run_repris_quatre_sur_douze(self):
        # plan de douze appels (deux séries) ; la reprise à compare-reports joue les quatre derniers et saute les huit premiers
        r = self.lancer_en("--from", "compare-reports")
        self.assertEqual(r.code, 0, r.sortie)
        self.assertIn("Monthly run complete: 4 of 12 steps, 8 skipped", r.sortie)
        self.assertNotIn("12 of 12", r.sortie)
        self.assertEqual(self.outils_appeles()[-1], "flow_retention")

    def test_reprise_a_compare_data(self):
        r = self.lancer_en("--from", "compare-data")
        self.assertIn("Monthly run complete: 5 of 12 steps, 7 skipped", r.sortie)

    def test_progression_numerotee_a_partir_de_un(self):
        r = self.lancer_en("--from", "compare-reports")
        for ligne in ("Step 1/4: compare-reports (series 1)", "Step 2/4: compare-reports (series 2)", "Step 3/4: dashboard",
                      "Step 4/4: retention"):
            self.assertIn(ligne, r.sortie)
        self.assertNotIn("Step 9/", r.sortie)

    def test_run_francais_repris(self):
        r = self.lancer("--from", "compare-reports")
        self.assertIn("Suivi mensuel terminé : 4 étapes sur 12, 8 sautées", r.sortie)
        self.assertNotIn("Monthly run", r.sortie)

    def test_requete_unique_et_serie_unique(self):
        self.ecrire_reglages("jql_export: project = AAA\nmonthly_run:\n  series:\n    - name: seulezz\n      dependencies: none\n")
        r = self.lancer_en()
        self.assertIn("Monthly run complete: 8 of 8 steps, 0 skipped", r.sortie)


class StatutSkipped(Decor):
    def test_reprise_sans_resume_anterieur(self):
        r = self.lancer_en("--from", "compare-data")
        self.assertEqual(r.code, 0, r.sortie)
        texte = self.resume()
        for etape, rang in (("export", "-"), ("history", "-"), ("import", "-"), ("flow", "1"), ("flow", "2"),
                            ("dependencies", "1"), ("dependencies", "2")):
            self.assertRegex(texte, rf"\| {etape} \| {rang} \| skipped \| - \| - \|")
        for etape in ("compare-data", "compare-reports", "dashboard", "retention"):
            self.assertRegex(texte, rf"\| {etape} \| (-|\d) \| passed \| 0 \|")
        self.assertNotIn("not run", texte)
        self.assertIn("- final status: complete", texte)

    def test_reprise_apres_un_arret_garde_passed_et_ne_saute_rien(self):
        self.codes(flow_import=1)
        self.lancer_en()
        self.codes_de({})
        r = self.lancer_en("--from", "import")
        self.assertEqual(r.code, 0, r.sortie)
        texte = self.resume()
        self.assertNotIn("skipped", texte)
        self.assertRegex(texte, r"\| export \| - \| passed \| 0 \|")
        self.assertRegex(texte, r"\| history \| - \| passed \| 0 \|")
        self.assertIn("- final status: complete", texte)
        self.assertIn("Monthly run complete: 10 of 12 steps, 2 skipped", r.sortie)    # le compte suit --from, pas le résumé

    def test_arret_apres_une_reprise_laisse_les_etapes_suivantes_not_run(self):
        self.codes(flow_compare__data=1)
        self.lancer_en("--from", "compare-data")
        texte = self.resume()
        self.assertRegex(texte, r"\| import \| - \| skipped \|")
        self.assertRegex(texte, r"\| compare-data \| - \| gap \| 1 \|")
        self.assertRegex(texte, r"\| retention \| - \| not run \|")
        self.assertIn("- final status: stopped at compare-data", texte)

    def test_le_mois_deja_fait_voit_un_resume_complet_avec_skipped(self):
        self.lancer_en("--from", "compare-data")                      # résumé complet qui contient des étapes skipped
        self.appels_vides()
        r = self.lancer_en()
        self.assertEqual(r.code, 5, r.sortie)
        self.assertIn("Monthly run already done this month", r.sortie)
        self.assertEqual(self.appels(), [])
        self.assertEqual(self.lancer_en("--force").code, 0)

    def appels_vides(self):
        (self.racine / "appels.jsonl").unlink()


class MarquageDeLImport(Decor):
    def test_import_avec_option_et_les_deux_exports_du_jour(self):
        self.lancer_en()
        imports = [a["args"] for a in self.appels() if a["outil"] == "flow_import"]
        self.assertEqual(len(imports), 1)
        self.assertIn("--mark-absent", imports[0])
        self.assertIn(f"Flux-Lab/exports/api-{REQUETE_1}-{aujourdhui()}.csv", imports[0])
        self.assertIn(f"Flux-Lab/exports/api-{REQUETE_2}-{aujourdhui()}.csv", imports[0])

    def test_reprise_a_une_autre_date_les_exports_de_cette_date(self):
        self.lancer_en("--from", "import", "--date", hier())
        args = next(a["args"] for a in self.appels() if a["outil"] == "flow_import")
        self.assertIn("--mark-absent", args)
        self.assertEqual([x for x in args if x.endswith(".csv")],
                         [f"Flux-Lab/exports/api-{REQUETE_1}-{hier()}.csv", f"Flux-Lab/exports/api-{REQUETE_2}-{hier()}.csv"])

    def test_seul_l_import_recoit_l_option(self):
        self.lancer_en()
        for a in self.appels():
            if a["outil"] != "flow_import":
                self.assertNotIn("--mark-absent", a["args"], a["outil"])


class EtapeRetention(Decor):
    def test_comptes_rapportes_sans_arret(self):
        self.sortie_retention("retention check: 7 items out of rule\ndry run: nothing deleted\n")
        r = self.lancer_en()
        self.assertEqual(r.code, 0, r.sortie)
        self.assertIn("retention dry run: 7 items out of rule", r.sortie)
        self.assertIn("- retention dry run: 7 items out of rule", self.resume())
        self.assertRegex(self.resume(), r"\| retention \| - \| passed \| 0 \|")
        self.assertIn("- final status: complete", self.resume())

    def test_la_ligne_suit_l_annonce_de_reussite_de_l_etape(self):
        self.sortie_retention("retention check: 7 items out of rule\ndry run: nothing deleted\n")
        lignes = self.lancer_en().sortie.splitlines()
        i = next(n for n, l in enumerate(lignes) if l.startswith("Step retention passed"))
        self.assertEqual(lignes[i + 1], "retention dry run: 7 items out of rule")

    def test_rien_hors_regle(self):
        r = self.lancer_en()                                            # sortie par défaut du faux outil : nothing out of rule
        self.assertIn("retention dry run: 0 items out of rule", r.sortie)
        self.assertIn("- retention dry run: 0 items out of rule", self.resume())

    def test_sortie_de_l_outil_jamais_imprimee(self):
        self.sortie_retention("retention check: 7 items out of rule\ndry run: nothing deleted\n")
        r = self.lancer_en()
        for fragment in ("retention check", "dry run: nothing deleted", "SORTIE-OUTIL"):
            self.assertNotIn(fragment, r.sortie)
            self.assertNotIn(fragment, self.resume())

    def test_erreur_de_l_outil(self):
        self.codes(flow_retention=1)
        r = self.lancer_en()
        self.assertEqual(r.code, 1, r.sortie)
        self.assertIn("Stopped at step retention: exit code 1", r.sortie)
        self.assertIn("--from retention", r.sortie)
        texte = self.resume()
        self.assertRegex(texte, r"\| dashboard \| - \| passed \| 0 \|")
        self.assertRegex(texte, r"\| retention \| - \| failed \| 1 \|")
        self.assertIn("- final status: stopped at retention", texte)
        self.assertNotIn("- retention dry run", texte)
        self.assertNotIn("complete:", r.sortie)

    def test_sortie_sans_ligne_de_total(self):
        self.sortie_retention("dry run: nothing deleted\n")
        r = self.lancer_en()
        self.assertEqual(r.code, 1, r.sortie)
        self.assertIn("Stopped at step retention: exit code 1", r.sortie)
        self.assertIn("- final status: stopped at retention", self.resume())
        self.assertNotIn("retention dry run:", r.sortie + self.resume())          # aucun compte deviné

    def test_total_dans_une_autre_langue_n_est_pas_lu(self):
        self.sortie_retention("contrôle de conservation : 3 éléments hors règle\n")
        r = self.lancer_en()
        self.assertEqual(r.code, 1, r.sortie)

    def test_appel_enregistre(self):
        self.lancer_en()
        appels = [a for a in self.appels() if a["outil"] == "flow_retention"]
        self.assertEqual([a["args"] for a in appels], [["purge", "--language", "en"]])
        self.assertEqual(self.outils_appeles()[-1], "flow_retention")
        self.assertEqual(self.outils_appeles()[-3:-1], ["flow_board", "flow_board"])
        for a in self.appels():
            self.assertNotIn("--apply", a["args"])
            self.assertNotIn("check", a["args"])

    def test_aucune_sauvegarde_etiquetee(self):
        self.lancer_en()
        self.assertNotIn("db_backup", " ".join(self.outils_appeles()))
        self.assertEqual(set(self.outils_appeles()) & {"db", "flow_views"}, set())

    def test_run_francais(self):
        self.sortie_retention("contrôle de conservation : 2 éléments hors règle\nessai : rien n'est supprimé\n")
        r = self.lancer()
        self.assertEqual(r.code, 0, r.sortie)
        self.assertIn("essai de purge : 2 éléments hors règle", r.sortie)
        self.assertIn("- essai de purge : 2 éléments hors règle", self.resume())
        self.assertEqual([a["args"] for a in self.appels() if a["outil"] == "flow_retention"], [["purge", "--language", "fr"]])

    def test_run_francais_rien_hors_regle(self):
        r = self.lancer()
        self.assertIn("essai de purge : 0 éléments hors règle", r.sortie)

    def test_reprise_a_retention(self):
        r = self.lancer_en("--from", "retention")
        self.assertEqual(r.code, 0, r.sortie)
        self.assertEqual(self.outils_appeles(), ["flow_retention"])
        self.assertIn("Monthly run complete: 1 of 12 steps, 11 skipped", r.sortie)

    def test_passage_a_blanc_inclut_l_etape(self):
        r = self.lancer_en("--dry-run")
        lignes = [l for l in r.sortie.splitlines() if l.strip()]
        self.assertEqual(lignes[-1], "dry run: would run uv run tools/flow_retention.py purge --language en")
        self.assertEqual(self.appels(), [])

    def test_passage_a_blanc_francais(self):
        r = self.lancer("--dry-run", "--from", "retention")
        self.assertEqual(r.sortie.strip(), "essai : lancerait uv run tools/flow_retention.py purge --language fr")


if __name__ == "__main__":
    unittest.main()
