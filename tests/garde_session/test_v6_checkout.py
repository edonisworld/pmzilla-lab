"""Garde de session : `git checkout -B` et `git switch -C` refusés (R-20261109-09, 4 a).

Par cohérence avec `git reset --hard`, refusé sous toutes ses formes dans un worktree (R-20261108-06, 2 a) et dans l'espace de travail principal (A3).
Remplace : rien. Retrait : permanent.

    bash tests/run_all.sh garde_session
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_lot7 import Base  # noqa: E402
import garde_session as g  # noqa: E402  (le chemin de tools/ est posé par aide)


class CheckoutBEtSwitchC(Base):
    def test_checkout_B_refuse_dans_un_worktree(self):
        self.refuse("A6-recree", ("git checkout -B x", "git checkout -B x main", "git checkout -Bx", "git checkout -qB x", "git checkout main -B x",
                                  "git -C " + self.a.wt + " checkout -B x"), cwd=self.a.wt)

    def test_switch_C_refuse_dans_un_worktree(self):
        self.refuse("A6-recree", ("git switch -C x", "git switch -C x main", "git switch -Cx", "git switch -qC x", "git -C " + self.a.wt + " switch -C x"),
                    cwd=self.a.wt)

    def test_switch_force_create_refuse_sous_la_cle_de_la_regle_force(self):
        # `--force` figure dans le mot : la règle reprise du fragment 26 (A6-force) passe avant, la forme est refusée quand même.
        self.refuse("A6-force", ("git switch --force-create x", "git switch --force-c x"), cwd=self.a.wt)

    def test_refuse_aussi_dans_l_espace_de_travail_principal(self):
        self.refuse("A6-recree", ("git checkout -B x", "git switch -C x", "git -C " + self.a.wt + " checkout -B x"), cwd=self.a.espace)

    def test_le_message_nomme_la_voie_permise(self):
        texte = g.message(g.verdict("A6-recree"))
        self.assertIn("la session recrée la branche", texte)
        self.assertIn("checkout -B", texte)

    def test_les_formes_voisines_passent(self):
        self.passe(("git checkout -b x", "git checkout -b x main", "git checkout -bBar", "git checkout -qb x", "git switch -c x", "git switch -c x main",
                    "git switch -cCar", "git checkout main", "git switch x", "git checkout -- f", "git checkout main -- f"),
                   cwd=self.a.wt)
        self.passe(("git checkout -b x", "git switch -c x", "git checkout main"), cwd=self.a.espace)

    def test_les_formes_deja_refusees_gardent_leur_cle(self):
        self.refuse("A6-destructif", ("git checkout -fB x", "git switch -f x"), cwd=self.a.wt)
        self.refuse("A6-force", ("git checkout --force", "git switch --force x"), cwd=self.a.wt)


if __name__ == "__main__":
    unittest.main()
