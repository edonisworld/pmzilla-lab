"""Aide des tests du rapport de flux des épics (R-89) : épics, périodes et contexte inventés, sans clé ni nom réel.

Un épic est le dictionnaire que rend `flow_store.lire_epics` (conception D13) : type, projet, etat, cree, resolu, classe, equipes,
transitions [(instant, départ, arrivée)], periodes [{role, cycle, sens, ajout, retrait}], a_historique. Les instants portent le
fuseau d'export de test (UTC-5, sans heure d'été) : une heure locale tardive tombe le lendemain en UTC.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import flux_config  # noqa: E402

FUSEAU = ZoneInfo("Etc/GMT+5")
UTC = dt.timezone.utc


def cycle(cle: str, debut: str, fin: str) -> flux_config.Cycle:
    return flux_config.Cycle(cle, "v-" + cle, dt.date.fromisoformat(debut), dt.date.fromisoformat(fin), None, False)


CYCLES = [cycle("2026-C1", "2026-01-05", "2026-02-27"), cycle("2026-C2", "2026-03-02", "2026-04-24"),
          cycle("2026-C3", "2026-04-27", "2026-06-19")]
DISCOVERY = {"columns": {"Idee": ["s-idee", "s-cadrage"], "Revue": ["s-revue"], "Pret": ["s-pret"], "Fait": ["s-fait"]},
             "start_column": "Idee", "review_passed_columns": ["Pret"], "ready_column": "Pret",
             "active_columns": ["Idee", "Revue"], "validated_on": dt.date(2026, 1, 2), "validated": True}


def inst(texte: str) -> dt.datetime:
    """Instant 'AAAA-MM-JJ' ou 'AAAA-MM-JJTHH:MM' dans le fuseau d'export de test."""
    return dt.datetime.fromisoformat(texte).replace(tzinfo=FUSEAU)


def periode(role: str, ajout: str, retrait: str | None = None, cycle: str | None = None, sens: str | None = None) -> dict:
    return {"role": role, "cycle": cycle, "sens": sens, "ajout": inst(ajout), "retrait": inst(retrait) if retrait else None}


def domaine(ajout: str = "2026-01-02", retrait: str | None = None) -> dict:
    return periode("pilot_domain", ajout, retrait)


def epic(cree: str = "2026-01-02", etat: str = "s-idee", transitions=(), periodes=None, resolu=None, classe=None,
         equipes=("Alpha",), a_historique: bool = True) -> dict:
    """Épic du pilote par défaut (période du domaine ouverte dès la création). `resolu` : instant ou texte."""
    if isinstance(resolu, str):
        resolu = inst(resolu)
    return {"type": "Epic", "projet": "ZZE", "etat": etat, "cree": inst(cree), "resolu": resolu,
            "classe": classe if classe is not None else ("done" if resolu else None), "equipes": list(equipes),
            "transitions": [(inst(t), d, a) for t, d, a in transitions],
            "periodes": [domaine()] + list(periodes or []) if periodes is not None else [domaine()],
            "a_historique": a_historique}


def contexte(**changements) -> dict:
    base = {"cycles": CYCLES, "discovery": DISCOVERY, "fuseau": FUSEAU, "aujourdhui": dt.date(2026, 7, 1),
            "source_ready": "colonne", "epic_review": True, "cycles_lies": True, "reference_p85": None}
    base.update(changements)
    return base
