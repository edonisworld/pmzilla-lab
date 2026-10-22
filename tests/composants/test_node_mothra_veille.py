"""Veille de Node de Mothra : seules les lignes LTS sont signalées comme versions majeures (change mothra-node-lts, design.md D3).
Listes de publications inventées servies par le faux serveur en boucle locale, aucun réseau.

    uv run --with pyyaml python -m unittest discover -s tests/composants -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_node import FICHIER, PROCEDURE, avec_mothra, publications  # noqa: E402
from aide_verification import AvecSources  # noqa: E402


class Veille(AvecSources):
    def setUp(self):
        super().setUp()
        avec_mothra(self.depot, "90.1.0")

    def nouveautes(self) -> list[str]:
        self.verifier()
        return [f"{n['nature']} {n['available']}" for n in self.etat()["components"]["node-mothra"]["novelties"]]

    def test_correctif_de_la_meme_ligne_est_une_mise_a_jour(self):
        self.serveur.routes["/node/index.json"] = publications(("90.1.1", "Alpha"), ("90.1.0", "Alpha"), ("90.0.0", False))
        code, sortie, _ = self.verifier()
        self.assertEqual(code, 1)
        self.assertIn("node-mothra 90.1.0 → 90.1.1 (mise à jour)", sortie)
        self.assertIn(f"Job proposé : Mettre à jour node-mothra 90.1.0 → 90.1.1 (procédure : {PROCEDURE}, major-watch-only)", sortie)

    def test_ligne_plus_recente_marquee_lts_est_une_version_majeure(self):
        self.serveur.routes["/node/index.json"] = publications(("92.0.1", "Gamma"), ("92.0.0", "Gamma"), ("91.0.0", False),
                                                               ("90.1.0", "Alpha"))
        code, sortie, _ = self.verifier()
        self.assertEqual(code, 1)
        self.assertIn("node-mothra 90.1.0 → 92.0.1 (version majeure)", sortie)
        self.assertIn(f"Job proposé : Mettre à jour node-mothra 90.1.0 → 92.0.1 (procédure : {PROCEDURE}", sortie)
        self.assertNotIn("node-mothra 90.1.0 → 91", sortie)

    def test_ligne_non_lts_jamais_signalee(self):
        self.serveur.routes["/node/index.json"] = publications(("91.2.0", False), ("91.0.0", False), ("90.1.0", "Alpha"))
        self.assertEqual(self.nouveautes(), [])
        self.assertNotIn("node-mothra", self.verifier()[1])

    def test_une_ligne_est_lts_des_qu_une_de_ses_publications_l_est(self):
        self.serveur.routes["/node/index.json"] = publications(("92.1.0", "Gamma"), ("92.0.0", False), ("90.1.0", "Alpha"))
        self.assertEqual(self.nouveautes(), ["major 92.1.0"])

    def test_le_node_de_bmad_garde_sa_regle(self):
        self.serveur.routes["/node/index.json"] = publications(("91.0.0", False), ("24.2.0", "Krypton"), ("24.1.0", "Krypton"))
        _, sortie, _ = self.verifier()
        self.assertIn("node 24.1.0 → 91.0.0 (version majeure)", sortie)
        self.assertNotIn("node-mothra 90.1.0 →", sortie)

    def test_liste_sans_marqueur_lts_rend_le_composant_incomplet(self):
        self.serveur.routes["/node/index.json"] = [{"version": "v92.0.0"}, {"version": "v90.1.0"}]
        _, sortie, _ = self.verifier()
        self.assertEqual(self.etat()["components"]["node-mothra"]["incomplete"], "UnexpectedBody")
        self.assertIn("node-mothra : source injoignable (UnexpectedBody)", sortie)
        self.assertNotIn("node-mothra 90.1.0 →", sortie)

    def test_version_invalide_ignoree_par_la_veille(self):
        self.depot.ecrire(FICHIER, "lts/*")
        self.serveur.routes["/node/index.json"] = publications(("92.0.0", "Gamma"))
        self.assertEqual(self.nouveautes(), [])
        self.assertEqual(self.etat()["components"]["node-mothra"]["used"], "introuvable")


if __name__ == "__main__":
    unittest.main()
