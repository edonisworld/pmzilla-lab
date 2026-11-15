"""
Témoins Task du jeu synthétique des panneaux de R-150 (tâche 36.1, décision R-20261031-27 Q58, plan R-150 Q2 A) : le groupe de types `story` de la vue
v_team_flow_inout couvre Story et Task. Le jeu porte donc des tâches, en tables à part (CREES_TACHES, TERMINES_TACHES) : les tables de Story seul
(CREES_ATTENDUS, TERMINES_ATTENDUS) et leur test (test_panneaux_r150.py) restent tels quels. Sans base : la forme du jeu ; la vue compte les tâches
dans le groupe `story` (tests/db/test_flow_team_flow_inout.py).

    bash tests/run_all.sh mothra_donnees
"""
from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(DOSSIER))
import jeu_synthetique as base  # noqa: E402
import tranche1 as t1  # noqa: E402
import panneaux_r150 as p  # noqa: E402

MAINTENANT = base.INSTANT_FIXE
SEUIL = 5


def taches(tickets):
    return [t for t in tickets if t["type"] == p.TYPE_TACHE]


def tables_taches(tickets):
    crees, termines = Counter(), Counter()
    for t in taches(tickets):
        if t["projet"] in p.PROJETS_EXCLUS:
            continue
        k = t1.indice_trimestre(MAINTENANT, t["cree"])
        if 0 <= k <= 3:
            crees[(t["equipe"], k)] += 1
        if t["resolu"]:
            k = t1.indice_trimestre(MAINTENANT, t["resolu"])
            if 0 <= k <= 3:
                termines[(t["equipe"], k)] += 1
    return crees, termines


class TemoinsTask(unittest.TestCase):
    def setUp(self):
        self.tickets = p.construire_panneaux(MAINTENANT)

    def test_le_jeu_porte_des_taches_d_equipes_generiques_de_la_population(self):
        self.assertEqual(p.TYPE_TACHE, "Task")
        lot = taches(self.tickets)
        self.assertTrue(lot)
        for t in lot:
            self.assertIn(t["equipe"], p.EQUIPES_PANNEAUX)
            self.assertEqual(t["projet"], base.SENTINELLES[0], t["cle"])        # dans la population : ni portefeuille, ni projet exclu
            self.assertRegex(t["cle"], r"^SYN-[1-9][0-9]*$")

    def test_les_tables_declarees_egalent_les_comptes_recalcules(self):
        crees, termines = tables_taches(self.tickets)
        self.assertEqual(dict(crees), dict(p.CREES_TACHES))
        self.assertEqual(dict(termines), dict(p.TERMINES_TACHES))

    def test_des_taches_font_franchir_le_plancher_a_une_cellule_de_stories_et_d_autres_non(self):
        franchit, reste = False, False
        for (equipe, k), n in p.CREES_TACHES.items():
            histoires = p.CREES_ATTENDUS.get((equipe, "story", k), 0)
            if histoires < SEUIL <= histoires + n:
                franchit = True
            if histoires + n < SEUIL:
                reste = True
        self.assertTrue(franchit, "une cellule sous 5 en stories seules et à 5 ou plus avec les tâches")
        self.assertTrue(reste, "une cellule qui reste sous 5 avec les tâches")

    def test_des_taches_creees_non_finies_et_aucun_ticket_existant_deplace(self):
        self.assertTrue(any(t["resolu"] is None for t in taches(self.tickets)))
        avant = p.construire_panneaux(MAINTENANT)
        self.assertEqual(avant, self.tickets)                                   # déterministe
        non_taches = [t for t in self.tickets if t["type"] != p.TYPE_TACHE]
        self.assertEqual(non_taches[0]["cle"], f"{base.PREFIXE_CLE}{p.CLE_DEPART + 1}")   # les clés des témoins existants ne bougent pas : les tâches viennent après
        self.assertEqual([t["cle"] for t in non_taches], [t["cle"] for t in self.tickets[:len(non_taches)]])


if __name__ == "__main__":
    unittest.main()
