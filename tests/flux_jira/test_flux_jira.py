"""Tests de flux_jira.py sur des exports synthétiques (aucun export réel, aucun nom réel).

    uv run --with pyyaml --with numpy python -m unittest discover -s tests/flux_jira -v

- un export à l'ancien format (sans Key ni Status Category, sans types_portefeuille ni projets_exclus) doit
  redonner exactement le rapport de référence, produit par la version précédente du script ;
- un export multi-projets en deux fichiers (deux workflows, Epics et RN Tasks à écarter, un projet exclu,
  des tickets en double) est fusionné, classé par catégorie d'état et filtré.
"""
import csv
import datetime as dt
import json
import os
import random
import subprocess
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ICI = Path(__file__).resolve().parent
SCRIPT = ICI.parent.parent / "tools" / "flux_jira.py"
FMT = "%d/%b/%Y %H:%M"
AUJOURDHUI = dt.date(2026, 10, 4)


def lancer(workspace: Path, *args: str) -> str:
    env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(workspace)}
    r = subprocess.run(["uv", "run", str(SCRIPT), *args], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def sans_lecture(md: str) -> str:
    """Le rapport sans la section fixe « Comment lire ce rapport », dont les définitions citent tous les termes."""
    debut = md.index("## Comment lire ce rapport")
    return md[:debut] + md[md.index("## Limites"):]


def p(valeurs: dict, k: int):
    """Percentile d'un rapport JSON relu (clés en chaînes)."""
    return valeurs.get(str(k), valeurs.get(k))


def ecrire_yaml(workspace: Path, texte: str) -> None:
    (workspace / "Flux-Lab").mkdir(parents=True, exist_ok=True)
    (workspace / "Flux-Lab" / "flux.yaml").write_text(texte, encoding="utf-8")


def construire(rng: random.Random, projet: str, workflow: dict, n: int, equipes: list[str],
               types: list[str], depart: int = 1) -> list[dict]:
    """Tickets synthétiques d'un projet : clés ABC-1…, états et catégories d'un workflow."""
    lignes = []
    for i in range(n):
        cree = AUJOURDHUI - dt.timedelta(days=rng.randint(10, 200))
        r = rng.random()
        if r < 0.5:
            etat, cat = workflow["termine"]
            resolu = min(cree + dt.timedelta(days=rng.randint(3, 90)), AUJOURDHUI - dt.timedelta(days=8))
            motif = "Done"
        elif r < 0.8:
            etat, cat = rng.choice(workflow["en_cours"])
            resolu, motif = None, ""
        else:
            etat, cat = rng.choice(workflow["a_faire"])
            resolu, motif = None, ""
        lignes.append({"cle": f"{projet}-{depart + i}", "type": rng.choice(types), "etat": etat, "categorie": cat,
                       "cree": cree, "resolu": resolu, "motif": motif, "equipe": rng.choice(equipes),
                       "debut": cree + dt.timedelta(days=2) if cat != "To Do" else None})
    return lignes


WORKFLOW_1 = {"termine": ("Done", "Done"), "en_cours": [("In Progress", "In Progress"), ("In Review", "In Progress")],
              "a_faire": [("Open", "To Do")]}
WORKFLOW_2 = {"termine": ("Closed", "Done"), "en_cours": [("Doing", "In Progress"), ("Validation", "In Progress")],
              "a_faire": [("Waiting", "To Do")]}


def ecrire_csv(chemin: Path, lignes: list[dict], avec_categorie: bool = True) -> None:
    with chemin.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        entete = ["Issue key", "Issue Type", "Status"] + (["Status Category"] if avec_categorie else []) + [
            "Created", "Resolved", "Resolution", "Status Category Changed", "Team"]
        w.writerow(entete)
        for t in lignes:
            ligne = [t["cle"], t["type"], t["etat"]] + ([t["categorie"]] if avec_categorie else []) + [
                t["cree"].strftime(FMT), t["resolu"].strftime(FMT) if t["resolu"] else "", t["motif"],
                t["debut"].strftime(FMT) if t["debut"] else "", t["equipe"]]
            w.writerow(ligne)


class AncienFormat(unittest.TestCase):
    def test_rapport_identique_a_la_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            lancer(ws, "compute", str(ICI / "ancien_export.csv"), "--name", "ancien",
                   "--today", AUJOURDHUI.isoformat(), "--no-comparison")
            rapports = ws / "Flux-Lab" / "rapports"
            # rapport gelé d'avant la suppression de --dormants : seule la phrase du glossaire sur les dormants change
            attendu = (ICI / "ancien_rapport.md").read_text(encoding="utf-8")
            ancienne = "(seulement quand un export des dormants est fourni)"
            nouvelle = "(déduit de l'historique des états, option --dormant-from-history)"
            self.assertIn(ancienne, attendu)
            self.assertEqual((rapports / "flux-ancien-2026-10-04.md").read_text(encoding="utf-8"),
                             attendu.replace(ancienne, nouvelle))
            self.assertEqual(json.loads((rapports / "flux-ancien-2026-10-04.json").read_text(encoding="utf-8")),
                             json.loads((ICI / "ancien_rapport.json").read_text(encoding="utf-8")))


class MultiProjets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = random.Random(3)
        equipes = ["Equipe A", "Equipe B", "Equipe C"]
        cls.lot1 = construire(rng, "ABC", WORKFLOW_1, 80, equipes, ["Story", "Task", "Epic"])
        cls.lot2 = construire(rng, "DEF", WORKFLOW_2, 80, equipes, ["Story", "RN Task", "Bug"])
        cls.lot2 += construire(rng, "BUG", WORKFLOW_2, 30, equipes, ["Bug"])
        # tickets présents dans les deux fichiers (fusion par clé : le dernier fichier l'emporte)
        cls.lot2 += [dict(t) for t in cls.lot1[:7]]
        cls.attendu = {}
        par_cle = {t["cle"]: t for t in cls.lot1 + cls.lot2}
        cls.fusion = list(par_cle.values())
        cls.doublons = len(cls.lot1 + cls.lot2) - len(cls.fusion)

    def lancer_calcul(self, avec_categorie=True, equipes_en_plus=0):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ws = Path(tmp.name)
        ecrire_yaml(ws, "portfolio_types: [Epic, RN Task]\nexcluded_projects: [BUG]\n")
        lot1, lot2 = list(self.lot1), list(self.lot2)
        for i in range(equipes_en_plus):
            lot1.append({**lot1[0], "cle": f"ABC-9{i}", "equipe": f"Equipe X{i}", "type": "Story"})
        ecrire_csv(ws / "a.csv", lot1, avec_categorie)
        ecrire_csv(ws / "b.csv", lot2, avec_categorie)
        lancer(ws, "compute", str(ws / "a.csv"), str(ws / "b.csv"), "--name", "multi",
               "--today", AUJOURDHUI.isoformat(), "--no-comparison")
        rap = ws / "Flux-Lab" / "rapports"
        return (json.loads((rap / "flux-multi-2026-10-04.json").read_text(encoding="utf-8")),
                (rap / "flux-multi-2026-10-04.md").read_text(encoding="utf-8"))

    def gardes(self):
        return [t for t in self.fusion if t["type"] not in ("Epic", "RN Task") and not t["cle"].startswith("BUG-")]

    def test_ecartes_par_type_et_par_projet(self):
        r, md = self.lancer_calcul()
        epics = [t for t in self.fusion if t["type"] in ("Epic", "RN Task")]
        bugs = [t for t in self.fusion if t["cle"].startswith("BUG-")]
        attendu_total = len({t["cle"] for t in epics + bugs})
        self.assertEqual(r["ecartes"]["total"], attendu_total)
        self.assertEqual(r["ecartes"]["par_type"], dict(Counter(t["type"] for t in epics)))
        self.assertEqual(r["ecartes"]["par_projet"], {"BUG": len(bugs)})
        self.assertIn("Écartés du débit", md)

    def test_fusion_par_cle(self):
        r, md = self.lancer_calcul()
        self.assertEqual(r["exports"], {"fichiers": 2, "doublons_retires": self.doublons})
        self.assertIn("Fusion de 2 exports par clé", md)

    def test_categorie_decide_en_cours_et_a_faire(self):
        r, _ = self.lancer_calcul()
        gardes = self.gardes()
        self.assertEqual(r["classement"], "catégorie d'état")
        self.assertEqual(r["wip"], sum(1 for t in gardes if not t["resolu"] and t["categorie"] == "In Progress"))
        self.assertEqual(r["a_faire"], sum(1 for t in gardes if not t["resolu"] and t["categorie"] == "To Do"))
        self.assertIn("Doing", r["wip_par_etat"])           # état absent des listes de flux.yaml
        self.assertEqual(r["etats_non_classes"], {})

    def test_sans_categorie_les_listes_de_flux_yaml_servent(self):
        r, _ = self.lancer_calcul(avec_categorie=False)
        self.assertNotIn("classement", r)
        self.assertNotIn("Doing", r["wip_par_etat"])        # « Doing » n'est dans aucune liste
        self.assertIn("Doing", r["etats_non_classes"])

    def test_note_sur_les_equipes_au_dela_de_dix(self):
        _, md = self.lancer_calcul()
        self.assertNotIn("Les équipes ne se comparent pas entre elles", md)
        _, md = self.lancer_calcul(equipes_en_plus=9)
        self.assertIn("Les équipes ne se comparent pas entre elles : workflows, tailles de tickets et types de "
                      "travail diffèrent. Chaque ligne sert d'abord à l'équipe concernée.", md)


def calculer(lots: list[list[dict]], yaml_texte: str, nom: str = "serie") -> tuple[dict, str]:
    """Écrit un export par lot, lance calcul sur tous et retourne le rapport JSON et Markdown."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        ecrire_yaml(ws, yaml_texte)
        chemins = []
        for i, lot in enumerate(lots):
            chemin = ws / f"lot{i}.csv"
            ecrire_csv(chemin, lot)
            chemins.append(str(chemin))
        lancer(ws, "compute", *chemins, "--name", nom, "--today", AUJOURDHUI.isoformat(), "--no-comparison")
        rap = ws / "Flux-Lab" / "rapports"
        return (json.loads((rap / f"flux-{nom}-2026-10-04.json").read_text(encoding="utf-8")),
                (rap / f"flux-{nom}-2026-10-04.md").read_text(encoding="utf-8"))


class Perimetre(unittest.TestCase):
    """--perimetre : projets retenus (clés séparées par des virgules, ou « tous »), indiqué en tête du rapport."""

    @classmethod
    def setUpClass(cls):
        rng = random.Random(11)
        equipes = ["Equipe A", "Equipe B"]
        cls.abc = construire(rng, "ABC", WORKFLOW_1, 70, equipes, ["Story", "Task"])
        cls.def_ = construire(rng, "DEF", WORKFLOW_2, 50, equipes, ["Story", "Bug"])
        cls.ghi = construire(rng, "GHI", WORKFLOW_1, 40, equipes, ["Story"])

    def calcul(self, lot, *extra, yaml_texte="", attendre_succes=True):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ws = Path(tmp.name)
        ecrire_yaml(ws, yaml_texte)
        chemin = ws / "export.csv"
        ecrire_csv(chemin, lot)
        args = ["compute", str(chemin), "--name", "p", "--today", AUJOURDHUI.isoformat(), "--no-comparison", *extra]
        if not attendre_succes:
            env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(ws)}
            return subprocess.run(["uv", "run", str(SCRIPT), *args], env=env, capture_output=True, text=True)
        sortie = lancer(ws, *args)
        rap = ws / "Flux-Lab" / "rapports"
        return (json.loads((rap / "flux-p-2026-10-04.json").read_text(encoding="utf-8")),
                (rap / "flux-p-2026-10-04.md").read_text(encoding="utf-8"), sortie)

    CLES = ("termines", "debit_par_semaine", "lead_time_jours", "wip", "a_faire", "arrivees", "par_equipe",
            "wip_par_etat", "age_seuils")

    def test_un_projet_donne_le_rapport_de_ce_projet_seul(self):
        tout, _, _ = self.calcul(self.abc + self.def_ + self.ghi, "--scope", "ABC")
        seul, _, _ = self.calcul(self.abc)
        for cle in self.CLES:
            self.assertEqual(tout[cle], seul[cle], cle)
        self.assertEqual(tout["perimetre"], {"projets": ["ABC"], "tickets_lus": 160, "tickets_retenus": 70})

    def test_plusieurs_projets_sans_casse_ni_espaces(self):
        tout, md, sortie = self.calcul(self.abc + self.def_ + self.ghi, "--scope", " abc, Def ,,")
        deux, _, _ = self.calcul(self.abc + self.def_)
        for cle in self.CLES:
            self.assertEqual(tout[cle], deux[cle], cle)
        self.assertEqual(tout["perimetre"]["projets"], ["ABC", "DEF"])
        self.assertIn("120 ticket(s) retenu(s) sur 160", sortie)
        self.assertIn("0 projet(s) demandé(s) sans ticket", sortie)

    def test_le_perimetre_est_indique_en_tete_du_rapport(self):
        _, md, _ = self.calcul(self.abc + self.def_, "--scope", "ABC,DEF")
        lignes = md.splitlines()
        self.assertEqual(lignes[0].split(",")[0], "# Métriques de flux : p")
        self.assertIn("Périmètre : projets ABC, DEF (120 ticket(s) retenu(s) sur 120 lus, option --scope).", md)
        self.assertLess(md.index("Périmètre :"), md.index("## Débit"))

    def test_tous_ne_filtre_rien(self):
        defaut, md_defaut, _ = self.calcul(self.abc + self.def_)
        tous, md, _ = self.calcul(self.abc + self.def_, "--scope", "tous")
        for cle in self.CLES:
            self.assertEqual(tous[cle], defaut[cle], cle)
        self.assertIn("Périmètre : tous les projets de l'export (120 ticket(s) retenu(s) sur 120 lus", md)

    def test_sans_l_option_le_rapport_ne_change_pas_meme_si_flux_yaml_a_un_perimetre(self):
        # projets_perimetre sert à dependencies_jira.py : flux_jira.py ne le lit pas
        sans, md_sans, _ = self.calcul(self.abc + self.def_)
        avec, md_avec, _ = self.calcul(self.abc + self.def_, yaml_texte="scope_projects: [ABC]\n")
        self.assertEqual(sans, avec)
        self.assertEqual(md_sans, md_avec)
        self.assertNotIn("perimetre", sans)
        self.assertNotIn("Périmètre :", md_sans)

    def test_perimetre_avec_les_exclusions_de_flux_yaml(self):
        r, md, _ = self.calcul(self.abc + self.def_, "--scope", "ABC,DEF", yaml_texte="excluded_projects: [DEF]\n")
        seul, _, _ = self.calcul(self.abc)
        self.assertEqual(r["termines"], seul["termines"])
        self.assertEqual(r["ecartes"]["par_projet"], {"DEF": 50})

    def test_comparaison_signale_un_perimetre_different_pas_un_effectif_different(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ws = Path(tmp.name)
        ecrire_yaml(ws, "")
        chemin = ws / "export.csv"
        ecrire_csv(chemin, self.abc + self.def_)
        for date, perimetre in (("2026-09-06", "ABC,DEF"), ("2026-10-04", "ABC,DEF"), ("2026-10-11", "ABC")):
            lancer(ws, "compute", str(chemin), "--name", "p", "--today", date, "--scope", perimetre)
        rap = ws / "Flux-Lab" / "rapports"
        memes = (rap / "evolution-p-2026-10-04.md").read_text(encoding="utf-8")
        self.assertNotIn("Périmètres différents", memes)
        autre = (rap / "evolution-p-2026-10-11.md").read_text(encoding="utf-8")
        self.assertIn("Périmètres différents (--scope) : « ABC, DEF » puis « ABC ».", autre)

    def test_projet_sans_ticket_signale_et_perimetre_vide_refuse(self):
        _, _, sortie = self.calcul(self.abc, "--scope", "ABC,ZZZ")
        self.assertIn("1 projet(s) demandé(s) sans ticket", sortie)
        r = self.calcul(self.abc, "--scope", "ZZZ", attendre_succes=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("aucun ticket des projets demandés", r.stdout + r.stderr)
        r = self.calcul(self.abc, "--scope", " , ", attendre_succes=False)
        self.assertNotEqual(r.returncode, 0)


class OrdreDesListesDansLaSerie(unittest.TestCase):
    """Les listes d'un rapport sont triées (effectif décroissant, puis nom). Un rapport mensuel écrit avant ce tri a ses listes dans
    l'ordre de lecture des tickets : la comparaison de la série ne doit pas y voir un écart."""

    def inverser(self, valeur):
        """Même contenu, dictionnaires écrits dans l'ordre inverse (à tous les niveaux)."""
        if isinstance(valeur, dict):
            return {k: self.inverser(v) for k, v in reversed(list(valeur.items()))}
        if isinstance(valeur, list):
            return [self.inverser(v) for v in valeur]
        return valeur

    def evolution(self, ancien_ordre: bool) -> str:
        rng = random.Random(31)
        lot = construire(rng, "ABC", WORKFLOW_1, 90, ["Equipe A", "Equipe B"], ["Story", "Task", "Bug"])
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ws = Path(tmp.name)
        ecrire_yaml(ws, "")
        chemin = ws / "export.csv"
        ecrire_csv(chemin, lot)
        lancer(ws, "compute", str(chemin), "--name", "s", "--today", "2026-09-06")
        rapport = ws / "Flux-Lab" / "rapports" / "flux-s-2026-09-06.json"
        if ancien_ordre:
            rapport.write_text(json.dumps(self.inverser(json.loads(rapport.read_text(encoding="utf-8"))), indent=2), encoding="utf-8")
        lancer(ws, "compute", str(chemin), "--name", "s", "--today", "2026-10-04")
        return (ws / "Flux-Lab" / "rapports" / "evolution-s-2026-10-04.md").read_text(encoding="utf-8")

    def test_un_ancien_rapport_dans_un_autre_ordre_ne_change_pas_la_comparaison(self):
        courant, ancien = self.evolution(False), self.evolution(True)
        self.assertEqual(courant, ancien)
        self.assertNotIn("Périmètres différents", ancien)


class AncienFormatDeRapport(unittest.TestCase):
    """compare ne plante pas devant un rapport JSON d'un ancien format : la section concernée est sautée, avec une ligne
    qui dit pourquoi."""

    @classmethod
    def setUpClass(cls):
        rng = random.Random(21)
        cls.lot = construire(rng, "ABC", WORKFLOW_1, 90, ["Equipe A", "Equipe B"], ["Story", "Task"])

    def serie(self, retirer, retirer_equipe=(), jours=("2026-09-27", "2026-10-04")):
        """Deux calculs à une semaine d'écart ; le premier rapport JSON est amputé de clés avant le second calcul."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ws = Path(tmp.name)
        ecrire_yaml(ws, "")
        chemin = ws / "export.csv"
        ecrire_csv(chemin, self.lot)
        lancer(ws, "compute", str(chemin), "--name", "s", "--today", jours[0])
        rap = ws / "Flux-Lab" / "rapports"
        fichier = rap / f"flux-s-{jours[0]}.json"
        ancien = json.loads(fichier.read_text(encoding="utf-8"))
        for cle in retirer:
            del ancien[cle]
        for equipe in ancien["par_equipe"].values():
            for cle in retirer_equipe:
                equipe.pop(cle, None)
        fichier.write_text(json.dumps(ancien), encoding="utf-8")
        sortie = lancer(ws, "compute", str(chemin), "--name", "s", "--today", jours[1])
        return sortie, (rap / f"evolution-s-{jours[1]}.md").read_text(encoding="utf-8")

    def test_debit_par_semaine_absent_ne_plante_pas(self):
        sortie, md = self.serie(["debit_par_semaine"])
        self.assertIn("## Débit", md)
        self.assertIn("- Débit non comparé : clé(s) absente(s) (rapport précédent du 2026-09-27 : debit_par_semaine), "
                      "sans doute un ancien format de rapport.", md)
        self.assertNotIn("Série du nouveau rapport", md)
        self.assertIn("Comparaison partielle : section(s) sautée(s) faute de clés dans un des deux rapports : Débit.", md)
        self.assertIn("## Lead time", md)
        self.assertIn("| Tous types |", md)                          # les autres sections sont comparées
        self.assertIn("## Par équipe", md)
        self.assertIn("Évolution :", sortie)

    def test_plusieurs_sections_sautees_chacune_avec_sa_ligne(self):
        _, md = self.serie(["age_seuils", "prevision_quand", "lead_time_par_type", "a_faire"])
        for section in ("Vieillissement", "Prévisions", "Lead time", "Travail en cours"):
            self.assertIn(f"- {section} non comparé : clé(s) absente(s)", md)
        self.assertIn("Comparaison partielle", md)
        self.assertIn("## Débit", md)
        self.assertIn("Moyenne sur toute la fenêtre", md)

    def test_etats_types_et_fenetre_absents_vont_dans_la_comparabilite(self):
        _, md = self.serie(["wip_par_etat", "types", "semaines"])
        comparabilite = md[md.index("## Comparabilité"):md.index("## Débit")]
        for section in ("États en cours", "Types retenus", "Fenêtres"):
            self.assertIn(f"{section} non comparé", comparabilite)
        self.assertNotIn("| État | Avant | Après |", md)

    def test_equipe_a_ancien_format_sautee_les_autres_sections_restent(self):
        _, md = self.serie([], retirer_equipe=("wip_plus_de_90_j",))
        self.assertIn("Équipe « Equipe A » non comparée : clé(s) absente(s)", md)
        self.assertIn("Équipe « Equipe B » non comparée", md)
        self.assertNotIn("## Par équipe", md)
        self.assertIn("## Vieillissement", md)

    def test_rapports_complets_inchanges(self):
        _, md = self.serie([])
        self.assertNotIn("non comparé", md)
        self.assertNotIn("Comparaison partielle", md)
        self.assertIn("## Par équipe", md)

    def test_la_ligne_explicative_est_aussi_affichee_dans_le_terminal(self):
        sortie, _ = self.serie(["debit_par_semaine", "debit"])
        self.assertIn("Débit non comparé", sortie)


class PlusieursEquipes(unittest.TestCase):
    """Un ticket peut avoir plusieurs équipes : colonnes de même nom ou valeurs séparées dans une cellule."""

    def exporter(self, ws: Path, lot: list[dict], deuxieme: dict, cellule: dict) -> str:
        """deuxieme : clé -> équipe de la seconde colonne « Team » ; cellule : clé -> texte de la première."""
        chemin = ws / "multi.csv"
        ecrire_csv(chemin, lot)
        with chemin.open(encoding="utf-8", newline="") as f:
            lignes = list(csv.reader(f))
        lignes[0].append("Team")
        for ligne in lignes[1:]:
            ligne[-1] = cellule.get(ligne[0], ligne[-1])
            ligne.append(deuxieme.get(ligne[0], ""))
        with chemin.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(lignes)
        return str(chemin)

    def lancer_calcul(self, yaml_texte=""):
        rng = random.Random(5)
        lot = construire(rng, "ABC", WORKFLOW_1, 60, ["Equipe A", "Equipe B"], ["Story"])
        cles = [t["cle"] for t in lot]
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ws = Path(tmp.name)
        ecrire_yaml(ws, yaml_texte)
        chemin = self.exporter(ws, lot, {cles[0]: "Equipe C", cles[1]: "Equipe C", cles[2]: "Equipe A"},
                               {cles[3]: "Equipe A;Equipe D"})
        lancer(ws, "compute", chemin, "--name", "multi", "--today", AUJOURDHUI.isoformat(), "--no-comparison")
        rap = ws / "Flux-Lab" / "rapports"
        return (lot, cles, json.loads((rap / "flux-multi-2026-10-04.json").read_text(encoding="utf-8")),
                (rap / "flux-multi-2026-10-04.md").read_text(encoding="utf-8"))

    def test_compte_les_tickets_a_plusieurs_equipes(self):
        lot, cles, r, md = self.lancer_calcul()
        # trois par seconde colonne (le troisième a la même équipe deux fois s'il l'a déjà : compté seulement si distinct)
        attendu = 2 + (1 if lot[2]["equipe"] != "Equipe A" else 0) + 1
        self.assertEqual(r["tickets_plusieurs_equipes"]["total"], attendu)
        self.assertEqual(r["tickets_plusieurs_equipes"]["sur"], len(lot))
        self.assertIn(f"Tickets à plusieurs équipes : {attendu} sur {len(lot)}", md)
        self.assertIn("Attribution actuelle", md)

    def test_attribution_inchangee_premiere_colonne_cellule_entiere(self):
        lot, cles, r, _ = self.lancer_calcul()
        self.assertIn("Equipe A;Equipe D", r["par_equipe"])          # cellule entière : ligne à part
        self.assertNotIn("Equipe C", r["par_equipe"])                 # la seconde colonne n'attribue rien

    def test_sans_plusieurs_equipes_rien_ne_change(self):
        rng = random.Random(5)
        lot = construire(rng, "ABC", WORKFLOW_1, 30, ["Equipe A", "Equipe B"], ["Story"])
        r, md = calculer([lot], "")
        self.assertNotIn("tickets_plusieurs_equipes", r)
        self.assertNotIn("Tickets à plusieurs équipes", md)


class DormantsHistorique(unittest.TestCase):
    """--dormants-historique : les dormants se déduisent du cache d'historique, sans export des dormants."""

    def ticket(self, cle, cree, etat="In Progress", categorie="In Progress", resolu=None):
        return {"cle": cle, "type": "Story", "etat": etat, "categorie": categorie, "cree": dt.date.fromisoformat(cree),
                "resolu": dt.date.fromisoformat(resolu) if resolu else None, "motif": "Done" if resolu else "",
                "equipe": "Equipe A", "debut": dt.date.fromisoformat(cree)}

    def monde(self):
        """(tickets, cache) : cinq dormants attendus parmi des cas limites. Dates relatives au 2026-10-04."""
        tickets = [
            self.ticket("ABC-1", "2024-01-10"),                                      # dormant : dernière transition 2024
            self.ticket("ABC-2", "2024-01-10"),                                      # transition récente : vivant
            self.ticket("ABC-3", "2024-01-10"),                                      # aucune transition : création ancienne
            self.ticket("ABC-4", "2026-05-01"),                                      # aucune transition, créé récemment
            self.ticket("ABC-5", "2025-10-04"),                                      # exactement 365 jours : dormant
            self.ticket("ABC-6", "2025-10-05"),                                      # 364 jours : vivant
            self.ticket("ABC-7", "2024-01-10"),                                      # absent du cache : inconnu
            self.ticket("ABC-8", "2024-01-01", "Closed", "Done", "2025-01-01"),      # terminé
            self.ticket("ABC-9", "2024-02-01", "Open", "To Do")]                     # à faire dormant
        def t(date, de, vers):
            return [f"{date}T10:00:00.000+0200", de, vers]
        cache = {
            "ABC-1": {"termine": False, "transitions": [t("2024-03-01", "Open", "Doing"), t("2024-06-01", "Doing", "In Progress")]},
            "ABC-2": {"termine": False, "transitions": [t("2024-03-01", "Open", "Doing"), t("2026-09-01", "Doing", "In Progress")]},
            "ABC-3": {"termine": False, "transitions": []},
            "ABC-4": {"termine": False, "transitions": []},
            "ABC-5": {"termine": False, "transitions": []},
            "ABC-6": {"termine": False, "transitions": []},
            "ABC-8": {"termine": True, "transitions": [t("2025-01-01", "Open", "Closed")]},
            "ABC-9": {"termine": False, "transitions": []}}
        return tickets, cache

    def preparer(self, yaml_texte=""):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ws = Path(tmp.name)
        ecrire_yaml(ws, yaml_texte)
        tickets, cache = self.monde()
        ecrire_csv(ws / "export.csv", tickets)
        (ws / "Flux-Lab" / "historique").mkdir(parents=True)
        (ws / "Flux-Lab" / "historique" / "transitions.json").write_text(json.dumps(cache), encoding="utf-8")
        return ws

    def calcul(self, ws, *extra, nom="dh"):
        env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(ws)}
        r = subprocess.run(["uv", "run", str(SCRIPT), "compute", str(ws / "export.csv"), "--name", nom,
                            "--today", AUJOURDHUI.isoformat(), "--no-comparison", *extra],
                           env=env, capture_output=True, text=True)
        rap = ws / "Flux-Lab" / "rapports"
        if r.returncode:
            return r, None, None
        return (r, json.loads((rap / f"flux-{nom}-2026-10-04.json").read_text(encoding="utf-8")),
                (rap / f"flux-{nom}-2026-10-04.md").read_text(encoding="utf-8"))

    def test_dormants_deduits_de_l_historique(self):
        r, js, md = self.calcul(self.preparer(), "--dormant-from-history")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        w = js["wip_repartition"]
        # en cours : ABC-1, 2, 3, 4, 5, 6, 7 ; dormants : 1, 3, 5 ; ABC-7 (sans historique) n'est pas dormant
        self.assertEqual((w["dormant"], w["actif"] + w["attente"]), (3, 4))
        self.assertEqual(js["a_faire_repartition"]["dormant"], 1)                # ABC-9
        self.assertEqual(js["dormants"]["source"], "historique")
        self.assertEqual(js["dormants"]["sans_historique"], 1)                   # ABC-7
        self.assertIn("d'après l'historique des états", md)
        self.assertIn("1 ticket(s) non terminé(s) sans historique dans le cache ne sont pas comptés dormants", md)
        self.assertIn("--dormant-from-history : 4 ticket(s) dormant(s)", r.stdout)
        self.assertNotIn("ABC-", r.stdout + md)

    def test_sans_l_option_le_rapport_ne_change_pas(self):
        r, js, md = self.calcul(self.preparer())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("dormants", js)
        self.assertNotIn("Dormants", md)

    def test_cache_choisi_avec_historique(self):
        ws = self.preparer()
        autre = ws / "autre.json"
        autre.write_text((ws / "Flux-Lab" / "historique" / "transitions.json").read_text(encoding="utf-8"), encoding="utf-8")
        (ws / "Flux-Lab" / "historique" / "transitions.json").unlink()
        r, js, _ = self.calcul(ws, "--dormant-from-history", "--history", str(autre))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(js["wip_repartition"]["dormant"], 3)


