"""
Tests de tools/gh_issue.py : sous-commande set-owner (propriétaire d'une tâche existante : owner:user OU model:<m>) et options
--owner / --model de new-task (R-148/u11). Même faux gh que test_gh_issue.py. Une tâche d'agent porte un libellé model:<m>,
une tâche de l'utilisateur owner:user, jamais les deux ni aucun (règle de `roadmap.py check`).

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import json
import unittest
from pathlib import Path

from test_gh_issue import Base
import roadmap
import roadmap_model as rm


class Verifie:
    """Rejoue la règle « un seul model: ou owner:user » de `roadmap.py check` sur l'état du faux dépôt."""

    def problemes_sous_issues(self, feature_n=1):
        st = self.load()
        feature = next(i for i in st["issues"] if i["body"].startswith(f"<!-- roadmap-id: R-{feature_n} -->"))
        issues = []
        for i in st["issues"]:
            if i["body"].startswith("<!-- roadmap-idea"):
                continue
            cle = rm.parse_marker(i["body"])
            est_sous = bool(cle) and cle.startswith(f"R-{feature_n}/")
            issues.append({"number": i["number"], "title": i["title"], "body": i["body"], "state": i["state"], "reason": "",
                           "labels": [l["name"] for l in i["labels"]], "milestone": None,
                           "parent": feature["number"] if est_sous else None, "blocked_by": [], "status": None})
        pb = roadmap.analyse_github(issues)[2]
        return [p for p in pb if p.startswith(f"R-{feature_n}/")]


