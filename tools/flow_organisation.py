"""PMZilla Lab : lecture stricte du référentiel d'organisation (Flux-Lab/organisation.yaml, hors Git).

Le référentiel décrit les sites, les départements, les Mission Teams, les équipes (effectif, site, identifiants Jira)
et les équipes transverses. Il remplace la table des équipes (equipes-assets.yaml) : l'identifiant d'équipe Jira est
traduit en nom d'équipe ici, et les rapports par Mission Team ou par site s'appuient sur lui. Aucun champ de personne :
toute clé hors de la liste ci-dessous est refusée (c'est la règle des clés inconnues qui garde les personnes dehors).

Structure du fichier (le contrat des outils qui le lisent) :

    source_date: 2026-10-01
    sites: [nom, ...]
    departments:
      - name: ...
        site: ...                    # un site déclaré
        headcount: 12
        mission_teams:               # OU teams: [noms d'équipes] (exactement l'un des deux)
          - name: ...
            discovery_workflow_pilot: true     # facultatif, booléen
            teams: [noms d'équipes]
    teams:
      - name: ...
        headcount: 5
        site: ...                    # facultatif
        jira_team_ids: [identifiant, ...]      # facultatif (absent ou vide : pas d'identifiant)
        single_po: true                        # facultatif, booléen (qualité des stories, attribut d'équipe)
    cross_cutting_teams: [noms d'équipes]      # facultatif

Les refus sont des `ErreurConfig` (code 1) : le message donne le chemin de la clé et le numéro de ligne, jamais une valeur,
ni un nom d'équipe, de site ou d'identifiant. Rien ici n'écrit de nom dans une sortie : les noms restent dans les fichiers
du dossier de flux hors Git.

    from flow_organisation import charger_si_present
    referentiel = charger_si_present(chemin)    # None si le fichier n'existe pas
    referentiel.team_for_jira_id("id1")

Ce module ne lit un fichier que si on lui donne un chemin (`charger_fichier`, `charger_si_present`) ; `charger` reçoit un texte.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from yaml_strict import DictLignes, ErreurConfig, charger as charger_strict

GROUPEMENTS = ("mission-team", "site")

# libellé du groupe des équipes de l'export que le référentiel ne décrit pas, selon la langue de la réponse
HORS_REFERENTIEL = {"fr": "hors référentiel", "en": "outside the referential"}
# libellé du groupe des équipes décrites mais sans Mission Team (ou sans site) : jamais confondu avec « hors référentiel »
SANS_GROUPE = {
    "mission-team": {"fr": "sans Mission Team", "en": "without Mission Team"},
    "site": {"fr": "sans site", "en": "without site"},
}

CLES_RACINE = {"source_date", "sites", "departments", "teams", "cross_cutting_teams"}
CLES_DEPARTEMENT = {"name", "site", "headcount", "mission_teams", "teams"}
CLES_MISSION_TEAM = {"name", "discovery_workflow_pilot", "teams"}
CLES_EQUIPE = {"name", "headcount", "site", "jira_team_ids", "type", "single_po"}
CLES_CATALOGUE_RACINE = {"teams"}
CLES_ENTREE_CATALOGUE = {"name", "jira_team_ids", "type", "obsolete"}
# les quatre sous-types de Team d'Assets (change team-mapping, design Q5) : noms génériques, comparés exactement
TYPES_EQUIPE = ("Development Team", "Verification Team", "Product Management Team", "Other Team")

# phrases du design D11 (refus), par langue ; les chemins suivent les deux points, jamais une valeur
PHRASE_TYPE = {"fr": "type d'équipe autre que les quatre sous-types de Team : {paths}",
               "en": "team type other than the four Team sub-types: {paths}"}
PHRASE_NOMME_COMME = {"fr": "équipe du catalogue nommée comme une équipe du référentiel : {paths}",
                      "en": "catalogue team named like a referential team: {paths}"}

STRUCTURE_CATALOGUE = """teams:
  - name: <libellé>
    jira_team_ids: [<identifiant>, ...]
    type: <sous-type de Team>        # facultatif
    obsolete: <true|false>           # facultatif"""

STRUCTURE = """source_date: <date>
sites: [<site>, ...]
departments:
  - name: <nom>
    site: <site déclaré>
    headcount: <entier>
    mission_teams:                 # ou teams: [<équipe>, ...]
      - name: <nom>
        discovery_workflow_pilot: <true|false>   # facultatif
        teams: [<équipe>, ...]
teams:
  - name: <nom>
    headcount: <entier>
    site: <site déclaré>           # facultatif
    jira_team_ids: [<identifiant>, ...]   # facultatif
    type: <sous-type de Team>      # facultatif, force le type déduit du catalogue
cross_cutting_teams: [<équipe>, ...]  # facultatif"""