class ExclusionPartout(unittest.TestCase):
    """types_portefeuille et projets_exclus s'appliquent à tous les comptes, pas seulement aux terminés."""

    def test_rapport_identique_a_un_export_sans_les_tickets_ecartes(self):
        rng = random.Random(11)
        equipes = ["Equipe A", "Equipe B", "Equipe C"]
        lot1 = construire(rng, "ABC", WORKFLOW_1, 120, equipes, ["Story", "Task", "Epic"])
        lot2 = construire(rng, "DEF", WORKFLOW_2, 120, equipes, ["Story", "RN Task", "Bug"])
        lot2 += construire(rng, "BUG", WORKFLOW_2, 40, equipes, ["Bug"])
        garde = [t for t in lot1 + lot2 if t["type"] not in ("Epic", "RN Task") and not t["cle"].startswith("BUG-")]
        avec, _ = calculer([lot1, lot2], "portfolio_types: [Epic, RN Task]\nexcluded_projects: [BUG]\n")
        sans, _ = calculer([garde], "")
        for cle in ("ecartes", "exports"):
            avec.pop(cle, None)
        sans.pop("ecartes", None)
        self.assertGreater(avec["wip"], 0)
        self.assertGreater(avec["a_faire"], 0)
        # débit, lead time, WIP, à faire, âges, équipes, prévisions : tout est identique
        self.assertEqual(avec, sans)


