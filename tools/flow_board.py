# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
PMZilla Lab : tableau de bord visuel des flux, pour les Agile Leads.

Un seul fichier HTML autonome, lisible hors ligne : la bibliothèque de graphiques (Apache ECharts, tools/vendor/), le CSS,
le JavaScript et les données sont dans le fichier. Aucun appel réseau, aucun CDN. Il est écrit dans Flux-Lab/tableaux/
(hors Git), à partir des JSON de Flux-Lab/rapports/ (flux-<série>-AAAA-MM-JJ.json, dependances-<nom>-AAAA-MM-JJ.json)
et, pour l'Aging WIP, de Flux-Lab/tableaux/points-<série>-AAAA-MM-JJ.json (flux_jira.py compute --points).

    uv run tools/flow_board.py [--language en|fr] [--anonymous] [--output CHEMIN] [--open]

La page est en anglais par défaut (--language en), car elle est lue par des Agile Leads anglophones ; les rapports Markdown
et les lectures de PMZilla restent en français. Tout le texte visible est traduit (titres, axes, légendes, infobulles,
boutons, notes, « How to read »). Les noms d'états Jira restent tels quels. Dates AAAA-MM-JJ ; en anglais, point décimal
et « d » pour les jours ; en français, virgule décimale et « j ».

--anonymous remplace les noms d'équipes, de projets et de séries par « Team A », « Project B », « Series 1 »... avant
d'écrire quoi que ce soit dans le fichier (voir Flux-Lab/tableaux/anonymes.yaml, la table de correspondance : des lettres
tirées au hasard une fois, puis stables d'un mois à l'autre ; un nom nouveau reçoit la lettre libre suivante).

