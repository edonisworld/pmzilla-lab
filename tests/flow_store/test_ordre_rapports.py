"""Les rapports de flux_jira.py et de dependencies_jira.py ne dépendent pas de l'ordre de lecture des tickets.

    uv run --with numpy --with pyyaml --with requests python -m unittest discover -s tests/flow_store -p "test_ordre*" -v

Le jeu inventé est fait pour les égalités : des types, des motifs de clôture, des états (en cours, en attente, à faire, non classés) et des
projets qui ont tous le même effectif. Avant le tri déterministe, chaque liste du rapport suivait l'ordre de lecture et deux lectures du même
export, dans un ordre différent ou en deux fichiers, donnaient des rapports différents. Pas de base : seule la voie CSV est utilisée ici (la
comparaison avec la base, dans un ordre différent, est dans test_sources_scripts.py).
"""
from __future__ import annotations

import datetime as dt
import json
import random
import re
import sys
import tempfile
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
sys.path.insert(0, str(ICI.parents[1] / "tools"))
import jeu  # noqa: E402
from test_sources_scripts import AvecDossier, DEPENDANCES, FLUX, lancer, rapports  # noqa: E402
import flow_compare  # noqa: E402

AUJOURDHUI = dt.date.today()
EQUIPES = ["Alpha", "Beta", "Gamma", "Delta"]
REGLAGES = "portfolio_types: [Epic, Initiative]\nexcluded_projects: [SUP]\nwaiting_states: [Waiting, Ready for]\n"


def tickets() -> list[dict]:
    rng = random.Random(5)
    liste: list[dict] = []

    def ajouter(projet="PROJ", **kw):
        liste.append(jeu.issue(f"{projet}-{len(liste) + 1}", **kw))

    for type_ in ("Story", "Bug", "Task", "Spike", "Epic", "Initiative"):             # effectifs égaux
        for _ in range(8):
            c = jeu.moment(rng.randint(40, 150), rng.randint(9, 17), rng.randint(0, 59), AUJOURDHUI)
            ajouter(type_=type_, etat="Closed", categorie="Done", cree=c, resolu=c + dt.timedelta(days=rng.randint(2, 30), hours=1),
                    motif=rng.choice(["Done", "Done", "Rejected", "Won't Do", "Duplicate", "Obsolete"]), debut=c,
                    equipes=[rng.choice(EQUIPES)])
    for etat, categorie in (("In Progress", "In Progress"), ("In Review", "In Progress"), ("Testing", "In Progress"),
                            ("Waiting", "In Progress"), ("Ready for QA", "In Progress"), ("Open", "To Do"), ("Backlog", "To Do"),
                            ("To Do", "To Do"), ("Weird", "Other"), ("Odd", "Other"), ("Strange", "Other")):
        for _ in range(4):
            c = jeu.moment(rng.randint(5, 120), 10, 0, AUJOURDHUI)
            ajouter(type_=rng.choice(["Story", "Bug", "Task"]), etat=etat, categorie=categorie, cree=c, debut=c + dt.timedelta(days=1),
                    equipes=[rng.choice(EQUIPES)])
    for _ in range(6):                                                                  # projet écarté
        ajouter("SUP", type_="Bug", etat="Open", categorie="To Do", cree=jeu.moment(30, 10, 0, AUJOURDHUI), equipes=["Alpha"])
    for i in range(10):                                                                 # fermetures dans la même minute, deux projets
        c = jeu.moment(70, 9, 0, AUJOURDHUI)
        ajouter("BATCHA" if i % 2 else "BATCHB", type_="Story", etat="Closed", categorie="Done", cree=c,
                resolu=jeu.moment(9, 11, 30, AUJOURDHUI), motif="Done", debut=c, equipes=["Alpha"])
    return liste


