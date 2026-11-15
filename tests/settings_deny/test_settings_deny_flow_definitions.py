"""Règle `deny` de tools/flow_definitions.py (change flow-definitions-loader, design D6, tâche 5.1 ; décision R-20261029-14).

La commande `load` écrit les définitions réelles de flux dans le référentiel du schéma flow : seul l'utilisateur la lance, dans le
Terminal. Source : le refus de session de l'outil (code 3, avant toute lecture). Les trois règles courtes du fragment
.claude/deny/05-flow-import-restauration.txt, une par lanceur (uv run, python, python3) et ancrées sur `tools/`, le doublent pour les
lancements qu'elles couvrent : chaque lanceur, avec ses options, suivi d'un chemin qui contient `tools/flow_definitions.py`. Écart détecté
ici : un lancement couvert qui ne serait plus refusé fait échouer test_chaque_lancement_couvert_est_refuse ; un refus de session retiré de
l'outil fait échouer test_la_source_est_le_refus_de_session. Ancrées sur `tools/`, les règles laissent passer la suite de l'outil
(tests/flow_definitions), le lanceur des suites et la lecture du script (test_ce_que_la_session_garde).
Limites (aucune règle ; le refus de session, code 3, reste la protection) : un lancement depuis le dossier tools/ (`cd tools && …`), le
nom seul du script, un lancement direct sans interpréteur, une ligne de Python.
Remplace : rien. Retrait : tombe avec R-164 (porte unique des données réelles), avec la commande et son refus de session, sauf décision
écrite dans le change de cette porte.

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json, le fragment 05 et le texte de tools/flow_definitions.py.
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_settings_deny import Base, RACINE  # noqa: E402

FRAGMENT = RACINE / ".claude" / "deny" / "05-flow-import-restauration.txt"
OUTIL = RACINE / "tools" / "flow_definitions.py"
REGLES_FLOW_DEFINITIONS = (
    "Bash(uv run *tools/flow_definitions.py*)",
    "Bash(python *tools/flow_definitions.py*)",
    "Bash(python3 *tools/flow_definitions.py*)",
)
SCRIPT = "flow_definitions.py"
LANCEURS = ("uv run", "uv run --isolated", "uv run -q", "uv run python", "uv run python3",
            'uv run --with pyyaml --with "psycopg[binary]" python', "python", "python3", "python3 -I", "python3 -W ignore")
CHEMINS = ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
           "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "/Users/quelquun/PMZilla-Lab/worktrees/wt-x/tools/{s}",
           "~/PMZilla-Lab/run/tools/{s}")
OPTIONS = ("", " load", " load --dry-run", " --help", " load --help")


def regles_attendues() -> list:
    """La liste imprimée par --json, contrôlée par la garde partagée (test_settings_deny_listes_declarees)."""
    return list(REGLES_FLOW_DEFINITIONS)


class DefinitionsDeFlux(Base):
    def test_regles_presentes_une_fois_dans_le_fragment_05(self):
        lignes = FRAGMENT.read_text(encoding="utf-8").split("\n")
        for regle in REGLES_FLOW_DEFINITIONS:
            self.assertEqual(lignes.count(regle), 1, regle)

    def test_regles_presentes_une_fois_dans_les_reglages(self):
        for regle in REGLES_FLOW_DEFINITIONS:
            self.assertEqual(self.deny.count(regle), 1, regle)

    def test_chaque_lancement_couvert_est_refuse(self):
        for lanceur, chemin, option in itertools.product(LANCEURS, CHEMINS, OPTIONS):
            commande = f"{lanceur} {chemin.format(s=SCRIPT)}{option}"
            self.assertTrue(self.interdite(commande), commande)

    def test_la_source_est_le_refus_de_session(self):
        texte = OUTIL.read_text(encoding="utf-8")
        for repere in ("VARIABLE_CLAUDE_CODE", "MESSAGE_SESSION"):
            self.assertIn(repere, texte, f"refus de session absent de tools/flow_definitions.py : {repere}")

    def test_ce_que_la_session_garde(self):
        for commande in ("cat tools/flow_definitions.py", "grep -n TABLES_CYCLES tools/flow_definitions.py",
                         "sed -n 1,40p tools/flow_definitions.py", "git log --oneline -3 -- tools/flow_definitions.py",
                         "bash tests/run_all.sh flow_definitions", "bash tests/run_all.sh --staged",
                         "python3 -W ignore -m unittest discover -s tests/flow_definitions -q -f",
                         'uv run --with pyyaml --with "psycopg[binary]" python -W ignore -m unittest discover -s tests/flow_definitions -q -f 2>&1 | tail -4',
                         "uv run --with pyyaml python -W ignore -m unittest discover -s tests/flow_definitions -p test_flow_definitions.py -q",
                         "python3 -W ignore -m unittest tests/flow_definitions/test_flow_definitions.py",
                         "python3 -W ignore -m unittest discover -s tests/settings_deny -p test_settings_deny_flow_definitions.py -q",
                         "uv run tools/flow_views.py list"):
            self.assertFalse(self.interdite(commande), commande)


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    else:
        unittest.main()