Réglages (Flux-Lab/flux.yaml, facultatif) : une clé « boards » avec « series », une liste de séries,
chacune avec « name » (le --name de flux_jira.py compute), et facultativement « dependencies » (le --name de
dependencies_jira.py compute, par équipe), « project_dependencies » (par projet) et « baseline » (AAAA-MM-JJ : rapport de référence
d'un suivi de pilote). Sans ce réglage, toutes les séries trouvées dans Flux-Lab/rapports/ sont affichées.

Aucune clé de ticket, aucun titre, aucune personne : seuls des agrégats et, pour l'Aging WIP, un point par ticket en cours
sans identifiant. Les équipes sont toujours en ordre alphabétique, jamais classées. Une section en échec n'empêche pas
la page de s'écrire.

Variables d'environnement (pour les tests) : PMZILLA_LAB_WORKSPACE, PMZILLA_LAB_TODAY (AAAA-MM-JJ),
PMZILLA_LAB_ECHARTS (fichier de la bibliothèque, au lieu de tools/vendor/echarts.min.js), PMZILLA_LAB_SEED (graine).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import random
import re
import sys
import webbrowser
from pathlib import Path

import yaml

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import flux_config                              # noqa: E402
from yaml_strict import charger                # noqa: E402
import flow_glossary as glossaire          # noqa: E402

WORKSPACE = Path(os.environ.get("PMZILLA_LAB_WORKSPACE", "~/PMZilla-Lab/workspace")).expanduser()
FLUX_DIR = WORKSPACE / "Flux-Lab"
RAPPORTS = FLUX_DIR / "rapports"
TABLEAUX = FLUX_DIR / "tableaux"
CONFIG = FLUX_DIR / "flux.yaml"
ANONYMES = TABLEAUX / "anonymes.yaml"
LIB_PAR_DEFAUT = ICI / "vendor" / "echarts.min.js"
MAX_RAPPORTS = 12               # rapports gardés par série pour les évolutions d'un mois à l'autre
DATE = r"(\d{4}-\d{2}-\d{2})"
SPECIAUX = ("(sans équipe)", "(hors export)")
NATURES = {"actif": "active", "attente": "waiting", "dormant": "dormant"}      # nature d'un ticket en cours, dans le JSON

MESSAGE_LIB = ("Bibliothèque de graphiques introuvable : {chemin}. Télécharge-la une fois (aucun appel réseau ensuite) : "
               "zsh tools/vendor/telecharger_echarts.sh")


class Arret(Exception):
    pass


def aujourdhui() -> dt.date:
    brut = os.environ.get("PMZILLA_LAB_TODAY")
    return dt.date.fromisoformat(brut) if brut else dt.date.today()


# ---------------------------------------------------------------------------
# Textes : tout le texte visible, en anglais et en français
# ---------------------------------------------------------------------------

TEXTES = {
    "en": {
        "title": "Flow dashboard", "generated": "Generated", "series": "Series", "team": "Team",
        "all_teams": "All teams (product view)", "scope": "Scope", "all_projects": "all projects of the export",
        "latest_report": "Latest report", "period": "Period", "weeks": "weeks", "baseline": "Baseline",
        "how_to_read": "How to read", "no_data": "No data for this view yet.", "nd": "n/a",
        "unit_day": "d", "days": "Days", "unit_items": "items", "per_week": "items per week", "items": "items", "week_of": "Week of",
        "no_team": "(no team)", "outside_export": "(outside export)", "no_team_project": "(no team: {p})",
        "teams_note": "Teams are listed alphabetically. The dashboard never ranks teams.",
        "print": "Print", "language": "Language", "anonymous": "Anonymous version",
        "sec_flow": "Arrivals and departures per week", "sec_cfd": "Cumulative flow diagram",
        "sec_segments": "Time in segment", "sec_aging": "Aging WIP", "sec_wip": "WIP breakdown",
        "sec_efficiency": "Flow efficiency and delivery lead time", "sec_deps": "Dependency map",
        "sec_base": "Change since the baseline",
        "arrivals": "Arrivals (tickets created)", "departures": "Departures (items delivered)",
        "arrivals_missing": "Arrivals per week are not in this report: only departures are shown.",
        "cfd_delivered": "Delivered (cumulative)", "cfd_backlog": "Not yet committed",
        "cfd_coverage": "{n} tickets with history; {m} without history are not shown.",
        "cfd_missing": "The cumulative flow diagram needs the status history (flux_jira.py compute --history).",
        "left_segment": "Left the segment", "p50": "P50", "p70": "P70", "p85": "P85", "p95": "P95",
        "tickets_n": "n = {n}", "seg_missing": "Time in segment needs the status history (--history).",
        "aging_by_status": "By status", "aging_by_segment": "By segment", "age_days": "Age (days)",
        "nature_active": "Active", "nature_waiting": "Waiting", "nature_dormant": "Dormant",
        "no_history": "(no history)", "in_segment_age": "Age in segment", "status": "Status", "segment": "Segment",
        "aging_p85": "Lead time P85", "aging_missing": "No ticket-level points. Run flux_jira.py compute --points.",
        "aging_note": "One point per ticket in progress. No ticket key is shown.",
        "wip_now": "WIP now", "wip_history": "WIP breakdown by report", "wip_total": "WIP",
        "wip_only_total": "The report has only the WIP total (no waiting statuses or dormant data).",
        "wip_hist_note": "Reports without the breakdown show the total only.",
        "dormant_unknown": "no breakdown",
        "lt_from_commitment": "Delivery lead time (from commitment point)", "lt_from_creation": "Lead time (from creation)",
        "flow_eff_aggregate": "Flow efficiency (aggregate)", "flow_eff_median": "Flow efficiency (median ticket)",
        "coverage": "Coverage", "coverage_low": "Coverage is below 90%: the figures describe only part of the tickets.",
        "eff_missing": "Delivery lead time and flow efficiency need the status history (--history).",
        "commitment_note": "Commitment point: entry into the segment {s}.", "delivered_n": "{n} delivered tickets",
        "graph_missing": "No dependency report for this series.", "graph_from": "Waits for", "graph_team": "Team",
        "graph_open": "Open", "graph_unknown": "Unknown state", "graph_all": "All", "graph_epics": "Between Epics",
        "graph_table": "Dependencies as a table", "graph_loops": "Loops between teams", "graph_none": "none",
        "graph_by_team": "By team", "graph_by_project": "By project", "graph_tickets": "tickets",
        "graph_truncated": "The export may be truncated (round ticket count): do not read this map.",
        "graph_unoriented": "Links have no type: the map counts links, not blockages.",
        "graph_date": "Dependency report of", "graph_age": "Age of blocked items (P50 / P85)",
        "base_missing": "No baseline report found.", "base_metric": "Metric", "base_value": "Baseline",
        "base_now": "Latest", "base_change": "Change", "base_higher": "higher", "base_lower": "lower",
        "base_same": "unchanged", "m_departures": "Departures per week (average)", "m_arrivals": "Arrivals per week (average)",
        "m_lead85": "Lead time P85", "m_wip": "WIP", "m_wip_active": "Active WIP", "m_wip_waiting": "Waiting WIP",
        "m_wip_dormant": "Dormant WIP", "m_delivery85": "Delivery lead time P85",
        "m_efficiency": "Flow efficiency (aggregate)",
        "base_not_comparable": "The baseline and the latest report were computed with different options ({d}): compare with care.",
        "base_diff_scope": "scope", "base_diff_history": "status history", "base_diff_dormant": "dormant source",
        "base_since": "Since {d}", "history_n": "Reports since the baseline",
        "seg_definition": "Definition", "seg_pret": "Ready", "seg_implementation": "Implementation",
        "seg_revue_verification": "Review and verification", "seg_acceptation": "Acceptance",
        "series_label": "Series {n}", "team_label": "Team {l}", "project_label": "Project {l}",
        "error_section": "This section could not be built.", "empty_page": "No flow report found in Flux-Lab/rapports/.",
        "decimal": ".",
    },
    "fr": {
        "title": "Tableau de bord des flux", "generated": "Généré le", "series": "Série", "team": "Équipe",
        "all_teams": "Toutes les équipes (vue produit)", "scope": "Périmètre",
        "all_projects": "tous les projets de l'export", "latest_report": "Dernier rapport", "period": "Période",
        "weeks": "semaines", "baseline": "Base", "how_to_read": "Comment lire", "no_data": "Pas encore de données pour cette vue.",
        "nd": "n/d", "unit_day": "j", "days": "Jours", "unit_items": "éléments", "per_week": "éléments par semaine", "items": "éléments",
        "week_of": "Semaine du", "no_team": "(sans équipe)", "outside_export": "(hors export)",
        "no_team_project": "(sans équipe : {p})",
        "teams_note": "Les équipes sont listées par ordre alphabétique. Le tableau ne classe jamais les équipes.",
        "print": "Imprimer", "language": "Langue", "anonymous": "Version anonyme",
        "sec_flow": "Arrivées et sorties par semaine", "sec_cfd": "Diagramme de flux cumulé",
        "sec_segments": "Temps par segment", "sec_aging": "Âge du WIP", "sec_wip": "Répartition du WIP",
        "sec_efficiency": "Efficacité de flux et lead time de livraison", "sec_deps": "Carte des dépendances",
        "sec_base": "Évolution depuis la base",
        "arrivals": "Arrivées (tickets créés)", "departures": "Sorties (éléments livrés)",
        "arrivals_missing": "Les arrivées par semaine ne sont pas dans ce rapport : seules les sorties sont affichées.",
        "cfd_delivered": "Livrés (cumul)", "cfd_backlog": "Pas encore engagés",
        "cfd_coverage": "{n} tickets avec historique ; {m} sans historique ne sont pas affichés.",
        "cfd_missing": "Le diagramme de flux cumulé demande l'historique des états (flux_jira.py compute --history).",
        "left_segment": "Sortis du segment", "p50": "P50", "p70": "P70", "p85": "P85", "p95": "P95",
        "tickets_n": "n = {n}", "seg_missing": "Le temps par segment demande l'historique des états (--history).",
        "aging_by_status": "Par état", "aging_by_segment": "Par segment", "age_days": "Âge (jours)",
        "nature_active": "Actif", "nature_waiting": "En attente", "nature_dormant": "Dormant",
        "no_history": "(sans historique)", "in_segment_age": "Âge dans le segment", "status": "État", "segment": "Segment",
        "aging_p85": "Lead time P85", "aging_missing": "Pas de points par ticket. Lancer flux_jira.py compute --points.",
        "aging_note": "Un point par ticket en cours. Aucune clé de ticket n'est affichée.",
        "wip_now": "WIP actuel", "wip_history": "Répartition du WIP par rapport", "wip_total": "WIP",
        "wip_only_total": "Le rapport ne donne que le total du WIP (pas d'états d'attente ni de dormants).",
        "wip_hist_note": "Les rapports sans répartition n'affichent que le total.",
        "dormant_unknown": "sans répartition",
        "lt_from_commitment": "Lead time de livraison (depuis le point d'engagement)",
        "lt_from_creation": "Lead time (depuis la création)", "flow_eff_aggregate": "Efficacité de flux (agrégée)",
        "flow_eff_median": "Efficacité de flux (ticket médian)", "coverage": "Couverture",
        "coverage_low": "La couverture est sous 90 % : les chiffres ne décrivent qu'une partie des tickets.",
        "eff_missing": "Le lead time de livraison et l'efficacité de flux demandent l'historique des états (--history).",
        "commitment_note": "Point d'engagement : entrée dans le segment {s}.", "delivered_n": "{n} tickets livrés",
        "graph_missing": "Pas de rapport de dépendances pour cette série.", "graph_from": "Attend", "graph_team": "Équipe",
        "graph_open": "Ouvertes", "graph_unknown": "État inconnu", "graph_all": "Toutes", "graph_epics": "Entre Epics",
        "graph_table": "Les dépendances en tableau", "graph_loops": "Boucles entre équipes", "graph_none": "aucune",
        "graph_by_team": "Par équipe", "graph_by_project": "Par projet", "graph_tickets": "tickets",
        "graph_truncated": "L'export est peut-être tronqué (nombre rond de tickets) : ne pas lire cette carte.",
        "graph_unoriented": "Les liens n'ont pas de type : la carte compte des liens, pas des blocages.",
        "graph_date": "Rapport de dépendances du", "graph_age": "Âge des éléments bloqués (P50 / P85)",
        "base_missing": "Aucun rapport de base trouvé.", "base_metric": "Mesure", "base_value": "Base",
        "base_now": "Dernier", "base_change": "Évolution", "base_higher": "en hausse", "base_lower": "en baisse",
        "base_same": "inchangé", "m_departures": "Sorties par semaine (moyenne)", "m_arrivals": "Arrivées par semaine (moyenne)",
        "m_lead85": "Lead time P85", "m_wip": "WIP", "m_wip_active": "WIP actif", "m_wip_waiting": "WIP en attente",
        "m_wip_dormant": "WIP dormant", "m_delivery85": "Lead time de livraison P85",
        "m_efficiency": "Efficacité de flux (agrégée)",
        "base_not_comparable": "La base et le dernier rapport ont été calculés avec des options différentes ({d}) : à comparer avec prudence.",
        "base_diff_scope": "périmètre", "base_diff_history": "historique des états", "base_diff_dormant": "source des dormants",
        "base_since": "Depuis le {d}", "history_n": "Rapports depuis la base",
        "seg_definition": "Définition", "seg_pret": "Prêt", "seg_implementation": "Implémentation",
        "seg_revue_verification": "Revue et vérification", "seg_acceptation": "Acceptation",
        "series_label": "Série {n}", "team_label": "Équipe {l}", "project_label": "Projet {l}",
        "error_section": "Cette section n'a pas pu être construite.", "empty_page": "Aucun rapport de flux dans Flux-Lab/rapports/.",
        "decimal": ",",
    },
}
CLES_GLOSSAIRE = ["debit", "arrivees", "cfd", "segment", "aging_wip", "repartition", "wip", "engagement", "efficacite",
                  "couverture", "graphe", "base", "p50", "p85", "lead_time_age", "little", "monte_carlo",
                  "pourquoi_percentiles"]
# définitions affichées sous « How to read » pour chaque section : identifiants du glossaire
LECTURE = {"flow": ["debit", "arrivees"], "cfd": ["cfd"], "segments": ["segment", "p50", "p85"],
           "aging": ["aging_wip", "lead_time_age", "p85"], "wip": ["wip", "repartition"],
           "efficiency": ["engagement", "efficacite", "couverture", "p85"], "deps": ["graphe"], "base": ["base", "p85"]}


# ---------------------------------------------------------------------------
# Noms : identité, ou anonymisation (étape 3)
# ---------------------------------------------------------------------------

class Noms:
    """Libellés affichés des équipes, des projets et des séries. Ici : les vrais noms (voir NomsAnonymes)."""
    anonyme = False

    def __init__(self, langue: str):
        self.langue = langue
        self.t = TEXTES[langue]

    def serie(self, nom: str) -> str:
        return nom

    def projet(self, nom: str) -> str:
        return nom

    def equipe_brute(self, nom: str) -> str:
        return nom

    def sauver(self) -> None:
        """Rien à garder pour les vrais noms (la version anonyme écrit sa table de correspondance)."""

    def equipe(self, nom: str) -> str:
        """Libellé d'une équipe, y compris les cas spéciaux « (sans équipe) », « (sans équipe : PROJET) », « (hors export) »."""
        if nom == "(sans équipe)":
            return self.t["no_team"]
        if nom == "(hors export)":
            return self.t["outside_export"]
        m = re.fullmatch(r"\(sans équipe : (.+)\)", nom)
        if m:
            return self.t["no_team_project"].format(p=self.projet(m.group(1)))
        return self.equipe_brute(nom)


def etiquette(n: int) -> str:
    """Étiquette de rang n : A..Z, puis AA, AB..."""
    texte = ""
    n += 1
    while n:
        n, reste = divmod(n - 1, 26)
        texte = chr(65 + reste) + texte
    return texte


class NomsAnonymes(Noms):
    """--anonymous : « Team A », « Project B », « Series 1 » à la place des vrais noms. La correspondance (vrai nom vers
    lettre ou numéro) est gardée dans Flux-Lab/tableaux/anonymes.yaml (hors Git, permissions 600) : les lettres sont tirées
    au hasard la première fois, puis stables d'un mois à l'autre ; un nom nouveau reçoit la lettre libre suivante.
    Les noms n'entrent dans la page qu'à travers ce remplacement, avant toute écriture."""
    anonyme = True
    TYPES = ("equipes", "projets", "series")

    def __init__(self, langue: str, chemin: Path | None = None):
        super().__init__(langue)
        self.chemin = Path(chemin or ANONYMES)
        self.table = {k: {} for k in self.TYPES}
        self.modifie = False
        graine = os.environ.get("PMZILLA_LAB_SEED")
        self.hasard = random.Random(int(graine)) if graine else random.SystemRandom()
        if self.chemin.exists():
            try:
                lu = charger(self.chemin.read_text(encoding="utf-8"), self.chemin.name) or {}
            except (OSError, yaml.YAMLError):
                raise Arret(f"{self.chemin.name} est illisible : corrige-le ou supprime-le (les lettres seront retirées au "
                            "hasard, donc différentes des versions déjà partagées).") from None
            for k in self.TYPES:
                self.table[k] = {str(n): str(v) for n, v in (lu.get(k) or {}).items()}
        self.neuf = {k: not self.table[k] for k in self.TYPES}      # genre sans correspondance : tirage au hasard

    def _etiquette(self, genre: str, nom: str) -> str:
        pris = self.table[genre]
        if nom not in pris:
            utilises = set(pris.values())
            if genre == "series":
                candidats = [str(i) for i in range(1, len(pris) + 30) if str(i) not in utilises]
            else:
                candidats = [etiquette(i) for i in range(len(pris) + 30) if etiquette(i) not in utilises]
            # première fois pour ce genre : tirage au hasard parmi les premières libres ; ensuite : la première libre
            if self.neuf[genre]:
                pris[nom] = self.hasard.choice(candidats[:26 if genre != "series" else 9])
            else:
                pris[nom] = candidats[0]
            self.modifie = True
        return pris[nom]

    def serie(self, nom: str) -> str:
        return self.t["series_label"].format(n=self._etiquette("series", nom))

    def projet(self, nom: str) -> str:
        return self.t["project_label"].format(l=self._etiquette("projets", nom))

    def equipe_brute(self, nom: str) -> str:
        return self.t["team_label"].format(l=self._etiquette("equipes", nom))

    def sauver(self) -> None:
        if not self.modifie:
            return
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.chemin.parent, 0o700)
        temporaire = self.chemin.with_suffix(".tmp")
        temporaire.write_text(
            "# Correspondance entre les vrais noms et les lettres de la version anonyme du tableau de bord (hors Git, illisible\n"
            "# par Claude Code). Les lettres sont stables d'un mois à l'autre : ne pas supprimer ce fichier si une version\n"
            "# anonyme a déjà été partagée.\n"
            + yaml.safe_dump({k: dict(sorted(v.items())) for k, v in self.table.items()}, allow_unicode=True, sort_keys=False),
            encoding="utf-8")
        os.chmod(temporaire, 0o600)
        os.replace(temporaire, self.chemin)
        self.modifie = False


