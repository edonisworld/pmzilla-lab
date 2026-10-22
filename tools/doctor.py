# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
PMZilla Lab : commande doctor, un contrôle de santé du laboratoire en lecture seule (change doctor-command, R-45).

    uv run tools/doctor.py [--language fr|en] [--json] [--quiet] [--record]

Lance les contrôles du design D5 et affiche une ligne par contrôle (`<contrôle> : <niveau> : <raison>`), puis une phrase de
résumé. Niveaux : ok, avertissement, problème, ignoré (avec sa raison). Contrôles : db, ollama, models, launchd, watch,
backup, offsite, disk, jira, branches, run-worktree, mothra-npm (change mothra-npm-ready, D3 : avertissement seulement, une ligne
par constat ; la commande `node` est prise dans le PATH).

Options : --json affiche le résultat au format du fichier d'état ; --quiet n'affiche que les contrôles qui ne sont pas ok, puis le
résumé ; --record écrit le fichier d'état `doctor-etat.json` du dossier de données et peut notifier (seul l'enveloppeur planifié
tools/doctor.sh la passe). Sans --record, aucun fichier n'est créé ni modifié.

Code de sortie : 0 si aucun contrôle n'est en problème (avertissements et contrôles ignorés compris) ; 1 si au moins un contrôle
est en problème ; 2 pour une erreur d'usage ou un doctor qui ne peut pas tourner (racine introuvable, fichier d'état non
inscriptible avec --record).

Le doctor ne répare rien : il ne démarre, ne charge, ne décharge, ne tire, ne supprime et n'élague rien. Il n'ouvre aucune session
de base, ne lit jamais le Trousseau ni le jeton, n'ouvre aucun fichier du dossier des sauvegardes, ne contacte que la machine
locale et ne compare aucune version (les versions sont à R-41).

