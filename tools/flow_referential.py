"""Référentiel des cycles du schéma flow : structure, validation et écriture (change cycle-referential-schema, partie 1, conception D5).

Le référentiel est la copie, pour les vues agrégées, de trois blocs des réglages de flux (les cycles neutres, le rôle de chaque étiquette déclarée,
la correspondance des colonnes du Discovery Workflow avec sa date de validation). Il est écrit en entier par un chargeur, jamais à la main :
le chargeur synthétique de Mothra aujourd'hui, le chargeur du référentiel réel en partie 2. Pas de ligne de commande en partie 1.

    Referentiel          cycles, etiquettes, colonnes, statuts et valide_le (date ou None) : le contrat de données des deux chargeurs ;
                         change flow-definitions-referential : statuts_flux, types_non_planifies et types_liens_bloquants (trois tuples,
                         vides par défaut : des définitions absentes sont valides et écrites en trois tables vidées)
    definir_statut(statut, segment, point_engagement)  le StatutFlux avec ses deux drapeaux (engagé, file Ready) : le seul endroit où ils
                         se calculent (conception D3) ; le point d'engagement est obligatoire, aucun défaut
    valider(ref, decl)   rend la liste des codes de constat (jamais une valeur), dans l'ordre de CODES ; decl est l'ensemble des étiquettes
                         déclarées par les réglages que lit le chargeur : toute étiquette hors de cet ensemble donne `label_undeclared`
    ecrire(conn, ref, decl)  refuse un référentiel invalide avant toute instruction, vérifie le rôle d'import, puis remplace tout le référentiel
                         dans une seule transaction (suppressions, insertions, ligne d'état en dernier, instant pris sur l'horloge de la base) ;
                         aucune mise à jour sur place ; l'échec annule tout : l'ancien référentiel ou le nouveau, jamais un mélange

Les refus sont des ReferentielInvalide, en français, qui ne portent que des codes : jamais une clé de cycle, une étiquette, un statut,
un nom de colonne ni une date. La connexion est celle de l'appelant (réelle ou fausse, en test) ; l'appelant prend le rôle d'import
et valide ou annule sa transaction. Le module ne lit aucun fichier et n'ouvre aucune connexion.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

ROLE_ECRITURE = "pmzilla_flow"
MESSAGE_INVALIDE = "référentiel des cycles invalide : "
MESSAGE_ROLE = "référentiel des cycles : rôle d'écriture inattendu"

# Les codes de constat, dans l'ordre de la table de la conception D5 (c'est l'ordre du message).
CODES = ("cycle_key_form", "cycle_dates", "cycle_duplicate", "label_role", "label_duplicate", "label_undeclared", "label_cycle_key",
         "confirmation_meaning", "single_label_role", "column_duplicate", "start_column", "ready_column", "status_column",
         # change flow-definitions-referential, conception D4 : les six codes des définitions, après les treize des cycles
         "flow_status_duplicate", "flow_status_segment", "commitment_flag", "ready_flag", "unplanned_type", "blocking_link_type")

# Conception D2 : les segments calculés (dans l'ordre du rapport de flux), les segments non comptés, les genres et les sens permis.
SEGMENTS_CALCULES = ("definition", "ready", "implementation", "review_verification", "acceptance")
SEGMENTS_NON_COMPTES = ("todo", "done")
SEGMENTS = SEGMENTS_CALCULES + SEGMENTS_NON_COMPTES
GENRES_NON_PLANIFIE = ("defect",)
SENS_LIEN = ("blocks", "waits_for")

ROLES_ETIQUETTE = ("up_merge", "cycle", "epic_review", "pilot_domain", "ready", "confirmation")
ROLES_UNIQUES = ("pilot_domain", "ready")
SENS_CONFIRMATION = ("taken_in", "not_taken_in")
FORME_CLE_CYCLE = re.compile(r"[0-9]{4}-(C[1-6]|EOY)")

# Ordre des suppressions : les enfants d'abord ; ordre des insertions : les parents d'abord, la ligne d'état en dernier.
TABLES_A_VIDER = ("ref_flow_statuses", "ref_unplanned_types", "ref_blocking_link_types",
                  "ref_dw_statuses", "ref_dw_columns", "ref_labels", "ref_cycles", "ref_state")


class ReferentielInvalide(Exception):
    """Le référentiel n'est pas écrit : le message, en français, ne porte que des codes ou la phrase du rôle, jamais une valeur."""


@dataclass(frozen=True)
class Cycle:
    cle: str
    debut: date
    fin: date


@dataclass(frozen=True)
class Etiquette:
    etiquette: str
    role: str
    cycle_cle: str | None
    sens: str | None