# mêmes structures pour une sortie en anglais (messages « aucune source d'équipes ») : clés seules, jamais une valeur
STRUCTURE_EN = """source_date: <date>
sites: [<site>, ...]
departments:
  - name: <name>
    site: <declared site>
    headcount: <integer>
    mission_teams:                 # or teams: [<team>, ...]
      - name: <name>
        discovery_workflow_pilot: <true|false>   # optional
        teams: [<team>, ...]
teams:
  - name: <name>
    headcount: <integer>
    site: <declared site>          # optional
    jira_team_ids: [<identifier>, ...]   # optional
    type: <Team sub-type>          # optional, forces the type deduced from the catalogue
cross_cutting_teams: [<team>, ...]  # optional"""

STRUCTURE_CATALOGUE_EN = """teams:
  - name: <label>
    jira_team_ids: [<identifier>, ...]
    type: <Team sub-type>            # optional
    obsolete: <true|false>           # optional"""


def outside_label(language: str = "fr") -> str:
    """Libellé du groupe « hors référentiel » (« outside the referential » en anglais) ; le français pour toute autre langue."""
    return HORS_REFERENTIEL["en" if language == "en" else "fr"]


def no_group_label(by: str, language: str = "fr") -> str:
    """Libellé des équipes décrites mais sans Mission Team (by = "mission-team") ou sans site (by = "site")."""
    return SANS_GROUPE[by]["en" if language == "en" else "fr"]


@dataclass(frozen=True)
class Equipe:
    """Une équipe décrite : effectif, site propre (ou None) et identifiants d'équipe Jira."""
    nom: str
    effectif: int
    site: str | None
    jira_ids: tuple[str, ...] = ()
    type: str | None = None          # type forcé (clé facultative du référentiel), jamais écrit par un outil
    chemin: str = ""                 # « teams[i] » et ligne de sa clé name, pour les messages (jamais le nom)
    ligne: int = 0
    chemin_type: str = ""            # chemin et ligne de la clé type (vides sans type forcé)
    ligne_type: int = 0
    single_po: bool = False          # story-quality-audit D8 : attribut de l'équipe déclaré par l'utilisateur, aucune donnée de personne


@dataclass(frozen=True)
class MissionTeam:
    """Une Mission Team : son drapeau pilote du Discovery Workflow et ses équipes."""
    nom: str
    pilote_discovery_workflow: bool
    equipes: tuple[str, ...]


@dataclass(frozen=True)
class Departement:
    """Un département : son site, son effectif, et soit des Mission Teams, soit des équipes directes."""
    nom: str
    site: str
    effectif: int
    mission_teams: tuple[MissionTeam, ...]
    equipes_directes: tuple[str, ...]

    def equipes(self) -> list[str]:
        """Toutes les équipes du département, par Mission Team puis directes."""
        return [e for mt in self.mission_teams for e in mt.equipes] + list(self.equipes_directes)


