"""
La commande /context (organisation-context, design D8, tâche 6.3) : .claude/commands/context.md.

    python3 -m unittest discover -s tests/workflow_commands -v

Mêmes contrôles d'en-tête que les autres commandes de travail (aucun lancement interdit, aucun lanceur trop large, aucune écriture sur
GitHub), plus ceux de la commande : seuls `list` et `check` sont pré-approuvés, jamais `add` ni `review` ; le corps ne nomme aucun chemin
des originaux ni des notes ; il exige un oui explicite avant d'écrire.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_workflow_commands import (BASH_NU, CORPS_COMMUNS, INTERDITS_COMMUNS, INTERDITS_EN_TETE_SEULEMENT, INTERDITS_LIVRES,  # noqa: E402
                                    LANCEURS_LARGES, lire, pre_approbations)

PREAPPROUVE = "Bash(uv run tools/context_lab.py list:*), Bash(uv run tools/context_lab.py check:*)"


class CommandeContexte(unittest.TestCase):
    def test_le_fichier_existe_avec_un_en_tete_et_un_corps(self):
        en_tete, corps = lire("context")
        self.assertIn("description:", en_tete)
        self.assertTrue(corps.strip())

    def test_seuls_list_et_check_sont_pre_approuves(self):
        approuve = pre_approbations(lire("context")[0])
        self.assertEqual(approuve, PREAPPROUVE)
        for motif in ("add", "review", "init", "pmzilla_lab_library"):
            self.assertNotRegex(approuve, rf"context_lab\.py {motif}\b" if motif in ("add", "review", "init") else motif)

    def test_aucun_lancement_interdit_ni_lanceur_large_dans_l_en_tete(self):
        approuve = pre_approbations(lire("context")[0])
        for motif in INTERDITS_COMMUNS + INTERDITS_LIVRES + INTERDITS_EN_TETE_SEULEMENT:
            self.assertNotIn(motif, approuve, motif)
        self.assertIsNone(LANCEURS_LARGES.search(approuve))
        self.assertIsNone(BASH_NU.search(approuve))
        for motif in ("gh_issue", r"(^|[\s(/])gh\s", r"roadmap\.py done"):
            self.assertIsNone(re.search(motif, approuve), motif)

    def test_le_corps_nomme_les_actions_interdites(self):
        corps = lire("context")[1]
        for motif in CORPS_COMMUNS + ("--no-verify", "db.py", "--source db", "pmzilla_lab_library"):
            self.assertIn(motif, corps, motif)

    def test_le_corps_ne_nomme_aucun_chemin_des_originaux_ni_des_notes(self):
        corps = lire("context")[1]
        for motif in ("originaux", "contexte/notes", "contexte/originaux", "notes/", "Contexte-Lab"):
            self.assertNotIn(motif, corps, motif)

    def test_ecrite_en_anglais_et_sert_la_langue_de_l_utilisateur(self):
        self.assertIn("THEIR language", lire("context")[1])

    def test_un_oui_explicite_avant_d_ecrire(self):
        corps = lire("context")[1]
        for motif in ("explicit yes", "whole draft", "add"):
            self.assertIn(motif, corps, motif)


if __name__ == "__main__":
    unittest.main()
