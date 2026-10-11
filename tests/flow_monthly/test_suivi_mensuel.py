"""
Tests de tools/flow_monthly.py (change monthly-flow-orchestrator, R-48) : l'ordre des étapes, l'arrêt au premier écart, la reprise, le
passage à blanc, le résumé et le refus d'un mois déjà fait. Faux outils, réglages inventés, aucune donnée réelle (aide_flow_monthly.py).

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/flow_monthly -q -f
"""
import os
import stat
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_flow_monthly import (Decor, MARQUES, PERIMETRE_1, PERIMETRE_2, REQUETE_1, REQUETE_2, SERIE_1, SERIE_2, aujourdhui,  # noqa: E402
                               demain, hier)

PORTEE = f"{PERIMETRE_1},{PERIMETRE_2}"


def exports(jour: str) -> list[str]:
    return [f"Flux-Lab/exports/api-{REQUETE_1}-{jour}.csv", f"Flux-Lab/exports/api-{REQUETE_2}-{jour}.csv"]


def rapport(nom: str, jour: str) -> str:
    return f"Flux-Lab/rapports/flux-{nom}-{jour}.md"


def appels_attendus(jour: str, langue: str = "en", date_option: bool = False) -> list[tuple[str, list[str]]]:
    e = exports(jour)
    today = ["--today", jour] if date_option else []
    return [
        ("export_jira_api", ["export", "--strict-teams", "--language", langue]),
        ("history_jira", ["collect", *e, "--strict", "--language", langue]),
        ("flow_import", [*e, "--history", "--language", langue]),
        ("flux_jira", ["compute", *e, "--name", SERIE_1, "--scope", PORTEE, "--history", "--dormant-from-history", "--points",
                       "--language", langue, *today]),
        ("flux_jira", ["compute", *e, "--name", SERIE_2, "--history", "--dormant-from-history", "--points", "--language", langue, *today]),
        ("dependencies_jira", ["compute", *e, "--name", SERIE_1, "--scope", PORTEE, "--language", langue]),
        ("dependencies_jira", ["compute", *e, "--name", SERIE_1, "--scope", PORTEE, "--by", "project", "--language", langue]),
        ("dependencies_jira", ["compute", *e, "--name", SERIE_2, "--language", langue]),
        ("flow_compare", ["--language", langue, "data", *e, "--history"]),
        ("flux_jira", ["compute", "--source", "db", "--name", f"{SERIE_1}-db", "--scope", PORTEE, "--history", "--dormant-from-history",
                       "--no-comparison", "--language", langue, *today]),
        ("flow_compare", ["--language", langue, "reports", rapport(SERIE_1, jour), rapport(f"{SERIE_1}-db", jour)]),
        ("flux_jira", ["compute", "--source", "db", "--name", f"{SERIE_2}-db", "--history", "--dormant-from-history",
                       "--no-comparison", "--language", langue, *today]),
        ("flow_compare", ["--language", langue, "reports", rapport(SERIE_2, jour), rapport(f"{SERIE_2}-db", jour)]),
        ("flow_board", ["--language", langue]),
        ("flow_board", ["--language", langue, "--anonymous"]),
    ]