class EtatsAttente(unittest.TestCase):
    WORKFLOW = {"termine": ("Closed", "Done"),
                "en_cours": [("Doing", "In Progress"), ("Ready for Review", "In Progress"),
                             ("Ready for Acceptance", "In Progress"), ("Implementation - On Hold", "In Progress")],
                "a_faire": [("Waiting", "To Do")]}

    def donnees(self):
        rng = random.Random(5)
        return construire(rng, "ABC", self.WORKFLOW, 200, ["Equipe A", "Equipe B"], ["Story", "Task"])

    def test_sans_reglage_rien_ne_change(self):
        lot = self.donnees()
        sans, md = calculer([lot], "")
        self.assertNotIn("wip_attente", sans)
        self.assertNotIn("Part d'attente", sans_lecture(md))
        self.assertNotIn("WIP actif", sans_lecture(md))

    def test_wip_total_inchange_et_attente_comptee_a_part(self):
        lot = self.donnees()
        sans, _ = calculer([lot], "")
        avec, md = calculer([lot], 'waiting_states: ["Ready for", "On Hold"]\n')
        self.assertEqual(avec["wip"], sans["wip"])                       # les états d'attente restent dans le WIP
        en_cours = [t for t in lot if not t["resolu"] and t["categorie"] == "In Progress"]
        attendu = [t for t in en_cours if t["etat"].startswith("Ready for") or t["etat"].endswith("On Hold")]
        w = avec["wip_attente"]
        self.assertEqual((w["actif"], w["attente"]), (len(en_cours) - len(attendu), len(attendu)))
        self.assertAlmostEqual(w["part"], len(attendu) / len(en_cours))
        self.assertEqual(w["par_etat"], dict(Counter(t["etat"] for t in attendu)))
        self.assertIn("WIP actif", md)
        self.assertIn("Part d'attente", md)

    def test_par_equipe(self):
        lot = self.donnees()
        avec, md = calculer([lot], 'waiting_states: ["Ready for", "On Hold"]\n')
        equipes = avec["par_equipe"]
        self.assertEqual(sum(d["wip_attente"] for d in equipes.values()), avec["wip_attente"]["attente"])
        for d in equipes.values():
            self.assertAlmostEqual(d["part_attente"], d["wip_attente"] / d["wip"])
        self.assertIn("WIP en attente", md)

    def test_etat_exact(self):
        lot = self.donnees()
        avec, _ = calculer([lot], 'waiting_states: ["Waiting", "Doing"]\n')
        # « Waiting » est « à faire » (pas en cours) : il n'entre pas dans le WIP ; « Doing » est un état exact
        self.assertEqual(set(avec["wip_attente"]["par_etat"]), {"Doing"})


