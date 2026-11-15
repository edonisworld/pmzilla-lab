"""
Verdicts attendus du jeu de la tranche 1, lus sur les vues MASQUÉES (R-20261104-42, question 1 : le jeu est corrigé sans toucher à
VERDICTS_ATTENDUS, avec d'abord ce test, qui rejoue la relation T3 et la règle de série).

test_tranche1.py recalcule les verdicts sur les tickets, sans masquage. Ici, le jeu passe par le chemin que suit le serveur :

    tickets -> lignes de v_team_lead_time_throughput et de v_team_weekly_resolved (comptes vrais, les mêmes tickets et les mêmes définitions
    que db/migrations/0026 et 0030) -> relation T3 (tools/flow_views.py : _t3_retires, lignes_publiees ; copie TypeScript :
    mothra/contract/src/masquage.ts, retiresT3 et lecturesPassent, lignes 110 à 174) -> masquer_vue (cellules, paires, règle de série :
    flow_views._masque_debit, copie TypeScript visibiliteDebit, lignes 178 à 247) -> lecture de la fiche (copie Python de
    mothra/contract/src/corps-fiche.ts, lignes 267 à 386, et de verdict.ts : h1Verdict, h5Verdict, referenceH5, attachmentSignal, verdictFinal).

Deux choses sont affirmées pour chaque équipe de VERDICTS_ATTENDUS : les cellules que la fiche lit ne sont pas masquées là où le verdict
attendu l'exige, puis le verdict obtenu égale le verdict attendu. Un écart avec cellules lisibles est un défaut de calcul de la fiche, pas du jeu.

Copies : la lecture de la fiche (fiche_h1, fiche_h5, h5_verdict, mesure) copie mothra/contract/src/corps-fiche.ts et verdict.ts, qui font foi ;
les lignes des vues copient les définitions de db/migrations/0026 et 0030. Aucun test ne compare automatiquement ces copies à leur source :
un changement de corps-fiche.ts, verdict.ts ou des vues 0026/0030 relit ce module dans la même branche. Tombe quand fiches-calcul.test.ts
compare le jeu de la tranche 1 à VERDICTS_ATTENDUS sur la base jetable.

    bash tests/run_all.sh mothra_donnees
"""
from __future__ import annotations

import math
import sys
import unittest
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(DOSSIER))
import jeu_synthetique as base  # noqa: E402
import tranche1 as t1  # noqa: E402
import test_tranche1 as tt  # noqa: E402  (ses constantes de départ et ses fonctions de lecture des tickets)

sys.path.insert(0, str(DOSSIER.parents[1] / "tools"))
import flow_views as fv  # noqa: E402

MAINTENANT = base.INSTANT_FIXE
JOUR = timedelta(days=1)
SEUIL = 5
NOMS_DEBIT = ["team", "period", "quarter_start", "throughput", "items_lt", "lead_median_days", "lead_p85_days", "items_ct",
              "cycle_median_days", "cycle_p85_days", "items_old", "items_without_commitment"]
NOMS_HEBDO = ["team", "type", "week_start", "tickets"]
TYPES_DEBIT = ("Story", "Task")
# Valeurs de départ des seuils (mêmes valeurs que mothra/server/test/db/fiches-calcul.test.ts, SEUILS) ; les tailles viennent de test_tranche1.
H5_CONFIG = {"band": 0.2, "double_band": 0.4, "run_rises": 2, "run_min_cumulative_rise": 0.1, "floor": 0.8, "low_floor": 0.6}
H1_BAS, H1_HAUT = 1.5, 3.0


def arrondi(x: float) -> float:
    """verdict.ts : Math.round(x * 1e9) / 1e9."""
    return math.floor(x * 1e9 + 0.5) / 1e9


# ---------------------------------------------------------------------------------------------------------------------------------------
# Les vues, d'après les tickets
# ---------------------------------------------------------------------------------------------------------------------------------------