class OrdreEtOptions(Decor):
    def test_run_complet_ordre_et_options(self):
        r = self.lancer_en()
        self.assertEqual(r.code, 0, r.sortie)
        self.assertEqual([(a["outil"], a["args"]) for a in self.appels()], appels_attendus(aujourdhui()))
        self.assertIn("Monthly run complete: 11 of 11 steps", r.sortie)

    def test_run_complet_en_francais_par_defaut(self):
        r = self.lancer()
        self.assertEqual(r.code, 0, r.sortie)
        self.assertIn("Suivi mensuel terminé : 11 étapes sur 11", r.sortie)
        self.assertEqual([(a["outil"], a["args"]) for a in self.appels()], appels_attendus(aujourdhui(), "fr"))

    def test_chaque_etape_est_annoncee_avec_son_rang(self):
        r = self.lancer_en()
        for ligne in ("Step 1/11: export", "Step 2/11: history", "Step 3/11: import", "Step 4/11: flow (series 1)",
                      "Step 5/11: flow (series 2)", "Step 6/11: dependencies (series 1)", "Step 7/11: dependencies (series 2)",
                      "Step 8/11: compare-data", "Step 9/11: compare-reports (series 1)", "Step 10/11: compare-reports (series 2)",
                      "Step 11/11: dashboard"):
            self.assertIn(ligne, r.sortie)
        self.assertRegex(r.sortie, r"Step export passed \(\d+ s\)")

    def test_outils_exclus_jamais_appeles_et_commandes_de_lecture_affichees(self):
        r = self.lancer_en()
        self.assertEqual(r.code, 0, r.sortie)
        self.assertEqual(set(self.outils_appeles()) & {"segment_sample", "db", "flow_views", "knowledge_import"}, set())
        self.assertNotIn("--dry-run", [m for a in self.appels() for m in a["args"]])      # pas d'essai à blanc de l'import
        for a in self.appels():
            self.assertNotIn("check", a["args"])
        derniere = r.sortie.strip().splitlines()[-3:]
        self.assertIn("/monthly-flow <series>", "\n".join(derniere))
        self.assertIn("/dependencies <series>", "\n".join(derniere))

    def test_option_open_va_aux_tableaux(self):
        self.lancer_en("--open")
        tableaux = [a["args"] for a in self.appels() if a["outil"] == "flow_board"]
        self.assertEqual(tableaux, [["--language", "en", "--open"], ["--language", "en", "--anonymous", "--open"]])

    def test_tableaux_selon_le_reglage(self):
        for valeur, attendu in (("full", [["--language", "en"]]), ("anonymous", [["--language", "en", "--anonymous"]])):
            self.setUp()
            self.ecrire_reglages(self.reglages_avec_tableaux(valeur))
            self.lancer_en()
            self.assertEqual([a["args"] for a in self.appels() if a["outil"] == "flow_board"], attendu)

    def reglages_avec_tableaux(self, valeur: str) -> str:
        from aide_flow_monthly import REGLAGES
        return REGLAGES.replace("dashboard: both", f"dashboard: {valeur}")

    def test_requete_unique_sans_nom(self):
        self.ecrire_reglages("jql_export: project = AAA\nmonthly_run:\n  series:\n    - name: seulezz\n      dependencies: none\n")
        r = self.lancer_en()
        self.assertEqual(r.code, 0, r.sortie)
        chemin = f"Flux-Lab/exports/api-{aujourdhui()}.csv"
        self.assertEqual(self.appels()[1]["args"], ["collect", chemin, "--strict", "--language", "en"])
        self.assertNotIn("dependencies_jira", self.outils_appeles())             # dependencies: none
        self.assertIn("Step 1/", r.sortie)

    def test_cartes_de_dependances_par_serie(self):
        r = self.lancer_en()
        deps = [a["args"] for a in self.appels() if a["outil"] == "dependencies_jira"]
        self.assertEqual(len(deps), 3)                                           # série 1 : équipe et projet ; série 2 : équipe
        self.assertEqual([("--by" in d) for d in deps], [False, True, False])
        self.assertEqual(r.code, 0, r.sortie)

    def test_perimetre_absent_aucune_option_scope(self):
        self.lancer_en()
        for a in self.appels():
            if a["outil"] in ("flux_jira", "dependencies_jira") and SERIE_2 in " ".join(a["args"]):
                self.assertNotIn("--scope", a["args"])

    def test_comparaison_des_rapports_par_la_serie_de_la_base(self):
        self.lancer_en()
        base = [a["args"] for a in self.appels() if a["outil"] == "flux_jira" and "--source" in a["args"]]
        self.assertEqual(len(base), 2)
        for args in base:
            self.assertIn("--no-comparison", args)
            self.assertNotIn("--points", args)
            self.assertTrue(args[args.index("--name") + 1].endswith("-db"))
            self.assertEqual([x for x in args if x.endswith(".csv")], [])
        comparaisons = [a["args"] for a in self.appels() if a["outil"] == "flow_compare" and "reports" in a["args"]]
        self.assertEqual(comparaisons[0][-2:], [rapport(SERIE_1, aujourdhui()), rapport(f"{SERIE_1}-db", aujourdhui())])


