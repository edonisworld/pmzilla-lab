"""Garde de session, niveau 1 (change session-guard-n1, tâche 7.3, design D4 « Effective configuration ») : avant une sous-commande git d'écriture, la garde lit
la configuration effective (`core.hooksPath` à tous les niveaux, `include.path` compris) et vérifie les six liens des crochets du dossier Git commun. Chaque test
crée son propre dépôt jetable et son propre dossier personnel : aucune configuration réelle n'est lue.

    bash tests/run_all.sh garde_session
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide import g  # noqa: E402


class Depot(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="garde-config-"))
        self.home = os.path.join(self.tmp, "home")
        self.repo = os.path.join(self.tmp, "depot")
        os.makedirs(self.home)
        os.makedirs(self.repo)
        self.git("init", "-q", ".")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "--allow-empty", "-m", "initial")
        for nom in g.CROCHETS:
            os.symlink(f"../../tools/hooks/{nom}", os.path.join(self.repo, ".git", "hooks", nom))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, *args, cwd=None):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": self.home, "LC_ALL": "C"}
        subprocess.run(["git", *args], cwd=cwd or self.repo, env=env, check=True, capture_output=True, stdin=subprocess.DEVNULL)

    def contexte(self, **options):
        return g.Contexte(cwd=self.repo, espace=os.path.join(self.tmp, "espace"), run=os.path.join(self.tmp, "run"), home=self.home,
                          compose=os.path.join(self.tmp, "absent.yml"), **options)

    def cle(self, commande, **options):
        v = g.decider(commande, self.contexte(**options))
        return v.cle if v else None

    def lien(self, nom):
        return os.path.join(self.repo, ".git", "hooks", nom)


class ConfigurationEffective(Depot):
    def test_depot_conforme_les_ecritures_passent(self):
        for commande in ("git commit -m x", "git add x", "git rebase main", "git tag v1", "git branch x", "git worktree add ../x"):
            with self.subTest(commande=commande):
                self.assertIsNone(self.cle(commande))

    def test_hookspath_local(self):
        self.git("config", "core.hooksPath", "/ailleurs")
        self.assertEqual(self.cle("git commit -m x"), "A6-hookspath")

    def test_hookspath_global_dans_le_dossier_personnel_de_l_essai(self):
        Path(self.home, ".gitconfig").write_text("[core]\n\thooksPath = /ailleurs\n", encoding="utf-8")
        self.assertEqual(self.cle("git add x"), "A6-hookspath")

    def test_hookspath_par_include_path(self):
        Path(self.home, "autre.conf").write_text("[core]\n\thooksPath = /ailleurs\n", encoding="utf-8")
        Path(self.home, ".gitconfig").write_text(f"[include]\n\tpath = {self.home}/autre.conf\n", encoding="utf-8")
        self.assertEqual(self.cle("git commit -m x"), "A6-hookspath")

    def test_hookspath_par_include_path_du_depot(self):
        Path(self.tmp, "inclus.conf").write_text("[core]\n\thookspath = /ailleurs\n", encoding="utf-8")
        self.git("config", "include.path", os.path.join(self.tmp, "inclus.conf"))
        self.assertEqual(self.cle("git commit -m x"), "A6-hookspath")

    def test_hookspath_vide_ou_absent_passe(self):
        self.assertIsNone(self.cle("git commit -m x"))

    def test_lien_manquant(self):
        os.unlink(self.lien("pre-commit"))
        self.assertEqual(self.cle("git commit -m x"), "A6-liens")

    def test_lien_vers_un_autre_fichier(self):
        os.unlink(self.lien("pre-push"))
        os.symlink("../../tools/hooks/pre-commit", self.lien("pre-push"))
        self.assertEqual(self.cle("git commit -m x"), "A6-liens")

    def test_lien_absolu_ou_fichier_ordinaire(self):
        os.unlink(self.lien("commit-msg"))
        os.symlink(os.path.join(self.repo, "tools", "hooks", "commit-msg"), self.lien("commit-msg"))
        self.assertEqual(self.cle("git commit -m x"), "A6-liens")
        os.unlink(self.lien("commit-msg"))
        Path(self.lien("commit-msg")).write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.assertEqual(self.cle("git commit -m x"), "A6-liens")

    def test_chacun_des_six_liens_est_controle(self):
        for nom in g.CROCHETS:
            with self.subTest(crochet=nom):
                os.unlink(self.lien(nom))
                self.assertEqual(self.cle("git commit -m x"), "A6-liens")
                os.symlink(f"../../tools/hooks/{nom}", self.lien(nom))
                self.assertIsNone(self.cle("git commit -m x"))

    def test_les_lectures_ne_sont_pas_controlees(self):
        self.git("config", "core.hooksPath", "/ailleurs")
        os.unlink(self.lien("pre-commit"))
        for commande in ("git status", "git log --oneline", "git diff", "git show HEAD", "git rev-parse HEAD", "git branch", "git branch --show-current",
                         "git worktree list", "git config --get core.hooksPath", "git fetch"):
            with self.subTest(commande=commande):
                self.assertIsNone(self.cle(commande))

    def test_depuis_un_worktree_le_dossier_commun_est_controle(self):
        self.git("worktree", "add", "-q", os.path.join(self.tmp, "wt"), "-b", "autre")
        wt = os.path.join(self.tmp, "wt")
        v = g.decider("git commit -m x", g.Contexte(cwd=wt, espace=os.path.join(self.tmp, "espace"), run=os.path.join(self.tmp, "run"), home=self.home))
        self.assertIsNone(v)
        os.unlink(self.lien("pre-commit"))
        v = g.decider("git commit -m x", g.Contexte(cwd=wt, espace=os.path.join(self.tmp, "espace"), run=os.path.join(self.tmp, "run"), home=self.home))
        self.assertEqual(v.cle, "A6-liens")

    def test_dossier_qui_n_est_pas_un_depot(self):
        hors = os.path.join(self.tmp, "hors")
        os.makedirs(hors)
        v = g.decider("git commit -m x", g.Contexte(cwd=hors, espace=os.path.join(self.tmp, "espace"), run=os.path.join(self.tmp, "run"), home=self.home))
        self.assertIsNone(v)

    def test_dossier_qui_n_est_pas_un_depot_mais_hookspath_global(self):
        hors = os.path.join(self.tmp, "hors")
        os.makedirs(hors)
        Path(self.home, ".gitconfig").write_text("[core]\n\thooksPath = /ailleurs\n", encoding="utf-8")
        v = g.decider("git commit -m x", g.Contexte(cwd=hors, espace=os.path.join(self.tmp, "espace"), run=os.path.join(self.tmp, "run"), home=self.home))
        self.assertEqual(v.cle, "A6-hookspath")

    def test_dossier_d_une_commande_cd(self):
        self.git("config", "core.hooksPath", "/ailleurs")
        v = g.decider(f"cd {self.repo} && git commit -m x",
                      g.Contexte(cwd=self.tmp, espace=os.path.join(self.tmp, "espace"), run=os.path.join(self.tmp, "run"), home=self.home))
        self.assertEqual(v.cle, "A6-hookspath")

    def test_dossier_d_une_option_C(self):
        self.git("config", "core.hooksPath", "/ailleurs")
        v = g.decider(f"git -C {self.repo} commit -m x",
                      g.Contexte(cwd=self.tmp, espace=os.path.join(self.tmp, "espace"), run=os.path.join(self.tmp, "run"), home=self.home))
        self.assertEqual(v.cle, "A6-hookspath")

    def test_controle_coupe_par_le_contexte(self):
        self.git("config", "core.hooksPath", "/ailleurs")
        self.assertIsNone(self.cle("git commit -m x", controle_configuration=False))


class LectureEnEchec(Depot):
    """Un échec de lecture de la configuration refuse (fermé par défaut), avec un doublon de test pour la lecture de Git."""

    def test_code_inattendu_de_git_config(self):
        v = g.decider("git commit -m x", self.contexte(lecteur_git=lambda args, cwd: (128, "")))
        self.assertEqual(v.cle, "erreur-interne")

    def test_exception_de_la_lecture(self):
        def casse(args, cwd):
            raise OSError("git introuvable")
        v = g.decider("git commit -m x", self.contexte(lecteur_git=casse))
        self.assertEqual(v.cle, "erreur-interne")

    def test_delai_depasse(self):
        def long(args, cwd):
            raise subprocess.TimeoutExpired(args, 5)
        v = g.decider("git commit -m x", self.contexte(lecteur_git=long))
        self.assertEqual(v.cle, "erreur-interne")

    def test_l_environnement_de_la_lecture_est_reduit(self):
        vus = []

        def espion(args, cwd):
            vus.append((tuple(args), cwd))
            return 1, ""
        g.decider("git commit -m x", self.contexte(lecteur_git=espion))
        self.assertEqual(vus[0][0], ("config", "--get-all", "core.hooksPath"))
        source = Path(g.__file__).read_text(encoding="utf-8")
        self.assertIn('env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home, "LC_ALL": "C"}', source)


if __name__ == "__main__":
    unittest.main()