def lignes_hebdo(tickets) -> list[tuple]:
    """v_team_weekly_resolved, comptes vrais, pour les types du débit : (équipe, type, lundi UTC, nombre)."""
    comptes: dict = defaultdict(int)
    for t in tickets:
        if t["equipe"] and t["resolu"] and t["type"] in TYPES_DEBIT:
            jour = t["resolu"].date()
            comptes[(t["equipe"], t["type"], jour - timedelta(days=jour.weekday()))] += 1
    return [(e, ty, w, n) for (e, ty, w), n in sorted(comptes.items())]


NOUVELLES_COLONNES = ("lead_median_days_excl_old", "lead_p85_days_excl_old", "cycle_median_days_excl_old", "cycle_p85_days_excl_old")
NOMS_DEBIT_16 = NOMS_DEBIT + list(NOUVELLES_COLONNES)      # 0038 (22.1, D16) : les quatre colonnes sans les anciens, en fin de liste


def ligne_debit(equipe: str, periode: str, debut, items: list[dict], regle: str = "a") -> tuple:
    """Une ligne de v_team_lead_time_throughput (0026, 0038), comptes vrais : débit, lead time, cycle time (de l'entrée dans le statut prêt à la
    résolution), anciens (créés plus d'un an avant l'engagement), sans engagement, puis les quatre statistiques sans les anciens (0038).
    `regle` : « a » (R-20261106-59, Q1 (a)) la statistique sans les anciens n'est publiée que si items_old de la ligne est montré par la vue (0, ou au
    moins 5 avec un reste nul ou d'au moins 5) ; « ancienne » la règle de la première 0038 (m - o ou c - o d'au moins 5 seul), pour la mesure."""
    leads = [(t["resolu"] - t["cree"]) / JOUR for t in items if t["resolu"] >= t["cree"]]
    leads_sans, cycles_sans = [], []
    cycles, anciens = [], 0
    for t in items:
        engage = tt.engagement(t)
        ancien = engage <= t["resolu"] and engage - t["cree"] > timedelta(days=365)
        if t["resolu"] >= t["cree"] and not ancien:
            leads_sans.append((t["resolu"] - t["cree"]) / JOUR)
        if engage <= t["resolu"]:
            cycles.append((t["resolu"] - engage) / JOUR)
            if ancien:
                anciens += 1
            else:
                cycles_sans.append((t["resolu"] - engage) / JOUR)
    n, m, c = len(items), len(leads), len(cycles)
    o_montre = anciens == 0 or (anciens >= SEUIL and (c - anciens == 0 or c - anciens >= SEUIL))

    def stat(valeurs, p):
        return round(tt.percentile(valeurs, p), 1) if len(valeurs) >= SEUIL else None

    def stat_sans(valeurs, p):
        return stat(valeurs, p) if regle == "ancienne" or o_montre else None
    return (equipe, periode, debut, n, m, stat(leads, 0.5), stat(leads, 0.85), c, stat(cycles, 0.5), stat(cycles, 0.85), anciens, n - c,
            stat_sans(leads_sans, 0.5), stat_sans(leads_sans, 0.85), stat_sans(cycles_sans, 0.5), stat_sans(cycles_sans, 0.85))


