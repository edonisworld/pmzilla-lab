"""Colonnes « Declared Label » et « Fix Version » ignorées par le rapport de dépendances (jira-flow-export, « New columns
ignored by the CSV calculations » ; design D11).

    uv run --with pyyaml --with requests python -m unittest discover -s tests/dependencies_jira -v

Le même export synthétique est écrit avec et sans les nouvelles colonnes (après les équipes, avant les colonnes de liens, comme
l'export de l'API). La carte de dépendances de chaque export est calculée dans un dossier de travail à part, avec le même nom :
le Markdown et le JSON sont identiques, hors la liste des colonnes lue.
"""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from test_dependencies_jira import AUJOURDHUI, SCRIPT, Base, ecrire_manuel, t

ETIQUETTES = ("zz-etiquette-a", "zz-etiquette-b")
VERSION = "zz-version"

TICKETS = [t("PROJ-1", "Equipe A", sortants=["PROJ-2"]),
           t("PROJ-2", "Equipe B", entrants=["PROJ-1"], sortants=["PROJ-4"]),
           t("PROJ-3", "Equipe B", etat="Open", cat="To Do", sortants=["PROJ-4"]),
           t("PROJ-4", "Equipe A", entrants=["PROJ-2", "PROJ-3"])]


class ColonnesIgnorees(Base):
    def export_avec_colonnes(self, chemin: Path) -> None:
        """L'export manuel des tickets, complété des colonnes d'étiquette et de version avant la première colonne de lien."""
        with chemin.open(encoding="utf-8", newline="") as f:
            lignes = list(csv.reader(f))
        place = next(i for i, h in enumerate(lignes[0]) if "issue link" in h)
        lignes[0][place:place] = ["Declared Label", "Declared Label", "Fix Version"]
        for ligne in lignes[1:]:
            ligne[place:place] = [*ETIQUETTES, VERSION]
        with chemin.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(lignes)

    def rapport(self, avec_colonnes: bool) -> dict:
        self.tmp2 = tempfile.TemporaryDirectory()          # un dossier de travail par calcul : même nom de rapport
        self.addCleanup(self.tmp2.cleanup)
        self.ws = Path(self.tmp2.name)
        (self.ws / "Flux-Lab").mkdir()
        export = self.ws / "export.csv"
        ecrire_manuel(export, TICKETS)
        if avec_colonnes:
            self.export_avec_colonnes(export)
        self.lancer("compute", str(export), "--name", "ref")
        dossier = self.ws / "Flux-Lab" / "rapports"
        js = json.loads((dossier / f"dependances-ref-{AUJOURDHUI.isoformat()}.json").read_text(encoding="utf-8"))
        md = (dossier / f"dependances-ref-{AUJOURDHUI.isoformat()}.md").read_text(encoding="utf-8")
        js.pop("colonnes", None)
        return {"json": js, "md": md}

    def test_rapport_identique_avec_et_sans_les_nouvelles_colonnes(self):
        sans, avec = self.rapport(False), self.rapport(True)
        self.assertEqual(avec["json"], sans["json"])
        self.assertEqual(avec["md"], sans["md"])
        self.assertTrue(avec["json"])                     # le rapport n'est pas vide : la comparaison ne passe pas à vide

    def test_ni_etiquette_ni_version_dans_le_rapport(self):
        avec = self.rapport(True)
        texte = avec["md"] + json.dumps(avec["json"])
        for chaine in (*ETIQUETTES, VERSION):
            self.assertNotIn(chaine, texte)

    def test_les_liens_sont_toujours_reconnus_apres_les_nouvelles_colonnes(self):
        sans, avec = self.rapport(False), self.rapport(True)
        self.assertTrue(avec["json"]["aretes"])                  # des dépendances sont bien lues après les colonnes ajoutées
        self.assertEqual(avec["json"]["aretes"], sans["json"]["aretes"])


if __name__ == "__main__":
    unittest.main()
