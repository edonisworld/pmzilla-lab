"""Scénario de test de la langue de flux_jira.py : données inventées, aucune donnée réelle, aucun appel à Jira.

`jouer(language)` lance le script sur un faux espace de travail temporaire (exports synthétiques, historique inventé,
rapports d'évolution fabriqués) et rend un dictionnaire {étape: sortie}. Sans langue (None), aucune option `--language`
n'est passée : c'est la sortie par défaut, en français. Les chemins du dossier temporaire sont remplacés par <WS>.
Les mêmes étapes servent à l'instantané anglais (reference_en.md) et à la comparaison avant/après du français.
"""
import csv
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import test_flux_jira as fx  # noqa: E402

EQUIPES = [f"Team {c}" for c in "ABCDEFGHIJKL"]          # douze équipes : la note sur les équipes s'affiche
YAML = """portfolio_types: [Epic, RN Task]
excluded_projects: [BUG]
waiting_states: [Ready for, Waiting]
jql_export: "project in (ABC, DEF) AND resolved >= -20w"
"""


def normaliser(texte: str, ws: Path) -> str:
    """Chemins du dossier temporaire remplacés par <WS>, messages d'installation de uv retirés."""
    for chemin in {str(ws), str(ws.resolve())}:
        texte = texte.replace(chemin, "<WS>")
    return re.sub(r"^(Installed|Uninstalled|Prepared|Resolved|Audited) \d+ packages? in .*\n", "", texte, flags=re.M)


def lire_fichiers(ws: Path) -> dict[str, str]:
    sortie = {}
    for dossier in ("rapports", "tableaux"):
        for chemin in sorted((ws / "Flux-Lab" / dossier).glob("*")) if (ws / "Flux-Lab" / dossier).exists() else []:
            sortie[f"{dossier}/{chemin.name}"] = chemin.read_text(encoding="utf-8")
    return sortie


class Jeu:
    def __init__(self, ws: Path, language: str | None):
        self.ws = ws
        self.language = language
        self.sorties: dict[str, str] = {}
        self.vus: dict[str, str] = {}

    def lancer(self, nom: str, *args: str, langue: bool = True) -> subprocess.CompletedProcess:
        extra = ["--language", self.language] if (langue and self.language) else []
        env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(self.ws), "PYTHONHASHSEED": "0"}
        r = subprocess.run(["uv", "run", str(fx.SCRIPT), *args, *extra], env=env, capture_output=True, text=True)
        fichiers = lire_fichiers(self.ws)
        nouveaux = {k: v for k, v in fichiers.items() if self.vus.get(k) != v}
        self.vus.update(fichiers)
        texte = (f"$ {' '.join(args)}\nexit code: {r.returncode}\n--- stdout ---\n{r.stdout}"
                 f"--- stderr ---\n{r.stderr}")
        for chemin, contenu in nouveaux.items():
            texte += f"--- file {chemin} ---\n{contenu}\n"
        self.sorties[nom] = normaliser(texte, self.ws)
        return r


def historique(lignes: list[dict], rng: random.Random) -> dict:
    """Cache d'historique inventé : parcours Definition, Ready, Implementation, puis fermeture ; quelques trous."""
    cache = {}
    for i, t in enumerate(lignes):
        if t["cle"].startswith("BUG-") or i % 9 == 4:           # absents du cache : couverture imparfaite
            continue
        d = t["cree"]
        etapes = [(d, "Open", "Definition - Ongoing"), (d, "Definition - Ongoing", "Ready for Implementation"),
                  (d, "Ready for Implementation", "Implementation - Ongoing")]
        transitions = []
        for k, (jour, de, vers) in enumerate(etapes):
            date = jour + __import__("datetime").timedelta(days=2 + 3 * k + rng.randint(0, 2))
            if t["resolu"] and date > t["resolu"]:
                break
            transitions.append([f"{date.isoformat()}T10:00:00.000+0200", de, vers])
        if t["resolu"]:
            dernier = transitions[-1][2] if transitions else "Open"
            transitions.append([f"{t['resolu'].isoformat()}T10:00:00.000+0200", dernier, "Closed"])
        if i % 40 == 7:
            transitions.append(["pas une date", "Closed", "Reopened"])
        cache[t["cle"]] = {"termine": bool(t["resolu"]), "transitions": transitions}
    return cache