@dataclass
class Referentiel:
    """Le référentiel lu et vérifié. Les noms servent aux fichiers du dossier de flux ; aucune méthode ne les écrit."""
    source_date: dt.date
    sites: tuple[str, ...]
    departments: tuple[Departement, ...]
    teams: dict[str, Equipe]
    cross_cutting_teams: tuple[str, ...] = ()
    _par_id: dict[str, str] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self._par_id = {i: e.nom for e in self.teams.values() for i in e.jira_ids}

    # ---- identifiants Jira
    def team_for_jira_id(self, identifiant) -> str | None:
        """Nom de l'équipe qui porte cet identifiant d'équipe Jira, ou None s'il n'est dans aucune."""
        return self._par_id.get(str(identifiant))

    @property
    def jira_ids_count(self) -> int:
        """Nombre d'identifiants d'équipe Jira distincts décrits."""
        return len(self._par_id)

    @property
    def has_jira_ids(self) -> bool:
        """Vrai si au moins une équipe porte un identifiant Jira (le référentiel remplace alors la table des équipes)."""
        return bool(self._par_id)

    # ---- rattachements
    def mission_team_of(self, nom_equipe: str) -> str | None:
        """Mission Team de l'équipe, ou None (équipe inconnue, directe d'un département ou transverse)."""
        for d in self.departments:
            for mt in d.mission_teams:
                if nom_equipe in mt.equipes:
                    return mt.nom
        return None

    def department_of(self, nom_equipe: str) -> str | None:
        """Département de l'équipe, ou None (équipe inconnue ou transverse)."""
        for d in self.departments:
            if nom_equipe in d.equipes():
                return d.nom
        return None

    def site_of(self, nom_equipe: str) -> str | None:
        """Site de l'équipe : le sien, sinon celui de son département ; None si aucun des deux ou équipe inconnue."""
        equipe = self.teams.get(nom_equipe)
        if equipe is None:
            return None
        if equipe.site:
            return equipe.site
        for d in self.departments:
            if nom_equipe in d.equipes():
                return d.site
        return None

    # ---- groupes
    def _groupe(self, nom_equipe: str, by: str) -> str | None:
        return self.mission_team_of(nom_equipe) if by == "mission-team" else self.site_of(nom_equipe)

    def group_of(self, nom_equipe: str, by: str, language: str = "fr") -> str:
        """Groupe de l'équipe : son nom de Mission Team ou de site ; « sans … » si elle est décrite sans groupe ;
        « hors référentiel » si le référentiel ne la décrit pas."""
        _verifier_groupement(by)
        if nom_equipe not in self.teams:
            return outside_label(language)
        return self._groupe(nom_equipe, by) or no_group_label(by, language)

    def groups(self, by: str, language: str = "fr") -> dict[str, dict]:
        """Groupes décrits par le référentiel, dans l'ordre alphabétique des noms de groupe :
        nom du groupe -> {"teams": équipes (ordre alphabétique), "headcount": somme des effectifs des équipes}.
        Les Mission Teams (ou sites) sans équipe y figurent à zéro ; le groupe « hors référentiel » n'y est pas
        (le référentiel ne connaît pas les équipes de l'export qu'il ne décrit pas : voir `group_of`)."""
        _verifier_groupement(by)
        groupes: dict[str, list[str]] = {}
        if by == "mission-team":
            for d in self.departments:
                for mt in d.mission_teams:
                    groupes.setdefault(mt.nom, [])
        else:
            for s in self.sites:
                groupes.setdefault(s, [])
        for nom in self.teams:
            groupes.setdefault(self.group_of(nom, by, language), []).append(nom)
        return {g: {"teams": sorted(groupes[g]), "headcount": sum(self.teams[n].effectif for n in groupes[g])}
                for g in sorted(groupes)}

    def structure_summary(self, by: str, language: str = "fr") -> list[dict]:
        """Résumé de structure pour un rapport par Mission Team ou par site : une ligne par groupe, par ordre alphabétique
        du nom de groupe, avec le nombre d'équipes et l'effectif. Aucun ratio, aucun classement par un chiffre."""
        return [{"group": g, "teams": len(v["teams"]), "headcount": v["headcount"]}
                for g, v in self.groups(by, language).items()]


def _verifier_groupement(by: str) -> None:
    if by not in GROUPEMENTS:
        raise ValueError(f"regroupement inconnu : attendu {' ou '.join(GROUPEMENTS)}")


