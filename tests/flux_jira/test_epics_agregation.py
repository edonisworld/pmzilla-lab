"""Agrégation et masquage du rapport de flux des épics (R-89, conception D10, tâche 2.7).

    bash tests/run_all.sh flux_jira

`fj.lignes_par_equipe(epics, calcul, contexte)` applique une fonction de calcul par ligne (domaine, équipes par ordre de nom, puis
« sans équipe ») et rend des cellules structurées `{"value", "state"}` déjà masquées : le JSON n'a jamais à relire un texte. Fonctions
de calcul inventées ici ; les mesures réelles sont dans test_epics_calcul.py. Aucune clé, aucun titre, aucune étiquette.
"""
import json
import sys
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
from aide_epics import contexte, epic  # noqa: E402
from aide_espace import fj  # noqa: E402


def epics_de(**par_equipe) -> list:
    """Des épics du pilote : equipe=nombre ; la clé `sans` donne des épics sans équipe."""
    liste = []
    for nom, n in par_equipe.items():
        liste += [epic(equipes=() if nom == "sans" else (nom,)) for _ in range(n)]
    return liste


def compte(epics, ctx):
    return {"n": fj.compte_brut(len(epics))}


def lignes(epics, calcul=compte):
    return fj.lignes_par_equipe(epics, calcul, contexte())


def cellules(rows, colonne="n"):
    return [(r["row"], r["team"], r["cells"][colonne]["value"], r["cells"][colonne]["state"]) for r in rows]


class Lignes(unittest.TestCase):
    def test_domaine_puis_equipes_par_ordre_de_nom_puis_sans_equipe(self):
        rows = lignes(epics_de(Zeta=9, Alpha=5, sans=6))
        self.assertEqual([(r["row"], r["team"]) for r in rows],
                         [("pilot_domain", None), ("team", "Alpha"), ("team", "Zeta"), ("no_team", None)])

    def test_ordre_de_nom_et_non_de_valeur(self):
        rows = lignes(epics_de(Zeta=30, Alpha=5))
        self.assertEqual([r["team"] for r in rows[1:]], ["Alpha", "Zeta"])

    def test_ligne_sans_equipe_absente_quand_vide(self):
        rows = lignes(epics_de(Alpha=6))
        self.assertEqual([r["row"] for r in rows], ["pilot_domain", "team"])

    def test_epic_sans_equipe_dans_le_domaine_et_la_ligne_sans_equipe_seulement(self):
        rows = lignes(epics_de(Alpha=6, sans=7))
        self.assertEqual(cellules(rows), [("pilot_domain", None, 13, "ok"), ("team", "Alpha", 6, "ok"), ("no_team", None, 7, "ok")])

    def test_premiere_equipe_seulement(self):
        e = epic(equipes=("Beta", "Alpha"))
        rows = fj.lignes_par_equipe([e] * 6, compte, contexte())
        self.assertEqual([r["team"] for r in rows[1:]], ["Beta"])

    def test_aucun_epic_aucune_ligne_d_equipe(self):
        rows = lignes([])
        self.assertEqual([r["row"] for r in rows], ["pilot_domain"])


