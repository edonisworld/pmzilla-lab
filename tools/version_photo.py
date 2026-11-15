# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "psycopg[binary]"]
# ///
"""
PMZilla Lab : photo hebdomadaire de qualité par version (change version-quality-photo, R-140, branche 1).

    uv run tools/version_photo.py reconstruct [--replace] [--language fr|en]
    uv run tools/version_photo.py take [--replace] [--language fr|en]
    uv run tools/version_photo.py adopt-n --weeks N --adopted-on AAAA-MM-JJ [--reason TEXTE] [--language fr|en]

À lancer par l'utilisateur seul, dans le Terminal (refusé dans une session Claude Code : règles deny et variable CLAUDECODE, sans option de
contournement). Ce que l'outil écrit : des agrégats par semaine, équipe et version dans le schéma flow (migration 0019), jamais une clé, un
titre ou une personne ; ces tables restent hors de la règle de conservation d'un an.

  reconstruct   reconstruit, d'après les tickets encore en base, une ligne par semaine, équipe et version pour chaque semaine de la plus
                ancienne résolution à la dernière semaine terminée. La semaine ISO (lundi à dimanche, UTC) est lue à la fin de son vendredi.
                Une semaine qui commence avant la limite de conservation du jour est marquée « partial » (ses tickets peuvent être purgés).
                Une seconde reconstruction est refusée ; --replace réécrit les seules semaines reconstruites encore recalculables depuis les
                données présentes, jamais une photo vivante ; les semaines plus anciennes, que la purge a rendues non recalculables, gardent
                leurs lignes et l'avertissement les compte. Un résolu se lit dans l'historique des transitions (repli sur resolved_at).
  take          photographie la semaine en cours à l'instant du lancement (source « live »). Une seconde photo de la même semaine est
                refusée ; --replace remplace la photo vivante de la semaine en cours seulement.
  adopt-n       ajoute une adoption de N (semaines avant la sortie) au registre, en ajout seulement. Une adoption qui en suit une autre exige
                --reason, rangé avec l'adoption et jamais imprimé ni exposé par une vue.

Comptes (design D6) : défauts trouvés dans V (version d'affects courante), défauts corrigés dans V (version corrigée courante, lue telle que
connue à la semaine et telle que connue aujourd'hui), défauts rouverts, défauts sans version d'affects, débit en correction. Les défauts
trouvés et les défauts corrigés ne sont jamais additionnés. Limite écrite (D7) : la version d'affects n'a pas d'historique, la
reconstruction lit celle d'aujourd'hui pour chaque semaine passée.

Registre des versions (change version-release-date, D5 à D9) : à chaque `reconstruct` et `take`, dans la même transaction, la date de sortie et
le drapeau « sortie » des versions courantes stockées sont copiés dans le registre, un nom à la fois : même valeur sur toutes les lignes d'un
nom, sinon nulle (le nom compte comme divergent). Un nom que plus aucun ticket stocké ne porte garde ses dernières valeurs. Aucune date n'est
jamais estimée ni lue de l'historique. Deux lignes de compte suivent les lignes habituelles : versions du registre sans date de sortie, noms
aux attributs divergents (jamais un nom, un numéro, une date ni un drapeau).

Codes : 0 fait ; 1 erreur de base (nom du type seul) ; 2 usage ; 3 refus (session Claude Code, types de défaut non réglés, reconstruction ou
photo déjà faite, N déjà adopté sans --reason, réglages invalides, masquage des croisements équipes x versions pas encore en place), rien
n'est écrit. adopt-n refuse tant que flow.masking_version() (marqueur de la migration de R-144) est absente ou inférieure à la version attendue.

La sortie ne porte que des effectifs, des dates de semaine et les phrases clés : jamais une clé, une équipe, un nom de version ni une valeur
de réglage.

Emplacements (variables d'environnement, pour les tests et le réglage) : VERSION_PHOTO_SETTINGS (flux.yaml, défaut celui de Flux-Lab),
VERSION_PHOTO_NOW (instant du lancement, ISO 8601 avec décalage). Base : db.connect(role="pmzilla_flow"), le rôle d'import.

Exemple :
    uv run tools/version_photo.py reconstruct
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flux_config as cfg                                  # noqa: E402
import history_common as commun                            # noqa: E402
import lab_paths                                           # noqa: E402
import yaml                                                # noqa: E402
from messages import LANGUAGES, Messages                   # noqa: E402
from version_photo_messages import CATALOGS                # noqa: E402
from yaml_strict import ErreurConfig, charger              # noqa: E402

ROLE = "pmzilla_flow"
VARIABLE_CLAUDE_CODE = "CLAUDECODE"
SANS_EQUIPE = "(sans équipe)"
UTC = dt.timezone.utc

COMPTES_VERSION = ("found", "found_open", "corrected_at_week", "corrected_now", "reopened")
COMPTES_LIBRES = ("defects_created", "defects_without_affects", "resolved_week", "resolved_week_defects")


class Usage(Exception):
    pass


class Prerequis(Exception):
    """Prérequis refusé (code 3) : `cle` est la clé du libellé fixe, `valeurs` ses champs."""
    def __init__(self, cle: str, **valeurs):
        super().__init__(cle)
        self.cle, self.valeurs = cle, valeurs


class Analyseur(argparse.ArgumentParser):
    def error(self, message):                                   # le message d'argparse peut citer ce que l'utilisateur a tapé
        raise Usage()


# ---------------------------------------------------------------------------------------------------------------------------------
# Fonction pure d'une semaine (design D6, D7) : aucune base, aucune sortie
# ---------------------------------------------------------------------------------------------------------------------------------

@dataclass
class Ticket:
    """Un ticket tel que la fonction de semaine le lit. Aucune clé : elle ne sert qu'à relier les lignes à la lecture."""
    type: str
    equipe: str
    cree: dt.datetime
    resolu: dt.datetime | None = None
    hors_export: bool = False
    fix: frozenset = field(default_factory=frozenset)                 # versions corrigées courantes
    affects: frozenset = field(default_factory=frozenset)             # versions d'affects courantes
    periodes: tuple = ()                                              # (version, posée le, retirée le ou None) de la fix version
    transitions: tuple = ()                                           # (instant, statut de départ, statut d'arrivée)


