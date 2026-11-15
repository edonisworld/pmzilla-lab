"""Référentiel synthétique des cycles de Mothra (change cycle-referential-schema, conception D6) : une fonction pure du jour du chargement.

    construire(jour, variante)   le Referentiel de tools/flow_referential.py : quatre cycles de huit semaines, du lundi au vendredi, contigus
                                 (un terminé, un en cours le jour du chargement, deux à venir ; le dernier à venir est celui que la tâche 39.1
                                 de mothra-slices laisse sans épique) ; une étiquette par rôle, deux étiquettes de fusion, une étiquette par
                                 cycle qui nomme sa clé, deux étiquettes de confirmation (une par sens) ; quatre colonnes (départ actif,
                                 revue passée active, Ready non active, une colonne simple) et au moins un statut par colonne
    etiquettes_declarees(jour)   l'ensemble que le jeu synthétique déclare, son substitut du bloc des étiquettes déclarées des réglages de flux :
                                 le chargeur le passe à `ecrire`, et le référentiel n'utilise que ces étiquettes
    STATUT_NON_ASSOCIE           un statut inventé que le référentiel ne range dans aucune colonne (la ligne « statut non associé » de la page)
    charger(conn, jour, variante)  écrit ce référentiel par `ecrire`, sous le rôle d'import, dans la transaction de l'appelant

Deux variantes de la correspondance, choisies par argument : `validated` (date de validation quelques jours avant le jour du chargement) et
`not_validated` (aucune date), par défaut : l'état réel à la démonstration. Tout est inventé, préfixé par celui du jeu synthétique (SYN-) ; aucun
réglage de flux n'est lu, aucune valeur n'en est copiée, rien ne se déduit de données réelles, aucun fichier n'est ouvert. Dates : un jour donné
donne toujours les mêmes cycles ; le cycle en cours est placé de sorte que le jour du chargement tombe à sa quatrième semaine, même un samedi.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import flow_referential as fr  # noqa: E402

PREFIXE = "SYN-"      # celui des clés du jeu synthétique (jeu_synthetique.PREFIXE_CLE, gardé égal par test_referentiel)
VARIANTES = ("not_validated", "validated")
VARIANTE_DEFAUT = "not_validated"
JOURS_AVANT_LE_CHARGEMENT = 5       # variante validée : la date de validation précède le jour du chargement de ces jours
SEMAINES = 8
DUREE_JOURS = 53                    # huit semaines, du lundi au vendredi (celle de tools/flux_config.py)
STATUT_NON_ASSOCIE = PREFIXE + "statut-sans-colonne"

_FIXES = {
    "up_merge": (PREFIXE + "fusion-1", PREFIXE + "fusion-2"),
    "epic_review": PREFIXE + "revue-epique",
    "pilot_domain": PREFIXE + "domaine-pilote",
    "ready": PREFIXE + "pret",
    "confirmation": {"taken_in": PREFIXE + "confirme-pris", "not_taken_in": PREFIXE + "confirme-non-pris"},
}


POINT_ENGAGEMENT = "ready"          # le point d'engagement des définitions synthétiques (conception D8)
TYPE_LIEN_BLOQUE = PREFIXE + "lien-bloque"      # inventés, préfixés : le module n'importe rien du jeu (décision R-20261029-15)
TYPE_LIEN_ATTENTE = PREFIXE + "lien-attend"
TYPE_DEFAUT_INVENTE = PREFIXE + "type-defaut"   # le type de défaut quand l'appelant ne donne pas celui du jeu
_SEGMENT_DE_CATEGORIE = {"To Do": "todo", "In Progress": "implementation", "Done": "done"}     # catégories que le jeu emploie
_STATUTS_INVENTES = {"definition": PREFIXE + "statut-definition", "ready": PREFIXE + "statut-pret",
                     "implementation": PREFIXE + "statut-realisation", "review_verification": PREFIXE + "statut-verification",
                     "acceptance": PREFIXE + "statut-acceptation", "todo": PREFIXE + "statut-a-faire", "done": PREFIXE + "statut-termine"}


STATUT_PRET = _STATUTS_INVENTES["ready"]        # le statut du segment « prêt » : le jeu de la tranche 1 le déclare dans ses transitions (R-20261029-21)


def definitions(noms_du_jeu=None) -> tuple[tuple[fr.StatutFlux, ...], tuple[fr.TypeNonPlanifie, ...], tuple[fr.TypeLienBloquant, ...]]:
    """Les définitions synthétiques, un statut au moins par segment, le type de défaut, un type de lien par sens.

    `noms_du_jeu` : ce que l'appelant tire du jeu synthétique, `{"statuts": {statut: catégorie}, "type_defaut": nom}` (jeu_synthetique.main le
    construit depuis GROUPES et TYPE_DEFAUT, les tests depuis le module du jeu) ; sans lui, tout est inventé. Un statut du jeu garde son nom et
    prend le segment de sa catégorie ; un segment qu'aucun statut du jeu ne couvre reçoit un statut inventé. Les types de lien sont inventés."""
    noms_du_jeu = noms_du_jeu or {}
    statuts = {nom: _SEGMENT_DE_CATEGORIE[categorie] for nom, categorie in sorted(noms_du_jeu.get("statuts", {}).items())}
    couverts = set(statuts.values())
    inventes = {**_STATUTS_INVENTES, "ready": noms_du_jeu.get("statut_pret") or STATUT_PRET}   # le jeu peut fournir le nom du statut prêt et du type de lien
    statuts.update({nom: segment for segment, nom in inventes.items() if segment not in couverts})
    return (tuple(fr.definir_statut(nom, segment, POINT_ENGAGEMENT) for nom, segment in statuts.items()),
            (fr.TypeNonPlanifie(noms_du_jeu.get("type_defaut") or TYPE_DEFAUT_INVENTE, "defect"),),
            (fr.TypeLienBloquant(noms_du_jeu.get("type_lien_bloquant") or TYPE_LIEN_BLOQUE, "blocks"),
             fr.TypeLienBloquant(TYPE_LIEN_ATTENTE, "waits_for")))


