"""Rappel facultatif de tools/npm_guard.py pour la garde de session (change session-guard-n1, tâche 8.2, design D1).

`npm_guard.avec_rappel(commande, rappel)` (et le paramètre `rappel` de `lancer`) passe au rappel chaque commande simple vue par l'analyseur (lanceurs et chaînes
`-c` compris), chaque affectation et les jetons de chaque texte découpé. Sans rappel, le comportement est exactement celui d'avant : les tests de test_npm_guard.py
(la classe Sobriete comprise) restent inchangés.

    bash tests/run_all.sh npm_guard
"""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import npm_guard  # noqa: E402


class Espion:
    def __init__(self):
        self.commandes, self.affectations, self.listes = [], [], []

    def commande(self, mots, env):
        self.commandes.append(list(mots))

    def affectation(self, nom, valeur):
        self.affectations.append((nom, valeur))

    def jetons(self, jetons):
        self.listes.append(list(jetons))


def espionner(commande):
    espion = Espion()
    refus = npm_guard.avec_rappel(commande, espion)
    return espion, refus


class RappelDesCommandes(unittest.TestCase):
    def test_commande_simple(self):
        espion, refus = espionner("git status")
        self.assertEqual(espion.commandes, [["git", "status"]])
        self.assertEqual(refus, [])

    def test_liste_de_commandes_et_tube(self):
        espion, _ = espionner("cd x && git status; ls | wc -l")
        self.assertEqual([c[0] for c in espion.commandes], ["cd", "git", "ls", "wc"])

    def test_lanceurs_la_commande_du_lanceur_puis_la_commande_lancee(self):
        espion, _ = espionner("env FOO=1 nohup git push")
        self.assertEqual([c[0] for c in espion.commandes], ["env", "nohup", "git"])
        self.assertEqual(espion.affectations, [("FOO", "1")])

    def test_chaine_c_et_substitution(self):
        espion, _ = espionner("bash -c 'cd /x && git push' ; echo $(security x)")
        noms = [c[0] for c in espion.commandes]
        for attendu in ("bash", "cd", "git", "echo", "security"):
            self.assertIn(attendu, noms)

    def test_affectations_de_toutes_les_formes(self):
        espion, _ = espionner("A=1 B=2 ls; export C=3; declare -x D=4; env E=5 ls")
        self.assertEqual([n for n, _ in espion.affectations], ["A", "B", "C", "D", "E"])

    def test_jetons_avec_les_redirections(self):
        espion, _ = espionner("echo x > f 2>&1")
        self.assertIn(("redir", ">"), espion.listes[0])
        self.assertIn(("w", "f"), espion.listes[0])

    def test_les_jetons_sont_rendus_pour_chaque_texte_decoupe(self):
        espion, _ = espionner("echo $(ls > a)")
        self.assertEqual(len(espion.listes), 2)

    def test_analyse_en_echec_laisse_ses_motifs(self):
        _, refus = espionner("echo 'abc")
        self.assertTrue(any(m.startswith("commande illisible") for m in refus))
        _, refus = espionner("$(" * 12 + "ls" + ")" * 12)
        self.assertTrue(any(m.startswith("commande trop imbriquée") for m in refus))

    def test_le_rappel_est_retire_apres_l_analyse(self):
        espionner("git status")
        self.assertIsNone(npm_guard._RAPPEL)
        npm_guard.refus_de("git status")
        self.assertIsNone(npm_guard._RAPPEL)

    def test_le_rappel_est_retire_apres_une_exception_du_rappel(self):
        class Casse(Espion):
            def commande(self, mots, env):
                raise ValueError("boum")
        refus = npm_guard.avec_rappel("git status", Casse())
        self.assertIn("analyse impossible", refus)
        self.assertIsNone(npm_guard._RAPPEL)

    def test_lancer_avec_un_rappel_direct(self):
        espion, refus = Espion(), []
        npm_guard.lancer(["git", "status"], {}, 0, refus, False, rappel=espion)
        self.assertEqual(espion.commandes, [["git", "status"]])
        self.assertIsNone(npm_guard._RAPPEL)


class SansRappel(unittest.TestCase):
    """Sans rappel, `avec_rappel` et `refus_de` rendent les mêmes motifs : la décision npm ne change pas."""

    COMMANDES = ("npm install", "npm test", "npx x", "node -e 1", "bash -c 'npm i'", "env npm update", "echo 'abc", "ls && npm ci", "git status",
                 "N=npm; $N install", "xargs npm publish", "find . -exec npm rm x ;")

    def test_memes_motifs_avec_ou_sans_rappel(self):
        for commande in self.COMMANDES:
            with self.subTest(commande=commande):
                self.assertEqual(npm_guard.refus_de(commande), list(dict.fromkeys(npm_guard.avec_rappel(commande, Espion()))))

    def test_le_comportement_par_defaut_n_appelle_aucun_rappel(self):
        self.assertIsNone(npm_guard._RAPPEL)
        self.assertEqual(npm_guard.refus_de("npm install"), ["npm install"])


if __name__ == "__main__":
    unittest.main()
