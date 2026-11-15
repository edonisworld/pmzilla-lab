"""Garde de session, niveau 1 (change session-guard-n1, tâche 7.2) : le contrat du hook avec Claude Code. JSON PreToolUse sur l'entrée standard, code 0 pour
laisser passer et 2 pour refuser, la ligne exacte de D10 sur la sortie d'erreur, rien sur la sortie standard, la commande jamais imprimée, `entrée illisible`
et `erreur interne de la garde` (avec un doublon de test), et l'appel de npm_guard.avec_rappel.

    bash tests/run_all.sh garde_session
"""
import contextlib
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide import Arbre, RACINE, g  # noqa: E402
import npm_guard  # noqa: E402

OUTIL = RACINE / "tools" / "garde_session.py"
LIGNE_A1 = "garde de session : refusé : A1 : git push, send-pack ou http-push. Voie permise : le train lancé par l'auteur.\n"
LIGNE_ILLISIBLE = "garde de session : refusé : — : entrée illisible. Voie permise : relancer la commande ; si le refus revient, le signaler.\n"
LIGNE_INTERNE = "garde de session : refusé : — : erreur interne de la garde. Voie permise : relancer la commande ; si le refus revient, le signaler.\n"


def entree(commande, cwd, outil="Bash"):
    return json.dumps({"tool_name": outil, "tool_input": {"command": commande}, "cwd": str(cwd)})


class Processus(unittest.TestCase):
    """Le hook lancé comme Claude Code le lance : un processus, l'entrée sur l'entrée standard."""

    @classmethod
    def setUpClass(cls):
        cls.a = Arbre()

    @classmethod
    def tearDownClass(cls):
        cls.a.fermer()

    def lancer(self, texte):
        return subprocess.run([sys.executable, "-I", str(OUTIL)], input=texte, capture_output=True, text=True, cwd=self.a.tmp)

    def test_refus_code_2_et_ligne_exacte(self):
        r = self.lancer(entree("git push origin main", self.a.tmp))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertEqual(r.stderr, LIGNE_A1)

    def test_la_commande_n_est_jamais_imprimee(self):
        r = self.lancer(entree("git push https://exemple.invalid/SECRET-1234 --repo /Users/quelquun/chemin", self.a.tmp))
        self.assertEqual(r.returncode, 2)
        for fragment in ("SECRET-1234", "exemple.invalid", "/Users/quelquun"):
            self.assertNotIn(fragment, r.stderr)

    def test_commande_permise_code_0_sans_sortie(self):
        for commande in ("ls", "git status", "echo bonjour", "gh issue list"):
            with self.subTest(commande=commande):
                r = self.lancer(entree(commande, self.a.tmp))
                self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_autre_outil_et_commande_vide_code_0(self):
        for texte in (entree("git push", self.a.tmp, outil="Edit"), entree("", self.a.tmp), entree("   ", self.a.tmp)):
            with self.subTest(texte=texte):
                r = self.lancer(texte)
                self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_entree_illisible_refuse(self):
        for texte in ("", "pas du json", "[]", "null", '{"tool_name": "Bash"}', '{"tool_name": "Bash", "tool_input": {"command": 3}}',
                      '{"tool_name": "Bash", "tool_input": "x"}', "{"):
            with self.subTest(texte=texte):
                r = self.lancer(texte)
                self.assertEqual(r.returncode, 2)
                self.assertEqual(r.stdout, "")
                self.assertEqual(r.stderr, LIGNE_ILLISIBLE)

    def test_json_trop_profond_refuse_sans_trace(self):
        profond = "[" * 100000 + "]" * 100000
        r = self.lancer('{"tool_name": "Bash", "tool_input": {"command": "ls"}, "x": ' + profond + "}")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertNotIn("Traceback", r.stderr)
        self.assertTrue(r.stderr.startswith("garde de session : refusé"))

    def test_une_ligne_et_une_seule_sur_la_sortie_d_erreur(self):
        r = self.lancer(entree("git push", self.a.tmp))
        self.assertEqual(len(r.stderr.splitlines()), 1)


class Appel(unittest.TestCase):
    """main() appelé en direct : le doublon de test force l'erreur interne ; l'analyseur de npm_guard est appelé avec un rappel."""

    @classmethod
    def setUpClass(cls):
        cls.a = Arbre()

    @classmethod
    def tearDownClass(cls):
        cls.a.fermer()

    def main(self, texte):
        erreur = io.StringIO()
        with contextlib.redirect_stderr(erreur), contextlib.redirect_stdout(io.StringIO()) as sortie:
            code = g.main([], texte, self.a.contexte())
        return code, sortie.getvalue(), erreur.getvalue()

    def test_erreur_interne_refuse(self):
        original = g.decider
        g.decider = lambda commande, contexte=None: 1 / 0
        try:
            self.assertEqual(self.main(entree("ls", self.a.tmp)), (2, "", LIGNE_INTERNE))
        finally:
            g.decider = original

    def test_recursion_interne_refuse(self):
        original = g.decider

        def recursif(commande, contexte=None):
            return recursif(commande, contexte)
        g.decider = recursif
        try:
            self.assertEqual(self.main(entree("ls", self.a.tmp)), (2, "", LIGNE_INTERNE))
        finally:
            g.decider = original

    def test_la_garde_appelle_l_analyseur_de_npm_guard_avec_un_rappel(self):
        appels = []
        original = npm_guard.avec_rappel

        def espion(commande, rappel):
            appels.append((commande, type(rappel).__name__))
            return original(commande, rappel)
        npm_guard.avec_rappel = espion
        try:
            self.assertEqual(self.main(entree("git push", self.a.tmp))[0], 2)
        finally:
            npm_guard.avec_rappel = original
        self.assertEqual(appels, [("git push", "Collecte")])

    def test_decider_est_pure_et_rend_un_verdict_structure(self):
        v = g.decider("git push", self.a.contexte())
        self.assertEqual((v.classe, v.cle), ("A1", "A1"))
        self.assertIsNone(g.decider("ls", self.a.contexte()))

    def test_les_codes_de_main(self):
        self.assertEqual(self.main(entree("ls", self.a.tmp))[0], 0)
        self.assertEqual(self.main(entree("git push", self.a.tmp))[0], 2)
        self.assertEqual(self.main("n'importe quoi")[0], 2)


class Sobriete(unittest.TestCase):
    """Bibliothèque standard seulement ; la garde n'écrit aucun fichier ; elle ne lance que des lectures de Git."""

    def test_source(self):
        source = OUTIL.read_text(encoding="utf-8")
        self.assertTrue(source.startswith("#!/usr/bin/env python3\n"))
        for interdit in ("write_text", "import socket", "urllib", "import requests", "import yaml", "os.system", "shutil", "os.remove", "os.unlink",
                         'open(fichier, "w', "write("):
            self.assertNotIn(interdit, source, interdit)
        for ligne in source.splitlines():
            if ligne.startswith(("import ", "from ")):
                self.assertIn(ligne.split()[1], {"json", "os", "pwd", "re", "subprocess", "sys", "typing", "npm_guard", "lab_paths"}, ligne)   # pwd : R-20261111-48 (base des comptes, jamais HOME)

    def test_les_seules_commandes_lancees_sont_des_lectures_de_git(self):
        source = OUTIL.read_text(encoding="utf-8")
        self.assertEqual(source.count("subprocess.run("), 1)
        self.assertIn('["git", *args]', source)
        for appel in ('["config", "--get-all", "core.hooksPath"]', '["rev-parse", "--path-format=absolute", "--git-common-dir"]'):
            self.assertIn(appel, source)


if __name__ == "__main__":
    unittest.main()
