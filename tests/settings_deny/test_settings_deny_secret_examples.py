"""Règles `deny` de la liste des exemples déclarés (change pre-commit-secret-scan, design D6, tâche 2.4 ; spec tooling-permission-guards).

La liste `tools/secret_scan_exemples.txt` est écrite par l'auteur seul (`secret_scan.py declare`, refusé dans une session). Les règles ci-dessous
l'enferment : 3 règles `Edit` (aucune `Write(chemin)` ni `NotebookEdit(chemin)`, que Claude Code ignore) et 10 formes d'écriture du terminal.
`REGLES_LISTE_EXEMPLES` (13, dans cet ordre) est imprimée par
`python3 tests/settings_deny/test_settings_deny_secret_examples.py --json` et contrôlée par la garde partagée
(test_settings_deny_listes_declarees.py).

Conception comme test_settings_deny_team_names.py : les cas sur le bloc sont toujours verts ; les cas contre les vrais réglages sont SAUTÉS tant
que l'auteur n'a posé aucune des 13 règles (tâche 5.0), ÉCHOUENT si la pose est partielle et rejouent la matrice quand tout y est.

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json. Noms de fichiers fictifs.

    python3 tests/settings_deny/test_settings_deny_secret_examples.py --json
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import garde_regles  # noqa: E402
from test_settings_deny_rgpd import Moteur  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"
LISTE = "secret_scan_exemples.txt"

REGLES_LISTE_EXEMPLES = [
    "Edit(./tools/secret_scan_exemples.txt)",
    "Edit(//**/tools/secret_scan_exemples.txt)",
    "Edit(~/**/tools/secret_scan_exemples.txt)",
    "Bash(tee *secret_scan_exemples.txt*)",
    "Bash(sed *secret_scan_exemples.txt*)",
    "Bash(cp *secret_scan_exemples.txt*)",
    "Bash(mv *secret_scan_exemples.txt*)",
    "Bash(echo *secret_scan_exemples.txt*)",
    "Bash(printf *secret_scan_exemples.txt*)",
    "Bash(cat *secret_scan_exemples.txt*)",
    "Bash(dd *secret_scan_exemples.txt*)",
    "Bash(truncate *secret_scan_exemples.txt*)",
    "Bash(*>*secret_scan_exemples.txt*)",
]

CHEMINS = ("tools/{f}", "./tools/{f}", "/Users/quelquun/PMZilla-Lab/workspace/tools/{f}", "~/PMZilla-Lab/workspace/tools/{f}",
           "$HOME/PMZilla-Lab/workspace/tools/{f}", "{f}")
FORMES_ECRITURE = (
    "tee {c}", "tee -a {c}", "sed -i '' s/a/b/ {c}", "sed -i s/a/b/ {c}", "cp /dev/null {c}", "cp autre.txt {c}", "mv autre.txt {c}",
    "echo x >> {c}", "echo x > {c}", "printf 'x' > {c}", "cat autre.txt > {c}", "cat {c}", "dd if=/dev/null of={c}", "truncate -s 0 {c}",
    "true >{c}", "ls >> {c}",
)
COMMANDES_PERMISES = (
    "git grep secret_scan_exemples -- docs/", "git log --oneline -3 -- tools/secret_scan_exemples.txt",
    "uv run tools/secret_scan.py --help", "cat tools/secret_scan.py", "head -40 tools/secret_scan.py",
    "bash tests/run_all.sh secret_scan", "bash tests/run_all.sh settings_deny",
    "python3 tests/settings_deny/test_settings_deny_secret_examples.py --json",
    "uv run --with pyyaml python -W ignore -m unittest discover -s tests/secret_scan -q -f",
)


def regles_attendues() -> list:
    """Les 13 règles que l'auteur ajoute à .claude/settings.json (tâche 5.0)."""
    return list(REGLES_LISTE_EXEMPLES)


def commandes_refusees():
    for chemin, forme in itertools.product(CHEMINS, FORMES_ECRITURE):
        yield forme.format(c=chemin.format(f=LISTE))


class BlocListe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_LISTE_EXEMPLES)

    def test_le_bloc_a_treize_regles_sans_doublon(self):
        self.assertEqual(len(REGLES_LISTE_EXEMPLES), 13)
        self.assertEqual(len(set(REGLES_LISTE_EXEMPLES)), 13)
        self.assertEqual(regles_attendues(), REGLES_LISTE_EXEMPLES)

    def test_la_garde_partagee_passe_sur_le_bloc(self):
        self.assertEqual(garde_regles.constats(regles_attendues()), [])
        self.assertTrue(garde_regles.imprime_json(Path(__file__).read_text(encoding="utf-8")))

    def test_trois_edit_et_dix_formes_du_terminal(self):
        self.assertEqual(len([r for r in REGLES_LISTE_EXEMPLES if r.startswith("Edit(")]), 3)
        self.assertEqual(len([r for r in REGLES_LISTE_EXEMPLES if r.startswith("Bash(")]), 10)
        self.assertEqual([r for r in REGLES_LISTE_EXEMPLES if r.startswith(("Write(", "NotebookEdit(", "Read("))], [])

    def test_chaque_forme_d_ecriture_est_refusee(self):
        manquantes = [c for c in commandes_refusees() if not self.moteur.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} forme(s) d'écriture non refusée(s)")

    def test_les_commandes_qui_ne_font_que_citer_restent_permises(self):
        self.assertEqual([c for c in COMMANDES_PERMISES if self.moteur.interdite(c)], [])


class DansLeFichierDeReglages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.moteur = Moteur(cls.deny)

    def exiger_la_pose(self):
        presentes = [r for r in REGLES_LISTE_EXEMPLES if r in self.deny]
        manquantes = [r for r in REGLES_LISTE_EXEMPLES if r not in self.deny]
        if not presentes:
            self.fail("règles de la liste des exemples déclarés pas encore posées par l'auteur (tâche 5.0)")
        if manquantes:
            self.fail(f"{len(manquantes)} règle(s) de la liste des exemples absente(s) de .claude/settings.json : " + " ; ".join(manquantes))

    def test_les_13_regles_sont_dans_les_reglages(self):
        self.exiger_la_pose()

    def test_les_formes_d_ecriture_sont_refusees_avec_les_vrais_reglages(self):
        self.exiger_la_pose()
        manquantes = [c for c in commandes_refusees() if not self.moteur.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} forme(s) d'écriture non refusée(s)")

    def test_les_commandes_permises_le_restent_avec_les_vrais_reglages(self):
        self.exiger_la_pose()
        self.assertEqual([c for c in COMMANDES_PERMISES if self.moteur.interdite(c)], [])

    def test_aucune_regle_write_ni_notebookedit_ne_vise_la_liste(self):
        self.assertEqual([d for d in self.deny if LISTE in d and d.startswith(("Write(", "NotebookEdit("))], [])


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    else:
        unittest.main()