class _Lecteur:
    """Vérifie le document lu par yaml_strict ; chaque refus nomme le chemin de la clé et la ligne, jamais une valeur."""

    def __init__(self, source: str, language: str = "fr", sujet: str = "le référentiel"):
        self.source = source
        self.language = "en" if language == "en" else "fr"
        self.sujet = sujet

    def refuser(self, message: str):
        raise ErreurConfig(f"{self.source} : {message}")

    @staticmethod
    def ligne_du_bloc(bloc, defaut: int = 0) -> int:
        return min(bloc.lignes.values()) if getattr(bloc, "lignes", None) else defaut

    def bloc(self, valeur, chemin: str, ligne: int) -> DictLignes:
        if not isinstance(valeur, DictLignes):
            self.refuser(f"« {chemin} » (L{ligne}) doit être un bloc de clés.")
        return valeur

    def cles(self, bloc: DictLignes, chemin: str, permises: set[str], obligatoires: set[str], ligne: int) -> None:
        """Refuse une clé inconnue (aucune clé de personne n'est permise) et une clé obligatoire absente."""
        pre = f"{chemin}." if chemin else ""
        for cle in bloc:
            if cle not in permises:
                self.refuser(f"clé inconnue « {pre}{cle} » (L{bloc.lignes.get(cle, ligne)}) ; "
                             f"{self.sujet} ne décrit aucune personne et n'accepte que les clés de sa structure.")
        for cle in sorted(obligatoires - set(bloc)):
            self.refuser(f"clé obligatoire absente : « {pre}{cle} » (bloc commençant L{ligne}).")

    def liste(self, bloc: DictLignes, cle: str, chemin: str) -> list:
        valeur = bloc.get(cle)
        if not isinstance(valeur, list):
            self.refuser(f"« {chemin}.{cle} » (L{bloc.lignes[cle]}) doit être une liste." if chemin
                         else f"« {cle} » (L{bloc.lignes[cle]}) doit être une liste.")
        return valeur

    def texte(self, valeur, chemin: str, ligne: int) -> str:
        if not isinstance(valeur, str) or not valeur.strip():
            self.refuser(f"« {chemin} » (L{ligne}) doit être un texte non vide.")
        return valeur

    def noms(self, bloc: DictLignes, cle: str, chemin: str) -> tuple[str, ...]:
        """Liste de textes non vides (noms d'équipes ou de sites)."""
        pre = f"{chemin}." if chemin else ""
        return tuple(self.texte(v, f"{pre}{cle}[{i}]", bloc.lignes[cle]) for i, v in enumerate(self.liste(bloc, cle, chemin)))

    def effectif(self, bloc: DictLignes, chemin: str) -> int:
        valeur = bloc["headcount"]
        if isinstance(valeur, bool) or not isinstance(valeur, int) or valeur < 0:
            self.refuser(f"« {chemin}.headcount » (L{bloc.lignes['headcount']}) doit être un entier positif ou nul.")
        return valeur

    def identifiants(self, bloc: DictLignes, chemin: str) -> tuple[str, ...]:
        if "jira_team_ids" not in bloc or bloc["jira_team_ids"] is None:
            return ()
        ids = []
        for i, v in enumerate(self.liste(bloc, "jira_team_ids", chemin)):
            if isinstance(v, bool) or not isinstance(v, (str, int)) or str(v).strip() == "":
                self.refuser(f"« {chemin}.jira_team_ids[{i}] » (L{bloc.lignes['jira_team_ids']}) doit être un identifiant "
                             "(texte ou entier non vide).")
            ids.append(str(v))
        return tuple(ids)

    def site(self, bloc: DictLignes, chemin: str, sites: set[str], obligatoire: bool) -> str | None:
        if "site" not in bloc and not obligatoire:
            return None
        nom = self.texte(bloc["site"], f"{chemin}.site", bloc.lignes["site"])
        if nom not in sites:
            self.refuser(f"« {chemin}.site » (L{bloc.lignes['site']}) désigne un site non déclaré dans « sites ».")
        return nom

    def lire(self, doc) -> Referentiel:
        if not isinstance(doc, DictLignes):
            self.refuser("le fichier doit être un bloc de clés (structure attendue : "
                         + ", ".join(sorted(CLES_RACINE)) + ").")
        self.cles(doc, "", CLES_RACINE, {"source_date", "sites", "departments", "teams"}, 1)
        date = doc["source_date"]
        if isinstance(date, str):
            try:
                date = dt.date.fromisoformat(date)
            except ValueError:
                pass
        if isinstance(date, dt.datetime) or not isinstance(date, dt.date):
            self.refuser(f"« source_date » (L{doc.lignes['source_date']}) doit être une date AAAA-MM-JJ.")
        sites = self.noms(doc, "sites", "")
        ensemble_sites = set(sites)
        equipes = self.equipes(doc, ensemble_sites)
        departements = self.departements(doc, ensemble_sites, equipes)
        transverses = self.noms(doc, "cross_cutting_teams", "") if "cross_cutting_teams" in doc else ()
        for i, nom in enumerate(transverses):
            if nom not in equipes:
                self.refuser(f"« cross_cutting_teams[{i}] » (L{doc.lignes['cross_cutting_teams']}) désigne une équipe "
                             "non décrite dans « teams ».")
        self.unicite_identifiants(doc, equipes)
        return Referentiel(date, sites, departements, equipes, transverses)

    def equipes(self, doc: DictLignes, sites: set[str]) -> dict[str, Equipe]:
        equipes: dict[str, Equipe] = {}
        vues: dict[str, str] = {}
        types_refuses: list[str] = []
        for i, brut in enumerate(self.liste(doc, "teams", "")):
            chemin = f"teams[{i}]"
            bloc = self.bloc(brut, chemin, doc.lignes["teams"])
            ligne = self.ligne_du_bloc(bloc, doc.lignes["teams"])
            self.cles(bloc, chemin, CLES_EQUIPE, {"name", "headcount"}, ligne)
            nom = self.texte(bloc["name"], f"{chemin}.name", bloc.lignes["name"])
            if nom in vues:
                self.refuser(f"une équipe est décrite deux fois : « {vues[nom]}.name » et « {chemin}.name » "
                             f"(L{equipes_ligne(doc, vues[nom])} et L{bloc.lignes['name']}).")
            vues[nom] = chemin
            type_ = None
            if "type" in bloc:
                if bloc["type"] in TYPES_EQUIPE:
                    type_ = bloc["type"]
                else:
                    types_refuses.append(f"« {chemin}.type » (L{bloc.lignes['type']})")
            un_seul_po = bloc.get("single_po", False)
            if not isinstance(un_seul_po, bool):
                self.refuser(f"« {chemin}.single_po » (L{bloc.lignes['single_po']}) doit être true ou false.")
            equipes[nom] = Equipe(nom, self.effectif(bloc, chemin), self.site(bloc, chemin, sites, False),
                                  self.identifiants(bloc, chemin), type_, chemin, bloc.lignes["name"],
                                  f"{chemin}.type" if "type" in bloc else "", bloc.lignes.get("type", 0), un_seul_po)
        if types_refuses:
            self.refuser(PHRASE_TYPE[self.language].format(paths=" ; ".join(types_refuses)))
        return equipes

    def departements(self, doc: DictLignes, sites: set[str], equipes: dict[str, Equipe]) -> tuple[Departement, ...]:
        departements = []
        rangees: dict[str, str] = {}   # nom d'équipe -> chemin (avec ligne) de la liste qui la range
        for i, brut in enumerate(self.liste(doc, "departments", "")):
            chemin = f"departments[{i}]"
            bloc = self.bloc(brut, chemin, doc.lignes["departments"])
            ligne = self.ligne_du_bloc(bloc, doc.lignes["departments"])
            self.cles(bloc, chemin, CLES_DEPARTEMENT, {"name", "site", "headcount"}, ligne)
            nom = self.texte(bloc["name"], f"{chemin}.name", bloc.lignes["name"])
            site = self.site(bloc, chemin, sites, True)
            effectif = self.effectif(bloc, chemin)
            if ("mission_teams" in bloc) == ("teams" in bloc):
                self.refuser(f"« {chemin} » (L{ligne}) doit avoir exactement l'une des clés « mission_teams » ou « teams » "
                             "(ni les deux, ni aucune).")
            mission_teams, directes = [], ()
            if "teams" in bloc:
                directes = self.noms(bloc, "teams", chemin)
                self.ranger(directes, f"{chemin}.teams", bloc.lignes["teams"], equipes, rangees)
            else:
                for j, mbrut in enumerate(self.liste(bloc, "mission_teams", chemin)):
                    cm = f"{chemin}.mission_teams[{j}]"
                    mbloc = self.bloc(mbrut, cm, bloc.lignes["mission_teams"])
                    mligne = self.ligne_du_bloc(mbloc, bloc.lignes["mission_teams"])
                    self.cles(mbloc, cm, CLES_MISSION_TEAM, {"name", "teams"}, mligne)
                    mnom = self.texte(mbloc["name"], f"{cm}.name", mbloc.lignes["name"])
                    pilote = mbloc.get("discovery_workflow_pilot", False)
                    if not isinstance(pilote, bool):
                        self.refuser(f"« {cm}.discovery_workflow_pilot » (L{mbloc.lignes['discovery_workflow_pilot']}) "
                                     "doit être true ou false.")
                    liste = self.noms(mbloc, "teams", cm)
                    self.ranger(liste, f"{cm}.teams", mbloc.lignes["teams"], equipes, rangees)
                    mission_teams.append(MissionTeam(mnom, pilote, liste))
            departements.append(Departement(nom, site, effectif, tuple(mission_teams), directes))
        return tuple(departements)

    def ranger(self, noms: tuple[str, ...], chemin: str, ligne: int, equipes: dict[str, Equipe],
               rangees: dict[str, str]) -> None:
        """Refuse une équipe non décrite, ou rangée sous deux Mission Teams / départements (les deux chemins et lignes)."""
        for i, nom in enumerate(noms):
            if nom not in equipes:
                self.refuser(f"« {chemin}[{i}] » (L{ligne}) désigne une équipe non décrite dans « teams ».")
            ici = f"« {chemin} » (L{ligne})"
            if nom in rangees:
                self.refuser(f"une équipe est rangée deux fois, sous deux Mission Teams ou départements : "
                             f"{rangees[nom]} et {ici}.")
            rangees[nom] = ici

    def unicite_identifiants(self, doc: DictLignes, equipes: dict[str, Equipe]) -> None:
        vus: dict[str, str] = {}
        for i, equipe in enumerate(doc["teams"]):
            chemin = f"« teams[{i}].jira_team_ids » (L{equipe.lignes.get('jira_team_ids', 0)})"
            for identifiant in dict.fromkeys(str(v) for v in (equipe.get("jira_team_ids") or [])):
                if identifiant in vus:
                    self.refuser(f"un identifiant d'équipe Jira est listé sous deux équipes : {vus[identifiant]} et {chemin}.")
                vus[identifiant] = chemin


