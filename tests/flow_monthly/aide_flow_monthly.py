"""
Aide commune des tests de tools/flow_monthly.py (change monthly-flow-orchestrator, R-48). Aucun effet réel :

  - un espace de travail temporaire (variable FLOW_MONTHLY_ROOT) avec un Flux-Lab/flux.yaml inventé et un tools/ de FAUX outils ;
  - chaque faux outil journalise ses arguments (appels.jsonl), sort avec le code choisi (codes.json) et écrit, comme le vrai, un rapport
    flux-<nom>-<date>.md pour un calcul de flux ;
  - les dossiers que l'orchestrateur n'a pas le droit de lire reçoivent des fichiers sentinelles ;
  - l'orchestrateur RÉEL est appelé dans le processus (main(argv, environ)) avec un environnement choisi par le test, sans la variable
    de session Claude Code (sauf pour le test du refus).

Les noms de série, de requête et de périmètre portent une marque (zz) : un test qui la retrouve dans une sortie ou dans le résumé prouve
que l'orchestrateur écrit une valeur qu'il ne doit pas écrire. Aucune donnée réelle.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
import flow_monthly as fm                # noqa: E402

SERIE_1 = "serieunzz"
SERIE_2 = "seriedeuxzz"
REQUETE_1 = "requetealphazz"
REQUETE_2 = "requetebetazz"
PERIMETRE_1 = "PORTEEUNZZ"
PERIMETRE_2 = "PORTEEDEUXZZ"
MARQUES = (SERIE_1, SERIE_2, REQUETE_1, REQUETE_2, PERIMETRE_1, PERIMETRE_2, "zz", "ZZ")

REGLAGES = f"""jira_site: https://exemple.invalide
jql_exports:
  {REQUETE_1}: project = AAA
  {REQUETE_2}: project = BBB
monthly_run:
  series:
    - name: {SERIE_1}
      scope: {PERIMETRE_1},{PERIMETRE_2}
      dependencies: both
    - name: {SERIE_2}
  dashboard: both
