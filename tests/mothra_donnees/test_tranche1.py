"""
Tests de l'extension du jeu synthétique de Mothra pour la tranche 1 (tâche 14.1, conception D13, D19, D22, D33).

Sans base : la forme et les équipes témoins. Les verdicts attendus sont recalculés ici, d'après l'annexe « Starting thresholds »
de la conception (rapport médian et P85 de l'hypothèse 1, première moitié ; bandes et planchers de l'hypothèse 5), puis comparés aux
verdicts que le jeu déclare pour chaque équipe témoin : le jeu ne dit pas seulement qu'un témoin existe, il le prouve.

    bash tests/run_all.sh mothra_donnees
"""
from __future__ import annotations

import sys
import unittest
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(DOSSIER))
sys.path.insert(0, str(DOSSIER.parents[1] / "tests" / "flow_store"))
import jeu_synthetique as base  # noqa: E402
import tranche1 as t1  # noqa: E402
import aide_base  # noqa: E402

MAINTENANT = base.INSTANT_FIXE
JOUR = timedelta(days=1)

# Seuils de départ de l'annexe (non normatifs : ils servent aux seules exécutions synthétiques). Ils restent en dur dans ces tests ;
# ils viendront de la configuration typée quand elle existera (D17, D21) : ce jour-là, ces constantes la liront.
RAPPORT_REFUTE_SOUS, RAPPORT_CONFIRME_AU_DESSUS = 1.5, 3.0
BANDE, BANDE_DOUBLE, PLANCHER, PLANCHER_BAS = 0.20, 0.40, 0.80, 0.60
SEUIL_MASQUAGE, FIABLE_MEDIANE, FIABLE_P85 = 5, 10, 20
ECART_TACHES_SANS_EQUIPE = 10.0   # points de pourcentage
UN_AN = timedelta(days=365)


def percentile(valeurs, p):
    v = sorted(valeurs)
    pos = (len(v) - 1) * p
    bas = int(pos)
    haut = min(bas + 1, len(v) - 1)
    return v[bas] + (v[haut] - v[bas]) * (pos - bas)


