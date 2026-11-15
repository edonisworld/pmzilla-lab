"""
Liste des chemins du runner et de la preuve (autonomous-trains-merge, design D3, tâche 3.3).

Le fichier tools/finish_runner_paths.txt est la source unique des chemins dont le changement garde une branche seule dans son train (R-20261102-43) et
en fait un train de l'auteur (D2). Ce test garde la liste honnête et la lecture en union :

  - (a) une entrée non couverte par un motif `juge` de tools/finish_protected.txt fait échouer le test, en nommant l'entrée ;
  - la fonction de service runner_proof_paths lit la liste en union à origin/main, à main local et au sommet : une branche ne se desserre pas en retirant
    une entrée ; absente partout, elle lève Impossible (jamais une liste vide qui admettrait) ;
  - runner_proof_touched rend les chemins que le sommet change depuis la base et que la liste couvre.

Le champ runner_proof_touched du JSON de « branch » est ajouté à l'ensemble de clés de test_le_json_porte_les_cles_du_contrat (R-20261106-28 Q1) ; tools/finish_train.sh
le lit à la place de son motif littéral (R-20261106-32).
"""
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
OUTILS = RACINE / "tools"
sys.path.insert(0, str(OUTILS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import finish_checks  # noqa: E402
from aide_depot import AvecDepot  # noqa: E402

LISTE = OUTILS / "finish_runner_paths.txt"
QUATRE_CHEMINS = ["tests/run_all.sh", "ci/passage.sh", "tools/preuve_arbre.py", "tools/finish_train.sh"]


def entrees_non_couvertes_par_un_juge(entrees, texte_protege):
    """Les entrées de la liste qu'aucun motif `juge` du texte de tools/finish_protected.txt ne couvre (D3 (a))."""
    classes = finish_checks.classes_proteges(texte_protege)
    juges = [motif for motif, classe in classes.items() if classe == "juge"]
    return [e for e in entrees if not finish_checks.couvert(e, juges)]


class ListeReelle(unittest.TestCase):
    def test_la_liste_porte_les_quatre_chemins_de_r_20261102_43(self):
        self.assertEqual(finish_checks.motifs_proteges(LISTE.read_text(encoding="utf-8")), QUATRE_CHEMINS)

    def test_chaque_entree_est_couverte_par_un_motif_juge(self):
        entrees = finish_checks.motifs_proteges(LISTE.read_text(encoding="utf-8"))
        protege = (OUTILS / "finish_protected.txt").read_text(encoding="utf-8")
        self.assertEqual(entrees_non_couvertes_par_un_juge(entrees, protege), [])

    def test_la_liste_elle_meme_est_un_fichier_juge(self):
        protege = (OUTILS / "finish_protected.txt").read_text(encoding="utf-8")
        self.assertEqual(entrees_non_couvertes_par_un_juge(["tools/finish_runner_paths.txt"], protege), [])

    def test_chaque_entree_designe_un_fichier_suivi(self):
        for entree in finish_checks.motifs_proteges(LISTE.read_text(encoding="utf-8")):
            self.assertTrue((RACINE / entree).is_file(), entree)


class GardeDeCouverture(unittest.TestCase):
    """Le contrôle (a) échoue bien sur des listes fabriquées, en nommant l'entrée."""

    def test_une_entree_couverte_seulement_par_un_motif_sensible_est_nommee(self):
        protege = "tests/run_all.sh  #[juge]\ntools/outil_x.py  #[sensible]\n"
        self.assertEqual(entrees_non_couvertes_par_un_juge(["tests/run_all.sh", "tools/outil_x.py"], protege), ["tools/outil_x.py"])

    def test_une_entree_sans_motif_est_nommee(self):
        protege = "tests/run_all.sh  #[juge]\n"
        self.assertEqual(entrees_non_couvertes_par_un_juge(["tests/run_all.sh", "ci/passage.sh"], protege), ["ci/passage.sh"])

    def test_un_dossier_juge_couvre_ses_fichiers(self):
        protege = "ci/  #[juge]\n"
        self.assertEqual(entrees_non_couvertes_par_un_juge(["ci/passage.sh"], protege), [])


class LectureEnUnion(AvecDepot):
    OPTIONS = {"liste_db": False, "liste_runner": False}   # la liste du runner n'existe nulle part au départ : poser_liste la crée (R-20261106-32)

    def poser_liste(self, texte="tests/run_all.sh\nci/passage.sh\n"):
        self.depot.commit({"tools/finish_runner_paths.txt": texte}, "liste du runner")
        self.depot.git("push", "-q", "origin", "main")

    def lire(self, tip="HEAD"):
        return finish_checks.runner_proof_paths(self.depot.travail, tip)

    def test_la_liste_est_lue_a_origin_main(self):
        self.poser_liste()
        self.assertEqual(self.lire("refs/heads/main"), ["tests/run_all.sh", "ci/passage.sh"])

    def test_une_branche_ne_retire_pas_une_entree(self):
        self.poser_liste()
        self.depot.branche("feat/x", {"tools/finish_runner_paths.txt": "tests/run_all.sh\n"})
        self.assertEqual(self.lire("refs/heads/feat/x"), ["tests/run_all.sh", "ci/passage.sh"])

    def test_une_entree_ajoutee_par_la_branche_compte(self):
        self.poser_liste()
        self.depot.branche("feat/x", {"tools/finish_runner_paths.txt": "tests/run_all.sh\nci/passage.sh\ntools/autre.py\n"})
        self.assertIn("tools/autre.py", self.lire("refs/heads/feat/x"))

    def test_main_local_en_avance_compte(self):
        self.poser_liste()
        self.depot.commit({"tools/finish_runner_paths.txt": "tests/run_all.sh\nci/passage.sh\ntools/local.py\n"}, "avance locale")
        self.depot.branche("feat/x", {"tools/outil.sh": "x\n"}, depuis="origin/main")
        self.assertIn("tools/local.py", self.lire("refs/heads/feat/x"))

    def test_commentaires_et_lignes_vides_ignores(self):
        self.poser_liste("# commentaire\n\ntests/run_all.sh   # fin de ligne\n  ci/passage.sh  \n")
        self.assertEqual(self.lire("refs/heads/main"), ["tests/run_all.sh", "ci/passage.sh"])

    def test_absente_partout_leve_impossible(self):
        with self.assertRaises(finish_checks.Impossible) as c:
            self.lire("refs/heads/main")
        self.assertIn("illisible", str(c.exception))

    def test_runner_proof_touched_rend_les_chemins_changes_couverts(self):
        self.poser_liste()
        self.depot.branche("feat/x", {"tests/run_all.sh": "autre\n", "tools/outil.sh": "x\n", "ci/passage.sh": "p\n"})
        origine = finish_checks._base_origine(self.depot.travail)
        sommet = finish_checks._commit(self.depot.travail, "refs/heads/feat/x")
        self.assertEqual(finish_checks.runner_proof_touched(self.depot.travail, origine, sommet), ["ci/passage.sh", "tests/run_all.sh"])

    def test_runner_proof_touched_vide_quand_rien_n_est_touche(self):
        self.poser_liste()
        self.depot.branche("feat/x", {"tools/outil.sh": "x\n"})
        origine = finish_checks._base_origine(self.depot.travail)
        sommet = finish_checks._commit(self.depot.travail, "refs/heads/feat/x")
        self.assertEqual(finish_checks.runner_proof_touched(self.depot.travail, origine, sommet), [])

    def test_runner_proof_touched_absente_partout_leve_impossible(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "x\n"})
        origine = finish_checks._base_origine(self.depot.travail)
        sommet = finish_checks._commit(self.depot.travail, "refs/heads/feat/x")
        with self.assertRaises(finish_checks.Impossible):
            finish_checks.runner_proof_touched(self.depot.travail, origine, sommet)


if __name__ == "__main__":
    unittest.main()