class Dormants(unittest.TestCase):
    """--dormant-from-history : répartition actif / attente / dormant, calculée sur un cache d'historique."""
    YAML = 'waiting_states: ["Ready for", "On Hold"]\n'
    WORKFLOW = EtatsAttente.WORKFLOW

    def lot(self):
        return construire(random.Random(5), "ABC", self.WORKFLOW, 240, ["Equipe A", "Equipe B"], ["Story", "Task"])

    def lancer_avec(self, lot, cles_dormantes, yaml_texte=None, nom="dorm", extra=()):
        """Retourne (sortie du terminal, rapport JSON, rapport Markdown). Les tickets de `cles_dormantes` sont créés il y
        a plus d'un an, sans transition ; les autres sont dans le cache sans transition et créés récemment."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ws = Path(tmp.name)
        ecrire_yaml(ws, self.YAML if yaml_texte is None else yaml_texte)
        anciens = set(cles_dormantes)
        ancien = AUJOURDHUI - dt.timedelta(days=500)
        lot = [{**t, "cree": ancien, "debut": ancien if t["debut"] else None} if t["cle"] in anciens else t for t in lot]
        ecrire_csv(ws / "principal.csv", lot)
        (ws / "Flux-Lab" / "historique").mkdir(parents=True)
        (ws / "Flux-Lab" / "historique" / "transitions.json").write_text(
            json.dumps({t["cle"]: {"termine": bool(t["resolu"]), "transitions": []} for t in lot}), encoding="utf-8")
        sortie = lancer(ws, "compute", str(ws / "principal.csv"), "--dormant-from-history",
                        "--name", nom, "--today", AUJOURDHUI.isoformat(), "--no-comparison", *extra)
        rap = ws / "Flux-Lab" / "rapports"
        return (sortie, json.loads((rap / f"flux-{nom}-2026-10-04.json").read_text(encoding="utf-8")),
                (rap / f"flux-{nom}-2026-10-04.md").read_text(encoding="utf-8"))

    def choisir(self, lot):
        en_cours = [t for t in lot if not t["resolu"] and t["categorie"] == "In Progress"]
        a_faire = [t for t in lot if not t["resolu"] and t["categorie"] == "To Do"]
        termines = [t for t in lot if t["resolu"]]
        dormants_wip = en_cours[::3]
        dormants_todo = a_faire[::2]
        return en_cours, a_faire, dormants_wip, dormants_todo, termines

    def test_repartition_actif_attente_dormant(self):
        lot = self.lot()
        en_cours, a_faire, dormants_wip, dormants_todo, termines = self.choisir(lot)
        cles = [t["cle"] for t in dormants_wip + dormants_todo]
        sortie, r, md = self.lancer_avec(lot, cles)
        vivants = [t for t in en_cours if t not in dormants_wip]
        attente = [t for t in vivants if t["etat"].startswith("Ready for") or t["etat"].endswith("On Hold")]
        w = r["wip_repartition"]
        self.assertEqual((w["actif"], w["attente"], w["dormant"]),
                         (len(vivants) - len(attente), len(attente), len(dormants_wip)))
        self.assertEqual(w["actif"] + w["attente"] + w["dormant"], len(en_cours))     # exclusifs et exhaustifs
        self.assertEqual(r["wip"], len(en_cours))                                     # le WIP total ne change pas
        self.assertAlmostEqual(w["parts"]["dormant"], len(dormants_wip) / len(en_cours))
        f = r["a_faire_repartition"]
        self.assertEqual((f["vivant"], f["dormant"]), (len(a_faire) - len(dormants_todo), len(dormants_todo)))
        self.assertIn("WIP dormant", md)
        self.assertIn("hors dormants", md)

    def test_resume_dans_le_terminal(self):
        lot = self.lot()
        _, _, dormants_wip, dormants_todo, _ = self.choisir(lot)
        sortie, r, _ = self.lancer_avec(lot, [t["cle"] for t in dormants_wip + dormants_todo])
        self.assertEqual(r["dormants"]["cles"], len(dormants_wip) + len(dormants_todo))
        self.assertIn(f"{len(dormants_wip)} en cours et {len(dormants_todo)} à faire dormant(s)", sortie)

    def test_aucune_cle_dans_le_rapport_ni_dans_la_sortie(self):
        lot = self.lot()
        _, _, dormants_wip, dormants_todo, termines = self.choisir(lot)
        cles = [t["cle"] for t in dormants_wip + dormants_todo]
        sortie, r, md = self.lancer_avec(lot, cles)
        for texte in (sortie, json.dumps(r, ensure_ascii=False), md):
            self.assertNotIn("ABC-", texte)

    def test_note_seuil_et_source(self):
        _, _, dormants_wip, _, _ = self.choisir(self.lot())
        _, r, md = self.lancer_avec(self.lot(), [t["cle"] for t in dormants_wip])
        self.assertEqual(r["dormants"]["seuil_jours"], 365)
        self.assertEqual(r["dormants"]["source"], "historique")
        self.assertNotIn("export", r["dormants"])
        self.assertIn("365 jours", md)
        self.assertIn("d'après l'historique des états", md)

    def test_par_equipe_et_par_etat(self):
        lot = self.lot()
        en_cours, a_faire, dormants_wip, dormants_todo, _ = self.choisir(lot)
        _, r, md = self.lancer_avec(lot, [t["cle"] for t in dormants_wip + dormants_todo])
        equipes = r["par_equipe"]
        for cle in ("actif", "attente", "dormant"):
            self.assertEqual(sum(d["wip_repartition"][cle] for d in equipes.values()), r["wip_repartition"][cle])
        for d in equipes.values():
            w = d["wip_repartition"]
            self.assertEqual(w["actif"] + w["attente"] + w["dormant"], d["wip"])
        self.assertEqual(sum(d["a_faire_dormant"] for d in equipes.values()), len(dormants_todo))
        self.assertEqual(sum(d["dormants"] for d in r["age_par_etat"].values()), len(dormants_wip))
        self.assertEqual(sum(d["dormants"] for d in r["age_a_faire_par_etat"].values()), len(dormants_todo))
        self.assertIn("Part dormante", md)

    def test_little_et_prevision_sur_le_wip_non_dormant(self):
        lot = self.lot()
        en_cours, _, dormants_wip, dormants_todo, _ = self.choisir(lot)
        _, r, md = self.lancer_avec(lot, [t["cle"] for t in dormants_wip + dormants_todo])
        non_dormant = len(en_cours) - len(dormants_wip)
        debit = r["debit"]["moyenne"]
        self.assertEqual(r["wip_non_dormant"], non_dormant)
        self.assertAlmostEqual(r["little_jours"], non_dormant / debit * 7)
        self.assertAlmostEqual(r["little_jours_wip_total"], len(en_cours) / debit * 7)
        self.assertEqual(r["prevision_quand"]["elements"], non_dormant)
        self.assertEqual(r["prevision_quand_wip_total"]["elements"], len(en_cours))
        self.assertGreater(r["little_jours_wip_total"], r["little_jours"])
        self.assertIn(f"WIP non dormant ({non_dormant} éléments", md)
        self.assertIn(f"Pour comparaison, sur le WIP total ({len(en_cours)} éléments)", md)
        self.assertIn(f"sur le WIP total ({len(en_cours)} éléments, dormants compris)", md)

    def test_objectif_explicite_garde_pour_les_deux(self):
        lot = self.lot()
        _, _, dormants_wip, _, _ = self.choisir(lot)
        _, r, _ = self.lancer_avec(lot, [t["cle"] for t in dormants_wip], extra=("--target", "50"))
        self.assertEqual(r["prevision_quand"]["elements"], 50)
        self.assertNotIn("prevision_quand_wip_total", r)

    def test_sans_dormants_little_et_prevision_sur_le_wip_total(self):
        lot = self.lot()
        sans, _ = calculer([lot], self.YAML)
        self.assertEqual(sans["prevision_quand"]["elements"], sans["wip"])
        self.assertNotIn("little_jours_wip_total", sans)
        self.assertNotIn("wip_non_dormant", sans)

    def test_sans_etats_attente_dormants_separes_quand_meme(self):
        lot = self.lot()
        en_cours, _, dormants_wip, dormants_todo, _ = self.choisir(lot)
        _, r, _ = self.lancer_avec(lot, [t["cle"] for t in dormants_wip], yaml_texte="")
        w = r["wip_repartition"]
        self.assertEqual((w["attente"], w["dormant"], w["actif"]),
                         (0, len(dormants_wip), len(en_cours) - len(dormants_wip)))

    def test_sans_l_option_aucun_changement(self):
        lot = self.lot()
        sans, md = calculer([lot], self.YAML)
        for cle in ("dormants", "wip_repartition", "a_faire_repartition"):
            self.assertNotIn(cle, sans)
        self.assertNotIn("WIP dormant", sans_lecture(md))
        self.assertNotIn("Part dormante", sans_lecture(md))

    def test_export_principal_sans_cle(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            ecrire_yaml(ws, "")
            ecrire_csv(ws / "p.csv", self.lot())
            texte = (ws / "p.csv").read_text(encoding="utf-8").replace("Issue key", "Autre")
            (ws / "p.csv").write_text(texte, encoding="utf-8")
            env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(ws)}
            r = subprocess.run(["uv", "run", str(SCRIPT), "compute", str(ws / "p.csv"), "--dormant-from-history",
                                "--today", AUJOURDHUI.isoformat()],
                               env=env, capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)

    def test_option_dormants_refusee_avec_la_voie_de_remplacement(self):
        for langue, extrait in (("fr", "n'existe plus"), ("en", "no longer exists")):
            with self.subTest(langue=langue), tempfile.TemporaryDirectory() as tmp:
                ws = Path(tmp)
                ecrire_yaml(ws, "")
                ecrire_csv(ws / "p.csv", self.lot())
                (ws / "d.csv").write_text("Issue key\nABC-1\n", encoding="utf-8")
                env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(ws)}
                r = subprocess.run(["uv", "run", str(SCRIPT), "compute", str(ws / "p.csv"), "--dormants",
                                    str(ws / "d.csv"), "--today", AUJOURDHUI.isoformat(), "--language", langue],
                                   env=env, capture_output=True, text=True)
                self.assertNotEqual(r.returncode, 0)
                sortie = r.stdout + r.stderr
                self.assertIn("--dormant-from-history", sortie)
                self.assertIn(extrait, sortie)
                self.assertNotIn("Traceback", sortie)
                self.assertFalse((ws / "Flux-Lab" / "rapports").exists())


class ExportDeLApiSeulement(unittest.TestCase):
    """Les CSV de export_jira_api.py sont la seule entrée : en-têtes anglais, date %d/%b/%Y %H:%M."""

    def test_export_a_en_tetes_francais_refuse_avec_la_voie_api(self):
        for langue in ("fr", "en"):
            with self.subTest(langue=langue), tempfile.TemporaryDirectory() as tmp:
                ws = Path(tmp)
                ecrire_yaml(ws, "")
                (ws / "manuel.csv").write_text("Clé,Type de ticket,Statut,Créé,Résolu\n"
                                               "ABC-1,Story,Fait,01/août/2026 09:00,10/août/2026 09:00\n", encoding="utf-8")
                env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(ws)}
                for commande in ("statuses", "compute"):
                    r = subprocess.run(["uv", "run", str(SCRIPT), commande, str(ws / "manuel.csv"), "--language", langue],
                                       env=env, capture_output=True, text=True)
                    self.assertNotEqual(r.returncode, 0)
                    self.assertIn("export_jira_api.py export", r.stdout + r.stderr)
                    self.assertNotIn("Traceback", r.stdout + r.stderr)

    def test_dates_hors_format_de_l_api_comptees_illisibles(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            ecrire_yaml(ws, "")
            (ws / "x.csv").write_text("Issue key,Issue Type,Status,Created,Resolved\n"
                                      "ABC-1,Story,Done,2026-08-01,2026-08-10\n"
                                      "ABC-2,Story,Done,01/Aug/2026 09:00,10/Aug/2026 09:00\n", encoding="utf-8")
            sortie = lancer(ws, "statuses", str(ws / "x.csv"))
            self.assertIn("1 ligne(s) avec une date de création illisible", sortie)
            self.assertIn("export_jira_api.py", sortie)

    def test_flux_yaml_ancien_avec_date_format_ou_alias_francais_est_refuse(self):
        lot = construire(random.Random(3), "ABC", WORKFLOW_1, 60, ["Equipe A", "Equipe B"], ["Story", "Task"])
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            ecrire_csv(ws / "e.csv", lot)
            env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(ws)}
            for texte, attendu in (('format_date: "%d/%m/%Y"\n', "« format_date » n'existe plus"),
                                   ("columns:\n  status: [Statut, Status]\n", "« Statut » n'existe plus")):
                ecrire_yaml(ws, texte)
                r = subprocess.run(["uv", "run", str(SCRIPT), "compute", str(ws / "e.csv"), "--name", "s", "--today",
                                    AUJOURDHUI.isoformat(), "--no-comparison"], env=env, capture_output=True, text=True)
                self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn(attendu, r.stderr)
                self.assertNotIn("%d/%m/%Y", r.stdout + r.stderr)
                self.assertFalse(list((ws / "Flux-Lab" / "rapports").glob("flux-s-*")))


class ArriveesEtSorties(unittest.TestCase):
    """Section « Arrivées et sorties » : tickets créés par semaine, mêmes types et exclusions que le débit."""

    def donnees(self):
        rng = random.Random(8)
        lot = construire(rng, "ABC", WORKFLOW_1, 150, ["Equipe A", "Equipe B"], ["Story", "Task", "Epic"])
        # tickets créés pendant la période puis rejetés : dans les arrivées, jamais dans les sorties
        rejetes = [{**t, "cle": f"REJ-{i}", "type": "Story", "etat": "Done", "categorie": "Done", "motif": "Rejected",
                    "cree": AUJOURDHUI - dt.timedelta(days=30 + i), "resolu": AUJOURDHUI - dt.timedelta(days=20),
                    "equipe": "Equipe A"} for i, t in enumerate(lot[:6])]
        return lot, rejetes

    def rapport(self, lot, yaml_texte="portfolio_types: [Epic]\n"):
        return calculer([lot], yaml_texte)

    def attendu(self, lot, r):
        premiere = dt.date.fromisoformat(r["periode"][0])
        derniere = dt.date.fromisoformat(r["periode"][1]) - dt.timedelta(days=6)
        def semaine(d):
            return d - dt.timedelta(days=d.weekday())
        gardes = [t for t in lot if t["type"] != "Epic"]
        return [sum(1 for t in gardes if semaine(t["cree"]) == premiere + dt.timedelta(weeks=i))
                for i in range((derniere - premiere).days // 7 + 1)], gardes

    def test_arrivees_par_semaine_memes_exclusions_que_le_debit(self):
        lot, rejetes = self.donnees()
        r, md = self.rapport(lot + rejetes)
        attendu, gardes = self.attendu(lot + rejetes, r)
        self.assertEqual(r["arrivees_par_semaine"], attendu)
        self.assertEqual(r["arrivees"], sum(attendu))
        self.assertEqual(len(r["arrivees_par_semaine"]), len(r["debit_par_semaine"]))
        epics = sum(1 for t in lot if t["type"] == "Epic")
        self.assertGreater(epics, 0)                               # les Epics sont écartés des arrivées aussi
        self.assertIn("## Arrivées et sorties", md)
        self.assertIn("| Semaine (début) | Arrivées | Sorties | Différence |", md)

    def test_rejetes_comptes_dans_les_arrivees_pas_dans_les_sorties(self):
        lot, rejetes = self.donnees()
        sans, _ = self.rapport(lot)
        avec, md = self.rapport(lot + rejetes)
        self.assertEqual(avec["arrivees"], sans["arrivees"] + len(rejetes))
        self.assertEqual(avec["termines"], sans["termines"])       # rejetés : hors débit
        self.assertEqual(avec["debit_par_semaine"], sans["debit_par_semaine"])
        self.assertIn("créés puis rejetés, ou restés sans mouvement, comptent dans les arrivées", md)

    def test_total_et_difference(self):
        lot, rejetes = self.donnees()
        r, md = self.rapport(lot + rejetes)
        arrivees, sorties = sum(r["arrivees_par_semaine"]), sum(r["debit_par_semaine"])
        self.assertIn(f"| **Total** | **{arrivees}** | **{sorties}** | **{arrivees - sorties:+d}** |", md)

    def test_par_equipe(self):
        lot, rejetes = self.donnees()
        r, md = self.rapport(lot + rejetes)
        equipes = r["arrivees_sorties_par_equipe"]
        self.assertEqual(sum(d["arrivees"] for d in equipes.values()), r["arrivees"])
        self.assertEqual(sum(d["sorties"] for d in equipes.values()), r["termines"])
        for d in equipes.values():
            self.assertEqual(d["difference"], d["arrivees"] - d["sorties"])
        self.assertEqual(list(equipes), sorted(equipes))          # ordre alphabétique, pas de classement
        self.assertIn("### Par équipe", md)

    def test_note_sur_les_equipes_au_dela_de_dix(self):
        lot, _ = self.donnees()
        _, md = self.rapport(lot)
        self.assertEqual(md.count("Les équipes ne se comparent pas entre elles"), 0)
        plus = lot + [{**lot[0], "cle": f"ABC-9{i}", "equipe": f"Equipe X{i}", "type": "Story"} for i in range(10)]
        _, md = self.rapport(plus)
        self.assertEqual(md.count("Les équipes ne se comparent pas entre elles"), 2)   # débit par équipe, arrivées


class CommentLire(unittest.TestCase):
    """Section fixe « Comment lire ce rapport » : texte identique d'un rapport à l'autre, exemples calculés."""

    def rapport(self, graine: int, n: int = 150):
        lot = construire(random.Random(graine), "ABC", WORKFLOW_1, n, ["Equipe A", "Equipe B"], ["Story", "Task"])
        return calculer([lot], "")

    def section(self, md: str) -> str:
        debut = md.index("## Comment lire ce rapport")
        return md[debut:md.index("## Limites")]

    def test_section_avant_limites_et_apres_les_previsions(self):
        _, md = self.rapport(1)
        self.assertLess(md.index("## Prévisions Monte Carlo"), md.index("## Comment lire ce rapport"))
        self.assertLess(md.index("## Comment lire ce rapport"), md.index("## Limites"))

    def test_definitions_presentes(self):
        _, md = self.rapport(1)
        sec = self.section(md)
        for terme in ("**P50 (médiane)**", "**P85**", "P70 et P95", "Pourquoi des percentiles", "**Lead time**",
                      "**Âge**", "**WIP actif**", "**WIP en attente**", "**WIP dormant**", "**Arrivées et sorties**",
                      "**Loi de Little**", "**Prévision Monte Carlo**", "Ce n'est pas une date."):
            self.assertIn(terme, sec)

    def test_texte_fixe_exemples_calcules(self):
        r1, md1 = self.rapport(1)
        r2, md2 = self.rapport(2, n=220)
        fixe1 = self.section(md1).split("Exemples tirés de ce rapport")[0]
        fixe2 = self.section(md2).split("Exemples tirés de ce rapport")[0]
        self.assertEqual(fixe1, fixe2)                              # le texte ne dépend pas des données
        for r, md in ((r1, md1), (r2, md2)):
            age = r["age_wip_jours"]
            ages = age["depuis_debut"] if age["base"] == "début" else age["depuis_creation"]
            n_age, n_lead = round(p(ages, 85)), round(p(r["lead_time_jours"], 85))
            self.assertIn(f"L'âge P85 des éléments en cours est de {n_age} jours : 15 % des éléments en cours y sont "
                          f"depuis plus de {n_age} jours.", md)
            self.assertIn(f"Le lead time P85 est de {n_lead} jours : 85 % des éléments terminés l'ont été en moins de "
                          f"{n_lead} jours.", md)
        self.assertNotEqual(p(r1["lead_time_jours"], 85), p(r2["lead_time_jours"], 85))     # les exemples suivent les chiffres


class TempsParSegment(unittest.TestCase):
    """--historique : temps par état puis par segment, calculé sur un historique inventé et vérifié à la main.

    Parcours inventés (aujourd'hui : 2026-10-04) :
    T0 (A) livré le 04-07 sans passer par un segment ; T1 (A) livré le 06-25 par tous les segments ;
    T2 (A) livré le 06-01, revient en implémentation après la revue, sans passer par « prêt » ;
    T3 (B) ouvert, en implémentation depuis le 09-20 ; T4 (B) ouvert, sans historique ;
    T5 (B) livré le 07-10 via « prêt » ; T6 (B) ouvert, créé le 09-24 directement en implémentation, sans transition.
    """
    YAML = 'waiting_states: ["Ready for"]\n'

    PARCOURS = {   # clé : (équipe, création, état initial, [(date, état d'arrivée)], résolution ou None)
        "ABC-0": ("Equipe A", "2026-04-01", "Open", [("2026-04-07", "Closed")], "2026-04-07"),
        "ABC-1": ("Equipe A", "2026-05-04", "Open",
                  [("2026-05-06", "Definition - Ongoing"), ("2026-05-20", "Ready for Implementation"),
                   ("2026-05-27", "Implementation - Ongoing"), ("2026-06-10", "Ready for Review (Implementation)"),
                   ("2026-06-20", "Ready for Acceptance"), ("2026-06-25", "Closed")], "2026-06-25"),
        "ABC-2": ("Equipe A", "2026-05-01", "Open",
                  [("2026-05-10", "Implementation - Ongoing"), ("2026-05-20", "Ready for Review (Implementation)"),
                   ("2026-05-25", "Implementation - Ongoing"), ("2026-06-01", "Closed")], "2026-06-01"),
        "ABC-3": ("Equipe B", "2026-09-01", "Open",
                  [("2026-09-05", "Definition - Ongoing"), ("2026-09-12", "Ready for Implementation"),
                   ("2026-09-20", "Implementation - Ongoing")], None),
        "ABC-4": ("Equipe B", "2026-08-01", "In Progress", None, None),            # absent du cache
        "ABC-5": ("Equipe B", "2026-06-01", "Open",
                  [("2026-06-03", "Ready for Implementation"), ("2026-06-10", "Implementation - Ongoing"),
                   ("2026-07-10", "Closed")], "2026-07-10"),
        "ABC-6": ("Equipe B", "2026-09-24", "Implementation - Ongoing", [], None),   # aucune transition
    }

    def preparer(self, yaml_texte=None, sans_cle=False, sans_cache=False):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ws = Path(tmp.name)
        ecrire_yaml(ws, self.YAML if yaml_texte is None else yaml_texte)
        lignes, cache = [], {}
        for cle, (equipe, cree, initial, etapes, resolu) in self.PARCOURS.items():
            etat_actuel = etapes[-1][1] if etapes else initial
            lignes.append({"cle": cle, "type": "Story", "etat": etat_actuel,
                           "categorie": "Done" if resolu else ("In Progress" if etat_actuel != "Open" else "To Do"),
                           "cree": dt.date.fromisoformat(cree),
                           "resolu": dt.date.fromisoformat(resolu) if resolu else None,
                           "motif": "Done" if resolu else "", "equipe": equipe,
                           "debut": dt.date.fromisoformat(cree)})
            if etapes is not None:
                avant, transitions = initial, []
                for date, vers in etapes:
                    transitions.append([f"{date}T10:00:00.000+0200", avant, vers])
                    avant = vers
                cache[cle] = {"termine": bool(resolu), "transitions": transitions}
        ecrire_csv(ws / "export.csv", lignes)
        if sans_cle:
            (ws / "export.csv").write_text((ws / "export.csv").read_text(encoding="utf-8").replace("Issue key", "Autre"),
                                           encoding="utf-8")
        if not sans_cache:
            dossier = ws / "Flux-Lab" / "historique"
            dossier.mkdir(parents=True)
            (dossier / "transitions.json").write_text(json.dumps(cache), encoding="utf-8")
        return ws

    def calcul(self, ws, *extra):
        env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(ws)}
        r = subprocess.run(["uv", "run", str(SCRIPT), "compute", str(ws / "export.csv"), "--name", "seg",
                            "--today", AUJOURDHUI.isoformat(), "--no-comparison", *extra],
                           env=env, capture_output=True, text=True)
        rap = ws / "Flux-Lab" / "rapports"
        if r.returncode:
            return r, None, None
        return (r, json.loads((rap / "flux-seg-2026-10-04.json").read_text(encoding="utf-8")),
                (rap / "flux-seg-2026-10-04.md").read_text(encoding="utf-8"))

    def rapport(self, yaml_texte=None):
        ws = self.preparer(yaml_texte)
        r, js, md = self.calcul(ws, "--history")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return js["temps_par_segment"], md

    def test_tickets_sortis_de_chaque_segment(self):
        ts, _ = self.rapport()
        sortis = ts["global"]["sortis"]
        self.assertEqual({k: v["n"] for k, v in sortis.items()},
                         {"definition": 2, "pret": 3, "implementation": 3, "revue_verification": 2, "acceptation": 1})
        # définition : T1 14 j, T3 7 j ; implémentation : T1 14 j, T2 17 j (deux visites cumulées), T5 30 j
        self.assertAlmostEqual(sortis["definition"]["p50"], 10.5)
        self.assertAlmostEqual(sortis["definition"]["p85"], 12.95)
        self.assertAlmostEqual(sortis["definition"]["moyenne"], 10.5)
        self.assertAlmostEqual(sortis["pret"]["p85"], 7.7)                      # 7, 7, 8
        self.assertAlmostEqual(sortis["implementation"]["p50"], 17)
        self.assertAlmostEqual(sortis["implementation"]["moyenne"], 61 / 3)
        self.assertAlmostEqual(sortis["revue_verification"]["p50"], 7.5)        # T1 10 j, T2 5 j
        self.assertAlmostEqual(sortis["acceptation"]["p50"], 5)

    def test_age_dans_le_segment_etat_initial_et_etat_actuel(self):
        ts, _ = self.rapport()
        dedans = ts["global"]["dans_le_segment"]
        # T3 en implémentation depuis le 09-20 (14 j) ; T6 créé directement en implémentation le 09-24 (10 j,
        # état initial puis état actuel jusqu'à la date du calcul, sans transition)
        self.assertEqual(dedans["implementation"]["n"], 2)
        self.assertAlmostEqual(dedans["implementation"]["p50"], 12)
        self.assertAlmostEqual(dedans["implementation"]["p85"], 13.4)
        self.assertEqual(dedans["definition"]["n"], 0)

    def test_lead_time_de_livraison(self):
        ts, _ = self.rapport()
        ltl = ts["global"]["lead_time_livraison"]
        self.assertEqual((ltl["n"], ltl["sans_engagement"]), (2, 2))            # T1 et T5 ; T0 et T2 sans « prêt »
        self.assertAlmostEqual(ltl["depuis_engagement"]["50"], 36.5)            # T1 36 j, T5 37 j
        self.assertAlmostEqual(ltl["depuis_creation"]["50"], 45.5)              # mêmes tickets : 52 j, 39 j

    def test_efficacite_de_flux(self):
        ts, _ = self.rapport()
        e = ts["global"]["efficacite"]
        # T1 : 14 j actifs sur 36 ; T5 : 30 j actifs sur 37 (les états « Ready for … » sont des attentes)
        self.assertEqual(e["n"], 2)
        self.assertAlmostEqual(e["p50"], (14 / 36 + 30 / 37) / 2)
        self.assertAlmostEqual(e["agregee"], 44 / 73)

    def test_efficacite_non_calculee_sans_etats_attente(self):
        ts, md = self.rapport(yaml_texte="")
        self.assertIsNone(ts["global"]["efficacite"])
        self.assertIn("Non calculée : aucun état d'attente", md)

    def test_couverture_et_avertissement(self):
        ts, md = self.rapport()
        c = ts["global"]["couverture"]
        self.assertEqual((c["avec"], c["total"]), (6, 7))                       # T4 n'a pas d'historique
        self.assertAlmostEqual(c["part"], 6 / 7)
        self.assertIn("Couverture : 6 tickets sur 7", md)
        self.assertIn("ATTENTION : la couverture est inférieure à 90 %", md)

    def test_pas_d_avertissement_si_couverture_suffisante(self):
        ws = self.preparer()
        cache_chemin = ws / "Flux-Lab" / "historique" / "transitions.json"
        cache = json.loads(cache_chemin.read_text(encoding="utf-8"))
        cache["ABC-4"] = {"termine": False, "transitions": []}
        cache_chemin.write_text(json.dumps(cache), encoding="utf-8")
        _, js, md = self.calcul(ws, "--history")
        self.assertEqual(js["temps_par_segment"]["global"]["couverture"]["part"], 1.0)
        self.assertNotIn("ATTENTION : la couverture", md)

    def test_par_equipe_sans_classement(self):
        ts, md = self.rapport()
        a, b = ts["par_equipe"]["Equipe A"], ts["par_equipe"]["Equipe B"]
        self.assertEqual((a["couverture"]["avec"], a["couverture"]["total"]), (3, 3))
        self.assertEqual((b["couverture"]["avec"], b["couverture"]["total"]), (3, 4))
        self.assertEqual(a["lead_time_livraison"]["n"], 1)                      # T1
        self.assertEqual(b["lead_time_livraison"]["n"], 1)                      # T5
        self.assertEqual(a["sortis"]["implementation"]["n"], 2)                 # T1, T2
        self.assertEqual(b["dans_le_segment"]["implementation"]["n"], 2)        # T3, T6
        self.assertEqual(list(ts["par_equipe"]), sorted(ts["par_equipe"]))
        self.assertIn("### Par équipe", md)
        self.assertIn("Les équipes ne se comparent pas entre elles", md)

    def test_note_equipes_au_dela_de_dix(self):
        ws = self.preparer()
        lignes = []
        # dix équipes en plus : on réécrit l'export avec des tickets terminés sans historique
        texte = (ws / "export.csv").read_text(encoding="utf-8")
        for i in range(10):
            texte += f"ABC-9{i},Story,Closed,Done,25/Jun/2026 10:00,25/Jun/2026 10:00,Done,26/Jun/2026 10:00,Equipe X{i}\n"
        (ws / "export.csv").write_text(texte, encoding="utf-8")
        _, _, md = self.calcul(ws, "--history")
        self.assertIn("Chaque ligne sert d'abord à l'équipe concernée.", md.split("## Temps par segment")[1])

    def test_point_engagement_reglable(self):
        ts, _ = self.rapport(yaml_texte=self.YAML + "commitment_point: implementation\n")
        ltl = ts["global"]["lead_time_livraison"]
        self.assertEqual((ltl["n"], ltl["sans_engagement"]), (3, 1))            # T1 29 j, T2 22 j, T5 30 j
        self.assertAlmostEqual(ltl["depuis_engagement"]["50"], 29)

    def test_point_engagement_inconnu_refuse(self):
        ws = self.preparer(self.YAML + "commitment_point: inexistant\n")
        r, _, _ = self.calcul(ws, "--history")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("commitment_point", r.stdout + r.stderr)

    def test_segments_reglables(self):
        ts, md = self.rapport(yaml_texte=self.YAML + "segments:\n  debut: [Definition - Ongoing]\n  ready: [Ready for Implementation]\n")
        self.assertEqual(list(ts["global"]["sortis"]), ["debut", "pret"])
        self.assertEqual(ts["global"]["sortis"]["debut"]["n"], 2)

    def test_etats_hors_segment_signales(self):
        ts, md = self.rapport(yaml_texte=self.YAML + "uncounted_segments: {}\n")
        self.assertIn("Open", ts["etats_hors_segment"])
        self.assertIn("Closed", ts["etats_hors_segment"])
        self.assertIn("rangés dans aucun segment", md)

    def test_etats_de_debut_et_de_fin_connus_par_defaut(self):
        ts, md = self.rapport()
        self.assertNotIn("Open", ts["etats_hors_segment"])
        self.assertNotIn("Closed", ts["etats_hors_segment"])
        self.assertEqual(ts["etats_hors_segment"], {})
        self.assertNotIn("rangés dans aucun segment", md)
        self.assertNotIn("a_faire", ts["global"]["sortis"])        # hors calcul : aucun temps calculé
        self.assertNotIn("termine", ts["global"]["sortis"])

    def test_vrai_oubli_encore_signale(self):
        ts, md = self.rapport(yaml_texte=self.YAML + "uncounted_segments:\n  todo: [Open]\n")
        self.assertEqual(list(ts["etats_hors_segment"]), ["Closed"])

    def test_sans_historique_rien_ne_change(self):
        ws = self.preparer()
        r, js, md = self.calcul(ws)
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("temps_par_segment", js)
        for terme in ("Temps par segment", "Point d'engagement", "Efficacité de flux", "Couverture"):
            self.assertNotIn(terme, md)

    def test_notions_ajoutees_a_comment_lire_ce_rapport(self):
        _, md = self.rapport()
        section = md[md.index("## Comment lire ce rapport"):md.index("## Limites")]
        for terme in ("**Segment**", "**Temps par segment**", "**Point d'engagement**", "**Lead time de livraison**",
                      "**Efficacité de flux**", "**Couverture**", "L'efficacité de flux agrégée est de"):
            self.assertIn(terme, section)
        _, js, md2 = self.calcul(self.preparer())
        self.assertNotIn("Point d'engagement", md2)

    def test_aucune_cle_dans_le_rapport(self):
        ws = self.preparer()
        _, js, md = self.calcul(ws, "--history")
        self.assertNotIn("ABC-", md)
        self.assertNotIn("ABC-", json.dumps(js))

    def test_cle_obligatoire(self):
        ws = self.preparer(sans_cle=True)
        r, _, _ = self.calcul(ws, "--history")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("colonne de clé", r.stdout + r.stderr)

    def test_cache_introuvable(self):
        ws = self.preparer(sans_cache=True)
        r, _, _ = self.calcul(ws, "--history")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("history_jira.py collect", r.stdout + r.stderr)

    def test_chemin_de_cache_en_argument(self):
        ws = self.preparer()
        ailleurs = ws / "ailleurs.json"
        ailleurs.write_text((ws / "Flux-Lab" / "historique" / "transitions.json").read_text(encoding="utf-8"), encoding="utf-8")
        (ws / "Flux-Lab" / "historique" / "transitions.json").unlink()
        r, js, _ = self.calcul(ws, "--history", str(ailleurs))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("temps_par_segment", js)


class DonneesDuTableau(unittest.TestCase):
    """Données ajoutées pour le tableau de bord : arrivées par équipe, CFD (avec --historique) et points de l'Aging WIP
    (avec --points, fichier à part). Mêmes parcours inventés que TempsParSegment (aujourd'hui : 2026-10-04)."""
    YAML = TempsParSegment.YAML
    PARCOURS = TempsParSegment.PARCOURS
    preparer = TempsParSegment.preparer
    calcul = TempsParSegment.calcul

    def lancer_avec(self, *extra):
        ws = self.preparer()
        r, js, md = self.calcul(ws, *extra)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return ws, r, js, md

    def test_arrivees_par_semaine_et_par_equipe(self):
        _, _, js, _ = self.lancer_avec()
        for equipe, donnees in js["par_equipe"].items():
            self.assertEqual(len(donnees["arrivees_par_semaine"]), js["semaines"])
            self.assertEqual(sum(donnees["arrivees_par_semaine"]), js["arrivees_sorties_par_equipe"][equipe]["arrivees"])

    def test_cfd_a_la_fin_de_chaque_semaine(self):
        _, _, js, _ = self.lancer_avec("--history")
        cfd = js["temps_par_segment"]["cfd"]["global"]
        semaines = cfd["semaines"]
        self.assertEqual(len(semaines), js["semaines"])
        self.assertEqual(semaines[0], js["periode"][0])
        i = semaines.index("2026-05-04")                  # fin de semaine : dimanche 05-10
        self.assertEqual(cfd["livres"][i], 1)             # ABC-0
        self.assertEqual(cfd["segments"]["definition"][i], 1)        # ABC-1 depuis le 05-06
        self.assertEqual(cfd["segments"]["implementation"][i], 1)    # ABC-2 : la transition du dimanche compte
        self.assertEqual(cfd["a_faire"][i], 0)
        derniere = cfd["segments"]["implementation"][-1], cfd["livres"][-1], cfd["a_faire"][-1]
        self.assertEqual(derniere, (2, 4, 0))             # ABC-3 et ABC-6 en implémentation ; quatre livrés
        self.assertEqual((cfd["tickets"], cfd["sans_historique"]), (6, 1))     # ABC-4 n'a pas d'historique

    def test_cfd_livres_cumules_croissants_et_jamais_plus_que_les_tickets(self):
        _, _, js, _ = self.lancer_avec("--history")
        for cfd in [js["temps_par_segment"]["cfd"]["global"], *js["temps_par_segment"]["cfd"]["par_equipe"].values()]:
            self.assertEqual(cfd["livres"], sorted(cfd["livres"]))
            for i in range(len(cfd["semaines"])):
                total = cfd["livres"][i] + cfd["a_faire"][i] + sum(v[i] for v in cfd["segments"].values())
                self.assertLessEqual(total, cfd["tickets"])

    def test_cfd_par_equipe_somme_au_global(self):
        _, _, js, _ = self.lancer_avec("--history")
        cfd = js["temps_par_segment"]["cfd"]
        equipes = cfd["par_equipe"]
        self.assertEqual([sum(e["livres"][i] for e in equipes.values()) for i in range(len(cfd["global"]["semaines"]))],
                         cfd["global"]["livres"])

    def test_pas_de_cfd_sans_historique(self):
        _, _, js, _ = self.lancer_avec()
        self.assertNotIn("temps_par_segment", js)

    def test_points_de_l_aging_wip_seulement_avec_l_option(self):
        ws, _, _, _ = self.lancer_avec("--history")
        self.assertFalse((ws / "Flux-Lab" / "tableaux").exists())
        ws, r, _, _ = self.lancer_avec("--history", "--points")
        fichier = ws / "Flux-Lab" / "tableaux" / "points-seg-2026-10-04.json"
        self.assertTrue(fichier.exists())
        self.assertIn("3 ticket(s) en cours", r.stdout)
        self.assertEqual(oct(fichier.stat().st_mode & 0o777), "0o600")
        self.assertEqual(oct(fichier.parent.stat().st_mode & 0o777), "0o700")
        contenu = json.loads(fichier.read_text(encoding="utf-8"))
        self.assertEqual(contenu["nom"], "seg")
        self.assertNotRegex(fichier.read_text(encoding="utf-8"), r"[A-Z]{2,}-\d+")      # aucune clé de ticket
        points = contenu["points"]
        self.assertEqual({tuple(sorted(p)) for p in points},
                         {("age", "age_segment", "equipe", "etat", "nature", "segment")})
        self.assertEqual([(p["equipe"], p["age"], p["segment"], p["age_segment"], p["nature"]) for p in points],
                         [("Equipe B", 10, "implementation", 10, "actif"),      # ABC-6
                          ("Equipe B", 33, "implementation", 14, "actif"),      # ABC-3
                          ("Equipe B", 64, None, None, "actif")])               # ABC-4 : sans historique

    def test_points_sans_historique_ni_segment(self):
        ws, _, _, _ = self.lancer_avec("--points")
        contenu = json.loads((ws / "Flux-Lab" / "tableaux" / "points-seg-2026-10-04.json").read_text(encoding="utf-8"))
        self.assertEqual({p["segment"] for p in contenu["points"]}, {None})
        self.assertEqual(len(contenu["points"]), 3)

    def test_points_nature_attente(self):
        ws = self.preparer('waiting_states: ["Implementation - Ongoing"]\n')
        r, js, _ = self.calcul(ws, "--points")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        contenu = json.loads((ws / "Flux-Lab" / "tableaux" / "points-seg-2026-10-04.json").read_text(encoding="utf-8"))
        self.assertEqual({p["nature"] for p in contenu["points"] if p["etat"] == "Implementation - Ongoing"}, {"attente"})


if __name__ == "__main__":
    unittest.main()