"""

# les outils que l'orchestrateur appelle, et ceux qu'il ne doit jamais appeler (ils existent en faux pour que l'appel se voie)
OUTILS = ("export_jira_api", "history_jira", "flow_import", "flux_jira", "dependencies_jira", "flow_compare", "flow_board", "flow_retention")
OUTILS_EXCLUS = ("segment_sample", "db", "flow_views", "knowledge_import")

FAUX_OUTIL = '''import datetime, json, os, sys
from pathlib import Path
racine = Path(__file__).resolve().parent.parent
outil = Path(__file__).stem
args = sys.argv[1:]
with open(racine / "appels.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps({"outil": outil, "args": args}) + "\\n")
codes = json.loads((racine / "codes.json").read_text(encoding="utf-8")) if (racine / "codes.json").exists() else {}
cle = outil
if outil == "flux_jira" and "--source" in args and args[args.index("--source") + 1] == "db":
    cle = "flux_jira:db"
if outil == "flow_compare":
    cle = "flow_compare:" + ("reports" if "reports" in args else "data")
code = codes.get(cle, codes.get(outil, 0))
print("SORTIE-OUTIL " + " ".join(args))
if outil == "flow_retention":
    imposee = racine / "retention-sortie.txt"
    if imposee.exists():
        print(imposee.read_text(encoding="utf-8"))
    elif "fr" in args:
        print("contrôle de conservation : rien hors règle\\nessai : rien n'est supprimé")
    else:
        print("retention check: nothing out of rule\\ndry run: nothing deleted")
if code or codes.get("stderr_ok"):
    print("ERREUR-OUTIL boum", file=sys.stderr)
if outil == "flux_jira" and "compute" in args and not code:
    nom = args[args.index("--name") + 1]
    jour = args[args.index("--today") + 1] if "--today" in args else datetime.date.today().isoformat()
    dossier = racine / "Flux-Lab" / "rapports"
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / f"flux-{nom}-{jour}.md").write_text("# Rapport\\n", encoding="utf-8")
    (dossier / f"flux-{nom}-{jour}.json").write_text("{}", encoding="utf-8")
sys.exit(code)
'''


def aujourdhui() -> str:
    return dt.date.today().isoformat()


def hier() -> str:
    return (dt.date.today() - dt.timedelta(days=1)).isoformat()


def demain() -> str:
    return (dt.date.today() + dt.timedelta(days=1)).isoformat()


class Resultat:
    def __init__(self, code: int, sortie: str):
        self.code, self.sortie = code, sortie


class Decor(unittest.TestCase):
    """Espace de travail factice ; les tests en héritent."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name).resolve()
        self.flux = self.racine / "Flux-Lab"
        self.rapports = self.flux / "rapports"
        for dossier in ("rapports", "exports", "historique", "tableaux"):
            (self.flux / dossier).mkdir(parents=True)
        for sentinelle in ("exports/sentinelle.csv", "historique/sentinelle.json", "tableaux/sentinelle.html",
                           "equipes-assets.yaml", "noms-sensibles.txt"):
            (self.flux / sentinelle).write_text("sentinelle", encoding="utf-8")
        (self.racine / "tools").mkdir()
        for outil in OUTILS + OUTILS_EXCLUS:
            (self.racine / "tools" / f"{outil}.py").write_text(FAUX_OUTIL, encoding="utf-8")
        self.ecrire_reglages(REGLAGES)
        self.env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE" and not k.startswith("FLOW_MONTHLY_")}
        self.env.update({"FLOW_MONTHLY_ROOT": str(self.racine), "FLOW_MONTHLY_LAUNCHER": sys.executable})

    # --- décor -----------------------------------------------------------------------------------------------------------------
    def ecrire_reglages(self, texte: str) -> None:
        (self.flux / "flux.yaml").write_text(texte, encoding="utf-8")

    def codes(self, **codes) -> None:
        """Codes de sortie des faux outils : codes(flow_import=1), ou avec « : » via un dictionnaire (voir codes_de)."""
        self.codes_de({k.replace("__", ":"): v for k, v in codes.items()})

    def codes_de(self, codes: dict) -> None:
        (self.racine / "codes.json").write_text(json.dumps(codes), encoding="utf-8")

    def sortie_retention(self, texte: str) -> None:
        """Ce que le faux outil de rétention imprime (par défaut : « rien hors règle » dans la langue demandée)."""
        (self.racine / "retention-sortie.txt").write_text(texte, encoding="utf-8")

    def resume_ecrit(self, jour: str, final: str, lignes: str = "") -> Path:
        """Un résumé déjà présent (écrit à la main, au format de l'orchestrateur)."""
        chemin = self.rapports / f"suivi-mensuel-{jour}.md"
        chemin.write_text(f"# Monthly flow run\n\n- run date: {jour}\n- final status: {final}\n\n"
                          f"| step | series | status | exit code | seconds |\n|---|---|---|---|---|\n{lignes}", encoding="utf-8")
        return chemin

    # --- lancement ---------------------------------------------------------------------------------------------------------------
    def lancer(self, *argv: str, env: dict | None = None) -> Resultat:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(sortie):
            code = fm.main(list(argv), environ=self.env if env is None else env)
        return Resultat(code, sortie.getvalue())

    def lancer_en(self, *argv: str) -> Resultat:
        return self.lancer("--language", "en", *argv)

    def appels(self) -> list[dict]:
        chemin = self.racine / "appels.jsonl"
        if not chemin.exists():
            return []
        return [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l]

    def outils_appeles(self) -> list[str]:
        return [a["outil"] for a in self.appels()]

    def resume(self, jour: str | None = None) -> str:
        return (self.rapports / f"suivi-mensuel-{jour or aujourdhui()}.md").read_text(encoding="utf-8")

    def toute_la_sortie_et_le_resume(self, resultat: Resultat) -> str:
        textes = [resultat.sortie]
        textes += [p.read_text(encoding="utf-8") for p in self.rapports.glob("suivi-mensuel-*.md")]
        return "\n".join(textes)