def historique(liste: list[dict], graine: int) -> dict:
    etats = ["Definition", "Ready for Implementation", "Implementation", "Code Review (Impl)", "Verification", "Weird", "Odd", "Mystery"]
    cache = {}
    for t in liste:
        rng = random.Random(t["cle"])                      # les transitions d'un ticket ne dépendent pas de l'ordre
        c, transitions, precedent = t["cree"], [], None
        for etat in rng.sample(etats, 4):
            c += dt.timedelta(days=rng.randint(1, 9))
            transitions.append([c.strftime("%Y-%m-%dT%H:%M:%S.000+0200"), precedent, etat])
            precedent = etat
        cache[t["cle"]] = {"termine": bool(t["resolu"]), "transitions": transitions}
    cles = list(cache)
    random.Random(graine).shuffle(cles)
    return {c: cache[c] for c in cles}


class OrdreDesRapports(AvecDossier):
    def calculer(self, graine: int, fichiers: int = 1, inverser: bool = False):
        ws = self.dossier()
        (ws / "Flux-Lab").mkdir()
        (ws / "Flux-Lab" / "flux.yaml").write_text(REGLAGES, encoding="utf-8")
        liste = tickets()
        random.Random(graine).shuffle(liste)
        parts = [liste] if fichiers == 1 else [liste[:len(liste) // 2 + 10], liste[len(liste) // 2 - 10:]]
        if inverser:
            parts.reverse()
        chemins = []
        for i, part in enumerate(parts):
            chemin = ws / f"e{i}.csv"
            jeu.ecrire_csv(chemin, part)
            chemins.append(str(chemin))
        cache = ws / "t.json"
        cache.write_text(json.dumps(historique(liste, graine)), encoding="utf-8")
        sorties = {}
        for nom, script, args in (
                ("flux", FLUX, ("compute", *chemins, "--name", "x", "--today", AUJOURDHUI.isoformat(), "--no-comparison", "--points",
                                "--history", str(cache), "--dormant-from-history")),
                ("equipes", DEPENDANCES, ("compute", *chemins, "--name", "d", "--by", "team")),
                ("projets", DEPENDANCES, ("compute", *chemins, "--name", "p", "--by", "project"))):
            r = lancer(script, ws, *args)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            sorties[nom] = r.stdout.replace(str(ws), "WS")
        points = {p.name: p.read_text(encoding="utf-8") for p in sorted((ws / "Flux-Lab" / "tableaux").glob("*"))}
        return sorties, rapports(ws), points

    def test_deux_ordres_de_lecture_donnent_les_memes_rapports(self):
        a, b = self.calculer(1), self.calculer(2)
        self.assertEqual(a[0], b[0])                                       # sorties de la console
        self.assertEqual(sorted(a[1]), sorted(b[1]))
        for nom in a[1]:
            self.assertEqual(a[1][nom], b[1][nom], nom)                    # .md et .json, octet pour octet
        self.assertEqual(a[2], b[2])                                       # points de l'Aging WIP

    def test_un_export_en_deux_fichiers_dans_un_ordre_ou_l_autre(self):
        unique = self.calculer(1)
        deux = self.calculer(3, fichiers=2)
        inverse = self.calculer(4, fichiers=2, inverser=True)
        self.assertEqual(deux[2], inverse[2])
        for nom in unique[1]:
            if not nom.endswith(".md"):
                continue
            # les deux lectures ne diffèrent que par ce que la comparaison de rapports ignore (fusion, noms de fichiers)
            self.assertEqual(flow_compare.normaliser_rapport(unique[1][nom]), flow_compare.normaliser_rapport(deux[1][nom]), nom)
            self.assertEqual(flow_compare.normaliser_rapport(deux[1][nom]), flow_compare.normaliser_rapport(inverse[1][nom]), nom)

    def test_les_listes_sont_par_effectif_decroissant_puis_par_nom(self):
        rapport = self.calculer(7)[1]["flux-x-%s.md" % AUJOURDHUI.isoformat()]
        for ligne in rapport.splitlines():
            if ligne.startswith("- Clos sans livraison"):
                comptes = re.findall(r"([A-Za-z' ]+) (\d+)", ligne.split(" : ", 1)[1])
                valeurs = [(-int(n), nom.strip(", ")) for nom, n in comptes]
                self.assertEqual(valeurs, sorted(valeurs), ligne)
                return
        self.fail("ligne « Clos sans livraison » introuvable")


if __name__ == "__main__":
    unittest.main()
