"""Tests de la version anglaise de tools/dependencies_jira.py (lot 3, étape 2) : catalogue de messages, option --language.

Mêmes exports inventés que test_dependencies_jira.py (aucun appel à Jira, aucune donnée réelle). Les sorties de chaque
scénario (console et rapport Markdown) sont comparées à deux instantanés versionnés : reference_fr.md (la sortie française,
identique à celle d'avant le catalogue) et reference_en.md (la sortie anglaise). La date du jour et le dossier temporaire y sont
remplacés par <DATE> et <WS>.

Pour régénérer un instantané après un changement voulu : PMZILLA_UPDATE_SNAPSHOTS=1 python -m unittest discover -s tests/dependencies_jira
Lancement : uv run --with pyyaml --with requests python -m unittest discover -s tests/dependencies_jira
"""
from __future__ import annotations

import csv
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))
import dependencies_jira_messages as dm      # noqa: E402
import messages                              # noqa: E402
from test_dependencies_jira import AUJOURDHUI, SCRIPT, Sens, date_manuel, ecrire_manuel, jour, t   # noqa: E402

REGLAGES = "portfolio_types: [Epic]\nexcluded_projects: [BUG]\n"


def tickets_riches() -> list[dict]:
    """Un jeu qui touche chaque section du rapport : blocages groupés, anciens, hors export, Epics anciens, boucle,
    projet exclu, liens de décomposition, lead time avec et sans dépendance, export au nombre rond (1000 tickets)."""
    x: list[dict] = []
    for i in (1, 2, 3):                                           # trois éléments entrés en cours le même jour
        x.append(t(f"AAA-{i}", "Alpha", sortants=[f"BBB-{i}"]))
        x.append(t(f"BBB-{i}", "Beta", entrants=[f"AAA-{i}"], debut=20))
    x.append(t("AAA-4", "Alpha", type_="Epic", sortants=["BBB-4"]))                      # Epic bloqué par un Epic
    x.append(t("BBB-4", "Beta", type_="Epic", entrants=["AAA-4"]))
    x.append(t("CCC-1", "Gamma", etat="Open", cat="To Do", sortants=["BBB-5"]))          # attendu pas commencé
    x.append(t("BBB-5", "Beta", entrants=["CCC-1"], debut=30))
    for i in range(6, 12):                                                                # attentes vers un ticket absent
        x.append(t(f"BBB-{i}", "Beta", entrants=[f"ZZZ-{i}"], debut=10 + i))
    for i in (20, 21):                                                                    # de quoi dépasser 30 % hors export
        x.append(t(f"BBC-{i}", "Beta", entrants=[f"ZZZ-{i}"], debut=10 + i))
    x.append(t("AAA-11", "Alpha", sortants=["BBB-12"]))                                # blocage de plus d'un an
    x.append(t("BBB-12", "Beta", entrants=["AAA-11"], debut=400, cree=500))
    x.append(t("DDD-1", "Delta", sortants=["AAA-5"]))                                     # boucle Alpha / Delta
    x.append(t("AAA-5", "Alpha", entrants=["DDD-1"], debut=40))
    x.append(t("AAA-6", "Alpha", sortants=["DDD-2"]))
    x.append(t("DDD-2", "Delta", entrants=["AAA-6"], debut=45))
    x.append(t("DDD-9", "Delta", etat="Done", cat="Done", resolu=5, motif="Done", sortants=["AAA-10"]))
    x.append(t("AAA-10", "Alpha", entrants=["DDD-9"]))
    x.append(t("BUG-1", "Alpha", sortants=["AAA-7"]))                                     # projet exclu, les deux sens
    x.append(t("AAA-7", "Alpha", entrants=["BUG-1"]))
    x.append(t("AAA-8", "Alpha", sortants=["BUG-2"]))
    x.append(t("BUG-2", "Alpha", entrants=["AAA-8"]))
    x.append(t("BUG-3", "Alpha", sortants=["BUG-4"]))
    x.append(t("BUG-4", "Alpha", entrants=["BUG-3"]))
    x.append(t("AAA-9", "Alpha", type_="Epic", sortants=["BBB-13"]))                      # lien de décomposition
    x.append(t("BBB-13", "Beta", entrants=["AAA-9"]))
    x.append(t("SSS-1", "", sortants=["BBB-14"]))                                         # ticket sans équipe
    x.append(t("BBB-14", "Beta", entrants=["SSS-1"], debut=15))
    x.append(t("WWW-1", "Alpha", etat="Weird", cat=""))                                   # état inconnu
    x += [                                                                                # Epics anciens
        t("EPA-1", "Alpha", type_="Epic", cree=800, debut=700, sortants=["EPB-1"]),
        t("EPB-1", "Beta", type_="Epic", cree=800, debut=700, entrants=["EPA-1"]),
        t("STA-1", "Alpha", parent="EPA-1", debut=10),
        t("EPA-2", "Alpha", type_="Epic", cree=900, debut=800, sortants=["EPG-1"]),
        t("EPG-1", "Gamma", type_="Epic", cree=900, debut=800, entrants=["EPA-2"]),
        t("STA-2", "Alpha", parent="EPA-2", debut=400),
        t("STG-1", "Gamma", parent="EPG-1", etat="Rejected", cat="Done", resolu=5, motif="Rejected", cree=300)]
    for i in range(6):                                                                    # lead time sans dépendance
        x.append(t(f"LLA-{i}", "Alpha", etat="Done", cat="Done", cree=30 + i, resolu=26 + i, motif="Done"))
    for i in range(5):                                                                    # lead time avec dépendance externe
        x.append(t(f"LLB-{i}", "Beta", etat="Done", cat="Done", cree=30 + i, resolu=20 + i, motif="Done", entrants=[f"LLC-{i}"]))
        x.append(t(f"LLC-{i}", "Gamma", etat="Done", cat="Done", cree=60, resolu=40, motif="Done", sortants=[f"LLB-{i}"]))
    x += [t(f"FIL-{i}", "Alpha") for i in range(1000 - len(x))]                           # nombre rond : export tronqué
    return x