def cle_tri(libelle: str, noms: Noms) -> tuple:
    """Ordre alphabétique, les cas spéciaux (sans équipe, hors export) à la fin. Jamais un classement."""
    speciaux = {noms.t["no_team"], noms.t["outside_export"]}
    return (libelle.startswith("(") or libelle in speciaux, libelle.casefold())


# ---------------------------------------------------------------------------
# Lecture des rapports
# ---------------------------------------------------------------------------

def lire_json(chemin: Path) -> dict | None:
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return donnees if isinstance(donnees, dict) else None


def fichiers_dates(dossier: Path, prefixe: str) -> list[tuple[str, Path]]:
    """Fichiers « <prefixe>-AAAA-MM-JJ.json » d'un dossier, triés par date. Le préfixe est exact : « serie » ne prend pas
    « serie-recent »."""
    motif = re.compile(rf"{re.escape(prefixe)}-{DATE}\.json")
    trouves = []
    if dossier.is_dir():
        for chemin in dossier.iterdir():
            m = motif.fullmatch(chemin.name)
            if m:
                trouves.append((m.group(1), chemin))
    return sorted(trouves)


def series_trouvees() -> list[str]:
    """Noms de séries d'après les fichiers flux-*.json (sans les séries « -recent », fenêtres de 10 semaines)."""
    noms = set()
    if RAPPORTS.is_dir():
        for chemin in RAPPORTS.glob("flux-*.json"):
            m = re.fullmatch(rf"flux-(.+)-{DATE}\.json", chemin.name)
            if m and not m.group(1).endswith("-recent"):
                noms.add(m.group(1))
    return sorted(noms)