@dataclass
class Regles:
    defauts: frozenset          # types de défaut, comparés sans casse ni espaces de bord
    portefeuille: frozenset     # types de niveau portefeuille (hors du débit), idem
    termine: frozenset          # états classés « terminé » par la table de segments partagée, idem
    periode_jours: int = 365    # durée de conservation du réglage retention


def _nom(texte) -> str:
    return (texte or "").strip().casefold()


def lundi_de(jour: dt.date) -> dt.date:
    return jour - dt.timedelta(days=jour.weekday())


def instant_de_la_semaine(lundi: dt.date) -> dt.datetime:
    """Instant d'état d'une semaine reconstruite : la fin de son vendredi, en UTC (design D2)."""
    return dt.datetime.combine(lundi + dt.timedelta(days=4), dt.time(23, 59, 59, 999999), tzinfo=UTC)


def est_defaut(ticket: Ticket, regles: Regles) -> bool:
    return _nom(ticket.type) in regles.defauts


def derniere_reouverture(ticket: Ticket, instant: dt.datetime, regles: Regles) -> dt.datetime | None:
    """Instant de la dernière transition de départ « terminé » et d'arrivée non « terminé » à l'instant ou avant (design D5) ; None sans
    réouverture. Une transition vers le même statut est ignorée, comme dans le contrôle de l'historique."""
    moments = [moment for moment, depart, arrivee in ticket.transitions
               if moment <= instant and not commun.meme_statut(depart, arrivee)
               and _nom(depart) in regles.termine and _nom(arrivee) not in regles.termine]
    return max(moments) if moments else None


def reouvert(ticket: Ticket, instant: dt.datetime, regles: Regles) -> bool:
    """Vrai si le ticket a été rouvert à l'instant ou avant (design D5), qu'il ait été résolu de nouveau depuis ou non."""
    return derniere_reouverture(ticket, instant, regles) is not None


def rouvert_en_cours(ticket: Ticket, resolu_a: dt.datetime | None, instant: dt.datetime, regles: Regles) -> bool:
    """Vrai si le ticket est ouvert à l'instant parce que sa dernière réouverture suit sa dernière résolution (décision 6 du 2026-10-23) ;
    résolu de nouveau depuis, il ne l'est plus."""
    rouverture = derniere_reouverture(ticket, instant, regles)
    return rouverture is not None and (resolu_a is None or rouverture > resolu_a)


def instant_de_resolution(ticket: Ticket, instant: dt.datetime, regles: Regles) -> dt.datetime | None:
    """Instant de résolution du ticket tel qu'il se lit à l'instant de la photo (décision A du 2026-10-23, design D7) : celui de la dernière
    transition vers un statut classé « terminé » survenue à l'instant ou avant ; None si le ticket n'était pas encore résolu. Repli sur
    resolved_at quand l'historique ne montre aucune transition vers « terminé » (historique absent, ou jamais collecté pour la période) ;
    un ticket dont l'historique montre une fermeture plus tardive n'est pas résolu avant elle."""
    fermetures = [moment for moment, depart, arrivee in ticket.transitions
                  if not commun.meme_statut(depart, arrivee) and _nom(arrivee) in regles.termine]
    if not fermetures:
        return ticket.resolu if ticket.resolu is not None and ticket.resolu <= instant else None
    jusque_la = [moment for moment in fermetures if moment <= instant]
    return max(jusque_la) if jusque_la else None


