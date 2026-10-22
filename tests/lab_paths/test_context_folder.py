"""
Le dossier de contexte dans les modules partagés des chemins du lab (organisation-context, design D16, tâche 9.2) :
tools/lab_paths.py et tools/lab_paths.sh.

    bash tests/run_all.sh lab_paths

Même règle dans les deux langages (PMZILLA_LAB_CONTEXT si posée et non vide, tilde développé, sinon `contexte` du dossier du lab),
septième ligne imprimée `context_folder=<chemin>`, jamais rien d'ouvert, de listé ni de testé à l'intérieur du dossier, et aucun
fichier de code suivi de tools/ qui écrive l'ancien nom du dossier.
"""
import builtins
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_lab_paths import SHELLS, Lab, lire, reel  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
OUTILS = RACINE / "tools"
sys.path.insert(0, str(OUTILS))
import lab_paths  # noqa: E402

ANCIEN_NOM = "Contexte" + "-Lab"      # écrit en deux morceaux : ce fichier ne porte pas l'ancien nom en littéral


class TestDossierDeContexte(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.lab = Lab(Path(cls._tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_defaut_sous_le_dossier_du_lab_dans_les_deux_langages(self):
        attendu = os.path.join(reel(self.lab.lab), "contexte")
        py = self.lab.python(self.lab.principal)
        self.assertEqual(py.returncode, 0, py.stderr)
        self.assertEqual(reel(lire(py.stdout)["context_folder"]), attendu)
        for interprete in SHELLS:
            with self.subTest(interprete):
                sh = self.lab.shell(interprete, self.lab.principal)
                self.assertEqual(sh.returncode, 0, sh.stderr)
                self.assertEqual(lire(sh.stdout), lire(py.stdout))

    def test_septieme_ligne_imprimee(self):
        # lab-folder-layout (D1, Q10) : `worktrees_folder` s'ajoute après lui ; le dossier de contexte reste la septième ligne sur huit
        # (ancien nom du cas : « septième ligne imprimée et dernière », faux depuis cette décision).
        py = self.lab.python(self.lab.principal)
        lignes = py.stdout.strip().splitlines()
        self.assertEqual(len(lignes), 8)
        self.assertTrue(lignes[6].startswith("context_folder="))
        for interprete in SHELLS:
            sh = self.lab.shell(interprete, self.lab.principal)
            self.assertEqual(len(sh.stdout.strip().splitlines()), 8)
            self.assertTrue(sh.stdout.strip().splitlines()[6].startswith("context_folder="))

    def test_variable_avec_tilde_developpe_et_git_non_interroge(self):
        extra = {"PMZILLA_LAB_CONTEXT": "~/ailleurs/contexte", "PMZILLA_LAB_WORKSPACE": str(self.lab.principal)}
        attendu = str(self.lab.home / "ailleurs" / "contexte")
        py = self.lab.python(self.lab.copie, **extra)         # copie hors Git : seule la variable du contenu la rend résoluble
        self.assertEqual(py.returncode, 0, py.stderr)
        self.assertEqual(lire(py.stdout)["context_folder"], attendu)
        for interprete in SHELLS:
            with self.subTest(interprete):
                sh = self.lab.shell(interprete, self.lab.copie, **extra)
                self.assertEqual(lire(sh.stdout)["context_folder"], attendu)

    def test_variable_vide_vaut_non_posee(self):
        py = self.lab.python(self.lab.principal, PMZILLA_LAB_CONTEXT="")
        self.assertEqual(reel(lire(py.stdout)["context_folder"]), os.path.join(reel(self.lab.lab), "contexte"))
        for interprete in SHELLS:
            sh = self.lab.shell(interprete, self.lab.principal, PMZILLA_LAB_CONTEXT="")
            self.assertEqual(lire(sh.stdout), lire(py.stdout))

    def test_variable_shell_exportee(self):
        commande = f'. "{self.lab.principal}/tools/lab_paths.sh" && lab_paths_init && printenv LAB_CONTEXT_FOLDER'
        for interprete in SHELLS:
            r = subprocess.run([interprete, "-c", commande], capture_output=True, text=True, env=self.lab.env(), cwd=str(self.lab.tmp))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(reel(r.stdout.strip()), os.path.join(reel(self.lab.lab), "contexte"))

    def test_le_dossier_n_est_pas_cree(self):
        extra = {"PMZILLA_LAB_CONTEXT": str(self.lab.tmp / "contexte-jamais-cree")}
        self.lab.python(self.lab.principal, **extra)
        for interprete in SHELLS:
            self.lab.shell(interprete, self.lab.principal, **extra)
        self.assertFalse((self.lab.tmp / "contexte-jamais-cree").exists())

    def test_rien_n_est_touche_dans_le_dossier(self):
        dossier = self.lab.tmp / "contexte-surveille"
        (dossier / "originaux").mkdir(parents=True)
        (dossier / "originaux" / "piege.txt").write_text("SENTINELLE", encoding="utf-8")
        env = {"PMZILLA_LAB_CONTEXT": str(dossier), "PMZILLA_LAB_WORKSPACE": str(self.lab.principal)}
        vus = []
        sous = str(dossier)

        def garde(original):
            def enveloppe(chemin, *args, **kwargs):
                if isinstance(chemin, (str, bytes, os.PathLike)) and os.fsdecode(chemin).startswith(sous):
                    vus.append(os.fsdecode(chemin))
                return original(chemin, *args, **kwargs)
            return enveloppe

        with mock.patch.object(os, "stat", garde(os.stat)), mock.patch.object(os, "scandir", garde(os.scandir)), \
                mock.patch.object(os, "listdir", garde(os.listdir)), mock.patch.object(os, "open", garde(os.open)), \
                mock.patch.object(builtins, "open", garde(builtins.open)):
            resultat = lab_paths.resolve(env, OUTILS / "lab_paths.py")
        self.assertEqual(resultat["context_folder"], dossier)
        self.assertEqual(vus, [])
        # le shell : la sortie ne porte jamais la sentinelle, et le dossier garde son contenu
        for interprete in SHELLS:
            sh = self.lab.shell(interprete, self.lab.principal, **env)
            self.assertNotIn("SENTINELLE", sh.stdout + sh.stderr)

    def test_fonction_context_folder(self):
        contenu = Path("/x/lab/workspace")
        self.assertEqual(lab_paths.context_folder(contenu, {}), Path("/x/lab/contexte"))
        self.assertEqual(lab_paths.context_folder(contenu, {lab_paths.VAR_CONTEXT: "/a/b"}), Path("/a/b"))
        self.assertEqual(lab_paths.context_folder(contenu, {lab_paths.VAR_CONTEXT: ""}), Path("/x/lab/contexte"))
        self.assertEqual(lab_paths.VAR_CONTEXT, "PMZILLA_LAB_CONTEXT")

    def test_septieme_cle_de_resolve(self):
        cles = list(lab_paths.resolve({"PMZILLA_LAB_WORKSPACE": str(self.lab.principal)}, OUTILS / "lab_paths.py"))
        # lab-folder-layout (D1) : la clé du dossier des worktrees est la dernière ; celle du contexte reste la septième.
        self.assertEqual(cles[6], "context_folder")
        self.assertEqual(cles[-1], "worktrees_folder")


class TestAncienNomJamaisEcrit(unittest.TestCase):
    def test_aucun_fichier_de_code_de_tools_n_ecrit_l_ancien_nom(self):
        r = subprocess.run(["git", "-C", str(RACINE), "ls-files", "-z", "--", "tools"], capture_output=True, text=True)
        noms = [p for p in r.stdout.split("\0") if p] or [str(p.relative_to(RACINE)) for p in OUTILS.rglob("*") if p.is_file()]
        trouves = []
        for nom in noms:
            try:
                texte = (RACINE / nom).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            trouves += [f"{nom}:{n}" for n, ligne in enumerate(texte.splitlines(), 1) if re.search(ANCIEN_NOM, ligne)]
        self.assertEqual(trouves, [], "ancien nom du dossier de contexte écrit dans un outil (chemin:ligne)")


if __name__ == "__main__":
    unittest.main()
