"""Tests de la section « Fermetures groupées » de flux_jira.py, sur un export synthétique (aucune donnée réelle).

    uv run --with pyyaml --with numpy python -m unittest discover -s tests/flux_jira -v

- elle compte, par projet, les tickets livrés résolus dans la même minute, à partir du seuil réglé (5 par défaut) ;
- elle ne retire rien du débit, et n'écrit aucune clé ;
- le motif suivi (Done par défaut) et le seuil se règlent dans flux.yaml ;
- sans colonne de clé ou sans heure dans la date de résolution, elle ne peut rien dire, et le dit.
"""
import csv
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent.parent / "tools" / "flux_jira.py"
ENTETE = ["Issue key", "Issue Type", "Status", "Status Category", "Created", "Resolved", "Resolution"]
AUJOURDHUI = "2026-10-04"


def lignes_de_test(heure: bool = True) -> list[list[str]]:
    """Tickets livrés ou rejetés de cinq projets ; chaque groupe partage la même minute de résolution."""
    def resolu(jour: str, hhmm: str) -> str:
        return f"{jour}/Sep/2026 {hhmm}" if heure else f"2026-09-{jour}"
    lignes, numero = [], {}

    def ajouter(projet: str, n: int, jour: str, hhmm: str, motif: str):
        for _ in range(n):
            numero[projet] = numero.get(projet, 0) + 1
            etat = "Rejected" if motif == "Rejected" else "Closed"
            lignes.append([f"{projet}-{numero[projet]}", "Story", etat, "Done",
                           ("01/Aug/2026 09:00" if heure else "2026-08-01"), resolu(jour, hhmm), motif])
    ajouter("AAA", 7, "02", "14:05", "Done")                 # un groupe de 7
    ajouter("AAA", 1, "02", "14:06", "Done")
    ajouter("AAA", 1, "02", "15:00", "Done")
    ajouter("AAA", 6, "03", "09:30", "Accepted & Released")   # un groupe de 6, autre motif
    ajouter("BBB", 4, "04", "10:00", "Done")                 # sous le seuil de 5
    ajouter("CCC", 5, "10", "08:00", "Done")                 # deux groupes, 5 et 6
    ajouter("CCC", 6, "11", "08:00", "Done")
    ajouter("CCC", 1, "11", "08:30", "Done")
    ajouter("CCC", 3, "10", "08:00", "Rejected")             # rejetés : pas du débit
    ajouter("DDD", 5, "02", "14:05", "Done")                 # même minute que AAA, autre projet
    ajouter("EEE", 3, "05", "11:00", "Done")
    return lignes