def corriges_a_la_semaine(ticket: Ticket, instant: dt.datetime) -> set:
    """Versions corrigées actives à l'instant d'après les périodes : posées à l'instant ou avant, retirées après ou jamais."""
    return {version for version, pose, retire in ticket.periodes if pose <= instant and (retire is None or retire > instant)}


def lignes_de_la_semaine(tickets, regles: Regles, lundi: dt.date, instant: dt.datetime, vivant: bool = False) -> list[dict]:
    """Lignes d'une semaine : une par équipe et version (cinq comptes, version nommée) et une par équipe sans version (quatre comptes,
    version None). Les tickets sortis de l'export sont écartés. `vivant` : photo prise maintenant, les périodes ne disent rien de plus que
    les versions courantes, « corrigé à la semaine » prend donc la même valeur que « corrigé maintenant ». Les défauts trouvés et les
    défauts corrigés ne sont jamais additionnés."""
    debut_semaine = dt.datetime.combine(lundi, dt.time(0), tzinfo=UTC)
    par_version: dict[tuple, dict] = {}
    libres: dict[str, dict] = {}

    def ligne_version(equipe, version):
        return par_version.setdefault((equipe, version), {c: 0 for c in COMPTES_VERSION})

    def ligne_libre(equipe):
        return libres.setdefault(equipe, {c: 0 for c in COMPTES_LIBRES})

    for ticket in tickets:
        if ticket.hors_export or ticket.cree > instant:
            continue
        resolu_a = instant_de_resolution(ticket, instant, regles)
        resolu_par = resolu_a is not None
        defaut = est_defaut(ticket, regles)
        if defaut:
            libre = ligne_libre(ticket.equipe)
            libre["defects_created"] += 1
            if not ticket.affects:
                libre["defects_without_affects"] += 1
            ouvert = not resolu_par or rouvert_en_cours(ticket, resolu_a, instant, regles)      # un rouvert est de nouveau ouvert (décision 6)
            for version in ticket.affects:
                ligne = ligne_version(ticket.equipe, version)
                ligne["found"] += 1
                if ouvert:
                    ligne["found_open"] += 1
            if resolu_par:
                a_la_semaine = set(ticket.fix) if vivant else corriges_a_la_semaine(ticket, instant)
                for version in a_la_semaine:
                    ligne_version(ticket.equipe, version)["corrected_at_week"] += 1
                rouvert = reouvert(ticket, instant, regles)
                for version in ticket.fix:
                    ligne = ligne_version(ticket.equipe, version)
                    ligne["corrected_now"] += 1
                    if rouvert:
                        ligne["reopened"] += 1
        if resolu_par and resolu_a >= debut_semaine and _nom(ticket.type) not in regles.portefeuille:
            libre = ligne_libre(ticket.equipe)
            libre["resolved_week"] += 1
            if defaut:
                libre["resolved_week_defects"] += 1
    lignes = []
    for (equipe, version), comptes in sorted(par_version.items()):
        lignes.append({"team": equipe, "version": version, **comptes, **{c: None for c in COMPTES_LIBRES}})
    for equipe, comptes in sorted(libres.items()):
        lignes.append({"team": equipe, "version": None, **{c: None for c in COMPTES_VERSION}, **comptes})
    return lignes


def attributs_de_sortie(lignes) -> tuple[dict, int]:
    """Date de sortie et drapeau de chaque nom de version d'après les lignes de versions courantes stockées (change version-release-date,
    design D5, D7). `lignes` : (nom, date de sortie ou None, drapeau ou None[, hors_export]), une par ticket et genre ; `hors_export` (faux
    par défaut) dit que le ticket est sorti de l'export : sa ligne ne compte plus (décision de l'auteur du 2026-10-23). Rend ({nom: (date,
    drapeau)}, nombre de noms divergents) : quand toutes les lignes comptées d'un nom portent la même date (nulle comprise), c'est cette
    date, sinon None ; de même pour le drapeau ; un nom dont la date ou le drapeau diffère entre tickets de l'export compte une fois comme
    divergent. Un nom que plus aucun ticket de l'export ne porte est absent du résultat : le registre garde ses dernières valeurs.
    Aucune estimation : une date nulle reste nulle. Pure : aucune base, aucune sortie."""
    dates: dict[str, set] = {}
    drapeaux: dict[str, set] = {}
    for nom, date_sortie, sortie, *reste in lignes:
        if reste and reste[0]:
            continue
        dates.setdefault(nom, set()).add(date_sortie)
        drapeaux.setdefault(nom, set()).add(sortie)
    attributs, divergents = {}, 0
    for nom in dates:
        date_commune = next(iter(dates[nom])) if len(dates[nom]) == 1 else None
        drapeau_commun = next(iter(drapeaux[nom])) if len(drapeaux[nom]) == 1 else None
        divergents += len(dates[nom]) > 1 or len(drapeaux[nom]) > 1
        attributs[nom] = (date_commune, drapeau_commun)
    return attributs, divergents