class SetOwner(Verifie, Base):
    def setUp(self):
        super().setUp()
        self.add_feature(1)
        self.add_issue("R-1/g1", "R-1 · 1. Groupe", ["type:task", "owner:user"])
        self.add_issue("R-1/g2", "R-1 · 2. Groupe", ["type:task", "model:sonnet"])
        self.add_issue("R-1/u1", "R-1 · Étape", ["type:task", "owner:user", "product:mothra"])
        self.add_issue("R-1/g3", "R-1 · 3. Fermé", ["type:task", "owner:user"], state="closed")
        self.add_issue("#idee", "Une idée", ["type:idea"], body="<!-- roadmap-idea -->\n\ntexte")
        self.st = self.load()
        self.st["labels"] = [{"name": n} for n in ("owner:user", "model:opus", "model:sonnet", "model:haiku")]
        self.save()

    def labels(self, key):
        return sorted(l["name"] for l in self.issue(key)["labels"])

    def test_agent_pose_model_et_retire_owner_user(self):
        code, out, err = self.run_cli("set-owner", "R-1/u1", "--owner", "agent", "--model", "opus")
        self.assertEqual(code, 0, err)
        self.assertIn("gh_issue: set owner of R-1/u1 (#", out)
        self.assertEqual(self.labels("R-1/u1"), ["model:opus", "product:mothra", "type:task"])

    def test_agent_remplace_un_autre_model(self):
        code, _, err = self.run_cli("set-owner", "R-1/g2", "--owner", "agent", "--model", "haiku")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.labels("R-1/g2"), ["model:haiku", "type:task"])

    def test_agent_retire_tous_les_model_et_owner_user_en_trop(self):
        self.st = self.load()
        for i in self.st["issues"]:
            if i["body"].startswith("<!-- roadmap-id: R-1/g1 -->"):
                i["labels"] = [{"name": n} for n in ("type:task", "owner:user", "model:opus", "model:haiku")]
        self.save()
        code, _, err = self.run_cli("set-owner", "R-1/g1", "--owner", "agent", "--model", "sonnet")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.labels("R-1/g1"), ["model:sonnet", "type:task"])

    def test_user_pose_owner_user_et_retire_les_model(self):
        code, _, err = self.run_cli("set-owner", "R-1/g2", "--owner", "user")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.labels("R-1/g2"), ["owner:user", "type:task"])

    def test_model_obligatoire_avec_agent(self):
        code, _, err = self.run_cli("set-owner", "R-1/u1", "--owner", "agent")
        self.assertEqual(code, 2)
        self.assertIn("usage", err)
        self.assertIn("--model", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_model_refuse_avec_user(self):
        code, _, err = self.run_cli("set-owner", "R-1/g2", "--owner", "user", "--model", "sonnet")
        self.assertEqual(code, 2)
        self.assertIn("usage", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_model_hors_liste(self):
        code, _, err = self.run_cli("set-owner", "R-1/u1", "--owner", "agent", "--model", "gpt")
        self.assertEqual(code, 2)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_idempotente_rien_ecrit(self):
        for key, argv in (("R-1/g1", ("--owner", "user")), ("R-1/g2", ("--owner", "agent", "--model", "sonnet"))):
            code, out, err = self.run_cli("set-owner", key, *argv)
            self.assertEqual(code, 0, err)
            self.assertIn("nothing to do", out)
            self.assertIn(f"already owned by {argv[1]}", out)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_changer_de_model_n_est_pas_idempotent(self):
        code, out, _ = self.run_cli("set-owner", "R-1/g2", "--owner", "agent", "--model", "opus")
        self.assertEqual(code, 0)
        self.assertNotIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), 1)

    def test_relance_ne_reecrit_pas(self):
        self.run_cli("set-owner", "R-1/g1", "--owner", "agent", "--model", "sonnet")
        n = len(self.calls(writes_only=True))
        code, out, _ = self.run_cli("set-owner", "R-1/g1", "--owner", "agent", "--model", "sonnet")
        self.assertEqual(code, 0)
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_refus_feature_idee_et_cle_mal_formee(self):
        for ref in ("R-1", "#idee", "7", "x", "R-1/z9"):
            code, _, err = self.run_cli("set-owner", ref, "--owner", "agent", "--model", "sonnet")
            self.assertEqual(code, 2, ref)
            self.assertIn("usage", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_refus_valeur_hors_liste_ou_absente(self):
        for argv in (("set-owner", "R-1/g1", "--owner", "robot"), ("set-owner", "R-1/g1")):
            code, _, err = self.run_cli(*argv)
            self.assertEqual(code, 2)
            self.assertIn("usage", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_refus_tache_fermee(self):
        code, _, err = self.run_cli("set-owner", "R-1/g3", "--owner", "agent", "--model", "sonnet")
        self.assertEqual(code, 2)
        self.assertIn("closed", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_tache_inconnue_code_7(self):
        code, _, _ = self.run_cli("set-owner", "R-1/u9", "--owner", "agent", "--model", "sonnet")
        self.assertEqual(code, 7)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_une_seule_ecriture_et_uniquement_les_libelles(self):
        self.run_cli("set-owner", "R-1/u1", "--owner", "agent", "--model", "sonnet")
        ecritures = self.calls(writes_only=True)
        self.assertEqual(len(ecritures), 1)
        self.assertIn("PATCH", ecritures[0]["args"])
        self.assertEqual(list(json.loads(ecritures[0]["stdin"])), ["labels"])
        issue = self.issue("R-1/u1")
        self.assertEqual(issue["title"], "R-1 · Étape")
        self.assertEqual(issue["state"], "open")

    def test_garde_tous_les_autres_libelles_dans_la_charge_envoyee(self):
        autres = ["type:task", "value:2", "product:mothra", "theme:outillage", "edition:public", "parallel"]
        self.add_issue("R-1/g4", "R-1 · 4. Riche", autres + ["owner:user"])
        self.st = self.load()
        self.st["labels"] += [{"name": n} for n in autres]
        self.save()
        code, _, err = self.run_cli("set-owner", "R-1/g4", "--owner", "agent", "--model", "haiku")
        self.assertEqual(code, 0, err)
        charge = json.loads(self.calls(writes_only=True)[-1]["stdin"])
        self.assertEqual(sorted(charge["labels"]), sorted(autres + ["model:haiku"]))
        code, _, err = self.run_cli("set-owner", "R-1/g4", "--owner", "user")
        self.assertEqual(code, 0, err)
        charge = json.loads(self.calls(writes_only=True)[-1]["stdin"])
        self.assertEqual(sorted(charge["labels"]), sorted(autres + ["owner:user"]))
        self.assertEqual(self.labels("R-1/g4"), sorted(autres + ["owner:user"]))

    def test_libelle_absent_du_depot_une_creation_puis_l_ecriture_de_l_issue(self):
        self.st = self.load()
        self.st["labels"] = []
        self.save()
        code, _, err = self.run_cli("set-owner", "R-1/u1", "--owner", "agent", "--model", "opus")
        self.assertEqual(code, 0, err)
        ecritures = self.calls(writes_only=True)
        self.assertEqual(len(ecritures), 2)
        self.assertTrue(ecritures[0]["args"][-3].endswith("/labels"))
        self.assertEqual(json.loads(ecritures[0]["stdin"])["name"], "model:opus")
        self.assertIn("PATCH", ecritures[1]["args"])
        self.assertEqual(list(json.loads(ecritures[1]["stdin"])), ["labels"])
        # owner:user absent du dépôt, côté user
        self.st = self.load()
        self.st["labels"] = []
        self.save()
        n = len(self.calls(writes_only=True))
        self.assertEqual(self.run_cli("set-owner", "R-1/u1", "--owner", "user")[0], 0)
        nouvelles = self.calls(writes_only=True)[n:]
        self.assertEqual(len(nouvelles), 2)
        self.assertEqual(json.loads(nouvelles[0]["stdin"])["name"], "owner:user")

    def test_libelle_present_du_depot_aucune_creation(self):
        self.run_cli("set-owner", "R-1/u1", "--owner", "agent", "--model", "opus")
        self.assertEqual(len(self.calls(writes_only=True)), 1)

    def test_pas_d_appel_gh_hors_outil_partage(self):
        src = (Path(__file__).resolve().parents[2] / "tools" / "gh_issue.py").read_text(encoding="utf-8")
        debut = src.index("def cmd_set_owner")
        corps = src[debut:src.index("\ndef ", debut + 10)]
        self.assertNotIn("subprocess", corps)
        self.assertNotIn("gh_run", corps)
        self.assertIn("patch_issue", corps)

    # GitHub ne distingue pas la casse des libellés
    def test_casse_un_model_existant_est_retire_jamais_garde_a_cote(self):
        self.add_issue("R-1/g6", "R-1 · 6. Casse", ["type:task", "Model:Opus"])
        code, _, err = self.run_cli("set-owner", "R-1/g6", "--owner", "agent", "--model", "haiku")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.labels("R-1/g6"), ["model:haiku", "type:task"])

    def test_casse_owner_user_en_majuscules_retire_cote_agent(self):
        self.add_issue("R-1/g7", "R-1 · 7. Casse", ["type:task", "Owner:User"])
        code, _, err = self.run_cli("set-owner", "R-1/g7", "--owner", "agent", "--model", "opus")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.labels("R-1/g7"), ["model:opus", "type:task"])

    def test_casse_meme_proprietaire_a_la_casse_pres_rien_a_faire(self):
        self.add_issue("R-1/g8", "R-1 · 8. Casse", ["type:task", "Model:Opus"])
        code, _, err = self.run_cli("set-owner", "R-1/g8", "--owner", "agent", "--model", "opus")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.labels("R-1/g8"), ["model:opus", "type:task"])

    def test_casse_libelle_du_depot_d_une_autre_casse_n_est_pas_recree(self):
        self.st = self.load()
        self.st["labels"] = [{"name": "Model:opus"}]
        self.save()
        code, _, err = self.run_cli("set-owner", "R-1/u1", "--owner", "agent", "--model", "opus")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(self.calls(writes_only=True)), 1)

    def test_casse_roadmap_check_voit_model_en_majuscule_comme_proprietaire(self):
        self.add_issue("R-1/g9", "R-1 · 9. Casse", ["type:task", "Model:Opus"])
        self.assertEqual([p for p in self.problemes_sous_issues() if "R-1/g9" in p], [])
        self.add_issue("R-1/g10", "R-1 · 10. Casse", ["type:task", "Owner:User", "model:opus"])
        self.assertTrue(any("R-1/g10" in p for p in self.problemes_sous_issues()))

    def test_casse_close_step_reconnait_owner_user_en_majuscules(self):
        self.add_issue("R-1/g11", "R-1 · 11. Casse", ["type:task", "Owner:User"])
        code, out, err = self.run_cli("close-step", "R-1/g11")
        self.assertEqual(code, 0, err)
        self.assertIn("closed R-1/g11", out)

    # croisé avec `roadmap.py check`
    def test_set_owner_puis_check_valide_dans_les_deux_sens(self):
        self.assertEqual(self.problemes_sous_issues(), [])
        self.assertEqual(self.run_cli("set-owner", "R-1/g1", "--owner", "agent", "--model", "sonnet")[0], 0)
        self.assertEqual(self.problemes_sous_issues(), [])
        self.assertEqual(self.run_cli("set-owner", "R-1/g2", "--owner", "user")[0], 0)
        self.assertEqual(self.problemes_sous_issues(), [])
        self.assertEqual(self.labels("R-1/g1"), ["model:sonnet", "type:task"])
        self.assertEqual(self.labels("R-1/g2"), ["owner:user", "type:task"])

    def test_le_controle_croise_voit_bien_une_tache_sans_proprietaire(self):
        self.add_issue("R-1/g5", "R-1 · 5. Sans", ["type:task"])
        self.assertTrue(any("R-1/g5" in p for p in self.problemes_sous_issues()))


