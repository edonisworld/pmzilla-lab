"""Extension du jeu synthétique pour la tranche 1 de Mothra (tâche 14.1, conception D13, D19, D22, D33).

La tranche 0 (jeu_synthetique.py) peuple la vue « statut par équipe » ; la tranche 1 ajoute ce qu'il faut aux verdicts de la
première moitié de l'hypothèse 1 et de l'hypothèse 5 :
  - des dates de création, d'engagement (entrée dans le statut prêt, le segment du point d'engagement, R-20261029-21) et de fin
    sur trois trimestres civils clos (R-20261114-49 : la fenêtre des vues passe de quatre trimestres à trois ; quatre avant) : le
    trimestre jugé (k = 0) est le dernier trimestre civil clos avant l'instant du chargement, les deux précédents (k = 1 et 2) sont la
    référence du signal de rattachement (D13) ; la référence de l'hypothèse 5 est la moyenne des trois trimestres, le jugé compris
    (D14 : sans trois trimestres complets, « échantillon insuffisant »). Les dates de fin sont placées par rapport aux
    bornes civiles, à 5 jours au moins de chaque bord ; le jeu s'aligne ainsi sur le début du trimestre civil courant et reste le même,
    pour les éléments terminés, quel que soit l'instant de chargement dans un trimestre ;
  - des équipes témoins : un verdict de la seule règle de seuils pour chaque sorte, pour l'hypothèse 1 (première moitié) et pour
    l'hypothèse 5 (VERDICTS_SEUILS_H1, VERDICTS_SEUILS_H5), avec les seuils de départ de l'annexe de la conception (les tests les
    recalculent), puis le verdict attendu après les explications concurrentes de D20 et D33, avec ses motifs (VERDICTS_ATTENDUS) ;
    des verdicts croisés (équipes de H5 sous la règle de H1, équipes de H1 sous celle de H5, déclarés « hors témoin ») ;
  - des échantillons sous chaque taille et exactement à chacune : 4 (masqué), 5 (échantillon insuffisant), 9 (médiane non fiable),
    10 (plafond « non tranché »), 19 (P85 non fiable), 20 (verdict plein) ;
  - des éléments créés plus d'un an avant leur engagement (champ `ancien`), comptés à part, sur un témoin dont le verdict change
    quand on les met en commun ;
  - des défauts sans équipe (jamais d'équipe, même terminés), dont certains liés à une story d'une équipe ou sous son épic, et des
    tâches terminées sans équipe, avec la même variété (témoins de D33), et une part de tâches sans équipe qui bondit au dernier trimestre ;
  - des liens « blocks » entre équipes (porté par le bloqueur, cible l'élément bloqué), dont une cellule sous 5 (BLOCAGES_ATTENDUS) ;
  - le débit attendu par équipe et trimestre (DEBIT_ATTENDU), que la tâche 15.1 vérifiera sur les vues.

Limites, à lire avant la tâche 15.1 :
  - Trimestre : civil (décision F de l'auteur, 2026-10-27). Seuls les éléments ouverts (en cours, prêts) dépendent de l'instant exact
    du chargement ; aucun verdict, débit, blocage ni signal n'en dépend dans un même trimestre.
  - Les effectifs des témoins de H1 sont annuels (année mise en commun, Q22), et la fiche de H1 lit la ligne « année mise en commun »
    des vues. Cette ligne n'est montrée que si aucun trimestre de la série n'est masqué (règle de série, masquage.ts:224-246) et si la
    relation T3 ne retire le débit d'aucun trimestre (masquage.ts:121 : des lignes hebdomadaires masquées toutes à 1 fixeraient le débit).
    Le jeu y pourvoit (R-20261104-42, question 1) : les témoins de taille I, J, S et T sont concentrés dans un seul trimestre (les autres
    n'ont aucune ligne), le témoin U compte 7, 7 et 6 éléments par trimestre, et chaque trimestre lu compte au moins une semaine à 2 éléments.
    Le test tests/mothra_donnees/test_tranche1_masquage.py le prouve sur les vues masquées. Seul K, masqué par construction (4 éléments),
    reste réparti sur trois trimestres.
  - Un seul trimestre est jugé (k = 0) : le jeu n'a donc pas de cas « pas de signal » sur la part de tâches sans équipe ; ce cas
    est couvert par les cas de parité de 17.1.
  - Passage de quatre trimestres à trois (R-20261114-49, -83) : 24 éléments de H1 en 8 par trimestre (grappes 2, 3, 3), le témoin U en 7, 7 et 6,
    quinze éléments anciens du témoin Q (cinq par trimestre), les cinq équipes de H5 recomposées sur trois trimestres complets, la part de
    tâches sans équipe sur trois trimestres (le signal lit les deux trimestres avant le jugé, D13).

Équipes : désignations génériques « équipe E » à « équipe U », distinctes de celles de la tranche 0. Clés : SYN-1001 et suivantes,
inventées. Aucune donnée réelle. Tâche 14.2 : `supplement` et `main` branchent ce jeu sur le chargeur de la tranche 0 (ses transitions, ses liens
et ses équipes sont écrits ; EQUIPES_TRANCHE1 entre dans l'ensemble contrôlé). L'engagement d'un élément est l'entrée dans le statut prêt
(R-20261029-21) : le statut prêt et le type de lien bloquant viennent du référentiel synthétique.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))      # lancé comme un script, avec -I : le dossier du script n'est pas dans le chemin
import jeu_synthetique as base  # noqa: E402
import referentiel_synthetique as referentiel  # noqa: E402

STATUT_PRET = referentiel.STATUT_PRET        # importé du référentiel synthétique, jamais recopié (R-20261029-21) : le statut du segment « prêt »

def debut_trimestre(maintenant: datetime, decalage: int) -> datetime:
    """Début (minuit) du trimestre civil qui contient `maintenant`, reculé de `decalage` trimestres."""
    annee, q = divmod(maintenant.year * 4 + (maintenant.month - 1) // 3 - decalage, 4)
    return maintenant.replace(year=annee, month=3 * q + 1, day=1, hour=0, minute=0, second=0, microsecond=0)


def indice_trimestre(maintenant: datetime, date: datetime) -> int:
    """0 pour le dernier trimestre civil clos avant `maintenant`, 1 pour celui d'avant, etc."""
    return (maintenant.year * 4 + (maintenant.month - 1) // 3) - (date.year * 4 + (date.month - 1) // 3) - 1


EQUIPES_TRANCHE1 = tuple(f"équipe {lettre}" for lettre in "EFGHIJKLMNOPQRSTU")
CLE_DEPART = 1000

# Équipes témoins, avec le verdict de la seule règle de seuils que le jeu leur destine (les tests le recalculent d'après l'annexe).
# Ce n'est pas le verdict affiché : voir VERDICTS_ATTENDUS plus bas.
TEMOIN_ZONE_GRISE = "équipe G"
TEMOIN_P85_DIVERGENT = "équipe H"
TEMOIN_SOUS_P85 = "équipe I"
TEMOIN_ANCIENS = "équipe Q"
VERDICTS_SEUILS_H1 = {
    "équipe E": "confirmé",
    "équipe F": "réfuté",
    "équipe G": "non tranché",              # rapport 2 : zone grise
    "équipe H": "non tranché",              # rapport médian 4, mais le P85 ne suit pas
    "équipe I": "non tranché",              # 19 éléments : sous la taille du P85, le verdict est plafonné (Q22)
    "équipe J": "échantillon insuffisant",  # 9 éléments : sous la taille d'une médiane
    "équipe K": "masqué",                   # 4 éléments : sous la taille de masquage
    "équipe Q": "non tranché",              # quinze éléments anciens (cinq par trimestre) comptés à part ; mis en commun, le verdict serait « confirmé »
    "équipe S": "échantillon insuffisant",  # 5 éléments : exactement la taille de masquage, non masqué
    "équipe T": "non tranché",              # 10 éléments : médiane fiable, P85 non fiable, plafond
    "équipe U": "confirmé",                 # 20 éléments : exactement la taille d'un P85, verdict plein
}
VERDICTS_SEUILS_H5 = {
    "équipe L": "confirmé",
    "équipe M": "réfuté",
    "équipe N": "réfuté",
    "équipe O": "réfuté",
    "équipe P": "non tranché",
}
# Verdict attendu après les explications concurrentes (D20, D33) : (verdict, motifs affichés).
# Aucune équipe n'a de défaut : « travail non planifié » n'est pas mesurable (`defects_without_team`), donc jamais « confirmé ».
# Le signal de rattachement des tâches (`tasks_attachment_signal`) est levé au trimestre jugé et se lit sur le débit : il accompagne
# les verdicts de l'hypothèse 5 ; « réfuté » reste possible (M, N, O). L'hypothèse 1 est tenue pour ne pas lire le débit (à décider
# à la revue de la tranche 1). Les motifs listés sont ceux qui ont interdit « confirmé », et le signal quand il est levé.
# Recalculé à la main sur trois trimestres clos (R-20261114-49, -83) : les verdicts de seuils de chaque témoin sont ceux d'avant (VERDICTS_SEUILS_H1, calculs à la
# main plus haut pour H5), le signal de rattachement reste levé (47,4 - 33,3 = 14,0 points, au-dessus de 10, sur deux trimestres de référence) ; les motifs
# sont donc ceux d'avant.
VERDICTS_ATTENDUS = {
    "équipe E": ("non tranché", ("defects_without_team",)),
    "équipe F": ("réfuté", ()),
    "équipe G": ("non tranché", ()),
    "équipe H": ("non tranché", ()),
    "équipe I": ("non tranché", ()),
    "équipe J": ("échantillon insuffisant", ()),
    "équipe K": ("masqué", ()),
    "équipe Q": ("non tranché", ()),
    "équipe S": ("échantillon insuffisant", ()),
    "équipe T": ("non tranché", ()),
    "équipe U": ("non tranché", ("defects_without_team",)),
    "équipe L": ("non tranché", ("defects_without_team", "tasks_attachment_signal")),
    "équipe M": ("réfuté", ("tasks_attachment_signal",)),
    "équipe N": ("réfuté", ("tasks_attachment_signal",)),
    "équipe O": ("réfuté", ("tasks_attachment_signal",)),
    "équipe P": ("non tranché", ("tasks_attachment_signal",)),
}
# Verdicts croisés. Les équipes de H5 sous la règle de H1 (attente de 2 jours sur 10 de cycle : rapport 1,2) : toutes réfutées.
# Les équipes de H1 sous la règle de H5 : hors témoin, leurs trimestres n'ont pas la taille que la règle de H5 demande (20 éléments).
VERDICTS_CROISES_H5_SOUS_H1 = {equipe: "réfuté" for equipe in VERDICTS_SEUILS_H5}
VERDICTS_CROISES_H1_SOUS_H5 = {equipe: "hors témoin" for equipe in VERDICTS_SEUILS_H1}
MOTIFS_REFUTATION_H5 = {
    "deux trimestres hors de la double bande": "équipe M",
    "série montante": "équipe N",
    "plancher bas de débit": "équipe O",
}

# H1 : (équipe, nombre d'éléments, jours d'engagement à fin, jours de création à engagement) ; les éléments sont répartis sur les trois
# trimestres. Le délai d'attente est la différence entre le délai total et le temps de cycle.
H1_STANDARD = (
    ("équipe E", 24, 5, 15),   # délai 20, cycle 5 : rapport 4 sur la médiane comme sur le P85
    ("équipe F", 24, 5, 1),    # délai 6, cycle 5 : rapport 1,2
    ("équipe G", 24, 5, 5),    # délai 10, cycle 5 : rapport 2
    ("équipe I", 19, 5, 15),
    ("équipe J", 9, 5, 15),
    ("équipe K", 4, 5, 15),
    ("équipe S", 5, 5, 15),    # exactement 5, 10 et 20 : les bornes elles-mêmes, rapport 4
    ("équipe T", 10, 5, 15),
    ("équipe U", 20, 5, 15),
)
ANCIENS_TEMOIN = 15   # créés 420 jours avant leur engagement, sur l'équipe Q : cinq par trimestre (R-20261106-39, décision de l'auteur : au moins 5 par trimestre ; trois trimestres, R-20261114-49)

# Grappes de fin (R-20261104-42, question 1). Les éléments terminés d'une même semaine le sont le même jour, une grappe tous les 7 jours à partir
# du 7e jour du trimestre : chaque semaine des vues (un lundi, 7 jours) contient alors exactement une grappe, quel que soit le jour de la semaine où
# commence le trimestre, donc le compte hebdomadaire d'une semaine est la taille de la grappe. La relation T3 (masquage.ts:110-127) retire le débit
# d'un trimestre dont les lignes hebdomadaires masquées (sous 5) sont toutes à 1, ou dont une seule est masquée : chaque trimestre lu a ici soit
# aucune ligne masquée (grappes de 5), soit au moins deux lignes masquées dont la somme atteint 5, avec au moins une grappe de 2 ou plus et jamais
# toutes de 4. Les tailles par trimestre (k : 0 = dernier trimestre clos) : { équipe : { k : tailles des grappes } }.
GRAPPES_H1 = {
    **{equipe: {k: (2, 3, 3) for k in range(3)} for equipe in ("équipe E", "équipe F", "équipe G", "équipe H")},   # 24 éléments en 8 par trimestre (quatre trimestres : 6, grappes 2, 2, 2)
    "équipe Q": {k: (2, 2, 3, 3, 3) for k in range(3)},                              # 24 éléments en 8, plus 15 anciens en 5 : 13 par trimestre (R-20261106-39)
    "équipe U": {0: (2, 2, 3), 1: (2, 2, 3), 2: (2, 2, 2)},                          # 20 éléments répartis i % 3 : 7, 7 et 6 ; l'année compte 20, aucun trimestre masqué
    # Les témoins de taille I, J, S, T tiennent dans un seul trimestre : un trimestre sous 5 masquerait l'année groupée (règle de série,
    # masquage.ts:224-246), qui est la seule ligne que la fiche de H1 lit. Les autres trimestres n'ont aucune ligne.
    "équipe I": {0: (3, 3, 3, 3, 3, 4)},
    "équipe J": {0: (3, 3, 3)},
    "équipe S": {0: (2, 3)},
    "équipe T": {0: (3, 3, 4)},
}
GRAPPES_H5 = 5      # H5 : des grappes de 5, donc des lignes hebdomadaires toutes visibles ; les effectifs par trimestre sont des multiples de 5
JOUR_PREMIERE_GRAPPE = 6


def jours_des_grappes(tailles) -> list[int]:
    """Jour (depuis le début du trimestre) de fin de chaque élément, une grappe tous les 7 jours : 6, 13, 20, ... (le dernier reste avant le 84e)."""
    return [JOUR_PREMIERE_GRAPPE + 7 * semaine for semaine, taille in enumerate(tailles) for _ in range(taille)]


class _Jours:
    """Les jours de fin des éléments d'une équipe de GRAPPES_H1, trimestre par trimestre, dans l'ordre où le constructeur les crée."""

    def __init__(self, equipe: str):
        self.jours = {k: jours_des_grappes(tailles) for k, tailles in GRAPPES_H1[equipe].items()}

    def quand(self, i: int, nombre: int, decalage: int = 0) -> tuple[int, int]:
        """(trimestre, jour) du i-e élément : dans l'unique trimestre de l'équipe, ou, répartis (i % 3), au rang i // 3 + decalage du trimestre."""
        if len(self.jours) == 1:
            k = next(iter(self.jours))
            assert len(self.jours[k]) == nombre, (k, nombre)
            return k, self.jours[k][i]
        return i % 3, self.jours[i % 3][i // 3 + decalage]
# Liens « blocks » entre équipes, (équipe bloquée, trimestre) -> éléments bloqués ; le bloqueur appartient à une autre équipe.
BLOCAGES = (
    ("équipe L", 0, 8, "équipe M"),
    ("équipe L", 1, 3, "équipe M"),   # cellule sous 5 : masquée
    ("équipe N", 0, 5, "équipe L"),   # cellule exactement à 5 : non masquée
)
BLOCAGES_ATTENDUS = {(bloquee, k): n for bloquee, k, n, _ in BLOCAGES}
# Débit attendu (stories et tâches terminées portées par l'équipe seule), par trimestre, pour L, O (un trimestre jugé plus maigre) et R.
DEBIT_ATTENDU = {
    "équipe L": {0: 25, 1: 25, 2: 25},
    "équipe O": {0: 20, 1: 60, 2: 60},
    "équipe R": {0: 20, 1: 20, 2: 20},
}
# H5 : (équipe, éléments par trimestre du plus ancien au plus récent, temps de cycle par trimestre) ; attente de 2 jours. Trois trimestres
# complets chacune (D14 : sans eux, « échantillon insuffisant » ; la référence est la moyenne des trois, le jugé compris). Calculs à la main
# (médiane = P85 = le temps de cycle, tous les éléments d'un trimestre ayant le même ; écart = |x - moyenne| / moyenne ; bandes 0,2 et 0,4 ;
# planchers 0,8 et 0,6 ; série montante : deux hausses consécutives de la médiane et une hausse cumulée d'au moins 10 %) :
#   L : cycles 10, 10, 10, débits 25, 25, 25 : tout dans la bande, au plancher : « confirmé » avant D20 et D33.
#   M : cycles 5, 15, 10, moyenne 10 : écarts 0,5, 0,5 et 0 : deux trimestres hors de la double bande (0,4) ; 5 < 15 puis 10 < 15 : pas de série montante.
#   N : cycles 10, 11, 12, moyenne 11 : écarts 1/11 = 0,09, 0 et 0,09, tous dans la bande ; 10 < 11 < 12, hausse cumulée 12 / 10 = 1,2 >= 1,1 : série montante.
#   O : débits 60, 60, 20, moyenne 46,67 : 20 / 46,67 = 0,43 < 0,6, sous le plancher bas ; les cycles sont tous à 10.
#   P : débits 30, 30, 20, moyenne 26,67 : 20 / 26,67 = 0,75 < 0,8 (sous le plancher) et >= 0,6 ; cycles 10, 10, 14, moyenne 11,33 : écarts 0,12, 0,12 et
#       0,24, le dernier hors de la bande (0,2) mais pas de la double (0,4) ; pas de série montante (10, 10 puis 14) : « non tranché ».
H5 = (
    ("équipe L", (25, 25, 25), (10, 10, 10)),
    ("équipe M", (25, 25, 25), (5, 15, 10)),
    ("équipe N", (25, 25, 25), (10, 11, 12)),
    ("équipe O", (60, 60, 20), (10, 10, 10)),
    ("équipe P", (30, 30, 20), (10, 10, 14)),
)
TACHES_AVEC_EQUIPE_PAR_TRIMESTRE = 20
# Du plus ancien au plus récent : 10 / 30 = 33 %, 33 %, 18 / 38 = 47 % de part sans équipe. Le signal compare le trimestre jugé à la moyenne des deux
# trimestres qui le précèdent (D13) : 47,4 - 33,3 = 14,0 points, au-dessus du seuil de 10.
TACHES_SANS_EQUIPE = (10, 10, 18)


class _Constructeur:
    def __init__(self, maintenant: datetime):
        self.maintenant = maintenant
        self.tickets: list[dict] = []
        self.rang = CLE_DEPART

    def _ajouter(self, equipe, type_, statut, categorie, cree, resolu, transitions, parent, liens, ancien) -> str:
        self.rang += 1
        cle = f"{base.PREFIXE_CLE}{self.rang}"
        derniere = max([cree] + [d for d, _, _ in transitions])
        self.tickets.append({
            "cle": cle,
            "projet": base.SENTINELLES[0],
            "type": type_,
            "statut": statut,
            "categorie": categorie,
            "cree": cree,
            "resolu": resolu,
            "resolution": base.SENTINELLES[1] if resolu else None,
            "debut": resolu or derniere,
            "points": 1 + self.rang % 5,
            "maj": derniere,
            "equipe": equipe,
            "equipes": [equipe] if equipe else [],
            "parent": parent,
            "liens": list(liens),
            "transitions": transitions,
            "ancien": ancien,
        })
        return cle

    def fait(self, equipe, type_, trimestre, cycle, attente, parent=None, liens=(), ancien=False, jour=None) -> str:
        """Un élément terminé au trimestre civil donné : fin placée de 5 à 84 jours après le début du trimestre (il en compte 90 au moins), ou,
        avec `jour`, ce jour-là exactement (grappes, voir GRAPPES_H1)."""
        decalage = 5 + ((self.rang + 1) * 7) % 80 if jour is None else jour
        resolu = debut_trimestre(self.maintenant, trimestre + 1) + timedelta(days=decalage, hours=(self.rang + 1) % 24)
        engage = resolu - timedelta(days=cycle)       # l'engagement : l'entrée dans le statut prêt (segment « prêt »), R-20261029-21
        cree = engage - timedelta(days=attente)
        reprise = engage + (resolu - engage) / 2      # le travail reprend à mi-chemin : passage du statut prêt à « In Progress »
        transitions = [(engage, "To Do", STATUT_PRET), (reprise, STATUT_PRET, "In Progress"), (resolu, "In Progress", "Done")]
        return self._ajouter(equipe, type_, "Done", "Done", cree, resolu, transitions, parent, liens, ancien)

    def en_cours(self, equipe, type_, jours_depuis_creation, jours_depuis_engagement, parent=None, liens=()) -> str:
        cree = self.maintenant - timedelta(days=jours_depuis_creation)
        engage = self.maintenant - timedelta(days=jours_depuis_engagement)
        return self._ajouter(equipe, type_, "In Progress", "In Progress", cree, None, [(engage, "To Do", "In Progress")], parent, liens, False)

    def pret(self, equipe, type_, jours_depuis_creation) -> str:
        cree = self.maintenant - timedelta(days=jours_depuis_creation)
        entree = cree + timedelta(days=1)             # entrée dans le statut prêt, un jour après la création : l'élément attend dans la file prête
        return self._ajouter(equipe, type_, STATUT_PRET, "To Do", cree, None, [(entree, "To Do", STATUT_PRET)], None, (), False)

    def epic(self, equipe, jours_depuis_creation) -> str:
        cree = self.maintenant - timedelta(days=jours_depuis_creation)
        return self._ajouter(equipe, "Epic", "In Progress", "In Progress", cree, None, [(cree + timedelta(days=1), "To Do", "In Progress")],
                             None, (), False)


def construire_tranche1(maintenant: datetime) -> list[dict]:
    """Les tickets de la tranche 1, dans un ordre fixe ; aucune date ne vient d'autre chose que de `maintenant` et du rang du ticket."""
    c = _Constructeur(maintenant)
    stories: dict[str, str] = {}   # première story terminée de chaque équipe, pour les liens de D33

    # Hypothèse 1, première moitié : un verdict de chaque sorte, des échantillons sous chaque taille.
    for equipe, nombre, cycle, attente in H1_STANDARD:
        jours = _Jours(equipe) if equipe in GRAPPES_H1 else None     # K : 4 éléments masqués par construction, dates au hasard des rangs
        for i in range(nombre):
            k, jour = jours.quand(i, nombre) if jours else (i % 3, None)
            cle = c.fait(equipe, "Story", k, cycle, attente, jour=jour)
            stories.setdefault(equipe, cle)
    jours = _Jours(TEMOIN_P85_DIVERGENT)
    for i in range(24):   # l'équipe H : 20 éléments qui attendent, 4 qui durent (le P85 ne suit pas la médiane)
        k, jour = jours.quand(i, 24)
        c.fait(TEMOIN_P85_DIVERGENT, "Story", k, 5 if i < 20 else 30, 15 if i < 20 else 10, jour=jour)
    jours = _Jours(TEMOIN_ANCIENS)
    for i in range(24):   # l'équipe Q : comme H, plus quinze éléments anciens ; à part « non tranché », en commun « confirmé »
        k, jour = jours.quand(i, 24)
        c.fait(TEMOIN_ANCIENS, "Story", k, 5 if i < 20 else 30, 15 if i < 20 else 10, jour=jour)
    for i in range(ANCIENS_TEMOIN):   # créés plus d'un an avant leur engagement, à compter à part ; à la suite des huit premiers de chaque trimestre
        k, jour = jours.quand(i, ANCIENS_TEMOIN, decalage=8)
        c.fait(TEMOIN_ANCIENS, "Story", k, 5, 420, ancien=True, jour=jour)
    for i in range(5):   # la file prête de l'équipe E, montrée à part
        c.pret("équipe E", "Story", 20 + 10 * i)

    # Hypothèse 5 : trois trimestres par équipe, du plus ancien au plus récent.
    epic_l = c.epic("équipe L", 300)
    for equipe, nombres, cycles in H5:
        for index, (nombre, cycle) in enumerate(zip(nombres, cycles)):
            assert nombre % GRAPPES_H5 == 0, (equipe, nombre)
            jours_h5 = jours_des_grappes((GRAPPES_H5,) * (nombre // GRAPPES_H5))
            for i in range(nombre):
                c.fait(equipe, "Story", 2 - index, cycle, 2, jour=jours_h5[i])

    # D33 : les défauts n'ont aucune équipe, terminés ou ouverts.
    for i in range(8):
        c.fait(None, "Bug", i % 3, 4, 6)
    for i in range(3):
        c.fait(None, "Bug", i % 3, 4, 6, parent=stories["équipe E"])
    for i in range(3):
        c.fait(None, "Bug", i % 3, 4, 6, liens=[(stories["équipe F"], "relates to")])
    for i in range(3):
        c.fait(None, "Bug", i % 3, 4, 6, parent=epic_l)
    for i in range(2):
        c.en_cours(None, "Bug", 40 + 10 * i, 12 + i)

    # D33 : des tâches terminées avec et sans équipe ; la part sans équipe bondit au trimestre jugé.
    # Les tâches de l'équipe R sont en grappes de 5, comme l'hypothèse 5 : leurs dates ne dépendent plus du rang du ticket, que le passage à trois
    # trimestres décale (des lignes hebdomadaires toutes visibles, donc aucun trimestre de R retiré par la relation T3, à chaque instant de chargement).
    jours_r = jours_des_grappes((GRAPPES_H5,) * (TACHES_AVEC_EQUIPE_PAR_TRIMESTRE // GRAPPES_H5))
    for k in range(3):
        for i in range(TACHES_AVEC_EQUIPE_PAR_TRIMESTRE):
            c.fait("équipe R", "Task", k, 3, 1, jour=jours_r[i])
        for j in range(TACHES_SANS_EQUIPE[2 - k]):
            if j == 0:
                c.fait(None, "Task", k, 3, 1, parent=stories["équipe E"])
            elif j == 1:
                c.fait(None, "Task", k, 3, 1, parent=epic_l)
            elif j == 2:
                c.fait(None, "Task", k, 3, 1, liens=[(stories["équipe F"], "relates to")])
            else:
                c.fait(None, "Task", k, 3, 1)

    _relier_blocages(c)
    return c.tickets


def _relier_blocages(c: _Constructeur) -> None:
    """Pose les liens « blocks » de BLOCAGES sur des stories terminées de l'équipe bloquante, vers des stories de l'équipe bloquée."""
    stories = defaultdict(list)
    for t in c.tickets:
        if t["type"] == "Story" and t["resolu"] and t["equipe"]:
            stories[t["equipe"]].append(t)
    bloqueurs_utilises: set[str] = set()
    for bloquee, k, nombre, bloqueuse in BLOCAGES:
        cibles = [t for t in stories[bloquee] if indice_trimestre(c.maintenant, t["resolu"]) == k][:nombre]
        libres = [t for t in stories[bloqueuse] if t["cle"] not in bloqueurs_utilises]
        assert len(cibles) == nombre and len(libres) >= nombre, (bloquee, k)
        for cible, bloqueur in zip(cibles, libres):
            bloqueur["liens"].append((cible["cle"], "blocks"))
            bloqueurs_utilises.add(bloqueur["cle"])
    # un lien « blocks » à l'intérieur d'une équipe : il ne compte dans aucune part bloquée par une autre équipe
    interne = stories["équipe P"]
    interne[0]["liens"].append((interne[1]["cle"], "blocks"))


def supplement(maintenant: datetime):
    """`(tickets, équipes)` que le chargeur de la tranche 0 ajoute à son jeu (tâche 14.2) : les tickets de la tranche 1 avec leurs transitions, leurs
    liens et leurs équipes, et les équipes de la tranche 1, qui entrent dans l'ensemble contrôlé des équipes synthétiques."""
    return construire_tranche1(maintenant), EQUIPES_TRANCHE1


def main(argv=None, env=None, connecter=None) -> int:
    """Le chargeur de la tranche 0 (mêmes gardes, même rôle d'import) avec le jeu de la tranche 1 en plus."""
    return base.main(argv, env, connecter, fournir_supplement=supplement)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
