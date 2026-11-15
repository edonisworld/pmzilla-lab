"""
Test d'ancrage du tableau de bord (tools/dashboard.py), audit #629, A-90 ; R-20261109-19.

    uv run --with pyyaml python -m unittest discover -s tests/dashboard -v

Le journal de la veille est lu, mais seuls les dates, les comptes, les durées et la clé des sources en erreur atteignent la page : le texte d'une
ligne d'erreur et celui d'une ligne non reconnue n'y figurent jamais. Vert d'emblée : aucun code ne change. Retire ce test : quand la lecture du
journal est retirée du tableau de bord.
"""
import tempfile
import unittest
from pathlib import Path

import test_dashboard as base

TEMOIN_ERREUR = "TEMOIN_TEXTE_DE_L_ERREUR_XQ7"
TEMOIN_INCONNUE = "TEMOIN_LIGNE_NON_RECONNUE_XQ7"
CLE_SOURCE = "source-temoin.example"


class JournalVeilleTexteAbsent(unittest.TestCase):
    def test_le_texte_d_une_erreur_et_d_une_ligne_inconnue_n_atteint_pas_la_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws, logs = root / "workspace", root / "logs"
            ws.mkdir()
            base.write(logs / "pmzilla-watch.log", f"""=== 2026-10-11 07:10 ===
{CLE_SOURCE} : 4 nouveaux
{CLE_SOURCE} : ERREUR {TEMOIN_ERREUR}
{TEMOIN_INCONNUE}
""")
            env = {"PMZILLA_LAB_WORKSPACE": str(ws), "PMZILLA_LAB_DATA": str(root / "data"), "PMZILLA_LAB_LOGS": str(logs)}
            resultat, page = base.generer(root, env)
            self.assertEqual(resultat.returncode, 0, resultat.stderr)
            self.assertNotIn(TEMOIN_ERREUR, page)
            self.assertNotIn(TEMOIN_INCONNUE, page)
            self.assertIn(CLE_SOURCE, page)          # garde le test honnête : le journal est bien lu (la clé de la source en erreur)


if __name__ == "__main__":
    unittest.main()