Variables d'environnement (pour les tests et le réglage) : PMZILLA_LAB_DATA, PMZILLA_LAB_LOGS, PMZILLA_LAB_TODAY (AAAA-MM-JJ),
PMZILLA_LAB_NOW (HH:MM), PMZILLA_LAB_WORKSPACE (copie principale, qui porte aussi le contenu : Flux-Lab), PMZILLA_LAB_RUN (dossier d'exécution, D3), HOME ; PMZILLA_LAB_DB_URL ou PMZILLA_LAB_DB_PORT ;
DOCTOR_OLLAMA_URL, DOCTOR_FLUX, DOCTOR_RUN_WORKTREE, DOCTOR_NOTIFIER (posée par l'enveloppeur planifié seulement), et les seuils
et heures DOCTOR_WATCH_DUE, DOCTOR_WATCH_LATEST, DOCTOR_BACKUP_DUE, DOCTOR_SCHEMAS, DOCTOR_OFFSITE_WARN_DAYS, DOCTOR_OFFSITE_PROBLEM_DAYS,
DOCTOR_DISK_PATH, DOCTOR_DISK_FREE_GB (mesure simulée), DOCTOR_DISK_WARN_GB, DOCTOR_DISK_PROBLEM_GB, DOCTOR_JIRA_WARN_DAYS,
DOCTOR_STALE_DAYS.

Contrôle watch (change watch-catch-up, design D13) : il lit le repère du passage du jour `veille-du-jour.json` du dossier de données
(design D2 : date, etat, ...) et non le journal ; le journal ne sert plus qu'au contrôle db. La date et l'heure du jour sont celles
d'Europe/Paris quand PMZILLA_LAB_TODAY et PMZILLA_LAB_NOW ne sont pas posées. L'heure due est DOCTOR_WATCH_DUE (08:00 par défaut) ;
l'heure limite de démarrage est la constante HEURE_LIMITE (celle de tools/watch.sh, un test les compare), surchargée par
DOCTOR_WATCH_LATEST (HH:MM). Un repère absent, illisible ou d'un autre jour vaut « aucun passage du jour ». Le doctor n'écrit rien
pour ce contrôle, ne prend aucun verrou et vérifie l'écriture du dossier de données sans y écrire (os.access) ; le marqueur d'alerte
`pmzilla-watch-alerte` du dossier des journaux, s'il contient la date du jour, signale un repère impossible à écrire.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lab_paths  # noqa: E402
from doctor_messages import CATALOGS  # noqa: E402
from messages import Messages, add_language_option, fields  # noqa: E402

RACINE = Path(__file__).resolve().parents[1]
NIVEAUX = ("ok", "warning", "problem", "skipped")
VERSION_ETAT = 1
HEURE_LIMITE = "22:00"   # dernier démarrage planifié de la veille : égale à HEURE_LIMITE de tools/watch.sh (un test les compare)
FUSEAU_VEILLE = "Europe/Paris"

# Les couples (contrôle, clé de raison) possibles : le test du squelette vérifie que chacun a un texte dans les deux langues.
TOUTES_LES_RAISONS = [
    ("db", "ok"), ("db", "port_closed"), ("db", "watch_unreachable"), ("db", "watch_tables_missing"), ("db", "not_local"),
    ("ollama", "ok"), ("ollama", "down"), ("ollama", "not_local"),
    ("models", "ok"), ("models", "missing"), ("models", "depends"),
    ("launchd", "ok"), ("launchd", "not_loaded"), ("launchd", "none_installed"),
    ("watch", "ok"), ("watch", "failed"), ("watch", "missing"), ("watch", "running"), ("watch", "not_due"),
    ("watch", "interrupted"), ("watch", "postponed"), ("watch", "missed"), ("watch", "record_not_writable"),
    ("backup", "ok"), ("backup", "missing"), ("backup", "short"), ("backup", "not_due"),
    ("offsite", "ok"), ("offsite", "warn_old"), ("offsite", "problem_old"), ("offsite", "never"), ("offsite", "not_set_up"),
    ("offsite", "not_permitted"), ("offsite", "incomplete"),
    ("disk", "ok"), ("disk", "low"), ("disk", "critical"),
    ("jira", "ok"), ("jira", "expired"), ("jira", "expiring"), ("jira", "unknown"), ("jira", "unreadable"),
    ("branches", "ok"), ("branches", "stale"),
    ("run-worktree", "ok"), ("run-worktree", "wrong_branch"), ("run-worktree", "missing"), ("run-worktree", "behind"),
    ("run-worktree", "off_history"), ("run-worktree", "dirty"),
    ("mothra-npm", "ok"), ("mothra-npm", "no_lock"), ("mothra-npm", "node_version"), ("mothra-npm", "node_missing"),
    ("mothra-npm", "modules_missing"), ("mothra-npm", "modules_stale"),
]


ORDRE = ["db", "ollama", "models", "launchd", "watch", "backup", "offsite", "disk", "jira", "branches", "run-worktree", "mothra-npm"]


class ImpossibleDeLancer(Exception):
    """Le doctor ne peut pas tourner (code 2) ; le message est la clé de la cause."""


@dataclasses.dataclass
class Resultat:
    id: str
    niveau: str
    cle: str
    compteurs: dict = dataclasses.field(default_factory=dict)   # nombres seulement : c'est ce que le fichier d'état garde
    noms: list = dataclasses.field(default_factory=list)        # noms de branches, de tâches, de rôles : le Terminal seulement
    valeurs: dict = dataclasses.field(default_factory=dict)     # textes des champs de la raison (versions) : le Terminal seulement
    constats: list = dataclasses.field(default_factory=list)    # sous-résultats du même contrôle : une ligne chacun (mothra-npm, D3)


def raison(resultat: Resultat, t: Messages) -> str:
    cle = f"raison_{resultat.id.replace('-', '_')}_{resultat.cle}"
    if cle not in t.catalogs["fr"]:
        cle = f"raison_{resultat.cle}"
    modele = t.catalogs["fr"][cle]
    valeurs = {nom: resultat.valeurs.get(nom, resultat.compteurs.get(nom, 0)) for nom in fields(modele)}
    if "noms" in valeurs:
        valeurs["noms"] = ", ".join(resultat.noms)
    return t(cle, **valeurs)


def ligne(resultat: Resultat, t: Messages) -> str:
    """Une ligne par contrôle ; un contrôle à plusieurs constats en donne une par constat, sous le même identifiant et le même niveau."""
    return "\n".join(t("ligne", check=resultat.id, level=t(f"niveau_{resultat.niveau}"), reason=raison(constat, t))
                     for constat in (resultat.constats or [resultat]))


def compter(resultats: list[Resultat]) -> dict[str, int]:
    return {niveau: sum(1 for r in resultats if r.niveau == niveau) for niveau in NIVEAUX}


def resume(resultats: list[Resultat], t: Messages) -> str:
    n = compter(resultats)
    if n["problem"]:
        return t("resume_problem", n=n["problem"], m=n["warning"])
    if n["warning"]:
        return t("resume_warning", n=n["warning"])
    return t("resume_ok")


def code_sortie(resultats: list[Resultat]) -> int:
    return 1 if any(r.niveau == "problem" for r in resultats) else 0


# --- contexte : tout ce que les contrôles lisent, redirigeable par l'environnement ----------------------------------------
LOCAUX = ("127.0.0.1", "localhost", "::1")


@dataclasses.dataclass
class Contexte:
    aujourdhui: dt.date
    heure: dt.time
    donnees: Path
    journaux: Path
    maison: Path
    env: dict

    def reglage(self, nom: str, defaut: float) -> float:
        """Seuil ou durée réglable par l'environnement ; une valeur illisible retombe sur le défaut."""
        try:
            return float(self.env.get(nom, defaut))
        except ValueError:
            return defaut

    def heure_due(self, nom: str, defaut: str) -> dt.time:
        try:
            return dt.time.fromisoformat(self.env.get(nom) or defaut)
        except ValueError:
            return dt.time.fromisoformat(defaut)

    @property
    def maintenant(self) -> dt.datetime:
        return dt.datetime.combine(self.aujourdhui, self.heure)


def construire_contexte(env=os.environ) -> Contexte:
    try:
        jour = dt.date.fromisoformat(env["PMZILLA_LAB_TODAY"]) if env.get("PMZILLA_LAB_TODAY") else dt.datetime.now(ZoneInfo(FUSEAU_VEILLE)).date()
    except ValueError:
        raise ImpossibleDeLancer("cause_date")
    try:
        heure = dt.time.fromisoformat(env["PMZILLA_LAB_NOW"]) if env.get("PMZILLA_LAB_NOW") else dt.datetime.now(ZoneInfo(FUSEAU_VEILLE)).time().replace(second=0, microsecond=0)
    except ValueError:
        raise ImpossibleDeLancer("cause_heure")
    maison = Path(env.get("HOME", "~")).expanduser()
    donnees = Path(env.get("PMZILLA_LAB_DATA") or maison / ".pmzilla-lab").expanduser()
    journaux = Path(env.get("PMZILLA_LAB_LOGS") or maison / "Library" / "Logs").expanduser()
    return Contexte(jour, heure, donnees, journaux, maison, dict(env))


# --- lecture du journal de la veille : la veille du jour, la même lecture que R-44 --------------------------------------------
def veille_du_jour(ctx: Contexte) -> dict | None:
    """Dernier passage daté d'aujourd'hui dans le journal de la veille : {"fin": "ok"|"echec"|None, "base": None|"unreachable"|"tables"}.
    None quand le journal est absent ou sans passage du jour. Ne lit que les lignes d'en-tête, de fin et de base de données."""
    try:
        lignes = (ctx.journaux / "pmzilla-watch.log").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    passage = None
    for texte in lignes:
        entete = re.match(r"^=== (\d{4}-\d{2}-\d{2}) \d{2}:\d{2} ===", texte)
        if entete:
            passage = {"fin": None, "base": None} if entete.group(1) == ctx.aujourdhui.isoformat() else None
        elif passage is not None:
            if texte.startswith("Base de données injoignable"):
                passage["base"] = "unreachable"
            elif texte.startswith("Tables de la veille absentes"):
                passage["base"] = "tables"
            elif texte.startswith("=== Veille terminée sans erreur"):
                passage["fin"] = "ok"
            elif texte.startswith(("=== Veille terminée avec", "=== Veille arrêtée")):
                passage["fin"] = "echec"
    return passage


# --- db, ollama, models, disk (D5.1, D5.2, D5.8) -------------------------------------------------------------------------
def adresse_base(env) -> tuple[str, int]:
    url = env.get("PMZILLA_LAB_DB_URL")
    if url:
        analyse = urllib.parse.urlparse(url)
        return analyse.hostname or "", analyse.port or 5432
    try:
        return "127.0.0.1", int(env.get("PMZILLA_LAB_DB_PORT") or 5432)
    except ValueError:
        return "127.0.0.1", 5432


def controle_db(ctx: Contexte, _precedents) -> Resultat:
    hote, port = adresse_base(ctx.env)
    if hote not in LOCAUX:
        return Resultat("db", "skipped", "not_local")
    try:
        with socket.create_connection((hote, port), timeout=3):
            pass
    except OSError:
        return Resultat("db", "problem", "port_closed")
    veille = veille_du_jour(ctx)
    if veille and veille["base"] == "unreachable":
        return Resultat("db", "problem", "watch_unreachable")
    if veille and veille["base"] == "tables":
        return Resultat("db", "problem", "watch_tables_missing")
    return Resultat("db", "ok", "ok")


def modeles_ollama_listes(ctx: Contexte) -> list[str] | None:
    """Noms des modèles que le serveur local liste ; None s'il ne répond pas. Une seule requête GET /api/tags."""
    adresse = ctx.env.get("DOCTOR_OLLAMA_URL") or "http://127.0.0.1:11434"
    try:
        with urllib.request.urlopen(adresse.rstrip("/") + "/api/tags", timeout=3) as reponse:
            return [m.get("name", "") for m in json.load(reponse).get("models", []) if isinstance(m, dict)]
    except (OSError, ValueError, urllib.error.URLError):
        return None


def controle_ollama(ctx: Contexte, _precedents) -> Resultat:
    adresse = ctx.env.get("DOCTOR_OLLAMA_URL") or "http://127.0.0.1:11434"
    if (urllib.parse.urlparse(adresse).hostname or "") not in LOCAUX:
        return Resultat("ollama", "skipped", "not_local")
    return Resultat("ollama", "ok", "ok") if modeles_ollama_listes(ctx) is not None else Resultat("ollama", "problem", "down")


def controle_models(ctx: Contexte, precedents) -> Resultat:
    ollama = next((r for r in precedents if r.id == "ollama"), None)
    if ollama is None or ollama.niveau != "ok":
        return Resultat("models", "skipped", "depends", {}, ["ollama"])
    import install_lab_context
    listes = modeles_ollama_listes(ctx) or []
    manquants = []
    for role, nom, _taille in install_lab_context.modeles_ollama(RACINE):
        if not any(vu == nom or (":" not in nom and vu.split(":")[0] == nom) for vu in listes):
            manquants.append(role)
    if manquants:
        return Resultat("models", "problem", "missing", {"missing": len(manquants)}, manquants)
    return Resultat("models", "ok", "ok")


def controle_disk(ctx: Contexte, _precedents) -> Resultat:
    simule = ctx.env.get("DOCTOR_DISK_FREE_GB")
    if simule is not None:
        libre = float(simule)
    else:
        libre = shutil.disk_usage(ctx.env.get("DOCTOR_DISK_PATH") or ctx.maison).free / 1e9
    libre_go = int(libre)
    compteurs = {"free_gb": libre_go}
    if libre < ctx.reglage("DOCTOR_DISK_PROBLEM_GB", 5):
        return Resultat("disk", "problem", "critical", compteurs)
    if libre < ctx.reglage("DOCTOR_DISK_WARN_GB", 20):
        return Resultat("disk", "warning", "low", compteurs)
    return Resultat("disk", "ok", "ok", compteurs)


# --- launchd, watch, backup, offsite (D5.3 à D5.7) --------------------------------------------------------------
def controle_launchd(ctx: Contexte, _precedents) -> Resultat:
    """Pour chaque gabarit du dépôt dont le fichier rendu est installé, la tâche doit être chargée (état de launchd, en lecture)."""
    dossier = ctx.maison / "Library" / "LaunchAgents"
    etiquettes = sorted(p.name[:-len(".plist")] for p in (RACINE / "tools").glob("com.pmzilla.*.plist"))
    installees = [e for e in etiquettes if (dossier / f"{e}.plist").exists()]
    if not installees:
        return Resultat("launchd", "skipped", "none_installed")
    non_chargees = []
    for etiquette in installees:
        try:
            sortie = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{etiquette}"], capture_output=True, timeout=10)
            charge = sortie.returncode == 0
        except (OSError, subprocess.SubprocessError):
            charge = False
        if not charge:
            non_chargees.append(etiquette)
    if non_chargees:
        return Resultat("launchd", "problem", "not_loaded", {"not_loaded": len(non_chargees)}, non_chargees)
    return Resultat("launchd", "ok", "ok", {"loaded": len(installees), "not_set_up": len(etiquettes) - len(installees)})


def repere_du_jour(ctx: Contexte) -> dict | None:
    """Repère `veille-du-jour.json` (design D2) s'il est lisible et daté d'aujourd'hui (Europe/Paris) ; sinon None (aucun passage du jour)."""
    try:
        repere = json.loads((ctx.donnees / "veille-du-jour.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(repere, dict) or repere.get("date") != ctx.aujourdhui.isoformat():
        return None
    return repere


def repere_impossible_a_ecrire(ctx: Contexte) -> bool:
    """Dossier de données non inscriptible (testé sans écrire) ou marqueur d'alerte du jour dans le dossier des journaux."""
    if ctx.donnees.is_dir() and not os.access(ctx.donnees, os.W_OK | os.X_OK):
        return True
    try:
        return (ctx.journaux / "pmzilla-watch-alerte").read_text(encoding="utf-8").strip() == ctx.aujourdhui.isoformat()
    except OSError:
        return False


def controle_watch(ctx: Contexte, _precedents) -> Resultat:
    """Design D13 : première règle qui correspond. Lecture seule : ni repère, ni marqueur, ni verrou écrits ou retirés."""
    if repere_impossible_a_ecrire(ctx):
        return Resultat("watch", "problem", "record_not_writable")
    repere = repere_du_jour(ctx)
    etat = repere.get("etat") if repere else None
    apres_limite = ctx.heure > ctx.heure_due("DOCTOR_WATCH_LATEST", HEURE_LIMITE)
    if etat == "termine":
        return Resultat("watch", "ok", "ok")
    if etat == "echoue":
        return Resultat("watch", "problem", "failed")
    if etat == "interrompu":
        return Resultat("watch", "problem", "interrupted")
    if etat == "commence":
        if (ctx.donnees / "veille.verrou").is_dir():
            return Resultat("watch", "skipped", "running")
        return Resultat("watch", "problem", "interrupted")
    if apres_limite:   # aucun repère du jour, ou un repère « reporte » (ou d'un état inconnu) : le jour est manqué
        return Resultat("watch", "problem", "missed")
    if etat == "reporte":
        return Resultat("watch", "skipped", "postponed")
    if ctx.heure < ctx.heure_due("DOCTOR_WATCH_DUE", "08:00"):
        return Resultat("watch", "skipped", "not_due")
    return Resultat("watch", "problem", "missing")


def controle_backup(ctx: Contexte, _precedents) -> Resultat:
    """Le dossier daté du jour et le nombre de dumps, par noms et nombre seulement : aucun fichier n'est ouvert, aucun nom n'est affiché."""
    racine = Path(ctx.env.get("DOCTOR_BACKUPS") or ctx.donnees / "sauvegardes")
    dossier = racine / f"db-{ctx.aujourdhui.isoformat()}"
    # un dump par schéma, plus le dump partiel de quality, obligatoire (tools/db_backup.sh, change story-quality-audit, D10)
    attendus = len((ctx.env.get("DOCTOR_SCHEMAS") or "knowledge cases flow").split()) + 1
    try:
        trouves = sum(1 for nom in os.listdir(dossier) if nom.endswith(".dump"))
    except OSError:
        if ctx.heure < ctx.heure_due("DOCTOR_BACKUP_DUE", "08:30"):
            return Resultat("backup", "skipped", "not_due")
        return Resultat("backup", "problem", "missing")
    if trouves < attendus:
        return Resultat("backup", "problem", "short", {"found": trouves, "expected": attendus})
    return Resultat("backup", "ok", "ok", {"found": trouves})


LIGNES_JOURNAL_OFFSITE = 40


def echec_journal_offsite(ctx: Contexte, derniere_reussite: dt.date) -> str | None:
    """Clé de raison (« not_permitted » ou « incomplete ») quand la fin du journal de la copie hors du Mac (pmzilla-offsite-copy.log)
    porte « Operation not permitted » ou « copie incomplète », et que le journal a été écrit après la dernière réussite (une copie à
    la main réussie après l'échec planifié n'est plus signalée). Ne lit que les 40 dernières lignes, n'en sort aucun texte."""
    chemin = ctx.journaux / "pmzilla-offsite-copy.log"
    try:
        ecrit = dt.datetime.fromtimestamp(chemin.stat().st_mtime).date()
        fin = chemin.read_text(encoding="utf-8", errors="replace").splitlines()[-LIGNES_JOURNAL_OFFSITE:]
    except OSError:
        return None
    if ecrit <= derniere_reussite:
        return None
    if any("Operation not permitted" in ligne for ligne in fin):
        return "not_permitted"
    if any(ligne.startswith("copie incomplète") for ligne in fin):
        return "incomplete"
    return None


def controle_offsite(ctx: Contexte, _precedents) -> Resultat:
    """Seule la ligne « copy » du fichier d'état de la copie hors du Mac est lue : la date de la dernière réussite. Aucun accès au disque."""
    dossier = ctx.donnees / "offsite"
    if not (dossier / "configuration").exists():
        return Resultat("offsite", "skipped", "not_set_up")
    derniere = None
    try:
        for texte in (dossier / "statut").read_text(encoding="utf-8", errors="replace").splitlines():
            if texte.startswith("copy "):
                trouve = re.search(r"derniere_reussite=(\S+)", texte)
                derniere = trouve.group(1) if trouve else None
    except OSError:
        pass
    try:
        jour = dt.date.fromisoformat(derniere) if derniere else None
    except ValueError:
        jour = None
    if jour is None:
        return Resultat("offsite", "problem", "never")
    jours = (ctx.aujourdhui - jour).days
    echec = echec_journal_offsite(ctx, jour)
    if echec:
        return Resultat("offsite", "problem", echec, {"days": jours})
    if jours > ctx.reglage("DOCTOR_OFFSITE_PROBLEM_DAYS", 15):
        return Resultat("offsite", "problem", "problem_old", {"days": jours})
    if jours > ctx.reglage("DOCTOR_OFFSITE_WARN_DAYS", 1):
        return Resultat("offsite", "warning", "warn_old", {"days": jours})
    return Resultat("offsite", "ok", "ok", {"days": jours})


# --- jira, branches, run-worktree (D3, D5.10, D5.11) ---------------------------------------------------------------------
def controle_jira(ctx: Contexte, _precedents) -> Resultat:
    """Lit `jira_token_expires` (et sa période d'avertissement) dans les réglages du flux, rien d'autre : ni Trousseau, ni jeton.
    La clé et sa période viennent du change jira-gdpr-alignment (R-58) ; tant qu'elle manque, le contrôle est ignoré."""
    import yaml
    if not ctx.env.get("DOCTOR_FLUX") and racine_contenu(ctx) is None:
        return Resultat("jira", "problem", "content_unknown")
    chemin = Path(ctx.env.get("DOCTOR_FLUX") or racine_contenu(ctx) / "Flux-Lab" / "flux.yaml")
    if not chemin.exists():
        return Resultat("jira", "skipped", "unknown")
    try:
        reglages = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
        if not isinstance(reglages, dict):
            raise ValueError
        valeur = reglages.get("jira_token_expires")
        periode = reglages.get("jira_token_warning_days")
        if valeur is None:
            return Resultat("jira", "skipped", "unknown")
        date = valeur if isinstance(valeur, dt.date) else dt.date.fromisoformat(str(valeur))
        if "DOCTOR_JIRA_WARN_DAYS" in ctx.env:
            periode = ctx.reglage("DOCTOR_JIRA_WARN_DAYS", 30)
        periode = float(periode) if isinstance(periode, (int, float)) and not isinstance(periode, bool) else ctx.reglage("DOCTOR_JIRA_WARN_DAYS", 30)
    except (OSError, ValueError, yaml.YAMLError):
        return Resultat("jira", "warning", "unreadable")
    jours = (date - ctx.aujourdhui).days
    if jours < 0:
        return Resultat("jira", "problem", "expired")
    if jours <= periode:
        return Resultat("jira", "warning", "expiring", {"days": jours})
    return Resultat("jira", "ok", "ok", {"days": jours})


def git_lire(dossier: Path, *arguments: str) -> str | None:
    """Une commande Git en lecture seule dans `dossier` ; None si elle échoue."""
    try:
        sortie = subprocess.run(["git", "-C", str(dossier), *arguments], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return sortie.stdout if sortie.returncode == 0 else None


def racine_contenu(ctx: Contexte) -> Path | None:
    """Le dépôt de développement, qui porte le contenu (Flux-Lab) : le module partagé tools/lab_paths.py (PMZILLA_LAB_WORKSPACE, sinon
    le dépôt Git de la racine du code). None quand il est introuvable : le doctor ne s'arrête jamais (R-77, D7), les contrôles qui
    en ont besoin rendent un problème (clé `content_unknown`) sans afficher de chemin."""
    try:
        return lab_paths.content_root(ctx.env, RACINE)
    except lab_paths.LabPathsError:
        return None


def copie_principale(ctx: Contexte) -> Path | None:
    return racine_contenu(ctx)


def worktrees(principale: Path) -> list[dict] | None:
    brut = git_lire(principale, "worktree", "list", "--porcelain")
    if brut is None:
        return None
    entrees, courante = [], None
    for texte in brut.splitlines():
        if texte.startswith("worktree "):
            courante = {"chemin": texte[9:], "branche": None, "detache": False, "elaguable": False}
            entrees.append(courante)
        elif courante is not None:
            if texte.startswith("branch refs/heads/"):
                courante["branche"] = texte[len("branch refs/heads/"):]
            elif texte == "detached":
                courante["detache"] = True
            elif texte.startswith("prunable"):
                courante["elaguable"] = True
    return entrees


def controle_branches(ctx: Contexte, _precedents) -> Resultat:
    principale = copie_principale(ctx)
    if principale is None:
        return Resultat("branches", "problem", "content_unknown")
    entrees = worktrees(principale)
    fusionnees_brut = git_lire(principale, "branch", "--merged", "main", "--format=%(refname:short)")
    if entrees is None or fusionnees_brut is None:
        return Resultat("branches", "skipped", "not_set_up")
    fusionnees = set(fusionnees_brut.split())
    seuil = ctx.reglage("DOCTOR_STALE_DAYS", 14)
    fusionnes_wt, inactifs, elagables, noms = [], [], [], []
    avec_worktree = set()
    execution = (dossier_execution(ctx) or Path(os.sep)).resolve()
    for entree in entrees[1:]:                       # la première entrée est la copie principale
        if Path(entree["chemin"]).resolve() == execution:   # le dossier d'exécution n'est ni une branche ni jamais inactif (D8)
            continue
        branche = entree["branche"]
        if entree["elaguable"]:
            elagables.append(branche or "?")
            continue
        if branche is None:
            continue
        avec_worktree.add(branche)
        if branche in fusionnees:
            fusionnes_wt.append(branche)
            continue
        horodatage = git_lire(principale, "log", "-1", "--format=%ct", branche)
        if horodatage and horodatage.strip().isdigit():
            age = (ctx.maintenant - dt.datetime.fromtimestamp(int(horodatage))).days
            if age > seuil:
                inactifs.append(branche)
    locales = sorted(b for b in fusionnees if b != "main" and b not in avec_worktree and b not in elagables)
    noms = fusionnes_wt + inactifs + locales + elagables
    if not noms:
        return Resultat("branches", "ok", "ok")
    return Resultat("branches", "warning", "stale",
                    {"merged_worktrees": len(fusionnes_wt), "stale_worktrees": len(inactifs), "merged_branches": len(locales), "prunable": len(elagables)}, noms)


def dossier_execution(ctx: Contexte) -> Path | None:
    """Le dossier d'exécution (design D3, D8) : DOCTOR_RUN_WORKTREE, sinon PMZILLA_LAB_RUN, sinon le dossier `run` du dossier du lab
    (module partagé) ; None quand le dossier de contenu est introuvable."""
    voulu = ctx.env.get("DOCTOR_RUN_WORKTREE") or ctx.env.get("PMZILLA_LAB_RUN")
    if voulu:
        return Path(voulu).expanduser()
    contenu = racine_contenu(ctx)
    return None if contenu is None else lab_paths.run_tree(contenu, ctx.env)


def controle_run_worktree(ctx: Contexte, _precedents) -> Resultat:
    """Règle de D8, en lecture seule (aucune commande Git qui change le dossier) : ok en tête détachée au sommet de main et propre ;
    avertissement s'il est en retard sur main par avance rapide ; problème s'il manque, est sur une branche, hors de l'historique
    de main ou porte un changement local."""
    dossier = dossier_execution(ctx)
    if dossier is None:
        return Resultat("run-worktree", "problem", "content_unknown")
    if not dossier.is_dir() or git_lire(dossier, "rev-parse", "--git-dir") is None:
        return Resultat("run-worktree", "problem", "missing")
    if git_lire(dossier, "symbolic-ref", "--short", "-q", "HEAD") is not None:
        return Resultat("run-worktree", "problem", "wrong_branch")
    tete = git_lire(dossier, "rev-parse", "HEAD")
    sommet = git_lire(dossier, "rev-parse", "refs/heads/main")
    if tete is None or sommet is None:
        return Resultat("run-worktree", "problem", "off_history")
    tete, sommet = tete.strip(), sommet.strip()
    en_retard = tete != sommet
    if en_retard and git_lire(dossier, "merge-base", "--is-ancestor", tete, sommet) is None:
        return Resultat("run-worktree", "problem", "off_history")
    modifie = git_lire(dossier, "--no-optional-locks", "status", "--porcelain", "--untracked-files=no")
    if modifie is None or modifie.strip():
        return Resultat("run-worktree", "problem", "dirty")
    return Resultat("run-worktree", "warning", "behind") if en_retard else Resultat("run-worktree", "ok", "ok")


# --- mothra-npm (change mothra-npm-ready, D3) ----------------------------------------------------------------------------
def version_node() -> str | None:
    """La sortie de `node --version` (commande prise dans le PATH, la couture des tests) ; None si Node manque ou échoue."""
    try:
        sortie = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return (sortie.stdout.strip() or None) if sortie.returncode == 0 else None


def meme_version(vue: str, fixee: str) -> bool:
    """`v22.11.0` répond à `.node-version` 22.11.0 ou v22.11.0 ; comparaison exacte, jamais par préfixe (D3 : « différent de »)."""
    return vue.strip().lstrip("v") == fixee.strip().lstrip("v")


def lire_octets(chemin: Path) -> bytes | None:
    try:
        return chemin.read_bytes()
    except OSError:
        return None


def paquets_du_verrou(brut: bytes | None) -> dict | None:
    """Les entrées `packages` d'un verrou npm (lockfileVersion 2 ou 3), hors entrée racine "" ; None si illisible."""
    try:
        paquets = json.loads(brut)["packages"] if brut is not None else None
    except (ValueError, TypeError, KeyError):
        return None
    if not isinstance(paquets, dict):
        return None
    return {cle: valeur for cle, valeur in paquets.items() if cle != "" and isinstance(valeur, dict)}


def modules_a_jour(verrou: bytes, cache: bytes | None) -> bool:
    """Le verrou caché que npm écrit dans `node_modules/.package-lock.json` n'est pas une copie du verrou : il omet l'entrée racine ""
    et les paquets non installés (optionnels d'une autre plateforme). À jour quand chaque entrée du verrou caché existe dans le verrou
    avec la même version et la même intégrité, et que chaque paquet non optionnel du verrou (`node_modules/…`) est dans le verrou caché."""
    attendus, installes = paquets_du_verrou(verrou), paquets_du_verrou(cache)
    if attendus is None or installes is None:
        return False
    for cle, installe in installes.items():
        attendu = attendus.get(cle)
        if attendu is None or any(installe.get(champ) != attendu.get(champ) for champ in ("version", "integrity")):
            return False
    return all(cle in installes for cle, attendu in attendus.items()
               if cle.startswith("node_modules/") and not attendu.get("optional"))


def controle_mothra_npm(ctx: Contexte, _precedents) -> Resultat:
    """Lecture seule, sans réseau : le verrou de Mothra de l'espace de travail, le Node de `mothra/.node-version` et le verrou recopié
    par npm dans `node_modules/.package-lock.json`. Avertissement, une ligne par constat ; jamais problème (D3)."""
    contenu = racine_contenu(ctx)
    if contenu is None:
        return Resultat("mothra-npm", "skipped", "content_unknown")
    mothra = contenu / "mothra"
    verrou = lire_octets(mothra / "package-lock.json")
    if verrou is None:
        return Resultat("mothra-npm", "skipped", "no_lock")
    constats = []
    fixee = lire_octets(mothra / ".node-version")
    fixee = fixee.decode("utf-8", errors="replace").strip() if fixee else ""
    if not fixee:
        constats.append(Resultat("mothra-npm", "warning", "node_unpinned"))
    else:
        vue = version_node()
        if vue is None:
            constats.append(Resultat("mothra-npm", "warning", "node_missing", valeurs={"pinned": fixee}))
        elif not meme_version(vue, fixee):
            constats.append(Resultat("mothra-npm", "warning", "node_version", valeurs={"version": vue, "pinned": fixee}))
    if not (mothra / "node_modules").is_dir():
        constats.append(Resultat("mothra-npm", "warning", "modules_missing"))
    elif not modules_a_jour(verrou, lire_octets(mothra / "node_modules" / ".package-lock.json")):
        constats.append(Resultat("mothra-npm", "warning", "modules_stale"))
    if not constats:
        return Resultat("mothra-npm", "ok", "ok")
    premier = constats[0]
    return Resultat("mothra-npm", "warning", premier.cle, {"findings": len(constats)}, valeurs=premier.valeurs, constats=constats)


# --- les contrôles, dans l'ordre d'affichage ---------------------------------------------------------------------------
CONTROLES: list = [controle_db, controle_ollama, controle_models, controle_launchd, controle_watch, controle_backup, controle_offsite,
                   controle_disk, controle_jira, controle_branches, controle_run_worktree, controle_mothra_npm]


def lancer_controles(ctx: Contexte) -> list[Resultat]:
    resultats: list[Resultat] = []
    for controle in CONTROLES:
        sortie = controle(ctx, resultats)
        resultats.extend(sortie if isinstance(sortie, list) else [sortie])
    return sorted(resultats, key=lambda r: ORDRE.index(r.id))


def etat_json(ctx: Contexte, resultats: list[Resultat], derniere_notification: str | None) -> dict:
    return {
        "version": VERSION_ETAT,
        "checked_at": ctx.maintenant.strftime("%Y-%m-%dT%H:%M"),
        "counts": compter(resultats),
        "checks": [{"id": r.id, "level": r.niveau, "reason": {"key": r.cle, "counts": dict(r.compteurs)}} for r in resultats],
        "last_notification": derniere_notification,
    }


def lire_derniere_notification(ctx: Contexte) -> str | None:
    try:
        valeur = json.loads((ctx.donnees / "doctor-etat.json").read_text(encoding="utf-8")).get("last_notification")
    except (OSError, ValueError, AttributeError):
        return None
    return valeur if isinstance(valeur, str) else None


def ecrire_etat(ctx: Contexte, etat: dict) -> None:
    """Remplace atomiquement doctor-etat.json (lecture et écriture du propriétaire seulement)."""
    cible = ctx.donnees / "doctor-etat.json"
    temporaire = ctx.donnees / f".doctor-etat.{os.getpid()}.tmp"
    try:
        ctx.donnees.mkdir(parents=True, exist_ok=True)
        descripteur = os.open(temporaire, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descripteur, "w", encoding="utf-8") as fichier:
            json.dump(etat, fichier, indent=2)
        os.replace(temporaire, cible)
    except OSError:
        try:
            temporaire.unlink()
        except OSError:
            pass
        raise ImpossibleDeLancer("cause_etat")


def notifier(texte: str) -> bool:
    """Notification macOS ; un échec ne change jamais le code de sortie."""
    try:
        return subprocess.run(["osascript", "-e", f'display notification "{texte}" with title "PMZilla doctor"'],
                              capture_output=True, timeout=15).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doctor.py", description="Contrôle de santé du laboratoire, en lecture seule.")
    add_language_option(parser)
    parser.add_argument("--json", action="store_true", help="affiche le résultat au format du fichier d'état")
    parser.add_argument("--quiet", action="store_true", help="n'affiche que les contrôles qui ne sont pas ok, puis le résumé")
    parser.add_argument("--record", action="store_true", help="écrit le fichier d'état et peut notifier (enveloppeur planifié seulement)")
    args = parser.parse_args(argv)
    t = Messages(CATALOGS, args.language)
    try:
        ctx = construire_contexte()
        resultats = lancer_controles(ctx)
    except ImpossibleDeLancer as erreur:
        print(t("impossible", cause=t(str(erreur))), file=sys.stderr)
        return 2
    derniere = lire_derniere_notification(ctx)
    a_notifier = False
    if args.record:
        problemes = [r.id for r in resultats if r.niveau == "problem"]
        a_notifier = bool(problemes) and ctx.env.get("DOCTOR_NOTIFIER") == "1" and derniere != ctx.aujourdhui.isoformat()
        try:
            ecrire_etat(ctx, etat_json(ctx, resultats, ctx.aujourdhui.isoformat() if a_notifier else derniere))
        except ImpossibleDeLancer as erreur:
            print(t("impossible", cause=t(str(erreur))), file=sys.stderr)
            return 2
    if args.json:
        print(json.dumps(etat_json(ctx, resultats, derniere), indent=2))
    else:
        for r in resultats:
            if not args.quiet or r.niveau != "ok":
                print(ligne(r, t))
        print(resume(resultats, t))
    if a_notifier:
        notifier(t("notification", n=len(problemes), checks=", ".join(problemes)))
    return code_sortie(resultats)


if __name__ == "__main__":
    sys.exit(main())
