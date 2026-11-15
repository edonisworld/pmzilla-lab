"""Sobriété de `npm ci` par la session (change npm-ci-session, design D6) : le module des conditions ne fait que lire. Son code source n'importe que la
bibliothèque standard (et les deux modules de tools/ que la conception nomme : la garde, pour son lecteur de shell, et le module des chemins du
lab) ; il ne touche pas au réseau, n'ouvre aucun fichier en écriture, ne lance que `git` avec les sous-commandes de lecture fixées, l'entrée
standard fermée et aucune variable GIT_* ; il ne fetch, ne pull, ne lance ni npm ni node. La garde ne l'importe que dans le chemin de `npm ci`.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/npm_guard -q -f
"""
import ast
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_npm_ci import AvecDepot, RACINE, npm_ci_conditions  # noqa: E402
import finish_lock  # noqa: E402

MODULE = RACINE / "tools" / "npm_ci_conditions.py"
GARDE = RACINE / "tools" / "npm_guard.py"
MODULES_DE_TOOLS = {"npm_guard", "lab_paths"}
LECTURES = {"rev-parse", "ls-tree", "status", "cat-file"}
RESEAU = {"socket", "ssl", "http", "urllib", "ftplib", "smtplib", "requests", "httpx", "xmlrpc", "asyncio", "telnetlib"}
ECRITURES = {"write_text", "write_bytes", "mkdir", "makedirs", "unlink", "remove", "rmdir", "rmtree", "rename", "touch",
             "symlink", "link", "chmod", "chown", "truncate", "copy", "copy2", "copytree", "move", "utime", "mkfifo"}   # « replace » : str.replace aussi


def arbre():
    return ast.parse(MODULE.read_text(encoding="utf-8"))


def importes(noeud):
    noms = set()
    for n in ast.walk(noeud):
        if isinstance(n, ast.Import):
            noms.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            noms.add(n.module.split(".")[0])
    return noms


class SourceDuModule(unittest.TestCase):
    def test_bibliotheque_standard_et_deux_modules_de_tools(self):
        standard = getattr(sys, "stdlib_module_names", None)
        self.assertIsNotNone(standard, "Python 3.10 ou plus attendu")
        for nom in importes(arbre()):
            self.assertTrue(nom in standard or nom in MODULES_DE_TOOLS, f"import hors bibliothèque standard : {nom}")

    def test_aucun_import_reseau(self):
        self.assertEqual(importes(arbre()) & RESEAU, set())

    def test_aucun_fichier_ouvert_en_ecriture(self):
        for n in ast.walk(arbre()):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open":
                mode = n.args[1] if len(n.args) > 1 else next((k.value for k in n.keywords if k.arg == "mode"), None)
                self.assertIsInstance(mode, ast.Constant, "mode d'ouverture non littéral")
                self.assertEqual(set(mode.value) & set("wax+"), set(), f"ouverture en écriture, ligne {n.lineno}")
                self.assertIn("r", mode.value)
            if isinstance(n, ast.Attribute):
                self.assertNotIn(n.attr, ECRITURES, f"écriture sur le disque, ligne {n.lineno}")

    def test_un_seul_appel_de_sous_processus_et_c_est_git_en_lecture(self):
        source = MODULE.read_text(encoding="utf-8")
        self.assertEqual(source.count("subprocess.run("), 1)
        for interdit in ("Popen", "os.system", "os.popen", "os.exec", "os.spawn", "shell=True", "check_output", "call("):
            self.assertNotIn(interdit, source, interdit)
        self.assertIn('["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", self.dossier, sous_commande, *arguments]', source)
        self.assertIn("stdin=subprocess.DEVNULL", source)
        self.assertIn("env=ENV_GIT", source)
        self.assertIn("timeout=reste", source)

    def test_les_sous_commandes_de_git_sont_fixees(self):
        self.assertEqual(set(npm_ci_conditions.LECTURES_GIT), LECTURES)
        appels = [n for n in ast.walk(arbre()) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "lire"]
        self.assertGreaterEqual(len(appels), 5)
        for appel in appels:
            self.assertIsInstance(appel.args[0], ast.Constant, f"sous-commande non littérale, ligne {appel.lineno}")
            self.assertIn(appel.args[0].value, LECTURES)

    def test_aucun_fetch_pull_npm_ni_node_parmi_les_arguments_litteraux(self):
        """Les chaînes littérales du code (docstrings exclues) ne nomment ni une écriture de Git, ni npm, ni node."""
        interdits = {"fetch", "pull", "push", "clone", "checkout", "commit", "add", "reset", "gc", "update-ref", "config",
                     "curl", "ssh"}   # npm et node : « npm » est un mot du lecteur de forme ; le test des appels de sous-processus les exclut
        docstrings = set()
        for n in ast.walk(arbre()):
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)):
                corps = n.body
                if corps and isinstance(corps[0], ast.Expr) and isinstance(corps[0].value, ast.Constant):
                    docstrings.add(id(corps[0].value))
        for n in ast.walk(arbre()):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings:
                self.assertNotIn(n.value, interdits, f"ligne {n.lineno}")

    def test_le_nom_du_verrou_est_celui_de_finish_lock(self):
        """Source : tools/finish_lock.py ; ce module en garde une copie pour ne rien importer qui regarde l'état d'un processus."""
        self.assertEqual(npm_ci_conditions.NOM_VERROU, finish_lock.LOCK_NAME)

    def test_le_module_ne_nomme_ni_ne_cree_le_verrou(self):
        source = MODULE.read_text(encoding="utf-8")
        self.assertNotIn("finish_lock", source.replace("tools/finish_lock.py", ""))