def csv_brut(chemin: Path, entete: list[str], lignes: list[list[str]]) -> None:
    with chemin.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(entete)
        w.writerows(lignes)


def preparer(ws: Path) -> dict:
    rng = random.Random(21)
    lot1 = fx.construire(rng, "ABC", fx.WORKFLOW_1, 90, EQUIPES, ["Story", "Task", "Epic"])
    lot2 = fx.construire(rng, "DEF", fx.WORKFLOW_2, 90, EQUIPES, ["Story", "RN Task", "Bug"])
    lot2 += fx.construire(rng, "BUG", fx.WORKFLOW_2, 20, EQUIPES, ["Bug"])
    lot2 += [dict(t) for t in lot1[:5]]                              # doublons entre les deux exports
    for t in lot1[10:16]:
        t["equipe"] = "Team A;Team B"                                # tickets à plusieurs équipes
    for t in lot1[20:24]:
        t["equipe"] = ""                                             # sans équipe
    for t in lot2[30:34]:
        t["motif"] = "Won't Do" if t["resolu"] else ""               # clos sans livraison
    for t in [t for t in lot1 + lot2 if not t["resolu"]][::5]:       # très anciens, sans mouvement : dormants
        t["cree"] = __import__("datetime").date(2024, 3, 1) + __import__("datetime").timedelta(days=len(t["cle"]))
        t["debut"] = None
    fx.ecrire_yaml(ws, YAML)
    fx.ecrire_csv(ws / "a.csv", lot1)
    fx.ecrire_csv(ws / "b.csv", lot2)
    csv_brut(ws / "dormants.csv", ["Issue key"], [["ABC-1"]])          # ancienne option --dormants : refusée
    dossier = ws / "Flux-Lab" / "historique"
    dossier.mkdir(parents=True)
    (dossier / "transitions.json").write_text(json.dumps(historique(lot1 + lot2, rng)), encoding="utf-8")
    return {"lot1": lot1, "lot2": lot2}