def equipes_ligne(doc: DictLignes, chemin: str) -> int:
    """Ligne de la clé « name » de l'équipe désignée par un chemin « teams[i] »."""
    return doc["teams"][int(chemin[chemin.index("[") + 1:-1])].lignes["name"]


def charger(texte: str, source: str = "organisation.yaml", language: str = "fr") -> Referentiel:
    """Référentiel d'un texte YAML : lecture stricte (clé écrite deux fois refusée par yaml_strict), structure vérifiée.
    Une erreur de syntaxe YAML devient une `ErreurConfig` avec la ligne seule (le texte fautif n'est jamais repris)."""
    try:
        document = charger_strict(texte, source)
    except yaml.YAMLError as erreur:
        repere = getattr(erreur, "problem_mark", None)
        ou = f" (L{repere.line + 1})" if repere is not None else ""
        raise ErreurConfig(f"{source} : YAML illisible{ou} ; corriger la syntaxe du fichier.") from None
    return _Lecteur(source, language).lire(document)


def charger_fichier(chemin, language: str = "fr") -> Referentiel:
    """Référentiel du fichier donné. Fichier absent : `ErreurConfig` (code 1) qui donne la structure attendue, sans valeur."""
    chemin = Path(chemin)
    if not chemin.is_file():
        raise ErreurConfig(f"{chemin.name} : le référentiel d'organisation est absent ; le créer avec cette structure "
                           f"(clés seules) :\n{STRUCTURE}")
    return charger(chemin.read_text(encoding="utf-8"), chemin.name, language)