@dataclass(frozen=True)
class Colonne:
    nom: str
    position: int
    depart: bool
    revue_passee: bool
    pret: bool
    active: bool


@dataclass(frozen=True)
class Statut:
    statut: str
    colonne: str


@dataclass(frozen=True)
class StatutFlux:
    statut: str
    segment: str
    engage: bool
    file_prete: bool


@dataclass(frozen=True)
class TypeNonPlanifie:
    type: str
    genre: str


@dataclass(frozen=True)
class TypeLienBloquant:
    type: str
    sens: str


@dataclass(frozen=True)
class Referentiel:
    cycles: tuple[Cycle, ...]
    etiquettes: tuple[Etiquette, ...]
    colonnes: tuple[Colonne, ...]
    statuts: tuple[Statut, ...]
    valide_le: date | None
    statuts_flux: tuple[StatutFlux, ...] = ()
    types_non_planifies: tuple[TypeNonPlanifie, ...] = ()
    types_liens_bloquants: tuple[TypeLienBloquant, ...] = ()


def _doublons(valeurs) -> bool:
    valeurs = list(valeurs)
    return len(valeurs) != len(set(valeurs))


def _forme(nom) -> str | None:
    """Le nom comparé sans casse ni espaces autour, comme le rapport de flux ; None s'il est vide ou n'est pas un texte."""
    if not isinstance(nom, str) or not nom.strip():
        return None
    return nom.strip().casefold()


def _doublons_ou_vides(noms) -> bool:
    formes = [_forme(n) for n in noms]
    return None in formes or _doublons(formes)


def definir_statut(statut: str, segment: str, point_engagement: str) -> StatutFlux:
    """Le statut avec ses deux drapeaux : seul endroit où ils se calculent (conception D3).

    Engagé : le statut est dans le segment du point d'engagement (lui seul, pas les segments suivants). File Ready : le statut est dans
    le segment `ready`. Le point d'engagement est obligatoire : aucun défaut n'est supposé ici."""
    if segment not in SEGMENTS:
        raise ReferentielInvalide(MESSAGE_INVALIDE + "flow_status_segment")
    if point_engagement not in SEGMENTS_CALCULES:
        raise ReferentielInvalide(MESSAGE_INVALIDE + "commitment_flag")
    return StatutFlux(statut, segment, segment == point_engagement, segment == "ready")


def _drapeaux_incoherents(statuts, drapeau: str, seul_segment: str | None = None) -> bool:
    """Un drapeau sur todo ou done, deux statuts d'un segment aux drapeaux différents, le drapeau dans deux segments, ou (avec `seul_segment`)
    hors de ce segment : le drapeau de la file Ready n'est permis que sur `ready` (D3). Segments inconnus ignorés."""
    par_segment: dict[str, set[bool]] = {}
    for s in statuts:
        if s.segment in SEGMENTS:
            par_segment.setdefault(s.segment, set()).add(bool(getattr(s, drapeau)))
    if any(len(valeurs) > 1 for valeurs in par_segment.values()):
        return True
    portes = [segment for segment, valeurs in par_segment.items() if True in valeurs]
    return (len(portes) > 1 or any(segment in SEGMENTS_NON_COMPTES for segment in portes)
            or (seul_segment is not None and any(segment != seul_segment for segment in portes)))