def rapports_fabriques(jeu: Jeu) -> None:
    """Rapports JSON retouchés pour exercer chaque signal, chaque note et les sections sautées de la comparaison."""
    rap = jeu.ws / "Flux-Lab" / "rapports"
    avant = json.loads((rap / "flux-s-2026-09-20.json").read_text(encoding="utf-8"))
    apres = json.loads((rap / "flux-s-2026-10-04.json").read_text(encoding="utf-8"))

    def ecrire(nom: str, date: str, r: dict) -> None:
        (rap / f"flux-{nom}-{date}.json").write_text(json.dumps({**r, "nom": nom, "date": date}), encoding="utf-8")

    # evo : tout bouge
    b, a = json.loads(json.dumps(avant)), json.loads(json.dumps(apres))
    b["types"] = "Story"
    b["perimetre"] = {"projets": ["ABC"], "tickets_lus": 1, "tickets_retenus": 1}
    a["perimetre"] = {"projets": "tous", "tickets_lus": 1, "tickets_retenus": 1}
    b["semaines"] = 20
    b["colonnes"] = {k: v for k, v in b["colonnes"].items() if k != "debut"}
    b["wip_par_etat"] = {**b["wip_par_etat"], "Old State": 3}
    a["wip_par_etat"] = {**a["wip_par_etat"], "New State": 2}
    b["debit_par_semaine"][-4:] = [0, 0, 0, 0]
    b["debit"]["moyenne"], b["debit"]["semaines_a_zero"] = 1.0, 9
    b["lead_time_jours"] = {k: v * 2 for k, v in b["lead_time_jours"].items()}
    b["wip"], b["little_jours"] = a["wip"] * 3, a["little_jours"] * 3
    b["age_seuils"] = {k: max(0, v - 5) for k, v in b["age_seuils"].items()}
    b["age_wip_jours"]["au_dela_du_lead_time_p85"] = 0
    a["age_wip_jours"]["au_dela_du_lead_time_p85"] = 4
    for etat, d in a["age_a_faire_par_etat"].items():
        b["age_a_faire_par_etat"][etat] = {**d, "plus_de_90_j": 0, "elements": d["elements"] * 3}
    equipes = sorted(a["par_equipe"])
    b["par_equipe"] = {k: json.loads(json.dumps(v)) for k, v in a["par_equipe"].items() if k != equipes[-1]}
    a["par_equipe"]["Team Extra"] = json.loads(json.dumps(a["par_equipe"][equipes[0]]))
    for k, v in b["par_equipe"].items():
        v["debit_par_semaine"] = [1] * len(v["debit_par_semaine"])
        v["wip_plus_de_90_j"] = 0
    a["par_equipe"][equipes[0]]["debit_par_semaine"] = [0] * 18 + [9, 0, 0, 0, 9, 0, 0, 0]
    a["par_equipe"][equipes[1]]["debit_par_semaine"] = [3] * 24 + [0, 0]
    b["par_equipe"][equipes[1]]["debit_par_semaine"] = [3] * 26
    a["par_equipe"][equipes[2]]["wip_plus_de_90_j"] = 7
    a["par_equipe"][equipes[3]]["debit_par_semaine"] = [3] * 26
    b["par_equipe"][equipes[3]]["debit_par_semaine"] = [0] * 18 + [9, 0, 0, 0, 9, 0, 0, 0]
    b["par_equipe"][equipes[4]] = {"termines": 1}
    b["prevision_quand"] = {"elements": 5, "semaines": {"50": 2, "85": 3, "95": 4}}
    a["prevision_quand"] = {"elements": a["prevision_quand"]["elements"], "semaines": a["prevision_quand"]["semaines"]}
    ecrire("evo", "2026-09-20", b)
    ecrire("evo", "2026-10-04", a)
    # evo2 : pas de semaine nouvelle, mêmes objectifs, même date cible
    b2, a2 = json.loads(json.dumps(avant)), json.loads(json.dumps(avant))
    a2["prevision_combien"] = {"date": "2026-11-15", "elements": {"85": 10, "50": 12, "95": 8}}
    b2["prevision_combien"] = {"date": "2026-11-15", "elements": {"85": 14, "50": 16, "95": 12}}
    b2["prevision_quand"] = {"elements": 5, "semaines": {"50": 2, "85": 3, "95": 4}}
    a2["prevision_quand"] = {"elements": 5, "semaines": {"50": 2, "85": 4, "95": 5}}
    ecrire("evo2", "2026-09-20", b2)
    ecrire("evo2", "2026-10-04", a2)
    # evo3 : ancien format, des clés manquent
    b3, a3 = json.loads(json.dumps(avant)), json.loads(json.dumps(apres))
    for cle in ("types", "semaines", "wip_par_etat", "periode", "lead_time_par_type", "wip", "age_seuils", "prevision_combien",
                "age_a_faire_par_etat"):
        b3.pop(cle, None)
    a3.pop("debit", None)
    for v in b3["par_equipe"].values():
        v.pop("lead_time", None)
    ecrire("evo3", "2026-09-20", b3)
    ecrire("evo3", "2026-10-04", a3)
    # evo4 : un rapport sans date, puis dates à l'envers (fichiers nommés par leur date)
    sans_date = json.loads(json.dumps(avant))
    (rap / "flux-evo4-2026-09-20.json").write_text(json.dumps({k: v for k, v in sans_date.items() if k != "date"}), encoding="utf-8")
    ecrire("evo4", "2026-10-04", json.loads(json.dumps(apres)))
    # evo5 : un seul rapport
    ecrire("evo5", "2026-10-04", json.loads(json.dumps(apres)))
    # evo6 : rapports à date interne incohérente avec le nom
    ecrire("evo6", "2026-09-20", json.loads(json.dumps(apres)))
    (rap / "flux-evo6-2026-09-20.json").write_text(json.dumps({**apres, "date": "2026-10-04"}), encoding="utf-8")
    ecrire("evo6", "2026-10-04", json.loads(json.dumps(avant)))


