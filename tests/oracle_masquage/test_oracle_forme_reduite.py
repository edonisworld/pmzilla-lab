"""Oracle de la forme réduite des fiches F-H5 et F-H1 (mothra-slices, tâche 20.3 ; conception D34 point 5 ; change masking-sums, oracle D8).

    uv run --with pyyaml --with "psycopg[binary]" python -W ignore -m unittest discover -s tests/db -p "test_oracle_forme_reduite.py" -q

Sans base : le module n'importe que l'oracle (oracle_masquage.py) et masquer_vue de tools/flow_views.py, telle quelle (jamais copiée, jamais
modifiée). Il tourne aussi au dbtest de l'auteur avec le reste de tests/db. Données synthétiques : équipes A et B, ligne « sans équipe », comptes
inventés, jamais un nom réel.

Ce que fait le test, pour chaque sorte de fiche (F-H5, F-H1) et chaque famille :
  1. la table brute est une colonne de cellules (une ligne de largeur 1 par cellule, ce qui rend l'élagage immédiat) : par semaine, les tickets
     résolus de l'équipe A et de l'équipe B par type (story, task) ; par trimestre, les tâches sans équipe, le travail non planifié (une seule
     cellule : les deux types de ce côté ne sont publiés que par leur somme, la vue ne les montre pas séparément) et la file prête de l'équipe A ;
  2. publier(brut, seuil) construit les lignes des vues que lit l'attaquant (v_team_weekly_resolved, v_team_lead_time_throughput avec la ligne
     de l'année groupée, v_task_without_team_share, v_unplanned_share, v_team_ready_queue), leur applique fv.masquer_vue, puis ajoute les cellules
     réduites de D34 comme CHAÎNES (jamais None : l'oracle prend None pour une cellule masquée de la table brute) ;
  3. une famille est « bien posée » si les vues seules ne fuient pas (garde de base) ; l'attendu est alors analyser(...)["fuites"] == [].
     Un échec nomme la sorte, la famille et la relation.
  4. témoin : une famille dont on ajoute une cellule interdite (le débit en clair) doit fuir, preuve que le test voit une fuite.

Relation T3 (masking-sums D17, R-20261031-07, tâche 13.1) : l'image publiée d'une cellule de v_team_weekly_resolved est « absente » (la chaîne ABSENT)
pour un zéro brut (une ligne de GROUP BY n'existe pas pour un compte nul) ou pour une ligne que la règle (a) retire, None pour une ligne présente
dont le compte est masqué, sa valeur sinon. Le zéro brut n'est plus élagué pour ces cellules. Les cellules absentes sont analysées comme les masquées
(`cellules_en_plus` de oracle_masquage.analyser) : un zéro ou une valeur déduite d'une ligne retirée serait une fuite. masquer_vue reçoit `liees` (la
vue hebdomadaire pour le débit, le débit pour la vue hebdomadaire) et lignes_publiees dit quelles lignes sont retirées. Les trimestres et les semaines
sont de vraies dates (le premier lundi après le début de chaque trimestre, jamais une semaine à cheval).

Limites assumées (écrites ici, pas ailleurs) :
  * Énumération exhaustive sur range(0, 13) par cellule, élaguée (une cellule visible de l'image observée est fixée) : seules les cellules
    masquées ou absentes varient (13 ** k tables pour k cellules). Aucune limite de k dans le design : aucune famille n'est refusée ni
    affaiblie ; la famille à 4 cellules masquées ou absentes (28 561 tables) est gardée. taille_max_somme = 3 borne seulement les sommes examinées
    (au-delà, la durée croît) : question pour l'auteur si des sommes de 4 cellules doivent être examinées.
  * Une fuite est signalée, jamais corrigée ni contournée : si un cas fuit, il prend unittest.expectedFailure avec un commentaire citant
    R-20261031-01 (Q12) et « ligne du registre de 20.4 à écrire par l'auteur le 2026-11-08 » ; la sorte reste sur le jeu synthétique.
  * Les relations T1 à T13 entre vues (masking-sums D16, D34 point 4) ne sont pas modélisées : tasks_done et unplanned_n sont des constantes
    visibles indépendantes des cellules, pour isoler ce que la forme réduite ajoute. Le seul lien entre vues gardé est débit = story + task.
  * Médianes et P85 : valeurs publiées sans relation aux comptes ; seul leur état (masquée, échantillon insuffisant) dépend d'un effectif.
  * waitShares (mothra-demo-habillage D3b, tâche 4.3, R-20261101-32) : F-H1 ajoute à ses cellules réduites les deux barres (médiane et P85 de
    l'année groupée) et les deux repères de seuil, comme les valeurs qu'ils représentent (la part d'attente 100 x (1 - 1/rapport), ou l'état :
    masquée, échantillon insuffisant, non comparable). Les seuils adoptés des repères sont inventés (1,5 et 2,5), constants ; les médianes et P85
    publiés étant constants, les barres le sont aussi : le test dit ce que l'ajout des cellules change à l'attaquant (rien de plus que l'état
    des médianes), il ne prouve pas la formule du contrat, fixée par son propre test. Aucun module de tests/db n'est lancé par un agent.
  * Le service de verdict est supposé connaître les comptes vrais (modèle le plus informatif, donc le plus prudent) : la référence de F-H5 est
    la moyenne des trimestres vrais, même si l'un d'eux est masqué dans la vue ; seule la position d'un trimestre masqué est « masked ».
  * Le verdict et ses raisons sont modélisés en partie (verdict_fh5, plafond de D22 pour F-H1) ; la bande sur les médianes et P85 et la
    montée de deux hausses consécutives ne le sont pas (valeurs publiées sans relation aux comptes). Le domaine de chaque cellule brute des
    lignes de v_team_weekly_resolved et de la file prête commence à 1 (BORNES lo = 1) : un zéro est refusé dans l'élagage, pas dans l'oracle.
  * v_team_status n'est pas modélisé : instantané courant, sans trimestre, il n'entre dans aucune relation des cellules réduites.
  * EXPLICATION « FILE PRÊTE » NON VÉRIFIÉE : FILE_PRETE_MIN = 6 est une hypothèse de test, non vérifiée (le design ne fixe ni seuil ni règle
    « masquée donne not_measurable » ; seuil gelé par l'auteur le 16/11, après la publication du 9). Le message de commit et la ligne de 20.4
    doivent dire « explication file prête non vérifiée ».
  * Paramètres : plancher 80 %, plancher bas 60 %, écart du signal 10 points, taille de fiabilité de la médiane 10 et du P85 20 (annexe de
    design.md). Le seuil de l'explication « file prête » (FILE_PRETE_MIN) n'est pas dans le design : HYPOTHÈSE DE TEST inventée (le design n'en fixe pas ; seuil gelé par l'auteur le 16/11 ; valeur non changée ici) ; la
    part bloquée n'est pas modélisée (aucun seuil écrit). L'explication du travail non planifié est « not_measurable » (defects_without_team),
    constante : aucune relation.
"""
import sys
import unittest
from datetime import date, timedelta
from fractions import Fraction
from functools import partial
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import flow_views as fv  # noqa: E402
import oracle_masquage as oracle  # noqa: E402

