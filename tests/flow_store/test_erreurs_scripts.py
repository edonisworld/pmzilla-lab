"""Les outils de rapport face à une base injoignable ou absente, et les refus d'usage (change database-only, D6).

    bash tools/dbtest.sh flow_store          (instance jetable : installation.md, 14.5 ; sautés sans elle)

- une base injoignable donne un message clair, le code de sortie 1, sans mot de passe ni trace d'appel ;
- --source (quelle que soit sa valeur) et un fichier d'export sont refusés avant toute connexion : code 2, sans nommer le fichier ;
- statuses, compute et diagnose sont refusés dans une session Claude Code : code 3, avant toute lecture.
Aucune donnée réelle ; Flux-Lab est isolé dans un dossier temporaire (PMZILLA_LAB_WORKSPACE).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import aide_base as base  # noqa: E402
from aide_base import MOT_DE_PASSE as MOT_DE_PASSE_BASE  # noqa: E402  (nom de constante : la garde des secrets n'y voit pas un littéral)
from aide_scripts import AvecDossier, DEPENDANCES, FAUX_MOT_DE_PASSE, FLUX, lancer  # noqa: E402

PORT_FERME = {"PMZILLA_LAB_DB_PORT": "1"}


def env_base_injoignable() -> dict:
    return {"PMZILLA_LAB_DB_URL": "postgresql://postgres@127.0.0.1:1/pmzilla", "PMZILLA_LAB_DB_PASSWORD": FAUX_MOT_DE_PASSE,
            "PMZILLA_LAB_DB_SECURITY_BIN": str(base.FAUX_SECURITY)}


class Erreurs(AvecDossier):
    def test_source_retiree_quelle_que_soit_la_valeur(self):
        for script, commande in ((FLUX, "statuses"), (FLUX, "compute"), (DEPENDANCES, "diagnose"), (DEPENDANCES, "compute")):
            for valeur in ("db", "csv", "ftp"):
                r = lancer(script, self.dossier(), commande, "--source", valeur, env=PORT_FERME)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("--source est retirée : la base est la seule source", r.stderr)
                self.assertNotIn("Traceback", r.stderr)

    def test_fichiers_refuses_avant_toute_connexion(self):
        for script, commande in ((FLUX, "statuses"), (FLUX, "compute"), (DEPENDANCES, "diagnose"), (DEPENDANCES, "compute")):
            for langue, attendu in (("fr", "les fichiers d'export ne sont plus lus : la base est la seule source"),
                                    ("en", "export files are no longer read: the database is the only source")):
                r = lancer(script, self.dossier(), commande, "export-secret.csv", "--language", langue, env=PORT_FERME)
                texte = r.stdout + r.stderr
                self.assertEqual(r.returncode, 2, texte)
                self.assertIn(attendu, texte, f"{script.name} {commande} {langue}")
                self.assertNotIn("export-secret", texte)
                self.assertNotIn("Traceback", texte)
                self.assertNotIn("injoignable", texte)               # refusé avant toute connexion à la base

    def test_session_claude_code_refusee_avant_toute_lecture(self):
        for script, commande in ((FLUX, "statuses"), (FLUX, "compute"), (DEPENDANCES, "diagnose"), (DEPENDANCES, "compute")):
            for langue, attendu in (("fr", "Refusé dans une session Claude Code"), ("en", "Refused inside a Claude Code session")):
                r = lancer(script, self.dossier(), commande, "--language", langue, env={**PORT_FERME, "CLAUDECODE": "1"})
                self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
                self.assertIn(attendu, r.stdout + r.stderr)

    def test_base_injoignable(self):
        env = env_base_injoignable()
        for script, args in ((FLUX, ("statuses",)), (FLUX, ("compute", "--name", "x")), (DEPENDANCES, ("diagnose",)),
                             (DEPENDANCES, ("compute",))):
            r = lancer(script, self.dossier(), *args, env=env)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("Base de données", r.stderr)
            self.assertNotIn("Traceback", r.stderr)
            self.assertNotIn(FAUX_MOT_DE_PASSE, r.stdout + r.stderr)

    def test_base_injoignable_en_anglais(self):
        r = lancer(FLUX, self.dossier(), "statuses", "--language", "en", env=env_base_injoignable())
        self.assertEqual(r.returncode, 1)
        self.assertIn("Database: cannot read.", r.stderr)
        self.assertNotIn(FAUX_MOT_DE_PASSE, r.stdout + r.stderr)

    def test_base_absente_du_serveur(self):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        env = {"PMZILLA_LAB_DB_URL": base.url_vers("pmzilla_test_inexistante"), "PMZILLA_LAB_DB_PASSWORD": MOT_DE_PASSE_BASE,
               "PMZILLA_LAB_DB_SECURITY_BIN": str(base.FAUX_SECURITY)}
        r = lancer(DEPENDANCES, self.dossier(), "diagnose", env=env)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("Base de données", r.stderr)
        self.assertNotIn(base.MOT_DE_PASSE, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