def indice_civil(maintenant, date):
    """Trimestre civil de `date` : 0 pour le dernier trimestre civil clos avant `maintenant`, 1 pour celui d'avant, etc."""
    return (maintenant.year * 4 + (maintenant.month - 1) // 3) - (date.year * 4 + (date.month - 1) // 3) - 1


def trimestre(t, maintenant=MAINTENANT):
    return indice_civil(maintenant, t["resolu"])


def engagement(t):
    """Le point d'engagement : la première transition vers le statut prêt (R-20261029-21)."""
    return min(d for d, _, vers in t["transitions"] if vers == t1.STATUT_PRET)


def cycle(t):
    return (t["resolu"] - engagement(t)) / JOUR


def delai(t):
    return (t["resolu"] - t["cree"]) / JOUR


def termines(tickets, equipe, types=("Story", "Task")):
    return [t for t in tickets if t["equipe"] == equipe and t["resolu"] and t["type"] in types]


def verdict_h1(tickets, equipe, pooler_anciens=False):
    """Verdict de la seule règle de seuils, première moitié de l'hypothèse 1 : année poolée, éléments créés plus d'un an avant leur
    début à part (ou mis en commun avec `pooler_anciens`, pour prouver ce que le comptage à part change)."""
    items = [t for t in termines(tickets, equipe)
             if (pooler_anciens or engagement(t) - t["cree"] <= UN_AN) and trimestre(t) < 3]
    n = len(items)
    if n < SEUIL_MASQUAGE:
        return "masqué"
    if n < FIABLE_MEDIANE:
        return "échantillon insuffisant"
    rapport_med = percentile([delai(t) for t in items], 0.5) / percentile([cycle(t) for t in items], 0.5)
    if rapport_med < RAPPORT_REFUTE_SOUS:
        return "réfuté"
    if n < FIABLE_P85:
        return "non tranché"   # l'année poolée sous la taille du P85 plafonne le verdict (Q22)
    rapport_p85 = percentile([delai(t) for t in items], 0.85) / percentile([cycle(t) for t in items], 0.85)
    if rapport_med > RAPPORT_CONFIRME_AU_DESSUS and rapport_p85 > RAPPORT_CONFIRME_AU_DESSUS:
        return "confirmé"
    return "non tranché"


def part_sans_equipe(tickets, k):
    taches = [t for t in tickets if t["type"] == "Task" and t["resolu"] and trimestre(t) == k]
    return 100.0 * sum(1 for t in taches if t["equipe"] is None) / len(taches)


def signal_rattachement_leve(tickets):
    """Signal de D33 : la part de tâches terminées sans équipe du trimestre jugé s'écarte de celle des trimestres de référence : les deux qui le
    précèdent (D13, R-20261114-51 ; trois avant)."""
    reference = sum(part_sans_equipe(tickets, k) for k in (1, 2)) / 2
    return abs(part_sans_equipe(tickets, 0) - reference) > ECART_TACHES_SANS_EQUIPE


def verdict_attendu(seuils, hypothese, signal):
    """Verdict après les explications concurrentes (D20, D33) : (verdict, motifs affichés).
    - défauts sans équipe : l'explication « travail non planifié » n'est pas mesurable, `defects_without_team` interdit « confirmé » ;
    - signal de rattachement des tâches : affiché à côté du verdict de l'hypothèse 5 (elle lit le débit) ; il interdit « confirmé »
      (`tasks_attachment_signal`), « réfuté » reste possible. L'hypothèse 1 n'est pas tenue de le lire (à décider à la revue de la
      tranche 1) : le jeu la traite comme ne lisant pas le débit.
    Les motifs listés sont ceux qui accompagnent le verdict : ceux qui ont interdit « confirmé », et le signal quand il est levé."""
    motifs = []
    verdict = seuils
    if seuils == "confirmé":
        motifs.append("defects_without_team")
        verdict = "non tranché"
    if hypothese == "h5" and signal:
        motifs.append("tasks_attachment_signal")
    return verdict, tuple(motifs)


def verdict_h5(tickets, equipe):
    """Verdict de la seule règle de seuils, hypothèse 5 : trois trimestres poolés (D14 : la référence est la moyenne des trois, le jugé compris), bandes
    sur la médiane et le P85, série montante, planchers de débit."""
    items = termines(tickets, equipe)
    par_trimestre = defaultdict(list)
    for t in items:
        par_trimestre[trimestre(t)].append(t)
    ordre = [2, 1, 0]   # du plus ancien au plus récent
    n = [len(par_trimestre[k]) for k in ordre]
    med = [percentile([cycle(t) for t in par_trimestre[k]], 0.5) for k in ordre]
    p85 = [percentile([cycle(t) for t in par_trimestre[k]], 0.85) for k in ordre]
    ref_n, ref_med, ref_p85 = sum(n) / 3, sum(med) / 3, sum(p85) / 3

    def hors(valeur, ref, bande):
        return abs(valeur - ref) / ref > bande
    hors_double = sum(1 for m, p in zip(med, p85) if hors(m, ref_med, BANDE_DOUBLE) or hors(p, ref_p85, BANDE_DOUBLE))
    serie = any(med[i] < med[i + 1] < med[i + 2] for i in range(1))      # trois trimestres : une seule série de trois (quatre : deux)
    sous_plancher_bas = any(x < PLANCHER_BAS * ref_n for x in n)
    if hors_double >= 2 or serie or sous_plancher_bas:
        return "réfuté"
    dans_la_bande = all(not hors(m, ref_med, BANDE) and not hors(p, ref_p85, BANDE) for m, p in zip(med, p85))
    if dans_la_bande and all(x >= PLANCHER * ref_n for x in n):
        return "confirmé"
    return "non tranché"


class DatesEtDeterminisme(unittest.TestCase):
    def setUp(self):
        self.tickets = t1.construire_tranche1(MAINTENANT)

    def test_deterministe(self):
        self.assertEqual(t1.construire_tranche1(MAINTENANT), t1.construire_tranche1(MAINTENANT))

    def test_trimestres_civils_alignes_sur_le_trimestre_courant(self):
        # le trimestre jugé est le dernier trimestre civil clos : janvier 2026 (T1) juge le T4 2025, les deux précédents sont la référence
        # (trois trimestres clos, R-20261114-49 : le T1 2025 n'est plus dans la fenêtre)
        for t in self.tickets:
            if t["resolu"]:
                self.assertIn((t["resolu"].year, (t["resolu"].month - 1) // 3 + 1), {(2025, 4), (2025, 3), (2025, 2)}, t["cle"])
        self.assertEqual({trimestre(t) for t in self.tickets if t["resolu"]}, {0, 1, 2})

    def test_marge_aux_deux_bords_du_trimestre(self):
        for t in self.tickets:
            if t["resolu"]:
                debut = t1.debut_trimestre(MAINTENANT, trimestre(t) + 1)
                fin = t1.debut_trimestre(MAINTENANT, trimestre(t))
                self.assertGreaterEqual(t["resolu"] - debut, timedelta(days=5), t["cle"])
                self.assertGreaterEqual(fin - t["resolu"], timedelta(days=5), t["cle"])

    def test_meme_jeu_a_deux_instants_du_meme_trimestre(self):
        # début et fin du trimestre civil courant (T1 2026) : les éléments terminés sont identiques, donc tous les verdicts aussi
        debut = base.INSTANT_FIXE.replace(month=1, day=1, hour=0, minute=0)
        fin = base.INSTANT_FIXE.replace(month=3, day=31, hour=23, minute=59)
        for autre_instant in (debut, fin):
            autre = t1.construire_tranche1(autre_instant)
            self.assertEqual(len(autre), len(self.tickets))
            for a, b in zip(self.tickets, autre):
                self.assertEqual(b["cle"], a["cle"])
                self.assertEqual((a["equipe"], a["type"], a["liens"], a["parent"], a["ancien"]),
                                 (b["equipe"], b["type"], b["liens"], b["parent"], b["ancien"]))
                if a["resolu"]:
                    self.assertEqual((a["cree"], a["resolu"], a["transitions"]), (b["cree"], b["resolu"], b["transitions"]), a["cle"])
                    self.assertEqual(trimestre(a), trimestre(b, autre_instant), a["cle"])
                else:
                    self.assertIsNone(b["resolu"])
            # verdicts, débits, blocages et signal inchangés (les éléments terminés étant les mêmes, les fonctions de test s'appliquent telles quelles)
            for equipe, attendu in t1.VERDICTS_SEUILS_H1.items():
                self.assertEqual(verdict_h1(autre, equipe), attendu, equipe)
            for equipe, attendu in t1.VERDICTS_SEUILS_H5.items():
                self.assertEqual(verdict_h5(autre, equipe), attendu, equipe)
            for equipe, par_trimestre in t1.DEBIT_ATTENDU.items():
                comptes = Counter(trimestre(t, autre_instant) for t in termines(autre, equipe))
                self.assertEqual({k: comptes[k] for k in range(3)}, par_trimestre, equipe)
            self.assertTrue(signal_rattachement_leve(autre))
            par_cle = {t["cle"]: t for t in autre}
            bloques = defaultdict(set)
            for t in autre:
                for cible, genre in t["liens"]:
                    c = par_cle[cible]
                    if genre == "blocks" and t["equipe"] and c["equipe"] and t["equipe"] != c["equipe"] and c["resolu"]:
                        bloques[(c["equipe"], trimestre(c, autre_instant))].add(c["cle"])
            self.assertEqual({k: len(v) for k, v in bloques.items()}, t1.BLOCAGES_ATTENDUS)

    def test_le_jeu_change_quand_le_trimestre_change(self):
        # sanity : un instant du trimestre suivant décale les trimestres civils
        suivant = t1.construire_tranche1(base.INSTANT_FIXE.replace(month=4, day=2))
        self.assertNotEqual([t["resolu"] for t in suivant], [t["resolu"] for t in self.tickets])

    def test_dates_coherentes(self):
        for t in self.tickets:
            self.assertLessEqual(t["cree"], MAINTENANT - timedelta(hours=1), t["cle"])
            self.assertLessEqual(t["maj"], MAINTENANT, t["cle"])
            self.assertEqual(t["categorie"] == "Done", t["resolu"] is not None, t["cle"])
            if t["resolu"]:
                self.assertLessEqual(t["resolu"], MAINTENANT - timedelta(hours=1), t["cle"])
                self.assertLessEqual(t["cree"], engagement(t), t["cle"])
                self.assertLess(engagement(t), t["resolu"], t["cle"])
            for d, _, _ in t["transitions"]:
                self.assertGreaterEqual(d, t["cree"], t["cle"])

    def test_creation_engagement_et_fin_sur_au_moins_trois_trimestres(self):
        def indices(dates):
            return {indice_civil(MAINTENANT, d) for d in dates}
        faits = [t for t in self.tickets if t["resolu"]]
        self.assertGreaterEqual(len(indices(t["resolu"] for t in faits)), 3)
        self.assertGreaterEqual(len(indices(engagement(t) for t in faits)), 3)
        self.assertGreaterEqual(len(indices(t["cree"] for t in self.tickets)), 3)

    def test_elements_crees_longtemps_avant_leur_demarrage(self):
        anciens = [t for t in self.tickets if t["resolu"] and engagement(t) - t["cree"] > UN_AN]
        self.assertGreaterEqual(len(anciens), 5)
        self.assertEqual({t["cle"] for t in anciens}, {t["cle"] for t in self.tickets if t["ancien"]})
        # ils sont terminés dans l'année retenue, sinon ils ne pèseraient pas sur la fenêtre
        for t in anciens:
            self.assertLess(trimestre(t), 3)
        # et les autres ne le sont pas
        for t in self.tickets:
            if t["resolu"] and not t["ancien"]:
                self.assertLessEqual(engagement(t) - t["cree"], UN_AN, t["cle"])

    def test_file_prete_a_part(self):
        pretes = [t for t in self.tickets if t["statut"] == t1.STATUT_PRET]
        self.assertGreaterEqual(len(pretes), 5)
        for t in pretes:
            self.assertEqual((t["resolu"], [(de, vers) for _, de, vers in t["transitions"]]), (None, [("To Do", t1.STATUT_PRET)]))


class FormeEtConfidentialite(unittest.TestCase):
    def setUp(self):
        self.tickets = t1.construire_tranche1(MAINTENANT)
        self.tranche0 = base.construire(MAINTENANT)

    def test_equipes_generiques_hors_de_la_tranche_0(self):
        noms = {t["equipe"] for t in self.tickets if t["equipe"]}
        self.assertEqual(noms, set(t1.EQUIPES_TRANCHE1))
        for nom in noms:
            self.assertRegex(nom, r"^équipe [A-Z]$")
        self.assertFalse(noms & base.EQUIPES_GENERIQUES)

    def test_cles_inventees_uniques_et_disjointes_de_la_tranche_0(self):
        cles = [t["cle"] for t in self.tickets]
        self.assertEqual(len(cles), len(set(cles)))
        self.assertFalse(set(cles) & {t["cle"] for t in self.tranche0})
        for cle in cles:
            self.assertRegex(cle, r"^SYN-[1-9][0-9]*$")

    def test_sentinelles_dans_des_colonnes_non_exposees(self):
        for t in self.tickets:
            for colonne in ("equipe", "type", "categorie", "statut"):
                for sentinelle in base.SENTINELLES:
                    self.assertNotIn(sentinelle, str(t[colonne]))
        texte = repr(self.tickets)
        for sentinelle in base.SENTINELLES[:2]:
            self.assertIn(sentinelle, texte)

    def test_aucune_cible_de_lien_ni_parent_hors_du_jeu(self):
        cles = {t["cle"] for t in self.tickets}
        for t in self.tickets:
            if t["parent"]:
                self.assertIn(t["parent"], cles, t["cle"])
            for cible, _ in t["liens"]:
                self.assertIn(cible, cles, t["cle"])


class EquipesTemoinsHypothese1(unittest.TestCase):
    def setUp(self):
        self.tickets = t1.construire_tranche1(MAINTENANT)

    def test_chaque_verdict_de_seuils_a_un_temoin(self):
        self.assertEqual(set(t1.VERDICTS_SEUILS_H1.values()),
                         {"confirmé", "réfuté", "non tranché", "échantillon insuffisant", "masqué"})

    def test_le_verdict_de_seuils_recalcule_egale_le_verdict_declare(self):
        for equipe, attendu in t1.VERDICTS_SEUILS_H1.items():
            self.assertEqual(verdict_h1(self.tickets, equipe), attendu, equipe)

    def test_un_verdict_non_tranche_pour_trois_raisons_distinctes(self):
        # zone grise, P85 qui ne suit pas la médiane, année poolée sous la taille du P85
        non_tranches = [e for e, v in t1.VERDICTS_SEUILS_H1.items() if v == "non tranché"]
        self.assertGreaterEqual(len(non_tranches), 3)
        gris = t1.TEMOIN_ZONE_GRISE
        items = termines(self.tickets, gris)
        r = percentile([delai(t) for t in items if not t["ancien"]], 0.5) / percentile([cycle(t) for t in items if not t["ancien"]], 0.5)
        self.assertTrue(RAPPORT_REFUTE_SOUS <= r <= RAPPORT_CONFIRME_AU_DESSUS)
        h = t1.TEMOIN_P85_DIVERGENT
        items = termines(self.tickets, h)
        self.assertGreater(percentile([delai(t) for t in items], 0.5) / percentile([cycle(t) for t in items], 0.5), RAPPORT_CONFIRME_AU_DESSUS)
        self.assertLessEqual(percentile([delai(t) for t in items], 0.85) / percentile([cycle(t) for t in items], 0.85),
                             RAPPORT_CONFIRME_AU_DESSUS)
        p = t1.TEMOIN_SOUS_P85
        items = termines(self.tickets, p)
        self.assertGreater(percentile([delai(t) for t in items], 0.5) / percentile([cycle(t) for t in items], 0.5), RAPPORT_CONFIRME_AU_DESSUS)
        self.assertLess(len(items), FIABLE_P85)

    def test_les_anciens_comptes_a_part_changent_le_verdict_s_ils_sont_mis_en_commun(self):
        equipe = t1.TEMOIN_ANCIENS
        items = termines(self.tickets, equipe)
        self.assertEqual(sum(1 for t in items if t["ancien"]), t1.ANCIENS_TEMOIN)
        a_part = [t for t in items if not t["ancien"]]
        # à part : le rapport médian dépasse 3, le P85 reste au plus à 3
        self.assertGreater(percentile([delai(t) for t in a_part], 0.5) / percentile([cycle(t) for t in a_part], 0.5), RAPPORT_CONFIRME_AU_DESSUS)
        self.assertLessEqual(percentile([delai(t) for t in a_part], 0.85) / percentile([cycle(t) for t in a_part], 0.85),
                             RAPPORT_CONFIRME_AU_DESSUS)
        self.assertGreaterEqual(len(a_part), FIABLE_P85)
        self.assertEqual(verdict_h1(self.tickets, equipe), "non tranché")
        self.assertEqual(verdict_h1(self.tickets, equipe, pooler_anciens=True), "confirmé")
        self.assertEqual(t1.VERDICTS_SEUILS_H1[equipe], "non tranché")

    def test_l_equipe_g_n_a_plus_d_ancien_et_reste_en_zone_grise(self):
        items = termines(self.tickets, t1.TEMOIN_ZONE_GRISE)
        self.assertFalse(any(t["ancien"] for t in items))
        r = percentile([delai(t) for t in items], 0.5) / percentile([cycle(t) for t in items], 0.5)
        self.assertTrue(RAPPORT_REFUTE_SOUS <= r <= RAPPORT_CONFIRME_AU_DESSUS)

    def test_verdicts_croises_h5_sous_h1_recalcules_et_h1_sous_h5_hors_temoin(self):
        self.assertEqual(set(t1.VERDICTS_CROISES_H5_SOUS_H1), set(t1.VERDICTS_SEUILS_H5))
        for equipe, attendu in t1.VERDICTS_CROISES_H5_SOUS_H1.items():
            self.assertEqual(verdict_h1(self.tickets, equipe), attendu, equipe)
        # les équipes de H1 ont moins de 20 éléments par trimestre : la règle de fiabilité de H5 ne les juge pas, elles sont hors témoin
        self.assertEqual(set(t1.VERDICTS_CROISES_H1_SOUS_H5), set(t1.VERDICTS_SEUILS_H1))
        self.assertEqual(set(t1.VERDICTS_CROISES_H1_SOUS_H5.values()), {"hors témoin"})

    def test_equipes_aux_bornes_exactes(self):
        # 5 : non masqué, échantillon insuffisant ; 10 : médiane fiable, plafond « non tranché » ; 20 : verdict plein
        for equipe, n, attendu in (("équipe S", 5, "échantillon insuffisant"), ("équipe T", 10, "non tranché"), ("équipe U", 20, "confirmé")):
            self.assertEqual(len(termines(self.tickets, equipe)), n, equipe)
            self.assertEqual(verdict_h1(self.tickets, equipe), attendu, equipe)
            self.assertEqual(t1.VERDICTS_SEUILS_H1[equipe], attendu, equipe)
        self.assertEqual((SEUIL_MASQUAGE, FIABLE_MEDIANE, FIABLE_P85), (5, 10, 20))

    def test_table_du_verdict_attendu_apres_les_explications_concurrentes(self):
        signal = signal_rattachement_leve(self.tickets)
        self.assertTrue(signal)
        attendu = {}
        for equipe, seuils in t1.VERDICTS_SEUILS_H1.items():
            attendu[equipe] = verdict_attendu(seuils, "h1", signal)
        for equipe, seuils in t1.VERDICTS_SEUILS_H5.items():
            attendu[equipe] = verdict_attendu(seuils, "h5", signal)
        self.assertEqual(t1.VERDICTS_ATTENDUS, attendu)
        # les cas qui comptent, écrits en clair
        self.assertEqual(t1.VERDICTS_ATTENDUS["équipe E"], ("non tranché", ("defects_without_team",)))
        self.assertEqual(t1.VERDICTS_ATTENDUS["équipe L"], ("non tranché", ("defects_without_team", "tasks_attachment_signal")))
        for equipe in "MNO":
            self.assertEqual(t1.VERDICTS_ATTENDUS[f"équipe {equipe}"], ("réfuté", ("tasks_attachment_signal",)))
        self.assertEqual(t1.VERDICTS_ATTENDUS["équipe F"], ("réfuté", ()))
        # « confirmé » n'est plus possible nulle part tant que les défauts n'ont pas d'équipe
        self.assertNotIn("confirmé", {v for v, _ in t1.VERDICTS_ATTENDUS.values()})


class TaillesDEchantillon(unittest.TestCase):
    def setUp(self):
        self.tickets = t1.construire_tranche1(MAINTENANT)

    def effectif(self, equipe):
        return len([t for t in termines(self.tickets, equipe) if not t["ancien"]])

    def test_un_echantillon_sous_chaque_taille(self):
        e = {equipe: self.effectif(equipe) for equipe in t1.VERDICTS_SEUILS_H1}
        self.assertTrue(any(n < SEUIL_MASQUAGE for n in e.values()), "sous la taille de masquage")
        self.assertTrue(any(SEUIL_MASQUAGE <= n < FIABLE_MEDIANE for n in e.values()), "sous la fiabilité d'une médiane")
        self.assertTrue(any(FIABLE_MEDIANE <= n < FIABLE_P85 for n in e.values()), "sous la fiabilité d'un P85")
        self.assertTrue(any(n >= FIABLE_P85 for n in e.values()), "assez pour un P85")

    def test_les_bornes_sont_encadrees(self):
        # un effectif juste sous chaque taille (4, 9 et 19) et exactement à chacune (5, 10) ; 20 est le premier effectif assez fourni
        effectifs = sorted(self.effectif(e) for e in t1.VERDICTS_SEUILS_H1)
        self.assertEqual([n for n in effectifs if n <= FIABLE_P85], [4, 5, 9, 10, 19, 20])

    def test_chaque_equipe_de_h1_a_des_dates_sur_plusieurs_trimestres(self):
        # Les témoins de taille I, J, S et T tiennent dans un seul trimestre (R-20261104-42, question 1) : un trimestre sous 5 masquerait
        # l'année groupée, que la fiche de H1 lit (test_tranche1_masquage.py). Les autres sont répartis sur les trois trimestres.
        for equipe in t1.VERDICTS_SEUILS_H1:
            quand = {trimestre(t) for t in termines(self.tickets, equipe)}
            attendu = {0} if equipe in {"équipe I", "équipe J", "équipe S", "équipe T"} else {0, 1, 2}   # littéral, pas relu dans le jeu
            self.assertEqual(quand, attendu, equipe)
        self.assertEqual({e for e, g in t1.GRAPPES_H1.items() if len(g) == 1}, {"équipe I", "équipe J", "équipe S", "équipe T"})

    def test_les_grappes_declarees_egalent_les_fins_par_trimestre(self):
        # Garde de déclaration (C3 de la revue de code) : une grappe plus grande que les éléments créés laisserait des comptes hebdomadaires
        # différents de GRAPPES_H1 sans erreur. Remplace : rien. Retrait : permanent, avec GRAPPES_H1.
        for equipe, par_k in t1.GRAPPES_H1.items():
            for k, tailles in par_k.items():
                self.assertEqual(sum(1 for t in termines(self.tickets, equipe) if trimestre(t) == k), sum(tailles), (equipe, k))

    def test_trimestres_de_h5_assez_fournis_pour_la_mediane_et_le_p85(self):
        for equipe in t1.VERDICTS_SEUILS_H5:
            par = Counter(trimestre(t) for t in termines(self.tickets, equipe))
            self.assertEqual(sorted(par), [0, 1, 2], equipe)
            for k, n in par.items():
                self.assertGreaterEqual(n, FIABLE_P85, (equipe, k))


class EquipesTemoinsHypothese5(unittest.TestCase):
    def setUp(self):
        self.tickets = t1.construire_tranche1(MAINTENANT)

    def test_chaque_verdict_de_seuils_a_un_temoin(self):
        self.assertEqual(set(t1.VERDICTS_SEUILS_H5.values()), {"confirmé", "réfuté", "non tranché"})

    def test_le_verdict_de_seuils_recalcule_egale_le_verdict_declare(self):
        for equipe, attendu in t1.VERDICTS_SEUILS_H5.items():
            self.assertEqual(verdict_h5(self.tickets, equipe), attendu, equipe)

    def test_les_trois_motifs_de_refutation_ont_chacun_un_temoin(self):
        self.assertEqual(set(t1.MOTIFS_REFUTATION_H5), {"deux trimestres hors de la double bande", "série montante", "plancher bas de débit"})
        self.assertEqual({t1.VERDICTS_SEUILS_H5[e] for e in t1.MOTIFS_REFUTATION_H5.values()}, {"réfuté"})
        self.assertEqual(len(set(t1.MOTIFS_REFUTATION_H5.values())), 3)


class DefautsEtTachesSansEquipe(unittest.TestCase):
    """Témoins de D33 : aucun défaut n'a d'équipe ; une part des tâches terminées n'en a pas."""

    def setUp(self):
        self.tickets = t1.construire_tranche1(MAINTENANT)
        self.par_cle = {t["cle"]: t for t in self.tickets}

    def rattache(self, t):
        """Trois sortes de lien déductible vers une équipe : ticket parent d'une équipe, lien vers une story d'une équipe, épic d'une équipe."""
        sortes = set()
        parent = self.par_cle.get(t["parent"])
        if parent and parent["equipe"]:
            sortes.add("parent_epic" if parent["type"] == "Epic" else "parent_story")
        for cible, _ in t["liens"]:
            c = self.par_cle[cible]
            if c["equipe"] and c["type"] == "Story":
                sortes.add("lien_story")
        return sortes

    def test_aucun_defaut_n_a_d_equipe_ouverts_comme_termines(self):
        defauts = [t for t in self.tickets if t["type"] == "Bug"]
        self.assertTrue(defauts)
        self.assertTrue(all(t["equipe"] is None for t in defauts))
        self.assertTrue(any(t["resolu"] for t in defauts))
        self.assertTrue(any(not t["resolu"] for t in defauts))

    def test_des_defauts_lies_a_une_story_ou_sous_l_epic_d_une_equipe(self):
        sortes = Counter()
        for t in self.tickets:
            if t["type"] == "Bug":
                sortes.update(self.rattache(t))
        self.assertGreaterEqual(sortes["parent_story"], 1)
        self.assertGreaterEqual(sortes["lien_story"], 1)
        self.assertGreaterEqual(sortes["parent_epic"], 1)
        # et des défauts sans aucun lien déductible
        self.assertTrue(any(t["type"] == "Bug" and not self.rattache(t) for t in self.tickets))

    def test_des_taches_terminees_sans_equipe_sur_chaque_trimestre(self):
        sans = [t for t in self.tickets if t["type"] == "Task" and t["resolu"] and t["equipe"] is None]
        self.assertEqual({trimestre(t) for t in sans}, {0, 1, 2})
        avec = [t for t in self.tickets if t["type"] == "Task" and t["resolu"] and t["equipe"]]
        self.assertEqual({trimestre(t) for t in avec}, {0, 1, 2})

    def test_des_taches_sans_equipe_liees_ou_sous_l_epic_d_une_equipe(self):
        sortes = Counter()
        for t in self.tickets:
            if t["type"] == "Task" and t["resolu"] and t["equipe"] is None:
                sortes.update(self.rattache(t))
        self.assertGreaterEqual(sortes["parent_story"], 1)
        self.assertGreaterEqual(sortes["lien_story"], 1)
        self.assertGreaterEqual(sortes["parent_epic"], 1)
        self.assertTrue(any(t["type"] == "Task" and t["resolu"] and t["equipe"] is None and not self.rattache(t) for t in self.tickets))

    def part_sans_equipe(self, k):
        return part_sans_equipe(self.tickets, k)

    def test_la_part_de_taches_sans_equipe_depasse_le_seuil_au_trimestre_juge(self):
        reference = sum(self.part_sans_equipe(k) for k in (1, 2)) / 2      # les deux trimestres qui précèdent le jugé (D13) ; trois avant
        self.assertGreater(self.part_sans_equipe(0) - reference, ECART_TACHES_SANS_EQUIPE)
        # les trimestres de référence entre eux restent dans le seuil : le témoin sépare le signal du bruit
        for k in (1, 2):
            self.assertLessEqual(abs(self.part_sans_equipe(k) - reference), ECART_TACHES_SANS_EQUIPE)

    def test_debit_attendu_par_equipe_et_trimestre_sans_rattachement_des_tickets_sans_equipe(self):
        # Débit d'une équipe : stories et tâches terminées portées par l'équipe seule. Les tâches et les défauts sans équipe, même liés à
        # une story ou sous un épic de l'équipe L, n'y entrent pas : la tâche 15.1 vérifiera ces chiffres sur les vues.
        for equipe, par_trimestre in t1.DEBIT_ATTENDU.items():
            comptes = Counter(trimestre(t) for t in termines(self.tickets, equipe))
            self.assertEqual({k: comptes[k] for k in range(3)}, par_trimestre, equipe)
        self.assertEqual(t1.DEBIT_ATTENDU["équipe L"], {0: 25, 1: 25, 2: 25})
        self.assertGreaterEqual(len(t1.DEBIT_ATTENDU), 2)
        rattaches = [t for t in self.tickets if t["equipe"] is None and (self.rattache(t))]
        self.assertTrue(any(t["type"] == "Task" for t in rattaches) and any(t["type"] == "Bug" for t in rattaches))

    def test_part_bloquee_par_une_autre_equipe(self):
        # lien « blocks » porté par le bloqueur, cible : l'élément bloqué ; seuls comptent les liens entre équipes différentes
        bloques = defaultdict(set)
        for t in self.tickets:
            for cible, genre in t["liens"]:
                c = self.par_cle[cible]
                if genre == "blocks" and t["equipe"] and c["equipe"] and t["equipe"] != c["equipe"] and c["resolu"]:
                    bloques[(c["equipe"], trimestre(c))].add(c["cle"])
        self.assertEqual({k: len(v) for k, v in bloques.items()}, t1.BLOCAGES_ATTENDUS)
        valeurs = list(t1.BLOCAGES_ATTENDUS.values())
        self.assertTrue(any(v < SEUIL_MASQUAGE for v in valeurs), "une cellule sous 5, à masquer")
        self.assertTrue(any(v == SEUIL_MASQUAGE for v in valeurs), "une cellule exactement à 5")
        self.assertTrue(any(v > SEUIL_MASQUAGE for v in valeurs))
        # un lien « blocks » dans la même équipe existe et ne compte pas
        self.assertTrue(any(g == "blocks" and self.par_cle[c]["equipe"] == t["equipe"] for t in self.tickets for c, g in t["liens"]))

    def test_les_taches_sans_equipe_ne_changent_pas_le_debit_de_l_equipe_de_leur_story(self):
        # aucune équipe ne reçoit le débit d'un ticket sans équipe : l'équipe d'un ticket est portée par le ticket seul
        for t in self.tickets:
            if t["equipe"] is None:
                self.assertEqual(t["equipes"], [])


class BranchementSurLeChargeur(unittest.TestCase):
    """Tâche 14.2, sans base : le jeu de la tranche 1 est écrit par le chargeur de la tranche 0, ses équipes entrent dans l'ensemble contrôlé,
    ses noms de statut prêt et de type de lien sont importés du référentiel synthétique (R-20261029-21)."""

    def setUp(self):
        self.supplement = t1.supplement(MAINTENANT)

    def test_le_statut_pret_est_celui_du_referentiel_synthetique(self):
        import referentiel_synthetique as rs
        self.assertEqual(t1.STATUT_PRET, rs.STATUT_PRET)
        statuts = {x for t in self.supplement[0] for _, de, vers in t["transitions"] for x in (de, vers)}
        self.assertEqual(statuts, {"To Do", "In Progress", "Done", rs.STATUT_PRET})

    def test_le_chargeur_ecrit_transitions_et_liens_avec_le_type_du_referentiel(self):
        import referentiel_synthetique as rs
        from test_chargeur import FausseConnexion
        conn = FausseConnexion()
        nombre = base.charger(conn, MAINTENANT, self.supplement, {"blocks": rs.TYPE_LIEN_BLOQUE})
        self.assertEqual(nombre, len(base.construire(MAINTENANT)) + len(self.supplement[0]))
        ecritures = conn.ecritures()
        self.assertEqual(sum(e.startswith("INSERT INTO flow.transitions") for e in ecritures),
                         sum(len(t["transitions"]) for t in self.supplement[0]))
        self.assertEqual(sum(e.startswith("INSERT INTO flow.links") for e in ecritures), sum(len(t["liens"]) for t in self.supplement[0]))
        self.assertGreater(sum(e.startswith("INSERT INTO flow.links") for e in ecritures), 0)

    def test_sans_supplement_le_chargeur_n_ecrit_ni_transition_ni_lien(self):
        from test_chargeur import FausseConnexion
        conn = FausseConnexion()
        base.charger(conn, MAINTENANT)
        self.assertEqual([e for e in conn.ecritures() if "transitions" in e or "flow.links" in e], [])

    def test_les_equipes_de_la_tranche_1_entrent_dans_l_ensemble_controle(self):
        from test_chargeur import FausseConnexion
        conn = FausseConnexion(equipes=[*sorted(base.EQUIPES_GENERIQUES), *t1.EQUIPES_TRANCHE1])
        base.charger(conn, MAINTENANT, self.supplement)                       # aucune équipe de la tranche 1 ne refuse le chargement
        with self.assertRaises(base.RefusJeu):
            base.charger(FausseConnexion(equipes=["équipe E"]), MAINTENANT)   # sans le supplément, une équipe de la tranche 1 déjà en base est refusée

    def test_une_ligne_d_une_equipe_hors_ensemble_refuse_en_nommant_le_code(self):
        from test_chargeur import FausseConnexion
        intrus = dict(self.supplement[0][0], equipe="équipe Z", equipes=["équipe Z"])
        conn = FausseConnexion()
        with self.assertRaises(base.RefusJeu) as refus:
            base.charger(conn, MAINTENANT, ([intrus], t1.EQUIPES_TRANCHE1))
        self.assertIn("équipe Z", str(refus.exception))
        self.assertEqual(conn.instructions, [])                                # refusé avant toute écriture


class TrancheEtVuesAvecBase(aide_base.AvecBase):
    """Tâche 14.2, avec la base jetable (bash tools/dbtest.sh mothra_donnees ; sautés sans elle) : les vues de la tâche 15.1 rendent, sur ce jeu, un cycle
    time, une file prête et une part bloquée non vides, au moins une cellule NULL par vue (D13) ; et elles sont vides avant tout chargement."""

    VUES = ("v_team_lead_time_throughput", "v_team_ready_queue", "v_team_blocked_share")

    def lire(self, requete):
        self.conn.execute("SET ROLE pmzilla_flow_views")
        try:
            return self.conn.execute(requete).fetchall()
        finally:
            self.conn.execute("RESET ROLE")

    def test_vues_vides_avant_tout_chargement(self):
        for vue in self.VUES:
            self.assertEqual(self.lire(f"SELECT count(*) FROM flow.{vue}"), [(0,)], vue)

    def test_les_vues_de_la_tranche_1_sur_le_jeu_charge(self):
        import referentiel_synthetique as rs
        maintenant = datetime.now(timezone.utc)
        self.conn.commit()           # le chargeur veut une connexion au repos
        base.charger(self.conn, maintenant, t1.supplement(maintenant), {"blocks": rs.TYPE_LIEN_BLOQUE})
        rs.charger(self.conn, maintenant.date(), noms_du_jeu={
            "statuts": {s: c for _, _, c, s, _ in base.GROUPES}, "type_defaut": base.TYPE_DEFAUT,
            "statut_pret": rs.STATUT_PRET, "type_lien_bloquant": rs.TYPE_LIEN_BLOQUE})
        self.conn.commit()
        cycle = self.lire("SELECT items_ct, cycle_median_days FROM flow.v_team_lead_time_throughput")
        pret = self.lire("SELECT ready FROM flow.v_team_ready_queue")
        bloque = self.lire("SELECT blocked_n, blocked FROM flow.v_team_blocked_share")
        self.assertTrue(any(x[0] is not None and x[1] is not None for x in cycle), "un cycle time non vide")
        self.assertTrue(pret, "une file prête non vide")
        self.assertTrue(any(x[1] is not None for x in bloque), "une part bloquée non vide")
        for nom, lignes in (("cycle", cycle), ("file prête", pret), ("part bloquée", bloque)):
            self.assertTrue(any(v is None for ligne in lignes for v in ligne), f"{nom} : au moins une cellule NULL (D13)")


if __name__ == "__main__":
    unittest.main()
