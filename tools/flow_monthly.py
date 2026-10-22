# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
PMZilla Lab : suivi mensuel du flux en une commande (change monthly-flow-orchestrator, job R-48).

    uv run tools/flow_monthly.py [--dry-run] [--from ETAPE] [--date AAAA-MM-JJ] [--force] [--verbose] [--language fr|en] [--open]

À lancer par l'utilisateur seul, dans le Terminal (refusé dans une session Claude Code : règles deny et variable CLAUDECODE).

Enchaîne les outils existants dans un ordre fixe et s'arrête au premier écart (change database-only, D8) :
    export, import, history, flow (par série), dependencies (par série), dashboard,
    retention (essai à blanc de la purge, sans --apply : il n'efface rien et n'ouvre aucun magasin).
Il n'ajoute aucun calcul : il passe des options, aucun chemin de fichier, les outils ouvrent la base. Il lit seulement Flux-Lab/flux.yaml
(bloc monthly_run : séries à calculer) et Flux-Lab/rapports/ ; jamais les exports, l'historique, les tableaux, la table des équipes
ni la liste des noms sensibles, et il ne se connecte pas à la base. Sa sortie et son résumé (Flux-Lab/rapports/suivi-mensuel-AAAA-MM-JJ.md)
ne portent que des identifiants d'étape, des rangs de série, des effectifs, des codes de sortie et des durées.

Codes de sortie : 0 terminé ; 1 une étape a échoué (tout code de sortie non nul d'un outil) ; 2 usage (une étape inconnue, dont les
anciennes compare-data et compare-reports) ; 3 prérequis refusé (réglages, bloc monthly_run, session Claude Code) ; 5 suivi du mois déjà
fait (--force pour relancer). Les codes 4 (écart de parité) et 6 (entrée manquante) sont retirés et jamais réutilisés.

Une reprise (--from une étape autre que export) sans --date reprend la date de la série en cours, lue dans les résumés du mois
(change flow-monthly-resume) ; sans série décidable, elle est refusée (code 2) et propose --date. Une date qui a déjà un résumé
prévient que ses rapports seront réécrits.

Pour les tests seulement, deux variables d'environnement remplacent la racine et le lanceur (FLOW_MONTHLY_ROOT, FLOW_MONTHLY_LAUNCHER) ;
les règles deny les couvrent. Aucun module de base de données n'est importé, aucune entrée du Trousseau n'est lue.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yaml                                                    # noqa: E402
from flow_monthly_messages import CATALOGS                     # noqa: E402
from messages import Messages                                  # noqa: E402
from yaml_strict import ErreurConfig, charger                  # noqa: E402

ETAPES = ("export", "import", "history", "flow", "dependencies", "dashboard", "retention")
SUFFIXE_BASE = "-db"             # réservé depuis la comparaison des séries (retirée) : le refus d'un nom en « -db » est gardé
DOSSIER_FLUX = "Flux-Lab"
RESUME = "suivi-mensuel-{jour}.md"
MOTIF_RESUME = re.compile(r"^suivi-mensuel-(\d{4}-\d{2}-\d{2})\.md$")
MOTIF_NOM = re.compile(r"^[A-Za-z0-9_-]+$")
DEPENDANCES = ("team", "project", "both", "none")
TABLEAUX = ("full", "anonymous", "both")
VARIABLE_CLAUDE_CODE = "CLAUDECODE"
# Ligne de total de l'essai de purge, dans la langue du run (D19) : « rien hors règle » compte pour 0.
TOTAL_RETENTION = {
    "fr": re.compile(r"^contrôle de conservation : (?:rien hors règle|(\d+) éléments hors règle)\s*$", re.M),
    "en": re.compile(r"^retention check: (?:nothing out of rule|(\d+) items out of rule)\s*$", re.M),
}
LIGNE_RESUME = re.compile(r"^\| ([a-z-]+) \| (-|\d+) \| (passed|failed|gap|skipped|not run) \| (-|\d+) \| (-|\d+) \|$")


