"""
Résolution partagée des dossiers du lab (R-77, design D1, D2, D5) : tools/lab_paths.py et son jumeau tools/lab_paths.sh.

    bash tests/run_all.sh lab_paths

Chaque cas bâtit un faux lab dans un dossier temporaire (dépôt principal, worktree lié, dossier d'exécution, copie hors Git) et y
copie les deux modules : jamais le vrai lab, ni sa vraie liste de noms. Les deux langages sont comparés sur les mêmes fixtures
(variable posée, variable sur un dossier absent, copie principale, worktree lié, worktree de type dossier d'exécution atteint par un
lien du dossier du lab, dossier hors Git), le shell sous bash et sous zsh. Échec : code 78, deux phrases clés, aucun chemin affiché.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
OUTILS = RACINE / "tools"
sys.path.insert(0, str(OUTILS))
import lab_paths  # noqa: E402

NOMS = ("code_root", "content_root", "lab_folder", "run_tree", "data_folder", "backups_folder")
SHELLS = [s for s in ("bash", "zsh") if shutil.which(s)]
PHRASE_ABSENT_FR = "dossier de contenu introuvable"
PHRASE_VARIABLE_FR = "PMZILLA_LAB_WORKSPACE désigne un dossier absent"


def reel(chemin) -> str:
    return os.path.realpath(str(chemin))


class Lab:
    """Un faux lab : <tmp>/lab/{workspace (principal), wt (worktree lié), run (worktree lié), lien-outils (lien vers run)}, <tmp>/copie."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.home = tmp / "home"
        self.home.mkdir()
        self.lab = tmp / "lab"
        self.lab.mkdir()
        self.env_git = {"GIT_CONFIG_GLOBAL": str(tmp / "gitconfig"), "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_TERMINAL_PROMPT": "0"}
        self.principal = self.lab / "workspace"
        (self.principal / "tools").mkdir(parents=True)
        self.installer(self.principal)
        for cmd in (["init", "-q", "-b", "main"], ["add", "-A"],
                    ["-c", "user.email=t@example.org", "-c", "user.name=t", "commit", "-q", "-m", "init"]):
            self.git(self.principal, *cmd)
        self.lien = self.lab / "run"
        self.git(self.principal, "worktree", "add", "-q", "-b", "run", str(self.lab / "run"))
        self.git(self.principal, "worktree", "add", "-q", "-b", "wt", str(self.lab / "wt"))
        self.copie = tmp / "copie"
        (self.copie / "tools").mkdir(parents=True)
        self.installer(self.copie)

    def installer(self, racine: Path):
        for nom in ("lab_paths.py", "lab_paths.sh"):
            shutil.copy(OUTILS / nom, racine / "tools" / nom)

    def git(self, dossier, *args):
        env = {**os.environ, **self.env_git}
        subprocess.run(["git", "-C", str(dossier), *args], check=True, capture_output=True, env=env)

    def env(self, **extra) -> dict:
        base = {"PATH": os.environ["PATH"], "HOME": str(self.home), "TMPDIR": str(self.tmp), **self.env_git}
        base.update(extra)
        return base

    def python(self, racine: Path, lien=None, **extra):
        script = lien or racine / "tools" / "lab_paths.py"
        return subprocess.run([sys.executable, str(script)], capture_output=True, text=True, env=self.env(**extra), cwd=str(self.tmp))

    def shell(self, interprete: str, racine: Path, lien=None, **extra):
        script = lien or racine / "tools" / "lab_paths.sh"
        commande = f'. "{script}" && lab_paths_print'
        return subprocess.run([interprete, "-c", commande], capture_output=True, text=True, env=self.env(**extra), cwd=str(self.tmp))


def lire(sortie: str) -> dict:
    return dict(ligne.split("=", 1) for ligne in sortie.strip().splitlines())


class TestFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.lab = Lab(Path(cls._tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def cas(self):
        """Les cas communs aux deux langages : nom -> (racine du code, lien éventuel, variables d'environnement)."""
        L = self.lab
        lien_outils = L.lab   # liens de fichier du dossier du lab vers le dossier d'exécution, comme les scripts planifiés
        for nom in ("lab_paths.py", "lab_paths.sh"):
            if not os.path.lexists(lien_outils / nom):
                os.symlink(L.lab / "run" / "tools" / nom, lien_outils / nom)
        dossier_var = L.tmp / "contenu-var"
        dossier_var.mkdir(exist_ok=True)
        return {
            "variable posée": (L.copie, None, {"PMZILLA_LAB_WORKSPACE": str(dossier_var)}),
            "copie principale": (L.principal, None, {}),
            "worktree lié": (L.lab / "wt", None, {}),
            "worktree de type exécution": (L.lab / "run", None, {}),
            "lien du dossier du lab": (L.lab / "run", lien_outils / "lab_paths.py", {}),
        }

    def attendu(self, nom, racine, lien, extra):
        if "PMZILLA_LAB_WORKSPACE" in extra:
            contenu = reel(extra["PMZILLA_LAB_WORKSPACE"])
        else:
            contenu = reel(self.lab.principal)
        return {"code_root": reel(racine), "content_root": contenu, "lab_folder": os.path.dirname(contenu),
                "run_tree": os.path.join(os.path.dirname(contenu), "run"), "data_folder": str(self.lab.home / ".pmzilla-lab")}

    def test_python_cas(self):
        cas = self.cas()
        for nom, (racine, lien, extra) in cas.items():
            with self.subTest(nom):
                r = self.lab.python(racine, lien, **extra)
                self.assertEqual(r.returncode, 0, r.stderr)
                obtenu = {k: (reel(v) if k != "data_folder" else v) for k, v in lire(r.stdout).items()}
                attendu = self.attendu(nom, racine, lien, extra)
                self.assertEqual(obtenu["content_root"], attendu["content_root"])
                self.assertEqual(obtenu["code_root"], attendu["code_root"])
                self.assertEqual(obtenu["lab_folder"], attendu["lab_folder"])
                self.assertEqual(reel(obtenu["run_tree"]), reel(attendu["run_tree"]))

    def test_worktree_lie_donne_la_copie_principale(self):
        r = self.lab.python(self.lab.lab / "wt")
        self.assertEqual(reel(lire(r.stdout)["content_root"]), reel(self.lab.principal))

    def test_parite_avec_le_shell(self):
        for nom, (racine, lien, extra) in self.cas().items():
            lien_sh = None if lien is None else lien.with_name("lab_paths.sh")
            py = self.lab.python(racine, lien, **extra)
            for interprete in SHELLS:
                with self.subTest(f"{nom} / {interprete}"):
                    sh = self.lab.shell(interprete, racine, lien_sh, **extra)
                    self.assertEqual(sh.returncode, 0, sh.stderr)
                    self.assertEqual(lire(sh.stdout), lire(py.stdout))

    def test_lance_directement_le_shell_ecrit_les_dossiers(self):
        py = self.lab.python(self.lab.lab / "wt")
        for interprete in SHELLS:
            with self.subTest(interprete):
                r = subprocess.run([interprete, str(self.lab.lab / "wt" / "tools" / "lab_paths.sh")], capture_output=True, text=True,
                                   env=self.lab.env(), cwd=str(self.lab.tmp))
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(lire(r.stdout), lire(py.stdout))

    def test_variable_dossier_absent(self):
        extra = {"PMZILLA_LAB_WORKSPACE": str(self.lab.tmp / "n-existe-pas")}
        resultats = [("python", self.lab.python(self.lab.principal, **extra))]
        resultats += [(i, self.lab.shell(i, self.lab.principal, **extra)) for i in SHELLS]
        for nom, r in resultats:
            with self.subTest(nom):
                self.assertEqual(r.returncode, 78)
                self.assertIn(PHRASE_VARIABLE_FR, r.stderr)
                self.assertNotIn("n-existe-pas", r.stderr + r.stdout)
                self.assertNotIn(str(self.lab.tmp), r.stderr + r.stdout)
                self.assertEqual(r.stdout, "")

    def test_variable_vide_vaut_non_posee(self):
        r = self.lab.python(self.lab.principal, PMZILLA_LAB_WORKSPACE="")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_dossier_hors_git(self):
        resultats = [("python", self.lab.python(self.lab.copie))]
        resultats += [(i, self.lab.shell(i, self.lab.copie)) for i in SHELLS]
        for nom, r in resultats:
            with self.subTest(nom):
                self.assertEqual(r.returncode, 78)
                self.assertIn(PHRASE_ABSENT_FR, r.stderr)
                self.assertNotIn(str(self.lab.tmp), r.stderr + r.stdout)
                self.assertEqual(r.stdout, "")

    def test_messages_en_anglais(self):
        r = subprocess.run([sys.executable, str(self.lab.copie / "tools" / "lab_paths.py"), "--lang", "en"], capture_output=True,
                           text=True, env=self.lab.env(), cwd=str(self.lab.tmp))
        self.assertEqual(r.returncode, 78)
        self.assertIn("lab paths: content folder not found", r.stderr)
        self.assertIn("PMZILLA_LAB_WORKSPACE", r.stderr)

    def test_aucun_tiret_cadratin_dans_les_messages(self):
        for langue in lab_paths.MESSAGES.values():
            for phrase in langue.values():
                self.assertNotIn("—", phrase)

    def test_le_module_ne_replie_pas_sur_la_racine_du_code(self):
        # copie hors Git, variable absente : jamais la racine du code ni le dossier courant
        r = self.lab.python(self.lab.copie)
        self.assertEqual(r.returncode, 78)
        self.assertNotIn("code_root", r.stdout)

    def test_dossier_d_execution_et_de_donnees_par_variable(self):
        extra = {"PMZILLA_LAB_RUN": str(self.lab.tmp / "ailleurs"), "PMZILLA_LAB_DATA": str(self.lab.tmp / "donnees")}
        py = lire(self.lab.python(self.lab.principal, **extra).stdout)
        self.assertEqual(py["run_tree"], str(self.lab.tmp / "ailleurs"))
        self.assertEqual(py["data_folder"], str(self.lab.tmp / "donnees"))
        for interprete in SHELLS:
            with self.subTest(interprete):
                self.assertEqual(lire(self.lab.shell(interprete, self.lab.principal, **extra).stdout), py)

    def test_dossier_des_sauvegardes_dans_les_deux_modules(self):
        # safe-branch-finish D4, D9 : la variable du script de sauvegarde quand elle est posée et non vide, sinon « sauvegardes » sous le dossier de données
        donnees = str(self.lab.tmp / "donnees")
        ailleurs = str(self.lab.tmp / "sauvegardes-ailleurs")
        par_defaut = str(self.lab.home / ".pmzilla-lab" / "sauvegardes")
        cas = [
            ("défaut", {}, par_defaut),
            ("dossier de données posé", {"PMZILLA_LAB_DATA": donnees}, os.path.join(donnees, "sauvegardes")),
            ("variable du script de sauvegarde", {"DB_BACKUP_SAUVEGARDES": ailleurs}, ailleurs),
            ("la variable l'emporte", {"PMZILLA_LAB_DATA": donnees, "DB_BACKUP_SAUVEGARDES": ailleurs}, ailleurs),
            ("variable vide", {"DB_BACKUP_SAUVEGARDES": ""}, par_defaut),
        ]
        for nom, extra, attendu in cas:
            py = self.lab.python(self.lab.principal, **extra)
            self.assertEqual(py.returncode, 0, py.stderr)
            with self.subTest(f"python / {nom}"):
                self.assertEqual(lire(py.stdout)["backups_folder"], attendu)
            for interprete in SHELLS:
                with self.subTest(f"{interprete} / {nom}"):
                    sh = self.lab.shell(interprete, self.lab.principal, **extra)
                    self.assertEqual(sh.returncode, 0, sh.stderr)
                    self.assertEqual(lire(sh.stdout)["backups_folder"], attendu)
                    self.assertEqual(lire(sh.stdout), lire(py.stdout))

    def test_le_dossier_des_sauvegardes_n_est_pas_cree_ni_liste(self):
        extra = {"DB_BACKUP_SAUVEGARDES": str(self.lab.tmp / "jamais-cree")}
        self.lab.python(self.lab.principal, **extra)
        for interprete in SHELLS:
            self.lab.shell(interprete, self.lab.principal, **extra)
        self.assertFalse((self.lab.tmp / "jamais-cree").exists())


class TestFichiersLocaux(unittest.TestCase):
    """D5 : fichiers locaux lus en place, depuis un worktree qui n'en porte aucune copie ni aucun lien."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.lab = Lab(Path(cls._tmp.name))
        (cls.lab.principal / "Flux-Lab").mkdir()
        (cls.lab.principal / "Flux-Lab" / "noms-sensibles.txt").write_text("valeur-factice\n", encoding="utf-8")
        (cls.lab.principal / ".pmzilla").mkdir()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def chemin_python(self, nom, racine, **extra):
        code = ("import sys; sys.path.insert(0, sys.argv[1]); import lab_paths; "
                "c = lab_paths.resolve_or_exit()['content_root']; print(lab_paths.local_file(sys.argv[2], c))")
        r = subprocess.run([sys.executable, "-c", code, str(racine / "tools"), nom], capture_output=True, text=True,
                           env=self.lab.env(**extra), cwd=str(self.lab.tmp))
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def chemin_shell(self, interprete, nom, racine, **extra):
        commande = f'. "{racine}/tools/lab_paths.sh" && lab_paths_init && lab_paths_local_file {nom}'
        r = subprocess.run([interprete, "-c", commande], capture_output=True, text=True, env=self.lab.env(**extra), cwd=str(self.lab.tmp))
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def test_liste_des_noms_depuis_un_worktree(self):
        wt = self.lab.lab / "wt"
        attendu = os.path.join(reel(self.lab.principal), "Flux-Lab", "noms-sensibles.txt")
        self.assertEqual(self.chemin_python("sensitive_names", wt), attendu)
        for interprete in SHELLS:
            self.assertEqual(self.chemin_shell(interprete, "sensitive_names", wt), attendu)
        # le worktree ne porte ni copie ni lien
        self.assertFalse((wt / "Flux-Lab").exists())
        self.assertFalse(os.path.lexists(wt / "Flux-Lab" / "noms-sensibles.txt"))
        # le fichier du dépôt principal n'a pas été touché
        self.assertEqual((self.lab.principal / "Flux-Lab" / "noms-sensibles.txt").read_text(encoding="utf-8"), "valeur-factice\n")

    def test_regles_bmad_depuis_un_worktree(self):
        wt = self.lab.lab / "wt"
        attendu = os.path.join(reel(self.lab.principal), ".pmzilla", "remplacements-bmad.tsv")
        self.assertEqual(self.chemin_python("bmad_replacements", wt), attendu)
        for interprete in SHELLS:
            self.assertEqual(self.chemin_shell(interprete, "bmad_replacements", wt), attendu)
        self.assertFalse(os.path.lexists(wt / ".pmzilla" / "remplacements-bmad.tsv"))

    def test_auteur_des_cas_au_registre_depuis_un_worktree(self):
        # Décision du 2026-10-21, point 8 (A9) : .pmzilla/cases.yaml (lu par tools/cases_store.py) est au registre des fichiers locaux.
        self.assertEqual(lab_paths.LOCAL_FILES["cases_author"], ((".pmzilla", "cases.yaml"), ()))
        wt = self.lab.lab / "wt"
        attendu = os.path.join(reel(self.lab.principal), ".pmzilla", "cases.yaml")
        self.assertEqual(self.chemin_python("cases_author", wt), attendu)
        for interprete in SHELLS:
            self.assertEqual(self.chemin_shell(interprete, "cases_author", wt), attendu)
        self.assertFalse(os.path.lexists(wt / ".pmzilla" / "cases.yaml"))

    def test_la_variable_l_emporte_et_les_deux_langages_s_accordent(self):
        autre = str(self.lab.tmp / "liste-ailleurs.txt")
        for variable in ("PMZILLA_LAB_SENSITIVE_NAMES", "PMZILLA_NOMS"):
            with self.subTest(variable):
                extra = {variable: autre}
                self.assertEqual(self.chemin_python("sensitive_names", self.lab.lab / "wt", **extra), autre)
                for interprete in SHELLS:
                    self.assertEqual(self.chemin_shell(interprete, "sensitive_names", self.lab.lab / "wt", **extra), autre)

    def test_tous_les_noms_du_registre_s_accordent(self):
        wt = self.lab.lab / "wt"
        for nom in lab_paths.LOCAL_FILES:
            with self.subTest(nom):
                py = self.chemin_python(nom, wt)
                for interprete in SHELLS:
                    self.assertEqual(self.chemin_shell(interprete, nom, wt), py)

    def test_le_module_n_ouvre_pas_le_fichier(self):
        source = (OUTILS / "lab_paths.py").read_text(encoding="utf-8")
        for appel in ("open(", "read_text", "read_bytes", ".exists(", "is_file("):
            self.assertNotIn(appel, source)

    def test_nom_inconnu_du_shell(self):
        commande = f'. "{self.lab.principal}/tools/lab_paths.sh" && lab_paths_init && lab_paths_local_file inconnu'
        for interprete in SHELLS:
            r = subprocess.run([interprete, "-c", commande], capture_output=True, text=True, env=self.lab.env(), cwd=str(self.lab.tmp))
            self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
