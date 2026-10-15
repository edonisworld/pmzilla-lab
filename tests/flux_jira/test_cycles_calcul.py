"""Calcul des cycles (R-58, tâche 9.3) : fonctions pures sur des éléments en mémoire, sans base ni fichier.

    uv run --with pyyaml --with numpy python -m unittest discover -s tests/flux_jira -v

Specs jira-flow-cycles (flux des cycles, up-merge hors du flux, « sans patch », provision, versions non mappées, drapeau de
version de base), jira-flow-labels (deux étiquettes d'up-merge, soumissions, passages et rejets, délai) et design D6, D7, D19.
Données inventées : clés de cycle neutres, versions et étiquettes fictives, aucune clé de ticket en sortie.
"""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent.parent / "tools"))
import flux_config as cfg  # noqa: E402
import flux_jira as fj  # noqa: E402
from messages import Messages  # noqa: E402
from flux_jira_messages import CATALOGS  # noqa: E402

UTC = dt.timezone.utc
PLUS_2H = ZoneInfo("Etc/GMT-2")        # UTC+2 toute l'année
D = dt.date
CYCLES = [cfg.Cycle("2026-C1", "ver-alpha", D(2026, 1, 5), D(2026, 2, 27), 0.1, False),
          cfg.Cycle("2026-C2", "ver-beta", D(2026, 3, 2), D(2026, 4, 24), None, False)]
PATCHES = {"2026-Q1": ["patch-alpha"], "2026-Q2": ["patch-beta"]}
ETIQUETTES = {"up_merge": {"prefix": "UM-", "labels": ["UM-legal", "UM-hotfix"]},
              "cycle": {"prefix": "CY-", "labels": ["CY-sujet"]},
              "epic_review": {"prefix": "ER-", "labels": ["ER-revue"]}}
COLONNES = {"A cadrer": ["Draft"], "Revue": ["In Review"], "Validé": ["Approved"], "Refusé": ["Rejected idea"]}
DISCOVERY = {"columns": COLONNES, "start_column": "A cadrer", "review_passed_columns": ["Validé"],
             "validated_on": D(2026, 9, 1), "validated": True}
DISCOVERY_NON_VALIDE = {**DISCOVERY, "validated_on": None, "validated": False}
OUVERT = None


def instant(jour: int, heure: int = 12, mois: int = 2, annee: int = 2026) -> dt.datetime:
    return dt.datetime(annee, mois, jour, heure, 0, tzinfo=UTC)


def element(resolu: dt.date | None = None, versions=(), labels=(), type_="Story", projet="PROJ", motif="Done", transitions=(),
            etat="Done") -> dict:
    ajout = instant(1, mois=1)
    return {"cle": "PROJ-0", "type": type_, "projet": projet, "etat": etat, "resolu": resolu, "motif": motif,
            "labels": [(nom, ajout, retire) for nom, retire in ((l, None) if isinstance(l, str) else l for l in labels)],
            "versions": [(nom, ajout, retire) for nom, retire in ((v, None) if isinstance(v, str) else v for v in versions)],
            "transitions": list(transitions)}


def calcul(elements, discovery=DISCOVERY, fuseau=PLUS_2H, etiquettes=ETIQUETTES, cycles=CYCLES, exclusions=(set(), set())):
    return fj.calculer_cycles(elements, cycles, PATCHES, etiquettes, discovery, exclusions, {"rejected"}, fuseau)


def cycle(r, cle):
    return next(c for c in r["cycles"] if c["cle"] == cle)


def livres(n, cycle_version="ver-alpha", jour=D(2026, 2, 10)):
    return [element(resolu=jour, versions=[cycle_version]) for _ in range(n)]


def up_merge(n, version="patch-alpha", label="UM-legal", jour=D(2026, 2, 12)):
    return [element(resolu=jour, versions=[version] if version else [], labels=[label]) for _ in range(n)]


