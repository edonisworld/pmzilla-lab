"""Colonnes « Declared Label » et « Fix Version » ignorées par le rapport de flux (jira-flow-export, « New columns ignored by
the CSV calculations » ; design D11).

    uv run --with pyyaml --with numpy python -m unittest discover -s tests/flux_jira -v

Le même export synthétique est écrit deux fois, avec et sans les nouvelles colonnes (placées après les équipes et avant la fin
de ligne, comme l'export de l'API, étiquettes déclarées et versions distinctives). Le rapport de flux de chaque export est
calculé dans un dossier de travail à part, avec le même nom de rapport et le même nom de fichier : le Markdown et le JSON sont
identiques, hors la liste des colonnes lue.
"""
import csv
import json
import random
import tempfile
import unittest
from pathlib import Path

from test_flux_jira import AUJOURDHUI, FMT, WORKFLOW_1, construire, ecrire_yaml, lancer

ETIQUETTES = ("zz-etiquette-a", "zz-etiquette-b")
VERSION = "zz-version"


def ecrire_export(chemin: Path, lignes: list[dict], avec_colonnes: bool) -> None:
    with chemin.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        entete = ["Issue key", "Issue Type", "Status", "Status Category", "Created", "Resolved", "Resolution",
                  "Status Category Changed", "Team"]
        w.writerow(entete + (["Declared Label", "Declared Label", "Fix Version"] if avec_colonnes else []))
        for t in lignes:
            ligne = [t["cle"], t["type"], t["etat"], t["categorie"], t["cree"].strftime(FMT),
                     t["resolu"].strftime(FMT) if t["resolu"] else "", t["motif"],
                     t["debut"].strftime(FMT) if t["debut"] else "", t["equipe"]]
            w.writerow(ligne + (list(ETIQUETTES) + [VERSION] if avec_colonnes else []))


def rapports(avec_colonnes: bool, lignes: list[dict], extra: tuple[str, ...] = ()) -> dict[str, str | dict]:
    """Rapports de flux (Markdown, JSON) d'un export calculé dans son propre dossier de travail."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        ecrire_yaml(ws, "")
        export = ws / "export.csv"
        ecrire_export(export, lignes, avec_colonnes)
        lancer(ws, "compute", str(export), "--name", "ref", "--today", AUJOURDHUI.isoformat(), "--no-comparison", *extra)
        dossier = ws / "Flux-Lab" / "rapports"
        md = (dossier / f"flux-ref-{AUJOURDHUI.isoformat()}.md").read_text(encoding="utf-8")
        js = json.loads((dossier / f"flux-ref-{AUJOURDHUI.isoformat()}.json").read_text(encoding="utf-8"))
    return {"md": md, "json": js}


class ColonnesIgnorees(unittest.TestCase):
    def setUp(self):
        self.lignes = construire(random.Random(11), "ABC", WORKFLOW_1, 40, ["Equipe A", "Equipe B"], ["Story", "Task"])

    def comparer(self, extra: tuple[str, ...] = ()):
        sans = rapports(False, self.lignes, extra)
        avec = rapports(True, self.lignes, extra)
        for rapport in (sans, avec):                 # la liste des colonnes lues est la seule différence permise
            rapport["json"].pop("colonnes", None)
        self.assertEqual(avec["json"], sans["json"])
        self.assertEqual(avec["md"], sans["md"])
        return avec

    def test_rapport_identique_avec_et_sans_les_nouvelles_colonnes(self):
        avec = self.comparer()
        self.assertGreater(avec["json"]["termines"], 0)         # le rapport n'est pas vide : la comparaison ne passe pas à vide

    def test_rapport_identique_avec_les_points_d_age(self):
        self.comparer(("--points",))

    def test_ni_etiquette_ni_version_dans_le_rapport(self):
        avec = rapports(True, self.lignes)
        texte = avec["md"] + json.dumps(avec["json"])
        for chaine in (*ETIQUETTES, VERSION):
            self.assertNotIn(chaine, texte)


if __name__ == "__main__":
    unittest.main()
