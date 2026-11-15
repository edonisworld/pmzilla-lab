"""
PMZilla Lab : règles communes de l'historique des états et des segments.

Utilisé par history_jira.py, history_store.py et flux_jira.py (compute --history) : une seule table range les états dans les segments,
une seule règle donne le fuseau d'export, pour que les outils ne puissent pas diverger. Aucune dépendance hors bibliothèque standard.
Le cache de fichier de l'historique n'existe plus (change database-only, D5) : l'historique vit dans la base.

Les dates des transitions sont des textes ISO 8601 avec décalage (2026-03-01T09:00:00.000+0200). L'API groupée de Jira peut les
donner sous une autre forme (millisecondes depuis 1970, en nombre ou en texte) : normaliser_date les ramène au format ISO (en UTC
dans ce cas) à la collecte.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FUSEAU_PAR_DEFAUT = "Europe/Paris"
REGLAGE_FUSEAU = "export_timezone"          # nom public du réglage (clé interne : export_fuseau)

# États neutres génériques (R-20261112-17) : les états réels du workflow de l'organisation viennent de `segments` et de
# `segments_hors_calcul` de flux.yaml, qui remplacent ces défauts (table_segments). Aucun nom réel dans l'arbre public.
SEGMENTS_PAR_DEFAUT = {
    "definition": ["Specification", "Specification - Active", "Specification - Blocked", "Awaiting Review (Specification)",
                   "Investigation", "Investigation - active", "Investigation - blocked", "Awaiting Sizing Check"],
    "pret": ["Awaiting Development"],
    "implementation": ["Development", "Development - Active", "Development - Blocked", "Investigation (Dev)",
                       "Peer Review (Dev)", "Lab Test (Dev)"],
    "revue_verification": ["Awaiting Review (Development)", "Review - Active (Dev.)",
                           "Review - Blocked (Dev.)", "Awaiting Testing", "Testing",
                           "Testing - Active", "Testing - Blocked"],
    "acceptation": ["Awaiting Acceptance", "Handover Notes (Dev)"],
}
# états connus de début et de fin du workflow : pas de temps calculé, mais jamais signalés comme oubliés
SEGMENTS_HORS_CALCUL_PAR_DEFAUT = {
    "a_faire": ["Open", "Draft"],
    "termine": ["Closed", "Resolved", "Shipped", "Rejected"],
}

# Point d'engagement du lead time de livraison (nom interne du segment) : défaut unique du rapport de flux et du chargeur des
# définitions de flux (change flow-definitions-loader, conception D2). Permanent tant qu'un rapport a un défaut de code.
POINT_ENGAGEMENT_PAR_DEFAUT = "pret"


def point_engagement(settings: dict) -> str:
    """Point d'engagement des réglages (clé interne `point_engagement`), ou le défaut commun ; lecteur partagé."""
    return settings.get("point_engagement") or POINT_ENGAGEMENT_PAR_DEFAUT


class ErreurFuseau(ValueError):
    """Fuseau d'export inconnu (idée #169, D9). Neutre : elle ne porte que le nom public du réglage (`reglage`) et le nom de
    fuseau lu dans les réglages (`nom`) ; chaque outil la traduit dans son message et son code de sortie."""

    def __init__(self, nom: str):
        super().__init__(REGLAGE_FUSEAU)
        self.reglage, self.nom = REGLAGE_FUSEAU, nom


def fuseau_export(settings: dict) -> ZoneInfo:
    """Fuseau des dates de l'export (réglage export_timezone, clé interne export_fuseau ; Europe/Paris par défaut), l'été et
    l'hiver compris. Règle unique de l'export, du lecteur de l'import, des lecteurs de la base et du rapport de flux. N'affiche
    rien ; un fuseau inconnu lève ErreurFuseau."""
    nom = str(settings.get("export_fuseau") or FUSEAU_PAR_DEFAUT).strip()
    try:
        return ZoneInfo(nom)
    except (ZoneInfoNotFoundError, ValueError):
        raise ErreurFuseau(nom) from None


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


