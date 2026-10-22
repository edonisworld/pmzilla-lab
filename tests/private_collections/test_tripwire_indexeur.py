"""
Le fil de déclenchement et l'indexeur (organisation-context, design D11) : l'entrée de l'indexeur dans la liste blanche exige un test de
refus hors boucle locale (tâche 4.1). Le test cherche, dans les tests de l'indexeur, une méthode dont le nom porte « loopback » et dont le
texte vérifie qu'aucun appel au plongement n'a lieu.

    bash tests/run_all.sh private_collections
"""
import ast
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
TESTS_INDEXEUR = RACINE / "tests" / "pmzilla_lab_library"


def methodes_loopback() -> list:
    trouvees = []
    for fichier in sorted(TESTS_INDEXEUR.glob("test_*.py")):
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.FunctionDef) and noeud.name.startswith("test_") and "loopback" in noeud.name:
                trouvees.append((fichier.name, noeud.name, ast.get_source_segment(fichier.read_text(encoding="utf-8"), noeud) or ""))
    return trouvees


class EntreeDeLIndexeur(unittest.TestCase):
    def test_un_test_prouve_le_refus_hors_boucle_locale_sans_appel_au_plongement(self):
        refus = [m for m in methodes_loopback() if "embedding service not local" in m[2] and "self.calls, 0" in m[2]]
        self.assertTrue(refus, "aucun test loopback de l'indexeur ne prouve le refus d'une adresse distante avec zéro appel au plongement")

    def test_un_test_prouve_que_les_adresses_locales_passent(self):
        locales = [m for m in methodes_loopback() if "127.0.0.1" in m[2] and "localhost" in m[2]]
        self.assertTrue(locales)


if __name__ == "__main__":
    unittest.main()
