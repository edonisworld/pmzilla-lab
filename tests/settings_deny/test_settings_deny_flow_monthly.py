"""Règles `deny` du suivi mensuel en une commande (change monthly-flow-orchestrator, R-48, design D14).

La session ne lance jamais tools/flow_monthly.py, sous aucune forme : ni l'essai à blanc, ni l'aide, ni une reprise, ni une ligne de
commande qui pose l'une des deux variables d'environnement de test (FLOW_MONTHLY_ROOT, FLOW_MONTHLY_LAUNCHER). Elle peut lire le
script et lancer sa suite de tests (tests/flow_monthly) ou le lanceur de tests. Les règles sont ajoutées à .claude/settings.json par
l'auteur (tâche 5.2) : ces cas restent rouges tant qu'elles n'y sont pas. Aucune commande n'est lancée ; le test ne lit que le fichier
de réglages.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
"""
import itertools
import json
import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]

REGLES = [
    "Bash(uv run *flow_monthly.py*)",
    "Bash(python *flow_monthly.py*)",
    "Bash(python3 *flow_monthly.py*)",
    "Bash(tools/flow_monthly.py*)",
    "Bash(./tools/flow_monthly.py*)",
    "Bash(~/*tools/flow_monthly.py*)",
    "Bash($HOME/*tools/flow_monthly.py*)",
    "Bash(/*tools/flow_monthly.py*)",
    "Bash(*FLOW_MONTHLY_*)",
]

LANCEURS = ("uv run", "uv run --isolated", "uv run python", "uv run python3", "uv run --with pyyaml", "uv run -q",
            "python", "python3", "python3 -I", "python3 -W ignore")
CHEMINS = ("tools/{s}", "./tools/{s}", "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}",
           "$HOME/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/{s}", "/Users/quelquun/PMZilla-Lab/{s}", "{s}")
CHEMINS_EXECUTION_DIRECTE = ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
                             "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}")
OPTIONS = ("", " --dry-run", " --help", " --from import", " --from compare-data --date 2026-10-09", " --force", " --verbose",
           " --language en", " --open", " --dry-run --from dashboard --language en")
SCRIPT = "flow_monthly.py"


def motif_en_regex(motif: str) -> re.Pattern:
    """« Bash(motif) » : le joker * vaut n'importe quelle suite (y compris vide), tout le reste est littéral."""
    return re.compile("".join(".*" if c == "*" else re.escape(c) for c in motif), re.DOTALL)


class SuiviMensuel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reglages = json.loads((RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))
        cls.deny = reglages["permissions"]["deny"]
        cls.motifs = [motif_en_regex(d[len("Bash("):-1]) for d in cls.deny if d.startswith("Bash(")]

    def interdite(self, commande: str) -> bool:
        return any(m.fullmatch(commande) for m in self.motifs)

    def test_les_regles_du_design_sont_dans_le_fichier_de_reglages(self):
        self.assertEqual([r for r in REGLES if r not in self.deny], [])

    def test_chaque_lanceur_chaque_chemin_chaque_option(self):
        for lanceur, chemin, option in itertools.product(LANCEURS, CHEMINS, OPTIONS):
            commande = f"{lanceur} {chemin.format(s=SCRIPT)}{option}"
            self.assertTrue(self.interdite(commande), commande)

    def test_execution_directe_sous_chaque_forme_de_chemin(self):
        for chemin, option in itertools.product(CHEMINS_EXECUTION_DIRECTE, OPTIONS):
            commande = f"{chemin.format(s=SCRIPT)}{option}"
            self.assertTrue(self.interdite(commande), commande)

    def test_variables_d_environnement_de_test_sur_une_ligne_de_commande(self):
        for commande in ("FLOW_MONTHLY_ROOT=/tmp/x uv run tools/flow_monthly.py", "FLOW_MONTHLY_ROOT=/tmp/x python3 -c 'print(1)'",
                         "FLOW_MONTHLY_LAUNCHER=python3 echo bonjour", "export FLOW_MONTHLY_ROOT=/tmp/x",
                         "env FLOW_MONTHLY_ROOT=/tmp/x FLOW_MONTHLY_LAUNCHER=python3 true",
                         "cd /tmp && FLOW_MONTHLY_LAUNCHER=/bin/true uv run --with pyyaml python -m unittest discover -s tests/flow_monthly",
                         "grep -n FLOW_MONTHLY_ROOT tools/flow_monthly.py"):
            self.assertTrue(self.interdite(commande), commande)

    def test_ce_qui_reste_permis_autour_de_l_orchestrateur(self):
        for commande in ("cat tools/flow_monthly.py", "head -40 tools/flow_monthly.py", "cat tools/flow_monthly_messages.py",
                         "grep -n ETAPES tools/flow_monthly.py", "cat tools/flow_monthly.py.lock | head -5",
                         "git log --oneline -3 -- tools/flow_monthly.py", "ls tests/flow_monthly",
                         "python3 -W ignore -m unittest discover -s tests/flow_monthly -q -f",
                         "uv run --with pyyaml python -W ignore -m unittest discover -s tests/flow_monthly -q -f",
                         "uv run --with numpy --with httpx --with pyyaml python -W ignore -m unittest discover -s tests/flow_monthly -q -f 2>&1 | tail -4",
                         "python3 tests/flow_monthly/test_suivi_mensuel.py", "python3 tests/flow_monthly/test_frontiere.py",
                         "bash tests/run_all.sh flow_monthly", "bash tests/run_all.sh --staged", "bash tests/run_all.sh settings_deny",
                         "uv run tools/flow_views.py list"):
            self.assertFalse(self.interdite(commande), commande)


if __name__ == "__main__":
    unittest.main()