class Usage(Exception):
    """Erreur d'usage : `cle` est la clé du libellé fixe dans le catalogue."""
    def __init__(self, cle: str):
        super().__init__(cle)
        self.cle = cle


class Prerequis(Exception):
    """Prérequis refusé avant toute étape : `quoi` est un libellé fixe (jamais une valeur)."""
    def __init__(self, quoi: str):
        super().__init__(quoi)
        self.quoi = quoi


class Analyseur(argparse.ArgumentParser):
    def error(self, message):                                  # le message d'argparse peut citer ce que l'utilisateur a tapé
        raise Usage("u_option")


# ---------------------------------------------------------------------------------------------------------------------------------
# Réglages : Flux-Lab/flux.yaml, bloc monthly_run
# ---------------------------------------------------------------------------------------------------------------------------------

@dataclass
class Serie:
    nom: str
    perimetre: str | None
    dependances: str


@dataclass
class Reglages:
    requetes: list[str | None]
    series: list[Serie]
    tableaux: str


def _refus(t: Messages, raison: str, chemin: str, ligne: int | None) -> Prerequis:
    return Prerequis(t("p_block", reason=t(raison), where=f"{chemin} (L{ligne})" if ligne else chemin))


def _ligne_min(contenu) -> int | None:
    lignes = getattr(contenu, "lignes", None)
    return min(lignes.values()) if lignes else None


def lire_reglages(racine: Path, t: Messages) -> Reglages:
    chemin = racine / DOSSIER_FLUX / "flux.yaml"
    try:
        texte = chemin.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise Prerequis(t("p_settings_missing")) from None
    except (OSError, UnicodeDecodeError):
        raise Prerequis(t("p_settings_unreadable")) from None
    try:
        brut = charger(texte, "flux.yaml")
    except ErreurConfig as erreur:
        m = re.search(r"« (.+?) » est écrite deux fois \(L(\d+) et L(\d+)\)", erreur.message)
        raise Prerequis(t("p_settings_twice", path=m[1], first=m[2], second=m[3]) if m else t("p_settings_unreadable")) from None
    except yaml.YAMLError:
        raise Prerequis(t("p_settings_unreadable")) from None
    if not isinstance(brut, dict):
        raise Prerequis(t("p_settings_unreadable"))
    requetes = _requetes(brut, t)
    series, tableaux = _bloc(brut, t)
    return Reglages(requetes, series, tableaux)


def _requetes(brut: dict, t: Messages) -> list[str | None]:
    nommees = brut.get("jql_exports")
    if nommees:
        if not isinstance(nommees, dict) or not all(MOTIF_NOM.match(str(n)) for n in nommees):
            raise Prerequis(t("p_query"))
        return [str(n) for n in nommees]
    if not str(brut.get("jql_export") or "").strip():
        raise Prerequis(t("p_query"))
    return [None]


