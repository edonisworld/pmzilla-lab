"""
Tests de la fonction de service du rapport, `report_data` de tools/story_quality_data.py (change story-quality-audit, tâche 3.23, design D15,
M1 (a), M4 révisé en (b) le 2026-10-20 : le dénominateur d'une part est le nombre d'audités). Le masquage complémentaire et le masquage
secondaire de D18 sont dans les vues (migration 0016, tests/db/test_quality_masking.py) : la fonction ne les recalcule pas au plancher ;
un seuil relevé refait les deux à son niveau (revue 4.1, E4). Aucune base : les lignes des trois vues sont données par des fixtures (ce que rendrait un lecteur des vues).

Les cellules suivent le schéma de cellule masquée de mothra-slices D3 : {"state": "value", "value": n} ou {"state": "masked",
"threshold": T} sans propriété `value`. Les équipes « Zzalpha », « Zzbeta » et « Zzgamma » sont des noms distinctifs inventés.
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_quality_data as data  # noqa: E402
from aide_story_quality import SOCLE  # noqa: E402

GRILLE = data.effective_grid(SOCLE, None, "en")
ALPHA, BETA, GAMMA = "Equipe Zzalpha", "Equipe Zzbeta", "Equipe Zzgamma"


def ligne_equipe(equipe, genre, code, lien, audites, satisfaits, non_satisfaits, sans_objet, indetermines, origine="core"):
    """Ligne de quality_by_team : None pour une cellule que la vue masque."""
    return {"team": equipe, "item_kind": genre, "criterion_code": code, "origin": origine, "link": lien, "audited": audites, "met": satisfaits,
            "not_met": non_satisfaits, "not_applicable": sans_objet, "undetermined": indetermines}


def ligne_produit(genre, code, lien, audites, satisfaits, non_satisfaits, sans_objet, indetermines, origine="core"):
    return {"item_kind": genre, "criterion_code": code, "origin": origine, "link": lien, "audited": audites, "met": satisfaits,
            "not_met": non_satisfaits, "not_applicable": sans_objet, "undetermined": indetermines}


def couverture(equipe, genre, collectes, audites, vides, un_seul_po=False):
    return {"team": equipe, "item_kind": genre, "collected": collectes, "audited": audites, "empty_acceptance_criteria": vides,
            "single_po": un_seul_po}


def valeur(n):
    return {"state": "value", "value": n}


def masquee(seuil=5):
    return {"state": "masked", "threshold": seuil}


def part(numerateur, denominateur):
    return {"state": "value", "numerator": valeur(numerateur), "denominator": valeur(denominateur)}   # deux cellules D3, jamais un nombre nu


# Deux équipes. Alpha : story-un 20 audités dont 5 sans objet, 9 non satisfaits (9/20, récurrent au seuil 0,45) ; story-trois 20 audités dont
# 5 sans objet, 2 non satisfaits masqués. Beta : story-un petit (cellules masquées).
VUE_EQUIPE = [
    ligne_equipe(ALPHA, "story", "story-un", "ticket_template", 20, 6, 9, 5, None),
    ligne_equipe(ALPHA, "story", "story-trois", "definition_of_ready", 20, 13, None, 5, None),
    ligne_equipe(ALPHA, "epic", "epic-un", "discovery_workflow_step", 12, 9, None, None, None),
    ligne_equipe(BETA, "story", "story-un", "ticket_template", 30, 8, 17, 5, None),
    ligne_equipe(BETA, "story", "story-trois", "definition_of_ready", None, None, None, None, None),
]
VUE_COUVERTURE = [
    couverture(BETA, "story", 41, 30, 7),
    couverture(ALPHA, "story", 25, 20, None, un_seul_po=True),
    couverture(ALPHA, "epic", None, None, None, un_seul_po=True),
]
VUE_PRODUIT = [
    ligne_produit("story", "story-un", "ticket_template", 50, 14, 26, 10, None),
    ligne_produit("story", "story-trois", "definition_of_ready", 25, 13, None, 10, None),
]


def donnees(equipes=None, couv=None, produit=None, **options):
    options = {"threshold": 0.45, "language": "en", **options}
    return data.report_data(copy.deepcopy(VUE_EQUIPE if equipes is None else equipes),
                            copy.deepcopy(VUE_COUVERTURE if couv is None else couv),
                            copy.deepcopy(VUE_PRODUIT if produit is None else produit), GRILLE, **options)


def critere(resultat, equipe, genre, code):
    section = next(e for e in resultat["teams"] if e["team"] == equipe)
    return next(c for c in section["criteria"][genre] if c["code"] == code)


class Structure(unittest.TestCase):
    def test_le_contrat_et_son_en_tete(self):
        r = donnees()
        self.assertEqual((r["contract"], r["contract_version"]), ("story_quality_report", 1))
        self.assertEqual(r["notice"], {"code": "team_results_notice", "text": "Team results: never a person's evaluation, never a ranking"})
        self.assertEqual(r["grid"], {"core_version": 3, "overlay_version": None, "disabled_codes": []})

    def test_les_versions_de_la_grille_et_les_codes_desactives_sans_raison(self):
        r = donnees(disabled=["story-deux"])
        self.assertEqual(r["grid"]["disabled_codes"], ["story-deux"])
        grille = data.effective_grid(SOCLE, {"identifier": "zzidentifiant-surcouche", "version": 4, "criteria": {}}, "en")
        r = data.report_data([], [], [], grille, threshold=0.5, language="en", disabled=["story-deux"])
        self.assertEqual(r["grid"], {"core_version": 3, "overlay_version": 4, "disabled_codes": ["story-deux"]})
        self.assertNotIn("zzidentifiant", json.dumps(r))

    def test_les_equipes_sont_dans_l_ordre_des_noms(self):
        self.assertEqual([e["team"] for e in donnees()["teams"]], [ALPHA, BETA])

    def test_la_langue_donne_les_libelles_et_les_codes_ne_changent_pas(self):
        en, fr = donnees(language="en"), donnees(language="fr")
        self.assertEqual(critere(en, ALPHA, "story", "story-un")["label"], "Label story-un")
        self.assertEqual(critere(fr, ALPHA, "story", "story-un")["label"], "Libellé story-un")
        self.assertEqual(fr["notice"]["text"], "Résultats d'équipe : jamais l'évaluation d'une personne, jamais un classement")
        self.assertEqual(critere(fr, ALPHA, "story", "story-un")["link"], "ticket_template")
        self.assertEqual(fr["notice"]["code"], en["notice"]["code"])

    def test_un_code_inconnu_de_la_grille_garde_son_code_comme_libelle(self):
        r = donnees(equipes=[ligne_equipe(ALPHA, "story", "orga-inconnu", "refinement", 20, 10, 5, 5, None, "organisation_rule")])
        c = critere(r, ALPHA, "story", "orga-inconnu")
        self.assertEqual((c["label"], c["origin"]), ("orga-inconnu", "organisation_rule"))


class CellulesEtParts(unittest.TestCase):
    def test_chaque_compte_est_une_cellule_structuree(self):
        c = critere(donnees(), ALPHA, "story", "story-un")
        self.assertEqual(c["counts"], {"met": valeur(6), "not_met": valeur(9), "not_applicable": valeur(5), "undetermined": masquee()})

    def test_une_cellule_masquee_n_a_pas_de_propriete_value(self):
        c = critere(donnees(), ALPHA, "story", "story-un")["counts"]["undetermined"]
        self.assertEqual(set(c), {"state", "threshold"})

    def test_denominateur_tous_les_audites_sans_objet_compris(self):
        c = critere(donnees(), ALPHA, "story", "story-un")
        self.assertEqual(c["share_not_met"], part(9, 20))
        self.assertEqual(c["share_met"], part(6, 20))

    def test_une_part_dont_le_numerateur_est_masque_est_masquee(self):
        c = critere(donnees(), ALPHA, "story", "story-trois")
        self.assertEqual(c["share_not_met"], masquee())
        self.assertEqual(c["share_met"], part(13, 20))

    def test_les_sans_objet_masques_ne_masquent_plus_la_part(self):
        c = critere(donnees(), ALPHA, "epic", "epic-un")
        self.assertEqual(c["share_met"], part(9, 12))          # M4 (b) : le dénominateur ne dépend plus du compte « sans objet »
        self.assertEqual(c["share_not_met"], masquee())

    def test_un_denominateur_masque_masque_la_part(self):
        r = donnees(equipes=[ligne_equipe(ALPHA, "story", "story-un", "ticket_template", None, None, None, None, None)])
        self.assertEqual(critere(r, ALPHA, "story", "story-un")["share_not_met"], masquee())
        r = donnees(equipes=[ligne_equipe(ALPHA, "story", "story-un", "ticket_template", 9, 9, None, None, None)], min_cell=10)
        self.assertEqual(critere(r, ALPHA, "story", "story-un")["share_met"], masquee(10))

    def test_aucune_valeur_n_est_estimee_pour_une_cellule_masquee(self):
        texte = json.dumps(donnees()["teams"][1]["criteria"]["story"][1])
        self.assertNotIn('"value": null', texte)
        self.assertNotIn("null", texte.replace('"overlay_version": null', ""))

    def test_un_seuil_releve_masque_les_valeurs_qui_passent_sous_lui(self):
        c = critere(donnees(min_cell=10), ALPHA, "story", "story-un")
        self.assertEqual(c["counts"]["not_applicable"], masquee(10))        # 5 passe sous 10
        self.assertNotIn("audited", c["counts"])
        self.assertEqual(c["share_not_met"], masquee(10))

    # Revue 4.1, E4 : la vue fait le masquage complémentaire au plancher de 5 ; un seuil relevé le refait à son niveau, sinon une cellule
    # masquée entre 5 et le seuil se retrouverait par différence avec `audited`.
    def test_un_seuil_releve_entraine_le_masquage_complementaire(self):
        ligne = ligne_equipe(ALPHA, "story", "story-un", "ticket_template", 35, 6, 12, 9, 8)       # aucune cellule sous 5 : la vue montre tout
        c = critere(donnees(equipes=[ligne], min_cell=8), ALPHA, "story", "story-un")
        self.assertEqual(c["counts"], {"met": masquee(8), "not_met": valeur(12), "not_applicable": valeur(9), "undetermined": masquee(8)})
        self.assertEqual(critere(donnees(equipes=[ligne]), ALPHA, "story", "story-un")["counts"],
                         {"met": valeur(6), "not_met": valeur(12), "not_applicable": valeur(9), "undetermined": valeur(8)})

    def test_le_complement_au_seuil_releve_continue_tant_que_la_somme_masquee_reste_sous_lui(self):
        ligne = ligne_equipe(ALPHA, "story", "story-un", "ticket_template", 40, 20, None, 9, 11)   # la vue a masqué 0 (non satisfaits)
        c = critere(donnees(equipes=[ligne], min_cell=10), ALPHA, "story", "story-un")
        self.assertEqual(c["counts"], {"met": valeur(20), "not_met": masquee(10), "not_applicable": masquee(10), "undetermined": masquee(10)})

    def test_un_seuil_releve_entraine_le_complement_de_la_couverture(self):
        couv = [couverture(BETA, "story", 30, 24, 12)]
        self.assertEqual(donnees(couv=couv, min_cell=8)["teams"][1]["coverage"]["story"],
                         {"collected": masquee(8), "audited": valeur(24), "empty_acceptance_criteria": valeur(12)})
        couv = [couverture(BETA, "story", 40, 30, 23)]
        self.assertEqual(donnees(couv=couv, min_cell=8)["teams"][1]["coverage"]["story"],
                         {"collected": valeur(40), "audited": valeur(30), "empty_acceptance_criteria": masquee(8)})
        self.assertEqual(donnees(couv=couv)["teams"][1]["coverage"]["story"],
                         {"collected": valeur(40), "audited": valeur(30), "empty_acceptance_criteria": valeur(23)})

    def test_la_couverture_par_equipe_et_par_genre_et_le_drapeau_un_seul_po(self):
        beta, alpha = donnees()["teams"][1], donnees()["teams"][0]
        self.assertEqual(beta["coverage"]["story"], {"collected": valeur(41), "audited": valeur(30), "empty_acceptance_criteria": valeur(7)})
        self.assertEqual(alpha["coverage"]["story"]["empty_acceptance_criteria"], masquee())
        self.assertEqual(alpha["coverage"]["epic"], {"collected": masquee(), "audited": masquee(), "empty_acceptance_criteria": masquee()})
        self.assertIs(alpha["single_po"], True)
        self.assertEqual(alpha["single_po_notice"], "Single-PO team: these results are those of one person's work; never use them to evaluate that person")
        self.assertIs(beta["single_po"], False)
        self.assertIsNone(beta["single_po_notice"])

    def test_le_drapeau_un_seul_po_ne_change_aucun_chiffre(self):
        sans = [dict(c, single_po=False) for c in VUE_COUVERTURE]
        a, b = donnees(), donnees(couv=sans)
        for equipe in (ALPHA, BETA):
            self.assertEqual(next(e for e in a["teams"] if e["team"] == equipe)["criteria"],
                             next(e for e in b["teams"] if e["team"] == equipe)["criteria"])
            self.assertEqual(next(e for e in a["teams"] if e["team"] == equipe)["coverage"],
                             next(e for e in b["teams"] if e["team"] == equipe)["coverage"])

    def test_les_criteres_sont_dans_l_ordre_des_codes_par_genre(self):
        codes = [c["code"] for c in donnees()["teams"][0]["criteria"]["story"]]
        self.assertEqual(codes, sorted(codes))


class DefautsRecurrents(unittest.TestCase):
    def test_un_defaut_au_seuil_est_recurrent_avec_son_maillon(self):
        lignes = donnees()["teams"][0]["probable_causes"]["lines"]
        self.assertEqual(lignes, [{"kind": "story", "code": "story-un", "label": "Label story-un", "origin": "core",
                                   "link": "ticket_template", "share_not_met": part(9, 20)}])

    def test_le_seuil_est_compare_sans_arrondi_flottant(self):
        # 7 sur 10 au seuil 0,7 : récurrent ; 0,7 * 10 vaut 7,000000000000001 en flottant
        r = donnees(equipes=[ligne_equipe(ALPHA, "story", "story-un", "refinement", 10, None, 7, None, None)], threshold=0.7)
        self.assertEqual(len(r["teams"][0]["probable_causes"]["lines"]), 1)
        r = donnees(equipes=[ligne_equipe(ALPHA, "story", "story-un", "refinement", 10, None, 7, None, None)], threshold=0.71)
        self.assertEqual(r["teams"][0]["probable_causes"]["lines"], [])

    def test_une_cellule_masquee_n_est_jamais_recurrente(self):
        lignes = donnees()["teams"][0]["probable_causes"]["lines"]
        self.assertNotIn("story-trois", [l["code"] for l in lignes])
        self.assertEqual(donnees()["teams"][1]["probable_causes"]["lines"][0]["code"], "story-un")        # Beta : 17/30
        r = donnees(equipes=[ligne_equipe(ALPHA, "story", "story-un", "ticket_template", 3, 0, 3, None, None)])
        self.assertEqual(r["teams"][0]["probable_causes"]["lines"], [])

    def test_sans_seuil_regle_aucun_defaut_n_est_recurrent(self):
        r = donnees(threshold=None)
        self.assertEqual([e["probable_causes"]["lines"] for e in r["teams"]], [[], []])
        self.assertEqual(r["product_chain"]["lines"], [])

    def test_ordre_par_maillon_puis_par_code_jamais_par_resultat(self):
        lignes = [ligne_equipe(ALPHA, "story", "story-zz", "ticket_template", 20, 5, 10, 5, None),
                  ligne_equipe(ALPHA, "story", "story-aa", "refinement", 20, 1, 14, 5, None),
                  ligne_equipe(ALPHA, "story", "story-bb", "definition_of_ready", 20, 6, 9, 5, None),
                  ligne_equipe(ALPHA, "epic", "epic-cc", "discovery_workflow_step", 20, 6, 9, 5, None),
                  ligne_equipe(ALPHA, "story", "story-ab", "ticket_template", 20, 6, 9, 5, None)]
        codes = [l["code"] for l in donnees(equipes=lignes)["teams"][0]["probable_causes"]["lines"]]
        self.assertEqual(codes, ["story-ab", "story-zz", "epic-cc", "story-bb", "story-aa"])

    def test_la_notice_et_l_absence_de_defaut(self):
        beta = donnees(equipes=[ligne_equipe(BETA, "story", "story-un", "refinement", 20, 15, 0, 5, None)])["teams"][0]["probable_causes"]
        self.assertEqual(beta["lines"], [])
        self.assertEqual(beta["notice"]["code"], "probable_causes_notice")
        self.assertIn("never a person's fault", beta["notice"]["text"])


class ChaineDuProduit(unittest.TestCase):
    def test_une_ligne_de_produit_lue_de_la_vue_produit_et_sans_equipe(self):
        chaine = donnees()["product_chain"]
        self.assertEqual(chaine["lines"], [{"kind": "story", "code": "story-un", "label": "Label story-un", "origin": "core",
                                            "link": "ticket_template", "share_not_met": part(26, 50)}])
        self.assertEqual(chaine["notice"]["code"], "product_chain_notice")

    def test_aucun_nom_d_equipe_ni_compte_d_equipes_dans_la_chaine(self):
        texte = json.dumps(donnees()["product_chain"])
        for equipe in (ALPHA, BETA, "Zzalpha", "Zzbeta"):
            self.assertNotIn(equipe, texte)
        for cle in ("team", "teams", "team_count"):
            self.assertNotIn(f'"{cle}"', texte)

    def test_une_cellule_de_produit_masquee_n_est_jamais_recurrente(self):
        # story-trois : not_met masqué dans la vue produit
        self.assertNotIn("story-trois", [l["code"] for l in donnees()["product_chain"]["lines"]])
        produit = [ligne_produit("story", "story-un", "ticket_template", 4, None, 4, None, None)]
        self.assertEqual(donnees(produit=produit)["product_chain"]["lines"], [])

    def test_le_masquage_secondaire_vient_de_la_vue_et_n_est_pas_recalcule(self):
        # Une ligne de produit que la vue masque (D18, migration 0016) n'a aucune part lisible : absente de la chaîne.
        produit = [ligne_produit("story", "story-un", "ticket_template", None, None, None, None, None)]
        self.assertEqual(donnees(produit=produit)["product_chain"]["lines"], [])
        # Une ligne que la vue montre est reprise telle quelle : la fonction ne recompte pas les cellules d'équipe masquées.
        equipes = VUE_EQUIPE + [ligne_equipe(GAMMA, "story", "story-un", "ticket_template", 12, 7, None, None, None)]
        self.assertEqual([l["code"] for l in donnees(equipes=equipes)["product_chain"]["lines"]], ["story-un"])

    # Revue 4.1, E4 (point 4) : au plancher, le masquage secondaire reste celui de la vue (test précédent) ; un seuil relevé le refait à
    # son niveau, sinon une cellule d'équipe masquée entre 5 et le seuil se retrouverait par différence avec la ligne du produit.
    SECONDAIRE_EQUIPES = [ligne_equipe(ALPHA, "story", "story-un", "ticket_template", 25, 9, 6, 5, 5),
                          ligne_equipe(BETA, "story", "story-un", "ticket_template", 40, 10, 20, 5, 5)]
    SECONDAIRE_PRODUIT = [ligne_produit("story", "story-un", "ticket_template", 65, 19, 26, 10, 10)]

    def test_un_seuil_releve_refait_le_masquage_secondaire(self):
        options = {"equipes": self.SECONDAIRE_EQUIPES, "couv": [], "produit": self.SECONDAIRE_PRODUIT, "threshold": 0.4}
        self.assertEqual([l["code"] for l in donnees(**options)["product_chain"]["lines"]], ["story-un"])      # 26 / 65 au plancher
        r = donnees(min_cell=8, **options)
        self.assertEqual(critere(r, ALPHA, "story", "story-un")["counts"]["not_met"], masquee(8))
        self.assertEqual(critere(r, BETA, "story", "story-un")["counts"]["not_met"], valeur(20))
        self.assertEqual(r["product_chain"]["lines"], [])          # 26 - 20 redonnerait les 6 non satisfaits d'Alpha
        self.assertNotIn('"value": 26', json.dumps(r))

    def test_au_seuil_releve_deux_cellules_d_equipe_masquees_dont_la_somme_atteint_le_seuil_gardent_la_ligne(self):
        equipes = self.SECONDAIRE_EQUIPES + [ligne_equipe(GAMMA, "story", "story-un", "ticket_template", 20, 8, 7, 5, None)]
        produit = [ligne_produit("story", "story-un", "ticket_template", 85, 27, 33, 15, 10)]
        r = donnees(equipes=equipes, couv=[], produit=produit, threshold=0.38, min_cell=8)
        self.assertEqual([l["share_not_met"] for l in r["product_chain"]["lines"]], [part(33, 85)])   # 6 + 7 masqués, somme 13

    def test_ordre_des_lignes_par_maillon_puis_code(self):
        produit = [ligne_produit("story", "story-b", "refinement", 20, 5, 15, 5, None),
                   ligne_produit("story", "story-a", "refinement", 20, 5, 15, 5, None),
                   ligne_produit("epic", "epic-a", "ticket_template", 20, 5, 15, 5, None)]
        self.assertEqual([l["code"] for l in donnees(equipes=[], produit=produit)["product_chain"]["lines"]], ["epic-a", "story-a", "story-b"])

    def test_un_element_de_deux_equipes_compte_une_fois_dans_la_vue_produit(self):
        # la fonction ne somme jamais les cellules d'équipe : 26 au produit alors que les équipes montrent 9 + 17
        self.assertEqual(donnees()["product_chain"]["lines"][0]["share_not_met"], part(26, 50))


class IndependanceDeLOrdreEtGardeAntiComparaison(unittest.TestCase):
    def test_le_resultat_est_le_meme_quel_que_soit_l_ordre_des_lignes(self):
        a = donnees()
        b = donnees(equipes=VUE_EQUIPE[::-1], couv=VUE_COUVERTURE[::-1], produit=VUE_PRODUIT[::-1])
        self.assertEqual(json.dumps(a, sort_keys=False), json.dumps(b, sort_keys=False))

    def test_deux_equipes_aux_resultats_echanges_gardent_leur_ordre(self):
        echange = [dict(l, team=BETA if l["team"] == ALPHA else ALPHA) for l in VUE_EQUIPE]
        echange_couv = [dict(l, team=BETA if l["team"] == ALPHA else ALPHA) for l in VUE_COUVERTURE]
        r = donnees(equipes=echange, couv=echange_couv)
        self.assertEqual([e["team"] for e in r["teams"]], [ALPHA, BETA])
        self.assertEqual([e["team"] for e in donnees()["teams"]], [ALPHA, BETA])

    def test_une_equipe_connue_de_la_seule_couverture_a_sa_place(self):
        r = donnees(couv=VUE_COUVERTURE + [couverture("Equipe Zzaaa", "story", 6, 0, 0)])
        self.assertEqual([e["team"] for e in r["teams"]], ["Equipe Zzaaa", ALPHA, BETA])
        self.assertEqual(r["teams"][0]["criteria"], {"story": [], "epic": []})

    def test_une_ligne_vide_donne_un_rapport_vide(self):
        r = data.report_data([], [], [], GRILLE, threshold=0.5, language="en")
        self.assertEqual((r["teams"], r["product_chain"]["lines"]), ([], []))


CLES = {
    "root": {"contract", "contract_version", "grid", "notice", "teams", "product_chain"},
    "grid": {"core_version", "overlay_version", "disabled_codes"},
    "notice": {"code", "text"},
    "team": {"team", "single_po", "single_po_notice", "coverage", "criteria", "probable_causes"},
    "coverage": {"collected", "audited", "empty_acceptance_criteria"},
    "criterion": {"code", "label", "origin", "link", "counts", "share_met", "share_not_met"},
    "counts": {"met", "not_met", "not_applicable", "undetermined"},         # les quatre comptes de D15 : `audited` ne sert qu'au dénominateur
    "causes": {"notice", "lines"},
    "line": {"kind", "code", "label", "origin", "link", "share_not_met"},
    "chain": {"notice", "lines"},
}


def verifier_cle(cas, objet, genre):
    cas.assertEqual(set(objet), CLES[genre], genre)


def verifier_cellule(cas, cellule):
    if cellule["state"] == "value":
        cas.assertEqual(set(cellule), {"state", "value"})
        cas.assertIsInstance(cellule["value"], int)
    else:
        cas.assertEqual(set(cellule), {"state", "threshold"})
        cas.assertEqual(cellule["state"], "masked")


def verifier_part(cas, p):
    if p["state"] == "value":
        cas.assertEqual(set(p), {"state", "numerator", "denominator"})
        verifier_cellule(cas, p["numerator"])
        verifier_cellule(cas, p["denominator"])
        cas.assertEqual((p["numerator"]["state"], p["denominator"]["state"]), ("value", "value"))
    else:
        cas.assertEqual(set(p), {"state", "threshold"})
        cas.assertEqual(p["state"], "masked")


class EnsembleDeClesFerme(unittest.TestCase):
    """Aucune clé hors du contrat de D15 : ni rang, ni score, ni total par équipe, ni nombre d'équipes, ni clé, texte ou personne."""

    def test_aucune_cle_hors_du_contrat(self):
        for langue in ("en", "fr"):
            r = donnees(language=langue)
            verifier_cle(self, r, "root")
            verifier_cle(self, r["grid"], "grid")
            verifier_cle(self, r["notice"], "notice")
            for equipe in r["teams"]:
                verifier_cle(self, equipe, "team")
                for genre, couverture_ in equipe["coverage"].items():
                    self.assertIn(genre, ("story", "epic"))
                    verifier_cle(self, couverture_, "coverage")
                    for cellule in couverture_.values():
                        verifier_cellule(self, cellule)
                for criteres in equipe["criteria"].values():
                    for c in criteres:
                        verifier_cle(self, c, "criterion")
                        verifier_cle(self, c["counts"], "counts")
                        for cellule in c["counts"].values():
                            verifier_cellule(self, cellule)
                        verifier_part(self, c["share_met"])
                        verifier_part(self, c["share_not_met"])
                verifier_cle(self, equipe["probable_causes"], "causes")
                verifier_cle(self, equipe["probable_causes"]["notice"], "notice")
                for ligne in equipe["probable_causes"]["lines"]:
                    verifier_cle(self, ligne, "line")
                    verifier_part(self, ligne["share_not_met"])
            verifier_cle(self, r["product_chain"], "chain")
            verifier_cle(self, r["product_chain"]["notice"], "notice")
            for ligne in r["product_chain"]["lines"]:
                verifier_cle(self, ligne, "line")

    def test_aucun_chiffre_ni_cle_hors_des_cellules_de_la_vue(self):
        # une clé distinctive dans une ligne de vue (colonnes inattendues) n'est jamais recopiée dans le résultat
        ligne = dict(VUE_EQUIPE[0], key="ZZ-1234", title="zztitre distinctif", person="zzpersonne", feedback="zzretour")
        texte = json.dumps(donnees(equipes=[ligne]))
        for distinctif in ("ZZ-1234", "zztitre", "zzpersonne", "zzretour"):
            self.assertNotIn(distinctif, texte)

    def test_le_resultat_se_serialise_en_json(self):
        json.dumps(donnees())


if __name__ == "__main__":
    unittest.main()