class FluxDuCycle(unittest.TestCase):
    def test_up_merge_hors_du_flux_du_cycle(self):
        """Scénario « Up-merge out of the cycle flow » : 20 livrés + 5 up-merge -> livrés 20, part 5 sur 25, patch 5."""
        r = calcul(livres(20) + up_merge(5))
        c = cycle(r, "2026-C1")
        self.assertEqual(c["livres"], 20)
        self.assertEqual(c["vises"], 20)
        self.assertEqual(c["up_merge"]["resolus"], 5)
        self.assertEqual(c["up_merge"]["part"], 5 / 25)
        self.assertEqual(c["up_merge"]["par_patch"], {"2026-Q1": 5})
        self.assertEqual(c["up_merge"]["sans_patch"], 0)
        self.assertEqual(cycle(r, "2026-C2")["livres"], 0)

    def test_up_merge_sans_patch_compte_dans_la_part_sur_une_ligne_a_part(self):
        """Scénario « Up-merge item without patch » : 20 livrés, 4 sous un patch, 1 sans patch -> part 5 sur 25."""
        r = calcul(livres(20) + up_merge(4) + up_merge(1, version=None))
        up = cycle(r, "2026-C1")["up_merge"]
        self.assertEqual(up["resolus"], 5)
        self.assertEqual(up["part"], 5 / 25)
        self.assertEqual(up["par_patch"], {"2026-Q1": 4})
        self.assertEqual(up["sans_patch"], 1)
        self.assertEqual(cycle(r, "2026-C1")["livres"], 20)

    def test_up_merge_avec_version_non_mappee_a_un_patch_est_sans_patch(self):
        """Une version qui n'est ni un cycle ni un patch ne rattache pas l'up-merge à un patch (jamais par les dates)."""
        r = calcul(livres(2) + up_merge(1, version="ver-inconnue"))
        up = cycle(r, "2026-C1")["up_merge"]
        self.assertEqual((up["sans_patch"], up["par_patch"], up["resolus"]), (1, {}, 1))

    def test_aucun_sans_patch_donne_zero(self):
        """Scénario « None without patch »."""
        r = calcul(livres(3) + up_merge(2))
        self.assertEqual(cycle(r, "2026-C1")["up_merge"]["sans_patch"], 0)
        texte = "\n".join(fj.lignes_cycles({"serie": "s", "date": "2026-05-04", **r}, Messages(CATALOGS, "fr")))
        self.assertIn("- sans patch : 0", texte)

    def test_deux_etiquettes_comptees_a_part_hors_de_la_part(self):
        """Exigence « Exactly one up-merge label » : l'élément à deux étiquettes n'est ni dans la part ni dans le flux."""
        deux = element(resolu=D(2026, 2, 11), versions=["patch-alpha"], labels=["UM-legal", "UM-hotfix"])
        r = calcul(livres(20) + up_merge(5) + [deux])
        c = cycle(r, "2026-C1")
        self.assertEqual(c["up_merge"]["deux_etiquettes"], 1)
        self.assertEqual(r["deux_etiquettes"], 1)
        self.assertEqual((c["up_merge"]["resolus"], c["up_merge"]["part"], c["livres"]), (5, 5 / 25, 20))
        self.assertEqual(c["up_merge"]["par_patch"], {"2026-Q1": 5})

    def test_deux_etiquettes_par_cycle(self):
        deux_c2 = element(resolu=D(2026, 3, 10), labels=["UM-legal", "UM-hotfix"])
        r = calcul([deux_c2])
        self.assertEqual([cycle(r, k)["up_merge"]["deux_etiquettes"] for k in ("2026-C1", "2026-C2")], [0, 1])

    def test_provision_configuree_et_absente(self):
        """Scénario « Provision missing » : la part est écrite, la provision dit qu'elle n'est pas configurée."""
        r = calcul(livres(2, "ver-beta", D(2026, 3, 10)) + up_merge(1, jour=D(2026, 3, 11), version="patch-beta"))
        self.assertEqual(cycle(r, "2026-C1")["up_merge"]["provision"], 0.1)
        self.assertIsNone(cycle(r, "2026-C2")["up_merge"]["provision"])
        resultat = {"serie": "s", "date": "2026-05-04", **r}
        fr = "\n".join(fj.lignes_cycles(resultat, Messages(CATALOGS, "fr")))
        en = "\n".join(fj.lignes_cycles(resultat, Messages(CATALOGS, "en")))
        self.assertIn("Part d'up-merge : 1 sur 3 (33 %) ; provision configurée : non configurée", fr)
        self.assertIn("provision configurée : 10 %", fr)
        self.assertIn("Up-merge share: 1 out of 3 (33%); configured provision: not configured", en)

    def test_part_sans_element_n_est_pas_un_chiffre(self):
        self.assertIsNone(cycle(calcul([]), "2026-C1")["up_merge"]["part"])

    def test_cycle_vise_vient_de_la_version_pas_de_l_etiquette(self):
        """Exigence « Targeted cycle from fix version » : étiquette de cycle sans version mappée -> dans aucun flux, comptée une fois."""
        sans_version = element(resolu=D(2026, 2, 10), labels=["CY-sujet"])
        autre_version = element(resolu=D(2026, 2, 10), labels=["CY-sujet"], versions=["ver-inconnue"])
        r = calcul([sans_version, autre_version])
        self.assertEqual([c["vises"] + c["livres"] for c in r["cycles"]], [0, 0])
        self.assertEqual(r["etiquette_cycle_sans_cycle"], 2)
        avec = calcul([element(resolu=D(2026, 2, 10), labels=["CY-sujet"], versions=["ver-alpha"])])
        self.assertEqual(avec["etiquette_cycle_sans_cycle"], 0)
        self.assertEqual(cycle(avec, "2026-C1")["vises"], 1)

    def test_versions_non_mappees_comptees_sans_nom(self):
        """Exigence « Version numbers never in outputs » : nombre de versions et de tickets, aucun nom."""
        r = calcul([element(versions=["ver-zz1"]), element(versions=["ver-zz1", "ver-zz2"]), element(versions=["ver-alpha"]),
                    element(versions=["patch-alpha"])])
        self.assertEqual(r["versions_non_mappees"], {"versions": 2, "tickets": 2})
        sortie = json.dumps(r) + "\n".join(fj.lignes_cycles({"serie": "s", "date": "2026-05-04", **r}, Messages(CATALOGS, "fr")))
        for nom in ("ver-zz1", "ver-zz2", "ver-alpha", "patch-alpha", "UM-legal", "CY-sujet", "PROJ-0"):
            self.assertNotIn(nom, sortie)

    def test_livre_dans_la_fenetre_seulement(self):
        hors = [element(resolu=D(2026, 3, 2), versions=["ver-alpha"]), element(resolu=D(2025, 12, 31), versions=["ver-alpha"]),
                element(resolu=None, versions=["ver-alpha"], etat="In Progress")]
        dedans = [element(resolu=D(2026, 1, 5), versions=["ver-alpha"]), element(resolu=D(2026, 2, 27), versions=["ver-alpha"])]
        c = cycle(calcul(hors + dedans), "2026-C1")
        self.assertEqual((c["vises"], c["livres"]), (5, 2))

    def test_motif_de_resolution_exclu_n_est_pas_livre(self):
        c = cycle(calcul([element(resolu=D(2026, 2, 10), versions=["ver-alpha"], motif="Rejected"),
                          element(resolu=D(2026, 2, 10), versions=["ver-alpha"])]), "2026-C1")
        self.assertEqual((c["vises"], c["livres"]), (2, 1))

    def test_reporte_sur_un_cycle_ulterieur(self):
        deplace = element(versions=[("ver-alpha", dt.datetime(2026, 2, 20, tzinfo=UTC)), "ver-beta"], etat="In Progress")
        r = calcul([deplace])
        self.assertEqual((cycle(r, "2026-C1")["reportes"], cycle(r, "2026-C1")["vises"]), (1, 0))
        self.assertEqual((cycle(r, "2026-C2")["reportes"], cycle(r, "2026-C2")["vises"]), (0, 1))

    def test_type_portefeuille_et_projet_exclu_hors_du_flux(self):
        epic = element(resolu=D(2026, 2, 10), versions=["ver-alpha"], type_="Epic")
        exclu = element(resolu=D(2026, 2, 10), versions=["ver-alpha"], projet="EXC")
        c = cycle(calcul(livres(2) + [epic, exclu], exclusions=({"epic"}, {"EXC"})), "2026-C1")
        self.assertEqual(c["livres"], 2)

    def test_drapeau_version_de_base_dans_l_entete_seulement_pour_le_cycle_marque(self):
        marques = [cfg.Cycle("2026-C1", "ver-alpha", D(2026, 1, 5), D(2026, 2, 27), None, True), CYCLES[1]]
        r = calcul(livres(2), cycles=marques)
        self.assertTrue(cycle(r, "2026-C1")["version_de_base"])
        resultat = {"serie": "s", "date": "2026-05-04", **r}
        fr = "\n".join(fj.lignes_cycles(resultat, Messages(CATALOGS, "fr")))
        en = "\n".join(fj.lignes_cycles(resultat, Messages(CATALOGS, "en")))
        self.assertIn("## 2026-C1 (version de base)", fr)
        self.assertIn("## 2026-C1 (base version)", en)
        self.assertIn("## 2026-C2\n", fr)
        self.assertEqual(cycle(r, "2026-C1")["livres"], 2)                  # chiffres calculés comme ceux des autres cycles
        sans = "\n".join(fj.lignes_cycles({"serie": "s", "date": "x", **calcul(livres(2))}, Messages(CATALOGS, "fr")))
        self.assertNotIn("version de base", sans)

    def test_sans_etiquette_d_up_merge_declaree_rien_n_est_compte_a_tort(self):
        r = calcul(livres(2) + up_merge(3), etiquettes=None)
        self.assertEqual(cycle(r, "2026-C1")["up_merge"]["resolus"], 0)
        self.assertFalse(r["etiquette_up_merge_declaree"])
        fr = "\n".join(fj.lignes_cycles({"serie": "s", "date": "x", **r}, Messages(CATALOGS, "fr")))
        self.assertIn("part d'up-merge non calculée", fr)