def ecrire_sans_categorie(chemin: Path, lignes: list[list[str]]) -> None:
    """Export sans « Status Category », avec une colonne de liens typée et une colonne de liens sans type."""
    with chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Issue key", "Status", "Created", "Team", "Outward issue link (Blocks)",
                    "Outward issue link (Relates)", "Linked Issues"])
        w.writerows(lignes)


def normaliser(texte: str, ws: Path) -> str:
    return texte.replace(str(ws), "<WS>").replace(AUJOURDHUI.isoformat(), "<DATE>")


class Scenarios:
    """Lance les scénarios dans un dossier temporaire et renvoie {étiquette: sortie normalisée}."""

    def __init__(self, ws: Path, options: list[str]):
        self.ws, self.options, self.sorties = ws, options, {}
        (ws / "Flux-Lab").mkdir(exist_ok=True)
        (ws / "Flux-Lab" / "flux.yaml").write_text(REGLAGES, encoding="utf-8")

    def lancer(self, etiquette: str, *args: str, attendu: int = 0, rapport: str | None = None) -> None:
        env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(self.ws)}
        r = subprocess.run(["uv", "run", "--with", "pyyaml", str(SCRIPT), *args, *self.options],
                           env=env, capture_output=True, text=True)
        assert r.returncode == attendu, f"{etiquette} : code {r.returncode}\n{r.stdout}{r.stderr}"
        texte = f"[console]\n{r.stdout}{r.stderr}"
        if rapport:
            fichier = self.ws / "Flux-Lab" / "rapports" / f"dependances-{rapport}-{AUJOURDHUI.isoformat()}.md"
            texte += f"\n[report {fichier.name}]\n{fichier.read_text(encoding='utf-8')}"
        self.sorties[etiquette] = normaliser(texte, self.ws)

    def tout(self) -> dict[str, str]:
        ws = self.ws
        riche = str(ws / "riche.csv")
        ecrire_manuel(ws / "riche.csv", tickets_riches())
        self.lancer("rich diagnose", "diagnose", riche)
        self.lancer("rich diagnose scope", "diagnose", riche, "--scope", "AAA,BBB")
        self.lancer("rich compute", "compute", riche, "--name", "riche", rapport="riche")
        self.lancer("rich compute keys", "compute", riche, "--name", "cles", "--keys", rapport="cles")
        self.lancer("rich compute by project", "compute", riche, "--name", "projets", "--by", "project",
                    rapport="projets-projets")
        ecrire_manuel(ws / "sans-type.csv", Sens.TICKETS, liens_sans_type=True)
        self.lancer("unoriented diagnose", "diagnose", str(ws / "sans-type.csv"))
        self.lancer("unoriented compute", "compute", str(ws / "sans-type.csv"), "--name", "sans", rapport="sans")
        ecrire_manuel(ws / "vide.csv", [t("AAA-1", "Alpha"), t("BBB-1", "Beta")])
        self.lancer("empty compute", "compute", str(ws / "vide.csv"), "--name", "vide", rapport="vide")
        ecrire_sans_categorie(ws / "lot1.csv", [
            ["AAA-1", "Weird", date_manuel(jour(50)), "Alpha", "BBB-1", "", ""],
            ["AAA-2", "In Progress", date_manuel(jour(50)), "Alpha", "", "BBB-1", ""]])
        ecrire_sans_categorie(ws / "lot2.csv", [["BBB-1", "Open", date_manuel(jour(50)), "Beta", "", "", "AAA-1"]])
        self.lancer("two exports diagnose", "diagnose", str(ws / "lot1.csv"), str(ws / "lot2.csv"))
        (ws / "sans-cle.csv").write_text("Status,Team\nOpen,Alpha\n", encoding="utf-8")
        self.lancer("missing key", "diagnose", str(ws / "sans-cle.csv"), attendu=1)
        (ws / "sans-liens.csv").write_text("Issue key,Status,Team\nAAA-1,Open,Alpha\n", encoding="utf-8")
        self.lancer("no link columns diagnose", "diagnose", str(ws / "sans-liens.csv"))
        self.lancer("no link columns compute", "compute", str(ws / "sans-liens.csv"), attendu=1)
        return self.sorties