def charger_si_present(chemin, language: str = "fr") -> Referentiel | None:
    """Référentiel du fichier donné, ou None s'il n'existe pas (outils qui ne lisent que les étiquettes d'équipe).
    Un fichier présent mais refusé lève toujours `ErreurConfig`."""
    if not Path(chemin).is_file():
        return None
    return charger_fichier(chemin, language)


# ---------------------------------------------------------------------------
# Catalogue des équipes Jira (change team-mapping, design D1) : Flux-Lab/equipes-jira.yaml, hors Git
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EntreeCatalogue:
    """Une entrée du catalogue : libellé, identifiants, type (ou None) et drapeau obsolète ; chemin et ligne pour les messages."""
    nom: str
    jira_ids: tuple[str, ...]
    type: str | None
    obsolete: bool
    chemin: str
    ligne: int


@dataclass
class Catalogue:
    """Le catalogue lu. Vide quand le fichier est absent. Aucune méthode n'écrit un libellé."""
    entrees: tuple[EntreeCatalogue, ...] = ()
    _par_id: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self._par_id = {i: e for e in self.entrees for i in e.jira_ids}

    def entree_pour(self, identifiant) -> EntreeCatalogue | None:
        """Entrée qui porte cet identifiant, obsolète ou non, ou None."""
        return self._par_id.get(str(identifiant))

    def est_obsolete(self, identifiant) -> bool:
        entree = self.entree_pour(identifiant)
        return bool(entree and entree.obsolete)

    @property
    def ids(self) -> set[str]:
        return set(self._par_id)