def reglages() -> list[dict]:
    brut = {}
    if CONFIG.exists():
        try:
            brut = flux_config.to_internal(charger(CONFIG.read_text(encoding="utf-8"), "flux.yaml"), "flux.yaml").get("tableaux") or {}
        except yaml.YAMLError:
            brut = {}
    series = [dict(s) for s in (brut.get("series") or []) if isinstance(s, dict) and s.get("nom")]
    return series or [{"nom": n} for n in series_trouvees()]


def pc(valeurs: dict | None, p: int):
    """Percentile d'un JSON relu (clés devenues des chaînes)."""
    if not isinstance(valeurs, dict):
        return None
    v = valeurs.get(str(p), valeurs.get(p))
    return float(v) if v is not None else None


def pcs(valeurs: dict | None) -> dict | None:
    if not isinstance(valeurs, dict):
        return None
    sortie = {p: pc(valeurs, p) for p in (50, 70, 85, 95)}
    return sortie if any(v is not None for v in sortie.values()) else None


def semaines(rapport: dict) -> list[str]:
    try:
        debut = dt.date.fromisoformat(rapport["periode"][0])
    except (KeyError, ValueError, TypeError, IndexError):
        return []
    n = len(rapport.get("debit_par_semaine") or [])
    return [(debut + dt.timedelta(weeks=i)).isoformat() for i in range(n)]


