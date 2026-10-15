"""tools/flux_config.py : réglage epic_types (types de tickets « épic », outil des statuts d'épics, change R-58 groupe 10).

Liste de chaînes, défaut ["Epic"] ; refus avec chemin de clé et ligne, sans la valeur. Données inventées ; aucun accès à Flux-Lab/."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flux_config  # noqa: E402
from yaml_strict import ErreurConfig, charger  # noqa: E402


def lire(texte: str) -> dict:
    return flux_config.to_internal(charger(texte))


class TestEpicTypes(unittest.TestCase):
    def test_defaut_sans_reglage(self):
        self.assertEqual(flux_config.epic_types(lire("jira_site: x\n")), ["Epic"])

    def test_liste_lue(self):
        self.assertEqual(flux_config.epic_types(lire("epic_types: [Epic, Initiative]\n")), ["Epic", "Initiative"])

    def test_pas_une_liste_refuse_avec_chemin_et_ligne(self):
        with self.assertRaises(ErreurConfig) as c:
            lire("jira_site: x\nepic_types: ValeurDistinctiveEpic\n")
        m = str(c.exception)
        self.assertIn("epic_types", m)
        self.assertIn("L2", m)
        self.assertNotIn("ValeurDistinctiveEpic", m)

    def test_element_non_chaine_refuse_sans_valeur(self):
        with self.assertRaises(ErreurConfig) as c:
            lire("epic_types: [Epic, 4242]\n")
        m = str(c.exception)
        self.assertIn("epic_types", m)
        self.assertIn("L1", m)
        self.assertNotIn("4242", m)

    def test_liste_vide_refusee(self):
        with self.assertRaises(ErreurConfig):
            lire("epic_types: []\n")


if __name__ == "__main__":
    unittest.main()