class Masquage(unittest.TestCase):
    def test_petite_cellule_d_equipe(self):
        """Domaine 20, A 12, B 6, C 2 : le domaine dit 20, A 12, B à l'état « masked » (suppression secondaire), C à
        l'état « lt5 » ; les deux s'écrivent « masqué » / « masked » dans le Markdown (idée #417)."""
        rows = lignes(epics_de(A=12, B=6, C=2))
        self.assertEqual(cellules(rows), [("pilot_domain", None, 20, "ok"), ("team", "A", 12, "ok"),
                                          ("team", "B", None, "masked"), ("team", "C", None, "lt5")])

    def test_zero_est_masque(self):
        rows = fj.lignes_par_equipe(epics_de(A=6), lambda e, c: {"n": fj.compte_brut(0)}, contexte())
        self.assertEqual(rows[1]["cells"]["n"], {"value": None, "state": "lt5"})

    def test_deux_cellules_masquees_pas_de_suppression_secondaire(self):
        rows = lignes(epics_de(A=12, B=6, C=2, D=3))
        self.assertEqual([c[3] for c in cellules(rows)], ["ok", "ok", "ok", "lt5", "lt5"])

    def test_aucune_cellule_masquee_aucune_suppression(self):
        rows = lignes(epics_de(A=12, B=6))
        self.assertEqual([c[3] for c in cellules(rows)], ["ok", "ok", "ok"])

    def test_le_plus_petit_des_autres_est_masque(self):
        rows = lignes(epics_de(A=40, B=9, C=7, D=2))
        self.assertEqual([c[3] for c in cellules(rows)], ["ok", "ok", "ok", "masked", "lt5"])

    def test_la_ligne_sans_equipe_est_une_ligne_d_equipe_pour_la_suppression(self):
        rows = lignes(epics_de(A=12, sans=2))
        self.assertEqual([c[3] for c in cellules(rows)], ["ok", "masked", "lt5"])

    def test_la_ligne_du_domaine_n_est_jamais_masquee_par_suppression(self):
        rows = lignes(epics_de(A=3, B=9))
        self.assertEqual(cellules(rows)[0], ("pilot_domain", None, 12, "ok"))
        self.assertEqual([c[3] for c in cellules(rows)[1:]], ["lt5", "masked"])

    def test_percentile_sur_moins_de_cinq_epics(self):
        def calcul(epics, ctx):
            return {"p50": fj.percentile_brut(12.5, len(epics))}
        rows = fj.lignes_par_equipe(epics_de(A=4, B=5, C=9), calcul, contexte())
        self.assertEqual([(r["team"], r["cells"]["p50"]["value"], r["cells"]["p50"]["state"]) for r in rows],
                         [(None, 12.5, "ok"), ("A", None, "lt5"), ("B", 12.5, "ok"), ("C", 12.5, "ok")])

    def test_les_percentiles_ne_declenchent_pas_la_suppression_secondaire(self):
        def calcul(epics, ctx):
            return {"p50": fj.percentile_brut(12.5, len(epics))}
        rows = fj.lignes_par_equipe(epics_de(A=4, B=9, C=11), calcul, contexte())
        self.assertEqual([r["cells"]["p50"]["state"] for r in rows], ["ok", "lt5", "ok", "ok"])

    def test_ligne_de_repartition(self):
        """Les cellules d'un même groupe de ligne (compartiments qui font un total) suivent la règle le long de la ligne."""
        def calcul(epics, ctx):
            n = len(epics)
            return {"b1": fj.compte_brut(n, "r"), "b2": fj.compte_brut(3, "r"), "b3": fj.compte_brut(n + 4, "r")}
        rows = fj.lignes_par_equipe(epics_de(A=7), calcul, contexte())
        equipe = rows[1]["cells"]
        self.assertEqual((equipe["b1"]["state"], equipe["b2"]["state"], equipe["b3"]["state"]), ("masked", "lt5", "ok"))
        self.assertEqual((equipe["b3"]["value"], equipe["b1"]["value"]), (11, None))

    def test_etat_force_traverse_l_agregation(self):
        def calcul(epics, ctx):
            return {"x": fj.etat_brut("cycle_in_progress"), "y": fj.etat_brut("not_computed"), "z": fj.etat_brut("no_reference")}
        rows = fj.lignes_par_equipe(epics_de(A=6), calcul, contexte())
        self.assertEqual([rows[1]["cells"][c] for c in ("x", "y", "z")],
                         [{"value": None, "state": "cycle_in_progress"}, {"value": None, "state": "not_computed"},
                          {"value": None, "state": "no_reference"}])

    def test_cellules_structurees_dans_le_json(self):
        rows = lignes(epics_de(A=12, B=6, C=2))
        relu = json.loads(json.dumps(rows))
        self.assertEqual(relu[2]["cells"]["n"], {"value": None, "state": "masked"})
        self.assertEqual(relu[3]["cells"]["n"], {"value": None, "state": "lt5"})
        self.assertEqual(relu[1]["cells"]["n"], {"value": 12, "state": "ok"})
        for ligne in relu:
            for cellule in ligne["cells"].values():
                self.assertEqual(set(cellule), {"value", "state"})
                self.assertIn(cellule["state"], {"ok", "lt5", "masked", "no_reference", "cycle_in_progress", "not_computed"})

    def test_centile_arrondi_au_dixieme_et_compte_rendu_tel_quel(self):
        """masking-mutation-tests 6.2, mutants tués dans cellule_masquee : `genre == "compte"` devenu `!=` (ou la condition niée)
        et la constante d'arrondi 1 devenue 2 ou 0."""
        self.assertEqual(fj.cellule_masquee(fj.percentile_brut(12.34, 5)), {"value": 12.3, "state": "ok"})
        self.assertEqual(fj.cellule_masquee(fj.percentile_brut(7.06, 9)), {"value": 7.1, "state": "ok"})
        cellule = fj.cellule_masquee(fj.compte_brut(12))
        self.assertEqual(cellule, {"value": 12, "state": "ok"})
        self.assertIs(type(cellule["value"]), int)                 # un compte n'est jamais converti en nombre à virgule
        self.assertEqual(fj.cellule_masquee(fj.compte_brut(5)), {"value": 5, "state": "ok"})
        self.assertEqual(fj.cellule_masquee(fj.compte_brut(4)), {"value": None, "state": "lt5"})
        self.assertEqual(fj.cellule_masquee(fj.percentile_brut(3.0, 4)), {"value": None, "state": "lt5"})

    def test_aucune_valeur_masquee_dans_le_json(self):
        ecrites = [c["value"] for ligne in json.loads(json.dumps(lignes(epics_de(A=12, B=6, C=2)))) for c in ligne["cells"].values()]
        self.assertNotIn(6, ecrites)
        self.assertNotIn(2, ecrites)


if __name__ == "__main__":
    unittest.main()