def repartition_wip(total, source_repartition, source_attente) -> dict | None:
    """WIP actif / en attente / dormant. Sans dormants ni états d'attente : le total seul (None si inconnu)."""
    if isinstance(source_repartition, dict) and "actif" in source_repartition:
        return {"total": total, "active": source_repartition.get("actif"), "waiting": source_repartition.get("attente"),
                "dormant": source_repartition.get("dormant")}
    if isinstance(source_attente, dict) and "attente" in source_attente:
        return {"total": total, "active": source_attente.get("actif"), "waiting": source_attente.get("attente"),
                "dormant": None}
    if isinstance(source_attente, int):
        return {"total": total, "active": (total - source_attente) if total is not None else None,
                "waiting": source_attente, "dormant": None}
    return {"total": total, "active": None, "waiting": None, "dormant": None} if total is not None else None


def source_equipe(rapport: dict, equipe: str | None) -> dict:
    return rapport if equipe is None else ((rapport.get("par_equipe") or {}).get(equipe) or {})


def segments_de(rapport: dict, equipe: str | None) -> dict | None:
    ts = rapport.get("temps_par_segment")
    if not isinstance(ts, dict):
        return None
    return ts.get("global") if equipe is None else (ts.get("par_equipe") or {}).get(equipe)


def cfd_de(rapport: dict, equipe: str | None) -> dict | None:
    cfd = (rapport.get("temps_par_segment") or {}).get("cfd")
    if not isinstance(cfd, dict):
        return None
    return cfd.get("global") if equipe is None else (cfd.get("par_equipe") or {}).get(equipe)