class Base(unittest.TestCase):
    """Faux espace de travail, export synthétique et lancement de flux_jira.py compute."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name)
        (self.ws / "Flux-Lab").mkdir()
        self.ecrire_reglages("")

    def ecrire_reglages(self, texte: str):
        (self.ws / "Flux-Lab" / "flux.yaml").write_text(texte, encoding="utf-8")

    def exporter(self, lignes, entete=ENTETE) -> Path:
        chemin = self.ws / "export.csv"
        with chemin.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows([entete] + lignes)
        return chemin

    def calcul(self, export: Path, nom="f", extra=(), aujourdhui=AUJOURDHUI) -> tuple[str, dict]:
        env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(self.ws)}
        r = subprocess.run(["uv", "run", str(SCRIPT), "compute", str(export), "--name", nom, "--today", aujourdhui,
                            "--no-comparison", *extra], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rapports = self.ws / "Flux-Lab" / "rapports"
        md = next(rapports.glob(f"flux-{nom}-*.md")).read_text(encoding="utf-8")
        js = json.loads(next(rapports.glob(f"flux-{nom}-*.json")).read_text(encoding="utf-8"))
        return md, js


class Fermetures(Base):
    def test_compte_par_projet_au_seuil_de_5_et_motif_done(self):
        md, js = self.calcul(self.exporter(lignes_de_test()))
        f = js["fermetures_groupees"]
        self.assertEqual((f["seuil"], f["motifs"]), (5, ["done"]))
        self.assertEqual(list(f["par_projet"]), ["CCC", "AAA", "DDD"])          # triés par tickets décroissants
        self.assertEqual(f["par_projet"]["CCC"], {"groupes": 2, "tickets": 11, "plus_grand": 6, "livres": 12,
                                                  "part": 11 / 12})
        self.assertEqual(f["par_projet"]["AAA"]["tickets"], 7)                  # le groupe « Accepted & Released » est hors motif
        self.assertEqual(f["par_projet"]["AAA"]["livres"], 15)                  # mais ces tickets restent livrés
        self.assertEqual(f["par_projet"]["DDD"]["groupes"], 1)                  # la même minute dans un autre projet ne fusionne pas
        self.assertNotIn("BBB", f["par_projet"])                                # 4 < 5
        self.assertEqual(f["total"], {"groupes": 4, "tickets": 23, "livres": 39, "part": 23 / 39})
        self.assertIn("## Fermetures groupées", md)
        self.assertIn("| CCC | 11 | 2 | 6 | 12 | 92 % |", md)
        self.assertIn("| **Total** | **23** | **4** | | **39** | **59 %** |", md)

    def test_aucun_ticket_retire_du_debit(self):
        _, js = self.calcul(self.exporter(lignes_de_test()))
        self.assertEqual(js["termines"], 39)             # 15 + 4 + 12 + 5 + 3 : les groupés y sont, les 3 rejetés non
        self.assertEqual(js["clos_sans_livraison"], {"Rejected": 3})
        self.assertEqual(sum(js["debit_par_semaine"]), 39)

    def test_seuil_reglable(self):
        self.ecrire_reglages("batch_closure_threshold: 4\n")
        _, js = self.calcul(self.exporter(lignes_de_test()))
        f = js["fermetures_groupees"]
        self.assertEqual(f["seuil"], 4)
        self.assertEqual(f["par_projet"]["BBB"]["tickets"], 4)

    def test_motifs_reglables_et_liste_vide_pour_tous_les_motifs_livres(self):
        self.ecrire_reglages("batch_closure_resolutions: []\n")
        md, js = self.calcul(self.exporter(lignes_de_test()))
        self.assertEqual(js["fermetures_groupees"]["par_projet"]["AAA"]["tickets"], 13)     # 7 Done + 6 Accepted & Released
        self.assertIn("tous les motifs comptés comme livrés", md)
        self.ecrire_reglages("batch_closure_resolutions: [Accepted & Released]\n")
        _, js = self.calcul(self.exporter(lignes_de_test()), nom="g")
        self.assertEqual(list(js["fermetures_groupees"]["par_projet"]), ["AAA"])

    def test_seuil_invalide_arrete_le_calcul(self):
        self.ecrire_reglages("batch_closure_threshold: 1\n")
        env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(self.ws)}
        r = subprocess.run(["uv", "run", str(SCRIPT), "compute", str(self.exporter(lignes_de_test())), "--today",
                            AUJOURDHUI], env=env, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("batch_closure_threshold", r.stdout + r.stderr)

    def test_aucune_cle_dans_le_rapport(self):
        md, js = self.calcul(self.exporter(lignes_de_test()))
        for texte in (md, json.dumps(js)):
            self.assertNotRegex(texte, r"\b[A-Z]{3}-\d+\b")

    def test_glossaire_seulement_avec_la_section(self):
        md, _ = self.calcul(self.exporter(lignes_de_test()))
        self.assertIn("**Fermeture groupée**", md)
        sans_cle = [[l[1], l[2], l[3], l[4], l[5], l[6]] for l in lignes_de_test()]
        md, js = self.calcul(self.exporter(sans_cle, entete=ENTETE[1:]), nom="s")
        self.assertNotIn("fermetures_groupees", js)
        self.assertNotIn("## Fermetures groupées", md)
        self.assertNotIn("Fermeture groupée", md)

    def test_aucune_fermeture_groupee_le_dit(self):
        un_par_minute = [[f"AAA-{i}", "Story", "Closed", "Done", "01/Aug/2026 09:00", f"02/Sep/2026 10:{i:02d}", "Done"]
                         for i in range(1, 9)]
        md, js = self.calcul(self.exporter(un_par_minute))
        self.assertEqual(js["fermetures_groupees"]["par_projet"], {})
        self.assertIn("Aucune fermeture groupée sur la période (8 tickets livrés).", md)


class MotifsEtFenetre(Base):
    """--motifs-fermetures (sans toucher à flux.yaml) et mention de la première semaine tronquée par resolved >= -26w."""

    def test_option_remplace_le_reglage_sans_toucher_a_flux_yaml(self):
        reglages = "batch_closure_resolutions: [Done]\nbatch_closure_threshold: 5\n"
        self.ecrire_reglages(reglages)
        md, js = self.calcul(self.exporter(lignes_de_test()), extra=["--batch-closure-resolutions", "Done,Accepted & Released"])
        f = js["fermetures_groupees"]
        self.assertEqual(f["motifs"], ["accepted & released", "done"])
        self.assertEqual(f["par_projet"]["AAA"]["tickets"], 13)                 # 7 Done + 6 Accepted & Released
        self.assertEqual(f["par_projet"]["AAA"]["groupes"], 2)
        self.assertIn("motif de résolution : accepted & released, done", md)
        self.assertEqual((self.ws / "Flux-Lab" / "flux.yaml").read_text(encoding="utf-8"), reglages)   # inchangé

    def test_option_seule_motif_et_tous(self):
        _, js = self.calcul(self.exporter(lignes_de_test()), extra=["--batch-closure-resolutions", "Accepted & Released"])
        self.assertEqual(list(js["fermetures_groupees"]["par_projet"]), ["AAA"])
        self.assertEqual(js["fermetures_groupees"]["par_projet"]["AAA"]["tickets"], 6)
        md, js = self.calcul(self.exporter(lignes_de_test()), nom="t", extra=["--batch-closure-resolutions", "tous"])
        self.assertEqual(js["fermetures_groupees"]["motifs"], [])
        self.assertEqual(js["fermetures_groupees"]["par_projet"]["AAA"]["tickets"], 13)
        self.assertIn("tous les motifs comptés comme livrés", md)

    def test_option_vide_arrete_le_calcul(self):
        env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(self.ws)}
        r = subprocess.run(["uv", "run", str(SCRIPT), "compute", str(self.exporter(lignes_de_test())), "--today",
                            AUJOURDHUI, "--batch-closure-resolutions", " , "], env=env, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--batch-closure-resolutions", r.stdout + r.stderr)

    def lignes_fenetre(self):
        """Un ticket résolu la première semaine de la période (2026-04-08) fixe le début à 2026-04-06."""
        premier = ["ZZZ-1", "Story", "Closed", "Done", "01/Mar/2026 09:00", "08/Apr/2026 10:00", "Done"]
        return [premier] + lignes_de_test()

    def test_premiere_semaine_tronquee_par_le_filtre_de_resolution(self):
        self.ecrire_reglages("jql_exports:\n  a: project = AAA AND (statusCategory != Done OR resolved >= -26w)\n")
        md, js = self.calcul(self.exporter(self.lignes_fenetre()), aujourdhui="2026-10-06")
        self.assertEqual(js["periode"][0], "2026-04-06")
        self.assertEqual(js["fenetre_export"], {"filtre": "resolved >= -26w", "debut": "2026-04-07",
                                                "semaine": "2026-04-06", "jours_manquants": 1})
        debut = md.index("## Arrivées et sorties"); fin = md.index("## Fermetures groupées")
        section = md[debut:fin]
        self.assertIn("Première semaine tronquée", section)
        self.assertIn("`resolved >= -26w`", section)
        self.assertIn("la fenêtre commence le 2026-04-07", section)
        self.assertIn("les 1 premiers jours de la période", section)
        self.assertIn("à exclure des comparaisons", section)

    def test_pas_de_mention_sans_fenetre_ou_si_la_periode_commence_apres(self):
        md, js = self.calcul(self.exporter(self.lignes_fenetre()), aujourdhui="2026-10-06")        # aucun jql dans flux.yaml
        self.assertNotIn("fenetre_export", js)
        self.assertNotIn("Première semaine tronquée", md)
        self.ecrire_reglages("jql_export: project = AAA AND resolved >= -26w\n")
        _, js = self.calcul(self.exporter(lignes_de_test()), nom="p", aujourdhui="2026-10-06")     # la période commence en août
        self.assertNotIn("fenetre_export", js)
        self.ecrire_reglages("jql_export: project = AAA AND statusCategory != Done\n")
        _, js = self.calcul(self.exporter(self.lignes_fenetre()), nom="q", aujourdhui="2026-10-06")
        self.assertNotIn("fenetre_export", js)


if __name__ == "__main__":
    unittest.main()