def valider(referentiel: Referentiel, etiquettes_declarees) -> list[str]:
    """Les codes de constat (chacun une fois, dans l'ordre de CODES) ; liste vide pour un référentiel valide. Jamais une valeur."""
    declarees = set(etiquettes_declarees)
    cles_de_cycle = {c.cle for c in referentiel.cycles}
    noms_de_colonne = {c.nom for c in referentiel.colonnes}
    constats = {
        "cycle_key_form": any(not isinstance(c.cle, str) or not FORME_CLE_CYCLE.fullmatch(c.cle) for c in referentiel.cycles),
        "cycle_dates": any(c.fin < c.debut for c in referentiel.cycles),
        "cycle_duplicate": _doublons(c.cle for c in referentiel.cycles),
        "label_role": any(e.role not in ROLES_ETIQUETTE for e in referentiel.etiquettes),
        "label_duplicate": _doublons(e.etiquette for e in referentiel.etiquettes),
        "label_undeclared": any(e.etiquette not in declarees for e in referentiel.etiquettes),
        "label_cycle_key": any(e.cycle_cle is not None and (e.role != "cycle" or e.cycle_cle not in cles_de_cycle)
                               for e in referentiel.etiquettes),
        "confirmation_meaning": any((e.sens not in SENS_CONFIRMATION) if e.role == "confirmation" else (e.sens is not None)
                                    for e in referentiel.etiquettes),
        "single_label_role": any(sum(1 for e in referentiel.etiquettes if e.role == role) > 1 for role in ROLES_UNIQUES),
        "column_duplicate": (_doublons(c.nom for c in referentiel.colonnes) or _doublons(c.position for c in referentiel.colonnes)
                             or any(c.position < 1 for c in referentiel.colonnes)),
        # change flow-definitions-loader (conception D4) : seule une partie des cycles entièrement vide (composition « définitions seules »)
        # n'exige pas de colonne de départ ; dès qu'elle contient quelque chose, exactement une reste exigée
        "start_column": (bool(referentiel.colonnes or referentiel.cycles or referentiel.etiquettes or referentiel.statuts
                              or referentiel.valide_le is not None)
                         and sum(1 for c in referentiel.colonnes if c.depart) != 1),
        "ready_column": sum(1 for c in referentiel.colonnes if c.pret) > 1 or any(c.pret and c.active for c in referentiel.colonnes),
        "status_column": (_doublons(s.statut for s in referentiel.statuts)
                          or any(s.colonne not in noms_de_colonne for s in referentiel.statuts)),
        "flow_status_duplicate": _doublons_ou_vides(s.statut for s in referentiel.statuts_flux),
        "flow_status_segment": any(s.segment not in SEGMENTS for s in referentiel.statuts_flux),
        "commitment_flag": _drapeaux_incoherents(referentiel.statuts_flux, "engage"),
        "ready_flag": _drapeaux_incoherents(referentiel.statuts_flux, "file_prete", "ready"),
        "unplanned_type": (_doublons_ou_vides(t.type for t in referentiel.types_non_planifies)
                           or any(t.genre not in GENRES_NON_PLANIFIE for t in referentiel.types_non_planifies)),
        "blocking_link_type": (_doublons_ou_vides(t.type for t in referentiel.types_liens_bloquants)
                               or any(t.sens not in SENS_LIEN for t in referentiel.types_liens_bloquants)),
    }
    return [code for code in CODES if constats[code]]


def ecrire(connexion, referentiel: Referentiel, etiquettes_declarees) -> None:
    """Remplace tout le référentiel dans une seule transaction, sous le rôle d'import ; lève ReferentielInvalide sinon, avant toute écriture."""
    constats = valider(referentiel, etiquettes_declarees)
    if constats:
        raise ReferentielInvalide(MESSAGE_INVALIDE + ", ".join(constats))      # aucune instruction n'a été envoyée
    if connexion.execute("SELECT current_user").fetchone()[0] != ROLE_ECRITURE:
        raise ReferentielInvalide(MESSAGE_ROLE)                                 # seule instruction envoyée : la lecture du rôle
    with connexion.transaction():
        for table in TABLES_A_VIDER:
            connexion.execute(f"DELETE FROM flow.{table}")
        for c in referentiel.cycles:
            connexion.execute("INSERT INTO flow.ref_cycles (cycle_key, start_date, end_date) VALUES (%s, %s, %s)", (c.cle, c.debut, c.fin))
        for c in referentiel.colonnes:
            connexion.execute("INSERT INTO flow.ref_dw_columns (name, position, is_start, is_review_passed, is_ready, is_active) "
                              "VALUES (%s, %s, %s, %s, %s, %s)", (c.nom, c.position, c.depart, c.revue_passee, c.pret, c.active))
        for e in referentiel.etiquettes:
            connexion.execute("INSERT INTO flow.ref_labels (label, role, cycle_key, meaning) VALUES (%s, %s, %s, %s)",
                              (e.etiquette, e.role, e.cycle_cle, e.sens))
        for s in referentiel.statuts:
            connexion.execute("INSERT INTO flow.ref_dw_statuses (status, column_name) VALUES (%s, %s)", (s.statut, s.colonne))
        for s in referentiel.statuts_flux:
            connexion.execute("INSERT INTO flow.ref_flow_statuses (status, segment, is_committed, is_ready_queue) VALUES (%s, %s, %s, %s)",
                              (s.statut, s.segment, s.engage, s.file_prete))
        for t in referentiel.types_non_planifies:
            connexion.execute("INSERT INTO flow.ref_unplanned_types (type, kind) VALUES (%s, %s)", (t.type, t.genre))
        for t in referentiel.types_liens_bloquants:
            connexion.execute("INSERT INTO flow.ref_blocking_link_types (type, direction) VALUES (%s, %s)", (t.type, t.sens))
        connexion.execute("INSERT INTO flow.ref_state (mapping_validated_on, loaded_at) VALUES (%s, now())", (referentiel.valide_le,))