class Vues:
    """Les lignes vraies des deux vues, la relation T3, puis les cellules que le serveur sert (masquer_vue)."""

    def __init__(self, tickets, maintenant=MAINTENANT, regle="a"):
        self.maintenant = maintenant
        self.debuts = [t1.debut_trimestre(maintenant, k + 1).date() for k in range(3)]      # indice k : 0 = dernier trimestre clos ; trois trimestres clos (R-20261114-49)
        par_equipe_k: dict = defaultdict(list)
        for t in tickets:
            if t["equipe"] and t["resolu"] and t["type"] in TYPES_DEBIT:
                k = tt.trimestre(t, maintenant)
                if 0 <= k <= 2:
                    par_equipe_k[(t["equipe"], k)].append(t)
        self.hebdo = lignes_hebdo(tickets)
        debit = []
        for equipe in sorted({e for e, _ in par_equipe_k}):
            for k in (2, 1, 0):
                if (equipe, k) in par_equipe_k:
                    debit.append(ligne_debit(equipe, "quarter", self.debuts[k], par_equipe_k[(equipe, k)], regle))
            debit.append(ligne_debit(equipe, "pooled_year", None, [t for k in range(3) for t in par_equipe_k.get((equipe, k), [])], regle))
        self.debit = debit
        # relation T3 : les (équipe, début de trimestre) dont le débit est retiré, puis les lignes hebdomadaires publiées (règle (a))
        self.retires = fv._t3_retires((NOMS_DEBIT_16, debit), (NOMS_HEBDO, self.hebdo), SEUIL)
        self.hebdo_publie = fv.lignes_publiees(fv.VUE_HEBDO, NOMS_HEBDO, self.hebdo, SEUIL, {fv.VUE_DEBIT: (NOMS_DEBIT_16, debit)})
        # la vue SQL publie un débit retiré comme un nul ; le serveur masque ensuite ses cellules (primaire, T3, paires, série)
        publie = [(*ligne[:3], None, *ligne[4:]) if ligne[1] == "quarter" and (ligne[0], ligne[2]) in self.retires else ligne for ligne in debit]
        cellules = fv.masquer_vue(fv.VUE_DEBIT, NOMS_DEBIT_16, publie, SEUIL, {fv.VUE_HEBDO: (NOMS_HEBDO, self.hebdo_publie)})
        self.cellules = {(ligne[0], ligne[1], ligne[2]): c for ligne, c in zip(debit, cellules)}
        self.vraies = {(ligne[0], ligne[1], ligne[2]): dict(zip(NOMS_DEBIT_16, ligne)) for ligne in debit}

    def ligne(self, equipe: str, k: int | None):
        """Les cellules de la ligne du trimestre k, ou de l'année groupée (k = None) ; None quand la vue n'a pas cette ligne."""
        cle = (equipe, "pooled_year", None) if k is None else (equipe, "quarter", self.debuts[k])
        return self.cellules.get(cle)

    def semaines(self, equipe: str, k: int) -> list[int]:
        """Les comptes hebdomadaires vrais des semaines qui touchent le trimestre k (diagnostic)."""
        debut, fin = self.debuts[k], fv._debut_suivant(self.debuts[k])
        return [n for e, _, w, n in self.hebdo if e == equipe and w + timedelta(days=7) > debut and w < fin]


def visible(cellule) -> bool:
    return cellule is not None and "masked" not in cellule and cellule["value"] is not None


def valeur(ligne, colonne):
    return ligne[colonne]["value"] if ligne is not None and visible(ligne[colonne]) else None


# ---------------------------------------------------------------------------------------------------------------------------------------
# La fiche : copie Python de corps-fiche.ts et de verdict.ts, sur les cellules servies
# ---------------------------------------------------------------------------------------------------------------------------------------

def deux_seuils(mesure: float, bas: float, haut: float) -> str:
    """verdict.ts, twoThresholds."""
    mesure = arrondi(mesure)
    if mesure < arrondi(bas):
        return "refuted"
    return "confirmed" if mesure > arrondi(haut) else "not_settled"