class ArretAuPremierEcart(Decor):
    def test_import_en_echec(self):
        self.codes(flow_import=1)
        r = self.lancer_en()
        self.assertEqual(r.code, 1, r.sortie)
        self.assertIn("Stopped at step import: exit code 1", r.sortie)
        self.assertIn("--from import", r.sortie)
        self.assertEqual(self.outils_appeles(), ["export_jira_api", "history_jira", "flow_import"])
        self.assertEqual(r.sortie.strip().splitlines()[-1], "To resume: uv run tools/flow_monthly.py --from import")

    def test_ecart_de_parite_sur_les_donnees(self):
        self.codes(flow_compare__data=1)
        r = self.lancer_en()
        self.assertEqual(r.code, 4, r.sortie)
        self.assertIn("Database and CSV differ at step compare-data", r.sortie)
        self.assertEqual(self.outils_appeles()[-1], "flow_compare")
        self.assertNotIn("flow_board", self.outils_appeles())
        self.assertNotIn("--source", [m for a in self.appels() for m in a["args"]])

    def test_ecart_de_parite_sur_les_rapports(self):
        self.codes(flow_compare__reports=1)
        r = self.lancer_en()
        self.assertEqual(r.code, 4, r.sortie)
        self.assertIn("Database and CSV differ at step compare-reports", r.sortie)
        self.assertNotIn("flow_board", self.outils_appeles())
        self.assertIn("--from compare-reports", r.sortie)

    def test_entree_illisible_de_la_comparaison_n_est_pas_un_ecart(self):
        self.codes(flow_compare__data=2)
        r = self.lancer_en()
        self.assertEqual(r.code, 1, r.sortie)
        self.assertIn("Stopped at step compare-data: exit code 2", r.sortie)
        self.assertNotIn("differ", r.sortie)

    def test_calcul_de_la_base_en_echec_est_une_panne(self):
        self.codes_de({"flux_jira:db": 1})
        r = self.lancer_en()
        self.assertEqual(r.code, 1, r.sortie)
        self.assertIn("Stopped at step compare-reports: exit code 1", r.sortie)

    def test_fichier_d_export_manquant_l_orchestrateur_ne_le_verifie_pas(self):
        self.codes(history_jira=1)
        r = self.lancer_en()
        self.assertEqual(r.code, 1, r.sortie)
        self.assertIn("Stopped at step history", r.sortie)
        self.assertEqual(self.outils_appeles(), ["export_jira_api", "history_jira"])
        self.assertEqual(list((self.flux / "exports").iterdir()), [self.flux / "exports" / "sentinelle.csv"])

    def test_pas_de_nouvelle_tentative(self):
        self.codes(flux_jira=1)
        self.lancer_en()
        self.assertEqual(self.outils_appeles().count("flux_jira"), 1)

    def test_etape_exportee_en_echec_avec_code_3_est_une_panne(self):
        self.codes(export_jira_api=3)
        r = self.lancer_en()
        self.assertEqual(r.code, 1, r.sortie)
        self.assertIn("Stopped at step export: exit code 3", r.sortie)

    def test_la_sortie_d_erreur_de_l_outil_en_echec_est_affichee_pas_sa_sortie_standard(self):
        self.codes(flow_import=1)
        r = self.lancer_en()
        self.assertIn("ERREUR-OUTIL boum", r.sortie)
        self.assertNotIn("SORTIE-OUTIL", r.sortie)
        self.assertIn("--verbose", r.sortie)

    def test_reprise_avec_une_autre_date_dans_la_phrase_de_reprise(self):
        self.codes(flow_import=1)
        r = self.lancer_en("--date", hier(), "--from", "history")
        self.assertEqual(r.sortie.strip().splitlines()[-1], f"To resume: uv run tools/flow_monthly.py --from import --date {hier()}")


