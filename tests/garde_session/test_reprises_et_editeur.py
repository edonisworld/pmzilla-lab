"""Garde de session, niveau 1 (change session-guard-n1, R-20261108-01, questions 15 a, 16 et 14) : les formes que les fragments deny 26 et 39 refusent et que le
design D4/D6 ne reprenait pas (`--force` hors de push, `git merge` et `git pull`, `git branch -M|-C … main`, le texte nommé), GIT_EDITOR=true devant
`git rebase --continue`, et l'aide du script (classé dans SCRIPTS de tests/script_dependencies, comme train_record).

Remplace : rien (les fragments 26 et 39 restent posés, la matrice de test_matrice_doublons.py compare leurs formes à la garde). Retrait : permanent pour les
refus ; les lignes qui lisent un fragment tombent avec lui, au désherbage du niveau 1.

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
from aide import Arbre, RACINE, g  # noqa: E402


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
                self.assertEqual(self.a.cle(commande, cwd or self.a.wt), cle)

    def passe(self, commandes, cwd=None):
        for commande in commandes:
            with self.subTest(commande=commande):
                self.assertIsNone(self.a.cle(commande, cwd or self.a.wt))


class ForceHorsDePush(Base):
    """A6 : `--force`, option ou texte, dans une commande git autre que push (le fragment 26 le refuse où qu'il figure)."""

    def test_option_force(self):
        self.refuse("A6-force", ("git checkout --force main", "git clean --force", "git reset --hard --force", "git worktree remove --force x",
                                 "git branch --force feat/x main", "git -C /x checkout --force y", "git rebase --force-rebase main",
                                 "/usr/bin/git clean --force", "cd /x && git clean --force", "bash -c 'git clean --force'"))

    def test_texte_force_dans_un_message_ou_une_recherche(self):
        self.refuse("A6-force", ("git commit -m 'sans --force'", "git grep -n x --force", "git log --grep=--force"))

    def test_push_force_reste_un_push(self):
        self.refuse("A1", ("git push --force", "git push --force-with-lease"))

    def test_sans_force_passe(self):
        self.passe(("git checkout main", "git clean -n", "git commit -m 'correctif'", "git worktree remove x"))


class FusionEtPull(Base):
    """A1 : git merge et git pull sous toutes leurs formes ; merge-base reste une lecture."""

    def test_merge_et_pull(self):
        self.refuse("A1-fusion", ("git merge main", "git merge --no-ff feat/x", "git merge --abort", "git merge", "git pull", "git pull --rebase", "git pull origin main",
                                  "/usr/bin/git merge main", "env FOO=1 git merge main", "git status && git merge x", "bash -c 'git merge main'"))

    def test_avec_une_option_globale_ou_un_chemin(self):
        self.refuse("A1-fusion", (f"git -C {self.a.wt} merge main", f"git -C {self.a.espace} merge feat/x", "git -C ~/PMZilla-Lab/workspace merge feat/x",
                                  f"git -C {self.a.espace}/ merge", "git --git-dir=/x/.git merge main", "git --git-dir /x/.git pull",
                                  "git -c core.quotepath=false merge main", "git --no-pager merge main", f"cd {self.a.espace} && git merge feat/x",
                                  f"cd {self.a.wt}; git pull"))

    def test_depuis_l_espace_de_travail_et_depuis_un_worktree(self):
        self.refuse("A1-fusion", ("git merge main", "git pull"), cwd=self.a.espace)
        self.refuse("A1-fusion", ("git merge main", "git pull"), cwd=self.a.run)

    def test_ce_qui_reste_permis(self):
        self.passe(("git merge-base main HEAD", f"git -C {self.a.wt} merge-base a b", "git rebase main", f"git -C {self.a.wt} rebase main", "git fetch",
                    "git log origin/main..main", "echo merge", "grep -n 'git merge' docs/x.md"))


class BrancheForceeSurMain(Base):
    """A6 : `git branch -M|-C … main` (fragment 39), dans l'ordre et l'amas d'options qu'on veut, et le même texte dans un message de commit."""

    def test_formes_nues(self):
        self.refuse("A6-main", ("git branch -M x main", "git branch -M main", "git branch -C x main", "git branch -C main", "git branch -M main x",
                                "git branch x main -M", "git branch main -C", "git branch -m -f x main", "git branch -f -m x main", "git branch -fM x main",
                                "git branch -Mf x main", "git branch -cf x main", "git branch --move --force x main", "git branch --copy --force x main",
                                "git branch -m x main -f", "git branch -c x main --force", "git branch -M x main --", "git branch -M x mainline",
                                "git branch -M x main-copie", "git branch -M x refs/heads/main"))

    def test_avec_options_globales_chemins_et_chaines(self):
        self.refuse("A6-main", (f"git -C {self.a.wt} branch -M x main", f"git -C {self.a.wt} branch -C main", "git -C . branch -C x main", "/usr/bin/git branch -M x main",
                                f"cd {self.a.wt} && git branch -M x main", f"cd {self.a.wt}; git branch -C x main", "git status && git branch -M x main",
                                "git status || git branch -C x main", "git status | git branch -M main", "git status;git branch -C x main",
                                f"git --git-dir={self.a.wt}/.git branch -M main", "git --no-pager branch -C x main", "env FOO=1 git branch -M x main"))

    def test_le_meme_texte_dans_un_message_de_commit(self):
        self.refuse("A6-main", ("git commit -m \"x && git branch -M x main\"", "git commit -m \"x; git branch -C x main\"", "git commit -m \"x | git branch -M main\""))

    def test_ce_qui_reste_permis(self):
        self.passe(("git branch", "git branch -a", "git branch --show-current", "git branch -d x", "git branch -D x", "git branch --list", "git branch -m x y",
                    "git branch -c x y", "git branch -m x main", "git branch -c x main", "git branch -f x main", "git branch -M x feat/main", "git branch -M x domain",
                    "git branch --merged main", "git branch --no-merged main", "git branch x main", "git commit -m 'branche principale main'"))


class TexteDeReglage(Base):
    """A6 : core.hooksPath (toutes casses) ou GIT_CONFIG_ nommés dans une commande, quel que soit le programme (fragment 39) ; la lecture par git config passe."""

    def test_le_texte_nomme_est_refuse(self):
        self.refuse("A6-texte", ("echo hookspath", "echo HOOKSPATH", "grep -n GIT_CONFIG_ docs/x.md", "echo x | grep Hookspath", "git commit -m \"documente core.hooksPath\"",
                                 "git commit -m \"note GIT_CONFIG_COUNT\"", f"git -C {self.a.wt} grep -n hooksPath docs", f"git -C {self.a.wt} log --grep HOOKSPATH",
                                 "cat docs/core.HooksPath.md"))

    def test_git_config_en_lecture_passe_son_ecriture_reste_refusee(self):
        self.passe(("git config --get core.hooksPath", "git config --get-all core.hooksPath", "git config core.hooksPath"))
        self.refuse("A6-config", ("git config core.hooksPath /x", "git config --global core.hookspath /x"))

    def test_les_formes_deja_refusees_gardent_leur_cle(self):
        self.refuse("A6-reglage", ("git -c core.hooksPath=/x commit -m y",))
        self.refuse("A6-variable", ("GIT_CONFIG_COUNT=1 git status",))


class TextePush(Base):
    """A1 : `git -C <chemin> … push` nommé en texte (le fragment 26 refuse `git -C * push*` où que le mot figure)."""

    def test_push_nomme_apres_une_option_C_ou_git_dir(self):
        self.refuse("A1-texte", (f"git -C {self.a.wt} commit -m 'prêt à push'", f"git -C {self.a.wt} log --grep push", "git --git-dir=/x/.git log --grep push"))

    def test_sans_option_C_le_texte_passe(self):
        self.passe(("git commit -m 'prêt à push'", "git grep -n 'git push' docs", f"git -C {self.a.wt} commit -m 'prêt'", f"git -C {self.a.wt} log --oneline"))

    def test_le_vrai_push_reste_a1(self):
        self.refuse("A1", (f"git -C {self.a.wt} push", "git --git-dir=/x/.git push"))


class EditeurPourRebaseContinue(Base):
    """A6-variable : GIT_EDITOR=true passe seulement devant `git rebase --continue` (R-20261107-27, point 12) ; toute autre valeur, toute autre commande et toute
    autre variable GIT_* restent refusées. Remplace : le refus de toute variable GIT_* pour cette seule variable. Retrait : permanent."""

    def test_passage_devant_rebase_continue(self):
        self.passe(("GIT_EDITOR=true git rebase --continue", "env GIT_EDITOR=true git rebase --continue", f"GIT_EDITOR=true git -C {self.a.wt} rebase --continue",
                    "GIT_EDITOR=true /usr/bin/git rebase --continue", "bash -c 'GIT_EDITOR=true git rebase --continue'",
                    "export GIT_EDITOR=true; git rebase --continue", "GIT_EDITOR=true git rebase --continue && git status"))

    def test_refus_de_toute_autre_valeur(self):
        self.refuse("A6-variable", ("GIT_EDITOR=vim git rebase --continue", "GIT_EDITOR=false git rebase --continue", "GIT_EDITOR= git rebase --continue",
                                    "GIT_EDITOR=: git rebase --continue", "GIT_EDITOR=/usr/bin/true git rebase --continue", "GIT_EDITOR=true; GIT_EDITOR=vim git rebase --continue",
                                    "env GIT_EDITOR=vim git rebase --continue", "export GIT_EDITOR=vim; git rebase --continue"))

    def test_refus_de_true_devant_une_autre_commande(self):
        self.refuse("A6-variable", ("GIT_EDITOR=true git commit -m x", "GIT_EDITOR=true git rebase main", "GIT_EDITOR=true git rebase --abort", "GIT_EDITOR=true git status",
                                    "GIT_EDITOR=true ls", "GIT_EDITOR=true bash -c 'git rebase --continue'", "env GIT_EDITOR=true git commit --amend",
                                    "GIT_EDITOR=true echo git rebase --continue", "ls && GIT_EDITOR=true git commit"))

    def test_true_sans_commande_derriere_est_refuse(self):
        self.refuse("A6-variable", ("export GIT_EDITOR=true", "declare -x GIT_EDITOR=true", "GIT_EDITOR=true"))

    def test_les_autres_variables_git_restent_refusees(self):
        self.refuse("A6-variable", ("GIT_EDITOR=true GIT_TRACE=1 git rebase --continue", "GIT_SEQUENCE_EDITOR=true git rebase --continue", "GIT_DIR=/x git rebase --continue"))

    def test_la_valeur_true_ne_se_reporte_pas_sur_la_commande_suivante(self):
        self.passe(("GIT_EDITOR=true git rebase --continue; git log --oneline",))


class FormesEtAide(unittest.TestCase):
    def test_les_formes_reprises_ne_doublonnent_pas_la_table_du_design(self):
        self.assertEqual(set(g.FORMES) & set(g.FORMES_REPRISES), set())

    def test_chaque_forme_reprise_a_sa_classe_et_son_message(self):
        for cle, (classe, forme, voie) in g.FORMES_REPRISES.items():
            with self.subTest(cle=cle):
                v = g.verdict(cle)
                self.assertEqual((v.classe, v.cle, v.forme, v.voie), (classe, cle, forme, voie))
                self.assertEqual(g.message(v), f"garde de session : refusé : {classe} : {forme}. Voie permise : {voie}.")
                self.assertTrue(forme and voie)

    def test_l_aide_ne_lit_pas_l_entree(self):
        r = subprocess.run([sys.executable, "-I", str(RACINE / "tools" / "garde_session.py"), "--help"], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           timeout=60)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertIn("usage", r.stdout.lower())

    def test_l_aide_n_ecrit_aucun_code_compile_dans_le_dossier_de_l_outil(self):
        """R-20261111-13 : `python3 -I` ignore PYTHONDONTWRITEBYTECODE ; l'import du module voisin ne doit pas laisser de __pycache__ dans le dossier
        de l'outil (ici une copie de tools/, créée par le test)."""
        with tempfile.TemporaryDirectory() as tmp:
            copie = Path(tmp) / "tools"
            shutil.copytree(RACINE / "tools", copie, ignore=shutil.ignore_patterns("__pycache__"))
            r = subprocess.run([sys.executable, "-I", str(copie / "garde_session.py"), "--help"], capture_output=True, text=True,
                               stdin=subprocess.DEVNULL, timeout=60, env={k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"})
            self.assertEqual((r.returncode, r.stderr), (0, ""))
            self.assertEqual(sorted(str(p.relative_to(copie)) for p in copie.rglob("__pycache__")), [])

    def test_le_bloc_de_metadonnees_declare_aucune_dependance(self):
        debut = (RACINE / "tools" / "garde_session.py").read_text(encoding="utf-8")[:200]
        self.assertIn('# /// script\n# requires-python = ">=3.11"\n# dependencies = []\n# ///\n', debut)


if __name__ == "__main__":
    unittest.main()
