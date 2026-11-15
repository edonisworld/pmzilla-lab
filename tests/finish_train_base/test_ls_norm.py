"""
Stabilité du train : la fonction fs_ls_norm de tools/finish_stability.sh, module partagé (change finish-single-b3-b6, D6 ; décision R-20261030-10,
précédent R-20261029-31 : la fonction a quitté tools/finish_train.sh, mêmes entrées, mêmes assertions) (normalisation de « ls -ai » : espaces de tête, « . » et « .. », contrôle de format,
tri en LC_ALL=C). Son texte est extrait du module (de « fs_ls_norm() { » à la « } » suivante) et exécuté par bash -c sur un texte donné ; le script
lui-même n'est pas lancé.
"""
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "finish_stability.sh"


def texte_de_la_fonction() -> str:
    lignes = SCRIPT.read_text(encoding="utf-8").splitlines()
    debut = next((i for i, l in enumerate(lignes) if l.startswith("fs_ls_norm() {")), None)
    if debut is None:
        raise AssertionError("fs_ls_norm introuvable dans tools/finish_stability.sh")
    fin = next(i for i in range(debut + 1, len(lignes)) if lignes[i] == "}")
    return "\n".join(lignes[debut:fin + 1])


def ls_norm(entree: str):
    r = subprocess.run(["bash", "-c", texte_de_la_fonction() + "\nfs_ls_norm"], input=entree, capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout


class LsNorm(unittest.TestCase):
    def test_espaces_de_tete_points_et_tri(self):
        code, sortie = ls_norm("   12 a\n12345 b\n    1 .\n    2 ..\n")
        self.assertEqual((code, sortie), (0, "12 a\n12345 b\n"))

    def test_une_ligne_qui_n_est_pas_inode_espace_nom_rend_1(self):
        code, _ = ls_norm("   12 a\na suite\n")
        self.assertEqual(code, 1)

    def test_entree_vide_sortie_vide(self):
        self.assertEqual(ls_norm(""), (0, ""))
        self.assertEqual(ls_norm("    1 .\n    2 ..\n"), (0, ""))

    def test_un_ajout_a_inode_plus_long_ne_change_pas_les_lignes_des_entrees_anciennes(self):
        # macOS cale les inodes à droite sur la largeur du plus grand : l'ajout élargit toutes les lignes de ls, pas celles de ls_norm
        _, avant = ls_norm("5 a\n6 b\n")
        _, apres = ls_norm("      5 a\n      6 b\n1234567 c\n")
        self.assertEqual(avant, "5 a\n6 b\n")
        self.assertEqual([l for l in apres.splitlines() if l in avant.splitlines()], avant.splitlines())
        self.assertIn("1234567 c", apres.splitlines())


if __name__ == "__main__":
    unittest.main()
