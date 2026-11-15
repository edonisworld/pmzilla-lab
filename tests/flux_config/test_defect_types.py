"""tools/flux_config.py : réglage defect_types (types de tickets comptés comme défauts, outil des photos de qualité par version, change
version-quality-photo, décision D4).

Liste de chaînes non vide, SANS défaut : un réglage absent donne une liste vide (l'outil refuse alors reconstruct et take, il ne retombe
jamais sur un nom de type écrit en dur). Refus avec chemin de clé et ligne, sans la valeur. Données inventées ; aucun accès à Flux-Lab/."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flux_config  # noqa: E402
from yaml_strict import ErreurConfig, charger  # noqa: E402


def lire(texte: str) -> dict:
    return flux_config.to_internal(charger(texte))


class TestDefectTypes(unittest.TestCase):
    def test_clef_connue_et_inchangee(self):
        self.assertIn("defect_types", flux_config.INCHANGEES)

    def test_absent_donne_une_liste_vide_sans_repli(self):
        self.assertEqual(flux_config.defect_types(lire("jira_site: x\n")), [])

    def test_liste_lue(self):
        self.assertEqual(flux_config.defect_types(lire("defect_types: [Bug, ' Defect ']\n")), ["Bug", "Defect"])

    def test_pas_une_liste_refuse_avec_chemin_et_ligne(self):
        with self.assertRaises(ErreurConfig) as c:
            lire("jira_site: x\ndefect_types: ValeurDistinctiveDefaut\n")
        m = str(c.exception)
        self.assertIn("defect_types", m)
        self.assertIn("L2", m)
        self.assertNotIn("ValeurDistinctiveDefaut", m)

    def test_element_non_chaine_refuse_sans_valeur(self):
        with self.assertRaises(ErreurConfig) as c:
            lire("defect_types: [Bug, 4242]\n")
        m = str(c.exception)
        self.assertIn("defect_types", m)
        self.assertIn("L1", m)
        self.assertNotIn("4242", m)

    def test_liste_vide_refusee(self):
        with self.assertRaises(ErreurConfig):
            lire("defect_types: []\n")

    def test_element_vide_refuse(self):
        with self.assertRaises(ErreurConfig):
            lire("defect_types: [Bug, '  ']\n")


if __name__ == "__main__":
    unittest.main()
