"""Extension du jeu synthétique pour les panneaux du tableau de bord du périmètre produit (R-150), tâche 36.2 de mothra-slices (conception D35, D33 point 1).

Les tranches 0 et 1 (jeu_synthetique.py, tranche1.py) restent telles quelles : leurs témoins ne changent pas. Ce module ajoute des tickets, sur des équipes
et des clés qui n'appartiennent qu'à lui, de quoi alimenter la vue des créés et des finis (v_team_flow_inout, tâche 36.1) :
  - histoires et défauts créés et finis par équipe et par trimestre civil clos (k = 0 : le dernier trimestre clos, k = 3 : le premier de l'année retenue) ;
  - des défauts avec équipe (champ d'équipe [G] rempli) et des défauts sans équipe (groupe « sans équipe »), avec des effectifs témoins de 1 à 4 et de 5
    dans les deux cas (D33 point 1, R-20261029-07 : le champ est rempli pour environ deux tiers des défauts réels) ;
  - des éléments qui doivent rester dehors : des types de portefeuille (TYPES_PORTEFEUILLE) et des éléments d'un projet exclu (PROJETS_EXCLUS), terminés
    dans les trimestres retenus ; la tâche 36.1 retire ces types et ces projets, ce jeu les déclare et ne les compte jamais dans ses tables ;
  - un premier trimestre retenu tronqué : peu d'éléments finis, et un pic de créations le jour de l'import de l'historique (JOURS_AVANT_LE_PIC après le début du
    trimestre) ; des éléments créés avant l'année retenue et finis dedans ;
  - un trimestre en cours qui ne doit jamais être servi : des éléments créés, des éléments finis et des éléments créés avant et finis dans ce trimestre ;
  - des éléments bloqués par une autre équipe (liens « blocks » portés par l'élément bloquant, qui cible l'élément bloqué) et par la même équipe (qui ne compte
    pas dans la part bloquée par une autre équipe) ;
  - des effectifs témoins de 1 à 4 (cellules à masquer) et exactement 5 (cellules rendues), des cellules plus grandes ;
  - un cas vide : une équipe dont aucun élément ne tombe dans une cellule servie ;
  - des chaînes sentinelles dans les colonnes qu'aucune vue n'expose (projet, résolution, ticket parent).

Les trimestres sont civils, alignés sur celui de l'instant du chargement, comme dans la tranche 1 : les dates des éléments des trimestres clos ne dépendent pas de
l'instant de chargement dans un trimestre, à 5 jours au moins de chaque bord. Seuls les éléments du trimestre en cours se placent par rapport à l'instant.

Équipes : désignations génériques « équipe V » à « équipe Z », distinctes des tranches 0 et 1. Clés : SYN-3001 et suivantes, inventées. Aucune donnée réelle.
Le chargeur de la tranche 0 écrit ce jeu avec celui de la tranche 1 (`supplement`, `main`) ; tools/dbtest.sh charge jeu_synthetique.py seul, rien ici ne l'y branche.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))      # lancé comme un script, avec -I : le dossier du script n'est pas dans le chemin
import jeu_synthetique as base  # noqa: E402
import tranche1 as t1  # noqa: E402

EQUIPES_PANNEAUX = tuple(f"équipe {lettre}" for lettre in "VWXYZ") + ("équipe W2",)       # W2 : témoin des tâches (R-20261114-79), aucune lettre libre
CLE_DEPART = 3000
COURANT = "courant"           # le trimestre en cours, jamais servi
PROJET_EXCLU = "SYN-projet-exclu"
PROJETS_EXCLUS = (PROJET_EXCLU,)
TYPES_PORTEFEUILLE = ("Epic", "Initiative")
JOURS_AVANT_LE_PIC = 5        # le pic d'import tombe 5 jours après le début du premier trimestre retenu (marge au bord)
ELEMENTS_DU_PIC = 30          # au moins ce nombre d'éléments créés dans les deux jours du pic

EQUIPE_GRANDE, TEMOIN_PETIT, EQUIPE_BLOQUEE, EQUIPE_BLOQUANTE, TEMOIN_VIDE, TEMOIN_TACHES = EQUIPES_PANNEAUX
TYPE_HISTOIRE = "Story"

# Flux d'éléments de la population : (équipe ou None, type, trimestre de création, trimestre de fin, nombre, pic d'import).
# Trimestre : 0 à 3 (clos), 4 (avant l'année retenue, création seulement), COURANT, None (non fini).
FLUX = (
    # équipe V : tous les comptes à 5 et plus, créés et finis qui diffèrent ; premier trimestre retenu tronqué avec son pic d'import
    (EQUIPE_GRANDE, TYPE_HISTOIRE, 4, 3, 4, False),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, 3, 3, 8, False),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, 3, 2, 20, True),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, 3, 1, 5, True),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, 3, None, 5, True),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, 3, 0, 2, False),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, 2, 2, 10, False),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, 2, 1, 3, False),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, 2, 0, 4, False),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, 2, None, 5, False),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, 1, 1, 9, False),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, 1, 0, 6, False),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, 1, None, 3, False),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, 1, COURANT, 2, False),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, 0, 0, 12, False),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, 0, None, 6, False),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, 0, COURANT, 3, False),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, 4, 0, 3, False),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, COURANT, COURANT, 4, False),
    # équipe W : des effectifs de 1 à 4 (cellules à masquer) et de 5 (rendues)
    (TEMOIN_PETIT, TYPE_HISTOIRE, 0, 0, 4, False),
    (TEMOIN_PETIT, TYPE_HISTOIRE, 1, 0, 1, False),
    (TEMOIN_PETIT, TYPE_HISTOIRE, 0, None, 1, False),
    (TEMOIN_PETIT, TYPE_HISTOIRE, 1, 1, 2, False),
    (TEMOIN_PETIT, TYPE_HISTOIRE, 2, 2, 4, False),
    (TEMOIN_PETIT, TYPE_HISTOIRE, 3, 3, 1, False),
    # équipes X (bloquée) et Y (bloquante) : créés égaux aux finis, les liens « blocks » se posent sur les finis
    (EQUIPE_BLOQUEE, TYPE_HISTOIRE, 0, 0, 12, False),
    (EQUIPE_BLOQUEE, TYPE_HISTOIRE, 1, 1, 8, False),
    (EQUIPE_BLOQUEE, TYPE_HISTOIRE, 2, 2, 6, False),
    (EQUIPE_BLOQUEE, TYPE_HISTOIRE, 3, 3, 5, False),
    (EQUIPE_BLOQUANTE, TYPE_HISTOIRE, 0, 0, 9, False),
    (EQUIPE_BLOQUANTE, TYPE_HISTOIRE, 1, 1, 6, False),
    (EQUIPE_BLOQUANTE, TYPE_HISTOIRE, 2, 2, 5, False),
    (EQUIPE_BLOQUANTE, TYPE_HISTOIRE, 3, 3, 3, False),
    # défauts sans équipe (champ d'équipe [G] vide, groupe « sans équipe ») : effectifs témoins 1 à 5, le pic d'import compte aussi pour eux
    (None, base.TYPE_DEFAUT, 4, 3, 1, False),
    (None, base.TYPE_DEFAUT, 3, 3, 3, False),
    (None, base.TYPE_DEFAUT, 3, 2, 8, True),
    (None, base.TYPE_DEFAUT, 3, None, 4, True),
    (None, base.TYPE_DEFAUT, 2, 2, 4, False),
    (None, base.TYPE_DEFAUT, 2, None, 1, False),
    (None, base.TYPE_DEFAUT, 1, 1, 1, False),
    (None, base.TYPE_DEFAUT, 1, 0, 1, False),
    (None, base.TYPE_DEFAUT, 0, 0, 3, False),
    (None, base.TYPE_DEFAUT, COURANT, COURANT, 3, False),
    # défauts avec équipe (champ d'équipe [G] rempli, R-20261029-07) : équipe V, comptes de 5 et plus
    (EQUIPE_GRANDE, base.TYPE_DEFAUT, 3, 3, 6, False),
    (EQUIPE_GRANDE, base.TYPE_DEFAUT, 2, 2, 7, False),
    (EQUIPE_GRANDE, base.TYPE_DEFAUT, 2, 1, 3, False),
    (EQUIPE_GRANDE, base.TYPE_DEFAUT, 1, 1, 6, False),
    (EQUIPE_GRANDE, base.TYPE_DEFAUT, 1, 0, 2, False),
    (EQUIPE_GRANDE, base.TYPE_DEFAUT, 0, 0, 8, False),
    (EQUIPE_GRANDE, base.TYPE_DEFAUT, 0, None, 2, False),
    # défauts avec équipe : équipe W, effectifs témoins 1 à 4 et 5
    (TEMOIN_PETIT, base.TYPE_DEFAUT, 0, 0, 3, False),
    (TEMOIN_PETIT, base.TYPE_DEFAUT, 0, None, 2, False),
    (TEMOIN_PETIT, base.TYPE_DEFAUT, 1, 1, 2, False),
    (TEMOIN_PETIT, base.TYPE_DEFAUT, 1, None, 2, False),
    (TEMOIN_PETIT, base.TYPE_DEFAUT, 2, 2, 1, False),
    (TEMOIN_PETIT, base.TYPE_DEFAUT, 3, 3, 4, False),
    (TEMOIN_PETIT, base.TYPE_DEFAUT, 3, None, 1, False),
)

# Éléments qui doivent rester hors des comptes : (équipe, type, projet, trimestre de création, trimestre de fin, nombre).
EXCLUS = (
    (EQUIPE_GRANDE, "Epic", base.SENTINELLES[0], 0, 0, 6),
    (EQUIPE_GRANDE, "Initiative", base.SENTINELLES[0], 1, 1, 3),
    (EQUIPE_GRANDE, "Epic", base.SENTINELLES[0], 2, None, 2),
    (TEMOIN_PETIT, "Epic", base.SENTINELLES[0], 0, 0, 5),
    (None, "Initiative", base.SENTINELLES[0], 0, 0, 3),
    (EQUIPE_GRANDE, TYPE_HISTOIRE, PROJET_EXCLU, 0, 0, 5),
    (TEMOIN_PETIT, TYPE_HISTOIRE, PROJET_EXCLU, 1, 1, 4),
    (None, base.TYPE_DEFAUT, PROJET_EXCLU, 1, 1, 4),
    (None, base.TYPE_DEFAUT, PROJET_EXCLU, 0, 0, 6),
    (EQUIPE_GRANDE, base.TYPE_DEFAUT, PROJET_EXCLU, 0, 0, 3),
    # cas vide : l'équipe Z n'a que ces éléments et une histoire du trimestre en cours, aucun ne tombe dans une cellule servie
    (TEMOIN_VIDE, "Epic", base.SENTINELLES[0], 0, 0, 3),
    (TEMOIN_VIDE, TYPE_HISTOIRE, PROJET_EXCLU, 1, 1, 2),
    (TEMOIN_VIDE, TYPE_HISTOIRE, base.SENTINELLES[0], COURANT, COURANT, 2),
)

# Comptes attendus de la population (hors portefeuille, hors projet exclu, trimestres clos 0 à 3), clé (équipe ou None, groupe de types, k) ; les tests les recalculent.
_CREES = {
    (EQUIPE_GRANDE, "story"): {3: 40, 2: 22, 1: 20, 0: 21},
    (TEMOIN_PETIT, "story"): {3: 1, 2: 4, 1: 3, 0: 5},
    (EQUIPE_BLOQUEE, "story"): {3: 5, 2: 6, 1: 8, 0: 12},
    (EQUIPE_BLOQUANTE, "story"): {3: 3, 2: 5, 1: 6, 0: 9},
    (None, "defect"): {3: 15, 2: 5, 1: 2, 0: 3},
    (EQUIPE_GRANDE, "defect"): {3: 6, 2: 10, 1: 8, 0: 10},
    (TEMOIN_PETIT, "defect"): {3: 5, 2: 1, 1: 4, 0: 5},
    (TEMOIN_TACHES, "story"): {1: 1},          # équipe W2 : la story du témoin des tâches (voir FLUX_TEMOIN_TACHES)
}
_TERMINES = {
    (EQUIPE_GRANDE, "story"): {3: 12, 2: 30, 1: 17, 0: 27},
    (TEMOIN_PETIT, "story"): {3: 1, 2: 4, 1: 2, 0: 5},
    (EQUIPE_BLOQUEE, "story"): {3: 5, 2: 6, 1: 8, 0: 12},
    (EQUIPE_BLOQUANTE, "story"): {3: 3, 2: 5, 1: 6, 0: 9},
    (None, "defect"): {3: 4, 2: 12, 1: 1, 0: 4},
    (EQUIPE_GRANDE, "defect"): {3: 6, 2: 7, 1: 9, 0: 10},
    (TEMOIN_PETIT, "defect"): {3: 4, 2: 1, 1: 2, 0: 3},
    (TEMOIN_TACHES, "story"): {1: 1},
}
# Témoins Task (tâche 36.1, décision R-20261031-27 Q58, plan R-150 Q2 A) : le groupe de types `story` de la vue couvre Story et Task. Les tâches sont des
# éléments à part, dans des tables à part : CREES_ATTENDUS et TERMINES_ATTENDUS restent ceux de Story seul. Valeur d'une cellule du groupe `story` de la
# vue = Story + Task. Flux : (équipe, trimestre de création, trimestre de fin, nombre) ; mêmes conventions que FLUX (None : non fini).
TYPE_TACHE = "Task"
# Équipe W2 (R-20261114-79) : EXACTEMENT 1 story + 2 tâches, créées et finies au trimestre 1 (dans la fenêtre de trois trimestres), rien d'autre. Dans le groupe `story`
# de la vue : 1 + 2 = 3 créés et 1 + 2 = 3 finis, sous 5 : cellule masquée. Les stories sont construites avant toutes les tâches (clés des témoins existants intactes).
FLUX_TEMOIN_TACHES = (
    (TEMOIN_TACHES, TYPE_HISTOIRE, 1, 1, 1, False),
)
FLUX_TACHES = (
    (TEMOIN_PETIT, 2, 2, 1),        # équipe W, trimestre 2 : 4 stories + 1 tâche = 5 (le plancher est franchi grâce à la tâche)
    (TEMOIN_PETIT, 3, 3, 2),        # équipe W, trimestre 3 : 1 story + 2 tâches = 3 (reste masqué ; hors de la fenêtre de trois trimestres, gardé tel quel)
    (EQUIPE_GRANDE, 1, 1, 3),
    (EQUIPE_GRANDE, 0, None, 2),    # créées, non finies
    (EQUIPE_GRANDE, 3, 2, 2),       # créées au premier trimestre retenu, finies au trimestre 2
    (TEMOIN_TACHES, 1, 1, 2),       # équipe W2, trimestre 1 : 1 story + 2 tâches = 3 créés et 3 finis (reste masqué)
)
CREES_TACHES = {(TEMOIN_PETIT, 2): 1, (TEMOIN_PETIT, 3): 2, (EQUIPE_GRANDE, 1): 3, (EQUIPE_GRANDE, 0): 2, (EQUIPE_GRANDE, 3): 2, (TEMOIN_TACHES, 1): 2}
TERMINES_TACHES = {(TEMOIN_PETIT, 2): 1, (TEMOIN_PETIT, 3): 2, (EQUIPE_GRANDE, 1): 3, (EQUIPE_GRANDE, 2): 2, (TEMOIN_TACHES, 1): 2}
CREES_ATTENDUS = {(e, g, k): n for (e, g), par_k in _CREES.items() for k, n in par_k.items()}
TERMINES_ATTENDUS = {(e, g, k): n for (e, g), par_k in _TERMINES.items() for k, n in par_k.items()}

# Éléments terminés de l'équipe bloquée (k) portant un lien « blocks » entrant : d'une autre équipe (cellules 3, 5, 7), de la même équipe (à part).
BLOQUES_PAR_UNE_AUTRE_EQUIPE = {(EQUIPE_BLOQUEE, 0): 7, (EQUIPE_BLOQUEE, 1): 3, (EQUIPE_BLOQUEE, 2): 5}
BLOQUES_PAR_LA_MEME_EQUIPE = {(EQUIPE_BLOQUEE, 0): 2, (EQUIPE_BLOQUEE, 1): 4}


class _Constructeur:
    def __init__(self, maintenant: datetime):
        self.maintenant = maintenant
        self.tickets: list[dict] = []
        self.rang = CLE_DEPART

    def _debut(self, k: int) -> datetime:
        """Début du trimestre civil clos d'indice k (4 : celui d'avant l'année retenue)."""
        return t1.debut_trimestre(self.maintenant, k + 1)

    def _en_cours(self, fraction: float) -> datetime:
        debut = t1.debut_trimestre(self.maintenant, 0)
        return debut + (self.maintenant - debut) * fraction

    def _fin(self, kd) -> datetime:
        if kd == COURANT:
            return self._en_cours(0.5)
        return self._debut(kd) + timedelta(days=8 + (self.rang * 7) % 75, hours=self.rang % 24)     # de 8 à 82 jours : à 5 jours au moins des deux bords

    def _creation(self, kc, kd, resolu, pic: bool) -> datetime:
        if kc == COURANT:
            return self._en_cours(0.25)
        if pic:
            return self._debut(3) + timedelta(days=JOURS_AVANT_LE_PIC, hours=self.rang % 36)
        if kc == kd:
            return resolu - timedelta(days=1 + self.rang % 2, hours=self.rang % 5)
        return self._debut(kc) + timedelta(days=8 + (self.rang * 5) % 75, hours=self.rang % 24)

    def ajouter(self, equipe, type_, projet, kc, kd, pic=False) -> dict:
        self.rang += 1
        resolu = self._fin(kd) if kd is not None else None
        cree = self._creation(kc, kd, resolu, pic)
        fini = resolu is not None
        statut = "Done" if fini else ("To Do" if self.rang % 2 == 0 else "In Progress")
        ticket = {
            "cle": f"{base.PREFIXE_CLE}{self.rang}",
            "projet": projet,
            "type": type_,
            "statut": statut,
            "categorie": statut,
            "cree": cree,
            "resolu": resolu,
            "resolution": base.SENTINELLES[1] if fini else None,
            "debut": resolu or cree,
            "points": 1 + self.rang % 5,
            "maj": resolu or cree,
            "equipe": equipe,
            "equipes": [equipe] if equipe else [],
            "parent": base.SENTINELLES[2] if self.rang % 3 == 0 else None,
            "liens": [],
            "transitions": [],
        }
        self.tickets.append(ticket)
        return ticket