def remplir_registre(magasin) -> tuple[int, int]:
    """Copie, dans la transaction du lancement, les attributs de sortie des versions courantes stockées dans le registre (design D5) : une
    ligne par nom porté par au moins un ticket encore dans l'export, jamais pour un autre nom (il garde ses dernières valeurs). Rend (versions du
    registre sans date de sortie après le lancement, noms divergents)."""
    attributs, divergents = attributs_de_sortie(magasin.lire_sorties_stockees())
    magasin.ecrire_registre(attributs)
    return magasin.compter_versions_sans_date(), divergents


def sans_historique(tickets, regles: Regles) -> int:
    """Défauts qui portent une fix version courante sans aucune période : leur historique n'a jamais été collecté. Ils comptent dans
    « corrigé maintenant » seulement."""
    return sum(1 for t in tickets if not t.hors_export and est_defaut(t, regles) and t.fix and not t.periodes)


def premiere_fermeture(ticket: Ticket, regles: Regles) -> dt.datetime | None:
    """Instant de la première transition vers un statut classé « terminé » (même définition des fermetures que instant_de_resolution)."""
    moments = [moment for moment, depart, arrivee in ticket.transitions
               if not commun.meme_statut(depart, arrivee) and _nom(arrivee) in regles.termine]
    return min(moments) if moments else None


def semaines_a_reconstruire(tickets, aujourdhui: dt.date, regles: Regles) -> list[dt.date]:
    """Les lundis de la semaine de la plus ancienne résolution à la dernière semaine terminée (la semaine en cours n'y est jamais). La plus
    ancienne résolution est la plus tôt de la première fermeture des transitions et de resolved_at : un défaut refermé a un resolved_at tardif,
    et un historique peut parler seul."""
    resolutions = []
    for t in tickets:
        if t.hors_export:
            continue
        resolutions += [m for m in (t.resolu, premiere_fermeture(t, regles)) if m is not None]
    if not resolutions:
        return []
    premier = lundi_de(min(resolutions).astimezone(UTC).date())
    dernier = lundi_de(aujourdhui) - dt.timedelta(days=7)
    lundis, courant = [], premier
    while courant <= dernier:
        lundis.append(courant)
        courant += dt.timedelta(days=7)
    return lundis


def couverture(lundi: dt.date, aujourdhui: dt.date, regles: Regles) -> str:
    """« partial » quand la semaine commence avant la limite de conservation du jour de la reconstruction (design D7)."""
    return "partial" if lundi < aujourdhui - dt.timedelta(days=regles.periode_jours) else "complete"


# ---------------------------------------------------------------------------------------------------------------------------------
# Réglages
# ---------------------------------------------------------------------------------------------------------------------------------

def lire_reglages(chemin: Path) -> dict:
    """Réglages internes de flux.yaml. Lève Prerequis. Un fichier absent donne des réglages vides (donc aucun type de défaut)."""
    try:
        texte = chemin.read_text(encoding="utf-8")
    except FileNotFoundError:
        brut = None
    except (OSError, UnicodeDecodeError):
        raise Prerequis("settings_unreadable") from None
    else:
        try:
            brut = charger(texte, "flux.yaml")
        except ErreurConfig as erreur:
            raise Prerequis("settings_refused", what=erreur.message) from None
        except yaml.YAMLError:
            raise Prerequis("settings_unreadable") from None
    if brut is not None and not isinstance(brut, dict):
        raise Prerequis("settings_unreadable")
    try:
        interne = cfg.to_internal(brut or {}, "flux.yaml")
        cfg.retention_days(interne)
    except ErreurConfig as erreur:
        raise Prerequis("settings_refused", what=erreur.message) from None
    except SystemExit:                                          # ancien nom d'option : to_internal sort avec son message
        raise Prerequis("settings_unreadable") from None
    return interne


def regles_de(interne: dict) -> Regles:
    """Règles de la photo. Lève Prerequis("defect_types_missing") sans type de défaut : jamais un nom de type écrit en dur."""
    defauts = frozenset(_nom(t) for t in cfg.defect_types(interne))
    if not defauts:
        raise Prerequis("defect_types_missing")
    portefeuille, _ = commun.ensembles_exclus(interne, avec_projets=False)
    segment_de, _ = commun.table_segments(interne)
    termine = frozenset(etat for etat, segment in segment_de.items() if segment == "termine")
    return Regles(defauts=defauts, portefeuille=frozenset(portefeuille), termine=termine,
                  periode_jours=cfg.retention(interne)["period_days"])


# ---------------------------------------------------------------------------------------------------------------------------------
# Magasin (base) : l'interface que les tests remplacent par un magasin en mémoire
# ---------------------------------------------------------------------------------------------------------------------------------

