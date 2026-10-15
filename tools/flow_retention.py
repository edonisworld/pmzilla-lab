# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "psycopg[binary]"]
# ///
"""
PMZilla Lab : contrôle et purge de la règle de conservation d'un an des données de flux (change jira-gdpr-alignment, groupe 11).

    uv run tools/flow_retention.py check [--language fr|en]
    uv run tools/flow_retention.py purge [--apply] [--language fr|en]

À lancer par l'utilisateur seul, dans le Terminal (refusé dans une session Claude Code : règles deny et variable CLAUDECODE, sans
option de contournement). Horloge d'un ticket (design D1) : date de résolution s'il est résolu ; sinon, instant de sortie de l'export
(flow.issues.out_of_export_at) ; un ticket ouvert encore dans l'export n'a pas d'horloge et n'est jamais hors règle. Une entrée du
cache d'historique a la même horloge : `resolu` si `termine`, sinon `vu_le` ; sans date, jamais hors règle.

Magasins lus : dossier des exports (CSV), fichiers de points `points-*.json` (dossier des tableaux), cache d'historique, base (rôle
d'import, schéma flow), sauvegardes locales (dossiers db-AAAA-MM-JJ-<étiquette>), ligne `flux` du fichier d'état de la copie hors
site. Un CSV est jugé sur son EN-TÊTE seulement (jamais une ligne de données). Hors règle : un CSV ou un fichier de points plus vieux
que l'âge maximal de fichier (date du fichier) ; un CSV dont l'en-tête nomme une colonne interdite, quel que soit son âge ; une entrée
de cache ou un ticket de la base au-delà de la durée de conservation ; une sauvegarde étiquetée dont le dump flow a plus que la durée de
vie ; des copies hors site dont le dump flux est trop vieux (compte rendu par offsite_backup.sh). Jamais comptés ni supprimés : les
rapports agrégés, les pages tableau-flux-*.html, anonymes.yaml, les sauvegardes datées simples, les copies hors site.

`check` ne supprime rien : code 0 si tout est à zéro, 4 sinon. `purge` sans --apply est un essai (mêmes comptes, la ligne de total du
contrôle, puis « essai : rien n'est supprimé », code 0 quel que soit le compte). `purge --apply` exige un dossier db-AAAA-MM-JJ-<étiquette>
DU JOUR (étiquette du réglage retention.backup_label) : sinon refus, code 3. Ordre : fichiers CSV et de points, entrées du cache (réécrit en
0600), tickets de la base en UNE transaction (annulée en cas d'échec : code 1, nom du type d'erreur seul), dump flow des sauvegardes
étiquetées trop vieilles (les dumps knowledge et cases restent).

Codes : 0 fait ou rien hors règle ; 1 erreur ; 2 usage (langue comprise) ; 3 prérequis refusé (session Claude Code, réglage de durée au-delà
d'un an, réglages invalides, sauvegarde étiquetée du jour absente) ; 4 le contrôle a trouvé des éléments hors règle.

La sortie ne porte que des noms de magasins, des effectifs, des âges en jours et les phrases clés : jamais une clé, une équipe, un nom de
fichier, une étiquette, une version ni une valeur de réglage. Une erreur est réduite au nom de son type.

Emplacements (variables d'environnement, pour les tests et le réglage ; par défaut ceux de Flux-Lab) : FLOW_RETENTION_SETTINGS (flux.yaml),
FLOW_RETENTION_EXPORTS, FLOW_RETENTION_TABLEAUX, FLOW_RETENTION_RAPPORTS (ne sert qu'à y trouver des CSV et des points-*.json),
FLOW_RETENTION_HISTORIQUE (cache), FLOW_RETENTION_SAUVEGARDES (défaut ~/.pmzilla-lab/sauvegardes), FLOW_RETENTION_STATUT (défaut
~/.pmzilla-lab/offsite/statut), FLOW_RETENTION_TODAY (AAAA-MM-JJ). Base : db.connect() puis SET ROLE pmzilla_flow, comme flow_import.py.

Exemple :
    uv run tools/flow_retention.py check
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db                                                  # noqa: E402
import flux_config as cfg                                  # noqa: E402
import history_common as commun                            # noqa: E402
import yaml                                                # noqa: E402
from flow_retention_messages import CATALOGS               # noqa: E402
from messages import LANGUAGES, Messages                   # noqa: E402
from yaml_strict import ErreurConfig, charger              # noqa: E402

ROLE = "pmzilla_flow"
VARIABLE_CLAUDE_CODE = "CLAUDECODE"
COLONNES_INTERDITES = {"summary", "title", "résumé", "resume", "description", "creator", "reporter", "assignee", "comment",
                       "comments", "labels"}             # « Declared Label » (export de l'API) n'est pas interdit
DOSSIER_SAUVEGARDE = re.compile(r"^db-(\d{4}-\d{2}-\d{2})-([a-z0-9]+)$")
LIGNE_FLUX = re.compile(r"^flux\s+copies_flux_anciennes=(\d+)\s+age_jours=(\d+)\b")
DUMP_FLUX = "flow.dump"

# Ticket hors règle : horloge = résolution, sinon sortie de l'export ; comparée en date UTC à la date limite.
SQL_COMPTE = """
SELECT count(*), min(horloge) FROM (
    SELECT (coalesce(resolved_at, out_of_export_at) AT TIME ZONE 'UTC')::date AS horloge
    FROM flow.issues WHERE resolved_at IS NOT NULL OR out_of_export_at IS NOT NULL) c