def construire_panneaux(maintenant: datetime) -> list[dict]:
    """Les tickets des panneaux, dans un ordre fixe ; aucune date ne vient d'autre chose que de `maintenant` et du rang du ticket."""
    c = _Constructeur(maintenant)
    for equipe, type_, kc, kd, nombre, pic in FLUX:
        for _ in range(nombre):
            c.ajouter(equipe, type_, base.SENTINELLES[0], kc, kd, pic)
    for equipe, type_, projet, kc, kd, nombre in EXCLUS:
        for _ in range(nombre):
            c.ajouter(equipe, type_, projet, kc, kd)
    for equipe, type_, kc, kd, nombre, pic in FLUX_TEMOIN_TACHES:     # la story du témoin des tâches : avant toute tâche
        for _ in range(nombre):
            c.ajouter(equipe, type_, base.SENTINELLES[0], kc, kd, pic)
    for equipe, kc, kd, nombre in FLUX_TACHES:          # après tous les autres : les clés des témoins existants ne bougent pas
        for _ in range(nombre):
            c.ajouter(equipe, TYPE_TACHE, base.SENTINELLES[0], kc, kd)
    _relier_blocages(c)
    return c.tickets


def _termines_par_trimestre(c: _Constructeur, equipe: str) -> dict[int, list[dict]]:
    par_k: dict[int, list[dict]] = {k: [] for k in range(4)}
    for t in c.tickets:
        if t["equipe"] == equipe and t["type"] == TYPE_HISTOIRE and t["projet"] == base.SENTINELLES[0] and t["resolu"]:
            k = t1.indice_trimestre(c.maintenant, t["resolu"])
            if 0 <= k <= 3:
                par_k[k].append(t)
    return par_k


