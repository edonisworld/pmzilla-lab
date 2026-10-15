"""Règles `deny` pour l'enveloppeur planifié du doctor, `tools/doctor.sh` (change doctor-command, design D10, tâches 4.5 et 4.6).

L'enveloppeur régénère le tableau de bord, qui ouvre une session de base : la session ne le lance jamais. Ces cas restent ROUGES tant que
l'auteur n'a pas ajouté à .claude/settings.json les règles de REGLES_A_AJOUTER, après les règles des scripts planifiés existants
(tâche 4.6, étape de l'utilisateur) : attendu. Aucune commande n'est lancée ; le test ne lit que .claude/settings.json.
"""
import itertools
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_settings_deny import Base  # noqa: E402

LANCEURS = ("bash", "sh", "zsh", "uv run", "")
CHEMINS = ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
           "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}")

# Les règles à ajouter à permissions.deny, sur le modèle de celles de tools/db_backup.sh.
REGLES_A_AJOUTER = [
    "Bash(bash *tools/doctor.sh*)", "Bash(sh *tools/doctor.sh*)", "Bash(zsh *tools/doctor.sh*)", "Bash(uv run *tools/doctor.sh*)",
    "Bash(tools/doctor.sh*)", "Bash(./tools/doctor.sh*)", "Bash(~/*tools/doctor.sh*)", "Bash($HOME/*tools/doctor.sh*)", "Bash(/*tools/doctor.sh*)",
]


class EnveloppeurDoctor(Base):
    def test_regles_presentes(self):
        self.assertEqual([r for r in REGLES_A_AJOUTER if r not in self.deny], [])

    def test_toute_forme_de_lancement_est_interdite(self):
        for lanceur, chemin in itertools.product(LANCEURS, CHEMINS):
            commande = f"{lanceur} {chemin.format(s='doctor.sh')}".strip()
            self.assertTrue(self.interdite(commande), commande)

    def test_le_doctor_python_reste_lancable(self):
        for commande in ("uv run tools/doctor.py", "uv run tools/doctor.py --json", "python3 tools/doctor.py --quiet"):
            self.assertFalse(self.interdite(commande), commande)


if __name__ == "__main__":
    unittest.main()
