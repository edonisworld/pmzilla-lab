"""Les trois modules du manuel (manual_python, manual_shell, manual_deny) sur le faux dépôt : formes des données retournées.

Rien n'est lancé ni importé de ce qu'ils lisent (sentinelle). Sans réseau.

    uv run python -m unittest discover -s tests/manual
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixtures  # noqa: E402
import manual_deny  # noqa: E402
import manual_python  # noqa: E402
import manual_shell  # noqa: E402


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dossier = Path(tempfile.mkdtemp(prefix="manuel-modules-"))
        cls.sentinelle = cls.dossier / "SENTINELLE"
        cls.depot = cls.dossier / "depot"
        fixtures.construire_depot(cls.depot, cls.sentinelle)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dossier, True)

    def tearDown(self):
        self.assertFalse(self.sentinelle.exists())


class ManualPython(Base):
    def lire(self, nom):
        return manual_python.lire_script(self.depot / "tools" / nom)

    def test_module_de_bibliotheque(self):
        self.assertIsNone(self.lire("bibliotheque_lib.py"))

    def test_role_usages_et_codes(self):
        donnees = self.lire("outil_simple.py")
        self.assertEqual(donnees["role"], "Outil simple de démonstration.")
        self.assertEqual(donnees["usages"], ["uv run tools/outil_simple.py --mode json"])
        self.assertEqual(donnees["codes"], ["0 succès", "1 échec", "2 erreur d'usage"])

    def test_arguments_et_arguments_caches(self):
        arguments = {a["noms"][0]: a for a in self.lire("outil_simple.py")["parseur"]["arguments"]}
        self.assertEqual(sorted(arguments), ["--mode", "--verbose", "fichier"])
        self.assertEqual(arguments["--mode"]["choix"], ["json", "text"])
        self.assertEqual(arguments["--mode"]["defaut"], "text")
        self.assertTrue(arguments["fichier"]["positionnel"])

    def test_sous_commandes_et_valeurs_calculees(self):
        parseur = self.lire("outil_sous.py")["parseur"]
        self.assertTrue(parseur["sous_commandes_requises"])
        sous = {s["nom"]: s for s in parseur["sous_commandes"]}
        self.assertEqual(list(sous), ["test", "local", "calcul", "origine", "profond"])
        self.assertEqual(sous["profond"]["sous_commandes"], ["un", "deux"])
        calcul = {a["noms"][0]: a for a in sous["calcul"]["arguments"]}
        self.assertEqual(calcul["--calculee"]["choix"], manual_python.VALEUR_CALCULEE)
        self.assertEqual(calcul["--json"]["exclusif"], calcul["--csv"]["exclusif"])
        self.assertIsNotNone(calcul["--json"]["exclusif"])

    def test_script_sans_parseur(self):
        donnees = self.lire("outil_sans_parseur.py")
        self.assertTrue(donnees["sans_parseur"])
        self.assertIsNone(donnees["parseur"])
        self.assertEqual(len(donnees["usages"]), 2)

    def test_aide_partagee(self):
        parseur = self.lire("outil_aide.py")["parseur"]
        self.assertTrue(parseur["fonction_partagee"])
        self.assertIn("--language", [a["noms"][0] for a in parseur["arguments"]])

    def test_source_illisible_remonte(self):
        casse = self.dossier / "casse.py"
        casse.write_text("def (:\n", encoding="utf-8")
        with self.assertRaises(SyntaxError):
            manual_python.lire_script(casse)


class ManualShell(Base):
    def test_en_tete(self):
        donnees = manual_shell.lire_shell(self.depot / "tools" / "lanceur.sh")
        self.assertEqual(donnees["role"], "PMZilla Lab : lanceur de démonstration. Deuxième ligne du rôle.")
        self.assertEqual(donnees["usages"], [{"commande": "bash tools/lanceur.sh", "explication": "lance tout"},
                                             {"commande": "bash tools/lanceur.sh --seulement", "explication": "seulement la moitié"}])
        self.assertEqual(donnees["codes"], ["0 succès", "1 échec", "2 erreur d'usage"])

    def test_sans_en_tete(self):
        donnees = manual_shell.lire_shell(self.depot / "tools" / "sans_entete.sh")
        self.assertEqual((donnees["role"], donnees["usages"], donnees["codes"]), (None, [], None))

    def test_commande_slash(self):
        donnees = manual_shell.lire_commande(self.depot / ".claude" / "commands" / "demo.md")
        self.assertEqual(donnees, {"nom": "demo", "description": "Commande de démonstration pour le manuel",
                                   "indice_argument": "[fr|en]", "modele": "sonnet"})
        self.assertEqual(manual_shell.exemple_commande("demo", "[fr|en]"), "/demo [fr|en]")
        self.assertEqual(manual_shell.exemple_commande("marqueur", "<identifiant>"), "/marqueur")

    def test_scripts_planifies_et_listes(self):
        self.assertEqual(manual_shell.scripts_planifies(self.depot / "tools"), {"tools/planifie.sh"})
        noms = [c.name for c in manual_shell.scripts_shell(self.depot)]
        self.assertEqual(noms, ["lanceur.sh", "planifie.sh", "sans_entete.sh"])
        self.assertEqual([c.name for c in manual_shell.commandes_slash(self.depot)], ["demo.md", "marqueur.md"])


class ManualDeny(Base):
    def regles(self):
        return manual_deny.lire_regles(self.depot / ".claude" / "settings.json")

    def test_seules_les_regles_bash_sont_lues(self):
        regles = self.regles()
        self.assertIn("uv run tools/outil_sous.py test*", regles)
        self.assertFalse([r for r in regles if r.startswith("Read") or r.startswith("Bash(")])

    def test_classement(self):
        regles = self.regles()
        classer = manual_deny.classer
        self.assertEqual(classer(regles, "outil_sous.py", "python", "test"), "Terminal seulement")
        self.assertEqual(classer(regles, "outil_sous.py", "python", "local"), "Terminal ou Claude Code")
        self.assertEqual(classer(regles, "outil_sous.py", "python", "calcul", ["--source fichier", "--source db"]),
                         "Terminal seulement avec `--source db`")
        self.assertEqual(classer(regles, "lanceur.sh", "shell"), "Terminal seulement")
        self.assertEqual(classer(regles, "outil_simple.py", "python"), "Terminal ou Claude Code")

    def test_fichier_absent(self):
        self.assertEqual(manual_deny.lire_regles(self.dossier / "absent.json"), [])


if __name__ == "__main__":
    unittest.main()
