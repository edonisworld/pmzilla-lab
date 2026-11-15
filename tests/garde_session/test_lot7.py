"""Garde de session, niveau 1 (change session-guard-n1) : décision R-20261108-04, points 2 (a) et 3 (a).

Chaque forme refusée a son test de refus et, quand il y en a une, celui de la forme voisine légitime qui passe.

    bash tests/run_all.sh garde_session

Aucun processus. Le contrôle de la configuration effective de Git est coupé (voir la suite sur la configuration effective).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide import Arbre  # noqa: E402


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


class Point2PythonPath(Base):
    """PYTHONPATH rejoint les variables de réglage refusées (classe E), comme une affectation, un export ou un `env`."""

    def test_pythonpath_refuse(self):
        self.refuse("E", ("PYTHONPATH=x git commit -m x", "export PYTHONPATH=/x", "env PYTHONPATH=x git status", "PYTHONPATH=/x python3 y.py",
                          "export PYTHONPATH", "declare -x PYTHONPATH=/x", "env -u PYTHONPATH git status", "unset PYTHONPATH"), cwd=self.a.wt)

    def test_la_forme_voisine_passe(self):
        self.passe(("python3 -I tools/x.py", "export PYTHONUNBUFFERED=1", "PYTHONDONTWRITEBYTECODE=1 python3 y.py", "echo $PYTHONPATH"), cwd=self.a.wt)


class Point3Clean(Base):
    def test_clean_qui_supprime_refuse(self):
        self.refuse("A6-force", ("git clean --force",), cwd=self.a.wt)   # `--force` en toutes lettres garde la clé de la règle reprise du fragment 26
        self.refuse("A6-destructif", ("git clean -f", "git clean -fd", "git clean -fdx", "git clean -fX", "git clean -xdf", "git clean -i",
                                      "git clean", "git clean --for", "git -C " + self.a.wt + " clean -fd"), cwd=self.a.wt)

    def test_clean_en_essai_passe(self):
        self.passe(("git clean -n", "git clean -nd", "git clean -fdn", "git clean --dry-run", "git clean -d --dry-run", "git clean --dr -fd"), cwd=self.a.wt)


class Point3CheckoutEtSwitch(Base):
    def test_checkout_force_refuse(self):
        self.refuse("A6-destructif", ("git checkout -f", "git checkout -f main", "git checkout -fB x", "git checkout main -f", "git checkout --fo main"),
                    cwd=self.a.wt)

    def test_checkout_force_en_toutes_lettres_garde_sa_cle(self):
        self.refuse("A6-force", ("git checkout --force", "git checkout --force main"), cwd=self.a.wt)

    def test_switch_refuse(self):
        self.refuse("A6-destructif", ("git switch --discard-changes x", "git switch -f x", "git switch --discard x"), cwd=self.a.wt)
        self.refuse("A6-force", ("git switch --force x",), cwd=self.a.wt)   # `--force` en toutes lettres garde la clé de la règle reprise du fragment 26

    def test_la_forme_voisine_passe(self):
        self.passe(("git checkout main", "git checkout -b x", "git checkout -- f", "git checkout main -- f", "git switch x", "git switch -c x"),
                   cwd=self.a.wt)


class Point3Reset(Base):
    def test_reset_soft_et_mixed_refuses(self):
        self.refuse("A6-reset", ("git reset --soft", "git reset --soft HEAD~1", "git reset --mixed HEAD~1", "git reset --mixed", "git reset --so HEAD~1",
                                 "git reset --mi HEAD~1", "git -C " + self.a.wt + " reset --soft HEAD~1"), cwd=self.a.wt)
        self.refuse("A6-reset", ("git reset --soft HEAD~1", "git reset --mixed"), cwd=self.a.espace)

    def test_la_forme_voisine_passe(self):
        self.passe(("git reset HEAD f", "git reset -- f"), cwd=self.a.wt)
        self.refuse("A6-reset", ("git reset --hard",), cwd=self.a.wt)   # R-20261108-06 point 2 : `--hard` refusé sous toutes ses formes dans un worktree
        self.refuse("A3", ("git reset --hard",), cwd=self.a.espace)   # --hard garde sa règle : l'arbre de l'espace de travail


class Point3Reflog(Base):
    def test_expire_et_delete_refuses(self):
        self.refuse("A6-reflog", ("git reflog expire --expire=now --all", "git reflog expire", "git reflog delete HEAD@{1}", "git reflog delete --rewrite HEAD@{2}",
                                  "git -C " + self.a.wt + " reflog expire --all"), cwd=self.a.wt)

    def test_lecture_passe(self):
        self.passe(("git reflog", "git reflog show", "git reflog show HEAD", "git reflog -n 5", "git reflog main", "git reflog exists refs/heads/x"), cwd=self.a.wt)


class Point3Output(Base):
    def chemins_proteges(self):
        e = self.a.espace
        return ("tools/hooks/pre-commit", ".claude/settings.json", "tools/garde_session.py", e + "/tools/npm_guard.py", e + "/tools/hooks/commit-msg",
                "../workspace/tools/hooks/pre-push", "~/.claude/settings.json")

    def test_log_et_diff_vers_un_chemin_protege_refuses(self):
        for chemin in self.chemins_proteges():
            for forme in ("git log --output={}", "git diff --output={}", "git log --output {}", "git diff --output {}", "git show --output={}",
                          "git diff --outp={}", "git diff HEAD~1 --output={} -- f"):
                with self.subTest(commande=forme.format(chemin)):
                    self.assertEqual(self.a.cle(forme.format(chemin), self.a.espace), "C")

    def test_chemin_protege_visé_par_c(self):
        self.assertEqual(self.a.cle("git -C " + self.a.espace + " diff --output=tools/hooks/pre-commit", self.a.wt), "C")

    def test_chemin_inconnu_lu_par_sa_fin(self):
        self.refuse("C", ("git log --output=$X/tools/hooks/pre-commit", "git diff --output=$(pwd)/.claude/settings.json"), cwd=self.a.espace)

    def test_la_forme_voisine_passe(self):
        self.passe(("git log --output=notes.txt", "git diff --output=../autre/x.patch", "git diff --output {} -- f".format(self.a.tmp + "/sortie.patch"),
                    "git log --oneline", "git diff --stat", "git log --output-indicator-new=+", "git diff --output-indicator-old=-"), cwd=self.a.espace)
        self.passe(("git diff --output=tools/hooks/pre-commit",), cwd=self.a.wt)   # dans un worktree, ce chemin n'est pas celui de l'espace de travail


class Point3Fetch(Base):
    def test_fetch_qui_ecrit_main_refuse(self):
        self.refuse("A6-fetch", ("git fetch -u . +x:main", "git fetch -u . x:main", "git fetch --update-head-ok . +x:main", "git fetch --update-head-ok . x:main",
                                 "git fetch . +x:refs/heads/main", "git fetch origin +main:main", "git fetch origin main:main", "git fetch origin +refs/heads/*:refs/heads/*",
                                 "git fetch . x:Main", "git fetch . x:heads/main", "git fetch -u . x:refs/heads/main y:z", "git fetch -u . $X:main",
                                 "git fetch . x:$Y", "git -C " + self.a.wt + " fetch -u . +x:main"), cwd=self.a.wt)

    def test_la_forme_voisine_passe(self):
        self.passe(("git fetch", "git fetch origin", "git fetch --all", "git fetch --prune origin", "git fetch origin main", "git fetch origin +x:refs/remotes/origin/x",
                    "git fetch . x:feat/x", "git fetch . x:main-bis", "git fetch . main:autre", "git fetch -u . x:refs/heads/feat/main", "git fetch --depth 1 origin",
                    "git fetch origin +refs/heads/*:refs/remotes/origin/*"), cwd=self.a.wt)


class SuiteA_Reset(Base):
    """Suite de R-20261108-04 (3 a), point A : `git reset <commit>` vaut `--mixed` ; seules passent les formes qui ne déplacent pas HEAD."""

    def test_reset_avec_un_commit_refuse(self):
        self.refuse("A6-reset", ("git reset HEAD~1", "git reset abc1234", "git reset main", "git reset HEAD^", "git reset @", "git reset HEAD~1 -- f",
                                 "git reset abc1234 -- f", "git reset -q HEAD~1", "git reset $X", "git -C " + self.a.wt + " reset HEAD~2"), cwd=self.a.wt)

    def test_soft_abrege_refuse(self):
        self.refuse("A6-reset", ("git reset --s HEAD~1", "git reset --so HEAD~1", "git reset --sof", "git reset --soft=x", "git reset --mi", "git reset --mix"),
                    cwd=self.a.wt)

    def test_reset_sans_deplacement_passe(self):
        self.passe(("git reset", "git reset HEAD", "git reset HEAD -- f", "git reset HEAD -- f g", "git reset -- f", "git reset -- f g", "git reset HEAD f",
                    "git reset -q", "git reset -q -- f", "git reset -p", "git reset --patch -- f"), cwd=self.a.wt)

    def test_hard_garde_son_traitement(self):
        self.refuse("A6-reset", ("git reset --hard", "git reset --hard HEAD", "git reset --har HEAD", "git reset --h", "git reset --hard HEAD~1"), cwd=self.a.wt)   # R-20261108-06, point 2
        self.refuse("A3", ("git reset --hard",), cwd=self.a.espace)

    def test_pythonplatlibdir_refuse(self):
        self.refuse("E", ("PYTHONPLATLIBDIR=x git commit -m x", "export PYTHONPLATLIBDIR=/x", "env PYTHONPLATLIBDIR=x git status", "PYTHONPLATLIBDIR=/x python3 y.py",
                          "unset PYTHONPLATLIBDIR"), cwd=self.a.wt)

    def test_pythonwarnings_refuse(self):
        self.refuse("E", ("PYTHONWARNINGS=x git commit -m x", "export PYTHONWARNINGS=/x", "env PYTHONWARNINGS=x git status", "PYTHONWARNINGS=/x python3 y.py",
                          "unset PYTHONWARNINGS"), cwd=self.a.wt)

    def test_output_a_valeur_illisible_refuse(self):
        self.refuse("C", ("git log --output=$X", "git log --output $X", "git format-patch --outp=$(echo x)", "git archive --output=\"$X\" HEAD", "git show-ref --output=$X/y"),
                    cwd=self.a.wt)


class SuiteF_Variantes(Base):
    """Point F de R-20261108-04 (3 a) : variantes des refus de clean, de reset et de A3 ; puis R-20261108-05, points 1 et 2."""

    def test_clean_apres_end_of_options_refuse(self):
        self.refuse("A6-destructif", ("git clean -f --end-of-options -n", "git clean --end-of-options -n"), cwd=self.a.wt)

    def test_clean_mot_inconnu_refuse(self):
        self.refuse("A6-destructif", ("git clean -n $X", "git clean $X -n", "git clean -n $(echo -f)", "git clean -n -$X", "git clean -n --$X"), cwd=self.a.wt)

    def test_clean_exclude_avec_valeur_nue_refuse(self):
        self.refuse("A6-destructif", ("git clean -n -e $X", "git clean -n --exclude=$X", "git clean -n --exclude $X", "git clean -n -e$X", "git clean -ne $X"),
                    cwd=self.a.wt)

    def test_clean_exclude_avec_valeur_lisible_ou_entre_guillemets_passe(self):
        self.passe(("git clean -n -e x", "git clean -n -e *.log", 'git clean -n -e "$X"', 'git clean -n --exclude="$X"', 'git clean -n --exclude "$X"',
                    'git clean -ne "$X"'), cwd=self.a.wt)

    def test_reset_mot_inconnu_refuse(self):
        self.refuse("A6-reset", ("git reset HEAD $X", "git reset -q $X", "git reset -$X", "git reset $X -- f"), cwd=self.a.wt)

    def test_hard_abrege_refuse_dans_l_espace_de_travail(self):
        self.refuse("A3", ("git reset --har", "git reset --ha", "git reset --har HEAD"), cwd=self.a.espace)

    def test_hard_reconnu_des_h_dans_l_espace_de_travail(self):
        self.refuse("A3", ("git reset --h", "git reset --h HEAD", "git reset --h HEAD~1"), cwd=self.a.espace)

    def test_hard_reconnu_des_h_avec_un_commit_dans_un_worktree(self):
        self.refuse("A6-reset", ("git reset --h HEAD~1", "git reset --h abc1234", "git reset --ha main"), cwd=self.a.wt)

    def test_clean_amas_illisible_avant_e_refuse(self):
        self.refuse("A6-destructif", ("git clean -n -$Xe x", "git clean -n -f$Xe x", "git clean -n -$Xex"), cwd=self.a.wt)

    def test_keep_et_merge_refuses(self):
        self.refuse("A6-reset", ("git reset --keep", "git reset --keep HEAD~1", "git reset --k", "git reset --merge", "git reset --merge HEAD~1", "git reset --me"),
                    cwd=self.a.wt)

    def test_pythonhome_refuse(self):
        self.refuse("E", ("PYTHONHOME=x git commit -m x", "export PYTHONHOME=/x", "env PYTHONHOME=x git status", "PYTHONHOME=/x python3 y.py",
                          "export PYTHONHOME", "declare -x PYTHONHOME=/x", "env -u PYTHONHOME git status", "unset PYTHONHOME"), cwd=self.a.wt)

    def test_pythonuserbase_refuse(self):
        self.refuse("E", ("PYTHONUSERBASE=x git commit -m x", "export PYTHONUSERBASE=/x", "env PYTHONUSERBASE=x git status", "PYTHONUSERBASE=/x python3 y.py",
                          "export PYTHONUSERBASE", "declare -x PYTHONUSERBASE=/x", "env -u PYTHONUSERBASE git status", "unset PYTHONUSERBASE"), cwd=self.a.wt)


class SuiteB_CleanOptions(Base):
    """Point B : l'essai à blanc de `git clean` est lu option par option."""

    def test_clean_sans_essai_effectif_refuse(self):
        self.refuse("A6-destructif", ("git clean -f -e -n", "git clean -fe n", "git clean -fen", "git clean -f -en", "git clean -f --exclude -n",
                                      "git clean -f --exclude=-n", "git clean -f --exclude -n -d", "git clean -n --no-dry-run", "git clean -n --no-d -f",
                                      "git clean --dry-run --no-dry-run -f", "git clean -f -- -n", "git clean -f -n --no-dry-run -d",
                                      "git clean -f --ex -n"), cwd=self.a.wt)

    def test_clean_en_essai_passe(self):
        self.passe(("git clean -n", "git clean -e x -n", "git clean -en x -n", "git clean -nex", "git clean -f --no-dry-run -n", "git clean --no-dry-run --dry-run",
                    "git clean -f -e x --dry-run", "git clean -d -e x --exclude=y -n", "git clean --exclude y -n", "git clean -n -- -e", "git clean --dry-run -f", "git clean -ne x -f"),
                   cwd=self.a.wt)


