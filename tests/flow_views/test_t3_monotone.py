"""
Relation T3 monotone en le seuil (audit #629, A-78 / L3-07 ; décision de l'auteur R-20261107-29, point 8) : un trimestre dont les lignes
hebdomadaires sont retirées à un seuil entre le plancher et le seuil effectif reste retiré au seuil effectif. Copie de `retiresT3Monotone` de
mothra/contract/src/masquage.ts ; mêmes données que le cas L3-07 de mothra/contract/test/masquage.test.ts. Aucune base, aucun réseau.

    bash tests/run_all.sh flow_views
"""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

NOMS_H = ["team", "type", "week_start", "tickets"]
NOMS_D = ["team", "period", "quarter_start", "throughput"]
# Le 1er janvier 2024 est un lundi : trois semaines pleines du trimestre, deux cellules masquées (nuls de la vue) et une visible (29).
LIGNES = [("A", "Story", "2024-01-01", None), ("A", "Story", "2024-01-08", None), ("A", "Story", "2024-01-15", 29)]
LIEES = {fv.VUE_DEBIT: (NOMS_D, [("A", "quarter", "2024-01-01", 37)])}


class T3Monotone(unittest.TestCase):
    def test_au_plancher_les_trois_lignes_sont_retirees(self):
        # S = 37 - 29 = 8 = 2 x 4 (k fois la borne haute) : la règle (b) échoue, la précondition du cas.
        self.assertEqual(fv.lignes_publiees(fv.VUE_HEBDO, NOMS_H, LIGNES, 5, LIEES), [])

    def test_un_trimestre_retire_au_plancher_le_reste_a_un_seuil_releve(self):
        # À 6, la borne haute vaut 5 et S = 8 est dans l'intervalle strict : publié par la seule évaluation au seuil. Monotone : retiré.
        self.assertEqual(fv.lignes_publiees(fv.VUE_HEBDO, NOMS_H, LIGNES, 6, LIEES), [])


if __name__ == "__main__":
    unittest.main()