SEUIL = fv.PLANCHER
VALEURS = range(13)
TAILLE_MAX_SOMME = None                # toutes les tailles de somme (revue 20.3, constat 3)
MEDIANE_MIN, P85_MIN = 10, 20
PLANCHER_DEBIT, PLANCHER_BAS = Fraction(4, 5), Fraction(3, 5)
ECART_SIGNAL = 10                      # points
FILE_PRETE_MIN = 6                     # valeur inventée pour le test (voir l'en-tête)
SEUILS_ADOPTES_H1 = (Fraction(3, 2), Fraction(5, 2))   # seuils adoptés de F-H1 inventés pour les repères de waitShares (voir reperes_attente)
EQUIPE_A, EQUIPE_B = "equipe A", "equipe B"
TACHES_FAITES, ELEMENTS_FAITS = 60, 120    # constantes visibles de la vue de part et de la vue du non planifié (voir l'en-tête)
NOMS_W = ["team", "type", "week_start", "tickets"]
NOMS_LEAD = ["team", "period", "quarter_start", "throughput", "items_lt", "lead_median_days", "lead_p85_days", "items_ct",
             "cycle_median_days", "cycle_p85_days", "items_old", "items_without_commitment"]
NOMS_PART = ["quarter_start", "tasks_done", "tasks_without_team", "share_percent"]
NOMS_NONPLAN = ["quarter_start", "unplanned_n", "unplanned", "share_percent"]
NOMS_PRETE = ["team", "quarter_start", "ready"]
MASQUE = "masque"
ABSENT = "absent"                      # image d'une ligne qui n'est pas publiée : zéro brut, ou ligne retirée par la règle (a) de T3 (D17)
DEBUTS = [date(2025, 10, 1), date(2026, 1, 1), date(2026, 4, 1), date(2026, 7, 1)]      # débuts de trimestres civils (un mercredi ou un jeudi)


def lundi_apres(debut: date) -> date:
    """Le premier lundi à partir du début du trimestre : une semaine entièrement dans le trimestre (jamais à cheval sur sa limite)."""
    return debut + timedelta(days=(7 - debut.weekday()) % 7)


def visible(cellule: dict) -> bool:
    return "masked" not in cellule and cellule["value"] is not None


def rep(cellule: dict):
    return cellule["value"] if visible(cellule) else MASQUE


class Forme:
    """Géométrie d'une famille : `semaines` semaines par trimestre, `trimestres` trimestres. Cellules : 4 par semaine (A story, A task, B story,
    B task) puis 3 par trimestre (tâches sans équipe, non planifié, file prête de A)."""

    def __init__(self, semaines: int, trimestres: int, cheval_fin: bool = False):
        self.S, self.Q = semaines, trimestres
        self.W = semaines * trimestres
        self.cheval_fin = cheval_fin       # revue de T3 : la dernière semaine du dernier trimestre chevauche sa fin (lundi 2026-03-30 pour le trimestre du 2026-01-01)

    def brut(self, sem, tri) -> tuple:
        plat = [v for w in sem for v in w] + [v for t in tri for v in t]
        assert len(plat) == 4 * self.W + 3 * self.Q
        return tuple((v,) for v in plat)

    def decoder(self, table):
        v = [r[0] for r in table]
        sem = [tuple(v[4 * k:4 * k + 4]) for k in range(self.W)]
        tri = [tuple(v[4 * self.W + 3 * q:4 * self.W + 3 * q + 3]) for q in range(self.Q)]
        return sem, tri


