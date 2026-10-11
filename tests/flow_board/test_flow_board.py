"""Tests de tools/flow_board.py sur des données inventées, dans un dossier temporaire.

Les rapports viennent de vrais calculs de flux_jira.py sur un export et un historique inventés (mêmes parcours que
tests/flux_jira) ; la bibliothèque de graphiques est remplacée par un faux ECharts (tests/flow_board/echarts_stub.js).
Le JavaScript de la page est exécuté sous Node dans un faux DOM (driver.js) si Node est installé.
Lancement : uv run --with pyyaml --with numpy python -m unittest discover -s tests/flow_board
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ICI = Path(__file__).resolve().parent
TOOLS = ICI.parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ICI.parent / "flux_jira"))
import flow_board as tf              # noqa: E402
import test_flux_jira as fx            # noqa: E402

NODE = shutil.which("node")
STUB = ICI / "echarts_stub.js"
CLE = re.compile(r"\b[A-Z][A-Z0-9_]+-\d+\b")
FRANCAIS = re.compile(r"[àâçéèêëîïôùûüÿœÀÂÇÉÈÊËÎÏÔÙÛÜŸŒ]|\b(les|des|une|pour|avec|dans|semaine|semaines|équipe|équipes|"
                      r"série|temps|jours|toutes|aucune|depuis|éléments|donnée|données)\b", re.IGNORECASE)

DEP = {"date": "2026-10-04", "mode": "orienté", "tronques": [], "boucles": [["Equipe B", "Equipe A"]],
       "equipes_tickets": {"Equipe A": 3, "Equipe B": 4, "(hors export)": 0},
       "aretes": [{"de": "Equipe B", "vers": "Equipe A", "ouvertes": 2, "inconnues": 0, "toutes": 3, "entre_epics": 0,
                   "bloquees_en_cours": 2, "age_bloquees": {"n": 2, "p50": 40, "p85": 55}, "oriente": True},
                  {"de": "Equipe A", "vers": "(hors export)", "ouvertes": 0, "inconnues": 1, "toutes": 1, "entre_epics": 0,
                   "bloquees_en_cours": 0, "age_bloquees": None, "oriente": True}]}


NOM = "serieconfidentielle"            # nom de la série : jamais dans la version anonyme


class Base(unittest.TestCase):
    YAML = ('waiting_states: ["Ready for"]\nboards:\n  series:\n    - name: ' + NOM + '\n      dependencies: dep\n'
            '      baseline: "2026-09-06"\n')
    PARCOURS = fx.TempsParSegment.PARCOURS
    preparer = fx.TempsParSegment.preparer

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.ws = cls.preparer_classe(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def preparer_classe(cls, racine: Path) -> Path:
        class Faux:                     # preparer() attend un TestCase : on lui donne ce qu'il utilise
            YAML, PARCOURS = cls.YAML, cls.PARCOURS
            def __init__(self):
                self.nettoyages = []
            def addCleanup(self, fonction, *args):
                self.nettoyages.append((fonction, args))
        faux = Faux()
        ws = fx.TempsParSegment.preparer(faux)       # crée son propre dossier temporaire : on le copie dans racine
        cible = racine / "ws"
        shutil.copytree(ws, cible)
        for fonction, args in faux.nettoyages:
            fonction(*args)
        env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(cible)}
        for date, extra in (("2026-09-06", ["--history", "--points", "--scope", "ABC"]),
                            ("2026-10-04", ["--history", "--points", "--dormant-from-history", "--scope", "ABC"])):
            r = subprocess.run(["uv", "run", str(fx.SCRIPT), "compute", str(cible / "export.csv"), "--name", NOM,
                                "--today", date, "--no-comparison", *extra], env=env, capture_output=True, text=True)
            assert r.returncode == 0, r.stdout + r.stderr
        (cible / "Flux-Lab" / "rapports" / "dependances-dep-2026-10-04.json").write_text(json.dumps(DEP), encoding="utf-8")
        return cible

    def generer(self, *args, ws=None, lib=STUB, env_extra=None, attendu=0):
        ws = ws or self.ws
        env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(ws), "PMZILLA_LAB_TODAY": "2026-10-04",
               "PMZILLA_LAB_SEED": "7"}
        if lib is not None:
            env["PMZILLA_LAB_ECHARTS"] = str(lib)
        else:
            env.pop("PMZILLA_LAB_ECHARTS", None)
        env.update(env_extra or {})
        r = subprocess.run(["uv", "run", str(TOOLS / "flow_board.py"), *args], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, attendu, r.stdout + r.stderr)
        return r

    def page(self, *args, **kw) -> tuple[str, dict]:
        self.generer(*args, **kw)
        suffixe = ("" if "fr" not in args else "-fr") + ("-anonyme" if "--anonymous" in args else "")
        chemin = (kw.get("ws") or self.ws) / "Flux-Lab" / "tableaux" / f"tableau-flux-2026-10-04{suffixe}.html"
        html = chemin.read_text(encoding="utf-8")
        brut = re.search(r'<script id="tf-data" type="application/json">(.*?)</script>', html, re.S).group(1)
        return html, json.loads(brut)

    def piloter(self, html_ou_donnees: dict) -> dict:
        fichier = Path(self.tmp.name) / "donnees.json"
        fichier.write_text(json.dumps(html_ou_donnees), encoding="utf-8")
        r = subprocess.run([NODE, str(ICI / "driver.js"), str(TOOLS / "flow_board_page.js"), str(fichier)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)


class Fichier(Base):
    def test_un_seul_fichier_autonome_hors_ligne(self):
        html, _ = self.page()
        chemin = self.ws / "Flux-Lab" / "tableaux" / "tableau-flux-2026-10-04.html"
        self.assertEqual(oct(chemin.stat().st_mode & 0o777), "0o600")
        self.assertEqual(oct(chemin.parent.stat().st_mode & 0o777), "0o700")
        self.assertIn("window.echarts", html)                       # la bibliothèque est dans le fichier
        self.assertNotRegex(html, r"https?://")                     # aucun lien ni appel réseau (le faux ECharts n'en a pas)
        self.assertNotRegex(html, r"<link\b|@import|<script[^>]+src=|<img\b|fetch\(|XMLHttpRequest|sendBeacon|WebSocket")

    def test_notre_code_ne_fait_aucun_appel_reseau(self):
        for nom in ("flow_board_page.js", "flow_board_page.css", "flow_board_page.html"):
            source = (TOOLS / nom).read_text(encoding="utf-8")
            self.assertNotRegex(source, r"https?://|fetch\(|XMLHttpRequest|sendBeacon|WebSocket|@import|<link\b|src=\"[^{]")

    def test_donnees_integrees_valides_sans_cle_ni_fichier(self):
        html, donnees = self.page()
        brut = json.dumps(donnees)
        self.assertNotRegex(brut, CLE)
        self.assertNotIn(".csv", brut)
        self.assertNotIn("</script", html.split('id="tf-data"')[1].split("</script>")[0])

    def test_noms_de_fichier_par_langue_et_option(self):
        self.generer("--language", "fr")
        self.assertTrue((self.ws / "Flux-Lab" / "tableaux" / "tableau-flux-2026-10-04-fr.html").exists())
        self.generer("--output", str(Path(self.tmp.name) / "x.html"))
        self.assertTrue((Path(self.tmp.name) / "x.html").exists())

    def test_anciennes_options_refusees_avec_le_nom_actuel(self):
        for ancien, nouveau in (("--langue", "--language"), ("--anonyme", "--anonymous")):
            r = self.generer(ancien, attendu=2)
            self.assertIn(f"« {ancien} » n'existe plus ; utiliser « {nouveau} »", r.stderr)
        self.assertFalse((self.ws / "Flux-Lab" / "tableaux" / "tableau-flux-2026-10-04-fr-anonyme.html").exists())

    def test_reglages_boards_anciens_noms_refuses(self):
        ancien = ("boards:\n  series:\n    - nom: " + NOM + "\n      dependances: dep\n      dependances_projets: dep-p\n"
                  "      base: '2026-09-06'\n")
        nouveau = ("boards:\n  series:\n    - name: " + NOM + "\n      dependencies: dep\n      project_dependencies: dep-p\n"
                   "      baseline: '2026-09-06'\n")
        fichier = Path(self.tmp.name) / "flux-test.yaml"
        fichier.write_text(ancien, encoding="utf-8")
        with unittest.mock.patch.object(tf, "CONFIG", fichier), self.assertRaises(SystemExit) as c:
            tf.reglages()
        self.assertIn("« boards.series.nom » n'existe plus ; utiliser « boards.series.name »", str(c.exception))
        fichier.write_text(nouveau, encoding="utf-8")
        with unittest.mock.patch.object(tf, "CONFIG", fichier), contextlib.redirect_stderr(io.StringIO()) as err:
            lus = tf.reglages()
        self.assertEqual(err.getvalue(), "")
        self.assertEqual(lus, [{"nom": NOM, "dependances": "dep", "dependances_projets": "dep-p", "base": "2026-09-06"}])

    def test_impression_et_themes_dans_le_css(self):
        css = (TOOLS / "flow_board_page.css").read_text(encoding="utf-8")
        self.assertIn("@media print", css)
        self.assertIn("break-inside:avoid", css)
        self.assertIn("prefers-color-scheme:dark", css)
        self.assertIn("print-color-adjust:exact", css)


class Donnees(Base):
    def test_vue_produit_puis_equipes_par_ordre_alphabetique(self):
        _, donnees = self.page()
        s = donnees["series"][0]
        self.assertEqual(s["teams"], ["Equipe A", "Equipe B"])
        self.assertEqual(list(s["views"]), ["", "Equipe A", "Equipe B"])    # la vue produit d'abord
        self.assertEqual(s["name"], NOM)

    def test_contenu_de_la_vue_produit(self):
        _, donnees = self.page()
        v = donnees["series"][0]["views"][""]
        self.assertEqual(len(v["weeks"]), len(v["departures"]))
        self.assertEqual(len(v["arrivals"]), len(v["weeks"]))
        self.assertEqual(v["cfd"]["delivered"][-1], 4)
        self.assertIn("implementation", v["segments"]["left"])
        self.assertIsNotNone(v["delivery"]["commitment"])
        self.assertIsNotNone(v["efficiency"]["aggregate"])
        self.assertEqual(v["wip"]["total"], 3)
        self.assertEqual(len(v["history"]), 2)
        self.assertEqual(v["base"]["date"], "2026-09-06")
        self.assertEqual(donnees["series"][0]["commitment"], "pret")

    def test_points_de_l_aging_wip_sans_cle(self):
        _, donnees = self.page()
        pts = donnees["series"][0]["points"]
        self.assertEqual(len(pts["items"]), 3)
        self.assertTrue({p["nature"] for p in pts["items"]} <= {"active", "waiting", "dormant"})   # identifiants internes
        self.assertEqual({tuple(sorted(p)) for p in pts["items"]},
                         {("age", "age_segment", "nature", "segment", "status", "team")})

    def test_base_non_comparable_signalee(self):
        _, donnees = self.page()
        b = donnees["series"][0]["baseline"]
        self.assertTrue(b["found"])
        self.assertEqual(b["differences"], ["dormant source"])     # la base n'a pas les dormants de l'historique

    def test_dependances_aretes_et_noeuds_alphabetiques(self):
        _, donnees = self.page()
        dep = donnees["series"][0]["dependencies"][0]
        self.assertEqual([n["name"] for n in dep["nodes"]], ["Equipe A", "Equipe B", "(outside export)"])
        self.assertEqual([(e["from"], e["to"]) for e in dep["edges"]],
                         [("Equipe A", "(outside export)"), ("Equipe B", "Equipe A")])
        self.assertEqual(dep["loops"], [["Equipe B", "Equipe A"]])

    def test_dependances_sans_aretes_reconstruites_des_matrices(self):
        ancien = {"date": "2026-09-06", "mode": "orienté", "matrice_ouverte": [["B", "A", 2]],
                  "matrice_inconnue": [["B", "A", 1]], "matrice_totale": [["B", "A", 4]], "matrice_portefeuille": []}
        dep = tf.construire_dependances(ancien, tf.Noms("en"), projets=False)
        self.assertEqual([(e["from"], e["to"], e["open"], e["unknown"], e["all"]) for e in dep["edges"]], [("B", "A", 2, 1, 4)])

    def test_fonctions_pures(self):
        self.assertEqual(tf.pc({"85": 12}, 85), 12.0)
        self.assertIsNone(tf.pc(None, 85))
        self.assertEqual(tf.repartition_wip(10, {"actif": 6, "attente": 3, "dormant": 1}, None),
                         {"total": 10, "active": 6, "waiting": 3, "dormant": 1})
        self.assertEqual(tf.repartition_wip(10, None, {"actif": 7, "attente": 3}),
                         {"total": 10, "active": 7, "waiting": 3, "dormant": None})
        self.assertEqual(tf.repartition_wip(10, None, None), {"total": 10, "active": None, "waiting": None, "dormant": None})
        self.assertIsNone(tf.repartition_wip(None, None, None))
        noms = tf.Noms("en")
        self.assertEqual(sorted(["b", "(no team)", "A", "c"], key=lambda x: tf.cle_tri(x, noms)), ["A", "b", "c", "(no team)"])
        self.assertNotIn("</", tf.json_sur({"x": "</script><!--"}))

    def test_equipes_speciales_traduites(self):
        n = tf.Noms("en")
        self.assertEqual(n.equipe("(sans équipe)"), "(no team)")
        self.assertEqual(n.equipe("(hors export)"), "(outside export)")
        self.assertEqual(n.equipe("(sans équipe : ABC)"), "(no team: ABC)")
        self.assertEqual(tf.Noms("fr").equipe("(hors export)"), "(hors export)")


class Langues(Base):
    def test_anglais_par_defaut_et_aucun_texte_francais(self):
        html, donnees = self.page()
        self.assertEqual(donnees["lang"], "en")
        self.assertIn('<html lang="en">', html)
        for cle, valeur in donnees["texts"].items():
            self.assertNotRegex(valeur, FRANCAIS, cle)
        for cle, valeur in donnees["glossary"].items():
            self.assertNotRegex(valeur, FRANCAIS, cle)
        for cle, valeur in tf.TEXTES["en"].items():
            self.assertNotRegex(valeur, FRANCAIS, cle)
        squelette = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
        self.assertNotRegex(squelette, FRANCAIS)

    def test_memes_cles_dans_les_deux_langues(self):
        self.assertEqual(set(tf.TEXTES["en"]), set(tf.TEXTES["fr"]))
        for cle in tf.CLES_GLOSSAIRE:
            self.assertIn(cle, tf.glossaire.GLOSSAIRE["en"])
            self.assertIn(cle, tf.glossaire.GLOSSAIRE["fr"])
        self.assertEqual(set(tf.glossaire.GLOSSAIRE["en"]), set(tf.glossaire.GLOSSAIRE["fr"]))

    def test_vocabulaire_du_flux_en_anglais(self):
        glossaire = " ".join(tf.glossaire.GLOSSAIRE["en"].values()) + " " + " ".join(tf.TEXTES["en"].values())
        for terme in ("throughput", "arrivals", "departures", "lead time", "delivery lead time", "WIP", "aging WIP",
                      "cumulative flow diagram", "flow efficiency", "segment", "commitment point", "Monte Carlo forecast"):
            self.assertIn(terme.lower(), glossaire.lower(), terme)

    def test_francais_avec_option(self):
        html, donnees = self.page("--language", "fr")
        self.assertEqual(donnees["lang"], "fr")
        self.assertIn('<html lang="fr">', html)
        self.assertEqual(donnees["texts"]["sec_cfd"], "Diagramme de flux cumulé")
        self.assertIn("Comment lire", donnees["texts"]["how_to_read"])
        self.assertEqual(donnees["series"][0]["segment_labels"]["revue_verification"], "Revue et vérification")

    def test_etats_jira_et_segments_inconnus_inchanges(self):
        _, donnees = self.page()
        etats = {p["status"] for p in donnees["series"][0]["points"]["items"]}
        self.assertTrue(etats <= {"Implementation - Ongoing", "In Progress"} or etats)
        self.assertIn("Implementation - Ongoing", etats)                  # nom d'état Jira tel quel
        self.assertEqual(donnees["series"][0]["segment_labels"]["implementation"], "Implementation")
        self.assertEqual(tf.libelle_segment("mon_segment", tf.TEXTES["en"]), "mon_segment")

    def test_formats_dates_et_nombres(self):
        _, donnees = self.page()
        self.assertTrue(all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", w) for w in donnees["series"][0]["views"][""]["weeks"]))
        self.assertEqual(donnees["texts"]["unit_day"], "d")
        self.assertEqual(donnees["texts"]["decimal"], ".")
        self.assertEqual(tf.TEXTES["fr"]["unit_day"], "j")
        self.assertEqual(tf.TEXTES["fr"]["decimal"], ",")


@unittest.skipUnless(NODE, "Node n'est pas installé : le JavaScript de la page n'est pas exécuté")
class JavaScript(Base):
    def test_la_page_s_execute_sans_erreur_pour_chaque_choix(self):
        _, donnees = self.page()
        r = self.piloter(donnees)
        self.assertEqual(r["errors"], [])
        etapes = {e["label"]: e for e in r["steps"]}
        for libelle in ("initial", "team Equipe A", "team Equipe B", "all teams", "aging by segment", "aging by status",
                        "print", "after print"):
            self.assertIn(libelle, etapes)
            self.assertGreaterEqual(etapes[libelle]["charts"], 8, libelle)       # tous les graphiques sont construits
        self.assertTrue(r["hasTeamSelector"])

    def test_aucun_francais_dans_la_page_anglaise_rendue(self):
        _, donnees = self.page()
        r = self.piloter(donnees)
        for e in r["steps"]:
            self.assertNotRegex(e["text"], FRANCAIS, e["label"])
            for chaine in e["optionStrings"]:
                self.assertNotRegex(chaine, FRANCAIS, e["label"])

    def test_aucune_cle_de_ticket_dans_la_page_rendue(self):
        _, donnees = self.page()
        r = self.piloter(donnees)
        for e in r["steps"]:
            self.assertNotRegex(e["text"], CLE)
            self.assertFalse([c for c in e["optionStrings"] if CLE.search(c)])

    def test_page_francaise_rendue(self):
        _, donnees = self.page("--language", "fr")
        r = self.piloter(donnees)
        self.assertEqual(r["errors"], [])
        self.assertIn("Comment lire", r["steps"][0]["text"])
        self.assertIn("Diagramme de flux cumulé", r["steps"][0]["text"])

    def test_la_couleur_ne_porte_jamais_seule_l_information(self):
        _, donnees = self.page()
        options = self.options_initiales(donnees)
        for o in options:
            if o["series"][0]["type"] != "graph":
                self.assertTrue(o["aria"]["decal"]["show"])                    # motifs en plus des couleurs
        aging = [o for o in options if o["series"][0]["type"] == "scatter"][0]
        self.assertEqual({s["symbol"] for s in aging["series"]}, {"circle", "triangle", "diamond"})
        flux = [o for o in options if o["series"][0]["type"] == "line" and "stack" not in o["series"][0]][0]
        self.assertEqual({s["symbol"] for s in flux["series"]}, {"circle", "triangle"})
        self.assertEqual({s["lineStyle"]["type"] for s in flux["series"]}, {"solid", "dashed"})
        graphe = [o for o in options if o["series"][0]["type"] == "graph"][0]
        self.assertTrue(all(n["label"]["show"] for n in graphe["series"][0]["data"]))     # libellés sur chaque noeud

    def options_initiales(self, donnees):
        fichier = Path(self.tmp.name) / "d2.json"
        fichier.write_text(json.dumps(donnees), encoding="utf-8")
        r = subprocess.run([NODE, str(ICI / "driver.js"), str(TOOLS / "flow_board_page.js"), str(fichier), "options"],
                           capture_output=True, text=True)
        return json.loads(r.stdout)["initialOptions"]

    def test_graphe_noeuds_alphabetiques_et_sans_classement(self):
        _, donnees = self.page()
        graphe = [o for o in self.options_initiales(donnees) if o["series"][0]["type"] == "graph"][0]
        noms = [n["name"] for n in graphe["series"][0]["data"]]
        self.assertEqual(noms, sorted(noms, key=lambda x: (x.startswith("("), x.casefold())))

    def test_constructeurs_sous_theme_sombre(self):
        script = (f"const p=require({json.dumps(str(TOOLS / 'flow_board_page.js'))});"
                  f"const d=require({json.dumps(str(Path(self.tmp.name) / 'donnees.json'))});"
                  "const c=new p.Ctx(d,true);const s=d.series[0],v=s.views[''];"
                  "const r=[p.buildFlow(v,c),p.buildCfd(v,c,s.segment_order,s.segment_labels),p.buildSegments(v,c,s.segment_labels),"
                  "p.buildAging(s.points,'','status',v,c,s.segment_labels),p.buildWip(v,c),p.buildWipHistory(v,c),"
                  "p.buildLeadTimes(v,c),p.buildEfficiency(v,c),p.buildGraph(s.dependencies[0],'',c)];"
                  "console.log(JSON.stringify(r.map(x=>x.empty?'vide':'ok')));")
        _, donnees = self.page()
        (Path(self.tmp.name) / "donnees.json").write_text(json.dumps(donnees), encoding="utf-8")
        r = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), ["ok"] * 9)


VRAIS_NOMS = ("Equipe A", "Equipe B", NOM, "ABC", "(hors export)", "(sans équipe)")


class Anonyme(Base):
    """--anonyme : aucun vrai nom n'entre dans le fichier ; la correspondance est stable d'un mois à l'autre."""

    def copie(self) -> Path:
        cible = Path(tempfile.mkdtemp(dir=self.tmp.name)) / "ws"
        shutil.copytree(self.ws, cible)
        return cible

    def table(self, ws) -> dict:
        import yaml
        return yaml.safe_load((ws / "Flux-Lab" / "tableaux" / "anonymes.yaml").read_text(encoding="utf-8"))

    def test_aucun_vrai_nom_dans_le_fichier(self):
        ws = self.copie()
        self.generer("--anonymous", ws=ws)
        chemin = ws / "Flux-Lab" / "tableaux" / "tableau-flux-2026-10-04-anonyme.html"
        html = chemin.read_text(encoding="utf-8")
        for nom in VRAIS_NOMS:
            self.assertNotIn(nom, html, nom)
        self.assertNotRegex(html, r"\bABC\b")
        self.assertEqual(oct(chemin.stat().st_mode & 0o777), "0o600")
        self.assertNotIn(NOM, chemin.name)

    def test_libelles_anonymes_et_ordre_alphabetique(self):
        ws = self.copie()
        _, donnees = self.page("--anonymous", ws=ws)
        s = donnees["series"][0]
        self.assertRegex(s["name"], r"^Series \d+$")
        self.assertEqual(sorted(s["teams"]), s["teams"])                      # alphabétique sur les libellés anonymes
        self.assertTrue(all(re.fullmatch(r"Team [A-Z]", t) for t in s["teams"]))
        self.assertEqual(s["scope"], [s["scope"][0]])
        self.assertRegex(s["scope"][0], r"^Project [A-Z]$")
        dep = s["dependencies"][0]
        self.assertIn("(outside export)", [n["name"] for n in dep["nodes"]])
        self.assertTrue(donnees["anonymous"])

    def test_table_de_correspondance_hors_git_en_600(self):
        ws = self.copie()
        self.generer("--anonymous", ws=ws)
        chemin = ws / "Flux-Lab" / "tableaux" / "anonymes.yaml"
        self.assertEqual(oct(chemin.stat().st_mode & 0o777), "0o600")
        table = self.table(ws)
        self.assertEqual(set(table["equipes"]), {"Equipe A", "Equipe B"})
        self.assertEqual(set(table["projets"]), {"ABC"})
        self.assertEqual(set(table["series"]), {NOM})
        self.assertEqual(len(set(table["equipes"].values())), 2)
        self.assertTrue(all(re.fullmatch(r"[A-Z]", v) for v in table["equipes"].values()))

    def test_lettres_stables_d_une_generation_a_l_autre(self):
        ws = self.copie()
        _, premiere = self.page("--anonymous", ws=ws, env_extra={"PMZILLA_LAB_SEED": "1"})
        table = self.table(ws)
        _, seconde = self.page("--anonymous", ws=ws, env_extra={"PMZILLA_LAB_SEED": "999"})   # autre graine : rien ne change
        self.assertEqual(premiere["series"][0]["teams"], seconde["series"][0]["teams"])
        self.assertEqual(premiere["series"][0]["name"], seconde["series"][0]["name"])
        self.assertEqual(self.table(ws), table)

    def test_nom_nouveau_recoit_la_premiere_lettre_libre(self):
        ws = self.copie()
        self.generer("--anonymous", ws=ws)
        avant = self.table(ws)["equipes"]
        libres = [chr(65 + i) for i in range(26) if chr(65 + i) not in avant.values()]
        # une troisième équipe apparaît dans le dernier rapport
        fichier = ws / "Flux-Lab" / "rapports" / f"flux-{NOM}-2026-10-04.json"
        rapport = json.loads(fichier.read_text(encoding="utf-8"))
        rapport["par_equipe"]["Equipe C"] = dict(rapport["par_equipe"]["Equipe A"])
        fichier.write_text(json.dumps(rapport), encoding="utf-8")
        self.generer("--anonymous", ws=ws)
        apres = self.table(ws)["equipes"]
        self.assertEqual({k: v for k, v in apres.items() if k in avant}, avant)       # les existantes ne bougent pas
        self.assertEqual(apres["Equipe C"], libres[0])

    def test_francais_anonyme(self):
        ws = self.copie()
        _, donnees = self.page("--anonymous", "--language", "fr", ws=ws)
        s = donnees["series"][0]
        self.assertRegex(s["name"], r"^Série \d+$")
        self.assertTrue(all(re.fullmatch(r"Équipe [A-Z]", t) for t in s["teams"]))
        self.assertEqual(s["dependencies"][0]["nodes"][-1]["name"], "(hors export)")

    def test_version_complete_garde_les_vrais_noms(self):
        ws = self.copie()
        html, donnees = self.page(ws=ws)
        self.assertEqual(donnees["series"][0]["teams"], ["Equipe A", "Equipe B"])
        self.assertFalse((ws / "Flux-Lab" / "tableaux" / "anonymes.yaml").exists())

    def test_correspondance_illisible_arrete_sans_ecraser(self):
        ws = self.copie()
        chemin = ws / "Flux-Lab" / "tableaux" / "anonymes.yaml"
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text("equipes: [pas, un, dictionnaire", encoding="utf-8")
        r = self.generer("--anonymous", ws=ws, attendu=1)
        self.assertIn("anonymes.yaml", r.stderr)
        self.assertEqual(chemin.read_text(encoding="utf-8"), "equipes: [pas, un, dictionnaire")

    def test_etiquettes_au_dela_de_26(self):
        self.assertEqual([tf.etiquette(i) for i in (0, 25, 26, 27, 51, 52, 701, 702)],
                         ["A", "Z", "AA", "AB", "AZ", "BA", "ZZ", "AAA"])

    def test_premier_tirage_au_hasard_puis_ordre(self):
        import tempfile as tmpmod
        chemin = Path(tmpmod.mkdtemp(dir=self.tmp.name)) / "a.yaml"
        os.environ["PMZILLA_LAB_SEED"] = "3"
        try:
            n = tf.NomsAnonymes("en", chemin)
            premieres = [n.equipe(x) for x in ("A", "B", "C", "D")]
            n.sauver()
            suivante = tf.NomsAnonymes("en", chemin)
            libre = sorted(set(tf.etiquette(i) for i in range(26)) - set(suivante.table["equipes"].values()))[0]
            self.assertEqual(suivante.equipe("E"), f"Team {libre}")
        finally:
            del os.environ["PMZILLA_LAB_SEED"]
        self.assertEqual(len(set(premieres)), 4)
        self.assertNotEqual(premieres, ["Team A", "Team B", "Team C", "Team D"])          # tirées au hasard (graine 3)


