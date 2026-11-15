"""Garde de session, R-20261108-07 : ZDOTDIR, PYTHONPYCACHEPREFIX et PATH modifié devant une commande git sont refusés comme PYTHONPATH.
R-20261108-09 : DEVELOPER_DIR modifié devant une commande git est refusé comme PATH.

Chaque forme refusée a son test de refus et celui de la forme voisine légitime qui passe.

    bash tests/run_all.sh garde_session

Aucun processus. Le contrôle de la configuration effective de Git est coupé (voir la suite sur la configuration effective).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide import Arbre, g  # noqa: E402


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = Arbre()

    @classmethod
    def tearDownClass(cls):
        cls.a.fermer()

    def refuse(self, cle, commandes, cwd=None):
        for commande in commandes:
            with self.subTest(commande=commande):
                self.assertEqual(self.a.cle(commande, cwd), cle)

    def passe(self, commandes, cwd=None):
        for commande in commandes:
            with self.subTest(commande=commande):
                self.assertIsNone(self.a.cle(commande, cwd))


class VariablesDeCrochets(Base):
    def test_zdotdir_refuse(self):
        self.refuse("E", ("ZDOTDIR=x git commit -m x", "export ZDOTDIR=/x", "env ZDOTDIR=x git status", "ZDOTDIR=/x python3 y.py", "export ZDOTDIR",
                          "declare -x ZDOTDIR=/x", "env -u ZDOTDIR git status", "unset ZDOTDIR"), cwd=self.a.wt)

    def test_pythonpycacheprefix_refuse(self):
        self.refuse("E", ("PYTHONPYCACHEPREFIX=x git commit -m x", "export PYTHONPYCACHEPREFIX=/x", "env PYTHONPYCACHEPREFIX=x git status",
                          "PYTHONPYCACHEPREFIX=/x python3 y.py", "export PYTHONPYCACHEPREFIX", "declare -x PYTHONPYCACHEPREFIX=/x",
                          "env -u PYTHONPYCACHEPREFIX git status", "unset PYTHONPYCACHEPREFIX"), cwd=self.a.wt)

    def test_les_formes_voisines_passent(self):
        self.passe(("echo $ZDOTDIR", "echo $PYTHONPYCACHEPREFIX", "export PYTHONUNBUFFERED=1", "git status", "ls"), cwd=self.a.wt)


class PathDevantGit(Base):
    def test_la_cle_de_path_a_son_message(self):
        v = g.verdict("E-path")
        self.assertEqual((v.classe, v.forme, v.voie), ("E", "PATH modifié devant une commande git qui lance des crochets", "la même commande sans changer PATH"))

    def test_le_tableau_path_de_zsh_vaut_path(self):
        self.refuse("E-path", ("path=(/x) git commit -m x", "path=(/x); git commit -m x", "path+=(/x); git commit -m x", "path=/x git commit -m x",
                               "path=(/x $path) && git commit -m x", "read path && git commit -m x", "typeset path && git commit -m x"), cwd=self.a.wt)

    def test_le_tableau_path_devant_une_commande_sans_git_ou_une_lecture_passe(self):
        self.passe(("path=(/x) ls", "path=(/x); git status", "echo $path"), cwd=self.a.wt)

    def test_les_autres_formes_de_modification_de_path_refusent(self):
        self.refuse("E-path", ("PATH=/x command git commit", "PATH=/x exec git commit", "(PATH=/x; git commit)", "for PATH in /x; do git commit; done",
                               "printf -v PATH /x && git commit", "typeset PATH && git commit", "declare -x PATH=/x && git commit",
                               "echo | PATH=/x git commit -F -"), cwd=self.a.wt)

    def test_path_modifie_devant_git_refuse(self):
        self.refuse("E-path", ("PATH=/x:$PATH git commit -m x", "PATH=/x git commit -m x", "env PATH=/x git commit -m x", "env PATH=/x:$PATH git rebase main",
                          "export PATH=/x:$PATH && git commit -m x", "export PATH=/x; git commit -m x", "PATH=/x; git commit -m x",
                          "PATH+=:/x git commit -m x", "read PATH && git commit -m x", "env -i PATH=/x git commit -m x",
                          "PATH=/x bash -c 'git commit -m x'", "PATH=/x git -C " + self.a.wt + " commit -m x", "PATH=/x git fetch",
                          "PATH=/x git"), cwd=self.a.wt)

    def test_path_non_modifie_passe(self):
        self.passe(("git commit -m x", "git status", "git -C " + self.a.wt + " status", "echo $PATH", "export PATH_X=/x && git commit -m x",
                    "export PATHEXT=/x; git status"), cwd=self.a.wt)

    def test_path_modifie_sans_git_passe(self):
        self.passe(("PATH=/x:$PATH ls", "export PATH=/x:$PATH && ls", "env PATH=/x ls", "PATH=/x:$PATH python3 -I tools/x.py"), cwd=self.a.wt)

    def test_path_modifie_devant_une_lecture_de_git_passe(self):
        self.passe(("PATH=/x:$PATH git status", "env PATH=/x git log -1", "export PATH=/x:$PATH && git diff"), cwd=self.a.wt)


class DeveloperDirDevantGit(Base):
    """R-20261108-09 : DEVELOPER_DIR est lu par le relais de /usr/bin/python3 ; il est refusé comme PATH devant une commande git qui lance des crochets."""

    def test_la_cle_de_developer_dir_a_son_message(self):
        v = g.verdict("E-developer-dir")
        self.assertEqual((v.classe, v.forme, v.voie), ("E", "DEVELOPER_DIR modifié devant une commande git qui lance des crochets",
                                                      "la même commande sans changer DEVELOPER_DIR"))

    def test_developer_dir_modifie_devant_git_refuse(self):
        self.refuse("E-developer-dir", ("DEVELOPER_DIR=/x git commit -m x", "env DEVELOPER_DIR=/x git commit -m x", "export DEVELOPER_DIR=/x && git commit -m x",
                                        "export DEVELOPER_DIR=/x; git commit -m x", "DEVELOPER_DIR=/x; git commit -m x", "read DEVELOPER_DIR && git commit -m x",
                                        "(DEVELOPER_DIR=/x; git commit -m x)", "declare -x DEVELOPER_DIR=/x && git commit -m x",
                                        "DEVELOPER_DIR=/x git -C " + self.a.wt + " commit -m x", "DEVELOPER_DIR=/x git fetch"), cwd=self.a.wt)

    def test_developer_dir_non_modifie_passe(self):
        self.passe(("git commit -m x", "echo $DEVELOPER_DIR", "xcode-select -p", "export DEVELOPER_DIR_X=/x && git commit -m x"), cwd=self.a.wt)

    def test_developer_dir_modifie_sans_git_ou_devant_une_lecture_passe(self):
        self.passe(("DEVELOPER_DIR=/x ls", "export DEVELOPER_DIR=/x && ls", "DEVELOPER_DIR=/x git status", "env DEVELOPER_DIR=/x git log -1"), cwd=self.a.wt)

    def test_path_garde_sa_propre_cle(self):
        self.refuse("E-path", ("PATH=/x git commit -m x",), cwd=self.a.wt)


if __name__ == "__main__":
    unittest.main()
