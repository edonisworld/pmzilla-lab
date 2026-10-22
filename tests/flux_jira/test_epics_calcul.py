"""Calculs des cinq mesures du rapport de flux des épics (R-89, tâche 2.6) : fonctions pures sur des épics inventés.

    bash tests/run_all.sh flux_jira

Spec jira-flow-epic-flow, un scénario par test. Chaque fonction `calculer_*` rend un dictionnaire nom de cellule -> valeur brute
(`fj.Brut` : genre « compte », « pct » ou « etat », valeur, effectif), pour une ligne ; le masquage est celui de l'agrégation
(test_epics_agregation.py). Aucun accès à une base, à un fichier ou à Jira.
"""
import datetime as dt
import sys
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
from aide_epics import CYCLES, DISCOVERY, FUSEAU, UTC, contexte, domaine, epic, inst, periode  # noqa: E402
from aide_espace import fj  # noqa: E402


def valeurs(resultat: dict) -> dict:
    return {cle: brut.valeur for cle, brut in resultat.items()}


class Population(unittest.TestCase):
    def test_domaine_ouvert_le_jour_du_calcul(self):
        ouvert, jamais, retire = epic(), epic(), epic()
        jamais["periodes"] = []
        retire["periodes"] = [domaine("2026-01-02", "2026-03-01")]
        pilote = fj.epics_du_pilote([ouvert, jamais, retire], dt.date(2026, 7, 1))
        self.assertEqual(pilote, [ouvert])

    def test_autres_roles_ne_font_pas_le_pilote(self):
        e = epic()
        e["periodes"] = [periode("cycle", "2026-01-02", cycle="2026-C1")]
        self.assertEqual(fj.epics_du_pilote([e], dt.date(2026, 7, 1)), [])


class PointsDeDepart(unittest.TestCase):
    def test_cree_dans_la_colonne_de_depart(self):
        e = epic("2026-01-12", transitions=[("2026-02-01", "s-idee", "s-pret")])
        self.assertEqual(fj.debut_idee(e, DISCOVERY), inst("2026-01-12"))

    def test_statut_initial_courant_sans_transition(self):
        e = epic("2026-01-12", etat="s-cadrage")
        self.assertEqual(fj.debut_idee(e, DISCOVERY), inst("2026-01-12"))

    def test_cree_ailleurs_premiere_entree_dans_la_colonne(self):
        e = epic("2026-01-06", etat="s-pret", transitions=[("2026-01-16", "s-brouillon", "s-idee"), ("2026-01-31", "s-idee", "s-pret")])
        self.assertEqual(fj.debut_idee(e, DISCOVERY), inst("2026-01-16"))

    def test_jamais_dans_la_colonne_de_depart(self):
        e = epic("2026-01-06", etat="s-pret", transitions=[("2026-01-16", "s-brouillon", "s-revue")])
        self.assertIsNone(fj.debut_idee(e, DISCOVERY))

    def test_fin_par_la_colonne_ready(self):
        e = epic(transitions=[("2026-02-01", "s-idee", "s-revue"), ("2026-02-05", "s-revue", "s-pret"), ("2026-02-09", "s-pret", "s-revue")])
        self.assertEqual(fj.fin_ready(e, DISCOVERY, "colonne"), inst("2026-02-05"))

    def test_fin_par_l_etiquette_ready_premier_ajout(self):
        e = epic(periodes=[periode("ready", "2026-02-10", "2026-02-12"), periode("ready", "2026-02-20")])
        self.assertEqual(fj.fin_ready(e, DISCOVERY, "label"), inst("2026-02-10"))
        self.assertIsNone(fj.fin_ready(epic(), DISCOVERY, "label"))