def fiche_h1(annee) -> tuple[str, list[str]]:
    """Première moitié de l'hypothèse 1 sur la ligne de l'année groupée (corps-fiche.ts 344 à 383, h1Verdict)."""
    # 22.1 (D16, R-20261105-30, R-20261106-59) : les rapports lisent les statistiques sans les anciens, et la taille d'échantillon est celle de H1
    # (items_lt et items_ct moins items_old, cellules montrées ; items_old masqué : aucune taille), comme corps-fiche.ts.
    n_lt = None if annee is None else fv.taille_echantillon_h1(annee, "lead")
    n_ct = None if annee is None else fv.taille_echantillon_h1(annee, "cycle")

    def rapport(a, b):
        return None if a is None or b is None or not b > 0 else a / b
    r_med = rapport(valeur(annee, "lead_median_days_excl_old"), valeur(annee, "cycle_median_days_excl_old"))
    r_p85 = rapport(valeur(annee, "lead_p85_days_excl_old"), valeur(annee, "cycle_p85_days_excl_old"))

    def atteint(taille):
        return n_lt is not None and n_ct is not None and n_lt >= taille and n_ct >= taille
    if r_med is None:
        return "insufficient_sample", ["median_masked"]
    if not atteint(tt.FIABLE_MEDIANE):
        return "insufficient_sample", ["median_insufficient_sample"]
    sur_mediane = deux_seuils(r_med, H1_BAS, H1_HAUT)
    if sur_mediane != "confirmed":
        return sur_mediane, []
    if r_p85 is None:
        return "not_settled", ["p85_masked"]
    if not atteint(tt.FIABLE_P85):
        return "not_settled", ["p85_insufficient_sample"]
    return ("confirmed" if deux_seuils(r_p85, H1_BAS, H1_HAUT) == "confirmed" else "not_settled"), []


def mesure(stat, effectif, taille):
    """lecture-vue.ts, mesureDeStatistique : (état, valeur)."""
    if stat is None or not visible(stat):
        return "masked", 0
    if effectif is None or not visible(effectif) or effectif["value"] < taille:
        return "insufficient_sample", 0
    return "value", stat["value"]


def fiche_h5(vues: Vues, equipe: str) -> str:
    """Hypothèse 5 : trois trimestres clos (du plus ancien au plus récent : k = 2 à 0), référence, h5Verdict (corps-fiche.ts 277 à 329). D14 : la référence
    n'existe qu'avec trois trimestres complets (`len(base_ref) < 3` ci-dessous) ; sinon « échantillon insuffisant », sans règle à deux trimestres."""
    fenetre = [2, 1, 0]
    trimestres = []
    for k in fenetre:
        ligne = vues.ligne(equipe, k)
        eff = None if ligne is None else ligne["items_ct"]
        med = mesure(None if ligne is None else ligne["cycle_median_days"], eff, tt.FIABLE_MEDIANE)
        p85 = mesure(None if ligne is None else ligne["cycle_p85_days"], eff, tt.FIABLE_P85)
        debit = valeur(ligne, "throughput")
        trimestres.append({"median": med[1], "p85": p85[1], "throughput": debit, "med_ok": med[0] == "value", "p85_ok": p85[0] == "value"})
    premier = next((i for i, k in enumerate(fenetre) if vues.ligne(equipe, k) is not None), -1)
    if vues.ligne(equipe, 0) is None or premier < 0:
        return "insufficient_sample"
    presents = trimestres[premier:]
    autres = presents[:-1]

    def complet(q):
        return q["med_ok"] and q["p85_ok"] and q["throughput"] is not None
    base_ref = [q for q in presents if complet(q)] if all(complet(q) for q in autres) else []
    if len(base_ref) < 3:
        return "insufficient_sample"
    derniers = base_ref[-4:]
    ref = {c: sum(q[c] for q in derniers) / len(derniers) for c in ("median", "p85", "throughput")}
    return h5_verdict(presents, ref)


