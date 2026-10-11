"""Tests de tools/dependencies_jira.py sur des exports inventés (aucun appel à Jira, aucune donnée réelle).

Les mêmes tickets sont écrits en CSV manuel et en CSV de l'API (construit par export_jira_api.construire_csv) : la carte
doit être identique. Les dates sont relatives à aujourd'hui (le script n'a pas d'option de date).
Lancement : uv run --with pyyaml --with requests python -m unittest discover -s tests/dependencies_jira
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
SCRIPT = TOOLS / "dependencies_jira.py"
sys.path.insert(0, str(TOOLS))
import export_jira_api as ex          # noqa: E402

AUJOURDHUI = dt.date.today()
MOIS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CHAMP = "customfield_10001"


def jour(n: int | None) -> dt.date | None:
    return None if n is None else AUJOURDHUI - dt.timedelta(days=n)


def t(cle, equipe, etat="In Progress", cat="In Progress", type_="Story", cree=100, resolu=None, motif="", debut=None,
      parent="", sortants=(), entrants=()):
    """Un ticket inventé. cree, resolu et debut : nombre de jours avant aujourd'hui. sortants : tickets que celui-ci
    bloque (« Outward issue link (Blocks) ») ; entrants : tickets qui le bloquent (« Inward issue link (Blocks) »)."""
    return {"cle": cle, "equipe": equipe, "etat": etat, "cat": cat, "type": type_, "cree": cree, "resolu": resolu,
            "motif": motif, "debut": debut if debut is not None else cree, "parent": parent,
            "sortants": list(sortants), "entrants": list(entrants)}


def date_manuel(d: dt.date | None) -> str:
    return "" if d is None else f"{d.day:02d}/{MOIS[d.month - 1]}/{d.year} 08:00"


def date_api(d: dt.date | None):
    return None if d is None else f"{d.isoformat()}T08:00:00.000+0000"


def ecrire_manuel(chemin: Path, tickets: list[dict], liens_sans_type: bool = False) -> None:
    entete = ["Issue key", "Issue Type", "Status", "Status Category", "Created", "Resolved", "Resolution",
              "Status Category Changed", "Parent key", "Team"]
    entete += ["Linked Issues"] if liens_sans_type else ["Outward issue link (Blocks)", "Inward issue link (Blocks)"]
    with chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(entete)
        for x in tickets:
            ligne = [x["cle"], x["type"], x["etat"], x["cat"], date_manuel(jour(x["cree"])), date_manuel(jour(x["resolu"])),
                     x["motif"], date_manuel(jour(x["debut"])), x["parent"], x["equipe"]]
            ligne += ([", ".join(x["sortants"] + x["entrants"])] if liens_sans_type
                      else [", ".join(x["sortants"]), ", ".join(x["entrants"])])
            w.writerow(ligne)


def ecrire_api(chemin: Path, tickets: list[dict]) -> None:
    """Le CSV que export_jira_api.py écrirait pour ces tickets (sans table d'équipes : libellés renvoyés tels quels)."""
    api = []
    for x in tickets:
        liens = [{"type": {"name": "Blocks", "inward": "is blocked by", "outward": "blocks"}, "outwardIssue": {"key": c}}
                 for c in x["sortants"]]
        liens += [{"type": {"name": "Blocks", "inward": "is blocked by", "outward": "blocks"}, "inwardIssue": {"key": c}}
                  for c in x["entrants"]]
        api.append({"key": x["cle"], "fields": {
            "issuetype": {"name": x["type"]}, "status": {"name": x["etat"], "statusCategory": {"name": x["cat"]}},
            "created": date_api(jour(x["cree"])), "resolutiondate": date_api(jour(x["resolu"])),
            "resolution": {"name": x["motif"]} if x["motif"] else None,
            "statuscategorychangedate": date_api(jour(x["debut"])), "parent": {"key": x["parent"]} if x["parent"] else None,
            "issuelinks": liens, CHAMP: [{"value": x["equipe"]}]}})
    lignes, _ = ex.construire_csv(api, CHAMP, "Team")
    ex.ecrire_csv(chemin, lignes)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name)
        (self.ws / "Flux-Lab").mkdir()

    def reglages(self, texte: str) -> None:
        (self.ws / "Flux-Lab" / "flux.yaml").write_text(texte, encoding="utf-8")

    def lancer(self, *args: str, attendu: int = 0) -> str:
        env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(self.ws)}
        r = subprocess.run(["uv", "run", "--with", "pyyaml", str(SCRIPT), *args], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, attendu, r.stdout + r.stderr)
        return r.stdout + r.stderr

    def csv(self, tickets: list[dict], nom: str = "manuel.csv", api: bool = False, **kw) -> str:
        chemin = self.ws / nom
        (ecrire_api(chemin, tickets) if api else ecrire_manuel(chemin, tickets, **kw))
        return str(chemin)

    def calcul(self, *exports: str, extra=(), nom="t") -> dict:
        self.lancer("compute", *exports, "--name", nom, *extra)
        fichier = self.ws / "Flux-Lab" / "rapports" / f"dependances-{nom}-{AUJOURDHUI.isoformat()}.json"
        return json.loads(fichier.read_text(encoding="utf-8"))