class Reprise(Decor):
    def test_from_compare_data(self):
        r = self.lancer_en("--from", "compare-data")
        self.assertEqual(r.code, 0, r.sortie)
        self.assertEqual(self.outils_appeles()[0], "flow_compare")
        self.assertEqual(self.appels()[0]["args"], ["--language", "en", "data", *exports(aujourdhui()), "--history"])
        for exclu in ("export_jira_api", "history_jira", "flow_import", "dependencies_jira"):
            self.assertNotIn(exclu, self.outils_appeles())
        self.assertNotIn(("flux_jira", "--points"), [(a["outil"], m) for a in self.appels() for m in a["args"]])

    def test_from_dashboard(self):
        self.lancer_en("--from", "dashboard")
        self.assertEqual(self.outils_appeles(), ["flow_board", "flow_board"])

    def test_date_d_un_autre_jour_chemins_et_rapports_de_cette_date(self):
        r = self.lancer_en("--from", "import", "--date", hier())
        self.assertEqual(r.code, 0, r.sortie)
        attendu = appels_attendus(hier(), date_option=True)[2:]
        self.assertEqual([(a["outil"], a["args"]) for a in self.appels()], attendu)
        self.assertTrue((self.rapports / f"suivi-mensuel-{hier()}.md").exists())

    def test_from_export_avec_une_autre_date_est_une_erreur_d_usage(self):
        r = self.lancer_en("--from", "export", "--date", hier())
        self.assertEqual(r.code, 2, r.sortie)
        self.assertEqual(self.appels(), [])

    def test_from_export_avec_la_date_du_jour_est_permis(self):
        r = self.lancer_en("--from", "export", "--date", aujourdhui())
        self.assertEqual(r.code, 0, r.sortie)

    def test_erreurs_d_usage(self):
        for argv in (["--from", "inconnue"], ["--date", "11/10/2026"], ["--date", "2026-13-40"], ["--date", demain()],
                     ["--bidule"], ["--language", "de"]):
            self.setUp()
            r = self.lancer(*argv)
            self.assertEqual(r.code, 2, (argv, r.sortie))
            self.assertEqual(self.appels(), [], argv)
            self.assertFalse(list(self.rapports.glob("suivi-mensuel-*")), argv)

    def test_reprise_conserve_les_etapes_reussies_avant(self):
        self.codes(flow_import=1)
        self.lancer_en()                                                           # s'arrête à import
        self.codes_de({})
        r = self.lancer_en("--from", "import")
        self.assertEqual(r.code, 0, r.sortie)
        texte = self.resume()
        for etape in ("export", "history"):
            self.assertRegex(texte, rf"\| {etape} \| - \| passed \| 0 \|")             # repris du résumé précédent
        self.assertIn("- final status: complete", texte)


class PassageABlanc(Decor):
    def test_dry_run_plan_avec_marques_sans_outil_ni_resume(self):
        r = self.lancer_en("--dry-run")
        self.assertEqual(r.code, 0, r.sortie)
        lignes = [l for l in r.sortie.splitlines() if l.strip()]
        self.assertEqual(len(lignes), 15)
        for ligne in lignes:
            self.assertTrue(ligne.startswith("dry run: would run "), ligne)
        self.assertIn("<series 1>", r.sortie)
        self.assertIn("<export 1>", r.sortie)
        self.assertIn("<scope 1>", r.sortie)
        self.assertEqual(self.appels(), [])
        self.assertFalse(list(self.rapports.glob("suivi-mensuel-*")))

    def test_dry_run_en_francais(self):
        r = self.lancer("--dry-run")
        for ligne in [l for l in r.sortie.splitlines() if l.strip()]:
            self.assertTrue(ligne.startswith("essai : lancerait "), ligne)
        self.assertIn("<série 1>", r.sortie)

    def test_dry_run_fait_les_verifications_prealables(self):
        self.ecrire_reglages("jira_site: x\n")
        r = self.lancer_en("--dry-run")
        self.assertEqual(r.code, 3, r.sortie)
        self.resume_ecrit(aujourdhui(), "complete")
        self.ecrire_reglages(self.reglages_ok())
        r = self.lancer_en("--dry-run")
        self.assertEqual(r.code, 5, r.sortie)

    def reglages_ok(self) -> str:
        from aide_flow_monthly import REGLAGES
        return REGLAGES

    def test_dry_run_avec_from(self):
        r = self.lancer_en("--dry-run", "--from", "dashboard")
        self.assertEqual(len([l for l in r.sortie.splitlines() if l.strip()]), 2)


