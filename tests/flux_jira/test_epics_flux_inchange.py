"""Les épics restent hors du rapport de flux (R-89, conception D12, tâche 2.4) : `compute` avec historique et tickets dormants donne
des rapports Markdown et JSON identiques à l'octet, que l'historique contienne ou non les transitions des épics.

    bash tests/run_all.sh flux_jira

Garde de non-régression : les types de niveau portefeuille sont retirés avant toute lecture de l'historique, donc la couverture, les
dormants et le temps par segment ne bougent pas quand la collecte garde les épics (groupe 3). Données inventées, sous-processus.
"""
import csv
import datetime as dt
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "lancer_flux_jira.py"          # database-only D11 : chargeur de test des fixtures CSV
FMT = "%d/%b/%Y %H:%M"
AUJOURDHUI = dt.date(2026, 10, 4)
REGLAGES = "portfolio_types: [Epic]\nepic_types: [Epic]\n"


def transition(date, de, vers):
    return [f"{date}T10:00:00.000+0200", de, vers]


TICKETS = [
    ("ABC-1", "Story", "In Progress", "In Progress", "2024-01-10", None),
    ("ABC-2", "Story", "In Progress", "In Progress", "2024-01-10", None),
    ("ABC-3", "Story", "Closed", "Done", "2026-03-01", "2026-04-01"),
    ("ABC-4", "Bug", "Closed", "Done", "2026-03-05", "2026-05-01"),
    ("EPI-1", "Epic", "In Progress", "In Progress", "2025-06-01", None),
    ("EPI-2", "Epic", "Closed", "Done", "2025-06-01", "2026-05-01"),
]
CACHE_TICKETS = {
    "ABC-1": {"termine": False, "transitions": [transition("2024-03-01", "Open", "In Progress")]},
    "ABC-2": {"termine": False, "transitions": [transition("2024-03-01", "Open", "Doing"), transition("2026-09-01", "Doing", "In Progress")]},
    "ABC-3": {"termine": True, "transitions": [transition("2026-03-02", "Open", "In Progress"), transition("2026-04-01", "In Progress", "Closed")]},
    "ABC-4": {"termine": True, "transitions": [transition("2026-03-06", "Open", "In Progress"), transition("2026-05-01", "In Progress", "Closed")]},
}
CACHE_EPICS = {
    "EPI-1": {"termine": False, "transitions": [transition("2025-07-01", "Open", "In Progress")],
              "etiquettes": [["2025-07-01T10:00:00.000+0200", "add", "zz-etiquette"]]},
    "EPI-2": {"termine": True, "transitions": [transition("2025-07-01", "Open", "In Progress"), transition("2026-05-01", "In Progress", "Closed")]},
}


def preparer(dossier: Path, cache: dict) -> None:
    flux = dossier / "Flux-Lab"
    (flux / "historique").mkdir(parents=True)
    (flux / "flux.yaml").write_text(REGLAGES, encoding="utf-8")
    with (dossier / "export.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Issue key", "Issue Type", "Status", "Status Category", "Created", "Resolved", "Resolution",
                    "Status Category Changed", "Team"])
        for cle, typ, etat, categorie, cree, resolu in TICKETS:
            cree_d = dt.date.fromisoformat(cree)
            resolu_d = dt.date.fromisoformat(resolu) if resolu else None
            w.writerow([cle, typ, etat, categorie, cree_d.strftime(FMT), resolu_d.strftime(FMT) if resolu_d else "",
                        "Done" if resolu_d else "", cree_d.strftime(FMT), "Equipe A"])
    (flux / "historique" / "transitions.json").write_text(json.dumps(cache), encoding="utf-8")


def calculer(cache: dict) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        dossier = Path(tmp)
        preparer(dossier, cache)
        env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(dossier)}
        r = subprocess.run(["uv", "run", str(SCRIPT), "compute", str(dossier / "export.csv"), "--name", "serie",
                            "--today", AUJOURDHUI.isoformat(), "--no-comparison", "--history", "--dormant-from-history"],
                           env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        rapports = dossier / "Flux-Lab" / "rapports"
        return ((rapports / "flux-serie-2026-10-04.md").read_text(encoding="utf-8"),
                (rapports / "flux-serie-2026-10-04.json").read_text(encoding="utf-8"))


class EpicsHorsDuRapportDeFlux(unittest.TestCase):
    def test_rapports_identiques_avec_ou_sans_les_transitions_des_epics(self):
        sans = calculer(CACHE_TICKETS)
        avec = calculer({**CACHE_TICKETS, **CACHE_EPICS})
        self.assertEqual(sans[0], avec[0])
        self.assertEqual(sans[1], avec[1])

    def test_les_epics_sont_ecartes_et_comptes_comme_tels(self):
        md, js = calculer({**CACHE_TICKETS, **CACHE_EPICS})
        self.assertNotIn("EPI-", md + js)
        self.assertNotIn("zz-etiquette", md + js)


if __name__ == "__main__":
    unittest.main()
