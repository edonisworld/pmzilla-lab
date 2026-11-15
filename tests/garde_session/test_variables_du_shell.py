"""Garde de session, R-20261111-15 et R-20261111-16 : BASH_ENV, ENV, SHELLOPTS, BASHOPTS, PS4, toute variable BASH_FUNC_… et `export -f` sont refusés comme ZDOTDIR.

BASH_ENV et ENV font lire un fichier au premier bash d'une enveloppe figée (hors du bac à sable) avant sa première ligne ; SHELLOPTS, BASHOPTS et PS4 règlent
ce que ce bash exécute ou évalue (PS4 est développée sous `set -x`) ; BASH_FUNC_<nom>%% et `export -f` passent une fonction à la place d'une commande appelée
par son nom. Un test de refus par forme et par nom, et le témoin qu'une variable ordinaire reste permise.

    bash tests/run_all.sh garde_session

Aucun processus. Le contrôle de la configuration effective de Git est coupé (voir la suite sur la configuration effective).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide import Arbre, g  # noqa: E402

NOMS = ("BASH_ENV", "ENV", "SHELLOPTS", "BASHOPTS", "PS4", "BASH_FUNC_cut", "BASH_FUNC_dirname")


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


class BashEtEnv(Base):
    """Les trois formes minimales demandées, pour BASH_ENV et ENV."""

    def test_bash_env_et_env_dans_les_trois_formes(self):
        for nom in ("BASH_ENV", "ENV"):
            self.refuse("E", (f"{nom}=/x bash /y.sh", f"{nom}=/x ls", f"export {nom}=/x", f"env {nom}=/x bash /y.sh"), cwd=self.a.wt)

    def test_la_cle_e_a_son_message(self):
        v = g.verdict("E")
        self.assertEqual((v.classe, v.forme), ("E", "variable de réglage des gardes"))


class AutresNoms(Base):
    def test_chaque_nom_dans_les_formes_de_zdotdir(self):
        for nom in NOMS:
            self.refuse("E", (f"{nom}=x ls", f"{nom}=x git status", f"export {nom}=x", f"env {nom}=x ls", f"export {nom}", f"unset {nom}",
                              f"env -u {nom} ls"), cwd=self.a.wt)

    def test_declare_et_typeset_x(self):
        for nom in NOMS:
            self.refuse("E", (f"declare -x {nom}=x", f"typeset -x {nom}=x", f"declare -x {nom}", f"typeset -x {nom}"), cwd=self.a.wt)

    def test_set_a_suivi_d_une_affectation(self):
        for nom in NOMS:
            self.refuse("E", (f"set -a; {nom}=x", f"set -a && {nom}=x; ls", f"set -a\n{nom}=x"), cwd=self.a.wt)

    def test_toute_variable_bash_func_par_le_prefixe(self):
        self.refuse("E", ("BASH_FUNC_x=y ls", "export BASH_FUNC_zzz=y", "env BASH_FUNC_qq=y ls", "declare -x BASH_FUNC_a=b"), cwd=self.a.wt)

    def test_bash_func_avec_les_signes_pour_cent_de_env(self):
        """La forme réelle d'une fonction exportée : le nom porte `%%`, que l'analyseur ne lit pas comme une affectation."""
        self.refuse("E", ("env 'BASH_FUNC_cut%%=() { echo x; }' ls", "env BASH_FUNC_cut%%=x ls", "env -i 'BASH_FUNC_dirname%%=() { :; }' bash /y.sh"),
                    cwd=self.a.wt)


class ExportF(Base):
    def test_export_f_refuse(self):
        self.refuse("E", ("export -f cut", "f() { :; }; export -f f", "export -nf f", "declare -fx cut", "typeset -fx cut", "declare -x -f cut",
                          "typeset -f -x cut"), cwd=self.a.wt)


class RetouchesR23(Base):
    """R-20261111-23 (revue Opus de fix/suites-portables-macos) : un test par forme qui contournait la garde de l'enveloppe."""

    def test_set_a_suivi_d_une_definition_de_fonction(self):
        self.refuse("E", ("set -a; f(){ :; }", "set -o allexport; f(){ :; }", "set -ea; f(){ :; }", "set -ae; f(){ :; }", "set -a\nfunction f { :; }",
                          "set -a; function f { :; }", "set -a; f ( ) { :; }"), cwd=self.a.wt)

    def test_bash_a_suivi_d_une_definition_de_fonction(self):
        self.refuse("E", ("bash -a -c 'f(){ :; }; ls'", "bash -o allexport -c 'f(){ :; }; ls'", "bash -ac 'function f { :; }; ls'"), cwd=self.a.wt)

    def test_la_chaine_complete_de_la_revue(self):
        self.refuse("E", ("bash -c 'set -a; exec(){ builtin exec \"$@\"; }; cut(){ echo x; }; /bin/bash ~/.pmzilla-lab/outils-figes/gh_issue.sh list'",),
                    cwd=self.a.wt)

    def test_bash_avec_options_longues_ou_a_valeur_avant_a(self):
        """Retouche 1 : une option longue (sans ou avec valeur) ou -O/+O avec sa valeur ne coupe pas la lecture des options du shell."""
        self.refuse("E", ("bash --norc -a -c 'f(){ :; }; ls'", "bash --rcfile /dev/null -a -c 'f(){ :; }; ls'", "bash -O extglob -a -c 'f(){ :; }; ls'",
                          "bash +O extglob -a -c 'f(){ :; }; ls'", "bash --noprofile -a -c 'f(){ :; }; ls'", "bash --norc -o allexport -c 'f(){ :; }; ls'"),
                    cwd=self.a.wt)

    def test_option_en_plus_ne_coupe_pas_la_lecture(self):
        """R-20261111-23 retouche 1 : une option en + (`+x`, `+o posix` avec sa valeur) ne coupe pas la lecture ; `-a` qui suit pose allexport."""
        self.refuse("E", ("bash +x -a -c 'f(){ :; }; ls'", ), cwd=self.a.wt)

    def test_plus_o_consomme_sa_valeur(self):
        self.refuse("E", ("bash +o posix -a -c 'f(){ :; }; ls'", ), cwd=self.a.wt)

    def test_grappe_avec_o_majuscule_consomme_sa_valeur(self):
        """R-20261111-23 retouche 2 : O dans une grappe prend l'argument suivant, comme dans la garde npm."""
        self.refuse("E", ("bash -xO extglob -a -c 'f(){ :; }; ls'", ), cwd=self.a.wt)

    def test_grappe_e_avec_o_majuscule_consomme_sa_valeur(self):
        self.refuse("E", ("bash -eO extglob -a -c 'f(){ :; }; ls'", ), cwd=self.a.wt)

    def test_la_chaine_de_la_revue_precedee_de_noprofile(self):
        self.refuse("E", ("bash --noprofile -c 'set -a; exec(){ :; }; cut(){ :; }; /bin/bash ~/.pmzilla-lab/outils-figes/gh_issue.sh list'",
                          "bash --noprofile -a -c 'exec(){ :; }; cut(){ :; }; /bin/bash ~/.pmzilla-lab/outils-figes/gh_issue.sh list'"), cwd=self.a.wt)

    def test_option_non_resolue_avec_une_fonction(self):
        """Retouche 2 : une option de set ou d'un shell avec expansion non résolue, ou une valeur non résolue de -o, compte comme allexport."""
        # bash -$(…) : refusé par la garde npm (npm_guard.analyser_interprete, « shell : option non résolue », testé dans tests/npm_guard), pas par cette clé
        self.refuse("E", ("set -$(printf a); f(){ :; }", "set -o \"$(echo allexport)\"; f(){ :; }", "set -$(printf a)e; f(){ :; }"), cwd=self.a.wt)

    def test_temoins_options_du_shell(self):
        self.passe(("bash --norc -c 'echo x'", "bash --norc -c 'f(){ :; }; f'", "bash --rcfile /dev/null -O extglob -c 'echo x'",
                    "set -e; f(){ :; }", "set -$(printf e)", "set -$(printf e); echo x"), cwd=self.a.wt)

    def test_declare_et_typeset_avec_f_majuscule_et_x(self):
        self.refuse("E", ("declare -Fx cut", "typeset -Fx cut", "declare -xF cut", "declare -F -x cut", "typeset -x -F cut"), cwd=self.a.wt)

    def test_env_avec_bash_func_dans_n_importe_quel_argument(self):
        self.refuse("E", ("env -S'BASH_FUNC_x%%=() { :; }' ls", "env -i FOO=1 'xBASH_FUNC_cut%%=() { :; }' ls", "env ls 'BASH_FUNC_cut%%=x'"),
                    cwd=self.a.wt)

    def test_un_nom_de_commande_qui_commence_par_bash_func(self):
        self.refuse("E", ("'BASH_FUNC_cut%%' ls", "BASH_FUNC_cut ls"), cwd=self.a.wt)

    def test_fige_relance_est_une_variable_de_reglage(self):
        self.refuse("E", ("FIGE_RELANCE=1 ls", "export FIGE_RELANCE=1", "env FIGE_RELANCE=1 ls", "FIGE_RELANCE=$$ bash /y.sh"), cwd=self.a.wt)

    def test_temoins_permis(self):
        self.passe(("set -a; FOO=x", "declare -F", "declare -F cut", "typeset -F", "env FOO=x ls", "env -i PATH=/usr/bin ls", "f(){ :; }; f",
                    "set -e; f(){ :; }", "bash -c 'f(){ :; }; f'", "set -a; arr=(a b); echo $arr"), cwd=self.a.wt)


class Temoins(Base):
    def test_une_variable_ordinaire_reste_permise(self):
        self.passe(("FOO=x ls", "export FOO=1", "env FOO=x ls", "declare -x FOO=1", "typeset -x FOO=1", "set -a; FOO=x", "export ENVIRONNEMENT=1",
                    "export BASH_VERSION_X=1", "export BASHOPTSX=1", "export PS44=1", "export MY_BASH_ENV=1", "echo $BASH_ENV $ENV $PS4"), cwd=self.a.wt)

    def test_les_formes_voisines_de_export_et_declare_passent(self):
        self.passe(("export -p", "export -n FOO", "declare -f", "declare -p", "typeset -f cut", "declare -F", "set -e", "set -x"), cwd=self.a.wt)


if __name__ == "__main__":
    unittest.main()
