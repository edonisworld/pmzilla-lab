"""Contenu de tools/flow_glossary.py, testé directement (jusqu'ici seulement à travers les rapports et le tableau de bord).

    uv run --with pyyaml --with numpy python -m unittest discover -s tests/flux_jira -v

- les deux langues ont exactement les mêmes clés, chacune avec une définition non vide ;
- toutes les clés des ordres de lecture existent, sans doublon ;
- lignes_rapport rend une puce par définition, dans l'ordre fixe, dans la langue demandée.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import flow_glossary as g  # noqa: E402


class Glossaire(unittest.TestCase):
    def test_deux_langues_memes_cles(self):
        self.assertEqual(set(g.GLOSSAIRE), {"fr", "en"})
        self.assertEqual(set(g.GLOSSAIRE["fr"]), set(g.GLOSSAIRE["en"]))

    def test_chaque_definition_est_non_vide(self):
        for langue, definitions in g.GLOSSAIRE.items():
            self.assertTrue(definitions)
            for cle, texte in definitions.items():
                self.assertIsInstance(texte, str, (langue, cle))
                self.assertTrue(texte.strip(), (langue, cle))
                self.assertTrue(texte.lstrip().startswith("**"), (langue, cle))      # un terme en gras ouvre la définition

    def test_les_deux_langues_ne_sont_pas_identiques(self):
        for cle in g.GLOSSAIRE["fr"]:
            self.assertNotEqual(g.GLOSSAIRE["fr"][cle], g.GLOSSAIRE["en"][cle], cle)

    def test_les_ordres_de_lecture_designent_des_cles_existantes(self):
        ids = g.ORDRE_RAPPORT + g.ORDRE_SEGMENT + g.ORDRE_FERMETURES
        self.assertEqual(len(ids), len(set(ids)))
        for langue in g.GLOSSAIRE:
            self.assertFalse(set(ids) - set(g.GLOSSAIRE[langue]), langue)

    def test_lignes_du_rapport_dans_l_ordre_et_la_langue(self):
        for langue in ("fr", "en"):
            simple = g.lignes_rapport(langue)
            self.assertEqual(simple, [f"- {g.GLOSSAIRE[langue][i]}" for i in g.ORDRE_RAPPORT])
            complet = g.lignes_rapport(langue, segments=True, fermetures=True)
            self.assertEqual(complet, [f"- {g.GLOSSAIRE[langue][i]}" for i in
                                       g.ORDRE_RAPPORT + g.ORDRE_SEGMENT + g.ORDRE_FERMETURES])
        self.assertNotEqual(g.lignes_rapport("fr"), g.lignes_rapport("en"))


if __name__ == "__main__":
    unittest.main()
