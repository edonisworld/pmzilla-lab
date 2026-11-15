"""Jeu synthétique de la page « préparation d'un cycle » de Mothra, tâche 39.1 de mothra-slices (conception D35).

Un module à part : il IMPORTE le référentiel synthétique (referentiel_synthetique.py, change cycle-referential-schema, conception D6) et n'en construit
aucun à lui (décision R-20261028-91). Les cycles, les étiquettes, les colonnes, les statuts et les deux variantes de la correspondance (`validated`,
`not_validated`) viennent de lui ; ce module ne leur ajoute que des épiques. Il ne modifie aucun module existant du dossier, et ne branche rien dans le
chargeur synthétique (tâche de chargement à part).

    construire(jour, variante, nombre_equipes)   le `Jeu` : le référentiel synthétique du jour, l'instant du chargement et les épiques (dictionnaires)

Ce que le jeu contient, pour les vues de la tâche 38.1 :
  - des épiques dans les colonnes de la correspondance (provisoire tant que la variante est `not_validated`), plus une ligne « statut non associé » ;
  - des équipes génériques du jeu synthétique (trois par défaut, deux dans la variante à deux équipes) ;
  - des périodes d'étiquettes du Discovery Workflow (Ready, revue d'épiques, confirmation prise et non prise) et d'étiquettes de cycle, avec des
    effectifs témoins de 1 à 4 (cellules à masquer) et exactement 5 (cellules rendues) ; des périodes closes pour Ready et pour la revue ;
  - le cycle prévu au début du cycle (instant de lecture : le début du cycle), distinct de l'étiquette actuelle : épiques déplacées après le début,
    épiques prévues tard (étiquette posée après le début), épiques replanifiées avant le début ;
  - des candidats à l'Epic Review (colonnes de départ ou de revue passée), avec et sans étiquette de revue ;
  - des épiques hors du domaine pilote et des épiques sans étiquette de cycle, qui restent hors des comptes ;
  - un cycle sans aucune épique (le dernier cycle à venir du référentiel synthétique) ;
  - des chaînes sentinelles en forme de clé et de titre dans des colonnes de flow.issues qu'aucune vue n'expose.

Les colonnes et les candidats ne se calculent qu'avec une correspondance validée : `lignes_par_colonne` et `candidats` rendent None pour la variante non
validée. Désignations génériques seulement. Les clés (SYN-5001 et suivantes) sont inventées. Aucune donnée réelle, aucun fichier lu. Les dates ne
dépendent que du jour du chargement et du rang de l'épique.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))      # lancé comme un script, avec -I : le dossier du script n'est pas dans le chemin
import jeu_synthetique as base  # noqa: E402
import referentiel_synthetique as rs  # noqa: E402

CLE_DEPART = 5000
PREFIXE_TITRE = "Sentinelle titre d'épique "
NON_ASSOCIE = "statut-non-associe"       # le nom de la ligne « statut non associé » de la page ; les épiques concernées portent rs.STATUT_NON_ASSOCIE
COLONNES_NON_EXPOSEES = ("cle", "resolution", "projet", "parent")     # colonnes de flow.issues : la clé, la résolution (qui porte ici le titre sentinelle)...
ETIQUETTES_DU_WORKFLOW = ("ready", "epic_review", "taken_in", "not_taken_in")
EQUIPES = tuple(sorted(base.EQUIPES_GENERIQUES))[:3]       # désignations génériques du jeu synthétique : équipes A à C (D est laissée au jeu de base)
NOMBRE_EQUIPES_DEFAUT = 3
NOMBRES_EQUIPES = (2, 3)       # trois équipes, ou la variante à deux équipes : un domaine de moins de trois équipes n'a aucun compte (R-20261031-17, Q46 ; spec jira-flow-views)

# Épiques du domaine pilote ayant une étiquette de cycle, par cycle (indice dans le référentiel) puis par colonne : les quatre colonnes par position,
# puis la ligne « statut non associé ». Témoins de 1 à 4 et de 5 ; le dernier cycle à venir n'a aucune épique.
EPIQUES_PAR_CYCLE_ET_COLONNE = {       # épiques construites par cycle de l'étiquette actuelle (celles qui sont tardives en font partie)
    0: (6, 5, 4, 3, 2),
    1: (1, 2, 3, 4, 5),
    2: (5, 1, 2, 4, 3),
    3: (0, 0, 0, 0, 0),
}
# Ce que les vues comptent par cycle et colonne (décision de l'auteur R-20261031-62, Q116) : les épiques PRÉVUES AU DÉBUT du cycle (instant de lecture de
# D35). Les tardives sortent des colonnes ; l'épique déplacée après le début reste au cycle d'origine (et compte aussi au cycle où elle est allée,
# où son étiquette était déjà posée au début). Chaque ligne somme à PREVUES_AU_DEBUT.
COMPTES_PAR_CYCLE_ET_COLONNE = {
    0: (9, 6, 4, 2, 0),
    1: (1, 2, 3, 4, 3),
    2: (5, 1, 2, 4, 3),
    3: (0, 0, 0, 0, 0),
}
# Confirmées, refusées, sans confirmation, sur les épiques prévues au début du cycle (décision R-20261031-62) : la somme est PREVUES_AU_DEBUT.
# Décision R-20261031-63 (Q118) : une confirmation ou un refus ne compte qu'au cycle pour lequel il a été donné, c'est-à-dire le cycle dont l'étiquette
# de cycle était posée à l'instant daté de la confirmation (la période de l'étiquette de confirmation). L'épique déplacée compte « sans confirmation »
# dans l'autre cycle ; un cas indéterminé (aucune étiquette de cycle posée à cet instant) compte « sans confirmation », jamais dans deux cycles.
CONFIRMATIONS_PREVUES = {0: (7, 3, 11), 1: (3, 1, 9), 2: (0, 0, 15), 3: (0, 0, 0)}
INDETERMINEES = 2       # épiques du cycle 0, prévues au début, dont l'étiquette de cycle est retirée avant la confirmation (une prise, un refus) : sans confirmation
CYCLE_SANS_EPIQUE = 3
HORS_DOMAINE = 3        # épiques du cycle 1, colonne 0, sans étiquette du domaine pilote : écartées des comptes
SANS_CYCLE = 2          # épiques du domaine sans étiquette de cycle : hors de tout cycle

# Épiques du domaine portant l'étiquette, au moins une fois, par cycle : (cycle 0, 1, 2, 3).
COMPTES_PAR_CYCLE_ET_ETIQUETTE = {
    "ready": (5, 1, 2, 0),
    "epic_review": (4, 2, 0, 0),
    "taken_in": (7, 3, 0, 0),
    "not_taken_in": (3, 1, 0, 0),
}
SANS_CONFIRMATION = (10, 11, 15, 0)      # ni prise ni non prise : le reste du cycle
CLOSES_PRET = 2         # étiquettes Ready du cycle 0 dont la période est close avant l'instant du chargement
CLOSES_REVUE = 2        # étiquettes de revue d'épiques du cycle 0 dont la période est close avant l'instant du chargement
# Étiquettes actives à l'instant du chargement, par cycle (« aujourd'hui »), à distinguer de « au moins une fois » (COMPTES_PAR_CYCLE_ET_ETIQUETTE).
ACTIFS_AUJOURDHUI = {"ready": (3, 1, 2, 0), "epic_review": (2, 2, 0, 0)}

# Déplacements : (cycle d'origine, cycle de destination, nombre d'épiques, retrait de l'étiquette d'origine avant le début du cycle d'origine).
DEPLACEMENTS = (
    (1, 2, 3, True),
    (0, 1, 2, False),
    (0, 1, 5, True),
)
REPLANIFIEES_AVANT_LE_DEBUT = {0: 5, 1: 3, 2: 0, 3: 0}      # témoins 3 et exactement 5

# Instant de lecture D35 : le cycle prévu AU DÉBUT du cycle (étiquette de cycle active au début du cycle), distinct de l'étiquette actuelle.
# L'épique déplacée du cycle 0 au cycle 1 après le début du cycle 0 compte comme prévue au cycle 0 ; l'épique « prévue tard » porte l'étiquette posée
# après le début du cycle.
TARDIVES = (3, 2, 0, 0)       # épiques par cycle dont l'étiquette de cycle est posée après le début du cycle (planned late)
PREVUES_AU_DEBUT = (21, 13, 15, 0)

# Candidats à l'Epic Review (colonne de départ ou de revue passée du référentiel, correspondance validée) : (avec étiquette de revue, sans), par cycle de
# l'étiquette actuelle. « Avec étiquette » veut dire « au moins une fois » (période close comprise), pas « aujourd'hui ».
CANDIDATS = {0: (3, 8), 1: (1, 2), 2: (0, 6), 3: (0, 0)}

# Source de l'état Ready selon la variante (codes de la page) : sous la correspondance non validée, l'étiquette seule.
SOURCE_PRET = {"not_validated": "ready_source_label", "validated": "ready_source_column"}


@dataclass(frozen=True)
class Jeu:
    referentiel: object
    instant: datetime
    epiques: tuple


def _etiquette(ref, role, sens=None, cycle_cle=None) -> str:
    """Le nom d'étiquette que le référentiel donne à ce rôle (jamais écrit ici)."""
    trouvees = [e.etiquette for e in ref.etiquettes if e.role == role and e.sens == sens and e.cycle_cle == cycle_cle]
    assert len(trouvees) >= 1, (role, sens, cycle_cle)
    return trouvees[0]


