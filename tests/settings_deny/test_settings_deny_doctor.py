"""Règles `deny` de .claude/settings.json pour le doctor (change doctor-command, design D10, tâche 4.5).

La session lance `tools/doctor.py` dans toutes ses formes (lecture seule, aucune session de base, aucun Trousseau) : aucune règle ne doit
le viser. Ce fichier est VERT. Les cas de l'enveloppeur `tools/doctor.sh` (qui régénère le tableau de bord et ouvre une session de base)
sont dans test_settings_deny_doctor_sh.py, rouge tant que l'auteur n'a pas ajouté ses règles (tâche 4.6).
Aucune commande n'est lancée ; le test ne lit que .claude/settings.json.
"""
import itertools
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_settings_deny import Base  # noqa: E402

LANCEURS_PY = ("uv run", "uv run --with pyyaml python", "python3", "python3 -I", "")
CHEMINS = ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
           "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "{s}")
OPTIONS = ("", "--json", "--quiet", "--language en", "--language fr --quiet", "--record", "--json --language en")


class DoctorPy(Base):
    def test_aucune_forme_de_lancement_n_est_interdite(self):
        for lanceur, chemin, option in itertools.product(LANCEURS_PY, CHEMINS, OPTIONS):
            commande = f"{lanceur} {chemin.format(s='doctor.py')} {option}".replace("  ", " ").strip()
            self.assertFalse(self.interdite(commande), commande)

    def test_lecture_du_code_de_ses_tests_et_de_ses_modeles_autorisee(self):
        for commande in ("cat tools/doctor.py", "cat tools/com.pmzilla.doctor.plist", "cat tools/doctor.sh", "grep -n launchctl tools/doctor.py",
                         "bash tests/run_all.sh doctor", "bash tests/run_all.sh --staged",
                         "uv run --with pyyaml python -W ignore -m unittest discover -s tests/doctor -q -f"):
            self.assertFalse(self.interdite(commande), commande)


if __name__ == "__main__":
    unittest.main()
