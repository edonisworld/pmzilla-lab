"""openspec/config.yaml : chaque règle est lue comme du texte. Une règle qui contient un « : » non protégé est lue par YAML comme un
dictionnaire, et openspec l'ignore sans rien dire ; les règles à deux-points sont donc entre guillemets. Le test charge le fichier,
vérifie que `rules` est un dictionnaire de listes dont chaque élément est une chaîne non vide, et que les listes proposal et design
portent la règle « What Mothra will consume », et que les listes proposal et tasks portent la règle des tranches de Mothra
(« product:mothra » et « mothra-tranches.md », décision du 2026-10-18). Aucun accès extérieur.

    python3 -m unittest discover -s tests/workflow_commands -v
"""
import unittest
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parents[2] / "openspec" / "config.yaml"
MOTIF_MOTHRA = "What Mothra will consume"
MOTIFS_TRANCHES = ("product:mothra", "mothra-tranches.md")


def charger_regles() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["rules"]


class ReglesOpenspecConfig(unittest.TestCase):
    def test_rules_est_un_dictionnaire_de_listes(self):
        regles = charger_regles()
        self.assertIsInstance(regles, dict)
        self.assertTrue(regles, "rules est vide")
        for nom, liste in regles.items():
            self.assertIsInstance(liste, list, f"rules.{nom} n'est pas une liste")

    def test_chaque_regle_est_une_chaine_non_vide(self):
        for nom, liste in charger_regles().items():
            for rang, regle in enumerate(liste, 1):
                self.assertIsInstance(regle, str, f"rules.{nom}, règle {rang} : lue comme {type(regle).__name__}, "
                                                  "probable « : » non protégé (mettre la règle entre guillemets)")
                self.assertTrue(regle.strip(), f"rules.{nom}, règle {rang} : vide")

    def test_proposal_et_design_demandent_ce_que_mothra_consommera(self):
        regles = charger_regles()
        for nom in ("proposal", "design"):
            self.assertTrue(any(isinstance(r, str) and MOTIF_MOTHRA in r for r in regles.get(nom, [])),
                            f"rules.{nom} ne contient aucune règle qui mentionne « {MOTIF_MOTHRA} »")

    def test_proposal_et_tasks_portent_la_regle_des_tranches(self):
        regles = charger_regles()
        for nom in ("proposal", "tasks"):
            self.assertTrue(any(isinstance(r, str) and all(m in r for m in MOTIFS_TRANCHES) for r in regles.get(nom, [])),
                            f"rules.{nom} ne contient aucune règle qui mentionne « product:mothra » et « mothra-tranches.md »")


if __name__ == "__main__":
    unittest.main()