def h5_verdict(quarters: list[dict], ref: dict) -> str:
    """verdict.ts, h5Verdict (la configuration est celle de H5_CONFIG)."""
    cfg = H5_CONFIG
    if all(not q["med_ok"] and not q["p85_ok"] and q["throughput"] is None for q in quarters):
        return "insufficient_sample"

    def ecart(x, r):
        return arrondi(abs(x - r) / r)
    comparaisons = hors_double = 0
    tout_dans_la_bande, sous_plancher_bas, sous_plancher, serie_atteinte = True, False, False, False
    serie: list[float] = []
    for q in quarters:
        ecarts = []
        if q["med_ok"]:
            ecarts.append(ecart(q["median"], ref["median"]))
        if q["p85_ok"]:
            ecarts.append(ecart(q["p85"], ref["p85"]))
        if ecarts:
            comparaisons += 1
            if max(ecarts) > cfg["double_band"]:
                hors_double += 1
            if max(ecarts) > cfg["band"]:
                tout_dans_la_bande = False
        if q["throughput"] is not None:
            rapport = arrondi(q["throughput"] / ref["throughput"])
            sous_plancher_bas |= rapport < cfg["low_floor"]
            sous_plancher |= rapport < cfg["floor"]
        if not q["med_ok"]:
            serie = []
            continue
        serie = [*serie, q["median"]] if serie and q["median"] > serie[-1] else [q["median"]]
        if len(serie) - 1 >= cfg["run_rises"]:
            depart = serie[len(serie) - 1 - cfg["run_rises"]]
            if arrondi(q["median"] / depart) >= arrondi(1 + cfg["run_min_cumulative_rise"]):
                serie_atteinte = True
    if hors_double >= 2 or serie_atteinte or sous_plancher_bas:
        return "refuted"
    if comparaisons == 0:
        return "not_settled" if sous_plancher else "insufficient_sample"
    if tout_dans_la_bande and not sous_plancher:
        return "not_settled" if any(q["throughput"] is None for q in quarters) else "confirmed"
    return "not_settled"


def signal_rattachement(tickets, maintenant=MAINTENANT) -> bool:
    """attachmentSignal sur v_task_without_team_share (masquage.ts 319 à 328 : la part se montre quand la partie, le reste et le tout atteignent 5)."""
    def part(k):
        taches = [t for t in tickets if t["type"] == "Task" and t["resolu"] and tt.trimestre(t, maintenant) == k]
        sans = sum(1 for t in taches if t["equipe"] is None)
        if sans < SEUIL or len(taches) - sans < SEUIL or len(taches) < SEUIL:
            return None
        return round(100.0 * sans / len(taches), 1)
    jugee, reference = part(0), [p for p in (part(1), part(2)) if p is not None]      # D13 : les deux trimestres qui précèdent le jugé (trois avant)
    if jugee is None or not reference:
        return False
    return arrondi(abs(jugee - sum(reference) / len(reference))) > 10.0


ETIQUETTES = {"refuted": "réfuté", "not_settled": "non tranché", "confirmed": "confirmé"}


def etiquette(brut: str, motifs: list[str]) -> str:
    """Le nom français du jeu : « masqué » quand la médiane l'est, « échantillon insuffisant » sinon."""
    if brut == "insufficient_sample":
        return "masqué" if "median_masked" in motifs else "échantillon insuffisant"
    return ETIQUETTES[brut]


# ---------------------------------------------------------------------------------------------------------------------------------------
# Les tests
# ---------------------------------------------------------------------------------------------------------------------------------------

