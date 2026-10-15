"""Règles `deny` de .claude/settings.json pour le résumé du matin (change morning-summary, R-50, design D11, tâche 4.6).

La session lance `tools/morning_summary.py` dans toutes ses formes, avec et sans options : il ouvre seulement la session de lecture des
cas (comme le crochet de début de séance), lit le dossier de données et n'appelle ni psql, ni docker, ni security, ni gh. Aucune règle
ne doit le viser, et les crochets de début de séance restent au nombre de deux. Aucune commande n'est lancée ; le test ne lit que
.claude/settings.json.
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_settings_deny import Base  # noqa: E402

LANCEURS_PY = ("uv run", "uv run --with pyyaml python", "python3", "python3 -I", "")
CHEMINS = ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
           "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "{s}", "~/PMZilla-Lab/{s}")
OPTIONS = ("", "--json", "--language en", "--language fr --json", "--notify", "--json --language en",
           '--failed-steps "collecte, pré-tri"', "--notify --failed-steps collecte", "--help")
RACINE = Path(__file__).resolve().parents[2]


class ResumeDuMatin(Base):
    def test_aucune_forme_de_lancement_n_est_interdite(self):
        for lanceur, chemin, option in itertools.product(LANCEURS_PY, CHEMINS, OPTIONS):
            commande = f"{lanceur} {chemin.format(s='morning_summary.py')} {option}".replace("  ", " ").strip()
            self.assertFalse(self.interdite(commande), commande)

    def test_avec_la_variable_du_planificateur(self):
        for commande in ("PMZILLA_SUMMARY_NOTIFY=1 uv run tools/morning_summary.py --notify",
                         "PMZILLA_LAB_TODAY=2026-10-14 uv run tools/morning_summary.py --json"):
            self.assertFalse(self.interdite(commande), commande)

    def test_lecture_du_code_de_ses_tests_et_de_ses_messages_autorisee(self):
        for commande in ("cat tools/morning_summary.py", "cat tools/morning_summary_messages.py", "grep -n notify tools/morning_summary.py",
                         "bash tests/run_all.sh morning_summary", "bash tests/run_all.sh --staged",
                         "uv run --with pyyaml python -W ignore -m unittest discover -s tests/morning_summary -q -f"):
            self.assertFalse(self.interdite(commande), commande)

    def test_les_crochets_de_debut_de_seance_restent_deux(self):
        reglages = json.loads((RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))
        debut = reglages.get("hooks", {}).get("SessionStart", [])
        self.assertEqual(sum(len(bloc.get("hooks", [])) for bloc in debut), 2)

    def test_aucun_crochet_ne_nomme_le_resume(self):
        self.assertNotIn("morning_summary", (RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
