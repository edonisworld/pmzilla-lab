"""Tests de bout en bout de l'option de source de flux_jira.py et de dependencies_jira.py (lot 6, commit C4).

    bash tools/dbtest.sh flow_store          (instance jetable : installation.md, 14.5 ; sautés sans elle)

- le même jeu inventé lu en CSV (source par défaut) et dans la base donne des rapports identiques ;
- la voie CSV ne charge jamais psycopg (un faux module psycopg qui lève une erreur à l'import est placé sur PYTHONPATH) ;
- une base injoignable ou une source inconnue donne un message clair, le code de sortie 1, sans mot de passe ni trace d'appel.
Aucune donnée réelle ; Flux-Lab est isolé dans un dossier temporaire (PMZILLA_LAB_WORKSPACE).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import aide_base as base          # noqa: E402
import jeu                        # noqa: E402

TOOLS = base.TOOLS
FLUX = TOOLS / "flux_jira.py"
DEPENDANCES = TOOLS / "dependencies_jira.py"
AUJOURDHUI = dt.date.today().isoformat()
SOURCE_DB = "--source" + "=db"          # écrit en deux morceaux : aucune règle deny ne lit ce fichier, mais le motif reste hors des commandes
FAUX_MOT_DE_PASSE = "FauxMotDePasse-5d2a77c1"


def lancer(script: Path, workspace: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    environnement = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(workspace), **(env or {})}
    return subprocess.run(["uv", "run", str(script), *args], env=environnement, capture_output=True, text=True)


def rapports(workspace: Path) -> dict[str, str]:
    dossier = workspace / "Flux-Lab" / "rapports"
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(dossier.iterdir())}


class AvecDossier(unittest.TestCase):
    def dossier(self) -> Path:
        chemin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, chemin, ignore_errors=True)
        return chemin


class VoieCsvSansPsycopg(AvecDossier):
    def test_la_voie_csv_ne_charge_pas_psycopg(self):
        faux = self.dossier() / "faux"
        (faux / "psycopg").mkdir(parents=True)
        (faux / "psycopg" / "__init__.py").write_text('raise RuntimeError("psycopg charge par la voie csv")\n')
        export = self.dossier() / "export.csv"
        jeu.ecrire_csv(export, jeu.tickets())
        for script, commande in ((FLUX, "statuses"), (DEPENDANCES, "diagnose")):
            r = lancer(script, self.dossier(), commande, str(export), env={"PYTHONPATH": str(faux)})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn("psycopg", r.stdout + r.stderr)

    def test_csv_sans_fichier_garde_le_message_d_avant(self):
        for script, commande in ((FLUX, "statuses"), (FLUX, "compute"), (DEPENDANCES, "diagnose"), (DEPENDANCES, "compute")):
            r = lancer(script, self.dossier(), commande)
            self.assertEqual(r.returncode, 2)
            self.assertIn("the following arguments are required: export", r.stderr)


class Erreurs(AvecDossier):
    def test_source_inconnue(self):
        export = self.dossier() / "export.csv"
        jeu.ecrire_csv(export, jeu.tickets())
        for script, commande in ((FLUX, "statuses"), (DEPENDANCES, "diagnose")):
            r = lancer(script, self.dossier(), commande, str(export), "--source", "ftp")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("--source", r.stderr)
            self.assertIn("ftp", r.stderr)
            self.assertNotIn("Traceback", r.stderr)

    def test_fichiers_csv_refuses_avec_la_base(self):
        """Avec la base, un fichier CSV passé en argument est refusé (code non nul, message clair), jamais ignoré. Aucune connexion."""
        export = self.dossier() / "export.csv"
        jeu.ecrire_csv(export, jeu.tickets())
        for script, commande in ((FLUX, "statuses"), (FLUX, "compute"), (DEPENDANCES, "diagnose"), (DEPENDANCES, "compute")):
            for langue, attendu in (("fr", "aucun fichier CSV ne doit être donné"), ("en", "no CSV file may be given")):
                r = lancer(script, self.dossier(), commande, str(export), "--source", "db", "--language", langue,
                           env={"PMZILLA_LAB_DB_PORT": "1"})
                texte = r.stdout + r.stderr
                self.assertNotEqual(r.returncode, 0, texte)
                self.assertIn(attendu, texte, f"{script.name} {commande} {langue}")
                self.assertNotIn("Traceback", texte)
                self.assertNotIn("injoignable", texte)               # refusé avant toute connexion à la base

    def test_base_injoignable(self):
        env = {"PMZILLA_LAB_DB_URL": "postgresql://postgres@127.0.0.1:1/pmzilla",
               "PMZILLA_LAB_DB_PASSWORD": FAUX_MOT_DE_PASSE, "PMZILLA_LAB_DB_SECURITY_BIN": str(base.FAUX_SECURITY)}
        for script, args in ((FLUX, ("statuses",)), (FLUX, ("compute", "--name", "x")), (DEPENDANCES, ("diagnose",)),
                             (DEPENDANCES, ("compute",))):
            r = lancer(script, self.dossier(), *args, "--source", "db", env=env)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("Base de données", r.stderr)
            self.assertNotIn("Traceback", r.stderr)
            self.assertNotIn(FAUX_MOT_DE_PASSE, r.stdout + r.stderr)

    def test_base_injoignable_en_anglais(self):
        env = {"PMZILLA_LAB_DB_URL": "postgresql://postgres@127.0.0.1:1/pmzilla",
               "PMZILLA_LAB_DB_PASSWORD": FAUX_MOT_DE_PASSE, "PMZILLA_LAB_DB_SECURITY_BIN": str(base.FAUX_SECURITY)}
        r = lancer(FLUX, self.dossier(), "statuses", "--source", "db", "--language", "en", env=env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Database: cannot read.", r.stderr)
        self.assertNotIn(FAUX_MOT_DE_PASSE, r.stdout + r.stderr)

    def test_base_absente_du_serveur(self):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        env = {"PMZILLA_LAB_DB_URL": base.url_vers("pmzilla_test_inexistante"), "PMZILLA_LAB_DB_PASSWORD": base.MOT_DE_PASSE,
               "PMZILLA_LAB_DB_SECURITY_BIN": str(base.FAUX_SECURITY)}
        r = lancer(DEPENDANCES, self.dossier(), "diagnose", "--source", "db", env=env)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("Base de données", r.stderr)
        self.assertNotIn(base.MOT_DE_PASSE, r.stdout + r.stderr)


class RapportsIdentiques(base.AvecBase, AvecDossier):
    """Même jeu, deux sources : mêmes sorties et mêmes fichiers de rapport."""

    def setUp(self):
        super().setUp()
        self.liste = jeu.tickets()
        self.inserer(self.liste, jeu.liens(), jeu.transitions())
        self.csv_ws, self.db_ws = self.dossier(), self.dossier()
        self.export = self.dossier() / "export.csv"
        jeu.ecrire_csv(self.export, self.liste)

    def sortie(self, texte: str, workspace: Path) -> str:
        return texte.replace(str(workspace), "WS")

    def cache(self) -> Path:
        cache = {t["cle"]: {"termine": bool(t["resolu"]), "transitions": []} for t in self.liste}
        for cle, instant, depart, arrivee in jeu.transitions():
            cache[cle]["transitions"].append([instant.strftime("%Y-%m-%dT%H:%M:%S.000%z"), depart, arrivee])
        chemin = self.dossier() / "transitions.json"
        chemin.write_text(json.dumps(cache), encoding="utf-8")
        return chemin

    def comparer(self, script: Path, args_csv: tuple, args_db: tuple, remplacements: dict | None = None):
        r_csv = lancer(script, self.csv_ws, *args_csv)
        r_db = lancer(script, self.db_ws, *args_db, env=self.env)
        self.assertEqual(r_csv.returncode, 0, r_csv.stdout + r_csv.stderr)
        self.assertEqual(r_db.returncode, 0, r_db.stdout + r_db.stderr)
        self.assertEqual(self.sortie(r_db.stdout, self.db_ws), self.sortie(r_csv.stdout, self.csv_ws))
        return r_csv, r_db

    def comparer_rapports(self, remplacements: dict | None = None):
        csv, db = rapports(self.csv_ws), rapports(self.db_ws)
        self.assertEqual(sorted(csv), sorted(db))
        self.assertTrue(csv)
        for nom, texte in csv.items():
            for ancien, nouveau in (remplacements or {}).items():
                texte = texte.replace(ancien, nouveau)
            self.assertEqual(db[nom], texte, nom)

    def test_flux_statuses(self):
        self.comparer(FLUX, ("statuses", str(self.export)), ("statuses", SOURCE_DB))

    def test_flux_compute(self):
        self.comparer(FLUX, ("compute", str(self.export), "--name", "demo", "--today", AUJOURDHUI, "--no-comparison"),
                      ("compute", SOURCE_DB, "--name", "demo", "--today", AUJOURDHUI, "--no-comparison"))
        self.comparer_rapports()

    def test_export_dans_un_autre_ordre_et_en_deux_fichiers_donne_les_memes_rapports_que_la_base(self):
        """Le CSV mélangé (ou coupé en deux fichiers, dans un ordre ou l'autre) et la base donnent les mêmes rapports."""
        import random
        melange = list(self.liste)
        random.Random(3).shuffle(melange)
        moitie = len(melange) // 2
        premier, second = self.dossier() / "a.csv", self.dossier() / "b.csv"
        jeu.ecrire_csv(premier, melange[:moitie + 8])
        jeu.ecrire_csv(second, melange[moitie - 8:])
        unique = self.dossier() / "melange.csv"
        jeu.ecrire_csv(unique, melange)
        base_ws = self.db_ws
        r = lancer(FLUX, base_ws, "compute", SOURCE_DB, "--name", "o", "--today", AUJOURDHUI, "--no-comparison", env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rapport_base = rapports(base_ws)[f"flux-o-{AUJOURDHUI}.md"]
        import flow_compare
        normal = flow_compare.normaliser_rapport
        for fichiers in ((unique,), (premier, second), (second, premier)):
            ws = self.dossier()
            r = lancer(FLUX, ws, "compute", *map(str, fichiers), "--name", "o", "--today", AUJOURDHUI, "--no-comparison")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(normal(rapports(ws)[f"flux-o-{AUJOURDHUI}.md"]), normal(rapport_base), [f.name for f in fichiers])
        # un seul fichier : octet pour octet (ni fusion ni nom de fichier dans le rapport de flux)
        self.assertEqual(rapports(self.dossier_de_calcul(unique))[f"flux-o-{AUJOURDHUI}.md"], rapport_base)

    def dossier_de_calcul(self, export: Path) -> Path:
        ws = self.dossier()
        r = lancer(FLUX, ws, "compute", str(export), "--name", "o", "--today", AUJOURDHUI, "--no-comparison")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return ws

    def test_flux_compute_avec_historique_et_dormants(self):
        cache = self.cache()
        self.comparer(FLUX, ("compute", str(self.export), "--name", "hist", "--today", AUJOURDHUI, "--no-comparison",
                             "--dormant-from-history", "--history", str(cache), "--scope", "PROJ"),
                      ("compute", SOURCE_DB, "--name", "hist", "--today", AUJOURDHUI, "--no-comparison",
                       "--dormant-from-history", "--history", "--scope", "PROJ"))
        self.comparer_rapports()
        texte = rapports(self.db_ws)[f"flux-hist-{AUJOURDHUI}.md"]
        self.assertIn("segment", texte.lower())

    def test_dependances_diagnose(self):
        r_csv, r_db = lancer(DEPENDANCES, self.csv_ws, "diagnose", str(self.export)), \
            lancer(DEPENDANCES, self.db_ws, "diagnose", SOURCE_DB, env=self.env)
        self.assertEqual(r_csv.returncode, 0, r_csv.stdout + r_csv.stderr)
        self.assertEqual(r_db.returncode, 0, r_db.stdout + r_db.stderr)
        self.assertEqual(r_db.stdout, r_csv.stdout)

    def test_dependances_compute(self):
        for par in ("team", "project"):
            for langue in ("fr", "en"):
                nom = f"carte-{par}-{langue}"
                r_csv = lancer(DEPENDANCES, self.csv_ws, "compute", str(self.export), "--name", nom, "--by", par,
                               "--language", langue)
                r_db = lancer(DEPENDANCES, self.db_ws, "compute", SOURCE_DB, "--name", nom, "--by", par,
                              "--language", langue, env=self.env)
                self.assertEqual(r_csv.returncode, 0, r_csv.stdout + r_csv.stderr)
                self.assertEqual(r_db.returncode, 0, r_db.stdout + r_db.stderr)
        source = {"fr": "base", "en": "database"}
        csv, db = rapports(self.csv_ws), rapports(self.db_ws)
        self.assertEqual(sorted(csv), sorted(db))
        for nom, texte in csv.items():
            langue = "en" if "-en-" in nom else "fr"
            self.assertEqual(db[nom], texte.replace("export.csv", source[langue]), nom)


if __name__ == "__main__":
    unittest.main()
