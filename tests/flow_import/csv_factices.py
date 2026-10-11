"""Aide des tests de flow_import : CSV factices au format de export_jira_api.py, données inventées (PROJ-n, Alpha, Beta)."""
import csv
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flux_jira  # noqa: E402

ENTETE = ["Issue key", "Issue Type", "Status", "Status Category", "Created", "Resolved", "Resolution",
          "Status Category Changed", "Updated", "Story Points", "Parent key", "Team", "Team",
          "Outward issue link (Blocks)", "Inward issue link (Blocks)", "Linked Issues"]


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