class Sens(Base):
    TICKETS = [
        t("AAA-1", "Alpha", sortants=["BBB-1"]),                                    # AAA-1 bloque BBB-1 : BBB-1 attend AAA-1
        t("BBB-1", "Beta", entrants=["AAA-1"]),                                     # même lien vu de l'autre côté
        t("BBB-2", "Beta", entrants=["CCC-1"]),                                     # BBB-2 attend CCC-1 (pas commencé)
        t("CCC-1", "Gamma", etat="Open", cat="To Do", sortants=["BBB-2"]),
        t("DDD-1", "Delta", etat="Done", cat="Done", resolu=5, motif="Done", sortants=["AAA-1"]),   # bloquant terminé
    ]

    def test_le_lien_vu_des_deux_cotes_compte_une_fois_et_la_ligne_attend_la_colonne(self):
        r = self.calcul(self.csv(self.TICKETS))
        self.assertEqual(r["mode"], "orienté")
        self.assertEqual(r["dependances"], 3)
        self.assertEqual(sorted(r["matrice_ouverte"]), [["Beta", "Alpha", 1], ["Beta", "Gamma", 1]])
        self.assertEqual(sorted(r["matrice_totale"]), [["Alpha", "Delta", 1], ["Beta", "Alpha", 1], ["Beta", "Gamma", 1]])

    def test_blocages_en_cours_selon_l_etat_du_bloquant(self):
        r = self.calcul(self.csv(self.TICKETS))
        par_etat = {(a, b): e for a, b, e, *_ in r["blocages"]}
        self.assertEqual(par_etat, {("Beta", "Alpha"): "en cours", ("Beta", "Gamma"): "pas commencé"})

    def test_types_de_liens_en_attente_se_lisent_a_l_envers(self):
        self.reglages("waiting_link_types: [Depends]\n")
        chemin = self.ws / "attente.csv"
        with chemin.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Issue key", "Status", "Status Category", "Created", "Team", "Outward issue link (Depends)"])
            w.writerow(["AAA-1", "In Progress", "In Progress", date_manuel(jour(50)), "Alpha", "BBB-1"])   # AAA-1 attend BBB-1
            w.writerow(["BBB-1", "In Progress", "In Progress", date_manuel(jour(50)), "Beta", ""])
        r = self.calcul(str(chemin))
        self.assertEqual(r["matrice_ouverte"], [["Alpha", "Beta", 1]])

    def test_un_type_de_lien_inconnu_est_ignore(self):
        chemin = self.ws / "autre.csv"
        with chemin.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Issue key", "Status", "Status Category", "Created", "Team", "Outward issue link (Relates)"])
            w.writerow(["AAA-1", "In Progress", "In Progress", date_manuel(jour(50)), "Alpha", "BBB-1"])
            w.writerow(["BBB-1", "In Progress", "In Progress", date_manuel(jour(50)), "Beta", ""])
        r = self.calcul(str(chemin))
        self.assertEqual(r["dependances"], 0)

    def test_liens_sans_type_mode_non_oriente(self):
        r = self.calcul(self.csv(self.TICKETS, liens_sans_type=True))
        self.assertEqual(r["mode"], "non orienté")
        self.assertEqual(r["blocages"], [])
        self.assertIn("non orienté", self.lancer("diagnose", str(self.ws / "manuel.csv")))