def _bloc(brut: dict, t: Messages) -> tuple[list[Serie], str]:
    lignes = getattr(brut, "lignes", {})
    if "monthly_run" not in brut:
        raise Prerequis(t("p_block_missing"))
    bloc = brut["monthly_run"]
    ligne_bloc = lignes.get("monthly_run")
    if not isinstance(bloc, dict):
        raise _refus(t, "r_invalid_block", "monthly_run", ligne_bloc)
    lignes_bloc = getattr(bloc, "lignes", {})
    for cle in bloc:
        if cle not in ("series", "dashboard"):
            raise _refus(t, "r_unknown_key", f"monthly_run.{cle}", lignes_bloc.get(cle))
    liste = bloc.get("series")
    if not isinstance(liste, list) or not liste:
        raise _refus(t, "r_empty_series", "monthly_run.series", lignes_bloc.get("series", ligne_bloc))
    series: list[Serie] = []
    for rang, item in enumerate(liste, start=1):
        base = f"monthly_run.series[{rang}]"
        if not isinstance(item, dict):
            raise _refus(t, "r_invalid_value", base, lignes_bloc.get("series"))
        lignes_item = getattr(item, "lignes", {})
        for cle in item:
            if cle not in ("name", "scope", "dependencies"):
                raise _refus(t, "r_unknown_key", f"{base}.{cle}", lignes_item.get(cle))
        if "name" not in item or item["name"] is None or (isinstance(item["name"], str) and not item["name"].strip()):
            raise _refus(t, "r_name_missing", base, _ligne_min(item) or lignes_bloc.get("series"))
        nom = item["name"]
        if not isinstance(nom, str) or not MOTIF_NOM.match(nom):
            raise _refus(t, "r_invalid_value", f"{base}.name", lignes_item.get("name"))
        if nom.endswith(SUFFIXE_BASE):
            raise _refus(t, "r_reserved_suffix", f"{base}.name", lignes_item.get("name"))
        if any(nom == s.nom for s in series):
            raise _refus(t, "r_name_twice", f"{base}.name", lignes_item.get("name"))
        perimetre = item.get("scope")
        if "scope" in item and (not isinstance(perimetre, str) or not perimetre.strip()):
            raise _refus(t, "r_invalid_value", f"{base}.scope", lignes_item.get("scope"))
        dependances = item.get("dependencies", "team")
        if dependances not in DEPENDANCES:
            raise _refus(t, "r_invalid_value", f"{base}.dependencies", lignes_item.get("dependencies"))
        series.append(Serie(nom, perimetre.strip() if perimetre else None, dependances))
    tableaux = bloc.get("dashboard", "both")
    if tableaux not in TABLEAUX:
        raise _refus(t, "r_invalid_value", "monthly_run.dashboard", lignes_bloc.get("dashboard"))
    return series, tableaux


# ---------------------------------------------------------------------------------------------------------------------------------
# Plan : unités (étape, rang de série) et appels
# ---------------------------------------------------------------------------------------------------------------------------------

@dataclass
class Appel:
    outil: str
    args: list[str]
    montres: list[str]                 # les mêmes arguments avec des repères à la place de chaque valeur (passage à blanc)
    retention: bool = False           # sortie capturée, jamais affichée : seul le total est lu


@dataclass
class Unite:
    etape: str
    rang: int | None
    appels: list[Appel]


class Commande:
    def __init__(self, outil: str, retention: bool = False):
        self.outil, self.retention = outil, retention
        self.args: list[str] = []
        self.montres: list[str] = []

    def ajouter(self, *valeurs: str) -> "Commande":
        self.args += valeurs
        self.montres += valeurs
        return self

    def valeur(self, reel: str, montre: str) -> "Commande":
        self.args.append(reel)
        self.montres.append(montre)
        return self

    def appel(self) -> Appel:
        return Appel(self.outil, self.args, self.montres, self.retention)