SQL_TICKETS = ("SELECT i.key, i.type, coalesce(t.name, '(sans équipe)'), i.created_at, i.resolved_at, i.out_of_export_at IS NOT NULL "
               "FROM flow.issues i LEFT JOIN flow.teams t ON t.id = i.team_id")
# Versions et périodes des seuls défauts : les autres tickets ne servent qu'au débit en correction. Transitions de TOUS les types (décision 3 du
# 2026-10-23) : une seule définition des fermetures, celle de instant_de_resolution, pour les défauts comme pour le débit.
SQL_VERSIONS = ("SELECT v.issue_key, v.kind, v.name FROM flow.issue_current_versions v JOIN flow.issues i ON i.key = v.issue_key "
                "WHERE lower(btrim(i.type)) = ANY(%(types)s)")
SQL_PERIODES = ("SELECT p.issue_key, p.version, p.added_at, p.removed_at FROM flow.issue_version_periods p "
                "JOIN flow.issues i ON i.key = p.issue_key WHERE lower(btrim(i.type)) = ANY(%(types)s)")
SQL_TRANSITIONS = ("SELECT x.issue_key, x.transitioned_at, x.from_status, x.to_status FROM flow.transitions x "
                   "ORDER BY x.issue_key, x.transitioned_at, x.id")
SQL_SEMAINES = ("SELECT w.week_start, r.source FROM flow.version_photo_weeks w JOIN flow.version_photo_runs r ON r.id = w.run_id")
SQL_RECONSTRUCTION = "SELECT EXISTS (SELECT 1 FROM flow.version_photo_runs WHERE source = 'reconstructed')"
# --replace : seules les semaines reconstruites encore recalculables sont retirées (jamais une semaine vivante) ; un passage reconstruit qui ne
# garde aucune semaine est supprimé, celui qui en garde (non recalculables) reste avec son instant. Le recalcul s'écrit dans un NOUVEAU passage.
SQL_SUPPRIME_SEMAINES_RECONSTRUITES = ("DELETE FROM flow.version_photo_weeks w USING flow.version_photo_runs r "
                                       "WHERE r.id = w.run_id AND r.source = 'reconstructed' AND w.week_start = ANY(%s)")
SQL_SUPPRIME_PASSAGE_VIDE = ("DELETE FROM flow.version_photo_runs r WHERE r.source = 'reconstructed' "
                             "AND NOT EXISTS (SELECT 1 FROM flow.version_photo_weeks w WHERE w.run_id = r.id)")
SQL_SUPPRIME_VIVANTE = ("DELETE FROM flow.version_photo_runs WHERE source = 'live' AND id IN "
                        "(SELECT run_id FROM flow.version_photo_weeks WHERE week_start = %s)")
SQL_NOUVEAU_PASSAGE = "INSERT INTO flow.version_photo_runs (taken_at, source) VALUES (%s, %s) RETURNING id"
SQL_NOUVELLE_SEMAINE = "INSERT INTO flow.version_photo_weeks (week_start, run_id, coverage) VALUES (%s, %s, %s)"
SQL_NOUVELLE_LIGNE = ("INSERT INTO flow.version_photo_rows (week_start, team, version_no, found, found_open, corrected_at_week, "
                      "corrected_now, reopened, defects_created, defects_without_affects, resolved_week, resolved_week_defects) "
                      "VALUES (" + ", ".join(["%s"] * 12) + ")")
# Registre des attributs de sortie (change version-release-date, design D5) : les lignes de versions courantes de TOUS les tickets stockés, avec
# le drapeau « sorti de l'export » (la clé du ticket n'est jamais lue, seulement jointe ; la fonction pure écarte les tickets sortis), puis
# d'abord une mise à jour des noms connus, ensuite l'insertion des seuls noms absents : un nom nouveau reçoit son numéro opaque, un nom connu
# n'en consomme aucun (pas de trou dans version_no, ce que ferait INSERT ... ON CONFLICT DO UPDATE).
SQL_SORTIES_STOCKEES = ("SELECT v.name, v.release_date, v.released, i.out_of_export_at IS NOT NULL "
                        "FROM flow.issue_current_versions v JOIN flow.issues i ON i.key = v.issue_key")
SQL_REGISTRE_MISE_A_JOUR = "UPDATE flow.version_photo_versions SET release_date = %s, released = %s WHERE name = %s"
SQL_REGISTRE_INSERTION = ("INSERT INTO flow.version_photo_versions (name, release_date, released) SELECT %s, %s, %s "
                          "WHERE NOT EXISTS (SELECT 1 FROM flow.version_photo_versions WHERE name = %s)")