WHERE horloge < %s
"""
# Les équipes d'un ticket, ses transitions, liens et périodes partent en cascade (ON DELETE CASCADE).
SQL_SUPPRESSION = """
DELETE FROM flow.issues
WHERE (coalesce(resolved_at, out_of_export_at) AT TIME ZONE 'UTC')::date < %s
  AND (resolved_at IS NOT NULL OR out_of_export_at IS NOT NULL)
"""


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


@dataclass
class Emplacements:
    reglages: Path
    exports: Path
    tableaux: Path
    rapports: Path
    historique: Path
    sauvegardes: Path
    statut: Path


def emplacements(environ) -> Emplacements:
    atelier = Path(environ.get("PMZILLA_LAB_WORKSPACE", "~/PMZilla-Lab/workspace")).expanduser() / "Flux-Lab"
    donnees = Path("~/.pmzilla-lab").expanduser()

    def lire(variable: str, defaut: Path) -> Path:
        return Path(environ[variable]).expanduser() if environ.get(variable) else defaut

    return Emplacements(
        reglages=lire("FLOW_RETENTION_SETTINGS", atelier / "flux.yaml"), exports=lire("FLOW_RETENTION_EXPORTS", atelier / "exports"),
        tableaux=lire("FLOW_RETENTION_TABLEAUX", atelier / "tableaux"), rapports=lire("FLOW_RETENTION_RAPPORTS", atelier / "rapports"),
        historique=lire("FLOW_RETENTION_HISTORIQUE", atelier / "historique" / "transitions.json"),
        sauvegardes=lire("FLOW_RETENTION_SAUVEGARDES", donnees / "sauvegardes"),
        statut=lire("FLOW_RETENTION_STATUT", donnees / "offsite" / "statut"))


# ---------------------------------------------------------------------------------------------------------------------------------
# Réglages : la durée au-delà d'un an est refusée avant toute autre lecture et avant la validation du reste du fichier
# ---------------------------------------------------------------------------------------------------------------------------------

def lire_reglages(chemin: Path) -> dict:
    """Réglages de conservation (flux_config.retention). Lève Prerequis. Un fichier absent donne les défauts."""
    try:
        texte = chemin.read_text(encoding="utf-8")
    except FileNotFoundError:
        return cfg.retention({})
    except (OSError, UnicodeDecodeError):
        raise Prerequis("settings_unreadable") from None
    try:
        brut = charger(texte, "flux.yaml")
    except ErreurConfig as erreur:
        raise Prerequis("settings_refused", what=erreur.message) from None
    except yaml.YAMLError:
        raise Prerequis("settings_unreadable") from None
    if brut is not None and not isinstance(brut, dict):
        raise Prerequis("settings_unreadable")
    bloc = (brut or {}).get("retention")
    duree = bloc.get("period_days") if isinstance(bloc, dict) else None
    if isinstance(duree, int) and not isinstance(duree, bool) and duree > cfg.PERIODE_MAX_JOURS:
        raise Prerequis("period_above_year")                   # avant la validation du reste, et sans la valeur
    try:
        interne = cfg.to_internal(brut, "flux.yaml")
        cfg.retention_days(interne)
    except ErreurConfig as erreur:
        raise Prerequis("settings_refused", what=erreur.message) from None
    return cfg.retention(interne)


# ---------------------------------------------------------------------------------------------------------------------------------
# Analyse des magasins : comptes et âges seulement, aucun nom n'est gardé pour l'affichage
# ---------------------------------------------------------------------------------------------------------------------------------

@dataclass
class Magasin:
    n: int = 0
    plus_ancien: int | None = None                              # âge en jours du plus ancien élément
    cibles: list = field(default_factory=list)                  # chemins ou clés à supprimer (jamais affichés)

    def ajouter(self, age: int | None, cible=None) -> None:
        self.n += 1
        if age is not None and (self.plus_ancien is None or age > self.plus_ancien):
            self.plus_ancien = age
        if cible is not None:
            self.cibles.append(cible)


@dataclass
class Analyse:
    base: Magasin = field(default_factory=Magasin)
    cache: Magasin = field(default_factory=Magasin)
    csv: Magasin = field(default_factory=Magasin)
    points: Magasin = field(default_factory=Magasin)
    interdits: Magasin = field(default_factory=Magasin)
    sauvegardes: Magasin = field(default_factory=Magasin)
    hors_site: Magasin = field(default_factory=Magasin)

    def total(self) -> int:
        return sum(m.n for m in (self.base, self.cache, self.csv, self.points, self.interdits, self.sauvegardes, self.hors_site))


def _age_fichier(chemin: Path, aujourdhui: dt.date) -> int:
    return (aujourdhui - dt.date.fromtimestamp(chemin.stat().st_mtime)).days


def colonne_interdite(chemin: Path) -> bool:
    """Vrai si l'EN-TÊTE du CSV nomme une colonne interdite. Seule la première ligne est lue (jamais une ligne de données)."""
    with chemin.open(encoding="utf-8-sig", errors="replace", newline="") as source:
        entete = next(csv.reader(source), [])
    return any(nom.strip().casefold() in COLONNES_INTERDITES for nom in entete)