def jouer(language: str | None) -> dict[str, str]:
    """Toutes les étapes du scénario, dans l'ordre ; rend {nom d'étape: sortie}."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        jeu = Jeu(ws, language)
        # premier lancement, sans flux.yaml : le script le crée
        empty = Path(tmp) / "empty"
        empty.mkdir()
        csv_brut(empty / "x.csv", ["Issue Type", "Status", "Created", "Resolved"],
                 [["Story", "Done", "01/Aug/2026 09:00", "10/Aug/2026 09:00"], ["Story", "Open", "pas une date", ""]])
        env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(empty), "PYTHONHASHSEED": "0"}
        extra = ["--language", language] if language else []
        r = subprocess.run(["uv", "run", str(fx.SCRIPT), "statuses", str(empty / "x.csv"), *extra], env=env, capture_output=True, text=True)
        jeu.sorties["statuses-first-run"] = normaliser(r.stdout + "--- stderr ---\n" + r.stderr, empty)
        preparer(ws)
        a, b = str(ws / "a.csv"), str(ws / "b.csv")
        jeu.lancer("statuses", "statuses", a, b)
        jeu.lancer("statuses-one-export", "statuses", a)
        csv_brut(ws / "no-key.csv", ["Issue Type", "Status", "Created", "Resolved"],
                 [["Story", "Done", "01/Aug/2026 09:00", "10/Aug/2026 09:00"], ["Story", "Open", "05/Aug/2026 09:00", ""]])
        jeu.lancer("statuses-no-key", "statuses", str(ws / "no-key.csv"), str(ws / "no-key.csv"))
        csv_brut(ws / "no-resolved.csv", ["Issue Type", "Status", "Created"], [["Story", "Open", "05/Aug/2026 09:00"]])
        jeu.lancer("statuses-no-resolved", "statuses", str(ws / "no-resolved.csv"))
        jeu.lancer("compute-older", "compute", a, b, "--name", "s", "--today", "2026-09-20", "--no-comparison",
                   "--scope", "ABC,DEF,ZZZ", "--history", "--dormant-from-history", "--points", "--target-date", "2026-11-15",
                   "--batch-closure-resolutions", "Done,Closed")
        jeu.lancer("compute-newer-with-comparison", "compute", a, b, "--name", "s", "--today", "2026-10-04",
                   "--scope", "ABC,DEF,ZZZ", "--history", "--dormant-from-history", "--points", "--target", "40",
                   "--target-date", "2026-11-15", "--batch-closure-resolutions", "Done,Closed")
        jeu.lancer("compute-dormants-history", "compute", a, b, "--name", "d", "--today", "2026-10-04", "--no-comparison",
                   "--dormant-from-history", "--teams-only", "--types", "Story,Bug,Task",
                   "--batch-closure-resolutions", "tous", "--scope", "tous")
        jeu.lancer("compute-simple", "compute", a, "--today", "2026-10-04", "--no-comparison", "--weeks", "8")
        jeu.lancer("compute-simple-no-earlier-report", "compute", a, "--today", "2026-10-04")
        jeu.lancer("compute-simple-history-only", "compute", a, "--name", "h", "--today", "2026-10-04", "--no-comparison",
                   "--history")
        jeu.lancer("compare", "compare", "--name", "s")
        jeu.lancer("compare-dates", "compare", "--name", "s", "--before", "2026-09-20", "--after", "2026-10-04")
        rapports_fabriques(jeu)
        for nom in ("evo", "evo2", "evo3"):
            jeu.lancer(f"compare-{nom}", "compare", "--name", nom)
        jeu.lancer("compare-evo4-no-date", "compare", "--name", "evo4")
        jeu.lancer("compare-evo5-single", "compare", "--name", "evo5")
        jeu.lancer("compare-evo-missing-after", "compare", "--name", "evo", "--after", "2030-01-01")
        jeu.lancer("compare-evo-missing-before", "compare", "--name", "evo", "--before", "2020-01-01", "--after", "2026-10-04")
        jeu.lancer("compare-evo-too-old", "compare", "--name", "evo", "--after", "2026-09-20")
        jeu.lancer("compare-evo6-reversed-dates", "compare", "--name", "evo6")
        jeu.lancer("compare-no-name", "compare")
        # erreurs de compute
        base = ["compute", a, "--today", "2026-10-04", "--no-comparison"]
        jeu.lancer("err-scope-empty", *base, "--scope", ",")
        jeu.lancer("err-scope-no-key", "compute", str(ws / "no-key.csv"), "--today", "2026-10-04", "--no-comparison", "--scope", "ABC")
        jeu.lancer("err-scope-no-ticket", *base, "--scope", "QQQ")
        jeu.lancer("err-no-resolved", "compute", str(ws / "no-resolved.csv"), "--today", "2026-10-04")
        jeu.lancer("err-dormants-removed", *base, "--dormants", str(ws / "dormants.csv"))
        jeu.lancer("err-dormant-history-no-key", "compute", str(ws / "no-key.csv"), "--today", "2026-10-04",
                   "--no-comparison", "--dormant-from-history")
        jeu.lancer("err-history-no-key", "compute", str(ws / "no-key.csv"), "--today", "2026-10-04",
                   "--no-comparison", "--history")
        jeu.lancer("err-history-cache-missing", *base, "--history", str(ws / "absent.json"))
        (ws / "broken.json").write_text("{pas du json", encoding="utf-8")
        jeu.lancer("err-history-cache-unreadable", *base, "--history", str(ws / "broken.json"))
        jeu.lancer("err-teams-only-no-team", "compute", str(ws / "no-key.csv"), "--today", "2026-10-04",
                   "--no-comparison", "--teams-only")
        jeu.lancer("err-resolutions-empty", *base, "--batch-closure-resolutions", " , ")
        csv_brut(ws / "no-status.csv", ["Issue Type", "Created"], [["Story", "05/Aug/2026 09:00"]])
        jeu.lancer("err-columns-missing", "statuses", str(ws / "no-status.csv"))
        # réglages invalides
        fx.ecrire_yaml(ws, YAML + "batch_closure_threshold: 1\n")
        jeu.lancer("err-threshold-invalid", *base)
        fx.ecrire_yaml(ws, YAML + "commitment_point: nowhere\n")
        jeu.lancer("err-commitment-point", *base, "--history")
        fx.ecrire_yaml(ws, YAML)
        # config migrate : rien d'abord, puis un ancien flux.yaml
        jeu.lancer("config-nothing-to-migrate", "config", "migrate")
        fx.ecrire_yaml(ws, 'etats_attente: [Ready for]\nprojets_exclus: [DEF]\nseuil_fermetures_groupees: 5\n')
        jeu.lancer("config-dry-run", "config", "migrate", "--dry-run")
        jeu.lancer("config-migrate", "config", "migrate")
        (ws / "Flux-Lab" / "flux.yaml").unlink()
        jeu.lancer("config-file-missing", "config", "migrate")
        return jeu.sorties
