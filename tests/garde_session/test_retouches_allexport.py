"""Garde de session, les trois retouches reportées de regle_allexport (bash-sandbox-n2, tâche 19.6, design D13 ; R-20261111-24).

 - `set -o -a` : bash lit `-o` sans nom quand l'argument suivant commence par `-`, puis applique `-a` : c'est allexport, refusé avec une fonction ;
 - une option longue inconnue d'un shell (MOTIF_SHELL_LONGUE_INCONNUE, qui peut prendre une valeur) compte comme un allexport possible ;
 - `ash` est un shell à option `a` comme bash, sh, zsh, dash et ksh.

Comme les formes déjà couvertes (tests/garde_session/test_variables_du_shell.py) : seul, `set -a` reste permis ; le refus (clé `E`) tombe quand une définition de
fonction est aussi dans la commande. La lecture des options est celle de npm_guard.lire_options_shell (source unique, importée, jamais copiée).

    uv run tools/pilot.py freeze --check && bash tests/run_all.sh garde_session
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide import Arbre, g  # noqa: E402


class Retouches(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = Arbre()

    @classmethod
    def tearDownClass(cls):
        cls.a.fermer()

    def refuse(self, commandes):
        for commande in commandes:
            with self.subTest(commande=commande):
                self.assertEqual(self.a.cle(commande, self.a.wt), "E")

    def passe(self, commandes):
        for commande in commandes:
            with self.subTest(commande=commande):
                self.assertIsNone(self.a.cle(commande, self.a.wt))

    def test_set_o_puis_a_avec_une_fonction(self):
        self.refuse(("set -o -a; f(){ :; }", "set -o -a\nfunction f { :; }", "set -o -ea; f(){ :; }", "set -o -ae; f(){ :; }", "set -o -ea\nf ( ) { :; }",
                     "f(){ :; }; set -o -a"))

    def test_set_o_puis_a_sans_fonction_passe(self):
        self.passe(("set -o -a", "set -o -a; FOO=x", "set -o -e", "set -o -x; f(){ :; }", "set -o errexit; f(){ :; }", "set -o allexport_x_inconnu_ok_sans_fonction"))

    def test_une_option_longue_inconnue_compte_comme_un_allexport_possible(self):
        self.refuse(("bash --inconnue -c 'f(){ :; }; ls'", "bash --inconnue=x -c 'f(){ :; }; ls'", "sh --autre -c 'function f { :; }; ls'",
                     "zsh --nouvelle -c 'f(){ :; }; ls'", "bash --inconnue\nf(){ :; }"))

    def test_une_option_longue_connue_reste_permise_avec_une_fonction(self):
        self.passe(("bash --norc -c 'f(){ :; }; ls'", "bash --noprofile --norc -c 'f(){ :; }; ls'", "bash --posix -c 'f(){ :; }; ls'"))

    def test_une_option_longue_inconnue_sans_fonction_passe(self):
        self.passe(("bash --inconnue -c 'ls'", "sh --autre -c 'ls'"))

    def test_ash_est_un_shell_a_option_a(self):
        self.assertIn("ash", g.SHELLS_A_OPTION_A)
        self.refuse(("ash -a -c 'f(){ :; }; ls'", "ash -o allexport -c 'f(){ :; }; ls'", "ash -ac 'function f { :; }; ls'", "/bin/ash -a -c 'f(){ :; }; ls'"))

    def test_ash_sans_allexport_ou_sans_fonction_passe(self):
        self.passe(("ash -c 'f(){ :; }; ls'", "ash -a -c 'ls'", "ash -e -c 'f(){ :; }; ls'"))

    def test_la_lecture_des_options_est_celle_de_la_garde_npm(self):
        """Pas de copie de liste : la garde de session appelle npm_guard.lire_options_shell."""
        source = Path(g.__file__).read_text(encoding="utf-8")
        self.assertIn("npm_guard.lire_options_shell(", source)
        self.assertNotIn("LONGUES_SHELL_SANS_VALEUR = ", source)


if __name__ == "__main__":
    unittest.main()