class IdeeAReady(unittest.TestCase):
    def un(self, e, **ctx):
        return valeurs(fj.calculer_idee_a_ready([e], contexte(**ctx)))

    def test_cree_dans_la_colonne_de_depart_vingt_jours(self):
        r = self.un(epic("2026-01-12", transitions=[("2026-02-01", "s-idee", "s-pret")]))
        self.assertEqual(r["total.p50"], 20)
        self.assertEqual(r["2026-C1.atteints"], 1)

    def test_cree_ailleurs_quinze_jours_pas_vingt_cinq(self):
        e = epic("2026-01-06", etat="s-pret", transitions=[("2026-01-16", "s-brouillon", "s-idee"), ("2026-01-31", "s-idee", "s-pret")])
        self.assertEqual(self.un(e)["total.p50"], 15)

    def test_etiquette_ready_configuree(self):
        e = epic("2026-01-06", etat="s-pret", periodes=[periode("ready", "2026-01-18")],
                 transitions=[("2026-01-21", "s-idee", "s-pret")])
        self.assertEqual(self.un(e, source_ready="label")["total.p50"], 12)
        self.assertEqual(self.un(e, source_ready="colonne")["total.p50"], 15)       # l'autre source : jamais mélangées

    def test_jamais_dans_la_colonne_de_depart(self):
        e = epic("2026-01-06", etat="s-pret", transitions=[("2026-03-10", "s-brouillon", "s-pret")])
        resultat = fj.calculer_idee_a_ready([e], contexte())
        self.assertEqual(resultat["sans_entree"].valeur, 1)
        self.assertEqual(resultat["total.p50"].n, 0)
        self.assertIsNone(resultat["total.p50"].valeur)
        self.assertEqual(resultat["2026-C2.atteints"].valeur, 1)

    def test_cycle_du_jour_de_fin(self):
        e = epic("2026-01-06", etat="s-pret", transitions=[("2026-02-20", "s-brouillon", "s-idee"), ("2026-03-10", "s-idee", "s-pret")])
        r = self.un(e)
        self.assertEqual((r["2026-C1.atteints"], r["2026-C2.atteints"]), (0, 1))

    def test_mediane_et_p85_sur_cinq_epics(self):
        epics = []
        for jours in (10, 20, 30, 40, 50):
            fin = dt.date(2026, 1, 5) + dt.timedelta(days=jours)
            epics.append(epic("2026-01-05", etat="s-pret", transitions=[(fin.isoformat(), "s-idee", "s-pret")]))
        r = fj.calculer_idee_a_ready(epics, contexte())
        self.assertEqual((r["2026-C1.p50"].valeur, r["2026-C1.p50"].n), (30.0, 5))
        self.assertAlmostEqual(r["2026-C1.p85"].valeur, 44.0)
        self.assertEqual(r["total.atteints"].valeur, 5)

    def test_fin_en_fin_de_journee_dans_le_fuseau_d_export(self):
        """23:30 locale le 5 janvier = 04:30 UTC le 6 : le jour d'export est le 5, soit 10 jours depuis le 26 décembre."""
        fin = dt.datetime(2026, 1, 6, 4, 30, tzinfo=UTC)
        e = epic("2025-12-26", etat="s-pret", transitions=[("2026-01-05", "s-idee", "s-pret")])
        e["transitions"] = [(fin, "s-idee", "s-pret")]
        self.assertEqual(self.un(e)["total.p50"], 10)

    def test_aucune_source_ready_ou_mapping_non_valide_rien_n_est_calcule(self):
        e = epic("2026-01-12", transitions=[("2026-02-01", "s-idee", "s-pret")])
        for ctx in ({"source_ready": None}, {"discovery": {**DISCOVERY, "validated": False}}):
            r = fj.calculer_idee_a_ready([e], contexte(**ctx))
            self.assertTrue(r and all(b.genre == "etat" and b.valeur == "not_computed" for b in r.values()), ctx)