SQL_VERSIONS_SANS_DATE = "SELECT count(*) FROM flow.version_photo_versions WHERE release_date IS NULL"
SQL_NUMERO = "SELECT version_no FROM flow.version_photo_versions WHERE name = %s"
SQL_NOUVELLE_VERSION = "INSERT INTO flow.version_photo_versions (name) VALUES (%s) RETURNING version_no"
# Garde d'adopt-n (change masking-sums, D9) : le marqueur flow.masking_version() de la migration de R-144 (masquage des croisements équipes x
# versions). Les versions du marqueur sont croissantes : adoption acceptée à partir de la version attendue, refusée en dessous ou sans marqueur.
VERSION_MASQUAGE_ATTENDUE = 3    # R-20261104-45 (1) : adopt-n attend 3 dès le groupe 6 ; la migration 0035 pose 2 (D15), la 3 viendra des groupes 7 et 8 : N reste bloqué jusque-là (échec fermé)
SQL_VERSION_MASQUAGE = "SELECT flow.masking_version()"
SQL_COMPTE_ADOPTIONS = "SELECT count(*) FROM flow.version_photo_n"
SQL_ADOPTION = "INSERT INTO flow.version_photo_n (weeks, adopted_on, reason) VALUES (%s, %s, %s)"


class MagasinBase:
    """Le magasin sous le rôle d'import. Une seule transaction par lancement : `valider` la termine, la fermeture sans validation l'annule."""

    def __init__(self, conn):
        self.conn = conn

    def lire_tickets(self, types_defaut) -> list[Ticket]:
        types = sorted(types_defaut)
        parametres = {"types": types}
        brut: dict[str, Ticket] = {}
        for cle, type_, equipe, cree, resolu, hors_export in self.conn.execute(SQL_TICKETS):
            brut[cle] = Ticket(type=type_ or "", equipe=equipe, cree=cree, resolu=resolu, hors_export=bool(hors_export))
        fix: dict[str, set] = {}
        affects: dict[str, set] = {}
        for cle, genre, nom in self.conn.execute(SQL_VERSIONS, parametres):
            (fix if genre == "fix" else affects).setdefault(cle, set()).add(nom)
        periodes: dict[str, list] = {}
        for cle, version, pose, retire in self.conn.execute(SQL_PERIODES, parametres):
            periodes.setdefault(cle, []).append((version, pose, retire))
        transitions: dict[str, list] = {}
        for cle, moment, depart, arrivee in self.conn.execute(SQL_TRANSITIONS):
            transitions.setdefault(cle, []).append((moment, depart, arrivee))
        for cle, ticket in brut.items():
            ticket.fix = frozenset(fix.get(cle, ()))
            ticket.affects = frozenset(affects.get(cle, ()))
            ticket.periodes = tuple(periodes.get(cle, ()))
            ticket.transitions = tuple(transitions.get(cle, ()))
        return list(brut.values())

    def semaines(self) -> dict[dt.date, str]:
        return {semaine: source for semaine, source in self.conn.execute(SQL_SEMAINES)}

    def reconstruction_existe(self) -> bool:
        return bool(self.conn.execute(SQL_RECONSTRUCTION).fetchone()[0])

    def supprimer_semaines_reconstruites(self, lundis) -> None:
        self.conn.execute(SQL_SUPPRIME_SEMAINES_RECONSTRUITES, (list(lundis),))
        self.conn.execute(SQL_SUPPRIME_PASSAGE_VIDE)

    def supprimer_photo_vivante(self, lundi: dt.date) -> None:
        self.conn.execute(SQL_SUPPRIME_VIVANTE, (lundi,))

    def _numero(self, nom: str, connus: dict) -> int:
        if nom not in connus:
            ligne = self.conn.execute(SQL_NUMERO, (nom,)).fetchone()
            connus[nom] = ligne[0] if ligne else self.conn.execute(SQL_NOUVELLE_VERSION, (nom,)).fetchone()[0]
        return connus[nom]

    def ecrire_passage(self, source: str, instant: dt.datetime, semaines) -> int:
        """Écrit un passage et ses semaines ; `semaines` : [(lundi, couverture, lignes)]. Rend le nombre de lignes écrites."""
        passage = self.conn.execute(SQL_NOUVEAU_PASSAGE, (instant, source)).fetchone()[0]       # toujours un nouveau passage (décision 2 du 2026-10-23)
        connus: dict[str, int] = {}
        total = 0
        for lundi, couv, lignes in semaines:
            self.conn.execute(SQL_NOUVELLE_SEMAINE, (lundi, passage, couv))
            for ligne in lignes:
                numero = None if ligne["version"] is None else self._numero(ligne["version"], connus)
                self.conn.execute(SQL_NOUVELLE_LIGNE, (lundi, ligne["team"], numero, *(ligne[c] for c in COMPTES_VERSION + COMPTES_LIBRES)))
                total += 1
        return total

    def lire_sorties_stockees(self) -> list[tuple]:
        """(nom, date de sortie, drapeau, ticket sorti de l'export) de chaque ligne de versions courantes stockée."""
        return [tuple(ligne) for ligne in self.conn.execute(SQL_SORTIES_STOCKEES)]

    def ecrire_registre(self, attributs: dict) -> None:
        """Écrit date et drapeau de chaque nom dans le registre, dans la transaction ouverte (aucune validation ici) : mise à jour des noms
        connus, puis insertion des seuls nouveaux noms, dans l'ordre des noms (déterministe, sans numéro sauté)."""
        noms = sorted(attributs)
        for nom in noms:
            self.conn.execute(SQL_REGISTRE_MISE_A_JOUR, (*attributs[nom], nom))
        for nom in noms:
            self.conn.execute(SQL_REGISTRE_INSERTION, (nom, *attributs[nom], nom))

    def compter_versions_sans_date(self) -> int:
        return int(self.conn.execute(SQL_VERSIONS_SANS_DATE).fetchone()[0])

    def version_masquage(self) -> int | None:
        """Version du marqueur de masquage, ou None quand la fonction est absente (l'erreur de fonction indéfinie vaut refus, jamais code 1)."""
        from psycopg import errors
        try:
            ligne = self.conn.execute(SQL_VERSION_MASQUAGE).fetchone()
        except errors.UndefinedFunction:
            self.conn.rollback()                                # la transaction est avortée ; rien n'était écrit
            return None
        return None if ligne is None or ligne[0] is None else int(ligne[0])

    def nombre_adoptions(self) -> int:
        return int(self.conn.execute(SQL_COMPTE_ADOPTIONS).fetchone()[0])

    def ajouter_adoption(self, semaines: int, jour: dt.date, raison: str | None) -> None:
        self.conn.execute(SQL_ADOPTION, (semaines, jour, raison))

    def valider(self) -> None:
        self.conn.commit()

    def fermer(self) -> None:
        try:
            self.conn.rollback()
        finally:
            self.conn.close()


