"""
Tests de tools/gh_issue.py : sous-commande edit-task (jalon d'une seule tâche existante, R-148/u12). Même faux gh que test_gh_issue.py.
Règle de `roadmap.py check` (analyse_github) : une tâche n'a pas à partager le jalon de sa feature ; seule une issue ouverte dans un
jalon fermé est un problème. edit-task refuse donc un jalon fermé (code 7, comme edit) et ne touche ni la feature ni les autres tâches.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import json
import unittest
from pathlib import Path

from test_gh_issue import Base
import roadmap
import roadmap_model as rm


class EditTask(Base):
    def setUp(self):
        super().setUp()
        self.add_feature(1, status="Todo")
        self.st = self.load()
        self.add_issue("R-1/g1", "R-1 · 1. Groupe", ["type:task", "owner:user"], milestone="Hydra")
        self.add_issue("R-1/t1.1", "R-1 · 1.1 Tâche", ["type:task", "owner:user"], milestone="Hydra")
        self.add_issue("R-1/u1", "R-1 · Étape", ["type:task", "owner:user", "product:mothra"], milestone="Hydra")
        self.add_issue("R-1/u2", "R-1 · Autre", ["type:task", "owner:user"], milestone="Hydra")
        self.add_issue("R-1/g3", "R-1 · 3. Fermé", ["type:task", "owner:user"], state="closed", milestone="Hydra")
        self.add_issue("#idee", "Une idée", ["type:idea"], body="<!-- roadmap-idea -->\n\ntexte", milestone="Hydra")
        self.st = self.load()
        feature = self.number_of("R-1")
        self.st["sub"] = {str(feature): [self.number_of(k) for k in ("R-1/g1", "R-1/t1.1", "R-1/u1", "R-1/u2", "R-1/g3")]}
        self.save()

    def liens(self):
        return {k: sorted(v) for k, v in self.load().get("sub", {}).items()}

    def verifie(self):
        """`roadmap.py check` (analyse_github) rejoué sur l'état du faux dépôt, jalons compris."""
        st = self.load()
        etat = {m["title"]: m["state"] for m in st["milestones"]}
        liens = {n: int(p) for p, subs in st.get("sub", {}).items() for n in subs}
        issues = []
        for i in st["issues"]:
            if i["body"].startswith("<!-- roadmap-idea"):
                continue
            m = i["milestone"]
            issues.append({"number": i["number"], "title": i["title"], "body": i["body"], "state": i["state"], "reason": "",
                           "labels": [l["name"] for l in i["labels"]],
                           "milestone": {"title": m["title"], "state": etat[m["title"]]} if m else None,
                           "parent": liens.get(i["number"]), "blocked_by": [],
                           "status": next((x["status"] for x in st["project"]["items"] if x["number"] == i["number"]), None)})
        return roadmap.analyse_github(issues)[2]

    def test_deplace_une_tache_seule(self):
        code, out, err = self.run_cli("edit-task", "R-1/u1", "--milestone", "Namazu")
        self.assertEqual(code, 0, err)
        self.assertIn("gh_issue: moved R-1/u1 (#", out)
        self.assertEqual(self.milestone_of("R-1/u1"), "Namazu")
        for autre in ("R-1", "R-1/g1", "R-1/t1.1", "R-1/u2", "R-1/g3"):
            self.assertEqual(self.milestone_of(autre), "Hydra", autre)

    def test_le_deplacement_tient_jusqu_a_ce_que_la_feature_bouge(self):
        self.st = self.load()
        self.st["milestones"].append({"number": 4, "title": "Cerberus", "state": "open"})
        self.save()
        self.assertEqual(self.run_cli("edit-task", "R-1/u1", "--milestone", "Namazu")[0], 0)
        self.assertEqual(self.milestone_of("R-1/u1"), "Namazu")
        code, _, err = self.run_cli("edit", "R-1", "--milestone", "Cerberus")
        self.assertEqual(code, 0, err)
        for cle in ("R-1", "R-1/u1", "R-1/g1", "R-1/t1.1", "R-1/u2"):
            self.assertEqual(self.milestone_of(cle), "Cerberus", cle)

    def test_une_seule_ecriture_qui_ne_porte_que_le_jalon(self):
        self.run_cli("edit-task", "R-1/u1", "--milestone", "Namazu")
        ecritures = self.calls(writes_only=True)
        self.assertEqual(len(ecritures), 1)
        self.assertIn("PATCH", ecritures[0]["args"])
        self.assertEqual(list(json.loads(ecritures[0]["stdin"])), ["milestone"])
        self.assertEqual(self.milestone_writes(), [(self.number_of("R-1/u1"), 2)])
        issue = self.issue("R-1/u1")
        self.assertEqual(issue["title"], "R-1 · Étape")
        self.assertEqual(issue["state"], "open")
        self.assertEqual(sorted(l["name"] for l in issue["labels"]), ["owner:user", "product:mothra", "type:task"])

    def test_lien_de_sous_issue_intact(self):
        avant = self.liens()
        self.assertTrue(avant)
        self.assertEqual(self.run_cli("edit-task", "R-1/u1", "--milestone", "Namazu")[0], 0)
        self.assertEqual(self.liens(), avant)
        self.assertFalse(any("sub_issue" in " ".join(c["args"]) for c in self.calls(writes_only=True)))

    def test_idempotente_rien_ecrit(self):
        code, out, err = self.run_cli("edit-task", "R-1/u1", "--milestone", "Hydra")
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_relance_ne_reecrit_pas(self):
        self.run_cli("edit-task", "R-1/u1", "--milestone", "Namazu")
        n = len(self.calls(writes_only=True))
        code, out, _ = self.run_cli("edit-task", "R-1/u1", "--milestone", "Namazu")
        self.assertEqual(code, 0)
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_tache_sans_jalon_en_recoit_un(self):
        self.add_issue("R-1/u3", "R-1 · Sans jalon", ["type:task", "owner:user"])
        self.assertEqual(self.run_cli("edit-task", "R-1/u3", "--milestone", "Namazu")[0], 0)
        self.assertEqual(self.milestone_of("R-1/u3"), "Namazu")

    def test_refus_feature_idee_et_cle_mal_formee(self):
        for ref in ("R-1", "#idee", "7", "x", "R-1/z9"):
            code, _, err = self.run_cli("edit-task", ref, "--milestone", "Namazu")
            self.assertEqual(code, 2, ref)
            self.assertIn("edit-task expects a task key", err, ref)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_refus_tache_fermee(self):
        code, _, err = self.run_cli("edit-task", "R-1/g3", "--milestone", "Namazu")
        self.assertEqual(code, 2)
        self.assertIn("closed", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_cle_inconnue_code_7(self):
        code, _, _ = self.run_cli("edit-task", "R-1/u9", "--milestone", "Namazu")
        self.assertEqual(code, 7)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_jalon_inconnu_code_7_nomme_rien_ecrit_ni_cree(self):
        code, _, err = self.run_cli("edit-task", "R-1/u1", "--milestone", "Inconnu")
        self.assertEqual(code, 7)
        self.assertIn("unknown milestone", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_jalon_ferme_refuse_code_7(self):
        code, _, err = self.run_cli("edit-task", "R-1/u1", "--milestone", "Tarasque")
        self.assertEqual(code, 7)
        self.assertIn("closed milestone", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_jalon_obligatoire(self):
        code, _, err = self.run_cli("edit-task", "R-1/u1")
        self.assertEqual(code, 2)
        self.assertIn("--milestone", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_pas_d_appel_gh_hors_outil_partage(self):
        src = (Path(__file__).resolve().parents[2] / "tools" / "gh_issue.py").read_text(encoding="utf-8")
        debut = src.index("def cmd_edit_task")
        corps = src[debut:src.index("\ndef ", debut + 10)]
        self.assertNotIn("subprocess", corps)
        self.assertNotIn("gh_run", corps)
        self.assertIn("set_milestone", corps)

    # croisé avec `roadmap.py check` (analyse_github)
    def test_check_valide_apres_le_deplacement(self):
        self.assertEqual(self.verifie(), [])
        self.assertEqual(self.run_cli("edit-task", "R-1/u1", "--milestone", "Namazu")[0], 0)
        self.assertEqual(self.milestone_of("R-1"), "Hydra")
        self.assertEqual(self.verifie(), [])

    def test_le_controle_croise_voit_bien_une_tache_ouverte_dans_un_jalon_ferme(self):
        self.st = self.load()
        next(i for i in self.st["issues"] if i["body"].startswith("<!-- roadmap-id: R-1/u2 -->")).update(
            milestone={"title": "Tarasque", "number": 3})
        self.save()
        self.assertTrue(any("jalon fermé Tarasque" in p for p in self.verifie()), self.verifie())


if __name__ == "__main__":
    unittest.main()