class Vues:
    """Cellules masquées des vues lues par l'attaquant, plus les comptes vrais utiles aux états."""

    def __init__(self, forme: Forme, table, seuil: int):
        sem, tri = forme.decoder(table)
        self.sem, self.tri = sem, tri
        lignes, self.rang_hebdo = [], {}                      # (semaine, position dans la semaine) -> rang de la ligne ; un zéro n'a pas de ligne
        for k, cellules_semaine in enumerate(sem):
            q, j = divmod(k, forme.S)
            lundi = lundi_apres(DEBUTS[q]) + timedelta(days=7 * j)
            if forme.cheval_fin and k == forme.W - 1:
                veille = DEBUTS[q + 1] - timedelta(days=1)                       # dernier jour du dernier trimestre
                lundi = veille - timedelta(days=veille.weekday())                # le lundi de la semaine qui le contient : elle chevauche la limite
            for position, (equipe, type_) in enumerate(((EQUIPE_A, "story"), (EQUIPE_A, "task"), (EQUIPE_B, "story"), (EQUIPE_B, "task"))):
                if cellules_semaine[position] != 0:
                    self.rang_hebdo[(k, position)] = len(lignes)
                    lignes.append((equipe, type_, lundi, cellules_semaine[position]))
        self.debit = {"A": [], "B": []}                       # vrais débits par trimestre
        for q in range(forme.Q):
            ws = sem[q * forme.S:(q + 1) * forme.S]
            self.debit["A"].append(sum(w[0] + w[1] for w in ws))
            self.debit["B"].append(sum(w[2] + w[3] for w in ws))
        lignes_lead, self.cles_lead, self.vide = [], [], set()
        for nom, equipe in (("A", EQUIPE_A), ("B", EQUIPE_B)):
            for q in range(forme.Q):
                n = self.debit[nom][q]
                lignes_lead.append((equipe, "quarter", DEBUTS[q], n, n, 3.0, 9.0, n, 2.0, 6.0, 0, 0))   # rapports 1,5 (revue 1b : jamais sous 1)
                self.cles_lead.append((nom, q))
                if n == 0:
                    self.vide.add((nom, q))                   # la vue n'a pas de ligne pour un débit nul : l'image est « absente »
            n = sum(self.debit[nom])
            lignes_lead.append((equipe, "pooled_year", None, n, n, 3.0, 9.0, n, 2.0, 6.0, 0, 0))   # rapports 1,5 : les barres peuvent être en valeur
            self.cles_lead.append((nom, "annee"))
            if n == 0:
                self.vide.add((nom, "annee"))
        # T3 (D17) : chaque vue lit l'autre ; les lignes retirées par la règle (a) sont absentes de l'image
        cl = fv.masquer_vue("v_team_lead_time_throughput", NOMS_LEAD, lignes_lead, seuil, {"v_team_weekly_resolved": (NOMS_W, lignes)})
        self.lead = {cle: c for cle, c in zip(self.cles_lead, cl)}
        liees_hebdo = {"v_team_lead_time_throughput": (NOMS_LEAD, lignes_lead)}
        publiees = set(fv.lignes_publiees("v_team_weekly_resolved", NOMS_W, lignes, seuil, liees_hebdo))
        self.retirees = {rang for rang, ligne in enumerate(lignes) if ligne not in publiees}
        self.hebdo = fv.masquer_vue("v_team_weekly_resolved", NOMS_W, lignes, seuil, liees_hebdo)
        pct = lambda p, t: round(100 * p / t)                 # noqa: E731
        self.part = fv.masquer_vue("v_task_without_team_share", NOMS_PART,
                                   [(DEBUTS[q], TACHES_FAITES, t[0], pct(t[0], TACHES_FAITES)) for q, t in enumerate(tri)], seuil)
        self.nonplan = fv.masquer_vue("v_unplanned_share", NOMS_NONPLAN,
                                      [(DEBUTS[q], ELEMENTS_FAITS, t[1], pct(t[1], ELEMENTS_FAITS)) for q, t in enumerate(tri)], seuil)
        self.prete = fv.masquer_vue("v_team_ready_queue", NOMS_PRETE, [(EQUIPE_A, DEBUTS[q], t[2]) for q, t in enumerate(tri)], seuil)

    def image_hebdo(self, k: int, position: int):
        """Image d'une cellule hebdomadaire brute : ABSENT (zéro brut, ou ligne retirée par la règle (a)), None (ligne présente au compte masqué),
        sa valeur sinon."""
        rang = self.rang_hebdo.get((k, position))
        if rang is None or rang in self.retirees:
            return ABSENT
        cellule = self.hebdo[rang]["tickets"]
        return cellule["value"] if visible(cellule) else None

    def cellules(self, forme):
        """Une cellule par ligne de la table brute : sa valeur si la vue la montre, None si elle est masquée, ABSENT si la ligne n'est pas publiée."""
        sortie = []
        for k in range(forme.W):
            sortie += [self.image_hebdo(k, j) for j in range(4)]
        for q in range(forme.Q):
            sortie += [c["value"] if visible(c) else None
                       for c in (self.part[q]["tasks_without_team"], self.nonplan[q]["unplanned"], self.prete[q]["ready"])]
        return tuple((x,) for x in sortie)

    def derivees(self, forme) -> tuple:
        """Cellules des vues qui ne sont pas une cellule brute (débits, effectifs, parts, états de médiane), toutes sans None."""
        sortie = []
        for cle in self.cles_lead:
            c = self.lead[cle]
            if cle in self.vide:                              # pas de ligne pour un débit nul : cinq cellules absentes
                sortie += [ABSENT] * 5
                continue
            sortie += [rep(c["throughput"]), rep(c["items_lt"]), rep(c["items_ct"]), rep(c["lead_median_days"]), rep(c["cycle_p85_days"])]
        for q in range(forme.Q):
            sortie += [rep(self.part[q]["share_percent"]), rep(self.nonplan[q]["share_percent"])]
        return tuple(sortie)