def construire(reglages: Reglages, jour: str, langue: str, aujourdhui: str, ouvrir: bool, t: Messages) -> list[Unite]:
    """Plan de la décision D8 : aucun chemin de fichier n'est passé, les outils lisent et écrivent dans la base."""
    use_date = jour != aujourdhui

    def avec_perimetre(c: Commande, serie: Serie, k: int) -> Commande:
        return c.ajouter("--scope").valeur(serie.perimetre, t("ph_scope", k=k)) if serie.perimetre else c

    def date_option(c: Commande) -> Commande:
        return c.ajouter("--today").valeur(jour, t("ph_date")) if use_date else c

    unites = [
        Unite("export", None, [Commande("export_jira_api").ajouter("export", "--strict-teams", "--language", langue).appel()]),
        Unite("import", None, [Commande("flow_import").ajouter("--mark-absent", "--language", langue).appel()]),
        Unite("history", None, [Commande("history_jira").ajouter("collect", "--strict", "--language", langue).appel()]),
    ]
    for k, serie in enumerate(reglages.series, start=1):
        c = Commande("flux_jira").ajouter("compute").ajouter("--name").valeur(serie.nom, t("ph_series", k=k))
        c = avec_perimetre(c, serie, k).ajouter("--history", "--dormant-from-history", "--points", "--language", langue)
        unites.append(Unite("flow", k, [date_option(c).appel()]))
    for k, serie in enumerate(reglages.series, start=1):
        appels = []
        for carte in {"team": ("team",), "project": ("project",), "both": ("team", "project"), "none": ()}[serie.dependances]:
            c = Commande("dependencies_jira").ajouter("compute").ajouter("--name").valeur(serie.nom, t("ph_series", k=k))
            c = avec_perimetre(c, serie, k)
            if carte == "project":
                c.ajouter("--by", "project")
            appels.append(c.ajouter("--language", langue).appel())
        if appels:
            unites.append(Unite("dependencies", k, appels))
    tableaux = []
    for anonyme in {"full": (False,), "anonymous": (True,), "both": (False, True)}[reglages.tableaux]:
        c = Commande("flow_board").ajouter("--language", langue)
        if anonyme:
            c.ajouter("--anonymous")
        if ouvrir:
            c.ajouter("--open")
        tableaux.append(c.appel())
    unites.append(Unite("dashboard", None, tableaux))
    unites.append(Unite("retention", None, [Commande("flow_retention", True).ajouter("purge", "--language", langue).appel()]))
    return unites


# ---------------------------------------------------------------------------------------------------------------------------------
# Rapports : résumé du mois (seul dossier lu avec le fichier de réglages)
# ---------------------------------------------------------------------------------------------------------------------------------

@dataclass
class Ligne:
    etape: str
    rang: int | None
    statut: str = "not run"
    code: int | None = None
    secondes: int | None = None

    def texte(self) -> str:
        return (f"| {self.etape} | {self.rang or '-'} | {self.statut} | "
                f"{'-' if self.code is None else self.code} | {'-' if self.secondes is None else self.secondes} |")


def lister(dossier: Path) -> list[str]:
    try:
        return sorted(os.listdir(dossier))
    except OSError:
        return []


def mois_deja_fait(rapports: Path, aujourdhui: str) -> bool:
    for nom in lister(rapports):
        m = MOTIF_RESUME.match(nom)
        if m and m[1][:7] == aujourdhui[:7]:
            try:
                if re.search(r"^- final status: complete$", (rapports / nom).read_text(encoding="utf-8"), re.M):
                    return True
            except OSError:
                continue
    return False


MOTIF_STATUT_FINAL = re.compile(r"^- final status: (complete|stopped at [a-z-]+)$", re.M)


@dataclass
class ResultatSerie:
    genre: str                         # "date", "ambiguous" ou "none"
    dates: list[str]                   # une date pour "date", les dates en cours (ordre croissant) pour "ambiguous"


