"""
Module d'empreinte cassé et contrôle 6 de tools/finish_checks.py (change finish-single-b3-b6, tâches 4.1 à 4.3 ; conception D13, D14, D17).

    uv run python -m unittest discover -s tests/finish_checks -v

Rétablis par B9 (finish-single-b7-b9, revue 4.7, R-20261105-32) depuis tests/finish_checks/test_delegation.py, supprimé avec la fin unitaire
tools/finish_branch.sh : ces deux tests ne testent que le module, la moitié « script » (depot.script et la phrase « finish_branch : ... ») est seule retirée.
Des dépôts jetables avec un dépôt distant nu et une copie du module (tests/finish_checks/aide_depot.py).
"""
import unittest

from aide_depot import AvecDepot


class EmpreinteCassee(AvecDepot):
    """Le module d'empreinte cassé donne le refus 6 dédié (code et phrase d'aujourd'hui), jamais le 53 : l'import n'est plus en tête du module."""

    def casse(self):
        self.depot.commit({"tools/posture_eval_fingerprint.py": "raise SystemExit(1)\n"}, "module d'empreinte cassé")
        self.depot.git("push", "-q", "origin", "main")

    def test_module_d_empreinte_qui_quitte_a_l_import_refuse_le_6_du_module(self):
        sommet = self.depot.branche("feat/x", {"CLAUDE.md": "changé\n"})
        self.depot.enregistrer_essai("2026-01-02", sommet, empreinte=self.depot.empreinte(sommet))
        self.casse()
        code_module, r = self.depot.json_branche("feat/x")
        self.assertEqual((code_module, self.verdicts(r)["6"]), (1, "refused"))
        c6 = next(c for c in r["controls"] if c["id"] == "6")
        self.assertTrue(any("n'a pas pu être calculée" in d for d in c6["details"]), c6)

    def test_les_autres_controles_sont_calcules_quand_l_empreinte_est_cassee(self):
        self.depot.branche("feat/x", {"CLAUDE.md": "changé\n", "db/001.sql": "SELECT 2;\n"})
        self.casse()
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(r["exit"], 1)
        self.assertEqual(self.verdicts(r)["14"], "refused")


if __name__ == "__main__":
    unittest.main()