def etat_statistique(cellule: dict, effectif: int, minimum: int) -> str:
    if not visible(cellule):
        return "masked"
    return "insufficient_sample" if effectif < minimum else "sufficient"


def etat_couverture(cellule: dict, effectif: int) -> str:
    if not visible(cellule):
        return "coverage_masked"
    return "coverage_sufficient" if effectif >= P85_MIN else "coverage_insufficient"


def position_debit(vrai: int, reference: Fraction, cellule: dict) -> str:
    if not visible(cellule):
        return "masked"
    rapport = Fraction(vrai) / reference
    if rapport >= PLANCHER_DEBIT:
        return "throughput_within_band"
    return "throughput_under_floor" if rapport >= PLANCHER_BAS else "throughput_under_low_floor"


def etat_signal(forme: Forme, v: Vues) -> str:
    """Écart de la part des tâches sans équipe, trimestre jugé (le dernier) contre les trimestres de référence (les précédents) dont la part
    est visible ; part jugée masquée ou aucune référence visible : état masqué (jamais estimée)."""
    q = forme.Q - 1
    if not visible(v.part[q]["share_percent"]):
        return "tasks_without_team_share_masked"
    refs = [Fraction(100 * v.tri[r][0], TACHES_FAITES) for r in range(q) if visible(v.part[r]["share_percent"])]
    if not refs:
        return "tasks_without_team_share_masked"
    ecart = abs(Fraction(100 * v.tri[q][0], TACHES_FAITES) - sum(refs) / len(refs))
    return "tasks_attachment_signal" if ecart > ECART_SIGNAL else "tasks_attachment_signal_not_raised"


def etat_file_prete(forme: Forme, v: Vues) -> str:
    q = forme.Q - 1
    if not visible(v.prete[q]["ready"]):
        return "not_measurable"
    return "not_ruled_out" if v.tri[q][2] >= FILE_PRETE_MIN else "ruled_out"


def reduites_fh5(forme: Forme, v: Vues) -> tuple:
    """F-H5 (équipe A) : position de débit par trimestre (référence = moyenne des trimestres, trois au moins), état de la médiane et du P85 de
    chaque trimestre, couverture du trimestre jugé, états des explications, état du signal. Moins de trois trimestres : aucune position (Q1)."""
    sortie = []
    total = sum(v.debit["A"])
    if forme.Q >= 3 and total > 0:
        reference = Fraction(total, forme.Q)
        sortie += [position_debit(v.debit["A"][q], reference, v.lead[("A", q)]["throughput"]) for q in range(forme.Q)]
    else:
        sortie.append("no_position")
    for q in range(forme.Q):
        c = v.lead[("A", q)]
        sortie += [etat_statistique(c["cycle_median_days"], v.debit["A"][q], MEDIANE_MIN),
                   etat_statistique(c["cycle_p85_days"], v.debit["A"][q], P85_MIN)]
    q = forme.Q - 1
    signal = etat_signal(forme, v)
    sortie += [etat_couverture(v.lead[("A", q)]["items_ct"], v.debit["A"][q]), etat_file_prete(forme, v), "not_measurable", signal]
    sortie += verdict_fh5(sortie[:forme.Q] if forme.Q >= 3 and total > 0 else None, signal)
    return tuple(sortie)


def verdict_fh5(positions, signal) -> list:
    """Verdict et raisons de F-H5, modèle partiel (revue 20.3, constat 4) : sans référence, échantillon insuffisant ; un trimestre sous le
    plancher bas réfute (sur les trimestres non masqués) ; un débit masqué interdit « confirmed » (throughput_masked) ; le signal levé aussi.
    Non modélisés : la bande ±20 % et la double bande sur les médianes et P85, et la montée de deux hausses consécutives (les médianes sont des
    valeurs publiées sans relation aux comptes)."""
    if positions is None:
        return ["verdict:insufficient_sample"]
    if "throughput_under_low_floor" in positions:
        return ["verdict:refuted", "reason:throughput_under_low_floor"]
    raisons = []
    if "masked" in positions:
        raisons.append("reason:throughput_masked")
    if signal == "tasks_attachment_signal":
        raisons.append("reason:tasks_attachment_signal")
    if raisons or any(p != "throughput_within_band" for p in positions):
        return ["verdict:not_settled"] + raisons
    return ["verdict:confirmed"]


