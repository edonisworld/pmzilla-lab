"""
Mesure de 22.1 sur le jeu synthétique de la tranche 1 (R-20261106-39, option (d) ; R-20261106-36, R-20261106-18) : nombre d'équipes dont le verdict F-H1
est possible (un verdict autre que « échantillon insuffisant » ou « masqué »), sur l'année groupée lue par la fiche, avec items_old = 0 montré quand
items_ct l'est. La règle de taille de H1 : items_lt et items_ct moins items_old atteignent chacun la taille d'une médiane ; un items_old masqué donne
« échantillon insuffisant ». Mesure attendue : 14 équipes sur 17, comme avant la règle, et les mêmes 14 ; aucun verdict d'équipe témoin ne change
(test_tranche1_masquage.py, qui rejoue VERDICTS_ATTENDUS sur les vues masquées, reste vert avec les mêmes valeurs attendues).

    bash tests/run_all.sh mothra_donnees
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(DOSSIER))
import tranche1 as t1  # noqa: E402
import test_tranche1 as tt  # noqa: E402
import test_tranche1_masquage as tm  # noqa: E402

sys.path.insert(0, str(DOSSIER.parents[1] / "tools"))
import flow_views as fv  # noqa: E402

POSSIBLES_ATTENDUES = ("équipe E", "équipe F", "équipe G", "équipe H", "équipe I", "équipe L", "équipe M", "équipe N", "équipe O", "équipe P",
                       "équipe Q", "équipe R", "équipe T", "équipe U")


def possible(annee, regle_nouvelle):
    if annee is None or not tm.visible(annee["items_lt"]) or not tm.visible(annee["items_ct"]):
        return False
    n_lt, n_ct = annee["items_lt"]["value"], annee["items_ct"]["value"]
    if regle_nouvelle:
        if not tm.visible(annee["items_old"]):
            return False
        n_lt, n_ct = n_lt - annee["items_old"]["value"], n_ct - annee["items_old"]["value"]
    return n_lt >= tt.FIABLE_MEDIANE and n_ct >= tt.FIABLE_MEDIANE


class Mesure(unittest.TestCase):
    def test_quatorze_verdicts_possibles_sur_dix_sept_avec_le_zero_montre(self):
        tickets = t1.construire_tranche1(tm.MAINTENANT)
        v = tm.Vues(tickets, tm.MAINTENANT)
        equipes = t1.EQUIPES_TRANCHE1
        self.assertEqual(len(equipes), 17)
        avant = [e for e in equipes if possible(v.ligne(e, None), False)]
        apres = [e for e in equipes if possible(v.ligne(e, None), True)]
        self.assertEqual(len(apres), 14, apres)
        self.assertEqual(tuple(apres), POSSIBLES_ATTENDUES)
        self.assertEqual(apres, avant)           # la règle de taille ne retire aucune équipe : l'ensemble est celui d'avant

    def test_quatorze_verdicts_possibles_sur_dix_sept_avec_les_quatre_colonnes_sans_les_anciens(self):
        """22.1, R-20261106-59 (Q1 (a)) : la réplique des vues porte les quatre colonnes sans les anciens ; le verdict F-H1 est possible quand les deux médianes
        sans les anciens sont lisibles et que la taille de H1 (items_lt et items_ct moins items_old, cellules montrées) atteint la taille d'une médiane. Mesure sous la
        règle de la première 0038 (statistique publiée sur m - o ou c - o d'au moins 5 seul) et sous (a) (statistique publiée seulement avec items_old montré) :
        attendu 14 sur 17, les mêmes équipes."""
        tickets = t1.construire_tranche1(tm.MAINTENANT)
        equipes = t1.EQUIPES_TRANCHE1

        def possibles(regle):
            v = tm.Vues(tickets, tm.MAINTENANT, regle)
            sortie = []
            for e in equipes:
                annee = v.ligne(e, None)
                if annee is None:
                    continue
                lead = fv.taille_echantillon_h1(annee, "lead")
                cycle = fv.taille_echantillon_h1(annee, "cycle")
                cm = tm.valeur(annee, "cycle_median_days_excl_old")
                if (tm.visible(annee["lead_median_days_excl_old"]) and cm is not None and cm > 0 and lead is not None and cycle is not None
                        and lead >= tt.FIABLE_MEDIANE and cycle >= tt.FIABLE_MEDIANE):
                    sortie.append(e)
            return sortie
        ancienne, a = possibles("ancienne"), possibles("a")
        print(f"mesure F-H1 : ancienne règle {len(ancienne)} sur {len(equipes)}, règle (a) {len(a)} sur {len(equipes)}")
        self.assertEqual((len(ancienne), len(a)), (14, 14), (ancienne, a))
        self.assertEqual(tuple(a), POSSIBLES_ATTENDUES)
        self.assertEqual(ancienne, a)

    def test_le_zero_d_items_old_est_montre_pour_les_equipes_sans_ancien_et_quinze_pour_l_equipe_q(self):      # quinze : trois trimestres de cinq (R-20261114-49)
        v = tm.Vues(t1.construire_tranche1(tm.MAINTENANT), tm.MAINTENANT)
        for equipe in t1.EQUIPES_TRANCHE1:
            annee, vrai = v.ligne(equipe, None), v.vraies[(equipe, "pooled_year", None)]
            if tm.visible(annee["items_ct"]):
                self.assertEqual(tm.valeur(annee, "items_old"), vrai["items_old"], equipe)


if __name__ == "__main__":
    unittest.main()
