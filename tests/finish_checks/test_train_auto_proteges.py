"""
Tâche 2.10 (change autonomous-trains-observe, design D13) : le passage du train automatique, la liste prête, leurs catalogues de messages et leurs suites
figurent dans la liste de l'outillage protégé (tools/finish_protected.txt) : ce sont des juges de la fin. Une branche qui les change ne passe jamais
par le passage, elle se termine par la fin unitaire de l'auteur.

    uv run python -m unittest discover -s tests/finish_checks -v
"""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import finish_checks  # noqa: E402

LISTE = "tools/finish_protected.txt"


def motifs():
    return finish_checks.motifs_proteges((RACINE / LISTE).read_text(encoding="utf-8"))


class TrainAutoProtege(unittest.TestCase):
    def test_les_outils_et_leurs_catalogues_sont_couverts(self):
        for chemin in ("tools/train_auto.py", "tools/train_auto_messages.py", "tools/train_ready.py", "tools/train_ready_messages.py"):
            self.assertTrue(finish_checks.couvert(chemin, motifs()), f"{chemin} absent de {LISTE}")

    def test_chaque_fichier_des_deux_suites_est_couvert(self):
        non_couverts = []
        for suite in ("tests/train_auto", "tests/train_ready"):
            dossier = RACINE / suite
            self.assertTrue(dossier.is_dir(), suite)
            for f in sorted(dossier.rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    chemin = str(f.relative_to(RACINE))
                    if not finish_checks.couvert(chemin, motifs()):
                        non_couverts.append(chemin)
        self.assertEqual(non_couverts, [])

    def test_chaque_motif_ajoute_a_sa_raison(self):
        texte = (RACINE / LISTE).read_text(encoding="utf-8")
        bloc = texte[texte.index("# Train automatique, observation"):]
        lignes = bloc.splitlines()
        self.assertTrue(lignes[0].startswith("# Train automatique, observation"))
        premier_motif = next(i for i, l in enumerate(lignes) if l.strip() and not l.startswith("#"))
        self.assertGreater(premier_motif, 0, "au moins une ligne de raison avant les motifs")
        self.assertTrue(all(l.startswith("#") for l in lignes[:premier_motif]))


if __name__ == "__main__":
    unittest.main()
