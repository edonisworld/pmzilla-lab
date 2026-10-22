"""Garde des tubes (change deny-rules-review, design D6 à D8, D10, D11) : tools/pipe_guard.py signale, sans bloquer, un tube vers
python3, python, grep, egrep, fgrep ou tail dans un appel Bash ; un tail qui suit directement le lanceur de tests est exempté.

    uv run python -W ignore -m unittest discover -s tests/pipe_guard -q
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
OUTIL = RACINE / "tools" / "pipe_guard.py"
sys.path.insert(0, str(RACINE / "tools"))
import pipe_guard  # noqa: E402

MESSAGE = ("garde des tubes : sortie passée à « {noms} » ; utiliser l'outil Read ou Grep, ou lire la sortie telle quelle "
           "(préambule des agents). Signalement seulement : la commande n'a pas été bloquée.")


def lancer(evenement, entree, brut=False):
    """Lance l'outil comme le fait un hook : le JSON sur l'entrée standard."""
    texte = entree if brut else json.dumps(entree)
    args = [sys.executable, str(OUTIL)] + (["--event", evenement] if evenement else [])
    return subprocess.run(args, input=texte, capture_output=True, text=True, timeout=30)


def bash(commande):
    return {"tool_name": "Bash", "tool_input": {"command": commande}}


class Receveurs(unittest.TestCase):
    def cas(self, attendu, *commandes):
        for commande in commandes:
            with self.subTest(commande=commande):
                self.assertEqual(pipe_guard.receveurs(commande), attendu)

    def test_signales(self):
        self.cas(["grep"], "ls tests | grep pilot", "ls|grep x", "ls |& grep x", "FOO=1 ls | FOO=1 grep x",
                 "ls | /usr/bin/grep x")
        self.cas(["egrep"], "ls | egrep x")
        self.cas(["fgrep"], "ls | fgrep x")
        self.cas(["python3"], "cat a | python3 -c 'print(1)'")
        self.cas(["python3.12"], "cat a | python3.12 -c 'print(1)'")
        self.cas(["python"], "cat a | python -c 'print(1)'")
        self.cas(["tail"], "ls | tail -4", "uv run foo | tail -4", "git log | tail -4")

    def test_deux_receveurs_dans_l_ordre(self):
        self.cas(["grep", "tail"], "bash tests/run_all.sh x | grep -v ok | tail -5")
        self.cas(["grep", "python3"], "ls | grep a | python3 -c y")

    def test_noms_distincts(self):
        self.cas(["grep"], "ls | grep a | grep b")

    def test_non_signales(self):
        self.cas([], "git grep x", "a || grep x", 'echo "a | grep"', "echo 'a | tail'", "grep x file", "tail -f log",
                 "ls | sort", "ls | wc -l", "", "ls && grep x f", "ls; grep x f")

    def test_entree_illisible(self):
        self.cas([], "echo 'non ferme | grep x", 'echo "abc | tail')

    def test_exemption_du_tail_apres_le_lanceur(self):
        self.cas([], "bash tests/run_all.sh select_suites 2>&1 | tail -4",
                 "uv run python -W ignore -m unittest discover -s tests/x -q -f 2>&1 | tail -4",
                 "tests/run_all.sh | tail -4", "bash tests/run_all.sh x 2>&1|tail -4",
                 "uv run --with numpy python -W ignore -m unittest discover -s tests/settings_deny -q -f 2>&1 | tail -4",
                 "bash tests/run_all.sh --staged 2>&1 | tail -4")

    def test_l_exemption_ne_couvre_pas_les_autres_programmes(self):
        self.cas(["grep"], "bash tests/run_all.sh x | grep ok")
        self.cas(["python3"], "python -m unittest | python3 -c y")
        self.cas(["python"], "bash tests/run_all.sh x | python -c y")
        self.cas(["grep", "tail"], "bash tests/run_all.sh x | grep -v ok | tail -5")

    def test_tail_apres_un_autre_programme_reste_signale(self):
        self.cas(["tail"], "ls | tail -4", "git log | tail -4", "cat run_all.sh.txt | tail -4")

    def test_le_lanceur_d_une_commande_precedente_n_exempte_pas(self):
        self.cas(["tail"], "bash tests/run_all.sh x && ls | tail -4", "bash tests/run_all.sh x; git log | tail -4")


class Evenements(unittest.TestCase):
    def test_post_signale_exit_2_sur_la_sortie_d_erreur(self):
        r = lancer("post", bash("ls | tail -4"))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stderr.strip(), MESSAGE.format(noms="tail"))
        self.assertEqual(r.stdout, "")

    def test_post_deux_noms(self):
        r = lancer("post", bash("ls | grep a | python3 -c y"))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stderr.strip(), MESSAGE.format(noms="grep, python3"))

    def test_pre_exit_0_et_additional_context(self):
        r = lancer("pre", bash("ls | grep a | python3 -c y"))
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stderr, "")
        sortie = json.loads(r.stdout)
        self.assertEqual(sortie, {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                         "additionalContext": MESSAGE.format(noms="grep, python3")}})

    def test_rien_a_signaler_exit_0_sans_sortie(self):
        for evenement in ("pre", "post"):
            for commande in ("git grep x", "bash tests/run_all.sh x 2>&1 | tail -4"):
                with self.subTest(evenement=evenement, commande=commande):
                    r = lancer(evenement, bash(commande))
                    self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_autre_outil_ignore(self):
        for evenement in ("pre", "post"):
            r = lancer(evenement, {"tool_name": "Read", "tool_input": {"command": "ls | grep x", "file_path": "a"}})
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_entree_non_json_ou_incomplete_ignoree(self):
        for evenement in ("pre", "post"):
            for brut in ("pas du json", "", "[1, 2]", '{"tool_name": "Bash"}', '{"tool_name": "Bash", "tool_input": "x"}',
                         '{"tool_name": "Bash", "tool_input": {"command": 3}}'):
                with self.subTest(evenement=evenement, brut=brut):
                    r = lancer(evenement, brut, brut=True)
                    self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_guillemets_non_fermes_ignores(self):
        r = lancer("post", bash("echo 'abc | grep x"))
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_erreur_d_usage(self):
        for args in ([], ["--event"], ["--event", "autre"]):
            with self.subTest(args=args):
                r = subprocess.run([sys.executable, str(OUTIL)] + args, input=json.dumps(bash("ls | grep x")),
                                   capture_output=True, text=True, timeout=30)
                self.assertEqual(r.returncode, 1)
                self.assertEqual(r.stderr.strip(), "pipe_guard : option --event attendue (pre ou post)")
                self.assertEqual(r.stdout, "")

    def test_le_texte_de_la_commande_n_est_jamais_imprime(self):
        commande = "cat /chemin/secret/fichier.txt | grep MOTIF_SECRET_42"
        for evenement in ("pre", "post"):
            r = lancer(evenement, bash(commande))
            sortie = r.stdout + r.stderr
            for morceau in ("/chemin/secret", "fichier.txt", "MOTIF_SECRET_42", "cat "):
                with self.subTest(evenement=evenement, morceau=morceau):
                    self.assertNotIn(morceau, sortie)


class Texte(unittest.TestCase):
    def test_aucune_decision_de_permission_ni_ecriture_ni_commande(self):
        texte = OUTIL.read_text(encoding="utf-8")
        for interdit in ("permissionDecision", "subprocess", "os.system", "open(", "write_text", "urllib", "socket", "requests"):
            with self.subTest(interdit=interdit):
                self.assertNotIn(interdit, texte)

    def test_bibliotheque_standard_seulement(self):
        imports = {l.split()[1].split(".")[0] for l in OUTIL.read_text(encoding="utf-8").splitlines()
                   if l.startswith(("import ", "from "))}
        self.assertLessEqual(imports, {"json", "os", "re", "shlex", "sys", "__future__"}, imports)


if __name__ == "__main__":
    unittest.main()
