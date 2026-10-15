"""
PMZilla Lab : lecture commune du cache de l'historique des états et des segments.

Utilisé par history_jira.py (collect, check) et flux_jira.py (compute --history) : une seule fonction lit
le cache, une seule table range les états dans les segments, pour que les deux ne puissent pas diverger.
Aucune dépendance hors bibliothèque standard.

Format du cache (Flux-Lab/historique/transitions.json) :
    {"<clé>": {"termine": bool, "transitions": [[date, état de départ, état d'arrivée], ...],
               "resolu": date de résolution | null, "vu_le": dernier jour vu dans un export | null,
               "versions": [[date, "add"|"remove", version], ...], "etiquettes": [[date, "add"|"remove", étiquette], ...]}}
Les quatre dernières clés sont facultatives (conservation d'un an, R-58 : horloge du design D1 ; périodes d'étiquettes déclarées
et de versions) : un ancien cache sans elles se lit comme un cache sans date, sans version et sans étiquette.
La date est un texte ISO 8601 avec décalage (2026-03-01T09:00:00.000+0200). L'API groupée de Jira peut la donner
sous une autre forme (millisecondes depuis 1970, en nombre ou en texte) : normaliser_date la ramène au format ISO
(en UTC dans ce cas) aussi bien à la collecte qu'à la lecture d'un ancien cache.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

SEGMENTS_PAR_DEFAUT = {
    "definition": ["Definition", "Definition - Ongoing", "Definition - On Hold", "Ready for Review (Definition)",
                   "Analysis", "Analysis - ongoing", "Analysis - on hold", "Ready for Enhancement Check"],
    "pret": ["Ready for Implementation"],
    "implementation": ["Implementation", "Implementation - Ongoing", "Implementation - On Hold", "Analysis (Impl)",
                       "Code Review (Impl)", "R&D Test (Impl)"],
    "revue_verification": ["Ready for Review (Implementation)", "Review - Ongoing (Impl.)",
                           "Review - On Hold (Impl.)", "Ready for Verification", "Verification",
                           "Verification - Ongoing", "Verification - On Hold"],
    "acceptation": ["Ready for Acceptance", "Documentation (Impl)"],
}
# états connus de début et de fin du workflow : pas de temps calculé, mais jamais signalés comme oubliés
SEGMENTS_HORS_CALCUL_PAR_DEFAUT = {
    "a_faire": ["Open", "Draft"],
    "termine": ["Closed", "Resolved", "Accepted & Released", "Rejected"],
}


class CacheIllisible(Exception):
    """Le fichier du cache n'est pas lisible (le message est sûr à afficher)."""


def normaliser_date(valeur) -> str | None:
    """Date de transition au format ISO 8601 avec décalage. Un texte ISO est gardé tel quel ; des millisecondes depuis
    1970 (nombre ou texte de chiffres) deviennent une date UTC. Une valeur inconnue est rendue en texte, telle quelle."""
    if valeur is None or valeur == "":
        return None
    if isinstance(valeur, bool):
        return str(valeur)
    texte = str(valeur).strip()
    if isinstance(valeur, (int, float)) or (texte.isdigit() and len(texte) >= 10):
        try:
            ms = int(float(texte))
            if len(texte) <= 11:                      # des secondes, pas des millisecondes
                ms *= 1000
            moment = dt.datetime.fromtimestamp(ms // 1000, tz=dt.timezone.utc)
            return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}+0000"
        except (ValueError, OverflowError, OSError):
            return texte
    return texte


def instant(date: str | None) -> tuple:
    """Clé de tri chronologique. Les dates Jira portent un décalage horaire (+0200) : un tri sur le texte
    mélangerait deux décalages différents. Une date illisible passe après les autres, triée comme texte."""
    try:
        return (0, dt.datetime.fromisoformat(date).timestamp(), "")
    except (TypeError, ValueError):
        return (1, 0.0, str(date or ""))


def date_calendaire(date: str | None) -> dt.date | None:
    """Jour de la date de transition (jour du décalage d'origine : les 10 premiers caractères du texte ISO)."""
    try:
        return dt.date.fromisoformat(str(date)[:10])
    except ValueError:
        return None


def en_fuseau(date: str | None, fuseau: dt.tzinfo) -> str | None:
    """Date ISO avec décalage ramenée dans `fuseau` (même format que le cache : millisecondes et décalage +HHMM). Une date sans
    décalage ou illisible est gardée telle quelle, comme `normaliser_date` garde une valeur inconnue."""
    if date is None:
        return None
    try:
        moment = dt.datetime.fromisoformat(str(date))
    except ValueError:
        return date
    if moment.tzinfo is None:
        return date
    local = moment.astimezone(fuseau)
    return local.strftime("%Y-%m-%dT%H:%M:%S.") + f"{local.microsecond // 1000:03d}" + local.strftime("%z")


def trier(transitions: list) -> list[list]:
    """Transitions [date, de, vers] normalisées et triées par instant (tri stable)."""
    propres = [[normaliser_date(t[0]), t[1], t[2]] for t in transitions or []]
    return sorted(propres, key=lambda t: instant(t[0]))


