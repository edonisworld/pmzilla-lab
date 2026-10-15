"""Aide des tests de flow_import : CSV factices au format de export_jira_api.py, données inventées (PROJ-n, Alpha, Beta)."""
import csv
import datetime
import sys
import zoneinfo
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flux_jira  # noqa: E402

ENTETE = ["Issue key", "Issue Type", "Status", "Status Category", "Created", "Resolved", "Resolution",
          "Status Category Changed", "Updated", "Story Points", "Parent key", "Team", "Team",
          "Outward issue link (Blocks)", "Inward issue link (Blocks)", "Linked Issues"]


MOIS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def jour_relatif(jours: int = 30):
    """Jour d'il y a `jours` jours : une date de résolution fixe finirait sous la règle de conservation d'un an."""
    return datetime.date.today() - datetime.timedelta(days=jours)


def date_export(jour, heure: int = 0, minute: int = 0) -> str:
    """Date au format de l'export de l'API (jour/mois/année heure:minute), mois en anglais sans dépendre de la locale."""
    return f"{jour.day:02d}/{MOIS[jour.month - 1]}/{jour.year} {heure:02d}:{minute:02d}"


def instant_utc(jour, heure: int = 0, minute: int = 0) -> datetime.datetime:
    """Instant UTC d'une date de l'export, lue dans le fuseau d'export par défaut (Europe/Paris), été ou hiver."""
    local = datetime.datetime(jour.year, jour.month, jour.day, heure, minute, tzinfo=zoneinfo.ZoneInfo("Europe/Paris"))
    return local.astimezone(datetime.timezone.utc)


def ligne(cle="PROJ-1", **valeurs):
    base = {"Issue key": cle, "Issue Type": "Story", "Status": "In Progress", "Status Category": "In Progress",
            "Created": "02/Jan/2026 09:30", "Resolved": "", "Resolution": "", "Status Category Changed": "05/Jan/2026 10:00",
            "Updated": "06/Jan/2026 11:15", "Story Points": "", "Parent key": "", "Team": "Alpha",
            "Outward issue link (Blocks)": "", "Inward issue link (Blocks)": "", "Linked Issues": ""}
    base.update(valeurs)
    return base


def ecrire(chemin, lignes, entete=None):
    """Écrit un CSV. Une ligne est un dictionnaire par nom de colonne ; la colonne « Team » est répétée dans l'en-tête et
    la clé « Team2 » remplit la seconde."""
    entete = entete or ENTETE
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(entete)
        for l in lignes:
            cellules, vu_team = [], 0
            for nom in entete:
                if nom == "Team":
                    cellules.append(l.get("Team2", "") if vu_team else l.get("Team", ""))
                    vu_team += 1
                else:
                    cellules.append(l.get(nom, ""))
            w.writerow(cellules)
    return chemin


def reglages(**surcharges):
    """Réglages de flux.yaml par défaut (comme flux_jira.config), sans toucher à Flux-Lab/."""
    r = {**flux_jira.DEFAULT_CONFIG, "colonnes": {**flux_jira.DEFAULT_CONFIG["colonnes"]}}
    r.update(surcharges)
    return r