def barre_attente(lead: dict, cycle: dict, verdict_insuffisant: bool, effectif: int, minimum: int) -> str:
    """Barre de la part d'attente de F-H1 (waitShares, mothra-demo-habillage D3b ; décisions R-20261101-20 et -32), sous forme de CHAÎNE (jamais
    None) : l'ÉTAT de la barre, ou la VALEUR qu'elle représente, la part d'attente 100 x (1 - 1/rapport) du rapport délai sur cycle de l'année
    groupée. Même ordre que partsDAttente : rapport masqué (un des deux termes masqué) -> masquée ; effectif sous la taille de fiabilité ->
    échantillon insuffisant ; rapport sous 1 -> non comparable ; sinon la part, en fraction exacte. Les valeurs publiées des médianes et des P85
    sont des constantes sans relation aux comptes (voir l'en-tête) : la part en est une aussi."""
    if not visible(lead) or not visible(cycle):
        return "barre:masked"
    if verdict_insuffisant or effectif < minimum:      # le verdict « échantillon insuffisant » ôte toute part aux deux barres (Q121, D3b)
        return "barre:insufficient_sample"
    rapport = Fraction(lead["value"]) / Fraction(cycle["value"])
    if rapport < 1:
        return "barre:not_comparable"
    return "barre:" + str(100 - 100 / rapport)


def reperes_attente() -> list:
    """Les deux repères de seuil de waitShares, en part d'attente : des seuils adoptés INVENTÉS pour le test (1,5 et 2,5, comme le scénario du
    contrat ; le contrat n'est pas lu), constants, donc sans relation aux comptes. Un seuil de 1 ou moins n'a pas de part (hors échelle)."""
    sortie = []
    for seuil in SEUILS_ADOPTES_H1:
        sortie.append("repere:" + (str(100 - 100 / seuil) if seuil > 1 else "hors_echelle"))
    return sortie


def reduites_fh1(forme: Forme, v: Vues) -> tuple:
    """F-H1 (équipe A, année groupée) : état de la médiane et du P85 (délai et cycle) des trimestres et de l'année, couverture de l'année, états
    des explications, barres et repères de waitShares (task 4.3 de mothra-demo-habillage, R-20261101-32). Aucune position de débit, aucun effet
    du signal (D34 point 3)."""
    sortie = []
    for cle in [("A", q) for q in range(forme.Q)] + [("A", "annee")]:
        c = v.lead[cle]
        n = sum(v.debit["A"]) if cle[1] == "annee" else v.debit["A"][cle[1]]
        sortie += [etat_statistique(c["lead_median_days"], n, MEDIANE_MIN), etat_statistique(c["lead_p85_days"], n, P85_MIN),
                   etat_statistique(c["cycle_median_days"], n, MEDIANE_MIN), etat_statistique(c["cycle_p85_days"], n, P85_MIN)]
    sortie += [etat_couverture(v.lead[("A", "annee")]["items_ct"], sum(v.debit["A"])), etat_file_prete(forme, v), "not_measurable"]
    # waitShares : les barres de la médiane et du P85 de l'année groupée (ratios.pooledYear) et les deux repères, comme valeurs représentées
    annee, n_annee = v.lead[("A", "annee")], sum(v.debit["A"])
    # Modèle du verdict « échantillon insuffisant » (hypothèse de test, comme le contrat l'applique : année sous la taille de la médiane, ou un
    # terme de médiane de l'année masqué) : les deux barres perdent leur part, sauf une barre masquée qui reste masquée.
    insuffisant = n_annee < MEDIANE_MIN or not visible(annee["lead_median_days"]) or not visible(annee["cycle_median_days"])
    sortie += [barre_attente(annee["lead_median_days"], annee["cycle_median_days"], insuffisant, n_annee, MEDIANE_MIN),
               barre_attente(annee["lead_p85_days"], annee["cycle_p85_days"], insuffisant, n_annee, P85_MIN)]
    sortie += reperes_attente()
    sortie.append("applicable:" + str(not insuffisant))   # markers.applicable (D3b, task 4.3 : les barres et les repères) : faux sous le verdict « insuffisant »
    # plafond de D22 : l'année groupée sous la taille de fiabilité du P85 plafonne le verdict à « not settled », même si la ligne est masquée
    sortie.append("verdict:capped_not_settled" if sum(v.debit["A"]) < P85_MIN else "verdict:ratios_decide")
    return tuple(sortie)


REDUITES = {"F-H5": reduites_fh5, "F-H1": reduites_fh1}