def retrait_et_statuts(retrait, transitions):
    """Un épic dont l'étiquette Epic Review est posée le 1er février et retirée à `retrait`."""
    return element(labels=[("ER-revue", retrait)], transitions=transitions, type_="Epic", etat="In Review")


def ajout_a(jour, retrait=None, heure=10, mois=2):
    e = element(type_="Epic")
    e["labels"] = [("ER-revue", instant(jour, heure, mois), retrait)]
    return e


class EpicReview(unittest.TestCase):
    def test_non_valide_soumissions_seulement(self):
        """Scénario « Mapping not validated » : 3 ajouts et 2 retraits -> 3 soumissions, la phrase D19, ni passage ni rejet."""
        a = ajout_a(3, retrait=instant(5))
        b = ajout_a(4, retrait=instant(6))
        c = ajout_a(9)
        r = calcul([a, b, c], discovery=DISCOVERY_NON_VALIDE)
        revue = cycle(r, "2026-C1")["epic_review"]
        self.assertEqual(revue, {"soumissions": 3})
        self.assertFalse(r["discovery_valide"])
        fr = "\n".join(fj.lignes_cycles({"serie": "s", "date": "x", **r}, Messages(CATALOGS, "fr")))
        en = "\n".join(fj.lignes_cycles({"serie": "s", "date": "x", **r}, Messages(CATALOGS, "en")))
        self.assertIn("correspondance du Discovery Workflow non validée : soumissions seulement", fr)
        self.assertIn("Discovery Workflow mapping not validated: submissions only", en)
        for interdit in ("passages :", "rejets :", "statut non mappé :", "délai jusqu'à"):
            self.assertNotIn(interdit, fr)
        for interdit in ("passes:", "rejections:", "delay to Epic Review"):
            self.assertNotIn(interdit, en)

    def test_sans_bloc_discovery_comme_non_valide(self):
        r = calcul([ajout_a(3)], discovery=None)
        self.assertEqual(cycle(r, "2026-C1")["epic_review"], {"soumissions": 1})

    def test_chaque_ajout_est_une_soumission(self):
        e = ajout_a(3, retrait=instant(5))
        e["labels"].append(("ER-revue", instant(10), None))
        self.assertEqual(cycle(calcul([e], discovery=None), "2026-C1")["epic_review"]["soumissions"], 2)

    def test_soumission_comptee_dans_le_cycle_de_son_ajout(self):
        r = calcul([ajout_a(10, mois=3)])
        self.assertEqual([cycle(r, k)["epic_review"]["soumissions"] for k in ("2026-C1", "2026-C2")], [0, 1])

    def test_passage_et_rejet(self):
        """Scénario « Pass and rejection »."""
        passe = ajout_a(3, retrait=instant(5, 10))
        passe["transitions"] = [(instant(5, 11), "In Review", "Approved")]
        rejete = ajout_a(3, retrait=instant(6, 10))
        rejete["transitions"] = [(instant(6, 11), "In Review", "Rejected idea")]
        revue = cycle(calcul([passe, rejete]), "2026-C1")["epic_review"]
        self.assertEqual((revue["soumissions"], revue["passages"], revue["rejets"], revue["statut_non_mappe"]), (2, 1, 1, 0))

    def test_statut_non_mappe(self):
        """Scénario « Status not mapped » : ni passage ni rejet."""
        e = ajout_a(3, retrait=instant(5, 10))
        e["transitions"] = [(instant(5, 11), "In Review", "On Hold")]
        revue = cycle(calcul([e]), "2026-C1")["epic_review"]
        self.assertEqual((revue["passages"], revue["rejets"], revue["statut_non_mappe"]), (0, 0, 1))

    def test_un_retrait_seul_n_est_pas_un_passage(self):
        """Sans aucune transition ni statut mappé, le retrait n'est rien d'autre que « statut non mappé »."""
        e = ajout_a(3, retrait=instant(5, 10))
        e["etat"] = "On Hold"
        revue = cycle(calcul([e]), "2026-C1")["epic_review"]
        self.assertEqual((revue["passages"], revue["rejets"], revue["statut_non_mappe"]), (0, 0, 1))

    def test_statut_courant_si_aucune_transition_et_mappe(self):
        e = ajout_a(3, retrait=instant(5, 10))
        e["etat"] = "Approved"
        self.assertEqual(cycle(calcul([e]), "2026-C1")["epic_review"]["passages"], 1)

    def test_statut_initial_si_toutes_les_transitions_viennent_apres_le_jour_du_retrait(self):
        """Le statut du jour du retrait est le départ de la première transition : « Draft », colonne mappée qui n'est pas une
        revue passée, donc un rejet (jamais un passage, jamais « statut non mappé »)."""
        e = ajout_a(3, retrait=instant(5, 10))
        e["transitions"] = [(instant(9, 10), "Draft", "Approved")]
        revue = cycle(calcul([e]), "2026-C1")["epic_review"]
        self.assertEqual((revue["passages"], revue["rejets"], revue["statut_non_mappe"]), (0, 1, 0))

    def scenario_minuit_local(self):
        """Fuseau +2 h. Étiquette retirée à 20:00 local (18:00 UTC), épic passé en colonne « revue passée » à 21:00 local (19:00 UTC),
        puis dans une autre colonne mappée à 01:00 local le lendemain (23:00 UTC le jour du retrait)."""
        e = ajout_a(3, retrait=dt.datetime(2026, 2, 5, 18, 0, tzinfo=UTC))
        e["transitions"] = [(dt.datetime(2026, 2, 5, 19, 0, tzinfo=UTC), "In Review", "Approved"),
                            (dt.datetime(2026, 2, 5, 23, 0, tzinfo=UTC), "Approved", "Rejected idea")]
        return e

    def test_jour_du_retrait_lu_dans_le_fuseau_d_export_un_passage(self):
        """Scénario « Removal day in the export time zone » : le statut à la fin du jour LOCAL est celui de la colonne passée."""
        revue = cycle(calcul([self.scenario_minuit_local()], fuseau=PLUS_2H), "2026-C1")["epic_review"]
        self.assertEqual((revue["passages"], revue["rejets"]), (1, 0))

    def test_la_lecture_en_utc_aurait_donne_un_rejet(self):
        """Contre-épreuve : la même fixture lue en UTC donne le rejet que le scénario interdit (le test précédent discrimine)."""
        revue = cycle(calcul([self.scenario_minuit_local()], fuseau=ZoneInfo("UTC")), "2026-C1")["epic_review"]
        self.assertEqual((revue["passages"], revue["rejets"]), (0, 1))

    def test_le_cycle_du_retrait_est_celui_du_jour_local(self):
        """Un retrait à 23:30 UTC le dernier jour d'un cycle (vendredi 27 février) est déjà le samedi 28 en local (+2 h) : hors fenêtre."""
        e = ajout_a(3, retrait=dt.datetime(2026, 2, 27, 23, 30, tzinfo=UTC))
        e["transitions"] = [(dt.datetime(2026, 2, 27, 20, 0, tzinfo=UTC), "In Review", "Approved")]
        r = calcul([e], fuseau=PLUS_2H)
        self.assertEqual(cycle(r, "2026-C1")["epic_review"]["passages"], 0)
        self.assertEqual(cycle(calcul([e], fuseau=ZoneInfo("UTC")), "2026-C1")["epic_review"]["passages"], 1)

    def test_delai_jusqu_a_l_epic_review(self):
        """Scénario « Mapping validated » : entrée dans la colonne de départ dix jours avant le premier ajout."""
        e = ajout_a(13, heure=10)
        e["transitions"] = [(instant(3, 10), "New", "Draft")]
        d = cycle(calcul([e]), "2026-C1")["epic_review"]["delai"]
        self.assertEqual((d["n"], d["p50"]), (1, 10.0))

    def test_delai_depuis_la_premiere_entree_et_le_premier_ajout(self):
        e = ajout_a(13, heure=10)
        e["labels"].append(("ER-revue", instant(20), None))
        e["transitions"] = [(instant(3, 10), "New", "Draft"), (instant(8, 10), "In Review", "Draft")]
        self.assertEqual(cycle(calcul([e]), "2026-C1")["epic_review"]["delai"]["p50"], 10.0)

    def test_delai_sans_entree_dans_la_colonne_de_depart_compte_a_part(self):
        e = ajout_a(13)
        e["transitions"] = [(instant(3, 10), "New", "In Review")]
        revue = cycle(calcul([e]), "2026-C1")["epic_review"]
        self.assertEqual((revue["delai"]["n"], revue["sans_depart"]), (0, 1))

    def test_delai_non_calcule_sans_mapping_valide(self):
        """Scénario « Mapping not validated » (délai) : aucun délai, ni création ni étiquette de cycle en remplacement."""
        e = ajout_a(13)
        e["transitions"] = [(instant(3, 10), "New", "Draft")]
        r = calcul([e], discovery=DISCOVERY_NON_VALIDE)
        self.assertNotIn("delai", cycle(r, "2026-C1")["epic_review"])
        fr = "\n".join(fj.lignes_cycles({"serie": "s", "date": "x", **r}, Messages(CATALOGS, "fr")))
        self.assertNotIn("délai", fr)

    def test_section_epic_review_sans_epic_ni_equipe_ni_personne(self):
        e = ajout_a(3, retrait=instant(5, 10))
        e["transitions"] = [(instant(5, 11), "In Review", "Approved")]
        r = calcul([e])
        sortie = json.dumps(r) + "\n".join(fj.lignes_cycles({"serie": "s", "date": "x", **r}, Messages(CATALOGS, "en")))
        for nom in ("PROJ-0", "Approved", "In Review", "ER-revue", "Validé"):
            self.assertNotIn(nom, sortie)
        self.assertIn("submissions: 1; passes: 1; rejections: 0; status not mapped: 0", sortie)


if __name__ == "__main__":
    unittest.main()
