"""Règles `deny` de tools/library_parity.py (audit du 2026-10-15, point 8).

L'outil se connecte à la base (psycopg) : l'utilisateur seul le lance, la session ne le lance jamais, quels que soient le lanceur
(`uv run`, `python`, `python3`, avec options), la forme du chemin (relatif, `./`, `~/`, `$HOME/`, absolu, dossier d'exécution
~/PMZilla-Lab/run/tools/…) ou une variable d'environnement devant le lanceur. Même mécanisme que flow_import.py et flow_compare.py
(test_settings_deny.py) et que test_settings_deny_run_worktree.py.

REGLES_PARITE est la liste exacte des règles à ajouter par l'auteur à `permissions.deny` de .claude/settings.json
(`python3 tests/settings_deny/test_settings_deny_library_parity.py --regles` les imprime, une par ligne). Tant qu'elles sont absentes,
les cas contre les vrais réglages ÉCHOUENT (rouge) en nommant les règles manquantes ; la classe ReglesProposees évalue les mêmes cas
sur les règles actuelles complétées de REGLES_PARITE et est toujours verte. Les formes permises sont vérifiées dans les deux cas.
Limites : une règle ne voit pas `cd … && uv run …` ni `bash -c '…'` ; la session n'en écrit jamais. Aucune commande n'est lancée.
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_settings_deny import RACINE  # noqa: E402
from test_settings_deny_run_worktree import Verifications  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"
SCRIPT = "library_parity.py"
LANCEURS = ("uv run", "python", "python3")
DEBUTS_DIRECTS = ("tools/", "./tools/", "~/", "$HOME/", "/")


def _regles():
    """Le nom doit être précédé d'une barre oblique ou d'une espace : un fichier de test « test_…_library_parity.py » reste permis."""
    regles = []
    for lanceur in LANCEURS:
        for forme in (f"*/{SCRIPT}*", f"* {SCRIPT}*", f"{SCRIPT}*"):
            regles += [f"Bash({lanceur} {forme})", f"Bash(*=* {lanceur} {forme})"]
    regles += ["Bash(tools/library_parity.py*)", "Bash(./tools/library_parity.py*)", f"Bash(~/*/{SCRIPT}*)",
               f"Bash($HOME/*/{SCRIPT}*)", f"Bash(/*/{SCRIPT}*)"]
    regles += ["Bash(*=* tools/library_parity.py*)", "Bash(*=* ./tools/library_parity.py*)", f"Bash(*=* ~/*/{SCRIPT}*)",
               f"Bash(*=* $HOME/*/{SCRIPT}*)", f"Bash(*=* /*/{SCRIPT}*)"]
    return regles


REGLES_PARITE = _regles()

CHEMINS = ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
           "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/run/tools/{s}", "$HOME/PMZilla-Lab/run/tools/{s}",
           "/Users/quelquun/PMZilla-Lab/run/tools/{s}", "~/PMZilla-Lab/{s}", "/Users/quelquun/PMZilla-Lab/{s}")
LANCEURS_AVEC_OPTIONS = ("uv run", "uv run -q", "uv run --with psycopg", "uv run --isolated", "python", "python3", "python3 -W ignore",
                         "python3 -I", "uv run --with numpy --with httpx python -W ignore")
SUITES = ("", " record", " record --replace", " --details", " --component hybrid", " --explain 3", " --scan", " --limit 5")
ENVS = ("PMZILLA_LAB_RUN=/tmp/x ", "PGHOST=127.0.0.1 PGPORT=5432 ", "FOO=bar ")
DIRECTS = ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
           "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/run/tools/{s}", "/Users/quelquun/PMZilla-Lab/run/tools/{s}")

PERMISES = (
    "cat tools/library_parity.py", "head -n 40 tools/library_parity.py", "grep -n snapshot tools/library_parity.py",
    "sed -n 1,30p tools/library_parity.py", "wc -l tools/library_parity.py", "cat ~/PMZilla-Lab/run/tools/library_parity.py",
    "git log --oneline -3 -- tools/library_parity.py", "git diff --stat -- tools/library_parity.py", "git blame tools/library_parity.py",
    "bash tests/run_all.sh parity", "bash tests/run_all.sh --staged",
    "python3 -W ignore -m unittest discover -s tests/parity -q",
    "uv run --with numpy --with httpx --with pyyaml python -W ignore -m unittest discover -s tests/parity -q -f",
    "uv run --with pyyaml python -W ignore -m unittest tests.parity.test_parity_main -q",
    "python3 -W ignore -m unittest discover -s tests/settings_deny -p test_settings_deny_library_parity.py -q",
    "uv run --with pyyaml python -W ignore -m unittest discover -s tests/parity -p test_library_parity.py -q",
    "python3 -W ignore -m unittest discover -s tests/settings_deny -p test_settings_deny_library_parity.py -q -f",
    "uv run tools/flow_views.py list", "ls tests/parity", "cat tests/parity/queries.yaml",
)


class Cas(Verifications):
    def formes_interdites(self):
        for lanceur, chemin, suite in itertools.product(LANCEURS_AVEC_OPTIONS, CHEMINS, SUITES):
            c = f"{lanceur} {chemin.format(s=SCRIPT)}{suite}"
            self.assertTrue(self.commande_interdite(c), c)
        for env, lanceur, chemin in itertools.product(ENVS, ("uv run", "python3", "python"), CHEMINS):
            c = f"{env}{lanceur} {chemin.format(s=SCRIPT)} record"
            self.assertTrue(self.commande_interdite(c), c)
        for chemin, suite in itertools.product(DIRECTS, SUITES):
            c = f"{chemin.format(s=SCRIPT)}{suite}"
            self.assertTrue(self.commande_interdite(c), c)
            c = f"PMZILLA_LAB_RUN=/tmp/x {chemin.format(s=SCRIPT)}{suite}"
            self.assertTrue(self.commande_interdite(c), c)

    def formes_permises(self):
        for commande in PERMISES:
            self.assertFalse(self.commande_interdite(commande), commande)


class ReglesProposees(Cas, unittest.TestCase):
    """Cas évalués sur les règles actuelles complétées de REGLES_PARITE : toujours verts."""

    @classmethod
    def setUpClass(cls):
        existantes = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.regles = list(dict.fromkeys(existantes + REGLES_PARITE))

    def test_toutes_les_formes_sont_interdites(self):
        self.formes_interdites()

    def test_les_formes_permises_restent_permises(self):
        self.formes_permises()

    def test_pas_de_regle_en_double(self):
        self.assertEqual(len(REGLES_PARITE), len(set(REGLES_PARITE)))

    def test_aucune_regle_de_lecture(self):
        self.assertEqual([r for r in REGLES_PARITE if not r.startswith("Bash(")], [])


class DansLeFichierDeReglages(Cas, unittest.TestCase):
    """L'auteur ajoute les règles dans .claude/settings.json : rouge tant qu'elles manquent."""

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.regles = cls.deny

    def test_les_regles_sont_dans_settings_json(self):
        manquantes = [r for r in REGLES_PARITE if r not in self.deny]
        self.assertEqual(manquantes, [], f"{len(manquantes)} règle(s) absente(s) de .claude/settings.json")

    def test_toute_forme_est_interdite_par_les_regles_reelles(self):
        self.formes_interdites()

    def test_les_formes_permises_le_sont_avec_les_regles_reelles(self):
        self.formes_permises()


if __name__ == "__main__":
    if "--regles" in sys.argv:
        print("\n".join(REGLES_PARITE))
    else:
        unittest.main()