def date_de_serie(rapports: Path, aujourdhui: str) -> ResultatSerie:
    """Date de la série à reprendre (change flow-monthly-resume, D1). Fonction pure du dossier des rapports et de la date du jour :
    ni sortie ni effet. Candidats : les résumés du mois dont l'étape export est `passed` et dont le statut final se lit. C : le
    dernier candidat complet ; U : les candidats arrêtés datés après C (tous s'il n'y a pas de C). Une date dans U : elle ; deux ou
    plus : ambigu ; aucune : C s'il existe ; sinon aucune série. Ne rend jamais aujourd'hui sans candidat du jour."""
    candidats: list[tuple[str, bool]] = []
    for nom in lister(rapports):
        m = MOTIF_RESUME.match(nom)
        if not m or m[1][:7] != aujourdhui[:7] or m[1] > aujourdhui:
            continue
        try:
            texte = (rapports / nom).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        final = MOTIF_STATUT_FINAL.search(texte)
        export_reussi = any((l := LIGNE_RESUME.match(ligne)) and l[1] == "export" and l[3] == "passed" for ligne in texte.splitlines())
        if final and export_reussi:
            candidats.append((m[1], final[1] == "complete"))
    completes = [jour for jour, complet in candidats if complet]
    dernier_complet = completes[-1] if completes else None
    en_cours = [jour for jour, complet in candidats if not complet and (dernier_complet is None or jour > dernier_complet)]
    if len(en_cours) == 1:
        return ResultatSerie("date", en_cours)
    if len(en_cours) > 1:
        return ResultatSerie("ambiguous", en_cours)
    if dernier_complet:
        return ResultatSerie("date", [dernier_complet])
    return ResultatSerie("none", [])


def lire_resume(rapports: Path, jour: str) -> dict[tuple[str, int | None], Ligne]:
    try:
        texte = (rapports / RESUME.format(jour=jour)).read_text(encoding="utf-8")
    except OSError:
        return {}
    lignes = {}
    for ligne in texte.splitlines():
        m = LIGNE_RESUME.match(ligne)
        if m:
            rang = None if m[2] == "-" else int(m[2])
            lignes[(m[1], rang)] = Ligne(m[1], rang, m[3], None if m[4] == "-" else int(m[4]), None if m[5] == "-" else int(m[5]))
    return lignes


def statut_final(lignes: list[Ligne]) -> str:
    for ligne in lignes:
        if ligne.statut not in ("passed", "skipped"):
            return f"stopped at {ligne.etape}"
    return "complete"


def ecrire_resume(rapports: Path, jour: str, langue: str, requetes: int, series: int, lignes: list[Ligne],
                  sorties_d_erreur: int | None, retention: str | None = None) -> None:
    fichiers = sum(1 for n in lister(rapports) if n.endswith((f"-{jour}.md", f"-{jour}.json")) and not MOTIF_RESUME.match(n))
    corps = [f"# Monthly flow run {jour}", "", f"- run date: {jour}", f"- language: {langue}", f"- export queries: {requetes}",
             f"- series: {series}",
             f"- tools with error output on success: {'n/a (verbose)' if sorties_d_erreur is None else sorties_d_erreur}",
             f"- report files of the run date: {fichiers}", *([f"- {retention}"] if retention else []),
             f"- final status: {statut_final(lignes)}", "",
             "| step | series | status | exit code | seconds |", "|---|---|---|---|---|", *[l.texte() for l in lignes], ""]
    try:
        rapports.mkdir(parents=True, exist_ok=True)
        chemin = rapports / RESUME.format(jour=jour)
        chemin.write_text("\n".join(corps), encoding="utf-8")
        os.chmod(chemin, 0o600)
    except OSError:
        pass


# ---------------------------------------------------------------------------------------------------------------------------------
# Exécution
# ---------------------------------------------------------------------------------------------------------------------------------

def executer(appel: Appel, racine: Path, environ: dict, detaille: bool, sortie: list[str] | None = None) -> tuple[int, str]:
    """Lance un outil depuis la racine. (code, sortie d'erreur capturée). Silencieux : tout est capturé en mémoire, rien n'est écrit.
    Avec `sortie` (liste), la sortie standard est capturée dans la liste et jamais diffusée, même en mode détaillé."""
    lanceur = shlex.split(environ.get("FLOW_MONTHLY_LAUNCHER") or "uv run")
    commande = [*lanceur, f"tools/{appel.outil}.py", *appel.args]
    try:
        if detaille and sortie is None:
            with subprocess.Popen(commande, cwd=racine, env=dict(environ), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, errors="replace") as processus:
                for ligne in processus.stdout:
                    print(ligne, end="", flush=True)
                return processus.wait(), ""
        fait = subprocess.run(commande, cwd=racine, env=dict(environ), capture_output=True, text=True, errors="replace")
        if sortie is not None:
            sortie.append(fait.stdout)
        return fait.returncode, fait.stderr
    except OSError:
        return 127, ""