def publier(forme: Forme, sorte: str | None, temoin: bool, table, seuil: int):
    """Image publiée : une ligne par cellule brute (valeur ou None), puis une ligne de cellules dérivées des vues et de la forme réduite (chaînes
    ou entiers, jamais None). sorte None : les vues seules (garde de base)."""
    v = Vues(forme, table, seuil)
    derniere = v.derivees(forme)
    if sorte is not None:
        derniere += REDUITES[sorte](forme, v)
    if temoin == "barre":                                # témoin de waitShares : une barre dont la valeur dérive d'un compte (10 x le débit du trimestre 2)
        derniere += (10 * v.debit["A"][1],)
    elif temoin:                                         # cellule interdite : le débit de l'équipe A en clair
        derniere += tuple(v.debit["A"])
    return v.cellules(forme) + (derniere,)


def indices_borne_basse_1(forme: Forme) -> set:
    """Lignes brutes dont un zéro est refusé dans l'élagage : la file prête, lue dans contrats/vues.json sans borne déclarée dans BORNES et traitée
    comme lo = 1 par la revue 20.3 (constat 5). Les cellules de v_team_weekly_resolved n'y sont plus (D17, tâche 13.1) : un zéro brut est une ligne
    « absente », une image que l'attaquant voit, et non une valeur impossible."""
    return {4 * forme.W + 3 * q + 2 for q in range(forme.Q)}


def analyse(forme: Forme, sorte: str | None, brut, temoin: bool | str = False) -> dict:
    pub = partial(publier, forme, sorte, temoin)
    observe = pub(brut, SEUIL)
    nb = len(brut)

    sans_zero = indices_borne_basse_1(forme)

    def elaguer(suite):
        i = len(suite) - 1
        if i in sans_zero and suite[i][0] == 0:        # file prête : lo = 1, un zéro n'est pas une valeur possible
            return False
        # une cellule visible de l'image (un entier) est fixée ; une cellule masquée (None) ou absente (ABSENT) varie
        return i >= nb or not isinstance(observe[i][0], int) or suite[i][0] == observe[i][0]

    def cellules_absentes(image):
        return [(i, j) for i, ligne in enumerate(image[:nb]) for j, x in enumerate(ligne) if x == ABSENT]

    resultat = oracle.analyser(pub, brut, SEUIL, VALEURS, elaguer, TAILLE_MAX_SOMME, cellules_absentes)
    resultat["masquees"] = len(oracle.cellules_masquees(observe))
    return resultat


