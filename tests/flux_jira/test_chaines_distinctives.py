"""Chaînes distinctives de flux_jira.py (change jira-gdpr-alignment, tâche 2.4).

    uv run --with pyyaml --with numpy python -m unittest discover -s tests/flux_jira -v

Spécification : jira-flow-reports (« Labels and versions absent from the flow report ») ; jira-flow-labels.
L'export synthétique porte une étiquette déclarée et une version corrective distinctives (colonnes « Declared Label » et
« Fix Version »). Ni l'une ni l'autre ne doit paraître dans la sortie de statuses, compute (avec --points), compare, ni dans
un fichier du dossier de flux (rapports Markdown et JSON, rapport d'évolution, points d'âge). Le code actuel ne lit pas ces
colonnes : le test verrouille la régression pour les groupes qui liront les étiquettes déclarées (les cycles n'y paraissent
que par des clés neutres).
Autorisé et donc non interdit ici : les clés, les équipes et le nom du fichier d'export dans les rapports du dossier de flux
(hors Git), le périmètre étant celui du rapport. Seules la console des contrôles d'export et le résumé mensuel excluent
les noms d'équipe, et ils ne relèvent pas de cet outil.
"""
import csv
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_flux_jira import AUJOURDHUI, FMT, SCRIPT, WORKFLOW_1, construire, ecrire_yaml
import os
import random

ETIQUETTE = "ZZDISTINCT-ETIQUETTE"
VERSION = "ZZDISTINCT-VERSION"
FICHIER = "zzdistinct-fichier.csv"
EQUIPE = "ZZDISTINCT-EQUIPE"


def ecrire_csv_distinctif(chemin: Path, lignes: list[dict]) -> None:
    with chemin.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Issue key", "Issue Type", "Status", "Status Category", "Created", "Resolved", "Resolution",
                    "Status Category Changed", "Team", "Declared Label", "Fix Version"])
        for t in lignes:
            w.writerow([t["cle"], t["type"], t["etat"], t["categorie"], t["cree"].strftime(FMT),
                        t["resolu"].strftime(FMT) if t["resolu"] else "", t["motif"],
                        t["debut"].strftime(FMT) if t["debut"] else "", t["equipe"], ETIQUETTE, VERSION])


def lancer(workspace: Path, *args: str) -> str:
    env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(workspace)}
    r = subprocess.run(["uv", "run", str(SCRIPT), *args], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout + r.stderr


class ChainesDistinctives(unittest.TestCase):
    def test_aucune_etiquette_ni_version_en_sortie_ni_dans_les_fichiers_de_flux(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            ecrire_yaml(ws, "")
            csv_entree = ws / FICHIER
            ecrire_csv_distinctif(csv_entree, construire(random.Random(7), "ZZKEY", WORKFLOW_1, 40, [EQUIPE], ["Story", "Task"]))
            sorties = [lancer(ws, "statuses", str(csv_entree))]
            for date in ("2026-09-20", "2026-10-04"):
                sorties.append(lancer(ws, "compute", str(csv_entree), "--name", "zz", "--today", date, "--points"))
            sorties.append(lancer(ws, "compare", "--name", "zz"))
            ecrits = [p for p in ws.rglob("*") if p.is_file() and p != csv_entree and p.name != "flux.yaml"]
            self.assertTrue(any(p.suffix == ".md" for p in ecrits), ecrits)
            self.assertTrue(any("evolution" in p.name or "compare" in p.name or "evo" in p.name for p in ecrits), ecrits)
            textes = {"console": "\n".join(sorties)}
            for p in ecrits:
                textes[p.name] = p.read_text(encoding="utf-8", errors="ignore")
            for nom, texte in textes.items():
                for chaine in (ETIQUETTE, VERSION, "Declared Label", "Fix Version"):
                    self.assertNotIn(chaine, texte, f"{chaine} dans {nom}")

    # `cycles` (clés neutres seulement, aucune étiquette ni version) : chaînes distinctives dans test_cycles_commande.py


if __name__ == "__main__":
    unittest.main()