class AretesDuGraphe(Base):
    """Données pour le graphe interactif du tableau de bord : une arête par paire d'équipes, et les tickets par équipe."""

    def test_aretes_par_paire_avec_age_des_blocages(self):
        r = self.calcul(self.csv(Sens.TICKETS))
        par_paire = {(a["de"], a["vers"]): a for a in r["aretes"]}
        self.assertEqual(set(par_paire), {("Beta", "Alpha"), ("Beta", "Gamma"), ("Alpha", "Delta")})
        beta_alpha = par_paire[("Beta", "Alpha")]
        self.assertEqual((beta_alpha["ouvertes"], beta_alpha["inconnues"], beta_alpha["toutes"]), (1, 0, 1))
        self.assertEqual((beta_alpha["bloquees_en_cours"], beta_alpha["age_bloquees"]["p50"]), (1, 100))
        self.assertTrue(beta_alpha["oriente"])
        termine = par_paire[("Alpha", "Delta")]                     # le bloquant est terminé : rien d'ouvert
        self.assertEqual((termine["ouvertes"], termine["toutes"], termine["bloquees_en_cours"]), (0, 1, 0))
        self.assertIsNone(termine["age_bloquees"])

    def test_aretes_et_tickets_par_equipe_sans_cle(self):
        r = self.calcul(self.csv(Sens.TICKETS))
        self.assertEqual(r["equipes_tickets"], {"Alpha": 1, "Beta": 2, "Delta": 1, "Gamma": 1})
        brut = json.dumps(r)
        for cle in ("AAA-1", "BBB-1", "CCC-1", "DDD-1"):
            self.assertNotIn(cle, brut)

    def test_aretes_dependance_vers_un_ticket_hors_export(self):
        r = self.calcul(self.csv([t("BBB-1", "Beta", entrants=["ZZZ-1"])]))
        self.assertEqual([(a["de"], a["vers"], a["ouvertes"], a["inconnues"]) for a in r["aretes"]],
                         [("Beta", "(hors export)", 0, 1)])

    def test_aretes_en_mode_non_oriente(self):
        r = self.calcul(self.csv(Sens.TICKETS, liens_sans_type=True))
        self.assertTrue(all(not a["oriente"] for a in r["aretes"]))


class ManuelEtApi(Base):
    def test_meme_carte_depuis_le_csv_manuel_et_le_csv_de_l_api(self):
        tickets = Sens.TICKETS + [
            t("BBB-3", "Beta", sortants=["ZZZ-9"]),                                  # vers un ticket absent de l'export
            t("BBB-4", "Beta", entrants=["ZZZ-8"])]
        manuel = self.calcul(self.csv(tickets), nom="m")
        api = self.calcul(self.csv(tickets, nom="api.csv", api=True), nom="a")
        for rapport in (manuel, api):
            rapport.pop("export"); rapport.pop("nom")
        self.assertEqual(manuel, api)
        self.assertEqual(api["hors_export"], 2)

    def test_diagnostic_lit_les_colonnes_de_l_api(self):
        sortie = self.lancer("diagnose", self.csv(Sens.TICKETS, nom="api.csv", api=True))
        self.assertIn("Mode : orienté", sortie)
        self.assertIn("Blocks", sortie)
        self.assertIn("dépendance (sortant = bloque)", sortie)
        for cle in ("AAA-1", "BBB-1", "Alpha", "Beta"):
            self.assertNotIn(cle, sortie)                                              # aucune clé ni nom affiché

    def test_aucune_cle_ni_nom_de_ticket_dans_le_rapport(self):
        self.calcul(self.csv(Sens.TICKETS))
        md = (self.ws / "Flux-Lab" / "rapports" / f"dependances-t-{AUJOURDHUI.isoformat()}.md").read_text(encoding="utf-8")
        for cle in ("AAA-1", "BBB-1", "CCC-1", "DDD-1"):
            self.assertNotIn(cle, md)
        self.assertIn("Alpha", md)                                                     # les équipes, elles, y sont

    def test_option_cles_affiche_les_blocages_dans_le_terminal_seulement(self):
        sortie = self.lancer("compute", self.csv(Sens.TICKETS), "--name", "t", "--keys")
        self.assertIn("BBB-1 (Beta) attend AAA-1 (Alpha, en cours)", sortie)

    def test_plusieurs_exports_fusionnes_par_cle(self):
        lot1 = self.csv(Sens.TICKETS[:3], nom="lot1.csv")
        lot2 = self.csv(Sens.TICKETS[2:], nom="lot2.csv")                              # BBB-2 en double
        r = self.calcul(lot1, lot2)
        seul = self.calcul(self.csv(Sens.TICKETS, nom="tout.csv"), nom="s")
        self.assertEqual(r["tickets"], 5)
        self.assertEqual(r["matrice_ouverte"], seul["matrice_ouverte"])
        self.assertEqual(r["dependances"], seul["dependances"])

    def test_nombre_rond_de_tickets_signale_comme_tronque(self):
        beaucoup = [t(f"AAA-{i}", "Alpha") for i in range(1000)]
        sortie = self.lancer("diagnose", self.csv(beaucoup))
        self.assertIn("Attention : 1000 tickets, un nombre rond", sortie)
        r = self.calcul(self.csv(beaucoup), nom="r")
        self.assertEqual(len(r["tronques"]), 1)

    def test_colonne_de_cle_absente_arrete_avec_un_message(self):
        chemin = self.ws / "sans-cle.csv"
        chemin.write_text("Status,Team\nOpen,Alpha\n", encoding="utf-8")
        self.assertIn("Colonne absente de l'export", self.lancer("diagnose", str(chemin), attendu=1))