class Reglages(Decor):
    def refuse(self, texte: str, fragment: str | None = None) -> str:
        self.ecrire_reglages(texte)
        r = self.lancer_en()
        self.assertEqual(r.code, 3, r.sortie)
        self.assertIn("Missing prerequisite", r.sortie)
        self.assertEqual(self.appels(), [])
        if fragment:
            self.assertIn(fragment, r.sortie)
        return r.sortie

    BASE = "jql_exports:\n  a: project = AAA\n"

    def test_cle_inconnue_nomme_le_chemin_et_la_ligne_sans_valeur(self):
        sortie = self.refuse(self.BASE + "monthly_run:\n  series:\n    - name: s1\n      bidule: valeurconfidentielle\n",
                             "monthly_run.series[1].bidule (L6)")
        self.assertNotIn("valeurconfidentielle", sortie)

    def test_cle_inconnue_au_niveau_du_bloc(self):
        self.refuse(self.BASE + "monthly_run:\n  extra: 1\n  series:\n    - name: s1\n", "monthly_run.extra (L4)")

    def test_fichier_de_reglages_absent(self):
        (self.flux / "flux.yaml").unlink()
        r = self.lancer_en()
        self.assertEqual(r.code, 3, r.sortie)
        self.assertIn("Missing prerequisite: settings file", r.sortie)

    def test_aucune_requete_d_export(self):
        self.refuse("monthly_run:\n  series:\n    - name: s1\n", "export query")

    def test_bloc_absent(self):
        self.refuse(self.BASE, "monthly_run block missing")

    def test_liste_de_series_vide(self):
        self.refuse(self.BASE + "monthly_run:\n  series: []\n", "series list empty")

    def test_serie_sans_nom(self):
        self.refuse(self.BASE + "monthly_run:\n  series:\n    - scope: ABC\n", "name missing")

    def test_deux_series_du_meme_nom(self):
        self.refuse(self.BASE + "monthly_run:\n  series:\n    - name: s1\n    - name: s1\n", "duplicate name (monthly_run.series[2].name (L6))")

    def test_nom_de_serie_qui_finit_par_le_suffixe_de_la_base(self):
        self.refuse(self.BASE + "monthly_run:\n  series:\n    - name: s1-db\n", "reserved suffix")

    def test_nom_de_serie_qui_contient_le_suffixe_au_milieu_est_permis(self):
        self.ecrire_reglages(self.BASE + "monthly_run:\n  series:\n    - name: s1-db-bis\n")
        self.assertEqual(self.lancer_en("--dry-run").code, 0)

    def test_valeurs_invalides(self):
        self.refuse(self.BASE + "monthly_run:\n  series:\n    - name: s1\n      dependencies: partout\n", "invalid value")
        self.refuse(self.BASE + "monthly_run:\n  series:\n    - name: s1\n  dashboard: tous\n", "invalid value")
        self.refuse(self.BASE + "monthly_run:\n  series:\n    - name: s1\n      scope: 12\n", "invalid value")

    def test_cle_ecrite_deux_fois_refusee_par_le_chargeur_strict(self):
        sortie = self.refuse(self.BASE + "monthly_run:\n  series:\n    - name: s1\n  series:\n    - name: s2\n", "written twice")
        self.assertIn("monthly_run.series", sortie)

    def test_yaml_illisible(self):
        self.refuse("monthly_run: [pas, un\n", "settings file unreadable")


