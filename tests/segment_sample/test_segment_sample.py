"""Tests de segment_sample.py sur un faux espace de travail (faux export, faux cache, aucune donnée réelle).

    uv run --with pyyaml --with numpy python -m unittest discover -s tests/segment_sample -v

Le script est lancé comme l'utilisateur le lance, avec PMZILLA_LAB_WORKSPACE sur un dossier temporaire. On vérifie :
- les visites, l'origine et la destination sur des cas construits à la main (aller-retour, résolution depuis le
  segment, création dans le segment, sortie avant la période, projet écarté, ticket sans historique) ;
- la population et le P50 identiques à ceux de la section « Temps par segment » de flux_jira.py compute --history ;
- le tirage reproductible à graine fixe, et sans recouvrement avec les plus longs ;
- les plus anciens encore dans le segment ;
- aucune écriture sur le disque, aucun titre ni nom dans la sortie ;
- --debuts : passages de Ready for Verification à Verification - Ongoing par projet ;
- --par-etat : temps par état (total, part, P50, P85, tickets), détail de l'échantillon, sorties groupées.
"""
import datetime as dt
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))
import segment_sample as es

ICI = Path(__file__).resolve().parent
OUTILS = ICI.parent.parent / "tools"
SCRIPT = OUTILS / "segment_sample.py"
FLUX = OUTILS / "flux_jira.py"
FMT = "%d/%b/%Y %H:%M"
AUJOURDHUI = "2026-10-06"          # période : 2026-04-06 au 2026-10-04
D = dt.date.fromisoformat
JOURS = len(es.jours_ouvres(D("2026-04-06"), D("2026-10-04")))      # jours fériés français retirés : 124 et non 130
ENTETE = "Issue key,Issue Type,Summary,Status,Created,Resolved,Resolution"
REVUE = "Ready for Verification"
IMPL = "Implementation - Ongoing"


def iso(jour: str) -> str:
    return f"{jour}T09:00:00.000+0200"


def ligne(cle: str, cree: str, etat: str, resolu: str = "", motif: str = "") -> str:
    f = lambda j: D(j).strftime(FMT) if j else ""
    return f"{cle},Story,TITRE SECRET {cle},{etat},{f(cree)},{f(resolu)},{motif}"