class Perimetre(Base):
    TICKETS = [
        t("AAA-1", "Alpha", sortants=["BBB-1"]), t("BBB-1", "Beta", entrants=["AAA-1"]),
        t("BBB-2", "Beta", sortants=["CCC-1"]), t("CCC-1", "Gamma", entrants=["BBB-2"]),
        t("DDD-1", "Delta", sortants=["CCC-2"]), t("CCC-2", "Gamma", entrants=["DDD-1"])]

    def test_sans_option_tous_les_liens(self):
        r = self.calcul(self.csv(self.TICKETS))
        self.assertEqual(r["dependances"], 3)
        self.assertEqual(r["tickets_perimetre"], 6)

    def test_perimetre_garde_les_liens_dont_un_cote_est_dans_le_perimetre(self):
        r = self.calcul(self.csv(self.TICKETS), extra=["--scope", "CCC"])
        self.assertEqual(r["dependances"], 2)                                         # BBB-2/CCC-1 et DDD-1/CCC-2
        self.assertEqual(r["tickets_perimetre"], 2)
        r = self.calcul(self.csv(self.TICKETS), extra=["--scope", "aaa, ddd"], nom="b")
        self.assertEqual(r["dependances"], 2)
        self.assertEqual(r["tickets_perimetre"], 2)

    def test_option_remplace_le_reglage_et_tous_le_desactive(self):
        self.reglages("scope_projects: [AAA]\n")
        self.assertEqual(self.calcul(self.csv(self.TICKETS))["dependances"], 1)       # le réglage de flux.yaml
        self.assertEqual(self.calcul(self.csv(self.TICKETS), extra=["--scope", "DDD"], nom="b")["dependances"], 1)
        r = self.calcul(self.csv(self.TICKETS), extra=["--scope", "tous"], nom="c")
        self.assertEqual(r["dependances"], 3)

    def test_diagnostic_dit_le_perimetre(self):
        sortie = self.lancer("diagnose", self.csv(self.TICKETS), "--scope", "CCC")
        self.assertIn("Périmètre : CCC (2 tickets", sortie)


class Exclusions(Base):
    def test_projet_exclu_compte_a_part_hors_de_la_matrice(self):
        self.reglages("excluded_projects: [BUG]\n")
        r = self.calcul(self.csv([
            t("AAA-1", "Alpha", entrants=["BUG-1"]), t("BUG-1", "Alpha", sortants=["AAA-1"]),
            t("AAA-2", "Alpha", sortants=["BUG-2"]), t("BUG-2", "Alpha", entrants=["AAA-2"]),
            t("AAA-3", "Alpha", sortants=["BBB-1"]), t("BBB-1", "Beta", entrants=["AAA-3"])]))
        self.assertEqual(sorted(r["exclus"]), [["BUG", "attend l'export", 1], ["BUG", "attendu par l'export", 1]])
        self.assertEqual(r["dependances"], 1)                                          # les liens du projet exclu sortent du compte
        self.assertEqual(r["matrice_totale"], [["Beta", "Alpha", 1]])

    def test_liens_de_decomposition_hors_de_la_carte(self):
        self.reglages("portfolio_types: [Epic]\n")
        r = self.calcul(self.csv([
            t("AAA-1", "Alpha", type_="Epic", sortants=["BBB-1"]), t("BBB-1", "Beta", entrants=["AAA-1"]),    # Epic vers Story
            t("AAA-2", "Alpha", type_="Epic", sortants=["BBB-2"]), t("BBB-2", "Beta", type_="Epic", entrants=["AAA-2"])]))
        self.assertEqual(r["types_exclus"], [["Epic", 1]])
        self.assertEqual(r["matrice_totale"], [["Beta", "Alpha", 1]])
        self.assertEqual(r["matrice_portefeuille"], [["Beta", "Alpha", 1]])             # l'autre : Epic bloquée par Epic

    def test_ancien_nom_types_exclus_refuse(self):
        self.reglages("types_exclus: [Epic]\n")
        sortie = self.lancer("compute", self.csv([t("AAA-1", "Alpha", type_="Epic", sortants=["BBB-1"]),
                                                  t("BBB-1", "Beta", entrants=["AAA-1"])]), "--name", "x", attendu=1)
        self.assertIn("« types_exclus » n'existe plus ; utiliser « portfolio_types »", sortie)

    def test_ticket_sans_equipe_garde_son_projet(self):
        r = self.calcul(self.csv([t("AAA-1", "", sortants=["BBB-1"]), t("BBB-1", "Beta", entrants=["AAA-1"])]))
        self.assertEqual(r["matrice_ouverte"], [["Beta", "(sans équipe : AAA)", 1]])

    def test_agregation_par_projet(self):
        self.lancer("compute", self.csv(Sens.TICKETS), "--name", "p", "--by", "project")
        fichier = self.ws / "Flux-Lab" / "rapports" / f"dependances-p-projets-{AUJOURDHUI.isoformat()}.json"
        r = json.loads(fichier.read_text(encoding="utf-8"))
        self.assertEqual(sorted(r["matrice_ouverte"]), [["BBB", "AAA", 1], ["BBB", "CCC", 1]])