def meme_statut(depart, arrivee) -> bool:
    """Vrai quand le statut de départ et le statut d'arrivée ont le même nom (espaces et casse ignorés) ; un statut vide n'est jamais
    compté. Une telle transition n'est ni un passage ni un changement d'état (idée 492) : les comptes de transitions et de passages
    l'écartent (les segments et les temps par segment n'en dépendent pas)."""
    nom = (depart or "").strip()
    return bool(nom) and nom.casefold() == (arrivee or "").strip().casefold()


def sans_meme_statut(transitions: list) -> list:
    """Les transitions [date, de, vers, ...] dont le départ et l'arrivée n'ont pas le même nom (voir `meme_statut`)."""
    return [t for t in transitions if not meme_statut(t[1], t[2])]


def trier_evenements(evenements: list) -> list[list]:
    """Événements [date, "add"|"remove", valeur] normalisés et triés par instant (tri stable) ; un événement mal formé est écarté."""
    propres = [[normaliser_date(e[0]), e[1], e[2]] for e in evenements or []
               if isinstance(e, (list, tuple)) and len(e) == 3 and e[1] in ("add", "remove")]
    return sorted(propres, key=lambda e: instant(e[0]))


def instant_de_transition(valeur, zone) -> dt.datetime | None:
    """Instant d'une date de transition ou d'événement (texte ISO) ; une date sans décalage est lue dans `zone`. Illisible : None."""
    try:
        moment = dt.datetime.fromisoformat(str(valeur))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=zone)


def construire_periodes(evenements: list, presentes: list[str] | None, cree: dt.datetime, zone,
                        admises: set[str] | None = None) -> list[tuple[str, dt.datetime, dt.datetime | None]]:
    """Périodes (valeur, posée le, retirée le ou None) d'un ticket, pour les étiquettes déclarées ou pour les versions.
    `evenements` : [date ISO, "add"|"remove", valeur] de la collecte, déjà triés ; `presentes` : valeurs courantes lues dans Jira
    (None : non suivies) ; `cree` : création du ticket ; `admises` : valeurs autorisées (les étiquettes déclarées ; None pour les
    versions). Règles :
      - un « add » ouvre une période (un second « add » sans retrait entre les deux est ignoré), un « remove » la ferme ;
      - un « remove » sans période ouverte ferme une période ouverte à la création du ticket (la valeur était posée avant le début) ;
      - une valeur présente dans Jira, sans aucun événement, ouvre une période à la création ;
      - la date de retrait n'est jamais antérieure à celle de pose ; un événement à date illisible est écarté ;
      - une valeur hors de `admises` n'apparaît jamais.
    Pure : aucun accès à la base."""
    ouvertes: dict[str, dt.datetime] = {}
    periodes: list[tuple[str, dt.datetime, dt.datetime | None]] = []
    vues: set[str] = set()
    for evenement in evenements or []:
        date, sens, valeur = evenement
        moment = instant_de_transition(date, zone)
        if moment is None or (admises is not None and valeur not in admises):
            continue
        vues.add(valeur)
        if sens == "add":
            ouvertes.setdefault(valeur, moment)
        elif valeur in ouvertes:
            debut = ouvertes.pop(valeur)
            periodes.append((valeur, debut, max(moment, debut)))
        else:
            periodes.append((valeur, cree, max(moment, cree)))
    for valeur in presentes or []:
        if valeur not in vues and (admises is None or valeur in admises):
            ouvertes[valeur] = cree
    periodes.extend((valeur, debut, None) for valeur, debut in ouvertes.items())
    return sorted(periodes, key=lambda p: (p[1], p[0]))


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


def ensembles_exclus(settings: dict, avec_projets: bool = True) -> tuple[set[str], set[str]]:
    """(types de niveau portefeuille en minuscules, projets exclus en majuscules) de flux.yaml ; « types_exclus » est
    l'ancien nom de `types_portefeuille`. Sans `avec_projets`, aucun projet (export sans colonne de clé)."""
    types = {t.strip().casefold() for t in (settings.get("types_portefeuille") or settings.get("types_exclus") or [])}
    projets = {p.strip().upper() for p in (settings.get("projets_exclus") or [])} if avec_projets else set()
    return types, projets