# ---- familles -------------------------------------------------------------------------------------------------------------------------------
# sem : par semaine (A story, A task, B story, B task) ; tri : par trimestre (tâches sans équipe, non planifié, file prête de A).
FORME_H5, FORME_H1 = Forme(1, 3), Forme(2, 2)
FORME_H1_CHEVAL = Forme(2, 2, cheval_fin=True)
GROS = (9, 8, 7, 6)
FAMILLES = {
    "F-H5": (FORME_H5, {
        "rien_de_masque_dans_la_serie_de_A": dict(
            sem=[GROS, GROS, (10, 9, 7, 6)], tri=[(9, 8, 9), (9, 8, 9), (9, 8, 9)]),
        "debit_masque_en_milieu_de_serie": dict(
            sem=[GROS, (3, 3, 7, 6), (10, 9, 7, 6)], tri=[(9, 8, 9), (9, 8, 9), (9, 8, 9)]),
        "debit_jugé_sous_le_plancher_bas": dict(
            sem=[GROS, GROS, (3, 3, 7, 6)], tri=[(9, 8, 9), (9, 8, 9), (9, 8, 9)]),
        # exemple de la revue 20.3 : débits de A 10, x masqué, 24 ; la position de T1 borne x (référence = (34 + x) / 3)
        "debit_masque_en_milieu_exemple_de_la_revue": dict(
            sem=[(5, 5, 7, 6), (2, 2, 7, 6), (12, 12, 7, 6)], tri=[(9, 8, 9), (9, 8, 9), (9, 8, 9)]),
        "debit_masque_au_premier_trimestre": dict(
            sem=[(2, 2, 7, 6), (5, 5, 7, 6), (12, 12, 7, 6)], tri=[(9, 8, 9), (9, 8, 9), (9, 8, 9)]),
        "debit_du_trimestre_juge_masque": dict(
            sem=[(12, 12, 7, 6), (11, 12, 7, 6), (2, 2, 7, 6)], tri=[(9, 8, 9), (9, 8, 9), (9, 8, 9)]),
        "part_sans_equipe_masquee_dans_la_reference": dict(
            sem=[GROS, GROS, (10, 9, 7, 6)], tri=[(2, 8, 9), (9, 8, 9), (9, 8, 9)]),
        "part_sans_equipe_jugee_masquee": dict(
            sem=[GROS, GROS, (10, 9, 7, 6)], tri=[(9, 8, 9), (9, 8, 9), (3, 8, 2)]),
        "file_prete_et_non_planifie_masques": dict(
            sem=[GROS, GROS, (10, 9, 7, 6)], tri=[(9, 8, 9), (9, 2, 9), (9, 8, 2)]),
    }),
    "F-H1": (FORME_H1, {
        "annee_au_dessus_des_tailles_de_fiabilite": dict(
            sem=[(12, 12, 7, 6), (11, 12, 7, 6), (12, 12, 7, 6), (11, 11, 7, 6)], tri=[(9, 8, 9), (9, 8, 9)]),
        "trimestre_masque_dans_l_annee": dict(
            sem=[(12, 12, 7, 6), (11, 12, 7, 6), (1, 2, 7, 6), (2, 1, 7, 6)], tri=[(9, 8, 9), (9, 8, 9)]),
        # trimestre de A sous 5 (4 cellules de 1) : l'année groupée est masquée par la règle de série, son effectif reste lu par le plafond de D22.
        # Fuite des vues sur main par la relation T3 (les quatre lignes se lisaient), fermée par la règle (a) de D17 (R-20261031-07) : les lignes sont absentes.
        "annee_masquee_par_la_serie": dict(
            sem=[(12, 12, 7, 6), (11, 12, 7, 6), (1, 1, 7, 6), (1, 1, 7, 6)], tri=[(9, 8, 9), (9, 8, 9)]),
        "semaine_masquee_dans_un_trimestre": dict(
            sem=[(12, 12, 7, 6), (11, 12, 7, 6), (3, 3, 7, 6), (8, 9, 7, 6)], tri=[(9, 8, 9), (9, 8, 9)]),
        "part_et_file_prete_masquees": dict(
            sem=[(12, 12, 7, 6), (11, 12, 7, 6), (12, 12, 7, 6), (11, 11, 7, 6)], tri=[(3, 8, 2), (9, 2, 9)]),
        # Relation T3 (D17, tâche 13.1). Le second trimestre de A porte deux semaines (histoire, tâche) ; le premier est gros et visible. Règle (b), débit
        # visible : une ligne masquée (k = 1) ; reste égal au nombre de lignes (S = k) ; reste égal à quatre fois ce nombre (S = 4k) ; reste sous le seuil
        # avec 2 <= k < S < 5. Chacune doit être close par le masquage du débit puis le retrait des lignes (règle (a)).
        "t3_une_ligne_masquee": dict(
            sem=[(12, 12, 7, 6), (11, 12, 7, 6), (12, 3, 7, 6), (12, 11, 7, 6)], tri=[(9, 8, 9), (9, 8, 9)]),
        "t3_reste_egal_au_nombre_de_lignes": dict(
            sem=[(12, 12, 7, 6), (11, 12, 7, 6), (12, 1, 7, 6), (1, 11, 7, 6)], tri=[(9, 8, 9), (9, 8, 9)]),
        "t3_reste_egal_a_quatre_fois_le_nombre": dict(
            sem=[(12, 12, 7, 6), (11, 12, 7, 6), (12, 4, 7, 6), (4, 11, 7, 6)], tri=[(9, 8, 9), (9, 8, 9)]),
        "t3_reste_sous_le_seuil": dict(
            sem=[(12, 12, 7, 6), (11, 12, 7, 6), (12, 1, 7, 6), (2, 11, 7, 6)], tri=[(9, 8, 9), (9, 8, 9)]),
        # témoins verts : le reste ne fixe rien (S = 5 avec k = 2 ; S = 6 avec k = 3), les lignes masquées restent publiées
        "t3_temoin_vert_reste_5": dict(
            sem=[(12, 12, 7, 6), (11, 12, 7, 6), (12, 3, 7, 6), (2, 11, 7, 6)], tri=[(9, 8, 9), (9, 8, 9)]),
        "t3_temoin_vert_trois_lignes_reste_6": dict(
            sem=[(12, 12, 7, 6), (11, 12, 7, 6), (1, 2, 7, 6), (3, 11, 7, 6)], tri=[(9, 8, 9), (9, 8, 9)]),
        # semaine à cheval (revue de T3) : la dernière semaine du dernier trimestre chevauche sa fin ; témoin vert (S = 5, k = 2). Les quatre lectures des
        # deux semaines à cheval : sans la semaine (2, 11) le reste vaut 16 pour une ligne masquée, lecture incohérente écartée ; avec elle S = 5 passe.
        "t3_semaine_a_cheval_temoin_vert": dict(
            forme=FORME_H1_CHEVAL, sem=[(12, 12, 7, 6), (11, 12, 7, 6), (12, 3, 7, 6), (2, 11, 7, 6)], tri=[(9, 8, 9), (9, 8, 9)]),
        # débit masqué (n = 4) avec k = T - 2 = 3 lignes présentes (1, 1, 2) et un zéro (ligne absente) : règle (a)
        "t3_debit_masque_k_egal_seuil_moins_deux": dict(
            sem=[(12, 12, 7, 6), (11, 12, 7, 6), (1, 1, 7, 6), (2, 0, 7, 6)], tri=[(9, 8, 9), (9, 8, 9)]),
    }),
}