class RegleT3EtSerie(unittest.TestCase):
    """La relation T3 et la règle de série sur des cas minimaux : ce qui rend la fiche de l'équipe E « masquée » avec six semaines à un ticket."""

    def test_six_semaines_a_un_ticket_retirent_le_debit(self):
        # S = 6 = k x lo : les six lignes masquées seraient toutes à 1, le débit les fixerait (masquage.ts:121, s !== k * LO_HEBDO)
        self.assertFalse(fv._t3_lectures_passent(6, [("in", None)] * 6, SEUIL))

    def test_une_semaine_a_deux_tickets_suffit(self):
        self.assertTrue(fv._t3_lectures_passent(6, [("in", None)] * 5, SEUIL))
        self.assertTrue(fv._t3_lectures_passent(5, [("in", None)] * 3, SEUIL))

    def test_un_trimestre_masque_masque_toute_l_annee_groupee(self):
        # deux trimestres de 6 et un de 4 (trois trimestres clos, R-20261114-49 ; trois de 6 et un de 4 avant) : la série masque l'année (masquage.ts:224-246),
        # même si l'année compte 16 (6 + 6 + 4)
        lignes = [("x", "quarter", fv.date(2025, 1 + 3 * k, 1), n, n, 20.0, 20.0, n, 5.0, 5.0, 0, 0) for k, n in enumerate((6, 6, 4))]
        lignes.append(("x", "pooled_year", None, 16, 16, 20.0, 20.0, 16, 5.0, 5.0, 0, 0))
        cellules = fv.masquer_vue(fv.VUE_DEBIT, NOMS_DEBIT, lignes, SEUIL)
        self.assertTrue(visible(cellules[1]["items_ct"]))
        self.assertFalse(visible(cellules[3]["items_ct"]))
        self.assertFalse(visible(cellules[3]["throughput"]))


# Les instants de chargement : l'instant fixe des tests, la date du constat (le 4 novembre 2026), puis un instant par trimestre jusqu'en 2027. Les
# trimestres civils ne commencent pas le même jour de la semaine d'un instant à l'autre : les semaines des vues, donc la relation T3, en dépendent.
# Le jeu doit tenir à chacun (la base d'essai charge le jeu à l'heure réelle).
INSTANTS = (MAINTENANT, MAINTENANT.replace(year=2026, month=11, day=4), MAINTENANT.replace(year=2027, month=2, day=10),
            MAINTENANT.replace(year=2027, month=5, day=12), MAINTENANT.replace(year=2027, month=8, day=11))