def instantane(rapport: dict, equipe: str | None) -> dict:
    """Quelques mesures d'un rapport, pour les évolutions d'un mois à l'autre et la base du pilote."""
    src = source_equipe(rapport, equipe)
    sortis = src.get("debit_par_semaine") or []
    arrivees = (rapport.get("arrivees_par_semaine") if equipe is None else src.get("arrivees_par_semaine")) or []
    lead = rapport.get("lead_time_jours") if equipe is None else src.get("lead_time")
    wip_total = rapport.get("wip") if equipe is None else src.get("wip")
    rep = repartition_wip(wip_total, src.get("wip_repartition"),
                          rapport.get("wip_attente") if equipe is None else src.get("wip_attente"))
    seg = segments_de(rapport, equipe) or {}
    livraison = pcs(((seg.get("lead_time_livraison") or {}).get("depuis_engagement")))
    efficacite = (seg.get("efficacite") or {}).get("agregee")
    return {"date": rapport.get("date"), "departures_avg": (sum(sortis) / len(sortis)) if sortis else None,
            "arrivals_avg": (sum(arrivees) / len(arrivees)) if arrivees else None, "lead_p85": pc(lead, 85),
            "wip": rep, "delivery_p85": livraison.get(85) if livraison else None,
            "efficiency": efficacite}


def vue(rapport: dict, equipe: str | None, historique: list[dict], base: dict | None, noms: Noms) -> dict:
    """Vue d'une série ou d'une équipe : tout ce que les graphiques lisent. `equipe` : vrai nom, ou None (vue produit)."""
    src = source_equipe(rapport, equipe)
    t = noms.t
    sortis = src.get("debit_par_semaine") or []
    arrivees = rapport.get("arrivees_par_semaine") if equipe is None else src.get("arrivees_par_semaine")
    lead = rapport.get("lead_time_jours") if equipe is None else src.get("lead_time")
    seg = segments_de(rapport, equipe)
    ordre = list(((rapport.get("temps_par_segment") or {}).get("parametres") or {}).get("segments") or [])
    cfd = cfd_de(rapport, equipe)
    wip_total = rapport.get("wip") if equipe is None else src.get("wip")
    rep = repartition_wip(wip_total, src.get("wip_repartition"),
                          rapport.get("wip_attente") if equipe is None else src.get("wip_attente"))
    segments = None
    livraison = efficacite = couverture = None
    if seg:
        segments = {"order": ordre, "left": {k: {"n": v.get("n"), "p50": v.get("p50"), "p85": v.get("p85")}
                                             for k, v in (seg.get("sortis") or {}).items()}}
        ll = seg.get("lead_time_livraison") or {}
        livraison = {"n": ll.get("n"), "sans_engagement": ll.get("sans_engagement"),
                     "commitment": pcs(ll.get("depuis_engagement")), "creation": pcs(ll.get("depuis_creation"))}
        e = seg.get("efficacite")
        efficacite = {"n": e.get("n"), "p50": e.get("p50"), "aggregate": e.get("agregee")} if e else None
        c = seg.get("couverture") or {}
        couverture = {"with": c.get("avec"), "total": c.get("total"), "share": c.get("part")}
    return {
        "weeks": semaines(rapport), "departures": sortis, "arrivals": arrivees or None,
        "cfd": ({"weeks": cfd.get("semaines"), "delivered": cfd.get("livres"), "backlog": cfd.get("a_faire"),
                 "segments": cfd.get("segments"), "n": cfd.get("tickets"), "without_history": cfd.get("sans_historique")}
                if cfd else None),
        "segments": segments, "delivery": livraison, "efficiency": efficacite, "coverage": couverture,
        "lead_time": pcs(lead), "wip": rep, "todo": rapport.get("a_faire") if equipe is None else src.get("a_faire"),
        "history": historique, "base": base,
    }


def libelle_segment(nom: str, t: dict) -> str:
    return t.get(f"seg_{nom}", nom)