def instantane(sorties: dict[str, str]) -> str:
    return "".join(f"=== {etiquette} ===\n{texte}\n" for etiquette, texte in sorties.items())


def lancer_tout(options: list[str]) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        return Scenarios(Path(tmp), options).tout()


class Langue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defaut = instantane(lancer_tout([]))
        cls.francais = instantane(lancer_tout(["--language", "fr"]))
        cls.anglais = instantane(lancer_tout(["--language", "en"]))

    def comparer(self, obtenu: str, nom: str) -> None:
        fichier = HERE / nom
        if os.environ.get("PMZILLA_UPDATE_SNAPSHOTS") == "1":
            fichier.write_text(obtenu, encoding="utf-8")
        self.assertEqual(obtenu, fichier.read_text(encoding="utf-8"))

    def test_catalogues_coherents(self):
        self.assertEqual(messages.check_catalogs(dm.CATALOGS), [])

    def test_sans_option_la_sortie_est_francaise(self):
        self.assertEqual(self.defaut, self.francais)
        self.comparer(self.defaut, "reference_fr.md")

    def test_sortie_anglaise_conforme_a_l_instantane(self):
        self.comparer(self.anglais, "reference_en.md")

    def test_pas_de_francais_dans_la_sortie_anglaise(self):
        mots = re.compile(r"\b(le|la|les|des|pour|une|sont|dans|avec|[ée]quipes?|semaines?|jours?|d[ée]pendances?|attend|"
                          r"[ée]l[ée]ments?|liens?|ouvertes?|toutes?|bloque|rapport)\b|[éèêàçùô]", re.IGNORECASE)
        restes = []
        for ligne in self.anglais.splitlines():
            if ligne.startswith("==="):
                continue
            ligne = re.sub(r"\S*dependances-\S+|\S*sans-\S+", "", ligne)       # noms de fichiers de données de test
            if mots.search(ligne):
                restes.append(ligne)
        self.assertEqual(restes, [])

    def test_ancienne_option_langue_refusee(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "Flux-Lab").mkdir()
            ecrire_manuel(ws / "m.csv", Sens.TICKETS)
            env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(ws)}
            r = subprocess.run(["uv", "run", "--with", "pyyaml", str(SCRIPT), "diagnose", str(ws / "m.csv"), "--langue", "en"],
                               env=env, capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("« --langue » n'existe plus ; utiliser « --language »", r.stderr)
            self.assertEqual(r.stdout, "")


if __name__ == "__main__":
    unittest.main()