def _relier_blocages(c: _Constructeur) -> None:
    """Pose les liens « blocks » : l'élément bloquant (porteur du lien) pointe l'élément bloqué ; les cibles de l'autre équipe sont les premières du trimestre,
    celles de la même équipe les dernières, donc les deux jeux de cibles sont disjoints."""
    bloquee = _termines_par_trimestre(c, EQUIPE_BLOQUEE)
    bloquants = iter([t for k in range(4) for t in _termines_par_trimestre(c, EQUIPE_BLOQUANTE)[k]])
    for (_, k), nombre in BLOQUES_PAR_UNE_AUTRE_EQUIPE.items():
        assert len(bloquee[k]) >= nombre + BLOQUES_PAR_LA_MEME_EQUIPE.get((EQUIPE_BLOQUEE, k), 0), k
        for cible in bloquee[k][:nombre]:
            next(bloquants)["liens"].append((cible["cle"], "blocks"))
    internes = bloquee[3]
    for (_, k), nombre in BLOQUES_PAR_LA_MEME_EQUIPE.items():
        for rang, cible in enumerate(bloquee[k][-nombre:]):
            internes[rang % len(internes)]["liens"].append((cible["cle"], "blocks"))


def supplement(maintenant: datetime):
    """`(tickets, équipes)` que le chargeur de la tranche 0 ajoute à son jeu : la tranche 1 inchangée, puis les panneaux, et les équipes des deux."""
    tickets, equipes = t1.supplement(maintenant)
    return tickets + construire_panneaux(maintenant), tuple(equipes) + EQUIPES_PANNEAUX


def main(argv=None, env=None, connecter=None) -> int:
    """Le chargeur de la tranche 0 (mêmes gardes, même rôle d'import) avec les jeux des tranches 1 et des panneaux en plus."""
    return base.main(argv, env, connecter, fournir_supplement=supplement)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
