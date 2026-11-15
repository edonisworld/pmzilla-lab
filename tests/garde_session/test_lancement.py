"""Garde de session, niveau 1 (change session-guard-n1, tâches 8.2 et D2) : les trois gardes PreToolUse sont lancées par le chemin absolu de leur copie avec
`python3 -I`, depuis un autre dossier de travail, et chargent leurs modules voisins depuis leur propre dossier. Un module de même nom planté dans le dossier
courant n'est jamais chargé.

    bash tests/run_all.sh garde_session
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
OUTILS = RACINE / "tools"
MARQUE = "MODULE-PLANTE-CHARGE"
VOISINS = ("npm_guard", "npm_ci_conditions", "lab_paths", "garde_session", "pipe_guard", "json", "re", "os")


def entree(commande, cwd):
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": commande}, "cwd": str(cwd)})


class LancementParCheminAbsolu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="garde-lancement-")).resolve()
        cls.autre = cls.tmp / "autre"
        cls.autre.mkdir()
        for nom in VOISINS:   # un module de chaque nom voisin, dans le dossier courant du processus : il afficherait la marque s'il était chargé
            (cls.autre / f"{nom}.py").write_text(f"print({MARQUE!r})\nraise SystemExit(99)\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def lancer(self, garde, texte, *options):
        return subprocess.run([sys.executable, "-I", str(OUTILS / garde), *options], input=texte, capture_output=True, text=True, cwd=self.autre)

    def test_garde_de_session_depuis_un_autre_dossier(self):
        r = self.lancer("garde_session.py", entree("git push", self.autre))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertTrue(r.stderr.startswith("garde de session : refusé : A1 : "))
        r = self.lancer("garde_session.py", entree("ls", self.autre))
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_garde_npm_depuis_un_autre_dossier(self):
        r = self.lancer("npm_guard.py", entree("npm install x", self.autre))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertTrue(r.stderr.startswith("garde npm : refusé"))
        self.assertNotIn(MARQUE, r.stdout + r.stderr)

    def test_garde_npm_charge_le_module_des_conditions_de_npm_ci_depuis_son_dossier(self):
        """Sous -I, le dossier du script n'est pas sur sys.path : sans le chargement des voisins, `npm ci` donnerait « vérification impossible »."""
        r = self.lancer("npm_guard.py", entree("npm ci", self.autre))
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("vérification impossible", r.stderr)
        self.assertNotIn(MARQUE, r.stdout + r.stderr)

    def test_garde_des_tubes_depuis_un_autre_dossier(self):
        r = self.lancer("pipe_guard.py", entree("cat x | grep y", self.autre), "--event", "pre")
        self.assertEqual(r.returncode, 0)
        self.assertIn("additionalContext", r.stdout)
        self.assertNotIn(MARQUE, r.stdout + r.stderr)

    def test_aucune_garde_n_utilise_le_dossier_courant(self):
        for garde in ("garde_session.py", "npm_guard.py"):
            with self.subTest(garde=garde):
                r = self.lancer(garde, entree("ls", self.autre))
                self.assertEqual((r.returncode, r.stdout), (0, ""))
                self.assertNotIn(MARQUE, r.stderr)

    def test_le_dossier_du_fichier_passe_en_tete_avant_l_import_d_un_voisin(self):
        for garde in ("garde_session.py", "npm_guard.py"):
            source = (OUTILS / garde).read_text(encoding="utf-8")
            with self.subTest(garde=garde):
                self.assertIn("os.path.realpath(__file__)", source)
                self.assertIn("sys.path.insert(0, _DOSSIER)", source)
                self.assertLess(source.index("sys.path.insert(0, _DOSSIER)"), source.index("import npm_guard") if garde == "garde_session.py"
                                else source.index("VAR_DEB, VAR_FIN"))
                # Le bloc de mise en tête du dossier n'utilise pas la variable du dossier du projet. La variable reste permise ailleurs :
                # npm_guard la range parmi les variables bénignes (BENIGNES, tests/npm_guard/test_npm_guard.py l'exige), ce n'est pas un lancement.
                debut = source.index("_DOSSIER = ")
                self.assertNotIn("CLAUDE_PROJECT_DIR", source[debut:source.index("sys.path.insert(0, _DOSSIER)") + 40])


if __name__ == "__main__":
    unittest.main()