def _cycles(jour: date) -> tuple[fr.Cycle, ...]:
    lundi = jour - timedelta(days=jour.weekday())
    debut_en_cours = lundi - timedelta(weeks=3)        # le jour du chargement est dans la quatrième semaine du cycle en cours
    annee = debut_en_cours.year
    cycles = []
    for rang, decalage in enumerate((-1, 0, 1, 2), start=1):        # un terminé, un en cours, deux à venir
        debut = debut_en_cours + timedelta(weeks=SEMAINES * decalage)
        cycles.append(fr.Cycle(f"{annee}-C{rang}", debut, debut + timedelta(days=DUREE_JOURS)))
    return tuple(cycles)


def _etiquette_de_cycle(cle: str) -> str:
    return f"{PREFIXE}cycle-{cle}"


def etiquettes_declarees(jour: date) -> frozenset[str]:
    """Les étiquettes que le jeu synthétique déclare pour ce jour : les fixes et celles des quatre cycles."""
    fixes = {*_FIXES["up_merge"], _FIXES["epic_review"], _FIXES["pilot_domain"], _FIXES["ready"], *_FIXES["confirmation"].values()}
    return frozenset(fixes | {_etiquette_de_cycle(c.cle) for c in _cycles(jour)})


def construire(jour: date, variante: str = VARIANTE_DEFAUT, noms_du_jeu=None) -> fr.Referentiel:
    if variante not in VARIANTES:
        raise ValueError(f"référentiel synthétique : variante inconnue (attendu : {', '.join(VARIANTES)})")
    cycles = _cycles(jour)
    etiquettes = (
        *(fr.Etiquette(nom, "up_merge", None, None) for nom in _FIXES["up_merge"]),
        *(fr.Etiquette(_etiquette_de_cycle(c.cle), "cycle", c.cle, None) for c in cycles),
        fr.Etiquette(_FIXES["epic_review"], "epic_review", None, None),
        fr.Etiquette(_FIXES["pilot_domain"], "pilot_domain", None, None),
        fr.Etiquette(_FIXES["ready"], "ready", None, None),
        *(fr.Etiquette(nom, "confirmation", None, sens) for sens, nom in _FIXES["confirmation"].items()),
    )
    colonnes = (
        fr.Colonne(PREFIXE + "colonne-a", 1, True, False, False, True),
        fr.Colonne(PREFIXE + "colonne-b", 2, False, True, False, True),
        fr.Colonne(PREFIXE + "colonne-c", 3, False, False, True, False),
        fr.Colonne(PREFIXE + "colonne-d", 4, False, False, False, False),
    )
    statuts = (
        fr.Statut(PREFIXE + "statut-a1", PREFIXE + "colonne-a"), fr.Statut(PREFIXE + "statut-a2", PREFIXE + "colonne-a"),
        fr.Statut(PREFIXE + "statut-b1", PREFIXE + "colonne-b"),
        fr.Statut(PREFIXE + "statut-c1", PREFIXE + "colonne-c"),
        fr.Statut(PREFIXE + "statut-d1", PREFIXE + "colonne-d"),
    )
    valide_le = jour - timedelta(days=JOURS_AVANT_LE_CHARGEMENT) if variante == "validated" else None
    statuts_flux, types_non_planifies, types_liens_bloquants = definitions(noms_du_jeu)
    return fr.Referentiel(cycles=cycles, etiquettes=etiquettes, colonnes=colonnes, statuts=statuts, valide_le=valide_le,
                          statuts_flux=statuts_flux, types_non_planifies=types_non_planifies, types_liens_bloquants=types_liens_bloquants)


def charger(conn, jour: date, variante: str = VARIANTE_DEFAUT, noms_du_jeu=None) -> None:
    """Écrit le référentiel synthétique par `ecrire`, sous le rôle d'import pris en local dans une transaction de la connexion de l'appelant."""
    referentiel = construire(jour, variante, noms_du_jeu)
    with conn.transaction():
        conn.execute(f"SET LOCAL ROLE {fr.ROLE_ECRITURE}")
        fr.ecrire(conn, referentiel, etiquettes_declarees(jour))
