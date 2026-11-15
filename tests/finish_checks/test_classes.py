"""
finish-single-b3-b6, B4 (design D9) : `protected_classes` et la sortie de « branch » par classe. Un motif sans étiquette compte `juge` ; un motif étiqueté
différemment selon la révision (origin/main, main local, sommet) compte `juge` ; le JSON de format 1 gagne `protected_judges` et `protected_sensitive`
(`protected_touched` reste, leur union) ; le texte donne les lignes « outillage de fin touché » et « outil sensible touché », chacune suivie de ses chemins.
Vrais dépôts jetables (tests/finish_checks/aide_depot.py), vrai module de contrôles.
"""
import sys
import unittest
from pathlib import Path

from aide_depot import AvecDepot, OUTILS

sys.path.insert(0, str(OUTILS))
import finish_checks  # noqa: E402

LISTE = ("# liste fictive classée\ntools/hooks/  #[juge]\ntools/finish_branch.sh  #[juge]\ntools/finish_protected.txt  #[juge]\ntests/run_all.sh  #[juge]\n"
         "tools/mapping_lab.py  #[sensible] vues de la base\ntools/context_lab.py  #[sensible] base\n")


class AvecListeClassee(AvecDepot):
    def setUp(self):
        super().setUp()
        self.poser(LISTE)

    def poser(self, texte, pousser=True):
        self.depot.commit({"tools/finish_protected.txt": texte}, "liste classée")
        if pousser:
            self.depot.git("push", "-q", "origin", "main")


class ProtectedClasses(AvecListeClassee):
    def classes(self, rev="main"):
        return finish_checks.protected_classes(self.depot.travail, rev)

    def test_les_deux_classes_sont_lues_a_la_revision(self):
        c = self.classes()
        self.assertEqual((c["tools/hooks/"], c["tools/mapping_lab.py"], c["tools/context_lab.py"]), ("juge", "sensible", "sensible"))

    def test_un_motif_sans_etiquette_compte_juge(self):
        self.poser(LISTE + "tools/sans_etiquette.py\ntools/raison_libre.py # raison sans étiquette\n")
        c = self.classes()
        self.assertEqual((c["tools/sans_etiquette.py"], c["tools/raison_libre.py"]), ("juge", "juge"))

    def test_un_motif_etiquete_differemment_d_une_revision_a_l_autre_compte_juge(self):
        # origin/main : sensible ; le sommet de la branche l'étiquette juge -> juge ; et l'inverse (la branche l'étiquette sensible) -> juge aussi
        self.depot.branche("feat/x", {"tools/finish_protected.txt": LISTE.replace("tools/mapping_lab.py  #[sensible]", "tools/mapping_lab.py  #[juge]")})
        self.assertEqual(self.classes("feat/x")["tools/mapping_lab.py"], "juge")
        self.depot.branche("feat/y", {"tools/finish_protected.txt": LISTE.replace("tools/hooks/  #[juge]", "tools/hooks/  #[sensible]")})
        self.assertEqual(self.classes("feat/y")["tools/hooks/"], "juge")

    def test_un_motif_ajoute_par_la_branche_entre_avec_son_etiquette(self):
        self.depot.branche("feat/x", {"tools/finish_protected.txt": LISTE + "docs/\n"})
        self.assertEqual(self.classes("feat/x")["docs/"], "juge")
        self.depot.branche("feat/y", {"tools/finish_protected.txt": LISTE + "docs/  #[sensible]\n"})
        self.assertEqual(self.classes("feat/y")["docs/"], "sensible")

    def test_un_motif_retire_par_la_branche_reste_dans_la_classe_d_origin_main(self):
        self.depot.branche("feat/x", {"tools/finish_protected.txt": LISTE.replace("tools/mapping_lab.py  #[sensible] vues de la base\n", "")})
        self.assertEqual(self.classes("feat/x")["tools/mapping_lab.py"], "sensible")

    def test_liste_illisible_partout_est_un_calcul_impossible(self):
        self.depot.commit({"tools/finish_protected.txt": None}, "sans liste")
        self.depot.git("push", "-q", "origin", "main")
        with self.assertRaises(finish_checks.Impossible):
            finish_checks.protected_classes(self.depot.travail, "main")