def construire_dependances(rapport: dict, noms: Noms, projets: bool) -> dict | None:
    """Carte des dépendances d'un rapport dependencies_jira.py : noeuds (équipes ou projets) et arêtes. Un rapport d'avant
    les « aretes » est reconstruit à partir des matrices."""
    nom = noms.projet if projets else noms.equipe
    aretes = rapport.get("aretes")
    if aretes is None:
        ouvertes = {(a, b): n for a, b, n in rapport.get("matrice_ouverte") or []}
        inconnues = {(a, b): n for a, b, n in rapport.get("matrice_inconnue") or []}
        epics = {(a, b): n for a, b, n in rapport.get("matrice_portefeuille") or []}
        aretes = [{"de": a, "vers": b, "ouvertes": ouvertes.get((a, b), 0), "inconnues": inconnues.get((a, b), 0),
                   "toutes": n, "entre_epics": epics.get((a, b), 0), "bloquees_en_cours": None, "age_bloquees": None,
                   "oriente": rapport.get("mode") == "orienté"} for a, b, n in rapport.get("matrice_totale") or []]
    tickets = rapport.get("equipes_tickets") or {}
    noeuds = {}
    for brut, n in tickets.items():
        noeuds[brut] = n
    for a in aretes:
        noeuds.setdefault(a["de"], 0)
        noeuds.setdefault(a["vers"], 0)
    return {
        "date": rapport.get("date"), "oriented": rapport.get("mode") == "orienté",
        "truncated": bool(rapport.get("tronques")),
        "nodes": sorted(({"name": nom(k), "tickets": v} for k, v in noeuds.items()),
                        key=lambda x: cle_tri(x["name"], noms)),
        "edges": sorted(({"from": nom(a["de"]), "to": nom(a["vers"]), "open": a.get("ouvertes", 0),
                          "unknown": a.get("inconnues", 0), "all": a.get("toutes", 0), "epics": a.get("entre_epics", 0),
                          "blocked": a.get("bloquees_en_cours"), "age": pcs(a.get("age_bloquees"))} for a in aretes),
                        key=lambda e: (cle_tri(e["from"], noms), cle_tri(e["to"], noms))),
        "loops": [[nom(x) for x in boucle] for boucle in rapport.get("boucles") or []],
    }


def comparabilite(base: dict, dernier: dict, noms: Noms) -> list[str]:
    """Différences d'options entre le rapport de base et le dernier : le tableau les signale au lieu de les cacher."""
    t = noms.t
    diffs = []
    if (base.get("perimetre") or {}).get("projets") != (dernier.get("perimetre") or {}).get("projets"):
        diffs.append(t["base_diff_scope"])
    if bool(base.get("temps_par_segment")) != bool(dernier.get("temps_par_segment")):
        diffs.append(t["base_diff_history"])
    if (base.get("dormants") or {}).get("source") != (dernier.get("dormants") or {}).get("source"):
        diffs.append(t["base_diff_dormant"])
    return diffs


def construire_serie(cfg: dict, indice: int, noms: Noms) -> dict | None:
    rapports = [(d, lire_json(c)) for d, c in fichiers_dates(RAPPORTS, f"flux-{cfg['nom']}")]
    rapports = [(d, r) for d, r in rapports if r][-MAX_RAPPORTS:]
    if not rapports:
        return None
    t = noms.t
    date, dernier = rapports[-1]
    base_rapport = next((r for d, r in rapports if d == str(cfg.get("base"))), None) if cfg.get("base") else None
    equipes = sorted((dernier.get("par_equipe") or {}), key=lambda e: cle_tri(noms.equipe(e), noms))

    def historique(equipe):
        return [instantane(r, equipe) for _, r in rapports]

    def base_de(equipe):
        return instantane(base_rapport, equipe) if base_rapport else None

    vues = {"": vue(dernier, None, historique(None), base_de(None), noms)}
    for e in equipes:
        vues[noms.equipe(e)] = vue(dernier, e, historique(e), base_de(e), noms)
    points = None
    fichiers_points = fichiers_dates(TABLEAUX, f"points-{cfg['nom']}")
    if fichiers_points:
        contenu = lire_json(fichiers_points[-1][1]) or {}
        points = {"date": contenu.get("date"), "base": contenu.get("base_age"),
                  "segments": contenu.get("segments") or [],
                  "items": [{"team": noms.equipe(p.get("equipe") or "(sans équipe)"), "status": p.get("etat"),
                             "segment": p.get("segment"), "age": p.get("age"), "age_segment": p.get("age_segment"),
                             "nature": NATURES.get(p.get("nature"), "active")} for p in contenu.get("points") or []]}
    deps = []
    for cle, projets in (("dependances", False), ("dependances_projets", True)):
        if cfg.get(cle):
            lus = [(d, lire_json(c)) for d, c in fichiers_dates(
                RAPPORTS, f"dependances-{cfg[cle]}" + ("-projets" if projets and not str(cfg[cle]).endswith("-projets") else ""))]
            lus = [(d, r) for d, r in lus if r]
            if lus:
                dep = construire_dependances(lus[-1][1], noms, projets)
                dep["kind"] = "project" if projets else "team"
                deps.append(dep)
    perimetre = (dernier.get("perimetre") or {}).get("projets")
    comparable = comparabilite(base_rapport, dernier, noms) if base_rapport else []
    return {
        "id": f"s{indice}", "name": noms.serie(cfg["nom"]), "date": date,
        "period": dernier.get("periode"), "weeks_n": dernier.get("semaines"),
        "scope": ("all" if not perimetre else ("all" if perimetre == "tous" else [noms.projet(p) for p in perimetre])),
        "teams": [noms.equipe(e) for e in equipes], "views": vues, "points": points, "dependencies": deps,
        "baseline": ({"date": str(cfg.get("base")), "found": bool(base_rapport), "differences": comparable}
                     if cfg.get("base") else None),
        "commitment": ((dernier.get("temps_par_segment") or {}).get("parametres") or {}).get("point_engagement"),
        "segment_order": list(((dernier.get("temps_par_segment") or {}).get("parametres") or {}).get("segments") or []),
        "segment_labels": {k: libelle_segment(k, t) for k in
                           (((dernier.get("temps_par_segment") or {}).get("parametres") or {}).get("segments") or [])},
    }


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