class SuiteC_Reflog(Base):
    """Point C : seule la lecture passe."""

    def test_sous_commandes_qui_ecrivent_refusees(self):
        self.refuse("A6-reflog", ("git reflog drop", "git reflog drop HEAD@{1}", "git reflog drop --all", "git reflog write", "git reflog write HEAD",
                                  "git reflog expire --all", "git reflog delete HEAD@{1}", "git reflog $X", "git -C " + self.a.wt + " reflog drop"),
                    cwd=self.a.wt)

    def test_lecture_passe(self):
        self.passe(("git reflog", "git reflog show", "git reflog list", "git reflog exists refs/heads/x", "git reflog --all", "git reflog -n 3", "git reflog HEAD",
                    "git reflog show --date=iso", "git reflog main"), cwd=self.a.wt)


class SuiteD_Output(Base):
    """Point D : `--output` vers un chemin protégé est refusé pour toute sous-commande git."""

    def test_autres_sous_commandes_refusees(self):
        for forme in ("git format-patch --output={}", "git archive --output={} HEAD", "git archive --output {} HEAD", "git archive --outp={} HEAD",
                      "git bundle --output={}", "git shortlog --output={}", "git range-diff --output={}", "git stash show --output={}",
                      "git cat-file --output={}", "git diff-tree --output={}", "git diff-files --output={}"):
            with self.subTest(commande=forme):
                self.assertEqual(self.a.cle(forme.format("tools/hooks/pre-commit"), self.a.espace), "C")

    def test_la_forme_voisine_passe(self):
        self.passe(("git show-ref --output=notes.txt", "git for-each-ref --output=../autre/x.txt", "git show-ref --output-directory=out",
                    "git for-each-ref --output=x.txt -- tools/hooks/pre-commit", "git log --output-indicator-new=+"), cwd=self.a.espace)
        self.passe(("git show-ref --output=tools/hooks/pre-commit",), cwd=self.a.wt)


if __name__ == "__main__":
    unittest.main()