def ouvrir_magasin_base() -> MagasinBase:
    import db
    return MagasinBase(db.connect(role=ROLE))


# ---------------------------------------------------------------------------------------------------------------------------------
# Sous-commandes
# ---------------------------------------------------------------------------------------------------------------------------------

def reconstruire(args, magasin, regles: Regles, maintenant: dt.datetime, t: Messages) -> int:
    if not args.replace and magasin.reconstruction_existe():
        raise Prerequis("reconstruction_exists")
    tickets = magasin.lire_tickets(regles.defauts)
    aujourdhui = maintenant.astimezone(UTC).date()
    recalculables = semaines_a_reconstruire(tickets, aujourdhui, regles)
    if args.replace:
        # décision B du 2026-10-23 : seules les semaines encore recalculables depuis les données présentes sont remplacées ; les plus anciennes
        # (tickets purgés) gardent leurs lignes telles quelles, et l'avertissement les compte
        gardees = sum(1 for lundi, source in magasin.semaines().items() if source == "reconstructed" and lundi not in set(recalculables))
        print(t("reconstruct_warning"))
        print(t("reconstruct_kept", n=gardees))
        magasin.supprimer_semaines_reconstruites(recalculables)
    deja = magasin.semaines()                                   # après la suppression : photos vivantes et semaines gardées
    semaines, versions, partielles = [], set(), 0
    for lundi in recalculables:
        if lundi in deja:                                       # jamais une semaine déjà photographiée (en direct, ou gardée)
            continue
        lignes = lignes_de_la_semaine(tickets, regles, lundi, instant_de_la_semaine(lundi))
        couv = couverture(lundi, aujourdhui, regles)
        partielles += couv == "partial"
        versions.update(l["version"] for l in lignes if l["version"] is not None)
        semaines.append((lundi, couv, lignes))
    if semaines:
        magasin.ecrire_passage("reconstructed", maintenant, semaines)
    sans_date, divergents = remplir_registre(magasin)
    magasin.valider()
    print(t("reconstruct_done", weeks=len(semaines), versions=len(versions), partial=partielles))
    print(t("no_history", n=sans_historique(tickets, regles)))
    print(t("versions_no_release_date", n=sans_date))
    print(t("versions_conflicting_release", n=divergents))
    return 0


def photographier(args, magasin, regles: Regles, maintenant: dt.datetime, t: Messages) -> int:
    lundi = lundi_de(maintenant.astimezone(UTC).date())
    existantes = magasin.semaines()
    if lundi in existantes:
        if not args.replace or existantes[lundi] != "live":      # jamais une semaine reconstruite, jamais une semaine passée
            raise Prerequis("photo_exists")
        magasin.supprimer_photo_vivante(lundi)
    tickets = magasin.lire_tickets(regles.defauts)
    lignes = lignes_de_la_semaine(tickets, regles, lundi, maintenant.astimezone(UTC), vivant=True)
    magasin.ecrire_passage("live", maintenant, [(lundi, "complete", lignes)])
    sans_date, divergents = remplir_registre(magasin)
    magasin.valider()
    print(t("photo_taken", date=lundi.isoformat(), rows=len(lignes)))
    print(t("no_history", n=sans_historique(tickets, regles)))
    print(t("versions_no_release_date", n=sans_date))
    print(t("versions_conflicting_release", n=divergents))
    return 0