def json_sur(donnees) -> str:
    """JSON pour un <script> : jamais de « </script> » ni de « <!-- » dans le texte."""
    return (json.dumps(donnees, ensure_ascii=False, separators=(",", ":"))
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def lire_lib(chemin: Path | None = None, empreinte: Path | None = None) -> str:
    """Contenu de la bibliothèque de graphiques. Par défaut tools/vendor/echarts.min.js, dont l'empreinte SHA-256 doit
    correspondre à tools/vendor/echarts.sha256 (écrite au téléchargement) ; PMZILLA_LAB_ECHARTS (tests) la remplace."""
    forcee = os.environ.get("PMZILLA_LAB_ECHARTS")
    chemin = Path(chemin or forcee or LIB_PAR_DEFAUT)
    if not chemin.is_file():
        raise Arret(MESSAGE_LIB.format(chemin=chemin))
    contenu = chemin.read_bytes()
    empreinte = empreinte or (None if (forcee and chemin == Path(forcee)) else ICI / "vendor" / "echarts.sha256")
    if empreinte is not None and Path(empreinte).is_file():
        attendu = Path(empreinte).read_text(encoding="utf-8").split()[0]
        if hashlib.sha256(contenu).hexdigest() != attendu:
            raise Arret(f"L'empreinte SHA-256 de {chemin.name} ne correspond pas à {Path(empreinte).name} : fichier modifié "
                        "ou corrompu. Retélécharge-le : zsh tools/vendor/telecharger_echarts.sh")
    return contenu.decode("utf-8").replace("</script", "<\\/script")


def donnees_page(langue: str, noms: Noms, anonyme: bool) -> dict:
    t = TEXTES[langue]
    series = []
    echecs = 0
    for i, cfg in enumerate(sorted(reglages(), key=lambda c: noms.serie(c["nom"]).casefold())):
        try:
            s = construire_serie(cfg, i, noms)
        except Exception:        # une série en échec n'empêche pas les autres, ni la page de s'écrire
            echecs += 1
            continue
        if s:
            series.append(s)
    series.sort(key=lambda s: s["name"].casefold())
    return {"lang": langue, "texts": t, "generated": aujourdhui().isoformat(), "anonymous": anonyme,
            "series": series, "failed_series": echecs,
            "glossary": {k: glossaire.GLOSSAIRE[langue][k] for k in CLES_GLOSSAIRE},
            "reading": LECTURE}


def ecrire_page(langue: str, anonyme: bool, sortie: Path | None) -> Path:
    noms = creer_noms(langue, anonyme)
    donnees = donnees_page(langue, noms, anonyme)
    gabarit = (ICI / "flow_board_page.html").read_text(encoding="utf-8")
    valeurs = {"LANG": langue, "TITLE": TEXTES[langue]["title"],
               "CSS": (ICI / "flow_board_page.css").read_text(encoding="utf-8"), "ECHARTS": lire_lib(),
               "APP": (ICI / "flow_board_page.js").read_text(encoding="utf-8").replace("</script", "<\\/script"),
               "DATA": json_sur(donnees)}
    # une seule passe : un texte inséré (la bibliothèque, par exemple) n'est jamais relu comme un gabarit
    page = re.sub(r"\{\{(LANG|TITLE|CSS|ECHARTS|APP|DATA)\}\}", lambda m: valeurs[m.group(1)], gabarit)
    if sortie is None:
        suffixe = ("" if langue == "en" else f"-{langue}") + ("-anonyme" if anonyme else "")
        sortie = TABLEAUX / f"tableau-flux-{aujourdhui().isoformat()}{suffixe}.html"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(sortie.parent, 0o700)
    except OSError:
        pass
    sortie.write_text(page, encoding="utf-8")
    os.chmod(sortie, 0o600)
    noms.sauver()
    return sortie


def creer_noms(langue: str, anonyme: bool) -> Noms:
    return NomsAnonymes(langue) if anonyme else Noms(langue)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tableau de bord visuel des flux (HTML autonome, hors ligne)")
    parser.add_argument("--language", dest="langue", choices=["en", "fr"], default="en", help="langue de la page (en par défaut)")
    parser.add_argument("--anonymous", dest="anonyme", action="store_true", help="remplace les noms d'équipes, de projets et de séries")
    parser.add_argument("--output", dest="sortie", help="fichier à écrire (par défaut Flux-Lab/tableaux/tableau-flux-AAAA-MM-JJ[-fr][-anonyme].html)")
    parser.add_argument("--open", dest="ouvrir", action="store_true", help="ouvre la page dans le navigateur")
    args = parser.parse_args(flux_config.refuse_old_options(sys.argv[1:] if argv is None else argv, flux_config.OPTIONS_COMMUNES))
    try:
        sortie = ecrire_page(args.langue, args.anonyme, Path(args.sortie).expanduser() if args.sortie else None)
    except Arret as erreur:
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 1
    print(f"Tableau de bord : {sortie} (permissions 600)")
    if args.ouvrir:
        webbrowser.open(sortie.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
