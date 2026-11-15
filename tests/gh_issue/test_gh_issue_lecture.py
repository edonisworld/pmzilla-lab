"""
Tests de tools/gh_issue.py : sous-commandes de lecture `view` et `list` (niveau 2 du bac à sable, tâche 7.8 ; R-20261109-12, réponse 1).
Le faux `gh` est un exécutable écrit par le test dans son dossier temporaire : il ne répond qu'à une requête GraphQL de lecture, note chaque
appel dans un journal et fait échouer la commande (code 97, appel noté « écriture ») pour toute autre forme, mutation comprise. Les tests
exigent que le journal ne contienne aucune écriture : les lectures n'écrivent jamais sur GitHub.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import json
import os
import stat
import sys
import unittest
from pathlib import Path
from unittest import mock

from test_gh_issue import Base, g, rm

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import roadmap  # noqa: E402

FAUX_GH = """#!{python}
import json, os, sys
args = sys.argv[1:]
entree = sys.stdin.read() if not sys.stdin.isatty() else ""
try:
    requete = json.loads(entree or "{{}}")
except ValueError:
    requete = {{}}
texte = (requete.get("query") or "")
ecriture = not (args[:1] == ["api"] and "graphql" in args and "mutation" not in texte.lower())
with open(os.environ["FAKE_LECTURE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({{"args": args, "ecriture": ecriture, "variables": requete.get("variables")}}) + "\\n")
if ecriture:
    sys.stderr.write("faux gh : forme d'écriture refusée\\n")
    sys.exit(97)
mode = os.environ.get("FAKE_LECTURE_MODE", "")
if mode == "hors_ligne":
    sys.stderr.write("error connecting to api.github.com\\n")
    sys.exit(1)
if mode == "erreurs":
    sys.stdout.write("HTTP/2.0 200 OK\\r\\n\\r\\n" + json.dumps({{"errors": [{{"message": "texte du serveur"}}]}}))
    sys.exit(0)
data = json.load(open(os.environ["FAKE_LECTURE_DATA"], encoding="utf-8"))
taille = int(os.environ.get("FAKE_LECTURE_PAGE", "100"))
debut = int((requete.get("variables") or {{}}).get("after") or 0)
fin = debut + taille
jalons = {{}}
for n in data:
    if n.get("milestone"):
        jalons[n["milestone"]["title"]] = n["milestone"]["state"]
jalons.update(json.loads(os.environ.get("FAKE_LECTURE_JALONS") or "{{}}"))
corps = {{"data": {{"repository": {{"milestones": {{"nodes": [{{"title": t, "state": e}} for t, e in jalons.items()]}},
         "issues": {{"pageInfo": {{"hasNextPage": fin < len(data), "endCursor": str(fin)}}, "nodes": data[debut:fin]}}}}}}}}
sys.stdout.write("HTTP/2.0 200 OK\\r\\nContent-Type: application/json\\r\\n\\r\\n" + json.dumps(corps))
"""


def noeud(numero, titre, etiquettes, *, cle=None, state="OPEN", jalon=None, jalon_state="OPEN", parent=None, statut=None):
    corps = (rm.marker(cle) + "\n\ntexte") if cle else "texte libre"
    return {
        "number": numero, "title": titre, "body": corps, "state": state, "stateReason": "COMPLETED" if state == "CLOSED" else None,
        "labels": {"nodes": [{"name": e} for e in etiquettes]},
        "milestone": {"title": jalon, "state": jalon_state} if jalon else None,
        "parent": {"number": parent} if parent else None, "blockedBy": {"nodes": []},
        "projectItems": {"nodes": [{"project": {"title": g.PROJECT_TITLE}, "fieldValueByName": {"name": statut}}] if statut else []},
    }


class Lecture(Base):
    REEL = True      # le faux gh de la lecture est un vrai exécutable

    def setUp(self):
        super().setUp()
        self.dossier = Path(self.tmp.name)
        self.journal = self.dossier / "lecture.log"
        self.donnees = self.dossier / "lecture.json"
        exe = self.dossier / "faux_gh_lecture"
        exe.write_text(FAUX_GH.format(python=sys.executable), encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
        env = {"PMZILLA_GH": str(exe), "FAKE_LECTURE_LOG": str(self.journal), "FAKE_LECTURE_DATA": str(self.donnees),
               "FAKE_LECTURE_MODE": "", "FAKE_LECTURE_PAGE": "100", "FAKE_LECTURE_JALONS": ""}
        p = mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)
        self.sortie = self.dossier / "sortie.json"
        self.donne(
            noeud(1, "R-1 · Une feature", ["type:feature", "theme:outillage"], cle="R-1", jalon="Hydra", statut="Ready"),
            noeud(2, "R-2 · Une autre", ["type:feature", "theme:base", "product:mothra"], cle="R-2", state="CLOSED", jalon="Hydra"),
            noeud(3, "R-1 · Étape", ["type:task", "owner:user"], cle="R-1/u1", jalon="Namazu", parent=1),
            noeud(4, "Une idée", ["type:idea"], jalon=None),
            noeud(5, "R-5 · Fermée ailleurs", ["type:feature", "theme:base"], cle="R-5", state="CLOSED", jalon="Tarasque",
                  jalon_state="CLOSED"))

    def donne(self, *noeuds):
        self.donnees.write_text(json.dumps(list(noeuds)), encoding="utf-8")

    def appels(self):
        return [json.loads(l) for l in self.journal.read_text(encoding="utf-8").splitlines()] if self.journal.exists() else []

    def lu(self):
        return json.loads(self.sortie.read_text(encoding="utf-8"))

    def numeros(self):
        return [i["number"] for i in self.lu()["issues"]]

    # --- list ---------------------------------------------------------------------------------------------------------

    def test_list_ecrit_le_json_dans_le_fichier_de_sortie(self):
        code, out, err = self.run_cli("list", "--sortie", str(self.sortie))
        self.assertEqual(code, 0, err)
        self.assertEqual(out.strip(), "gh_issue: wrote 5 issue(s)")
        self.assertNotIn(str(self.sortie), out + err)            # jamais le chemin
        d = self.lu()
        self.assertEqual(self.numeros(), [1, 2, 3, 4, 5])
        self.assertEqual(d["milestones"], {"Hydra": "open", "Namazu": "open", "Tarasque": "closed"})
        un = d["issues"][0]
        self.assertEqual(set(un), {"number", "title", "body", "state", "reason", "labels", "milestone", "parent", "blocked_by", "status"})
        self.assertEqual((un["status"], un["state"], un["milestone"]), ("Ready", "open", {"title": "Hydra", "state": "open"}))
        self.assertEqual(d["issues"][2]["parent"], 1)

    def test_list_filtre_par_jalon_etat_et_libelles(self):
        self.assertEqual(self.run_cli("list", "--milestone", "Hydra", "--sortie", str(self.sortie))[0], 0)
        self.assertEqual(self.numeros(), [1, 2])
        self.assertEqual(self.run_cli("list", "--state", "closed", "--sortie", str(self.sortie))[0], 0)
        self.assertEqual(self.numeros(), [2, 5])
        self.assertEqual(self.run_cli("list", "--state", "open", "--milestone", "Hydra", "--sortie", str(self.sortie))[0], 0)
        self.assertEqual(self.numeros(), [1])
        self.assertEqual(self.run_cli("list", "--label", "type:feature", "--label", "product:mothra", "--sortie", str(self.sortie))[0], 0)
        self.assertEqual(self.numeros(), [2])
        self.assertEqual(self.run_cli("list", "--label", "type:idea", "--sortie", str(self.sortie))[0], 0)
        self.assertEqual(self.numeros(), [4])

    def test_list_filtre_ne_retire_pas_les_jalons(self):
        self.run_cli("list", "--milestone", "Hydra", "--sortie", str(self.sortie))
        self.assertEqual(set(self.lu()["milestones"]), {"Hydra", "Namazu", "Tarasque"})

    def test_list_filtre_vide_ecrit_un_fichier_vide_de_issues(self):
        code, out, err = self.run_cli("list", "--milestone", "Inconnu", "--sortie", str(self.sortie))
        self.assertEqual(code, 0, err)
        self.assertEqual(self.lu()["issues"], [])
        self.assertIn("wrote 0 issue(s)", out)

    def test_list_pagine(self):
        os.environ["FAKE_LECTURE_PAGE"] = "2"
        self.assertEqual(self.run_cli("list", "--sortie", str(self.sortie))[0], 0)
        self.assertEqual(self.numeros(), [1, 2, 3, 4, 5])
        self.assertEqual(len(self.appels()), 3)
        self.assertEqual([a["variables"]["after"] for a in self.appels()], [None, "2", "4"])

    def test_list_sans_sortie_imprime_le_json_sur_la_sortie_standard(self):
        code, out, err = self.run_cli("list", "--milestone", "Namazu")
        self.assertEqual(code, 0, err)
        d = json.loads(out)
        self.assertEqual([i["number"] for i in d["issues"]], [3])

    def test_list_sortie_inecrivable_code_2(self):
        code, _, err = self.run_cli("list", "--sortie", str(self.dossier))      # un dossier
        self.assertEqual(code, 2)
        self.assertIn("--sortie", err)

    def test_list_etat_inconnu_code_2(self):
        self.assertEqual(self.run_cli("list", "--state", "brouillon")[0], 2)

    # --- view ---------------------------------------------------------------------------------------------------------

    def test_view_par_numero_dieze_et_cle(self):
        for ref, attendu in (("1", 1), ("#3", 3), ("R-2", 2), ("R-1/u1", 3), ("R-1", 1)):
            code, out, err = self.run_cli("view", ref, "--sortie", str(self.sortie))
            self.assertEqual(code, 0, f"{ref}: {err}")
            self.assertEqual(out.strip(), "gh_issue: wrote 1 issue(s)")
            self.assertEqual(self.numeros(), [attendu], ref)
            self.assertIn("milestones", self.lu())

    def test_view_inconnue_code_7(self):
        for ref in ("99", "R-99", "R-1/u9"):
            code, _, err = self.run_cli("view", ref, "--sortie", str(self.sortie))
            self.assertEqual(code, 7, ref)
            self.assertIn(f"unknown issue {ref}", err)
        self.assertFalse(self.sortie.exists())

    def test_view_reference_mal_formee_code_2(self):
        for ref in ("abc", "R-", "R-1/x2", "1; rm", ""):
            code, _, _ = self.run_cli("view", ref)
            self.assertEqual(code, 2, repr(ref))
        self.assertEqual(self.appels(), [])      # la forme est refusée avant tout appel

    def test_view_sans_sortie_imprime_le_json(self):
        code, out, err = self.run_cli("view", "R-5")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["issues"][0]["number"], 5)

    # --- aucune écriture ----------------------------------------------------------------------------------------------

    def test_aucune_ecriture_sur_github(self):
        self.run_cli("list", "--sortie", str(self.sortie))
        self.run_cli("view", "R-1", "--sortie", str(self.sortie))
        self.run_cli("view", "R-99")
        appels = self.appels()
        self.assertTrue(appels)
        for a in appels:
            self.assertFalse(a["ecriture"], a)
            self.assertIn("graphql", a["args"])
            self.assertNotIn("-X", a["args"])
            self.assertNotIn("--method", a["args"])

    def test_les_lectures_ne_posent_ni_ne_chargent_le_garde_fou_d_ecriture(self):
        """Une lecture ne passe pas par `send` ni par `graphql_write` : aucune de ces deux méthodes n'est appelée."""
        with mock.patch.object(g.Client, "send", side_effect=AssertionError("écriture")), \
                mock.patch.object(g.Client, "graphql_write", side_effect=AssertionError("écriture")):
            self.assertEqual(self.run_cli("list", "--sortie", str(self.sortie))[0], 0)
            self.assertEqual(self.run_cli("view", "1", "--sortie", str(self.sortie))[0], 0)

    # --- erreurs de GitHub --------------------------------------------------------------------------------------------

    def test_gh_hors_ligne_code_5_sans_ecriture(self):
        os.environ["FAKE_LECTURE_MODE"] = "hors_ligne"
        code, _, err = self.run_cli("list", "--sortie", str(self.sortie))
        self.assertEqual(code, 5, err)
        self.assertFalse(self.sortie.exists())

    def test_erreur_dans_le_corps_refusee_sans_citer_le_texte(self):
        os.environ["FAKE_LECTURE_MODE"] = "erreurs"
        code, out, err = self.run_cli("list", "--sortie", str(self.sortie))
        self.assertEqual(code, 1)
        self.assertNotIn("texte du serveur", out + err)
        self.assertFalse(self.sortie.exists())

    # --- accord avec le lecteur de la file ----------------------------------------------------------------------------

    def test_le_fichier_est_lu_tel_quel_par_le_lecteur(self):
        self.run_cli("list", "--sortie", str(self.sortie))
        issues, jalons = roadmap.lecture_fichier(self.sortie)
        self.assertEqual([i["number"] for i in issues], [1, 2, 3, 4, 5])
        self.assertEqual(jalons["Tarasque"], "closed")
        self.assertEqual(issues[0], roadmap.normalise(self.donnees_noeud(1)))

    def donnees_noeud(self, numero):
        return next(n for n in json.loads(self.donnees.read_text(encoding="utf-8")) if n["number"] == numero)


if __name__ == "__main__":
    unittest.main()
