"""Même Node dans l'image de la CI locale et dans `mothra/.node-version` (change mothra-node-lts, design.md D4). Définitions d'image
inventées de la forme réelle du lot 6 (aide_composants.DOCKERFILE_CI : base, uv copié, Python de .python-version, CLI OpenSpec), dont
seule la base `FROM node:<MAJEUR.MINEUR.CORRECTIF>-slim@sha256:...` change, avec les trois entrées de la CI dans l'inventaire : un
écart vient donc du seul contrôle de Node. Le contrôle lit la base par images_ci et exige l'égalité exacte.

    uv run --with pyyaml python -m unittest discover -s tests/composants -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_composants import AvecDepot  # noqa: E402
from aide_node import avec_mothra, definition_image  # noqa: E402


class ImageDeLaCI(AvecDepot):
    def ecart(self, fichier: str, etiquette: str, prefixe: str = ""):
        avec_mothra(self.depot, fichier, image=definition_image(etiquette, prefixe))
        return self.inventaire("--verify")

    def test_versions_egales(self):
        code, sortie, _ = self.ecart("90.1.0", "90.1.0")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("contrôle Node de l'image sauté", sortie)
        self.assertNotIn("Node de l'image de CI", sortie)
        self.assertIn("library/node · docker-image · 90.1.0-slim · CI Dockerfile", sortie)

    def test_majeure_seule_refusee(self):
        code, sortie, _ = self.ecart("90.1.0", "90")
        self.assertEqual(code, 1)
        self.assertIn("Node de l'image de CI différent du Node de Mothra : 90 contre 90.1.0", sortie)

    def test_correctif_different(self):
        code, sortie, _ = self.ecart("90.1.1", "90.1.0")
        self.assertEqual(code, 1)
        self.assertIn("Node de l'image de CI différent du Node de Mothra : 90.1.0 contre 90.1.1", sortie)

    def test_majeures_differentes(self):
        code, sortie, _ = self.ecart("91.0.0", "90.1.0")
        self.assertEqual(code, 1)
        self.assertIn("90.1.0 contre 91.0.0", sortie)

    def test_seul_le_controle_de_node_signale(self):
        code, sortie, _ = self.ecart("90.1.1", "90.1.0")
        self.assertEqual(code, 1)
        ecarts = [l for l in sortie.splitlines() if not l.startswith(("Inventaire", "contrôle")) and " · " not in l]
        self.assertEqual(ecarts, ["Node de l'image de CI différent du Node de Mothra : 90.1.0 contre 90.1.1"])

    def test_base_nommee_par_le_registre(self):
        for prefixe in ("docker.io/library/", "library/", "docker.io/", "index.docker.io/library/"):
            with self.subTest(prefixe=prefixe):
                code, sortie, _ = self.ecart("90.1.0", "90.1.0", prefixe)
                self.assertEqual(code, 0, sortie)
                self.assertNotIn("Node de l'image de CI", sortie)
                code, sortie, _ = self.ecart("90.1.0", "90.1.1", prefixe)
                self.assertEqual(code, 1)
                self.assertIn("Node de l'image de CI différent du Node de Mothra : 90.1.1 contre 90.1.0", sortie)

    def test_autre_image_du_registre_non_lue(self):
        code, sortie, _ = self.ecart("90.1.0", "90.1.0", "docker.io/autre/")
        self.assertEqual(code, 1)
        self.assertIn("Node de l'image de CI différent du Node de Mothra : introuvable contre 90.1.0", sortie)

    def test_base_sans_version_lisible(self):
        avec_mothra(self.depot, "90.1.0", image=definition_image("lts", empreinte=None))
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 1)
        self.assertIn("Node de l'image de CI différent du Node de Mothra : lts contre 90.1.0", sortie)

    def test_definition_absente_saute_sans_echouer(self):
        avec_mothra(self.depot)
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 0, sortie)
        self.assertIn("contrôle Node de l'image sauté : ci/Dockerfile absent", sortie)

    def test_fichier_de_version_absent_saute_sans_echouer(self):
        self.depot.ajouter_ci(definition_image("90.1.0"))
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 0, sortie)
        self.assertIn("contrôle Node de l'image sauté : mothra/.node-version absent", sortie)

    def test_pas_de_controle_hors_verification(self):
        avec_mothra(self.depot, "91.0.0", image=definition_image("90.1.0"))
        code, sortie, _ = self.inventaire()
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("Node de l'image", sortie)


if __name__ == "__main__":
    unittest.main()