class Passages(unittest.TestCase):
    def test_resoumission(self):
        e = epic(periodes=[periode("epic_review", "2026-02-10", "2026-02-20"), periode("epic_review", "2026-03-10")])
        r = valeurs(fj.calculer_passages([e], contexte()))
        self.assertEqual((r["2026-C1.soumissions"], r["2026-C1.resoumissions"]), (1, 0))
        self.assertEqual((r["2026-C2.soumissions"], r["2026-C2.resoumissions"]), (1, 1))
        self.assertEqual((r["repartition.1"], r["repartition.2"], r["repartition.3+"]), (0, 1, 0))

    def test_trois_soumissions_et_plus(self):
        e = epic(periodes=[periode("epic_review", f"2026-0{m}-10", f"2026-0{m}-12") for m in (1, 2, 3, 4)])
        r = valeurs(fj.calculer_passages([e, epic(periodes=[periode("epic_review", "2026-01-10")])], contexte()))
        self.assertEqual((r["repartition.1"], r["repartition.2"], r["repartition.3+"]), (1, 0, 1))

    def test_epic_jamais_soumis_hors_repartition(self):
        r = valeurs(fj.calculer_passages([epic()], contexte()))
        self.assertEqual((r["repartition.1"], r["repartition.2"], r["repartition.3+"]), (0, 0, 0))

    def test_aucune_etiquette_epic_review_declaree(self):
        self.assertIsNone(fj.calculer_passages([epic()], contexte(epic_review=False)))

    def test_aucun_statut_n_est_lu_et_le_mapping_n_est_pas_requis(self):
        e = epic(periodes=[periode("epic_review", "2026-02-10")])
        r = valeurs(fj.calculer_passages([e], contexte(discovery=None)))
        self.assertEqual(r["2026-C1.soumissions"], 1)


class CyclePlanifie(unittest.TestCase):
    def cle(self, *labels):
        e = epic(periodes=[periode("cycle", ajout, cycle=cycle) for ajout, cycle in labels])
        return fj.cycle_planifie(e, CYCLES, FUSEAU)

    def test_decalage_apres_le_demarrage(self):
        p = self.cle(("2026-02-20", "2026-C2"), ("2026-03-10", "2026-C3"))
        self.assertEqual((p["cle"], p["tard"], p["replanifie"], p["decale"]), ("2026-C2", False, False, True))

    def test_replanifie_avant_le_demarrage(self):
        p = self.cle(("2026-02-10", "2026-C2"), ("2026-02-20", "2026-C3"))
        self.assertEqual((p["cle"], p["tard"], p["replanifie"], p["decale"]), ("2026-C3", False, True, False))

    def test_meme_cle_deux_fois_pas_un_decalage(self):
        p = self.cle(("2026-04-20", "2026-C3"), ("2026-04-28", "2026-C3"))
        self.assertEqual((p["cle"], p["decale"], p["replanifie"]), ("2026-C3", False, False))

    def test_planifie_tard(self):
        p = self.cle(("2026-03-04", "2026-C2"))
        self.assertEqual((p["cle"], p["tard"], p["replanifie"], p["decale"]), ("2026-C2", True, False, False))

    def test_planifie_tard_puis_decale(self):
        p = self.cle(("2026-03-04", "2026-C2"), ("2026-03-20", "2026-C3"))
        self.assertEqual((p["cle"], p["tard"], p["decale"]), ("2026-C2", True, True))

    def test_aucune_etiquette_de_cycle(self):
        self.assertIsNone(fj.cycle_planifie(epic(), CYCLES, FUSEAU))

    def test_etiquette_de_cycle_sans_cle_de_cycle(self):
        e = epic(periodes=[periode("cycle", "2026-02-10")])
        self.assertIsNone(fj.cycle_planifie(e, CYCLES, FUSEAU))

    def test_etiquette_presente_des_la_creation(self):
        p = self.cle(("2026-01-02", "2026-C1"))
        self.assertEqual((p["cle"], p["tard"]), ("2026-C1", False))          # posée avant le premier jour de C1

    def test_jour_d_ajout_lu_dans_le_fuseau_d_export(self):
        """Ajout à 23:30 locale le dimanche 1er mars (04:30 UTC le lundi 2) : le jour local est avant le début de C2, donc pas tard."""
        e = epic()
        e["periodes"].append({"role": "cycle", "cycle": "2026-C2", "sens": None,
                              "ajout": dt.datetime(2026, 3, 2, 4, 30, tzinfo=UTC), "retrait": None})
        p = fj.cycle_planifie(e, CYCLES, FUSEAU)
        self.assertEqual((p["cle"], p["tard"]), ("2026-C2", False))


