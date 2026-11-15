"""
Le contrat des vues (contrats/vues.json) liste les quatre statistiques « sans les anciens » de v_team_lead_time_throughput (change masking-sums, tâche 22.1 ;
D16 ; R-20261105-30 ; R-20261106-58 pour l'ordre en fin de liste). Le test statique du contrat contre les migrations (test_contrat_vues.py) vérifie qu'elles
existent dans le SELECT final de la vue, masquées par la vue, dans chaque branche de l'UNION.

    bash tests/run_all.sh flow_views
"""
import json
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
NOUVELLES = ["lead_median_days_excl_old", "lead_p85_days_excl_old", "cycle_median_days_excl_old", "cycle_p85_days_excl_old"]


class Contrat(unittest.TestCase):
    def test_le_contrat_liste_les_quatre_colonnes_apres_les_statistiques_existantes(self):
        contrat = json.loads((RACINE / "contrats" / "vues.json").read_text(encoding="utf-8"))
        debit = next(v for v in contrat["views"] if v["name"] == "v_team_lead_time_throughput")
        self.assertEqual(debit["maskableColumns"], ["lead_median_days", "lead_p85_days", "cycle_median_days", "cycle_p85_days", *NOUVELLES])
        self.assertEqual(debit["countColumns"], ["throughput", "items_lt", "items_ct", "items_old", "items_without_commitment"])   # aucun compte ajouté
        self.assertEqual(debit["plainColumns"], ["team", "period", "quarter_start"])


if __name__ == "__main__":
    unittest.main()