class SortieParClasse(AvecListeClassee):
    def test_json_un_fichier_juge_seul(self):
        self.depot.branche("feat/x", {"tools/hooks/pre-commit": "x\n", "tools/outil.sh": "y\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual((r["protected_judges"], r["protected_sensitive"], r["protected_touched"]),
                         (["tools/hooks/pre-commit"], [], ["tools/hooks/pre-commit"]))

    def test_json_un_fichier_sensible_seul(self):
        self.depot.branche("feat/x", {"tools/mapping_lab.py": "v\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual((r["protected_judges"], r["protected_sensitive"], r["protected_touched"]),
                         ([], ["tools/mapping_lab.py"], ["tools/mapping_lab.py"]))

    def test_json_les_deux_classes_triees_et_leur_union(self):
        self.depot.branche("feat/x", {"tools/context_lab.py": "d\n", "tools/mapping_lab.py": "v\n", "tests/run_all.sh": "r2\n", "tools/hooks/pre-commit": "h\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(r["protected_judges"], ["tests/run_all.sh", "tools/hooks/pre-commit"])
        self.assertEqual(r["protected_sensitive"], ["tools/context_lab.py", "tools/mapping_lab.py"])
        self.assertEqual(r["protected_touched"], sorted(r["protected_judges"] + r["protected_sensitive"]))

    def test_un_fichier_couvert_par_un_motif_juge_et_un_motif_sensible_est_juge(self):
        self.poser(LISTE + "tools/*.py  #[sensible] tout le reste\n")
        self.depot.branche("feat/x", {"tools/mapping_lab.py": "v\n", "tools/autre.py": "a\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(r["protected_judges"], [])
        self.assertEqual(r["protected_sensitive"], ["tools/autre.py", "tools/mapping_lab.py"])
        self.poser(LISTE + "tools/*.py  #[sensible] tout le reste\ntools/mapping_lab.py  #[juge] aussi\n")
        self.depot.branche("feat/y", {"tools/mapping_lab.py": "v\n", "tools/autre.py": "a\n"})
        _, r = self.depot.json_branche("feat/y")
        self.assertEqual(r["protected_judges"], ["tools/mapping_lab.py"])
        self.assertEqual(r["protected_sensitive"], ["tools/autre.py"])

    def test_json_aucun_fichier_protege(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "y\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual((r["protected_judges"], r["protected_sensitive"], r["protected_touched"]), ([], [], []))

    def test_les_champs_de_classe_sont_aussi_dans_la_sortie_d_une_branche_non_controlable(self):
        code, r = self.depot.json_branche("spike/x")
        self.assertEqual(code, 3)
        self.assertEqual((r["protected_judges"], r["protected_sensitive"]), ([], []))

    def test_l_ordre_des_champs_garde_exit_en_dernier(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "y\n"})
        code, sortie, _ = self.depot.module("branch", "feat/x", "--json")
        self.assertRegex(sortie, r'"protected_touched": \[\], "protected_judges": \[\], "protected_sensitive": \[\], "exit": 0\}\s*$')

    def test_texte_deux_lignes_chacune_suivie_de_ses_chemins(self):
        self.depot.branche("feat/x", {"tools/context_lab.py": "d\n", "tools/mapping_lab.py": "v\n", "tests/run_all.sh": "r2\n"})
        code, sortie, _ = self.depot.module("branch", "feat/x")
        lignes = sortie.splitlines()
        i = lignes.index("finish_checks : outillage de fin touché : 1 fichier(s)")
        self.assertEqual(lignes[i + 1], "  - tests/run_all.sh")
        j = lignes.index("finish_checks : outil sensible touché : 2 fichier(s)")
        self.assertEqual(lignes[j + 1:j + 3], ["  - tools/context_lab.py", "  - tools/mapping_lab.py"])
        self.assertNotIn("finish_checks : outillage protégé non touché", lignes)
        self.assertNotIn("finish_checks : outillage protégé touché", sortie)

    def test_texte_sensible_seul_n_a_pas_la_ligne_juge(self):
        self.depot.branche("feat/x", {"tools/mapping_lab.py": "v\n"})
        _, sortie, _ = self.depot.module("branch", "feat/x")
        self.assertIn("finish_checks : outil sensible touché : 1 fichier(s)", sortie)
        self.assertNotIn("outillage de fin touché", sortie)

    def test_texte_rien_de_touche_garde_la_ligne_non_touche(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "y\n"})
        _, sortie, _ = self.depot.module("branch", "feat/x")
        self.assertIn("finish_checks : outillage protégé non touché", sortie)
        self.assertNotIn("outil sensible touché", sortie)
        self.assertNotIn("outillage de fin touché", sortie)

    def test_le_code_de_sortie_ne_depend_pas_de_la_classe(self):
        self.depot.branche("feat/x", {"tools/mapping_lab.py": "v\n"})
        self.depot.branche("feat/y", {"tools/hooks/pre-commit": "h\n"})
        self.assertEqual(self.depot.module("branch", "feat/x")[0], 0)
        self.assertEqual(self.depot.module("branch", "feat/y")[0], 0)

    def test_la_commande_protected_reste_inchangee(self):
        self.depot.branche("feat/x", {"tools/mapping_lab.py": "v\n"}, revenir=False)
        code, sortie, _ = self.depot.module("protected")
        self.assertEqual(code, 0)
        self.assertIn("outillage protégé touché : 1 fichier(s)", sortie)
        self.assertIn("  - tools/mapping_lab.py", sortie)
        self.assertIn("  - tools/hooks/", sortie)   # les motifs sont imprimés sans étiquette


if __name__ == "__main__":
    unittest.main()