def planifie(cycle_label: str, ajout: str, **kw):
    return epic(periodes=[periode("cycle", ajout, cycle=cycle_label)], **kw)


class Report(unittest.TestCase):
    def calculer(self, epics, **ctx):
        return fj.calculer_report(epics, contexte(**ctx))

    def test_resolu_apres_son_cycle_reporte_avec_ou_sans_etiquette_de_cycle_suivant(self):
        sans = planifie("2026-C2", "2026-02-20", resolu="2026-04-28")
        avec = epic(periodes=[periode("cycle", "2026-02-20", cycle="2026-C2"), periode("cycle", "2026-03-10", cycle="2026-C3")],
                    resolu="2026-04-28")
        r = valeurs(self.calculer([sans, avec]))
        self.assertEqual((r["2026-C2.planifies"], r["2026-C2.reportes"], r["2026-C2.dans_le_cycle"]), (2, 2, 0))

    def test_non_resolu_report_provisoire(self):
        r = valeurs(self.calculer([planifie("2026-C2", "2026-02-20")]))
        self.assertEqual((r["2026-C2.report_provisoire"], r["2026-C2.reportes"], r["2026-C2.dans_le_cycle"]), (1, 0, 0))

    def test_resolu_tard_le_soir_le_dernier_jour(self):
        """23:30 locale le 24 avril, dernier jour de C2 : le 25 en UTC."""
        resolu = dt.datetime(2026, 4, 25, 4, 30, tzinfo=UTC)
        r = valeurs(self.calculer([planifie("2026-C2", "2026-02-20", resolu=resolu)]))
        self.assertEqual((r["2026-C2.dans_le_cycle"], r["2026-C2.reportes"]), (1, 0))

    def test_resolu_avant_la_fenetre_du_cycle_dans_le_cycle_planifie(self):
        r = valeurs(self.calculer([planifie("2026-C2", "2026-02-20", resolu="2026-02-25")]))
        self.assertEqual(r["2026-C2.dans_le_cycle"], 1)

    def test_epic_rejete(self):
        e = planifie("2026-C2", "2026-02-20", resolu="2026-05-04", classe="not_done")
        r = valeurs(self.calculer([e]))
        self.assertEqual(r["2026-C2.rejetes"], 1)
        self.assertEqual((r["2026-C2.reportes"], r["2026-C2.report_provisoire"], r["2026-C2.dans_le_cycle"]), (0, 0, 0))
        self.assertEqual(r["2026-C2.planifies"], 1)
        self.assertEqual(r["2026-C2.decalage_declare_reporte"] + r["2026-C2.decalage_declare_non_reporte"]
                         + r["2026-C2.reporte_sans_decalage_declare"], 0)

    def test_cycle_en_cours(self):
        epics = [planifie("2026-C3", "2026-04-01"), planifie("2026-C3", "2026-04-02", resolu="2026-05-01", classe="not_done")]
        brut = self.calculer(epics, aujourdhui=dt.date(2026, 5, 4))
        self.assertEqual(brut["2026-C3.planifies"].valeur, 2)
        self.assertEqual(brut["2026-C3.rejetes"].valeur, 1)
        for cle in ("dans_le_cycle", "reportes", "report_provisoire", "decalage_declare_reporte"):
            self.assertEqual((brut[f"2026-C3.{cle}"].genre, brut[f"2026-C3.{cle}"].valeur), ("etat", "cycle_in_progress"), cle)

    def test_confirmation_a_la_fin_du_dernier_jour_du_cycle(self):
        e = epic(periodes=[periode("cycle", "2026-02-20", cycle="2026-C2"),
                           periode("confirmation", "2026-03-05", "2026-04-28", sens="taken_in"),
                           periode("confirmation", "2026-04-28", sens="not_taken_in")], resolu="2026-04-10")
        r = valeurs(self.calculer([e]))
        self.assertEqual((r["2026-C2.confirmation.pris"], r["2026-C2.confirmation.non_pris"], r["2026-C2.confirmation.sans"]), (1, 0, 0))
        self.assertEqual(r["2026-C2.confirmation.pris.dans_le_cycle"], 1)
        self.assertEqual(r["2026-C2.confirmation.pris.reportes"], 0)

    def test_sans_etiquette_de_confirmation(self):
        r = valeurs(self.calculer([planifie("2026-C2", "2026-02-20")]))
        self.assertEqual(r["2026-C2.confirmation.sans"], 1)
        self.assertEqual(r["2026-C2.confirmation.sans.report_provisoire"], 1)

    def test_decalage_non_declare(self):
        r = valeurs(self.calculer([planifie("2026-C2", "2026-02-20", resolu="2026-05-04")]))
        self.assertEqual((r["2026-C2.reportes"], r["2026-C2.reporte_sans_decalage_declare"]), (1, 1))

    def test_decalage_declare_termine_a_temps(self):
        e = epic(periodes=[periode("cycle", "2026-02-20", cycle="2026-C2"), periode("cycle", "2026-03-10", cycle="2026-C3")],
                 resolu="2026-04-10")
        r = valeurs(self.calculer([e]))
        self.assertEqual((r["2026-C2.dans_le_cycle"], r["2026-C2.decalage_declare_non_reporte"], r["2026-C2.decalage_declare_reporte"]),
                         (1, 1, 0))

    def test_decalage_declare_et_reporte_provisoire_compris(self):
        e = epic(periodes=[periode("cycle", "2026-02-20", cycle="2026-C2"), periode("cycle", "2026-03-10", cycle="2026-C3")])
        r = valeurs(self.calculer([e]))
        self.assertEqual((r["2026-C2.report_provisoire"], r["2026-C2.decalage_declare_reporte"]), (1, 1))

    def test_replanifie_avant_le_demarrage_livre_dans_le_nouveau_cycle(self):
        e = epic(periodes=[periode("cycle", "2026-02-10", cycle="2026-C2"), periode("cycle", "2026-02-20", cycle="2026-C3")],
                 resolu="2026-05-04")
        r = valeurs(self.calculer([e], aujourdhui=dt.date(2026, 7, 1)))
        self.assertEqual((r["2026-C3.planifies"], r["2026-C3.dans_le_cycle"], r["2026-C3.reportes"]), (1, 1, 0))
        self.assertEqual(r["2026-C3.replanifies_avant_demarrage"], 1)
        self.assertEqual(r["2026-C3.decalage_declare_reporte"] + r["2026-C3.decalage_declare_non_reporte"], 0)
        self.assertEqual(r["2026-C2.planifies"], 0)

    def test_planifie_tard(self):
        e = planifie("2026-C2", "2026-03-04", resolu="2026-04-10")
        r = valeurs(self.calculer([e]))
        self.assertEqual((r["2026-C2.planifies_tard"], r["2026-C2.planifies"], r["2026-C2.dans_le_cycle"]), (1, 1, 1))

    def test_non_planifies_et_rejetes_sans_etiquette(self):
        epics = [epic(), epic(), epic(resolu="2026-05-04", classe="not_done")]
        r = valeurs(self.calculer(epics))
        self.assertEqual((r["non_planifies"], r["non_planifies_rejetes"]), (3, 1))
        self.assertEqual(r["2026-C1.planifies"], 0)

    def test_aucune_etiquette_de_cycle_liee_a_un_cycle(self):
        self.assertIsNone(self.calculer([epic()], cycles_lies=False))

    def test_cycle_a_venir_pas_termine(self):
        brut = self.calculer([planifie("2026-C3", "2026-04-01")], aujourdhui=dt.date(2026, 3, 1))
        self.assertEqual(brut["2026-C3.dans_le_cycle"].valeur, "cycle_in_progress")