def charger_catalogue(texte: str, source: str = "equipes-jira.yaml", language: str = "fr") -> Catalogue:
    """Catalogue d'un texte YAML : lecture stricte, refus (code 1) avec chemin et ligne de clé, jamais une valeur :
    clé inconnue (`obsolete_to_confirm` comprise), nom vide ou en double, identifiant en double, type hors des quatre noms."""
    try:
        document = charger_strict(texte, source)
    except yaml.YAMLError as erreur:
        repere = getattr(erreur, "problem_mark", None)
        ou = f" (L{repere.line + 1})" if repere is not None else ""
        raise ErreurConfig(f"{source} : YAML illisible{ou} ; corriger la syntaxe du fichier.") from None
    lecteur = _Lecteur(source, language, "le catalogue")
    if not isinstance(document, DictLignes):
        lecteur.refuser("le fichier doit être un bloc de clés (structure attendue : teams).")
    lecteur.cles(document, "", CLES_CATALOGUE_RACINE, {"teams"}, 1)
    entrees, noms, ids, types_refuses = [], {}, {}, []
    brutes = [] if document["teams"] is None else lecteur.liste(document, "teams", "")      # « teams: » vide : aucune entrée
    for i, brut in enumerate(brutes):
        chemin = f"teams[{i}]"
        bloc = lecteur.bloc(brut, chemin, document.lignes["teams"])
        ligne = lecteur.ligne_du_bloc(bloc, document.lignes["teams"])
        lecteur.cles(bloc, chemin, CLES_ENTREE_CATALOGUE, {"name", "jira_team_ids"}, ligne)
        nom = lecteur.texte(bloc["name"], f"{chemin}.name", bloc.lignes["name"])
        if nom in noms:
            lecteur.refuser(f"un libellé est décrit deux fois : « {noms[nom][0]}.name » et « {chemin}.name » "
                            f"(L{noms[nom][1]} et L{bloc.lignes['name']}).")
        noms[nom] = (chemin, bloc.lignes["name"])
        identifiants = lecteur.identifiants(bloc, chemin)
        for identifiant in dict.fromkeys(identifiants):
            if identifiant in ids:
                lecteur.refuser("un identifiant d'équipe Jira est listé sous deux entrées : « "
                                f"{ids[identifiant][0]}.jira_team_ids » (L{ids[identifiant][1]}) et « {chemin}.jira_team_ids » "
                                f"(L{bloc.lignes['jira_team_ids']}).")
            ids[identifiant] = (chemin, bloc.lignes["jira_team_ids"])
        type_ = None
        if "type" in bloc:
            if bloc["type"] in TYPES_EQUIPE:
                type_ = bloc["type"]
            else:
                types_refuses.append(f"« {chemin}.type » (L{bloc.lignes['type']})")
        obsolete = bloc.get("obsolete", False)
        if not isinstance(obsolete, bool):
            lecteur.refuser(f"« {chemin}.obsolete » (L{bloc.lignes['obsolete']}) doit être true ou false.")
        entrees.append(EntreeCatalogue(nom, tuple(dict.fromkeys(identifiants)), type_, obsolete, chemin, bloc.lignes["name"]))
    if types_refuses:
        lecteur.refuser(PHRASE_TYPE[lecteur.language].format(paths=" ; ".join(types_refuses)))
    return Catalogue(tuple(entrees))


def charger_catalogue_si_present(chemin, language: str = "fr") -> Catalogue:
    """Catalogue du fichier donné ; un fichier absent est lu comme un catalogue vide. Un fichier présent mais refusé lève `ErreurConfig`."""
    chemin = Path(chemin)
    if not chemin.is_file():
        return Catalogue()
    return charger_catalogue(chemin.read_text(encoding="utf-8"), chemin.name, language)


# ---------------------------------------------------------------------------
# Liste de revue des entrées extérieures (change names-and-team-review, design D4) : Flux-Lab/equipes-revues.yaml, hors Git
# ---------------------------------------------------------------------------

CLES_REVUE_RACINE = {"reviewed_ids"}
IDENTIFIANT_REVUE = re.compile(r"[0-9A-Za-z_-]+")