class Atelier:
    """Faux espace de travail : export CSV, cache d'historique et flux.yaml."""

    def __init__(self, racine: Path):
        self.ws = racine
        (racine / "Flux-Lab" / "historique").mkdir(parents=True)
        (racine / "Flux-Lab" / "exports").mkdir()
        (racine / "Flux-Lab" / "flux.yaml").write_text(
            "excluded_projects: [EXC]\nportfolio_types: [Initiative]\nwaiting_states: ['Ready for', 'On Hold']\n",
            encoding="utf-8")
        self.lignes, self.cache = [], {}

    def ticket(self, cle, cree, etat, transitions, resolu="", motif=""):
        """transitions : [(jour, de, vers)] ; etat : état actuel du ticket dans l'export."""
        self.lignes.append(ligne(cle, cree, etat, resolu, motif))
        self.cache[cle] = {"termine": bool(resolu), "transitions": [[iso(j), de, vers] for j, de, vers in transitions]}

    def sans_historique(self, cle, cree, etat):
        self.lignes.append(ligne(cle, cree, etat))

    def ecrire(self) -> Path:
        export = self.ws / "Flux-Lab" / "exports" / "faux.csv"
        export.write_text("\n".join([ENTETE] + self.lignes) + "\n", encoding="utf-8")
        (self.ws / "Flux-Lab" / "historique" / "transitions.json").write_text(json.dumps(self.cache), encoding="utf-8")
        return export

    def lancer(self, script: Path, *args: str) -> str:
        env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(self.ws)}
        r = subprocess.run(["uv", "run", str(script), *args], env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        return r.stdout


def construire(a: Atelier) -> None:
    # AAA-1 : deux visites (41 j puis 15 j), la première reste dans le segment en changeant d'état
    a.ticket("AAA-1", "2026-05-01", "Accepted & Released", [
        ("2026-05-02", "Open", "Code Review (Impl)"), ("2026-05-10", "Code Review (Impl)", REVUE),
        ("2026-06-10", REVUE, "Verification - Ongoing"), ("2026-06-20", "Verification - Ongoing", IMPL),
        ("2026-06-25", IMPL, REVUE), ("2026-07-10", REVUE, "Ready for Acceptance"),
        ("2026-07-20", "Ready for Acceptance", "Accepted & Released")], resolu="2026-07-20", motif="Accepted & Released")
    # FFF-1 : résolu depuis le segment (60 j) ; GGG-1 : créé directement dans le segment (30 j)
    a.ticket("FFF-1", "2026-05-01", "Done", [("2026-05-02", "Open", REVUE), ("2026-07-01", REVUE, "Done")],
             resolu="2026-07-01", motif="Done")
    a.ticket("GGG-1", "2026-06-01", "Done", [("2026-07-01", REVUE, IMPL), ("2026-07-02", IMPL, "Done")],
             resolu="2026-07-02", motif="Done")
    # RRR-1 : résolu au début de la période, sans passage dans le segment ; sans lui, flux_jira.py réduit la période
    # à partir de la première résolution de l'export (voir cmd_calcul) et les BBB, non résolus, en sortiraient
    a.ticket("RRR-1", "2026-03-01", "Done", [("2026-03-05", "Open", IMPL), ("2026-04-08", IMPL, "Done")],
             resolu="2026-04-08", motif="Done")
    # EEE-1 : sortie avant la période (hors population) ; EXC-1 : projet écarté ; ABC-9 : sans historique
    a.ticket("EEE-1", "2026-01-01", IMPL, [("2026-02-01", "Open", REVUE), ("2026-03-01", REVUE, IMPL)])
    a.ticket("EXC-1", "2026-05-01", IMPL, [("2026-05-02", "Open", REVUE), ("2026-07-01", REVUE, IMPL)])
    a.sans_historique("ABC-9", "2026-05-01", REVUE)
    # BBB-1 à BBB-40 : une visite de 1 à 40 jours, qui finit pendant la période
    for i in range(1, 41):
        entree = D("2026-05-01")
        a.ticket(f"BBB-{i}", "2026-04-20", IMPL, [
            ((entree).isoformat(), "Open", REVUE), ((entree + dt.timedelta(days=i)).isoformat(), REVUE, IMPL)])
    # CCC-1 à CCC-3 : très longs (200, 190, 180 jours) ; DDD-1 à DDD-4 : encore dans le segment depuis longtemps
    for i, jours in enumerate((200, 190, 180), 1):
        entree = D("2026-01-10")
        a.ticket(f"CCC-{i}", "2026-01-01", IMPL, [
            (entree.isoformat(), "Open", REVUE), ((entree + dt.timedelta(days=jours)).isoformat(), REVUE, IMPL)])
    for i, entree in enumerate(("2026-03-01", "2026-04-01", "2026-05-01", "2026-06-01"), 1):
        a.ticket(f"DDD-{i}", "2026-02-01", REVUE, [(entree, "Open", REVUE)])
    # Initiative écartée du calcul (type de portefeuille)
    a.lignes.append(ligne("INI-1", "2026-05-01", REVUE).replace(",Story,", ",Initiative,"))
    a.cache["INI-1"] = {"termine": False, "transitions": [[iso("2026-05-02"), "Open", REVUE]]}


def lignes_de(sortie: str, titre: str) -> list[list[str]]:
    """Cellules des lignes du tableau Markdown qui suit le titre de section commençant par `titre`."""
    bloc = sortie.split(titre, 1)[1].split("\n## ", 1)[0]
    rangees = [l for l in bloc.splitlines() if l.startswith("| ") and "---" not in l]
    return [[c.strip() for c in l.strip("|").split(" | ")] for l in rangees[1:]]


def ticket_a_l_heure(a: Atelier, cle: str, entree: str, sortie: str, resolu_a: str, motif: str = "Done") -> None:
    """Ticket qui entre dans « Ready for Verification » le jour `entree`, passe en vérification le lendemain, puis est
    résolu depuis le segment le jour `sortie`, à l'heure `resolu_a` (AAAA-MM-JJ HH:MM)."""
    resolu = dt.datetime.strptime(resolu_a, "%Y-%m-%d %H:%M").strftime(FMT)
    cree = D("2026-04-20").strftime(FMT)
    a.lignes.append(f"{cle},Story,TITRE SECRET {cle},Done,{cree},{resolu},{motif}")
    suite = (D(entree) + dt.timedelta(days=1)).isoformat()
    a.cache[cle] = {"termine": True, "transitions": [
        [iso(entree), "Open", REVUE], [iso(suite), REVUE, "Verification - Ongoing"],
        [iso(sortie), "Verification - Ongoing", "Done"]]}


def construire_lots(a: Atelier) -> None:
    """LOT : 6 tickets résolus dans la même minute (un lot, seuil 5). ETA : 6 tickets résolus le même jour mais à des
    minutes différentes (fermetures étalées). PET : 4 tickets dans la même minute (sous le seuil)."""
    a.ticket("RRR-1", "2026-03-01", "Done", [("2026-03-05", "Open", IMPL), ("2026-04-08", IMPL, "Done")],
             resolu="2026-04-08", motif="Done")                 # fixe le début de la période
    for i in range(1, 7):
        ticket_a_l_heure(a, f"LOT-{i}", f"2026-05-{i:02d}", "2026-07-20", "2026-07-20 10:15")
    for i in range(1, 7):
        ticket_a_l_heure(a, f"ETA-{i}", f"2026-05-{i:02d}", "2026-07-20", f"2026-07-20 10:{i:02d}")
    for i in range(1, 5):
        ticket_a_l_heure(a, f"PET-{i}", f"2026-05-{i:02d}", "2026-07-21", "2026-07-21 11:00")


class TestFermeturesEnLot(unittest.TestCase):
    """--exclude-batch-closures : les tickets sortis du segment dans une fermeture en lot sont retirés de la population."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.a = Atelier(Path(self._tmp.name))
        construire_lots(self.a)
        self.export = str(self.a.ecrire())

    def lancer(self, *args):
        return self.a.lancer(SCRIPT, self.export, "--today", AUJOURDHUI, *args)

    def test_sans_l_option_la_sortie_ne_change_pas(self):
        sortie = self.lancer()
        self.assertIn("Tickets sortis du segment pendant la période : 16", sortie)
        self.assertNotIn("Fermetures en lot", sortie)
        self.assertNotIn("--exclude-batch-closures", sortie)
        self.assertEqual(sortie, self.lancer())

    def test_un_lot_dans_la_meme_minute_est_ecarte_et_pas_les_fermetures_etalees(self):
        sortie = self.lancer("--exclude-batch-closures", "--oldest", "0", "--longest", "100", "--near-median", "0")
        self.assertIn("Tickets sortis du segment pendant la période : 10", sortie)   # 16 - les 6 LOT
        self.assertNotIn("LOT-", sortie)
        for i in range(1, 7):
            self.assertIn(f"ETA-{i} ", sortie)                    # étalées sur 6 minutes : conservées
        for i in range(1, 5):
            self.assertIn(f"PET-{i} ", sortie)                    # 4 dans la même minute, sous le seuil de 5 : conservées

    def test_entete_avec_les_comptes(self):
        sortie = self.lancer("--exclude-batch-closures")
        entete = sortie.split("## États du segment", 1)[0]
        self.assertIn("Fermetures en lot écartées (--exclude-batch-closures) : 6 tickets sortis du segment, "
                      "6 passages de « Ready for Verification » à « Verification - Ongoing ».", entete)
        self.assertNotIn("sans heure de résolution", sortie)

    def test_tous_les_calculs_sont_faits_sans_les_tickets_ecartes(self):
        sans = self.lancer("--exclude-batch-closures", "--by-state", "--starts", "--min-passes", "1")
        avec = self.lancer("--by-state", "--starts", "--min-passes", "1")
        # temps par état : 10 tickets au lieu de 16
        self.assertIn("(population de 10 tickets sortis)", sans)
        self.assertIn("(population de 16 tickets sortis)", avec)
        # passages par projet : le projet LOT disparaît, ETA et PET restent
        projets_sans = {r[0] for r in lignes_de(sans, "## Passages de")}
        projets_avec = {r[0] for r in lignes_de(avec, "## Passages de")}
        self.assertEqual(projets_avec, {"LOT", "ETA", "PET"})
        self.assertEqual(projets_sans, {"ETA", "PET"})
        self.assertIn("10 passages dans les visites terminées de la population, 10 tickets", sans)
        self.assertIn("16 passages dans les visites terminées de la population, 16 tickets", avec)
        # la population et le détail par état sont ceux des 10 tickets restants
        self.assertIn("Tickets sortis du segment pendant la période : 10", sans)

    def test_heure_absente_aucun_ticket_en_lot_et_decompte(self):
        # sans heure de résolution, deux tickets ne peuvent pas être dits « dans la même minute »
        tickets = [{"cle": f"P-{i}", "projet": "P", "resolu": D("2026-07-20"), "resolu_a": None, "motif": "Done"}
                   for i in range(8)]
        lot = es.lot_fermetures(tickets, {"seuil_fermetures_groupees": 5, "motifs_exclus": [],
                                          "motifs_fermetures_groupees": ["Done"]},
                                D("2026-04-06"), D("2026-10-04"), es.Messages(es.CATALOGS, "fr"))
        self.assertEqual(lot, {"cles": set(), "sans_heure": 8})
        sortie = es.Messages(es.CATALOGS, "fr")("batch_no_time", count=8)
        self.assertEqual(sortie, "8 tickets livrés sans heure de résolution : jamais comptés en lot.")

    def test_meme_regle_que_flux_jira(self):
        import flux_jira as fj
        done = [{"projet": "P", "resolu_a": dt.datetime(2026, 7, 20, 10, 15), "motif": "Done", "resolu": D("2026-07-20")}
                for _ in range(5)]
        done += [{"projet": "P", "resolu_a": dt.datetime(2026, 7, 20, 10, 16), "motif": "Done", "resolu": D("2026-07-20")}
                 for _ in range(4)]
        self.assertEqual(len(fj.tickets_en_fermeture_groupee(done, 5, {"done"})), 5)
        self.assertEqual(fj.fermetures_groupees(done, 5, {"done"})["total"]["tickets"], 5)
        self.assertEqual(len(fj.tickets_en_fermeture_groupee(done, 5, {"accepted"})), 0)


class TestEchantillon(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.atelier = Atelier(Path(self._tmp.name))
        construire(self.atelier)
        self.export = str(self.atelier.ecrire())

    def lancer(self, *args):
        return self.atelier.lancer(SCRIPT, self.export, "--today", AUJOURDHUI, *args)

    def test_cas_construits(self):
        sortie = self.lancer("--longest", "100")
        par_cle = {r[0]: r for r in lignes_de(sortie, "## Les ")}
        # colonnes : clé, projet, jours, visites, entrée, sortie, jours de la visite, origine, destination
        self.assertEqual(par_cle["AAA-1"][1:], ["AAA", "56", "2", "2026-05-10", "2026-06-20", "41", "Code Review (Impl)", IMPL])
        self.assertEqual(par_cle["FFF-1"][1:], ["FFF", "60", "1", "2026-05-02", "2026-07-01", "60", "Open", "Done"])
        self.assertEqual(par_cle["GGG-1"][1:5], ["GGG", "30", "1", "2026-06-01"])
        self.assertEqual(par_cle["GGG-1"][7], "(création)")
        self.assertEqual(par_cle["BBB-7"][1:], ["BBB", "7", "1", "2026-05-01", "2026-05-08", "7", "Open", IMPL])
        for absent in ("EEE-1", "EXC-1", "ABC-9", "INI-1", "DDD-1"):
            self.assertNotIn(absent, par_cle)

    def test_resolu_depuis_le_segment(self):
        a = self.atelier
        a.ticket("HHH-1", "2026-05-01", REVUE, [("2026-05-02", "Open", REVUE)], resolu="2026-06-01", motif="Done")
        a.ecrire()
        par_cle = {r[0]: r for r in lignes_de(self.lancer("--longest", "100"), "## Les ")}
        self.assertEqual(par_cle["HHH-1"][1:], ["HHH", "30", "1", "2026-05-02", "2026-06-01", "30", "Open",
                                               "(résolu depuis le segment)"])

    def test_etats_du_segment_et_population(self):
        sortie = self.lancer()
        for etat in ("Ready for Review (Implementation)", "Ready for Verification", "Verification - On Hold"):
            self.assertIn(f"- {etat}", sortie)
        self.assertNotIn("- Code Review (Impl)", sortie)
        self.assertIn("1 sans historique", sortie)
        self.assertIn("(2 écartés)", sortie)                       # EXC-1 (projet) et INI-1 (type)
        # 40 BBB + 3 CCC + AAA-1 + FFF-1 + GGG-1 = 46 tickets sortis pendant la période
        self.assertIn("Tickets sortis du segment pendant la période : 46 ;", sortie)

    def test_meme_population_que_flux_jira(self):
        sortie = self.lancer()
        self.atelier.lancer(FLUX, "compute", self.export, "--history", "--name", "parite", "--today", AUJOURDHUI)
        rapport = json.loads(next((self.atelier.ws / "Flux-Lab" / "rapports").glob("flux-parite-*.json")).read_text("utf-8"))
        ref = rapport["temps_par_segment"]["global"]["sortis"]["revue_verification"]
        self.assertEqual(ref["n"], 46)
        self.assertIn(f"Tickets sortis du segment pendant la période : {ref['n']} ; temps cumulé P50 "
                      f"{ref['p50']:.0f} j, P85 {ref['p85']:.0f} j, moyenne {ref['moyenne']:.1f} j", sortie)
        ref_dedans = rapport["temps_par_segment"]["global"]["dans_le_segment"]["revue_verification"]
        self.assertIn(f"sur {ref_dedans['n']})", sortie)

    def test_plus_longs_puis_proches_sans_recouvrement(self):
        sortie = self.lancer()
        longs = [r[0] for r in lignes_de(sortie, "## Les 6 plus longs")]
        self.assertEqual(longs, ["CCC-1", "CCC-2", "CCC-3", "FFF-1", "AAA-1", "BBB-40"])
        proches = lignes_de(sortie, "## 4 tickets proches")
        self.assertEqual(len(proches), 4)
        self.assertFalse({r[0] for r in proches} & set(longs))
        bas, haut = (float(x) for x in sortie.split("Fenêtre : de ")[1].split(" j (P40")[0].split(" à "))
        for r in proches:
            self.assertTrue(bas <= float(r[2]) <= haut, r)

    def test_tirage_reproductible_a_graine_fixe(self):
        premier = lignes_de(self.lancer("--seed", "7"), "## 4 tickets proches")
        second = lignes_de(self.lancer("--seed", "7"), "## 4 tickets proches")
        self.assertEqual(premier, second)
        autres = {tuple(r[0] for r in lignes_de(self.lancer("--seed", str(g)), "## 4 tickets proches"))
                  for g in range(1, 8)}
        self.assertGreater(len(autres), 1)

    def test_plus_anciens_dans_le_segment(self):
        sortie = self.lancer()
        anciens = lignes_de(sortie, "## Les 3 plus anciens")
        # DDD-1 : entré le 2026-03-01, âge au 2026-10-06 = 219 j
        self.assertEqual([r[0] for r in anciens], ["DDD-1", "DDD-2", "DDD-3"])
        self.assertEqual(anciens[0][1:], ["DDD", "219", "2026-03-01", "219", "1", REVUE, "Open"])
        self.assertIn("(sur 4)", sortie)           # DDD-1 à 4 ; ABC-9, sans historique, n'est pas compté

    def test_aller_retour_encore_dans_le_segment(self):
        a = self.atelier
        a.ticket("III-1", "2026-04-01", REVUE, [("2026-04-02", "Open", REVUE), ("2026-04-12", REVUE, IMPL),
                                              ("2026-05-01", IMPL, REVUE)])
        a.ecrire()
        anciens = {r[0]: r for r in lignes_de(self.lancer("--oldest", "10"), "plus anciens encore")}
        # visite en cours depuis le 2026-05-01 (158 j), visite précédente de 10 j : cumul 168, 2 visites
        self.assertEqual(anciens["III-1"][1:], ["III", "158", "2026-05-01", "168", "2", REVUE, IMPL])

    def test_anciennes_options_refusees_avec_le_nom_actuel(self):
        env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(self.atelier.ws)}
        for ancien, nouveau_nom in (("--aujourdhui", "--today"), ("--plus-longs", "--longest"), ("--graine", "--seed")):
            r = subprocess.run(["uv", "run", str(SCRIPT), self.export, ancien, "7"], env=env, capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn(f"« {ancien} » n'existe plus ; utiliser « {nouveau_nom} »", r.stderr)
            self.assertEqual(r.stdout, "")

    def test_segment_sous_son_nom_anglais(self):
        interne = self.lancer("--segment", "revue_verification")
        anglais = self.lancer("--segment", "review_verification")
        self.assertEqual(anglais, interne)

    def test_sortie_sans_titre_ni_ecriture(self):
        avant = {p for p in self.atelier.ws.rglob("*") if p.is_file()}
        sortie = self.lancer()
        self.assertNotIn("TITRE SECRET", sortie)
        self.assertEqual({p for p in self.atelier.ws.rglob("*") if p.is_file()}, avant)

    def test_segment_inconnu_et_export_sans_historique(self):
        env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(self.atelier.ws)}
        r = subprocess.run(["uv", "run", str(SCRIPT), self.export, "--segment", "nimportequoi"],
                           env=env, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("n'est pas un segment calculé", r.stdout + r.stderr)
        (self.atelier.ws / "Flux-Lab" / "historique" / "transitions.json").unlink()
        r = subprocess.run(["uv", "run", str(SCRIPT), self.export], env=env, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("cache introuvable", r.stdout + r.stderr)


class TestParEtat(unittest.TestCase):
    """--par-etat : temps par état, détail de l'échantillon, sorties groupées."""
    ETATS = ["Ready for Review (Implementation)", "Review - Ongoing (Impl.)", "Review - On Hold (Impl.)",
             "Ready for Verification", "Verification", "Verification - Ongoing", "Verification - On Hold"]

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.atelier = Atelier(Path(self._tmp.name))
        construire(self.atelier)
        self.export = str(self.atelier.ecrire())

    def lancer(self, *args):
        return self.atelier.lancer(SCRIPT, self.export, "--today", AUJOURDHUI, "--by-state", *args)

    def test_sans_l_option_rien_de_plus(self):
        sortie = self.atelier.lancer(SCRIPT, self.export, "--today", AUJOURDHUI)
        self.assertNotIn("Temps par état", sortie)
        self.assertNotIn("Sorties groupées", sortie)

    def test_temps_par_etat_de_la_population(self):
        sortie = self.lancer()
        lignes = {r[0]: r for r in lignes_de(sortie, "## Temps par état du segment")}
        self.assertEqual(list(lignes), self.ETATS)                       # les 7 états, dans l'ordre du réglage
        revue = [*range(1, 41), 200, 190, 180, 46, 60, 30]                # BBB, CCC, AAA-1, FFF-1, GGG-1
        p50, p85 = np.percentile(revue, 50), np.percentile(revue, 85)
        self.assertEqual(lignes["Ready for Verification"][1:], [
            "46", "1526", f"{100 * 1526 / 1536:.1f} %", f"{p50:.0f}", f"{p85:.0f}"])
        self.assertEqual(lignes["Verification - Ongoing"][1:], ["1", "10", f"{100 * 10 / 1536:.1f} %", "10", "10"])
        self.assertEqual(lignes["Verification"][1:], ["0", "0", "0.0 %", "-", "-"])
        self.assertIn("Total du segment : 1536 j", sortie)
        self.assertEqual(sum(int(r[2]) for r in lignes.values()), 1536)   # les états rendent le temps du segment

    def test_detail_des_tickets_de_l_echantillon(self):
        sortie = self.lancer()
        detail = {r[0]: r for r in lignes_de(sortie, "## Détail par état")}
        self.assertEqual(len(detail), 6 + 4 + 3)
        # colonnes : clé, groupe, total, puis les 7 états (indices 3 à 9)
        self.assertEqual(detail["AAA-1"][1:], ["plus long", "56", "-", "-", "-", "46", "-", "10", "-"])
        self.assertEqual(detail["CCC-1"][1:3], ["plus long", "200"])
        self.assertEqual(detail["DDD-1"][1:], ["encore dans le segment", "219", "-", "-", "-", "219", "-", "-", "-"])
        for cle, ligne_ in detail.items():
            if ligne_[1] == "tiré près de la médiane":
                self.assertEqual(ligne_[2], ligne_[6])                    # un seul état : total = Ready for Verification

    def test_detail_d_un_ticket_encore_dedans_avec_deux_visites(self):
        a = self.atelier
        a.ticket("III-1", "2026-04-01", "Verification - On Hold", [
            ("2026-04-02", "Open", REVUE), ("2026-04-12", REVUE, IMPL), ("2026-05-01", IMPL, "Verification - On Hold")])
        a.ecrire()
        detail = {r[0]: r for r in lignes_de(self.lancer("--oldest", "10"), "## Détail par état")}
        # 10 j dans « Ready for Verification », puis 158 j en cours dans « Verification - On Hold » (au 2026-10-06)
        self.assertEqual(detail["III-1"][1:], ["encore dans le segment", "168", "-", "-", "-", "10", "-", "-", "158"])

    def test_sorties_groupees(self):
        a = self.atelier
        for i in (1, 2, 3):           # trois tickets dont la visite finit le 2026-07-29, comme CCC-1
            a.ticket(f"JJJ-{i}", "2026-07-01", IMPL, [("2026-07-20", "Open", REVUE), ("2026-07-29", REVUE, IMPL)])
        a.ecrire()
        sortie = self.lancer()
        groupees = {r[0]: r for r in lignes_de(sortie, "## Sorties groupées")}
        self.assertEqual(groupees["CCC-1"][1:], ["2026-07-29", "3"])
        self.assertEqual(groupees["CCC-2"][1:], ["2026-07-19", "0"])
        self.assertEqual(groupees["FFF-1"][1:], ["2026-07-01", "1"])      # GGG-1 sort le même jour
        self.assertEqual(groupees["AAA-1"][1:], ["2026-06-20", "0"])
        self.assertEqual(set(groupees), {"CCC-1", "CCC-2", "CCC-3", "FFF-1", "AAA-1", "BBB-40"})
        self.assertIn("maximum 4 le 2026-07-29", sortie)                  # CCC-1 et les trois JJJ

    def test_aucune_ecriture_ni_titre(self):
        avant = {p for p in self.atelier.ws.rglob("*") if p.is_file()}
        sortie = self.lancer()
        self.assertNotIn("TITRE SECRET", sortie)
        self.assertEqual({p for p in self.atelier.ws.rglob("*") if p.is_file()}, avant)


class TestDebuts(unittest.TestCase):
    """--debuts : passages de Ready for Verification à Verification - Ongoing, par projet."""
    VERIF = "Verification - Ongoing"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.a = a = Atelier(Path(self._tmp.name))
        a.ticket("RRR-1", "2026-03-01", "Done", [("2026-03-05", "Open", IMPL), ("2026-04-08", IMPL, "Done")],
                 resolu="2026-04-08", motif="Done")           # fixe le début de la période (voir construire)
        # PPP : 25 passages entrés en « Ready for Verification » le 05-01 : 10 le 05-11, 7 le 05-08, 8 jours à 1
        jours = [11] * 10 + [8] * 7 + [2, 3, 4, 5, 6, 7, 9, 12]
        for i, j in enumerate(jours, 1):
            self.passage("PPP", i, j)
        # QQQ : 30 passages sur 30 jours distincts, attentes de 1 à 30 jours
        for i in range(1, 31):
            self.passage("QQQ", i, i + 1)
        # SSS : 19 passages, sous le seuil
        for i in range(1, 20):
            self.passage("SSS", i, 3)
        self.export = str(a.ecrire())

    def passage(self, projet, i, jour):
        """Entre en REVUE le 2026-05-01, passe en vérification le jour `jour` de mai, sort vingt jours plus tard."""
        passe = D("2026-05-01") + dt.timedelta(days=jour - 1)
        self.a.ticket(f"{projet}-{i}", "2026-04-20", IMPL, [
            ("2026-05-01", "Open", REVUE), (passe.isoformat(), REVUE, self.VERIF),
            ((passe + dt.timedelta(days=20)).isoformat(), self.VERIF, IMPL)])

    def lancer(self, *args):
        return self.a.lancer(SCRIPT, self.export, "--today", AUJOURDHUI, "--starts", *args)

    def test_projets_tries_et_chiffres(self):
        sortie = self.lancer()
        lignes = lignes_de(sortie, "## Passages de")
        # colonnes : projet, passages, jours distincts, jours retenus, part observée, part attendue (jours actifs égaux),
        # 95e centile, plus concentré ?, jours attendus, 5e centile des jours, ratio, moins de jours actifs ?, P50 de l'attente
        def hasard(projet, n, jours):
            moyenne, centile = es.reference_hasard(n, JOURS, 42, projet)
            attendus, centile_5 = es.reference_jours_actifs(n, JOURS, 42, projet)
            return [f"{100 * moyenne:.1f} %", f"{100 * centile:.1f} %"], [f"{attendus:.1f}", f"{centile_5:.1f}", f"{jours / attendus:.2f}"]
        qa, qb = hasard("QQQ", 30, 30)
        pa, pb = hasard("PPP", 25, 10)
        self.assertEqual(lignes, [["QQQ", "30", "30", "6", "20.0 %", *qa, "non", *qb, "non", "16"],
                                  ["PPP", "25", "10", "2", "68.0 %", *pa, "oui", *pb, "oui", "7"]])
        self.assertIn(f"sur les {JOURS} jours ouvrés", sortie)
        self.assertEqual(JOURS, 124)
        self.assertIn("74 passages", sortie)                    # 25 + 30 + 19
        self.assertIn("1 projet(s) sous le seuil (19 passages)", sortie)

    def test_seuil_reglable(self):
        lignes = lignes_de(self.lancer("--min-passes", "19"), "## Passages de")
        self.assertEqual([r[0] for r in lignes], ["QQQ", "PPP", "SSS"])
        self.assertEqual(lignes[2][1:5], ["19", "1", "1", "100.0 %"])
        self.assertEqual(lignes[2][5], f"{100 * es.reference_hasard(19, JOURS, 42, 'SSS')[0]:.1f} %")

    def test_passages_directs_seulement_et_allers_retours(self):
        a = self.a
        # deux visites, un passage chacun : 2 passages. Un passage par un autre état n'en est pas un.
        a.ticket("UUU-1", "2026-04-20", IMPL, [
            ("2026-05-01", "Open", REVUE), ("2026-05-05", REVUE, self.VERIF), ("2026-05-10", self.VERIF, IMPL),
            ("2026-05-20", IMPL, REVUE), ("2026-05-23", REVUE, self.VERIF), ("2026-05-30", self.VERIF, IMPL)])
        a.ticket("UUU-2", "2026-04-20", IMPL, [
            ("2026-05-01", "Open", REVUE), ("2026-05-05", REVUE, "Verification"),
            ("2026-05-06", "Verification", self.VERIF), ("2026-05-12", self.VERIF, IMPL)])
        a.ecrire()
        ligne = {r[0]: r for r in lignes_de(self.lancer("--min-passes", "1"), "## Passages de")}["UUU"]
        self.assertEqual(ligne[1:5] + ligne[12:], ["2", "2", "1", "50.0 %", "4"])  # attentes 4 et 3 j, P50 3,5 arrondi à 4 ; un jour retenu sur deux

    def test_aucune_cle_dans_la_section_et_sortie_inchangee_sans_option(self):
        sortie = self.lancer()
        section = sortie.split("## Passages de", 1)[1]
        self.assertNotRegex(section, r"[A-Z]{3}-\d+")
        sans = self.a.lancer(SCRIPT, self.export, "--today", AUJOURDHUI)
        self.assertNotIn("Passages de", sans)

    def test_colonnes_de_reference_et_indicateur_dans_la_sortie(self):
        sortie = self.lancer()
        en_tete = next(l for l in sortie.splitlines() if l.startswith("| Projet |"))
        colonnes = [c.strip() for c in en_tete.strip("|").split("|")]
        self.assertEqual(colonnes[4:12], ["Part des passages sur ces jours", "Part attendue au hasard (à jours actifs égaux)",
                                          "95e centile des tirages (à jours actifs égaux)",
                                          "Plus concentré que le hasard à jours actifs égaux", "Jours distincts attendus au hasard",
                                          "5e centile des jours distincts", "Ratio jours observés / attendus",
                                          "Moins de jours actifs que le hasard"])
        lignes = {r[0]: r for r in lignes_de(sortie, "## Passages de")}
        centile = lambda projet, n: f"{100 * es.reference_hasard(n, JOURS, 42, projet)[1]:.1f} %"
        self.assertEqual((lignes["QQQ"][6], lignes["QQQ"][7]), (centile("QQQ", 30), "non"))     # 20,0 % : dans l'intervalle
        self.assertEqual((lignes["PPP"][6], lignes["PPP"][7]), (centile("PPP", 25), "oui"))     # 68,0 % : bien au-dessus
        for projet, passages, jours in (("QQQ", 30, 30), ("PPP", 25, 10)):
            attendus, centile_5 = es.reference_jours_actifs(passages, JOURS, 42, projet)
            self.assertEqual(lignes[projet][8:11], [f"{attendus:.1f}", f"{centile_5:.1f}", f"{jours / attendus:.2f}"])
        self.assertEqual(lignes["QQQ"][11], "non")                                              # 30 jours sur 30 : autant que le hasard
        self.assertEqual(lignes["PPP"][11], "oui")                                              # 10 jours actifs pour 25 passages
        self.assertIn("95e centile de ces parts", sortie)
        self.assertIn("ne voit pas un projet qui n'a que peu de jours actifs", sortie)
        self.assertIn("moins de jours actifs que le hasard n'en produit", sortie)

    def test_sortie_identique_d_un_lancement_a_l_autre(self):
        """Graine fixe : deux lancements sur les mêmes données donnent exactement la même section, colonnes de référence comprises."""
        self.assertEqual(self.lancer(), self.lancer())
        self.assertNotEqual(self.lancer(), self.lancer("--seed", "7"))

    def test_aucun_projet_au_seuil(self):
        sortie = self.lancer("--min-passes", "500")
        self.assertIn("Aucun projet n'atteint le seuil.", sortie)


class TestPartAttendue(unittest.TestCase):
    """Part attendue au hasard : fonctions du script, appelées directement."""

    def test_jours_ouvres(self):
        self.assertEqual(len(es.jours_ouvres(D("2026-04-06"), D("2026-10-04"))), 124)     # 26 semaines complètes (130) moins 6 fériés en semaine
        self.assertEqual([j.isoformat() for j in es.jours_ouvres(D("2026-10-02"), D("2026-10-06"))],
                         ["2026-10-02", "2026-10-05", "2026-10-06"])                      # le week-end saute

    def test_jours_retenus_arrondis_au_dessus_sans_derive_flottante(self):
        self.assertEqual([es.jours_retenus(d) for d in (1, 4, 5, 6, 10, 15, 20, 25)], [1, 1, 1, 2, 2, 3, 4, 5])

    def test_cas_limites(self):
        # un seul jour (tout y tombe) : couvert par TestIndicateurDeReference
        grand = es.reference_hasard(20, 100_000, 42, "X")[0]                     # jamais deux le même jour : 4 jours sur 20
        self.assertAlmostEqual(grand, 0.2, delta=0.01)
        self.assertGreater(grand, 0.2 - 1e-9)

    def test_plus_concentre_avec_peu_de_jours(self):
        self.assertGreater(es.reference_hasard(30, 20, 42, "X")[0], es.reference_hasard(30, 130, 42, "X")[0])

    def test_reproductible_et_independant_des_autres_projets(self):
        a = es.reference_hasard(25, 130, 42, "PPP")
        es.reference_hasard(30, 130, 42, "QQQ")
        self.assertEqual(a, es.reference_hasard(25, 130, 42, "PPP"))
        self.assertNotEqual(a, es.reference_hasard(25, 130, 42, "QQQ"))           # le projet joue (la graine : plus bas)


class TestIndicateurDeReference(unittest.TestCase):
    """Part observée contre le 95e centile des tirages au hasard : données synthétiques, fonctions appelées directement."""

    DEBUT, FIN = D("2026-04-06"), D("2026-10-04")                    # 124 jours ouvrés (fériés retirés)
    OUVRES = es.jours_ouvres(DEBUT, FIN)

    def sortis(self, dates, projet="PPP"):
        return [{"projet": projet, "passages": [(d, 3.0) for d in dates]}]

    def ligne(self, dates, projet="PPP", graine=42):
        t = es.Messages(es.CATALOGS, "fr")
        lignes = es.affichage_debuts(self.sortis(dates, projet), 1, self.DEBUT, self.FIN, graine, t)
        return [c.strip() for c in next(l for l in lignes if l.startswith(f"| {projet} |")).strip("|").split("|")]

    def verdict(self, dates, graine=42):
        lignes, _ = es.debuts_par_projet(self.sortis(dates), 1)
        _, centile = es.reference_hasard(len(dates), len(self.OUVRES), graine, "PPP")
        return lignes[0]["part"], centile, es.au_dessus_du_hasard(lignes[0]["part"], centile)

    def test_repartition_uniforme_l_observe_reste_dans_l_intervalle(self):
        dates = self.OUVRES[2:2 + 5 * 25:5]                            # 25 passages, un jour ouvré sur cinq
        self.assertEqual(len(dates), 25)
        part, centile, au_dessus = self.verdict(dates)
        self.assertAlmostEqual(part, 5 / 25)                           # 25 jours distincts, 5 retenus, un passage par jour
        self.assertLessEqual(part, centile)
        self.assertFalse(au_dessus)
        self.assertEqual(self.ligne(dates)[7], "non")

    def test_demarrages_tous_le_meme_jour_l_observe_est_au_dessus(self):
        dates = [self.OUVRES[60]] * 30
        part, centile, au_dessus = self.verdict(dates)
        self.assertEqual(part, 1.0)
        self.assertLess(centile, 1.0)                                  # 30 passages au hasard sur 130 jours ne tiennent pas en un jour
        self.assertTrue(au_dessus)
        self.assertEqual(self.ligne(dates)[7], "oui")

    def test_jours_actifs_tous_les_passages_le_meme_jour_ratio_tres_bas_et_oui(self):
        dates = [self.OUVRES[60]] * 30
        ligne = self.ligne(dates)
        attendus, centile_5 = es.reference_jours_actifs(30, len(self.OUVRES), 42, "PPP")
        self.assertGreater(attendus, 20)                               # 30 passages au hasard touchent 27 jours environ
        self.assertEqual(ligne[2], "1")
        self.assertEqual(float(ligne[8]), round(attendus, 1))
        self.assertEqual(float(ligne[9]), round(centile_5, 1))
        self.assertLess(float(ligne[10]), 0.1)                         # 1 jour observé contre ~27 attendus
        self.assertEqual(ligne[11], "oui")                             # moins de jours actifs que le hasard
        self.assertEqual(ligne[7], "oui")                              # et, à jours actifs égaux, plus concentré aussi

    def test_jours_actifs_un_passage_par_jour_ratio_proche_de_1_et_non(self):
        dates = self.OUVRES[2:2 + 5 * 25:5]                            # 25 passages sur 25 jours distincts
        ligne = self.ligne(dates)
        self.assertEqual(ligne[2], "25")
        self.assertGreater(float(ligne[10]), 0.9)
        self.assertLess(float(ligne[10]), 1.3)                         # proche de 1 : le hasard fait presque autant de jours distincts
        self.assertEqual(ligne[11], "non")
        # un passage sur chaque jour ouvré de la période : plus de jours actifs que le hasard (qui en laisse de vides), jamais « oui »
        tous = self.ligne(list(self.OUVRES))
        self.assertEqual(tous[2], str(len(self.OUVRES)))
        self.assertGreaterEqual(float(tous[10]), 1.0)
        self.assertEqual(tous[11], "non")

    def test_jours_actifs_seuil_strict_et_donnees_du_calcul(self):
        self.assertFalse(es.moins_de_jours_actifs(10, 10.0))
        self.assertFalse(es.moins_de_jours_actifs(10, 10.0 - 1e-15))
        self.assertTrue(es.moins_de_jours_actifs(9, 10.0))
        moyenne, centile_5 = es.reference_jours_actifs(30, 124, 42, "PPP")
        self.assertLessEqual(centile_5, moyenne)
        self.assertLessEqual(moyenne, 30)                              # jamais plus de jours distincts que de passages
        self.assertEqual(es.reference_jours_actifs(20, 1, 42, "PPP"), (1.0, 1.0))
        self.assertEqual(es.reference_jours_actifs(30, 124, 42, "PPP"), es.reference_jours_actifs(30, 124, 42, "PPP"))
        self.assertNotEqual(es.reference_jours_actifs(30, 124, 42, "PPP"), es.reference_jours_actifs(30, 124, 43, "PPP"))

    def test_les_deux_mesures_lisent_les_memes_tirages(self):
        """Mêmes tirages (même graine) : la concentration est calculée sur les jours distincts de ceux qui servent aux jours actifs."""
        comptes = es.tirages_au_hasard(30, 124, 42, "PPP")
        self.assertEqual(len(comptes), es.TIRAGES)
        self.assertTrue(all(c.sum() == 30 and len(c) == 124 for c in comptes))
        distincts = [int((c > 0).sum()) for c in comptes]
        self.assertAlmostEqual(es.reference_jours_actifs(30, 124, 42, "PPP")[0], sum(distincts) / len(distincts))

    def test_aucun_jour_ouvre_pas_de_reference(self):
        with self.assertRaises(ValueError):
            es.tirages_au_hasard(10, 0, 42, "PPP")
        t = es.Messages(es.CATALOGS, "fr")
        samedi, dimanche = D("2026-10-03"), D("2026-10-04")
        lignes = es.affichage_debuts(self.sortis([samedi] * 25), 1, samedi, dimanche, 42, t)
        self.assertIn("| PPP | 25 | 1 | 1 | 100.0 % | — | — | — | — | — | — | — | 3 |", lignes)

    def test_jours_feries_francais_retires_de_la_periode_et_du_tirage(self):
        # 2026 : Pâques le 5 avril, donc lundi de Pâques le 6, Ascension le 14 mai, lundi de Pentecôte le 25
        feries = es.jours_feries_france(2026)
        self.assertEqual(feries, {D("2026-01-01"), D("2026-04-06"), D("2026-05-01"), D("2026-05-08"), D("2026-05-14"),
                                  D("2026-05-25"), D("2026-07-14"), D("2026-08-15"), D("2026-11-01"), D("2026-11-11"),
                                  D("2026-12-25")})
        self.assertEqual(es.paques(2025), D("2025-04-20"))
        self.assertEqual(es.paques(2024), D("2024-03-31"))
        self.assertIn(D("2025-05-29"), es.jours_feries_france(2025))               # Ascension 2025
        self.assertIn(D("2025-06-09"), es.jours_feries_france(2025))               # lundi de Pentecôte 2025
        self.assertNotIn(D("2026-04-03"), feries)                                 # Vendredi saint : Alsace-Moselle seulement
        self.assertNotIn(D("2026-12-26"), feries)
        fenetre = es.jours_ouvres(D("2026-04-30"), D("2026-05-12"))
        self.assertEqual([d.isoformat() for d in fenetre],
                         ["2026-04-30", "2026-05-04", "2026-05-05", "2026-05-06", "2026-05-07", "2026-05-11", "2026-05-12"])
        self.assertEqual(len(self.OUVRES), 130 - 6)                               # 6 fériés tombent en semaine sur la période
        # une période à cheval sur deux années
        self.assertNotIn(D("2026-01-01"), es.jours_ouvres(D("2025-12-29"), D("2026-01-02")))
        self.assertNotIn(D("2025-12-25"), es.jours_ouvres(D("2025-12-22"), D("2025-12-31")))

    def test_le_tirage_et_la_note_comptent_les_jours_sans_feries_et_les_passages_feries_sont_hors_modele(self):
        t = es.Messages(es.CATALOGS, "fr")
        ferie = D("2026-05-01")                                        # vendredi férié
        dates = [ferie] * 2 + self.OUVRES[2:2 + 5 * 23:5]
        lignes = es.affichage_debuts(self.sortis(dates), 1, self.DEBUT, self.FIN, 42, t)
        note = next(l for l in lignes if l.startswith("Les deux mesures"))
        self.assertIn(f"sur les {len(self.OUVRES)} jours ouvrés", note)
        self.assertIn("jours fériés français retirés", note)
        self.assertIn("2 passage(s) tombent un week-end, un jour férié ou hors période", note)

    def test_une_part_egale_au_95e_centile_n_est_pas_au_dessus(self):
        self.assertFalse(es.au_dessus_du_hasard(0.4, 0.4))
        self.assertFalse(es.au_dessus_du_hasard(0.4 + 1e-15, 0.4))      # bruit d'arrondi
        self.assertTrue(es.au_dessus_du_hasard(0.41, 0.4))

    def test_le_95e_centile_est_au_moins_la_moyenne(self):
        moyenne, centile = es.reference_hasard(30, 130, 42, "PPP")
        self.assertGreaterEqual(centile, moyenne)

    def test_les_tirages_ont_le_meme_nombre_de_passages_et_de_jours_que_le_reel(self):
        """Peu de passages sur peu de jours : le hasard concentre davantage ; le 95e centile suit le réel, pas une valeur fixe."""
        _, large = es.reference_hasard(30, 130, 42, "PPP")
        _, etroit = es.reference_hasard(30, 20, 42, "PPP")
        _, peu = es.reference_hasard(8, 130, 42, "PPP")
        self.assertGreater(etroit, large)
        self.assertNotEqual(peu, large)
        # un seul jour disponible : tout y tombe, la part vaut 1 à tous les centiles
        self.assertEqual(es.reference_hasard(20, 1, 42, "PPP"), (1.0, 1.0))

    def test_resultat_identique_d_un_lancement_a_l_autre_graine_fixe(self):
        dates = self.OUVRES[2::5]
        self.assertEqual(self.ligne(dates), self.ligne(dates))
        self.assertEqual(es.reference_hasard(26, 130, 42, "PPP"), es.reference_hasard(26, 130, 42, "PPP"))
        self.assertNotEqual(es.reference_hasard(26, 130, 42, "PPP"), es.reference_hasard(26, 130, 43, "PPP"))   # la graine joue
        self.assertNotEqual(es.reference_hasard(26, 130, 42, "PPP"), es.reference_hasard(26, 130, 42, "QQQ"))   # le projet aussi

    def test_la_colonne_ne_depend_pas_de_la_presence_des_autres_projets(self):
        seul = self.ligne(self.OUVRES[2::5])
        t = es.Messages(es.CATALOGS, "fr")
        deux = es.affichage_debuts(self.sortis(self.OUVRES[2::5]) + self.sortis([self.OUVRES[10]] * 40, "QQQ"), 1, self.DEBUT, self.FIN, 42, t)
        avec = [c.strip() for c in next(l for l in deux if l.startswith("| PPP |")).strip("|").split("|")]
        self.assertEqual(seul[5:8], avec[5:8])


if __name__ == "__main__":
    unittest.main()