class ImportDansLaGarde(unittest.TestCase):
    def test_le_module_n_est_importe_que_dans_le_chemin_de_npm_ci(self):
        tete = ast.parse(GARDE.read_text(encoding="utf-8"))
        for n in tete.body:
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                self.assertNotIn("npm_ci_conditions", importes(n), "import au niveau du module")
        fonctions = [n for n in ast.walk(tete) if isinstance(n, ast.FunctionDef) and "npm_ci_conditions" in importes(n)]
        self.assertEqual([f.name for f in fonctions], ["_npm_ci"])

    def test_refus_de_reste_pur_et_ne_connait_pas_le_module(self):
        tete = ast.parse(GARDE.read_text(encoding="utf-8"))
        refus_de = next(n for n in tete.body if isinstance(n, ast.FunctionDef) and n.name == "refus_de")
        self.assertNotIn("npm_ci_conditions", ast.dump(refus_de))

    def test_la_garde_n_importe_pas_le_module_pour_une_autre_commande(self):
        import io
        import json
        import contextlib
        import npm_guard
        sys.modules.pop("npm_ci_conditions", None)
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                for commande in ("ls", "npm test", "npm install x", "node server.js"):
                    npm_guard.main([], json.dumps({"tool_name": "Bash", "tool_input": {"command": commande}}))
            self.assertNotIn("npm_ci_conditions", sys.modules)
        finally:
            sys.modules["npm_ci_conditions"] = npm_ci_conditions


class AppelsEnVrai(AvecDepot):
    """Les appels de sous-processus d'une vérification complète, enregistrés : seuls des `git` en lecture, entrée standard fermée, sans GIT_*."""

    def test_chaque_appel_est_un_git_de_lecture(self):
        import subprocess
        vrai = subprocess.run
        vus = []

        def enregistre(argv, *a, **k):
            vus.append((list(argv), k))
            return vrai(argv, *a, **k)

        with mock.patch.object(npm_ci_conditions.subprocess, "run", side_effect=enregistre):
            self.assertEqual(npm_ci_conditions.verifier(self.mothra, self.depot.worktrees), [])
        self.assertGreaterEqual(len(vus), 5)
        for argv, k in vus:
            self.assertEqual(argv[0], "git", argv)
            self.assertIn(argv[argv.index("-C") + 2], LECTURES, argv)
            self.assertIs(k["stdin"], subprocess.DEVNULL)
            self.assertFalse([v for v in k["env"] if v.startswith("GIT_")])
            self.assertEqual(k["env"]["PATH"], "/usr/bin:/bin:/usr/sbin:/sbin")
            self.assertGreater(k["timeout"], 0)
            self.assertLessEqual(k["timeout"], npm_ci_conditions.DELAI_TOTAL)
            self.assertNotIn("shell", k)

    def test_les_variables_git_de_l_appelant_ne_passent_pas(self):
        import os
        with mock.patch.dict(os.environ, {"GIT_DIR": "/nulle/part", "GIT_WORK_TREE": "/nulle/part", "GIT_INDEX_FILE": "/nulle/part"}):
            self.assertEqual(npm_ci_conditions.verifier(self.mothra, self.depot.worktrees), [])

    def test_une_verification_ne_modifie_rien(self):
        """Ni index, ni références, ni verrou : les fichiers du dépôt sont les mêmes avant et après."""
        import os

        def etat():
            sortie = {}
            for racine in (self.depot.commun, self.wt):
                for dossier, _, fichiers in os.walk(racine):
                    for nom in fichiers:
                        chemin = os.path.join(dossier, nom)
                        sortie[chemin] = os.path.getmtime(chemin)
            return sortie

        avant = etat()
        self.assertEqual(npm_ci_conditions.verifier(self.mothra, self.depot.worktrees), [])
        self.assertEqual(etat(), avant)


if __name__ == "__main__":
    unittest.main()