# Fuites trouvées : (sorte, famille). Un cas qui fuit est signalé par unittest.expectedFailure, jamais corrigé (tâche 20.3). Chaque entrée
# ci-dessous : R-20261031-01 Q12, ligne du registre de 20.4 à écrire par l'auteur (le 2026-11-08). Un succès inattendu (fuite disparue) rend
# la suite rouge. Vide tant qu'aucune exécution n'a trouvé de fuite.
# F-H5 : R-20261031-01 Q12 ; fuite de F-H5 par la position du trimestre jugé (D22) ; ligne du registre de 20.4 à écrire par l'auteur le
# 2026-11-08 ; question R-20261031-04 Q17. Message de l'oracle, deux cas : « somme unique sous le seuil » = 4 (les deux cellules masquées du
# trimestre masqué : (0,0)+(1,0) pour debit_masque_au_premier_trimestre, (4,0)+(5,0) pour l'exemple de la revue).
# F-H1 / annee_masquee_par_la_serie : sortie de la liste (R-20261031-07, tâche 13.1). C'était les VUES SEULES qui fuyaient (15 fuites dont « valeur
# unique : cellule (8, 0) = 1 ») par la relation T3 entre le débit masqué du trimestre et ses quatre lignes hebdomadaires masquées de 1 (et non par la
# série entre le trimestre et l'année, comme le commentaire de la première version le disait). La règle (a) de D17 retire ces lignes : verte avec 13.2
# et 13.3 (migration et masquer_vue).
# F-H5, debit_masque_au_premier_trimestre et debit_masque_en_milieu_exemple_de_la_revue : sorties de la liste (R-20261031-11 les laissait en attendant
# l'exécution ; R-20261031-18, Q47 (a), les retire). Avec D17 un débit visible dont la règle (b) échoue est masqué lui aussi et ses lignes sont
# retirées : le débit masqué du trimestre ne vaut plus « moins de 5 » mais toute valeur de 4 à 16 que les positions du trimestre voisin permettent
# (par exemple 12 + 4), la somme des deux cellules n'est plus unique et la fuite de F-H5 par la position du trimestre jugé (D22) a disparu : le premier
# passage de la suite db l'a confirmé (deux succès inattendus). Les deux tests sont des preuves ordinaires. Aucune fuite connue : le dict est vide.
FUITES_CONNUES: set = set()


class SorteDeFiche:
    """Mélange (pas un TestCase : unittest ne le joue pas seul). Une méthode de test par famille (générées plus bas)."""
    sorte = None

    def verifier_famille(self, nom):
        forme, familles = FAMILLES[self.sorte]
        f = familles[nom]
        forme = f.get("forme", forme)                  # une famille peut porter sa propre géométrie (semaine à cheval)
        brut = forme.brut(f["sem"], f["tri"])
        base = analyse(forme, None, brut)
        self.assertEqual(base["fuites"], [], f"{self.sorte}/{nom} : famille mal posée, les vues seules fuient (relation entre vues)")
        complet = analyse(forme, self.sorte, brut)
        self.assertEqual(complet["fuites"], [], f"{self.sorte}/{nom} : la forme réduite ajoute une fuite")


def _methode(nom):
    def test(self):
        self.verifier_famille(nom)
    return test


def _classe(sorte):
    attributs = {"sorte": sorte}
    for nom in FAMILLES[sorte][1]:
        m = _methode(nom)
        if (sorte, nom) in FUITES_CONNUES:
            m = unittest.expectedFailure(m)
        attributs["test_" + nom.replace("é", "e")] = m
    return type("Oracle" + sorte.replace("-", ""), (SorteDeFiche, unittest.TestCase), attributs)


FH5 = _classe("F-H5")
FH1 = _classe("F-H1")


class Temoin(unittest.TestCase):
    def test_le_debit_en_clair_fuit(self):
        """Preuve que le test voit une fuite : on ajoute à F-H5 la cellule interdite (le débit de A en clair) sur une famille dont le débit d'un
        trimestre est masqué : la somme de ses deux cellules masquées n'a plus qu'une valeur, sous le seuil."""
        forme, familles = FAMILLES["F-H5"]
        f = {"sem": [GROS, (2, 2, 7, 6), (10, 9, 7, 6)], "tri": [(9, 8, 9), (9, 8, 9), (9, 8, 9)]}
        brut = forme.brut(f["sem"], f["tri"])
        self.assertEqual(analyse(forme, None, brut)["fuites"], [], "famille mal posée")
        res = analyse(forme, "F-H5", brut, temoin=True)
        self.assertTrue(any("somme unique sous le seuil" in x or "valeur unique" in x for x in res["fuites"]), res["fuites"])

    def test_une_barre_derivee_d_un_compte_fuit(self):
        """Revue 1b (a) : preuve que l'oracle voit une fuite par waitShares. On ajoute à F-H1 une barre dont la valeur dérive d'un compte (10 x
        le débit de A du trimestre 2, qui vaut 4, masqué) : la valeur est connue, donc le débit masqué n'a qu'une valeur, sous le seuil."""
        forme, familles = FAMILLES["F-H1"]
        brut = forme.brut(familles["annee_masquee_par_la_serie"]["sem"], familles["annee_masquee_par_la_serie"]["tri"])
        self.assertEqual(analyse(forme, None, brut)["fuites"], [], "famille mal posée")
        res = analyse(forme, "F-H1", brut, temoin="barre")
        self.assertTrue(res["fuites"], "une barre dérivée d'un compte masqué doit fuir")


if __name__ == "__main__":
    unittest.main()