class Anciennete(Base):
    """Blocages anciens, attentes vers un élément hors export et Epics anciens (vivants ou abandonnés)."""

    def test_blocage_de_plus_d_un_an_est_a_part(self):
        r = self.calcul(self.csv([
            t("AAA-1", "Alpha", sortants=["BBB-1"]), t("BBB-1", "Beta", entrants=["AAA-1"], debut=400, cree=500),
            t("AAA-2", "Alpha", sortants=["BBB-2"]), t("BBB-2", "Beta", entrants=["AAA-2"], debut=40)]))
        self.assertEqual([[a, b, n] for a, b, n, _ in r["blocages_anciens"]], [["Beta", "Alpha", 1]])
        self.assertEqual([(a, b, n) for a, b, _, n, *_ in r["blocages"]], [("Beta", "Alpha", 1)])

    def test_attente_vers_un_element_hors_export(self):
        r = self.calcul(self.csv([t("BBB-1", "Beta", entrants=["ZZZ-1"]), t("BBB-2", "Beta", entrants=["ZZZ-2"])]))
        self.assertEqual([(a, p, n) for a, p, n, _ in r["attentes_inconnues"]], [("Beta", "ZZZ", 2)])
        self.assertEqual(r["hors_export"], 2)

    def test_epics_anciens_vivants_inactifs_ou_sans_enfant(self):
        self.reglages("portfolio_types: [Epic]\n")
        r = self.calcul(self.csv([
            # E-1 : enfant qui a bougé il y a 10 jours : vivant
            t("EPA-1", "Alpha", type_="Epic", cree=800, debut=700, sortants=["EPB-1"]),
            t("EPB-1", "Beta", type_="Epic", cree=800, debut=700, entrants=["EPA-1"]),
            t("STA-1", "Alpha", parent="EPA-1", debut=10),
            # EPB-1 : aucun enfant : sans enfant de livraison. EPA-2 : enfant inactif depuis 400 jours
            t("EPA-2", "Alpha", type_="Epic", cree=900, debut=800, sortants=["EPG-1"]),
            t("EPG-1", "Gamma", type_="Epic", cree=900, debut=800, entrants=["EPA-2"]),
            t("STA-2", "Alpha", parent="EPA-2", debut=400),
            # EPG-1 : enfant clos sans livraison (rejet) il y a 5 jours : ne compte pas comme activité
            t("STG-1", "Gamma", parent="EPG-1", etat="Rejected", cat="Done", resolu=5, motif="Rejected", cree=300)]))
        lignes = {(e, etat): n for e, etat, n in r["epics_anciens"]["lignes"]}
        self.assertEqual(lignes, {("Alpha", "vivant"): 1, ("Alpha", "enfants inactifs"): 1,
                                  ("Beta", SANS_ENFANT): 1, ("Gamma", "enfants inactifs"): 1})

    def test_epic_recent_ou_sans_lien_ouvert_non_compte(self):
        self.reglages("portfolio_types: [Epic]\n")
        r = self.calcul(self.csv([
            t("EPA-1", "Alpha", type_="Epic", cree=100, debut=50, sortants=["EPB-1"]),                 # trop récent
            t("EPB-1", "Beta", type_="Epic", cree=100, debut=50, entrants=["EPA-1"]),
            t("EPA-2", "Alpha", type_="Epic", cree=800, debut=700),                                    # aucun lien
            t("STA-1", "Alpha", parent="EPA-2", debut=10)]))
        self.assertEqual(r["epics_anciens"]["lignes"], [])