@unittest.skipUnless(NODE, "Node n'est pas installé")
class AnonymeJavaScript(Base):
    def test_la_page_anonyme_rendue_ne_contient_aucun_vrai_nom(self):
        ws = Path(tempfile.mkdtemp(dir=self.tmp.name)) / "ws"
        shutil.copytree(self.ws, ws)
        _, donnees = self.page("--anonymous", ws=ws)
        r = self.piloter(donnees)
        self.assertEqual(r["errors"], [])
        for e in r["steps"]:
            for nom in VRAIS_NOMS:
                self.assertNotIn(nom, e["text"], (e["label"], nom))
                self.assertFalse([c for c in e["optionStrings"] if nom in c], (e["label"], nom))
        self.assertIn("Anonymous version", r["steps"][0]["text"])


VRAI_ECHARTS = Path(os.environ.get("PMZILLA_LAB_ECHARTS_REEL") or TOOLS / "vendor" / "echarts.min.js")


@unittest.skipUnless(NODE and VRAI_ECHARTS.is_file(),
                     "ECharts n'est pas dans tools/vendor/ (zsh tools/vendor/telecharger_echarts.sh) : rendu réel non testé")
class RenduReel(Base):
    """Chaque graphique est rendu par le vrai ECharts (SVG côté serveur) : une option invalide fait échouer le test."""

    def rendre(self, *args):
        _, donnees = self.page(*args)
        fichier = Path(self.tmp.name) / "reel.json"
        fichier.write_text(json.dumps(donnees), encoding="utf-8")
        r = subprocess.run([NODE, str(ICI / "rendu_reel.js"), str(VRAI_ECHARTS), str(TOOLS / "flow_board_page.js"), str(fichier)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_tous_les_graphiques_se_rendent_en_clair_et_en_sombre(self):
        sorties = self.rendre()
        rendus = [x for x in sorties if not x.get("vide")]
        self.assertTrue(rendus)
        for x in rendus:
            self.assertGreater(x["taille"], 800, x)
            self.assertGreater(x["formes"], 3, x)                       # le graphique contient bien des formes
        noms = {x["nom"] for x in rendus}
        self.assertTrue({"flow", "cfd", "segments", "agingStatus", "agingSegment", "wip", "leadTimes", "efficiency",
                         "graph0"} <= noms, noms)
        self.assertEqual({x["dark"] for x in rendus}, {False, True})

    def test_les_points_de_l_aging_wip_sont_dessines(self):
        sorties = self.rendre()
        aging = [x for x in sorties if x["nom"] == "agingStatus" and x["team"] == "" and not x["dark"] and not x.get("vide")]
        self.assertTrue(aging)
        self.assertGreater(aging[0]["formes"], 30)                        # axes, grille et les 3 points

    def test_rendu_francais(self):
        self.assertTrue([x for x in self.rendre("--language", "fr") if not x.get("vide")])


class Robustesse(Base):
    def copie(self) -> Path:
        cible = Path(tempfile.mkdtemp(dir=self.tmp.name)) / "ws"
        shutil.copytree(self.ws, cible)
        return cible

    def test_bibliotheque_absente(self):
        r = self.generer(lib=Path(self.tmp.name) / "absent.js", attendu=1)
        self.assertIn("telecharger_echarts.sh", r.stderr)

    def test_empreinte_verifiee(self):
        lib = Path(self.tmp.name) / "lib.js"
        lib.write_text("window.echarts={};", encoding="utf-8")
        empreinte = Path(self.tmp.name) / "lib.sha256"
        empreinte.write_text(hashlib.sha256(lib.read_bytes()).hexdigest() + "  lib.js\n", encoding="utf-8")
        self.assertEqual(tf.lire_lib(lib, empreinte), "window.echarts={};")
        lib.write_text("window.echarts={evil:1};", encoding="utf-8")
        with self.assertRaises(tf.Arret) as e:
            tf.lire_lib(lib, empreinte)
        self.assertIn("SHA-256", str(e.exception))

    def test_aucune_serie_page_vide_sans_erreur(self):
        ws = Path(tempfile.mkdtemp(dir=self.tmp.name)) / "ws"
        (ws / "Flux-Lab" / "rapports").mkdir(parents=True)
        _, donnees = self.page(ws=ws)
        self.assertEqual(donnees["series"], [])
        if NODE:
            r = self.piloter(donnees)
            self.assertEqual(r["errors"], [])
            self.assertIn(tf.TEXTES["en"]["empty_page"], r["steps"][0]["text"])

    def test_rapport_illisible_ignore(self):
        ws = self.copie()
        for f in (ws / "Flux-Lab" / "rapports").glob(f"flux-{NOM}-*.json"):
            f.write_text("{pas du json", encoding="utf-8")
        _, donnees = self.page(ws=ws)
        self.assertEqual(donnees["series"], [])

    def test_ancien_format_de_rapport_tolere(self):
        ws = self.copie()
        rap = ws / "Flux-Lab" / "rapports"
        for f in rap.glob(f"flux-{NOM}-*.json"):
            r = json.loads(f.read_text(encoding="utf-8"))
            for cle in ("temps_par_segment", "arrivees_par_semaine", "wip_repartition", "wip_attente", "dormants"):
                r.pop(cle, None)
            for e in r["par_equipe"].values():
                for cle in ("arrivees_par_semaine", "wip_repartition", "wip_attente"):
                    e.pop(cle, None)
            f.write_text(json.dumps(r), encoding="utf-8")
        (rap / "dependances-dep-2026-10-04.json").unlink()
        _, donnees = self.page(ws=ws)
        v = donnees["series"][0]["views"][""]
        self.assertIsNone(v["cfd"])
        self.assertIsNone(v["segments"])
        self.assertIsNone(v["arrivals"])
        if NODE:
            r = self.piloter(donnees)
            self.assertEqual(r["errors"], [])
            self.assertIn(tf.TEXTES["en"]["cfd_missing"], r["steps"][0]["text"])
            self.assertIn(tf.TEXTES["en"]["graph_missing"], r["steps"][0]["text"])

    def test_series_recent_ignoree_sans_reglage(self):
        ws = self.copie()
        (ws / "Flux-Lab" / "flux.yaml").write_text("waiting_states: []\n", encoding="utf-8")
        rap = ws / "Flux-Lab" / "rapports"
        shutil.copy(rap / f"flux-{NOM}-2026-10-04.json", rap / f"flux-{NOM}-recent-2026-10-04.json")
        _, donnees = self.page(ws=ws)
        self.assertEqual([s["name"] for s in donnees["series"]], [NOM])

    def test_le_prefixe_de_serie_est_exact(self):
        ws = self.copie()
        rap = ws / "Flux-Lab" / "rapports"
        shutil.copy(rap / f"flux-{NOM}-2026-10-04.json", rap / f"flux-{NOM}-recent-2026-10-04.json")
        self.assertEqual([d for d, _ in tf.fichiers_dates(rap, f"flux-{NOM}")], ["2026-09-06", "2026-10-04"])


if __name__ == "__main__":
    unittest.main()