class NewTaskOwner(Verifie, Base):
    def setUp(self):
        super().setUp()
        self.body_file = Path(self.tmp.name) / "tache.md"
        self.body_file.write_text("Texte.\n", encoding="utf-8")
        self.add_feature(1)

    def task(self, *extra):
        return self.run_cli("new-task", "R-1", "--title", "Une tâche", "--body-file", str(self.body_file), *extra)

    def labels(self, key):
        return sorted(l["name"] for l in self.issue(key)["labels"])

    def test_defaut_owner_user(self):
        self.assertEqual(self.task()[0], 0)
        self.assertEqual(self.labels("R-1/u1"), ["owner:user", "type:task"])

    def test_owner_user_explicite(self):
        self.assertEqual(self.task("--owner", "user")[0], 0)
        self.assertEqual(self.labels("R-1/u1"), ["owner:user", "type:task"])

    def test_owner_agent_avec_model(self):
        code, _, err = self.task("--owner", "agent", "--model", "sonnet")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.labels("R-1/u1"), ["model:sonnet", "type:task"])

    def test_owner_agent_sans_model_refuse_rien_cree(self):
        code, _, err = self.task("--owner", "agent")
        self.assertEqual(code, 2)
        self.assertIn("--model", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_model_avec_owner_user_refuse(self):
        for extra in (("--model", "sonnet"), ("--owner", "user", "--model", "sonnet")):
            code, _, err = self.task(*extra)
            self.assertEqual(code, 2, extra)
            self.assertIn("usage", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_owner_hors_liste_code_2(self):
        code, _, err = self.task("--owner", "robot")
        self.assertEqual(code, 2)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_relance_meme_titre_autre_owner_ne_change_pas_le_proprietaire_et_le_dit(self):
        self.assertEqual(self.task("--owner", "user")[0], 0)
        n = len(self.calls(writes_only=True))
        code, out, err = self.task("--owner", "agent", "--model", "opus")
        self.assertEqual(code, 0, err)
        self.assertIn("already exists", out)
        self.assertIn("set-owner", out)
        self.assertEqual(self.labels("R-1/u1"), ["owner:user", "type:task"])
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_new_task_agent_puis_check_valide(self):
        self.assertEqual(self.task("--owner", "agent", "--model", "haiku")[0], 0)
        self.assertEqual(self.problemes_sous_issues(), [])
        self.assertEqual(self.labels("R-1/u1"), ["model:haiku", "type:task"])


class ProprietairesModele(unittest.TestCase):
    def test_liste_fermee_partagee(self):
        self.assertEqual(rm.OWNERS, ("user", "agent"))


if __name__ == "__main__":
    unittest.main()