class LeadTime(Base):
    def test_lead_time_avec_et_sans_dependance_externe(self):
        livres = []
        for i in range(6):                           # six livrés sans dépendance externe, quatre jours de lead time chacun
            livres.append(t(f"AAA-{i}", "Alpha", etat="Done", cat="Done", cree=30 + i, resolu=26 + i, motif="Done"))
        for i in range(5):                           # cinq livrés qui attendaient une autre équipe : dix jours chacun
            livres.append(t(f"BBB-{i}", "Beta", etat="Done", cat="Done", cree=30 + i, resolu=20 + i, motif="Done",
                            entrants=[f"CCC-{i}"]))
            livres.append(t(f"CCC-{i}", "Gamma", etat="Done", cat="Done", cree=60, resolu=40, motif="Done", sortants=[f"BBB-{i}"]))
        r = self.calcul(self.csv(livres))
        par_type = {typ: (av, sa) for typ, av, sa in r["lead_time"]["par_type"]}
        avec, sans = par_type["Story"]
        self.assertEqual(avec["n"], 5)
        self.assertEqual(avec["p50"], 10)
        self.assertEqual(sans["n"], 11)                                              # six AAA et cinq CCC (bloquants, pas bloqués)
        self.assertEqual(sans["p50"], 4)

    def test_clos_sans_livraison_hors_du_lead_time(self):
        r = self.calcul(self.csv([t(f"AAA-{i}", "Alpha", etat="Rejected", cat="Done", cree=30, resolu=5, motif="Rejected")
                                  for i in range(8)] + [t("BBB-1", "Beta", sortants=["AAA-0"])]))
        self.assertEqual(r["lead_time"]["par_type"], [])


SANS_ENFANT = "sans enfant de livraison"

class AnciensNoms(Base):
    """Plan 7.1 : anciens noms d'options, de valeurs et de réglages acceptés avec un avertissement ; anciens noms de
    sous-commandes refusés ; même rapport quels que soient les noms."""

    def rapport(self, nom, projets=False):
        suffixe = "-projets" if projets else ""
        return (self.ws / "Flux-Lab" / "rapports" / f"dependances-{nom}{suffixe}-{AUJOURDHUI.isoformat()}.json").read_text(encoding="utf-8")

    def test_anciennes_options_et_valeur_refusees_avec_le_nom_actuel(self):
        csv = self.csv(Sens.TICKETS)
        for ancien, nouveau in (("--nom", "--name"), ("--par", "--by"), ("--semaines", "--weeks")):
            sortie = self.lancer("compute", csv, ancien, "2", attendu=2)
            self.assertIn(f"« {ancien} » n'existe plus ; utiliser « {nouveau} »", sortie)
        sortie = self.lancer("compute", csv, "--name", "n", "--by", "projet", attendu=2)
        self.assertIn("« projet » n'existe plus ; utiliser « project »", sortie)
        self.assertFalse(list((self.ws / "Flux-Lab" / "rapports").glob("dependances-n*")))

    def test_anciens_noms_de_sous_commandes_refuses(self):
        for ancien in ("calcul", "diagnostic"):
            self.assertIn("invalid choice", self.lancer(ancien, self.csv(Sens.TICKETS), attendu=2))

    def test_ancien_nom_de_reglage_refuse_nouveau_nom_sans_message(self):
        csv = self.csv(Sens.TICKETS)
        self.reglages("projets_exclus: [CCC]\n")
        ancien = self.lancer("compute", csv, "--name", "k", attendu=1)
        self.assertIn("« projets_exclus » n'existe plus ; utiliser « excluded_projects »", ancien)
        self.reglages("excluded_projects: [CCC]\nexcluded_resolutions: [Rejected]\n")
        nouveau = self.lancer("compute", csv, "--name", "k")
        self.assertNotIn("n'existe plus", nouveau)


if __name__ == "__main__":
    unittest.main()