def _fichiers(dossier: Path, motif: str) -> list[Path]:
    if not dossier.is_dir():
        return []
    return sorted(p for p in dossier.glob(motif) if p.is_file() and not p.is_symlink())


def analyser_fichiers(lieux: Emplacements, reglages: dict, aujourdhui: dt.date, analyse: Analyse) -> None:
    """Exports CSV (et CSV du dossier des rapports) et fichiers de points (dossiers des tableaux et des rapports)."""
    age_max = reglages["max_file_age_days"]
    vus: set[Path] = set()
    for dossier in (lieux.exports, lieux.rapports):
        for chemin in _fichiers(dossier, "*"):
            if chemin.suffix.lower() != ".csv" or chemin in vus:
                continue
            vus.add(chemin)
            age = _age_fichier(chemin, aujourdhui)
            if colonne_interdite(chemin):                       # supprimé quel que soit son âge ; compté une seule fois
                analyse.interdits.ajouter(age, chemin)
            elif age > age_max:
                analyse.csv.ajouter(age, chemin)
    for dossier in (lieux.tableaux, lieux.rapports):
        for chemin in _fichiers(dossier, "points-*.json"):
            if chemin in vus:
                continue
            vus.add(chemin)
            age = _age_fichier(chemin, aujourdhui)
            if age > age_max:
                analyse.points.ajouter(age, chemin)


def analyser_cache(chemin: Path, duree: int, aujourdhui: dt.date, analyse: Analyse) -> None:
    """Entrées du cache au-delà de la règle : horloge `resolu` si `termine`, sinon `vu_le` ; sans date, jamais hors règle."""
    if not chemin.is_file():
        return
    try:
        cache = commun.lire_cache(chemin)
    except commun.CacheIllisible:
        raise OSError("cache illisible") from None
    for cle, entree in cache.items():
        jour = commun.date_calendaire(entree["resolu"] if entree["termine"] else entree["vu_le"])
        if jour is not None and (aujourdhui - jour).days > duree:
            analyse.cache.ajouter((aujourdhui - jour).days, cle)


