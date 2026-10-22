"""Node de Mothra : genre `node-runtime` et version lue dans `mothra/.node-version` (change mothra-node-lts, design.md D2, D3). Fichiers
de version inventés sous des dossiers temporaires, aucun réseau.

    uv run --with pyyaml python -m unittest discover -s tests/composants -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_composants import AvecDepot  # noqa: E402
from aide_node import avec_mothra  # noqa: E402


class Inventaire(AvecDepot):
    def test_genre_accepte_et_version_lue_dans_le_fichier(self):
        avec_mothra(self.depot, "90.1.0\n")
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 0, sortie)
        self.assertIn("node-mothra · node-runtime · 90.1.0 · mothra/.node-version", sortie)
        self.assertIn("Inventaire à jour : 22 composant(s)", sortie)

    def test_le_node_de_bmad_reste_non_epingle(self):
        avec_mothra(self.depot)
        _, sortie, _ = self.inventaire()
        self.assertIn("node · tool · non épinglé · not pinned (fnm)", sortie)

    def test_contenu_invalide_refuse(self):
        for contenu in ("lts/*", "v90.1.0", "90.1", "latest", "90.x.0", "", "Iron"):
            with self.subTest(contenu=contenu):
                avec_mothra(self.depot, contenu)
                code, sortie, _ = self.inventaire()
                self.assertEqual(code, 1, sortie)
                self.assertIn(f"version de Node de Mothra invalide : {contenu.strip()} (attendu MAJEUR.MINEUR.CORRECTIF)", sortie)

    def test_contenu_invalide_jamais_affiche_en_entier(self):
        longue = "x" * 200
        for contenu, apercu in (("90.1.0 \n90.2.0", "90.1.0 …"), (longue, "x" * 40 + " …"),
                                ("lts/*\nligne-secrete-a-ne-pas-afficher\n", "lts/* …")):
            with self.subTest(contenu=contenu[:20]):
                avec_mothra(self.depot, contenu)
                code, sortie, _ = self.inventaire()
                self.assertEqual(code, 1, sortie)
                self.assertIn(f"version de Node de Mothra invalide : {apercu} (attendu MAJEUR.MINEUR.CORRECTIF)", sortie)
                self.assertNotIn("90.2.0", sortie)
                self.assertNotIn("x" * 41, sortie)
                self.assertNotIn("ligne-secrete", sortie)

    def test_fichier_sans_entree(self):
        avec_mothra(self.depot, entree_presente=False)
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 1)
        self.assertIn("Composant à ajouter à l'inventaire : node-mothra (déclaré dans mothra/.node-version)", sortie)

    def test_entree_sans_fichier(self):
        avec_mothra(self.depot, version=None)
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 1)
        self.assertIn("Composant à retirer de l'inventaire : node-mothra", sortie)

    def test_sans_fichier_ni_entree_rien_ne_change(self):
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("node-mothra", sortie)

    def test_aucun_fichier_ecrit(self):
        avec_mothra(self.depot)
        self.depot.fichiers_initiaux = {p: p.read_bytes() for p in self.depot.racine.rglob("*") if p.is_file()}
        self.inventaire("--verify")
        self.assertEqual(self.depot.inchange(), [])


if __name__ == "__main__":
    unittest.main()