def trier_evenements(evenements: list) -> list[list]:
    """Événements [date, "add"|"remove", valeur] normalisés et triés par instant (tri stable) ; un événement mal formé est écarté."""
    propres = [[normaliser_date(e[0]), e[1], e[2]] for e in evenements or []
               if isinstance(e, (list, tuple)) and len(e) == 3 and e[1] in ("add", "remove")]
    return sorted(propres, key=lambda e: instant(e[0]))


def lire_cache(chemin: Path) -> dict[str, dict]:
    """Cache lu et normalisé : dates ISO, transitions et événements triés ; les clés facultatives (resolu, vu_le, versions,
    etiquettes) sont toujours rendues (None ou liste vide quand elles manquent). Lève CacheIllisible si le fichier est absent
    ou invalide."""
    try:
        donnees = json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise CacheIllisible("cache de l'historique illisible.") from None
    if not isinstance(donnees, dict):
        raise CacheIllisible("cache de l'historique illisible.")
    sortie = {}
    for cle, entree in donnees.items():
        if isinstance(entree, dict):
            sortie[cle] = {"termine": bool(entree.get("termine")), "transitions": trier(entree.get("transitions")),
                           "resolu": normaliser_date(entree.get("resolu")), "vu_le": normaliser_date(entree.get("vu_le")),
                           "versions": trier_evenements(entree.get("versions")),
                           "etiquettes": trier_evenements(entree.get("etiquettes"))}
    return sortie


def table_segments(settings: dict) -> tuple[dict[str, str], list[str]]:
    """(état en minuscules -> segment, noms des segments calculés). Les segments hors calcul rangent leurs états sans
    que le segment soit calculé. `segments` et `segments_hors_calcul` de flux.yaml remplacent les valeurs par défaut."""
    calcules = settings.get("segments") or SEGMENTS_PAR_DEFAUT
    hors_calcul = settings.get("segments_hors_calcul")
    if hors_calcul is None:
        hors_calcul = SEGMENTS_HORS_CALCUL_PAR_DEFAUT
    segment_de = {etat.strip().casefold(): nom for nom, etats in {**hors_calcul, **calcules}.items()
                  for etat in (etats or [])}
    return segment_de, list(calcules)


def segments_traverses(transitions: list, segment_de: dict[str, str], calcules: list[str]) -> set[str]:
    """Segments calculés par lesquels un ticket est passé : état de départ de la première transition et états d'arrivée."""
    if not transitions:
        return set()
    etats = {transitions[0][1]} | {t[2] for t in transitions}
    return {segment_de.get((e or "").strip().casefold()) for e in etats} & set(calcules)


SEUIL_DORMANT_JOURS = 365


def dormants_selon_historique(tickets, cache: dict[str, list], aujourdhui: dt.date,
                              seuil: int = SEUIL_DORMANT_JOURS) -> tuple[set[str], int]:
    """Clés (en majuscules) des tickets dormants d'après l'historique : non terminé, créé il y a au moins `seuil` jours,
    aucun changement d'état depuis au moins `seuil` jours (date de la dernière transition, ou de la création s'il n'y
    en a aucune). `tickets` : (clé, date de création, terminé) ; `cache` : transitions par clé en majuscules.
    Un ticket absent du cache n'est pas dormant : on ne sait rien de lui (il est compté à part, second résultat)."""
    dormants, sans_historique = set(), 0
    for cle, cree, termine in tickets:
        if termine or not cle or cree is None:
            continue
        transitions = cache.get(cle.upper())
        if transitions is None:
            sans_historique += 1
            continue
        dernier = cree
        for transition in transitions:
            jour = date_calendaire(transition[0])
            if jour and jour > dernier:
                dernier = jour
        if (aujourdhui - cree).days >= seuil and (aujourdhui - dernier).days >= seuil:
            dormants.add(cle.upper())
    return dormants, sans_historique


# Format des dates des CSV de export_jira_api.py (09/Nov/2017 08:49) : fixe, un seul endroit pour tous les lecteurs.
FORMAT_DATE = "%d/%b/%Y %H:%M"


def ensembles_exclus(settings: dict, avec_projets: bool = True) -> tuple[set[str], set[str]]:
    """(types de niveau portefeuille en minuscules, projets exclus en majuscules) de flux.yaml ; « types_exclus » est
    l'ancien nom de `types_portefeuille`. Sans `avec_projets`, aucun projet (export sans colonne de clé)."""
    types = {t.strip().casefold() for t in (settings.get("types_portefeuille") or settings.get("types_exclus") or [])}
    projets = {p.strip().upper() for p in (settings.get("projets_exclus") or [])} if avec_projets else set()
    return types, projets


def parse_moment(valeur: str) -> dt.datetime | None:
    """Date et heure (à la minute) d'une cellule d'un CSV de l'API, None si elle est vide ou illisible."""
    try:
        return dt.datetime.strptime((valeur or "").strip(), FORMAT_DATE)
    except ValueError:
        return None


def parse_jour(valeur: str) -> dt.date | None:
    """Jour d'une cellule d'un CSV de l'API, None si elle est vide ou illisible."""
    moment = parse_moment(valeur)
    return moment.date() if moment else None