def charger_revue(texte: str, source: str = "equipes-revues.yaml", language: str = "fr") -> tuple[str, ...]:
    """Identifiants de la liste de revue d'un texte YAML (`reviewed_ids: [identifiant, ...]`, rien d'autre) : lecture stricte, refus
    (code 1) avec chemin de clé et ligne, jamais une valeur ni un nom de clé inconnu (un libellé pourrait s'y trouver) : clé inconnue,
    valeur qui n'est pas un identifiant, identifiant en double."""
    try:
        document = charger_strict(texte, source)
    except yaml.YAMLError as erreur:
        repere = getattr(erreur, "problem_mark", None)
        ou = f" (L{repere.line + 1})" if repere is not None else ""
        raise ErreurConfig(f"{source} : YAML illisible{ou} ; corriger la syntaxe du fichier.") from None
    lecteur = _Lecteur(source, language, "la liste de revue")
    if not isinstance(document, DictLignes):
        lecteur.refuser("le fichier doit être un bloc de clés (structure attendue : reviewed_ids).")
    for cle in document:
        if cle not in CLES_REVUE_RACINE:
            lecteur.refuser(f"clé inconnue (L{document.lignes.get(cle, 1)}) ; la liste de revue n'accepte que la clé « reviewed_ids ».")
    if "reviewed_ids" not in document:
        lecteur.refuser("clé obligatoire absente : « reviewed_ids » (bloc commençant L1).")
    if document["reviewed_ids"] is None:
        return ()
    ligne = document.lignes["reviewed_ids"]
    vus, resultat = set(), []
    for i, valeur in enumerate(lecteur.liste(document, "reviewed_ids", "")):
        if (isinstance(valeur, bool) or not isinstance(valeur, (str, int)) or not IDENTIFIANT_REVUE.fullmatch(str(valeur))):
            lecteur.refuser(f"« reviewed_ids[{i}] » (L{ligne}) doit être un identifiant (texte ou entier sans espace).")
        identifiant = str(valeur)
        if identifiant in vus:
            lecteur.refuser(f"« reviewed_ids[{i}] » (L{ligne}) est un identifiant en double.")
        vus.add(identifiant)
        resultat.append(identifiant)
    return tuple(resultat)


def charger_revue_si_present(chemin, language: str = "fr") -> tuple[str, ...]:
    """Identifiants du fichier donné ; un fichier absent est lu comme une liste vide. Un fichier présent mais refusé lève `ErreurConfig`."""
    chemin = Path(chemin)
    if not chemin.is_file():
        return ()
    return charger_revue(chemin.read_text(encoding="utf-8"), chemin.name, language)


def verifier_sources(referentiel: Referentiel, catalogue: Catalogue, language: str = "fr") -> None:
    """Règle entre les deux fichiers (design D1) : un identifiant dans les deux est accepté ; une entrée du catalogue nommée comme
    une équipe du référentiel qui porte un identifiant qu'aucune équipe du référentiel ne liste est refusée (code 1, les deux
    chemins et lignes, ni nom ni identifiant)."""
    refus = []
    for entree in catalogue.entrees:
        equipe = referentiel.teams.get(entree.nom)
        if equipe is not None and any(referentiel.team_for_jira_id(i) is None for i in entree.jira_ids):
            ref = "referential" if language == "en" else "référentiel"
            refus.append(f"catalogue « {entree.chemin}.name » (L{entree.ligne}) / {ref} « {equipe.chemin}.name » "
                         f"(L{equipe.ligne})")
    if refus:
        raise ErreurConfig(PHRASE_NOMME_COMME["en" if language == "en" else "fr"].format(paths=" ; ".join(refus)))


def nom_traduit(identifiant, referentiel: Referentiel | None, catalogue: Catalogue | None) -> str | None:
    """Nom d'un identifiant : celui de l'équipe du référentiel qui le liste, sinon le libellé du catalogue, sinon None."""
    if referentiel is not None:
        nom = referentiel.team_for_jira_id(identifiant)
        if nom is not None:
            return nom
    entree = catalogue.entree_pour(identifiant) if catalogue is not None else None
    return entree.nom if entree is not None else None


# ---------------------------------------------------------------------------
# Type d'une équipe du référentiel (design Q5, point 2) : forcé, sinon déduit du catalogue, sinon aucun
# ---------------------------------------------------------------------------

def _types_du_catalogue(equipe: Equipe, catalogue: Catalogue) -> set[str]:
    """Types que le catalogue donne aux identifiants de l'équipe (une entrée sans type ne dit rien)."""
    entrees = (catalogue.entree_pour(i) for i in equipe.jira_ids)
    return {e.type for e in entrees if e is not None and e.type}


def type_deduit(equipe: Equipe, catalogue: Catalogue) -> str | None:
    """Type commun aux identifiants de l'équipe dans le catalogue ; None si aucun n'y est, ou si les types diffèrent."""
    types = _types_du_catalogue(equipe, catalogue)
    return next(iter(types)) if len(types) == 1 else None


def types_differents(equipe: Equipe, catalogue: Catalogue) -> bool:
    """Vrai si les identifiants de l'équipe ont au moins deux types différents dans le catalogue."""
    return len(_types_du_catalogue(equipe, catalogue)) > 1


def type_effectif(equipe: Equipe, catalogue: Catalogue) -> str | None:
    """Type forcé (clé `type` du référentiel), sinon type déduit du catalogue, sinon None. Jamais tiré du nom."""
    return equipe.type or type_deduit(equipe, catalogue)
