"""Écart entre les règles deny et la garde pour `npm ci` (change npm-ci-session, design D9).

Source et écart : pour `npm ci` nu et `cd <dossier> && npm ci` nu, la garde npm est la seule barrière et la source ; pour toute autre forme de
`npm ci`, les règles deny du bloc déclaré sont la source et la garde un filet. Ce test rejoue la matrice de
tests/settings_deny/test_settings_deny_npm.py : toute commande de `npm ci` que le bloc déclaré refuse est aussi refusée par la garde, dans un
worktree où toutes les conditions tiennent ; un écart fait échouer le test en nommant la commande. Il vérifie aussi que les deux formes
laissées à la garde passent dans ce même worktree et que les formes que l'effet énoncé (D8) laisse sans règle sont refusées par la garde.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/npm_guard -q -f
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "settings_deny"))
from aide_npm_ci import AvecDepot  # noqa: E402
import test_settings_deny_npm as regles_deny  # noqa: E402

FORME = "forme non admise (aucune option, aucun alias, rien avant ni après)"


def est_npm_ci(commande: str) -> bool:
    return "ci" in commande.split()


class EcartRegleGarde(AvecDepot):
    @classmethod
    def setUpClass(cls):
        cls.bloc = regles_deny.Moteur(regles_deny.regles_attendues())

    def test_toute_commande_de_npm_ci_refusee_par_le_bloc_l_est_par_la_garde(self):
        ecarts = []
        total = 0
        for commande in regles_deny.refusees():
            if not est_npm_ci(commande) or not self.bloc.interdite(commande):
                continue
            total += 1
            code, _ = self.lancer(commande)
            if code != 2:
                ecarts.append(commande)
        self.assertGreater(total, 40, "la matrice ne porte presque plus de commande de npm ci")
        self.assertEqual(ecarts, [], f"{len(ecarts)} commande(s) de npm ci que le bloc refuse et que la garde laisse passer, dans un worktree propre")

    def test_les_commandes_de_npm_ci_hors_matrice_du_bloc(self):
        for commande in regles_deny.EFFETS_LAISSES_A_LA_GARDE:
            with self.subTest(commande=commande):
                self.assertFalse(self.bloc.interdite(commande))
                code, erreur = self.lancer(commande)
                self.assertEqual(code, 2)
                self.assertIn(FORME, erreur)

    def test_les_deux_formes_laissees_a_la_garde_passent_dans_un_worktree_propre(self):
        self.assertEqual(self.lancer("npm ci"), (0, ""))
        self.assertEqual(self.lancer("cd mothra && npm ci", cwd=self.wt), (0, ""))
        self.assertEqual(self.lancer(f"cd {self.mothra} && npm ci", cwd=self.depot.repo), (0, ""))

    def test_les_limites_declarees_de_ci_sont_refusees_par_la_garde(self):
        """Les limites des règles (abréviations, alias, camelCase) sont couvertes par la garde, y compris dans un worktree propre."""
        for commande in ("npm cleanInstall", "npm clean-install", "npm ic", "npm install-clean", 'bash -c "npm ci"'):
            with self.subTest(commande=commande):
                code, _ = self.lancer(commande)
                self.assertEqual(code, 2)

    def test_un_ecart_est_nomme(self):
        """Le test sait échouer : une garde qui admettrait `npm ci --offline` serait nommée."""
        from unittest import mock
        import npm_guard
        with mock.patch.object(npm_guard, "_npm_ci", return_value=0):
            code, _ = self.lancer("npm ci --offline")
        self.assertEqual(code, 0)   # avec la garde affaiblie, la commande passe : le test d'écart la verrait


if __name__ == "__main__":
    unittest.main()