class ColonnesEtStatuts(unittest.TestCase):
    def test_compte_par_colonne_dans_l_ordre_declare_et_statut_non_mappe(self):
        epics = [epic(etat="s-idee"), epic(etat="S-CADRAGE"), epic(etat="s-revue")] + [epic(etat="s-inconnu") for _ in range(3)]
        brut = fj.calculer_colonnes(epics, contexte())
        self.assertEqual(list(brut), ["colonne.Idee", "colonne.Revue", "colonne.Pret", "colonne.Fait", "statut_non_mappe"])
        self.assertEqual(valeurs(brut), {"colonne.Idee": 2, "colonne.Revue": 1, "colonne.Pret": 0, "colonne.Fait": 0, "statut_non_mappe": 3})

    def test_mapping_non_valide_non_calcule(self):
        brut = fj.calculer_colonnes([epic()], contexte(discovery={**DISCOVERY, "validated": False}))
        self.assertTrue(all(b.genre == "etat" and b.valeur == "not_computed" for b in brut.values()))

    def test_compte_par_statut_jira_sans_mapping(self):
        epics = [epic(etat="s-idee"), epic(etat="s-idee"), epic(etat="s-revue")]
        self.assertEqual(valeurs(fj.calculer_statuts(epics, contexte(discovery=None))), {"statut.s-idee": 2, "statut.s-revue": 1})