def adopter(args, magasin, t: Messages) -> int:
    version = magasin.version_masquage()
    if version is None:  # R-144 : pas de marqueur, croisements équipes x versions pas encore masqués, rien n'est écrit
        raise Prerequis("crossing_masking_missing")
    if version < VERSION_MASQUAGE_ATTENDUE:  # décision du 2026-10-28 : version installée trop basse (la 0022 pose 1, D15 pose 2), rien n'est écrit
        raise Prerequis("crossing_masking_version", installed=version, expected=VERSION_MASQUAGE_ATTENDUE)
    raison = (args.reason or "").strip() or None
    if magasin.nombre_adoptions() > 0:
        if raison is None:
            raise Prerequis("n_exists")
        print(t("n_warning"))
    magasin.ajouter_adoption(args.weeks, args.adopted_on, raison)
    magasin.valider()
    print(t("n_adopted", n=args.weeks, date=args.adopted_on.isoformat()))
    return 0


# ---------------------------------------------------------------------------------------------------------------------------------
# Programme
# ---------------------------------------------------------------------------------------------------------------------------------

def _entier_positif(texte: str) -> int:
    try:
        valeur = int(texte)
    except ValueError:
        raise Usage() from None
    if valeur <= 0:
        raise Usage()
    return valeur


def _date(texte: str) -> dt.date:
    try:
        return dt.date.fromisoformat(texte)
    except ValueError:
        raise Usage() from None


def lire_arguments(argv: list[str]):
    analyseur = Analyseur(prog="version_photo.py")               # --help : usage et code 0, sans rien lire
    analyseur.add_argument("--language", default="fr")
    sous = analyseur.add_subparsers(dest="commande", required=True, parser_class=Analyseur)
    for nom in ("reconstruct", "take"):
        commande = sous.add_parser(nom, add_help=False)
        commande.add_argument("--language", default=argparse.SUPPRESS)
        commande.add_argument("--replace", action="store_true")
    adoption = sous.add_parser("adopt-n", add_help=False)
    adoption.add_argument("--language", default=argparse.SUPPRESS)
    adoption.add_argument("--weeks", type=_entier_positif, required=True)
    adoption.add_argument("--adopted-on", dest="adopted_on", type=_date, required=True)
    adoption.add_argument("--reason", default=None)
    return analyseur.parse_args(argv)


def lire_horloge(environ) -> dt.datetime:
    texte = environ.get("VERSION_PHOTO_NOW")
    if not texte:
        return dt.datetime.now(UTC)
    moment = dt.datetime.fromisoformat(texte)
    if moment.tzinfo is None:
        raise ValueError(texte)
    return moment


def emplacement_reglages(environ) -> Path:
    if environ.get("VERSION_PHOTO_SETTINGS"):
        return Path(environ["VERSION_PHOTO_SETTINGS"]).expanduser()
    return lab_paths.resolve_or_exit(environ)["content_root"] / "Flux-Lab" / "flux.yaml"


def main(argv: list[str] | None = None, environ=None, ouvrir_magasin=None) -> int:
    """Rend le code de sortie. `environ` et `ouvrir_magasin` sont remplaçables pour les tests."""
    environ = os.environ if environ is None else environ
    ouvrir_magasin = ouvrir_magasin or ouvrir_magasin_base
    t = Messages(CATALOGS, "fr")
    try:
        args = lire_arguments(sys.argv[1:] if argv is None else argv)
    except Usage:
        print(t("usage"), file=sys.stderr)
        return 2
    if args.language not in LANGUAGES:
        print(t("language"), file=sys.stderr)
        return 2
    t = Messages(CATALOGS, args.language)
    if VARIABLE_CLAUDE_CODE in environ:                         # avant toute lecture : ni réglage, ni dossier, ni base
        print(t("session"))
        return 3
    try:
        maintenant = lire_horloge(environ)
    except ValueError:
        print(t("usage"), file=sys.stderr)
        return 2
    magasin = None
    try:
        regles = None
        if args.commande != "adopt-n":                          # les types de défaut avant toute connexion, avant toute écriture
            regles = regles_de(lire_reglages(emplacement_reglages(environ)))
        magasin = ouvrir_magasin()
        if args.commande == "reconstruct":
            return reconstruire(args, magasin, regles, maintenant, t)
        if args.commande == "take":
            return photographier(args, magasin, regles, maintenant, t)
        return adopter(args, magasin, t)
    except Prerequis as refus:
        print(t(refus.cle, **refus.valeurs))
        return 3
    except Exception as erreur:                                 # aucun détail : un message pourrait citer une clé, une équipe ou une version
        print(t("error", name=type(erreur).__name__), file=sys.stderr)
        return 1
    finally:
        if magasin is not None:
            try:
                magasin.fermer()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