def analyser_sauvegardes(dossier: Path, vie: int, aujourdhui: dt.date, analyse: Analyse) -> None:
    """Sauvegardes étiquetées (db-AAAA-MM-JJ-<étiquette>, quelle que soit l'étiquette) dont le dump flow a plus que la durée de vie."""
    if not dossier.is_dir():
        return
    for sous in sorted(dossier.iterdir()):
        trouve = DOSSIER_SAUVEGARDE.match(sous.name)
        if not trouve or not sous.is_dir() or not (sous / DUMP_FLUX).is_file():
            continue
        try:
            age = (aujourdhui - dt.date.fromisoformat(trouve[1])).days
        except ValueError:
            continue
        if age > vie:
            analyse.sauvegardes.ajouter(age, sous / DUMP_FLUX)


def lire_hors_site(chemin: Path, analyse: Analyse) -> int | None:
    """Ligne `flux` du fichier d'état de offsite_backup.sh : copies avec un dump flux trop vieux. Rend l'âge configuré à la copie."""
    try:
        lignes = chemin.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, NotADirectoryError):
        return None
    for ligne in lignes:
        trouve = LIGNE_FLUX.match(ligne)
        if trouve:
            analyse.hors_site.n = int(trouve[1])
            return int(trouve[2])
    return None


def sauvegarde_du_jour(dossier: Path, etiquette: str, aujourdhui: dt.date) -> bool:
    return (dossier / f"db-{aujourdhui.isoformat()}-{etiquette}").is_dir()


# --- base : fonctions séparées, essayées avec une fausse connexion -------------------------------------------------------------

def ouvrir_base_import():
    """Connexion sous le rôle d'import (comme flow_import.py : connexion de l'exécuteur, puis SET ROLE)."""
    conn = db.connect()
    conn.cursor().execute(f"SET ROLE {ROLE}")
    return conn


def compter_base(conn, limite: dt.date) -> tuple[int, dt.date | None]:
    """(nombre de tickets au-delà de la règle, date de l'horloge du plus ancien). `limite` : date de l'horloge au plus tard exclue."""
    cur = conn.cursor()
    cur.execute(SQL_COMPTE, (limite,))
    n, plus_ancien = cur.fetchone()
    return int(n), plus_ancien


def supprimer_base(conn, limite: dt.date) -> int:
    """Supprime les tickets au-delà de la règle en UNE transaction ; l'échec l'annule (rollback) et relève l'erreur."""
    cur = conn.cursor()
    try:
        cur.execute(SQL_SUPPRESSION, (limite,))
        supprimes = cur.rowcount
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return supprimes


# ---------------------------------------------------------------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------------------------------------------------------------

def reecrire_cache(chemin: Path, cles: list[str]) -> None:
    """Retire les entrées du cache et réécrit le fichier en 0600 (écriture dans un fichier voisin, puis remplacement)."""
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    for cle in cles:
        donnees.pop(cle, None)
    temporaire = chemin.with_name(chemin.name + ".tmp")
    descripteur = os.open(temporaire, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descripteur, "w", encoding="utf-8") as sortie:
        json.dump(donnees, sortie, ensure_ascii=False)
    os.chmod(temporaire, 0o600)
    os.replace(temporaire, chemin)


def supprimer(analyse: Analyse, lieux: Emplacements, conn, limite: dt.date) -> None:
    """Ordre fixé par la spécification : fichiers, cache, base (une transaction), dump flow des sauvegardes étiquetées."""
    for magasin in (analyse.interdits, analyse.csv, analyse.points):
        for chemin in magasin.cibles:
            chemin.unlink(missing_ok=True)
    if analyse.cache.cibles:
        reecrire_cache(lieux.historique, analyse.cache.cibles)
    if analyse.base.n:
        supprimer_base(conn, limite)
    for chemin in analyse.sauvegardes.cibles:
        chemin.unlink(missing_ok=True)