class Age(unittest.TestCase):
    AUJOURDHUI = dt.date(2026, 3, 31)

    def calculer(self, epics, **ctx):
        return fj.calculer_age(epics, contexte(aujourdhui=self.AUJOURDHUI, **ctx))

    def test_age_et_age_dans_la_colonne(self):
        e = epic("2026-03-01", etat="s-revue", transitions=[("2026-03-11", "s-idee", "s-revue")])
        brut = self.calculer([e])
        self.assertEqual(valeurs(brut)["en_cours"], 1)
        self.assertEqual((brut["age.p50"].valeur, brut["age_colonne.p50"].valeur), (30.0, 20.0))

    def test_cree_dans_la_colonne_courante_age_depuis_la_creation(self):
        e = epic("2026-03-01", etat="s-idee")
        brut = self.calculer([e])
        self.assertEqual((brut["age.p50"].valeur, brut["age_colonne.p50"].valeur), (30.0, 30.0))

    def test_derniere_entree_dans_la_colonne_courante(self):
        e = epic("2026-03-01", etat="s-revue", transitions=[("2026-03-05", "s-idee", "s-revue"), ("2026-03-08", "s-revue", "s-idee"),
                                                           ("2026-03-21", "s-idee", "s-revue")])
        self.assertEqual(self.calculer([e])["age_colonne.p50"].valeur, 10.0)

    def test_epic_sans_depart(self):
        e = epic("2026-03-01", etat="s-revue", transitions=[("2026-03-11", "s-brouillon", "s-revue")])
        brut = self.calculer([e])
        self.assertEqual(brut["sans_entree"].valeur, 1)
        self.assertEqual(brut["age.p50"].n, 0)
        self.assertEqual(brut["age_colonne.p50"].valeur, 20.0)

    def test_colonne_non_active_exclue(self):
        brut = self.calculer([epic(etat="s-pret"), epic(etat="s-fait")])
        self.assertEqual(brut["en_cours"].valeur, 0)

    def test_plus_vieux_que_la_reference(self):
        epics = [epic("2026-02-01", etat="s-revue", transitions=[("2026-02-02", "s-idee", "s-revue")]) for _ in range(6)]
        epics.append(epic("2026-03-25", etat="s-idee"))
        brut = self.calculer(epics, reference_p85=40.0)
        self.assertEqual(brut["plus_vieux_que_reference"].valeur, 6)

    def test_sans_reference(self):
        brut = self.calculer([epic("2026-02-01")], reference_p85=None)
        self.assertEqual((brut["plus_vieux_que_reference"].genre, brut["plus_vieux_que_reference"].valeur), ("etat", "no_reference"))

    def test_mapping_non_valide_ou_sans_colonnes_actives(self):
        for discovery in ({**DISCOVERY, "validated": False}, {**DISCOVERY, "active_columns": []}):
            brut = self.calculer([epic()], discovery=discovery)
            self.assertTrue(all(b.genre == "etat" and b.valeur == "not_computed" for b in brut.values()))


if __name__ == "__main__":
    unittest.main()