def langue_demandee(argv: list[str]) -> str:
    for i, argument in enumerate(argv[:-1]):
        if argument == "--language" and argv[i + 1] in ("fr", "en"):
            return argv[i + 1]
    return "fr"


def analyseur() -> Analyseur:
    p = Analyseur(prog="flow_monthly.py", allow_abbrev=False,
                  description="Monthly flow run in one command: export, import, history, flow and dependency calculations per series, "
                              "dashboards, retention dry run. Stops at the first gap. Run it in the Terminal.")
    p.add_argument("--dry-run", action="store_true", help="print the plan with placeholders and run nothing")
    p.add_argument("--from", dest="depuis", metavar="STEP", help="resume at this step: " + ", ".join(ETAPES))
    p.add_argument("--date", metavar="YYYY-MM-DD", help="run date of the report names (default: today)")
    p.add_argument("--force", action="store_true", help="run again even if this month's run is already complete")
    p.add_argument("--verbose", action="store_true", help="stream the tools' output (it can hold series, query or team names)")
    p.add_argument("--language", default="fr", metavar="{fr,en}", help="language of the messages and of the tools' output (default: fr)")
    p.add_argument("--open", action="store_true", help="open the dashboards in the browser")
    return p


def main(argv: list[str] | None = None, environ=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    environ = os.environ if environ is None else environ
    t = Messages(CATALOGS, langue_demandee(argv))
    try:
        args = analyseur().parse_args(argv)
    except Usage as erreur:
        print(t("usage_error", what=t(erreur.cle)))
        return 2
    except SystemExit as sortie:                                # --help
        return int(sortie.code or 0)
    try:
        return _executer(args, environ, t)
    except Usage as erreur:
        print(t("usage_error", what=t(erreur.cle)))
        return 2
    except Prerequis as erreur:
        print(t("prerequisite", what=erreur.quoi))
        return 3


def _executer(args: argparse.Namespace, environ, t: Messages) -> int:
    if args.language not in ("fr", "en"):
        raise Usage("u_language")
    t = Messages(CATALOGS, args.language)
    aujourdhui = dt.date.today()
    jour = aujourdhui.isoformat()
    if args.depuis is not None and args.depuis not in ETAPES:
        raise Usage("u_step")
    if args.date is not None:
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
                raise ValueError
            demande = dt.date.fromisoformat(args.date)
        except ValueError:
            raise Usage("u_date") from None
        if demande > aujourdhui:
            raise Usage("u_future")
        jour = demande.isoformat()
    if args.depuis == "export" and jour != aujourdhui.isoformat():
        raise Usage("u_export_date")
    if environ.get(VARIABLE_CLAUDE_CODE):                       # avant toute lecture : aucun fichier n'est ouvert
        print(t("under_claude_code"))
        return 3

    racine = Path(os.path.abspath(environ["FLOW_MONTHLY_ROOT"])) if environ.get("FLOW_MONTHLY_ROOT") else Path(__file__).resolve().parent.parent
    rapports = racine / DOSSIER_FLUX / "rapports"
    reglages = lire_reglages(racine, t)
    serie_decidee = args.depuis not in (None, "export") and args.date is None
    if serie_decidee:                                           # reprise sans --date : la date de la série en cours, jamais le jour
        resultat = date_de_serie(rapports, aujourdhui.isoformat())
        if resultat.genre == "ambiguous":
            print(t("series_ambiguous", dates=", ".join(resultat.dates)))
            return 2
        if resultat.genre == "none":
            print(t("series_none"))
            return 2
        jour = resultat.dates[0]
    if not args.force and mois_deja_fait(rapports, aujourdhui.isoformat()):
        print(t("already_done"))
        return 5
    if serie_decidee:
        print(t("series_date", date=jour), flush=True)
    reecriture = (serie_decidee or args.date is not None) and (rapports / RESUME.format(jour=jour)).exists()

    unites = construire(reglages, jour, args.language, aujourdhui.isoformat(), args.open, t)
    debut = next((i for i, u in enumerate(unites) if u.etape == args.depuis), 0) if args.depuis else 0
    if args.dry_run:
        for unite in unites[debut:]:
            for appel in unite.appels:
                print(t("dry_run", command=f"uv run tools/{appel.outil}.py " + " ".join(appel.montres)))
        return 0
    return _suivre(args, environ, t, racine, rapports, reglages, unites, debut, jour, aujourdhui.isoformat(), reecriture)


def _suivre(args, environ, t: Messages, racine: Path, rapports: Path, reglages: Reglages, unites: list[Unite], debut: int,
            jour: str, aujourdhui: str, reecriture: bool = False) -> int:
    precedentes = lire_resume(rapports, jour) if args.depuis else {}
    lignes = [Ligne(u.etape, u.rang) for u in unites]
    for i in range(debut):                                      # avant --from : le statut du résumé du jour, sinon « skipped »
        avant = precedentes.get((unites[i].etape, unites[i].rang))
        lignes[i] = avant if avant and avant.statut in ("passed", "skipped") else Ligne(unites[i].etape, unites[i].rang, "skipped")
    if args.verbose:
        print(t("verbose_warning"), flush=True)
    if reecriture:
        print(t("rewrite_warning", date=jour), flush=True)
    sorties_d_erreur = None if args.verbose else 0
    total = len(unites)
    a_faire = total - debut
    retention = None
    for i in range(debut, total):
        unite = unites[i]
        print(t("step_start_series" if unite.rang else "step_start", i=i - debut + 1, n=a_faire, step=unite.etape, k=unite.rang), flush=True)
        t0 = time.monotonic()
        code, erreur, appel = 0, "", None
        for appel in unite.appels:
            capture: list[str] | None = [] if appel.retention else None
            code, erreur = executer(appel, racine, environ, args.verbose, capture)
            if appel.retention and code == 0:
                trouve = TOTAL_RETENTION[args.language].search("".join(capture))
                if trouve is None:
                    code = 1                                     # sans ligne de total, aucun compte n'est deviné
                else:
                    retention = t("retention_line", n=int(trouve[1] or 0))
            if code != 0:
                break
            if sorties_d_erreur is not None and erreur.strip():
                sorties_d_erreur += 1
        secondes = round(time.monotonic() - t0)
        ligne = lignes[i]
        ligne.code, ligne.secondes = code, secondes
        if code == 0:
            ligne.statut = "passed"
            print(t("step_passed", step=unite.etape, s=secondes), flush=True)
            if unite.etape == "retention" and retention:
                print(retention, flush=True)
            continue
        ligne.statut = "failed"                                  # tout code non nul arrête le suivi avec le code 1 (D8)
        if not args.verbose and erreur.strip():
            print(erreur.rstrip(), file=sys.stderr, flush=True)
        print(t("step_failed", step=unite.etape, code=code))
        if not args.verbose:
            print(t("see_output"))
        ecrire_resume(rapports, jour, args.language, len(reglages.requetes), len(reglages.series), lignes, sorties_d_erreur, retention)
        print(t("resume", step=unite.etape) + (t("resume_date", date=jour) if jour != aujourdhui else ""))
        return 1
    ecrire_resume(rapports, jour, args.language, len(reglages.requetes), len(reglages.series), lignes, sorties_d_erreur, retention)
    print(t("complete", run=a_faire, total=total, skipped=debut))
    print(t("reading_title"))
    print(t("reading_monthly"))
    print(t("reading_dependencies"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