class VerdictsLusSurLesVuesMasquees(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cas = []
        for instant in INSTANTS:
            tickets = t1.construire_tranche1(instant)
            cls.cas.append((instant, Vues(tickets, instant), signal_rattachement(tickets, instant)))

    def diagnostic(self, v: Vues, equipe: str) -> str:
        masquees = []
        for k in (None, 0, 1, 2):
            ligne = v.ligne(equipe, k)
            if ligne is not None:
                cols = [c for c in ("throughput", "items_lt", "items_ct", "lead_median_days", "cycle_median_days", "cycle_p85_days")
                        if not visible(ligne[c])]
                masquees.append(f"{'année' if k is None else f'k={k}'}: {cols or 'rien de masqué'}")
        retires = sorted(f"k={v.debuts.index(d)}" for e, d in v.retires if e == equipe and d in v.debuts)
        hebdo = {f"k={k}": sorted(v.semaines(equipe, k), reverse=True) for k in range(3) if v.semaines(equipe, k)}
        vrais = {("année" if k is None else f"k={k}"): v.vraies[(equipe, "pooled_year", None) if k is None else (equipe, "quarter", v.debuts[k])]["throughput"]
                 for k in (None, 0, 1, 2) if ((equipe, "pooled_year", None) if k is None else (equipe, "quarter", v.debuts[k])) in v.vraies}
        return f"{equipe} | débits vrais {vrais} | T3 retire {retires} | comptes hebdo {hebdo} | masqué : {'; '.join(masquees)}"

    def test_les_cellules_lues_par_la_fiche_ne_sont_pas_masquees_la_ou_le_verdict_l_exige(self):
        for instant, v, _ in self.cas:
            for equipe in t1.VERDICTS_SEUILS_H1:
                with self.subTest(instant=instant.date().isoformat(), equipe=equipe, fiche="h1"):
                    annee = v.ligne(equipe, None)
                    if t1.VERDICTS_ATTENDUS[equipe][0] == "masqué":
                        self.assertFalse(visible(annee["cycle_median_days"]) if annee else False, self.diagnostic(v, equipe))
                        continue
                    self.assertIsNotNone(annee, equipe)
                    lues = ["items_lt", "items_ct", "lead_median_days", "cycle_median_days"]
                    if v.vraies[(equipe, "pooled_year", None)]["items_ct"] >= tt.FIABLE_P85:
                        lues += ["lead_p85_days", "cycle_p85_days"]      # assez d'éléments pour un P85 : la fiche le lit
                    masquees = [c for c in lues if not visible(annee[c])]
                    self.assertEqual(masquees, [], self.diagnostic(v, equipe))
            for equipe in t1.VERDICTS_SEUILS_H5:
                for k in range(3):
                    with self.subTest(instant=instant.date().isoformat(), equipe=equipe, fiche="h5", k=k):
                        ligne = v.ligne(equipe, k)
                        self.assertIsNotNone(ligne, equipe)
                        masquees = [c for c in ("throughput", "items_ct", "cycle_median_days", "cycle_p85_days") if not visible(ligne[c])]
                        self.assertEqual(masquees, [], self.diagnostic(v, equipe))

    def obtenu(self, v: Vues, signal: bool, equipe: str) -> tuple:
        if equipe in t1.VERDICTS_SEUILS_H1:
            brut, motifs = fiche_h1(v.ligne(equipe, None))
            return tt.verdict_attendu(etiquette(brut, motifs), "h1", signal)
        return tt.verdict_attendu(etiquette(fiche_h5(v, equipe), []), "h5", signal)

    def test_le_verdict_obtenu_egale_le_verdict_attendu(self):
        for instant, v, signal in self.cas:
            self.assertTrue(signal)
            for equipe in t1.VERDICTS_ATTENDUS:
                with self.subTest(instant=instant.date().isoformat(), equipe=equipe):
                    obtenu = self.obtenu(v, signal, equipe)
                    if equipe == t1.TEMOIN_ANCIENS:      # le verdict seul ici ; ses motifs : test_les_motifs_du_temoin_des_anciens
                        obtenu = (obtenu[0], t1.VERDICTS_ATTENDUS[equipe][1])
                    self.assertEqual(obtenu, t1.VERDICTS_ATTENDUS[equipe], self.diagnostic(v, equipe))

    def test_les_motifs_du_temoin_des_anciens(self):      # le décorateur expectedFailure est retiré (22.1, R-20261105-30, R-20261106-59) : la fiche lit les colonnes sans les anciens
        # Défaut de la vue (0030), non masqué, pas de la fiche : les cellules de l'équipe Q sont toutes lues, mais la ligne de l'année groupée de
        # flow.v_team_lead_time_throughput compte les six éléments anciens dans la médiane et le P85 (ils ne sont que comptés à part dans items_old),
        # contre mothra-hypotheses/spec.md « counted apart, out of the ratio » ; la fiche lit donc « confirmé » avant l'interdiction de D20 et affiche
        # le motif defects_without_team, que VERDICTS_ATTENDUS (anciens exclus du verdict) n'a pas. La fiche ne peut pas corriger seule (design.md de mothra-slices,
        # « never rebuilds a yearly statistic from quarterly rows »). Le jeu n'est pas modifié (R-20261104-42, question 1) : une migration neuve corrigera la vue ;
        # ce test tombe, avec son expectedFailure, à ce moment-là.
        for instant, v, signal in self.cas:
            self.assertEqual(self.obtenu(v, signal, t1.TEMOIN_ANCIENS), t1.VERDICTS_ATTENDUS[t1.TEMOIN_ANCIENS], instant.date().isoformat())

    def test_les_verdicts_attendus_sont_ceux_de_toutes_les_equipes_temoins(self):
        self.assertEqual(set(t1.VERDICTS_ATTENDUS), set(t1.VERDICTS_SEUILS_H1) | set(t1.VERDICTS_SEUILS_H5))


if __name__ == "__main__":
    unittest.main()