class Resume(Decor):
    def test_resume_apres_un_arret(self):
        self.codes(history_jira=1)
        r = self.lancer_en()
        self.assertEqual(r.code, 1)
        texte = self.resume()
        self.assertRegex(texte, r"\| export \| - \| passed \| 0 \| \d+ \|")
        self.assertRegex(texte, r"\| history \| - \| failed \| 1 \| \d+ \|")
        self.assertRegex(texte, r"\| import \| - \| not run \| - \| - \|")
        self.assertRegex(texte, r"\| flow \| 2 \| not run \|")
        self.assertIn("- final status: stopped at history", texte)
        self.assertIn("- export queries: 2", texte)
        self.assertIn("- series: 2", texte)

    def test_resume_apres_un_ecart(self):
        self.codes(flow_compare__data=1)
        self.lancer_en()
        self.assertRegex(self.resume(), r"\| compare-data \| - \| gap \| 1 \|")

    def test_resume_complet_avec_nombre_de_rapports(self):
        self.lancer_en()
        texte = self.resume()
        self.assertIn("- final status: complete", texte)
        self.assertIn("- report files of the run date: 8", texte)        # 2 séries x (rapport CSV, rapport base) x (.md, .json)
        self.assertNotIn("not run", texte)

    def test_permissions_du_resume(self):
        self.lancer_en()
        mode = stat.S_IMODE((self.rapports / f"suivi-mensuel-{aujourdhui()}.md").stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_le_resume_compte_les_outils_qui_ont_ecrit_sur_la_sortie_d_erreur(self):
        self.codes_de({"stderr_ok": 1})
        self.lancer_en()
        self.assertRegex(self.resume(), r"- tools with error output on success: 15")

    def test_pas_de_resume_quand_un_prerequis_est_refuse(self):
        self.ecrire_reglages("jira_site: x\n")
        self.lancer_en()
        self.assertFalse(list(self.rapports.glob("suivi-mensuel-*")))


class MoisDejaFait(Decor):
    def test_refus_quand_un_resume_du_mois_est_complet(self):
        self.resume_ecrit(aujourdhui(), "complete")
        r = self.lancer_en()
        self.assertEqual(r.code, 5, r.sortie)
        self.assertIn("Monthly run already done this month", r.sortie)
        self.assertEqual(self.appels(), [])

    def test_refus_en_francais(self):
        self.resume_ecrit(aujourdhui(), "complete")
        r = self.lancer()
        self.assertEqual(r.code, 5)
        self.assertIn("Suivi mensuel déjà fait ce mois-ci (--force pour relancer)", r.sortie)

    def test_force_relance(self):
        self.resume_ecrit(aujourdhui(), "complete")
        r = self.lancer_en("--force")
        self.assertEqual(r.code, 0, r.sortie)
        self.assertTrue(self.appels())

    def test_from_ne_contourne_pas_le_refus(self):
        self.resume_ecrit(aujourdhui(), "complete")
        r = self.lancer_en("--from", "dashboard")
        self.assertEqual(r.code, 5, r.sortie)
        self.assertEqual(self.appels(), [])

    def test_un_resume_arrete_ne_bloque_pas(self):
        self.resume_ecrit(aujourdhui(), "stopped at import")
        self.assertEqual(self.lancer_en("--from", "import").code, 0)

    def test_un_resume_d_un_autre_mois_ne_bloque_pas(self):
        import datetime as dt
        autre = (dt.date.today().replace(day=1) - dt.timedelta(days=1)).isoformat()
        self.resume_ecrit(autre, "complete")
        self.assertEqual(self.lancer_en().code, 0)


class SortieSilencieuseEtDetaillee(Decor):
    def test_sortie_silencieuse_aucune_sortie_d_outil(self):
        r = self.lancer_en()
        self.assertNotIn("SORTIE-OUTIL", r.sortie)
        self.assertNotIn("ERREUR-OUTIL", r.sortie)

    def test_verbose_avertit_puis_diffuse(self):
        r = self.lancer_en("--verbose")
        self.assertEqual(r.code, 0, r.sortie)
        avertissement = "Verbose mode: the tools' output can hold series, query or team names"
        self.assertIn(avertissement, r.sortie)
        self.assertLess(r.sortie.index(avertissement), r.sortie.index("Step 1/"))
        self.assertIn("SORTIE-OUTIL", r.sortie)
        self.assertNotIn("SORTIE-OUTIL", self.resume())
        self.assertNotIn(SERIE_1, self.resume())

    def test_pas_d_avertissement_hors_verbose(self):
        self.assertNotIn("Verbose mode", self.lancer_en().sortie)


if __name__ == "__main__":
    unittest.main()