# ---------------------------------------------------------------------------------------------------------------------------------
# Sortie
# ---------------------------------------------------------------------------------------------------------------------------------

def ligne_magasin(t: Messages, cle: str, magasin: Magasin, suffixe: str = "") -> str:
    texte = t(cle, n=magasin.n)
    if magasin.n and magasin.plus_ancien is not None:
        texte += t("oldest", days=magasin.plus_ancien)
    return texte + suffixe


def afficher_comptes(analyse: Analyse, age_hors_site: int | None, t: Messages) -> None:
    print(ligne_magasin(t, "store_database", analyse.base))
    print(ligne_magasin(t, "store_cache", analyse.cache))
    print(ligne_magasin(t, "store_csv", analyse.csv))
    print(ligne_magasin(t, "store_points", analyse.points))
    print(t("forbidden", n=analyse.interdits.n))
    print(ligne_magasin(t, "store_backups", analyse.sauvegardes))
    suffixe = t("offsite_age", days=age_hors_site) if analyse.hors_site.n and age_hors_site is not None else ""
    print(ligne_magasin(t, "store_offsite", analyse.hors_site, suffixe))


def ligne_total(analyse: Analyse, t: Messages) -> str:
    return t("check_found", n=analyse.total()) if analyse.total() else t("check_clean")


# ---------------------------------------------------------------------------------------------------------------------------------
# Programme
# ---------------------------------------------------------------------------------------------------------------------------------

def lire_arguments(argv: list[str]):
    analyseur = Analyseur(prog="flow_retention.py")     # --help : usage et code 0, sans rien lire
    analyseur.add_argument("--language", default="fr")
    sous = analyseur.add_subparsers(dest="commande", required=True, parser_class=Analyseur)
    for nom in ("check", "purge"):
        commande = sous.add_parser(nom, add_help=False)
        commande.add_argument("--language", default=argparse.SUPPRESS)
        if nom == "purge":
            commande.add_argument("--apply", action="store_true")
    return analyseur.parse_args(argv)


def main(argv: list[str] | None = None, environ=None, ouvrir_base=None) -> int:
    """Rend le code de sortie. `environ` et `ouvrir_base` sont remplaçables pour les tests."""
    environ = os.environ if environ is None else environ
    ouvrir_base = ouvrir_base or ouvrir_base_import
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
    lieux = emplacements(environ)
    try:
        reglages = lire_reglages(lieux.reglages)
    except Prerequis as refus:
        print(t(refus.cle, **refus.valeurs))
        return 3
    appliquer = args.commande == "purge" and args.apply
    try:
        aujourdhui = dt.date.fromisoformat(environ["FLOW_RETENTION_TODAY"]) if environ.get("FLOW_RETENTION_TODAY") else dt.date.today()
    except ValueError:
        print(t("usage"), file=sys.stderr)
        return 2
    if appliquer and not sauvegarde_du_jour(lieux.sauvegardes, reglages["backup_label"], aujourdhui):
        print(t("backup_missing"))
        return 3
    duree = reglages["period_days"]
    limite = aujourdhui - dt.timedelta(days=duree)
    analyse = Analyse()
    conn = None
    try:
        analyser_fichiers(lieux, reglages, aujourdhui, analyse)
        analyser_cache(lieux.historique, duree, aujourdhui, analyse)
        analyser_sauvegardes(lieux.sauvegardes, reglages["labelled_backup_days"], aujourdhui, analyse)
        age_hors_site = lire_hors_site(lieux.statut, analyse)
        conn = ouvrir_base()
        analyse.base.n, plus_ancien = compter_base(conn, limite)
        if plus_ancien is not None:
            analyse.base.plus_ancien = (aujourdhui - plus_ancien).days
        afficher_comptes(analyse, age_hors_site, t)
        print(ligne_total(analyse, t))
        if args.commande == "check":
            return 4 if analyse.total() else 0
        if not appliquer:
            print(t("dry_run"))
            return 0
        supprimer(analyse, lieux, conn, limite)
        print(t("purge_done"))
        return 0
    except Exception as erreur:                                 # aucun détail : un message pourrait citer une clé ou un nom de fichier
        print(t("error", name=type(erreur).__name__), file=sys.stderr)
        return 1
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