def _colonnes_et_statuts(ref) -> list[list[str]]:
    """Pour chaque colonne par position, ses statuts d'après le référentiel."""
    return [[s.statut for s in ref.statuts if s.colonne == c.nom] for c in sorted(ref.colonnes, key=lambda c: c.position)]


def _avant(instant: datetime, t: datetime) -> datetime:
    """Une période commence toujours avant l'instant du chargement."""
    return min(t, instant - timedelta(days=2))


def _debut_cycle(cycle) -> datetime:
    return datetime(cycle.debut.year, cycle.debut.month, cycle.debut.day, 8, tzinfo=timezone.utc)


def _positions_revue(total: int, nombre: int) -> list[int]:
    """Les rangs qui portent l'étiquette de revue : répartis dans le cycle, donc dans plusieurs colonnes."""
    return [(k * total) // nombre for k in range(nombre)] if nombre else []


def construire(jour: date, variante: str = rs.VARIANTE_DEFAUT, nombre_equipes: int = NOMBRE_EQUIPES_DEFAUT) -> Jeu:
    if nombre_equipes not in NOMBRES_EQUIPES:
        raise ValueError(f"préparation d'un cycle : nombre d'équipes inconnu (attendu : {', '.join(map(str, NOMBRES_EQUIPES))})")
    ref = rs.construire(jour, variante)
    instant = datetime(jour.year, jour.month, jour.day, 12, tzinfo=timezone.utc)
    equipes = EQUIPES[:nombre_equipes]
    statuts_par_colonne = _colonnes_et_statuts(ref)
    epiques: list[dict] = []
    rang = CLE_DEPART

    def nouvelle(statut, cycle_index, position):
        nonlocal rang
        rang += 1
        epique = {
            "cle": f"{base.PREFIXE_CLE}{rang}",
            "resolution": f"{PREFIXE_TITRE}{rang}",
            "projet": base.SENTINELLES[0],
            "parent": base.SENTINELLES[2],
            "type": "Epic",
            "statut": statut,
            "equipe": equipes[rang % len(equipes)],
            "cree": _debut_cycle(ref.cycles[cycle_index if cycle_index is not None else 0]) - timedelta(days=90),
            "etiquettes": [],
        }
        epiques.append(epique)
        return epique

    def periode(epique, nom, debut, fin=None):
        epique["etiquettes"].append({"etiquette": nom, "debut": debut, "fin": fin})

    domaine = _etiquette(ref, "pilot_domain")
    for c, par_colonne in EPIQUES_PAR_CYCLE_ET_COLONNE.items():
        cycle = ref.cycles[c]
        debut = _debut_cycle(cycle)
        etiquette_cycle = _etiquette(ref, "cycle", cycle_cle=cycle.cle)
        total = sum(par_colonne)
        deplacees = [(origine, avant) for origine, destination, nombre, avant in DEPLACEMENTS if destination == c for _ in range(nombre)]
        revue = _positions_revue(total, COMPTES_PAR_CYCLE_ET_ETIQUETTE["epic_review"][c])
        pris = COMPTES_PAR_CYCLE_ET_ETIQUETTE["taken_in"][c]
        non_pris = COMPTES_PAR_CYCLE_ET_ETIQUETTE["not_taken_in"][c]
        genres = ["taken_in"] * pris + ["not_taken_in"] * non_pris
        if pris and non_pris:
            genres.insert(1, genres.pop(pris))        # le premier refus au rang 1 : l'épique déplacée du rang 1 porte un refus
        position = 0
        for j, nombre in enumerate(par_colonne):
            statuts = statuts_par_colonne[j] if j < len(statuts_par_colonne) else [rs.STATUT_NON_ASSOCIE]
            for _ in range(nombre):
                e = nouvelle(statuts[position % len(statuts)], c, position)
                periode(e, domaine, _avant(instant, debut - timedelta(days=100)))
                # étiquette de cycle : posée avant le début, après un déplacement depuis un autre cycle, ou posée tard (après le début)
                debut_cycle_label = _avant(instant, debut - timedelta(days=60) + timedelta(hours=position))
                if position < len(deplacees):
                    origine, avant = deplacees[position]
                    cycle_origine = ref.cycles[origine]
                    ajoutee = _debut_cycle(cycle_origine) - timedelta(days=40)
                    retiree = _debut_cycle(cycle_origine) - timedelta(days=10) if avant else _debut_cycle(cycle_origine) + timedelta(days=5)
                    periode(e, _etiquette(ref, "cycle", cycle_cle=cycle_origine.cle), ajoutee, retiree)
                    debut_cycle_label = retiree + timedelta(hours=1)
                elif position >= total - TARDIVES[c]:
                    debut_cycle_label = _avant(instant, debut + timedelta(days=3, hours=position))
                periode(e, etiquette_cycle, debut_cycle_label)
                # Discovery Workflow : Ready en tête de cycle (les premières closes), revue répartie (les premières closes), confirmation après le début
                if position < COMPTES_PAR_CYCLE_ET_ETIQUETTE["ready"][c]:
                    fin = debut + timedelta(days=10) if (c == 0 and position < CLOSES_PRET) else None
                    periode(e, _etiquette(ref, "ready"), _avant(instant, debut - timedelta(days=20) + timedelta(hours=position)), fin)
                if position in revue:
                    fin = debut + timedelta(days=5) if (c == 0 and revue.index(position) < CLOSES_REVUE) else None
                    periode(e, _etiquette(ref, "epic_review"), _avant(instant, debut - timedelta(days=10) + timedelta(hours=position)), fin)
                if position < len(genres):
                    periode(e, _etiquette(ref, "confirmation", sens=genres[position]), _avant(instant, debut + timedelta(days=1, hours=position)))
                position += 1
    # hors du domaine pilote : un cycle, la colonne 0, aucune étiquette du domaine
    cycle = ref.cycles[1]
    for position in range(HORS_DOMAINE):
        e = nouvelle(statuts_par_colonne[0][position % len(statuts_par_colonne[0])], 1, position)
        periode(e, _etiquette(ref, "cycle", cycle_cle=cycle.cle), _avant(instant, _debut_cycle(cycle) - timedelta(days=50) + timedelta(hours=position)))
    # indéterminées : prévues au cycle 0 au début, étiquette de cycle retirée après le début ; confirmation (une prise, un refus) donnée alors qu'aucune
    # étiquette de cycle n'est posée : sans confirmation, dans aucun cycle
    cycle = ref.cycles[0]
    for position, genre in enumerate(("taken_in", "not_taken_in")[:INDETERMINEES]):
        e = nouvelle(statuts_par_colonne[0][position % len(statuts_par_colonne[0])], 0, position)
        periode(e, domaine, _avant(instant, _debut_cycle(cycle) - timedelta(days=100)))
        periode(e, _etiquette(ref, "cycle", cycle_cle=cycle.cle), _avant(instant, _debut_cycle(cycle) - timedelta(days=60) + timedelta(hours=position)),
                _debut_cycle(cycle) + timedelta(days=5))
        periode(e, _etiquette(ref, "confirmation", sens=genre), _debut_cycle(cycle) + timedelta(days=8, hours=position))
    # sans étiquette de cycle : dans le domaine, nulle part ailleurs
    for position in range(SANS_CYCLE):
        e = nouvelle(statuts_par_colonne[1][0], None, position)
        periode(e, domaine, _avant(instant, _debut_cycle(ref.cycles[1]) - timedelta(days=100)))
    return Jeu(ref, instant, tuple(epiques))


def lignes_par_colonne(jeu: Jeu):
    """Les comptes par cycle et colonne que les vues calculent : seulement avec une correspondance validée, sinon aucune ligne (None)."""
    if jeu.referentiel.valide_le is None:
        return None
    return COMPTES_PAR_CYCLE_ET_COLONNE


def candidats(jeu: Jeu):
    """Les candidats à l'Epic Review par cycle, (avec, sans étiquette de revue) : seulement avec une correspondance validée, sinon None."""
    if jeu.referentiel.valide_le is None:
        return None
    return CANDIDATS


def source_du_pret(jeu: Jeu) -> str:
    """Le code de la source de l'état Ready : l'étiquette seule sans correspondance validée, la colonne Ready avec."""
    return SOURCE_PRET["validated" if jeu.referentiel.valide_le is not None else "not_validated"]


if __name__ == "__main__":
    construit = construire(date.today())
    print(f"{len(construit.epiques)} épiques synthétiques")
